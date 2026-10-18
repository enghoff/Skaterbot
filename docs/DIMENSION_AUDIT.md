# Dimension audit — 12 October 2026

**Written because the first printed pelvis would not take its charge inlet.**
The XT60E-M's nose measures 15.3 × 8.0 mm, and the rear wall was cut for
14.20 × 6.70, which printed as 14.5 × 7.0. The bill of materials said to measure
an XT60E-M before printing the pelvis. Nothing in the tooling knew that, the
export ran, and the part was printed. This is a pass over every dimension the
CAD takes from a bought part, and every assumption the fits rest on, asking where
each number came from and whether anything has checked it.

**The short version.** The inlet and the button hole are corrected and every
gate passes. But the pelvis is **not ready to reprint**: three more interfaces
on it are unverified and could fail the same way: the inlet's ear plate, the
antenna bulkhead's hole and the IMU's seat. Two boards that were ordered on
8 October are placed from photographs of modules that have been in hand since
1 October. Two faults in the legs would stop a joint being assembled. And the
CAD's fits were set for powder-bed nylon, while the prototype is printed in PLA
on a printer that takes about 0.2 mm off a hole.

## Changed today

| | Was | Now | Source |
|---|---|---|---|
| XT60E-M nose | 14.20 × 6.70 | **15.3 × 8.0** | the part in hand, calipers, 2026-10-12 |
| Its cutout | 14.7 × 7.2 | **15.7 × 8.4**, the nose plus 0.2 a side | gate H's minimum air |
| Its two screws | M2 on Ø2.4, 20 mm apart | **M2.5 on Ø2.9, 20.5 mm apart, no washer**, holes that pass the screw as printed | Each screw stands 0.25 mm outboard in the connector's Ø3.00 ear hole, so the M2.5 nut lands on the connector's body instead of 0.25 mm into it. That leaves 0.95 mm of wall to the cut, which gate G accepts on the record, the only wall on the robot under 1.0. Drawn in a scratch check: the head clears the nose by 0.35, and an M2.5 × 10's tip has nothing within 0.5 mm |
| Inlet station | x 59.0 | **x 58.7** | gate I: the wider nose meets the rear-right lid boss on its way in at 59.0. It passes from 58.5 to 58.85 and fails at 58.4 and 58.95 |
| Button hole | Ø12.2 | **Ø12.4** | Daier's GQ-12B sheet gives a Ø12.4 cutout |
| Gate A | **failing since 10 October** | passes | the SMA side-mount commit added nine dimensions without declaring them; now declared, with their sources |

Gates A to I all pass on the result. `/check` is clean. The rear wall loses
81.8 mm³, 0.08 g, which leaves the robot's 1 974.2 g unchanged at the roll-up's
resolution. Gate B holds the split, measured against the golden STEP: 10.3 mm³
of it is wall the KCL pelvis also had. The pelvis is re-exported and the
simulation model is rebuilt from fresh meshes. `reference/` now holds the AMASS
catalogue and the Daier sheet these figures came from.

## Must be settled before the pelvis is reprinted

**1. The XT60E-M's ear plate.** The CAD draws it as 27.0 × 6.13 × 3.2 mm.
AMASS's catalogue gives the part as 27.10 × 12.10 overall. If the plate is
12.1 mm tall where its ears are, it shares 23 mm³ with the lid's rear-right screw
boss and the inlet cannot be fitted (tested by drawing it so: gates H and I both
fail). If only the middle is 12.1 and the ears narrow to about 6, it fits. Only
the part can say which.

**2. The antenna bulkhead's hole.** It is a Ø6.5 D with its flat 6.0 from the
far side, which is Amphenol's panel cutout for their own bulkhead. The one in
hand is a generic u.FL pigtail. A 1/4-36 thread is 6.35 across. If this one
has no flat it cannot pass a 6.0 D at all, and even with a flat, Ø6.5 prints
about 6.3 on this printer.

**3. The IMU seat.** The seat is drawn for a bare 11 × 10 board stuck flat to
the floor inside three 2.5 mm ribs. The board ordered is 7Semi's ES-12234, and
its own STEP (in `exports/imu-research/`) shows it is 10.0 × 10.5 × 1.6 with a
Qwiic socket **under** it, 4.3 × 6.0 × 2.9 mm, entered from one edge. It cannot
sit flat, it would stand above its own ribs, and its plug needs a way out. The
note added to NOTES.md today, which says the IMU change needs no geometry
change, is wrong. The seat needs redrawing, and which way the board faces is a
decision.

