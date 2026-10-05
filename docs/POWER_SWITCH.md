# The power switch board

The second board this robot designs for itself, and the first one that carries
its own bus current. It stands in the pack's positive lead between the pack and
the distribution board, and it holds three of the four things that lead needed:
the **main fuse**, which was an in-line holder taped to the bought distribution
board; a **MOSFET switch** that is the robot's on/off and its low-battery cutoff
at once, which the bill had never bought; and the **bulk capacitor bank**, which
used to stand on the bought board underneath.

**The fourth was a bus shunt, and it was deleted on 16 September 2026** along
with the current measurement it existed to serve. The section at the end of this
file records why, and it reverses what the rest of the file used to argue rather
than quietly rewriting it.

It is the bought distribution board's own 50 × 50 mm footprint, two layers, and
it sits 8 mm above that board on that board's own four screws.
[`electrical/power.py`](../electrical/power.py) is the circuit,
[`electrical/power_pcb.py`](../electrical/power_pcb.py) is the board and
[`electrical/power_sch.py`](../electrical/power_sch.py) is the drawing:

```
uv run electrical/power.py                 # the circuit, checked and printed
uv run electrical/power_sch.py             # draw it, check the netlist off it, ERC it
uv run electrical/power_pcb.py             # lay it out, build it in KiCad, DRC it
uv run electrical/power_pcb.py --draw      # also rewrite electrical/power_pcb.png
```

**Nothing here has been built.** Every figure below is off a datasheet, off
KiCad's own library, or off the CAD.

## Why there is a switch at all

The robot has had no way to turn itself off. Pulling the loop key was the only
disconnect, so a robot left switched on flattened its own pack, and a flat LiPo
is a damaged LiPo; the BMS added in September 2026 is on the cell taps only and
cannot break the discharge path. Against that, a switch that carries 24 A cannot
be a panel switch — [`docs/BOM.md`](BOM.md) works that out — so what is here is
the sensible version of the idea: a pair of MOSFETs in the positive lead, turned
on by a button, held on by the controller, and turned off by either the
controller or by the board itself when the pack falls too far.

## What it does, in the order a user meets it

1. **The pack is connected and the robot is off.** Nothing on this board draws
   current except leakage. Every comparator, divider and reference hangs off the
   SWITCHED side of the MOSFETs, so it is unpowered until the switch closes.
2. **A push button closes the switch while it is held.** It pulls the gates down
   directly, through a diode, so it depends on nothing that needs power. The
   gates are pulled through 470 kΩ against a 220 nF capacitor to the drains, and
   that is the soft start: the bus comes up over about 130 ms at roughly a third
   of an amp rather than slamming the capacitor bank. That is the pre-charge the
   bill has been missing since the anti-spark connector went.
3. **The controller boots and drives HOLD high.** The SBC may drive its own hold
   as well: either is enough. That is what lets the SBC reflash the
   microcontroller — a reset of one does not drop the power to the other.
4. **The board takes over from the button after about half a second.** A
   comparator watches the switched bus through a 0.29 s filter, and the switch
   is held on only while the bus is above the cutoff AND a hold is present.
5. **It turns off** when both holds have been gone for about a second — which is
   what rides through a reset — or when the filtered bus falls below 18.9 V,
   whichever comes first. It is then latched off, because everything that could
   hold it on has just lost its supply. Only the button starts it again.

The active C1 reset uses Q5 to restore the Miller node and C7 to hold the gates
near their sources while that happens. D8 isolates a falling bus. Turn-off is
checked with a transient model: the old sub-2 microsecond claim ignored Q4's
falling base drive and was not a valid bound.

## Every part on it is through-hole

**Nothing on this board is surface mount**, which is the whole of its second
pass: it is a board a person can place by hand, solder with an iron and read
with their eyes. The resistors and the diodes **stand on end** on a 2.54 mm
pitch, the comparator is a DIP-8, the reference and the three small transistors
and the transistors are TO-92.

