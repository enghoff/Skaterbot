"""The printed wheel adapter: output disc, Ø22 spigot, and the plug tying them.

Ported from wheel_adapter.kcl.

The wheel is a bought 80 x 24 mm inline-skate wheel with its two 608 bearings
pulled out, which leaves a clean Ø22 bore straight through the hub. This part
fills that bore, lands the hub flat on the actuator's output disc, and is clamped
there by one M5 on the axis through a Ø30 washer.

Torque crosses that CLAMPED FACE, not the spigot. An M5 at a modest 1 kN preload
on the disc's r11-r18 annulus is worth about 4 Nm of friction against the
actuator's 3 Nm peak. A press fit alone would have depended on how the print came
off the bed, which is not a thing to hang a drive on.
"""

from __future__ import annotations

from build123d import Axis, Cylinder, Pos, Rot

from cad.joint import outputDisc
from cad.parameters import actuatorOutputBoltCircle, rotorHubOuterX
from cad.wheeled_parameters import (
    wheelKeyAccessDiameter,
    wheelSpigotDiameter,
    wheelSpigotInsertBore,
    wheelSpigotInsertDepth,
    wheelSpigotLength,
    wheelSpigotPlugDiameter,
)

spigotInnerX = rotorHubOuterX
spigotOuterX = rotorHubOuterX + wheelSpigotLength
spigotCenterX = (spigotInnerX + spigotOuterX) / 2

# The plug reaches 2 mm back into the disc and 4 mm out past the spigot's root,
# so both joints in the chain are a real overlap rather than a butted face.
plugInnerX = rotorHubOuterX - 2.0
plugOuterX = rotorHubOuterX + 4.0
plugCenterX = (plugInnerX + plugOuterX) / 2

insertOuterX = spigotOuterX
insertInnerX = spigotOuterX - wheelSpigotInsertDepth


def _disc(diameter: float, thickness: float, x: float = 0.0):
    return Pos(x, 0, 0) * Rot(0, 90, 0) * Cylinder(diameter / 2, thickness)


def wheelAdapterRight() -> list:
    """The +X hand, as three interpenetrating bodies.

    KCL-SHAPED, and this one is load-bearing rather than incidental: the plug has
    to stay inside r9.25 or it fills the output screws' own counterbores back in.
    That is the failure this project has already been caught by once, on the
    rotor hub, and it is why the adapter is left as three bodies rather than
    unioned. Ø17 clears the counterbores by half a millimetre.
    """
    adapterDiscRaw = outputDisc()

    spigotBlank = _disc(wheelSpigotDiameter, wheelSpigotLength, spigotCenterX)

    # Six cutters on the output bolt centres, run past both ends of the spigot so
    # that no wall of the cut is coplanar with a face of the body it crosses --
    # docs/KCL_GOTCHAS.md lists coincident walls as a reliable way to have a
    # boolean refused.
    firstKeyCut = (
        Pos(spigotCenterX, actuatorOutputBoltCircle / 2, 0)
        * Rot(0, 90, 0)
        * Cylinder(wheelKeyAccessDiameter / 2, wheelSpigotLength + 4.0)
    )
    spigotAfterKeyAccess = spigotBlank
    for i in range(6):
        spigotAfterKeyAccess -= firstKeyCut.rotate(Axis.X, i * 60)

    insertCutter = _disc(
        wheelSpigotInsertBore,
        wheelSpigotInsertDepth + 2.0,
        insertInnerX + (wheelSpigotInsertDepth + 2.0) / 2 - 2.0,
    )
    spigotRaw = spigotAfterKeyAccess - insertCutter

    plugRaw = _disc(wheelSpigotPlugDiameter, plugOuterX - plugInnerX, plugCenterX)

    return [adapterDiscRaw, spigotRaw, plugRaw]


def wheelAdapterLeft() -> list:
    from build123d import Plane

    from cad.geometry import mirrored

    return [mirrored(body, Plane.YZ) for body in wheelAdapterRight()]
