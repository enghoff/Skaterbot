r"""Put the rigged robot on a floor in Isaac Sim, and measure what it does.

    run.py --check      # headless, measures the rig and prints PASS/FAIL
    run.py              # a window, and it falls over
    run.py --balance    # legs frozen, balancing on its wheels, and it stays up

Run it with Isaac Sim's own Python and pass -u, because Kit shuts the process
down hard enough to discard buffered stdout:

    Z:\IsaacSim\venv\Scripts\python.exe -u simulation/isaacsim/run.py --check

It needs simulation/isaacsim/usd/wheeled_biped/wheeled_biped.usda, which
`import_urdf.py` writes.

WHY --check EXISTS. This project's rule is that execution is not evidence: a
boolean the engine accepts can still have built the wrong solid, and the same
is true of a physics import. Isaac Sim will happily simulate a robot whose
wheels are the wrong radius, whose joints turn the wrong way, or whose armature
never arrived, and none of that shows up as an error. So --check does not ask
whether the robot loads. It measures five things the rig has to get right and
compares each with what the CAD says:

  1. THE JOINTS ARE THERE. All six, by name, with the travel the URDF declares.
  2. THE ARMATURE ARRIVED. Read back out of PhysX rather than assumed, because
     the reflected rotor inertia is the setting most likely to be dropped in
     silence and the one that does the most damage when it is.
  3. THE SIGNS ARE RIGHT. Positive hip flexion must swing the leg FORWARD and
     positive knee flexion must fold the shin BACK, because that is the
     convention pose_check.kcl and squat_check.kcl are written in and a policy
     trained against a flipped joint is worthless on hardware. It drives each
     joint and looks at where the wheel ends up.
  4. THE WHEEL IS 40 mm. Dropped on the floor with its legs locked straight,
     the robot must settle with base_link at the height the CAD says. This is
     the check that catches a cylinder collider PhysX decided to approximate:
     a convex hull of a cylinder stands a little lower than the cylinder does.
  5. IT ROLLS ON 40 mm. Driven gently enough not to slip, ground covered
     divided by wheel angle turned is the rolling radius, and it must be the
     same 40 mm. The static check can be fooled by a squashed contact; this one
     cannot.

WHAT IT DOES NOT DO. It does not tell you the robot is right, only that it is
the robot the CAD describes. Whether THAT robot can balance is a question about
the design, and --balance is what asks it.

--BALANCE. Freezes the hips and knees, reducing the robot to the wheeled
inverted pendulum balance.py derives from the URDF, and holds it up on wheel
torque alone with LQR gains computed from that model. It shoves the robot at
2 s to see it recover, and it FAILS if the robot falls -- unlike every other
mode here, staying up is the point.

The controller reads body pitch and pitch rate, which is an IMU, and wheel
angle and rate, which is the actuator's own encoder. It never asks the
simulator where the robot is, so the same law would run on the hardware.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIMULATION = HERE.parent
for path in (str(SIMULATION), str(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="run the rig checks and exit"
    )
    parser.add_argument(
        "--balance",
        action="store_true",
        help="freeze the hips and knees and balance on the wheels, using the"
        " LQR gains balance.py derives from the URDF. Fails if it falls.",
    )
    parser.add_argument(
        "--hold",
        action="store_true",
        help="lock the legs straight and let the wheels run free, so the robot"
        " falls as one rigid body. Useful for watching contact behave.",
    )
    parser.add_argument("--seconds", type=float, default=10.0, help="how long to run")
    parser.add_argument("--headless", action="store_true", help="no window")
    parser.add_argument(
        "--usd", type=Path, default=None, help="a different robot USD to load"
    )
    parser.add_argument(
        "--allow-stale",
        action="store_true",
        help="load the USD even when the URDF it was built from has moved"
        " since. build_urdf.py carries the same escape for the same reason.",
    )
    return parser.parse_args()


ARGS = parse_args()
HEADLESS = ARGS.headless or ARGS.check

# plant.py is standard library only, so it is safe to import before Isaac Sim
# has been started -- and it carries the message for when Isaac Sim is missing.
import plant  # noqa: E402

try:
    from isaacsim import SimulationApp
except ImportError:
    try:  # Isaac Sim 4.0 and earlier
        from omni.isaac.kit import SimulationApp  # type: ignore
    except ImportError:
        # Report the FIRST failure, not the fallback's. Left to itself this
        # raises "No module named 'omni'", which sends the reader looking for
        # an Omniverse package rather than for the right interpreter.
        raise SystemExit(
            plant.needs_isaac_python("simulation/isaacsim/run.py")
        ) from None

simulation_app = SimulationApp({"headless": HEADLESS})

import numpy as np  # noqa: E402
from pxr import Sdf, UsdPhysics  # noqa: E402

# --------------------------------------------------------------------------
# The core API was renamed at Isaac Sim 4.5 -- omni.isaac.core became
# isaacsim.core -- and the single-prim wrappers were renamed with it. Resolving
# by trying, rather than by version-sniffing, keeps this working on both and
# says plainly which one it found.


def resolve(candidates: list[tuple[str, str]], what: str):
    import importlib

    for module_name, attribute in candidates:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        found = getattr(module, attribute, None)
        if found is not None:
            return found, f"{module_name}.{attribute}"
    raise RuntimeError(
        f"could not find {what}. Tried: " + ", ".join(f"{m}.{a}" for m, a in candidates)
    )


World, world_from = resolve(
    [("isaacsim.core.api", "World"), ("omni.isaac.core", "World")], "World"
)
GroundPlane, ground_from = resolve(
    [
        ("isaacsim.core.api.objects", "GroundPlane"),
        ("omni.isaac.core.objects", "GroundPlane"),
    ],
    "GroundPlane",
)
PhysicsMaterial, material_from = resolve(
    [
        ("isaacsim.core.api.materials", "PhysicsMaterial"),
        ("omni.isaac.core.materials", "PhysicsMaterial"),
    ],
    "PhysicsMaterial",
)
Articulation, articulation_from = resolve(
    [
        ("isaacsim.core.prims", "SingleArticulation"),
        ("omni.isaac.core.articulations", "Articulation"),
    ],
    "a single-articulation wrapper",
)
add_reference_to_stage, stage_from = resolve(
    [
        ("isaacsim.core.utils.stage", "add_reference_to_stage"),
        ("omni.isaac.core.utils.stage", "add_reference_to_stage"),
    ],
    "add_reference_to_stage",
)

ROBOT_PATH = "/World/Robot"
GROUND_PATH = "/World/GroundPlane"


# --------------------------------------------------------------------------


class LinkProbe:
    """Where PhysX actually has a link, asked of the articulation itself.

    Wrapping the link in a SingleRigidPrim looks like the obvious way to do
    this and is a trap: creating a rigid-body tensor view over a prim that is
    already part of an articulation view INVALIDATES the articulation's view,
    and the run then dies at the next step with the wheel's collider reported
    as deleted. It cost a debugging pass to find, so it is written down here.

    The articulation already knows where its own links are. This is the tensor
    API Isaac Lab uses for the same job; it is reached through a private
    attribute only because the single-articulation wrapper does not re-export
    it.
    """

    def __init__(self, robot, name: str) -> None:
        self._view = robot._articulation_view._physics_view
        self._name = name
        self.index = self._view.get_metatype(0).link_indices[name]

    def position(self) -> np.ndarray:
        """The link's world position in metres. Transforms are x y z qx qy qz qw."""
        data = self._view.get_link_transforms()
        array = data.numpy() if hasattr(data, "numpy") else np.asarray(data)
        return np.asarray(array).reshape(-1, 7)[self.index, :3]


