---
description: Show a model in the OCP CAD Viewer. Free, offline.
allowed-tools: Bash(uv run tools/view.py:*)
---

Show the model the user named, or the whole robot if they did not:

```
uv run tools/view.py $ARGUMENTS
```

`--list` names what can be shown: the neutral assembly, each printed piece on
its own, and each check scene. `--finished` shows a piece with its edges broken.

Free and offline — the geometry is tessellated locally and pushed to a viewer
over a socket, where the KCL `/views` command this replaced rendered on the
metered engine. It needs a viewer listening: either the OCP CAD Viewer panel in
VS Code, or

```
uv run --with ocp_viewer --with build123d python -m ocp_viewer --port 3939
```

Then:

- Say what you actually see, and check the thing the change was meant to affect
  is on the side it should be on. A slot cut on the wrong face builds perfectly.
- Do **not** offer a render as evidence that a feature exists. Structure behind a
  hole makes an open one look closed, which is exactly how four filled bolt holes
  survived several rebuilds here. `uv run tools/gate_e.py` counts the holes on
  the finished solid, and `tools/gate_f.py` measures the clearances; those are
  the evidence, and this is for looking at the machine.
