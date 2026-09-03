"""Everything about this rig that can be checked without Isaac Sim.

    python simulation/isaacsim/preflight.py

Free, offline, and it needs nothing but numpy -- no Isaac Sim, no Isaac Lab, no
trimesh. Run it before spending an Isaac Sim launch on a URDF that was never
going to load, and run it after every `/urdf` rebuild.

WHAT IT IS FOR. simulation/check_model.py checks the MODEL -- that the tree
reproduces the CAD's own pose arithmetic, that the mass adds up, that the
tensors are physical. This checks the FILE: that the URDF on disk is a thing a
physics engine can actually ingest, that every mesh it points at is there and
is readable, and that the plant description the Isaac scripts will apply still
describes the same robot the URDF does.

That last one is the check worth having. plant.py reads the CAD for the wheel
radius, the standing height and the track; build_urdf.py reads the same CAD, by
a different path, for the joint origins and the collision geometry. They are
two independent readings of one source, so agreement is evidence and
disagreement means one of the two has gone stale.

WHAT IT CANNOT CHECK. Whether PhysX makes the same robot out of this file.
Cylinder colliders, self collision, drive modes and the reflected rotor inertia
are all things only the simulator can answer, and run.py --check is what asks
it.
"""

from __future__ import annotations

import math
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SIMULATION = HERE.parent
if str(SIMULATION) not in sys.path:
    sys.path.insert(0, str(SIMULATION))

import plant  # noqa: E402

# The robot's mass ceiling, tools/mass_budget.toml's reason for existing.
MASS_CEILING_KG = 2.300

# How closely two independent readings of the same CAD have to agree. Both are
# exact arithmetic on the same millimetre figures, so anything above a
# micrometre is a real disagreement rather than rounding.
TOLERANCE_M = 1e-6


def fail(problems: list[str], message: str) -> None:
    problems.append(message)


# --------------------------------------------------------------------------
# The file itself


def load_urdf(path: Path, problems: list[str]) -> ET.Element | None:
    if not path.exists():
        fail(problems, f"no URDF at {path}. Run `uv run simulation/build_urdf.py`.")
        return None
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as exc:
        fail(problems, f"{path.name} is not well-formed XML: {exc}")
        return None


def check_tree(root: ET.Element, problems: list[str]) -> list[tuple[str, str, str, str]]:
    """One root, no cycles, every link reachable, no link driven twice."""
    links = [link.get("name") for link in root.findall("link")]
    joints = [
        (
            joint.get("name"),
            joint.get("type"),
            joint.find("parent").get("link"),
            joint.find("child").get("link"),
        )
        for joint in root.findall("joint")
    ]

    duplicates = {name for name in links if links.count(name) > 1}
    if duplicates:
        fail(problems, f"links declared more than once: {sorted(duplicates)}")

    children = [child for _, _, _, child in joints]
    twice = {name for name in children if children.count(name) > 1}
    if twice:
        fail(problems, f"links with more than one parent joint: {sorted(twice)}")

    known = set(links)
    for name, _, parent, child in joints:
        for role, link in (("parent", parent), ("child", child)):
            if link not in known:
                fail(problems, f"joint {name} names a {role} link that does not exist: {link}")

    roots = [link for link in links if link not in children]
    if roots != ["base_link"]:
        fail(problems, f"expected exactly one root named base_link, found {roots}")

    # Walk from the root; anything not reached is detached or in a cycle.
    edges: dict[str, list[str]] = {}
    for _, _, parent, child in joints:
        edges.setdefault(parent, []).append(child)
    reached, stack = set(), ["base_link"]
    while stack:
        link = stack.pop()
        if link in reached:
            fail(problems, f"the joint tree loops back on {link}")
            continue
        reached.add(link)
        stack.extend(edges.get(link, []))
    stranded = set(links) - reached
    if stranded:
        fail(problems, f"links not reachable from base_link: {sorted(stranded)}")

    return joints


