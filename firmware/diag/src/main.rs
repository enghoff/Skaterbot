//! The controller as the Banana Pi's window onto the robot: every frame on the
//! three CAN buses, the IMU, the battery bus and the power switch, carried over
//! the carrier's J5 so that a program on the Pi -- or on a PC through it -- can
//! watch them and drive them. docs/DIAGNOSTICS.md is the specification and
//! says what each message carries; this is the controller's end of it, and
//! `sbc/diagd.py` is the Pi's.
//!
//! USART1 on PA9/PA10 at 1.5 Mbaud, 8N1, to the Pi's UART4. Messages both ways
//! are COBS frames with a CRC ([`diag_link`]).
//!
//! The three buses are FDCAN1 on PA11/PA12 (bus A, the hips, J2), FDCAN2 on
//! PB12/PB13 (bus B, the knees, J3) and FDCAN3 on PA8/PB4 (bus C, the wheels,
//! J4), each at 1 Mbit/s classic CAN, which the motors default to. Every frame
//! heard on any of them goes to the Pi with the time it came; every frame the
//! Pi sends goes onto its bus in the order it was sent, or is given up after
//! [`SEND_TIMEOUT`] if nothing on the bus will take it.
//!
//! I2C1 on PA15/PB7 carries the BNO085 IMU and the INA226 that reads the
//! battery bus, both found by asking. The IMU is polled every [`IMU_POLL`],
//! since J6 does not carry its interrupt line, and every packet it sends goes
//! to the Pi whole; the Pi writes to it whole as well, so all of SH-2 is the
//! Pi's to use. The battery bus is read every [`VBUS_PERIOD`] and goes out in
//! the status the controller sends every [`STATUS_PERIOD`].
//!
//! It knows one thing about the motors, which is how to switch them off: a
//! stop throws away every frame waiting to go and sends DAMIAO's disable to
//! every motor ID the Pi has addressed and to 1 to 16, on all four modes' frame
//! IDs, [`STOP_ROUNDS`] times, on all three buses. It stops when the Pi asks,
//! when the Pi has said nothing for [`DEADMAN`], on the power button's
//! half-second press, and as it starts.
//!
//! Nothing here has run on the robot yet: what has is `wheel_check`, on bus C.

#![no_std]
#![no_main]

use core::cell::RefCell;
use core::fmt::Write as _;

use board::power;
use diag_link::{Decoder, MAX_IMU_PACKET, MAX_WIRE, host, mcu};
use embassy_executor::Spawner;
use embassy_futures::join::{join, join3, join5};
use embassy_futures::select::{Either, select};
use embassy_stm32::can::config::TxBufferMode;
use embassy_stm32::can::enums::BusErrorMode;
use embassy_stm32::can::{self, CanConfigurator, CanRx, CanTx, Frame, Properties};
use embassy_stm32::gpio::{Level, Output, Speed};
use embassy_stm32::i2c::{self, I2c, Master};
use embassy_stm32::mode::Async;
use embassy_stm32::time::Hertz;
use embassy_stm32::usart::{self, BufferedUart, BufferedUartRx, BufferedUartTx};
use embassy_stm32::{bind_interrupts, dma, pac, peripherals, uid};
use embassy_sync::blocking_mutex::raw::NoopRawMutex;
use embassy_sync::channel::Channel;
use embassy_sync::pipe::Pipe;
use embassy_sync::signal::Signal;
use embassy_time::{Duration, Instant, Ticker, Timer, with_timeout};
use embedded_can::Id;
use embedded_io_async::{Read, Write};
use heapless::{String, Vec};

bind_interrupts!(struct Irqs {
    FDCAN1_IT0 => can::IT0InterruptHandler<peripherals::FDCAN1>;
    FDCAN1_IT1 => can::IT1InterruptHandler<peripherals::FDCAN1>;
    FDCAN2_IT0 => can::IT0InterruptHandler<peripherals::FDCAN2>;
    FDCAN2_IT1 => can::IT1InterruptHandler<peripherals::FDCAN2>;
    FDCAN3_IT0 => can::IT0InterruptHandler<peripherals::FDCAN3>;
    FDCAN3_IT1 => can::IT1InterruptHandler<peripherals::FDCAN3>;
    USART1 => usart::BufferedInterruptHandler<peripherals::USART1>;
    I2C1_EV => i2c::EventInterruptHandler<peripherals::I2C1>;
    I2C1_ER => i2c::ErrorInterruptHandler<peripherals::I2C1>;
    DMA1_CHANNEL1 => dma::InterruptHandler<peripherals::DMA1_CH1>;
    DMA1_CHANNEL2 => dma::InterruptHandler<peripherals::DMA1_CH2>;
});