Standing the passives up is the one choice here that is not the obvious one, and
it is what made the rest fit: an 0204 resistor upright occupies 9.5 mm² of board
against a 1206's 10.3, so the passive rows did not have to grow at all. Laid
down on a 7.62 mm pitch they would each have taken 29 mm², and there would have
been no board left.

**Two pinouts changed with the package**, and both are worth knowing because a
transposed one is a board that does nothing:

| | surface mount | through-hole |
|---|---|---|
| the reference | TL431 SOT-23-3: 1 K, 2 REF, 3 A | TL431 TO-92: **1 REF, 2 A, 3 K** |
| the transistors | BC846B SOT-23: 1 B, 2 E, 3 C | BC546B TO-92: **1 C, 2 B, 3 E** |

Both come from KiCad's own symbol library, which agrees with TI's SLVS543 and
with Nexperia's BC546 data sheet.

## What the board grew, and what paid for it

The board was 54 × 32.5 mm over the rear half of the bought distribution board.
Through-hole wants about half again the area, and **the shunt was the extreme
case in the original layout**: its axial placeholder reserved 246 mm² against the 2512's 33. That placeholder was invalid at 1 mΩ and has now been replaced by the PBV-F1 described below. On the old
outline that was arithmetically impossible — parts and pours came to 98 % of the
board.

**What paid for it was the capacitor bank's reservation.** The CAD drew four cans
of Ø16 × 25 across the whole front of the power bay while `docs/BOM.md` has
specified **two** Panasonic EEU-FR1V471B since the day it first named a part, and
those are Ø10 × 16. The reserve was eight times the volume of the parts in it.
Sweeping a probe of the board's own thickness over the bought board's whole 50 ×
50 footprint found the bank to be the only solid in the way; everything else —
the pack's own XT60s, the series link, the main leads — sits 7.4 mm or more above
the board and caps part height rather than blocking the board.

So the reserve is now the size of the parts in it, the two cans stand on **this**
board on the bus copper they damp, and the outline lands exactly on the bought
board underneath. **The capacitance itself is unchanged and still unmeasured**:
what shrank is the reservation, not the bank.

The robot came out 32 g lighter for it: the bank's line falls from a 60 g
allowance to the 20 g those two cans and their leads actually are, against the
8 g the bigger board costs.

## What the circuit is held to

`electrical/power.py` is a netlist, and it is checked the way
[`electrical/carrier.py`](../electrical/carrier.py) is: every pin of every part
on exactly one net, no net a dead end, no pin on two nets. What is particular to
this board is that **its behaviour is computed from the component values rather
than described beside them**, so changing a resistor changes the answer:

| | |
|---|---|
| cutoff | 18.85 V falling, 19.19 V rising: 3.14 V per cell, filtered over 0.29 s |
| with tolerances | 18.28 to 19.41 V at the ends of the reference's and the divider's |
| button | held about 0.4 s from a full pack, 0.7 s from a tired one |
| hold | 0.90 s after the last hold input drops |
| gate drive | −12.2 V at an 18 V bus, clamped to −15 at 30 |
| soft start | 199 V/s, 127 ms, about 0.31 A into the bank |
| switch off | See the C1 reset transient results below; loaded MOSFET SOA unverified |
| the switch | 1.26 W per MOSFET at a sustained 24 A; 24 A continuous at 50 °C ambient |

Those are the figures since the parts change of 2026-10-01 at the end of this
file, which moved the cutoff down by a third of a volt.

The run fails if the cutoff leaves 3.05–3.35 V per cell, if the hold is outside
0.5–2 s, if the gate drive falls under the −10 V the MOSFET's on-resistance is
specified at, if the calculated inrush exceeds 2 A,
if a resistor is asked for more than half its quarter watt, or if any part sees
more than 85 % of its voltage rating at a 30 V bus.

## The drawing, and what checks it

