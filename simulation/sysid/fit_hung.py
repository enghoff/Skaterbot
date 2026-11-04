# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy>=1.26", "scipy>=1.11", "mujoco>=3.2", "matplotlib>=3.8",
#                 "trimesh>=4.0", "build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1"]
# ///
"""Fit stage B of docs/SYSID.md: the whole robot hanging from the rail.

    uv run simulation/sysid/fit_hung.py LOG [--bench fit_bench.json] [--out DIR]

Replays the log through simulation/sysid/rig.py's hanging robot, in windows of
a little over half a second, each from the state the motors and the IMU
measured at its start and under the commands logged for it, and fits the
joints' armature, friction and damping and the motors' torque scale to make the
model's joints move as the robot's did. The legs hang under gravity, which is
a torque the CAD already knows, so the torque scale can be fitted here without
a scale; the wheels are only fitted when the log drove them.

Then, with those fixed, it fits how late the IMU reads and the rail's own
damping, from the torso's measured pitch rate. A B3 log's free swing is set
against the model's, which checks the mass and its distribution in one number.

--bench takes stage A's results: the delay from command to torque, which this
then holds rather than searches for, and the torque-speed line.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import logfile  # noqa: E402
import rig  # noqa: E402
import sysid_tests as st  # noqa: E402

JOINTS = st.JOINTS
WINDOW_S = 0.6
STEP_S = 0.3
MOST_WINDOWS = 60
DT = 1e-3
SIGMA = {"p": 0.01, "v": 0.3, "gyro": 0.05}
DELAYS_MS = (0.0, 1.0, 2.0, 4.0)
IMU_DELAYS_MS = np.arange(0.0, 20.5, 0.5)
HINGE_DAMPINGS = (0.0, 0.001, 0.003, 0.01, 0.03, 0.1)
# Which joints each test moves enough to fit.
EXCITED = {"B1": ("legs",), "B3": (), "B4": ("legs",), "B2": ("wheels",)}
# What the policies were trained to tolerate on every scaled sensor reading
# (simulation/isaaclab's sensor_noise_std and sensor_bias_std, 0.02 each), in
# each reading's own units: the scale is docs/POLICY_INTERFACE.md's.
TRAINED_NOISE = {
    "gyro": 0.02 / 0.25,
    "gravity": 0.02,
    "angle": 0.02,
    "speed": 0.02 / 0.05,
}
# The torso's typical pitch rate in a window, rad/s, below which the IMU's lag
# has nothing to be measured against.
PITCHED = 0.05
BOUNDS = {
    "leg_armature": (1e-5, 5e-3),
    "leg_friction": (0.0, 0.5),
    "leg_damping": (0.0, 0.1),
    "wheel_armature": (1e-5, 5e-3),
    "wheel_friction": (0.0, 0.5),
    "wheel_damping": (0.0, 0.05),
    "scale": (0.5, 1.5),
    "hinge_damping": (0.0, 0.2),
}


def local_speed(t, x, at):
    """A line through the five samples nearest `at`: its value there."""
    k = np.argsort(np.abs(t - at))[:5]
    if np.ptp(t[k]) == 0:
        return float(x[k].mean())
    return float(np.polyfit(t[k] - at, x[k], 1)[1])


class Replay:
    def __init__(self, log: logfile.Log, rng, params: dict, fixed: bool = False):
        self.log = log
        gravity = log.imu.get("gravity")
        gyro = log.imu.get("gyro")
        self.hinge = (
            not fixed and bool(log.header.get("imu_axes")) and gravity is not None
        )
        if fixed:
            print("  the torso was held fixed: no hinge")
        elif not self.hinge:
            print(
                "  no IMU axes in the header, or no gravity report: the torso is "
                "held fixed, which a hanging robot is not. Run `map` first."
            )
        self.sim = rig.Hung(params, hinge=self.hinge, dt=DT)
        self.commanded = [j for j in JOINTS if j in log.commands]
        self.tracked = [j for j in JOINTS if j in log.tracks]
        t_lo = max(log.commands[j].t[0] for j in self.commanded)
        t_hi = min(log.commands[j].t[-1] for j in self.commanded)
        starts = []
        for name, t0, t1 in log.segments():
            if name.startswith("let down"):
                continue
            t0, t1 = max(t0, t_lo), min(t1, t_hi)
            starts.extend(np.arange(t0 + 0.05, t1 - WINDOW_S, STEP_S))
        starts = np.array(sorted(starts))
        if len(starts) > MOST_WINDOWS:
            starts = np.sort(rng.choice(starts, MOST_WINDOWS, replace=False))
        self.starts = starts
        self.steps = int(round(WINDOW_S / DT))
        self.grid = np.arange(self.steps + 1) * DT

        self.q0 = np.zeros((len(starts), len(JOINTS)))
        self.v0 = np.zeros_like(self.q0)
        for i, j in enumerate(JOINTS):
            tr = log.tracks.get(j)
            if tr is None:
                continue
            self.q0[:, i] = np.interp(starts, tr.t, tr.p)
            self.v0[:, i] = [local_speed(tr.t, tr.v, t) for t in starts]
        self.pitch0 = np.zeros(len(starts))
        self.rate0 = np.zeros(len(starts))
        if self.hinge:
            gt, gv = gravity
            for w, t in enumerate(starts):
                g = np.array([np.interp(t, gt, gv[:, k]) for k in range(3)])
                self.pitch0[w] = rig.pitch_from_gravity(g)
            if gyro is not None:
                self.rate0 = np.array(
                    [local_speed(gyro[0], gyro[1][:, 1], t) for t in starts]
                )
        self.gyro = gyro

        self.samples = []
        for t0 in starts:
            per = {}
            for j in self.tracked:
                tr = log.tracks[j]
                k = (tr.t > t0) & (tr.t <= t0 + WINDOW_S)
                per[j] = (tr.t[k] - t0, tr.p[k], tr.v[k])
            if gyro is not None and self.hinge:
                k = (gyro[0] > t0) & (gyro[0] <= t0 + WINDOW_S)
                per["gyro"] = (gyro[0][k] - t0, gyro[1][k, 1])
            self.samples.append(per)
        self._tables = {}

    def tables(self, delay: float) -> np.ndarray:
        """W x S x 6 x 5: the command in force at every step, less the delay."""
        key = round(delay, 6)
        if key not in self._tables:
            out = np.zeros((len(self.starts), self.steps, len(JOINTS), 5))
            times = self.starts[:, None] + self.grid[None, :-1] - delay
            for i, j in enumerate(JOINTS):
                c = self.log.commands.get(j)
                if c is None:
                    continue
                k = np.searchsorted(c.t, times, side="right") - 1
                out[:, :, i, :] = c.table()[np.clip(k, 0, None)]
                out[:, :, i, :] *= (k >= 0)[..., None]
            self._tables = {key: out}
        return self._tables[key]

    def run(self, params: dict):
        """Every window: W x (S+1) x 6 positions and speeds, and W x (S+1) pitch rates."""
        self.sim.set_params(params)
        tables = self.tables(self.sim.p["delay"])
        W, S = len(self.starts), self.steps
        q = np.zeros((W, S + 1, len(JOINTS)))
        v = np.zeros_like(q)
        rate = np.zeros((W, S + 1))
        for w in range(W):
            self.sim.place(self.q0[w], self.v0[w], self.pitch0[w], self.rate0[w])
            q[w, 0], v[w, 0] = self.sim.joints()
            rate[w, 0] = self.sim.pitch()[1]
            for s in range(S):
                self.sim.step(tables[w, s])
                q[w, s + 1], v[w, s + 1] = self.sim.joints()
                rate[w, s + 1] = self.sim.pitch()[1]
        return q, v, rate

    def joint_residuals(self, q, v) -> np.ndarray:
        out = []
        for w, per in enumerate(self.samples):
            for i, j in enumerate(JOINTS):
                if j not in per:
                    continue
                dt, p, vel = per[j]
                if j in st.LEGS:
                    out.append((np.interp(dt, self.grid, q[w, :, i]) - p) / SIGMA["p"])
                out.append((np.interp(dt, self.grid, v[w, :, i]) - vel) / SIGMA["v"])
        return np.concatenate(out) if out else np.zeros(0)

    def gyro_fit(self, params: dict, delays) -> dict[float, np.ndarray]:
        """The torso's pitch-rate error at each IMU lag in `delays`.

        A window's starting pitch rate cannot be read off the gyro: the gyro
        reads late, and the windows that matter start in the middle of a jerk.
        So each window's start is solved for. The swing's answer to its own
        starting pitch and rate is near enough linear, so the model is run three
        times -- as measured, and nudged in each -- and the two corrections that
        fit best are found by least squares, window by window, at every lag."""
        base = self.run(params)[2]
        nudge = 1e-3
        keep_p, keep_r = self.pitch0.copy(), self.rate0.copy()
        self.pitch0 = keep_p + nudge
        by_pitch = (self.run(params)[2] - base) / nudge
        self.pitch0, self.rate0 = keep_p, keep_r + nudge
        by_rate = (self.run(params)[2] - base) / nudge
        self.rate0 = keep_r
        out = {}
        for delay in delays:
            res = []
            for w, per in enumerate(self.samples):
                if "gyro" not in per:
                    continue
                dt, g = per["gyro"]
                s = dt[dt >= delay] - delay
                g = g[dt >= delay]
                a = np.column_stack(
                    (
                        np.interp(s, self.grid, by_pitch[w]),
                        np.interp(s, self.grid, by_rate[w]),
                    )
                )
                b = g - np.interp(s, self.grid, base[w])
                x, *_ = np.linalg.lstsq(a, b, rcond=None)
                res.append((b - a @ x) / SIGMA["gyro"])
            out[delay] = np.concatenate(res) if res else np.zeros(0)
        return out


def rms_by_group(replay, q, v):
    """Root-mean-square position and speed error per joint group."""
    errs = {}
    for w, per in enumerate(replay.samples):
        for i, j in enumerate(JOINTS):
            if j not in per:
                continue
            dt, p, vel = per[j]
            group = "wheels" if j in st.WHEELS else "legs"
            e = errs.setdefault(group, [[], []])
            # A wheel's angle means nothing, and wraps round besides.
            if group == "legs":
                e[0].append(np.interp(dt, replay.grid, q[w, :, i]) - p)
            e[1].append(np.interp(dt, replay.grid, v[w, :, i]) - vel)
    return {
        g: (
            float(np.sqrt(np.mean(np.concatenate(a) ** 2))) if a else float("nan"),
            float(np.sqrt(np.mean(np.concatenate(b) ** 2))),
        )
        for g, (a, b) in errs.items()
    }


def swing_period(t, rate) -> float:
    """Twice the median time between the pitch rate's zero crossings."""
    s = np.sign(rate - np.mean(rate))
    cross = t[np.nonzero(np.diff(s) != 0)[0]]
    return float(2.0 * np.median(np.diff(cross))) if len(cross) >= 4 else float("nan")


