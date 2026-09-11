"""The bought metal at a straddled joint: the bearing and its journal.

Ported from lib/hardware.kcl. Neither is printed, and that is the point of
keeping them in their own module: tools/gate_c.py weighs the printed structure at
PA12-CF density and would be wrong about both, so they are counted as bought
items in mass_budget.toml instead -- 9.9 g a set, two sets, because hip pitch is
the only straddled joint left on this robot.

WHAT WAS HERE AND IS NOT. A turned aluminium carrier, a Ø30 x 3 mm flanged ring
bonded into a Ø30.2 cheek bore, which gave the bearing a metal seat. It was the
only bespoke machined part on the robot and the only line on docs/BOM.md with no
supplier, so the cheek is bored Ø19.2 and the bearing is bonded into the print
instead. cad/parameters.py carries the reasoning and cad/joint.py carries what
the flange did that nothing does now.

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
    journalSeatDepth,
    rotorHubOuterX,
)

journalCenterX = rotorHubOuterX - journalSeatDepth + journalLength / 2
# The bearing sits with its inboard face flush with the cheek's, which is where
# the seat now starts: 1 mm further out than it used to sit, so its whole width
# is in the seat and it clears the rotor hub's outer face by that millimetre
# instead of touching it.
bearingCenterX = frontCheekX - cheekThickness / 2 + bearingWidth / 2


def _disc(diameter: float, thickness: float, x: float = 0.0):
    return Pos(x, 0, 0) * Rot(0, 90, 0) * Cylinder(diameter / 2, thickness)


def bearing():
    """6800-2RS, 10 x 19 x 5, seated against the front cheek's shoulder."""
    blank = _disc(bearingOuterDiameter, bearingWidth, bearingCenterX)
    bore = _disc(bearingBore, bearingWidth + 4.0, bearingCenterX)
    return blank - bore


def journal():
    """Ø10 x 8 hardened journal, seated 2.2 mm into the rotor hub."""
    return _disc(journalDiameter, journalLength, journalCenterX)


def jointHardware() -> list:
    """One straddled joint's worth of bought metal, as two bodies."""
    return [bearing(), journal()]
