"""Thigh -- a flat-plate limb spanning the hip-pitch and knee joints.

Ported from thigh.kcl. All of the geometry lives in cad/limb.py and
cad/joint.py; the thigh only chooses its length and its hand.

The robot is mirror-symmetric about its midline, so each leg segment exists in
two hands. They are true mirrors across YZ, not spins: the stator plate's
connector relief is not symmetric fore and aft, so spinning the part about its
own axis would put the relief on the wrong side.

Both leg segments are 105 mm, so the right thigh and the left shin are the same
print, and so are the left thigh and the right shin. There are still only two
distinct limb parts on the robot.
"""

from __future__ import annotations

from build123d import Plane

from cad.geometry import mirrored
from cad.limb import limbAssembly
from cad.parameters import upperLegLength


def thighRight() -> list:
    """The hand whose plate lies on +X, which is the right leg's thigh.

    Its hip pitch actuator drives towards +X and its knee actuator, turned round,
    presents its rear cover the same way.
    """
    return limbAssembly(upperLegLength)


def thighLeft() -> list:
    return [mirrored(body, Plane.YZ) for body in thighRight()]
