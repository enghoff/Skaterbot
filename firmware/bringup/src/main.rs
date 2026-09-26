//! Bring-up test for the WeAct STM32G474 core board.
//!
//! Flashes the blue LED in a heartbeat and appears over USB as a serial port
//! that echoes whatever it is sent. Each time a host opens the port it prints a
//! banner with the chip's unique ID and its uptime, and while the port is open
//! it reports presses of the KEY button. One terminal session therefore
//! exercises the clock tree, the USB peripheral, a GPIO output and an EXTI
//! input, and two banners a known time apart check the crystal: if it were not
//! the 8 MHz the clock tree assumes, the uptime would drift against the host's.
//!
//! Opening the port at 1200 baud reboots the board into ST's USB bootloader, as
//! Arduino boards do, so `flash.ps1` can reflash it without anyone holding
//! BOOT0. The button still works whatever this firmware does, because the
//! option bytes that give it that job are left alone.

#![no_std]
#![no_main]

use core::fmt::Write;
use core::mem::MaybeUninit;

use embassy_executor::Spawner;
use embassy_futures::join::join3;
use embassy_futures::select::{Either3, select3};
use embassy_stm32::exti::{self, ExtiInput};
use embassy_stm32::gpio::{Level, Output, Pull, Speed};
use embassy_stm32::mode::Async;
use embassy_stm32::time::Hertz;
use embassy_stm32::usb::{self, Driver};
use embassy_stm32::{Config, bind_interrupts, interrupt, pac, peripherals, uid};
use embassy_time::{Instant, Timer};
use embassy_usb::Builder;
use embassy_usb::class::cdc_acm::{self, CdcAcmClass, ControlChanged, State};
use embassy_usb::driver::EndpointError;
use panic_halt as _;

bind_interrupts!(struct Irqs {
    USB_LP => usb::InterruptHandler<peripherals::USB>;
    EXTI15_10 => exti::InterruptHandler<interrupt::typelevel::EXTI15_10>;
});

/// Full-speed bulk endpoints carry at most 64 bytes per packet.
const MAX_PACKET: usize = 64;

type Sender<'d> = cdc_acm::Sender<'d, Driver<'d, peripherals::USB>>;
type Receiver<'d> = cdc_acm::Receiver<'d, Driver<'d, peripherals::USB>>;

/// The baud rate that asks for the bootloader rather than setting a speed,
/// which a USB serial port does not have anyway.
const BOOTLOADER_BAUD: u32 = 1200;
/// ST's bootloader, in the G474's system memory, starts with its vector table.
const SYSTEM_MEMORY: u32 = 0x1FFF_0000;
/// Left in RAM across a reset to ask for the bootloader. Anything else,
/// including whatever RAM holds at power-up, means start normally.
const BOOTLOADER_REQUEST: u32 = 0xB007_10AD;

/// In a section the runtime neither zeroes nor initialises, so it survives the
/// reset that `reboot_if_requested` performs.
#[unsafe(link_section = ".uninit.BOOT_REQUEST")]
static mut BOOT_REQUEST: MaybeUninit<u32> = MaybeUninit::uninit();

#[embassy_executor::main]
async fn main(_spawner: Spawner) {
    restart_if_started_by_bootloader();
    enter_bootloader_if_requested();

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
    let p = embassy_stm32::init(config);

    // Blue LED D1, from PC6 through 5.1 k to ground: high is on.
    let mut led = Output::new(p.PC6, Level::Low, Speed::Low);
    // KEY switches PC13 to 3.3 V through 330 R and has no pull of its own.
    let mut key = ExtiInput::new(p.PC13, p.EXTI13, Pull::Down, Irqs);

    let driver = Driver::new(p.USB, Irqs, p.PA12, p.PA11);

    // 1209:0001 is pid.codes' ID for private testing, not a claimed product.
    let mut usb_config = embassy_usb::Config::new(0x1209, 0x0001);
    usb_config.manufacturer = Some("Bipedal");
    usb_config.product = Some("G474 bring-up");
    usb_config.serial_number = Some(uid::uid_hex());

    let mut config_descriptor = [0; 256];
    let mut bos_descriptor = [0; 256];
    let mut control_buf = [0; 64];
    let mut state = State::new();

    let mut builder = Builder::new(
        driver,
        usb_config,
        &mut config_descriptor,
        &mut bos_descriptor,
        &mut [],
        &mut control_buf,
    );
    let (mut tx, mut rx, control) =
        CdcAcmClass::new(&mut builder, &mut state, MAX_PACKET as u16).split_with_control();
    let mut usb = builder.build();

    // A heartbeat, two short flashes a second, because WeAct's factory firmware
    // blinks this LED steadily and a plain blink would not show which is running.
    let blink = async {
        loop {
            for _ in 0..2 {
                led.set_high();
                Timer::after_millis(100).await;
                led.set_low();
                Timer::after_millis(150).await;
            }
            Timer::after_millis(500).await;
        }
    };

    // The USB link being up says only that the host has configured the device.
    // A program opening the port is what raises DTR, and closing it drops DTR,
    // so that is what bounds a session.
    let sessions = async {
        loop {
            tx.wait_connection().await;
            while !control.dtr() {
                control.control_changed().await;
                reboot_if_requested(&tx).await;
            }
            let _ = session(&mut tx, &mut rx, &control, &mut key).await;
        }
    };

    join3(usb.run(), blink, sessions).await;
}