def swing(log, replay: Replay, params_list):
    """B3's free swing: its period on the robot and in the model."""
    segs = [s for s in log.segments() if s[0] == "swing"]
    if not segs or replay.gyro is None or not replay.hinge:
        return None
    _, t0, t1 = segs[0]
    gt, gv = replay.gyro
    k = (gt >= t0) & (gt <= t1)
    tt, rate = gt[k], gv[k, 1]
    if len(tt) < 50:
        return None
    start = tt[np.argmax(np.abs(rate))] + 0.5
    span = min(8.0, t1 - start)
    k = (tt >= start) & (tt <= start + span)
    measured = swing_period(tt[k], rate[k])
    out = {"measured_s": measured}
    gravity = log.imu["gravity"]
    g = np.array([np.interp(start, gravity[0], gravity[1][:, c]) for c in range(3)])
    q0 = np.array(
        [
            np.interp(start, log.tracks[j].t, log.tracks[j].p)
            if j in log.tracks
            else 0.0
            for j in JOINTS
        ]
    )
    for name, params in params_list:
        sim = rig.Hung(params, hinge=True, dt=DT)
        sim.place(
            q0,
            np.zeros(len(JOINTS)),
            rig.pitch_from_gravity(g),
            np.interp(start, tt, rate),
        )
        n = int(span / DT)
        rates = np.zeros(n)
        times = start + np.arange(n) * DT
        tables = np.zeros((len(JOINTS), 5))
        for s in range(n):
            for i, j in enumerate(JOINTS):
                c = log.commands.get(j)
                if c is not None:
                    idx = max(0, int(np.searchsorted(c.t, times[s], side="right")) - 1)
                    tables[i] = c.table()[idx]
            sim.step(tables)
            rates[s] = sim.pitch()[1]
        out[f"{name}_s"] = swing_period(times, rates)
    return out