**Settled 2026-10-14, by moving the IMU off the pelvis.** It hangs chip down
under the deck over the power bay now, in two grooved printed rails, with a
printed post on its socket face and its socket 0.5 clear of the deck's underside;
nothing else had to move. The floor
seat came off the pelvis the same day, before it was reprinted. That takes this item
off the pelvis's list. The board is 10.5 × 10 off 7Semi's STEP and 1.50 thick
by calipers; the chip height, 1.18, and the socket's, 2.95, are still the STEP's
and JST's; the socket has 0.5 mm of air over it in case it is taller. See NOTES.md, 14 October.

**4. Fits that this printer will close up.** Every fit below was drawn with
0.2 mm or less a side, which suits powder-bed nylon at about ±0.2. The
prototype is FDM PLA, and the inlet hole shows this printer takes about 0.1 mm
a side off a hole and, typically, adds about as much to an outside face.

| Fit | Drawn | Likely on this printer |
|---|---|---|
| inlet nose in its cut | 0.2 a side | 0.1 a side |
| button thread in its hole | 0.2 a side | 0.1 a side |
| SMA thread in its D | 0.075 a side | interference |
| 6800 bearing in its Ø19.2 seat, meant to be bonded with clearance | 0.1 a side | line to line or a press |
| lid lip in the cavity | 0.2 a side | about nothing |
| IMU in its seat | 0.2 a side | about nothing, and see 3 |

Either the prototype gets a per-process allowance (a slicer hole compensation,
or a printer allowance in the CAD), or each of these is test-fitted on the print
already in hand. **The print in hand is the cheapest test there is.** Try the
button, the antenna bulkhead, a 6800 in a hip seat and the lid in it before
anything is reprinted.

**5. Still unmeasured, on the pelvis.** These are the button's nut, drawn as
17.5 across corners from no drawing, and the BMS board, whose 58 × 33 × 8.2 is
the vendor's table although the board has been in hand since 5 October. There
are also the floor's two cable ports, which the code calls provisional until a
motor's plug is measured.

**6. The battery connectors.** Each pack's mated XT60 pair is drawn 15.6 mm on
its long side. AMASS's catalogue gives the XT60 as **16.0**, and the covered
XT60H as 16.4 × 9.2. The strips these lie in are laid out to 0.5 mm of air.
Measure the mated pair in hand.

## Already committed and unverified: the two boards ordered 8 October

Both boards were ordered from PCB Power on 8 October, for dispatch on
16 October. The power switch boards have arrived and one is being populated,
reported by the owner on 17 October, and the carrier boards on 18 October. Each was laid out round modules that were already in hand, which the
documents said to measure before ordering. Nothing records that they were.

| Module | What the board assumes | Source |
|---|---|---|
| Matek BEC12S-PRO, in hand since 1 October | four pins at 3.81 mm pitch, 2.5 mm in from the short edge, and a 35 × 24 outline between two cable ties | scaled off Matek's product photograph |
| INA226 module, in hand | 22 × 22, two mounting holes 16.7 apart and 2.5 mm in | scaled off the vendor's photographs |
| Banana Pi BPI-M4 Zero, in hand | holes on 58 × 23, Ø2.75 | inferred from Banana Pi's "fits Pi Zero cases" claim |
| WeAct STM32G474 core board, in hand | `cad/` draws 36.53 × 28.40 and `electrical/carrier_pcb.py` uses 36.28 × 28.14 | two vendor files that disagree by 0.25 mm |

Measuring these now tells you, before the boards arrive, whether each module
will go on. CARRIER.md's tightest figure on the carrier is also stale. It is
the 0.85 mm between the IMU's plug and the antenna bulkhead "in the shell
wall", and the bulkhead moved to the left flank on 10 October.

## Faults in the legs that would stop a joint going together

**The captive M5 nut can spin.** The pocket in the output disc is a hexagon
9.3 mm across the flats. That was opened from 8.3 so the finishing chamfer would
leave the nut a flat floor. An M5 nut is 8.79 to 9.24 across its corners, so it
turns freely in a 9.3 pocket. It sits in the pocket with the motor's register
closing the mouth, and the screw comes in from outside through the sleeve, so
nothing stops the nut turning with it. `cad/hardware.py` draws that nut as a Ø8
cylinder and says "Ø8 is the circle it sweeps", but it sweeps up to 9.24, so the
gates measure it 0.6 mm small. The pocket needs to be smaller than the nut's
corners, with the floor chamfer handled some other way.

