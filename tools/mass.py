# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9"]
# ///
"""Measure the printed parts and roll the whole robot's mass up against its ceiling.

Every geometry change is supposed to be reported with its mass delta. This
integrates each printed part's volume at PA12-CF density, multiplies by the count
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
        +0.4,
        "the connector relief cut flush with the waist adds 206 mm3 to each of "
        "the two plates, the register pocket cut clear of the waist takes "
        "11 mm3 off and the waist's two bottom corners carried down to the "
        "plate's rim add 9, so +204 mm3 a limb, twice over on the pair. Gate B "
        "holds the volumes exactly",
    ),
    "cad/shin.py": (
        +0.4,
        "the same three changes on the same shared limb geometry",
    ),
    "cad/torso.py": (
        +66.4,
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
        "to fit inside it",
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
    for part in budget["printed"]:
        summed, merged = weigh(bodies_of(part), density)
        measured[part["file"]] = round(summed, 1)
        printed_total += summed * part["count"]
        union_total += merged * part["count"]

        base = baseline.get(part["file"])
        expected, _ = EXPECTED_CHANGE_G.get(part["file"], (0.0, ""))
        if base is None:
            verdict = "no base"
        elif abs(round(summed, 1) - (base + expected)) <= TOLERANCE_G:
            # A declared change reads as the change rather than as "ok", so the
            # table says which parts are not on their original figure.
            verdict = "ok" if not expected else f"{expected:+.1f}!"
        else:
            verdict = f"{summed - base:+.1f}"
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
