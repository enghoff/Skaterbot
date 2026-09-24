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

        self._actions = torch.zeros(self.num_envs, 6, device=self.device)
        self._previous_actions = torch.zeros_like(self._actions)
        self._leg_targets = torch.zeros(self.num_envs, 4, device=self.device)
        self._wheel_torque = torch.zeros(self.num_envs, 2, device=self.device)

        # forward speed (m/s), yaw rate (rad/s)
        self._commands = torch.zeros(self.num_envs, 2, device=self.device)
        self._command_timer = torch.zeros(self.num_envs, device=self.device)

        self._reward_terms = [
            "track_lin_vel",
            "track_yaw_rate",
            "alive",
            "upright",
            "lin_vel_z",
            "ang_vel_xy",
            "thermal",
            "torque",
            "action_rate",
            "leg_posture",
            "leg_asymmetry",
            "terminated",
        ]
        self._episode_sums = {
            name: torch.zeros(self.num_envs, device=self.device)
            for name in self._reward_terms
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
        self._actions = actions.clone().clamp(-1.0, 1.0)
        default_legs = self.robot.data.default_joint_pos.torch[:, self._leg_ids]
        limits = self.robot.data.soft_joint_pos_limits.torch[:, self._leg_ids]
        self._leg_targets = (
            default_legs + self.cfg.leg_action_scale_rad * self._actions[:, :4]
        ).clamp(limits[..., 0], limits[..., 1])
        self._wheel_torque = self.cfg.wheel_action_scale_nm * self._actions[:, 4:]

        # Commands are resampled on a timer as well as at reset, so an episode
        # contains a change of mind and not just a steady state.
        self._command_timer += self.step_dt
        due = (
            (self._command_timer >= self.cfg.command_resample_s)
            .nonzero(as_tuple=False)
            .flatten()
        )
        if len(due) > 0:
            self._resample_commands(due)

    def _apply_action(self):
        self.robot.set_joint_position_target_index(
            target=self._leg_targets, joint_ids=self._leg_ids
        )
        self.robot.set_joint_effort_target_index(
            target=self._wheel_torque, joint_ids=self._wheel_ids
        )

    # -- sensing

    def _get_observations(self) -> dict:
        self._previous_actions = self._actions.clone()
        data = self.robot.data
        joint_pos = data.joint_pos.torch
        joint_vel = data.joint_vel.torch
        default = data.default_joint_pos.torch
        policy = torch.cat(
            (
                data.root_ang_vel_b.torch * 0.25,
                data.projected_gravity_b.torch,
                self._commands,
                joint_pos[:, self._leg_ids] - default[:, self._leg_ids],
                joint_vel[:, self._leg_ids] * 0.05,
                joint_vel[:, self._wheel_ids] * 0.05,
                self._actions,
            ),
            dim=-1,
        )
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

    def _get_rewards(self) -> torch.Tensor:
        data = self.robot.data
        lin_vel_b = data.root_lin_vel_b.torch
        ang_vel_b = data.root_ang_vel_b.torch
        gravity_b = data.projected_gravity_b.torch
        joint_pos = data.joint_pos.torch
        default = data.default_joint_pos.torch
        torque = data.applied_torque.torch

        lin_err = torch.square(self._commands[:, 0] - lin_vel_b[:, 0])
        yaw_err = torch.square(self._commands[:, 1] - ang_vel_b[:, 2])
        leg_offset = joint_pos[:, self._leg_ids] - default[:, self._leg_ids]
        # right hip, right knee against left hip, left knee
        asymmetry = torch.sum(
            torch.square(leg_offset[:, :2] - leg_offset[:, 2:]), dim=1
        )
        terminated = self.reset_terminated.float()

        c = self.cfg
        terms = {
            "track_lin_vel": c.rew_track_lin_vel * torch.exp(-lin_err / 0.05),
            "track_yaw_rate": c.rew_track_yaw_rate * torch.exp(-yaw_err / 0.25),
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
        }
        # The termination penalty is a one-off, not a rate; everything else is
        # per second of simulated time.
        reward = terms["terminated"].clone()
        for name, value in terms.items():
            if name != "terminated":
                value = value * self.step_dt
                terms[name] = value
                reward += value
        for name, value in terms.items():
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

    def _resample_commands(self, env_ids: torch.Tensor):
        n = len(env_ids)
        lo, hi = self.cfg.command_lin_vel_x
        self._commands[env_ids, 0] = torch.empty(n, device=self.device).uniform_(lo, hi)
        lo, hi = self.cfg.command_yaw_rate
        self._commands[env_ids, 1] = torch.empty(n, device=self.device).uniform_(lo, hi)
        standing = (
            torch.rand(n, device=self.device) < self.cfg.command_standing_fraction
        )
        self._commands[env_ids[standing]] = 0.0
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
        for name in self._reward_terms:
            log["Episode_Reward/" + name] = (
                torch.mean(self._episode_sums[name][env_ids])
                / self.max_episode_length_s
            )
            self._episode_sums[name][env_ids] = 0.0
        log["Episode_Termination/fell"] = torch.count_nonzero(
            self.reset_terminated[env_ids]
        ).item()
        log["Episode_Termination/time_out"] = torch.count_nonzero(
            self.reset_time_outs[env_ids]
        ).item()
        self.extras["log"] = log
