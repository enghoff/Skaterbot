# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1",
#                 "trimesh==4.5.3", "numpy<2.3", "scipy", "networkx", "rtree",
#                 "shapely"]
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
    uv run tools/export.py --release                    # a versioned set, for a bureau

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
assume. It also says which commit each file was built from, and the file's
SHA-256.

A RELEASE IS WHAT GOES TO A BUREAU, and it is versioned by the commit it was
built from. exports/ is a working directory that every run rewrites, so a file
uploaded from it says nothing about which geometry it held by the time a quote
comes back. `--release` writes the set into exports/releases/<commit>/ instead,
every file named for that commit -- pelvis-shell_8c6cfe4.step -- because the
file name is the one thing a bureau's cart shows back. It is refused from a tree
whose cad/ or mass budget has uncommitted changes, since a commit that does not
hold the geometry cannot version it; it is all or nothing, so one refused piece
releases nothing; and it never writes over a file already released, because
that file may be the one a bureau has. docs/ORDERS.md is where the version sent
is recorded, with the settings it was printed at.

EVERY FILE IS ONE SOLID. The pieces are still DRAWN as several interpenetrating
bodies -- that is what the KCL engine forced, and the `bodies` counts in the
budget are the register of them -- and until September 2026 they were exported
that way too, on the argument that a slicer merges them. The first printed
pelvis came back missing sixteen of its twenty-two bodies, which only rested
face-to-face on the shell. So the bodies are united here, into the single part
they are, before anything is written: cad/finish.py's one_solid() does it and
says how. A printer is never again handed a question about which bodies belong
together.

THE UNION RUNS IN A CHILD PROCESS, and that is deliberate. OCCT has taken this
project's process down more than once on chamfered bodies -- an access
violation, which no try/except can catch -- and one_solid() avoids the known
case rather than being provably immune to it. A child that dies is a piece
refused with its exit code, where the same crash in-process would end the run
with nothing written and nothing said.

WHAT IS CHECKED ON THE WAY OUT, and why it is not ceremony. Each of these has
actually gone wrong here:

* the drawn body count against the `bodies` figure the budget declares, which
  catches a piece that arrives with a sibling attached or a shell missing;
* every body's volume, because a twice-mirrored solid comes back inverted and
  measures zero while keeping a correct bounding box and working booleans -- that
  is how the limb's rear gusset shipped wrong once;
* that the finish pass cut something at all, because a piece that comes back
  with no arris broken has silently skipped the whole pass and is a sharp part
  wearing a finished part's name. Which arrises were left sharp and why is
  tools/finish_report.py's subject; this only refuses to write the file that
  missed the pass entirely;
* that the united piece is one solid with one shell -- no loose body, no sealed
  cavity -- before it is written, which is cad/finish.py's problems();
* and the FILE, re-read from disk and checked twice: by OCCT for one solid and
  one shell, and by trimesh, on the triangles a slicer would get, for one closed
  consistently wound surface enclosing the solid's volume. The second reader is
  the one that matters, because it is not the kernel that drew the part --
  tools/printable.py says why that distinction cost a print.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from build123d import export_step, export_stl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUDGET = HERE / "mass_budget.toml"
DEFAULT_OUT = ROOT / "exports"

# Beside the exported files, saying which form each of them is in. See the module
# docstring: the file itself cannot answer that question.
MANIFEST = "manifest.json"

# Where `--release` writes, under the output directory, one folder per version.
RELEASES = "releases"

# What the geometry is built from, so what has to be committed before a release
# can name it: the drawing, and the register of which pieces there are and which
# way up they print.
SOURCES = ("cad", "tools/mass_budget.toml")

sys.path.insert(0, str(ROOT))

FORMATS = ("step", "stl")


