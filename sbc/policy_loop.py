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
from collections import deque
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

# A wheel's report wraps round at its VMAX, so past this it cannot be read: VMAX less
# a margin. 55 is what every motor was set to until 6 November 2026, and is assumed
# where nobody says.
WHEEL_VMAX = 55.0
WHEEL_MARGIN_RAD_S = 5.0
WHEEL_SPEED_CAP = WHEEL_VMAX - WHEEL_MARGIN_RAD_S

# Armed and driving, nothing short of the robot lying on the floor cuts its motors:
# whatever can be recovered from is, and what cannot be is let down gently. The owner's
# rule, 6 November 2026, after a wheel past its cap had dropped the robot three times
# the day before. Past this it is lying down: training gave up there too.
FALLEN_DEG = 60.0
# A sensor silent this long is not coming back soon enough to balance on.
LOST_S = 0.5
# A motor in a fault state is cleared, then enabled, no oftener than this.
REVIVE_S = 0.05
# Over this, a wheel slows the command, by GOVERN_PER_S of it a second, until it is back
# under this less GOVERN_BAND; and a winding over its hot limit slows it to a stop.
WHEEL_GOVERN_BELOW_CAP = 10.0
GOVERN_BAND = 5.0
GOVERN_PER_S = 0.25

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
# And the wheels speeding up by this much while the knees are light: off the floor
# nothing holds them back. Braking hard from 1.6 m/s in MuJoCo on 6 November 2026 the
# knees went light for 0.2 s with the wheels at 21 rad/s, slowing from 44, which the
# rule without this took for a lift, and on the robot would have braked the wheels
# at speed and dropped it.
LIFT_SPEEDING_UP_RAD_S = 5.0


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


# The chip starts its estimate of which way is down over again when it is shaken hard
# enough. A jump on the robot on 2026-11-06 shook it at up to 7 g, and for half a second
# its gravity report read exactly (0, 0, +9.8) in its own frame, the robot upside down,
# then wandered back over a second or more at the wrong length. The fall check believed
# it and let go of a robot standing at 4 degrees. So a report of the wrong length, or one
# further than GRAVITY_JUMP_RAD from where the gyro has turned the last one believed, is
# not believed, and the gyro turns that one on, for GYRO_CARRY_S at most.
GRAVITY_M_S2 = 9.80665
# Standing and driving on the robot its reports were 9.55 to 9.70 m/s2 long, but
# replayed over every run of 5 and 6 November, set down by hand or driven, they reached
# 9.0 and 10.6 for half a second at a time; starting over, 4.9, 6.3 and 15.9.
GRAVITY_LENGTH_TOLERANCE = 0.20
# Once it has started over the reports are not believed until nearly the right length:
# on 8 November 2026 at 20:13 they came back at 13.8 m/s2, shrank to 11.0 over 2.3 s with
# their direction 10 degrees out, and only then snapped to 9.75 and the truth, so inside
# the tolerance above and still wrong for the last 0.8 s of it.
GRAVITY_RESTART_TOLERANCE = 0.10
# Judged as each new report comes in, against the last one believed turned on by the gyro
# since: a jump turns the torso at 10 rad/s, and the chip's gravity comes 30 to 60 times
# a second and later than its gyro, so a closer mark doubted good reports in MuJoCo.
GRAVITY_JUMP_RAD = math.radians(25.0)
# Was 1.5 s, which let down a robot standing happily on the gyro at 20:13 on 8 November
# 2026, the chip back 2.9 s after a knock in a hard turn. Against the chip's own reports
# over that run's driving the gyro's gravity is 4 degrees out at the median whether
# carried for 3 s or 8, so most of that is the chip's error and little is drift.
GYRO_CARRY_S = 4.0
# A longer gap between two readings is not turned through: nothing was seen of it.
CARRY_STEP_MAX_S = 0.05


class Attitude:
    """Gravity's direction in the torso's frame: the chip's report while it can be
    believed, and while it cannot, the last one believed turned by the gyro.
    `doubted_for` is how long it has not been, and `why` the reason."""

    def __init__(self, imu: Imu):
        self.imu = imu
        self.g: np.ndarray | None = None
        self.at: float | None = None
        self.last_raw: np.ndarray | None = None
        self.believed: np.ndarray | None = None
        self.doubted_for = 0.0
        self.why = ""
        self.restarted = False

    def read(self, now: float, gyro, gravity) -> tuple[np.ndarray, np.ndarray]:
        w = self.imu.axes @ np.asarray(gyro, dtype=float)
        raw = np.asarray(gravity, dtype=float)
        dt = 0.0 if self.at is None else min(max(now - self.at, 0.0), CARRY_STEP_MAX_S)
        self.at = now
        if self.g is not None:
            # A direction fixed in the world, seen from a body turning at w.
            g = self.g - np.cross(w, self.g) * dt
            self.g = g / np.linalg.norm(g)
        fresh = self.last_raw is None or not np.array_equal(raw, self.last_raw)
        self.last_raw = raw
        if not fresh:
            # The same report as last step: judged already, and the gyro carries on.
            if self.why:
                self.doubted_for += dt
                return w, self.g if self.g is not None else self._unit(raw)
            if self.believed is not None:
                return w, self.believed
        return self._judge(raw, w, dt)

    def _unit(self, raw: np.ndarray) -> np.ndarray:
        length = float(np.linalg.norm(raw))
        if length == 0.0:
            return np.array([0.0, 0.0, -1.0])
        return self.imu.axes @ raw * self.imu.gravity_sign / length

    def _judge(self, raw: np.ndarray, w: np.ndarray, dt: float):
        length = float(np.linalg.norm(raw))
        unit = self._unit(raw)
        why = ""
        if length == 0.0 or (raw[0] == 0.0 and raw[1] == 0.0 and raw[2] > 0.0):
            # (0, 0, +9.8) exactly: which way is down as the chip has it starting over,
            # and on this robot upside down.
            why = "reads straight along the chip's own axis, as it does starting over"
            self.restarted = True
        elif abs(length - GRAVITY_M_S2) > GRAVITY_M_S2 * (
            GRAVITY_RESTART_TOLERANCE if self.restarted else GRAVITY_LENGTH_TOLERANCE
        ):
            why = f"reads {length:.1f} m/s2 long"
        elif self.g is not None:
            off = math.acos(min(max(float(unit @ self.g), -1.0), 1.0))
            if off > GRAVITY_JUMP_RAD:
                why = f"turned {math.degrees(off):.0f} degrees more than the gyro saw"
        if not why:
            self.g = unit
            self.believed = unit
            self.doubted_for = 0.0
            self.why = ""
            self.restarted = False
            return w, unit
        self.doubted_for += dt
        self.why = why
        if self.g is None:
            # Nothing believed yet to carry: what it says, as it always was.
            return w, unit
        return w, self.g

    def believe_anyway(self) -> None:
        """Carried as long as it can be: the next report is taken as it is."""
        self.g = None
        self.believed = None
        self.last_raw = None
        self.doubted_for = 0.0
        self.why = ""
        self.restarted = False


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


# ---- jumping ---------------------------------------------------------------------
#
# docs/POLICY_INTERFACE.md, "Two policies: one drives, one jumps": the driving policy
# runs until a jump is asked for, then a jump policy takes the robot through its crouch,
# the jump and the landing, and hands it back. simulation/mujoco/drive.py's TwoPolicies
# is the reference. Nothing is reset at a hand-over: the incoming policy is fed what the
# outgoing one would have been, its own last outputs being the outgoing one's,
# converted to its own action scaling.

CLEARANCE_SCALE = 10.0
TIMER_CLIP_S = 2.0
BATTERY_SCALE = 5.0
RATED_VOLTS = 24.0
# Hip to knee and knee to axle (POLICY_INTERFACE.md): a leg's height from its angles alone.
LEG_LINK_M = 0.105
# The jump policy does not drive fast: handed a robot at 1.2 to 1.4 m/s it fell on
# landing, and below 1.1 never (MuJoCo, September). So a press above this brakes first,
# the operator's speed held under JUMP_SPEED_CAP_M_S until the jump is over.
JUMP_TOP_SPEED_M_S = 1.0
JUMP_SPEED_CAP_M_S = 0.9
JUMP_BRAKE_GIVE_UP_S = 3.0
# And having braked, under JUMP_TOP_SPEED_M_S this long before the crouch: handed over
# the moment it got there, still pitched back from braking, the September jump policy
# fell on landing in MuJoCo, where pressed at 0.5 m/s it landed and stood.
JUMP_BRAKED_S = 0.5
# The ride height asked for stays at the bottom this long after the trigger, then the
# operator's again (POLICY_INTERFACE.md, the jump's step 3).
JUMP_HOLD_BOTTOM_S = 0.5
# A press is refused tilted past this, or with either knee carrying less than this
# above what it felt in the air: both wheels have to be on the floor.
JUMP_TILT_DEG = 15.0
JUMP_KNEE_LOADED_NM = 0.05
# After the hand-back, this long more before anything may take the landing for a lift.
JUMP_SETTLE_S = 0.5
# Handed back this long after the trigger, landed and still crouched, however long the
# run's window. On the robot on 2026-11-06 the jump policy landed a 30 mm jump, stood
# itself up and then tipped over backwards 0.7 s after the trigger, still in charge
# until 1.5 s; the driving policy is the one proven on the robot. In MuJoCo, handed
# back here, every case of launch_check's 17 landed and stood, at the robot's delays
# and longer ones. The longest flight the jump runs make is 0.21 s, at 120 mm.
JUMP_HAND_BACK_S = 0.5


def leg_heights(fb: dict) -> list[float]:
    """Each leg's hip-to-axle height, from its joint angles alone."""
    return [
        LEG_LINK_M * (math.cos(fb[hip].p) + math.cos(fb[knee].p - fb[hip].p))
        for hip, knee in (
            ("hip_pitch_right", "knee_right"),
            ("hip_pitch_left", "knee_left"),
        )
    ]


