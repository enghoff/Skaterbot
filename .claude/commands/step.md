---
description: Write one STEP file per printable piece, into exports/. Uses the engine.
allowed-tools: Bash(uv run tools/export.py:*)
---

Export the printable pieces:

```
uv run tools/export.py $ARGUMENTS
```

With no arguments it writes all of them. `--list` names the pieces and costs
nothing; `--pieces a,b` exports only those; `--format stl` writes STL instead;
`--mock` runs the isolation wrappers through the local interpreter, which is
free and catches a renamed or unexported piece before the metered run does.

Which pieces exist is not decided here — it is the `[[printed.piece]]` register
in `tools/mass_budget.toml`, the same file that says which parts are printed for
the mass roll-up. Add a piece there, not in the tool.

This executes on the real engine, **one execution per piece**, and spends API
credits. Run `--mock` first if anything in the register changed.

Then:

- Read the table it prints. Every piece has a declared body count in the
  register and the tool compares against it, because isolating one piece out of
  a file that builds several depends on `hide` reaching the exporter. A count
  above the declared one means a sibling part is inside the file: say so and do
  not call the export good.
- Check the bounding extents too. A handed pair must come out as mirror images
  of each other in x; extents that straddle x = 0 symmetrically on a part that
  belongs to one side mean both hands are in the file.
- `--verify` re-runs both those checks against the files already on disk,
  without the engine, so a doubt costs nothing to settle.
