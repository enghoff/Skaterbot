"""The joint interface, designed once and used at all eight joints.

Ported from lib/joint.kcl. The commentary below is that file's, because the
reasoning is the valuable part and none of it changed in the move.

The actuator offers a grip on only two faces -- 4 x M3 on Ø41 at the rear and
6 x M3 on Ø24 at the front -- and nothing can pass through it. So the
stationary side has to reach around the body to support the moving side, and
the moving side is necessarily a single plate on the output face. That is
forced by the actuator, not chosen, and it makes every joint the same shape:

* `statorClevis` -- two cheeks straddling the actuator, anchored on the rear
  pattern, reaching past the body to a metal-seated bearing on the far side,
  with a saddle over the top that carries the load into whatever is above.
* `rotorHub` -- a plate bolted to the output circle and piloted on the Ø30
  register, carrying a Ø10 journal outboard into that bearing, with an arm
  and bridge that take its offset back to the centre line below. The journal is
  a bought sleeve screwed on from outside once the joint is closed, because the
  fork is one print and nothing standing proud of this plate can be brought in
  past its far cheek -- see cad/parameters.py beside journalDiameter.

Both are positioned with the joint centre at the origin and the joint axis
along X. The clevis rises in +Z, the hub descends in -Z, so a limb is a shell
with a clevis at its bottom and a hub at its top.

The clevis is open at the front, the back and below on purpose. The actuator
sits in free air and can still radiate, which is what lets the limbs be closed
shells without cooking the motors.

WHAT THE PORT CHANGED, AND WHAT IT DELIBERATELY DID NOT. Every cut here is still
taken on the simple body it belongs to, before anything is unioned, and every
body is still built in the order the KCL built it. None of that is necessary any
more -- OCCT accepts the blind pockets and the combined-solid cuts the Zoo engine
refused -- but phase 1 of docs/BUILD123D_MIGRATION.md is a translation, and gate B
requires this to come out identical to the geometry the engine produced. The
places where the shape was bent around a refusal are marked KCL-SHAPED; those are
the phase 3 list, and each is a separate change with its own mass delta.
"""

from __future__ import annotations

from math import cos, radians, sin

from build123d import (
    Align,
    Axis,
    Box,
    BuildLine,
    BuildSketch,
    CenterArc,
    Cylinder,
    Line,
    Plane,
    Pos,
    RegularPolygon,
    Rot,
    extrude,
    make_face,
)

from cad.parameters import (
    actuatorConnectorFlatOffset,
    actuatorRearBoltOffset,
    bearingSeatBossDiameter,
    bearingSeatBossThickness,
    bearingSeatDiameter,
    bearingSeatShoulderBore,
    bearingWidth,
    cheekDiameter,
    cheekNeckWidth,
    cheekThickness,
    frontCheekX,
    jointKeepOut,
    journalNutPocketDepth,
    journalNutPocketFlats,
    journalScrewClearance,
    journalSeatDepth,
    journalSeatDiameter,
    limbPlateThickness,
    m3CapCounterbore,
    m3CapCounterboreDepth,
    m3Clearance,
    rearCheekX,
    rotorFilletRadius,
    rotorHubDiameter,
    rotorHubInnerX,
    rotorHubOuterX,
    rotorHubThickness,
    saddleDrainDiameter,
    shellDepth,
    shellWall,
    shellWidth,
    statorPlateCenterX,
    statorPlateDiameter,
    statorPlateFlatOffset,
)

outputBoltRadius = 24.0 / 2  # actuatorOutputBoltCircle / 2

# The rear bolts sit at 45 degrees on Ø41, so both offsets are the same number.
# It lives in parameters.py because the limb measures its waist against it too.
rearBoltOffset = actuatorRearBoltOffset

rotorHubCenterX = rotorHubInnerX + rotorHubThickness / 2
shellInnerDepth = shellDepth - (shellWall * 2)

# The outboard end of the clevis, and the reason it is a name rather than a sum
# spelled out where it is used. The front cheek's outer face and the saddle's
# outboard end are the same plane -- the saddle spans from the rear cheek's outer
# face to this one -- so this is the last plane of printed structure on a joint,
# with only the bearing boss standing proud of it. cad/wheeled_parameters.py
# builds the pelvis's width on it so that the torso's side wall lands here too.
clevisOuterX = frontCheekX + cheekThickness / 2

