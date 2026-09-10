# Migrating the CAD from KCL to build123d

**Status:** phases 0, 1 and 2 complete and green. **The KCL is deleted and the
CAD is build123d only.** Every printed piece, every check scene, every tool and
the whole simulation pipeline run off `cad/`, and all six gates pass. Phase 3 --
the improvements the migration was for -- has not started, apart from the rotor
arm's fillet. See section 0 for where it actually stands.
**Branch:** `migrate/build123d`, off `refactor/kcl-lib-split`.
**Estimated effort:** eight to twelve focused days, in the phases of section 5.

This document says what the migration would cost, what it would buy, how the
result would be proved equivalent to what exists today, and where to stop if it
turns out not to be worth it.

---

## 0. Where this actually stands

Phases 0, 1 and 2 are complete and the KCL is gone. Every component the wheeled
robot needs is ported, the seven check scenes are ported, the tools are rewritten
on build123d, the simulation reads its dimensions out of `cad/`, and every gate is
green. The walking robot was deleted from this branch earlier and lives on the
`walking` branch, still in KCL. A 0.5 mm chamfer has been put on the printed parts' outer edges.

**What went with the KCL, and what took its place.**

| Deleted | Replaced by |
|---|---|
| 24 `.kcl` files, including `lib/` and the seven check scenes | `cad/`, one flat Python package |
| the check scenes as things you look at | `cad/poses.py` and `cad/scenes.py`, measured by gate F |
| `simulation/kcl_params.py`, 220 lines of regex | `cad/dimensions.py`, 30 lines that import |
| `tools/views.py`, metered renders | `tools/view.py`, a local viewer -- and gates E and F, which measure what a render used to be asked to show |
| `tools/clear_cache.py`, Design Studio's caches | nothing; the app is not used |
| `tools/capture_golden.py`, the KCL parameter freeze | nothing; its output is frozen in `reference/golden/` |
| `project.toml`, the Design Studio project | nothing |

**One thing was lost rather than replaced: the rendered view sheet.** `/views`
produced a six-sided sheet of any model on the metered engine, and the golden
renders section 3 asked for were never captured, so there is no frozen visual
reference to diff against either. `tools/view.py` shows a model in a live viewer
and gates E and F measure what a render was previously asked to prove, which is
strictly better evidence -- but there is no longer a way to produce a PNG of the
robot without a viewer open.

| Gate | What it checks | Result |
|---|---|---|
| A | every ported dimension against the frozen KCL values | 192 live names, **0 differing**; 19 retired, correctly absent; 1 added with a reason |
| B | each piece's solid against its golden STEP, by symmetric difference | **8/8 pieces**, 7 at 0.0000 mm3 and 1 deliberately changed |
| C | the mass roll-up, part by part, against the baseline | 1 606.6 g, 693.4 g under, **all four parts ok** |
| D | the joint tree against the pose scenes, via `check_model.py` | **both scenes, within 1e-6 mm** |
| E | holes and pockets, counted on the finished solid | **pass** |
| F | the check scenes' poses and clearances | **71 checks, all pass** |

Gate F is new, and it is the second half of porting the check scenes. It pins
every one of the 51 constants those scenes computed against
`reference/golden/scenes.json` -- captured from the KCL before it was deleted, and
matching bit for bit -- and then measures the twelve clearances the scenes were
drawn to show, where each wheel lands, and whether the four payload volumes fit
inside the pelvis.

**It also keeps gate D honest.** Gate D used to compare a tree built from the
port against a pose computed by the KCL, which made it an independent check by
construction. Both halves are Python now, so the independence comes from gate F's
frozen reference instead: the tree is built from `cad/parameters.py`, the pose is
computed in `cad/poses.py`, and both are held against figures neither had a hand
in.