/// J5's rate. 115 200 carries about 570 CAN frames a second each way, and the
/// bench GUI driving six motors at 200 Hz wants 1 200. This is exact on the
/// Pi's 24 MHz UART clock and 0.3 % off on this one's 170 MHz.
const BAUD: u32 = 1_500_000;
/// The motors' default, and what all three buses are laid out for.
const BITRATE: u32 = 1_000_000;

const BUSES: usize = 3;
/// Each bus's name on the Pi's side, its controller, its connector and what
/// it carries (docs/CARRIER.md).
const BUS_NAMES: [&str; BUSES] = [
    "A FDCAN1 J2 hips",
    "B FDCAN2 J3 knees",
    "C FDCAN3 J4 wheels",
];

/// How long the Pi may say nothing before every motor is stopped. The Pi
/// pings every 50 ms.
const DEADMAN: Duration = Duration::from_millis(300);
/// How often the deadman, the power button and the status are looked at.
const TICK: Duration = Duration::from_millis(20);
const STATUS_PERIOD: Duration = Duration::from_millis(100);
/// A frame nothing on the bus acknowledges is retried by the controller for
/// ever, holding its buffer while it is; after this it is withdrawn.
const SEND_TIMEOUT: Duration = Duration::from_millis(5);
/// Frames from the Pi waiting for each bus.
const QUEUE: usize = 32;
/// Bytes waiting for the UART to the Pi: about 55 ms of it.
const OUT_BYTES: usize = 8192;

const IMU_ADDRESSES: [u8; 2] = [0x4A, 0x4B];
const IMU_POLL: Duration = Duration::from_millis(2);
/// An SHTP length past this is not a BNO085 talking: a bus that reads all
/// ones, say.
const IMU_LONGEST: usize = 1024;
const VBUS_PERIOD: Duration = Duration::from_millis(100);
/// How often a missing IMU or INA226 is looked for again.
const SEARCH_PERIOD: Duration = Duration::from_secs(1);
/// Reads in a row a part may fail before it is taken to be gone and looked
/// for again: half a second of each.
const GIVE_UP_IMU: u32 = 250;
const GIVE_UP_INA: u32 = 5;
/// The most a raw I2C transaction from the Pi may write or read.
const I2C_MOST: usize = 64;

// ---- DAMIAO's disable, the one thing this knows about the motors -------------

/// Seven 0xFF and the code, to the frame ID of any mode: a motor takes a frame
/// whose low eight ID bits are its own, whatever mode it is in.
const DISABLE: [u8; 8] = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFD];
const MODE_OFFSETS: [u16; 4] = [0x000, 0x100, 0x200, 0x300];
/// The ID a motor's registers are reached on, with its own ID in the data.
const CONFIG_ID: u32 = 0x7FF;
const STOP_ROUNDS: usize = 3;
/// Disabled at every stop whether or not the Pi has addressed them: every ID
/// the bench GUI scans by default.
const ALWAYS_STOPPED: core::ops::RangeInclusive<u8> = 1..=16;

/// Why every motor was stopped, as STOPPED tells the Pi.
#[derive(Clone, Copy)]
enum Stop {
    Asked = 0,
    Silent = 1,
    Button = 2,
    Starting = 3,
}

/// What a bus has done, for the status.
#[derive(Clone, Copy, Default)]
struct BusCounts {
    tx: u32,
    /// Frames nothing on the bus took within [`SEND_TIMEOUT`], with every
    /// frame waiting behind them.
    tx_fail: u32,
    rx: u32,
    rx_errors: u32,
    /// Frames heard and not passed on, for want of room to the Pi.
    rx_drop: u32,
    /// Frames from the Pi not queued, for want of room in the bus's queue.
    queue_drop: u32,
}

/// What the futures share. Each takes it only between awaits.
struct Shared {
    /// When the Pi last sent a message that held together.
    last_host: Option<Instant>,
    /// Set when the deadman has stopped the motors, until the Pi is heard again.
    lost: bool,
    link: diag_link::Counts,
    uart_errors: u32,
    /// Messages from the Pi that held together but made no sense.
    malformed: u32,
    /// Messages to the Pi dropped for want of room.
    out_drop: u32,
    buses: [BusCounts; BUSES],
    /// The low eight bits of every motor ID the Pi has addressed on each bus,
    /// as a 256-bit set.
    addressed: [[u32; 8]; BUSES],
    imu: Option<u8>,
    ina: Option<u8>,
    vbus_mv: Option<u16>,
    imu_packets: u32,
    imu_errors: u32,
}

