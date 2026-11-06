# /// script
# requires-python = ">=3.11"
# dependencies = ["pyserial>=3.5"]
# ///
"""Run a system-identification test on the robot, through diagd, and log every frame of it.

    python3 sysid.py list                          the tests, and what each needs set up
    python3 sysid.py map                           which motor is which joint, and the IMU's axes
    python3 sysid.py level                         then the IMU against a level, and the legs' zeros
    python3 sysid.py A2 --motor C:1                one motor on the bench, output bare
    python3 sysid.py A2 --motor C:1 --load-inertia 0.004 --label disc
    python3 sysid.py B1                            the robot hanging from the rail

docs/SYSID.md is the plan, and sbc/sysid_tests.py holds the tests themselves:
what each segment asks of each motor, and the limits that stop it. This plays
them at the test's rate through diagd (docs/DIAGNOSTICS.md) in MIT mode, and
writes everything that comes back -- every motor's report as the controller
stamped it, every IMU report, the controller's status -- with every command as
it was sent, to one file, ~/sysid_logs/<when>_<test>.jsonl unless --out says
otherwise. simulation/sysid/ reads that on a PC.

It stops every motor, and says why, if a motor faults, overheats, goes past
its test's speed or its leg's window, or stops answering; on Ctrl-C; and if
diagd or the controller stops them, which they do on their own if this goes
quiet. The controller's deadman and the power button stand behind all of it.

`map` comes first on the robot. With the motors off it asks for each joint to
be moved by hand, finds the motor that turned and which way, takes the legs'
zero hanging straight down, and finds the IMU's axes from the accelerometer
while level and the gyro while the robot is tipped nose-down. It writes
sbc/sysid_robot.json; until that exists every robot test refuses to run.

`level` comes next, and puts right the two things `map` can only take from the
robot as it hangs. The IMU's up is taken with the torso held level by a phone's
level app, read both ways round so the phone's own error cancels, and its
forward from the accelerometer alone as the robot is tipped, since a gyro also
counts the robot turning on the rail. Each leg's zero is the middle of where
the joint settles from in front and from behind, because the joints' friction
holds a hanging leg anywhere in a band several degrees wide.

Run it on the Pi, beside diagd, so the commands keep time. --robot takes what
diag_client.py takes for running it from a PC instead.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "bench"))

import damiao  # noqa: E402
import diag_client  # noqa: E402
import sysid_tests as st  # noqa: E402

LOG_DIR = Path.home() / "sysid_logs"
MAP_LIMIT = (1, 16)
G = 9.80665
# The host's clock for everything this does: pacing, and the `h` of every
# record. time.monotonic() is the same clock on Linux, but on Windows it ticks
# every 15.6 ms, which held a 1 kHz test to about 100 Hz.
clock = time.perf_counter
# How much of each interval is spun rather than slept. Linux wakes a sleeper
# within a fraction of a millisecond; Windows wakes it on its 15.6 ms tick,
# which sent commands in bursts of eight at 500 Hz until this spun instead.
SPIN_S = 0.017 if os.name == "nt" else 0.0005


def pace(until: float) -> None:
    """Back at `until`, by sleeping most of the way and spinning the rest."""
    wait = until - clock()
    if wait > SPIN_S:
        time.sleep(wait - SPIN_S)
    while clock() < until:
        pass


class LoggingRobot(diag_client.Robot):
    """diag_client's Robot, leaving every time on the controller's clock: the
    log keeps both clocks and puts them together afterwards."""

    def to_host(self, t: float) -> float:
        return t


class Rig:
    """The motors a test uses, and the log everything about them goes into."""

    def __init__(self, robot: LoggingRobot, wiring: dict[str, st.Wiring]):
        self.robot = robot
        self.wiring = wiring
        self.writer: st.LogWriter | None = None
        self.buses: dict[str, damiao.Bus] = {}
        self.motors: dict[str, damiao.Motor] = {}
        self.by_motor: dict[tuple[str, int], str] = {}
        self.latest: dict[str, st.Fb] = {}
        self.raw: dict[str, tuple] = {}
        self.imu: dict[str, tuple[float, list]] = {}
        self.stopped_by: str | None = None
        self.stopped_why: str | None = None
        self.counts = {"f": 0, "c": 0, "i": 0}
        for letter in sorted({w.bus for w in wiring.values()}):
            can = robot.can(letter)
            bus = damiao.Bus(can, letter)
            can.set_handler(lambda i, d, t, b=bus, n=letter: self._frame(b, n, i, d, t))
            self.buses[letter] = bus
        robot.on("imu", self._imu)
        robot.on("status", self._status)
        robot.on("log", self._log)
        robot.on("stopped", self._stopped)

    # -- what comes in --------------------------------------------------------------

    def _frame(self, bus: damiao.Bus, letter: str, can_id: int, d: bytes, t: float):
        h = clock()
        bus._dispatch(can_id, d, t)
        m = bus._motor_for_feedback(can_id, d[0] & 0x0F)
        if m is None or m.feedback is None or m.feedback.t != t:
            return
        joint = self.by_motor.get((letter, m.can_id))
        if joint is None:
            return
        fb = m.feedback
        self.raw[joint] = (h, fb.pos, fb.vel, fb.torque)
        w = self.wiring[joint]
        p, v, q = w.to_joint(fb.pos, fb.vel, fb.torque)
        self.latest[joint] = st.Fb(h, p, v, q, fb.state, fb.t_mos, fb.t_rotor)
        self.counts["f"] += 1
        if self.writer:
            self.writer.write(
                st.feedback_record(
                    t,
                    h,
                    joint,
                    fb.state,
                    fb.pos,
                    fb.vel,
                    fb.torque,
                    fb.t_mos,
                    fb.t_rotor,
                    d,
                )
            )

    def _imu(self, m: dict) -> None:
        h = clock()
        self.imu[m["report"]] = (h, m["v"])
        self.counts["i"] += 1
        if self.writer:
            self.writer.write(
                {
                    "k": "i",
                    "t": m["t"],
                    "h": round(h, 6),
                    "r": m["report"],
                    "v": m["v"],
                    "a": m.get("status"),
                }
            )

    def _status(self, m: dict) -> None:
        if self.writer:
            self.writer.write(
                {"k": "s", "t": m.get("t"), "h": round(clock(), 6), "status": m}
            )

    def _log(self, m: dict) -> None:
        if self.writer:
            self.writer.write(
                {
                    "k": "l",
                    "t": m.get("t"),
                    "h": round(clock(), 6),
                    "text": m.get("text"),
                }
            )

    def _stopped(self, m: dict) -> None:
        self.stopped_why = m.get("why")
        self.stopped_by = f"diagd or the controller stopped the motors ({m.get('why')})"

    # -- what goes out --------------------------------------------------------------

    def find(self, need_mit: bool = True) -> None:
        """Every motor the wiring names, with its registers read."""
        for joint, w in self.wiring.items():
            m = self.buses[w.bus].probe(w.id)
            if m is None:
                raise SystemExit(f"{joint}: nothing answers at bus {w.bus}, ID {w.id}")
            if need_mit and m.mode != damiao.MIT:
                raise SystemExit(
                    f"{joint} (bus {w.bus}, ID {w.id}) is in {damiao.MODE_NAMES.get(m.mode)} "
                    "mode. Set CTRL_MODE to MIT in the motor console and save it."
                )
            for name in (
                "PMAX",
                "VMAX",
                "TMAX",
                "KT_Value",
                "Gr",
                "MAX_SPD",
                "TIMEOUT",
                "UV_Value",
            ):
                if damiao.RID[name] not in m.registers:
                    value = self.buses[w.bus].read(w.id, damiao.RID[name])
                    if value is not None:
                        m.registers[damiao.RID[name]] = value
            self.motors[joint] = m
            self.by_motor[(w.bus, m.can_id)] = joint

    def registers(self) -> dict:
        out = {}
        for joint, m in self.motors.items():
            out[joint] = {
                r.name: m.registers[r.rid]
                for r in damiao.REGISTERS
                if r.rid in m.registers
            }
        return out

    def ask_status(self, joints) -> None:
        for j in joints:
            self.buses[self.wiring[j].bus].request_status(self.motors[j])

    def fresh(self, joints, within: float = 0.3) -> bool:
        now = clock()
        return all(
            j in self.latest and now - self.latest[j].at < within for j in joints
        )

    def wait_fresh(self, joints, timeout: float = 1.0) -> bool:
        deadline = clock() + timeout
        while clock() < deadline:
            self.ask_status(joints)
            time.sleep(0.02)
            if self.fresh(joints, 0.05):
                return True
        return False

    def send(self, joint: str, c: st.Cmd) -> None:
        m = self.wiring[joint].to_motor(c)
        h = clock()
        self.buses[self.wiring[joint].bus].mit(
            self.motors[joint], m.p, m.v, m.kp, m.kd, m.t
        )
        self.counts["c"] += 1
        if self.writer:
            self.writer.write(st.command_record(h, joint, m))

    def enable(self, joints) -> None:
        # A motor its TIMEOUT dropped sits in state 0xD until cleared, and will
        # not enable from there.
        for j in joints:
            self.buses[self.wiring[j].bus].clear_error(self.motors[j])
        time.sleep(0.01)
        for j in joints:
            self.buses[self.wiring[j].bus].enable(self.motors[j])

    def clear_fault(self, joint: str) -> None:
        """Out of a fault state, which enabling will not leave by itself."""
        self.buses[self.wiring[joint].bus].clear_error(self.motors[joint])

    def wake(self, joint: str) -> None:
        self.buses[self.wiring[joint].bus].enable(self.motors[joint])

    def disable(self, joints) -> None:
        for _ in range(3):
            for j in joints:
                self.buses[self.wiring[j].bus].disable(self.motors[j])
            time.sleep(0.005)

    def stop(self) -> None:
        self.robot.stop()


# ---- a test ----------------------------------------------------------------------


def commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(HERE.parent), "describe", "--always", "--dirty"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def log_path(args, test: str) -> Path:
    if args.out:
        return Path(args.out)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    label = f"_{args.label}" if args.label else ""
    return LOG_DIR / f"{stamp}_{test}{label}.jsonl"


def connect(args) -> LoggingRobot:
    streams = ("status", "log", "can", "imu")
    try:
        robot = LoggingRobot(args.robot, name="sysid", streams=streams)
    except diag_client.RobotError as error:
        raise SystemExit(str(error))
    try:
        robot.take_control()
    except diag_client.RobotError as error:
        robot.close()
        raise SystemExit(
            f"cannot take control: {error}. Close the motor console or the bench GUI first."
        )
    return robot


def wiring_for(test: st.Test, a, args) -> tuple[dict[str, st.Wiring], dict]:
    robot = st.load_robot()
    if test.fixture == "bench":
        bus, _, ident = (args.motor or "").partition(":")
        if not bus or not ident:
            raise SystemExit(
                "a bench test needs --motor BUS:ID, for instance --motor C:1"
            )
        return {st.BENCH: st.Wiring(bus.upper(), int(ident))}, robot
    if not robot["mapped"] and not args.assume_wiring:
        raise SystemExit(
            "the robot has not been mapped: run `sysid.py map` first, so that every "
            "command goes to the joint it is meant for and with the right sign."
        )
    joints = test.joints(a)
    return {j: robot["joints"][j] for j in joints}, robot


def run(args) -> int:
    test = st.TESTS[args.test]
    a = st.defaults(
        **{k: v for k, v in vars(args).items() if hasattr(st.defaults(), k)}
    )
    wiring, robot_file = wiring_for(test, a, args)
    joints = tuple(wiring)
    rate = args.hz or test.hz

    robot = connect(args)
    rig = Rig(robot, wiring)
    path = status_before = None
    try:
        rig.find()
        regs = rig.registers()
        a.vmax = min(float(r.get("VMAX", 50.0)) for r in regs.values())
        segments, limits = test.build(a)
        for j, cap in limits.speed.items():
            vmax = float(regs[j].get("VMAX", 0.0))
            if cap >= vmax and not args.force:
                raise SystemExit(
                    f"{j}: the test may reach {cap:g} rad/s and its VMAX is {vmax:g}, past "
                    "which a report's speed wraps round. Set VMAX to 55 first "
                    "(docs/POLICY_INTERFACE.md), or pass --force."
                )
        print(f"{test.key}  {test.title}\n\n{test.setup}\n")
        for j, w in wiring.items():
            r = regs[j]
            print(
                f"  {j:<18} bus {w.bus} ID {w.id}, sign {w.sign:+d}, zero {w.zero:+.3f}; "
                f"VMAX {r.get('VMAX')}, TMAX {r.get('TMAX')}, TIMEOUT {r.get('TIMEOUT')}"
            )
        if not args.yes:
            input("\nEnter to start, Ctrl-C to leave it. ")

        path = log_path(args, test.key)
        header = {
            "test": test.key,
            "title": test.title,
            "fixture": test.fixture,
            "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "host": socket.gethostname(),
            "commit": commit(),
            "args": {k: v for k, v in vars(a).items()},
            "hz": rate,
            "joints": {j: vars(w) for j, w in wiring.items()},
            "registers": regs,
            "controller": robot.info,
            "robot_file": robot_file.get("date") if robot_file.get("mapped") else None,
            "imu_axes": robot_file.get("imu_axes") if test.fixture != "bench" else None,
            "imu_gravity_sign": robot_file.get("imu_gravity_sign", 1),
            "load_inertia": a.load_inertia,
            "label": args.label,
        }
        rig.writer = st.LogWriter(path, header)
        status_before = diag_client.wait_for_status(robot)

        for report, hz in test.imu.items():
            try:
                robot.request("imu.enable", report=report, hz=hz)
            except diag_client.RobotError as error:
                print(f"  IMU {report} at {hz:g} Hz refused: {error}")
        if not rig.wait_fresh(joints):
            raise SystemExit("not every motor answered a status request")

        reason = play(rig, segments, limits, joints, rate)
    except KeyboardInterrupt:
        reason = "stopped: Ctrl-C"
    except SystemExit as why:
        # Refused before or while starting: say why, and still hand control back.
        reason = f"not run: {why}"
    finally:
        rig.stop()
        if rig.motors:
            rig.disable(list(rig.motors))
        time.sleep(0.1)
        for report in test.imu:
            try:
                robot.request("imu.enable", report=report, hz=0)
            except diag_client.RobotError:
                pass
    status_after = diag_client.wait_for_status(robot)
    try:
        robot.release_control()
    except diag_client.RobotError:
        pass
    robot.close()
    if rig.writer is None:
        print(reason)
        return 1
    rig.writer.close({"ended": reason, "counts": rig.counts})
    summary(rig, path, reason, status_before, status_after)
    return 0 if reason == "done" else 1


def play(rig: Rig, segments, limits, joints, rate: float) -> str:
    """The test, at its rate, on a thread of its own; this thread answers
    whatever the test asks the operator."""
    seq = st.Sequencer(segments, limits, joints)
    done = threading.Event()
    result = {"why": "done"}
    lock = threading.Lock()

    def loop():
        period = 1.0 / rate
        last: dict[str, st.Cmd] = {}
        rig.enable(joints)
        nxt = clock()
        late = 0
        try:
            while not done.is_set():
                now = clock()
                if rig.stopped_by:
                    raise st.Abort(rig.stopped_by)
                with lock:
                    cmds = seq.tick(now, dict(rig.latest))
                    events, seq.events = seq.events, []
                for e in events:
                    rig.writer.write({"k": "n", "h": round(now, 6), **e})
                    if "seg" in e and "answer" not in e:
                        if not seq.segments[e["i"]].quiet:
                            print(f"\n  {e['seg']}", flush=True)
                if cmds is None:
                    break
                for j, c in cmds.items():
                    rig.send(j, c)
                    last[j] = c
                # A motor the segment did not command is still enabled, and its
                # TIMEOUT (200 ms, since 2026-11-04) drops it if no command
                # reaches it; a status request does not count. So it is sent
                # again what it was last sent, which it would go on doing
                # anyway, or no torque at all if it has been sent nothing.
                for j in joints:
                    if j not in cmds:
                        rig.send(j, last.get(j, st.Cmd()))
                nxt += period
                if nxt - clock() < -5 * period:
                    late += 1
                    nxt = clock()
                pace(nxt)
            if late:
                rig.writer.write({"k": "n", "h": round(clock(), 6), "late": late})
        except st.Abort as why:
            rig.stop()
            result["why"] = f"stopped: {why}"
            rig.writer.write({"k": "x", "h": round(clock(), 6), "why": str(why)})
            print(f"\nSTOPPED: {why}", flush=True)
        except Exception as error:  # anything at all stops the motors
            rig.stop()
            result["why"] = f"stopped: {error!r}"
            rig.writer.write({"k": "x", "h": round(clock(), 6), "why": repr(error)})
            raise
        finally:
            done.set()

    worker = threading.Thread(target=loop, daemon=True)
    worker.start()
    coached = (None, 0.0)  # which segment was last coached, and when
    try:
        while not done.is_set():
            with lock:
                prompt = seq.prompt
                seg, start = seq.segment, seq.start
            if prompt:
                answer = input(f"\n{prompt} ")
                with lock:
                    seq.answer(answer.strip())
                continue
            if seg is not None and seg.coach is not None and start is not None:
                now = clock()
                if coached[0] is not seg or now - coached[1] >= seg.coach_s:
                    coached = (seg, now)
                    try:
                        say = seg.coach(now - start, dict(rig.latest))
                    except Exception as error:  # a coach never stops a test
                        say = f"({error!r})"
                    if say:
                        print(f"    {say}", flush=True)
            done.wait(0.05)
    except (KeyboardInterrupt, EOFError):
        done.set()
        rig.stop()
        worker.join(1.0)
        rig.writer.write({"k": "x", "h": round(clock(), 6), "why": "Ctrl-C"})
        return "stopped: Ctrl-C"
    worker.join()
    return result["why"]


def summary(rig: Rig, path: Path, reason: str, before, after) -> None:
    print(f"\n{reason}. {rig.writer.lines} lines in {path}")
    print(
        f"  {rig.counts['c']} commands sent, {rig.counts['f']} motor reports and "
        f"{rig.counts['i']} IMU reports heard"
    )
    if before and after:
        drops = []
        for key in ("dropped", "uart_errors", "crc_errors"):
            b, a = before["link"].get(key, 0), after["link"].get(key, 0)
            if a != b:
                drops.append(f"{a - b} {key.replace('_', ' ')} at the controller")
        for name, bus in after.get("buses", {}).items():
            was = before.get("buses", {}).get(name, {})
            for key in ("rx_drop", "queue_drop", "tx_fail"):
                if bus.get(key, 0) != was.get(key, 0):
                    drops.append(f"bus {name}: {bus[key] - was.get(key, 0)} {key}")
        print("  link: " + ("; ".join(drops) if drops else "nothing dropped"))


# ---- map -------------------------------------------------------------------------

MOVES = {
    "hip_pitch_right": "Swing the RIGHT thigh FORWARD by about 30 degrees",
    "knee_right": "Fold the RIGHT shin BACK, relative to its thigh, by about 30 degrees",
    "wheel_drive_right": "Roll the RIGHT wheel FORWARD by about a quarter turn",
    "hip_pitch_left": "Swing the LEFT thigh FORWARD by about 30 degrees",
    "knee_left": "Fold the LEFT shin BACK, relative to its thigh, by about 30 degrees",
    "wheel_drive_left": "Roll the LEFT wheel FORWARD by about a quarter turn",
}


def unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def mapping(args) -> int:
    robot = connect(args)
    found: dict[str, st.Wiring] = {}
    rig = None
    try:
        for letter in "ABC":
            bus = damiao.Bus(robot.can(letter), letter)
            for m in bus.scan(range(MAP_LIMIT[0], MAP_LIMIT[1] + 1)):
                found[f"{letter}{m.can_id}"] = st.Wiring(letter, m.can_id)
        if not found:
            raise SystemExit("no motor answered on any bus")
        print("motors found: " + ", ".join(sorted(found)))
        rig = Rig(robot, found)
        rig.find(need_mit=False)
        path = log_path(args, "map")
        rig.writer = st.LogWriter(
            path,
            {
                "test": "map",
                "title": "which motor is which",
                "fixture": "hung",
                "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "joints": {k: vars(w) for k, w in found.items()},
                "registers": rig.registers(),
                "controller": robot.info,
            },
        )
        for report, hz in (("accel", 100.0), ("gravity", 100.0), ("gyro", 200.0)):
            # diagd can say the IMU did not answer and the reports arrive
            # anyway, as on 2026-11-04; what arrives is what counts.
            try:
                robot.request("imu.enable", report=report, hz=hz)
            except diag_client.RobotError as error:
                print(f"  IMU {report}: {error}; carrying on")

        polling = threading.Event()
        spin = {"on": False, "sum": [0.0, 0.0, 0.0], "last": None}

        def poll():
            while not polling.is_set():
                rig.ask_status(list(found))
                time.sleep(0.05)

        def gyro(m):
            if m["report"] != "gyro" or not spin["on"]:
                return
            if spin["last"] is not None:
                dt = m["t"] - spin["last"]
                if 0 < dt < 0.1:
                    spin["sum"] = [s + w * dt for s, w in zip(spin["sum"], m["v"])]
            spin["last"] = m["t"]

        robot.on("imu", gyro)
        threading.Thread(target=poll, daemon=True).start()

        def snapshot():
            time.sleep(0.3)
            return {k: rig.raw[k][1] for k in found if k in rig.raw}

        input(
            "\nHang the robot from the rail, motors off. Let both legs hang straight "
            "down and still, torso level. Enter. "
        )
        rest = snapshot()
        accel0 = rig.imu.get("accel", (0, None))[1]
        gravity0 = rig.imu.get("gravity", (0, None))[1]
        joints: dict[str, st.Wiring] = {}
        for joint, words in MOVES.items():
            while True:
                before = snapshot()
                input(f"\n{words}, and hold it there. Enter. ")
                after = snapshot()
                moved = {k: after[k] - before[k] for k in after if k in before}
                key = max(moved, key=lambda k: abs(moved[k]))
                if abs(moved[key]) < 0.2:
                    print(
                        f"  nothing turned more than {abs(moved[key]):.2f} rad; again."
                    )
                    continue
                if key in {f"{w.bus}{w.id}" for w in joints.values()}:
                    print(f"  that was {key}, already taken; again.")
                    continue
                break
            w = found[key]
            sign = 1 if moved[key] > 0 else -1
            zero = rest.get(key, 0.0) if joint in st.LEGS else 0.0
            joints[joint] = st.Wiring(w.bus, w.id, sign, round(zero, 5))
            print(f"  {joint}: bus {w.bus} ID {w.id}, sign {sign:+d}, zero {zero:+.4f}")
            input("  Let it go back. Enter. ")

        axes, gravity_sign = None, 1
        if accel0 and gravity0:
            input("\nTorso level again, hanging still. Enter. ")
            accel0 = rig.imu["accel"][1]
            gravity0 = rig.imu["gravity"][1]
            spin["sum"], spin["last"], spin["on"] = [0.0, 0.0, 0.0], None, True
            input(
                "Now tip the whole robot NOSE-DOWN, front of the torso lower, by 20 to 30 degrees, and hold. Enter. "
            )
            spin["on"] = False
            turned = math.sqrt(dot(spin["sum"], spin["sum"]))
            if turned < 0.25:
                print(
                    f"  it turned only {math.degrees(turned):.0f} degrees; the IMU's axes are not set."
                )
            else:
                # Up is where the accelerometer pulls at rest; nose-down is a
                # positive turn about the torso's +Y (left), by the right-hand
                # rule, and the gyro measured that turn in its own axes.
                ez = unit(accel0)
                ey = unit(spin["sum"])
                ey = unit([e - dot(ey, ez) * z for e, z in zip(ey, ez)])
                ex = cross(ey, ez)
                axes = [[round(x, 5) for x in v] for v in (ex, ey, ez)]
                gravity_sign = -1 if dot(gravity0, ez) > 0 else 1
                print(
                    f"  IMU axes found, nose-down by {math.degrees(turned):.0f} degrees; its "
                    f"gravity report points {'UP' if gravity_sign < 0 else 'down'}"
                )
        else:
            print("\n  no accelerometer or gravity report: the IMU's axes are not set.")
        polling.set()

        out = {
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "joints": {j: vars(w) for j, w in joints.items()},
            "imu_axes": axes,
            "imu_gravity_sign": gravity_sign,
            "found": sorted(found),
        }
        st.ROBOT_FILE.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(f"\nwritten {st.ROBOT_FILE}")
        rig.writer.close({"ended": "done", "map": out})
        return 0
    except KeyboardInterrupt:
        print("\nleft; nothing written")
        return 1
    finally:
        robot.stop()
        for report in ("accel", "gravity", "gyro"):
            try:
                robot.request("imu.enable", report=report, hz=0)
            except diag_client.RobotError:
                pass
        try:
            robot.release_control()
        except diag_client.RobotError:
            pass
        robot.close()


# ---- level -----------------------------------------------------------------------

# How far a shin hanging off straight moves the place its thigh hangs still, as
# a share of the thigh's own angle: the lower leg's moment about the hip over the
# whole leg's. From the URDF on 2026-11-04 -- thigh link 221.6 g at 95.6 mm below
# the hip, shin link 213.6 g at 95.2 mm below the knee, wheel 91.6 g at the
# 105 mm axle -- 0.0300 over 0.0532 kg m.
SHIN_SHARE = 0.563

# Each leg joint settled twice, from either side. The joint friction holds a
# hanging leg anywhere in a band either side of straight down, which `map` found
# to be several degrees wide, so where it stops is the edge of that band; the
# middle of the two edges is straight down.
SETTLES = (
    (
        "hip_pitch",
        +1,
        "Push the {side} THIGH FORWARD by about 20 degrees, leaving the shin alone, "
        "then let it ease back by itself until it stops",
    ),
    (
        "hip_pitch",
        -1,
        "Now push the {side} THIGH BACK by about 20 degrees and let it ease forward "
        "by itself until it stops",
    ),
    (
        "knee",
        +1,
        "Fold the {side} SHIN BACK by about 20 degrees, leaving the thigh alone, "
        "then let it ease forward by itself until it stops",
    ),
    (
        "knee",
        -1,
        "Now push the {side} SHIN FORWARD, past straight, by about 15 degrees and "
        "let it ease back by itself until it stops",
    ),
)


def levelling(args) -> int:
    """Put right the two things `map` takes from a robot hanging as it hangs:
    the IMU's axes, against a level held on the shell, and each leg's zero."""
    if not st.ROBOT_FILE.exists():
        raise SystemExit("run `map` first: there is no sysid_robot.json")
    before = json.loads(st.ROBOT_FILE.read_text(encoding="utf-8"))
    wiring = {j: st.Wiring(**w) for j, w in before["joints"].items()}
    missing = [j for j in st.LEGS if j not in wiring]
    if missing:
        raise SystemExit(f"sysid_robot.json has no {', '.join(missing)}: run `map`")
    robot = connect(args)
    legs = {j: wiring[j] for j in st.LEGS}
    rig = None
    try:
        rig = Rig(robot, legs)
        rig.find(need_mit=False)
        path = log_path(args, "level")
        rig.writer = st.LogWriter(
            path,
            {
                "test": "level",
                "title": "the IMU against a level, and the legs' zeros",
                "fixture": "hung",
                "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "joints": {k: vars(w) for k, w in legs.items()},
                "map": before,
                "controller": robot.info,
            },
        )
        try:
            robot.request("imu.enable", report="accel", hz=100.0)
        except diag_client.RobotError as error:
            print(f"  IMU accel: {error}; carrying on")

        polling = threading.Event()
        # How far each motor has gone either way since its entry was last set
        # to None.
        travel: dict[str, list[float] | None] = {}

        def poll():
            while not polling.is_set():
                rig.ask_status(list(legs))
                for j, row in list(rig.raw.items()):
                    span = travel.get(j)
                    if span is None:
                        travel[j] = [row[1], row[1]]
                    else:
                        span[0], span[1] = min(span[0], row[1]), max(span[1], row[1])
                time.sleep(0.02)

        threading.Thread(target=poll, daemon=True).start()
        samples: list[list[float]] = []
        # The gravity report beside the accelerometer, whose length is what diagd
        # holds the robot standing still to from now on: the accelerometer's
        # zero-g offset is the up these axes rest on, and when the IMU's own
        # calibration moved it on 2026-11-05 the length stepped by 0.2 m/s2.
        gravities: list[list[float]] = []
        lengths: list[float] = []
        grab = {"on": False}

        def on_imu(m):
            if not grab["on"]:
                return
            if m["report"] == "accel":
                samples.append(m["v"])
            elif m["report"] == "gravity":
                gravities.append(m["v"])

        robot.on("imu", on_imu)

        def still(
            span: float, wobble: float, legs_too: bool
        ) -> tuple[list[float], dict] | None:
            """The accelerometer's mean and each leg motor's position over span
            seconds, once nothing moves; None if it never stops within 6 s."""
            deadline = clock() + 6.0
            while clock() < deadline:
                samples.clear()
                gravities.clear()
                spots: dict[str, list[float]] = {j: [] for j in legs}
                grab["on"] = True
                end = clock() + span
                while clock() < end:
                    for j in legs:
                        if j in rig.raw:
                            spots[j].append(rig.raw[j][1])
                    time.sleep(0.02)
                grab["on"] = False
                rows = list(samples)
                if len(rows) < 10 or any(len(s) < 5 for s in spots.values()):
                    raise SystemExit("the IMU or a motor has gone quiet")
                m = mean_vec(rows)
                spread = max(
                    math.sqrt(sum((r[i] - m[i]) ** 2 for r in rows) / len(rows))
                    for i in range(3)
                )
                drift = max(max(s) - min(s) for s in spots.values())
                if spread < wobble and (drift < 0.004 or not legs_too):
                    if gravities:
                        lengths.append(
                            math.sqrt(sum(c * c for c in mean_vec(gravities)))
                        )
                    return m, {j: sum(s) / len(s) for j, s in spots.items()}
            return None

        def capture(prompt: str, span: float, wobble: float, legs_too: bool = True):
            while True:
                input(prompt)
                got = still(span, wobble, legs_too)
                if got:
                    return got
                print("  still moving; again.")

        def turned(a, b) -> float:
            """Degrees between two of the torso's axes as the IMU sees them."""
            return math.degrees(math.acos(max(-1.0, min(1.0, dot(a, b)))))

        def reading(prompt: str) -> float:
            while True:
                text = input(prompt).strip()
                if not text:
                    return 0.0
                try:
                    return float(text)
                except ValueError:
                    print("  a number, please, or Enter for none")

        def off_square(v) -> float:
            """How far v is from the nearest of the IMU's own axes, in degrees."""
            return math.degrees(math.acos(min(1.0, max(abs(c) for c in v))))

        if args.legs:
            if not before.get("imu_axes"):
                raise SystemExit("--legs keeps the IMU's axes, and the file has none")
            ex, ey, ez = before["imu_axes"]
            axes = before["imu_axes"]
            imu_record = {"imu": "kept from the file", "imu_axes": axes}
            print("\nThe IMU's axes are kept as the file has them.")
        else:
            lengths.clear()
            ex, ey, ez, axes, imu_record = level_imu(capture, reading)
            print(
                f"  IMU axes set. The phone's own error was {imu_record['phone_error_deg']:.1f} "
                f"degrees. The torso's up is {off_square(ez):.1f} degrees off the IMU's "
                f"nearest axis, and its forward {off_square(ex):.1f}."
            )
            if before.get("imu_axes"):
                was = before["imu_axes"]
                imu_record["up_moved_deg"] = round(turned(was[2], ez), 2)
                print(
                    f"  Its up has moved {imu_record['up_moved_deg']:.1f} degrees from "
                    f"the file's, and its forward {turned(was[0], ex):.1f}."
                )
            # level_imu's first two captures are the level ones, phone either way round.
            if len(lengths) >= 2:
                imu_record["gravity_m_s2"] = round(sum(lengths[:2]) / 2, 3)
                print(
                    f"  Gravity reads {imu_record['gravity_m_s2']:.3f} m/s2 long level; "
                    "diagd says so if that moves."
                )
            else:
                print(
                    "  No gravity report came: diagd will have no length to hold it to."
                )
        imu_record["imu_up_off_square_deg"] = round(off_square(ez), 2)
        imu_record["imu_forward_off_square_deg"] = round(off_square(ex), 2)

        def pitch(a) -> float:
            """The torso's nose-down pitch, from the accelerometer in its axes."""
            return torso_pitch(axes, a)

        if args.imu:
            polling.set()
            out = dict(before)
            out["map"] = before.get(
                "map", {"joints": before["joints"], "imu_axes": before.get("imu_axes")}
            )
            out["imu_axes"] = axes
            out["imu_axes_from"] = (
                f"`level --imu` {datetime.now(timezone.utc).isoformat(timespec='seconds')}: "
                "up with the shell level by a phone read both ways round, forward from a "
                "nose-down tip, accelerometer only"
            )
            out["imu_level"] = imu_record
            if "gravity_m_s2" in imu_record:
                out["imu_gravity_m_s2"] = imu_record["gravity_m_s2"]
            st.ROBOT_FILE.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
            print(
                f"\nwritten {st.ROBOT_FILE}: the IMU's axes only; the legs' zeros kept"
            )
            rig.writer.close({"ended": "done", "level": out})
            return 0

        # -- the legs ----------------------------------------------------------
        print(
            "\nNow the legs, one joint at a time. Let go of the torso and let it hang "
            "for these; each one asks for a joint to be pushed and let go."
        )
        caught: dict[tuple[str, str, int], dict] = {}
        for side, word in (("right", "RIGHT"), ("left", "LEFT")):
            for part, direction, words in SETTLES:
                joint = f"{part}_{side}"
                w = legs[joint]
                while True:
                    travel[joint] = None
                    accel, at = capture(
                        f"\n{words.format(side=word)}. Enter. ", 0.6, 0.05
                    )
                    lo, hi = travel.get(joint) or [at[joint], at[joint]]
                    pushed = max(w.sign * (r - at[joint]) * direction for r in (lo, hi))
                    if pushed > math.radians(8):
                        break
                    print(
                        f"  it went only {math.degrees(pushed):.0f} degrees that way first; again."
                    )
                caught[(side, part, direction)] = {
                    "side": side,
                    "part": part,
                    "from": direction,
                    "hip": round(at[f"hip_pitch_{side}"], 5),
                    "knee": round(at[f"knee_{side}"], 5),
                    # Kept as read, so the zeros can be worked again from these
                    # with better IMU axes (leg_zeros).
                    "accel": [round(x, 4) for x in unit(accel)],
                }
                rig.writer.write(
                    {
                        "k": "n",
                        "h": round(clock(), 6),
                        "settled": joint,
                        **caught[(side, part, direction)],
                    }
                )
        polling.set()

        captures = list(caught.values())
        zeros, bands = leg_zeros(captures, legs, axes)
        hanging = [pitch(c["accel"]) for c in captures]
        print(
            f"\nThe torso hangs {math.degrees(sum(hanging) / len(hanging)):+.1f} degrees "
            "nose-down on the rail, legs straight."
        )
        print("  joint               zero was   zero now   moved    friction band")
        for j in st.LEGS:
            old = wiring[j].zero
            print(
                f"  {j:<18} {old:+9.4f}  {zeros[j]:+9.4f}  {math.degrees(zeros[j] - old):+5.1f} deg"
                f"   +/-{abs(math.degrees(bands[j])):.1f} deg"
            )

        out = dict(before)
        out["map"] = before.get(
            "map", {"joints": before["joints"], "imu_axes": before.get("imu_axes")}
        )
        out["joints"] = {
            j: {**before["joints"][j], "zero": round(zeros[j], 5)} if j in zeros else w
            for j, w in before["joints"].items()
        }
        out["imu_axes"] = axes
        if "gravity_m_s2" in imu_record:
            out["imu_gravity_m_s2"] = imu_record["gravity_m_s2"]
        out["level"] = {
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **imu_record,
            "hanging_pitch_deg": round(math.degrees(sum(hanging) / len(hanging)), 2),
            "friction_band_deg": {
                j: round(abs(math.degrees(b)), 2) for j, b in bands.items()
            },
            "shin_share": SHIN_SHARE,
            "captures": captures,
        }
        st.ROBOT_FILE.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(f'\nwritten {st.ROBOT_FILE}; what `map` found is kept in it under "map"')
        rig.writer.close({"ended": "done", "level": out})
        return 0
    except KeyboardInterrupt:
        print("\nleft; nothing written")
        return 1
    finally:
        robot.stop()
        try:
            robot.request("imu.enable", report="accel", hz=0)
        except diag_client.RobotError:
            pass
        try:
            robot.release_control()
        except diag_client.RobotError:
            pass
        robot.close()


