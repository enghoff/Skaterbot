"""Shove a trained jump-task policy forward and back, and see what it takes.

    bash simulation/isaaclab/runpod/train.sh --evaluate-push --policy <run>/exported/policy.pt

Each cell -- a shove of a given size, forward or back, while standing or
driving -- is given to its own robots. They are turned to face +x, stand or
drive for two seconds, and are then shoved: the torso's velocity is changed by
the shove at once, as the training's own pushes do. For the next four seconds
it records the share still upright, the torso's largest pitch, how far the
robot gave way (from where it would have been at its commanded speed), and
how long until its speed was back within 0.1 m/s of the command and stayed.
No jumps are asked for.
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
    "--shoves", default="0.5,1.0,1.5,2.0", help="shove sizes, m/s, each way"
)
parser.add_argument("--speeds", default="0,0.5", help="forward speeds, m/s")
add_launcher_args(parser)
args = parser.parse_args()

import torch  # noqa: E402
from wheeled_biped_task.jump_env_cfg import WheeledBipedJumpEnvCfg  # noqa: E402

BEFORE_S = 2.0
WATCH_S = 4.0
SETTLED_M_S = 0.1


def policy_inputs(path: str) -> int:
    """How many inputs an exported policy takes, found by trying."""
    policy = torch.jit.load(path, map_location="cpu").eval()
    for n in range(40, 0, -1):
        try:
            with torch.inference_mode():
                policy(torch.zeros(1, n))
            return n
        except RuntimeError:
            continue
    raise SystemExit(f"{path}: no input width from 1 to 40 works")


def main() -> int:
    sizes = [float(v) for v in args.shoves.split(",")]
    shoves = sizes + [-v for v in sizes]
    speeds = [float(v) for v in args.speeds.split(",")]
    cells = [(s, v) for v in speeds for s in shoves]
    cfg = WheeledBipedJumpEnvCfg()
    # On the flat field: training puts steps in a share of it.
    cfg.steps_fraction = 0.0
    if policy_inputs(args.policy) == cfg.observation_space - 1:
        cfg.observe_battery = False
        cfg.observation_space -= 1
    per = args.robots_per_cell
    cfg.scene.num_envs = len(cells) * per
    cfg.events.push = None
    cfg.battery_speed_scale = (1.0, 1.0)
    cfg.command_resample_s = 1.0e9
    cfg.jump_interval_s = (1.0e9, 1.0e9)
    cfg.episode_length_s = BEFORE_S + WATCH_S + 1.0

    with launch_simulation(cfg, args):
        # Only once Kit is up: see wheeled_biped_task/env_cfg.py.
        from isaaclab.utils.math import quat_from_euler_xyz
        from wheeled_biped_task.jump_env import WheeledBipedJumpEnv

        env = WheeledBipedJumpEnv(cfg)
        policy = torch.jit.load(args.policy, map_location=env.device).eval()
        dev = env.device
        n = env.num_envs
        ids = torch.arange(n, device=dev)
        shove = torch.tensor([c[0] for c in cells], device=dev).repeat_interleave(per)
        speed = torch.tensor([c[1] for c in cells], device=dev).repeat_interleave(per)

        obs, _ = env.reset()
        env.episode_length_buf[:] = 0
        # All facing +x, so a shove along x is straight ahead or behind.
        pose = env.robot.data.root_link_pose_w.torch.clone()
        zero = torch.zeros(n, device=dev)
        pose[:, 3:7] = quat_from_euler_xyz(zero, zero, zero)
        env.robot.write_root_pose_to_sim_index(root_pose=pose, env_ids=ids)
        env._commands[:, 0] = speed
        env._commands[:, 1] = 0.0
        env._commands[:, 2] = cfg.default_leg_height_m

        dt = env.step_dt
        before, watch = round(BEFORE_S / dt), round(WATCH_S / dt)
        fallen = torch.zeros(n, dtype=torch.bool, device=dev)
        pitch = torch.zeros(n, device=dev)
        unsettled = torch.zeros(n, device=dev)
        x0 = torch.zeros(n, device=dev)
        for k in range(before + watch):
            if k == before:
                x0 = env.robot.data.root_link_pos_w.torch[:, 0].clone()
                vel = env.robot.data.root_vel_w.torch.clone()
                vel[:, 0] += shove
                env.robot.write_root_velocity_to_sim_index(
                    root_velocity=vel, env_ids=ids
                )
            with torch.inference_mode():
                actions = policy(obs["policy"])
            obs, _, terminated, _, _ = env.step(actions)
            if k >= before:
                fallen |= terminated
                data = env.robot.data
                gx = data.projected_gravity_b.torch[:, 0].clamp(-1.0, 1.0)
                tilt = torch.rad2deg(torch.asin(gx)).abs()
                pitch = torch.where(~fallen, torch.maximum(pitch, tilt), pitch)
                off = (data.root_lin_vel_b.torch[:, 0] - speed).abs() > SETTLED_M_S
                unsettled = torch.where(off, (k - before + 1) * dt, unsettled)
        x = env.robot.data.root_link_pos_w.torch[:, 0]
        gave = x - x0 - speed * WATCH_S

        print(f"\n{n} robots, {per} per cell, one shove each\n")
        print(
            f"  {'shove':>9} {'speed':>8} {'upright':>8} {'pitch peak':>11}"
            f" {'gave way':>10} {'settled after':>14}"
        )
        for i, (s, v) in enumerate(cells):
            sl = slice(i * per, (i + 1) * per)
            up = ~fallen[sl]
            if up.any():
                tipped = f"{pitch[sl][up].mean().item():8.1f}deg"
                way = f"{gave[sl][up].mean().item() * 1000:+7.0f}mm"
                took = f"{unsettled[sl][up].mean().item():11.2f}s"
            else:
                tipped, way, took = f"{'--':>11}", f"{'--':>10}", f"{'--':>14}"
            print(
                f"  {s:+6.1f}m/s {v:5.1f}m/s {up.float().mean().item() * 100:7.0f}%"
                f" {tipped} {way} {took}"
            )
        env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
