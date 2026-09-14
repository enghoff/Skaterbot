# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9", "shapely>=2.0", "matplotlib>=3.8", "numpy>=1.26"]
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
socket stands in a post, whether the antenna's bulkhead is over a header.

WHAT THE CHECKS PROVE, in the order they run:

  1. every footprint has exactly the pins carrier.py gives its part;
  2. every body is on the board, clear of the mounting holes and the SBC posts,
     and clear of every other body in three dimensions -- which is what lets a
     capacitor stand under the socketed core board without being called a clash;
  3. every body, and every plug with its wires leaving it, clears every drawn
     thing in the torso, measured in the CAD's own frame (skipped by --no-cad);
  4. the copper of any two nets is at least CLEARANCE apart on each layer, and
     no copper is near the board edge, a mounting hole or a post;
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
POSTS = [(px - ORIGIN_X, py - ORIGIN_Y) for px, py in e.sbc_posts_through_carrier()]


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
POUR_CLEARANCE = 0.3
THERMAL_GAP = 0.3
THERMAL_SPOKE = 0.5

# WHAT MAY STAND NEAR A MOUNTING HOLE. On top, an M3 washer is 7 mm across and a
# driver comes down onto it; underneath, the 6 mm A/F brass standoff is 6.9 mm
# across its corners and its face has to seat flat on the board, so no solder
# joint may be under it either. Copper stays clear of both, whatever its net:
# the standoff is brass, and nothing on this board is meant to be grounded
# through a printed deck.
MOUNT_BODY_KEEPOUT = 3.5 + 0.5
MOUNT_COPPER_KEEPOUT = 6.0 / math.sqrt(3) + 0.35
# The SBC's posts come up through Ø8.6 holes with 0.3 mm of air round a Ø8
# pillar. Bodies and copper both stay half a millimetre outside the hole.
POST_KEEPOUT = e.sbcPostClearance / 2 + 0.5


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
    """A dipped 100 nF X7R on 2.54 mm leads, stood upright."""
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


def bec_module() -> Footprint:
    """The Matek BEC12S-PRO lying flat, tied down, its four leads on a header.

    NO VENDOR HOLE PATTERN EXISTS to screw it by -- the part is a moulded brick
    with flying leads -- so it is not screwed at all. Four Ø3 holes take two
    cable ties across its short axis, and the leads land on the 1 x 4 header
    beside it. It lies on a 1 mm silicone pad, which is the one thing here that
    does anything about its heat: about 3 W at full output, and the pad puts that
    into this board's ground pour instead of into the still air under the SBC.

    35 x 24 x 5.5 is cad/electronics.py's becWidth, becDepth and becHeight, which
    are catalogue figures. Measure the part when it arrives: the tie holes are
    drilled to the catalogue and a brick 2 mm wider than the catalogue says will
    not sit between them.
    """
    pads = tuple(
        Pad(
            str(n),
            7.81 - 2.54 * (n - 1),
            15.0,
            1.7,
            1.7,
            1.0,
            "rect" if n == 1 else "circle",
        )
        for n in (1, 2, 3, 4)
    )
    return Footprint(
        "Matek BEC12S-PRO, tied down, on a 1 x 4",
        pads,
        (
            Body((-17.5, -12.0, 17.5, 12.0, 0.0, 1.0), "thermal pad"),
            Body((-17.5, -12.0, 17.5, 12.0, 1.0, 6.5), "BEC"),
            # Two straps and not a lid over the whole module: drawn as one slab
            # it fouled the SBC's microSD socket, which hangs 7.8 mm over this
            # board, and a cable tie is 4 mm wide.
            Body((-14.0, -14.5, -10.0, 14.5, 6.5, 8.5), "cable tie"),
            Body((10.0, -14.5, 14.0, 14.5, 6.5, 8.5), "cable tie"),
        ),
        tuple((dx, dy, 3.0) for dx in (-12.0, 12.0) for dy in (-13.6, 13.6)),
    )


