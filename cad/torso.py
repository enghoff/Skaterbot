"""The six-motor pelvis: one closed box from the hip pitch axes to the cover.

Ported from torso.kcl.

Every station is derived from the kinematics rather than typed in, so moving the
hip pitch axis or the actuator diameter moves the whole shell with it. The floor
is one joint keep-out above hip pitch and nothing else; the torso bottom follows
it rather than the other way round.

The shell is now exactly as wide as the joints it carries. Each hip clevis ends
at its front cheek's outer face, 76.95 mm from the centre line, and
cad/wheeled_parameters.py builds the shell's width on that plane rather than on
the payload, so the saddle runs out flush with the flank instead of standing
6.45 mm proud of it. The only hardware outside that plane is the two Ø26 bearing
bosses, at 80.45, and the wheels at 104.
"""

from __future__ import annotations

from build123d import Box, Cylinder, Plane, Pos, Rot

from cad.electronics import (
    batteryWidth,
    batteryX,
    bmsGuideDepth,
    bmsGuideSlot,
    bmsGuideSlotDepth,
    bmsGuideWidth,
    bmsGuideY,
    bmsX,
    bmsZ,
    chargeSocketFixings,
    deckLedgeDepth,
    deckLedgeHeight,
    deckLedgeWidth,
    deckLedgeX,
    deckLedgeY,
    deckZ,
    disconnectFlangeFixings,
    imuBoardDepth,
    imuBoardWidth,
    interiorHalfWidth,
    lowerBandZ,
    panelWallY,
    pdbHolePitch,
    pdbY,
    powerX,
    rearWallCutouts,
)
from cad.geometry import mirrored
from cad.joint import saddleHeight, statorClevis
from cad.parameters import (
    hipCenterX,
    jointKeepOut,
    m2Clearance,
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
# carries instead is the two things a pack needs brought outside: the main
# disconnect, and a charge port ahead of it.
#
# IT CARRIED THREE UNTIL THE BMS WENT IN. The third was a 7-way balance port for
# the whole 6S string -- itself two 4-way ports joined into one inside the shell,
# so a bench charger saw the single 6S pack the pair are wired as and finished in
# one session. A balancing BMS now sits on those same seven cell taps
# permanently, so the socket presented nothing the board inside does not already
# hold, and a second path to the cells is a thing to insulate rather than a
# convenience. It went, and this wall gained 703 mm3 of shell back.
#
# The charge port stays and is now the only way in: the bus has to be dead while
# the cells charge, so a charger cannot come in through the disconnect.
#
# The strain relief went with the tether and is not missed. A cable tie carrying
# a moving umbilical's pull in shear through 2.4 mm of wall was solving a problem
# this robot no longer has: nothing now pulls on this wall at all, because
# everything it connects to is inside the shell.
#
# THE CONNECTORS ARE BACK IN THIS WALL, AND THE PRINTED PANEL IS GONE. For a
# fortnight this wall carried three coarse apertures and four screw holes, and a
# 6 mm plate behind it held the connectors, because the three fitted then -- an
# XT90-S, a JST-XH and an XT30 -- are constant-section prisms that no cut in
# 2.4 mm of shell can capture. That argument was right and is kept in
# cad/electronics.py. What answered it in the end was not a printed part but
# different hardware: a male and a female XT60 that each bolt through this wall
# by their own ears or flange, and an antenna bushing that clamps it between a
# shoulder and a nut.
#
# So the wall carries its holes again -- one per part, plus two for each XT60's
# screws -- and this pelvis is the only printed piece involved.
# There is no bonded joint anywhere on the robot now.
#
# THEY ALL SIT ABOVE THE ELECTRONICS DECK, at z = 22, which is new. Below the
# deck this wall is full: the bus monitor comes within 12.6 mm of it and the
# deck's own ledges stand on it. A bare prism could thread between those; the
# GX16 bushing whose nut wanted a clear 22 mm circle could not, and it is what
# first put the row up here. It has gone, and the row has stayed: every station
# on it is now solved against the cavity, and cad/electronics.py has the
# measurements.

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

# AND THE RAILS CARRY THE STRAPS, which until now had nowhere to go. docs/BOM.md
# buys two hook-and-loop cinch straps for the packs and the shell offered them
# nothing to pass through, so they could only be wrapped round the cells and left
# to slide. A slot through each rail anchors them: a strap goes down through the
# front rail, under the packs in the 9 mm the saddle rise leaves, up through the
# rear rail and over the top.
#
# They are NOT what holds the packs in flight -- cad/deck.py's plate bearing on
# 3 mm of squeeze is, and tools/gate_f.py measures it. These are for when the
# deck is off, which is whenever anyone is working in this bay.
strapSlotWidth = 16.0
strapSlotHeight = 3.0
strapSlotX = (-55.0, -15.0)

# THE IMU SEAT. The one board in this torso small enough that no screw will fit
# it -- a BNO085 Nano breakout is 11 x 10 -- and the one board whose ORIENTATION
# is half its value. Adhesive holds it down and three ribs decide where it
# points; the fourth side is left open to the rear, which is where its flylead
# leaves to join the harness run along the back of the cavity.
#
# It sits in the square of floor between the two hip saddles, which is the
# stiffest spot in the pelvis and the reason the battery rails were laid across
# the robot rather than along it.
imuSeatClearance = 0.2
imuSeatWall = 1.5
imuSeatHeight = 2.5


# THE DISTRIBUTION-BOARD POSTS. Four, standing from the shell floor to the plane
# the board's standoffs sit on, and THE PATTERN IS THE BOARD'S RATHER THAN OURS:
# a 45 mm square, read off the SwiftWing datasheet. That is the difference the
# bought board makes to this part -- these four posts have to be where somebody
# else decided, and if the board is ever swapped they move.
#
# They pass through the hip saddle where they meet it and are left
# interpenetrating, like everything else on this print.
boardPostSize = 8.0
powerPostX = pdbHolePitch / 2
powerPostY = pdbHolePitch / 2

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
    the lead chase beyond it is clear to the floor. Each carries two strap slots
    at mid-height, cut out of the rail itself and nothing unioned on after.
    """
    railLength = batteryRailEndX + interiorHalfWidth
    railCenterX = (batteryRailEndX - interiorHalfWidth) / 2
    railHeight = lowerBandZ - cavityBottomZ
    slotZ = cavityBottomZ + railHeight / 2
    rails = []
    for sy in (1, -1):
        rail = Pos(
            railCenterX, sy * batteryRailY, cavityBottomZ + railHeight / 2
        ) * Box(railLength, batteryRailThickness, railHeight)
        for atX in strapSlotX:
            rail -= Pos(atX, sy * batteryRailY, slotZ) * Box(
                strapSlotWidth, batteryRailThickness + 4.0, strapSlotHeight
            )
        rails.append(rail)
    return rails


def bmsGuides() -> list:
    """Two slotted guides the battery management board's lower edge drops into.

    The slot is taken out of the guide it belongs to and NOTHING IS UNIONED ON
    afterwards, which is this part's rule everywhere: a body unioned over a slot
    would close it with nothing to report it.
    """
    guideHeight = bmsZ - cavityBottomZ
    guides = []
    for atY in bmsGuideY:
        block = Pos(bmsX, atY, cavityBottomZ + (guideHeight / 2)) * Box(
            bmsGuideWidth, bmsGuideDepth, guideHeight
        )
        slot = Pos(bmsX, atY, bmsZ - (bmsGuideSlotDepth / 2)) * Box(
            bmsGuideSlot, bmsGuideDepth + 2.0, bmsGuideSlotDepth
        )
        guides.append(block - slot)
    return guides


def imuSeat() -> list:
    """Three ribs on the shell floor that decide which way the IMU faces.

    One body, and it is a block with a pocket taken out of it rather than three
    ribs drawn separately: the pocket runs out through the rear face, which is
    what leaves that side open for the flylead.
    """
    pocketWidth = imuBoardWidth + (imuSeatClearance * 2)
    pocketDepth = imuBoardDepth + (imuSeatClearance * 2)
    blockDepth = pocketDepth + imuSeatWall
    blockCenterY = (pocketDepth + imuSeatWall) / 2 - (pocketDepth / 2)
    block = Pos(0, blockCenterY, cavityBottomZ + (imuSeatHeight / 2)) * Box(
        pocketWidth + (imuSeatWall * 2), blockDepth, imuSeatHeight
    )
    # Taken out towards -Y and beyond the block, so the rear rib is never drawn.
    pocket = Pos(
        0,
        (pocketDepth / 2) - (pocketDepth + blockDepth) / 2,
        cavityBottomZ + (imuSeatHeight / 2),
    ) * Box(pocketWidth, pocketDepth + blockDepth, imuSeatHeight + 2.0)
    return [block - pocket]


def powerEntryPosts() -> list:
    """Four posts from the shell floor to the distribution board's standoffs."""
    postHeight = lowerBandZ - cavityBottomZ
    posts = []
    for sx in (1, -1):
        for sy in (1, -1):
            atX = powerX + sx * powerPostX
            atY = pdbY + sy * powerPostY
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

    # WHAT THE REAR WALL IS CUT FOR, AND IT IS THE HARDWARE ITSELF NOW. One hole
    # per bought part -- a rectangle for the XT60E-M's nose, a rectangle for the
    # XT60E-F's body, a round hole for the antenna's bushing -- plus two
    # clearance holes for each XT60's screws. A round hole is square in
    # cad/electronics.py's table, which is why this is the one place that has to
    # tell them apart.
    panelCutouts = []
    for _, atX, atZ, width, height in rearWallCutouts():
        if width == height:
            panelCutouts.append(
                Pos(atX, panelWallY, atZ)
                * Rot(90, 0, 0)
                * Cylinder(width / 2, shellWall + 4.0)
            )
        else:
            panelCutouts.append(
                Pos(atX, panelWallY, atZ) * Box(width, shellWall + 4.0, height)
            )

    # The two XT60s' four screws, and they are M2 where everything else on this
    # robot is M3. Each connector is clamped to the wall by its own ears or
    # flange and a nut, so this wall is clamped rather than threaded. That is
    # what a panel-mount part buys over a bonded one -- 2.4 mm of shell will not
    # hold a thread, and the printed panel that used to carry these needed 6 mm
    # of plate to tap into.
    #
    # THE SIZE IS THE DISCONNECT'S NUTS' DOING: they sit 2.25 mm from its body,
    # which an M2 clears and an M2.5 does not. It leaves 1.45 mm of wall between
    # each disconnect screw and its cutout and 1.7 at the charge socket, the
    # thinnest material anywhere on this wall; cad/parameters.py has the reason
    # and tools/gate_e.py counts all four holes on the finished solid.
    panelFixings = [
        Pos(atX, panelWallY, atZ)
        * Rot(90, 0, 0)
        * Cylinder(m2Clearance / 2, shellWall + 4.0)
        for atX, atZ in [*disconnectFlangeFixings(), *chargeSocketFixings()]
    ]

    # KCL-SHAPED: slots first, into the simple box, then the cavity. Taking them
    # out of the already-hollowed shell is the ordering the engine rejects, and it
    # is the same ordering the keel needed when the tether entered through that.
    shellSlotted = shellBlank
    for cutter in [*cablePorts, *panelCutouts, *panelFixings]:
        shellSlotted -= cutter
    shellRaw = shellSlotted - shellCavity

    # No quarter turn: the clevis is used exactly as cad/joint.py draws it, axis
    # across the robot, because a hip pitch joint is what it was drawn for. The
    # saddle lands in the shell floor and, spanning 25.75 to 76.95 against a shell
    # half-width of 76.95, it runs the whole way out through the lower side wall
    # as well -- so this hip's load enters the closed section through two faces
    # rather than one. It now STOPS in that wall's outer face rather than crossing
    # it: the wall is built on this plane, which is what makes the flank flush.
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
        *bmsGuides(),
        # LAST, AND tools/gate_f.py RELIES ON IT. The IMU's seat is the one
        # printed feature in this cavity that stands inside its own reserved
        # volume, so that gate measures the IMU against the shell less this body.
        *imuSeat(),
    ]


def torsoCover():
    """The lid: one print of its own, the shared design drawn to this box."""
    return torsoLid(torsoShellWidth, torsoShellDepth, shellTopZ)


def torsoAssembly() -> list:
    return [*pelvisShell(), torsoCover()]
