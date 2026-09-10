---
description: Measure the printed parts and roll the robot's mass up against its ceiling. Free, offline.
allowed-tools: Bash(uv run tools/mass.py:*)
---

Roll up the robot's mass from the CAD:

```
uv run tools/mass.py $ARGUMENTS
```

Free and offline, in about a second — it integrates each part's volume locally
rather than executing it on the Zoo engine, so there is no reason not to run it
on every geometry change. `--union` shows what the parts weigh with their
interpenetrating shells resolved, `--gate` fails if a part has moved from the
baseline, and `--save-baseline` makes the current figures the new reference.

The parts, their counts, the functions that build them and the bought-item
allowances all live in `tools/mass_budget.toml`. If a part was added or removed,
edit that file rather than the script, and keep the provenance note on any fixed
figure.

Then:

- Report the total, the headroom against the 2 300 g ceiling, and the delta from
  the baseline. A change that adds mass needs a stated justification.
- If this run is the new reference point, re-run with `--save-baseline` and
  commit `tools/mass_baseline.json` alongside the geometry change.
- Update the mass tables in `docs/PLAN.md` and `docs/BOM.md` if the total moved
  enough to matter.