/// Reboots into the bootloader if the host has set the port to
/// `BOOTLOADER_BAUD`, and returns if it has not.
async fn reboot_if_requested(tx: &Sender<'_>) {
    if tx.line_coding().data_rate() == BOOTLOADER_BAUD {
        // Let the host's request finish before the board drops off the bus.
        Timer::after_millis(50).await;
        unsafe {
            (&raw mut BOOT_REQUEST)
                .cast::<u32>()
                .write_volatile(BOOTLOADER_REQUEST)
        };
        cortex_m::peripheral::SCB::sys_reset();
    }
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

/// Jumps to ST's bootloader if the last reset asked for it. This runs before
/// any clock or peripheral is set up, which is the state the bootloader expects
/// to start from, as it would after a reset with BOOT0 held.
fn enter_bootloader_if_requested() {
    unsafe {
        let request = (&raw mut BOOT_REQUEST).cast::<u32>();
        if request.read_volatile() != BOOTLOADER_REQUEST {
            return;
        }
        request.write_volatile(0);
        // Map system memory at address 0, where the bootloader expects to be.
        pac::RCC.apb2enr().modify(|w| w.set_syscfgen(true));
        pac::SYSCFG.memrmp().modify(|w| w.set_mem_mode(0b001));
        cortex_m::asm::bootload(SYSTEM_MEMORY as *const u32);
    }
}

struct Disconnected;

impl From<EndpointError> for Disconnected {
    fn from(_: EndpointError) -> Self {
        Disconnected
    }
}

/// One opening of the port: the banner, then echo and key reports until the
/// host closes it.
async fn session(
    tx: &mut Sender<'_>,
    rx: &mut Receiver<'_>,
    control: &ControlChanged<'_>,
    key: &mut ExtiInput<'_, Async>,
) -> Result<(), Disconnected> {
    reboot_if_requested(tx).await;
    // Windows empties a port's buffers as it finishes opening it, just after
    // raising DTR, and would throw away a banner sent at once.
    Timer::after_millis(100).await;

    let mut banner: heapless::String<128> = heapless::String::new();
    let _ = write!(
        banner,
        "Bipedal bring-up, STM32G474 at 170 MHz, uid {}, up {} ms\r\n",
        uid::uid_hex(),
        Instant::now().as_millis()
    );
    send(tx, banner.as_bytes()).await?;

    let mut buf = [0; MAX_PACKET];
    loop {
        match select3(
            rx.read_packet(&mut buf),
            key.wait_for_rising_edge(),
            control.control_changed(),
        )
        .await
        {
            Either3::First(n) => send(tx, &buf[..n?]).await?,
            Either3::Second(()) => send(tx, b"KEY pressed\r\n").await?,
            Either3::Third(()) => {
                reboot_if_requested(tx).await;
                if !control.dtr() {
                    return Ok(());
                }
            }
        }
    }
}

/// Writes `data` as whole packets, ending with a short one so the host hands
/// it over at once rather than waiting for more.
async fn send(tx: &mut Sender<'_>, data: &[u8]) -> Result<(), Disconnected> {
    for chunk in data.chunks(MAX_PACKET) {
        tx.write_packet(chunk).await?;
    }
    if data.len() % MAX_PACKET == 0 {
        tx.write_packet(&[]).await?;
    }
    Ok(())
}
