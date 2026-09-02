r"""The robot as a wheeled inverted pendulum, and a controller for it.

    Z:\IsaacSim\venv\Scripts\python.exe simulation/isaacsim/balance.py

Needs NumPy and SciPy and nothing else -- no Isaac Sim, no SimulationApp -- so
it runs in a second and the whole design can be checked before any simulator is
started. Run on its own it prints the plant it derived, the gains it chose, and
the closed-loop poles, and it fails if any of those poles is unstable.

WHAT THIS IS FOR. `run.py --check` proves the simulator is integrating the
robot the CAD describes. It says nothing about whether that robot can be
balanced, which is a question about the DESIGN: whether 3 Nm on a 40 mm wheel
under a 1.6 kg body is enough authority, and how much of the actuator's thermal
budget just standing still costs. This file answers it.

THE MODEL. With the legs locked straight the robot is a textbook wheeled
inverted pendulum: two wheels free to spin, and everything above them one rigid
body leaning about the wheel axle. Nothing here is typed in -- every mass,
centre of mass and inertia is read out of the URDF, which was itself integrated
from the CAD, so the model moves when the robot does.

  x      where the wheels are, metres, forward positive
  theta  how far the body leans, radians, FORWARD positive
  u      total wheel torque, Nm, positive drives forward

WHAT IT ASSUMES. Legs locked, so the four leg joints contribute mass and
inertia but no freedom. Small angles, so it is a linearisation and says nothing
about recovering from a large fall. Both wheels driven together, so it cannot
steer. And the plant is only as good as the numbers under it -- the rotor
inertia and the wheel mass have never been measured, and both are in here.

ONLY SIGNALS THE HARDWARE HAS. The controller reads body pitch and pitch rate,
which is an IMU, and wheel angle and wheel rate, which is the actuator's own
encoder. It never asks the simulator where the robot is, so the same control
law can be moved to the robot without acquiring a new sensor.
"""

from __future__ import annotations