class JumpBalancer(Balancer):
    """A jump policy: the balance policy's 25 inputs and then the trigger, the target
    clearance and the time since the trigger, and the battery if it was trained with it;
    its 6 outputs and then the legs' stiffness and damping, as powers of the run's
    leg_gain_range about the driving policy's 12 Nm/rad and 0.4 Nm s/rad."""

    def __init__(self, net: Net, wheel_limit: float | None = None):
        super().__init__(net, wheel_limit)
        j = self.meta.get("jump")
        if not j or self.meta["n_obs"] < 28 or self.meta["n_act"] != 8:
            raise ValueError("not a jump policy's pack: see sbc/pack_policy.py")
        self.jump = j
        self.gain_range = float(j["leg_gain_range"])
        self.trigger = 0.0
        self.target = 0.0
        self.timer = 0.0
        self.volts: float | None = None
        self.leg_kp, self.leg_kd = self.kp, self.kd

    def observe(self, fb: dict, w, g, speed: float, turn: float, height: float):
        o = super().observe(fb, w, g, speed, turn, height)
        o[25] = self.trigger
        o[26] = self.target * CLEARANCE_SCALE * self.trigger
        o[27] = min(self.timer, TIMER_CLIP_S) * self.trigger
        if self.meta["n_obs"] > 28:
            volts = RATED_VOLTS if self.volts is None else self.volts
            o[28] = (volts / RATED_VOLTS - 1.0) * BATTERY_SCALE
        return o

    def decide(self, obs: np.ndarray) -> dict[str, st.Cmd]:
        cmds = super().decide(obs)
        self.leg_kp = self.kp * self.gain_range ** float(self.actions[6])
        self.leg_kd = self.kd * self.gain_range ** float(self.actions[7])
        for j in st.LEGS:
            cmds[j] = dataclasses.replace(cmds[j], kp=self.leg_kp, kd=self.leg_kd)
        return cmds


def converted(actions: np.ndarray, src: Balancer, dst: Balancer) -> np.ndarray:
    """`src`'s last outputs as `dst`'s: the same leg angles and wheel torques asked for,
    in `dst`'s scaling, clipped as its own are; a jump policy's gains at their middle."""
    out = np.zeros(dst.meta["n_act"], dtype=np.float32)
    angles = src.crouch + src.leg_scale * actions[:4]
    out[:4] = (angles - dst.crouch) / dst.leg_scale
    out[4:6] = actions[4:6] * src.wheel_scale / dst.wheel_scale
    return np.clip(out, -1.0, 1.0)


class TwoPolicies:
    """The driving policy and a jump policy behind one balancer's face, handing over
    between them. `press` asks for a jump; the rest of a step is a balancer's.

    States: "drive"; "braking", the driving policy still driving, the operator's speed
    held under JUMP_SPEED_CAP_M_S until the robot is under JUMP_TOP_SPEED_M_S;
    "crouch", the jump policy asked for its lowest ride height, the trigger still 0,
    until the legs are within the run's tolerance of it or its jump_crouch_s has passed;
    "jump", the trigger up, the bottom height held JUMP_HOLD_BOTTOM_S, and the robot
    handed back JUMP_HAND_BACK_S after the trigger, or at the run's jump_window_s if
    that is sooner. No landing is detected:
    POLICY_INTERFACE.md has why none is needed. What happens goes into `events`."""

    # A press faster than this brakes first, held under `cap_m_s`, until it has been
    # slower for `braked_s`.
    top_speed_m_s = JUMP_TOP_SPEED_M_S
    cap_m_s = JUMP_SPEED_CAP_M_S
    braked_s = JUMP_BRAKED_S

    def __init__(
        self,
        driving: Balancer,
        jumping: JumpBalancer,
        clearance: float,
        volts=None,
    ):
        self.driving = driving
        self.jumping = jumping
        j = jumping.jump
        lo, hi = j["clearance_m"]
        self.clearance = min(max(float(clearance), lo), hi)
        self.crouch_s = float(j["crouch_s"]) or 0.6
        self.bottom = float(jumping.meta["height_range"][0])
        self.tolerance = float(j["crouch_tolerance_m"])
        self.window_s = min(float(j["window_s"]), JUMP_HAND_BACK_S)
        self.volts = volts
        self.events: list[str] = []
        self.reset()

    # -- a balancer's face, with the driving policy's settings

    @property
    def meta(self) -> dict:
        return self.driving.meta

    @property
    def kp(self) -> float:
        return self.driving.kp

    @property
    def kd(self) -> float:
        return self.driving.kd

    @property
    def actions(self) -> np.ndarray:
        return self.active.actions

    @property
    def last_wheels(self) -> tuple[float, float]:
        return self.active.last_wheels

    @property
    def obs(self) -> np.ndarray:
        return self.active.obs

    def reset(self) -> None:
        self.driving.reset()
        self.jumping.reset()
        self.jumping.trigger = 0.0
        self.active = self.driving
        self.state = "drive"
        self.t = 0.0
        self.since_back = math.inf
        self.slow_for = 0.0

    # -- what balance.py asks of it

    @property
    def busy(self) -> bool:
        """Jumping, or just back from it: nothing should take this for a lift."""
        return self.state in ("crouch", "jump") or self.since_back < JUMP_SETTLE_S

    @property
    def assist(self) -> bool:
        """Whether Trim and Hold may act: not while the jump policy has the robot."""
        return self.active is self.driving

    @property
    def speed_cap(self) -> float | None:
        return None if self.state == "drive" else self.cap_m_s

    @property
    def jump_meta(self) -> dict:
        """What jumps, for the run's log."""
        return self.jumping.meta

    def press(
        self, g, speed: float, loaded: bool | None, held: bool = False
    ) -> str | None:
        """A press of the jump button. None if it is taken up, or why not. `held`, the
        button still down as the press is heard, a jump policy takes no notice of: it
        jumps at the press."""
        if self.state != "drive":
            doing = "braking for" if self.state == "braking" else "in"
            return f"already {doing} a jump"
        if g is not None and math.degrees(tilt(g)) > JUMP_TILT_DEG:
            return f"tilted {math.degrees(tilt(g)):.0f} degrees"
        if loaded is False:
            return "a wheel is not on the floor"
        self.t = 0.0
        if abs(speed) > self.top_speed_m_s:
            self.state = "braking"
            self.slow_for = 0.0
            self.events.append(f"pressed at {speed:+.2f} m/s: braking first")
            return None
        self.events.append(f"pressed at {speed:+.2f} m/s")
        self._crouch()
        return None

    def button(self, held: bool | None, loaded: bool | None = None) -> None:
        """The jump button each step, as ScriptedJump's: a jump policy has nothing to wait
        for."""

    def _crouch(self) -> None:
        d, j = self.driving, self.jumping
        j.actions = converted(d.actions, d, j)
        j.last_wheels = d.last_wheels
        j.trigger = 0.0
        self.active = j
        self.state, self.t = "crouch", 0.0
        self.events.append(f"crouching to {self.bottom * 1000:.0f} mm, jump policy on")

    def _hand_back(self) -> None:
        d, j = self.driving, self.jumping
        d.actions = converted(j.actions, j, d)
        d.last_wheels = j.last_wheels
        j.trigger = 0.0
        self.active = d
        self.state, self.t = "drive", 0.0
        self.since_back = 0.0
        self.events.append("handed back to the driving policy")

    def _braking(self, fb: dict, w) -> None:
        """On to the crouch once it has been slow enough for long enough, or given up."""
        rolling = ground_speed(fb, float(w[1]), self.meta["wheel_radius"])
        self.slow_for = (
            self.slow_for + PERIOD_S if abs(rolling) < self.top_speed_m_s else 0.0
        )
        if self.slow_for >= self.braked_s:
            self._crouch()
        elif self.t > JUMP_BRAKE_GIVE_UP_S:
            self.state, self.t = "drive", 0.0
            self.events.append(
                f"refused: still at {rolling:+.2f} m/s after "
                f"{JUMP_BRAKE_GIVE_UP_S:g} s of braking"
            )

    def observe(self, fb: dict, w, g, speed: float, turn: float, height: float):
        self.t += PERIOD_S
        self.since_back += PERIOD_S
        if self.state == "braking":
            self._braking(fb, w)
        if self.state == "crouch":
            low = float(np.mean(leg_heights(fb)))
            if low <= self.bottom + self.tolerance or self.t >= self.crouch_s:
                self.state, self.t = "jump", 0.0
                self.events.append(
                    f"jump: legs at {low * 1000:.0f} mm, "
                    f"target {self.clearance * 1000:.0f} mm"
                )
        if self.state == "jump" and self.t >= self.window_s:
            self._hand_back()
        if self.active is self.jumping:
            j = self.jumping
            jumping = self.state == "jump"
            j.trigger = 1.0 if jumping else 0.0
            j.target = self.clearance
            j.timer = self.t if jumping else 0.0
            j.volts = self.volts() if callable(self.volts) else self.volts
            if self.state == "crouch" or (jumping and self.t < JUMP_HOLD_BOTTOM_S):
                height = self.bottom
        return self.active.observe(fb, w, g, speed, turn, height)

    def decide(self, obs: np.ndarray) -> dict[str, st.Cmd]:
        return self.active.decide(obs)


# ---- the scripted jump -------------------------------------------------------------
#
# A jump with no network, in place of the jump policy behind the A button. Every jump
# policy so far tucked rather than jumped, and its knees answered the robot's roll
# (simulation/roll_mode.py); the owner tried jd8 on the robot on 8 November 2026 and found
# it unsteady and its height unconvincing, and agreed to a scripted jump first, from
# standstill. Both legs are always sent the same command, so the roll mode is never
# driven. It jumps standing or driving, up to JUMP_RUN_TOP_M_S, and lands at the speed it
# left at. In order:
#
#   crouch  the driving policy, asked for the lowest ride height it was trained on, at
#           the speed the operator asks;
#   hold    still the driving policy, until the robot is calm, steady and balanced;
#   push    the knees push with the push's torque, the hips keeping each axle under the
#           centre of mass and the wheels driving forward against the push's turn, until
#           on their speed they would pass the take-off height;
#   brake   the legs stopped there, which pulls the wheels off the floor;
#   flight  the legs drawn up a little and held, until the knees feel the floor;
#
# and then it is the driving policy's again, as it lands. What each is, and what MuJoCo
# showed, is in JumpScript. The push is the one setting for how high (JUMP_PUSH_NM).

# The robot's masses and where each sits, in the legs' plane: the torso's forward and up
# of the hips' axis in its own frame; a thigh's and a shin's along it from the joint above;
# a wheel's at its axle. From simulation/urdf/wheeled_biped.urdf, the CAD's, whose 2 098 g
# came within 12 g of the whole robot as it runs on a scale (tools/mass_budget.toml); the
# centre of mass from these is MuJoCo's to 0.02 mm over the legs' travel.
TORSO_KG = 1.044633
TORSO_COM_M = (0.000146, 0.0685 - 0.027481)
THIGH_KG = 0.221560
THIGH_COM_M = 0.095588
SHIN_KG = 0.213560
SHIN_COM_M = 0.095235
WHEEL_KG = 0.093634
ROBOT_KG = TORSO_KG + 2.0 * (THIGH_KG + SHIN_KG + WHEEL_KG)


