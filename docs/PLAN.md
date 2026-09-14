# Shell-Structure Overhaul Plan

**Status: active. Phases 2, 3, 4 and 5 are complete, and the Phase 7 poses and
torque models are done. The robot carries its own 6S battery again — see
Phase 5b, which reverses Phase 5a — and stands 360 mm rather than 339.
Phase 1 is drawn but waits on a printer, about a week out. What remains is hard
stops, a simultaneous-extremes pose, cable routing, and ribbing. See section 11
for what has been made. This supersedes `CHECKLIST.md`,** which stays in the repository
as the record of the skeleton design and of what was learned building it. Every
item still open there has been carried into this document or explicitly retired
in section 9.

---

## 1. What is changing, and why

The robot is being rebuilt from a **skeleton** into a **stressed-shell** machine.

Today the load path runs through two 8 × 8 mm carbon tubes per limb, held in
printed sockets, with the actuators gripped from outside by open yokes. The
target is the arrangement the BIMO robot reads as: closed printed limb shells
that carry the load themselves, with the actuator discs left **exposed at the
joints so they can still cool**. Nothing else on the robot is left visible.

This is not a styling change. The section numbers say the current architecture
is weak in exactly the direction a walking leg is loaded:

| Section | Area | I, sagittal | I, lateral | Mass per 105 mm link |
|---|---:|---:|---:|---:|
| Two 8 × 8 × 1 tubes at ±9 mm | 56 mm² | **467 mm⁴** | 5 003 mm⁴ | 33.1 g (spans only 63 mm) |
| Closed box, 32 × 24, 2 mm wall | 208 mm² | **18 197 mm⁴** (39×) | 28 949 mm⁴ (5.8×) | 27.7 g |
| Closed box, 40 × 28, 2 mm wall | 256 mm² | 31 701 mm⁴ (68×) | 56 021 mm⁴ (11×) | 34.1 g |

Both tubes sit on the centre line, so they contribute nothing to each other's
fore-aft stiffness. The pair is stiff side-to-side and floppy in the sagittal
plane, which is backwards for a leg. A plain closed box of the same outside size
is **39 times stiffer where it matters, spans the full 105 mm bay instead of
63 mm, and still weighs less** than the tube-and-socket module it replaces —
before counting the 8.2 g of fasteners per link that also disappear.

Add ribs, bosses and a clamshell flange and a real shell will land nearer
35–45 g rather than 27.7 g. It is still the better structure by a wide margin.

---

## 2. Architecture, stated once

- Each limb is **one closed shell** running joint centre to joint centre, with
  the joint interface built into the shell ends rather than bolted on.
- **Carbon tubes are removed entirely.** Carrying both a tube and a shell means
  paying for the structure twice; that was the mistake the current model was
  drifting into.
- The **actuator stays outside the shell**, clamped at the joint, free to
  radiate. Joints are visible; limbs are not.
- **Metal goes where printed plastic is untrustworthy**: bearing seats, the
  journal, and any threaded interface that gets taken apart more than once.
- Every printed part is a shell, a rib, or a boss. **No solid blocks.**

---

## 3. What survives the overhaul

Keep, unchanged:

- **All of `parameters.kcl`'s actuator provenance.** The Ø46 × 37.9 envelope,
  the 6 × M3 on Ø24 output circle, the Ø30 register, the 4 × M3 on Ø41 housing
  and rear patterns, the 3.2 mm rear cover, and the 69° connector flat. This is
  the hardest-won data in the project and none of it is affected.
- **The kinematics.** 380 mm overall, 96 mm hip spacing, 105 mm thigh and shin,
  ankle axis at 36 mm, knee at 141 mm, hip pitch at 246 mm, hip roll at 301 mm.
  The ankle was at 44 mm until the actuator was seated down onto the foot in
  August 2026; the links and the overall height are unchanged, and the 8 mm came
  out of the leg stack and went into the hip carrier's offset, which grew from
  47 mm to 55 mm.
- **The static torque envelope and duty analysis** in `NOTES.md`, including the
  finding that the 0.8 Nm continuous rating is crossed near 47° of knee flexion.
- **The knee interface logic** in `knee_module.kcl`: drive from the Ø24 output
  circle, anchor from the rear Ø41 pattern, take the far support on a 6800-2RS
  over a Ø10 journal, and stop the joint at 110° on a pad. The *interface* is
  right; only its packaging changes, from a bracket into a shell end.
- **The four-model regression habit.** Neutral, crouched pose, knee at 100° and
  knee at 110°. Any change reaches all four.
- The foot's footprint and sensor layout: 115 × 65 mm, four corner seats.

Retire:

- `pitch_yoke.kcl` — already recorded as structurally invalid because its
  annular cheeks contain neither of the actuator's real bolt circles, and
  meaningless in a shell design. **Deleted.**
- `tube_link.kcl` — the bonded-and-bolted tube joint built on 2026-08-28 goes
  with the tubes. It solved a real problem correctly for the architecture it was
  built in; that architecture is being replaced. **Deleted**, along with
  `knee_module.kcl` and `limb_mass.kcl`.
- `thigh.kcl` and `shin.kcl` were expected to go too, but survived: they are now
  three lines each, naming a length and calling the shared `limbAssembly()`.
  Keeping them means the models still read as thigh and shin rather than as two
  anonymous limb lengths, at no cost.
- `hip_carrier.kcl` was to be absorbed into the pelvis shell. It has not been,
  and cannot be until Phase 5 rebuilds the pelvis: it is still its own file,
  because the hip roll axis is the only joint that is not across the robot and
  the quarter-turn belongs somewhere.

---

## 4. Decisions taken

All four were settled on 28 August 2026 and the CAD is built on them.