def check_meshes(root: ET.Element, urdf_dir: Path, problems: list[str]) -> list[tuple]:
    """Every referenced mesh is present and is a readable binary STL.

    Binary STL is 80 bytes of header, a triangle count, and 50 bytes per
    triangle, so the file's own length says whether it is intact. That catches
    a truncated copy, an ASCII file that build_urdf.py failed to rewrite, and a
    git-lfs pointer left unfetched -- all of which reach Isaac Sim as an
    unhelpful parse error deep inside the importer.
    """
    seen = {}
    for mesh in root.iter("mesh"):
        filename = mesh.get("filename")
        if filename in seen:
            continue
        path = (urdf_dir / filename).resolve()
        if not path.exists():
            fail(problems, f"missing mesh {filename}")
            continue
        data = path.read_bytes()
        if data[:5].lower().lstrip() == b"solid" and b"facet" in data[:512]:
            fail(problems, f"{filename} is ASCII STL; build_urdf.py should have written binary")
            continue
        if len(data) < 84:
            fail(problems, f"{filename} is too short to be an STL ({len(data)} bytes)")
            continue
        (triangles,) = struct.unpack("<I", data[80:84])
        expected = 84 + 50 * triangles
        if len(data) != expected:
            fail(
                problems,
                f"{filename} claims {triangles} triangles, which needs {expected} bytes,"
                f" but the file is {len(data)}",
            )
            continue
        if triangles == 0:
            fail(problems, f"{filename} holds no triangles")
            continue
        seen[filename] = (triangles, len(data))
    return sorted((name, *facts) for name, facts in seen.items())


# --------------------------------------------------------------------------
# The physics the file declares


def check_inertials(root: ET.Element, problems: list[str]) -> list[tuple]:
    """Mass positive, tensor symmetric positive-definite, triangle inequality.

    A tensor whose principal moments break the triangle inequality describes a
    body that cannot exist. PhysX will integrate it anyway, and the robot will
    behave in a way no amount of tuning explains.
    """
    rows = []
    for link in root.findall("link"):
        name = link.get("name")
        inertial = link.find("inertial")
        if inertial is None:
            fail(problems, f"link {name} has no inertial block")
            continue

        mass = float(inertial.find("mass").get("value"))
        if not math.isfinite(mass) or mass <= 0.0:
            fail(problems, f"link {name} has mass {mass}")
            continue

        i = inertial.find("inertia")
        tensor = np.array(
            [
                [float(i.get("ixx")), float(i.get("ixy")), float(i.get("ixz"))],
                [float(i.get("ixy")), float(i.get("iyy")), float(i.get("iyz"))],
                [float(i.get("ixz")), float(i.get("iyz")), float(i.get("izz"))],
            ]
        )
        if not np.isfinite(tensor).all():
            fail(problems, f"link {name} has a non-finite inertia tensor")
            continue

        moments = np.linalg.eigvalsh(tensor)
        if (moments <= 0.0).any():
            fail(problems, f"link {name} has a non-positive principal moment: {moments}")
        a, b, c = sorted(moments)
        if a + b < c * (1.0 - 1e-9):
            fail(
                problems,
                f"link {name} breaks the triangle inequality: {a:.3e} + {b:.3e} < {c:.3e}",
            )
        rows.append((name, mass, moments))
    return rows