# Both ends are the same height whatever limb they belong to: the saddle and the
# bridge each start one actuator radius plus a millimetre clear of the joint.
saddleHeight = 12.0
bridgeHeight = 8.0
statorEndHeight = jointKeepOut + saddleHeight
rotorEndHeight = jointKeepOut + bridgeHeight


def _disc(diameter: float, thickness: float, x: float = 0.0):
    """A disc on the joint axis: circle in YZ, thickness symmetric about x.

    Every round feature in this module is drawn this way -- the KCL sketched on
    YZ and extruded symmetrically along X -- so it is worth one helper rather
    than a rotation spelled out thirty times.
    """
    return Pos(x, 0, 0) * Rot(0, 90, 0) * Cylinder(diameter / 2, thickness)


def statorClevis():
    """Two cheeks and a saddle, straddling the actuator, anchored on the rear pattern."""
    saddleWidth = frontCheekX - rearCheekX + cheekThickness
    saddleCenterX = (frontCheekX + rearCheekX) / 2
    saddleCenterZ = jointKeepOut + saddleHeight / 2

    rearCheekDisc = _disc(cheekDiameter, cheekThickness, rearCheekX)
    rearCheekNeck = Pos(rearCheekX, 0, statorEndHeight / 2) * Box(
        cheekThickness, cheekNeckWidth, statorEndHeight
    )
    frontCheekDisc = _disc(cheekDiameter, cheekThickness, frontCheekX)
    frontCheekNeck = Pos(frontCheekX, 0, statorEndHeight / 2) * Box(
        cheekThickness, cheekNeckWidth, statorEndHeight
    )

    # The saddle is the only path the joint load has into the limb above, so it
    # is a closed box rather than a plate.
    saddleBlank = Pos(saddleCenterX, 0, saddleCenterZ) * Box(
        saddleWidth, shellDepth, saddleHeight
    )
    saddleCavity = Pos(saddleCenterX, 0, saddleCenterZ) * Box(
        saddleWidth - (shellWall * 2), shellInnerDepth, saddleHeight - (shellWall * 2)
    )

    # That cavity is closed on all six faces, and in a sintered part a closed
    # cavity is a pocket of loose powder with no way out of the print. One bore
    # straight through opens it at both side walls, so the powder can be blown
    # out rather than worked out of a blind hole. saddleDrainDiameter carries
    # why it is 4 mm and why it goes in the sides rather than anywhere else.
    saddleDrain = (
        Pos(saddleCenterX, 0, saddleCenterZ)
        * Rot(90, 0, 0)
        * Cylinder(saddleDrainDiameter / 2, shellDepth + 2.0)
    )
    saddleRaw = saddleBlank - saddleCavity - saddleDrain

    # The four rear bolts, on Ø41 at 45 degrees, so both offsets are one number.
    rearBolts = [
        _disc(m3Clearance, cheekThickness + 2.0, rearCheekX).moved(
            Pos(0, y * rearBoltOffset, z * rearBoltOffset)
        )
        for y in (1, -1)
        for z in (1, -1)
    ]

    # The rear cheek is solid through the middle. It carried a Ø30.2 lightening
    # bore for as long as it has existed, and that bore sat squarely across the
    # only path the joint load has: from the four rear bolts, up through the neck,
    # into the saddle. Filling it is the correction the stator plate has already
    # had, for the same reason -- about 2.3 g on a cheek that is 3 mm thick and
    # that sets the coaxiality of the whole joint. Nothing passed through it: the
    # cheek lands on the motor's flat rear face, and the bearing the bore was
    # sized to accept lives in the front cheek.

    # The connector relief. The rear cheek used to be a full Ø52 disc sitting
    # 0.3 mm off the rear face, which covered the connector flat and everything
    # plugged into it -- the flat limb plate had been truncated on this chord
    # since it was drawn, and the clevis was simply never given the same cut. It
    # is the same chord, at 19 mm, and it takes the cheek entirely out of the
    # estimated plug keep-out at r 27. Only the rear cheek needs it: the saddle
    # reaches 15 mm either side and the front cheek is at the far end of the
    # actuator, so neither is in the way.
    rearFlatCutter = Pos(
        rearCheekX, -(actuatorConnectorFlatOffset + cheekDiameter / 2), 0
    ) * Box(cheekThickness + 4.0, cheekDiameter, cheekDiameter)

    # The front cheek is bored for the bearing itself. It held a Ø30.2 bore for a
    # turned aluminium carrier until that part was deleted for want of a supplier,
    # and the bearing is now bonded into the print with the same retaining
    # compound the carrier was bonded in with.
    #
    # The boss is what replaces the carrier's flange. A 3 mm cheek cannot seat a
    # 5 mm bearing, so the boss stands off the cheek's outer face, makes up the
    # missing 2 mm and carries 1.5 mm of shoulder past it: the bearing goes in
    # from inboard, seats against the shoulder, and the journal then loads it
    # against that face rather than against the bond. The Ø17.5 shoulder bore
    # touches the outer race only -- the seal and the inner race turn -- and is
    # also how a pin reaches the bearing to push it out.
    #
    # The seat cutter runs 1 mm past the cheek's inner face rather than stopping
    # on it, and the shoulder bore starts inside the seat it is cut through, so
    # neither cut ends coplanar with a face it does not mean to touch.
    frontSeatBoss = _disc(
        bearingSeatBossDiameter,
        bearingSeatBossThickness,
        clevisOuterX + bearingSeatBossThickness / 2,
    )
    frontBearingSeat = _disc(bearingSeatDiameter, bearingWidth + 2.0, frontCheekX)
    frontShoulderBore = _disc(
        bearingSeatShoulderBore,
        bearingSeatBossThickness + 2.0,
        clevisOuterX + (bearingSeatBossThickness + 2.0) / 2,
    )

    # KCL-SHAPED: each cut is taken on the simple body it belongs to, before
    # anything is unioned, because the engine rejected pockets cut out of a large
    # combined solid. OCCT does not care, but gate B does.
    rearCheekBlank = rearCheekDisc + rearCheekNeck
    rearCheekAfterBolts = rearCheekBlank
    for bolt in rearBolts:
        rearCheekAfterBolts -= bolt
    rearCheekFinished = rearCheekAfterBolts - rearFlatCutter

    # The boss is unioned on BEFORE the seat is cut, not after: a bore drilled
    # first and then unioned over is a bore filled back in, which is the failure
    # CLAUDE.md and gate E exist for.
    frontCheekBlank = frontCheekDisc + frontCheekNeck + frontSeatBoss
    frontCheekFinished = frontCheekBlank - frontBearingSeat - frontShoulderBore

    return rearCheekFinished + frontCheekFinished + saddleRaw


