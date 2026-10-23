//! The two wheel motors on the carrier's bus C, driven from this board through
//! U3: the first motion that goes the way the robot's will, rather than through
//! DAMIAO's debugger on the bench.
//!
//! FDCAN3 on PB4/PA8 at 1 Mbit/s classic CAN, which the motors default to, into
//! U3 and out on J4 (docs/CARRIER.md). USART1 on PA9/PA10 at 115 200 8N1 to the
//! Banana Pi, as `serial_check` uses it, carries text both ways: a line in is a
//! command, and every command's answer ends with a line saying `ready`.
//!
//! ```text
//! scan        look for motors at CAN IDs 1 to 16, by register reads alone
//! run [n]     n cycles (60 if not given) of ±45° at 2 Hz on every motor found
//! tx [s]      one frame back to back for s seconds (60 if not given), for a
//!             scope on the bus; nothing on the bus answers it
//! ```
//!
//! `sbc/wheel_check.py` is the Pi's end of it. The image scans as it starts,
//! which cannot move anything; nothing moves until a run is asked for.
//!
//! A run holds each motor to `centre + a sin(2π·2t)` in MIT mode, with the
//! sine's own speed fed forward, where `centre` is wherever the motor stood
//! when it was enabled. `a` rises from nothing to 45° over the first two
//! cycles and falls back over the last two, so `run 60` is 64 cycles, 32 s. It
//! is the bench GUI's safety, by the same rule: the target is kept within
//! [`REACH_NM`] of spring of where the motor is, and the speed within the same
//! of damping, so a wheel that is held is pushed with about 1 Nm at most,
//! against the motor's 0.8 Nm continuous and 3 Nm peak.
//!
//! The run stops, disables every motor and says why on any byte from the Pi
//! other than a line ending, on the power button, on a motor that faults,
//! disables itself, falls silent for [`SILENT`], or strays [`ABORT_ERROR_DEG`]
//! from its target, and on a bus that will not take a frame for
//! [`SEND_TIMEOUT`]. It ends with a line per motor and a verdict. A motor
//! passes if it ran every cycle at full amplitude within 10 % of 45°, never
//! strayed [`PASS_ERROR_DEG`] from its target, and answered 99 % of its
//! commands; the bus passes if both its motors do.
//!
//! What it cannot do: if this image dies with a motor enabled, the motor holds
//! its last command unless its TIMEOUT register is set, which the scan reports.
//! The watchdog then puts the board in its bootloader within 30 s, which lets
//! go of HOLD.
//!
//! A motor in another mode is switched to MIT for the run, in RAM only, so it
//! is back in its saved mode the next time it is powered.

#![no_std]
#![no_main]

use core::cell::RefCell;
use core::f32::consts::PI;
use core::fmt::Write as _;

use board::power;
use embassy_executor::Spawner;
use embassy_futures::join::join5;
use embassy_stm32::can::config::TxBufferMode;
use embassy_stm32::can::enums::BusErrorMode;
use embassy_stm32::can::{self, CanConfigurator, CanRx, CanTx, Frame, Properties};
use embassy_stm32::gpio::{Level, Output, Speed};
use embassy_stm32::i2c::{self, I2c, Master};
use embassy_stm32::mode::Blocking;
use embassy_stm32::usart::{self, BufferedUart, BufferedUartRx, BufferedUartTx};
use embassy_stm32::{bind_interrupts, pac, peripherals};
use embassy_time::{Duration, Instant, Ticker, Timer, with_timeout};
use embedded_can::Id;
use embedded_io_async::{Read, Write};
use heapless::{String, Vec};
use libm::{atan2f, cosf, sinf, sqrtf};

bind_interrupts!(struct Irqs {
    FDCAN3_IT0 => can::IT0InterruptHandler<peripherals::FDCAN3>;
    FDCAN3_IT1 => can::IT1InterruptHandler<peripherals::FDCAN3>;
    USART1 => usart::BufferedInterruptHandler<peripherals::USART1>;
});

/// The rate the Pi's end is opened at, as for `serial_check`.
const BAUD: u32 = 115_200;
/// The motors' default, and what bus C is laid out for (docs/CARRIER.md).
const BITRATE: u32 = 1_000_000;

// ---- the motion --------------------------------------------------------------

const DEG: f32 = PI / 180.0;
const AMPLITUDE: f32 = 45.0 * DEG;
/// How often every motor is sent its command.
const TICK_HZ: u32 = 500;
/// 2 Hz, as a whole number of ticks so that every cycle is the same.
const CYCLE_TICKS: u32 = 250;
const FREQ_HZ: f32 = TICK_HZ as f32 / CYCLE_TICKS as f32;
const OMEGA: f32 = 2.0 * PI * FREQ_HZ;
/// Cycles over which the amplitude rises from nothing, and falls back.
const FADE_CYCLES: u32 = 2;
const FADE_RATE: f32 = FREQ_HZ / FADE_CYCLES as f32;
const DEFAULT_CYCLES: u32 = 60;
/// An hour.
const MAX_CYCLES: u32 = 7200;

// ---- a frame for a scope -----------------------------------------------------

/// Alternate bits in the ID and the data, so that no bit is stuffed and the
/// frame reads as a clock on the scope: 1 µs a bit. No motor here answers to
/// it, since a motor takes a frame by its ID's low eight bits, 0x55 here.
const TX_ID: u16 = 0x555;
const TX_DATA: [u8; 8] = [0x55; 8];
const TX_DEFAULT_S: u32 = 60;
const TX_MAX_S: u32 = 3600;

/// MIT-mode stiffness, Nm/rad, and damping, Nm·s/rad. Unloaded, the output
/// needs a few hundredths of a newton-metre to follow this sine, so these hold
/// it to within a degree or so while leaving the reach below generous.
const KP: f32 = 8.0;
const KD: f32 = 0.2;
/// The most either the spring or the damper may push with, as in the bench
/// GUI's limits.
const REACH_NM: f32 = 0.5;
/// How close to a motor's VMAX, or to the speed MAX_SPD allows, the sine may
/// come. Past VMAX the motor's speed reading wraps round to the other sign.
const SPEED_MARGIN: f32 = 0.8;
/// How close to the end of a motor's ±PMAX the swing may come.
const POSITION_MARGIN: f32 = 0.95;

