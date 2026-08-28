# Biped Development Checklist

> **Superseded on 28 August 2026 by [`PLAN.md`](PLAN.md).**
>
> The robot is being rebuilt from this skeleton architecture into a stressed-shell
> one, so the open items below no longer describe the work. They are carried over
> or explicitly retired in section 9 of the plan. This file stays as the record of
> the skeleton design and of what was learned building it — in particular the
> actuator investigation, which the overhaul keeps in full.

## Initial skeleton complete

- [x] 380 mm neutral overall layout
- [x] Eight simplified DM-J3507-2EC actuator envelopes
- [x] Orthogonal hip roll and hip pitch axes
- [x] Reusable double-supported pitch-joint yoke concept
- [x] Twin carbon-tube thigh and shin modules
- [x] Two 115 x 65 mm prototype feet with separate soles and four sensor locations
- [x] Compact torso frame and realistic payload reservation volumes
- [x] Neutral standing review with no detached source geometry
- [x] Crouched single-step pose check with lifted-foot clearance
- [x] Fully constrained solver sketches
- [x] Project lint, format, execution, and targeted visual reviews

## Regeneration verification — August 23, 2026

- [x] Mock-execute and execute `main.kcl` after the Ø46 x 37.9 mm actuator-proxy correction
- [x] Mock-execute and execute `pose_check.kcl` after the actuator-proxy correction
- [x] Reconfirm the crouched-pose claim: approximately 21.8 mm swing-foot clearance and no visible self-collision in the reviewed pose
- [x] Retry the `pose_check.kcl` entrypoint constraint report: no errors or warnings; the entrypoint reports zero local sketches, so imported part sketches are not independently enumerated

## Actuator data resolved

- [x] Locate authoritative vendor documentation (manual V1.0, 2D print, STEP)
- [x] Record the real spec table, including the 0.8 Nm continuous rating
- [x] Correct the proxy envelope to Ø46 x 37.9 mm with nothing protruding
- [x] Capture the real bolt patterns as parameters: 6 x M3 on Ø24 output, 4 x M3 on Ø41 housing
- [x] Compute the static torque envelope and the resulting duty limit
- [x] **Import the vendor STEP itself and regenerate — it cannot be done.** `import` of the STEP is rejected by the engine outright (`engine: import failed`), with or without a lowercase extension, and importing the same file directly into a modeling session times out after 300 s. The 4.4 MB open-shell model is beyond what the engine will ingest, so the parametric proxy plus the recorded interface numbers remain the only representation
- [x] Establish that nothing projects past Ø46 and the cable exit is axial at the rear, not radial
- [x] Locate the connectors — rear end, against a flat chord on the Ø46 housing, opposite the Ø30 output boss
- [x] Correct the harness pin counts — power/CAN is 8-pin, debug UART is 3-pin; the manual's parts list has them swapped
- [x] Measure the flat's angular width — a chord 19.0 mm from the axis, about 25.9 mm wide, subtending about 69°
- [ ] Measure how far a mated plug and its strain relief project axially past the rear face (needs the part or the connector datasheet)
- [x] **Confirm the 4 x M3 deep 4 tapped holes on the rear face** — real, on Ø41.00 at 45°/135°/225°/315°, behind Ø3.20 clearance through the 3.20 mm cover; the 2D print and the STEP agree. A rear-anchored bracket supersedes the ribbed shroud

## Knee actuator-interface implementation — August 24, 2026

- [x] Create and fully constrain `knee_module.kcl`; preserve `pitch_yoke.kcl` for the other six shared joints
- [x] Install the new module at the two knees only in `main.kcl` and `pose_check.kcl`
- [x] Regenerate `main.kcl`, `pose_check.kcl`, `knee_prelimit_check.kcl`, and `knee_limit_check.kcl`
- [x] Confirm no visible interference at knee 0°, 30°, 65°, 90°, 100°, and 110° in the reviewed scenes
- [x] Record support span, bearing selection, fasteners, estimated mass, and remaining risks in `NOTES.md` and `BOM.md`
- [ ] Print fit coupons for the Ø30.4 register, Ø19.4 bearing pocket, and rear M3 bracket pattern before committing to a full knee print
- [ ] Resolve the mated-plug axial projection and add cable routing/strain-relief geometry
- [ ] Validate journal retention and stop durability analytically and with hardware when available

## Required next refinement

- [x] Confirm which actuator face is the output — the front face, output inside the Ø30 register, housing on Ø41
- [x] Assess the three support schemes — ribbed shroud plus stub axle recommended; front-face ring fails on load, plain bearing on friction
- [ ] Ask DAMIAO for the output bearing's radial and moment rating — it decides whether the shroud is needed at all
- [x] Detail the rear-anchored bracket: bolt to the 4 x M3 on Ø41, run arms forward past the Ø46 body, carry the far bearing near the output plane, keep the 69° connector sector clear
- [x] Convert the driving cheek from a Ø46.6 annulus into a bolted hub on the Ø24 circle
- [x] Provide the second support, carried by the rear bracket’s forward arms and a 6800-2RS bearing
- [x] Select current-knee support hardware: 6800-2RS, Ø10 x 8 mm hardened journal, M3 x 6 output screws, and M3 x 12 rear screws with washers
- [ ] Add real M3 through-holes, nut traps, and service-access fasteners
- [x] Convert tube socket blocks into clamped/bolted carbon-tube interfaces
- [x] Add a knee-only 110° circular-pad hard stop; 100° pre-limit and 110° limit review scenes execute cleanly
- [ ] Add protected cable channels, service loops, and strain relief
- [ ] Rib and hollow torso/hip parts **and the new link sockets** to recover 100-150 g; the sockets added about 68 g and are now the largest single block of removable material outside the torso
- [ ] Validate all limit combinations and mirrored walking poses; current evidence covers knee 0°, 30°, the 65° crouched pose, 90°, 100°, and 110° only
- [ ] Print joint coupons and test bearing-pocket creep and layer strength

## Carbon-tube link interface — August 28, 2026

- [x] Replace the butt-jointed socket blocks with bonded square pockets, 16 mm deep, giving 531 mm² of bond area per tube end
- [x] Add a transverse M3 through-bolt per tube with a captive nut, so the joint survives a failed bond
- [x] Model the matching cross hole in the carbon tube itself rather than leaving it implied
- [x] Add a bleed hole through each pocket floor for trapped air and surplus adhesive
- [x] Fold `thigh.kcl` and `shin.kcl` into one shared `tube_link.kcl`, leaving only the tube spacing to differ
- [x] Regenerate all four models on the engine after the change
- [ ] **Resolve the link socket against the joint hardware it sits inside.** Each socket's outer face is 21 mm from the joint centre while the actuator is Ø46 and the yoke Ø54, so every socket shares about 2 mm of space with its actuator, and the thigh's upper and shin's lower sockets also pass through a yoke strap. This predates the change and is not made worse by it, but it cannot be fixed by shortening the link — the socket has to become the joint's mounting boss
- [ ] Bolt the sockets to the yokes and knee brackets; nothing currently connects a link to a joint
- [ ] Confirm the 3 mm nut seat is enough in PETG, or move to a metal insert plate, once coupons exist