*Fixed 14 October 2026.* The pocket is 8.3 across the flats, so the smallest M5
nut's 8.79 corners cannot turn in it, and its corners and floor are drawn
rounded, which the finishing chamfer leaves alone. It is also 4.3 deep where it
was 3.3, so a DIN 934 nut goes in as bought and is no longer filed to 2.7; the
web behind it is 1.7 mm and the screw takes 3.3 mm of thread instead of 2.3.
The fastdep nuts measure 7.8 across the flats, 8.9 across the corners and 3.9
thick. Gate F now seats the largest DIN 934 nut in the finished disc and turns
the smallest one in it, as hexagons, and fails both the old 9.3 pocket and a
sharp-cornered 8.3 one. In PLA, which prints a hole about 0.2 mm small, the
delivered nuts go in with a little play and still cannot turn.

**The journal sleeve cannot enter its bearing as drawn.** The sleeve is
printed (it is in `mass_budget.toml` as four prints), Ø10.0, into a 6800 whose
bore is Ø10.0 with a 0 to −0.008 tolerance. That is line to line in nylon and
oversize in PLA. `cad/hardware.py` calls it "the Ø10 steel sleeve". It needs a
deliberate allowance, or a bought steel sleeve.

**The wheel's fits are drawn at zero.** The adapter's spigot and the cap are
both Ø22 into the wheel's Ø22 bearing seats. The wheel's hub (Ø45), the bore
through its centre ridge (Ø16), its seat depth (7) and its tread crown (R20) are
all unmeasured. The wheels were due 10–11 October.

**Smaller items.** The M5 heat-set insert is listed as 6 mm long and drawn as
8 on the seller's own page; the pocket allows for both, so measure one. A motor's
mated plug is still the 8 mm estimate. The rear thread is 3.8 mm deep in the
vendor STEP, against the 4.0 `actuatorRearBoltDepth` still carries; the bill
already allows for 3.8.

## Checked and right

- **The motor.** The vendor STEP was measured directly. It confirms Ø46 ×
  37.9, the Ø30 register 1.0 mm proud, 6 × M3 on Ø24 tapped 6.5 deep, 4 × M3
  on Ø41 front and rear at 45°, and the Ø8 × 1.85 recess at the centre of the
  output face. All of these agree with `cad/parameters.py`.
- **The battery packs**, measured on arrival on 5 October.
- **The standard parts**: the 6800 (10 × 19 × 5) and the 608 (8 × 22 × 7), the
  ISO screw heads, nuts and washers the CAD draws, and the 10 × 16 capacitor
  cans.
- **The button**, against Daier's sheet: M12 × 1, a 1–6 mm panel, and 21 mm
  from the dome to the terminals. The hole is now the sheet's Ø12.4.
- **The XT60E-M's 20 mm screw spacing** agrees with the CAD. Nothing else
  about the part does yet.

## The records that contradict the model

None of these changes geometry. Each one says something the model no longer
does, which is how the next wrong assumption gets made.

- `cad/electronics.py` still describes the SwiftWing distribution board as fitted
  and lists it among the settled part numbers. It has been off the bill since
  7 October.
- The same file says the bus monitor lies against the rear wall from x 42.5 to
  66.5. It has been on the carrier since 14 September.
- It says the M2 pair and its 1.45 mm bridge are gone from the rear wall. They
  came back with the inlet on 5 October.
- It says the antenna is "on the other side of the disconnect". The disconnect
  is gone and the antenna is on the left flank.
- `cad/parameters.py` still gives the material as PA12-CF at 1.06 g/cm³ and the
  wall as four perimeters of a 0.6 mm nozzle. The mass budget is SLS PA12 at
  0.93, and the prototype is PLA.
- `docs/BOM.md` put the button at z 22. It is 23.5, corrected today.

## What this means for mass

The budget weighs the printed parts as SLS PA12 at 0.93 g/cm³. In PLA, at about
1.24, the 421 g of printed structure is about 560 g. A PLA robot would be
roughly 2 115 g against the 2 300 g ceiling, with 185 g of headroom rather
than 326.

## Why it was preventable, and what would prevent it

Every one of these had a warning beside it in a comment or in the bill, and
none of the warnings was in the path from the CAD to the printer. The gates
check the model against itself and against the KCL it was ported from. Nothing
checks it against the parts on the bench, and nothing knows which numbers
nobody has measured.

The fix is a register of every dimension a printed piece takes from a bought
part, saying where each came from: measured, a maker's drawing, a listing, or an
estimate. `/step` would then refuse to export a piece whose interfaces are not
all measured unless asked to, and print the list of what is not. The inlet
would have been stopped at export on the 12th.
