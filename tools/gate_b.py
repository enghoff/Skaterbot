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
# differ by exactly the volume recorded here AND by nothing else, which is
# checked by requiring the symmetric difference to be that same figure. A change
# that removes the intended material and also moves something else fails, because
# the symmetric difference then exceeds the delta.
#
# The golden STEPs are never regenerated to make a gate pass. They are the frozen
# record of what the KCL built, and an entry here is how the project says "we
# changed this on purpose, and here is how much".
DEVIATIONS = {
    "joint-rotor-hub": {
        "delta_mm3": -4.2979372781,
        "why": (
            "the arm-root blend is now a true 1 mm fillet tangent to both faces, "
            "where the KCL's solver had built an unconstrained sqrt(8.5) = 2.9155 mm "
            "arc tangent to neither. Carries less material and relieves more. "
            "Affects no printed piece of the wheeled robot -- rotorHub is used by "
            "the hip carrier and the foot, which are the walking robot's."
        ),
    },
}


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

    deviation = DEVIATIONS.get(name)
    if deviation is None:
        ok = rel <= TOLERANCE
        note = ""
    else:
        # Two things have to hold: the volume moved by the stated amount, and
        # nothing moved that was not meant to. The second is the symmetric
        # difference matching the delta -- if anything else changed, it exceeds it.
        expected = deviation["delta_mm3"]
        actual = new.volume - old.volume
        moved_right = abs(actual - expected) <= DEVIATION_TOLERANCE_MM3
        confined = abs(sym - abs(expected)) <= DEVIATION_TOLERANCE_MM3
        ok = moved_right and confined
        if not moved_right:
            note = f"  <-- expected {expected:+.4f} mm3, got {actual:+.4f}"
        elif not confined:
            note = f"  <-- {sym:.4f} mm3 changed, but only {abs(expected):.4f} was intended"
        else:
            note = f"  (deviation {expected:+.4f} mm3, as intended)"

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
            print(f"  {n}: {DEVIATIONS[n]['why']}")
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
