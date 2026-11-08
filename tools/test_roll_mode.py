# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy>=1.26", "torch>=2.4"]
# ///
"""The robot's roll mode, as both simulators take it, held to its definition and to
the investigation's own code.

    uv run tools/test_roll_mode.py

simulation/roll_mode.py is the mode the jump task trains against in Isaac Lab
(`Robots`, torch, a 2.5 ms physics step, the delay in whole steps) and the jump gate
runs in MuJoCo (simulation/mujoco/jump_roll_check.py: `coefficients` and `advance` on
floats at 0.5 ms, the delay in seconds). The session's simj.py, which found the loop on
7 November 2026, integrated it with semi-implicit Euler instead. This checks:

1. the step answer against the closed form, at both steps;
2. the rate's answer to a sine against |H|, which peaks at the natural frequency at
   exactly the gain asked (simj.py's definition of its GAIN);
3. the ring-down's frequency, w sqrt(1 - zeta^2);
4. Isaac Lab's form against the MuJoCo gate's on the same knee targets, robot by
   robot with their own parameters: the same answer;
5. both against simj.py's own lines on the same knee targets: the same answer to
   within what Euler and its half-millisecond input timing cost, stated;
6. the gravity turned in the torso's frame, against simj.py turning it through the
   chip's axes.

Free, offline, a few seconds.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "simulation"))

import roll_mode  # noqa: E402

FIT = roll_mode.FITTED
GAIN, HZ, ZETA, DELAY = (
    FIT["gain_rad_s_per_rad"],
    FIT["hz"],
    FIT["zeta"],
    FIT["delay_s"],
)
ISAAC_DT = 0.0025  # plant.PHYSICS_DT
MUJOCO_DT = 0.0005  # launch_check.run's timestep
POLICY_DT = 0.01

failures: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    print(f"   {'ok' if ok else 'FAILED'}: {name}: {detail}", flush=True)
    if not ok:
        failures.append(name)


def knee_targets(seconds: float, seed: int) -> np.ndarray:
    """A knee target difference a policy step, as a jump policy sends it: a slow wander
    and a 22 Hz chatter of 0.15 rad, with a jump's asymmetry kicked in now and then."""
    rng = np.random.default_rng(seed)
    n = int(round(seconds / POLICY_DT))
    t = np.arange(n) * POLICY_DT
    slow = np.cumsum(rng.normal(0.0, 0.01, n))
    chatter = 0.15 * np.sin(2 * math.pi * 22.0 * t + rng.uniform(0, 2 * math.pi))
    kicks = np.where(rng.random(n) < 0.03, rng.normal(0.0, 0.3, n), 0.0)
    return slow + chatter + kicks


def sent_at(u, t: float) -> float:
    """The knee difference as it stood at t: the last policy step's at or before, or u(t)
    where u is a function of time."""
    if callable(u):
        return float(u(t))
    i = math.floor(t / POLICY_DT + 1e-9)
    return float(u[i]) if i >= 0 else 0.0


def gate_form(u, gain, hz, zeta, delay_s, dt, seconds):
    """simulation/mujoco/jump_roll_check.py's Rig._physics: exact, the input held from
    what stood `delay_s` before the step's start. (time at the step's end, angle, rate)."""
    coef = roll_mode.coefficients(gain, hz, zeta, dt)
    angle = rate = 0.0
    out = []
    for i in range(int(round(seconds / dt))):
        held = sent_at(u, i * dt - delay_s)
        angle, rate = roll_mode.advance(angle, rate, held, coef)
        out.append(((i + 1) * dt, angle, rate))
    return np.array(out)


def simj_form(u, gain, hz, zeta, delay_s, dt, seconds):
    """simj.py's Rig._physics, its lines as they ran (session scratchpad jumpwhy/,
    7 November 2026): super()._physics(dt) moves the clock on first, then semi-implicit
    Euler with the input from `delay` before the step's END."""
    ry = ryd = 0.0
    out = []
    for i in range(int(round(seconds / dt))):
        t = (i + 1) * dt
        w = 2 * math.pi * hz
        k = gain / (w * (1.0 / (2 * zeta)))  # |s * w^2/(...)| at w is w/(2 zeta)
        uu = sent_at(u, t - delay_s)
        ydd = w * w * (k * uu - ry) - 2 * zeta * w * ryd
        ryd += ydd * dt
        ry += ryd * dt
        out.append((t, ry, ryd))
    return np.array(out)