# The Ø24 output pattern as free-standing cutters: six M3 clearance holes, and
# separately their cap counterbores. They are out here rather than inline so the
# pattern has one definition and one place to correct.
#
# The rule that goes with them: nothing may be built across this circle in the
# disc's own plane. The rotor arm used to, and the union filled four of the six
# holes back in without an error anywhere -- mock never evaluates a boolean, the
# engine built it happily, and the mass looked fine. Every way of drilling
# through such an overlap was then tried and refused, one of them by returning
# five open holes and one filled, which is worse than a refusal. The arm now
# keeps clear of the circle instead. See docs/KCL_GOTCHAS.md before putting
# anything else in this plane.
def _outputBoltCutters():
    first = (
        Pos(rotorHubCenterX, outputBoltRadius, 0)
        * Rot(0, 90, 0)
        * Cylinder(m3Clearance / 2, rotorHubThickness + 2.0)
    )
    return [first.rotate(Axis.X, i * 60) for i in range(6)]


def _outputCounterboreCutters():
    first = (
        Pos(rotorHubOuterX - (m3CapCounterboreDepth / 2), outputBoltRadius, 0)
        * Rot(0, 90, 0)
        * Cylinder(m3CapCounterbore / 2, m3CapCounterboreDepth)
    )
    return [first.rotate(Axis.X, i * 60) for i in range(6)]


