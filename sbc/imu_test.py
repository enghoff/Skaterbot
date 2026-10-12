# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Read the BNO085 straight off the Banana Pi's header, and say whether it works.

    sudo python3 imu_test.py                  stream readings until Ctrl-C
    sudo python3 imu_test.py --seconds 20     stream for 20 s, then judge it
    sudo python3 imu_test.py --csv imu.csv    also log every report to a file

This is the bench test from before the carrier exists. On the robot the IMU
hangs off the STM32's I2C through carrier J6; here it is wired to the Banana
Pi's 40-pin header through a Qwiic-to-jumper lead (Adafruit 4397 or similar):

    module 3V3 -> header pin 1      module SDA -> header pin 3
    module GND -> header pin 6      module SCL -> header pin 5

Never 5 V: the 7Semi pinout labels the supply 3.3 V input, whatever the product
page says (docs/CARRIER.md). Pins 3 and 5 are TWI0, which Armbian only switches
on with the `bananapi-m4-pi-5-6-i2c0` overlay in /boot/armbianEnv.txt. The M4
Zero has no pull-ups of its own on those pins, so the bus relies on the
module's.

Held still on a bench for the length of a run, it checks what a working part
must show: an answer at 0x4A or 0x4B, a product ID, every report arriving at the
rate it was granted, gravity within 0.5 of 9.81 m/s^2, a gyro bias under
2 deg/s, and a unit quaternion. A magnetic field outside 20-70 uT is only a
warning, because a bench full of steel bends it. Moved during the run, it skips
the checks that need it still and says so.

Only the standard library. The BNO085 speaks Hillcrest's SHTP over plain I2C
reads and writes, which /dev/i2c-N does without smbus: every read begins with a
4-byte header giving the packet's length, so a packet is read as its header
first and then whole. Channel 2 carries commands and their answers, channel 3
the sensor reports. Numbers are from the SH-2 reference manual.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import glob
import math
import os
import struct
import sys
import time

I2C_SLAVE = 0x0703
TWI0 = "5002000.i2c"  # the controller on header pins 3 and 5
ADDRESSES = (0x4A, 0x4B)  # the module's ADD jumper on 0 or 1

# report id: (name, fixed-point Q, how many values)
REPORTS = {
    0x01: ("accel", 8, 3),  # m/s^2
    0x02: ("gyro", 9, 3),  # rad/s
    0x03: ("mag", 4, 3),  # uT
    0x05: ("rotation", 14, 5),  # i, j, k, real, then accuracy in Q12 radians
}
# The length of everything that can share a channel-3 packet, so a packet can be
# walked: the four above, the two timestamp records, and reports nobody asked for.
LENGTHS = {0x01: 10, 0x02: 10, 0x03: 10, 0x05: 14, 0xFA: 5, 0xFB: 5}
LENGTHS |= {0x04: 10, 0x06: 10, 0x07: 16, 0x08: 12, 0x09: 14, 0x0F: 16}
LENGTHS |= {0x28: 14, 0x29: 12, 0x2A: 14}


class Hub:
    """One BNO085 on /dev/i2c-<bus>, spoken to in SHTP packets."""

    def __init__(self, bus: int, address: int):
        self.fd = os.open(f"/dev/i2c-{bus}", os.O_RDWR)
        fcntl.ioctl(self.fd, I2C_SLAVE, address)
        self.seq = [0] * 6

    def send(self, channel: int, payload: bytes) -> None:
        header = struct.pack("<HBB", len(payload) + 4, channel, self.seq[channel])
        self.seq[channel] = (self.seq[channel] + 1) & 0xFF
        os.write(self.fd, header + payload)

    def receive(self) -> tuple[int, bytes] | None:
        """The next packet as (channel, payload), or None if the hub has none.

        A read the hub refuses is treated as nothing to read: it holds the bus
        while it works, and the caller notices if that never ends."""
        try:
            length = struct.unpack("<H", os.read(self.fd, 4)[:2])[0] & 0x7FFF
            if length <= 4 or length > 4096:
                return None
            packet = os.read(self.fd, length)
        except OSError:
            return None
        return packet[2], packet[4:]

    def wait_for(self, channel: int, first_byte: int, seconds: float) -> bytes | None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            got = self.receive()
            if got is None:
                time.sleep(0.005)
            elif got[0] == channel and got[1][:1] == bytes([first_byte]):
                return got[1]
        return None

    def enable(self, report: int, interval_us: int) -> None:
        # Set Feature: id, flags, change sensitivity, interval, batch, config.
        self.send(2, struct.pack("<BBBHIII", 0xFD, report, 0, 0, interval_us, 0, 0))

    def close(self) -> None:
        os.close(self.fd)


