"""A complete driven wheel: the printed adapter, the bought wheel, and the clamp.

Ported from wheel.kcl.

THE CLAMP IS THREE BOUGHT ITEMS, and until they were drawn this module had two.
An M5 socket cap screw pulls a Ø30 washer against the hub's outer face and
threads into a heat-set insert in the spigot; what stood here was the washer as a
solid disc and a cylinder the size of the screw's head, which showed where the
clamp sits without showing what is in it. The screw and the insert were not
modelled at all, and the washer had no bore.

DRAWING THE SCREW IS WHAT SETTLED ITS LENGTH. The pocket it goes into is blind
and reaches 15 mm below the head by the dimensions as declared, 17 as
cad/wheel_adapter.py actually cuts them, so the M5 x 20 the bill of materials
asks for lands on the bottom of the bore before the head ever reaches the
washer and the joint would never see preload. Measured rather than reasoned: a
Ø5 shank 20 mm under the head shares 58.9 mm3 with the printed adapter, which is
3 mm of screw inside solid plastic. The screw here is the 12 mm one, which
threads through 9 of the insert's 9.5 mm and shares nothing with the adapter.

Nothing in this file is printed. The clamp is bought steel and brass and is
counted in tools/mass_budget.toml with the fasteners, not weighed from the CAD.
"""

from __future__ import annotations

from build123d import Cylinder, Plane, Pos, RegularPolygon, Rot, extrude

from cad.geometry import mirrored
from cad.skate_wheel import skateWheelHub, skateWheelTread
from cad.wheel_adapter import (
    insertOuterX,
    wheelAdapterLeft,
    wheelAdapterRight,
)
from cad.wheeled_parameters import (
    capHeadDiameter,
    capHeadLength,
    skateWheelOuterX,
    wheelClampScrewDiameter,
    wheelClampScrewLength,
    wheelClampSocketAcrossFlats,
    wheelClampSocketDepth,
    wheelClampWasherBore,
    wheelClampWasherDiameter,
    wheelClampWasherThickness,
    wheelInsertLength,
    wheelInsertThreadDiameter,
    wheelSpigotInsertBore,
)

washerInnerX = skateWheelOuterX
washerOuterX = washerInnerX + wheelClampWasherThickness
washerCenterX = washerInnerX + wheelClampWasherThickness / 2

# The head sits on the washer and the shank hangs below it.
capHeadOuterX = washerOuterX + capHeadLength
screwTipX = washerOuterX - wheelClampScrewLength


def _disc(diameter: float, thickness: float, x: float = 0.0):
    return Pos(x, 0, 0) * Rot(0, 90, 0) * Cylinder(diameter / 2, thickness)


def clampWasher():
    """Ø30 x 2, bored M5 clearance.

    Deliberately a big washer: it bridges the millimetre the spigot is held short
    and lands on the WHEEL's hub face, so the preload crosses the hub and not the
    end of a printed spigot.
    """
    blank = _disc(wheelClampWasherDiameter, wheelClampWasherThickness, washerCenterX)
    bore = _disc(wheelClampWasherBore, wheelClampWasherThickness + 2.0, washerCenterX)
    return blank - bore


def clampScrew():
    """The M5 socket cap screw: head, shank, and the hex socket in its face.

    The head and the shank are unioned with a millimetre of overlap rather than
    butted together, because two cylinders meeting on one shared plane is the
    coincident-face case docs/KCL_GOTCHAS.md lists as a reliable way to have a
    boolean refused. The overlap is inside the head, so the length under the head
    is still wheelClampScrewLength.

    The thread is not cut. A helix would tessellate into thousands of triangles
    to show what a plain Ø5 shank already shows, which is where the screw is and
    how far into the insert it reaches.
    """
    head = _disc(capHeadDiameter, capHeadLength, washerOuterX + capHeadLength / 2)
    shankLength = wheelClampScrewLength + 1.0
    shank = _disc(wheelClampScrewDiameter, shankLength, screwTipX + shankLength / 2)
    socketDepth = wheelClampSocketDepth + 1.0
    socket = Pos(capHeadOuterX - wheelClampSocketDepth, 0, 0) * extrude(
        Plane.YZ * RegularPolygon(wheelClampSocketAcrossFlats / 2, 6, False),
        amount=socketDepth,
    )
    return (head + shank) - socket


def heatSetInsert():
    """The M5 brass insert, seated flush with the spigot's outer end.

    A plain sleeve. A real one is knurled outside and slightly tapered, and
    neither changes what this body is here for: showing that the screw has
    something to pull against, and how much of the screw is inside it.
    """
    sleeve = _disc(
        wheelSpigotInsertBore, wheelInsertLength, insertOuterX - wheelInsertLength / 2
    )
    thread = _disc(
        wheelInsertThreadDiameter,
        wheelInsertLength + 2.0,
        insertOuterX - wheelInsertLength / 2,
    )
    return sleeve - thread


def _clampHardware() -> list:
    """The screw, the washer and the insert, as three separate bodies."""
    return [clampScrew(), clampWasher(), heatSetInsert()]


def wheelRight() -> list:
    """Matches a right wheel motor whose output points +X."""
    return [
        *wheelAdapterRight(),
        skateWheelHub(),
        skateWheelTread(),
        *_clampHardware(),
    ]


def wheelLeft() -> list:
    """The mirrored installation.

    The adapter brings its own mirrored hand from cad/wheel_adapter.py, so only
    the bought parts are mirrored here.
    """
    donor = [skateWheelHub(), skateWheelTread(), *_clampHardware()]
    return [*wheelAdapterLeft(), *[mirrored(body, Plane.YZ) for body in donor]]
