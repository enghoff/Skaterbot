# Torque-Controlled Biped

A compact, approximately 340 mm, 3D-printable biped designed around low-ratio, backdrivable, torque-controlled actuators. On this branch it is a **wheeled** robot with **6 DOF** — hip pitch, knee pitch and a driven wheel on each leg. The walking robot it grew out of has 8 and stands 380 mm, and is `walking_main.kcl` here and `main.kcl` on `main`.

The structure is flat printed plates lying in the actuators' own planes, with the actuators sandwiched between them and left exposed so they can cool.

The current baseline uses DAMIAO DM-J3507-2EC actuators and PA12-CF printed shells. The immediate engineering gate is a printed box coupon: the whole structural case rests on a calculated 73-fold stiffness gain that has not yet been measured.

## Key documents

All project documentation lives in [`docs/`](docs/):

- [`docs/AGENTS.md`](docs/AGENTS.md) — binding instructions for any agent working this CAD. **Read this first.**
- [`docs/ZOOKEEPER_TASK.md`](docs/ZOOKEEPER_TASK.md) — the currently open CAD task brief.
- [`docs/OPUS_HANDOFF.md`](docs/OPUS_HANDOFF.md) — the original engineering brief. Objectives and actuator reasoning still stand; its structure, mass and battery figures are superseded by `PLAN.md`.
- [`docs/NOTES.md`](docs/NOTES.md) — the running engineering log: what was measured, what was found, and what turned out to be wrong. Read it back to front.
- [`docs/PLAN.md`](docs/PLAN.md) — **the active plan**: overhauling the skeleton into a stressed-shell design.
- [`docs/CHECKLIST.md`](docs/CHECKLIST.md) — superseded by `PLAN.md`; kept as the record of the skeleton design.
- [`docs/BOM.md`](docs/BOM.md) — provisional bill of materials with India-focused sourcing notes and supply-risk flags.
- [`docs/KCL_GOTCHAS.md`](docs/KCL_GOTCHAS.md) — what this engine refuses, which way the robot faces, and what the failure messages actually mean. Read before designing a pocket, a hole or a union.

One README sits outside `docs/`, beside the code it describes:
[`simulation/README.md`](simulation/README.md) — how the CAD becomes a URDF, the
frame and joint-sign conventions, and how much of the robot has actually been
measured.

## Repository layout

The models and the parts they place sit at the repository root, because Zoo
Design Studio expects `project.toml` and `main.kcl` there. The dimensions and the
shared drawing functions sit in [`lib/`](lib/) and arrive through
[`lib/main.kcl`](lib/main.kcl), which re-exports them.

That line is not arbitrary, and it is as much of a hierarchy as KCL allows.
Importing a module runs it, and any solid it built at its top level joins your
scene whether you asked for it or not — so a part file has to be imported by
name, one at a time, by the scene that wants it. Everything in `lib/` is
geometry-free: numbers, and functions that draw only when called. Nothing there
can put a body in a scene by being imported, which is what makes one shared
front door safe. The rest of the tree is fixed by two syntax rules: a
subdirectory can only be entered through its `main.kcl`, and a path may not climb
with `..`. So a check scene cannot be filed away in `checks/` — it would no
longer be able to see the parts it places — and two sibling directories can never
share a third. See [`docs/KCL_GOTCHAS.md`](docs/KCL_GOTCHAS.md).

```text
bipedal/
├── project.toml           Zoo Design Studio project file
│
│   the wheeled robot — this branch
├── main.kcl               neutral standing assembly — the WHEELED robot
├── pose_check.kcl         crouched pose, one wheel lifted / clearance check
├── squat_check.kcl        deepest legal squat, both wheels down
├── knee_*_check.kcl       knee at 100 and 110 degrees
├── wheel_module_check.kcl one wheel motor and its wheel, on their own
├── torso_packing_check.kcl  the pelvis with its lid off and the boards in it
├── limb_check.kcl         single-joint review model
├── coupon_box.kcl         the Phase 1 bending coupon — print this first
├── fillet_study.kcl       fillet radii on the joint saddle, side by side
│
│   the walking robot, kept for comparison and unchanged on `main`
├── walking_main.kcl       neutral standing assembly — the WALKING robot
├── walk_pose_check.kcl    mirrored walking stance, both feet flat
├── roll_limit_check.kcl   hip roll at the inward limit the feet impose
├── torque_limit_pose.kcl  the deepest crouch the knees can hold indefinitely
│
│   the parts — each builds its bodies, so a scene imports the ones it wants
├── actuator.kcl           simplified DM-J3507-2EC envelope
├── thigh.kcl, shin.kcl    the limb at two lengths
├── wheel_adapter.kcl      the printed part that drives a skate wheel
├── wheel.kcl              adapter, wheel and clamp, as the assemblies place it
├── foot.kcl               ribbed foot tray, sole, sensor seats (walking robot)
├── walking_hip_carrier.kcl  the hip carrier at the walking robot's 55 mm span
├── torso.kcl              six-motor pelvis, 125 x 68 x 65, hip pitch in its floor
├── walking_torso.kcl      eight-motor pelvis, 118 x 68 x 106, keel and hip roll
├── wheeled_electronics.kcl  the boards that set the six-motor torso's height
├── payload_envelopes.kcl  reserved power-entry and electronics volumes
│
├── lib/                   dimensions and shared functions — no geometry at all
│   ├── main.kcl           re-exports the rest; the only way in from above
│   ├── parameters.kcl     shared dimensions and joint angles
│   ├── wheeled_parameters.kcl  the donor wheel and the axis heights it implies
│   ├── joint.kcl          the joint, designed once, used at all eight
│   ├── hardware.kcl       bearing carrier, 6800-2RS, journal
│   ├── limb.kcl           closed-shell limb, parametric on length
│   ├── hip_carrier.kcl    orthogonal hip roll/pitch carrier, parametric on span
│   ├── torso_shell.kcl    lid and cover bosses, as functions taking a box size
│   └── skate_wheel.kcl    the bought 80 x 24 mm wheel the adapter drives
│
├── tools/                 check, mass, render and export scripts (see below)
├── simulation/            the CAD as a URDF, for Isaac Sim and RL (see below)
├── docs/                  project documentation (see above)
├── reference/             vendor STEP and datasheets — design inputs
└── secrets/               local credentials, not committed
```