def pitch_of(orientation) -> float:
    """Body lean in radians from a wxyz quaternion, FORWARD positive.

    A positive rotation about +Y tilts the forward axis downward, so a positive
    value here is the robot leaning forward, towards +X. balance.py's model
    uses the same sense, and the sign of the whole control law rests on it.
    """
    w, x, y, z = (float(v) for v in orientation)
    sin_pitch = 2.0 * (w * y - z * x)
    return math.asin(max(-1.0, min(1.0, sin_pitch)))


def lock_legs(stage, stiffness_per_degree: float = 8.0, damping: float = 0.8) -> None:
    """Give the four leg joints a position drive, so the robot stands rigid.

    The rig is torque-controlled everywhere -- that is what a DM-J3507 in MIT
    mode is -- which means a robot left alone folds up under its own weight
    before anything about its wheels can be measured. Locking the legs is a
    property of the TEST, not of the robot, so it is done here and never in
    import_urdf.py.

    USD states angular drive gains per DEGREE, not per radian.
    """
    for prim in stage.Traverse():
        if not prim.IsA(UsdPhysics.RevoluteJoint):
            continue
        if prim.GetName() not in plant.LEG_JOINTS:
            continue
        drive = UsdPhysics.DriveAPI.Get(prim, "angular")
        if not drive:
            drive = UsdPhysics.DriveAPI.Apply(prim, "angular")
        drive.CreateStiffnessAttr().Set(float(stiffness_per_degree))
        drive.CreateDampingAttr().Set(float(damping))
        drive.CreateTargetPositionAttr().Set(0.0)


