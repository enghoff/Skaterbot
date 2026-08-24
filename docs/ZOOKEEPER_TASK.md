# Zookeeper task brief — build the knee actuator interface

**Status:** open, written 2026-08-24. This replaces the previous brief, which
asked for the actuator envelope to be verified and the support architecture to be
chosen. Both are now settled and the results are in [`NOTES.md`](NOTES.md); the
old brief is in git history if you want to see what it asked. Nothing in it is
still outstanding except the one item repeated under "What is still unknown"
below.

All paths below are relative to the repository root, not to this file.

---

Read [`AGENTS.md`](AGENTS.md) first — it is binding, and its frozen parameters,
mass budget, joint limits, duty limit and sourcing constraints all apply here.

Unlike the last brief, **this one is an implementation task.** You are being
asked to build geometry, not to investigate and report. The reason it is going to
you rather than being done outside Design Studio is simple: Design Studio here is
GUI-only with no headless command line, so an external agent can write KCL but
cannot execute it. You can. Everything below therefore ends in "and confirm it
builds", and a change that has not been regenerated is not finished.

## What is already settled — do not re-open these

The actuator interface has been read off the vendor STEP
(`reference/dm_3507_3d-241021.STEP`) and the vendor 2D print, cross-checked
against manual V1.0, and the numbers now live in `parameters.kcl` with their
provenance in comments. In summary:

- The part is **Ø46.0 × 37.9 mm** overall and **nothing protrudes** beyond it.
- **Output face:** 6 × M3 tapped 5 mm deep on a Ø24 bolt circle, inside a **Ø30
  boss raised 1 mm** above the surrounding face. The boss is a register — use it
  to locate the hub, do not ignore it. There is **no through-bore**.
- **Housing, same face:** 4 × M3 tapped 5 mm deep on Ø41.
- **Rear face:** 4 × M3 tapped **4 mm** deep on Ø41 at 45°, 135°, 225° and 315°,
  each behind a Ø3.20 clearance hole through the 3.20 mm rear cover. A screw
  therefore crosses 3.2 mm of cover before it reaches any thread.
- **Not for mounting:** 4 × M2.5 on Ø42 at 33.5°, 146.5°, 213.5° and 326.5°.
  Those hold the driver compartment shut. Leave them alone.
- **Connector flat:** one chord 19.0 mm from the axis, about 25.9 mm wide,
  subtending about 69° and centred between the 45° and 135° tapped holes, which
  clear its edges by roughly 11°. The connectors sit at the rear end against this
  flat and project rearward by an unmeasured amount.

The architecture that follows from this is also settled: **anchor the fixed link
to the rear face and run arms forward past the body to carry the far bearing.**
The alternatives were assessed and rejected — a front-face ring bearing fails on
load, and a plain bearing clamped on the Ø46 housing burns 23–43% of the 0.8 Nm
continuous rating in friction. The reasoning is in `NOTES.md` under "The three
schemes, assessed". Do not revisit the choice; build it.

## Why the existing yoke cannot be reused as drawn

`pitch_yoke.kcl` is a double-shear yoke whose two cheeks are Ø54/Ø46.6 annuli
3 mm thick, sitting at x = ±20.75 mm. Both bolt circles that could drive it are
**inside** Ø46, so an annulus bored to Ø46.6 has no material anywhere the
actuator actually attaches. It also assumes a spigot on the far face for the
second bearing, and there is none. The Ø22 × 5 mm `supportBearing` in that file
is a placeholder running on nothing.

## Work to do

### Step 1 — regenerate before you change anything

`parameters.kcl` gained the rear-face and connector-flat constants, and
`actuator.kcl` had a stale comment corrected, in the most recent commit. Neither
has been executed since.

Regenerate `main.kcl` and `pose_check.kcl` and confirm they still build clean and
still show what `NOTES.md` describes, in particular roughly 22 mm of swing-foot
clearance in the crouched pose. Report the result before proceeding. If something
is already broken, say so and stop — do not build on top of it.

### Step 2 — put the new module in its own file

Create **`knee_module.kcl`**. Do not modify `pitch_yoke.kcl`.

The reason matters: `main.kcl` and `pose_check.kcl` both import
`pitchYokeAssembly` and clone it seven times, so all eight joints share that one
part. Editing it would silently re-proportion the whole robot, which `AGENTS.md`
forbids. Build the knee as a separate part, wire it into `main.kcl` **at the knee
only**, and leave the other seven joints on the old yoke. That also makes the
before-and-after visible on screen in one view.

