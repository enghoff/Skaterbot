# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9"]
# ///
"""Measure the printed parts and roll the whole robot's mass up against its ceiling.

Every geometry change is supposed to be reported with its mass delta. This
integrates each printed part's volume at the print material's density,
multiplies by the count
the robot carries, adds the bought and estimated items, and compares the total to
the ceiling. Parts, counts, allowances and the functions that build them all live
in mass_budget.toml beside this file; nothing is hard-coded here.

    uv run tools/mass.py                    # the table, and the delta from baseline
    uv run tools/mass.py --union            # also what the parts weigh unioned
    uv run tools/mass.py --gate             # fail if a part has moved (gate C)
    uv run tools/mass.py --save-baseline    # make this the new baseline

Free and offline, in about a second. It used to be four metered engine
executions, which is why the discipline around it was "measure when the geometry
has to be right" rather than "measure every time"; there is no longer any reason
not to run it on every change.

TWO FIGURES, AND THE DIFFERENCE BETWEEN THEM MATTERS. A printed piece is several
interpenetrating bodies, so there are two honest ways to weigh it:

  sum    add the bodies up and count every overlap twice. This is what the Zoo
         engine reported and therefore what the baseline holds, and it is the
         column reported by default, because the bias errs UPWARD against a
         ceiling.
  union  resolve the overlaps first. This is the real mass, and it is what
         simulation/ has always used -- about 19 g lighter across the robot.

--gate compares SUM against the baseline part by part rather than on the total,
because a total can come out right by cancellation between two parts that are
both wrong. A part that is MEANT to have moved is declared in EXPECTED_CHANGE_G
below with the grams and the reason, and then has to have moved by exactly that;
the baseline itself is the engine's record and is not rewritten to suit. Once phase 3 of docs/BUILD123D_MIGRATION.md unions these parts for
real, the union column becomes the only one, and the drop is a MEASUREMENT
ARTEFACT rather than a saving.

A further bias, unchanged by any of this: printed infill is not modelled, so a
real print comes out lighter than its solid volume suggests.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUDGET = HERE / "mass_budget.toml"
BASELINE = HERE / "mass_baseline.json"

sys.path.insert(0, str(ROOT))

# A tenth of a gram is the resolution the baseline is stored at, so that is what
# a comparison against it can mean.
TOLERANCE_G = 0.05

# PARTS THAT ARE MEANT TO HAVE MOVED, and by how much.
#
# The baseline is the engine's own figures from before the migration and is not
# recomputed -- its note says so, and it is the same principle as the golden STEPs
# that gate B compares against: a reference you rewrite to make a gate pass is
# not a reference. So a deliberate design change is declared here instead, as the
# grams it is expected to add or remove, and the gate then requires the part to
# have moved by THAT and not merely to have moved.
#
# --save-baseline still exists and still overwrites everything. It is for the day
# the engine-era figures stop being the reference at all, which is the end of
# phase 3, and not for silencing a row.
EXPECTED_CHANGE_G = {
    "cad/thigh.py": (
        +21.9,
        "THE JOURNAL IS NOT PART OF THIS PRINT AND CANNOT BE, which is -0.2 g of "
        "the figure. It was a bonded dowel, then a printed stub worth 1.4 g on "
        "the pair, and neither can be assembled: both stand proud of the output "
        "disc before the joint is closed, and the fork is one print whose cheeks "
        "are 4.7 mm closer together than the motor and disc that have to enter "
        "it. So the journal is a Ø10 sleeve printed on its own and "
        "fitted from outside at the end, and this print carries what it screws into -- no seat, a Ø5.5 hole "
        "and a hex pocket for a captive M5 nut, which take 103 mm3 more out of "
        "each limb than the old blind seat did. cad/parameters.py carries the "
        "interference and what the anchor is worth against the stub. "
        "THE KNEE IS STRADDLED, which is 19.2 g of the figure and 9.6 g a "
        "thigh: the flat plate on the knee motor's rear cover is cad/joint.py's "
        "statorClevis instead, two cheeks reaching round the motor to a 6800 "
        "bonded into the far one. It buys the joint that carries the whole leg "
        "below it a second bearing, where it had only the actuator's own output "
        "bearing on a 22 mm overhang -- the question DAMIAO have never answered. "
        "The waist gives 6.1 mm of its length back at that end, because what it "
        "lands on is the saddle rather than a disc, and the clevis-end cable-tie "
        "arch moves out to 42 mm to stand clear of that saddle. Neither shows "
        "separately here; gate E counts the three features the clevis brings and "
        "gate F measures what the saddle costs the knee's fold. There is no "
        "golden STEP for a thigh any more, so this line and gate E are the whole "
        "of its arithmetic. The remaining 1.5 g is the shin's figure below, "
        "which is the limb geometry the two still share: "
        "the connector relief cut flush with the waist adds 206 mm3 to each of "
        "the two plates and the waist's two bottom corners carried down to the "
        "plate's rim add 9, so +215 mm3 a limb, twice over on the pair. The "
        "waist used to be cut clear of the register pocket for 11 mm3 more and "
        "is not any longer, there being no pocket to clear. Gate B "
        "holds the volumes exactly. The other 1.1 g is the two cable-tie "
        "arches each limb now carries on its inboard face, 237 mm3 apiece: the "
        "harness had nothing to be tied to anywhere outside the pelvis, and a "
        "slot cut through the waist instead would have taken section off the "
        "plate that breaks first. Moving the connector relief to the aft flank, "
        "so the leads leave on the side the pelvis's ports are on, costs no "
        "mass at all -- it fills one segment of the plate in and takes the "
        "identical segment off the other. "
        "AND THE Ø30.4 REGISTER POCKET IS RETIRED, 14 September 2026, which is "
        "1.7 g of this line and about 0.8 g a limb. The actuator's Ø30 output "
        "register stands 1.0 mm proud of its housing -- the body is 36.9 mm "
        "long where the actuator is 37.9, both figures on the vendor 2D print "
        "-- so the plate seats on the register and clears the housing, where "
        "this model had it landing on the housing with the register filling a "
        "1.2 mm pocket in it. The plate was seating on nothing at all, with the "
        "six M3 that carry the joint's whole output torque clamping across the "
        "gap. The pocket is simply not cut now and the plate lands flat, so it "
        "keeps 871 mm3 the golden throws away, less 65 the six output holes "
        "take crossing 1.2 mm more plate. Turning the pocket inside out instead "
        "-- a Ø36 x 0.7 rim to pilot on -- was drawn first and taken off, "
        "because the rim's height and the plate's air over the housing are the "
        "same millimetre shared out and a rim that prints long lands on the "
        "housing and stops the plate seating at all. What the plate gives up is "
        "its pilot, which cad/parameters.py argues is worth less than the "
        "clearance. Gate B holds the volumes exactly and tools/gate_e.py "
        "asserts the millimetre in front of the plate is empty. AND THE KNEE "
        "SADDLE IS DRAINED, 21 September 2026, which is the 0.1 g this line "
        "came DOWN by. The saddle is a closed box, and on the union of the "
        "finished bodies it measured as a sealed 7.66 cm3 cavity -- un-fused "
        "powder with no way out of a sintered print, about 3.4 g of it in "
        "each thigh that nothing on this table counts. One Ø4 bore through "
        "both side walls opens it. The 0.1 g is the wall that bore takes, "
        "60.3 mm3 a saddle; the powder it lets out is worth thirty times as "
        "much and was never on the bill to lose.",
    ),
    "cad/shin.py": (
        +2.9,
        "the same changes on the same shared limb geometry, which now includes "
        "the journal's anchor: a shin carries one at its knee end exactly as a "
        "thigh does at its hip, and the sleeve itself is a print of its own, "
        "fitted last at both. THE SHIN DID NOT "
        "TAKE THE CLEVIS: the wheel joint carries the wheel alone on a 12 mm "
        "arm, which is a third of the knee's overhang and inside what the flat "
        "limbs already ask of the same bearing, so it stays a plate. That is "
        "also why this piece keeps the golden STEP gate B holds it against, and "
        "the thigh has none. "
        "AND THE Ø30.4 REGISTER POCKET IS RETIRED, 14 September 2026, which is "
        "1.7 g of this line and about 0.8 g a limb. The actuator's Ø30 output "
        "register stands 1.0 mm proud of its housing -- the body is 36.9 mm "
        "long where the actuator is 37.9, both figures on the vendor 2D print "
        "-- so the plate seats on the register and clears the housing, where "
        "this model had it landing on the housing with the register filling a "
        "1.2 mm pocket in it. The plate was seating on nothing at all, with the "
        "six M3 that carry the joint's whole output torque clamping across the "
        "gap. The pocket is simply not cut now and the plate lands flat, so it "
        "keeps 871 mm3 the golden throws away, less 65 the six output holes "
        "take crossing 1.2 mm more plate. Turning the pocket inside out instead "
        "-- a Ø36 x 0.7 rim to pilot on -- was drawn first and taken off, "
        "because the rim's height and the plate's air over the housing are the "
        "same millimetre shared out and a rim that prints long lands on the "
        "housing and stops the plate seating at all. What the plate gives up is "
        "its pilot, which cad/parameters.py argues is worth less than the "
        "clearance. Gate B holds the volumes exactly and tools/gate_e.py "
        "asserts the millimetre in front of the plate is empty.",
    ),
    "cad/wheel_adapter.py": (
        +1.7,
        "THE Ø30.4 REGISTER POCKET IS RETIRED, and this is the first time this "
        "piece has been off the engine's figure at all. It shares "
        "cad/joint.py's output disc with the limbs, so it takes the correction "
        "with them: the actuator's Ø30 output register stands 1.0 mm proud of "
        "its housing rather than 1.2 mm into the plate, so the plate seats on "
        "the register and clears the housing, and the pocket that used to pilot "
        "it is not cut at all. 806 mm3 an adapter, and gate B holds it exactly. "
        "Of the three pieces that share this disc it loses least by having no "
        "pilot: there is no far bearing on a wheel joint, and half a per cent "
        "of runout on an Ø80 wheel is nothing.",
    ),
    "cad/torso.py": (
        +68.1,
        "the torso grew from 125 x 68 x 65 to 153.9 x 72 x 86 in two steps: to "
        "141 wide to carry a battery and a bought distribution board, with the "
        "ten features that hold them -- two rails under the packs, four posts on "
        "the board's own 45 mm square and four ledges carrying the electronics "
        "deck -- and then to 153.9 to bring the flank out to the plane the hip "
        "saddle ends at, which is 12.8 g of wall, floor and lid for a step the "
        "saddle no longer stands proud of. 61.7 g of the figure is the bigger "
        "box and the features, and 4.7 is the older bearing-seat "
        "change this line already carried -- "
        "the two hip pitch cheeks are bored Ø19.2 for the bearing itself "
        "rather than Ø30.2 for the turned carrier it used to sit in, and each "
        "carries a Ø26 boss for the bearing's shoulder where the carrier's "
        "flange used to be: 2 561 mm3 of PA12 back into the wall the joint's "
        "load crosses, and 1 837 standing off its outer face. The carrier was "
        "6.4 g of aluminium apiece. Gate B holds every one of those volumes "
        "exactly, and cad/wheeled_parameters.py derives the box from what has "
        "to fit inside it. The figure then moved 1.0 g DOWN on balance when "
        "everything in the torso was given a mount: three coarse apertures "
        "where three precision connector cutouts were, four fixings for the "
        "connector panel that carries them now, and four strap slots through the "
        "battery rails, against the two things the sweep added -- the IMU's "
        "three-rib seat and the two card guides a 6S BMS stands on edge in. "
        "It then came back UP 0.8 g when that BMS made the balance port "
        "redundant: the board balances the string on the cell taps inside the "
        "shell, so the seven-way socket in the rear wall went, and 703 mm3 of "
        "wall the aperture used to take is wall again. A further 0.9 g went "
        "into those two card guides when a board was finally chosen and they "
        "could be cut to it rather than to its class: a 33 mm card stood on the "
        "bay floor lifts clear of a 4 mm slot before the deck over it can stop "
        "it, so the guides rise 7 mm to hang the board 1.5 mm under the deck, "
        "and the slot widens from a bare PCB to the board's whole 8.2 mm "
        "envelope. 871 mm3 of PA12, and gate B holds it exactly. It moved a "
        "last 0.4 g UP when the connector panel was deleted and this wall took "
        "its own hardware back: three coarse apertures and four screw holes "
        "filled in, against the disconnect's cut, two screw holes, a 16 mm hole "
        "for the charge socket and a 6.5 for the antenna bulkhead. The 8.6 g "
        "panel it replaced is off this bill altogether. It then gained a final "
        "0.8 g when the disconnect's own cut was corrected: this wall was cut "
        "25 x 16 with two Ø3.4 screw holes for an AMASS XT90E-M on a "
        "marketplace listing's figures, and the maker's drawing makes that part "
        "42.0 across with its screws 32.4 apart and 19.7 mm of it inside the "
        "wall -- too deep for this cavity at any station the charge inlet "
        "leaves free. What is here now is an XT60E-M cut to its 14.20 nose, "
        "14.7 x 7.2 with two Ø2.8 holes, which is 720 mm3 of wall the pelvis "
        "used to throw away. And it gave 0.1 g of that back when the charge "
        "socket became the disconnect's female twin: an XT60E-F body cut of "
        "19.2 x 12.0 and two screw holes where the GX16's 16 mm hole was, the "
        "antenna's hole moved to the far side of the disconnect, and every "
        "screw on the wall down to M2, which is 84 mm3 net. Gate B holds it "
        "exactly. It then took 705 mm3 in two bodies when the INA226 bus "
        "monitor stopped being held by tape -- two piloted pads on the rear "
        "wall -- and gave every one of them back on 14 September 2026, when "
        "the controller carrier grew from 76 mm wide to 140 to carry that "
        "monitor and the logic BEC itself. Both boards are on the carrier now, "
        "so the pads carried nothing and came off, and this shell is 0.6 g "
        "lighter for it. THE SHUNT MOVED ONTO THE POWER SWITCH BOARD AND THEN "
        "OFF THE ROBOT ALTOGETHER: the current measurement was deleted on "
        "16 September 2026, so there is no shunt, and no twisted pair up to "
        "the carrier's J7 either. The monitor stays on the carrier reading bus "
        "voltage on its own pin, which never went through the shunt. None of "
        "it ever cost this shell anything. "
        "THE "
        "POWER SWITCH BOARD COSTS THIS SHELL NOTHING AT ALL: it took a 320 mm3 "
        "pad on the right-hand wall for a third screw while it was a rectangle "
        "over half the bought distribution board, and when it grew to that "
        "board's own 50 x 50 outline it took all four of that board's screws "
        "instead and the pad came off again. AND THE MAIN DISCONNECT WENT ON 2026-09-16, which is 4.83 mm3 and not a gram: a momentary button that commands the switch board replaced the loop key, and three holes in the rear wall became one -- a 14.7 x 7.2 nose cut and two O2.4 ear holes out, a single O12.2 bushing hole in, at x -44 rather than x 18 because there is 11.2 mm of clear depth behind the old station and a panel switch needs more. The wall loses the thinnest material on this shell with it, the 1.45 mm between each ear screw and its cutout. tools/gate_b.py holds the split. "
        "AND BOTH HIP SADDLES ARE DRAINED, 21 September 2026, which is the "
        "0.1 g this line came DOWN by: the same Ø4 bore as the knee's, twice, "
        "opening two sealed 7.53 cm3 cavities that between them held about "
        "6.8 g of powder this shell would have been weighed with and the CAD "
        "never counted. 120.6 mm3 of wall on the pair, and gate B holds it "
        "exactly.",
    ),
}


def bodies_of(part: dict) -> list:
    """Every body a printed entry's `measure` functions build.

    The engine weighed a KCL file, which meant whatever solids that file left
    standing -- both hands of a mirrored pair, or a shell and its lid. `measure`
    is that list written down, so the figure means the same thing it used to.
    """
    module = importlib.import_module(
        part["file"].removesuffix(".py").replace("/", ".").replace("\\", ".")
    )
    bodies: list = []
    for name in part["measure"]:
        built = getattr(module, name)()
        bodies += list(built) if isinstance(built, (list, tuple)) else [built]
    return bodies


def weigh(bodies: list, density: float) -> tuple[float, float]:
    """(sum of the bodies, the union of them), in grams.

    A body that measures zero is refused outright rather than silently added in.
    Nothing on this robot has no volume, so a zero means the solid is malformed --
    the way a twice-mirrored gusset did, with a correct bounding box, working
    booleans and inverted faces. A union re-orients what it swallows and hides
    that; adding the bodies up is what exposes it, so this is the place to check.
    """
    empty = [i for i, body in enumerate(bodies) if body.volume <= 0.0]
    if empty:
        raise ValueError(
            f"bodies {empty} measure zero volume -- malformed solids, "
            f"probably inverted by a double mirror"
        )
    total = sum(body.volume for body in bodies)
    merged = bodies[0]
    for body in bodies[1:]:
        merged = merged + body
    # density is kg/m3; a mm3 of it weighs density * 1e-6 grams.
    return total * density * 1e-6, merged.volume * density * 1e-6


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--union", action="store_true", help="show what the parts weigh unioned"
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="fail if any part differs from the baseline, or the ceiling is passed",
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="write the measured per-part masses to mass_baseline.json",
    )
    args = parser.parse_args(argv)

    budget = tomllib.loads(BUDGET.read_text(encoding="utf-8"))
    density = budget["material"]["density"]
    ceiling = budget["ceiling_g"]

    stored = (
        json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    )
    baseline = stored.get("parts", {})

    width = max(
        max(len(p["label"]) for p in budget["printed"]),
        max(len(f["label"]) for f in budget["fixed"]),
    )
    pad = f" {'':8} {'':7}" if args.union else ""

    head = f"{'part':<{width}}  {'sum g':>8}"
    if args.union:
        head += f" {'union g':>8} {'bias g':>7}"
    head += f" {'n':>3} {'total g':>9} {'vs base':>8}"
    print(head)
    print("-" * len(head))

    failures = 0
    measured: dict[str, float] = {}
    printed_total = union_total = 0.0
    # The baseline is a record of GEOMETRY, weighed at whatever the material was
    # when it was taken. Comparing today's parts against it at today's density
    # would report every one of them as moved the day the material changed, which
    # is exactly the drift this gate exists NOT to report. So the comparison is
    # made at the baseline's own density and the roll-up at the real one.
    baseline_density = budget["material"].get("baseline_density", density)
    for part in budget["printed"]:
        summed, merged = weigh(bodies_of(part), density)
        against_base, _ = weigh(bodies_of(part), baseline_density)
        measured[part["file"]] = round(against_base, 1)
        printed_total += summed * part["count"]
        union_total += merged * part["count"]

        base = baseline.get(part["file"])
        expected, _ = EXPECTED_CHANGE_G.get(part["file"], (0.0, ""))
        if base is None:
            verdict = "no base"
        elif abs(round(against_base, 1) - (base + expected)) <= TOLERANCE_G:
            # A declared change reads as the change rather than as "ok", so the
            # table says which parts are not on their original figure.
            verdict = "ok" if not expected else f"{expected:+.1f}!"
        else:
            verdict = f"{against_base - base:+.1f}"
            failures += 1

        row = f"{part['label']:<{width}}  {summed:8.1f}"
        if args.union:
            row += f" {merged:8.1f} {summed - merged:7.1f}"
        row += f" {part['count']:3d} {summed * part['count']:9.1f} {verdict:>8}"
        print(row)

    print(f"{'printed structure':<{width}}  {'':8}{pad} {'':3} {printed_total:9.1f}")
    print()

    # A bought item is quoted either per unit with a count, or as one figure for
    # the whole allowance. mass_budget.toml uses each_g for the first and total_g
    # for the second, and the distinction is meaningful: each_g is a thing you can
    # put on a scale, total_g is an estimate for a bag of parts.
    total = printed_total
    for item in budget["fixed"]:
        each = item.get("each_g", item.get("total_g"))
        count = item.get("count", 1) if "each_g" in item else 1
        total += each * count
        print(
            f"{item['label']:<{width}}  {each:8.1f}{pad} {count:3d} {each * count:9.1f}"
        )

    print("-" * len(head))
    print(f"{'total':<{width}}  {'':8}{pad} {'':3} {total:9.1f}")
    print(f"{'ceiling':<{width}}  {'':8}{pad} {'':3} {ceiling:9.1f}")
    headroom = ceiling - total
    verdict = "under" if headroom > 0 else "OVER THE CEILING BY"
    print(
        f"{'headroom':<{width}}  {'':8}{pad} {'':3} {abs(headroom):9.1f}  ({verdict})"
    )

    if args.union:
        print()
        print(
            "overlap counted twice across the printed structure: "
            f"{printed_total - union_total:.1f} g"
        )

    previous = stored.get("total_g")
    if previous is not None:
        change = total - previous
        if abs(change) < 0.05:
            print("\nNo change against the baseline.")
        else:
            print(f"\nAgainst the baseline: {change:+.1f} g (was {previous:.1f} g).")

    declared = [
        (part["label"], EXPECTED_CHANGE_G[part["file"]])
        for part in budget["printed"]
        if part["file"] in EXPECTED_CHANGE_G
    ]
    if declared:
        print("\nparts deliberately off the engine's figures (marked ! above):")
        for label, (grams, why) in declared:
            print(f"  {label}, {grams:+.1f} g: {why}")

    if args.save_baseline:
        stored = {
            "note": stored.get(
                "note",
                "Per-part mass in grams at the density in tools/mass_budget.toml.",
            ),
            "parts": measured,
            "total_g": round(total, 1),
        }
        BASELINE.write_text(json.dumps(stored, indent=2) + "\n", encoding="utf-8")
        print(f"\nBaseline written to {BASELINE.relative_to(ROOT)}.")

    if args.gate:
        print()
        bad = failures or headroom <= 0
        print("gate C: FAIL" if bad else "gate C: pass")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
