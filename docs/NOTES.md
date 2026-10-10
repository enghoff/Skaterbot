# Initial Biped Skeleton Notes

## Architecture

- Overall neutral height: **380 mm**.
- Eight actuators: hip roll, hip pitch, knee pitch, and ankle pitch per leg.
- Hip spacing: **96 mm**.
- Hip-pitch to knee and knee to ankle: **105 mm** each.
- Feet: **115 x 65 mm** with a separate 2 mm sole and four sensor locations.
- Link choice: **Option B**, twin 8 x 8 x 1 mm carbon-fibre square tubes with printed end interfaces. This gives lower distal inertia than fully printed box links.
- Torso envelope: **126 x 74 x 106 mm**, with the battery reserved low near the hip axes.

## Actuator data — now authoritative

DAMIAO publish the manual, the 2D print and a STEP model for this actuator on their own Gitee, at `gitee.com/kit-miao/DM-J3507-2EC`. The figures below are from the user manual V1.0 (2024-11-19) and the 2025 selection catalogue, not from estimates.

| | |
|---|---|
| Rated / peak torque | **0.8 Nm / 3 Nm** |
| Rated / no-load speed | 150 rpm / 460 rpm |
| Reduction | 7:1, 14 pole pairs |
| Phase current, rated / peak | 3.0 A / 8.3 A |
| Supply current, rated / peak | **1.2 A / 4 A** |
| Voltage | 24 V rated, 24-30 V supported, undervoltage cutout at 15 V |
| Envelope / mass | Ø46 x 37.9 mm, ~150 g |
| Encoders | two 14-bit magnetic, single-turn absolute on the output shaft |
| Interfaces | CAN, 1 Mbps default, up to 5 Mbps as CAN FD; UART at 921600 for tuning |
| Thermal cutouts | driver 120 °C, motor coil recommended <= 100 °C |

The **0.8 Nm continuous rating** is the number that matters for this robot and was previously unrecorded. The 3 Nm figure the design targets is a peak, not a duty rating.

Control is four modes selected through register `0x0A`: MIT on the base CAN ID, position-velocity at `0x100+ID`, velocity at `0x200+ID` and a force-position hybrid at `0x300+ID`. Position, velocity and torque in the feedback frame all refer to the output shaft after reduction.

## Corrected actuator envelope

The vendor STEP confirms Ø46.000 mm and 37.9 mm overall, and confirms that **nothing protrudes beyond that envelope**. The previous proxy in `actuator.kcl` added an output flange, an output boss and a rear pilot outside the 37.9 mm body, making it 48.9 mm long overall and placing the output interface about 7 mm too far out. The proxy is now a plain Ø46 x 37.9 mm cylinder, and the interface is carried by exported parameters in `parameters.kcl` rather than by guessed geometry.

Resolving all fifteen assembly transforms into a single frame gives the envelope exactly: **Y from 0.000 to 37.900 mm, maximum diameter Ø46.000 mm**, with no part of the assembly reaching past either bound. Stations below are measured from the front face at Y = 0.

The part stack, in assembly coordinates:

| Component | Axial station | Diameter |
|---|---|---|
| Main body (surface model) | 0.00 - 30.70 | Ø46.00 |
| Plate `3505_00` | 28.45 - 34.70 | Ø46.00 |
| Plate `3505_0002` | 34.70 - 37.90 | Ø46.00 |
| Driver PCB | 31.95 - 36.80 | Ø42.10 |
| 4 x M2.5 internal screws | 2.00 - 9.00 | on Ø42 PCD |
| 4 x M2.5 internal screws | 30.90 - 37.90 | on Ø42 PCD |
| 3 x small screws | 5.65 - 11.21 | on Ø17.5 PCD, 120° apart |

Interface features, all on the **front face**:

- **6 x M3 on a Ø24 mm bolt circle** on a **Ø30 mm boss standing 1 mm proud** of the body, with a shallow concentric Ø8-10 mm bore. This is the rotating output. The manual's page-4 drawing dimensions 36.90 mm to the body and 37.90 mm over the boss, so the mating hub needs a Ø30 bore to register **onto** the boss. An earlier revision of this file called it a 3 mm recess, which was wrong — the concentric bores seen in the STEP at that station are internal features, not the register.
- **4 x M3 on a Ø41 mm bolt circle** at 90° spacing, on the stationary housing outside the register.
- The Ø42 mm circle carries the actuator's own M2.5 assembly screws. It is not a mounting pattern.

**Which face is the output is now settled.** The rear third of the actuator is a plate / driver-PCB / plate stack, which must be stationary because it is what the cabling terminates on. The Ø41 pattern sits on the outer housing beyond the register, so it is the stationary mount. Everything inside the Ø30 register — the Ø24 bolt circle and the central bore — is the rotating output. So one link bolts to the outer circle and the other to the concentric inner circle, both from the front.

**There is no through-bore.** The central features are only about 3 mm deep from the front face, and the rear face carries nothing within Ø20 mm of the axis. A through-shaft, which would have carried joint bending independently of the actuator, is not available.

Two caveats. The STEP's main body is exported as an open-shell surface model rather than a solid, so it may not import as usable solid geometry. And its internal part names read `3505` rather than `3507` (the 2D print is likewise titled "DM 3508-7"), which appears to be the base stator designation reused, but confirm the envelope on opening it.

### Correction — the cable exit is not radial

An earlier revision of this file recorded a "radial cable exit 31.7 mm from the output face". That was wrong. The figure came from misreading plate `3505_00`'s placement origin as a connector location. **No part of the assembly projects beyond Ø46**, and there is no radial slot in the shell. The driver PCB sits at Ø42.1 inside the rear stack, so the electrical interfaces are on or near the **rear face** and the keep-out is axial rather than radial.

The manual's page-4 figures resolve where they are. The housing carries a **flat chord across the Ø46 outside diameter at one angular position**, and the connectors sit at the **rear end** against that flat, opposite the Ø30 output boss. Both connector bodies fall inside the 37.9 mm and Ø46 envelope, consistent with the STEP.

The pinouts are also worth recording, because the manual contradicts itself. Its parts list says a 3-pin power/CAN cable and an 8-pin tuning cable; its pinout figures show **power/CAN as 8-pin** (3 x VCC, 3 x GND, CAN_L, CAN_H) and the **debug UART as 3-pin** (GND, RX, TX). The figures are authoritative, and tripling the supply pins matches the 4 A peak. `BOM.md` has been corrected accordingly.

The flat is now measured. It is a chord about 19.0 mm from the axis against the 23 mm radius, so it takes roughly 4 mm off one side, is about 25.9 mm wide, and subtends about 69° of arc. The two rear tapped holes that flank it, at 45° and 135°, clear the flat's edges by only about 11°, so a rear bracket can reach them but must not run material across the sector between them.

Still unmeasured: how far a mated plug and its strain relief project axially past the rear face. That needs the physical part or the connector's own datasheet, so it stays open.

## Yoke re-check against the real interface

Re-checking `pitch_yoke.kcl` against the measured interface changes the conclusion recorded here previously. The 38.5 mm clear cheek spacing against a 37.9 mm body still gives **0.3 mm of axial clearance per side**, so the envelope fit is sound and unchanged.

The problem is that the fit is not the constraint. Both cheeks are annuli bored to Ø46.6 mm to clear the actuator body, but **both real bolt circles — Ø24 mm and Ø41 mm — lie inside that bore**. The yoke as drawn has no material anywhere the actuator actually attaches, so the 0.3 mm clearance is measuring a gap that carries no load.

**Both bolt circles are on the same face**, as recorded above, so this is a pancake module and **the far side offers nothing to attach to or run a bearing on**. That invalidates the double-shear premise as drawn: cheeks straddling the actuator cannot pick it up on both sides, because there is only one side. Weakness 2 below is therefore not an alignment problem but an architecture question — the joint is a cantilever at the actuator until a second support is designed in.

## Support architecture — the load case decides it

The governing requirement is the handoff's 100 N side load at 100 mm from the joint axis, which is **10 Nm of bending**. What matters is the span between the two bearings that resist it, because a short span multiplies the reaction:

| Bearing span | Reaction per bearing |
|---:|---:|
| 8 mm | 1350 N |
| 12 mm | 933 N |
| 20 mm | 600 N |
| 30 mm | 433 N |
| 40 mm | 350 N |

Since both interfaces are on the front face, a support confined to that face gets only 8-12 mm of span against the actuator's own internal bearing, so roughly **1000-1350 N per bearing**. Reaching past the 37.9 mm body is what buys span, and that is the whole argument.

Mass matters as much as load. There is 40-80 g of headroom plus the 100-150 g this file already identifies as recoverable, so the realistic ceiling for new joint hardware is **140-230 g, or 18-29 g per joint across all eight**.

### The three schemes, assessed

**A ring bearing on the front face only — rejected on load.** Of the bearings that fit the Ø30-Ø46 annulus, only a 6706 (30 x 37 x 4) is light enough at 6.4 g per joint, 51 g across eight. But a single bearing cannot resist a moment, and paired with the actuator's internal bearing the span is 8-12 mm, so the reaction is around 1000 N — far beyond an extra-thin 4 mm section. Stepping up to a 6806 (30 x 42 x 7) costs 20.5 g per joint, 164 g in total, which is over budget, and it still only buys about 12 mm of span. This fails on load, not on mass.

**A plain bearing on the Ø46 housing — rejected on friction.** The lightest option by far at about 3.2 g per joint, 26 g in total, and running on the outside diameter gives a useful arm. But sliding friction at Ø23 radius under 100 N costs 0.18 Nm even at an optimistic µ = 0.08, rising to 0.35 Nm at a realistic dry µ = 0.15. That is **23% to 43% of the actuator's entire 0.8 Nm continuous rating** lost to friction, in a robot whose premise is backdrivable torque control. It also clamps the stator, which is the heat path.

**A ribbed shroud past the far end, carrying a stub axle — recommended.** Reaching 40-50 mm gives 300-350 N per bearing, comfortably inside a small commodity bearing. A full 2.5 mm cylindrical shroud costs 19.4 g per joint and 155 g overall, which is too much, but ribs covering 30-40% of the annulus cost **4.6-7.7 g per joint, 37-62 g overall**, which fits. It is the only scheme that achieves the span the load case demands at an affordable mass.

Two conditions on that recommendation, which the confirmed rear mounting below makes largely academic. The shroud and its stub-axle boss have to clear the rear-face cabling, and if mass gets tight, **double-supporting only the knee and ankle** — the four joints that see landing loads — halves the cost, leaving hip roll and pitch on shorter arms single-supported.

### A rear-face mount supersedes all three

The manual's page-4 end view carries an explicit **4 x M3 tapped 4 mm deep** plus 4 x Ø3.20, and its centre is empty — no Ø30 boss and no Ø24 circle. So that view is the **rear** face, and the housing appears to be bolt-mountable from **both** ends: 4 x M3 deep 5 at the front and 4 x M3 deep 4 at the rear. The output is still front-only, but the *housing* is not.

If that holds it changes the answer. Anchor the fixed link to the **rear** face, run arms forward alongside the Ø46 body, and carry the bearing near the front output plane. That gives about 38 mm of span — the 350 N case — without any structure wrapping backwards over the cabling, and the connector flat says which angular sector to leave clear. It is a shorter, stiffer load path than the ribbed shroud and probably lighter, because the arms are loaded in tension and compression rather than as a cantilevered shell.

**Both sources now agree, so this is the architecture to build.** The vendor 2D print's rear view carries `4xM3 v4` and `Ø3.20 v3.2` as two callouts on the same four locations, and the STEP matches exactly. The 3.20 mm outer rear cover, part `3505_0002`, has four Ø3.20 clearance holes on a Ø41.00 circle at 45°, 135°, 225° and 315°. The plate immediately beneath it, `3505_00`, has four Ø2.50 tapped holes on the same Ø41.00 circle at the same four angles, and Ø2.50 is the tap drill for M3. So a screw passes through 3.2 mm of cover before it reaches 4 mm of thread. That sets the fastener: bracket thickness plus 3.2 mm plus engagement, so M3 x 10 or M3 x 12 for a 4 mm bracket, and the plain shank must not exceed 3.2 mm plus the bracket if the thread is to engage fully.

**Do not mistake these for the cover screws.** A second four-hole pattern sits on Ø42.00 at 33.5°, 146.5°, 213.5° and 326.5°, Ø2.20 through the cover into Ø2.10 below, and those are the M2.5 screws holding the rear stack together — the STEP ships M2.5 fastener solids at exactly those positions, and they are what the hex-socket symbols in the rear view represent. Undoing them opens the driver compartment.

### The question worth asking the vendor

The long span is forced entirely by the 100 N at 100 mm case. If that is a survival case rather than a design case, a modest front bearing sharing load with the actuator's internal bearing becomes viable and much simpler. Deciding that needs **DAMIAO's radial and moment load rating for the output bearing**, which the manual does not publish. Worth asking them directly, because the answer removes or confirms the need for the shroud.

The top and bottom cross-straps run the full 44.5 mm width at Ø54, so they need re-checking against whatever the shroud becomes.

## Load path

Ground load travels from the replaceable sole and corner sensor seats into the foot perimeter rails and center spine, through two transverse ankle bridge rails and twin risers, then through the ankle yoke, output interface, and opposite bearing. The shin and thigh use paired carbon tubes to carry bending and torsion. Joint loads continue through the knee yoke, hip-pitch module, orthogonal hip carrier, torso hip beam, corner posts, and torso tray.

## Module mass estimates

Estimates use ideal modeled volume, PETG at about 1.27 g/cm3, carbon composite at about 1.6 g/cm3, and TPU at about 1.2 g/cm3. They exclude print-process variation and are not slicer estimates.

| Module | Quantity | Estimated total |
|---|---:|---:|
| Actuators | 8 | 1200 g fixed assumption |
| Printed yoke structures | 8 | 65 g |
| Opposite support bearings | 8 | 40-64 g allowance |
| Hip carriers | 2 | 50 g |
| Thigh modules | 2 | 30 g |
| Shin modules | 2 | 28 g |
| Feet including thin soles | 2 | 97 g |
| Torso frame | 1 | 104 g |
| M3 hardware/shafts | — | 30-45 g allowance |
| Electronics and wiring | — | 100 g assumption |
| 6S battery | 1 | 175 g midpoint |

Expected initial total: approximately **1.92-1.96 kg**. This is below 2.0 kg but not close to 1.8 kg. Non-foot printed/carbon structure is about **277 g before bearings and hardware**; the feet are about **97 g total**.

A credible route toward 1.8 kg is to rib the torso trays, hollow the hip-carrier hubs, use smaller thin-section support bearings with metal shoulder axles, reduce foot-frame volume after load testing, and select a battery near the low end of the 150-200 g range.

## Motion check

`pose_check.kcl` validates a crouched step without visible self-collision:

- Stance leg: hip -6 degrees, knee 12 degrees, ankle 18 degrees.
- Swing leg: hip 35 degrees, knee 65 degrees, ankle 25 degrees.
- Swing foot absolute pitch: about -5 degrees.
- Calculated swing-foot ground clearance: approximately **22 mm**.

The test verifies a useful walking pose, not every simultaneous extreme. Recommended commissioning limits are hip roll +/-25 degrees, hip pitch -45 to +70 degrees, knee 0 to 110 degrees, and ankle +/-30 degrees. After hard-stop, cable, and interference refinement, the intended mechanical goals are approximately hip roll +/-30 degrees, hip pitch -55 to +80 degrees, knee 0 to 125 degrees, and ankle +/-40 degrees. Simultaneous inward hip-roll extremes near +/-35 degrees are not considered collision-safe in the present layout.

### Regeneration verification — August 23, 2026

`main.kcl` and `pose_check.kcl` were both mock-executed and executed successfully in Design Studio after the actuator proxy was changed to a plain Ø46 x 37.9 mm cylinder. Neutral and crouched multi-view renders show all actuator envelopes and no **visible** self-collision.

The crouched pose still has approximately **21.8 mm** of swing-foot clearance: the right ankle is at about 71.3 mm above the nominal ground plane, and the -5° foot pitch lowers the forward sole corner to about 21.8 mm above it. This confirms the approximately 22 mm claim. It is a single-pose visual/kinematic check, not a full-ROM collision proof.

The yoke's 38.5 mm clear cheek spacing now exceeds the 37.9 mm proxy length by 0.6 mm, leaving the intended 0.3 mm axial clearance per side. The regenerated neutral and crouched views show no apparent motor/yoke/link interference. This verifies envelope clearance only; the yoke remains structurally invalid for the real actuator interface because its Ø46.6 annular cheeks contain neither real bolt circle.

The initial constraint-report attempts for `pose_check.kcl` dropped their modeling connection while resolving imports, but a retry after re-execution succeeded on August 23, 2026. The entrypoint reported no constraint errors or warnings; it reports zero local sketches, so this result does not independently enumerate constraints inside the imported part files.

## Static torque envelope

A static single-leg-stance model, 1.95 kg on 105 mm links with the hip held above the ankle, gives the knee torque required to hold a given crouch. Knee offset is `105 * sin(angle / 2)`; required torque is weight times that offset.

| Knee angle | Knee offset | Static torque | At 2x GRF | At 3x GRF |
|---:|---:|---:|---:|---:|
| 12° | 11.0 mm | 0.21 Nm | 0.42 | 0.63 |
| 30° | 27.2 mm | 0.52 Nm | 1.04 | 1.56 |
| 45° | 40.2 mm | 0.77 Nm | 1.54 | 2.31 |
| 60° | 52.5 mm | 1.00 Nm | 2.01 | **3.01** |
| 90° | 74.2 mm | 1.42 Nm | 2.84 | 4.26 |
| 110° | 86.0 mm | 1.65 Nm | 3.29 | 4.94 |

Two conclusions, and both are design constraints rather than observations.

The architecture holds. Even a fully folded 110° knee on one leg needs only **1.65 Nm against a 3 Nm peak**, so the actuator can hold any static pose within its range with margin, and the 6 Nm structural target stays correct.

The binding limit is duty, not range. The **0.8 Nm continuous rating is crossed at about 47° of knee flexion**, and allowing three times body weight for landing impact reaches the 3 Nm peak at **60°**. So the mechanical stop stays at 110° for crouching and recovery, but sustained loaded stance beyond roughly 45° is a thermal limit the controller has to respect, and dynamic walking should stay inside about 50°. The existing pose check is comfortably inside this at 0.21 Nm.

This is a computed result, not a measured one. It assumes the hip stays above the ankle and ignores link mass, so treat it as the shape of the limit rather than a precise threshold.

## Electrical and bus notes

- **Every actuator ships with its CAN termination resistor enabled.** Eight in parallel gives roughly 15 Ω instead of 120, so termination must be switched off on all but the two ends of the bus.
- Peak supply current is 4 A each, so eight actuators can draw about **32 A at 24 V, near 770 W**. Continuous draw is far lower at 1.2 A each, about 9.6 A. The battery, wiring and connector sizing all follow from the peak figure.
- The provisional **6S pack is the right choice**: 25.2 V charged sits inside the 24-30 V window, whereas 7S at 29.4 V would sit on the over-voltage limit. The trade is that 6S spends most of its discharge below the 24 V nominal, so peak speed fades as the pack empties.
- Saving parameters writes to flash rated for only about 10,000 cycles, so configuration should not be written on every boot.

## Five priority weaknesses before refinement

1. **Hip-roll carrier and torso hip beam:** peak roll moments enter a solid printed hub and narrow rails. PETG creep and layer splitting are likely without a metal shoulder axle, large washers, and a cross-tied hip beam.
2. **Opposite-bearing support, not just alignment:** the STEP confirms the actuator has no rear spigot, so there is nothing on the motor for a support bearing to run on. The stub axle has to be supplied by the yoke and located off the 4 x M3 Ø41 housing pattern, which makes this a missing part rather than a tolerance problem. Printed bearing pockets alone can still ovalize or misalign; use a metal through-shaft or shoulder bolt with accurately located seats.
3. **Carbon-tube socket retention:** the current sockets are packaging blocks, not finished clamps. They need real tube pockets, anti-rotation geometry, adhesive bond length, and transverse M3 through-bolts rather than relying on inserts or butt contact.
4. **Ankle and foot impact path:** the added bridge rails connect the risers to the spine, but landing loads remain concentrated at printed riser roots. Add generous ribs and consider a thin aluminum cross-plate or continuous metal ankle axle.
5. **Moving cable loops:** space is reserved but final ducts, bend radii, and strain relief are not modeled. Knee and ankle CAN/power leads are vulnerable to pinching and fatigue until routed through guarded rear channels and tested across the mechanical stops.

## CAD limitation

The foot-frame members overlap as one printable connected set, but the current CAD engine rejected a multi-body 3D union. They therefore remain overlapping top-level bodies in `foot.kcl`; verify that the selected slicer merges coincident/overlapping shells before printing.

## Deferred until hardware exists

There is currently no hardware, so nothing can be bench tested. The development order in `OPUS_HANDOFF.md` opens with characterising one or two actuators, and that step cannot start. Design work is not blocked by this — the vendor STEP and manual supply what the CAD was actually waiting on — but the following stay open and must not be read as settled:

