# Initial Biped Skeleton Notes

## Architecture

- Overall neutral height: **380 mm**.
- Eight actuators: hip roll, hip pitch, knee pitch, and ankle pitch per leg.
- Hip spacing: **96 mm**.
- Hip-pitch to knee and knee to ankle: **105 mm** each.
- Feet: **115 x 65 mm** with a separate 2 mm sole and four sensor locations.
- Link choice: **Option B**, twin 8 x 8 x 1 mm carbon-fibre square tubes with printed end interfaces. This gives lower distal inertia than fully printed box links.
- Torso envelope: **126 x 74 x 106 mm**, with the battery reserved low near the hip axes.

## Actuator and yoke fit

The simplified DM-J3507-2EC envelope is 46 mm diameter by 37.9 mm axial depth. The reusable yoke uses a 46.6 mm internal diameter and 38.5 mm clear cheek spacing, giving nominal **0.3 mm radial and axial clearance per side**. Each pitch-style joint has two 3 mm annular cheeks, removable cross-straps, and a placeholder opposite-side support bearing.

The actuator STEP model and its real output flange, stator mounting pattern, connector, and cable exit remain authoritative when supplied. Those details are not guessed in this skeleton.

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

## Five priority weaknesses before refinement

1. **Hip-roll carrier and torso hip beam:** peak roll moments enter a solid printed hub and narrow rails. PETG creep and layer splitting are likely without a metal shoulder axle, large washers, and a cross-tied hip beam.
2. **Opposite-bearing alignment:** the two yoke cheeks must hold the motor output and support bearing coaxial. Printed bearing pockets alone can ovalize or misalign; use a metal through-shaft/shoulder bolt and accurately located bearing seats.
3. **Carbon-tube socket retention:** the current sockets are packaging blocks, not finished clamps. They need real tube pockets, anti-rotation geometry, adhesive bond length, and transverse M3 through-bolts rather than relying on inserts or butt contact.
4. **Ankle and foot impact path:** the added bridge rails connect the risers to the spine, but landing loads remain concentrated at printed riser roots. Add generous ribs and consider a thin aluminum cross-plate or continuous metal ankle axle.
5. **Moving cable loops:** space is reserved but final ducts, bend radii, and strain relief are not modeled. Knee and ankle CAN/power leads are vulnerable to pinching and fatigue until routed through guarded rear channels and tested across the mechanical stops.

## CAD limitation

The foot-frame members overlap as one printable connected set, but the current CAD engine rejected a multi-body 3D union. They therefore remain overlapping top-level bodies in `foot.kcl`; verify that the selected slicer merges coincident/overlapping shells before printing.
