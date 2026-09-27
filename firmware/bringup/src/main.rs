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
//! BOOT0; a crash or a hang goes there too. All of that is the `board` crate's.

#![no_std]
#![no_main]

use core::fmt::Write;

use board::{MAX_PACKET, send};
use embassy_executor::Spawner;
use embassy_futures::join::join4;
use embassy_futures::select::{Either3, select3};
use embassy_stm32::exti::{self, ExtiInput};
use embassy_stm32::gpio::{Level, Output, Pull, Speed};
use embassy_stm32::mode::Async;
use embassy_stm32::usb::{self, Driver};
use embassy_stm32::{bind_interrupts, interrupt, peripherals, uid};
use embassy_time::{Instant, Timer};
use embassy_usb::Builder;
use embassy_usb::class::cdc_acm::{self, CdcAcmClass, ControlChanged, State};
use embassy_usb::driver::EndpointError;

bind_interrupts!(struct Irqs {
    USB_LP => usb::InterruptHandler<peripherals::USB>;
    EXTI15_10 => exti::InterruptHandler<interrupt::typelevel::EXTI15_10>;
});

type Sender<'d> = cdc_acm::Sender<'d, Driver<'d, peripherals::USB>>;
type Receiver<'d> = cdc_acm::Receiver<'d, Driver<'d, peripherals::USB>>;

#[embassy_executor::main]
async fn main(_spawner: Spawner) {
    board::early_init();
    let p = embassy_stm32::init(board::config());

    // Blue LED D1, from PC6 through 5.1 k to ground: high is on.
    let mut led = Output::new(p.PC6, Level::Low, Speed::Low);
    // KEY switches PC13 to 3.3 V through 330 R and has no pull of its own.
    let mut key = ExtiInput::new(p.PC13, p.EXTI13, Pull::Down, Irqs);

    let driver = Driver::new(p.USB, Irqs, p.PA12, p.PA11);

    let usb_config = board::usb_config("G474 bring-up");

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
        board::usb_deadline(tx.wait_connection()).await;
        loop {
            tx.wait_connection().await;
            while !control.dtr() {
                control.control_changed().await;
                board::reboot_if_requested(&tx).await;
            }
            let _ = session(&mut tx, &mut rx, &control, &mut key).await;
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

/// One opening of the port: the banner, then echo and key reports until the
/// host closes it.
async fn session(
    tx: &mut Sender<'_>,
    rx: &mut Receiver<'_>,
    control: &ControlChanged<'_>,
    key: &mut ExtiInput<'_, Async>,
) -> Result<(), Disconnected> {
    board::reboot_if_requested(tx).await;
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
                board::reboot_if_requested(tx).await;
                if !control.dtr() {
                    return Ok(());
                }
            }
        }
    }
}
