# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy>=1.26", "scipy>=1.11", "matplotlib>=3.8"]
# ///
"""Fit stage A of docs/SYSID.md: one motor on the bench.

    uv run simulation/sysid/fit_bench.py LOG [LOG ...] [--out DIR]

Give it every bench log of one motor at once; each is used for what its test
measures, and later ones lean on earlier ones' answers.

  A1  the torque the motor delivers, from the scale, against what it was
      commanded and what it reports
  A2  the inertia at the output, friction and the command's delay, by running
      the actuator model over short windows of the log from the measured state
      under the logged commands and fitting it to the speed the motor reported.
      Two A2 runs with different known loads separate the rotor's inertia from
      the torque scale; one run takes the scale from A1, or assumes 1.
  A3  the torque available at each speed, from the disc's acceleration at full
      command, and the straight line that replaces the simulator's
  A4  how long a command takes to show in the reported torque
  A5  how hot the winding gets at the continuous rating, and how fast

What it prints is set against the simulator's current figures. It writes the
numbers to fit_bench.json and its plots beside them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit, least_squares
from scipy.signal import savgol_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import actuator  # noqa: E402
import logfile  # noqa: E402

G = 9.80665
JOINT = "bench"
WINDOW_S = 0.25
STEP_S = 0.08
MOST_WINDOWS = 200
SIGMA_V = 0.05
# The delay is searched rather than fitted: a coarse pass, then a quarter of a
# millisecond either side of the best of it.
DELAYS_MS = (0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0)


def arg(log, name, default=0.0):
    return float(log.header.get("args", {}).get(name, default) or default)


# ---- A1 ------------------------------------------------------------------------


def fit_a1(logs) -> dict | None:
    rows = []
    for log in logs:
        arm = arg(log, "arm_mm") / 1000.0
        if arm <= 0:
            print(f"  {log.path.name}: no --arm-mm in its header; skipped")
            continue
        tr = log.tracks[JOINT]
        for seg, value, t in log.answers("scale_g"):
            asked = float(seg.split()[1])
            near = (tr.t > t - 0.6) & (tr.t < t - 0.1)
            reported = float(np.mean(tr.tau[near])) if near.any() else np.nan
            delivered = float(value) / 1000.0 * G * arm * np.sign(asked)
            rows.append((asked, reported, delivered))
    if not rows:
        return None
    a = np.array(rows)
    c, r, d = a.T
    by_cmd = float(c @ d / (c @ c))
    ok = ~np.isnan(r)
    by_rep = float(r[ok] @ d[ok] / (r[ok] @ r[ok])) if ok.any() else np.nan
    print("\nA1  torque, against the scale")
    print("    commanded   reported   delivered")
    for asked, reported, deliv in rows:
        print(f"    {asked:+8.3f}   {reported:+8.3f}   {deliv:+8.3f} Nm")
    print(
        f"    delivered = {by_cmd:.3f} x commanded, {by_rep:.3f} x reported "
        "(the simulator assumes 1)"
    )
    return {"scale": by_cmd, "scale_of_reported": by_rep, "points": rows}


# ---- A2 ------------------------------------------------------------------------


class Setup:
    """One log's windows, made ready for the model."""

    def __init__(self, log, rng):
        self.log = log
        self.load = arg(log, "load_inertia")
        cmd = log.commands[JOINT]
        self.cmd_t, self.table = cmd.t, cmd.table()
        tr = log.tracks[JOINT]
        self.tr = tr
        starts = []
        for name, t0, t1 in log.segments():
            if name.split()[0] in ("bang", "brake", "to", "speed", "square"):
                starts.extend(np.arange(t0 + 0.02, t1 - WINDOW_S, STEP_S))
        starts = np.array(starts)
        if len(starts) > MOST_WINDOWS:
            starts = np.sort(rng.choice(starts, MOST_WINDOWS, replace=False))
        self.starts = starts
        self.p0 = np.interp(starts, tr.t, tr.p)
        self.v0 = np.array([self._speed_at(t) for t in starts])
        self.samples = []
        for t0 in starts:
            k = (tr.t > t0) & (tr.t <= t0 + WINDOW_S)
            self.samples.append((tr.t[k] - t0, tr.v[k]))

    def _speed_at(self, t):
        """A line through the five reports nearest t, for its speed there."""
        k = np.argsort(np.abs(self.tr.t - t))[:5]
        if np.ptp(self.tr.t[k]) == 0:
            return float(self.tr.v[k].mean())
        slope, icpt = np.polyfit(self.tr.t[k] - t, self.tr.v[k], 1)
        return float(icpt)

    def run(self, motor):
        m = actuator.Motor(**motor.as_dict())
        m.inertia = motor.inertia + self.load
        grid, _, vs = actuator.simulate(
            m, self.cmd_t, self.table, self.starts, self.p0, self.v0, WINDOW_S
        )
        return grid, vs

    def residuals(self, motor):
        grid, vs = self.run(motor)
        out = [np.interp(dt, grid, vs[w]) - v for w, (dt, v) in enumerate(self.samples)]
        return np.concatenate(out) / SIGMA_V if out else np.zeros(0)