impl Shared {
    fn new() -> Self {
        let mut addressed = [[0u32; 8]; BUSES];
        for set in addressed.iter_mut() {
            for id in ALWAYS_STOPPED {
                set[id as usize / 32] |= 1 << (id % 32);
            }
        }
        Self {
            last_host: None,
            lost: false,
            link: diag_link::Counts::default(),
            uart_errors: 0,
            malformed: 0,
            out_drop: 0,
            buses: [BusCounts::default(); BUSES],
            addressed,
            imu: None,
            ina: None,
            vbus_mv: None,
            imu_packets: 0,
            imu_errors: 0,
        }
    }
}

/// A job for the I2C bus from the Pi. Both kinds take the larger's room in the
/// queue, which is four of them, and there is no heap to box the larger in.
#[allow(clippy::large_enum_variant)]
enum Job {
    ImuWrite(Vec<u8, MAX_IMU_PACKET>),
    Raw {
        tag: u8,
        address: u8,
        read: usize,
        write: Vec<u8, I2C_MOST>,
    },
}

/// Everything the futures reach each other through.
struct Ctx<'a> {
    shared: &'a RefCell<Shared>,
    out: Out<'a>,
    queues: &'a [Channel<NoopRawMutex, Frame, QUEUE>; BUSES],
    stops: &'a [Signal<NoopRawMutex, ()>; BUSES],
    jobs: &'a Channel<NoopRawMutex, Job, 4>,
}

#[embassy_executor::main]
async fn main(_spawner: Spawner) {
    board::early_init();
    let mut config = board::config();
    // FDCAN straight from the 8 MHz crystal, as wheel_check has it: eight
    // quanta a bit at 1 Mbit/s.
    config.rcc.mux.fdcansel = embassy_stm32::rcc::mux::Fdcansel::HSE;
    let p = embassy_stm32::init(config);

    // Blue LED D1, from PC6 through 5.1 k to ground: high is on.
    let mut led = Output::new(p.PC6, Level::Low, Speed::Low);

    let mut uart_config = usart::Config::default();
    uart_config.baudrate = BAUD;
    let mut tx_buffer = [0u8; 4096];
    let mut rx_buffer = [0u8; 1024];
    let uart = BufferedUart::new(
        p.USART1,
        p.PA10,
        p.PA9,
        &mut tx_buffer,
        &mut rx_buffer,
        Irqs,
        uart_config,
    )
    .unwrap();
    let (mut uart_tx, mut uart_rx) = uart.split();

    let (mut tx_a, mut rx_a, props_a) = start(CanConfigurator::new(p.FDCAN1, p.PA11, p.PA12, Irqs));
    let (mut tx_b, mut rx_b, props_b) = start(CanConfigurator::new(p.FDCAN2, p.PB12, p.PB13, Irqs));
    let (mut tx_c, mut rx_c, props_c) = start(CanConfigurator::new(p.FDCAN3, p.PA8, p.PB4, Irqs));

    let mut i2c_config = i2c::Config::default();
    i2c_config.frequency = Hertz::khz(400);
    // A backstop: the carrier's own pull-ups are fitted only if no module
    // brings its own.
    i2c_config.scl_pullup = true;
    i2c_config.sda_pullup = true;
    // Long enough for the longest IMU packet at 400 kHz, about 12 ms.
    i2c_config.timeout = Duration::from_millis(25);
    let mut i2c = I2c::new(
        p.I2C1, p.PA15, p.PB7, p.DMA1_CH1, p.DMA1_CH2, Irqs, i2c_config,
    );

    let pipe = Pipe::<NoopRawMutex, OUT_BYTES>::new();
    let shared = RefCell::new(Shared::new());
    let queues = [Channel::new(), Channel::new(), Channel::new()];
    let stops = [Signal::new(), Signal::new(), Signal::new()];
    let jobs = Channel::new();
    let ctx = Ctx {
        shared: &shared,
        out: Out {
            pipe: &pipe,
            shared: &shared,
        },
        queues: &queues,
        stops: &stops,
        jobs: &jobs,
    };
    let properties = [&props_a, &props_b, &props_c];

    join5(
        join3(
            board::heartbeat(&mut led),
            board::watchdog(p.IWDG),
            supervise(&ctx, properties),
        ),
        join(uart_in(&mut uart_rx, &ctx), uart_out(&mut uart_tx, &pipe)),
        join3(
            can_in(0, &mut rx_a, &ctx),
            can_in(1, &mut rx_b, &ctx),
            can_in(2, &mut rx_c, &ctx),
        ),
        join3(
            can_out(0, &mut tx_a, &ctx),
            can_out(1, &mut tx_b, &ctx),
            can_out(2, &mut tx_c, &ctx),
        ),
        peripherals(&mut i2c, &ctx),
    )
    .await;
}

