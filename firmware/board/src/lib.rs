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
//! On the robot it also holds the power on and turns it off: [`early_init`]
//! raises the power switch board's HOLD as soon as it knows this image is to
//! run, and starts [`power`]'s watch on the robot's button, which lets go of
//! HOLD after a half-second press, or waits for Linux shutdown when the image
//! opts into graceful power-off (with timed and long-press forced-off fallbacks).
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
/// otherwise raises HOLD, starts watching the power button, and takes any
/// crash record out of the backup registers for [`last_crash`].
///
/// HOLD goes up only once this image is certain to run, because ST's
/// bootloader reads no button: a robot held on in it could not be turned off.
/// Entered after a crash, the robot turns off instead. The checks before it
/// are a few register reads, so the press that turns the robot on is no longer.
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
    power::hold_early();
    power::watch();
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
// Power

mod power_button;

pub mod power {
    //! The power switch board's hold and its button, on the carrier's J7.
    //!
    //! The button closes the switch directly while it is pressed. The board
    //! then keeps it closed only while a hold is present -- this MCU's on PC11,
    //! or the SBC's -- and opens it about 0.9 s after the last one goes, or when
    //! the pack falls below its cutoff (docs/POWER_SWITCH.md). So a press has
    //! to last until this firmware raises HOLD, which [`super::early_init`]
    //! does as soon as it has ruled out the bootloader, and the button can then
    //! be let go.
    //!
    //! Turning off belongs to this crate rather than to the image, so that
    //! every image turns off the same way whatever else it does or fails to do.
    //! [`super::early_init`] starts SysTick, and every [`TICK_MS`] its handler
    //! reads the button on PB14, which the power board's D7 pulls low against
    //! the MCU's pull-up. Normally a half-second press drops HOLD immediately.
    //! An image that calls [`wait_for_sbc_shutdown`] instead latches a shutdown
    //! request while keeping HOLD high. The Pi's final shutdown hook then resets
    //! the MCU to release HOLD after Linux is safe. An eight-second button hold,
    //! or twenty seconds without completing shutdown, releases HOLD regardless
    //! of the image or Pi's state. The pressed button itself keeps power on until
    //! released. The image must stop motors when [`off_requested`] becomes true.
    //!
    //! A press counts as let go only once the button has read up for
    //! [`RELEASE_MS`], so a contact that chatters does not start the count
    //! again. The press that turned the robot on is still held when the
    //! firmware starts, and is not one: nothing counts until the button has
    //! been seen up.
    //!
    //! PC11, PB14 and SysTick are this module's, and no image may take them.
    //! With no power board on J7, SENSE reads high and nothing happens, and
    //! HOLD drives an open pin.

    use core::cell::RefCell;
    use core::sync::atomic::{AtomicBool, Ordering};

    use cortex_m::interrupt::{Mutex, free};
    use cortex_m::peripheral::{SCB, SYST};
    use embassy_stm32::pac;
    use embassy_stm32::pac::gpio::vals::{Idr, Moder, Pupdr};
    use embassy_stm32::pac::rcc::vals::Sw;

    use crate::power_button::Button;
    pub use crate::power_button::{
        FORCE_OFF_MS, OFF_PRESS_MS, RELEASE_MS, SHUTDOWN_GRACE_MS, TICK_MS,
    };

    /// HOLD, PC11, J7-1.
    const HOLD_PIN: usize = 11;
    /// SENSE, PB14, J7-2.
    const SENSE_PIN: usize = 14;

    /// SysTick's control bits: the core clock, its interrupt, and the counter.
    const SYST_CORE_CLOCK_TICKINT_ENABLE: u32 = 0b111;
    /// SysTick's priority byte in SHPR3. The lowest, so that it never delays
    /// an image's own interrupts.
    const SYSTICK_SHPR: usize = 11;

    static OFF: AtomicBool = AtomicBool::new(false);
    static GRACEFUL: AtomicBool = AtomicBool::new(false);
    static BUTTON: Mutex<RefCell<Button>> = Mutex::new(RefCell::new(Button::Starting { up_ms: 0 }));

    /// Raises HOLD from the reset state, before clocks or embassy: the button
    /// has to be held until this runs, so it runs as early as it can. embassy's
    /// start-up turns the GPIO clocks on and leaves the ports alone, so HOLD
    /// stays raised.
    pub(crate) fn hold_early() {
        pac::RCC.ahb2enr().modify(|w| w.set_gpiocen(true));
        let port = pac::GPIOC;
        port.bsrr().write(|w| w.set_bs(HOLD_PIN, true));
        port.moder()
            .modify(|w| w.set_moder(HOLD_PIN, Moder::OUTPUT));
    }

