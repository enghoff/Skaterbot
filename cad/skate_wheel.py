"""The bought 80 x 24 mm inline-skate wheel, modelled from its standard interface.

Ported from lib/skate_wheel.kcl. The hub and the tread are separate functions
rather than one returning both, because the assemblies hold their wheels as flat
lists of solids.
"""

from __future__ import annotations

from math import atan2, degrees, hypot

from build123d import (
    Axis,
    BuildLine,
    BuildSketch,
    CenterArc,
    Cylinder,
    Line,
    Plane,
    Pos,
    Rot,
    make_face,
    revolve,
)

from cad.wheeled_parameters import (
    skateWheelBearingBore,
    skateWheelCenterX,
    skateWheelCrownCenterRadius,
    skateWheelHubDiameter,
    skateWheelInnerX,
    skateWheelShoulderDiameter,
    skateWheelWidth,
)

hubOuterRadius = skateWheelHubDiameter / 2
shoulderRadius = skateWheelShoulderDiameter / 2


def skateWheelHub():
    """A plain annulus standing in for a spoked hub.

    Its bore is the pair of Ø22 bearing seats, drawn straight through: with the
    608s pulled out for the direct drive, the seats and the 8 mm bore between
    them become one bore.
    """
    hubBlank = (
        Pos(skateWheelCenterX, 0, 0)
        * Rot(0, 90, 0)
        * Cylinder(skateWheelHubDiameter / 2, skateWheelWidth)
    )
    hubBoreCutter = (
        Pos(skateWheelCenterX, 0, 0)
        * Rot(0, 90, 0)
        * Cylinder(skateWheelBearingBore / 2, skateWheelWidth + 2.0)
    )
    return hubBlank - hubBoreCutter


def skateWheelTread():
    """The crowned tread, revolved rather than extruded.

    The crown is the whole point: a flat annulus would put the contact patch
    across the full 24 mm and would misreport how far the wheel leans before its
    shoulder digs in.

    Drawn from the inboard face at x = 0 and slid outboard afterwards -- the
    sketch's radial coordinates have to be the true ones for the revolve, but its
    axial ones do not, and a solid of revolution moves along its own axis freely.
    """
    crownCentre = (skateWheelWidth / 2, skateWheelCrownCenterRadius)
    start = (skateWheelWidth, shoulderRadius)
    end = (0.0, shoulderRadius)
    radius = hypot(start[0] - crownCentre[0], start[1] - crownCentre[1])
    startAngle = degrees(atan2(start[1] - crownCentre[1], start[0] - crownCentre[0]))
    endAngle = degrees(atan2(end[1] - crownCentre[1], end[0] - crownCentre[0]))

    with BuildSketch(Plane.XZ) as profile:
        with BuildLine():
            Line((0.0, hubOuterRadius), (skateWheelWidth, hubOuterRadius))
            Line((skateWheelWidth, hubOuterRadius), start)
            CenterArc(
                center=crownCentre,
                radius=radius,
                start_angle=startAngle,
                arc_size=endAngle - startAngle,
            )
            Line(end, (0.0, hubOuterRadius))
        make_face()

    return Pos(skateWheelInnerX, 0, 0) * revolve(profile.sketch, axis=Axis.X)
