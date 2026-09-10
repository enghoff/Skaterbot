"""The parts of the torso that are one design at two sizes.

Ported from lib/torso_shell.kcl.

One pelvis is built over this file now: the wheeled robot's, in cad/torso.py,
125 x 68 x 65, hanging its hip PITCH actuators straight off its floor. The
walking robot's was the other -- 118 x 68 x 106, hip ROLL actuators off a floor
51 mm higher, with a keel reaching down between them -- and it went with the
walking robot when that was deleted from this branch.

These stay FUNCTIONS taking a box size rather than becoming fixed bodies, and
that is worth keeping even with one caller. The two pelvises stopped sharing a
section long before they stopped sharing a branch -- the wheeled box is 7 mm
wider and 41 mm shorter -- so what was shared was a DESIGN and not a part: the
same lid on the same four bosses with the same lip and the same four screws,
drawn to whatever box it is closing. The limb is one limb at two lengths for the
same reason, and it still has two callers.
"""

from __future__ import annotations

from build123d import Box, Cylinder, Pos

from cad.parameters import m3Clearance, shellWall, torsoCoverThickness

# The one section dimension the two pelvises still agree on. Depth is set by
# the actuators' fore-and-aft envelope, which neither robot changed; width is
# each pelvis' own business, because the wheeled one grew to fit two boards
# side by side.
torsoShellDepth = 68.0

# Provisional. A cable has to leave each hip actuator and get inside, and this
# slot clears both the saddle and the cheeks on either pelvis. Its exact
# position waits on the mated-plug measurement that Phase 6 is blocked on.
cablePortWidth = 14.0
cablePortDepth = 10.0
cablePortX = 40.0
cablePortY = -28.0

bossSize = 8.0
bossHeight = 12.0
bossHoleDiameter = 2.5
coverLipHeight = 2.4


def coverBossInset(innerSpan: float) -> float:
    """Where the four cover screws land, as an inset from the cavity's corners.

    The boss and the hole through the lid have to agree on this, and they are
    built by two different functions, so it is computed once here.
    """
    return innerSpan / 2 - (bossSize / 2)


def coverBoss(x: float, y: float, topZ: float):
    """One tapped boss standing down from the shell's top face.

    Four of these carry the lid, and they are part of whichever pelvis calls for
    them rather than parts in their own right.
    """
    bossCenterZ = topZ - (bossHeight / 2)

    bossBlank = Pos(x, y, bossCenterZ) * Box(bossSize, bossSize, bossHeight)
    bossHole = Pos(x, y, bossCenterZ) * Cylinder(bossHoleDiameter / 2, bossHeight + 2.0)
    return bossBlank - bossHole


def torsoLid(lidWidth: float, lidDepth: float, topZ: float):
    """The removable lid.

    A plate the size of the box's outside, a lip that drops into the cavity to
    locate it, and four clearance holes onto the bosses.
    """
    innerWidth = lidWidth - (shellWall * 2)
    innerDepth = lidDepth - (shellWall * 2)
    coverCenterZ = topZ + torsoCoverThickness / 2
    coverLipWidth = innerWidth - 0.4
    coverLipDepth = innerDepth - 0.4
    coverLipCenterZ = topZ - (coverLipHeight / 2)
    screwX = coverBossInset(innerWidth)
    screwY = coverBossInset(innerDepth)

    coverPlate = Pos(0, 0, coverCenterZ) * Box(lidWidth, lidDepth, torsoCoverThickness)
    coverLip = Pos(0, 0, coverLipCenterZ) * Box(
        coverLipWidth, coverLipDepth, coverLipHeight
    )

    # KCL-SHAPED: long enough to clear the lip as well as the plate, because a
    # screw hole that stopped inside the lip would be a blind cylindrical pocket,
    # which the engine refuses.
    coverScrewLength = torsoCoverThickness + coverLipHeight + 2.0
    coverScrewZ = topZ - coverLipHeight + (coverLipHeight + torsoCoverThickness) / 2

    coverBlank = coverPlate + coverLip
    for sx in (1, -1):
        for sy in (1, -1):
            coverBlank -= Pos(sx * screwX, sy * screwY, coverScrewZ) * Cylinder(
                m3Clearance / 2, coverScrewLength
            )
    return coverBlank
