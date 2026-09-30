---
description: Build every part and scene, then lint and format-check the tree. Free, offline.
allowed-tools: Bash(uv run tools/check.py:*)
---

Sweep the whole project:

```
uv run tools/check.py $ARGUMENTS
```

With no arguments it imports every module in `cad/`, builds every printed piece
and every check scene, requires every printed piece to unite into ONE solid with
no sealed cavity, and then lints and format-checks `cad/`, `tools/` and
`simulation/` against `ruff.toml`. Add `--fix` to apply what ruff can fix on its
own, or `--no-lint` for the geometry alone while iterating.

It is free and offline and takes a few seconds, so run it after every edit.

Then:

- Fix anything that fails and re-run until the sweep is clean.
- Report the result in one line. If everything passes, say so and move on.
- Building a part here **does** evaluate its booleans, unlike the KCL mock
  execution this replaced, so a cut that cannot be made fails here rather than
  later. But a boolean that succeeds is still not a boolean that worked: it does
  not prove a hole is open or a clearance is real. `/gates` is what proves that.
