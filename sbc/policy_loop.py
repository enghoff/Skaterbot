"""What runs the trained policy, whatever it runs against.

sbc/balance.py uses this on the robot, through diagd, and
simulation/mujoco/balance_check.py uses the very same code against a simulated
robot, so what is tested is what runs. It knows nothing of how a command reaches
a motor: it is given a rig, with `latest` (each joint's last report, sbc/sysid.py's
st.Fb), `imu` (each report's last reading and when it was heard), `send` and
`ask_status`, and it is told the time and how to wait.

docs/POLICY_INTERFACE.md is the contract, and simulation/mujoco/drive.py's
Controller the reference implementation. A policy's own numbers come from its
pack (sbc/pack_policy.py), written from the run and never typed in here.

The one thing here that is not in that contract is the order of a step. A motor
reports only when it is spoken to, once for each frame it gets, so a loop that
just sent its commands every 10 ms would see each motor as it was about 9 ms
before, where training had the encoders at most 2.5 ms late. So each step starts
by sending every motor the command it already holds, waits a moment for the
reports that brings, and only then looks and decides. The commands go out a few
milliseconds after the look, which is what training has them doing anyway.
"""

from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path

import numpy as np
import sysid_tests as st

# What the readings are multiplied by before they go in, as training has them
# (wheeled_biped_task/env.py). balance_check.py holds them against drive.py's.
ANG_VEL_SCALE = 0.25
JOINT_VEL_SCALE = 0.05

PERIOD_S = 0.01
# How long a step waits for the motors' reports before it looks anyway. On the
# robot on 2026-11-04 they were in after 4.7 ms, 6.6 at the 99th percentile, by
# way of diagd and back. The decision then takes 1.5 ms, and the commands still
# act within the 10 ms training allows them.
REPORT_WAIT_S = 0.006
# A reading older than this is a sensor that has stopped, not a late one: training
# went to 20 ms and MuJoCo stays up with the IMU 40 ms late.
IMU_STALE_S = 0.1
# Past what a step should ever take, the robot has been running blind.
STEP_LATE_S = 0.05

WHEEL_SPEED_CAP = 50.0  # the report's speed wraps at VMAX, 55

# How long both knees must feel the weight before it counts. Handling it in the air
# passes in less: a 2 cm shake at 6 Hz, in MuJoCo, makes them feel 0.13 Nm for 40 ms
# and nothing for 100, where standing makes them feel 0.27.
TOUCH_CONFIRM_S = 0.1
# Tilted further than this it is being carried, not put down.
TOUCH_TILT_DEG = 20.0
# Further than this from where they were put, a leg is being held by something.
TOUCH_LEGS_RAD = 0.2
# In the air the knees hold up a shin and a wheel, and read above this: +0.08 and
# +0.11 Nm in the crouch on the rail on 2026-11-04. Under the robot's weight they read
# about -0.15 in MuJoCo. Learned below this, the weight is already on them.
AIR_LEAST_NM = -0.02
# Picked up while running. Over the 900 s of driving on 2026-11-05, up to 0.5 m/s, what the
# two knees feel, on average, stayed under this for at most 50 ms but when it was lifted,
# three times, when this rule fired with the wheels at 20 to 33 rad/s. One knee alone
# will not do: as a wheel spins up in the air the two read 0.4 Nm apart. Nor will the
# wheels' speed: a cut at 30 and then 40 rad/s stopped two runs with the knees still
# loaded, one in a full reversal and one catching a dive at 47. A moment's lightness at
# speed, over a bump, keeps going.
LIFT_LIGHT_NM = 0.10
LIFT_CONFIRM_S = 0.15
LIFT_SPIN_RAD_S = 20.0
# MuJoCo's worst start reaches 25 rad/s, so the first moments ask for more.
LIFT_EARLY_S = 2.0
LIFT_EARLY_SPIN_RAD_S = 30.0
# Nothing on the floor keeps its knees this light for this long, however slow its wheels.
LIFT_SURE_S = 1.0


