# The power switch board

The second board this robot designs for itself, and the first one that carries
its own bus current. It stands in the pack's positive lead between the pack and
the distribution board, and it holds the four things that lead needed: the
**main fuse**, which was an in-line holder taped to the bought distribution
board; the **bus shunt** the INA226 on the controller carrier reads, which had no
mount at all; a **MOSFET switch** that is the robot's on/off and its low-battery
cutoff at once, which the bill had never bought; and the **bulk capacitor bank**,
which used to stand on the bought board underneath.

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
   comparator watches the switched bus through a 0.28 s filter, and the switch
   is held on only while the bus is above the cutoff AND a hold is present.
5. **It turns off** when both holds have been gone for about a second — which is
   what rides through a reset — or when the filtered bus falls below 19.2 V,
   whichever comes first. It is then latched off, because everything that could
   hold it on has just lost its supply. Only the button starts it again.

Switching off is fast even though switching on is slow: a diode takes the
soft-start capacitor out of circuit when the gates rise, so the transistor that
pulls them up drives 56 mA into them and the switch is through its linear region
in under two microseconds.

## Every part on it is through-hole

**Nothing on this board is surface mount**, which is the whole of its second
pass: it is a board a person can place by hand, solder with an iron and read
with their eyes. The resistors and the diodes **stand on end** on a 2.54 mm
pitch, the comparator is a DIP-8, the reference and the two small transistors
are TO-92, and the shunt is a four-terminal PBV-F1 through-hole part.

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
Through-hole wants about half again the area, and **the shunt is the extreme
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
| cutoff | 19.18 V falling, 19.53 V rising: 3.20 V per cell, filtered over 0.28 s |
| with tolerances | 18.61 to 19.76 V at the ends of the reference's and the divider's |
| button | held about 0.4 s from a full pack, 0.8 s from a tired one |
| hold | 0.97 s after the last hold input drops |
| gate drive | −10.3 V at an 18 V bus, clamped to −15 at 30 |
| soft start | 192 V/s, 131 ms, about 0.30 A into the bank |
| switch off | 56 mA of gate pull-up, 1.5 µs through the plateau |
| the switch | 1.58 W per MOSFET at a sustained 24 A; 21 A continuous at 50 °C ambient |
| the shunt | 0.58 W of its 3 W at 24 A, 24 mV across it, 81.92 A ADC range; 65.534 A current-register range |

The run fails if the cutoff leaves 3.05–3.35 V per cell, if the hold is outside
0.5–2 s, if the gate drive falls under the −10 V the MOSFET's on-resistance is
specified at, if the inrush exceeds 2 A, if switching off takes more than 10 µs,
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
`Transistor_FET:Q_PMOS_GDS`, `Device:R_Shunt` for the four-terminal shunt,
`Comparator:LM393` drawn as the three real units it has — and **joins them with
wire**, in the four blocks the circuit is read in: the power path, the gate
drive, the reference and its comparators, and the hold with its button.
Each symbol was chosen so that **its pin numbers already match the footprint the
board uses**, which is what lets the drawing and the copper mean the same part;
the TL431's TO-92 symbol rather than its surface-mount one is the case where
that mattered most.

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

* **A pad's middle is its hole.** The shunt's leads sit in 1.5 mm drills inside
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
| 1.10 mm | over the PBV shunt, to that deck |
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
* **The shunt has a mount for the first time.** It is a four-terminal 1 mΩ PBV-F1 through-hole
  part soldered into this board, and the twisted pair to the carrier's J7 leaves
  on J1 with the same pin order.
* **It is on the switched side of the MOSFETs**, deliberately: with the robot
  off, the only live copper on this board is the fuse and the MOSFET sources,
  and the two sense wires running up to the carrier are dead with it.
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
* **The bus current has still never been measured.** The fuse's rating, the
  shunt's value and the switch's continuous rating all follow that measurement,
  and the 24 A this board is sized to is an estimate.
