# /// script
# requires-python = ">=3.11"
# dependencies = ["zoo-kcl>=0.3.181"]
# ///
"""Measure the printed parts and roll the whole robot's mass up against its ceiling.

Every geometry change is supposed to be reported with its mass delta. This
measures each printed part from the CAD at PA12-CF density, multiplies by the
count the robot carries, adds the bought and estimated items, and compares the
total to the ceiling. Parts, counts and allowances live in mass_budget.toml
beside this file; nothing is hard-coded here.

    uv run tools/mass.py                    # table, plus the delta from baseline
    uv run tools/mass.py --save-baseline    # make this the new baseline

This executes on the real engine — one execution per printed part — and
therefore spends API credits. Volume and mass are the only outputs used: this
API has returned a bounding box 173 mm long for a 115 mm foot, so its centre of
mass and extents are not trusted here (docs/KCL_GOTCHAS.md).

Two known biases, both small and both in the safe direction for a ceiling:
parts left as interpenetrating bodies have their overlaps counted twice, and
printed infill is not modelled, so a real print comes out lighter than its
solid volume suggests.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tomllib
from pathlib import Path

import kcl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUDGET = HERE / "mass_budget.toml"
BASELINE = HERE / "mass_baseline.json"


async def measure(path: Path, density: float) -> tuple[float, float]:
    request = kcl.PhysicalPropertiesRequest()
    request.set_mass(kcl.UnitMass.Grams, density, kcl.UnitDensity.KilogramsPerCubicMeter)
    request.set_volume(kcl.UnitVolume.CubicCentimeters)
    response = await kcl.execute_and_measure(str(path), request)
    return response.get_mass(), response.get_volume()


def delta(current: float, previous: float | None) -> str:
    if previous is None:
        return ""
    change = current - previous
    if abs(change) < 0.05:
        return "     ="
    return f"{change:+7.1f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="write the measured per-part masses to mass_baseline.json",
    )
    args = parser.parse_args()

    budget = tomllib.loads(BUDGET.read_text(encoding="utf-8"))
    density = budget["material"]["density"]
    printed = budget["printed"]
    ceiling = budget["ceiling_g"]

    baseline = {}
    if BASELINE.exists():
        baseline = json.loads(BASELINE.read_text(encoding="utf-8")).get("parts", {})

    print(
        f"engine run: {len(printed)} printed parts at "
        f"{budget['material']['name']} {density} kg/m3 — this spends API credits\n"
    )

    measured: dict[str, float] = {}
    rows = []
    for part in printed:
        path = ROOT / part["file"]
        try:
            mass, volume = asyncio.run(measure(path, density))
        except Exception as exc:  # noqa: BLE001 - the engine diagnostic is the payload
            cause = getattr(exc, "args", ())
            message = cause[0] if cause and isinstance(cause[0], str) else str(exc)
            print(f"{part['file']}: FAILED\n{message}", file=sys.stderr)
            if "auth_token_missing" in message:
                print(
                    "\nauth_token_missing is a BILLING failure, not an authentication "
                    "one. Check https://zoo.dev/account/billing.",
                    file=sys.stderr,
                )
            return 1
        # Stored to a tenth of a gram: finer than that is noise against a 2.3 kg
        # ceiling, and it keeps the baseline readable in a diff.
        measured[part["file"]] = round(mass, 1)
        rows.append((part["label"], part["file"], mass, part["count"], volume))

    width = max(len(label) for label, *_ in rows)
    width = max(width, max(len(item["label"]) for item in budget["fixed"]))

    print(f"{'part':<{width}}  {'each g':>8} {'n':>3} {'total g':>9} {'Δ each':>7}")
    print("-" * (width + 32))

    printed_total = 0.0
    for label, file, mass, count, _volume in rows:
        printed_total += mass * count
        print(
            f"{label:<{width}}  {mass:8.1f} {count:3d} {mass * count:9.1f}"
            f" {delta(mass, baseline.get(file)):>7}"
        )
    print(f"{'printed structure':<{width}}  {'':8} {'':3} {printed_total:9.1f}")
    print()

    fixed_total = 0.0
    for item in budget["fixed"]:
        if "total_g" in item:
            total = item["total_g"]
            print(f"{item['label']:<{width}}  {'':8} {'':3} {total:9.1f}")
        else:
            total = item["each_g"] * item["count"]
            print(
                f"{item['label']:<{width}}  {item['each_g']:8.1f}"
                f" {item['count']:3d} {total:9.1f}"
            )
        fixed_total += total

    total = printed_total + fixed_total
    print("-" * (width + 32))
    print(f"{'total':<{width}}  {'':8} {'':3} {total:9.1f}")
    print(f"{'ceiling':<{width}}  {'':8} {'':3} {ceiling:9.1f}")

    headroom = ceiling - total
    verdict = "under" if headroom >= 0 else "OVER THE CEILING BY"
    print(f"{'headroom':<{width}}  {'':8} {'':3} {abs(headroom):9.1f}  ({verdict})")

    previous_total = None
    if BASELINE.exists():
        previous_total = json.loads(BASELINE.read_text(encoding="utf-8")).get("total_g")
    if previous_total is not None:
        change = total - previous_total
        if abs(change) < 0.05:
            print("\nNo change against the baseline.")
        else:
            print(f"\nAgainst the baseline: {change:+.1f} g (was {previous_total:.1f} g).")

    if args.save_baseline:
        BASELINE.write_bytes(
            (
                json.dumps({"parts": measured, "total_g": round(total, 1)}, indent=2)
                + "\n"
            ).encode("utf-8")
        )
        where = BASELINE.relative_to(ROOT) if BASELINE.is_relative_to(ROOT) else BASELINE
        print(f"\nBaseline written to {where}.")

    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
