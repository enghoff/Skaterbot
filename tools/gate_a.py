# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9"]
# ///
"""Gate A -- every ported dimension, against what the KCL said, to full precision.

This is the cheapest and widest of the migration gates
(docs/BUILD123D_MIGRATION.md section 4). It compares the build123d parameter
modules under cad/ against reference/golden/parameters.json, which was frozen off
the KCL before the migration started, name for name and as exact floats.

    uv run tools/gate_a.py            # summary, non-zero exit if anything differs
    uv run tools/gate_a.py --verbose  # list every name, including the matches

It reports four things, and only two of them are failures:

  MISMATCH   a name both sides define, with different values. Always a failure.
  EXTRA      a name cad/ defines that the KCL did not. Always a failure: the
             migration is a translation, so a new dimension is either a typo in
             the name or a dimension invented along the way.
  ADDED      a dimension introduced after the port, which the reference cannot
             hold. Allowed only by being named in ADDED below, with its reason.
  CHANGED    a ported dimension whose value has deliberately moved since. Allowed
             only by being named in CHANGED below, which pins BOTH ends of the
             change, so a third value is still a MISMATCH.
  RETIRED    a golden name this branch deliberately dropped, because it
             belonged to the walking robot. Reported as a count, and a failure
             only if one reappears in cad/.
  UNPORTED   a golden name no cad/ module defines yet. Expected while phase 1 is
             in progress, and reported rather than failed. It becomes a failure
             once the last module lands, which is what --strict is for.
  ok         matched exactly.

Free, offline, and no engine. Nothing here executes geometry -- but it does
import the cad/ modules to read their constants, and those import build123d,
which is why it is declared above.
"""

from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "reference" / "golden" / "parameters.json"

# The golden capture holds three exported names that are geometry rather than
# dimensions -- lists of solids that wheeled_electronics.kcl builds. They have no
# parameter to compare against and never will.
NOT_DIMENSIONS = {"torsoElectronics", "torsoReservations", "torsoPayload"}

# Names the KCL defines but the golden capture cannot evaluate, so they are absent
# from the reference through no fault of the port. simulation/kcl_params.py is a
# line evaluator and not an interpreter: it refuses a call into a KCL function
# rather than guessing at it, which is the right behaviour and is why these two
# come out blank.
#
# They are not waved through. Each is checked by hand here, against the same
# arithmetic the KCL function does -- coverBossInset(span) = span / 2 - bossSize / 2:
#
#   bossX = coverBossInset(torsoInnerWidth) = 120.2 / 2 - 8 / 2 = 56.1
#   bossY = coverBossInset(torsoInnerDepth) =  63.2 / 2 - 8 / 2 = 27.6
#
# and cad/torso.py computes 56.1 and 27.6. If either moves, this note is wrong and
# has to be redone rather than extended.
UNEVALUATABLE = {"bossX": 56.1, "bossY": 27.6}

# Names the golden reference holds that this branch has DELIBERATELY retired,
# because the walking robot they belonged to was deleted from it. They are not
# "not ported yet" and reporting them that way would make the unported list grow
# a permanent tail of things nobody intends to port. The gate asserts the
# opposite of what it asserts everywhere else: a retired name reappearing in
# cad/ is the failure, because it would mean the walking robot crept back in.
#
# The numbers themselves survive in reference/golden/parameters.json and on the
# `main` branch. cad/parameters.py carries the reasoning.
RETIRED = {
    # the foot
    "footLength",
    "footWidth",
    "footCenterY",
    "soleThickness",
    "footTrayHeight",
    # the axis chain the foot decided, replaced by the wheel's radius
    "ankleAxisHeight",
    "kneeAxisHeight",
    "hipPitchAxisHeight",
    "hipRollAxisHeight",
    "hipAxisOffset",
    # the walking torso, replaced by one derived from what fits inside it
    "torsoBottom",
    "torsoTop",
    "torsoHeight",
    "torsoCenterHeight",
    "torsoWidth",
    "torsoDepth",
    # the hip carrier, which hung hip pitch off a hip roll actuator. Only its
    # own connector-shroud dimensions: carrierThickness and journalCenterX look
    # like they belong here and do not -- they are lib/hardware.kcl's, the
    # bearing carrier and journal, which this robot still uses at hip pitch.
    "connectorHeight",
    "connectorInnerDepth",
    "connectorInnerWidth",
}


