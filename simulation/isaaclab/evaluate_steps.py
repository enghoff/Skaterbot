"""Drive a trained jump-task policy down steps of set heights, and count falls.

    bash simulation/isaaclab/runpod/train.sh --evaluate-steps --policy <run>/exported/policy.pt

The ground is all pyramids of steps -- a platform at the top and steps falling
away on four sides, on the treads training uses -- in columns of one step
height each, 20 to 80 mm. Robots start in the middle of the platforms, stand
for a second, and are then told to drive straight at one of four speeds; any
direction from the top goes down. Half face a flight of steps squarely, so
both wheels drop together, and half at 30 degrees to it, so one wheel drops
first -- which is how a kerb is usually met, and much the harder. A robot
that gets off the bottom of its tile upright has made it. It reports, per
step height, speed and approach, the share that made it, the share that fell,
and the torso's largest pitch on the way down. The policy sees no terrain:
every step is a surprise.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from isaaclab_tasks.utils import add_launcher_args, launch_simulation  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--policy", required=True, help="exported TorchScript policy.pt")
add_launcher_args(parser)
args = parser.parse_args()

import isaaclab.terrains as terrain_gen  # noqa: E402
import torch  # noqa: E402
from wheeled_biped_task.jump_env_cfg import (  # noqa: E402
    STEPS_BORDER_M,
    WheeledBipedJumpEnvCfg,
    stairs_platform_m,
)
from wheeled_biped_task.rough_env_cfg import (  # noqa: E402
    ROBOTS_PER_TILE,
    WHEELED_TERRAINS_CFG,
)

# Four heights by four speeds is sixteen columns, the rough grid's width, so
# scale_terrain leaves it alone: one row, one tile a column.
HEIGHTS_M = (0.02, 0.04, 0.06, 0.08)
SPEEDS_M_S = (0.2, 0.4, 0.7, 1.0)
STAND_S = 1.0
# Long enough to reach the bottom at the slowest speed at 30 degrees: 1.8 m
# from the middle to where the tile ends, 2.1 m at the angle, 10.4 s at 0.2 m/s.
GO_S = 12.0
ANGLED_DEG = 30.0


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
    cfg = WheeledBipedJumpEnvCfg()
    # Its own steps, below, not the share of them training lays out.
    cfg.steps_fraction = 0.0
    if policy_inputs(args.policy) == cfg.observation_space - 1:
        cfg.observe_battery = False
        cfg.observation_space -= 1
    cols = len(HEIGHTS_M) * len(SPEEDS_M_S)
    assert cols == WHEELED_TERRAINS_CFG.num_cols
    per = ROBOTS_PER_TILE
    cfg.scene.num_envs = cols * per
    # One step height a sub-terrain, each a quarter of the columns: with the
    # curriculum on, the generator lays sub-terrains out by column, in order.
    stairs = {
        f"steps_{h * 1000:.0f}mm": terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=1.0,
            step_height_range=(h, h),
            step_width=cfg.step_width_m,
            platform_width=cfg.step_platform_m,
            border_width=STEPS_BORDER_M,
        )
        for h in HEIGHTS_M
    }
    platform = stairs_platform_m(cfg)
    if platform < 0.8:
        raise SystemExit(f"the platform would be {platform:.2f} m across")
    cfg.terrain = cfg.terrain.replace(
        terrain_generator=WHEELED_TERRAINS_CFG.replace(
            curriculum=True, num_rows=1, num_cols=cols, sub_terrains=stairs
        ),
        max_init_terrain_level=0,
    )
    cfg.terrain_curriculum = False
    cfg.events.push = None
    cfg.battery_speed_scale = (1.0, 1.0)
    cfg.command_resample_s = 1.0e9
    cfg.jump_interval_s = (1.0e9, 1.0e9)
    cfg.episode_length_s = STAND_S + GO_S + 1.0

    with launch_simulation(cfg, args):
        # Only once Kit is up: see wheeled_biped_task/env_cfg.py.
        from isaaclab.utils.math import quat_from_euler_xyz
        from wheeled_biped_task.jump_env import WheeledBipedJumpEnv

        env = WheeledBipedJumpEnv(cfg)
        policy = torch.jit.load(args.policy, map_location=env.device).eval()
        dev = env.device
        n = env.num_envs
        col = torch.arange(n, device=dev) // per
        speed = torch.tensor(SPEEDS_M_S, device=dev)[col % len(SPEEDS_M_S)]
        # What the terrain actually built, a column at a time: its top.
        tops = env._terrain.terrain_origins[0, :, 2]
        print(
            f"platform {platform:.2f} m across; heights by column, mm:",
            [round(v * 1000) for v in tops.tolist()],
        )

        obs, _ = env.reset()
        env.episode_length_buf[:] = 0
        # Square to one of the four flights, the second half of each cell
        # turned 30 degrees off it. Upright, where reset tips them slightly.
        ids = torch.arange(n, device=dev)
        angled = (ids % per) >= per // 2
        yaw = torch.randint(0, 4, (n,), device=dev) * (math.pi / 2)
        yaw = yaw + angled.float() * math.radians(ANGLED_DEG)
        pose = env.robot.data.root_link_pose_w.torch.clone()
        zero = torch.zeros(n, device=dev)
        pose[:, 3:7] = quat_from_euler_xyz(zero, zero, yaw)
        env.robot.write_root_pose_to_sim_index(root_pose=pose, env_ids=ids)
        env._commands[:, :2] = 0.0
        env._commands[:, 2] = cfg.default_leg_height_m

        dt = env.step_dt
        stand = round(STAND_S / dt)
        fallen = torch.zeros(n, dtype=torch.bool, device=dev)
        made_it = torch.zeros_like(fallen)
        pitch = torch.zeros(n, device=dev)
        for k in range(stand + round(GO_S / dt)):
            if k == stand:
                env._commands[:, 0] = speed
            with torch.inference_mode():
                actions = policy(obs["policy"])
            obs, _, terminated, truncated, _ = env.step(actions)
            done = made_it | fallen
            # Off the bottom of its tile, the environment's own time-out --
            # unless it fell in the same step.
            made_it |= truncated & ~terminated & ~done & (k > stand)
            fallen |= terminated & ~done
            done = made_it | fallen
            gx = env.robot.data.projected_gravity_b.torch[:, 0].clamp(-1.0, 1.0)
            tilt = torch.rad2deg(torch.asin(gx)).abs()
            pitch = torch.where(done, pitch, torch.maximum(pitch, tilt))

        half = per // 2
        print(f"\n{n} robots, {half} per cell, one descent each\n")
        print(
            f"  {'step':>6} {'speed':>8} {'approach':>9}"
            f" {'made it':>8} {'fell':>6} {'pitch peak':>11}"
        )
        for c in range(cols):
            h = HEIGHTS_M[c // len(SPEEDS_M_S)]
            v = SPEEDS_M_S[c % len(SPEEDS_M_S)]
            for approach, sl in (
                ("square", slice(c * per, c * per + half)),
                (f"{ANGLED_DEG:.0f}deg", slice(c * per + half, (c + 1) * per)),
            ):
                print(
                    f"  {h * 1000:4.0f}mm {v:5.1f}m/s {approach:>9}"
                    f" {made_it[sl].float().mean().item() * 100:7.0f}%"
                    f" {fallen[sl].float().mean().item() * 100:5.0f}%"
                    f" {pitch[sl].mean().item():8.1f}deg"
                )
        env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