class Net:
    """The exported network: (obs - offset) / divisor, then fully connected
    layers with an ELU after every one but the last."""

    def __init__(self, path: Path):
        with np.load(path, allow_pickle=False) as z:
            self.meta = json.loads(str(z["meta"]))
            self.offset = z["offset"].astype(np.float32)
            self.divisor = z["divisor"].astype(np.float32)
            self.layers = [
                (z[f"w{k}"].astype(np.float32), z[f"b{k}"].astype(np.float32))
                for k in range(self.meta["layers"])
            ]
        self.alpha = np.float32(self.meta["elu_alpha"])

    def __call__(self, obs: np.ndarray) -> np.ndarray:
        x = (obs - self.offset) / self.divisor
        last = len(self.layers) - 1
        for k, (w, b) in enumerate(self.layers):
            x = w @ x + b
            if k < last:
                x = np.where(x > 0, x, self.alpha * np.expm1(np.minimum(x, 0)))
        return x


# ---- the IMU ---------------------------------------------------------------------


class Imu:
    """The chip's readings in the torso's frame, as `map` and `level` found it:
    `axes` holds the torso's axes in the chip's, by row."""

    def __init__(self, axes, gravity_sign: int):
        self.axes = np.asarray(axes, dtype=float)
        self.gravity_sign = gravity_sign

    def torso(self, gyro, gravity) -> tuple[np.ndarray, np.ndarray]:
        """The turn rate, rad/s, and gravity's direction, a unit vector."""
        g = self.axes @ np.asarray(gravity, dtype=float) * self.gravity_sign
        return self.axes @ np.asarray(gyro, dtype=float), g / np.linalg.norm(g)


def nose_down(g: np.ndarray) -> float:
    """The torso's pitch from gravity's direction, radians, nose down positive."""
    return math.atan2(g[0], -g[2])


def right_down(g: np.ndarray) -> float:
    """The torso's roll from gravity's direction, radians, right side down positive."""
    return math.atan2(-g[1], -g[2])


def tilt(g: np.ndarray) -> float:
    return math.acos(min(max(-float(g[2]), -1.0), 1.0))


# ---- the policy ------------------------------------------------------------------


class Balancer:
    """Readings into an input, the input through the network, its answer into
    motor commands, in the joints' frame. POLICY_INTERFACE.md's two tables."""

    def __init__(self, net: Net, wheel_limit: float | None = None):
        m = net.meta
        if tuple(m["legs"]) != st.LEGS or tuple(m["wheels"]) != st.WHEELS:
            raise ValueError("the pack's joint order is not this code's")
        self.net = net
        self.meta = m
        self.crouch = np.array(m["crouch"], dtype=np.float32)
        self.leg_scale = np.array(m["leg_scale"], dtype=np.float32)
        self.leg_lo = np.array(m["leg_lo"], dtype=np.float32)
        self.leg_hi = np.array(m["leg_hi"], dtype=np.float32)
        self.kp, self.kd = float(m["kp"]), float(m["kd"])
        self.wheel_scale = float(m["wheel_scale"])
        self.wheel_limit = self.wheel_scale if wheel_limit is None else wheel_limit
        self.actions = np.zeros(m["n_act"], dtype=np.float32)
        self.obs = np.zeros(m["n_obs"], dtype=np.float32)
        self.last_wheels = (0.0, 0.0)

    def reset(self) -> None:
        self.actions[:] = 0.0

    def observe(self, fb: dict, w, g, speed: float, turn: float, height: float):
        o = self.obs
        o[0:3] = np.asarray(w) * ANG_VEL_SCALE
        o[3:6] = g
        o[6] = speed
        o[7] = turn
        if self.meta["scale_height"]:
            lo, hi = self.meta["height_range"]
            height = (height - (lo + hi) / 2) / ((hi - lo) / 2)
        o[8] = height
        for k, j in enumerate(st.LEGS):
            o[9 + k] = fb[j].p - self.crouch[k]
            o[13 + k] = fb[j].v * JOINT_VEL_SCALE
        for k, j in enumerate(st.WHEELS):
            o[17 + k] = fb[j].v * JOINT_VEL_SCALE
        o[19:25] = self.actions[:6]
        return o

    def decide(self, obs: np.ndarray) -> dict[str, st.Cmd]:
        self.actions = np.clip(self.net(obs), -1.0, 1.0)
        targets = np.clip(
            self.crouch + self.leg_scale * self.actions[:4], self.leg_lo, self.leg_hi
        )
        cmds = {
            j: st.Cmd(p=float(targets[k]), kp=self.kp, kd=self.kd)
            for k, j in enumerate(st.LEGS)
        }
        # A limit the policy is not told of, for trying it with the wheels off
        # the ground: what it remembers asking for is what it asked for.
        wheels = np.clip(
            self.wheel_scale * self.actions[4:6], -self.wheel_limit, self.wheel_limit
        )
        self.last_wheels = (float(wheels[0]), float(wheels[1]))
        for k, j in enumerate(st.WHEELS):
            cmds[j] = st.Cmd(t=float(wheels[k]))
        return cmds