[`electrical/power_sch.py`](../electrical/power_sch.py) writes the netlist out as
a one-sheet A3 KiCad schematic — 51 parts in 53 symbols, 114 pins, 27 nets — so
that the board can be read the way an electrical drawing is read rather than by
following a dictionary in a Python file.

**It is an ordinary schematic since 2026-09-16, and it was a table of boxes
before that.** The first version drew one generated rectangle per part with its
net's name on a stub off every pin, and joined nothing to anything: legible to a
machine, and to nobody else, because a resistor looked like a diode looked like a
comparator. It now places **KiCad's own symbols** — `Device:R`, `Device:D_Zener`,
`Transistor_FET:Q_PMOS_GDS`, `Comparator:LM393` drawn as the three real units it has — and **joins them with
wire**, in the four blocks the circuit is read in: the power path, the gate
drive, the reference and its comparators, and the hold with its button.
Each symbol was chosen so that **its pin numbers already match the footprint the
board uses**, which is what lets the drawing and the copper mean the same part;
the TL431's TO-92 symbol rather than its surface-mount one is the case where
that mattered most.

**Which way the sheet reads.** The power path runs left to right across the
whole top, the pack pad at one edge and the bus pad at the other. The control
underneath is a feedback loop around it — it senses the bus at the right-hand
end of that path and drives the gates near the left-hand end, because the fuse
has to come before the switches and the bank after them — so the lower half
returns right to left, and the hold and the button are drawn that way on
purpose, their connectors at the right edge and their signals running leftward
into the comparators and on into the gate drive. Moving those connectors to the
left edge would not remove the reversal, only move it onto the gate net. What
the sheet does insist on is that nothing reads against its own block: the
button's two diodes take the button line in from the right and hand the pull-down
and the sense line out to the left, and the two gate resistors stand above the
gate rail so that G1 and G2 leave pointing at the MOSFETs they feed.

**Six nets are still names rather than lines**, and deliberately: the pack rail,
the switched bus, the gates, the enable line and ground run the width of the
board, and drawing those as wires between four corners of a sheet is how a
schematic becomes unreadable. Each is wired inside the block it belongs to and
carries its name where it leaves — which is how the drawing would be done by
hand.

**The drawing is checked against the netlist, not trusted.** The sheet is handed
to `kicad-cli`, which extracts its netlist, and that is compared pin by pin with
`power.py`'s `NETS`. A wire that misses a pin, a stub that lands on the wrong
trunk, a junction dot left out where three wires meet — none of those is visible
in a rendering and all of them come out as a net that does not match, and the
script fails. That check is what found KiCad joining nothing to a pin that
merely lies part way along a wire: a trunk is now drawn in segments between its
pins so that every pin is a wire end.

Two more things are worth knowing. **Every symbol names the footprint the board
really uses**, read out of `power_pcb.py` rather than typed again. And **KiCad's
own ERC runs on it** as part of writing it, which is what caught the first
version pointing all 51 parts at a footprint library that does not exist. The
sheet's title block carries the arithmetic above, so somebody reading the drawing
sees what these component values actually do.

[`electrical/kicad_symbols.py`](../electrical/kicad_symbols.py) is what reads
KiCad's libraries. Its one subtlety is worth repeating because guessing it costs
an afternoon: **a library's y axis points up and a sheet's points down**, and a
pin's own angle points inward, from its connection end back at the body. Both
are asserted rather than believed — the transform was checked at all four
rotations and both mirrors against `kicad-cli`'s netlist export, by wiring each
pin of a placed symbol to a uniquely named label and confirming KiCad put that
label on that pin.

## The board, and what checks it

Most footprints are **KiCad library parts**. R1 is a local footprint in
`electrical/kicad_power/power.pretty`, drawn from Isabellenhütte PBV drawing
Z-DW-132b (12-Feb-2026); the project library table makes it available in KiCad.
The high-current nets are **zones on both layers** rather than tracks; the
signals are searched for on a 0.1 mm grid the way the carrier's are, and kept
out of those zones so that no track can cut a power path in two. Ground is
poured over the whole bottom layer AND routed pad to pad, because a signal
crossing that pour can cut it in two — which KiCad has reported as an open
circuit on both versions of this board.