def find_prim_path(stage, name: str, api=None) -> str:
    """Where a named prim ended up, rather than where we assumed it would.

    The 6.0 importer nests the robot -- base_link sits under a Geometry scope
    and each link under its parent link, so wheel_right is five levels down --
    and it puts the articulation root on base_link rather than on the prim the
    reference is anchored at. Hardcoding any of that would break the first time
    the importer reorganised its output, so nothing here does.
    """
    for prim in stage.Traverse():
        if not str(prim.GetPath()).startswith(ROBOT_PATH):
            continue
        if api is not None and not prim.HasAPI(api):
            continue
        if name is None or prim.GetName() == name:
            return str(prim.GetPath())
    raise RuntimeError(f"no prim named {name!r} under {ROBOT_PATH}")


def attach_gantry(stage, base_path: str) -> None:
    """A world joint that lets the robot slide along the floor but not tip.

    This robot is an inverted pendulum. Released on its wheels with no
    controller it is on its side in about a second -- which is correct, and
    useless for measuring anything: a settled height read off a fallen robot
    says nothing about its wheels, and the first run of this check duly
    reported an 89 degree torso pitch and a 25 mm rolling radius.

    So the two measuring checks run the robot on a gantry: free to translate in
    any direction, locked against rotation. Like locking the legs, it is a
    property of the TEST and never of the robot, and nothing outside --check
    ever sees it.

    A generic UsdPhysics.Joint is free in all six degrees of freedom until an
    axis is limited, and an axis whose low limit is above its high limit is
    locked. Excluding it from the articulation matters: left included, PhysX
    would treat it as the articulation's root joint and give the robot a fixed
    base instead of a constrained free one.
    """
    joint = UsdPhysics.Joint.Define(stage, Sdf.Path("/World/Gantry"))
    joint.CreateBody1Rel().SetTargets([Sdf.Path(base_path)])
    joint.CreateExcludeFromArticulationAttr().Set(True)
    for axis in ("rotX", "rotY", "rotZ"):
        limit = UsdPhysics.LimitAPI.Apply(joint.GetPrim(), axis)
        limit.CreateLowAttr().Set(1.0)
        limit.CreateHighAttr().Set(-1.0)


def build_world(usd_path: Path, lock: bool, gantry: bool = False):
    world = World(
        stage_units_in_meters=1.0,
        physics_dt=plant.PHYSICS_DT,
        rendering_dt=plant.RENDER_DT,
    )

    # The floor the wheels stand on. GroundPlane takes a material object rather
    # than friction numbers, and this is the same urethane-on-floor guess the
    # wheels themselves carry -- see plant.CONTACT.
    ground_material = PhysicsMaterial(
        prim_path="/World/PhysicsMaterials/ground",
        name="ground_material",
        static_friction=plant.CONTACT["static_friction"],
        dynamic_friction=plant.CONTACT["dynamic_friction"],
        restitution=plant.CONTACT["restitution"],
    )
    GroundPlane(
        prim_path=GROUND_PATH,
        name="ground",
        z_position=0.0,
        physics_material=ground_material,
    )

    if not HEADLESS:
        try:
            from isaacsim.core.utils.prims import create_prim
        except ImportError:
            from omni.isaac.core.utils.prims import create_prim  # type: ignore
        create_prim(
            "/World/DomeLight",
            "DomeLight",
            attributes={"inputs:intensity": 1200.0},
        )

    add_reference_to_stage(usd_path=str(usd_path), prim_path=ROBOT_PATH)

    import omni.usd

    stage = omni.usd.get_context().get_stage()
    root_path = find_prim_path(stage, None, api=UsdPhysics.ArticulationRootAPI)
    print(f"articulation root   {root_path}")

    if lock:
        lock_legs(stage)
    if gantry:
        attach_gantry(stage, root_path)
        print("on a gantry: free to slide, locked against tipping -- a test fixture")

    robot = Articulation(
        prim_path=root_path,
        name=plant.ROBOT_NAME,
        position=np.array([0.0, 0.0, plant.spawn_height_m()]),
    )
    world.scene.add(robot)
    world.reset()

    # A handle on the right wheel, because two of the checks ask where it
    # actually is. Built after the reset, when the articulation's view exists.
    wheel = LinkProbe(robot, "wheel_right")
    print(f"right wheel         link {wheel.index} of the articulation")
    return world, robot, wheel


