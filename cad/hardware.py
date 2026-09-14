"""The bought metal at a straddled joint: the bearing, and nothing else now.

Ported from lib/hardware.kcl. The bearing is not printed, and that is the point
of keeping it in its own module: tools/gate_c.py weighs the printed structure at
the print material's density and would be wrong about it, so it is counted as a
bought item in mass_budget.toml instead -- 5.0 g apiece, four of them, at the two
hip pitch joints and the two knees.

WHAT WAS HERE AND IS NOT, and it is two things now.

A turned aluminium carrier, a Ø30 x 3 mm flanged ring bonded into a Ø30.2 cheek
bore, which gave the bearing a metal seat. It was the only bespoke machined part
on the robot and the only line on docs/BOM.md with no supplier, so the cheek is
bored Ø19.2 and the bearing is bonded into the print instead.

And THE JOURNAL, which went on 13 September 2026. It was a Ø10 hardened dowel
bonded into a blind seat in the limb's output disc; the limb grows its own Ø10
stub out of that disc now and is printed with it. That deletes four bought items,
four bonded joints and the seat they went into, and it takes 29.6 g of steel off
the robot. It only became sound when the print material went from PA12-CF to SLS
PA12: the stub carries the bearing's reaction as bending at its root, which on an
FDM part laid flat is a stack of layer lines in tension at 30 MPa, and is 48 MPa
in any direction once the material is isotropic. cad/parameters.py carries the
arithmetic and what about it is still unquantified.

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
)

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


def jointHardware() -> list:
    """One straddled joint's worth of bought metal, which is one bearing.

    Still a list, and still called from the same places, because what a joint
    needs from this module is "the bought parts at it" rather than "the bearing"
    -- and because it was two bodies until the journal was printed instead.
    """
    return [bearing()]