**The board is assembled by KiCad itself.**
[`electrical/power_kicad.py`](../electrical/power_kicad.py) runs inside KiCad's
own Python: it places the library footprints, lays the copper, fills the zones
and writes the file. Then `kicad-cli` runs KiCad's design rule check on the
result, and every short, open and clearance is KiCad's finding on the filled
board rather than a claim made here — **0 errors and 0 unconnected items**, on
99 tracks and 57 vias (11 silkscreen warnings remain). What this repository checks on top of that is the part
that lives outside the board: that every pad is where the layout meant to put it
(to a hundredth of a millimetre, read back from the built board), that no two
courtyards overlap, that nothing stands on a screw's washer, that no lead lands
in the bought board's input socket, and that every part clears every drawn thing
in the torso, measured in the CAD's own frame.

**It wants 2 oz copper.** The zones are sized for it; at 1 oz the switch's own
copper would run hot at the peak current this robot has never measured.

### Three things that check found that looked finished

Worth writing down, because each was a board that passed every check this
repository owned and would not have worked:

* **A pad's middle is its hole**, found on the shunt while it was still here
  and true of every drilled pad on the board. Its leads sat in 1.5 mm drills inside
  3.0 mm pads, leaving a 0.75 mm ring of copper. The router aimed at the pad's
  centre and laid its track into the hole; KiCad called both sense pads
  unconnected. A track may land on the ring now, and on the ring only — and not
  in the corners of the ring's bounding box either, because a drilled pad is
  round and those corners are not copper.
* **A pour drawn as boxes that touch is two pours.** The bank's outboard riser
  met the bus bar on a boundary line and filled as a separate island.
* **A round courtyard read as flat.** A radial capacitor's whole outline is one
  circle in KiCad's footprint file, and the reader took the two points it is
  written with as the extent — so a 6 mm can measured 0 mm deep and every part
  beside it was placed on top of it.

## Where it sits, and how it is held

Directly over the bought distribution board, on the same outline. Four M3
self-tapping screws from above, which is the only direction anything in this bay
can be driven from: each goes through this board, an 8 mm spacer and the
distribution board into the printed post that already carries that board's
corner. They are **that board's own four screws, made longer**, and there is no
printed material anywhere in this change — the wall pad the old two-screw
outline needed is gone with it.

What the fit comes to, all of it measured by `tools/gate_f.py` and
`electrical/power_pcb.py` rather than asserted:

| | |
|---|---|
| 8.00 mm | under the board, over the distribution board: its solder joints and the motor leads leaving them |
| 5.80 mm | over the two capacitor cans, to the electronics deck above |
| 3.00 mm | over the two TO-220 switches, to that deck |
| 0.60 mm | from the nearest trimmed lead to the distribution board's own XT60 input socket |
| 0.65 mm | from the nearest can to the pack's own XT60 connectors overhead |
| 0.50 mm | over that input socket |

**Nothing with a lead may stand over that socket**, and that is a keepout in the
layout rather than a clearance to check afterwards: the socket reaches to within
half a millimetre of the underside and a trimmed lead is 2 mm long. Raising the
board to 10 mm of spacer to clear it outright was tried and is worse — it takes
two millimetres off the far side, where the pack's connectors hang 7.4 mm over
this board, and leaves 1 mm over the switches instead of 3.

## What this changes elsewhere

* **The fuse moved onto this board** and became a mini (ATM) blade in a
  PCB-mount holder, where it was a standard blade in an in-line holder taped to
  the distribution board. The rating still follows the measurement.
* **There is no bus shunt and no sense pair.** Both went with the current
  measurement; the carrier's J7 is now a spare header. With the robot off, the
  only live copper on this board is the fuse and the MOSFET sources.
* **The capacitor bank is on this board**, two cans on the switched bus, where it
  stood on the bought board before. It is the capacitance the soft start is
  sized to charge, so it belongs here.
