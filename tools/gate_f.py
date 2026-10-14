# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1"]
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
            312.7857332246598,
            "the torso grew from 65 mm to 86 to carry a battery, and to 89 when "
            "the packs were measured, so its centre is 12 mm further above a "
            "floor that has not moved",
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
            243.48539803417327,
            "12 mm of it is the taller torso, on a floor that has not moved; "
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
        # against the outboard end of a 4.3 mm pocket and is 4.0 mm thick, so
        # 0.3 mm of that pocket is empty and the register closes the mouth of it
        # 0.3 mm from the nut's face. That is not a clearance anybody chose and
        # it is not free air either -- it is what makes the nut captive, and the
        # nut has never been anywhere else. Asked a shade under the nominal
        # 0.3, as the clevis row below is asked a shade under its 0.3. It was
        # 0.6 of a 3.3 mm pocket round a 2.7 mm nut until 14 October 2026, when
        # the pocket was deepened for an ordinary DIN 934 nut as bought; the
        # nut is drawn at that standard's 4.0, so the 3.9 delivered leaves 0.4.
        "knee_limit_check",
        "the hardware against the knee actuator it straddles",
        ("hardware",),
        ("motor",),
        "clear",
        0.25,
    ),
    (
        "wheel_module_check",
        "the adapter on its motor's output face",
        ("motor",),
        ("wheel adapter", "skate wheel", "wheel cap", "wheel clamp"),
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

    The 89 mm torso is derived from what has to fit in it, so this is where that
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

    THE POWER SWITCH BOARD'S PAD IS THE SECOND SUCH CASE, September 2026, and for
    the same reason: it is a pad off the right-hand wall carrying a board that
    lives INSIDE the power bay, so it stands in that bay's own reserved volume by
    definition. Its row was measured against the shell less that pad, and the fit
    that matters -- the board sitting on it -- is asserted in FITS below. The pad
    came off when the board took the bought board's four posts, and the slice that
    left it out went on leaving out whatever body was second to last: a hoist lug,
    then a hip-arm brace, neither of them anywhere near the bay. Its row is
    measured against the whole shell since 2026-10-14.

    THE BATTERY'S RAILS ARE THE THIRD, 2026-09-30. The packs shrank inside a
    bay that did not, so the stop on each rail's end, which catches the foot of
    a pack's end face, stands in the bay's own reserved volume by definition --
    and so do the wall pads the block's side foam bears on, which reach in from
    the long walls to it and which the pelvis carries too. The battery's row is measured against the shell less its
    rails and those three, and what they have to do -- carry the packs, stop
    them and hold them -- is asserted face by face in
    check_battery_hold_down().

    THE IMU'S ROW WAS THE FIRST SUCH CASE, measured without the floor seat it
    stood in, until the IMU went under the deck on 2026-10-14. Its reservation is
    the board hanging under the deck now, nowhere near the shell, and is measured
    against all of it; the seat came off the pelvis the same day.
    """
    from cad import scenes, torso
    from cad.wheeled_parameters import wheeledTorsoCenterHeight

    print()
    print("WHAT STANDS IN THE TORSO, AND WHETHER IT FITS")
    groups = scenes.GROUPS["torso_packing_check"]()
    shell = groups["pelvis"]
    # The docstring above says why a reservation is measured without its OWN
    # mount and against everything else. Sliced rather than named so that a new
    # feature on the pelvis cannot quietly drop out of this check as well.
    #
    # The rails and then the wall pads come straight after the shell, its four
    # cover bosses and its two hip clevises -- the seven check_no_clashes()
    # calls the pelvis proper.
    rails = len(torso.batteryRails()) + len(torso.batteryPads())
    shellLessRails = shell[:7] + shell[7 + rails :]

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
    without = {
        "battery": shellLessRails,
    }
    for name, item in zip(items, groups["reservations"]):
        against = without.get(name, shell)
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
        0.6,
        "what set the shell's depth at 1.6: a 68 mm shell left a tenth of a "
        "millimetre here. 0.6 since 2026-09-30, when the ledges went a "
        "millimetre deeper for plastic round their screws' threads; the bay is "
        "sized for packs that do not exist, and the packs in it are 7.6 mm away",
    ),
    (
        "power bay vs the four deck ledges",
        "power entry",
        "ledges",
        0.6,
        "the same clearance the battery bay has, and it is why the bay is 54 "
        "deep rather than the 62 the old power block was: at 62 it runs 270 mm3 "
        "straight through two of them. 1.6 until the ledges went a millimetre "
        "deeper; nothing drawn in the bay comes within 5.5 mm",
    ),
    (
        "battery packs vs their rails",
        "packs",
        "rails",
        0.0,
        "the packs SIT ON the rails, so any gap here means they are floating",
    ),
    # THE ROW THAT STOOD HERE, "battery packs vs the deck above, 3.0 mm", called
    # that gap "the squeeze that holds the packs down". It was air: nothing filled
    # it, so it held nothing, and the gate passed it for as long as the gap was the
    # size drawn. What holds the packs since 2026-09-30 is measured by
    # check_battery_hold_down() below, face by face.
    (
        "battery bay vs the power bay",
        "battery",
        "power entry",
        15.1,
        "slack rather than a chase, and the only number in this table nobody "
        "chose. The shell is as wide as the hip clevises make it, which is "
        "12.9 mm more than the payload needs, and neither bay spends any of it",
    ),
    # "IMU vs the battery over it", 3.0, stood here while the IMU was on the
    # shell floor under the battery. It went under the deck on 2026-10-14, and
    # its rows are at the end of this table.
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
        "the rear button vs the deck below it",
        "on/off button",
        "deck plate",
        5.25,
        "The button returns to its original rear-wall station.",
    ),
    (
        "the rear button vs the core board",
        "on/off button",
        "WeAct core board",
        5.4,
        "The original rear-wall body clearance to the core board.",
    ),
    (
        "the charge inlet vs the deck below it",
        "charge inlet",
        "deck plate",
        8.0,
        "Owner-assumed 12 mm flange level with the button at z23.5; its lower edge is 8.0 mm above the deck.",
    ),
    (
        "the side antenna vs the carrier",
        "antenna bulkhead",
        "controller carrier board",
        2.15,
        "The 9.5 mm internal shoulder clears the carrier's top edge.",
    ),
    (
        "the side antenna vs the core board",
        "antenna bulkhead",
        "WeAct core board",
        4.593446901,
        "The coax bushing lies behind the core board on the left side.",
    ),
    # THE BMS HAD FIVE ROWS HERE while it stood on edge in the gap between the
    # two bays: its bay against the deck and its guides, and the board against
    # the plate over it, the deck's top guides and its card guides. It went
    # between the battery packs on 2026-10-05, into one block with them, and the
    # guides went with the bay; check_battery_hold_down() measures the block.
    # THE BUS MONITOR HAD TWO ROWS HERE while it stood on two pads off the
    # pelvis's rear wall. It rides on the controller carrier now, and
    # electrical/carrier_pcb.py measures it there against everything in this
    # torso, so the rows went with the pads.
    #
    # THE SBC ON ITS STANDOFFS, September 2026, when it came off the deck's
    # printed posts and onto bought M2.5 x 10 pillars on the controller carrier.
    (
        "SBC board on its four standoffs",
        "SBC board",
        "SBC standoffs",
        0.0,
        "the SBC SITS ON its standoffs, so any gap here means it is hanging on "
        "its screws -- and the height of every drawn thing on this board follows "
        "from that one face",
    ),
    (
        "SBC standoff screw heads vs the deck plate",
        "SBC standoffs",
        "deck plate",
        0.5,
        "the four M2.5 heads hang under the controller carrier in the 3 mm its "
        "own standoffs leave over the deck. A longer head, or a carrier standoff "
        "bought 2 mm short, and they land on the plate and tilt the board",
    ),
    # THE POWER SWITCH BOARD, September 2026, and its numbers are the whole of
    # how it is held and what it has to miss. Four screws go down through it and
    # an M3 nut on a washer into the printed posts. It stood 8 mm over a bought
    # distribution board on printed spacers until 2026-10-07; that board went,
    # and this one stands on the nuts where it stood and carries the motor
    # outputs itself.
    (
        "power switch board on its standoffs",
        "power switch board",
        "power switch standoffs",
        0.0,
        "the board SITS ON the four nuts, so any gap here means it is hanging on "
        "its screws -- the same test the packs on their rails get. They are the "
        "bought board's own four posts on its 45 mm square, so the pelvis did "
        "not change when that board went",
    ),
    (
        "the power switch parts vs the deck",
        "power switch parts",
        "deck plate",
        15.6,
        "THE TWO TO-220 SWITCHES ARE THE TALLEST THING ON THIS BOARD AGAIN, "
        "standing 18.8 mm on their leads and leaving 15.6 mm under the deck "
        "since the board came down onto the posts on 2026-10-07; it was 6.0 "
        "while it stood over the bought distribution board. "
        "It was 1.1 mm while the PBV-F1 Kelvin shunt stood here at 20.7 mm "
        "installed, and that shunt went with the current measurement on "
        "2026-09-16; it was 3.0 until the measured battery packs raised the "
        "deck 3 mm on 2026-10-05. The PCB placement check also checks each "
        "real part separately",
    ),
    (
        # THE BANK USED TO BE THE THING THIS BOARD STOPPED SHORT OF, 2 mm off
        # four reserved cans of 16 x 25 across the whole front of the bay. It
        # stands ON the board now -- two 10 x 16 cans, which is what docs/BOM.md
        # has bought since it first named a part -- so what is worth measuring
        # is no longer a gap beside them but the air over them.
        "the capacitor bank vs the deck plate over it",
        "capacitor bank",
        "deck plate",
        18.4,
        "a 16 mm can standing on this board, under a deck 34.4 mm above it "
        "since the board came down 9.6 mm onto the posts. The two switches "
        "beside them are what governs this bay's height, at 15.6",
    ),
    # THE IMU UNDER THE DECK, 2026-10-14. It was a board in a three-rib seat on
    # the shell floor, "IMU board vs the ribs that aim it" at 0.2, until its
    # socket was found to be on its underside. These are the whole of how it is
    # held now: it hangs chip down in two grooved rails off the deck's
    # underside, the deck's post on its socket face and the socket itself clear.
    (
        "IMU socket under the deck",
        "IMU socket",
        "deck plate",
        0.5,
        "the socket's 2.95 is JST's catalogue and not measured, and the deck's "
        "grooves set the board's height, so the socket stands this far off the "
        "plate rather than on it: a socket taller than drawn would otherwise jam "
        "the board in its grooves. It bore on the plate for its first afternoon",
    ),
    (
        "IMU board against its post",
        "IMU board",
        "IMU post",
        0.0,
        "and the deck's post bears on its socket face at the rear, so that the "
        "board hangs flat",
    ),
    (
        "IMU board in its rails",
        "IMU board",
        "IMU rails",
        0.0,
        "the lips are drawn TOUCHING the board's chip face and the stops its "
        "rear edge, which is what holds it without glue: a gap here is a board "
        "that rattles or has not gone home. Its sides stand 0.2 off the walls, "
        "which is what the 2 degrees of yaw the firmware expects comes from",
    ),
    (
        "IMU board under its ledges",
        "IMU board",
        "IMU ledges",
        0.0,
        "and the ledges over the lips are drawn touching its socket face, so "
        "that each side is held in a groove on both faces",
    ),
    (
        "IMU jumpers vs the short ledge",
        "IMU jumpers",
        "IMU ledges",
        0.3,
        "the left-hand ledge stands between the ADD pad and the 0 and 1 blobs, "
        "which are off a photograph to a tenth; less than this and a ledge "
        "lands on solder and tilts the board",
    ),
    (
        "IMU chip vs the capacitor bank under it",
        "IMU sensor",
        "capacitor bank",
        12.27,
        "what is under the IMU's chip, and the warmest thing that is: the power "
        "switch board's two TO-220 switches are further over, at x 47.5 and "
        "beyond, which is why the IMU is at x 38 and not over them",
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
        # And the IMU's two rails and its post, which follow the plate.
        "IMU rails": deck.electronicsDeck()[1:3],
        "IMU post": deck.electronicsDeck()[3:],
        # The rails' two ledges on their own, which are part of the rails above.
        "IMU ledges": [deck.imuLedge(-1), deck.imuLedge(1)],
        **{
            name: electronics.torsoElectronicsGroups()[name]
            for name in (
                "IMU board",
                "IMU jumpers",
                "IMU sensor",
                "IMU socket",
                "on/off button",
                "controller carrier board",
                "WeAct core board",
                "charge inlet",
                "antenna bulkhead",
                "SBC board",
                "SBC standoffs",
                "BMS board",
                "bus monitor",
                "capacitor bank",
                "power switch board",
                "power switch parts",
                "power switch standoffs",
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


def check_battery_hold_down() -> tuple[int, int]:
    """Each pack held on every side, and every piece of foam squeezed but not flat.

    cad/electronics.py's hold-down block says what holds the battery block -- two
    packs and the BMS between them, assembled into one piece since 2026-10-05 --
    in each of six directions: a rail under each pack, a stop on the rail's end,
    the wall pads straight on each pack's outer face since 2026-10-06, and foam
    between each pack and the deck and the left wall.
    The wall pads are part of the pelvis, so every face but the top pads' is
    made before the deck goes on. Each
    of those is a pair of drawn bodies that has to TOUCH -- distance zero and no
    shared volume -- and a pair that has come apart by any amount is a pack free
    to move by that amount. The rail's stop is measured on its own since the
    packs were measured: the rail drops away under the lead end, so the pack
    touching the rail no longer says it has reached the stop.

    The foam is drawn at the thickness it is squeezed to, so the other half of
    the test is that each piece is thinner than the sheet it is cut from, and not
    so much thinner that it has been squeezed flat and stopped pushing. Half the
    sheet is the floor for that: closed-cell EVA takes a set beyond it.
    """
    from cad import deck, torso
    from cad import electronics as e

    packs = {"rear": e.batteryPacks()[0], "front": e.batteryPacks()[1]}
    rails = {"front": torso.batteryRails()[0], "rear": torso.batteryRails()[1]}
    foam = e.batteryFoam()
    pads = {"front": foam[0], "rear": foam[1]}
    ends = {"front": foam[2], "rear": foam[3]}
    wallPads = torso.batteryPads()
    lowPads = {"front": wallPads[0:3], "rear": wallPads[4:7]}
    highPads = {"front": wallPads[3:4], "rear": wallPads[7:8]}
    plate = deck.electronicsDeck()[0]
    wall = torso.pelvisShell()[0]

    print()
    print("WHAT HOLDS EACH BATTERY PACK, FACE BY FACE")
    checked = failed = 0
    rows = []
    for side in ("front", "rear"):
        pack = [packs[side]]
        rows += [
            (f"{side} pack on its rail", pack, [rails[side]]),
            (f"{side} pack under its top pad", pack, [pads[side]]),
            (f"{side} top pad under the deck", [pads[side]], [plate]),
            (f"{side} pack on the three low pads", pack, lowPads[side]),
            (f"{side} pack on the high pad", pack, highPads[side]),
            (f"{side} pack against its end pad", pack, [ends[side]]),
            (f"{side} end pad against the left wall", [ends[side]], [wall]),
        ]
    for what, left, right in rows:
        distance, shared = measure(left, right)
        ok = distance <= 0.001 and shared <= CONTACT_MM3
        checked += 1
        failed += 0 if ok else 1
        mark = "  ok  " if ok else " FAIL "
        print(
            f" {mark} {what:<38} gap {distance:6.3f} mm  shared {shared:8.3f} mm3"
            "  wants contact"
        )
    # Each pack has to bear on all three of its low pads and not merely the
    # nearest, or the block is held at one point along its length.
    for side in ("front", "rear"):
        for i, padBody in enumerate(lowPads[side]):
            distance, shared = measure([packs[side]], [padBody])
            ok = distance <= 0.001 and shared <= CONTACT_MM3
            checked += 1
            failed += 0 if ok else 1
            mark = "  ok  " if ok else " FAIL "
            what = f"{side} pack on low pad {i + 1}"
            print(
                f" {mark} {what:<38} gap {distance:6.3f} mm  shared {shared:8.3f} mm3"
                "  wants contact"
            )

    # No wall pad reaches more than batteryPadReach up the pack from its bottom
    # face, the owner's limit. A pad's top is its bounding box's, since the
    # lead-in chamfer is below it and its underside below that.
    for side in ("front", "rear"):
        for i, padBody in enumerate([*lowPads[side], *highPads[side]]):
            reach = padBody.bounding_box().max.Z - e.lowerBandZ
            ok = reach <= e.batteryPadReach + 1e-6
            checked += 1
            failed += 0 if ok else 1
            mark = "  ok  " if ok else " FAIL "
            what = f"{side} {'high pad' if i == 3 else f'low pad {i + 1}'} top"
            print(
                f" {mark} {what:<38} {reach:5.2f} mm up the pack"
                f"   wants {e.batteryPadReach:.1f} at most"
            )

    for what, squeezed in (
        ("top pads", e.batteryFoamTop),
        ("end pads", e.batteryFoamEnd),
    ):
        ratio = squeezed / e.batteryFoamFree
        ok = 0.5 <= ratio < 1.0
        checked += 1
        failed += 0 if ok else 1
        mark = "  ok  " if ok else " FAIL "
        print(
            f" {mark} {what:<38} {squeezed:5.2f} of {e.batteryFoamFree:4.1f} mm, "
            f"squeezed {100 * (1 - ratio):4.1f} %   wants 0 to 50 %"
        )

    # THE LEAD END, measured 2026-10-05. A pack is 17 x 35 only over the 65 mm
    # furthest from its leads; the last 12 mm is up to 19 x 38, and nobody knows
    # which faces the extra is on. So each lead end is tested here as the box it
    # could fill whichever way the extra falls -- the whole 2 mm on either face,
    # the whole 3 mm above or below -- and nothing printed and no foam may share
    # any volume with that box. Touching is allowed, because two faces do and are
    # meant to: the stop meets the end face, end-on, and the rail's full-height
    # length ends where the body does. What this catches is a wall pad, a rail
    # or a strip of foam run on past the 65 mm, the BMS between the packs moved
    # out between their lead ends, or a deck brought down into the lead end's
    # 38 mm. The pair beside it is the stop: the rail's top no
    # longer stands under the lead end, so its contact with the rail no longer
    # says the stop is reached, and it is measured on its own.
    from build123d import Box, Pos

    spareY = e.batteryPackLeadThickness - e.batteryPackThickness
    spareZ = e.batteryPackLeadWidth - e.batteryPackWidth
    lengthX = e.batteryPackRightX - e.batteryPackBodyEndX
    innerY = e.batteryPackGap / 2 - spareY
    outerY = e.batteryPackOuterY + spareY
    heightZ = e.batteryPackLeadWidth + spareZ
    printed = [*torso.pelvisShell(), *deck.electronicsDeck()]
    bms = e.torsoElectronicsGroups()["BMS board"]
    stopHeight = e.lowerBandZ + e.batteryRailStopHeight - torso.cavityBottomZ
    for side, sy in (("front", 1), ("rear", -1)):
        envelope = Pos(
            e.batteryPackBodyEndX + lengthX / 2,
            sy * (innerY + outerY) / 2,
            e.lowerBandZ - spareZ + heightZ / 2,
        ) * Box(lengthX, outerY - innerY, heightZ)
        stop = Pos(
            torso.batteryRailEndX - torso.batteryRailStopLength / 2,
            sy * torso.batteryRailY,
            torso.cavityBottomZ + stopHeight / 2,
        ) * Box(torso.batteryRailStopLength, torso.batteryRailThickness, stopHeight)
        for what, left, right, wants in (
            (f"{side} pack against its end stop", [packs[side]], [stop], "contact"),
            (f"{side} lead end, worst case, vs print", [envelope], printed, "none"),
            (f"{side} lead end, worst case, vs foam", [envelope], foam, "none"),
            (f"{side} lead end, worst case, vs the BMS", [envelope], bms, "none"),
        ):
            distance, shared = measure(left, right)
            if wants == "contact":
                ok = distance <= 0.001 and shared <= CONTACT_MM3
            else:
                ok = shared <= CONTACT_MM3
            checked += 1
            failed += 0 if ok else 1
            mark = "  ok  " if ok else " FAIL "
            want = "wants contact" if wants == "contact" else "wants none shared"
            print(
                f" {mark} {what:<38} gap {distance:6.3f} mm  shared {shared:8.3f} mm3"
                f"  {want}"
            )
    return checked, failed


# How far under a feature's underside the ground is looked for. A face resting
# on another reads as touching to machine precision; a tenth of a millimetre is
# far below any gap that could be printed and far above that noise.
FOOTING_PROBE_MM = 0.1


def footing(body, ground) -> tuple[float, float]:
    """(underside area, the part of it resting on the ground), in mm2.

    Every face of the body that points straight down is pushed FOOTING_PROBE_MM
    further down, and what of that slab lies inside the ground is the part of
    the face that is carried.
    """
    from build123d import GeomType, extrude

    total = carried = 0.0
    for face in body.faces():
        if face.geom_type != GeomType.PLANE or face.normal_at().Z > -0.999:
            continue
        slab = extrude(face, amount=FOOTING_PROBE_MM, dir=(0, 0, -1))
        common = slab & ground
        try:
            inside = abs(common.volume) if common is not None else 0.0
        except (ValueError, AttributeError, TypeError):
            inside = 0.0
        total += face.area
        carried += inside / FOOTING_PROBE_MM
    return total, carried


def check_footings() -> tuple[int, int]:
    """Everything that stands in the cavity stands on something, all along.

    WHY THIS EXISTS. The battery's two fences were drawn standing on the left hip
    saddle's top over the saddle's length, because the saddle's bounding box
    reaches 26 mm either side of the centre line. Its top reaches 15, and the
    fences stand at 21: for 45 mm of their 75 each hung 9 mm over the floor from
    the 30 mm that did reach it. Every gate passed that. It was one solid, so the
    export and tools/check.py were content; each layer of it touched the layer
    below somewhere, so tools/gate_g.py found no island; and nothing it was meant
    to hold was drawn anywhere it was not. It was seen by eye.

    So each feature that stands up from the floor or the saddle top has every
    downward face measured against the shell and the two hip clevises, and all
    of each face has to rest on them. The wall-hung features -- the cover bosses,
    the deck ledges, the hoist lugs and, since 2026-10-05, the battery's wall
    pads -- hang on purpose and are not here. The fences and the fin that stood
    here until then went with the BMS's floor guides.
    """
    from cad import torso

    print()
    print("WHAT EACH FEATURE IN THE CAVITY STANDS ON")
    pelvis = torso.pelvisShell()
    ground = union([pelvis[0], pelvis[5], pelvis[6]])
    features = [
        ("front battery rail", torso.batteryRails()[0]),
        ("rear battery rail", torso.batteryRails()[1]),
        *(
            (f"power board post {i + 1}", post)
            for i, post in enumerate(torso.powerEntryPosts())
        ),
    ]
    checked = failed = 0
    for what, body in features:
        total, carried = footing(body, ground)
        share = carried / total if total else 0.0
        ok = share >= 0.999
        checked += 1
        failed += 0 if ok else 1
        mark = "  ok  " if ok else " FAIL "
        print(
            f" {mark} {what:<38} {carried:7.1f} of {total:7.1f} mm2 underneath "
            f"rests on the pelvis ({100 * share:5.1f} %)"
        )
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
    groups["battery pads"] = torso.batteryPads()
    groups["board posts"] = torso.powerEntryPosts()
    groups["deck ledges"] = torso.deckLedges()
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


def check_journal_fastening() -> tuple[int, int]:
    """Check thread reach and what the screw's head lands on, which collision
    tests miss.

    THE WASHER IS GONE, 2026-09-30. A DIN 433 5.3 x 9 x 1 sat under the head to
    keep the tip off the motor, small-series because an ordinary Ø10 one reaches
    the bearing, and nobody in India stocks it. The printed sleeve is a
    millimetre longer instead, so the head lands on the sleeve's own end, in the
    same place, and what has to be checked is that it touches the sleeve and
    keeps clear of the bearing.
    """
    from cad import hardware as h
    from cad.parameters import rotorHubInnerX

    screw = h.journalScrew()
    nut = h.journalNut()
    tip = screw.bounding_box().min.X
    nut_box = nut.bounding_box()
    engaged = nut_box.max.X - max(nut_box.min.X, tip)
    tip_air = tip - rotorHubInnerX
    bearing_air, clash = measure([screw], [h.bearing()])
    seat_gap, seat_shared = measure([screw], [h.journalSleeve()])
    checks = [
        ("nut engagement >= 3.0 mm", engaged >= 3.0 - 1e-6, engaged),
        ("screw tip air >= 0.8 mm", tip_air >= 0.8 - 1e-6, tip_air),
        (
            "screw clears bearing by 0.5 mm",
            bearing_air >= 0.5 - 1e-6 and clash < 1e-6,
            bearing_air,
        ),
        (
            "screw head on the sleeve's end",
            seat_gap < 1e-6 and seat_shared < 1e-6,
            seat_gap,
        ),
    ]
    print("\nJOURNAL FASTENING")
    for label, passed, value in checks:
        print(f"  {'ok' if passed else 'FAIL'}  {label}: {value:.3f} mm")
    return len(checks), sum(not passed for _, passed, _ in checks)


def check_journal_nut_pocket() -> tuple[int, int]:
    """Check the journal's nut against its pocket as the hexagon it is.

    THE SCENES CANNOT ASK THIS. They draw the nut as a Ø8 cylinder, because they
    do not turn a joint's hardware with its limb, and a cylinder has no corners:
    so they passed a nut that spun freely in a pocket 9.3 across its flats, with
    corners of at most 9.24, until 14 October 2026. In a pocket the motor closes
    and on a screw driven from the far side, a nut that turns is a joint that
    cannot be tightened.

    So the disc is built on its own and the nuts are drawn here as hexagons, in
    the disc's frame, the pocket's way round. The largest DIN 934 M5 nut, seated
    on the floor, must share nothing with it: that is the nut going in, and
    landing on the floor rather than on anything standing in it, which is how
    cad/finish.py's chamfer once took the seat. The smallest, turned 30 degrees so
    its corners face the flats, must not fit at all: a nut that cannot be there
    cannot turn through there. It is the narrowest nut a turn has to pass, 8.79
    across its corners against 8.3 across the flats, and no sideways slop helps
    it, because it is that wide across every pair of flats at once. Both are
    asked of the disc as drawn and of the finished disc a printer gets.

    THE NUTS HAVE THEIR FACE CHAMFERS, because every ISO 4032 nut does and the
    seat depends on it. The bearing face is a circle no wider than the flats, and
    the corners rise off it at the chamfer's angle, so a nut's corners never
    reach the floor. A sharp hexagon would put them there, on the floor's round,
    and fail this by five microns of nothing real. Each nut gets the chamfer that
    is hardest on its question: the largest the shallowest, 15 degrees from a
    face as wide as its flats, so it keeps the most corner to seat; the smallest
    the steepest, 30 degrees from the narrowest face the standard allows, so it
    keeps the least corner to be stopped by.
    """
    from math import radians, tan

    from build123d import (
        Axis,
        BuildSketch,
        Cone,
        Cylinder,
        Plane,
        Pos,
        RegularPolygon,
        Rot,
        extrude,
    )

    from cad.finish import one_solid
    from cad.joint import outputDisc
    from cad.parameters import (
        journalNutAcrossCornersMin,
        journalNutAcrossFlats,
        journalNutAcrossFlatsMin,
        journalNutPocketDepth,
        journalNutThickness,
        rotorHubInnerX,
    )

    # ISO 4032 M5: the bearing face is at least 6.9 across, and the face chamfer
    # runs 15 to 30 degrees. A catalogue table, like the nut's other figures in
    # cad/parameters.py.
    bearingFaceMin = 6.9
    floor = rotorHubInnerX + journalNutPocketDepth
    t = journalNutThickness

    def hexNut(acrossFlats: float, face: float, chamfer: float):
        with BuildSketch(Plane.YZ) as profile:
            RegularPolygon(acrossFlats / 2, 6, major_radius=False)
        nut = Pos(floor - t, 0, 0) * extrude(profile.sketch, amount=t)
        # A cone from each face, widening at the chamfer's angle off the face
        # and still wider than the corners at the other one.
        flare = face / 2 + t / tan(radians(chamfer))
        for at, turn in ((floor - t / 2, 90), (floor - t / 2, -90)):
            nut = nut & (Pos(at, 0, 0) * Rot(0, turn, 0) * Cone(face / 2, flare, t))
        return nut

    largest = hexNut(journalNutAcrossFlats, journalNutAcrossFlats, 15)
    corners = (
        Pos(floor - t / 2, 0, 0)
        * Rot(0, 90, 0)
        * Cylinder(journalNutAcrossCornersMin / 2, t)
    )
    smallest = hexNut(journalNutAcrossFlatsMin, bearingFaceMin, 30) & corners
    smallest = smallest.rotate(Axis.X, 30)

    drawn = outputDisc(journalAnchor=True)
    finished, _, _ = one_solid([drawn])
    checks = []
    for which, disc in (("as drawn", drawn), ("finished", finished)):
        seat, shared = measure([largest], [disc])
        checks.append(
            (
                f"{which}: largest nut seats on the floor, sharing nothing",
                seat < 1e-6 and shared < CONTACT_MM3,
                shared,
            )
        )
        _, blocked = measure([smallest], [disc])
        checks.append(
            (
                f"{which}: smallest nut cannot turn, sharing > 1 mm3 at 30 deg",
                blocked > 1.0,
                blocked,
            )
        )
    proud = journalNutPocketDepth - journalNutThickness
    checks.append(
        (
            "largest nut stays under the seating face, mm",
            proud >= 0.2 - 1e-6,
            proud,
        )
    )
    print("\nJOURNAL NUT IN ITS POCKET")
    for label, passed, value in checks:
        print(f"  {'ok' if passed else 'FAIL'}  {label}: {value:.3f}")
    return len(checks), sum(not passed for _, passed, _ in checks)


def check_antenna_base() -> tuple[int, int]:
    """Check the owner's antenna diameter plus radial hand clearance."""
    from build123d import Cylinder, Pos, Rot

    from cad import electronics as e
    from cad import torso
    from cad.parameters import hoistLugProud

    base = (
        Pos(
            -torso.torsoShellWidth / 2 - hoistLugProud / 2,
            e.antennaSideY,
            e.antennaSideZ,
        )
        * Rot(0, 90, 0)
        * Cylinder(e.antennaBaseDiameter / 2, hoistLugProud)
    )
    gap, shared = measure([base], [torso.hoistLugs()[1]])
    ok = gap >= e.antennaBaseClearance and shared <= CONTACT_MM3
    print(
        f" {'ok' if ok else 'FAIL'} 12 mm antenna base vs left hoist lug: "
        f"{gap:.3f} mm clearance, wants >= {e.antennaBaseClearance:.1f} mm"
    )
    return 1, int(not ok)


def check_charge_inlet_boss() -> tuple[int, int]:
    """The full interior flange must clear the rear right lid screw boss."""
    from cad import electronics as e
    from cad import torso
    from cad.torso_shell import coverBoss

    boss = coverBoss(torso.bossX, -torso.bossY, torso.shellTopZ)
    gap, shared = measure(e.torsoElectronicsGroups()["charge inlet"], [boss])
    ok = gap >= e.chargeInletBossClearance - 1e-6 and shared <= CONTACT_MM3
    print(
        f" {'ok' if ok else 'FAIL'} XT60 interior flange vs lid screw boss: "
        f"{gap:.3f} mm clearance, wants >= {e.chargeInletBossClearance:.1f} mm"
    )
    return 1, int(not ok)


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
        for stage in (
            check_clearances,
            check_packing,
            check_battery_hold_down,
            check_footings,
            check_no_clashes,
            check_journal_fastening,
            check_journal_nut_pocket,
            check_antenna_base,
            check_charge_inlet_boss,
        ):
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