def git(*args: str) -> str | None:
    """One git query's output, or None outside a checkout or without git."""
    try:
        done = subprocess.run(
            ["git", *args], capture_output=True, text=True, cwd=ROOT, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    # Trailing only: a porcelain status line starts with a space that matters.
    return done.stdout.rstrip()


def source() -> dict:
    """The commit the geometry is built from, and what in it has moved since.

    `version` is the short commit, with `+uncommitted` on it when cad/ or the
    budget has changes the commit does not hold -- a file built then is not
    the commit's geometry, and must not be mistaken for it.
    """
    commit = git("rev-parse", "HEAD")
    if not commit:
        return {"commit": None, "version": None, "uncommitted": None}
    changed = git("status", "--porcelain", "--", *SOURCES) or ""
    moved = [line[3:] for line in changed.splitlines()]
    short = git("rev-parse", "--short", "HEAD") or commit[:7]
    return {
        "commit": commit,
        "committed": git("show", "-s", "--format=%cI", "HEAD"),
        "version": short + ("+uncommitted" if moved else ""),
        "uncommitted": moved,
    }


def filename(piece: dict, fmt: str, version: str | None = None) -> str:
    """`pelvis-shell.step`, or `pelvis-shell_8c6cfe4.step` in a release."""
    return f"{piece['name']}_{version}.{fmt}" if version else f"{piece['name']}.{fmt}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pieces_from_budget() -> list[dict]:
    """Every `[[printed.piece]]`, with the module its `[[printed]]` parent names."""
    budget = tomllib.loads(BUDGET.read_text(encoding="utf-8"))
    found = []
    for part in budget["printed"]:
        for piece in part.get("piece", []):
            found.append({**piece, "file": part["file"]})
    return found


def build(piece: dict) -> list:
    """The bodies of one piece as drawn, by calling the function the budget names.

    `file` is a module path under cad/ and `export` the function in it. A builder
    returns either one solid or the list of interpenetrating bodies the piece is
    drawn as; both come back as a list here.
    """
    module = importlib.import_module(
        piece["file"].removesuffix(".py").replace("/", ".").replace("\\", ".")
    )
    built = getattr(module, piece["export"])()
    return list(built) if isinstance(built, (list, tuple)) else [built]


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


def write(solid, path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "step":
        export_step(solid, str(path))
    else:
        export_stl(solid, str(path))


def worker(name: str, fmt: str, path: Path, finished: bool) -> int:
    """Build, finish, unite and write ONE piece. Runs in the child process.

    Prints one line of JSON saying what happened, and exits 0 if the file was
    written or 3 if the piece was refused. Any other exit is the process dying,
    which produce() reports as exactly that.
    """
    from cad.finish import one_solid, problems

    piece = next(p for p in pieces_from_budget() if p["name"] == name)
    bodies = build(piece)
    found = []
    solid, broken, sharp = None, 0, 0
    empty = zero_volume(bodies)
    if empty:
        found.append(
            f"bodies {empty} measure zero volume -- malformed solids, probably "
            "inverted by a double mirror"
        )
    else:
        solid, broken, sharp = one_solid(bodies, finished=finished)
        found += problems(solid)
        # A finished piece that broke no arris did not run the pass at all, and
        # writing it would put a sharp part under a finished part's name.
        if finished and not broken:
            found.append("the finish pass broke no arris at all")
    if not found:
        write(solid, path, fmt)
    box = None
    if solid is not None:
        b = solid.bounding_box()
        box = [b.min.X, b.max.X, b.min.Y, b.max.Y, b.min.Z, b.max.Z]
    record = {
        # Counted as SOLIDS, because one drawn item can be several: a block with
        # a slot cut through its whole depth is two ribs.
        "bodies": sum(len(body.solids()) for body in bodies),
        "broken": broken,
        "sharp": sharp,
        "volume": solid.volume if solid is not None else None,
        "box": box,
        "problems": found,
    }
    print(json.dumps(record))
    return 3 if found else 0


def produce(piece: dict, path: Path, fmt: str, finished: bool) -> dict:
    """Have a child process write one piece, and say what it did.

    The result is worker()'s record, with `problems` naming the crash if the
    child died rather than answering.
    """
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        piece["name"],
        "--format",
        fmt,
        "--out",
        str(path),
    ]
    if not finished:
        command.append("--as-drawn")
    done = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    lines = [line for line in done.stdout.splitlines() if line.startswith("{")]
    if done.returncode not in (0, 3) or not lines:
        tail = (done.stderr or done.stdout).strip().splitlines()[-1:] or [""]
        return {
            "problems": [
                f"the process uniting this piece died (exit {done.returncode}) "
                f"and nothing was written. {tail[0]}"
            ]
        }
    return json.loads(lines[-1])


def verify(path: Path, fmt: str, volume: float | None = None) -> list[str]:
    """Why the file on disk is not one printable solid, or nothing if it is.

    Read back from disk rather than trusted from what was intended, and asked
    twice: OCCT counts solids and shells in a STEP, and trimesh -- which did not
    draw the part and has no opinion about which bodies touch -- checks the
    triangles a slicer would get. An STL has only the second reader.
    """
    import printable

    if not path.exists():
        return [f"nothing written at {path}"]
    if fmt == "step":
        from build123d import import_step

        from cad.finish import problems

        shape = import_step(str(path))
        found = problems(shape)
        if found:
            return found
        return printable.integrity(printable.mesh_of(shape), volume or shape.volume)
    import trimesh

    return printable.integrity(trimesh.load_mesh(str(path)), volume)


def extents(box: list | None) -> str:
    """The piece's bounding box, which is the cheap half of a sanity check.

    A part that should sit to one side of the robot and comes out symmetric about
    x = 0 has a sibling in it.
    """
    if not box:
        return ""
    return "  ".join(
        f"{low:7.1f}..{high:7.1f}"
        for low, high in ((box[0], box[1]), (box[2], box[3]), (box[4], box[5]))
    )


def report(rows: list[tuple]) -> None:
    """The table, with what the finish pass did to each piece in it.

    `broken` and `sharp` are counts on a piece that was finished, a dash on one
    exported as drawn where there was nothing to break, and a question mark on a
    file that was only read back and that nothing records the form of.
    """
    width = max(len(path.name) for path, *_ in rows)
    head = f"{'file':<{width}}  {'KB':>8} {'bodies':>7} {'broken':>7} {'sharp':>6}"
    head += f"  {'file is':<10}  {'x mm':^16}  {'y mm':^16}  {'z mm':^16}"
    print(head)
    print("-" * len(head))
    for path, size, bodies, broken, sharp, verdict, box in rows:
        kb = f"{size / 1024:8.1f}" if size is not None else "       -"
        print(
            f"{path.name:<{width}}  {kb} {bodies!s:>7} {broken!s:>7} {sharp!s:>6}"
            f"  {verdict:<10}  {box}"
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
        help="re-read the files already in the output directory and check each"
        " is one printable solid, without rebuilding. A release is verified by"
        " naming its folder with --out",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="write a versioned set for a print order into"
        " <out>/releases/<commit>/, every file named for the commit it was built"
        " from. Refused if cad/ or the mass budget has uncommitted changes, and"
        " never writes over a file already released",
    )
    # The child process's entry point, with --out naming the FILE; see produce().
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        return worker(args.worker, args.format, args.out, not args.as_drawn)

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
                f" {piece.get('prints', 1)} print(s), {bodies} bodies drawn,"
                f" prints {piece.get('print_up', '?')} up"
            )
        return 0

    origin = source()
    out = args.out
    version = None
    if args.release:
        if args.as_drawn or args.verify:
            print(
                "a release is the finished part, written fresh: not with"
                " --as-drawn or --verify"
            )
            return 2
        if not origin["commit"]:
            print("no git commit to version a release by -- is this a checkout?")
            return 2
        if origin["uncommitted"]:
            print(
                "not released: a release is named for the commit it was built"
                " from, and these have changes that commit does not hold --"
                " commit them first:"
            )
            for path in origin["uncommitted"]:
                print(f"  {path}")
            return 2
        version = origin["version"]
        out = args.out / RELEASES / version
        already = [
            name
            for name in (filename(p, args.format, version) for p in pieces)
            if (out / name).exists()
        ]
        if already:
            print(
                f"not released: {out} already holds {', '.join(already)}. A"
                " released file is never written over, because it may be the one"
                " a bureau has; delete it by hand only if it was never sent."
            )
            return 2

    finished = not args.as_drawn
    size = chamfer_size() if finished and not args.verify else None

    rows: list[tuple] = []
    bad: list[str] = []
    recorded = read_manifest(out) if args.verify else {}
    written: dict = {}
    broke_total = sharp_total = 0

    def target(piece: dict) -> Path:
        """Where this piece is. In --verify, wherever the manifest says it was
        written, which is how a release's versioned names are found again."""
        if args.verify:
            for name, known in recorded.items():
                if known.get("piece") == piece["name"] and name.endswith(
                    f".{args.format}"
                ):
                    return out / name
        return out / filename(piece, args.format, version)

    # Each piece is its own process, so they run side by side: most of a
    # child's time is starting Python and OCCT, and none of it is shared.
    produced = {}
    shapes: dict = {}
    if not args.verify:
        print(f"building {len(pieces)} piece(s) ...", flush=True)
        with ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) // 2)) as pool:
            futures = {
                piece["name"]: pool.submit(
                    produce, piece, target(piece), args.format, finished
                )
                for piece in pieces
            }
            # A STEP is what goes to a printer, so it is held to everything gate
            # G holds a piece to -- walls, gaps, and nothing starting in mid-air
            # -- and not only to being one solid. Asked here, while the children
            # build the files. The STLs are the simulation's, and a part too
            # thin to print still has a mass to simulate -- unless they are a
            # release, which some bureaus take in place of the STEP.
            if finished and (args.format == "step" or args.release):
                import gate_g

                shapes = {p["name"]: gate_g.check_shape(p) for p in pieces}
            produced = {name: future.result() for name, future in futures.items()}

    for piece in pieces:
        path = target(piece)
        box = ""
        found: list[str] = []

        if args.verify:
            known = recorded.get(path.name)
            if not path.exists():
                found.append(f"nothing written at {path}")
            elif known is None:
                found.append(
                    "on disk, and nothing says which form it is in -- export it again"
                )
            bodies = known.get("bodies_drawn", "?") if known else "?"
            if known is None:
                broken = sharp = "?"
            elif known.get("form") == "as drawn":
                broken = sharp = "-"
            else:
                broken = known.get("arrises_broken", "?")
                sharp = known.get("arrises_left_sharp", "?")
            if path.exists():
                if known and known.get("sha256") not in (None, sha256(path)):
                    found.append(
                        "not the file the manifest recorded: its SHA-256 differs"
                    )
                found += verify(path, args.format)
        else:
            result = produced[piece["name"]]
            found += result.get("problems", [])
            bodies = result.get("bodies", "?")
            expected = piece.get("bodies")
            if expected is not None and bodies != expected:
                found.append(
                    f"{bodies} bodies drawn where the budget declares {expected} "
                    "-- a sibling part inside, or a body missing"
                )
            broken = result.get("broken", 0) if finished else "-"
            sharp = result.get("sharp", 0) if finished else "-"
            box = extents(result.get("box"))
            if not result.get("problems"):
                found += verify(path, args.format, result.get("volume"))
            if piece["name"] in shapes and not found:
                lines, wrong = shapes[piece["name"]]
                if wrong:
                    found += [
                        "gate G: " + " ".join(text.split())
                        for text in lines
                        if "FAIL" in text or text.startswith("          ")
                    ]
            if not found:
                volume = result.get("volume")
                written[path.name] = {
                    "piece": piece["name"],
                    "form": "finished" if finished else "as drawn",
                    "chamfer_mm": size,
                    "arrises_broken": broken if finished else None,
                    "arrises_left_sharp": sharp if finished else None,
                    "bodies_drawn": bodies,
                    "solids": 1,
                    "prints": piece.get("prints", 1),
                    "print_up": piece.get("print_up"),
                    "volume_cm3": round(volume / 1000, 2) if volume else None,
                    "version": origin["version"],
                    "commit": origin["commit"],
                    "uncommitted": origin["uncommitted"],
                    "sha256": sha256(path),
                    "written": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                if finished:
                    broke_total += broken
                    sharp_total += sharp
            elif path.exists():
                # Whatever is on disk under this name is not this piece as it now
                # stands, and must not be mistaken for it.
                path.unlink()

        verdict = "one solid" if not found else "REFUSED"
        size_on_disk = path.stat().st_size if path.exists() else None
        rows.append((path, size_on_disk, bodies, broken, sharp, verdict, box))
        if found:
            bad.append(piece["name"])
            for problem in found:
                print(f"  {piece['name']}: {problem}")

    if args.release and bad:
        # All or nothing: a set with a piece missing is not a release of the
        # commit, and leaving its other files would block the one that is.
        for name in written:
            (out / name).unlink(missing_ok=True)
        written = {}
        if out.exists() and not any(out.iterdir()):
            out.rmdir()
    write_manifest(out, written)

    if rows:
        print()
        report(rows)
        print()
        print(f"{len(rows)} file(s) in {out}")
        if origin["uncommitted"] and not args.verify:
            print(
                f"built from {origin['version']}: cad/ or the budget had changes"
                " that commit does not hold, so this is not a version of anything"
                " -- a print order wants --release"
            )
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
        if args.release and not bad:
            release_table(out, written, origin)

    if bad:
        print(f"\nREFUSED: {', '.join(sorted(set(bad)))}")
        if args.release:
            print("nothing released: a release is every piece asked for, or none")
        return 1
    return 0


def release_table(out: Path, written: dict, origin: dict) -> None:
    """What was released, as the table docs/ORDERS.md records an order against.

    The bureau's settings go beside it there, read off the cart when it is
    built: nothing in a STEP says what infill or layer height it was quoted at.
    """
    print(
        f"\nrelease {origin['version']}, commit {origin['commit']}"
        f" of {origin['committed']}, in {out}\n"
    )
    print("| File | Prints | Up | cm³ | SHA-256 |")
    print("|---|---:|---|---:|---|")
    for name, record in sorted(written.items()):
        print(
            f"| {name} | {record['prints']} | {record['print_up']} |"
            f" {record['volume_cm3']} | {record['sha256'][:12]} |"
        )
    total = sum(record["prints"] for record in written.values())
    print(f"\n{total} prints from {len(written)} files")


if __name__ == "__main__":
    raise SystemExit(main())
