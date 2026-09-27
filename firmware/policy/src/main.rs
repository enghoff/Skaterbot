//! The trained policy, run on the WeAct STM32G474 board for a host to check.
//!
//! The network is a run's exported ONNX, normaliser and all, with its weights
//! in flash: `net/`, which `export.py` writes. A host sends an observation over
//! USB and gets back the network's raw outputs and the cycles the board took
//! over them, which is what `hil.py` needs to drive the simulated robot with
//! the board and hold each answer against onnxruntime's. Building the
//! observation and using the actions stay with the host, as
//! docs/POLICY_INTERFACE.md sets out: this is the network alone.
//!
//! Requests, and their replies, all little-endian. Every reply is the request's
//! letter, a u16 length, and that many bytes.
//!
//! ```text
//! 'I'                    what the board holds, and why it last reset, as text
//! 'P' obs: f32 x N_OBS   actions: f32 x N_ACT, cycles: u32
//! 'B' count: u16         count: u32, fewest and most cycles: u32 x 2,
//!                        cycles in all: u64, microseconds in all: u64
//! 'C' kind: u8           crash, after replying: 0 panic, 1 hard fault,
//!                        2 hang, 3 unhandled interrupt
//! 'Z'                    reboot into the bootloader, after replying
//! ```
//!
//! 'B' runs the network `count` times on the last observation 'P' sent, timing
//! each run by the core's cycle counter and the whole by the system timer, so
//! the one checks the other. 'C' is for proving that every way this firmware
//! can die leaves the board in its bootloader.

#![no_std]
#![no_main]

use core::fmt::Write;
use core::hint::black_box;
use core::sync::atomic::{Ordering, compiler_fence};

use board::MAX_PACKET;
use cortex_m::peripheral::DWT;
use embassy_executor::Spawner;
use embassy_futures::join::join4;
use embassy_futures::select::{Either, select};
use embassy_stm32::gpio::{Level, Output, Speed};
use embassy_stm32::usb::{self, Driver};
use embassy_stm32::{bind_interrupts, peripherals};
use embassy_time::{Instant, Timer};
use embassy_usb::Builder;
use embassy_usb::class::cdc_acm::{self, CdcAcmClass, ControlChanged, State};
use embassy_usb::driver::EndpointError;

use net::{N_ACT, N_OBS};

bind_interrupts!(struct Irqs {
    USB_LP => usb::InterruptHandler<peripherals::USB>;
});

type Sender<'d> = cdc_acm::Sender<'d, Driver<'d, peripherals::USB>>;
type Receiver<'d> = cdc_acm::Receiver<'d, Driver<'d, peripherals::USB>>;

/// The longest request, an observation after its letter.
const MAX_REQUEST: usize = 1 + 4 * N_OBS;
/// The longest reply's payload, the text 'I' sends.
const MAX_REPLY: usize = 512;
/// The most runs one 'B' may ask for, well inside the watchdog's time.
const MAX_BENCH: u16 = 5000;

#[embassy_executor::main]
async fn main(_spawner: Spawner) {
    board::early_init();
    let p = embassy_stm32::init(board::config());

    // The core's cycle counter, which runs without a debugger once trace is on.
    let mut core = unsafe { cortex_m::Peripherals::steal() };
    core.DCB.enable_trace();
    core.DWT.enable_cycle_counter();

    // Blue LED D1, from PC6 through 5.1 k to ground: high is on.
    let mut led = Output::new(p.PC6, Level::Low, Speed::Low);

    let driver = Driver::new(p.USB, Irqs, p.PA12, p.PA11);
    let mut config_descriptor = [0; 256];
    let mut bos_descriptor = [0; 256];
    let mut control_buf = [0; 64];
    let mut state = State::new();
    let mut builder = Builder::new(
        driver,
        board::usb_config("G474 policy"),
        &mut config_descriptor,
        &mut bos_descriptor,
        &mut [],
        &mut control_buf,
    );
    let (mut tx, mut rx, control) =
        CdcAcmClass::new(&mut builder, &mut state, MAX_PACKET as u16).split_with_control();
    let mut usb = builder.build();

    // Three short flashes a second, where the bring-up firmware gives two, so
    // the board shows which it is running.
    let blink = async {
        loop {
            for _ in 0..3 {
                led.set_high();
                Timer::after_millis(80).await;
                led.set_low();
                Timer::after_millis(120).await;
            }
            Timer::after_millis(400).await;
        }
    };

    // A program opening the port raises DTR and closing it drops DTR, so that
    // is what bounds a session.
    let sessions = async {
        board::usb_deadline(tx.wait_connection()).await;
        let mut last_obs = [0.0f32; N_OBS];
        loop {
            tx.wait_connection().await;
            while !control.dtr() {
                control.control_changed().await;
                board::reboot_if_requested(&tx).await;
            }
            let _ = session(&mut tx, &mut rx, &control, &mut last_obs).await;
        }
    };

    join4(usb.run(), blink, sessions, board::watchdog(p.IWDG)).await;
}

