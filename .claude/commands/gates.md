---
description: Run the nine gates the build123d CAD is held to. Free, offline.
allowed-tools: Bash(uv run tools/gate_a.py:*), Bash(uv run tools/gate_b.py:*), Bash(uv run tools/gate_c.py:*), Bash(uv run tools/gate_d.py:*), Bash(uv run tools/gate_e.py:*), Bash(uv run tools/gate_f.py:*), Bash(uv run tools/gate_g.py:*), Bash(uv run tools/gate_h.py:*), Bash(uv run tools/gate_i.py:*)
---

Run every gate, in order of what it costs:

```
uv run tools/gate_a.py    # every dimension against the frozen reference
uv run tools/gate_b.py    # each piece's solid against its golden STEP
uv run tools/gate_c.py    # the mass roll-up, part by part
uv run tools/gate_d.py    # the joint tree against the pose scenes
uv run tools/gate_e.py    # the holes and pockets, counted on the solid
uv run tools/gate_f.py    # the check scenes' poses and clearances
uv run tools/gate_h.py    # every part against every other, in every scene
uv run tools/gate_g.py    # every piece prints as one part, on any process
uv run tools/gate_i.py    # the torso goes together, in order, part by part
```

All nine are free and offline. A to F take about a minute together; H and I take
about two and one, and G about three, because G builds the file a printer would get for
every piece and reads it back. A and B hold the CAD against `reference/golden/`,
which is what the Zoo engine actually built before the migration and is a
tracked input rather than an export.

G and H exist because gates A to F passed two faults the first printed prototype
found in an afternoon: a pelvis exported as twenty-two separate bodies, sixteen
of which the printer never joined to the shell, and a lid whose lip sat on its
own screw bosses. A to F prove the part is what was drawn. G proves what was
drawn can be printed as one part by FDM, nylon powder or resin, and H proves the
parts fit each other. I proves they can get there: it runs each torso part out
along the way it goes in, in build order, against everything already in.

Then:

- Report which gates ran and what each said. A gate that fails is the finding —
  do not explain it away, and do not report a change as done with one red.
- Gates E to I are written against the DRAWING INTENT rather than against the
  golden reference, so they can fail on a part that is a faithful translation.
  That is deliberate: if one fails while B passes, the geometry was always
  wrong and the finding stands on its own.
- A deliberate geometry change is expected to move gate B, and `tools/gate_b.py`
  carries a register of those departures with the reason for each. Add to it
  rather than loosening the tolerance. G and H have registers of the same kind
  (`ACCEPTED`, `INTENDED`), pinned to the measured value; neither limit is ever
  loosened to make a part pass.
