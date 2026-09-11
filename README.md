# Torque-Controlled Biped

A compact, approximately 340 mm, 3D-printable biped designed around low-ratio, backdrivable, torque-controlled actuators. On this branch it is a **wheeled** robot with **6 DOF** — hip pitch, knee pitch and a driven wheel on each leg. The walking robot it grew out of has 8 and stands 380 mm, and lives on the `walking` branch, still in KCL.

The CAD is [build123d](https://build123d.readthedocs.io) — Python over OCCT — in [`cad/`](cad/). It was KCL executed on Zoo's engine until September 2026; [`docs/BUILD123D_MIGRATION.md`](docs/BUILD123D_MIGRATION.md) is the record of the move, and the practical consequence is that every check is now free, local and offline.

The structure is flat printed plates lying in the actuators' own planes, with the actuators sandwiched between them and left exposed so they can cool.

The current baseline uses DAMIAO DM-J3507-2EC actuators and PA12-CF printed shells. The immediate engineering gate is a printed box coupon: the whole structural case rests on a calculated 73-fold stiffness gain that has not yet been measured.

## Key documents

All project documentation lives in [`docs/`](docs/):

- [`docs/AGENTS.md`](docs/AGENTS.md) — binding instructions for any agent working this CAD. **Read this first.**
- [`docs/ZOOKEEPER_TASK.md`](docs/ZOOKEEPER_TASK.md) — the last CAD task brief, now closed and superseded. There is no open brief.
- [`docs/OPUS_HANDOFF.md`](docs/OPUS_HANDOFF.md) — the original engineering brief. Objectives and actuator reasoning still stand; its structure, mass and battery figures are superseded by `PLAN.md`.
- [`docs/NOTES.md`](docs/NOTES.md) — the running engineering log: what was measured, what was found, and what turned out to be wrong. Read it back to front.
- [`docs/PLAN.md`](docs/PLAN.md) — **the active plan**: overhauling the skeleton into a stressed-shell design.
- [`docs/CHECKLIST.md`](docs/CHECKLIST.md) — superseded by `PLAN.md`; kept as the record of the skeleton design.
- [`docs/BOM.md`](docs/BOM.md) — provisional bill of materials with India-focused sourcing notes and supply-risk flags.
- [`docs/BUILD123D_MIGRATION.md`](docs/BUILD123D_MIGRATION.md) — how the CAD moved from KCL to build123d, and the six gates it is held to.
- [`docs/KCL_GOTCHAS.md`](docs/KCL_GOTCHAS.md) — what the Zoo engine refused and which way the robot faces. **History now**, but it is why several parts are shaped as they are: the interpenetrating shells, the rectangular cable ports, the arcs drawn into profiles instead of real fillets.

One README sits outside `docs/`, beside the code it describes:
[`simulation/README.md`](simulation/README.md) — how the CAD becomes a URDF, the
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
bipedal/
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

Six scripts in [`tools/`](tools/), each also a slash command in Claude Code. They
run with `uv run`, which fetches build123d by itself. **All of them are free,
offline and take seconds** — the metered engine is gone.

```bash
uv run tools/check.py              # build every part and scene, then lint and format
uv run tools/gate_a.py             # … through gate_f.py: the six gates
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
[`reference/golden/`](reference/golden/) holds what the Zoo engine actually built
before the migration — one STEP per printed piece, every dimension to full
precision, every check scene's pose — and gates A to D hold today's Python
against it. Gates E and F are written against the drawing intent instead: E
counts the holes and pockets that must exist **on the finished solid**, which is
the permanent answer to a boolean that silently fills a hole back in, and F
measures every clearance the check scenes were drawn to show.

`export.py` writes the parts you would hand to a printer, one file per piece, and
re-reads each file to check it against the body count declared in the
`[[printed.piece]]` register in
[`tools/mass_budget.toml`](tools/mass_budget.toml) — the same file that lists what
is printed for the mass roll-up, so the two cannot drift apart. What comes out
is the part **as it would be printed**, its arrises broken at 0.5 mm by
[`cad/finish.py`](cad/finish.py) — and the run says how many it broke and how
many OCCT left sharp rather than taking the pass on trust. `--as-drawn` asks for
the other form, the one gate B compares against the golden STEP, and a
`manifest.json` beside the files records which of the two each of them is.

Exported geometry (`*.stl`, `*.step`) is deliberately untracked. Geometry under
[`reference/`](reference/) is the exception: it is an input rather than an export,
so it is tracked, and [`reference/README.md`](reference/README.md) records where
each file came from along with its checksum and known caveats. The simulation
meshes under `simulation/urdf/meshes/` are tracked for the same reason — they are
what the URDF points at.

## Simulation

[`simulation/`](simulation/) turns the CAD into a URDF of the wheeled robot,
with a full inertia tensor for every link, and an Isaac Lab config to load it.
Its own [`README`](simulation/README.md) has the detail; the workflow is one
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

## Current baseline

- Height: 339 mm. It was 380 until the torso was cut from 106 mm to 65 —
  see `cad/wheeled_parameters.py`, which derives that height from the electronics
  rather than choosing it. The walking robot is still 380.
- DOF: 6 (hip pitch, knee pitch, driven wheel per leg). Hip roll was deleted on
  this branch: see `docs/WHEELED_BIPED_ANALYSIS.md` section 11 for the argument
  and what it costs, which is the ability to lean or step sideways at all.
  The walking robot still has 8 (hip roll, hip pitch, knee pitch, ankle pitch).
- Actuator: DAMIAO DM-J3507-2EC, 24 V
- Mass ceiling: 2.3 kg, set by torque rather than chosen — see `docs/PLAN.md`
- Current mass, measured from the CAD: **1.607 kg**, leaving 693 g of headroom.
  `uv run tools/mass.py` re-measures it in about a second. Two actuators, two bearing sets, both
  hip carriers and the pelvis keel went with hip roll, and the shorter torso took
  another 32 g, which is about 440 g off the 2.047 kg the eight-motor wheeled
  robot weighed.
- Limbs: each is a flat plate in one plane — a Ø52 disc bolted to one actuator's
  rear cover, a Ø36 disc bolted to the next actuator's output, and a channel
  waist between them. Nothing reaches around an actuator, so there is no clevis
  and no far bearing at the knee or the ankle. This works because the knee
  actuator is turned round; it assumes the actuator's own output bearing carries
  the joint moment, which DAMIAO have not yet confirmed.
- The two legs are mirrored about the midline. Both leg segments are 105 mm, so
  the right thigh and the left shin are the same print: two limb parts, plus a
  left and a right wheel adapter. There is no hip carrier — with hip roll gone,
  the clevis that holds each hip pitch actuator is part of the pelvis.
- Power: **tethered.** 24 V and CAN arrive on one umbilical from a bench supply;
  there is no pack on board. What the pelvis holds instead is a bulk capacitor
  bank, because the battery was also the bus's only sink for regeneration from
  backdrivable actuators, and a tether cannot do that job. It used to live in a
  keel between the hip roll actuators; with those gone the pelvis is one closed
  box down to the hip pitch axes and the bank sits in the bottom of it, beside
  the controller carrier rather than under it. That pair side by side is why the
  shell is 125 mm wide where the walking robot's is 118, and it is what let the
  torso lose 41 mm of height.
- Mechanical prototype: PA12-CF printed shells

## Development order

Steps 1 and 3 need hardware that does not exist yet. The actuator's vendor STEP
and manual are in hand, so step 2 can proceed now and the measurements from
step 1 get folded in later.

1. Characterise 1–2 actuators. *(blocked — no hardware)*
2. Engineer and print one real knee assembly.
3. Validate loads, stiffness, thermal behaviour and backdrivability.
4. Build one complete leg.
5. Build realtime torque/impedance control.
6. Only then commit to the complete robot.
