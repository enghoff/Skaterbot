"""One actuator, as the simulator models it and with what the bench is to measure.

The motor law is the training simulator's own: MIT mode's PD plus feed-forward,
then the straight torque-speed line Isaac Lab's DCMotor draws from 3 Nm at
standstill to nothing at the no-load speed (simulation/mujoco/drive.py's
_saturate). Four things are added, which are what stage A of docs/SYSID.md
measures: the inertia at the output (the rotor's, reflected through the 7:1,
plus whatever is bolted on), Coulomb and viscous friction, the ratio of the
torque delivered to the torque commanded, and how long a command takes to
become torque.

`simulate` runs many short windows of one joint at once, each from a measured
state, under the commands logged for it: that is how a fit compares model and
motor without small errors integrating into large ones.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

# The simulator's figures (simulation/robot.py ACTUATOR), as the starting point.
PEAK_NM = 3.0
NO_LOAD_RAD_S = 48.2
ARMATURE_KG_M2 = 2.3e-4
# Coulomb friction is smoothed over this much speed, so it has a slope to
# integrate rather than a step; well under the 0.024 rad/s a report resolves.
STICTION_RAD_S = 0.02


@dataclass
class Motor:
    inertia: float = ARMATURE_KG_M2  # kg m2 at the output, everything turning
    coulomb: float = 0.0  # Nm
    viscous: float = 0.0  # Nm s/rad
    scale: float = 1.0  # torque delivered over torque commanded
    delay: float = 0.0  # s, from a command reaching the motor to its torque
    peak: float = PEAK_NM
    no_load: float = NO_LOAD_RAD_S

    def as_dict(self) -> dict:
        return asdict(self)


def saturate(tau, v, peak=PEAK_NM, no_load=NO_LOAD_RAD_S):
    """drive.py's _saturate: the torque-speed line, both ways."""
    hi = np.clip(peak * (1.0 - v / no_load), 0.0, peak)
    lo = np.clip(peak * (-1.0 - v / no_load), -peak, 0.0)
    return np.clip(tau, lo, hi)


def mit(table, p, v):
    """MIT mode's torque from rows of (p, v, kp, kd, tau) at position p, speed v."""
    return (
        table[..., 2] * (table[..., 0] - p)
        + table[..., 3] * (table[..., 1] - v)
        + table[..., 4]
    )


def delivered(motor: Motor, table, p, v):
    """What reaches the output: the command, clipped as the motor clips it,
    scaled by what it really delivers, then held to the torque-speed line."""
    asked = np.clip(mit(table, p, v), -motor.peak, motor.peak)
    return saturate(motor.scale * asked, v, motor.peak * motor.scale, motor.no_load)


def friction(motor: Motor, v):
    return motor.coulomb * np.tanh(v / STICTION_RAD_S) + motor.viscous * v


def simulate(motor: Motor, cmd_t, cmd_table, starts, p0, v0, length, dt=2e-4):
    """Every window at once: W windows of `length` seconds from `starts`, each
    from its own (p0, v0), under the commands in force at each instant less the
    motor's delay. Returns the step times from each start and W x S arrays of
    position and speed."""
    starts = np.asarray(starts, dtype=float)
    p = np.array(p0, dtype=float)
    v = np.array(v0, dtype=float)
    steps = int(round(length / dt))
    ps = np.empty((len(starts), steps + 1))
    vs = np.empty_like(ps)
    ps[:, 0], vs[:, 0] = p, v
    for s in range(steps):
        now = starts + s * dt - motor.delay
        k = np.clip(np.searchsorted(cmd_t, now, side="right") - 1, 0, None)
        tau = delivered(motor, cmd_table[k], p, v)
        tau = np.where(np.searchsorted(cmd_t, now, side="right") > 0, tau, 0.0)
        v = v + dt * (tau - friction(motor, v)) / motor.inertia
        p = p + dt * v
        ps[:, s + 1], vs[:, s + 1] = p, v
    return np.arange(steps + 1) * dt, ps, vs