def axle_at(hip: float, knee: float) -> tuple[float, float]:
    """A leg's axle, forward of its hip and up from it in the torso's frame, m."""
    shin = hip - knee
    return (
        LEG_LINK_M * (math.sin(hip) + math.sin(shin)),
        -LEG_LINK_M * (math.cos(hip) + math.cos(shin)),
    )


def leg_for(forward: float, down: float) -> tuple[float, float]:
    """The hip and knee that put the axle `forward` of the hip and `down` below it, the
    knee folded back as it always is."""
    reach = math.hypot(forward, down)
    bend = reach * reach / (2.0 * LEG_LINK_M * LEG_LINK_M) - 1.0
    knee = math.acos(min(max(bend, -1.0), 1.0))
    return math.atan2(forward, down) + knee / 2.0, knee


def leg_jacobian(hip: float, knee: float) -> np.ndarray:
    """How the axle moves, forward and up, for each of the hip and the knee."""
    shin = hip - knee
    link = LEG_LINK_M
    return np.array(
        [
            [link * (math.cos(hip) + math.cos(shin)), -link * math.cos(shin)],
            [link * (math.sin(hip) + math.sin(shin)), -link * math.sin(shin)],
        ]
    )


def mass_centre(hip: float, knee: float) -> tuple[float, float]:
    """The whole robot's centre of mass, both legs at these angles, forward of the hips'
    axis and up from it in the torso's frame, m."""
    shin = hip - knee
    kx, kz = LEG_LINK_M * math.sin(hip), -LEG_LINK_M * math.cos(hip)
    ax, az = axle_at(hip, knee)
    x = TORSO_KG * TORSO_COM_M[0] + 2.0 * (
        THIGH_KG * THIGH_COM_M * math.sin(hip)
        + SHIN_KG * (kx + SHIN_COM_M * math.sin(shin))
        + WHEEL_KG * ax
    )
    z = TORSO_KG * TORSO_COM_M[1] + 2.0 * (
        -THIGH_KG * THIGH_COM_M * math.cos(hip)
        + SHIN_KG * (kz - SHIN_COM_M * math.cos(shin))
        + WHEEL_KG * az
    )
    return x / ROBOT_KG, z / ROBOT_KG


def off_balance(hip: float, knee: float, up) -> float:
    """How far the centre of mass is ahead of the axles, across `up`, the world's up in
    the torso's frame: nought when it is straight above them, m."""
    cx, cz = mass_centre(hip, knee)
    ax, az = axle_at(hip, knee)
    return (cx - ax) * up[1] - (cz - az) * up[0]


def under_mass(down: float, up) -> float:
    """How far forward of the hip the axle has to be, `down` below it, for the centre of
    mass to be straight above it along `up`. The centre of mass moves with the legs, so it
    is found by Newton's method."""

    def off(forward: float) -> float:
        return off_balance(*leg_for(forward, down), up)

    forward = 0.0
    for _ in range(4):
        f = off(forward)
        forward -= f / ((off(forward + 1e-4) - f) / 1e-4)
    return forward


@dataclasses.dataclass(frozen=True)
class JumpScript:
    """What the scripted jump does, phase by phase. MuJoCo's figures are on
    launch_check.py's rig with the roll mode at its fit (simulation/mujoco/
    jump_roll_check.py), D8 driving, 8 November 2026 (session scratchpad scripted_jump/;
    the crouch's rate, the hold, the level push, the brake's hips and the jump while
    driving from jump_grace/, the angular momentum MuJoCo's own)."""

    # THE CROUCH is the driving policy's own, asked for the lowest of its trained heights,
    # brought down at this rate, until the legs are within the tolerance or the time is
    # up. The driving policy cannot balance with its legs taken from it: given the legs
    # in a scripted crouch, 155 or 165 mm, it rocked at 5-6 Hz, growing, and tipped past
    # 15 degrees within a second. Nor does a scripted dip from there to 150-155 mm pay:
    # with nothing balancing it the torso drifted, and it fell 4 times in 16, the knees
    # pushed within 0.02 rad of straight.
    # Brought down at 0.25 m/s it swayed 0.2-0.4 s after; at 0.4 no longer, and with the
    # hold below it took off 0.43-0.45 s after the press; at 1.0 the wheels came 3 mm off
    # the floor as it dropped.
    crouch_m: float = 0.165
    crouch_rate_m_s: float = 0.4
    crouch_tolerance_m: float = 0.005
    crouch_s: float = 1.5
    # THE HOLD. The push sends the torso turning with whatever turn it starts with, and with
    # the centre of mass off its axles it adds one: 7 mm off under a 60 N push spun it at 2
    # rad/s. So it waits, for at least `hold_s`, until the torso turns slower than
    # `calm_rad_s`, the wheels' speed over the floor has spread less than `steady_m_s`, so
    # standing or driving steadily, and the centre of mass is within `over_m` of above the
    # axles (by the legs' angles and the IMU), all for `ready_s`; and gives the jump up
    # after `hold_most_s`. Standing in the crouch the driving policy sways the axles 7 mm
    # either side of balance over a second or so, and waiting for them within 5 mm, the
    # wheels still, took 0.2-0.9 s: the pause the eye caught. The level push (below)
    # answers where the centre of mass starts, and from within 20 mm it took off 0.43-0.45
    # s after the press, landing as level. On the worst rig the driving policy sways 17 mm
    # either side in the crouch: within 5 mm it never pushed, and within 20 it pushes at
    # the end of a sway, where it is still. Pushing as soon as it was down, the legs still
    # settling, it left the floor turning nose-down at 23-36 mNm s, which no estimate of
    # the robot's angular momentum from the gyro and the joints, 16 ms apart, foretold.
    # Held in the crouch the operator may steer, and letting go straightens the turn asked
    # (THE BUTTON, below), so it also waits for the torso to turn about the vertical slower
    # than `calm_yaw_rad_s` and for both knees to carry weight, as a press is refused
    # without (JUMP_KNEE_LOADED_NM): turning at 0.5 rad/s and 0.5 m/s MuJoCo's inner knee
    # goes light. Standing, the turn rate stays under 0.2 rad/s (Hold). Let go still
    # steering at 0.75 rad/s and 0.4 m/s, on launch_check.py's rig, it jumped about 0.1 s
    # later than let go going straight, and stood, on the worst rig as well (8 November
    # 2026, case 17). And it waits to be going over the floor slower than ScriptedJump's
    # top speed (JUMP_RUN_TOP_M_S, less if asked slower), however it was pressed: on the
    # worst rig at 2.5 Nm, pressed at 0.5 m/s asked while swaying back at 0.32, it ran up to
    # 0.93 in the crouch, pushed at that, and fell forward on landing (launch_check.py case
    # 17 on the worst rig, 8 November 2026).
    hold_s: float = 0.1
    calm_rad_s: float = 0.5
    calm_yaw_rad_s: float = 0.3
    steady_m_s: float = 0.15
    over_m: float = 0.02
    ready_s: float = 0.05
    hold_most_s: float = 2.0
    # THE PUSH. The knees push with the push's torque and no stiffness; the hips, at
    # `hip_kp` and `hip_kd`, keep each axle on the path that holds the centre of mass above
    # it along the IMU's up as the push began, for wherever the knees are as measured: under
    # load the knees lag their command by 0.3 rad and more, and a hip that kept to the
    # command put the axle 20 mm behind the centre of mass, and spun the torso nose-down at
    # 10 rad/s. Following a planned extension instead, at a speed asked, the knees' torque
    # lag (18 ms) had them catch up at 35 rad/s, overshoot to within 0.08 rad of straight
    # and ring in the air, and the height came out of order with the speed asked.
    hip_kp: float = 40.0
    hip_kd: float = 1.0
    push_most_s: float = 0.3
    # THE LEVEL PUSH: through the push both wheels drive forward with `level_nm`, and
    # `level_nm_per_m` more for each metre the centre of mass starts ahead of the axles,
    # both at JUMP_PUSH_NM and in proportion to the push. Without it the robot left the
    # floor turning nose-down, 28-45 mNm s about its centre of mass, and touched down 4-16
    # degrees nose-down and still turning, up to 24 after, its centre of mass 14-42 mm
    # ahead of the wheels, which the driving policy caught by running forward: as the legs
    # straightened, the floor pushed the robot back at the wheels, below the centre of mass,
    # about 4 N for 70 ms, and that, not anything in the air, is what turned it. Driving
    # the wheels forward has the floor push it forward instead. At 0.10 Nm it left at 12-21
    # mNm s, at 0.15 3-12, at 0.18 0-8 and at 0.21 -4 to 0, landing nose-up; the spread was
    # where the centre of mass started, 1.2 mNm s for each millimetre ahead, which the 6 Nm
    # per m takes out. Feedback through the push on the torso's turning, from the gyro,
    # changed nothing: the gyro is 16 ms late, the wheels' torque 15 ms, the push 70 ms.
    # The same at a push of 1.0 Nm landed it 4-5 degrees nose-up, and at 1.8 2-4 nose-down;
    # in proportion to the push, 2-4 and 0.5-2 nose-down, and at 1.0 Nm and 1.5 m/s the
    # worst tilt through the jump went from 12 degrees to 8.
    #
    # Both shares, the centre of mass's and the speed's below, are in proportion to
    # `level_nm` as set, so that set to the robot's 0.35, twice MuJoCo's, for the robot
    # answering it half as much (balance.py's JUMP_LEVEL_RANGE_NM), they are twice
    # MuJoCo's as well. Over the robot's 89 scripted jumps of 8 November 2026, at 1.6-2.5
    # Nm and 0.35 with 6 Nm per m, the IMU's pitch 50 ms after the brake came 0.38 +- 0.07
    # degrees more nose-down for each mm the centre of mass was ahead as it pushed, 0.49
    # +- 0.16 of the 29 at 2.5 Nm, and at the hand-back 0.33 +- 0.07 (session scratchpad
    # jump_speed/fit_com.py): the under-correction a half answer to 6 Nm per m leaves.
    #
    # And past `level_from_m_s` rolling, `level_per_m_s` more of itself for each m/s
    # faster, forward and in proportion backward. The robot's jumps landed no more
    # nose-down for their speed once the centre of mass is allowed for, -1.3 +- 1.2
    # degrees per m/s at the hand-back; but rolling, its wheels have that much less to
    # catch a nose-down landing with, and the robot's landings scatter 5 degrees either
    # way (JUMP_RUN_TOP_M_S). On launch_check.py's rig with the robot's floor friction and
    # its half answer to the level push, landing 10 degrees more nose-down than it does,
    # as the robot's worse landings do, at 0.83-0.88 m/s the wheels reached their
    # ceiling, 52-53 rad/s, without it, and 40-45 with 0.6 of itself per m/s from a
    # standstill; 14 more,
    # it fell twice in three without and stood with. But MuJoCo itself answers it twice as
    # much: from a standstill, at 0.6, launch_check.py case 17's driving jumps landed 25-31
    # degrees nose-up, braked to a stop and on backwards, and failed it, 0.5 m/s asked
    # going -0.07 half a second after landing. So it starts at 0.45 m/s, under which the
    # robot jumped 29 times at 2.5 Nm without it and none fell, and then rises faster.
    # (8 November 2026, session scratchpad jump_speed/.)
    level_nm: float = 0.18
    level_nm_per_m: float = 6.0
    level_per_m_s: float = 1.0
    level_from_m_s: float = 0.45
    # THE BRAKE: the push ends as soon as the knees, `brake_lead_s` ahead on their own
    # speed, would pass the take-off height, and the legs are held there, stiffly, for
    # `brake_s`. Stopping the legs pulls the wheels up as the body goes on. The brake
    # reaches the knees 18 ms late and they overshoot it all the same: at 1.6 Nm to within
    # 0.33 rad of straight, at 1.8 0.45; taking off at 200 mm, or braking 10 ms later,
    # bought 1-3 mm and brought them within 0.06. The hips are held where the take-off
    # height puts them: following the knees as they overshot, as the push's do, swung the
    # legs back and forth as they left the floor, and the torso 13-15 degrees with them in
    # 50 ms; held, 6-7. Softer, at 20 Nm/rad, or damped at 2.5, it swung 10-12 and cleared
    # 3 mm less.
    #
    # The lead is at JUMP_PUSH_NM and in proportion to the push, since a harder push has
    # the knees faster at the brake and further to stop. The brake can only fall on a
    # loop's step, 10 ms apart, so a lead either moves it a whole step or not at all. Held
    # at 0.02 s, the knees came within 0.12 rad of straight at 2.2 Nm and 1 m/s, and at 2.5
    # Nm and 0.5 m/s reached it; at 0.035 s, which this is at 2.5, they stayed 0.49 rad or
    # more from it, standing, at 0.5 m/s and braked from 1-1.4 m/s, and with the push 4 per
    # cent either side of 2.5, so that the brake fell on either side of a step (session
    # scratchpad jump_height/).
    takeoff_m: float = 0.195
    brake_lead_s: float = 0.0225
    brake_kp: float = 40.0
    brake_kd: float = 1.5
    # Was 0.03: the hold takes nothing from the rise but holds up the tuck, and at 0.015 the
    # robot-like rig cleared 2-3 mm more with the same landings (session scratchpad
    # envelope_jump/, 8 November 2026).
    brake_s: float = 0.015
    # THE FLIGHT: the legs drawn up to `land_m` over `tuck_s`, softly, and held. Held at
    # the take-off height they cleared 10-16 mm at 1.8-2.2 Nm, and drawn up 25 mm, 18-22
    # at 1.6-1.8; drawn up further it did not finish in the flight, and stiffer it was
    # slower. Moving the legs any more than that in the air turns the torso, with nothing
    # to stop it: swinging them under the centre of mass for the landing turned it 14
    # degrees further the same way.
    land_m: float = 0.170
    tuck_s: float = 0.07
    air_kp: float = 12.0
    air_kd: float = 0.5
    # Commands reach the motors about 6 ms after they are sent and are held for 10.
    lead_s: float = 0.025
    # THE WHEELS hold their spin against the world through the push and the flight, by
    # `spin_kd`, and as the legs are asked to fold, each rotor is turned with its shin.
    # Left free, as a shin swings its wheel's rotor has to be turned with it, and the floor
    # did that, pushing the robot forward under its centre of mass: the torso left the
    # floor turning nose-down at 0.8-1.8 rad/s with the wheels free, and at -1.1 to +0.7
    # with their spin held.
    spin_kd: float = 0.02
    # TOUCHDOWN, the knees as the loop sees them: their torque below -`touch_nm`, the
    # weight arriving, or folding past where they were asked, by `touch_rad`, or by
    # `touch_past_rad` and `touch_rad_s` faster than asked. Looked for only from `earliest`
    # of the flight the legs' speed at the brake predicts, the body leaving at `leaves` of
    # it, since in the first part of a flight the knees still ring from the brake; and
    # taken as landed at `latest` of it and `latest_s` more, felt or not. Landing on legs
    # near straight, the knees hardly fold, but their torque jumped by 1 Nm. From 1.0 to
    # 1.8 Nm, on that rig and the worse one below, it was felt between 5 ms before the
    # wheels touched and 20 ms after.
    touch_nm: float = 0.3
    touch_rad: float = 0.08
    touch_past_rad: float = -0.02
    touch_rad_s: float = 2.0
    leaves: float = 0.9
    earliest: float = 0.6
    latest: float = 1.5
    latest_s: float = 0.15
    # Landed, it is the driving policy's at once; it was given the robot 0.1 s later in
    # MuJoCo and the robot fell on from 11 degrees to 27 meanwhile. The height it is asked
    # for then rises from where it landed to the operator's at this rate.
    rise_m_s: float = 0.1


