# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Read the INA226 bus monitor straight off the Banana Pi's header, and say whether it works.

    sudo python3 ina226_test.py                  read the Pi's 5 V rail for 10 s, then judge it
    sudo python3 ina226_test.py --expect 5.08    judge it against a meter reading instead
    sudo python3 ina226_test.py --seconds 0      stream until Ctrl-C

This is the bench test from before the carrier exists. On the robot the monitor
hangs off the STM32's I2C on the carrier and its VBS pin reads the battery bus;
here it is wired to the Banana Pi's 40-pin header with female jumpers onto its
own 1 x 8 header, and VBS reads the Pi's own 5 V:

    module VCC -> header pin 1 (3.3 V)      module SDA -> header pin 3
    module GND -> header pin 6              module SCL -> header pin 5
    module VBS -> header pin 4 (5 V)        ALE, IN- and IN+ left unconnected

VCC is 3.3 V, never 5 V: the module pulls SDA and SCL up to its own VCC, and the
Pi's pins are not 5 V tolerant. VBS is the measured input and takes anything up
to 36 V whatever VCC is. The shunt inputs are left open because the robot uses
this part as a voltmeter only (docs/CARRIER.md), so nothing here judges them.
Pins 3 and 5 are TWI0, which Armbian only switches on with the
`bananapi-m4-pi-5-6-i2c0` overlay in /boot/armbianEnv.txt.

It checks what a working part must show: an answer between 0x40 and 0x4F, TI's
manufacturer ID and the INA226's die ID, the configuration register's documented
value after a reset, conversions arriving at the rate they were set for, and the
bus voltage. Without --expect the bus is held to USB's own 4.75-5.25 V, which
proves the scale but not much more; with a meter's reading it is held to 1 %. A
noisy reading is only a warning, because that is the rail and not the part.