`cad/` now holds the whole wheeled robot: parameters, joint, hardware, limb,
thigh, shin, wheel adapter, skate wheel, wheel, torso shell, torso, electronics,
actuator, the assembly, the check scenes and the finishing pass. `/check` builds
all twenty modules, six printed pieces and seven scenes in about five seconds.

**The migration cost one metered run in total**, the golden capture of section 3,
and nothing since. The project now spends no API credits at all.

### What phase 2 changed in the tools

`/check` builds every part and scene and then runs `ruff` against `ruff.toml`,
which is new: the CAD is Python now, so lint and format are part of checking it.
`/mass` measures locally in about a second, and gate C is one flag on it rather
than a second implementation of the same table. `/step` writes a STEP or an STL
per piece with no wrapper scenes and no `hide` dance, and re-reads each file to
check its body count. `/gates` is a new command that runs all six.

Three things in `tools/mass_budget.toml` moved with the tools. Its `file` keys
name Python modules instead of KCL files; the `hide` lists are gone, because
calling one function builds one piece; and each `[[printed]]` entry gained a
`measure` list, because the engine weighed whatever solids a KCL file left
standing and a Python module leaves none. `tools/mass_baseline.json` was rekeyed
the same way, with a note recording that the figures are still the engine's and
were not recomputed.

### The walking robot is gone from this branch

`foot.kcl`, `walking_main.kcl`, `walking_torso.kcl`, `walking_hip_carrier.kcl`,
`lib/hip_carrier.kcl`, `payload_envelopes.kcl` and the three walking check scenes
are deleted, and the foot dimensions, the ankle-derived axis chain and the
walking torso are retired out of `lib/parameters.kcl` and `cad/parameters.py`
with a note in the house style saying what they decided and where that decision
went. The branch question in section 7 is answered: this branch is wheeled-only,
the walking robot lives on the `walking` branch, and the two are no longer
comparable.

Nothing carries hip roll any more. It left the wheeled robot in `58e1869`, and
the walking robot was the last thing holding roll clevises and a carrier. Both
assemblies build exactly six actuators.

`tools/gate_a.py` learned two ideas in the process. **RETIRED** names are golden
dimensions this branch deliberately dropped; the gate asserts they stay ABSENT,
so the walking robot cannot creep back in unnoticed. **ADDED** names are
dimensions introduced after the port, each listed with the change it belongs to,
which is what lets the EXTRA rule keep meaning "the translation invented
something". The first ADDED entry is the chamfer.

### The chamfer

0.5 mm on outer edges only, in `cad/finish.py`, applied on top of the faithful
parts rather than inside them so that gate B still means what it meant. An edge
is chamfered when every face meeting it is flat or a CONVEX cylinder, so bores,
seats, registers, counterbores and the Ø22 spigot are untouched and no fit moves.
Convex or concave is measured from the face normal against the radial direction,
not guessed.

`uv run tools/finish_report.py` is the measurement:

| piece | edges cut | left sharp | delta |
|---|---|---|---|
| limb, each hand | 39 | 0 | −0.160 g |
| wheel adapter, each hand | 18 | 0 | −0.056 g |
| pelvis shell | 241 | 59 | −0.313 g |
| torso cover | 24 | 0 | −0.104 g |

**Three things this cost, and they are worth recording.**

OCCT will not chamfer a crowded solid's edges in one pass. It refuses all 61 of
the rotor hub's at 0.5 mm and refuses them just as firmly at 0.05 mm, while
chamfering any one of them alone without complaint. It is the interaction, not
the size and not any individual edge.

So the set is bisected, and edges have to be re-found on each new solid. Not by
position -- a chamfer shortens its neighbours and moves their midpoints -- but by
the PAIR OF FACES an edge lies between, because cutting a chamfer somewhere on a
plane makes that plane's face smaller without moving the plane.

