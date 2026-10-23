# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Swing the two wheel motors on bus C from the Banana Pi, and say whether they followed.

    sudo python3 wheel_check.py                 scan, then 60 cycles of +/-45 deg at 2 Hz
    sudo python3 wheel_check.py --cycles 240    the same for two minutes
    sudo python3 wheel_check.py --scan          scan only; nothing moves
    sudo python3 wheel_check.py --tx 600        one frame back to back for ten
                                                minutes, for a scope on the bus

The controller board has to be running firmware/wheel_check, which this talks
to through the carrier's J5 as flash_mcu.py does. The motors' CAN goes from the
board through the carrier's U3 and out on J4, so a pass is the whole of bus C
working. What a run does, what it holds the motors to and what it counts as a
pass are in that image's doc comment. To put it on the board:

    sudo python3 flash_mcu.py wheel_check.elf --listen 3

Lift the wheels clear first. Each swings 90 degrees end to end, about wherever
it stands when the run starts, at up to 10 rad/s.

Ctrl-C stops the motors: any byte the board hears during a run stops it and
disables them, and it stops --tx the same way. Every line the board sends is
printed as it comes, and the exit status of a run is 0 only on the board's PASS.
"""

from __future__ import annotations

import argparse
import sys
import time

from flash_mcu import Port, uart4

# A scan of an empty bus takes the board about a quarter of a second.
ANSWER_S = 3.0
# The cycles the board adds to every run, fading in and out, and their length.
FADE_CYCLES = 2
CYCLE_S = 0.5


class Board:
    """wheel_check's end of J5: a line out is a command, and the board's answer
    is every line back up to one saying `ready`."""

    def __init__(self, port: Port):
        self.port = port
        self.pending = b""
        self.heard: list[str] = []

    def send(self, command: str) -> None:
        self.port.write(command.encode() + b"\n")

    def clear(self) -> None:
        """End any partial line the board is holding, and drop its answer to it.
        The Pi's port puts stray bytes on the line while the Pi boots, and the
        board takes them for the start of a command: the first `scan` after a
        power-up read as garbage followed by `scan`, on 2026-10-23."""
        self.port.write(b"\n")
        end = time.monotonic() + 0.3
        while time.monotonic() < end:
            self.port.read(256, 0.1)
        self.pending = b""

    def ask(self, command: str, seconds: float) -> list[str] | None:
        self.heard = []
        self.send(command)
        return self.answer(seconds)

    def answer(self, seconds: float) -> list[str] | None:
        """Print the answer as it comes. Returns its lines so far, or None if it
        did not end in time."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.pending += self.port.read(256, 0.1)
            while b"\n" in self.pending:
                raw, self.pending = self.pending.split(b"\n", 1)
                line = raw.decode(errors="replace").rstrip()
                if line == "ready":
                    return self.heard
                print(line, flush=True)
                self.heard.append(line)
        return None

    def ask_until_stopped(self, command: str, seconds: float) -> list[str] | None:
        """As ask, but Ctrl-C sends a byte, which stops a run or a tx, and the
        answer is then heard out."""
        try:
            return self.ask(command, seconds)
        except KeyboardInterrupt:
            print("\n(stopping)", flush=True)
            self.send("stop")
            return self.answer(ANSWER_S)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--cycles",
        type=int,
        default=60,
        help="full-amplitude cycles, half a second each (default 60)",
    )
    ap.add_argument("--scan", action="store_true", help="scan only; nothing moves")
    ap.add_argument(
        "--tx",
        type=int,
        metavar="SECONDS",
        help="transmit one frame back to back for this long, for a scope",
    )
    args = ap.parse_args()
    if not 1 <= args.cycles <= 7200:
        sys.exit("--cycles is 1 to 7200")
    if args.tx is not None and not 1 <= args.tx <= 3600:
        sys.exit("--tx is 1 to 3600")

    port = Port(uart4())
    board = Board(port)
    try:
        board.clear()
        if args.tx is not None:
            if board.ask_until_stopped(f"tx {args.tx}", args.tx + ANSWER_S) is None:
                sys.exit("The board stopped answering.")
            sys.exit(0)

        scan = board.ask("scan", ANSWER_S)
        if scan is None:
            sys.exit(
                f"No answer from the board on {port.path}. Is wheel_check running? "
                "sudo python3 flash_mcu.py --listen 3 shows what is."
            )
        found = next(
            (
                int(s.split()[1])
                for s in scan
                if s.startswith("scan: ") and " on bus C;" in s
            ),
            0,
        )
        if args.scan or found == 0:
            sys.exit(0 if found == 2 else 1)

        seconds = (args.cycles + 2 * FADE_CYCLES) * CYCLE_S + ANSWER_S
        try:
            run = board.ask(f"run {args.cycles}", seconds)
        except KeyboardInterrupt:
            # Any byte stops a run; the board then disables the motors and
            # finishes its answer.
            print("\n(stopping)", flush=True)
            board.send("stop")
            run = board.answer(ANSWER_S)
        if run is None:
            sys.exit("The board stopped answering mid-run.")
        sys.exit(0 if any(s.startswith("verdict: PASS") for s in run) else 1)
    finally:
        port.close()


if __name__ == "__main__":
    main()
