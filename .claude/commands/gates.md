---
description: Run the six gates the build123d CAD is held to. Free, offline.
allowed-tools: Bash(uv run tools/gate_a.py:*), Bash(uv run tools/gate_b.py:*), Bash(uv run tools/gate_c.py:*), Bash(uv run tools/gate_d.py:*), Bash(uv run tools/gate_e.py:*), Bash(uv run tools/gate_f.py:*)
---

Run every gate, in order of what it costs:

```
uv run tools/gate_a.py    # every dimension against the frozen reference
uv run tools/gate_b.py    # each piece's solid against its golden STEP
uv run tools/gate_c.py    # the mass roll-up, part by part
uv run tools/gate_d.py    # the joint tree against the pose scenes
uv run tools/gate_e.py    # the holes and pockets, counted on the solid
uv run tools/gate_f.py    # the check scenes' poses and clearances
```

All six are free and offline and take about a minute together. A and B hold the
CAD against `reference/golden/`, which is what the Zoo engine actually built
before the migration and is a tracked input rather than an export.

Then:

- Report which gates ran and what each said. A gate that fails is the finding —
  do not explain it away, and do not report a change as done with one red.
- Gates E and F are written against the DRAWING INTENT rather than against the
  golden reference, so they can fail on a part that is a faithful translation.
  That is deliberate: if E or F fails while B passes, the geometry was always
  wrong and the finding stands on its own.
- A deliberate geometry change is expected to move gate B, and `tools/gate_b.py`
  carries a register of those departures with the reason for each. Add to it
  rather than loosening the tolerance.
