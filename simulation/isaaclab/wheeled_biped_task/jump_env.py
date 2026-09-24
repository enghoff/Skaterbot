"""Jump on command. The design is in jump_env_cfg.py; this is what runs, and it
is the rough-ground environment with the jump added.

Imported after the simulator has started -- see env_cfg.py for why.
"""

from __future__ import annotations

import torch

from .env_cfg import LEG_DAMPING_NM_S_RAD, LEG_STIFFNESS_NM_RAD
from .jump_env_cfg import WheeledBipedJumpEnvCfg
from .rough_env import WheeledBipedRoughEnv

# Scales for the new observations, so each sits near the range of the rest.
_CLEARANCE_SCALE = 10.0  # 0.02-0.07 m -> 0.2-0.7
_TIMER_CLIP_S = 2.0


class WheeledBipedJumpEnv(WheeledBipedRoughEnv):
    cfg: WheeledBipedJumpEnvCfg

    def __init__(
        self, cfg: WheeledBipedJumpEnvCfg, render_mode: str | None = None, **kwargs
    ):
        super().__init__(cfg, render_mode, **kwargs)
        n, dev = self.num_envs, self.device
        self._legs = self.robot.actuators["legs"]

        # The jump, per robot.
        self._jump_active = torch.zeros(n, dtype=torch.bool, device=dev)
        self._jump_t = torch.zeros(n, device=dev)
        self._jump_target = torch.zeros(n, device=dev)
        self._next_jump_in = torch.zeros(n, device=dev)
        self._took_off = torch.zeros(n, dtype=torch.bool, device=dev)
        self._peak = torch.zeros(n, device=dev)
        self._touch_t = torch.full((n, 2), -1.0, device=dev)
        self._landed_t = torch.full((n,), -1.0, device=dev)
        self._clearance = torch.zeros(n, 2, device=dev)
        self._gains = torch.zeros(n, 2, device=dev)

        self._one_off_terms |= {
            "jump_clearance",
            "jump_missed",
            "jump_takeoff",
            "touchdown_speed",
            "touchdown_skew",
            "touchdown_scrub",
        }

    # -- acting

    def _pre_physics_step(self, actions: torch.Tensor):
        # The first six are the balance task's; the last two set the legs' gains.
        self._gains = actions[:, 6:8].clone().clamp(-1.0, 1.0)
        super()._pre_physics_step(actions[:, :6])
        span = self.cfg.leg_gain_range
        kp = LEG_STIFFNESS_NM_RAD * span ** self._gains[:, 0]
        kd = LEG_DAMPING_NM_S_RAD * span ** self._gains[:, 1]
        self._legs.stiffness[:] = kp.unsqueeze(1)
        self._legs.damping[:] = kd.unsqueeze(1)
        self._schedule_jumps()

    def _schedule_jumps(self):
        dt = self.step_dt
        self._jump_t += dt * self._jump_active.float()
        self._next_jump_in -= dt
        start = (~self._jump_active) & (self._next_jump_in <= 0.0)
        lo, hi = self.cfg.jump_clearance_m
        target = torch.empty(self.num_envs, device=self.device).uniform_(lo, hi)
        lo, hi = self.cfg.jump_interval_s
        wait = torch.empty(self.num_envs, device=self.device).uniform_(lo, hi)
        self._jump_active |= start
        self._jump_t = torch.where(start, torch.zeros_like(self._jump_t), self._jump_t)
        self._jump_target = torch.where(start, target, self._jump_target)
        self._next_jump_in = torch.where(start, wait, self._next_jump_in)
        self._took_off &= ~start
        self._peak = torch.where(start, torch.zeros_like(self._peak), self._peak)
        self._touch_t = torch.where(start.unsqueeze(1), -1.0, self._touch_t)
        self._landed_t = torch.where(start, -1.0, self._landed_t)

    # -- sensing

    def _wheel_clearance(self) -> torch.Tensor:
        """How far each wheel's tyre is off the ground, right then left."""
        axle_z = self.robot.data.body_link_pos_w.torch[:, self._wheel_bodies, 2]
        ground = self._terrain.env_origins[:, 2].unsqueeze(1)
        return axle_z - self._wheel_radius - ground

    def _get_observations(self) -> dict:
        obs = super()._get_observations()
        active = self._jump_active.float()
        jump = torch.stack(
            (
                active,
                self._jump_target * _CLEARANCE_SCALE * active,
                self._jump_t.clamp(max=_TIMER_CLIP_S) * active,
            ),
            dim=-1,
        )
        obs["policy"] = torch.cat((obs["policy"], jump), dim=-1)
        obs["critic"] = torch.cat(
            (
                obs["critic"],
                jump,
                (self._clearance.min(dim=1).values * _CLEARANCE_SCALE).unsqueeze(-1),
                (self._peak * _CLEARANCE_SCALE).unsqueeze(-1),
            ),
            dim=-1,
        )
        return obs

    # -- scoring

    def _reward_terms(self) -> dict[str, torch.Tensor]:
        terms = super()._reward_terms()
        c = self.cfg
        active = self._jump_active
        idle = (~active).float()

        # Suspended or eased while jumping: the thermal rating is a matter of
        # minutes and the push is a tenth of a second; the ride height and the
        # wheel's place under the hip are exactly what a jump changes.
        terms["thermal"] = terms["thermal"] * idle
        terms["action_rate"] = terms["action_rate"] * (
            idle + c.jump_action_rate_scale * active.float()
        )
        terms["track_leg_height"] = terms["track_leg_height"] * idle
        terms["wheel_fore_aft"] = terms["wheel_fore_aft"] * idle
        terms["wheel_stagger"] = terms["wheel_stagger"] * idle

        # Where the wheels are.
        self._clearance = self._wheel_clearance()
        on_ground = self._clearance < c.wheel_contact_tolerance_m
        airborne = active & ~on_ground.any(dim=1)
        first_flight = airborne & ~self._took_off
        self._took_off |= airborne
        terms["jump_takeoff"] = c.rew_jump_takeoff * first_flight.float()
        lowest = self._clearance.min(dim=1).values
        # A wheel in the air may spin freely; only a wheel on the ground slips.
        slip = self._wheel_slip().square() * on_ground.float()
        terms["wheel_slip"] = c.rew_wheel_slip * slip.sum(dim=1)
        self._peak = torch.where(
            airborne, torch.maximum(self._peak, lowest), self._peak
        )

        # Each wheel's touchdown, once, after a take-off.
        touching = (
            self._took_off.unsqueeze(1)
            & on_ground
            & (self._touch_t < 0.0)
            & active.unsqueeze(1)
        )
        self._touch_t = torch.where(touching, self._jump_t.unsqueeze(1), self._touch_t)
        wheel_vz = self.robot.data.body_link_lin_vel_w.torch[:, self._wheel_bodies, 2]
        wheel_w = self.robot.data.joint_vel.torch[:, self._wheel_ids]
        ground_speed = self.robot.data.root_lin_vel_b.torch[:, 0].unsqueeze(1)
        scrub = wheel_w * self._wheel_radius - ground_speed
        terms["touchdown_speed"] = c.rew_touchdown_speed * torch.sum(
            touching.float() * wheel_vz.square(), dim=1
        )
        terms["touchdown_scrub"] = c.rew_touchdown_scrub * torch.sum(
            touching.float() * scrub.square(), dim=1
        )

        # The landing: both wheels down. Paid once, for the flight as a whole.
        landed = (
            active
            & self._took_off
            & (self._touch_t >= 0.0).all(dim=1)
            & (self._landed_t < 0.0)
        )
        self._landed_t = torch.where(landed, self._jump_t, self._landed_t)
        error = self._peak - self._jump_target
        terms["jump_clearance"] = (
            c.rew_jump_clearance
            * landed.float()
            * torch.exp(-error.square() / c.jump_clearance_sigma_m**2)
        )
        skew = (self._touch_t[:, 0] - self._touch_t[:, 1]).abs()
        terms["touchdown_skew"] = c.rew_touchdown_skew * landed.float() * skew

        # Upward speed before take-off, as it happens: the dense signal that
        # leads a policy to its first jump.
        rising = self.robot.data.root_link_lin_vel_w.torch[:, 2].clamp(min=0.0, max=1.0)
        terms["jump_lift"] = (
            c.rew_jump_lift * rising * (active & ~self._took_off).float()
        )

        # A jump that never left the ground.
        missed = active & ~self._took_off & (self._jump_t > c.jump_takeoff_window_s)
        terms["jump_missed"] = c.rew_jump_missed * missed.float()

        # The jump ends after the recovery, or when it was missed.
        recovered = (self._landed_t >= 0.0) & (
            self._jump_t > self._landed_t + c.jump_recovery_s
        )
        self._jump_active &= ~(recovered | missed)
        return terms

    # -- resetting

    def _reset_idx(self, env_ids: torch.Tensor | None):
        super()._reset_idx(env_ids)
        if env_ids is None:
            env_ids = torch.arange(self.num_envs, device=self.device)
        lo, hi = self.cfg.jump_interval_s
        self._jump_active[env_ids] = False
        self._jump_t[env_ids] = 0.0
        self._took_off[env_ids] = False
        self._peak[env_ids] = 0.0
        self._touch_t[env_ids] = -1.0
        self._landed_t[env_ids] = -1.0
        self._next_jump_in[env_ids] = torch.empty(
            len(env_ids), device=self.device
        ).uniform_(lo, hi)
