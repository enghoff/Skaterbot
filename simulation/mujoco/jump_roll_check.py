# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy>=1.26", "mujoco>=3.2", "onnxruntime>=1.18", "pyyaml>=6.0",
#                 "pygame>=2.5", "pyserial>=3.5"]
# ///
"""A jump policy against the robot's roll answer to its knees, in MuJoCo.

    uv run simulation/mujoco/jump_roll_check.py exports/rl/jump-2026-11-06_19-35-39_jl_lag
    uv run simulation/mujoco/jump_roll_check.py RUN_OR_NPZ [--seeds 1,2,3] [--no-roll]

The gate a jump policy passes before it goes on the robot. Every jump on the robot
failed on 6 and 7 November 2026 while every one in MuJoCo passed, because the robot's
torso rolls about 10 rad/s per rad of fast knee target difference and MuJoCo's barely
at all, and the jump policy closes that loop through its gyro into 20-25 Hz chatter
(simulation/roll_mode.py has the whole of it). This puts the robot's fitted roll mode
into the IMU's readings, as the session's simj.py did, on launch_check.py's rig as it
stands (its wheel inertia, its wheels' and legs' torque lag and gain, the IMU 16 ms
late and commands 6 ms), with the driving policy on the robot driving, standing, and
the A button pressed 5 s after the wheels touch: balance.py's own two-policy handover,
the crouch, the jump and the hand back, at 30 mm asked. Each seed is a run, side by
side. A jump passes when, for every seed:

  * it stands: the run ends standing, never fell nor was taken for lifted, jumped, and
    was handed back to the driving policy (launch_check.py case 17's test);
  * it is upright again by 1.5 s after the press, or 0.9 s after the hand back if that
    is later, under 15 degrees from then to the end of the run. The jump itself pitches
    the torso: jl_lag on this rig without the loop reaches 31-36 degrees 0.45-0.7 s after
    the press and is back under 2 by 1.5 s; the robot's jumps tipped over backwards about
    0.7 s after the trigger. A jump policy hands back 0.6 s after the press, so for one
    the two are the same; the scripted jump waits in its crouch until the robot is calm,
    steady and balanced, and lands 0.6-0.8 s after the press (it waited 0.7-1.0 s and
    landed 1.0-1.4 s after until 8 November 2026);
  * the torso's roll rate as the IMU sees it, the body's own and the mode's, is under
    1.5 rad/s rms over the 1.5 s from the press, or to 0.9 s after the hand back;
  * the knees' targets move under 0.2 rad a step on average while the jump policy has
    them, from the crouch to the hand back (on the robot, 0.27-0.46);
  * the lower wheel clears at least 80 % of the height asked at the top of the jump.

jl_lag, the jump policy on the robot, behind D8, on 7 November 2026 (seeds 1, 2, 3):
with the loop it fails every seed, rolling 2.20, 2.46 and 3.88 rad/s rms with its knee
targets moving 0.28, 0.31 and 0.40 rad a step, and on seed 3 it falls; without it
(--no-roll) it passes every seed, rolling 0.50-0.82 with its knees at 0.15-0.17 and
clearing 31-35 mm. That the gate passes a jump without the loop and fails it with is
the case for the gate.

`scripted` in place of a run is sbc/policy_loop.py's ScriptedJump, pushing --push Nm, its
wheels' level push --level-nm as balance.py's --jump-level-nm (the robot's launcher passes
0.35), and asked for no height, so held to no clearance; and --wheel-gain, --leg-gain
and --volts make the rig a worse one. The worst it has been held to is the wheels' torque at 0.8 of
asked, the legs' at 0.9, the pack at 23.4 V and --imu-ms 40.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # roll_mode.py, beside plant.py
sys.path.insert(0, str(HERE))

import launch_check as lc  # noqa: E402
import roll_mode  # noqa: E402

KNEES = ("knee_right", "knee_left")
# The gate's marks (above).
UPRIGHT_BY_S = 1.5
# Or this long after the hand back, if that is later.
BACK_S = 0.9
UPRIGHT_DEG = 15.0
ROLL_WINDOW_S = 1.5
ROLL_RMS_RAD_S = 1.5
KNEE_STEP_RAD = 0.2
CLEAR_SHARE = 0.8


class Steps(lc.Notes):
    """launch_check.py's notes, and the knees' targets as each policy step left them.
    A step speaks to every motor with the commands it holds before it sends new ones,
    so every target goes out twice and the sends alone halve the chatter."""

    def __init__(self, rig):
        super().__init__(rig)
        # (time, right, left), one a policy step.
        self.knees: list[tuple[float, float, float]] = []

    def write(self, m: dict) -> None:
        if m.get("k") == "p":
            sent = self.rig.sent
            self.knees.append((m["h"], *(sent[j][-1][1] for j in KNEES)))
        super().write(m)


class Rig(lc.HandRig):
    """launch_check.py's rig, its IMU reading the robot's roll mode on top of the body's
    own, and what the gate measures."""

    # (gain at the natural frequency rad/s per rad, hz, damping, delay s), or None: set
    # on a subclass per run, since launch_check.run builds the rig itself.
    roll: tuple[float, float, float, float] | None = None

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        # Every knee target as sent, (time, rad); level legs before the first.
        self.sent = {j: [(-math.inf, 0.0)] for j in KNEES}
        self.angle = self.rate = 0.0
        self.coef = None
        self.press = None
        self.clear = 0.0
        self.fell_at = None
        # (time, tilt deg, roll rate seen rad/s) at each physics step from the press.
        self.log: list[tuple[float, float, float]] = []
        # Before launch_check.run hands the writer to the policy's stepper.
        self.writer = Steps(self)

    def send(self, joint, c):
        super().send(joint, c)
        if joint in self.sent:
            self.sent[joint].append((self.t, c.p))

    def knee_difference(self, t: float) -> float:
        """The knees' targets as sent, right minus left, as they stood at t."""
        right, left = (
            h[bisect.bisect_right(h, (t, math.inf)) - 1][1]
            for h in (self.sent[j] for j in KNEES)
        )
        return right - left

    def _physics(self, dt: float) -> None:
        # The mode across this step, its input held at what was sent `delay` before the
        # step starts, so the IMU's reports at the step's end read it there: the same
        # exact step and the same timing as wheeled_biped_task/jump_env.py takes.
        if self.roll is not None:
            if self.coef is None:
                self.coef = roll_mode.coefficients(*self.roll[:3], dt)
            u = self.knee_difference(self.t - self.roll[3])
            self.angle, self.rate = roll_mode.advance(
                self.angle, self.rate, u, self.coef
            )
        super()._physics(dt)
        if self.press is not None:
            seen = float(self.d.qvel[3]) + self.rate
            self.log.append((self.t, self.tilt_deg(), seen))

    def _chip(self, report: str) -> list:
        v = super()._chip(report)
        if self.roll is None:
            return v
        if report == "gyro":
            return [
                float(x)
                for x in np.array(v) + self.to_chip @ np.array([self.rate, 0.0, 0.0])
            ]
        # Gravity in the torso's frame, turned by the mode's angle about its x.
        g = self.axes @ (np.array(v) * self.gravity_sign)
        g[1], g[2] = roll_mode.turn_gravity(g[1], g[2], self.angle)
        return [float(x) for x in self.gravity_sign * (self.to_chip @ g)]


