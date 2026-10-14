"""Shin -- a flat-plate limb spanning the knee and wheel joints.

Ported from shin.kcl. The same part as the thigh at the same 105 mm, in the
opposite hand: the right thigh and the left shin are one print, the left thigh
and the right shin the other.
"""

from __future__ import annotations

from build123d import Plane

from cad.geometry import mirrored
from cad.limb import atUpperJoint, limbAssembly
from cad.parameters import lowerLegLength


def shinRight() -> list:
    return [mirrored(body, Plane.YZ) for body in limbAssembly(lowerLegLength)]


def shinLeft() -> list:
    return limbAssembly(lowerLegLength)


def shinRightOutput(bodies: list) -> list:
    """Joint-frame bodies carried to the right shin's knee disc, as it is drawn."""
    return [mirrored(body, Plane.YZ) for body in shinLeftOutput(bodies)]


def shinLeftOutput(bodies: list) -> list:
    return atUpperJoint(bodies, lowerLegLength)