And a body chamfered that way **segfaults OCCT in any subsequent boolean**, even
a union with a body it does not touch. It reports itself valid; `clean()` and
`fix()` do not help; no try/except can catch it. That is why the finished pieces
are left as the interpenetrating bodies they already were rather than unioned --
which is the form the project already ships and a slicer already merges, so
nothing is lost, but it does mean **phase 3's "union the pieces for real" cannot
be combined with the chamfer** on this OCP build.

The 59 sharp arrises on the pelvis are almost all in its two hip clevises, where
two Ø52 discs, a neck and a hollow saddle meet within a few millimetres.

### Two things the gates found earlier

**The rotor arm's stress-relief fillet is not the 1 mm radius its parameter
names.** The KCL sketch constrained only how far the blend reaches and left the
arc's centre unconstrained, so the solver kept its initial guess's offset while
shrinking the chord. What it built is a shallow arc of radius sqrt(8.5) = 2.9155
mm, leaving nearly double the material a true 1 mm quarter-round would. It is
reproduced exactly so gate B means something, and flagged for phase 3.

**A twice-mirrored solid comes back inverted and measures zero.** The limb's rear
gusset was mirrored, then the whole limb mirrored again for the opposite hand.
The result had the right bounding box, took part in every boolean correctly, and
reported a volume of zero. Gate B never saw it because a union re-orients what it
swallows; gate C caught it because it adds the bodies up. `cad/geometry.py`
carries the fix and gate C now refuses any body measuring zero.

---

## 1. Why this is worth considering

The project pays three recurring taxes to KCL and the Zoo engine, and all three
are structural rather than incidental.

**Geometry the engine refuses.** [`KCL_GOTCHAS.md`](KCL_GOTCHAS.md), under
"Geometry the engine refuses", is a list of ten things OCCT does without
complaint: blind pockets, blind cylindrical pockets, holes that stop inside
material, pockets cut into an already-hollowed shell, unions whose bodies share
two faces, cutters tangent to two faces of a block, and unions of hollow boxes
meeting at right angles. The design has been bent around every one of them. Most
consequentially, **the hip carrier, the torso hip mounts and the foot frame are
left as interpenetrating bodies** because the engine will not union them, which
is why an exported STL is not manufacturing-ready without checking it in the
slicer, and why `/mass` double-counts those overlaps. The pelvis shell exports
as seven bodies where it is one part; a limb as five.

**Verification that costs money.** Three of the six commands -- `/mass`,
`/views`, `/step` -- run on the metered engine. Under build123d, volume, mass and
STEP export are local OCCT calls that return in milliseconds, so the whole
"mock-execute while iterating, spend the engine only when geometry has to be
correct" discipline collapses into just running the file. That changes how often
the robot gets measured, which is the real benefit rather than the credits.

**No way to prove a feature exists.** The rule in `CLAUDE.md` that a boolean
which succeeds is not a boolean that worked exists because the rotor hub carried
four filled bolt holes through several rebuilds, on the joint that takes the
actuator's full torque, and nothing reported it. The only available evidence was
looking at a render down the feature's axis. In build123d the finished solid is
an object in memory whose faces can be counted, so "this part has six M3
through-holes on the Ø24 output circle" becomes an assertion that runs free on
every build. Gate E in section 4 is that idea written down.

Against those: the geometry vocabulary in use is narrow enough that this is a
translation and not a redesign. Across about 6,200 lines in 34 files there are 83
extrudes, 34 subtracts, 29 unions, two revolves and four sweeps -- and no fillet
or chamfer operations, no patterns, no lofts and no helices at all. Every one of
those maps onto core build123d. Much of the bulk is constraint-solver
boilerplate: a plain rectangle costs about twenty lines of `sketch` with
`coincident` / `horizontal` / `horizontalDistance` constraints plus a `region()`
call, and becomes `Box(w, h, d)`. Expect the geometry files to come out three to
four times shorter.

### What is given up