1. **Material: SLS PA12**, laser-sintered, sent out. *Amended 13 September 2026;
   it was PA12-CF on an FDM machine, and the reasoning for that is kept below
   because it was right for what it was deciding.* PETG stays only for fit
   mock-ups.

   **What decided it was the layer axis, not the material.** Every strength
   figure this project has argued with comes in two: PA12-CF gives about 75 MPa
   in the print plane and about 30 across the layers, and the whole of the limb
   analysis has been arithmetic against that pair -- which way to lay a part on
   the bed is worth 2.5x on it, the thigh could not be laid flat at all once its
   knee clevis existed, and an integral journal was ruled out at 1.3 to 1.7 times
   its load because its root would have been a stack of layer lines in tension.
   SLS has no weak axis: about **48 MPa in every direction**. That is worse than
   75 and far better than 30, and it is the second number that has been deciding
   things.

   **What it bought, all of it measured.** The journal stopped being a bought
   part -- see decision 10 -- which deletes four dowels, four bonded joints and
   29.6 g of steel. Print orientation stops being a design input, which retires
   the open question the thigh's clevis had just created. And the parts got
   lighter for no change of shape: **0.93 g/cm3** against PA12-CF's 1.06, which
   is 57 g off the printed structure on its own. Together the robot went from
   2 149.7 g to **2 073.8 g**, and headroom under the 2 300 ceiling from 150 to
   **226**.

   **What it costs.** Parts are sent out, so there is a per-part cost and a
   turnaround where there was a spool and an afternoon. Sections designed against
   75 MPa in the print plane are now designed against 48, which no one has been
   back through -- the limb's worst section was held at seven times its load with
   ample room, but that sweep is open work. The 2.4 mm wall came from four
   perimeters of a 0.6 mm nozzle and now means nothing; it is a thickness SLS can
   hold comfortably, but it is no longer *derived*. And **0.93 g/cm3 is the
   bureau's number, not ours** -- sintered PA12 runs 0.90 to 0.95 depending on
   powder packing and refresh rate, which is about 5 g across the printed
   structure.

   The retired reasoning, kept because it is still the case: PA12 was chosen over
   PA6 for moisture stability -- PA6 takes up several times as much water, and
   this robot will not live in a dry box. PA6-CF was the acceptable FDM
   substitute if supply was difficult.
2. **No clamshell split.** The earlier recommendation was wrong and has been
   dropped. A sagittal split puts the seam down the middle of the most-loaded
   faces, and a frontal split cuts every bearing bore in half. The limb is
   instead printed as one closed shell with the joint ends integral, and the one
   part that has to come off for assembly -- the far bearing seat -- is a
   separate metal carrier bonded into the cheek. That gives no structural seam
   at all and no split bore.
3. **Eight actuators at eight joints**, unchanged.
4. **Mass ceiling 2.3 kg**, accepting a sustained-load knee limit near 40°. See
   section 8 for why those are the same decision.

Two decisions were added that the plan had not anticipated:

5. ~~**Both legs are identical rather than mirrored.**~~ **Reversed on
   29 August 2026 -- see decision 9.** It was the right call while the only
   asymmetry was which side of an actuator a hub sat on. It stopped being right
   when the limbs became flat plates that stand 25 mm off to one side.
6. ~~**The robot is tethered and carries no battery.**~~ **Reversed on
   11 September 2026 -- see Phase 5b.** It was right on the mass alone: 190 g
   against a ceiling with 5 g left in it. Deleting hip roll gave back 700 g and
   took that argument away, and the packaging argument turned out to be about
   pack SHAPE rather than pack existence -- no 6S brick fits across this torso,
   but two 3S bricks in series, stood on edge, do. The robot carries 48.8 Wh for
   288 g, the umbilical is deleted along with the boom nobody had designed, and
   the mass budget below assumes the pack.
7. **A limb is a flat plate, and the knee actuator is turned round to allow
   it.** This went in two steps. First the shell was shifted outboard so its
   outer wall lay in the output plane, which deleted the arm and the bridge.
   Then the shell went too: with the knee actuator reversed, the thigh meets the
   hip pitch rotor and the knee's rear cover on the same side, and the shin
   meets the knee rotor and the ankle's rear cover on the other, so each limb is
   a Ø52 disc, a Ø36 disc and a channel waist lying in one plane. Every
   attachment is the confirmed Ø24 output circle or the confirmed Ø41 rear
   pattern; the unprovenanced front-housing pattern is not used. A limb is
   **32.1 g** against 48.3 g before this month's joint work. The knee fold limit
   stops being structural as well, since thigh and shin now lie in different
   planes and cannot touch. *That last sentence stopped being true with decision
   10: the knee's clevis puts them back in one plane, and the fold now runs out
   at 103.0°.*
8. **No joint is straddled, and the knee and ankle have no far bearing at
   all.** *Half reversed by decision 10: the knee is straddled again, with the
   hip's own clevis.* A forked rotor was drawn, fitted, and removed on the evidence that the
   printed part fails long before the bearing does: the plate breaks at 21-53 N
   of sideways load at the foot depending on print orientation, and at that load
   the 6800 is under a third of its static rating. The flat limb then removed
   the clevis as well, so only the hip roll and the hip pitch are straddled and
   the bearing count is four rather than eight.

   **This rests on an unanswered question and is proceeding anyway.** With
   nothing reaching around the actuator, its own output bearing takes the joint
   moment -- 0.45 Nm standing on one foot, about 1.35 Nm landing at three times
   body weight, because the plate sits 22 mm off the axis. DAMIAO have not
   confirmed it. The decision was to build on the assumption and send them those
   two numbers rather than keep waiting. `rotorYoke` and `rearJointHardware`
   stay drawn, with nothing importing them, in case the answer is unfavourable.
9. **The two legs are mirrored, and the robot is symmetric about its midline.**
   This reverses decision 5. A flat limb stands 25 mm off to one side, so two
   identical legs would put the thigh outboard on one and inboard on the other.
   The cost is smaller than decision 5 feared: both leg segments are 105 mm, so
   the right thigh and the left shin are the same print and there are still only
   two distinct limb parts. The foot and the hip carrier do become a left and a
   right, which is two extra prints on the robot.

   *Amended by decision 10: the two leg segments are no longer the same print.*