struct Disconnected;

impl From<EndpointError> for Disconnected {
    fn from(_: EndpointError) -> Self {
        Disconnected
    }
}

/// One opening of the port: requests answered until the host closes it.
async fn session(
    tx: &mut Sender<'_>,
    rx: &mut Receiver<'_>,
    control: &ControlChanged<'_>,
    last_obs: &mut [f32; N_OBS],
) -> Result<(), Disconnected> {
    board::reboot_if_requested(tx).await;
    // A request can span packets, and a packet can end one and start another.
    let mut inbox = [0u8; MAX_REQUEST + MAX_PACKET];
    let mut held = 0;
    let mut packet = [0u8; MAX_PACKET];
    loop {
        match select(rx.read_packet(&mut packet), control.control_changed()).await {
            Either::First(n) => {
                let n = n?;
                inbox[held..held + n].copy_from_slice(&packet[..n]);
                held += n;
                while held > 0 {
                    let Some(len) = request_len(inbox[0]) else {
                        // Out of step with the host: say so, and start afresh.
                        reply(tx, b'E', b"unknown request").await?;
                        held = 0;
                        break;
                    };
                    if held < len {
                        break;
                    }
                    handle(&inbox[..len], tx, last_obs).await?;
                    inbox.copy_within(len..held, 0);
                    held -= len;
                }
            }
            Either::Second(()) => {
                board::reboot_if_requested(tx).await;
                if !control.dtr() {
                    return Ok(());
                }
            }
        }
    }
}

fn request_len(letter: u8) -> Option<usize> {
    match letter {
        b'I' | b'Z' => Some(1),
        b'P' => Some(MAX_REQUEST),
        b'B' => Some(3),
        b'C' => Some(2),
        _ => None,
    }
}

async fn handle(
    request: &[u8],
    tx: &mut Sender<'_>,
    last_obs: &mut [f32; N_OBS],
) -> Result<(), Disconnected> {
    let letter = request[0];
    let body = &request[1..];
    match letter {
        b'I' => {
            let mut text: heapless::String<MAX_REPLY> = heapless::String::new();
            let _ = describe(&mut text);
            reply(tx, letter, text.as_bytes()).await
        }
        b'P' => {
            for (x, bytes) in last_obs.iter_mut().zip(body.as_chunks::<4>().0) {
                *x = f32::from_le_bytes(*bytes);
            }
            let mut actions = [0.0f32; N_ACT];
            let cycles = timed(|| net::run(last_obs, &mut actions));
            let mut out = [0u8; 4 * N_ACT + 4];
            for (bytes, a) in out.as_chunks_mut::<4>().0.iter_mut().zip(actions) {
                *bytes = a.to_le_bytes();
            }
            out[4 * N_ACT..].copy_from_slice(&cycles.to_le_bytes());
            reply(tx, letter, &out).await
        }
        b'B' => {
            let count = u16::from_le_bytes([body[0], body[1]]).clamp(1, MAX_BENCH);
            let (mut fewest, mut most, mut all) = (u32::MAX, 0u32, 0u64);
            let mut actions = [0.0f32; N_ACT];
            let start = Instant::now();
            for _ in 0..count {
                // Hidden from the compiler, or it would run the network once
                // and hand back the same answer every time.
                let obs = black_box(&*last_obs);
                let cycles = timed(|| net::run(obs, &mut actions));
                black_box(&actions);
                fewest = fewest.min(cycles);
                most = most.max(cycles);
                all += u64::from(cycles);
            }
            let micros = start.elapsed().as_micros();
            let mut out = [0u8; 28];
            out[0..4].copy_from_slice(&u32::from(count).to_le_bytes());
            out[4..8].copy_from_slice(&fewest.to_le_bytes());
            out[8..12].copy_from_slice(&most.to_le_bytes());
            out[12..20].copy_from_slice(&all.to_le_bytes());
            out[20..28].copy_from_slice(&micros.to_le_bytes());
            reply(tx, letter, &out).await
        }
        b'C' => {
            reply(tx, letter, &[]).await?;
            Timer::after_millis(50).await;
            crash(body[0])
        }
        b'Z' => {
            reply(tx, letter, &[]).await?;
            Timer::after_millis(50).await;
            board::reboot_to_bootloader()
        }
        _ => unreachable!("request_len admits no other letter"),
    }
}

