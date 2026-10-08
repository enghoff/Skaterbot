# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1", "shapely>=2.0", "matplotlib>=3.8", "numpy>=1.26"]
# ///
"""The controller carrier as a two-layer printed circuit board, through-hole only.

electrical/carrier.py says what is soldered to what. This file says where, and
on which copper: every footprint, where it sits, every track, and the checks
that hold all of it against the netlist and against the torso it has to fit in.

    uv run electrical/carrier_pcb.py            # check it
    uv run electrical/carrier_pcb.py --draw     # also rewrite electrical/carrier_pcb.svg
    uv run electrical/carrier_pcb.py --no-cad   # skip the clash check against the torso

A PROPOSAL, AND NOT YET A FABRICATION FILE. The copper here is exact -- pads,
drills, tracks and pours are all real geometry, and the checks below run on that
geometry rather than on an intention -- but a board house wants Gerbers, and the
right way to get them is to transcribe this into KiCad and let its own DRC agree
with this one. What this file adds that KiCad does not is the part of the answer
that lives outside the board: whether a mated plug fouls the SBC, whether a
socket stands where a standoff has to, whether the antenna's bulkhead is over
a header.

WHAT THE CHECKS PROVE, in the order they run:

  1. every footprint has exactly the pins carrier.py gives its part;
  2. every body is on the board, clear of the mounting holes and the SBC's
     standoffs,
     and clear of every other body in three dimensions -- which is what lets a
     capacitor stand under the socketed core board without being called a clash;
  3. every body, and every plug with its wires leaving it, clears every drawn
     thing in the torso, measured in the CAD's own frame (skipped by --no-cad);
  4. the copper of any two nets is at least CLEARANCE apart on each layer, and
     no copper is near the board edge, a mounting hole or a standoff;
  5. each net's copper is ONE connected piece that reaches every pin the netlist
     puts on that net, and reaches nothing else. That is the check that matters:
     it is a short and open test on the drawn copper, pour included, and a track
     that stops a tenth short of its pad fails it.

PROVENANCE. The core board's header grid is WeAct's own board-shape drawing,
WeAct-STM32G474CoreBoard_V10 Board Shape.pdf in the same repository as the
schematic carrier.py cites: 36.28 x 28.14 mm, first column 6.97 mm from the
edge, rows 1.37 mm in, 20.32 mm between the inner rows. The JST-XH figures are
JST's catalogue eXH.pdf; pad and drill sizes are KiCad's standard library
footprints for the same parts. Every placement figure below is either read from
cad/electronics.py or is a choice, and says which.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "electrical"))

import carrier  # noqa: E402 -- the netlist, beside this file

from cad import electronics as e  # noqa: E402

SVG = ROOT / "electrical" / "carrier_pcb.svg"


# ---- the board, as the CAD draws it ------------------------------------------
#
# The frame is the board's own: origin at its rear outboard corner, x across the
# robot towards its centre line, y forwards, z up from the board's TOP face. So
# the edge at y = 0 faces the rear wall and its panel hardware, the edge at
# x = 0 is 2 mm off the left-hand wall, and the edge at x = 76 faces the empty
# half of the deck band under the SBC.

BOARD_W = e.controllerWidth
BOARD_D = e.controllerDepth
ORIGIN_X = e.controllerX - BOARD_W / 2
ORIGIN_Y = -BOARD_D / 2
TOP_Z = e.controllerBoardZ + e.pcbThickness

# WHERE IT IS SCREWED DOWN. Six stations, not four corners: a 140 mm board wants
# more than four, and two of the four corners are not available anyway -- the
# rear edge carries connectors from x 43 to x 118, and the rear outboard corner
# passes under the charge socket. The table lives in cad/electronics.py because
# cad/deck.py drills its bosses to the same list, and a station typed twice is a
# station that will disagree once.
MOUNTS = [(x - ORIGIN_X, y - ORIGIN_Y) for x, y in e.carrier_screw_xy()]
# AND WHAT IS SCREWED DOWN TO IT: the SBC, on four M2.5 x 10 standoffs on its own
# 58 x 23 hole pattern. These were Ø8.6 clearance holes for the posts the deck
# used to print, and the SBC hung over this board rather than standing on it.
STANDOFFS = [(px - ORIGIN_X, py - ORIGIN_Y) for px, py in e.sbc_standoff_xy()]


# ---- design rules --------------------------------------------------------------
#
# Chosen to sit well inside what any two-layer hobby fab builds as standard
# (0.15 mm track and gap, 0.3 mm drill), because the margin is what makes a
# hand-soldered board forgiving -- not because anything here needs to be fine.

TRACK = 0.25
POWER = 0.5
CLEARANCE = 0.2
EDGE_CLEARANCE = 0.3
VIA_PAD = 0.8
VIA_DRILL = 0.4
# HOW CLOSE TWO DRILLED HOLES MAY COME, edge to edge. Nothing about copper: two
# holes 0.2 mm apart in the laminate are one hole with a wall that breaks out
# under the drill, and the board house will either refuse the file or ship it
# broken. It is the rule a via on the same net as the pad beside it slips past,
# because there is no clearance to violate when both are ground.
HOLE_TO_HOLE = 0.25
POUR_CLEARANCE = 0.3
THERMAL_GAP = 0.3
THERMAL_SPOKE = 0.5
# These connector returns need solid copper, rather than a single surviving
# thermal spoke. Shared with the KiCad exporter; solder with board preheat.
SOLID_GROUND_PADS = frozenset({"J5-2", "J6-2"})

# WHAT MAY STAND NEAR A MOUNTING HOLE. On top, an M3 washer is 7 mm across and a
# driver comes down onto it; underneath, the 6 mm A/F brass standoff is 6.9 mm
# across its corners and its face has to seat flat on the board, so no solder
# joint may be under it either. Copper stays clear of both, whatever its net:
# the standoff is brass, and nothing on this board is meant to be grounded
# through a printed deck.
MOUNT_BODY_KEEPOUT = 3.5 + 0.5
MOUNT_COPPER_KEEPOUT = 6.0 / math.sqrt(3) + 0.35
# THE SBC'S STANDOFFS, which stand ON this board rather than passing through it:
# a 5 mm A/F hex pillar is 5.8 mm across its corners, and its foot has to seat
# flat, so no copper and no body comes inside that circle plus the same margins
# the mounting holes get. It is a smaller barrier than the posts were -- 6.8 mm
# across against 9.6 -- which is 2.8 mm more of every route that has to cross
# the line each pair stands on.
STANDOFF_BODY_KEEPOUT = e.sbcStandoffDiameter / math.sqrt(3) + 0.5
STANDOFF_COPPER_KEEPOUT = e.sbcStandoffDiameter / math.sqrt(3) + 0.35


# ---- footprints ------------------------------------------------------------------


@dataclass(frozen=True)
class Pad:
    """One plated through-hole, in its footprint's frame."""

    name: str
    x: float
    y: float
    w: float
    h: float
    drill: float
    shape: str = "circle"  # circle, oval or rect


@dataclass(frozen=True)
class Body:
    """A box a part occupies, in its footprint's frame: x0 y0 x1 y1 z0 z1."""

    box: tuple[float, float, float, float, float, float]
    what: str = "body"


@dataclass(frozen=True)
class Footprint:
    name: str
    pads: tuple[Pad, ...]
    bodies: tuple[Body, ...]
    # Holes that are not pins: cable-tie holes and the standoffs the two bought
    # modules bolt to. (x, y, diameter) in the footprint's frame. They are drilled
    # and they keep copper off, and that is the whole of what they do.
    holes: tuple[tuple[float, float, float], ...] = ()


def xh_top_entry(circuits: int) -> Footprint:
    """JST B#B-XH-A, top entry, 2.50 mm pitch -- NOT 2.54.

    Pads and body from KiCad's JST_XH_B#B-XH-A footprint, turned from its y-down
    frame into this file's y-up one, which is a change of convention and not a
    mirror: pin 1 is still on the left seen from above, and the 3.4 mm side of
    the body is still the side it was. Height 7.0 from JST's catalogue; the plug
    brings it to 9.8, and 3 mm is allowed over that for the wires to leave the
    housing before they bend.
    """
    pads = tuple(
        Pad(str(i + 1), 2.5 * i, 0.0, 1.7, 1.95, 0.95, "rect" if i == 0 else "oval")
        for i in range(circuits)
    )
    right = 2.5 * (circuits - 1) + 2.45
    return Footprint(
        f"JST B{circuits}B-XH-A",
        pads,
        (
            Body((-2.45, -3.4, right, 2.35, 0.0, 7.0), "header"),
            Body((-2.45, -3.4, right, 2.35, 7.0, 12.8), "plug and wires"),
        ),
    )


def dip8_socket() -> Footprint:
    """An 8-pin DIP in a turned-pin socket, centred. Pin 1 top left, anticlockwise.

    KiCad's DIP-8_W7.62mm_Socket pads; 7.0 mm tall with the chip in, which is the
    figure cad/electronics.py draws the transceivers at.
    """
    left = [(-3.81, 3.81), (-3.81, 1.27), (-3.81, -1.27), (-3.81, -3.81)]
    right = [(3.81, -3.81), (3.81, -1.27), (3.81, 1.27), (3.81, 3.81)]
    pads = tuple(
        Pad(str(n), x, y, 1.6, 1.6, 0.8, "rect" if n == 1 else "circle")
        for n, (x, y) in enumerate(left + right, start=1)
    )
    return Footprint(
        "DIP-8 socket", pads, (Body((-5.08, -5.14, 5.08, 5.14, 0.0, 7.0)),)
    )


def radial_mlcc() -> Footprint:
    """A dipped 100 nF X7R on 2.54 mm leads, stood upright.

    KEMET's C315 CASE SINCE 2026-10-07, C315C104K5R5TA: 3.81 long, 2.54 thick
    and 3.14 tall at most on KEMET's own sheet, with up to 1.52 of coating down
    the leads, so inside the 4.0 x 2.6 x 6.0 drawn here. The bill named
    the C320 until then, which is 5.08 x 3.18, and an outside review found it did
    not fit what was drawn: at its own size it stood within 0.25 mm of a
    neighbour in seven places round the transceivers. The smaller case is the
    same capacitor, so the part changed and not the layout.
    """
    return Footprint(
        "C radial 2.54",
        (
            Pad("1", 0.0, 0.0, 1.6, 1.6, 0.8),
            Pad("2", 2.54, 0.0, 1.6, 1.6, 0.8),
        ),
        (Body((-0.73, -1.3, 3.27, 1.3, 0.0, 6.0)),),
    )


def radial_electrolytic() -> Footprint:
    """10 uF, Ø5 x 7 mm or shorter, 2.0 mm leads. Square pad is the + lead."""
    return Footprint(
        "CP radial D5 P2.0",
        (
            Pad("1", 0.0, 0.0, 1.6, 1.6, 0.8, "rect"),
            Pad("2", 2.0, 0.0, 1.6, 1.6, 0.8),
        ),
        (Body((-1.5, -2.5, 3.5, 2.5, 0.0, 7.5)),),
    )


def axial_resistor() -> Footprint:
    """1/4 W on 10.16 mm, lying flat."""
    return Footprint(
        "R axial 0207 P10.16",
        (
            Pad("1", 0.0, 0.0, 1.6, 1.6, 0.8),
            Pad("2", 10.16, 0.0, 1.6, 1.6, 0.8),
        ),
        (Body((1.93, -1.25, 8.23, 1.25, 0.0, 2.6)),),
    )


def upright_resistor() -> Footprint:
    """1/4 W stood on end on 2.54 mm: the body over pin 1, its far lead bent over.

    Only the body is a box here. The lead that comes back down to pin 2 is bare
    wire a few tenths across, which nothing on this board has to keep clear of.
    """
    return Footprint(
        "R axial 0207 P2.54 vertical",
        (
            Pad("1", 0.0, 0.0, 1.6, 1.6, 0.8),
            Pad("2", 2.54, 0.0, 1.6, 1.6, 0.8),
        ),
        (Body((-1.4, -1.4, 1.4, 1.4, 0.0, 9.5)),),
    )


