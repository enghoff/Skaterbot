"""Measure how fast a trained jump-task policy drives and turns, to the envelope.

    bash simulation/isaaclab/runpod/train.sh --evaluate-envelope --policy <run>/exported/policy.pt

The jump task is trained on drive commands up to what the wheels can do at the
actuator's no-load speed (jump_env_cfg.py), so that the policy is never what
limits the robot. This finds where the robot does top out. Each cell of a grid
of commands -- straight ahead and back, turning on the spot, and a few of each
together -- is given to its own robots, which stand for a second, are then told
to go, and are watched for five seconds more. For each it reports the speed and
turn rate held over the last two seconds by the robots still up, against what
was asked, the share still upright, the share of the time a wheel was off the
ground, and the torso's sideways lean. Jumps are not asked for.
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
    "--no-delay", action="store_true", help="without the robot's sensing delays"
)
parser.add_argument(
    "--battery", type=float, default=1.0, help="motor speed, as a share of rated"
)
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


# Standing, at ride heights across the trained range: fractions of the way
# from its bottom to its top.
HEIGHTS = (0.0, 0.33, 0.67, 1.0)


def main() -> int:
    cfg = WheeledBipedJumpEnvCfg()
    # On the flat field: training puts steps in a share of it.
    cfg.steps_fraction = 0.0
    lo, hi = cfg.command_leg_height_m
    cells = [
        (fv * TOP_SPEED_M_S, fw * TOP_YAW_RATE_RAD_S, cfg.default_leg_height_m)
        for fv, fw in FRACTIONS
    ] + [(0.0, 0.0, lo + f * (hi - lo)) for f in HEIGHTS]
    # A policy trained before the battery was one of its inputs has one fewer.
    if policy_inputs(args.policy) == cfg.observation_space - 1:
        cfg.observe_battery = False
        cfg.observation_space -= 1
    cfg.scene.num_envs = len(cells) * args.robots_per_cell
    cfg.events.push = None
    cfg.battery_speed_scale = (args.battery, args.battery)
    if args.no_delay:
        cfg.imu_delay_steps = cfg.joint_delay_steps = cfg.action_delay_steps = (0, 0)
        cfg.delay_jitter_prob = cfg.command_drop_prob = 0.0
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
        height = torch.tensor([c[2] for c in cells], device=dev).repeat_interleave(per)

        dt = env.step_dt
        fallen = torch.zeros(env.num_envs, dtype=torch.bool, device=dev)
        done_speed = torch.zeros(env.num_envs, device=dev)
        done_turn = torch.zeros(env.num_envs, device=dev)
        # Whether a wheel is off the ground, and the sideways lean: in a fast
        # turn the torso should lean in, or the inside wheel unloads and lifts.
        lifted = torch.zeros(env.num_envs, device=dev)
        lean = torch.zeros(env.num_envs, device=dev)
        # How much it rocks: the torso's pitch rate, root mean square.
        sway = torch.zeros(env.num_envs, device=dev)
        legs = torch.zeros(env.num_envs, device=dev)
        steps = round((STAND_S + GO_S) / dt)
        hold = round(HOLD_S / dt)
        for k in range(steps):
            if k == round(STAND_S / dt):
                env._commands[:, 0] = speed
                env._commands[:, 1] = turn
                env._commands[:, 2] = height
            with torch.inference_mode():
                actions = policy(obs["policy"])
            obs, _, terminated, _, _ = env.step(actions)
            fallen |= terminated
            if k >= steps - hold:
                data = env.robot.data
                done_speed += data.root_lin_vel_b.torch[:, 0] / hold
                done_turn += data.root_ang_vel_b.torch[:, 2] / hold
                off = env._wheel_clearance() > cfg.wheel_contact_tolerance_m
                lifted += off.any(dim=1).float() / hold
                gravity_y = data.projected_gravity_b.torch[:, 1].clamp(-1.0, 1.0)
                lean += torch.rad2deg(torch.asin(gravity_y)) / hold
                sway += data.root_ang_vel_b.torch[:, 1].square() / hold
                legs += env._leg_geometry()[0].mean(dim=1) / hold

        print(
            f"\n{env.num_envs} robots, {per} per command; the envelope's tips are"
            f" {TOP_SPEED_M_S:.2f} m/s and {TOP_YAW_RATE_RAD_S:.1f} rad/s\n"
        )
        print(
            f"  {'asked':>20}   {'held (robots still up)':>24}   {'upright':>7}"
            f"  {'a wheel up':>10}  {'lean':>6}  {'sway':>9}  {'ride height':>18}"
        )
        for i, (v, w, h) in enumerate(cells):
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
                f"  {lifted[sl][up].mean().item() * 100:9.0f}%"
                f"  {lean[sl][up].mean().item():+5.1f}°"
                f"  {torch.rad2deg(sway[sl][up].sqrt()).mean().item():5.1f}°/s"
                f"  {h * 1000:4.0f} -> {legs[sl][up].mean().item() * 1000:4.0f} mm"
            )
        env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
