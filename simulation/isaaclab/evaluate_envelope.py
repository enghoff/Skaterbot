"""Measure how fast a trained jump-task policy drives and turns, to the envelope.

    bash simulation/isaaclab/runpod/train.sh --evaluate-envelope --policy <run>/exported/policy.pt

The jump task is trained on drive commands up to what the wheels can do at the
actuator's no-load speed (jump_env_cfg.py), so that the policy is never what
limits the robot. This finds where the robot does top out. Each cell of a grid
of commands -- straight ahead and back, turning on the spot, and a few of each
together -- is given to its own robots, which stand for a second, are then told
to go, and are watched for five seconds more. For each it reports the speed and
turn rate held over the last two seconds by the robots still up, against what
was asked, and the share still upright. Jumps are not asked for.
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
add_launcher_args(parser)
args = parser.parse_args()

import torch  # noqa: E402
from wheeled_biped_task.jump_env_cfg import (  # noqa: E402
    TOP_SPEED_M_S,
    TOP_YAW_RATE_RAD_S,
    WheeledBipedJumpEnvCfg,
)

STAND_S = 1.0
GO_S = 5.0
HOLD_S = 2.0  # measured over the last this-many seconds

# (forward m/s, turn rad/s), as fractions of the envelope's tips
FRACTIONS = [
    (0.0, 0.0),
    (0.25, 0.0),
    (0.5, 0.0),
    (0.75, 0.0),
    (0.9, 0.0),
    (1.0, 0.0),
    (-0.5, 0.0),
    (-1.0, 0.0),
    (0.0, 0.025),
    (0.0, 0.05),
    (0.0, 0.1),
    (0.0, 0.25),
    (0.0, 0.5),
    (0.0, 0.75),
    (0.0, 1.0),
    (0.5, 0.25),
    (0.25, 0.5),
    (0.25, 0.05),
]


def main() -> int:
    cells = [(fv * TOP_SPEED_M_S, fw * TOP_YAW_RATE_RAD_S) for fv, fw in FRACTIONS]
    cfg = WheeledBipedJumpEnvCfg()
    cfg.scene.num_envs = len(cells) * args.robots_per_cell
    cfg.events.push = None
    cfg.command_resample_s = 1.0e9
    cfg.jump_interval_s = (1.0e9, 1.0e9)
    cfg.episode_length_s = STAND_S + GO_S + 1.0

    with launch_simulation(cfg, args):
        # Only once Kit is up: see wheeled_biped_task/env_cfg.py.
        from wheeled_biped_task.jump_env import WheeledBipedJumpEnv

        env = WheeledBipedJumpEnv(cfg)
        policy = torch.jit.load(args.policy, map_location=env.device).eval()
        dev = env.device
        per = args.robots_per_cell
        speed = torch.tensor([c[0] for c in cells], device=dev).repeat_interleave(per)
        turn = torch.tensor([c[1] for c in cells], device=dev).repeat_interleave(per)

        obs, _ = env.reset()
        env.episode_length_buf[:] = 0
        env._commands[:, :2] = 0.0
        env._commands[:, 2] = cfg.default_leg_height_m

        dt = env.step_dt
        fallen = torch.zeros(env.num_envs, dtype=torch.bool, device=dev)
        done_speed = torch.zeros(env.num_envs, device=dev)
        done_turn = torch.zeros(env.num_envs, device=dev)
        steps = round((STAND_S + GO_S) / dt)
        hold = round(HOLD_S / dt)
        for k in range(steps):
            if k == round(STAND_S / dt):
                env._commands[:, 0] = speed
                env._commands[:, 1] = turn
            with torch.inference_mode():
                actions = policy(obs["policy"])
            obs, _, terminated, _, _ = env.step(actions)
            fallen |= terminated
            if k >= steps - hold:
                data = env.robot.data
                done_speed += data.root_lin_vel_b.torch[:, 0] / hold
                done_turn += data.root_ang_vel_b.torch[:, 2] / hold

        print(
            f"\n{env.num_envs} robots, {per} per command; the envelope's tips are"
            f" {TOP_SPEED_M_S:.2f} m/s and {TOP_YAW_RATE_RAD_S:.1f} rad/s\n"
        )
        print(f"  {'asked':>20}   {'held (robots still up)':>24}   {'upright':>7}")
        for i, (v, w) in enumerate(cells):
            sl = slice(i * per, (i + 1) * per)
            up = ~fallen[sl]
            if up.any():
                held = (
                    f"{done_speed[sl][up].mean().item():+5.2f} m/s"
                    f" {done_turn[sl][up].mean().item():+6.1f} rad/s"
                )
            else:
                held = "--"
            print(
                f"  {v:+5.2f} m/s {w:+6.1f} rad/s   {held:>24}"
                f"   {up.float().mean().item() * 100:6.0f}%"
            )
        env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