import math
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SIMULATION = HERE.parent
for path in (str(SIMULATION), str(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)

import plant  # noqa: E402

try:
    from scipy.linalg import solve_continuous_are
except ImportError:
    # This file needs no simulator, but it does need SciPy, and the
    # interpreter that has SciPy here is Isaac Sim's.
    raise SystemExit(plant.needs_isaac_python("simulation/isaacsim/balance.py")) from None

GRAVITY = 9.81

# Which links are the body and which are the wheels, with the legs locked.
WHEEL_LINKS = ("wheel_right", "wheel_left")

# --------------------------------------------------------------------------
# Bryson's rule: weight each state by how much of it we are willing to accept.
#
# These are the only numbers in this file that are a choice rather than a
# measurement, so they are together and each says what it is allowing.

# Station keeping is what costs torque, and this robot has no cheap way to do
# it: with the legs frozen the only way to move is to lean first. So it is
# allowed to wander half a metre and to travel at a metre a second, and the
# lean is what is held tight.
MAX_POSITION_M = 0.50
MAX_LEAN_RAD = 0.05  # about 3 degrees of lean
MAX_SPEED_M_S = 1.0
MAX_LEAN_RATE_RAD_S = 2.0


@dataclass(frozen=True)
class Pendulum:
    """The wheeled inverted pendulum, in SI, read out of the URDF."""

    body_mass: float  # kg, everything above the wheel axle
    wheel_mass: float  # kg, both wheels
    wheel_inertia: float  # kg m^2 about the axle, both wheels, armature included
    body_inertia: float  # kg m^2 about the body's own centre of mass, pitch
    com_height: float  # m, body centre of mass above the wheel axle
    radius: float  # m

    @property
    def total_mass(self) -> float:
        return self.body_mass + self.wheel_mass

    def describe(self) -> str:
        return "\n".join(
            [
                f"  body mass            {self.body_mass * 1000:8.1f} g",
                f"  wheel mass, both     {self.wheel_mass * 1000:8.1f} g",
                f"  wheel inertia, both  {self.wheel_inertia:8.3e} kg m2  (armature included)",
                f"  body pitch inertia   {self.body_inertia:8.3e} kg m2  (about its own CoM)",
                f"  CoM above the axle   {self.com_height * 1000:8.1f} mm",
                f"  wheel radius         {self.radius * 1000:8.1f} mm",
            ]
        )


def _links_and_joints(urdf_path: Path):
    root = ET.parse(urdf_path).getroot()

    links = {}
    for link in root.findall("link"):
        inertial = link.find("inertial")
        if inertial is None:
            continue
        i = inertial.find("inertia")
        links[link.get("name")] = {
            "mass": float(inertial.find("mass").get("value")),
            "com": np.array([float(v) for v in inertial.find("origin").get("xyz").split()]),
            # Pitch is rotation about Y, so iyy is the only component this
            # planar model needs.
            "iyy": float(i.get("iyy")),
        }

    joints = {
        joint.get("name"): {
            "parent": joint.find("parent").get("link"),
            "child": joint.find("child").get("link"),
            "origin": np.array([float(v) for v in joint.find("origin").get("xyz").split()]),
        }
        for joint in root.findall("joint")
    }
    return links, joints


@lru_cache(maxsize=1)
def pendulum() -> Pendulum:
    """Reduce the URDF to the four numbers a planar balance model needs.

    Every joint in this robot has an identity rotation at its origin and the
    legs are locked straight, so with all angles at zero every link frame is
    parallel to base_link's. That is what makes this a sum rather than a
    kinematics problem: the inertia tensors add directly, and only the parallel
    axis term is needed.
    """
    links, joints = _links_and_joints(plant.URDF_PATH)

    # Where each link sits in base_link's frame, walking the joint tree.
    origin = {"base_link": np.zeros(3)}
    for name in ("hip_pitch_right", "knee_right", "wheel_drive_right",
                 "hip_pitch_left", "knee_left", "wheel_drive_left"):
        joint = joints[name]
        origin[joint["child"]] = origin[joint["parent"]] + joint["origin"]

    axle_z = origin["wheel_right"][2]
    if not math.isclose(axle_z, origin["wheel_left"][2]):
        raise ValueError("the two wheel axles are at different heights")

    body_links = [name for name in links if name not in WHEEL_LINKS]

    # -- the body: mass, centre of mass, and pitch inertia about that centre --
    mass = 0.0
    moment = np.zeros(3)
    for name in body_links:
        link = links[name]
        mass += link["mass"]
        moment += link["mass"] * (origin[name] + link["com"])
    centre = moment / mass

    inertia = 0.0
    for name in body_links:
        link = links[name]
        offset = origin[name] + link["com"] - centre
        # Parallel axis about the pitch (Y) axis: the x and z offsets count.
        inertia += link["iyy"] + link["mass"] * (offset[0] ** 2 + offset[2] ** 2)

    # -- the wheels ------------------------------------------------------
    # Their spin inertia plus the rotor inertia the 7:1 reduction reflects to
    # the joint. The armature is several times the wheel's own figure, which is
    # exactly why it cannot be left out of a balance model.
    wheel_mass = sum(links[name]["mass"] for name in WHEEL_LINKS)
    wheel_inertia = sum(links[name]["iyy"] + plant.ARMATURE_KG_M2 for name in WHEEL_LINKS)

    return Pendulum(
        body_mass=mass,
        wheel_mass=wheel_mass,
        wheel_inertia=wheel_inertia,
        body_inertia=inertia,
        com_height=float(centre[2] - axle_z),
        radius=plant.wheel_radius_m(),
    )


def state_space(p: Pendulum) -> tuple[np.ndarray, np.ndarray]:
    """Linearise about upright. State is [x, theta, x_dot, theta_dot].

    Horizontal:  M_t x'' + m l theta''            = u / r
    Body pitch:  m l x'' + I_t theta'' - m g l th = -u

    The reaction term is negative because a torque that drives the wheels
    forward pushes the body backwards, which is the whole trick: to catch a
    forward lean the controller drives forward, under the falling body.
    """
    m, l, r = p.body_mass, p.com_height, p.radius
    total = p.body_mass + p.wheel_mass + p.wheel_inertia / (r * r)
    pitch = p.body_inertia + m * l * l
    coupling = m * l
    gravity = m * GRAVITY * l

    determinant = total * pitch - coupling * coupling
    if determinant <= 0.0:
        raise ValueError("the mass matrix is not positive definite")

    A = np.zeros((4, 4))
    A[0, 2] = 1.0
    A[1, 3] = 1.0
    A[2, 1] = -coupling * gravity / determinant
    A[3, 1] = total * gravity / determinant

    B = np.zeros((4, 1))
    B[2, 0] = (pitch / r + coupling) / determinant
    B[3, 0] = (-total - coupling / r) / determinant
    return A, B


def traction_limit_nm(p: Pendulum | None = None) -> float:
    """The most TOTAL wheel torque that does anything, in Nm.

    THIS, NOT THE ACTUATOR, IS THE BINDING CONSTRAINT. Past mu m g at the
    contact the wheels slip, and a slipping wheel produces less force than a
    gripping one, so torque beyond this point does not merely stop helping --
    it loses the robot. On 85A urethane at the friction plant.py guesses, a
    1.6 kg robot on 40 mm wheels can use about 0.56 Nm across both wheels,
    which is well inside one actuator's 0.8 Nm thermal rating.

    The first version of this controller was weighted against the 3 Nm peak
    instead. It saturated from the first step, turned the loop bang-bang, and
    lost the robot after 6.8 seconds.
    """
    p = p or pendulum()
    return plant.CONTACT["dynamic_friction"] * p.total_mass * GRAVITY * p.radius


def weights() -> tuple[np.ndarray, np.ndarray]:
    Q = np.diag(
        [
            1.0 / MAX_POSITION_M**2,
            1.0 / MAX_LEAN_RAD**2,
            1.0 / MAX_SPEED_M_S**2,
            1.0 / MAX_LEAN_RATE_RAD_S**2,
        ]
    )
    # Bryson against the torque that is actually available, which is the
    # traction limit and not the actuator's peak.
    R = np.array([[1.0 / traction_limit_nm() ** 2]])
    return Q, R


@lru_cache(maxsize=1)
def gains() -> np.ndarray:
    """The LQR gain row. Total wheel torque is -K @ [x, theta, x_dot, theta_dot]."""
    A, B = state_space(pendulum())
    Q, R = weights()
    P = solve_continuous_are(A, B, Q, R)
    return np.linalg.solve(R, B.T @ P)


def torque(state: np.ndarray) -> float:
    """Total wheel torque for a state, before any per-joint limit is applied."""
    return float(-(gains() @ np.asarray(state, dtype=float).reshape(4, 1))[0, 0])


def closed_loop_poles() -> np.ndarray:
    A, B = state_space(pendulum())
    return np.linalg.eigvals(A - B @ gains())


# --------------------------------------------------------------------------


def main() -> int:
    p = pendulum()
    A, B = state_space(p)
    K = gains()
    open_loop = np.linalg.eigvals(A)
    closed = closed_loop_poles()

    print("the robot as a wheeled inverted pendulum, read out of the URDF")
    print(p.describe())

    print("\nopen loop poles, per second")
    print("  " + "  ".join(f"{v.real:+.2f}{v.imag:+.2f}j" for v in open_loop))
    unstable = [v for v in open_loop if v.real > 1e-9]
    print(
        f"  {len(unstable)} of them in the right half plane, which is the robot"
        " falling over."
    )
    if unstable:
        time_constant = 1.0 / max(v.real for v in unstable)
        print(f"  it diverges with a time constant of {time_constant * 1000:.0f} ms,")
        print("  which is how long a controller has to notice and respond.")

    print("\nLQR gains, total wheel torque = -K [x, theta, x_dot, theta_dot]")
    print(
        f"  K = [{K[0, 0]:+.2f} N/m, {K[0, 1]:+.2f} Nm/rad,"
        f" {K[0, 2]:+.2f} Ns/m, {K[0, 3]:+.2f} Nms/rad]"
    )

    print("\nclosed loop poles, per second")
    print("  " + "  ".join(f"{v.real:+.2f}{v.imag:+.2f}j" for v in closed))

    traction = traction_limit_nm(p)
    print("\nwhat torque is actually available")
    print(f"  traction limit       {traction:5.2f} Nm total, {traction / 2:.2f} Nm a wheel")
    print(f"  actuator thermal     {plant.CONTINUOUS_TORQUE_NM * 2:5.2f} Nm total")
    print(f"  actuator peak        {plant.PEAK_TORQUE_NM * 2:5.2f} Nm total")
    print("  the wheels slip before the actuator strains, so traction is the ceiling")

    # What a small disturbance actually costs, which is the design question.
    print("\nwhat it takes to hold a lean")
    for degrees in (1.0, 3.0, 5.0):
        needed = abs(torque([0.0, math.radians(degrees), 0.0, 0.0]))
        verdict = (
            "within traction"
            if needed <= traction
            else f"{needed / traction:.1f}x past traction -- the wheels would slip"
        )
        print(
            f"  {degrees:.0f} deg of lean asks {needed:5.2f} Nm total"
            f" ({needed / 2:.2f} a wheel), {verdict}"
        )

    worst = max(abs(v.real) for v in closed)
    print(f"\nfastest closed-loop mode {worst:.1f} rad/s, against a 400 Hz control rate")

    if any(v.real > -1e-6 for v in closed):
        print("\nDESIGN FAILED: the closed loop is not stable.")
        return 1
    print("\nStable. Whether it holds in Isaac Sim is a different question:")
    print("    run.py --balance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