# THE PUSH, Nm of each knee's 3, the one setting for how high. Three seeds each, on
# launch_check.py's rig with the roll mode at its fit, MuJoCo, 8 November 2026: at 1.4 the
# wheels cleared 13-15 mm and the body rose 3-4 above where it stood, at 1.6 18-21 and
# 8-9, at 1.8 18-22 and 7-8, at 2.0 22-28 and 11-14, every run landing and standing,
# tilting up to 23 degrees, and 30 at 2.0; jd8 cleared 38 and rose 15, tilting 13. With
# the roll mode at twice its fit, the same. With the wheels' torque at 0.8 of asked, the
# IMU 40 ms late, the pack at 23.4 V and the legs' gain 0.9, three tries in five never
# came still in the crouch and stood up again, and the rest jumped and stood from 1.2 to
# 1.8; at 2.0 one fell. So it was held to 1.8 at most.
#
# With the brake's lead in proportion to the push (THE BRAKE), and the level push at the
# robot's 0.35 Nm, on the same rig: at 1.8 the wheels cleared 20-21 mm standing, 14-16 at
# 0.5 m/s and 12 at 1 m/s, the knees within 0.24 rad of straight; at 2.5 26-29 standing,
# 23-24 at 0.5 m/s and 20-26 braked from 1-1.4 m/s to 0.45, the knees no
# nearer than 0.49, the push 4 per cent either side of it so that the brake fell on either
# side of a loop's step; at 2.8 it cleared 32-34 standing but no more driving, the knees
# then at 2.8 of their 3 Nm. With the level push answered half as much and the wheels'
# floor friction as measured, as on the robot (JUMP_RUN_TOP_M_S), 2.5 cleared 21-23 mm
# standing, 20-22 at 0.5 m/s and 19-21 braked. So it is held to 2.5 at most, whatever is
# asked (session scratchpad jump_height/, 8 November 2026).
JUMP_PUSH_NM = 1.6
JUMP_PUSH_RANGE_NM = (1.0, 2.5)
# It jumps driving as it does standing: the crouch and the hold on the driving policy at
# the speed the operator asks, the wheels holding their speed over the floor through the
# push and the flight, and the robot handed back landing at it. It used to brake to a stop
# first, which put the take-off 1.5-2.3 s after a press at 0.5-1.4 m/s, and had it going
# 0.5 m/s a second after landing. On launch_check.py's rig, the driving policy told it
# leans 1.67 degrees per m/s, pressed at a full pull in fast mode, 1.8 m/s asked and 1.38
# held, it took off 0.41-0.46 s after the press and was going 1.36 m/s a second after
# landing; at 1.5, 1.0 and 0.5 asked likewise, every one of 8 standing, with the
# roll mode at twice its fit and on the worst rig (1.50 held there) as well, and with the
# trigger let go at the press or in the crouch. Turning, even at 0.5 rad/s and 0.5 m/s,
# MuJoCo's inner knee goes light, balance.py takes a wheel for off the floor and refuses
# the press; at 0.3 rad/s and 1 m/s it jumps, and straight on.
#
# On the robot on 8 November 2026, pushing 1.8 Nm at a level push of 0.35, jumps driving
# at 0.7 m/s and more landed about 4 degrees more nose-down than standing ones, which
# landed -10 to +10, median level; one of 34, rolling 1.05 m/s, landed about 10 nose-down,
# the driving policy drove both wheels to their ceiling, 51-52 rad/s, within 0.1 s and
# held them there while the robot tipped on to 30 degrees, and it fell forward. Rolling,
# the wheels have that much less to catch a nose-down landing with. MuJoCo lands driving
# jumps no more nose-down; given the wheels' friction on the floor as measured
# (docs/SYSID.md: 0.04 Nm and 0.004 Nm s/rad, where it has 0.03 and 0.002) and the level
# push answered half as much, as the robot answers it, it does, by 4-5 degrees at 1 m/s,
# and at 1.37 m/s it fell as the robot did, the wheels held at 52 rad/s while it tipped
# on. On that rig at 2.5 Nm it landed 0-3 degrees nose-up at 0-1 m/s; 10 degrees more
# nose-down, as the robot's worst landed, it stood at 0-1 m/s, its wheels at their
# ceiling from 0.7 m/s up and at 47-49 rad/s at 0.5; 14 degrees more, it stood at 0.5
# m/s and fell at 0.7 and at 1.0. So it jumped at up to 0.6 m/s, and a press faster than
# that was braked first, to 0.45 (session scratchpad jump_height/).
#
# On the robot at 17:25 that day, at 2.5 Nm, all 29 jumps stood, landing -8 to +13
# degrees nose-down at the hand-back, median +3, those pushing at 0.54-0.57 m/s among
# them; but of seven presses at 0.81-1.02 m/s, five were refused after 3 s of braking
# (JUMP_SLOWED_S), so that driving, it did not jump. Now it pushes at no more than
# JUMP_RUN_TOP_M_S; from the press until JUMP_SETTLE_S after the hand-back it is asked no
# more than JUMP_RUN_CAP_M_S, under which the driving policy rolls with room to rock (0.2
# m/s either side on the robot), so that a full pull is no run-up as it lands; a press
# under JUMP_RUN_BRAKE_M_S crouches at once, slowing to the cap as it goes down, and one
# faster brakes first, at its height; and the level push rises with the speed (JumpScript's
# THE LEVEL PUSH). On launch_check.py's rig with the robot's floor friction and its half
# answer to the level push, landing 10 degrees more nose-down than it does, three seeds
# each, at 0.5, 0.8, 0.9, 1.0, 1.2, 1.5 m/s asked and a full pull in fast mode, it pushed
# at 0.58-0.79 m/s and stood every time, its wheels at 28-52 rad/s after landing against
# their 51-52, at their ceiling once in 21; at 0.5 42-47, where they were 48-52 before.
# 14 degrees more, it stood every time, the wheels touching their ceiling at every speed,
# where before it fell once in three at 0.5 and at 0.8. Pressed at 0.98 m/s and
# crouching at once rather than braking, it pushed at 0.56-0.78 and landed up to 9
# degrees nose-down, the wheels at their ceiling once in three; braked, 2-3 and 35-41
# rad/s (session scratchpad jump_speed/, 8 November 2026).
#
# Asked less than the cap, the most it may push at comes down with what it is asked, to
# the cap's margin over that and no lower than JUMP_RUN_LOW_TOP_M_S (ScriptedJump's
# _push_top): the driving policy rocks either side of what it is asked and the hold goes
# at the first steady moment, which may be the top of a rock. On launch_check.py's rig at
# its worst, MuJoCo's own answer to the level push, asked 0.5 m/s, three seeds, under a
# flat 0.8 it pushed at 0.72-0.77, landed 21 degrees nose-up and went over backwards,
# where 0.6 had stood; held to 0.65 it pushed at 0.54-0.57 and stood, 13 nose-up.
#
# What this does not cure: on the worst rig with the robot's floor friction and half
# answer, landing 10 degrees more nose-down, every jump driving fell, whatever the speed
# it pushed at, 0.39 m/s as before as well as 0.62-0.77, though standing it stood. Before,
# presses faster than the top were refused there, as five of seven were on the robot; now
# they jump and fall. Nothing told the two apart that would not refuse the robot too:
# rolling spread in the crouch's last 0.4 s up to 0.62 m/s on the robot at 17:25 (session
# scratchpad jump_speed/hold_robot.py, 8 November 2026).
JUMP_RUN_TOP_M_S = 0.8
JUMP_RUN_CAP_M_S = 0.65
JUMP_RUN_BRAKE_M_S = 0.9
JUMP_RUN_LOW_TOP_M_S = 0.6
# How long braked before the crouch: at least JUMP_BRAKE_LEAST_S, and until over the last
# JUMP_SLOWED_S its speed over the floor has averaged under the top and spread less than
# JUMP_SLOWED_SPREAD_M_S. The driving policy takes a second or more to slow, and whether it
# is still slowing or already running up again as it pushes turns the landing: on that
# rig, pressed at a full pull in fast mode, 1.38 m/s, and braked to 1.0, it landed 0-6
# degrees nose-down 0.2 s under the top, the wheels at up to their ceiling, and 12 nose-up
# after 0.8 s, still slowing; braked to 0.45 on the worst rig, with the robot's floor
# friction, 9-10 nose-down after 0.5 s, running up again. So it waited for it to be steady
# as well, spread under JumpScript's steady_m_s, 0.15 m/s. But on the robot the driving
# policy is never that steady at 0.45-1.0 m/s: on 8 November 2026 at 17:25, asked a steady
# 0.45 it rocked 0.25-0.7 m/s about every 0.8 s, spreading 0.27-0.38 m/s over half a
# second, and 0.30-0.41 asked 1.0 at 21:05 the day before; braked from 0.8-1.0 it rose to
# 1.0-1.3 and fell to 0.13-0.33 in the first second, spreading 0.6-1.0. Five presses of
# seven were refused. Averaged and spread under 0.5, all seven would have gone on 1.0-1.8
# s after the press (session scratchpad jump_speed/brake_when.py). Braking for less, from
# 0.83 m/s to 0.65 on the rig with the robot's floor friction, it crouched 0.5 s in,
# pushed as it ran up again, and landing 14 degrees more nose-down fell twice in three.
JUMP_SLOWED_S = 0.5
JUMP_SLOWED_SPREAD_M_S = 0.5
JUMP_BRAKE_LEAST_S = 1.0
# THE BUTTON. The owner's, 8 November 2026: pressing A crouches, and letting it go jumps.
# gamepad.py sets bit 8 over the count of presses while A is held (balance.py's
# JUMP_HELD), and a press heard with it set waits in the hold, however long, on the
# driving policy at the operator's speed and turn, under JUMP_RUN_CAP_M_S, Trim and Hold
# acting as they do driving, until A is let go of; then it goes on as a press without it
# does, hold_most_s from then to be ready, and straight on. A press and a let-go between
# two of the controller's 50 Hz frames comes without the bit, and jumps at once, as every
# press did before. The controller's stream gone stale or not live while it waits is not
# a let-go: it stands up again, so a controller switched off or out of range never jumps
# the robot. Held in the hold past JUMP_SETTLE_S, the lift detector is on again, as it
# is for any crouch the D-pad asks for. On launch_check.py's rig (case 17, 8 November
# 2026) held 2-3 s, standing or driving and steering, it had landed and was handed back
# 0.19-0.22 s after the let-go and stood, on the worst rig as well; let go still
# steering, 0.30-0.36 s; picked up held, it was taken for lifted.