// ---- stopping and passing ---------------------------------------------------

const SILENT: Duration = Duration::from_millis(20);
const ABORT_ERROR_DEG: f32 = 15.0;
const SEND_TIMEOUT: Duration = Duration::from_millis(5);
/// A motor answers a register read within a few hundred microseconds.
const REPLY_TIMEOUT: Duration = Duration::from_millis(10);
const PASS_AMPLITUDE: f32 = 0.1;
const PASS_ERROR_DEG: f32 = 5.0;
const PASS_REPLIES: f32 = 0.99;

// ---- DAMIAO's protocol, as bench/damiao.py has it ---------------------------

const MIT: u32 = 1;
const MODE_NAMES: [&str; 5] = [
    "mode 0",
    "MIT",
    "position-velocity",
    "velocity",
    "force-position",
];
/// What each mode adds to the motor's CAN ID for its frames, by mode.
const MODE_OFFSET: [u16; 5] = [0, 0x000, 0x100, 0x200, 0x300];
const KP_MAX: f32 = 500.0;
const KD_MAX: f32 = 5.0;

const ENABLE: u8 = 0xFC;
const DISABLE: u8 = 0xFD;
const CLEAR_ERROR: u8 = 0xFB;
const REG_READ: u8 = 0x33;
const REG_WRITE: u8 = 0x55;
const STATUS: u8 = 0xCC;
const CONFIG_ID: u16 = 0x7FF;

const MAX_SPD: u8 = 0x06;
const MST_ID: u8 = 0x07;
const ESC_ID: u8 = 0x08;
const TIMEOUT: u8 = 0x09;
const CTRL_MODE: u8 = 0x0A;
const GR: u8 = 0x14;
const PMAX: u8 = 0x15;
const VMAX: u8 = 0x16;
const TMAX: u8 = 0x17;

const DISABLED: u8 = 0x0;
const ENABLED: u8 = 0x1;

/// The motors a scan can find: one for every CAN ID it tries.
const MAX_MOTORS: usize = 16;
/// The motors bus C carries.
const BUS_MOTORS: usize = 2;
/// The longest line sent to the Pi.
const LINE: usize = 256;

#[derive(Clone, Copy)]
struct Feedback {
    at: Instant,
    state: u8,
    pos: f32,
    vel: f32,
    torque: f32,
    t_mos: u8,
    t_rotor: u8,
}

impl Feedback {
    fn fault(&self) -> bool {
        self.state >= 0x8
    }
}

fn state_name(state: u8) -> &'static str {
    match state {
        0x0 => "disabled",
        0x1 => "enabled",
        0x8 => "overvoltage",
        0x9 => "undervoltage",
        0xA => "overcurrent",
        0xB => "MOSFET over-temperature",
        0xC => "winding over-temperature",
        0xD => "communication lost",
        0xE => "overload",
        _ => "an unknown state",
    }
}

/// What the bus knows of one motor: its IDs, its mode, its mapping ranges, and
/// what it last reported.
#[derive(Clone)]
struct Motor {
    id: u16,
    master: u16,
    mode: u32,
    pmax: f32,
    vmax: f32,
    tmax: f32,
    /// The output speed MAX_SPD holds it to, if both it and the gearing read.
    speed_cap: Option<f32>,
    timeout: Option<u32>,
    feedback: Option<Feedback>,
    /// Feedback frames heard from it, to tell a fresh one from the last.
    heard: u32,
}

impl Motor {
    fn new(id: u16) -> Self {
        Self {
            id,
            master: 0,
            mode: MIT,
            pmax: 12.566,
            vmax: 50.0,
            tmax: 5.0,
            speed_cap: None,
            timeout: None,
            feedback: None,
            heard: 0,
        }
    }

    fn mode_name(&self) -> &'static str {
        MODE_NAMES
            .get(self.mode as usize)
            .copied()
            .unwrap_or("an unknown mode")
    }

    fn decode(&self, d: &[u8], at: Instant) -> Feedback {
        let p = (d[1] as u32) << 8 | d[2] as u32;
        let v = (d[3] as u32) << 4 | (d[4] >> 4) as u32;
        let q = ((d[4] & 0xF) as u32) << 8 | d[5] as u32;
        Feedback {
            at,
            state: d[0] >> 4,
            pos: to_float(p, -self.pmax, self.pmax, 16),
            vel: to_float(v, -self.vmax, self.vmax, 12),
            torque: to_float(q, -self.tmax, self.tmax, 12),
            t_mos: d[6],
            t_rotor: d[7],
        }
    }
}

fn to_uint(x: f32, lo: f32, hi: f32, bits: u32) -> u32 {
    ((x.clamp(lo, hi) - lo) * ((1u32 << bits) - 1) as f32 / (hi - lo)) as u32
}

fn to_float(u: u32, lo: f32, hi: f32, bits: u32) -> f32 {
    u as f32 * (hi - lo) / ((1u32 << bits) - 1) as f32 + lo
}

enum Request {
    Scan,
    Run(u32),
    Transmit(u32),
    Unknown,
}

/// What the futures share. Each takes it only between awaits.
struct Shared {
    motors: Vec<Motor, MAX_MOTORS>,
    /// The register request awaiting its reply: CAN ID, operation, register.
    pending: Option<(u16, u8, u8)>,
    reply: Option<[u8; 4]>,
    request: Option<Request>,
    running: bool,
    /// Set by any byte from the Pi, other than a line ending, during a run.
    interrupted: bool,
}

impl Shared {
    fn motor(&self, id: u16) -> Option<&Motor> {
        self.motors.iter().find(|m| m.id == id)
    }

    fn motor_mut(&mut self, id: u16) -> Option<&mut Motor> {
        self.motors.iter_mut().find(|m| m.id == id)
    }
}