# Dimensions ADDED after the port, which the golden reference cannot hold because
# the KCL never had them. The migration proper invents nothing -- that is what the
# EXTRA rule enforces -- so every entry here is a deliberate design change made on
# top of a finished, gated translation, and it names the change it belongs to.
#
# A name may only be added here alongside the commit that introduces it, and with
# a reason. If this list ever grows without one, the EXTRA rule has stopped
# meaning anything.
ADDED = {
    # cad/finish.py: the 0.5 mm chamfer put on every printed part's outer edges.
    # About one and a half layers at this nozzle -- a deburr, not a feature.
    "CHAMFER": 0.5,
}


# Dimensions the port carried FAITHFULLY and that have since been CHANGED on
# purpose. Different from ADDED: the golden reference does hold these names, so
# both ends of the change are pinned here -- what the KCL said, and what cad/ now
# says. A value that matches neither is still a MISMATCH, so this records a
# decision without loosening the gate. The reason lives with the dimension in
# cad/parameters.py; the sentence here is the index entry.
CHANGED = {
    "statorPlateFlatOffset": (
        19.0,
        20.0,
        "the connector relief is cut flush with the limb's flank rather than on "
        "the housing's connector flat, because widening the waist to 40 mm had "
        "left the limb standing a millimetre proud of the relief",
    ),
}


