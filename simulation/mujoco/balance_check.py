# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy>=1.26", "mujoco>=3.2", "onnxruntime>=1.18", "pyyaml>=6.0",
#                 "pygame>=2.5"]
# ///
"""The loop that runs the policy on the robot, run against MuJoCo instead.

    uv run simulation/mujoco/balance_check.py
    uv run simulation/mujoco/balance_check.py --run exports/rl/<run> --imu-ms 25

sbc/balance.py runs sbc/policy_loop.py on the robot, through diagd. This runs the
very same code against a simulated robot that answers it the way the real one
does: each motor reports only when a frame reaches it, a command takes effect
some milliseconds after it is sent, and the IMU's reports come late, at their
own rates, in the chip's own axes as sbc/sysid_robot.json says the chip sits.

It checks three things, and fails if any is wrong:

1. The input and the answer match simulation/mujoco/drive.py's, which is how
   the policy was checked against Isaac Lab, to float precision, on a spread of
   states. A sign or an order wrong in the loop shows here.
2. Tipped nose-down and held still, the policy drives its wheels forward, which
   is what the motors-off check on the robot looks for.
3. Closed loop through the delays the robot measured, it stands, drives,
   turns, and holds its place, without a fall.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import sys
from collections import deque
from pathlib import Path

import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sbc"))

import drive  # noqa: E402
import policy_loop as pl  # noqa: E402
import sysid_tests as st  # noqa: E402

RUN = ROOT / "exports" / "rl" / "rough-2026-11-04_09-01-34_measured_fix"
ROBOT_FILE = ROOT / "reference" / "motors" / "sysid_robot_2026-11-04.json"
G = 9.80665


class SimRig:
    """The robot as the loop meets it through diagd, in the joints' frame."""

    def __init__(
        self,
        ctl: drive.Controller,
        robot_file: dict,
        cmd_s: float,
        report_s: float,
        imu_s: float,
        gyro_hz: float,
        gravity_hz: float,
        seed: int = 0,
        broken: str | None = None,
    ):
        self.ctl, self.m = ctl, ctl.m
        self.d = mujoco.MjData(self.m)
        self.rng = np.random.default_rng(seed)
        self.cmd_s, self.report_s, self.imu_s = cmd_s, report_s, imu_s
        self.axes = np.array(robot_file["imu_axes"], dtype=float)
        self.to_chip = np.linalg.inv(self.axes)
        self.gravity_sign = robot_file["imu_gravity_sign"]
        self.periods = {"gyro": 1.0 / gyro_hz, "gravity": 1.0 / gravity_hz}
        self.t = 0.0
        self.latest: dict[str, st.Fb] = {}
        self.imu: dict[str, tuple[float, list]] = {}
        self.events: list = []
        self.seq = 0
        self.active = {j: st.Cmd() for j in st.JOINTS}
        self.next_imu = dict.fromkeys(self.periods, 0.0)
        self.past: deque = deque(maxlen=400)
        self.q = np.concatenate(
            (ctl.leg_q, [self.m.jnt_qposadr[self.m.joint(j).id] for j in st.WHEELS])
        )
        self.v = np.concatenate((ctl.leg_v, ctl.wheel_v))
        self.act = np.concatenate((ctl.leg_act, ctl.wheel_act))
        self.tau = np.zeros(6)
        # A hand or the strings, holding the torso's attitude and place while
        # it settles on its wheels, until the policy takes over.
        self.held_at: np.ndarray | None = None
        self.broken = broken

    def place(self, pitch: float = 0.0) -> None:
        self.ctl.place(self.d)
        q = np.zeros(4)
        mujoco.mju_euler2Quat(q, np.array([0.0, pitch, 0.0]), "XYZ")
        self.d.qpos[3:7] = q
        mujoco.mj_forward(self.m, self.d)

    def _at(self, t: float, kind: str, payload) -> None:
        self.seq += 1
        heapq.heappush(self.events, (t, self.seq, kind, payload))

    # -- what the loop calls

    def send(self, joint: str, c: st.Cmd) -> None:
        self._at(self.t + self.cmd_s, "cmd", (joint, c))
        self._at(self.t + self.report_s, "report", joint)

    def ask_status(self, joints) -> None:
        for j in joints:
            self._at(self.t + self.report_s, "report", j)

    def advance(self, until: float) -> None:
        dt = self.m.opt.timestep
        while True:
            while self.events and self.events[0][0] <= self.t:
                _, _, kind, payload = heapq.heappop(self.events)
                if kind == "cmd":
                    self.active[payload[0]] = payload[1]
                else:
                    self._report(payload)
            if self.t + dt > until + 1e-12:
                break
            self._physics(dt)

    # -- the robot

    def _report(self, joint: str) -> None:
        k = st.JOINTS.index(joint)
        p = float(self.d.qpos[self.q[k]]) + self.rng.normal(0, 2e-4)
        v = float(self.d.qvel[self.v[k]]) + self.rng.normal(0, 0.01)
        self.latest[joint] = st.Fb(self.t, p, v, float(self.tau[k]))

    def _physics(self, dt: float) -> None:
        d = self.d
        q, v = d.qpos[self.q], d.qvel[self.v]
        cmds = [self.active[j] for j in st.JOINTS]
        tau = np.array(
            [
                c.kp * (c.p - q[k]) + c.kd * (c.v - v[k]) + c.t
                for k, c in enumerate(cmds)
            ]
        )
        self.tau = self.ctl._saturate(tau, v)
        if self.broken == "wheel":
            self.tau[4] = -self.tau[4]
        d.ctrl[self.act] = self.tau
        mujoco.mj_step(self.m, d)
        if self.held_at is not None:
            d.qpos[0:2] = self.held_at[0:2]
            d.qpos[3:7] = self.held_at[3:7]
            d.qvel[0:2] = 0.0
            d.qvel[3:6] = 0.0
        self.t += dt
        rot = d.xmat[self.ctl.base].reshape(3, 3)
        w = d.qvel[3:6].copy()
        g = rot.T @ np.array([0.0, 0.0, -G])
        self.past.append((self.t, w, g))
        for report, period in self.periods.items():
            if self.t >= self.next_imu[report]:
                self.next_imu[report] += period
                self.imu[report] = (self.t, self._chip(report))

    def _chip(self, report: str) -> list:
        """The reading of imu_s ago, in the chip's axes, with a little noise."""
        want = self.t - self.imu_s
        _, w, g = next((p for p in self.past if p[0] >= want), self.past[-1])
        if report == "gyro":
            if self.broken == "gyro":
                w = -w
            v = self.to_chip @ w + self.rng.normal(0, 0.007, 3)
        else:
            v = self.gravity_sign * (self.to_chip @ g) + self.rng.normal(0, 0.01, 3)
        return [float(x) for x in v]

    # -- what the check reads

    def tilt_deg(self) -> float:
        return math.degrees(math.acos(np.clip(self.d.xmat[self.ctl.base][8], -1, 1)))

    def pitch_deg(self) -> float:
        """Nose down positive."""
        rot = self.d.xmat[self.ctl.base].reshape(3, 3)
        return math.degrees(pl.nose_down(rot.T @ np.array([0.0, 0.0, -1.0])))

    def forward_speed(self) -> float:
        rot = self.d.xmat[self.ctl.base].reshape(3, 3)
        return float((rot.T @ self.d.qvel[0:3])[0])

    def yaw_rate(self) -> float:
        return float(self.d.qvel[5])


