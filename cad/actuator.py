"""The DM-J3507-2EC actuator, as the plain cylinder it is to the structure.

Ported from actuator.kcl. A Ø46 x 37.9 body on the joint axis and nothing else:
the mounting interface it presents is drawn by cad/joint.py, and the vendor STEP
in reference/ is the authority on everything this proxy leaves out. Importing the
real STEP instead of approximating it is a phase 3 item.
"""

from __future__ import annotations

from build123d import Cylinder

from cad.parameters import actuatorDepth, actuatorDiameter


def actuatorAssembly() -> list:
    """One motor body, axis along Z, centred on the joint."""
    return [Cylinder(actuatorDiameter / 2, actuatorDepth)]