def ground_speed(fb: dict, pitch_rate: float, wheel_radius: float) -> float:
    """Each wheel's spin against the ground is its joint's plus the leg's and the
    torso's pitching."""
    spins = [
        pitch_rate - fb[hip].v + fb[knee].v + fb[wheel].v
        for hip, knee, wheel in (
            ("hip_pitch_right", "knee_right", "wheel_drive_right"),
            ("hip_pitch_left", "knee_left", "wheel_drive_left"),
        )
    ]
    return wheel_radius * (spins[0] + spins[1]) / 2.0


class Hold:
    """Heading and place, held while nobody asks for speed or turn, since the
    policy sees only its turn rate and drifts: 336 mm in 20 s in MuJoCo, standing.

    drive.py's Hold, from the robot's own sensors, and far gentler. A wheel on the
    floor sticks near standstill about three times as hard as the policy was trained
    for (docs/SYSID.md), so with drive.py's bands and gains each correction set the
    robot rocking and the rocking set off the next correction. Nor does it count until
    the robot has slowed, or letting go of a trigger would reel it back to where the
    trigger was let go. The heading is the turn rate about gravity added up, rather than
    the IMU's game rotation, since it only has to last until somebody next drives.
    """

    HEADING_BAND_RAD = (math.radians(2.0), math.radians(6.0))
    PLACE_BAND_M = (0.05, 0.15)
    HEADING_GAIN = 1.5
    PLACE_GAIN = 0.3
    MAX_TURN_RAD_S = 0.3
    MAX_SPEED_M_S = 0.1
    # Under both of these it has stopped, and whatever it does now is drift.
    SLOWED_M_S = 0.03
    SLOWED_RAD_S = 0.1

    def __init__(self, wheel_radius: float):
        self.wheel_radius = wheel_radius
        self.holding = False
        self.slowed = False
        self.heading = self.rolled = 0.0
        self.turning = self.moving = False

    def command(
        self, speed: float, turn: float, fb: dict, w, g, dt: float
    ) -> tuple[float, float]:
        if speed or turn:
            self.holding = False
            return speed, turn
        if not self.holding:
            self.holding = True
            self.slowed = False
            self.heading = self.rolled = 0.0
            self.turning = self.moving = False
        turning = -float(np.dot(w, g))
        rolling = ground_speed(fb, float(w[1]), self.wheel_radius)
        if not self.slowed:
            self.slowed = (
                abs(rolling) < self.SLOWED_M_S and abs(turning) < self.SLOWED_RAD_S
            )
            return 0.0, 0.0
        self.heading += turning * dt
        self.rolled += rolling * dt
        lo, hi = self.HEADING_BAND_RAD
        self.turning = abs(self.heading) > (lo if self.turning else hi)
        lo, hi = self.PLACE_BAND_M
        self.moving = abs(self.rolled) > (lo if self.moving else hi)
        cap = self.MAX_TURN_RAD_S
        back_turn = min(max(-self.HEADING_GAIN * self.heading, -cap), cap)
        cap = self.MAX_SPEED_M_S
        back_speed = min(max(-self.PLACE_GAIN * self.rolled, -cap), cap)
        return (
            back_speed if self.moving else 0.0,
            back_turn if self.turning else 0.0,
        )


# ---- finding the floor -----------------------------------------------------------


