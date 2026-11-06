"""Driving to the motors' envelope. The design is in drive_env_cfg.py; this is the rough
environment with the differences added.

Imported after the simulator has started -- see env_cfg.py for why.
"""

from __future__ import annotations

import torch

from .drive_env_cfg import WheeledBipedDriveEnvCfg
from .rough_env import WheeledBipedRoughEnv


class WheeledBipedDriveEnv(WheeledBipedRoughEnv):
    cfg: WheeledBipedDriveEnvCfg

    def __init__(
        self, cfg: WheeledBipedDriveEnvCfg, render_mode: str | None = None, **kwargs
    ):
        super().__init__(cfg, render_mode, **kwargs)
        # Where the speed and turn commands are headed. The commands the policy sees
        # and is scored on move towards these at a limited rate.
        self._command_targets = self._commands.clone()
        step = self.step_dt
        # The ride height too, if the task slews it: then each episode starts from the
        # crouch's height, where the robot is taken over, and moves to what is asked.
        self._slewed = 3 if cfg.command_slew_height_m_s > 0.0 else 2
        self._slew = torch.tensor(
            [
                cfg.command_slew_m_s2 * step,
                cfg.command_slew_rad_s2 * step,
                cfg.command_slew_height_m_s * step,
            ][: self._slewed],
            device=self.device,
        )
        # The robot's field, tiles and the flat border beyond them, as the jump task's.
        gen = self.cfg.terrain.terrain_generator
        origins = self._terrain.terrain_origins
        self._field_half = torch.stack(
            (
                origins[..., 0].abs().max() + gen.size[0] / 2 + gen.border_width,
                origins[..., 1].abs().max() + gen.size[1] / 2 + gen.border_width,
            )
        ).to(self.device)

    # -- acting

    def _pre_physics_step(self, actions: torch.Tensor):
        n = self._slewed
        before = self._commands[:, :n].clone()
        # This draws a new command for each robot whose time has come.
        super()._pre_physics_step(actions)
        due = (self._command_timer == 0.0).unsqueeze(1)
        self._command_targets = torch.where(due, self._commands, self._command_targets)
        change = self._command_targets[:, :n] - before
        self._commands[:, :n] = before + torch.max(
            torch.min(change, self._slew), -self._slew
        )

    # -- scoring

    def _reward_terms(self) -> dict[str, torch.Tensor]:
        terms = super()._reward_terms()
        c = self.cfg
        data = self.robot.data
        terms["lin_vel_error"] = c.rew_lin_vel_error * torch.abs(
            self._commands[:, 0] - data.root_lin_vel_b.torch[:, 0]
        )
        terms["yaw_rate_error"] = c.rew_yaw_rate_error * torch.abs(
            self._commands[:, 1] - data.root_ang_vel_b.torch[:, 2]
        )
        return terms

    # -- endings and beginnings

    def _get_dones(self) -> tuple[torch.Tensor, torch.Tensor]:
        fallen, time_out = super()._get_dones()
        xy = self.robot.data.root_pos_w.torch[:, :2]
        near_edge = (xy.abs() > self._field_half - self.cfg.edge_margin_m).any(dim=1)
        return fallen, time_out | near_edge

    def _sample_commands(self, n: int) -> torch.Tensor:
        commands = super()._sample_commands(n)
        # Evenly over the diamond |speed|/top + |turn|/top <= 1: a point in the square
        # outside it is reflected into it.
        a = torch.rand(n, device=self.device) * 2.0 - 1.0
        b = torch.rand(n, device=self.device) * 2.0 - 1.0
        outside = a.abs() + b.abs() > 1.0
        a, b = (
            torch.where(outside, a.sign() * (1.0 - b.abs()), a),
            torch.where(outside, b.sign() * (1.0 - a.abs()), b),
        )
        # The standing robots' commands were zeroed; keep them so.
        moving = (commands[:, :2] != 0.0).any(dim=1).float()
        c = self.cfg
        opened = min(
            1.0, self.common_step_counter / max(c.command_envelope_ramp_steps, 1)
        )
        scale = c.command_envelope_start + (1.0 - c.command_envelope_start) * opened
        speed = a * c.command_lin_vel_x[1] * scale
        turn = b * c.command_yaw_rate[1] * scale
        everyday = torch.rand(n, device=self.device) < c.command_everyday_fraction
        lo, hi = c.command_everyday_lin_vel_x
        speed = torch.where(everyday, torch.rand_like(speed) * (hi - lo) + lo, speed)
        lo, hi = c.command_everyday_yaw_rate
        turn = torch.where(everyday, torch.rand_like(turn) * (hi - lo) + lo, turn)
        commands[:, 0] = speed * moving
        commands[:, 1] = turn * moving
        return commands

    def _reset_idx(self, env_ids: torch.Tensor | None):
        super()._reset_idx(env_ids)
        if env_ids is None:
            env_ids = torch.arange(self.num_envs, device=self.device)
        self._command_targets[env_ids] = self._commands[env_ids]
        self._commands[env_ids, :2] = 0.0
        if self._slewed > 2:
            self._commands[env_ids, 2] = self.cfg.default_leg_height_m