10. **The knee is straddled again, and the knee alone.** This reverses half of
    decision 8, on the same unanswered question that decision recorded. The knee
    carries the shin, the wheel motor, the adapter and the wheel on a plate
    22 mm off its axis — 0.45 Nm standing on one leg and about 1.35 Nm landing
    at three times body weight — and it is the largest overhung moment on the
    robot by some way. The wheel joint carries the wheel alone on a 12 mm arm, a
    third of that; the hip was never unstraddled. So the thigh's lower end is
    `statorClevis` again, the hip's own part used exactly as drawn, with a 6800
    bonded into its far cheek and a Ø10 dowel journal out of the shin's rotor
    disc. Four bearing-and-journal sets rather than two.

    **What it costs, all of it measured.** 9.6 g of PA12 a thigh and 19.8 g of
    steel, so 38.9 g on a robot that had 191 g of headroom and now has 152. The
    two leg segments stop being the same print: four distinct limb pieces, one
    of each, where there were two printed twice. The thigh loses the flat print
    orientation — its far cheek stands 48 mm across the joint from its plate, so
    laid on that plate it has a disc floating in the air — and **which way it
    should be printed instead has not been decided.** And the knee's fold limit
    becomes structural again, which is unavoidable rather than an oversight: a
    far bearing means reaching round the actuator, and what reaches is a saddle
    standing in the plane the shin sweeps. They touch at 103.0°, so the
    commissioning stop is 100° rather than the inherited 110°, and the deepest
    squat is 14.5 mm shallower.

    **What it does not do is answer decision 8's question.** DAMIAO still have
    not said what the DM-J3507's output bearing will take. This takes the knee
    off the list of joints that depend on the answer; the wheel joint is still
    on it, at a third of the load.

    *Amended 13 September 2026: the journal is not a bought part any more.* The
    limb's output disc grows its own Ø10 stub into the far bearing and is printed
    with it, at the hip and at the knee, with a 0.8 mm fillet at the root. Four
    dowels, four bonded joints and 29.6 g of steel gone, and the seat they went
    into with them.

    **It was the wrong thing to do on FDM and the right thing on SLS**, which is
    the whole of why decision 1 moved first. The stub carries the bearing's
    reaction as bending at its root: 17.8 to 23.2 MPa at the 500-650 N recorded
    at the 6800, against 30 MPa across an FDM part's layers -- a margin of 1.3 to
    1.7 on the joint that takes the actuator's full torque, where the limb's own
    worst section is held to seven times its load. Isotropic at 48 MPa it is 2.1
    to 2.7, and no longer the thing that breaks first.

    **What is still unquantified, and it is worth naming.** Fatigue, which nobody
    has run. And the stress concentration at the root: 0.8 mm on a Ø10 shaft is
    r/d = 0.08, a Kt near 1.9, and 1.9 x 23.2 is 44 MPa against 48. The static
    case survives that because PA12 is ductile at 18 per cent elongation and the
    peak redistributes; a cyclic one might not. The fillet is as large as the
    space allows -- the bearing's inner face is 1 mm off the disc.

---

## 5. Phase 1 — material and process selection

**Goal:** know what the shells are made of before designing them, because wall
thickness, rib pitch and boss design all follow from the material.

The current PETG is the wrong material for a stressed shell. It creeps under
sustained load, which `NOTES.md` already flags as an open risk for the bearing
pockets and the hip hub, and it softens near 80 °C right next to a motor that
runs at its continuous limit.

| Candidate | Case for | Case against |
|---|---|---|
| **PETG** (current) | Cheap, prints anywhere, known | Creeps, low Tg, weak layer adhesion — keep only for mock-ups |
| **PA6-CF / PA12-CF** | 2–3× the strength, far better creep and heat resistance; already named in the handoff as the intended later revision | Needs a hardened nozzle, drying and an enclosed printer; hygroscopic in service |
| **PC-CF** | Highest Tg of the practical options | Warps badly at these part sizes |
| **SLS PA12** | Isotropic — no weak layer axis — and thin curved shells print unsupported; this is what a shell architecture really wants | Must be sent out; per-part cost; slower iteration |

The layer axis matters more here than it did before. A stressed shell loads its
walls in shear along the print direction, and FDM is weakest exactly there, so
print orientation becomes a design input rather than a slicer setting. That is
the strongest argument for keeping SLS open for the final set.

- [x] Choose the structural material and record the decision with its reasoning
      — PA12-CF, section 4, decision 1
- [x] **Draw the box coupon.** `coupon_box.kcl` is the real limb section at full
      size: 30 × 30 mm outside, 2.4 mm wall, 200 mm long, with a solid 40 mm root
      to clamp in a vice and a Ø5 cross hole at the tip to hang weights from. The
      file carries its own print orientation, test method and expected numbers in
      its header. Executes on the engine.
- [ ] **Print and measure the box coupon.** Expect about 0.1 mm of tip droop per
      kilogram — roughly 0.2 mm at 2 kg and 1.0 mm at 10 kg, against a section of
      33 894 mm⁴. Plot deflection against load and take the slope; a single
      reading is not worth much.
- [ ] Print tensile and interlaminar coupons in the chosen material, in the two
      orientations the shells will actually use
- [ ] Print a bearing-seat coupon and a boss coupon; load them and leave them
      loaded for a week to get a creep number rather than a guess
- [ ] Decide wall thickness and rib pitch from the coupon results, not from
      the table above

**Gate:** the box coupon's measured stiffness must land within a factor of two of
prediction. If 10 kg gives much beyond 2 mm, the printed walls are softer than
assumed and the wall or the material is wrong.

The gate was originally written as *do not design shells until this passes*. That
has been relaxed deliberately, and the reason is worth stating: the wall is a
single named parameter, `shellWall`, and every part on the robot derives from it
rather than repeating the number. A disappointing coupon is therefore a one-line
change plus a re-run of the regression suite, not a redesign. What the gate still
genuinely holds back is **ribbing, lightening and any final mass claim** — none of
which can be sized honestly against a modulus nobody has measured.

---

## 6. Phase 2 — the joint module, designed once and used eight times

**Goal:** one parametric joint interface that clamps an exposed actuator between
two shell ends, replacing both the yoke and the knee bracket.

The knee already proves the interface. What changes is that the bracket stops
being a separate printed part and becomes the moulded end of a limb shell.

- [x] Define the joint as a module taking the two shell ends it joins, so all
      eight joints share one definition — `joint.kcl`, `statorClevis()` and
      `rotorHub()`
- [x] Drive from the 6 × M3 on Ø24, piloting on the Ø30 register — carried over
      from the retired `knee_module.kcl`
- [x] Anchor from the 4 × M3 on the rear Ø41 pattern, through the 3.2 mm cover
- [x] Keep the 69° connector sector clear on every joint, not just the knee
- [x] Leave the actuator's cylindrical face **fully open to air** — this is the
      cooling requirement and it is a hard constraint, not a preference
- [x] Carry the far support on a 6800-2RS in a **metal seat**, not a printed
      pocket — an aluminium flanged carrier bonded into the cheek with retaining
      compound, so no screw passes through a 3 mm printed wall. `hardware.kcl`.