def same_answers(ctl: drive.Controller, bal: pl.Balancer, rng) -> float:
    """The loop's input and answer against drive.py's, over random states."""
    m = ctl.m
    d = mujoco.MjData(m)
    worst = 0.0
    q_of = {j: m.jnt_qposadr[m.joint(j).id] for j in st.JOINTS}
    v_of = {j: m.jnt_dofadr[m.joint(j).id] for j in st.JOINTS}
    for _ in range(200):
        ctl.place(d)
        d.qpos[q_of["hip_pitch_right"]] += rng.uniform(-0.3, 0.3)
        d.qpos[q_of["knee_left"]] += rng.uniform(-0.3, 0.3)
        qa = rng.normal(size=4)
        d.qpos[3:7] = qa / np.linalg.norm(qa) * 0.2 + np.array([0.98, 0, 0, 0])
        d.qpos[3:7] /= np.linalg.norm(d.qpos[3:7])
        d.qvel[:] = rng.normal(0, 1.0, m.nv)
        mujoco.mj_forward(m, d)
        actions = rng.uniform(-1, 1, 6).astype(np.float32)
        command = np.array(
            [rng.uniform(-0.5, 0.5), rng.uniform(-1.5, 1.5), rng.uniform(0.185, 0.207)]
        )
        ctl.reset_state()
        ctl.actions = actions.copy()
        ctl.command = command.copy()
        theirs = ctl.observe(d)
        rot = d.xmat[ctl.base].reshape(3, 3)
        fb = {
            j: st.Fb(0.0, float(d.qpos[q_of[j]]), float(d.qvel[v_of[j]]), 0.0)
            for j in st.JOINTS
        }
        bal.actions = actions.copy()
        ours = bal.observe(
            fb, d.qvel[3:6], rot.T @ np.array([0.0, 0.0, -1.0]), *command
        )
        worst = max(worst, float(np.abs(ours - theirs).max()))
        cmds = bal.decide(ours.copy())
        ctl.actions = actions.copy()
        ctl.act(d)
        targets = np.array([cmds[j].p for j in st.LEGS])
        wheels = np.array([cmds[j].t for j in st.WHEELS])
        worst = max(worst, float(np.abs(targets - ctl.leg_targets).max()))
        worst = max(worst, float(np.abs(wheels - ctl.wheel_torque).max()))
    return worst


