"""Starts the robot when somebody taps its button, with no one at a keyboard.

    python3 launcher.py

It holds no control and moves no motor, so it can run all the time, beside the motor
console, and does nothing until asked. To ask, tap the robot's power button, for under
TAP_S. The firmware takes two seconds held as the way to turn the robot off, stopping
every motor, and that still works.

Asked, it runs `balance.py launch --drive`: pick the robot up by the torso, tap, and
the legs go to the crouch. Lower it, let go as the wheels touch, and it takes over by
itself, and drives as the controller asks. It has no time limit, and there must never
be one: its end would drop a robot somebody is driving. A tap arms it, and it stays
armed: picked up, or fallen over and picked up, it gets ready again by itself and takes
over when next put down. The next tap stops every motor at once, and disarms it. No
button on the game controller does: letting go of its triggers stops the driving and
leaves it standing.

If the robot is not fit to start, because the motor console's tab holds control or
there is no launch.json, nothing moves, and launcher.log says why. Its motors wake
when it is lifted only once it has been armed: a robot not tapped stays limp.
"""

from __future__ import annotations

import argparse
import queue
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import diag_client  # noqa: E402

# Well under the two seconds that turn the robot off. Status comes ten times a second.
TAP_S = 0.4
# After it stops, for a press that was meant to stop it not to start it again.
QUIET_S = 1.0
RECONNECT_S = 1.0
ENDING_S = 10.0


class Tap:
    """Whether what the robot reports of its button is somebody tapping it. Only
    events, so that it can be tested with none of the rest."""

    def __init__(self):
        self.down_at: float | None = None

    def heard(self, m: dict, now: float) -> bool:
        """A tap is down and up again, soon enough not to be turning the robot off."""
        if m.get("off"):
            self.down_at = None
            return False
        down = bool(m.get("button"))
        if down and self.down_at is None:
            self.down_at = now
        elif not down and self.down_at is not None:
            held, self.down_at = now - self.down_at, None
            return held < TAP_S
        return False


class Launcher:
    def __init__(self, args, command: list[str]):
        self.args = args
        self.command = command
        self.tap = Tap()
        self.tapped: queue.Queue[bool] = queue.Queue()
        self.child: subprocess.Popen | None = None
        self.quiet_until = 0.0
        self.running = True
        self.out = open(args.log, "a", buffering=1, encoding="utf-8")

    def say(self, text: str) -> None:
        self.out.write(f"{datetime.now().isoformat(timespec='seconds')} {text}\n")

    # -- on the reader's thread: nothing here may wait

    def _status(self, m: dict) -> None:
        if self.tap.heard(m, time.monotonic()):
            self.tapped.put(True)

    # -- on the main thread

    def connect(self) -> diag_client.Robot:
        robot = diag_client.Robot(self.args.robot, name="launcher", streams=("status",))
        robot.on("status", self._status)
        return robot

    def asked(self, robot) -> None:
        now = time.monotonic()
        if self.child is not None:
            self.say("the button asked for it to stop")
            robot.stop()
            # A tap before it has taken control has nothing there for that to stop.
            self.child.terminate()
        elif now < self.quiet_until:
            self.say("the button asked, too soon after the last one: ignored")
        else:
            self.say(f"the button asked: {' '.join(self.command)}")
            self.child = subprocess.Popen(
                self.command,
                cwd=HERE,
                stdin=subprocess.DEVNULL,
                stdout=self.out,
                stderr=subprocess.STDOUT,
            )

    def watch_child(self) -> None:
        if self.child is not None and self.child.poll() is not None:
            self.say(f"it ended, with exit code {self.child.returncode}")
            self.child = None
            self.quiet_until = time.monotonic() + QUIET_S

    def stop_child(self) -> None:
        """balance.py takes a TERM as a reason to stop the motors, and diagd stops
        them anyway the moment it goes."""
        if self.child is None:
            return
        self.child.terminate()
        try:
            self.child.wait(ENDING_S)
        except subprocess.TimeoutExpired:
            self.child.kill()
            self.child.wait()
        self.child = None

    def run(self) -> None:
        self.say("waiting for the button")
        robot = None
        while self.running:
            self.watch_child()
            if robot is not None and robot.error:
                self.say(f"lost diagd: {robot.error}")
                robot.close()
                robot = None
            if robot is None:
                try:
                    robot = self.connect()
                    self.say(f"connected to diagd at {self.args.robot}")
                except diag_client.RobotError:
                    time.sleep(RECONNECT_S)
                    continue
            try:
                self.tapped.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self.asked(robot)
            except (OSError, diag_client.RobotError) as error:
                self.say(f"the button asked, and it failed: {error}")
        self.stop_child()
        if robot is not None:
            robot.close()
        self.say("stopped")


def balance_command(args) -> list[str]:
    command = [sys.executable, str(HERE / "balance.py"), "launch", "--yes", "--drive"]
    command += ["--seconds", "0", "--touch-wait", "0"]
    if args.rt:
        command.append("--rt")
    return command


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--robot", default=diag_client.DEFAULT_ROBOT)
    ap.add_argument("--rt", action="store_true", help="the loop at real-time priority")
    ap.add_argument("--log", type=Path, default=HERE / "launcher.log")
    ap.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        help="all that follows is run instead of balance.py, for testing",
    )
    args = ap.parse_args(argv)
    launcher = Launcher(args, args.command or balance_command(args))

    def stop(*_):
        launcher.running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    launcher.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
