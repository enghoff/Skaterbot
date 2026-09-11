# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy>=1.26", "trimesh>=4.0", "scipy>=1.11",
#                 "networkx>=3.0", "manifold3d>=2.3", "build123d>=0.9"]
# ///
"""Check the simulation model against the CAD it came from.

    uv run simulation/check_model.py

Free and offline. It answers four questions, and the fourth is the one that
matters most.

1. DOES THE KINEMATIC TREE AGREE WITH THE CAD? cad/poses.py's pose_check and
   squat_check each place a leg at a stated hip and knee angle and work out
   where the wheel ends up. Those scenes are the project's own arithmetic, done
   independently of anything here, so driving the URDF's tree to the same
   angles and landing on the same wheel centre is real evidence -- it tests the
   link lengths, the joint origins, the axis directions and the sign of every
   joint at once. A sign error anywhere shows up here as tens of millimetres.

2. DOES THE MASS ADD UP? Against tools/mass_budget.toml, which is the same
   table tools/mass.py rolls up on the engine, and against the robot's 2 300 g
   ceiling.

3. ARE THE INERTIA TENSORS PHYSICAL? A tensor whose principal moments break the
   triangle inequality describes a body that cannot exist, and a physics engine
   will integrate it anyway.

4. HOW MUCH OF THIS ROBOT HAS ACTUALLY BEEN MEASURED? Every mass carries where
   it came from, and the summary at the end totals them by provenance. A policy
   trained on this model is only as good as that table, so it is printed last
   and in full rather than buried.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import robot as robot_model  # noqa: E402
from inertia import MeshLibrary, is_plausible, link_properties, skew_of  # noqa: E402

from cad import poses  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW_MESHES = HERE / "meshes"

# How closely the tree has to reproduce the CAD's own pose arithmetic. These
# are closed-form trigonometry on both sides, so anything above a micrometre is
# a real disagreement rather than rounding.
TOLERANCE_MM = 1e-6


def rotation(axis: np.ndarray, radians: float) -> np.ndarray:
    """Rodrigues, for an axis that is already a unit vector."""
    k = np.asarray(axis, dtype=float)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(radians) * K + (1 - np.cos(radians)) * (K @ K)


def forward_kinematics(
    joints, angles_deg: dict[str, float], base_origin: np.ndarray
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Every link's (origin, orientation) in the CAD world frame.

    Walks the joint list in order, which is valid because robot.build() emits
    parents before children.
    """
    frames = {"base_link": (np.asarray(base_origin, dtype=float), np.eye(3))}
    for joint in joints:
        parent_p, parent_R = frames[joint.parent]
        origin = parent_p + parent_R @ np.asarray(joint.origin, dtype=float)
        turn = rotation(
            np.asarray(joint.axis, dtype=float),
            np.deg2rad(angles_deg.get(joint.name, 0.0)),
        )
        frames[joint.child] = (origin, parent_R @ turn)
    return frames


# --------------------------------------------------------------------------
# 1. The tree against the CAD's own pose scenes


