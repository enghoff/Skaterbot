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

- **6 x M3 on a Ø24 mm bolt circle**, at the bottom of a **Ø30 mm register recess** about 3 mm deep, with a shallow concentric Ø8-10 mm bore. This is the rotating output, and the recess makes it a self-centring spigot fit.
- **4 x M3 on a Ø41 mm bolt circle** at 90° spacing, on the stationary housing outside the register.
- The Ø42 mm circle carries the actuator's own M2.5 assembly screws. It is not a mounting pattern.

**Which face is the output is now settled.** The rear third of the actuator is a plate / driver-PCB / plate stack, which must be stationary because it is what the cabling terminates on. The Ø41 pattern sits on the outer housing beyond the register, so it is the stationary mount. Everything inside the Ø30 register — the Ø24 bolt circle and the central bore — is the rotating output. So one link bolts to the outer circle and the other to the concentric inner circle, both from the front.

**There is no through-bore.** The central features are only about 3 mm deep from the front face, and the rear face carries nothing within Ø20 mm of the axis. A through-shaft, which would have carried joint bending independently of the actuator, is not available.

Two caveats. The STEP's main body is exported as an open-shell surface model rather than a solid, so it may not import as usable solid geometry. And its internal part names read `3505` rather than `3507` (the 2D print is likewise titled "DM 3508-7"), which appears to be the base stator designation reused, but confirm the envelope on opening it.

### Correction — the cable exit is not radial

An earlier revision of this file recorded a "radial cable exit 31.7 mm from the output face". That was wrong. The figure came from misreading plate `3505_00`'s placement origin as a connector location. **No part of the assembly projects beyond Ø46**, and there is no radial slot in the shell. The driver PCB sits at Ø42.1 inside the rear stack, so the electrical interfaces are on or near the **rear face** and the keep-out is axial rather than radial.

The STEP does not model the connectors themselves, so the exact position and the plug's protrusion are still unknown. They are in the manual's interface figure, which is a diagram rather than extractable text, so this needs someone to look at it or at a photograph of the part.

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

Two conditions on that recommendation. The shroud and its stub-axle boss have to clear the rear-face cabling, whose position is still unknown, so this cannot be detailed until the cable exit is located. And if mass gets tight, **double-supporting only the knee and ankle** — the four joints that see landing loads — halves the cost, leaving hip roll and pitch on shorter arms single-supported.

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

Zoo Design Studio here is a GUI application with no headless command line, so KCL edits in this repository cannot currently be executed, regenerated or visually inspected outside the app. The envelope correction described above is a reviewed text change and has **not** been regenerated. Open the project in Design Studio and re-run the neutral assembly and pose check before trusting it.
