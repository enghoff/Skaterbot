r"""Turn the URDF into a rigged USD robot Isaac Sim can simulate.

    Z:\IsaacSim\venv\Scripts\python.exe -u simulation/isaacsim/import_urdf.py

Run it with Isaac Sim's own Python, not the system one. It writes

    simulation/isaacsim/usd/wheeled_biped/wheeled_biped.usda

which is generated output: it is not tracked, and editing it by hand is always
wrong for the same reason editing the URDF is. Change the CAD, rebuild the URDF
with `/urdf`, and run this again.

WHICH ISAAC SIM. This is written for the 6.0 importer, `URDFImporter` and
`URDFImporterConfig`. The `URDFParseAndImportFile` kit command that earlier
releases used no longer exists, so this will not run on 5.x or below without
being rewritten back to it.

WHAT "RIGGING" MEANS HERE. The importer gives back the mechanism -- links,
masses, inertia tensors, joints, travel -- and only some of how it should be
simulated. The rest is this file's job:

  * every joint in TORQUE control, which is what a DM-J3507 in MIT mode is.
    Stiffness and damping are zero, so a command is a torque and nothing is
    quietly holding a position for you. The importer can do this much itself,
    and it is asked to;
  * the actuator's reflected rotor inertia as joint armature. On a 7:1
    reduction this is several times the wheel's own spin inertia, so without it
    the wheels are a different plant and no tuning recovers it. The importer
    has no setting for it at all;
  * a urethane friction material bound to the two wheel colliders, because
    those are the only things touching the floor;
  * solver counts, CCD and sleep thresholds.

None of those numbers are stated here. They come from plant.py, which reads
robot.py and the KCL, so this file cannot disagree with the Isaac Lab config
about what the robot is.

WHAT IT CHECKS BEFORE IT SAVES. That the robot PhysX built is the robot the
URDF describes: every link's mass, centre of mass and principal moments, and
every joint's travel, read back out of the USD and compared with the XML. A
mass that arrived as a density-derived guess instead of the URDF's own figure
is invisible until the robot behaves oddly.

WHAT IT CANNOT CHECK. Whether the wheel rolls on a 40 mm radius. USD says
"cylinder"; whether PhysX collides it as one is a runtime question, and
`run.py --check` is what measures it.
"""

from __future__ import annotations

