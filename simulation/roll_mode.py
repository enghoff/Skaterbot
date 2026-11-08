"""The robot's roll answer to its own knees, as a mode its sensors see.

EVERY JUMP ON THE ROBOT FAILED AND EVERY ONE IN MUJOCO PASSED: eleven jumps on 6 and 7
November 2026, by three jump policies, against none failing in simulation (session
scratchpad jumpwhy/, 7 November 2026). On the robot a fast change in the knees' target
difference, right minus left in the joints' frame, rolls the torso about 10 rad/s per
rad (5 to 14 across the jumps), fitted as a 25 Hz second-order mode with damping 0.3,
about 15 ms after the command is sent; MuJoCo's rigid robot answers 0.23, forty times
weaker. The jump policy answers roll rate with a knee difference some 10 ms later, with
the sign that around that 25 ms round trip makes positive feedback at 20-25 Hz: its knee
targets chatter 0.27-0.46 rad a step, the push-off is cut short, and it tips over
backwards about 0.7 s after the trigger. Closed in MuJoCo through the sensors as below,
the loop at 10.8 tips jl_lag over behind D3 two times in two and behind D8 once in three,
the other two chattering 0.28-0.31 rad a step with the roll rate seen at 2.2-2.5 rad/s
rms (simulation/mujoco/jump_roll_check.py); at half the gain it is quiet. So the robot sits just past instability. What flexes is
probably the printed legs, which splay into an A under load standing (a rubber band has
held the shins together since 6 November); that it is them is not proven.

THE FORM, from that investigation's simj.py, and the same in MuJoCo and Isaac Lab:

    roll rate = K s w^2 / (s^2 + 2 zeta w s + w^2) x (knee target R - L, sent `delay` ago)

with w = 2 pi hz, and the gain given as GAIN, the rate's answer AT ITS NATURAL FREQUENCY
in rad/s per rad, which is what the robot's jumps measured: |H(j w)| = K w / (2 zeta), so
K = GAIN 2 zeta / w is the roll angle per rad of knee difference held (0.041 at the
robot's fit). A rate's answer at zero frequency is nothing; a "DC gain" of 5-15 rad/s per
rad can only mean this one. The angle is the rate's integral and leans the gravity the
IMU reports about the torso's own x (forward, so positive is the right side down); the
rate is added to the gyro's x. The simulated body does not roll: it is the sensors'
mode, which is all the loop through the policy needs and what keeps it identical in
both simulators.

THE STEP. simj.py integrated it with semi-implicit Euler at MuJoCo's 0.5 ms. Here it is
the exact solution over a step with the input held (`coefficients`, `advance`), so it
is the same mode at Isaac Lab's 2.5 ms physics step as at MuJoCo's 0.5 ms: on the same
knee targets the two agree to float precision. simj.py's own steps answered 20-30 Hz
within 2 % of the same gain and about 7 degrees, 0.75 ms, ahead in phase, from taking
its input at each step's end and from Euler's lead (tools/test_roll_mode.py measures
all of it); against a delay drawn 5 ms either way in training, that is nothing. The
plain functions here are arithmetic on whatever they are given, floats, numpy arrays
or torch tensors, with `xp` the module whose sqrt, exp, sin and cos to use.
"""

from __future__ import annotations

import math

# The robot's mode as fitted from its jumps (above): the gate in
# simulation/mujoco/jump_roll_check.py runs at these.
FITTED = {
    "gain_rad_s_per_rad": 10.8,
    "hz": 25.0,
    "zeta": 0.3,
    "delay_s": 0.015,
}

# What training draws, per robot per episode, evenly: the gain over the 5-14 the jumps
# spread across and a little past, so that a policy which is quiet at 10.8 has margin;
# the frequency and damping a third either way of the fit, which three parameters fitted
# to eleven noisy jumps cannot claim better than; and the delay 5 ms either side.
DRAWN = {
    "gain_rad_s_per_rad": (5.0, 15.0),
    "hz": (20.0, 30.0),
    "zeta": (0.2, 0.4),
    "delay_s": (0.010, 0.020),
}