def fit_a2(logs, scale_hint: float | None) -> dict | None:
    if not logs:
        return None
    rng = np.random.default_rng(0)
    setups = [Setup(log, rng) for log in logs]
    loads = sorted({round(s.load, 9) for s in setups})
    fit_scale = len(loads) > 1
    scale = 1.0 if scale_hint is None else scale_hint

    def motor_from(x, delay):
        return actuator.Motor(
            inertia=x[0],
            coulomb=x[1],
            viscous=x[2],
            scale=x[3] if fit_scale else scale,
            delay=delay,
        )

    def cost(x, delay):
        return np.concatenate([s.residuals(motor_from(x, delay)) for s in setups])

    x0 = [actuator.ARMATURE_KG_M2, 0.02, 1e-4] + ([1.0] if fit_scale else [])
    lo = [1e-6, 0.0, 0.0] + ([0.5] if fit_scale else [])
    hi = [1e-2, 0.5, 0.05] + ([1.5] if fit_scale else [])
    best = None

    def attempt(ms):
        nonlocal best
        r = least_squares(
            cost, x0, bounds=(lo, hi), args=(ms / 1000.0,), x_scale="jac", max_nfev=60
        )
        rms = float(np.sqrt(np.mean(r.fun**2))) * SIGMA_V
        if best is None or rms < best[1]:
            best = (r, rms, ms)

    for ms in DELAYS_MS:
        attempt(ms)
    centre = best[2]
    for ms in (centre - 0.5, centre - 0.25, centre + 0.25, centre + 0.5):
        if ms >= 0.0:
            attempt(ms)
    r, rms, ms = best
    motor = motor_from(r.x, ms / 1000.0)
    nominal = actuator.Motor()
    rms0 = float(np.sqrt(np.mean(cost_nominal(setups, nominal) ** 2))) * SIGMA_V

    # Friction again, from the steady speeds alone: the torque each was held
    # with, against the speed.
    steady = []
    for s in setups:
        for name, t0, t1 in s.log.segments():
            if name.startswith("speed"):
                k = (s.tr.t > t1 - 1.5) & (s.tr.t < t1)
                if k.sum() > 10:
                    steady.append((s.tr.v[k].mean(), motor.scale * s.tr.tau[k].mean()))
    sweep = None
    if len(steady) >= 4:
        v, tau = np.array(steady).T
        a = np.column_stack((np.sign(v), v))
        (fc, b), *_ = np.linalg.lstsq(a, tau, rcond=None)
        sweep = {"coulomb": float(fc), "viscous": float(b), "points": steady}

    print(
        "\nA2  inertia, friction and delay, from",
        ", ".join(s.log.path.name for s in setups),
    )
    print(f"    loads on the output: {', '.join(f'{x:.3g}' for x in loads)} kg m2")
    print(
        f"    inertia at the output, the motor's own  {motor.inertia:.3e} kg m2   (simulator 2.30e-04)"
    )
    print(
        f"    Coulomb friction                         {motor.coulomb:.4f} Nm        (simulator 0)"
    )
    print(
        f"    viscous friction                         {motor.viscous:.2e} Nm s/rad (simulator 0)"
    )
    how = (
        "fitted"
        if fit_scale
        else ("from A1" if scale_hint is not None else "ASSUMED, not measured")
    )
    print(f"    torque delivered / commanded             {motor.scale:.3f}  {how}")
    print(
        f"    command to torque                        {ms:.2f} ms, to the nearest 0.25"
    )
    print(
        f"    speed error: {rms:.3f} rad/s rms fitted, {rms0:.3f} with the simulator's figures"
    )
    if sweep:
        print(
            f"    from the steady speeds alone: Coulomb {sweep['coulomb']:.4f} Nm, "
            f"viscous {sweep['viscous']:.2e} Nm s/rad"
        )
    return {
        "motor": motor.as_dict(),
        "scale_source": how,
        "rms_rad_s": rms,
        "rms_simulator_rad_s": rms0,
        "loads": loads,
        "sweep": sweep,
        "setups": setups,
    }


