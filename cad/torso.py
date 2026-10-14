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

from build123d import Box, Cone, Cylinder, Plane, Polygon, Pos, Rot, extrude

from cad.electronics import (
    antennaHoleDiameter,
    antennaHoleFlatSpan,
    antennaSideY,
    antennaSideZ,
    batteryLeadEndAir,
    batteryPackBodyEndX,
    batteryPackLeadWidth,
    batteryPackOuterY,
    batteryPackRightX,
    batteryPackWidth,
    batteryPadHeight,
    batteryPadHighX,
    batteryPadHighZ,
    batteryPadLowX,
    batteryPadLowZ,
    batteryPadWidth,
    batteryRailStopHeight,
    chargeInletFixings,
    chargeInletKeyRadius,
    chargeInletProfile,
    deckLedgeDepth,
    deckLedgeHeight,
    deckLedgeWidth,
    deckLedgeX,
    deckLedgeY,
    deckScrewY,
    deckZ,
    lowerBandZ,
    panelWallY,
    pdbHolePitch,
    pdbY,
    powerX,
    rearWallCutouts,
    sideWallX,
)
from cad.geometry import mirrored
from cad.joint import saddleHeight, statorClevis
from cad.parameters import (
    bearingSeatBossThickness,
    cheekDiameter,
    cheekThickness,
    hipArmButtressDrop,
    hipArmButtressRise,
    hipArmGussetDrop,
    hipArmGussetInnerY,
    hipArmGussetReach,
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
    m25Clearance,
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
# THEY ALL SIT ABOVE THE ELECTRONICS DECK, at z = 23.5, which is new. Below the
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
# Since the BMS went between the packs on 2026-10-05 they are under the packs'
# own centre lines to a tenth of a millimetre.
#
# THE IMU LEFT THE FLOOR ON 2026-10-14, for the underside of the deck
# (cad/electronics.py, imuX), and the rails stayed where they were. The 22 mm
# square they stand either side of is that old reservation's, kept as its own
# number so that the pelvis does not move when the IMU's reservation does.
#
# AND THEY START AT THE LEFT HIP SADDLE'S INBOARD FACE, not at the left wall. The
# saddle's top is the band's floor for its whole length and carries the packs
# itself; under that top the saddle is hollow, drained through its two walls,
# and a rail run through the hollow at this station walls its middle off into a
# sealed void -- tools/check.py refused the pelvis for exactly that. At y = 20
# the rails ran outside the saddle's walls and never met it.
#
# THEY CARRY THE PACKS' BODIES AND NOTHING ELSE, since the packs were measured
# on 2026-10-05: full height only as far as the 65 mm a body's 17 x 35 is good
# for, and past it a sill a millimetre under the lowest the lead end can reach,
# out to the end stop. The sill is there for the stop's sake -- a 2.5 mm block
# standing 14 mm off the floor on its own is a lever, and on the sill it is the
# end of a beam.
batteryRailThickness = 3.0
floorSquareDepth = 22.0
batteryRailY = (floorSquareDepth + batteryRailThickness) / 2
batteryRailStartX = -(hipCenterX + rearCheekX - cheekThickness / 2)
# The stop's own length along the pack. It was whatever the pack left of the
# bay, 1.5 mm, until the measured pack's lead end came out to the bay's end; it
# stands in the bay gap now, under the packs' leads where they turn.
batteryRailStopLength = 2.5
batteryRailEndX = batteryPackRightX + batteryRailStopLength
batteryRailSillTopZ = (
    lowerBandZ - (batteryPackLeadWidth - batteryPackWidth) - batteryLeadEndAir
)

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
# leave the top of that face have it to themselves. It meets the lead end
# end-on, past the pack's 77 mm, and is the one printed face that touches the
# lead end at all; whatever the end's shape, it never comes alongside it.

# THE WALL PADS, four off each long wall, which replaced the battery's fin and
# its two fences on 2026-10-05. cad/electronics.py's hold-down block says why and
# places them; this is how they are made.
#
# THE FIN WENT BECAUSE THE BMS IS THE FIN NOW: it stands between the packs and the
# three are taped into one block. The fences went because each stood on the floor
# along the whole of its pack, which took the strip between the pack and the wall
# from top to bottom -- and that strip is where each pack's XT60 has to lie, and
# the back one is where the actuator harness runs along the floor. A pad bears
# where a fence did and takes the strip only where it stands.
#
# THEY BEAR ON THE BLOCK ITSELF, since 2026-10-06, and not on foam: the owner's
# call, so the front and rear pads' faces are the block's own 45 mm apart. The
# 3 mm side strips went, and every pad reaches 3 mm further in from its wall.
#
# EACH HAS A 45 DEGREE UNDERSIDE, from the bearing face down to the wall, because the
# pelvis prints upright and a flat shelf 9.5 mm deep would print as a bridge into
# nothing. The low pads are set by that underside: where it comes nearest the
# wall, over the actuator harness, it clears the harness by half a millimetre.
# AND A 1.5 mm CHAMFER ON THE TOP OF THE BEARING FACE, because the block goes in
# from above between the two rows of pads, and a square edge would catch it.
batteryPadLeadIn = 1.5

# THE IMU SEAT CAME OFF THE FLOOR, 2026-10-14. Three ribs 2.5 mm tall on the
# square of floor between the hip saddles held the IMU, with adhesive under it,
# until the board bought turned out to have its socket on its underside, so it
# could never have sat flat there. It hangs under the electronics deck now
# (cad/deck.py), and the seat stood empty for an afternoon before it went with
# the pelvis's next reprint.


# THE DISTRIBUTION-BOARD POSTS. Four, standing from the shell floor to the plane
# the board's standoffs sit on, and THE PATTERN IS THE BOARD'S RATHER THAN OURS:
# a 45 mm square, read off the SwiftWing datasheet. That is the difference the
# bought board makes to this part -- these four posts have to be where somebody
# else decided, and if the board is ever swapped they move. It was, on
# 2026-10-07, for the power switch board on its own, and that board kept the
# square so that nothing here had to.
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

    They start at the left hip saddle's inboard face, stand full height under
    the packs' bodies, drop to a sill under the lead ends and end in a stop just
    past them, 2.5 mm into the bay gap. Rail, sill and stop overlap rather than
    touch, so each is one body the moment they are united.
    """
    railLength = batteryPackBodyEndX - batteryRailStartX
    railHeight = lowerBandZ - cavityBottomZ
    sillLength = batteryRailEndX - batteryPackBodyEndX + 1.0
    sillHeight = batteryRailSillTopZ - cavityBottomZ
    stopHeight = railHeight + batteryRailStopHeight
    rails = []
    for sy in (1, -1):
        rail = Pos(
            batteryRailStartX + railLength / 2,
            sy * batteryRailY,
            cavityBottomZ + railHeight / 2,
        ) * Box(railLength, batteryRailThickness, railHeight)
        sill = Pos(
            batteryRailEndX - sillLength / 2,
            sy * batteryRailY,
            cavityBottomZ + sillHeight / 2,
        ) * Box(sillLength, batteryRailThickness, sillHeight)
        stop = Pos(
            batteryRailEndX - batteryRailStopLength / 2,
            sy * batteryRailY,
            cavityBottomZ + stopHeight / 2,
        ) * Box(batteryRailStopLength, batteryRailThickness, stopHeight)
        rails.append(rail + sill + stop)
    return rails


def _wallPad(atX: float, faceZ: float, sy: int):
    """One pad off a long wall: a bearing face on the block, a 45 degree underside
    down to the wall and a lead-in chamfer on top. It meets the wall's inner face
    face to face, as the deck ledges and cover bosses do, and is one body with
    the shell once the piece is united for export.

    The rear pad is the front one reflected, NOT the front profile drawn with its
    y negated. Negating y reverses the profile's winding, which turns the face's
    normal round, and the extrusion then runs towards -x: until 2026-10-06 every
    rear pad stood a whole pad width to the left of the front one it faces."""
    wall = torsoInnerDepth / 2
    face = batteryPackOuterY
    topZ = faceZ + batteryPadHeight
    profile = [
        (wall, topZ),
        (face + batteryPadLeadIn, topZ),
        (face, topZ - batteryPadLeadIn),
        (face, faceZ),
        (wall, faceZ - (wall - face)),
    ]
    pad = extrude(Plane.YZ * Polygon(*profile, align=None), amount=batteryPadWidth)
    pad = Pos(atX - batteryPadWidth / 2, 0, 0) * pad
    return pad if sy > 0 else mirrored(pad, Plane.XZ)


def batteryPads() -> list:
    """The pads off the two long walls that the battery block's faces bear on.

    Front wall then rear, and on each the three low pads from left to right and
    then the high one. They hang off the wall and stand on nothing, on purpose:
    the rear ones are over the actuator harness, which is the reason they exist.
    """
    return [
        _wallPad(atX, faceZ, sy)
        for sy in (1, -1)
        for atX, faceZ in (
            *((x, batteryPadLowZ) for x in batteryPadLowX),
            (batteryPadHighX, batteryPadHighZ),
        )
    ]


def powerEntryPosts() -> list:
    """Four posts from the shell floor to the power switch board's standoffs."""
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


def hipArmBraces() -> list:
    """Ribs on the two inboard hip arms, and a buttress outside each outboard one.

    cad/parameters.py says why beside hipArmGussetReach, and how each is placed
    to keep clear of the motor, its rear screws and the thigh. Every one laps
    half the floor's thickness up into the floor and half an arm or a wall into
    the arm or wall it stands on, so it shares real material with the shell and
    unites with it rather than touching it face to face.

    Drawn for the right hip and reflected for the left, like the clevis, which
    keeps the forward-edge rib on the forward edge of both.
    """
    floorZ = shellFloorZ
    lapZ = floorZ + floorThickness / 2

    # The ribs, on the inboard arm's face towards the centre line: along the
    # floor by the reach, down the arm by the drop.
    armFace = hipCenterX + rearCheekX - cheekThickness / 2
    ribProfile = [
        (armFace + cheekThickness / 2, lapZ),
        (armFace - hipArmGussetReach, lapZ),
        (armFace - hipArmGussetReach, floorZ),
        (armFace, floorZ - hipArmGussetDrop),
        (armFace + cheekThickness / 2, floorZ - hipArmGussetDrop),
    ]
    rib = extrude(
        Plane.XZ * Polygon(*ribProfile, align=None),
        amount=cheekThickness / 2,
        both=True,
    )
    forwardEdgeY = cheekDiameter / 2 - cheekThickness / 2
    ribs = [
        Pos(0, atY, 0) * rib
        for atY in (-hipArmGussetInnerY, hipArmGussetInnerY, forwardEdgeY)
    ]

    # The buttress, on the outboard arm's outer face -- which is the flank's,
    # since the shell is built on that plane -- across the arm's full width.
    flankX = torsoShellWidth / 2
    buttressProfile = [
        (flankX - shellWall / 2, floorZ - hipArmButtressDrop),
        (flankX, floorZ - hipArmButtressDrop),
        (flankX + bearingSeatBossThickness, floorZ),
        (flankX, floorZ + hipArmButtressRise),
        (flankX - shellWall / 2, floorZ + hipArmButtressRise),
    ]
    buttress = extrude(
        Plane.XZ * Polygon(*buttressProfile, align=None),
        amount=cheekDiameter / 2,
        both=True,
    )

    right = [*ribs, buttress]
    return right + [mirrored(body, Plane.YZ) for body in right]


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

    Thirty-five bodies now, drawn separately, eight of them the hip arms' braces
    since 2026-10-12; the IMU's seat came off on 2026-10-14. KCL-SHAPED: the
    engine refused to union hollow boxes that meet at right angles, and the hip
    saddles are
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
    # per bought part -- a round hole for the button's bushing, a keyed cut for
    # the XT60E-M charge inlet's nose, a round hole for the antenna's bushing --
    # plus two clearance holes for the XT60's screws. A round hole is square in
    # cad/electronics.py's table, which is why this is the one place that has to
    # tell them apart.
    panelCutouts = []
    # Retain the lower circular segment: the flat faces down, 0.5 mm
    # above the circle's bottom, with 6.0 mm to the opposite arc.
    smaRound = (
        Pos(-sideWallX, antennaSideY, antennaSideZ)
        * Rot(0, 90, 0)
        * Cylinder(antennaHoleDiameter / 2, shellWall + 4.0)
    )
    smaFlatZ = antennaSideZ - antennaHoleFlatSpan + antennaHoleDiameter / 2
    smaBottom = Pos(-sideWallX, antennaSideY, smaFlatZ - antennaHoleDiameter / 2) * Box(
        shellWall + 6.0, antennaHoleDiameter + 2.0, antennaHoleDiameter
    )
    panelCutouts.append(smaRound - smaBottom)
    for _, atX, atZ, width, height in rearWallCutouts():
        if width == height:
            panelCutouts.append(
                Pos(atX, panelWallY, atZ)
                * Rot(90, 0, 0)
                * Cylinder(width / 2, shellWall + 4.0)
            )
        else:
            panelCutouts.append(
                Pos(atX, panelWallY, atZ)
                * chargeInletProfile(
                    width, height, shellWall + 4.0, chargeInletKeyRadius
                )
            )

    # The XT60's two screws, and they are M2.5 since 2026-10-12, M2 before
    # that, where most of this robot is M3. The connector is clamped to the wall by its own ears and a
    # nut, so this wall is clamped rather than threaded. That is
    # what a panel-mount part buys over a bonded one -- 2.4 mm of shell will not
    # hold a thread, and the printed panel that used to carry these needed 6 mm
    # of plate to tap into.
    #
    # THE SIZE WAS THE DISCONNECT'S NUTS' DOING and the disconnect is gone: its
    # nuts sat 2.25 mm from its body, which an M2 cleared and an M2.5 did not,
    # and that pair is what set M2 for the whole wall. THE SAME PART IS BACK, as
    # the charge inlet since 2026-10-05, so the reason is too: the female socket
    # it replaced would have taken an M2.5, and the male did not until each
    # screw was stood 0.25 mm outboard in its ear hole. So is the
    # thinnest material on this wall, the strip between each ear screw and the
    # nose cutout: 1.45 mm until the nose was measured 15.3 wide on 2026-10-12,
    # and 0.95 since, on M2.5 holes that pass the screw as printed --
    # cad/parameters.py says why the screws are M2.5 now and tools/gate_g.py
    # registers the 0.95. The female's flange screws left 1.7. The button that
    # replaced the disconnect needs no screws at all -- it clamps the wall with
    # its own nut -- so tools/gate_e.py counts two holes here and not four.
    panelFixings = [
        Pos(atX, panelWallY, atZ)
        * Rot(90, 0, 0)
        * Cylinder(m25Clearance / 2, shellWall + 4.0)
        for atX, atZ in chargeInletFixings()
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
    #
    # ITS ARMS ARE FILLED TO FULL WIDTH, 2026-10-12, where the thigh's clevis
    # keeps its waist: the second PLA pelvis lost all four at the floor.
    # Half the floor's thickness is how far the fill runs on into it.
    rightHipPitchJoint = Pos(hipCenterX, 0, hipPitchZ) * statorClevis(
        fullWidthInto=floorThickness / 2
    )

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
        *batteryPads(),
        *powerEntryPosts(),
        *deckLedges(),
        *hoistLugs(),
        *hipArmBraces(),
    ]


def torsoCover():
    """The lid: one print of its own, the shared design drawn to this box."""
    return torsoLid(torsoShellWidth, torsoShellDepth, shellTopZ)


def torsoAssembly() -> list:
    return [*pelvisShell(), torsoCover()]