import argparse
import math
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIMULATION = HERE.parent
for path in (str(SIMULATION), str(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-self-collision",
        action="store_true",
        help="import without self collision. Try this first if a fresh import"
        " jitters or refuses to settle at the knee's hard stop.",
    )
    parser.add_argument(
        "--asset-transformer",
        action="store_true",
        help="run Isaac Sim's asset transformer profile, which restructures the"
        " output into a layered package instead of one flat file.",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="show the Isaac Sim window while importing, for watching it go wrong",
    )
    return parser.parse_args()


ARGS = parse_args()

# plant.py is standard library only, so it is safe to import before Isaac Sim
# has been started -- and it carries the message for when Isaac Sim is missing.
import plant  # noqa: E402

# SimulationApp has to be constructed before anything else from Isaac Sim or
# Omniverse is imported. Nothing above this line may touch either.
try:
    from isaacsim import SimulationApp
except ImportError:
    raise SystemExit(plant.needs_isaac_python("simulation/isaacsim/import_urdf.py")) from None

simulation_app = SimulationApp({"headless": not ARGS.gui})

from isaacsim.asset.importer.urdf import URDFImporter, URDFImporterConfig  # noqa: E402
from pxr import PhysxSchema, Sdf, Usd, UsdPhysics, UsdShade  # noqa: E402


# --------------------------------------------------------------------------
# The import


def import_urdf(urdf_path: Path, self_collision: bool) -> Path:
    """Convert the URDF to USD and hand back the file the importer wrote.

    The importer takes an output DIRECTORY and picks the filename itself, and
    it refuses to overwrite -- given a directory that is already there it
    invents a numbered one beside it. So the old one is cleared first, and the
    build stays repeatable instead of growing wheeled_biped_01, _02, _03.
    """
    output_root = plant.USD_DIR
    stale = output_root / plant.ROBOT_NAME
    if stale.exists():
        shutil.rmtree(stale)
    output_root.mkdir(parents=True, exist_ok=True)

    config = URDFImporterConfig(
        urdf_path=str(urdf_path),
        usd_path=str(output_root),
        # A floating base: this robot balances, it does not hang.
        fix_base=False,
        # Every joint in this URDF is actuated, so there is nothing to merge.
        merge_fixed_joints=False,
        merge_mesh=False,
        # The URDF's collisions are already primitives -- boxes and two
        # cylinders -- so there is nothing to build out of the visuals.
        collision_from_visuals=False,
        allow_self_collision=self_collision,
        # TORQUE CONTROL. "force" with a target type of "none" and no gains is
        # what makes a command a torque rather than a position request. Left at
        # the importer's default the joints arrive with a position drive, and a
        # robot quietly holding its own pose looks like it balances.
        joint_drive_type="force",
        joint_target_type="none",
        override_joint_stiffness=0.0,
        override_joint_damping=float(plant.JOINT_DAMPING_NM_S_RAD),
        # No density override: the URDF's masses are the mass budget's, and
        # they have to survive the trip.
        link_density=None,
        run_asset_transformer=ARGS.asset_transformer,
        run_multi_physics_conversion=True,
    )

    written = URDFImporter(config).import_urdf()
    return Path(written)


# --------------------------------------------------------------------------
# The rigging


def articulation_root(stage):
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            return prim
    return stage.GetDefaultPrim()


def joint_prims(stage) -> dict:
    return {
        prim.GetName(): prim
        for prim in stage.Traverse()
        if prim.IsA(UsdPhysics.RevoluteJoint)
    }


def link_prims(stage) -> dict:
    return {
        prim.GetName(): prim
        for prim in stage.Traverse()
        if prim.HasAPI(UsdPhysics.RigidBodyAPI)
    }


def rig_joints(joints: dict, notes: list[str]) -> list[tuple]:
    """Torque control, armature, friction and a velocity ceiling on every joint."""
    rows = []
    for name in plant.JOINT_ORDER:
        prim = joints.get(name)
        if prim is None:
            notes.append(f"MISSING JOINT {name} -- the URDF has it and the USD does not")
            continue

        drive = UsdPhysics.DriveAPI.Get(prim, "angular")
        if not drive:
            drive = UsdPhysics.DriveAPI.Apply(prim, "angular")
        drive.CreateTypeAttr().Set("force")
        drive.CreateStiffnessAttr().Set(0.0)
        drive.CreateDampingAttr().Set(float(plant.JOINT_DAMPING_NM_S_RAD))
        drive.CreateMaxForceAttr().Set(float(plant.PEAK_TORQUE_NM))
        drive.CreateTargetPositionAttr().Set(0.0)
        drive.CreateTargetVelocityAttr().Set(0.0)

        # The reflected rotor inertia. The single most consequential number in
        # this rig, and the one the importer has no opinion about.
        physx_joint = PhysxSchema.PhysxJointAPI.Apply(prim)
        physx_joint.CreateArmatureAttr().Set(float(plant.ARMATURE_KG_M2))
        physx_joint.CreateJointFrictionAttr().Set(float(plant.JOINT_FRICTION_NM))
        # PhysX states this one in degrees per second.
        physx_joint.CreateMaxJointVelocityAttr().Set(
            float(math.degrees(plant.MAX_VELOCITY_RAD_S))
        )

        rows.append(
            (name, float(plant.PEAK_TORQUE_NM), float(plant.ARMATURE_KG_M2),
             float(plant.JOINT_FRICTION_NM))
        )
    return rows


def rig_articulation(root) -> None:
    api = PhysxSchema.PhysxArticulationAPI.Apply(root)
    api.CreateSolverPositionIterationCountAttr().Set(int(plant.SOLVER["position_iterations"]))
    api.CreateSolverVelocityIterationCountAttr().Set(int(plant.SOLVER["velocity_iterations"]))
    api.CreateEnabledSelfCollisionsAttr().Set(bool(plant.SELF_COLLISION))
    # A balancing robot that falls asleep is one that has fallen over.
    api.CreateSleepThresholdAttr().Set(float(plant.SOLVER["sleep_threshold"]))
    api.CreateStabilizationThresholdAttr().Set(float(plant.SOLVER["stabilization_threshold"]))


def rig_bodies(links: dict) -> None:
    for prim in links.values():
        api = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        api.CreateDisableGravityAttr().Set(False)
        api.CreateEnableCCDAttr().Set(bool(plant.SOLVER["enable_ccd"]))
        api.CreateMaxDepenetrationVelocityAttr().Set(
            float(plant.SOLVER["max_depenetration_velocity"])
        )
        api.CreateSleepThresholdAttr().Set(float(plant.SOLVER["sleep_threshold"]))


def rig_wheel_contact(stage, root, notes: list[str]) -> list[str]:
    """Bind a urethane friction material to the two wheel colliders.

    They are the only things on this robot that touch the floor, so this is the
    whole of its contact with the world. Every number in it is a guess -- see
    plant.CONTACT -- which is the argument for randomising over it rather than
    for tuning it.
    """
    material_path = root.GetPath().AppendChild("PhysicsMaterials").AppendChild("urethane")
    material = UsdShade.Material.Define(stage, material_path)
    prim = material.GetPrim()

    physics_material = UsdPhysics.MaterialAPI.Apply(prim)
    physics_material.CreateStaticFrictionAttr().Set(float(plant.CONTACT["static_friction"]))
    physics_material.CreateDynamicFrictionAttr().Set(float(plant.CONTACT["dynamic_friction"]))
    physics_material.CreateRestitutionAttr().Set(float(plant.CONTACT["restitution"]))

    physx_material = PhysxSchema.PhysxMaterialAPI.Apply(prim)
    # Take the lower of the two surfaces' friction rather than averaging, so a
    # slippery floor stays slippery whatever the wheel claims.
    physx_material.CreateFrictionCombineModeAttr().Set("min")

    bound = []
    for candidate in stage.Traverse():
        path = str(candidate.GetPath())
        if "wheel_left" not in path and "wheel_right" not in path:
            continue
        if not candidate.HasAPI(UsdPhysics.CollisionAPI):
            continue
        UsdShade.MaterialBindingAPI.Apply(candidate).Bind(
            material, UsdShade.Tokens.weakerThanDescendants, "physics"
        )
        bound.append(path)

    if len(bound) != 2:
        notes.append(
            f"expected to bind the wheel material to 2 colliders, bound {len(bound)}: {bound}"
        )
    return bound


# --------------------------------------------------------------------------
# Reading the robot back out of the USD and comparing it with the URDF


def urdf_facts(urdf_path: Path) -> tuple[dict, dict]:
    import numpy as np

    root = ET.parse(urdf_path).getroot()

    links = {}
    for link in root.findall("link"):
        inertial = link.find("inertial")
        if inertial is None:
            continue
        i = inertial.find("inertia")
        tensor = np.array(
            [
                [float(i.get("ixx")), float(i.get("ixy")), float(i.get("ixz"))],
                [float(i.get("ixy")), float(i.get("iyy")), float(i.get("iyz"))],
                [float(i.get("ixz")), float(i.get("iyz")), float(i.get("izz"))],
            ]
        )
        links[link.get("name")] = {
            "mass": float(inertial.find("mass").get("value")),
            "com": [float(v) for v in inertial.find("origin").get("xyz").split()],
            "moments": sorted(float(v) for v in np.linalg.eigvalsh(tensor)),
        }

    joints = {}
    for joint in root.findall("joint"):
        limit = joint.find("limit")
        joints[joint.get("name")] = {
            "type": joint.get("type"),
            "lower": None if limit.get("lower") is None else float(limit.get("lower")),
            "upper": None if limit.get("upper") is None else float(limit.get("upper")),
        }
    return links, joints


def compare(links, joints, urdf_links, urdf_joints) -> list[str]:
    """Did the importer give back the robot the URDF describes?"""
    problems = []

    for name, expected in urdf_links.items():
        prim = links.get(name)
        if prim is None:
            problems.append(f"link {name} is in the URDF and not in the USD")
            continue
        mass_api = UsdPhysics.MassAPI(prim)

        mass = mass_api.GetMassAttr().Get()
        if mass is None or abs(float(mass) - expected["mass"]) > 1e-6:
            problems.append(
                f"{name}: USD mass {mass} kg, URDF says {expected['mass']:.6f} kg"
            )

        com = mass_api.GetCenterOfMassAttr().Get()
        if com is not None:
            offset = max(abs(float(com[i]) - expected["com"][i]) for i in range(3))
            if offset > 1e-5:
                problems.append(
                    f"{name}: centre of mass off by {offset * 1000:.2f} mm from the URDF"
                )

        diagonal = mass_api.GetDiagonalInertiaAttr().Get()
        if diagonal is not None and any(float(v) != 0.0 for v in diagonal):
            got = sorted(float(v) for v in diagonal)
            want = expected["moments"]
            relative = max(abs(g - w) / max(w, 1e-12) for g, w in zip(got, want, strict=True))
            if relative > 1e-3:
                problems.append(
                    f"{name}: principal moments differ from the URDF by {relative * 100:.1f}%."
                    f" USD {['%.3e' % v for v in got]}, URDF {['%.3e' % v for v in want]}"
                )

    for name, expected in urdf_joints.items():
        prim = joints.get(name)
        if prim is None:
            problems.append(f"joint {name} is in the URDF and not in the USD")
            continue
        if expected["lower"] is None:
            continue
        revolute = UsdPhysics.RevoluteJoint(prim)
        # USD states angular limits in DEGREES; the URDF states them in radians.
        for label, attribute, radians in (
            ("lower", revolute.GetLowerLimitAttr(), expected["lower"]),
            ("upper", revolute.GetUpperLimitAttr(), expected["upper"]),
        ):
            value = attribute.Get()
            if value is None:
                problems.append(f"joint {name} has no {label} limit in the USD")
                continue
            if abs(float(value) - math.degrees(radians)) > 1e-3:
                problems.append(
                    f"joint {name}: USD {label} limit {float(value):.3f} deg,"
                    f" URDF says {math.degrees(radians):.3f} deg"
                )

    return problems


# --------------------------------------------------------------------------


def main() -> int:
    urdf_path = plant.URDF_PATH
    if not urdf_path.exists():
        print(f"no URDF at {urdf_path}. Run `uv run simulation/build_urdf.py` first.")
        return 1

    self_collision = plant.SELF_COLLISION and not ARGS.no_self_collision
    print(f"URDF:               {urdf_path}")
    print(f"self collision:     {'on' if self_collision else 'OFF (--no-self-collision)'}")

    written = import_urdf(urdf_path, self_collision)
    print(f"importer wrote:     {written}")

    stage = Usd.Stage.Open(str(written))
    if stage is None:
        print(f"could not open the USD the importer wrote at {written}")
        return 1

    notes: list[str] = []
    joints = joint_prims(stage)
    links = link_prims(stage)
    root = articulation_root(stage)

    print(f"articulation root:  {root.GetPath()}")
    print(f"rigid bodies:       {sorted(links)}")
    print(f"revolute joints:    {sorted(joints)}\n")

    rows = rig_joints(joints, notes)
    rig_articulation(root)
    rig_bodies(links)
    bound = rig_wheel_contact(stage, root, notes)

    print("joints, rigged for torque control")
    print(f"  {'joint':<20} {'max Nm':>7} {'armature kg m2':>15} {'friction Nm':>12}")
    for name, effort, armature, friction in rows:
        print(f"  {name:<20} {effort:7.2f} {armature:15.3e} {friction:12.3f}")

    print("\nwheel contact material, every number of it a guess")
    for key, value in plant.CONTACT.items():
        print(f"  {key:<20} {value}")
    for path in bound:
        print(f"  bound to {path}")

    urdf_links, urdf_joints = urdf_facts(urdf_path)
    problems = compare(links, joints, urdf_links, urdf_joints)

    print("\nlinks, as PhysX now has them")
    print(f"  {'link':<14} {'mass kg':>9}")
    total = 0.0
    for name in urdf_links:
        prim = links.get(name)
        mass = UsdPhysics.MassAPI(prim).GetMassAttr().Get() if prim else None
        if mass is not None:
            total += float(mass)
        print(f"  {name:<14} {'--' if mass is None else f'{float(mass):9.4f}'}")
    print(f"  {'TOTAL':<14} {total:9.4f}")

    if notes:
        print("\nnotes from the rigging")
        for note in notes:
            print(f"  {note}")

    if problems:
        print(f"\nTHE USD DOES NOT MATCH THE URDF, {len(problems)} problem(s)")
        for problem in problems:
            print(f"  {problem}")
        print("\nSaved anyway so it can be looked at, but do not simulate this.")
        stage.Save()
        return 1

    stage.Save()
    print(f"\nsaved {written}")
    print("Mass, centre of mass, principal moments and travel all match the URDF.")
    print("What has NOT been shown is that the wheel rolls on a 40 mm radius.")
    print("Measure it:  run.py --check")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        simulation_app.close()
    raise SystemExit(code)