def one(job: dict) -> dict:
    """One seed's run, judged."""
    cfg, onnx = lc.drive.load_run(Path(job["run"]))
    cfg["robot"]["actuators"]["wheels"]["armature"] = lc.WHEEL_ARMATURE_KG_M2
    ctl = lc.drive.Controller(lc.drive.build_model(cfg), cfg, onnx)
    # The motors' speed goes with their supply (drive.py's set_conditions).
    ctl.vmax = ctl.vmax_rated * job["volts"] / lc.pl.RATED_VOLTS
    ctx = SimpleNamespace(
        ctl=ctl,
        net=lc.pl.Net(Path(job["run"]) / "exported" / "policy.npz"),
        robot_file=json.loads(lc.bc.ROBOT_FILE.read_text()),
        lags=dict(
            wheel_lag_s=lc.WHEEL_LAG_S,
            wheel_gain=job["wheel_gain"],
            leg_lag_s=lc.LEG_LAG_S,
            leg_gain=job["leg_gain"],
        ),
    )
    rig_class = type("RolledRig", (Rig,), {"roll": job["roll"]})
    press_at, height = job["press_at"], job["height"]

    def script(rig):
        if rig.first_touch is None:
            return None
        t = rig.t - rig.first_touch
        if t >= press_at:
            if rig.press is None:
                rig.press = rig.t
            if rig.t <= rig.press + 2 * ROLL_WINDOW_S:
                clear = float(np.min(rig.ctl.clearance_now(rig.d)))
                rig.clear = max(rig.clear, clear)
        return {"forward": 0.0, "turn": 0.0, "live": True, "height": None, "mode": 0,
                "jump": int(t >= press_at)}  # fmt: skip

    lower = lc.lowers()

    def hand(rig):
        # Fallen, it would lie there until launch_check's two minutes ran out.
        if rig.writer.fell is not None:
            rig.fell_at = rig.t if rig.fell_at is None else rig.fell_at
            if rig.t > rig.fell_at + 0.5:
                raise lc.Finished
        lower(rig)

    scripted = job["jump"] == lc.balance.SCRIPTED
    jump = lc.balance.SCRIPTED if scripted else lc.pl.Net(Path(job["jump"]))
    why, rig = lc.run(
        "launch", hand, ctx, seconds=press_at + 4.0, rearm=True, script=script,
        jump_net=jump, imu_ms=job["imu_ms"], cmd_ms=job["cmd_ms"], rig_class=rig_class,
        seed=job["seed"], jump_height=height, jump_push=job["push"],
        jump_script=lc.balance.jump_script(job["level"]) if scripted else None,
    )  # fmt: skip
    n = rig.writer
    said = [w for _, w in n.jumps]
    on = next((h for h, w in n.jumps if w.startswith("crouching")), None)
    back = next((h for h, w in n.jumps if w.startswith("handed back")), None)
    out = {"seed": job["seed"], "why": why, "fell": n.fell, "said": said}
    out["stood"] = (
        why == "stood"
        and n.fell is None
        and "lifted" not in n.phases
        and any(w.startswith("jump:") for w in said)
        and back is not None
    )
    p = rig.press
    log = np.array(rig.log) if rig.log else np.zeros((0, 3))
    if p is None or on is None or len(log) == 0:
        out.update(tilt_after=math.inf, peak_tilt=math.inf, roll_rms=math.inf,
                   knee_step=math.inf, clear=0.0, steps=0)  # fmt: skip
        return out
    # A run cut short by a fall ends lying where it fell.
    settled = p + UPRIGHT_BY_S if back is None else max(p + UPRIGHT_BY_S, back + BACK_S)
    after = log[log[:, 0] >= settled]
    out["tilt_after"] = float((after if len(after) else log[-1:])[:, 1].max())
    out["settled_s"] = settled - p
    window = log[log[:, 0] <= max(p + ROLL_WINDOW_S, settled)]
    out["peak_tilt"] = float(window[:, 1].max())
    out["roll_rms"] = float(np.sqrt(np.mean(window[:, 2] ** 2)))
    # The jump policy's knee targets, each knee's step to step, from the crouch to the
    # hand back (or the roll's window, if it never handed back).
    end = back if back is not None else p + ROLL_WINDOW_S
    steps = np.array([k[1:] for k in n.knees if on <= k[0] <= end])
    moves = (
        np.abs(np.diff(steps, axis=0)) if len(steps) > 1 else np.full((1, 2), np.inf)
    )
    out["knee_step"] = float(moves.mean())
    out["steps"] = len(moves)
    out["clear"] = rig.clear
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "jump",
        type=Path,
        help="the jump run packed by sbc/pack_policy.py, or its exported/policy.npz, or "
        "'scripted' for the scripted jump",
    )
    ap.add_argument(
        "--push",
        type=float,
        default=lc.pl.JUMP_PUSH_NM,
        help="the scripted jump's push, Nm, as balance.py's --jump-push",
    )
    ap.add_argument(
        "--level-nm",
        type=float,
        help="the scripted jump's level push, Nm of each wheel, as balance.py's "
        f"--jump-level-nm (default pl.JumpScript's {lc.pl.JumpScript.level_nm:g}; the "
        "robot's launcher passes 0.35)",
    )
    ap.add_argument("--workers", type=int, default=4, help="runs at once")
    ap.add_argument("--wheel-gain", type=float, default=lc.WHEEL_GAIN)
    ap.add_argument("--leg-gain", type=float, default=lc.LEG_GAIN)
    ap.add_argument(
        "--volts",
        type=float,
        default=lc.pl.RATED_VOLTS,
        help="the pack, V, which the motors' speed goes with",
    )
    ap.add_argument(
        "--run",
        type=Path,
        default=lc.DEPLOYED_RUN,
        help="the driving run that hands to it (default: launch_check.py's, on the robot)",
    )
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--height", type=float, default=0.03, help="m asked")
    ap.add_argument(
        "--press-at", type=float, default=5.0, help="s after the wheels touch"
    )
    ap.add_argument("--imu-ms", type=float, default=16.0)
    ap.add_argument("--cmd-ms", type=float, default=6.0)
    f = roll_mode.FITTED
    ap.add_argument(
        "--roll",
        type=float,
        nargs=4,
        metavar=("GAIN", "HZ", "ZETA", "DELAY_MS"),
        default=[f["gain_rad_s_per_rad"], f["hz"], f["zeta"], f["delay_s"] * 1000],
        help="the roll mode: rad/s per rad at its natural frequency, that frequency, "
        "its damping, and its delay from the knees' targets as sent (default: the "
        "robot's fit, roll_mode.FITTED)",
    )
    ap.add_argument("--no-roll", action="store_true", help="without the roll mode")
    args = ap.parse_args()

    scripted = str(args.jump) == lc.balance.SCRIPTED
    pack = args.jump / "exported" / "policy.npz" if args.jump.is_dir() else args.jump
    if not scripted and not pack.exists():
        print(f"FAILED: no {pack}: uv run sbc/pack_policy.py {args.jump}")
        return 1
    gain, hz, zeta, delay_ms = args.roll
    roll = None if args.no_roll else (gain, hz, zeta, delay_ms / 1000)
    asked = (
        f"the scripted jump pushing {args.push:g} Nm, the wheels "
        f"{lc.balance.jump_script(args.level_nm).level_nm:g}"
        if scripted
        else f"{pack.parent.parent.name if args.jump.is_dir() else pack}, "
        f"{args.height * 1000:g} mm asked"
    )
    print(
        f"{asked}, handed to by {args.run.name}, standing; the wheels' torque "
        f"{args.wheel_gain:g} of asked through {lc.WHEEL_LAG_S * 1000:g} ms, the legs' "
        f"{args.leg_gain:g} through {lc.LEG_LAG_S * 1000:g} ms, the wheels' armature "
        f"{lc.WHEEL_ARMATURE_KG_M2:.1e} kg m2, the pack at {args.volts:g} V, IMU "
        f"{args.imu_ms:g} ms, commands {args.cmd_ms:g} ms; "
        + (
            "no roll mode"
            if roll is None
            else f"the roll mode {gain:g} rad/s per rad at {hz:g} Hz, damping {zeta:g}, "
            f"{delay_ms:g} ms after the knees' targets"
        ),
        flush=True,
    )
    jobs = [
        dict(
            run=str(args.run),
            jump=lc.balance.SCRIPTED if scripted else str(pack),
            push=args.push,
            level=args.level_nm,
            wheel_gain=args.wheel_gain,
            leg_gain=args.leg_gain,
            volts=args.volts,
            roll=roll,
            seed=int(s),
            press_at=args.press_at,
            height=args.height,
            imu_ms=args.imu_ms,
            cmd_ms=args.cmd_ms,
        )
        for s in args.seeds.split(",")
    ]
    with ProcessPoolExecutor(max_workers=min(len(jobs), args.workers)) as pool:
        results = list(pool.map(one, jobs))
    good = True
    for r in results:
        marks = {
            "stood": r["stood"],
            "upright": r["tilt_after"] < UPRIGHT_DEG,
            "roll": r["roll_rms"] < ROLL_RMS_RAD_S,
            "knees": r["knee_step"] < KNEE_STEP_RAD,
            # The scripted jump is asked for no height: the push sets it.
            "clear": scripted or r["clear"] >= CLEAR_SHARE * args.height,
        }
        fine = all(marks.values())
        good &= fine
        missed = [k for k, v in marks.items() if not v]
        print(
            f"   seed {r['seed']}: {'ok' if fine else 'FAILED (' + ', '.join(missed) + ')'}: "
            f"{'stood' if r['stood'] else (r['fell'] or r['why'])}; tilted to "
            f"{r['peak_tilt']:.1f} deg, {r['tilt_after']:.1f} after "
            f"{r.get('settled_s', UPRIGHT_BY_S):.2f} s; "
            f"roll {r['roll_rms']:.2f} rad/s rms; knee targets {r['knee_step']:.3f} rad "
            f"a step over {r.get('steps', 0)} steps; cleared "
            f"{r['clear'] * 1000:.0f} mm; {' / '.join(r['said'])}"[:420],
            flush=True,
        )
    print("passed" if good else "FAILED")
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
