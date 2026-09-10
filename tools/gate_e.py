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
    from cad.parameters import (
        bearingCarrierBore,
        journalSeatDiameter,
        m3CapCounterbore,
        m3Clearance,
        rotorFilletRadius,
        rotorRegisterDiameter,
    )

    return {
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
                "Ø30.2 bearing carrier bore in the front cheek",
                bearingCarrierBore / 2,
                1,
            ),
        ],
    }


def registry() -> dict[str, callable]:
    from cad import joint

    return {
        "joint-stator-clevis": joint.statorClevis,
        "joint-rotor-hub": joint.rotorHub,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pieces", nargs="*")
    args = parser.parse_args()

    built = registry()
    wanted = args.pieces or sorted(expectations())

    failures = 0
    for name in wanted:
        rows = expectations().get(name)
        if rows is None or name not in built:
            print(f"{name}: nothing declared yet")
            failures += 1
            continue

        found = cylinder_radii(built[name]())
        print(name)
        for what, radius, count in rows:
            got = found.get(round(radius, PLACES), 0)
            ok = got == count
            failures += 0 if ok else 1
            mark = "  ok  " if ok else " FAIL "
            print(f" {mark} {count:>2} x r{radius:<7.3f}  found {got:>2}   {what}")

    print()
    print("gate E: FAIL" if failures else "gate E: pass")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