Design Studio as a viewer. The replacement is `ocp_vscode` in the editor, which
renders a model and lets you spin it but is not as pleasant for wandering around
an assembly. And the sketch constraint solver, which this project uses only to
restate dimensions it already holds in named variables -- `diameter(cheekCircle)
== cheekDiameter` is a `Circle(cheekDiameter / 2)`, and nothing is lost.

---

## 2. Scope, and the two-phase rule

**The migration is a faithful translation. It changes no geometry.**

This is the most important constraint in the plan, and it is what makes section 4
possible. Every gate below works by requiring the new part to be *identical* to
the old one. The improvements the migration unlocks -- real unions for the hip
carrier and the foot frame, true fillets in place of arcs drawn into profiles,
blind pockets, holes that stop inside material -- all deliberately change the
geometry, and would fail those gates.

So they are **phase 3**, after the translation has landed with every gate green,
and each is a separate change with its own measured mass delta. Then a surprise
in the numbers is attributable to exactly one edit rather than to a
six-thousand-line rewrite.

Not in scope at all: any change to the robot's design, its dimensions, its mass
budget, or the simulation's physics. `simulation/` is rewired to a new source of
numbers and otherwise untouched.

---

## 3. Capture the golden reference first

Everything in section 4 compares against artefacts that only the current KCL can
produce. **They must be captured before any KCL file is edited or deleted**, and
capturing them is the last metered work the project ever does.

| Artefact | How | Cost | Where it lands |
|---|---|---|---|
| One STEP per printed piece, six pieces | `uv run tools/export.py` | metered, six executions | `reference/golden/step/`, tracked |
| Per-part volume and mass at PA12-CF density | `uv run tools/mass.py --save-baseline` | metered, four executions | `tools/mass_baseline.json` |
| Every named dimension, to full precision | `simulation/kcl_params.py`, dumped to JSON | free | `reference/golden/parameters.json`, tracked |
| A render sheet per part and per check scene | `uv run tools/views.py` | metered | `reference/golden/renders/`, tracked |

Three notes on that table.

`exports/` is untracked today because it is regenerated output. The golden STEPs
are the opposite -- they are a **tracked input**, the frozen record of what the
Zoo engine actually built, in the same sense that the vendor actuator STEP in
`reference/` is a tracked input. They belong under `reference/golden/` and stay
there after the migration as the provenance of the geometry.

**`tools/mass_baseline.json` is stale and must be re-captured.** It currently
lists `lib/hip_carrier.kcl` and `foot.kcl` among the printed parts, neither of
which the six-motor wheeled robot prints. Comparing against it as it stands would
be meaningless.

The walking robot needs the same capture if it is ever to be migrated too. It
never had one, and the `walking` branch is where it would have to be taken. `foot.kcl`, `walking_torso.kcl` and `lib/hip_carrier.kcl` have no golden
STEP on this branch, because the wheeled robot does not print them. See
section 7.

---

## 4. The gates

Five gates, ordered by cost. A task is not done until its gates are green.
Everything here except the capture in section 3 is free and local.

### Gate A -- every parameter, to full precision

Compare the new Python parameter module against `reference/golden/parameters.json`
name by name, as floats, with zero tolerance.

This covers the largest single error class -- a mistyped dimension -- almost
completely, and it costs nothing.
[`simulation/kcl_params.py`](../simulation/kcl_params.py) already reads the KCL
half, so it serves as the oracle for the length of the migration and is deleted
at the end of it, along with the 220 lines of regex that exist only because the
parameters live in KCL.

A name present in one and missing from the other is a failure, not a warning.
Silently dropping a parameter is exactly the failure this gate is for.

### Gate B -- solid identity, per part

For each of the six printed pieces: import the golden STEP, build the new part,
and compute the **symmetric difference** -- the volume of `new - old` plus the
volume of `old - new`. Require it below the tolerance floor established in task
0.3, as a fraction of the part's own volume.

This is the load-bearing gate. It is strictly stronger than comparing volumes,
which happily passes a part that is mirrored, translated, or has a hole in the
wrong place. Bounding box and centre of mass are computed alongside it -- not as
the gate, but as the diagnostic that says *how* a part differs when the
difference is not zero.