def ported_values() -> tuple[
    dict[str, float], dict[str, str], dict[str, str], list[str]
]:
    """Every constant the cad/ package defines, and which module defined it."""
    sys.path.insert(0, str(ROOT))
    import cad  # noqa: F401

    clashes: list[str] = []
    numbers: dict[str, float] = {}
    colors: dict[str, str] = {}
    origin: dict[str, str] = {}

    for info in pkgutil.iter_modules([str(ROOT / "cad")]):
        module = importlib.import_module(f"cad.{info.name}")
        for name, value in vars(module).items():
            if name.startswith("_"):
                continue
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                # Two modules may legitimately define the same name -- the torso
                # and the electronics both derive saddleTopZ, from different
                # directions, and agreeing is the point. Two modules defining it
                # DIFFERENTLY is a real fault, and a flat dict would hide it, so
                # it is caught here rather than silently resolved by import order.
                if name in numbers and numbers[name] != float(value):
                    clashes.append(
                        f"  CLASH     {name}: cad/{origin[name]}.py says "
                        f"{numbers[name]!r}, cad/{info.name}.py says {float(value)!r}"
                    )
                numbers[name] = float(value)
                origin[name] = info.name
            elif isinstance(value, str) and value.startswith("#") and len(value) == 7:
                colors[name] = value.lower()
                origin[name] = info.name
    return numbers, colors, origin, clashes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="list the matches too")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail on UNPORTED as well; for the end of phase 1",
    )
    args = parser.parse_args()

    if not GOLDEN.exists():
        print(f"no golden reference at {GOLDEN.relative_to(ROOT)}", file=sys.stderr)
        print("run: uv run tools/capture_golden.py", file=sys.stderr)
        return 2

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    gold_numbers: dict[str, float] = golden["dimensions"]
    gold_colors = {
        k: "#" + "".join(f"{round(c * 255):02x}" for c in v)
        for k, v in golden["colors"].items()
    }

    numbers, colors, origin, clashes = ported_values()

    mismatch: list[str] = []
    extra: list[str] = []
    changed: list[str] = []
    unported: list[str] = []
    matched = 0

    for name, value in sorted(numbers.items()):
        if name in ADDED:
            if value != ADDED[name]:
                mismatch.append(
                    f"  MISMATCH  {name} (added after the port, see ADDED):"
                    f" expected {ADDED[name]!r}, cad says {value!r}"
                )
            else:
                matched += 1
            continue
        if name in RETIRED:
            extra.append(
                f"  RETIRED   {name} is back in cad/{origin[name]}.py"
                f" -- it belongs to the deleted walking robot"
            )
            continue
        if name in UNEVALUATABLE:
            if value != UNEVALUATABLE[name]:
                mismatch.append(
                    f"  MISMATCH  {name} (hand-checked, see UNEVALUATABLE):"
                    f" expected {UNEVALUATABLE[name]!r},"
                    f" cad says {value!r}  (cad/{origin[name]}.py)"
                )
            else:
                matched += 1
            continue
        if name not in gold_numbers:
            extra.append(f"  EXTRA     {name}  = {value!r}  (cad/{origin[name]}.py)")
            continue
        if name in CHANGED:
            was, now, _ = CHANGED[name]
            if gold_numbers[name] == was and value == now:
                matched += 1
                changed.append(f"  CHANGED   {name}  {was!r} -> {now!r}")
            else:
                mismatch.append(
                    f"  MISMATCH  {name} (changed on purpose, see CHANGED):"
                    f" expected {was!r} -> {now!r},"
                    f" kcl says {gold_numbers[name]!r} and cad says {value!r}"
                )
            continue
        if value != gold_numbers[name]:
            mismatch.append(
                f"  MISMATCH  {name}\n"
                f"              kcl {gold_numbers[name]!r}\n"
                f"              cad {value!r}   (cad/{origin[name]}.py)"
            )
        else:
            matched += 1
            if args.verbose:
                print(f"  ok        {name:<34} {value!r}")

    for name, value in sorted(colors.items()):
        if name not in gold_colors:
            extra.append(f"  EXTRA     {name}  = {value!r}  (cad/{origin[name]}.py)")
        elif value != gold_colors[name]:
            mismatch.append(
                f"  MISMATCH  {name}   kcl {gold_colors[name]}   cad {value}"
            )
        else:
            matched += 1

    for name in sorted(set(gold_numbers) | set(gold_colors)):
        if name in NOT_DIMENSIONS or name in RETIRED:
            continue
        if name in numbers or name in colors:
            continue
        unported.append(name)

    for line in clashes:
        print(line)
    for line in mismatch:
        print(line)
    for line in extra:
        print(line)
    for line in changed:
        print(line)

    # The two UNEVALUATABLE names are checked and counted as matches, but the
    # golden capture could not evaluate them so they are not in its key set.
    golden_names = set(gold_numbers) | set(gold_colors)
    total_golden = (
        len(golden_names - NOT_DIMENSIONS - RETIRED) + len(UNEVALUATABLE) + len(ADDED)
    )
    print()
    print(f"gate A: {matched}/{total_golden} live golden names matched exactly")
    print(f"        {len(RETIRED)} retired with the walking robot, correctly absent")
    print(f"        {len(ADDED)} added after the port, by name and with a reason")
    if changed:
        print(f"        {len(changed)} changed on purpose since the port:")
        for name, (was, now, why) in sorted(CHANGED.items()):
            print(f"          {name} {was!r} -> {now!r}: {why}")
    if unported:
        print(f"        {len(unported)} not ported yet:")
        for i in range(0, len(unported), 4):
            print("          " + "  ".join(f"{n:<30}" for n in unported[i : i + 4]))
    if mismatch:
        print(f"        {len(mismatch)} MISMATCH")
    if extra:
        print(f"        {len(extra)} EXTRA")

    if clashes:
        print(f"        {len(clashes)} CLASH")
    failed = bool(mismatch or extra or clashes) or (args.strict and bool(unported))
    print("        FAIL" if failed else "        pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
