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
    """(distance, shared volume) between two groups of bodies, in mm and mm3.

    THIS USED `a.intersect(b)` AND IT WAS REPORTING ZERO FOR REAL OVERLAPS.
    In this build123d, Shape.intersect() hands back a ShapeList rather than a
    shape, and a ShapeList has no `.volume` -- so every call raised
    AttributeError, and the except clause below was written for a genuinely
    empty intersection and swallowed it. Two solids could share any amount of
    volume at all and this function would say 0.000, which is the number the
    whole packing story rests on.

    It was found in September 2026 by cross-checking one pair by hand against
    `a & b`: 270 mm3 of a reserved volume was inside a printed ledge and every
    check here had passed it. The `&` operator returns a shape, and where there
    is no intersection it returns something with no volume rather than raising,
    so the guard below is now the belt and not the mechanism.

    A distance of zero with a shared volume of zero still means the two touch,
    which several pairs here are meant to do -- see the note at the top.
    """
    a, b = union(first), union(second)
    common = a & b
    try:
        shared = abs(common.volume)
    except (ValueError, AttributeError, TypeError):
        shared = 0.0
    return a.distance_to(b), shared


# Scene constants that have MOVED on purpose since the reference was frozen.
#
# The same idea as gate A's CHANGED and gate B's DEVIATIONS, and written the same
# way for the same reason: BOTH ENDS ARE PINNED, so a value matching neither is
# still a failure and a second change cannot hide inside the first. A pose is not
# loosened here, it is re-frozen at a stated number with a stated cause.
#
WHY_KNEE_STOP = "THE KNEE'S STOP IS MEASURED NOW, NOT INHERITED. 110 degrees came from the walking robot and survived a year only because the flat limbs put thigh and shin in disjoint planes, so the fold had no structural limit to disagree with it. Straddling the knee puts the clevis's saddle back in the plane the shin sweeps -- unavoidably, because a second bearing means reaching round the actuator -- and the shin's waist corners touch that saddle at 103.0 degrees, sharing 62 mm3 at 110. 100 is where the gap is 1.0 mm, the same air the shin's rotor disc has against the far cheek, so one margin covers both."
WHY_FOLLOWS = "the squat is the deepest the knee stop allows, so it follows the stop"
WHY_REVIEW = "the knee review scenes are aimed at the stop and ten degrees under it"

