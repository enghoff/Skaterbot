"""Measure a trained jump policy: does it leave the ground, how close to the
clearance it was asked for, and does it land?

    bash simulation/isaaclab/runpod/train.sh --evaluate-jump --policy <run>/exported/policy.pt

Every robot is asked for one jump, two seconds into its episode, at a fixed
target clearance and a fixed forward speed -- a grid of both across the robots
-- and is then watched for three seconds more. For each cell of the grid it
reports the share that left the ground, the peak wheel clearance they reached
against the target, the share still upright at the end, and how far the torso
leans sideways in the second before the jump and the last second of the run --
because staying upright is not the same as standing straight, and one policy
learned to stand on one locked leg with the torso rolled 12 degrees.
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
parser.add_argument(
    "--targets-mm", default="10,20,40,60,80,100,120", help="target clearances"
)
parser.add_argument("--speeds", default="0,1.0", help="forward speeds, m/s")
add_launcher_args(parser)
args = parser.parse_args()

import torch  # noqa: E402
from wheeled_biped_task.jump_env_cfg import WheeledBipedJumpEnvCfg  # noqa: E402

TARGETS_M = tuple(float(t) / 1000.0 for t in args.targets_mm.split(","))
SPEEDS_M_S = tuple(float(v) for v in args.speeds.split(","))
TRIGGER_AT_S = 2.0
WATCH_S = 3.0


def main() -> int:
    cells = [(t, v) for t in TARGETS_M for v in SPEEDS_M_S]
    cfg = WheeledBipedJumpEnvCfg()
    cfg.scene.num_envs = len(cells) * args.robots_per_cell
    cfg.events.push = None
    cfg.command_resample_s = 1.0e9
    # No random jumps: this script asks for exactly one.
    cfg.jump_interval_s = (1.0e9, 1.0e9)
    cfg.episode_length_s = TRIGGER_AT_S + WATCH_S + 1.0

    with launch_simulation(cfg, args):
        # Only once Kit is up: see wheeled_biped_task/env_cfg.py.
        from wheeled_biped_task.jump_env import WheeledBipedJumpEnv

        env = WheeledBipedJumpEnv(cfg)
        policy = torch.jit.load(args.policy, map_location=env.device).eval()
        dev = env.device
        target = torch.tensor([c[0] for c in cells], device=dev).repeat_interleave(
            args.robots_per_cell
        )
        speed = torch.tensor([c[1] for c in cells], device=dev).repeat_interleave(
            args.robots_per_cell
        )

        obs, _ = env.reset()
        env.episode_length_buf[:] = 0
        env._commands[:, 0] = speed
        env._commands[:, 1] = 0.0
        env._commands[:, 2] = cfg.default_leg_height_m

        fallen = torch.zeros(env.num_envs, dtype=torch.bool, device=dev)
        took_off = torch.zeros_like(fallen)
        peak = torch.zeros(env.num_envs, device=dev)
        # Sideways lean, degrees, summed over the second before the jump and
        # the last second of the run.
        roll_before = torch.zeros(env.num_envs, device=dev)
        roll_after = torch.zeros(env.num_envs, device=dev)
        dt = env.step_dt
        second = round(1.0 / dt)
        steps = round((TRIGGER_AT_S + WATCH_S) / dt)
        for k in range(steps):
            if k == round(TRIGGER_AT_S / dt):
                env._next_jump_in[:] = 0.0
                env._schedule_jumps()
                env._jump_target[:] = target
                # _pre_physics_step will advance the schedule again; the jump
                # has started, so that only moves its clock on.
            with torch.inference_mode():
                actions = policy(obs["policy"])
            obs, _, terminated, _, _ = env.step(actions)
            fallen |= terminated
            took_off |= env._took_off & ~fallen
            peak = torch.where(~fallen, torch.maximum(peak, env._peak), peak)
            gravity_y = env.robot.data.projected_gravity_b.torch[:, 1]
            roll = torch.rad2deg(torch.asin(gravity_y.clamp(-1.0, 1.0))).abs()
            if round(TRIGGER_AT_S / dt) - second <= k < round(TRIGGER_AT_S / dt):
                roll_before += roll / second
            if k >= steps - second:
                roll_after += roll / second

        print(
            f"\n{env.num_envs} robots, {args.robots_per_cell} per cell, one jump each\n"
        )
        print(
            f"  {'target':>7} {'speed':>7} {'took off':>9} {'peak clearance':>18}"
            f" {'error':>8} {'upright':>8} {'lean before/after':>18}"
        )
        for i, (t, v) in enumerate(cells):
            sl = slice(i * args.robots_per_cell, (i + 1) * args.robots_per_cell)
            off = took_off[sl]
            reached = peak[sl][off]
            up = ~fallen[sl]
            before = roll_before[sl][up].mean().item() if up.any() else float("nan")
            after = roll_after[sl][up].mean().item() if up.any() else float("nan")
            mean = reached.mean().item() * 1000 if off.any() else float("nan")
            spread = reached.std().item() * 1000 if off.sum() > 1 else float("nan")
            print(
                f"  {t * 1000:5.0f}mm {v:5.1f}m/s {off.float().mean().item() * 100:8.0f}%"
                f" {mean:9.1f} +/-{spread:4.1f}mm {mean - t * 1000:+7.1f}mm"
                f" {(~fallen[sl]).float().mean().item() * 100:7.0f}%"
                f" {before:8.1f} / {after:4.1f} deg"
            )
        env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