- [ ] Put a hard stop on every joint, not only the knee, at the commissioning
      limits: hip roll ±25°, hip pitch −45° to +70°, knee 0–110°, ankle ±30°.
      **Not started.** Nothing in the CAD is a stop; the knee's 112.8° is
      structure meeting structure, which is a backstop.
- [ ] Route the actuator's cable into the shell interior at the joint, with a
      bend radius and a service loop. The cavity is left clear for it, but no
      routing is modelled, and this is blocked on the Phase 6 plug measurement.
      The limb end of it is answered: the connector relief faces aft and two
      cable-tie arches on the inboard face carry the run up the leg.
- [x] Mock-execute, then engine-execute, a single-joint review model —
      `limb_check.kcl`

**Gate: passed.** One joint module executes on the engine, holds an actuator with
both bolt circles genuinely engaged, and leaves the motor barrel open to air.

---

## 7. Phase 3 to 6 — building outward

### Phase 3 — the limb shell

**Goal:** one parametric closed shell used for all four links.

- [x] Build the parametric shell — `limb.kcl`, taking length; the joint ends are
      always a clevis below and a hub above, so orientation is not an argument
- [x] Closed box section. It is **not** tapered and **not** deeper than wide, for
      the reason in section 11: the knee fold sets the depth, not stiffness
- [x] Cable channel: the cavity runs right through and is left clear, closed at
      both ends by the joint structures that overlap it
- [x] Thigh and shin differ only in their argument, as the tube links did
- [x] Verify by section property, not by eye — 33 894 mm⁴ sagittal, 73× the old
      tube pair
- [ ] Internal bulkheads at both ends where the joint loads enter. Deferred with
      the ribbing, because both are sized from the coupon.
- [ ] Compare the calculated section against the measured coupon. This is the
      only part of Phase 3 the printer actually gates.

The plan's original "clamshell split with a lap flange" line has been dropped
rather than left open: decision 2 in section 4 reversed it, and the limb is
printed as one closed shell with no structural seam.

### Phase 4 — foot and ankle — **done**

- [x] Rebuild the foot as a shell rather than nine overlapping rails — it is now
      a shallow open-topped tray: 2.4 mm floor, continuous perimeter wall, two
      transverse ribs under the ankle spreader and a longitudinal rib tying heel
      to toe
- [x] Keep 115 × 65 mm and the four sensor seats
- [x] Carry the landing load into the shell walls, not into printed riser roots —
      priority weakness 4 in `NOTES.md` is closed
- [x] Keep the separate replaceable sole

The top is left open deliberately, and it is a printing decision rather than a
structural one. The foot prints sole-face-down, which is the orientation that
puts the layer lines across the landing load; in that orientation an open top
needs no support and a closed one would have to bridge 60 mm. The floor and the
perimeter wall are what carry the load, and a top skin would add mass at the
neutral axis.

### Phase 5 — pelvis and torso — **done**

- [x] One pelvis-and-torso shell. The battery tray, four corner posts, two cover
      rails and the hip beam are gone, replaced by a keel between the hip roll
      actuators and a full-width closed box above them.
- [x] Carry the hip roll moment through a closed section — the keel is a channel
      worth about 98 000 mm⁴ against the old hip beam's 597 mm⁴, roughly 165×
- [x] Provide a removable cover for electronics access — a 2.4 mm lid on a lip,
      four M3 into corner bosses
- [ ] ~~Merge `hip_carrier.kcl` into the shell.~~ **Retired: it was wrong.** The
      carrier sits on the *moving* side of the hip roll joint, so it can never be
      part of the pelvis. It stays its own file.
- [ ] ~~A metal axle for the hip roll hub.~~ Superseded: the hub is not a printed
      hub any more, and the far support is already the metal bearing carrier from
      Phase 2.
- [ ] **The reserved payload volumes could not be kept as they were.** See below.

The payload envelopes had never been checked against the actuators. The battery
reservation, 92 × 34 × 32 lying across the torso, sat **21 mm inside both hip
roll actuators**; the controller board clipped them by 13 mm; and the IMU was
buried inside the controller. This is forced by the kinematics rather than a
modelling slip — a Ø46 actuator on a 301 mm roll axis necessarily fills 278 to
324 mm at |x| between 25 and 71 — so the layout now follows the space the
actuators leave: power low in the keel, everything else stacked above the hip
saddles.

That repack also exposed a battery problem, which has since been settled a
different way. The keel's longest inside dimension is 63 mm, every common 6S
brick is 70–110 mm long, and even a single 18650 cell is 65 mm, so no pack could
be bought — one would have had to be assembled from pouch cells. **The robot is
tethered instead, and carries no battery.** See Phase 5a.

### Phase 5a — the tether, and what replaced the battery *(reversed; see Phase 5b)*

The pack is gone. 24 V and CAN arrive on a single umbilical from the bench
supply, and the keel that was drawn as a battery bay is now a power-entry bay.

This was taken as a decision rather than forced by geometry, but the geometry
was pushing the same way: no off-the-shelf 6S pack fits between the hip roll
actuators, so the on-board option was always going to be a hand-built pouch
pack, and the 190 g it weighed was the whole of the mass headroom.

**Dropping the battery is not simply minus 190 g, and this is the part worth
understanding.** The pack was also the DC bus's energy store and the only thing
on board able to absorb regeneration. Eight backdrivable actuators peak at about
32 A together; they push current *back* when a limb is driven by the ground or
by gravity; and a bench supply generally cannot sink current at all. A tether
adds resistance and inductance between the robot and whatever is at the far end.
So a low-ESR bulk capacitor bank at the robot end stops being the "TBD, after
bench tests" line it is in `BOM.md` and becomes required hardware. The keel
reserves it, together with the main fuse and the tether's terminal, as one
power-entry block of 38 × 62 × 30 reachable from underneath.

**The bank is not sized.** Sizing it needs the measured bus excursion from the
actuator bench tests and the real tether length. The 60 g carried in the mass
table below is an allowance for capacitors, fuse, terminal and clamp hardware,
not a measurement.

Modelled in `torso.kcl`: the umbilical enters the **back of the keel**, not the
back of the shell. Down there its pull acts within about 10 mm of the hip roll
axis rather than at the top of a 106 mm lever, and it arrives beside the
power-entry block instead of having to cross the electronics stack. Strain
relief is a cable tie through two narrow slots flanking the entry, so a pull is
carried in shear by 2.4 mm of wall and never reaches the terminal — and every
cut stays rectangular, which is the only blind pocket shape the engine accepts
in this shell.

