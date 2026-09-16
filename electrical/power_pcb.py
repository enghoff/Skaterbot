# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9", "numpy>=1.26", "matplotlib>=3.8", "shapely>=2.0"]
# ///
"""The power switch board as a printed circuit board, laid out and checked.

electrical/power.py says what is soldered to what. This file says where, and on
which copper, and then hands the result to KiCad to build and to check:

    uv run electrical/power_pcb.py            # lay it out, build it, DRC it
    uv run electrical/power_pcb.py --draw     # also rewrite electrical/power_pcb.png
    uv run electrical/power_pcb.py --no-cad   # skip the clash check against the torso

HOW THIS DIFFERS FROM THE CARRIER, and why. The carrier is through-hole and every
pad on it is drawn here in Python; this board is a power board, and most of its
area is copper carrying 24 A rather than tracks carrying signals. So:

  * Most footprints come from KiCad. R1 uses the checked-in power library:
    Isabellenhuette PBV-F1, drawn from manufacturer drawing Z-DW-132b.
  * THE HIGH-CURRENT NETS ARE ZONES ON BOTH LAYERS, not tracks. The signals are
    searched for on a grid the way the carrier's are, and kept out of those zones
    so that no track can cut a power path in two.
  * THE BOARD IS BUILT BY KICAD ITSELF. electrical/power_kicad.py runs inside
    KiCad's own Python, places the library footprints, lays the copper this file
    found, fills the zones and saves the board; then kicad-cli runs its design
    rule check on the result. Every short, open and clearance is KiCad's finding
    on the filled board, not a claim made here.

WHAT IS STILL CHECKED HERE: that every pad this file places is where KiCad put
it -- the two disagree about nothing or the build fails -- that no two parts'
courtyards overlap, that nothing stands on a screw's washer, and that every part
clears every drawn thing in the torso, measured in the CAD's own frame.

The board is 2-layer, 1.6 mm FR-4, and it wants 2 oz copper: the zones are sized
for that, and at 1 oz the switch's copper would run hot at the peak current.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "electrical"))

import power  # noqa: E402

from cad import electronics as e  # noqa: E402

OUT = ROOT / "electrical" / "kicad_power"
BOARD_FILE = OUT / "power.kicad_pcb"
PNG = ROOT / "electrical" / "power_pcb.png"


# ---- where KiCad is ------------------------------------------------------------


def kicad_root() -> Path:
    """The KiCad 10 installation: $KICAD_ROOT, then kicad-cli on PATH, then the default."""
    if os.environ.get("KICAD_ROOT"):
        return Path(os.environ["KICAD_ROOT"])
    cli = shutil.which("kicad-cli")
    if cli:
        return Path(cli).resolve().parent.parent
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), "/usr"):
        candidate = Path(base) / "KiCad" / "10.0"
        if candidate.exists():
            return candidate
    raise RuntimeError("KiCad 10 was not found; set KICAD_ROOT")


def kicad_share() -> Path:
    return kicad_root() / "share" / "kicad"


def kicad_python() -> Path:
    return kicad_root() / "bin" / ("python.exe" if os.name == "nt" else "python3")


def kicad_cli() -> Path:
    return kicad_root() / "bin" / ("kicad-cli.exe" if os.name == "nt" else "kicad-cli")


# ---- reading KiCad's footprints ---------------------------------------------------


def parse_sexpr(text: str):
    """A KiCad S-expression as nested lists of strings."""
    tokens: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "()":
            tokens.append(c)
            i += 1
        elif c.isspace():
            i += 1
        elif c == '"':
            j = i + 1
            out = []
            while text[j] != '"':
                if text[j] == "\\":
                    j += 1
                out.append(text[j])
                j += 1
            tokens.append('"' + "".join(out))
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()":
                j += 1
            tokens.append(text[i:j])
            i = j
    stack: list[list] = [[]]
    for token in tokens:
        if token == "(":
            stack.append([])
        elif token == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(token[1:] if token.startswith('"') else token)
    return stack[0][0]


def _children(node, name: str) -> list:
    return [child for child in node if isinstance(child, list) and child[0] == name]


def _child(node, name: str):
    found = _children(node, name)
    return found[0] if found else None


@dataclass(frozen=True)
class Pad:
    """One pad, in its footprint's own KiCad frame (y down)."""

    name: str
    kind: str  # smd, thru_hole, np_thru_hole
    x: float
    y: float
    w: float
    h: float
    rotation: float
    drill: float
    layers: frozenset

    def copper(self) -> set[str]:
        if "*.Cu" in self.layers:
            return {"F.Cu", "B.Cu"}
        return {layer for layer in self.layers if layer.endswith(".Cu")}


@dataclass(frozen=True)
class Footprint:
    library: str
    name: str
    pads: tuple[Pad, ...]
    courtyard: tuple[float, float, float, float]  # x0 y0 x1 y1, KiCad frame
    height: float  # above the board's top face, with what plugs into it


def footprint_library(library: str) -> Path:
    if library == "power":
        return ROOT / "electrical" / "kicad_power" / "power.pretty"
    return kicad_share() / "footprints" / f"{library}.pretty"


def load_footprint(library: str, name: str, height: float) -> Footprint:
    path = footprint_library(library) / f"{name}.kicad_mod"
    tree = parse_sexpr(path.read_text(encoding="utf-8"))
    pads = []
    for node in _children(tree, "pad"):
        at = _child(node, "at")
        size = _child(node, "size")
        drill = _child(node, "drill")
        layers = _child(node, "layers")
        pads.append(
            Pad(
                name=node[1],
                kind=node[2],
                x=float(at[1]),
                y=float(at[2]),
                w=float(size[1]),
                h=float(size[2]),
                rotation=float(at[3]) if len(at) > 3 else 0.0,
                drill=float(drill[1]) if drill else 0.0,
                layers=frozenset(layers[1:]),
            )
        )
    xs: list[float] = []
    ys: list[float] = []
    for kind in ("fp_line", "fp_rect", "fp_circle", "fp_arc", "fp_poly"):
        for node in _children(tree, kind):
            layer = _child(node, "layer")
            if not layer or layer[1] != "F.CrtYd":
                continue
            # A CIRCLE IS ITS CENTRE AND ONE POINT ON IT, and taking those two as
            # the extent is how a round courtyard came out flat: a radial
            # capacitor's whole outline is one fp_circle, and read that way a 6 mm
            # can measured 0 mm deep and every part beside it was let in on top
            # of it. So a circle is expanded to the box that holds it.
            centre = _child(node, "center")
            edge = _child(node, "end")
            if kind == "fp_circle" and centre and edge:
                cx, cy = float(centre[1]), float(centre[2])
                radius = math.hypot(float(edge[1]) - cx, float(edge[2]) - cy)
                xs += [cx - radius, cx + radius]
                ys += [cy - radius, cy + radius]
                continue
            for key in ("start", "mid", "end", "center"):
                point = _child(node, key)
                if point:
                    xs.append(float(point[1]))
                    ys.append(float(point[2]))
            points = _child(node, "pts")
            if points:
                for xy in _children(points, "xy"):
                    xs.append(float(xy[1]))
                    ys.append(float(xy[2]))
    if not xs:
        raise ValueError(f"{library}:{name} has no courtyard")
    return Footprint(
        library, name, tuple(pads), (min(xs), min(ys), max(xs), max(ys)), height
    )


