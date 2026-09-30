# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1", "numpy>=1.26", "matplotlib>=3.8", "shapely>=2.0"]
# ///
"""Draw the power switch board as an ordinary schematic, one A3 sheet.

    uv run electrical/power_sch.py

electrical/power.py is the netlist and it is the thing that is checked. This
file DRAWS it: standard symbols, wires between them, and the circuit laid out
in the four blocks somebody reads it in -- the power path, the gate drive, the
reference and its comparators, and the hold with its button.

IT WAS A TABLE OF BOXES AND LABELS until September 2026, one generated symbol
per part with its net's name on a stub off every pin. That is legible to a
machine and to whoever wrote it, and to nobody else: a resistor looked like a
diode looked like a comparator, and following a signal meant searching the
sheet for its name. This version uses KICAD'S OWN SYMBOLS -- Device:R,
Device:D_Zener, Transistor_FET:Q_PMOS_GDS, Comparator:LM393 in its three real
units -- so a part looks like what it is, and joins them with WIRE.

WHAT IS STILL A LABEL, and it is deliberate rather than a shortfall. Six nets
run the width of the board: the pack rail, the switched bus, the gates, the
enable line and ground. Drawing those as lines between four corners of a sheet
is how a schematic becomes unreadable, so each is wired within the block it
belongs to and carries its name where it leaves. That is how the drawing would
be done by hand, and every label on this sheet names a net that power.py
declares.

HOW THE WIRES ARE BUILT. A net is one or more TRUNKS -- a horizontal or
vertical line -- with a stub from each of its pins onto it, and a junction dot
wherever three wires meet. A pin already standing on the trunk gets no stub; a
pin pointing along the trunk rather than at it turns a corner first. Crossing
wires do not touch, which is what lets the blocks sit side by side.

NOTHING HERE IS TRUSTED. The sheet is handed to kicad-cli, which extracts its
netlist, and that netlist is compared pin by pin with power.py's NETS. A wire
that misses a pad by a tenth of a millimetre, a stub that lands on the wrong
trunk, a junction that should be there and is not -- all of them come out as a
net that does not match, and the script fails. KiCad's own ERC runs after it.

EVERY SYMBOL NAMES THE FOOTPRINT THE BOARD REALLY USES, read out of
electrical/power_pcb.py rather than written again here, so the drawing and the
copper cannot disagree about what package a part is in.
"""

from __future__ import annotations

import sys
import uuid as uuidlib
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "electrical"))

import kicad_symbols as ksym  # noqa: E402
import power  # noqa: E402
import power_pcb  # noqa: E402

OUT = ROOT / "electrical" / "kicad_power"

FONT = "(effects (font (size 1.27 1.27)))"
STUB = 5.08
RISE = 2.54
GRID = 1.27


# ---- which KiCad symbol draws which part -------------------------------------------
#
# Every one of these is a stock symbol whose PIN NUMBERS already match the
# footprint the board uses, which is the thing that has to be true for the
# drawing and the copper to mean the same part. Two were worth choosing
# carefully: Reference_Voltage:TL431LP is the TO-92 pinout, 1 REF 2 anode 3 cathode,
# and NOT the TL431P's; and Comparator:LM393 is drawn as three units, the two
# comparators and the supply, which is how the wired-AND on the enable line
# becomes visible instead of being asserted.
SYMBOL_OF = {
    "P1": "Connector_Generic:Conn_01x01",
    "P2": "Connector_Generic:Conn_01x01",
    "P3": "Connector_Generic:Conn_01x01",
    "F1": "Device:Fuse",
    "Q1": "Transistor_FET:Q_PMOS_GDS",
    "Q2": "Transistor_FET:Q_PMOS_GDS",
    "Q6": "Transistor_FET:Q_PMOS_GDS",
    "Q7": "Transistor_FET:Q_PMOS_GDS",
    "Q3": "Transistor_BJT:BC546",
    "Q4": "Transistor_BJT:BC546",
    "Q5": "Transistor_BJT:BC546",
    "C7": "Device:C",
    "U1": "Comparator:LM393",
    "U2": "Reference_Voltage:TL431LP",
    "C1": "Device:C",
    "C2": "Device:C",
    "C3": "Device:C_Polarized",
    "C4": "Device:C_Polarized",
    "C5": "Device:C_Polarized",
    "C6": "Device:C_Polarized",
    "D1": "Device:D_Zener",
    "D2": "Device:D_Schottky",
    "D3": "Device:D",
    "D8": "Device:D_Schottky",
    "D4": "Device:D_Schottky",
    "D5": "Device:D_Schottky",
    "D6": "Device:D_Schottky",
    "D7": "Device:D_Schottky",
    "J3": "Connector_Generic:Conn_01x02",
    "J2": "Connector_Generic:Conn_01x04",
}
SYMBOL_OF.update({f"R{n}": "Device:R" for n in range(2, 27) if n != 24})


