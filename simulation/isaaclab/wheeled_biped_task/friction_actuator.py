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

    def compute(self, control_action, joint_pos: torch.Tensor, joint_vel: torch.Tensor):
        control_action = super().compute(control_action, joint_pos, joint_vel)
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