1. **Thermal behaviour**, including whether the 47° continuous-torque limit above is real or conservative once the driver's own protection and duty cycle are involved.
2. **Backdrivability and gear friction** through the 7:1 reduction, which is the whole premise of the actuator choice.
3. **PETG creep** in printed bearing pockets and the hip-roll hub under sustained load.
4. **Layer-line strength** at the ankle riser roots under landing impact.
5. **Printed bearing-pocket accuracy**, which decides whether the double-supported yoke can hold the output and support bearing coaxial.

Items 3 to 5 need printed coupons; items 1 and 2 need a powered actuator on a bench. Until then, analysis can bound these but cannot close them.

## Verification status of CAD changes

KCL edits cannot be executed, regenerated or visually inspected outside Zoo Design Studio. The current actuator-interface implementation was regenerated in Design Studio on **August 24, 2026**: `knee_module.kcl`, `main.kcl`, `pose_check.kcl`, `knee_prelimit_check.kcl`, and `knee_limit_check.kcl` all execute successfully. The knee module contains 18 fully constrained sketches and has no lint findings.

## Knee actuator-interface implementation — August 24, 2026

### Scope and assembly integration

`knee_module.kcl` is a separate knee-only module. `main.kcl` and `pose_check.kcl` import it at the two knee locations only; the other six joints continue to import the original `pitch_yoke.kcl` unchanged. The fixed rear bracket follows the thigh-side actuator frame, while the output hub and journal follow the shin-side orientation in the crouched pose.

### Interface and hardware

- **Output hub:** Ø36 mm PETG hub landing FLAT on the Ø30 boss, with no register pocket and no pilot — the hub is located by its six screws, and its whole inboard face stands 1 mm clear of the housing behind the boss. It carried a Ø30.4 x 1.2 mm pocket until 14 September 2026, drawn on the reading that the boss stood into the hub rather than proud of the body; see the entry at the end of this file for why that was wrong and why a shallower pocket was not the answer. Plus 6 x Ø3.4 mm clearance holes on the authoritative Ø24 mm output circle. Six Ø6.0 mm x 3.2 mm cap-head counterbores retain the heads. The 12.6 mm bolt-circle chord spacing leaves about 7.1 mm between Ø5.5 mm M3 cap heads.
- **Output fasteners:** 6 x M3 x 6 socket-head cap screws. From the counterbore floor to the raised output-boss face is 2.8 mm, leaving 3.2 mm of the screw in thread. **This figure was 4.2 mm here until 14 September 2026 and the screws never had it**: the hub was modelled seating on the housing with the boss inside a 1.2 mm pocket, which put the thread's mouth 1.2 mm further out than it is. 3.2 mm is about 1.1 x D, and the vendor STEP models the output holes 4.0 mm deep, so M3 x 6 remains the right screw — an M3 x 8 would bottom before it clamped. At 6 Nm, equal sharing gives about 83 N tangential demand per output screw.
- **Rear bracket:** four Ø3.4 mm clearance holes on the authoritative Ø41 mm rear circle at 45°, 135°, 225°, and 315°. Use 4 x M3 x 12 fully threaded socket-head cap screws with 1 mm washers: 4.0 mm bracket + 1.0 mm washer + 3.2 mm rear cover leaves about 3.8 mm engagement in the 4 mm rear thread. At 6 Nm, equal sharing gives about 73 N tangential demand per rear screw.
- **Connector keep-out:** the bracket leaves the measured 69° rear connector sector open between the upper two rear holes. The mated-plug projection is still unknown; a conservative 25 mm rearward service envelope is assumed for routing and no cross-bracket material is placed in that sector.
- **Second support:** NTN/Koyo-equivalent **6800-2RS**, 10 x 19 x 5 mm, on a Ø10 x 8 mm hardened-steel journal. The nominal 6800 dimensions, 5 g mass, 1.83 kN dynamic rating, and 0.925 kN static rating are reported by KG Bearing India; source: `https://kgbearing.com/pdd/deep-groove-ball-bearing/single-row-deep-groove-ball-bearing/6800`.

### Load path and checks

The fixed link reacts through the rear Ø41 mounting circle into two side arms that clear the Ø46.6 mm envelope, then into the forward bearing housing. The moving link reacts through the output hub, steel journal, and 6800 inner ring. The modeled support-bearing center is **48.4 mm** forward of the actuator rear face (`29.45 - (-18.95) mm`). For the 100 N at 100 mm case, using `R = F + M / span` gives about **307 N** at the outer support (`100 + 10 / 0.0484`), well below the cited 0.925 kN static bearing rating. This is a static analytical screen, not a fatigue, shock, pocket-creep, or FEA result.

The circular stop pads use a 20 mm radius and Ø6 mm contact pads. The moving pad has a modeled 3.4 mm surface gap at 100°; its center-to-center distance equals the 6 mm pad diameter at **110°**, where it reaches the fixed pad. The `knee_prelimit_check.kcl` (100°) and `knee_limit_check.kcl` (110°) renders show the intended pre-limit clearance and end-stop contact. Neutral (0°), low-range (30°), crouched (65°), mid-range (90°), pre-limit (100°), and end-stop (110°) renders show no visible thigh/shin/module interference. This is not a continuous collision sweep or a physical validation.

### Mass impact

`kcl_physical_analysis` with PETG density 1.27 g/cm³ reports 16.114 cm³ / 20.465 g for all modeled knee-module solids, and 8.255 cm³ / 10.483 g for the legacy yoke under the same uniform-material assumption: a **+9.98 g per-knee CAD-solid delta**, or **+79.9 g across eight**. That uniform comparison is only a geometry metric because it treats steel parts as PETG.

| New knee component | Estimated mass per knee | Eight-joint equivalent | Basis |
|---|---:|---:|---|
| Printed hub, rear bracket, ties, and stop pads | 18.37 g | 146.9 g | KCL volume after removing modeled steel volumes, PETG at 1.27 g/cm³ |
| 6800-2RS bearing | 5.0 g | 40.0 g | Catalogue value |
| Ø10 x 8 mm steel journal | 4.93 g | 39.5 g | Modeled volume, steel at 7.85 g/cm³ |
| Output/rear M3 fasteners and washers | 6–7 g | 48–56 g | Hardware allowance, not measured |
| **Complete module estimate** | **34–35 g** | **272–280 g** | Analytical estimate |

Only the two knees are changed in CAD. The defensible eight-joint replacement comparison is the uniform-material KCL result: +79.9 g, which already reaches the upper end of the 40–80 g headroom. The 272–280 g figure is an absolute complete-module estimate, not an additive robot delta, because the legacy yoke used a nonphysical bearing placeholder and has no resolved fastener/metal mass. A wider rollout is therefore not approved until the legacy and new joint hardware are reconciled in one measured mass model.

### Remaining open risks

No hardware exists. The rear plug projection, bearing-pocket print accuracy and creep, layer strength at the arm roots, actual bearing preload/fit, journal retention, actuator output-bearing load rating, fatigue, cable bend radius, and stop impact durability remain unvalidated. The model contains no detailed connector, screw, washer, thread, or cable geometry beyond the functional holes and interfaces.

## Carbon-tube link interface — August 28, 2026

### What changed

The thighs and shins used to end in solid printed blocks that sat against the
cut ends of the carbon tubes and held them with nothing whatsoever. That was
priority weakness 3 above. Each block is now a real joint: two square pockets
16 mm deep that the tubes bond into, a transverse M3 through-bolt per tube with
a captive nut behind it, and a bleed hole through each pocket floor.

The two files that build the links were also merged. `tube_link.kcl` now holds
the whole construction and `thigh.kcl` and `shin.kcl` are three-line wrappers
that pass in the tube spacing — 9 mm half-spacing for the thigh, 7.5 mm for the
shin. About 260 duplicated lines went away with no change in what either file
exports.

### The interface

| Feature | Value | Why |
|---|---|---|
| Pocket section | 8.3 mm square | 8 mm tube plus 0.15 mm per side, a bondable slip fit |
| Pocket depth | 16 mm | Two tube widths; 531 mm² of bond area per tube end |
| Anti-rotation | the square section itself | No extra geometry needed |
| Clamp bolt | M3 x 20, one per tube per end | Backs up the bond; passes through the tube, which is drilled at assembly |
| Nut | M3 hex in a 5.6 x 5.6 x 2.6 mm trap on the rear face | A hex nut can only turn about two degrees in it |
| Nut seat | 3 mm of PETG | Thinner creeps under a steel nut |
| Bleed hole | Ø2.5 through the floor | Lets air and surplus adhesive out, and shows the tube has bottomed |
| Block | 32.3 x 19.5 x 22 mm thigh, 29.3 x 19.5 x 22 mm shin | Width follows tube spacing at a 3 mm wall; depth is set by the nut |

The link's overall length is unchanged at 63 mm, which was not a free choice:
the knee's Ø36 moving hub clears the thigh's lower socket by only about 3 mm, so
the pockets had to grow inwards. The exposed carbon between the two socket faces
therefore falls from 47 mm to 19 mm and each tube is cut at 51 mm instead of
47 mm. Bending stiffness does not suffer — the block's solid section is far
stiffer than the pair of tubes it holds — but the link is now mostly printed
part by length.

The 6 mm pocket floor is also set by interference rather than by strength. The
pitch and ankle yokes are Ø54, so their envelope reaches 27 mm from the joint
centre while the socket's outer face is only 21 mm from it; 6 mm of floor is
exactly what keeps the carbon tube outside the yoke.

### Mass impact — this made the robot heavier

| Module | Was | Now | Change |
|---|---:|---:|---:|
| Thigh modules, 2 | 30 g | 66 g | +36 g |
| Shin modules, 2 | 28 g | 60 g | +32 g |

Measured from KCL volume: 22 549 mm³ of PETG per thigh pair and 19 975 mm³ per
shin pair at 1.27 g/cm³, plus 2 784 mm³ of carbon per link at 1.6 g/cm³.

That is **about 68 g added** against a checklist item asking to recover 100-150 g,
and it should not be waved away. It is the price of turning four decorative
blocks into four joints, and most of it is recoverable: the blocks are solid
slabs with a 6 mm floor and no ribbing at all. They are now the largest single
piece of removable material outside the torso and belong in the same ribbing
exercise. The alternative — dropping the captive nut and tightening a bare nut
with a spanner inside the leg — would save about 34 g and is not worth it.

### The interference nobody had noticed

Every link socket shares space with the actuator next to it. The arithmetic is
simple: the joints are 105 mm apart, the link module is 63 mm long, so each
socket's outer face sits 21 mm from the joint centre — inside the Ø46 actuator,
which reaches 23 mm. The thigh's upper socket and the shin's lower socket also
pass through their yoke's cross strap, which spans 23 to 27 mm from the joint
centre across the full yoke width.

This predates this change and is not made worse by it — the socket's outer face
has not moved, only its width, by about 1.2 mm each side. It is recorded now
because the deeper pocket made it obvious. It cannot be fixed by shortening the
link: clearing both the actuator and the yoke strap would leave a 51 mm module
with 7 mm of exposed tube. The socket has to stop being a free-floating block
and become the joint's mounting boss, which is the same open item as bolting the
links to the joints at all.

### An engine quirk worth remembering

The Zoo engine refused the bleed holes with "cannot handle this 3D subtraction
yet" as long as they were blind cylinders ending inside the block. Cutting the
full block height instead — the lower part of the cylinder falls inside the
pocket, which is removed afterwards, so the finished part is identical — is
accepted. Mock execution passed in both cases, which is a reminder that mock
execution does not exercise the booleans.

### Verification

`main.kcl`, `pose_check.kcl`, `knee_limit_check.kcl` and `knee_prelimit_check.kcl`
all mock-execute and all execute on the engine after the change, and the project
lints and formats clean. The neutral, crouched, 100° and 110° scenes were
rendered and show the new sockets clearing the knee bracket in all of them. This
is visual and arithmetic evidence in the reviewed poses, not a swept-volume
collision proof.

## Stressed-shell rebuild — August 28, 2026

The skeleton described everywhere above has been replaced. The carbon tubes,
their bonded sockets, the placeholder pitch yoke and the separate knee bracket
are all gone; `PLAN.md` carries the reasoning and the phase plan, and this
section records what the robot now is.

### The architecture in one paragraph

Each limb is a closed printed box, 30 x 30 mm with a 2.4 mm wall, that carries
the load itself. Every one of the eight joints is the same pair of parts: a
stator clevis on the limb above, straddling the actuator and anchored on its rear
4 x M3 Ø41 pattern, and a rotor hub on the limb below, bolted to the 6 x M3 Ø24
output circle and piloted on the Ø30 register. The clevis reaches past the
actuator to a metal-seated 6800-2RS that takes the moment off the motor's own
bearing. The actuators sit in open clevises, exposed front, back and below, so
they still radiate.

### Why the shell, in numbers

The old pair of 8 x 8 mm tubes gave **467 mm⁴** in the sagittal plane, because
both tubes sat on the centre line and neither contributed to the other's
fore-aft stiffness. The link was stiff side-to-side and floppy in the plane a
walking leg is actually loaded. The closed box gives **33 894 mm⁴** — 73 times as
much — for 29.5 g per 105 mm of link, and it spans the whole bay instead of
63 mm of it. Tip deflection at three times body weight in a 45° crouch is
0.13 mm and the slope is 0.10°, both far inside the joint clearances.

### The shape is set by the knee, not by the beam

The section wants to be deeper than wide, because sagittal loads dominate. It
cannot be. The shin has to fold against the thigh's saddle, and a deeper shell
reaches it sooner: at 34 mm deep the shin's rotor arm fouls the saddle at
**108.5°**, inside the 110° commissioning limit. At 30 mm the first contact moves
to **112.8°**, which makes the structure a backstop rather than a premature stop.
So the section is square, and `shellDepth`, `jointKeepOut` and `bridgeHeight` are
now coupled to the knee's travel. Change any of them and re-run
`knee_limit_check.kcl`.

There is still no *designed* hard stop. 112.8° is structure meeting structure,
which is a backstop, not a stop, and a pad at 110° on every joint is open work.

### What the actuator forces

Worth writing down because it explains the shape of every joint on the robot: the
actuator offers a grip on its rear face and a drive on its front face and nothing
in between, and nothing can pass through it. So the stationary side has to reach
around the body to support the moving side, and the moving side is necessarily a
single plate on the output face. Every joint is that same asymmetric shape, and
no rearrangement avoids it.

That is also why both legs are built identically rather than mirrored. The only
asymmetry is which side of the actuator the hub sits on, and since it is forced,
mirroring buys a symmetrical silhouette at the cost of doubling the number of
distinct printed parts. On a printed robot that trade is the wrong way round.

### Mass

Measured from the CAD at PA12-CF's 1.06 g/cm3, which is lighter than the PETG it
replaces: limb 48.3 g each, hip carrier 39.8 g, foot 61.6 g including its sole,
torso 152.5 g with its new hip mounts. Printed structure totals **549 g**, and
the whole robot comes to about **2.21 kg** against a 2.3 kg ceiling.

That ceiling is not a preference. Inverting the single-leg static model above,
the knee can hold `0.7767 / sin(θ/2)` kilograms on its 0.8 Nm continuous rating,
so 2.21 kg buys a sustained-load knee limit of about **41°**. Mass and crouch
depth are the same decision. The continuous rating binds before the peak does —
allowing three times body weight for landing against the 3 Nm peak gives a
ceiling 25 per cent higher at every angle — so the 6 Nm structural target is
never the constraint.

### Two engine limitations found while building

Both are worked around in the code, and both would have gone unnoticed on mock
execution, which does not exercise the booleans.

- **Blind pockets cut from a large combined solid are rejected.** Every cut is
  now made on the simple body it belongs to before anything is unioned.
- **A union of two hollow boxes meeting at right angles is rejected.** The hip
  carrier and the torso hip mounts are therefore left as interpenetrating
  bodies, the same fallback already recorded above for the foot frame. Confirm
  the slicer merges coincident shells before printing either.

### Verification

`main.kcl`, `pose_check.kcl`, `knee_limit_check.kcl`, `knee_prelimit_check.kcl`
and the new `limb_check.kcl` all mock-execute and all execute on the engine after
the rebuild, and the project lints and formats clean. Neutral, crouched, 100° and
110° scenes were rendered. This is calculation and single-pose evidence, not a
swept-volume proof, and the stiffness case rests on arithmetic until a printed
box coupon is measured.

---

## Pelvis, foot and the poses nobody had drawn — August 28, 2026

Phases 4 and 5 of `PLAN.md` are done, and the two missing regression poses now
exist. Three things came out of it that change decisions rather than just
geometry.

### The reserved battery could never have been built

Before touching the torso, the payload envelopes were checked against the
actuators for the first time. The battery reservation, 92 x 34 x 32 lying
across the torso, sat **21 mm inside both hip roll actuators**. The controller
board clipped them by 13 mm as well, and the IMU was buried inside the
controller board.

This was not a modelling slip; it is forced by the kinematics. The roll axis is
at 301 mm, so a Ø46 actuator necessarily fills 278 to 324 mm at |x| between 25
and 71, and its clevis cheeks reach in to |x| = 22. Nothing 92 mm wide fits
across the torso below 337 mm, and there is not enough height above that to
stack a battery on top of the boards.

So the layout follows the space the actuators leave. The battery is now
38 x 62 x 46 standing in the keel between them -- 108 000 mm3 against the
100 000 originally reserved, so no capacity is lost. The controller and the
optional SBC lie flat above the hip saddles; the IMU sits low and central on the
shell floor, which is where an IMU wants to be anyway.

### No off-the-shelf pack fits, and the battery mass is the budget's weak point

The keel's longest inside dimension is 63 mm. Every common 6S brick is 70 to
110 mm long, and even a single 18650 cell is 65 mm, so **the pack cannot be
bought as a brick** -- it has to be assembled from pouch cells. Six 1300 mAh
cells make a 6S1P block of roughly 45 x 32 x 39, about 190 g and 29 Wh, which
drops into the envelope with room to spare.

That 190 g is also the figure the mass budget assumes, and it is the number to
watch. The bay would physically hold 126 000 mm3, but capacity costs mass at
about 6.6 g per watt-hour:

| Pack | Mass | Energy | Robot total | Against the 2 300 g ceiling |
|---|---:|---:|---:|---:|
| 6S1P, 1300 mAh | 190 g | 29 Wh | 2 295 g | 5 g under |
| 6S1P, 2000 mAh | 295 g | 44 Wh | 2 400 g | 100 g over |

So the robot can carry about half an hour of the actuators' continuous draw, and
buying more runtime means finding the mass somewhere else. Until the coupon says
how much can be ribbed out, 29 Wh is the working figure.

### The pelvis, and what it is worth

The torso is one closed shell now: a keel between the actuators from 274 to
328 mm, and a full-width box above them from 325 to 380 with a removable cover.
The battery tray, four corner posts, two cover rails and the hip beam are gone.

The old hip beam offered 14 x 8^3/12 = 597 mm^4 in roll. The keel is a channel --
a 68 x 3 floor flange over two 2.4 mm webs 51 mm deep -- and works out at about
98 000 mm^4 about its own centroid, roughly **165 times as much**, with the shell
above adding to it again. Like every other section figure here that is
arithmetic, and it inherits whatever the Phase 1 coupon says about modulus.

The hip clevis cheeks are Ø52 discs on the leg axes, so the robot is 148 mm
across at the hips against a 118 mm torso. That is unchanged from the skeleton
and is deliberate: the joints are the visible hardware.

### The foot

The nine overlapping rails are gone. The foot is a shallow open-topped tray --
2.4 mm floor, continuous perimeter wall, two transverse ribs under the ankle
spreader and a longitudinal rib tying heel to toe. Priority weakness 4, the
landing load going into printed riser roots, is closed.

The top is open on purpose and it is a printing decision. The foot prints
sole-face-down, which puts the layer lines across the landing load; in that
orientation an open top needs no support and a closed one would have to bridge
60 mm. The floor and the perimeter wall carry the load; a top skin would add
mass at the neutral axis and buy little.

### Mass: the headroom is gone

| Part | Each | Count | Total |
|---|---:|---:|---:|
| Limb, thigh or shin | 48.3 g | 4 | 193 g |
| Hip carrier | 39.8 g | 2 | 80 g |
| Foot, tray, sole and pads | 76.6 g | 2 | 153 g |
| Pelvis and torso shell with cover | 189.0 g | 1 | 189 g |
| **Printed structure** | | | **615 g** |
| Actuators | 150 g | 8 | 1 200 g |
| Bearing, journal, carrier | 16.3 g | 8 | 130 g |
| Fasteners | | | 60 g |
| Electronics and wiring | | | 100 g |
| Battery, 6S1P pouch pack | | | 190 g |
| **Total** | | | **about 2 295 g** |

That is **5 g under the 2 300 g ceiling**, and it buys a sustained-load knee
limit of 39.6 degrees, which still meets the 40 degree target but no longer with
anything to spare. The pelvis cost 37 g and each foot 15 g over what they
replaced, which is the honest price of closing both sections. Ribbing and
lightening have gone from a nice-to-have to a requirement, and they cannot be
sized until the coupon is measured.

### The ankle and hip roll cases, modelled at last

Both were flagged as never having been checked. They now have numbers, on the
2 295 g robot.

