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

from build123d import Box, Cone, Cylinder, Plane, Pos, Rot

from cad.electronics import (
    batteryFenceThickness,
    batteryFenceTopZ,
    batteryFenceY,
    batteryPackGap,
    batteryPackLeftX,
    batteryPackRightX,
    batteryRailStopHeight,
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
    deckScrewY,
    deckZ,
    imuBoardDepth,
    imuBoardWidth,
    imuDepth,
    imuWidth,
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
    cheekThickness,
    hipCenterX,
    hoistLugEyeChamfer,
    hoistLugHeight,
    hoistLugHoleDiameter,
    hoistLugHoleDrop,
    hoistLugHoleInset,
    hoistLugLap,
    hoistLugLength,
    hoistLugProud,
    hoistLugTaper,
    jointKeepOut,
    m2Clearance,
    m25Pilot,
    rearCheekX,
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
# deck this wall is fuller than ever: the deck's own ledges stand on it, and it
# now CARRIES the bus monitor as well, on the two pads below -- 0.75 mm of air
# between that board and this wall. A bare prism could thread between those; the
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
#
# EACH RAIL STANDS JUST OUTBOARD OF THE IMU'S RESERVATION, since 2026-09-30, when
# the packs went from 25 mm thick to 17 and a rail at y = 20 would have stood
# outside the pack it carries. At the packs' own centre lines the rails would
# have run 3 mm into the 22 x 22 the IMU is reserved; touching that reservation
# from outside, they are under the middle of any pack from 13 mm thick to 22.
#
# AND THEY START AT THE LEFT HIP SADDLE'S INBOARD FACE, not at the left wall. The
# saddle's top is the band's floor for its whole length and carries the packs
# itself; under that top the saddle is hollow, drained through its two walls,
# and a rail run through the hollow at this station walls its middle off into a
# sealed void -- tools/check.py refused the pelvis for exactly that. At y = 20
# the rails ran outside the saddle's walls and never met it.
batteryRailThickness = 3.0
batteryRailY = (imuDepth + batteryRailThickness) / 2
batteryRailStartX = -(hipCenterX + rearCheekX - cheekThickness / 2)
batteryRailEndX = batteryX + (batteryWidth / 2)

# THE STRAP SLOTS ARE GONE, 2026-09-30. Each rail carried two, for two cinch
# straps that were to go down through the front rail, under the packs and up
# through the rear one, and neither route was ever open: measured, the left one
# led into the hip saddle and the right one into the CAN loom and the actuator
# harness runs, and no 20 mm strap lane anywhere along the packs cleared the
# looms, the deck ledges and the saddle by a millimetre. What holds the packs is
# cad/electronics.py's hold-down, and the straps came off docs/BOM.md with the
# slots.
#
# WHAT EACH RAIL CARRIES INSTEAD is the packs' right-hand end stop: a block on the
# rail's own end that stands into the foot of the pack's end face, from the pack's
# end to the rail's, and no higher than batteryRailStopHeight, so the leads that
# leave the top of that face have it to themselves.

# THE BATTERY'S FIN AND FENCES, which make each pack a slot of its own that it is
# pushed down into by hand before anything else goes in over it. They hung from
# the deck for a day, 2026-09-30, and cad/electronics.py's hold-down block says
# why they came down here.
#
# THE FENCES STAND ON THE SHELL FLOOR FOR THEIR WHOLE LENGTH. The left hip
# saddle's top is only 30 mm wide -- its bounding box reaches 26 mm either side
# of the centre line, and its top reaches 15 -- so at y = 21 there is 9 mm of air
# over the floor all along the saddle. They were first drawn standing on that
# top, and for 45 mm of their 75 they stood on nothing: each hung off the 30 mm
# that did reach the floor, and every gate passed it. tools/gate_f.py now
# checks that everything standing in this cavity rests on the pelvis under the
# whole of its underside.
#
# THE FIN STANDS ON THE SADDLE'S TOP over the saddle's length, which is solid
# at the centre line, and on the floor from the saddle's inboard face on, as the
# rails do -- never down through the saddle, whose hollow a body run through it
# would wall off into a sealed void. It stops where the IMU's reservation
# begins, so it covers the packs' first 60 mm and leaves the square of floor the
# IMU stands in as it was.
batteryFinEndX = -(imuWidth / 2)

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
# This said they pass through the hip saddle and are left interpenetrating. They
# do not: measured, they share no material with the saddle or anything else, and
# stand on the floor face to face. That is fine in the single solid the piece is
# exported as now, and it is how three of the four went missing from the first
# print, when the piece was exported as separate bodies.
boardPostSize = 8.0
powerPostX = pdbHolePitch / 2
powerPostY = pdbHolePitch / 2

# THE DECK LEDGES stand on the four stations cad/electronics.py names, because
# cad/deck.py's plate has to land on the same four. Both they and the posts above
# are PILOTED rather than inserted: 5 mm of pad will not sink a 5.7 mm insert.
# The posts take a self-tapping M3 in the same Ø2.5 the cover bosses use; the
# ledges take an M2.5 since September 2026, because no M3 head fits between the
# screw and the wall -- cad/parameters.py's m25Clearance says so.

bossX = coverBossInset(torsoInnerWidth)
bossY = coverBossInset(torsoInnerDepth)


def _piloted(
    block,
    atX: float,
    atY: float,
    topZ: float,
    depth: float,
    diameter: float = bossHoleDiameter,
):
    """A printed pad or post with a pilot hole down its top face.

    The bore is taken out of the body it belongs to and NOTHING IS UNIONED ON
    afterwards, which is the rule cad/electronics.py's board() follows for the
    same reason: this part is a list of interpenetrating bodies, and a body
    unioned over a pilot would fill it back in with nothing to report it but
    tools/gate_e.py's count.

    The diameter is an argument because ONE mount on this part is not an M3. The
    bus monitor's holes are 2.5 mm in from the board's own edge, which an M3
    clearance hole would break straight out of, so its two pads are piloted Ø1.7
    for an M2 -- see cad/electronics.py.
    """
    bore = Pos(atX, atY, topZ - (depth / 2) + 0.5) * Cylinder(diameter / 2, depth + 1.0)
    return block - bore


def batteryRails() -> list:
    """The two rails the packs sit on, laid across the robot, and their end stops.

    They start at the left hip saddle's inboard face and stop at the battery
    bay's own inboard end, so the bay gap beyond it is clear to the floor. Each
    rail and its stop overlap rather than touch, so they are one body the moment
    they are united.
    """
    railLength = batteryRailEndX - batteryRailStartX
    railCenterX = (batteryRailEndX + batteryRailStartX) / 2
    railHeight = lowerBandZ - cavityBottomZ
    stopLength = batteryRailEndX - batteryPackRightX
    stopHeight = railHeight + batteryRailStopHeight
    rails = []
    for sy in (1, -1):
        rail = Pos(
            railCenterX, sy * batteryRailY, cavityBottomZ + railHeight / 2
        ) * Box(railLength, batteryRailThickness, railHeight)
        stop = Pos(
            batteryRailEndX - stopLength / 2,
            sy * batteryRailY,
            cavityBottomZ + stopHeight / 2,
        ) * Box(stopLength, batteryRailThickness, stopHeight)
        rails.append(rail + stop)
    return rails


def batteryCradle() -> list:
    """The two fences and the fin the packs stand between: front fence, rear
    fence, fin.

    Each fence is one box standing on the shell floor from end to end. The fin
    is one body drawn as two lengths that meet at the saddle's inboard face --
    one standing on the saddle's top, one on the shell floor -- so it is as tall
    as what it stands on allows and no taller.
    """
    fenceHeight = batteryFenceTopZ - cavityBottomZ
    fences = [
        Pos(
            (batteryPackLeftX + batteryPackRightX) / 2,
            sy * (batteryFenceY + batteryFenceThickness / 2),
            cavityBottomZ + fenceHeight / 2,
        )
        * Box(batteryPackRightX - batteryPackLeftX, batteryFenceThickness, fenceHeight)
        for sy in (1, -1)
    ]
    finOnSaddle = Pos(
        (batteryPackLeftX + batteryRailStartX) / 2,
        0.0,
        (lowerBandZ + batteryFenceTopZ) / 2,
    ) * Box(
        batteryRailStartX - batteryPackLeftX,
        batteryPackGap,
        batteryFenceTopZ - lowerBandZ,
    )
    finOnFloor = Pos(
        (batteryRailStartX + batteryFinEndX) / 2,
        0.0,
        cavityBottomZ + fenceHeight / 2,
    ) * Box(batteryFinEndX - batteryRailStartX, batteryPackGap, fenceHeight)
    return [*fences, finOnSaddle + finOnFloor]


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


# THE POWER SWITCH BOARD USED TO NEED A PAD HERE, one printed block off the
# right-hand wall carrying a third screw, because that board was a rectangle over
# the rear half of the bought board and two screws on one edge are a hinge. It is
# the bought board's own 50 x 50 footprint now and takes all four of that board's
# screws, so the pad is gone and this bay costs the robot no printed material at
# all. cad/electronics.py's power switch section says why the board grew.


def hoistLugs() -> list:
    """The two lugs the robot is hung and caught by, one on each flank.

    A development fitting rather than a part of the machine, and printed in
    anyway because there is nowhere else on this box to put it: everything a
    bracket could bolt to is inside the cavity mouth, and the mouth has to stay
    clear. cad/parameters.py carries the argument.

    The relief under the outboard corner is cut from the LUG and not from the
    finished list, which matters: the plane it lies on crosses the side wall
    lower down, so a cutter taken out of the whole part would gouge the shell
    35 mm below the lug. It is taken here, where the only body it can reach is
    the one it belongs to.
    """
    flankX = torsoShellWidth / 2
    lugCenterX = flankX + (hoistLugProud - hoistLugLap) / 2
    lugWidth = hoistLugProud + hoistLugLap
    lugCenterZ = shellTopZ - hoistLugHeight / 2

    # The 45 degree plane, written as the corner it starts from: out at the
    # outboard face, up by the taper, and in along the bottom face by the same.
    cornerX = flankX + hoistLugProud
    cornerZ = shellTopZ - hoistLugHeight
    reliefX = (cornerX + (cornerX - hoistLugTaper)) / 2
    reliefZ = (cornerZ + (cornerZ + hoistLugTaper)) / 2
    reach = lugWidth + hoistLugHeight
    step = reach / (2**0.5)

    lug = Pos(lugCenterX, 0, lugCenterZ) * Box(lugWidth, hoistLugLength, hoistLugHeight)
    lug -= (
        Pos(reliefX + step / 2, 0, reliefZ - step / 2)
        * Rot(0, 45, 0)
        * Box(reach, hoistLugLength + 4.0, reach)
    )
    eyeX = flankX + hoistLugHoleInset
    eyeZ = shellTopZ - hoistLugHoleDrop
    eyeRadius = hoistLugHoleDiameter / 2
    lug -= (
        Pos(eyeX, 0, eyeZ) * Rot(90, 0, 0) * Cylinder(eyeRadius, hoistLugLength + 4.0)
    )

    # The two mouths, broken 45 degrees out to Ø8. Cut here and not by
    # cad/finish.py, which takes outer edges only and so never sees the rim of a
    # bore -- see cad/parameters.py. The cone's wide end sits in the end face and
    # its narrow end meets the bore a millimetre in, so the two together are one
    # continuous surface for a rope to turn over.
    mouthRadius = eyeRadius + hoistLugEyeChamfer
    for sy in (1, -1):
        lug -= (
            Pos(eyeX, sy * (hoistLugLength - hoistLugEyeChamfer) / 2, eyeZ)
            * Rot(sy * 90, 0, 0)
            * Cone(mouthRadius, eyeRadius, hoistLugEyeChamfer)
        )
    return [lug, mirrored(lug, Plane.YZ)]


def deckLedges() -> list:
    """Four pads on the front and rear walls, carrying cad/deck.py's plate.

    Piloted for an M2.5 at deckScrewY rather than an M3 on the ledge's centre
    line, and THROUGH the ledge rather than blind: cad/electronics.py says why
    on both counts.
    """
    ledges = []
    for sx in (1, -1):
        for sy in (1, -1):
            atX = sx * deckLedgeX
            block = Pos(atX, sy * deckLedgeY, deckZ - deckLedgeHeight / 2) * Box(
                deckLedgeWidth, deckLedgeDepth, deckLedgeHeight
            )
            ledges.append(
                _piloted(
                    block,
                    atX,
                    sy * deckScrewY,
                    deckZ,
                    deckLedgeHeight + 1.0,
                    diameter=m25Pilot,
                )
            )
    return ledges


def pelvisShell() -> list:
    """The shell, its four cover bosses and both hip clevises: one printed part.

    Twenty-five bodies now, drawn separately. KCL-SHAPED: the engine refused to
    union hollow boxes that meet at right angles, and the hip saddles are
    exactly that case, so the pieces were drawn -- and until September 2026
    exported -- as bodies laid into one another.

    THE DOCSTRING HERE USED TO SAY every overlap was several millimetres of real
    solid, so a slicer would merge them. That was true of the saddles and the
    hoist lugs and of nothing else: the posts, rails, guides and IMU seat stand
    on the floor and the bosses and ledges against the walls, face to face,
    sharing no material at all, and the first printed pelvis came back without
    all but one of them. tools/export.py unites the bodies into one solid before
    writing the file, tools/check.py fails an edit that leaves one that will not
    unite, and tools/gate_g.py reads back the file a printer would get.
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
    # THE SIZE WAS THE DISCONNECT'S NUTS' DOING and the disconnect is gone: its
    # nuts sat 2.25 mm from its body, which an M2 cleared and an M2.5 did not,
    # and that pair is what set M2 for the whole wall. The charge socket would
    # take an M2.5 happily and keeps M2 anyway, because one thread size on one
    # wall is worth more than a quarter millimetre of bridge. THE THINNEST
    # MATERIAL ON THIS WALL WENT WITH THE DISCONNECT: it was the 1.45 mm between
    # each of its ear screws and its cutout, and what is left is the charge
    # socket's own 1.7. The button that replaced it needs no screws at all --
    # it clamps the wall with its own nut -- so tools/gate_e.py counts two holes
    # here now and not four.
    panelFixings = [
        Pos(atX, panelWallY, atZ)
        * Rot(90, 0, 0)
        * Cylinder(m2Clearance / 2, shellWall + 4.0)
        for atX, atZ in chargeSocketFixings()
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
        *batteryCradle(),
        *powerEntryPosts(),
        *deckLedges(),
        *bmsGuides(),
        *hoistLugs(),
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
