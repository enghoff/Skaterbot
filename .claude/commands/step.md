---
description: Write one STEP file per printable piece, into exports/. Free, offline.
allowed-tools: Bash(uv run tools/export.py:*)
---

Export the printable pieces:

```
uv run tools/export.py $ARGUMENTS
```

With no arguments it writes every piece as STEP into `exports/`. `--list` names
the pieces without building anything; `--pieces a,b` exports only those;
`--format stl --out simulation/meshes` writes the meshes the URDF is built from;
`--finished` applies the 0.5 mm chamfer, which is how a piece would actually be
printed, where the default is the part as drawn and as the gates compare it.

Free and offline: a piece is a Python object, so exporting it is a local OCCT
call. It used to be one metered engine execution per piece plus a generated
wrapper scene to isolate it.

Which pieces exist is not decided here — it is the `[[printed.piece]]` register
in `tools/mass_budget.toml`, the same file that says which parts are printed for
the mass roll-up. Add a piece there, not in the tool.

Then:

- Read the table it prints. Every piece has a declared body count in the register
  and the tool re-reads the written file to check it. A count above the declared
  one means a sibling part is inside the file: say so, and do not call the export
  good.
- Check the bounding extents too. A handed pair must come out as mirror images of
  each other in x; extents that straddle x = 0 symmetrically on a part that
  belongs to one side mean both hands are in the file.
- `--verify` re-runs those checks against the files already on disk.