* **The pack's main lead takes a different route.** Its positive leaves the
  pack's connector, rises through the electronics deck's rear notch to the loop
  key above, and comes back down to this board's input pad.
* **The distribution board's motor leads must be soldered first.** This board
  covers that one completely, so every lead leaving it has to be on before this
  board goes over it, and every lead has to leave through the 8 mm gap.

## What is not settled

* **The button has no hole.** The rear wall is cut for two XT60s and an antenna,
  and a momentary push button needs a third opening. Nothing is drawn for it and
  the wall's stations were solved rather than laid out, so adding one means
  sweeping it against the cavity again.
* **The carrier has no connector for the hold and the button sense.** Those
  three wires land on J2 here and have nowhere to go at the other end:
  `electrical/carrier.py` is at a checked fabrication release and adding a plug
  to it is a change of its own. The SBC's hold is a flying lead to a GPIO on its
  40-pin header, and which GPIO has not been chosen.
* **Nothing isolates the pack any more, and this is the open item to weigh.**
  The loop key was deleted on 2026-09-16 and its button took the wall station,
  so the only break in the pack's positive lead is this board's two transistors
  — and **a MOSFET usually fails shorted, and silently**. The robot would still
  run and would no longer turn off or cut off, with nothing mechanical to say
  so. What is left as an isolator is unplugging a pack from the series harness
  inside the lid, which is a lid-off job. **What the change does not cost is
  standing current**: the off state has no DC path from the pack at all, so a
  pack left connected is drained by its own leakage rather than by this board.
* **The bus current has still never been measured**, and this board no longer
  contains anything that would measure it. The fuse's rating and the switch's
  continuous rating both follow that measurement, and the 24 A this board is
  sized to is an estimate. Take it once on a bench with a clamp meter round the
  pack lead, through a first stand and a first drive.
* **The bought board's own geometry is a catalogue outline.** Its XT60 input
  socket, which this board passes half a millimetre over and keeps every lead
  out of, is drawn from a listing rather than from a board anybody has held.
  Measure one before ordering this.
* **A regeneration clamp is still not on the bill.** This board switches the bus;
  it does not absorb energy coming back into it.

## The current measurement was removed — 2026-09-16

**There is no shunt on this board and no current measurement anywhere on the
robot.** The section this replaces had just re-specified R1 as an Isabellenhütte
PBV-R001-F1-1.0 — 1 mΩ ±1 %, four-terminal, 3 W without a heatsink — after the
Vishay CPSL footprint it replaced turned out to be for a part nobody makes at
1 mΩ. That correction was right and it is what made the cost visible.

**Sourcing it is what settled the question.** €14.22 at Bürklin in Germany,
$18.60 at LCSC and out of stock, $43.37 at DigiKey with 442 on the shelf, and no
Indian seller stocking a four-terminal shunt in any package at any value near
1 mΩ. A genuine Kelvin through-hole shunt is a three-part market — the others
are the Ohmite CS3FR001E at $29.65 and the Riedon PCS-0R001D1 at $39.40 — so the
PBV was already the cheap one. It would have been the most expensive component on
this board by more than the rest of it put together, and the reason it costs that
is not margin alone: what you buy in a milliohm shunt is a value that stays put
across its own self-heating, a manganin alloy whose thermal EMF against copper
is about a microvolt per degree, and a pair of sense taps trimmed to ten
microohms — because the solder joint holding the part down is itself worth about
half a milliohm.

**Nothing was protected by it.** The low-battery cutoff on this board is a
comparator watching bus VOLTAGE through a divider and never looked at current, so
the pack's protection is untouched. All six actuators report torque in their own
CAN feedback frame, referred to the output shaft, so a stalled or straining joint
stays visible. And the INA226 on the carrier reads bus voltage on its own VBS
pin, which never went through the shunt, so pack telemetry survives intact.