def dof_index(robot, name: str) -> int:
    names = list(robot.dof_names)
    if name not in names:
        raise KeyError(f"{name} is not a degree of freedom. Isaac has: {names}")
    return names.index(name)


def settle(world, steps: int) -> None:
    for _ in range(steps):
        world.step(render=not HEADLESS)


# --------------------------------------------------------------------------
# The checks


def check_joints(robot, problems: list[str]) -> None:
    """All six, by name."""
    names = set(robot.dof_names)
    missing = [name for name in plant.JOINT_ORDER if name not in names]
    extra = sorted(names - set(plant.JOINT_ORDER))
    if missing:
        problems.append(f"degrees of freedom missing from the articulation: {missing}")
    if extra:
        problems.append(f"the articulation has joints the CAD does not: {extra}")

    print(f"  Isaac reports {len(names)} degrees of freedom, in its own order:")
    print(f"    {list(robot.dof_names)}")


def check_signs(world, robot, wheel, problems: list[str]) -> None:
    """Positive hip flexion goes forward; positive knee flexion folds back.

    Driven kinematically rather than by torque, because the question is about
    the axis the importer built, not about the dynamics. The wheel is the point
    furthest down the chain, so it shows the sign most clearly.
    """

    def wheel_x_at(**angles) -> float:
        positions = np.zeros(robot.num_dof)
        for name, value in angles.items():
            positions[dof_index(robot, name)] = value
        robot.set_joint_positions(positions)
        robot.set_joint_velocities(np.zeros(robot.num_dof))
        world.step(render=False)
        return float(wheel.position()[0])

    neutral = wheel_x_at()
    hip_flexed = wheel_x_at(hip_pitch_right=0.30)
    knee_flexed = wheel_x_at(knee_right=0.30)

    hip_delta = hip_flexed - neutral
    knee_delta = knee_flexed - neutral

    print(f"  neutral, the wheel sits at x = {neutral * 1000:+.1f} mm")
    print(
        f"  hip_pitch_right +17 deg moves it {hip_delta * 1000:+.1f} mm (forward is +)"
    )
    print(f"  knee_right      +17 deg moves it {knee_delta * 1000:+.1f} mm (back is -)")

    if hip_delta <= 1e-3:
        problems.append(
            f"positive hip flexion moves the leg {hip_delta * 1000:+.1f} mm, but the CAD's"
            " convention is that it swings FORWARD. The hip axis is flipped."
        )
    if knee_delta >= -1e-3:
        problems.append(
            f"positive knee flexion moves the shin {knee_delta * 1000:+.1f} mm, but the CAD's"
            " convention is that it folds BACK. The knee axis is flipped."
        )

    robot.set_joint_positions(np.zeros(robot.num_dof))
    robot.set_joint_velocities(np.zeros(robot.num_dof))


def check_standing_height(world, robot, problems: list[str]) -> float:
    """Dropped with its legs locked, does it stand where the CAD says?"""
    robot.set_world_pose(
        position=np.array([0.0, 0.0, plant.spawn_height_m()]),
        orientation=np.array([1.0, 0.0, 0.0, 0.0]),
    )
    robot.set_joint_positions(np.zeros(robot.num_dof))
    robot.set_joint_velocities(np.zeros(robot.num_dof))

    settle(world, int(1.5 / plant.PHYSICS_DT))

    position, orientation = robot.get_world_pose()
    height = float(position[2])
    expected = plant.standing_base_height_m()
    error = height - expected
    tilt = math.degrees(pitch_of(orientation))

    print(f"  settles with base_link at {height * 1000:.1f} mm")
    print(
        f"  the CAD says it should be  {expected * 1000:.1f} mm  ({error * 1000:+.1f} mm)"
    )
    print(f"  torso pitch after settling {tilt:+.1f} deg")

    # A millimetre is generous for a rigid contact and tight enough to catch a
    # cylinder PhysX quietly replaced with a hull or a capsule.
    if abs(error) > 0.001:
        problems.append(
            f"the robot stands {error * 1000:+.1f} mm off the height the CAD gives it."
            " The wheel collider is not the 40 mm cylinder it is meant to be --"
            " check whether PhysX approximated it."
        )
    return height


