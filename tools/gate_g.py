# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1",
#                 "trimesh==4.5.3", "numpy<2.3", "scipy", "networkx", "rtree",
#                 "shapely"]
# ///
"""Gate G -- every printed piece prints as one part, on any process.

WHY THIS GATE EXISTS. The first printed pelvis came back without all but one of
its floor posts, both battery rails, the battery-board guides and the IMU seat.
Sixteen of its twenty-two bodies only rested face-to-face on the shell, the file
handed the printer all twenty-two separately, and every gate here passed it --
because every gate here asked OCCT, and OCCT unites bodies that merely touch
without a murmur. Gates A to F prove the part is the part that was drawn. This
one proves the part that was drawn is a part a printer can make.

Four questions a piece, each a failure this project has had:

1. THE FILE. The piece is built, finished and united exactly as tools/export.py
   does it, in a child process, written to a scratch directory and read back --
   and must be ONE solid with ONE shell, and one closed, consistently wound
   surface to trimesh, which did not draw it. This is the deliverable, tested,
   not a model of it.
2. WALLS no thinner than tools/printable.py's MIN_WALL_MM anywhere.
3. GAPS within the part no narrower than MIN_GAP_MM, which is what fuses shut in
   a powder bed.
4. NOTHING STARTS IN MID-AIR when the piece is printed the way
   tools/mass_budget.toml says it is -- its `print_up`. The orientations that
   would also have worked are listed, so a failure says what to change to.

The limits, and why they are the strictest of FDM, nylon powder and resin, are
in tools/printable.py. They are not loosened here: a finding that is accepted on
purpose goes in ACCEPTED below with its measured value and its reason, pinned
both ends like gate B's register, so a second finding cannot hide in the first.

    uv run tools/gate_g.py                    # every piece, a few minutes
    uv run tools/gate_g.py pelvis-shell       # one
    uv run tools/gate_g.py --quick            # skip building the file (question 1)

Free, offline, no engine.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import export  # noqa: E402
import printable  # noqa: E402

# Findings accepted ON PURPOSE: (piece, rule) -> (the worst value measured, why).
# `rule` is "wall", "gap" or "islands". The value is pinned, so the entry holds
# only while the part measures exactly that; a thinner wall is a new finding.
ACCEPTED: dict[tuple[str, str], tuple[float, str]] = {
    # THE ONE ACCEPTED WALL, 2026-10-12: the strip between the charge inlet's
    # cutout and each of its two screw holes, four readings at x 49.9 and 67.5,
    # z 22.5, both faces of the rear wall. Nothing else on this wall is under
    # 1.0. It is the connector's own figures that set it: its ear holes are
    # 20.00 apart, its nose measured 15.3 wide with 0.2 mm of air a side, and the
    # owner wants holes that pass an M2.5 as printed, so Ø2.9 -- with each screw
    # already stood the 0.25 mm outboard that the Ø3.00 ear hole allows. At M2
    # on a Ø2.2 hole it was 1.05 and the holes had to be drilled. It carries no
    # load of its own: the screw head clamps the wall to the connector's ear
    # plate across it. On the owner's printer both holes come out about 0.1 mm
    # a side small, so the strip prints nearer 1.15.
    ("pelvis-shell", "wall"): (
        0.95,
        "the inlet's 15.7 mm cut and its two Ø2.9 M2.5 holes, set by the "
        "connector's 20 mm ear holes; clamped, not loaded",
    ),
}


def accepted(piece: str, rule: str, worst: float) -> str | None:
    """The reason a finding stands, if it is registered at exactly this value."""
    entry = ACCEPTED.get((piece, rule))
    if entry is not None and abs(entry[0] - worst) <= 0.01:
        return entry[1]
    return None


def line(ok: bool, text: str) -> str:
    return f"  {'  ok  ' if ok else ' FAIL '} {text}"


def check_file(result: dict, found: list) -> tuple[list[str], int]:
    """Question 1: the file tools/export.py would write. (lines, failures)"""
    ok = not found
    lines = [
        line(
            ok,
            "the file a printer gets is one solid, one closed surface"
            + (f"  ({result.get('broken')} arrises broken)" if ok else ""),
        )
    ]
    lines += [f"          {problem}" for problem in found]
    return lines, 0 if ok else 1


def check_shape(piece: dict) -> tuple[list[str], int]:
    """Questions 2 to 4, on the piece as drawn and united. (lines, failures)"""
    from cad.finish import one_solid

    name = piece["name"]
    lines: list[str] = []
    failures = 0
    solid, _, _ = one_solid(export.build(piece), finished=False)
    mesh = printable.mesh_of(solid)

    for rule, found, limit, what in (
        ("wall", printable.thin_walls(mesh), printable.MIN_WALL_MM, "wall"),
        (
            "gap",
            printable.narrow_gaps(mesh),
            printable.MIN_GAP_MM,
            "gap within the part",
        ),
    ):
        worst = min((v for _, v in found), default=None)
        why = accepted(name, rule, worst) if found else None
        ok = not found or why is not None
        failures += 0 if ok else 1
        lines.append(
            line(
                ok,
                f"no {what} under {limit} mm"
                + (f"  (accepted at {worst:.2f}: {why})" if why else ""),
            )
        )
        if not ok:
            lines += [f"          {value:.2f} mm at {where}" for where, value in found]

    up = piece.get("print_up")
    if up not in printable.ORIENTATIONS:
        lines.append(
            line(
                False,
                f"print_up is {up!r} in tools/mass_budget.toml; it must be one of "
                f"{', '.join(printable.ORIENTATIONS)}",
            )
        )
        return lines, failures + 1
    isles = printable.islands(mesh, up)
    why = accepted(name, "islands", float(len(isles))) if isles else None
    ok = not isles or why is not None
    failures += 0 if ok else 1
    text = f"printed {up} up, nothing starts in mid-air"
    if isles and why is None:
        # Only on a failure is it worth slicing the other five ways: it turns
        # "this is wrong" into "this is what to declare instead".
        clean = [
            o
            for o in printable.ORIENTATIONS
            if o != up and not printable.islands(mesh, o)
        ]
        text += f"  (would print: {', '.join(clean) or 'no axis-aligned way up'})"
    elif why:
        text += f"  (accepted: {why})"
    lines.append(line(ok, text))
    if not ok:
        lines += [
            f"          {area:.1f} mm2 starting {height:.1f} mm up, at {where}"
            for height, area, where in isles[:6]
        ]
    return lines, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pieces", nargs="*", help="piece names; default is all")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="skip building and reading back the finished file",
    )
    args = parser.parse_args()

    pieces = export.pieces_from_budget()
    if args.pieces:
        unknown = set(args.pieces) - {p["name"] for p in pieces}
        if unknown:
            print(f"no such piece: {', '.join(sorted(unknown))}")
            return 2
        pieces = [p for p in pieces if p["name"] in args.pieces]

    print("WHAT EACH PIECE PRINTS AS")
    print(
        f"limits: walls {printable.MIN_WALL_MM} mm, gaps {printable.MIN_GAP_MM} mm,"
        f" layers sliced every {printable.LAYER_MM} mm -- tools/printable.py says why"
    )
    print()

    failed = 0
    with tempfile.TemporaryDirectory() as scratch, ThreadPoolExecutor(4) as pool:
        folder = Path(scratch)
        # The files are built by child processes, so they are started first and
        # the shape questions are answered here while they run.
        futures = {}
        if not args.quick:
            futures = {
                p["name"]: pool.submit(
                    export.produce, p, folder / f"{p['name']}.step", "step", True
                )
                for p in pieces
            }
        shapes = {p["name"]: check_shape(p) for p in pieces}

        for piece in pieces:
            name = piece["name"]
            print(name)
            if name in futures:
                result = futures[name].result()
                found = list(result.get("problems", []))
                if not found:
                    found = export.verify(
                        folder / f"{name}.step", "step", result.get("volume")
                    )
                lines, wrong = check_file(result, found)
                print("\n".join(lines))
                failed += wrong
            lines, wrong = shapes[name]
            print("\n".join(lines))
            failed += wrong

    print()
    if failed:
        print(f"gate G: FAIL -- {failed} finding(s)")
        return 1
    print(f"gate G: pass -- {len(pieces)} piece(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