def isaac_form(u, params, seconds):
    """roll_mode.Robots as wheeled_biped_task/jump_env.py drives it: reset, then each
    physics step the policy step's knee difference in. Rows per robot: (time, angle,
    rate) at each physics step's end."""
    gain, hz, zeta, delay_s = (torch.tensor(c, dtype=torch.float) for c in zip(*params))
    steps = torch.round(delay_s / ISAAC_DT).long()
    robots = roll_mode.Robots(len(params), ISAAC_DT, int(steps.max()))
    ids = torch.arange(len(params))
    robots.reset(ids, gain, hz, zeta, steps, torch.zeros(len(params)))
    rows = []
    per = int(round(POLICY_DT / ISAAC_DT))
    for i in range(int(round(seconds / ISAAC_DT))):
        robots.step(torch.full((len(params),), float(u[i // per])))
        rows.append(
            np.stack(
                (
                    np.full(len(params), (i + 1) * ISAAC_DT),
                    robots.angle.numpy(),
                    robots.rate.numpy(),
                ),
                axis=1,
            )
        )
    return np.stack(rows, axis=1)  # (robot, step, 3)


def main() -> int:
    k = roll_mode.angle_gain(GAIN, HZ, ZETA)
    w = 2 * math.pi * HZ
    wd = w * math.sqrt(1 - ZETA**2)
    sigma = ZETA * w
    print(
        f"the robot's fit: {GAIN:g} rad/s per rad at {HZ:g} Hz, damping {ZETA:g}, "
        f"{DELAY * 1000:g} ms late; {k:.4f} rad of roll per rad of knee difference held"
    )

    print("1. the answer to a step of 1 rad, against the closed form")
    for dt in (ISAAC_DT, MUJOCO_DT):
        u = np.ones(100)
        got = gate_form(u, GAIN, HZ, ZETA, 0.0, dt, 0.5)
        t = got[:, 0]
        decay = np.exp(-sigma * t)
        angle = k * (1 - decay * (np.cos(wd * t) + sigma / wd * np.sin(wd * t)))
        rate = k * w * w / wd * decay * np.sin(wd * t)
        err = max(np.abs(got[:, 1] - angle).max(), np.abs(got[:, 2] - rate).max())
        check(
            f"at {dt * 1000:g} ms",
            err < 1e-9 and abs(got[-1, 1] - k) < 1e-6,
            f"off by {err:.1e} at most; rate peaks at {rate.max():.2f} rad/s, "
            f"angle settles at {got[-1, 1]:.4f}",
        )

    print("2. the rate's answer to a sine of knee difference, against |H|")
    dt = 2e-5
    coef = roll_mode.coefficients(GAIN, HZ, ZETA, dt)
    answers = {}
    for share in (0.5, 0.8, 1.0, 1.25, 2.0):
        f = share * HZ
        angle = rate = 0.0
        n = int(round(1.0 / dt))
        peak = 0.0
        for i in range(n):
            # Held at the step's middle: a held input lags the sine by half a step.
            angle, rate = roll_mode.advance(
                angle, rate, math.sin(2 * math.pi * f * (i + 0.5) * dt), coef
            )
            if i > n * 0.6:
                peak = max(peak, abs(rate))
        om = 2 * math.pi * f
        want = k * w * w * om / math.hypot(w * w - om * om, 2 * ZETA * w * om)
        answers[share] = peak
        check(
            f"at {f:g} Hz",
            abs(peak / want - 1) < 0.002,
            f"{peak:.3f} rad/s per rad, |H| {want:.3f}",
        )
    check(
        "the most at the natural frequency, and that the gain",
        max(answers, key=answers.get) == 1.0 and abs(answers[1.0] / GAIN - 1) < 0.002,
        f"{answers[1.0]:.3f} against {GAIN:g}",
    )

    print("3. the ring-down's frequency")
    for dt in (ISAAC_DT, MUJOCO_DT):
        coef = roll_mode.coefficients(GAIN, HZ, ZETA, dt)
        angle, rate = 0.0, 1.0
        rates = []
        for _ in range(int(round(0.2 / dt))):
            angle, rate = roll_mode.advance(angle, rate, 0.0, coef)
            rates.append(rate)
        r = np.array(rates)
        down = np.where((r[:-1] > 0) & (r[1:] <= 0))[0]
        # Each crossing to the step's fraction, by straight-line interpolation.
        at = (down + r[down] / (r[down] - r[down + 1]) + 1) * dt
        hz = 1.0 / np.mean(np.diff(at))
        want = wd / (2 * math.pi)
        check(
            f"at {dt * 1000:g} ms",
            abs(hz / want - 1) < 0.003,
            f"{hz:.3f} Hz, w sqrt(1 - zeta^2) / 2 pi {want:.3f}",
        )

    print("4. Isaac Lab's form against the MuJoCo gate's, on the same knee targets")
    lo = {key: span[0] for key, span in roll_mode.DRAWN.items()}
    hi = {key: span[1] for key, span in roll_mode.DRAWN.items()}
    order = ("gain_rad_s_per_rad", "hz", "zeta", "delay_s")
    params = [tuple(p[key] for key in order) for p in (FIT, lo, hi)]
    u = knee_targets(3.0, seed=1)
    isaac = isaac_form(u, params, 3.0)
    per = int(round(ISAAC_DT / MUJOCO_DT))
    for (name, p), rows in zip(zip(("fit", "lowest", "highest"), params), isaac):
        gate = gate_form(u, *p, MUJOCO_DT, 3.0)[per - 1 :: per]
        scale = np.sqrt(np.mean(gate[:, 2] ** 2))
        err = np.abs(rows[:, 2] - gate[:, 2]).max()
        check(
            f"{name}: {p[0]:g} rad/s per rad, {p[1]:g} Hz, damping {p[2]:g}, "
            f"{p[3] * 1000:g} ms",
            err < 1e-4 * max(scale, 1.0) and np.allclose(rows[:, 0], gate[:, 0]),
            f"rates {scale:.2f} rad/s rms, off by {err:.1e} at most (float32)",
        )

    print("5. both against simj.py's own lines, answering a sine of knee difference")
    # The rate's phasor over the last half of 1.2 s, against the continuous mode's,
    # H(j w) e^(-j w delay). The gate holds its input from each step's start, which lags
    # a smooth input by half a step (a jump policy's targets, held a policy step each,
    # it takes exactly); simj.py took its input at the step's end, half a step early, and
    # its Euler step leads a further 2 degrees or so. Between them simj.py's loop runs
    # about 7 degrees ahead of the gate's at 25 Hz, three quarters of a millisecond.
    for f in (20.0, 25.0, 30.0):
        om = 2 * math.pi * f
        want = k * w * w * 1j * om / (w * w - om * om + 2j * ZETA * w * om)
        want *= np.exp(-1j * om * DELAY)
        got = {}
        for name, form in (("gate", gate_form), ("simj", simj_form)):
            rows = form(
                lambda t: math.sin(om * t), GAIN, HZ, ZETA, DELAY, MUJOCO_DT, 1.2
            )
            m = rows[:, 0] > 0.6
            a = np.stack((np.sin(om * rows[m, 0]), np.cos(om * rows[m, 0])), axis=1)
            s, c = np.linalg.lstsq(a, rows[m, 2], rcond=None)[0]
            h = complex(s, c) / want
            got[name] = (abs(h), math.degrees(np.angle(h)))
        half = -math.degrees(om * MUJOCO_DT / 2)
        (gg, gp), (sg, sp) = got["gate"], got["simj"]
        check(
            f"at {f:g} Hz",
            abs(gg - 1) < 0.002
            and abs(gp - half) < 0.3
            and abs(sg - 1) < 0.03
            and abs(sp) < 6.0,
            f"the gate {gg:.3f} of |H| and {gp:+.1f} degrees (half its step "
            f"{half:+.1f}), simj.py {sg:.3f} and {sp:+.1f}",
        )

    print("6. the gravity turned, in the torso's frame and through the chip's axes")
    rng = np.random.default_rng(3)
    axes, _ = np.linalg.qr(rng.normal(size=(3, 3)))  # any chip mounting
    to_chip, sign = np.linalg.inv(axes), -1.0
    worst = 0.0
    for _ in range(50):
        g = rng.normal(size=3)
        angle = rng.uniform(-0.3, 0.3)
        c, s = math.cos(angle), math.sin(angle)
        rx = np.array([[1, 0, 0], [0, c, s], [0, -s, c]])
        chip = sign * (to_chip @ g)
        theirs = sign * (to_chip @ (rx @ (axes @ (chip * sign))))  # simj.py's _chip
        ours = g.copy()
        ours[1], ours[2] = roll_mode.turn_gravity(g[1], g[2], angle)
        worst = max(worst, np.abs(axes @ (theirs * sign) - ours).max())
    check("50 readings", worst < 1e-12, f"off by {worst:.1e} at most")

    print("passed" if not failures else f"FAILED: {', '.join(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
