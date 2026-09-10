"""What goes inside the pelvis, and therefore how tall the pelvis is.

Ported from wheeled_electronics.kcl -- its RESERVED VOLUMES, which are the part
that matters. The six-motor torso's height is not a chosen number: it is derived
in cad/wheeled_parameters.py from what has to fit inside, and these are the
things that have to fit. Anything that changes a reserved volume changes the
robot's height.

The boards themselves -- the slabs that stand in for a power-entry block, a
controller carrier, an SBC and an IMU so the packing can be looked at rather than
asserted -- are the rest of that file and are phase 1 task 1.7. The envelopes
below are what the simulation reads for its payload masses, so they come first.
"""

from __future__ import annotations

from build123d import Align, Box, Cylinder, Pos

from cad.parameters import shellWall
from cad.wheeled_parameters import (
    wheeledHipSaddleRise,
    wheeledTorsoInteriorFloorZ,
    wheeledTorsoShellWidth,
)

interiorHalfWidth = (wheeledTorsoShellWidth - (shellWall * 2)) / 2
floorZ = wheeledTorsoInteriorFloorZ
saddleTopZ = floorZ + wheeledHipSaddleRise

# How much air each item leaves against the side wall it is pushed up to. The
# pair in the lower band needs 114 of the 120.2 mm available, so 2 mm at each
# wall leaves 2.2 mm between them.
wallClearance = 2.0
bandGap = 2.0

# ---- the reserved volumes, which are the requirement ------------------------

powerWidth = 38.0
powerDepth = 62.0
powerHeight = 30.0
controllerWidth = 76.0
controllerDepth = 46.0
controllerHeight = 12.0
sbcWidth = 85.0
sbcDepth = 58.0
sbcHeight = 16.0
imuWidth = 22.0
imuDepth = 22.0
imuHeight = 6.0

powerX = interiorHalfWidth - wallClearance - (powerWidth / 2)
controllerX = -interiorHalfWidth + wallClearance + controllerWidth / 2
lowerBandZ = saddleTopZ
upperBandZ = lowerBandZ + powerHeight + bandGap

pcbThickness = 1.6
capacitorDiameter = 16.0
capacitorHeight = 25.0
capacitorZ = lowerBandZ + pcbThickness

pcbGreen = "#1c6b42"
componentBlack = "#20232a"
canSilver = "#8c939c"
terminalBlue = "#2f5fb4"


# ---- the boards themselves --------------------------------------------------
#
# Every one of these is a stand-in for a bought board or connector, drawn so the
# packing can be looked at rather than asserted. None is printed and none is
# weighed from the CAD: mass_budget.toml carries them as the "Electronics and
# wiring" and "Power entry" allowances, both estimates with nothing in hand.


def slab(width, depth, height, atX, atY, atZ):
    """A rectangular solid on its centre in x and y, sitting ON atZ."""
    return Pos(atX, atY, atZ) * Box(
        width, depth, height, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )


def can(diameter, height, atX, atY, atZ):
    """An electrolytic can, standing on atZ.

    The capacitor bank is the only round thing in the torso.
    """
    return Pos(atX, atY, atZ) * Cylinder(
        diameter / 2, height, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )


def torsoElectronics() -> list:
    """The hardware on its own, for a scene that wants nothing but the boards."""
    # ---- power entry: bank, fuse and terminal -------------------------------
    bodies = [slab(powerWidth, powerDepth, pcbThickness, powerX, 0.0, lowerBandZ)]
    for dx in (-9.0, 9.0):
        for dy in (-11.0, 11.0):
            bodies.append(
                can(capacitorDiameter, capacitorHeight, powerX + dx, dy, capacitorZ)
            )
    # The tether lands here, which is why it is on the rear face: the slot in the
    # shell's back wall is 20 mm below and a little inboard of this terminal.
    bodies.append(slab(30.0, 10.0, 12.0, powerX, -25.0, capacitorZ))
    bodies.append(slab(20.0, 10.0, 14.0, powerX, 25.0, capacitorZ))

    # ---- controller carrier -------------------------------------------------
    bodies.append(
        slab(
            controllerWidth, controllerDepth, pcbThickness, controllerX, 0.0, lowerBandZ
        )
    )
    # The WeAct core board, on headers above the carrier.
    bodies.append(
        slab(36.3, 28.1, 6.0, controllerX - 12.0, 3.0, lowerBandZ + pcbThickness)
    )
    for dy in (8.0, 0.0):
        bodies.append(
            slab(6.0, 4.0, 1.5, controllerX + 20.0, dy, lowerBandZ + pcbThickness)
        )
    # Where the six actuator harnesses land, facing the rear wall and its ports.
    bodies.append(
        slab(46.0, 6.0, 8.0, controllerX + 8.0, -19.0, lowerBandZ + pcbThickness)
    )

    # ---- SBC ----------------------------------------------------------------
    bodies.append(slab(sbcWidth, sbcDepth, pcbThickness, 0.0, 0.0, upperBandZ))
    bodies.append(slab(15.0, 15.0, 2.0, -6.0, 0.0, upperBandZ + pcbThickness))
    # The connector bank stands 13.5 mm off the board and is what makes the whole
    # upper band as tall as it is.
    for dx in (-22.0, 8.0):
        bodies.append(slab(18.0, 16.0, 13.5, dx, 21.0, upperBandZ + pcbThickness))
    bodies.append(slab(51.0, 5.0, 8.5, 0.0, -26.0, upperBandZ + pcbThickness))

    # ---- IMU, in the clear floor between the two hip saddles ----------------
    bodies.append(slab(11.0, 10.0, pcbThickness, 0.0, 0.0, floorZ))
    bodies.append(slab(4.0, 4.0, 1.2, 0.0, 0.0, floorZ + pcbThickness))
    return bodies


def torsoReservations() -> list:
    """The reservations on their own, which are what nothing may be designed through."""
    return [
        slab(powerWidth, powerDepth, powerHeight, powerX, 0.0, lowerBandZ),
        slab(
            controllerWidth,
            controllerDepth,
            controllerHeight,
            controllerX,
            0.0,
            lowerBandZ,
        ),
        slab(sbcWidth, sbcDepth, sbcHeight, 0.0, 0.0, upperBandZ),
        slab(imuWidth, imuDepth, imuHeight, 0.0, 0.0, floorZ),
    ]


def torsoPayload() -> list:
    """Both together, and what the assemblies place."""
    return [*torsoElectronics(), *torsoReservations()]
