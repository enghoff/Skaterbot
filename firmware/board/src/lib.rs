//! What every firmware image for the WeAct STM32G474 board carries: its clocks,
//! its USB identity, and the ways back into ST's USB bootloader.
//!
//! The bootloader is the only way this board is programmed -- there is no debug
//! probe on it -- so an image that cannot get back there can only be recovered
//! by hand, holding BOOT0 and tapping NRST. Every image built on this crate gets
//! there by itself:
//!
//! * when asked, by the host opening its serial port at 1200 baud
//!   ([`reboot_if_requested`]), as Arduino boards do;
//! * on a panic, a hard fault, or an interrupt nothing handles;
//! * after a hang: [`watchdog`] feeds the independent watchdog, which resets the
//!   chip if the executor stops running it, and [`early_init`] takes a start
//!   after a watchdog reset into the bootloader;
//! * if USB has not come up within [`USB_DEADLINE_S`] of starting
//!   ([`usb_deadline`]).
//!
//! A crash also leaves a record in the backup registers, which a system reset
//! does not clear, and the next ordinary start takes it out for the firmware to
//! report ([`last_crash`]).
//!
//! The button still works whatever an image does, because the option bytes that
//! give it that job are left alone.

#![no_std]

use core::fmt::{self, Write};
use core::future::Future;
use core::mem::MaybeUninit;
use core::sync::atomic::{AtomicU32, Ordering};

use cortex_m_rt::{ExceptionFrame, exception};
use embassy_futures::select::{Either, select};
use embassy_stm32::time::Hertz;
use embassy_stm32::wdg::IndependentWatchdog;
use embassy_stm32::{Config, Peri, pac, peripherals, uid};
use embassy_time::Timer;
use embassy_usb::class::cdc_acm::Sender;
use embassy_usb::driver::{Driver, EndpointError};

/// Full-speed bulk endpoints carry at most 64 bytes per packet.
pub const MAX_PACKET: usize = 64;

/// The baud rate that asks for the bootloader rather than setting a speed,
/// which a USB serial port does not have anyway.
pub const BOOTLOADER_BAUD: u32 = 1200;
/// ST's bootloader, in the G474's system memory, starts with its vector table.
const SYSTEM_MEMORY: u32 = 0x1FFF_0000;
/// Left in RAM across a reset to ask for the bootloader. Anything else,
/// including whatever RAM holds at power-up, means start normally.
const BOOTLOADER_REQUEST: u32 = 0xB007_10AD;

/// How long the executor may stop running before the watchdog resets the chip.
/// Long, because the one thing it must never do is reset the bootloader in the
/// middle of a flash: a software reset stops the watchdog, and ST's bootloader
/// feeds it anyway, but neither is something this firmware can see for itself.
pub const WATCHDOG_S: u32 = 30;

/// How long after starting USB has to be configured by a host before the
/// firmware gives up and enters the bootloader. Only for the bench: on the
/// robot, with no host, this would always fire.
pub const USB_DEADLINE_S: u64 = 10;

/// In a section the runtime neither zeroes nor initialises, so it survives the
/// reset that [`reboot_to_bootloader`] performs.
#[unsafe(link_section = ".uninit.BOOT_REQUEST")]
static mut BOOT_REQUEST: MaybeUninit<u32> = MaybeUninit::uninit();

/// The reset flags as this start found them, before clearing them.
static RESET_FLAGS: AtomicU32 = AtomicU32::new(0);

/// The clocks: 170 MHz from the crystal, and USB's 48 MHz from its own
/// oscillator.
pub fn config() -> Config {
    let mut config = Config::default();
    {
        use embassy_stm32::rcc::*;
        // The board's 8 MHz crystal, X2 on WeAct's schematic.
        config.rcc.hse = Some(Hse {
            freq: Hertz(8_000_000),
            mode: HseMode::Oscillator,
        });
        // 8 MHz / 2 x 85 / 2 = 170 MHz, the part's maximum, which needs boost mode.
        config.rcc.pll = Some(Pll {
            source: PllSource::HSE,
            prediv: PllPreDiv::DIV2,
            mul: PllMul::MUL85,
            divp: None,
            divq: None,
            divr: Some(PllRDiv::DIV2),
        });
        config.rcc.sys = Sysclk::PLL1_R;
        config.rcc.boost = true;
        // USB takes its 48 MHz from the internal RC oscillator, trimmed against
        // the host's start-of-frame packets, so it does not depend on the crystal.
        config.rcc.hsi48 = Some(Hsi48Config {
            sync_from_usb: true,
        });
        config.rcc.mux.clk48sel = mux::Clk48sel::HSI48;
    }
    config
}