/// One bus, at [`BITRATE`], sending in the order it is given frames: in the
/// default priority queue an enable and the first command after it share an ID
/// and either could go first.
fn start(mut can: CanConfigurator<'_>) -> (CanTx<'_>, CanRx<'_>, Properties) {
    can.set_bitrate(BITRATE);
    can.set_config(can.config().set_tx_buffer_mode(TxBufferMode::Fifo));
    can.into_normal_mode().split()
}

fn now_us() -> u32 {
    Instant::now().as_micros() as u32
}

// ---- to the Pi ---------------------------------------------------------------

/// The queue of bytes to the Pi, which [`uart_out`] empties.
struct Out<'a> {
    pipe: &'a Pipe<NoopRawMutex, OUT_BYTES>,
    shared: &'a RefCell<Shared>,
}

impl Out<'_> {
    /// Queues one message for the Pi, or drops it, counted, if there is no
    /// room: a frame heard is never worth stalling the bus it came from.
    fn send(&self, kind: u8, body: &[&[u8]]) -> bool {
        let mut wire = [0u8; MAX_WIRE];
        let Some(n) = diag_link::encode(kind, body, &mut wire) else {
            return false;
        };
        if self.pipe.free_capacity() < n {
            self.shared.borrow_mut().out_drop += 1;
            return false;
        }
        // The pipe is a ring, and takes what fits before its end first.
        let mut written = 0;
        while written < n {
            match self.pipe.try_write(&wire[written..n]) {
                Ok(k) => written += k,
                Err(_) => break,
            }
        }
        true
    }

    fn log(&self, text: &str) {
        self.send(mcu::LOG, &[&now_us().to_le_bytes(), text.as_bytes()]);
    }
}

macro_rules! log {
    ($out:expr, $($arg:tt)*) => {{
        let mut text: String<120> = String::new();
        let _ = write!(text, $($arg)*);
        $out.log(&text);
    }};
}

async fn uart_out(tx: &mut BufferedUartTx<'_>, pipe: &Pipe<NoopRawMutex, OUT_BYTES>) -> ! {
    let mut chunk = [0u8; 256];
    loop {
        let n = pipe.read(&mut chunk).await;
        let _ = tx.write_all(&chunk[..n]).await;
    }
}

/// What the controller is and what it found, one `key=value` a line.
fn send_info(ctx: &Ctx<'_>) {
    let (imu, ina) = {
        let s = ctx.shared.borrow();
        (s.imu, s.ina)
    };
    let mut text: String<512> = String::new();
    let _ = writeln!(text, "firmware=diag");
    let _ = writeln!(text, "protocol={}", diag_link::PROTOCOL);
    let _ = writeln!(text, "uid={}", uid::uid_hex());
    let _ = writeln!(text, "sysclk_hz={}", board::SYSCLK_HZ);
    let _ = writeln!(text, "baud={BAUD}");
    let _ = writeln!(text, "bitrate={BITRATE}");
    let _ = write!(text, "buses=");
    for (i, name) in BUS_NAMES.iter().enumerate() {
        let _ = write!(text, "{}{name}", if i == 0 { "" } else { "," });
    }
    let _ = writeln!(text);
    let _ = writeln!(text, "deadman_ms={}", DEADMAN.as_millis());
    match imu {
        Some(a) => writeln!(text, "imu=0x{a:02X}"),
        None => writeln!(text, "imu=none"),
    }
    .ok();
    match ina {
        Some(a) => writeln!(text, "ina226=0x{a:02X}"),
        None => writeln!(text, "ina226=none"),
    }
    .ok();
    let _ = write!(text, "reset=");
    let _ = board::reset_cause(&mut text);
    let _ = writeln!(text);
    let _ = write!(text, "last_crash=");
    let _ = board::last_crash(&mut text);
    let _ = writeln!(text);
    ctx.out.send(mcu::INFO, &[text.as_bytes()]);
}

// ---- from the Pi -------------------------------------------------------------

async fn uart_in(rx: &mut BufferedUartRx<'_>, ctx: &Ctx<'_>) -> ! {
    let mut decoder = Decoder::new();
    let mut chunk = [0u8; 64];
    loop {
        match rx.read(&mut chunk).await {
            Ok(n) => {
                for &byte in &chunk[..n] {
                    if let Some((kind, body)) = decoder.push(byte) {
                        handle(kind, body, ctx);
                    }
                }
            }
            // Noise, a framing error or an overrun: whatever message it was in
            // is lost, and the CRC would only have said so later.
            Err(_) => {
                ctx.shared.borrow_mut().uart_errors += 1;
                decoder.reset();
            }
        }
        ctx.shared.borrow_mut().link = decoder.counts;
    }
}

