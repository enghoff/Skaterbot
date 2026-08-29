# Torque-Controlled Biped

A compact, approximately 380 mm, 8-DOF, 3D-printable biped designed around low-ratio, backdrivable, torque-controlled actuators.

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

## Repository layout

The KCL sources sit at the repository root because Zoo Design Studio expects
`project.toml` and `main.kcl` there.

```text
bipedal/
├── project.toml           Zoo Design Studio project file
├── main.kcl               neutral standing assembly
├── pose_check.kcl         crouched single-step pose / clearance check
├── walk_pose_check.kcl    mirrored walking stance, both feet flat
├── roll_limit_check.kcl   hip roll at the inward limit the feet impose
├── torque_limit_pose.kcl  the deepest crouch the knees can hold indefinitely
├── knee_*_check.kcl       knee at 100 and 110 degrees
├── limb_check.kcl         single-joint review model
├── coupon_box.kcl         the Phase 1 bending coupon — print this first
├── parameters.kcl         shared dimensions and joint angles
├── actuator.kcl           simplified DM-J3507-2EC envelope
├── joint.kcl              the joint, designed once, used at all eight
├── limb.kcl               closed-shell limb, parametric on length
├── hardware.kcl           bearing carrier, 6800-2RS, journal
├── hip_carrier.kcl        orthogonal hip roll/pitch carrier
├── thigh.kcl, shin.kcl    the limb at two lengths
├── foot.kcl               ribbed foot tray, sole, sensor seats
├── torso.kcl              pelvis and torso shell, keel, tether entry, cover
├── payload_envelopes.kcl  reserved power-entry and electronics volumes
├── tools/                 check, mass and render scripts (see below)
├── docs/                  project documentation (see above)
├── reference/             vendor STEP and datasheets — design inputs
└── secrets/               local credentials, not committed
```

## Working on the CAD

Three scripts in [`tools/`](tools/), each also available as a slash command in
Claude Code. They run with `uv run`, which fetches their one dependency —
Zoo's own KCL interpreter, the same one the MCP server is built on — by itself.

```bash
uv run tools/check.py              # every .kcl file: mock-execute, lint, format
uv run tools/mass.py               # mass roll-up against the 2 300 g ceiling
uv run tools/views.py main.kcl     # render, in views named front/back/left/right
```

Only the first is free. `check.py` runs entirely on this machine, costs no API
credits and needs no token, so it can be run after every edit; the other two
execute on Zoo's engine and are metered. Views are named in the **robot's**
frame, where `front` is the face it walks towards — the opposite of Zoo's own
camera named "front", which is one of the traps collected in
[`docs/KCL_GOTCHAS.md`](docs/KCL_GOTCHAS.md).

Exported geometry (`*.stl`, `*.step`) and the Design Studio `thumbnail.png` are
deliberately untracked. Vendor geometry under [`reference/`](reference/) is the
exception: it is an input rather than an export, so it is tracked, and
[`reference/README.md`](reference/README.md) records where each file came from
along with its checksum and known caveats.

## Current baseline

- Height: 380 mm
- DOF: 8 (hip roll, hip pitch, knee pitch, ankle pitch per leg)
- Actuator: DAMIAO DM-J3507-2EC, 24 V
- Mass ceiling: 2.3 kg, set by torque rather than chosen — see `docs/PLAN.md`
- Current mass, measured from the CAD: **2.025 kg**, which buys a sustained-load
  knee limit of 45.1° and leaves 275 g of headroom. `uv run tools/mass.py`
  re-measures it.
- Limbs: each is a flat plate in one plane — a Ø52 disc bolted to one actuator's
  rear cover, a Ø36 disc bolted to the next actuator's output, and a channel
  waist between them. Nothing reaches around an actuator, so there is no clevis
  and no far bearing at the knee or the ankle. This works because the knee
  actuator is turned round; it assumes the actuator's own output bearing carries
  the joint moment, which DAMIAO have not yet confirmed.
- The two legs are mirrored about the midline. Both leg segments are 105 mm, so
  the right thigh and the left shin are the same print: two limb parts, as
  before, plus a left and a right foot and hip carrier.
- Power: **tethered.** 24 V and CAN arrive on one umbilical from a bench supply;
  there is no pack on board. What the keel holds instead is a bulk capacitor
  bank, because the battery was also the bus's only sink for regeneration from
  eight backdrivable actuators, and a tether cannot do that job.
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
