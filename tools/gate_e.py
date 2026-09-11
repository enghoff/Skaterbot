# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9"]
# ///
"""Gate E -- the features that must exist, counted on the finished solid.

This is the gate the migration CREATES rather than one it has to pass, and it is
the answer to the rule in CLAUDE.md that a boolean which succeeds is not a
boolean that worked. The rotor hub carried four filled bolt holes through several
rebuilds, on the joint that takes the actuator's full torque, and nothing
reported it: the KCL executed, the mass looked right, and the only evidence
available was a render taken down the feature's axis with nothing behind it.

Here the finished part is an object with faces, so the question is arithmetic. A
Ø3.4 through-hole leaves a cylindrical face of radius 1.7; six of them leave six.
A hole that a union filled back in leaves none, and this fails.

COUNTING IS NOT ALWAYS ENOUGH, and the second check exists because counting was
not. A pocket a union has eaten a SEGMENT out of still leaves one face at the
right radius, so it passes the count while the thing it locates no longer fits.
Features that have to be whole rather than merely present are listed separately,
in complete_pockets(), and are checked by how far round the circle actually goes.

    uv run tools/gate_e.py                   # every ported piece
    uv run tools/gate_e.py joint-rotor-hub   # just one

These assertions are written against the DRAWING INTENT, not against the golden
reference, so unlike gates A to D they can fail on a part that is a faithful
translation. That is the point: a gate E failure on a piece that passes gate B
means the KCL was wrong and the finding stands on its own. Record it and fix it
in phase 3.

WHAT BELONGS IN HERE, AND WHAT DOES NOT. Assert HOLES, BORES AND POCKETS --
features a boolean can silently fill back in, which is the failure this gate
exists to catch. Do not assert rims and outside diameters. Nothing fills a rim,
and a rim's FACE COUNT is not a property of the design: whatever crosses it
splits it. The clevis makes the point twice over -- the Ø52 cheek rim survives as
one face on the front cheek, and as two on the rear, where the connector flat cuts
it -- so an assertion about how many rim faces there are would be encoding
topology rather than intent, and would break the next time the flat moved.

Free, offline, no engine.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_SurfaceType

# The parts carry Ø in their feature names and Windows consoles default to a
# codepage that cannot print it.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Radii are compared to this many decimal places before being counted, so that a
# Ø3.4 hole and a Ø3.4000001 hole are the same hole.
PLACES = 4


def open_arc(part, radius: float) -> float:
    """How much of the circle at `radius` is still open, in degrees.

    WHY COUNTING FACES IS NOT ENOUGH, learned the hard way twice. A bore that a
    union has eaten a segment out of still leaves ONE cylindrical face at the
    right radius, so the count above passes it. Both the limb's waist plate and
    the rotor hub's arm reach far enough into the rotor disc to fill part of the
    Ø30.4 register pocket, and both did, for as long as the parts have existed:
    314 and 318 degrees open instead of 360, with the actuator's Ø30 register due
    to land on what was left. Nothing said so until the angular span was asked
    for.

    So this is the assertion for a pocket that has to be COMPLETE rather than
    merely present, and it is summed over faces because a boolean is free to
    split one cylinder into several.
    """
    from math import degrees

    total = 0.0
    for face in part.faces():
        surface = BRepAdaptor_Surface(face.wrapped)
        if surface.GetType() != GeomAbs_SurfaceType.GeomAbs_Cylinder:
            continue
        if round(surface.Cylinder().Radius(), PLACES) != round(radius, PLACES):
            continue
        total += surface.LastUParameter() - surface.FirstUParameter()
    return degrees(total)


def cylinder_radii(part) -> Counter:
    """How many cylindrical faces of each radius the finished solid carries.

    The radius is read off the underlying surface rather than from
    Face.radius, which returns None for a face a boolean has trimmed --
    and a trimmed face is exactly what a hole through a curved rim, or a
    cheek cut on the connector chord, leaves behind. Those are the faces
    this gate most needs to see, so the convenience property is not enough.
    """
    found: Counter = Counter()
    for face in part.faces():
        surface = BRepAdaptor_Surface(face.wrapped)
        if surface.GetType() != GeomAbs_SurfaceType.GeomAbs_Cylinder:
            continue
        found[round(surface.Cylinder().Radius(), PLACES)] += 1
    return found


def expectations() -> dict[str, list[tuple[str, float, int]]]:
    """piece -> [(what it is, the radius that proves it, how many), ...]

    Each row is a feature the part must have, named so a failure reads as a
    sentence rather than as a number.
    """
    from cad.electronics import sbcHoleDiameter, sbcPostClearance
    from cad.parameters import (
        bearingSeatBossDiameter,
        bearingSeatDiameter,
        bearingSeatShoulderBore,
        journalSeatDiameter,
        m3CapCounterbore,
        m3Clearance,
        m25InsertBore,
        rotorFilletRadius,
        rotorRegisterDiameter,
    )
    from cad.torso_shell import bossHoleDiameter

    rows = {
        "joint-rotor-hub": [
            # The six that were filled. This is the whole reason the gate exists.
            ("M3 clearance holes on the Ø24 output circle", m3Clearance / 2, 6),
            ("cap counterbores over them", m3CapCounterbore / 2, 6),
            ("Ø30.4 register pocket", rotorRegisterDiameter / 2, 1),
            ("Ø10.2 journal seat", journalSeatDiameter / 2, 1),
            # Not a hole, and the one exception to the rule below. It is here
            # because this blend was wrong for as long as the part existed -- the
            # KCL's solver left the arc's centre unconstrained and built radius
            # 2.9155 where the parameter said 1 -- and nothing measured it. A
            # radius IS a property of the design, unlike a rim's face count, so
            # asserting it is meaningful and it stays asserted.
            ("arm-root blend, tangent both faces", rotorFilletRadius, 1),
        ],
        "joint-stator-clevis": [
            ("M3 clearance holes on the Ø41 rear pattern", m3Clearance / 2, 4),
            (
                "Ø19.2 bearing seat in the front cheek",
                bearingSeatDiameter / 2,
                1,
            ),
            # The seat is 5 mm deep and the cheek is 3, so both of these are
            # the boss that makes up the difference. If a rebuild ever unions the
            # boss on AFTER the seat is cut, the seat fills back in and the
            # shoulder bore is the only cylinder left -- so they are asserted
            # together on purpose.
            (
                "Ø17.5 shoulder the bearing seats against",
                bearingSeatShoulderBore / 2,
                1,
            ),
            (
                "Ø26 boss carrying that shoulder",
                bearingSeatBossDiameter / 2,
                1,
            ),
        ],
        # The limb is the piece the wheeled robot actually prints, and it is here
        # because the register pocket defect below bit it as well as the hub. Its
        # ten M3 holes are the six on the Ø24 output circle plus the four on the
        # Ø41 rear pattern, which are the same clearance and so the same radius.
        "limb-105-unmirrored": [
            (
                "M3 clearance holes, six on the output circle and four on the rear",
                m3Clearance / 2,
                10,
            ),
            ("cap counterbores over the output six", m3CapCounterbore / 2, 6),
            ("Ø30.4 register pocket", rotorRegisterDiameter / 2, 1),
            ("Ø10.2 journal seat", journalSeatDiameter / 2, 1),
        ],
        # The payload boards are not printed, and they are here anyway. They are
        # mocks, but they are mocks that a printed standoff is going to be drawn
        # against, and they are built the one way this gate exists to police --
        # a slab with holes cut in it, standing in a list beside the components
        # that sit on top of it. Union one of those components on by accident and
        # the holes fill back in exactly as the rotor hub's did, with nothing to
        # report it but this count.
        "pcb-power-entry": [
            ("M3 clearance holes, one at each corner", m3Clearance / 2, 4),
        ],
        "pcb-controller-carrier": [
            ("M3 clearance holes, one at each corner", m3Clearance / 2, 4),
            # The two the SBC's posts pass through. Asserted separately from the
            # four above and not merely counted with them, because they are a
            # different diameter and a different job: lose these and the board
            # cannot be fitted at all, while the part still looks right.
            (
                "clearances for the two SBC posts that pass through",
                sbcPostClearance / 2,
                2,
            ),
        ],
        "pcb-sbc": [
            (
                "Ø2.75 mounting holes on the Pi Zero 58 x 23 pattern",
                sbcHoleDiameter / 2,
                4,
            ),
        ],
        # THE PELVIS, asserted here for the first time. It had nothing in this
        # gate while its only round features were the two bearing seats its
        # clevises bring with them, and those are already counted on the clevis
        # itself. The battery gave it ten mounting features of its own, every one
        # of them a pilot hole in a body that stands in a list beside sixteen
        # others -- which is precisely the arrangement that filled the rotor
        # hub's six bolt holes back in. Four of the eight are under the
        # power-entry board and four carry the electronics deck.
        #
        # Each clevis contributes its own bearing seat, shoulder and boss, so
        # those come in twos here where they come in ones on the clevis.
        "pelvis-shell": [
            # Twelve at this radius, not eight: the four cover bosses have
            # carried the same Ø2.5 pilot since the pelvis was first drawn, and
            # they are on the same part. Counting only the new eight would fail
            # the moment anyone looked, so all twelve are named here.
            (
                "pilots: four cover bosses, four power-entry posts, four deck ledges",
                bossHoleDiameter / 2,
                12,
            ),
            ("Ø19.2 bearing seats, one per hip", bearingSeatDiameter / 2, 2),
            (
                "Ø17.5 shoulders the bearings seat against",
                bearingSeatShoulderBore / 2,
                2,
            ),
            ("Ø26 bosses carrying those shoulders", bearingSeatBossDiameter / 2, 2),
            ("M3 clearance holes on the two Ø41 rear patterns", m3Clearance / 2, 8),
        ],
        # THE ELECTRONICS DECK, which is the one piece on this robot with no
        # golden STEP behind it -- the KCL never had it, so gate B cannot say
        # anything about it and this is the only arithmetic it answers to.
        "electronics-deck": [
            ("M3 clearances onto the four wall ledges", m3Clearance / 2, 4),
            ("pilots under the controller's four standoffs", bossHoleDiameter / 2, 4),
            ("M2.5 insert bores in the four SBC posts", m25InsertBore / 2, 4),
        ],
    }
    rows["limb-105-mirrored"] = rows["limb-105-unmirrored"]
    return rows


def complete_pockets() -> dict[str, list[tuple[str, float]]]:
    """piece -> [(what it is, the radius that must be a WHOLE circle), ...]

    Features that have to be complete and not merely present, because something
    is going to be piloted in them. See open_arc() for what filled them in.
    """
    from cad.parameters import rotorRegisterDiameter

    register = ("Ø30.4 register pocket, all the way round", rotorRegisterDiameter / 2)
    return {
        "joint-rotor-hub": [register],
        "limb-105-unmirrored": [register],
        "limb-105-mirrored": [register],
    }


def registry() -> dict[str, callable]:
    from cad import deck, electronics, joint, thigh, torso

    return {
        "joint-stator-clevis": joint.statorClevis,
        "joint-rotor-hub": joint.rotorHub,
        "limb-105-unmirrored": thigh.thighRight,
        "limb-105-mirrored": thigh.thighLeft,
        "pelvis-shell": torso.pelvisShell,
        "electronics-deck": deck.electronicsDeck,
        "pcb-power-entry": electronics.powerEntryBoard,
        "pcb-controller-carrier": electronics.controllerCarrierBoard,
        "pcb-sbc": electronics.sbcBoard,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pieces", nargs="*")
    args = parser.parse_args()

    from cad.finish import united

    built = registry()
    declared = expectations()
    pockets = complete_pockets()
    wanted = args.pieces or sorted(set(declared) | set(pockets))

    failures = 0
    for name in wanted:
        rows = declared.get(name, [])
        whole = pockets.get(name, [])
        if not (rows or whole) or name not in built:
            print(f"{name}: nothing declared yet")
            failures += 1
            continue

        # A printed piece is several interpenetrating bodies, and the features
        # this gate is about are exactly the ones a merge can fill in, so the
        # question is asked of the merged solid rather than of any one body.
        part = united(built[name]())
        found = cylinder_radii(part)
        print(name)
        for what, radius, count in rows:
            got = found.get(round(radius, PLACES), 0)
            ok = got == count
            failures += 0 if ok else 1
            mark = "  ok  " if ok else " FAIL "
            print(f" {mark} {count:>2} x r{radius:<7.3f}  found {got:>2}   {what}")
        for what, radius in whole:
            span = open_arc(part, radius)
            ok = abs(span - 360.0) <= 0.01
            failures += 0 if ok else 1
            mark = "  ok  " if ok else " FAIL "
            print(f" {mark} 360 deg at r{radius:<7.3f}  found {span:6.2f}   {what}")

    print()
    print("gate E: FAIL" if failures else "gate E: pass")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