/// Acts on one message from the Pi. Never waits: what has to wait goes on a
/// queue, and what will not fit on one is dropped and counted.
fn handle(kind: u8, body: &[u8], ctx: &Ctx<'_>) {
    let back = {
        let mut s = ctx.shared.borrow_mut();
        s.last_host = Some(Instant::now());
        core::mem::replace(&mut s.lost, false)
    };
    if back {
        ctx.out.log("link: the Pi is back");
    }
    let ok = match kind {
        host::HELLO => {
            send_info(ctx);
            true
        }
        host::PING => true,
        host::STOP => {
            stop_all(ctx, Stop::Asked);
            true
        }
        host::CAN_SEND => can_send(body, ctx),
        host::IMU_WRITE => match Vec::from_slice(body) {
            Ok(packet) => {
                if ctx.jobs.try_send(Job::ImuWrite(packet)).is_err() {
                    ctx.out
                        .log("imu: a write from the Pi dropped: the I2C queue is full");
                }
                true
            }
            Err(_) => false,
        },
        host::I2C => i2c_request(body, ctx),
        _ => false,
    };
    if !ok {
        ctx.shared.borrow_mut().malformed += 1;
    }
}

/// CAN_SEND: bus u8, flags u8, id u32, then the data.
fn can_send(body: &[u8], ctx: &Ctx<'_>) -> bool {
    if body.len() < 6 || body.len() > 14 {
        return false;
    }
    let bus = body[0] as usize;
    let extended = body[1] & 1 != 0;
    let id = u32::from_le_bytes([body[2], body[3], body[4], body[5]]);
    let data = &body[6..];
    if bus >= BUSES || (!extended && id > 0x7FF) {
        return false;
    }
    let frame = if extended {
        Frame::new_extended(id, data)
    } else {
        Frame::new_standard(id as u16, data)
    };
    let Ok(frame) = frame else {
        return false;
    };
    let mut s = ctx.shared.borrow_mut();
    if !extended {
        // The motor this reaches, by the low eight bits of its ID: from the
        // frame's ID, or from the data of a register request.
        let motor = if id == CONFIG_ID {
            data.first().copied()
        } else {
            Some(id as u8)
        };
        if let Some(m) = motor {
            s.addressed[bus][m as usize / 32] |= 1 << (m % 32);
        }
    }
    if ctx.queues[bus].try_send(frame).is_err() {
        s.buses[bus].queue_drop += 1;
    }
    true
}

/// I2C: tag u8, address u8, read length u16, then the bytes to write.
fn i2c_request(body: &[u8], ctx: &Ctx<'_>) -> bool {
    if body.len() < 4 {
        return false;
    }
    let tag = body[0];
    let read = u16::from_le_bytes([body[2], body[3]]) as usize;
    let write = Vec::from_slice(&body[4..]);
    let (Ok(write), true) = (write, read <= I2C_MOST) else {
        ctx.out.send(mcu::I2C_RESULT, &[&[tag, 3]]);
        return true;
    };
    let job = Job::Raw {
        tag,
        address: body[1],
        read,
        write,
    };
    if ctx.jobs.try_send(job).is_err() {
        ctx.out.send(mcu::I2C_RESULT, &[&[tag, 3]]);
    }
    true
}

// ---- the buses ---------------------------------------------------------------

/// Passes every frame heard on one bus to the Pi, with when it came.
async fn can_in(bus: usize, rx: &mut CanRx<'_>, ctx: &Ctx<'_>) -> ! {
    loop {
        let envelope = match rx.read().await {
            Ok(envelope) => envelope,
            // The controller's last error code, read with no frame waiting.
            Err(_) => {
                ctx.shared.borrow_mut().buses[bus].rx_errors += 1;
                continue;
            }
        };
        let frame = &envelope.frame;
        let (mut flags, id) = match frame.id() {
            Id::Standard(id) => (0u8, id.as_raw() as u32),
            Id::Extended(id) => (1u8, id.as_raw()),
        };
        if frame.header().rtr() {
            flags |= 2;
        }
        let t = envelope.ts.as_micros() as u32;
        ctx.shared.borrow_mut().buses[bus].rx += 1;
        let sent = ctx.out.send(
            mcu::CAN_RECV,
            &[
                &t.to_le_bytes(),
                &[bus as u8, flags],
                &id.to_le_bytes(),
                frame.data(),
            ],
        );
        if !sent {
            ctx.shared.borrow_mut().buses[bus].rx_drop += 1;
        }
    }
}