def cost_nominal(setups, motor):
    return np.concatenate([s.residuals(motor) for s in setups])


# ---- A3 ------------------------------------------------------------------------


def fit_a3(logs, motor: actuator.Motor | None) -> dict | None:
    if not logs:
        return None
    if motor is None:
        print(
            "\nA3  needs an A2 fit in the same run for the motor's own inertia; skipped"
        )
        return None
    out = {}
    for log in logs:
        load = arg(log, "load_inertia")
        inertia = motor.inertia + load
        tr = log.tracks[JOINT]
        pts = []
        for name, t0, t1 in log.segments():
            if not name.startswith("run-up"):
                continue
            sign = 1.0 if "+" in name.split()[1] else -1.0
            grid = np.arange(t0, t1, 0.001)
            if len(grid) < 25:
                continue
            v = np.interp(grid, tr.t, tr.v) * sign
            acc = savgol_filter(v, 21, 3, deriv=1, delta=0.001)
            vs = savgol_filter(v, 21, 3)
            tau = (
                inertia * acc + motor.coulomb * np.tanh(vs / 0.02) + motor.viscous * vs
            )
            # The filter's ends are guesses, and the first of them is the step
            # the run-up starts with.
            keep = vs > 1.0
            keep[:12] = keep[-12:] = False
            pts.extend(zip(vs[keep], tau[keep]))
        if not pts:
            continue
        v, tau = np.array(pts).T
        edges = np.arange(0.0, v.max() + 2.0, 2.0)
        table = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            k = (v >= lo) & (v < hi)
            if k.sum() >= 5:
                table.append(((lo + hi) / 2, float(np.median(tau[k]))))
        tb = np.array(table)
        top = tb[:, 1].max()
        line = tb[(tb[:, 1] < 0.92 * top) & (tb[:, 0] > 2.0)]
        stall = no_load = np.nan
        if len(line) >= 3:
            slope, icpt = np.polyfit(line[:, 0], line[:, 1], 1)
            stall, no_load = float(icpt), float(-icpt / slope)
        pack = log.answers("pack_v")
        pack_v = pack[0][1] if pack else "not given"
        print(f"\nA3  torque against speed, {log.path.name} (pack {pack_v} V)")
        print("    speed rad/s   torque Nm")
        for s, t in table[:: max(1, len(table) // 12)]:
            print(f"    {s:8.1f}      {t:6.3f}")
        print(
            f"    the line through the falling part: {stall:.3f} Nm at standstill, "
            f"none at {no_load:.1f} rad/s (simulator: 3.000 and 48.2)"
        )
        out[log.path.name] = {
            "pack_v": pack_v,
            "stall_nm": stall,
            "no_load_rad_s": no_load,
            "table": table,
            "points": (v, tau),
        }
    return out


# ---- A4, A5 --------------------------------------------------------------------


def fit_a4(logs) -> dict | None:
    """How soon after a reversal the motor's reports show it. A motor answers
    each command as it arrives, so its reports come at the command rate and
    this can say no better than "within one interval"; A2's fit, which runs
    the model at a fifth of a millisecond, is the finer figure."""
    lags, first = [], []
    for log in logs:
        cmd, tr = log.commands[JOINT], log.tracks[JOINT]
        flips = np.nonzero(np.diff(np.sign(cmd.tau)) != 0)[0] + 1
        for i in flips:
            t0, new = cmd.t[i], cmd.tau[i]
            after = (tr.t >= t0 - 0.002) & (tr.t < t0 + 0.05)
            tt, q = tr.t[after], tr.tau[after] * np.sign(new)
            cross = np.nonzero((q[:-1] < 0) & (q[1:] >= 0))[0]
            if len(cross):
                first.append(tt[cross[0] + 1] - t0)
                c = cross[0]
                frac = -q[c] / (q[c + 1] - q[c])
                lags.append(tt[c] + frac * (tt[c + 1] - tt[c]) - t0)
    if not lags:
        return None
    lags, first = np.array(lags), np.array(first)
    step = float(np.median(np.diff(logs[0].tracks[JOINT].t)))
    print("\nA4  command to reported torque")
    print(
        f"    the first report showing a reversal comes {np.median(first) * 1000:.2f} ms "
        f"after it (median of {len(first)}), with reports every {step * 1000:.2f} ms, "
        f"so the torque changed within that; {np.median(lags) * 1000:.2f} ms by "
        "interpolating between reports"
    )
    return {
        "first_report_s": float(np.median(first)),
        "interpolated_s": float(np.median(lags)),
        "report_interval_s": step,
        "n": len(first),
    }


def fit_a5(logs) -> dict | None:
    out = {}
    for log in logs:
        tr = log.tracks[JOINT]
        segs = [s for s in log.segments() if s[0].startswith("hold")]
        if not segs:
            continue
        _, t0, t1 = segs[0]
        k = (tr.t >= t0) & (tr.t <= t1)
        t, temp = tr.t[k] - t0, tr.t_rotor[k]

        def rise(t, top, tau):
            return top - (top - temp[0]) * np.exp(-t / tau)

        try:
            (top, tau), _ = curve_fit(
                rise, t, temp, p0=(temp.max() + 5, 200.0), maxfev=5000
            )
        except RuntimeError:
            top, tau = np.nan, np.nan
        hold = arg(log, "hold_torque", 0.8)
        print(f"\nA5  heat at {hold:g} Nm, {log.path.name}")
        print(
            f"    winding {temp[0]:.0f} C to {temp.max():.0f} C in {t[-1] / 60:.1f} min; "
            f"settles near {top:.0f} C with a {tau / 60:.1f} min time constant"
        )
        if not t[-1] > 2.0 * tau:
            # The motor reports whole degrees, and a curve seen for less than
            # two of its time constants says little about where it ends.
            print(
                "    that is an extrapolation: the run was shorter than twice the "
                "time constant. Run it for longer to pin it down."
            )
        out[log.path.name] = {
            "start_c": float(temp[0]),
            "end_c": float(temp.max()),
            "settles_c": float(top),
            "tau_s": float(tau),
        }
    return out or None


# ---- plots ---------------------------------------------------------------------


def plots(out: Path, a1, a2, a3) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    made = []
    if a2:
        motor = actuator.Motor(**a2["motor"])
        s = a2["setups"][0]
        # The windows the speed changed most in, which are the ones that say
        # anything about inertia.
        spread = [np.ptp(v) if len(v) else 0.0 for _, v in s.samples]
        pick = np.sort(np.argsort(spread)[-6:])
        grid, fitted = s.run(motor)
        _, nominal = s.run(actuator.Motor())
        fig, axes = plt.subplots(2, 3, figsize=(12, 6), sharey=False)
        for ax, w in zip(axes.ravel(), pick):
            dt, v = s.samples[w]
            ax.plot(dt * 1000, v, ".", ms=3, label="motor")
            ax.plot(grid * 1000, fitted[w], label="fitted")
            ax.plot(grid * 1000, nominal[w], "--", label="simulator now")
            ax.set_title(f"t = {s.starts[w]:.2f} s", fontsize=9)
            ax.set_xlabel("ms")
        axes[0, 0].set_ylabel("rad/s")
        axes[0, 0].legend(fontsize=8)
        fig.suptitle(f"A2 windows, {s.log.path.name}")
        fig.tight_layout()
        made.append(out / "a2_windows.png")
        fig.savefig(made[-1], dpi=110)
        plt.close(fig)
        if a2["sweep"]:
            v, tau = np.array(a2["sweep"]["points"]).T
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.plot(v, tau, "o", label="held speeds")
            vv = np.linspace(v.min(), v.max(), 200)
            ax.plot(vv, actuator.friction(motor, vv), label="fitted from the windows")
            ax.set_xlabel("rad/s")
            ax.set_ylabel("Nm")
            ax.legend()
            ax.set_title("friction")
            fig.tight_layout()
            made.append(out / "a2_friction.png")
            fig.savefig(made[-1], dpi=110)
            plt.close(fig)
    for name, r in (a3 or {}).items():
        v, tau = r["points"]
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(v, tau, ",", alpha=0.4, label="from acceleration")
        tb = np.array(r["table"])
        ax.plot(tb[:, 0], tb[:, 1], "o-", label="median by speed")
        vv = np.linspace(0, max(50.0, v.max()), 100)
        ax.plot(vv, actuator.saturate(3.0, vv), "--", label="simulator now")
        if np.isfinite(r["stall_nm"]):
            ax.plot(
                vv,
                np.clip(r["stall_nm"] * (1 - vv / r["no_load_rad_s"]), 0, None),
                label="fitted line",
            )
        ax.set_xlabel("rad/s")
        ax.set_ylabel("Nm available")
        ax.legend()
        ax.set_title(f"A3 {name}")
        fig.tight_layout()
        made.append(out / f"a3_{Path(name).stem}.png")
        fig.savefig(made[-1], dpi=110)
        plt.close(fig)
    if a1:
        c, rep, d = np.array(a1["points"]).T
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.plot(c, d, "o", label="against commanded")
        ax.plot(rep, d, "x", label="against reported")
        lim = np.abs(c).max() * 1.1
        ax.plot([-lim, lim], [-lim, lim], "--", lw=0.8, label="equal")
        ax.set_xlabel("Nm asked / reported")
        ax.set_ylabel("Nm on the scale")
        ax.legend()
        fig.tight_layout()
        made.append(out / "a1_torque.png")
        fig.savefig(made[-1], dpi=110)
        plt.close(fig)
    return made


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("logs", nargs="+", type=Path)
    ap.add_argument(
        "--out",
        type=Path,
        help="where the results go; beside the first log if not given",
    )
    ap.add_argument(
        "--scale", type=float, help="torque delivered / commanded, if known otherwise"
    )
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args(argv)

    logs = [logfile.load(p) for p in args.logs]
    by_test: dict[str, list] = {}
    for log in logs:
        print(logfile.describe(log))
        if JOINT not in log.tracks:
            print(f"  {log.path.name} is not a bench log; skipped")
            continue
        by_test.setdefault(log.test, []).append(log)

    a1 = fit_a1(by_test.get("A1", []))
    hint = args.scale if args.scale is not None else (a1["scale"] if a1 else None)
    a2 = fit_a2(by_test.get("A2", []), hint)
    motor = actuator.Motor(**a2["motor"]) if a2 else None
    a3 = fit_a3(by_test.get("A3", []), motor)
    a4 = fit_a4(by_test.get("A4", []))
    a5 = fit_a5(by_test.get("A5", []))

    out = args.out or args.logs[0].parent / "fit"
    out.mkdir(parents=True, exist_ok=True)
    result = {
        "logs": [str(p) for p in args.logs],
        "torque": {k: v for k, v in (a1 or {}).items() if k != "points"} or None,
        "motor": a2["motor"] if a2 else None,
        "scale_source": a2["scale_source"] if a2 else None,
        "friction_sweep": (
            {k: v for k, v in a2["sweep"].items() if k != "points"}
            if a2 and a2["sweep"]
            else None
        ),
        "torque_speed": {
            k: {x: y for x, y in v.items() if x != "points"}
            for k, v in (a3 or {}).items()
        }
        or None,
        "latency": a4,
        "heat": a5,
    }
    truths = {
        log.path.name: log.header["truth"] for log in logs if log.header.get("truth")
    }
    if truths:
        result["truth"] = truths
        t = next(iter(truths.values()))
        if motor:
            print("\nSYNTHETIC: what the model was built with, and what came back")
            for key in ("inertia", "coulomb", "viscous", "scale", "delay"):
                print(f"    {key:<8} {t[key]:.4g}   fitted {getattr(motor, key):.4g}")
            for r in (a3 or {}).values():
                print(
                    f"    no_load  {t['no_load']:.4g}   fitted {r['no_load_rad_s']:.4g}"
                )
    (out / "fit_bench.json").write_text(
        json.dumps(result, indent=2, default=float), encoding="utf-8"
    )
    print(f"\nwritten {out / 'fit_bench.json'}")
    if not args.no_plots:
        for p in plots(out, a1, a2, a3):
            print(f"written {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
