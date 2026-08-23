# Biped Development Checklist

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

## Actuator data resolved

- [x] Locate authoritative vendor documentation (manual V1.0, 2D print, STEP)
- [x] Record the real spec table, including the 0.8 Nm continuous rating
- [x] Correct the proxy envelope to Ø46 x 37.9 mm with nothing protruding
- [x] Capture the real bolt patterns as parameters: 6 x M3 on Ø24 output, 4 x M3 on Ø41 housing
- [x] Compute the static torque envelope and the resulting duty limit
- [ ] Import the vendor STEP itself and regenerate (its body is an open-shell surface model, so it may not import as a solid)
- [ ] Measure the connector/cable-exit keep-out at the Ø46 rim, 31.7 mm from the output face

## Required next refinement

- [ ] **Choose the knee support architecture** — both bolt circles are on one actuator face, so the double-shear yoke as drawn cannot work
- [ ] Confirm which actuator face is the output before designing either cheek
- [ ] Convert the driving cheek from a Ø46.6 annulus into a bolted hub on the Ø24 circle
- [ ] Provide the second support, which the actuator does not offer on its far side
- [ ] Select exact support bearings, axles, spacers, and retention method
- [ ] Add real M3 through-holes, nut traps, and service-access fasteners
- [ ] Convert tube socket blocks into clamped/bolted carbon-tube interfaces
- [ ] Add robust hard stops for each joint
- [ ] Add protected cable channels, service loops, and strain relief
- [ ] Rib and hollow torso/hip parts to recover 100-150 g
- [ ] Validate all limit combinations and mirrored walking poses
- [ ] Print joint coupons and test bearing-pocket creep and layer strength