# WHERE THE BEC'S FOUR PINS ARE, AND HOW WELL THAT IS KNOWN. The module carries
# four plated holes on one 24 mm edge -- IN, G, G, OUT, reading down its
# photograph -- and Matek publish no drawing of them. The 3.81 mm pitch is
# dimensioned on that photograph; the row's 2.5 mm inset from that edge and OUT's
# 2.7 mm from the long edge are scaled off the same picture and are the softest
# numbers on this board. MEASURE ONE BEFORE THE BOARD IS ORDERED: a row 1 mm out
# is a module that will not go onto its pins, and unlike the tie holes there is
# no slack anywhere to take it up.
BEC_PIN_PITCH = 3.81
BEC_PIN_INSET = 2.5
BEC_PIN_END = 2.7
# WHERE THE TWO STRAPS CROSS THE MODULE, measured from its centre along its long
# axis. THIS WAS 12.0 AND IT CHOKED THE MODULE'S OWN PINS. The pin column stands
# 15.0 from the centre and its pads are 1.7 across, so a Ø3 tie hole at 12.0
# leaves 12.65 - 12.0 = 0.65 mm of laminate between the hole and the pad copper
# -- less than one 0.25 mm track and its clearance, so the two live pins had to
# escape north, south or east and the router paid for it all the way across the
# board. At 10.0 there are 2.65 mm there, which is two tracks, and the board
# comes out 13 mm of copper and seven vias lighter for a change that moves
# nothing anybody can see.
#
# IT IS NOT A VENDOR DIMENSION. Matek publish no hole pattern at all -- see the
# footprint below -- so where the straps cross is ours to choose, and the only
# thing it has to do is hold a 35 mm module down on a sheet. 10.0 puts them
# 20 mm apart and 7.5 mm in from each end, against 24 and 5.5 before. IT ALSO
# BUYS BACK THE TIGHTEST MECHANICAL GAP ON THIS BOARD: the outboard strap stood
# 1.20 mm from the SBC's microSD socket, which hangs over it, and stands 3.20 mm
# from it now.
BEC_TIE_X = 10.0


def bec_module() -> Footprint:
    """The Matek BEC12S-PRO flat on a thermal sheet, COMPONENT SIDE UP, on pins.

    WHICH WAY UP IT LIES IS DECIDED HERE, and it was not decided before: this was
    drawn as a featureless brick, and a brick has no sides. It is a bare 35 x 24
    PCB with a shielded inductor, a diode and a switching FET standing most of its
    5.5 mm on one face and nothing but laminate on the other. THE LAMINATE FACE
    GOES DOWN, on the sheet. Turning it over was tried and taken off again: the
    only thing it buys is a flat back for the cable ties to bear on, and what it
    costs is the whole reason the sheet is there. Face down, the sheet touches the
    inductor and the diode and nothing else, with the rest of a 3 W regulator
    standing in a closed pocket 3 mm under the SBC. Face up, the sheet takes the
    module's whole 35 x 24 back, which is 700-odd mm2 of contact through 1.6 mm of
    laminate that has copper planes in it, and the parts themselves are in the air
    under the SBC rather than facing the board. THE CABLE TIES BEAR ON THE PARTS,
    and that is the price: each strap lands on whatever is tallest in its lane,
    which on the outboard lane is the inductor's steel can. Keep them snug and not
    tight.

    ITS FOUR PADS THEN FACE UP, which is what makes the pins work. Four pins stand
    out of this board, the module drops over them through the sheet's cut edge,
    and they are soldered at the module's own rings on top where a joint can be
    seen. SOLDER THEM FROM UNDER THIS BOARD, not on top: the module's back lies
    1 mm off the copper here and a fillet on the top face would hold it off the
    sheet.

    NO VENDOR HOLE PATTERN EXISTS to screw it by, so it is not screwed at all.
    Four Ø3 holes take two 2.5 mm ties across its short axis, inboard of the pins,
    and each tie's head is what goes under the board -- 2.4 mm of the 3 mm the
    standoffs leave. That is the whole reason the ties are 2.5 mm and not 4.

    35 x 24 x 5.5 is cad/electronics.py's becWidth, becDepth and becHeight, which
    are catalogue figures. Measure the part when it arrives: the tie holes are
    drilled to the catalogue and a module 2 mm wider than the catalogue says will
    not sit between them.
    """
    # Seen from above, the right way up: the pin row is on the +x edge and OUT is
    # the +y end of it, which is Matek's photograph turned half round and NOT
    # mirrored. Half round because that is what puts the input pin nearest the
    # fuse that feeds it and the output pin nearest the bulk it charges.
    pads = tuple(
        Pad(
            str(n),
            17.5 - BEC_PIN_INSET,
            12.0 - BEC_PIN_END - BEC_PIN_PITCH * (4 - n),
            1.7,
            1.7,
            1.0,
            "rect" if n == 1 else "circle",
        )
        for n in (1, 2, 3, 4)
    )
    return Footprint(
        "Matek BEC12S-PRO on a sheet, on pins",
        pads,
        (
            # The sheet stops short of the pin row rather than being pierced four
            # times by it. The module overhangs it there by 5 mm, 1 mm over copper
            # and over four joints that are made from underneath.
            Body((-17.5, -12.0, 12.5, 12.0, 0.0, 1.0), "thermal sheet"),
            # One body for the module, but two things in it: its own laminate is
            # the 1.6 above the sheet, and its parts stand from 2.6 to 6.5.
            Body((-17.5, -12.0, 17.5, 12.0, 1.0, 6.5), "BEC"),
            # Two straps and not a lid over the whole module: drawn as one slab
            # it fouled the SBC's microSD socket, which hangs 7.8 mm over this
            # board. 2.5 mm of strap, in 2 mm of height to lie loose in. They
            # cross the module's parts, which is what lying the right way up
            # costs: the outboard strap lands on the inductor's can.
            Body(
                (-BEC_TIE_X - 1.25, -14.5, -BEC_TIE_X + 1.25, 14.5, 6.5, 8.5),
                "cable tie",
            ),
            Body(
                (BEC_TIE_X - 1.25, -14.5, BEC_TIE_X + 1.25, 14.5, 6.5, 8.5),
                "cable tie",
            ),
        ),
        tuple((dx, dy, 3.0) for dx in (-BEC_TIE_X, BEC_TIE_X) for dy in (-13.6, 13.6)),
    )


# THE BUS MONITOR'S HEADER SITS 2.5 mm IN FROM ITS OWN EDGE, which is the one
# number about this module that cad/electronics.py does not carry: nothing in the
# torso depended on it until this board started landing the module on its pins.
# Scaled off the vendor's photographs like the rest of that block, and unmeasured
# like the rest of it. The column of four large holes is on the OPPOSITE edge.
BUS_MONITOR_HEADER_INSET = 2.5


def ina226_module() -> Footprint:
    """The INA226 breakout on two M2 standoffs, landed on all eight of its pins.

    THE ONLY PART OF THIS BOARD THAT NEEDS MORE THAN 10 mm OF AIR, which is why
    it is at this end of the carrier and not somewhere more convenient: 8 mm of
    module on 3 mm standoffs is 11, and 10 mm is all the SBC leaves anywhere it
    stands over. cad/electronics.py's headroom is what settled that.

    ALL EIGHT PINS COME DOWN INTO THIS BOARD -- VCC, GND, SDA, SCL, ALE, VBS, IN-
    and IN+, in that order down the column, off the vendor's own photograph of the
    silkscreen. It was drawn as five pads on a header standing 3 mm outboard of
    the module, and that was wrong twice over: a module's pins cannot reach a
    header beside it, so it needed five flying wires nobody had drawn, and that
    header was on the same edge as the module's four large holes -- which is the
    opposite edge from the one its pins are on. Landed on all eight it plugs in,
    and its two mounting holes come down on the two M2 standoffs instead of near
    them.

    ITS SCREW TERMINALS ARE LEFT EMPTY, and IN+ and IN- -- which are on the
    header too -- go to ground on this board. They took a twisted pair from the
    main bus shunt on J7 until that shunt went with the current measurement on
    2026-09-16; since 2026-10-07 J7 is the power switch board's hold lead and the
    two inputs are tied down rather than left to float.

    THE MODULE CARRIES ITS OWN 0.1 OHM SHUNT between those two pins. With both of
    them at ground it carries nothing and can stay on.

    The two mounting holes are the outer pair of the four in the board's own
    column -- busSenseHolePitch 16.7, busSenseHoleInset 2.5, both read off the
    vendor's photographs and neither measured.
    """
    # Pin 1 at the rear, pin 8 at the front. IN+ and IN- came out of the end
    # nearest the shunt's plug while there was one; they go to ground now.
    span = PITCH * 7
    pads = tuple(
        Pad(
            str(n),
            -11.0 + BUS_MONITOR_HEADER_INSET,
            PITCH * (n - 1) - span / 2,
            1.7,
            1.7,
            1.0,
            "rect" if n == 1 else "circle",
        )
        for n in range(1, 9)
    )
    return Footprint(
        "INA226 breakout on standoffs, on a 1 x 8",
        pads,
        (
            Body((-11.0, -11.0, 11.0, 11.0, 0.0, 3.0), "standoffs"),
            Body((-11.0, -11.0, 11.0, 11.0, 3.0, 11.0), "bus monitor"),
        ),
        tuple(
            (11.0 - e.busSenseHoleInset, dy, 2.4)
            for dy in (-e.busSenseHolePitch / 2, e.busSenseHolePitch / 2)
        ),
    )


def radial_ptc() -> Footprint:
    """A resettable fuse on 5.08 mm leads, standing on the bus feed.

    THE BODY IS THE RXEF185'S OWN, 2026-10-07: a 17.5 mm disc, 3.0 mm thick and
    22.4 mm tall seated, the distributors' figures for Littelfuse's part. It was
    drawn 12.1 wide and 13 tall until an outside review held it against the
    listing; the thickness keeps the 3.6 it had, for the leads' kink.
    """
    return Footprint(
        "PTC radial P5.08",
        (
            Pad("1", 0.0, 0.0, 1.8, 1.8, 1.0, "rect"),
            Pad("2", 5.08, 0.0, 1.8, 1.8, 1.0),
        ),
        (Body((2.54 - 8.75, -1.8, 2.54 + 8.75, 1.8, 0.0, 22.4)),),
    )


def wire_link_3() -> Footprint:
    """Three holes on 2.54 mm for a wire link across 1-2 or 2-3.

    carrier.py drew JP1 as a solder bridge, which is copper and not a part. On a
    through-hole board the same choice is a wire link, soldered once when the
    IMU in hand has been read.
    """
    return Footprint(
        "wire link 1x3",
        tuple(Pad(str(n), 2.54 * (n - 1), 0.0, 1.6, 1.6, 0.8) for n in (1, 2, 3)),
        (Body((-0.8, -0.8, 5.88, 0.8, 0.0, 1.5)),),
    )


