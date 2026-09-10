# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9"]
# ///
"""Write one file per printable piece of the robot: STEP to print from, STL to simulate.

Which pieces those are lives in mass_budget.toml beside this file, in the
`[[printed.piece]]` entries under each printed module. Nothing is hard-coded here.

    uv run tools/export.py                              # every piece, STEP, to exports/
    uv run tools/export.py --pieces pelvis-shell        # just one
    uv run tools/export.py --finished                   # with its edges broken
    uv run tools/export.py --format stl --out simulation/meshes
    uv run tools/export.py --list                       # what there is to export
    uv run tools/export.py --verify                     # re-read what is already written

Free and offline. This used to be the most expensive tool in the repository: one
metered engine execution per piece, plus a generated wrapper scene per piece to
isolate it, because a KCL export took the whole scene and every module built more
than one part. A piece is a Python object now, so exporting it is a local OCCT
call and isolating it is calling one function instead of another.

WHAT IS CHECKED ON THE WAY OUT, and why it is not ceremony. Three things, each of
which has actually gone wrong here:

* the body count against the `bodies` figure the budget declares, which catches a
  piece that arrives with a sibling attached or a shell missing;
* every body's volume, because a twice-mirrored solid comes back inverted and
  measures zero while keeping a correct bounding box and working booleans -- that
  is how the limb's rear gusset shipped wrong once;
* the file re-read from disk, so the count that gets reported is the count that
  landed rather than the count that was intended.

THE PIECES ARE STILL SEVERAL INTERPENETRATING SHELLS, not one solid. That is what
the engine forced -- it refuses to union hollow boxes meeting at right angles, and
the hip saddles are exactly that -- and it is what a slicer merges anyway. Phase 3
of docs/BUILD123D_MIGRATION.md is where they become single solids; until then the
`bodies` counts in the budget are the register of what is still to be unioned.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import tomllib
from pathlib import Path

from build123d import Compound, export_step, export_stl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUDGET = HERE / "mass_budget.toml"
DEFAULT_OUT = ROOT / "exports"

sys.path.insert(0, str(ROOT))

FORMATS = ("step", "stl")


def pieces_from_budget() -> list[dict]:
    """Every `[[printed.piece]]`, with the module its `[[printed]]` parent names."""
    budget = tomllib.loads(BUDGET.read_text(encoding="utf-8"))
    found = []
    for part in budget["printed"]:
        for piece in part.get("piece", []):
            found.append({**piece, "file": part["file"]})
    return found


def build(piece: dict, finished: bool) -> list:
    """The bodies of one piece, by calling the function the budget names.

    `file` is a module path under cad/ and `export` the function in it. A builder
    returns either one solid or the list of interpenetrating bodies the piece is
    made of; both come back as a list here.
    """
    module = importlib.import_module(
        piece["file"].removesuffix(".py").replace("/", ".").replace("\\", ".")
    )
    built = getattr(module, piece["export"])()
    bodies = list(built) if isinstance(built, (list, tuple)) else [built]

    if finished:
        from cad.finish import chamfered

        bodies, _, _ = chamfered(bodies)
    return bodies


def zero_volume(bodies: list) -> list[int]:
    """Which bodies measure nothing, which means malformed rather than empty."""
    return [i for i, body in enumerate(bodies) if body.volume <= 0.0]


def write(bodies: list, path: Path, fmt: str) -> None:
    shape = bodies[0] if len(bodies) == 1 else Compound(children=bodies)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "step":
        export_step(shape, str(path))
    else:
        export_stl(shape, str(path))


def solids_in(path: Path, fmt: str) -> int | None:
    """How many solid bodies the written file actually holds.

    Read back from the file rather than counted before writing it, so what gets
    reported is what landed. STL has no notion of a body, only of triangles, so
    it claims nothing.
    """
    if fmt != "step":
        return None
    from build123d import import_step

    return len(import_step(str(path)).solids())


def extents(bodies: list) -> str:
    """The piece's bounding box, which is the cheap half of a sanity check.

    A part that should sit to one side of the robot and comes out symmetric about
    x = 0 has a sibling in it.
    """
    box = bodies[0].bounding_box()
    for body in bodies[1:]:
        box = box.add(body.bounding_box())
    return "  ".join(
        f"{low:7.1f}..{high:7.1f}"
        for low, high in (
            (box.min.X, box.max.X),
            (box.min.Y, box.max.Y),
            (box.min.Z, box.max.Z),
        )
    )


def report(rows: list[tuple]) -> None:
    width = max(len(path.name) for path, *_ in rows)
    head = f"{'file':<{width}}  {'KB':>8} {'solids':>7}   "
    head += f"{'x mm':^16}  {'y mm':^16}  {'z mm':^16}"
    print(head)
    print("-" * len(head))
    for path, size, solids, note, box in rows:
        shown = "     ?" if solids is None else f"{solids:6d}"
        print(f"{path.name:<{width}}  {size / 1024:8.1f}  {shown}   {box}{note}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pieces",
        help="comma-separated piece names to export; default is all of them",
    )
    parser.add_argument(
        "--format",
        default="step",
        choices=FORMATS,
        help="output format (default: step)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="directory to write into (default: exports/)",
    )
    parser.add_argument(
        "--finished",
        action="store_true",
        help="export the piece with its 0.5 mm chamfer, as it would be printed;"
        " the default is the part as drawn, which is what the gates compare",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list the printable pieces and exit, without building anything",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="re-read the files already in the output directory and check them"
        " against the declared body counts, without rebuilding",
    )
    args = parser.parse_args()

    pieces = pieces_from_budget()
    if args.pieces:
        wanted = [name.strip() for name in args.pieces.split(",")]
        unknown = [n for n in wanted if n not in {p["name"] for p in pieces}]
        if unknown:
            print(f"no such piece: {', '.join(unknown)}")
            return 2
        pieces = [p for p in pieces if p["name"] in wanted]

    if args.list:
        for piece in pieces:
            bodies = piece.get("bodies", "?")
            print(
                f"{piece['name']:<24} {piece['file']}:{piece['export']:<20}"
                f" {piece.get('prints', 1)} print(s), {bodies} bodies"
            )
        return 0

    rows: list[tuple] = []
    bad: list[str] = []
    for piece in pieces:
        path = args.out / f"{piece['name']}.{args.format}"

        if args.verify:
            if not path.exists():
                print(f"{piece['name']}: nothing written at {path}")
                bad.append(piece["name"])
                continue
            box = ""
        else:
            bodies = build(piece, args.finished)
            empty = zero_volume(bodies)
            if empty:
                print(
                    f"{piece['name']}: bodies {empty} measure zero volume -- "
                    "malformed solids, probably inverted by a double mirror"
                )
                bad.append(piece["name"])
                continue
            write(bodies, path, args.format)
            box = extents(bodies)

        solids = solids_in(path, args.format)
        expected = piece.get("bodies")
        note = ""
        if solids is not None and expected is not None and solids != expected:
            note = f"  <-- expected {expected}"
            bad.append(piece["name"])
        elif solids == 0:
            note = "  <-- EMPTY"
            bad.append(piece["name"])
        rows.append((path, path.stat().st_size, solids, note, box))

    if rows:
        report(rows)
        print(f"\n{len(rows)} file(s) in {args.out}")
        if args.finished:
            print("edges broken at 0.5 mm; tools/finish_report.py measures the cut")

    if bad:
        print(f"\nWRONG: {', '.join(sorted(set(bad)))}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
