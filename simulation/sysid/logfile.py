"""A system-identification log, read back into arrays on the controller's clock.

sbc/sysid_tests.py writes the format and says what each record is. This reads
it into one Track of reports and one Commands of commands per joint, in the
joint's frame, by the wiring the header carries -- so a wiring found wrong
after the run is corrected by editing the header, not by running again.

THE TWO CLOCKS. Every motor report and IMU reading is stamped by the controller
as it arrives; a command is stamped only by the host as it is sent, and the
host's clock is not the controller's. Two things put it there. The smallest gap
seen between a report's host time and its controller time is the clocks'
offset plus the quickest the link ever was, which maps the host's time onto the
controller's to within a millisecond or two. And every MIT command is answered
by one report from the motor it reached, sent as it arrived, so the first
report from that motor after the mapped send time is when the command took
hold, to the tenth of a millisecond. A command no report answered keeps the
mapped time plus the usual wait.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Track:
    """A motor's reports, joint frame, controller seconds."""

    t: np.ndarray
    p: np.ndarray
    v: np.ndarray
    tau: np.ndarray
    state: np.ndarray
    t_mos: np.ndarray
    t_rotor: np.ndarray

    def at(self, t: float) -> tuple[float, float]:
        """Position and speed at t, interpolated."""
        return float(np.interp(t, self.t, self.p)), float(np.interp(t, self.t, self.v))


@dataclass
class Commands:
    """A motor's commands, joint frame: t is when each reached the motor, on the
    controller's clock, and `answered` says whether a report pinned that down."""

    t: np.ndarray
    h: np.ndarray
    p: np.ndarray
    v: np.ndarray
    kp: np.ndarray
    kd: np.ndarray
    tau: np.ndarray
    answered: np.ndarray

    def __len__(self) -> int:
        return len(self.t)

    def table(self) -> np.ndarray:
        """N x 5: p, v, kp, kd, tau."""
        return np.column_stack((self.p, self.v, self.kp, self.kd, self.tau))


@dataclass
class Log:
    path: Path
    header: dict
    footer: dict | None
    tracks: dict[str, Track]
    commands: dict[str, Commands]
    imu: dict[str, tuple[np.ndarray, np.ndarray]]
    events: list[dict] = field(default_factory=list)
    stops: list[dict] = field(default_factory=list)
    clock: tuple[float, float] = (0.0, 0.0)
    reply_s: float = 0.0

    @property
    def test(self) -> str:
        return self.header["test"]

    def to_controller(self, h) -> np.ndarray:
        a, b = self.clock
        return (np.asarray(h, dtype=float) - a) / (1.0 + b)

    def segments(self) -> list[tuple[str, float, float]]:
        """(name, start, end) on the controller's clock."""
        marks = [e for e in self.events if "seg" in e and "answer" not in e]
        end = max((tr.t[-1] for tr in self.tracks.values() if len(tr.t)), default=0.0)
        out = []
        for k, e in enumerate(marks):
            stop = marks[k + 1]["t"] if k + 1 < len(marks) else end
            out.append((e["seg"], e["t"], stop))
        return out

    def answers(self, key: str) -> list[tuple[str, str, float]]:
        """(segment, value, controller time) for every answer under key."""
        return [
            (e["seg"], e["value"], e["t"])
            for e in self.events
            if e.get("answer") == key and e.get("value") not in (None, "")
        ]

    def window(self, joint: str, t0: float, t1: float) -> Track:
        tr = self.tracks[joint]
        k = (tr.t >= t0) & (tr.t < t1)
        return Track(*(getattr(tr, f)[k] for f in Track.__dataclass_fields__))


def _wiring(header: dict) -> dict[str, tuple[int, float]]:
    return {
        name: (int(w.get("sign", 1)), float(w.get("zero", 0.0)))
        for name, w in header.get("joints", {}).items()
    }


def _fit_clock(pairs: np.ndarray) -> tuple[float, float]:
    """host = t + a + b t, from the least-delayed messages: the smallest gap in
    each second, then a line through those and down onto the lowest of them."""
    t, gap = pairs[:, 0], pairs[:, 1] - pairs[:, 0]
    bins = np.floor(t - t.min()).astype(int)
    lows_t, lows_g = [], []
    for k in np.unique(bins):
        sel = bins == k
        i = np.argmin(gap[sel])
        lows_t.append(t[sel][i])
        lows_g.append(gap[sel][i])
    lows_t, lows_g = np.array(lows_t), np.array(lows_g)
    if len(lows_t) >= 3 and np.ptp(lows_t) > 5.0:
        b, a = np.polyfit(lows_t, lows_g, 1)
        a += np.min(lows_g - (a + b * lows_t))
    else:
        a, b = float(lows_g.min()), 0.0
    return float(a), float(b)