# WHAT EACH PART IS, AS A KICAD LIBRARY FOOTPRINT, AND HOW TALL IT STANDS. The
# heights are what gate the part against the deck over it. Three are measured off
# KiCad's own 3D model of the part (TO-220 18.77, the fuse holder 7.37); the mini
# blade fuse adds its catalogue body over the holder; a JST-XH is the carrier's
# figure with its plug and 3 mm for the wires to leave; the wire pads reserve a
# column for a 14 AWG lead to stand up out of the board before it bends.
#
# NOT ONE PART ON THIS BOARD IS SURFACE MOUNT, September 2026, and every one of
# them was until this pass. It is a board a person can build with an iron: the
# resistors and the diodes STAND ON END on a 2.54 mm pitch, which is the one
# choice here that is not the obvious one and is what makes the rest fit. An 0204
# resistor upright occupies 9.5 mm2 of board against a 1206's 10.3, so the passive
# rows did not have to grow at all; laid down on a 7.62 mm pitch they would each
# have taken 29 and there would have been no board left. What did grow is the
# comparator (a DIP-8 is 104 mm2 against a SOIC-8's 40), the reference and the two
# small transistors (TO-92, 26 against a SOT-23's 13), the four small capacitors
# -- and the shunt, which is the whole story.
#
# The original axial shunt placeholder did not exist at 1 mOhm. R1 now uses
# the PBV-F1: four inline through-hole pins, 17.78 mm current-pin span, and
# a 22.5 x 4.45 mm body. Its 20.7 mm installed height clears the deck by 1.1 mm.
# The board keeps the bought distribution board's own 50 x 50 footprint, which it became
# when the capacitor bank stopped reserving four cans for the two it buys.
#
# THE HEIGHTS OF THE UPRIGHT PARTS ARE NOT SPARE HEADROOM. The pack's own XT60s
# hang over the inboard column of this board with 7.4 mm to spare, so a 9 mm can
# there would foul them. check_against_cad() measures that against the drawn
# torso rather than trusting this note.
THT_RESISTOR = ("Resistor_THT", "R_Axial_DIN0204_L3.6mm_D1.6mm_P2.54mm_Vertical", 5.5)
THT_DIODE = ("Diode_THT", "D_DO-35_SOD27_P2.54mm_Vertical_AnodeUp", 5.5)
FOOTPRINT_OF = {
    "P1": ("Connector_Wire", "SolderWire-2.5sqmm_1x01_D2.4mm_OD4.4mm", 12.0),
    "P2": ("Connector_Wire", "SolderWire-2.5sqmm_1x01_D2.4mm_OD4.4mm", 12.0),
    "P3": ("Connector_Wire", "SolderWire-0.5sqmm_1x01_D0.9mm_OD2.3mm", 6.0),
    "F1": ("Fuse", "Fuseholder_Blade_Mini_Keystone_3568", 7.37 + 9.0),
    "Q1": ("Package_TO_SOT_THT", "TO-220-3_Vertical", 18.77),
    "Q2": ("Package_TO_SOT_THT", "TO-220-3_Vertical", 18.77),
    "R1": ("power", "R_Shunt_Isabellenhuette_PBV_F1", 20.7),
    "U1": ("Package_DIP", "DIP-8_W7.62mm", 5.0),
    # The staggered TO-92 and not the inline one: inline stands three 1.1 mm pads
    # on a 1.27 mm pitch, which leaves 0.17 mm of gap where this board's rules
    # want 0.2. Staggered means bending the middle lead, which is how a TO-92
    # goes into a 2.54 mm grid anyway.
    "U2": ("Package_TO_SOT_THT", "TO-92", 6.5),
    "Q3": ("Package_TO_SOT_THT", "TO-92", 6.5),
    "Q4": ("Package_TO_SOT_THT", "TO-92", 6.5),
    "C1": ("Capacitor_THT", "C_Rect_L7.0mm_W2.5mm_P5.00mm", 8.0),
    "C2": ("Capacitor_THT", "C_Disc_D5.0mm_W2.5mm_P2.50mm", 7.0),
    "C3": ("Capacitor_THT", "CP_Radial_Tantal_D6.0mm_P2.50mm", 9.0),
    "C4": ("Capacitor_THT", "CP_Radial_Tantal_D5.0mm_P2.50mm", 8.0),
    # The bank: the two cans docs/BOM.md buys, on the bus copper they damp.
    "C5": ("Capacitor_THT", "CP_Radial_D10.0mm_P5.00mm", e.capacitorHeight),
    "C6": ("Capacitor_THT", "CP_Radial_D10.0mm_P5.00mm", e.capacitorHeight),
    "J1": ("Connector_JST", "JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical", 12.8),
    "J2": ("Connector_JST", "JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical", 12.8),
    "J3": ("Connector_JST", "JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical", 12.8),
}
for _part in power.PARTS:
    if _part.refdes in FOOTPRINT_OF:
        continue
    if _part.refdes[0] == "D":
        FOOTPRINT_OF[_part.refdes] = THT_DIODE
    elif _part.refdes[0] == "R":
        FOOTPRINT_OF[_part.refdes] = THT_RESISTOR


# ---- the board frame --------------------------------------------------------------
#
# Everything below is in the TORSO's x and y, so a station here and a station in
# cad/electronics.py are the same number. KiCad wants its own frame -- y down,
# origin at the page corner -- and place() is the only thing that knows it.

OUTLINE = e.power_switch_outline()
X_MIN = min(x for x, _ in OUTLINE)
X_MAX = max(x for x, _ in OUTLINE)
Y_MIN = min(y for _, y in OUTLINE)
Y_MAX = max(y for _, y in OUTLINE)
TOP_Z = e.powerSwitchBoardZ + e.pcbThickness
SCREWS = e.power_switch_screw_xy()
PAGE_X = 25.0
PAGE_Y = 25.0


def place(x: float, y: float) -> tuple[float, float]:
    """A torso point, in KiCad's frame."""
    return (round(PAGE_X + x - X_MIN, 4), round(PAGE_Y + Y_MAX - y, 4))


def unplace(kx: float, ky: float) -> tuple[float, float]:
    return (kx - PAGE_X + X_MIN, Y_MAX - (ky - PAGE_Y))


def inside_outline(x: float, y: float, margin: float = 0.0) -> bool:
    """Whether a point is on the board, at least `margin` in from every edge."""
    return (X_MIN + margin <= x <= X_MAX - margin) and (
        Y_MIN + margin <= y <= Y_MAX - margin
    )


@dataclass
class Report:
    faults: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ---- design rules ----------------------------------------------------------------
#
# Chosen inside what a hobby board house builds in 2 oz copper as standard -- 0.2
# mm track and gap is the usual floor at that weight -- with the margin that
# makes hand soldering forgiving.

TRACK = 0.25
BRANCH = 0.4  # a power or ground net where it leaves its zone for a small part
CLEARANCE = 0.2
EDGE_CLEARANCE = 0.4
VIA_PAD = 0.8
VIA_DRILL = 0.4
HOLE_TO_HOLE = 0.25
# Round an M3 screw: its head and washer on top, the Ø6 spacer underneath.
SCREW_BODY_KEEPOUT = 4.0
SCREW_COPPER_KEEPOUT = 3.6
SCREW_HOLE = e.m3Clearance
ZONE_CLEARANCE = 0.3
ZONE_MIN_WIDTH = 0.25

# HOW LONG A TRIMMED LEAD IS under the board, and the one place on this board
# where that costs something. The bought distribution board's own XT60 input
# socket stands to within half a millimetre of this board's underside, so a part
# with a drilled pad over that socket lands its leads inside it. Nothing with a
# drill goes over this rectangle -- it is a keepout rather than a clearance, and
# it is the price through-hole pays that surface mount did not. The rectangle
# comes from cad/electronics.py, which draws the socket, rather than being typed
# again here.
TAIL = 2.0
TAIL_CLEARANCE = 0.5
SOCKET = e.bus_input_socket_box()
SOCKET_FOULS_TAILS = e.bus_input_socket_top() > (e.powerSwitchBoardZ - TAIL)


# ---- placement ---------------------------------------------------------------------