~~The tether must be carried on a boom~~, ~~size the bulk capacitance from the
tether length~~ and ~~measure the real umbilical~~ are all struck out by Phase
5b. The boom is the one worth remembering: it was a rig requirement nobody had
designed, hanging a moving unmodelled load on a biped with a 170 mm track and no
hip roll, and the battery removes it rather than solving it. What survives of
this list -- sizing the bank against a measured excursion -- has moved to Phase
5b, because the excursion is now a pack's rather than a bench supply's.

### Phase 5b — the battery is back, and the torso grew to take it

**This reverses Phase 5a.** Both of the objections that removed the pack have
been answered rather than waved away, and `docs/NOTES.md` carries the full
record; what follows is the shape of it.

The pack is two 3S 2200 mAh bricks in series, 48.8 Wh for 288 g, stood ON EDGE
side by side in the bottom band of the pelvis. That orientation is the design:
laid flat the pair is 66 mm across the robot and misses, on edge it is 52 and
fits. No 6S brick was ever going to -- every one on the market is 108 to 125 mm
long -- which is what made Phase 5a's packaging argument look like a law rather
than a shape.

The mass argument is simply out of date. 190 g was the whole headroom in August;
deleting hip roll left 700. The real pack is heavier than that reservation
assumed as well, 288 g rather than 190, because the old figure worked out at
153 Wh/kg and no high-discharge 6S pack reaches it.

**The torso is 153.9 × 72 × 86 where it was 125 × 68 × 65.** The height is
derived in `cad/wheeled_parameters.py` from what has to fit; the depth is set by
a clearance, 1.6 mm between a pack and the ledges the electronics deck lands on;
and the width is not derived from the payload at all any more. It is twice the
hip half-spacing plus the clevis's own outboard face, so the shell ends exactly
where the joints it carries do. That gives 12.9 mm more than the payload needs,
which lands in the gap between the two bays. The robot stands 360 mm.

**The power hardware is bought rather than drawn.** The power-entry PCB this
project was going to lay out is gone; a SwiftWing PDB-02-XT60 distribution board
does that job, a Matek 12S Pro BEC makes the logic rail, and an INA226 watches
the bus. That deleted three BOM lines outright -- the tether's main connector,
the DC power switch the XT90-S replaced, and the M3 heat-set inserts every board
mount used to need -- and it is why the capacitor bank now stands on somebody
else's copper.

**One new printed part**, `cad/deck.py` -- the first piece on this robot the Zoo
engine never built, so the one piece gate B has nothing to compare against. It
is a 3 mm plate on four wall ledges, carrying the controller and the SBC over
the battery and holding the packs down. It is only half the battery's doing: the
SBC has had no mount drawn since the layout was first done, because the cavity
is full at floor level and a standoff has never had anywhere to land.

**What it costs.** 454 g all in -- 288 of cells, 65 of wiring and mounts, 13 of
distribution board, 66 of extra pelvis and cover and 33 of deck -- so the
headroom goes from 694 g to 240. The centre of mass rises from 168 mm to 202,
which lengthens the pendulum from 128 to 162 and slows the fall from 114 ms to
128, and costs six degrees of lateral
margin: the lean at which the centre of mass leaves the 170 mm track falls from
34° to 28°. On a robot with no hip roll that is the price to watch, and the cheap
fix is track width rather than mass placement.

- [ ] **Set the actuator undervoltage threshold to about 21.6 V**, 3.6 V a cell.
      It is configurable and its floor is 15 V, so six backdrivable motors will
      otherwise drag a pack past 3.0 V a cell and destroy it. This was irrelevant
      on a bench supply and it is one mistake per pack now.
- [ ] Size the bulk capacitance from the measured bus excursion. The pack is the
      regeneration sink now, which is a reason to expect the bank to shrink and
      not a measurement of how far; the 38 × 62 × 30 reservation stands.
- [ ] **Measure a pack, an XT90-S housing and a JST-XH shell before the pelvis is
      printed.** All three are catalogue figures, and all three are cut into a
      wall that cannot be adjusted afterwards.
- [ ] Find a home for the emergency stop. It matters more on a battery than it
      did on a tether, where the bench supply was always the stop of last resort,
      and a 22 mm mushroom wants 22 mm of hole and 30 mm behind it.
- [ ] Measure the actual bus current through a first stand and a first drive. The
      runtime estimate -- roughly two hours balancing, an hour driving, under
      twenty minutes holding a loaded crouch -- is computed and nothing in it has
      been seen. The INA226 on the bill is what closes it.

### Phase 6 — assembly, cables and service

- [ ] Every actuator removable without destroying a printed part
- [ ] Cable runs closed end to end, with strain relief at each joint. **Half
      done.** Each limb carries two cable-tie arches on its inboard face, and
      the connector relief at its lower joint faces aft, so a lead runs from its
      plug straight up the leg inside the limb's own silhouette. The crossings
      at the knee and the hip are measured as spans between tie points and are
      not drawn as cable.
- [ ] **Measure how far a mated plug and its strain relief project past the rear
      face** — carried over from `CHECKLIST.md` and now blocking, because the
      shell has to clear it
- [ ] Full fastener schedule: sizes, lengths, thread engagement, and which are
      metal-to-metal

---

## 8. Phase 7 — validation and the mass budget

The four-model regression suite is rebuilt against the new geometry and stays
the standard of evidence. Executing the neutral model alone still proves nothing.

- [x] Rebuild `main.kcl`, `pose_check.kcl`, `knee_limit_check.kcl` and
      `knee_prelimit_check.kcl` on the shell parts
- [x] Add the **mirrored walking stance** — `walk_pose_check.kcl`, mid-stride
      with both feet flat, an 84 mm stride. Nothing interferes, but the trailing
      ankle sits at 27.5° against a 30° limit, so a longer stride runs the
      trailing ankle out of travel before anything else moves.
- [x] Add a **hip-roll extreme scene** — `roll_limit_check.kcl`. The result is
      worth reading twice: with the other leg standing neutral, inward roll runs
      out at **6.9°**, not 25°, because the two soles meet. See section 11.
- [x] Re-derive the static torque envelope on the new masses — the tethered
      2 165 g robot buys a sustained-load knee limit of 42.0°, against 39.6° for
      the 2 295 g build that carried a battery
