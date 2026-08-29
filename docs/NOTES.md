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

- **Output hub:** Ø36 mm PETG hub, Ø30.4 mm x 1.2 mm blind register pocket for the Ø30 boss, and 6 x Ø3.4 mm clearance holes on the authoritative Ø24 mm output circle. Six Ø6.0 mm x 3.2 mm cap-head counterbores retain the heads. The 12.6 mm bolt-circle chord spacing leaves about 7.1 mm between Ø5.5 mm M3 cap heads.
- **Output fasteners:** 6 x M3 x 6 socket-head cap screws. From the modeled counterbore floor to the raised output-boss face is 1.8 mm, giving approximately 4.2 mm engagement in the specified 5 mm-deep output threads. At 6 Nm, equal sharing gives about 83 N tangential demand per output screw.
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
