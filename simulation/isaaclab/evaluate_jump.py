"""Measure a trained jump policy: does it leave the ground, how close to the
clearance it was asked for, and does it land?

    bash simulation/isaaclab/runpod/train.sh --evaluate-jump --policy <run>/exported/policy.pt

Every robot is asked for one jump, two seconds into its episode, at a fixed
target clearance and a fixed forward speed -- a grid of both across the robots
-- and is then watched for three seconds more. For each cell of the grid it
reports the share that left the ground, the peak wheel clearance they reached
against the target, the share still upright at the end, how far the torso
itself rose and how long the wheels were off the ground, and how far the torso
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
    "--no-delay", action="store_true", help="without the robot's sensing delays"
)
parser.add_argument(
    "--battery", type=float, default=1.0, help="motor speed, as a share of rated"
)
parser.add_argument(
    "--targets-mm", default="10,20,40,60,80,100,120,150", help="target clearances"
)
parser.add_argument("--speeds", default="0,1.0", help="forward speeds, m/s")
parser.add_argument(
    "--crouch-s",
    type=float,
    default=0.0,
    help="crouch before jumping, as a policy trained with jump_crouch_s expects,"
    " for at most this long",
)
add_launcher_args(parser)
args = parser.parse_args()

import torch  # noqa: E402
from wheeled_biped_task.jump_env_cfg import WheeledBipedJumpEnvCfg  # noqa: E402

TARGETS_M = tuple(float(t) / 1000.0 for t in args.targets_mm.split(","))
SPEEDS_M_S = tuple(float(v) for v in args.speeds.split(","))
TRIGGER_AT_S = 2.0
WATCH_S = 3.0


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
    cells = [(t, v) for t in TARGETS_M for v in SPEEDS_M_S]
    cfg = WheeledBipedJumpEnvCfg()
    # On the flat field: training puts steps in a share of it.
    cfg.steps_fraction = 0.0
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
    # No random jumps: this script asks for exactly one.
    cfg.jump_interval_s = (1.0e9, 1.0e9)
    cfg.jump_crouch_s = args.crouch_s
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
        # The torso's own rise above where it stood before the jump, and how long
        # the wheels were off the ground: what a tuck of the legs alone lacks.
        rise = torch.zeros(env.num_envs, device=dev)
        air = torch.zeros(env.num_envs, device=dev)
        # How far the torso pitches after the trigger, and how long apart the
        # two wheels leave the ground: a tuck that swings the legs up turns
        # the body the other way, and a hop off one wheel is a rock, not a jump.
        pitch = torch.zeros(env.num_envs, device=dev)
        # And the whole robot's centre of mass, which is what a jump raises.
        com = torch.zeros(env.num_envs, device=dev)
        # And the widest the wheels split fore and aft, crouching and jumping:
        # a policy crouched in the splits (crouchmerge) and lifted a wheel.
        split = torch.zeros(env.num_envs, device=dev)
        # And how far its heading turned, beyond the turn asked for.
        turned = torch.zeros(env.num_envs, device=dev)
        # And the jump's lopsidedness: the torso's sideways tilt at its worst,
        # and the widest the two knees bend apart. Every policy up to
        # quickcrouch jumped folding its right knee 50-90 degrees further.
        roll_peak = torch.zeros(env.num_envs, device=dev)
        knees = torch.zeros(env.num_envs, device=dev)
        lifted_at = torch.full((env.num_envs, 2), float("nan"), device=dev)
        dt = env.step_dt
        second = round(1.0 / dt)
        steps = round((TRIGGER_AT_S + WATCH_S) / dt)
        # The press: a crouch first, if there is one, then the trigger. The
        # rises are measured from the robot standing there, before any
        # crouch, so a jump from a crouch is not credited with climbing out
        # of it.
        k_crouch = round(TRIGGER_AT_S / dt)
        stand_com = torch.zeros(env.num_envs, device=dev)
        stand_z = torch.zeros(env.num_envs, device=dev)
        # When the jump was triggered, and the ride height in the last second:
        # how long the crouch took, and whether the robot went back to the
        # height it was asked for.
        started = torch.full((env.num_envs,), float("nan"), device=dev)
        height_after = torch.zeros(env.num_envs, device=dev)
        for k in range(steps):
            if k == k_crouch:
                stand_com = env._com_height().clone()
                stand_z = env._torso_height().clone()
                env._next_jump_in[:] = 0.0
                if args.crouch_s == 0.0:
                    env._schedule_jumps()
                # Otherwise the environment's own schedule crouches, then
                # triggers; _pre_physics_step moves the jump's clock on.
            env._jump_target = torch.where(env._jump_active, target, env._jump_target)
            with torch.inference_mode():
                actions = policy(obs["policy"])
            obs, _, terminated, _, _ = env.step(actions)
            fresh = torch.isnan(started) & env._jump_active & (k >= k_crouch)
            started = torch.where(fresh, (k - k_crouch) * dt, started)
            if k >= steps - second:
                legs, _ = env._leg_geometry()
                height_after += legs.mean(dim=1) / second
            fallen |= terminated
            took_off |= env._took_off & ~fallen
            peak = torch.where(~fallen, torch.maximum(peak, env._peak), peak)
            up_z = torch.where(env._jump_active, env._apex_z - stand_z, 0.0)
            rise = torch.where(~fallen, torch.maximum(rise, up_z), rise)
            air = torch.where(~fallen, torch.maximum(air, env._air_t), air)
            up_com = torch.where(env._jump_active, env._com_apex - stand_com, 0.0)
            com = torch.where(~fallen, torch.maximum(com, up_com), com)
            gravity_y = env.robot.data.projected_gravity_b.torch[:, 1]
            roll = torch.rad2deg(torch.asin(gravity_y.clamp(-1.0, 1.0))).abs()
            if round(TRIGGER_AT_S / dt) - second <= k < round(TRIGGER_AT_S / dt):
                roll_before += roll / second
            if k >= steps - second:
                roll_after += roll / second
            if k >= k_crouch:
                _, ahead = env._leg_geometry()
                apart = (ahead[:, 0] - ahead[:, 1]).abs()
                split = torch.where(~fallen, torch.maximum(split, apart), split)
                drift = env._heading_drift.abs()
                turned = torch.where(~fallen, torch.maximum(turned, drift), turned)
                gravity_x = env.robot.data.projected_gravity_b.torch[:, 0]
                tilt = torch.rad2deg(torch.asin(gravity_x.clamp(-1.0, 1.0))).abs()
                pitch = torch.where(~fallen, torch.maximum(pitch, tilt), pitch)
                rolled = torch.where(env._jump_active, roll, 0.0)
                roll_peak = torch.where(
                    ~fallen, torch.maximum(roll_peak, rolled), roll_peak
                )
                q = env.robot.data.joint_pos.torch[:, env._leg_ids]
                bent = torch.rad2deg(q[:, 1] - q[:, 3]).abs()
                bent = torch.where(env._jump_active | env._crouching, bent, 0.0)
                knees = torch.where(~fallen, torch.maximum(knees, bent), knees)
                off = env._clearance > cfg.wheel_contact_tolerance_m
                first = off & torch.isnan(lifted_at)
                lifted_at = torch.where(first, k * dt, lifted_at)

        print(
            f"\n{env.num_envs} robots, {args.robots_per_cell} per cell, one jump each\n"
        )
        print(
            f"  {'target':>7} {'speed':>7} {'took off':>9} {'peak clearance':>18}"
            f" {'error':>8} {'upright':>8} {'torso rise':>11} {'in the air':>11}"
            f" {'lean before/after':>18} {'pitch peak':>11} {'lift skew':>10}"
            f" {'CoM rise':>9} {'split':>7} {'turned':>7} {'crouch':>7}"
            f" {'height after':>13} {'roll peak':>10} {'knees apart':>12}"
        )
        for i, (t, v) in enumerate(cells):
            sl = slice(i * args.robots_per_cell, (i + 1) * args.robots_per_cell)
            off = took_off[sl]
            reached = peak[sl][off]
            rose = rise[sl][off].mean().item() * 1000 if off.any() else float("nan")
            flew = air[sl][off].mean().item() if off.any() else float("nan")
            up = ~fallen[sl]
            before = roll_before[sl][up].mean().item() if up.any() else float("nan")
            after = roll_after[sl][up].mean().item() if up.any() else float("nan")
            mean = reached.mean().item() * 1000 if off.any() else float("nan")
            spread = reached.std().item() * 1000 if off.sum() > 1 else float("nan")
            tipped = pitch[sl][up].mean().item() if up.any() else float("nan")
            lifted = com[sl][off].mean().item() * 1000 if off.any() else float("nan")
            apart = split[sl][up].mean().item() * 1000 if up.any() else float("nan")
            swung = turned[sl][up].rad2deg().mean().item() if up.any() else float("nan")
            took = started[sl][off].mean().item() if off.any() else float("nan")
            back_to = (
                height_after[sl][up].mean().item() * 1000 if up.any() else float("nan")
            )
            leaned = roll_peak[sl][up].mean().item() if up.any() else float("nan")
            unequal = knees[sl][up].mean().item() if up.any() else float("nan")
            both = off & ~torch.isnan(lifted_at[sl]).any(dim=1)
            skew = (
                (lifted_at[sl][both, 0] - lifted_at[sl][both, 1]).abs().mean().item()
                * 1000
                if both.any()
                else float("nan")
            )
            print(
                f"  {t * 1000:5.0f}mm {v:5.1f}m/s {off.float().mean().item() * 100:8.0f}%"
                f" {mean:9.1f} +/-{spread:4.1f}mm {mean - t * 1000:+7.1f}mm"
                f" {(~fallen[sl]).float().mean().item() * 100:7.0f}%"
                f" {rose:8.1f}mm {flew:9.2f}s"
                f" {before:8.1f} / {after:4.1f} deg"
                f" {tipped:8.1f}deg {skew:7.0f}ms {lifted:7.1f}mm {apart:5.0f}mm"
                f" {swung:5.0f}deg {took:6.2f}s {back_to:9.0f}mm"
                f" {leaned:7.1f}deg {unequal:9.0f}deg"
            )
        env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