class Touch:
    """Whether the robot's weight has come onto its wheels, from what its knees feel.

    A motor reports the torque it is making, and on the rail a knee's reading held
    still to 0.001 Nm, though a jolt could leave it 0.04 away, held by friction. So
    the knees' readings in the air are learned afresh each time, and what is watched
    is how far each has come from there. Both knees have to feel it, for
    TOUCH_CONFIRM_S, with the torso near upright and the legs near where they were
    put: one wheel down, a hand on one leg, or a shake in the air is none of those.
    """

    KNEES = ("knee_right", "knee_left")

    def __init__(self, each_nm: float | None, pose: dict[str, float]):
        self.each = each_nm
        self.pose = pose
        self.heard: list[list[float]] = []
        self.air: list[float] | None = None
        # The air's readings at the measuring run, for a robot armed with its weight on it.
        self.usual: list[float] | None = None
        self.since: float | None = None
        self.light_since: float | None = None
        # What `lower` watched, for touch_numbers.
        self.samples: list[tuple[float, float, float]] = []

    def learn(self, fb: dict) -> None:
        self.heard.append([fb[j].tau for j in self.KNEES])

    def learned(self) -> str | None:
        """Takes what was heard as the air's readings. What is wrong with them, if
        anything, in words for whoever is holding it."""
        self.air = [float(x) for x in np.mean(self.heard, axis=0)]
        self.heard = []
        self.since = self.light_since = None
        lowest = min(self.air)
        if lowest < AIR_LEAST_NM:
            return (
                f"the knees read {self.air[0]:+.2f} and {self.air[1]:+.2f} Nm, so they are "
                "already carrying its weight: lift it clear of the floor first"
            )
        return None

    def pulls(self, fb: dict) -> list[float]:
        """How far each knee has come from the air's reading, Nm, weight positive."""
        return [a - fb[j].tau for a, j in zip(self.air, self.KNEES, strict=True)]

    def felt(self, now: float, fb: dict, g: np.ndarray) -> bool:
        """True once the weight has been on both knees for long enough."""
        steady = (
            min(self.pulls(fb)) > self.each
            and tilt(g) < math.radians(TOUCH_TILT_DEG)
            and all(abs(fb[j].p - p) < TOUCH_LEGS_RAD for j, p in self.pose.items())
        )
        if not steady:
            self.since = None
            return False
        if self.since is None:
            self.since = now
        return now - self.since >= TOUCH_CONFIRM_S

    def lifted(self, now: float, fb: dict, spin: float, running_s: float) -> bool:
        """Whether what stands on them has been picked up, from a policy that has been
        running this long and wheels this fast."""
        if sum(self.pulls(fb)) / len(self.KNEES) >= LIFT_LIGHT_NM:
            self.light_since = None
            return False
        if self.light_since is None:
            self.light_since = now
        light = now - self.light_since
        least = LIFT_EARLY_SPIN_RAD_S if running_s < LIFT_EARLY_S else LIFT_SPIN_RAD_S
        return light >= LIFT_SURE_S or (light >= LIFT_CONFIRM_S and spin > least)


# ---- what stops it ---------------------------------------------------------------


def limits(legs_limp: bool = False) -> st.Limits:
    """A motor that faults, overheats, overspeeds or stops answering, and a leg
    out of its window, as every test on the robot has it. Legs nobody is
    commanding can be anywhere."""
    speed = {j: st.LEG_SPEED_CAP for j in st.LEGS}
    speed.update({j: WHEEL_SPEED_CAP for j in st.WHEELS})
    return st.Limits(speed=speed, windows={} if legs_limp else dict(st.WINDOWS))


class Tipped(st.Abort):
    """Fallen over, or a leg driven out of its place: nothing wrong with the robot, and
    a launch waits to be picked up again."""


class Guard:
    """What stops a run. With `free` set, nothing is standing and nothing is being
    driven, so a robot may be carried at any angle and its limp legs swing as they
    like: only a motor's own faults count."""

    def __init__(self, tilt_deg: float, lim: st.Limits):
        self.tilt_rad = math.radians(tilt_deg)
        self.windows = lim.windows
        self.free = False
        self.speed = lim.speed
        self.motors = st.Sequencer(
            [], dataclasses.replace(lim, windows={}, speed={}), st.JOINTS
        )

    def sensors(self, now: float, rig) -> tuple[list, list]:
        readings = []
        for report in ("gyro", "gravity"):
            heard = rig.imu.get(report)
            if heard is None or now - heard[0] > IMU_STALE_S:
                raise st.Abort(
                    f"IMU: no {report} report for {IMU_STALE_S * 1000:.0f} ms"
                )
            readings.append(heard[1])
        return readings[0], readings[1]

    def check(self, now: float, fb: dict, g: np.ndarray) -> None:
        self.motors.check(now, fb)
        if self.free:
            return
        # A knee flung past its cap, as it was by a crash on 2026-11-05, is a fall too.
        for j, cap in self.speed.items():
            if abs(fb[j].v) > cap:
                raise Tipped(f"{j}: {fb[j].v:+.1f} rad/s, past the {cap:g} cap")
        for j, (low, high) in self.windows.items():
            if not low <= fb[j].p <= high:
                raise Tipped(f"{j}: at {fb[j].p:+.3f} rad, outside {(low, high)}")
        angle = tilt(g)
        if angle > self.tilt_rad:
            raise Tipped(
                f"tilted {math.degrees(angle):.0f} degrees, past "
                f"{math.degrees(self.tilt_rad):.0f}"
            )