# THE Ø30.4 REGISTER POCKET WAS HERE, and outputRegisterCutter() with it. The
# plate has no pilot on the actuator any more: it lands flat on the Ø30 register
# and is located by the six M3 on Ø24. cad/parameters.py carries the reasoning
# where the two names used to be declared, and the short version is that the
# pilot and the plate's clearance over the housing were the same millimetre
# shared out, and a printed part cannot be trusted with 0.3 mm of it.
#
# The history is worth keeping here because two of this project's failures are
# in it. The register was the second feature on this joint to have been quietly
# filled back in by a body unioned across it, and it hid for longer than the six
# bolt holes did because it left no hole to count: a union that eats a segment
# out of a Ø30.4 pocket still leaves ONE cylindrical face of radius 15.2 behind,
# so gate E counted one and passed while the pocket was 314 degrees open instead
# of 360. What caught it in the end was measuring the angular span. Nothing lies
# in this plane now for anything to fill, but the rule that produced both
# failures stands: NOTHING MAY BE BUILT ACROSS THE Ø24 OUTPUT CIRCLE in the
# disc's own plane, and the note above _outputBoltCutters is where it lives.


def _nutPocket():
    """The hex pocket the journal's nut sits in, cut from the plate's seating face.

    The nut is what the journal screws into, and it has to be captive before the
    disc goes onto the motor, because the motor's own output face is what closes
    this pocket. So it is cut from the INBOARD face -- the one the actuator is
    on -- and the Ø30 register lands across its mouth.

    The cutter starts a millimetre inboard of that floor rather than on it, which
    is the same rule the bearing seat is cut to in the clevis above: a cut that
    ends coplanar with a face it does not mean to touch is a cut waiting to leave
    a zero-thickness sliver.
    """
    mouth = rotorHubInnerX
    overshoot = 1.0
    with BuildSketch(Plane.YZ) as hexProfile:
        RegularPolygon(journalNutPocketFlats / 2, 6, major_radius=False)
    return Pos(mouth - overshoot, 0, 0) * extrude(
        hexProfile.sketch, amount=journalNutPocketDepth + overshoot
    )


def outputDisc(journalAnchor: bool = False):
    """The plate that bolts to the actuator's output.

    Kept on its own so that the two rotor ends -- the offset hub the hip carrier
    and the foot use, and the in-plane plate the limbs use -- are the same disc
    with different structure hung off it. Ø30 register, six M3 counterbored into
    the Ø24 output circle, and at the centre either a seat for a journal or the
    anchor a journal screws into.

    `journalAnchor` takes the blind seat away and puts a through hole and a
    captive nut's pocket at the centre instead, which is what a straddled joint
    needs: the journal is a bought Ø10 sleeve fitted from outside after the motor
    is in its fork, because nothing that is part of this disc before then can be
    brought into the far bearing at all. cad/parameters.py carries that
    arithmetic, and what the anchor costs against the stub it replaces.

    False leaves the seat, which is what the wheel adapter wants: it shares this
    disc and has never carried a journal, and leaving it alone is what keeps that
    piece identical to its golden STEP.
    """
    part = _disc(rotorHubDiameter, rotorHubThickness, rotorHubCenterX)

    if journalAnchor:
        # Both cuts before the bolt holes, like everything else on this disc.
        # Neither reaches r4.2 and the counterbores start at r9, so they cannot
        # meet; the ordering is the one CLAUDE.md insists on all the same.
        part -= _disc(journalScrewClearance, rotorHubThickness + 2.0, rotorHubCenterX)
        part -= _nutPocket()
    else:
        part -= _disc(
            journalSeatDiameter,
            journalSeatDepth,
            rotorHubOuterX - (journalSeatDepth / 2),
        )

    for cutter in _outputBoltCutters():
        part -= cutter
    for cutter in _outputCounterboreCutters():
        part -= cutter
    return part


