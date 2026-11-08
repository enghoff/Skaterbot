# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy>=1.26", "mujoco>=3.2", "onnxruntime>=1.18", "pyyaml>=6.0",
#                 "pygame>=2.5", "pyserial>=3.5"]
# ///
"""A hand lowers the robot and lets go, and sbc/balance.py has to catch it, in MuJoCo.

    uv run simulation/mujoco/launch_check.py
    uv run simulation/mujoco/launch_check.py --quick

This runs balance.py's own `powered`, with its clock and its stepper pointed at the
simulated robot of balance_check.py, so what is tested is what the robot runs. All it
adds is a hand on the torso, moved by a script, which can carry the robot's weight,
steady it, or both. It fails if any of these goes wrong:

1. Lowered and let go, in the ways a person might, it stands.
2. Handled in the air, shaken and tipped, it does not start.
3. Put down on one wheel, it waits for the other.
4. Armed with its weight already on its legs, it refuses.
5. Left in the air, it gives up and lets the legs down, and the policy never ran.
6. Started in the air by mistake, the wheels are cut before they get far.
7. Picked up while running, the wheels are cut.
8. A lowering with a steadying hand gives touch_numbers what it needs, and what
   comes out launches it.
9. Armed sitting on its folded legs for one run only, it says so before any motor is
   enabled.
10. Stood up, it drives as the controller asks: full gas, full brake, a full turn.
11. Picked up while running, it stays armed, and takes over when put down again.
12. Fallen over, it lets go, and when picked up gets ready and takes over again.
13. A tap always answers: armed on folded legs, or with its shins the wrong way, in the
    air, its legs go to the crouch at once, and lowered it stands; on the floor it just
    starts; and lying slumped, it tries.
14. Fallen over and lying limp, a tap wakes it, whatever its legs are doing.
15. Select on the controller takes it from the slow limit to the fast one, and back,
    and in fast mode a full pull holds --fast-mark.
16. Driving, nothing short of lying down cuts its motors: a motor's fault is cleared,
    the IMU or a step late, the controller's deadman, a wheel too fast, a winding too
    hot and a hard shove are driven through, and an IMU gone for good lets it down.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sbc"))

import balance  # noqa: E402
import balance_check as bc  # noqa: E402
import drive  # noqa: E402
import policy_loop as pl  # noqa: E402
import sysid_tests as st  # noqa: E402

# The hand: stiff enough to hold the robot, soft enough to feel it arrive.
K, C, K_TURN, C_TURN = 1500.0, 30.0, 6.0, 0.4
# What each knee has to feel, here: 0.55 of the half of the robot that it carries.
EACH_NM = 0.15
CLEAR_M = 0.06  # how far above the floor the straight legs hang
UP = np.array([0.0, 0.0, 1.0])


# The wheels' VMAX on the robot from 6 November 2026, which sets their cap.
WHEEL_VMAX = 70.0
# How the wheels' torque follows what is sent, from the robot's own logs of 6 November
# 2026: the torque each wheel reports against the command, fitted as gain x first-order
# lag of the command 4-8 ms late, standing at 207 and 170 mm, both wheels alike: lag 12
# to 15 ms, gain 0.79 to 0.91, residual 0.006 to 0.034 Nm (0.007 standing at 207: 4 ms,
# 15 ms, 0.91). The delay is the rig's cmd_s and report_s, 6 + 1.5 ms. Without the lag
# MuJoCo stood D3 at 170 mm rocking at 0.28 rad/s and 2.0 Hz where the robot rocked at
# 0.61 and 1.55 Hz; with 12 ms and 0.85, 0.73 at 1.70 Hz. The reported torque is the
# motor's own estimate and may be filtered itself, so the lag is fitted, not proven.
#
# Raised on 7 November 2026 to the robot's 11 Hz shake (simulation/plant.py's SHAKE): the
# commands logged as sent against what each wheel reported, at 11 Hz, are a 15 ms lag at
# 0.93; and with that MuJoCo's torso still answers a push 0.81 as strongly as the robot's,
# for a reason not yet found, which the gain stands in for at 1.15 (0.93 / 0.81). On it
# D6 rocks as it did on the robot and D3 stands calm, where at 13 ms and 0.85 both stood
# calm and D6 went on the robot to rock it.
WHEEL_LAG_S = 0.015
WHEEL_GAIN = 1.15
# The wheel's own inertia on its joint, for every run judged whatever its training drew:
# the robot's leg targets and wheel torques replayed here move the wheels as the robot's
# moved at 2.8e-4 to 3.5e-4 kg m2, where the 8.3e-4 of plant.MEASURED (the wheels spinning
# in the air) moves them half as far (plant.SHAKE).
WHEEL_ARMATURE_KG_M2 = 3.0e-4
# How the legs' torque follows what the motor's own position-and-damping law asks, from
# the robot's logs of the same day (plant.LEG_RESPONSE): each hip and knee a first-order
# lag of 8 to 12 ms after the motor's torque limit, 0 to 2.5 ms late, at 0.9 to 1.05 of
# what is asked, driving at kp 12 and jumping at kp 6. Drawn at the middle of that, with
# the 0 to 2.5 ms left out. Unlike the wheels', this is real torque and not a filtered
# reading: on the rail the joints' acceleration, from the encoders alone, kept step with
# it. The motor's damping on a speed it reads about 4 ms late is not drawn.
# With it D3, which drives well on the robot, cruises 0.5 m/s in a 1.6 Hz surge, its
# wheels between 0 and 23 rad/s, and case 16's hard shove lands mid-surge and tips it;
# at gain 0.9, inside the fit, it cruises steadily and passes as before. Whether the
# robot surges there is not known: its logs of 6 November have no steady stretch at
# 0.25-0.5 m/s. Until one is driven, judge a policy against D3 at both gains.
#
# Raised on 7 November 2026 with the wheels' (plant.SHAKE): the hips' torque at 11 Hz is a
# first-order lag of 18 ms at 1.06 of what their law asks, the knees' 14.5 ms at 1.16.
LEG_LAG_S = 0.018
LEG_GAIN = 1.1
# Simulated seconds with no end before a check gives up: one armed for good never ends by
# itself, and a check that hung said nothing at all.
LONGEST_S = 120.0


class Finished(Exception):
    """The script has seen enough."""


class GaveUp(Exception):
    """It never got there."""


class Notes:
    """What balance.py logs, which is how a check knows what phase it reached."""

    def __init__(self, rig):
        self.rig = rig
        self.touched_at = self.policy_at = None
        self.stop_at_letdown = False
        self.phases: list[str] = []
        self.fell = None
        self.rearm = False
        self.recovering: list[str] = []
        self.lost = None
        self.jumps: list[tuple[float, str]] = []

    def write(self, m: dict) -> None:
        if m.get("k") != "n":
            return
        if "jump" in m:
            self.jumps.append((m["h"], m["jump"]))
        if "recovering" in m:
            self.recovering.append(m["recovering"])
        if "lost" in m:
            self.lost = m["lost"]
        if "touched" in m:
            self.touched_at = m["h"]
        if "fell" in m:
            self.fell = m["fell"]
        if "seg" in m:
            self.phases.append(m["seg"])
            if m["seg"] == "policy":
                self.policy_at = m["h"]
            if m["seg"] == "letdown" and self.stop_at_letdown:
                # One armed for good lets down and waits, unless it has been standing.
                if not self.rearm or "policy" in self.phases:
                    raise Finished


class HandRig(bc.SimRig):
    """SimRig, with a hand on the torso that follows `target`, and `upright`."""

    def __init__(
        self,
        *a,
        hand=None,
        wheel_lag_s=WHEEL_LAG_S,
        wheel_gain=WHEEL_GAIN,
        leg_lag_s=LEG_LAG_S,
        leg_gain=LEG_GAIN,
        **k,
    ):
        super().__init__(
            *a, wheel_lag_s=wheel_lag_s, wheel_gain=wheel_gain, leg_lag_s=leg_lag_s,
            leg_gain=leg_gain, **k,
        )  # fmt: skip
        self.stopped_by = self.stopped_why = None
        # Motors in a fault state: disabled, no torque, until cleared and enabled.
        self.dead: dict[str, bool] = {}
        self.woken: list[str] = []
        self.imu_quiet_until = -1.0
        # The chip starting its estimate over, as a jump's shaking made it on the robot
        # on 2026-11-06: gravity read straight along its own axis until the first time,
        # then at the wrong length until the second.
        self.imu_restart: tuple[float, float] | None = None
        self.stall = 0.0
        self.writer = Notes(self)
        self.hand = hand or (lambda rig: None)
        self.target = np.zeros(3)
        self.upright = UP.copy()
        self.carry = self.steady = 1.0
        self.weight = float(mujoco.mj_getTotalmass(self.m)) * bc.G
        self.floor = 0.0
        self.first_touch = None
        self.peak_tilt = self.peak_spin = self.peak_wheel = 0.0
        self.since_touch = False

    def enable(self, joints) -> None:
        for j in joints:
            self.dead.pop(j, None)

    def clear_fault(self, joint: str) -> None:
        if joint in self.dead:
            self.dead[joint] = True

    def wake(self, joint: str) -> None:
        if self.dead.get(joint):
            del self.dead[joint]
            self.woken.append(joint)

    def advance(self, until: float) -> None:
        if self.stall:
            until, self.stall = until + self.stall, 0.0
        super().advance(until)

    def on_wheels(self) -> float:
        """The share of the robot's weight the floor is carrying, as a hand would feel
        it: a moment behind, and only from the floor, not from the hand's own moving."""
        return self.floor / self.weight

    def _pressing(self) -> float:
        force = np.zeros(6)
        total = 0.0
        for k in range(self.d.ncon):
            mujoco.mj_contactForce(self.m, self.d, k, force)
            total += float(force[0])
        return total

    def _report(self, joint: str) -> None:
        super()._report(joint)
        f = self.latest[joint]
        tau = f.tau + float(self.rng.normal(0, 0.002))  # 0.001 on the rail
        state = 0xA if joint in self.dead else 1
        self.latest[joint] = st.Fb(f.at, f.p, f.v, tau, state)

    def _physics(self, dt: float) -> None:
        self.hand(self)
        d, b = self.d, self.ctl.base
        d.xfrc_applied[:] = 0.0
        rot = d.xmat[b].reshape(3, 3)
        off = rot @ np.array([0.0, 0.0, 0.05])
        at = d.xpos[b] + off
        w = rot @ d.qvel[3:6]
        pull = K * (self.target - at) - C * (d.qvel[0:3] + np.cross(w, off))
        pull[:2] *= self.steady
        pull[2] *= self.carry
        turn = self.steady * (
            K_TURN * np.cross(rot[:, 2], self.upright) - C_TURN * w
        ) + np.cross(at - d.xipos[b], pull)
        d.xfrc_applied[b, 0:3] = pull
        d.xfrc_applied[b, 3:6] = turn
        if self.dead:
            for j in self.dead:
                self.active[j] = st.Cmd()
        quiet = dict(self.imu) if self.t < self.imu_quiet_until else None
        super()._physics(dt)
        if quiet is not None:
            self.imu = quiet
        if self.imu_restart is not None and "gravity" in self.imu:
            frozen, wrong = self.imu_restart
            at, v = self.imu["gravity"]
            if self.t < frozen:
                self.imu["gravity"] = (at, [0.0, 0.0, 9.800781])
            elif self.t < wrong:
                self.imu["gravity"] = (at, [1.6 * x for x in v])
        self.floor += 0.05 * (self._pressing() - self.floor)
        if self.first_touch is None and self.on_wheels() > 0.02:
            self.first_touch = self.t
        self.peak_tilt = max(self.peak_tilt, self.tilt_deg())
        if self.writer.policy_at is not None:
            self.peak_spin = max(
                self.peak_spin, *(abs(float(self.d.qvel[v])) for v in self.ctl.wheel_v)
            )
            self.peak_wheel = max(self.peak_wheel, *np.abs(self.tau[4:6]).tolist())

    def hang(self) -> None:
        """Legs straight, the torso held level, the wheels clear of the floor."""
        self.place(0.0)
        for j in st.LEGS:
            self.d.qpos[self.m.jnt_qposadr[self.m.joint(j).id]] = 0.0
        link = 0.105 * 2
        self.d.qpos[2] = link + self.ctl.wheel_radius + 0.0685 + CLEAR_M
        mujoco.mj_forward(self.m, self.d)
        self.target = self.d.xpos[self.ctl.base] + np.array([0.0, 0.0, 0.05])
        self.target[2] += self.weight / K


