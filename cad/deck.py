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

WHAT IT CARRIES. The controller carrier on four standoffs, the SBC on four posts
that are part of this print, and the battery: the plate's underside lands on the
2 mm of squeeze the battery's reservation leaves over the packs, so lifting the
deck is what releases them and nothing else holds them down. Two of the four SBC
posts pass THROUGH the controller carrier, which is drilled for them --
cad/electronics.py says why that is unavoidable rather than untidy.

Four bodies: the plate and the four posts, left interpenetrating like every other
printed piece here, because a slicer merges coincident shells and cad/finish.py's
chamfer cannot be applied to a solid that is then booleaned again.

It has no golden STEP and it never will: the KCL had no such part, so gate B has
nothing to compare it against and does not list it. Gate E does -- every hole in
it is asserted there.
"""

from __future__ import annotations

from build123d import Align, Box, Cylinder, Pos

from cad.electronics import (
    _sbc_post_xy,
    boardHoleInset,
    controllerDepth,
    controllerWidth,
    controllerX,
    deckBandZ,
    deckLedgeX,
    deckLedgeY,
    deckThickness,
    deckZ,
    interiorHalfDepth,
    interiorHalfWidth,
    sbcPostDiameter,
    sbcPostHeight,
)
from cad.parameters import m3Clearance, m25InsertBore, m25InsertDepth
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

# The controller's four standoffs land here, on its own corner pattern.
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
    for sx in (1, -1):
        for sy in (1, -1):
            blank -= Pos(
                controllerX + sx * controllerScrewX,
                sy * controllerScrewY,
                deckZ + deckThickness / 2,
            ) * Cylinder(bossHoleDiameter / 2, deckThickness * 3)
    return blank


def _post(atX: float, atY: float):
    """One SBC post: a pillar off the plate with a heat-set insert in its top."""
    pillar = Pos(atX, atY, deckBandZ) * Cylinder(
        sbcPostDiameter / 2,
        sbcPostHeight,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    bore = Pos(atX, atY, deckBandZ + sbcPostHeight - m25InsertDepth / 2) * Cylinder(
        m25InsertBore / 2, m25InsertDepth + 1.0
    )
    return pillar - bore


def electronicsDeck() -> list:
    """The deck as printed: one plate and four posts."""
    return [_plate(), *(_post(dx, dy) for dx, dy in _sbc_post_xy())]
