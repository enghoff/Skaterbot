# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""What a system-identification run does to the motors, step by step, and the file it leaves.

docs/SYSID.md is the plan this serves. Each test is a list of segments: a few
seconds of commands, each joint's command a function of the time into the
segment and of what the motors last reported. sbc/sysid.py plays them on the
robot through diagd, and simulation/sysid/synth.py plays the very same lists
against a model, so a test means the same inputs wherever it runs and a fit can
be checked on data whose answer is known.

Everything here is in the JOINT's frame -- the URDF's angles and signs, which are
the policy's (docs/POLICY_INTERFACE.md) -- and in MIT mode's five numbers:
target position and speed, stiffness, damping and feed-forward torque. Wiring
turns that into one motor's own frame. The log records what the motor itself
was sent and said, in its own frame, with the wiring in the header, so a wiring
found wrong later corrects the reading rather than the run.

Only the standard library: it runs on the Banana Pi as it is.
"""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

FORMAT = 1

LEGS = ("hip_pitch_right", "knee_right", "hip_pitch_left", "knee_left")
WHEELS = ("wheel_drive_right", "wheel_drive_left")
JOINTS = LEGS + WHEELS
# The one motor on the bench, whatever joint it will become.
BENCH = "bench"

# The crouch every policy was trained from, and the gains a balance policy holds
# its legs at (docs/POLICY_INTERFACE.md).
CROUCH = {
    "hip_pitch_right": 0.25,
    "knee_right": 0.50,
    "hip_pitch_left": 0.25,
    "knee_left": 0.50,
}
HOLD_KP, HOLD_KD = 12.0, 0.4

# Where a leg may go while a test runs before the test is stopped: inside the
# hip's provisional +/-1.047 and the knee's 1.745 stop, with room to stop. A leg
# hanging free is straight, knee at zero, which is where every hanging test
# starts from, so the knee's window reaches past it for a zero that is off and
# a shin the joint's friction holds forward of straight: on the robot on
# 2026-11-04 a shin let go 15 degrees forward stayed there. The owner's limit
# that way is 90 degrees, past which the shin pulls on its leads.
WINDOWS = {
    "hip_pitch_right": (-0.7, 0.9),
    "hip_pitch_left": (-0.7, 0.9),
    "knee_right": (-0.35, 1.55),
    "knee_left": (-0.35, 1.55),
}
LEG_SPEED_CAP = 15.0
PEAK_NM = 3.0

ROBOT_FILE = Path(__file__).with_name("sysid_robot.json")


# ---- commands, feedback and the wiring between them -------------------------


@dataclass(frozen=True)
class Cmd:
    """One MIT-mode command: torque = kp (p - pos) + kd (v - vel) + t."""

    p: float = 0.0
    v: float = 0.0
    kp: float = 0.0
    kd: float = 0.0
    t: float = 0.0


@dataclass(frozen=True)
class Fb:
    """A motor's last report, in the joint's frame. `at` is when it was heard,
    on whichever clock the caller runs the sequence on."""

    at: float
    p: float
    v: float
    tau: float
    state: int = 1
    t_mos: int = 0
    t_rotor: int = 0


@dataclass(frozen=True)
class Wiring:
    """Which motor a joint is, and how its frame sits on the joint's:
    motor angle = sign x joint angle + zero."""

    bus: str
    id: int
    sign: int = 1
    zero: float = 0.0

    def to_motor(self, c: Cmd) -> Cmd:
        s = self.sign
        return Cmd(s * c.p + self.zero, s * c.v, c.kp, c.kd, s * c.t)

    def to_joint(self, p: float, v: float, tau: float) -> tuple[float, float, float]:
        s = self.sign
        return s * (p - self.zero), s * v, s * tau


# Until sbc/sysid.py's `map` has been run on the robot: the IDs a scan found on
# 2026-11-04, one pair to a bus as docs/DIAGNOSTICS.md lays them out, and a
# guess at which of each pair is which side.
ASSUMED = {
    "hip_pitch_right": Wiring("A", 1),
    "hip_pitch_left": Wiring("A", 2),
    "knee_right": Wiring("B", 3),
    "knee_left": Wiring("B", 4),
    "wheel_drive_right": Wiring("C", 5),
    "wheel_drive_left": Wiring("C", 6),
}


def load_robot(path: Path = ROBOT_FILE) -> dict:
    """The wiring and IMU axes `map` found, or the assumed wiring, marked so."""
    if not path.exists():
        return {"mapped": False, "joints": dict(ASSUMED), "imu_axes": None}
    raw = json.loads(path.read_text(encoding="utf-8"))
    joints = {name: Wiring(**w) for name, w in raw["joints"].items()}
    return {
        "mapped": True,
        "joints": joints,
        "imu_axes": raw.get("imu_axes"),
        # Which way the gravity report points, as `map` found it. Dropped here
        # until 2026-11-04, so every log before then says 1 where the robot's
        # map says -1, and a fit read its torso as hanging upside down.
        "imu_gravity_sign": raw.get("imu_gravity_sign", 1),
        "imu_report": raw.get("imu_report", "gravity"),
        "date": raw.get("date"),
    }


# ---- waveforms ---------------------------------------------------------------


def min_jerk(s: float) -> float:
    """0 to 1 over s = 0 to 1, starting and ending at rest."""
    s = min(max(s, 0.0), 1.0)
    return s * s * s * (10.0 - 15.0 * s + 6.0 * s * s)


def chirp(t: float, f0: float, f1: float, span: float, fade: float = 0.5) -> float:
    """A logarithmic sweep from f0 to f1 Hz over span seconds, unit amplitude,
    faded in and out so it starts and ends at rest."""
    if t <= 0.0 or t >= span:
        return 0.0
    k = math.log(f1 / f0) / span
    phase = 2.0 * math.pi * f0 * (math.exp(k * t) - 1.0) / k
    edge = min(t, span - t)
    gain = 0.5 - 0.5 * math.cos(math.pi * edge / fade) if edge < fade else 1.0
    return gain * math.sin(phase)


# ---- segments, tests and the sequence that runs them --------------------------

CmdFn = Callable[[float, dict], Cmd]


@dataclass
class Segment:
    """A stretch of a test. It ends when `until` says so, after `duration`
    seconds at the most; or, if it asks the operator something, when they have
    answered, and their answer goes into the log under `answer`. A `coach`, given
    the time into the segment and the latest reports, says what the person doing
    the test should do now; the runner prints it every `coach_s`."""

    name: str
    commands: dict[str, CmdFn]
    duration: float | None = None
    until: Callable[[float, dict], bool] | None = None
    prompt: str | None = None
    answer: str | None = None
    coach: Callable[[float, dict], str | None] | None = None
    coach_s: float = 1.0
    quiet: bool = False  # not announced as it starts

    def __post_init__(self):
        if self.prompt is None and self.duration is None:
            raise ValueError(f"segment {self.name} has no end")


@dataclass
class Limits:
    """What stops a test outright. Speeds are per joint, in rad/s; a leg out of
    its window, a winding past hot_c or a motor in a fault state stops it too,
    and so does a motor that has said nothing for stale_s."""

    speed: dict[str, float]
    windows: dict[str, tuple[float, float]] = field(default_factory=dict)
    torque: float = PEAK_NM
    hot_c: int = 90
    stale_s: float = 0.1


@dataclass
class Test:
    key: str
    title: str
    fixture: str  # "bench", "hung" or "floor"
    setup: str
    hz: float
    build: Callable[[SimpleNamespace], tuple[list[Segment], Limits]]
    joints: Callable[[SimpleNamespace], tuple[str, ...]]
    imu: dict[str, float] = field(default_factory=dict)
    options: str = ""


class Abort(Exception):
    pass


class Sequencer:
    """Steps through a test's segments. Call tick(now, feedback) at the test's
    rate; it gives the command for every joint, or None once the test is over,
    and raises Abort if a limit is crossed. What it did -- each segment's start
    and every answer -- collects in `events` for the caller to log."""

    def __init__(self, segments: list[Segment], limits: Limits, joints):
        self.segments = segments
        self.limits = limits
        self.joints = tuple(joints)
        self.i = 0
        self.start: float | None = None
        self.answered: str | None = None
        self.events: list[dict] = []

    @property
    def done(self) -> bool:
        return self.i >= len(self.segments)

    @property
    def segment(self) -> Segment | None:
        return None if self.done else self.segments[self.i]

    @property
    def prompt(self) -> str | None:
        seg = self.segment
        if seg is None or seg.prompt is None or self.start is None:
            return None
        return seg.prompt if self.answered is None else None

    def answer(self, text: str) -> None:
        self.answered = text

    def check(self, now: float, fb: dict[str, Fb]) -> None:
        lim = self.limits
        for j in self.joints:
            f = fb.get(j)
            if f is None or now - f.at > lim.stale_s:
                raise Abort(f"{j}: no report for {lim.stale_s * 1000:.0f} ms")
            if f.state >= 0x8:
                raise Abort(f"{j}: motor fault, state {f.state:X}")
            if f.t_rotor >= lim.hot_c:
                raise Abort(f"{j}: winding at {f.t_rotor} C")
            cap = lim.speed.get(j)
            if cap is not None and abs(f.v) > cap:
                raise Abort(f"{j}: {f.v:+.1f} rad/s, past the {cap:g} cap")
            window = lim.windows.get(j)
            if window and not window[0] <= f.p <= window[1]:
                raise Abort(f"{j}: at {f.p:+.3f} rad, outside {window}")

    def tick(self, now: float, fb: dict[str, Fb]) -> dict[str, Cmd] | None:
        self.check(now, fb)
        while not self.done:
            seg = self.segments[self.i]
            if self.start is None:
                self.start, self.answered = now, None
                self.events.append({"seg": seg.name, "i": self.i})
            t = now - self.start
            if seg.prompt is not None:
                over = self.answered is not None
            else:
                over = t >= seg.duration or (seg.until is not None and seg.until(t, fb))
            if over:
                if seg.prompt is not None:
                    self.events.append(
                        {"answer": seg.answer, "value": self.answered, "seg": seg.name}
                    )
                self.i += 1
                self.start = None
                continue
            return {j: self._clip(f(t, fb)) for j, f in seg.commands.items()}
        return None

    def _clip(self, c: Cmd) -> Cmd:
        cap = self.limits.torque
        return Cmd(c.p, c.v, c.kp, c.kd, min(max(c.t, -cap), cap))


# ---- building blocks -----------------------------------------------------------


def const(c: Cmd) -> CmdFn:
    return lambda t, fb: c


def ramp_torque(a: float, b: float, span: float, kd: float = 0.0) -> CmdFn:
    return lambda t, fb: Cmd(kd=kd, t=a + (b - a) * min(t / span, 1.0))


def brake(kd: float) -> CmdFn:
    """Hold speed at zero by damping alone."""
    return const(Cmd(kd=kd))


def ease(joint: str, target: float, span: float, kp: float, kd: float) -> CmdFn:
    """From wherever the joint is when the segment starts to target, gently."""
    start: list[float] = []

    def f(t: float, fb: dict) -> Cmd:
        if not start:
            start.append(fb[joint].p if joint in fb else target)
        p = start[0] + (target - start[0]) * min_jerk(t / span)
        return Cmd(p=p, kp=kp, kd=kd)

    return f


def hold(joint: str, kp: float = HOLD_KP, kd: float = HOLD_KD) -> CmdFn:
    return const(Cmd(p=CROUCH[joint], kp=kp, kd=kd))


def hold_here(joint: str, kp: float, kd: float) -> CmdFn:
    """Hold wherever the joint was when the segment started."""
    here: list[float] = []

    def f(t: float, fb: dict) -> Cmd:
        if not here:
            here.append(fb[joint].p if joint in fb else 0.0)
        return Cmd(p=here[0], kp=kp, kd=kd)

    return f


def bang_bang(joint: str, torque: float, switch: float, cycles: int, sign=1.0):
    """Full torque one way until the joint passes switch rad/s, then the other
    way until it passes -switch: accelerations at every speed, both ways.
    sign -1 starts the other way. Returns the command and the test for having
    done `cycles` of it."""
    state = {"dir": 1.0, "flips": 0}

    def f(t: float, fb: dict) -> Cmd:
        v = sign * (fb[joint].v if joint in fb else 0.0)
        if state["dir"] > 0 and v > switch:
            state["dir"], state["flips"] = -1.0, state["flips"] + 1
        elif state["dir"] < 0 and v < -switch:
            state["dir"], state["flips"] = 1.0, state["flips"] + 1
        return Cmd(t=sign * state["dir"] * torque)

    # Done, or given up: a torque under the friction never reaches the switch.
    return f, (
        lambda t, fb: state["flips"] >= 2 * cycles or (t > 3.0 and not state["flips"])
    )


def nudge(joint: str, by: float, span: float, kp: float, kd: float) -> CmdFn:
    """From wherever the joint is when the segment starts, by `by`, gently,
    and held there."""
    start: list[float] = []

    def f(t: float, fb: dict) -> Cmd:
        if not start:
            start.append(fb[joint].p if joint in fb else 0.0)
        return Cmd(p=start[0] + by * min_jerk(t / span), kp=kp, kd=kd)

    return f


def stopped(joint: str, below: float = 0.5) -> Callable[[float, dict], bool]:
    return lambda t, fb: joint in fb and abs(fb[joint].v) < below and t > 0.2


def legs_hold(legs, kp=HOLD_KP, kd=HOLD_KD, skip=()) -> dict[str, CmdFn]:
    return {j: hold(j, kp, kd) for j in legs if j not in skip}


def legs_ease(legs, span: float = 3.0) -> dict[str, CmdFn]:
    return {j: ease(j, CROUCH[j], span, 6.0, 0.3) for j in legs}


def legs_release(legs, span: float = 2.0) -> dict[str, CmdFn]:
    """Let the legs down: stiffness to nothing, damping kept, so they sink."""
    return {
        j: (
            lambda j: (
                lambda t, fb: Cmd(
                    p=CROUCH[j], kp=HOLD_KP * (1.0 - min(t / span, 1.0)), kd=0.3
                )
            )
        )(j)
        for j in legs
    }


def floats(text: str | None, default: list[float]) -> list[float]:
    if not text:
        return default
    return [float(x) for x in str(text).split(",") if x.strip()]


# ---- the tests -----------------------------------------------------------------
#
# Stage A is one motor on the bench, clamped, its output either bare or carrying
# an arm or a disc whose inertia is known. Stage B is the whole robot hanging
# from the rail by its hoist lugs, wheels clear of everything. Stage C is on the
# floor. docs/SYSID.md says what each is for and how to set it up.


def _a1(a):
    sign = -1.0 if a.negative else 1.0
    levels = floats(a.torques, [0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    segs = [
        Segment(
            "tare",
            {BENCH: const(Cmd())},
            prompt="Arm resting on the scale, no torque. Tare the scale, then Enter.",
        )
    ]
    last = 0.0
    for tau in levels:
        tau *= sign
        segs.append(
            Segment(f"ramp {tau:+.2f}", {BENCH: ramp_torque(last, tau, 0.5)}, 0.5)
        )
        segs.append(
            Segment(
                f"hold {tau:+.2f}",
                {BENCH: const(Cmd(t=tau))},
                prompt=f"Holding {tau:+.2f} Nm. Scale reading, grams?",
                answer="scale_g",
            )
        )
        last = tau
    segs.append(Segment("release", {BENCH: ramp_torque(last, 0.0, 0.5)}, 0.5))
    return segs, Limits(speed={BENCH: 3.0})


def _a2(a):
    loaded = a.load_inertia > 0
    torques = floats(a.torques, [0.3, 0.6, 1.2] if loaded else [0.06, 0.12, 0.25])
    switch = a.vswitch
    speeds = floats(a.speeds, [0.5, 1, 2, 4, 8, 16, 30, -0.5, -1, -2, -4, -8, -16, -30])
    speeds = [v for v in speeds if abs(v) <= switch + 10.0]
    kd = a.kd_sweep
    segs = [Segment("settle", {BENCH: brake(0.2)}, 1.0)]
    for tau in torques:
        f, done = bang_bang(BENCH, tau, switch, a.cycles)
        segs.append(Segment(f"bang {tau:.3f}", {BENCH: f}, 20.0, until=done))
        segs.append(Segment("brake", {BENCH: brake(0.3)}, 3.0, until=stopped(BENCH)))
    previous = 0.0
    for v in speeds:
        segs.append(
            Segment(
                f"to {v:+g}",
                {
                    BENCH: (
                        lambda a0, b0: (
                            lambda t, fb: Cmd(v=a0 + (b0 - a0) * min_jerk(t), kd=kd)
                        )
                    )(previous, v)
                },
                1.0,
            )
        )
        segs.append(Segment(f"speed {v:+g}", {BENCH: const(Cmd(v=v, kd=kd))}, 2.5))
        previous = v
    segs.append(Segment("stop", {BENCH: brake(0.3)}, 3.0, until=stopped(BENCH)))
    return segs, Limits(speed={BENCH: switch + 15.0})


def _a3(a):
    if a.load_inertia <= 0:
        raise ValueError(
            "A3 needs a disc of known inertia on the output: --load-inertia"
        )
    top = min(0.95 * a.vmax, 52.0)
    full = a.full_torque
    segs = [
        Segment(
            "pack",
            {BENCH: brake(0.2)},
            prompt="Pack voltage now, volts? (Enter to skip)",
            answer="pack_v",
        )
    ]
    for rep in range(a.repeats):
        for sign in (1.0, -1.0):
            seen = {"peak": 0.0, "since": 0.0}

            def plateau(t, fb, sign=sign, seen=seen):
                v = sign * fb[BENCH].v if BENCH in fb else 0.0
                if v > seen["peak"] + 0.3:
                    seen["peak"], seen["since"] = v, t
                return v >= top or (v > 20.0 and t - seen["since"] > 0.3)

            segs.append(
                Segment(
                    f"run-up {sign:+.0f} #{rep + 1}",
                    {BENCH: const(Cmd(t=sign * full))},
                    4.0,
                    until=plateau,
                )
            )
            segs.append(
                Segment("brake", {BENCH: brake(0.5)}, 5.0, until=stopped(BENCH))
            )
            segs.append(Segment("rest", {BENCH: brake(0.3)}, 0.5))
    # Under VMAX, past which a report's speed wraps round and reads backwards.
    return segs, Limits(speed={BENCH: min(top + 4.0, 0.99 * a.vmax)})


def _a4(a):
    square = a.square if a.square else (0.5 if a.load_inertia > 0 else 0.1)
    segs = [Segment("settle", {BENCH: brake(0.2)}, 1.0)]
    for hz in floats(a.freqs, [2.0, 5.0, 10.0]):
        segs.append(
            Segment(
                f"square {hz:g} Hz",
                {
                    BENCH: (
                        lambda hz: (
                            lambda t, fb: Cmd(
                                kd=0.05,
                                t=square if (t * hz) % 1.0 < 0.5 else -square,
                            )
                        )
                    )(hz)
                },
                2.0,
            )
        )
    segs.append(Segment("stop", {BENCH: brake(0.3)}, 3.0, until=stopped(BENCH)))
    return segs, Limits(speed={BENCH: 30.0})


def _a5(a):
    tau = (-1.0 if a.negative else 1.0) * a.hold_torque
    segs = [
        Segment("ramp", {BENCH: ramp_torque(0.0, tau, 1.0)}, 1.0),
        Segment(f"hold {tau:+.2f}", {BENCH: const(Cmd(t=tau))}, a.minutes * 60.0),
        Segment("release", {BENCH: ramp_torque(tau, 0.0, 1.0)}, 1.0),
    ]
    return segs, Limits(speed={BENCH: 3.0}, hot_c=a.hot_c)


def _legs(a) -> tuple[str, ...]:
    if a.joint in (None, "", "all"):
        return LEGS
    if a.joint not in LEGS:
        raise ValueError(f"--joint is one of {', '.join(LEGS)} or all")
    return (a.joint,)


def _leg_limits(extra=None) -> Limits:
    speed = {j: LEG_SPEED_CAP for j in LEGS}
    speed.update(extra or {})
    return Limits(speed=speed, windows=dict(WINDOWS))


def _b1(a):
    gains = [(3.0, 0.1), (12.0, 0.4), (48.0, 1.6), (12.0, 0.1), (12.0, 1.6)]
    if a.gains:
        pairs = floats(a.gains, [])
        gains = list(zip(pairs[0::2], pairs[1::2]))
    segs = [
        Segment("ease", legs_ease(LEGS), 3.0),
        Segment("settle", legs_hold(LEGS), 1.0),
    ]
    for j in _legs(a):
        base = 0.15 if "hip" in j else 0.25
        for kp, kd in gains:
            # A step no bigger than asks the motor for 2 Nm, a sweep for 1.5.
            step = min(base, 2.0 / kp)
            swing = min(0.08, 1.5 / kp)
            for level in (step, 0.0, -step, 0.0):
                cmds = legs_hold(LEGS, skip=(j,))
                cmds[j] = const(Cmd(p=CROUCH[j] + level, kp=kp, kd=kd))
                segs.append(
                    Segment(f"{j} step {level:+.3f} kp {kp:g} kd {kd:g}", cmds, 1.0)
                )
            cmds = legs_hold(LEGS, skip=(j,))
            cmds[j] = (
                lambda j, kp, kd, swing: (
                    lambda t, fb: Cmd(
                        p=CROUCH[j] + swing * chirp(t, 0.5, 6.0, 8.0), kp=kp, kd=kd
                    )
                )
            )(j, kp, kd, swing)
            segs.append(Segment(f"{j} sweep kp {kp:g} kd {kd:g}", cmds, 8.0))
            segs.append(Segment("rest", legs_hold(LEGS), 1.0))
    segs.append(Segment("let down", legs_release(LEGS), 2.0))
    return segs, _leg_limits()


def _b2(a):
    switch = a.vswitch
    wheel_cap = {w: switch + 10.0 for w in WHEELS}
    hold_legs = legs_hold(LEGS)
    segs = [
        Segment("ease", {**legs_ease(LEGS), **{w: brake(0.1) for w in WHEELS}}, 3.0),
    ]
    for tau in floats(a.torques, [0.1, 0.2, 0.4]):
        # The two wheels opposite ways, so their reactions on the hanging torso
        # cancel rather than pitch it.
        right, right_done = bang_bang(WHEELS[0], tau, switch, a.cycles)
        left, left_done = bang_bang(WHEELS[1], tau, switch, a.cycles, sign=-1.0)
        segs.append(
            Segment(
                f"bang {tau:.2f}",
                {**hold_legs, WHEELS[0]: right, WHEELS[1]: left},
                20.0,
                until=lambda t, fb, a=right_done, b=left_done: a(t, fb) and b(t, fb),
            )
        )
        segs.append(
            Segment("brake", {**hold_legs, **{w: brake(0.2) for w in WHEELS}}, 2.0)
        )
    sweep = {
        w: (
            lambda s: lambda t, fb: Cmd(kd=0.02, t=s * 0.15 * chirp(t, 1.0, 20.0, 10.0))
        )(s)
        for w, s in zip(WHEELS, (1.0, -1.0))
    }
    segs.append(Segment("torque sweep", {**hold_legs, **sweep}, 10.0))
    previous = 0.0
    for v in floats(a.speeds, [1, 3, 10, 25, -1, -3, -10, -25]):
        if abs(v) > switch:
            continue
        to = {
            w: (
                lambda a0, b0, s: (
                    lambda t, fb: Cmd(v=s * (a0 + (b0 - a0) * min_jerk(t)), kd=0.2)
                )
            )(previous, v, s)
            for w, s in zip(WHEELS, (1.0, -1.0))
        }
        at = {w: const(Cmd(v=s * v, kd=0.2)) for w, s in zip(WHEELS, (1.0, -1.0))}
        segs.append(Segment(f"to {v:+g}", {**hold_legs, **to}, 1.0))
        segs.append(Segment(f"speed {v:+g}", {**hold_legs, **at}, 2.5))
        previous = v
    segs.append(Segment("stop", {**hold_legs, **{w: brake(0.3) for w in WHEELS}}, 3.0))
    segs.append(Segment("let down", legs_release(LEGS), 2.0))
    return segs, _leg_limits(wheel_cap)


def _b3(a):
    stiff = legs_hold(LEGS, kp=24.0, kd=0.5)
    segs = [
        Segment("ease", legs_ease(LEGS), 3.0),
        Segment("still", stiff, a.still_s),
        Segment(
            "swing",
            stiff,
            prompt=(
                "Push the torso so the robot swings on the rail, let go, and "
                "press Enter once it has nearly stopped."
            ),
            answer="swung",
        ),
        Segment("let down", legs_release(LEGS), 2.0),
    ]
    return segs, _leg_limits()


def _b4(a):
    hips = ("hip_pitch_right", "hip_pitch_left")
    segs = [
        Segment("ease", legs_ease(LEGS), 3.0),
        Segment("settle", legs_hold(LEGS), 1.0),
    ]
    for k in range(a.repeats):
        level = 0.05 if k % 2 == 0 else -0.05
        cmds = legs_hold(LEGS, skip=hips)
        for h in hips:
            cmds[h] = const(Cmd(p=CROUCH[h] + level, kp=40.0, kd=1.0))
        segs.append(Segment(f"jerk {level:+.2f}", cmds, 1.5))
    segs.append(Segment("rest", legs_hold(LEGS), 1.0))
    segs.append(Segment("let down", legs_release(LEGS), 2.0))
    return segs, _leg_limits()


# Each leg joint swept slowly through most of its range and back, at the
# policies' own stiffness, so that the torque it takes, each way, at every angle
# is gravity's pull on the leg plus the joint's friction: the two directions
# together give the friction, and their mean gives gravity, whose shape puts the
# joint's true zero where the encoder's is not. Kept well inside the windows,
# the knees short of the owner's 90 degree fold, and slow enough that nothing
# but gravity and friction matters. Gains above about kp 40, kd 1 set the hips
# buzzing at 39 Hz on 2026-11-04; these are a third of that.
SWEEP_RANGE = {
    "hip_pitch_right": (-0.3, 0.6),
    "hip_pitch_left": (-0.3, 0.6),
    "knee_right": (0.05, 1.4),
    "knee_left": (0.05, 1.4),
}
SWEEP_RAD_S = 0.1


def ramp(joint: str, a: float, b: float, span: float, kp: float, kd: float) -> CmdFn:
    """From a to b at a constant speed, the speed fed forward."""
    v = (b - a) / span
    return lambda t, fb: Cmd(
        p=a + v * min(t, span), v=v if t < span else 0.0, kp=kp, kd=kd
    )


def _b5(a):
    segs = [
        Segment("ease", legs_ease(LEGS), 3.0),
        Segment("settle", legs_hold(LEGS), 1.0),
    ]
    for j in _legs(a):
        lo, hi = SWEEP_RANGE[j]
        others = legs_hold(LEGS, skip=(j,))
        span = (hi - lo) / SWEEP_RAD_S
        segs += [
            Segment(
                f"{j} to {lo:+.2f}",
                {**others, j: ease(j, lo, 2.0, HOLD_KP, HOLD_KD)},
                2.5,
            ),
            Segment(
                f"{j} up",
                {**others, j: ramp(j, lo, hi, span, HOLD_KP, HOLD_KD)},
                span + 0.5,
            ),
            Segment(
                f"{j} down",
                {**others, j: ramp(j, hi, lo, span, HOLD_KP, HOLD_KD)},
                span + 0.5,
            ),
            Segment(
                f"{j} back",
                {**others, j: ease(j, CROUCH[j], 2.0, HOLD_KP, HOLD_KD)},
                2.5,
            ),
        ]
    segs.append(Segment("let down", legs_release(LEGS), 2.0))
    return segs, _leg_limits()


# The first moves the robot makes under power, so as small and soft as will
# still show each motor turning its joint the way the map says: the legs eased
# to straight, then each joint in turn a few degrees and back, and each wheel a
# sixth of a turn and back. Nothing in it asks for more than about 0.6 Nm.
JOG_RAD = 0.15
JOG_KP, JOG_KD = 4.0, 0.15
WHEEL_JOG_RAD = 1.0
WHEEL_KP, WHEEL_KD = 1.0, 0.05


def _j1(a):
    held = {j: const(Cmd(p=0.0, kp=JOG_KP, kd=JOG_KD)) for j in LEGS}
    loose = {w: const(Cmd(kd=0.02)) for w in WHEELS}
    segs = [
        Segment(
            "legs eased to straight",
            {**{j: ease(j, 0.0, 3.0, JOG_KP, JOG_KD) for j in LEGS}, **loose},
            3.0,
        ),
        Segment("held straight", {**held, **loose}, 1.0),
    ]
    for j in _legs(a):
        way = "forward" if "hip" in j else "back"
        segs += [
            Segment(
                f"{j}: {math.degrees(JOG_RAD):.0f} degrees {way}",
                {**held, **loose, j: ease(j, JOG_RAD, 1.5, JOG_KP, JOG_KD)},
                2.0,
            ),
            Segment(
                f"{j}: back to straight",
                {**held, **loose, j: ease(j, 0.0, 1.5, JOG_KP, JOG_KD)},
                2.0,
            ),
        ]
    for w in WHEELS:
        segs += [
            Segment(
                f"{w}: a sixth of a turn forward",
                {**held, **loose, w: nudge(w, WHEEL_JOG_RAD, 2.0, WHEEL_KP, WHEEL_KD)},
                2.5,
            ),
            Segment(
                f"{w}: and back",
                {**held, **loose, w: nudge(w, -WHEEL_JOG_RAD, 2.0, WHEEL_KP, WHEEL_KD)},
                2.5,
            ),
        ]
    # Not legs_release, which lets go from the crouch: from straight, its crouch
    # target at full stiffness is a 0.5 rad step.
    let_go = {
        j: (lambda t, fb: Cmd(p=0.0, kp=JOG_KP * (1.0 - min(t / 2.0, 1.0)), kd=JOG_KD))
        for j in LEGS
    }
    segs.append(Segment("let go", {**let_go, **loose}, 2.0))
    return segs, Limits(
        speed={j: 3.0 for j in JOINTS}, windows=dict(WINDOWS), torque=1.0
    )


def _c1(a):
    legs = legs_hold(LEGS, kp=24.0, kd=0.5)
    wheels = {w: hold_here(w, 20.0, 0.5) for w in WHEELS}
    segs = [Segment("ease", {**legs_ease(LEGS), **wheels}, 3.0)]
    for k in range(a.repeats):
        segs.append(
            Segment(
                f"pull {k + 1}",
                {**legs, **wheels},
                prompt=(
                    "Pull the robot slowly by the torso, level, until the wheels "
                    "slide. Peak reading on the luggage scale, grams?"
                ),
                answer="pull_g",
            )
        )
    segs.append(Segment("let down", {**legs_release(LEGS), **wheels}, 2.0))
    return segs, _leg_limits({w: 5.0 for w in WHEELS})


HAND_S = 20.0
HAND_REST_S = 20.0


def _w_wheel(a) -> str:
    wheel = a.joint or WHEELS[0]
    if wheel not in WHEELS:
        raise ValueError(f"W1 runs a wheel: --joint {' or '.join(WHEELS)}")
    return wheel


def _w1(a):
    """One wheel's torque against speed, on the robot, with nothing taken off it.

    First, hands off, full torque each way from standstill until the wheel stops
    gaining speed: the low end of the curve, in the 15 ms or so the wheel takes to
    reach its top. Then a steady push of --hold-torque, twice, while a hand on the
    tread slows the wheel from its top speed down: each speed it settles at is
    where the motor can give no more than the hand takes, the top of the curve.
    The legs are left off and the robot is held by hand."""
    wheel = _w_wheel(a)
    top = min(0.95 * a.vmax, 52.0)
    spins = 2 * a.repeats

    def speed(fb) -> float:
        return abs(fb[wheel].v) if wheel in fb else 0.0

    def torque(fb) -> float:
        return abs(fb[wheel].tau) if wheel in fb else 0.0

    def squeeze(t, fb, seen):
        """Slow it from its top speed to a crawl in a straight line over the push:
        firmer when it runs ahead of that, easier when it falls behind."""
        v = speed(fb)
        left = HAND_S - t
        if t < 2.0:
            seen["top"] = max(seen.get("top", 0.0), v)
            return f"SPINNING UP. Rest the cloth on the tread, barely touching.  {v:4.1f} rad/s"
        start = max(seen.get("top", 0.0), 30.0)
        want = max(15.0, start * (1.0 - (t - 2.0) / (HAND_S - 4.0)))
        if v > want + 6.0:
            say = "FIRMER"
        elif v < want - 6.0:
            say = "EASE OFF a little"
        else:
            say = "good, keep tightening slowly"
        return (
            f"{say:<28} {left:4.0f} s left   wheel {v:4.1f} rad/s (aim {want:4.1f}), "
            f"{torque(fb):4.2f} Nm"
        )

    def resting(t, fb, span):
        return f"LET GO and rest. Next push in {span - t:3.0f} s"

    segs = [
        Segment(
            "HANDS OFF THE TREAD, hold the shin: six quick spin-ups now",
            {wheel: brake(0.05)},
            1.0,
        )
    ]
    for rep in range(a.repeats):
        for sign in (1.0, -1.0):
            seen = {"peak": 0.0, "since": 0.0}

            def plateau(t, fb, sign=sign, seen=seen):
                v = sign * fb[wheel].v if wheel in fb else 0.0
                if v > seen["peak"] + 0.3:
                    seen["peak"], seen["since"] = v, t
                return v >= top or (v > 20.0 and t - seen["since"] > 0.3)

            done = 2 * rep + (1 if sign > 0 else 2)
            segs.append(
                Segment(
                    f"  spin-up {done} of {spins}, hands off",
                    {wheel: const(Cmd(t=sign * a.full_torque))},
                    2.0,
                    until=plateau,
                )
            )
            segs.append(
                Segment(
                    "brake", {wheel: brake(0.5)}, 3.0, until=stopped(wheel), quiet=True
                )
            )
            segs.append(Segment("rest", {wheel: brake(0.3)}, 0.5, quiet=True))
    segs.append(
        Segment(
            "GET READY: cloth in hand, not touching yet. The wheel will spin and keep "
            "spinning, then you slow it over 20 s, following the prompts",
            {wheel: brake(0.3)},
            4.0,
            coach=lambda t, fb: f"starting in {4.0 - t:2.0f} s",
        )
    )
    for k in (1, 2):
        seen: dict = {}
        segs.append(
            Segment(
                f"PUSH {k} OF 2: squeeze gradually, light to firm",
                {wheel: const(Cmd(t=a.hold_torque))},
                HAND_S,
                coach=lambda t, fb, seen=seen: squeeze(t, fb, seen),
            )
        )
        if k == 1:
            segs.append(
                Segment(
                    "LET GO: it stops itself",
                    {wheel: brake(0.3)},
                    HAND_REST_S,
                    coach=lambda t, fb: resting(t, fb, HAND_REST_S),
                    coach_s=5.0,
                )
            )
    segs.append(Segment("LET GO. Finished.", {wheel: brake(0.3)}, 2.0))
    # Under VMAX, past which a report's speed wraps round and reads backwards.
    return segs, Limits(speed={wheel: min(top + 8.0, a.vmax - 5.0)}, hot_c=a.hot_c)


TESTS: dict[str, Test] = {
    t.key: t
    for t in (
        Test(
            "A1",
            "Torque, against a scale",
            "bench",
            "A bar bolted to the output, its far end resting on a kitchen scale at "
            "--arm-mm from the axis. --negative for the other direction, with the "
            "bar on the scale's other side.",
            200.0,
            _a1,
            lambda a: (BENCH,),
            options="--arm-mm, --negative, --torques",
        ),
        Test(
            "A2",
            "Inertia and friction",
            "bench",
            "The output bare, or carrying a balanced disc or bar of known inertia "
            "(--load-inertia, kg m2), free to turn. Run it both ways: the two "
            "together separate the rotor's inertia from any error in the torque.",
            500.0,
            _a2,
            lambda a: (BENCH,),
            options="--load-inertia, --torques, --vswitch, --speeds, --cycles",
        ),
        Test(
            "A3",
            "Torque against speed",
            "bench",
            "The disc of known inertia, secure and guarded: it reaches 50 rad/s. "
            "Run it on a full pack and again near cut-off. Braking it puts energy "
            "back into the supply; a bench supply may trip on it.",
            1000.0,
            _a3,
            lambda a: (BENCH,),
            options="--load-inertia, --full-torque, --repeats",
        ),
        Test(
            "A4",
            "Command to torque, how long",
            "bench",
            "The output bare or loaded, free to turn.",
            1000.0,
            _a4,
            lambda a: (BENCH,),
            options="--square, --freqs",
        ),
        Test(
            "A5",
            "Heat at the continuous rating",
            "bench",
            "The A1 bar on the scale, or against anything that stops it turning.",
            50.0,
            _a5,
            lambda a: (BENCH,),
            options="--hold-torque, --minutes, --hot-c, --negative",
        ),
        Test(
            "B1",
            "Leg steps and sweeps",
            "hung",
            "The robot hanging from the rail by both hoist lugs, on a rod through "
            "the two eyes, legs hanging free and nothing in reach of them.",
            200.0,
            _b1,
            lambda a: LEGS,
            imu={"gyro": 400.0, "gravity": 100.0, "game": 100.0},
            options="--joint, --gains kp,kd,kp,kd...",
        ),
        Test(
            "B2",
            "Wheels in the air",
            "hung",
            "Hanging as for B1. Both wheels spin, opposite ways: keep clear.",
            200.0,
            _b2,
            lambda a: JOINTS,
            imu={"gyro": 400.0, "gravity": 100.0},
            options="--torques, --vswitch, --speeds, --cycles",
        ),
        Test(
            "B3",
            "Still, then swinging",
            "hung",
            "Hanging as for B1. It holds still for --still-s, then asks for a push.",
            200.0,
            _b3,
            lambda a: LEGS,
            imu={"gyro": 400.0, "gravity": 100.0, "game": 100.0, "accel": 200.0},
            options="--still-s",
        ),
        Test(
            "B4",
            "Torso jerks, for the IMU's lag",
            "hung",
            "Hanging as for B1.",
            300.0,
            _b4,
            lambda a: LEGS,
            imu={"gyro": 400.0, "gravity": 100.0},
            options="--repeats",
        ),
        Test(
            "B5",
            "Slow sweeps, for the legs' zeros and friction",
            "hung",
            "Hanging as for B1, the torso held or free. Each leg joint in turn moves "
            "slowly through most of its range and back, the others holding the "
            "crouch: hips 17 degrees back to 34 forward, knees straight to 80 folded.",
            200.0,
            _b5,
            lambda a: LEGS,
            imu={"gyro": 400.0, "gravity": 100.0},
            options="--joint",
        ),
        Test(
            "J1",
            "First moves",
            "hung",
            "Hanging as for B1. The legs ease to straight, then each joint in turn "
            "moves a few degrees and back, slowly and softly, and each wheel a sixth "
            "of a turn. --joint for one leg joint only.",
            200.0,
            _j1,
            lambda a: JOINTS,
            options="--joint",
        ),
        Test(
            "C1",
            "Grip on the floor",
            "floor",
            "Standing on the floor under test, on the slack safety line, steadied "
            "upright by hand. The wheels are held; pull level by the torso with a "
            "luggage scale. Repeat on every floor it will run on.",
            100.0,
            _c1,
            lambda a: JOINTS,
            options="--repeats",
        ),
        Test(
            "W1",
            "A wheel's torque against speed, braked by hand",
            "table",
            "The robot on the table, its legs off and the wheel clear of everything. "
            "Hold the shin just above the wheel's motor with one hand throughout. "
            "Hands off for the spin-ups; then, gloved, slow the tread with the other "
            "hand, gradually, light to firm, through each 20 s push. Never the hub.",
            1000.0,
            _w1,
            lambda a: (_w_wheel(a),),
            options="--joint, --repeats, --full-torque, --hold-torque, --hot-c",
        ),
    )
}


def defaults(**over) -> SimpleNamespace:
    """Every option a test reads, at its default."""
    a = SimpleNamespace(
        joint=None,
        torques=None,
        speeds=None,
        gains=None,
        freqs=None,
        negative=False,
        arm_mm=0.0,
        load_inertia=0.0,
        load_label="",
        vswitch=20.0,
        kd_sweep=0.3,
        cycles=3,
        full_torque=PEAK_NM,
        repeats=3,
        square=0.0,
        hold_torque=0.8,
        minutes=10.0,
        hot_c=90,
        still_s=60.0,
        vmax=50.0,
    )
    for k, v in over.items():
        setattr(a, k, v)
    return a


# ---- the log -------------------------------------------------------------------
#
# One JSON object a line. The first is the header and the last the footer; in
# between, by "k":
#
#   c  a command as the motor was sent it: h (host seconds), j, p v kp kd t
#   f  a motor's report: t (controller seconds), h, j, s state, p v q (torque),
#      tm tr (MOSFET and winding C), d (the frame, hex)
#   i  an IMU report: t, h, r (its name), v (SI units, the IMU's own axes), a
#   s  the controller's status: t, h, status
#   n  what the sequence did: seg, or answer and value
#   l  a line the controller or diagd logged: t, h, text
#   x  the run stopped early: h, why
#
# "t" is the controller's clock, which every motor report and IMU reading is
# stamped with as it arrives; "h" is the host's time.monotonic(). A command has
# only h: simulation/sysid/logfile.py puts it on the controller's clock by the
# report the motor answered it with.


class LogWriter:
    def __init__(self, path: Path, header: dict):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.path, "w", encoding="utf-8")
        self._lock = threading.Lock()
        self.lines = 0
        self.write({"kind": "header", "format": FORMAT, **header})

    def write(self, record: dict) -> None:
        line = json.dumps(record, separators=(",", ":"))
        with self._lock:
            self._f.write(line + "\n")
            self.lines += 1

    def flush(self) -> None:
        with self._lock:
            self._f.flush()

    def close(self, footer: dict) -> None:
        self.write({"kind": "footer", **footer})
        with self._lock:
            self._f.close()


def r5(x: float) -> float:
    return round(float(x), 5)


def command_record(h: float, joint: str, c: Cmd) -> dict:
    return {
        "k": "c",
        "h": round(h, 6),
        "j": joint,
        "p": r5(c.p),
        "v": r5(c.v),
        "kp": r5(c.kp),
        "kd": r5(c.kd),
        "t": r5(c.t),
    }


def feedback_record(t, h, joint, state, p, v, q, t_mos, t_rotor, data=b"") -> dict:
    rec = {
        "k": "f",
        "t": round(t, 6),
        "h": round(h, 6),
        "j": joint,
        "s": state,
        "p": r5(p),
        "v": r5(v),
        "q": r5(q),
        "tm": t_mos,
        "tr": t_rotor,
    }
    if data:
        rec["d"] = bytes(data).hex()
    return rec


if __name__ == "__main__":
    for t in TESTS.values():
        print(f"{t.key}  {t.title}  [{t.fixture}, {t.hz:g} Hz]")
        print(f"    {t.setup}")
        segs, _ = t.build(defaults(load_inertia=0.01))
        span = sum(s.duration or 0.0 for s in segs if s.prompt is None)
        print(f"    {len(segs)} segments, about {span / 60:.1f} min plus what it asks")
