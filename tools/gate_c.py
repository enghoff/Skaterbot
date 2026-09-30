# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1"]
# ///
"""Gate C -- the mass roll-up, part by part against the baseline.

The gate is one flag on the tool that does the work, because the migration ended
with the two being the same thing. tools/mass.py measures every printed part off
the build123d geometry, rolls the bought items in and compares the total to the
2 300 g ceiling; `--gate` turns a part that has moved from
tools/mass_baseline.json into an exit code rather than a column.

    uv run tools/gate_c.py         # this, or: uv run tools/mass.py --gate

The comparison is PART BY PART and not on the total, because a total can come out
right by cancellation between two parts that are both wrong -- which is exactly
the error a translation makes. Read tools/mass.py for what the two mass columns
mean and which of them the baseline holds.

Free, offline, no engine.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mass  # noqa: E402

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(mass.main([*sys.argv[1:], "--gate"]))