- [x] Model the ankle and hip-roll cases — both now have numbers, below
- [ ] Add a **simultaneous joint extremes** scene; each joint has now been taken
      to a limit on its own, but never together
- [ ] Thermal check with an actuator in its final mounting: hold 0.8 Nm and
      measure the shell temperature next to the motor

### The mass ceiling is set by torque, not by a target

Mass is allowed to grow as far as the actuators can reasonably drive it. That
turns out to be a calculation rather than a preference, and the answer is
uncomfortable in an interesting way.

Take the single-leg static model already in `NOTES.md` — body mass on 105 mm
links with the hip above the ankle — and invert it. The knee has to hold
`m · g · 105 sin(θ/2)`, so the mass the actuator can carry falls as the crouch
deepens:

| Sustained knee angle | Knee lever | Mass ceiling on the 0.8 Nm continuous rating |
|---:|---:|---:|
| 20° | 18.2 mm | 4.47 kg |
| 30° | 27.2 mm | 3.00 kg |
| 40° | 35.9 mm | 2.27 kg |
| 45° | 40.2 mm | 2.03 kg |
| 50° | 44.4 mm | 1.84 kg |
| 60° | 52.5 mm | 1.55 kg |

**The continuous rating governs, not the peak.** Allowing three times body
weight for landing impact against the 3 Nm peak gives a ceiling 25 per cent
*higher* than the continuous figure at every angle, so the thermal limit binds
first and the structural 6 Nm target is never the constraint. This confirms from
the other direction what `NOTES.md` already concluded: the limit is duty, not
range.

So mass and crouch depth are the same decision. Growing the robot from 1.95 kg
to 2.4 kg pulls the sustained-load knee limit from about 46° down to about 38°.
Nothing about the mechanism changes — the 110° hard stop stays, and the robot can
still fold up to sit down or recover — but it can no longer *hold* a deep crouch
while loaded.

**Recommended budget: 2.3 kg**, which keeps sustained load to roughly 40°. That
is still three times the 12° crouch the current pose check uses, and it leaves
about 250 g of headroom over the estimate below — enough to build the shells
properly, with metal bearing seats and real ribbing, instead of value-engineering
them from the first day.

| Group | Target |
|---|---:|
| Actuators, 8 | 1 200 g (fixed) |
| Bearings, journals, metal seats | 90 g |
| Limb shells with integral joint ends, 4 | 220 g |
| Feet and soles, 2 | 90 g |
| Pelvis and torso shell | 130 g |
| Fasteners and inserts | 60 g |
| Electronics and wiring | 100 g |
| Power entry — bulk capacitors, fuse, terminal | 60 g |
| **Estimate** | **≈ 1 950 g** |
| **Ceiling** | **2 300 g** |

### The ankle and hip roll, now modelled

Both were open. Both now have numbers, taken on the measured 2 165 g tethered
robot. The robot has since come down to 2 025 g, which eases every figure below
by about six per cent and changes none of the conclusions -- each case gets a
little more margin, not less. The bracketed figures are what the same cases gave at 2 295 g with a
battery, to show which way losing the pack moves them.

- **Ankle.** In single support it carries 2 088 g. On the continuous rating the
  centre of pressure may travel **39.0 mm** from the axis (was 36.8 mm) — 59 per
  cent of the 66 mm to the toe, 80 per cent of the 49 mm to the heel. A full toe
  load is 1.35 Nm, which is 1.7× continuous but under half the 3 Nm peak. So
  push-off is fine and it is *standing* on the toe that is not. The foot is the
  right size; its continuous working area is simply smaller than it looks.
- **Hip roll.** Standing on one leg, the roll actuator carries 1 493 g at the
  48 mm half-spacing, which is 0.703 Nm — **88 per cent of the continuous
  rating** (was 96 per cent). Losing 130 g off the torso helps here more than
  anywhere else, because torso mass is exactly what this joint holds up. Static
  single-leg stance with the body centred is still not comfortable: shifting the
  centre of mass 7 mm toward the stance foot, about 1.4° of lean, brings it to
  75 per cent. Real bipeds lean anyway, but this has to be in the controller
  rather than assumed.

---

## 9. Carried over, and retired

Carried into this plan from `CHECKLIST.md`:

- Mated-plug axial projection — now blocking, Phase 6
- Cable channels, service loops, strain relief — Phases 2, 3 and 6
- Real M3 holes, nut traps and service fasteners — Phases 2 and 6
- Ribbing and hollowing to recover mass — the whole premise of the overhaul
- Full ROM and mirrored-pose validation — Phase 7
- Printed coupons for creep and layer strength — Phase 1, and now a gate
- The question to DAMIAO about the output bearing's radial and moment rating —
  still open, still decides how much the far support has to carry

Retired as no longer applicable:

- Converting tube sockets into clamped interfaces — done, then superseded
- The three yoke support schemes and the yoke's Ø46.6 cheeks
- Resolving the link socket against the joint hardware it sits inside — the
  shell end *is* the joint hardware, so the conflict cannot arise

Settled and not revisited:

- Importing the vendor STEP. The engine rejects it and a direct session import
  times out after 300 s; the parametric proxy plus the recorded interface
  numbers stay the only representation.

---

## 10. Order of work

Phases 2, 3, 4 and 5 are done, along with the missing poses and torque models.
Phase 1 is drawn and waiting on hardware. What follows is the order for the rest.

1. **Designed hard stops.** They belong on the limb parts, not in `joint.kcl` —
   see section 11 for why the shared clevis cannot carry them. A pad on the
   pelvis for hip roll, on the thigh for hip pitch, on the shin saddle for the
   ankle; the knee can be stopped by widening the saddle chord.
2. **A simultaneous-extremes pose.** Each joint has now been taken to a limit on
   its own, never together.
3. **Phase 1, print and measure**, the day the printer lands.
4. **Ribbing and lightening.** Less urgent since the battery came out — the
   build is about 135 g under the ceiling rather than 5 g — but still the way to
   buy margin back. Sized from what the coupon actually measured.
5. Phase 6, cables and service, once a mated plug can be measured.
6. Print one complete leg before printing two.

### Waiting on the printer, and what is not