#[embassy_executor::main]
async fn main(_spawner: Spawner) {
    board::early_init();
    let mut config = board::config();
    // FDCAN straight from the 8 MHz crystal, as it is out of reset: eight
    // quanta a bit at 1 Mbit/s, sampled at 87.5 %.
    config.rcc.mux.fdcansel = embassy_stm32::rcc::mux::Fdcansel::HSE;
    let p = embassy_stm32::init(config);

    // Blue LED D1, from PC6 through 5.1 k to ground: high is on.
    let mut led = Output::new(p.PC6, Level::Low, Speed::Low);

    let mut uart_config = usart::Config::default();
    uart_config.baudrate = BAUD;
    // Large enough that a run's lines never wait for the wire.
    let mut tx_buffer = [0u8; 2048];
    let mut rx_buffer = [0u8; 64];
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
    let (uart_tx, mut uart_rx) = uart.split();

    let mut can = CanConfigurator::new(p.FDCAN3, p.PA8, p.PB4, Irqs);
    can.set_bitrate(BITRATE);
    // Frames go in the order they are written. In the default priority queue,
    // an enable and the first command after it share an ID and either could
    // go first.
    can.set_config(can.config().set_tx_buffer_mode(TxBufferMode::Fifo));
    let (can_tx, mut can_rx, properties) = can.into_normal_mode().split();

    let shared = RefCell::new(Shared {
        motors: Vec::new(),
        pending: None,
        reply: None,
        request: None,
        running: false,
        interrupted: false,
    });
    let mut bus = Bus {
        tx: can_tx,
        properties,
        shared: &shared,
    };
    let mut out = Out(uart_tx);

    let mut i2c_config = i2c::Config::default();
    // A backstop: the carrier's own pull-ups are fitted only if no module
    // brings its own.
    i2c_config.scl_pullup = true;
    i2c_config.sda_pullup = true;
    i2c_config.timeout = Duration::from_millis(10);
    let mut monitor = Monitor(I2c::new_blocking(p.I2C1, p.PA15, p.PB7, i2c_config));

    join5(
        board::heartbeat(&mut led),
        board::watchdog(p.IWDG),
        listen(&mut uart_rx, &shared),
        hear(&mut can_rx, &shared),
        serve(&mut bus, &mut monitor, &mut out),
    )
    .await;
}

/// The carrier's INA226 (A3), which reads the battery bus on its VBS pin: the
/// motors' supply as the power board passes it on.
struct Monitor<'d>(I2c<'d, Blocking, Master>);

impl Monitor<'_> {
    /// The battery bus in volts, or None if no INA226 answers. Found by TI's
    /// manufacturer ID, since the module's address straps are not recorded.
    fn volts(&mut self) -> Option<f32> {
        for address in 0x40..=0x4F {
            let mut id = [0; 2];
            if self
                .0
                .blocking_write_read(address, &[0xFE], &mut id)
                .is_ok()
                && id == *b"TI"
            {
                let mut raw = [0; 2];
                self.0
                    .blocking_write_read(address, &[0x02], &mut raw)
                    .ok()?;
                // 1.25 mV a count.
                return Some(u16::from_be_bytes(raw) as f32 * 1.25e-3);
            }
        }
        None
    }
}

// ---- the Pi's side -----------------------------------------------------------

struct Out<'d>(BufferedUartTx<'d>);

impl Out<'_> {
    async fn send(&mut self, text: &str) {
        let _ = self.0.write_all(text.as_bytes()).await;
        let _ = self.0.write_all(b"\r\n").await;
    }
}

/// Sends one formatted line to the Pi.
macro_rules! say {
    ($out:expr, $($arg:tt)*) => {{
        let mut text: String<LINE> = String::new();
        let _ = write!(text, $($arg)*);
        $out.send(&text).await;
    }};
}

/// Why a run was refused or cut short, in a few words.
type Why = String<120>;

macro_rules! why {
    ($($arg:tt)*) => {{
        let mut text = Why::new();
        let _ = write!(text, $($arg)*);
        text
    }};
}

/// Collects command lines from the Pi, and during a run turns any byte other
/// than a line ending into a stop.
async fn listen(rx: &mut BufferedUartRx<'_>, shared: &RefCell<Shared>) -> ! {
    let mut line: String<32> = String::new();
    let mut chunk = [0u8; 32];
    loop {
        let result = rx.read(&mut chunk).await;
        let mut s = shared.borrow_mut();
        let Ok(n) = result else {
            // Noise or an overrun: something was sent, so a run stops.
            if s.running {
                s.interrupted = true;
            }
            continue;
        };
        for &byte in &chunk[..n] {
            let end = byte == b'\r' || byte == b'\n';
            if s.running {
                if !end {
                    s.interrupted = true;
                }
                line.clear();
            } else if end {
                if !line.is_empty() {
                    s.request = Some(parse(&line));
                    line.clear();
                }
            } else {
                // A line too long for this is no command, and reads as none.
                let _ = line.push(byte as char);
            }
        }
    }
}

fn parse(line: &str) -> Request {
    let mut words = line.split_ascii_whitespace();
    match (words.next(), words.next(), words.next()) {
        (Some("scan"), None, _) => Request::Scan,
        (Some("run"), None, _) => Request::Run(DEFAULT_CYCLES),
        (Some("run"), Some(n), None) => match n.parse() {
            Ok(n) if (1..=MAX_CYCLES).contains(&n) => Request::Run(n),
            _ => Request::Unknown,
        },
        (Some("tx"), None, _) => Request::Transmit(TX_DEFAULT_S),
        (Some("tx"), Some(s), None) => match s.parse() {
            Ok(s) if (1..=TX_MAX_S).contains(&s) => Request::Transmit(s),
            _ => Request::Unknown,
        },
        _ => Request::Unknown,
    }
}