def check_joints(root: ET.Element, problems: list[str]) -> list[tuple]:
    """Unit axes, ordered limits, an effort and a velocity on every joint."""
    rows = []
    for joint in root.findall("joint"):
        name = joint.get("name")
        kind = joint.get("type")

        axis_element = joint.find("axis")
        axis = np.array([float(v) for v in axis_element.get("xyz").split()])
        norm = float(np.linalg.norm(axis))
        if abs(norm - 1.0) > 1e-9:
            fail(problems, f"joint {name} has a non-unit axis of length {norm:.6f}")

        limit = joint.find("limit")
        if limit is None:
            fail(problems, f"joint {name} has no limit block, so it has no effort ceiling")
            continue

        effort = float(limit.get("effort"))
        velocity = float(limit.get("velocity"))
        if effort <= 0.0:
            fail(problems, f"joint {name} may exert no torque (effort {effort})")
        if velocity <= 0.0:
            fail(problems, f"joint {name} may not turn (velocity {velocity})")

        lower = upper = None
        if kind == "revolute":
            lower, upper = float(limit.get("lower")), float(limit.get("upper"))
            if not lower < upper:
                fail(problems, f"joint {name} has limits that do not open: [{lower}, {upper}]")
        elif kind == "continuous":
            if limit.get("lower") is not None:
                fail(problems, f"continuous joint {name} declares a position limit")
        else:
            fail(problems, f"joint {name} is of type {kind!r}, which nothing here rigs")

        rows.append((name, kind, axis, lower, upper, effort, velocity))
    return rows


# --------------------------------------------------------------------------
# The cross-check: does plant.py still describe the same robot?


def check_against_plant(root: ET.Element, joints: list[tuple], problems: list[str]) -> None:
    """Two independent readings of one CAD, compared.

    plant.py reads the KCL for the wheel radius, the standing height and the
    track. build_urdf.py read the same KCL, separately, for the collision
    cylinders and the joint origins. Neither knows about the other, so if they
    agree the reading is sound, and if they disagree the URDF has been rebuilt
    since plant.py was last right, or the other way round.
    """
    geometry = plant.geometry()

    # -- the joints the scripts will command must be the joints that exist ---
    in_file = [name for name, _, _, _ in joints]
    if sorted(in_file) != sorted(plant.JOINT_ORDER):
        fail(
            problems,
            "plant.JOINT_ORDER does not match the URDF's joints:"
            f" URDF has {sorted(in_file)}, plant has {sorted(plant.JOINT_ORDER)}",
        )
    for name in plant.WHEEL_JOINTS:
        kind = next((k for n, k, _, _ in joints if n == name), None)
        if kind != "continuous":
            fail(problems, f"{name} should be a continuous joint, the URDF says {kind!r}")

    # -- walk each leg from base_link out to the wheel's contact patch -------
    # Every joint origin down the chain, plus the collider's own offset inside
    # the wheel link. With the legs straight every rotation on the way is the
    # identity, so the offsets simply add -- which is the whole point of doing
    # it here rather than trusting the header comment, which is prose.
    origins = _joint_origins(root)
    contacts = {}
    for side in ("right", "left"):
        chain = (f"hip_pitch_{side}", f"knee_{side}", f"wheel_drive_{side}")
        try:
            centre = sum((origins[name] for name in chain), np.zeros(3))
        except KeyError as exc:
            fail(problems, f"cannot walk the {side} leg: no joint {exc}")
            continue

        link = next(
            (l for l in root.findall("link") if l.get("name") == f"wheel_{side}"), None
        )
        if link is None:
            fail(problems, f"no wheel_{side} link to stand on")
            continue

        cylinders = [c for c in link.findall("collision") if c.find("geometry/cylinder") is not None]
        if len(cylinders) != 1:
            fail(
                problems,
                f"wheel_{side} should collide as exactly one cylinder, found {len(cylinders)}",
            )
            continue

        collision = cylinders[0]
        radius = float(collision.find("geometry/cylinder").get("radius"))
        if abs(radius - geometry["wheel_radius_m"]) > TOLERANCE_M:
            fail(
                problems,
                f"wheel_{side}'s collider is {radius:.6f} m but the CAD says"
                f" {geometry['wheel_radius_m']:.6f} m",
            )
        offset = np.array([float(v) for v in collision.find("origin").get("xyz").split()])
        contacts[side] = (centre + offset, radius)

    if len(contacts) == 2:
        track = abs(contacts["left"][0][1] - contacts["right"][0][1])
        if abs(track - geometry["track_m"]) > TOLERANCE_M:
            fail(
                problems,
                f"the URDF's wheels are {track:.6f} m apart but the CAD says"
                f" {geometry['track_m']:.6f} m",
            )

        # The robot has to stand where plant.py says it will: the wheel axis
        # sits one radius off the floor, so that fixes base_link's height.
        for side, (centre, radius) in contacts.items():
            base_height = radius - centre[2]
            if abs(base_height - geometry["standing_base_height_m"]) > TOLERANCE_M:
                fail(
                    problems,
                    f"walking the {side} leg puts base_link {base_height:.6f} m up, but the"
                    f" CAD says it stands at {geometry['standing_base_height_m']:.6f} m",
                )


