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
which is not free either. The ledges cleared the battery's bay by 1.6 mm and
the power block by 1 mm, and that pair of numbers is what set the shell's depth --
cad/torso_shell.py records it. They are a millimetre deeper since 2026-09-30,
for plastic round the screws, and clear both bays by 0.6.

WHAT IT CARRIES. The controller carrier on six standoffs, and the foam pads
that hold the battery down. Until 2026-09-30 this said the plate landed on 2 mm
of squeeze over the packs, and it landed on nothing: the gap was air. For a day
after that it also hung two fences and a fin down beside and between the packs,
and they had to find the gap between two packs blind as the plate came down;
they stand on the pelvis now, and a pad needs nothing finding. The SBC is carried too, but at one
remove -- it stands on four bought standoffs on the controller carrier.

IT PRINTED THE SBC'S FOUR POSTS UNTIL SEPTEMBER 2026, 14 mm Ø8 pillars with an
M2.5 heat-set insert in each, and they came up THROUGH the carrier in Ø8.6 holes.
They cost the carrier two walls of bare laminate its tracks had to be routed
round, and a drill bigger than the board house owns; cad/electronics.py says what
replaced them. 2.5 g of PA12 came off this part with them.

IT WAS THE TOP HALF OF THE BMS's MOUNT until 2026-10-05: two slotted guides on
its underside took the board's top edge while two off the cavity floor took its
bottom. The board went between the two battery packs that day, into one block
with them, and the guides came off this plate with nothing to replace them.

THE BUS MONITOR IS NOT ON THIS PLATE, and it was for one revision. Two posts on
this underside held it, and they were the wrong answer for a reason no gate can
measure: the board's leads run down into the bay, so hanging it here ties the
deck to the torso by its wiring, and the deck is the assembly that has to come
straight out. It went to two pads on the pelvis's rear wall, and since
September 2026 it rides on the controller carrier, with every lead it takes down
into the bay on a plug. This plate still lifts off with nothing of its own
attached below it.

One solid, the plate, since the guides went. It was three groups containing
five solids -- the plate and two ribs per guide that only touched its
underside -- and a piece handed to a printer that way is not one part, which is
why tools/export.py unites every piece before anything is written and
tools/check.py fails the edit that leaves a body that would not unite.

It has no golden STEP and it never will: the KCL had no such part, so gate B has
nothing to compare it against and does not list it. Gate E does -- every hole in
it is asserted there.
"""

from __future__ import annotations

from build123d import Align, Box, Cylinder, Pos

from cad.electronics import (
    boardHoleInset,
    carrier_screw_xy,
    controllerDepth,
    controllerWidth,
    deckLedgeX,
    deckScrewY,
    deckThickness,
    deckZ,
    interiorHalfDepth,
    interiorHalfWidth,
)
from cad.parameters import m25Clearance
from cad.torso_shell import bossHoleDiameter, bossSize

# How much smaller than the cavity the plate is, all round, so it drops in. The
# same 0.4 mm the cover's locating lip is held off the walls by.
deckDropClearance = 0.4
deckWidth = (interiorHalfWidth * 2) - (deckDropClearance * 2)
deckDepth = (interiorHalfDepth * 2) - (deckDropClearance * 2)

# WHY THE CORNERS ARE CUT AWAY. The four cover bosses hang down the inside of
# the shell from just under its top face, and this plate has to pass them on its
# way in. It never shares a height with one -- they stop about 18 mm above it,
# since they came down 2.8 mm to clear the lid's lip -- so this is a
# clearance for the ASSEMBLY and not for the assembled position, which is the
# kind of interference a static check never finds.
deckCornerNotch = bossSize + 1.0

# THE CABLE CHASE THROUGH THE PLATE. Wide enough for the two actuator bundles
# and the CAN loom the shell already reserves -- 9 and 2.6 mm across -- plus the
# two 14 AWG leads that now come down off the rear wall, and no wider: every
# millimetre of it is plate taken out of the span that carries the boards.
# It sits between the bay gap and the right-hand wall ledge, which is the only
# stretch of the rear edge that is neither a fixing nor over the packs' hold-down.
deckChaseWidth = 44.0
deckChaseDepth = 6.0
deckChaseX = 22.0
# 2026-09-15: full pin-row width plus dressing clearance at the actual
# carrier connectors. The notches stop at y +/-27.2, outboard of the battery's
# fences at +/-22.5, and clear the wall ledges beginning at x +/-46.
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

    # Onto the wall ledges: clearance, because the screw is tapped into the shell,
    # and A SLOT RUN OUT TO THE PLATE'S EDGE rather than a hole, September 2026.
    # The hole was an M3 clearance on the ledge's centre line, which left 0.4 mm
    # of plate between itself and the edge -- tools/gate_g.py fails anything under
    # a millimetre, and no process prints that. Open to the edge there is no strip
    # to be thin, and nothing is lost: the plate is located by the four walls it
    # stands 0.4 mm off, so these four screws only hold it down. M2.5 now, placed
    # by its head; cad/electronics.py's deckScrewY says where and why.
    slotLength = deckDepth / 2 + 1.0 - deckScrewY
    for sx in (1, -1):
        for sy in (1, -1):
            blank -= Pos(
                sx * deckLedgeX, sy * deckScrewY, deckZ + deckThickness / 2
            ) * Cylinder(m25Clearance / 2, deckThickness * 3)
            blank -= Pos(
                sx * deckLedgeX,
                sy * (deckScrewY + slotLength / 2),
                deckZ + deckThickness / 2,
            ) * Box(m25Clearance, slotLength, deckThickness * 3)

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
    # threaded before anything is terminated. It stops at y = -27.2, outboard of
    # the battery's rear fence below.
    for _, at_x, width, side in cable_notches():
        blank -= Pos(
            at_x,
            side * (deckDepth / 2 - deckChaseDepth / 2 + 1.0),
            deckZ + deckThickness / 2,
        ) * Box(width, deckChaseDepth + 2.0, deckThickness * 3)
    return blank


def electronicsDeck() -> list:
    """The deck as printed: one plate. It carried the BMS's two top guides until
    2026-10-05, when the board went between the battery packs."""
    return [_plate()]