def torso_pitch(axes, a) -> float:
    """The torso's nose-down pitch from an accelerometer reading at rest, which
    points up, given the torso's axes in the IMU's (`imu_axes`, by row)."""
    b = [dot(row, a) for row in axes]
    return math.atan2(-b[0], b[2])


def leg_zeros(captures, legs, axes) -> tuple[dict, dict]:
    """Each leg joint's zero, and the half-width of its friction band, from the
    four places `level` let that leg settle.

    Thigh angle a = sh (hip - zh) - pitch and shin angle b = a - sk (knee - zk),
    each from straight down, forward positive. The thigh rests where the whole
    leg's moment about the hip, a + SHIN_SHARE b, is at either edge of its band,
    and the shin where b is. Both pairs' sums are zero, which is linear in the
    two zeros."""
    by = {(c["side"], c["part"], c["from"]): c for c in captures}
    zeros, bands = {}, {}
    for side in ("right", "left"):
        wh, wk = legs[f"hip_pitch_{side}"], legs[f"knee_{side}"]

        def parts(c):
            a_ = wh.sign * c["hip"] - torso_pitch(axes, c["accel"])
            return a_, a_ - wk.sign * c["knee"]

        hips = [parts(by[(side, "hip_pitch", d)]) for d in (1, -1)]
        knees = [parts(by[(side, "knee", d)]) for d in (1, -1)]
        sum_a = sum(a_ for a_, _ in hips)
        sum_b_hip = sum(b_ for _, b_ in hips)
        sum_b_knee = sum(b_ for _, b_ in knees)
        h = (sum_a + SHIN_SHARE * (sum_b_hip - sum_b_knee)) / 2
        k = h - sum_b_knee / 2
        zeros[f"hip_pitch_{side}"] = wh.sign * h
        zeros[f"knee_{side}"] = wk.sign * k
        bands[f"hip_pitch_{side}"] = (
            (hips[0][0] - hips[1][0]) + SHIN_SHARE * (hips[0][1] - hips[1][1])
        ) / (2 * (1 + SHIN_SHARE))
        bands[f"knee_{side}"] = (knees[1][1] - knees[0][1]) / 2
    return zeros, bands


