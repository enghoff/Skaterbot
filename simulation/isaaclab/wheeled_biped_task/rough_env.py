"""Balance and drive over rough ground. The design is in rough_env_cfg.py; this
is what runs, and it is the flat environment with the differences added.

Imported after the simulator has started -- see env_cfg.py for why.
"""

from __future__ import annotations

import math

import isaaclab.sim as sim_utils
import torch
from isaaclab.assets import Articulation
from isaaclab.sensors import ContactSensor, RayCaster

from .env import WheeledBipedBalanceEnv
from .rough_env_cfg import (
    WheeledBipedRoughEnvCfg,
    plant,
    scale_terrain,
    size_gpu_buffers,
)

# The torso's nominal height above the ground, subtracted from the critic's
# height map so the numbers it sees sit around zero.
_NOMINAL_BASE_HEIGHT_M = 0.3


class WheeledBipedRoughEnv(WheeledBipedBalanceEnv):
    cfg: WheeledBipedRoughEnvCfg

    def __init__(
        self, cfg: WheeledBipedRoughEnvCfg, render_mode: str | None = None, **kwargs
    ):
        # Before the simulation exists, and after the training script has set
        # the robot count: the terrain grid and the contact buffers scale with it.
        scale_terrain(cfg)
        size_gpu_buffers(cfg)
        super().__init__(cfg, render_mode, **kwargs)
        # forward speed (m/s), yaw rate (rad/s), leg height (m)
        self._commands = torch.zeros(self.num_envs, 3, device=self.device)
        self._commands[:, 2] = self.cfg.default_leg_height_m

        g = plant.geometry()
        self._upper_leg = g["upper_leg_m"]
        self._lower_leg = g["lower_leg_m"]

        self._base_contact_id, _ = self._contact_sensor.find_sensors("base_link")
        self._wheel_bodies, _ = self.robot.find_bodies(
            ["wheel_right", "wheel_left"], preserve_order=True
        )
        self._wheel_radius = plant.wheel_radius_m()

        # Per-episode speed error, for the curriculum's verdict at reset.
        self._speed_error_sum = torch.zeros(self.num_envs, device=self.device)
        self._step_count = torch.zeros(self.num_envs, device=self.device)

    # -- scene

    def _setup_scene(self):
        self.robot = Articulation(self.cfg.robot)
        self.scene.articulations["robot"] = self.robot
        self._contact_sensor = ContactSensor(self.cfg.contact_sensor)
        self.scene.sensors["contact_sensor"] = self._contact_sensor
        self._height_scanner = RayCaster(self.cfg.height_scanner)
        self.scene.sensors["height_scanner"] = self._height_scanner
        self.cfg.terrain.num_envs = self.scene.cfg.num_envs
        self.cfg.terrain.env_spacing = self.scene.cfg.env_spacing
        self._terrain = self.cfg.terrain.class_type(self.cfg.terrain)
        self.scene.clone_environments(copy_from_source=False)
        # Explicitly, and on the GPU too. Here some twenty robots share each
        # tile's start, and without this they are spawned inside one another.
        self.scene.filter_collisions(global_prim_paths=[self.cfg.terrain.prim_path])
        light_cfg = sim_utils.DomeLightCfg(intensity=2000.0, color=(0.75, 0.75, 0.75))
        light_cfg.func("/World/Light", light_cfg)

    # -- the legs, as the ride height sees them

    def _leg_geometry(self) -> tuple[torch.Tensor, torch.Tensor]:
        """Each leg's hip-to-axle height and the axle's offset ahead of the hip.

        (num_envs, 2) each, right then left, in the torso's own frame -- so
        independent of how the torso is pitched, which is what makes the
        height something the policy can see in its own joint angles.
        """
        q = self.robot.data.joint_pos.torch[:, self._leg_ids]
        hip = q[:, [0, 2]]
        shin = q[:, [1, 3]] - hip
        height = self._upper_leg * torch.cos(hip) + self._lower_leg * torch.cos(shin)
        # Hip flexion swings the wheel forward and knee flexion folds it back.
        ahead = self._upper_leg * torch.sin(hip) - self._lower_leg * torch.sin(shin)
        return height, ahead

    def _wheel_slip(self) -> torch.Tensor:
        """How fast each tyre's contact point moves over the ground, right, left.

        The contact point is the bottom of the wheel, a radius below the axle,
        so its horizontal velocity is the axle's plus the spin's contribution:
        (v_x - r w_y, v_y + r w_x) in the world frame. Zero for a wheel that
        rolls; the skid speed for one that does not, whichever way it skids.
        """
        vel = self.robot.data.body_link_lin_vel_w.torch[:, self._wheel_bodies]
        spin = self.robot.data.body_link_ang_vel_w.torch[:, self._wheel_bodies]
        r = self._wheel_radius
        vx = vel[..., 0] - r * spin[..., 1]
        vy = vel[..., 1] + r * spin[..., 0]
        return torch.sqrt(vx.square() + vy.square())

    def _ground_below(self) -> torch.Tensor:
        """Height of the torso above the ground under it, from the ray caster."""
        hits = self._height_scanner.data.ray_hits_w.torch[..., 2]
        hits = torch.nan_to_num(hits, nan=0.0, posinf=0.0, neginf=0.0)
        return self.robot.data.root_pos_w.torch[:, 2] - hits.mean(dim=1)

    # -- sensing

    def _get_observations(self) -> dict:
        obs = super()._get_observations()
        data = self.robot.data
        hits = self._height_scanner.data.ray_hits_w.torch[..., 2]
        hits = torch.nan_to_num(hits, nan=0.0, posinf=0.0, neginf=0.0)
        scan = (
            self._height_scanner.data.pos_w.torch[:, 2].unsqueeze(1)
            - self._height_scanner.cfg.offset.pos[2]
            - hits
            - _NOMINAL_BASE_HEIGHT_M
        ).clip(-0.5, 0.5)
        obs["critic"] = torch.cat(
            (data.root_lin_vel_b.torch, self._ground_below().unsqueeze(-1), scan),
            dim=-1,
        )
        return obs

    # -- scoring

    def _reward_terms(self) -> dict[str, torch.Tensor]:
        terms = super()._reward_terms()
        c = self.cfg
        height, ahead = self._leg_geometry()
        height_err = torch.square(height.mean(dim=1) - self._commands[:, 2])
        terms["track_leg_height"] = c.rew_track_leg_height * torch.exp(
            -height_err / 0.01**2
        )
        # And in proportion, per metre off: past 20 mm the kernel above pays
        # nothing either way, so gives no direction back to the command.
        terms["leg_height_error"] = c.rew_leg_height_error * height_err.sqrt()
        terms["wheel_fore_aft"] = c.rew_wheel_fore_aft * torch.sum(
            torch.square(ahead), dim=1
        )
        terms["wheel_stagger"] = c.rew_wheel_stagger * torch.square(
            ahead[:, 0] - ahead[:, 1]
        )
        terms["wheel_slip"] = c.rew_wheel_slip * torch.sum(
            torch.square(self._wheel_slip()), dim=1
        )
        for off in ("leg_posture", "leg_asymmetry"):
            if getattr(c, "rew_" + off) == 0.0:
                terms.pop(off, None)

        speed_error = (
            self._commands[:, 0] - self.robot.data.root_lin_vel_b.torch[:, 0]
        ).abs()
        self._speed_error_sum += speed_error
        self._step_count += 1.0
        return terms

    def _get_dones(self) -> tuple[torch.Tensor, torch.Tensor]:
        time_out = self.episode_length_buf >= self.max_episode_length - 1
        tilted = self.robot.data.projected_gravity_b.torch[:, 2] > -math.cos(
            self.cfg.max_tilt_rad
        )
        forces = self._contact_sensor.data.net_forces_w_history.torch
        touched = torch.any(
            torch.max(
                torch.linalg.norm(forces[:, :, self._base_contact_id], dim=-1), dim=1
            )[0]
            > 1.0,
            dim=1,
        )
        return tilted | touched, time_out

    # -- resetting

    def _sample_commands(self, n: int) -> torch.Tensor:
        commands = super()._sample_commands(n)
        lo, hi = self.cfg.command_leg_height_m
        commands[:, 2].uniform_(lo, hi)
        return commands

    def _reset_idx(self, env_ids: torch.Tensor | None):
        if (
            self.cfg.terrain_curriculum
            and env_ids is not None
            and len(env_ids) < self.num_envs
        ):
            mean_error = self._speed_error_sum[env_ids] / self._step_count[
                env_ids
            ].clamp(min=1.0)
            move_up = self.reset_time_outs[env_ids] & (
                mean_error < self.cfg.curriculum_speed_error_m_s
            )
            move_down = self.reset_terminated[env_ids]
            self._terrain.update_env_origins(env_ids, move_up, move_down)
        if env_ids is not None:
            self._speed_error_sum[env_ids] = 0.0
            self._step_count[env_ids] = 0.0

        super()._reset_idx(env_ids)

        self.extras["log"]["Curriculum/terrain_level"] = (
            self._terrain.terrain_levels.float().mean()
        )
