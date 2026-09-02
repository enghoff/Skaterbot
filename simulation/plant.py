"""The simulator-facing choices, in one place and framework-independent.

The URDF says what the mechanism IS: links, masses, inertia tensors, joint
axes, travel. None of that is a choice, and none of it belongs here. This
module holds the things that ARE choices -- how hard the actuator may push,
what the wheels grip, how finely the solver integrates, where the robot starts
-- so that the Isaac Sim scripts and the Isaac Lab config cannot drift apart by
being edited separately.

Nothing in here is typed in twice either. The actuator numbers come from
robot.py, which is where this project already keeps them; the geometry comes
from the KCL by way of kcl_params, so a change to the CAD moves it. What is
genuinely new -- contact, solver settings, randomisation ranges -- is written
once, below, with its provenance.

IT IMPORTS NOTHING BUT THE STANDARD LIBRARY. That is deliberate: Isaac Sim
ships its own Python, and this module has to be importable inside it without
installing anything. numpy, trimesh and the rest stay on the build side.

READ THE UNMEASURED MARKERS. Three numbers here decide whether a policy trained
against this plant has any chance of transferring, and all three are currently
guesses: the actuator's reflected rotor inertia, its velocity limit, and the
friction of urethane on whatever the robot is driven on.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from robot import ACTUATOR  # noqa: E402
from kcl_params import load as load_dimensions  # noqa: E402

# --------------------------------------------------------------------------
# Where the description is

ROBOT_NAME = "wheeled_biped"

# Where Isaac Sim's own Python lives on this machine. Nothing here imports it.
# It is recorded so that the scripts which DO need it can say where it is when
# they are started with the system interpreter instead -- which is much the
# commonest way to trip over this directory, and the resulting
# "No module named 'omni'" points nowhere useful.
ISAAC_PYTHON = Path(r"Z:\IsaacSim\venv\Scripts\python.exe")


def needs_isaac_python(script: str) -> str:
    """The message for someone who ran an Isaac script with the wrong Python."""
    interpreter = ISAAC_PYTHON if ISAAC_PYTHON.exists() else Path("<isaac>/python.exe")
    return (
        f"\n{script} needs Isaac Sim's own Python, not the system one."
        f"\n\n    {interpreter} -u {script}"
        "\n\nor activate that environment first:"
        f"\n\n    {ISAAC_PYTHON.parent / 'activate'}"
        "\n\nPass -u either way: Kit shuts down hard enough to discard buffered"
        "\noutput, so without it a finished run can print nothing at all.\n"
    )

URDF_PATH = HERE / "urdf" / f"{ROBOT_NAME}.urdf"
USD_DIR = HERE / "isaacsim" / "usd"

# Isaac Sim 6.0's URDF importer takes an output DIRECTORY and writes
# <dir>/<robot name>/<robot name>.usda inside it, so the path below is the
# importer's choice rather than ours. It also refuses to overwrite: given a
# directory that already exists it invents wheeled_biped_01 beside it, which is
# why import_urdf.py clears the old one before every build.
ROBOT_USD_PATH = USD_DIR / ROBOT_NAME / f"{ROBOT_NAME}.usda"

# --------------------------------------------------------------------------
# The actuator, all six of them the same.
#
# DAMIAO DM-J3507-2EC, 7:1, 24 V, CAN-FD, MIT-mode torque control. These are
# robot.py's own figures, re-exported so that a simulator config never states
# an actuator number in its own right.

PEAK_TORQUE_NM = ACTUATOR["peak_torque_nm"]
CONTINUOUS_TORQUE_NM = ACTUATOR["continuous_torque_nm"]
MAX_VELOCITY_RAD_S = ACTUATOR["max_velocity_rad_s"]
ARMATURE_KG_M2 = ACTUATOR["armature_kg_m2"]
JOINT_FRICTION_NM = ACTUATOR["friction_nm"]
JOINT_DAMPING_NM_S_RAD = ACTUATOR["damping_nm_s_rad"]

# --------------------------------------------------------------------------
# The joints, in the order this project names them.
#
# Isaac Sim reports degrees of freedom in ITS OWN order, which is a depth-first
# walk of the articulation and is not this one. Every script here resolves by
# name and never by index; this tuple exists so that a report can be printed in
# an order a person recognises, and so that a missing joint is noticed.

LEG_JOINTS = (
    "hip_pitch_right",
    "knee_right",
    "hip_pitch_left",
    "knee_left",
)
WHEEL_JOINTS = (
    "wheel_drive_right",
    "wheel_drive_left",
)
JOINT_ORDER = (
    "hip_pitch_right",
    "knee_right",
    "wheel_drive_right",
    "hip_pitch_left",
    "knee_left",
    "wheel_drive_left",
)

# --------------------------------------------------------------------------
# Where it starts
#
# base_link's origin is the torso centre. A centimetre of clearance keeps the
# wheels off the ground plane at reset, so the first contact is resolved rather
# than penetrated.

RESET_CLEARANCE_M = 0.01

# --------------------------------------------------------------------------
# Ground contact
#
# UNMEASURED, ALL OF IT. 85A skate urethane on a hard floor is a high-friction,
# fairly lossy contact, and none of these numbers come from a measurement of
# this wheel on any surface. They are a starting point to randomise around, not
# a description of anything.
#
# The wheel collides as a cylinder rather than as its crowned tread, because
# every solver resolves a cylinder against a plane cleanly and none of them
# resolves a crowned mesh cleanly. What that loses is the contact patch
# narrowing as the robot leans, which is real; if a policy turns out to depend
# on it, that is the assumption to revisit first.

CONTACT = {
    "static_friction": 1.0,
    "dynamic_friction": 0.9,
    "restitution": 0.1,
}

# Ranges worth randomising over, since the true value is unknown. Urethane on a
# painted concrete floor and urethane on a rug are not the same robot.
DOMAIN_RANDOMISATION = {
    "static_friction": (0.6, 1.4),
    "dynamic_friction": (0.5, 1.2),
    # The wheels have never been weighed and the capacitor bank has never been
    # sized, so the mass this model carries is uncertain by a good deal more
    # than the usual few per cent. Randomise the base mass accordingly.
    "base_mass_scale": (0.85, 1.15),
    "wheel_mass_scale": (0.8, 1.2),
    "armature_scale": (0.5, 2.0),
}

# --------------------------------------------------------------------------
# The solver
#
# A 40 mm wheel at the actuator's 20 rad/s covers 2 mm of ground in a 2.5 ms
# step, which is small against the wheel's own radius and is what a rolling
# contact needs to stay a rolling contact. That is tighter than the 4 ms the
# Isaac Lab config's CCD note assumes, and it is cheap on a robot with seven
# links.
#
# The iteration counts are the Isaac Lab config's, unchanged. A six-degree-of-
# freedom articulation standing on two point-ish contacts is not a hard solve;
# raise the position count first if the wheels start sinking.

PHYSICS_DT = 1.0 / 400.0
RENDER_DT = 1.0 / 60.0

SOLVER = {
    "position_iterations": 8,
    "velocity_iterations": 2,
    # This robot is small and light, and CCD stays on until it is shown to be
    # unnecessary.
    "max_depenetration_velocity": 1.0,
    "enable_ccd": True,
    # A balancing robot that falls asleep is a balancing robot that has fallen
    # over. Nothing here should ever sleep.
    "sleep_threshold": 0.0,
    "stabilization_threshold": 0.0,
}

# The legs fold under the robot at the knee's 110 degree stop, and the wheel
# comes up close to the thigh there. Self collision is left ON so that the stop
# is enforced by geometry as well as by the joint limit -- but it is the
# setting most likely to make a fresh import behave oddly, so it is named here
# rather than buried.
SELF_COLLISION = True


# --------------------------------------------------------------------------
# Geometry, read out of the CAD


@lru_cache(maxsize=1)
def geometry() -> dict[str, float]:
    """The handful of CAD dimensions a simulator scene needs, in metres.

    Read from the KCL, so a change to the CAD moves the scene without anything
    here being edited. The relationships are asserted rather than the numbers,
    the same way build_urdf.py does it: a dimension that failed to parse breaks
    a relationship, and a legitimate design change does not.
    """
    d = load_dimensions()

    wheel_radius = d["prototypeWheelAxisHeight"] / 1000.0
    standing_base_height = d["wheeledTorsoCenterHeight"] / 1000.0
    standing_height = d["wheeledTorsoTop"] / 1000.0
    track = (d["skateWheelCenterX"] * 2.0 + d["hipSpacing"]) / 1000.0

    assert (
        abs(wheel_radius - d["skateWheelDiameter"] / 2000.0) < 1e-9
    ), "the wheel axis is not at the wheel's own radius"
    assert (
        0.0 < wheel_radius < standing_base_height < standing_height
    ), "the robot's heights do not stack up"

    return {
        "wheel_radius_m": wheel_radius,
        "wheel_width_m": d["skateWheelWidth"] / 1000.0,
        "standing_base_height_m": standing_base_height,
        "standing_height_m": standing_height,
        "track_m": track,
    }


def standing_base_height_m() -> float:
    """How high base_link's origin sits with the legs straight."""
    return geometry()["standing_base_height_m"]


def spawn_height_m() -> float:
    """Where to drop base_link from, wheels a centimetre clear of the floor."""
    return standing_base_height_m() + RESET_CLEARANCE_M


def wheel_radius_m() -> float:
    """The rolling radius, which run.py measures back out of the simulation."""
    return geometry()["wheel_radius_m"]


# --------------------------------------------------------------------------
# The continuous torque limit
#
# The URDF carries the 3 Nm peak because that is the only limit a URDF can
# express. The 0.8 Nm continuous rating is thermal, and docs/PLAN.md already
# records that the knee crosses it at about 47 degrees of sustained flexion
# just holding the robot up. Anything commanding this robot for long enough to
# matter needs a cost on it, because the hardware will derate and then stop.


def continuous_torque_excess(torques) -> list[float]:
    """How far past the thermal rating each joint is, in Nm, never negative.

    Takes any iterable of applied torques and returns a plain list, so that it
    works the same on a numpy array inside Isaac Sim and on six floats out of a
    log. The framework-specific reward term wrapping this lives with the
    framework.
    """
    return [max(abs(float(t)) - CONTINUOUS_TORQUE_NM, 0.0) for t in torques]