# ---- where each part stands, and which way up --------------------------------------
#
# Four blocks, each drawn the way that circuit is drawn: the power path runs
# left to right across the whole top, the pack pad at one edge of the sheet and
# the bus pad at the other, with the two switches stacked in parallel and the
# bank hanging off the bus; the gate drive sits under its left end with the
# source rail along its top and the gate bus across its middle; the reference
# and the two comparators are in the band under the bus rail; the hold and the
# button are bottom right.
#
# WHICH WAY THE SHEET READS, because it is asked of every schematic and the
# answer here is not the usual one. The power path reads left to right, pack to
# bus. The control is a FEEDBACK LOOP around it: it senses the bus at the
# right-hand end of that path and drives the gates near its left-hand end,
# because the fuse has to come before the switches and the shunt after them. So
# the lower half returns right to left, and the hold and the button are drawn
# that way on purpose -- their connectors are at the right edge and their
# signals run leftward into the comparators and on into the gate drive. Putting
# those connectors on the left would not remove the reversal, only move it onto
# GATE. What is worth insisting on is that nothing reads against its own block:
# the button's two diodes take BTN from the right and hand PULL and SENSE out
# to the left, and the gate resistors stand ABOVE the gate rail so that G1 and
# G2 leave pointing at the MOSFETs they feed rather than away from them.
#
# A part is (unit, x, y, rotation, mirror). Rotation is counter-clockwise and
# the y axis points down the sheet -- kicad_symbols.py carries the whole of what
# that means and the evidence it was checked with.
PLACEMENT: dict[str, list[tuple[int, float, float, float, str | None]]] = {
    # the power path
    "P1": [(1, 25.40, 45.72, 0, "y")],
    "F1": [(1, 45.72, 45.72, 90, None)],
    # FOUR SWITCHES SINCE 2026-09-22, and the two added ones sit side by side
    # below the pair that were here rather than continuing their column. Q7
    # WAS AT (76.20, 119.38) AND THAT WAS A SHORT: a P-MOS turned this way puts
    # its gate 5.08 mm above itself, which is exactly the y the source trunk
    # runs along to reach R8 and Q4, so G2 and VSRC came out as one net.
    # check_drawing() refused it, which is the whole point of that check.
    "Q1": [(1, 76.20, 43.18, 270, None)],
    "Q2": [(1, 76.20, 68.58, 270, None)],
    "Q6": [(1, 76.20, 93.98, 270, None)],
    "Q7": [(1, 101.60, 93.98, 270, None)],
    "C5": [(1, 127.00, 60.96, 0, None)],
    "C6": [(1, 152.40, 60.96, 0, None)],
    "P2": [(1, 373.38, 45.72, 0, None)],
    "P3": [(1, 368.30, 83.82, 0, None)],
    # the gate drive
    "R2": [(1, 33.02, 129.54, 0, None)],
    "D1": [(1, 48.26, 129.54, 270, None)],
    "C1": [(1, 68.58, 129.54, 0, "x")],
    "D8": [(1, 76.20, 142.24, 90, None)],
    "C7": [(1, 30.48, 228.60, 0, None)],
    "R25": [(1, 63.50, 228.60, 90, None)],
    "Q5": [(1, 91.44, 228.60, 0, None)],
    "R26": [(1, 93.98, 208.28, 0, None)],
    "R3": [(1, 99.06, 144.78, 180, None)],
    "R4": [(1, 111.76, 144.78, 180, None)],
    "R5": [(1, 129.54, 154.94, 0, None)],
    "D2": [(1, 144.78, 154.94, 270, None)],
    "Q3": [(1, 127.00, 177.80, 0, None)],
    "R6": [(1, 109.22, 177.80, 90, None)],
    "R7": [(1, 116.84, 190.50, 0, None)],
    "R8": [(1, 147.32, 121.92, 0, None)],
    "Q4": [(1, 165.10, 137.16, 0, None)],
    "R9": [(1, 154.94, 154.94, 0, None)],
    "D3": [(1, 137.16, 163.83, 0, None)],
    # the reference and the comparators
    "R10": [(1, 228.60, 96.52, 0, None)],
    "U2": [(1, 228.60, 116.84, 90, None)],
    "R11": [(1, 241.30, 96.52, 0, None)],
    "R12": [(1, 241.30, 116.84, 0, None)],
    "C3": [(1, 254.00, 116.84, 0, None)],
    "R13": [(1, 259.08, 106.68, 90, None)],
    "R14": [(1, 266.70, 88.90, 0, None)],
    "R15": [(1, 292.10, 96.52, 0, None)],
    "C2": [(1, 342.90, 55.88, 0, None)],
    "R22": [(1, 241.30, 152.40, 0, None)],
    "R23": [(1, 241.30, 172.72, 0, None)],
    "R21": [(1, 254.00, 152.40, 0, None)],
    # U1C is the comparator's own supply pin and its decoupling, so it stands on
    # the bus rail at the top right rather than with the two comparator units.
    "U1": [
        (1, 279.40, 119.38, 0, None),
        (2, 279.40, 165.10, 0, None),
        (3, 330.20, 60.96, 0, None),
    ],
    # the hold and the button
    "R20": [(1, 266.70, 194.31, 270, None)],
    "R19": [(1, 279.40, 208.28, 0, None)],
    "C4": [(1, 292.10, 208.28, 0, None)],
    "R18": [(1, 309.88, 194.31, 270, None)],
    "D4": [(1, 337.82, 187.96, 0, None)],
    "D5": [(1, 337.82, 200.66, 0, None)],
    "D6": [(1, 337.82, 223.52, 180, None)],
    "D7": [(1, 337.82, 236.22, 180, None)],
    "R16": [(1, 360.68, 208.28, 0, None)],
    "R17": [(1, 353.06, 220.98, 0, None)],
    "J2": [(1, 386.08, 190.50, 0, None)],
    "J3": [(1, 386.08, 245.11, 0, None)],
}