Only the numbers wait. The wall is one named parameter, `shellWall`, and nothing
on the robot repeats the figure, so a coupon that comes back soft is a one-line
change and a re-run of the four regression models. Shape, kinematics, joint
interfaces, mass distribution and pose clearance are all independent of it, and
all of items 1 to 4 above can be finished before anything is printed.

The two things that genuinely cannot move are the mass claim — quoting a total
against an unmeasured modulus would be dishonest — and cable routing, which is
blocked on measuring a mated plug against a real actuator rather than on a print.

---

## 11. Build status — 28 August 2026

The skeleton is gone. `pitch_yoke.kcl`, `knee_module.kcl`, `tube_link.kcl` and
the carbon tubes have been deleted, and the robot is now built from four files:

| File | What it is |
|---|---|
| `joint.kcl` | The joint, designed once. `statorClevis()` and `rotorHub()`, used at all eight joints. |
| `limb.kcl` | A closed shell with a clevis at the bottom and a hub at the top, parametric on length. |
| `hardware.kcl` | The bought parts per joint: aluminium bearing carrier, 6800-2RS, Ø10 journal. |
| `limb_check.kcl` | The single-joint review model that gates Phases 2 and 3. |
| `coupon_box.kcl` | The Phase 1 bending coupon: the real limb section as a 200 mm test bar. Drawn, not yet printed. |
| `torso.kcl` | The pelvis and torso shell: a keel between the hip roll actuators, a closed box above them, a removable cover. |
| `foot.kcl` | The foot as a ribbed tray rather than nine rails. |
| `walk_pose_check.kcl` | Mirrored walking stance, both feet flat, 84 mm stride. |
| `roll_limit_check.kcl` | Hip roll at the inward limit the feet actually impose. |

`thigh.kcl` and `shin.kcl` are now three lines each. `hip_carrier.kcl` composes
the same two joint ends with its upper one turned a quarter turn, because the
hip roll axis is the only one that is not across the robot. `foot.kcl` lost its
twin risers and bridge rails and bolts straight to the ankle output through the
shared hub. `torso.kcl` gained a stator clevis and mount box at each hip.

### Done

- [x] **Phase 2 gate passed.** One joint module executes on the engine, holds the
      actuator on both of its real bolt circles -- 4 x M3 on Ø41 at the rear,
      6 x M3 on Ø24 at the front -- and leaves the motor barrel open to air.
- [x] **Phase 3.** One parametric shell serves all four limbs. Section verified
      by calculation: 33 894 mm⁴ sagittal, 73x the old tube pair, 0.13 mm tip
      deflection at three times body weight in a 45° crouch.
- [x] Metal bearing seat rather than a printed pocket, bonded in, no screws
      through a 3 mm printed wall.
- [x] All four regression models rebuilt and executing on the engine, plus the
      new single-joint model. Project lints and formats clean.

### Found while building

- **Dropping the battery is not just minus 190 g.** The pack was the DC bus's
  energy store and the only thing on board able to absorb regeneration from
  eight backdrivable actuators, and a tether is neither — it has resistance and
  inductance, and a bench supply generally cannot sink current at all. So a
  low-ESR bulk capacitor bank stops being a deferred line in `BOM.md` and
  becomes required hardware. It is reserved in the keel and **not yet sized**;
  the 60 g in the mass table is an allowance. The umbilical also has to be
  carried on a boom, because an unsupported cable hangs a moving, unmodelled
  load on the machine.
- **+Y is forward, and nothing in the torso file said so.** The tether slot was
  first cut in the robot's front, between its shins. It executed on the engine
  without complaint — a slot is a slot — and only a rendered front-and-back pair
  caught it. The convention is settled by `foot.kcl`, whose rear pressure pads
  sit at y = -40 and front pads at y = +51, and by the leading knee in
  `walk_pose_check.kcl` swinging to +Y. Note also that Zoo's *front* camera looks
  at the -Y face, so the view named "front" shows the robot's back.
- **The knee fold used to be limited by structure, and no longer is.** While
  the limbs were shells, the shin's rotor end fouled the thigh's saddle: 108.5°
  at a 34 mm section, 112.8° at 30 mm, which is why the section was square
  rather than the deeper-than-wide shape a leg would otherwise want. Those
  angles were first attributed to the rotor *arm*, which was wrong -- the arm
  was `shellInnerDepth` and never the first thing to touch. With flat limbs the
  question disappears: the thigh and the shin lie in different planes on either
  side of the knee actuator and cannot reach each other at any angle. The
  110° commissioning limit is now purely a control decision, which makes the
  designed hard stops below more important, not less.
- **Two engine limitations, both worked around and both worth knowing.** Blind
  pockets cut out of a large combined solid are rejected, so every cut is now
  made on the simple body it belongs to before anything is unioned. And a union
  of two hollow boxes meeting at right angles is rejected, so the hip carrier and
  the torso hip mounts are left as interpenetrating bodies -- the same fallback
  `NOTES.md` already records for the foot frame. Verify your slicer merges
  coincident shells before printing those two.
- Mock execution passes in both those cases. It does not exercise the booleans.
- **Inward hip roll is limited to 6.9°, not 25°.** The roll axis is 257 mm above
  the ankle, so a degree of roll moves the foot 4.5 mm sideways, and there are
  only 31 mm of air between two 65 mm feet on 96 mm centres. With the other leg
  standing neutral the soles meet at 6.9°; the shin shells would not meet until
  14.9°. Outward roll is unobstructed. This does not stop the machine walking —
  the swing leg is lifted, and a lateral lean rolls both hips the same way and
  never closes the gap — but inward roll against a planted neutral leg is a
  fault case, not available travel, and the commissioning limits should say so.
- **The walking stride is limited by the trailing ankle.** In the 84 mm stride
  of `walk_pose_check.kcl` nothing interferes, but the trailing ankle already
  sits at 27.5° against its 30° limit. Ankle travel, not clearance, is what caps
  the stride.
- **`calculate_kcl_physical_properties` is only trustworthy for volume and
  mass.** It returned a 173 mm bounding box in y for a 115 mm foot, and a centre
  of mass to match. Volume and mass agreed with hand calculation; nothing else
  from that tool is quoted here.

### Mass, measured from the CAD

`tools/mass.py`, SLS PA12 at 0.93 g/cm3. The four leg files each build both hands
now, so their figure is the pair.