def header_bus() -> int | None:
    """The /dev/i2c number Linux gave TWI0, if the overlay has switched it on."""
    for path in glob.glob("/sys/bus/i2c/devices/i2c-*"):
        if TWI0 in os.path.realpath(path):
            return int(path.rsplit("-", 1)[1])
    return None


def open_hub(bus: int | None, address: int | None) -> tuple[Hub, int, int]:
    bus = header_bus() if bus is None else bus
    if bus is None:
        sys.exit(
            "Header I2C is off. Add bananapi-m4-pi-5-6-i2c0 to the overlays= "
            "line of /boot/armbianEnv.txt and reboot, or pass --bus."
        )
    for addr in (address,) if address else ADDRESSES:
        try:
            hub = Hub(bus, addr)
        except PermissionError:
            sys.exit(f"No permission on /dev/i2c-{bus}: run with sudo.")
        try:
            os.read(hub.fd, 4)
            return hub, bus, addr
        except OSError:
            hub.close()
    sys.exit(
        f"Nothing answers at {', '.join(hex(a) for a in ADDRESSES)} on "
        f"/dev/i2c-{bus}. Check 3V3 on pin 1, SDA on pin 3, SCL on pin 5, "
        "GND on pin 6, and that SDA and SCL are not swapped."
    )


def decode(report: int, body: bytes) -> tuple[int, list[float]]:
    """A report's calibration status (0-3) and its values in SI units."""
    _, q, count = REPORTS[report]
    raw = struct.unpack_from(f"<{count}h", body, 4)
    values = [v / (1 << q) for v in raw]
    if report == 0x05:
        values[4] = raw[4] / (1 << 12)  # heading accuracy, radians, in Q12
    return body[2] & 0x03, values


def euler(i: float, j: float, k: float, r: float) -> tuple[float, float, float]:
    """Roll, pitch and yaw in degrees from the hub's quaternion."""
    roll = math.atan2(2 * (r * i + j * k), 1 - 2 * (i * i + j * j))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (r * j - k * i))))
    yaw = math.atan2(2 * (r * k + i * j), 1 - 2 * (j * j + k * k))
    return tuple(math.degrees(a) for a in (roll, pitch, yaw))


def mean_std(rows: list[list[float]]) -> tuple[list[float], list[float]]:
    n = len(rows)
    mean = [sum(col) / n for col in zip(*rows)]
    std = [
        math.sqrt(sum((v - m) ** 2 for v in col) / n)
        for col, m in zip(zip(*rows), mean)
    ]
    return mean, std


