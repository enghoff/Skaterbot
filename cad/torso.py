"""The six-motor pelvis: one closed box from the hip pitch axes to the cover.

Ported from torso.kcl.

Every station is derived from the kinematics rather than typed in, so moving the
hip pitch axis or the actuator diameter moves the whole shell with it. The floor
is one joint keep-out above hip pitch and nothing else; the torso bottom follows
it rather than the other way round.

The hip clevis cheeks are Ø52 discs centred on the leg axes, so they still reach
74 mm from the centre line and the robot is still 148 mm across at the hips. The
joints are the visible hardware, the shell is not.
"""

from __future__ import annotations

from build123d import Box, Plane, Pos

from cad.geometry import mirrored
from cad.joint import saddleHeight, statorClevis
from cad.parameters import (
    hipCenterX,
    jointKeepOut,
    shellWall,
    tetherCableDiameter,
    torsoCoverThickness,
    torsoFloorThickness,
)
from cad.torso_shell import (
    cablePortDepth,
    cablePortWidth,
    cablePortX,
    cablePortY,
    coverBoss,
    coverBossInset,
    torsoLid,
    torsoShellDepth,
)
from cad.wheeled_parameters import (
    wheeledHipPitchAxisHeight,
    wheeledTorsoCenterHeight,
    wheeledTorsoHeight,
    wheeledTorsoShellWidth,
)

torsoShellWidth = wheeledTorsoShellWidth
torsoInnerWidth = torsoShellWidth - (shellWall * 2)
torsoInnerDepth = torsoShellDepth - (shellWall * 2)
floorThickness = torsoFloorThickness

hipPitchZ = wheeledHipPitchAxisHeight - wheeledTorsoCenterHeight
shellFloorZ = hipPitchZ + jointKeepOut
saddleTopZ = shellFloorZ + saddleHeight

shellTopZ = wheeledTorsoHeight / 2 - torsoCoverThickness
shellHeight = shellTopZ - shellFloorZ
shellCenterZ = (shellFloorZ + shellTopZ) / 2
cavityBottomZ = shellFloorZ + floorThickness
cavityLength = shellTopZ + 2.0 - cavityBottomZ

# ---- tether entry -----------------------------------------------------------
#
# There is no battery, so a single umbilical brings 24 V and CAN in from the
# bench. It enters the back of the shell as low as the wall allows, for the two
# reasons the keel used to be the place for it: down here the tether's pull acts
# near the hip axes rather than at the top of a 106 mm lever, and it arrives
# beside the power-entry block instead of crossing the electronics stack above.
#
# Strain relief is a cable tie, not a clamp or a threaded insert. The tie goes
# out through one narrow slot, around the tether inside the shell, and back in
# through the other, so a pull on the cable is carried in shear by 2.4 mm of
# wall and never reaches the terminal. That also keeps every cut on this part
# rectangular, which is the only blind pocket shape the engine will take out of
# this shell.
tetherPortWidth = tetherCableDiameter + 4.0
tetherPortHeight = tetherCableDiameter
# Two millimetres above the cavity's inside floor, so the slot opens into the
# cavity with the shell floor left intact below it.
tetherPortZ = cavityBottomZ + 2.0 + tetherPortHeight / 2
# Negative Y is the rear: the foot's front pressure pads sit at y = +51 and its
# rear pads at y = -40, and the leading leg swings to +Y.
tetherWallY = -(torsoShellDepth / 2 - (shellWall / 2))
tieSlotWidth = 3.0
tieSlotHeight = 8.0
tieSlotX = tetherPortWidth / 2 + 5.0

bossX = coverBossInset(torsoInnerWidth)
bossY = coverBossInset(torsoInnerDepth)


def pelvisShell() -> list:
    """The shell, its four cover bosses and both hip clevises: one printed part.

    Seven bodies, where the eight-motor pelvis needed twelve. KCL-SHAPED: they
    are left as interpenetrating bodies rather than unioned because the engine
    refuses to union hollow boxes that meet at right angles, and the hip saddles
    are exactly that case. Every overlap here is several millimetres of real
    solid, so a slicer that merges coincident shells prints them as the single
    part they are. Unioning them for real is the first item in phase 3.
    """
    shellBlank = Pos(0, 0, shellCenterZ) * Box(
        torsoShellWidth, torsoShellDepth, shellHeight
    )
    shellCavity = Pos(0, 0, cavityBottomZ + cavityLength / 2) * Box(
        torsoInnerWidth, torsoInnerDepth, cavityLength
    )

    # KCL-SHAPED: rectangular rather than round, and deliberately so -- the engine
    # will not take a blind cylindrical pocket out of this box, though it takes a
    # rectangular one happily. A slot suits a cable with a moulded connector
    # better than a grommet hole anyway.
    cablePorts = [
        Pos(sx * cablePortX, cablePortY, shellFloorZ + floorThickness / 2)
        * Box(cablePortWidth, cablePortDepth, floorThickness + 4.0)
        for sx in (1, -1)
    ]

    tetherPort = Pos(0, tetherWallY, tetherPortZ) * Box(
        tetherPortWidth, shellWall + 4.0, tetherPortHeight
    )
    tieSlots = [
        Pos(sx * tieSlotX, tetherWallY, tetherPortZ)
        * Box(tieSlotWidth, shellWall + 4.0, tieSlotHeight)
        for sx in (1, -1)
    ]

    # KCL-SHAPED: slots first, into the simple box, then the cavity. Taking them
    # out of the already-hollowed shell is the ordering the engine rejects, and it
    # is the same ordering the keel needed when the tether entered through that.
    shellSlotted = shellBlank
    for cutter in [*cablePorts, tetherPort, *tieSlots]:
        shellSlotted -= cutter
    shellRaw = shellSlotted - shellCavity

    # No quarter turn: the clevis is used exactly as cad/joint.py draws it, axis
    # across the robot, because a hip pitch joint is what it was drawn for. The
    # saddle lands in the shell floor and, being 51 mm across against a shell
    # half-width of 59, it runs out through the lower side wall as well -- so this
    # hip's load enters the closed section through two faces rather than one.
    rightHipPitchJoint = Pos(hipCenterX, 0, hipPitchZ) * statorClevis()

    # The left hip is the right one reflected, not a second copy of it. The rear
    # cheek carries a relief cut on the actuator's connector flat, and a plain
    # copy would leave that relief facing the same way at both hips -- outboard on
    # one leg, inboard on the other, so that actuator's leads would have to leave
    # towards the centre line and turn back on themselves. Reflecting keeps both
    # reliefs on the rear of their own actuator, which is the same thing as
    # installing the left actuator spun 180 degrees about its own axis.
    leftHipPitchJoint = mirrored(rightHipPitchJoint, Plane.YZ)

    return [
        shellRaw,
        coverBoss(bossX, bossY, shellTopZ),
        coverBoss(-bossX, bossY, shellTopZ),
        coverBoss(bossX, -bossY, shellTopZ),
        coverBoss(-bossX, -bossY, shellTopZ),
        rightHipPitchJoint,
        leftHipPitchJoint,
    ]


def torsoCover():
    """The lid: one print of its own, the shared design drawn to this box."""
    return torsoLid(torsoShellWidth, torsoShellDepth, shellTopZ)


def torsoAssembly() -> list:
    return [*pelvisShell(), torsoCover()]
