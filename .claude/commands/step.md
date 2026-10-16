---
description: Write one STEP file per printable piece, into exports/. Free, offline.
allowed-tools: Bash(uv run tools/export.py:*)
---

Export the printable pieces:

```
uv run tools/export.py $ARGUMENTS
```

With no arguments it writes every piece as STEP into `exports/`, **as it would
be printed** — arrises broken at 0.5 mm by `cad/finish.py`. `--list` names the
pieces without building anything; `--pieces a,b` exports only those;
`--format stl --out simulation/meshes` writes the meshes the URDF is built from;
`--as-drawn` leaves every arris sharp, which is the form gate B compares against
`reference/golden/step` and not the form to send to a printer.

**Anything sent to a bureau is a release:** `--release` writes the set into
`exports/releases/<commit>/`, each file named for the commit it was built from
(`pelvis-shell_8c6cfe4.step`), so the name a bureau's cart shows back says which
geometry it holds. It refuses while `cad/` or the mass budget has uncommitted
changes, refuses to write over a file already released, and releases nothing if
any piece is refused. It ends with a table of file, prints, way up, volume and
SHA-256 for [docs/ORDERS.md](../../docs/ORDERS.md), where the order is recorded
with the bureau's settings — read off the cart when it is built. `--verify --out
exports/releases/<commit>` re-checks a release, including that each file is
still the one its manifest hashed. Every manifest, release or not, names the
commit its files were built from, with `+uncommitted` when `cad/` had moved.

The finish pass used to be the flag rather than the default, which meant the
files in `exports/` were the unfinished part unless somebody remembered to ask.
Nobody should have to remember.

Free and offline: a piece is a Python object, so exporting it is a local OCCT
call. It used to be one metered engine execution per piece plus a generated
wrapper scene to isolate it.

Which pieces exist is not decided here — it is the `[[printed.piece]]` register
in `tools/mass_budget.toml`, the same file that says which parts are printed for
the mass roll-up. Add a piece there, not in the tool.

Then:

- Read the table it prints. **Every file is one solid**: the bodies a piece is
  drawn as are united before it is written, because the first printed pelvis
  was exported as twenty-two separate bodies and came back without sixteen of
  them. The `file is` column says `one solid` only when the file, read back from
  disk, is one solid with one shell to OCCT *and* one closed surface to trimesh,
  which reads it as a slicer would. `REFUSED` means nothing was written, and the
  reason is printed above the table: say so, and do not call the export good.
- The `bodies` column is how many bodies the piece is drawn as, against the
  count the register declares. A count above it means a sibling part is inside
  the piece.
- Check the bounding extents too. A handed pair must come out as mirror images of
  each other in x; extents that straddle x = 0 symmetrically on a part that
  belongs to one side mean both hands are in the file.
- Read the `broken` and `sharp` columns. `broken` is how many arrises the
  finish pass cut and `sharp` how many OCCT would not take — a few on a crowded
  piece is normal and `tools/finish_report.py` says which, but a piece that
  broke *nothing* has skipped the pass and is refused rather than written.
- Tell the vendor which way up each piece prints: `print_up` in the register,
  also written to `manifest.json`. Gate G checks nothing starts in mid-air that
  way up; the pelvis printed rim-down would start nine floor features in air.
- `--verify` re-runs those checks against the files already on disk, and reads
  `manifest.json` for which form each file is in. A file that manifest does not
  name cannot be identified at all — nothing in a `.step` says whether its
  arrises were broken — so export it again rather than guess.
