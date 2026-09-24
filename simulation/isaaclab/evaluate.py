"""Measure a trained balance policy: does it stay up, and does it go where it is told?

    bash simulation/isaaclab/runpod/train.sh --evaluate --policy <run>/exported/policy.pt
    bash simulation/isaaclab/runpod/train.sh --evaluate --rough --policy <...>

A training curve says the reward went up. It does not say what the robot does,
and a policy can climb a reward by standing still and ignoring the command. So
this runs the exported policy -- the same file that would go to the robot --
through one fixed script of commands on hundreds of robots at once, each with
its own randomised friction, masses and armature, and reports what happened:

    0-4 s    stand still, and take a 0.3 m/s shove at 2 s
    4-8 s    forward at 0.4 m/s
    8-12 s   back at 0.3 m/s
    12-16 s  turn on the spot at 1 rad/s
    16-20 s  forward at 0.3 m/s while turning at 0.8 rad/s
    20-24 s  (--rough only) forward at 0.2 m/s, crouched to a 190 mm leg

For each phase it gives the fraction still upright, the speed and turn-rate
errors of those still up (from a second into the phase, so the reaction time
is not scored as error), and the peak torque at the wheels, hips and knees with
the share of time each spends above the 0.8 Nm thermal rating -- and the RMS,
which is what heats a motor: a torque that chatters between plus and minus
1 Nm averages to nothing and still cooks the winding. A robot that
falls is counted as fallen for the rest of the run, even though the
environment puts it back.

--rough puts the robots on the rough-ground task's terrain, spread evenly over
every kind of ground and every row of difficulty with the curriculum off, and
adds a table of who stayed up by ground and by difficulty -- which is where the
robot's limits show.
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
parser.add_argument("--rough", action="store_true", help="the rough-ground task")
parser.add_argument("--num_envs", type=int, default=None)
parser.add_argument(
    "--noise-free", action="store_true", help="switch the observation noise off"
)
add_launcher_args(parser)
args = parser.parse_args()

import numpy as np  # noqa: E402
import torch  # noqa: E402
from wheeled_biped_cfg import CONTINUOUS_TORQUE_NM  # noqa: E402

# (start s, end s, forward m/s, yaw rad/s, leg height m or None, name)
SCRIPT = [
    (0.0, 4.0, 0.0, 0.0, None, "stand, shoved at 2 s"),
    (4.0, 8.0, 0.4, 0.0, None, "forward 0.4 m/s"),
    (8.0, 12.0, -0.3, 0.0, None, "back 0.3 m/s"),
    (12.0, 16.0, 0.0, 1.0, None, "turn 1 rad/s"),
    (16.0, 20.0, 0.3, 0.8, None, "arc 0.3 m/s, 0.8 rad/s"),
]
ROUGH_SCRIPT = [(20.0, 24.0, 0.2, 0.0, 0.190, "crouched, forward 0.2")]
SHOVE_AT_S = 2.0
SHOVE_M_S = 0.3
SETTLE_S = 1.0
# A tyre whose contact point moves faster than this over the ground is skidding.
SLIPPING_M_S = 0.3


def make_cfg():
    if args.rough:
        from wheeled_biped_task.rough_env_cfg import WheeledBipedRoughEnvCfg

        cfg = WheeledBipedRoughEnvCfg()
        cfg.terrain_curriculum = False
        rows = cfg.terrain.terrain_generator.num_rows
        cfg.terrain.max_init_terrain_level = rows - 1
        cfg.scene.num_envs = args.num_envs or 1280
    else:
        from wheeled_biped_task.env_cfg import WheeledBipedBalanceEnvCfg

        cfg = WheeledBipedBalanceEnvCfg()
        cfg.scene.num_envs = args.num_envs or 512
    if args.noise_free:
        cfg.observation_noise_model = None
    # The shove is scripted here, not random, and the command is too.
    cfg.events.push = None
    cfg.command_resample_s = 1.0e9
    return cfg


def terrain_names(cfg, types: np.ndarray) -> list[str]:
    """Which kind of ground each robot is on, the way Isaac Lab assigns columns."""
    gen = cfg.terrain.terrain_generator
    names = list(gen.sub_terrains)
    shares = np.array([sub.proportion for sub in gen.sub_terrains.values()])
    edges = np.cumsum(shares / shares.sum())
    return [
        names[int(np.min(np.where(t / gen.num_cols + 0.001 < edges)[0]))] for t in types
    ]


def main() -> int:
    cfg = make_cfg()
    script = SCRIPT + (ROUGH_SCRIPT if args.rough else [])
    cfg.episode_length_s = script[-1][1] + 2.0

    with launch_simulation(cfg, args):
        # Only once Kit is up: see wheeled_biped_task/env_cfg.py.
        if args.rough:
            from wheeled_biped_task.rough_env import WheeledBipedRoughEnv as Env
        else:
            from wheeled_biped_task.env import WheeledBipedBalanceEnv as Env

        env = Env(cfg)
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

        for start, end, vx, wz, height, name in script:
            env._commands[:, 0] = vx
            env._commands[:, 1] = wz
            if args.rough:
                env._commands[:, 2] = height or cfg.default_leg_height_m
            lin_err, yaw_err = [], []
            peak = dict.fromkeys(groups, 0.0)
            hot = dict.fromkeys(groups, 0.0)
            square = dict.fromkeys(groups, 0.0)
            stagger, slipping = [], []
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
                    square[group] += tau.square().mean().item()
                if args.rough:
                    _, ahead = env._leg_geometry()
                    stagger.append((ahead[up, 0] - ahead[up, 1]).abs().mean().item())
                    slip = env._wheel_slip()[up].max(dim=1).values
                    slipping.append((slip > SLIPPING_M_S).float().mean().item())
                samples += 1

            rows.append(
                {
                    "name": name,
                    "up": 1.0 - fallen.float().mean().item(),
                    "lin": sum(lin_err) / len(lin_err) if lin_err else float("nan"),
                    "yaw": sum(yaw_err) / len(yaw_err) if yaw_err else float("nan"),
                    "peak": peak,
                    "hot": {g: v / max(samples, 1) for g, v in hot.items()},
                    "rms": {g: (v / max(samples, 1)) ** 0.5 for g, v in square.items()},
                    "stagger": sum(stagger) / len(stagger) if stagger else float("nan"),
                    "slipping": sum(slipping) / len(slipping)
                    if slipping
                    else float("nan"),
                }
            )

        print(
            f"\n{n} robots, each with its own randomised friction, masses, armature\n"
        )
        print(
            f"  {'phase':<24} {'upright':>7} {'speed err':>10} {'turn err':>9}"
            "   torque, Nm: peak / RMS (time above 0.8 Nm)"
        )
        print(f"  {'':<55}{'wheel':>18} {'hip':>18} {'knee':>18}")
        for row in rows:
            torques = " ".join(
                f"{row['peak'][g]:4.2f} /{row['rms'][g]:5.2f} ({row['hot'][g] * 100:3.0f}%)"
                for g in groups
            )
            print(
                f"  {row['name']:<24} {row['up'] * 100:6.1f}% {row['lin']:7.3f}m/s"
                f" {row['yaw']:6.3f}r/s   {torques}"
            )
        if args.rough:
            print(
                "\n  wheel stagger (fore-aft distance between the wheels) and wheelspin"
                f" (a tyre skidding at more than {SLIPPING_M_S} m/s)"
            )
            for row in rows:
                print(
                    f"  {row['name']:<24} stagger {row['stagger'] * 1000:5.1f} mm"
                    f"   skidding {row['slipping'] * 100:5.1f}% of robots"
                )
        survived = rows[-1]["up"]
        print(f"\nstill upright after {script[-1][1]:.0f} s: {survived * 100:.1f}%")

        if args.rough:
            report_by_ground(cfg, env, fallen)
        env.close()
    return 0


def report_by_ground(cfg, env, fallen) -> None:
    """Who stayed up, by kind of ground and by row of difficulty."""
    levels = env._terrain.terrain_levels.cpu().numpy()
    kinds = terrain_names(cfg, env._terrain.terrain_types.cpu().numpy())
    up = (~fallen).cpu().numpy()
    bands = [
        (0, 2, "rows 0-2"),
        (3, 5, "rows 3-5"),
        (6, 7, "rows 6-7"),
        (8, 9, "rows 8-9"),
    ]

    print("\nstill upright, by ground and difficulty (robots in brackets)\n")
    print(f"  {'ground':<12}" + "".join(f"{b[2]:>16}" for b in bands) + f"{'all':>14}")
    for kind in cfg.terrain.terrain_generator.sub_terrains:
        mask = np.array([k == kind for k in kinds])
        cells = []
        for lo, hi, _ in bands:
            sel = mask & (levels >= lo) & (levels <= hi)
            cells.append(
                f"{up[sel].mean() * 100:9.0f}% ({sel.sum():3d})"
                if sel.any()
                else f"{'--':>16}"
            )
        total = f"{up[mask].mean() * 100:7.0f}% ({mask.sum():3d})" if mask.any() else ""
        print(f"  {kind:<12}" + "".join(f"{c:>16}" for c in cells) + f"{total:>14}")


if __name__ == "__main__":
    raise SystemExit(main())