def check_rolling_radius(world, robot, wheel, problems: list[str]) -> None:
    """Ground covered per radian turned, which has to be the wheel's radius.

    Driven at a torque well under what the contact can hold, so the wheel rolls
    rather than slips: with the robot's weight over two wheels and a friction
    coefficient near one, slip needs about 0.3 Nm and this uses 0.08.
    """
    torque = 0.08
    radius = plant.wheel_radius_m()

    robot.set_world_pose(
        position=np.array([0.0, 0.0, plant.spawn_height_m()]),
        orientation=np.array([1.0, 0.0, 0.0, 0.0]),
    )
    robot.set_joint_positions(np.zeros(robot.num_dof))
    robot.set_joint_velocities(np.zeros(robot.num_dof))
    settle(world, int(1.0 / plant.PHYSICS_DT))

    index = dof_index(robot, "wheel_drive_right")

    efforts = np.zeros(robot.num_dof)
    for name in plant.WHEEL_JOINTS:
        efforts[dof_index(robot, name)] = torque

    start_x = float(wheel.position()[0])

    # THE WHEEL ANGLE WRAPS. wheel_drive_* is a continuous joint, so PhysX
    # reports its position folded into [-pi, pi]: a wheel that has turned 11.5
    # radians reads as -1.1, and the rolling radius comes out negative and
    # absurd. Accumulate the per-step difference instead, folding each one into
    # [-pi, pi] rather than the total. At the actuator's 48 rad/s a 2.5 ms step
    # turns 0.12 rad, so a step can never be mistaken for a wrap.
    previous = float(robot.get_joint_positions()[index])
    turned = 0.0

    for _ in range(int(0.8 / plant.PHYSICS_DT)):
        robot.set_joint_efforts(efforts)
        world.step(render=False)
        current = float(robot.get_joint_positions()[index])
        step = (current - previous + math.pi) % (2.0 * math.pi) - math.pi
        turned += step
        previous = current

    travelled = float(wheel.position()[0]) - start_x

    robot.set_joint_efforts(np.zeros(robot.num_dof))

    print(f"  {torque:.2f} Nm on each wheel for 0.8 s")
    print(
        f"  the wheel turned {turned:+.3f} rad and travelled {travelled * 1000:+.1f} mm"
    )

    if abs(turned) < 0.05:
        problems.append(
            f"the wheels barely turned ({turned:+.3f} rad) under {torque} Nm."
            " Either the drive is not in torque mode or something is holding them."
        )
        return

    measured = travelled / turned
    print(
        f"  so it rolls on a radius of {measured * 1000:.1f} mm, against the CAD's {radius * 1000:.1f} mm"
    )

    if measured < 0:
        problems.append(
            "a positive wheel torque drove the robot BACKWARDS. The CAD's convention"
            " is that a positive wheel angle rolls it forward; the wheel axis is flipped."
        )
        return
    # Some slip is real and expected; a wrong collider is not a few per cent.
    if abs(measured - radius) / radius > 0.05:
        problems.append(
            f"the effective rolling radius is {measured * 1000:.1f} mm, more than 5% off the"
            f" CAD's {radius * 1000:.1f} mm. Either the wheel collider is the wrong shape or"
            " the wheels are slipping, and neither is something to train against."
        )


def check_armature(robot, problems: list[str]) -> None:
    """Did the reflected rotor inertia actually reach PhysX?

    It is the setting most likely to be silently dropped and the one that does
    the most damage if it is: 7:1 puts about 2.3e-4 kg m2 at each joint, which
    is several times the wheel's own spin inertia.
    """
    # The single-articulation wrapper does not expose get_armatures; the
    # batched view it wraps does. Reaching for the private view is worth it
    # here: reporting "not verified" for the one setting most likely to be
    # silently dropped would leave the check almost pointless.
    getter = getattr(robot, "get_armatures", None)
    if not callable(getter):
        view = getattr(robot, "_articulation_view", None)
        getter = getattr(view, "get_armatures", None)
    if not callable(getter):
        print("  this Isaac Sim build exposes no armature readback -- NOT VERIFIED")
        return
    try:
        armatures = np.asarray(getter()).reshape(-1)
    except Exception as exc:  # noqa: BLE001
        print(f"  armature readback failed ({exc}) -- NOT VERIFIED")
        return

    expected = plant.ARMATURE_KG_M2
    for name in plant.JOINT_ORDER:
        value = float(armatures[dof_index(robot, name)])
        if abs(value - expected) > 1e-9:
            problems.append(
                f"{name} has armature {value:.3e} kg m2, not the {expected:.3e} the"
                " actuator's 7:1 reduction reflects to the joint."
            )
    print(f"  all six joints carry {expected:.3e} kg m2 of reflected rotor inertia")