def lowers(rate=0.03, react=0.2, release=0.3, begin=2.0, feel=0.05, early_m=0.0):
    """Waits, lowers until it feels the floor, takes a moment to react, and lets go.
    With `early_m`, lets go with the wheels that far above the floor."""
    felt = stopped = None

    def hand(rig):
        nonlocal felt, stopped
        if rig.t < begin:
            return
        dt = rig.m.opt.timestep
        if felt is None and rig.on_wheels() > feel:
            felt = rig.t
        if felt is None and early_m > 0.0:
            if float(np.min(rig.ctl.clearance_now(rig.d))) < early_m:
                felt = rig.t
        if felt is None or rig.t < felt + react:
            rig.target = rig.target - np.array([0.0, 0.0, rate * dt])
        else:
            stopped = rig.t if stopped is None else stopped
            s = max(0.0, 1.0 - (rig.t - stopped) / release)
            rig.carry = rig.steady = s

    return hand


class Asked(balance.Operator):
    """The controller's stream, on a script of what gamepad.py would send."""

    script = None
    rig = None

    def ask(self, now, spin=0.0):
        m = self.script(self.rig)
        if m is not None:
            self.last = (now, m)
        return super().ask(now, spin)


# What launch.json has from the measuring run: the knees in the air, Nm.
USUAL_AIR_NM = [0.126, 0.133]


