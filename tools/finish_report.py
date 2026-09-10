# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9"]
# ///
"""What the 0.5 mm chamfer costs, piece by piece, and how many arrises it missed.

The chamfer is a real design change on top of the faithful port, so it gets its
own measurement rather than being folded into gate C. This is that measurement.

    uv run tools/finish_report.py                  # every printed piece
    uv run tools/finish_report.py pelvis-shell     # just one

The mass column is the SUM of the piece's bodies before and after, which is the
same convention tools/gate_c.py and the baseline use -- overlaps counted twice,
erring upward against the ceiling. It is the honest comparison here because the
chamfer does not change how the bodies overlap.

SKIPPED EDGES ARE REAL AND ARE REPORTED. Where OCCT will not cut a chamfer even
on its own, the arris is left sharp. That is a finish defect, not a modelling
error: the part is correct, it just has a few edges the printer will leave crisp.
The clevis is the worst of them and the reason is its own geometry -- two Ø52
discs, a neck and a hollow saddle all meeting in a few millimetres.

Free, offline, no engine.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DENSITY = 1060.0  # PA12-CF, kg/m3, as mass_budget.toml has it


def pieces() -> dict:
    from cad import joint, shin, thigh, torso, wheel_adapter

    return {
        "limb-105-unmirrored": thigh.thighRight,
        "limb-105-mirrored": thigh.thighLeft,
        "wheel-adapter-right": wheel_adapter.wheelAdapterRight,
        "wheel-adapter-left": wheel_adapter.wheelAdapterLeft,
        "pelvis-shell": torso.pelvisShell,
        "torso-cover": torso.torsoCover,
        # not printed pieces in their own right, but they are what the pieces
        # above are mostly made of, so a regression shows up here first
        "joint-stator-clevis": joint.statorClevis,
        "joint-rotor-hub": joint.rotorHub,
        "joint-stator-plate": joint.statorPlate,
        "joint-output-disc": joint.outputDisc,
        "shin-unmirrored": shin.shinLeft,
    }


def grams(bodies) -> float:
    if not isinstance(bodies, (list, tuple)):
        bodies = [bodies]
    return sum(b.volume for b in bodies) * DENSITY * 1e-6


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("piece", nargs="?")
    parser.add_argument("--size", type=float, default=None, help="chamfer, mm")
    args = parser.parse_args()

    from cad.finish import CHAMFER, chamfered

    size = args.size if args.size is not None else CHAMFER
    built = pieces()
    wanted = [args.piece] if args.piece else list(built)

    head = (
        f"{'piece':<22} {'bodies':>6} {'cut':>5} {'sharp':>6} "
        f"{'before g':>9} {'after g':>9} {'delta g':>9} {'s':>6}"
    )
    print(f"chamfer {size} mm on outer edges only\n")
    print(head)
    print("-" * len(head))

    total_before = total_after = 0.0
    total_cut = total_sharp = 0
    for name in wanted:
        if name not in built:
            print(f"{name}: no such piece")
            return 2
        start = time.time()
        original = built[name]()
        before = grams(original)
        finished, cut, sharp = chamfered(original, size)
        after = grams(finished)
        count = len(original) if isinstance(original, (list, tuple)) else 1
        print(
            f"{name:<22} {count:>6} {cut:>5} {sharp:>6} "
            f"{before:>9.3f} {after:>9.3f} {after - before:>+9.3f} {time.time() - start:>6.1f}"
        )
        if name.startswith(("limb-", "wheel-adapter-", "pelvis-", "torso-")):
            total_before += before
            total_after += after
            total_cut += cut
            total_sharp += sharp

    print("-" * len(head))
    print(
        f"{'the six printed pieces':<22} {'':>6} {total_cut:>5} {total_sharp:>6} "
        f"{total_before:>9.3f} {total_after:>9.3f} {total_after - total_before:>+9.3f}"
    )
    print()
    print(
        "That total counts one of each piece. The robot carries two of each limb "
        "and one of everything else, so see tools/gate_c.py for the roll-up."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
