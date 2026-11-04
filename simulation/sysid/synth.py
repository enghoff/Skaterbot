# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy>=1.26", "trimesh>=4.0", "scipy>=1.11", "mujoco>=3.2",
#                 "build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1"]
# ///
"""Play a test against a model whose answers are known, and write the log the robot would.

    uv run simulation/sysid/synth.py A2 --out runs/A2_bare.jsonl
    uv run simulation/sysid/synth.py A2 --load-inertia 0.01 --out runs/A2_disc.jsonl
    uv run simulation/sysid/synth.py B1 --out runs/B1.jsonl --truth leg_armature=4e-4

Two uses. The fits in fit_bench.py and fit_hung.py are only worth trusting if
they find what is there, and this is data where what is there is known: the
"truth" goes into the header, and a fit should come back with it. And before a
test is run on the robot, its synthetic run shows what the motors will be asked
for and that it stays inside its limits.

It plays sbc/sysid_tests.py's own segments through the same Sequencer the robot
runner uses, at the test's rate, with the robot's path in between: a command
reaches its motor a fraction of a millisecond after it is sent, the motor
answers with a report of where it was, the report reaches the host a millisecond
or two later, positions, speeds and torques come back quantised as a
DM-J3507-2EC packs them, and the host's clock is not the controller's. The
wiring is deliberately not the identity, so a log read with the wrong signs
shows it.

The bench tests run against simulation/sysid/actuator.py's model of one motor;
the hanging tests against simulation/sysid/rig.py's MuJoCo robot.
"""

from __future__ import annotations

import argparse
import heapq
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sbc"))

import actuator  # noqa: E402
import sysid_tests as st  # noqa: E402

# The link, as the robot's has been measured or is likely to be.
HOST_OFFSET_S = 1234.5  # the host's clock, ahead of the controller's
DOWN_S = (0.3e-3, 1.2e-3)  # a command, host to motor
UP_S = (0.8e-3, 3.0e-3)  # a report, controller to host
REPLY_S = 0.1e-3  # a motor's answer, on the bus
# DM-J3507-2EC feedback packing, at the mapping ranges a fresh motor has.
PMAX, VMAX, TMAX = 12.5, 50.0, 5.0
# What a reading wanders by besides its quantisation.
NOISE = {"p": 2e-4, "v": 0.02, "tau": 0.004}

BENCH_TRUTH = actuator.Motor(
    inertia=3.1e-4,
    coulomb=0.035,
    viscous=6e-4,
    scale=0.93,
    delay=0.9e-3,
    peak=3.0,
    no_load=44.0,
)
# The arm on the scale in A1, and what a bench test is clamped to.
STALLED = {"A1", "A5"}


def quantise(x, span, bits):
    x = np.clip(x, -span, span)
    step = 2 * span / ((1 << bits) - 1)
    return np.round((x + span) / step) * step - span


class BenchPlant:
    """One motor on the bench: actuator.Motor's dynamics, with the output
    free, or stopped dead against the A1 scale."""

    def __init__(self, truth: actuator.Motor, load: float, stalled: bool, rng):
        self.m = actuator.Motor(**truth.as_dict())
        self.m.inertia = truth.inertia + load
        self.stalled = stalled
        self.rng = rng
        self.t = 0.0
        self.p, self.v = 0.3, 0.0
        self.cmd = st.Cmd()
        self.pending: list = []
        self.tau = 0.0
        self.temp = 31.0

    joints = (st.BENCH,)

    def command(self, joint: str, c: st.Cmd, at: float) -> None:
        heapq.heappush(self.pending, (at, id(c), c))

    def advance(self, to: float, dt=1e-4) -> None:
        while self.t < to - 1e-12:
            h = min(dt, to - self.t)
            while self.pending and self.pending[0][0] <= self.t:
                self.cmd = heapq.heappop(self.pending)[2]
            table = np.array(
                [self.cmd.p, self.cmd.v, self.cmd.kp, self.cmd.kd, self.cmd.t]
            )
            self.tau = float(actuator.delivered(self.m, table, self.p, self.v))
            if not self.stalled:
                acc = (
                    self.tau - float(actuator.friction(self.m, self.v))
                ) / self.m.inertia
                self.v += h * acc
                self.p += h * self.v
            asked = abs(float(actuator.mit(table, self.p, self.v)))
            self.temp += h * (40.0 * asked * asked - (self.temp - 25.0)) / 300.0
            self.t += h

    def report(self, joint: str):
        """What the motor says: position, speed, and the torque it believes it
        makes, which is the current it drives times the torque constant it
        assumes -- so it does not see its own scale error."""
        r = self.rng
        tau = self.tau / self.m.scale
        return (
            self.p + r.normal(0, NOISE["p"]),
            self.v + r.normal(0, NOISE["v"]),
            tau + r.normal(0, NOISE["tau"]),
            int(self.temp),
        )

    def imu(self, t: float):
        return []


