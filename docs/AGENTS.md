# Project Instructions — Torque-Controlled Biped

Standing context for any agent working this CAD (Zookeeper in Design Studio,
or an external agent via Zoo MCP). Full reasoning lives in
[`OPUS_HANDOFF.md`](OPUS_HANDOFF.md) beside this file; this file is the short,
binding version.

The KCL sources are at the repository root (one level up), because Zoo Design
Studio expects `project.toml` and `main.kcl` there. Everything in prose —
this file, the handoff, [`NOTES.md`](NOTES.md), [`CHECKLIST.md`](CHECKLIST.md),
and [`BOM.md`](BOM.md) — lives here in `docs/`.

## Current objective

Build **one complete, manufacturable knee module**. Nothing else.

Do not beautify, globally refine, or re-proportion the rest of the robot. The
architecture is being proven at a single joint first. If a whole-robot change
looks necessary, say so and stop — do not make it.

## Frozen parameters

Do not change these without explicit approval:

| Parameter | Value |
|---|---|
| Neutral height | 380 mm |
| Hip spacing | 96 mm |
| Thigh length | 105 mm |
| Shin length | 105 mm |
| Foot | 115 × 65 mm |
| Actuated DOF | 8 (hip roll, hip pitch, knee pitch, ankle pitch × 2) |
| Actuator | DAMIAO DM-J3507-2EC |

If you believe a frozen parameter must move, state what fails, why, the
proposed value, and the downstream consequences — then wait.

## Mass budget

Hard ceiling **2.0 kg**. Current estimate is 1.92–1.96 kg, so there is roughly
40–80 g of headroom for the entire robot.

Report the mass delta of every geometry change. A change that adds mass needs a
stated justification.

## Joint limits (commissioning values)

Hip roll ±25°, hip pitch −45° to +70°, knee 0° to 110°, ankle ±30°.

These were tightened from the original request because of interference risk.
Verify clearance against them; do not widen them to make a design fit.

## Sourcing constraints

Design around commodity parts available in India:

- standard precision/hardened shaft diameters, common metric bearing IDs
- 6800/6900-series and common miniature bearings
- M3/M4 fasteners; washers, spacers, circlips, or threaded retention
- PETG and TPU

Do **not** design around an unusual imported shoulder bolt or any part that
requires a specific import to reproduce.

## Manufacturing constraints

FDM, modest workshop tooling. Parts must be printable without exotic support
strategies, and orientation should put load paths across layer lines
sensibly rather than along them.

## Known defect — read before touching the feet

The connected foot-frame members currently exist as **overlapping bodies**
because the kernel rejected their 3D union. This is in `foot.kcl` at the
repository root. The exported STL is a concept export, not
manufacturing-ready. Do not treat intersecting bodies as acceptable output;
resolve them into valid solids.

## Working method

For each substantial change, in order: inspect the existing model, name the
governing constraint, explain the intended change, modify the CAD, regenerate
and inspect the geometry, verify dimensions, check collisions, check mass,
check manufacturability, record the outcome in [`NOTES.md`](NOTES.md) and
[`CHECKLIST.md`](CHECKLIST.md) (and [`BOM.md`](BOM.md) if a part was chosen),
and state what risk is left open.

Prefer small iterative steps over large speculative redesigns. Never silently
alter a major parameter.