**What it would have bought is the runtime figure** that
[`docs/NOTES.md`](NOTES.md) still lists as unknown — two hours balancing, an hour
driving, under twenty minutes in a loaded crouch, every one computed and none
seen — along with the fuse rating and the switch's continuous rating. All of
those are a characterisation taken once, on a bench, through a first stand and a
first drive, where a clamp meter round the pack lead answers as well as a fitted
Kelvin shunt does. **What is genuinely given up is coulomb counting**: state of
charge from integrated current rather than from voltage sagging under load, which
on a LiPo is much better. Nothing on this robot does it yet, and the cheap way
back is a two-terminal shunt on a future board revision with a one-off software
calibration, not a €28 Kelvin part.

**What came off, measured rather than asserted.** R1 and its sense plug J1 are
gone from the netlist, which is 49 parts, 108 pins and 24 nets where it was 51,
114 and 27. VDRN and VBUS were two pours with the shunt bridging them and are one
pour now, running from both MOSFET drains to the output pad. The board keeps the
bought distribution board's 50 × 50 footprint, so what the removal bought is room
rather than a smaller board: about 250 mm² of courtyard out of the middle of the
bus path, and it shows in the layout — 97 tracks and 58 vias where the same board
took 107 and 66, with KiCad's DRC reporting 0 errors and 0 unconnected on the
filled board. The mass line falls from 36 g to 28.

**Two loose ends.** The carrier's J7 is now a header with nothing to plug into
it, and the INA226's IN+ and IN− behind it are left floating; tie them to ground
rather than leaving them so, which is a wire at the plug rather than a change to
a board already at a checked fabrication release. And the instruction to lift the
INA226 breakout's own R100 is withdrawn — it existed only to stop that 0.1 Ω
sitting in parallel with the external Kelvin pair, and there is no longer a pair.

## Active C1 reset, 2026-09-21

The old 10 Mohm R24 / 220 nF C1 reset had a 2.2 s time constant. A cold
connection with the button held, or a brief off/on cycle, could turn the
MOSFETs on before C1 recovered. R24 is now removed. Q5, a BC546B emitter
follower, restores MILLER toward GATE minus one base-emitter drop. Its base
comes from GATE through R25 (10 kohm), and its collector from VSRC through
R26 (1 kohm, 1 W). Q5 stops conducting during the rising Miller ramp.
C7 (2.2 uF film) connects VSRC to GATE and delays turn-on while C1 resets.
D2 and D8 are now BAT46 Schottky diodes to reduce the recovery voltage gap.
The original R2, R5 and C1 values are retained. Nominal plateau slew is
193 V/s, about 130 ms and 0.30 A into 1540 uF, excluding the initial gate delay.