def stillness(log) -> dict | None:
    """B3's still minute: how far each reading wanders, and where the gyro
    reads when nothing turns -- set against what training already covers."""
    segs = [s for s in log.segments() if s[0] == "still"]
    if not segs:
        return None
    _, t0, t1 = segs[0]
    t0 += 1.0  # the legs settling on their gains
    out = {"joints": {}, "trained": TRAINED_NOISE}
    for j, tr in log.tracks.items():
        k = (tr.t > t0) & (tr.t < t1)
        if k.sum() > 20:
            out["joints"][j] = {
                "angle": float(np.std(tr.p[k])),
                "speed": float(np.std(tr.v[k])),
            }
    if "gyro" in log.imu:
        t, v = log.imu["gyro"]
        k = (t > t0) & (t < t1)
        out["gyro_bias"] = v[k].mean(axis=0).tolist()
        out["gyro_noise"] = v[k].std(axis=0).tolist()
    if "gravity" in log.imu:
        t, v = log.imu["gravity"]
        k = (t > t0) & (t < t1)
        u = v[k] / np.linalg.norm(v[k], axis=1, keepdims=True)
        out["gravity_noise"] = u.std(axis=0).tolist()
        # Hanging, the torso is not level: this is the hang plus any error in
        # the IMU's seat, and only standing level separates the two.
        out["hang_pitch_deg"] = float(
            np.degrees(rig.pitch_from_gravity(u.mean(axis=0)))
        )
    tn = TRAINED_NOISE
    print(f"\n{log.test}  held still for {t1 - t0:.0f} s: the noise on each reading")
    print(f"    {'':<20} {'measured':>10} {'trained to':>10}")
    if "gyro_noise" in out:
        print(
            f"    {'gyro, rad/s':<20} {max(out['gyro_noise']):10.4f} {tn['gyro']:10.4f}"
        )
        print(
            f"    {'gyro bias, rad/s':<20} {max(np.abs(out['gyro_bias'])):10.4f} {tn['gyro']:10.4f}"
        )
    if "gravity_noise" in out:
        print(
            f"    {'gravity, unit':<20} {max(out['gravity_noise']):10.4f} {tn['gravity']:10.4f}"
        )
    if out["joints"]:
        angle = max(x["angle"] for x in out["joints"].values())
        speed = max(x["speed"] for x in out["joints"].values())
        print(f"    {'leg angle, rad':<20} {angle:10.4f} {tn['angle']:10.4f}")
        print(f"    {'leg speed, rad/s':<20} {speed:10.4f} {tn['speed']:10.4f}")
    if "hang_pitch_deg" in out:
        print(
            f"    hanging {out['hang_pitch_deg']:+.1f} degrees nose-down, IMU seat included"
        )
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("log", type=Path)
    ap.add_argument("--bench", type=Path, help="fit_bench.json from stage A")
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--fit",
        help="legs, wheels or both: whose figures to fit, over what the test excites",
    )
    ap.add_argument(
        "--scale",
        type=float,
        help="torque delivered / commanded, from A1 or a B1 fit, for a test without legs",
    )
    ap.add_argument("--no-plots", action="store_true")
    ap.add_argument(
        "--fixed-torso",
        action="store_true",
        help="the torso was held still (strung in a V), so no hinge",
    )
    args = ap.parse_args(argv)

    log = logfile.load(args.log)
    print(logfile.describe(log))
    base = dict(rig.NOMINAL)
    delays = DELAYS_MS
    scale_from = None
    if args.bench:
        bench = json.loads(args.bench.read_text(encoding="utf-8"))
        motor = bench.get("motor") or {}
        if motor.get("delay") is not None:
            delays = (motor["delay"] * 1000.0,)
        if motor.get("scale") is not None and "ASSUMED" not in (
            bench.get("scale_source") or ""
        ):
            base["scale"], scale_from = motor["scale"], "the bench"
        for r in (bench.get("torque_speed") or {}).values():
            if np.isfinite(r.get("no_load_rad_s", np.nan)):
                base["no_load"] = r["no_load_rad_s"]
        print(
            f"  from the bench: delay {delays[0]:.2f} ms, no-load {base['no_load']:.1f} rad/s"
        )
    if args.scale is not None:
        base["scale"], scale_from = args.scale, "--scale"

    rng = np.random.default_rng(0)
    replay = Replay(log, rng, base, fixed=args.fixed_torso)
    # Only what the test moves. B2 holds the legs still while the wheels spin,
    # and a fit of the legs' figures from that wanders to wherever its bounds
    # are, so they keep the simulator's.
    groups = (
        args.fit.split(",") if args.fit else EXCITED.get(log.test, ("legs", "wheels"))
    )
    names = []
    if "legs" in groups and any(j in st.LEGS for j in replay.commanded):
        names += ["leg_armature", "leg_friction", "leg_damping"]
    if "wheels" in groups and any(j in st.WHEELS for j in replay.commanded):
        names += ["wheel_armature", "wheel_friction", "wheel_damping"]
    # The torque scale only separates from the inertia where a torque is known
    # for it to be measured against, which is gravity on the legs. A wheel in the
    # air shows only their ratio, so without the legs it is held, at the
    # bench's figure if there is one.
    if "leg_armature" in names:
        names.append("scale")
    elif names:
        print(
            f"  the torque scale is held at {base['scale']:.3f}, "
            f"{'from ' + scale_from if scale_from else 'NOT MEASURED: the simulator assumes it'}; "
            "the inertias fitted are only as right as it is"
        )
    print(
        f"  {len(replay.starts)} windows of {WINDOW_S} s; fitting "
        f"{', '.join(names) if names else 'nothing of the motors: this test holds them still'}"
    )

    def params_of(x, delay):
        return {**base, **dict(zip(names, x)), "delay": delay}

    def cost(x, delay):
        q, v, _ = replay.run(params_of(x, delay))
        return replay.joint_residuals(q, v)

    if names:
        x0 = [base[n] if base[n] > 0 else 0.5 * sum(BOUNDS[n]) * 0.1 for n in names]
        lo = [BOUNDS[n][0] for n in names]
        hi = [BOUNDS[n][1] for n in names]
        best = None
        for ms in delays:
            r = least_squares(
                cost,
                x0,
                bounds=(lo, hi),
                args=(ms / 1000.0,),
                x_scale="jac",
                max_nfev=40,
            )
            if best is None or r.cost < best[0].cost:
                best = (r, ms)
        r, ms = best
        fitted = params_of(r.x, ms / 1000.0)
    else:
        ms = delays[0]
        fitted = params_of([], ms / 1000.0)

    q, v, rate = replay.run(fitted)
    q0, v0, rate0 = replay.run({**base, "delay": ms / 1000.0})
    after, before = rms_by_group(replay, q, v), rms_by_group(replay, q0, v0)

    imu_delay = hinge_damping = None
    pitched = [np.std(per["gyro"][1]) for per in replay.samples if "gyro" in per]
    if replay.hinge and replay.gyro is not None and np.median(pitched) < PITCHED:
        print(
            "  the torso hardly pitched in this log, so the IMU's lag is not fitted "
            "from it; B4 is the test for that"
        )
    elif replay.hinge and replay.gyro is not None:
        # The rail's damping changes the swing, so each value of it needs the
        # model run again; the IMU's lag only shifts the comparison. Both are
        # searched, the lag finely and the damping coarsely: it is the rail's,
        # not the robot's, and is fitted only so it does not bend the rest.
        best_g = None
        for hd in HINGE_DAMPINGS:
            errs = replay.gyro_fit(
                {**fitted, "hinge_damping": hd}, IMU_DELAYS_MS / 1000.0
            )
            for d, e in errs.items():
                score = float(np.mean(e**2))
                if best_g is None or score < best_g[0]:
                    best_g = (score, hd, d)
        _, hinge_damping, imu_delay = best_g
        fitted["hinge_damping"], fitted["imu_delay"] = hinge_damping, float(imu_delay)

    print(f"\n{log.test}  the hanging robot, {args.log.name}")
    print(f"    {'':<16} {'simulator':>11} {'fitted':>11}")
    for n in (
        names
        + ["delay"]
        + (["imu_delay", "hinge_damping"] if imu_delay is not None else [])
    ):
        print(f"    {n:<16} {rig.NOMINAL[n]:11.4g} {fitted[n]:11.4g}")
    for g in after:
        b, a = before[g], after[g]
        where = f"position {b[0]:.4f} -> {a[0]:.4f} rad, " if g == "legs" else ""
        print(
            f"    {g:<6} error, {where}speed {b[1]:.3f} -> {a[1]:.3f} rad/s "
            "(simulator -> fitted)"
        )

    sw = swing(
        log, replay, [("simulator", {**base, "delay": ms / 1000.0}), ("fitted", fitted)]
    )
    if sw:
        print(
            f"    free swing on the rail: period {sw['measured_s']:.3f} s on the robot, "
            f"{sw['simulator_s']:.3f} in the simulator now, {sw['fitted_s']:.3f} fitted"
        )
    still = stillness(log)

    truth = log.header.get("truth")
    if truth:
        print("\nSYNTHETIC: what the model was built with, and what came back")
        for n in (
            names
            + ["delay"]
            + (["imu_delay", "hinge_damping"] if imu_delay is not None else [])
        ):
            print(f"    {n:<16} {truth[n]:11.4g} {fitted[n]:11.4g}")

    out = args.out or args.log.parent / "fit"
    out.mkdir(parents=True, exist_ok=True)
    result = {
        "log": str(args.log),
        "test": log.test,
        "fitted": {
            n: fitted[n]
            for n in names + ["delay", "imu_delay", "hinge_damping"]
            if fitted.get(n) is not None
        },
        "rms_before": before,
        "rms_after": after,
        "swing": sw,
        "still": still,
        "truth": truth,
    }
    path = out / f"fit_hung_{args.log.stem}.json"
    path.write_text(json.dumps(result, indent=2, default=float), encoding="utf-8")
    print(f"\nwritten {path}")
    if not args.no_plots:
        for p in plots(
            out, args.log.stem, replay, (q0, v0, rate0), (q, v, rate), imu_delay
        ):
            print(f"written {p}")
    return 0