def check_poses(joints, dimensions) -> list[str]:
    """Drive the tree to each scene's angles and land where the scene says."""
    failures = []

    scenes = [
        (
            "pose_check",
            "crouched, right wheel lifted",
            "pose_check",
            {
                "hip_pitch_left": "leftHipAngle",
                "knee_left": "leftKneeAngle",
                "hip_pitch_right": "rightHipAngle",
                "knee_right": "rightKneeAngle",
            },
            "poseHipPitchZ",
            {
                "wheel_left": ("leftWheelY", "leftWheelZ"),
                "wheel_right": ("rightWheelY", "rightWheelZ"),
            },
        ),
        (
            "squat_check",
            "deepest squat the knee stop allows",
            "squat_check",
            {
                "hip_pitch_left": "squatHipAngle",
                "knee_left": "squatKneeAngle",
                "hip_pitch_right": "squatHipAngle",
                "knee_right": "squatKneeAngle",
            },
            "squatHipPitchZ",
            {
                "wheel_left": ("wheelY", "wheelZ"),
                "wheel_right": ("wheelY", "wheelZ"),
            },
        ),
    ]

    print("1. THE TREE AGAINST THE CAD'S OWN POSE SCENES")
    for label, description, source, angle_names, hip_z_name, expected in scenes:
        scene = poses.SCENES[source]()
        angles = {joint: scene[name] for joint, name in angle_names.items()}

        # The scenes drop the whole robot so the standing wheel stays on the
        # floor, and express the leg in world coordinates from the dropped hip.
        # Put the base at the height that puts the hip axes there.
        drop = dimensions["wheeledHipPitchAxisHeight"] - scene[hip_z_name]
        base = np.array([0.0, 0.0, dimensions["wheeledTorsoCenterHeight"] - drop])
        frames = forward_kinematics(joints, angles, base)

        print(f"\n   {label} -- {description}")
        print(
            "     "
            + "  ".join(f"{name}={value:+.0f}deg" for name, value in angles.items())
        )
        for link, (y_name, z_name) in expected.items():
            position = frames[link][0]
            want = np.array([scene[y_name], scene[z_name]])
            got = np.array([position[1], position[2]])
            error = float(np.max(np.abs(got - want)))
            verdict = "ok" if error < TOLERANCE_MM else "MISMATCH"
            print(
                f"     {link:<12} y {got[0]:+9.3f} z {got[1]:+9.3f} mm   "
                f"scene says y {want[0]:+9.3f} z {want[1]:+9.3f}   {verdict}"
            )
            if error >= TOLERANCE_MM:
                failures.append(
                    f"{label}: {link} is {error:.3f} mm from where the scene puts it"
                )
    return failures


# --------------------------------------------------------------------------
# 2 and 3. Mass, and whether the tensors are physical


def check_links(links, joints, dimensions, meshes) -> tuple[list[str], dict]:
    failures = []
    print("\n\n2. MASS AND INERTIA, LINK BY LINK")
    print(
        f"   {'link':<14} {'mass g':>8} {'|com| mm':>9}  "
        f"{'principal moments, kg m2':<34} off-diagonal"
    )

    rolled = {}
    total = 0.0
    for name in ["base_link"] + [joint.child for joint in joints]:
        link = links[name]
        grams, centre, tensor = link_properties(link.solids, meshes)
        rolled[name] = (grams, centre, tensor)
        total += grams

        si_tensor = tensor * 1e-9
        ok, why = is_plausible(si_tensor)
        moments = np.linalg.eigvalsh(si_tensor)
        print(
            f"   {name:<14} {grams:8.1f} {np.linalg.norm(centre):9.1f}  "
            + "  ".join(f"{m:.3e}" for m in moments)
            + f"   {skew_of(tensor) * 100:5.1f}%"
            + ("" if ok else f"   IMPLAUSIBLE: {why}")
        )
        if not ok:
            failures.append(f"{name}: {why}")

    # Every printed piece the robot carries, taken from the `[[printed.piece]]`
    # register in tools/mass_budget.toml rather than from a list kept here.
    #
    # THIS IS WHAT CATCHES A PART THAT WAS ADDED TO THE ROBOT AND NEVER ADDED TO
    # THE MODEL. The register says how many of each piece the robot is built
    # from; the model is counted for how many it actually places. A new brace
    # printed twice and hung on nothing would otherwise pass every other check
    # in this file, because a link that does not exist has no mass to be wrong.
    register = {
        piece["name"]: piece["prints"]
        for part in robot_model.budget()["printed"]
        for piece in part.get("piece", [])
    }
    placed: dict[str, int] = {}
    for link in links.values():
        for solid in link.solids:
            if solid.shape == "mesh":
                placed[solid.piece] = placed.get(solid.piece, 0) + 1

    print("\n   printed pieces, against the register in tools/mass_budget.toml")
    for piece in sorted(set(register) | set(placed)):
        wanted, got = register.get(piece, 0), placed.get(piece, 0)
        grams = meshes.properties(piece).grams if piece in placed else 0.0
        note = "" if wanted == got else f"   <-- register says {wanted}"
        print(f"     {piece:<24} x{got}  {grams * got:7.1f} g{note}")
        if wanted != got:
            failures.append(
                f"{piece}: the robot is built from {wanted} of these but the model "
                f"places {got}"
            )

    budget = robot_model.budget()
    ceiling = budget["ceiling_g"]
    fixed = sum(
        item.get("total_g", item.get("each_g", 0.0) * item.get("count", 1))
        for item in budget["fixed"]
    )
    printed = sum(meshes.properties(p).grams * n for p, n in placed.items())
    budget_total = printed + fixed

    # As tools/mass.py would report it: the shells added up, overlaps and all.
    # It errs upward on purpose, so the two tools disagree by exactly that bias
    # and the difference is worth printing rather than reconciling silently.
    as_exported = sum(
        meshes.properties(piece).summed_grams * count for piece, count in placed.items()
    )

    print(f"\n   this model          {total:7.1f} g   overlaps resolved")
    print(
        f"   as tools/mass.py    {as_exported + fixed:7.1f} g   shells added up, "
        f"which counts {as_exported - printed:.1f} g of overlap twice"
    )
    print(
        f"   budget fixed lines  {fixed:7.1f} g   every bought and estimated item in "
        "mass_budget.toml, all of it placed here"
    )
    print(
        f"   ceiling             {ceiling:7.1f} g  -- {ceiling - total:+.1f} g of headroom"
    )
    if abs(total - budget_total) > 0.5:
        failures.append(
            f"the model totals {total:.1f} g but the budget totals {budget_total:.1f} g; "
            "a mass has been dropped or double-counted"
        )
    if total > ceiling:
        failures.append(f"the model is {total - ceiling:.1f} g over the ceiling")

    return failures, rolled