# THE CORE BOARD, and which row of a header carries its odd pins is settled.
# WeAct's board-shape drawing gives the four rows and the twelve columns but not
# that; their pin-label drawing of the same board does. Each column there carries
# two port names, one line above the other, and six of those pairs are pins this
# netlist already numbers: B12/B13 are P1-5 and P1-6, A11/A12 are P1-13 and
# P1-14, B4/B5 are P1-19 and P1-20, B6/B7 are P1-21 and P1-22, B8 is P1-23 and
# B15 is P1-8. In every one of them the EVEN pin is the name on the upper line.
# NRST -- P2-19, the odd pin the whole question turned on -- is on the lower line
# of the top header, which agrees. So the odd pins are on the row printed LOWER
# in each header, and because the two headers face opposite edges that is P1's
# OUTER row and P2's INNER row, which is what the footprint below builds.
WEACT_W = 36.28
WEACT_D = 28.14
WEACT_FIRST_COLUMN = 6.97
WEACT_ROW_INSET = 1.37
WEACT_INNER_ROWS = 20.32
PITCH = 2.54
# Standard 2.54 mm female header, 8.5 mm tall, and the 2.5 mm plastic collar on
# the core board's own male pins: the core board's underside is 11 mm up. Its
# own underside parts -- the SOIC-8 flash is the tallest -- are allowed 1.8 mm.
SOCKET_HEIGHT = 8.5
COLLAR_HEIGHT = 2.5
WEACT_UNDERSIDE_PARTS = 1.8
WEACT_TOP_PARTS = 3.5
WEACT_USB_OVERHANG = 0.25


def weact_on_sockets() -> Footprint:
    """The core board on two 2 x 12 sockets, in its own frame, as WeAct draw it.

    Centred on the board's outline, USB-C on the left, P1 along the bottom edge.
    """
    left = -WEACT_W / 2
    bottom = -WEACT_D / 2
    pads = []
    for header, odd_row, even_row in (
        ("P1", WEACT_ROW_INSET, WEACT_ROW_INSET + PITCH),
        (
            "P2",
            WEACT_ROW_INSET + PITCH + WEACT_INNER_ROWS,
            WEACT_ROW_INSET + 2 * PITCH + WEACT_INNER_ROWS,
        ),
    ):
        for column in range(12):
            x = left + WEACT_FIRST_COLUMN + PITCH * column
            for number, row in ((2 * column + 1, odd_row), (2 * column + 2, even_row)):
                pads.append(
                    Pad(
                        f"{header}-{number}",
                        x,
                        bottom + row,
                        1.7,
                        1.7,
                        1.0,
                        "rect" if number == 1 else "circle",
                    )
                )
    first = left + WEACT_FIRST_COLUMN - PITCH / 2
    last = left + WEACT_FIRST_COLUMN + PITCH * 11 + PITCH / 2
    bodies = []
    for low, high in (
        (bottom + WEACT_ROW_INSET - PITCH / 2, bottom + WEACT_ROW_INSET + 1.5 * PITCH),
        (
            -bottom - WEACT_ROW_INSET - 1.5 * PITCH,
            -bottom - WEACT_ROW_INSET + PITCH / 2,
        ),
    ):
        bodies.append(Body((first, low, last, high, 0.0, SOCKET_HEIGHT), "socket"))
        bodies.append(
            Body(
                (first, low, last, high, SOCKET_HEIGHT, SOCKET_HEIGHT + COLLAR_HEIGHT),
                "pin collar",
            )
        )
    underside = SOCKET_HEIGHT + COLLAR_HEIGHT
    bodies.append(
        Body(
            (
                left,
                bottom,
                -left,
                -bottom,
                underside - WEACT_UNDERSIDE_PARTS,
                underside,
            ),
            "core board underside",
        )
    )
    bodies.append(
        Body(
            (
                left - WEACT_USB_OVERHANG,
                bottom,
                -left,
                -bottom,
                underside,
                underside + e.pcbThickness + WEACT_TOP_PARTS,
            ),
            "core board",
        )
    )
    return Footprint("WeAct core board on 2 x 2x12 sockets", tuple(pads), tuple(bodies))


# ---- placement ---------------------------------------------------------------------


@dataclass(frozen=True)
class Placed:
    refdes: str
    footprint: Footprint
    x: float
    y: float
    rotation: int = 0  # degrees anticlockwise, seen from above

    def at(self, px: float, py: float) -> tuple[float, float]:
        """A point in the footprint's frame, on the board."""
        c = round(math.cos(math.radians(self.rotation)))
        s = round(math.sin(math.radians(self.rotation)))
        return (self.x + px * c - py * s, self.y + px * s + py * c)

    def un(self, bx: float, by: float) -> tuple[float, float]:
        """The reverse of at(): a point on the board, in the footprint's frame.

        A footprint is written out with its own geometry at its own offsets, so
        anything measured against the whole board -- a silkscreen line clipped
        against the part next door -- has to come back into the part's frame
        before it is written.
        """
        c = round(math.cos(math.radians(self.rotation)))
        s = round(math.sin(math.radians(self.rotation)))
        dx, dy = bx - self.x, by - self.y
        return (dx * c + dy * s, -dx * s + dy * c)

    def pads(self) -> list[tuple[Pad, float, float, float, float]]:
        """(pad, x, y, w, h) on the board, sizes swapped for a quarter turn."""
        placed = []
        for pad in self.footprint.pads:
            x, y = self.at(pad.x, pad.y)
            w, h = (pad.h, pad.w) if self.rotation % 180 else (pad.w, pad.h)
            placed.append((pad, x, y, w, h))
        return placed

    def holes(self) -> list[tuple[float, float, float]]:
        """Every drilled hole that is not a pin, on the board."""
        return [(*self.at(hx, hy), d) for hx, hy, d in self.footprint.holes]

    def boxes(self) -> list[tuple[Body, tuple[float, ...]]]:
        """Every body as an axis-aligned box on the board."""
        placed = []
        for body in self.footprint.bodies:
            x0, y0, x1, y1, z0, z1 = body.box
            ax, ay = self.at(x0, y0)
            bx, by = self.at(x1, y1)
            placed.append(
                (body, (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by), z0, z1))
            )
        return placed


# WHERE THE CORE BOARD SITS is cad/electronics.py's weActX, which centres it in
# the larger of the two pieces the SBC's posts cut this board into. That figure
# is its envelope's centre, and the envelope carries the USB-C connector's
# quarter millimetre of overhang, so the board's own outline is that much off it.
#
# IT IS TURNED HALF ROUND from how WeAct draw it, so that P1 -- which carries
# every signal this board uses bar reset -- faces the front edge where the SBC,
# IMU and bus monitor connectors are. The cost is the SWD header, which then
# points at the left-hand wall 3.8 mm away; nothing here needs it in place,
# because the SBC reflashes the MCU over J5, and a socketed core board comes out.
#
# IN y IT IS CENTRED, which is 2 mm aft of where cad/electronics.py draws it.
# Centred is what leaves 2.6 mm between its outline and the connector rows at
# both edges, so that a plug can be pulled without catching the core board.
WEACT_X = e.weActX - ORIGIN_X - WEACT_USB_OVERHANG / 2
WEACT_Y = BOARD_D / 2

FOOTPRINTS = {
    "A1": weact_on_sockets(),
    "A2": bec_module(),
    "A3": ina226_module(),
    "U": dip8_socket(),
    "C": radial_mlcc(),
    "C1": radial_electrolytic(),
    "C9": radial_electrolytic(),
    "R": upright_resistor(),
    "F1": radial_ptc(),
    "JP1": wire_link_3(),
}


def _fp(refdes: str) -> Footprint:
    if refdes in FOOTPRINTS:
        return FOOTPRINTS[refdes]
    if refdes.startswith("J"):
        part = next(p for p in carrier.PARTS if p.refdes == refdes)
        return xh_top_entry(len(part.pins))
    return FOOTPRINTS[refdes[0]]


# WHERE EVERYTHING SITS, AND WHY IT SITS THERE. Three things decide this board
# and nothing else gets a vote.
#
# 1. THE SBC LEAVES 10 mm OF AIR over everything between x 40 and x 105, and a
#    mated JST-XH plug is 9.8 mm tall with its wires still to leave. So every
#    connector is on one of the two edges, outboard of the SBC's own front and
#    rear edges, and so is anything else taller than the SBC's underside: the
#    core board on its sockets, the bus monitor on its standoffs, the two
#    pull-ups and the fuse.
# 2. THE SBC STANDS ON THIS BOARD, on four standoffs in two pairs at x 43.55 and
#    x 101.55, 23 mm apart. Each pair is a bollard 6.8 mm across with a 16.2 mm
#    gate in the middle of it, so nothing wider than that gate crosses either
#    pair. That is why the BEC is between the two pairs, the monitor outboard
#    of the right-hand one, and the core board outboard of the left-hand one.
# 3. WHAT COMES UP THROUGH THE DECK COMES UP AT THE REAR, through cad/deck.py's
#    34 mm chase at x 82.55 to 116.55 in this frame, which is the whole reason
#    this layout was redone: the connectors used to be at the far outboard end
#    and the loom crossed the torso to reach them. THIS SAID "THE THREE BUS
#    CONNECTORS SIT OVER IT" and two of them do: bus C's is 2 mm short of the
#    chase's western end and the IMU's is 24 mm short of it, so those two looms
#    are dressed westward under the board after they come up. check_leads_down()
#    measures it against the deck solid on every run rather than leaving it to a
#    comment, which is how the claim survived unexamined in the first place.
#
# The front edge carries what goes UP rather than down -- the SBC's own cable,
# the bus feed that comes through a second opening in the deck over the power
# bay, and since 2026-10-07 the power switch board's hold lead.
REAR_ROW_Y = 3.0
FRONT_ROW_Y = BOARD_D - 3.0

