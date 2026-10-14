# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1"]
# ///
"""Gate H -- every part against every other part, in every scene.

WHY THIS GATE EXISTS. The first printed lid could not be fitted. Its locating lip
dropped into the cavity across the whole mouth, and the four cover bosses stand
in the cavity's corners flush with the rim, so the lid sat on the bosses and not
on the rim: 124 mm3 of lip and boss in the same place at each corner. The model
had said so all along. Nothing asked it: gate F measures the clearances the check
scenes were DRAWN to show, and its sweep of the torso compares a hand-picked list
of what stands in the cavity -- and the lid was never on the list.

So this gate picks nothing by hand. Every scene is built as named groups, one
group per part (cad/scenes.py and cad/main.py), and every group is measured
against every other: the neutral stance, the crouch, the squat, both knee
reviews, the limb, the wheel module and the packed torso. A new part joins the
sweep by being placed in a scene, and a new scene by being added to
cad/scenes.py's GROUPS; neither has to remember this gate exists.

Two rules a pair of parts:

* SHARED VOLUME IS A FAILURE. Two parts cannot be in the same place. Touching is
  fine -- a lid sits on a rim, a board on its standoffs -- and is what a
  distance of zero with nothing shared means.
* AIR UNDER MIN_FIT_GAP_MM IS A FAILURE, where there is any air at all. A gap
  that small is inside the tolerance of every process that might print either
  part: FDM holds perhaps +/-0.2 mm, powder-bed nylon about the same, so a
  0.1 mm gap in the model is interference or rattle in the part and nobody can
  say which. Either close it to contact or open it to MIN_FIT_GAP_MM.

The reserved volumes are not parts -- they are the space a board is allowed, and
a board stands inside its own by design -- so they are left out here; gate F
holds them against the shell.

WHAT THIS CANNOT SEE is anything not drawn. Most screws are not in these
scenes, so a screw head that does not fit its counterbore, or meets a wall,
passes here. The deck-ledge screws were the known case -- every standard M3 head
reached 0.25 mm into the shell wall -- until they became M2.5s placed by their
heads. THE SIX M3 AT EVERY MOTOR OUTPUT ARE DRAWN, since 14 October 2026, a
group to a joint, in the motor's threads (cad/hardware.py's boltedToOutput):
each touches its counterbore and its thread, and a screw too long for the
thread shares volume with the motor and fails here -- an M3 x 10 shares 29.69
mm3 across the six. The rest is still arithmetic in the part files and in
docs/BOM.md's fastener schedule.

An overlap or a tight gap that is right ON PURPOSE is registered in INTENDED
with its measured value and its reason, pinned both ends like gate B's
register. It is empty, and should stay short.

    uv run tools/gate_h.py                 # every scene
    uv run tools/gate_h.py pose_check      # one

Free, offline, no engine.
"""

from __future__ import annotations

import argparse
import itertools
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Air narrower than this between two parts is inside the print tolerance. See
# the module docstring.
MIN_FIT_GAP_MM = 0.2

# A shared volume below this is two faces meeting, measured through an inexact
# boolean -- contact, not interference. A cubic micron, the same as gate F's.
CONTACT_MM3 = 1e-6

# And a distance below this is contact rather than a gap.
CONTACT_MM = 1e-6

# Groups that are not parts. See the module docstring.
NOT_PARTS = {"reservations"}

# Pairs that are meant to share volume or sit closer than MIN_FIT_GAP_MM:
# (scene, group, group) -> ("shared" or "gap", measured value, why). The groups
# in alphabetical order. Empty, and an entry needs a better reason than that the
# gate complained.
INTENDED: dict[tuple[str, str, str], tuple[str, float, str]] = {}


def scene_builders() -> dict:
    from cad import scenes
    from cad.main import robotAssemblyGroups

    return {"neutral_assembly": robotAssemblyGroups, **scenes.GROUPS}