**Ankle.** In single support it carries 2 219 g. On the 0.8 Nm continuous
rating the centre of pressure may travel only **36.8 mm** from the axis, which
is 56 per cent of the 66 mm to the toe and 75 per cent of the 49 mm to the heel.
A full toe load is 1.44 Nm -- 1.8 times continuous, but less than half the 3 Nm
peak, so push-off is fine and it is *standing* on the toe that is not. The foot
is the right size; only its continuous working area is smaller than it looks.

**Hip roll.** Standing on one leg, the roll actuator carries 1 623 g at a 48 mm
lever, which is 0.764 Nm, or **96 per cent of the continuous rating**. Static
single-leg stance with the body centred is therefore not sustainable. Moving the
centre of mass 10 mm toward the stance foot -- about 2 degrees of lean -- brings
it to 75 per cent. That is what a real biped does anyway, but it needs to be in
the controller rather than assumed.

### Hip roll inward travel is seven degrees, not twenty-five

`roll_limit_check.kcl` renders it. The roll axis is 257 mm above the ankle, so a
degree of roll moves the foot 4.5 mm sideways, and the two feet are 96 mm apart
on a 65 mm width -- 31 mm of air:

| What touches | Clearance | Contact |
|---|---:|---:|
| The two soles | 31 mm | **6.9 deg** |
| The two shin shells | 66 mm | 14.9 deg |

With the other leg standing neutral, inward roll runs out at seven degrees. The
plus or minus 25 degree commissioning limit is only meaningful outward, where
nothing obstructs the foot at all. This does not stop the machine walking -- the
swing leg is lifted, and a lateral lean rolls both hips the same way and never
closes the gap -- but inward roll against a planted neutral leg has to be handled
as a fault case rather than as available travel.

### The mirrored walking stance

`walk_pose_check.kcl` is the pose the suite never had: mid-stride, both feet
flat, left leg leading at 25 degrees of hip and 40 of knee, right trailing at
-10 and 17.5. Both legs must drop the hip equally for the feet to be coplanar,
so the trailing shin angle follows from the leading leg's reach.

No interference anywhere. The finding is at the ankle: the trailing ankle sits
at 27.5 degrees against a 30 degree limit, so **a longer stride runs the
trailing ankle out of travel before anything else moves**. 84 mm is close to the
usable maximum for this stance.

### Hard stops: why they are not in the joint module

Still not done, and the reason matters. The shared clevis cannot carry them.
Everything within Ø52 of the joint axis is either the actuator body (radius 23),
the bearing carrier, or a 3 mm printed cheek; a pin-in-slot through that cheek
would shear under a full-torque runaway and give false confidence. Widening the
saddle chord can stop the knee at 110 degrees because the limit is near the
structural contact at 116, but the same trick cannot reach 25 or 30 degrees.

The stops therefore belong on the **limb parts**, not in `joint.kcl`: a pad on
the pelvis for hip roll, on the thigh for hip pitch, on the shin saddle for the
ankle. Those have room and material. Each one needs its own rendered pose at the
limit, which is why the two poses above had to come first.

### Two more engine notes

- A blind **cylindrical** pocket in the torso shell is rejected, in either
  order, and unioning the ports into the cavity tool first does not help. A
  blind **rectangular** pocket in the same place is accepted. The cable ports are
  slots for that reason, which suits a moulded connector better anyway.
- A hole through a stepped solid is fine, but it must exit both ends. The cover
  screw cutters were originally short enough to stop inside the lip, which is
  the blind-pocket case again.

### Verification

`main.kcl`, `pose_check.kcl`, `knee_limit_check.kcl`, `knee_prelimit_check.kcl`,
`limb_check.kcl`, `walk_pose_check.kcl` and `roll_limit_check.kcl` all execute on
the real engine. Neutral, walking, roll-limit and foot geometry were rendered and
inspected. Project lints and formats clean.

`calculate_kcl_physical_properties` returned a centre of mass and a bounding box
for the foot that are inconsistent with the rendered geometry -- the bounding box
was 173 mm in y for a 115 mm foot. Volume and mass agreed with hand calculation
and are the only outputs from that tool trusted here.

---

## The robot is tethered now — August 28, 2026

The on-board battery is gone. 24 V and CAN come in on a single umbilical from
the bench supply, and the keel that was drawn as a battery bay is a power-entry
bay instead.

This was a decision, not something the geometry forced, but the geometry had
been pushing the same way all day. The keel's longest inside dimension is 63 mm,
every common 6S brick is 70 to 110 mm long, and a single 18650 cell is 65 mm, so
an on-board pack could never have been bought -- it would have had to be built
by hand from six pouch cells. And the 190 g that pack weighed was the entire
mass headroom.

### What it buys

| | With a battery | Tethered |
|---|---:|---:|
| Total mass | 2 295 g | **2 165 g** |
| Under the 2 300 g ceiling | 5 g | **135 g** |
| Sustained-load knee limit | 39.6 deg | **42.0 deg** |
| Ankle CoP travel on continuous | 36.8 mm | **39.0 mm** |
| Hip roll, single support | 96 % of continuous | **88 %** |

The hip roll line is the one to notice. That joint holds up everything above it,
so torso mass is exactly what it carries, and taking 130 g out of the torso
helps it more than it helps anything else. Single-leg stance with the body
centred is still not comfortable -- it wants about 7 mm of lean, roughly 1.4
degrees, to sit at 75 per cent -- but it is no longer sitting on the rating.

### What it costs, which is the part that matters

**Dropping the battery is not simply minus 190 g.** The pack was also the DC
bus's energy store and the only thing on board that could absorb regeneration.
Eight backdrivable actuators peak near 32 A together, they push current *back*
whenever a limb is driven by gravity or by the ground, and a bench supply
generally cannot sink current at all. A tether adds resistance and inductance
between the robot and whatever is at the far end -- about 0.8 V in each 14 AWG
conductor at 32 A over 3 m, so 1.6 V round trip off a 24 V bus.

So the low-ESR bulk capacitor bank that `BOM.md` had as "TBD, after actuator
bench tests" is now required hardware, and it has moved to a red risk. The keel
reserves it with the main fuse and the tether's terminal as one power-entry
block, 38 x 62 x 30, reachable from underneath. **It has not been sized** --
that needs the measured bus excursion and the real tether length -- so the 60 g
in the mass table is an allowance for the bank, fuse, terminal and clamp
hardware together, not a measurement. It is the softest line in the budget.

The second cost is a rig requirement rather than a robot one, and it is easy to
forget: **the umbilical has to be carried on a boom or a spring balancer.** An
unsupported cable hangs a moving, unmodelled load on a 2.165 kg biped whose hip
roll actuator is at 88 per cent of continuous in single support. Not designed
yet.

### Where the tether enters, and why there

The back of the **keel**, not the back of the shell. Two reasons. Down there the
pull acts within about 10 mm of the hip roll axis instead of at the top of a
106 mm lever, so tension on the cable is close to a pure force on the pelvis
rather than a moment about it. And it arrives beside the power-entry block
instead of having to cross the electronics stack, which at the top of the shell
it would have had to do -- the SBC envelope leaves only 2.6 mm behind it.

Strain relief is a cable tie, not a clamp and not a threaded insert. The tie
goes out through one narrow slot, around the tether inside the keel, and back in
through the other, so a pull is carried in shear by 2.4 mm of wall and never
reaches the terminal. It also keeps every cut on this part rectangular, which is
the only blind pocket shape this engine will take out of the shell -- the same
limitation the cable ports were reshaped for. The slots are cut into the plain
keel blank before the cavity, which is the ordering that worked for the shell.

The cable diameter, 12 mm, is now `tetherCableDiameter` in `parameters.kcl`, and
the entry slot and both tie slots are derived from it. **It is an estimate from
the wire the BOM already specifies** -- two 14 AWG silicone conductors, a 24 AWG
twisted CAN pair and a braided sleeve -- not a measurement of a cable in hand.
Measure the made-up umbilical before printing the pelvis.

### The tether went in on the wrong side first

Worth recording because execution would never have caught it. The entry slot was
first cut at y = +32.8, which put the umbilical in the robot's **front**, between
its shins. It executed on the engine without complaint -- a slot is a slot -- and
only a rendered back-and-front pair showed it.

The sign convention is settled by `foot.kcl`, which puts the rear pressure pads
at y = -40 and the front pads at y = +51, and confirmed by
`walk_pose_check.kcl`, where the leading leg's knee swings to +Y. So **+Y is
forward** and the rear face of the torso is at y = -34. The slot now sits there
and `torso.kcl` carries a comment saying why, because nothing else in the file
made the direction obvious.

Note that Zoo's *front* camera looks at the -Y face, so the view named "front"
shows the robot's back. That is the ordinary CAD convention rather than a bug,
but it is a good way to mislead yourself for ten minutes.

### Verification

All eight models execute on the real engine after the change: `main.kcl`,
`pose_check.kcl`, `walk_pose_check.kcl`, `roll_limit_check.kcl`,
`knee_limit_check.kcl`, `knee_prelimit_check.kcl`, `limb_check.kcl` and
`coupon_box.kcl`, plus `torso.kcl` and `payload_envelopes.kcl` on their own. All
eight mock-execute. The three changed files format and lint clean.

The keel's three new pockets were the thing worth proving, since a pocket in an
already-hollowed shell is the case this engine has refused twice before. Cutting
them into the plain keel blank before the cavity -- the ordering the shell above
already needed -- works, and the rendered pelvis shows the slot and both tie
slots where the arithmetic puts them, just under the shell floor.

### A third MCP failure mode: the cold uvx cache

The Zoo MCP server failed to connect at the start of this session, with a
`CONNECT_TIMEOUT` after 30 seconds. **This is not the billing failure recorded
above, and it is not an authentication problem either.** The server is launched
as `uvx zoo-mcp`, and uvx had no cached copy of the package, so the spawn spent
its whole 30 second budget downloading 53 packages and never got as far as
speaking MCP.

The fix is to warm the cache once from a shell -- running `uvx zoo-mcp` directly
installs it in a couple of seconds thereafter -- and then restart VS Code. Worth
knowing that the diagnosis is visible in the timing: a billing failure comes back
fast and says `auth_token_missing`, while this one simply runs out the clock.

While the session's own MCP link was down, the server was driven over stdio by a
throwaway JSON-RPC client instead, which is how the validation above was done. If
that is ever needed again, the protocol is one JSON object per line: `initialize`,
then a `notifications/initialized`, then `tools/call`. Nothing about it is
special to this project.

One transport flake to expect on longer runs: `execute_kcl` on `main.kcl` came
back once with a `RequestError` against `api.zoo.dev/ws/modeling/commands`. It is
a dropped request rather than a KCL error, and the same file passed on the retry.

---

## Local tooling for the CAD — August 29, 2026

### The KCL interpreter runs here, without the engine and without the MCP server

Zoo publish their KCL interpreter as a Python package, `zoo-kcl`, and the MCP
server is itself built on it. That means mock execution, linting and formatting
need no token, no network and no MCP link at all. `tools/check.py` sweeps every
`.kcl` file in the project in about two and a half seconds, and reports the same
diagnostics the MCP tool does. All 21 files pass, lint clean and format clean.

This matters beyond convenience. Two of the three MCP failure modes recorded
above — the billing rejection and the cold `uvx` cache — leave the project
unverifiable for as long as they last. They no longer do: only geometry needs
the engine now.

Two more scripts sit on the same package and do need the engine, so they are
metered: `tools/mass.py` measures each printed part and rolls the whole robot up
against its ceiling, and `tools/views.py` renders a model from several sides.
Both are also slash commands in Claude Code, as `/check`, `/mass` and `/views`.

`views.py` names its views in the **robot's** frame, so `front` is the face the
robot walks towards. That is the opposite of Zoo's camera named "front", which
is what let the tether entry go in on the wrong side.

### The current tree is 2 200 g, not 2 165 g

The first real run of `tools/mass.py` measured 649.4 g of printed structure
against the 615 g in the table above, putting the robot at **2 199.8 g with
100.2 g of headroom** rather than 2 165 g with 135 g.

Almost the whole difference is in the limbs: 59.6 g each against the 48.3 g
recorded, or +45 g across four. The hip carrier, foot and torso have all moved
by a gram or two in the other direction. The working tree carries uncommitted
changes to `joint.kcl`, `limb.kcl` and `hardware.kcl`, so the likely explanation
is that in-progress work has added mass that was never measured — but that is
inference. The committed geometry was not measured for comparison, because doing
so costs another five engine runs.

`tools/mass_baseline.json` now holds these figures, so the next run reports the
delta from here. The tables in `PLAN.md` and `BOM.md` still say 2 165 g and
should be corrected once the limb work settles.

### A fourth engine failure mode: two connections per user

`Too many active connections, only 2 allowed per user` came back from three
separate attempts while the render and mass scripts were being tested. It is not
a KCL error, not a billing error and not an authentication error: something else
is holding an engine connection — Design Studio, an MCP modeling session, or an
earlier script whose connection has not been released yet. Close one and retry.

Worth knowing too that the full assembly is slow: `main.kcl` took over two
minutes to execute and snapshot. That is normal, not a hang.

### Where the traps are written down now

The engine refusals this log had accumulated in five separate places — blind
cylindrical pockets, holes that must exit both ends, pockets before hollowing,
unions of hollow boxes meeting at right angles, and the fact that mock execution
never exercises any of it — are collected in `docs/KCL_GOTCHAS.md`, along with
the orientation convention and the failure messages above. Add to that file when
the engine refuses something new.

## The limbs move into the output plane — August 29, 2026

The thigh and the shin no longer reach out to the actuator. Their shell is
shifted outboard by `shellOffsetX` = 9.95 mm until its outer wall lies in the
output plane, so the plate that bolts to the rotor is that wall carried on down
to the disc. The arm and the bridge are gone, and with them the whole business
of walking the hub's offset back to the limb centre line.

The prompt was a photograph of somebody else's leg, in which the links are flat
plates bolted straight to the motor faces. The question it raised was whether
this design's bridge existed for a reason or only because the shell had been
centred on the joint axis out of habit. It was habit.

### What it buys

A limb is **46.3 g**, against 48.3 g before any of this month's joint work and
59.6 g with the forked rotor on it. The whole robot is **2 146.7 g** with
**153 g** of headroom, and the sustained-load knee limit is **42.4°** against a
40° target. `tools/mass.py` measures it; the numbers above are that script's.

The load path is also better. The joint load now enters the shell wall as
in-plane shear instead of as a couple across a cantilevered slab, and the plate
is 30 mm deep where the old arm was 25.2, so its lateral section modulus rises
from 151 to 180 mm³.

### What it costs

Lateral symmetry. The actuator hangs entirely inboard, so a limb sits 9.95 mm
off its own joint axis, and since both legs are built identically rather than
mirrored — see *What the actuator forces*, above — both shift to the robot's
right. The **gap** between the two legs is unchanged, so `roll_limit_check.kcl`
is unaffected, but the robot is wider on its right than on its left and the left
limb passes closer to the keel. It clears: the thigh's shell stops at z = 230
and the keel starts around the hip pitch axis at 254.

The knee fold is unchanged at the limit that matters. The old bridge was already
30 mm deep and was already the first thing to touch the thigh's saddle; the new
plate is 30 mm deep in the same place. `knee_limit_check.kcl` renders clean at
110°, and a 2D sweep of the rotating rectangles against the saddle puts first
contact at the same angle for the old bridge and the new plate. The 25.2 mm arm
was never the limiting body, which means the note in `parameters.kcl` attributing
the 112.8° contact to the arm was attributing it to the wrong part.

### The forked rotor came off

`rotorYoke` and `rearJointHardware` are still drawn but nothing imports them.
The straddled joint was curing the second-weakest link.

Work the numbers for a sideways force at the foot. At the hip pitch the lever is
254 mm, and the printed section that has to carry it is the rotor plate, 6 mm
thick against 30 mm deep, so Z = 180 mm³ and σ = 1.41 MPa per newton at the
foot. PA12-CF gives about 75 MPa in the print plane and about 30 across the
layers, so the plate breaks at **53 N** printed one way and **21 N** printed the
other. The limb shell, by comparison, would take 267 N, and the clevis's two
cheeks acting as a pair are stiffer still: the plate is the weak link by more
than a factor of twelve.

Now the bearing. Without the fork the rotor's two supports — the actuator's own
output bearing and the 6800 in the front cheek — sit about 20 mm apart on the
same side, so a foot force is amplified about 7.5× as a couple. At 21 N, the
force that breaks the plate, the 6800 sees 260 N, which is under a third of its
static rating. **The printed part fails first, comfortably.** Straddling the
joint to protect the bearing was therefore fixing the wrong thing, and the 105 g
it cost is better spent elsewhere or not at all.

That is not a clean bill of health for dropping it. It rests on the plate being
sound, and the plate's margin is thin the way it is loaded least: in service the
lateral ground reaction is perhaps 6 N, which is 9× margin printed the good way
and 3.5× the bad way — and against a fatigue limit of a third of ultimate, the
bad orientation is marginal. **Print orientation is worth 2.5× here and costs
nothing**, which makes it the reinforcement to spend first. If more is needed
after the coupon is measured, 8 mm of plate instead of 6 is another 1.8× for
about 3 g a joint, growing outboard because the actuator blocks the inboard side.

The reason the yoke is kept in the file rather than deleted is that all of this
still assumes the DM-J3507's own output bearing will take the moment, and DAMIAO
have not been asked. That question is unchanged and still open.

### One more thing the engine will not do

A union whose two bodies share both of their faces in one axis is refused. The
plate is exactly `rotorHubThickness` and sits exactly where the disc sits, so
both x-faces coincide and `union([outputDisc(), plateRaw])` fails; the arm it
replaced was tolerated because only its outer face was shared. The limb places
the disc and the plate as separate interpenetrating bodies instead, which brings
it to four. Recorded in `docs/KCL_GOTCHAS.md`.


## The legs go flat, and one of them gets mirrored — August 29, 2026

The limbs are no longer beams between two clevises. Each is a plate lying in one
plane: a Ø52 disc bolted flat to one actuator's rear cover, a Ø36 disc bolted to
the next actuator's output, and a channel waist between them. Nothing reaches
around an actuator any more, so the clevis, the saddle, the closed shell and the
far bearing at the knee and the ankle are all gone.

### The knee actuator is turned round, and that is what makes it work

Follow the chain. The thigh's upper end meets the hip pitch rotor; with the knee
actuator reversed, its rear cover now faces the same way, so the thigh's lower
end meets that — one plate, one plane. The shin's upper end meets the knee rotor
on the far side, and the ankle actuator below it presents its rear cover the same
way, so the shin is a plate too, in the opposite plane. Thigh and shin end up in
disjoint slabs of X on either side of the knee actuator.

Every attachment is either the six-bolt Ø24 output circle or the four-bolt Ø41
rear pattern. Both are confirmed twice over against the vendor 2D print and the
STEP. The Ø41 *front-housing* pattern that `parameters.kcl` carries with no
provenance is not needed by any of it, which is worth saying plainly, because
building on it would have been building on a guess.

### What it is worth

| | Before | After |
|---|---:|---:|
| Limb, each | 46.3 g | **32.1 g** |
| Printed structure | 596 g | **539 g** |
| Whole robot | 2 147 g | **2 025 g** |
| Headroom under 2 300 g | 153 g | **275 g** |
| Sustained-load knee | 42.4° | **45.1°** |
| Bearing/journal/carrier sets | 8 | **4** |

Two things come free with it. The knee fold limit stops being structural: thigh
and shin are in different planes and cannot touch, so the 112.8° contact that
set `shellDepth` is simply gone. And the flanged bearing carrier — the only
non-commodity item on the BOM — drops from eight to four.

### The waist is a channel, and that is the support the plate needed

A bare 6 mm plate is sixty times softer sideways than the closed box it replaces:
`Iyy` 540 mm⁴ against 33 894, which is about 7.7 mm of sway at the hip in single
support. Two flanges, 12 mm out and 4 mm thick, pointing inboard towards the
joint axis, take that to **9 468 mm⁴ and 0.44 mm** for about 5 g a limb. In the
sagittal direction the same section gives 29 852 mm⁴, within twelve per cent of
the box. The flanges point inboard because that space is empty: each actuator
body reaches only 29.5 mm from its own joint centre and the flanges stop at 25.

What the channel does *not* fix is the short unflanged run where the waist meets
each disc. That section is the bare plate, 6 × 30, and it remains the weakest
printed thing on the robot at 21 N sideways at the foot across the layers or
53 N in the print plane. Unchanged from the previous build, and print
orientation is still worth 2.5× on it for nothing.

### What it assumes, and it is not confirmed

Nothing straddles the knee or the ankle now, so the actuator's own output bearing
takes the joint moment. The plate sits about 22 mm off the joint axis, so every
load down the leg arrives as an overhung moment: **0.45 Nm standing on one foot,
about 1.35 Nm landing at three times body weight.** DAMIAO have not been asked
whether the bearing will take it. The decision was to proceed on the assumption
that it will, and to send them those two numbers rather than the open-ended
question the project had been sitting on. `rotorYoke` and `rearJointHardware`
remain drawn with nothing importing them if the answer comes back badly.

### The robot is mirror-symmetric now, which reverses an earlier decision

