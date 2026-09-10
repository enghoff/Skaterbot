"""The robot as a kinematic tree, with every gram accounted for and sourced.

cad/main.py is a scene: it places parts at absolute heights, and nothing in it
says which part turns about which axis or what hangs off what. This module is
where that is written down once. It is the only file in simulation/ that
carries engineering judgement; build_urdf.py and the Isaac Lab config are
mechanical translations of what is here.

WHERE THE NUMBERS COME FROM. Every dimension is read out of the CAD by
cad/dimensions.py, so the tree moves when the CAD moves. Every mass is either
measured off the exported mesh at PA12-CF density or taken from
tools/mass_budget.toml, which is the same table tools/mass.py rolls up against
the robot's 2 300 g ceiling. Nothing is typed in twice and nothing is invented:
where this file splits one of the budget's lump figures across several places
it keeps the lump's total, and says so in the `source` field.

READ THE `source` FIELD BEFORE TRUSTING A SIMULATION RESULT. It is not
decoration. About a third of this robot's mass has never been on a scale, and
check_model.py totals the mass by provenance precisely so that the size of that
third stays visible.

THE FRAME. Everything here is in the CAD's own frame -- +X is the robot's
right, +Y is forward, +Z is up, the convention tools/view.py names -- and
lengths are in millimetres. build_urdf.py does the single rotation into the
ROS convention a URDF wants, and the single conversion into metres, so that
both have exactly one place to go wrong.

WHICH PART BELONGS TO WHICH LINK. A limb print carries a diameter-36 output
disc at one end and a diameter-52 stator plate at the other (cad/limb.py). The
output disc bolts to the actuator that drives the limb; the stator plate bolts
to the REAR COVER of the next actuator down. So each limb carries the housing
of the joint below it, and that actuator's 150 g belongs to the limb rather
than to the segment it drives. The pelvis carries the two hip pitch housings
the same way, in the clevises rooted in its floor.
"""

from __future__ import annotations

import math
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cad.dimensions import load as load_dimensions  # noqa: E402

MESHES = Path(__file__).resolve().parent / "meshes"
BUDGET = ROOT / "tools" / "mass_budget.toml"

SIDES = ("right", "left")
# The CAD builds the robot mirror-symmetric about x = 0, so a side is a sign.
SIDE_SIGN = {"right": +1.0, "left": -1.0}


# --------------------------------------------------------------------------
# The actuator
#
# The torque figures are the project's own and are used throughout
# docs/PLAN.md. The rest is NOT. Everything marked unmeasured here has to come
# from DAMIAO or from a bench test before a policy trained against it means
# anything on hardware.

ACTUATOR = {
    "model": "DAMIAO DM-J3507-2EC",
    "gear_ratio": 7.0,  # docs/BOM.md
    "continuous_torque_nm": 0.8,  # docs/PLAN.md; a thermal limit, not a stop
    "peak_torque_nm": 3.0,  # docs/PLAN.md
    # UNMEASURED. No published no-load speed has been recorded in this project.
    # 20 rad/s at the output is a placeholder consistent with a 7:1 reduction on
    # a 24 V 3507; it decides the robot's top speed -- 0.8 m/s on a 80 mm wheel
    # -- and it must be replaced with the vendor figure.
    "max_velocity_rad_s": 20.0,
    # UNMEASURED, AND THE ONE THAT MATTERS MOST. A 7:1 reduction multiplies the
    # rotor's own inertia by 49 at the joint. For a 3507 outrunner rotor of
    # roughly 30 g at a 15 mm radius, J_rotor is about 4.7e-6 kg m2, so the
    # reflected term is about 2.3e-4 kg m2 -- several times the wheel's own spin
    # inertia. A balancing policy trained without it is trained on the wrong
    # plant. Measure it by spin-down, or get it from DAMIAO.
    "armature_kg_m2": 2.3e-4,
    # UNMEASURED. Joint friction and damping have never been characterised on
    # this actuator. Zero is not a claim that they are zero; it is a refusal to
    # invent them. Identify them on the first joint that runs.
    "friction_nm": 0.0,
    "damping_nm_s_rad": 0.0,
}


