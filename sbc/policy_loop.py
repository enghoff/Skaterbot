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
# Judged as each new report comes in, against the last one believed turned on by the gyro
# since: a jump turns the torso at 10 rad/s, and the chip's gravity comes 30 to 60 times
# a second and later than its gyro, so a closer mark doubted good reports in MuJoCo.
GRAVITY_JUMP_RAD = math.radians(25.0)
GYRO_CARRY_S = 1.5
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
        elif abs(length - GRAVITY_M_S2) > GRAVITY_LENGTH_TOLERANCE * GRAVITY_M_S2:
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
        return None if self.state == "drive" else JUMP_SPEED_CAP_M_S

    def press(self, g, speed: float, loaded: bool | None) -> str | None:
        """A press of the jump button. None if it is taken up, or why not."""
        if self.state != "drive":
            doing = "braking for" if self.state == "braking" else "in"
            return f"already {doing} a jump"
        if g is not None and math.degrees(tilt(g)) > JUMP_TILT_DEG:
            return f"tilted {math.degrees(tilt(g)):.0f} degrees"
        if loaded is False:
            return "a wheel is not on the floor"
        self.t = 0.0
        if abs(speed) > JUMP_TOP_SPEED_M_S:
            self.state = "braking"
            self.slow_for = 0.0
            self.events.append(f"pressed at {speed:+.2f} m/s: braking first")
            return None
        self.events.append(f"pressed at {speed:+.2f} m/s")
        self._crouch()
        return None

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

    def observe(self, fb: dict, w, g, speed: float, turn: float, height: float):
        self.t += PERIOD_S
        self.since_back += PERIOD_S
        if self.state == "braking":
            rolling = ground_speed(fb, float(w[1]), self.meta["wheel_radius"])
            self.slow_for = (
                self.slow_for + PERIOD_S if abs(rolling) < JUMP_TOP_SPEED_M_S else 0.0
            )
            if self.slow_for >= JUMP_BRAKED_S:
                self._crouch()
            elif self.t > JUMP_BRAKE_GIVE_UP_S:
                self.state, self.t = "drive", 0.0
                self.events.append(
                    f"refused: still at {rolling:+.2f} m/s after "
                    f"{JUMP_BRAKE_GIVE_UP_S:g} s of braking"
                )
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
            self.slowed = self.waited >= self.SLOWED_S or (
                abs(rolling) < self.SLOWED_M_S and abs(turning) < self.SLOWED_RAD_S
            )
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
