"""A complete driven wheel: the printed adapter and cap, the bought wheel, and the clamp.

Ported from wheel.kcl.

THE CLAMP IS A PRINTED CAP AND THREE BOUGHT ITEMS. An M5 socket cap screw sits
on a plain M5 washer inside the cap, passes down through the cap's floor and the
hub's centre ridge, and threads into a heat-set insert in the adapter. The cap
stands on the ridge, so tightening the screw clamps the hub between the cap and
the adapter's output disc. The insert is pressed in from the motor side, so the
screw pulls it against a step in the adapter's bore rather than out of it.

UNTIL 6 OCTOBER 2026 THE CAP WAS A Ø30 PENNY WASHER lying on the hub's outer
face, and the spigot ran the hub's whole width to hold the insert at its far end.
Both rested on the hub being bored Ø22 straight through, which it is not, and
the washer was a part nobody in India sells in a basket.

DRAWING THE SCREW IS WHAT SETS ITS LENGTH, as it was the first time: an M5 x 20
was once asked for and would have bottomed in the old spigot's blind bore. Under
the head there are 30.5 mm of washer, floor, ridge, air and adapter before the
motor, so the screw is a 30, runs through the whole insert, and stops half a
millimetre inside the adapter's back face.
cad/wheeled_parameters.py carries the arithmetic beside wheelClampScrewLength.

Nothing in this file is printed. The cap is cad/wheel_cap.py and the adapter is
cad/wheel_adapter.py; the clamp is bought steel and brass and is counted in
tools/mass_budget.toml with the fasteners, not weighed from the CAD.
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
from cad.wheel_cap import wheelCapLeft, wheelCapRight
from cad.wheeled_parameters import (
    capHeadDiameter,
    capHeadLength,
    wheelCapFloor,
    wheelCapInnerX,
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

# The washer lies on the cap's floor, inside it.
washerInnerX = wheelCapInnerX + wheelCapFloor
washerOuterX = washerInnerX + wheelClampWasherThickness
washerCenterX = washerInnerX + wheelClampWasherThickness / 2

# The head sits on the washer and the shank hangs below it.
capHeadOuterX = washerOuterX + capHeadLength
screwTipX = washerOuterX - wheelClampScrewLength


def _disc(diameter: float, thickness: float, x: float = 0.0):
    return Pos(x, 0, 0) * Rot(0, 90, 0) * Cylinder(diameter / 2, thickness)


def clampWasher():
    """A plain M5 washer, Ø11 x 1.5 as fastdep sells it, on the cap's floor.

    It is there to keep the screw head off printed plastic: 1 kN on the bare
    head is 30 MPa on the cap's floor, and on this washer 14. It was a Ø30
    penny washer on the hub's face until 6 October 2026.
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
    """The M5 brass insert, pressed in from the motor side against the step.

    Its outer end bears on the step in the adapter's bore, and the screw coming
    the other way pulls it against that step rather than out of its pocket.

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


def wheelRightGroups() -> dict[str, list]:
    """The right wheel as the four things it is assembled from.

    Kept apart so that a scene which wants to measure them against each other --
    the cap on the ridge, the spigot short of it, the screw through the cap's
    bore -- can, rather than receiving them as one bag. tools/gate_h.py measures
    every group against every other, and nothing within a group.
    """
    return {
        "wheel adapter": wheelAdapterRight(),
        "skate wheel": [skateWheelHub(), skateWheelTread()],
        "wheel cap": [wheelCapRight()],
        "wheel clamp": _clampHardware(),
    }


def wheelRight() -> list:
    """Matches a right wheel motor whose output points +X."""
    return [body for group in wheelRightGroups().values() for body in group]


def wheelLeft() -> list:
    """The mirrored installation.

    The adapter and the cap bring their own mirrored hands from their own
    modules, so only the bought parts are mirrored here.
    """
    donor = [skateWheelHub(), skateWheelTread(), *_clampHardware()]
    return [
        *wheelAdapterLeft(),
        wheelCapLeft(),
        *[mirrored(body, Plane.YZ) for body in donor],
    ]
