"""The bought metal at a straddled joint: the bearing, and the journal that is
fitted into it last.

Ported from lib/hardware.kcl. None of this is printed, and that is the point of
keeping it in its own module: tools/gate_c.py weighs the printed structure at the
print material's density and would be wrong about it, so these are counted as
bought items in mass_budget.toml instead, at the two hip pitch joints and the two
knees.

WHAT WAS HERE AND IS NOT. A turned aluminium carrier, a Ø30 x 3 mm flanged ring
bonded into a Ø30.2 cheek bore, which gave the bearing a metal seat. It was the
only bespoke machined part on the robot and the only line on docs/BOM.md with no
supplier, so the cheek is bored Ø19.2 and the bearing is bonded into the print
instead.

AND WHAT WENT AND CAME BACK, which is the journal. It was a Ø10 dowel bonded into
the limb's output disc; on 13 September 2026 the limb grew its own Ø10 stub and
printed it, which deleted four bought items and 29.6 g of steel. Neither can be
ASSEMBLED: both are one piece with the moving side before the joint is closed,
and the fork is a single print whose cheeks stand 4.7 mm closer together than
that unit is long. So the journal is a sleeve again -- but a sleeve that goes in
from OUTSIDE, through the boss's Ø17.5 shoulder bore and the bearing, onto the
disc's face, where a screw pulls it down onto a nut captive in the disc.

Four bought pieces at each straddled joint, then: the bearing, the sleeve, the
screw and the nut. cad/parameters.py carries what the anchor is worth and what it
is not, beside journalDiameter.

Positioned in the joint's own frame, like everything in cad/joint.py: joint
centre at the origin, axis along X, actuator output towards +X.
"""

from __future__ import annotations

from build123d import Cylinder, Pos, Rot

from cad.parameters import (
    bearingBore,
    bearingOuterDiameter,
    bearingWidth,
    cheekThickness,
    frontCheekX,
    journalDiameter,
    journalLength,
    journalNutAcrossFlats,
    journalNutPocketDepth,
    journalNutThickness,
    journalScrewClearance,
    journalScrewDiameter,
    journalScrewHeadDiameter,
    journalScrewHeadHeight,
    journalScrewLength,
    journalSleeveBore,
    rotorHubInnerX,
    rotorHubOuterX,
    rotorRegisterDepth,
)

# The bearing sits with its inboard face flush with the cheek's, which is where
# the seat now starts: 1 mm further out than it used to sit, so its whole width
# is in the seat and it clears the rotor hub's outer face by that millimetre
# instead of touching it.
bearingCenterX = frontCheekX - cheekThickness / 2 + bearingWidth / 2


def _disc(diameter: float, thickness: float, x: float = 0.0):
    return Pos(x, 0, 0) * Rot(0, 90, 0) * Cylinder(diameter / 2, thickness)


# The journal's own two stations. The sleeve lands on the rotor disc's outer face
# and ends flush with the bearing's outer face, which is exactly where the
# printed stub ended and where the dowel before it ended: the bearing runs on the
# same 5 mm of Ø10 it always did.
journalInnerX = rotorHubOuterX
journalOuterX = rotorHubOuterX + journalLength
# Where the nut sits: pulled up against the outboard end of its pocket, which is
# the face the sleeve clamps the disc's web against.
journalNutOuterX = rotorHubInnerX + rotorRegisterDepth + journalNutPocketDepth


def bearing():
    """6800-2RS, 10 x 19 x 5, seated against the front cheek's shoulder."""
    blank = _disc(bearingOuterDiameter, bearingWidth, bearingCenterX)
    bore = _disc(bearingBore, bearingWidth + 4.0, bearingCenterX)
    return blank - bore


def journalSleeve():
    """The Ø10 steel sleeve the bearing turns on, bored Ø5.3 for its screw.

    Fitted from outside, last of everything: it passes the boss's Ø17.5 shoulder
    bore and the bearing, and lands on the rotor disc. It is a slip fit in the
    bearing rather than a bond, because a bonded sleeve could not be drawn back
    out and the joint could then never be taken apart.

    THE BORE IS CENTRED ON THE SLEEVE AND NOT ON ITS INBOARD FACE, and that is
    worth a line because it was wrong here first: a cutter centred at
    journalInnerX ran out a millimetre short of the outer end and left the sleeve
    capped, with the screw modelled straight through the cap. Nothing objected.
    The screw is not a printed piece, so gate E never saw it and gate F only
    measures this hardware against the parts it sits in, not against itself;
    tools/gate_e.py now asks this bore to be open, which is the check that was
    missing rather than a check of this one mistake.
    """
    centre = journalInnerX + journalLength / 2
    blank = _disc(journalDiameter, journalLength, centre)
    bore = _disc(journalSleeveBore, journalLength + 4.0, centre)
    return blank - bore


def journalScrew():
    """The M5 x 10 button head that holds the sleeve down, and its shank.

    The head is drawn as a plain cylinder rather than as the dome it is, which
    overstates it -- so what tools/gate_f.py measures off it is the pessimistic
    figure, which is the way round a clearance wants to be wrong.
    """
    head = _disc(
        journalScrewHeadDiameter,
        journalScrewHeadHeight,
        journalOuterX + journalScrewHeadHeight / 2,
    )
    shank = _disc(
        journalScrewDiameter,
        journalScrewLength,
        journalOuterX - journalScrewLength / 2,
    )
    return head + shank


def journalNut():
    """The M5 thin nut captive in the disc, drawn as the circle it turns inside.

    A CYLINDER AND NOT A HEXAGON, deliberately. The nut is the one piece of this
    hardware whose shape has an orientation, and cad/scenes.py places a joint's
    hardware without turning it to match the limb's own rotation -- so a drawn
    hexagon would read as interfering with its pocket in every flexed pose and
    say nothing true about the part. Ø8 is the nut across its flats, which is the
    circle it sweeps and what has to fit the pocket whichever way it went in.
    """
    blank = _disc(
        journalNutAcrossFlats,
        journalNutThickness,
        journalNutOuterX - journalNutThickness / 2,
    )
    bore = _disc(journalScrewClearance, journalNutThickness + 4.0, journalNutOuterX)
    return blank - bore


def jointHardware() -> list:
    """One straddled joint's worth of bought metal.

    Four pieces now: the bearing in the stationary cheek, and the journal that
    closes the joint -- sleeve, screw and nut -- which turns with the limb.
    """
    return [bearing(), journalSleeve(), journalScrew(), journalNut()]
