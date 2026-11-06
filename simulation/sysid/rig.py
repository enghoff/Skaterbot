"""The robot hanging from the rail, in MuJoCo, with motors as the bench measures them.

Stage B of docs/SYSID.md hangs the robot by a rod through its two hoist lugs'
eyes, which leaves it free to pitch about the line between them and nothing
else. This is that: the URDF the policies train on, its torso on a hinge along
that line, no floor and no contacts, and every joint driven by the motor law in
actuator.py -- MIT mode's PD, the torque scale, the torque-speed line -- with
the joint's own armature, friction and damping as MuJoCo carries them.

The eye line's height comes from the CAD, so it moves when the torso does:
cad/parameters.py's hoistLugHoleDrop below cad/torso.py's shellTopZ, in the
torso's own frame, centred fore and aft.
"""

from __future__ import annotations

import heapq
import sys
from functools import lru_cache
from pathlib import Path

import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sbc"))

import actuator  # noqa: E402
import sysid_tests as st  # noqa: E402

URDF = ROOT / "simulation" / "urdf" / "wheeled_biped.urdf"
JOINTS = st.JOINTS
G = 9.80665

# What the simulator assumes now (simulation/robot.py ACTUATOR, plant.py).
NOMINAL = {
    "leg_armature": actuator.ARMATURE_KG_M2,
    "leg_friction": 0.0,
    "leg_damping": 0.0,
    "wheel_armature": actuator.ARMATURE_KG_M2,
    "wheel_friction": 0.0,
    "wheel_damping": 0.0,
    "scale": 1.0,
    "delay": 0.0,
    "imu_delay": 0.0,
    "hinge_damping": 0.0,
    "peak": actuator.PEAK_NM,
    "no_load": actuator.NO_LOAD_RAD_S,
}
# What synth.py builds its hanging robot with, so a fit has an answer to find.
TRUTH = {
    **NOMINAL,
    "leg_armature": 3.0e-4,
    "leg_friction": 0.03,
    "leg_damping": 0.002,
    "wheel_armature": 2.8e-4,
    "wheel_friction": 0.025,
    "wheel_damping": 8e-4,
    "scale": 0.95,
    "delay": 0.001,
    "imu_delay": 0.004,
    "hinge_damping": 0.003,
}


@lru_cache(maxsize=1)
def eye_height_m() -> float:
    """The hoist lugs' eye line above the torso's centre, from the CAD."""
    sys.path.insert(0, str(ROOT))
    from cad.dimensions import load

    d = load()
    return (d["shellTopZ"] - d["hoistLugHoleDrop"]) / 1000.0


def build(hinge: bool = True, dt: float = 1e-3) -> mujoco.MjModel:
    spec = mujoco.MjSpec.from_file(str(URDF))
    spec.option.timestep = dt
    spec.option.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    spec.option.disableflags |= mujoco.mjtDisableBit.mjDSBL_CONTACT
    spec.compiler.degree = False
    # A torso with no hinge is fixed, and a fixed body is fused into the world
    # unless asked not to be, which takes base_link's name with it.
    spec.compiler.fusestatic = False
    base = spec.body("base_link")
    base.pos = [0.0, 0.0, 1.0]
    if hinge:
        base.add_joint(
            name="rail",
            type=mujoco.mjtJoint.mjJNT_HINGE,
            axis=[0.0, 1.0, 0.0],
            pos=[0.0, 0.0, eye_height_m()],
        )
    return spec.compile()