PLACEMENT = {
    # The core board, outboard of the left-hand posts, where there are 16 mm of
    # air. Turned half round so P1 -- every signal but reset -- faces inboard.
    "A1": (WEACT_X, WEACT_Y, 180),
    # NOTHING STANDS BETWEEN THE LEFT-HAND STANDOFFS. A DIP-8 fits there and one
    # was there, and it cost more than it was worth: eighteen nets have to cross
    # that pair to get from the core board to the rest of the board, and a
    # transceiver standing in the gate left two slots of 2 mm. Four nets could
    # not be routed at all. It is a corridor, and it was 2.8 mm narrower again
    # when the deck's posts came up through here instead of standoffs.
    # The BEC, flat between the two pairs of standoffs, component side up. Its
    # four pins stand out of the board under its inboard end, on the side the
    # fuse and the transceivers are.
    "A2": (66.5, 23.0, 0),
    # Bus B's and bus A's transceivers, stacked against the right-hand posts with
    # their own decoupling in the column beside them.
    "U2": (90.0, 12.0, 0),
    "U3": (90.0, 23.0, 0),
    "U1": (90.0, 34.0, 0),
    # The bus monitor, outboard of the right-hand posts: 11 mm tall on standoffs,
    # and this is the only clear patch of board with the air for it.
    "A3": (126.0, 22.0, 0),
    # The rear edge, left to right: the IMU, then the three buses over the chase.
    "J6": (58.0, REAR_ROW_Y, 180),
    "J4": (83.0, REAR_ROW_Y, 180),
    "J3": (99.0, REAR_ROW_Y, 180),
    "J2": (115.0, REAR_ROW_Y, 180),
    # The front edge: the SBC's cable under its own 40-pin header, and the bus
    # feed where the deck's second opening brings it up over the power bay.
    "J5": (56.0, FRONT_ROW_Y, 0),
    "J1": (110.0, FRONT_ROW_Y, 0),
    # THE POWER SWITCH BOARD'S HOLD LEAD, 2026-10-07, at the front edge in front
    # of the core board, where the strip between its header and the edge was
    # empty. Pin 2 stands straight in front of P1-7, the button's pin, and pin
    # 1's track runs left to P1-17, away from it, so the two never cross.
    # Its plug's 9.8 mm clears the core board's own edge by 2 mm. This number was
    # the shunt's sense pair until then, a two-pin plug in the channel beside the
    # monitor; the shunt went on 2026-09-16 and so has that plug.
    "J7": (21.0, FRONT_ROW_Y, 0),
    # The bus feed's own hardware, in the outboard strip where the fuse's height
    # is not under the SBC. THE FUSE CAME 6.4 mm BACK FROM THE FRONT EDGE AND 1.3
    # INBOARD on 2026-10-07, when it was drawn at the RXEF185's real 17.5 mm
    # across: at the edge it stood 2.7 mm from the mounting hole where 4 is
    # wanted. The can it feeds took the front-edge spot instead.
    "F1": (120.7, 36.6, 0),
    "C9": (125.0, 43.0, 0),
    # Bulk on the 5 V rail, at the SBC's cable, which is the load that takes most
    # of it. It sat by the BEC's old header; the BEC's output pin is under the
    # module now and there is nothing standing beside it to put a can on.
    "C1": (81.0, 43.0, 0),
    # A pair of 100 nF at each transceiver, VDD then VIO. THE DISTANCE FROM THE
    # PIN IS THE WHOLE POINT OF A DECOUPLER, so each of these six was put where
    # it is by searching the board for the nearest position that breaks no rule
    # and then keeping the move only if every net still routed. What that
    # arrived at, live pad to the pin it bypasses:
    #
    #   C4  U2 VDD   2.9 mm      C5  U2 VIO   3.0 mm      C7  U3 VIO   2.5 mm
    #   C2  U1 VDD   8.8 mm      C3  U1 VIO  11.7 mm      C6  U3 VDD  10.8 mm
    #
    # THE THREE THAT ARE STILL FAR OFF ARE FAR OFF FOR ONE REASON: the BEC lies
    # across the whole flank west of this column, from y 11 to y 35, and VDD is
    # pin 3 -- on the sockets' west side. Only U2's VDD pin escapes it, because
    # U2 is the southernmost socket and there is 2 mm of board south of the BEC's
    # corner.
    #
    # C2 HAS A LEGAL STATION 4.6 mm FROM ITS PIN and cannot have it. It is in the
    # channel between the BEC's outboard strap and U1, and putting a capacitor
    # there costs the MCU's reset line and the I2C data line their route -- that
    # channel and the strip east of the column are the only two ways past this
    # block of parts, and the I2C bus, the SBC's serial link and bus A all need
    # them. IT WAS TRIED TWICE: once when the straps stood at 12.0 and the
    # channel was 5.2 mm, and again after they came in to 10.0 and it was 8.2,
    # and the second attempt failed on the same two nets as the first. Standing
    # off and relying on the plane for the return is the lesser evil, and it is
    # the answer this board gives rather than a good one.
    #
    # THE WHOLE COLUMN WAS OFFERED 2 mm OF ROOM TO THE EAST as well, at x 91 and
    # x 92, with all six capacitors re-searched against the new stations. Both
    # cost the I2C bus its route to the monitor. The strip east of this column is
    # not spare board: it is the corridor.
    #
    # THE TWO SLOTS BETWEEN THE THREE SOCKETS ARE LEFT OPEN. They are 1.78 mm of
    # copper each and they are the only way across this column for anything that
    # has to reach the monitor, so a capacitor standing in one costs three nets
    # their route as surely as one in the channel does.
    "C2": (86.0, 41.5, 0),
    "C3": (91.0, 41.5, 0),
    "C6": (97.0, 22.5, 0),
    "C7": (96.3, 19.2, 0),
    "C4": (83.7, 9.2, 180),
    "C5": (96.8, 8.2, 90),
    # 3.3 V decoupling at the monitor's own supply pin, which is at the rear end
    # of its header now, and the two I2C pull-ups, which belong to the bus rather
    # than to either sensor and stay where there is room for a 9.5 mm resistor
    # outboard of the SBC.
    "C8": (110.0, 13.0, 0),
    "R1": (109.5, 18.0, 180),
    "R2": (113.0, 18.0, 0),
    # The IMU's supply link, in the rear strip beside its connector.
    "JP1": (24.0, 4.0, 0),
}


def placed() -> list[Placed]:
    return [
        Placed(refdes, _fp(refdes), *PLACEMENT[refdes]) for refdes in sorted(PLACEMENT)
    ]


def net_of_pads(parts: list[Placed]) -> dict[tuple[str, str], str]:
    """Every pad's net, and a name of its own for a pin on no net at all."""
    net_of = {
        endpoint: net
        for net, endpoints in carrier.NETS.items()
        for endpoint in endpoints
    }
    return {
        (part.refdes, pad.name): net_of.get(
            (part.refdes, pad.name), f"~{part.refdes}-{pad.name}"
        )
        for part in parts
        for pad in part.footprint.pads
    }


# ---- routing -------------------------------------------------------------------------


@dataclass(frozen=True)
class Track:
    net: str
    layer: str  # "top" or "bottom"
    points: tuple[tuple[float, float], ...]
    width: float = TRACK


@dataclass(frozen=True)
class Via:
    net: str
    x: float
    y: float


def top(net: str, *points, width: float = TRACK) -> Track:
    return Track(net, "top", tuple(points), width)


def bot(net: str, *points, width: float = TRACK) -> Track:
    return Track(net, "bottom", tuple(points), width)


# ---- the router ----------------------------------------------------------------
#
# WHY THIS IS A PROGRAM AND NOT A TABLE OF COORDINATES. The 76 mm board was hand
# routed, and that was reasonable for what it was. This one is 140 mm with six
# more parts on it, four posts through it, and a netlist that moves whenever a
# module does; a table of two hundred hand-typed vertices would be a table
# nobody dares change. So the tracks are searched for instead, on a 0.2 mm grid,
# and then held to exactly the checks the hand-routed ones were held to: the
# copper the router lays down is measured for clearance against every other net
# and put through the same short-and-open test. A router that cheats still fails.
#
# It is a plain A* maze router with a via cost and a bend cost, routing one net
# at a time into a growing tree, in an order that lays the wide rails first
# because they are the ones with nowhere else to go. A net that fails is retried
# once after everything else is down, and anything still unrouted is a fault
# rather than a silence.
#
# GROUND IS NOT ROUTED. It is poured on both layers, as it was, and stitched
# between them by the vias placed at the end.

GRID = 0.2
VIA_COST = 6.0
# How much slack the grid itself needs on top of the clearance. The router works
# on cell centres and the copper is a polyline through them, so a track's real
# edge stands off its cells by a fraction of a cell at every bend and every
# diagonal. Measured rather than reasoned: at half a cell the drawn copper came
# out 0.15 to 0.19 mm apart where 0.20 was wanted, and at three quarters it does
# not. The check on the drawn geometry is what settles this, not this comment.
GRID_MARGIN = 0.15
BEND_COST = 1.0
DIAGONAL = math.sqrt(2.0)

# What each net is drawn at.
NET_WIDTH = {"+5V": 0.6, "+3V3": 0.5, "VBAT": 0.5, "VBAT_F": 0.5}
LAYER_INDEX = {"top": 0, "bottom": 1}


def net_width(net: str) -> float:
    return NET_WIDTH.get(net, TRACK)


def _grid_shape() -> tuple[int, int]:
    return int(round(BOARD_W / GRID)) + 1, int(round(BOARD_D / GRID)) + 1


def _disc(radius: float) -> list[tuple[int, int]]:
    reach = int(math.ceil(radius / GRID))
    return [
        (dx, dy)
        for dx in range(-reach, reach + 1)
        for dy in range(-reach, reach + 1)
        if math.hypot(dx, dy) * GRID <= radius + GRID / 2
    ]


class Board:
    """The grid the router works on: which net owns which cell, on each layer."""

    def __init__(self, parts: list[Placed]) -> None:
        import numpy as np

        self.np = np
        self.nx, self.ny = _grid_shape()
        xs = np.arange(self.nx) * GRID
        ys = np.arange(self.ny) * GRID
        self.gx, self.gy = np.meshgrid(xs, ys, indexing="ij")
        # How far each grid point is from anything copper may never touch: the
        # board's edge, a mounting hole's washer, an SBC standoff, a drilled
        # hole.
        self.fixed = np.minimum.reduce(
            [self.gx, self.gy, BOARD_W - self.gx, BOARD_D - self.gy]
        )
        for mx, my in MOUNTS:
            self.fixed = np.minimum(
                self.fixed, np.hypot(self.gx - mx, self.gy - my) - MOUNT_COPPER_KEEPOUT
            )
        for px, py in STANDOFFS:
            self.fixed = np.minimum(
                self.fixed,
                np.hypot(self.gx - px, self.gy - py) - STANDOFF_COPPER_KEEPOUT,
            )
        self.own = {
            layer: np.full((self.nx, self.ny), -1, dtype=np.int32) for layer in LAYERS
        }
        self.nets: list[str] = []
        self.index: dict[str, int] = {}
        nets = net_of_pads(parts)
        # How far each grid point is from the nearest DRILLED hole's edge. A via
        # is a hole too, and a hole that breaks into another one is scrap
        # whatever net either of them is on -- which is the case the clearance
        # test above cannot see, because a ground via beside a ground pad has no
        # clearance to violate.
        self.drills = np.full_like(self.fixed, 1e3)
        for mx, my in MOUNTS:
            self.drills = np.minimum(
                self.drills, np.hypot(self.gx - mx, self.gy - my) - e.m3Clearance / 2
            )
        for px, py in STANDOFFS:
            self.drills = np.minimum(
                self.drills,
                np.hypot(self.gx - px, self.gy - py) - e.sbcStandoffHole / 2,
            )
        for part in parts:
            for pad, x, y, w, h in part.pads():
                net = nets[(part.refdes, pad.name)]
                radius = math.hypot(w, h) / 2 if pad.shape == "rect" else max(w, h) / 2
                for layer in LAYERS:
                    self.stamp(layer, x, y, radius, self.id(net))
                self.drills = np.minimum(
                    self.drills,
                    np.hypot(self.gx - x, self.gy - y) - pad.drill / 2,
                )
            for hx, hy, diameter in part.holes():
                self.fixed = np.minimum(
                    self.fixed,
                    np.hypot(self.gx - hx, self.gy - hy) - diameter / 2,
                )
                self.drills = np.minimum(
                    self.drills,
                    np.hypot(self.gx - hx, self.gy - hy) - diameter / 2,
                )

    def id(self, net: str) -> int:
        if net not in self.index:
            self.index[net] = len(self.nets)
            self.nets.append(net)
        return self.index[net]

    def cell(self, x: float, y: float) -> tuple[int, int]:
        return int(round(x / GRID)), int(round(y / GRID))

    def stamp(self, layer: str, x: float, y: float, radius: float, owner: int) -> None:
        cx, cy = self.cell(x, y)
        grid = self.own[layer]
        for dx, dy in _disc(radius):
            ix, iy = cx + dx, cy + dy
            if 0 <= ix < self.nx and 0 <= iy < self.ny:
                grid[ix, iy] = owner

    def mark(self, layer: str, points, owner: int, width: float) -> None:
        """Stamp a whole polyline, not just its corners."""
        # A wide net is stamped wider than it is, by the amount it is wider
        # than a signal: the margin on the query above is the routing net's, so
        # without this a signal keeps a signal's distance from a rail.
        radius = width / 2 + max(0.0, (width - TRACK) / 2)
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            steps = max(1, int(math.dist((ax, ay), (bx, by)) / GRID) + 1)
            for i in range(steps + 1):
                f = i / steps
                self.stamp(layer, ax + (bx - ax) * f, ay + (by - ay) * f, radius, owner)

    def forbidden(self, owner: int, width: float, drilled: bool = False):
        """Cells this net may not put the centre of a track on, per layer.

        With `drilled`, the cell has to take a HOLE as well as copper, so every
        other drilled hole on the board is kept away from it by HOLE_TO_HOLE --
        the one rule that does not care whose net it is.
        """
        np = self.np
        offsets = _disc(width / 2 + CLEARANCE + GRID_MARGIN)
        out = {}
        for layer in LAYERS:
            taken = (self.own[layer] >= 0) & (self.own[layer] != owner)
            blocked = np.zeros_like(taken)
            for dx, dy in offsets:
                shifted = np.zeros_like(taken)
                x0, x1 = max(0, dx), min(self.nx, self.nx + dx)
                y0, y1 = max(0, dy), min(self.ny, self.ny + dy)
                shifted[x0:x1, y0:y1] = taken[x0 - dx : x1 - dx, y0 - dy : y1 - dy]
                blocked |= shifted
            blocked |= self.fixed < (width / 2 + EDGE_CLEARANCE + GRID / 2)
            if drilled:
                blocked |= self.drills < (VIA_DRILL / 2 + HOLE_TO_HOLE + GRID / 2)
            out[layer] = blocked
        return out