## Working on the CAD

Four scripts in [`tools/`](tools/), each also available as a slash command in
Claude Code. They run with `uv run`, which fetches their one dependency —
Zoo's own KCL interpreter, the same one the MCP server is built on — by itself.

```bash
uv run tools/check.py              # every .kcl file: mock-execute, lint, format
uv run tools/mass.py               # mass roll-up against the 2 300 g ceiling
uv run tools/views.py main.kcl     # render, in views named front/back/left/right
uv run tools/export.py             # one STEP per printable piece, into exports/
```

Only the first is free. `check.py` runs entirely on this machine, costs no API
credits and needs no token, so it can be run after every edit; the other three
execute on Zoo's engine and are metered.

`export.py` writes the parts you would hand to a printer, one file per piece,
and its `--verify` and `--mock` modes cost nothing. Which pieces exist is the
`[[printed.piece]]` register in
[`tools/mass_budget.toml`](tools/mass_budget.toml) — the same file that lists
what is printed for the mass roll-up, so the two cannot drift apart. Views are named in the **robot's**
frame, where `front` is the face it walks towards — the opposite of Zoo's own
camera named "front", which is one of the traps collected in
[`docs/KCL_GOTCHAS.md`](docs/KCL_GOTCHAS.md).

Exported geometry (`*.stl`, `*.step`) and the Design Studio `thumbnail.png` are
deliberately untracked. Vendor geometry under [`reference/`](reference/) is the
exception: it is an input rather than an export, so it is tracked, and
[`reference/README.md`](reference/README.md) records where each file came from
along with its checksum and known caveats. The simulation meshes under
`simulation/urdf/meshes/` are tracked for the same reason — they are what the
URDF points at, so a checkout can be simulated without spending credits.

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
the KCL, the printed masses and inertias are integrated from the exported
meshes, and the bought masses come from `tools/mass_budget.toml`. So a change to
a joint height, an axis or a mass allowance costs nothing to carry through — only
a printed part changing *shape* needs a fresh mesh, and the build refuses to run
against a stale one rather than quietly mixing new kinematics with old geometry.

`check_model.py` drives the tree to the angles in `pose_check.kcl` and
`squat_check.kcl` and checks the wheels land where those scenes independently
compute them, which exercises every link length, joint origin and axis sign at
once. It closes by totalling the robot's mass **by provenance** — read that
before quoting a simulation result, because only a fifth of this robot's mass is
measured geometry.

## Current baseline

- Height: 339 mm. It was 380 until the torso was cut from 106 mm to 65 —
  see `lib/wheeled_parameters.kcl`, which derives that height from the electronics
  rather than choosing it. The walking robot is still 380.
- DOF: 6 (hip pitch, knee pitch, driven wheel per leg). Hip roll was deleted on
  this branch: see `docs/WHEELED_BIPED_ANALYSIS.md` section 11 for the argument
  and what it costs, which is the ability to lean or step sideways at all.
  The walking robot still has 8 (hip roll, hip pitch, knee pitch, ankle pitch).
- Actuator: DAMIAO DM-J3507-2EC, 24 V
- Mass ceiling: 2.3 kg, set by torque rather than chosen — see `docs/PLAN.md`
- Current mass, measured from the CAD: **1.607 kg**, leaving 693 g of headroom.
  `uv run tools/mass.py` re-measures it. Two actuators, two bearing sets, both
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