def run(
    mode,
    hand,
    ctx,
    each=EACH_NM,
    seed=0,
    imu_ms=16.0,
    cmd_ms=6.0,
    seconds=10.0,
    wait=120.0,
    stop_at_letdown=True,
    then=None,
    script=None,
    rearm=False,
    woken=False,
    rig_class=None,
    jump_net=None,
    jump_height=0.12,
    jump_push=None,
    jump_script=None,
):
    """balance.powered, on a hand's script. What it ended with, and the rig. `jump_net`
    is a jump policy's network, or "scripted" for sbc/policy_loop.py's ScriptedJump,
    pushing at `jump_push` Nm."""
    rig = (rig_class or HandRig)(
        ctx.ctl, ctx.robot_file, cmd_s=cmd_ms / 1000, report_s=0.0015, imu_s=imu_ms / 1000,
        gyro_hz=400.0, gravity_hz=30.0, seed=seed, hand=hand, **getattr(ctx, "lags", {}),
    )  # fmt: skip
    rig.m.opt.timestep = 0.0005
    rig.hang()
    if then:
        then(rig)
    rig.writer.stop_at_letdown = stop_at_letdown
    rig.writer.rearm = rearm
    its_hand = rig.hand

    def watched(r):
        if r.t > LONGEST_S:
            raise GaveUp
        its_hand(r)

    rig.hand = watched
    balance.clock = lambda: rig.t
    bal = balance.LeanedBalancer(
        ctx.net, lean_per_m_s=getattr(ctx, "lean_per_m_s", 0.0)
    )
    if isinstance(jump_net, str):
        push = pl.JUMP_PUSH_NM if jump_push is None else jump_push
        bal = pl.ScriptedJump(bal, push, script=jump_script)
    elif jump_net is not None:
        bal = pl.TwoPolicies(bal, pl.JumpBalancer(jump_net), jump_height, volts=24.8)
    stepper = pl.Stepper(
        bal, pl.Imu(ctx.robot_file["imu_axes"], ctx.robot_file["imu_gravity_sign"]), rig,
        pl.Guard(30.0, pl.limits(wheel_vmax=WHEEL_VMAX)), clock=lambda: rig.t, wait=rig.advance,
        nap=lambda: rig.advance(rig.t + rig.m.opt.timestep),
        hold=pl.Hold(bal.meta["wheel_radius"]),
        trim=pl.Trim(bal.meta["wheel_radius"]), writer=rig.writer,
    )  # fmt: skip
    args = SimpleNamespace(
        mode=mode, seconds=seconds, touch_wait=wait, height=None, max_speed=0.5, max_turn=1.5,
        fast_speed=getattr(ctx, "fast_speed", None), drive=False, rearm=rearm, tilt=30.0,
        woken=threading.Event() if woken else None,
    )  # fmt: skip
    rig.args = args
    op = Asked(None, bal.meta, args)
    op.rig, op.script = rig, script or (lambda _rig: None)
    touch = pl.Touch(each, dict(zip(st.LEGS, bal.meta["crouch"], strict=True)))
    touch.usual = USUAL_AIR_NM
    rig.ask_status(list(st.JOINTS))
    rig.advance(rig.t + 0.02)
    go, stop = threading.Event(), threading.Event()
    try:
        why = balance.powered(
            rig, stepper, bal, op, balance.View(), args, go, stop, touch
        )
    except Finished:
        why = "stood"
    except GaveUp:
        why = f"nothing more after {LONGEST_S:g} s"
    except st.Abort as abort:
        why = f"cut: {abort}"
    rig.touch = touch
    return why, rig


def stood(name, ctx, hand, **k) -> bool:
    why, rig = run("launch", hand, ctx, **k)
    n = rig.writer
    after = None if n.touched_at is None else (n.touched_at - rig.first_touch) * 1000
    good = why == "stood"
    print(
        f"   {'stood' if good else 'FAILED: ' + why}: {name}; took over {after and round(after)} ms "
        f"after touching, tilted to {rig.peak_tilt:.1f} deg, wheels to {rig.peak_wheel:.2f} Nm "
        f"and {rig.peak_spin:.1f} rad/s",
        flush=True,
    )
    return good


def shaken(amplitude_m=0.0, hz=0.0, pitch_deg=0.0, roll_deg=0.0, begin=2.0):
    """Held still, then moved about in the air, tipping over a second."""
    centre = None

    def hand(rig):
        nonlocal centre
        if centre is None:
            centre = rig.target.copy()
        if rig.t < begin:
            return
        t = rig.t - begin
        rig.target = centre + np.array(
            [0.0, 0.0, amplitude_m * math.sin(2 * math.pi * hz * t)]
        )
        s = min(t, 1.0)
        p, r = math.radians(pitch_deg) * s, math.radians(roll_deg) * s
        rig.upright = np.array(
            [-math.sin(p) * math.cos(r), math.sin(r), math.cos(p) * math.cos(r)]
        )

    return hand


def still_waiting(name, ctx, hand, wait=8.0) -> bool:
    why, rig = run("launch", hand, ctx, wait=wait, stop_at_letdown=False)
    good = why.startswith("nothing touched") and "policy" not in rig.writer.phases
    print(f"   {'never started' if good else 'FAILED: ' + why}: {name}", flush=True)
    return good


def tilted_down(name, ctx, roll_deg=0.0, pitch_deg=0.0, **k) -> bool:
    def tip(rig):
        p, r = math.radians(pitch_deg), math.radians(roll_deg)
        rig.upright = np.array(
            [-math.sin(p) * math.cos(r), math.sin(r), math.cos(p) * math.cos(r)]
        )

    return stood(name, ctx, lowers(**k), then=tip)


def steadied_lowering(rig_begin=2.0):
    """What the measuring run asks for: carried about for a while, lowered until it
    stands with a hand only steadying it, kept there, then lifted clear."""
    shake = shaken(0.012, 3.0, 8.0, 0.0, begin=rig_begin)
    state = {"phase": "carry", "at": None}

    def hand(rig):
        s = state
        dt = rig.m.opt.timestep
        if s["phase"] == "carry":
            shake(rig)
            if rig.t > rig_begin + 8.0:
                rig.upright = UP.copy()
                s["phase"], s["at"] = "lower", rig.t
        elif s["phase"] == "lower":
            rig.target = rig.target - np.array([0.0, 0.0, 0.03 * dt])
            if rig.on_wheels() > 0.1:
                s["phase"], s["at"] = "let", rig.t
        elif s["phase"] == "let":
            rig.carry = max(0.0, 1.0 - (rig.t - s["at"]) / 1.5)
            if rig.t > s["at"] + 12.0:
                s["phase"], s["at"] = "lift", rig.t
        elif s["phase"] == "lift":
            rig.carry = min(1.0, (rig.t - s["at"]) / 0.5)
            rig.target = rig.target + np.array([0.0, 0.0, 0.05 * dt])
            if rig.t > s["at"] + 2.0:
                s["phase"] = "up"

    return hand


# The driving policy on the robot, which the suite judges unless told otherwise: D8
# (WheeledBipedDriveD8EnvCfg) from 2026-11-07 evening, passing every case here. D3 was
# back on it that afternoon after D7 (d7_rate, 14:39 to 15:27) swung the robot at 1-1.5
# Hz, about 10 degrees and 1.4 m/s each way, until it ran into a wall; this rig gives D7
# that swing at 204 mm with the wheels' torque at 0.8 of asked, and D3 none. D3 drove it from
# 2026-11-05; D5 went on and came off again on 2026-11-06, and D6 on 2026-11-07, which
# rocked the robot at 11-12 Hz and which this rig, on the loop it now draws, fails as the
# robot did (TRAINING_HISTORY.md). balance_check.py's RUN is the one trained only to
# 0.5 m/s, on which case 15's fast mode cannot pass.
DEPLOYED_RUN = ROOT / "exports" / "rl" / "rough-2026-11-07_11-52-47_d8"

