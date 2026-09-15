"""The electronics deck: the plate the upper two boards stand on.

A NEW PART, September 2026, and the first printed piece on this robot that the
KCL never had. It exists because the pelvis has a floor problem that the battery
made obvious rather than caused: the cavity is full at floor level, so a board
in an upper band has nothing under it to stand on. The SBC has floated in its
reserved volume with no mount drawn since the layout was first done, and this is
what it lands on.

WHAT CARRIES IT. Four ledges on the front and rear inner walls, cad/torso.py's
`deckLedge`, whose top faces are the plane this plate sits on. They are where
they are because they are the only places in this cavity that are free: the
battery fills the bottom band from the left wall to past the centre line, the
power-entry block fills the rest of it, and between them is the lead chase,
which is not free either. The ledges clear the packs by 1.6 mm and the power
block by 1 mm, and that pair of numbers is what set the shell's depth --
cad/torso_shell.py records it.

WHAT IT CARRIES. The controller carrier on six standoffs, and the battery: the
plate's underside lands on the 2 mm of squeeze the battery's reservation leaves
over the packs, so lifting the deck is what releases them and nothing else holds
them down. The SBC is carried too, but at one remove -- it stands on four bought
standoffs on the controller carrier.

IT PRINTED THE SBC'S FOUR POSTS UNTIL SEPTEMBER 2026, 14 mm Ø8 pillars with an
M2.5 heat-set insert in each, and they came up THROUGH the carrier in Ø8.6 holes.
They cost the carrier two walls of bare laminate its tracks had to be routed
round, and a drill bigger than the board house owns; cad/electronics.py says what
replaced them. 2.5 g of PA12 came off this part with them.

AND IT IS THE TOP HALF OF THE BMS's MOUNT, which is what the two guides on its
underside are. The board stands on edge in a slot in the cavity floor and the
plate over it stops it lifting; these take its TOP edge in the same 9 mm slot, so
a card that was held at one end only is held at both. The deck goes on last and
comes straight down, so they swallow the top edge as it lands.

THE BUS MONITOR IS NOT ON THIS PLATE, and it was for one revision. Two posts on
this underside held it, and they were the wrong answer for a reason no gate can
measure: the board's leads run down into the bay, so hanging it here ties the
deck to the torso by its wiring, and the deck is the assembly that has to come
straight out. It went to two pads on the pelvis's rear wall, and since
September 2026 it rides on the controller carrier, with every lead it takes down
into the bay on a plug. This plate still lifts off with nothing of its own
attached below it.

Three groups containing five solids: the plate and two ribs per BMS guide, left interpenetrating like
every other printed piece here, because a slicer merges
coincident shells and cad/finish.py's chamfer cannot be applied to a solid that
is then booleaned again.

It has no golden STEP and it never will: the KCL had no such part, so gate B has
nothing to compare it against and does not list it. Gate E does -- every hole in
it is asserted there.
"""

from __future__ import annotations

from build123d import Align, Box, Cylinder, Pos

from cad.electronics import (
    bmsGuideDepth,
    bmsGuideSlot,
    bmsGuideWidth,
    bmsGuideY,
    bmsTopGuideDrop,
    bmsX,
    boardHoleInset,
    carrier_screw_xy,
    controllerDepth,
    controllerWidth,
    deckLedgeX,
    deckLedgeY,
    deckThickness,
    deckZ,
    interiorHalfDepth,
    interiorHalfWidth,
)
from cad.parameters import m3Clearance
from cad.torso_shell import bossHoleDiameter, bossSize

# How much smaller than the cavity the plate is, all round, so it drops in. The
# same 0.4 mm the cover's locating lip is held off the walls by.
deckDropClearance = 0.4
deckWidth = (interiorHalfWidth * 2) - (deckDropClearance * 2)
deckDepth = (interiorHalfDepth * 2) - (deckDropClearance * 2)

# WHY THE CORNERS ARE CUT AWAY. The four cover bosses hang down the inside of
# the shell from its top face, and this plate has to pass them on its way in. It
# never shares a height with one -- they stop 20 mm above it -- so this is a
# clearance for the ASSEMBLY and not for the assembled position, which is the
# kind of interference a static check never finds.
deckCornerNotch = bossSize + 1.0

# THE CABLE CHASE THROUGH THE PLATE. Wide enough for the two actuator bundles
# and the CAN loom the shell already reserves -- 9 and 2.6 mm across -- plus the
# two 14 AWG leads that now come down off the rear wall, and no wider: every
# millimetre of it is plate taken out of the span that holds the battery down.
# It sits between the bay gap and the right-hand wall ledge, which is the only
# stretch of the rear edge that is neither a fixing nor over the packs' hold-down.
deckChaseWidth = 44.0
deckChaseDepth = 6.0
deckChaseX = 22.0
# 2026-09-15: full pin-row width plus dressing clearance at the actual
# carrier connectors. The notches stop at y +/-27.2, outside the packs'
# +/-26 mm hold-down area, and clear the wall ledges beginning at x +/-46.
deckImuChaseX = -20.8
deckImuChaseWidth = 18.0
deckPowerChaseX = 38.0
deckPowerChaseWidth = 12.0