# --------------------------------------------------------------------------
# What the robot is, as a plant


def describe_plant(links, joints, dimensions, rolled) -> None:
    print("\n\n3. WHAT THIS IS, AS A THING TO CONTROL")

    base = np.array([0.0, 0.0, dimensions["wheeledTorsoCenterHeight"]])
    frames = forward_kinematics(joints, {}, base)

    total = 0.0
    weighted = np.zeros(3)
    for name, (grams, centre, _) in rolled.items():
        position, orientation = frames[name]
        weighted += grams * (position + orientation @ centre)
        total += grams
    com = weighted / total

    axle = dimensions["prototypeWheelAxisHeight"]
    track = 2.0 * (dimensions["hipCenterX"] + dimensions["skateWheelCenterX"])
    radius = dimensions["skateWheelDiameter"] / 2.0
    pendulum = com[2] - axle

    print(f"   standing height                {dimensions['wheeledTorsoTop']:8.1f} mm")
    print(f"   centre of mass, standing       {com[2]:8.1f} mm above the floor")
    print(f"     ... fore and aft of the axle {com[1]:+8.1f} mm")
    print(f"     ... left and right of centre {com[0]:+8.1f} mm")
    print(f"   wheel axle                     {axle:8.1f} mm")
    print(f"   pendulum length above the axle {pendulum:8.1f} mm")
    print(f"   wheel radius                   {radius:8.1f} mm")
    print(f"   track, contact patch to patch  {track:8.1f} mm")

    # What the numbers mean for a controller. The unstable pole of an inverted
    # pendulum is sqrt(g / L), and its reciprocal is how long the robot takes to
    # fall over by a factor of e once it starts.
    tip = np.degrees(np.arctan2(track / 2.0, pendulum))
    pole = np.sqrt(9810.0 / pendulum)
    print(
        f"\n   It falls sideways with nothing to stop it but differential drive: there is no\n"
        f"   hip roll on this robot. Leaning past {tip:.0f} deg puts the centre of mass outside the\n"
        f"   track. As an inverted pendulum about the axle its unstable pole is {pole:.1f} per second,\n"
        f"   so it falls with a {1000.0 / pole:.0f} ms time constant and a balance loop wants to run an\n"
        f"   order of magnitude faster than that -- upwards of 100 Hz."
    )

    # The comparison that decides how much the unmeasured armature matters.
    wheel_spin = float(np.linalg.eigvalsh(rolled["wheel_right"][2] * 1e-9)[-1])
    armature = robot_model.ACTUATOR["armature_kg_m2"]
    print(
        f"\n   A wheel's own spin inertia is {wheel_spin:.2e} kg m2. The actuator's rotor, reflected\n"
        f"   through its 7:1 reduction, is estimated at {armature:.2e} -- {armature / wheel_spin:.1f} times as much. So the\n"
        "   thing a balance policy mostly accelerates is the motor, not the wheel, and that\n"
        "   number has never been measured."
    )

    if abs(com[1]) > 2.0:
        print(
            f"\n   NOTE: the standing centre of mass is {abs(com[1]):.1f} mm "
            f"{'forward of' if com[1] > 0 else 'behind'} the axle, so the robot\n"
            "   does not stand still at zero wheel torque."
        )
    if abs(com[0]) > 0.5:
        print(
            f"\n   NOTE: the standing centre of mass sits {abs(com[0]):.1f} mm to the "
            f"{'right' if com[0] > 0 else 'left'}. The bottom band\n"
            "   of the pelvis holds a 288 g battery against a 60 g power-entry block\n"
            "   (cad/electronics.py), one at each side wall, and they do not weigh the\n"
            "   same. On a robot with no hip roll that is a standing bias the wheels have\n"
            "   to hold out against, and where the pack sits is the cheapest way to trim\n"
            "   it -- nothing else in this torso weighs enough to matter."
        )