All added parts are through-hole. C7 is WIMA MKS2C042201K00KSSD, 2.2 uF
+/-10%, 63 V, 7.2 x 7.2 x 13 mm with 5 mm pitch; the layout reserves 13.5 mm
height. It occupies space released by the deleted shunt connector. R26 is a
Vishay PR01 1 kohm 1 W axial part, in a DIN0207 vertical footprint. Sources:
[WIMA MKS2](https://wima.de/wp-content/uploads/media/e_WIMA_MKS_2.pdf),
[Vishay PR01](https://www.vishay.com/docs/28729/pr010203.pdf),
[BC546B](https://www.onsemi.com/pdf/datasheet/bc546-d.pdf),
[BAT46](https://www.vishay.com/docs/85662/bat46.pdf).

Run `uv run electrical/power_reset.py` for the ngspice regression. It checks
model connections against the actual netlist and reads the timing values from
power.py. It reproduces the original cold-start failure, then passes 26 revised
cases: 18/25.2/30 V; 0.1-100 ms OFF gaps; 1 ohm load; 2200 uF bus capacitance;
C1 +20%, C7 -20%, BJT gain 50, MOSFET threshold 1.5 V; plus nominal light
load and the opposite capacitor corner. Each run checks completed initial and
repeat startup, capacitor charging current, gate voltage, and complete turn-off
for longer OFF requests. Very short requests need not fully disconnect the load.

Maximum modeled capacitor charging current is 1.419 A. Nominal light-load
turn-off is 0.785 ms; the additional adverse turn-off case is 5.557 ms.
The old microsecond turn-off claim has been removed. These are simplified
semiconductor models at nominal temperature, NOT qualified manufacturer models
or a guaranteed hardware inrush limit. Loaded startup/turn-off SOA, temperature
and leakage margins, and constant-power loads remain unverified. The held-button
UVLO override and regeneration clamp remain separate open issues.

Mass allowance increases by 2 g for the reset components, to 30 g for this
board and 2077.4 g for the robot, with 222.6 g below the 2300 g ceiling.
The allowance is unweighed. The shunt and current sensing remain removed.

Verification: schematic netlist comparison and ERC pass (52 parts, 115 pins,
26 nets). The regenerated PCB has 111 tracks and 67 vias; DRC reports zero
errors, zero unconnected nets, and 13 silkscreen warnings. Component and lead
clearance checks pass; minimum reported lead clearance is 0.60 mm.

The broader mechanical clearance suite also passes: gate F, 850 checks,
including 741 body pairs with no shared volume.

## Five parts changed for sourcing — 2026-10-01

**Three of this board's parts could not be bought when the bill went into carts,
so the board was changed to parts that can, and kept through-hole.**

- **The six BAT46 are 1N4148.** ST no longer makes the BAT46, the BAT41 or the
  BAT48 in DO-35, and every BAT46 still stocked is surface mount; through-hole
  small-signal Schottkys have gone the way of the old switch. The 1N4148 was
  already on the board as D3, uses the same DO-35 footprint, and is rated 75 V
  against the 45 V D8 sees. It costs about 0.2 V more forward drop. The hold
  time is computed with it, at 0.45 V, and `power_reset.py` now models D2 and
  D8 as the silicon diode it had always carried for the old circuit.
- **R12, the bottom of the cutoff divider, is 15 kΩ 1 %.** Nobody stocks the
  14.7 kΩ in the 0204 body, only in the 0207, which does not fit. The cutoff
  falls from 3.20 to 3.14 V a cell, inside the 3.05–3.35 V the check allows.
- **R2, the gate's pull to its source, is 1 MΩ** where it was 680 kΩ, for the
  same reason. It raises the gate drive at an 18 V bus from −10.6 to −12.2 V.
- **C7 is KEMET's MMK5225K63J06L4BULK.** The WIMA MKS2 is discontinued; the
  KEMET part is the same 2.2 µF 63 V in the same 7.2 × 7.2 × 13 mm on the same
  5 mm pitch, and element14 marks it as its last stock.
- **C1 and C2 name the parts bought.** C1 is a KEMET R82, 220 nF 63 V,
  7.2 × 2.5 × 6.5 mm, so its footprint is KiCad's 7.2 mm film footprint where
  it was a generic 7.0. C2 is the carrier's dipped KEMET C320 100 nF X7R on
  2.54 mm, rated 50 V where the disc was 100, which the ratings check now
  covers at a 30 V bus.

**What it costs is margin in the switch-off transient**, and nothing else the
checks measure. `power_reset.py` still passes all 26 cases, but its worst
capacitor peak rises from 1.85 to 1.97 A against the 2 A it allows, and the
adverse turn-off from 5.6 to 8.1 ms against 10. Most of that is the diodes: the
same run with 1N4148s and the old 680 kΩ gives 1.91 A and 8.0 ms. These are
the same simplified models as before, not a qualification.

Verification, all run on 2026-10-01: `power.py` passes its netlist and every
arithmetic limit; `power_sch.py` matches the netlist and KiCad's ERC is clean
(54 parts, 121 pins, 26 nets); `power_pcb.py` places and routes all 54 parts,
103 tracks and 57 vias, with zero DRC errors, zero unconnected nets and the
same 13 silkscreen warnings as before, and every body and lead clearance check
passes, the closest at 0.60 mm.