def operator(test: str, args, plant, seq: st.Sequencer, now: float, state: dict):
    """The operator's answers, as someone at the bench would give them."""
    prompt = seq.prompt
    if prompt is None:
        state.pop("asked", None)
        return None
    asked = state.setdefault("asked", now)
    if "scale" in prompt.lower() and "grams" in prompt.lower() and test in STALLED:
        if now - asked < 1.0:
            return None
        force = abs(plant.tau) / (args.arm_mm / 1000.0)
        return f"{force / 9.80665 * 1000.0 + plant.rng.normal(0, 1.0):.0f}"
    if "Pack voltage" in prompt:
        return "24.6"
    if "swings" in prompt:
        if "kicked" not in state:
            state["kicked"] = now
            plant.kick()
        return "yes" if now - state["kicked"] > 12.0 else None
    if "luggage" in prompt:
        return None
    return "" if now - asked > 0.5 else None


def run(test_key: str, args, out: Path, truth: dict, seed: int = 1) -> Path:
    test = st.TESTS[test_key]
    rng = np.random.default_rng(seed)
    a = st.defaults(
        **{k: v for k, v in vars(args).items() if hasattr(st.defaults(), k)}
    )
    a.vmax = VMAX
    joints = test.joints(a)
    segments, limits = test.build(a)

    if test.fixture == "bench":
        motor = actuator.Motor(**{**BENCH_TRUTH.as_dict(), **truth})
        plant = BenchPlant(motor, a.load_inertia, test_key in STALLED, rng)
        wiring = {st.BENCH: st.Wiring("C", 1, -1, 0.7)}
        truth_out = motor.as_dict()
        delay = motor.delay
    elif test.fixture == "hung":
        import rig

        params = {**rig.TRUTH, **truth}
        plant = rig.HungPlant(params, rng)
        wiring = {
            j: st.Wiring(w.bus, w.id, -1 if "left" in j else 1, 0.05 * (i + 1))
            for i, (j, w) in enumerate(st.ASSUMED.items())
        }
        truth_out = dict(params)
        delay = params["delay"]
    else:
        raise SystemExit(
            f"{test_key} is a {test.fixture} test, which this does not model"
        )

    imu_axes = [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    header = {
        "test": test_key,
        "title": test.title,
        "fixture": test.fixture,
        "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "synthetic": True,
        "truth": truth_out,
        "args": {k: v for k, v in vars(a).items()},
        "hz": test.hz,
        "joints": {j: vars(w) for j, w in wiring.items()},
        "registers": {j: {"PMAX": PMAX, "VMAX": VMAX, "TMAX": TMAX} for j in wiring},
        "imu_axes": imu_axes if test.fixture == "hung" else None,
        "load_inertia": a.load_inertia,
    }
    writer = st.LogWriter(out, header)
    seq = st.Sequencer(segments, limits, joints)
    # The IMU's own axes are a quarter turn off the torso's, as a chip seated
    # any old way would be; the header says how, as `map` would have found.
    to_imu = np.array(imu_axes).T

    period = 1.0 / test.hz
    events: list = []
    fb_queue: list = []
    latest: dict[str, st.Fb] = {}
    op_state: dict = {}
    imu_next = {r: 0.0 for r in test.imu}
    reason = "done"

    def reply(joint: str, c_time: float):
        p, v, tau, temp = plant.report(joint)
        w = wiring[joint]
        pm, vm, qm = w.sign * p + w.zero, w.sign * v, w.sign * tau
        pm, vm, qm = (
            quantise(pm, PMAX, 16),
            quantise(vm, VMAX, 12),
            quantise(qm, TMAX, 12),
        )
        t = c_time + REPLY_S
        h = t + HOST_OFFSET_S + rng.uniform(*UP_S)
        writer.write(st.feedback_record(t, h, joint, 1, pm, vm, qm, temp - 3, temp))
        pj, vj, qj = w.to_joint(pm, vm, qm)
        heapq.heappush(fb_queue, (h, joint, st.Fb(h, pj, vj, qj, 1, temp - 3, temp)))

    # Every motor reports once before anything is commanded, as the runner's
    # status requests make it.
    for j in joints:
        reply(j, 0.0)

    k = 0
    while True:
        h_now = HOST_OFFSET_S + 0.05 + k * period + rng.uniform(0, 0.1e-3)
        c_now = h_now - HOST_OFFSET_S
        while events and events[0][0] <= c_now:
            t_ev, _, joint, cmd = heapq.heappop(events)
            plant.advance(t_ev)
            reply(joint, t_ev)
            plant.command(joint, cmd, t_ev + delay)
        for report, hz in test.imu.items():
            while imu_next[report] <= c_now:
                t_i = imu_next[report]
                plant.advance(max(t_i, plant.t))
                for name, vec in plant.imu(t_i):
                    if name != report:
                        continue
                    h = t_i + HOST_OFFSET_S + rng.uniform(*UP_S)
                    writer.write(
                        {
                            "k": "i",
                            "t": round(t_i, 6),
                            "h": round(h, 6),
                            "r": name,
                            "v": [round(float(x), 5) for x in to_imu @ vec],
                            "a": 3,
                        }
                    )
                imu_next[report] += 1.0 / hz
        plant.advance(c_now)
        while fb_queue and fb_queue[0][0] <= h_now:
            _, joint, f = heapq.heappop(fb_queue)
            latest[joint] = f
        answer = operator(test_key, a, plant, seq, h_now, op_state)
        if answer is not None:
            seq.answer(answer)
        try:
            cmds = seq.tick(h_now, latest)
        except st.Abort as why:
            writer.write({"k": "x", "h": round(h_now, 6), "why": str(why)})
            reason = f"stopped: {why}"
            break
        for e in seq.events:
            writer.write({"k": "n", "h": round(h_now, 6), **e})
        seq.events.clear()
        if cmds is None:
            break
        for j, c in cmds.items():
            m = wiring[j].to_motor(c)
            writer.write(st.command_record(h_now, j, m))
            arrive = c_now + rng.uniform(*DOWN_S)
            heapq.heappush(events, (arrive, k * 16 + len(events), j, c))
        k += 1
    writer.close({"ended": reason, "ticks": k})
    return out


def parse_truth(text: str) -> dict:
    out = {}
    for item in filter(None, (text or "").split(",")):
        key, _, value = item.partition("=")
        out[key.strip()] = float(value)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("test", choices=sorted(st.TESTS))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--truth", default="", help="name=value,... over the defaults")
    ap.add_argument("--seed", type=int, default=1)
    for name, value in vars(st.defaults()).items():
        flag = "--" + name.replace("_", "-")
        if isinstance(value, bool):
            ap.add_argument(flag, action="store_true")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            ap.add_argument(flag, type=type(value), default=value)
        else:
            ap.add_argument(flag, default=value)
    args = ap.parse_args(argv)
    path = run(args.test, args, args.out, parse_truth(args.truth), args.seed)
    print(f"{path}: {sum(1 for _ in open(path, encoding='utf-8'))} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