class Trim:
    """What is asked of the policy, nudged slowly until the robot does what was asked.

    The policy's answer to a command is off by a steady amount, which it cannot see. On
    the robot on 2026-11-05, asked for 0.5 m/s straight on it did 0.46 and turned 0.12
    rad/s to the left, a circle of 4 m; asked to turn on the spot it backed round a
    circle of 33 to 87 mm; and at 0.5 m/s and 1.5 rad/s it turned 1.89 rad/s to the left
    and 1.58 to the right. Its wheels and gyro say all of that, and no manual trim could
    cover it, since the error changes with what is asked.

    Slow on purpose, with time constants of 1 and 2 s against the 1.56 Hz it rings at, so
    that it cannot feed the rocking. A change of command swings the robot, so nothing is
    learned until the command has been steady for a moment, and what was learned fades
    while it changes, being for the last command. With nothing asked, Hold has it.
    """

    SPEED_GAIN = 0.5
    TURN_GAIN = 1.0
    MAX_SPEED_M_S = 0.15
    MAX_TURN_RAD_S = 0.6
    # A change of this much in a step is the command changing: under the ramps' 0.006 m/s
    # and 0.03 rad/s, and over a thumb's tremble.
    CHANGING_M_S = 0.002
    CHANGING_RAD_S = 0.01
    SETTLE_S = 0.5
    FADE_S = 0.3

    def __init__(self, wheel_radius: float):
        self.wheel_radius = wheel_radius
        self.reset()

    def reset(self) -> None:
        self.speed = self.turn = 0.0
        self.last_speed = self.last_turn = 0.0
        self.settled = 0.0

    def command(
        self, speed: float, turn: float, fb: dict, w, g, dt: float
    ) -> tuple[float, float]:
        if not (speed or turn):
            self.reset()
            return speed, turn
        changing = (
            abs(speed - self.last_speed) > self.CHANGING_M_S
            or abs(turn - self.last_turn) > self.CHANGING_RAD_S
        )
        self.last_speed, self.last_turn = speed, turn
        if changing:
            self.settled = 0.0
            fade = math.exp(-dt / self.FADE_S)
            self.speed *= fade
            self.turn *= fade
        else:
            self.settled += dt
            if self.settled >= self.SETTLE_S:
                rolling = ground_speed(fb, float(w[1]), self.wheel_radius)
                turning = -float(np.dot(w, g))
                self.speed += self.SPEED_GAIN * (speed - rolling) * dt
                self.turn += self.TURN_GAIN * (turn - turning) * dt
                cap = self.MAX_SPEED_M_S
                self.speed = min(max(self.speed, -cap), cap)
                cap = self.MAX_TURN_RAD_S
                self.turn = min(max(self.turn, -cap), cap)
        return speed + self.speed, turn + self.turn


# ---- one step --------------------------------------------------------------------