/// What the board holds, one `key=value` a line.
fn describe(out: &mut impl Write) -> core::fmt::Result {
    writeln!(out, "firmware=policy")?;
    writeln!(out, "run={}", net::RUN)?;
    writeln!(out, "digest={}", net::DIGEST)?;
    writeln!(out, "obs={}", N_OBS)?;
    writeln!(out, "act={}", N_ACT)?;
    write!(out, "layers=")?;
    for (i, (n_in, n_out)) in net::LAYERS.iter().enumerate() {
        write!(out, "{}{}x{}", if i == 0 { "" } else { "," }, n_in, n_out)?;
    }
    writeln!(out)?;
    writeln!(out, "sysclk_hz={}", board::SYSCLK_HZ)?;
    write!(out, "reset=")?;
    board::reset_cause(out)?;
    writeln!(out)?;
    write!(out, "last_crash=")?;
    board::last_crash(out)?;
    writeln!(out)
}

/// Runs `f`, and returns the core cycles it took. The fences keep the compiler
/// from moving the work outside the two reads of the counter.
fn timed(f: impl FnOnce()) -> u32 {
    compiler_fence(Ordering::SeqCst);
    let start = DWT::cycle_count();
    compiler_fence(Ordering::SeqCst);
    f();
    compiler_fence(Ordering::SeqCst);
    let end = DWT::cycle_count();
    compiler_fence(Ordering::SeqCst);
    end.wrapping_sub(start)
}

async fn reply(tx: &mut Sender<'_>, letter: u8, payload: &[u8]) -> Result<(), Disconnected> {
    let mut out = [0u8; 3 + MAX_REPLY];
    let n = payload.len().min(MAX_REPLY);
    out[0] = letter;
    out[1..3].copy_from_slice(&(n as u16).to_le_bytes());
    out[3..3 + n].copy_from_slice(&payload[..n]);
    Ok(board::send(tx, &out[..3 + n]).await?)
}

/// Dies the way `kind` names, for the host to see the board come back in its
/// bootloader.
fn crash(kind: u8) -> ! {
    match kind {
        0 => panic!("crash test, as asked"),
        1 => cortex_m::asm::udf(),
        2 => loop {
            core::hint::spin_loop();
        },
        _ => {
            // FMAC has no driver here, so nothing binds its interrupt.
            let irq = embassy_stm32::pac::Interrupt::FMAC;
            unsafe { cortex_m::peripheral::NVIC::unmask(irq) };
            cortex_m::peripheral::NVIC::pend(irq);
            loop {
                core::hint::spin_loop();
            }
        }
    }
}

mod net {
    //! The network, as `export.py` wrote it into `net/`.

    include!(concat!(env!("CARGO_MANIFEST_DIR"), "/net/net.rs"));

    const _: () = assert!(PARAM_COUNT * 4 == core::mem::size_of::<Params>());

