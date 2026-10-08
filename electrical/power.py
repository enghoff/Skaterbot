# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = []
# ///
"""The power switch board, as a netlist whose circuit arithmetic can be checked.

The second board this robot designs for itself. It takes the pack's leads in and
hands the switched bus out, and it carries the things that path needed and had
nowhere to put: the main fuse, a MOSFET switch that is the robot's on/off and
its low-battery cutoff at once, the bulk capacitor bank the soft start is sized
to charge -- and since 2026-10-07 the distribution itself, six motor outputs and
the carrier's feed, each on a plug. Until then a bought distribution board sat
under this one and every motor lead was soldered to it.

THERE IS NO CURRENT MEASUREMENT ON THIS BOARD, since 2026-09-16, and the reason
is worth keeping because the shunt was one of the four reasons this board was
drawn. Nothing was ever protected by it: the cutoff below is a comparator on bus
VOLTAGE and never looked at current, and the six actuators report their own
torque over CAN, so a straining joint stays visible. What it would have bought
is the runtime measurement docs/NOTES.md is still waiting on -- and that is a
characterisation taken once on a bench, where a clamp meter round the pack lead
answers it as well as a fitted Kelvin shunt does. What it costs is coulomb
counting, which nothing on this robot does yet. The INA226 stays on the carrier
and still reads bus voltage on its own VBS pin, which never went through the
shunt.

    uv run electrical/power.py          # check it, then print the tables

WHAT THE SWITCH DOES, in the order a user meets it:

  1. The pack is connected and the robot is OFF. Nothing on this board draws
     current except leakage: every comparator, reference and divider hangs off
     the SWITCHED side, so it is unpowered until the switch closes.
  2. A push button pulls the MOSFET gates down directly -- not through anything
     that needs power -- so the switch closes while it is held. The gates are
     pulled through 470 kOhm against a 220 nF Miller capacitor, which slews the
     bus up over about a tenth of a second instead of slamming the capacitor
     bank. A diode takes that capacitor out of circuit when the switch opens,
     and Q5 resets it while C7 delays the next gate turn-on.
  3. The controller boots and drives HOLD high; the SBC may as well. Either one
     is enough, which is what lets the MCU be reflashed by the SBC -- a reset of
     one does not drop the power to the other.
  4. A comparator watches the switched bus through a 0.28 s filter. Only when the
     bus is above the cutoff AND a hold is present is the switch held on by the
     board itself, so the button can be let go. That takes about half a second.
  5. The robot turns OFF when both holds go away (after about a second, which is
     what rides through a reset) or when the filtered bus falls below about
     18.9 V, whichever comes first. It is then latched off, because everything
     that could hold it on has just lost its supply. Only the button restarts it.

The cutoff is in hardware on purpose. The MCU should see the pack sagging long
before this trips and put the robot down gracefully; this is what happens when
it does not.

WHAT THE CHECK PROVES. That every pin of every part is on exactly one net or is
excused by name, and that no net is a dead end -- the same rules
electrical/carrier.py holds its board to. And then the part that is particular
to this board: the cutoff voltage, its hysteresis, the hold time, the gate drive
across the whole bus range, the soft-start, the switch's heat and every part's
voltage rating are all COMPUTED FROM THE COMPONENT VALUES BELOW, so changing a
resistor changes the answer rather than leaving a comment behind.

NOT ONE PART ON THIS BOARD IS SURFACE MOUNT, and that is the point of its second
pass: it is a board a person can build with an iron and their eyes. The resistors
and the diodes stand on end on a 2.54 mm pitch, the comparator is a DIP, the
reference and the three small transistors are TO-92.

PROVENANCE. The MOSFET is Infineon's IRF4905PbF, datasheet rev. 2.1 of
2026-04-08: -55 V, 20 mOhm max at -10 V and 25 C, VGS +/-20 V, Crss 640 pF
typical, RthJA 62 C/W, TO-220AB with G-D-S pinout and the tab on the drain. The
hot resistance is 35 mOhm, which is figure 4's normalised curve at 125 C rather
than a tabulated maximum -- that datasheet gives no hot figure, and the one it
replaced did.

THE SWITCH WAS VISHAY'S SQP120P06-6m7L UNTIL 2026-09-22 and the change is a
sourcing one, not an electrical improvement. That part is discontinued: Vishay
still publishes the data sheet, but no distributor carries it, and its nearest
living relative in the same package -- the SUP90P06-09L at 9.3 mOhm -- is
backordered into 2028. Low-resistance P-channel in a TO-220 has become a thin
category, and what is left in it either costs four times as much per milliohm or
is surface mount.

WHAT THAT COSTS IS THREE TIMES THE RESISTANCE AND TWICE THE DEVICES. 20 mOhm
against 6.7 is the whole of the difference, and since the heat goes as the square
of the current each device carries, the answer is to share it wider: MOSFETS is 4
where it was 2, which brings the continuous rating back to 23.5 A against the old
21. THE SWITCH IS NO BETTER AND NO WORSE THAN IT WAS; it is four commodity parts
instead of two specialist ones. The IRF4905 is a fifth-generation HEXFET that has
been in volume production for twenty years, 38 000 of them on one distributor's
shelf in Denmark, and -- the reason it was preferred to a surface-mount part with
better numbers -- it is stocked in India too, at ~78 rupees, so a spare is not an
import. docs/BOM.md section 1b carries that sourcing argument.

A NOTE ON THE 24 A THIS IS SIZED AGAINST, because the arithmetic below reads
worse than it is. PEAK_CURRENT is an estimate of what six actuators draw at once
at their peak, and the dissipation line calls it "sustained", which no duty cycle
on this robot actually is. The board did not meet it before either: two of the
old parts at 24 A came to 148 C of junction against a 125 C limit, and the honest
figure was always the continuous rating beside it.

TWO PINOUTS CHANGED WITH THE PACKAGE and both are worth stating, because a
transposed one is a board that does nothing. The TL431 in TO-92 (TI's LP) is
1 REF, 2 anode, 3 cathode -- NOT the SOT-23-3's 1 cathode, 2 reference, 3 anode,
which is what this board carried while it was surface mount. The BC546B in TO-92
is 1 collector, 2 base, 3 emitter, where the BC846B in SOT-23 was 1 base,
2 emitter, 3 collector. Both are KiCad's own symbol library (TL431LP, and BC546
extending Q_NPN_CBE), which agrees with TI SLVS543 and with Nexperia's BC546
data sheet.

The fuse holder is Keystone's 3568 for mini blade fuses; its pad pattern is
KiCad's own library footprint and its height is KiCad's 3D model of the part.
Everything else is a commodity part named by its generic number.

FIVE PARTS CHANGED ON 2026-10-01, ALL FOR SOURCING, when the bill was put into
carts and three of them turned out not to exist any more. Through-hole small-
signal Schottkys have gone the way of the old switch: ST has stopped making the
BAT46, the BAT41 and the BAT48 in DO-35, and every BAT46 still on a shelf is
surface mount. So the six BAT46 are 1N4148, the silicon diode this board already
used for D3, on the same DO-35 footprint and rated 75 V against the 45 V D8 sees;
what it costs is about 0.2 V more forward drop, and the hold time below is
computed with it. The 14.7 kOhm 1 % and the 680 kOhm are not stocked in the 0204
body this board is drawn around -- only in the 0207, which does not fit -- so the
divider's bottom is 15 kOhm, moving the cutoff from 3.20 to 3.14 V a cell, and
the gate's pull to its source is 1 MOhm, which raises the gate drive at the
bottom of the bus. The WIMA MKS2 for C7 is discontinued, and KEMET's MMK5 is
the same 7.2 x 7.2 x 13 mm on the same pitch. C1 and C2 name the parts bought:
a KEMET R82, which is 7.2 mm long where the footprint was 7.0, and a dipped
KEMET C315, 50 V where the disc was 100, which the ratings below now check. It
was the C320 until 2026-10-07, which is 5.08 x 3.18 mm and did not fit the
carrier it is bought with; the C315 is the same capacitor at 3.81 x 2.54.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from carrier import Part  # noqa: E402

# ---- the component values the arithmetic reads ------------------------------
#
# Named here rather than typed into the parts list, because the check below
# computes the board's behaviour from them. A value that is only in a
# description is a value nothing checks.

# The switch.
MOSFET_RDS_ON_25C = 0.020  # ohm, max at VGS -10 V and ID -38 A
MOSFET_RDS_ON_125C = 0.035  # figure 4's normalised curve, 1.75x; not a tabulated max
MOSFET_VDS_MAX = 55.0
MOSFET_VGS_MAX = 20.0
MOSFET_CRSS = 640e-12  # typical, at f = 1 MHz
MOSFET_RTH_JA = 62.0  # C/W, a TO-220 standing in free air -- the data sheet's own max
MOSFETS = 4  # four, since the IRF4905 is 20 mOhm where the obsolete part was 6.7
GATE_CLAMP = 15.0  # BZT52C15, nominal: a clamp for transients, idle in normal use
GATE_CLAMP_RANGE = (14.3, 15.8)
R_GATE_SOURCE = 1e6  # 680 kOhm until 2026-10-01, which nobody stocks in 0204
R_GATE_PULL = 470e3
C_MILLER = 220e-9
C_GATE_SOURCE = 2.2e-6
R_RESET_BASE = 10e3
R_RESET_COLLECTOR = 1e3
R_FAST_OFF_BASE = 47e3

# The comparator and its reference.
V_REF = 2.495  # TL431A, 1 %
V_REF_TOLERANCE = 0.01
R_REF_FEED = 15e3
TL431_MIN_CATHODE_CURRENT = 1e-3

# Under-voltage: a divider, a filter, and hysteresis fed back from the output.
R_UV_TOP = 100e3
R_UV_BOTTOM = 15e3  # 14.7 kOhm until 2026-10-01, which nobody stocks in 0204
C_UV_FILTER = 22e-6
R_UV_INPUT = 22e3
R_UV_HYSTERESIS = 10e6

# Hold: two diodes into a capacitor, compared against half the reference.
V_GPIO_HIGH = 3.3
# A 1N4148 at the 30 uA the bleed draws from a held capacitor: 0.42 V on the
# silicon model power_reset.py uses, rounded up, since more drop is less hold.
# It was 0.25 V for the BAT46 until 2026-10-01.
V_HOLD_DIODE = 0.45
R_HOLD_CHARGE = 1e3
C_HOLD = 10e-6
R_HOLD_BLEED = 100e3
R_HOLD_INPUT = 22e3
R_HOLD_HYSTERESIS = 10e6
R_HOLD_REF_TOP = 100e3
R_HOLD_REF_BOTTOM = 100e3

# The output that holds the switch on.
R_ENABLE_PULLUP = 47e3
R_ENABLE_BASE = 47e3
R_ENABLE_BASE_EMITTER = 100e3
V_BE = 0.65
NPN_HFE_MIN = 200  # BC846B

# The bus.
BUS_RANGE = (18.0, 30.0)  # a flat pack under load to a leg regenerating into a full one
PACK_FULL = 25.2
CELLS = 6
PEAK_CURRENT = 24.0  # estimated, never measured
BUS_CAPACITANCE = 940e-6 + 6 * 100e-6  # the bank, plus a guess at six drivers' own
AMBIENT = 50.0
JUNCTION_LIMIT = 125.0

# A 0204 metal film resistor standing on end. The same quarter watt the 1206s
# these replaced were held to, so the dissipation check below is unchanged.
RESISTOR_POWER = 0.25


PARTS = [
    # ---- the power path ------------------------------------------------------
    Part(
        "P1",
        "pack positive in, from the pack's own connector -- 14 AWG soldered through",
        "wire pad, 3.0 mm hole",
        {"1": "in"},
    ),
    # Separate holes for the battery and the shell's charge inlet: both are
    # on raw pack positive, before the main fuse and the MOSFET switch.
    Part(
        "P5",
        "charge inlet positive, shell XT60 + -- 14 AWG soldered through",
        "wire pad, 3.0 mm hole",
        {"1": "in"},
    ),
    Part(
        "F1",
        "the main fuse, moved onto this board from an in-line holder",
        "Keystone 3568 holder + mini (ATM) blade fuse, 20 A to start",
        {"1": "a", "2": "b"},
    ),
    # FOUR IN PARALLEL, AND THEY ARE Q1, Q2, Q6 AND Q7 rather than Q1 to Q4,
    # because Q3, Q4 and Q5 are the three small signal transistors and have been
    # since this board was drawn. Renumbering them would touch this file, the
    # schematic, the board, power_reset.py and the bill for no gain a reader can
    # see; the gap is cheaper than the churn.
    Part(
        "Q1",
        "high-side switch, one of four in parallel",
        "Infineon IRF4905PbF, P-channel 55 V, TO-220AB",
        {"1": "G", "2": "D", "3": "S"},
    ),
    Part(
        "Q2",
        "high-side switch, one of four in parallel",
        "Infineon IRF4905PbF, P-channel 55 V, TO-220AB",
        {"1": "G", "2": "D", "3": "S"},
    ),
    Part(
        "Q6",
        "high-side switch, one of four in parallel",
        "Infineon IRF4905PbF, P-channel 55 V, TO-220AB",
        {"1": "G", "2": "D", "3": "S"},
    ),
    Part(
        "Q7",
        "high-side switch, one of four in parallel",
        "Infineon IRF4905PbF, P-channel 55 V, TO-220AB",
        {"1": "G", "2": "D", "3": "S"},
    ),
    # THE BULK BANK IS ON THIS BOARD NOW. It stood on the bought distribution
    # board until this one covered it, and it belongs here anyway: it is the
    # capacitance the soft start is sized to charge, and these are the two cans
    # docs/BOM.md has specified since it first named a part for the job.
    Part(
        "C5",
        "bulk bus capacitance, one of two -- the bank the soft start charges",
        "470 uF 35 V low-ESR aluminium, 10 x 16 radial",
        {"1": "+", "2": "-"},
    ),
    Part(
        "C6",
        "bulk bus capacitance, one of two",
        "470 uF 35 V low-ESR aluminium, 10 x 16 radial",
        {"1": "+", "2": "-"},
    ),
    # THE PACK'S NEGATIVE LANDS HERE TOO, since the bought distribution board
    # went: P3 was a 22 AWG ground from that board's negative, and it is the
    # whole return current now, so it is P1's size. The BMS's B- joins it on a
    # pad of its own beside it, because two leads do not share one hole.
    Part(
        "P3",
        "pack negative in, the series harness's negative leg -- 14 AWG soldered through",
        "wire pad, 3.0 mm hole",
        {"1": "gnd"},
    ),
    Part(
        "P4",
        "the BMS's B-, which meets the pack's negative here -- 16 AWG",
        "wire pad, 2.15 mm hole",
        {"1": "gnd"},
    ),
    # ---- the distribution ----------------------------------------------------
    # SIX MOTOR OUTPUTS ON PLUGS, 2026-10-07, where there were six pairs of
    # solder tabs on a bought board. A motor's own plug is a JST-SH whose three
    # 1 A contacts a side are what limits its branch, so two JST-PH contacts a
    # side, 2 A each, are more than the branch can use. PH AND NOT XH because
    # nothing else in the robot is PH: a power lead cannot be pushed into one of
    # the XH signal sockets. It was chosen while the board was notched under the
    # deck's ledges, for its length -- a four-pin is 10.9 mm where an XH five-pin
    # is 15.9 -- and kept when the notches went, for the keying and because its
    # ready-made leads are the ones whose wire gauge is published.
    #
    # NOT FUSED ONE BY ONE. A resettable fuse per output was the intention, and
    # a radial one that will stand a 30 V bus is a 12 mm disc: there is room on
    # this board for one or two, not six. One in each motor lead was the next
    # idea, and the owner dropped it on 2026-10-07. The 20 A main fuse covers
    # the outputs together.
    *(
        Part(
            f"J{n}",
            f"motor output {n - 3}: 1 and 2 the switched bus, 3 and 4 ground",
            "JST-PH 4-pin",
            {"1": "VBUS", "2": "VBUS", "3": "GND", "4": "GND"},
        )
        for n in range(4, 10)
    ),
    # THE CARRIER'S FEED, which came off the bought board's tabs as well. Three
    # pins so that one ground pin is all the bus copper under it has to step
    # round; the carrier fuses its own end.
    Part(
        "J10",
        "the carrier's feed: 1 and 2 the switched bus, 3 ground",
        "JST-XH 3-pin",
        {"1": "VBUS", "2": "VBUS", "3": "GND"},
    ),
    # ---- the gate drive ------------------------------------------------------
    Part(
        "R2",
        "gate to source: off by default, and half of the gate divider",
        "1 MOhm, 0204 metal film",
        {"1": "1", "2": "2"},
    ),
    Part(
        "D1",
        "gate clamp for transients: idle while the bus is in range",
        "BZX79-C15, 15 V 0.5 W zener, DO-35",
        {"1": "K", "2": "A"},
    ),
    # ONE RESISTOR PER PAIR OF DEVICES, NOT PER DEVICE, and that is a departure
    # worth reading before it is copied. Paralleled MOSFETs whose gates are tied
    # hard together can ring against one another's capacitance through the gate
    # loop, and the usual guard is a few ohms in each gate. There is no room on
    # this board for two more of them -- with the second row of switches down,
    # legalize() finds five legal positions on the whole 50 x 50 for one more
    # 0204, all of them 10 to 23 mm from the gate they would serve, which is
    # further than the track they would be damping.
    #
    # It is defensible here because THIS IS NOT A SWITCHING CONVERTER. The gates
    # move twice in a power cycle: up over the 130 ms soft-start below, and down
    # through Q4 in milliseconds. Parasitic oscillation between paralleled
    # devices is a hard-switching problem, and nothing on this board switches
    # hard. If a built board rings, the fix is one resistor per device and a
    # bigger board, and that is the trade this comment exists to record.
    Part(
        "R3",
        "gate resistor for Q1 and Q6",
        "10 Ohm, 0204 metal film",
        {"1": "1", "2": "2"},
    ),
    Part(
        "R4",
        "gate resistor for Q2 and Q7",
        "10 Ohm, 0204 metal film",
        {"1": "1", "2": "2"},
    ),
    Part(
        "C1",
        "Miller capacitor, drain to gate through D8: the soft-start",
        "KEMET R82DC3220AA60K, 220 nF 63 V film, 5 mm pitch",
        {"1": "1", "2": "2"},
    ),
    Part(
        "D8",
        "lets C1 slow the drain rising and not the switch opening",
        "1N4148, DO-35",
        {"1": "K", "2": "A"},
    ),
    Part(
        "Q5",
        "actively resets C1",
        "BC546B NPN 65 V, TO-92",
        {"1": "C", "2": "B", "3": "E"},
    ),
    Part(
        "C7",
        "holds the gates off while C1 resets",
        "KEMET MMK5225K63J06L4BULK, 2.2 uF 63 V 10 %, 5 mm pitch",
        {"1": "1", "2": "2"},
    ),
    Part(
        "R25", "Q5 base current limit", "10 kOhm, 0204 metal film", {"1": "1", "2": "2"}
    ),
    Part(
        "R26",
        "Q5 collector current limit",
        "1 kOhm 1 W, PR01 axial",
        {"1": "1", "2": "2"},
    ),
    Part(
        "R5",
        "gate pull-down, which sets how fast the soft-start slews",
        "470 kOhm, 0204 metal film",
        {"1": "1", "2": "2"},
    ),
    Part(
        "Q3",
        "holds the gates down while the board says ON",
        "BC546B NPN 65 V, TO-92",
        {"1": "C", "2": "B", "3": "E"},
    ),
    Part("R6", "Q3 base", "47 kOhm, 0204 metal film", {"1": "1", "2": "2"}),
    Part("R7", "Q3 base to emitter", "100 kOhm, 0204 metal film", {"1": "1", "2": "2"}),
    Part(
        "Q4",
        "pulls the gates back up fast when the hold lets go",
        "BC546B NPN 65 V, TO-92",
        {"1": "C", "2": "B", "3": "E"},
    ),
    Part(
        "R8",
        "Q4 base, from the source",
        "47 kOhm, 0204 metal film",
        {"1": "1", "2": "2"},
    ),
    Part(
        "R9",
        "Q4 base to emitter, so its emitter never floats",
        "1 MOhm, 0204 metal film",
        {"1": "1", "2": "2"},
    ),
    Part(
        "D2",
        "Q4's emitter to the gate, one way only",
        "1N4148, DO-35",
        {"1": "K", "2": "A"},
    ),
    Part(
        "D3",
        "holds Q4's base down while the gates are held",
        "1N4148, DO-35",
        {"1": "K", "2": "A"},
    ),
    # ---- the cutoff and the hold ---------------------------------------------
    Part(
        "U1",
        "dual comparator, both outputs on the one enable line",
        "LM393P, DIP-8",
        {
            "1": "OUTA",
            "2": "INA-",
            "3": "INA+",
            "4": "GND",
            "5": "INB+",
            "6": "INB-",
            "7": "OUTB",
            "8": "VCC",
        },
    ),
    Part(
        "C2",
        "U1 supply",
        "KEMET C315C104K5R5TA, 100 nF 50 V X7R, 2.54 mm",
        {"1": "1", "2": "2"},
    ),
    Part(
        "U2",
        "the 2.495 V reference both comparators use",
        "TL431ACLP, TO-92",
        {"1": "REF", "2": "A", "3": "K"},
    ),
    Part("R10", "reference feed", "15 kOhm, 0204 metal film", {"1": "1", "2": "2"}),
    Part(
        "R11", "bus divider, top", "100 kOhm 1 %, 0204 metal film", {"1": "1", "2": "2"}
    ),
    Part(
        "R12",
        "bus divider, bottom",
        "15 kOhm 1 %, 0204 metal film",
        {"1": "1", "2": "2"},
    ),
    Part(
        "C3",
        "cutoff filter: a motor's sag is not a flat pack",
        "22 uF 16 V solid tantalum, radial",
        {"1": "1", "2": "2"},
    ),
    Part(
        "R13",
        "cutoff comparator input",
        "22 kOhm, 0204 metal film",
        {"1": "1", "2": "2"},
    ),
    Part("R14", "cutoff hysteresis", "10 MOhm, 0204 metal film", {"1": "1", "2": "2"}),
    Part("R15", "enable pull-up", "47 kOhm, 0204 metal film", {"1": "1", "2": "2"}),
    Part(
        "D4",
        "MCU hold in",
        "1N4148, DO-35",
        {"1": "K", "2": "A"},
    ),
    Part(
        "D5",
        "SBC hold in",
        "1N4148, DO-35",
        {"1": "K", "2": "A"},
    ),
    Part(
        "R16",
        "MCU hold pull-down: a loose wire is OFF",
        "100 kOhm, 0204 metal film",
        {"1": "1", "2": "2"},
    ),
    Part(
        "R17",
        "SBC hold pull-down: a loose wire is OFF",
        "100 kOhm, 0204 metal film",
        {"1": "1", "2": "2"},
    ),
    Part("R18", "hold charge", "1 kOhm, 0204 metal film", {"1": "1", "2": "2"}),
    Part(
        "C4",
        "hold capacitor: what rides through a reset",
        "10 uF 16 V solid tantalum, radial",
        {"1": "1", "2": "2"},
    ),
    Part("R19", "hold bleed", "100 kOhm, 0204 metal film", {"1": "1", "2": "2"}),
    Part(
        "R20", "hold comparator input", "22 kOhm, 0204 metal film", {"1": "1", "2": "2"}
    ),
    Part("R21", "hold hysteresis", "10 MOhm, 0204 metal film", {"1": "1", "2": "2"}),
    Part(
        "R22",
        "hold threshold, top",
        "100 kOhm 1 %, 0204 metal film",
        {"1": "1", "2": "2"},
    ),
    Part(
        "R23",
        "hold threshold, bottom",
        "100 kOhm 1 %, 0204 metal film",
        {"1": "1", "2": "2"},
    ),
    # ---- the button ----------------------------------------------------------
    Part(
        "D6",
        "the button pulls the gates down through this",
        "1N4148, DO-35",
        {"1": "K", "2": "A"},
    ),
    Part(
        "D7",
        "and the MCU reads the same button through this",
        "1N4148, DO-35",
        {"1": "K", "2": "A"},
    ),
    # ---- what plugs in -------------------------------------------------------
    # ONE HOUSING FOR BOTH HOLDS, and the lead splits after it: three wires to
    # the carrier, one to a GPIO on the SBC's 40-pin header. The SBC needs no
    # ground of its own on this plug -- it already shares the carrier's.
    Part(
        "J2",
        "the MCU's hold and the button as its input; the SBC's hold on pin 4",
        "JST-XH 4-pin",
        {"1": "HOLD", "2": "SENSE", "3": "GND", "4": "HOLD2"},
    ),
    Part(
        "J3",
        "the push button; a shorting link here is ON for the bench",
        "JST-XH 2-pin",
        {"1": "BTN", "2": "GND"},
    ),
]

NETS: dict[str, list[tuple[str, str]]] = {
    # THE POWER PATH, in the order the current takes it. With the robot off the
    # only live copper on this board is the fuse and the MOSFET sources.
    #
    # THE DRAINS AND THE BUS ARE ONE NET. They were two, VDRN and VBUS, with the
    # Kelvin shunt between them; with the shunt gone there is nothing in the path
    # to separate, so the switched bus runs from the drains straight to the
    # outputs. C1 hangs off it as before -- the Miller capacitor watches the
    # drains, and the drains are the bus.
    "BATT": [("P1", "1"), ("P5", "1"), ("F1", "1")],
    "VSRC": [
        ("F1", "2"),
        ("Q1", "3"),
        ("Q2", "3"),
        ("Q6", "3"),
        ("Q7", "3"),
        ("R2", "1"),
        ("D1", "1"),
        ("Q4", "1"),
        ("R8", "1"),
        ("C7", "1"),
        ("R26", "1"),
    ],
    "VBUS": [
        ("Q1", "2"),
        ("Q2", "2"),
        ("Q6", "2"),
        ("Q7", "2"),
        ("C1", "2"),
        *((f"J{n}", pin) for n in range(4, 11) for pin in ("1", "2")),
        ("C5", "1"),
        ("C6", "1"),
        ("U1", "8"),
        ("C2", "1"),
        ("R10", "1"),
        ("R11", "1"),
        ("R15", "1"),
    ],
    # THE GATES. Clamped to their sources, each behind its own resistor, and
    # pulled down only through R5 -- so the soft-start is the same whether the
    # button or the board is holding them.
    "GATE": [
        ("R2", "2"),
        ("D1", "2"),
        ("R3", "1"),
        ("R4", "1"),
        ("D8", "1"),
        ("R5", "1"),
        ("D2", "1"),
        ("C7", "2"),
        ("R25", "1"),
    ],
    # THE MILLER NODE. While the drain rises, C1 pushes current through D8 into
    # the gates and holds the slew to what R5 can pull against it. When the
    # drain falls, D8 blocks, so Q4 is not fighting 220 nF to turn the switch
    # off. Q5 restores MILLER toward GATE minus one VBE. C7 slows the next
    # gate fall while this happens, including connection with ON already held.
    "MILLER": [("C1", "1"), ("D8", "2"), ("Q5", "3")],
    "RESET_B": [("R25", "2"), ("Q5", "2")],
    "RESET_C": [("R26", "2"), ("Q5", "1")],
    "G1": [("R3", "2"), ("Q1", "1"), ("Q6", "1")],
    "G2": [("R4", "2"), ("Q2", "1"), ("Q7", "1")],
    # THE NODE EVERYTHING THAT TURNS THE ROBOT ON PULLS DOWN: Q3 for the board,
    # D6 for the button. When neither does, R8 lifts Q4's base and Q4 drags the
    # gates up to the source in milliseconds.
    "PULL": [("R5", "2"), ("Q3", "1"), ("D3", "1"), ("D6", "2")],
    "FAST_B": [("R8", "2"), ("Q4", "2"), ("D3", "2"), ("R9", "1")],
    "FAST_E": [("Q4", "3"), ("D2", "2"), ("R9", "2")],
    # THE ENABLE LINE. Two open-collector outputs on one pull-up is an AND:
    # either comparator can hold it low, and it is high only if neither does.
    "EN": [
        ("U1", "1"),
        ("U1", "7"),
        ("R15", "2"),
        ("R14", "1"),
        ("R21", "1"),
        ("R6", "1"),
    ],
    "EN_B": [("R6", "2"), ("Q3", "2"), ("R7", "1")],
    "REF": [("R10", "2"), ("U2", "3"), ("U2", "1"), ("U1", "2"), ("R22", "1")],
    "UV_DIV": [("R11", "2"), ("R12", "1"), ("C3", "1"), ("R13", "1")],
    "UV_IN": [("R13", "2"), ("R14", "2"), ("U1", "3")],
    "HOLD_REF": [("R22", "2"), ("R23", "1"), ("U1", "6")],
    "HOLD_MCU": [("J2", "1"), ("D4", "2"), ("R16", "1")],
    "HOLD_SBC": [("J2", "4"), ("D5", "2"), ("R17", "1")],
    "HOLD_OR": [("D4", "1"), ("D5", "1"), ("R18", "1")],
    "HOLD_CAP": [("R18", "2"), ("C4", "1"), ("R19", "1"), ("R20", "1")],
    "HOLD_IN": [("R20", "2"), ("R21", "2"), ("U1", "5")],
    "BTN": [("J3", "1"), ("D6", "1"), ("D7", "1")],
    "SENSE": [("J2", "2"), ("D7", "2")],
    "GND": [
        ("P3", "1"),
        ("P4", "1"),
        *((f"J{n}", pin) for n in range(4, 10) for pin in ("3", "4")),
        ("J10", "3"),
        ("Q3", "3"),
        ("R7", "2"),
        ("U1", "4"),
        ("C2", "2"),
        ("U2", "2"),
        ("R12", "2"),
        ("C3", "2"),
        ("R16", "2"),
        ("R17", "2"),
        ("C4", "2"),
        ("R19", "2"),
        ("R23", "2"),
        ("C5", "2"),
        ("C6", "2"),
        ("J2", "3"),
        ("J3", "2"),
    ],
}

# Nothing on this board is left unconnected on purpose.
UNCONNECTED: dict[tuple[str, str], str] = {}


# ---- the checks --------------------------------------------------------------


def check_netlist() -> list[str]:
    """The rules electrical/carrier.py holds its board to, on this one."""
    faults: list[str] = []
    parts = {part.refdes: part for part in PARTS}
    seen: dict[tuple[str, str], str] = {}
    for net, endpoints in NETS.items():
        if len(endpoints) < 2:
            faults.append(f"{net}: only {len(endpoints)} endpoint, so it goes nowhere")
        for refdes, pin in endpoints:
            if refdes not in parts:
                faults.append(f"{net}: no such part {refdes}")
            elif pin not in parts[refdes].pins:
                faults.append(f"{net}: {refdes} has no pin {pin}")
            if (refdes, pin) in seen:
                faults.append(
                    f"{refdes}-{pin}: on both {seen[(refdes, pin)]} and {net}"
                )
            seen[(refdes, pin)] = net
    for part in PARTS:
        for pin in part.pins:
            if (part.refdes, pin) not in seen and (part.refdes, pin) not in UNCONNECTED:
                faults.append(f"{part.refdes}-{pin} is on no net and is not excused")
    return faults


def _series(*values: float) -> float:
    return sum(values)


def _parallel(*values: float) -> float:
    return 1.0 / sum(1.0 / value for value in values)


def cutoff() -> dict[str, float]:
    """Where the bus has to fall to turn the robot off, and rise to let it on.

    Solved as the two-node circuit it is, not as a divider with a correction:
    the hysteresis current flows through the filter node's own resistance as
    well as through the input resistor, and on a divider of this impedance the
    first of those is a third of the effect. Getting that wrong is how a
    0.4 V hysteresis turns out to be 2.6 V on the bench.
    """
    ratio = R_UV_BOTTOM / (R_UV_TOP + R_UV_BOTTOM)
    thevenin = _parallel(R_UV_TOP, R_UV_BOTTOM)

    def comparator_input(bus: float, enable: float) -> float:
        # Nodal: the divider node sees the divider's Thevenin source and the
        # feedback string R13 + R14 to the enable line. The comparator's own
        # input current is tens of nanoamps and is left out.
        source = bus * ratio
        feedback = _series(R_UV_INPUT, R_UV_HYSTERESIS)
        node = (source / thevenin + enable / feedback) / (1 / thevenin + 1 / feedback)
        return node + (enable - node) * R_UV_INPUT / feedback

    def trip(enable: float) -> float:
        low, high = 5.0, 40.0
        for _ in range(60):
            middle = (low + high) / 2
            if comparator_input(middle, enable) > V_REF:
                high = middle
            else:
                low = middle
        return (low + high) / 2

    enabled = enable_level(PACK_FULL)
    return {
        "falls to": trip(enabled),
        "rises to": trip(0.1),
        "filter": thevenin * C_UV_FILTER,
    }


def enable_level(bus: float) -> float:
    """What the enable line sits at when both comparators let it go."""
    # R15 from the bus into the node; R6 then Q3's base-emitter and R7 to ground.
    base_current_path = R_ENABLE_BASE
    return (bus * base_current_path + V_BE * R_ENABLE_PULLUP) / (
        R_ENABLE_PULLUP + base_current_path
    )


def hold_time() -> float:
    """How long the switch stays on after the last hold input lets go."""
    start = V_GPIO_HIGH - V_HOLD_DIODE
    start -= start * R_HOLD_CHARGE / (R_HOLD_CHARGE + R_HOLD_BLEED)
    threshold = V_REF * R_HOLD_REF_BOTTOM / (R_HOLD_REF_TOP + R_HOLD_REF_BOTTOM)
    enabled = enable_level(PACK_FULL)
    # With the enable line high, R20 + R21 feed a little current back into the
    # capacitor, so it decays towards that offset rather than to zero.
    offset = enabled * R_HOLD_BLEED / (R_HOLD_BLEED + R_HOLD_INPUT + R_HOLD_HYSTERESIS)
    lift = (enabled - threshold) * R_HOLD_INPUT / (R_HOLD_INPUT + R_HOLD_HYSTERESIS)
    tau = R_HOLD_BLEED * C_HOLD
    return tau * math.log((start - offset) / (threshold - lift - offset))


def gate_drive(bus: float) -> float:
    """VGS with the board holding the switch on, at this bus voltage.

    The gate node is a divider -- R2 up to the source, R5 down to a saturated
    Q3. Q5 is off during steady ON operation. The zener only matters
    at the top of the bus, where the divider alone would overdrive the gate.
    """
    low, high = 0.0, bus
    for _ in range(60):
        vgs = (low + high) / 2
        up = vgs / R_GATE_SOURCE
        down = (bus - 0.1 - vgs) / R_GATE_PULL
        if up > down:
            high = vgs
        else:
            low = vgs
    return min((low + high) / 2, GATE_CLAMP)


def check_arithmetic() -> tuple[list[str], list[str]]:
    """Everything this board does, worked out from the values above."""
    faults: list[str] = []
    lines: list[str] = []

    # The cutoff.
    cut = cutoff()
    per_cell = cut["falls to"] / CELLS
    lines.append(
        f"cutoff          off below {cut['falls to']:.2f} V ({per_cell:.2f} V per cell), "
        f"on again above {cut['rises to']:.2f} V, filtered over {cut['filter']:.2f} s"
    )
    worst_low = cut["falls to"] * (1 - V_REF_TOLERANCE - 0.02)
    worst_high = cut["falls to"] * (1 + V_REF_TOLERANCE + 0.02)
    lines.append(
        f"                {worst_low:.2f} to {worst_high:.2f} V with the reference and "
        "the divider at the ends of their tolerance"
    )
    if not 3.05 <= per_cell <= 3.35:
        faults.append(f"cutoff at {per_cell:.2f} V per cell: wants 3.05 to 3.35")
    hysteresis = cut["rises to"] - cut["falls to"]
    if not 0.2 <= hysteresis <= 0.8:
        faults.append(f"cutoff hysteresis {hysteresis:.2f} V: wants 0.2 to 0.8")

    # How long the button has to be held, from a full pack and from a tired one.
    ratio = R_UV_BOTTOM / (R_UV_TOP + R_UV_BOTTOM)
    rise_threshold = cut["rises to"] * ratio
    for pack in (PACK_FULL, 21.0):
        target = pack * ratio
        wait = cut["filter"] * math.log(target / (target - rise_threshold))
        lines.append(
            f"button          hold about {wait:.2f} s to switch on from {pack:.1f} V"
        )
        if wait > 1.5:
            faults.append(f"the button needs {wait:.2f} s at {pack} V: too long")

    # The hold.
    held = hold_time()
    lines.append(
        f"hold            stays on {held:.2f} s after the last hold input drops"
    )
    if not 0.5 <= held <= 2.0:
        faults.append(f"hold time {held:.2f} s: wants 0.5 to 2.0")

    # The gate drive, at both ends of the bus.
    for bus in BUS_RANGE:
        vgs = gate_drive(bus)
        lines.append(f"gate drive      VGS -{vgs:.1f} V at {bus:.0f} V")
        if vgs < 10.0:
            faults.append(f"VGS only -{vgs:.1f} V at {bus} V: Rds(on) is rated at -10")
    if GATE_CLAMP_RANGE[1] > MOSFET_VGS_MAX:
        faults.append("the gate clamp can exceed the MOSFET's VGS rating")

    # The soft-start. On the Miller plateau the gate stands still about 3 V
    # below the source and everything R5 pulls goes into C1 as the drain rises.
    plateau = 3.0
    pull = (PACK_FULL - plateau) / R_GATE_PULL - plateau / R_GATE_SOURCE
    slew = pull / (C_MILLER + MOSFETS * MOSFET_CRSS)
    inrush = BUS_CAPACITANCE * slew
    ramp = PACK_FULL / slew
    lines.append(
        f"soft-start      {slew:.0f} V/s, {ramp * 1e3:.0f} ms to full, "
        f"about {inrush:.2f} A into {BUS_CAPACITANCE * 1e6:.0f} uF"
    )
    if inrush > 2.0:
        faults.append(f"inrush {inrush:.1f} A: the soft-start is not soft")
    if ramp > 0.4:
        faults.append(f"soft-start {ramp:.2f} s: longer than the button wants")

    # Q4's base drive falls as GATE rises. Initial current / Qgd did not bound
    # turn-off and omitted the reset capacitor. Use the transient regression.
    lines.append("C1 reset        Q5 active reset, C7 2.2 uF gate delay; R24 removed")
    lines.append("switch-off      see power_reset.py; loaded MOSFET SOA unverified")

    # Enough base drive to hold the gates.
    enabled = enable_level(BUS_RANGE[0])
    base = (enabled - V_BE) / R_ENABLE_BASE - V_BE / R_ENABLE_BASE_EMITTER
    collector = BUS_RANGE[1] / R_GATE_PULL + BUS_RANGE[1] / R_FAST_OFF_BASE
    if base * NPN_HFE_MIN < 3 * collector:
        faults.append("Q3 is not driven hard enough to saturate")

    # The switch's heat. Hot resistance, both halves sharing.
    per_fet = PEAK_CURRENT / MOSFETS
    watts = per_fet**2 * MOSFET_RDS_ON_125C
    rise = watts * MOSFET_RTH_JA
    continuous = MOSFETS * math.sqrt(
        (JUNCTION_LIMIT - AMBIENT) / MOSFET_RTH_JA / MOSFET_RDS_ON_125C
    )
    lines.append(
        f"switch          {watts:.2f} W per MOSFET at a sustained {PEAK_CURRENT:.0f} A "
        f"({rise:.0f} C over ambient); {continuous:.0f} A continuous keeps "
        f"{JUNCTION_LIMIT:.0f} C at {AMBIENT:.0f} C ambient"
    )
    # Resistor dissipation at the top of the bus, against a 0204's quarter watt.
    top = BUS_RANGE[1]
    worst = {
        "R5": (top - gate_drive(top)) ** 2 / R_GATE_PULL,
        "R8": top**2 / R_FAST_OFF_BASE,
        "R10": (top - V_REF) ** 2 / R_REF_FEED,
        "R11": (top * R_UV_TOP / (R_UV_TOP + R_UV_BOTTOM)) ** 2 / R_UV_TOP,
        "R15": top**2 / R_ENABLE_PULLUP,
    }
    for refdes, watts in worst.items():
        if watts > RESISTOR_POWER / 2:
            faults.append(f"{refdes} dissipates {watts * 1e3:.0f} mW at {top} V")
    lines.append(
        "dissipation     worst resistor "
        + max(worst, key=worst.get)
        + f" at {max(worst.values()) * 1e3:.0f} mW of 250"
    )

    # The reference has to stay in regulation at the bottom of the bus.
    feed = (BUS_RANGE[0] - V_REF) / R_REF_FEED - V_REF / _series(
        R_HOLD_REF_TOP, R_HOLD_REF_BOTTOM
    )
    if feed < TL431_MIN_CATHODE_CURRENT:
        faults.append(f"TL431 gets {feed * 1e3:.2f} mA at {BUS_RANGE[0]} V: wants 1")

    # Voltage ratings, against the highest voltage each part can see.
    ratings = {
        "Q1/Q2/Q6/Q7 VDS": (MOSFET_VDS_MAX, top),
        "U1 supply (LM393, 36 V)": (36.0, top),
        "Q3/Q4 VCE (BC546B, 65 V)": (65.0, top),
        "Q5 VCE (BC546B, 65 V)": (65.0, top + gate_drive(top)),
        "D2/D4-D7 reverse (1N4148, 75 V)": (75.0, top),
        "D3 reverse (1N4148, 75 V)": (75.0, top),
        # Off, with the drain discharged: the gate is at the source and C1's
        # far end has been pulled a clamp's worth below ground.
        "D8 reverse (1N4148, 75 V)": (75.0, top + gate_drive(top)),
        "C1 (63 V)": (63.0, top),
        "C2 (50 V)": (50.0, top),
        "C7 (63 V)": (63.0, GATE_CLAMP_RANGE[1]),
    }
    for what, (rating, seen) in ratings.items():
        if seen > rating * 0.85:
            faults.append(f"{what}: sees {seen} V of {rating}")

    return faults, lines


def check() -> list[str]:
    faults = check_netlist()
    more, _ = check_arithmetic()
    return faults + more


# ---- the tables ----------------------------------------------------------------


def netlist() -> str:
    lines = ["Netlist", ""]
    for net, endpoints in NETS.items():
        joined = "  ".join(f"{refdes}-{pin}" for refdes, pin in endpoints)
        lines.append(f"  {net:<10}{joined}")
    return "\n".join(lines)


def parts_list() -> str:
    lines = ["Parts", ""]
    for part in PARTS:
        lines.append(f"  {part.refdes:<5}{part.partNumber}")
        lines.append(f"       {part.description}")
    return "\n".join(lines)


def main() -> int:
    faults = check_netlist()
    arithmetic, lines = check_arithmetic()
    faults += arithmetic
    print("What the switch does, from the component values\n")
    for line in lines:
        print(f"  {line}")
    print()
    if faults:
        print("power: FAILED")
        for fault in faults:
            print(f"  {fault}")
        return 1
    print("power: every pin checks out and the arithmetic holds\n")
    print(netlist())
    print()
    print(parts_list())
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
