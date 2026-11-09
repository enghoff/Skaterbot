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
//! It knows how to switch the motors off, which is what a stop is, and, for
//! their LEDs alone and only while the Pi is leaving them be ([`motor_flash`]),
//! how to switch them on with no torque asked: a
//! stop throws away every frame waiting to go and sends DAMIAO's disable to
//! every motor ID the Pi has addressed and to 1 to 16, on all four modes' frame
//! IDs, [`STOP_ROUNDS`] times, on all three buses. It stops when the Pi asks,
//! when the Pi has said nothing for [`DEADMAN`], on the power button's
//! two-second press, and as it starts.
//!
//! Its LED, D1, beats board::heartbeat's heartbeat while all is well and shows
//! a fault's pattern while something is wrong ([`health`]): the IMU missing or
//! found and silent, the INA226 missing, a bus gone bus-off, or nothing from
//! the Pi. It tells the Pi the same in HEALTH, so the Pi's LED can agree.
//!
//! Nothing here has run on the robot yet: what has is `wheel_check`, on bus C.

#![no_std]
#![no_main]

mod health;
mod motor_flash;

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

use health::{Fault, Health};
use motor_flash::{Action, EVERY_MOTOR, MotorFlash};

// A healthy controller beats exactly as every other image does.
const _: () = assert!(
    health::HEARTBEAT_PERIOD_MS == board::HEARTBEAT_PERIOD_MS
        && health::HEARTBEAT_FLASH_MS == board::HEARTBEAT_FLASH_MS
);

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
/// Acceleration, calibrated gyro, gravity and game rotation at 100 Hz.
const IMU_DEFAULT_REPORTS: [u8; 4] = [0x01, 0x02, 0x06, 0x08];
const IMU_REPORT_INTERVAL_US: u32 = 10_000;
/// Leave the hub's boot/reset sequence undisturbed before I2C setup.
const IMU_BOOT_QUIET: Duration = Duration::from_millis(300);
/// SH-2's Command Request, on the control channel, and the two commands sent
/// with it: the report IDs are the BNO08X datasheet's (1000-3927 v1.17, figure
/// 1-30, reference/BNO080_085-Datasheet.pdf), and the commands and their
/// parameters the SH-2 Reference Manual's (1000-3625), which the datasheet
/// points to and which CEVA's sh2 driver sends the same way (SH2_CMD_ME_CAL 7,
/// SH2_CMD_DCD_PERIOD_SAVE 9). The answers come back as Command Responses
/// (0xF1) with every other packet, and diagd reads them.
const SH2_COMMAND_REQUEST: u8 = 0xF2;
const SH2_ME_CALIBRATION: u8 = 0x07;
const SH2_PERIODIC_DCD_SAVE: u8 = 0x09;
/// What the hub calibrates by itself, as Configure ME Calibration's parameters:
/// P0 accelerometer, P1 gyroscope, P2 magnetometer, P3 the subcommand (0 is
/// configure), P4 planar accelerometer, P5 on-table, 1 for on.
///
/// The accelerometer's is off. Its zero-g offset is what the robot's up was
/// levelled against, and the hub's own calibration moved it on 2026-11-05 at
/// about 16:10: the gravity report's length stepped from 9.93-9.96 to 9.74-9.75
/// m/s2, and the robot standing balanced read 2.4-3.2 degrees nose-down from
/// then on, which the policy answered by driving slower forwards and faster in
/// reverse than it was asked. That calibration wants the device held still in
/// four to six orientations (datasheet 3.2); a robot on wheels gives it
/// whatever it happens to do. The magnetometer's is off as well, nothing here
/// using it: the game rotation vector has none. The gyroscope's stays off, as
/// the datasheet has it by default, for want of a hand's tremor (3.1.3), and
/// the on-table correction is on, which puts the zero rate right whenever the
/// robot stands still.
const IMU_CALIBRATE: [u8; 9] = [0, 0, 0, 0, 0, 1, 0, 0, 0];
/// Get ME Calibration: the same command with the subcommand 1, answered with
/// the five settings the hub is running with.
const IMU_CALIBRATION_GET: [u8; 9] = [0, 0, 0, 1, 0, 0, 0, 0, 0];
/// Configure Periodic DCD Save, P0 1 for off. The hub otherwise writes what it
/// has learned to its flash every so often, where every later power-up reads
/// it. It still writes it at any reset that is not a power-up (datasheet 3.4),
/// which with the accelerometer's calibration off no longer changes the up.
const IMU_DCD_SAVE_OFF: [u8; 9] = [1, 0, 0, 0, 0, 0, 0, 0, 0];
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