# What case 15's full pull in fast mode has to hold, m/s, over two seconds once it has had
# six to get there. 1.0 is what every driving policy since D3 has been held to: D8 holds
# 1.11 here at its top of 2.2, and d8_calm failed at 0.80. D9, trained for the top speed
# this motor allows (WheeledBipedDriveD9EnvCfg), is to be held to 1.35 at its top of 1.6:
# on this rig on 7 November 2026 D8 cruised at 1.11-1.17 whatever was asked from 1.4 to
# 2.2, D3 at 1.54, and the motor stops being able to brake at about 1.5.
FAST_MARK_M_S = 1.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, default=DEPLOYED_RUN)
    ap.add_argument("--quick", action="store_true", help="one delay, fewer ways down")
    ap.add_argument(
        "--jump-run",
        type=Path,
        default=JUMP_RUN,
        help="a jump run packed by sbc/pack_policy.py, for the A button's case, or "
        "'scripted' for the scripted jump",
    )
    ap.add_argument(
        "--jump-push",
        type=float,
        help=f"the scripted jump's push, Nm, as balance.py's (default {pl.JUMP_PUSH_NM:g})",
    )
    ap.add_argument(
        "--jump-level-nm",
        type=float,
        help="the scripted jump's level push, Nm of each wheel, as balance.py's "
        f"(default pl.JumpScript's {pl.JumpScript.level_nm:g})",
    )
    ap.add_argument(
        "--jump-delays",
        default="16,6",
        metavar="IMU,COMMAND",
        help="ms, for the A button's case: the robot's, as the rest; the September "
        "stand-in was trained to 10 ms at most and passes only at 4,2",
    )
    ap.add_argument(
        "--wheel-lag-ms",
        type=float,
        default=WHEEL_LAG_S * 1000,
        help="the wheels' torque lag, measured; 0 for none",
    )
    ap.add_argument("--wheel-gain", type=float, default=WHEEL_GAIN)
    ap.add_argument(
        "--leg-lag-ms",
        type=float,
        default=LEG_LAG_S * 1000,
        help="the legs' torque lag, after their limit, measured; 0 for none",
    )
    ap.add_argument("--leg-gain", type=float, default=LEG_GAIN)
    ap.add_argument(
        "--fast-speed",
        type=float,
        help="m/s at a full pull in fast mode, as balance.py's --fast-speed: the robot's "
        "launcher passes 1.8, which balance.py holds to the policy's top (default: the top)",
    )
    ap.add_argument(
        "--lean-per-m-s",
        type=float,
        default=0.0,
        help="balance.py's --lean-per-m-s: degrees nose-up the driving policy is told it "
        "leans, per m/s it is sent",
    )
    ap.add_argument(
        "--fast-mark",
        type=float,
        default=FAST_MARK_M_S,
        help="m/s case 15's full pull in fast mode has to hold: 1.35 for D9",
    )
    ap.add_argument(
        "--wheel-armature",
        type=float,
        default=WHEEL_ARMATURE_KG_M2,
        help="kg m2 on each wheel's joint; 0 for what the run trained on",
    )
    args = ap.parse_args()
    cfg, onnx = drive.load_run(args.run)
    if args.wheel_armature > 0.0:
        cfg["robot"]["actuators"]["wheels"]["armature"] = args.wheel_armature
    ctl = drive.Controller(drive.build_model(cfg), cfg, onnx)
    ctx = SimpleNamespace(
        ctl=ctl,
        net=pl.Net(args.run / "exported" / "policy.npz"),
        robot_file=json.loads(bc.ROBOT_FILE.read_text()),
        fast_speed=args.fast_speed,
        fast_mark=args.fast_mark,
        lean_per_m_s=args.lean_per_m_s,
        lags=dict(
            wheel_lag_s=args.wheel_lag_ms / 1000,
            wheel_gain=args.wheel_gain,
            leg_lag_s=args.leg_lag_ms / 1000,
            leg_gain=args.leg_gain,
        ),
    )
    print(
        f"the wheels' torque {args.wheel_gain:g} of asked through {args.wheel_lag_ms:g} ms, "
        f"the legs' {args.leg_gain:g} through {args.leg_lag_ms:g} ms, "
        f"the wheels' armature {cfg['robot']['actuators']['wheels']['armature']:.1e} kg m2"
    )
    good = True

    print("1. lowered and let go, in the ways a person might")
    ways = [
        ("3 cm/s, lets go over 0.3 s", dict(rate=0.03, react=0.2, release=0.3)),
        ("1 cm/s, careful", dict(rate=0.01, react=0.3, release=0.5)),
        ("6 cm/s, quick", dict(rate=0.06, react=0.1, release=0.1)),
        ("3 cm/s, lets go at once", dict(rate=0.03, react=0.1, release=0.05)),
        ("2 cm/s, slow to let go", dict(rate=0.02, react=0.5, release=1.0)),
        ("1 cm/s, very slow to let go", dict(rate=0.01, react=1.0, release=2.0)),
        ("let go 3 cm up", dict(rate=0.03, react=0.0, release=0.05, early_m=0.03)),
    ]
    delays = [(16.0, 6.0)] if args.quick else [(16.0, 6.0), (26.0, 10.0)]
    for imu_ms, cmd_ms in delays:
        for name, way in ways[: 2 if args.quick else None]:
            good &= stood(
                f"{name}, IMU {imu_ms:g} ms, commands {cmd_ms:g} ms", ctx, lowers(**way),
                imu_ms=imu_ms, cmd_ms=cmd_ms,
            )  # fmt: skip

    print("2. handled in the air")
    for name, hand in (
        ("shaken 1.5 cm at 3 Hz", shaken(0.015, 3.0)),
        ("shaken 1 cm at 6 Hz", shaken(0.01, 6.0)),
        ("tipped 15 deg nose-down", shaken(pitch_deg=15.0)),
        ("tipped 15 deg nose-up", shaken(pitch_deg=-15.0)),
        ("tipped 15 deg to the right", shaken(roll_deg=15.0)),
    ):
        good &= still_waiting(name, ctx, hand)

    print("3. put down crooked: one wheel first, and waits for the other")
    for name, k in (
        ("rolled 3 deg", dict(roll_deg=3.0)),
        ("rolled 6 deg", dict(roll_deg=6.0)),
        ("nose-down 8 deg", dict(pitch_deg=8.0)),
        ("nose-up 8 deg", dict(pitch_deg=-8.0)),
    ):
        good &= tilted_down(name, ctx, **k)

    print("4. armed with its weight on its legs")

    def on_floor(rig):
        rig.d.qpos[2] -= CLEAR_M + 0.0255
        mujoco.mj_forward(rig.m, rig.d)
        rig.target = rig.d.xpos[rig.ctl.base] + np.array([0.0, 0.0, 0.05])
        rig.carry = 0.0

    why, rig = run("launch", None, ctx, stop_at_letdown=False, then=on_floor)
    fine = why.startswith("not started") and "policy" not in rig.writer.phases
    good &= fine
    print(f"   {'refused' if fine else 'FAILED'}: {why}", flush=True)

    print("5. left in the air")
    why, rig = run("launch", None, ctx, wait=3.0, stop_at_letdown=False)
    fine = why.startswith("nothing touched") and "policy" not in rig.writer.phases
    good &= fine
    print(f"   {'gave up' if fine else 'FAILED'}: {why}", flush=True)

    print("6. started in the air by mistake")
    why, rig = run("launch", None, ctx, each=-1.0)
    fine = "off the floor" in why
    good &= fine
    after = rig.t - (rig.writer.policy_at or 0.0)
    print(
        f"   {'cut' if fine else 'FAILED'} {after * 1000:.0f} ms after starting: {why}",
        flush=True,
    )

    print("7. picked up while running")
    lower_first = lowers()

    lift = {}

    def picks_up(rig):
        lower_first(rig)
        if rig.writer.policy_at is not None and rig.t > rig.writer.policy_at + 5.0:
            rig.carry = rig.steady = 1.0
            # Once: set afresh each step, the hand went on rising for as long as it ran.
            if "to" not in lift:
                lift["to"] = rig.d.xpos[rig.ctl.base] + np.array([0.0, 0.0, 0.13])
            rig.target = lift["to"]

    why, rig = run("launch", picks_up, ctx, seconds=30.0)
    fine = why.startswith("cut")
    good &= fine
    after = rig.t - (rig.writer.policy_at + 5.0)
    print(
        f"   {'cut' if fine else 'FAILED'} {after * 1000:.0f} ms after being picked up: {why}",
        flush=True,
    )

    print("8. the measuring run, and launching on what it found")
    why, rig = run("lower", steadied_lowering(), ctx, seconds=30.0)
    numbers = balance.touch_numbers(rig.touch.samples)
    fine = "each_nm" in numbers
    good &= fine
    print(f"   {'usable' if fine else 'FAILED'}: {json.dumps(numbers)}", flush=True)
    if fine:
        good &= stood(
            f"launched at {numbers['each_nm']:.3f} Nm",
            ctx,
            lowers(),
            each=numbers["each_nm"],
        )

    print("9. armed on folded legs")

    def folded(rig):
        for j in ("knee_right", "knee_left"):
            rig.d.qpos[rig.m.jnt_qposadr[rig.m.joint(j).id]] = 1.85
        mujoco.mj_forward(rig.m, rig.d)

    rig = HandRig(ctl, ctx.robot_file, 0.006, 0.0015, 0.016, 400.0, 30.0, **ctx.lags)
    rig.m.opt.timestep = 0.0005
    rig.hang()
    folded(rig)
    rig.ask_status(list(st.JOINTS))
    rig.advance(rig.t + 0.05)
    imu = pl.Imu(ctx.robot_file["imu_axes"], ctx.robot_file["imu_gravity_sign"])
    why = balance.legs_problem(rig, 30.0, imu)
    fine = why is not None and "hang" in why
    good &= fine
    print(f"   {'refused' if fine else 'FAILED'}: {why}", flush=True)

    print("10. driven from the controller")
    top_speed = max(map(abs, ctx.net.meta["speed_range"]))
    top_turn = max(map(abs, ctx.net.meta["turn_range"]))
    marks = {}

    def pose(rig):
        x, y = rig.d.qpos[:2]
        w, _, _, z = rig.d.qpos[3:7]
        return float(x), float(y), float(2 * np.arctan2(z, w))

    def script(rig):
        if rig.first_touch is None:
            return None
        t = rig.t - rig.first_touch
        for at in (4.0, 7.0, 9.0, 12.0, 14.0, 17.0):
            if t >= at and at not in marks:
                marks[at] = pose(rig)
        forward = 1.0 if 4.0 <= t < 7.0 else -1.0 if 9.0 <= t < 12.0 else 0.0
        # A full pull and a full turn are the policy's whole range, as gamepad.py sends
        # them, and --max-speed and --max-turn, 0.5 and 1.5 here, are what they ask for.
        return {
            "forward": forward * top_speed,
            "turn": top_turn if 14.0 <= t < 17.0 else 0.0,
            "live": True,
            "height": None,
        }

    why, rig = run("launch", lowers(0.03, 0.2, 0.3), ctx, seconds=18.0, script=script)
    gas = marks[7.0][0] - marks[4.0][0]
    brake = marks[12.0][0] - marks[9.0][0]
    turned = marks[17.0][2] - marks[14.0][2]
    fine = (
        why == "stood"
        and gas > 1.0
        and brake < -1.0
        and turned > 3.0
        and rig.peak_tilt < 28.0
    )
    good &= fine
    print(
        f"   {'ok' if fine else 'FAILED'}: {why}; 3 s of full gas moved it {gas:+.2f} m, of full brake "
        f"{brake:+.2f} m, and of a full turn {turned:+.2f} rad; tilted to {rig.peak_tilt:.1f} degrees",
        flush=True,
    )
    print("11. picked up while running, and put down again")

    def picked_up_and_put_down(rig):
        s = state
        n = rig.writer
        if s["again"] is None:
            first(rig)
        if s["stage"] == "down" and n.policy_at and rig.t > n.policy_at + 5.0:
            rig.carry = rig.steady = 1.0
            rig.upright = UP.copy()
            rig.target = rig.d.xpos[rig.ctl.base] + np.array([0.0, 0.0, 0.05 + 0.08])
            s["stage"], s["at"] = "up", rig.t
            s["again"] = lowers(begin=rig.t + 3.0)
        if s["again"] is not None:
            s["again"](rig)

    state = {"stage": "down", "at": 0.0, "again": None}
    first = lowers()
    why, rig = run("launch", picked_up_and_put_down, ctx, seconds=8.0, rearm=True)
    n = rig.writer
    fine = why == "stood" and n.phases.count("policy") == 2 and "lifted" in n.phases
    good &= fine
    print(
        f"   {'stood again' if fine else 'FAILED'}: {why}; went through {' '.join(n.phases)}; "
        f"wheels to {rig.peak_spin:.1f} rad/s",
        flush=True,
    )

    print("12. fallen over, picked up and put down")

    def lift_from_floor(rig, s, begin):
        """Takes it by the torso, up to where it hangs clear, over a second or so."""
        if s.get("from") is None:
            s["from"] = rig.d.xpos[rig.ctl.base].copy()
            s["to"] = np.array([s["from"][0], s["from"][1], 0.0])
            s["to"][2] = 0.105 * 2 + rig.ctl.wheel_radius + 0.0685 + CLEAR_M + 0.05
            s["to"][2] += rig.weight / K
        rig.carry = rig.steady = 1.0
        rig.upright = UP.copy()
        k = min((rig.t - begin) / 1.5, 1.0)
        rig.target = s["from"] + (s["to"] - s["from"]) * k

    def falls_then_picked_up(rig):
        s = fall
        n = rig.writer
        if s["again"] is not None:
            lift_done = s["again"]
            lift_done(rig)
            return
        if s["stage"] == "down":
            first_fall(rig)
            if n.policy_at and rig.t > n.policy_at + 4.0:
                s["stage"], s["at"] = "pushed", rig.t
        elif s["stage"] == "pushed":
            # A hard knock, which takes it past the cut-off.
            if not s.get("knocked"):
                rig.d.qvel[4] += 12.0
                s["knocked"] = True
            if n.fell is not None:
                s["stage"], s["at"] = "lying", rig.t
        elif s["stage"] == "lying":
            rig.carry = rig.steady = 0.0
            if rig.t > s["at"] + 2.0:
                s["stage"], s["at"] = "lifting", rig.t
        elif s["stage"] == "lifting":
            lift_from_floor(rig, s, s["at"])
            if (
                "ease" in n.phases[n.phases.index("limp") :]
                and "air" in (n.phases[n.phases.index("limp") :])
            ):
                s["again"] = lowers(begin=rig.t + 1.0)

    fall = {"stage": "down", "at": 0.0, "again": None}
    first_fall = lowers()
    why, rig = run("launch", falls_then_picked_up, ctx, seconds=8.0, rearm=True)
    n = rig.writer
    fine = why == "stood" and n.fell is not None and n.phases.count("policy") == 2
    good &= fine
    print(
        f"   {'stood again' if fine else 'FAILED'}: {why}; {n.fell}; went through "
        f"{' '.join(n.phases)}",
        flush=True,
    )

    print("13. a tap always answers")

    def waits_and_rises(rig, s):
        n = rig.writer
        if s["again"] is not None:
            s["again"](rig)
            return
        if rig.t > s["begin"]:
            lift_from_floor(rig, s, s["begin"])
            if "air" in n.phases:
                s["again"] = lowers(begin=rig.t + 1.0)

    def shins_forward(rig):
        for j, p in (("knee_right", -1.27), ("knee_left", -1.13)):
            rig.d.qpos[rig.m.jnt_qposadr[rig.m.joint(j).id]] = p
        for j, p in (("hip_pitch_right", 0.14), ("hip_pitch_left", 0.40)):
            rig.d.qpos[rig.m.jnt_qposadr[rig.m.joint(j).id]] = p
        mujoco.mj_forward(rig.m, rig.d)

    for name, then, begin in (
        ("on folded legs, in the air", folded, 0.0),
        ("shins the wrong way, in the air", shins_forward, 0.0),
        ("standing on the floor", on_floor, float("inf")),
    ):
        s13 = {"begin": begin, "again": None}
        why, rig = run(
            "launch",
            lambda rig, s=s13: waits_and_rises(rig, s),
            ctx,
            seconds=5.0,
            rearm=True,
            then=then,
        )
        n = rig.writer
        fine = (
            why == "stood"
            and n.phases.count("policy") == 1
            and n.phases[0] == "ease"
            and "limp" not in n.phases
        )
        good &= fine
        print(
            f"   {'stood' if fine else 'FAILED'}: {name}: {why}; went through {' '.join(n.phases)}",
            flush=True,
        )

    def slumped(knee, hip):
        def then(rig):
            rig.carry = rig.steady = 0.0
            for j in ("knee_right", "knee_left"):
                rig.d.qpos[rig.m.jnt_qposadr[rig.m.joint(j).id]] = knee
            for j in ("hip_pitch_right", "hip_pitch_left"):
                rig.d.qpos[rig.m.jnt_qposadr[rig.m.joint(j).id]] = hip
            mujoco.mj_forward(rig.m, rig.d)
            low = float(np.min(rig.ctl.clearance_now(rig.d)))
            rig.d.qpos[2] -= low - 0.002
            mujoco.mj_forward(rig.m, rig.d)
            rig.target = rig.d.xpos[rig.ctl.base] + np.array([0.0, 0.0, 0.05])

        return then

    def tilted(rig):
        z = float(rig.d.xmat[rig.ctl.base][8])
        return math.degrees(math.acos(min(1.0, max(-1.0, z))))

    def watch_for(seconds):
        def hand(rig):
            rig.peak_tilt = max(rig.peak_tilt, tilted(rig))
            if rig.t > seconds:
                raise Finished

        return hand

    for name, then in (
        ("slumped on the floor, knees folded", slumped(1.85, 0.9)),
        ("slumped on the floor, shins forward", slumped(-1.2, 0.2)),
    ):
        _, rig = run(
            "launch", watch_for(10.0), ctx, seconds=0.0, rearm=True, then=then, wait=0.0
        )
        n = rig.writer
        # Nothing it did was trained, so this says what it does, and only that it answers.
        fine = n.phases[:2] == ["ease", "firm"]
        good &= fine
        print(
            f"   {'answered' if fine else 'FAILED'}: {name}: went through {' '.join(n.phases)}; "
            f"{n.fell or 'no fall'}; now tilted {tilted(rig):.0f} degrees, at most "
            f"{rig.peak_tilt:.0f}; wheels to {rig.peak_spin:.0f} rad/s, torso at "
            f"{rig.d.xpos[rig.ctl.base][2]:.2f} m",
            flush=True,
        )

    print("    a stop from before it began")

    def old_stop(rig):
        rig.stopped_by = "diagd or the controller stopped the motors (asked)"

    why, rig = run("launch", lowers(), ctx, seconds=3.0, rearm=True, then=old_stop)
    fine = why == "stood"
    good &= fine
    print(f"   {'ignored' if fine else 'FAILED'}: {why}", flush=True)

    print("14. fallen over and lying limp, a tap wakes it")

    def fallen_then_tapped(rig):
        s = s14
        n = rig.writer
        if s["again"] is not None:
            s["again"](rig)
            return
        if s["stage"] == "down":
            s["first"](rig)
            if n.policy_at and rig.t > n.policy_at + 4.0:
                rig.d.qvel[4] += 12.0
                s["stage"] = "pushed"
        elif s["stage"] == "pushed":
            if n.fell is not None:
                s["stage"], s["at"] = "lying", rig.t
        elif s["stage"] == "lying":
            rig.carry = rig.steady = 0.0
            if rig.t > s["at"] + 2.0:
                s["stage"] = "tapped"
                rig.args.woken.set()
        elif s["stage"] == "tapped":
            if "ease" in n.phases[n.phases.index("limp") :]:
                s["woke"] = True
                raise Finished

    s14 = {"stage": "down", "at": 0.0, "again": None, "first": lowers(), "woke": False}
    why, rig = run(
        "launch", fallen_then_tapped, ctx, seconds=8.0, rearm=True, woken=True
    )
    fine = s14["woke"]
    good &= fine
    print(
        f"   {'woke' if fine else 'FAILED'}: {why}; went through {' '.join(rig.writer.phases)}",
        flush=True,
    )

    print("15. select toggles the speed")
    seen = {}

    def toggles(rig):
        if rig.first_touch is None:
            return None
        t = rig.t - rig.first_touch
        for at in (6.0, 8.0, 14.0, 16.0, 22.0, 24.0):
            if t >= at and at not in seen:
                seen[at] = pose(rig)[0]
        presses = 0 if t < 8.0 else 1 if t < 16.0 else 2
        return {
            "forward": top_speed if 3.0 <= t < 24.0 else 0.0,
            "turn": 0.0,
            "live": True,
            "height": None,
            "mode": presses,
        }

    why, rig = run("launch", lowers(), ctx, seconds=27.0, script=toggles)
    slow = (seen[8.0] - seen[6.0]) / 2.0
    fast = (seen[16.0] - seen[14.0]) / 2.0
    again = (seen[24.0] - seen[22.0]) / 2.0
    mark = ctx.fast_mark
    fine = why == "stood" and 0.4 < slow < 0.6 and fast > mark and 0.4 < again < 0.6
    good &= fine
    print(
        f"   {'ok' if fine else 'FAILED'}: {why}; full gas held {slow:.2f} m/s slow, "
        f"{fast:.2f} fast (to beat {mark:g}), {again:.2f} slow again; tilted to "
        f"{rig.peak_tilt:.1f} degrees, wheels to {rig.peak_spin:.1f} rad/s",
        flush=True,
    )

    print("16. driving, it recovers rather than cutting the motors")

    def trouble(at, do, until=None):
        """Full gas, 0.5 m/s here, and at `at` s after touching, `do` to the rig."""
        done = {}

        def script(rig):
            if rig.first_touch is None:
                return None
            t = rig.t - rig.first_touch
            if t >= at and "did" not in done:
                done["did"] = True
                do(rig)
            if until is not None and t >= at:
                until(rig, t - at)
            return {"forward": top_speed, "turn": 0.0, "live": True, "height": None}

        return script

    def fault(j):
        def do(rig):
            rig.dead[j] = False

        return do

    def quiet(seconds):
        def do(rig):
            rig.imu_quiet_until = rig.t + seconds

        return do

    def restart(frozen_s, wrong_s):
        def do(rig):
            rig.imu_restart = (rig.t + frozen_s, rig.t + frozen_s + wrong_s)

        return do

    def stall(rig):
        rig.stall = 0.15

    def deadman(rig):
        for j in st.JOINTS:
            rig.dead[j] = False
        rig.stopped_why = "silent"
        rig.stopped_by = "diagd or the controller stopped the motors (silent)"

    def shove(rig):
        # To 24 degrees. Shoved past 30, which cut the motors before, it fell on to 60 and
        # past every time in MuJoCo, forwards or back, so going on to 60 saves nothing
        # there: it only lets it fall under its own control rather than dropped.
        rig.d.qvel[4] += 9.0

    def hot(rig):
        rig.hot = True

    class Hot(HandRig):
        hot = False

        def _report(self, joint):
            super()._report(joint)
            if self.hot and joint == "knee_left":
                f = self.latest[joint]
                self.latest[joint] = st.Fb(f.at, f.p, f.v, f.tau, f.state, 0, 95)

    cases = [
        (
            "a wheel's motor faults",
            trouble(6.0, fault("wheel_drive_left")),
            "motor fault",
        ),
        ("a knee's motor faults", trouble(6.0, fault("knee_right")), "motor fault"),
        ("the IMU silent 0.3 s", trouble(6.0, quiet(0.3)), "IMU"),
        (
            "the IMU starting over, as a jump made it",
            trouble(6.0, restart(0.5, 0.8)),
            "carried on the gyro",
        ),
        ("a step 150 ms late", trouble(6.0, stall), "a step took"),
        ("the controller's deadman", trouble(6.0, deadman), "silent"),
        ("shoved hard", trouble(6.0, shove), None),
        ("a winding too hot", trouble(6.0, hot), "winding"),
    ]
    for name, script, expect in cases:
        rig_class = Hot if name.startswith("a winding") else HandRig
        why, rig = run(
            "launch", lowers(), ctx, seconds=12.0, rearm=True, script=script,
            rig_class=rig_class,
        )  # fmt: skip
        n = rig.writer
        noted = expect is None or any(expect in r for r in n.recovering)
        fine = why == "stood" and n.fell is None and n.lost is None and noted
        good &= fine
        print(
            f"   {'drove on' if fine else 'FAILED'}: {name}: {why}; tilted to "
            f"{rig.peak_tilt:.1f} degrees; {', '.join(sorted(set(n.recovering)))[:150] or 'nothing to recover'}"
            f"{'; woke ' + ', '.join(rig.woken) if rig.woken else ''}",
            flush=True,
        )

    why, rig = run(
        "launch", lowers(), ctx, seconds=12.0, rearm=True,
        script=trouble(6.0, quiet(30.0)),
    )  # fmt: skip
    n = rig.writer
    fine = n.lost is not None and "letdown" in n.phases and n.fell is None
    good &= fine
    print(
        f"   {'let down' if fine else 'FAILED'}: the IMU gone for good: {n.lost}; went through "
        f"{' '.join(n.phases)}",
        flush=True,
    )

    why, rig = run(
        "launch", lowers(), ctx, seconds=12.0, rearm=True,
        script=trouble(6.0, restart(0.5, 3.0)),
    )  # fmt: skip
    n = rig.writer
    fine = n.lost is not None and "letdown" in n.phases and n.fell is None
    good &= fine
    print(
        f"   {'let down' if fine else 'FAILED'}: the IMU starting over and not back in "
        f"{pl.GYRO_CARRY_S:g} s: {n.lost}; went through {' '.join(n.phases)}",
        flush=True,
    )

    imu_ms, cmd_ms = (float(x) for x in args.jump_delays.split(","))
    good &= jumps(
        ctx, args.jump_run, imu_ms, cmd_ms, args.jump_push, args.jump_level_nm
    )

    good &= taken_over_low(ctx)

    print("passed" if good else "FAILED")
    return 0 if good else 1


