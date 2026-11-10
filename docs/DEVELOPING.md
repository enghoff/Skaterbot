# Developing Skaterbot

Working notes for anyone changing the robot. The project's front page is
[`README.md`](../README.md); [`AGENTS.md`](AGENTS.md) and
[`../CLAUDE.md`](../CLAUDE.md) hold the rules the work is done under.

## Key documents

All project documentation lives in this folder:

- [`docs/AGENTS.md`](AGENTS.md) — binding instructions for any agent working this CAD. **Read this first.**
- [`docs/ZOOKEEPER_TASK.md`](ZOOKEEPER_TASK.md) — the last CAD task brief, now closed and superseded. There is no open brief.
- [`docs/OPUS_HANDOFF.md`](OPUS_HANDOFF.md) — the original engineering brief. Objectives and actuator reasoning still stand; its structure, mass and battery figures are superseded by `PLAN.md`.
- [`docs/NOTES.md`](NOTES.md) — the running engineering log: what was measured, what was found, and what turned out to be wrong. Read it back to front.
- [`docs/PLAN.md`](PLAN.md) — **the active plan**: overhauling the skeleton into a stressed-shell design.
- [`docs/CHECKLIST.md`](CHECKLIST.md) — superseded by `PLAN.md`; kept as the record of the skeleton design.
- [`docs/BOM.md`](BOM.md) — provisional bill of materials with India-focused sourcing notes and supply-risk flags.
- [`docs/CARRIER.md`](CARRIER.md) — the controller carrier: what is soldered to what, why each part is where it is, and what the board is checked against.
- [`docs/DIAGNOSTICS.md`](DIAGNOSTICS.md) — the diagnostics link: the controller firmware, the Banana Pi's daemon and the client that carry all three CAN buses, the IMU and the battery bus to a program on the Pi or a PC, what stops the motors when any part of it fails, and what has and has not been run.
- [`docs/POWER_SWITCH.md`](POWER_SWITCH.md) — the power switch board: the main fuse, the bus shunt, the bulk bank and the MOSFET switch that is the robot's on/off and its low-battery cutoff. Every part on it is through-hole, and since 2026-09-16 the button on the rear wall is the only thing that turns the robot on — the loop key is gone, and nothing isolates the pack but its own connector.
- [`docs/BUILD123D_MIGRATION.md`](BUILD123D_MIGRATION.md) — how the CAD moved from KCL to build123d, and the six gates it is held to.
- [`docs/KCL_GOTCHAS.md`](KCL_GOTCHAS.md) — what the Zoo engine refused and which way the robot faces. **History now**, but it is why several parts are shaped as they are: the interpenetrating shells, the rectangular cable ports, the arcs drawn into profiles instead of real fillets.

One README sits outside `docs/`, beside the code it describes:
[`simulation/README.md`](../simulation/README.md) — how the CAD becomes a URDF, the
frame and joint-sign conventions, and how much of the robot has actually been
measured.

## Repository layout

The CAD is one flat Python package. The KCL-era split between the project root
and `lib/` is gone along with the reason for it: importing a KCL module ran it,
and any solid it built at its top level joined your scene whether you asked for
it or not, so the shared modules had to be geometry-free and reached through a
single facade. A Python module that defines functions builds nothing, and a scene
assembles what it asks for by calling functions.

```text
Skaterbot/
├── cad/                   the CAD — build123d, one flat package
│   ├── parameters.py      shared dimensions and joint angles, with provenance
│   ├── wheeled_parameters.py  the donor wheel and the axis heights it implies
│   ├── joint.py           the joint, designed once, used at all six
│   ├── limb.py            closed-shell limb, parametric on length
│   ├── hardware.py        bearing carrier, 6800-2RS, journal
│   ├── torso_shell.py     lid and cover bosses, as functions taking a box size
│   ├── skate_wheel.py     the bought 80 x 24 mm wheel the adapter drives
│   ├── geometry.py        the mirroring and profile helpers the parts share
│   │
│   ├── thigh.py, shin.py  the limb at two lengths — the printed parts
│   ├── wheel_adapter.py   the printed part that drives a skate wheel
│   ├── torso.py           six-motor pelvis, 125 x 68 x 65, hip pitch in its floor
│   ├── actuator.py        simplified DM-J3507-2EC envelope
│   ├── wheel.py           adapter, wheel and clamp, as the assemblies place it
│   ├── electronics.py     the boards that set the torso's height, and their envelopes
│   │
│   ├── main.py            robotAssembly() — the neutral standing assembly
│   ├── poses.py           the check scenes' poses, as numbers
│   ├── scenes.py          the check scenes, as bodies placed at those poses
│   ├── finish.py          the 0.5 mm chamfer, applied on the way out
│   └── dimensions.py      every constant and colour, collected for simulation/
│
├── tools/                 check, gates, mass, view and export scripts (see below)
├── bench/                 the motors on the bench: a window to configure and drive
│                          them through DAMIAO's USB-to-CAN debugger or the robot's
│                          own buses (motor_gui.py)
├── simulation/            the CAD as a URDF, for Isaac Sim and RL (see below)
├── docs/                  project documentation (see above)
├── reference/             vendor STEP and datasheets — design inputs
│   └── golden/            what the Zoo engine built, frozen: the gates' reference
└── secrets/               local credentials, not committed
```

