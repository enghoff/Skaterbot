# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy>=1.26", "mujoco>=3.2", "onnxruntime>=1.18",
#                 "pyyaml>=6.0", "pygame>=2.5"]
# ///
"""How high can the legs throw the robot? A scripted jump, no policy.

    uv run simulation/mujoco/scripted_jump.py
    uv run simulation/mujoco/scripted_jump.py --optimistic

Every trained jump policy has cleared about 100-110 mm by snapping its legs up
under a body that barely rises, and none has learnt to crouch first. Before
teaching it one, this asks whether a crouch is worth anything with these
motors: it crouches to a chosen depth, pushes at full effort, tucks once the
wheels are off the ground, and reports the torso's rise and the wheels'
clearance, over a sweep of crouch depths.

The motors are the MuJoCo driver's -- Isaac Lab's DCMotor, its torque falling
in a straight line from the 3 Nm peak to nothing at the no-load speed, read
from the run's env.yaml -- so the answer is the simulator's answer, which the
trained policy lives by. --optimistic puts the line's knee at half the no-load
speed instead, full torque up to there, which is closer to how a motor with a
current limit behaves and has not been measured either.

The legs keep the knee at twice the hip, which keeps the axle under the hip,
so a jump is straight up. The torso's pitch is held (its rotational inertia
multiplied a thousandfold, its mass unchanged) and the wheels are left free,
so what is measured is the legs' ceiling and not whether the push also
balances; each trial ends at touchdown, since nothing here balances after it.

WHAT IT FOUND (2026-09-26). On the simulator's straight line, a crouch is
worth little: the torso rises 14 mm from the standing crouch and at most 27
mm from any depth, and crouch, push and tuck together clear 93 mm at best --
where the trained policies already clear 110 with the torso rising 20-28. So
the policy is at the motors' ceiling, and not crouching is not what holds it
back. With --optimistic the same crouch to a hip of 0.7 rad lifts the torso
56 mm and clears 118: a crouch pays only if the motor keeps its torque at
speed, which is the torque-speed curve nobody has measured.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import drive  # noqa: E402

CROUCH_HIP_RAD = 0.25  # the stance the policies stand in, knee at twice it
SETTLE_S = 0.5
CROUCH_S = 0.30  # time to sink to the crouch
HOLD_S = 0.10
EXTEND_HIP_RAD = 0.05  # the push aims here: nearly straight
TUCK_HIP_RAD = 0.85  # and the tuck here: the knee at 1.7 of its 1.745 stop
HOLD_GAINS = (30.0, 0.8)  # Nm/rad, Nm s/rad
PUSH_GAINS = (300.0, 1.0)  # far past saturation: the motor limit decides
CONTACT_M = 0.003


def jump(model, cfg, ctl, crouch_hip: float, tuck: bool) -> dict:
    d = mujoco.MjData(model)
    ctl.place(d)
    dt = model.opt.timestep
    hip = np.array([0, 2])
    phase, t, target = "settle", 0.0, CROUCH_HIP_RAD
    start_z = apex_z = None
    peak = 0.0
    took_off_at = None
    air = 0.0
    lowest_z = None
    for _ in range(round(3.0 / dt)):
        t += dt
        clear = ctl.clearance_now(d)
        z = d.xpos[ctl.base, 2]
        if phase == "settle" and t > SETTLE_S:
            phase, t0, start_z, lowest_z = "crouch", t, z, z
        if phase == "crouch":
            s = min((t - t0) / CROUCH_S, 1.0)
            target = CROUCH_HIP_RAD + (crouch_hip - CROUCH_HIP_RAD) * s
            lowest_z = min(lowest_z, z)
            if t - t0 > CROUCH_S + HOLD_S:
                phase, t_push = "push", t
        if phase == "push":
            target = EXTEND_HIP_RAD
            if (clear > CONTACT_M).all():
                phase, took_off_at = "air", t - t_push
        if phase == "air":
            target = TUCK_HIP_RAD if tuck else EXTEND_HIP_RAD
            if (clear > CONTACT_M).all():
                peak = max(peak, clear.min())
                apex_z = max(apex_z or z, z)
                air += dt
            elif air > 0.02:
                break  # landed; nothing here balances it afterwards
        kp, kd = PUSH_GAINS if phase in ("push", "air") else HOLD_GAINS
        legs = np.empty(4)
        legs[hip], legs[hip + 1] = target, 2 * target
        q, v = d.qpos[ctl.leg_q], d.qvel[ctl.leg_v]
        tau = kp * (np.clip(legs, ctl.leg_lo, ctl.leg_hi) - q) - kd * v
        d.ctrl[ctl.leg_act] = ctl._saturate(tau, v)
        d.ctrl[ctl.wheel_act] = 0.0
        mujoco.mj_step(model, d)
        if ctl.tilt(d) > 1.0:
            return {"fell": True, "at": (phase, round(t, 2))}
    return {
        "fell": False,
        "dip": (start_z - lowest_z) * 1000,
        "push_s": took_off_at,
        "rise": ((apex_z or start_z) - start_z) * 1000,
        "clearance": peak * 1000,
        "air": air,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path, default=drive.DEFAULT_RUN)
    parser.add_argument("--optimistic", action="store_true")
    args = parser.parse_args()

    cfg, policy = drive.load_run(args.run)
    model = drive.build_model(cfg)
    ctl = drive.Controller(model, cfg, policy)
    model.body_inertia[ctl.base] *= 1000.0
    if args.optimistic:
        ctl.saturation = 2.0 * ctl.peak
    print(
        f"torque line: {ctl.peak:.1f} Nm peak, {ctl.saturation:.1f} Nm at stall,"
        f" zero at {ctl.vmax:.1f} rad/s"
    )
    print(
        f"  {'crouch hip':>10} {'tuck':>5} {'dip':>7} {'push':>7}"
        f" {'torso rise':>11} {'clearance':>10} {'in the air':>11}"
    )
    for crouch in (0.25, 0.40, 0.55, 0.70, 0.80):
        for tuck in (False, True):
            r = jump(model, cfg, ctl, crouch, tuck)
            if r["fell"]:
                print(f"  {crouch:10.2f} {str(tuck):>5}   fell over, {r['at']}")
                continue
            push = f"{r['push_s'] * 1000:5.0f}ms" if r["push_s"] else "   --  "
            print(
                f"  {crouch:10.2f} {str(tuck):>5} {r['dip']:5.0f}mm {push}"
                f" {r['rise']:9.0f}mm {r['clearance']:8.0f}mm {r['air']:9.2f}s"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