Decision 5 in `PLAN.md` was that both legs are built identically rather than
mirrored, on the grounds that mirroring doubles the number of distinct printed
parts. That was right when the only asymmetry was which side of an actuator a
hub sat on. It is wrong now: a flat limb sticks out 25 mm to one side, and two
identical legs put the thigh outboard on one and inboard on the other.

So the legs are mirrored, and the count of distinct prints barely moves. Both
leg segments are 105 mm, so **the right thigh and the left shin are the same
part**, and so are the left thigh and the right shin — two limb prints, exactly
as before. The foot and the hip carrier do become a left and a right, which is
two extra prints on the whole robot.

Handedness in the models: the pitch-axis actuators drive towards +X on the right
leg's hip pitch and ankle and towards -X on its knee, and the left leg reverses
all three. The hip roll is unaffected, its axis being fore-and-aft.

### Mirroring in KCL

`mirror3d` **copies rather than transforms**: it leaves the original standing in
the scene, so a mirrored part measures double unless the source is disposed of.
`hide()` on the source is enough — the mirrored body survives and the hidden one
drops out of both the render and the mass. `delete()` also works but lints as
experimental. `scale(x = -1)` is not a mirror; it appears to reflect about the
body's own centroid and leaves it where it started.

Spinning a part 180° about Z is a true mirror **only if the part is symmetric
fore and aft**, which the limb is not: the stator plate's connector relief sits
on one side. So the limbs are mirrored properly rather than spun.


## Four bolt holes that were never there — August 29, 2026

Three defects, all of the same kind: a body drawn in another body's plane, and a
bolt pattern underneath it.

**The knee and ankle bolts.** The flat limb's waist ran symmetrically to 38.5 mm
either side of the limb centre. At the stator end that put its corner 0.7 mm from
the two rear bolts nearest the waist, filling 46 % of each hole and leaving a
1.2 mm crescent no screw could pass. The waist is now derived from the bolt
circle at that end and stops at 34.6 mm, which leaves 1.7 mm of wall to each hole
and 0.4 mm round the cap head, and costs nothing: the Ø52 plate is still 38 mm
wide there, so the section never narrows. The rotor end is unchanged at 38.5 mm,
because it only just reaches the Ø36 disc as it is and the nearest counterbore
clears it by 0.6 mm. The waist is therefore no longer symmetric about the limb
centre, and each end is now set by the pattern it has to miss.

**The stator plate's bore.** It inherited the clevis's Ø30.2 lightening hole. On
a 3 mm cheek that is 0.6 g for nothing; on a 6 mm plate it left 14.8 mm of the
available 45 mm of width at the joint axis, and 266 mm⁴ out of plane against the
540 mm⁴ of the bare waist this file already calls the weakest printed thing on
the robot. It is filled: 810 mm⁴ for 4.6 g a plate. Nothing needed it — the rear
cover is a flat static face the plate lands on, and the knee and ankle have had
no far bearing since the clevis went. The bore stays on the clevis, where it is
cheap and is still the way a carrier could be bonded in.

**The rotor hub's output pattern, which is the serious one.** `rotorHub` unioned
its arm onto the output disc after the disc had been drilled. The arm lies in the
disc's own plane and ran up to the joint centre, so it filled four of the six
M3 holes: the pair below the axis buried outright, the pair on it half filled
with their counterbores ruined. Two usable bolts out of six, side by side on a
12 mm chord, on the ankle and hip roll joints — the ones carrying the actuator's
whole output torque. It had been like that through several rebuilds. Nothing in
the repository could see it: mock execution does not evaluate booleans, the
engine built it without complaint, and the mass was plausible. It was spotted by
eye in Design Studio.

Every way of drilling through the overlap was refused, and one was worse than
refused — an oversized relief in the arm was *accepted* and came back with five
holes open and one filled. Those are recorded in `KCL_GOTCHAS.md`. What works is
not to overlap: the arm now seats below the bolt circle, its top corners just
inside the disc's edge at 52°, 14.2 mm below the axis and 0.8 mm clear of the
counterbores. Its top face has to sit wholly inside the disc or the union fails
outright, and that is what sets its width — 21.2 mm where the disc is 22.2. The
arm gives up 4 mm of width for six bolts instead of two, which is not a close
call, but it is a real reduction in a load-carrying member and is worth
re-checking if the ankle is ever found wanting.

**The hip connector relief.** Unrelated, found in the same pass. The limb plate
had been truncated on the connector chord at 19 mm since it was drawn; the clevis
never was, so both hip rolls and both hip pitches had a full Ø52 cheek sitting
0.3 mm off the rear face and over the connectors. The cheek now takes the same
chord. The plug projection behind it, 8 mm, is an **estimate**, not a
measurement: the manual gives the connectors as an SH1.0 3-pin for supply and CAN
and an SH1.0 8-pin for debug serial, both on 200 mm flying leads, and JST SH
mated housings stand about 3 mm off their header with 28 AWG needing roughly
5 mm to turn. Measure it on the first actuator that arrives.

One thing that follows from the relief and is not settled: `torso.kcl` places
both hip roll clevises with the same quarter turn rather than as a mirrored pair,
so both reliefs face the robot's right — cables exit outboard on the right leg
and inboard, into the torso, on the left. The knees and ankles all face forward
and the hip pitches all face aft, which are both symmetric.

| | Before | After |
|---|---:|---:|
| Thighs, the pair | 64.2 g | **71.8 g** |
| Shins, the pair | 64.2 g | **71.8 g** |
| Hip carriers, the pair | 74.4 g | **71.2 g** |
| Feet, the pair | 149.3 g | **147.2 g** |
| Torso | 187.3 g | **186.2 g** |
| Whole robot | 2 024.6 g | **2 033.4 g** |
| Headroom under 2 300 g | 275.4 g | **266.6 g** |


## The hips get their mirror, and the limbs get their ribs back — August 29, 2026

Four changes, all of them things that were spotted by looking at the model
rather than by anything the tooling reports.

**The left hip roll was never mirrored.** `torso.kcl` gave both hip roll
clevises the same quarter turn about Z, which is a translation of the right one
rather than a reflection, so both rear cheeks carried their connector relief on
the same side of the robot: outboard on the right leg, and inboard, into the
torso, on the left. That is the loose end the previous entry left open. The left
clevis is now `mirror3d` of the right, which is the same thing as installing the
left actuator spun 180 degrees about its own axis so its connector flat faces
away from the keel.

No rotation can do this. Half a turn about the roll axis takes the saddle with
it and puts it underneath; the quarter turn the other way swaps the front and
rear cheeks end for end and would drag the bearing, the carrier's hub and the
actuator round with it. Reflection leaves Y alone, so the front cheek and its
bearing stay forward on both legs and the hip carriers are untouched.

**The keel only ever touched the hip cheeks along a line.** The keel is 44 mm
wide precisely so that its walls land on the Ø52 cheeks, but a flat wall meets a
circle at a tangent and nothing more — a 3 mm line of contact. Above and below
that tangent the cheek's arc curves away and left an open curved triangle, one
under the shell floor and one at the torso's bottom edge, on both cheeks of both
hips. Four of them, and the only path from a hip into the keel ran up through the
saddle and along the shell floor instead.

Each is now closed by a web in its own cheek's plane and of the cheek's own
3 mm, from the keel's inner wall face out to the joint axis, with its outer edge
a semicircle at the actuator keep-out radius. That radius does two things at
once: it laps 2 mm over the cheek, which is enough for a slicer to merge the two
shells, and it keeps 1.8 mm away from the four M3 rear bolt holes on their Ø41
circle. Cut as a plain rectangle minus a cylinder, with the cylinder crossing
the rectangle's outboard edge and clear of the other three — a cutter tangent to
a face is the case this engine refuses.

Verified both ways the previous entry asks for, because the web lives in the
cheek's own plane and would fill the bolt pattern back in if the cut had failed.
The torso rendered on its own, straight down the joint axis, shows the Ø30.2
bores open and all four bolt holes standing; and the torso gained 7.6 g against
7.64 g predicted for the web with its semicircle cut, where a web without it
would have been 19.1 g.

**The rotor arm's fillet was inside the motor.** The corner it fills is between
the arm's inner face, which lies in the actuator's own end plane, and the top of
the bridge, which sits at `jointKeepOut`. A fillet there can only grow into the
gap between those two, and that gap is the one millimetre by which `jointKeepOut`
clears the Ø46 body. At 4 mm it climbed three millimetres past that and cut
about half a millimetre into the bottom rim of the housing over roughly 13 mm of
its width, on both hip rolls and both ankles. It is now 1 mm, which is the whole
of the clearance there is.

The 4 mm was not arbitrary — it closed exactly the 3.95 mm of bridge that
cantilevers unsupported between the hip carrier's connector wall and the arm
root — it was simply sized against the wrong constraint. That span is now left
open, because there is nowhere to put material that is not inside the actuator.

**The limb flanges move outboard, and grow along the limb instead of across
it.** They used to point inboard, into the gap between the plate and the
actuator, which is the one piece of space on the limb that anything else has to
share: the joint hardware and the actuator's own leads both live there. They now
stand on the plate's outboard face, where the only thing they can reach is the
hip carrier's front cheek. Reach drops from 12 mm to 8.4, and the length goes
from a 50 mm band in the middle of the limb to the whole 60 mm span between the
two clearances, with both ends running out into the plate on an arc of the
flange's own reach rather than stopping in a square shoulder.

The section pays for the narrower flange. Sideways, the channel was about
6 800 mm⁴ with a 12 mm flange inboard and is about 3 500 with an 8.4 mm one
outboard, because the shallower flange sits nearer the centroid as well as being
smaller. Covering the whole span rather than its middle half wins a good deal of
that back, but not all of it, so sway at the hip should be expected to be
somewhat worse than the millimetre the old flange bought. Arithmetic, not
measurement, and still never tested on a coupon.

What stops the flange at the rotor end is the hip carrier's front cheek: a Ø52
disc on the hip pitch axis whose inner face is 1 mm outboard of the limb plate.
The flange stops a cheek radius and a millimetre short of that joint centre. It
costs the shin, which has no cheek at its knee end and could have run on to the
waist's own end at 38.5 mm. That is deliberate — the right thigh and the left
shin are the same print, so giving the shin the longer flange would make four
distinct limb parts out of two. Say so if the stiffness is wanted more than the
part count.

Two KCL lessons came out of drawing that profile, both now in `KCL_GOTCHAS.md`:
`arc` always sweeps counter-clockwise from start to end, and `region` needs its
two segments to touch and its `direction` to match the way the outline is
written. Getting either wrong builds a solid without complaint — the first
attempt was a dumbbell and the second was empty.

| | Before | After |
|---|---:|---:|
| Thighs, the pair | 71.8 g | **68.3 g** |
| Shins, the pair | 71.8 g | **68.3 g** |
| Hip carriers, the pair | 71.2 g | **70.5 g** |
| Feet, the pair | 147.2 g | **146.4 g** |
| Torso | 186.2 g | **193.8 g** |
| Whole robot | 2 033.4 g | **2 032.6 g** |
| Headroom under 2 300 g | 266.6 g | **267.4 g** |

The torso's 7.6 g is the four cheek webs, and it is measured with the overlaps
counted twice as `mass.py` always does: the material that is actually new, the
part outside the cheeks and the keel, is about 3 g.


## The limb flanges come off, and what actually carries a fall — August 30, 2026

The flanges were asked for, not diagnosed. They were never introduced to cure a
measured weakness, and when the numbers were finally run they turned out to be
answering a different question from the one that was worrying us.

### A rib is a stiffness feature, not a strength feature

A rib standing proud of a plate adds material away from the centroid, which
raises the second moment. But it also moves the outermost fibre out by nearly as
much, and section modulus — the number that decides whether something breaks —
is the second moment divided by that distance. The two effects very nearly
cancel for strength while compounding for stiffness.

| Flange reach | Area | `Iyy` | Z | Z vs bare |
|---|---:|---:|---:|---:|
| none | 180 mm² | 540 mm⁴ | 180 mm³ | 1.00× |
| 4.2 mm | 213.6 mm² | 1 326 mm⁴ | 207 mm³ | **1.15×** |
| 8.4 mm | 247.2 mm² | 3 472 mm⁴ | 368 mm³ | 2.04× |
| 12 mm | 276.0 mm² | 6 763 mm⁴ | 570 mm³ | 3.17× |

At the 4.2 mm reach they ended at, the flanges were worth two and a half times
the lateral stiffness and fifteen per cent of the strength.

### And they were not where it counts

The weakest printed thing on the robot is the short run of bare plate just under
the thigh's hip-pitch hub, between where the flange had to stop and where the
Ø36 disc begins. The flange stopped a cheek radius short of that joint because
the hip carrier's front cheek stands 1 mm outboard of the plate there — the same
obstacle that stopped a central flange being added at the rotor end.

So the limb's breaking load was **identical with the flanges and without them**:
23.7 N applied sideways at the foot across the layers, 59.2 N in the print
plane. Every gram of flange bought nothing against snapping.

### What the robot can do to itself

**A lateral push cannot break a leg.** Standing on one foot the robot tips at
about 2 N applied at the torso, because the foot is 65 mm wide and the centre of
mass sits at 202 mm — well below the torso centre, because 1 200 g of the
2 089 g total is actuators and they are low. At the tipping point the worst
section sees 4 MPa against 30, better than seven times margin.

**A sideways topple is marginal, and print orientation decides it.** Falling
from one-leg stance releases 2.85 J and arrives at 1.65 m/s. Taking the worst
credible path — foot planted, hip arrested by the torso hitting the floor, the
knee actuator's 150 g swinging between them:

| Floor give | Deceleration | Margin across layers | Margin in plane |
|---|---:|---:|---:|
| 1 mm, hard floor | 139 g | **0.44× — breaks** | 1.10× |
| 2 mm | 70 g | **0.88× — breaks** | 2.19× |
| 5 mm | 28 g | 2.19× | 5.48× |
| 25 mm, foam | 6 g | 10.97× | 27.42× |

The leg cannot rescue itself either. It stores 0.21 J of elastic energy before
that section fails across the layers, against the 2.85 J a fall releases — seven
per cent. It survives falls because the torso and the floor absorb the energy,
not because the leg is tough.

### So the levers are orientation and thickness

Print orientation is worth 2.5× and costs nothing, which makes it the first
thing to spend and the only one already available. Taking the plate from 6 mm to
8 is worth another 1.78×, and unlike a rib it lifts the bare run under the hub
as well, for about 3 g a joint. Neither is a flange.

Removing them takes 6.36 g off each limb pair, 12.7 g across the robot, and
leaves the limb a single flat profile 6 mm thick end to end — which is also the
cheapest thing to print and the strongest way to print it.

### How the limb should be printed

Laid **flat on the bed**, its 6 mm thickness in the build direction, footprint
about 180 × 52 mm. Every bending load on a limb — lateral or sagittal — puts
tension and compression along its long axis, so that axis must lie in the bed
plane and never up the build direction. Standing it upright is the 30 MPa case
and it is the orientation in which a sideways fall breaks a limb.

**Outboard face down.** The inboard face carries the Ø30.4 register recess only
1.2 mm deep, and that register pilots the hub on the actuator's Ø30 boss, so it
is a precision feature. Face-down it would need a sagging 30 mm bridge; face-up
it is an open pocket. The features that then have to bridge are the six Ø6
counterbores and the Ø10.2 journal seat — short, easy spans.

**Run the solid-layer raster along the limb.** Printed flat, the extreme fibres
for *lateral* bending are the top and bottom solid layers, so their fill
direction is the tension path; the usual ±45° default wastes it. Sagittal
bending is carried by the side edges, which are perimeters and already follow
the outline, so perimeter count is what helps there. Print solid or near it: the
part is about 31 g, and the mass budget already models it solid.

Interlaminar shear is not a concern in this orientation — 0.20 MPa at the
breaking load against 15–25 MPa available.

All of the above is arithmetic against 75 MPa in plane and 30 MPa across layers
for PA12-CF, which this project has still never measured on a coupon. Those
coupons remain the gate they have always been.


## The CAD left KCL, and what that changed about checking it

