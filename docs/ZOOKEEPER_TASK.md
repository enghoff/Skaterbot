# Zookeeper task brief — knee support architecture

**Status:** steps 2 to 4 answered 2026-08-23 by analysis of the vendor STEP; the
results are in [`NOTES.md`](NOTES.md). **Step 1 is still open** — the KCL has
never been executed, because Design Studio here is GUI-only with no headless
command line. Anyone opening the project should still do step 1 and check the
findings on screen. It is a task brief, not standing guidance; standing guidance
lives in [`AGENTS.md`](AGENTS.md).

All paths below are relative to the repository root, not to this file.

---

Read `docs/AGENTS.md` first — it is binding, and its frozen parameters, mass
budget, duty limit and sourcing constraints all apply here.

This is an **investigation and verification** task. Do not redesign the knee, do
not modify the yoke, and do not pick the support architecture and build it. The
deliverable is a report that lets a human make that choice. Stop where the task
says to stop.

## Why you are being asked

Three things were established outside Design Studio, by reading the vendor STEP
and manual as text. None of it has been regenerated or seen on screen, and the
method has already produced one wrong answer that had to be corrected. Treat
every number below as a claim to check, not a fact to build on. If you find any
of it wrong, say so plainly and stop rather than working around it.

The relevant files: `reference/dm_3507_3d-241021.STEP` is the vendor model, with
provenance and known caveats in `reference/README.md`. The claims are recorded in
`docs/NOTES.md` under "Corrected actuator envelope" and "Yoke re-check against
the real interface".

## Step 1 — regenerate what has already changed

`actuator.kcl` was rewritten and `parameters.kcl` gained actuator interface
constants, both without ever being executed.

Regenerate `main.kcl` and `pose_check.kcl`. Report whether they build clean, and
whether the neutral assembly and the crouched pose check still show what
`docs/NOTES.md` describes — in particular the roughly 22 mm swing-foot clearance
and no self-collision. The actuator proxy is now a plain Ø46 × 37.9 mm cylinder
where it used to be 48.9 mm long overall, so joint spacing that previously looked
clear may have changed.

Do not fix anything you find here yet. Report it.

## Step 2 — verify the actuator envelope against the vendor model

Bring `reference/dm_3507_3d-241021.STEP` into the project and check it against
these claims. Note that its main body is exported as an open-shell surface model
rather than a solid, so it may not import as usable solid geometry — if that
blocks you, say so and fall back to measuring what you can.

Confirm or correct:

- Overall envelope Ø46.0 × 37.9 mm, with nothing protruding beyond it.
- Output-side face: 6 × M3 tapped 5 mm deep on a Ø24 mm bolt circle, inside a
  Ø30 mm register, with concentric bores around Ø8–10 mm.
- 4 × M3 on a Ø41 mm bolt circle at 90° spacing.
- Both bolt circles on the **same** face, at axial stations 0 and 1.0.
- Nothing usable on the opposite face except internal M2.5 fasteners on a Ø42 mm
  circle.

## Step 3 — settle the two unknowns that block the design

**Which face is the output.** The station-0 face carries the Ø24 six-hole pattern
with counterbores inside a Ø30 register and concentric Ø8–10 bores. That reads as
an output flange, but a stator mounting face with a rotor clearance bore would
look similar in geometry alone, and the text analysis could not separate them.
Determine which it is and give your evidence — concentricity with the rotor,
which features rotate, wall thickness, whatever actually distinguishes them. This
decides which link is fixed and which moves, so it gates everything downstream.

**The cable exit keep-out.** There is a radial cable exit about 31.7 mm from the
station-0 face. Its radial extent has never been measured and is deliberately
absent from the CAD. Give it as a keep-out volume: radial projection beyond
Ø46, angular position and width relative to the bolt patterns, and axial extent.
Say whether the connector body, the mating plug, or both are included.

## Step 4 — assess the support architecture, and stop

Both actuator interfaces are on one face, so the far side offers nothing to bolt
to or run a bearing on. The double-shear yoke currently in `pitch_yoke.kcl`
cannot work as drawn: its cheeks are Ø46.6 mm annuli that clear the body without
touching either bolt circle, and there is no rear spigot for the second bearing.

Assess these three candidate schemes against the real geometry:

1. A stub axle cantilevered from the fixed link, carrying a bearing in the
   moving link past the actuator's far end.
2. A large thin-section bearing running on a ring bolted to the Ø41 mm circle.
3. The moving link supported on the actuator's own Ø46 mm outside diameter
   through a clamped bearing ring.

For each, report the load path from ground reaction to the fixed link, whether it
physically fits given the cable exit you measured in step 3, the bearing family
it implies and whether that size is commodity in India, an estimated mass delta
against the 40–80 g of headroom in the budget, and its main failure mode in PETG.

Design for **6 Nm static** at the joint, and remember the duty limit in
`docs/AGENTS.md`: sustained loaded stance past roughly 45° of knee flexion is
outside the thermal envelope, so the support has to be stiff in the near-straight
poses the robot will actually hold.

Then recommend one, and **stop**. Do not implement it. If none of the three works,
say what fails and what minimum change would be needed — do not invent a fourth
and build it.

## What to hand back

A report covering: what regenerated and what did not, each claim in step 2
confirmed or corrected with the measured value, which face is the output and why,
the cable-exit keep-out, the three schemes assessed, your recommendation with its
reasoning, and what risk is left open.

Update `docs/NOTES.md` and `docs/CHECKLIST.md` with what you actually established.
Where you correct one of the claims above, say so explicitly rather than quietly
editing the number — the provenance of the error matters.

Do not change any frozen parameter. Do not touch anything outside the knee.