class ScriptedJump(TwoPolicies):
    """The driving policy, and a jump that is a script rather than a network, behind one
    balancer's face. The press, its refusals, and braking first under the speed cap are
    TwoPolicies', braking only past JUMP_RUN_BRAKE_M_S and only to JUMP_RUN_CAP_M_S; it is
    handed back as it lands, or as soon as anything stops the jump going ahead, and nothing
    here cuts a motor. Both legs are always sent the same command. A press with the button
    held waits for it to be let go of, `button` telling it each step (THE BUTTON, above).
    What happens goes into `events`, as TwoPolicies' does."""

    top_speed_m_s = JUMP_RUN_BRAKE_M_S
    run_top_m_s = JUMP_RUN_TOP_M_S
    cap_m_s = JUMP_RUN_CAP_M_S
    braked_s = JUMP_SLOWED_S
    braked_spread_m_s = JUMP_SLOWED_SPREAD_M_S

    def __init__(
        self,
        driving: Balancer,
        push: float = JUMP_PUSH_NM,
        script: JumpScript | None = None,
    ):
        self.driving = driving
        lo, hi = JUMP_PUSH_RANGE_NM
        self.push = min(max(float(push), lo), hi)
        self.script = script or JumpScript()
        self.events: list[str] = []
        self.reset()

    # -- a balancer's face: the driving policy's, which has the robot but for the legs and
    # wheels the script sends while it jumps

    @property
    def jump_meta(self) -> dict:
        return {"scripted": True, "push_nm": self.push} | dataclasses.asdict(
            self.script
        )

    @property
    def assist(self) -> bool:
        """Trim and Hold: driving, braking, and held in the crouch."""
        return self.state in ("drive", "braking") or self.waiting

    @property
    def speed_cap(self) -> float | None:
        """Under the cap from the press, braking or crouching, until JUMP_SETTLE_S after
        the hand-back (JUMP_RUN_TOP_M_S)."""
        if self.state != "drive" or self.waiting or self.since_back < JUMP_SETTLE_S:
            return self.cap_m_s
        return None

    @property
    def busy(self) -> bool:
        """TwoPolicies', but for a crouch held in the hold past JUMP_SETTLE_S, which a
        lift is told from as it is driving."""
        if self.waiting and self.phase == "hold" and self.pt >= JUMP_SETTLE_S:
            return False
        return super().busy

    @property
    def actions(self) -> np.ndarray:
        return self.driving.actions

    @property
    def last_wheels(self) -> tuple[float, float]:
        return self.driving.last_wheels

    @property
    def obs(self) -> np.ndarray:
        return self.driving.obs

    def reset(self) -> None:
        self.driving.reset()
        self.active = self.driving
        self.state, self.phase = "drive", ""
        self.t = self.pt = 0.0
        self.since_back = math.inf
        self.slow_for = 0.0
        self.legs: dict[str, st.Cmd] = {}
        self.wheels: tuple[float, float] = (0.0, 0.0)
        self.height = self.back_from = self.asked = 0.0
        self.speed_jump = 0.0
        self.braked: deque = deque(maxlen=round(self.braked_s / PERIOD_S))

        # Pressed with the button held, and not yet let go of; how long it has been
        # held; and whether both wheels carry weight, None if balance.py cannot tell.
        self.waiting = False
        self.held_s = 0.0
        self.loaded: bool | None = None

    def press(
        self, g, speed: float, loaded: bool | None, held: bool = False
    ) -> str | None:
        """TwoPolicies', and with the button held, waiting in the crouch for it to be let
        go of."""
        why = super().press(g, speed, loaded)
        if why is None and held:
            self.waiting, self.held_s = True, 0.0
            self.events.append("held: crouching until it is let go of")
        return why

    def button(self, held: bool | None, loaded: bool | None = None) -> None:
        """The jump button as balance.py hears it, each step before `observe`: True held,
        False let go of, None not known, the controller's stream stale or not live; and
        whether both wheels carry weight. Waiting, let go of it goes on to jump; not
        known, it stands up again."""
        self.loaded = loaded
        if not self.waiting:
            return
        if held:
            self.held_s += PERIOD_S
            return
        self.waiting = False
        where = (
            "braking"
            if self.state == "braking"
            else "on the way down"
            if self.phase == "crouch"
            else "in the crouch"
        )
        if held is None:
            why = (
                f": the controller went quiet with A held {self.held_s:.2f} s, {where}"
            )
            if self.state == "braking":
                self.state, self.t = "drive", 0.0
                self.events.append("stopped braking" + why)
            else:
                self._hand_back(why)
            return
        self.events.append(f"let go after {self.held_s:.2f} s, {where}")

    def _braking(self, fb: dict, w) -> None:
        """On to the crouch once its speed over the floor has, over the last `braked_s`,
        averaged under the top and spread less than `braked_spread_m_s`, so that it has
        done slowing, or given up. The hold waits for under the top as it pushes."""
        rolling = ground_speed(fb, float(w[1]), self.meta["wheel_radius"])
        if self.t <= 1.5 * PERIOD_S:
            self.braked.clear()
        self.braked.append(rolling)
        steady = (
            self.t >= JUMP_BRAKE_LEAST_S
            and len(self.braked) == self.braked.maxlen
            and abs(float(np.mean(self.braked))) < self.run_top_m_s
            and max(self.braked) - min(self.braked) < self.braked_spread_m_s
        )
        if steady:
            self._crouch()
        elif self.t > JUMP_BRAKE_GIVE_UP_S:
            self.state, self.t = "drive", 0.0
            # Given up braking: nothing more to wait for.
            self.waiting = False
            self.events.append(
                f"refused: still at {rolling:+.2f} m/s after "
                f"{JUMP_BRAKE_GIVE_UP_S:g} s of braking"
            )

    def _crouch(self) -> None:
        self.state, self.t = "crouch", 0.0
        self.phase, self.pt = "crouch", 0.0
        self.start = None
        self.legs = {}
        self.events.append(
            f"crouching to {self.script.crouch_m * 1000:.0f} mm on the driving policy"
        )

    def _hand_back(self, why: str = "") -> None:
        d = self.driving
        if self.legs:
            # It is told it asked for what the script last did, as a hand-over between two
            # policies tells the incoming one.
            asked = np.array([self.legs[j].p for j in st.LEGS], dtype=np.float32)
            d.actions[:4] = np.clip((asked - d.crouch) / d.leg_scale, -1.0, 1.0)
            d.actions[4:6] = np.clip(np.array(self.wheels) / d.wheel_scale, -1.0, 1.0)
            d.last_wheels = self.wheels
        self.state, self.phase, self.t = "drive", "", 0.0
        self.since_back = 0.0
        self.back_from = self.height
        self.legs = {}
        self.waiting = False
        self.events.append("handed back to the driving policy" + why)

    def observe(self, fb: dict, w, g, speed: float, turn: float, height: float):
        self.t += PERIOD_S
        self.since_back += PERIOD_S
        self.asked = height
        if self.state == "braking":
            turn = 0.0
            self._braking(fb, w)
        if self.state in ("crouch", "jump"):
            self._script(fb, np.asarray(w, dtype=float), np.asarray(g, dtype=float))
        lo, hi = self.driving.meta["height_range"]
        if self.state in ("crouch", "jump"):
            # Driving, it goes on at the operator's speed until the push, no faster than
            # the cap, and is told the speed it pushed at until it lands; straight
            # on, whatever turn is asked, but for the turn asked while the button is held.
            if self.phase in ("crouch", "hold"):
                self.speed_jump = min(max(speed, -self.cap_m_s), self.cap_m_s)
            speed, turn = self.speed_jump, turn if self.waiting else 0.0
            height = min(max(self.height, lo), hi)
        elif self.since_back < (hi - lo) / self.script.rise_m_s:
            rose = self.back_from + self.script.rise_m_s * self.since_back
            height = min(height, max(rose, lo))
        return self.driving.observe(fb, w, g, speed, turn, height)

    def decide(self, obs: np.ndarray) -> dict[str, st.Cmd]:
        d = self.driving
        if not self.legs:
            return d.decide(obs)
        cmds = dict(self.legs)
        for k, j in enumerate(st.WHEELS):
            cmds[j] = st.Cmd(t=float(self.wheels[k]))
        return cmds

    # -- the script

    def _script(self, fb: dict, w: np.ndarray, g: np.ndarray) -> None:
        s = self.script
        self.pt += PERIOD_S
        hip = (fb["hip_pitch_right"].p + fb["hip_pitch_left"].p) / 2.0
        knee = (fb["knee_right"].p + fb["knee_left"].p) / 2.0
        knee_v = (fb["knee_right"].v + fb["knee_left"].v) / 2.0
        knee_nm = (fb["knee_right"].tau + fb["knee_left"].tau) / 2.0
        up = np.array([-g[0], -g[2]]) / max(math.hypot(g[0], g[2]), 1e-6)
        if self.phase in ("crouch", "hold") and math.degrees(tilt(g)) > JUMP_TILT_DEG:
            self._hand_back(f": tilted {math.degrees(tilt(g)):.0f} degrees crouching")
            return
        if self.phase == "crouch":
            if self.start is None:
                self.start = self.asked
            self.height = max(s.crouch_m, self.start - s.crouch_rate_m_s * self.pt)
            low = float(np.mean(leg_heights(fb)))
            if low <= s.crouch_m + s.crouch_tolerance_m or self.pt >= s.crouch_s:
                self.phase, self.pt = "hold", 0.0
                self.ready_for = self.free_s = 0.0
                self.ups: deque = deque(maxlen=5)
                self.rolls: deque = deque(maxlen=round(s.ready_s / PERIOD_S) + 1)
            return
        if self.phase == "hold":
            self.ups.append(up)
            rolling = ground_speed(fb, float(w[1]), self.driving.meta["wheel_radius"])
            self.rolls.append(rolling)
            over = off_balance(hip, knee, up)
            yaw = float(np.dot(w, g)) / max(float(np.linalg.norm(g)), 1e-6)
            ready = (
                abs(w[1]) < s.calm_rad_s
                and abs(yaw) < s.calm_yaw_rad_s
                and self.loaded is not False
                and max(self.rolls) - min(self.rolls) < s.steady_m_s
                and abs(over) < s.over_m
                and abs(rolling) < self._push_top()
            )
            self.ready_for = self.ready_for + PERIOD_S if ready else 0.0
            # Held, it waits however long; let go of, hold_most_s from then at most.
            if self.waiting:
                return
            self.free_s += PERIOD_S
            if self.pt >= s.hold_s and self.ready_for >= s.ready_s:
                self._plan(fb, w, hip, knee, rolling)
            elif self.free_s >= s.hold_most_s:
                light = "" if self.loaded is not False else ", a wheel light"
                self._hand_back(
                    f": never steady in the crouch, turning {w[1]:+.1f} rad/s and "
                    f"{yaw:+.1f} about the vertical, rolling {rolling:+.2f} m/s, "
                    f"{over * 1000:+.0f} mm off balance{light}"
                )
                return
            else:
                return
        if self.phase == "push":
            ahead = knee + knee_v * self.brake_lead
            if ahead > self.brake_knee and self.pt < s.push_most_s:
                self._push(hip, knee)
                self._wheels(fb, w)
                return
            # The body leaves at about the legs' rate of extending now.
            rising = max(-knee_v * LEG_LINK_M * math.sin(knee / 2.0), 0.0)
            self.flight_s = 2.0 * s.leaves * rising / GRAVITY_M_S2
            self.events.append(
                f"braking at {-axle_at(hip, knee)[1] * 1000:.0f} mm, rising "
                f"{rising:.2f} m/s"
            )
            self.phase, self.pt = "brake", 0.0
        if self.phase == "brake":
            self._legs(s.takeoff_m, 0.0, s.brake_kp, s.brake_kd)
            self._wheels(fb, w)
            if self.pt >= s.brake_s:
                self.phase, self.pt = "flight", 0.0
            return
        # The flight.
        k = st.min_jerk((self.pt + s.lead_s) / s.tuck_s)
        rate = (s.land_m - s.takeoff_m) * min_jerk_rate((self.pt + s.lead_s) / s.tuck_s)
        h = s.takeoff_m + (s.land_m - s.takeoff_m) * k
        self._legs(h, rate / s.tuck_s, s.air_kp, s.air_kd)
        self._wheels(fb, w)
        asked = self.legs["knee_right"]
        fold = knee_v - asked.v
        past = knee - asked.p
        pressed = (
            knee_nm < -s.touch_nm
            or (past > s.touch_rad and fold > 0.0)
            or (past > s.touch_past_rad and fold > s.touch_rad_s)
        )
        if self.pt >= s.earliest * self.flight_s and pressed:
            self._hand_back(
                f": landed {self.pt:.2f} s into the flight, the knees at "
                f"{knee_nm:+.2f} Nm, {past:+.2f} rad past and folding {fold:+.1f} rad/s"
            )
        elif self.pt >= s.latest * self.flight_s + s.latest_s:
            self._hand_back(f": no landing felt in {self.pt:.2f} s, taken as landed")

    def _push_top(self) -> float:
        """The fastest it may push at, for the speed it is being asked for: the operator's,
        under the cap, plus what the top allows over the cap for rocking; but never less
        than JUMP_RUN_LOW_TOP_M_S."""
        over_cap = self.run_top_m_s - self.cap_m_s
        return min(
            self.run_top_m_s,
            max(JUMP_RUN_LOW_TOP_M_S, abs(self.speed_jump) + over_cap),
        )

    def _plan(
        self, fb: dict, w: np.ndarray, hip: float, knee: float, rolling: float
    ) -> None:
        """The push's path: for each height, the axle's place forward of the hip that keeps
        the centre of mass straight above it along the IMU's up now; and the level push,
        for where the centre of mass is now."""
        s = self.script
        up = np.mean(np.asarray(self.ups), axis=0)
        self.aim = up / float(np.linalg.norm(up))
        h0 = -axle_at(hip, knee)[1]
        over = off_balance(hip, knee, self.aim)
        # The centre of mass's share and the speed's are in proportion to the level push
        # as set, as the robot's answer to all of it is (THE LEVEL PUSH).
        faster = math.copysign(max(abs(rolling) - s.level_from_m_s, 0.0), rolling)
        level = (
            s.level_nm * (1.0 + s.level_per_m_s * faster)
            + s.level_nm_per_m * over * s.level_nm / JumpScript.level_nm
        )
        self.level = level * self.push / JUMP_PUSH_NM
        self.brake_lead = s.brake_lead_s * self.push / JUMP_PUSH_NM
        self.heights = np.linspace(min(h0, s.land_m) - 0.005, s.takeoff_m + 0.005, 16)
        self.forwards = np.array([under_mass(h, self.aim) for h in self.heights])
        self.brake_knee = leg_for(self._along(s.takeoff_m), s.takeoff_m)[1]
        self.spin0 = self._spins(fb, w)
        self.knee_rate = self.knee_accel = 0.0
        self.flight_s = 0.0
        self.phase, self.pt = "push", 0.0
        self.state, self.t = "jump", 0.0
        self.events.append(
            f"jump: legs at {h0 * 1000:.0f} mm, {over * 1000:+.0f} mm off balance, "
            f"rolling {rolling:+.2f} m/s, pushing {self.push:.1f} Nm to "
            f"{s.takeoff_m * 1000:.0f} mm, the wheels {self.level:+.2f} Nm"
        )

    def _along(self, h: float) -> float:
        return float(np.interp(h, self.heights, self.forwards))

    def _push(self, hip: float, knee: float) -> None:
        """The knees' torque, and the hips keeping the axles on the path for the knees as
        they are, with their share of the same force."""
        s = self.script
        self._legs(
            -axle_at(hip, knee)[1], 0.0, s.hip_kp, s.hip_kd, knee_now=(knee, 0.0)
        )
        hip_c = self.legs["hip_pitch_right"]
        jac = leg_jacobian(hip_c.p, knee)
        ux, uz = self.aim
        force = self.push / max(jac[0, 1] * ux + jac[1, 1] * uz, 1e-3)
        hip_nm = -(jac[0, 0] * ux + jac[1, 0] * uz) * force
        hip_nm = min(max(hip_nm, -st.PEAK_NM), st.PEAK_NM)
        hips = dataclasses.replace(hip_c, t=float(hip_nm))
        knees = st.Cmd(p=knee, t=-self.push)
        self.legs = {j: hips if "hip" in j else knees for j in st.LEGS}

    def _legs(self, h, h_rate, kp, kd, knee_now=None) -> None:
        """Both legs to height h on the path, rising at h_rate. With `knee_now`, the knees'
        angle and rate as measured, the hips keep the axles on the path for that knee
        rather than for the one asked, and move with it."""
        dt = 1e-3
        hip, knee = leg_for(self._along(h), h)
        hip2, knee2 = leg_for(self._along(h + h_rate * dt), h + h_rate * dt)
        hip_v, knee_v = (hip2 - hip) / dt, (knee2 - knee) / dt
        if knee_now is not None:
            angle, rate = knee_now
            down = 2.0 * LEG_LINK_M * math.cos(angle / 2.0)
            down *= math.cos(math.atan2(self._along(down), down))
            hip = math.atan2(self._along(down), down) + angle / 2.0
            hip_v = rate / 2.0
        self.height = h
        self.knee_accel = (knee_v - self.knee_rate) / PERIOD_S
        self.knee_rate = knee_v
        self.legs = {
            j: st.Cmd(p=hip, v=hip_v, kp=kp, kd=kd)
            if "hip" in j
            else st.Cmd(p=knee, v=knee_v, kp=kp, kd=kd)
            for j in st.LEGS
        }

    def _wheels(self, fb: dict, w: np.ndarray) -> None:
        """Each wheel's spin against the world held, and as the legs are asked to fold or
        straighten, each wheel's rotor turned with its shin by its motor; and through the
        push, the level push forward."""
        s = self.script
        ff = -FREE_WHEEL_KG_M2 * self.knee_accel / 2.0
        if self.phase == "push":
            ff += self.level
        spins = self._spins(fb, w)
        self.wheels = tuple(
            ff - s.spin_kd * (spin - spin0) for spin, spin0 in zip(spins, self.spin0)
        )

    def _spins(self, fb: dict, w: np.ndarray) -> tuple[float, float]:
        """Each wheel's spin against the world, as ground_speed has it."""
        return tuple(
            float(w[1]) - fb[hip].v + fb[knee].v + fb[wheel].v
            for hip, knee, wheel in FREE_WHEEL_JOINTS
        )