# ---- how each net is drawn ----------------------------------------------------------
#
# "trunks" is a line and the pins that join it: ("h", y, [pins]) or
# ("v", x, [pins]). A pin standing on the line needs no stub; one pointing along
# it turns a corner first. "labels" are the pins that carry the net's name
# instead, which is every pin on a different block from its trunk, and every pin
# of a connector. "gnd" is a ground symbol at the pin.
#
# "name_at" moves a net's name off the middle of its trunk, where a few of them
# would otherwise land on a neighbour's value. It needs no guard of its own: a
# name placed off the wire does not name the net, and the netlist check below
# then reports the net as drawn correctly and called something else.
#
# An "extra" is a point that joins the trunk without being a pin -- the two
# PWR_FLAGs, which exist only to tell KiCad's ERC that the supply rails are fed
# from somewhere, since every part on this board is passive and the comparator's
# two supply pins are not.
NET_DRAW: dict[str, dict] = {
    "BATT": {"trunks": [("h", 45.72, ["P1.1", "F1.1"])]},
    "VSRC": {
        # Q6 AND Q7 BY LABEL, LIKE THEIR DRAINS AND GATES. Running the source
        # trunk down the column to reach them put it through Q2's gate and
        # shorted VSRC to G2 -- check_drawing() caught it, which is what that
        # check is for. Every pin of the two added devices is a label.
        "labels": ["C7.1", "R26.1", "Q6.3", "Q7.3"],
        "trunks": [
            ("v", 60.96, ["F1.2", "Q1.3", "Q2.3"]),
            ("h", 114.30, ["R2.1", "D1.1", "R8.1", "Q4.1"]),
        ],
    },
    "VBUS": {
        "trunks": [
            (
                "h",
                45.72,
                ["Q1.2", "Q2.2", "C5.1", "C6.1", "U1.8", "C2.1", "P2.1"],
                [(311.15, 38.10)],
            ),
            ("h", 76.20, ["R10.1", "R11.1", "R15.1"]),
        ],
        # Q6 AND Q7 TAKE A LABEL RATHER THAN THE TRUNK. The bus trunk runs along
        # y 45.72 past the top of the column, and a stub down to the third and
        # fourth device would cross both the devices above it.
        "labels": ["C1.2", "Q6.2", "Q7.2"],
    },
    "GATE": {
        "labels": ["C7.2", "R25.1"],
        "trunks": [
            ("h", 149.86, ["R2.2", "D1.2", "D8.1", "R3.1", "R4.1", "R5.1", "D2.1"])
        ],
    },
    "MILLER": {
        "labels": ["Q5.3"],
        "trunks": [("h", 138.43, ["C1.1", "D8.2"])],
    },
    "RESET_B": {"trunks": [("h", 228.60, ["R25.2", "Q5.2"])]},
    "RESET_C": {
        "trunks": [("v", 93.98, ["R26.2", "Q5.1"])],
        "name_at": (93.98, 217.17, 0),
    },
    # ONE RESISTOR FEEDS TWO GATES. electrical/power.py says why there is not one
    # per device: there is no room left on the board for two more resistors.
    "G1": {"labels": ["Q1.1", "Q6.1", "R3.2"]},
    "G2": {"labels": ["Q2.1", "Q7.1", "R4.2"]},
    "PULL": {
        "trunks": [("v", 129.54, ["R5.2", "Q3.1", "D3.1"])],
        "labels": ["D6.2"],
        "name_at": (129.54, 170.18, 180),
    },
    "FAST_B": {
        "trunks": [("v", 147.32, ["R8.2", "Q4.2", "R9.1", "D3.2"])],
    },
    "FAST_E": {
        "trunks": [("h", 171.45, ["Q4.3", "R9.2", "D2.2"])],
    },
    "EN": {
        "trunks": [("v", 297.18, ["U1.1", "U1.7", "R15.2"])],
        "labels": ["R6.1", "R14.1", "R21.1"],
    },
    "EN_B": {"trunks": [("h", 177.80, ["R6.2", "Q3.2", "R7.1"])]},
    "REF": {
        "trunks": [("v", 220.98, ["R10.2", "U2.1", "U2.3"])],
        "labels": ["U1.2", "R22.1"],
    },
    "UV_DIV": {"trunks": [("h", 106.68, ["R11.2", "R12.1", "C3.1", "R13.1"])]},
    "UV_IN": {"trunks": [("v", 266.70, ["R13.2", "R14.2", "U1.3"])]},
    "HOLD_REF": {
        "trunks": [("v", 241.30, ["R22.2", "R23.1", "U1.6"])],
        "name_at": (241.30, 162.56, 180),
    },
    "HOLD_IN": {
        "trunks": [("v", 259.08, ["R21.2", "U1.5"])],
        "labels": ["R20.2"],
        "name_at": (259.08, 160.66, 180),
    },
    "HOLD_MCU": {
        "trunks": [("v", 360.68, ["D4.2", "R16.1"])],
        "labels": ["J2.1"],
    },
    "HOLD_SBC": {
        "trunks": [("v", 353.06, ["D5.2", "R17.1"])],
        "labels": ["J2.4"],
    },
    "HOLD_OR": {"trunks": [("v", 325.12, ["D4.1", "D5.1", "R18.1"])]},
    "HOLD_CAP": {
        "trunks": [("h", 194.31, ["R18.2", "R20.1", "C4.1", "R19.1"])],
    },
    "BTN": {
        "trunks": [("v", 346.71, ["D6.1", "D7.1"])],
        "labels": ["J3.1"],
    },
    "SENSE": {"labels": ["D7.2", "J2.2"]},
    "GND": {
        "gnd": [
            "P3.1",
            "C5.2",
            "C6.2",
            "Q3.3",
            "R7.2",
            "U1.4",
            "C2.2",
            "U2.2",
            "R12.2",
            "C3.2",
            "R23.2",
            "R16.2",
            "R17.2",
            "C4.2",
            "R19.2",
        ],
        "labels": ["J2.3", "J3.2"],
        "flag": (342.90, 96.52),
    },
}


