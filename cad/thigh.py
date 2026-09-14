"""Thigh -- a limb spanning the hip-pitch and knee joints, straddling the knee.

Ported from thigh.kcl. All of the geometry lives in cad/limb.py and
cad/joint.py; the thigh only chooses its length, its hand, and which of the two
lower ends cad/limb.py offers it.

IT TAKES THE CLEVIS AND THE SHIN DOES NOT. The knee carries everything below it
-- shin, wheel motor, adapter and wheel -- on a plate 22 mm off the joint axis,
and that overhung moment was the one open question the flat limbs left with
DAMIAO. It is the joint on this robot worth a second bearing, so the thigh's
lower end is cad/joint.py's `statorClevis` reaching past the knee motor to a
bonded 6800, and the shin's stays the plate it has always been.

The robot is mirror-symmetric about its midline, so each leg segment exists in
two hands. They are true mirrors across YZ, not spins: the connector relief on
both the stator plate and the clevis's rear cheek is not symmetric fore and aft,
so spinning the part about its own axis would put the relief on the wrong side.

Both leg segments are still 105 mm, but a thigh is no longer the same piece as a
shin, so there are four distinct limb prints on the robot rather than two printed
twice. What that buys and what it costs is in cad/limb.py's own docstring.
"""

from __future__ import annotations

from build123d import Plane

from cad.geometry import mirrored
from cad.limb import limbAssembly
from cad.parameters import upperLegLength


def thighRight() -> list:
    """The hand whose plate lies on +X, which is the right leg's thigh.

    Its hip pitch actuator drives towards +X and its knee actuator, turned round,
    presents its rear cover the same way -- so the clevis's rear cheek lands on
    +X and its far cheek reaches out to -X, past the shin's rotor disc.
    """
    return limbAssembly(upperLegLength, lowerEnd="clevis")


def thighLeft() -> list:
    return [mirrored(body, Plane.YZ) for body in thighRight()]
