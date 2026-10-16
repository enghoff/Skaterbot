# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Show the INA226's VBS voltage as one line that updates in place, until Ctrl-C.

    sudo python3 vbs_monitor.py

Wired to the Banana Pi's header as ina226_test.py describes, with that script
beside this one: it finds the monitor and sets it converting the same way. The
line carries the latest reading and the lowest and highest since it started, so
a sag or a spike between two refreshes is still seen.
"""

from __future__ import annotations

import argparse
import sys
import time

from ina226_test import BUS, BUS_LSB, CONFIG, CVRF, MASK, RESET, RUN, open_monitor


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bus", type=int, help="/dev/i2c number (default: find TWI0)")
    ap.add_argument("--address", type=lambda s: int(s, 0), help="0x40 to 0x4F")
    ap.add_argument("--refresh", type=float, default=10, help="line updates per second")
    args = ap.parse_args()

    monitor, bus, addr, _ = open_monitor(args.bus, args.address)
    print(f"INA226 at {addr:#04x} on /dev/i2c-{bus}. Ctrl-C to stop.")
    monitor.write(CONFIG, RESET)
    time.sleep(0.01)
    monitor.write(CONFIG, RUN)

    low, high = float("inf"), 0.0
    shown = heard = time.monotonic()
    try:
        while True:
            if not monitor.read(MASK) & CVRF:
                if time.monotonic() - heard > 1:
                    sys.exit(
                        "\nNo conversion for 1 s: the monitor has stopped converting."
                    )
                time.sleep(0.002)
                continue
            heard = time.monotonic()
            volts = monitor.read(BUS) * BUS_LSB
            low, high = min(low, volts), max(high, volts)
            if heard - shown >= 1 / args.refresh:
                shown = heard
                line = f"VBS {volts:6.3f} V    min {low:6.3f}    max {high:6.3f}"
                sys.stdout.write(f"\r{line}\x1b[K")
                sys.stdout.flush()
    except KeyboardInterrupt:
        print()
    except OSError as error:
        sys.exit(f"\nThe monitor stopped answering: {error}")
    finally:
        try:
            monitor.write(CONFIG, RUN & ~0b111)  # power-down: leave it quiet
        except OSError:
            pass
        monitor.close()


if __name__ == "__main__":
    main()