class Stepper:
    """The policy's 100 Hz, against a rig, on a clock and ways of waiting that
    the caller supplies: real ones on the robot, simulated ones in MuJoCo.
    `wait(until)` returns at a time, `nap()` lets a moment pass while the
    reports come in, and on the robot must let the thread hearing them run."""

    def __init__(
        self,
        balancer,
        imu,
        rig,
        guard,
        clock,
        wait,
        nap,
        hold=None,
        writer=None,
        trim=None,
    ):
        self.balancer = balancer
        self.imu = imu
        self.rig = rig
        self.guard = guard
        self.clock = clock
        self.wait = wait
        self.nap = nap
        self.hold = hold
        self.trim = trim
        self.writer = writer
        self.held: dict[str, st.Cmd] = {}
        # For the motors-off check: what the policy is told of the motors, in
        # place of what they say.
        self.pretend = None
        self.send_commands = True
        self.asked_at = 0.0
        self.last_step: float | None = None
        # Each step's timing, for the summary.
        self.waits: list[float] = []
        self.ages: list[float] = []
        self.gaps: list[float] = []
        self.thinks: list[float] = []
        self.missed = 0

    def speak(self) -> None:
        """Every motor spoken to, so that it reports where it is now."""
        self.asked_at = self.clock()
        if self.send_commands:
            for j, c in self.held.items():
                self.rig.send(j, c)
            missing = [j for j in st.JOINTS if j not in self.held]
        else:
            missing = list(st.JOINTS)
        if missing:
            self.rig.ask_status(missing)

    def heard_all(self) -> bool:
        latest = self.rig.latest
        return all(j in latest and latest[j].at >= self.asked_at for j in st.JOINTS)

    def look(self):
        """Every motor's report and the IMU, in the torso's frame, checked."""
        now = self.clock()
        fb = dict(self.rig.latest)
        gyro, gravity = self.guard.sensors(now, self.rig)
        w, g = self.imu.torso(gyro, gravity)
        self.guard.check(now, fb, g)
        return now, fb, w, g

    def step(
        self,
        t0: float,
        speed: float,
        turn: float,
        height: float,
        override: dict[str, st.Cmd] | None = None,
    ) -> dict:
        """One policy step, starting at t0: speak, look, decide, send. With
        `override`, that is sent instead, and the policy's answer only logged."""
        self.wait(t0)
        self.speak()
        deadline = t0 + REPORT_WAIT_S
        while not self.heard_all() and self.clock() < deadline:
            self.nap()
        now, fb, w, g = self.look()
        if self.last_step is not None:
            gap = now - self.last_step
            self.gaps.append(gap)
            if gap > STEP_LATE_S:
                raise st.Abort(f"a step took {gap * 1000:.0f} ms")
        self.last_step = now
        self.waits.append(now - self.asked_at)
        self.ages.append(now - min(fb[j].at for j in st.JOINTS))
        if not self.heard_all():
            self.missed += 1
        asked_speed, asked_turn = speed, turn
        if self.trim is not None:
            speed, turn = self.trim.command(speed, turn, fb, w, g, PERIOD_S)
        if self.hold is not None:
            speed, turn = self.hold.command(speed, turn, fb, w, g, PERIOD_S)
        b = self.balancer
        told = self.pretend(fb) if self.pretend else fb
        obs = b.observe(told, w, g, speed, turn, height)
        cmds = b.decide(obs)
        self.thinks.append(self.clock() - now)
        if override is not None:
            cmds = override
        if self.send_commands:
            for j, c in cmds.items():
                self.rig.send(j, c)
            self.held = cmds
        if self.writer:
            self.writer.write(
                {
                    "k": "p",
                    "h": round(now, 6),
                    "o": [round(float(x), 4) for x in obs],
                    "a": [round(float(x), 4) for x in b.actions],
                    "ask": [round(asked_speed, 3), round(asked_turn, 3)],
                    "wait": round(self.waits[-1], 5),
                }
            )
        return {
            "t": now,
            "w": w,
            "g": g,
            "fb": fb,
            "speed": speed,
            "turn": turn,
            "obs": obs,
            "cmds": cmds,
        }

    def timing(self) -> str:
        if not self.gaps:
            return "no steps"

        def ms(values, q):
            return np.percentile(values, q) * 1000.0

        return (
            f"{len(self.gaps) + 1} steps, a step every {ms(self.gaps, 50):.1f} ms "
            f"(99th percentile {ms(self.gaps, 99):.1f}, worst {max(self.gaps) * 1000:.1f}); "
            f"the look {ms(self.waits, 50):.1f} ms after speaking "
            f"(worst {max(self.waits) * 1000:.1f}), the oldest report then "
            f"{ms(self.ages, 50):.1f} ms old (worst {max(self.ages) * 1000:.1f}); "
            f"the decision took {ms(self.thinks, 50):.2f} ms "
            f"(worst {max(self.thinks) * 1000:.2f}); {self.missed} steps "
            "looked without every report"
        )