def judge(samples: dict, granted: dict, elapsed: float) -> bool:
    print(f"\n--- {elapsed:.1f} s of readings")
    ok = True

    def check(passed: bool | None, text: str, fails: bool = True) -> None:
        nonlocal ok
        ok &= passed is not False or not fails
        if passed is None:
            word = "SKIP"
        else:
            word = "PASS" if passed else "FAIL" if fails else "WARN"
        print(f"  {word}  {text}")

    for report, (name, *_rest) in REPORTS.items():
        want = 1e6 / granted[report] if granted.get(report) else 0
        got = len(samples[report]) / elapsed
        check(
            want > 0 and got >= 0.9 * want,
            f"{name:8s} {got:6.1f} Hz of {want:.1f} Hz granted",
        )
    if not all(samples[r] for r in REPORTS):
        return False

    gyro, gyro_sd = mean_std([v for _, v in samples[0x02]])
    still = max(gyro_sd) < math.radians(0.5)
    accel, _ = mean_std([v for _, v in samples[0x01]])
    g = math.hypot(*accel)
    bias = math.degrees(math.hypot(*gyro))
    field = math.hypot(*mean_std([v for _, v in samples[0x03]])[0])
    quat = [v for _, v in samples[0x05]]
    norm = max(abs(math.hypot(*q[:4]) - 1) for q in quat)
    status = {name: samples[r][-1][0] for r, (name, *_x) in REPORTS.items()}

    if not still:
        print("  moved during the run: gravity and gyro bias need it held still")
    check(abs(g - 9.81) < 0.5 if still else None, f"gravity  {g:.2f} m/s^2")
    check(bias < 2.0 if still else None, f"gyro bias {bias:.2f} deg/s")
    # A warning only: steel, magnets and the Pi itself bend the field on a bench.
    check(20 < field < 70, f"field    {field:.1f} uT (Earth's is 25-65)", False)
    check(norm < 0.01, f"quaternion unit to within {norm:.4f}")
    print(
        "  calibration status (0 unreliable .. 3 high): "
        + ", ".join(f"{n} {s}" for n, s in status.items())
    )
    print("  RESULT:", "the IMU works" if ok else "something is wrong")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bus", type=int, help="/dev/i2c number (default: find TWI0)")
    ap.add_argument("--address", type=lambda s: int(s, 0), help="0x4A or 0x4B")
    ap.add_argument("--rate", type=float, default=50, help="report rate, Hz")
    ap.add_argument("--seconds", type=float, help="stop after this long")
    ap.add_argument("--csv", help="log every report to this file")
    args = ap.parse_args()

    hub, bus, addr = open_hub(args.bus, args.address)
    print(f"BNO085 answers at {addr:#04x} on /dev/i2c-{bus}")

    hub.send(1, b"\x01")  # executable channel: reset, so every run starts clean
    time.sleep(0.5)
    hub.wait_for(1, 0x01, 1.0)  # "reset complete", after the advertisement
    hub.send(2, b"\xf9\x00")
    pid = hub.wait_for(2, 0xF8, 1.0)
    if pid is None:
        sys.exit(
            "It answered but sent no product ID: not a BNO08x, or the bus "
            "is unreliable. Shorten the leads and try again."
        )
    major, minor, part, build, patch = struct.unpack_from("<BBIIH", pid, 2)
    print(f"product ID: part {part}, firmware {major}.{minor}.{patch} build {build}")

    interval = int(1e6 / args.rate)
    granted = {}
    for report in REPORTS:
        hub.enable(report, interval)
        reply = hub.wait_for(2, 0xFC, 1.0)  # Get Feature Response: what was set
        granted[report] = (
            struct.unpack_from("<I", reply, 5)[0]
            if reply and reply[1] == report
            else interval
        )

    log_file = open(args.csv, "w", newline="") if args.csv else None
    log = csv.writer(log_file) if log_file else None
    if log:
        log.writerow(["t", "report", "status", "v0", "v1", "v2", "v3", "v4"])

    samples = {r: [] for r in REPORTS}
    latest: dict[int, list[float]] = {}
    start = shown = heard = time.monotonic()
    tty = sys.stdout.isatty()
    try:
        while args.seconds is None or time.monotonic() - start < args.seconds:
            got = hub.receive()
            if got is None:
                if time.monotonic() - heard > 3:
                    print("\nNo reports for 3 s: the hub has stopped answering.")
                    break
                time.sleep(0.002)
                continue
            channel, payload = got
            if channel != 3:
                continue
            heard = time.monotonic()
            now = heard - start
            i = 0
            while i < len(payload):
                report = payload[i]
                size = LENGTHS.get(report)
                if size is None or i + size > len(payload):
                    break
                if report in REPORTS:
                    status, values = decode(report, payload[i : i + size])
                    samples[report].append((status, values))
                    latest[report] = values
                    if log:
                        log.writerow(
                            [
                                f"{now:.4f}",
                                REPORTS[report][0],
                                status,
                                *(f"{v:.5f}" for v in values),
                            ]
                        )
                i += size
            if len(latest) == len(REPORTS) and time.monotonic() - shown > 0.1:
                shown = time.monotonic()
                a, w, m, q = (latest[r] for r in REPORTS)
                roll, pitch, yaw = euler(*q[:4])
                line = (
                    f"t {now:5.1f}  acc {a[0]:6.2f} {a[1]:6.2f} {a[2]:6.2f}"
                    f"  gyr {math.degrees(w[0]):6.1f} {math.degrees(w[1]):6.1f}"
                    f" {math.degrees(w[2]):6.1f} deg/s"
                    f"  mag {m[0]:5.1f} {m[1]:5.1f} {m[2]:5.1f} uT"
                    f"  roll {roll:6.1f} pitch {pitch:6.1f} yaw {yaw:6.1f}"
                )
                print(line, end="\r" if tty else "\n", flush=True)
    except KeyboardInterrupt:
        pass
    elapsed = time.monotonic() - start
    if log_file:
        log_file.close()
    try:
        for report in REPORTS:
            hub.enable(report, 0)  # leave the hub quiet
    except OSError:
        pass
    hub.close()
    sys.exit(0 if judge(samples, granted, elapsed) else 1)


if __name__ == "__main__":
    main()
