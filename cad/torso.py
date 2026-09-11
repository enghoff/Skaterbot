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

from build123d import Box, Cylinder, Plane, Pos

from cad.electronics import (
    balancePortHeight,
    balancePortWidth,
    balancePortZ,
    batteryWidth,
    batteryX,
    boardHoleInset,
    deckLedgeDepth,
    deckLedgeHeight,
    deckLedgeWidth,
    deckLedgeX,
    deckLedgeY,
    deckZ,
    disconnectZ,
    interiorHalfWidth,
    leadChaseX,
    lowerBandZ,
    powerDepth,
    powerWidth,
    powerX,
    xt90Length,
    xt90Width,
)
from cad.geometry import mirrored
from cad.joint import saddleHeight, statorClevis
from cad.parameters import (
    hipCenterX,
    jointKeepOut,
    shellWall,
    torsoCoverThickness,
    torsoFloorThickness,
)
from cad.torso_shell import (
    bossHoleDiameter,
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

# ---- the service panel ------------------------------------------------------
#
# THE UMBILICAL IS GONE. From August 2026 this wall carried a 12 mm tether slot
# and two cable-tie slots either side of it, because the robot had no battery and
# 24 V and CAN came in from a bench supply down one cable. The battery came back
# in September 2026 -- cad/electronics.py says how and why -- and what the wall
# carries instead is the three things a pack needs brought outside: the main
# disconnect and one balance port per 3S brick.
#
# The strain relief went with the tether and is not missed. A cable tie carrying
# a moving umbilical's pull in shear through 2.4 mm of wall was solving a problem
# this robot no longer has: nothing now pulls on this wall at all, because
# everything it connects to is inside the shell.
#
# EVERY CUT IS STILL RECTANGULAR, and now for a reason of its own rather than an
# engine's: an XT90-S housing and a JST-XH shell are both rectangular mouldings,
# so a round hole would have to be bigger than either to pass it. The cutouts are
# the connector bodies plus half a millimetre all round, which means they are
# only as good as the catalogue figures in cad/electronics.py -- measure the
# connectors before this part is printed, because a panel cutout is the one thing
# that cannot be adjusted afterwards.
panelClearance = 0.5
disconnectPortWidth = xt90Length + (panelClearance * 2)
disconnectPortHeight = xt90Width + (panelClearance * 2)
disconnectPortZ = disconnectZ + (xt90Width / 2)
balanceSlotWidth = balancePortWidth + (panelClearance * 2)
balanceSlotHeight = balancePortHeight + (panelClearance * 2)
balanceSlotZ = balancePortZ + (balancePortHeight / 2)
balanceSlotX = balancePortWidth / 2 + 1.5
# Negative Y is the rear: the foot's front pressure pads sit at y = +51 and its
# rear pads at y = -40, and the leading leg swings to +Y.
panelWallY = -(torsoShellDepth / 2 - (shellWall / 2))

# ---- what stands inside ------------------------------------------------------
#
# Three sets of printed features that did not exist while the cavity held nothing
# but boards lying in reserved volumes. A reserved volume says where a thing may
# be and nothing about what holds it there, and this is the other half of that
# answer.
#
# THE BATTERY RAILS. The packs sit at the saddle top, which is a plane the hip
# clevises define and only occupy between |x| = 26 and 60. Under the rest of the
# battery there is a 9 mm drop to the shell floor, so two rails carry it across.
# THEY RUN ACROSS THE ROBOT AND NOT ALONG IT, which is the whole point: rails
# laid fore and aft would wall off the square of floor between the hip saddles,
# and that square is where the IMU goes. Laid this way they leave it open and
# leave the actuator harnesses a clear run along the back of the cavity as well.
batteryRailThickness = 3.0
batteryRailY = 20.0
batteryRailEndX = batteryX + (batteryWidth / 2)

# THE POWER-ENTRY POSTS. Four, on the board's own corner pattern, standing from
# the shell floor to the plane its standoffs sit on. They pass through the hip
# saddle where they meet it and are left interpenetrating, like everything else
# on this part.
boardPostSize = 8.0
powerPostX = (powerWidth / 2) - boardHoleInset
powerPostY = (powerDepth / 2) - boardHoleInset

# THE DECK LEDGES stand on the four stations cad/electronics.py names, because
# cad/deck.py's plate has to land on the same four. Both they and the posts above
# are PILOTED rather than inserted, at the same Ø2.5 the cover bosses have always
# used for a self-tapping M3: 5 mm of pad will not sink a 5.7 mm insert, and this
# project already stocks the screw.

bossX = coverBossInset(torsoInnerWidth)
bossY = coverBossInset(torsoInnerDepth)


def _piloted(block, atX: float, atY: float, topZ: float, depth: float):
    """A printed pad or post with a pilot hole down its top face.

    The bore is taken out of the body it belongs to and NOTHING IS UNIONED ON
    afterwards, which is the rule cad/electronics.py's board() follows for the
    same reason: this part is a list of interpenetrating bodies, and a body
    unioned over a pilot would fill it back in with nothing to report it but
    tools/gate_e.py's count.
    """
    bore = Pos(atX, atY, topZ - (depth / 2) + 0.5) * Cylinder(
        bossHoleDiameter / 2, depth + 1.0
    )
    return block - bore


def batteryRails() -> list:
    """The two rails the packs sit on, laid across the robot.

    They start at the left wall and stop at the battery's own inboard end, so
    the lead chase beyond it is clear to the floor.
    """
    railLength = batteryRailEndX + interiorHalfWidth
    railCenterX = (batteryRailEndX - interiorHalfWidth) / 2
    railHeight = lowerBandZ - cavityBottomZ
    return [
        Pos(railCenterX, sy * batteryRailY, cavityBottomZ + railHeight / 2)
        * Box(railLength, batteryRailThickness, railHeight)
        for sy in (1, -1)
    ]


def powerEntryPosts() -> list:
    """Four posts from the shell floor to the power-entry board's standoffs."""
    postHeight = lowerBandZ - cavityBottomZ
    posts = []
    for sx in (1, -1):
        for sy in (1, -1):
            atX = powerX + sx * powerPostX
            atY = sy * powerPostY
            block = Pos(atX, atY, cavityBottomZ + postHeight / 2) * Box(
                boardPostSize, boardPostSize, postHeight
            )
            posts.append(_piloted(block, atX, atY, lowerBandZ, postHeight - 1.0))
    return posts


def deckLedges() -> list:
    """Four pads on the front and rear walls, carrying cad/deck.py's plate."""
    ledges = []
    for sx in (1, -1):
        for sy in (1, -1):
            atX = sx * deckLedgeX
            atY = sy * deckLedgeY
            block = Pos(atX, atY, deckZ - deckLedgeHeight / 2) * Box(
                deckLedgeWidth, deckLedgeDepth, deckLedgeHeight
            )
            ledges.append(_piloted(block, atX, atY, deckZ, deckLedgeHeight - 1.0))
    return ledges


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

    disconnectPort = Pos(leadChaseX, panelWallY, disconnectPortZ) * Box(
        disconnectPortWidth, shellWall + 4.0, disconnectPortHeight
    )
    balanceSlots = [
        Pos(leadChaseX + sx * balanceSlotX, panelWallY, balanceSlotZ)
        * Box(balanceSlotWidth, shellWall + 4.0, balanceSlotHeight)
        for sx in (1, -1)
    ]

    # KCL-SHAPED: slots first, into the simple box, then the cavity. Taking them
    # out of the already-hollowed shell is the ordering the engine rejects, and it
    # is the same ordering the keel needed when the tether entered through that.
    shellSlotted = shellBlank
    for cutter in [*cablePorts, disconnectPort, *balanceSlots]:
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
        *batteryRails(),
        *powerEntryPosts(),
        *deckLedges(),
    ]


def torsoCover():
    """The lid: one print of its own, the shared design drawn to this box."""
    return torsoLid(torsoShellWidth, torsoShellDepth, shellTopZ)


def torsoAssembly() -> list:
    return [*pelvisShell(), torsoCover()]
