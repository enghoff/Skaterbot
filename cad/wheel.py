"""A complete driven wheel: the printed adapter, the bought wheel, and the clamp.

Ported from wheel.kcl.
"""

from __future__ import annotations

from build123d import Cylinder, Plane, Pos, Rot

from cad.geometry import mirrored
from cad.skate_wheel import skateWheelHub, skateWheelTread
from cad.wheel_adapter import wheelAdapterLeft, wheelAdapterRight
from cad.wheeled_parameters import (
    skateWheelOuterX,
    wheelClampWasherDiameter,
    wheelClampWasherThickness,
)

washerInnerX = skateWheelOuterX
washerOuterX = washerInnerX + wheelClampWasherThickness
# M5 socket cap head, Ø8.5 x 5.
capHeadDiameter = 8.5
capHeadLength = 5.0


def _clampHardware() -> list:
    washer = (
        Pos(washerInnerX + wheelClampWasherThickness / 2, 0, 0)
        * Rot(0, 90, 0)
        * Cylinder(wheelClampWasherDiameter / 2, wheelClampWasherThickness)
    )
    capHead = (
        Pos(washerOuterX + capHeadLength / 2, 0, 0)
        * Rot(0, 90, 0)
        * Cylinder(capHeadDiameter / 2, capHeadLength)
    )
    return [washer, capHead]


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