    /// Makes SENSE an input against the MCU's pull-up and starts SysTick.
    /// Only once the bootloader is ruled out, since it expects SysTick off.
    pub(crate) fn watch() {
        pac::RCC.ahb2enr().modify(|w| w.set_gpioben(true));
        let port = pac::GPIOB;
        port.pupdr()
            .modify(|w| w.set_pupdr(SENSE_PIN, Pupdr::PULL_UP));
        port.moder()
            .modify(|w| w.set_moder(SENSE_PIN, Moder::INPUT));
        // Through the registers rather than cortex_m::Peripherals, which an
        // image may take for itself.
        unsafe {
            (*SCB::PTR).shpr[SYSTICK_SHPR].write(0xFF);
            let syst = &*SYST::PTR;
            syst.rvr.write(reload());
            syst.cvr.write(0);
            syst.csr.write(SYST_CORE_CLOCK_TICKINT_ENABLE);
        }
    }

    /// SysTick's reload for one [`TICK_MS`] at the clock the core is on now:
    /// the reset's 16 MHz HSI until embassy sets the clocks up, and
    /// [`super::SYSCLK_HZ`] from the PLL after. The tick that spans the change
    /// is the wrong length, which does not matter.
    fn reload() -> u32 {
        let hz = match pac::RCC.cfgr().read().sws() {
            Sw::PLL1_R => super::SYSCLK_HZ,
            Sw::HSE => 8_000_000,
            _ => 16_000_000,
        };
        hz / 1000 * TICK_MS - 1
    }

    /// One tick of the watch, from SysTick.
    pub(crate) fn tick() {
        unsafe { (*SYST::PTR).rvr.write(reload()) };
        let pressed = pressed();
        let action = free(|cs| {
            let mut button = BUTTON.borrow(cs).borrow_mut();
            let (next, action) = button.step(pressed, GRACEFUL.load(Ordering::Relaxed));
            *button = next;
            action
        });
        if action.request_off {
            OFF.store(true, Ordering::Relaxed);
        }
        if action.cut_power {
            pac::GPIOC.bsrr().write(|w| w.set_br(HOLD_PIN, true));
        }
    }

    /// Keep HOLD high while the Pi shuts down. Call once, just after early_init.
    /// The independent SysTick still enforces the forced-off fallbacks.
    pub fn wait_for_sbc_shutdown() {
        GRACEFUL.store(true, Ordering::Relaxed);
    }

    /// The Pi has accepted orderly shutdown. Start the same grace period as
    /// the button, without extending a shutdown already requested by the button.
    pub fn request_shutdown() {
        free(|cs| {
            if !OFF.swap(true, Ordering::Relaxed) {
                *BUTTON.borrow(cs).borrow_mut() = Button::Waiting {
                    elapsed_ms: 0,
                    held_ms: 0,
                    up_ms: RELEASE_MS,
                };
            }
        });
    }

    /// Whether HOLD is high at the pin, read back rather than remembered.
    pub fn held() -> bool {
        pac::GPIOC.idr().read().idr(HOLD_PIN) == Idr::HIGH
    }

    /// Whether the button is down this moment, as read, without the debounce.
    pub fn pressed() -> bool {
        pac::GPIOB.idr().read().idr(SENSE_PIN) == Idr::LOW
    }

    /// Whether a half-second press requested shutdown. This remains latched
    /// through the grace period, even after the button is released.
    pub fn off_requested() -> bool {
        OFF.load(Ordering::Relaxed)
    }
}

// --------------------------------------------------------------------------
// Heartbeat

/// [`heartbeat`]'s period and flash, for an image that beats it itself
/// (the diag image, which shows faults on the same LED).
pub const HEARTBEAT_PERIOD_MS: u64 = 300 + 6720 / 7;
pub const HEARTBEAT_FLASH_MS: u64 = 70;

/// The Banana Pi's heartbeat, on an LED of this board: two 70 ms flashes, the
/// second a quarter of a period after the first, then dark to the end of it.
///
/// It is Linux's own heartbeat trigger (drivers/leds/trigger/ledtrig-heartbeat.c),
/// which the Pi's red status LED runs. The kernel stretches the period with the
/// one-minute load average -- 300 + 6720 / (5 x load + 7) ms, so 1260 ms idle,
/// 860 at a load of 1, 510 at 5 -- and this board has no load average, so it
/// beats at the idle period, as the Pi does with nothing to do. Two boards that
/// both beat are two boards both running.
/// A latched shutdown request cancels the pattern and leaves this LED dark;
/// the executor and its safety watchdog continue running.
pub async fn heartbeat(led: &mut embassy_stm32::gpio::Output<'_>) -> ! {
    const PERIOD_MS: u64 = HEARTBEAT_PERIOD_MS;
    const FLASH_MS: u64 = HEARTBEAT_FLASH_MS;
    let beat = async {
        loop {
            led.set_high();
            Timer::after_millis(FLASH_MS).await;
            led.set_low();
            Timer::after_millis(PERIOD_MS / 4 - FLASH_MS).await;
            led.set_high();
            Timer::after_millis(FLASH_MS).await;
            led.set_low();
            Timer::after_millis(PERIOD_MS - PERIOD_MS / 4 - FLASH_MS).await;
        }
    };
    let shutting_down = async {
        while !power::off_requested() {
            Timer::after_millis(10).await;
        }
    };
    select(beat, shutting_down).await;
    led.set_low();
    core::future::pending::<()>().await;
    unreachable!()
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

/// The power button's watch, every [`power::TICK_MS`].
#[exception]
fn SysTick() {
    power::tick();
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