def taken_over_low(ctx) -> bool:
    """Case 18: the D-pad's height left at the bottom of the trained range by the run
    before, and the hand that puts it down staying on it. On 2026-11-06 at 19:41-19:43
    D5, taking over at 155 mm, folded its knees 0.85 rad in 0.15 s under the owner's
    hand, its wheels came off the floor and spun to 55 rad/s, and the lift rule stopped
    it, three times running. Here, with the height asked from the first step and no
    crouch held first, D5 is cut with its wheels at 30 to 33 rad/s, and D3 at 170 mm is
    cut or reaches 33. balance.py's Operator now takes over at the crouch's height."""
    print("18. put down with the height already asked low, a hand staying on it")
    low = ctx.net.meta["height_range"][0]

    def asked_low(_rig):
        return {"forward": 0.0, "turn": 0.0, "live": True, "height": low}

    def nose_down(rig):
        p = math.radians(6.0)
        rig.upright = np.array([math.sin(p), 0.0, math.cos(p)])

    good = True
    for name, hand in (
        ("staying a second, then letting go over one", lowers(react=1.0, release=1.0)),
        ("letting go over two seconds", lowers(release=2.0)),
    ):
        why, rig = run(
            "launch", hand, ctx, seconds=10.0, then=nose_down, script=asked_low
        )
        # Without the crouch first the wheels reach 30 rad/s and more; with it 11 to 18.
        legs = float(np.mean(pl.leg_heights(rig.latest)))
        fine = why == "stood" and rig.peak_spin < 20.0
        good &= fine
        print(
            f"   {'stood' if fine else 'FAILED: ' + why}: {name}, {low * 1000:.0f} mm "
            f"asked; wheels to {rig.peak_spin:.1f} rad/s, tilted to {rig.peak_tilt:.1f} "
            f"deg, legs at {legs * 1000:.0f} mm",
            flush=True,
        )
    return good