def min_jerk_rate(s: float) -> float:
    """st.min_jerk's slope at s."""
    s = min(max(s, 0.0), 1.0)
    return 30.0 * s * s * (1.0 - s) * (1.0 - s)


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

    Asked for nothing, the policy trained from scratch on 2026-11-05 creeps backwards at
    0.046 m/s in MuJoCo, and on the robot up to 0.084: faster than SLOWED_M_S was, so that it never counted as
    stopped, and with nothing to hold it went 590 mm in 13 s. So it counts as stopped
    under a looser SLOWED_M_S, or after SLOWED_S whatever, and what it creeps at,
    standing, is learned the way Trim learns while driving and asked against, held
    from one stop to the next since the creep is the policy's own.
    """

    HEADING_BAND_RAD = (math.radians(2.0), math.radians(6.0))
    PLACE_BAND_M = (0.05, 0.15)
    HEADING_GAIN = 1.5
    PLACE_GAIN = 0.3
    MAX_TURN_RAD_S = 0.3
    MAX_SPEED_M_S = 0.1
    # Under both of these it has stopped, and whatever it does now is drift; or this long
    # after it was let go of, whatever it is doing.
    SLOWED_M_S = 0.08
    SLOWED_RAD_S = 0.2
    SLOWED_S = 1.5
    # Never before this, as at a take-over, and never while it twists faster than this.
    # On the robot on 2026-11-07 at 18:02 a take-over twisted it side to side about three
    # times a second, growing to 13 rad/s until it fell, and the hold, counting from the
    # first step, learned the twist as creep and turned back against it at its whole 0.5
    # rad/s, flipping sides with each swing; standing, the turn rate stays under 0.2.
    LEAST_WAIT_S = 1.0
    TWISTING_RAD_S = 0.5
    # What it creeps at standing, learned with these time constants' inverses.
    CREEP_SPEED_GAIN = 0.5
    CREEP_TURN_GAIN = 1.0
    # On the robot on 2026-11-06 it crept at up to 0.084 m/s, 4.8 m in a minute.
    MAX_CREEP_M_S = 0.15
    MAX_CREEP_RAD_S = 0.2

    def __init__(self, wheel_radius: float):
        self.wheel_radius = wheel_radius
        self.holding = False
        self.slowed = False
        self.heading = self.rolled = 0.0
        self.turning = self.moving = False
        self.creep_speed = self.creep_turn = 0.0
        self.waited = 0.0

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
            self.waited = 0.0
        turning = -float(np.dot(w, g))
        rolling = ground_speed(fb, float(w[1]), self.wheel_radius)
        if not self.slowed:
            self.waited += dt
            self.slowed = self.waited >= self.LEAST_WAIT_S and (
                self.waited >= self.SLOWED_S
                or (abs(rolling) < self.SLOWED_M_S and abs(turning) < self.SLOWED_RAD_S)
            )
            return 0.0, 0.0
        if abs(turning) > self.TWISTING_RAD_S:
            # Not drift: nothing is counted or learned, and nothing asked, until it calms.
            return 0.0, 0.0
        cap = self.MAX_CREEP_M_S
        self.creep_speed -= self.CREEP_SPEED_GAIN * rolling * dt
        self.creep_speed = min(max(self.creep_speed, -cap), cap)
        cap = self.MAX_CREEP_RAD_S
        self.creep_turn -= self.CREEP_TURN_GAIN * turning * dt
        self.creep_turn = min(max(self.creep_turn, -cap), cap)
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
            (back_speed if self.moving else 0.0) + self.creep_speed,
            (back_turn if self.turning else 0.0) + self.creep_turn,
        )


# A second test of being lifted, beside Touch's knees. Off the floor a wheel turns as its
# own motor pushes it, against nothing but its own inertia and friction; on the floor the
# same torque has the robot to move. So each step, for each wheel, the change in its spin
# against the ground (the joint's, plus the shin's and the torso's pitching, as
# ground_speed has it) is compared with the change a free wheel would have made on the
# torque its motor reports. Touch's knees miss a lift once the policy has straightened
# the legs: hanging at their lower limit the knees hold the shins up the same way the
# robot's weight pushes, and read 0.13-0.25 Nm from the air's reading at the crouch,
# never under LIFT_LIGHT_NM. On the robot on 2026-11-07 that left four of seven lifts
# undetected until stopped, one for 12 s, the policy driving the wheels to their 55 rad/s
# in the air; this caught six of the seven 0.50-0.72 s after the wheels left the floor,
# and over about 900 s of standing and driving in the same logs, two hard knocks and a
# bump at 1 m/s among them, came to 0.24 of FREE_SURE_S at most.
FREE_WHEEL_JOINTS = (
    ("hip_pitch_right", "knee_right", "wheel_drive_right"),
    ("hip_pitch_left", "knee_left", "wheel_drive_left"),
)

# A free wheel, fitted on the robot's logs of 2026-11-07 over the four lifts of 15:25
# and 18:02 in which both wheels spun in the air (R2 0.78 to 0.96): 4.3e-4 to 4.8e-4
# kg m2 on its joint, 0.01 to 0.07 Nm of dry friction, and 0.0005 to 0.0024 Nm per rad/s
# of drag, the middle of which is taken.
FREE_WHEEL_KG_M2 = 4.5e-4
FREE_WHEEL_DRY_NM = 0.03
FREE_WHEEL_DRAG_NM_PER_RAD_S = 0.0015
# Over the last FREE_STEPS policy steps, the regression of each wheel's measured change
# in spin on a free wheel's. In the air it came to 1.0 (the lifts' median); on the floor
# 0.1 to 0.3, over 900 s of standing, driving to 1.5 m/s and spinning on the spot.
FREE_STEPS = 10
FREE_AT = 0.75
FLOOR_AT = 0.5
# Below this much a free wheel would have changed speed over the window, rad/s, the
# window says nothing: standing still, the torques are too small to tell apart.
FREE_LEAST_RAD_S = 2.0
# Above this the drag, which is the least certain part, is most of what a free wheel
# would do, and at the supply's limit, 50 to 55 rad/s, a free wheel holds its speed on
# its friction: a wheel that does not speed up there says nothing of the floor, though
# one that turns as a free wheel still says it is free. (MuJoCo's wheels carry 2.7 times
# this drag, and held at 45 rad/s in the air looked like the floor without it.)
FREE_FASTEST_RAD_S = 40.0
# Seconds of a wheel turning free with neither on the floor, less FREE_FORGET times the
# seconds of one on the floor, before it counts. Over the logs of 6 and 7 November bumps,
# two hard knocks and a 15 Hz shake in a deep crouch came to 0.24 at most; the lifts
# reached this 0.5 to 0.72 s after leaving the floor. A wheel on the floor outvotes the
# other's looking free: in a hard turn at 1.3 m/s at 20:12 on 8 November 2026 the inside
# wheel turned as a free one for 0.4 s, grip lost or off the floor, with the outside one
# plainly on it, and taken for a lift the wheels were braked and it fell. Replayed so,
# that run came to 0.12 at most, and the runs of 7 and 8 November were caught at the same
# moments, to 0.04 s, but for two in the chattering run of 08:57 on the 8th which the old
# rule's own stop cuts short, so which the replay cannot follow.
FREE_SURE_S = 0.4
FREE_FORGET = 2.0


class FreeWheels:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.spins = [deque(maxlen=FREE_STEPS + 1) for _ in FREE_WHEEL_JOINTS]
        self.pushes = [deque(maxlen=FREE_STEPS + 1) for _ in FREE_WHEEL_JOINTS]
        self.speeds = [deque(maxlen=FREE_STEPS + 1) for _ in FREE_WHEEL_JOINTS]
        self.sure = 0.0
        self.last: float | None = None
        self.said: list[int] = [0, 0]

    def _one(self, k: int, fb: dict, pitch_rate: float, dt: float) -> int:
        """+1 if this wheel has been turning as a free one, -1 as one on the floor."""
        hip, knee, wheel = FREE_WHEEL_JOINTS[k]
        v = fb[wheel].v
        q = fb[wheel].tau
        if abs(v) > 1.0:
            q -= FREE_WHEEL_DRY_NM * np.sign(v) + FREE_WHEEL_DRAG_NM_PER_RAD_S * v
        self.spins[k].append(pitch_rate - fb[hip].v + fb[knee].v + v)
        self.pushes[k].append(q / FREE_WHEEL_KG_M2 * dt)
        self.speeds[k].append(abs(v))
        if len(self.spins[k]) <= FREE_STEPS:
            return 0
        moved = np.diff(np.asarray(self.spins[k]))
        pushed = np.asarray(self.pushes[k])[1:]
        sq = float(pushed @ pushed)
        if sq < FREE_LEAST_RAD_S**2:
            return 0
        share = float(moved @ pushed) / sq
        if share >= FREE_AT:
            return 1
        if share <= FLOOR_AT and max(self.speeds[k]) <= FREE_FASTEST_RAD_S:
            return -1
        return 0

    def update(self, fb: dict, pitch_rate: float, now: float) -> bool:
        """Whether a wheel has been turning as a free one for long enough. `now` is the
        step's own time: a step seen again (one that raised) is not counted twice."""
        if self.last is not None and now <= self.last:
            return self.sure >= FREE_SURE_S
        dt = 0.01 if self.last is None else min(max(now - self.last, 0.004), 0.05)
        self.last = now
        said = [self._one(k, fb, pitch_rate, dt) for k in range(len(FREE_WHEEL_JOINTS))]
        self.said = said
        if min(said) < 0:
            self.sure -= FREE_FORGET * dt
        elif max(said) > 0:
            self.sure += dt
        self.sure = min(max(self.sure, 0.0), 1.0)
        return self.sure >= FREE_SURE_S


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
        self.light_spin = 0.0
        self.wheels = FreeWheels()
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
        self.wheels.reset()
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
            self.light_spin = spin
        self.light_spin = min(self.light_spin, spin)
        light = now - self.light_since
        least = LIFT_EARLY_SPIN_RAD_S if running_s < LIFT_EARLY_S else LIFT_SPIN_RAD_S
        speeding = spin > self.light_spin + LIFT_SPEEDING_UP_RAD_S
        return light >= LIFT_SURE_S or (
            light >= LIFT_CONFIRM_S and spin > least and speeding
        )


