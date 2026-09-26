# /// script
# requires-python = ">=3.11"
# dependencies = ["pyserial>=3.5"]
# ///
"""Check the bring-up firmware from the host: its banner, its echo, and its clock.

    uv run firmware/bringup/test_serial.py           # finds the board by USB ID
    uv run firmware/bringup/test_serial.py COM8      # or name the port
    uv run firmware/bringup/test_serial.py --key     # also wait for a KEY press

The board prints a banner carrying its uptime each time the port is opened. Two
banners a known time apart compare the board's clock with the host's, and the
board's clock is the 8 MHz crystal multiplied up, so a wrong crystal frequency or
PLL setting shows up as a ratio far from 1. Echo is checked with packets on
either side of the 64-byte USB packet size, since a transfer of exactly one
packet is the case that stalls if the firmware forgets to end it.
"""

import argparse
import re
import sys
import time

import serial
from serial.tools import list_ports

VID, PID = 0x1209, 0x0001
BANNER = re.compile(rb"Bipedal bring-up, .* uid ([0-9a-f]{24}), up (\d+) ms\r\n")
GAP_S = 10.0


def find_port() -> str:
    for port in list_ports.comports():
        if (port.vid, port.pid) == (VID, PID):
            return port.device
    sys.exit(f"no board with USB ID {VID:04x}:{PID:04x}; is the firmware running?")


def banner(device: str) -> tuple[serial.Serial, str, int, float]:
    """Open the port, and return it with the banner's uid and uptime."""
    port = serial.Serial(device, timeout=2)
    opened = time.monotonic()
    line = port.readline()
    match = BANNER.fullmatch(line)
    if not match:
        sys.exit(f"unexpected banner: {line!r}")
    return port, match[1].decode(), int(match[2]), opened


def echo(port: serial.Serial, size: int) -> None:
    sent = bytes((i % 94) + 33 for i in range(size))
    port.write(sent)
    got = port.read(size)
    if got != sent:
        sys.exit(f"echo of {size} bytes came back as {len(got)}: {got[:40]!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "port", nargs="?", help="serial port; found by USB ID if omitted"
    )
    parser.add_argument("--key", action="store_true", help="wait for a KEY press")
    args = parser.parse_args()
    device = args.port or find_port()

    port, uid, up1, t1 = banner(device)
    print(f"{device}: uid {uid}, up {up1} ms")
    for size in (1, 5, 63, 64, 65, 200):
        echo(port, size)
    print("echo: 1, 5, 63, 64, 65 and 200 bytes all came back intact")

    if args.key:
        print("press KEY on the board...")
        port.timeout = 120
        line = port.readline()
        if line != b"KEY pressed\r\n":
            sys.exit(f"no key report within 120 s: {line!r}")
        print("KEY: reported")
    port.close()

    time.sleep(GAP_S)
    port, _, up2, t2 = banner(device)
    port.close()
    ratio = (up2 - up1) / 1000 / (t2 - t1)
    print(
        f"clock: board counted {(up2 - up1) / 1000:.3f} s while the host counted "
        f"{t2 - t1:.3f} s, a ratio of {ratio:.4f}"
    )
    # Opening the port is not instantaneous, so allow a few milliseconds of
    # jitter each way; a wrong crystal would be off by tens of percent.
    if abs(ratio - 1) > 0.005:
        sys.exit("clock: out of tolerance")


if __name__ == "__main__":
    main()