def rotorHub():
    """The offset rotor end: disc, arm and bridge.

    The arm carries the hub's offset down past the actuator and the bridge takes
    that offset back to the limb centre line. Used by the hip carrier and the
    foot, whose own structure cannot be moved into the output plane. The limbs
    can, and use rotorPlate instead.
    """
    bridgeWidth = rotorHubOuterX + shellWidth / 2
    bridgeCenterX = rotorHubOuterX - (bridgeWidth / 2)

    # Two things fix where the arm ends, and between them they fix how wide it is.
    # It has to stop clear of the output counterbores: the arm lies in the disc's
    # own plane, so anything it covers it fills, and run up to the joint centre it
    # buried the two bolts below the axis and half filled the two on it, leaving
    # two usable screws out of six to carry the actuator's whole output torque.
    # And its top face has to sit wholly inside the disc, because a face that is
    # part buried and part proud is the one case the engine will not union at all.
    # Seating the top corners just inside the disc's edge at 52 degrees does both:
    # 14.2 mm below the axis, 0.8 mm clear of the counterbores, and 21.2 mm across
    # where the disc is 22.2. The arm gives up 4 mm of width for that, which is
    # the price of the six bolts.
    rotorArmSeatAngle = 52.0
    rotorArmTopZ = -(rotorHubDiameter / 2 * sin(radians(rotorArmSeatAngle)))
    rotorArmWidth = rotorHubDiameter * cos(radians(rotorArmSeatAngle)) - 1.0
    rotorArmHeight = rotorEndHeight + rotorArmTopZ

    # The arm's root is filleted into the bridge rather than left as a sharp
    # re-entrant corner. That corner is the peak-stress point for the load the
    # limb below puts through the offset -- about 11 MPa nominal, which a sharp
    # angle multiplies by roughly 2.5 -- and the radius costs almost no mass.
    #
    # Drawn as a profile with an arc in it rather than as a fillet() on the
    # assembled corner. That is not a leftover workaround: a swept profile puts
    # the blend exactly where the arithmetic says it goes, where fillet() would
    # have to FIND the edge with a sorted selector and would quietly take a
    # different one the day the arm moves.
    #
    # CORRECTED, and the history is the point. The KCL this was ported from
    # constrained only how far the blend REACHES -- one millimetre horizontally
    # and one vertically between its endpoints -- and left the arc's CENTRE
    # unconstrained. Its solver therefore kept the centre two millimetres off the
    # chord midpoint, where the sketch's initial guess had put it, while shrinking
    # the chord from 4 mm to 1.4. What it built was an arc of radius sqrt(8.5) =
    # 2.9155 mm that met NEITHER wall tangentially: two fresh corners of about 31
    # degrees in place of the single one it was meant to remove, which is the
    # opposite of what a stress-relief blend is for. It carried more material than
    # a true fillet and relieved less. Nothing had ever measured it; gate B did,
    # on the first day of the migration.
    #
    # This is the fillet the parameter always described. Radius
    # rotorFilletRadius, centred one radius in from each face, so it runs tangent
    # into the top of the bridge at one end and into the arm's inner face at the
    # other. It still reaches only 1 mm into the corner, so it still clears the
    # actuator -- which is what limits the radius here, not the stress. See the
    # note beside rotorFilletRadius in cad/parameters.py.
    outer = rotorHubThickness + rotorFilletRadius
    inner = rotorFilletRadius
    armRootZ = bridgeHeight

    with BuildSketch(Plane.XZ) as armProfile:
        with BuildLine():
            Line((0.0, 0.0), (outer, 0.0))
            Line((outer, 0.0), (outer, rotorArmHeight))
            Line((outer, rotorArmHeight), (inner, rotorArmHeight))
            Line((inner, rotorArmHeight), (inner, armRootZ + rotorFilletRadius))
            CenterArc(
                center=(0.0, armRootZ + rotorFilletRadius),
                radius=rotorFilletRadius,
                start_angle=0.0,
                arc_size=-90.0,
            )
            Line((0.0, armRootZ), (0.0, 0.0))
        make_face()
    rotorArmRaw = Pos(rotorHubInnerX - rotorFilletRadius, 0, -rotorEndHeight) * extrude(
        armProfile.sketch, amount=rotorArmWidth / 2, both=True
    )

    bridgeRaw = Pos(bridgeCenterX, 0, -rotorEndHeight + bridgeHeight / 2) * Box(
        bridgeWidth, shellDepth, bridgeHeight
    )

    # The bridge is a 40 x 30 plate only 8 mm thick and it bends about its own
    # long axis, so the material at mid-height carries almost nothing. Three
    # through-slots leave a flange above and below and a rib between each pair,
    # all at shellWall -- the same four-perimeter rule the shells are drawn to.
    # That takes about 2 g out of every rotor end, 17 g across the eight joints,
    # for roughly 6 per cent of the section's second moment.
    #
    # The slots stop clear of the rotor arm, which fills the outboard third of
    # the bridge and would refill anything cut there. Nothing on the outside of
    # the part moves, so the 112.8 degree knee contact is unaffected. In an
    # assembled limb the shell walls close the slot ends, so if the final set is
    # printed SLS rather than FDM the voids will need a vent for the powder.
    bridgeSlotHeight = bridgeHeight - (shellWall * 2)
    bridgeSlotInnerX = bridgeCenterX - (bridgeWidth / 2) + shellWall
    bridgeSlotOuterX = rotorHubInnerX - rotorFilletRadius - shellWall
    bridgeSlotLength = (bridgeSlotOuterX - bridgeSlotInnerX - (shellWall * 2)) / 3
    bridgeSlotPitch = bridgeSlotLength + shellWall

    bridgeLightened = bridgeRaw
    for i in range(3):
        bridgeLightened -= Pos(
            bridgeSlotInnerX + bridgeSlotPitch * i,
            0,
            -rotorEndHeight + shellWall,
        ) * Box(
            bridgeSlotLength,
            shellDepth + 4.0,
            bridgeSlotHeight,
            align=(Align.MIN, Align.CENTER, Align.MIN),
        )

    # The arm shares the disc's plane and covers its lower half, so the output
    # pattern is taken through the assembled end. Drilled into the disc alone, as
    # this was until August 2026, the union refilled four of the six holes: the
    # pair at the horizontal diameter half filled with their counterbores ruined,
    # and the pair below the axis buried outright, leaving two usable bolts on a
    # 12 mm chord to carry the actuator's whole output torque.
    #
    # The REGISTER POCKET used to be re-cut here for exactly the same reason, and
    # it was missed when the bolt holes were caught: the arm's top face sits
    # 14.18 mm below the axis, inside the Ø30.4 pocket's own 15.2 mm radius, so
    # the union filled a 42 degree segment of it back in and the actuator's Ø30
    # register would have landed on that instead of in the pocket. The 52 degree
    # seat that fixes the arm's width was chosen against the counterbores, which
    # it clears by 0.8 mm, and the register was never in that arithmetic. There
    # is no pocket to re-cut now -- see the note where the cutter used to be --
    # so what is left of that correction is the arm's width, which stays as it is.
    return outputDisc() + rotorArmRaw + bridgeLightened