# ---- what a part is CALLED on the drawing -------------------------------------------
#
# power.py names a part by what to buy -- "100 kOhm 1 %, 0204 metal film" -- and
# that is the right name for a bill of materials and the wrong one for a
# drawing: printed beside fifty symbols it covers the wires. So the sheet shows
# the value and the sheet alone, and the full specification rides along in a
# hidden Spec property, where KiCad's bill-of-materials export still finds it.
#
# It is a table rather than a rule that chops the string, because a rule that is
# nearly right leaves one part mislabelled and nothing to catch it. Every
# specification power.py uses has to appear here or build() stops.
VALUE_ON_SHEET = {
    "WIMA MKS2C042201K00KSSD, 2.2 uF 63 V 10 %, 5 mm pitch": "2.2u 63V",
    "10 kOhm, 0204 metal film": "10k",
    "1 kOhm 1 W, PR01 axial": "1k 1W",
    "wire pad, 3.0 mm hole": "14 AWG pad",
    "wire pad, 1.15 mm hole": "22 AWG pad",
    "Keystone 3568 holder + mini (ATM) blade fuse, 20 A to start": "20 A ATM",
    "Infineon IRF4905PbF, P-channel 55 V, TO-220AB": "IRF4905",
    "470 uF 35 V low-ESR aluminium, 10 x 16 radial": "470u 35V",
    "22 uF 16 V solid tantalum, radial": "22u 16V",
    "10 uF 16 V solid tantalum, radial": "10u 16V",
    "220 nF 63 V metallised film, 5 mm pitch": "220n 63V",
    "100 nF 100 V ceramic disc, 2.5 mm pitch": "100n 100V",
    "BZX79-C15, 15 V 0.5 W zener, DO-35": "BZX79-C15",
    "1N4148, DO-35": "1N4148",
    "BAT46 Schottky 100 V, DO-35": "BAT46",
    "BC546B NPN 65 V, TO-92": "BC546B",
    "LM393P, DIP-8": "LM393P",
    "TL431ACLP, TO-92": "TL431ACLP",
    "JST-XH 2-pin": "JST-XH 2",
    "JST-XH 4-pin": "JST-XH 4",
    "10 Ohm, 0204 metal film": "10R",
    "1 kOhm, 0204 metal film": "1k",
    "15 kOhm, 0204 metal film": "15k",
    "14.7 kOhm 1 %, 0204 metal film": "14k7 1%",
    "22 kOhm, 0204 metal film": "22k",
    "47 kOhm, 0204 metal film": "47k",
    "100 kOhm, 0204 metal film": "100k",
    "100 kOhm 1 %, 0204 metal film": "100k 1%",
    "470 kOhm, 0204 metal film": "470k",
    "680 kOhm, 0204 metal film": "680k",
    "1 MOhm, 0204 metal film": "1M",
    "10 MOhm, 0204 metal film": "10M",
}

# How far above and below a symbol its reference and value sit. Taken from where
# the symbol's own pins are, which is right for a resistor and too tight for the
# few symbols drawn much bigger than their pin span.
TEXT_CLEARANCE = {
    "Comparator:LM393": 8.89,
    "Reference_Voltage:TL431LP": 5.08,
}