def level_imu(capture, reading):
    """The IMU's axes against a phone's level held on the shell, read both ways
    round, and the robot tipped nose-down on the rail."""
    print(
        "\nThe IMU first. You will need the level app on the phone, and a hand on "
        "the torso to hold it where the phone says."
    )
    ups, rolls = [], []
    for turn in ("", " again, with the phone turned END FOR END on the same spot"):
        accel, _ = capture(
            f"\nPhone on the shell top, long side nose to tail{turn}. Hold or prop the "
            "torso so the phone reads 0.0 nose to tail, and keep it still. Enter. ",
            1.0,
            0.25,
            legs_too=False,
        )
        ups.append(unit(accel))
        rolls.append(
            reading(
                "  What does it read side to side? A plain number if the robot's LEFT "
                "side is the higher, with a minus if its RIGHT side is; Enter if under 0.2. "
            )
        )
    # Turned end for end, the phone's own error changes sign, so the mean of
    # the two is level whatever the phone's camera bump does.
    u0 = unit(mean_vec(ups))
    roll = math.radians(sum(rolls) / len(rolls))
    phone = math.degrees(math.acos(max(-1.0, min(1.0, dot(*ups))))) / 2
    while True:
        accel, _ = capture(
            "\nNow tip the torso NOSE-DOWN by 20 to 30 degrees, turning it only about "
            "its side-to-side axis, so the phone's side-to-side reading stays as it "
            "was, and hold it there still. Enter. ",
            1.0,
            0.25,
            legs_too=False,
        )
        u1 = unit(accel)
        tipped = math.acos(max(-1.0, min(1.0, dot(u0, u1))))
        if tipped > math.radians(12):
            break
        print(f"  only {math.degrees(tipped):.0f} degrees; again.")
    # Nose-down is a turn about the torso's +Y. Gravity turns the other way in
    # the IMU's axes, so the axis is u1 x u0. This is the accelerometer alone: a
    # gyro integral, which `map` used, also takes in the robot turning on the
    # rail as it is tipped, which on 2026-11-04 put 10 degrees into the forward
    # axis.
    ey = unit(cross(u1, u0))
    ey = unit([e - dot(ey, u0) * u for e, u in zip(ey, u0)])
    ez = u0
    # The torso was held level nose to tail but stood at `roll` side to side,
    # LEFT side up, which is a turn about +X.
    ey, ez = (
        [math.cos(roll) * a + math.sin(roll) * b for a, b in zip(ey, ez)],
        [-math.sin(roll) * a + math.cos(roll) * b for a, b in zip(ey, ez)],
    )
    ex = cross(ey, ez)
    axes = [[round(x, 5) for x in v] for v in (ex, ey, ez)]
    record = {
        "phone_error_deg": round(phone, 2),
        "roll_deg": round(math.degrees(roll), 2),
        "tipped_deg": round(math.degrees(tipped), 1),
    }
    return ex, ey, ez, axes, record


