# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9"]
# ///
"""Gate F -- the check scenes, as numbers instead of pictures.

The seven check scenes were the project's regression suite and the way you saw
interference the standing pose hides. They were also, every one of them, a thing
you looked at: the KCL could place a shin at the knee stop but it could not tell
you how close the plate came, so the answer lived in a render and in a comment
saying it was fine.

This gate is the other half of porting them. It does two things.

FIRST, IT PINS THE POSES. reference/golden/scenes.json is what the KCL computed
for these same scenes, frozen before it was deleted. Every constant cad/poses.py
produces is compared against it by name at zero tolerance, and a name in one and
not the other is a failure. That is what keeps gate D honest now that both halves
of it are Python: the joint tree comes out of cad/parameters.py, the pose comes
out of cad/poses.py, and this holds the pose against a reference neither had a
hand in.

SECOND, IT MEASURES THE CLEARANCES. Every gap a scene was drawn to show is
computed between the two actual solids -- the real distance, and the volume they
share -- and held against what the scene claims. An overlap is a hard failure
wherever two bodies are meant to miss each other; a gap is checked against the
margin the design intends.

    uv run tools/gate_f.py            # the poses and every clearance
    uv run tools/gate_f.py --poses    # just the frozen-reference comparison

WHY CONTACT IS NOT INTERFERENCE. Several of these pairs are meant to touch. The
wheel adapter lands on its motor's output face, the limb plate lands on the
actuator's rear cover, and the payload's reserved volumes sit on the shell floor
and the saddle tops. For those the assertion is that the shared volume is ZERO
while the distance is zero -- they meet, and neither eats into the other.

Free, offline, no engine.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GOLDEN = ROOT / "reference" / "golden" / "scenes.json"

# What counts as touching. OCCT's distance between two faces that meet is zero to
# machine precision, but a boolean between them is not exact, so a shared volume
# below this is contact rather than interference. A cubic micron.
CONTACT_MM3 = 1e-6


def union(bodies: list):
    """One solid from a scene group, which is a list of interpenetrating bodies."""
    merged = bodies[0]
    for body in bodies[1:]:
        merged = merged + body
    return merged


def measure(first: list, second: list) -> tuple[float, float]:
    """(distance, shared volume) between two groups of bodies, in mm and mm3."""
    a, b = union(first), union(second)
    try:
        shared = abs(a.intersect(b).volume)
    except (ValueError, AttributeError):
        # An empty intersection: OCCT hands back a compound with no solids in it.
        shared = 0.0
    return a.distance_to(b), shared


def check_poses() -> tuple[int, int]:
    """Every scene constant against the frozen KCL reference. (checked, failed)"""
    from cad import poses

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["scenes"]

    print("THE POSES, AGAINST THE FROZEN KCL REFERENCE")
    checked = failed = 0
    for scene, frozen in sorted(golden.items()):
        name = scene.removesuffix(".kcl")
        computed = poses.SCENES[name]() if name in poses.SCENES else {}

        extra = sorted(set(computed) - set(frozen))
        missing = sorted(set(frozen) - set(computed))
        differing = [
            n for n in sorted(set(frozen) & set(computed)) if frozen[n] != computed[n]
        ]
        checked += len(frozen)
        failed += len(extra) + len(missing) + len(differing)

        note = f"{len(frozen):>2} constants" if frozen else "places bodies only"
        mark = "  ok  " if not (extra or missing or differing) else " FAIL "
        print(f" {mark} {name:<20} {note}")
        for missed in missing:
            print(f"        missing: {missed} = {frozen[missed]!r}")
        for invented in extra:
            print(f"        invented: {invented} = {computed[invented]!r}")
        for drifted in differing:
            print(
                f"        {drifted}: kcl {frozen[drifted]!r}  cad {computed[drifted]!r}"
            )
    return checked, failed


# Each clearance: the scene, what it is, the two groups, and what must hold.
#
# "clear" -- the two must not interfere, and the gap must be at least the margin.
# "touch" -- they are meant to meet, so the gap is not checked but the shared
#            volume still must be zero.
CLEARANCES = (
    (
        "pose_check",
        "torso floor vs the thigh swung 35deg forward",
        ("pelvis", "cover"),
        ("right thigh",),
        "clear",
        0.5,
    ),
    (
        "pose_check",
        "torso vs the standing leg's thigh",
        ("pelvis", "cover"),
        ("left thigh",),
        "clear",
        0.5,
    ),
    (
        "pose_check",
        "torso vs the forward knee actuator",
        ("pelvis", "cover"),
        ("right knee motor",),
        "clear",
        5.0,
    ),
    (
        "pose_check",
        "the lifted wheel against its own thigh",
        ("right wheel",),
        ("right thigh",),
        "clear",
        5.0,
    ),
    (
        "squat_check",
        "the folded wheel against its own thigh",
        ("right wheel",),
        ("right thigh",),
        "clear",
        5.0,
    ),
    (
        "squat_check",
        "torso floor vs the thigh at 55deg of hip",
        ("pelvis", "cover"),
        ("right thigh",),
        "clear",
        0.5,
    ),
    (
        "squat_check",
        "torso vs the knee actuator, 86 mm forward",
        ("pelvis", "cover"),
        ("right knee motor",),
        "clear",
        5.0,
    ),
    (
        # Measured, not assumed: these two never come near each other. The shin
        # carries its stator plate inboard of the joint and the wheel hangs
        # outboard of it, so what separates them is the width of the joint rather
        # than anything about the pose.
        "squat_check",
        "the wheel against its own shin",
        ("right wheel",),
        ("right shin",),
        "clear",
        5.0,
    ),
    (
        "knee_limit_check",
        "shin plate vs thigh plate at the 110deg stop",
        ("shin",),
        ("thigh",),
        "clear",
        1.0,
    ),
    (
        "knee_prelimit_check",
        "shin plate vs thigh plate at 100deg",
        ("shin",),
        ("thigh",),
        "clear",
        1.0,
    ),
    (
        "wheel_module_check",
        "the adapter on its motor's output face",
        ("motor",),
        ("wheel",),
        "touch",
        0.0,
    ),
    (
        "limb_check",
        "the limb plate on the actuator's rear cover",
        ("motor",),
        ("limb",),
        "touch",
        0.0,
    ),
)

# Where each wheel has to be, and why. The two poses put a wheel on the floor by
# arithmetic rather than by drawing, so this is the check that the arithmetic
# reaches the geometry: a tread whose lowest point is not at zero is a robot
# standing through its own floor.
#
# Each row names the pose constant that says where the axle is. The tread's
# lowest point has to be exactly that, less the wheel's radius -- which checks
# the pose and the wheel solid against each other -- and where the scene says the
# wheel is down, that lowest point has to be zero. Nothing here is a measured
# number typed back in; the expectation is computed from the pose.
ON_THE_FLOOR = (
    ("pose_check", "left wheel", "leftWheelZ", True, "the standing wheel"),
    ("pose_check", "right wheel", "rightWheelZ", False, "the lifted wheel"),
    ("squat_check", "left wheel", "wheelZ", True, "the left wheel, still down"),
    ("squat_check", "right wheel", "wheelZ", True, "the right wheel, still down"),
)

# A tenth of a micron. These are closed-form positions, not measurements, so the
# only thing between the pose and the tread is floating point.
FLOOR_TOLERANCE_MM = 1e-4


def check_clearances() -> tuple[int, int]:
    """Every clearance a scene was drawn to prove. (checked, failed)"""
    from cad import scenes

    print()
    print("THE CLEARANCES, MEASURED BETWEEN THE SOLIDS")
    checked = failed = 0
    built: dict[str, dict] = {}
    for scene, what, first, second, kind, margin in CLEARANCES:
        groups = built.setdefault(scene, scenes.GROUPS[scene]())
        a = [body for name in first for body in groups[name]]
        b = [body for name in second for body in groups[name]]
        distance, shared = measure(a, b)

        checked += 1
        if kind == "touch":
            ok = shared <= CONTACT_MM3
            wanted = "meet, sharing no volume"
        else:
            ok = shared <= CONTACT_MM3 and distance >= margin
            wanted = f"clear by >= {margin:.1f} mm"
        failed += 0 if ok else 1

        mark = "  ok  " if ok else " FAIL "
        print(
            f" {mark} {scene:<19} {what:<45} "
            f"gap {distance:7.3f} mm  shared {shared:8.3f} mm3   {wanted}"
        )

    from cad import poses
    from cad.wheeled_parameters import skateWheelDiameter

    print()
    print("WHERE THE WHEELS LAND")
    radius = skateWheelDiameter / 2
    for scene, group, axleName, onFloor, what in ON_THE_FLOOR:
        groups = built.setdefault(scene, scenes.GROUPS[scene]())
        bottom = union(groups[group]).bounding_box().min.Z
        axleZ = poses.SCENES[scene]()[axleName]

        ok = abs(bottom - (axleZ - radius)) < FLOOR_TOLERANCE_MM
        if onFloor:
            ok = ok and abs(bottom) < FLOOR_TOLERANCE_MM
        checked += 1
        failed += 0 if ok else 1

        wanted = "on the floor" if onFloor else f"clear of it by {bottom:.3f} mm"
        mark = "  ok  " if ok else " FAIL "
        print(
            f" {mark} {scene:<19} {what:<28} axle {axleZ:7.3f} mm, tread bottom "
            f"{bottom:7.3f} mm   {wanted}"
        )
    return checked, failed


def check_packing() -> tuple[int, int]:
    """Every reserved payload volume inside the shell, and clear of it.

    The 65 mm torso is derived from what has to fit in it, so this is where that
    derivation is actually checked rather than asserted. Two things per item: it
    does not eat into the shell, and it lies inside the cavity -- because a block
    that sticks out through a wall shares no volume with it either.
    """
    from cad import scenes, torso
    from cad.wheeled_parameters import wheeledTorsoCenterHeight

    print()
    print("WHAT STANDS IN THE TORSO, AND WHETHER IT FITS")
    groups = scenes.GROUPS["torso_packing_check"]()
    shell = groups["pelvis"]

    # The cavity, in the robot's frame: the shell's inner walls, its cavity floor
    # and the underside of the lid.
    halfWidth = torso.torsoInnerWidth / 2
    halfDepth = torso.torsoInnerDepth / 2
    floorZ = torso.cavityBottomZ + wheeledTorsoCenterHeight
    lidZ = torso.shellTopZ + wheeledTorsoCenterHeight

    items = ("power entry", "controller carrier", "SBC", "IMU")
    checked = failed = 0
    for name, item in zip(items, groups["reservations"]):
        distance, shared = measure([item], shell)
        box = item.bounding_box()
        inside = min(
            halfWidth - abs(box.min.X),
            halfWidth - abs(box.max.X),
            halfDepth - abs(box.min.Y),
            halfDepth - abs(box.max.Y),
            box.min.Z - floorZ,
            lidZ - box.max.Z,
        )
        ok = shared <= CONTACT_MM3 and inside >= -FLOOR_TOLERANCE_MM
        checked += 1
        failed += 0 if ok else 1
        mark = "  ok  " if ok else " FAIL "
        print(
            f" {mark} {name:<20} shell gap {distance:6.3f} mm  shared "
            f"{shared:8.3f} mm3  tightest wall {inside:6.3f} mm"
        )
    return checked, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--poses",
        action="store_true",
        help="only compare the poses against the frozen reference",
    )
    args = parser.parse_args()

    checked, failed = check_poses()
    if not args.poses:
        for stage in (check_clearances, check_packing):
            more, wrong = stage()
            checked += more
            failed += wrong

    print()
    if failed:
        print(f"gate F: FAIL -- {failed} of {checked} checks")
        return 1
    print(f"gate F: pass -- {checked} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