def _near(a, b, margin: float) -> bool:
    """Do two bounding boxes come within `margin` of each other?"""
    return not (
        a.min.X - margin > b.max.X
        or b.min.X - margin > a.max.X
        or a.min.Y - margin > b.max.Y
        or b.min.Y - margin > a.max.Y
        or a.min.Z - margin > b.max.Z
        or b.min.Z - margin > a.max.Z
    )


def measure(first: list, second: list, boxes: dict) -> tuple[float, float]:
    """(nearest distance, shared volume) between two parts, body by body.

    Body by body rather than union against union: a part's own bodies overlap on
    purpose, and uniting a twenty-two-body pelvis for every pair it is in costs
    far more than the few body pairs whose boxes actually meet.
    """
    shared = 0.0
    nearest = float("inf")
    for a in first:
        for b in second:
            if not _near(boxes[id(a)], boxes[id(b)], MIN_FIT_GAP_MM):
                continue
            common = a & b
            try:
                volume = abs(common.volume) if common is not None else 0.0
            except (ValueError, AttributeError, TypeError):
                volume = 0.0
            if volume > CONTACT_MM3:
                shared += volume
                nearest = 0.0
            elif nearest > 0.0:
                nearest = min(nearest, a.distance_to(b))
    return nearest, shared


def sweep(scene: str, groups: dict) -> tuple[int, int, list[str]]:
    """Every part against every other in one scene. (pairs, failures, lines)"""
    parts = {k: v for k, v in groups.items() if k not in NOT_PARTS and v}
    boxes = {id(b): b.bounding_box() for bodies in parts.values() for b in bodies}
    outline = {}
    for name, bodies in parts.items():
        box = boxes[id(bodies[0])]
        for body in bodies[1:]:
            box = box.add(boxes[id(body)])
        outline[name] = box

    pairs = failures = 0
    lines = []
    for left, right in itertools.combinations(sorted(parts), 2):
        if not _near(outline[left], outline[right], MIN_FIT_GAP_MM):
            continue
        pairs += 1
        nearest, shared = measure(parts[left], parts[right], boxes)
        problem = None
        if shared > CONTACT_MM3:
            problem = ("shared", shared, f"share {shared:.2f} mm3")
        elif CONTACT_MM < nearest < MIN_FIT_GAP_MM:
            problem = ("gap", nearest, f"are {nearest:.3f} mm apart")
        if problem is None:
            continue
        kind, value, said = problem
        entry = INTENDED.get((scene, left, right))
        if entry and entry[0] == kind and abs(entry[1] - value) <= 1e-3:
            lines.append(f"   ok   {left} and {right} {said} -- intended: {entry[2]}")
            continue
        failures += 1
        lines.append(f"  FAIL  {left} and {right} {said}")
    return pairs, failures, lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenes", nargs="*", help="scene names; default is all")
    args = parser.parse_args()

    builders = scene_builders()
    if args.scenes:
        unknown = set(args.scenes) - set(builders)
        if unknown:
            print(f"no such scene: {', '.join(sorted(unknown))}")
            return 2
        builders = {k: v for k, v in builders.items() if k in args.scenes}

    print("EVERY PART AGAINST EVERY OTHER, IN EVERY SCENE")
    print(
        f"parts may touch; they may not share volume, or stand closer than "
        f"{MIN_FIT_GAP_MM} mm without touching"
    )
    total_pairs = total_failures = 0
    for scene, build in builders.items():
        started = time.time()
        groups = build()
        pairs, failures, lines = sweep(scene, groups)
        total_pairs += pairs
        total_failures += failures
        mark = "  ok  " if not failures else " FAIL "
        print(
            f"\n {mark} {scene}: {len([g for g in groups if g not in NOT_PARTS])} "
            f"parts, {pairs} pairs close enough to measure, {failures} failing "
            f"({time.time() - started:.0f}s)"
        )
        for text in lines:
            print(f"      {text}")

    print()
    if total_failures:
        print(f"gate H: FAIL -- {total_failures} of {total_pairs} pairs")
        return 1
    print(f"gate H: pass -- {total_pairs} pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