# WHERE EACH PART IS DOCUMENTED. A symbol carries its datasheet as a property, so
# double-clicking a part in KiCad opens the page it was designed from. The ones
# that have one are the ones this board was designed around; the rest are
# commodity parts named by their generic number, and a link to one vendor's copy
# of a 1N4148 data sheet would be a link, not a provenance.
DATASHEETS = {
    "Q5": "https://www.onsemi.com/pdf/datasheet/bc546-d.pdf",
    "C7": "https://wima.de/wp-content/uploads/media/e_WIMA_MKS_2.pdf",
    "R26": "https://www.vishay.com/docs/28729/pr010203.pdf",
    "D2": "https://www.vishay.com/docs/85662/bat46.pdf",
    "D8": "https://www.vishay.com/docs/85662/bat46.pdf",
    "Q1": "https://www.infineon.com/dgdl/irf4905pbf.pdf",
    "Q2": "https://www.infineon.com/dgdl/irf4905pbf.pdf",
    "Q6": "https://www.infineon.com/dgdl/irf4905pbf.pdf",
    "Q7": "https://www.infineon.com/dgdl/irf4905pbf.pdf",
    "U1": "https://www.ti.com/lit/ds/symlink/lm393.pdf",
    "U2": "https://www.ti.com/lit/ds/symlink/tl431.pdf",
    "F1": "https://www.keyelco.com/product-pdf.cfm?p=1160",
    "C5": "https://industrial.panasonic.com/cdbs/www-data/pdf/RDF0000/ABA0000C1053.pdf",
    "C6": "https://industrial.panasonic.com/cdbs/www-data/pdf/RDF0000/ABA0000C1053.pdf",
}


def _uuid(seed: str) -> str:
    """A stable uuid, so that rewriting the file does not churn every id."""
    return str(uuidlib.uuid5(uuidlib.NAMESPACE_URL, f"power-sch/{seed}"))


ROOT_UUID = _uuid("sheet/root")


def footprint_of(refdes: str) -> str:
    """The KiCad library footprint the board puts this part in."""
    library, name, _ = power_pcb.FOOTPRINT_OF[refdes]
    return f"{library}:{name}"


# ---- where every pin lands ----------------------------------------------------------


def pin_geometry() -> tuple[dict[str, tuple[float, float]], dict[str, tuple[int, int]]]:
    """Every pin's place on the sheet, and which way it points, by "R1.2"."""
    where: dict[str, tuple[float, float]] = {}
    facing: dict[str, tuple[int, int]] = {}
    for refdes, instances in PLACEMENT.items():
        library = ksym.pins(SYMBOL_OF[refdes])
        for unit, x, y, angle, mirror in instances:
            for number, pin in library.items():
                if pin.unit != unit:
                    continue
                key = f"{refdes}.{number}"
                where[key] = ksym.place(pin, (x, y), angle, mirror)
                facing[key] = ksym.outward(pin, (x, y), angle, mirror)
    return where, facing


def check_placement(where: dict[str, tuple[float, float]]) -> list[str]:
    """Every pin drawn once, on the connection grid, and none on top of another."""
    faults: list[str] = []
    declared = {f"{part.refdes}.{pin}" for part in power.PARTS for pin in part.pins}
    drawn = set(where)
    for missing in sorted(declared - drawn):
        faults.append(f"{missing} is in the netlist and not on the sheet")
    for extra in sorted(drawn - declared):
        faults.append(f"{extra} is on the sheet and not in the netlist")
    for part in power.PARTS:
        if part.partNumber not in VALUE_ON_SHEET:
            faults.append(f"{part.refdes}: no short value for {part.partNumber!r}")
    seen: dict[tuple[float, float], str] = {}
    for key, (x, y) in sorted(where.items()):
        if (
            abs(round(x / GRID) * GRID - x) > 1e-6
            or abs(round(y / GRID) * GRID - y) > 1e-6
        ):
            faults.append(f"{key} at {x:.3f},{y:.3f} is off the 1.27 mm grid")
        if (x, y) in seen:
            faults.append(f"{key} sits exactly on {seen[(x, y)]} at {x:.2f},{y:.2f}")
        seen[(x, y)] = key
    return faults


# ---- drawing --------------------------------------------------------------------