class Hung:
    """The model and its state, stepped under per-joint MIT commands."""

    def __init__(self, params: dict, hinge: bool = True, dt: float = 1e-3):
        self.hinge = hinge
        self.m = build(hinge, dt)
        self.d = mujoco.MjData(self.m)
        self.dt = dt
        self.q = np.array([self.m.jnt_qposadr[self.m.joint(j).id] for j in JOINTS])
        self.v = np.array([self.m.jnt_dofadr[self.m.joint(j).id] for j in JOINTS])
        self.rail = self.m.joint("rail").id if hinge else None
        self.base = self.m.body("base_link").id
        self.set_params(params)

    def set_params(self, p: dict) -> None:
        self.p = {**NOMINAL, **p}
        p = self.p
        for i, j in enumerate(JOINTS):
            kind = "wheel" if j in st.WHEELS else "leg"
            dof = self.v[i]
            self.m.dof_armature[dof] = p[f"{kind}_armature"]
            self.m.dof_frictionloss[dof] = p[f"{kind}_friction"]
            self.m.dof_damping[dof] = p[f"{kind}_damping"]
        if self.hinge:
            self.m.dof_damping[self.m.jnt_dofadr[self.rail]] = p["hinge_damping"]
        self.motor = actuator.Motor(
            scale=p["scale"], delay=p["delay"], peak=p["peak"], no_load=p["no_load"]
        )

    def place(self, qpos: np.ndarray, qvel: np.ndarray, pitch=0.0, rate=0.0) -> None:
        mujoco.mj_resetData(self.m, self.d)
        self.d.qpos[self.q] = qpos
        self.d.qvel[self.v] = qvel
        if self.hinge:
            self.d.qpos[self.m.jnt_qposadr[self.rail]] = pitch
            self.d.qvel[self.m.jnt_dofadr[self.rail]] = rate
        mujoco.mj_forward(self.m, self.d)

    def step(self, table: np.ndarray) -> np.ndarray:
        """One step under a 6 x 5 table of MIT commands; returns the torque each
        joint's motor delivered."""
        q, v = self.d.qpos[self.q], self.d.qvel[self.v]
        tau = actuator.delivered(self.motor, table, q, v)
        self.d.qfrc_applied[self.v] = tau
        mujoco.mj_step(self.m, self.d)
        return tau

    def joints(self) -> tuple[np.ndarray, np.ndarray]:
        return self.d.qpos[self.q].copy(), self.d.qvel[self.v].copy()

    def pitch(self) -> tuple[float, float]:
        if not self.hinge:
            return 0.0, 0.0
        return (
            float(self.d.qpos[self.m.jnt_qposadr[self.rail]]),
            float(self.d.qvel[self.m.jnt_dofadr[self.rail]]),
        )

    def imu(self) -> dict[str, np.ndarray]:
        """What an IMU on the torso reads, in the torso's frame: its turn rate,
        and gravity's pull as the BNO085's gravity report gives it, m/s2."""
        rot = self.d.xmat[self.base].reshape(3, 3)
        # In the world's frame and turned into the torso's here: asked for in a
        # body's "local" frame, MuJoCo gives its principal axes of inertia.
        w = np.zeros(6)
        mujoco.mj_objectVelocity(
            self.m, self.d, mujoco.mjtObj.mjOBJ_BODY, self.base, w, 0
        )
        return {"gyro": rot.T @ w[:3], "gravity": rot.T @ np.array([0.0, 0.0, -G])}


def pitch_from_gravity(g: np.ndarray) -> float:
    """The torso's pitch about +Y from gravity in its frame: (sin, 0, -cos) x g."""
    return float(np.arctan2(g[0], -g[2]))


class HungPlant:
    """synth.py's robot: the hanging model, its motors answering as the real
    ones do, and an IMU that reads late."""

    joints = JOINTS

    def __init__(self, params: dict, rng, dt: float = 5e-4):
        self.sim = Hung(params, hinge=True, dt=dt)
        self.params = self.sim.p
        self.rng = rng
        self.t = 0.0
        self.cmd = {j: st.Cmd() for j in JOINTS}
        self.pending: list = []
        self.tau = np.zeros(len(JOINTS))
        self.history: list = []
        self.temp = 30.0
        # Hanging still, legs straight down, as it is before any test.
        self.sim.place(np.zeros(len(JOINTS)), np.zeros(len(JOINTS)))
        keep = self.sim.m.dof_damping.copy()
        self.sim.m.dof_damping[:] = 0.5
        for _ in range(int(3.0 / dt)):
            self.sim.step(np.zeros((len(JOINTS), 5)))
        self.sim.m.dof_damping[:] = keep
        self._record()

    def command(self, joint: str, c: st.Cmd, at: float) -> None:
        heapq.heappush(self.pending, (at, id(c), joint, c))

    def _record(self) -> None:
        self.history.append((self.t, self.sim.imu()))
        if len(self.history) > 400:
            del self.history[:100]

    def advance(self, to: float) -> None:
        while self.t < to - 1e-12:
            while self.pending and self.pending[0][0] <= self.t:
                _, _, j, c = heapq.heappop(self.pending)
                self.cmd[j] = c
            table = np.array([[c.p, c.v, c.kp, c.kd, c.t] for c in self.cmd.values()])
            self.tau = self.sim.step(table)
            self.t += self.sim.dt
            self._record()

    def report(self, joint: str):
        q, v = self.sim.joints()
        i = JOINTS.index(joint)
        r = self.rng
        from synth import NOISE

        return (
            q[i] + r.normal(0, NOISE["p"]),
            v[i] + r.normal(0, NOISE["v"]),
            self.tau[i] / self.params["scale"] + r.normal(0, NOISE["tau"]),
            int(self.temp),
        )

    def imu(self, t: float):
        """The reading of imu_delay ago."""
        want = t - self.params["imu_delay"]
        times = np.array([h[0] for h in self.history])
        k = int(np.clip(np.searchsorted(times, want), 0, len(times) - 1))
        reading = self.history[k][1]
        noise = {"gyro": 0.002, "gravity": 0.02}
        return [
            (name, vec + self.rng.normal(0, noise[name], 3))
            for name, vec in reading.items()
        ]

    def kick(self) -> None:
        rail = self.sim.m.jnt_dofadr[self.sim.rail]
        self.sim.d.qvel[rail] += 0.8
