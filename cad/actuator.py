"""The DM-J3507-2EC actuator, as the two plain cylinders it is to the structure.

Ported from actuator.kcl. A Ø46 body on the joint axis and nothing else: the
mounting interface it presents is drawn by cad/joint.py, and the vendor STEP in
reference/ is the authority on everything this proxy leaves out. Importing the
real STEP instead of approximating it is a phase 3 item.

WHAT IT GAINED ON 14 SEPTEMBER 2026, AND WHY ONE CYLINDER WAS NOT ENOUGH. The
body is 36.9 mm long and the actuator is 37.9: the Ø30 output register fills the
last millimetre on its own, standing proud of the housing's front face. Drawn as
a single Ø46 x 37.9 cylinder the proxy put solid motor where that step is, which
is the plane the rotor plate seats in -- so the one thing this envelope existed
to answer, where a printed part may and may not be, it answered wrongly at the
only joint face that carries the output torque. cad/parameters.py carries the
measurement beside actuatorOutputProjection and what it cost.

The two bodies abut rather than overlap, and are left as two for the same reason
every assembly here is: nothing downstream needs them unioned.
"""

from __future__ import annotations

from build123d import Cylinder, Pos

from cad.parameters import (
    actuatorDepth,
    actuatorDiameter,
    actuatorHousingDepth,
    actuatorOutputProjection,
    actuatorOutputRegister,
)


def actuatorAssembly() -> list:
    """The housing and the register standing proud of it, axis along Z.

    The three faces are local rather than module-level names on purpose: they
    are stations in the PROXY's own frame, output towards +Z, and nothing
    downstream measures against them. Every scene turns this assembly onto the
    joint axis it belongs to, and cad/joint.py's frame puts the output at +X, so
    a scene's +90 degree turn about Y is what lines the two up.
    """
    rearFace = -actuatorDepth / 2
    outputFace = actuatorDepth / 2
    housingFace = outputFace - actuatorOutputProjection

    housing = Pos(0, 0, (rearFace + housingFace) / 2) * Cylinder(
        actuatorDiameter / 2, actuatorHousingDepth
    )
    register = Pos(0, 0, (housingFace + outputFace) / 2) * Cylinder(
        actuatorOutputRegister / 2, actuatorOutputProjection
    )
    return [housing, register]