/// Answers the Pi's commands, one at a time. Never returns.
async fn serve(bus: &mut Bus<'_>, monitor: &mut Monitor<'_>, out: &mut Out<'_>) -> ! {
    let mut line: String<LINE> = String::new();
    let _ = write!(
        line,
        "wheel_check: bus C (FDCAN3, U3, J4) at {} kbit/s, reset by ",
        BITRATE / 1000
    );
    let _ = board::reset_cause(&mut line);
    out.send(&line).await;
    scan(bus, monitor, out).await;
    say!(
        out,
        "commands: scan, run [cycles] ({DEFAULT_CYCLES} if not given), or tx [seconds] ({TX_DEFAULT_S} if not given)"
    );
    out.send("ready").await;

    let mut told_off = false;
    loop {
        if power::off_requested() && !told_off {
            told_off = true;
            out.send("power: button held, HOLD released").await;
        }
        let request = bus.shared.borrow_mut().request.take();
        match request {
            Some(Request::Scan) => scan(bus, monitor, out).await,
            Some(Request::Run(cycles)) => run(bus, out, cycles).await,
            Some(Request::Transmit(seconds)) => transmit(bus, out, seconds).await,
            Some(Request::Unknown) => out.send("? scan, run [cycles], or tx [seconds]").await,
            None => {
                Timer::after_millis(10).await;
                continue;
            }
        }
        out.send("ready").await;
    }
}

// ---- the bus -----------------------------------------------------------------

struct Bus<'d> {
    tx: CanTx<'d>,
    properties: Properties,
    shared: &'d RefCell<Shared>,
}

/// Hears every frame on bus C: a register reply that is awaited goes to its
/// request, and anything else is a motor's feedback.
async fn hear(rx: &mut CanRx<'_>, shared: &RefCell<Shared>) -> ! {
    loop {
        // An error here is the controller's last error code, read with no
        // frame waiting; the counters in `Bus::health` say the same in sum.
        let Ok(envelope) = rx.read().await else {
            continue;
        };
        let frame = envelope.frame;
        let Id::Standard(id) = frame.id() else {
            continue;
        };
        let d = frame.data();
        if d.len() != 8 {
            continue;
        }
        let mut s = shared.borrow_mut();
        let key = (d[0] as u16 | (d[1] as u16) << 8, d[2], d[3]);
        if s.pending == Some(key) {
            s.pending = None;
            s.reply = Some([d[4], d[5], d[6], d[7]]);
            continue;
        }
        if (d[2] == REG_READ || d[2] == REG_WRITE) && s.motor(key.0).is_some() {
            // A reply that came after its request gave up. Feedback can look
            // the same, about one frame in twenty thousand, and losing that
            // one beats reading a register as a position.
            continue;
        }
        let at = Instant::now();
        if let Some(m) = feedback_motor(&mut s.motors, id.as_raw(), d[0] & 0x0F) {
            m.feedback = Some(m.decode(d, at));
            m.heard = m.heard.wrapping_add(1);
        }
    }
}

/// The motor a feedback frame is from, by the bench's rule: by its feedback ID
/// if exactly one motor has that, and otherwise by the low four bits of the
/// CAN ID it carries in its first byte, if exactly one motor has those.
fn feedback_motor(motors: &mut [Motor], id: u16, nibble: u8) -> Option<&mut Motor> {
    if id != 0 && motors.iter().filter(|m| m.master == id).count() == 1 {
        return motors.iter_mut().find(|m| m.master == id);
    }
    let ours = |m: &Motor| (m.id & 0x0F) as u8 == nibble;
    if motors.iter().filter(|m| ours(m)).count() == 1 {
        return motors.iter_mut().find(|m| ours(m));
    }
    None
}

impl Bus<'_> {
    /// Queues a frame, or gives up after [`SEND_TIMEOUT`] and clears the
    /// transmit buffers: a frame nothing acknowledges is retried for ever and
    /// holds its buffer while it is.
    async fn send(&mut self, id: u16, data: [u8; 8]) -> bool {
        let frame = Frame::new_standard(id, &data).unwrap();
        if with_timeout(SEND_TIMEOUT, self.tx.write(&frame))
            .await
            .is_ok()
        {
            return true;
        }
        cancel_pending();
        false
    }

    async fn request(&mut self, id: u16, op: u8, rid: u8, value: [u8; 4]) -> Option<[u8; 4]> {
        {
            let mut s = self.shared.borrow_mut();
            s.pending = Some((id, op, rid));
            s.reply = None;
        }
        let [lo, hi] = id.to_le_bytes();
        let [a, b, c, d] = value;
        if self.send(CONFIG_ID, [lo, hi, op, rid, a, b, c, d]).await {
            let deadline = Instant::now() + REPLY_TIMEOUT;
            while Instant::now() < deadline {
                if let Some(reply) = self.shared.borrow_mut().reply.take() {
                    return Some(reply);
                }
                Timer::after_micros(100).await;
            }
        }
        self.shared.borrow_mut().pending = None;
        None
    }

    async fn read_u32(&mut self, id: u16, rid: u8) -> Option<u32> {
        let raw = self.request(id, REG_READ, rid, [0; 4]).await?;
        Some(u32::from_le_bytes(raw))
    }

    async fn read_f32(&mut self, id: u16, rid: u8) -> Option<f32> {
        let raw = self.request(id, REG_READ, rid, [0; 4]).await?;
        Some(f32::from_le_bytes(raw))
    }

    /// Asks a motor for a feedback frame without commanding it, and returns
    /// the frame, or None if none came.
    ///
    /// Frames queued just before this are answered just after it is sent, and
    /// the first answer to come back would otherwise be taken for this one's:
    /// on 2026-10-23 the answer to the command before an enable, which said
    /// disabled, was read as the motor refusing to enable. So every frame
    /// already queued goes, and its answer lands, first.
    async fn status(&mut self, id: u16) -> Option<Feedback> {
        let deadline = Instant::now() + SEND_TIMEOUT;
        while pac::FDCAN3.txbrp().read().0 != 0 && Instant::now() < deadline {
            Timer::after_micros(100).await;
        }
        // An answer is one frame, about 130 µs at 1 Mbit/s.
        Timer::after_millis(1).await;
        let before = self.shared.borrow().motor(id)?.heard;
        let [lo, hi] = id.to_le_bytes();
        if !self.send(CONFIG_ID, [lo, hi, STATUS, 0, 0, 0, 0, 0]).await {
            return None;
        }
        let deadline = Instant::now() + REPLY_TIMEOUT;
        while Instant::now() < deadline {
            {
                let s = self.shared.borrow();
                let m = s.motor(id)?;
                if m.heard != before {
                    return m.feedback;
                }
            }
            Timer::after_micros(100).await;
        }
        None
    }

    /// Enable, disable or clear error, sent to the frame ID of the mode the
    /// motor is in.
    async fn special(&mut self, m: &Motor, code: u8) -> bool {
        let offset = MODE_OFFSET.get(m.mode as usize).copied().unwrap_or(0);
        let mut data = [0xFF; 8];
        data[7] = code;
        self.send(m.id + offset, data).await
    }

    async fn mit(&mut self, m: &Motor, p: f32, v: f32, kp: f32, kd: f32, t: f32) -> bool {
        let p = to_uint(p, -m.pmax, m.pmax, 16);
        let v = to_uint(v, -m.vmax, m.vmax, 12);
        let kp = to_uint(kp, 0.0, KP_MAX, 12);
        let kd = to_uint(kd, 0.0, KD_MAX, 12);
        let t = to_uint(t, -m.tmax, m.tmax, 12);
        let data = [
            (p >> 8) as u8,
            p as u8,
            (v >> 4) as u8,
            ((v & 0xF) << 4 | kp >> 8) as u8,
            kp as u8,
            (kd >> 4) as u8,
            ((kd & 0xF) << 4 | t >> 8) as u8,
            t as u8,
        ];
        self.send(m.id, data).await
    }

    /// The controller's error counters and state, for a line.
    ///
    /// Not its last error code: the driver reads the status register that holds
    /// it, which resets it, so by the time this looks it says nothing.
    /// Transmit errors held at 128, error passive, are the code's work done
    /// another way: a frame that goes out and comes back intact but that no
    /// node acknowledges climbs to 128 and stays there, where a fault between
    /// this board and the bus would be bit errors, which go on to bus off.
    fn health(&self) -> Why {
        let mode = match self.properties.bus_error_mode() {
            BusErrorMode::ErrorActive => "error active",
            BusErrorMode::ErrorPassive => "error passive",
            BusErrorMode::BusOff => "bus off",
        };
        why!(
            "transmit errors {}, receive errors {}, {}",
            self.properties.tx_error_count(),
            self.properties.rx_error_count(),
            mode
        )
    }
}

