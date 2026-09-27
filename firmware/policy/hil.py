# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy>=1.26", "mujoco>=3.2", "onnxruntime>=1.18",
#                 "pyyaml>=6.0", "pygame>=2.5", "onnx>=1.16", "pyserial>=3.5"]
# ///
"""Drive the simulated robot with the policy running on the board.

    uv run firmware/policy/hil.py --check
    uv run firmware/policy/hil.py                  the viewer, as drive.py gives it
    uv run firmware/policy/hil.py --port COM8 --run exports/rl/<run> --check

Every argument but --port is simulation/mujoco/drive.py's, and so is everything
else: the robot, the motor model, the commands, the report. The one difference
is what answers the policy's question each step: the board, over USB, where
drive.py asks onnxruntime on this machine. The board has to hold the run's
network -- export.py writes it into the firmware and flash.ps1 policy puts it
on the board -- and its digest is checked before the first step.

Every observation the board answers also goes to onnxruntime and to the same
network worked in 64 bits, and at the end this reports how far the board's
answers were from each, and how long the board took over them. The simulation
waits for the board each step, so --check's verdict is on the board's
arithmetic in closed loop, not on its timing: running to a 10 ms clock of its
own is the robot firmware's job, still to come.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import onnxruntime as ort

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "simulation" / "mujoco"))

import drive  # noqa: E402
import export  # noqa: E402
from link import Board  # noqa: E402


class BoardSession:
    """onnxruntime's InferenceSession, as drive.py calls it, answered by the
    board, with onnxruntime and the exact answer alongside for comparison."""

    def __init__(self, policy: Path, board: Board):
        held, wanted = board.info["digest"], export.digest(policy)
        if held != wanted:
            sys.exit(
                f"the board holds {board.info['run']} ({held}), not {policy}"
                f" ({wanted}): export.py that run and flash.ps1 policy"
            )
        self.board = board
        self.reference = ort.InferenceSession(str(policy))
        self.net = export.load(policy)
        self.steps: list[tuple[float, ...]] = []

    def run(self, _outputs, feeds):
        obs = feeds["obs"]
        start = time.perf_counter()
        ours, cycles = self.board.step(obs[0])
        trip = time.perf_counter() - start
        theirs = self.reference.run(None, feeds)[0][0]
        exact = self.net.forward(obs.astype(np.float64), np.float64)[0]
        self.steps.append(
            (
                np.abs(ours - theirs).max(),
                np.abs(np.clip(ours, -1, 1) - np.clip(theirs, -1, 1)).max(),
                np.abs(ours - exact).max(),
                np.abs(theirs - exact).max(),
                np.abs(ours).max(),
                cycles / self.board.hz,
                trip,
            )
        )
        return [ours[None]]

    def report(self):
        if not self.steps:
            return
        vs_ort, clipped, ours_off, theirs_off, size, compute, trip = np.array(
            self.steps
        ).T
        us, ms = 1e6, 1e3
        print(
            f"\nthe board answered {len(self.steps)} steps."
            f" Its raw outputs reached {size.max():.0f} before clipping to +/-1."
        )
        print(
            f"  from onnxruntime, largest difference {vs_ort.max():.1e} raw,"
            f" {clipped.max():.1e} once clipped as the robot uses them"
        )
        print(
            f"  from the exact answer, the board at most {ours_off.max():.1e},"
            f" onnxruntime at most {theirs_off.max():.1e}"
        )
        print(
            f"  the network on the board: {np.median(compute) * us:.0f} us median,"
            f" {compute.min() * us:.0f} to {compute.max() * us:.0f}"
        )
        print(
            f"  the USB round trip with it: {np.median(trip) * ms:.2f} ms median,"
            f" {np.percentile(trip, 99) * ms:.2f} at the 99th percentile,"
            f" {trip.max() * ms:.2f} at most"
        )


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--port", help="the board's serial port, if not found by ID")
    ours, theirs = parser.parse_known_args()

    board = Board(ours.port)
    sessions: list[BoardSession] = []

    def session(policy: str) -> BoardSession:
        sessions.append(BoardSession(Path(policy), board))
        return sessions[-1]

    # drive.py asks onnxruntime for a session once, when it builds its
    # controller; this is the only thing about it that changes.
    drive.ort = SimpleNamespace(InferenceSession=session)
    sys.argv = [drive.__file__, *theirs]
    try:
        return drive.main()
    finally:
        for s in sessions:
            s.report()
        board.close()


if __name__ == "__main__":
    raise SystemExit(main())
