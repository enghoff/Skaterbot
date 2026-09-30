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

# Depth was the one section dimension the two pelvises agreed on, at 68 mm, and
# the wheeled one has now left that behind as well. 68 was the actuators'
# fore-and-aft envelope and nothing else, which was right while the cavity held
# nothing but boards lying flat. THE BATTERY MADE IT A REQUIREMENT RATHER THAN A
# LEFTOVER: two 3S packs on edge are 52 mm across the robot, and the four ledges
# the electronics deck lands on stand 5 mm proud of these walls, so a 68 mm
# shell leaves the packs and the ledges a tenth of a millimetre apart. 72 opens
# that to 1.6 mm. The four millimetres are checked rather than assumed -- this
# floor is what a thigh swings under, and tools/gate_f.py measures that clearance
# in the pose and squat scenes.
#
# Width is each pelvis' own business and is in cad/wheeled_parameters.py.
torsoShellDepth = 72.0

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

# THE BOSSES STAND BELOW THE LID'S LIP, September 2026, and until then the lid
# could not be fitted at all. They stood down from the shell's top face flush
# with it, and the lip drops 2.4 mm into the cavity across its whole plan -- so
# each corner of the lip landed on a boss's top, 124 mm3 of them sharing space,
# and the lid rode on the four bosses instead of sitting on the rim. The first
# printed prototype is what found it. Nothing measured it: gate F compared a
# hand-picked list of the torso's contents and the lid was never on it, which
# is why tools/gate_h.py now sweeps every part against every other.
#
# The bosses came down rather than the lip being notched, because the lid had
# already been printed and the pelvis was being reprinted anyway. Each keeps its
# full 12 mm and stops this far under the lip, the same air the electronics
# deck's corner notches pass the same bosses with. The lid sits on the rim and
# its screws pull it down onto it across that gap: an M3 x 10 through the lid's
# 4.8 mm and the 0.4 of air has 4.8 mm of boss to cut its thread in.
coverLipBossClearance = 0.4
coverBossDrop = coverLipHeight + coverLipBossClearance


def coverBossInset(innerSpan: float) -> float:
    """Where the four cover screws land, as an inset from the cavity's corners.

    The boss and the hole through the lid have to agree on this, and they are
    built by two different functions, so it is computed once here.
    """
    return innerSpan / 2 - (bossSize / 2)


def coverBoss(x: float, y: float, topZ: float):
    """One tapped boss hanging in a corner of the cavity, under the lid's lip.

    Four of these carry the lid, and they are part of whichever pelvis calls for
    them rather than parts in their own right. `topZ` is the shell's top face;
    the boss's own top is coverBossDrop below it.
    """
    bossCenterZ = topZ - coverBossDrop - (bossHeight / 2)

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
