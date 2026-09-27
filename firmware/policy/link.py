# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "pyserial>=3.5"]
# ///
"""Talk to the policy firmware over its USB serial port.

    uv run firmware/policy/link.py                  what the board holds
    uv run firmware/policy/link.py bench [COUNT]    time the network on the board
    uv run firmware/policy/link.py crash KIND       panic, fault, hang or interrupt
    uv run firmware/policy/link.py bootloader       reboot into the bootloader

`crash` is how the firmware's recovery is proven: every kind should leave the
board in its USB bootloader, from which `flash.ps1 -Start` restarts it and
`link.py` then reports what the crash was. A hang takes the watchdog's 30 s.

hil.py imports Board from here; the protocol is set out in src/main.rs.
"""

from __future__ import annotations

import argparse
import struct
import sys
import time

import numpy as np
import serial
from serial.tools import list_ports

VID, PID = 0x1209, 0x0001
CRASHES = {"panic": 0, "fault": 1, "hang": 2, "interrupt": 3}


class BoardError(RuntimeError):
    pass


def find_port() -> str:
    for port in list_ports.comports():
        if (port.vid, port.pid) == (VID, PID):
            return port.device
    raise BoardError(
        f"no board with USB ID {VID:04x}:{PID:04x}: is it in its bootloader?"
        " (flash.ps1 -Start restarts it)"
    )


class Board:
    """The policy firmware, one request at a time."""

    def __init__(self, port: str | None = None, timeout: float = 2.0):
        self.port = serial.Serial(port or find_port(), 115200, timeout=timeout)
        # Opening the port starts a session on the board. Anything a different
        # firmware says on opening -- the bring-up one's banner -- is dropped.
        time.sleep(0.2)
        self.port.reset_input_buffer()
        try:
            self.info = self.describe()
        except BoardError as error:
            self.port.close()
            raise BoardError(f"{self.port.port} is not the policy firmware: {error}")
        if self.info.get("firmware") != "policy":
            self.port.close()
            raise BoardError(f"{self.port.port} is running {self.info}")
        self.n_obs, self.n_act = int(self.info["obs"]), int(self.info["act"])
        self.hz = int(self.info["sysclk_hz"])

    def close(self):
        self.port.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def request(self, letter: bytes, payload: bytes = b"") -> bytes:
        self.port.write(letter + payload)
        head = self.port.read(3)
        if len(head) < 3:
            raise BoardError(f"no answer to {letter!r}")
        n = struct.unpack("<H", head[1:])[0]
        body = self.port.read(n)
        if len(body) < n:
            raise BoardError(f"{letter!r}: {len(body)} of {n} bytes")
        if head[:1] == b"E":
            raise BoardError(body.decode(errors="replace"))
        if head[:1] != letter:
            raise BoardError(f"asked {letter!r}, answered {head[:1]!r}")
        return body

    def describe(self) -> dict[str, str]:
        text = self.request(b"I").decode()
        return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)

    def step(self, obs: np.ndarray) -> tuple[np.ndarray, int]:
        """The network's raw outputs for one observation, and the cycles the
        board took over them."""
        obs = np.asarray(obs, dtype="<f4").ravel()
        assert obs.size == self.n_obs, obs.shape
        body = self.request(b"P", obs.tobytes())
        actions = np.frombuffer(body[: 4 * self.n_act], dtype="<f4").copy()
        (cycles,) = struct.unpack("<I", body[4 * self.n_act :])
        return actions, cycles

    def bench(self, count: int = 1000) -> dict[str, float]:
        """The network run `count` times on the last observation stepped."""
        old = self.port.timeout
        self.port.timeout = 30.0
        try:
            body = self.request(b"B", struct.pack("<H", count))
        finally:
            self.port.timeout = old
        n, fewest, most, cycles, micros = struct.unpack("<IIIQQ", body)
        return dict(
            count=n,
            fewest_us=fewest / self.hz * 1e6,
            most_us=most / self.hz * 1e6,
            mean_us=cycles / n / self.hz * 1e6,
            # The same span by the cycle counter and by the system timer.
            cycles_s=cycles / self.hz,
            timer_s=micros / 1e6,
        )

    def crash(self, kind: str):
        self.request(b"C", bytes([CRASHES[kind]]))

    def bootloader(self):
        self.request(b"Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", help="the board's serial port, if not found by ID")
    sub = parser.add_subparsers(dest="command")
    bench = sub.add_parser("bench", help="time the network on the board")
    bench.add_argument("count", type=int, nargs="?", default=1000)
    crash = sub.add_parser("crash", help="crash the firmware, to prove recovery")
    crash.add_argument("kind", choices=CRASHES)
    sub.add_parser("bootloader", help="reboot into the bootloader")
    args = parser.parse_args()

    try:
        board = Board(args.port)
    except (BoardError, serial.SerialException) as error:
        print(error, file=sys.stderr)
        return 1
    with board:
        if args.command is None:
            for key, value in board.info.items():
                print(f"{key:>12}  {value}")
        elif args.command == "bench":
            # The time hangs on the input only through how many units come out
            # negative and take the ELU's exp; hil.py times real observations.
            board.step(np.zeros(board.n_obs, dtype=np.float32))
            r = board.bench(args.count)
            print(
                f"{r['count']} runs: {r['mean_us']:.1f} us each on average,"
                f" {r['fewest_us']:.1f} fewest, {r['most_us']:.1f} most"
            )
            print(
                f"the whole by the cycle counter {r['cycles_s'] * 1e3:.1f} ms,"
                f" by the system timer {r['timer_s'] * 1e3:.1f} ms"
            )
        elif args.command == "crash":
            board.crash(args.kind)
            print(f"crashed by {args.kind}: the board should now be in its bootloader")
        elif args.command == "bootloader":
            board.bootloader()
            print("rebooting into the bootloader")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