/// Withdraws every frame waiting to go.
fn cancel_pending() {
    pac::FDCAN3.txbcr().write(|w| {
        for n in 0..3 {
            w.set_cr(n, true);
        }
    });
}

// ---- scan --------------------------------------------------------------------

/// Finds the motors at CAN IDs 1 to 16 and reads what a run needs of each.
/// Register reads and status requests only, so nothing moves.
async fn scan(bus: &mut Bus<'_>, monitor: &mut Monitor<'_>, out: &mut Out<'_>) {
    match monitor.volts() {
        Some(v) => say!(out, "scan: battery bus {v:.2} V"),
        None => {
            out.send("scan: battery bus not read: no INA226 answered on I2C1")
                .await
        }
    }
    bus.shared.borrow_mut().motors.clear();
    for id in 1..=MAX_MOTORS as u16 {
        if bus.read_u32(id, ESC_ID).await.is_none() {
            continue;
        }
        let mut m = Motor::new(id);
        if let Some(v) = bus.read_u32(id, MST_ID).await {
            m.master = v as u16;
        }
        if let Some(v) = bus.read_u32(id, CTRL_MODE).await {
            m.mode = v;
        }
        if let Some(v) = bus.read_f32(id, PMAX).await {
            m.pmax = v;
        }
        if let Some(v) = bus.read_f32(id, VMAX).await {
            m.vmax = v;
        }
        if let Some(v) = bus.read_f32(id, TMAX).await {
            m.tmax = v;
        }
        // MAX_SPD is at the rotor, so the output's limit is it over the
        // gearing (bench/damiao.py's `speed_cap`).
        if let (Some(spd), Some(gr)) = (bus.read_f32(id, MAX_SPD).await, bus.read_f32(id, GR).await)
            && spd > 0.0
            && gr > 0.0
        {
            m.speed_cap = Some(spd / gr);
        }
        m.timeout = bus.read_u32(id, TIMEOUT).await;
        let _ = bus.shared.borrow_mut().motors.push(m.clone());
        let state = bus
            .status(id)
            .await
            .map_or("no answer to a status request", |f| state_name(f.state));

        let mut line: String<LINE> = String::new();
        let _ = write!(
            line,
            "scan: motor {id}: feedback ID 0x{:02X}, {} mode, {state}; PMAX {:.2} rad, VMAX {:.1} rad/s, TMAX {:.1} Nm",
            m.master,
            m.mode_name(),
            m.pmax,
            m.vmax,
            m.tmax
        );
        if let Some(cap) = m.speed_cap {
            let _ = write!(line, ", speed cap {cap:.1} rad/s");
        }
        match m.timeout {
            Some(0) => {
                let _ = write!(line, ", TIMEOUT 0 (off)");
            }
            Some(t) => {
                let _ = write!(line, ", TIMEOUT {t}");
            }
            None => {}
        }
        out.send(&line).await;
    }

    let health = bus.health();
    // What a scan of an empty bus leaves behind: frames nothing acknowledged.
    if pac::FDCAN3.txbrp().read().0 != 0 {
        cancel_pending();
    }
    let found = bus.shared.borrow().motors.len();
    let motors = if found == 1 { "motor" } else { "motors" };
    say!(out, "scan: {found} {motors} on bus C; {health}");
    match found {
        0 if bus.properties.tx_error_count() > 0 => out.send(
            "scan: nothing acknowledged a frame, so no motor is powered and on this bus. Is each motor's LED lit, and J4's lead in with black on the dot?",
        )
        .await,
        0 => out.send("scan: frames were acknowledged, but nothing answered at CAN IDs 1 to 16").await,
        1 => out.send(
            "scan: bus C carries two motors. Two at one CAN ID answer as one: give each its own on the bench",
        )
        .await,
        BUS_MOTORS => {}
        _ => say!(out, "scan: bus C carries {BUS_MOTORS} motors, and {found} answered"),
    }
}

// ---- tx ----------------------------------------------------------------------