def _search(board: Board, blocked, via_blocked, sources, target):
    """A* from any cell of the net's tree to one pad centre, over both layers."""
    import heapq

    tx, ty = target
    names = ("top", "bottom")
    best: dict[tuple[int, int, int], float] = {}
    came: dict[tuple[int, int, int], object] = {}
    heap: list = []
    for sx, sy, layer in sources:
        key = (sx, sy, LAYER_INDEX[layer])
        if key not in best:
            best[key] = 0.0
            heapq.heappush(heap, (abs(sx - tx) + abs(sy - ty), 0.0, key, None))
    steps = (
        (1, 0, 1.0),
        (-1, 0, 1.0),
        (0, 1, 1.0),
        (0, -1, 1.0),
        (1, 1, DIAGONAL),
        (1, -1, DIAGONAL),
        (-1, 1, DIAGONAL),
        (-1, -1, DIAGONAL),
    )
    while heap:
        _, cost, key, parent = heapq.heappop(heap)
        if key in came:
            continue
        came[key] = parent
        ix, iy, il = key
        if (ix, iy) == (tx, ty):
            path = []
            walk = key
            while walk is not None:
                path.append(walk)
                walk = came[walk]
            return list(reversed(path))
        layer = names[il]
        for dx, dy, step in steps:
            jx, jy = ix + dx, iy + dy
            if not (0 <= jx < board.nx and 0 <= jy < board.ny):
                continue
            if blocked[layer][jx, jy]:
                continue
            if dx and dy:
                if blocked[layer][ix + dx, iy] or blocked[layer][ix, iy + dy]:
                    continue
            move = cost + step
            if parent is not None and parent[2] == il:
                if (ix - parent[0], iy - parent[1]) != (dx, dy):
                    move += BEND_COST
            nkey = (jx, jy, il)
            if move < best.get(nkey, 1e18) - 1e-9:
                best[nkey] = move
                heapq.heappush(
                    heap, (move + abs(jx - tx) + abs(jy - ty), move, nkey, key)
                )
        other = 1 - il
        if not (via_blocked[names[other]][ix, iy] or via_blocked[layer][ix, iy]):
            move = cost + VIA_COST
            nkey = (ix, iy, other)
            if move < best.get(nkey, 1e18) - 1e-9:
                best[nkey] = move
                heapq.heappush(
                    heap, (move + abs(ix - tx) + abs(iy - ty), move, nkey, key)
                )
    return None


def _merge(run) -> tuple[tuple[float, float], ...]:
    """A run of grid cells as a polyline, with everything but the bends dropped."""
    points = [run[0]]
    for i in range(1, len(run) - 1):
        ax, ay = run[i - 1]
        bx, by = run[i]
        cx, cy = run[i + 1]
        if (bx - ax, by - ay) != (cx - bx, cy - by):
            points.append((bx, by))
    points.append(run[-1])
    return tuple((x * GRID, y * GRID) for x, y in points)


def _to_geometry(path, net: str, width: float):
    names = ("top", "bottom")
    tracks: list[Track] = []
    vias: list[Via] = []
    run = [(path[0][0], path[0][1])]
    layer = path[0][2]
    for ix, iy, il in path[1:]:
        if il != layer:
            if len(run) > 1:
                tracks.append(Track(net, names[layer], _merge(run), width))
            vias.append(Via(net, run[-1][0] * GRID, run[-1][1] * GRID))
            run = [(ix, iy)]
            layer = il
        else:
            run.append((ix, iy))
    if len(run) > 1:
        tracks.append(Track(net, names[layer], _merge(run), width))
    return tracks, vias


def _nearest_first(points):
    """The pads of one net, ordered so each is the nearest one still left."""
    remaining = sorted(points)
    order = [remaining.pop(0)]
    while remaining:
        nxt = min(
            remaining,
            key=lambda p: min(math.dist(p, q) for q in order),
        )
        remaining.remove(nxt)
        order.append(nxt)
    return order


def _pin_sites(parts: list[Placed]) -> dict[str, list[tuple[float, float]]]:
    nets = net_of_pads(parts)
    sites: dict[str, list[tuple[float, float]]] = {}
    for part in parts:
        for pad, x, y, _, _ in part.pads():
            sites.setdefault(nets[(part.refdes, pad.name)], []).append((x, y))
    return sites


# The wide rails go down first: they are the ones with nowhere else to go, and a
# signal will always find a way round a rail where a rail will not find a way
# round fifteen signals. Putting the two long I2C nets in here as well was tried
# and is not here: it routed both of them and cost five other nets their route.
PASSES = 8
ROUTE_FIRST = ("+5V", "+3V3", "VBAT_F", "VBAT")
# WHAT A VIA IS WORTH IN MILLIMETRES OF TRACK, when two orders both route the
# whole board and the search has to say which it prefers. A via is a drilled
# hole, a plated barrel and two pad lands, and it is the thing on this board most
# likely to be the reason a net has to detour around it later -- so it is not
# free the way a couple of millimetres of copper is. 5 mm means an order only
# earns its via by saving more than 5 mm of track with it.
VIA_COST = 5.0


def _copper(tracks: list[Track], vias: list[Via]) -> float:
    """What a routed board costs, for comparing one pass against another."""
    length = sum(
        math.dist(track.points[i], track.points[i + 1])
        for track in tracks
        for i in range(len(track.points) - 1)
    )
    return length + VIA_COST * len(vias)


def route(parts: list[Placed], report: Report) -> tuple[list[Track], list[Via]]:
    """Every net but ground, searched for on the grid and returned as geometry."""
    board = Board(parts)
    sites = _pin_sites(parts)
    todo = [
        net
        for net, points in sites.items()
        if len(points) > 1 and net != POUR_NET and not net.startswith("~")
    ]

    def span(net: str) -> float:
        xs = [p[0] for p in sites[net]]
        ys = [p[1] for p in sites[net]]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    todo.sort(key=lambda net: (net not in ROUTE_FIRST, span(net)))

    # EVERY ORDER IS TRIED AND THE CHEAPEST IS KEPT, which is not what this did
    # before: it stopped at the first order that routed the whole board, and the
    # first order that works is not the best one. On the placement as it stands,
    # two of the eight orders route everything -- 1968 mm of copper on 92 vias
    # against 2003 on 93 -- and the search takes the first of those. WHICH ORDERS
    # WORK IS NOT PREDICTABLE and moves with the placement: the same eight seeds
    # measured against a slightly different set of stations had a different
    # three of them succeed, spanning five per cent of copper. So the early exit
    # was not picking the best board, it was picking whichever board came first,
    # and it had no way of knowing which that was.
    #
    # WHAT IT COSTS is eight passes' routing time on every run instead of one,
    # which is a couple of minutes. The board is a thing that gets fabricated.
    first: list[str] = []
    best = None
    for attempt in range(PASSES):
        order = [net for net in todo if net in ROUTE_FIRST]
        order += [net for net in first if net in todo and net not in order]
        rest = [net for net in todo if net not in order and net != POUR_NET]
        # After the first two passes the queue is shuffled as well as reordered.
        # Pushing what failed to the front is not enough on its own: the nets
        # that blocked it are still in the same order behind it, so the same
        # board comes back with a different net left out. A seeded shuffle gives
        # a genuinely different pass, and the seed keeps the answer repeatable.
        # EACH ATTEMPT IS SEEDED ON ITS OWN NUMBER and not drawn from one
        # generator walked forward through the loop. That mattered: walked
        # forward, the sequence an attempt sees depends on how many attempts
        # came before it, so the queue this search actually reached was never
        # the one the twenty-four-order measurement found at 1915 mm. Seeded per
        # attempt, attempt n is the same queue every time whatever happened
        # before it, and the measurement and the search are looking at the same
        # thing.
        if attempt and not (attempt == 1 and first):
            random.Random(20260914 + attempt).shuffle(rest)
        order += rest
        board = Board(parts)
        tracks, vias, failures = _one_pass(board, order, sites)
        score = (len(failures), _copper(tracks, vias))
        if best is None or score < best[0]:
            best = (score, board, tracks, vias, failures)
        first = [net for net, _ in failures if net not in ROUTE_FIRST] + first
    _, board, tracks, vias, failures = best
    for net, target in failures:
        report.faults.append(
            f"{net}: no route to the pad at {target[0]:.2f}, {target[1]:.2f}"
        )
    return tracks, vias + _stitching(board, parts, tracks, vias)


def _one_pass(board: Board, order, sites):
    """Route every net once, in this order, onto a bare board."""
    tracks: list[Track] = []
    vias: list[Via] = []
    failures: list[str] = []
    for net in order:
        width = net_width(net)
        owner = board.id(net)
        before = {layer: board.own[layer].copy() for layer in LAYERS}
        blocked = board.forbidden(owner, width)
        via_blocked = board.forbidden(owner, VIA_PAD, drilled=True)
        points = _nearest_first(sites[net])
        tree = [(*board.cell(*points[0]), layer) for layer in LAYERS]
        laid: list[Track] = []
        via_set: list[Via] = []
        failed_at = None
        ok = True
        for target in points[1:]:
            path = _search(board, blocked, via_blocked, tree, board.cell(*target))
            if path is None:
                ok = False
                failed_at = target
                break
            netTracks, netVias = _to_geometry(path, net, width)
            for track in netTracks:
                board.mark(track.layer, track.points, owner, width)
            for via in netVias:
                for layer in LAYERS:
                    board.stamp(layer, via.x, via.y, VIA_PAD / 2, owner)
            laid += netTracks
            via_set += netVias
            for ix, iy, il in path:
                tree.append((ix, iy, LAYERS[il]))
            blocked = board.forbidden(owner, width)
            via_blocked = board.forbidden(owner, VIA_PAD, drilled=True)
        if ok:
            tracks += laid
            vias += via_set
        else:
            board.own = before
            failures.append((net, failed_at))
    return tracks, vias, failures


# HOW THE TWO GROUND PLANES ARE JOINED. A through-hole ground pad stitches them
# wherever there is one, and over most of this board there is, but the outboard
# ends have long runs with none. A via wherever one fits on a 15 mm grid costs
# nothing and is what keeps the pour one piece rather than several -- which the
# connectivity check would otherwise call an open circuit, correctly.
STITCH_PITCH = 8.0
STITCH_APART = 2.2


def _stitching(board: Board, parts, tracks, vias) -> list[Via]:
    owner = board.id(POUR_NET)
    for track in tracks:
        board.mark(track.layer, track.points, board.id(track.net), track.width)
    for via in vias:
        for layer in LAYERS:
            board.stamp(layer, via.x, via.y, VIA_PAD / 2, board.id(via.net))
    blocked = board.forbidden(
        owner, VIA_PAD + 2 * (POUR_CLEARANCE - CLEARANCE), drilled=True
    )
    out: list[Via] = []

    def place(x: float, y: float) -> bool:
        ix, iy = board.cell(x, y)
        if not (0 <= ix < board.nx and 0 <= iy < board.ny):
            return False
        if blocked["top"][ix, iy] or blocked["bottom"][ix, iy]:
            return False
        if any(
            math.dist((via.x, via.y), (ix * GRID, iy * GRID)) < STITCH_APART
            for via in out
        ):
            return False
        out.append(Via(POUR_NET, ix * GRID, iy * GRID))
        return True

    # One beside every ground pad first, which is what keeps a pad in the plane
    # rather than on an island of its own, and then a field of them on a grid.
    nets = net_of_pads(parts)
    for part in parts:
        for pad, x, y, _, _ in part.pads():
            if nets[(part.refdes, pad.name)] != POUR_NET:
                continue
            for reach in (1.8, 2.4, 3.0):
                if any(
                    place(x + reach * math.cos(a), y + reach * math.sin(a))
                    for a in [i * math.pi / 4 for i in range(8)]
                ):
                    break
    x = STITCH_PITCH / 2
    while x < BOARD_W:
        y = STITCH_PITCH / 2
        while y < BOARD_D:
            place(x, y)
            y += STITCH_PITCH
        x += STITCH_PITCH
    return out