@dataclass(frozen=True)
class Placed:
    refdes: str
    footprint: Footprint
    x: float
    y: float
    rotation: int = 0  # KiCad's, degrees anticlockwise as seen from above

    def local(self, px: float, py: float) -> tuple[float, float]:
        """A point in the footprint's KiCad frame, in torso x and y."""
        angle = math.radians(self.rotation)
        # KiCad rotates anticlockwise on screen, where y points down.
        kx = px * math.cos(angle) + py * math.sin(angle)
        ky = -px * math.sin(angle) + py * math.cos(angle)
        return (self.x + kx, self.y - ky)

    def pads(self) -> list[tuple[Pad, float, float, float, float]]:
        """(pad, x, y, w, h) in the torso frame, sizes swapped for a quarter turn."""
        out = []
        for pad in self.footprint.pads:
            x, y = self.local(pad.x, pad.y)
            quarter = round((self.rotation + pad.rotation) / 90) % 2
            w, h = (pad.h, pad.w) if quarter else (pad.w, pad.h)
            out.append((pad, x, y, w, h))
        return out

    def box(self, x0: float, y0: float, x1: float, y1: float):
        corners = [self.local(x, y) for x in (x0, x1) for y in (y0, y1)]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        return (min(xs), min(ys), max(xs), max(ys))

    def courtyard(self) -> tuple[float, float, float, float]:
        return self.box(*self.footprint.courtyard)


# THE TALL PARTS STAND WHERE cad/electronics.py PUTS THEM, because the torso is
# what decides where they can go and the CAD draws them there; the rest of the
# circuit is placed here, around them. A target, not a station: legalize() moves
# each small part the least distance that clears everything already down.
TARGETS: dict[str, tuple[float, float, int]] = {
    **e.powerSwitchStations,
    # WHERE THE SMALL PARTS GO, and WHAT DECIDES IT is worth stating, because the
    # first attempt at this layout placed every part legally and then could not be
    # routed at all. The board's clear space is four separate islands -- the
    # shunt, the bank, the fuse and the two switches take the middle of it -- and
    # the circuit is three clusters. Put a cluster across two islands and its own
    # nets have to cross the board to find each other; that is what failed. So
    # each cluster gets one island:
    #
    #   THE GATE BAND, between the fuse and the switches, and THE INBOARD POCKET
    #   forward of the bought board's XT60: the gate drive, with the parts that
    #   hang off the source copper in the band nearest it and the transistors and
    #   their followers in the pocket;
    #   THE FRONT STRIP, between the bank and the plugs: the cutoff's divider,
    #   its filter and what feeds the reference;
    #   THE OUTBOARD BLOCK beside the comparator: the hold, round the plug it
    #   arrives on, with the narrow parts standing on end in a 2.1 mm column.
    #
    # Only R3 and R4 care in the electrical sense -- 10 ohms in series with a
    # gate wants to be at the gate. Everything else here is kilohms and megohms
    # into a comparator, and a long track costs it nothing but room.
    "D1": (33.2, -16.3, 0),
    "R2": (38.05, -16.3, 0),
    "R3": (42.9, -16.3, 0),
    "R8": (33.2, -13.0, 0),
    "R24": (38.05, -13.0, 0),
    "D2": (42.9, -13.0, 0),
    # The inboard pocket. Nothing with a lead may stand behind it, over the
    # bought board's own input socket, and nothing over 7.4 mm may stand in it,
    # under the pack's own connectors.
    "Q4": (23.5, 2.0, 0),
    "Q3": (23.5, 7.0, 0),
    "R6": (29.1, 0.8, 90),
    "R7": (29.1, 5.5, 90),
    "R5": (22.7, 11.0, 0),
    "D3": (22.8, 13.6, 0),
    "R9": (29.1, 10.2, 90),
    "D8": (22.8, 16.0, 0),
    # Outboard of the switches, beside the gate and the button they serve.
    "R4": (70.2, -17.4, 90),
    "D6": (38.5, 14.9, 0),
    # The front strip: the divider, its filter, and the comparator's own feed.
    "C3": (33.0, 11.7, 0),
    "R11": (38.5, 9.5, 0),
    "R12": (43.35, 9.5, 0),
    "R10": (52.9, -1.4, 0),
    "R15": (62.6, -1.4, 0),
    "C2": (38.5, 12.2, 0),
    "R13": (57.75, -1.4, 0),
    "D7": (43.35, 12.2, 0),
    "R14": (67.45, -1.4, 0),
    "R16": (52.9, 6.5, 0),
    # THE COMPARATOR, turned so the reference and the divider are on the pins
    # facing the front strip and the two holds are on the pins facing the block
    # of upright parts outboard of it.
    "U1": (65.32, 7.0, 180),
    "C1": (69.5, -10.0, 90),
    "R17": (52.9, 9.2, 0),
    "C4": (53.3, 2.3, 0),
    "U2": (58.2, 2.0, 0),
    "R18": (52.9, 11.9, 0),
    "R19": (52.9, 14.6, 0),
    "D4": (67.7, 6.5, 0),
    "D5": (67.7, 9.2, 0),
    "R20": (48.2, 9.5, 0),
    "R21": (48.2, 12.2, 0),
    "R22": (67.7, 11.9, 0),
    "R23": (67.7, 14.6, 0),
}

FIXED = frozenset(e.powerSwitchStations)


def net_of() -> dict[tuple[str, str], str]:
    return {
        endpoint: net for net, endpoints in power.NETS.items() for endpoint in endpoints
    }


# ---- the copper that is poured rather than routed -----------------------------------
#
# Each zone is a union of rectangles, in torso x and y. They are drawn round the
# pads they join and away from the pads they must not, and they are kept out of
# one another by more than KiCad's zone clearance -- so the fill does not have to
# arbitrate, and a router that stays out of them cannot cut one in two.
#
# BATT and VSRC are poured on both layers: every pad on them is a through-hole
# pin, so the two layers share the current. VDRN and VBUS join the switches'
# drains to the shunt's pads and the shunt to the output pad, and a 2512 is only
# on the top: they are top-layer pours, which leaves the bottom layer under them
# free for the gate line and the Kelvin pair to cross.
ZONES = [
    {
        "net": "BATT",
        "layers": ("F.Cu", "B.Cu"),
        "rects": [(30.0, -24.6, 43.0, -17.9)],
        "priority": 2,
    },
    {
        "net": "VSRC",
        "layers": ("F.Cu", "B.Cu"),
        "rects": [
            (48.5, -24.6, 63.0, -17.0),
            (53.9, -17.0, 56.3, -13.8),
            (59.8, -17.0, 62.2, -13.8),
        ],
        "priority": 2,
    },
    {
        "net": "VDRN",
        "layers": ("F.Cu",),
        "rects": [
            (51.4, -11.6, 67.5, -9.4),
            (51.4, -15.5, 53.6, -11.6),
            (62.4, -15.5, 64.7, -11.6),
            (60.5, -9.8, 63.9, -5.2),
        ],
        "priority": 1,
    },
    {
        "net": "VBUS",
        "layers": ("F.Cu",),
        # The bar from the shunt's far lead to the output pad, and two risers up
        # to the bank's positive leads. THE RISERS REACH WELL INSIDE THE BAR
        # rather than meeting it edge to edge: a pour drawn as boxes that share
        # only a boundary line fills as two islands, and KiCad reported exactly
        # that -- one VBUS zone unconnected to another VBUS zone.
        # The bar from the shunt's far lead to the output pad, and two risers up
        # to the bank's positive leads. The outboard riser cannot stand on the bar
        # -- the shunt's inboard sense lead is in the way -- so it comes off a link
        # that runs UNDER that lead, and the whole of it overlaps rather than
        # touching: a pour drawn as boxes that meet only on a boundary line fills
        # as two islands, and KiCad reported exactly that, one VBUS zone
        # unconnected to another VBUS zone.
        "rects": [
            (31.6, -9.9, 46.2, -5.1),
            (31.9, -8.6, 34.1, 4.0),
            (41.0, -9.9, 44.3, -8.9),
            (42.9, -9.9, 44.3, 4.0),
        ],
        "priority": 1,
    },
    # AND GROUND, WHICH IS THE WHOLE BOTTOM LAYER. It is "soft": tracks may cross
    # it, because the fill flows round them and every ground pad is a via away
    # from it. That is what keeps the signal side of this board short -- without
    # it the ground net alone wandered the length of the board twice.
    {
        "net": "GND",
        "layers": ("B.Cu",),
        "rects": [(X_MIN + 0.5, Y_MIN + 0.5, X_MAX - 0.5, Y_MAX - 0.5)],
        "priority": 0,
        "soft": True,
    },
]