Only the standard library: registers are 16 bits, big-endian, written as a
pointer byte and read back as two. Numbers are from TI's datasheet, SBOS547.
"""

from __future__ import annotations

import argparse
import fcntl
import glob
import math
import os
import struct
import sys
import time

I2C_SLAVE = 0x0703
TWI0 = "5002000.i2c"  # the controller on header pins 3 and 5
ADDRESSES = range(0x40, 0x50)  # A0 and A1 each to GND, VS, SDA or SCL; 0x40 as sold

CONFIG, BUS, MASK = 0x00, 0x02, 0x06
MANUFACTURER, DIE = 0xFE, 0xFF
TI, INA226 = 0x5449, 0x226  # "TI", and the top 12 bits of the die ID
CONFIG_DEFAULT = 0x4127  # what CONFIG reads after a reset
RESET = 0x8000
CVRF = 0x0008  # conversion ready, in MASK; reading MASK clears it
BUS_LSB = 1.25e-3  # V

# 16-sample averaging and 1.1 ms for each of shunt and bus, both continuously: a
# fresh pair every 16 x 2.2 ms. The datasheet holds its conversion times to 10 %.
AVERAGES = 16
CONVERSION = 1.1e-3
RUN = 0x4000 | (2 << 9) | (4 << 6) | (4 << 3) | 0b111
PERIOD = AVERAGES * 2 * CONVERSION


class Monitor:
    """One INA226 on /dev/i2c-<bus>."""

    def __init__(self, bus: int, address: int):
        self.fd = os.open(f"/dev/i2c-{bus}", os.O_RDWR)
        fcntl.ioctl(self.fd, I2C_SLAVE, address)

    def read(self, register: int) -> int:
        os.write(self.fd, bytes([register]))
        return struct.unpack(">H", os.read(self.fd, 2))[0]

    def write(self, register: int, value: int) -> None:
        os.write(self.fd, struct.pack(">BH", register, value))

    def close(self) -> None:
        os.close(self.fd)


def header_bus() -> int | None:
    """The /dev/i2c number Linux gave TWI0, if the overlay has switched it on."""
    for path in glob.glob("/sys/bus/i2c/devices/i2c-*"):
        if TWI0 in os.path.realpath(path):
            return int(path.rsplit("-", 1)[1])
    return None


def open_monitor(bus: int | None, address: int | None) -> tuple[Monitor, int, int, int]:
    bus = header_bus() if bus is None else bus
    if bus is None:
        sys.exit(
            "Header I2C is off. Add bananapi-m4-pi-5-6-i2c0 to the overlays= "
            "line of /boot/armbianEnv.txt and reboot, or pass --bus."
        )
    strangers = []
    for addr in (address,) if address else ADDRESSES:
        try:
            monitor = Monitor(bus, addr)
        except PermissionError:
            sys.exit(f"No permission on /dev/i2c-{bus}: run with sudo.")
        try:
            maker, die = monitor.read(MANUFACTURER), monitor.read(DIE)
        except OSError:
            monitor.close()
            continue
        if maker == TI and die >> 4 == INA226:
            return monitor, bus, addr, die
        strangers.append(f"{addr:#04x}")
        monitor.close()
    if strangers:
        sys.exit(
            f"Something answers at {', '.join(strangers)} on /dev/i2c-{bus}, "
            "but not with an INA226's IDs."
        )
    sys.exit(
        f"Nothing answers between 0x40 and 0x4F on /dev/i2c-{bus}. Check 3V3 on "
        "pin 1, SDA on pin 3, SCL on pin 5, GND on pin 6, and that SDA and SCL "
        "are not swapped."
    )


def judge(
    after_reset: int, volts: list[float], elapsed: float, expect: float | None
) -> bool:
    print(f"\n--- {elapsed:.1f} s of readings")
    ok = True

    def check(passed: bool, text: str, fails: bool = True) -> None:
        nonlocal ok
        ok &= passed or not fails
        print(f"  {'PASS' if passed else 'FAIL' if fails else 'WARN'}  {text}")

    check(
        after_reset == CONFIG_DEFAULT,
        f"config   {after_reset:#06x} after a reset, {CONFIG_DEFAULT:#06x} documented",
    )
    want = 1 / PERIOD
    got = len(volts) / elapsed
    check(
        0.8 * want <= got <= 1.2 * want,
        f"rate     {got:5.1f} conversions/s of {want:.1f}",
    )
    if not volts:
        return False

    mean = sum(volts) / len(volts)
    noise = math.sqrt(sum((v - mean) ** 2 for v in volts) / len(volts))
    if expect is None:
        check(4.75 <= mean <= 5.25, f"bus      {mean:.3f} V, USB allows 4.75-5.25 V")
    else:
        # The part's own gain and offset errors are 0.1 % and 7.5 mV; the rest is
        # the meter's, and the rail moving between the meter and this.
        tolerance = 0.01 * expect + 0.010
        check(
            abs(mean - expect) <= tolerance,
            f"bus      {mean:.3f} V against {expect:.3f} V on the meter, within {tolerance * 1000:.0f} mV",
        )
    if mean < 0.1:
        print("  VBS reads nothing: check it is on header pin 4.")
    # A warning only: this is the Pi's rail moving under its own load.
    check(noise < 0.020, f"noise    {noise * 1000:.1f} mV rms", False)
    print("  RESULT:", "the bus monitor works" if ok else "something is wrong")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bus", type=int, help="/dev/i2c number (default: find TWI0)")
    ap.add_argument("--address", type=lambda s: int(s, 0), help="0x40 to 0x4F")
    ap.add_argument("--expect", type=float, help="a meter's reading on VBS, volts")
    ap.add_argument("--seconds", type=float, default=10, help="0 streams until Ctrl-C")
    args = ap.parse_args()

    monitor, bus, addr, die = open_monitor(args.bus, args.address)
    print(f"INA226 answers at {addr:#04x} on /dev/i2c-{bus}, die revision {die & 0xF}")

    monitor.write(CONFIG, RESET)  # so every run starts from the datasheet's defaults
    time.sleep(0.01)
    after_reset = monitor.read(CONFIG)
    monitor.write(CONFIG, RUN)
    monitor.read(MASK)  # clear a conversion-ready flag left over from before

    volts: list[float] = []
    start = shown = heard = time.monotonic()
    tty = sys.stdout.isatty()
    try:
        while not args.seconds or time.monotonic() - start < args.seconds:
            if not monitor.read(MASK) & CVRF:
                if time.monotonic() - heard > 1:
                    print(
                        "\nNo conversion for 1 s: the monitor has stopped converting."
                    )
                    break
                time.sleep(0.002)
                continue
            heard = time.monotonic()
            volts.append(monitor.read(BUS) * BUS_LSB)
            if heard - shown > 0.1:
                shown = heard
                line = f"t {heard - start:5.1f}  bus {volts[-1]:6.3f} V"
                print(line, end="\r" if tty else "\n", flush=True)
    except KeyboardInterrupt:
        pass
    except OSError as error:
        print(f"\nThe monitor stopped answering: {error}")
    elapsed = time.monotonic() - start
    try:
        monitor.write(CONFIG, RUN & ~0b111)  # power-down: leave it quiet
    except OSError:
        pass
    monitor.close()
    sys.exit(0 if judge(after_reset, volts, elapsed, args.expect) else 1)


if __name__ == "__main__":
    main()