/// Keeps bus C busy with [`TX_ID`] for `seconds`, or until any byte from the
/// Pi, for a scope. The frame goes again as soon as it is done whether or not
/// anything acknowledges it: acknowledged, the next is queued behind it, and
/// unacknowledged, the controller repeats it by itself for as long as it is
/// left queued.
async fn transmit(bus: &mut Bus<'_>, out: &mut Out<'_>, seconds: u32) {
    say!(
        out,
        "tx: ID 0x{TX_ID:03X}, eight bytes of 0x55, back to back at {} kbit/s for {seconds} s. Any byte stops it.",
        BITRATE / 1000
    );
    {
        let mut s = bus.shared.borrow_mut();
        s.running = true;
        s.interrupted = false;
    }
    let frame = Frame::new_standard(TX_ID, &TX_DATA).unwrap();
    let start = Instant::now();
    let end = start + Duration::from_secs(seconds as u64);
    let mut queued: u32 = 0;
    let mut why = "done";
    while Instant::now() < end {
        if bus.shared.borrow().interrupted {
            why = "stopped from the Pi";
            break;
        }
        if power::off_requested() {
            why = "stopped by the power button";
            break;
        }
        // Waits only while all three buffers are full, which unacknowledged
        // is for good; the timeout is how often the stops above are looked at.
        if with_timeout(Duration::from_millis(10), bus.tx.write(&frame))
            .await
            .is_ok()
        {
            queued += 1;
        }
    }
    bus.shared.borrow_mut().running = false;
    let health = bus.health();
    let pending = pac::FDCAN3.txbrp().read().0.count_ones();
    cancel_pending();
    let acknowledged = queued.saturating_sub(pending);
    say!(
        out,
        "tx: {why} after {:.1} s: {acknowledged} frames acknowledged of {queued} queued; {health}",
        start.elapsed().as_millis() as f32 / 1000.0
    );
}

// ---- run ---------------------------------------------------------------------

/// One motor's figures over one cycle, or over a run.
#[derive(Clone, Copy, Default)]
struct Figures {
    /// The position against the sine and the cosine, to find the fundamental.
    sin_sum: f32,
    cos_sum: f32,
    samples: u32,
    /// The furthest from its target, in radians.
    worst: f32,
    torque: f32,
    t_mos: u8,
    t_rotor: u8,
}

impl Figures {
    fn add(&mut self, x: f32, theta: f32, error: f32, f: &Feedback) {
        self.sin_sum += x * sinf(theta);
        self.cos_sum += x * cosf(theta);
        self.samples += 1;
        self.worst = self.worst.max(error.abs());
        self.torque = self.torque.max(f.torque.abs());
        self.t_mos = self.t_mos.max(f.t_mos);
        self.t_rotor = self.t_rotor.max(f.t_rotor);
    }

    /// The amplitude of the motion at the sine's frequency, in radians, and how
    /// far it lags the target, in degrees. For x = a sin(θ − φ), the sums are
    /// (n/2)·a·cos φ and −(n/2)·a·sin φ.
    fn fundamental(&self) -> (f32, f32) {
        let n = self.samples.max(1) as f32;
        let amplitude = 2.0 * sqrtf(self.sin_sum * self.sin_sum + self.cos_sum * self.cos_sum) / n;
        (amplitude, atan2f(-self.cos_sum, self.sin_sum) / DEG)
    }
}

/// One motor's record over a whole run.
#[derive(Clone, Copy)]
struct Record {
    full_cycles: u32,
    amplitude_lo: f32,
    amplitude_hi: f32,
    lag_sum: f32,
    worst: f32,
    torque: f32,
    t_mos: u8,
    t_rotor: u8,
    replies: u32,
}

impl Record {
    fn new() -> Self {
        Self {
            full_cycles: 0,
            amplitude_lo: f32::MAX,
            amplitude_hi: 0.0,
            lag_sum: 0.0,
            worst: 0.0,
            torque: 0.0,
            t_mos: 0,
            t_rotor: 0,
            replies: 0,
        }
    }

    fn add(&mut self, cycle: &Figures, full: bool) {
        if full {
            let (amplitude, lag) = cycle.fundamental();
            self.full_cycles += 1;
            self.amplitude_lo = self.amplitude_lo.min(amplitude);
            self.amplitude_hi = self.amplitude_hi.max(amplitude);
            self.lag_sum += lag;
        }
        self.worst = self.worst.max(cycle.worst);
        self.torque = self.torque.max(cycle.torque);
        self.t_mos = self.t_mos.max(cycle.t_mos);
        self.t_rotor = self.t_rotor.max(cycle.t_rotor);
    }
}

/// The amplitude's share at tick `k` of a run of `total` ticks, and how fast
/// that share is changing, per second.
fn fade(k: u32, total: u32) -> (f32, f32) {
    let ramp = FADE_CYCLES * CYCLE_TICKS;
    if k < ramp {
        (k as f32 / ramp as f32, FADE_RATE)
    } else if k >= total - ramp {
        ((total - k) as f32 / ramp as f32, -FADE_RATE)
    } else {
        (1.0, 0.0)
    }
}

