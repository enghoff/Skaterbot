# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9"]
# ///
"""Write one file per printable piece of the robot: STEP to print from, STL to simulate.

Which pieces those are lives in mass_budget.toml beside this file, in the
`[[printed.piece]]` entries under each printed module. Nothing is hard-coded here.

    uv run tools/export.py                              # every piece, STEP, to exports/
    uv run tools/export.py --pieces pelvis-shell        # just one
    uv run tools/export.py --as-drawn                   # arrises left sharp
    uv run tools/export.py --format stl --out simulation/meshes
    uv run tools/export.py --list                       # what there is to export
    uv run tools/export.py --verify                     # re-read what is already written

Free and offline. This used to be the most expensive tool in the repository: one
metered engine execution per piece, plus a generated wrapper scene per piece to
isolate it, because a KCL export took the whole scene and every module built more
than one part. A piece is a Python object now, so exporting it is a local OCCT
call and isolating it is calling one function instead of another.

WHAT COMES OUT IS THE PART AS IT WOULD BE PRINTED, arrises broken at 0.5 mm by
cad/finish.py. That pass is a separate module for a good reason -- gate B holds
the part AS DRAWN against the STEP the Zoo engine built, and a chamfer is by
definition a change to that geometry -- but separate used to mean optional, and
optional meant the files in exports/ were the unfinished part unless somebody
remembered a flag. Nobody should have to: the finished part is what this writes
now, and `--as-drawn` is how the gates ask for the other one.

Which form a file on disk is in is not left to memory either. A .step cannot say
for itself whether its arrises were broken -- you would have to measure it -- so
every run writes a manifest.json beside the files saying, piece by piece, which
form was written, what the chamfer was set to and how many arrises it took. That
is what `--verify` reads, and what anything downstream should read rather than
assume.

WHAT IS CHECKED ON THE WAY OUT, and why it is not ceremony. Four things, each of
which has actually gone wrong here:

* the body count against the `bodies` figure the budget declares, which catches a
  piece that arrives with a sibling attached or a shell missing;
* every body's volume, because a twice-mirrored solid comes back inverted and
  measures zero while keeping a correct bounding box and working booleans -- that
  is how the limb's rear gusset shipped wrong once;
* the file re-read from disk, so the count that gets reported is the count that
  landed rather than the count that was intended;
* that the finish pass cut something at all, because a piece that comes back
  with no arris broken has silently skipped the whole pass and is a sharp part
  wearing a finished part's name. Which arrises were left sharp and why is
  tools/finish_report.py's subject; this only refuses to write the file that
  missed the pass entirely.

THE PIECES ARE STILL SEVERAL INTERPENETRATING SHELLS, not one solid. That is what
the engine forced -- it refuses to union hollow boxes meeting at right angles, and
the hip saddles are exactly that -- and it is what a slicer merges anyway. Phase 3
of docs/BUILD123D_MIGRATION.md is where they become single solids; until then the
`bodies` counts in the budget are the register of what is still to be unioned.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from build123d import Compound, export_step, export_stl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUDGET = HERE / "mass_budget.toml"
DEFAULT_OUT = ROOT / "exports"

# Beside the exported files, saying which form each of them is in. See the module
# docstring: the file itself cannot answer that question.
MANIFEST = "manifest.json"

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


def build(piece: dict, finished: bool) -> tuple[list, int, int]:
    """The bodies of one piece, by calling the function the budget names.

    `file` is a module path under cad/ and `export` the function in it. A builder
    returns either one solid or the list of interpenetrating bodies the piece is
    made of; both come back as a list here.

    Returns the bodies with how many arrises the finish pass broke and how many
    it left sharp. As drawn there is no such pass, and so nothing to count.
    """
    module = importlib.import_module(
        piece["file"].removesuffix(".py").replace("/", ".").replace("\\", ".")
    )
    built = getattr(module, piece["export"])()
    bodies = list(built) if isinstance(built, (list, tuple)) else [built]

    if not finished:
        return bodies, 0, 0

    from cad.finish import chamfered

    return chamfered(bodies)


def chamfer_size() -> float:
    """What an arris is broken by -- asked of cad/finish.py, not repeated here."""
    from cad.finish import CHAMFER

    return CHAMFER


def read_manifest(out: Path) -> dict:
    """What the last run recorded about the files in `out`, if anything did."""
    path = out / MANIFEST
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_manifest(out: Path, written: dict) -> None:
    """Record what each file is, MERGED over whatever the directory already knew.

    Merged rather than replaced because exporting one piece must not erase what
    is recorded about the other five, and a partial re-export is the normal way
    to work here.
    """
    if not written:
        return
    record = read_manifest(out)
    record.update(written)
    (out / MANIFEST).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


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
    """The table, with what the finish pass did to each piece in it.

    `broken` and `sharp` are counts on a piece that was finished, a dash on one
    exported as drawn where there was nothing to break, and a question mark on a
    file that was only read back and that nothing records the form of.
    """
    width = max(len(path.name) for path, *_ in rows)
    head = f"{'file':<{width}}  {'KB':>8} {'solids':>7} {'broken':>7} {'sharp':>6}   "
    head += f"{'x mm':^16}  {'y mm':^16}  {'z mm':^16}"
    print(head)
    print("-" * len(head))
    for path, size, solids, broken, sharp, note, box in rows:
        shown = "     ?" if solids is None else f"{solids:6d}"
        print(
            f"{path.name:<{width}}  {size / 1024:8.1f}  {shown}"
            f" {broken:>7} {sharp:>6}   {box}{note}"
        )


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
    form = parser.add_mutually_exclusive_group()
    form.add_argument(
        "--as-drawn",
        action="store_true",
        help="export the part as cad/ draws it, every arris left sharp. That is"
        " the form gate B compares against reference/golden/step, and it is not"
        " the form to hand a printer",
    )
    form.add_argument(
        "--finished",
        action="store_true",
        help="export the piece as it would be printed, arrises broken at 0.5 mm"
        " by cad/finish.py. This is what happens anyway; the flag is kept only"
        " because it used to be how you asked for it",
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

    finished = not args.as_drawn
    size = chamfer_size() if finished and not args.verify else None

    rows: list[tuple] = []
    bad: list[str] = []
    recorded = read_manifest(args.out) if args.verify else {}
    written: dict = {}
    broke_total = sharp_total = 0

    for piece in pieces:
        path = args.out / f"{piece['name']}.{args.format}"

        if args.verify:
            if not path.exists():
                print(f"{piece['name']}: nothing written at {path}")
                bad.append(piece["name"])
                continue
            box = ""
            known = recorded.get(path.name)
            if known is None:
                print(
                    f"{piece['name']}: {path.name} is on disk and nothing says"
                    " which form it is in. Export it again."
                )
                bad.append(piece["name"])
                broken = sharp = "?"
            elif known.get("form") == "as drawn":
                broken = sharp = "-"
            else:
                broken = known.get("arrises_broken", "?")
                sharp = known.get("arrises_left_sharp", "?")
        else:
            bodies, broken, sharp = build(piece, finished)
            empty = zero_volume(bodies)
            if empty:
                print(
                    f"{piece['name']}: bodies {empty} measure zero volume -- "
                    "malformed solids, probably inverted by a double mirror"
                )
                bad.append(piece["name"])
                continue
            # A finished piece that broke no arris did not run the pass at all,
            # and writing it would put a sharp part under a finished part's
            # name -- which is the failure this default exists to stop.
            if finished and not broken:
                print(
                    f"{piece['name']}: the finish pass broke no arris at all, so"
                    " nothing was written -- this piece would have been sharp"
                )
                bad.append(piece["name"])
                continue
            write(bodies, path, args.format)
            box = extents(bodies)
            written[path.name] = {
                "piece": piece["name"],
                "form": "finished" if finished else "as drawn",
                "chamfer_mm": size,
                "arrises_broken": broken if finished else None,
                "arrises_left_sharp": sharp if finished else None,
                "bodies": len(bodies),
                "written": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            if finished:
                broke_total += broken
                sharp_total += sharp
            else:
                broken = sharp = "-"

        solids = solids_in(path, args.format)
        expected = piece.get("bodies")
        note = ""
        if solids is not None and expected is not None and solids != expected:
            note = f"  <-- expected {expected}"
            bad.append(piece["name"])
        elif solids == 0:
            note = "  <-- EMPTY"
            bad.append(piece["name"])
        rows.append((path, path.stat().st_size, solids, broken, sharp, note, box))

    write_manifest(args.out, written)

    if rows:
        report(rows)
        print()
        print(f"{len(rows)} file(s) in {args.out}")
        if args.verify:
            print(
                f"form as {MANIFEST} records it; a file it does not name has to"
                " be exported again before anyone can say what it is"
            )
        elif finished:
            print(
                f"as printed: {broke_total} arrises broken at {size} mm,"
                f" {sharp_total} left sharp -- tools/finish_report.py says which"
            )
        else:
            print(
                "AS DRAWN: every arris left sharp. This is the form gate B"
                " compares against reference/golden/step, not the form to print."
            )

    if bad:
        print(f"\nWRONG: {', '.join(sorted(set(bad)))}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
