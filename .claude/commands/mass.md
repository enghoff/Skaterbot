---
description: Measure the printed parts and roll the robot's mass up against its ceiling. Uses the engine.
allowed-tools: Bash(uv run tools/mass.py:*)
---

Roll up the robot's mass from the CAD:

```
uv run tools/mass.py $ARGUMENTS
```

This executes each printed part on the real engine and **spends API credits**,
so run it when geometry has actually moved, not as a reflex.

The parts, their counts and the bought-item allowances live in
`tools/mass_budget.toml`. If a part was added or removed, edit that file rather
than the script, and keep the provenance note on any fixed figure.

Then:

- Report the total, the headroom against the 2 300 g ceiling, and the delta
  from the baseline. A change that adds mass needs a stated justification.
- If this run is the new reference point, re-run with `--save-baseline` and
  commit `tools/mass_baseline.json` alongside the geometry change.
- Update the mass tables in `docs/PLAN.md` and `docs/BOM.md` if the total moved
  enough to matter.