# Ground is poured on both layers, and it is the only net that is.
POUR_NET = "GND"
LAYERS = ("top", "bottom")


# ---- the copper -----------------------------------------------------------------------


@dataclass
class Copper:
    net: str
    layers: tuple[str, ...]
    geom: object
    label: str
    kind: str  # pad, track, via, pour


def _pad_geometry(x: float, y: float, w: float, h: float, shape: str):
    from shapely.geometry import LineString, Point
    from shapely.geometry import box as rectangle

    if shape == "rect":
        return rectangle(x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    if shape == "circle" or abs(w - h) < 1e-9:
        return Point(x, y).buffer(w / 2, quad_segs=8)
    radius = min(w, h) / 2
    if w > h:
        spine = LineString([(x - w / 2 + radius, y), (x + w / 2 - radius, y)])
    else:
        spine = LineString([(x, y - h / 2 + radius), (x, y + h / 2 - radius)])
    return spine.buffer(radius, quad_segs=8)


def _outline():
    from shapely.geometry import box as rectangle

    return rectangle(0, 0, BOARD_W, BOARD_D).buffer(-EDGE_CLEARANCE, join_style=2)


def _hole_keepouts(parts: list[Placed] | None = None):
    from shapely.geometry import Point
    from shapely.ops import unary_union

    holes = []
    for part in parts or []:
        holes += [Point(x, y).buffer(d / 2 + CLEARANCE) for x, y, d in part.holes()]
    return unary_union(
        [Point(x, y).buffer(MOUNT_COPPER_KEEPOUT) for x, y in MOUNTS]
        + [Point(x, y).buffer(STANDOFF_COPPER_KEEPOUT) for x, y in STANDOFFS]
        + holes
    )


def _via_label(via: Via) -> str:
    return f"via at {via.x:.2f},{via.y:.2f}"


def build_copper(
    parts: list[Placed], tracks: list[Track], vias: list[Via]
) -> list[Copper]:
    """Every pad, track and via as geometry, and the ground pour cut round them."""
    from shapely.geometry import LineString, Point
    from shapely.geometry import box as rectangle
    from shapely.ops import unary_union

    nets = net_of_pads(parts)
    items: list[Copper] = []
    for part in parts:
        for pad, x, y, w, h in part.pads():
            items.append(
                Copper(
                    nets[(part.refdes, pad.name)],
                    LAYERS,
                    _pad_geometry(x, y, w, h, pad.shape),
                    f"{part.refdes}-{pad.name}",
                    "pad",
                )
            )
    for index, track in enumerate(tracks):
        items.append(
            Copper(
                track.net,
                (track.layer,),
                LineString(track.points).buffer(track.width / 2, quad_segs=6),
                f"track {index} ({track.layer}, from "
                f"{track.points[0][0]:.2f},{track.points[0][1]:.2f})",
                "track",
            )
        )
    for via in vias:
        items.append(
            Copper(
                via.net,
                LAYERS,
                Point(via.x, via.y).buffer(VIA_PAD / 2, quad_segs=6),
                _via_label(via),
                "via",
            )
        )

    # THE POUR. Everything that is not ground is cut out with POUR_CLEARANCE
    # round it; every ground pad is cut out with THERMAL_GAP round it and joined
    # back by four spokes, which is what lets a small iron solder a pin that
    # sits in a plane; slivers too thin to etch are opened away; and an island
    # that touches no ground at all is dropped rather than left floating.
    board = _outline()
    holes = _hole_keepouts(parts)
    for layer in LAYERS:
        others = unary_union(
            [c.geom for c in items if c.net != POUR_NET and layer in c.layers]
        ).buffer(POUR_CLEARANCE, quad_segs=6)
        base = board.difference(holes).difference(others)
        ground_pads = [c for c in items if c.net == POUR_NET and c.kind == "pad"]
        thermal_pads = [c for c in ground_pads if c.label not in SOLID_GROUND_PADS]
        gaps = unary_union([c.geom.buffer(THERMAL_GAP) for c in thermal_pads])
        spokes = []
        for pad in thermal_pads:
            cx, cy = pad.geom.centroid.x, pad.geom.centroid.y
            minx, miny, maxx, maxy = pad.geom.bounds
            reach = max(maxx - minx, maxy - miny) / 2 + THERMAL_GAP + THERMAL_SPOKE
            half = THERMAL_SPOKE / 2
            spokes += [
                rectangle(cx, cy - half, cx + reach, cy + half),
                rectangle(cx - reach, cy - half, cx, cy + half),
                rectangle(cx - half, cy, cx + half, cy + reach),
                rectangle(cx - half, cy - reach, cx + half, cy),
            ]
        spokes = unary_union(spokes).intersection(base)
        pour = base.difference(gaps)
        pour = pour.buffer(-0.12, quad_segs=4).buffer(0.12, quad_segs=4)
        pour = unary_union([pour.intersection(base), spokes])
        anchors = [c.geom for c in items if c.net == POUR_NET and layer in c.layers]
        anchor = unary_union(anchors)
        for number, piece in enumerate(getattr(pour, "geoms", [pour])):
            if piece.is_empty or piece.area < 0.05 or not piece.intersects(anchor):
                continue
            items.append(
                Copper(POUR_NET, (layer,), piece, f"{layer} pour {number}", "pour")
            )
    return items


def connected(items: list[Copper]):
    """What touches what: one root per piece of copper, by net and by layer.

    Everything that asks whether the drawn copper hangs together asks it this
    way -- the island joiner, the stray-stitch pass and the connectivity check --
    so they share one answer rather than three that could differ.
    """
    from shapely.strtree import STRtree

    tree = STRtree([item.geom for item in items])
    parent = list(range(len(items)))

    def find(m: int) -> int:
        while parent[m] != m:
            parent[m] = parent[parent[m]]
            m = parent[m]
        return m

    for a, item in enumerate(items):
        for b in tree.query(item.geom, predicate="intersects"):
            b = int(b)
            if b <= a or items[b].net != item.net:
                continue
            if set(item.layers) & set(items[b].layers):
                parent[find(a)] = find(b)
    return find


def stranded_vias(items: list[Copper], vias: list[Via]) -> list[Via]:
    """Stitching vias that hold nothing but copper reaching no pin.

    A stitch is put down on a grid BEFORE there is a pour to judge it by, so now
    and then a route moves and one of them is left in a pocket the pour comes out
    in with no ground pad anywhere in it. What it joins is then two pieces of
    floating copper on a net that is meant to be one plane, which is exactly what
    the connectivity check calls a stray. Dropping the via drops the pockets with
    it, because a pour piece nothing else anchors is not kept.
    """
    find = connected(items)
    anchored = {find(i) for i, item in enumerate(items) if item.kind == "pad"}
    stray = {
        item.label
        for i, item in enumerate(items)
        if item.kind == "via" and find(i) not in anchored
    }
    return [via for via in vias if _via_label(via) in stray]


def ground_islands(items: list[Copper]) -> list[list[tuple[float, float]]]:
    """Which ground pads the drawn copper leaves out of touch with which."""
    find = connected(items)
    islands: dict[int, list[tuple[float, float]]] = {}
    for index, item in enumerate(items):
        if item.net == POUR_NET and item.kind == "pad":
            point = item.geom.centroid
            islands.setdefault(find(index), []).append((point.x, point.y))
    return list(islands.values())


def join_islands(parts, tracks, vias, islands, report: Report):
    """Short hops of copper between the pieces the ground pour comes out in.

    THE POUR IS THE GROUND and this is not a substitute for it. It is the answer
    to one specific thing a poured plane on two layers cannot promise: a bundle
    of signals crossing both layers in the same place cuts both planes in the
    same place, and a pad on the far side of that is on an island. Three or four
    tracks a few millimetres long put it back.
    """
    board = Board(parts)
    owner = board.id(POUR_NET)
    for track in tracks:
        board.mark(track.layer, track.points, board.id(track.net), track.width)
    for via in vias:
        for layer in LAYERS:
            board.stamp(layer, via.x, via.y, VIA_PAD / 2, board.id(via.net))
    added: list[Track] = []
    addedVias: list[Via] = []
    main = max(islands, key=len)
    tree = [(*board.cell(*point), layer) for point in main for layer in LAYERS]
    for island in islands:
        if island is main:
            continue
        blocked = board.forbidden(owner, TRACK)
        via_blocked = board.forbidden(owner, VIA_PAD, drilled=True)
        path = _search(board, blocked, via_blocked, tree, board.cell(*island[0]))
        if path is None:
            report.faults.append(
                f"ground: no way to reach the island at {island[0][0]:.1f},"
                f" {island[0][1]:.1f}"
            )
            continue
        hop, hopVias = _to_geometry(path, POUR_NET, TRACK)
        for track in hop:
            board.mark(track.layer, track.points, owner, TRACK)
        for via in hopVias:
            for layer in LAYERS:
                board.stamp(layer, via.x, via.y, VIA_PAD / 2, owner)
        added += hop
        addedVias += hopVias
        tree += [(ix, iy, LAYERS[il]) for ix, iy, il in path]
    return added, addedVias


# ---- the checks -------------------------------------------------------------------------


@dataclass
class Report:
    faults: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# The core board's SWD header is a right-angle header on the core board itself,
# and nothing on the carrier meets it -- carrier.py excuses it for that reason.
OFF_BOARD_PINS = carrier.OFF_BOARD_PINS


def check_footprints(report: Report) -> None:
    parts = {part.refdes: part for part in carrier.PARTS}
    for refdes, part in parts.items():
        if refdes not in PLACEMENT:
            report.faults.append(f"{refdes} is in the netlist and not on the board")
            continue
        names = {pad.name for pad in _fp(refdes).pads}
        wanted = {pin for pin in part.pins if (refdes, pin) not in OFF_BOARD_PINS}
        if wanted - names:
            report.faults.append(
                f"{refdes}: footprint lacks pins {sorted(wanted - names)}"
            )
        if names - wanted:
            report.faults.append(
                f"{refdes}: footprint has pins {sorted(names - wanted)} the part lacks"
            )
    for refdes in PLACEMENT:
        if refdes not in parts:
            report.faults.append(f"{refdes} is on the board and not in the netlist")


def _overlap(a, b, margin: float) -> bool:
    return all(
        a[lo] < b[hi] + margin and b[lo] < a[hi] + margin
        for lo, hi in ((0, 2), (1, 3), (4, 5))
    )


def _box_circle_distance(box, cx: float, cy: float) -> float:
    dx = max(box[0] - cx, 0.0, cx - box[2])
    dy = max(box[1] - cy, 0.0, cy - box[3])
    return math.hypot(dx, dy)


BODY_AIR = 0.25


def check_placement(report: Report, parts: list[Placed]) -> None:
    """Bodies on the board, off the holes, and out of each other."""
    standoff_top = e.upperBandZ - TOP_Z
    for part in parts:
        for body, box in part.boxes():
            label = f"{part.refdes} {body.what}"
            if body.what != "core board" and (
                box[0] < -1e-6
                or box[1] < -1e-6
                or box[2] > BOARD_W + 1e-6
                or box[3] > BOARD_D + 1e-6
            ):
                report.faults.append(f"{label} is off the board")
            for mx, my in MOUNTS:
                gap = _box_circle_distance(box, mx, my)
                if gap < MOUNT_BODY_KEEPOUT:
                    report.faults.append(
                        f"{label} is {gap:.2f} mm from the mounting hole at "
                        f"({mx:g}, {my:g}); wants {MOUNT_BODY_KEEPOUT:.2f}"
                    )
            for hx, hy, diameter in part.holes():
                if _box_circle_distance(box, hx, hy) < diameter / 2:
                    continue  # its own tie holes, which it is meant to sit over
            for px, py in STANDOFFS:
                # The standoffs stop at the SBC's underside, and the core
                # board sits higher than that, so only what is lower has to
                # miss.
                gap = _box_circle_distance(box, px, py)
                if gap < STANDOFF_BODY_KEEPOUT and box[4] < standoff_top:
                    report.faults.append(
                        f"{label} is {gap:.2f} mm from the SBC standoff at "
                        f"({px:.2f}, {py:.2f}); wants "
                        f"{STANDOFF_BODY_KEEPOUT:.2f}"
                    )
    for i, first in enumerate(parts):
        for second in parts[i + 1 :]:
            for body_a, a in first.boxes():
                for body_b, b in second.boxes():
                    if _overlap(a, b, BODY_AIR):
                        report.faults.append(
                            f"{first.refdes} {body_a.what} and {second.refdes} "
                            f"{body_b.what} are within {BODY_AIR} mm"
                        )


def check_copper(report: Report, parts: list[Placed], items: list[Copper]) -> None:
    """Clearance between nets, and copper kept off the edge, holes and posts."""
    from shapely.ops import nearest_points, unary_union

    board = _outline()
    holes = _hole_keepouts(parts)
    for layer in LAYERS:
        by_net: dict[str, list] = {}
        for item in items:
            if layer in item.layers:
                by_net.setdefault(item.net, []).append(item.geom)
        merged = {net: unary_union(geoms) for net, geoms in by_net.items()}
        names = sorted(merged)
        bounds = {net: merged[net].bounds for net in names}
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                ba, bb = bounds[a], bounds[b]
                if (
                    ba[0] > bb[2] + CLEARANCE
                    or bb[0] > ba[2] + CLEARANCE
                    or ba[1] > bb[3] + CLEARANCE
                    or bb[1] > ba[3] + CLEARANCE
                ):
                    continue
                gap = merged[a].distance(merged[b])
                if gap < CLEARANCE - 1e-6:
                    p, _ = nearest_points(merged[a], merged[b])
                    what = "SHORTED" if gap < 1e-9 else f"{gap:.3f} mm apart"
                    report.faults.append(
                        f"{layer}: {a} and {b} {what} at ({p.x:.2f}, {p.y:.2f})"
                    )
        everything = unary_union(list(merged.values()))
        for what, region in (
            ("the board edge", everything.difference(board)),
            ("a hole", everything.intersection(holes)),
        ):
            if region.area > 1e-4:
                c = region.centroid
                report.faults.append(
                    f"{layer}: copper too near {what} at ({c.x:.2f}, {c.y:.2f})"
                )


def check_holes(report: Report, parts: list[Placed], vias: list[Via]) -> None:
    """No two drilled holes closer than HOLE_TO_HOLE, whatever is on them.

    THE ONE RULE THAT IS NOT ABOUT COPPER, and the one this file was missing: a
    via and a pad on the same net have no clearance to violate, so a stitch or a
    layer change could be put down on top of a pin and every copper check would
    still pass. KiCad's own DRC found three of them on a board this file called
    clean, which is the whole reason that export exists.
    """
    holes = [
        (x, y, e.m3Clearance, f"mounting hole at ({x:g}, {y:g})") for x, y in MOUNTS
    ]
    holes += [
        (x, y, e.sbcStandoffHole, f"SBC standoff hole at ({x:.2f}, {y:.2f})")
        for x, y in STANDOFFS
    ]
    for part in parts:
        for pad, x, y, _, _ in part.pads():
            holes.append((x, y, pad.drill, f"{part.refdes}-{pad.name}"))
        for hx, hy, diameter in part.holes():
            holes.append((hx, hy, diameter, f"{part.refdes} hole"))
    holes += [(via.x, via.y, VIA_DRILL, _via_label(via)) for via in vias]
    for i, (ax, ay, ad, a) in enumerate(holes):
        for bx, by, bd, b in holes[i + 1 :]:
            gap = math.hypot(ax - bx, ay - by) - (ad + bd) / 2
            if gap < HOLE_TO_HOLE - 1e-6:
                report.faults.append(
                    f"{a} and {b} are drilled {gap:.3f} mm apart, edge to edge; "
                    f"wants {HOLE_TO_HOLE}"
                )


MIN_SPOKES = 2


def check_thermals(report: Report, parts: list[Placed], items: list[Copper]) -> None:
    """Every ground pad reaches the plane by at least two of its four spokes.

    A pad in a plane is joined to it by four 0.5 mm spokes so that a small iron
    can heat it, and a spoke only exists where there is pour on the other side of
    the gap to join. Between two pads on a 2.5 mm pitch there is not: the two
    clearances leave 0.2 mm of copper and the sliver pass takes it away, so those
    two spokes were never there. That leaves the other two, and a track laid over
    one of them leaves the pad hanging on a single 0.5 mm bridge.

    KiCad calls that starved_thermal and it is right to. This is the same
    question asked on our own geometry, so the answer comes out here rather than
    three tools later.

    IT IS A NOTE AND NOT A FAULT, which is a judgement and should be read as one.
    Reserving all four lanes off every ground pad before routing was tried, and
    then reserving only the lanes that a neighbouring pad has not already closed:
    both cost the router more routes than they saved pads, on a board whose
    corridors are already 2 mm wide. One 0.5 mm spoke carries about 2 A and is
    warm to solder, not cold. WATCH THE ONE THAT CARRIES CURRENT: J5-2 is one of
    the SBC's two returns, and the SBC draws up to 2 A across the pair.
    """
    from shapely.geometry import Point

    starved: list[str] = []
    pours = {layer: [] for layer in LAYERS}
    for item in items:
        if item.kind == "pour":
            pours[item.layers[0]].append(item.geom)
    nets = net_of_pads(parts)
    for part in parts:
        for pad, x, y, w, h in part.pads():
            if nets[(part.refdes, pad.name)] != POUR_NET:
                continue
            if f"{part.refdes}-{pad.name}" in SOLID_GROUND_PADS:
                continue  # Solid connection; connectivity is checked separately.
            for layer, pieces in pours.items():
                reach = max(w, h) / 2 + THERMAL_GAP + THERMAL_SPOKE / 2
                alive = sum(
                    any(
                        piece.contains(Point(x + dx * reach, y + dy * reach))
                        for piece in pieces
                    )
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                )
                if 0 < alive < MIN_SPOKES:
                    starved.append(f"{part.refdes}-{pad.name} on {layer}")
    if starved:
        report.notes.append(
            f"{len(starved)} ground pad(s) reach the plane on one spoke of four: "
            + ", ".join(starved)
        )


def check_connectivity(report: Report, items: list[Copper]) -> None:
    """Each net's copper is one piece, and that piece holds every pin on the net."""
    find = connected(items)
    by_net: dict[str, list[int]] = {}
    for index, item in enumerate(items):
        by_net.setdefault(item.net, []).append(index)
    for net, members in sorted(by_net.items()):
        if net.startswith("~"):
            continue  # a spare pin, which only has to be touched by nothing
        pads = [m for m in members if items[m].kind == "pad"]
        pieces: dict[int, list[int]] = {}
        for m in pads:
            pieces.setdefault(find(m), []).append(m)
        if len(pieces) > 1:
            report.faults.append(
                f"{net} is open, in {len(pieces)} pieces: "
                + " | ".join(
                    " ".join(items[m].label for m in group) for group in pieces.values()
                )
            )
        stray = [
            items[m].label
            for m in members
            if items[m].kind in ("track", "via") and find(m) not in pieces
        ]
        if stray:
            report.faults.append(f"{net}: copper that reaches no pin: {stray}")


# The carrier's own stand-ins in cad/electronics.py, which this file replaces and
# so must not be measured against.
CARRIER_STAND_INS = {
    "controller carrier board",
    "WeAct core board",
    "CAN transceivers",
    "actuator harness bank",
    # Both of these were down in the power bay and are on this board now, so
    # cad/electronics.py draws them where this file puts them. Measuring the
    # real part against its own stand-in would find a clash every time.
    "bus monitor",
    "logic BEC",
}


def check_against_cad(report: Report, parts: list[Placed]) -> None:
    """Every body on this board against every drawn thing in the torso."""
    from build123d import Align, Box, Pos

    from cad import deck, torso

    groups = {
        name: bodies
        for name, bodies in e.torsoElectronicsGroups().items()
        if name not in CARRIER_STAND_INS
    }
    groups["deck"] = deck.electronicsDeck()
    groups["pelvis"] = torso.pelvisShell()[:7]

    def solid(box):
        x0, y0, x1, y1, z0, z1 = box
        return Pos(
            (x0 + x1) / 2 + ORIGIN_X, (y0 + y1) / 2 + ORIGIN_Y, z0 + TOP_Z
        ) * Box(
            x1 - x0, y1 - y0, z1 - z0, align=(Align.CENTER, Align.CENTER, Align.MIN)
        )

    reach = 3.0
    nearest: dict[str, tuple[float, str]] = {}
    for name, bodies in groups.items():
        for other in bodies:
            bb = other.bounding_box()
            for part in parts:
                for body, box in part.boxes():
                    if not (
                        box[0] + ORIGIN_X < bb.max.X + reach
                        and bb.min.X - reach < box[2] + ORIGIN_X
                        and box[1] + ORIGIN_Y < bb.max.Y + reach
                        and bb.min.Y - reach < box[3] + ORIGIN_Y
                        and box[4] + TOP_Z < bb.max.Z + reach
                        and bb.min.Z - reach < box[5] + TOP_Z
                    ):
                        continue
                    label = f"{part.refdes} {body.what}"
                    mine = solid(box)
                    common = mine & other
                    try:
                        shared = abs(common.volume)
                    except (ValueError, AttributeError, TypeError):
                        shared = 0.0
                    if shared > 1e-6:
                        report.faults.append(
                            f"{label} shares {shared:.2f} mm3 with the {name}"
                        )
                        continue
                    gap = mine.distance_to(other)
                    if gap < nearest.get(label, (reach, ""))[0]:
                        nearest[label] = (gap, name)
    for label, (gap, name) in sorted(nearest.items(), key=lambda item: item[1][0]):
        report.notes.append(f"{label}: {gap:.2f} mm from the {name}")


# THE TWO PLUGS ON THIS BOARD WHOSE LEADS DO NOT GO STRAIGHT DOWN. J5 runs up to
# the SBC standing 10 mm above it on its own standoffs, so the deck under J5 is
# nothing to do with J5. J7, since 2026-10-07, is the power switch board's hold
# lead, and it stands at the front edge in front of the core board where the
# deck under it is solid: its lead comes up through the deck's front opening
# beside J1 and runs along the front edge to it, about 90 mm, on a 250 mm lead.
# Every other plug here is fed from the bay below or from a leg beyond it, and
# has to get through the deck where it stands. JP1 is not in this list because
# it is not a plug: it is three holes and a wire link.
LEADS_UP = ("J5", "J7")


def check_leads_down(report: Report, parts: list[Placed]) -> None:
    """Require a continuous edge opening for every downward connector lead.

    The lead turns above the deck, outside the carrier outline, then drops
    through the notch. It never needs dressing amongst underside solder tails.
    Probe the full pin-row width plus 1.25 mm each end, through 5.5 mm of
    deck depth at its edge. Partial openings are failures, not advisory notes.
    The original rear notch was only under two buses; this check catches that.
    """
    from build123d import Box, Pos

    from cad import deck

    plate = deck.electronicsDeck()[0]
    bb = plate.bounding_box()
    mid = (bb.min.Z + bb.max.Z) / 2
    for part in sorted(parts, key=lambda p: p.refdes):
        pads = [(x, y) for _, x, y, _, _ in part.pads()]
        plugged = any(body.what == "plug and wires" for body in part.footprint.bodies)
        if not plugged or part.refdes in LEADS_UP or not pads:
            continue
        low = min(x for x, _ in pads) - 1.25 + ORIGIN_X
        high = max(x for x, _ in pads) + 1.25 + ORIGIN_X
        rear = sum(y for _, y in pads) / len(pads) < BOARD_D / 2
        centre_y = bb.min.Y + 2.75 if rear else bb.max.Y - 2.75
        probe = Pos((low + high) / 2, centre_y, mid) * Box(
            high - low, 5.5, bb.max.Z - bb.min.Z + 2.0
        )
        shared = abs((probe & plate).volume)
        if shared > 1e-6:
            report.faults.append(
                f"{part.refdes} downward cable exit blocked by {shared:.2f} mm3 of deck"
            )
        else:
            report.notes.append(f"{part.refdes} downward cable exit: full width open")


# ---- the drawing -------------------------------------------------------------------------


def ratsnest(parts: list[Placed], items: list[Copper]) -> list[tuple[tuple, tuple]]:
    """What is still unconnected, as straight lines between the nearest pins."""
    return []


def draw(path: Path, parts: list[Placed], items: list[Copper]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    # Text as text rather than as outlines, which is most of an SVG's size when
    # every pad carries its number.
    matplotlib.rcParams["svg.fonttype"] = "none"
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, PathPatch, Rectangle
    from matplotlib.path import Path as MplPath

    def patch(geom, **style):
        # Simplified to a hundredth of a millimetre before it is drawn: the
        # pour's outline is a buffered boolean with thousands of vertices, and
        # none of them is a fabrication figure -- this file's geometry is.
        geom = geom.simplify(0.05)
        polygons = getattr(geom, "geoms", [geom])
        vertices, codes = [], []
        for polygon in polygons:
            for ring in [polygon.exterior, *polygon.interiors]:
                coords = list(ring.coords)
                vertices += coords
                codes += [MplPath.MOVETO] + [MplPath.LINETO] * (len(coords) - 2)
                codes += [MplPath.CLOSEPOLY]
        return PathPatch(MplPath(vertices, codes), **style)

    colours = {"top": "#c0392b", "bottom": "#2e6fbd"}
    fig, axes = plt.subplots(3, 1, figsize=(12, 22))
    titles = ("parts, as placed", "top copper", "bottom copper, seen from above")
    for ax, title, layer in zip(axes, titles, (None, "top", "bottom")):
        ax.add_patch(Rectangle((0, 0), BOARD_W, BOARD_D, fc="#f3f1e8", ec="k", lw=1))
        if layer:
            for item in items:
                if layer in item.layers and item.kind != "pad":
                    ax.add_patch(
                        patch(
                            item.geom,
                            fc=colours[layer],
                            ec="none",
                            alpha=0.35 if item.kind == "pour" else 0.9,
                        )
                    )
        # Pads as plain circles and rectangles rather than as their geometry:
        # the drawing is for looking at, and a file full of 32-sided circles is
        # a file nobody opens.
        for part in parts:
            for pad, x, y, w, h in part.pads():
                if pad.shape == "circle":
                    ax.add_patch(Circle((x, y), w / 2, fc="#b8912b", ec="none"))
                else:
                    ax.add_patch(
                        Rectangle((x - w / 2, y - h / 2), w, h, fc="#b8912b", ec="none")
                    )
        for part in parts:
            for hx, hy, diameter in part.holes():
                ax.add_patch(Circle((hx, hy), diameter / 2, fc="w", ec="k", lw=0.5))
        for item in items:
            if item.kind == "via":
                ax.add_patch(
                    Circle(item.geom.centroid.coords[0], VIA_DRILL / 2, fc="w")
                )
        for part in parts:
            for pad, x, y, _, _ in part.pads():
                ax.add_patch(Circle((x, y), pad.drill / 2, fc="w", ec="none"))
                if layer:
                    ax.text(
                        x,
                        y,
                        pad.name.split("-")[-1],
                        fontsize=3.5,
                        ha="center",
                        va="center",
                    )
        for mx, my in MOUNTS:
            ax.add_patch(Circle((mx, my), e.m3Clearance / 2, fc="w", ec="k", lw=0.6))
        for px, py in STANDOFFS:
            ax.add_patch(
                Circle((px, py), e.sbcStandoffHole / 2, fc="w", ec="k", lw=0.6)
            )
        if layer is None:
            for part in parts:
                for body, box in part.boxes():
                    if body.what in (
                        "plug and wires",
                        "pin collar",
                        "core board underside",
                    ):
                        continue
                    ax.add_patch(
                        Rectangle(
                            (box[0], box[1]),
                            box[2] - box[0],
                            box[3] - box[1],
                            fc="none",
                            ec="#444",
                            lw=0.7,
                            ls=":" if body.what == "core board" else "-",
                        )
                    )
                ax.text(
                    part.x,
                    part.y,
                    part.refdes,
                    fontsize=9,
                    ha="center",
                    va="center",
                    color="#176b3a",
                    weight="bold",
                )
            sbc = Rectangle(
                (-e.sbcBoardWidth / 2 - ORIGIN_X, -e.sbcBoardDepth / 2 - ORIGIN_Y),
                e.sbcBoardWidth,
                e.sbcBoardDepth,
                fc="none",
                ec="#7d4fb0",
                ls="--",
                lw=1,
            )
            ax.add_patch(sbc)
        ax.set_title(title)
        ax.set_xlim(-1, BOARD_W + 1)
        ax.set_ylim(-1, BOARD_D + 1)
        ax.set_aspect("equal")
        ax.set_xticks(range(0, int(BOARD_W) + 1, 2))
        ax.set_yticks(range(0, int(BOARD_D) + 1, 2))
        ax.tick_params(labelsize=5)
        ax.grid(True, lw=0.15)
    fig.tight_layout()
    fig.savefig(
        path,
        dpi=220 if path.suffix == ".png" else 72,
        metadata={"Date": None} if path.suffix == ".svg" else None,
    )
    if path.suffix == ".svg":
        # Two decimals is a hundredth of a screen pixel. Matplotlib writes six,
        # which triples the file for nothing anybody can see -- and this file is
        # a picture of the board, not the board: the geometry above is that.
        import re

        text = path.read_text(encoding="utf-8")
        path.write_text(
            re.sub(r"\d+\.\d{3,}", lambda m: f"{float(m.group()):.2f}", text),
            encoding="utf-8",
        )


# ---- entry point -------------------------------------------------------------------------


def summary(
    parts: list[Placed], items: list[Copper], tracks: list[Track], vias: list[Via]
) -> str:
    """What a board house and a stores order would each want to know."""
    # EVERY HOLE THE BOARD HOUSE HAS TO DRILL, which includes the six it is
    # screwed down by and the four the SBC's standoffs are screwed to. Those
    # belong to the board rather than to any part on it, and this count left
    # them out until September 2026 -- so the figure quoted to the fab was ten
    # holes short of the drill file the same board exports.
    drills: dict[float, int] = {e.m3Clearance: len(MOUNTS)}
    drills[e.sbcStandoffHole] = drills.get(e.sbcStandoffHole, 0) + len(STANDOFFS)
    for part in parts:
        for pad in part.footprint.pads:
            drills[pad.drill] = drills.get(pad.drill, 0) + 1
        for _, _, diameter in part.holes():
            drills[diameter] = drills.get(diameter, 0) + 1
    if vias:
        drills[VIA_DRILL] = drills.get(VIA_DRILL, 0) + len(vias)
    length = sum(
        sum(
            math.dist(track.points[i], track.points[i + 1])
            for i in range(len(track.points) - 1)
        )
        for track in tracks
    )
    tallest = max(
        (box[5], f"{part.refdes} {body.what}")
        for part in parts
        for body, box in part.boxes()
    )
    lines = [
        "THE BOARD",
        "",
        f"  {BOARD_W:g} x {BOARD_D:g} mm, two layers, 1.6 mm FR-4, 1 oz copper",
        f"  smallest track {min(t.width for t in tracks):.2f} mm, "
        f"clearance {CLEARANCE:.2f} mm, smallest drill {min(drills):.2f} mm",
        f"  {sum(drills.values())} holes: "
        + ", ".join(f"{n} x Ø{d:g}" for d, n in sorted(drills.items())),
        f"  {len(tracks)} tracks, {length:.0f} mm of them, and {len(vias)} vias",
        f"  {len([c for c in items if c.kind == 'pour'])} pieces of poured ground",
        f"  tallest thing on it: {tallest[1]}, {tallest[0]:.1f} mm over the board",
        "",
        "WHAT IS SOLDERED TO IT",
        "",
    ]
    for part in sorted(parts, key=lambda p: (p.refdes[0], len(p.refdes), p.refdes)):
        item = next(p for p in carrier.PARTS if p.refdes == part.refdes)
        lines.append(f"  {part.refdes:<5}{part.footprint.name:<38}{item.partNumber}")
    return "\n".join(lines)


def lay_out(
    report: Report,
) -> tuple[list[Placed], list[Track], list[Via], list[Copper]]:
    """The whole board: placed, routed, poured, joined, and checked on the copper.

    ONE SEQUENCE AND NOT TWO. electrical/carrier_kicad.py exports what this
    returns, and it used to repeat these fifteen lines to get it -- which is a
    second design of the same board sitting in the file whose whole point is that
    it decides nothing. What is checked here is what is exported.
    """
    parts = placed()
    check_footprints(report)
    check_placement(report, parts)
    tracks, vias = route(parts, report)
    items = build_copper(parts, tracks, vias)
    for _ in range(3):
        islands = ground_islands(items)
        if len(islands) < 2:
            break
        hop, hopVias = join_islands(parts, tracks, vias, islands, report)
        if not hop and not hopVias:
            break
        tracks += hop
        vias += hopVias
        items = build_copper(parts, tracks, vias)
    stray = stranded_vias(items, vias)
    if stray:
        vias = [via for via in vias if via not in stray]
        items = build_copper(parts, tracks, vias)
        report.notes.append(
            f"{len(stray)} stitching via(s) dropped, each in a pocket of pour with "
            "no ground pad in it: " + ", ".join(_via_label(via) for via in stray)
        )
    check_copper(report, parts, items)
    check_holes(report, parts, vias)
    check_thermals(report, parts, items)
    check_connectivity(report, items)
    return parts, tracks, vias, items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draw", action="store_true", help="rewrite the SVG")
    parser.add_argument("--no-cad", action="store_true", help="skip the torso check")
    parser.add_argument("--png", type=Path, help="also draw to this PNG")
    args = parser.parse_args()

    faults = carrier.check()
    if faults:
        print("carrier netlist: FAILED")
        for fault in faults:
            print(f"  {fault}")
        return 1

    report = Report()
    parts, tracks, vias, items = lay_out(report)
    if not args.no_cad:
        check_against_cad(report, parts)
        check_leads_down(report, parts)

    if args.png:
        draw(args.png, parts, items)
    if args.draw:
        draw(SVG, parts, items)

    for note in report.notes:
        print(f"  note  {note}")
    if report.faults:
        print(f"carrier board: FAILED, {len(report.faults)} faults")
        for fault in report.faults:
            print(f"  {fault}")
        return 1
    print("carrier board: every check passes\n")
    print(summary(parts, items, tracks, vias))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