class Sheet:
    """Collects wires, junctions, labels and symbols, and writes them out."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.segments: list[tuple[str, tuple[float, float], tuple[float, float]]] = []
        self.serial = 0

    def wire(self, net: str, a: tuple[float, float], b: tuple[float, float]) -> None:
        if a == b:
            return
        self.serial += 1
        self.segments.append((net, a, b))
        self.lines.append(
            f"  (wire (pts (xy {a[0]:.2f} {a[1]:.2f}) (xy {b[0]:.2f} {b[1]:.2f}))"
            " (stroke (width 0) (type default))"
            f' (uuid "{_uuid(f"wire/{net}/{self.serial}")}"))'
        )

    def label(self, net: str, at: tuple[float, float], angle: float) -> None:
        justify = "left" if angle in (0, 90) else "right"
        self.lines.append(
            f'  (label "{net}" (at {at[0]:.2f} {at[1]:.2f} {angle:g})'
            f" (effects (font (size 1.27 1.27)) (justify {justify} bottom))"
            f' (uuid "{_uuid(f"label/{net}/{at[0]}/{at[1]}")}"))'
        )

    def junction(self, at: tuple[float, float]) -> None:
        self.lines.append(
            f"  (junction (at {at[0]:.2f} {at[1]:.2f}) (diameter 0) (color 0 0 0 0)"
            f' (uuid "{_uuid(f"junction/{at[0]}/{at[1]}")}"))'
        )

    def junctions(self) -> None:
        """A dot wherever three wire ends meet, or a wire end lands mid-wire.

        Worked out from the segments rather than declared, because a junction
        that should be there and is not is a net silently split in two, and the
        netlist check would find it but not say where.
        """
        ends: dict[tuple[float, float], int] = {}
        for _, a, b in self.segments:
            ends[a] = ends.get(a, 0) + 1
            ends[b] = ends.get(b, 0) + 1
        for point, count in sorted(ends.items()):
            total = count
            for _, a, b in self.segments:
                if point in (a, b):
                    continue
                if a[0] == b[0] == point[0] and min(a[1], b[1]) < point[1] < max(
                    a[1], b[1]
                ):
                    total += 2
                elif a[1] == b[1] == point[1] and min(a[0], b[0]) < point[0] < max(
                    a[0], b[0]
                ):
                    total += 2
            if total >= 3:
                self.junction(point)


def stub(
    sheet: Sheet,
    net: str,
    start: tuple[float, float],
    facing: tuple[int, int],
    axis: str,
    line: float,
) -> tuple[float, float]:
    """Run a pin onto its trunk, turning a corner first if it points along it.

    Returns where it met the trunk, which is what the junction pass needs.
    """
    x, y = start
    if axis == "v":
        if x == line:
            return start
        if facing[0] == 0:
            # The pin points along the trunk: come out of it, then turn.
            y = y + facing[1] * RISE
            sheet.wire(net, start, (x, y))
        sheet.wire(net, (x, y), (line, y))
        return (line, y)
    if y == line:
        return start
    if facing[1] == 0:
        x = x + facing[0] * RISE
        sheet.wire(net, start, (x, y))
    sheet.wire(net, (x, y), (x, line))
    return (x, line)


def draw_nets(sheet: Sheet, where, facing) -> None:
    for net, plan in NET_DRAW.items():
        for trunk in plan.get("trunks", []):
            axis, line, members = trunk[0], trunk[1], trunk[2]
            extras = trunk[3] if len(trunk) > 3 else []
            touches = [
                stub(sheet, net, where[m], facing[m], axis, line) for m in members
            ]
            for point in extras:
                meets = (line, point[1]) if axis == "v" else (point[0], line)
                sheet.wire(net, point, meets)
                touches.append(meets)
            # THE TRUNK IS DRAWN IN SEGMENTS, one between each pair of touches,
            # so that every pin standing on it is a wire END. KiCad does not
            # join a pin that merely lies part way along a wire, which is one
            # net silently split in two and nothing on the drawing to show it.
            along = sorted({p[1] if axis == "v" else p[0] for p in touches})
            for start, end in zip(along, along[1:]):
                a = (line, start) if axis == "v" else (start, line)
                b = (line, end) if axis == "v" else (end, line)
                sheet.wire(net, a, b)
            # And its name, a little in from one end so it is certainly ON it.
            inset = (
                (along[0] + along[-1]) / 2
                if axis == "v"
                else min(along[0] + 2.54, (along[0] + along[-1]) / 2)
            )
            spot = (line, inset) if axis == "v" else (inset, line)
            turn = 90 if axis == "v" else 0
            if "name_at" in plan:
                spot, turn = (
                    (plan["name_at"][0], plan["name_at"][1]),
                    plan["name_at"][2],
                )
            sheet.label(net, spot, turn)
        for member in plan.get("labels", []):
            at, dx_dy = where[member], facing[member]
            end = (at[0] + dx_dy[0] * STUB, at[1] + dx_dy[1] * STUB)
            sheet.wire(net, at, end)
            angle = (
                0
                if dx_dy[0] > 0
                else 180
                if dx_dy[0] < 0
                else 270
                if dx_dy[1] > 0
                else 90
            )
            sheet.label(net, end, angle)
        for member in plan.get("gnd", []):
            at, dx_dy = where[member], facing[member]
            foot = at
            if dx_dy[1] <= 0:
                # Not pointing down the sheet: step out, then drop to the symbol.
                foot = (at[0] + dx_dy[0] * STUB, at[1] + dx_dy[1] * STUB)
                sheet.wire(net, at, foot)
            end = (foot[0], foot[1] + (0.0 if dx_dy[1] > 0 else STUB))
            sheet.wire(net, foot, end)
            sheet.lines.extend(symbol_instance("#PWR", "power:GND", "GND", end, 1))
        if "flag" in plan:
            flag = plan["flag"]
            sheet.lines.extend(
                symbol_instance("#FLG", "power:PWR_FLAG", "PWR_FLAG", flag, 1)
            )
            sheet.wire(net, flag, (flag[0], flag[1] + STUB))
            sheet.lines.extend(
                symbol_instance(
                    "#PWR", "power:GND", "GND", (flag[0], flag[1] + STUB), 1
                )
            )
    # The bus rail's flag, wired onto the trunk by the "extras" above.
    sheet.lines.extend(
        symbol_instance("#FLG", "power:PWR_FLAG", "PWR_FLAG", (311.15, 38.10), 1)
    )


_ANON = {"count": 0}


def symbol_instance(
    prefix: str, lib_id: str, value: str, at: tuple[float, float], unit: int
) -> list[str]:
    """A power symbol or flag: no footprint, no bill entry, its own reference."""
    _ANON["count"] += 1
    refdes = f"{prefix}{_ANON['count']:02d}"
    seed = f"{refdes}/{at[0]}/{at[1]}"
    return [
        f'  (symbol (lib_id "{lib_id}") (at {at[0]:.2f} {at[1]:.2f} 0) (unit {unit})',
        "    (in_bom no) (on_board no) (dnp no)",
        f'    (uuid "{_uuid("sym/" + seed)}")',
        f'    (property "Reference" "{refdes}" (at {at[0]:.2f} {at[1]:.2f} 0)'
        " (effects (font (size 1.27 1.27)) hide))",
        f'    (property "Value" "{value}" (at {at[0]:.2f} {at[1] + 3.81:.2f} 0)'
        " (effects (font (size 1.27 1.27)) hide))",
        f'    (pin "1" (uuid "{_uuid("pin/" + seed)}"))',
        '    (instances (project "power"',
        f'      (path "/{ROOT_UUID}" (reference "{refdes}") (unit {unit}))',
        "    ))",
        "  )",
    ]


def placed_part(part: power.Part, where, facing) -> list[str]:
    """One netlist part on the sheet, once per unit its symbol draws."""
    lib_id = SYMBOL_OF[part.refdes]
    description = part.description.replace('"', "'")
    out: list[str] = []
    for unit, x, y, angle, mirror in PLACEMENT[part.refdes]:
        mirrored = f" (mirror {mirror})" if mirror else ""
        seed = f"{part.refdes}/{unit}"
        mine = [
            f"{part.refdes}.{number}"
            for number, pin in ksym.pins(lib_id).items()
            if pin.unit == unit
        ]
        rows = [where[key][1] for key in mine]
        clear = TEXT_CLEARANCE.get(lib_id, 0.0)
        above = min(min(rows) - y, -clear) - 2.54 + y
        below = max(max(rows) - y, clear) + 2.54 + y
        # A part whose pins all point down the sheet -- a connector standing over
        # what it feeds -- has wires under it and nothing over it, so both its
        # name and its value go above rather than into the wiring.
        if all(facing[key] == (0, 1) for key in mine):
            above, below = above - 3.81, above
        # KICAD ROTATES A FIELD WITH ITS SYMBOL, so a horizontal fuse or a
        # sideways shunt would print its value up the page. The angle stored
        # here is the one that cancels that back to level.
        #
        # A HALF TURN IS THE EXCEPTION, and it is worth knowing before drawing
        # anything upside down: KiCad keeps a 180-rotated symbol's fields the
        # right way up on its own, by swapping their justification rather than
        # turning them. Cancelling it with another 180 is therefore what prints
        # the value upside down -- checked against kicad-cli's own plot.
        spin = 0 if angle % 180 == 0 else int((360 - angle) % 360)
        out += [
            f'  (symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} {angle:g}){mirrored}'
            f" (unit {unit})",
            "    (in_bom yes) (on_board yes) (dnp no)",
            f'    (uuid "{_uuid("sym/" + seed)}")',
            f'    (property "Reference" "{part.refdes}"'
            f" (at {x:.2f} {above:.2f} {spin}) {FONT})",
            f'    (property "Value" "{VALUE_ON_SHEET[part.partNumber]}"'
            f" (at {x:.2f} {below:.2f} {spin}) {FONT})",
            f'    (property "Footprint" "{footprint_of(part.refdes)}"'
            f" (at {x:.2f} {y:.2f} 0)"
            " (effects (font (size 1.27 1.27)) hide))",
            f'    (property "Datasheet" "{DATASHEETS.get(part.refdes, "")}"'
            f" (at {x:.2f} {y:.2f} 0) (effects (font (size 1.27 1.27)) hide))",
            f'    (property "Description" "{description}"'
            f" (at {x:.2f} {y:.2f} 0) (effects (font (size 1.27 1.27)) hide))",
            f'    (property "Spec" "{part.partNumber}"'
            f" (at {x:.2f} {y:.2f} 0) (effects (font (size 1.27 1.27)) hide))",
        ]
        for number, pin in ksym.pins(lib_id).items():
            if pin.unit == unit:
                out.append(
                    f'    (pin "{number}"'
                    f' (uuid "{_uuid(f"pin/{part.refdes}/{number}")}"))'
                )
        out += [
            '    (instances (project "power"',
            f'      (path "/{ROOT_UUID}" (reference "{part.refdes}") (unit {unit}))',
            "    ))",
            "  )",
        ]
    return out


def build() -> str:
    where, facing = pin_geometry()
    faults = check_placement(where)
    if faults:
        for fault in faults:
            print(f"  FAULT  {fault}")
        raise SystemExit("the sheet's placement does not match the netlist")
    _, lines = power.check_arithmetic()
    body = [
        "(kicad_sch",
        "  (version 20230121)",
        '  (generator "power_sch.py")',
        f'  (uuid "{ROOT_UUID}")',
        '  (paper "A3")',
        "  (title_block",
        '    (title "Biped power switch board")',
        f'    (date "{date.today().isoformat()}")',
        '    (company "generated by electrical/power_sch.py -- do not edit")',
        '    (comment 1 "Netlist: electrical/power.py. Board: electrical/'
        'power_pcb.py.")',
        '    (comment 2 "Blocks: power path, gate drive, reference and '
        'comparators, hold and button.")',
    ]
    for number, line in enumerate(lines[:6], start=3):
        body.append(f'    (comment {number} "{" ".join(line.split())}")')
    body += ["  )", "  (lib_symbols"]
    for lib_id in sorted({*SYMBOL_OF.values(), "power:GND", "power:PWR_FLAG"}):
        body.append("\t" + ksym.symbol(lib_id))
    body.append("  )")
    sheet = Sheet()
    draw_nets(sheet, where, facing)
    sheet.junctions()
    body += sheet.lines
    for part in power.PARTS:
        body += placed_part(part, where, facing)
    body += ['  (sheet_instances (path "/" (page "1")))', ")"]
    return "\n".join(body) + "\n"


# ---- what checks it ---------------------------------------------------------------


def exported_netlist(path: Path) -> dict[str, set[tuple[str, str]]]:
    """The nets KiCad itself reads off the drawing."""
    import re
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as scratch:
        out = Path(scratch) / "power.net"
        subprocess.run(
            [
                str(power_pcb.kicad_cli()),
                "sch",
                "export",
                "netlist",
                "--format",
                "kicadsexpr",
                "-o",
                str(out),
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        if not out.exists():
            raise SystemExit("kicad-cli wrote no netlist")
        text = out.read_text(encoding="utf-8")
    nets: dict[str, set[tuple[str, str]]] = {}
    for block in re.finditer(
        r'\(net\s*\n\s*\(code "\d+"\)\s*\n\s*\(name "([^"]+)"\)(.*?)\n\t\t\)',
        text,
        re.S,
    ):
        members = {
            (ref, pin)
            for ref, pin in re.findall(
                r'\(ref "([^"]+)"\)\s*\n\s*\(pin "([^"]+)"\)', block.group(2)
            )
            if not ref.startswith("#")
        }
        if members:
            nets[block.group(1).lstrip("/")] = members
    return nets


def check_drawing(path: Path) -> list[str]:
    """Does the drawing carry the netlist, pin for pin, as KiCad reads it?

    This is the check the whole file exists to pass. A wire that misses a pin,
    two nets that touch, a junction left out where three wires meet -- none of
    them is visible in a rendering and all of them come out here.
    """
    drawn = exported_netlist(path)
    wanted = {
        net: {tuple(e) for e in endpoints} for net, endpoints in power.NETS.items()
    }
    faults: list[str] = []
    by_members = {frozenset(members): name for name, members in drawn.items()}
    for net, endpoints in sorted(wanted.items()):
        key = frozenset(endpoints)
        if key in by_members:
            if by_members[key] != net:
                faults.append(
                    f"{net} is drawn correctly but KiCad calls it "
                    f"{by_members[key]} -- a label is missing or misspelt"
                )
            continue
        near = max(drawn.items(), key=lambda kv: len(kv[1] & endpoints))
        missing = sorted(f"{r}.{p}" for r, p in endpoints - near[1])
        spare = sorted(f"{r}.{p}" for r, p in near[1] - endpoints)
        faults.append(
            f"{net}: drawn as {near[0]}"
            + (f", missing {', '.join(missing)}" if missing else "")
            + (f", wrongly joined to {', '.join(spare)}" if spare else "")
        )
    extra = set(drawn) - set(wanted)
    for name in sorted(extra):
        if frozenset(drawn[name]) not in {frozenset(v) for v in wanted.values()}:
            members = ", ".join(sorted(f"{r}.{p}" for r, p in drawn[name]))
            faults.append(f"{name} is on the drawing and not in the netlist: {members}")
    return faults


def erc(path: Path) -> list[str]:
    """KiCad's own electrical rule check on the sheet this file just wrote."""
    import json
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as scratch:
        report = Path(scratch) / "erc.json"
        subprocess.run(
            [
                str(power_pcb.kicad_cli()),
                "sch",
                "erc",
                "--format",
                "json",
                "--severity-all",
                "--units",
                "mm",
                "-o",
                str(report),
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        if not report.exists():
            return ["kicad-cli wrote no ERC report"]
        result = json.loads(report.read_text(encoding="utf-8"))
    out = []
    for sheet in result.get("sheets", []):
        for violation in sheet.get("violations", []):
            out.append(
                f"{violation.get('severity')} {violation.get('type')}: "
                f"{violation.get('description')}"
            )
    return out


def main() -> int:
    faults = power.check()
    if faults:
        print("power netlist: FAILED, not drawing a schematic of a broken netlist")
        for fault in faults:
            print(f"  {fault}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "power.kicad_sch"
    path.write_text(build(), encoding="utf-8")
    pins = sum(len(p.pins) for p in power.PARTS)
    units = sum(len(v) for v in PLACEMENT.values())
    print(f"wrote {path.relative_to(ROOT)}")
    print(
        f"  {len(power.PARTS)} parts in {units} symbols, {pins} pins, "
        f"{len(power.NETS)} nets"
    )
    wrong = check_drawing(path)
    if wrong:
        print(f"  the drawing does NOT carry the netlist: {len(wrong)} nets wrong")
        for fault in wrong[:20]:
            print(f"  FAULT  {fault}")
        return 1
    print("  every net on the drawing is the net power.py declares")
    violations = erc(path)
    if violations:
        print(f"  KiCad ERC: {len(violations)} violations")
        for violation in violations[:15]:
            print(f"  FAULT  {violation}")
        return 1
    print("  KiCad ERC: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