async fn run(bus: &mut Bus<'_>, out: &mut Out<'_>, cycles: u32) {
    if power::off_requested() {
        out.send("verdict: not run: the power button has turned the robot off")
            .await;
        return;
    }
    let mut motors: Vec<Motor, BUS_MOTORS> = Vec::new();
    for m in bus.shared.borrow().motors.iter() {
        if motors.push(m.clone()).is_err() {
            break;
        }
    }
    let found = bus.shared.borrow().motors.len();
    if found == 0 || found > BUS_MOTORS {
        say!(
            out,
            "verdict: not run: bus C carries {BUS_MOTORS} motors, and the last scan found {found}"
        );
        return;
    }

    {
        let mut s = bus.shared.borrow_mut();
        s.running = true;
        s.interrupted = false;
    }
    let peak = AMPLITUDE * sqrtf(OMEGA * OMEGA + FADE_RATE * FADE_RATE);
    say!(
        out,
        "run: {cycles} cycles of +/-45 deg at {FREQ_HZ:.0} Hz, {FADE_CYCLES} more each end to fade in and out; Kp {KP} Nm/rad, Kd {KD} Nm.s/rad, peak {peak:.1} rad/s. Any byte stops it."
    );

    let outcome = match prepare(bus, out, &mut motors, peak).await {
        Ok(centres) => Ok(motion(bus, out, &motors, &centres, cycles).await),
        Err(why) => Err(why),
    };

    bus.shared.borrow_mut().running = false;
    let all_off = disable_all(bus, out, &motors).await;

    let (stopped, records, ticks) = match outcome {
        Ok(outcome) => outcome,
        Err(why) => {
            say!(out, "verdict: not run: {why}");
            return;
        }
    };
    let mut verdict: Option<Why> = stopped.clone();
    for (m, r) in motors.iter().zip(records.iter()) {
        let replies = r.replies as f32 / ticks.saturating_sub(1).max(1) as f32;
        let mut faults = Why::new();
        if r.full_cycles < cycles {
            let _ = write!(faults, " ran {} of {cycles} full cycles;", r.full_cycles);
        }
        if r.full_cycles > 0
            && (r.amplitude_lo < AMPLITUDE * (1.0 - PASS_AMPLITUDE)
                || r.amplitude_hi > AMPLITUDE * (1.0 + PASS_AMPLITUDE))
        {
            let _ = write!(faults, " amplitude outside 45 deg +/-10 %;");
        }
        if r.worst / DEG >= PASS_ERROR_DEG {
            let _ = write!(faults, " strayed {PASS_ERROR_DEG} deg or more;");
        }
        if replies < PASS_REPLIES {
            let _ = write!(faults, " answered under {:.0} %;", PASS_REPLIES * 100.0);
        }
        let mut line: String<LINE> = String::new();
        let _ = write!(
            line,
            "result: motor {} {}: ",
            m.id,
            if faults.is_empty() { "PASS" } else { "FAIL" }
        );
        if r.full_cycles > 0 {
            let _ = write!(
                line,
                "amplitude {:.1} to {:.1} deg, lag {:.1} deg, ",
                r.amplitude_lo / DEG,
                r.amplitude_hi / DEG,
                r.lag_sum / r.full_cycles as f32
            );
        }
        let _ = write!(
            line,
            "error under {:.1} deg, torque under {:.2} Nm, {:.2} % answered, hottest {}/{} C",
            r.worst / DEG,
            r.torque,
            replies * 100.0,
            r.t_mos,
            r.t_rotor
        );
        if !faults.is_empty() {
            let _ = write!(line, ";{}", faults.trim_end_matches(';'));
        }
        out.send(&line).await;
        if verdict.is_none() && !faults.is_empty() {
            verdict = Some(why!("motor {}{}", m.id, faults.trim_end_matches(';')));
        }
    }
    if verdict.is_none() && motors.len() < BUS_MOTORS {
        verdict = Some(why!("only one motor answered on bus C"));
    }
    if verdict.is_none() && !all_off {
        verdict = Some(why!("a motor did not confirm it was disabled"));
    }
    match verdict {
        None => say!(
            out,
            "verdict: PASS: both motors on bus C followed +/-45 deg at {FREQ_HZ:.0} Hz for {cycles} cycles"
        ),
        Some(why) => say!(out, "verdict: FAIL: {why}"),
    }
}

/// Readies every motor for the run: out of any fault, in MIT mode, with room
/// to swing and speed to spare. Then enables each where it stands, and returns
/// where that is.
async fn prepare(
    bus: &mut Bus<'_>,
    out: &mut Out<'_>,
    motors: &mut [Motor],
    peak: f32,
) -> Result<Vec<f32, BUS_MOTORS>, Why> {
    for m in motors.iter_mut() {
        let Some(mut f) = bus.status(m.id).await else {
            return Err(why!("motor {} did not answer a status request", m.id));
        };
        if f.fault() {
            let was = state_name(f.state);
            bus.special(m, CLEAR_ERROR).await;
            f = bus.status(m.id).await.unwrap_or(f);
            if f.fault() {
                return Err(why!(
                    "motor {} reports {}, and would not clear",
                    m.id,
                    state_name(f.state)
                ));
            }
            say!(out, "run: motor {} reported {was}, and has cleared", m.id);
        }
        if m.mode != MIT {
            let was = m.mode_name();
            let echo = bus
                .request(m.id, REG_WRITE, CTRL_MODE, MIT.to_le_bytes())
                .await;
            if echo != Some(MIT.to_le_bytes()) {
                return Err(why!(
                    "motor {} would not change from {was} to MIT mode",
                    m.id
                ));
            }
            m.mode = MIT;
            if let Some(shared) = bus.shared.borrow_mut().motor_mut(m.id) {
                shared.mode = MIT;
            }
            say!(
                out,
                "run: motor {} changed from {was} to MIT mode, in RAM only",
                m.id
            );
        }
        if peak > SPEED_MARGIN * m.vmax {
            return Err(why!(
                "motor {}: VMAX {:.1} rad/s is too near the sine's {peak:.1}",
                m.id,
                m.vmax
            ));
        }
        if let Some(cap) = m.speed_cap
            && peak > SPEED_MARGIN * cap
        {
            return Err(why!(
                "motor {}: MAX_SPD holds it to {cap:.1} rad/s, too near the sine's {peak:.1}",
                m.id
            ));
        }
        if f.pos.abs() + AMPLITUDE > POSITION_MARGIN * m.pmax {
            return Err(why!(
                "motor {} is at {:.0} deg, too near the end of its +/-{:.0} to swing 45",
                m.id,
                f.pos / DEG,
                m.pmax / DEG
            ));
        }
    }

    let mut centres = Vec::new();
    for m in motors.iter() {
        // The bench GUI's start: a command to do nothing where the motor
        // stands, before the enable and after it, so that whatever command it
        // last held is never acted on.
        let Some(f) = bus.status(m.id).await else {
            return Err(why!("motor {} did not answer before it was enabled", m.id));
        };
        bus.mit(m, f.pos, 0.0, 0.0, 0.0, 0.0).await;
        bus.special(m, ENABLE).await;
        bus.mit(m, f.pos, 0.0, 0.0, 0.0, 0.0).await;
        match bus.status(m.id).await {
            Some(f) if f.state == ENABLED => {
                let _ = centres.push(f.pos);
                say!(out, "run: motor {} enabled at {:.1} deg", m.id, f.pos / DEG);
            }
            Some(f) => {
                return Err(why!(
                    "motor {} did not enable: it reports {}",
                    m.id,
                    state_name(f.state)
                ));
            }
            None => return Err(why!("motor {} did not answer after it was enabled", m.id)),
        }
    }
    Ok(centres)
}