/// Puts the Pi's frames on one bus, and does its part of every stop.
async fn can_out(bus: usize, tx: &mut CanTx<'_>, ctx: &Ctx<'_>) -> ! {
    let queue = &ctx.queues[bus];
    loop {
        // A stop first, if both are waiting.
        match select(ctx.stops[bus].wait(), queue.receive()).await {
            Either::First(()) => stop_bus(bus, tx, ctx).await,
            Either::Second(frame) => {
                send(bus, tx, &frame, ctx).await;
            }
        }
    }
}

/// Queues a frame on the bus, or gives up after [`SEND_TIMEOUT`] and withdraws
/// every frame still waiting: one that nothing acknowledges is retried for
/// ever, and holds its buffer while it is.
async fn send(bus: usize, tx: &mut CanTx<'_>, frame: &Frame, ctx: &Ctx<'_>) -> bool {
    if with_timeout(SEND_TIMEOUT, tx.write(frame)).await.is_ok() {
        ctx.shared.borrow_mut().buses[bus].tx += 1;
        return true;
    }
    let waiting = REGS[bus].txbrp().read().0.count_ones();
    cancel_pending(bus);
    let mut s = ctx.shared.borrow_mut();
    let counts = &mut s.buses[bus];
    // The frames withdrawn were counted as sent when they were queued.
    counts.tx = counts.tx.saturating_sub(waiting);
    counts.tx_fail += 1 + waiting;
    false
}

const REGS: [pac::can::Fdcan; BUSES] = [pac::FDCAN1, pac::FDCAN2, pac::FDCAN3];

/// Withdraws every frame waiting to go on one bus.
fn cancel_pending(bus: usize) {
    REGS[bus].txbcr().write(|w| {
        for n in 0..3 {
            w.set_cr(n, true);
        }
    });
}

/// One bus's part of a stop: whatever is still waiting in the controller is
/// withdrawn, then every motor the Pi has addressed, and 1 to 16, is disabled
/// on all four modes' frame IDs. A bus that will not take a frame is given up
/// on, since nothing on it can hear the rest.
async fn stop_bus(bus: usize, tx: &mut CanTx<'_>, ctx: &Ctx<'_>) {
    cancel_pending(bus);
    let addressed = ctx.shared.borrow().addressed[bus];
    let disable = |motor: u16, offset: u16| Frame::new_standard(motor + offset, &DISABLE).unwrap();
    for _ in 0..STOP_ROUNDS {
        for motor in 0..=255u16 {
            if addressed[motor as usize / 32] & (1 << (motor % 32)) == 0 {
                continue;
            }
            for offset in MODE_OFFSETS {
                if !send(bus, tx, &disable(motor, offset), ctx).await {
                    return;
                }
            }
        }
    }
}

/// Every bus stops, and the Pi is told why. The queues are emptied here and
/// now, so that what the Pi sends after a stop is kept and goes after it; the
/// disabling is each bus's own future's, in [`stop_bus`].
fn stop_all(ctx: &Ctx<'_>, why: Stop) {
    for (queue, stop) in ctx.queues.iter().zip(ctx.stops) {
        queue.clear();
        stop.signal(());
    }
    ctx.out.send(mcu::STOPPED, &[&[why as u8]]);
}

// ---- the watches, and the status ---------------------------------------------

async fn supervise(ctx: &Ctx<'_>, properties: [&Properties; BUSES]) -> ! {
    // A motor enabled by an image that has since reset holds a command nobody
    // is sending any more.
    stop_all(ctx, Stop::Starting);
    send_info(ctx);
    let mut ticker = Ticker::every(TICK);
    let mut next_status = Instant::now();
    let mut told_off = false;
    loop {
        ticker.next().await;
        let now = Instant::now();
        let silent = {
            let mut s = ctx.shared.borrow_mut();
            let silent = !s.lost && s.last_host.is_some_and(|t| now - t > DEADMAN);
            s.lost |= silent;
            silent
        };
        if silent {
            log!(
                ctx.out,
                "link: nothing from the Pi for {} ms; every motor stopped",
                DEADMAN.as_millis()
            );
            stop_all(ctx, Stop::Silent);
        }
        if power::off_requested() && !told_off {
            told_off = true;
            ctx.out
                .log("power: button held, HOLD released; every motor stopped");
            stop_all(ctx, Stop::Button);
        }
        if now >= next_status {
            next_status += STATUS_PERIOD;
            send_status(ctx, &properties);
        }
    }
}

