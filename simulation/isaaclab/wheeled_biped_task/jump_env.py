"""Jump on command. The design is in jump_env_cfg.py; this is what runs, and it
is the rough-ground environment with the jump added.

Imported after the simulator has started -- see env_cfg.py for why.
"""

from __future__ import annotations

import math

import torch

from .env_cfg import LEG_DAMPING_NM_S_RAD, LEG_STIFFNESS_NM_RAD
from .jump_env_cfg import WheeledBipedJumpEnvCfg, steps_terrain
from .rough_env import WheeledBipedRoughEnv

# Scales for the new observations, so each sits near the range of the rest.
_CLEARANCE_SCALE = 10.0  # 0.02-0.07 m -> 0.2-0.7
_TIMER_CLIP_S = 2.0
_BATTERY_SCALE = 5.0  # 19.2-25.2 V -> -1 to 0.25


class WheeledBipedJumpEnv(WheeledBipedRoughEnv):
    cfg: WheeledBipedJumpEnvCfg

    def __init__(
        self, cfg: WheeledBipedJumpEnvCfg, render_mode: str | None = None, **kwargs
    ):
        # Before the scene exists: the ground, and the size of the shoves.
        if cfg.steps_fraction > 0.0:
            cfg.terrain = cfg.terrain.replace(
                terrain_generator=steps_terrain(cfg),
                max_init_terrain_level=cfg.steps_init_level,
            )
            cfg.terrain_curriculum = True
        if cfg.push_x_m_s is not None and cfg.events.push is not None:
            cfg.events.push.params["velocity_range"]["x"] = tuple(cfg.push_x_m_s)
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
        # The crouch before it (jump_crouch_s), and the ride height the
        # operator had asked for, to go back to afterwards.
        self._crouching = torch.zeros(n, dtype=torch.bool, device=dev)
        self._crouch_t = torch.zeros(n, device=dev)
        # How far the heading has turned beyond the turn asked for, from the
        # crouch or the trigger to the end of the jump (rew_jump_heading).
        self._heading_drift = torch.zeros(n, device=dev)
        self._asked_height = torch.full((n,), cfg.default_leg_height_m, device=dev)
        # The torso: its height at the trigger, the highest it has been since
        # the wheels left the ground, and how long they have been off it.
        self._start_z = torch.zeros(n, device=dev)
        self._apex_z = torch.zeros(n, device=dev)
        self._air_t = torch.zeros(n, device=dev)
        self._touch_t = torch.full((n, 2), -1.0, device=dev)
        self._landed_t = torch.full((n,), -1.0, device=dev)
        self._clearance = torch.zeros(n, 2, device=dev)
        self._gains = torch.zeros(n, 2, device=dev)
        self._held_gains = torch.zeros(n, 2, device=dev)
        # The whole robot's centre of mass: its height at the trigger and the
        # highest it reaches in flight. A tuck lifts the wheels by folding the
        # legs and moves the centre of mass hardly at all; a jump raises it.
        mass = self.robot.data.default_mass
        mass = torch.as_tensor(getattr(mass, "torch", mass), dtype=torch.float)
        self._mass = mass[:1].to(dev)
        self._com_start = torch.zeros(n, device=dev)
        self._com_apex = torch.zeros(n, device=dev)
        # When each wheel first left the ground in this jump, and whether the
        # gap between the two has been charged.
        self._lift_t = torch.full((n, 2), -1.0, device=dev)
        self._skew_charged = torch.zeros(n, dtype=torch.bool, device=dev)

        self._one_off_terms |= {
            "jump_clearance",
            "jump_missed",
            "jump_takeoff",
            "touchdown_speed",
            "touchdown_skew",
            "touchdown_scrub",
            "jump_shortfall",
            "jump_rise",
            "jump_height",
            "jump_com_rise",
            "liftoff_skew",
            "jump_body_rise",
        }

        # The ground's half-width each way: the tiles, from their centres,
        # and the flat border beyond them. Measured from the tiles alone, the
        # outermost robots started inside the margin and were reset on every
        # step.
        gen = self.cfg.terrain.terrain_generator
        origins = self._terrain.terrain_origins
        self._field_half = torch.stack(
            (
                origins[..., 0].abs().max() + gen.size[0] / 2 + gen.border_width,
                origins[..., 1].abs().max() + gen.size[1] / 2 + gen.border_width,
            )
        ).to(dev)

        # The step tiles: each one's origin is its top platform, above the
        # floor; a flat tile's is on it. Which robots start on steps, and the
        # band of the field, across, that the step columns fill.
        self._tile = torch.tensor(gen.size, device=dev)
        tops = origins[..., 2].amax(dim=0) > 0.005
        self._on_steps = self._terrain.env_origins[:, 2] > 0.005
        if tops.any():
            ys = origins[0, tops, 1]
            half = gen.size[1] / 2
            self._steps_band = (ys.min() - half, ys.max() + half)
        else:
            self._steps_band = None

    # -- acting

    def _pre_physics_step(self, actions: torch.Tensor):
        # The first six are the balance task's; the last two set the legs' gains,
        # which go to the motors in the same command and are as late as it is.
        dropped = (self._late_steps >= self.cfg.decimation).unsqueeze(1)
        self._held_gains = torch.where(dropped, self._held_gains, self._gains)
        self._gains = actions[:, 6:8].clone().clamp(-1.0, 1.0)
        super()._pre_physics_step(actions[:, :6])
        self._schedule_jumps()

    def _apply_action(self):
        gains = torch.where(self._command_late(), self._held_gains, self._gains)
        span = self.cfg.leg_gain_range
        kp = LEG_STIFFNESS_NM_RAD * span ** gains[:, 0]
        kd = LEG_DAMPING_NM_S_RAD * span ** gains[:, 1]
        self._legs.stiffness[:] = kp.unsqueeze(1)
        self._legs.damping[:] = kd.unsqueeze(1)
        super()._apply_action()

    def _schedule_jumps(self):
        dt = self.step_dt
        self._jump_t += dt * self._jump_active.float()
        self._next_jump_in -= dt
        c = self.cfg
        due = (~self._jump_active) & (self._next_jump_in <= 0.0) & ~self._on_steps
        if c.jump_crouch_s > 0.0:
            # A press starts the crouch, and the jump comes the moment the legs
            # reach the bottom of the ride height -- or at jump_crouch_s, if
            # they have not -- rather than after a wait in the crouch.
            self._crouch_t = torch.where(due, self._crouch_t + dt, 0.0)
            height, _ = self._leg_geometry()
            bottom = c.command_leg_height_m[0] + c.jump_crouch_tolerance_m
            low = height.mean(dim=1) <= bottom
            start = due & (low | (self._crouch_t >= c.jump_crouch_s))
        else:
            start = due
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
        z = self._torso_height()
        self._start_z = torch.where(start, z, self._start_z)
        self._apex_z = torch.where(start, z, self._apex_z)
        self._air_t = torch.where(start, torch.zeros_like(self._air_t), self._air_t)
        self._touch_t = torch.where(start.unsqueeze(1), -1.0, self._touch_t)
        self._landed_t = torch.where(start, -1.0, self._landed_t)
        com = self._com_height()
        self._com_start = torch.where(start, com, self._com_start)
        self._com_apex = torch.where(start, com, self._com_apex)
        self._lift_t = torch.where(start.unsqueeze(1), -1.0, self._lift_t)
        self._skew_charged &= ~start
        # The crouch: from the press until both wheels are down again, the
        # ride height asked for is the bottom of its range, as the firmware
        # will ask for it; then the operator's again, not a second crouch
        # while the rest of the jump's window runs out. Never on the steps,
        # where no jump comes.
        if c.jump_crouch_s > 0.0:
            landed = self._landed_t >= 0.0
            crouch = due | (self._jump_active & ~landed)
            self._asked_height = torch.where(
                self._crouching, self._asked_height, self._commands[:, 2]
            )
            self._commands[:, 2] = torch.where(
                crouch, c.command_leg_height_m[0], self._asked_height
            )
            self._crouching = crouch

    # -- sensing

    def _torso_height(self) -> torch.Tensor:
        """How high the torso's origin is above the ground."""
        z = self.robot.data.root_link_pos_w.torch[:, 2]
        return z - self._terrain.env_origins[:, 2]

    def _com_height(self) -> torch.Tensor:
        """How high the whole robot's centre of mass is above the ground."""
        z = self.robot.data.body_com_pos_w.torch[..., 2]
        com = (z * self._mass).sum(dim=1) / self._mass.sum()
        return com - self._terrain.env_origins[:, 2]

    def com_rise(self) -> torch.Tensor:
        """How far the centre of mass has risen above where it was at the trigger."""
        return (self._com_apex - self._com_start).clamp(min=0.0)

    def rise(self) -> torch.Tensor:
        """How far the torso has risen above where it was at the trigger."""
        return (self._apex_z - self._start_z).clamp(min=0.0)

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
        if self.cfg.observe_battery:
            # The pack's voltage against the rated 24 V, as the carrier's
            # INA226 reads it: (V / 24 - 1) x 5, so 0.25 full and -1 at cut-off.
            volts = (self._battery - 1.0) * _BATTERY_SCALE
            obs["policy"] = torch.cat((obs["policy"], volts.unsqueeze(-1)), dim=-1)
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
        # With a crouch asked for, the ride height is paid again from the
        # landing, when the operator's height is asked for again.
        settled = idle
        if c.jump_crouch_s > 0.0:
            settled = (~active | (self._landed_t >= 0.0)).float()
        terms["track_leg_height"] = terms["track_leg_height"] * settled
        terms["leg_height_error"] = terms["leg_height_error"] * settled
        # The wind-up: a crouch to push from, just after the trigger.
        height, ahead = self._leg_geometry()
        winding = (active & (self._jump_t < c.jump_windup_s)).float()
        above = (height.mean(dim=1) - c.command_leg_height_m[0]).clamp(min=0.0)
        terms["jump_windup"] = c.rew_jump_windup * winding * above
        # The wheels split fore and aft while crouching for a jump and in it,
        # per metre, where wheel_stagger below is off or too weak to notice.
        busy = (self._crouching | active).float()
        split = (ahead[:, 0] - ahead[:, 1]).abs()
        terms["jump_stagger"] = c.rew_jump_stagger * busy * split
        # And the two legs bending differently in it, hip against hip and knee
        # against knee, per radian squared.
        legs = self.robot.data.joint_pos.torch[:, self._leg_ids]
        unequal = torch.sum(torch.square(legs[:, :2] - legs[:, 2:]), dim=1)
        terms["jump_leg_asymmetry"] = c.rew_jump_leg_asymmetry * busy * unequal
        # And the heading it turns through, beyond the turn asked for, for
        # as long as it is off: the turn-rate cost charged about 1 for a
        # 53 degree swing, against some 200 for the jump.
        rate = self.robot.data.root_ang_vel_w.torch[:, 2] - self._commands[:, 1]
        self._heading_drift = torch.where(
            busy > 0.0, self._heading_drift + rate * self.step_dt, 0.0
        )
        terms["jump_heading"] = c.rew_jump_heading * busy * self._heading_drift.abs()
        terms["wheel_fore_aft"] = terms["wheel_fore_aft"] * idle
        terms["wheel_stagger"] = terms["wheel_stagger"] * idle
        terms["stand_still"] = terms["stand_still"] * idle
        if c.jump_score_max:
            terms["lin_vel_z"] = terms["lin_vel_z"] * idle
        # Lean against the lean a turn needs: the torso tilted so that gravity
        # and the turn's centripetal acceleration together point down between
        # the wheels, which loads them equally. Level when driving straight.
        data = self.robot.data
        gravity_y = data.projected_gravity_b.torch[:, 1]
        # From the command, not the measured speed and turn: at 1.5 m/s the
        # measured turn rate's wobble swung the target faster than a torso can
        # follow, and the cheapest way out was to stop driving fast.
        # And no further than the legs can lean it: past that, the turn is too
        # tight for the speed, and slowing is the answer, not tipping over.
        accel = self._commands[:, 0] * self._commands[:, 1]
        cap = math.sin(c.max_turn_lean_rad)
        cornering = (accel / torch.sqrt(accel.square() + 9.81**2)).clamp(-cap, cap)
        cornering = cornering * float(c.lean_into_turns)
        terms["torso_roll"] = c.rew_torso_roll * torch.square(gravity_y - cornering)
        terms["lin_vel_error"] = c.rew_lin_vel_error * torch.abs(
            self._commands[:, 0] - data.root_lin_vel_b.torch[:, 0]
        )
        terms["yaw_rate_error"] = c.rew_yaw_rate_error * torch.abs(
            self._commands[:, 1] - data.root_ang_vel_b.torch[:, 2]
        )

        # Where the wheels are.
        self._clearance = self._wheel_clearance()
        on_ground = self._clearance < c.wheel_contact_tolerance_m
        airborne = active & ~on_ground.any(dim=1)
        self._com_apex = torch.where(
            airborne, torch.maximum(self._com_apex, self._com_height()), self._com_apex
        )
        # The two wheels leaving the ground apart is a rock off one of them,
        # charged once per second of the gap when the second one goes.
        first_off = active.unsqueeze(1) & ~on_ground & (self._lift_t < 0.0)
        self._lift_t = torch.where(first_off, self._jump_t.unsqueeze(1), self._lift_t)
        both_off = (self._lift_t >= 0.0).all(dim=1) & ~self._skew_charged
        self._skew_charged |= both_off
        gap = (self._lift_t[:, 0] - self._lift_t[:, 1]).abs()
        terms["liftoff_skew"] = c.rew_liftoff_skew * both_off.float() * gap
        # And the torso pitching while it jumps: swinging the legs up turns
        # the body the other way, 50 degrees in the policies scored on wheel
        # clearance alone.
        gravity_x = data.projected_gravity_b.torch[:, 0]
        terms["jump_pitch"] = c.rew_jump_pitch * active.float() * gravity_x.square()
        first_flight = airborne & ~self._took_off
        self._took_off |= airborne
        terms["jump_takeoff"] = c.rew_jump_takeoff * first_flight.float()
        lowest = self._clearance.min(dim=1).values
        # A wheel off the ground when not jumping, rising to the full cost at
        # wheel_lift_full_m: in a turn the load moves outward, and riding on
        # the outside wheel is the step before rolling over.
        lift = (self._clearance - c.wheel_contact_tolerance_m) / c.wheel_lift_full_m
        terms["wheel_lift"] = c.rew_wheel_lift * idle * lift.clamp(0.0, 1.0).sum(dim=1)
        # A wheel in the air may spin freely; only a wheel on the ground slips.
        slip = self._wheel_slip().square() * on_ground.float()
        terms["wheel_slip"] = c.rew_wheel_slip * slip.sum(dim=1)
        self._peak = torch.where(
            airborne, torch.maximum(self._peak, lowest), self._peak
        )
        self._apex_z = torch.where(
            airborne, torch.maximum(self._apex_z, self._torso_height()), self._apex_z
        )
        self._air_t += self.step_dt * airborne.float()

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
        # The torso's own rise, up to the target: clearance got by lifting the
        # body rather than only by snapping the legs up under it.
        rise_share = torch.minimum(
            self.rise(), self._jump_target
        ) / self._jump_target.clamp(min=1.0e-3)
        terms["jump_rise"] = c.rew_jump_rise * landed.float() * rise_share
        terms["jump_shortfall"] = (
            c.rew_jump_shortfall * landed.float() * (-error).clamp(min=0.0)
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
        if c.jump_score_max:
            # Scored at a fixed time after the trigger, so taking longer to
            # crouch and push costs nothing; the jump lasts until then.
            closing = active & (self._jump_t >= c.jump_window_s)
            scored = closing & (self._landed_t >= 0.0)
            terms["jump_height"] = c.rew_jump_height * scored.float() * self._peak
            # And the torso's own rise in flight, which a tuck does not earn.
            terms["jump_body_rise"] = (
                c.rew_jump_body_rise * scored.float() * self.rise()
            )
            # And the whole robot's centre of mass, which is what a jump is.
            terms["jump_com_rise"] = (
                c.rew_jump_com_rise * scored.float() * self.com_rise()
            )
            recovered = closing
        self._jump_active &= ~(recovered | missed)
        return terms

    # -- commands and endings

    def _sample_commands(self, n: int) -> torch.Tensor:
        commands = super()._sample_commands(n)
        if not self.cfg.command_envelope:
            return commands
        # Evenly over the diamond |speed|/top + |turn|/top <= 1: a point in
        # the square outside it is reflected into it.
        a = torch.rand(n, device=self.device) * 2.0 - 1.0
        b = torch.rand(n, device=self.device) * 2.0 - 1.0
        outside = a.abs() + b.abs() > 1.0
        a, b = (
            torch.where(outside, a.sign() * (1.0 - b.abs()), a),
            torch.where(outside, b.sign() * (1.0 - a.abs()), b),
        )
        # The standing robots' commands were zeroed; keep them so.
        moving = (commands[:, :2] != 0.0).any(dim=1).float()
        # The envelope, opened as far as the ramp has got.
        c = self.cfg
        opened = min(
            1.0, self.common_step_counter / max(c.command_envelope_ramp_steps, 1)
        )
        scale = c.command_envelope_start + (1.0 - c.command_envelope_start) * opened
        speed = a * c.command_lin_vel_x[1] * scale
        turn = b * c.command_yaw_rate[1] * scale
        # And a share of everyday commands, drawn evenly over their ranges.
        everyday = torch.rand(n, device=self.device) < c.command_everyday_fraction
        lo, hi = c.command_everyday_lin_vel_x
        speed = torch.where(everyday, torch.rand_like(speed) * (hi - lo) + lo, speed)
        lo, hi = c.command_everyday_yaw_rate
        turn = torch.where(everyday, torch.rand_like(turn) * (hi - lo) + lo, turn)
        commands[:, 0] = speed * moving
        commands[:, 1] = turn * moving
        return commands

    def _get_dones(self) -> tuple[torch.Tensor, torch.Tensor]:
        fallen, time_out = super()._get_dones()
        xy = self.robot.data.root_pos_w.torch[:, :2]
        near_edge = (xy.abs() > self._field_half - self.cfg.edge_margin_m).any(dim=1)
        if self._steps_band is not None:
            # Off the bottom of its own steps: done, and not a failure.
            off_tile = (
                (xy - self._terrain.env_origins[:, :2]).abs() > self._tile / 2 - 0.2
            ).any(dim=1) & self._on_steps
            # And a robot from the flat, before it drives into steps from below.
            lo, hi = self._steps_band
            y = xy[:, 1]
            into = (y > lo - 0.3) & (y < hi + 0.3) & ~self._on_steps
            near_edge = near_edge | off_tile | into
        return fallen, time_out | near_edge

    # -- resetting

    def _reset_idx(self, env_ids: torch.Tensor | None):
        super()._reset_idx(env_ids)
        if env_ids is None:
            env_ids = torch.arange(self.num_envs, device=self.device)
        lo, hi = self.cfg.jump_interval_s
        self._gains[env_ids] = 0.0
        self._held_gains[env_ids] = 0.0
        self._jump_active[env_ids] = False
        self._jump_t[env_ids] = 0.0
        self._took_off[env_ids] = False
        self._peak[env_ids] = 0.0
        self._start_z[env_ids] = 0.0
        self._apex_z[env_ids] = 0.0
        self._air_t[env_ids] = 0.0
        self._touch_t[env_ids] = -1.0
        self._landed_t[env_ids] = -1.0
        self._com_start[env_ids] = 0.0
        self._com_apex[env_ids] = 0.0
        self._lift_t[env_ids] = -1.0
        self._skew_charged[env_ids] = False
        self._crouching[env_ids] = False
        self._crouch_t[env_ids] = 0.0
        self._heading_drift[env_ids] = 0.0
        self._next_jump_in[env_ids] = torch.empty(
            len(env_ids), device=self.device
        ).uniform_(lo, hi)