Export an **array**, as `pitch_yoke.kcl` does, so the consuming files keep
working.

### Step 3 — the driving hub

Replace the driven cheek with a disc that actually bolts to the output.

- Seat it on the **Ø30 boss**, with a counterbore about 1 mm deep and 0.2–0.4 mm
  of diametral clearance, so the boss carries the concentricity rather than the
  bolts.
- 6 × Ø3.4 clearance holes on Ø24 at 60°. Check M3 cap-head clearance: the heads
  are Ø5.5 and the arc spacing on Ø24 is 12.6 mm, so they fit, but confirm it
  against whatever counterbore or recess you add.
- The threads are 5 mm deep, so state the screw length you are designing for and
  make sure the hub thickness plus engagement is consistent with it.
- The hub also has to carry the inner member of the second bearing, so it needs a
  journal or stub projecting **forward, past the output face**. That axial
  projection is what buys the support span — see step 5.

### Step 4 — the rear-anchored bracket

- Bolt to the 4 × M3 on Ø41 at 45°, 135°, 225°, 315°.
- Screw length is bracket thickness + 3.2 mm of cover + engagement, with
  engagement not exceeding the 4 mm of available thread. State the length you
  choose. Do not let a plain shank bottom out before the thread engages.
- **Leave the 69° connector sector open.** A mated plug projects rearward by an
  amount nobody has measured, so the bracket must not close that sector off, and
  it must not need the connectors removed to be fitted or serviced.
- Arms run forward alongside the Ø46 body to the bearing seat. Keep them clear of
  Ø46 plus the existing 0.3 mm `actuatorClearance`.

### Step 5 — the second support, sized to the real load case

The point of the second bearing is to straddle the joint load with the actuator's
own internal output bearing. If the new bearing sits level with the output face
the two supports are nearly coincident and it achieves nothing, so the span is a
design output you have to report, not an afterthought.

- Design for **6 Nm static** at the joint, and separately check the **100 N at
  100 mm** landing case, which is what forces the long span. `NOTES.md` puts the
  reaction at roughly 300–350 N for a 40–50 mm span, against 1000–1350 N for the
  8–12 mm a front-face bearing would give.
- Report the span you achieved and the reaction that follows from it.
- Pick a real bearing, not a placeholder. Give the designation, the mass per
  joint and across eight joints, and whether it is a commodity part in India.
- Remember the duty limit in `AGENTS.md`: sustained loaded stance past roughly
  45° of knee flexion is outside the thermal envelope, so this has to be stiff in
  the near-straight poses the robot will actually hold, not just at full flexion.

### Step 6 — check it in the poses that matter

Regenerate both entrypoints. Confirm the knee module clears the thigh and shin
across the full **0° to 110°** knee range, that the mechanical stop at 110° is
still reachable, and that nothing new collides in the crouched pose check. Do not
widen a joint limit to make the design fit.

## What is still unknown, and how to handle it

Two things are genuinely open, and neither should stop you:

**How far a mated plug projects past the rear face.** Unmeasured, and it needs the
physical part or the connector's datasheet. Assume a generous keep-out, say what
you assumed, and make the bracket's rear plate easy to shorten later if the real
number is smaller.

**The output bearing's radial and moment rating.** DAMIAO does not publish it, and
it is the one number that could remove the need for the second support entirely.
Until they answer, the second support stays. Do not design as though the internal
bearing can take the moment.

## What to hand back

- What regenerated cleanly and what did not, per entrypoint.
- The mass delta of every new part, per joint and across all eight, against the
  40–80 g of headroom in `AGENTS.md`.
- The fastener list: size, length, count and engagement depth for the output hub
  and the rear bracket separately.
- The bearing designation, span achieved, resulting reaction, and sourcing.
- Any interference you found, and what you assumed for the connector keep-out.
- What is still open.

Update [`NOTES.md`](NOTES.md), [`CHECKLIST.md`](CHECKLIST.md) and
[`BOM.md`](BOM.md) with what you actually established.

One request about the report itself. The last handback contained a claim that
turned out to be false — that the yoke's clear span had gone from 49.5 mm to
38.5 mm and the cheeks had moved inward, when `pitch_yoke.kcl` had not been
touched since the baseline commit and the span had always been 38.5 mm. It came
from describing project history rather than the model. So: **report only what you
measured in the model you just built, and say where you read each number.** If
you did not measure it, do not state it. Corrections are cheap; a confident wrong
number costs a redesign.

Do not change any frozen parameter. Do not touch anything outside the knee.