def angle_gain(gain, hz, zeta):
    """Roll angle per radian of knee difference held: GAIN x 2 zeta / w."""
    return gain * 2.0 * zeta / (2.0 * math.pi * hz)


def delay_steps(delay_s: tuple[float, float], dt: float) -> tuple[int, int]:
    """A range of delays in seconds as whole steps of dt."""
    return tuple(int(round(s / dt)) for s in delay_s)


def coefficients(gain, hz, zeta, dt: float, xp=math):
    """The mode's exact step over dt with its input held, as (K, f11, f12, f21, f22).

    The state is the angle and the rate; off its resting angle K u, it decays as the
    homogeneous system does, whose transition matrix over dt is [[f11, f12], [f21, f22]].
    For damping under 1, which every draw here is.
    """
    w = 2.0 * math.pi * hz
    wd = w * xp.sqrt(1.0 - zeta * zeta)
    sigma = zeta * w
    decay = xp.exp(-sigma * dt)
    c, s = xp.cos(wd * dt), xp.sin(wd * dt)
    return (
        gain * 2.0 * zeta / w,
        decay * (c + sigma / wd * s),
        decay * s / wd,
        -w * w * decay * s / wd,
        decay * (c - sigma / wd * s),
    )


def advance(angle, rate, u, coef):
    """The angle and rate one step on, with u the knee difference (rad) held over it."""
    k, f11, f12, f21, f22 = coef
    off = angle - k * u
    return k * u + f11 * off + f12 * rate, f21 * off + f22 * rate


def turn_gravity(gy, gz, angle, xp=math):
    """The y and z of a gravity reading in the torso's frame, the torso rolled by angle
    about its x: R_x(angle)^T g, which is simj.py's [[1, 0, 0], [0, c, s], [0, -s, c]]."""
    c, s = xp.cos(angle), xp.sin(angle)
    return c * gy + s * gz, -s * gy + c * gz


class Robots:
    """The mode for many robots at once on torch tensors, as Isaac Lab's jump task steps
    it (wheeled_biped_task/jump_env.py), each robot with its own gain, frequency,
    damping and delay. Stepped once a physics step, before the step: the knee difference
    commanded now goes in, and the mode moves across the step on what was commanded
    `delay` steps before, so the delay is that many steps exactly, as in
    simulation/mujoco/jump_roll_check.py. torch is imported here and not above, so the
    MuJoCo side needs none."""

    def __init__(self, n: int, dt: float, longest_delay_steps: int, device="cpu"):
        import torch

        self.torch, self.dt = torch, dt
        # The knee difference commanded, newest first, back to the longest delay.
        self.u = torch.zeros(n, longest_delay_steps + 1, device=device)
        self.delay = torch.zeros(n, 1, dtype=torch.long, device=device)
        self.angle = torch.zeros(n, device=device)
        self.rate = torch.zeros(n, device=device)
        self.coef = torch.zeros(5, n, device=device)

    def reset(self, ids, gain, hz, zeta, delay_steps, u) -> None:
        """Robots `ids` at rest with these parameters, their knees long at difference u."""
        t = self.torch
        self.coef[:, ids] = t.stack(coefficients(gain, hz, zeta, self.dt, t))
        self.delay[ids] = delay_steps.unsqueeze(1)
        self.angle[ids] = 0.0
        self.rate[ids] = 0.0
        self.u[ids] = u.unsqueeze(1)

    def step(self, u) -> None:
        """One physics step on, u the knee difference commanded now (rad)."""
        self.u = self.torch.roll(self.u, 1, 1)
        self.u[:, 0] = u
        held = self.u.gather(1, self.delay).squeeze(1)
        self.angle, self.rate = advance(
            self.angle, self.rate, held, self.coef.unbind(0)
        )