Two things to get right:

- **Calibrate the tolerance floor empirically before trusting it.** Difference a
  golden STEP against itself, re-imported, to find what OCCT's own numerical
  noise costs on this geometry. Judge real mismatches against that number rather
  than against a guess.
- **Compare against the union of the exported shells, not their sum.** The KCL
  pieces export as several interpenetrating bodies -- five for a limb, three for a
  wheel adapter, seven for the pelvis shell, one for the cover. Phase 1 builds
  the same interpenetrating bodies, so the comparison is like for like, but the
  measured volume of a union is about **19 g lighter across the robot** than the
  sum of the shells. `simulation/` already resolves this and is the reference for
  how.

### Gate C -- the mass roll-up

The `/mass` equivalent under build123d, compared to the re-captured baseline
**part by part**, not on the total. A total can come out right by cancellation
between two parts that are both wrong.

Phase 1 target: every part within the gate-B tolerance of its baseline, and the
robot still under its 2,300 g ceiling.

### Gate D -- the kinematics, unchanged

Regenerate the URDF from build123d and run
[`simulation/check_model.py`](../simulation/check_model.py) with no edits to it
at all.

This is already the best test in the project and it survives the migration
untouched. It drives the tree to the exact angles in `pose_check.kcl` and
`squat_check.kcl` and requires the wheel to land within `TOLERANCE_MM = 1e-6` of
where those scenes independently compute it, which exercises every link length,
joint origin and axis sign at once. Require the same pass, at the same tolerance,
printing the same numbers.

### Gate E -- feature assertions, which are new

For each part, assert that the features which must exist do exist, by counting
them on the finished solid rather than by looking at a picture: six cylindrical
faces at the output bolt radius on the Ø24 circle, four at the rear bolt radius
on Ø41, the bearing bore at its diameter, and so on for every hole and pocket
that lives where two bodies overlap.

These have no KCL counterpart -- they are what the migration buys -- so they
cannot be validated against the golden reference. They are written *against the
drawing intent*, and they are the permanent replacement for the
render-down-the-axis rule. Where one of them fails on a part that passes gate B,
**the KCL was wrong and the finding stands on its own**: record it, and fix it in
phase 3 rather than in phase 1.

### The visual backstop

Keep a render sheet per part and diff it by eye against
`reference/golden/renders/`. It is the weakest gate here and must not be
load-bearing -- once gate B is green it adds very little -- but it costs a minute
and it catches a class of gross error that would be embarrassing to ship.

---

## 5. Task breakdown

### Phase 0 -- prove the ground, before committing (1 day) -- **done**

| # | Task | Done when |
|---|---|---|
| 0.1 | Confirm `build123d` and its OCP wheels install under `uv` on Windows 11, and pin the Python version in the script metadata | a script imports `build123d` and builds a `Box` |
| 0.2 | Capture the golden reference of section 3 | all four artefacts committed under `reference/golden/` and `tools/` |
| 0.3 | Establish the gate-B tolerance floor by differencing a golden STEP against itself re-imported | a number, written into the gate-B check |
| 0.4 | Port `lib/parameters.kcl` and `lib/joint.kcl` only; build `statorClevis` and `rotorHub`; run gates A and B against them | both pass, or the migration is abandoned here |

**Task 0.4 is the decision point.** `lib/joint.kcl` is the hardest file in the
project -- 736 lines, the joint interface used at every joint, and the part that
carries most of the constructions the engine forced. If it ports cleanly and
matches, the rest of the estimate holds. If it does not, one day has been spent
instead of ten. Do not proceed past phase 0 without gates A and B green on the
clevis and the hub.

### Phase 1 -- the translation (5 to 8 days) -- **done**

Ordered so that nothing is built before what it depends on. Each task's gates
must be green before the next begins.

