//! A check of the serial link between the controller and the Banana Pi, and of
//! flashing over it: the first image written to the board through the carrier's
//! J5 rather than its USB port.
//!
//! USART1 on PA9/PA10 at 115 200 8N1 -- the pins the carrier takes to J5, and
//! the port ST's ROM bootloader listens on, which is how `sbc/flash_mcu.py`
//! wrote this image. Twice a second it sends one line,
//!
//! ```text
//! serial_check 7: up 3.5 s, reset by pin, hold on, button up
//! ```
//!
//! and beats the blue LED as the Banana Pi beats its red one
//! ([`board::heartbeat`]); every byte it receives it sends straight back.
//! The count shows no line was lost, the reset cause shows the Pi's NRST did the
//! reset, and the echo shows the Pi-to-board direction works as well.
//!
//! It also holds the power switch board on, as every image does, and reports
//! HOLD as read back at the pin and the button on J7. Held for two seconds, the
//! button asks for the robot to turn off: this says so on a line of its own and
//! lets go of HOLD. On the bench, with no power board, shorting J7-2 to J7-3 is
//! the button.
//!
//! No USB and no watchdog, so none of the `board` crate's ways back into the
//! bootloader that need them: the way back is the Pi, holding BOOT0 and pulsing
//! NRST, which is the thing being checked.

#![no_std]
#![no_main]

use core::fmt::Write;

use board::power::Power;
use embassy_executor::Spawner;
use embassy_futures::join::join;
use embassy_futures::yield_now;
use embassy_stm32::gpio::{Level, Output, Speed};
use embassy_stm32::mode::Blocking;
use embassy_stm32::usart::{Config, Uart};
use embassy_time::{Duration, Instant};
use embedded_hal_nb::serial::Read;
use heapless::String;

/// The rate the Pi's end is opened at, and the fastest ST's bootloader takes,
/// so one setting serves both.
const BAUD: u32 = 115_200;
/// How often a line is sent.
const PERIOD: Duration = Duration::from_millis(500);

#[embassy_executor::main]
async fn main(_spawner: Spawner) {
    board::early_init();
    let p = embassy_stm32::init(board::config());

    // Blue LED D1, from PC6 through 5.1 k to ground: high is on.
    let mut led = Output::new(p.PC6, Level::Low, Speed::Low);
    let mut power = Power::new(p.PC11, p.PB14);

    let mut config = Config::default();
    config.baudrate = BAUD;
    let mut uart = Uart::new_blocking(p.USART1, p.PA10, p.PA9, config).unwrap();

    join(board::heartbeat(&mut led), serve(&mut uart, &mut power)).await;
}

/// Echoes, reports twice a second, and acts on an off request. Never returns.
async fn serve(uart: &mut Uart<'_, Blocking>, power: &mut Power<'_>) {
    let start = Instant::now();
    let mut next = start;
    let mut count: u32 = 0;
    loop {
        // Echo. Polled rather than waited for, so a line goes out on time
        // whether or not anything is arriving; at 170 MHz the loop comes round
        // far faster than one byte takes at 115 200 baud.
        while let Ok(byte) = uart.read() {
            let _ = uart.blocking_write(&[byte]);
        }

        if power.update() {
            let _ = uart.blocking_write(b"power: off requested, releasing HOLD\r\n");
            power.release();
        }

        if Instant::now() >= next {
            next += PERIOD;
            count += 1;
            let up = start.elapsed().as_millis();
            let mut line: String<128> = String::new();
            let _ = write!(
                line,
                "serial_check {}: up {}.{} s, reset by ",
                count,
                up / 1000,
                up % 1000 / 100
            );
            let _ = board::reset_cause(&mut line);
            let _ = write!(
                line,
                ", hold {}, button {}\r\n",
                if power.held() { "on" } else { "off" },
                if power.pressed() { "down" } else { "up" }
            );
            let _ = uart.blocking_write(line.as_bytes());
        }
        yield_now().await;
    }
}