SOFT = frozenset(zone["net"] for zone in ZONES if zone.get("soft"))


def zone_pieces(zone) -> list[tuple[list, list]]:
    """A zone as KiCad wants it: one (outline, holes) per connected piece.

    A pour with a screw's keepout taken out of it near an edge comes back from
    shapely as several pieces, and a screw well inside it comes back as a hole.
    Both are real, and a zone that dropped either would be a zone that is not
    the shape this file checked.
    """
    shape = zone_polygon(zone)
    parts = list(shape.geoms) if shape.geom_type == "MultiPolygon" else [shape]
    return [
        (list(part.exterior.coords)[:-1], [list(h.coords)[:-1] for h in part.interiors])
        for part in parts
    ]


def zone_polygon(zone):
    from shapely.geometry import Point, box
    from shapely.ops import unary_union

    shape = unary_union([box(*rect) for rect in zone["rects"]])
    for sx, sy in SCREWS:
        shape = shape.difference(Point(sx, sy).buffer(SCREW_COPPER_KEEPOUT, 32))
    return shape


# ---- legalizing the placement ---------------------------------------------------------


def _pad_shape(x: float, y: float, w: float, h: float):
    from shapely.geometry import box

    return box(x - w / 2, y - h / 2, x + w / 2, y + h / 2)


def legal(part: Placed, down: list[Placed], zones) -> bool:
    x0, y0, x1, y1 = part.courtyard()
    if not (inside_outline(x0, y0, 0.1) and inside_outline(x1, y1, 0.1)):
        return False
    for sx, sy in SCREWS:
        nx = min(max(sx, x0), x1)
        ny = min(max(sy, y0), y1)
        if math.hypot(nx - sx, ny - sy) < SCREW_BODY_KEEPOUT:
            return False
    for other in down:
        a0, b0, a1, b1 = other.courtyard()
        if x0 < a1 and a0 < x1 and y0 < b1 and b0 < y1:
            return False
    nets = net_of()
    for pad, px, py, w, h in part.pads():
        if pad.drill and SOCKET_FOULS_TAILS:
            sx0, sy0, sx1, sy1 = SOCKET
            if (
                px + w / 2 + TAIL_CLEARANCE > sx0
                and px - w / 2 - TAIL_CLEARANCE < sx1
                and py + h / 2 + TAIL_CLEARANCE > sy0
                and py - h / 2 - TAIL_CLEARANCE < sy1
            ):
                return False
        net = nets.get((part.refdes, pad.name))
        shape = _pad_shape(px, py, w, h).buffer(ZONE_CLEARANCE + 0.05)
        for zone, polygon in zones:
            if zone.get("soft") or zone["net"] == net:
                continue
            if not (set(zone["layers"]) & pad.copper()):
                continue
            if polygon.intersects(shape):
                return False
    return True


def legalize() -> list[Placed]:
    """Every part at its target, or at the nearest place it fits.

    The tall parts are not moved at all: they are where the CAD says. Every other
    part is tried at its target and then on rings of growing radius, and takes the
    first position that is on the board, off every screw, clear of every courtyard
    already down and clear of every zone that is not its own net's.
    """
    zones = [(zone, zone_polygon(zone)) for zone in ZONES]
    down: list[Placed] = []
    steps = [(0.0, 0.0)]
    for ring in range(1, 49):
        r = ring * 0.25
        count = max(8, int(2 * math.pi * r / 0.25))
        for k in range(count):
            a = 2 * math.pi * k / count
            steps.append((round(r * math.cos(a), 3), round(r * math.sin(a), 3)))

    # THE TALL PARTS FIRST BECAUSE THE CAD PUT THEM THERE, then the rest BIGGEST
    # FIRST. That second rule is worth the line it costs: placing in the order the
    # table is written lets a 9 mm2 resistor take the only block a 42 mm2 capacitor
    # could have used, and then the capacitor has nowhere to go and the whole run
    # fails on the largest part rather than the one that stole from it. Biggest
    # first is the ordinary bin-packing answer and it is what makes this board's
    # two big capacitors land where they were asked for.
    def area(refdes: str) -> float:
        x0, y0, x1, y1 = load_footprint(*FOOTPRINT_OF[refdes]).courtyard
        return (x1 - x0) * (y1 - y0)

    order = [r for r in TARGETS if r in FIXED] + sorted(
        (r for r in TARGETS if r not in FIXED), key=area, reverse=True
    )
    for refdes in order:
        x, y, rotation = TARGETS[refdes]
        footprint = load_footprint(*FOOTPRINT_OF[refdes])
        if refdes in FIXED:
            down.append(Placed(refdes, footprint, x, y, rotation))
            continue
        for dx, dy in steps:
            candidate = Placed(refdes, footprint, x + dx, y + dy, rotation)
            if legal(candidate, down, zones):
                down.append(candidate)
                break
        else:
            UNPLACED.append(refdes)
    return sorted(down, key=lambda p: p.refdes)


# Parts legalize() found nowhere for; check_placement() reports them.
UNPLACED: list[str] = []


# ---- the router -----------------------------------------------------------------------
#
# A plain A* maze router on a 0.1 mm grid over both layers, with a cost for a via
# and for a bend, connecting each net's pads one at a time into a growing tree.
# It is the same idea as the carrier's with two differences this board needs: a
# surface-mount pad exists on the top layer only, and a poured net's zone is part
# of its tree from the start, so a small part on VBUS connects to the nearest edge
# of VBUS copper rather than to the output pad on the far side of it.

GRID = 0.1
# HOW MUCH SLACK THE GRID ITSELF NEEDS on top of the clearance. The router works
# on cell centres and the copper is a polyline through them, so a track's real
# edge stands off its cells by a fraction of a cell at every bend and every
# diagonal. Measured rather than reasoned, by KiCad: at 0.06 it reported ten
# clearances of 0.175 mm where 0.2 was wanted, all of them a diagonal or a via
# against a diagonal, and 0.1 clears them.
MARGIN = 0.1
VIA_COST = 35.0
BEND_COST = 3.0
# The bottom layer is the ground pour's; a signal pays a little to cut through it.
BOTTOM_COST = 1.25
LAYERS = ("F.Cu", "B.Cu")


