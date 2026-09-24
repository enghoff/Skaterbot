"""Measure a trained balance policy: does it stay up, and does it go where it is told?

    source /opt/isaac-venv/bin/activate
    python -u simulation/isaaclab/evaluate.py --headless \\
        --policy /workspace/runs/logs/rsl_rl/wheeled_biped_balance/<run>/exported/policy.pt

A training curve says the reward went up. It does not say what the robot does,
and a policy can climb a reward by standing still and ignoring the command. So
this runs the exported policy -- the same file that would go to the robot --
through one fixed script of commands on a few hundred robots at once, each with
its own randomised friction, masses and armature, and reports what happened:

    0-4 s    stand still, and take a 0.3 m/s shove at 2 s
    4-8 s    forward at 0.4 m/s
    8-12 s   back at 0.3 m/s
    12-16 s  turn on the spot at 1 rad/s
    16-20 s  forward at 0.3 m/s while turning at 0.8 rad/s

For each phase it gives the fraction still upright, the speed and turn-rate
errors of those still up (from a second into the phase, so the reaction time
is not scored as error), and the peak torque at the wheels, hips and knees with
the share of time each spends above the 0.8 Nm thermal rating. A robot that
falls is counted
as fallen for the rest of the run, even though the environment puts it back.
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
parser.add_argument("--num_envs", type=int, default=512)
add_launcher_args(parser)
args = parser.parse_args()

import torch  # noqa: E402
from wheeled_biped_cfg import CONTINUOUS_TORQUE_NM  # noqa: E402
from wheeled_biped_task.env_cfg import WheeledBipedBalanceEnvCfg  # noqa: E402

# (start s, end s, forward m/s, yaw rad/s, name)
SCRIPT = [
    (0.0, 4.0, 0.0, 0.0, "stand, shoved at 2 s"),
    (4.0, 8.0, 0.4, 0.0, "forward 0.4 m/s"),
    (8.0, 12.0, -0.3, 0.0, "back 0.3 m/s"),
    (12.0, 16.0, 0.0, 1.0, "turn 1 rad/s"),
    (16.0, 20.0, 0.3, 0.8, "arc 0.3 m/s, 0.8 rad/s"),
]
SHOVE_AT_S = 2.0
SHOVE_M_S = 0.3
SETTLE_S = 1.0


def main() -> int:
    cfg = WheeledBipedBalanceEnvCfg()
    cfg.scene.num_envs = args.num_envs
    cfg.episode_length_s = SCRIPT[-1][1] + 2.0
    # The shove is scripted here, not random, and the command is too.
    cfg.events.push = None
    cfg.command_resample_s = 1.0e9

    with launch_simulation(cfg, args):
        # Only once Kit is up: see wheeled_biped_task/env_cfg.py.
        from wheeled_biped_task.env import WheeledBipedBalanceEnv

        env = WheeledBipedBalanceEnv(cfg)
        policy = torch.jit.load(args.policy, map_location=env.device).eval()

        obs, _ = env.reset()
        # Every robot starts its episode now, not at a random point in it.
        env.episode_length_buf[:] = 0

        n = env.num_envs
        dt = env.step_dt
        fallen = torch.zeros(n, dtype=torch.bool, device=env.device)
        rows = []

        # Joint groups whose torque is reported, by name, in plant.py's order.
        groups = {
            "wheel": env._wheel_ids,
            "hip": [env._leg_ids[0], env._leg_ids[2]],
            "knee": [env._leg_ids[1], env._leg_ids[3]],
        }

        for start, end, vx, wz, name in SCRIPT:
            env._commands[:, 0] = vx
            env._commands[:, 1] = wz
            lin_err, yaw_err = [], []
            peak = dict.fromkeys(groups, 0.0)
            hot = dict.fromkeys(groups, 0.0)
            samples = 0
            steps = round((end - start) / dt)
            for k in range(steps):
                t = start + k * dt
                if abs(t - SHOVE_AT_S) < dt / 2:
                    vel = env.robot.data.root_vel_w.torch.clone()
                    vel[:, 0] += SHOVE_M_S
                    env.robot.write_root_velocity_to_sim_index(root_velocity=vel)
                with torch.inference_mode():
                    actions = policy(obs["policy"])
                obs, _, terminated, _, _ = env.step(actions)
                fallen |= terminated

                if t - start < SETTLE_S:
                    continue
                up = ~fallen
                if not up.any():
                    continue
                data = env.robot.data
                lin_err.append(
                    (data.root_lin_vel_b.torch[up, 0] - vx).abs().mean().item()
                )
                yaw_err.append(
                    (data.root_ang_vel_b.torch[up, 2] - wz).abs().mean().item()
                )
                torque = data.applied_torque.torch[up].abs()
                for group, ids in groups.items():
                    tau = torque[:, ids]
                    peak[group] = max(peak[group], tau.max().item())
                    hot[group] += (tau > CONTINUOUS_TORQUE_NM).float().mean().item()
                samples += 1

            rows.append(
                {
                    "name": name,
                    "up": 1.0 - fallen.float().mean().item(),
                    "lin": sum(lin_err) / len(lin_err) if lin_err else float("nan"),
                    "yaw": sum(yaw_err) / len(yaw_err) if yaw_err else float("nan"),
                    "peak": peak,
                    "hot": {g: v / max(samples, 1) for g, v in hot.items()},
                }
            )

        print(
            f"\n{n} robots, each with its own randomised friction, masses, armature\n"
        )
        print(
            f"  {'phase':<24} {'upright':>7} {'speed err':>10} {'turn err':>9}"
            "   peak torque, Nm (and time above 0.8 Nm)"
        )
        print(f"  {'':<55}{'wheel':>13} {'hip':>13} {'knee':>13}")
        for row in rows:
            torques = " ".join(
                f"{row['peak'][g]:5.2f} ({row['hot'][g] * 100:3.0f}%)" for g in groups
            )
            print(
                f"  {row['name']:<24} {row['up'] * 100:6.1f}% {row['lin']:7.3f}m/s"
                f" {row['yaw']:6.3f}r/s   {torques}"
            )
        survived = rows[-1]["up"]
        print(f"\nstill upright after {SCRIPT[-1][1]:.0f} s: {survived * 100:.1f}%")
        env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