# --------------------------------------------------------------------------
# Masses


@dataclass(frozen=True)
class Solid:
    """One contribution to a link's mass, with enough shape to have inertia.

    The shape is also what the URDF DRAWS. Every one of these is a real part of
    the robot -- an actuator, a bearing, a board, a wheel -- so a URDF that
    carried only the printed meshes would show a machine with a third of itself
    missing and no visible wheels at all. build_urdf.py turns each of these
    into a visual as well as into inertia, which is why the primitives are
    chosen to be the part's actual envelope and not merely something with the
    right moments.

    `at` is the solid's own centre in the link's frame, in millimetres, except
    for a mesh, where it is the offset of the mesh file's origin from the link
    origin -- a mesh brings its own centroid with it.

    `shape` is one of:
      mesh        dims unused; `piece` names an STL in simulation/meshes
      cylinder_x  dims = (diameter, length), axis along X
      tube_x      dims = (outer diameter, inner diameter, length), axis along X
      box         dims = (x, y, z)
      point       dims unused; contributes mass but no inertia of its own

    `material` names a colour in the CAD's own palette -- cad/parameters.py for
    the robot, cad/electronics.py for the boards -- so a part is the same
    colour in the simulator as it is in Design Studio, and neither file is a
    second source of the other.

    `draw` is for the one solid that has mass and a bounding volume but is not
    a body: the wiring, which is spread through the whole cavity and would be
    drawn as a slab filling the pelvis.
    """

    label: str
    grams: float
    shape: str
    at: tuple[float, float, float]
    source: str
    note: str
    dims: tuple[float, ...] = ()
    piece: str = ""
    material: str = "printedOrange"
    draw: bool = True


# What each `source` is worth. check_model.py reports the mass total split this
# way, because "2 300 g" means something very different when a third of it has
# never been weighed.
SOURCES = {
    "measured": "measured from the CAD at PA12-CF density",
    "vendor": "vendor datasheet or vendor STEP",
    "bom": "docs/BOM.md line item, itself an estimate",
    "estimate": "estimate in tools/mass_budget.toml, never weighed",
    "assumption": "this file's split of a budget lump; the lump total is kept",
}


