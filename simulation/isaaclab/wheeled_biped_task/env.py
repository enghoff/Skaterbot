"""The balance-and-drive environment. Its configuration, and the reasoning
behind every choice in it, is in env_cfg.py; this file is only what runs.

Imported after the simulator has started -- see env_cfg.py for why that
matters.
"""

from __future__ import annotations

import math

import isaaclab.sim as sim_utils
import torch
import warp as wp
from isaaclab.assets import Articulation
from isaaclab.envs import DirectRLEnv
from isaaclab.utils.math import quat_from_euler_xyz
from wheeled_biped_cfg import continuous_torque_penalty

from .env_cfg import WheeledBipedBalanceEnvCfg, plant


class WheeledBipedBalanceEnv(DirectRLEnv):
    cfg: WheeledBipedBalanceEnvCfg

    def __init__(
        self, cfg: WheeledBipedBalanceEnvCfg, render_mode: str | None = None, **kwargs
    ):
        super().__init__(cfg, render_mode, **kwargs)

        # Isaac Lab's joint order is PhysX's, not this project's, so every
        # joint is resolved by name.
        self._leg_ids, _ = self.robot.find_joints(
            list(plant.LEG_JOINTS), preserve_order=True
        )
        self._wheel_ids, _ = self.robot.find_joints(
            list(plant.WHEEL_JOINTS), preserve_order=True
        )

        # A single number, or one per leg joint in plant.LEG_JOINTS order.
        self._leg_scale = torch.as_tensor(
            self.cfg.leg_action_scale_rad, dtype=torch.float, device=self.device
        )

        self._actions = torch.zeros(self.num_envs, 6, device=self.device)
        self._raw_actions = torch.zeros_like(self._actions)
        self._previous_actions = torch.zeros_like(self._actions)
        self._leg_targets = torch.zeros(self.num_envs, 4, device=self.device)
        self._wheel_torque = torch.zeros(self.num_envs, 2, device=self.device)

        # forward speed (m/s), yaw rate (rad/s)
        self._commands = torch.zeros(self.num_envs, 2, device=self.device)
        self._command_timer = torch.zeros(self.num_envs, device=self.device)

        # Filled on the first scoring pass, from whatever terms it returns, so
        # a subclass that adds or drops a term is logged without registering it.
        self._episode_sums: dict[str, torch.Tensor] = {}
        # Terms paid once, on the step they happen, rather than as a rate.
        self._one_off_terms = {"terminated"}

        # What the sensors read after each physics step of the last policy
        # step, indexed by how many steps old the reading is, for the delays.
        n, dev, d = self.num_envs, self.device, self.cfg.decimation
        self._delays = (
            max(self.cfg.imu_delay_steps[1], self.cfg.joint_delay_steps[1]) > 0
        )
        self._sensor_history = torch.zeros(n, d + 1, 16, device=dev)
        self._history_stale = torch.ones(n, dtype=torch.bool, device=dev)
        self._env_index = torch.arange(n, device=dev)
        self._imu_delay = torch.zeros(n, dtype=torch.long, device=dev)
        self._joint_delay = torch.zeros_like(self._imu_delay)
        self._action_delay = torch.zeros_like(self._imu_delay)
        # The physics steps this policy step still running the last command.
        self._late_steps = torch.zeros_like(self._imu_delay)
        self._substep = 0
        self._held_leg_targets = torch.zeros(n, 4, device=dev)
        self._held_wheel_torque = torch.zeros(n, 2, device=dev)

        # The motors' no-load speeds at the rated voltage, for the battery, and
        # each robot's battery as a share of that voltage.
        self._battery = torch.ones(n, device=dev)
        # Each robot's sensor offsets for the episode (cfg.sensor_bias_std).
        self._sensor_bias = torch.zeros(n, 16, device=dev)
        self._rated_speed = {
            name: act.velocity_limit.clone()
            for name, act in self.robot.actuators.items()
        }

    # -- scene

    def _setup_scene(self):
        self.robot = Articulation(self.cfg.robot)
        self.scene.articulations["robot"] = self.robot
        self.cfg.terrain.num_envs = self.scene.cfg.num_envs
        self.cfg.terrain.env_spacing = self.scene.cfg.env_spacing
        self._terrain = self.cfg.terrain.class_type(self.cfg.terrain)
        self.scene.clone_environments(copy_from_source=False)
        if self.device == "cpu":
            self.scene.filter_collisions(global_prim_paths=[self.cfg.terrain.prim_path])
        light_cfg = sim_utils.DomeLightCfg(intensity=2000.0, color=(0.75, 0.75, 0.75))
        light_cfg.func("/World/Light", light_cfg)

    # -- acting

    def _pre_physics_step(self, actions: torch.Tensor):
        # What the motors ran by the end of the last step, which they keep
        # running until this step's command reaches them.
        self._hold_last_command()
        # Unclipped, for the cost on leaving the action range; the policy's
        # training wrapper no longer clips, so this is the only place that does.
        self._raw_actions = actions.clone()
        self._actions = actions.clone().clamp(-1.0, 1.0)
        default_legs = self.robot.data.default_joint_pos.torch[:, self._leg_ids]
        limits = self.robot.data.soft_joint_pos_limits.torch[:, self._leg_ids]
        self._leg_targets = (
            default_legs + self._leg_scale * self._actions[:, :4]
        ).clamp(limits[..., 0], limits[..., 1])
        self._wheel_torque = self.cfg.wheel_action_scale_nm * self._actions[:, 4:]

        # Commands are resampled on a timer as well as at reset, so an episode
        # contains a change of mind and not just a steady state. Done as a
        # masked update over every robot rather than by gathering the ones
        # that are due, because gathering them makes the CPU wait on the GPU
        # every step, and the simulation here is limited by the CPU.
        self._command_timer += self.step_dt
        due = self._command_timer >= self.cfg.command_resample_s
        fresh = self._sample_commands(self.num_envs)
        self._commands = torch.where(due.unsqueeze(1), fresh, self._commands)
        self._command_timer = torch.where(
            due, torch.zeros_like(self._command_timer), self._command_timer
        )

    def _apply_action(self):
        # Called before each physics step, so the state now is the reading
        # decimation - substep physics steps before the policy's next look.
        if self._delays:
            self._sensor_history[:, self.cfg.decimation - self._substep] = (
                self._sensor_reading()
            )
        late = self._command_late()
        self._substep += 1
        legs = torch.where(late, self._held_leg_targets, self._leg_targets)
        wheels = torch.where(late, self._held_wheel_torque, self._wheel_torque)
        self.robot.set_joint_position_target_index(target=legs, joint_ids=self._leg_ids)
        self.robot.set_joint_effort_target_index(
            target=wheels, joint_ids=self._wheel_ids
        )

    # -- the delays

    def _command_late(self) -> torch.Tensor:
        """(num_envs, 1): whether this physics step still runs the last command."""
        return (self._substep < self._late_steps).unsqueeze(1)

    def _hold_last_command(self):
        """Start a policy step: keep what the motors ran last, pick the lateness."""
        dropped = (self._late_steps >= self.cfg.decimation).unsqueeze(1)
        self._held_leg_targets = torch.where(
            dropped, self._held_leg_targets, self._leg_targets
        )
        self._held_wheel_torque = torch.where(
            dropped, self._held_wheel_torque, self._wheel_torque
        )
        self._substep = 0
        late = self._jittered(self._action_delay)
        p = self.cfg.command_drop_prob
        if p > 0.0:
            lost = torch.rand(self.num_envs, device=self.device) < p
            late = torch.where(lost, self.cfg.decimation, late)
        self._late_steps = late

    def _jittered(self, steps: torch.Tensor) -> torch.Tensor:
        """An episode's delay, one step either way now and then."""
        p = self.cfg.delay_jitter_prob
        if p <= 0.0:
            return steps
        shift = torch.randint_like(steps, -1, 2) * (
            torch.rand(steps.shape, device=self.device) < p
        )
        return (steps + shift).clamp(0, self.cfg.decimation)

    def _sample_delays(self, env_ids: torch.Tensor):
        c = self.cfg
        for (lo, hi), delay in (
            (c.imu_delay_steps, self._imu_delay),
            (c.joint_delay_steps, self._joint_delay),
            (c.action_delay_steps, self._action_delay),
        ):
            delay[env_ids] = torch.randint(
                lo, hi + 1, (len(env_ids),), device=self.device
            )

    # -- sensing

    def _sensor_reading(self) -> torch.Tensor:
        """What the robot's own sensors read now, scaled as the policy sees it.

        The IMU's turn rate and gravity direction, 6, then the encoders' leg
        angles from the crouch, leg speeds and wheel speeds, 10.
        """
        data = self.robot.data
        joint_pos = data.joint_pos.torch
        joint_vel = data.joint_vel.torch
        default = data.default_joint_pos.torch
        return torch.cat(
            (
                data.root_ang_vel_b.torch * 0.25,
                data.projected_gravity_b.torch,
                joint_pos[:, self._leg_ids] - default[:, self._leg_ids],
                joint_vel[:, self._leg_ids] * 0.05,
                joint_vel[:, self._wheel_ids] * 0.05,
            ),
            dim=-1,
        )

    def _get_observations(self) -> dict:
        self._previous_actions = self._actions.clone()
        data = self.robot.data
        now = self._sensor_reading()
        if self._delays:
            history = self._sensor_history
            history[:, 0] = now
            # A robot just reset has no past: its readings are all this one.
            stale = self._history_stale.view(-1, 1, 1)
            history = torch.where(stale, now.unsqueeze(1).expand_as(history), history)
            self._sensor_history = history
            self._history_stale[:] = False
            i = self._env_index
            imu = history[i, self._jittered(self._imu_delay), :6]
            encoders = history[i, self._jittered(self._joint_delay), 6:]
        else:
            imu, encoders = now[:, :6], now[:, 6:]
        # Noise and a per-episode offset on what the sensors read -- and only
        # on that: the commands and the policy's own last outputs are known
        # exactly on the robot. Applied to the whole input, the noise buried
        # the ride-height command, 0.02 on a range of 0.022 m, and no policy
        # ever followed it.
        sensed = torch.cat((imu, encoders), dim=-1) + self._sensor_bias
        if self.cfg.sensor_noise_std > 0.0:
            sensed = sensed + self.cfg.sensor_noise_std * torch.randn_like(sensed)
        imu, encoders = sensed[:, :6], sensed[:, 6:]
        commands = self._commands
        if self.cfg.scale_height_command and commands.shape[1] > 2:
            # The ride height as -1 to 1 over its range, like the other inputs.
            lo, hi = self.cfg.command_leg_height_m
            commands = commands.clone()
            commands[:, 2] = (commands[:, 2] - (lo + hi) / 2) / ((hi - lo) / 2)
        policy = torch.cat((imu, commands, encoders, self._actions), dim=-1)
        critic = torch.cat(
            (
                data.root_lin_vel_b.torch,
                (
                    data.root_pos_w.torch[:, 2] - self._terrain.env_origins[:, 2]
                ).unsqueeze(-1),
            ),
            dim=-1,
        )
        return {"policy": policy, "critic": critic}

    # -- scoring

    def _reward_terms(self) -> dict[str, torch.Tensor]:
        """Each term's reward this step, before scaling by time.

        "terminated" is a one-off on the step a robot falls; every other term
        is a rate, and _get_rewards multiplies it by the step length.
        """
        data = self.robot.data
        lin_vel_b = data.root_lin_vel_b.torch
        ang_vel_b = data.root_ang_vel_b.torch
        gravity_b = data.projected_gravity_b.torch
        joint_pos = data.joint_pos.torch
        default = data.default_joint_pos.torch
        torque = data.applied_torque.torch

        lin_err = torch.square(self._commands[:, 0] - lin_vel_b[:, 0])
        yaw_err = torch.square(self._commands[:, 1] - ang_vel_b[:, 2])
        # The tracking tolerance, widened in proportion to the command where
        # the task asks for it: 0.2 m/s off at 1.9 m/s is a good attempt, and
        # a kernel that scores it as nothing gives no reason to try.
        rel = self.cfg.command_tracking_relative
        lin_tol = 0.05 + torch.square(rel * self._commands[:, 0])
        yaw_tol = 0.25 + torch.square(rel * self._commands[:, 1])
        leg_offset = joint_pos[:, self._leg_ids] - default[:, self._leg_ids]
        # right hip, right knee against left hip, left knee
        asymmetry = torch.sum(
            torch.square(leg_offset[:, :2] - leg_offset[:, 2:]), dim=1
        )
        terminated = self.reset_terminated.float()
        standing = (self._commands[:, :2] == 0.0).all(dim=1).float()
        joint_vel = data.joint_vel.torch[:, self._leg_ids + self._wheel_ids]
        motion = torch.sum(torch.square(joint_vel), dim=1) + 10.0 * torch.sum(
            torch.square(ang_vel_b), dim=1
        )

        c = self.cfg
        terms = {
            "track_lin_vel": c.rew_track_lin_vel * torch.exp(-lin_err / lin_tol),
            "track_yaw_rate": c.rew_track_yaw_rate * torch.exp(-yaw_err / yaw_tol),
            "alive": c.rew_alive * (1.0 - terminated),
            "upright": c.rew_upright * torch.sum(torch.square(gravity_b[:, :2]), dim=1),
            "lin_vel_z": c.rew_lin_vel_z * torch.square(lin_vel_b[:, 2]),
            "ang_vel_xy": c.rew_ang_vel_xy
            * torch.sum(torch.square(ang_vel_b[:, :2]), dim=1),
            "thermal": continuous_torque_penalty(torque, weight=c.rew_thermal),
            "torque": c.rew_torque * torch.sum(torch.square(torque), dim=1),
            "action_rate": c.rew_action_rate
            * torch.sum(torch.square(self._actions - self._previous_actions), dim=1),
            "leg_posture": c.rew_leg_posture
            * torch.sum(torch.square(leg_offset), dim=1),
            "leg_asymmetry": c.rew_leg_asymmetry * asymmetry,
            "terminated": c.rew_terminated * terminated,
            "stand_still": c.rew_stand_still
            * standing
            * torch.exp(-motion / c.stand_still_tolerance),
            # Asking for more than the action range allows. Without it a policy
            # clipped at +/-1 learns to shout: the first rough policy's wheel
            # output swung +/-20, a bang-bang controller behind the clip.
            "action_bound": c.rew_action_bound
            * torch.sum(
                torch.square((self._raw_actions.abs() - 1.0).clamp(min=0.0)), dim=1
            ),
        }
        return terms

    def _get_rewards(self) -> torch.Tensor:
        terms = self._reward_terms()
        # The termination penalty is a one-off, not a rate; everything else is
        # per second of simulated time.
        reward = torch.zeros(self.num_envs, device=self.device)
        for name in self._one_off_terms & terms.keys():
            reward += terms[name]
        for name, value in terms.items():
            if name not in self._one_off_terms:
                value = value * self.step_dt
                terms[name] = value
                reward += value
        for name, value in terms.items():
            if name not in self._episode_sums:
                self._episode_sums[name] = torch.zeros(
                    self.num_envs, device=self.device
                )
            self._episode_sums[name] += value
        return reward

    def _get_dones(self) -> tuple[torch.Tensor, torch.Tensor]:
        data = self.robot.data
        time_out = self.episode_length_buf >= self.max_episode_length - 1
        # projected gravity's z is -cos(tilt) for any direction of lean
        tilted = data.projected_gravity_b.torch[:, 2] > -math.cos(self.cfg.max_tilt_rad)
        height = data.root_pos_w.torch[:, 2] - self._terrain.env_origins[:, 2]
        collapsed = height < self.cfg.min_base_height_m
        return tilted | collapsed, time_out

    # -- resetting

    def _sample_commands(self, n: int) -> torch.Tensor:
        """A fresh command for each of n robots: speed, turn rate, and any more."""
        commands = torch.zeros(n, self._commands.shape[1], device=self.device)
        lo, hi = self.cfg.command_lin_vel_x
        commands[:, 0].uniform_(lo, hi)
        lo, hi = self.cfg.command_yaw_rate
        commands[:, 1].uniform_(lo, hi)
        standing = (
            torch.rand(n, device=self.device) < self.cfg.command_standing_fraction
        )
        commands[:, :2] *= (~standing).float().unsqueeze(1)
        return commands

    def _resample_commands(self, env_ids: torch.Tensor):
        self._commands[env_ids] = self._sample_commands(len(env_ids))
        self._command_timer[env_ids] = 0.0

    def _reset_idx(self, env_ids: torch.Tensor | None):
        if env_ids is None or len(env_ids) == self.num_envs:
            env_ids = wp.to_torch(self.robot._ALL_INDICES)
        self.robot.reset(env_ids)
        super()._reset_idx(env_ids)
        if len(env_ids) == self.num_envs:
            # Spread the first resets out so the whole batch does not fall and
            # reset in lockstep.
            self.episode_length_buf[:] = torch.randint_like(
                self.episode_length_buf, high=int(self.max_episode_length)
            )

        self._actions[env_ids] = 0.0
        self._previous_actions[env_ids] = 0.0
        self._resample_commands(env_ids)

        # A new episode's delays and battery, and nothing held over from the
        # last one's commands or readings.
        self._sample_delays(env_ids)
        self._history_stale[env_ids] = True
        self._sensor_bias[env_ids] = self.cfg.sensor_bias_std * torch.randn(
            len(env_ids), 16, device=self.device
        )
        default_legs = self.robot.data.default_joint_pos.torch[env_ids][
            :, self._leg_ids
        ]
        self._leg_targets[env_ids] = default_legs
        self._held_leg_targets[env_ids] = default_legs
        self._wheel_torque[env_ids] = 0.0
        self._held_wheel_torque[env_ids] = 0.0
        lo, hi = self.cfg.battery_speed_scale
        if (lo, hi) != (1.0, 1.0):
            charge = torch.empty(len(env_ids), 1, device=self.device).uniform_(lo, hi)
            self._battery[env_ids] = charge.squeeze(1)
            for name, act in self.robot.actuators.items():
                act.velocity_limit[env_ids] = self._rated_speed[name][env_ids] * charge

        joint_pos = self.robot.data.default_joint_pos.torch[env_ids].clone()
        joint_vel = self.robot.data.default_joint_vel.torch[env_ids].clone()
        root_pose = self.robot.data.default_root_pose.torch[env_ids].clone()
        root_vel = self.robot.data.default_root_vel.torch[env_ids].clone()
        root_pose[:, :3] += self._terrain.env_origins[env_ids]
        # A small random yaw so the robots do not all face one way, and a small
        # random lean so every episode begins with something to correct.
        n = len(env_ids)
        yaw = torch.empty(n, device=self.device).uniform_(-math.pi, math.pi)
        pitch = torch.empty(n, device=self.device).uniform_(-0.05, 0.05)
        root_pose[:, 3:7] = quat_from_euler_xyz(torch.zeros_like(yaw), pitch, yaw)

        self.robot.write_root_pose_to_sim_index(root_pose=root_pose, env_ids=env_ids)
        self.robot.write_root_velocity_to_sim_index(
            root_velocity=root_vel, env_ids=env_ids
        )
        self.robot.write_joint_position_to_sim_index(
            position=joint_pos, env_ids=env_ids
        )
        self.robot.write_joint_velocity_to_sim_index(
            velocity=joint_vel, env_ids=env_ids
        )

        log = {}
        for name in self._episode_sums:
            log["Episode_Reward/" + name] = (
                torch.mean(self._episode_sums[name][env_ids])
                / self.max_episode_length_s
            )
            self._episode_sums[name][env_ids] = 0.0
        # Tensors, not .item(): rsl_rl takes either, and .item() would make the
        # CPU wait for the GPU on every step some robot resets -- most steps.
        log["Episode_Termination/fell"] = torch.count_nonzero(
            self.reset_terminated[env_ids]
        ).float()
        log["Episode_Termination/time_out"] = torch.count_nonzero(
            self.reset_time_outs[env_ids]
        ).float()
        self.extras["log"] = log