2026-09-10. The CAD is [build123d](https://build123d.readthedocs.io) in `cad/`,
and the KCL is deleted. [`BUILD123D_MIGRATION.md`](BUILD123D_MIGRATION.md) is
the plan and the record; this entry is what it means for how the robot gets
checked, which is the part worth remembering.

**Everything is free now.** Measuring the mass, exporting a STEP, exporting the
simulation meshes and building any part were all metered engine calls, so the
working discipline was "iterate against a free mock execution, spend credits when
the geometry has to be right". The mock execution never evaluated a boolean,
which is the whole gap that discipline lived in. Building a part locally IS the
boolean, so `/check` now catches a cut that cannot be made, and it takes five
seconds.

**Two defects surfaced during the port, and both are fixed.** The rotor arm's
stress-relief fillet was never the 1 mm radius its parameter named: the KCL
sketch constrained how far the blend reached but left the arc's centre free, so
the solver kept its initial guess and built a shallow sqrt(8.5) = 2.9155 mm arc
tangent to neither face, carrying nearly double the material a true quarter-round
would. It is a real 1 mm fillet now. Separately, a twice-mirrored solid comes back
inverted and measures ZERO volume while keeping a correct bounding box and taking
part in every boolean correctly -- the limb's rear gusset was in that state, and
nothing reported it. Every tool that adds bodies up now refuses a body of zero
volume outright.

**A render is no longer the evidence for a feature.** It never should have been:
structure behind a hole makes an open one look closed, which is how the rotor hub
carried four filled bolt holes through several rebuilds. `tools/gate_e.py` counts
the holes and bores on the finished solid, and `tools/gate_f.py` measures every
clearance the check scenes were drawn to show. Numbers from that, worth keeping:
the shin plate clears the thigh plate by 37.900 mm at the 110 degree knee stop
(they are in different planes, either side of the actuator, so the gap is the
joint's width and not a function of the angle); the folded wheel clears its own
thigh by 39.882 mm in the deepest legal squat, which is the tightest either pose
gets; and the torso floor clears a thigh swung 35 degrees forward by exactly
1.000 mm, which is the joint keep-out and nothing to spare.

**What was lost.** The rendered view sheet. `/views` produced a six-sided PNG
sheet of any model on the engine, and there is no local replacement -- `/view`
needs a viewer open. The golden renders the migration plan asked for were never
captured either, so there is no frozen visual reference to diff against.

**What is still open.** The printed pieces are still several interpenetrating
shells rather than single solids, because the Zoo engine refused to union them.
OCCT will, so that is now a matter of doing it -- with one obstacle: a body
carrying the 0.5 mm chamfer segfaults OCCT in any subsequent boolean, so as
things stand the union and the chamfer cannot both be had.

---

## The battery is back, and the torso grew 21 mm to take it — September 11, 2026

The umbilical is gone. The robot carries a 6S 2200 mAh pack of its own, made of
two 3S bricks in series, and 24 V and CAN no longer come from a bench.

This reverses the August 28 decision above rather than amending it, so both
objections it rested on have to be answered.

**"No 6S brick fits."** True, and still true: every 6S pack on the market is 108
to 125 mm long and this cavity's longest dimension is across the robot. What was
never tried is two 3S bricks, which are 76 mm each, wired in series. Stood ON
EDGE side by side they are 52 mm across the robot where flat they would be 66,
and 63 mm of interior depth is what there was. That orientation is the whole
design.

**"190 g is the entire mass headroom."** It was, in August. Deleting hip roll
gave back 700 g. The pack is heavier than that old reservation assumed as well:
288 g for 48.8 Wh, where NOTES had 190 g for 29 Wh. The old figure was
optimistic — it works out at 153 Wh/kg, and no high-discharge 6S pack on the
market reaches that. The two 3S bricks manage 169 Wh/kg, which is better per
watt-hour and half again the mass.

### Why two 3S rather than one 6S, in mass terms as well as packaging

| | Mass | Energy | Longest side |
|---|---:|---:|---:|
| 2 × Gens Ace 3S 2200 mAh 35C | **288 g** | 48.8 Wh | 76 mm |
| 1 × Gens Ace 6S 2200 mAh 45C | 374 g | 48.8 Wh | 125 mm |
| 1 × GenX 6S 2200 mAh 40C | 420 g | 48.8 Wh | 108 mm |
| 1 × GenX 6S 1550 mAh 95C | 363 g | 34.4 Wh | 86 mm |

The last row is the one to look at before anyone buys on C-rating. Peak draw is
six actuators at 4 A, which is 24 A — 11C on a 2200 mAh pack, against a 35C
rating. A 95C pack buys discharge headroom nobody needs and pays for it in
energy density.

### The objection to 6S that turned out not to matter

A 6S LiPo charges to 25.2 V and falls to 19.8, so it spends most of its
discharge below the actuator's 24 V nominal — which is what the August note
recorded as the trade. **The undervoltage cutout is 15 V, not 24.** Below
nominal you lose top speed, because back-EMF limits it, and nothing else. 7S
would have been the real problem: 29.4 V charged against a 30 V overvoltage trip
leaves six tenths of a volt for regenerative overshoot.

### What it costs

| | Tethered | On a battery |
|---|---:|---:|
| Total mass | 1 606 g | **2 060 g** |
| Under the 2 300 g ceiling | 694 g | **240 g** |
| Torso | 125 × 68 × 65 | **153.9 × 72 × 86** |
| Standing height | 339 mm | **360 mm** |
| Centre of mass | 168 mm | **202 mm** |
| Pendulum above the axle | 128 mm | **162 mm** |
| Time constant of the fall | 114 ms | **128 ms** |
| Lean before the CoM leaves the track | 34° | **28°** |

454 g and six degrees of lateral margin, for cutting the umbilical. The sagittal
balance problem got very slightly easier — a taller pendulum falls more slowly —
and the lateral one got harder, because there is no hip roll and a higher centre
of mass leaves a 170 mm track sooner. **If lateral margin is what matters,
widening the track is far cheaper than moving mass**: 170 to 220 mm takes the
tip angle from 28° to 36°, which no rearrangement of 288 g comes close to.

### The three millimetres that set the shell section

The torso is derived from what fits inside it, and two of its three dimensions
were decided by clearances rather than by contents:

* **153.9 mm wide, and nobody chose it.** This number moved three times in a
  day and the last move is the one that matters. 135 was picked to leave a
  10.2 mm cable chase between the battery and a 38 mm power block of our own
  design. Buying the distribution board took that back -- it is 50 mm square
  where the custom PCB was 38 wide -- and 141 was what fitting it needed. Then
  the width stopped being a free number at all: it is derived from the hip
  clevises now, twice the hip half-spacing plus the clevis's own outboard face,
  so the shell ends exactly where the joints it carries do. That is 12.9 mm more
  than the payload asks for, none of it is spent on either bay, and it lands in
  the gap between them -- so there is a 15.1 mm chase again, by accident.
* **72 mm deep, not 68.** The four ledges the electronics deck lands on stand
  5 mm proud of the front and rear walls, right beside the packs. At 68 mm the
  pack and the ledge are a tenth of a millimetre apart; at 72 they are 1.6.
* **86 mm tall.** 9 of hip saddle, 36 of battery, 3 of deck, 12 of controller,
  16 of SBC, two 2 mm band gaps and 2.6 under the lid, plus floor and cover.

`tools/gate_f.py` measures all of those rather than asserting them, and the
1.6 mm is the tightest fit in the robot.

### A new printed part, and the problem it was always going to solve

`cad/deck.py` is the first piece on this robot the Zoo engine never built. It is
a 3 mm plate on four wall ledges carrying the controller carrier and the SBC
above the battery, and it holds the packs down through 3 mm of squeeze.

It is not really the battery's doing. **The SBC has floated in its reserved
volume with no mount drawn since the layout was first done**, because the cavity
is full at floor level and there has never been anywhere for a standoff to land.
The battery made that impossible to keep ignoring. Two of the deck's four SBC
posts pass through clearance holes in the controller carrier, which is
unavoidable rather than untidy: 76 mm of carrier plus 85 of SBC is more than the
shell is wide however they are arranged.

### The setting that matters more than any part on the bill

The DM-J3507's undervoltage threshold is configurable and its floor is 15 V. Six
backdrivable motors will drag a 6S pack well past 3.0 V a cell and destroy it.
**Set the threshold to about 21.6 V — 3.6 V per cell.** On a bench supply this
was irrelevant; on a battery it is one mistake per pack.

### What is still not known

* **Runtime.** Computed, never measured: about two hours standing and balancing,
  an hour driving, under twenty minutes holding a loaded crouch. The fixed
  overhead is a guess, the gearbox friction that decides the cost of holding a
  pose has never been characterised, and a twitchy balance loop at 100 Hz could
  burn several times the calm figure. THE INA226 NO LONGER CLOSES THIS: the
  current measurement was deleted on 16 September 2026 and the monitor is a
  voltmeter now, so the figure is closed by a clamp meter round the pack lead
  through a first stand and a first drive, taken once on a bench.
* **The capacitor bank.** Still not sized, and its reservation is unchanged. The
  pack is the regeneration sink now, which is a reason to expect the bank to
  shrink and not a measurement of how far.
* **The emergency stop.** It has no home in the CAD, and it matters more now
  than it did: on a tether the bench supply was always the stop of last resort.
* **The torque envelope.** Still not re-derived for the wheeled robot, so the
  255 g of remaining headroom is measured against a walking robot's ceiling.

## The pack charges in one go, and the rear wall carries a charge port — September 11, 2026

The panel the battery came with had one balance port per 3S brick, which meant
one charging session per brick. That is now a single 7-way port with the two
packs' tails joined **inside** the shell, so a charger sees the 6S pack they are
already wired as and finishes the lot in one session, at 1C and 55 W on the
B6AC's 80.

The merge could have been an adapter on the bench and very nearly was. Nothing of
the kind is stocked in India: everything sold there as a "2S–6S balance board" is
a breakout on common pins, which across a series pair shorts a pack through its
own balance wires, and the one ready-made twin-pack lead that does the job
properly is discontinued. Made once, inside the robot, it can be metered and then
left alone — which is the better place for it anyway.

### Why there is a second power connector now

**The charger cannot come in through the disconnect.** Charging through the
XT90-S leaves six actuator controllers, the BEC and the SBC across the charger at
something like half an amp, and a constant-voltage taper never falls below that,
so the charge never terminates and the pack is held at 25.2 V for as long as it
is plugged in. So the pack's own terminals come out on an XT30 ahead of the
disconnect, and the routine is: pull the XT90-S to kill the bus, then charge.

XT30 rather than XT60 is deliberate — 2.2 A needs nothing bigger, and no two
connectors on this panel should mate with each other.

### What it cost

The rear wall lost 82.56 mm3 of material, which is 0.1 g, and nothing else moved:
one 20.5 × 8 opening and one 12 × 7.2 where there were two of 13.5 × 8. The robot
still totals 2 060 g against its 2 300 ceiling. Gate E now asserts all three
panel openings on the finished solid — empty, with wall around them — which
rectangular cuts had never been held to, because counting cylindrical faces
cannot see them.

**Still unmeasured, and it is the same warning as before:** the 7-pin JST-XH and
the XT30 are catalogue-class figures. A panel cutout is the one thing that cannot
be adjusted after printing, so measure both mouldings first.


## The harness gets a side, and something to hold on to — September 13, 2026

Two changes to the one limb part, which is every limb on the robot. Neither is
large and one of them is free.

### The connector relief faces aft

The flat limb's lower plate is drawn behind an actuator whose output faces +X
and then brought to the near side to land on the rear cover, because the lower
actuator at every joint is turned round. It had always been brought across by a
half turn about Z, which is a true mirror of everything on that plate except the
one feature that is not symmetric fore and aft: the connector relief. So the
relief ended up forward.

Nothing was wrong with that until somebody routed a cable. The hip actuators'
connectors face aft, and both floor ports into the pelvis are aft, so with the
knee's and the wheel motor's facing forward, all four leads on the robot would
have had to cross their own limb front to back before they could go anywhere.
Reflecting the plate across YZ instead of spinning it puts it in exactly the
same place with its relief still aft — the same thing as installing that
actuator the other way up.

Gate B measures it as +817.87 mm3 added and 817.87 removed, the same number to
1e-5, and that agreement is the check rather than the cost: the forward segment
the relief used to take is filled back in and the identical segment comes off
the aft one. No material, no mass, one silhouette mirrored.

### Two cable-tie arches on each limb's inboard face

Nothing outside the pelvis anchored a lead. `docs/BOM.md` buys adhesive tie
mounts, but they were bought for the torso floor, and a limb that swings through
110 degrees is not where to trust an adhesive pad. Each limb now carries two
arches — a 6 x 10 block standing 4 mm off the plate with a 3.5 x 2.0 tunnel
under it, so a 2.5 mm tie passes through and closes round the bundle lying
beside it. 237 mm3 apiece, 1.1 g across the four limbs.

**A slot through the plate was never an option, and the arithmetic is the
reason.** The waist is 40 x 6 and its weak direction is sideways, out of the
plate's plane, where the whole section modulus is 240 mm3. A tie needs two slots
to straddle a bundle; a 2 mm pair takes a tenth of that, and a slot in a bending
plate concentrates stress at its edge by something like 1.5 to 2. Together, at
the station these sit at, that lands 1.5 to 2 MPa per newton of sideways load at
the wheel against the 0.99 the limb's worst section carries today. The tie point
would have become the weakest thing on the robot: roughly 30 N sideways down to
15 or 20. Anything standing ON the plate costs the section nothing.

**They were ears in the plate's own plane for one revision**, reaching 12 mm aft
of the flank, which is cheaper to print and is what a slot would have been
replaced by if only strength mattered. They moved because of what they were
exposed to: the ear and the bundle tied to it were the aft-most material at
their own station by 12 mm, inside the robot's silhouette only by the 4 mm the
wheels and the torso's back stand proud of them. A fall onto a flat floor would
not reach them; a doorway, a bench leg or a table edge would. On the inboard
face the whole run is inside the box the two limb plates and the actuators make,
and that is the side every connector on the leg is on anyway.

**What that costs is a print orientation.** The arch is 4 mm proud of one face,
so that face has to be uppermost on the bed or it wants support. It is the face
the Ø30.4 register pocket is in, which would rather be uppermost than bridged,
and which way up a flat plate lies costs nothing structurally — the layers run
along the limb either way.

### What the run is, and what still is not known

The bundle lies on the inboard face 17 mm aft of the limb's centre line, beside
the arches. There it is clear of both Ø46 actuator bodies from z -35 to +35 and
swings out past the flank over the last 17 mm at each end, which is where its
connector is. The arches are the rigid part and are held further off: 30.5 mm
from their own joint axis, which leaves **3.44 mm between an arch and its
actuator**, measured by `tools/gate_f.py`. The limb check scene carries the
actuator at BOTH ends now for exactly that reason — it held only the lower one
while nothing stood off the limb's faces.

**The loops at the joints are still arithmetic, not geometry.** Anchor to
anchor, the knee crossing runs 31 mm folded to 68 mm straight, so it wants 68 mm
of lead carrying 37 mm of slack; the hip runs 34 to 75 over the provisional
+/-60 degrees of travel, and wants 40 mm of slack. Those are spans between tie
points and not cable lengths, they assume a hip range no swept clearance check
has ever confirmed, and they wait on the same measurement Phase 6 has been
blocked on since the limb was drawn: how far a mated SH1.0 plug and its strain
relief stand off the actuator's rear face.

### What it cost

+1.5 g on each limb pair — 0.4 of that is the relief and register corrections
this line already carried, 1.1 is the arches. The robot totals 2 108.6 g against
its 2 300 ceiling, 191.4 g under. All six gates pass, the URDF is rebuilt from
the re-exported meshes, and `simulation/check_model.py` still agrees with the
CAD.

---

## The knee gets its bearing back, and the leg gets shorter legs — September 13, 2026

The thigh no longer ends in a flat plate. Its lower end is `cad/joint.py`'s
`statorClevis` — the part the hip has always used, unaltered — two cheeks
straddling the knee actuator with a 6800 bonded into the far one, and a Ø10
dowel journal reaching into it out of the shin's rotor disc. The shin is
untouched. Four bearing-and-journal sets on the robot now rather than two.

### Why the knee and not the wheel joint

The flat limbs left every lower joint hanging on the actuator's own output
bearing, and the entry above from 29 August records the two numbers that rest on
it and the fact that DAMIAO have never confirmed either: **0.45 Nm standing on
one leg, about 1.35 Nm landing at three times body weight**, because the plate
sits 22 mm off the axis.

Those are the knee's numbers, and the knee's alone. Everything below it hangs off
it — the shin, the wheel motor, the adapter and the wheel. The wheel joint below
carries the wheel and nothing else, on a 12 mm arm rather than a 22 mm one, which
`cad/wheeled_parameters.py` already put at 0.12 and 0.36 Nm and called "not the
governing case". A sideways scuff widens the gap further: the knee stands 145 mm
from the contact patch where the wheel bearing stands 40.

And the wheel joint has nowhere to put a second bearing that does not mean a fork
reaching round a Ø80 wheel, turning at road speed all day. The knee's second
support is a part that already exists.

### What it cost

| | Before | After |
|---|---:|---:|
| Thigh, each | 37.1 g | **46.7 g** |
| Bearing and journal sets | 2 | **4** |
| Printed structure | 444.1 g | **465.9 g** |
| Whole robot | 2 108.6 g | **2 147.5 g** |
| Headroom under 2 300 g | 191.4 g | **152.5 g** |
| Distinct limb prints | 2, printed twice each | **4, one each** |
| Knee commissioning stop | 110° | **100°** |
| Deepest squat | 89.5 mm of drop | **75.0 mm** |

38.9 g all in, of which half is steel.

### The fold limit comes back, and it had to

The flat limbs' best trick was that thigh and shin lay in disjoint slabs of X on
either side of the knee motor and could not touch at any angle, so the 110°
commissioning stop was a control decision and nothing more. **A straddle cannot
keep that.** Reaching a bearing round to the far side of an actuator means a
saddle spanning the joint, and the saddle stands 24 to 36 mm above the axis —
squarely in the plane the shin sweeps.

Measured rather than argued: the shin's waist is a 40 mm plate whose top corners
sit 24.4 mm from the knee axis, they touch the saddle's floor at **103.0°**, and
at 110° the two share 62 mm³. The stop is 100° now, which is where the gap
between them is exactly 1.0 mm — the same air the shin's rotor disc has against
the far cheek, so one margin in `tools/gate_f.py` covers both. `cad/poses.py`
derives the squat and both knee review scenes from that one constant, and the
URDF's knee limit reads it out of the CAD.

Three ways of buying the 110° back were looked at and all three are worse than
the 14.5 mm of squat they would return. Trimming the shin's waist corners cuts
exactly the material the gussets were added to provide, at the peak-stress
section. Notching the saddle's floor puts a hole through it 0.5 mm from the far
cheek's root, which is the load path the whole change exists to make. Narrowing
the saddle in Y guts the cheek necks.

### Two prints become four, and one of them cannot be printed flat

The right thigh and the left shin used to be the same solid, so two prints
covered four limbs. Not any more: a thigh ends in a clevis and a shin in a plate.
Same part count on the robot, twice as many things to slice.

**The shin is the piece that did not change**, so it keeps the `limb-105` name,
and with it the golden STEP `tools/gate_b.py` holds it against — `gate_b.py`'s
registry simply points those two names at `cad/shin.py` now and both still match
the engine's geometry exactly. The thighs are new pieces with no golden behind
them, like the electronics deck, and `tools/gate_e.py` counts their thirteen
features instead: the ten M3 holes they always had, plus the bearing seat, its
shoulder and the boss that carries it, which are asserted together because the
seat is 5 mm deep in a 3 mm cheek and only exists if the boss was unioned on
first.

**What is genuinely unresolved is how a thigh should be printed.** A flat limb
lies on the bed with every fibre running along it. A thigh's far cheek stands
48 mm across the joint from its plate, joined only by the saddle, so laid the
same way it has a Ø52 disc floating in the air. On end or on its flank, either
puts layer lines across a section that had none, and the entry from 30 August
puts that at 21 N sideways at the wheel against 53. Nothing in the gates can
settle it.

### What is checked

All six gates pass. Gate B holds both shins byte-for-byte against the engine's
STEPs and the clevis against its own. Gate E counts thirteen features on each
thigh and both cable-tie tunnels open — the clevis-end arch had to move from
30.5 mm to 42 to stand clear of the saddle, and an arch inside a saddle is
exactly the closed tunnel that test exists for. Gate F measures the fold at the
stop, ten degrees under it and in the squat, the bearing seated in the thigh's
cheek, the journal in the shin's disc, and the clevis's 0.3 mm off the rear
cover. Gate D drives the tree to 50°/100° and lands both wheels on the floor.

### What is not

The thigh's print orientation, above. The torque envelope, which the entry from
29 August left open and which this does not close — it takes the knee off the
list of joints waiting on DAMIAO and leaves the wheel joint on it, at a third of
the load. And the value of the second bearing itself is still an argument rather
than a measurement: nobody has loaded a printed cheek with a bonded 6800 in it.
`docs/BOM.md`'s fit coupon is where that gets settled.

---

## The parts get sintered, and the journal stops being a part — September 13, 2026

Two changes, and the order matters: the material moved first and the journal
followed, because on the old material the journal would have been the thing that
broke.

### SLS PA12, and the reason is the layer axis

Every strength argument this project has ever had came in two numbers. PA12-CF
gives about **75 MPa in the print plane and about 30 across the layers**, and
almost everything above is arithmetic against that pair: which way a limb lies on
the bed is worth 2.5x on it, the thigh could not be laid flat at all once its
knee clevis existed, and the one thing that decides whether a part survives is
usually the 30.

Laser-sintered PA12 has no weak axis — about **48 MPa in every direction**. That
is worse than 75 and much better than 30, and it is the second figure that has
been governing.

### What it bought

| | Before | After |
|---|---:|---:|
| Density | 1.06 g/cm³ | **0.93 g/cm³** |
| Printed structure | 465.9 g | **411.8 g** |
| Bought steel at the joints | 49.4 g | **20.0 g** |
| Whole robot | 2 149.7 g | **2 073.8 g** |
| Headroom under 2 300 g | 150.3 g | **226.2 g** |

Fifty-four grams of that is the density alone, on parts whose shape did not
change by a thousandth of a millimetre. The rest is the journal, below.

**Print orientation stops being a design input**, which quietly retires the open
question the thigh's clevis had created a few hours earlier: a thigh cannot be
laid flat, and it no longer matters which way it is built.

### What it costs, and one of these is unfinished

Parts are sent out now — a per-part cost and a turnaround where there was a spool
and an afternoon. The 2.4 mm wall was four perimeters of a 0.6 mm nozzle and now
means nothing; it is a thickness SLS holds comfortably, but it is no longer
*derived* from anything. And **every section designed against 75 MPa in the print
plane is now designed against 48**, which nobody has been back through. The
limb's worst section had seven times its load and has room to spare; that sweep
is open work rather than a finding.

**0.93 g/cm³ is the bureau's number, not ours.** Sintered PA12 runs 0.90 to 0.95
depending on how powder is packed and refreshed, which is about 5 g across the
robot. It is the softest figure in the printed half of the table.

### The journal is printed with the limb

It was a Ø10 × 8 hardened dowel bonded into a Ø10.2 × 2.2 blind seat in the
limb's output disc. The disc grows its own Ø10 stub instead, 6 mm proud with a
0.8 mm fillet at the root, at the hip on a thigh and at the knee on a shin — the
two straddled joints on each leg. **Four bought items, four bonded joints, 29.6 g
of steel and the seat itself, all gone.**

It was the wrong thing to do a day earlier. The stub carries the bearing's
reaction as bending at its root: **17.8 to 23.2 MPa** at the 500–650 N this
project records at the 6800. Against PA12-CF's 30 MPa across the layers — which
is exactly what a root standing off a flat-laid plate is made of — that is a
margin of 1.3 to 1.7, on the joint that takes the actuator's full torque, where
the limb's own worst section is held to seven times its load. Against 48 MPa
isotropic it is 2.1 to 2.7, and the stub is no longer the thing that goes first.

### What is still not known about it

**Fatigue.** Nobody has run it, and a printed shaft turning under a reversing
bending load is exactly where it would matter.

**The root.** 0.8 mm on a Ø10 shaft is r/d = 0.08, a stress concentration near
1.9, and 1.9 × 23.2 is 44 MPa against 48. The static case survives that because
PA12 is ductile at about 18 per cent elongation and the peak redistributes; a
cyclic one might not. The fillet is as large as the space allows — the bearing's
inner face sits 1 mm off the disc and the fillet has to stop short of it.

**The bearing fit.** The stub is Ø10 nominal in a Ø10 bore, printed rather than
ground, and SLS holds about ±0.2 mm. The inner race will want bonding onto it
with the same retaining compound that holds the outer race in the cheek, exactly
as the bond takes up the gap everywhere else here. That is an argument, not a
measurement, and `docs/BOM.md`'s fit coupon is still where it gets settled.

### What is checked

All six gates pass. Gate B holds the limbs to a declared **+655.48 mm³** each —
471.2 of stub, about 4.5 of fillet, and 179.8 of seat no longer taken away —
and nothing else moved. Gate E counts the Ø10 journal as a cylindrical face on
the finished solid, which is the check that the union actually happened: a union
that quietly does nothing leaves a disc with no stub and nothing else to report
it. Gate C needed a change of its own to stay meaningful, and it is worth
knowing: the mass baseline is a record of **geometry**, so comparing today's
parts against it at today's density would have reported every part on the robot
as having drifted the moment the material changed. It compares at the baseline's
own density now, and the roll-up reports at the real one.

### One thing found along the way and not acted on

The actuator's output face carries a **Ø9 +0.02/+0.04 bore on its axis**, with a
Ø3 +0.03/+0.05 ↧4 dowel hole beside it — manual V1.0, page 5. Neither is used by
anything in this CAD. **No depth is given for the Ø9**, and the 2D print that
would say is the one vendor file this repository has not mirrored. A Ø9 journal
piloting in the motor's own bore, with a 689 (9 × 17 × 5) in place of the 6800,
would locate the joint in steel at both ends and retire the printed seat's
coaxiality argument altogether — at the cost of 27 per cent of the journal's
bending strength, since section goes as the cube of diameter. It needs the depth
first, which needs a caliper or a question to DAMIAO.

Also unresolved from the same drawing: the output register measures as both Ø25
and Ø30 depending on which circle the leader is read against, and
`cad/parameters.py` carries Ø30. Worth a caliper before the pelvis is printed.

---

## The joint could not be assembled, so the journal is bought again — September 14, 2026

The four straddled joints could not have been put together. The clevis is one
print whose two cheeks stand **45.2 mm** apart, and an actuator with its limb's
output disc bolted to it measures **49.9 mm** from its rear face to the journal's
tip. That is 4.7 mm of interference on a joint with 1.3 mm of axial slack, and it
was as true of the Ø10 dowel bonded into a blind seat as it is of the printed
stub that replaced it on 13 September: both are one piece with the moving side
before the joint is closed.

**There is no order that works.** The six output screws are counterbored on the
face the far cheek ends up 1 mm from, so the disc has to be on the motor before
the motor goes into the fork; the journal then needs 5 mm of axial travel to
enter the bearing and has 1.3. Springing the cheeks apart is not a way out
either: 4.7 mm strains a 3 mm cheek roughly 2 to 4 per cent at its root, at or
past what PA12 takes elastically, on the one part that holds the bearing in line
with the output.

### What it is now

A bought Ø10 × Ø5.3 × 6 steel sleeve, fitted **last** and from **outside**:
through the bearing boss's Ø17.5 shoulder bore, through the bearing, onto the
disc's face, with an M5 × 10 button head pulling it down onto an M5 thin nut
captive in a hex pocket in the disc's motor-side face. The assembly order is
bearing bonded in, disc screwed to the motor with the nut already in its pocket,
motor into the fork, four rear screws, then the journal.

Every printed part keeps its shape but the limb discs, which lose the blind seat
and gain a Ø5.5 hole and the nut's pocket: **+92.3 mm³ and −195.3 mm³** against
the golden STEP, both declared in `tools/gate_b.py`.

### The sleeve was drawn capped, and nothing in this repository could see it

Its bore was cut by a cylinder centred on the sleeve's inboard face rather than
on the sleeve, so it ran out **1 mm short of the outer end**: a tube with a cap on
it, with the screw modelled straight through that cap — 19.6 mm³ of steel in the
same place as 19.6 mm³ of steel. Every gate passed. A blind bore still leaves one
cylindrical face for gate E's radius count; gate F measures this hardware against
the printed parts it sits in and not against itself; and a bought part is in no
other gate at all. **The bought half of this robot has had no geometric check on
it whatsoever**, which is worth knowing beyond this one part.

`tools/gate_e.py` now asks the sleeve's bore to be open end to end, the same
opening test the cable-tie tunnels and the nut's pocket get. The corrected sleeve
measures 338.9 mm³, which is exactly a Ø10 × Ø5.3 × 6 tube.

### The sleeve is printed, and the fit is what has to be proved

**Decided 14 September 2026: it goes on the printed table.** `journal-sleeve` is
in the export set, four off, and what is left bought at each joint is the screw
and the nut. That is 9.6 g off the robot — **2 084.2 g, 215.8 under the
ceiling** — and it is the softest figure in this entry, because it rests on the
fit coming good.

Strength is not the worry. In SLS PA12 the section carries **25 MPa at the 650 N
case and 14 at 350**, against 48 — margins of 1.9 and 3.5, better than the printed
stub had. Two other things are, and both are what the coupon settles:

- **Fit.** The 6800's bore is Ø10 held to eight microns and the sleeve has to
  slide into it and back out again. SLS holds about ±0.2 mm, which is twenty-five
  times that gap, so a printed sleeve either will not enter or leaves the far
  support with 0.2 mm of radial play — which is the slop the second bearing
  exists to remove.
- **Creep.** The sleeve is inside the clamped stack. An M5 at a modest 1 kN puts
  about 18 MPa of sustained compression on its section, and PA12 relaxes under
  that; the preload is already the weak thing about this anchor.

So **print several and dress them** until one slides into a 6800 and back out
without play; that is a bench operation on a 6 mm tube rather than a machining
job. Bonding one into the race would take the tolerance up and would also mean
the sleeve could never be withdrawn, which is the whole reason it is a slip fit.

**The steel sleeve remains the upgrade**, and nothing else about the joint
changes if it is taken: a Ø10 h6/g6 × Ø5.3 × 6 ground sleeve — a precision
spacer, a hollow dowel or a drill bush — puts 2.7 g back at each joint and
settles both objections at once. `docs/BOM.md` carries it that way round.

### The pocket had to be measured on the FINISHED part

It was drawn 0.3 mm over the nut's flats, which is the fit a pushed-in nut wants.
Then the seat was measured after `cad/finish.py` had run: that module breaks every
edge whose faces are all flat, the floor of a hex pocket is one of those, and the
0.5 mm chamfer round its perimeter took the seat from **35.9 mm² to 22.3** against
a nut face of **31.6**. The nut would have landed on the chamfer rather than on
the floor, on the one joint here whose preload is already the weak thing about it.
The pocket is 1.3 mm over the flats now, which leaves 35.8 mm² of flat floor once
the chamfer has been cut. Nothing in the gates would have caught it: gate B
compares the unfinished part and gate E only asks whether the pocket is open.

### What it costs

**13.2 g** back on the robot — 12.0 of bought screws and nuts and 1.3 of printed
sleeve, against 0.2 g of disc material the anchor takes away. That is
**2 084.2 g all in, 215.8 g under the ceiling**, where it was 2 071.2 and 228.8.

And the anchor is weaker than the stub was, which is the honest part. A stub
grown out of the disc spread its bending into the whole Ø36 plate; a sleeve
clamped to that plate's face is held by the 4.8 mm of PA12 at the disc's centre,
and nothing wider is available, because anything that clamps it has to pass the
bearing's Ø10 bore or fit the 1 mm gap behind it. The clamp lets go and the
plastic under the sleeve's rim begins to crush somewhere around **300–400 N**
against the **500–650 N** this project records at the 6800 for the 100 N at
100 mm case. That is an estimate from clamped-annulus and embedded-pin
arithmetic, not a test — and by the 29 August entry's own figures it is about
where the limb plate itself breaks, so it is not the first thing to go.

### What would give it back, and what it waits on

Metal behind the disc: a steel hub between the disc and the motor's output
flange, held by the same six screws, carrying the thread, so the journal's
bending crosses steel instead of 4.8 mm of plastic. Whether there is room turns
on how far that flange stands proud. **The vendor STEP puts it 1 mm proud inside
the 37.9 mm overall length**, which would leave the disc's 1.2 mm register pocket
free for a hub — while `cad/parameters.py` assumes that pocket is filled by the
register. The two disagree, and the 2D drawing that would settle it is the one
vendor file this repository has not mirrored. It is the same caliper the Ø25-or-
Ø30 register question has been waiting for.

Also unmeasured, and the same coupon settles both: the sleeve's fit in the
bearing bore, and whether the clamp holds its preload in sintered PA12 or creeps
out of it.

### What is checked

All six gates pass. Gate B holds the two volumes above exactly. Gate E counts the
Ø5.5 screw hole on every limb and thigh and asks the nut's pocket to be open with
nothing standing in it — a hexagon has no arc for the radius count to find, so it
is asserted as an opening like the cable-tie tunnels. Gate F measures the journal
seated at the knee and, for the first time, at the hip: bearing, sleeve, screw
and nut meet the printed parts and share no volume in either. The URDF is rebuilt
from re-exported meshes and `simulation/check_model.py` still agrees with the
CAD, with 5.7 g of journal now riding on each thigh and shin rather than inside
the mesh.

## CAN topology, and the pins the third bus costs — September 14, 2026

The six motors now sit **two to a bus on three buses**, paired left and right by
joint: both hips, both knees, both wheels. It came out of wanting every motor to
run home to the torso on its own cable, with nothing spliced into a trunk part way
down a leg. With two motors on a bus, the bus is a straight line from one motor,
through the carrier, to the other — the transceiver taps the middle of it, there
is no star point, no stub, and no junction anywhere for a splice to be needed at.
Termination falls out of the same arrangement for free: both ends of every bus are
motors, so all six of their own switches stay ON and the carrier carries no
resistor at all. That is a simpler loom **and** a simpler carrier than the two-bus
plan it replaces, which is not the usual direction of travel.

The bandwidth argument runs the same way, though it is computed and not measured.
A command and its reply at 1 Mbit is of the order of a quarter of a millisecond per
motor, so two motors is about half a millisecond per bus and three would have been
close to 0.8 — comfortable against a 1 kHz loop in the first case and marginal in
the second. Giving the wheels a bus to themselves is also what
`WHEELED_BIPED_IMPLEMENTATION.md` suspected would eventually be wanted.

**The third bus is not free, and what it costs is the BOOT0 button.** On the
48-pin package the first CAN controller can only come out on PA11/PA12, which are
USB D−/D+, or on PB8/PB9 — its third option, PD0/PD1, is not bonded out on this
package. The other two controllers are unaffected and sit on PB12/PB13 and on
PB3/PA15. Keeping USB therefore means taking PB8, and PB8 is the BOOT0 pin: it
only becomes an ordinary pin once the boot function is switched off in the option
bytes, and from then on holding the button at reset no longer reaches the built-in
USB bootloader. USB itself still works, both as DFU and as a serial port, because
PA11/PA12 are untouched; it is the way *into* DFU that is gone, so entering it
needs firmware that flips the option bit and reboots — which is no use if the
firmware is what is broken. Hence the ST-LINK on the bill. The alternative, kept
here in case losing the button proves worse than it looks, is to put the first bus
on PA11/PA12 instead, give up USB entirely, keep the BOOT0 button, and program
through the bootloader's own CAN interface with the Waveshare adapter this bill
already buys.

One firmware detail worth writing down before it bites someone: PA15 and PB3 are
JTAG pins and come up as JTAG after reset, so the third bus only works with
SWD-only debugging selected, which is what the board's pins offer anyway.

What is still unproven, and one thing that is now plainly a gap. The bought motor
pigtail on the bill is **300 mm of 30 AWG**, plugged at the motor and bare at the
other end, and 300 mm serves a hip and a knee but **does not reach from a wheel
motor**, which sits two 105 mm limbs below the hip. So for two of the six the loom
is still spliced part way down a shin, which is exactly what the home-run layout
exists to avoid. Pre-terminated 28 AWG leads up to 800 mm exist abroad and are the
answer, but nobody has sourced one. Nobody has checked three cables of real diameter through the
14 × 10 mm floor port either, and the wheel motor's cable now crosses both the hip
and the knee, so it wants a service loop at each. The V1.1 manual reverses the
motors' termination default, so read each switch rather than trusting that all six
arrive ON. And the CAD was already drawn for this: `cad/electronics.py` routes the
harnesses as two runs of three through the floor ports and carries one WeAct board
on the carrier, so nothing in `cad/` had to move for the routing. **That was wrong
about the transceivers**, and it stood for most of a day: the CAD drew a pair of
DIP-8s rather than a bank of four positions, so going to three buses left the
packing a transceiver short and this paragraph said otherwise. It draws three now,
at 12.7 mm centres — five perfboard holes — with the column moved 2.5 mm inboard,
because at the old inset the outer two overlapped the carrier's own M3 corner holes
by 0.3 mm. The fourth position is a socket on the bill and nothing in the CAD,
which is where the spare goes.


## The output register stands proud, and the plate was seating on nothing — September 14, 2026

This file has said since 24 August that the actuator's output is **a Ø30 boss
standing 1 mm proud of the body**, that the vendor drawing dimensions 36.90 to
the body and 37.90 over the boss, and that the mating hub therefore has to
register **onto** it. The CAD never did. It drew the motor as a plain
Ø46 × 37.9 cylinder, landed the rotor plate flat on the end of it, and cut a
Ø30.4 × 1.2 pocket in the plate for a boss it assumed stood 1.2 mm into it.

With the housing 1.0 mm shorter than the cylinder, the plate was seating on
nothing at all. Its annulus hung 1.0 mm off the housing's front face, the boss's
face sat under an empty pocket, and the six M3 that carry the joint's whole
output torque were clamping across the gap. The M5 nut captive in that pocket
was floating in it too. Six joints on this robot, and both wheel adapters.

**The plate lands flat on the register now, and the pocket is gone.** Not moved
— gone. The first fix drawn was to turn the pocket inside out: cut it inboard of
the seating face, in a Ø36 × 0.7 rim the plate would carry, so it still piloted
on the boss. That survived about an hour. The rim's height and the plate's
clearance over the housing are the same millimetre shared out — they always add
to the boss's 1.0 — so a 0.7 mm rim leaves 0.3 mm of air, and 0.3 mm is inside
what SLS holds on the 0.7 mm feature that sets it, before the plate's own
flatness over Ø36 is counted. A rim that prints long does not merely rub. It
lands on the housing and stops the plate seating on the register, which is the
exact defect it was drawn to cure, on a face that turns.

**What that costs is the pilot, and the pilot was worth less than it looked.**
At a straddled joint the plate is already located twice — by the six M3 on Ø24
and by its own journal in the far bearing — and that bearing sits in a printed
clevis bolted to the rear cover through Ø3.4 clearance holes, so the coaxiality
a 0.2 mm pilot would have protected is not available at the other end of the
joint anyway. A third radial location on one rigid plate is over-constraint, and
in a printed assembly over-constraint is something binding. On the wheel adapter
there is no far bearing at all, and ±0.2 mm of runout on an Ø80 wheel is half a
per cent.

**Nothing on the robot moved.** The seating face is where it always was, so the
plate's outer face, the journal, the bearing, the wheel and the pelvis width
derived from the hip clevis are untouched, and the URDF's kinematics are
unchanged. Taking the plate *out* to meet the register would have moved all of
them and put a 0.7 mm step in the exterior of the leg, since a limb lands on a
rear cover at one end and on this register at the other.

**It costs 5.3 g**, about 0.9 g a plate, all of it the 1.2 mm pocket filled back
in. Gate B holds every cubic millimetre — 806 mm³ on a plain plate, 740 on one
carrying the journal's anchor — and the nut's web goes from 1.5 mm to 2.7 for
free, the pocket floor it used to hang off having been the thing that was wrong.

**What replaced the pocket's own check.** `tools/gate_e.py` used to assert the
Ø30.4 pocket was a whole circle and not a partly-filled one. There is no pocket
to assert, so what it asserts instead is the *millimetre in front of the plate*:
a probe filling the register's footprint between the plate's face and the
housing, with nothing allowed to stand in it. That is the failure mode directly
— a rim, a boss, a waist that crept towards the joint — and it is checked on all
five pieces that carry an output plate.

**And it closed two open notes.** The paragraph beside `journalDiameter` used to
say the STEP and the CAD disagreed about this millimetre and that a caliper
would have to settle it; the vendor's own drawing settles it, and against the
CAD. The second is the thread engagement in the "Knee actuator-interface
implementation" entry above: the six output screws engage 3.2 mm, not the 4.2
this file claimed, and they always did — `BOM.md` had it right.

**Two things it also ended.** Both of this project's refilled-feature failures —
the rotor arm burying four of six bolt holes, and the limb waist filling 46° of
the register pocket — happened in the plane the pocket occupied. There is
nothing in that plane to fill now. The rule that produced them stands: nothing
may be built across the Ø24 output circle in the plate's own plane.

## Review findings 1-4 corrected ? 2026-09-15

The journal screw was still sized for the retired 1.5 mm web. The current web
is 2.7 mm, leaving M5 x 10 only 1.3 mm of nut engagement. The replacement is
M5 x 12 with a small-series DIN 433 M5 washer, 5.3 x 9 x 1 mm. It reaches
2.3 mm into the thin nut and ends 1.0 mm before the actuator. Gate F now checks
thread reach, tip air, washer clearance from the bearing and its seating.
The washer must be fitted. The printed anchor's strength/creep remain open.

Three deck notches now serve the six downward connectors. The motor-bus notch
widens from 34 to 44 mm and moves 5 mm left; the IMU gets an 18 mm notch and
power/sense get a 12 mm front notch. All remain outside the packs' hold-down
area and clear the four ledges. Gate E checks all openings. The carrier check
now rejects a partially blocked exit instead of reporting an advisory note.

J5-2 and J6-2 have solid ground connections on both PCB layers, shared by the
custom pour and KiCad exporter. Their old one-spoke thermal reliefs failed
KiCad. Solder these two pads with preheat; the copper connection is deliberate.
The schematic and PCB now share proper footprint identities, local-label net
names and explicit no-connect identities. The four SWD pins live only on the
core board; they are not phantom carrier pads in the schematic. Board-only
mounting holes have unique references. No DRC or parity rule was relaxed.

The old Gerbers were from before the hole-clearance and silkscreen fixes.
`electrical/fabricate.py` now rebuilds, checks, exports and packages the board,
with source/output hashes and a freshness check. The regenerated top silk is
required to be nonempty. The exported drill set and copper come from the same
filled board, after DRC and ERC; neither is taken from the old Gerber folder.

Mass: 2087.4 g, +1.8 g from the review baseline (2.4 g added fastener allowance
less 0.6 g removed deck). The journal fastener allowance is read from the BOM
budget by the simulation rather than repeated as a hard-coded 3 g.

Validation: CAD build/lint and gates A-F passed (771 clearance/fastening checks).
The old screw length and old deck openings were deliberately restored in memory;
the new checks rejected both. Finished deck STEP round-trips with five solids:
one plate plus four BMS guide ribs; the old export register incorrectly said
three, counting groups instead of solids. The register now records five.
The simulation was rebuilt and agrees with the CAD. KiCad reports zero DRC,
ERC, unconnected-pad and schematic-parity issues. The release contains 249
drilled holes (233 plated, 16 unplated); its silkscreen was rendered from the
actual Gerber and visually inspected. The ZIP and source hashes verify.
No hardware has been fabricated or tested.

## The power switch board, 2026-09-15

The robot can be switched off now, and until today it could not. Pulling the
loop key was the only disconnect, so a robot left on flattened its own pack, and
the BMS added two days earlier is on the cell taps and cannot break the discharge
path. What answers it is a second board of our own, in the pack's positive lead
between the loop key and the distribution board: `electrical/power.py` is the
circuit and `electrical/power_pcb.py` the board, and `docs/POWER_SWITCH.md` is
the whole account. It carries the main fuse, which was an in-line holder taped to
the bought board; the bus shunt, which had no mount at all; and two P-channel
MOSFETs that are the on/off and the low-battery cutoff at once.

Three things about it are worth keeping here rather than in the document.

**The soft start was got wrong first, and the arithmetic caught it.** The gate
was drawn pulled down through 4.7 kΩ against a 10 nF capacitor, which reads as a
gentle ramp and is not one: 4.7 mA into 10 nF is 470 kV/s, so the bus would have
come up in 60 microseconds and the check reported 617 A of inrush into the bank.
What is there now is 470 kΩ against 220 nF — 192 V/s, 131 ms, about 0.3 A — with
a diode that takes the capacitor out of circuit when the gates rise, so switching
OFF stays fast at 1.5 µs through the plateau. Slow on, fast off, and one part
between the two.

**The cutoff is at 19.2 V on the filtered bus, which is 3.20 V per cell.** The
actuators' own undervoltage cutout is 15 V, so this trips well above anything the
motors would complain about, and the 0.28 s filter is what stops a motor's sag
being read as a flat pack. It is a PACK-level cutoff: the BMS sees each cell and
cannot act, this acts and cannot see a cell, and a single weak cell falls between
them. The cell alarm on the balance tail is still the answer to that.

**KiCad's design rule check is the only opinion that counts on the copper.**
The layout is searched for here, but the board is assembled inside KiCad's own
Python from KiCad's own library footprints, and `kicad-cli` runs DRC on the
filled board: zero errors, zero unconnected, five warnings (two removed copper
islands and three pieces of silkscreen over pads). Two findings came out of that
loop rather than out of intention. Ten clearances came back at 0.175 mm where
0.2 was wanted, all of them a diagonal or a via against a diagonal, and the
router's grid margin went from 0.06 to 0.10. And the ground pour, which is the
whole bottom layer, was cut in two by a signal crossing it — an open circuit
KiCad called correctly. Ground is poured AND routed pad to pad now, so nothing
depends on the fill staying in one piece.

Mass: 2109.7 g against the 2300 g ceiling, +22.3 g for the change — 22 g of
board, parts and mounting hardware added up rather than allowed for, and 0.3 g of
printed pad on the pelvis's right-hand wall for the third screw. The other two
screws are the distribution board's own rear pair, made longer.

Validation: CAD build and lint clean, gates A–F pass (846 clearance and fastening
checks, including six new figures for this board), the netlist and its arithmetic
check, and KiCad's DRC is clean on the built board. Nothing has been fabricated
or tested, the peak bus current has still never been measured, and three things
this board needs are still missing: a hole in the rear wall for its button, a
connector on the controller carrier for the hold and button-sense wires, and a
regeneration clamp, which this board does not provide and never could.

## The power switch board goes through-hole, and grows to fit, 2026-09-15

Two changes, one day later, and the second one is the interesting one.

**It has a schematic now.** `electrical/power_sch.py` writes the netlist out as a
one-sheet KiCad drawing the way `carrier_sch.py` does — 51 symbols, 114 pins, 27
nets, joined by label rather than by wire — and runs KiCad's own ERC on it as
part of writing it. That check earned its keep immediately: the first version
pointed all 51 parts at a footprint library that does not exist. Every symbol
names the footprint the BOARD really uses, read out of `power_pcb.py`, so the
drawing and the copper cannot disagree about a package. The sheet's title block
carries the circuit's computed behaviour, so somebody reading it sees what these
component values actually do.

**Not one part on the board is surface mount any more.** It is a board a person
can place by hand and solder with an iron. The resistors and the diodes stand on
END on a 2.54 mm pitch, which is the one choice here that is not obvious and is
what makes the rest fit: an 0204 upright is 9.5 mm² of board against a 1206's
10.3, where the same part laid down on 7.62 mm would be 29. The comparator is a
DIP, the reference and the two small transistors are TO-92, and **two pinouts
changed with the package** — a TL431 in TO-92 is 1 REF, 2 anode, 3 cathode, not
the SOT-23's 1 cathode, 2 reference, 3 anode; a BC546B is 1 collector, 2 base,
3 emitter where the BC846B was 1 base, 2 emitter, 3 collector. A transposed one
is a board that does nothing.

**The shunt is what made it expensive, and the capacitor bank paid.** The only
four-terminal shunt made in through-hole runs 25.4 mm between its current leads,
246 mm² of courtyard against the 2512's 33, and on the old 54 × 32.5 outline that
was arithmetically impossible: parts and pours came to 98 % of the board. What
freed the room was a reservation nobody had re-read. The CAD drew FOUR cans of
Ø16 × 25 across the front of the power bay while `docs/BOM.md` has specified TWO
Panasonic EEU-FR1V471B — Ø10 × 16 — since the day it first named a part. Eight
times the volume, for the whole front half of the bay. Sweeping a probe of the
board's own thickness over the bought distribution board's entire 50 × 50
footprint found the bank to be the only solid in the way.

So the board is that bought board's own footprint now, stacked on it, and the two
cans stand on THIS board on the bus copper they damp. **The capacitance is
unchanged and still unmeasured**: what shrank is the reservation. It buys the
mount as well — four screws where there were two and a printed pad on the wall —
so the pad is gone and this bay costs the robot no printed material at all.

**The robot got lighter.** 2077.4 g against the 2300 g ceiling, where it was
2109.4: the bank's line falls from a 60 g allowance to the 20 g those two cans
and their leads actually are, against the 8 g the bigger board costs.

Three bugs in the layout tooling came out of this and each had produced a board
that passed every check this repository owned. **A pad's middle is its hole**:
the router aimed at the centre of the shunt's 3.0 mm pads and laid its track into
the 1.5 mm drill, and KiCad called both sense pads unconnected. **A pour drawn as
boxes that touch is two pours**: the bank's outboard riser met the bus bar on a
boundary line and filled as a separate island. And **a round courtyard read as
flat**: a radial capacitor's whole outline is one circle in KiCad's footprint
file, and the reader took the two points it is written with as the extent, so a
6 mm can measured 0 mm deep and parts were placed on top of it.

**Raising the board to clear the bought board's XT60 was tried and is worse.**
A trimmed lead hangs 2 mm under the board and that socket stands to within half a
millimetre of the underside, so nothing with a lead may stand over it. Ten
millimetres of spacer clears it outright — and takes two millimetres off the far
side, where the pack's own connectors hang 7.4 mm over this board and an upright
resistor is 5.5, and leaves 1 mm over the switches instead of 3. The socket stays
a keepout in the layout.

Validation: CAD build and lint clean, gates A–F pass (851 clearance and fastening
checks), the netlist and its arithmetic check, KiCad's ERC is clean on the
drawing and its DRC is clean on the built board at zero errors and zero
unconnected. Nothing has been fabricated or tested, the peak bus current has
still never been measured, and the bought board's own outline — including the
input socket this board passes half a millimetre over — is a catalogue drawing
rather than a board anybody has held.


## The schematic becomes a schematic, and the board turns out to need an import, 2026-09-16

Two pieces of work, and they are unrelated except that both are about the same
board being taken seriously as something somebody will actually build.

**The drawing is an ordinary schematic now.** What it was before is worth
recording because it looked finished: one generated rectangle per part, every
pin with a stub and its net's name on the end, and not one wire between any two
symbols. Every check passed. KiCad's ERC was clean. And it was unreadable,
because a resistor, a diode and a comparator were the same box with different
words in it, and following a signal meant searching the sheet for a name. A
drawing whose only reader is the program that wrote it is not a drawing.

It now places KiCad's own symbols — `Device:R`, `Device:D_Zener`,
`Transistor_FET:Q_PMOS_GDS`, `Comparator:LM393` as the three real units it has,
and `Device:R_Shunt`, which is the four-terminal Kelvin symbol and exactly what
R1 is — and joins them with wire, in the four blocks the circuit is read in.
Each symbol was picked so that **its pin numbers already match the footprint the
board uses**; the TL431's TO-92 symbol against its surface-mount one is where
that mattered, being the same part with the pins in a different order. Six nets
are still names rather than lines — the pack rail, the switched bus, the gates,
the enable line, ground — because they run the width of the board and drawing
those as wires between four corners is how a schematic stops being readable.
That is how it would be drawn by hand.

**The new check is the one worth keeping.** The sheet is handed to `kicad-cli`,
which extracts its netlist, and that is compared pin by pin against `power.py`'s
own. It caught something no rendering would have shown: **KiCad does not join a
pin that merely lies part way along a wire.** A bus drawn as one long line with
pins standing on it silently leaves those pins off the net. Trunks are drawn in
segments between their pins now, so every pin is a wire end. Two smaller things
came out the same way — a pin's angle in a KiCad library points INWARD, back at
the body, so taking it as the outward direction put every ground symbol inside
the part it grounded; and a field's angle is relative to its symbol, so a
rotated part printed its value up the page.

**The board cannot be built from Indian shops.** The bill had carried the word
*generic* against most of this board since it was drawn, and sourcing it found
that five of its lines have no Indian source at all. Two of those must be
imported and there is no honest way round either: the **four-terminal shunt** is
stocked by nobody here in any package at any resistance near 1 mΩ, and a
two-terminal substitute puts a few milliohms of lead and solder in series with a
1 mΩ element, which is most of a 24 mV reading; and the **P-channel MOSFET** has
one domestic alternative that meets the voltage and current, the IRF4905, whose
20 mΩ against the design's 6.7 is 4.7 W per device at 24 A with the tabs bolted
to nothing.

The other three are softer. **BAT46 Schottkys** are unobtainable and the
substitution was measured rather than guessed: silicon 1N4148s in their place
shorten the hold-through from 0.97 s to 0.84 s, which is survivable. The
**BZX79-C15** has a stocked equivalent in the 1N4744A, in a fatter DO-41 body
that wants a footprint check. The **14.7 kΩ 1 %** turned up nowhere, and it is
one of the two resistors that set the cutoff voltage.

**And one thing is unconfirmed rather than missing, which may yet cost a board
revision.** No Indian resistor listing states a body size. The ordinary 1/4 W
part sold here is the 0207, 6.3 × 2.5 mm, against the 0204 the layout is drawn
around — and twenty-three of them stand upright on a 2.54 mm pitch, which is the
choice the whole floorplan rests on. That wants checking before the board is
ordered, not after.

Validation: the drawing's netlist matches `power.py` pin for pin as KiCad reads
it, KiCad's ERC is clean, the board's DRC is unchanged at zero errors and zero
unconnected, CAD build and lint are clean and gates A–F pass. Nothing has been
fabricated, nothing has been ordered, and the peak bus current has still never
been measured.


## 2026-09-16 — Replace the invalid axial shunt with PBV-F1

The power board's 1 mΩ axial placeholder used a Vishay CPSL footprint, but
that discontinued family starts at 10 mΩ. R1 is now the orderable
**Isabellenhütte PBV-R001-F1-1.0**, preserving the entirely through-hole
assembly requirement. DigiKey India listed 442 at ₹4,144 each; its advertised
10 W requires a heatsink, so this design uses the manufacturer's **3 W** rating.
The manufacturer PDF is archived in reference/Isabellenhuette_PBV.pdf.

The 1 mΩ value is retained: 24 A produces 24 mV / 0.576 W, and 30 A produces
30 mV / 0.900 W. Both fit the INA226's approximately ±81.92 mV ADC range with
2.5 mA raw resolution. Documented firmware settings are 2 mA Current_LSB,
CAL=2560 (0x0A00), and 50 mW Power_LSB. No firmware was programmed. The module's
R100 must be removed before connecting the Kelvin pair; the previous text
understated its parallel-loading error and incorrectly treated it as optional.

A local footprint follows PBV drawing Z-DW-132b: I-U-U-I at 0, 5.08, 12.70,
17.78 mm. The power pours, CAD station and body envelope were updated. The
20.7 mm installed height leaves 1.10 mm to the deck. Gate F's existing check
measured the entire power-parts group while calling it the switches; it now
names the PBV and checks its intended 1.10 mm gap. The TO-220 clearance remains
3 mm. There is no change to printed geometry or the board outline.

Mass allowance rises **6 g**, from an unsupported 2 g axial placeholder to an
8 g provisional PBV allowance. This is not a measured mass. The full budget is
2,083.4 g against the 2,300 g ceiling, leaving 216.6 g.

Validation: schematic netlist matches power.py; ERC has zero violations. The
rebuilt PCB has 99 tracks and 57 vias, zero DRC errors and zero unconnected
items; 11 unrelated silkscreen warnings remain. Per-part PCB/CAD collision
checks pass. The 30 A measurement and dissipation checks pass and reject a
10 mΩ substitution. The shunt selection does not raise the board's MOSFET
continuous-current rating, and the prior review's startup and regeneration
issues remain outside this change. Plated lead fit and installed thermal
behavior have not been physically verified.

Final validation: `uv run tools/check.py` passes, including CAD builds, lint
and formatting; `uv run tools/gate_f.py` passes all 850 checks.

## The loop key comes out and a button goes in, 2026-09-16

**Asked for directly, and it reverses a decision this project had argued for in
writing.** `docs/BOM.md` carried a section called "why the disconnect is a loop
key and not a switch", and the half of that argument about amps still stands: no
12–16 mm panel switch will CARRY 24 A, so a switch can only command the bus, and
the power switch board is what commands it. What has gone is the second half —
that the wall should keep a pull-link beside the button anyway, because a MOSFET
usually fails shorted and silently and nothing but a mechanical break would say
so.

**Three things decided it.** A wall carrying both a switch and a pull-link asks
the user which one turns the robot off, and two controls for one job is how a
robot gets left on. The button had nowhere else to go. And the standing-current
worry turns out not to exist: with the switch off there is no DC path from the
pack through this board at all — every divider, comparator and reference hangs
off the switched side — so a pack left connected is drained by its own leakage.
That was checked rather than assumed.

**The station moved, and the depth behind the wall is the whole reason.** The
disconnect sat at x 18 with **11.2 mm** of clear air behind it before the
actuator harness bank's mated plugs. That is enough for a connector reaching
8.3 mm in and is not enough for any panel switch, which is a bushing, a body and
its terminals. The wall was swept at the station height for the depth a round
bushing can reach: 11.2 mm at the old station, 18.6 mm over the SBC, and
**21.4 mm** outboard of x −44, where what stands in front is the WeAct core
board on the far side of the carrier. So the button is at x −44 and the CAD
reserves 16 mm of it, leaving 5.4 mm.

**The part is a 12 mm and not a 16 mm anti-vandal, and that follows from the
same figure.** Common 16 mm switches are 21 to 27 mm behind the panel and would
not clear 21.4 with anything in hand. The one candidate anybody publishes a
dimensioned drawing for is a Daier GQ-12B/S: 12 mm hole, M12 × 1, momentary,
screw terminal, **21 mm from its dome to the tip of its terminal**, ₹190 and in
stock in Mumbai. No listing anywhere states a behind-panel length, so that 21 mm
is the only real figure and the 16 mm reservation errs deep against it. Measure
one before the pelvis is printed.

**The wall lost two screw holes and its thinnest material with them.** A button
mounts on its own thread, so the M2 pair 20 mm apart that held the disconnect's
ears is gone, and with it the 1.45 mm bridge between each of those screws and
the cutout — which was the thinnest material anywhere on this shell. What is
left is the charge socket's own 1.7 mm.

**What it costs is stated rather than buried.** Nothing isolates the pack any
more except unplugging one from the series harness with the lid off. A
failed-short MOSFET looks exactly like a working one, and there is no longer a
hand-operated break to prove otherwise. If that is not acceptable the fix is not
to put the key back in this wall — there is no depth for the button anywhere
else on it — but to make the pack's own in-shell connector the service
disconnect and say so in the build notes.

**The geometry is 4.83 mm³ and the arithmetic matches to four places.** A Ø12.2
hole through 2.4 mm of wall is 280.5568 mm³; the rectangle and two ear holes it
replaces were 275.7307. Gate B's register carries the split against the golden —
−4.0218 added, 0.8044 removed — and that split was MEASURED rather than solved
for: the shell was built twice, once with the disconnect put back, and each
differenced against the golden. Both holes are cut almost entirely in wall the
golden never had, which is why a 280 mm³ hole reads as 0.80 against it.

**One correction that arrived from elsewhere in the same pass, and it matters
more than the button.** The bus shunt had been specified as a Vishay CPSL axial
part, and **that part does not exist at this value** — the family starts at
10 mΩ, not 1 mΩ. It is an Isabellenhuette PBV-R001-F1-1.0 now, four inline
through-hole pins on a footprint drawn from the maker's own Z-DW-132b, standing
20.7 mm tall with 1.1 mm over it to the deck. The board was laid out to a
footprint for a shunt nobody makes.

Validation: gates A–F pass at 850 clearance and fastening checks, CAD build and
lint clean, the netlist and its arithmetic check, the schematic's netlist still
matches `power.py` pin for pin as KiCad reads it, ERC clean and the board's DRC
unchanged at zero errors and zero unconnected. Mass 2083.4 g against the 2300
ceiling — the 6 g is the shunt's re-specification, not the button, which is
0.005 g. Nothing has been fabricated and no switch has been measured.

## The current measurement is deleted — 16 September 2026

**There is no shunt on the power switch board and no current measurement
anywhere on this robot.** The entry above had just re-specified R1 as an
Isabellenhütte PBV-R001-F1-1.0 after the Vishay CPSL footprint turned out to be
for a part nobody makes at 1 mΩ. That correction was right, and pricing it is
what made the case for deleting the whole function: €14.22 at Bürklin, $18.60 at
LCSC and out of stock, $43.37 at DigiKey, and no Indian stock of any
four-terminal shunt in any package. The rest of that market is two parts, the
Ohmite CS3FR001E at $29.65 and the Riedon PCS-0R001D1 at $39.40, so the PBV was
already the cheap one — and it would still have cost more than everything else
on that board put together.

**Nothing was protected by it and nothing is lost that protects.** The
low-battery cutoff is a comparator on bus VOLTAGE and never looked at current.
All six actuators report torque in their own CAN feedback frame, referred to the
output shaft, so a straining joint stays visible. The INA226 stays on the carrier
and reads the bus on its VBS pin, which never went through the shunt.

**What it would have bought was the runtime figure**, which is a characterisation
taken once on a bench rather than fitted telemetry: a clamp meter round the pack
lead through a first stand and a first drive answers it as well. **What is given
up is coulomb counting**, which nothing here does yet; the way back is a
two-terminal shunt on a future revision with a software calibration.

**Measured rather than asserted.** The netlist is 49 parts, 108 pins and 24 nets,
where it was 51, 114 and 27: R1 and its sense plug J1 are gone, and VDRN and
VBUS — two pours with the shunt bridging them — are one pour from both MOSFET
drains to the output pad. The board keeps the bought board's 50 × 50 outline, so
the gain is room and not size: about 250 mm² of courtyard out of the middle of
the bus path. It shows in the result — 97 tracks and 58 vias against the same
board's 107 and 66, KiCad DRC 0 errors and 0 unconnected on the filled board,
and every pad where the layout meant to put it. The schematic carries the
netlist pin for pin and ERC is clean. Mass 2075.4 g against the 2300 ceiling,
which is −8 g, the whole of it the shunt's allowance.

**Two loose ends.** The carrier's J7 is a header with nothing to plug into it,
and the monitor's IN+ and IN− behind it are floating — link them to ground at the
plug rather than revising a board already at a checked fabrication release. And
the standing instruction to lift the INA226 breakout's own R100 is withdrawn: it
existed only to keep that 0.1 Ω out of parallel with the external Kelvin pair.

## 2026-09-21 - Power-board C1 reset

Replaced the slow R24 reset path with Q5/R25/R26 and a source-to-gate C7.
The board remains through-hole and the current shunt remains deleted. The
original soft-start timing components remain; D2 and D8 now use BAT46.
`electrical/power_reset.py` reproduces the old cold-start failure and passes
26 revised cold-start/restart cases in a simplified ngspice model. Maximum
modeled capacitor charging current is 1.419 A. Turn-off is 0.785 ms nominal
and 5.557 ms in the additional adverse case; the old microsecond claim was
invalid and is removed. Loaded switching SOA and temperature/leakage limits
remain unverified, as do the separate held-button UVLO and regeneration issues.

The schematic passes netlist comparison and ERC. The board has 111 tracks,
67 vias, zero DRC errors and zero unconnected nets; 13 silkscreen warnings
remain. Placement clears the torso geometry. The project build and mass check
pass: +2 g unweighed component allowance, total 2077.4 g against 2300 g.
See POWER_SWITCH.md for component sources and the regression's limits.

The broader mechanical clearance suite also passes: gate F, 850 checks,
including 741 body pairs with no shared volume.

## The robot gets something to be hung from — 22 September 2026

**Two hoist lugs on the pelvis flanks, 9.3 g, so a topple during development is
caught before it reaches the floor.** This is the first thing printed into the
robot that is there for the bench rather than for the machine, and the case for
it is already measured in this file: a sideways topple releases 2.85 J and
arrives at 1.65 m/s, the limb's worst section stores 0.21 J before it fails
across the layers, and on a hard floor the margin is 0.44x. The robot survives
falls because the floor gives, not because anything on it is tough. A balancing
machine falls over as a matter of routine during bring-up, so the choice was a
catch or a supply of spare limbs.

**It is not on the lid, and that decision is the whole of the design.** The four
cover bosses are the strongest anchorage on this box — each is a corner column
merged into two walls, with 12 mm of thread-forming M3 — and they were the
obvious answer until the electronics deck was measured against them. Their
screws stand 4 mm inboard of the cavity edge, and `cad/deck.py`'s deck is
148.3 mm wide in a 149.1 mm opening with 0.4 mm of drop clearance: it lifts
straight out or not at all. Anything reaching those screws overhangs the mouth
and seals the battery in, which is exactly the access that running with the lid
off was meant to buy. So the attachment had to go outside the shell, and that
meant changing the pelvis print rather than bolting a fixture to it.

**The flank was free.** Each side wall is plain 2.4 mm shell from the top of the
hip saddle at 286 mm up to the rim at 357.6 — the cable ports are in the floor
and every connector is in the back — and the whole lug stands outside the
153.9 mm the lid covers, so the lid still fits over it.

**Long fore-aft rather than tall, and flush with the rim**, because the lug is
hanging the wall rather than hanging off it: the load crosses into the wall and
runs down it to the floor the hip clevises are rooted in, and 30 mm of length
feeds it into 30 mm of the wall's width at once. The underside is relieved at
45° so the wall does not meet a square step. None of it is near a limit — at ten
times the robot's weight the wall sees under 1 MPa against the 30 this project
assumes across the layers — so every number is about where the load goes and not
how much of it there is.

**And the outboard face lands at ±88.95 against wheels at ±104**, so the lug
never touches the floor first in the topple it exists to catch. That is the same
test the limbs' cable-tie arches were moved inboard to pass.

**Both mouths of the eye are broken 45° out to Ø8, and that break is drawn into
the part rather than left to the finish pass.** `cad/finish.py` takes outer
edges only — an edge is chamfered when every face it touches is flat or the
outside of a round — so by construction it never sees the rim of a bore, and the
eye came off the printer with two sharp rims that the finish report counted
among the 77 it skips. Every other bore on this robot is a bearing seat or a
clearance hole and wants a sharp mouth; this is the only place on the machine
where a rope turns over a printed edge under load. So it belongs in the geometry,
where gate B holds it to 41.89 mm³ across the four mouths, rather than in a pass
that could drop it silently.

### How it is meant to be used

The two lugs are a bridle, not a single hang point, and the kinematics are the
reason. Hung from two cords to one ring with a swivel at the ring, the robot is
free to pitch about the line joining the lugs — 148 mm above the centre of mass
at 202 mm, so it hangs upright and rights itself — and free to yaw, so it can
still steer; but roll is held rigidly by the triangle. That matters more here
than it would on most robots: this branch has no hip roll at all, so sideways is
the one direction the machine cannot recover in.

Above it, a rigid bar rather than a wire. A 2 m wire loaded in the middle during
a catch sags tens of millimetres, which is several times the whole slack budget,
and the robot is past 30° before the line notices. Set about 10 mm of slack: the
lugs are 350 mm up, so ten millimetres of droop lets the robot reach 13° of
pitch before the cord takes any load, which is outside anything a working
balance controller should do and inside the angle where it is committed to
falling. Catching at 13° releases about 0.1 J, so the peak on the cord is under
30 N — the forces are nothing, and the whole difficulty is keeping the slack
small. Horizontal travel eats it: stay within about 100 mm either side of the
bar's line.

Two things belong with it and neither is CAD. Put 20–25 mm of foam down anyway —
the table above puts the limb at 0.44x on a hard floor and 11x on foam, which is
the cheapest protection available. And the tether catches the robot without
stopping it, so a caught robot hangs there with its wheels still driving; that
wants a torque cutoff past about 20° of tilt, which the IMU already seated in
the pelvis can drive.

---

## The battery was drawn from a pack nobody makes — 30 September 2026

The bay was sized for "a Gens Ace class 3S 2200 mAh brick, 76 x 33 x 25 mm and
144 g", two of them on edge. No such pack exists. Every 3S 2200 mAh pack on sale
in India is 105 to 108 mm long: GenX 105 x 34 x 25 and 184 g at Indian Hobby
Center, the same pack listed 108 x 35 x 22 at Robokits, Bonka 105 x 34 x 25 and
175 g. Seventy-six millimetres is the length of a 1000 to 1500 mAh pack. The
2200 mAh pair would have missed the bay by 30 mm, and the power bay beside it
leaves nowhere for the extra length to go.

The bay stays and the pack comes down to it. What fits and was on a shelf on
the day is a Bonka 11.1 V 1000 mAh 35C at Indian Hobby Center: 75 x 32 x 17 mm
and 95 g by ElectronicsComp's listing, the only published figure for it. Bonka's
1300 and 1500 mAh packs are the same 72 mm long and would give 60 to 68 % of the
planned energy, but none of the shops that could be read had either in stock.

| | Planned | Now |
|---|---:|---:|
| Pack | 2 x 3S 2200 mAh | 2 x 3S 1000 mAh |
| Energy | 48.8 Wh | 22.2 Wh |
| Cells | 288 g | 190 g |
| Continuous current | 77 A | 35 A |

35 A is still well over the 24 A the six actuators are estimated to draw at
once, and the 20 A fuse is below both. What it costs is runtime, by a little
more than half, and a harder sag under load: 24 A is 24C on this pack where it
was 11C. The training's battery range, 0.75 to 1.05 of the rated voltage, still
covers that sag.

**Nothing held the packs, either.** The deck was said to bear on 3 mm of squeeze
over them, and the 3 mm was air: a pack could lift 3 mm, slide 2.5 to 3 mm
endwise and swing its foot 7 mm towards a wall. The two cinch straps meant to
back it up had no route: one strap lane led into the left hip saddle, the other
into the CAN loom and the actuator harnesses, and no 20 mm lane along the packs
cleared everything by a millimetre. So each pack is now held on all six sides:

- down, on a rail under it, moved inboard to stand under the thinner pack and
  shortened to start at the left hip saddle, whose own top carries the packs
  over its length. Run through the saddle's hollow, the rail sealed a void inside
  it, and `tools/check.py` refused the pelvis for it;
- to the right, on a 5 mm stop on the rail's end, which catches the foot of the
  end face and leaves the top of it to the leads;
- towards the other pack, on a 2 mm fin hanging from the deck between them;
- outwards, up and to the left, through 5 mm EVA foam against a fence hanging
  from the deck, the deck itself and the left wall.

The foam is drawn squeezed and `tools/gate_f.py` checks every face touches and
no piece is squeezed past half. It is also what takes up the difference between
the pack drawn and the pack bought, which nobody has measured. Measure one first:
the rails, the fences and the stops all follow the three pack dimensions in
`cad/electronics.py`, so a measured pack is a change to three numbers.

**Later the same day the fin and the fences came off the deck and onto the pelvis
floor.** Hanging from the deck, they had to find the 2 mm between two packs that
nothing had yet placed fore and aft, under a plate carrying both boards, and the
side foam was dragged down each pack's face on the way. Standing in the pelvis
instead, they make each pack a slot of its own that it
is pushed into by hand and in sight, so both packs are held on five sides before
their leads are plugged or the BMS goes in beside them, and the deck brings only
the pads over them. The fin stops at the IMU's reservation, so it covers 60 mm of
each pack's 75, and the fences are 1.5 mm rather than 1.6 because the rear one
stands against the actuator harness run. It costs 3.2 g on the robot and a pull
tab of polyimide tape under each pack, because the foam grips the pack and
nothing leaves room for fingers beside it.

**The fences were first drawn standing on nothing for most of their length, and
no gate saw it.** They stood on the left hip saddle's top over the saddle's
length, on the strength of its bounding box, which reaches 26 mm either side of
the centre line. Its top reaches 15 and the fences stand at 21, so 45 mm of each
hung 9 mm over the floor off the 30 mm that did reach it. It was one solid, so
the export and `/check` passed it; every layer of it touched the layer below
somewhere, so gate G found no island; and nothing was drawn where it should not
be, so gates F and H had nothing to measure. It was seen in the viewer. The
fences now stand on the floor end to end, and gate F has a new check,
`check_footings()`, that measures the underside of every rail, fence, fin, post,
guide and seat standing in the cavity and fails any that does not rest on the
pelvis all the way along. Run against the first drawing it reads 40 % for each
fence. `tools/gate_i.py` now puts the side
foam in before the packs and pushes each pack down between the fin and its foam.

## The deck ledges were a millimetre too shallow for their screws — 30 September 2026

The four M2.5s that hold the electronics deck down were drawn in place for the
first time, against the shell, the ledges, the deck and everything standing in
the torso. The heads fit: a 4.5 mm socket cap clears the wall by 0.5 mm, which is
what the ledges were drawn to leave, and 5 mm of thread is engaged, twice the
screw's diameter. What did not hold up was the plastic round the thread. The
screw is placed by its head, so it sits 2.75 mm off the wall, and a ledge 5 mm
deep left its cavity-side face 1.0 mm outside the thread the screw cuts, under
the 1.25 mm or so a self-cut thread in plastic wants. A firm tightening would
have split that face.

The ledges are 6 mm deep now, which leaves 2.0 mm, for 0.2 g on the four. They
come 0.6 mm from the battery and power bays' reserved space rather than 1.6, and
nothing drawn in either bay is within 5.5 mm. The head bears on only 41 % of its
underside, because the deck's clearance hole has to run out to the plate edge
as a slot, and no washer fits in the half millimetre beside the wall, so these
four are tightened gently.

The same drawing showed the two rear screws sitting directly under the on/off
button and the charge socket. That is why those parts come out before the deck,
and it means a notch in the controller carrier would not free the deck on its
own.

## Every fastener comes off a shelf — 30 September 2026

The robot's fasteners were sourced from three carts, and one of them was MISUMI,
for a single length: the M3 × 14 the motors' rear screws took through a 6 mm
plate, which no hobby shop stocks in 12.9. Working out how to lose it found that
the bill had those screws wrong for half the joints. It listed sixteen M3 × 14
for "knee and wheel", but the knees have been straddled clevises since
13 September, and a clevis's rear cheek is 3 mm, like the hips'. There, an
M3 × 14 on the 1.5 mm of washers the bill gave it would have bottomed about
2.5 mm before it clamped, and no gate could see it, because screws are not drawn.

So the hips and knees take an M3 × 10 on one 0.5 mm DIN 125 washer, which leaves
the 3.3 mm of thread the M3 × 12 on 2.5 mm of washers did. The wheel motors' 6 mm
plate carries a 1 mm spot face at each of its four rear screws, so an M3 × 12 on
the same washer takes the 3.3 mm the M3 × 14 did. The first cut of those spot
faces lost 1.8 mm³ to the shin's waist, whose end stops a cap head short of the
two nearest bolts and so 0.4 mm inside their spot faces. Gate B's figure came out
143.3 mm³ removed against 145.1 of arithmetic, which is how it was found, and the
waist now takes the same four cuts from `cad/joint.py`'s `statorPlateSpotFaces()`.
The output screws default to M3 × 8, because the vendor STEP shows 6.5 mm of
thread, with 40 M3 × 6 bought as the fallback.

The two fasteners nobody stocks are designed out rather than imported:

- **The journal's DIN 433 5.3 × 9 × 1 washer**, an import at ₹2,538 for thirty,
  was a 1 mm spacer under the screw head that kept the tip off the motor. The
  printed sleeve is 1 mm longer now and stands that far past the bearing, so the
  head sits exactly where it did, clamping the same sleeve. Gate F checks that
  the head lands on the sleeve and clears the bearing by 1.0 mm.
- **The power switch board's four Ø6 × 8 unthreaded spacers** were in nobody's
  stock: Robu's 8 mm nylon ones were sold out, and fastdep's aluminium ones come
  in 5, 10, 15 and 20. They are printed PA12 tubes now, `power-switch-spacer`,
  with their bore asserted open by gate E.

The M5 thin nut is an ordinary M5 nut filed to 2.7 mm, which is the height the
pocket was drawn for. Every M3 is a fastdep 12.9 in a pack of ten, and every M3
washer is the ordinary 0.5 mm one. The robot is 0.1 g lighter for all of it.

## The power switch board's parts are ones that exist — 1 October 2026

Putting the bill into carts found three of the power switch board's parts gone.
ST no longer makes the BAT46 in DO-35, nor the BAT41 or BAT48, and every BAT46
still stocked is surface mount; the WIMA MKS2 that was C7 is discontinued; and
the 14.7 kΩ 1 % and 680 kΩ are stocked only in the 0207 body, where the board is
drawn around the 0204. The board stays through-hole: the six BAT46 are 1N4148,
the part already at D3; C7 is KEMET's MMK5, the same 7.2 × 7.2 × 13 mm; R12 is
15 kΩ 1 % and R2 is 1 MΩ. C1 and C2 now name the parts bought, and C1's
footprint is KiCad's 7.2 mm film footprint, because the 7.0 it had is a size
nobody sells.

`electrical/power.py` computes what that does: the cutoff falls from 3.20 to
3.14 V a cell, the hold-through from 0.97 to 0.90 s, and the gate drive at an
18 V bus rises from −10.6 to −12.2 V. All inside the limits it holds them to.
The cost is in `power_reset.py`, whose switch-off cases all still pass with a
worst capacitor peak of 1.97 A against 2 and an adverse turn-off of 8.1 ms
against 10, where they were 1.85 A and 5.6 ms; the diodes' extra drop is most of
it. The schematic matches the netlist with a clean ERC, and the board routes with
zero DRC errors.

## The battery packs, measured — 5 October 2026

Both packs arrived and were measured. They are 77 × 38 × 19 mm at most, where
the only published figure, ElectronicsComp's listing, said 75 × 32 × 17. But
the pack is not a brick of that size: the 65 mm furthest from the leads is
within 35 × 17, and only the last 12 mm, where the tabs fold under the wrap and
the leads come out, grows to 19 × 38. Nobody knows which faces that extra sits
on, so the design has to clear it whichever way it falls.

So the pack is drawn as two blocks, a 65 mm body and a 12 mm lead end, and
every printed face and piece of foam that bears on a pack from beside stops at
the 65 mm. The rails stand full height under the body only, then drop to a sill
a millimetre under the lowest a lead end could reach, and end in the stop. The
fences end at the body. The side strips and the top pads stop 2 mm short of it.
The fin already ended inside it, at the IMU. The one face that touches a lead
end is the stop, end-on, past the 77 mm, so whatever the end's shape it is
never alongside it. Gate F now tests each lead end as the box it could fill if
all of the extra were on any one face, and holds every printed part and every
piece of foam to sharing none of it.

The height is the real cost. A 35 mm body under the same 4 mm of squeezed foam
is 39 mm, and a lead end up to 38 mm tall needs that too, with a millimetre to
spare if all of its extra is on top. At the old 36 mm band it would have run
into the deck by up to 2 mm. The band went to 39, the torso from 86 mm to 89,
and the robot from 360 mm to 363. The 3 mm went in under the deck, so
everything above it — the boards, the rear-wall connectors, the cover — rose
with it and kept its place, and the hip axis and legs have not moved.

Lengthwise the pack grew towards the left wall. Its lead end sits at the bay's
end, 1.5 mm further right than before, which squeezes the end pad to 3 mm, the
same 40 % as the side strips, and puts the stops 2.5 mm into the bay gap. The
balance tails used to lie over the packs' ends before turning down to the BMS;
the lead end took that air, so they now leave the end face and come straight
down the 3.05 mm between the packs and the BMS's slot. That gap was 4.55 mm.

Fore and aft, two lead ends at the full 19 mm meet in the middle. If more of
the extra is on the inner faces than the outer, the pair want up to 2 mm more
than the fin leaves and will splay outwards, where nothing stands beside them.
That is two wrapped ends pressing on each other, and harmless.

The pelvis is 3.1 g heavier, nearly all of it 3 mm more wall: 2 008.2 g against
the 2 300 g ceiling. Gates A to I pass, and the simulation model was rebuilt
from the re-exported meshes and agrees with the CAD.

## The battery packs, the BMS and the series harness, weighed — 5 October 2026

The first bought parts on the robot to go on a scale. Each pack is 86 g, against
the 95 g of ElectronicsComp's listing, so the pair is 172 g where 190 was
carried. The Daly BMS is 40 g, against the 45 g of its own vendor's table. The
XT60 series harness that joins the packs is 23 g; it had no figure of its own
before, only a share of the 68 g battery-wiring estimate, so it now has a line of
its own and that estimate is the 45 g that is left, not re-estimated.

That is 23 g off the robot: 1 985.2 g against the 2 300 g ceiling, 314.8 g of
headroom. The simulation model carries the three as weighed parts, a provenance
it did not have until now, and they are 235 g of it, 12 % of the robot.

## The charge inlet is male, and the female is on the charger's lead — 5 October 2026

The robot's charge inlet is an AMASS XT60E-M now, the eared male panel mount
the main disconnect used to be, and the charger's lead ends in a female XT60.
It was the other way round for three weeks, for a reason that still holds: the
inlet lands on the BMS's charge input, so it is live at pack voltage whenever
the cells are connected, and the half with the pins is the one that would rather
be dead. The female is on the lead by choice, because the lead is live only while
the charger is on. What that costs is two shrouded pins at up to 25.2 V on the
back of the robot with nothing fused behind them, and whether the BMS cuts a
short on its charge input is untested.

The male mounts the other way round from the female: its ears bear on the
inside of the wall and its nose comes out through a 14.7 × 7.2 cut, so it goes
in from inside, after the deck, and that is what decided where it is. It has to
stand 8.4 mm off the wall with nothing in the way before it can come down, and at
the female's x 55.5 its ear plate sat 3 mm into the actuator harness bank's
plugs. Inboard of x 58.45 the ears meet those plugs, and outboard of 59.45 the
nose meets the rear right cover boss, so it is at x 59.0, half a millimetre from
each. There its rear body stands 0.2 mm under that boss in plan, so it is also a
millimetre below the row, at z 22.5, which leaves 0.75 mm. Inside the cavity it
is an ear plate 27 mm across, x 45.5 to 72.5, from the inner face to 3.2 mm off
it, and behind that a 15.5 × 8.1 body whose solder tabs end 8.3 mm off the
inner face, where the female's reached 14.7. The bridge between the cut and each
M2 screw is the disconnect's 1.45 mm again. The controller carrier's notch,
which was cut for the female's body, now has nothing over it and stays.

The pelvis is 298.9 mm³ heavier, the female's larger cut put back less the
male's: 0.3 g, 1 985.5 g against the 2 300 g ceiling. Gates A to I pass, the
carrier board's clash check passes, and the simulation model was rebuilt from
re-exported meshes and agrees with the CAD.

The male panel mount is AMASS's XT60E-M.G.Y at Evelta, ₹54.28 and 98 in stock,
to go into the Evelta cart beside the buttons, and the Probots cart, which holds
only the two female sockets, is to be emptied. Neither change is made: the
browser could not be reached. The charge lead is a female XT60 pigtail and a
pair of 4 mm banana plugs from QuartzComponents, or QuartzComponents' ready-made
female-XT60-to-banana lead; docs/BOM.md has both.

## Room for the battery's wiring — 5 October 2026

With the BMS and a pack in hand it was plain that the torso had no real room for
the battery's wiring. Two things were wrong. The BMS's leads leave its two short
ends — B-, the NTC pair and P- at one, the 7-way balance socket at the other —
and standing on edge in the gap between the battery and the power board, those
ends faced the shell walls 4.6 mm away. And that same board was a wall across the
only path the packs' main leads had to the power board. The leads are 14 AWG and
stiff, they leave the pack's end face, and they had 3.5 mm before they met it.

The BMS now goes between the two packs. The packs and the board are one block,
45 mm across, which the builder assembles and the torso is laid out to. The
board's power end sits at the packs' 65 mm body line, so its three leads leave
through the 7 mm between the two lead ends. Its balance plug end is 10 mm off
the left wall, and the thin balance wires fold up over its top edge from there.
The board's floor guides and the deck's top guides are gone, and so is the fin
the board replaces.

The gap between the battery and the power board is cleared, and it is the
battery's wiring space now. Each pack's XT60, mated with one male of the series
harness, is a rigid block about 30 mm long and 15.6 × 8.1 across. That block,
not the wire, was what had nowhere to go. It now lies in the strip between the
block of packs and the long wall beside it. The pack's leads turn into it
through the gap at about an 8 mm radius. The harness's legs leave its far end,
turn up over it and run back along the top of the strip to the gap, which they
cross to the power board. There is no third XT60 pair, because the harness's
own female output is cut off and its two legs are soldered to the power switch
board's input and the distribution board's negative.

For the strips to be clear, the battery's two fences had to go. They stood on
the floor the whole length of each pack, which took the strip from the bottom
up, and the rear one sat on the actuator harness that runs along the back of
the floor. Eight small pads off the two long walls bear on the side foam
instead. The low ones sit just clear of the harness, on 45-degree undersides so
they print upright, and the connector lies over them. The high ones are at the
left, where the connector isn't. The side foam is cut to the pads, so at the
connector's height the strip is clear from the block's face to the wall. The
CAN loom moved from that strip to the back of the gap, and the rail end stops
came down 2 mm, clear of the pack's bottom lead.

All of the wiring is drawn as space for it rather than as wire, as one group
the gates hold everything else out of. None of it is proven against the real
leads yet: the layout asks about 50 mm of each pack's 76 mm and about 100 mm of
each harness leg. The pelvis is 9.1 g lighter and the deck 0.2 g, for
1 976.2 g against the 2 300 g ceiling.

## Separate positive landings for the battery and charge inlet — 8 October 2026

P1 takes the series harness's positive and P5 takes the shell XT60's positive,
each through its own 2.4 mm plated hole in a 4.4 mm pad. Both belong to BATT,
before the main fuse and switch. P5 stands at torso (39, −21.5) beside P1 at
(33, −21.5); the fuse holder moves 6 mm outboard and 1 mm rearward to make
room and clear Q2's courtyard. The BATT pour
extends with it and the VSRC pour starts farther outboard, leaving the gate
band and its parts in place. The board outline and printed geometry do not
change, so the printed mass delta is zero; the extra wire is part of the
existing harness allowance.

The negatives do not join at the charge inlet. The series harness's negative
lands on P3 and BMS B− on P4, both GND. The inlet's negative goes only to BMS
P−: joining it directly to board GND would bypass charge protection. The
schematic passes netlist comparison and KiCad ERC, and the project build,
lint and formatting checks pass. KiCad DRC reports zero errors and zero
unconnected nets, with 12 silkscreen warnings. P1 to P5 measures 5.39 mm of
copper at its narrowest against the 2 mm check; the existing motor and bank
paths also pass. Gate I passes all 13 assembly steps. These are design checks,
not bench results.


## Antenna clearance and original button location - 10 October 2026

The button is back in its original rear-wall hole (x -44, z 23.5), at the
owner's request. Both hoist lugs are their original shape again. The SMA is on
the left flank at y -21.5, z 21: 1.5 mm rearward of the first side station.
A 12 mm antenna base clears the left lug by 2.262 mm over the full lug depth,
including a conservative base starting at the shell face. The check reserves
2 mm radial margin, equivalent to a 16 mm diameter envelope.

The SMA opening remains a single D, flat down: 6.50 mm diameter, 6.00 mm
flat-to-opposite-arc span, matching the Amphenol 132203 panel drawing:
https://www.amphenolrf.com/en-us/assets/file/4065789559/
The supplied 9.5 mm internal diameter is modelled as an inner shoulder with
the existing provisional 15 mm inward depth. Its axial dimension still needs
measurement. Such a shoulder cannot pass through the hole from outside:
the SMA now installs from inside and the retaining nut goes outside. It goes
in before the rear button body, which otherwise blocks its inward path.

The united as-drawn shell is 2.817 mm3 (0.003 g PA12) heavier than the original
rear-panel design; restoring the lug and button adds 0.082 g versus the first
side-controls design. The fitted antenna's full length, angle and any larger
hinge or collar still need checking for fall protection.
