# Project Instructions — Torque-Controlled Biped

Standing context for any agent working this CAD. Full reasoning lives in
[`OPUS_HANDOFF.md`](OPUS_HANDOFF.md) beside this file; this file is the short,
binding version.

**Two things here are older than the branch you are on.** The frozen parameters
and the mass ceiling below describe the eight-motor WALKING robot, which now
lives on the `walking` branch. `main` is the six-motor wheeled robot: 6 DOF,
339 mm, a 2 300 g ceiling, and no hip roll or ankle at all. `../CLAUDE.md` and
`../README.md` are current; where they disagree with this file, they win.

The CAD is build123d in `../cad/`, one flat Python package, and every check is
free and local — see `../CLAUDE.md`. It was KCL executed on Zoo's engine until
September 2026; [`BUILD123D_MIGRATION.md`](BUILD123D_MIGRATION.md) is the record
of the move. Everything in prose — this file, the handoff,
[`NOTES.md`](NOTES.md), [`CHECKLIST.md`](CHECKLIST.md), and [`BOM.md`](BOM.md)
— lives here in `docs/`.

## Current objective

Build **one complete, manufacturable knee module**. Nothing else.

There is an open task brief at [`ZOOKEEPER_TASK.md`](ZOOKEEPER_TASK.md) that
scopes the immediate step. If it is still marked open, do that rather than
inventing your own starting point. The support architecture is now settled — the
fixed link anchors to the actuator's rear face — so that brief is an
implementation task, and it lists what has already been established and must not
be re-opened.

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

## Torque duty limit

The actuator is rated **0.8 Nm continuous and 3 Nm peak**. Peak is not a duty
rating, and the continuous figure is the one that binds. Static single-leg
stance crosses 0.8 Nm at roughly **47° of knee flexion**, and at three times
body weight the 3 Nm peak arrives at **60°**.

Keep the mechanical stop at 110° so the robot can crouch and recover, but treat
sustained loaded stance past about 45° as outside the thermal envelope. Design
hard stops for the full range and leave the duty limit to the controller. The
derivation is in [`NOTES.md`](NOTES.md).

## Actuator geometry is now authoritative — use it

The vendor STEP, 2D print and manual are published at
`gitee.com/kit-miao/DM-J3507-2EC`. Do not re-guess the interface. The output
face carries **6 × M3 on a Ø24 mm bolt circle** inside a Ø30 mm register; the
housing carries **4 × M3 on Ø41 mm**; there is **no rear spigot**, so any
opposite support bearing needs a stub axle you supply. These are declared in
`../cad/parameters.py` — reference them rather than restating numbers.

## No hardware exists

Nothing can be bench tested, printed or measured. Do not propose a step whose
output is a physical measurement, and do not record an analytical result as
though it were validated. Thermal behaviour, backdrivability, PETG creep,
layer strength and printed bearing-pocket accuracy are all open; say so
explicitly rather than designing past them.

This constraint used to have a second half, and it is worth recording that it is
gone: the CAD could not be executed outside Design Studio, so every change was
unverified until someone opened the app. Now `uv run tools/check.py` builds every
part and scene locally in a few seconds, and the six gates check the result
against what the engine built before the migration. There is no longer any excuse
for reporting a change without having built it.

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

## Known defect — the pieces are still interpenetrating bodies

Every printed piece is several overlapping shells rather than one solid, because
the Zoo engine refused to union them: the pelvis shell is seven bodies, a limb
five, a wheel adapter three. A slicer merges them, so the parts are printable,
but an exported STEP is not a valid single solid and the mass roll-up counts
every overlap twice.

OCCT will union them, so this is fixable now and it is phase 3 of
[`BUILD123D_MIGRATION.md`](BUILD123D_MIGRATION.md) — with one obstacle recorded
there: a body carrying the 0.5 mm chamfer segfaults OCCT in any subsequent
boolean, so the union and the chamfer cannot currently both be had. The `bodies`
count on each `[[printed.piece]]` in `../tools/mass_budget.toml` is the register
of what is still to be resolved. The foot this section used to be about belonged
to the walking robot and is not on this branch.

## Working method

For each substantial change, in order: inspect the existing model, name the
governing constraint, explain the intended change, modify the CAD, regenerate
and inspect the geometry, verify dimensions, check collisions, check mass,
check manufacturability, record the outcome in [`NOTES.md`](NOTES.md) and
[`CHECKLIST.md`](CHECKLIST.md) (and [`BOM.md`](BOM.md) if a part was chosen),
and state what risk is left open.

Prefer small iterative steps over large speculative redesigns. Never silently
alter a major parameter.

"Regenerate and inspect the geometry" means inspect the **feature**, not the
part. Where a hole or a pocket sits in a plane that another body is unioned to,
the boolean will fill it back in without complaining, and a clean `/check` and a
plausible mass both report nothing — which is how the rotor hub carried four
filled bolt holes through several rebuilds, on the joint that takes the
actuator's full torque.

The answer is no longer a render. `../tools/gate_e.py` counts the holes, bores
and pockets on the finished solid, and `../tools/gate_f.py` measures the
clearances the check scenes were drawn to show. Add your feature's assertion to
gate E when you cut it, and say which check you ran.