# ---- what stops it ---------------------------------------------------------------


def limits(legs_limp: bool = False, wheel_vmax: float = WHEEL_VMAX) -> st.Limits:
    """A motor that faults, overheats, overspeeds or stops answering, and a leg
    out of its window, as every test on the robot has it. Legs nobody is
    commanding can be anywhere."""
    speed = {j: st.LEG_SPEED_CAP for j in st.LEGS}
    speed.update({j: wheel_vmax - WHEEL_MARGIN_RAD_S for j in st.WHEELS})
    return st.Limits(speed=speed, windows={} if legs_limp else dict(st.WINDOWS))


class Tipped(st.Abort):
    """Fallen over, or a leg driven out of its place: nothing wrong with the robot, and
    a launch waits to be picked up again."""


class Lost(st.Abort):
    """Driving, a sensor has been silent for too long to balance on. A launch lets the
    robot down gently, and waits to be picked up again."""


class Guard:
    """What stops a run. With `free` set, nothing is standing and nothing is being
    driven, so a robot may be carried at any angle and its limp legs swing as they
    like: only a motor's own faults count, and a sensor gone quiet is waited for.

    With `recover` set, it is armed and driving, and only lying on the floor stops it,
    past FALLEN_DEG, or a sensor gone for LOST_S. Everything else is put in `trouble`,
    for the stepper to deal with: a motor's fault, by clearing it; a wheel too fast or a
    winding too hot, by slowing; a reading late, or a leg out of its place or too
    fast, by carrying on."""

    def __init__(self, tilt_deg: float, lim: st.Limits):
        self.tilt_rad = math.radians(tilt_deg)
        self.windows = lim.windows
        self.free = False
        self.recover = False
        self.speed = lim.speed
        self.hot_c = lim.hot_c
        self.stale_s = lim.stale_s
        self.motors = st.Sequencer(
            [], dataclasses.replace(lim, windows={}, speed={}), st.JOINTS
        )
        self.trouble: dict[str, str] = {}
        self.faulted: set[str] = set()
        self.slow_down = False

    def sensors(self, now: float, rig) -> tuple[list, list]:
        readings = []
        for report in ("gyro", "gravity"):
            heard = rig.imu.get(report)
            age = math.inf if heard is None else now - heard[0]
            if age > IMU_STALE_S:
                words = f"IMU: no {report} report for {IMU_STALE_S * 1000:.0f} ms"
                if heard is None or not (self.free or self.recover):
                    raise st.Abort(words)
                if self.recover and age > LOST_S:
                    raise Lost(f"IMU: no {report} report for {age * 1000:.0f} ms")
                self.trouble["imu"] = words
            readings.append(heard[1])
        return readings[0], readings[1]

    def check(self, now: float, fb: dict, g: np.ndarray) -> None:
        if self.recover:
            self.weather(now, fb, g)
            return
        if self.free:
            # Carried or waiting: a report gone quiet is waited for, a fault is not.
            fresh = {j: f for j, f in fb.items() if now - f.at <= self.stale_s}
            for j in st.JOINTS:
                if j in fb and j not in fresh:
                    fresh[j] = dataclasses.replace(fb[j], at=now)
            self.motors.check(now, fresh)
            return
        self.motors.check(now, fb)
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

    def weather(self, now: float, fb: dict, g: np.ndarray) -> None:
        """Armed and driving: what is wrong, kept rather than acted on, but for lying
        down and a motor gone silent for LOST_S."""
        trouble = self.trouble
        self.faulted = set()
        self.slow_down = False
        for j in st.JOINTS:
            f = fb.get(j)
            if f is None:
                raise Lost(f"{j}: never heard")
            age = now - f.at
            if age > LOST_S:
                raise Lost(f"{j}: no report for {age * 1000:.0f} ms")
            if age > self.stale_s:
                trouble[j] = f"no report for {self.stale_s * 1000:.0f} ms"
            if f.state >= 0x8:
                self.faulted.add(j)
                trouble[j] = f"motor fault, state {f.state:X}"
            if f.t_rotor >= self.hot_c:
                self.slow_down = True
                trouble[j] = f"winding at {f.t_rotor} C"
            cap = self.speed.get(j)
            if cap is not None and abs(f.v) > cap:
                trouble[j] = f"{f.v:+.1f} rad/s, past the {cap:g} cap"
            window = self.windows.get(j)
            if window and not window[0] <= f.p <= window[1]:
                trouble[j] = f"at {f.p:+.3f} rad, outside {window}"
        angle = tilt(g)
        if angle > math.radians(FALLEN_DEG):
            raise Tipped(
                f"tilted {math.degrees(angle):.0f} degrees, past {FALLEN_DEG:g}"
            )
        if angle > self.tilt_rad:
            trouble["tilt"] = f"tilted {math.degrees(angle):.0f} degrees"


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
        self.attitude = Attitude(imu)
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
        # Armed and driving: what slows the command, from 1 for nothing to 0 for all.
        self.govern = 1.0
        self.revived_at: dict[str, float] = {}
        self.said: set[str] = set()
        self.recoveries: list[str] = []
        self.assisted = True

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
        self.guard.trouble = {}
        gyro, gravity = self.guard.sensors(now, self.rig)
        w, g = self.attitude.read(now, gyro, gravity)
        if self.attitude.doubted_for > 0.0:
            self.guard.trouble["imu gravity"] = (
                f"IMU: gravity {self.attitude.why}: carried on the gyro"
            )
            if self.attitude.doubted_for > GYRO_CARRY_S:
                if self.guard.recover:
                    raise Lost(
                        f"IMU: gravity not believable for "
                        f"{self.attitude.doubted_for:.1f} s"
                    )
                self.attitude.believe_anyway()
        self.guard.check(now, fb, g)
        if self.guard.recover:
            self.revive(now)
        self.tell(now)
        return now, fb, w, g

    def revive(self, now: float) -> None:
        """A motor in a fault state is disabled, and on the floor at speed that is a
        fall: it is cleared, and on the next try enabled, while the rest drive on."""
        for j in self.guard.faulted:
            if now - self.revived_at.get(j, -1.0) < REVIVE_S:
                continue
            first = j not in self.revived_at or now - self.revived_at[j] > 1.0
            self.revived_at[j] = now
            try:
                if first:
                    self.rig.clear_fault(j)
                else:
                    self.rig.wake(j)
            except (AttributeError, OSError):
                pass

    def tell(self, now: float) -> None:
        """Each kind of trouble once, as it starts, into the log."""
        trouble = self.guard.trouble
        for name, words in trouble.items():
            if name not in self.said:
                text = f"{name}: {words}" if not words.startswith(name) else words
                self.recoveries.append(text)
                if self.writer:
                    self.writer.write(
                        {"k": "n", "h": round(now, 6), "recovering": text}
                    )
        self.said = set(trouble)

    def governed(self, fb: dict, speed: float, turn: float) -> tuple[float, float]:
        """Slowing what is asked while a wheel is too fast or a winding too hot, and
        coming back once neither is."""
        cap = min(self.guard.speed.get(j, math.inf) for j in st.WHEELS)
        soft = cap - WHEEL_GOVERN_BELOW_CAP
        fastest = max(abs(fb[j].v) for j in st.WHEELS if j in fb)
        if fastest > soft or self.guard.slow_down:
            self.govern = max(0.0, self.govern - GOVERN_PER_S * PERIOD_S)
        elif fastest < soft - GOVERN_BAND:
            self.govern = min(1.0, self.govern + GOVERN_PER_S * PERIOD_S)
        return speed * self.govern, turn * self.govern

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
                words = f"a step took {gap * 1000:.0f} ms"
                if not self.guard.recover:
                    raise st.Abort(words)
                self.recoveries.append(words)
                if self.writer:
                    self.writer.write(
                        {"k": "n", "h": round(now, 6), "recovering": words}
                    )
        self.last_step = now
        self.waits.append(now - self.asked_at)
        self.ages.append(now - min(fb[j].at for j in st.JOINTS))
        if not self.heard_all():
            self.missed += 1
        asked_speed, asked_turn = speed, turn
        speed, turn = self.governed(fb, speed, turn)
        # A jump policy has the robot: what Trim and Hold learned is the driving
        # policy's, and the jump moves it. Back from one, they start afresh.
        assist = getattr(self.balancer, "assist", True)
        if assist and not self.assisted:
            if self.trim is not None:
                self.trim.reset()
            if self.hold is not None:
                self.hold.holding = False
        self.assisted = assist
        if self.trim is not None and assist:
            speed, turn = self.trim.command(speed, turn, fb, w, g, PERIOD_S)
        if self.hold is not None and assist:
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
