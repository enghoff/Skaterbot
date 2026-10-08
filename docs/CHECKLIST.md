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
