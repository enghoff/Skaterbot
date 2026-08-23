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

Measured from the STEP and cross-checked against the 2D print:

- **Output face: 6 x M3 tapped 5 mm deep on a Ø24 mm bolt circle**, inside a Ø30 mm register and concentric bores around Ø8-10 mm.
- **Housing: 4 x M3 on a Ø41 mm bolt circle**, at 90° spacing.
- A three-hole pattern on a Ø17.5 mm circle near the centre of the output face.
- **Radial cable exit 31.7 mm from the output face**, so roughly 12.8 mm rear of the actuator's mid-plane. Its radial size has not been measured and remains a keep-out to resolve.
- Four M2.5 screws on a Ø42 mm circle entering the rear face are internal assembly fasteners, not mounting points.

Two caveats. The STEP's main body is exported as an open-shell surface model rather than a solid, so it may not import as usable solid geometry. And its internal part names read `3505` rather than `3507` (the 2D print is likewise titled "DM 3508-7"), which appears to be the base stator designation reused, but confirm the envelope on opening it.

## Yoke re-check against the real interface

Re-checking `pitch_yoke.kcl` against the measured interface changes the conclusion recorded here previously. The 38.5 mm clear cheek spacing against a 37.9 mm body still gives **0.3 mm of axial clearance per side**, so the envelope fit is sound and unchanged.

The problem is that the fit is not the constraint. Both cheeks are annuli bored to Ø46.6 mm to clear the actuator body, but **both real bolt circles — Ø24 mm at the output and Ø41 mm on the housing — lie inside that bore**. The yoke as drawn has no material anywhere the actuator actually attaches, so the 0.3 mm clearance is measuring a gap that carries no load. Turning each cheek into a bolted hub is the substance of the knee module task:

- the output-side cheek becomes a disc registering on the Ø30 mm feature and bolting to the 6 x M3 Ø24 pattern;
- the housing-side cheek picks up the 4 x M3 Ø41 pattern;
- the opposite support bearing needs a stub axle supplied by the yoke, because **the actuator has no rear spigot to run a bearing on**. This sharpens weakness 2 below from an alignment concern into a missing part.

The top and bottom cross-straps run the full 44.5 mm width at Ø54, so they need checking against the radial cable exit once the connector's size is known.

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