/// Lays numbers end to end, little-endian.
struct Put<'a> {
    buf: &'a mut [u8],
    n: usize,
}

impl Put<'_> {
    fn bytes(&mut self, b: &[u8]) {
        self.buf[self.n..self.n + b.len()].copy_from_slice(b);
        self.n += b.len();
    }
    fn u8(&mut self, v: u8) {
        self.bytes(&[v]);
    }
    fn u16(&mut self, v: u16) {
        self.bytes(&v.to_le_bytes());
    }
    fn u32(&mut self, v: u32) {
        self.bytes(&v.to_le_bytes());
    }
}

/// STATUS, laid out as docs/DIAGNOSTICS.md gives it: 127 bytes.
fn send_status(ctx: &Ctx<'_>, properties: &[&Properties; BUSES]) {
    let mut buf = [0u8; 127];
    let mut put = Put {
        buf: &mut buf,
        n: 0,
    };
    {
        let s = ctx.shared.borrow();
        let now = Instant::now();
        put.u32(now.as_micros() as u32);
        put.u32(now.as_millis() as u32);
        let flags = power::held() as u8
            | (power::pressed() as u8) << 1
            | (power::off_requested() as u8) << 2
            | (s.lost as u8) << 3
            | (s.imu.is_some() as u8) << 4
            | (s.ina.is_some() as u8) << 5;
        put.u8(flags);
        put.u16(s.vbus_mv.unwrap_or(0));
        put.u32(s.link.frames);
        put.u32(s.link.crc_errors);
        put.u32(s.link.overruns);
        put.u32(s.uart_errors);
        put.u32(s.malformed);
        put.u32(s.out_drop);
        put.u32(s.imu_packets);
        put.u32(s.imu_errors);
        for (props, counts) in properties.iter().zip(s.buses.iter()) {
            // Reading the state clears the controller's last error code, so a
            // receive error that lands between two reads of it is not counted
            // in rx_errors; the error counters beside it still see it.
            put.u8(match props.bus_error_mode() {
                BusErrorMode::ErrorActive => 0,
                BusErrorMode::ErrorPassive => 1,
                BusErrorMode::BusOff => 2,
            });
            put.u8(props.tx_error_count());
            put.u8(props.rx_error_count());
            put.u8(0);
            put.u32(counts.tx);
            put.u32(counts.tx_fail);
            put.u32(counts.rx);
            put.u32(counts.rx_errors);
            put.u32(counts.rx_drop);
            put.u32(counts.queue_drop);
        }
    }
    let n = put.n;
    ctx.out.send(mcu::STATUS, &[&buf[..n]]);
}

// ---- I2C: the IMU, the battery bus, and the Pi's own transactions ------------

async fn peripherals(i2c: &mut I2c<'_, Async, Master>, ctx: &Ctx<'_>) -> ! {
    let mut packet = [0u8; MAX_IMU_PACKET];
    let start = Instant::now();
    let (mut next_search, mut next_vbus, mut next_imu) = (start, start, start);
    // Reads in a row that each part has not answered.
    let (mut imu_missed, mut ina_missed) = (0u32, 0u32);
    loop {
        let (imu, ina) = {
            let s = ctx.shared.borrow();
            (s.imu, s.ina)
        };
        let mut wake = next_vbus;
        if imu.is_none() || ina.is_none() {
            wake = wake.min(next_search);
        }
        if imu.is_some() {
            wake = wake.min(next_imu);
        }
        if let Either::First(job) = select(ctx.jobs.receive(), Timer::at(wake)).await {
            run_job(i2c, job, ctx).await;
        }
        let now = Instant::now();
        if now >= next_search && (imu.is_none() || ina.is_none()) {
            next_search = now + SEARCH_PERIOD;
            search(i2c, ctx).await;
        }
        if let Some(address) = imu
            && now >= next_imu
        {
            next_imu = now + IMU_POLL;
            if poll_imu(i2c, address, &mut packet, ctx).await {
                imu_missed = 0;
            } else {
                imu_missed += 1;
                if imu_missed == GIVE_UP_IMU {
                    imu_missed = 0;
                    ctx.shared.borrow_mut().imu = None;
                    ctx.out
                        .log("i2c: the IMU has stopped answering; looking for it again");
                }
            }
        }
        if now >= next_vbus {
            next_vbus = now + VBUS_PERIOD;
            let volts = match ina {
                Some(address) => {
                    let mut raw = [0u8; 2];
                    match i2c.write_read(address, &[0x02], &mut raw).await {
                        // 1.25 mV a count.
                        Ok(()) => Some((u16::from_be_bytes(raw) as u32 * 5 / 4) as u16),
                        Err(_) => None,
                    }
                }
                None => None,
            };
            ina_missed = if ina.is_some() && volts.is_none() {
                ina_missed + 1
            } else {
                0
            };
            let mut s = ctx.shared.borrow_mut();
            s.vbus_mv = volts;
            if ina_missed == GIVE_UP_INA {
                ina_missed = 0;
                s.ina = None;
                drop(s);
                ctx.out
                    .log("i2c: the INA226 has stopped answering; looking for it again");
            }
        }
    }
}

