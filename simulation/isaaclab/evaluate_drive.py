"""Measure what a policy from the driving task does across the motors' envelope, on the flat.

    TASK=Biped-Wheeled-Drive-v0 bash simulation/isaaclab/runpod/train.sh --evaluate-drive \
        --policy <run>/exported/policy.pt

Each command below goes to its own robots, which stand for a second, are told to go (the
command moving at the rate training moved it) and are watched for six seconds more. For
each it reports what the robots still up held over the last two seconds, against what
was asked: speed and turn, the wheels' top speed, how far they lean, how much they rock,
and how far the two legs stand from each other, which is what the task's symmetry costs
and its mirror run are about. Commands come in left and right pairs, since on the robot
this policy's parent turned 0.65 m/s and 2.07 rad/s one way and 0.44 and 1.60 the other.

The motors are held to --motor rad/s with no load, the low end of the range training drew
from. Robots that reach the field's edge are left out and counted, not scored.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from isaaclab_tasks.utils import add_launcher_args, launch_simulation  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--policy", required=True, help="exported TorchScript policy.pt")
parser.add_argument("--robots-per-cell", type=int, default=64)
parser.add_argument("--motor", type=float, default=50.0, help="no-load speed, rad/s")
parser.add_argument(
    "--measured",
    action="store_true",
    help="the motors' measured curve (WheeledBipedDriveMeasuredEnvCfg); --motor then 55",
)
parser.add_argument(
    "--low",
    action="store_true",
    help="the measured motors and the 155 mm ride height (WheeledBipedDriveLowEnvCfg)",
)
parser.add_argument(
    "--d6",
    action="store_true",
    help="D6's task: the robot as it drove, from 165 mm (WheeledBipedDriveD6EnvCfg)",
)
parser.add_argument(
    "--d6-legs",
    action="store_true",
    help="D6's task with the legs' torque late too (WheeledBipedDriveD6LegsEnvCfg)",
)
parser.add_argument(
    "--d7",
    action="store_true",
    help="D7's task: D6's with the robot's 11 Hz shake in it (WheeledBipedDriveD7EnvCfg)",
)
parser.add_argument(
    "--d8",
    action="store_true",
    help="D8's task: D7's with the robot's slow sway in it (WheeledBipedDriveD8EnvCfg)",
)
parser.add_argument(
    "--d9",
    action="store_true",
    help="D9's task: D8's asked for its top speed, often (WheeledBipedDriveD9EnvCfg); "
    "score it at --motor 55 and at its battery's floor, --motor 49.5",
)
add_launcher_args(parser)
args = parser.parse_args()

import isaaclab.terrains as terrain_gen  # noqa: E402
import torch  # noqa: E402
from wheeled_biped_task.drive_env_cfg import (  # noqa: E402
    TOP_WHEEL_RAD_S,
    WheeledBipedDriveD6EnvCfg,
    WheeledBipedDriveD6LegsEnvCfg,
    WheeledBipedDriveD7EnvCfg,
    WheeledBipedDriveD8EnvCfg,
    WheeledBipedDriveD9EnvCfg,
    WheeledBipedDriveEnvCfg,
    WheeledBipedDriveLowEnvCfg,
    WheeledBipedDriveMeasuredEnvCfg,
)

STAND_S = 1.0
GO_S = 6.0
HOLD_S = 2.0  # measured over the last this-many seconds

SPEEDS = (0.25, 0.5, 1.0, 1.5, 2.0, 2.2)
SPINS = (0.5, 1.5, 3.0, 6.0, 12.0, 20.0, 25.0)
ARCS = (
    (0.25, 1.5),
    (0.5, 1.5),
    (0.5, 3.0),
    (1.0, 1.5),
    (1.0, 3.0),
    (1.0, 6.0),
    (1.5, 3.0),
)
HEIGHTS = (0.170, 0.180, 0.190, 0.200, 0.207)
if args.low:
    HEIGHTS = (0.155, 0.160, 0.170, 0.180, 0.190, 0.200, 0.207)
if args.d6 or args.d6_legs or args.d7 or args.d8 or args.d9:
    HEIGHTS = (0.165, 0.170, 0.180, 0.190, 0.200, 0.207)
if args.d9:
    # The band D9 is asked for most, 1.3 to 1.6 m/s, and its top; 2.0 and 2.2, past the
    # top, kept so it can be set beside the runs before it, which were scored there.
    SPEEDS = (0.25, 0.5, 1.0, 1.3, 1.5, 1.6, 2.0, 2.2)


def cells(default_height: float) -> list[tuple[float, float, float]]:
    h = default_height
    out = [(0.0, 0.0, h)]
    out += [(sign * v, 0.0, h) for v in SPEEDS for sign in (1.0, -1.0)]
    out += [(0.0, sign * w, h) for w in SPINS for sign in (1.0, -1.0)]
    out += [(v, sign * w, h) for v, w in ARCS for sign in (1.0, -1.0)]
    out += [(0.0, 0.0, height) for height in HEIGHTS]
    out += [(0.5, 0.0, HEIGHTS[0]), (0.5, 0.0, HEIGHTS[-1])]
    return out


def main() -> int:
    if args.d9:
        cfg = WheeledBipedDriveD9EnvCfg()
    elif args.d8:
        cfg = WheeledBipedDriveD8EnvCfg()
    elif args.d7:
        cfg = WheeledBipedDriveD7EnvCfg()
    elif args.d6_legs:
        cfg = WheeledBipedDriveD6LegsEnvCfg()
    elif args.d6:
        cfg = WheeledBipedDriveD6EnvCfg()
    elif args.low:
        cfg = WheeledBipedDriveLowEnvCfg()
    elif args.measured:
        cfg = WheeledBipedDriveMeasuredEnvCfg()
    else:
        cfg = WheeledBipedDriveEnvCfg()
    # All of the field flat, and robots placed anywhere on it.
    gen = cfg.terrain.terrain_generator
    gen.sub_terrains = {"flat": terrain_gen.MeshPlaneTerrainCfg(proportion=1.0)}
    gen.curriculum = False
    cfg.terrain_curriculum = False
    table = cells(cfg.default_leg_height_m)
    per = args.robots_per_cell
    cfg.scene.num_envs = len(table) * per
    cfg.events.push = None
    scale = args.motor / TOP_WHEEL_RAD_S
    cfg.battery_speed_scale = (scale, scale)
    cfg.command_resample_s = 1.0e9
    cfg.episode_length_s = STAND_S + GO_S + 1.0

    with launch_simulation(cfg, args):
        # Only once Kit is up: see wheeled_biped_task/env_cfg.py.
        from wheeled_biped_task.drive_env import WheeledBipedDriveEnv
        from wheeled_biped_task.drive_fast_env import WheeledBipedDriveFastEnv

        env = (WheeledBipedDriveFastEnv if args.d9 else WheeledBipedDriveEnv)(cfg)
        policy = torch.jit.load(args.policy, map_location=env.device).eval()
        dev = env.device

        def column(i: int) -> torch.Tensor:
            values = torch.tensor([c[i] for c in table], device=dev)
            return values.repeat_interleave(per)

        speed, turn, height = column(0), column(1), column(2)

        obs, _ = env.reset()
        env.episode_length_buf[:] = 0
        env._commands[:, :2] = 0.0
        env._command_targets[:, :2] = 0.0
        env._commands[:, 2] = cfg.default_leg_height_m
        env._command_targets[:, 2] = cfg.default_leg_height_m

        fallen = torch.zeros(env.num_envs, dtype=torch.bool, device=dev)
        gone = torch.zeros(env.num_envs, dtype=torch.bool, device=dev)
        names = (
            "speed",
            "turn",
            "pitch",
            "roll",
            "rock",
            "wheel",
            "hip_gap",
            "leg_right",
            "leg_left",
            "stagger",
        )
        sums = {name: torch.zeros(env.num_envs, device=dev) for name in names}
        wheel_top = torch.zeros(env.num_envs, device=dev)
        steps = round((STAND_S + GO_S) / env.step_dt)
        hold = round(HOLD_S / env.step_dt)
        for k in range(steps):
            if k == round(STAND_S / env.step_dt):
                env._command_targets[:, 0] = speed
                env._command_targets[:, 1] = turn
                # A task that slews the ride height moves to it, as the robot does.
                env._command_targets[:, 2] = height
                if not cfg.command_slew_height_m_s:
                    env._commands[:, 2] = height
            with torch.inference_mode():
                actions = policy(obs["policy"])
            obs, _, terminated, truncated, _ = env.step(actions)
            fallen |= terminated
            gone |= truncated
            if k < steps - hold:
                continue
            data = env.robot.data
            gravity = data.projected_gravity_b.torch
            legs = data.joint_pos.torch[:, env._leg_ids]
            wheels = data.joint_vel.torch[:, env._wheel_ids].abs().max(dim=1).values
            up_down, ahead = env._leg_geometry()
            wheel_top = torch.max(wheel_top, wheels)
            now = {
                "speed": data.root_lin_vel_b.torch[:, 0],
                "turn": data.root_ang_vel_b.torch[:, 2],
                "pitch": torch.rad2deg(torch.atan2(gravity[:, 0], -gravity[:, 2])),
                "roll": torch.rad2deg(torch.asin(gravity[:, 1].clamp(-1.0, 1.0))),
                "rock": data.root_ang_vel_b.torch[:, 1].square(),
                "wheel": wheels,
                "hip_gap": torch.rad2deg(legs[:, 0] - legs[:, 2]),
                "leg_right": up_down[:, 0],
                "leg_left": up_down[:, 1],
                "stagger": ahead[:, 0] - ahead[:, 1],
            }
            for name in names:
                sums[name] += now[name] / hold

        print(
            f"\n{env.num_envs} robots, {per} per command, motors to {args.motor:g} rad/s"
            f" with no load; {args.policy}\n"
        )
        print(
            f"  {'asked':>26}  {'held':>18}  {'up':>4} {'edge':>4}  {'wheels':>12}"
            f"  {'pitch':>6} {'roll':>5} {'rock':>5}  {'hips':>5}"
            f"  {'legs R, L':>9}  {'stagger':>7}"
        )
        for i, (v, w, h) in enumerate(table):
            sl = slice(i * per, (i + 1) * per)
            up = (~fallen[sl]) & (~gone[sl])
            scored = (~gone[sl]).sum().clamp(min=1)
            share = (up.sum() / scored).item() * 100
            if not up.any():
                print(f"  {v:+5.2f} m/s {w:+5.1f} rad/s {h * 1000:3.0f} mm  none up")
                continue

            def mean(name: str) -> float:
                return sums[name][sl][up].mean().item()

            print(
                f"  {v:+5.2f} m/s {w:+5.1f} rad/s {h * 1000:3.0f} mm"
                f"  {mean('speed'):+5.2f} m/s {mean('turn'):+5.1f} /s"
                f"  {share:3.0f}% {gone[sl].sum().item():4d}"
                f"  {mean('wheel'):4.1f} {wheel_top[sl][up].max().item():4.1f} rad/s"
                f"  {mean('pitch'):+5.1f}° {mean('roll'):+4.1f}°"
                f" {torch.rad2deg(sums['rock'][sl][up].sqrt()).mean().item():4.1f}°"
                f"  {mean('hip_gap'):+4.1f}°"
                f"  {mean('leg_right') * 1000:4.0f} {mean('leg_left') * 1000:4.0f}"
                f"  {mean('stagger') * 1000:+5.1f} mm"
            )
        env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