def tipped(bal: pl.Balancer, degrees: float) -> tuple[float, float]:
    """The wheel torques asked for, held still and tipped nose-down, legs in the
    crouch, from the policy's own memory of nothing."""
    p = math.radians(degrees)
    g = np.array([math.sin(p), 0.0, -math.cos(p)])
    fb = {
        j: st.Fb(0.0, float(bal.crouch[k]) if k < 4 else 0.0, 0.0, 0.0)
        for k, j in enumerate(st.JOINTS)
    }
    bal.reset()
    cmds = {}
    for _ in range(3):
        cmds = bal.decide(
            bal.observe(fb, np.zeros(3), g, 0.0, 0.0, bal.meta["default_height"]).copy()
        )
    return cmds["wheel_drive_right"].t, cmds["wheel_drive_left"].t


SCRIPT = [
    # (seconds, forward m/s, turn rad/s, name, shove m/s at its start)
    (3.0, 0.0, 0.0, "stand"),
    (3.0, 0.0, 0.0, "shoved forward", 0.3),
    (3.0, 0.0, 0.0, "shoved back", -0.3),
    (4.0, 0.25, 0.0, "forward 0.25"),
    (3.0, 0.0, 0.0, "stop"),
    (4.0, 0.0, 0.8, "turn 0.8"),
    (4.0, -0.25, 0.0, "back 0.25"),
    (10.0, 0.0, 0.0, "stand, holding"),
]