def statorPlate():
    """The flat limb's lower end, bolted straight to the actuator's rear cover.

    It replaces the two-cheek clevis wherever the limb can lie in one plane,
    which is the knee and the ankle. Hip pitch keeps
    `statorClevis`, because the torso and the hip carrier cannot put their
    structure in the joint's plane.

    Drawn in the same frame as everything else here -- joint centre at the
    origin, axis along X, actuator output towards +X -- so the plate sits behind
    the motor at -X. A limb whose lower actuator is turned round REFLECTS it
    across YZ to bring it to +X, rather than spinning it half a turn about Z.
    The two are the same plate everywhere but the connector flat, which is the
    one feature that is not symmetric fore and aft -- and that flat is where the
    actuator's leads come out, so it has to stay aft, with the hip's and with
    both floor ports into the pelvis. See cad/limb.py.

    It is solid inside the bolt circle. It carried the clevis's Ø30.2 lightening
    bore until that was measured on a 6 mm plate rather than a 3 mm cheek: the
    bore left 14.8 mm of the available 45 mm of width at the joint axis, and
    266 mm^4 out of plane against the 540 mm^4 of the bare waist that NOTES.md
    already calls the weakest printed thing on the robot. Filling it is 4.6 g a
    plate and takes that section to 810 mm^4. Nothing needed the hole: the rear
    cover is a flat static face the plate lands on, and the knee and the ankle
    have had no far bearing since the clevis went.
    """
    plateBlank = _disc(statorPlateDiameter, limbPlateThickness, statorPlateCenterX)

    # The connector relief, taken as a straight cut on the housing's own flat.
    flatCutter = Pos(
        statorPlateCenterX,
        -(statorPlateFlatOffset + statorPlateDiameter / 2),
        0,
    ) * Box(limbPlateThickness + 4.0, statorPlateDiameter, statorPlateDiameter)

    plateBolts = [
        _disc(m3Clearance, limbPlateThickness + 4.0, statorPlateCenterX).moved(
            Pos(0, y * rearBoltOffset, z * rearBoltOffset)
        )
        for y in (1, -1)
        for z in (1, -1)
    ]

    # KCL-SHAPED: every cut on the plain disc, before anything else, as
    # everywhere here.
    plate = plateBlank - flatCutter
    for bolt in plateBolts:
        plate -= bolt
    return plate