def run_checks(world, robot, wheel) -> int:
    problems: list[str] = []

    print("\n1. the joints")
    check_joints(robot, problems)

    print("\n2. armature")
    check_armature(robot, problems)

    print("\n3. joint signs, against the CAD's own convention")
    check_signs(world, robot, wheel, problems)

    print("\n4. standing height, dropped with the legs locked")
    check_standing_height(world, robot, problems)

    print("\n5. rolling radius, measured")
    check_rolling_radius(world, robot, wheel, problems)

    print()
    if problems:
        print(f"RIG CHECK FAILED, {len(problems)} problem(s)")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("RIG CHECK PASSED.")
    print("The robot Isaac Sim is simulating is the robot the CAD describes.")
    print("Whether it can balance is a different question, and four of the numbers")
    print("it turns on have never been measured -- see simulation/README.md.")
    return 0


# --------------------------------------------------------------------------
# Watching it


def run_balance(
    world, robot, seconds: float, shove_at: float = 2.0, shove_m_s: float = 0.3
) -> int:
    """Balance the robot on its wheels, legs frozen, and shove it to see.

    The legs are locked straight, so this is the wheeled inverted pendulum
    balance.py derives from the URDF, driven by the LQR gains it computes. The
    controller reads body pitch and pitch rate -- an IMU -- and wheel angle and
    rate -- the actuator's own encoder. It never asks the simulator where the
    robot is, so the same law would run on the hardware.

    Falling over is a failure here, unlike everywhere else in this file.
    """
    import balance

    pendulum = balance.pendulum()
    radius = pendulum.radius

    # Clamp at TRACTION, not at the actuator's peak. Past mu m g the wheels
    # slip, and a slipping wheel makes less force than a gripping one, so
    # asking for more than this actively loses the robot -- which is exactly
    # how the first version of this fell over.
    ceiling = min(plant.PEAK_TORQUE_NM, balance.traction_limit_nm(pendulum) / 2.0)

    wheel_indices = [dof_index(robot, name) for name in plant.WHEEL_JOINTS]
    efforts = np.zeros(robot.num_dof)

    print(
        f"  CoM {pendulum.com_height * 1000:.0f} mm above the axle, so it falls with a"
    )
    unstable = [
        v.real
        for v in np.linalg.eigvals(balance.state_space(pendulum)[0])
        if v.real > 0
    ]
    print(
        f"  {1000.0 / max(unstable):.0f} ms time constant. Control runs every"
        f" {plant.PHYSICS_DT * 1000:.1f} ms."
    )
    print(
        f"  torque ceiling {ceiling:.2f} Nm a wheel, which is traction, not the actuator"
    )
    print(f"  a {shove_m_s:.1f} m/s shove goes in at t = {shove_at:.0f} s\n")

    # The wheel angle wraps, the same as in the rolling check, so it is
    # accumulated rather than read.
    previous_angle = float(np.mean(robot.get_joint_positions()[wheel_indices]))
    spun = 0.0

    steps = int(seconds / plant.PHYSICS_DT)
    peak, squared, over_thermal, shoved = 0.0, 0.0, 0, False

    for step in range(steps):
        now = step * plant.PHYSICS_DT

        _, orientation = robot.get_world_pose()
        lean = pitch_of(orientation)
        lean_rate = float(robot.get_angular_velocity()[1])

        angle = float(np.mean(robot.get_joint_positions()[wheel_indices]))
        spun += (angle - previous_angle + math.pi) % (2.0 * math.pi) - math.pi
        previous_angle = angle
        spin_rate = float(np.mean(robot.get_joint_velocities()[wheel_indices]))

        # Ground position and speed of the contact patch, from the wheel angle
        # relative to the body plus the body's own lean.
        position = radius * (spun + lean)
        speed = radius * (spin_rate + lean_rate)

        total = balance.torque([position, lean, speed, lean_rate])
        per_wheel = float(np.clip(total / 2.0, -ceiling, ceiling))

        peak = max(peak, abs(per_wheel))
        squared += per_wheel * per_wheel
        over_thermal += abs(per_wheel) > plant.CONTINUOUS_TORQUE_NM

        efforts[:] = 0.0
        for index in wheel_indices:
            efforts[index] = per_wheel
        robot.set_joint_efforts(efforts)

        if not shoved and now >= shove_at:
            velocity = robot.get_linear_velocity()
            robot.set_linear_velocity(
                np.array([float(velocity[0]) + shove_m_s, 0.0, 0.0])
            )
            shoved = True
            print(f"  t={now:5.1f}s  SHOVED at {shove_m_s:.1f} m/s")

        world.step(render=not HEADLESS)

        if step % int(0.5 / plant.PHYSICS_DT) == 0:
            base, _ = robot.get_world_pose()
            print(
                f"  t={now:5.1f}s  lean {math.degrees(lean):+6.2f} deg"
                f"  ground {position * 1000:+7.1f} mm"
                f"  height {float(base[2]) * 1000:6.1f} mm"
                f"  torque {per_wheel:+5.2f} Nm"
            )

        if abs(lean) > math.radians(45.0):
            print(
                f"\n  FELL OVER at t = {now:.2f} s, {math.degrees(lean):+.0f} deg of lean"
            )
            return 1

    base, orientation = robot.get_world_pose()
    rms = math.sqrt(squared / steps)
    print(
        f"\n  upright after {seconds:.0f} s: lean {math.degrees(pitch_of(orientation)):+.2f} deg,"
        f" base at {float(base[2]) * 1000:.1f} mm"
    )
    print(f"  torque per wheel: peak {peak:.2f} Nm, rms {rms:.2f} Nm")
    print(
        f"  above the 0.8 Nm thermal rating for {100.0 * over_thermal / steps:.0f}% of the run,"
        f" and the 3.0 Nm peak was {'REACHED' if peak >= plant.PEAK_TORQUE_NM - 1e-6 else 'never reached'}"
    )
    return 0