def load(path) -> Log:
    path = Path(path)
    header = footer = None
    fb: dict[str, list] = {}
    cmd: dict[str, list] = {}
    imu: dict[str, list] = {}
    events, stops, pairs = [], [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            kind = r.get("k")
            if kind == "f":
                fb.setdefault(r["j"], []).append(
                    (r["t"], r["p"], r["v"], r["q"], r["s"], r["tm"], r["tr"])
                )
                pairs.append((r["t"], r["h"]))
            elif kind == "c":
                cmd.setdefault(r["j"], []).append(
                    (r["h"], r["p"], r["v"], r["kp"], r["kd"], r["t"])
                )
            elif kind == "i":
                v = r["v"]
                imu.setdefault(r["r"], []).append((r["t"], *v))
                pairs.append((r["t"], r["h"]))
            elif kind == "n":
                events.append(r)
            elif kind == "x":
                stops.append(r)
            elif r.get("kind") == "header":
                header = r
            elif r.get("kind") == "footer":
                footer = r
    if header is None:
        raise ValueError(f"{path} has no header")

    clock = _fit_clock(np.array(pairs)) if pairs else (0.0, 0.0)
    log = Log(path, header, footer, {}, {}, {}, events, stops, clock)
    wiring = _wiring(header)

    for j, rows in fb.items():
        a = np.array(rows, dtype=float)
        a = a[np.argsort(a[:, 0], kind="stable")]
        s, z = wiring.get(j, (1, 0.0))
        log.tracks[j] = Track(
            a[:, 0],
            s * (a[:, 1] - z),
            s * a[:, 2],
            s * a[:, 3],
            a[:, 4].astype(int),
            a[:, 5],
            a[:, 6],
        )

    # Commands onto the controller's clock: mapped, then pinned to the report
    # that answered each, matched in order so no report answers two.
    waits = []
    staged = {}
    for j, rows in cmd.items():
        a = np.array(rows, dtype=float)
        mapped = log.to_controller(a[:, 0])
        reply = np.full(len(a), np.nan)
        tr = log.tracks.get(j)
        if tr is not None and len(tr.t):
            k = 0
            for i, t in enumerate(mapped):
                k = max(k, int(np.searchsorted(tr.t, t, side="left")))
                if k < len(tr.t) and tr.t[k] - t < 0.02:
                    reply[i] = tr.t[k]
                    k += 1
        waits.extend((reply - mapped)[~np.isnan(reply)])
        staged[j] = (a, mapped, reply)
    log.reply_s = float(np.median(waits)) if waits else 0.0
    for j, (a, mapped, reply) in staged.items():
        answered = ~np.isnan(reply)
        t = np.where(answered, reply, mapped + log.reply_s)
        s, z = wiring.get(j, (1, 0.0))
        log.commands[j] = Commands(
            t,
            a[:, 0],
            s * (a[:, 1] - z),
            s * a[:, 2],
            a[:, 3],
            a[:, 4],
            s * a[:, 5],
            answered,
        )

    # Into the torso's axes, as `map` found them; and the gravity report made
    # to point down, which is the way `map` found it points or the reverse.
    axes = header.get("imu_axes")
    rot = np.array(axes, dtype=float) if axes else None
    for report, rows in imu.items():
        a = np.array(rows, dtype=float)
        a = a[np.argsort(a[:, 0], kind="stable")]
        v = a[:, 1:]
        if rot is not None and v.shape[1] == 3:
            v = v @ rot.T
        if report == "gravity":
            v = v * header.get("imu_gravity_sign", 1)
        log.imu[report] = (a[:, 0], v)

    for e in log.events:
        e["t"] = float(log.to_controller(e["h"]))
    for e in log.stops:
        e["t"] = float(log.to_controller(e["h"]))
    return log


def describe(log: Log) -> str:
    h = log.header
    lines = [
        f"{log.path.name}: {h['test']} {h.get('title', '')}, {h.get('started', '')}"
    ]
    for j, tr in log.tracks.items():
        n_cmd = len(log.commands.get(j, []))
        span = tr.t[-1] - tr.t[0] if len(tr.t) > 1 else 0.0
        rate = (len(tr.t) - 1) / span if span else 0.0
        lines.append(
            f"  {j:<18} {len(tr.t):6d} reports over {span:6.1f} s ({rate:5.0f} Hz), "
            f"{n_cmd} commands"
        )
    for r, (t, _) in log.imu.items():
        span = t[-1] - t[0] if len(t) > 1 else 0.0
        lines.append(f"  imu {r:<14} {len(t):6d} over {span:6.1f} s")
    lines.append(
        f"  command to its report: {log.reply_s * 1000:.2f} ms typical; clock "
        f"offset {log.clock[0]:+.4f} s, drift {log.clock[1] * 1e6:+.1f} ppm"
    )
    for s in log.stops:
        lines.append(f"  STOPPED: {s['why']}")
    return "\n".join(lines)
