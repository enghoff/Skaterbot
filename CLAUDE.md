# Reporting

Report in plain English.

Write for the person who owns the rover but does not carry its code in their head. They
want the conclusion and the decision, not the workings.

- Lead with what is the case now: what works, what does not, and what it means for the
  project.
- Anything they cannot act on — the investigation, the options weighed, the names of
  files and settings — is a supporting clause at most, and usually is not needed at all.
- Say plainly when something is unproven, failed, or was skipped.
- Two sentences beat two paragraphs.
- Finish with the next step if there is one.

# CAD work

The CAD is [`cad/`](cad/): parametric solid modelling in
[build123d](https://build123d.readthedocs.io), which is Python over OCCT. Every
part, every assembly and every check is a function you call, and every check is
free and local. Nothing here talks to a remote CAD engine and nothing here costs
API credits.

It was KCL until September 2026, executed on Zoo's engine, and much of the shape
of this repository still comes from that. [`docs/BUILD123D_MIGRATION.md`](docs/BUILD123D_MIGRATION.md)
is the record of the move and the gates it was held to;
[`docs/KCL_GOTCHAS.md`](docs/KCL_GOTCHAS.md) is why several parts are drawn the
way they are, and is now history rather than a working reference. The Zoo MCP
server is still configured in `.mcp.json`, and nothing in this project needs it.

## Validate every change by building it

Run `/check` after every edit. It imports every module in `cad/`, builds every
printed piece and every check scene, and lints and format-checks the tree. It is
free, offline, and takes a few seconds, so there is no reason to iterate without
it.

Building a part **does** evaluate its booleans. That is the main thing the
migration bought: under KCL the free check was a mock execution that never
evaluated a boolean, so a cut the engine would refuse passed it silently, and
confirming geometry meant spending credits. Now a cut that cannot be made fails
in `/check`.

## A boolean that succeeds is not a boolean that worked

Worse than a refusal is a boolean that is **accepted** having built the wrong
solid. Union a body onto a disc after the disc is drilled and the holes are
filled back in, and nothing reports it: `/check` is clean, the part builds,
`/mass` prints a number. The rotor hub carried four filled bolt holes that way
through several rebuilds, on the joint that takes the actuator's full torque.

Under KCL the only available evidence was a render taken down the feature's axis.
Now the finished part is an object with faces, so the question is arithmetic:

- **`/gates`, and gate E in particular**, counts the holes, bores and pockets on
  the finished solid. A Ø3.4 through-hole leaves a cylindrical face of radius
  1.7; six of them leave six; one a union filled back in leaves none, and that
  fails. Assert a new feature there when you add one.
- **Gate F** measures the clearances the check scenes were drawn to show — the
  real distance between two solids, and the volume they share.
- Measuring volume across a change and checking the difference is the size and
  the sign of the feature you intended is still valid, and still cheap.

Say which of those you did when reporting a change. "It built" is not an answer,
and neither is "it looks right".

## Tools in this repository

Six commands, run with `uv run`, which fetches what they need on its own. **All
six are free and offline.**

| | | |
|---|---|---|
| `/check` | `tools/check.py` | build every part and scene, then lint and format-check `cad/`, `tools/` and `simulation/`. A few seconds. |
| `/gates` | `tools/gate_[a-f].py` | the six gates the CAD is held to: dimensions, solid identity, mass, kinematics, features, clearances. About a minute. |
| `/mass` | `tools/mass.py` | measure the printed parts and roll the robot's mass up against its 2 300 g ceiling, with the delta from the committed baseline. |
| `/step` | `tools/export.py` | write one STEP file per printable piece into `exports/`, or the STLs the simulation reads, checking each against its declared body count. Pieces come out as they would be printed, arrises broken; `--as-drawn` is the form the gates compare. |
| `/view` | `tools/view.py` | show a model in the OCP CAD Viewer, tessellated locally. |
| `/urdf` | `simulation/build_urdf.py` | regenerate the simulation URDF from the CAD and check it against the pose scenes. |

Report the mass delta of every geometry change, and make `/check` clean before
saying a change is done.

There is no longer a rendered view sheet. `/views` rendered on the metered
engine, and what replaced it is `/view`, which needs a viewer open. So a change
whose evidence was "look at it" now needs a measurement instead, which is what
gates E and F are for.

## What the CAD is checked against, and why it is trustworthy

[`reference/golden/`](reference/golden/) is a **tracked input**, not an export.
It holds what the Zoo engine actually built before the migration: one STEP per
printed piece, every named dimension to full precision, and every check scene's
computed pose. The gates hold today's Python against it, so "the port is
faithful" is a measured claim and not a hope.

Six gates, in order of what they cost, all free:

| | |
|---|---|
| A | every dimension in `cad/` against `reference/golden/parameters.json`, at zero tolerance |
| B | each printed piece against its golden STEP, by symmetric difference |
| C | the mass roll-up, part by part against `tools/mass_baseline.json` |
| D | the joint tree against the pose scenes, through `simulation/check_model.py` |
| E | the holes and pockets that must exist, counted on the finished solid |
| F | the check scenes' poses against the frozen reference, and their clearances measured |

Gates A and B mean the geometry has not drifted from what was built and printed.
Gates E and F are written against the **drawing intent** instead, so they can
fail on a part that is a faithful translation — and when they do, the finding
stands on its own: the geometry was always wrong.

A deliberate geometry change is expected to move gate B. `tools/gate_b.py`
carries a register of those departures, one line of reason each. Add to it rather
than loosening a tolerance.

## The simulation model is downstream of the CAD, never beside it

[`simulation/`](simulation/) turns the CAD into a URDF the wheeled robot can be
simulated and trained in. Nothing in it is a second copy of a dimension: the
kinematics are read out of `cad/` by `cad/dimensions.py`, the printed masses and
inertia tensors are integrated from the exported meshes, and the bought masses
come from `tools/mass_budget.toml`. **A change to the CAD is followed by
regenerating it, not by editing the URDF**, which carries a do-not-edit banner
for that reason.

`/urdf` is the whole workflow. It refuses to build against a mesh older than the
CAD it came from, names the file that moved, and prints the re-export command for
the affected pieces. That export is free now, so re-exporting everything costs
seconds and there is no reason to be clever about which pieces changed.

`check_model.py` is the regression test. It drives the tree to the exact angles
of `cad/poses.py`'s `pose_check` and `squat_check` and checks the wheel lands
where those scenes independently compute it, which exercises every link length,
joint origin and axis sign at once. It also totals the robot's mass **by
provenance**, and that table is the point: four fifths of this robot has never
been on a scale, so a simulation result is worth what those figures are worth and
no more.

Two things the CAD frame and a URDF disagree about, both handled in one place
each and both easy to reintroduce by hand. The CAD is +Y forward and +X to the
robot's right; a URDF is +X forward, +Y left. And the printed parts are still
several interpenetrating shells, so simply adding their volumes counts the
overlaps twice — `tools/mass.py` accepts that bias on purpose because it errs
upward against a ceiling, but the simulation resolves the union instead, which is
about 18 g lighter across the robot.

## How cad/ is laid out

Every module is in one flat package and imports what it needs by name. The
KCL-era split between the project root and `lib/` is gone, and so is the reason
for it: importing a KCL module RAN it, and any solid it built at its top level
joined your scene whether you asked for it or not, which is why the shared
modules had to be geometry-free and reached through a single facade. A Python
module that defines functions builds nothing, so a scene assembles what it asks
for by calling functions.

| | |
|---|---|
| `parameters.py`, `wheeled_parameters.py` | every dimension, with its provenance |
| `joint.py`, `limb.py`, `hardware.py`, `torso_shell.py`, `skate_wheel.py`, `geometry.py` | the shared drawing functions |
| `thigh.py`, `shin.py`, `wheel_adapter.py`, `torso.py` | the printed parts |
| `actuator.py`, `wheel.py`, `electronics.py` | the bought parts and the payload envelopes |
| `main.py` | the neutral 339 mm assembly, `robotAssembly()` |
| `poses.py`, `scenes.py` | the check scenes: the poses, and the bodies placed at them |
| `finish.py` | the 0.5 mm chamfer, applied on top of the parts rather than inside them |
| `dimensions.py` | every constant and colour, collected for the simulation |

`finish.py` is deliberately a separate pass: the parts stay as gate B compares
them, and the chamfer is added on the way out. Two things it records are worth
knowing before you touch it — OCCT will not chamfer a crowded solid's edges in
one pass, and a body chamfered this way **segfaults OCCT in any subsequent
boolean**, which is why the finished pieces are left as interpenetrating bodies.

## The scenes are the regression suite

`cad/main.py`'s `robotAssembly()` is the neutral 339 mm assembly of the
six-motor wheeled robot: hip pitch, knee and a driven wheel per leg, with no hip
roll at all. **The walking robot is not here.** It is the `walking` branch,
still in KCL, and the two are no longer comparable.

The torso's height is not a chosen number. It is derived in
`cad/wheeled_parameters.py` from what has to fit inside, and `cad/electronics.py`
draws those boards, so the packing is checked rather than asserted. **Anything
that changes a reserved volume changes the robot's height.**

`cad/scenes.py` holds the six other configurations, each of which exists to catch
something the neutral stance hides:

- `pose_check` — crouched stance with one wheel lifted, for sagittal clearance
  and joint-chain validation
- `squat_check` — the deepest squat the knee stop allows with both wheels still
  on the ground, which is where a Ø80 wheel comes closest to its own thigh
- `knee_limit_check` — the knee at its 110° hard stop
- `knee_prelimit_check` — the same knee at 100°, just before contact
- `torso_packing_check` — the pelvis with its lid off and the four payload items
  standing in it, which is where the 65 mm height is justified
- `limb_check`, `wheel_module_check` — one joint and one wheel module on their
  own, for looking at a change narrowly

A change to `cad/parameters.py` or to any shared module reaches all of them.
`/check` builds every one, and gate F measures what each was drawn to show, so
building the neutral assembly alone is not sufficient evidence and must not be
reported as if it were.

**The wheeled robot's torque envelope has not been re-derived.** The KCL scene
that explored it belonged to the walking robot and went with it, and the answer
does change with wheels.

## Dimensions live in cad/parameters.py

`cad/parameters.py` is the single source of mechanical dimensions, and its
comments carry the provenance — which vendor STEP, which 2D print, which
measurement, and where two sources were cross-checked against each other. They
transferred from the KCL word for word. Honour that:

- Keep important dimensions as named module-level constants. Do not inline magic
  numbers into part files.
- Never delete or weaken a provenance comment. If a dimension changes, say where
  the new value came from in the same style.
- Where a dimension comes from vendor geometry, it is in `reference/` — that
  directory is a tracked input, not an export.
- Prefer reusable functions over duplicated geometry, and preserve the existing
  parametric relationships rather than substituting constants.
- A new dimension that is not in `reference/golden/parameters.json` has to be
  declared in `tools/gate_a.py` as an ADDED name with the reason for it.
  Otherwise gate A reports it as something the translation invented, which is
  exactly what that rule is for.

Avoid destructive rewrites unless they materially simplify the model, and
summarize dimensional or structural changes after each substantial edit.

Do not commit unless asked.