def plots(out, stem, replay, nominal, fitted, imu_delay):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    made = []
    for i, j in enumerate(JOINTS):
        if j not in replay.tracked or j not in replay.commanded:
            continue
        spread = [
            np.ptp(per[j][1 if j in st.LEGS else 2])
            if j in per and len(per[j][0])
            else 0.0
            for per in replay.samples
        ]
        pick = np.sort(np.argsort(spread)[-4:])
        fig, axes = plt.subplots(1, 4, figsize=(14, 3.2))
        k = 1 if j in st.LEGS else 2
        for ax, w in zip(axes, pick):
            dt, p, vel = replay.samples[w][j]
            ax.plot(dt * 1000, p if k == 1 else vel, ".", ms=3, label="robot")
            ax.plot(
                replay.grid * 1000,
                (fitted[0] if k == 1 else fitted[1])[w, :, i],
                label="fitted",
            )
            ax.plot(
                replay.grid * 1000,
                (nominal[0] if k == 1 else nominal[1])[w, :, i],
                "--",
                label="simulator now",
            )
            ax.set_title(f"t = {replay.starts[w]:.1f} s", fontsize=9)
            ax.set_xlabel("ms")
        axes[0].set_ylabel("rad" if k == 1 else "rad/s")
        axes[0].legend(fontsize=8)
        fig.suptitle(j)
        fig.tight_layout()
        made.append(out / f"{stem}_{j}.png")
        fig.savefig(made[-1], dpi=100)
        plt.close(fig)
    return made


if __name__ == "__main__":
    sys.exit(main())