* **The bought board's own geometry is a catalogue outline.** Its XT60 input
  socket, which this board passes half a millimetre over and keeps every lead
  out of, is drawn from a listing rather than from a board anybody has held.
  Measure one before ordering this.
* **A regeneration clamp is still not on the bill.** This board switches the bus;
  it does not absorb energy coming back into it.

## Shunt correction and INA226 configuration — 2026-09-16

R1 is **Isabellenhütte PBV-R001-F1-1.0**, 1 mΩ ±1 %, four-terminal
through-hole. [Manufacturer datasheet](https://www.isabellenhuette.de/fileadmin/user_upload/PBV.PDF),
issue 12-Feb-2026, specifies **3 W without a heatsink**; the 10 W headline
requires a heatsink. DigiKey India listed 442 at ₹4,144 each on 2026-09-16.
The previous Vishay CPSL-based footprint was not a valid part selection:
that discontinued family starts at 10 mΩ. Do not fit a 10 mΩ substitute.

The board stays entirely through-hole and retains its 50 × 50 mm outline.
The local footprint numbers the terminals left-to-right as 1=current,
2=sense, 3=sense, 4=current, at 0 / 5.08 / 12.70 / 17.78 mm.
The body is 22.5 × 4.45 × 17.5 mm, with a conservative installed height of
20.7 mm including lead shoulders. The drawing's maximum rectangular lead
sections determine 2.2 mm current-pin drills and 1.9 mm sense-pin drills,
with 3.4 mm and 3.0 mm pads respectively. Check actual plated-lead fit before
fabrication. The model clears the deck by 1.10 mm; no heatsink is fitted.

**1 mΩ is appropriate for the requested 24–30 A measurement range.**
The [INA226 datasheet](https://www.ti.com/lit/ds/symlink/ina226.pdf) gives
approximately ±81.92 mV ADC range and a 2.5 µV shunt-voltage step.

| Current | Shunt voltage | Nominal dissipation | Positive ADC range used |
|---|---:|---:|---:|
| 24 A | 24 mV | 0.576 W | 29.3 % |
| 30 A | 30 mV | 0.900 W | 36.6 % |

At +1 % resistance tolerance, 30 A produces 30.3 mV and 0.909 W.
The raw current step is 2.5 mA. A larger 2 mΩ shunt would double the signal
but also double the heating to 1.8 W at 30 A; the existing resolution is
adequate for bus monitoring, so retain 1 mΩ. Resolution is not accuracy:
1 % shunt tolerance, temperature drift, INA226 gain/offset and installation
errors remain. At the datasheet's reference conditions, the INA226's maximum
10 µV offset corresponds to 10 mA with this shunt.

Firmware must set **Current_LSB = 0.002 A** and **CAL = 2560 (0x0A00)**:
`CAL = 0.00512 / (Current_LSB × Rshunt)`. Read the current register as signed
16-bit and multiply by 0.002 A; the power-register multiplier is 0.050 W.
The signed current range is −65.536 to +65.534 A, below the ADC's approximately
±81.92 A but well above 30 A. These are configuration requirements, not a
claim that firmware exists or has been programmed. Regeneration is represented
by negative current; do not interpret the unsigned power register as signed power.

**Remove the INA226 breakout's R100 resistor before attaching the Kelvin pair.**
Leaving it fitted draws current through the sense wiring. Even with ideal
sense wires it parallels the 1 mΩ element and causes approximately 0.99 %
under-reading; real sense wiring adds further error. The carrier circuit comment
now requires removal rather than accepting the earlier incorrect 0.5 % estimate.

The shunt's 3 W rating and <15 K/W thermal resistance give useful margin at
0.9 W, but enclosure temperature and terminal-temperature derating still apply.
This does **not** rate the rest of the power board for 30 A continuous: its
MOSFET thermal estimate remains about 21 A continuous at 50 °C ambient.

Mass allowance: reserve 8 g for the PBV instead of the previous unsupported
2 g placeholder, adding **6 g** to the power-board budget. This is a provisional
allowance, not a manufacturer mass or a measurement; printed geometry is unchanged.