# The jump policy for case 17: jl_lag, trained on the measured robot with its legs' and
# wheels' torque lag and its delays, which with D6 lands and hands back standing at the
# robot's delays, IMU 16 ms and commands 6, at both leg strengths (2026-11-07). With D3
# it does too, standing and at 0.5 m/s; but pressed at 1.5 m/s, D3 braking first is taken
# for lifted before the jump begins, and does not get up again. The
# September stand-in, jump-2026-09-28_06-13-36_jumpsym300, was trained on the model
# before the robot was measured: at those delays it lands and then tips over within half
# a second, and it passes only at the 10 ms at most it was trained to (TRAINING_HISTORY.md).
JUMP_RUN = ROOT / "exports" / "rl" / "jump-2026-11-06_19-35-39_jl_lag"
# Pressed driving, the scripted jump is going on at this share of the speed it was pressed
# at (or, pressed faster than pl.JUMP_RUN_TOP_M_S, of the speed it had been braked to as
# it pushed), this long after it is handed back: on this rig on 8 November 2026, pressed
# at 0.41 and 1.40 m/s, it was going 0.90 and 0.99 of it (session scratchpad
# jump_grace/); braking to a stop first, as it did before, it would be going none of it.
# Pushing 2.5 Nm rather than 1.6 it lands harder and keeps less: pressed at 0.41 m/s, 0.85
# of it, and let go of A on the way down, 0.71, standing every time (jump_merge/, 8
# November 2026). Braking to a stop would still be none.
LANDED_S = 0.5
LANDED_SHARE = 0.65