class Grid:
    def __init__(self, parts: list[Placed]) -> None:
        import numpy as np

        self.np = np
        self.nx = int(round((X_MAX - X_MIN) / GRID)) + 1
        self.ny = int(round((Y_MAX - Y_MIN) / GRID)) + 1
        xs = X_MIN + np.arange(self.nx) * GRID
        ys = Y_MIN + np.arange(self.ny) * GRID
        self.gx, self.gy = np.meshgrid(xs, ys, indexing="ij")
        edge = np.minimum.reduce(
            [self.gx - X_MIN, self.gy - Y_MIN, X_MAX - self.gx, Y_MAX - self.gy]
        )
        self.edge = edge
        self.screw = np.full_like(edge, 1e3)
        self.drills = np.full_like(edge, 1e3)
        for sx, sy in SCREWS:
            d = np.hypot(self.gx - sx, self.gy - sy)
            self.screw = np.minimum(self.screw, d - SCREW_COPPER_KEEPOUT)
            self.drills = np.minimum(self.drills, d - SCREW_HOLE / 2)
        self.owner = {
            layer: np.full((self.nx, self.ny), -1, np.int32) for layer in LAYERS
        }
        self.names: list[str] = []
        self.ids: dict[str, int] = {}
        self.zone_mask: dict[tuple[str, str], object] = {}
        import shapely

        for zone in ZONES:
            polygon = zone_polygon(zone)
            inside = shapely.contains_xy(polygon, self.gx, self.gy)
            for layer in zone["layers"]:
                key = (zone["net"], layer)
                prior = self.zone_mask.get(key)
                self.zone_mask[key] = inside if prior is None else (prior | inside)
        nets = net_of()
        self.pad_cells: dict[tuple[str, str], list[tuple[int, int, int]]] = {}
        for part in parts:
            for pad, x, y, w, h in part.pads():
                net = nets[(part.refdes, pad.name)]
                owner = self.id(net)
                layers = [
                    LAYERS.index(layer) for layer in LAYERS if layer in pad.copper()
                ]
                full = (np.abs(self.gx - x) <= w / 2) & (np.abs(self.gy - y) <= h / 2)
                # WHERE A TRACK MAY LAND ON THIS PAD. On a surface-mount pad that
                # is the pad less a hair, so the track's own width stays on the
                # copper. On a DRILLED pad it is a RING, because the middle of the
                # pad is the hole: the shunt's leads sit in 1.5 mm drills inside
                # 3.0 mm pads, and a router that aimed at the centre laid its
                # track into the hole -- which KiCad reported as two unconnected
                # sense pads on a board that looked finished.
                if pad.drill:
                    radius = np.hypot(self.gx - x, self.gy - y)
                    # Inside the ring AND inside the pad: a drilled pad is round
                    # or oval, so the corners of its bounding box are not copper,
                    # and a track that stopped in one of them read as unconnected
                    # on a board where every other check was clean.
                    core = (radius >= pad.drill / 2 + 0.15) & (
                        radius <= max(min(w, h) / 2 - 0.05, pad.drill / 2 + 0.2)
                    )
                else:
                    core = (np.abs(self.gx - x) <= max(w / 2 - 0.15, 0.05)) & (
                        np.abs(self.gy - y) <= max(h / 2 - 0.15, 0.05)
                    )
                for li in layers:
                    self.owner[LAYERS[li]][full] = owner
                ix, iy = np.nonzero(core)
                # Extended rather than assigned: a footprint may carry the same
                # pin twice -- the fuse holder does -- and both are copper the
                # net may be reached at.
                self.pad_cells.setdefault((part.refdes, pad.name), []).extend(
                    (int(a), int(b), li) for a, b in zip(ix, iy) for li in layers
                )
                if pad.drill:
                    d = np.hypot(self.gx - x, self.gy - y) - pad.drill / 2
                    self.drills = np.minimum(self.drills, d)

    def id(self, net: str) -> int:
        if net not in self.ids:
            self.ids[net] = len(self.names)
            self.names.append(net)
        return self.ids[net]

    def cell(self, x: float, y: float) -> tuple[int, int]:
        return int(round((x - X_MIN) / GRID)), int(round((y - Y_MIN) / GRID))

    def point(self, ix: int, iy: int) -> tuple[float, float]:
        return (round(X_MIN + ix * GRID, 4), round(Y_MIN + iy * GRID, 4))

    def _dilate(self, mask, radius: float):
        np = self.np
        reach = int(math.ceil(radius / GRID))
        out = mask.copy()
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                if (dx or dy) and math.hypot(dx, dy) * GRID <= radius:
                    shifted = np.zeros_like(mask)
                    x0, x1 = max(0, dx), min(self.nx, self.nx + dx)
                    y0, y1 = max(0, dy), min(self.ny, self.ny + dy)
                    shifted[x0:x1, y0:y1] = mask[x0 - dx : x1 - dx, y0 - dy : y1 - dy]
                    out |= shifted
        return out

    def blocked(self, net: str, width: float, via: bool = False):
        """Cells a track centre -- or a via centre -- of this net may not use."""
        owner = self.id(net)
        half = (VIA_PAD / 2) if via else (width / 2)
        out = {}
        for layer in LAYERS:
            other = (self.owner[layer] >= 0) & (self.owner[layer] != owner)
            block = self._dilate(other, half + CLEARANCE + MARGIN)
            block |= self.edge < (half + EDGE_CLEARANCE)
            block |= self.screw < (half + CLEARANCE)
            for (zone_net, zone_layer), mask in self.zone_mask.items():
                if zone_layer == layer and zone_net != net and zone_net not in SOFT:
                    block |= self._dilate(mask, half + ZONE_CLEARANCE + MARGIN)
            if via:
                block |= self.drills < (VIA_DRILL / 2 + HOLE_TO_HOLE + MARGIN)
            out[layer] = block
        return out

    def stamp_track(self, layer: str, points, net: str, width: float) -> None:
        np = self.np
        owner = self.id(net)
        grid = self.owner[layer]
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            x0, x1 = sorted((ax, bx))
            y0, y1 = sorted((ay, by))
            pad = width / 2 + GRID
            sel = (
                (self.gx >= x0 - pad)
                & (self.gx <= x1 + pad)
                & (self.gy >= y0 - pad)
                & (self.gy <= y1 + pad)
            )
            ix, iy = np.nonzero(sel)
            px = self.gx[ix, iy]
            py = self.gy[ix, iy]
            vx, vy = bx - ax, by - ay
            length = vx * vx + vy * vy
            t = (
                np.clip(((px - ax) * vx + (py - ay) * vy) / length, 0, 1)
                if length
                else 0
            )
            d = np.hypot(px - (ax + t * vx), py - (ay + t * vy))
            hit = d <= width / 2
            grid[ix[hit], iy[hit]] = owner

    def stamp_via(self, x: float, y: float, net: str) -> None:
        np = self.np
        d = np.hypot(self.gx - x, self.gy - y)
        for layer in LAYERS:
            self.owner[layer][d <= VIA_PAD / 2] = self.id(net)
        self.drills = np.minimum(self.drills, d - VIA_DRILL / 2)


def _astar(grid: Grid, blocked, via_blocked, sources, targets, goal_xy):
    tx, ty = goal_xy
    goal = set(targets)

    def h(ix, iy):
        dx, dy = abs(ix - tx), abs(iy - ty)
        return max(dx, dy) + 0.414 * min(dx, dy)

    best: dict[tuple[int, int, int], float] = {}
    came: dict[tuple[int, int, int], object] = {}
    heap: list = []
    for s in sources:
        if s not in best:
            best[s] = 0.0
            heapq.heappush(heap, (h(s[0], s[1]), 0.0, s, None))
    steps = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0)] + [
        (dx, dy, 1.4142) for dx in (1, -1) for dy in (1, -1)
    ]
    expanded = 0
    while heap:
        _, cost, key, parent = heapq.heappop(heap)
        if key in came:
            continue
        came[key] = parent
        expanded += 1
        # THE GRID IS HALF A MILLION CELLS ON TWO LAYERS, so a search that has
        # expanded four times that has not been unlucky, it is walled in.
        if expanded > 2_000_000:
            return None
        if key in goal:
            path = []
            walk = key
            while walk is not None:
                path.append(walk)
                walk = came[walk]
            return list(reversed(path))
        ix, iy, il = key
        layer = LAYERS[il]
        for dx, dy, step in steps:
            jx, jy = ix + dx, iy + dy
            if not (0 <= jx < grid.nx and 0 <= jy < grid.ny):
                continue
            if blocked[layer][jx, jy] and (jx, jy, il) not in goal:
                continue
            if (
                dx
                and dy
                and (blocked[layer][ix + dx, iy] or blocked[layer][ix, iy + dy])
            ):
                continue
            move = cost + step * (BOTTOM_COST if il else 1.0)
            if parent is not None and parent[2] == il:
                if (ix - parent[0], iy - parent[1]) != (dx, dy):
                    move += BEND_COST
            nkey = (jx, jy, il)
            if move < best.get(nkey, 1e18):
                best[nkey] = move
                heapq.heappush(heap, (move + h(jx, jy), move, nkey, key))
        other = 1 - il
        if not (via_blocked["F.Cu"][ix, iy] or via_blocked["B.Cu"][ix, iy]):
            nkey = (ix, iy, other)
            move = cost + VIA_COST
            if move < best.get(nkey, 1e18):
                best[nkey] = move
                heapq.heappush(heap, (move + h(ix, iy), move, nkey, key))
    return None


