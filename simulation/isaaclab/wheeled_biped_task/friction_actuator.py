"""A DC motor that also loses torque to its joint's friction.

Isaac Lab's `friction` on an actuator is not this. It is PhysX's joint friction
coefficient, unitless: it scales with the force the joint carries, so on a
wheel it grows with the robot's weight and on a hanging leg it is next to
nothing. What the robot showed on 4 November 2026 (docs/SYSID.md) is a torque,
the same whatever the joint carries -- the gearbox and the motor's own drag --
so it is applied here, as one: subtracted from what the motor puts out, after
the motor's own torque-speed limit, so it never counts as the motor working.
`applied_effort`, which the costs on torque and heat read, stays the motor's.

The friction turns over smoothly through zero speed, over `coulomb_speed_rad_s`,
because this is an explicit torque on a 2.5 ms step: a sharp one chatters. At
0.1 rad/s it is stable on the lightest joint, a wheel at half its armature
(0.015 Nm / 0.1 rad/s over 4.2e-4 kg m2, times 2.5 ms, is 0.9, under 2). It
leaves out the sticking before a joint moves, which the robot also showed, unless
`static_nm` is given: a higher friction that falls away to `coulomb_nm` over
`static_speed_rad_s`.

Each robot draws its own friction and drag at startup, uniformly over the
configured ranges, as the startup events draw its masses.

A wheel's torque can also be made to follow what is asked late and short, as the
robot's did on 6 November 2026 (plant.WHEEL_RESPONSE): `torque_gain` times the
command, through a first-order lag of `torque_lag_s`, before the motor's own
torque-speed limit. Both are drawn again each episode. Only the torque sent as an
effort is lagged, which for a torque-driven wheel is all of it; a leg's position
loop is left alone, unless `lag_after_pd` is set: then the lag is on what the
position loop asks for, after the motor's own limit, as the robot's legs showed it
(plant.LEG_RESPONSE). Either way `applied_effort` is the torque the motor makes.
"""

from __future__ import annotations

import torch
from isaaclab.actuators import DCMotor, DCMotorCfg
from isaaclab.utils.configclass import configclass


class FrictionDCMotor(DCMotor):
    cfg: FrictionDCMotorCfg

    def __init__(self, cfg: FrictionDCMotorCfg, *args, **kwargs):
        super().__init__(cfg, *args, **kwargs)
        shape = (self._num_envs, self.num_joints)

        def draw(span: tuple[float, float]) -> torch.Tensor:
            lo, hi = span
            return lo + (hi - lo) * torch.rand(shape, device=self._device)

        self.coulomb_nm = draw(cfg.coulomb_nm)
        self.viscous_nm_s_rad = draw(cfg.viscous_nm_s_rad)
        self.static_extra_nm = (draw(cfg.static_nm) - self.coulomb_nm).clamp(min=0.0)

        self._lagged = tuple(cfg.torque_lag_s) != (0.0, 0.0) or tuple(
            cfg.torque_gain
        ) != (1.0, 1.0)
        if self._lagged:
            self.torque_lag_s = draw(cfg.torque_lag_s)
            self.torque_gain = draw(cfg.torque_gain)
            # The torque the motor is making, which moves towards what is asked.
            self._made = torch.zeros(shape, device=self._device)

    def reset(self, env_ids):
        super().reset(env_ids)
        if not self._lagged:
            return
        if env_ids is None:
            env_ids = slice(None)
        rows = self._made[env_ids].shape[0]

        def draw(span: tuple[float, float]) -> torch.Tensor:
            lo, hi = span
            return lo + (hi - lo) * torch.rand(
                (rows, self.num_joints), device=self._device
            )

        self.torque_lag_s[env_ids] = draw(self.cfg.torque_lag_s)
        self.torque_gain[env_ids] = draw(self.cfg.torque_gain)
        self._made[env_ids] = 0.0

    def _lag(self, asked: torch.Tensor) -> torch.Tensor:
        """The torque made this step, moving towards what is asked."""
        step = self.cfg.step_s
        want = self.torque_gain * asked
        self._made = self._made + step / (self.torque_lag_s + step) * (
            want - self._made
        )
        return self._made.clone()

    def compute(self, control_action, joint_pos: torch.Tensor, joint_vel: torch.Tensor):
        after = self._lagged and self.cfg.lag_after_pd
        if self._lagged and not after:
            control_action.joint_efforts = self._lag(control_action.joint_efforts)
        control_action = super().compute(control_action, joint_pos, joint_vel)
        if after:
            self.applied_effort = self._lag(control_action.joint_efforts)
            control_action.joint_efforts = self.applied_effort.clone()
        fading = torch.exp(-torch.square(joint_vel / self.cfg.static_speed_rad_s))
        loss = (self.coulomb_nm + self.static_extra_nm * fading) * torch.tanh(
            joint_vel / self.cfg.coulomb_speed_rad_s
        ) + self.viscous_nm_s_rad * joint_vel
        control_action.joint_efforts = control_action.joint_efforts - loss
        return control_action


@configclass
class FrictionDCMotorCfg(DCMotorCfg):
    class_type: type = FrictionDCMotor

    coulomb_nm: tuple[float, float] = (0.0, 0.0)
    """Friction torque each way, Nm: a range each robot draws from."""

    viscous_nm_s_rad: tuple[float, float] = (0.0, 0.0)
    """Drag in proportion to speed, Nm s/rad: a range each robot draws from."""

    coulomb_speed_rad_s: float = 0.1
    """How quickly the friction turns over through zero speed."""

    static_nm: tuple[float, float] = (0.0, 0.0)
    """Friction torque just off a standstill, Nm, if it is more than coulomb_nm."""

    static_speed_rad_s: float = 0.5
    """How quickly that falls away to coulomb_nm with speed."""

    torque_lag_s: tuple[float, float] = (0.0, 0.0)
    """The first-order lag between the torque asked and the torque made, s: a range
    each robot draws from, each episode. Nothing, the torque made at once."""

    torque_gain: tuple[float, float] = (1.0, 1.0)
    """The torque made as a share of the torque asked: a range drawn each episode."""

    step_s: float = 0.0025
    """The physics step the lag is taken over, s: plant.PHYSICS_DT."""

    lag_after_pd: bool = False
    """Lag the position loop's torque, after the motor's limit, rather than the
    effort sent: a leg's, as the robot's showed it (plant.LEG_RESPONSE)."""