| # | Task | Source | Gates |
|---|---|---|---|
| 1.1 | Parameters, and the derived stack heights | `lib/parameters.kcl` (410), `lib/wheeled_parameters.kcl` (171) | A |
| 1.2 | The joint interface | `lib/joint.kcl` (736) | A, then B via 1.5, E |
| 1.3 | Hardware, limb, torso shell, hip carrier, skate wheel | `lib/hardware.kcl` (263), `lib/limb.kcl` (196), `lib/torso_shell.kcl` (218), `lib/hip_carrier.kcl` (129), `lib/skate_wheel.kcl` (118) | A |
| 1.4 | Bought-part proxies | `actuator.kcl` (41), `wheel.kcl` (88) | volume only; not printed |
| 1.5 | Printed parts: thigh, shin, wheel adapter | `thigh.kcl`, `shin.kcl`, `wheel_adapter.kcl` | B, C, E |
| 1.6 | Printed parts: the pelvis | `torso.kcl` (383) | B, C, E |
| 1.7 | Payload envelopes and the electronics stack | `wheeled_electronics.kcl` (479), `payload_envelopes.kcl` (203) | A; envelopes, not printed |
| 1.8 | The neutral assembly | `main.kcl` (132) | C, plus the 339 mm standing height |
| 1.9 | Check scenes -- **done**, as `cad/poses.py` and `cad/scenes.py` | the seven check scenes | A and F |
| 1.10 | The walking robot -- **not done, and not going to be**: it stays in KCL on the `walking` branch, and this work deleted it here | | |

**Task 1.9 is where the check scenes got better, and this is how it went.** They
were scenes you looked at; a clearance is a number now. The knee at its 110° stop
clears by 37.900 mm, the folded wheel clears its own thigh by 39.882 mm in the
squat -- the tightest of the two poses, as the scene always claimed -- and the
torso floor clears a thigh swung 35° forward by exactly 1.000 mm. All of it is in
`tools/gate_f.py`.

Two departures from the plan as written. There were no golden renders to prove
the ported scenes against, because that capture never happened, so the scenes
were pinned to their computed CONSTANTS instead, which is stronger: 51 numbers at
zero tolerance rather than a picture compared by eye. And three of the seven
scenes -- the packing check, the limb review and the wheel module -- compute no
constants at all, so for those the assertion is entirely about measured
clearances.

The two `hide()` calls those scenes carried are simply gone. They existed because
importing a KCL module ran it, so the wheel module review had to import the left
wheel purely to hide it; calling a function builds only what you asked for.

### Phase 2 -- the tooling (2 days) -- **done**

| # | Task | Replaces | Note |
|---|---|---|---|
| 2.1 | `/check` | `tools/check.py` (164) | Running the module is the check. Add `ruff` for lint and format, which the repo already uses |
| 2.2 | `/mass` | `tools/mass.py` (170) | `part.volume × density`, local. `mass_budget.toml` is unchanged: it is the register of what is printed and what is bought, and none of that is KCL-specific |
| 2.3 | `/step` | `tools/export.py` (336) | `export_step()`. The generated wrapper scene and the `hide` dance disappear entirely -- a piece is a Python object, and you export it |
| 2.4 | `/views` | `tools/views.py` (134) | Headless OCCT screenshots, or `ocp_vscode`. Keep the robot-frame view names: **+Y forward, +Z up, +X the robot's right** |
| 2.5 | `/cache` | `tools/clear_cache.py` (333) | Deleted along with Design Studio |
| 2.6 | `/urdf` | `simulation/build_urdf.py` | Import the parameters directly, and delete `simulation/kcl_params.py` (220) |

The `bodies` counts in `mass_budget.toml` stay meaningful through phase 1, and
then become the record of what phase 3 unions away.

### Phase 3 -- the improvements, one at a time (open-ended)

Each is a separate commit with a measured mass delta, and each **intentionally
breaks gate B** against the golden reference, which is the point. Re-baseline
after each.

