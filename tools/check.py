# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1", "ruff>=0.16"]
# ///
"""Build every part and every scene, then lint and format-check the whole tree.

This is the sweep to run after any edit, and it is the whole of what the KCL
version of this command did plus rather more. It was a mock execution: Zoo's own
interpreter, run locally, which caught bad arguments and broken sketches but
never evaluated a boolean -- so a pocket the engine would refuse passed it
silently. Building the part here IS the boolean, so a cut that cannot be made is
a failure rather than a surprise later.

    uv run tools/check.py             # everything
    uv run tools/check.py --fix       # reformat what ruff would reformat
    uv run tools/check.py --no-lint   # geometry only, when iterating

What it checks, in order of what it costs:

1. every module in cad/ imports, which catches a name that moved;
2. every printed piece and every check scene builds, and no body of one measures
   zero volume -- the signature of a twice-mirrored solid, which keeps a correct
   bounding box and takes part in booleans while reporting no volume at all;
   and every printed piece unites into ONE solid with no sealed cavity in it,
   which is the rule cad/finish.py's problems() states. A body that does not
   reach the rest of its piece, or a pocket closed over into a void, fails here
   on the edit that caused it rather than at the printer;
3. ruff lints and format-checks cad/, tools/, simulation/, electrical/, bench/
   and sbc/, against the rules pinned in ruff.toml.

WHAT IT STILL DOES NOT PROVE. That a feature exists. A hole is a boolean, and a
boolean the engine accepts having built the wrong solid is the failure this
project has actually shipped -- four filled bolt holes on the joint that takes
the actuator's full torque. tools/gate_e.py counts the holes on the finished
solid and tools/gate_f.py measures the clearances the check scenes were drawn to
show; those are the checks that a part is right, and this is the check that it is
buildable.

Free, offline, no engine. A few seconds.
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Where the Python that this project runs on lives. Everything else in the tree
# is geometry output, reference input or documentation.
SOURCE_DIRS = ("cad", "tools", "simulation", "electrical", "bench", "sbc")


def modules() -> list[str]:
    """Every module in cad/, which is where the CAD now lives."""
    return sorted(
        info.name
        for info in pkgutil.iter_modules([str(ROOT / "cad")])
        if not info.name.startswith("_")
    )


def build_all() -> tuple[list[tuple], int]:
    """Build every printed piece and every scene. (rows, failures)"""
    import tomllib

    rows: list[tuple] = []
    failures = 0

    budget = tomllib.loads((ROOT / "tools" / "mass_budget.toml").read_text("utf-8"))
    work: list[tuple[str, str, object]] = []

    for part in budget["printed"]:
        module = importlib.import_module(
            part["file"].removesuffix(".py").replace("/", ".")
        )
        for piece in part.get("piece", []):
            work.append(("piece", piece["name"], getattr(module, piece["export"])))

    from cad import scenes

    for name, build in scenes.SCENES.items():
        work.append(("scene", name, build))

    from cad.main import robotAssembly

    work.append(("scene", "the neutral assembly", robotAssembly))

    for kind, name, build in work:
        started = time.time()
        try:
            built = build()
            bodies = list(built) if isinstance(built, (list, tuple)) else [built]
            empty = [i for i, body in enumerate(bodies) if body.volume <= 0.0]
            if empty:
                raise ValueError(
                    f"bodies {empty} measure zero volume -- malformed solids, "
                    "probably inverted by a double mirror"
                )
            note = f"{len(bodies):3d} bodies"
            if kind == "piece":
                # A printed piece has to be ONE part, and this is where a design
                # finds out, on every edit. See cad/finish.py's problems().
                from cad.finish import one_solid, problems

                found = problems(one_solid(bodies, finished=False)[0])
                if found:
                    raise ValueError("does not print as one piece: " + "; ".join(found))
                note += " -> one solid"
            status = "ok"
        except Exception as exc:  # noqa: BLE001 - the OCCT diagnostic is the payload
            note = f"{type(exc).__name__}: {exc}"
            status = "FAIL"
            failures += 1
        rows.append((kind, name, status, time.time() - started, note))

    return rows, failures


def ruff(argv: list[str]) -> tuple[int, str]:
    """Run ruff from the environment this script was launched in."""
    binary = shutil.which("ruff") or shutil.which(
        "ruff", path=str(Path(sys.executable).parent)
    )
    if binary is None:
        return 0, "ruff not found; skipped"
    done = subprocess.run(
        [binary, *argv, *SOURCE_DIRS],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return done.returncode, (done.stdout + done.stderr).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix", action="store_true", help="reformat and auto-fix what ruff can"
    )
    parser.add_argument(
        "--no-lint", action="store_true", help="skip ruff; build the geometry only"
    )
    args = parser.parse_args()

    failures = 0

    print("MODULES")
    for name in modules():
        try:
            importlib.import_module(f"cad.{name}")
            print(f"  ok    cad/{name}.py")
        except Exception as exc:  # noqa: BLE001 - the import error is the payload
            print(f"  FAIL  cad/{name}.py  {type(exc).__name__}: {exc}")
            failures += 1

    print("\nPARTS AND SCENES")
    rows, broken = build_all()
    failures += broken
    for kind, name, status, seconds, note in rows:
        mark = "  ok  " if status == "ok" else " FAIL "
        print(f" {mark} {kind:<6} {name:<24} {seconds:5.2f}s  {note}")

    if not args.no_lint:
        print("\nLINT AND FORMAT")
        checks = (
            (["check", "--fix"], "lint") if args.fix else (["check"], "lint"),
            (["format"], "format") if args.fix else (["format", "--check"], "format"),
        )
        for argv, label in checks:
            code, output = ruff(argv)
            summary = output.splitlines()[-1] if output else "clean"
            print(f"  {'ok  ' if code == 0 else 'FAIL'}  ruff {label:<7} {summary}")
            if code != 0:
                print("\n" + output)
                failures += 1

    print()
    print(f"check: FAIL -- {failures} problem(s)" if failures else "check: pass")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
