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
import itertools
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


# Scene constants that have MOVED on purpose since the reference was frozen.
#
# The same idea as gate A's CHANGED and gate B's DEVIATIONS, and written the same
# way for the same reason: BOTH ENDS ARE PINNED, so a value matching neither is
# still a failure and a second change cannot hide inside the first. A pose is not
# loosened here, it is re-frozen at a stated number with a stated cause.
#
# Nothing in these two scenes is a different POSE. The joints are at the angles
# they always were and the wheels land where they always did -- which is the
# check immediately below this one, and it still passes untouched. What moved is
# where the torso's own centre sits, because the torso got taller, and these two
# constants are the height of that centre above the floor.
MOVED = {
    "pose_check": {
        "poseTorsoCenterZ": (
            300.7857332246598,
            311.2857332246598,
            "the torso grew from 65 mm to 86 to carry a battery, so its centre "
            "is 10.5 mm further above a floor that has not moved",
        ),
    },
    "squat_check": {
        "squatTorsoCenterZ": (
            216.95105163371966,
            227.45105163371966,
            "the same 10.5 mm, in the deepest squat",
        ),
    },
}


def check_poses() -> tuple[int, int]:
    """Every scene constant against the frozen KCL reference. (checked, failed)"""
    from cad import poses

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["scenes"]

    print("THE POSES, AGAINST THE FROZEN KCL REFERENCE")
    checked = failed = 0
    for scene, frozen in sorted(golden.items()):
        name = scene.removesuffix(".kcl")
        computed = poses.SCENES[name]() if name in poses.SCENES else {}
        moved = MOVED.get(name, {})

        extra = sorted(set(computed) - set(frozen))
        missing = sorted(set(frozen) - set(computed))
        differing = []
        wrong = []
        for n in sorted(set(frozen) & set(computed)):
            if frozen[n] == computed[n]:
                continue
            if n in moved:
                was, now, _ = moved[n]
                if frozen[n] == was and computed[n] == now:
                    continue
                wrong.append(n)
            else:
                differing.append(n)
        checked += len(frozen)
        failed += len(extra) + len(missing) + len(differing) + len(wrong)

        note = f"{len(frozen):>2} constants" if frozen else "places bodies only"
        if moved and not (extra or missing or differing or wrong):
            note += f", {len(moved)} moved on purpose"
        mark = "  ok  " if not (extra or missing or differing or wrong) else " FAIL "
        print(f" {mark} {name:<20} {note}")
        for missed in missing:
            print(f"        missing: {missed} = {frozen[missed]!r}")
        for invented in extra:
            print(f"        invented: {invented} = {computed[invented]!r}")
        for drifted in differing:
            print(
                f"        {drifted}: kcl {frozen[drifted]!r}  cad {computed[drifted]!r}"
            )
        for bad in wrong:
            was, now, _ = moved[bad]
            print(
                f"        {bad} (moved on purpose, see MOVED): expected "
                f"{was!r} -> {now!r}, kcl says {frozen[bad]!r} and cad says "
                f"{computed[bad]!r}"
            )
        for name_, (was, now, why) in sorted(moved.items()):
            if name_ not in wrong:
                print(f"        MOVED {name_} {was!r} -> {now!r}: {why}")
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

    The 86 mm torso is derived from what has to fit in it, so this is where that
    derivation is actually checked rather than asserted. Two things per item: it
    does not eat into the shell, and it lies inside the cavity -- because a block
    that sticks out through a wall shares no volume with it either.

    THE SHELL IS NOT THE ONLY THING THE PAYLOAD CAN FOUL any more. The battery
    brought ten printed features into the cavity with it -- two rails, four board
    posts and four deck ledges -- and they are part of cad/torso.py's list, so
    they are inside `shell` here and measured along with it. That is deliberate:
    the tightest clearance in this torso is the 1.6 mm between a battery pack and
    a deck ledge, and it would mean nothing if the ledges were left out of the
    body the packing is measured against.
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

    # In cad/electronics.py's torsoReservations() order, which is also the order
    # simulation/robot.py places a mass in each.
    items = ("battery", "power entry", "controller carrier", "SBC", "IMU")
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

    more, wrong = check_fits(items)
    return checked + more, failed + wrong