    fn params() -> &'static [f32] {
        // Params is aligned for f32 and holds PARAM_COUNT of them.
        unsafe { core::slice::from_raw_parts(PARAMS.0.as_ptr().cast(), PARAM_COUNT) }
    }

    /// The policy's raw outputs, before any clipping, for one observation.
    pub fn run(obs: &[f32; N_OBS], out: &mut [f32; N_ACT]) {
        let (offset, rest) = params().split_at(N_OBS);
        let (divisor, mut rest) = rest.split_at(N_OBS);
        let mut a = [0.0f32; WIDEST];
        let mut b = [0.0f32; WIDEST];
        for i in 0..N_OBS {
            a[i] = (obs[i] - offset[i]) / divisor[i];
        }
        let (mut x, mut y) = (&mut a, &mut b);
        for (k, &(n_in, n_out)) in LAYERS.iter().enumerate() {
            let (weights, r) = rest.split_at(n_in * n_out);
            let (biases, r) = r.split_at(n_out);
            rest = r;
            dense(&x[..n_in], weights, biases, &mut y[..n_out]);
            if k + 1 < LAYERS.len() {
                for v in &mut y[..n_out] {
                    *v = elu(*v);
                }
            }
            core::mem::swap(&mut x, &mut y);
        }
        out.copy_from_slice(&x[..N_ACT]);
    }

    /// y = W x + b, W stored one output's row at a time.
    ///
    /// Arranged around the loads, which on the M4 cost as much as the
    /// arithmetic: a single-float load takes two cycles, where a multiply and
    /// an add take one each. So four rows go together and each input is loaded
    /// once for all four, 1.25 loads a multiply-add rather than 2, which took
    /// a run from 3.40 ms to 2.57. Each row still sums in plain order, one
    /// product after the next, and the bias last.
    ///
    /// What is left is mostly those loads: the compiler will not merge four
    /// neighbouring floats into the one load instruction the M4 has for them,
    /// and about a quarter of a run is waiting on flash, which is the only
    /// place 193 KB of weights fit.
    fn dense(x: &[f32], weights: &[f32], biases: &[f32], y: &mut [f32]) {
        let n = x.len();
        let (x4, x_rest) = x.as_chunks::<4>();
        let mut rows = weights.chunks_exact(n);
        let (y4, y_rest) = y.as_chunks_mut::<4>();
        let (b4, b_rest) = biases.as_chunks::<4>();
        for (y, b) in y4.iter_mut().zip(b4) {
            let (r0, r1, r2, r3) = (
                rows.next().unwrap(),
                rows.next().unwrap(),
                rows.next().unwrap(),
                rows.next().unwrap(),
            );
            let (mut s0, mut s1, mut s2, mut s3) = (0.0f32, 0.0f32, 0.0f32, 0.0f32);
            let chunks = x4
                .iter()
                .zip(r0.as_chunks::<4>().0)
                .zip(r1.as_chunks::<4>().0)
                .zip(r2.as_chunks::<4>().0)
                .zip(r3.as_chunks::<4>().0);
            for ((((&[x0, x1, x2, x3], w0), w1), w2), w3) in chunks {
                s0 += w0[0] * x0;
                s1 += w1[0] * x0;
                s2 += w2[0] * x0;
                s3 += w3[0] * x0;
                s0 += w0[1] * x1;
                s1 += w1[1] * x1;
                s2 += w2[1] * x1;
                s3 += w3[1] * x1;
                s0 += w0[2] * x2;
                s1 += w1[2] * x2;
                s2 += w2[2] * x2;
                s3 += w3[2] * x2;
                s0 += w0[3] * x3;
                s1 += w1[3] * x3;
                s2 += w2[3] * x3;
                s3 += w3[3] * x3;
            }
            let tail = n - x_rest.len();
            for (j, &xj) in x_rest.iter().enumerate() {
                s0 += r0[tail + j] * xj;
                s1 += r1[tail + j] * xj;
                s2 += r2[tail + j] * xj;
                s3 += r3[tail + j] * xj;
            }
            y[0] = b[0] + s0;
            y[1] = b[1] + s1;
            y[2] = b[2] + s2;
            y[3] = b[3] + s3;
        }
        // A layer whose width is not a multiple of four ends a row at a time.
        for ((y, b), row) in y_rest.iter_mut().zip(b_rest).zip(rows) {
            let mut sum = 0.0f32;
            for (w, xj) in row.iter().zip(x) {
                sum += w * xj;
            }
            *y = b + sum;
        }
    }

    /// In 32 bits throughout: the core's FPU does single precision only, and a
    /// 64-bit exp would run in software.
    fn elu(v: f32) -> f32 {
        if v > 0.0 {
            v
        } else {
            ELU_ALPHA * (libm::expf(v) - 1.0)
        }
    }
}
