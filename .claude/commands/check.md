---
description: Mock-execute, lint and format-check every KCL file. Free, offline, no engine.
allowed-tools: Bash(uv run tools/check.py:*)
---

Check the KCL sources with the local interpreter:

```
uv run tools/check.py $ARGUMENTS
```

With no arguments it checks every `.kcl` file in the project; pass filenames to
check only those. Add `--fix` to rewrite anything the formatter disagrees with.

This costs no API credits and needs no token, so run it freely — after every
edit, and on every file you touched.

Then:

- Fix anything that fails, and re-run until the sweep is clean.
- Report the result in one line. If everything passes, say so and move on.
- Do **not** claim the geometry is good on the strength of this. Mock execution
  never evaluates the booleans, so every engine refusal listed in
  `docs/KCL_GOTCHAS.md` passes here. Geometry needs `execute_kcl` or
  `tools/views.py`.