| Part | Each | Count | Total |
|---|---:|---:|---:|
| Thighs, the pair | 64.2 g | 1 | 64.2 g |
| Shins, the pair | 64.2 g | 1 | 64.2 g |
| Hip carriers, the pair | 74.4 g | 1 | 74.4 g |
| Feet, the pair | 149.3 g | 1 | 149.3 g |
| Pelvis and torso shell with cover | 187.3 g | 1 | 187.3 g |
| **Printed structure** | | | **539 g** |
| Actuators | 150 g | 8 | 1 200 g |
| Bearing, journal, carrier | 16.3 g | 4 | 65 g |
| Fasteners | | | 60 g |
| Electronics and wiring | | | 100 g |
| Power entry — capacitors, fuse, terminal (allowance) | | | 60 g |
| **Total** | | | **2 025 g** |

**Three changes bought the margin, in this order.** Going tethered removed a
190 g battery for a 60 g power-entry allowance, taking the robot from 5 g under
the ceiling to about 135 g. Then the limbs moved their structure into the
actuator's output plane, deleting the arm and the bridge, and the forked rotor
came off with its four extra bearing sets. Then the limbs went flat: no clevis,
no saddle, no shell, and no far bearing at the knee or the ankle. The robot is
now **2 025 g with 275 g of headroom**, and the sustained-load knee limit is
**45.1°** against a 40° target.

A limb is 32.1 g, against 48.3 g before any of this month's joint work. The 60 g
power-entry figure is still the softest number in the table, because the
capacitor bank has not been sized.

### How much sideways load the printed parts take

Hand calculation from the sections, with nothing measured behind it. The binding
case is a sideways force at the foot, and the part that gives is the limb plate
where it meets a disc, in the short run the waist flanges cannot reach: 6 mm
thick against 30 mm deep on a 254 mm lever at the hip pitch, so Z = 180 mm³ and
stress is 1.41 MPa per newton at the foot.

| Printed section | Z | Across layers, 30 MPa | In print plane, 75 MPa |
|---|---:|---:|---:|
| Limb plate at a disc — 6 × 30 | 180 mm³ | **21 N** | **53 N** |
| The same plate at 8 mm thick | 320 mm³ | 38 N | 95 N |

The robot weighs 20 N and the lateral ground reaction in single support is
perhaps 6 N, so the margin is about nine times printed one way and three and a
half the other. Against a fatigue limit of roughly a third of ultimate the bad
orientation is marginal and the good one is not, **which makes print orientation
the reinforcement to spend first: it is worth 2.5× here and costs nothing.** If
the coupon then says more is needed, 8 mm of plate instead of 6 is another 1.8×
for about 3 g a joint.

**Stiffness is a separate question and it is where the waist flanges earn their
keep.** A bare plate is sixty times softer sideways than the closed box it
replaces — 540 mm⁴ against 33 894, which is 7.7 mm of sway at the hip in single
support. The two 12 × 4 mm flanges take the waist to 9 468 mm⁴ and 0.44 mm for
about 5 g a limb, and leave the sagittal section at 29 852 mm⁴, within twelve per
cent of the box.

### Still open

- [ ] **Phase 1 coupons.** The box coupon is drawn and executing --
      `coupon_box.kcl` -- but there is no printer on site and one is roughly a
      week out. The stiffness case rests on calculation until it is measured.
      This does not block items 1 to 4 of section 10; see the note there.
- [x] **Phase 4, properly.** The foot is a closed-perimeter tray with ribs, not
      nine overlapping rails.
- [x] **Phase 5, properly.** The torso is one closed shell with a keel and a
      removable cover, and the payload interference it exposed is fixed.
- [x] **Phase 7 poses and torque models.** Mirrored walking stance and the
      hip-roll extreme are rendered; the ankle and hip-roll static cases have
      numbers.
- [ ] **Designed hard stops. Not started, and the reason is worth recording.**
      The shared clevis cannot carry them: everything inside Ø52 of the joint
      axis is either the actuator body (radius 23), the bearing carrier, or a
      3 mm printed cheek, and a pin-in-slot through that cheek would shear under
      a full-torque runaway — which is worse than no stop, because it invites
      trust. Widening the saddle chord can stop the knee at 110°, since the
      structural contact is already at 116°, but the same trick cannot reach
      ±25° or ±30°. **So the stops belong on the limb parts** — a pad on the
      pelvis for hip roll, on the thigh for hip pitch, on the shin saddle for
      the ankle — where there is room and material. Each needs its own rendered
      pose at the limit, which is why the two new poses had to come first.
- [ ] **A simultaneous-extremes pose.** Each joint has been taken to a limit
      alone, never together.
- [ ] **Phase 6, and it got harder.** The limbs no longer have an internal
      cavity, because they no longer have an inside: the closed shell that used
      to carry the cable went when the legs went flat. Routing is now external
      along the plate, which means clips, a service loop at each joint and
      abrasion protection where a cable crosses a rotating face. **The clips
      exist now** -- two cable-tie arches on each limb's inboard face, and the
      lower joint's connector relief turned round to face aft so that every lead
      on the robot leaves on the side the pelvis's floor ports are on. What is
      still only arithmetic is the loop at each joint: 68 mm of lead with 37 of
      slack at the knee, 75 with 40 at the hip on a travel nothing has confirmed.
      The pelvis slots at each hip are unchanged. Still blocked on the
      mated-plug measurement.
- [ ] **Designed hard stops matter more than they did.** The knee fold used to
      be backed up by structure at 116°. Flat limbs lie in different planes and
      cannot touch, so there is no longer any structural backstop anywhere on
      the robot: every limit is a number in software until a pad is drawn.
- [ ] **Ribbing and lightening** — no longer the only thing keeping the robot
      under its ceiling, but still the way to buy margin, and still waiting on
      the coupon.
- [ ] **The tether's two loose ends**, both in Phase 5a: the bulk capacitor bank
      is required hardware and is not sized, and the umbilical needs a boom or
      balancer to carry it. Neither is geometry, and neither is optional.
- [ ] **Print orientation, which is now a structural decision.** It is worth
      2.5× on the sideways load the rotor plate will take, which is the binding
      strength case on the robot. Coupons in both orientations are already in
      the Phase 1 list; this is what they are for.
- [ ] **Ask DAMIAO for the output bearing's radial and moment rating.** Dropping
      the forked rotor assumes the actuator's own bearing carries the joint
      moment. Nothing else in the design depends on an unanswered question this
      directly, and if the answer is unfavourable `rotorYoke` goes back in.