def _joint_origins(root: ET.Element) -> dict[str, np.ndarray]:
    return {
        joint.get("name"): np.array(
            [float(v) for v in joint.find("origin").get("xyz").split()]
        )
        for joint in root.findall("joint")
    }


# --------------------------------------------------------------------------


def main() -> int:
    problems: list[str] = []
    urdf_path = plant.URDF_PATH

    root = load_urdf(urdf_path, problems)
    if root is None:
        print("PREFLIGHT FAILED")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print(f"robot {root.get('name')!r}, from {urdf_path.relative_to(plant.ROOT)}\n")

    joints = check_tree(root, problems)
    meshes = check_meshes(root, urdf_path.parent, problems)
    inertials = check_inertials(root, problems)
    joint_rows = check_joints(root, problems)
    check_against_plant(root, joints, problems)

    print("meshes")
    for name, triangles, size in meshes:
        print(f"  {name:<32} {triangles:6d} triangles   {size / 1024:6.0f} KB binary")

    print("\nlinks")
    total = 0.0
    print(f"  {'link':<14} {'mass kg':>9}   principal moments, kg m2")
    for name, mass, moments in inertials:
        total += mass
        print(f"  {name:<14} {mass:9.4f}   " + "  ".join(f"{m:.3e}" for m in moments))
    headroom = MASS_CEILING_KG - total
    print(f"  {'TOTAL':<14} {total:9.4f}   {headroom * 1000:+.0f} g against the 2 300 g ceiling")
    if total > MASS_CEILING_KG:
        fail(problems, f"the model weighs {total:.3f} kg, over the {MASS_CEILING_KG} kg ceiling")

    print("\njoints, in the order plant.py names them")
    print(f"  {'joint':<20} {'type':<11} {'axis':<12} {'travel, deg':<16} {'Nm':>5} {'rad/s':>7}")
    by_name = {row[0]: row for row in joint_rows}
    for name in plant.JOINT_ORDER:
        if name not in by_name:
            continue
        _, kind, axis, lower, upper, effort, velocity = by_name[name]
        axis_text = " ".join(f"{v:+.0f}" for v in axis)
        travel = (
            "continuous"
            if lower is None
            else f"{math.degrees(lower):+.0f} to {math.degrees(upper):+.0f}"
        )
        print(f"  {name:<20} {kind:<11} {axis_text:<12} {travel:<16} {effort:5.1f} {velocity:7.1f}")

    geometry = plant.geometry()
    print("\nas the CAD has it, read independently of the URDF")
    print(f"  wheel radius          {geometry['wheel_radius_m'] * 1000:6.1f} mm")
    print(f"  track, patch to patch {geometry['track_m'] * 1000:6.1f} mm")
    print(f"  base_link stands at   {geometry['standing_base_height_m'] * 1000:6.1f} mm")
    print(f"  spawn height          {plant.spawn_height_m() * 1000:6.1f} mm")

    print()
    if problems:
        print(f"PREFLIGHT FAILED, {len(problems)} problem(s)")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print("PREFLIGHT CLEAN. The file is loadable and agrees with the CAD.")
    print("What PhysX makes of it is a different question. Ask it, with Isaac")
    print("Sim's own Python and -u so a hard shutdown cannot eat the output:")
    print("    <isaac>/python.exe -u simulation/isaacsim/import_urdf.py")
    print("    <isaac>/python.exe -u simulation/isaacsim/run.py --check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