/// The run itself. Returns why it stopped early, if it did, each motor's
/// record, and how many ticks it ran.
async fn motion(
    bus: &mut Bus<'_>,
    out: &mut Out<'_>,
    motors: &[Motor],
    centres: &[f32],
    cycles: u32,
) -> (Option<Why>, Vec<Record, BUS_MOTORS>, u32) {
    let n = motors.len();
    let total = (cycles + 2 * FADE_CYCLES) * CYCLE_TICKS;
    let mut records: Vec<Record, BUS_MOTORS> = Vec::new();
    let mut cycle = [Figures::default(); BUS_MOTORS];
    // The target each motor was last sent, and the phase it was sent at: the
    // feedback that answers it is where the motor was when it arrived.
    let mut sent: [Option<(f32, f32)>; BUS_MOTORS] = [None; BUS_MOTORS];
    let mut heard = [0u32; BUS_MOTORS];
    for (i, m) in motors.iter().enumerate() {
        let _ = records.push(Record::new());
        heard[i] = bus.shared.borrow().motor(m.id).map_or(0, |m| m.heard);
    }

    let mut ticker = Ticker::every(Duration::from_hz(TICK_HZ as u64));
    let mut k = 0;
    let stopped = 'run: loop {
        if k == total {
            break None;
        }
        ticker.next().await;
        if bus.shared.borrow().interrupted {
            break Some(why!("stopped from the Pi"));
        }
        if power::off_requested() {
            break Some(why!("stopped by the power button"));
        }
        let now = Instant::now();
        let theta = 2.0 * PI * (k % CYCLE_TICKS) as f32 / CYCLE_TICKS as f32;
        let (share, rate) = fade(k, total);

        for (i, m) in motors.iter().enumerate() {
            let (f, count) = {
                let s = bus.shared.borrow();
                let latest = s.motor(m.id);
                (
                    latest.and_then(|m| m.feedback),
                    latest.map_or(0, |m| m.heard),
                )
            };
            let Some(f) = f else {
                break 'run Some(why!("motor {} has never reported", m.id));
            };
            if f.fault() {
                break 'run Some(why!("motor {} reports {}", m.id, state_name(f.state)));
            }
            if f.state == DISABLED {
                break 'run Some(why!("motor {} disabled itself", m.id));
            }
            // Saturating, because feedback heard since `now` was read, while
            // an earlier motor's command went out, is later than it.
            if now.saturating_duration_since(f.at) > SILENT {
                break 'run Some(why!(
                    "motor {} was silent for {} ms",
                    m.id,
                    SILENT.as_millis()
                ));
            }
            if count != heard[i] {
                heard[i] = count;
                records[i].replies += 1;
                if let Some((target, phase)) = sent[i] {
                    let error = f.pos - target;
                    if error.abs() > ABORT_ERROR_DEG * DEG {
                        break 'run Some(why!(
                            "motor {} was {:.0} deg from its target",
                            m.id,
                            error / DEG
                        ));
                    }
                    cycle[i].add(f.pos - centres[i], phase, error, &f);
                }
            }

            let target = centres[i] + AMPLITUDE * share * sinf(theta);
            let speed = AMPLITUDE * (rate * sinf(theta) + share * OMEGA * cosf(theta));
            // The bench GUI's rule: neither the spring nor the damper can
            // push harder than REACH_NM, however far the target runs ahead.
            let p = target.clamp(f.pos - REACH_NM / KP, f.pos + REACH_NM / KP);
            let v = speed.clamp(f.vel - REACH_NM / KD, f.vel + REACH_NM / KD);
            if !bus.mit(m, p, v, KP, KD, 0.0).await {
                break 'run Some(why!(
                    "bus C took no frame for {} ms",
                    SEND_TIMEOUT.as_millis()
                ));
            }
            sent[i] = Some((target, theta));
        }
        k += 1;

        if k % CYCLE_TICKS == 0 {
            let c = k / CYCLE_TICKS;
            let full = c > FADE_CYCLES && c <= FADE_CYCLES + cycles;
            let mut line: String<LINE> = String::new();
            let _ = write!(line, "cycle {c} of {}:", cycles + 2 * FADE_CYCLES);
            for i in 0..n {
                let (amplitude, lag) = cycle[i].fundamental();
                let _ = write!(
                    line,
                    "{} m{} {:.1} deg, lag {:.1}, error {:.1}, {:.2} Nm, {}/{} C",
                    if i == 0 { "" } else { " |" },
                    motors[i].id,
                    amplitude / DEG,
                    lag,
                    cycle[i].worst / DEG,
                    cycle[i].torque,
                    cycle[i].t_mos,
                    cycle[i].t_rotor
                );
                records[i].add(&cycle[i], full);
                cycle[i] = Figures::default();
            }
            if !full {
                let _ = write!(line, " (fading)");
            }
            out.send(&line).await;
        }
    };
    (stopped, records, k)
}

/// Disables every motor, three times over, and says whether each confirms it.
async fn disable_all(bus: &mut Bus<'_>, out: &mut Out<'_>, motors: &[Motor]) -> bool {
    for _ in 0..3 {
        for m in motors {
            bus.special(m, DISABLE).await;
        }
        Timer::after_millis(2).await;
    }
    let mut all = true;
    for m in motors {
        match bus.status(m.id).await {
            Some(f) if f.state == DISABLED => say!(out, "run: motor {} disabled", m.id),
            Some(f) => {
                all = false;
                say!(
                    out,
                    "run: motor {} still reports {} after disabling",
                    m.id,
                    state_name(f.state)
                );
            }
            None => {
                all = false;
                say!(out, "run: motor {} did not answer after disabling", m.id);
            }
        }
    }
    all
}
