"""Starts the robot when somebody taps its button, with no one at a keyboard.

    python3 launcher.py

It holds no control and moves no motor, so it can run all the time, beside the motor
console, and does nothing until asked. To ask, tap the robot's power button. Any press
counts that is let go of before the two seconds the firmware takes as the way to turn the
robot off, stopping every motor, and that still works.

Asked, it runs `balance.py launch --drive`, and the legs go to the crouch whatever the
robot's pose. Lower it, let go as the wheels touch, and it takes over by itself, and
drives as the controller asks. It has no time limit, and there must never be one: its end
would drop a robot somebody is driving. A tap arms it, and it stays armed: picked up, or
fallen over and picked up, it gets ready again by itself and takes over when next put
down. The next tap stops every motor at once, and disarms it, unless the robot is lying
limp, when a tap wakes it instead, since stopping what is already limp would look like
nothing at all. No button on the game controller does either: letting go of its triggers
stops the driving and leaves it standing.

A press must get an answer unless something is seriously wrong. So what only looks like
a reason to wait is not one: a tap while the last run is still ending arms it again as
soon as that has gone, a tap while one is starting leaves it to start, and a motor
console's tab holding control gives way to it. What is left is balance.py's to refuse, in
get_ready, and launcher.log says why. Its motors wake when it is lifted only once it has
been armed: a robot not tapped stays limp.
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

RECONNECT_S = 1.0
# How long a run told to stop gets to save its log, with its motors already stopped.
ENDING_S = 5.0
# Longer than getting ready takes, however many looks that needs. After this, one that
# has not said what it is doing is treated as any other, and a tap stops it.
STARTING_S = 10.0
# A run takes a moment of the Pi's time to start, which is not for the moment it is
# starting one of its own. And one failing to start must not be retried in a tight loop.
SPARE_AFTER_S = 5.0
SPARE_AGAIN_S = 5.0
LIMP = "limp"


class Tap:
    """Whether what the robot reports of its button is somebody tapping it. Only
    events, so that it can be tested with none of the rest."""

    def __init__(self):
        self.down = False

    def heard(self, m: dict) -> bool:
        """A tap is down and up again, short of turning the robot off. Status comes ten
        times a second, and the firmware holds a press over until the next one goes."""
        if m.get("off"):
            self.down = False
            return False
        was, self.down = self.down, bool(m.get("button"))
        return was and not self.down


class Launcher:
    def __init__(self, args, command: list[str]):
        self.args = args
        self.command = command
        self.tap = Tap()
        self.tapped: queue.Queue[bool] = queue.Queue()
        self.child: subprocess.Popen | None = None
        # One already loaded and waiting for the word, since loading takes a second.
        self.spare: subprocess.Popen | None = None
        self.spare_at = -SPARE_AGAIN_S
        self.started_at = 0.0
        self.stopping_at: float | None = None
        self.again = False
        self.running = True
        self.out = open(args.log, "a", buffering=1, encoding="utf-8")

    def say(self, text: str) -> None:
        self.out.write(f"{datetime.now().isoformat(timespec='seconds')} {text}\n")

    # -- on the reader's thread: nothing here may wait

    def _status(self, m: dict) -> None:
        if self.tap.heard(m):
            self.tapped.put(True)

    # -- on the main thread

    def connect(self) -> diag_client.Robot:
        robot = diag_client.Robot(self.args.robot, name="launcher", streams=("status",))
        robot.on("status", self._status)
        return robot

    def phase(self) -> str | None:
        """What the run says it is doing. None until it has begun to do anything; what
        cannot be read counts as doing something, so that a tap stops it."""
        try:
            return self.args.phase_file.read_text().strip() or "unknown"
        except FileNotFoundError:
            return None
        except OSError:
            return "unknown"

    def warm(self) -> subprocess.Popen:
        self.spare_at = time.monotonic()
        return subprocess.Popen(
            self.command,
            cwd=HERE,
            stdin=subprocess.PIPE,
            stdout=self.out,
            stderr=subprocess.STDOUT,
        )

    def word(self, child: subprocess.Popen, what: bytes) -> None:
        child.stdin.write(what + b"\n")
        child.stdin.flush()

    def start(self) -> None:
        self.say(f"the button asked: {' '.join(self.command)}")
        self.args.phase_file.unlink(missing_ok=True)
        child, self.spare = self.spare, None
        if child is None or child.poll() is not None:
            child = self.warm()
        # One still loading reads this when it is ready for it.
        try:
            self.word(child, b"go")
        except OSError:
            child = self.warm()
            self.word(child, b"go")
        self.child = child
        self.started_at = time.monotonic()

    def stop(self, robot) -> None:
        self.say("the button asked for it to stop")
        self.stopping_at = time.monotonic()
        try:
            robot.stop()
        finally:
            # A tap before it has taken control has nothing there for that to stop.
            self.child.terminate()

    def asked(self, robot) -> None:
        if self.child is None:
            self.start()
        elif self.stopping_at is not None:
            # Motors already stopped, and the same again, as many times as it takes.
            self.again = not self.again
            self.say(
                f"the button asked while it ends: {'arms' if self.again else 'stays off'} after"
            )
        else:
            phase = self.phase()
            young = time.monotonic() - self.started_at < STARTING_S
            if phase is None and young:
                self.say("the button asked while it starts: left to start")
            elif phase == LIMP:
                self.say("the button asked while it is limp: waking it")
                try:
                    self.word(self.child, b"wake")
                except OSError:
                    self.stop(robot)
            else:
                self.stop(robot)

    def watch_child(self) -> None:
        now = time.monotonic()
        if self.child is not None and self.child.poll() is not None:
            self.say(f"it ended, with exit code {self.child.returncode}")
            self.child = None
            self.stopping_at = None
            if self.again:
                self.again = False
                try:
                    self.start()
                except OSError as error:
                    self.say(f"it could not start again: {error}")
        elif self.stopping_at is not None and now - self.stopping_at > ENDING_S:
            self.say("it has not gone: killing it")
            self.child.kill()
            self.stopping_at = now
        wanted = self.spare is None or self.spare.poll() is not None
        settled = self.child is None or now - self.started_at > SPARE_AFTER_S
        if wanted and settled and now - self.spare_at > SPARE_AGAIN_S:
            try:
                self.spare = self.warm()
            except OSError as error:
                self.say(f"it could not load a spare: {error}")

    def end(self, child: subprocess.Popen | None) -> None:
        """balance.py takes a TERM as a reason to stop the motors, and diagd stops
        them anyway the moment it goes."""
        if child is None:
            return
        child.terminate()
        try:
            child.wait(ENDING_S)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()

    def run(self) -> None:
        self.say("waiting for the button")
        robot = None
        while self.running:
            self.watch_child()
            if robot is not None and robot.error:
                self.say(f"lost diagd: {robot.error}")
                robot.close()
                robot = None
                self.tap = Tap()
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
        self.end(self.child)
        self.end(self.spare)
        if robot is not None:
            robot.close()
        self.say("stopped")


def balance_command(args) -> list[str]:
    command = [sys.executable, str(HERE / "balance.py"), "launch", "--yes", "--drive"]
    command += ["--seconds", "0", "--touch-wait", "0"]
    command += ["--button", "--phase-file", str(args.phase_file)]
    # Slow, which every run starts in; select on the controller toggles to fast, which
    # is 1.8 m/s and 15 rad/s: D3's whole trained range, where the robot has been
    # driven, and inside D5's 2.2 m/s and 25 rad/s, whose top the wheels' 50 rad/s
    # stop in sbc/policy_loop.py would cut short.
    command += ["--max-speed", "1.0", "--max-turn", "2.0"]
    command += ["--fast-speed", "1.8", "--fast-turn", "15.0"]
    # The driving policy told it leans 1.67 degrees nose-up per m/s it is sent, 3 at
    # fast mode's 1.8: on launch_check.py's rig D8 then holds 1.41 m/s rather than
    # 1.17 and passes every case (balance.py's THE LEAN). Untried on the robot when set
    # on 8 November 2026; 0 takes it out.
    command += ["--lean-per-m-s", "1.67"]
    # The A button jumps: the scripted jump, pushing balance.py's --jump-push, 1.6 Nm of
    # each knee's 3 unless that is changed here, held to 1.8 at most. In MuJoCo on 8
    # November 2026 it cleared 18-21 mm there and landed and stood every time; untried on
    # the robot when set. With args.jump "policy", a jump policy put beside the driving one
    # is used instead, as high as balance.py's --jump-height, 30 mm unless changed here;
    # "none" is no jump.
    jump = HERE / "policy_jump.npz"
    chosen = getattr(args, "jump", "scripted")
    if chosen == "scripted":
        # At balance.py's cap, 2.5 Nm, from 1.8. At 1.8 and the level push below, on the
        # robot on 8 November 2026, 34 jumps, one of which fell, driving at 1.05 m/s
        # (policy_loop.py's JUMP_RUN_TOP_M_S has it). In MuJoCo, the level push at 0.35,
        # 2.5 cleared 26-29 mm standing and 20-26 driving, against 20-21 and 12-16 at 1.8,
        # the knees no nearer than 0.49 rad to straight, standing every time; on that rig
        # with the robot's floor friction and its half answer to the level push, 21-23
        # standing and 19-22 driving (jump_height/). Untried on the robot when set.
        command += ["--jump-policy", "scripted", "--jump-push", "2.5"]
        # The level push, each wheel driven forward through the push, at twice MuJoCo's
        # 0.18 Nm: the robot answers it about half as much. Its scripted jumps on 8
        # November 2026, the IMU's pitch at the hand back: with none (08:57, 13 jumps)
        # 8-32 degrees nose-down, median 16, where MuJoCo lands 17-18; at 0.13-0.23 Nm
        # (10:56, 10 jumps) -2 to +23, median 10, where MuJoCo lands 1-2. The jumps that
        # fell, 3 and 2, were those landing steepest, 17-37 degrees. At 0.35 MuJoCo lands
        # 9-11 degrees nose-up and stands; the robot, by its half, about 4 nose-down. At
        # 11:28-11:42, pushing 1.6 Nm, 26 jumps landed -10 to +10, median level, and none
        # fell. balance.py's --jump-level-nm: Nm at a push of 1.6 Nm, and in proportion to
        # the push, so 0.55 Nm at 2.5.
        command += ["--jump-level-nm", "0.35"]
    elif chosen == "policy" and jump.exists():
        command += ["--jump-policy", str(jump)]
    if args.rt:
        command.append("--rt")
    return command


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--robot", default=diag_client.DEFAULT_ROBOT)
    ap.add_argument("--rt", action="store_true", help="the loop at real-time priority")
    ap.add_argument(
        "--jump",
        choices=("scripted", "policy", "none"),
        default="scripted",
        help="what the A button does: the scripted jump, the jump policy in "
        "policy_jump.npz if there is one, or nothing (default scripted)",
    )
    ap.add_argument("--log", type=Path, default=HERE / "launcher.log")
    ap.add_argument(
        "--phase-file",
        type=Path,
        default=Path("/dev/shm/bipedal_phase"),
        help="where a run says what it is doing: in memory, so that it never waits on a disk",
    )
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