def mean_vec(rows):
    return [sum(c) / len(rows) for c in zip(*rows)]


# ---- the command line ------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("test", help="list, map, or a test: " + ", ".join(st.TESTS))
    ap.add_argument(
        "--robot", default=os.environ.get("BIPEDAL_ROBOT", diag_client.DEFAULT_ROBOT)
    )
    ap.add_argument("--motor", help="the bench motor, BUS:ID")
    ap.add_argument("--out", help="the log's path")
    ap.add_argument(
        "--label", default="", help="added to the log's name, and kept in it"
    )
    ap.add_argument("--hz", type=float, help="the command rate, over the test's own")
    ap.add_argument("--yes", action="store_true", help="start without asking")
    ap.add_argument(
        "--legs",
        action="store_true",
        help="level: the legs' zeros only, keeping the file's IMU axes",
    )
    ap.add_argument(
        "--imu",
        action="store_true",
        help="level: the IMU's axes only, keeping the file's zeros; off the rail",
    )
    ap.add_argument("--force", action="store_true", help="run though VMAX is low")
    ap.add_argument(
        "--assume-wiring",
        action="store_true",
        help="run a robot test with the assumed wiring, before `map`: on your head be it",
    )
    for name, value in vars(st.defaults()).items():
        if name == "vmax":
            continue
        flag = "--" + name.replace("_", "-")
        if isinstance(value, bool):
            ap.add_argument(flag, action="store_true")
        elif isinstance(value, (int, float)):
            ap.add_argument(flag, type=type(value), default=value)
        else:
            ap.add_argument(flag, default=value)
    args = ap.parse_args(argv)

    if args.test == "list":
        for t in st.TESTS.values():
            print(f"{t.key}  {t.title}  [{t.fixture}, {t.hz:g} Hz]  {t.options}")
            print(f"    {t.setup}")
        return 0
    if args.test == "map":
        return mapping(args)
    if args.test == "level":
        return levelling(args)
    if args.test not in st.TESTS:
        ap.error(f"no test {args.test}")
    return run(args)


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    sys.exit(main())