def ina226_module() -> Footprint:
    """The INA226 breakout on two M2 standoffs, its logic side on a header.

    THE ONLY PART OF THIS BOARD THAT NEEDS MORE THAN 9.4 mm OF AIR, which is why
    it is at this end of the carrier and not somewhere more convenient: 8 mm of
    module on 3 mm standoffs is 11, and 9.4 is all the SBC leaves anywhere it
    stands over. cad/electronics.py's headroom is what settled that.

    The two mounting holes are the outer pair of the four in the board's own
    column -- busSenseHolePitch 16.7, busSenseHoleInset 2.5, both read off the
    vendor's photographs and neither measured. ITS SHUNT TERMINALS ARE NOT HERE.
    IN+ and IN- are screw terminals on the module and the twisted pair from the
    shunt lands in them directly, so the 75 mV never touches this board's copper.
    """
    pads = tuple(
        Pad(
            str(n),
            2.54 * (n - 1) - 5.08,
            -14.0,
            1.7,
            1.7,
            1.0,
            "rect" if n == 1 else "circle",
        )
        for n in (1, 2, 3, 4, 5)
    )
    return Footprint(
        "INA226 breakout on two M2 standoffs, on a 1 x 5",
        pads,
        (
            Body((-11.0, -11.0, 11.0, 11.0, 0.0, 3.0), "standoffs"),
            Body((-11.0, -11.0, 11.0, 11.0, 3.0, 11.0), "bus monitor"),
        ),
        tuple((dx, -8.5, 2.4) for dx in (-8.35, 8.35)),
    )