- Union the pelvis shell's seven bodies into one solid. The hip mounts are the
  case the engine refused outright.
- Union the limb's five bodies and the wheel adapter's three.
- Union the foot frame, on the walking robot.
- Replace the hand-drawn fillet arcs with real fillets, starting with the rotor
  arm and bridge corner that `fillet_study.kcl` was written to explore.
- Import the vendor DM-J3507 STEP from `reference/` directly as the actuator
  proxy, instead of approximating it.
- Revisit the cable ports, which are rectangular slots only because blind
  cylindrical pockets were refused.

Once the unions land, `/mass` stops double-counting the overlaps and the robot's
measured mass falls by roughly 19 g. **That is a measurement artefact, not a
saving**, and it must be reported as such against the ceiling.

### Phase 4 -- the documents (1 day)

`KCL_GOTCHAS.md` becomes a historical record rather than a working reference, and
should be retitled and headed as such rather than deleted -- it explains why
several parts are shaped the way they are, and phase 3 needs it. `CLAUDE.md`,
`README.md`, `docs/AGENTS.md` and `simulation/README.md` all describe the KCL
workflow and the metered-versus-free split, and all need rewriting.
`docs/NOTES.md` is a log and stays as it is.

---

## 6. What does not change

`mass_budget.toml`, and the whole idea behind it: the ceiling, the material, the
bought-item allowances, the provenance notes. `simulation/check_model.py`,
`inertia.py`, `plant.py`, `robot.py`, and everything under `isaacsim/` and
`isaaclab/`. The URDF's do-not-edit banner, and the rule that the simulation is
downstream of the CAD and never beside it. The two frame conversions -- the CAD's
+Y-forward against a URDF's +X-forward, and the union-versus-sum mass bias --
which each stay handled in exactly one place.

The rule that dimensions live in one file with their provenance in the comments
survives verbatim; the file merely becomes Python. **Provenance comments transfer
word for word.** They are the most valuable thing in `lib/parameters.kcl` and the
easiest thing to lose in a rewrite.

---

## 7. Risks

**Silent dimensional drift.** The mass ceiling and the URDF's joint origins both
rest on the geometry being right, and a translation error does not announce
itself. Bought down by gates A, B and D, which between them cover the named
dimensions, the solid shape, and the kinematic chain.

**The branch structure.** `main` carries the walking robot as its `main.kcl`;
this branch carries the wheeled one. The two are compared and merged, and
`mass_budget.toml` uses the branch itself as the variant mechanism. **Migrating
one branch alone ends that permanently.** Either both robots move together --
which is why task 1.10 exists, and why section 3 asks for a golden capture on
`main` -- or the walking variant is formally retired first. This is a decision to
take before phase 0, not during phase 1.

**Windows and OCP.** build123d depends on OCP, a large binary wheel. Task 0.1
exists because the whole plan rests on it installing cleanly under `uv` on this
machine, and that has not been tried.

**Losing the interactive viewer mid-migration.** ~~Design Studio still opens the
KCL while phase 1 runs~~ -- settled: the KCL was kept until every gate was green
and then deleted, and `tools/view.py` with `ocp_vscode` is the viewer. What was
not replaced is the metered render sheet; see section 0.

**Effort overrun.** Bought down by the phase-0 decision point. `lib/joint.kcl` is
the hardest file, and it is ported first on purpose, for one day's cost.

---

## 8. Kill criteria

Stop, and keep the KCL, if any of these hold:

- Task 0.1 cannot get build123d installed and running under `uv` on Windows.
- Task 0.4 cannot make gates A and B green on the stator clevis and the rotor hub
  within a day, or can only do so by changing the geometry.
- The gate-B tolerance floor from task 0.3 comes out so loose that a real
  mismatch could hide underneath it.
- The walking robot's future is undecided, and the branch question in section 7
  has no answer.