def main() -> int:
    usd_path = ARGS.usd or plant.ROBOT_USD_PATH
    if not usd_path.exists():
        print(f"no robot USD at {usd_path}.")
        print(f"Build it first:  {plant.rebuild_command()}")
        return 1

    # A stale USD is the one failure in this pipeline that produces no error at
    # all: it loads, the rig checks pass, and every number describes the robot
    # as it was before the CAD moved. Refuse it the way build_urdf.py refuses a
    # stale mesh -- name what moved, print the fix, and stop.
    behind = plant.stale_usd(usd_path)
    if behind:
        print()
        print(f"STALE ROBOT USD: {usd_path.name} is older than what it was built from.")
        for name, age in behind:
            print(f"  {name} is newer by {age / 60.0:.1f} min")
        print()
        print(f"Rebuild it:  {plant.rebuild_command()}")
        print("or pass --allow-stale to simulate the USD as it stands.")
        if not ARGS.allow_stale:
            return 1
        print(
            "--allow-stale: going on anyway. The numbers below are NOT the current CAD."
        )

    print(f"World               {world_from}")
    print(f"Articulation        {articulation_from}")
    print(f"robot USD           {usd_path}")
    print(f"physics dt          {plant.PHYSICS_DT * 1000:.2f} ms")

    lock = ARGS.check or ARGS.hold or ARGS.balance
    world, robot, wheel = build_world(usd_path, lock=lock, gantry=ARGS.check)
    if lock:
        print(
            "legs locked straight by a position drive -- a property of the test, not the robot"
        )

    if ARGS.check:
        return run_checks(world, robot, wheel)

    if ARGS.balance:
        print("\nbalancing on the wheels alone, legs frozen straight.")
        return run_balance(world, robot, ARGS.seconds)

    print(
        f"\nrunning for {ARGS.seconds:.0f} s. With no controller it falls over, which is correct:"
    )
    print("this is an inverted pendulum with a two-joint leg under each wheel.")
    settle(world, int(ARGS.seconds / plant.PHYSICS_DT))
    position, orientation = robot.get_world_pose()
    print(
        f"  ended at {float(position[2]) * 1000:.0f} mm,"
        f" pitched {math.degrees(pitch_of(orientation)):+.0f} deg"
    )
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        simulation_app.close()
    raise SystemExit(code)