def radial_ptc() -> Footprint:
    """A resettable fuse on 5.08 mm leads, standing on the bus feed."""
    return Footprint(
        "PTC radial P5.08",
        (
            Pad("1", 0.0, 0.0, 1.8, 1.8, 1.0, "rect"),
            Pad("2", 5.08, 0.0, 1.8, 1.8, 1.0),
        ),
        (Body((-3.5, -1.8, 8.58, 1.8, 0.0, 13.0)),),
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
# 1. THE SBC LEAVES 9.4 mm OF AIR over everything between x 40 and x 105, and a
#    mated JST-XH plug is 9.8 mm tall. So every connector is on one of the two
#    edges, outboard of the SBC's own front and rear edges, and so is anything
#    else taller than the SBC's underside: the core board on its sockets, the bus
#    monitor on its standoffs, the two pull-ups and the fuse.
# 2. THE SBC'S FOUR POSTS COME UP THROUGH THIS BOARD in two pairs, at x 43.55 and
#    x 101.55, 23 mm apart. Each pair is a wall 9.6 mm wide with a 14.4 mm gate
#    in the middle of it, so nothing wider than that gate crosses either pair.
#    That is why the BEC is between the two walls, the monitor outboard of the
#    right-hand one, and the core board outboard of the left-hand one.
# 3. WHAT COMES UP THROUGH THE DECK COMES UP AT THE REAR, through cad/deck.py's
#    34 mm chase at x 82.55 to 116.55 in this frame. The three bus connectors sit
#    over it, which is the whole reason this layout was redone: they used to be
#    at the far outboard end and the loom crossed the torso to reach them.
#
# The front edge carries what goes UP rather than down -- the SBC's own cable,
# and the bus feed and shunt pair that come through a second opening in the deck
# over the distribution board.
REAR_ROW_Y = 3.0
FRONT_ROW_Y = BOARD_D - 3.0

PLACEMENT = {
    # The core board, outboard of the left-hand posts, where there are 16 mm of
    # air. Turned half round so P1 -- every signal but reset -- faces inboard.
    "A1": (WEACT_X, WEACT_Y, 180),
    # NOTHING STANDS BETWEEN THE LEFT-HAND POSTS. A DIP-8 fits there and one was
    # there, and it cost more than it was worth: eighteen nets have to cross that
    # pair of posts to get from the core board to the rest of the board, the gate
    # between them is 13.4 mm wide, and a transceiver standing in it left two
    # slots of 2 mm. Four nets could not be routed at all. It is a corridor.
    # The BEC, lying flat between the two pairs of posts. Its four leads come out
    # on the header along its front edge, beside the 5 V bulk.
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
    # The bus feed's own hardware, in the outboard strip where the fuse's 13 mm
    # of height is not under the SBC.
    "F1": (122.0, 43.0, 0),
    "C9": (130.0, 36.0, 0),
    # Bulk on the 5 V rail, between the BEC's output pin and the SBC's cable.
    "C1": (81.0, 43.0, 0),
    # A pair of 100 nF at each transceiver, VDD then VIO.
    # THE TWO SLOTS BETWEEN THE THREE SOCKETS ARE LEFT OPEN. They are 1.78 mm
    # each and they are the only way across this column for anything that has to
    # reach the monitor, so a capacitor standing in one costs three nets their
    # route. Two pairs sit clear of them, and bus B's pair has to stand off in
    # the channel beside the right-hand posts, 16 mm from its own pin: this is
    # the one place on the board where a decoupling capacitor is further from its
    # chip than it should be, and the ground plane under the pair is what makes
    # that tolerable rather than the lead length.
    "C2": (86.0, 41.5, 0),
    "C3": (91.0, 41.5, 0),
    "C6": (97.0, 21.5, 0),
    "C7": (97.0, 25.5, 0),
    "C4": (103.0, 20.0, 0),
    "C5": (103.0, 25.5, 0),
    # 3.3 V decoupling and the two I2C pull-ups, by the monitor.
    "C8": (118.0, 36.0, 0),
    "R1": (110.0, 36.0, 180),
    "R2": (113.5, 36.0, 0),
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
        # board's edge, a mounting hole's washer, an SBC post, a drilled hole.
        self.fixed = np.minimum.reduce(
            [self.gx, self.gy, BOARD_W - self.gx, BOARD_D - self.gy]
        )
        for mx, my in MOUNTS:
            self.fixed = np.minimum(
                self.fixed, np.hypot(self.gx - mx, self.gy - my) - MOUNT_COPPER_KEEPOUT
            )
        for px, py in POSTS:
            self.fixed = np.minimum(
                self.fixed, np.hypot(self.gx - px, self.gy - py) - POST_KEEPOUT
            )
        self.own = {
            layer: np.full((self.nx, self.ny), -1, dtype=np.int32) for layer in LAYERS
        }
        self.nets: list[str] = []
        self.index: dict[str, int] = {}
        nets = net_of_pads(parts)
        for part in parts:
            for pad, x, y, w, h in part.pads():
                net = nets[(part.refdes, pad.name)]
                radius = math.hypot(w, h) / 2 if pad.shape == "rect" else max(w, h) / 2
                for layer in LAYERS:
                    self.stamp(layer, x, y, radius, self.id(net))
            for hx, hy, diameter in part.holes():
                self.fixed = np.minimum(
                    self.fixed,
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

    def forbidden(self, owner: int, width: float):
        """Cells this net may not put the centre of a track on, per layer."""
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

    first: list[str] = []
    best = None
    shuffle = random.Random(20260914)
    for attempt in range(PASSES):
        order = [net for net in todo if net in ROUTE_FIRST]
        order += [net for net in first if net in todo and net not in order]
        rest = [net for net in todo if net not in order and net != POUR_NET]
        # After the first two passes the queue is shuffled as well as reordered.
        # Pushing what failed to the front is not enough on its own: the nets
        # that blocked it are still in the same order behind it, so the same
        # board comes back with a different net left out. A seeded shuffle gives
        # a genuinely different pass, and the seed keeps the answer repeatable.
        if attempt >= 2:
            shuffle.shuffle(rest)
        order += rest
        board = Board(parts)
        tracks, vias, failures = _one_pass(board, order, sites)
        if best is None or len(failures) < len(best[3]):
            best = (board, tracks, vias, failures)
        if not failures:
            break
        first = [net for net, _ in failures if net not in ROUTE_FIRST] + first
    board, tracks, vias, failures = best
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
        via_blocked = board.forbidden(owner, VIA_PAD)
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
            via_blocked = board.forbidden(owner, VIA_PAD)
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
    blocked = board.forbidden(owner, VIA_PAD + 2 * (POUR_CLEARANCE - CLEARANCE))
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
        + [Point(x, y).buffer(POST_KEEPOUT) for x, y in POSTS]
        + holes
    )


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
                f"via at {via.x:.2f},{via.y:.2f}",
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
        gaps = unary_union([c.geom.buffer(THERMAL_GAP) for c in ground_pads])
        spokes = []
        for pad in ground_pads:
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


def ground_islands(items: list[Copper]) -> list[list[tuple[float, float]]]:
    """Which ground pads the drawn copper leaves out of touch with which."""
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
        via_blocked = board.forbidden(owner, VIA_PAD)
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
OFF_BOARD_PINS = {("A1", f"P3-{n}") for n in carrier.WEACT_P3}


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
    post_top = e.upperBandZ - TOP_Z
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
            for px, py in POSTS:
                # The posts stop at the SBC's underside, and the core board
                # sits higher than that, so only what is lower has to miss.
                gap = _box_circle_distance(box, px, py)
                if gap < POST_KEEPOUT and box[4] < post_top:
                    report.faults.append(
                        f"{label} is {gap:.2f} mm from the SBC post at "
                        f"({px:.2f}, {py:.2f}); wants {POST_KEEPOUT:.2f}"
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


def check_connectivity(report: Report, items: list[Copper]) -> None:
    """Each net's copper is one piece, and that piece holds every pin on the net."""
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
    groups["deck and SBC posts"] = deck.electronicsDeck()
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
        for px, py in POSTS:
            ax.add_patch(
                Circle((px, py), e.sbcPostClearance / 2, fc="w", ec="k", lw=0.6)
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
    drills: dict[float, int] = {}
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
    check_copper(report, parts, items)
    check_connectivity(report, items)
    if not args.no_cad:
        check_against_cad(report, parts)

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