def jumps(
    ctx, jump_run: Path, imu_ms: float = 4.0, cmd_ms: float = 2.0, push=None, level=None
) -> bool:
    """Case 17, on a jump policy's run, or with `jump_run` "scripted" on
    sbc/policy_loop.py's ScriptedJump pushing `push` Nm, its level push `level` Nm if
    given (balance.py's --jump-level-nm)."""
    scripted = str(jump_run) == balance.SCRIPTED
    what = (
        f"the scripted jump, pushing {pl.JUMP_PUSH_NM if push is None else push:g} Nm, "
        f"the wheels {balance.jump_script(level).level_nm:g}"
        if scripted
        else "the jump policy"
    )
    print(
        f"17. the A button jumps, on {what}, and hands back "
        f"(IMU {imu_ms:g} ms, commands {cmd_ms:g} ms)"
    )
    if scripted:
        jump_net = balance.SCRIPTED
    else:
        pack = jump_run / "exported" / "policy.npz"
        if not pack.exists():
            print(
                f"   FAILED: no {pack}: uv run sbc/pack_policy.py {jump_run}",
                flush=True,
            )
            return False
        jump_net = pl.Net(pack)
    good = True
    top_turn = max(map(abs, ctx.net.meta["turn_range"]))

    def pressing(
        at,
        forward,
        fast=False,
        again=None,
        held=None,
        steer=None,
        quiet=None,
        lift=None,
    ):
        """A press `at` seconds after touching, and then: `held`, A held that long, with
        gamepad.py's bit set over the count as it sends it, or None for a controller from
        before, which never sets it; `steer`, (from, to, share of a full turn) after the
        press; `quiet`, the controller silent from that long after it; `lift`, picked up
        that long after it, and put down again."""
        seen = {"clear": 0.0, "low": 1.0, "tilt": 0.0, "press": None, "after": None}
        seen |= {"heading": None, "turned": 0.0, "lifted": None}

        def script(rig):
            if rig.first_touch is None:
                return None
            t = rig.t - rig.first_touch
            if quiet is not None and t >= at + quiet:
                return None
            presses = (t >= at) + (again is not None and t >= at + again)
            if t >= at and seen["press"] is None:
                seen["press"] = rig.t
                seen["going"] = rig.forward_speed()
            if "pushed" not in seen and any(
                w.startswith("jump:") for _, w in rig.writer.jumps
            ):
                seen["pushed"] = rig.forward_speed()
            if t >= at:
                w, _, _, z = rig.d.qpos[3:7]
                heading = float(2 * np.arctan2(z, w))
                seen["heading"] = seen["heading"] or heading
                turned = math.remainder(heading - seen["heading"], 2 * math.pi)
                seen["turned"] = max(seen["turned"], abs(math.degrees(turned)))
            if lift is not None and t >= at + lift and seen["lifted"] is None:
                # As case 11 picks it up, and put down again 3 s later.
                seen["lifted"] = lowers(begin=rig.t + 3.0)
                rig.carry = rig.steady = 1.0
                rig.upright = UP.copy()
                rig.target = rig.d.xpos[rig.ctl.base] + np.array([0.0, 0.0, 0.13])
            jump = int(presses)
            if held is not None and at <= t < at + held:
                jump |= balance.JUMP_HELD
            turning = 0.0
            if steer is not None and at + steer[0] <= t < at + steer[1]:
                turning = steer[2] * top_turn
            back = next(
                (h for h, w in rig.writer.jumps if w.startswith("handed back")), None
            )
            if seen["after"] is None and back is not None and rig.t >= back + LANDED_S:
                seen["after"] = rig.forward_speed()
            if t >= at - 0.1:
                clear = float(np.min(rig.ctl.clearance_now(rig.d)))
                seen["clear"] = max(seen["clear"], clear)
                seen["low"] = min(
                    seen["low"], float(np.mean(pl.leg_heights(rig.latest)))
                )
                seen["tilt"] = max(seen["tilt"], rig.tilt_deg())
            return {
                "forward": forward,
                "turn": turning,
                "live": True,
                "height": None,
                "mode": int(fast and t >= 1.0),
                "jump": jump,
            }

        first = lowers()

        def hand(rig):
            # Put down, and with `lift` picked up and put down again.
            (seen["lifted"] or first)(rig)

        return script, seen, hand

    # The scripted jump jumps driving, up to pl.JUMP_RUN_TOP_M_S, and at a full pull in
    # fast mode brakes to pl.JUMP_RUN_CAP_M_S first; a jump policy brakes.
    top = max(map(abs, ctx.net.meta["speed_range"]))
    fast = (
        (
            "at a full pull in fast mode, braking to the cap first",
            dict(at=8.0, forward=top),
        )
        if scripted
        else ("at 1.5 m/s, braking first", dict(at=8.0, forward=1.5))
    )
    cases = [
        ("standing", dict(at=5.0, forward=0.0)),
        ("at 0.5 m/s", dict(at=6.0, forward=1.8)),
        (fast[0], fast[1] | dict(fast=True)),
        ("pressed twice", dict(at=5.0, forward=0.0, again=0.4)),
    ]
    if scripted:
        # 1 m/s asked in fast mode, where on the robot a jump fell.
        at_1 = 1.0 * top / (getattr(ctx, "fast_speed", None) or top)
        cases.insert(2, ("at 1 m/s", dict(at=8.0, forward=at_1, fast=True)))
        # THE BUTTON (sbc/policy_loop.py): pressed, it crouches and waits while A is
        # held, and let go of, it jumps. The cases above are a controller from before,
        # which never sends the held bit; a jump policy takes no notice of it.
        cases += [
            ("A held 2 s standing, then let go", dict(at=5.0, forward=0.0, held=2.0)),
            (
                "A held 3 s at 0.5 m/s, steering for 1.5 s, then let go",
                dict(at=6.0, forward=1.8, held=3.0, steer=(0.5, 2.0, 0.5)),
            ),
            ("a quick tap, A held 0.1 s", dict(at=5.0, forward=0.0, held=0.1)),
            (
                "A let go on the way down, at 0.5 m/s",
                dict(at=6.0, forward=1.8, held=0.04),
            ),
            (
                "A let go while braking, at a full pull in fast mode",
                fast[1] | dict(fast=True, held=0.04),
            ),
            (
                "the controller silent 1 s into holding A",
                dict(at=5.0, forward=0.0, held=3.0, quiet=1.0),
            ),
            (
                "A let go still steering, at 0.5 m/s",
                dict(at=6.0, forward=1.8, held=2.0, steer=(0.5, 4.0, 0.5)),
            ),
            (
                "picked up 2 s into holding A, and put down",
                dict(at=5.0, forward=0.0, held=8.0, lift=2.0),
            ),
        ]
    for name, k in cases:
        script, seen, hand = pressing(**k)
        why, rig = run(
            "launch", hand, ctx, seconds=14.0, rearm=True, script=script,
            jump_net=jump_net, imu_ms=imu_ms, cmd_ms=cmd_ms, jump_push=push,
            jump_script=balance.jump_script(level) if scripted else None,
        )  # fmt: skip
        n = rig.writer
        said = [w for _, w in n.jumps]
        back = next((h for h, w in n.jumps if w.startswith("handed back")), None)
        jumped = next((h for h, w in n.jumps if w.startswith("jump:")), None)
        took = None if back is None or seen["press"] is None else back - seen["press"]
        held = k.get("held")
        # Silent or picked up it must not jump, and let go still turning it need not:
        # standing up again is as good. Picked up, taking over again starts it afresh,
        # with no hand-back.
        lifting = k.get("lift") is not None
        turning = k.get("steer") is not None and k["steer"][1] > (held or 0.0)
        must_jump = None if turning else k.get("quiet") is None and not lifting
        fine = (
            why == "stood"
            and n.fell is None
            and ("lifted" in n.phases) == lifting
            and (back is not None or lifting)
        )
        if must_jump is not None:
            fine &= (jumped is not None) == must_jump
        if k.get("again") is not None:
            fine &= any(w.startswith("refused: already") for w in said)
        if held is not None and jumped is not None:
            # Never before A is let go of.
            fine &= jumped >= seen["press"] + held - 0.02
        if held is not None and held < 0.05:
            # Let go before the crouch is reached: on the way down, or, pressed past the top,
            # still braking to it.
            fine &= any(
                "let go" in w and ("on the way down" in w or "braking" in w)
                for w in said
            )
        if k.get("quiet") is not None:
            fine &= any("controller went quiet" in w for w in said)
        if lifting:
            fine &= n.phases.count("policy") == 2
        if k.get("steer") is not None:
            fine &= seen["turned"] > 10.0
        going = ""
        if scripted and k["forward"] and jumped is not None:
            # Pressed driving, it jumps, braking first only past the top, and lands going
            # on at the speed it jumped at: pressed, or braked, as it pushed.
            after = seen["after"]
            over = seen["going"] > pl.JUMP_RUN_TOP_M_S
            fine &= over == any("braking first" in w for w in said)
            jumped_at = seen.get("pushed", math.inf) if over else seen["going"]
            if not turning:
                # Turning as it lands, its speed straight on is less.
                fine &= after is not None and after >= LANDED_SHARE * jumped_at
            going = (
                f"going {seen['going']:.2f} m/s"
                + (f", {seen.get('pushed', math.nan):.2f} as it pushed" if over else "")
                + f", then {after or 0.0:.2f}; "
            )
        elif k.get("fast") and not scripted:
            fine &= any("braking first" in w for w in said)
        if k.get("steer") is not None:
            going += f"turned {seen['turned']:.0f} deg; "
        good &= fine
        print(
            f"   {'ok' if fine else 'FAILED'}: {name}: {why}; {going}legs down to "
            f"{seen['low'] * 1000:.0f} mm, wheels cleared {seen['clear'] * 1000:.0f} mm, "
            f"tilted to {seen['tilt']:.1f} deg; back {took and round(took, 2)} s after the "
            f"press; went through {' '.join(n.phases)}; {' / '.join(said)}"[:600],
            flush=True,
        )
    return good


if __name__ == "__main__":
    raise SystemExit(main())