def _geometry(grid: Grid, path, net: str, width: float):
    tracks, vias = [], []
    run = [path[0]]
    for node in path[1:]:
        if node[2] != run[-1][2]:
            if len(run) > 1:
                tracks.append(_track(grid, run, net, width))
            x, y = grid.point(run[-1][0], run[-1][1])
            vias.append({"net": net, "x": x, "y": y})
            run = [node]
        else:
            run.append(node)
    if len(run) > 1:
        tracks.append(_track(grid, run, net, width))
    return tracks, vias


def _track(grid: Grid, run, net: str, width: float):
    points = [run[0]]
    for i in range(1, len(run) - 1):
        a, b, c = run[i - 1], run[i], run[i + 1]
        if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
            points.append(b)
    points.append(run[-1])
    return {
        "net": net,
        "layer": LAYERS[run[0][2]],
        "width": width,
        "points": [grid.point(p[0], p[1]) for p in points],
    }


# The nets that have to find a way through the most, first.
# The nets with the least room to find a way through, first. Ground is early
# rather than late for the same reason: each of its pads is one via from the
# pour under the board, and a via needs somewhere to sit.
ROUTE_FIRST = ("GATE", "GND", "VSRC", "VBUS", "SHUNT_P", "SHUNT_N", "EN", "REF")
PASSES = 4


def _pins_by_net(parts: list[Placed]) -> dict[str, list[tuple[str, str]]]:
    nets = net_of()
    out: dict[str, list[tuple[str, str]]] = {}
    for part in parts:
        for pad, *_ in part.pads():
            out.setdefault(nets[(part.refdes, pad.name)], []).append(
                (part.refdes, pad.name)
            )
    return out