def closed_loop(ctl, net, robot_file, args, seed: int) -> tuple[bool, list[str]]:
    rig = SimRig(
        ctl,
        robot_file,
        cmd_s=args.cmd_ms / 1000,
        report_s=args.report_ms / 1000,
        imu_s=args.imu_ms / 1000,
        gyro_hz=args.gyro_hz,
        gravity_hz=args.gravity_hz,
        seed=seed,
        broken=args.broken,
    )
    rig.m.opt.timestep = 0.0005
    rig.place(pitch=math.radians(np.random.default_rng(seed).uniform(-3, 3)))
    bal = pl.Balancer(net)
    imu = pl.Imu(robot_file["imu_axes"], robot_file["imu_gravity_sign"])
    guard = pl.Guard(args.tilt, pl.limits())
    hold = pl.Hold(bal.meta["wheel_radius"])
    stepper = pl.Stepper(
        bal,
        imu,
        rig,
        guard,
        clock=lambda: rig.t,
        wait=rig.advance,
        nap=lambda: rig.advance(rig.t + rig.m.opt.timestep),
        hold=hold,
    )
    height = bal.meta["default_height"]
    crouch = {
        j: st.Cmd(p=float(bal.crouch[k]), kp=bal.kp, kd=bal.kd)
        for k, j in enumerate(st.LEGS)
    }
    crouch.update({j: st.Cmd() for j in st.WHEELS})
    for j, c in crouch.items():
        rig.active[j] = c
    rig.held_at = rig.d.qpos.copy()
    rig.advance(0.05)
    lines = []
    t0 = rig.t
    # The legs held in the crouch before the policy starts, as on the robot.
    for k in range(50):
        stepper.step(t0 + k * pl.PERIOD_S, 0.0, 0.0, height, override=crouch)
    bal.reset()
    rig.held_at = None
    t0 += 50 * pl.PERIOD_S
    ok = True
    try:
        for span, speed, turn, name, *shove in SCRIPT:
            if shove:
                rot = rig.d.xmat[ctl.base].reshape(3, 3)
                rig.d.qvel[0:3] += rot @ np.array([shove[0], 0.0, 0.0])
            steps = round(span / pl.PERIOD_S)
            speeds, turns, tilts, pitches = [], [], [], []
            x0 = rig.d.qpos[0:2].copy()
            for k in range(steps):
                stepper.step(t0 + k * pl.PERIOD_S, speed, turn, height)
                if k * pl.PERIOD_S >= 1.0:
                    speeds.append(rig.forward_speed())
                    turns.append(rig.yaw_rate())
                tilts.append(rig.tilt_deg())
                pitches.append(rig.pitch_deg())
            t0 += steps * pl.PERIOD_S
            moved = np.linalg.norm(rig.d.qpos[0:2] - x0) * 1000
            lines.append(
                f"  {name:<16} asked {speed:+.2f} m/s {turn:+.1f} rad/s, held "
                f"{np.mean(speeds):+.2f} m/s {np.mean(turns):+.2f} rad/s, "
                f"pitch {np.mean(pitches):+5.1f} deg, {min(pitches):+5.1f} to {max(pitches):+5.1f}, "
                f"tilt to {max(tilts):4.1f}, moved {moved:4.0f} mm"
            )
    except st.Abort as why:
        ok = False
        lines.append(f"  STOPPED at {rig.t:.2f} s: {why}")
    lines.append("  " + stepper.timing())
    return ok, lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, default=RUN)
    ap.add_argument("--imu-ms", type=float, default=16.0, help="how late the IMU reads")
    ap.add_argument("--cmd-ms", type=float, default=6.0, help="how late a command acts")
    ap.add_argument(
        "--report-ms", type=float, default=1.5, help="a motor's report, after a frame"
    )
    ap.add_argument("--gyro-hz", type=float, default=400.0)
    ap.add_argument(
        "--gravity-hz", type=float, default=30.0, help="the rail saw 25-60 Hz"
    )
    ap.add_argument("--tilt", type=float, default=30.0, help="the cut-off, degrees")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument(
        "--broken",
        choices=("wheel", "gyro"),
        help="a robot with one wheel or the gyro the wrong way round: this should fall",
    )
    args = ap.parse_args()

    cfg, onnx = drive.load_run(args.run)
    model = drive.build_model(cfg)
    ctl = drive.Controller(model, cfg, onnx)
    net = pl.Net(args.run / "exported" / "policy.npz")
    robot_file = json.loads(ROBOT_FILE.read_text())
    if net.meta["run"] != args.run.name:
        sys.exit(f"{args.run}/exported/policy.npz was packed from {net.meta['run']}")
    failed = False

    worst = same_answers(ctl, pl.Balancer(net), np.random.default_rng(0))
    good = worst < 1e-4
    failed |= not good
    print(
        f"1. against drive.py over 200 states: worst difference {worst:.1e}, {'same' if good else 'DIFFERENT'}"
    )

    bal = pl.Balancer(net)
    rows = [(deg, *tipped(bal, deg)) for deg in (-15, -8, 8, 15)]
    forward = all((right + left > 0) == (deg > 0) for deg, right, left in rows)
    failed |= not forward
    print(
        "2. tipped and held: "
        + ", ".join(
            f"{deg:+d} deg nose-down asks {right:+.2f} / {left:+.2f} Nm"
            for deg, right, left in rows
        )
        + ("; nose-down drives forward" if forward else "; WRONG WAY")
    )

    print(
        f"3. closed loop: the IMU {args.imu_ms:g} ms late, gyro {args.gyro_hz:g} Hz, gravity "
        f"{args.gravity_hz:g} Hz; commands act {args.cmd_ms:g} ms after sending; reports "
        f"{args.report_ms:g} ms after a frame"
    )
    for seed in range(args.seeds):
        ok, lines = closed_loop(ctl, net, robot_file, args, seed)
        failed |= not ok
        print(f" seed {seed}: {'stayed up' if ok else 'FELL'}")
        print("\n".join(lines))
    print("FAILED" if failed else "passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