def budget() -> dict:
    """tools/mass_budget.toml, which is the same table tools/mass.py reads."""
    return tomllib.loads(BUDGET.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# The tree


@dataclass
class Link:
    name: str
    solids: list[Solid] = field(default_factory=list)
    # Collision primitives, as (shape, dims, centre) in the link's CAD frame.
    collisions: list[tuple[str, tuple[float, ...], tuple[float, float, float]]] = field(
        default_factory=list
    )


@dataclass
class Joint:
    name: str
    parent: str
    child: str
    origin: tuple[float, float, float]  # mm, in the parent's CAD frame
    axis: tuple[float, float, float]  # unit vector in the CAD frame
    kind: str  # "revolute" or "continuous"
    lower: float = 0.0  # degrees
    upper: float = 0.0  # degrees
    effort: float = 0.0  # Nm
    velocity: float = 0.0  # rad/s
    note: str = ""


def build() -> tuple[dict[str, Link], list[Joint], dict[str, float]]:
    """The whole robot: links with their masses, joints, and the dimensions."""
    d = load_dimensions()

    # ---- the stations, all of them derived in the KCL ---------------------
    hip_x = d["hipCenterX"]
    hip_z = d["wheeledHipPitchAxisHeight"]
    knee_z = d["wheeledKneeAxisHeight"]
    wheel_z = d["prototypeWheelAxisHeight"]
    torso_z = d["wheeledTorsoCenterHeight"]
    thigh_len = d["upperLegLength"]
    shin_len = d["lowerLegLength"]

    motor_d = d["actuatorDiameter"]
    motor_l = d["actuatorDepth"]

    # These relationships are what make a silent parse failure loud. They are
    # relations rather than constants, so a real design change does not trip
    # them but a dimension that came back wrong does.
    assert math.isclose(knee_z, wheel_z + shin_len), "shin does not span knee to wheel"
    assert math.isclose(hip_z, knee_z + thigh_len), "thigh does not span hip to knee"
    assert math.isclose(
        torso_z, hip_z + d["jointKeepOut"] + d["wheeledTorsoHeight"] / 2
    ), "torso does not sit one keep-out above the hip axis"

    links: dict[str, Link] = {}
    joints: list[Joint] = []

    # ---- base link: the pelvis, its lid, and everything standing in it -----
    # Its origin is the torso centre, which is the frame cad/torso.py and
    # cad/electronics.py are both already drawn in, so both drop in at
    # identity.
    hip_local_z = hip_z - torso_z

    base = Link("base_link")
    base.solids += [
        Solid(
            label="pelvis shell, clevises and cover bosses",
            grams=0.0,  # measured from the mesh
            shape="mesh",
            piece="pelvis-shell",
            at=(0.0, 0.0, 0.0),
            source="measured",
            note="cad/torso.py:pelvisShell, seven bodies",
        ),
        Solid(
            label="torso cover",
            grams=0.0,
            shape="mesh",
            piece="torso-cover",
            at=(0.0, 0.0, 0.0),
            source="measured",
            note="cad/torso.py:torsoCover",
        ),
    ]

    # The two hip pitch actuators. Their housings are held by the pelvis
    # clevises, so their mass is the pelvis's even though their output drives
    # the thighs. The body is centred on the joint axis: cad/main.py translates it
    # to the axis and no further.
    for side in SIDES:
        sign = SIDE_SIGN[side]
        base.solids.append(
            Solid(
                label=f"hip pitch actuator, {side}",
                grams=150.0,
                shape="cylinder_x",
                dims=(motor_d, motor_l),
                at=(sign * hip_x, 0.0, hip_local_z),
                source="vendor",
                material="motorGrey",
                note="DM-J3507-2EC, vendor manual V1.0: 46 dia x 37.9, about 150 g",
            )
        )
        # The flanged carrier is bonded into the pelvis cheek and the bearing
        # sits in it; only the journal turns with the thigh.
        base.solids.append(
            Solid(
                label=f"hip pitch bearing and carrier, {side}",
                grams=11.4,
                shape="cylinder_x",
                dims=(d["bearingCarrierFlangeDiameter"], d["bearingWidth"] + 3.0),
                at=(sign * (hip_x + d["frontCheekX"]), 0.0, hip_local_z),
                source="bom",
                material="bearingSteel",
                note="6800-2RS at 5.0 g and the turned carrier at 6.4 g, docs/BOM.md section 10",
            )
        )

    # The payload. cad/electronics.py draws each item inside its reserved
    # envelope in this same frame, so the envelope centroids are where the mass
    # goes -- which is a good deal better than a lump at the torso centre, and
    # it is the only reason this model's roll inertia means anything.
    #
    # mass_budget.toml carries these as two lines: 100 g of "electronics and
    # wiring" and 60 g of power entry. The 100 is split below across the boards
    # that make it up. The split is an assumption; the total is not.
    #
    # The colours are cad/electronics.py's own, so a board is the same
    # colour in the simulator as it is in the packing scene, and `draw` is what
    # separates a body from a bounding volume: everything here is a real box
    # standing in a real reserved envelope except the wiring, which is a mass
    # spread through the whole cavity and would be drawn as a slab filling it.
    payload = [
        (
            "SBC",
            45.0,
            "sbc",
            "assumption",
            "pcbGreen",
            True,
            "Raspberry-Pi-4-class board, 46 g published",
        ),
        (
            "controller carrier",
            25.0,
            "controller",
            "assumption",
            "pcbGreen",
            True,
            "STM32G474 core board, two CAN-FD transceivers, carrier and header",
        ),
        ("IMU", 3.0, "imu", "assumption", "sensorBlue", True, "BNO085 nano breakout"),
        (
            "wiring and looms",
            27.0,
            "wiring",
            "assumption",
            "carbonBlack",
            False,
            "the remainder of the budget's 100 g, spread through the cavity",
        ),
        (
            "power entry",
            60.0,
            "power",
            "estimate",
            "canSilver",
            True,
            "capacitor bank, fuse and terminal. THE BANK HAS NOT BEEN SIZED -- docs/BOM.md red line",
        ),
    ]
    envelopes = {
        "power": (
            d["powerWidth"],
            d["powerDepth"],
            d["powerHeight"],
            d["powerX"],
            d["lowerBandZ"],
        ),
        "controller": (
            d["controllerWidth"],
            d["controllerDepth"],
            d["controllerHeight"],
            d["controllerX"],
            d["lowerBandZ"],
        ),
        "sbc": (d["sbcWidth"], d["sbcDepth"], d["sbcHeight"], 0.0, d["upperBandZ"]),
        "imu": (d["imuWidth"], d["imuDepth"], d["imuHeight"], 0.0, d["floorZ"]),
        # Wiring has no envelope; it is spread through the box, so it is given
        # the cavity's own extent and sat in the middle of it.
        "wiring": (
            d["wheeledTorsoShellWidth"] - 2 * d["shellWall"],
            d["torsoShellDepth"] - 2 * d["shellWall"],
            d["upperBandZ"] + d["sbcHeight"] - d["floorZ"],
            0.0,
            d["floorZ"],
        ),
    }
    for label, grams, key, source, material, draw, note in payload:
        width, depth, height, at_x, base_z = envelopes[key]
        base.solids.append(
            Solid(
                label=label,
                grams=grams,
                shape="box",
                dims=(width, depth, height),
                at=(at_x, 0.0, base_z + height / 2),
                source=source,
                material=material,
                draw=draw,
                note=note,
            )
        )

    # M3 fastener sets, spread over the six joints they serve. The budget's
    # 45 g is for the joints; its 6 g of wheel clamps is placed on the wheels.
    for side in SIDES:
        base.solids.append(
            Solid(
                label=f"hip pitch fastener set, {side}",
                grams=45.0 / 6.0,
                shape="point",
                at=(SIDE_SIGN[side] * hip_x, 0.0, hip_local_z),
                source="assumption",
                note="the budget's 45 g of M3, split evenly over the six joints",
            )
        )

    # The pelvis collides as its own box. A convex hull of the shell would be
    # this box with the clevises added, and the clevises sit inside the legs'
    # own swept volume anyway.
    base.collisions.append(
        (
            "box",
            (
                d["wheeledTorsoShellWidth"],
                d["torsoShellDepth"],
                d["wheeledTorsoHeight"],
            ),
            (0.0, 0.0, 0.0),
        )
    )
    # The two hip actuators are NOT inside that box. They hang a keep-out below
    # the shell floor, on the clevises, and they are the lowest and widest thing
    # on the pelvis -- a 46 mm can whose outboard face is past the shell's own
    # side. Without these the robot could put its hip motors through an obstacle
    # and the simulator would never notice.
    for side in SIDES:
        base.collisions.append(
            (
                "cylinder_x",
                (motor_d, motor_l),
                (SIDE_SIGN[side] * hip_x, 0.0, hip_local_z),
            )
        )
    links[base.name] = base

    # ---- the two legs -----------------------------------------------------
    # cad/limb.py: "the limb axis is Z, both joint axes are X, and the two joint
    # centres sit at z = +/- limbLength/2", with the driven output disc at +z.
    # So a limb link whose origin is its proximal joint carries its mesh half a
    # limb-length down.
    #
    # The hands are crosswise. limbAssembly builds the plate on +X, which is
    # the RIGHT thigh and the LEFT shin; the mirror is the other two. That is
    # the same crosswise pairing tools/mass_budget.toml describes, and it is why
    # two prints cover four limbs.
    limb_mesh = {
        ("thigh", "right"): "limb-105-unmirrored",
        ("thigh", "left"): "limb-105-mirrored",
        ("shin", "left"): "limb-105-unmirrored",
        ("shin", "right"): "limb-105-mirrored",
    }

    for side in SIDES:
        sign = SIDE_SIGN[side]

        # -- thigh: hip pitch axis to knee axis --
        thigh = Link(f"thigh_{side}")
        thigh.solids += [
            Solid(
                label=f"thigh limb plate, {side}",
                grams=0.0,
                shape="mesh",
                piece=limb_mesh[("thigh", side)],
                at=(0.0, 0.0, -thigh_len / 2),
                source="measured",
                note="cad/limb.py, 105 mm, five bodies",
            ),
            Solid(
                label=f"knee actuator, {side}",
                grams=150.0,
                shape="cylinder_x",
                dims=(motor_d, motor_l),
                at=(0.0, 0.0, -thigh_len),
                source="vendor",
                material="motorGrey",
                note="held by the thigh's stator plate; drives the shin",
            ),
            Solid(
                label=f"hip pitch journal, {side}",
                grams=4.9,
                shape="cylinder_x",
                dims=(d["journalDiameter"], d["journalLength"]),
                at=(sign * (d["rotorHubInnerX"] + d["journalLength"] / 2), 0.0, 0.0),
                source="bom",
                material="bearingSteel",
                note="10 dia x 8 ground steel, seated in the rotor hub and turning with the thigh",
            ),
            Solid(
                label=f"knee fastener set, {side}",
                grams=45.0 / 6.0,
                shape="point",
                at=(0.0, 0.0, -thigh_len),
                source="assumption",
                note="the budget's 45 g of M3, split evenly over the six joints",
            ),
        ]
        thigh.collisions.append(
            (
                "box",
                (d["limbPlateThickness"] + motor_l, d["limbWaistDepth"], thigh_len),
                (0.0, 0.0, -thigh_len / 2),
            )
        )
        links[thigh.name] = thigh

        joints.append(
            Joint(
                name=f"hip_pitch_{side}",
                parent="base_link",
                child=thigh.name,
                origin=(sign * hip_x, 0.0, hip_local_z),
                # Positive is FLEXION: the thigh swings forward, towards +Y.
                # Same sign as cad/poses.py's pose_check's hip angles.
                axis=(1.0, 0.0, 0.0),
                kind="revolute",
                lower=-60.0,
                upper=60.0,
                note=(
                    "PROVISIONAL TRAVEL. No swept clearance check has ever been run on "
                    "hip pitch; the knee's 110 deg stop is the only joint limit this "
                    "project has established."
                ),
            )
        )

        # -- shin: knee axis to wheel axis --
        shin = Link(f"shin_{side}")
        shin.solids += [
            Solid(
                label=f"shin limb plate, {side}",
                grams=0.0,
                shape="mesh",
                piece=limb_mesh[("shin", side)],
                at=(0.0, 0.0, -shin_len / 2),
                source="measured",
                note="cad/limb.py, 105 mm, five bodies",
            ),
            Solid(
                label=f"wheel actuator, {side}",
                grams=150.0,
                shape="cylinder_x",
                dims=(motor_d, motor_l),
                at=(0.0, 0.0, -shin_len),
                source="vendor",
                material="motorGrey",
                note="held by the shin's stator plate; drives the wheel",
            ),
            Solid(
                label=f"wheel fastener set, {side}",
                grams=45.0 / 6.0,
                shape="point",
                at=(0.0, 0.0, -shin_len),
                source="assumption",
                note="the budget's 45 g of M3, split evenly over the six joints",
            ),
        ]
        shin.collisions.append(
            (
                "box",
                (d["limbPlateThickness"] + motor_l, d["limbWaistDepth"], shin_len),
                (0.0, 0.0, -shin_len / 2),
            )
        )
        links[shin.name] = shin

        joints.append(
            Joint(
                name=f"knee_{side}",
                parent=thigh.name,
                child=shin.name,
                origin=(0.0, 0.0, -thigh_len),
                # Positive is FLEXION, matching cad/poses.py's squat_check and the 110 deg
                # commissioning stop. In the sagittal plane knee flexion is the
                # opposite sense to hip flexion, hence the opposite sign here.
                axis=(-1.0, 0.0, 0.0),
                kind="revolute",
                lower=0.0,
                upper=110.0,
                note="110 deg is the commissioning hard stop, cad/poses.py's knee_limit_check.",
            )
        )

        # -- wheel --
        wheel = Link(f"wheel_{side}")
        wheel_centre_x = sign * d["skateWheelCenterX"]
        wheel.solids += [
            Solid(
                label=f"wheel adapter, {side}",
                grams=0.0,
                shape="mesh",
                piece=f"wheel-adapter-{side}",
                at=(0.0, 0.0, 0.0),
                source="measured",
                note="cad/wheel_adapter.py, three bodies, joint centre at its own origin",
            ),
            Solid(
                label=f"skate wheel, {side}",
                grams=60.0,
                shape="tube_x",
                # Urethane from the hub out to the tread. The hub itself is thin
                # plastic; putting all 60 g in the urethane annulus is the
                # pessimistic choice for spin inertia, and it is flagged as such.
                dims=(
                    d["skateWheelDiameter"],
                    d["skateWheelHubDiameter"],
                    d["skateWheelWidth"],
                ),
                at=(wheel_centre_x, 0.0, 0.0),
                source="estimate",
                material="soleBlack",
                note=(
                    "NEVER WEIGHED. Catalogue-typical for an 80 x 24 mm 85A wheel with "
                    "the bearings out. Its spin inertia is the most sensitive unmeasured "
                    "number in this model."
                ),
            ),
            Solid(
                label=f"wheel clamp, {side}",
                grams=3.0,
                shape="cylinder_x",
                dims=(
                    d["wheelClampWasherDiameter"],
                    d["wheelClampWasherThickness"] + 5.0,
                ),
                at=(sign * (d["skateWheelOuterX"] + 3.5), 0.0, 0.0),
                source="bom",
                material="bearingSteel",
                note="M5 x 20 cap screw, 30 dia washer and heat-set insert; the budget's 6 g for the pair",
            ),
        ]
        # The contact primitive. A cylinder, not the crowned tread: every
        # physics engine resolves a cylinder against a plane cleanly and none of
        # them resolves a crowned mesh cleanly. What this loses is the contact
        # patch narrowing as the robot leans, which is a real effect and one to
        # come back to if a policy turns out to depend on it.
        wheel.collisions.append(
            (
                "cylinder_x",
                (d["skateWheelDiameter"], d["skateWheelWidth"]),
                (wheel_centre_x, 0.0, 0.0),
            )
        )
        links[wheel.name] = wheel

        joints.append(
            Joint(
                name=f"wheel_drive_{side}",
                parent=shin.name,
                child=wheel.name,
                origin=(0.0, 0.0, -shin_len),
                # Positive drives the robot forward, towards +Y.
                axis=(-1.0, 0.0, 0.0),
                kind="continuous",
                note="Direct drive; no reduction beyond the actuator's own 7:1.",
            )
        )

    # ---- what the actuator can do ----------------------------------------
    # The same six actuators everywhere, so this is set in one place. The
    # effort declared is the PEAK, because a URDF has one number and the
    # continuous rating is thermal rather than a hard ceiling; the Isaac Lab
    # config carries both.
    for joint in joints:
        joint.effort = ACTUATOR["peak_torque_nm"]
        joint.velocity = ACTUATOR["max_velocity_rad_s"]

    return links, joints, d