def _one_pass(parts: list[Placed], order: list[str], by_net):
    """Route every net once, in this order, onto a bare board."""
    grid = Grid(parts)
    # THE SOFT POUR IS NOT A CONNECTION, it is copper. Ground is poured over the
    # whole bottom layer AND routed pad to pad like any other net, because a
    # signal crossing that pour can cut it in two -- which KiCad reported as an
    # open circuit both times this board has been laid out, once as a surface
    # mount board and once as this one. Routed as well, the pour shares the
    # current and nothing depends on the fill staying in one piece.
    zoned = {zone["net"] for zone in ZONES if not zone.get("soft")}
    tracks: list[dict] = []
    vias: list[dict] = []
    failures: list[str] = []
    positions = {
        (part.refdes, pad.name): (x, y)
        for part in parts
        for pad, x, y, _, _ in part.pads()
    }
    for net in order:
        pins = by_net[net]
        width = BRANCH if net in zoned else TRACK
        tree: set[tuple[int, int, int]] = set()
        todo = list(pins)
        if net in zoned:
            for (zone_net, layer), mask in grid.zone_mask.items():
                if zone_net != net:
                    continue
                li = LAYERS.index(layer)
                # NOT THE POUR'S EDGE, A LITTLE INSIDE IT. A track that stops on
                # the outline stops where the fill is thinnest and KiCad reported
                # the pad on the far end of it as unconnected; the fill keeps its
                # own clearance and min-width and simply is not there at the line
                # the polygon is drawn on. Eroding the target by a quarter of a
                # millimetre makes the track land in copper that is really filled.
                inside = ~grid._dilate(~mask, 0.25)
                ix, iy = grid.np.nonzero(inside)
                tree.update((int(a), int(b), li) for a, b in zip(ix, iy))
            todo = [p for p in pins if not any(c in tree for c in grid.pad_cells[p])]
        if not tree:
            tree.update(grid.pad_cells[todo.pop(0)])
        sample = [
            grid.point(c[0], c[1]) for c in list(tree)[:: max(1, len(tree) // 300)]
        ]
        while todo:
            todo.sort(key=lambda p: min(math.dist(positions[p], q) for q in sample))
            target = todo.pop(0)
            blocked = grid.blocked(net, width)
            via_blocked = grid.blocked(net, width, via=True)
            path = _astar(
                grid,
                blocked,
                via_blocked,
                tree,
                grid.pad_cells[target],
                grid.cell(*positions[target]),
            )
            if path is None:
                failures.append(net)
                continue
            new_tracks, new_vias = _geometry(grid, path, net, width)
            for track in new_tracks:
                grid.stamp_track(track["layer"], track["points"], net, width)
            for via in new_vias:
                grid.stamp_via(via["x"], via["y"], net)
            tracks += new_tracks
            vias += new_vias
            tree.update(path)
            tree.update(grid.pad_cells[target])
            sample += [grid.point(p[0], p[1]) for p in path[:: max(1, len(path) // 8)]]
    return tracks, vias, failures, grid


def route(parts: list[Placed], report: Report):
    """Every net, in the cheapest order of a few that were tried.

    A net that cannot be routed is pushed to the front of the queue and the whole
    board is laid again, which is the only rip-up this router has and is usually
    enough: what blocks a net is nearly always a net that went down before it.
    """
    by_net = _pins_by_net(parts)
    rest = sorted(n for n in by_net if n not in ROUTE_FIRST)
    first: list[str] = []
    best = None
    for attempt in range(PASSES):
        order = (
            [n for n in first if n in by_net]
            + [n for n in ROUTE_FIRST if n in by_net and n not in first]
            + [n for n in rest if n not in first]
        )
        tracks, vias, failures, grid = _one_pass(parts, order, by_net)
        copper = sum(
            math.dist(t["points"][i], t["points"][i + 1])
            for t in tracks
            for i in range(len(t["points"]) - 1)
        ) + 5.0 * len(vias)
        score = (len(failures), copper)
        if best is None or score < best[0]:
            best = (score, tracks, vias, failures, grid)
        if not failures:
            break
        first = failures + first
    _, tracks, vias, failures, grid = best
    for net in failures:
        report.faults.append(f"{net}: no route found, in {PASSES} orders")
    return tracks, vias, grid


# THE TWO LAYERS OF A BOTH-LAYER POUR ARE STITCHED, so they share the current
# between the pins rather than only at them.
STITCH_PITCH = 1.6


def stitching(grid: Grid) -> list[dict]:
    out = []
    for zone in ZONES:
        if len(zone["layers"]) < 2:
            continue
        net = zone["net"]
        both = grid.zone_mask[(net, "F.Cu")] & grid.zone_mask[(net, "B.Cu")]
        clear = both.copy()
        for layer in LAYERS:
            other = (grid.owner[layer] >= 0) & (grid.owner[layer] != grid.id(net))
            clear &= ~grid._dilate(other, VIA_PAD / 2 + ZONE_CLEARANCE + 0.1)
            own = grid.owner[layer] == grid.id(net)
            clear &= ~grid._dilate(own, VIA_PAD / 2 + 0.2)
        clear &= grid.edge > VIA_PAD / 2 + EDGE_CLEARANCE
        clear &= grid.screw > VIA_PAD / 2 + CLEARANCE
        # Shrink by a via radius so the via sits wholly inside the pour.
        clear &= ~grid._dilate(~both, VIA_PAD / 2 + ZONE_MIN_WIDTH)
        step = int(round(STITCH_PITCH / GRID))
        for ix in range(0, grid.nx, step):
            for iy in range(0, grid.ny, step):
                if (
                    clear[ix, iy]
                    and grid.drills[ix, iy] > VIA_DRILL / 2 + HOLE_TO_HOLE + 0.1
                ):
                    x, y = grid.point(ix, iy)
                    out.append({"net": net, "x": x, "y": y})
                    grid.stamp_via(x, y, net)
    return out


# ---- checks --------------------------------------------------------------------------


def check_placement(report: Report, parts: list[Placed]) -> None:
    """Every netlist part placed, with the pins its footprint really has."""
    names = {part.refdes for part in parts}
    for part in power.PARTS:
        if part.refdes not in names:
            why = (
                "nowhere legal near its target"
                if part.refdes in UNPLACED
                else "no target"
            )
            report.faults.append(f"{part.refdes} is not placed: {why}")
    for part in parts:
        pins = {pad.name for pad in part.footprint.pads if pad.kind != "np_thru_hole"}
        wanted = set(next(p for p in power.PARTS if p.refdes == part.refdes).pins)
        if pins != wanted:
            report.faults.append(
                f"{part.refdes}: footprint pins {sorted(pins)}, netlist {sorted(wanted)}"
            )


def bodies(part: Placed) -> list[tuple[str, tuple[float, ...]]]:
    """What a part occupies above and below the board, as boxes in the torso frame.

    (what, (x0, y0, x1, y1, z0, z1)). Above the board it is the part and what
    plugs into it; below it is 2 mm of solder tail under every through-hole pin.
    """
    name = part.footprint.name
    top = TOP_Z
    out = []
    if name.startswith("TO-220"):
        x0, y0, x1, y1 = part.box(-2.46, -3.15, 7.54, 1.25)
        out.append(("body", (x0, y0, x1, y1, top, top + part.footprint.height)))
    elif name.startswith("Fuseholder"):
        x0, y0, x1, y1 = part.box(-3.04, -1.67, 12.96, 5.07)
        out.append(("holder", (x0, y0, x1, y1, top, top + 7.37)))
        x0, y0, x1, y1 = part.box(4.96 - 5.45, 1.7 - 1.9, 4.96 + 5.45, 1.7 + 1.9)
        out.append(("fuse", (x0, y0, x1, y1, top + 7.37, top + part.footprint.height)))
    elif name == "R_Shunt_Isabellenhuette_PBV_F1":
        # Manufacturer drawing Z-DW-132b; reserve the lead stand-off as body too.
        x0, y0, x1, y1 = part.box(-2.36, -2.55, 20.14, 1.9)
        out.append(("body", (x0, y0, x1, y1, top, top + part.footprint.height)))
    elif name.startswith("SolderWire"):
        pad = part.footprint.pads[0]
        x0, y0, x1, y1 = part.box(-pad.w / 2, -pad.h / 2, pad.w / 2, pad.h / 2)
        out.append(("lead", (x0, y0, x1, y1, top, top + part.footprint.height)))
    else:
        x0, y0, x1, y1 = part.courtyard()
        out.append(("body", (x0, y0, x1, y1, top, top + part.footprint.height)))
    for pad, x, y, w, h in part.pads():
        if pad.drill:
            bottom = TOP_Z - e.pcbThickness
            out.append(
                (
                    "tail",
                    (x - w / 2, y - h / 2, x + w / 2, y + h / 2, bottom - 2.0, bottom),
                )
            )
    return out


# The power board's own stand-ins in cad/electronics.py, which this file replaces
# and so must not be measured against.
STAND_INS = {
    "power switch board",
    "power switch parts",
    "power switch spacers",
    # The bank is two parts ON this board now, so the CAD's cans are this file's
    # own C5 and C6 drawn twice rather than something to clear.
    "capacitor bank",
}

# WHAT IS DRAWN AS A SOLID BUT IS ACTUALLY A PIECE OF WIRE. The pack's main leads
# and the link that puts the two packs in series are flying leads: the CAD draws
# them as blocks so that the space they need is reserved and visible, but a lead
# goes where it is dressed and a part standing in its drawn path is a lead to be
# re-dressed rather than a part to be moved. So a clash with one of these is a
# note, and everything else -- the pack's own connectors, the bought boards, the
# deck, the shell -- is a fault. The connectors are NOT in here: an XT60 on the
# end of a lead still has to be somewhere, and where it can be is set by the pack
# it plugs into.
FLEXIBLE = {"battery main leads", "battery series link"}


def check_against_cad(report: Report, parts: list[Placed]) -> None:
    """Every body on this board against every drawn thing in the torso."""
    from build123d import Align, Box, Pos

    from cad import deck, torso

    groups = {
        name: solids
        for name, solids in e.torsoElectronicsGroups().items()
        if name not in STAND_INS
    }
    groups["deck"] = deck.electronicsDeck()
    groups["pelvis"] = torso.pelvisShell()[:-1]

    reach = 3.0
    nearest: dict[str, tuple[float, str]] = {}
    for part in parts:
        for what, (x0, y0, x1, y1, z0, z1) in bodies(part):
            mine = Pos((x0 + x1) / 2, (y0 + y1) / 2, z0) * Box(
                x1 - x0, y1 - y0, z1 - z0, align=(Align.CENTER, Align.CENTER, Align.MIN)
            )
            label = f"{part.refdes} {what}"
            for name, solids in groups.items():
                for other in solids:
                    bb = other.bounding_box()
                    if not (
                        x0 < bb.max.X + reach
                        and bb.min.X - reach < x1
                        and y0 < bb.max.Y + reach
                        and bb.min.Y - reach < y1
                        and z0 < bb.max.Z + reach
                        and bb.min.Z - reach < z1
                    ):
                        continue
                    try:
                        shared = abs((mine & other).volume)
                    except (ValueError, AttributeError, TypeError):
                        shared = 0.0
                    if shared > 1e-6:
                        where = report.notes if name in FLEXIBLE else report.faults
                        where.append(f"{label} shares {shared:.2f} mm3 with the {name}")
                        continue
                    gap = mine.distance_to(other)
                    if gap < nearest.get(label, (reach, ""))[0]:
                        nearest[label] = (gap, name)
    for label, (gap, name) in sorted(nearest.items(), key=lambda item: item[1][0])[:8]:
        report.notes.append(f"{label}: {gap:.2f} mm from the {name}")


# ---- building it in KiCad ------------------------------------------------------------

PROJECT = """{
  "board": {
    "design_settings": {
      "defaults": {
        "board_outline_line_width": 0.1,
        "copper_line_width": 0.25,
        "silk_line_width": 0.15,
        "silk_text_size_h": 1.0,
        "silk_text_size_v": 1.0,
        "silk_text_thickness": 0.15
      },
      "rules": {
        "min_clearance": 0.2,
        "min_copper_edge_clearance": 0.4,
        "min_hole_clearance": 0.25,
        "min_hole_to_hole": 0.25,
        "min_through_hole_diameter": 0.4,
        "min_track_width": 0.25,
        "min_via_annular_width": 0.15,
        "min_via_diameter": 0.8
      }
    }
  },
  "meta": { "filename": "power.kicad_pro", "version": 1 },
  "net_settings": {
    "classes": [
      {
        "clearance": 0.2,
        "microvia_diameter": 0.3,
        "microvia_drill": 0.1,
        "name": "Default",
        "track_width": 0.25,
        "via_diameter": 0.8,
        "via_drill": 0.4
      }
    ]
  },
  "sheets": [],
  "text_variables": {}
}
"""


def description(parts: list[Placed], tracks, vias) -> dict:
    nets = net_of()
    values = {part.refdes: part.partNumber for part in power.PARTS}
    return {
        "board": str(BOARD_FILE),
        "pads_out": str(OUT / "pads.json"),
        "outline": [place(x, y) for x, y in OUTLINE],
        "holes": [
            {
                "name": f"H{i + 1}",
                "x": place(x, y)[0],
                "y": place(x, y)[1],
                "d": SCREW_HOLE,
            }
            for i, (x, y) in enumerate(SCREWS)
        ],
        "parts": [
            {
                "ref": part.refdes,
                "lib": str(footprint_library(part.footprint.library)),
                "fp": part.footprint.name,
                "x": place(part.x, part.y)[0],
                "y": place(part.x, part.y)[1],
                "rot": part.rotation,
                "value": values[part.refdes],
                "pads": {
                    pad.name: nets[(part.refdes, pad.name)]
                    for pad in part.footprint.pads
                },
            }
            for part in parts
        ],
        "tracks": [
            {**track, "points": [place(x, y) for x, y in track["points"]]}
            for track in tracks
        ],
        "vias": [
            {
                **via,
                "x": place(via["x"], via["y"])[0],
                "y": place(via["x"], via["y"])[1],
                "d": VIA_PAD,
                "drill": VIA_DRILL,
            }
            for via in vias
        ],
        "zones": [
            {
                "net": zone["net"],
                "layers": list(zone["layers"]),
                "polygon": [place(x, y) for x, y in outline],
                "holes": [[place(x, y) for x, y in hole] for hole in holes],
                "priority": zone["priority"],
                "clearance": ZONE_CLEARANCE,
                "min_width": ZONE_MIN_WIDTH,
            }
            for zone in ZONES
            for outline, holes in zone_pieces(zone)
        ],
        "title": "power switch board -- generated by electrical/power_pcb.py, do not edit",
    }


def build_in_kicad(parts: list[Placed], tracks, vias, report: Report) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    project = OUT / "power.kicad_pro"
    if not project.exists():
        project.write_text(PROJECT, encoding="utf-8")
    spec = OUT / "power_board.json"
    spec.write_text(
        json.dumps(description(parts, tracks, vias), indent=1), encoding="utf-8"
    )
    # KiCad's Python finds pcbnew through its own installation, so it is run
    # with this one's environment taken off it: uv puts a virtual environment on
    # PYTHONPATH and PYTHONHOME, and either is enough to hide pcbnew.
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "VIRTUAL_ENV")
    }
    env["PYTHONNOUSERSITE"] = "1"
    done = subprocess.run(
        [str(kicad_python()), str(ROOT / "electrical" / "power_kicad.py"), str(spec)],
        capture_output=True,
        text=True,
        env=env,
    )
    if done.returncode != 0:
        report.faults.append("KiCad build failed:\n" + done.stdout + done.stderr)
        return {}
    # Every pad where this file put it: KiCad's own positions, read back.
    built = json.loads((OUT / "pads.json").read_text(encoding="utf-8"))
    worst = 0.0
    for part in parts:
        for index, (pad, x, y, _, _) in enumerate(part.pads()):
            kx, ky = built[f"{part.refdes}#{index}"]
            bx, by = unplace(kx, ky)
            worst = max(worst, math.hypot(bx - x, by - y))
    if worst > 0.01:
        report.faults.append(f"KiCad put a pad {worst:.3f} mm from where it was placed")
    report.notes.append(f"every pad is where KiCad put it, to {worst:.4f} mm")
    return built


def drc(report: Report) -> None:
    out = OUT / "drc.json"
    subprocess.run(
        [
            str(kicad_cli()),
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--units",
            "mm",
            "--refill-zones",
            "--save-board",
            "--output",
            str(out),
            str(BOARD_FILE),
        ],
        capture_output=True,
        text=True,
    )
    result = json.loads(out.read_text(encoding="utf-8"))
    errors = [v for v in result.get("violations", []) if v.get("severity") == "error"]
    warnings = [v for v in result.get("violations", []) if v.get("severity") != "error"]
    unconnected = result.get("unconnected_items", [])
    for v in errors:
        where = "; ".join(item.get("description", "") for item in v.get("items", []))
        report.faults.append(f"DRC {v.get('type')}: {v.get('description')} -- {where}")
    for v in unconnected:
        where = "; ".join(item.get("description", "") for item in v.get("items", []))
        report.faults.append(f"DRC unconnected: {where}")
    kinds: dict[str, int] = {}
    for v in warnings:
        kinds[v.get("type")] = kinds.get(v.get("type"), 0) + 1
    report.notes.append(
        f"KiCad DRC: {len(errors)} errors, {len(unconnected)} unconnected, "
        f"{len(warnings)} warnings {dict(sorted(kinds.items()))}"
    )


# ---- the drawing -----------------------------------------------------------------------


def draw(path: Path, parts: list[Placed], tracks=(), vias=()) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon, Rectangle

    fig, ax = plt.subplots(figsize=(16, 10.5), dpi=110)
    ax.add_patch(
        Polygon(OUTLINE, closed=True, facecolor="#eef2ea", edgecolor="black", lw=1.2)
    )
    colours = {"F.Cu": "#c0392b", "B.Cu": "#2e6fbd"}
    for zone in ZONES:
        if zone.get("soft"):
            continue
        for outline, _ in zone_pieces(zone):
            for layer in zone["layers"]:
                ax.add_patch(
                    Polygon(
                        outline,
                        closed=True,
                        facecolor=colours[layer],
                        alpha=0.10,
                        edgecolor=colours[layer],
                        lw=0.6,
                    )
                )
        c = zone_polygon(zone).representative_point()
        ax.text(c.x, c.y, zone["net"], fontsize=9, color="#444", ha="center")
    for sx, sy in SCREWS:
        ax.add_patch(Circle((sx, sy), SCREW_HOLE / 2, color="black"))
        ax.add_patch(Circle((sx, sy), SCREW_BODY_KEEPOUT, fill=False, ls="--", lw=0.6))
    nets = net_of()
    for part in parts:
        x0, y0, x1, y1 = part.courtyard()
        ax.add_patch(
            Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, lw=0.5, color="#888")
        )
        ax.text((x0 + x1) / 2, y1 + 0.12, part.refdes, fontsize=6.5, ha="center")
        for pad, x, y, w, h in part.pads():
            colour = "#d4a017" if pad.kind == "smd" else "#b8860b"
            ax.add_patch(
                Rectangle((x - w / 2, y - h / 2), w, h, color=colour, alpha=0.9)
            )
            ax.text(
                x,
                y,
                nets.get((part.refdes, pad.name), "")[:7],
                fontsize=3.2,
                ha="center",
                va="center",
            )
    for track in tracks:
        xs = [p[0] for p in track["points"]]
        ys = [p[1] for p in track["points"]]
        ax.plot(
            xs,
            ys,
            color=colours[track["layer"]],
            lw=track["width"] * 4.5,
            alpha=0.75,
            solid_capstyle="round",
        )
    for via in vias:
        ax.add_patch(Circle((via["x"], via["y"]), VIA_PAD / 2, color="#333"))
    ax.set_xlim(X_MIN - 1, X_MAX + 1)
    ax.set_ylim(Y_MIN - 1, Y_MAX + 1)
    ax.set_aspect("equal")
    ax.grid(True, lw=0.3, alpha=0.5)
    ax.set_title(
        "power switch board from above, torso x and y in mm -- red top, blue bottom"
    )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draw", action="store_true")
    parser.add_argument("--no-cad", action="store_true")
    parser.add_argument("--place-only", action="store_true")
    args = parser.parse_args()

    if power.check():
        print("power_pcb: the netlist does not check out -- run electrical/power.py")
        return 1

    report = Report()
    parts = legalize()
    check_placement(report, parts)
    tracks: list[dict] = []
    vias: list[dict] = []
    if not args.place_only and not report.faults:
        tracks, vias, grid = route(parts, report)
        vias += stitching(grid)
    if args.draw:
        draw(PNG, parts, tracks, vias)
        print(f"wrote {PNG.relative_to(ROOT)}")
    if not args.place_only and not report.faults:
        build_in_kicad(parts, tracks, vias, report)
        if not report.faults:
            drc(report)
    if not args.no_cad:
        check_against_cad(report, parts)

    if args.place_only and args.draw:
        pass
    moved = [
        f"{p.refdes} {math.hypot(p.x - TARGETS[p.refdes][0], p.y - TARGETS[p.refdes][1]):.1f}"
        for p in parts
        if math.hypot(p.x - TARGETS[p.refdes][0], p.y - TARGETS[p.refdes][1]) > 0.01
    ]
    print(f"placed {len(parts)} parts; moved off target: {', '.join(moved) or 'none'}")
    print(f"routed {len(tracks)} tracks and {len(vias)} vias")
    for note in report.notes:
        print(f"  note   {note}")
    for fault in report.faults:
        print(f"  FAULT  {fault}")
    print("power_pcb: FAIL" if report.faults else "power_pcb: pass")
    return 1 if report.faults else 0


if __name__ == "__main__":
    raise SystemExit(main())