# --------------------------------------------------------------------------
# 4. What has actually been measured


def report_provenance(links) -> None:
    print("\n\n4. HOW MUCH OF THIS ROBOT HAS BEEN MEASURED")

    meshes = MeshLibrary(RAW_MESHES, robot_model.budget()["material"]["density"])
    by_source: dict[str, float] = {}
    soft: list[tuple[str, float, str]] = []
    for link in links.values():
        for solid in link.solids:
            grams = (
                meshes.properties(solid.piece).grams
                if solid.shape == "mesh"
                else solid.grams
            )
            by_source[solid.source] = by_source.get(solid.source, 0.0) + grams
            if solid.source in ("estimate", "assumption"):
                soft.append((solid.label, grams, solid.note))

    total = sum(by_source.values())
    for source in ("measured", "vendor", "bom", "estimate", "assumption"):
        grams = by_source.get(source, 0.0)
        if grams:
            print(
                f"   {source:<12} {grams:7.1f} g  {grams / total * 100:5.1f}%   "
                f"{robot_model.SOURCES[source]}"
            )
    unweighed = total - by_source.get("measured", 0.0)
    print(
        f"\n   {unweighed / total * 100:.0f} per cent of this robot's mass has never been on a scale."
    )

    print("\n   The parts of that which would move a simulation result:")
    for label, grams, note in sorted(soft, key=lambda row: -row[1])[:6]:
        print(f"     {label:<26} {grams:6.1f} g   {note[:88]}")

    actuator = robot_model.ACTUATOR
    print("\n   And on the actuator, which is not geometry at all:")
    print(
        f"     velocity limit    {actuator['max_velocity_rad_s']:.1f} rad/s   PLACEHOLDER. "
        "No vendor figure has been recorded."
    )
    print(
        f"     armature          {actuator['armature_kg_m2']:.1e} kg m2   ESTIMATED from a "
        "30 g rotor at 15 mm, reflected through 7:1."
    )
    print(
        f"     friction, damping {actuator['friction_nm']:.1f} Nm, "
        f"{actuator['damping_nm_s_rad']:.1f} Nm s/rad   NEVER CHARACTERISED. Zero is a "
        "refusal to invent them."
    )
    print(
        "\n   Contact against the ground is 85A urethane on a crowned tread, modelled as a\n"
        "   cylinder with whatever friction the simulator is told to use. Nothing about it\n"
        "   has been measured either."
    )


def main() -> int:
    links, joints, dimensions = robot_model.build()
    meshes = MeshLibrary(RAW_MESHES, robot_model.budget()["material"]["density"])

    try:
        failures = check_poses(joints, dimensions)
        more, rolled = check_links(links, joints, dimensions, meshes)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    failures += more

    describe_plant(links, joints, dimensions, rolled)
    report_provenance(links)

    if failures:
        print("\n\nFAILED", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print("\n\nThe model agrees with the CAD.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