/// Looks for whichever of the IMU and the INA226 has not been found: the
/// INA226 by TI's manufacturer ID, since the module's address straps are not
/// recorded, and the IMU by anything at all answering at its two addresses.
async fn search(i2c: &mut I2c<'_, Async, Master>, ctx: &Ctx<'_>) {
    let (imu, ina) = {
        let s = ctx.shared.borrow();
        (s.imu, s.ina)
    };
    if ina.is_none() {
        for address in 0x40..=0x4F {
            let mut id = [0u8; 2];
            if i2c.write_read(address, &[0xFE], &mut id).await.is_ok() && id == *b"TI" {
                ctx.shared.borrow_mut().ina = Some(address);
                log!(ctx.out, "i2c: INA226 at 0x{address:02X}");
                break;
            }
        }
    }
    if imu.is_none() {
        for address in IMU_ADDRESSES {
            // A header read takes nothing from the packet it heads: the next
            // read starts the packet again.
            let mut header = [0u8; 4];
            if i2c.read(address, &mut header).await.is_ok() {
                ctx.shared.borrow_mut().imu = Some(address);
                log!(ctx.out, "i2c: IMU at 0x{address:02X}");
                break;
            }
        }
    }
}

/// Reads the IMU's next packet, if it has one, and passes it to the Pi.
///
/// SHTP over I2C: a read starts with the waiting packet's four-byte header,
/// whose length is the whole packet's, header included, and a read that stops
/// short leaves the packet where it was. So the header is read alone to learn
/// the length, and then the packet whole.
///
/// Returns whether the IMU answered at all.
async fn poll_imu(
    i2c: &mut I2c<'_, Async, Master>,
    address: u8,
    packet: &mut [u8; MAX_IMU_PACKET],
    ctx: &Ctx<'_>,
) -> bool {
    let mut header = [0u8; 4];
    if i2c.read(address, &mut header).await.is_err() {
        ctx.shared.borrow_mut().imu_errors += 1;
        return false;
    }
    let length = (u16::from_le_bytes([header[0], header[1]]) & 0x7FFF) as usize;
    if length <= 4 {
        return true;
    }
    if length > IMU_LONGEST {
        ctx.shared.borrow_mut().imu_errors += 1;
        return true;
    }
    // A packet longer than this comes as a continuation the next time round.
    let n = length.min(MAX_IMU_PACKET);
    let t = now_us();
    if i2c.read(address, &mut packet[..n]).await.is_err() {
        ctx.shared.borrow_mut().imu_errors += 1;
        return false;
    }
    ctx.shared.borrow_mut().imu_packets += 1;
    ctx.out
        .send(mcu::IMU_PACKET, &[&t.to_le_bytes(), &packet[..n]]);
    true
}

async fn run_job(i2c: &mut I2c<'_, Async, Master>, job: Job, ctx: &Ctx<'_>) {
    match job {
        Job::ImuWrite(packet) => {
            let imu = ctx.shared.borrow().imu;
            match imu {
                Some(address) => {
                    if i2c.write(address, &packet).await.is_err() {
                        ctx.shared.borrow_mut().imu_errors += 1;
                    }
                }
                None => ctx
                    .out
                    .log("imu: a write from the Pi dropped: no IMU has answered"),
            }
        }
        Job::Raw {
            tag,
            address,
            read,
            write,
        } => {
            let mut data = [0u8; I2C_MOST];
            let result = match (write.is_empty(), read) {
                (_, 0) => i2c.write(address, &write).await,
                (true, n) => i2c.read(address, &mut data[..n]).await,
                (false, n) => i2c.write_read(address, &write, &mut data[..n]).await,
            };
            let status = match result {
                Ok(()) => 0u8,
                Err(i2c::Error::Nack) => 1,
                Err(i2c::Error::Timeout) => 2,
                Err(_) => 3,
            };
            let n = if status == 0 { read } else { 0 };
            ctx.out.send(mcu::I2C_RESULT, &[&[tag, status], &data[..n]]);
        }
    }
}
