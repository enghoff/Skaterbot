# Power-board reset checks, 2026-09-21

- [x] Preserve removal of the current shunt and sense connector.
- [x] Use through-hole parts for the active C1 reset.
- [x] Reproduce the previous cold-start failure in a simplified model.
- [x] Pass 26 modeled cold-start and rapid-restart cases.
- [x] Check schematic connectivity against the netlist; pass KiCad ERC.
- [x] Route the PCB; zero DRC errors and zero unconnected nets.
- [x] Check component/lead clearances against the torso CAD.
- [x] Pass the broader gate F mechanical clearance suite: 850 checks.
- [x] Build the project and verify the 2077.4 g mass estimate.
- [ ] Resolve 13 remaining silkscreen warnings.
- [ ] Qualify loaded switching SOA, temperature/leakage and constant-power loads.
- [ ] Address held-button UVLO override and regeneration handling separately.

No hardware exists. Simulated and CAD results are not physical validation.

# Charge-inlet positive landing, 2026-10-08

- [x] Give battery positive P1 and shell XT60 positive P5 separate plated holes on BATT.
- [x] Document battery negative to P3, BMS B− to P4, and inlet negative only to BMS P−.
- [x] Check schematic connectivity against the netlist; pass KiCad ERC.
- [x] Check component and lead placement against the torso CAD.
- [x] Build the project; pass lint and formatting checks.
- [x] Route and check the PCB: zero DRC errors and zero unconnected nets; 5.39 mm minimum charge-positive copper width.
- [x] Pass all 13 torso assembly steps after moving the fuse holder.
- [ ] Resolve 12 silkscreen warnings; bench-test the assembled charge path.


### Antenna and button - 10 October 2026

- [x] Return the button to its original rear-wall station and restore both lugs.
- [x] Move the side SMA rearward to clear a 12 mm base by at least 2 mm.
- [x] Keep the SMA D-flat down: 6.50 mm diameter, 6.00 mm flat-to-arc span.
- [x] Reserve 9.5 mm for the internal SMA body; retain provisional 15 mm depth.
- [ ] Confirm the purchased SMA body depth and mounting shoulder/nut arrangement.
- [ ] Measure the full fitted antenna and check its fall-contact envelope.

### IMU supply and harness — 12 October 2026

- [x] Establish the advertised ES-12234 interface: four-pin Qwiic/JST-SH-compatible, 1.00 mm pitch.
- [x] Set assembly documentation to JP1 2–3, 3.3 V; retain existing carrier copper and footprints.
- [x] Correct harness mapping: SCL/GND/3V3/SDA to J6-1/2/3/6; J6-4/5 unused.
- [ ] Verify delivered board revision and resolve manufacturer's contradictory supply text.
- [ ] Obtain a mating four-pin SH lead; the ordered six-pin XH cable is carrier-side only.
- [ ] Fit JP1 2–3 with power disconnected; check harness continuity and 3.3 V before connecting IMU.
- [ ] Check IMU pull-up voltage and core regulator current/thermal margin during commissioning.