The check scenes are `cad/scenes.py`, one function each: the crouched pose with
one wheel lifted, the deepest legal squat, the knee at 100 and 110 degrees, the
pelvis with its lid off and the boards in it, one limb on its own and one wheel
module on its own. `uv run tools/view.py --list` names them.

Two KCL files went without a Python equivalent, and both were studies rather than
parts of the robot: a printable bending coupon for the limb section, and a
side-by-side comparison of the rotor-arm fillet. The coupon is worth rebuilding
when someone is ready to print and test one; the fillet study is spent, because
that fillet is real geometry in `cad/joint.py` now.

## Working on the CAD

Six scripts in [`tools/`](../tools/), each also a slash command in Claude Code. They
run with `uv run`, which fetches build123d by itself. **All of them are free,
offline and take seconds** — the metered engine is gone.

```bash
uv run tools/check.py              # build every part and scene, then lint and format
uv run tools/gate_a.py             # … through gate_i.py: the nine gates
uv run tools/mass.py               # mass roll-up against the 2 300 g ceiling
uv run tools/export.py             # one STEP per printable piece, as it would be printed
uv run tools/view.py               # show a model in the OCP CAD Viewer
uv run simulation/build_urdf.py    # the simulation model
```

`check.py` is the sweep to run after every edit: it imports every module, builds
every printed piece and every check scene, and lints and format-checks the tree
against `ruff.toml`. Unlike the KCL mock execution it replaced, building a part
evaluates its booleans, so a cut that cannot be made fails here rather than
later.

The gates are what make "the CAD is right" a measured claim.
[`reference/golden/`](../reference/golden/) holds what the Zoo engine actually built
before the migration — one STEP per printed piece, every dimension to full
precision, every check scene's pose — and gates A to D hold today's Python
against it. Gates E and F are written against the drawing intent instead: E
counts the holes and pockets that must exist **on the finished solid**, which is
the permanent answer to a boolean that silently fills a hole back in, and F
measures every clearance the check scenes were drawn to show.

`export.py` writes the parts you would hand to a printer, one file per piece, and
re-reads each file to check it against the body count declared in the
`[[printed.piece]]` register in
[`tools/mass_budget.toml`](../tools/mass_budget.toml) — the same file that lists what
is printed for the mass roll-up, so the two cannot drift apart. What comes out
is the part **as it would be printed**, its arrises broken at 0.5 mm by
[`cad/finish.py`](../cad/finish.py) — and the run says how many it broke and how
many OCCT left sharp rather than taking the pass on trust. `--as-drawn` asks for
the other form, the one gate B compares against the golden STEP, and a
`manifest.json` beside the files records which of the two each of them is.

Exported geometry (`*.stl`, `*.step`) is deliberately untracked. Geometry under
[`reference/`](../reference/) is the exception: it is an input rather than an export,
so it is tracked, and [`reference/README.md`](../reference/README.md) records where
each file came from along with its checksum and known caveats. The simulation
meshes under `simulation/urdf/meshes/` are tracked for the same reason — they are
what the URDF points at.

## Simulation

[`simulation/`](../simulation/) turns the CAD into a URDF of the wheeled robot,
with a full inertia tensor for every link, and an Isaac Lab config to load it.
Its own [`README`](../simulation/README.md) has the detail; the workflow is one
free command:

```bash
uv run simulation/build_urdf.py     # rebuild from the CAD
uv run simulation/check_model.py    # check it against the CAD
```

Nothing in it is a second copy of a dimension: the kinematics are read out of
`cad/` by `cad/dimensions.py`, the printed masses and inertias are integrated
from the exported meshes, and the bought masses come from
`tools/mass_budget.toml`. A change to a joint height, an axis or a mass allowance
carries through on its own; only a printed part changing *shape* needs a fresh
mesh, and the build refuses to run against a stale one rather than quietly mixing
new kinematics with old geometry.

`check_model.py` drives the tree to the angles of `cad/poses.py`'s `pose_check`
and `squat_check` and checks the wheels land where those scenes independently
compute them, which exercises every link length, joint origin and axis sign at
once. It closes by totalling the robot's mass **by provenance** — read that
before quoting a simulation result, because only a fifth of this robot's mass is
measured geometry.
