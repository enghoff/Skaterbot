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

AND THE SIX M3 AT EVERY MOTOR OUTPUT, since 14 October 2026, with the threads
in the motor they go into. Every joint has them, straddled or not, and they are
placed by boltedToOutput() wherever a disc is bolted to a motor in a scene.

Positioned in the joint's own frame, like everything in cad/joint.py: joint
centre at the origin, axis along X, actuator output towards +X.
"""

from __future__ import annotations

from build123d import Axis, Cylinder, Pos, Rot

from cad.parameters import (
    actuatorOutputBoltCircle,
    actuatorOutputBoltCount,
    actuatorOutputThreadDepth,
    bearingBore,
    bearingOuterDiameter,
    bearingWidth,
    cheekThickness,
    frontCheekX,
    journalDiameter,
    journalNutAcrossFlats,
    journalNutPocketDepth,
    journalNutThickness,
    journalScrewClearance,
    journalScrewDiameter,
    journalScrewHeadDiameter,
    journalScrewHeadHeight,
    journalScrewLength,
    journalSleeveBore,
    journalSleeveLength,
    m3CapCounterboreDepth,
    m3CapHeadDiameter,
    m3CapHeadHeight,
    m3ScrewDiameter,
    outputScrewLength,
    rotorHubInnerX,
    rotorHubOuterX,
)

# The bearing sits with its inboard face flush with the cheek's, which is where
# the seat now starts: 1 mm further out than it used to sit, so its whole width
# is in the seat and it clears the rotor hub's outer face by that millimetre
# instead of touching it.
bearingCenterX = frontCheekX - cheekThickness / 2 + bearingWidth / 2


def _disc(diameter: float, thickness: float, x: float = 0.0):
    return Pos(x, 0, 0) * Rot(0, 90, 0) * Cylinder(diameter / 2, thickness)


# The journal's own two stations. The sleeve lands on the rotor disc's outer face
# and runs through the bearing, which is exactly where the printed stub and the
# dowel before it ran: the bearing turns on the same 5 mm of Ø10 it always did.
# It ends a millimetre past the bearing's outer face since 2026-09-30, where a
# washer used to end -- cad/parameters.py's journalSleeveProud says why.
journalInnerX = rotorHubOuterX
journalOuterX = rotorHubOuterX + journalSleeveLength
# Where the nut sits: pulled up against the outboard end of its pocket, which is
# the face the sleeve clamps the disc's web against. The pocket's mouth is the
# plate's own seating face, so the actuator's Ø30 output register lands across
# it and closes it -- which is what makes the nut captive. It used to be 1.2 mm
# outboard of that face, on the floor of a register pocket that has since been
# retired, so the nut sits 1.2 mm further in than it did and the web goes from
# 1.5 mm to 2.7.
journalNutOuterX = rotorHubInnerX + journalNutPocketDepth


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
    centre = journalInnerX + journalSleeveLength / 2
    blank = _disc(journalDiameter, journalSleeveLength, centre)
    bore = _disc(journalSleeveBore, journalSleeveLength + 4.0, centre)
    return blank - bore


def journalScrew():
    """The M5 x 12 button head, seated on the sleeve's end.

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

    Four pieces: the bearing in the stationary cheek, and the journal that
    closes the joint -- sleeve, screw and nut -- which turns with the limb. There
    was a washer under the screw's head until 2026-09-30; the sleeve took its
    millimetre.
    """
    return [bearing(), journalSleeve(), journalScrew(), journalNut()]


def outputScrews() -> list:
    """The six M3 x 8 cap screws that hold an output disc to its motor.

    Drawn on 14 October 2026, after the wheel adapter's spigot turned out to
    have been printed over them with scallops that passed the key and stopped
    the head -- which nothing could say while no screw existed. Each head sits
    on its counterbore's floor and the shank runs on into the motor's thread.
    tools/gate_i.py runs them in along their axis, and every scene places them
    with boltedToOutput() below, so gate H measures them against everything.

    Head and shank overlap by a millimetre inside the head rather than butting on
    one plane, as cad/wheel.py's clamp screw does and for the same reason. The
    socket is not drawn; nothing here asks about it.
    """
    seatX = rotorHubOuterX - m3CapCounterboreDepth
    head = _disc(m3CapHeadDiameter, m3CapHeadHeight, seatX + m3CapHeadHeight / 2)
    shankLength = outputScrewLength + 1.0
    shank = _disc(m3ScrewDiameter, shankLength, seatX + 1.0 - shankLength / 2)
    return _onOutputCircle(head + shank)


def outputThreads() -> list:
    """The motor's six output threads, as cutters to take out of the actuator.

    Drawn at the thread's Ø3, which is the screw's own, so a screw in one
    touches it rather than overlapping it, and 6.5 mm deep from the output
    register's face, as the vendor STEP has them. A screw too long for its
    thread runs into the floor, and gate H reports the overlap. Each cutter
    stands a millimetre out past the face so none of its walls is coplanar with
    one.
    """
    outer = rotorHubInnerX + 1.0
    inner = rotorHubInnerX - actuatorOutputThreadDepth
    return _onOutputCircle(_disc(m3ScrewDiameter, outer - inner, (outer + inner) / 2))


def _onOutputCircle(body) -> list:
    """Six of `body`, from +Y round the Ø24 circle, as the disc's holes are."""
    first = Pos(0, actuatorOutputBoltCircle / 2, 0) * body
    step = 360 / actuatorOutputBoltCount
    return [first.rotate(Axis.X, i * step) for i in range(actuatorOutputBoltCount)]


def boltedToOutput(motor: list, place) -> tuple[list, list]:
    """A placed motor with its output threads cut, and the six screws in them.

    THE THREADS GO WHERE THE DISC IS, NOT WHERE THE MOTOR IS. They are in the
    output, which turns with the limb, so a knee at 110 degrees has them 110
    degrees round from where the housing alone would put them. `place` is
    whatever carries a body from the joint's own frame to the disc's place in
    the scene -- the same placement the part bolted to this output gets -- and
    both the cutters and the screws go through it, so the two cannot disagree.
    """
    threads = place(outputThreads())
    return [body.cut(*threads) for body in motor], place(outputScrews())