// ---- DAMIAO's disable, and what the motors' LEDs need ------------------------

/// Seven 0xFF and the code, to the frame ID of any mode: a motor takes a frame
/// whose low eight ID bits are its own, whatever mode it is in.
const DISABLE: [u8; 8] = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFD];
const ENABLE: [u8; 8] = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFC];
/// MIT mode's five numbers with no gains and no torque: position and speed at the
/// middle of their ranges, where they count for nothing with the gains at 0, and
/// the torque at the nearest 12 bits have to 0, -0.0012 Nm with TMAX at 5.
const NO_TORQUE: [u8; 8] = [0x7F, 0xFF, 0x7F, 0xF0, 0x00, 0x00, 0x07, 0xFF];
/// The register CTRL_MODE is, and a read's and a write's codes in a register frame.
const CTRL_MODE: u8 = 0x0A;
const READ_REGISTER: u8 = 0x33;
/// Each motor's bus, by its ID less one: sysid_robot.json's wiring.
const MOTOR_BUS: [usize; 6] = [0, 0, 1, 1, 2, 2];
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

#[derive(Default)]
struct ImuDiag {
    header_reads: u32,
    empty_reads: u32,
    header_errors: u32,
    payload_errors: u32,
    write_errors: u32,
    nack: u32,
    timeouts: u32,
    bus_errors: u32,
    arbitration: u32,
    other_errors: u32,
    invalid_lengths: u32,
    resets: u32,
    input_packets: u32,
    last_input_ms: u32,
    ina_errors: u32,
    searches: u32,
    max_i2c_us: u32,
    max_service_gap_us: u32,
    last_header: u32,
    last_error_ms: u32,
    host_resets: u32,
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
    /// One sequence per SHTP channel, shared by defaults and Pi requests.
    imu_sequence: [u8; 6],
    /// SH-2's own sequence for Command Requests, which each answer repeats.
    imu_command_sequence: u8,
    imu_quiet_until: Option<Instant>,
    ina: Option<u8>,
    vbus_mv: Option<u16>,
    imu_packets: u32,
    imu_errors: u32,
    imu_diag: ImuDiag,
    health: Health,
    /// What [`Health::flags`] said at the last tick, which the LED shows.
    health_flags: u16,
    /// Until when the LED shows the fast speed mode, from the Pi's INDICATE.
    fast_until: Option<Instant>,
    motor_flash: MotorFlash,
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
            imu_sequence: [0; 6],
            imu_command_sequence: 0,
            imu_quiet_until: None,
            ina: None,
            vbus_mv: None,
            imu_packets: 0,
            imu_errors: 0,
            imu_diag: ImuDiag::default(),
            health: Health::new(),
            health_flags: 0,
            fast_until: None,
            motor_flash: MotorFlash::new(),
        }
    }

    /// The IMU has stopped answering, or is to be looked for again.
    fn imu_gone(&mut self) {
        self.imu = None;
        self.health.imu_lost(now_ms());
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
    power::wait_for_sbc_shutdown();
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
            indicator(&mut led, &ctx),
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

fn now_ms() -> u64 {
    Instant::now().as_millis()
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
    let mut text: String<576> = String::new();
    let _ = writeln!(text, "firmware=diag");
    let _ = writeln!(text, "protocol={}", diag_link::PROTOCOL);
    let _ = writeln!(text, "uid={}", uid::uid_hex());
    let _ = writeln!(text, "sysclk_hz={}", board::SYSCLK_HZ);
    let _ = writeln!(text, "baud={BAUD}");
    let _ = writeln!(text, "bitrate={BITRATE}");
    let _ = writeln!(text, "power_shutdown=grace-20s-force-8s");
    let _ = writeln!(text, "shutdown_led=1");
    let _ = writeln!(text, "imu_startup=quiet-300ms");
    let _ = writeln!(text, "imu_diagnostics=2");
    let _ = writeln!(text, "imu_bus=clean-boundaries-v1");
    let _ = writeln!(text, "health=1");
    let _ = writeln!(text, "motor_flash=1");
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
        host::SHUTDOWN if body.is_empty() => {
            power::request_shutdown();
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
        host::INDICATE if body.len() == 1 => {
            ctx.shared.borrow_mut().fast_until = (body[0] & 1 != 0)
                .then(|| Instant::now() + Duration::from_millis(health::FAST_HOLD_MS));
            true
        }
        host::MOTOR_FLASH if body.len() == 3 => motor_flash_test(body, ctx),
        _ => false,
    };
    if !ok {
        ctx.shared.borrow_mut().malformed += 1;
    }
}

/// MOTOR_FLASH: fault u8, as HEALTH has it and 0 to end a test, motors u8, bit n
/// being motor n + 1, and seconds u8.
fn motor_flash_test(body: &[u8], ctx: &Ctx<'_>) -> bool {
    let pattern = match body[0] {
        0 => {
            ctx.shared.borrow_mut().motor_flash.end_test();
            ctx.out.log("motor flash: test ended by the Pi");
            return true;
        }
        1 => Fault::Link.pattern(),
        2 => Fault::Imu.pattern(),
        3 => Fault::Hardware.pattern(),
        _ => return false,
    };
    let started = ctx.shared.borrow_mut().motor_flash.start_test(
        now_ms(),
        pattern,
        body[1],
        body[2],
        power::off_requested(),
    );
    ctx.out.log(if started {
        "motor flash: test started, with no fault"
    } else {
        "motor flash: test refused: the Pi has used a motor in the last 3 s, or asked for none"
    });
    true
}

/// What the flash tells the motors in `mask`. Nothing here waits, so that it
/// happens whole between the Pi's frames.
fn flash_frames(ctx: &Ctx<'_>, s: &mut Shared, action: Action, mask: u8) {
    if action == Action::AskMode {
        for (n, &bus) in MOTOR_BUS.iter().enumerate() {
            if mask & (1 << n) != 0 {
                let asking = [n as u8 + 1, 0, READ_REGISTER, CTRL_MODE];
                let frame = Frame::new_standard(CONFIG_ID as u16, &asking).unwrap();
                if ctx.queues[bus].try_send(frame).is_err() {
                    s.buses[bus].queue_drop += 1;
                }
            }
        }
        return;
    }
    let frames: &[&[u8; 8]] = match action {
        Action::Nothing | Action::AskMode => return,
        Action::Light => &[&NO_TORQUE, &ENABLE, &NO_TORQUE],
        Action::Keep => &[&NO_TORQUE],
        Action::Darken => &[&DISABLE, &DISABLE],
    };
    for (n, &bus) in MOTOR_BUS.iter().enumerate() {
        if mask & (1 << n) == 0 {
            continue;
        }
        for data in frames {
            let frame = Frame::new_standard(n as u16 + 1, *data).unwrap();
            if ctx.queues[bus].try_send(frame).is_err() {
                s.buses[bus].queue_drop += 1;
            }
        }
    }
}

/// CAN_SEND: bus u8, flags u8, id u32, then the data.
fn can_send(body: &[u8], ctx: &Ctx<'_>) -> bool {
    if power::off_requested() {
        return false;
    }
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
    // The motors are the Pi's from this frame on: any lit by the flash go out
    // ahead of it, in the same queues, so that nothing disables what it enables.
    if s.motor_flash.pi_frame(now_ms()) {
        flash_frames(ctx, &mut s, Action::Darken, EVERY_MOTOR);
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
        {
            let mut s = ctx.shared.borrow_mut();
            s.buses[bus].rx += 1;
            // A motor saying which mode it is in, on its own bus. A motor's report
            // has its position's high byte where this has the ID's high byte, 0,
            // which is the end of the position's range, never reached.
            let d = frame.data();
            if d.len() == 8
                && d[1] == 0
                && d[2] == READ_REGISTER
                && d[3] == CTRL_MODE
                && MOTOR_BUS.get((d[0] as usize).wrapping_sub(1)) == Some(&bus)
            {
                let mode = u32::from_le_bytes([d[4], d[5], d[6], d[7]]);
                s.motor_flash.mode_heard(d[0], mode);
            }
        }
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
                if !power::off_requested() {
                    send(bus, tx, &frame, ctx).await;
                }
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
    let by_pi = matches!(why, Stop::Asked | Stop::Button);
    ctx.shared.borrow_mut().motor_flash.stopped(now_ms(), by_pi);
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
    let mut next_diag = next_status;
    let mut last_service = next_status;
    let mut told_off = false;
    let mut told_health = 0u16;
    let mut told_flash = false;
    loop {
        ticker.next().await;
        let now = Instant::now();
        {
            let mut s = ctx.shared.borrow_mut();
            s.imu_diag.max_service_gap_us = s
                .imu_diag
                .max_service_gap_us
                .max((now - last_service).as_micros() as u32);
        }
        last_service = now;
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
                .log("power: button held; every motor stopped; waiting for Pi shutdown");
            stop_all(ctx, Stop::Button);
        }
        let flags = {
            let mut s = ctx.shared.borrow_mut();
            let ms = now.as_millis();
            let lost = health::link_lost(s.lost, s.last_host.is_some(), ms);
            s.health_flags = s.health.flags(ms, lost);
            s.health_flags
        };
        let flashing = {
            let fault = Some(Fault::of(flags))
                .filter(|&fault| fault != Fault::Healthy)
                .map(Fault::pattern);
            let mut s = ctx.shared.borrow_mut();
            let action = s
                .motor_flash
                .tick(now.as_millis(), fault, power::off_requested());
            let mask = match action {
                Action::Darken => EVERY_MOTOR,
                Action::AskMode => s.motor_flash.target(),
                _ => s.motor_flash.mask(),
            };
            flash_frames(ctx, &mut s, action, mask);
            s.motor_flash.showing()
        };
        if flashing != told_flash {
            told_flash = flashing;
            ctx.out.log(if flashing {
                "motor flash: the motors' LEDs are showing a fault's pattern"
            } else {
                "motor flash: the motors' LEDs are no longer showing one"
            });
        }
        if flags != told_health {
            told_health = flags;
            log_health(ctx, flags);
            send_health(ctx, flags);
        }
        if now >= next_status {
            next_status += STATUS_PERIOD;
            send_status(ctx, &properties);
        }
        if now >= next_diag {
            next_diag = now + Duration::from_secs(1);
            send_imu_diag(ctx);
            send_health(ctx, flags);
        }
    }
}

/// HEALTH: version, the fault the LED shows, and every condition that holds.
fn send_health(ctx: &Ctx<'_>, flags: u16) {
    let head = [1, Fault::of(flags) as u8];
    ctx.out.send(mcu::HEALTH, &[&head, &flags.to_le_bytes()]);
}

fn log_health(ctx: &Ctx<'_>, flags: u16) {
    let mut text: String<120> = String::new();
    let _ = write!(text, "health: ");
    if flags == 0 {
        let _ = write!(text, "all clear");
    }
    let held = health::NAMES.iter().filter(|(bit, _)| flags & bit != 0);
    for (i, (_, name)) in held.enumerate() {
        let _ = write!(text, "{}{name}", if i == 0 { "" } else { ", " });
    }
    ctx.out.log(&text);
}

/// Blue LED D1: board::heartbeat's beat while the controller is healthy, a
/// fault's pattern while it is not, and dark once shutdown is asked for, as
/// every image's is. Each cycle is chosen afresh, so a fault shows, and
/// clears, within one heartbeat.
async fn indicator(led: &mut Output<'_>, ctx: &Ctx<'_>) -> ! {
    let show = async {
        loop {
            let (fault, fast) = {
                let s = ctx.shared.borrow();
                let fast = s.fast_until.is_some_and(|t| Instant::now() < t);
                (Fault::of(s.health_flags), fast)
            };
            for &(lit, ms) in fault.shown(fast) {
                if lit {
                    led.set_high();
                } else {
                    led.set_low();
                }
                Timer::after_millis(ms).await;
            }
        }
    };
    let shutting_down = async {
        while !power::off_requested() {
            Timer::after_millis(10).await;
        }
    };
    select(show, shutting_down).await;
    led.set_low();
    core::future::pending::<()>().await;
    unreachable!()
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
    let mut bus_off = false;
    {
        let s = ctx.shared.borrow();
        let now = Instant::now();
        put.u32(now.as_micros() as u32);
        put.u32(now.as_millis() as u32);
        let flags = power::held() as u8
            | (power::pressed_lately() as u8) << 1
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
                BusErrorMode::BusOff => {
                    bus_off = true;
                    2
                }
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
    if bus_off {
        ctx.shared.borrow_mut().health.bus_off(now_ms());
    }
    let n = put.n;
    ctx.out.send(mcu::STATUS, &[&buf[..n]]);
}

// ---- I2C: the IMU, the battery bus, and the Pi's own transactions ------------

fn i2c_pins() -> u32 {
    ((pac::GPIOA.idr().read().0 >> 15) & 1) | (((pac::GPIOB.idr().read().0 >> 7) & 1) << 1)
}

async fn reset_i2c_host(ctx: &Ctx<'_>) {
    let before = i2c_pins();
    let isr = pac::I2C1.isr().read().0;
    pac::I2C1.cr1().modify(|w| w.set_pe(false));
    while pac::I2C1.cr1().read().pe() {}
    Timer::after_micros(10).await;
    let released = i2c_pins();
    pac::I2C1.cr1().modify(|w| w.set_pe(true));
    let count = {
        let mut s = ctx.shared.borrow_mut();
        s.imu_diag.host_resets += 1;
        s.imu_diag.host_resets
    };
    if count <= 8 || count % 100 == 0 {
        log!(
            ctx.out,
            "i2c host reset #{count}: pins {before}->{released}, ISR={isr:08x}"
        );
    }
}

async fn prepare_imu_bus(ctx: &Ctx<'_>) -> Result<(), i2c::Error> {
    // The released HAL's DMA reads can leave STOPF set. Its blocking reader
    // interprets that old STOP as a completed read even without fresh RXNE,
    // producing a false empty header. Wait for the previous transaction to
    // finish and remove its flags before using the bounded polled path.
    let idle = with_timeout(Duration::from_millis(25), async {
        while pac::I2C1.isr().read().busy() || pac::I2C1.cr2().read().start() {
            Timer::after_micros(10).await;
        }
    })
    .await;
    if idle.is_err() {
        reset_i2c_host(ctx).await;
        return Err(i2c::Error::Timeout);
    }
    pac::I2C1.icr().write(|w| {
        w.set_stopcf(true);
        w.set_nackcf(true);
        w.set_berrcf(true);
        w.set_arlocf(true);
        w.set_ovrcf(true);
    });
    if pac::I2C1.isr().read().rxne() {
        let _ = pac::I2C1.rxdr().read();
    }
    // A NACK during a DMA write may leave a preloaded byte in TXDR. It must
    // not become the first byte of the next sensor's SHTP header. This is the
    // same flush sequence as the HAL's polled error handler, at an idle bus.
    if pac::I2C1.isr().read().txis() {
        pac::I2C1.txdr().write(|w| w.set_txdata(0));
    }
    if !pac::I2C1.isr().read().txe() {
        pac::I2C1.isr().write(|w| w.set_txe(true));
    }
    Ok(())
}

async fn read_imu_bus(
    i2c: &mut I2c<'_, Async, Master>,
    address: u8,
    buffer: &mut [u8],
    ctx: &Ctx<'_>,
) -> Result<(), i2c::Error> {
    prepare_imu_bus(ctx).await?;
    let result = i2c.blocking_read(address, buffer);
    if matches!(result, Err(i2c::Error::Timeout)) {
        reset_i2c_host(ctx).await;
    }
    result
}

async fn write_i2c_bus(
    i2c: &mut I2c<'_, Async, Master>,
    address: u8,
    data: &[u8],
    ctx: &Ctx<'_>,
) -> Result<(), i2c::Error> {
    prepare_imu_bus(ctx).await?;
    let result = i2c.blocking_write(address, data);
    if matches!(result, Err(i2c::Error::Timeout)) {
        reset_i2c_host(ctx).await;
    }
    result
}

async fn write_read_i2c_bus(
    i2c: &mut I2c<'_, Async, Master>,
    address: u8,
    write: &[u8],
    read: &mut [u8],
    ctx: &Ctx<'_>,
) -> Result<(), i2c::Error> {
    prepare_imu_bus(ctx).await?;
    let result = i2c.blocking_write_read(address, write, read);
    if matches!(result, Err(i2c::Error::Timeout)) {
        reset_i2c_host(ctx).await;
    }
    result
}

fn send_imu_diag(ctx: &Ctx<'_>) {
    let mut buf = [0u8; 96];
    let mut put = Put {
        buf: &mut buf,
        n: 0,
    };
    {
        let s = ctx.shared.borrow();
        let d = &s.imu_diag;
        for value in [
            2,
            d.header_reads,
            d.empty_reads,
            d.header_errors,
            d.payload_errors,
            d.write_errors,
            d.nack,
            d.timeouts,
            d.bus_errors,
            d.arbitration,
            d.other_errors,
            d.invalid_lengths,
            d.resets,
            d.input_packets,
            d.last_input_ms,
            d.ina_errors,
            d.searches,
            d.max_i2c_us,
            d.max_service_gap_us,
            d.last_header,
            d.last_error_ms,
            i2c_pins(),
            pac::I2C1.isr().read().0,
            d.host_resets,
        ] {
            put.u32(value);
        }
    }
    ctx.out.send(mcu::IMU_DIAG, &[&buf]);
}

fn track_i2c(ctx: &Ctx<'_>, started: Instant) -> u32 {
    let elapsed = (Instant::now() - started).as_micros() as u32;
    let mut s = ctx.shared.borrow_mut();
    s.imu_diag.max_i2c_us = s.imu_diag.max_i2c_us.max(elapsed);
    elapsed
}

fn i2c_fault(ctx: &Ctx<'_>, stage: &str, error: i2c::Error, elapsed: u32) {
    let count = {
        let mut s = ctx.shared.borrow_mut();
        let d = &mut s.imu_diag;
        match stage {
            "header" => d.header_errors += 1,
            "payload" => d.payload_errors += 1,
            "write" => d.write_errors += 1,
            "ina" => d.ina_errors += 1,
            _ => {}
        }
        match error {
            i2c::Error::Nack => d.nack += 1,
            i2c::Error::Timeout => d.timeouts += 1,
            i2c::Error::Bus => d.bus_errors += 1,
            i2c::Error::Arbitration => d.arbitration += 1,
            _ => d.other_errors += 1,
        }
        d.last_error_ms = Instant::now().as_millis() as u32;
        d.header_errors + d.payload_errors + d.write_errors + d.ina_errors
    };
    // Capture early faults without flooding the link during a stuck bus.
    if count <= 8 || count % 100 == 0 {
        log!(
            ctx.out,
            "i2c fault #{count} {stage}: {error:?}, {elapsed}us, pins={}, ISR={:08x}",
            i2c_pins(),
            pac::I2C1.isr().read().0
        );
    }
}

async fn peripherals(i2c: &mut I2c<'_, Async, Master>, ctx: &Ctx<'_>) -> ! {
    Timer::after(IMU_BOOT_QUIET).await;
    let mut packet = [0u8; MAX_IMU_PACKET];
    let start = Instant::now();
    let (mut next_search, mut next_vbus, mut next_imu) = (start, start, start);
    // Reads in a row that each part has not answered.
    let (mut imu_missed, mut ina_missed) = (0u32, 0u32);
    loop {
        let quiet_until = ctx.shared.borrow_mut().imu_quiet_until.take();
        if let Some(deadline) = quiet_until {
            Timer::at(deadline).await;
            next_search = Instant::now();
        }
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
            if ctx.shared.borrow().imu_quiet_until.is_some() {
                continue;
            }
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
                    ctx.shared.borrow_mut().imu_gone();
                    ctx.out
                        .log("i2c: the IMU has stopped answering; looking for it again");
                }
            }
        }
        if now >= next_vbus {
            if ctx.shared.borrow().imu_quiet_until.is_some() {
                continue;
            }
            next_vbus = now + VBUS_PERIOD;
            let volts = match ina {
                Some(address) => {
                    let mut raw = [0u8; 2];
                    let started = Instant::now();
                    let result = write_read_i2c_bus(i2c, address, &[0x02], &mut raw, ctx).await;
                    let elapsed = track_i2c(ctx, started);
                    match result {
                        // 1.25 mV a count.
                        Ok(()) => Some((u16::from_be_bytes(raw) as u32 * 5 / 4) as u16),
                        Err(error) => {
                            i2c_fault(ctx, "ina", error, elapsed);
                            None
                        }
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
                s.health.ina_lost(now_ms());
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
    ctx.shared.borrow_mut().imu_diag.searches += 1;
    let (imu, ina) = {
        let s = ctx.shared.borrow();
        (s.imu, s.ina)
    };
    if ina.is_none() {
        for address in 0x40..=0x4F {
            // These belong to the SHTP IMU, not a register-based device.
            // A one-byte register request is not a valid SHTP packet and
            // must not be sent to it while looking for the INA226.
            if IMU_ADDRESSES.contains(&address) {
                continue;
            }
            let mut id = [0u8; 2];
            if write_read_i2c_bus(i2c, address, &[0xFE], &mut id, ctx)
                .await
                .is_ok()
                && id == *b"TI"
            {
                {
                    let mut s = ctx.shared.borrow_mut();
                    s.ina = Some(address);
                    s.health.ina_found();
                }
                log!(ctx.out, "i2c: INA226 at 0x{address:02X}");
                break;
            }
            // A missing or held-low device must not monopolize the executor
            // for a whole address scan.
            Timer::after_micros(1).await;
        }
    }
    if imu.is_none() {
        for address in IMU_ADDRESSES {
            // A header read takes nothing from the packet it heads: the next
            // read starts the packet again.
            let mut header = [0u8; 4];
            if read_imu_bus(i2c, address, &mut header, ctx).await.is_ok()
                && diag_link::imu_header_length(&header, IMU_LONGEST).is_some()
            {
                {
                    let mut s = ctx.shared.borrow_mut();
                    s.imu = Some(address);
                    // Its reports are asked for next, so it is silent from
                    // now until the first one comes.
                    s.health.imu_found(now_ms());
                }
                log!(ctx.out, "i2c: IMU at 0x{address:02X}");
                start_imu_reports(i2c, address, ctx).await;
                break;
            }
        }
    }
}

/// Assign sequence numbers here so automatic setup and host commands cannot
/// reuse one another's SHTP sequence numbers.
async fn write_imu(
    i2c: &mut I2c<'_, Async, Master>,
    address: u8,
    packet: &mut [u8],
    ctx: &Ctx<'_>,
) -> bool {
    if packet.len() < 4 || packet[2] >= 6 {
        ctx.shared.borrow_mut().imu_errors += 1;
        return false;
    }
    {
        let mut s = ctx.shared.borrow_mut();
        let sequence = &mut s.imu_sequence[packet[2] as usize];
        packet[3] = *sequence;
        *sequence = sequence.wrapping_add(1);
    }
    let started = Instant::now();
    let result = write_i2c_bus(i2c, address, packet, ctx).await;
    let elapsed = track_i2c(ctx, started);
    if let Err(error) = result {
        ctx.shared.borrow_mut().imu_errors += 1;
        i2c_fault(ctx, "write", error, elapsed);
        return false;
    }
    true
}

async fn start_imu_reports(i2c: &mut I2c<'_, Async, Master>, address: u8, ctx: &Ctx<'_>) {
    for report in IMU_DEFAULT_REPORTS {
        // SH-2 Set Feature: SHTP header, report ID, flags, sensitivity,
        // report interval, batch interval, sensor-specific configuration.
        let mut packet = [0u8; 21];
        packet[0] = 21;
        packet[2] = 2;
        packet[4] = 0xFD;
        packet[5] = report;
        packet[9..13].copy_from_slice(&IMU_REPORT_INTERVAL_US.to_le_bytes());
        if !write_imu(i2c, address, &mut packet, ctx).await {
            ctx.shared.borrow_mut().imu_gone();
            ctx.out
                .log("imu: default setup failed; looking for it again");
            return;
        }
    }
    ctx.out.log("imu: default reports requested at 100 Hz");
    // A reset puts the hub's calibration settings back to its defaults with its
    // reports, so they are set again with them, and then asked back.
    for (command, parameters) in [
        (SH2_ME_CALIBRATION, IMU_CALIBRATE),
        (SH2_PERIODIC_DCD_SAVE, IMU_DCD_SAVE_OFF),
        (SH2_ME_CALIBRATION, IMU_CALIBRATION_GET),
    ] {
        if !command_imu(i2c, address, command, &parameters, ctx).await {
            ctx.shared.borrow_mut().imu_gone();
            ctx.out
                .log("imu: calibration setup failed; looking for it again");
            return;
        }
    }
    ctx.out.log(
        "imu: its own accelerometer and magnetometer calibration off, and the \
         saving of it; asked back",
    );
}

/// An SH-2 Command Request: the report, its sequence, the command and nine
/// parameters, on the control channel.
async fn command_imu(
    i2c: &mut I2c<'_, Async, Master>,
    address: u8,
    command: u8,
    parameters: &[u8; 9],
    ctx: &Ctx<'_>,
) -> bool {
    let mut packet = [0u8; 16];
    packet[0] = 16;
    packet[2] = 2;
    packet[4] = SH2_COMMAND_REQUEST;
    {
        let mut s = ctx.shared.borrow_mut();
        packet[5] = s.imu_command_sequence;
        s.imu_command_sequence = s.imu_command_sequence.wrapping_add(1);
    }
    packet[6] = command;
    packet[7..16].copy_from_slice(parameters);
    write_imu(i2c, address, &mut packet, ctx).await
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
    ctx.shared.borrow_mut().imu_diag.header_reads += 1;
    let started = Instant::now();
    let result = read_imu_bus(i2c, address, &mut header, ctx).await;
    let elapsed = track_i2c(ctx, started);
    if let Err(error) = result {
        ctx.shared.borrow_mut().imu_errors += 1;
        i2c_fault(ctx, "header", error, elapsed);
        return false;
    }
    ctx.shared.borrow_mut().imu_diag.last_header = u32::from_le_bytes(header);
    let Some(length) = diag_link::imu_header_length(&header, IMU_LONGEST) else {
        invalid_imu_header(ctx, &header);
        return false;
    };
    if length <= 4 {
        ctx.shared.borrow_mut().imu_diag.empty_reads += 1;
        return true;
    }
    // A packet longer than this comes as a continuation the next time round.
    let n = length.min(MAX_IMU_PACKET);
    let t = now_us();
    let started = Instant::now();
    let result = read_imu_bus(i2c, address, &mut packet[..n], ctx).await;
    let elapsed = track_i2c(ctx, started);
    if let Err(error) = result {
        ctx.shared.borrow_mut().imu_errors += 1;
        i2c_fault(ctx, "payload", error, elapsed);
        return false;
    }
    if !matches!(diag_link::imu_header_length(packet, IMU_LONGEST), Some(5..)) {
        invalid_imu_header(ctx, packet);
        return false;
    }
    ctx.shared.borrow_mut().imu_packets += 1;
    if packet[2] == 3 || packet[2] == 4 || packet[2] == 5 {
        let mut s = ctx.shared.borrow_mut();
        s.imu_diag.input_packets += 1;
        s.imu_diag.last_input_ms = Instant::now().as_millis() as u32;
        s.health.imu_input();
    }
    ctx.out
        .send(mcu::IMU_PACKET, &[&t.to_le_bytes(), &packet[..n]]);
    if n >= 5 && packet[2] == 1 && packet[4] == 0x01 {
        // An IMU reset clears its enabled reports. Restore defaults even if
        // no GUI is connected. An explicit host 'off' lasts until a reset.
        let mut s = ctx.shared.borrow_mut();
        s.imu_diag.resets += 1;
        s.imu_sequence = [0; 6];
        s.imu_gone();
        s.imu_quiet_until = Some(Instant::now() + IMU_BOOT_QUIET);
    }
    true
}

fn invalid_imu_header(ctx: &Ctx<'_>, header: &[u8]) {
    let count = {
        let mut s = ctx.shared.borrow_mut();
        s.imu_errors += 1;
        s.imu_diag.invalid_lengths += 1;
        s.imu_diag.last_error_ms = Instant::now().as_millis() as u32;
        s.imu_diag.invalid_lengths
    };
    if count <= 8 || count % 100 == 0 {
        log!(
            ctx.out,
            "imu: invalid header #{count}: {:02x?}",
            &header[..4]
        );
    }
}

async fn run_job(i2c: &mut I2c<'_, Async, Master>, job: Job, ctx: &Ctx<'_>) {
    match job {
        Job::ImuWrite(mut packet) => {
            let imu = ctx.shared.borrow().imu;
            match imu {
                Some(address) => {
                    let reset = packet.len() == 5 && packet[2] == 1 && packet[4] == 1;
                    if write_imu(i2c, address, &mut packet, ctx).await && reset {
                        let mut s = ctx.shared.borrow_mut();
                        s.imu_gone();
                        s.imu_sequence = [0; 6];
                        s.imu_quiet_until = Some(Instant::now() + IMU_BOOT_QUIET);
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
                (_, 0) => write_i2c_bus(i2c, address, &write, ctx).await,
                (true, n) => read_imu_bus(i2c, address, &mut data[..n], ctx).await,
                (false, n) => write_read_i2c_bus(i2c, address, &write, &mut data[..n], ctx).await,
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
