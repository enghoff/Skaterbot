"""The bought metal at a straddled joint: carrier, bearing and journal.

Ported from lib/hardware.kcl. None of this is printed, and that is the point of
keeping it in its own module: tools/gate_c.py weighs the printed structure at
PA12-CF density and would be wrong about every one of these, so they are counted
as bought items in mass_budget.toml instead -- 16.3 g a set, two sets, because
hip pitch is the only straddled joint left on this robot.

WHY THE SEAT IS METAL. NOTES.md records printed pockets ovalising, and this one
sets the coaxiality of the whole joint. The carrier is a flanged ring bonded into
the cheek bore with retaining compound, which avoids putting screws through a
3 mm printed wall.

Positioned in the joint's own frame, like everything in cad/joint.py: joint
centre at the origin, axis along X, actuator output towards +X.
"""

from __future__ import annotations

from build123d import Cylinder, Pos, Rot

from cad.parameters import (
    bearingBore,
    bearingCarrierDiameter,
    bearingCarrierFlangeDiameter,
    bearingCarrierFlangeThickness,
    bearingOuterDiameter,
    bearingWidth,
    cheekThickness,
    frontCheekX,
    journalDiameter,
    journalLength,
    journalSeatDepth,
    rotorHubOuterX,
)

carrierThickness = cheekThickness
journalCenterX = rotorHubOuterX - journalSeatDepth + journalLength / 2


def _disc(diameter: float, thickness: float, x: float = 0.0):
    return Pos(x, 0, 0) * Rot(0, 90, 0) * Cylinder(diameter / 2, thickness)


def bearingCarrier():
    """The flanged ring, bonded into the front cheek's Ø30.2 bore."""
    carrierBody = _disc(bearingCarrierDiameter, carrierThickness, frontCheekX)
    carrierFlange = _disc(
        bearingCarrierFlangeDiameter,
        bearingCarrierFlangeThickness,
        frontCheekX + carrierThickness / 2 + bearingCarrierFlangeThickness / 2,
    )
    carrierSeatCutter = _disc(
        bearingOuterDiameter,
        carrierThickness + bearingCarrierFlangeThickness + 4.0,
        frontCheekX,
    )
    return (carrierBody + carrierFlange) - carrierSeatCutter


def bearing():
    """6800-2RS, 10 x 19 x 5."""
    blank = _disc(bearingOuterDiameter, bearingWidth, frontCheekX)
    bore = _disc(bearingBore, bearingWidth + 4.0, frontCheekX)
    return blank - bore


def journal():
    """Ø10 x 8 hardened journal, seated 2.2 mm into the rotor hub."""
    return _disc(journalDiameter, journalLength, journalCenterX)


def jointHardware() -> list:
    """One straddled joint's worth of bought metal, as three bodies."""
    return [bearingCarrier(), bearing(), journal()]
