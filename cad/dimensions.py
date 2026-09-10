"""Every number and colour the CAD defines, for the things downstream of it.

This is what simulation/kcl_params.py used to be, and it is 30 lines instead of
220. That module existed because the dimensions lived in a language Python could
not read, so it carried a regular-expression parser, a unit-suffix rewriter and a
small expression evaluator for KCL's `sqrt` and `**`. The dimensions are Python
now, so reading them is importing them.

WHAT THE CONTRACT IS, AND WHY IT DID NOT CHANGE. simulation/robot.py, plant.py
and check_model.py all take their numbers through one call that returns
`name -> float` in millimetres and degrees, and colours as fractions of 1. That
is deliberately the same shape the parser returned, so the simulation was rewired
rather than rewritten: the CAD is upstream of it and the interface between them is
this dict.

Nothing here builds geometry, and nothing here holds a dimension of its own. It
collects what the other modules declare, so a name that is not in cad/ is not in
the simulation either.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Modules that define geometry-building functions but no dimensions worth
# exporting, and whose import cost is real. Everything else in the package is
# walked, so a new parameter file is picked up without being registered here.
SKIP = {"dimensions", "finish", "geometry", "main", "scenes"}

# A colour is a `#rrggbb` string at module level, which is how the palette is
# written in cad/parameters.py and cad/electronics.py. Underscored because it is
# not a dimension of the robot, and gate A checks that nothing in cad/ pretends
# to be one -- it caught this constant the first time it was written.
_HEX_LENGTH = 7


def _modules():
    """Every dimension-carrying module in the package, imported."""
    for info in pkgutil.iter_modules([str(HERE)]):
        if info.name in SKIP or info.name.startswith("_"):
            continue
        yield importlib.import_module(f"cad.{info.name}")


def load() -> dict[str, float]:
    """Every constant the CAD declares, in millimetres and degrees.

    Booleans are excluded because Python counts them as integers and a flag is
    not a dimension. Everything else numeric is included, including the derived
    stack heights, which is the point: the simulation reads the DERIVED torso
    height rather than recomputing it from the boards inside.
    """
    found: dict[str, float] = {}
    for module in _modules():
        for name, value in vars(module).items():
            if name.startswith("_") or isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                found[name] = float(value)
    return found


def colors() -> dict[str, tuple[float, float, float]]:
    """Every `name = "#rrggbb"` the CAD declares, as fractions of 1.

    Read rather than retyped for the same reason the dimensions are: a colour
    written into the URDF by hand is a second source of it, and the two drift.
    """
    palette: dict[str, tuple[float, float, float]] = {}
    for module in _modules():
        for name, value in vars(module).items():
            if name.startswith("_") or not isinstance(value, str):
                continue
            if len(value) != _HEX_LENGTH or not value.startswith("#"):
                continue
            try:
                palette[name] = tuple(
                    int(value[i : i + 2], 16) / 255.0 for i in (1, 3, 5)
                )
            except ValueError:
                continue
    return palette


def closure(module: str | None = None) -> set[Path]:
    """Every file a piece's geometry can depend on: all of cad/.

    A piece depends on far more than the file that exports it -- a limb is drawn
    by cad/limb.py out of cad/joint.py's discs on cad/parameters.py's dimensions,
    and a change to any of those changes the printed part -- so "is this exported
    mesh still current" has to be asked about a set of files rather than one.

    THE SET IS THE WHOLE PACKAGE, DELIBERATELY. The KCL version of this walked
    each file's import graph to name the smallest honest set, because re-exporting
    was metered and a spurious stale flag cost real money. Exporting is a local
    OCCT call now and costs seconds, which turns the trade-off around: the
    failure that matters is a mesh that is quietly out of date, and the cheapest
    way to never have one is to treat any change in cad/ as reaching every piece.

    A tracked import graph would also be the wrong tool. Half of what a part file
    takes from cad/parameters.py is plain floats, which carry no record of where
    they came from, so an import walk would miss exactly the dependency most
    likely to move a dimension.

    `module` is accepted and ignored, so a caller can still say what it is asking
    about.
    """
    return {path.resolve() for path in HERE.glob("*.py")}


if __name__ == "__main__":
    import sys

    found = load()
    wanted = sys.argv[1:]
    for key in sorted(found):
        if not wanted or any(w.lower() in key.lower() for w in wanted):
            print(f"{key:<34} {found[key]:12.4f}")
    print(f"\n{len(found)} dimensions read from cad/.")