def cable_notches():
    """(name, x, width, side): -1 rear, +1 front; open to the shell wall."""
    return (
        ("motor buses", deckChaseX, deckChaseWidth, -1),
        ("IMU", deckImuChaseX, deckImuChaseWidth, -1),
        ("bus feed and shunt", deckPowerChaseX, deckPowerChaseWidth, 1),
    )


# The controller's standoffs land here. SIX OF THEM SINCE SEPTEMBER 2026 and
# not on a corner pattern any more: the board is 140 mm long, its rear edge is
# full of connectors and its rear outboard corner passes under the charge
# socket, so the stations are a table in cad/electronics.py that this plate and
# electrical/carrier_pcb.py both read. The two names below are what the corner
# pattern was, and they are kept because tools/gate_a.py holds them: they are
# still the outermost pair's offsets from the board's own centre.
controllerScrewX = (controllerWidth / 2) - boardHoleInset
controllerScrewY = (controllerDepth / 2) - boardHoleInset


def _plate():
    """The plate itself, with its corners cut and every hole through it."""
    blank = Pos(0, 0, deckZ) * Box(
        deckWidth,
        deckDepth,
        deckThickness,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )

    for sx in (1, -1):
        for sy in (1, -1):
            blank -= Pos(
                sx * (deckWidth / 2 - deckCornerNotch / 2 + 1.0),
                sy * (deckDepth / 2 - deckCornerNotch / 2 + 1.0),
                deckZ + deckThickness / 2,
            ) * Box(deckCornerNotch, deckCornerNotch, deckThickness * 3)

    # Onto the wall ledges: clearance, because the screw is tapped into the shell.
    for sx in (1, -1):
        for sy in (1, -1):
            blank -= Pos(
                sx * deckLedgeX, sy * deckLedgeY, deckZ + deckThickness / 2
            ) * Cylinder(m3Clearance / 2, deckThickness * 3)

    # Under the controller's standoffs: piloted at the same Ø2.5 the cover
    # bosses use, because the screw taps into this plate from above. No insert
    # anywhere on this part: it is 3 mm thick and an M3 insert is 5.7 mm long.
    for atX, atY in carrier_screw_xy():
        blank -= Pos(atX, atY, deckZ + deckThickness / 2) * Cylinder(
            bossHoleDiameter / 2, deckThickness * 3
        )

    # THE CABLE CHASE, and it is a debt being paid rather than a new feature.
    # This plate has spanned the cavity wall to wall with no way through it since
    # it was drawn, while the actuator harnesses have always had to get from the
    # two floor cable ports up to the controller carrier above -- drawn at both
    # ends and nowhere in between. It is now also the only route for the two
    # power leads off the rear wall's panel hardware, which stands above this
    # plate and feeds a bay below it.
    #
    # An open notch in the rear edge rather than a closed slot: a loom is dressed
    # into it from the side once the deck is down, where a closed hole has to be
    # threaded before anything is terminated. It stops short of the battery's
    # squeeze -- the packs end at y = -26 and this reaches y = -27.2 -- so the
    # plate still bears on the cells across their whole width.
    for _, at_x, width, side in cable_notches():
        blank -= Pos(
            at_x,
            side * (deckDepth / 2 - deckChaseDepth / 2 + 1.0),
            deckZ + deckThickness / 2,
        ) * Box(width, deckChaseDepth + 2.0, deckThickness * 3)
    return blank


def _bmsGuide(atY: float):
    """One pair of ribs off the plate's underside, straddling the board's top.

    A block with the slot taken straight out of it, and the slot runs the block's
    WHOLE drop so that what is left is two ribs with the plate itself closing the
    top. The 1.5 mm of air between that face and the board's top edge is the
    hold-down, and cutting the slot any shallower would take it away.

    The slot is subtracted from the block it belongs to and nothing is unioned on
    afterwards, which is the rule on every printed piece here: a body unioned
    over a slot closes it with nothing to report it.
    """
    block = Pos(bmsX, atY, deckZ - (bmsTopGuideDrop / 2)) * Box(
        bmsGuideWidth, bmsGuideDepth, bmsTopGuideDrop
    )
    slot = Pos(bmsX, atY, deckZ - (bmsTopGuideDrop / 2)) * Box(
        bmsGuideSlot, bmsGuideDepth + 2.0, bmsTopGuideDrop
    )
    return block - slot


def electronicsDeck() -> list:
    """The deck as printed: one plate and the two BMS guides."""
    return [
        _plate(),
        *(_bmsGuide(atY) for atY in bmsGuideY),
    ]
