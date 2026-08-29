---
description: Render a model from several sides, named in the robot's frame. Uses the engine.
allowed-tools: Bash(uv run tools/views.py:*)
---

Render the model the user named (default `main.kcl` if they did not):

```
uv run tools/views.py $ARGUMENTS
```

Views are `front`, `back`, `left`, `right`, `top`, `bottom`, `iso`, `iso_back`,
or `all`; the default is `front,right,iso`. They are named in the **robot's**
frame — `front` is the face it walks towards — which is the opposite of Zoo's
own camera named "front". See `docs/KCL_GOTCHAS.md`.

This executes on the real engine and **spends API credits**. One execution
covers all the views in a single call, so ask for the views you want in one go.
The full assembly can take over two minutes; that is normal.

Then:

- Read the PNGs it wrote under `renders/` and say what you actually see.
- Check the thing the change was meant to affect, and check it is on the side
  it should be on. A slot cut on the wrong face executes perfectly.