/// The system clock [`config`] sets, for turning cycles into time.
pub const SYSCLK_HZ: u32 = 170_000_000;

/// The board's USB identity, with `product` naming the image, which is how a
/// host tells one firmware from another.
pub fn usb_config(product: &'static str) -> embassy_usb::Config<'static> {
    // 1209:0001 is pid.codes' ID for private testing, not a claimed product.
    let mut config = embassy_usb::Config::new(0x1209, 0x0001);
    config.manufacturer = Some("Bipedal");
    config.product = Some(product);
    config.serial_number = Some(uid::uid_hex());
    config
}

// --------------------------------------------------------------------------
// Starting

/// The first thing `main` calls, before `embassy_stm32::init` and before any
/// clock or peripheral is set up.
///
/// Resets the chip if the bootloader started this firmware; enters the
/// bootloader if the last reset asked for it or was the watchdog's; and
/// otherwise takes any crash record out of the backup registers for
/// [`last_crash`].
pub fn early_init() {
    restart_if_started_by_bootloader();

    // The flags accumulate across resets until cleared, and the bootloader
    // leaves them standing, so they are cleared on every start and describe
    // only the reset that led to this one.
    let flags = pac::RCC.csr().read();
    pac::RCC.csr().modify(|w| w.set_rmvf(true));
    if flags.iwdgrstf() {
        crash::record(crash::Cause::Watchdog, [0; 3], &[]);
        enter_bootloader();
    }
    if take_bootloader_request() {
        enter_bootloader();
    }
    RESET_FLAGS.store(flags.0, Ordering::Relaxed);
    crash::take();
}

/// Resets the chip if ST's bootloader started this firmware.
///
/// After flashing, the bootloader starts the firmware by jumping to it, not by
/// resetting, which leaves the chip as the bootloader had it: its clocks, its
/// USB peripheral running, and system memory mapped at address 0. Started that
/// way the firmware comes up but often fails to enumerate, where after a reset
/// it never has, so this makes every start a reset. Neither the USB clock nor the
/// system-memory mapping is on after a reset with BOOT0 low. Reset flags cannot
/// tell the two apart, since the bootloader leaves standing whatever flag the
/// reset that started it set.
fn restart_if_started_by_bootloader() {
    pac::RCC.apb2enr().modify(|w| w.set_syscfgen(true));
    let remapped = pac::SYSCFG.memrmp().read().mem_mode() != 0;
    let usb_on = pac::RCC.apb1enr1().read().usben();
    if remapped || usb_on {
        cortex_m::peripheral::SCB::sys_reset();
    }
}

/// Whether the last reset asked for the bootloader, clearing the request.
fn take_bootloader_request() -> bool {
    unsafe {
        let request = (&raw mut BOOT_REQUEST).cast::<u32>();
        let asked = request.read_volatile() == BOOTLOADER_REQUEST;
        request.write_volatile(0);
        asked
    }
}

/// Jumps to ST's bootloader. Only from [`early_init`]: this runs before any
/// clock or peripheral is set up, which is the state the bootloader expects to
/// start from, as it would after a reset with BOOT0 held.
fn enter_bootloader() -> ! {
    // Map system memory at address 0, where the bootloader expects to be.
    pac::RCC.apb2enr().modify(|w| w.set_syscfgen(true));
    pac::SYSCFG.memrmp().modify(|w| w.set_mem_mode(0b001));
    unsafe { cortex_m::asm::bootload(SYSTEM_MEMORY as *const u32) }
}

/// Resets into ST's bootloader, from anywhere: the reset puts the chip back in
/// the state the bootloader needs, and [`early_init`] makes the jump.
pub fn reboot_to_bootloader() -> ! {
    unsafe {
        (&raw mut BOOT_REQUEST)
            .cast::<u32>()
            .write_volatile(BOOTLOADER_REQUEST)
    };
    cortex_m::peripheral::SCB::sys_reset();
}

/// What reset the chip before this start, as the reset flags named it: a
/// power-on also sets the pin's flag, and every reset but a power-on sets it.
pub fn reset_cause(out: &mut impl Write) -> fmt::Result {
    let flags = pac::rcc::regs::Csr(RESET_FLAGS.load(Ordering::Relaxed));
    let named = [
        (flags.borrstf(), "power-on"),
        (flags.pinrstf(), "pin"),
        (flags.sftrstf(), "software"),
        (flags.iwdgrstf(), "watchdog"),
        (flags.wwdgrstf(), "window watchdog"),
        (flags.lpwrrstf(), "low power"),
        (flags.oblrstf(), "option bytes"),
    ];
    let mut first = true;
    for (_, name) in named.iter().filter(|(set, _)| *set) {
        out.write_str(if first { "" } else { ", " })?;
        out.write_str(name)?;
        first = false;
    }
    if first {
        out.write_str("none")?;
    }
    Ok(())
}

// --------------------------------------------------------------------------
// Running

/// Starts the independent watchdog and feeds it, forever. Join it with the
/// firmware's other futures: if the executor stops polling it -- a task
/// spinning, an interrupt storm, a deadlock -- the watchdog resets the chip
/// within [`WATCHDOG_S`], and the next start goes into the bootloader.
pub async fn watchdog(iwdg: Peri<'_, peripherals::IWDG>) -> ! {
    let mut dog = IndependentWatchdog::new(iwdg, WATCHDOG_S * 1_000_000);
    dog.unleash();
    loop {
        dog.pet();
        Timer::after_millis(500).await;
    }
}

/// Enters the bootloader unless `configured` finishes within
/// [`USB_DEADLINE_S`]: pass it the serial port's `wait_connection()`.
pub async fn usb_deadline(configured: impl Future<Output = ()>) {
    let deadline = Timer::after_secs(USB_DEADLINE_S);
    if let Either::Second(()) = select(configured, deadline).await {
        reboot_to_bootloader();
    }
}

/// Reboots into the bootloader if the host has set the port to
/// [`BOOTLOADER_BAUD`], and returns if it has not. Call it whenever the port's
/// control lines change.
pub async fn reboot_if_requested<'d, D: Driver<'d>>(tx: &Sender<'d, D>) {
    if tx.line_coding().data_rate() == BOOTLOADER_BAUD {
        // Let the host's request finish before the board drops off the bus.
        Timer::after_millis(50).await;
        reboot_to_bootloader();
    }
}

/// Writes `data` as whole packets, ending with a short one so the host hands
/// it over at once rather than waiting for more.
pub async fn send<'d, D: Driver<'d>>(
    tx: &mut Sender<'d, D>,
    data: &[u8],
) -> Result<(), EndpointError> {
    for chunk in data.chunks(MAX_PACKET) {
        tx.write_packet(chunk).await?;
    }
    if data.len().is_multiple_of(MAX_PACKET) {
        tx.write_packet(&[]).await?;
    }
    Ok(())
}

// --------------------------------------------------------------------------
// Crashing

#[panic_handler]
fn panic(info: &core::panic::PanicInfo) -> ! {
    cortex_m::interrupt::disable();
    let mut text = crash::Text::new();
    if let Some(at) = info.location() {
        // The file's name alone: a dependency's full path would leave no room
        // for the message.
        let file = at.file().rsplit(['/', '\\']).next().unwrap_or("");
        let _ = write!(text, "{}:{}: ", file, at.line());
    }
    let _ = write!(text, "{}", info.message());
    crash::record(crash::Cause::Panic, [0; 3], text.as_bytes());
    reboot_to_bootloader();
}

#[exception]
unsafe fn HardFault(frame: &ExceptionFrame) -> ! {
    // The configurable fault status says which fault it was, escalated: bus,
    // memory management or usage. A bus or memory fault may also leave the
    // address it faulted on, and the status says whether it did.
    let scb = unsafe { &*cortex_m::peripheral::SCB::PTR };
    let cfsr = scb.cfsr.read();
    let address = if cfsr & crash::BFARVALID != 0 {
        scb.bfar.read()
    } else if cfsr & crash::MMARVALID != 0 {
        scb.mmfar.read()
    } else {
        0
    };
    crash::record(crash::Cause::HardFault, [frame.pc(), cfsr, address], &[]);
    reboot_to_bootloader();
}

#[exception]
unsafe fn DefaultHandler(irqn: i16) {
    crash::record(crash::Cause::Interrupt, [irqn as u32, 0, 0], &[]);
    reboot_to_bootloader();
}

/// Describes the crash that ended the last run, if the last run crashed, or
/// writes nothing.
pub fn last_crash(out: &mut impl Write) -> fmt::Result {
    crash::describe(out)
}

mod crash {
    //! A crash, recorded in the TAMP backup registers: 32 words that only a
    //! backup-domain reset or a tamper event clears, so a system reset, the
    //! bootloader and a reflash all leave them as they were.

    use super::*;

    const MAGIC: u32 = 0xC4A5_0000;
    /// The fault status bits that say the bus or memory fault address holds
    /// the address the fault was on.
    pub const BFARVALID: u32 = 1 << 15;
    pub const MMARVALID: u32 = 1 << 7;
    const WORDS: usize = 32;
    /// Word 0 is the magic and the cause, 1-3 the cause's own numbers, and the
    /// rest text.
    const TEXT_BYTES: usize = (WORDS - 4) * 4;

    #[derive(Clone, Copy)]
    pub enum Cause {
        Panic = 1,
        HardFault = 2,
        Interrupt = 3,
        Watchdog = 4,
    }

    /// The record the last start took out, for [`describe`].
    static LAST: [AtomicU32; WORDS] = [const { AtomicU32::new(0) }; WORDS];

    fn writable() {
        // Peripheral writes with their clock off are ignored rather than
        // faulting, so this is safe from a fault handler whatever state the
        // firmware left the clocks in.
        pac::RCC.apb1enr1().modify(|w| {
            w.set_pwren(true);
            w.set_rtcapben(true);
        });
        pac::PWR.cr1().modify(|w| w.set_dbp(true));
    }

    pub fn record(cause: Cause, numbers: [u32; 3], text: &[u8]) {
        writable();
        let tamp = pac::TAMP;
        for (i, n) in numbers.iter().enumerate() {
            tamp.bkpr(1 + i).write(|w| w.set_bkp(*n));
        }
        let mut padded = [0u8; TEXT_BYTES];
        let n = text.len().min(TEXT_BYTES);
        padded[..n].copy_from_slice(&text[..n]);
        for (i, word) in padded.as_chunks::<4>().0.iter().enumerate() {
            let word = u32::from_le_bytes(*word);
            tamp.bkpr(4 + i).write(|w| w.set_bkp(word));
        }
        // The magic last, so a record cut short is not taken for a whole one.
        tamp.bkpr(0).write(|w| w.set_bkp(MAGIC | cause as u32));
    }

    pub fn take() {
        writable();
        let tamp = pac::TAMP;
        if tamp.bkpr(0).read().bkp() & 0xFFFF_0000 != MAGIC {
            return;
        }
        for (i, last) in LAST.iter().enumerate() {
            last.store(tamp.bkpr(i).read().bkp(), Ordering::Relaxed);
        }
        tamp.bkpr(0).write(|w| w.set_bkp(0));
    }

    pub fn describe(out: &mut impl Write) -> fmt::Result {
        let word = |i: usize| LAST[i].load(Ordering::Relaxed);
        if word(0) & 0xFFFF_0000 != MAGIC {
            return Ok(());
        }
        match word(0) & 0xFF {
            1 => {
                out.write_str("panic: ")?;
                let mut text = [0u8; TEXT_BYTES];
                for (i, chunk) in text.as_chunks_mut::<4>().0.iter_mut().enumerate() {
                    *chunk = word(4 + i).to_le_bytes();
                }
                let end = text.iter().position(|&b| b == 0).unwrap_or(TEXT_BYTES);
                for &b in &text[..end] {
                    out.write_char(if b.is_ascii_graphic() || b == b' ' {
                        b as char
                    } else {
                        '?'
                    })?;
                }
                Ok(())
            }
            2 => {
                write!(
                    out,
                    "hard fault at pc {:#010x}, CFSR {:#010x}",
                    word(1),
                    word(2)
                )?;
                if word(2) & (BFARVALID | MMARVALID) != 0 {
                    write!(out, ", at address {:#010x}", word(3))?;
                }
                Ok(())
            }
            3 => write!(out, "unhandled interrupt {}", word(1) as i16),
            4 => write!(out, "watchdog: the firmware stopped running"),
            other => write!(out, "unknown cause {other}"),
        }
    }

    /// A panic's text, cut to what the record holds.
    pub struct Text {
        bytes: [u8; TEXT_BYTES],
        len: usize,
    }

    impl Text {
        pub fn new() -> Self {
            Self {
                bytes: [0; TEXT_BYTES],
                len: 0,
            }
        }

        pub fn as_bytes(&self) -> &[u8] {
            &self.bytes[..self.len]
        }
    }

    impl Write for Text {
        fn write_str(&mut self, s: &str) -> fmt::Result {
            let n = s.len().min(TEXT_BYTES - self.len);
            self.bytes[self.len..self.len + n].copy_from_slice(&s.as_bytes()[..n]);
            self.len += n;
            Ok(())
        }
    }
}