# Nothing in the pose check is a different POSE. Its joints are at the angles
# they always were and its wheels land where they always did -- which is the
# check immediately below this one, and it still passes untouched. What moved
# there is where the torso's own centre sits, because the torso got taller.
#
# THE SQUAT AND THE TWO KNEE REVIEWS ARE DIFFERENT POSES, and that is the one
# thing straddling the knee cost that cannot be bought back with material. See
# the reason on squatKneeAngle below; cad/poses.py derives all of it from a
# single constant so these cannot drift apart.
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
        "squatKneeAngle": (110.0, 100.0, WHY_KNEE_STOP),
        "squatHipAngle": (55.0, 50.0, WHY_FOLLOWS),
        "squatShinAngle": (-55.0, -50.0, WHY_FOLLOWS),
        "legVerticalReach": (120.45105163371967, 134.98539803417327, WHY_FOLLOWS),
        "squatDrop": (89.54894836628033, 75.01460196582673, WHY_FOLLOWS),
        "squatHipPitchZ": (160.45105163371966, 174.98539803417327, WHY_FOLLOWS),
        "squatTorsoCenterZ": (
            216.95105163371966,
            241.98539803417327,
            "10.5 mm of it is the taller torso, on a floor that has not moved; "
            "the other 14.5 is the shallower squat the knee stop now allows",
        ),
        "kneeY": (86.01096465034414, 80.4346665274927, WHY_FOLLOWS),
        "kneeZ": (100.22552581685983, 107.49269901708664, WHY_FOLLOWS),
        "thighCenterY": (43.00548232517207, 40.21733326374635, WHY_FOLLOWS),
        "thighCenterZ": (130.33828872528974, 141.23904852562995, WHY_FOLLOWS),
        "shinCenterY": (43.00548232517207, 40.21733326374635, WHY_FOLLOWS),
        "shinCenterZ": (70.11276290842991, 73.74634950854332, WHY_FOLLOWS),
        # Not a move at all: both wheels are still on the floor, which is the
        # constraint the whole pose is solved against, and the check below
        # measures the tread rather than trusting this. Two different pairs of
        # cosines reach 40 mm and one of them lands a bit short in binary.
        "wheelZ": (
            39.99999999999999,
            40.0,
            "the same 40 mm axle height, reached through a 50 degree shin "
            "instead of a 55 degree one",
        ),
    },
    "knee_limit_check": {
        "kneeLimitAngle": (110.0, 100.0, WHY_KNEE_STOP),
        "shinLimitAngle": (-110.0, -100.0, WHY_KNEE_STOP),
        "lowerLinkCenterY": (-49.33386259126019, -51.70240703314092, WHY_REVIEW),
        "lowerLinkCenterZ": (17.956057524597608, 9.116529327513842, WHY_REVIEW),
    },
    "knee_prelimit_check": {
        "kneePreLimitAngle": (100.0, 90.0, WHY_REVIEW),
        "shinPreLimitAngle": (-100.0, -90.0, WHY_REVIEW),
        "lowerLinkCenterY": (-51.70240703314092, -52.5, WHY_REVIEW),
        "lowerLinkCenterZ": (9.116529327513842, -3.214697847761802e-15, WHY_REVIEW),
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
        "torso floor vs the thigh at 50deg of hip",
        ("pelvis", "cover"),
        ("right thigh",),
        "clear",
        0.5,
    ),
    (
        "squat_check",
        "torso vs the knee actuator, 80 mm forward",
        ("pelvis", "cover"),
        ("right knee motor",),
        "clear",
        5.0,
    ),
    (
        # THE FOLD, IN THE POSE THE ROBOT ACTUALLY HOLDS. The two knee review
        # scenes look at the joint on its own; this is the same contact in the
        # deepest squat, where the leg is loaded and the pose is solved against
        # the floor rather than posed. It was never checked before because it
        # could not fail: the flat limbs put thigh and shin in different planes.
        # The thigh's clevis puts them back in one, so the squat's depth is now
        # a clearance and this row is what holds it.
        "squat_check",
        "the shin against the thigh's knee saddle, folded",
        ("right shin",),
        ("right thigh",),
        "clear",
        1.0,
    ),
    (
        # THE SHIN'S PLATE IS NOT IN limb_check ANY MORE, because that scene now
        # shows a thigh, whose lower end is a clevis. This is where the plate
        # landing flat on the wheel motor's rear cover is held instead: a mating
        # face, so the two meet and share nothing.
        "squat_check",
        "the shin's plate on the wheel motor's rear cover",
        ("right shin",),
        ("right wheel motor",),
        "touch",
        0.0,
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
        # AND THIS ROW IS WHAT SET THE STOP. It used to be a formality -- the
        # note beside the scene said the two lie in different planes and cannot
        # touch -- and straddling the knee made it the binding constraint on how
        # far the leg folds. The margin is 1.0 mm because that is the air the
        # shin's rotor disc has against the far cheek: at 100 degrees the fold is
        # no tighter than the joint's own assembly clearance, and both are this
        # one number. They share 62 mm3 at the 110 degrees the stop used to be.
        "knee_limit_check",
        "the shin against the thigh's knee saddle, at the stop",
        ("shin",),
        ("thigh",),
        "clear",
        1.0,
    ),
    (
        "knee_prelimit_check",
        "the same pair ten degrees short of the stop",
        ("shin",),
        ("thigh",),
        "clear",
        1.0,
    ),
    (
        # The bought metal, seated -- and it is four pieces again. The bearing is
        # bonded into the far cheek and lands on its Ø17.5 shoulder, so it MEETS
        # the thigh. The journal is bought again too, and fitted last: a Ø10
        # sleeve pushed in from outside through that shoulder bore and the
        # bearing, landing on the shin's disc, with an M5 button head pulling it
        # onto a nut captive in the disc. So the second row below is three
        # separate contacts at once -- sleeve on the disc's face, nut on the
        # floor of its pocket, screw in a Ø5.5 hole it must not touch -- and it
        # is the check that the anchor is a fit rather than an interference.
        "knee_limit_check",
        "the far bearing in the thigh's cheek",
        ("hardware",),
        ("thigh",),
        "touch",
        0.0,
    ),
    (
        "knee_limit_check",
        "the bought journal on the shin's disc, in the bearing's bore",
        ("hardware",),
        ("shin",),
        "touch",
        0.0,
    ),
    (
        # AND THE SAME JOURNAL AT THE HIP, which had no row at all while it was a
        # printed stub that could not be got wrong on its own part. It is an
        # anchor cut into the thigh's upper disc now -- a hole, a pocket and a
        # nut sitting in the pocket -- and the piece it sits in is a different
        # print from the shin above, so it is measured on its own.
        "pose_check",
        "the bought journal on the thigh's hip disc",
        ("right hip hardware",),
        ("right thigh",),
        "touch",
        0.0,
    ),
    (
        # THE 1.0 mm THIS ASKED FOR WAS AN ARTEFACT OF THE PROXY, and correcting
        # the proxy is what exposed it. The nearest bought thing to the motor is
        # the M5 nut captive in the rotor plate, and what it is near is the
        # actuator's Ø30 output register -- which the proxy did not draw until
        # 14 September 2026, so this row was measuring against a motor that
        # stopped 1.0 mm short of its own output face. The real figure is
        # journalNutPocketDepth less journalNutThickness: the nut is pulled up
        # against the outboard end of a 3.3 mm pocket and is 2.7 mm thick, so
        # 0.6 mm of that pocket is empty and the register closes the mouth of it
        # 0.6 mm from the nut's face. That is not a clearance anybody chose and
        # it is not free air either -- it is what makes the nut captive, and the
        # nut has never been anywhere else. Asked a shade under the nominal
        # 0.6, as the clevis row below is asked a shade under its 0.3.
        "knee_limit_check",
        "the hardware against the knee actuator it straddles",
        ("hardware",),
        ("motor",),
        "clear",
        0.55,
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
        # THE THIGH'S CLEVIS DOES NOT LAND ON THE REAR COVER, and that is the one
        # place the hip's part behaves differently from the plate it replaces.
        # The plate is a mating face and sits flat on the cover; the clevis's
        # rear cheek has always stood actuatorClearance -- 0.3 mm -- off it, and
        # is pulled down onto it by the four rear bolts. So this asks for a gap
        # rather than for contact, and the number is that clearance.
        "limb_check",
        "the thigh's clevis on the knee actuator's rear cover",
        ("motor",),
        ("limb",),
        "clear",
        0.25,
    ),
    # THE CABLE-TIE ARCHES, at both ends, and this row is why the scene carries
    # the upper actuator at all. The arches stand 4 mm off the same face the
    # actuators sit against, so what stops them fouling a Ø46 body is 30.5 mm of
    # limb between each arch and its joint axis and nothing else. The pair is
    # asked to TOUCH rather than to clear because the disc lands on the output
    # face in this scene as the plate lands on the rear cover below: the
    # assertion is the shared volume, which is zero only if the arch misses.
    (
        "limb_check",
        "the limb, arches and all, against the actuator above",
        ("motor above",),
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

    THE IMU'S SEAT IS THE ONE EXCEPTION, and it is a real one rather than a
    tolerance quietly widened. Every other printed feature in this cavity sits
    BESIDE or BELOW the thing it carries -- the rails stop at the plane the packs
    start on, the ledges stand between two bays, the posts are under a board --
    so a reservation fouling one is always a fault. The IMU's three ribs stand
    INSIDE its reservation by definition: an 11 x 10 board is too small to screw
    to anything, so the only mount available is one that surrounds it. Measured
    against the whole shell the seat reads as 132 mm3 of printed material in the
    payload's own envelope, which is true and is not a finding.

    So the IMU's row is measured against the shell LESS that seat, and the fit
    that actually matters -- the 0.2 mm between the ribs and the board they aim
    -- is asserted in FITS below, exactly as the packs resting on their rails is.
    The seat is still measured against everything else by check_no_clashes().

    WHAT THIS GIVES UP is worth writing down. The 22 x 22 reservation used to say
    that any breakout up to that size would fit, and the seat is cut to 11 x 10.
    The reservation still holds the headroom, but spending it now means
    reprinting the pelvis, because the ribs are part of it.
    """
    from cad import scenes, torso
    from cad.wheeled_parameters import wheeledTorsoCenterHeight

    print()
    print("WHAT STANDS IN THE TORSO, AND WHETHER IT FITS")
    groups = scenes.GROUPS["torso_packing_check"]()
    shell = groups["pelvis"]
    # cad/torso.py returns the seat last, and the docstring above says why the
    # IMU alone is measured without it. Sliced rather than named so that a new
    # feature on the pelvis cannot quietly drop out of this check as well.
    shellLessImuSeat = shell[:-1]

    # The cavity, in the robot's frame: the shell's inner walls, its cavity floor
    # and the underside of the lid.
    halfWidth = torso.torsoInnerWidth / 2
    halfDepth = torso.torsoInnerDepth / 2
    floorZ = torso.cavityBottomZ + wheeledTorsoCenterHeight
    lidZ = torso.shellTopZ + wheeledTorsoCenterHeight

    # In cad/electronics.py's torsoReservations() order, which is also the order
    # simulation/robot.py places a mass in each.
    items = ("battery", "power entry", "controller carrier", "SBC", "IMU", "BMS")
    checked = failed = 0
    for name, item in zip(items, groups["reservations"]):
        against = shellLessImuSeat if name == "IMU" else shell
        distance, shared = measure([item], against)
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
        "power bay vs the four deck ledges",
        "power entry",
        "ledges",
        1.6,
        "the same 1.6 mm the battery clears them by, and it is why the bay is "
        "54 deep rather than the 62 the old power block was: at 62 it runs "
        "270 mm3 straight through two of them",
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
        "deck plate",
        3.0,
        "the squeeze that holds the packs down, and the only thing that does. "
        "Against the PLATE and not the whole deck, because the deck grew two "
        "guides that hang down beside the BMS and one of them is 2.55 mm off the "
        "nearer pack -- a real clearance, but not this one",
    ),
    (
        "battery bay vs the power bay",
        "battery",
        "power entry",
        15.1,
        "slack rather than a chase, and the only number in this table nobody "
        "chose. The shell is as wide as the hip clevises make it, which is "
        "12.9 mm more than the payload needs, and neither bay spends any of it",
    ),
    (
        "IMU vs the battery over it",
        "IMU",
        "battery",
        3.0,
        "the IMU stays on the shell floor with the battery above it, which is "
        "why cad/torso.py's rails run across the robot rather than along it",
    ),
    # THE PANEL HARDWARE, AND WHAT IT HAS TO MISS. There are no bond lines in
    # this robot any more: every one of these three parts holds itself into the
    # wall, so what matters is no longer a gap of exactly half a millimetre but
    # whether the body behind each one has the room its nut and its barrel need.
    # EVERY FIGURE HERE IS WHAT THE DRAWING PRODUCES, and this gate checks it to
    # a thousandth rather than as a minimum, which is what caught the disconnect:
    # while the connector stood here as a 25 x 16 slab -- neither the flange of
    # the part named nor its body -- these three read 6.00, 8.00 and 8.50 and
    # passed, and the real part would have fouled the SBC by 1.8 mm. So what a
    # number in this column means is "the part as AMASS draws it, where this file
    # puts it". Change either and the number changes with it, on purpose.
    (
        "the disconnect vs the deck below it",
        "main disconnect",
        "deck plate",
        9.95,
        "the whole reason this hardware stands above the deck rather than down "
        "in the bay with the bus it breaks: below the plate the rear wall is "
        "committed end to end and a bushing's nut fits nowhere. This is the air "
        "between the XT60E-M's rear body and the top face of the plate its leads "
        "drop through, and it is what a lead needs to turn in. It was 6.00 while "
        "the drawn body was a 16 mm slab; the real connector is 8.1 mm tall, so "
        "the same station leaves four millimetres more",
    ),
    (
        "the disconnect vs the SBC in front of it",
        "main disconnect",
        "SBC board",
        10.3,
        "the price of putting the bus link in the logic band, and the figure to "
        "watch if the SBC ever moves back. THIS IS THE NUMBER THE XT90 DIED ON: "
        "an XT90E-M stands 19.7 mm inside this wall and the board's rear edge is "
        "18.6 mm from it, so the part named here used to overlap the board it "
        "was gated as clearing by 8 mm. The XT60E-M stands 8.3 mm in -- an ear "
        "plate 3.2 thick and a rear body 5.1 behind it -- which is what makes "
        "this station possible at all",
    ),
    (
        "the charge socket vs the disconnect beside it",
        "charge socket",
        "main disconnect",
        7.4,
        "diagonally through the wall, from the XT60E-F's flange edge outside to "
        "the XT60E-M's ear tip inside, which is nearer than anything on the same "
        "side: 9.5 mm between the socket's nut and that ear, 13.4 between its "
        "flange and the disconnect's nose. The two genders of one family stand "
        "side by side here ON PURPOSE -- the key only fits the male and the "
        "charger's lead only the female -- so this station is solved rather "
        "than laid out: the socket went as far outboard as its 34 mm flange "
        "still lands on the wall",
    ),
    (
        "the charge socket's flange vs the deck below it",
        "charge socket",
        "deck plate",
        6.712,
        "also diagonal, flange outside to plate inside; the socket's body, "
        "which is what the leads leave from, stands 8.25 over the plate",
    ),
    (
        "the antenna vs the SBC in front of it",
        "antenna bulkhead",
        "SBC board",
        6.0,
        "THE TIGHTEST FIGURE ON THIS WALL NOW, AND NO LAYOUT CAN MOVE IT: it is "
        "the bushing's own 15 mm of depth against the board's rear edge, and it "
        "is the same 6.00 at any x over the board. The antenna crossed to this "
        "side of the disconnect when the charge socket became a 34 mm flange "
        "and left no room for an 11 mm nut beyond it. The 1.5 mm nut to nut it "
        "used to have with the GX16 is gone with the GX16",
    ),
    (
        "the antenna vs the disconnect beside it",
        "antenna bulkhead",
        "main disconnect",
        7.0,
        "nut circle to ear tip, both on the inside face. Chosen together with "
        "the board figure above: x -8 keeps this at 7 and puts the bushing in "
        "the gap between the SBC's mini-HDMI and its first USB-C rather than "
        "square in front of either",
    ),
    # THE BMS BAY, and all three of its bounds are somebody else's face. It is the
    # last free column in this torso -- 15.1 mm of slack between the two bays that
    # nobody chose, because the shell is as wide as the hip clevises make it -- so
    # every one of these is what stops the bay being bigger.
    (
        "BMS bay vs the deck that closes it",
        "BMS",
        "deck",
        0.0,
        "the deck's two guides come down the bay's own SIDES to take the board's "
        "top edge, so they touch it -- which they must, because the bay is the "
        "slot. The 1.5 mm over the bay's top face is the plate, and it is the "
        "row two below",
    ),
    (
        "BMS bay vs the guides that hold it",
        "BMS",
        "BMS guides",
        0.0,
        "the board SITS ON the guides, so any gap here means it is floating -- "
        "the same test the packs on their rails get",
    ),
    # AND THE BOARD ITSELF, not only the volume reserved for it. These two are the
    # whole of the hold-down and they are a pair: 4 mm of slot under it and 1.5 mm
    # of air over it, so it can rise 1.5 and is still 2.5 mm engaged. Get them the
    # wrong way round -- which is what a full-height stand-in hid until a real
    # board was chosen -- and the card lifts clear of its guides.
    (
        "BMS board vs the deck plate over it",
        "BMS board",
        "deck plate",
        1.5,
        "the board can rise by THIS before the plate stops it, and the slot under "
        "it is 4 mm deep, so it cannot leave its guides. 8.5 mm here with the "
        "board stood on the bay floor is the defect this pair was added to catch",
    ),
    (
        "BMS board vs the deck's top guides",
        "BMS board",
        "deck",
        0.4,
        "the running fit at the card's top edge, and half the shim: 9 mm of slot "
        "on an 8.2 mm board. The board is held at BOTH ends because of it -- at "
        "the bottom alone it is a cantilever 33 mm long on 4 mm of engagement",
    ),
    (
        "BMS board vs its card guides",
        "BMS board",
        "BMS guides",
        0.0,
        "its bottom edge SITS ON the slot floor, so any gap here means the board "
        "is hanging on nothing -- the same test the packs on their rails get",
    ),
    # THE BUS MONITOR, WHICH IS SCREWED DOWN NOW RATHER THAN TAPED, and both of
    # these arrived with that change. It hung under the deck for one revision,
    # which tied that plate to the torso by the board's own wiring; it is bolted
    # to the pelvis's rear wall instead, and these two are what that mount is.
    (
        "IMU board vs the ribs that aim it",
        "IMU board",
        "IMU seat",
        0.2,
        "the one board too small to take a screw, so a printed seat decides "
        "where it points and adhesive holds it down. Any looser than this and "
        "it can turn in its own seat, which is the whole thing the seat is for",
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
        # The plate on its own, which is the first body cad/deck.py returns.
        # Sliced rather than named for the same reason the shell is: the whole
        # deck now includes the two guides that come down BESIDE the board, and
        # measuring the air OVER it has to ignore them.
        "deck plate": [deck.electronicsDeck()[0]],
        "IMU seat": torso.imuSeat(),
        "BMS guides": torso.bmsGuides(),
        # The monitor's two pads on their own, sliced out of the pelvis the same
        # way the ledges and rails are: measuring the board ONTO them has to
        # ignore the wall they stand on.
        **{
            name: electronics.torsoElectronicsGroups()[name]
            for name in (
                "IMU board",
                "main disconnect",
                "charge socket",
                "antenna bulkhead",
                "SBC board",
                "BMS board",
                "bus monitor",
                "distribution board",
            )
        },
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
    groups["board posts"] = torso.powerEntryPosts()
    groups["deck ledges"] = torso.deckLedges()
    groups["IMU seat"] = torso.imuSeat()
    groups["BMS guides"] = torso.bmsGuides()
    # The shell WITHOUT the four feature sets listed above it, because
    # pelvisShell() returns all of them in one list and comparing a part with
    # its own features is not a finding. Seven bodies: the shell, four cover
    # bosses and two hip clevises, which is what the pelvis was before the
    # battery gave it ten more and the mounting sweep an eleventh.
    groups["pelvis"] = torso.pelvisShell()[:7]

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