# The fits inside the torso that are tight enough to be worth a number, and what
# each one has to be. Written as EQUALITIES, which is the difference between this
# table and the clearance table above: these are not "stay clear of each other",
# they are "sit exactly here". A pack that stops resting on its rails, or a deck
# that stops landing on its ledges, is a defect even though nothing interferes
# and nothing in gates A to E would say a word about it.
#
# Two of these numbers were arrived at backwards. The shell's depth was chosen to
# make the first 1.6 mm rather than 0.1, and its width to make the fifth 10.2
# rather than 0.2 -- so if either ever fails, the shell section is what has to
# move, not the tolerance.
FITS = [
    (
        "battery bay vs the four deck ledges",
        "battery",
        "ledges",
        1.6,
        "the tightest clearance in this torso, and what set the shell's depth: "
        "a 68 mm shell leaves a tenth of a millimetre here",
    ),
    (
        "power block vs the four deck ledges",
        "power entry",
        "ledges",
        1.0,
        "the ledges are 5 mm tall and the power block is 30 in a 36 mm band",
    ),
    (
        "battery packs vs their rails",
        "packs",
        "rails",
        0.0,
        "the packs SIT ON the rails, so any gap here means they are floating",
    ),
    (
        "battery packs vs the deck above",
        "packs",
        "deck",
        3.0,
        "the squeeze that holds the packs down, and the only thing that does",
    ),
    (
        "battery bay vs the power block",
        "battery",
        "power entry",
        10.2,
        "the lead chase, and what the shell's extra 10 mm of width bought",
    ),
    (
        "IMU vs the battery over it",
        "IMU",
        "battery",
        3.0,
        "the IMU stays on the shell floor with the battery above it, which is "
        "why cad/torso.py's rails run across the robot rather than along it",
    ),
]


def check_fits(items: tuple) -> tuple[int, int]:
    """The tight fits inside the torso, each against the figure it was drawn to."""
    from cad import deck, electronics, torso

    # Built here rather than lifted out of the scene above, and that matters:
    # the scene places the pelvis at the robot's own standing height and these
    # are all torso-local. Mixing the two frames measures the 281 mm between
    # them instead of the millimetre and a half that is actually in question.
    bodies = {
        "ledges": torso.deckLedges(),
        "rails": torso.batteryRails(),
        "packs": electronics.batteryPacks(),
        "deck": deck.electronicsDeck(),
        **{
            name: [solid] for name, solid in zip(items, electronics.torsoReservations())
        },
    }

    print()
    print("THE FITS INSIDE IT, AGAINST WHAT EACH WAS DRAWN TO")
    checked = failed = 0
    for what, left, right, wanted, why in FITS:
        distance, shared = measure(bodies[left], bodies[right])
        ok = abs(distance - wanted) <= 0.001 and shared <= CONTACT_MM3
        checked += 1
        failed += 0 if ok else 1
        mark = "  ok  " if ok else " FAIL "
        print(
            f" {mark} {what:<38} gap {distance:6.3f} mm  shared "
            f"{shared:8.3f} mm3  wants {wanted:5.2f}"
        )
        if not ok:
            print(f"        {why}")
    return checked, failed


def check_no_clashes() -> tuple[int, int]:
    """Every drawn thing in the torso against every other, pair by pair.

    THE CHECK ABOVE IS ABOUT RESERVATIONS AND THIS ONE IS ABOUT HARDWARE, and the
    difference is the whole point. A reserved volume clearing the shell says the
    layout is possible; it says nothing about whether the connector actually drawn
    in it fouls the standoff actually drawn beside it. The torso holds two battery
    packs, four boards, seven connectors and modules, four looms, twelve standoffs,
    a printed deck and ten printed features inside the shell, and every one of
    them was placed by hand against numbers in another file.

    So they are all measured against each other rather than eyeballed. It is a few
    hundred pairs and it costs a couple of seconds, which is the trade this whole
    gate suite is built on.
    """
    from cad import deck, electronics, torso

    groups = dict(electronics.torsoElectronicsGroups())
    groups["deck"] = deck.electronicsDeck()
    groups["battery rails"] = torso.batteryRails()
    groups["power-entry posts"] = torso.powerEntryPosts()
    groups["deck ledges"] = torso.deckLedges()
    groups["pelvis"] = torso.pelvisShell()

    print()
    print("EVERY DRAWN THING IN THE TORSO, AGAINST EVERY OTHER")
    checked = failed = 0
    for left, right in itertools.combinations(sorted(groups), 2):
        _, shared = measure(groups[left], groups[right])
        checked += 1
        if shared > CONTACT_MM3:
            failed += 1
            print(f"  FAIL  {left:<26} x {right:<26} shares {shared:10.2f} mm3")
    mark = "  ok  " if not failed else " FAIL "
    print(f" {mark} {checked} pairs, {failed} sharing volume")
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
        for stage in (check_clearances, check_packing, check_no_clashes):
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
