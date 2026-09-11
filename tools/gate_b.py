# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9"]
# ///
"""Gate B -- is the ported solid the same solid the Zoo engine built?

The load-bearing gate of docs/BUILD123D_MIGRATION.md. For each piece it imports
the golden STEP that KCL produced, builds the build123d part, and computes the
SYMMETRIC DIFFERENCE between them: the volume of (new - old) plus the volume of
(old - new). Two solids that occupy the same space difference to nothing.

    uv run tools/gate_b.py                   # every piece with a port
    uv run tools/gate_b.py joint-rotor-hub   # just one

Why symmetric difference and not volume. Matching volumes prove very little: a
part that is mirrored, or shifted 5 mm along its axis, or has a hole in the wrong
place, has exactly the volume it should. The symmetric difference is zero only if
every point inside one solid is inside the other.

Why the golden shells are unioned first. A KCL piece exports as several
interpenetrating bodies -- five for a limb, seven for the pelvis shell -- because
the engine would not union them. Adding their volumes counts every overlap twice,
so the reference here is the union, which is also what simulation/ resolves.

The tolerance. reference/golden/step round-trips through OCCT exactly -- STEP is
a BREP format and carries analytic surfaces, not a mesh -- so the noise floor
measured in task 0.3 was 0.0 on every piece. What is left is the difference
between two constructions of nominally the same shape, which shows up as thin
slivers along coincident faces. TOLERANCE is set well below anything that could
be a real feature and well above that.

Free, offline, no engine.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import build123d as bd

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "reference" / "golden" / "step"

sys.path.insert(0, str(ROOT))

# Relative to the part's own volume. A 1e-6 slice of the smallest piece here is
# under 0.01 mm3, which is far smaller than any feature the robot has.
TOLERANCE = 1e-6

# Absolute, for the deviations below, whose whole point is that they are a known
# number rather than a proportion.
DEVIATION_TOLERANCE_MM3 = 1e-3

# DELIBERATE DEPARTURES FROM THE GOLDEN REFERENCE.
#
# A piece listed here is EXPECTED to differ from what the Zoo engine built, by a
# stated amount, for a stated reason. This is not a way of silencing the gate --
# it is the opposite. An unlisted piece must match exactly; a listed one must
# differ by exactly the volume recorded here AND by nothing else. A change that
# removes the intended material and also moves something else fails, because the
# symmetric difference then exceeds what was declared.
#
# Each piece carries a LIST, one entry per change, because a piece accumulates
# them: the migration's discipline is one change, one measured delta, and adding
# a second correction must not blur the first one's figure into a net total that
# no longer says what either change did.
#
# ADDED AND REMOVED ARE DECLARED SEPARATELY, and that is what makes the "and
# nothing else" half of the check work. A net delta is not enough once a piece
# has changes of both signs -- the limb's connector relief adds 206 mm3 and its
# register pocket takes 11 away, and a gate that only knew the net +195 would
# have accepted any pair of numbers 195 apart. So the totals are checked twice
# over: the volume must move by (added - removed), and the symmetric difference
# must be exactly (added + removed), which is only true if nothing else moved.
#
# The golden STEPs are never regenerated to make a gate pass. They are the frozen
# record of what the KCL built, and an entry here is how the project says "we
# changed this on purpose, and here is how much".
DEVIATIONS = {
    "joint-rotor-hub": [
        {
            "removed_mm3": 4.2979372781,
            "why": (
                "the arm-root blend is now a true 1 mm fillet tangent to both "
                "faces, where the KCL's solver had built an unconstrained "
                "sqrt(8.5) = 2.9155 mm arc tangent to neither. Carries less "
                "material and relieves more."
            ),
        },
        {
            "removed_mm3": 8.9406906219,
            "why": (
                "the Ø30.4 register pocket is re-cut after the arm is unioned "
                "on. The arm's top face sits 14.18 mm below the joint axis, "
                "inside the pocket's own 15.2 mm radius, so the union had filled "
                "a 42 degree segment of it back in -- 11 mm wide and the pocket's "
                "full 1.2 mm deep -- and the actuator's Ø30 output register would "
                "have landed on that instead of in the pocket. Same class of "
                "failure as the six bolt holes, missed when those were caught, "
                "and it hid longer because a part-filled pocket still leaves one "
                "cylindrical face for gate E to count."
            ),
        },
    ],
    # Both hands of the limb, and the same two changes on each: the numbers are
    # one mirror image of the other and agree to 1e-5.
    "limb-105-unmirrored": [
        {
            "added_mm3": 206.3020897,
            "why": (
                "the stator plate's connector relief is cut flush with the "
                "waist's flank at 20 mm rather than on the housing's connector "
                "flat at 19. Widening the waist from 30 mm to 40 in August 2026 "
                "had put the limb's edge a millimetre PROUD of the relief, which "
                "is the 1 mm step in the silhouette above the lower joint. See "
                "statorPlateFlatOffset in cad/parameters.py for why the "
                "millimetre is given to the plate rather than taken off the limb."
            ),
        },
        {
            "removed_mm3": 11.4582296,
            "why": (
                "the waist plate is cut clear of the Ø30.4 register pocket, "
                "which it filled a 45.8 degree segment of -- 11.8 mm across and "
                "the pocket's full depth. Same defect as the rotor hub's above, "
                "on the piece the wheeled robot actually prints."
            ),
        },
        {
            "added_mm3": 8.5686735,
            "why": (
                "the waist's two bottom corners carry down to where the Ø52 "
                "stator plate's rim has come out to the waist's own 20 mm. The "
                "end of the waist is held a cap head clear of the rear bolts, "
                "1.28 mm short of that, so the limb's outline dipped in to "
                "follow the rim and then stepped back out to the flank: a notch "
                "1.14 mm deep at each corner with the waist's end face showing "
                "as a ledge in the floor of it. Same class of accident as the "
                "1 mm silhouette step above, one corner away on the same joint, "
                "and found the same way -- by looking at the finished part."
            ),
        },
    ],
    "joint-stator-clevis": [
        {
            "added_mm3": 1280.3560859705,
            "why": (
                "the front cheek is bored Ø19.2 for the bearing itself, where it "
                "was bored Ø30.2 for a turned aluminium carrier that the bearing "
                "then sat in. The carrier was the only bespoke machined part on "
                "the robot and docs/BOM.md had no supplier for it, so it is "
                "deleted and the bearing is bonded into the print with the same "
                "retaining compound. The material is the annulus between the two "
                "bores through a 3 mm cheek, and it goes back INTO the cheek, "
                "which is the wall the joint's load crosses."
            ),
        },
        {
            "added_mm3": 918.4014153780,
            "why": (
                "the boss on the cheek's outer face that carries the bearing's "
                "shoulder: Ø26 x 3.5 mm, with the seat cut 2 mm into it and a "
                "Ø17.5 bore through the 1.5 mm that is left. A 3 mm cheek cannot "
                "seat a 5 mm bearing, so this is what makes the seat full depth "
                "and gives the race a face to sit against, which the deleted "
                "carrier's flange used to be. It stands proud of the pelvis at "
                "±77 mm and the wheels are at ±104, so it costs no envelope."
            ),
        },
    ],
    "pelvis-shell": [
        # A WHOLE-PART RESIZE, and it is a different kind of entry from every
        # other one in this register. The rest are features: a bore, a boss, a
        # relief, each a number you can go and measure on the part. This is the
        # box being a different box -- 125 x 68 x 65 tethered, 135 x 72 x 86
        # carrying a battery -- plus the ten mounting features that came with it.
        #
        # BE CLEAR ABOUT WHAT IS AND IS NOT STILL BEING CHECKED. For a change of
        # this shape the two halves of the test can always be satisfied, because
        # any pair of numbers with the right sum and difference will do, and
        # these two were computed from the built part rather than derived from
        # intent. So this entry proves nothing about the DECISION. What it does
        # still do, and the reason it is written out to ten places rather than
        # waved through, is PIN THE RESULT: the next change to this part, however
        # small, breaks both sums at once and has to come back here. The decision
        # itself is checked elsewhere -- gate A holds every dimension that moved
        # against both of its values, gate E counts the new features on the
        # finished solid, and gate F measures the packing the height was derived
        # from.
        {
            "added_mm3": 119101.4817759765,
            "removed_mm3": 84930.4212284464,
            "why": (
                "the torso grew to carry a battery: 135 x 72 x 86 where it was "
                "125 x 68 x 65. Ten millimetres of width for the pack's lead "
                "chase, four of depth for the electronics deck's ledges and "
                "twenty-one of height for the packs and the deck over them, all "
                "of it derived in cad/wheeled_parameters.py from what has to fit "
                "inside. The added figure also carries the ten mounting features "
                "that came with it -- two battery rails, four posts under the "
                "power-entry board and four deck ledges -- and the removed one "
                "carries the tether slot and its two cable-tie slots, which went "
                "when the umbilical did."
            ),
        },
        {
            "added_mm3": 2560.7121719410,
            "why": (
                "the same bore, on the two hip pitch clevises the pelvis carries: "
                "exactly twice the clevis figure above, which is also the check "
                "that the added material lands in the cheeks and nowhere else."
            ),
        },
        {
            "added_mm3": 1836.8028307560,
            "why": (
                "the same shoulder boss, twice: exactly twice the clevis figure "
                "above again, on the two hips."
            ),
        },
    ],
    # The lid, and this is the cleanest example of what a resize does to this
    # test: the figures below are EXACTLY the new lid's volume and exactly the
    # old lid's, because the two do not overlap at all. The shell's top face went
    # from 30.1 mm above the torso centre to 40.6, which is more than the lid is
    # thick, so the new one stands entirely clear of where the old one was. The
    # part is otherwise the same design at a new size -- cad/torso_shell.py's
    # torsoLid drawn to a 135 x 72 box instead of a 125 x 68 one.
    "torso-cover": [
        {
            "added_mm3": 43963.2153068376,
            "removed_mm3": 38281.9353068376,
            "why": (
                "the same lid on the same four bosses with the same lip and the "
                "same four screws, drawn to the taller, wider box the battery "
                "made of this pelvis. It shares no volume with the lid it "
                "replaces because the shell's top face moved further than the "
                "lid is thick."
            ),
        },
    ],
}
DEVIATIONS["limb-105-mirrored"] = DEVIATIONS["limb-105-unmirrored"]


def registry() -> dict[str, callable]:
    """Piece name -> the function that builds it. Grows as phase 1 lands.

    A builder may return a single solid or a list of interpenetrating bodies,
    which is what the printed pieces are while phase 1 lasts. Either is unioned
    before the comparison, the same way the golden shells are.
    """
    from cad import joint, thigh, torso, wheel_adapter

    return {
        "joint-stator-clevis": joint.statorClevis,
        "joint-rotor-hub": joint.rotorHub,
        "limb-105-unmirrored": thigh.thighRight,
        "limb-105-mirrored": thigh.thighLeft,
        "wheel-adapter-right": wheel_adapter.wheelAdapterRight,
        "wheel-adapter-left": wheel_adapter.wheelAdapterLeft,
        "pelvis-shell": torso.pelvisShell,
        "torso-cover": torso.torsoCover,
    }


def golden_union(path: Path):
    """The golden STEP with its interpenetrating shells resolved into one solid."""
    shape = bd.import_step(str(path))
    solids = shape.solids()
    part = solids[0]
    for extra in solids[1:]:
        part = part + extra
    return part, len(solids)


def volume_of(shape) -> float:
    if shape is None:
        return 0.0
    try:
        return abs(shape.volume)
    except (AttributeError, ValueError):
        return 0.0


def compare(name: str, build) -> tuple[bool, str]:
    step = GOLDEN / f"{name}.step"
    if not step.exists():
        return False, f"{name:<24} no golden STEP at {step.relative_to(ROOT)}"

    old, shells = golden_union(step)

    built = build()
    if isinstance(built, (list, tuple)):
        new = built[0]
        for body in built[1:]:
            new = new + body
    else:
        new = built

    sym = volume_of(new - old) + volume_of(old - new)
    rel = sym / old.volume

    changes = DEVIATIONS.get(name)
    if changes is None:
        ok = rel <= TOLERANCE
        note = ""
    else:
        # Two things have to hold: the volume moved by the stated amount, and
        # nothing moved that was not meant to. The second is the symmetric
        # difference matching added + removed -- if anything else changed, it
        # exceeds that.
        added = sum(c.get("added_mm3", 0.0) for c in changes)
        removed = sum(c.get("removed_mm3", 0.0) for c in changes)
        expected = added - removed
        actual = new.volume - old.volume
        moved_right = abs(actual - expected) <= DEVIATION_TOLERANCE_MM3
        confined = abs(sym - (added + removed)) <= DEVIATION_TOLERANCE_MM3
        ok = moved_right and confined
        if not moved_right:
            note = f"  <-- expected {expected:+.4f} mm3, got {actual:+.4f}"
        elif not confined:
            note = (
                f"  <-- {sym:.4f} mm3 changed, but only "
                f"{added + removed:.4f} was intended"
            )
        else:
            note = (
                f"  ({len(changes)} deviation(s): +{added:.4f} -{removed:.4f} mm3, "
                "as intended)"
            )

    ob, nb = old.bounding_box(), new.bounding_box()
    dbox = max(abs(getattr(nb.min, ax) - getattr(ob.min, ax)) for ax in ("X", "Y", "Z"))
    dbox = max(
        dbox,
        max(abs(getattr(nb.max, ax) - getattr(ob.max, ax)) for ax in ("X", "Y", "Z")),
    )

    verdict = "pass" if ok else "FAIL"
    line = (
        f"{name:<24} {shells:>2} shell(s)  kcl {old.volume:11.4f}  "
        f"cad {new.volume:11.4f}  sym {sym:10.4f} mm3  rel {rel:8.2e}  "
        f"dbox {dbox:7.4f} mm  {verdict}{note}"
    )
    return ok, line


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pieces", nargs="*", help="piece names; default is all ported")
    args = parser.parse_args()

    built = registry()
    wanted = args.pieces or sorted(built)

    failures = 0
    for name in wanted:
        if name not in built:
            print(f"{name:<24} not ported yet")
            failures += 1
            continue
        ok, line = compare(name, built[name])
        print(line)
        failures += 0 if ok else 1

    print()
    deviating = [n for n in wanted if n in DEVIATIONS]
    if deviating:
        print("deliberate departures from the golden reference:")
        for n in deviating:
            for change in DEVIATIONS[n]:
                moved = change.get("added_mm3", -change.get("removed_mm3", 0.0))
                print(f"  {n} {moved:+.4f} mm3: {change['why']}")
        print()
    print(
        f"gate B: {len(wanted) - failures}/{len(wanted)} pieces as expected "
        f"({len(wanted) - len(deviating)} identical to the engine's, "
        f"{len(deviating)} deliberately changed)"
    )
    print("        FAIL" if failures else "        pass")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
