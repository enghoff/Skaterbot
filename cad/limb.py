"""Flat-plate limb, with a straddled lower joint where the load asks for one.

Ported from lib/limb.kcl, comments and all.

One parametric limb, used for the thigh and the shin. It is a plate lying in a
single plane: a Ø36 disc bolted to the joint above's output, a channel waist,
and at the bottom either a Ø52 disc lying flat on the next actuator's rear cover
or -- at the knee, and only there -- the two-cheek clevis that reaches past that
actuator to a second bearing on the far side.

WHY ONLY THE KNEE, September 2026. Every joint on this robot was a plate for a
year, on the assumption that the actuator's own output bearing would take the
overhung moment of a limb hung 22 mm off the axis, which DAMIAO have never
confirmed. The knee is the worst of the three by some way: the shin, the wheel
motor, the adapter and the wheel all hang off it, where the wheel joint below
carries the wheel alone on a 12 mm arm and the hip above was never unstraddled.
So the knee gets the second support and the other two do not, which is the
"double-support only the joints that see landing loads" that NOTES.md has
recommended since the load cases were first run.

The clevis is not a new part. It is cad/joint.py's `statorClevis`, the hip's
own, with one thing asked of it that a torso does not: the saddle is slid 2.7 mm
outboard so that it ends on the limb plate's exterior face, which costs it all
but 0.3 mm of its landing on the far cheek's neck. The hip's form is unchanged
and is still what gate B holds against its golden STEP.

Local frame: the limb axis is Z, both joint axes are X, and the two joint centres
sit at z = +/- limbLength/2. The plate lies on the +X side with both actuators
inboard of it. That works because the knee actuator is turned round -- see the
note in parameters.py -- so the upper joint presents its output face and the
lower joint presents its rear cover on the same side.

A limb for the other hand is this one mirrored across YZ. cad/thigh.py and
cad/shin.py each export both hands. THE TWO SEGMENTS ARE NO LONGER THE SAME
PRINT: they are still both 105 mm, but a thigh ends in a clevis and a shin in a
plate, so the four limbs on the robot are four distinct pieces where they were
two printed twice each. The shins are the part that did not change, so they keep
the `limb-105` name and the golden STEP that goes with it.

The waist is a plain plate. It carried two stiffening flanges on its outboard
face for a while; they came off on 30 August 2026 once the numbers were run,
because they bought stiffness and almost no strength, and none at all at the
section that decides whether a limb breaks. The reasoning is kept in
cad/parameters.py beside the waist dimensions, and in NOTES.md.

What is left, on a shin, is a single flat profile 6 mm thick from one end to the
other, which is both the cheapest thing to print and the strongest way to print
it: laid flat, every fibre runs along the limb and no load crosses a layer line.

A THIGH CANNOT BE PRINTED THAT WAY AND THAT IS THE REAL COST OF THE CLEVIS. The
far cheek stands 48 mm across the joint from the plate, joined only by the
saddle, so a thigh laid on its plate face has a disc floating 48 mm in the air.
It has to stand on end instead, or on its flank, and either puts layer lines
across a section that had none. NOTES.md carries what the orientation is worth
and it has not been re-decided for this shape.

Two cable-tie arches stand on the INBOARD face, one at each end of the waist,
and they are the only thing on the robot outside the pelvis that a harness can
be tied to. They put the run inside the box the limb plates and the actuators
make rather than hanging it off the back of the leg, and they add material
where a slot through the plate would have taken it away. The reasoning, and
why the lower joint's connector relief now faces aft to meet the harness, is
in cad/parameters.py.

The waist is not symmetric about the limb centre. Each end runs as far into its
disc as that disc's bolt pattern allows, and the two patterns are not the same
distance out, so the two ends are not either.
"""

from __future__ import annotations

from math import sqrt

from build123d import (
    Align,
    Box,
    BuildLine,
    BuildSketch,
    Plane,
    Polyline,
    Pos,
    extrude,
    make_face,
)

from cad.geometry import mirrored
from cad.joint import (
    outputDisc,
    outputRegisterCutter,
    statorClevis,
    statorPlate,
)
from cad.parameters import (
    actuatorRearBoltOffset,
    jointKeepOut,
    kneeOutboardOffset,
    limbPlateThickness,
    limbTieArchHeight,
    limbTieArchLap,
    limbTieArchLength,
    limbTieArchTunnel,
    limbTieArchWidth,
    limbTieArchY,
    limbTieArchZ,
    limbTieArchZClevis,
    limbTieSlotWidth,
    limbWaistDepth,
    limbWaistUpperZ,
    m3CapHeadStandoff,
    rotorHubDiameter,
    rotorHubInnerX,
    statorPlateDiameter,
)


def limbAssembly(limbLength: float, lowerEnd: str = "plate") -> list:
    """One limb, as seven interpenetrating bodies.

    `lowerEnd` is what the limb presents to the actuator below it:

    * "plate" -- the Ø52 disc lying flat on that actuator's rear cover, which is
      every limb this robot had until the knee was straddled and is still what
      the shin gives the wheel motor;
    * "clevis" -- cad/joint.py's `statorClevis`, the hip's own part, reaching
      past the actuator to a bonded 6800 on the far side. Only the thigh uses
      it, and only because the knee is the joint that carries the whole of the
      leg below it on an overhung 22 mm arm.

    Returns a LIST, not a single solid, because that is what the KCL returned
    and what the golden STEP contains: the waist plate occupies exactly the same
    band in X as both discs, which is the union the Zoo engine refused. Every
    overlap is millimetres of real material, so a slicer that merges coincident
    shells prints this as the single plate it is -- verify that before printing.
    Unioning them for real is a phase 3 change; see docs/BUILD123D_MIGRATION.md.
    """
    if lowerEnd not in ("plate", "clevis"):
        raise ValueError(f"lowerEnd must be 'plate' or 'clevis', not {lowerEnd!r}")
    jointZ = limbLength / 2

    # The waist reaches into both discs so the three bodies merge, but it cannot
    # reach the same distance at both ends. At the rotor end it stops where
    # parameters.py puts it, one counterbore clear of the Ø24 output circle. At
    # the stator end the Ø41 rear bolts are the constraint, and a waist symmetric
    # about the limb centre overshot them: its corner landed 0.7 mm from the two
    # bolt centres nearest the waist and filled 46 % of each hole, leaving a
    # 1.2 mm crescent no screw could pass. It now stops a cap head short of them,
    # which costs nothing structurally -- the plate is still 38 mm wide there, so
    # the section never narrows -- and leaves 8 mm of engagement into the disc.
    #
    # AT A CLEVIS END NEITHER OF THOSE IS THE CONSTRAINT. The bolts are in a 3 mm
    # cheek 48 mm across the joint from each other and the waist never goes near
    # them; what the waist has to meet is the saddle, which is the only path the
    # far cheek's load has into the limb. So it runs straight down through the
    # saddle to its floor, one joint keep-out from the axis, and the saddle wraps
    # the plate's full 6 mm for its own 12 mm of height -- it is slid out to the
    # plate's exterior face, so the two end together -- while the rear cheek's
    # neck merges into the rest. That is 6.1 mm less plate than the
    # stator end takes, and it stops 9.5 mm above the nearest rear bolt, so a cap
    # head and a driver still reach all four along the axis.
    waistUpperZ = limbWaistUpperZ
    if lowerEnd == "clevis":
        waistLowerZ = -(jointZ - jointKeepOut)
    else:
        waistLowerZ = -(jointZ - actuatorRearBoltOffset - m3CapHeadStandoff)

    waistBlank = Pos(rotorHubInnerX, -(limbWaistDepth / 2), waistLowerZ) * Box(
        limbPlateThickness,
        limbWaistDepth,
        waistUpperZ - waistLowerZ,
        align=(Align.MIN, Align.MIN, Align.MIN),
    )

    # THE WAIST'S TWO BOTTOM CORNERS REACH FURTHER DOWN THAN THE REST OF IT.
    #
    # The end above is held a cap head clear of the rear bolts, and at that
    # height the Ø52 stator plate's own rim has come out to only 18.86 mm of the
    # waist's 20. So the limb's outline dipped in to follow the rim for 1.28 mm
    # and then stepped back out to the flank, leaving a notch at each bottom
    # corner 1.14 mm deep, with the waist's end face showing as a ledge in the
    # floor of it. Nobody drew that: it is the same accident as the 1 mm step in
    # the silhouette that statorPlateFlatOffset was introduced to cure, one
    # corner away on the same joint.
    #
    # Taking the corners off instead does not work. The flank is 40 mm wide for
    # the whole length of the limb and the plate is a Ø52 disc, so above this
    # point the waist is LEGITIMATELY outside the rim and trimming it back would
    # only move the step rather than remove it. Carrying the corners down to
    # where the rim is 20 mm wide closes it for good: on the inboard side the
    # flank runs flush into the connector relief, which is cut at that same
    # 20 mm, and on the outboard side it runs tangent into the rim.
    #
    # Only the corners can go down. The middle of the end stays where the bolts
    # put it, and this reaches no further inboard than y = 17.90, which leaves
    # the nearest bolt centre 4.00 mm -- more than the 3.40 the whole end is
    # already held to.
    #
    # A CLEVIS END HAS NO SUCH NOTCH AND GETS NO SUCH CORNERS. The step was the
    # waist standing proud of a Ø52 disc's rim; a clevis puts a 30 mm saddle
    # there instead, the waist is 40 mm wide and passes it on both flanks by
    # 5 mm for the saddle's whole height, and there is no rim for an outline to
    # follow. Carrying the corners down would only bury more plate in the saddle.
    if lowerEnd == "plate":
        cornerHalfWidth = limbWaistDepth / 2
        cornerDepth = cornerHalfWidth - (actuatorRearBoltOffset + m3CapHeadStandoff)
        cornerFlushZ = -jointZ + sqrt(
            (statorPlateDiameter / 2) ** 2 - cornerHalfWidth**2
        )
        for side in (1, -1):
            waistBlank += Pos(
                rotorHubInnerX,
                side * (cornerHalfWidth - cornerDepth / 2),
                cornerFlushZ,
            ) * Box(
                limbPlateThickness,
                cornerDepth,
                waistLowerZ - cornerFlushZ,
                align=(Align.MIN, Align.CENTER, Align.MIN),
            )

    # The waist has to cut itself clear of the rotor disc's register pocket,
    # because it reaches far enough into the disc to fill part of it in.
    #
    # The window the waist's top edge was fitted into was measured against the
    # disc's rim and against the nearest output counterbore, 13.4 mm below the
    # joint centre, which 38.5 mm clears by 0.6. The Ø30.4 REGISTER was not in
    # that arithmetic, and its radius is 15.2, so a top edge 14 mm below the
    # centre lies 1.2 mm inside it: the waist filled a 45.8 degree segment of the
    # pocket, 11.8 mm across and the pocket's full 1.2 mm depth. The actuator's
    # Ø30 output register would have landed on that instead of in the pocket, and
    # the plate would have rocked on it rather than piloting.
    #
    # Nothing reported it. The pocket still had a cylindrical face of the right
    # radius, so gate E counted it; the union that filled it is between two
    # bodies this piece never merges, so the fill was not even a boolean anyone
    # could have watched. What made it visible in the end was the FINISH pass:
    # the waist's top arris is an outer edge of its own body and got its 0.5 mm
    # chamfer, and inside the pocket -- the one place that arris is not buried in
    # the disc -- the chamfer surfaced as a bevel with a sliver at each end,
    # sitting in a locating feature that finish.py is explicit must never be
    # chamfered. Cutting the pocket clear takes the chamfer with it, because
    # there is no longer an edge of the waist inside the pocket at all.
    waistPlate = waistBlank - Pos(0, 0, jointZ) * outputRegisterCutter()

    # Where the waist runs into the hub disc, the plate has to neck down from
    # 40 mm to the Ø36 disc, and the step between them is where the limb hands
    # its bending into the joint -- the peak-stress point on the part. These two
    # gussets carry the width up past that step as a taper, running from the
    # waist's top corner to the point where the taper goes tangent to the disc's
    # rim, so the section narrows gradually instead of in a shoulder.
    #
    # While the waist was 30 mm the gusset was a small fillet tangent to both the
    # plate's side and the disc. That construction has no solution once the waist
    # is wider than the disc: a line 20 mm off the axis never touches a circle of
    # radius 18, so the blend became a straight taper instead.
    #
    # The inner edge is a chord between two points on the disc, so it is buried --
    # a chord of a circle stays inside it -- and the visible outline is the disc's
    # own arc. The taper clears both output counterbore rows: it is outboard of
    # y = 15.7 everywhere it passes the pair on the horizontal diameter, whose
    # heads reach y = 15.
    discRadius = rotorHubDiameter / 2
    gussetDrop = jointZ - waistUpperZ
    gussetHalfWidth = limbWaistDepth / 2
    gussetSpanSq = gussetHalfWidth**2 + gussetDrop**2
    gussetTangentLen = sqrt(gussetSpanSq - discRadius**2)
    # Where the disc's rim crosses the waist's top edge, and where the taper from
    # the waist's corner goes tangent to that rim.
    gussetArchY = sqrt(discRadius**2 - gussetDrop**2)
    gussetTangentY = (
        discRadius**2 * gussetHalfWidth + discRadius * gussetTangentLen * gussetDrop
    ) / gussetSpanSq
    gussetTangentZ = (
        jointZ
        + (discRadius * gussetTangentLen * gussetHalfWidth - discRadius**2 * gussetDrop)
        / gussetSpanSq
    )

    with BuildSketch(Plane.YZ) as gussetProfile:
        with BuildLine():
            Polyline(
                (gussetArchY, waistUpperZ),
                (gussetHalfWidth, waistUpperZ),
                (gussetTangentY, gussetTangentZ),
                close=True,
            )
        make_face()
    # Plane.YZ's own x runs along global Y and its normal along global X, so the
    # profile above is already in the limb's frame and only needs its thickness.
    gussetFront = Pos(rotorHubInnerX + limbPlateThickness / 2, 0, 0) * extrude(
        gussetProfile.sketch, amount=limbPlateThickness / 2, both=True
    )
    # mirrored(), not build123d's mirror(). This body gets mirrored a SECOND time
    # when cad/thigh.py or cad/shin.py builds the opposite hand, and a twice-
    # mirrored shape reports a volume of zero: build123d wraps each mirror in a
    # fresh Compound, and Compound.volume only looks one level down. The geometry
    # is perfect throughout -- valid, correctly oriented, right bounding box, and
    # every boolean behaves -- so nothing objects; only the number everything
    # reads goes silently to nothing. cad/geometry.py has the detail. This is the
    # line that found it, and it is left as a mirror rather than rewritten so
    # that gate C keeps exercising the fix.
    gussetRear = mirrored(gussetFront, Plane.XZ)

    # THE JOURNAL IS NOT PART OF THIS DISC, and it cannot be. The rotor end of a
    # limb is the hip on a thigh and the knee on a shin, both straddled, and a
    # journal standing proud of this face -- a printed stub, or the dowel before
    # it -- cannot be brought into the far bearing at all: the fork is one print
    # and the motor with this disc bolted to it is 4.7 mm too long to enter it.
    # So the disc carries the ANCHOR and the journal is a sleeve fitted from
    # outside at the end. cad/parameters.py carries the arithmetic, what the
    # anchor costs against the stub, and what would give it back.
    upperDisc = Pos(0, 0, jointZ) * outputDisc(journalAnchor=True)
    # The stator plate is drawn behind an actuator whose output faces +X. This
    # limb's lower actuator is turned round, so the plate has to come to the near
    # side to land on the rear cover that now faces +X with everything else.
    #
    # REFLECTED RATHER THAN SPUN, September 2026, AND THE CONNECTORS ARE WHY.
    # A half turn about Z brings the plate across and takes its connector relief
    # with it, from the aft flank to the forward one -- which is where the relief
    # sat from the day this part was drawn, because the spin was chosen when
    # nobody was routing a cable. It put every lead on this robot on the wrong
    # side: the hip actuators' connectors face aft, both floor ports into the
    # pelvis are aft, and the knee's and the wheel motor's faced forward, so each
    # of the four leads had to cross its own limb front to back to get home.
    # Mirroring across YZ moves the plate the same way and leaves the relief
    # where it is, which is the same thing as installing that actuator the other
    # way up. Every feature on this plate is symmetric fore and aft except the
    # relief, so nothing else moves; gate B holds the pair of segments it swaps.
    #
    # A CLEVIS GOES ON THE SAME TRANSFORM BUT NOT AT THE SAME STATION. It is
    # cad/joint.py's part untouched -- the one gate B holds against its own
    # golden STEP -- and it stands kneeOutboardOffset further out along the joint
    # axis than a plate does, because a 3 mm cheek held 0.3 mm off the rear cover
    # ends 2.7 mm inside the 6 mm plate's exterior face and the leg had a step
    # there. The whole knee joint moves with it: cad/main.py and cad/scenes.py
    # put the knee actuator, the shin and the wheel at the same offset, so the
    # cheek still lands on the cover and the far cheek keeps its 1.0 mm against
    # the shin's rotor disc. See cad/parameters.py beside the dimension. It is
    # drawn
    # for an actuator whose output faces +X, so its rear cheek is on -X; the knee
    # motor is turned round like every lower joint on a limb, so the same mirror
    # that brings the plate across brings the clevis, putting the rear cheek on
    # the rear cover at +X and reaching the far cheek out past the shin's rotor
    # disc on -X. The cheek's own connector relief is a cut in Y and the mirror
    # leaves it where it is, aft, beside the harness, exactly as it does for the
    # plate.
    if lowerEnd == "clevis":
        lowerJoint = Pos(kneeOutboardOffset, 0, -jointZ) * mirrored(
            statorClevis(), Plane.YZ
        )
    else:
        lowerJoint = Pos(0, 0, -jointZ) * mirrored(statorPlate(), Plane.YZ)

    # The two cable-tie arches, standing on the INBOARD face at each end of the
    # waist -- the face the actuators are on, where a lead is inside the leg
    # rather than hanging off the back of it. A tie passes under the arch and
    # closes round the bundle lying beside it, holding the bundle against the
    # plate. cad/parameters.py carries why they are here and not cut through the
    # plate, and why the harness runs on this face and not aft of the flank.
    #
    # Each is a plain block lapped 1 mm into the plate with its tunnel cut
    # before it goes anywhere near the rest of the piece, and each stays its own
    # body like everything else here, so what it weighs and what it adds can be
    # measured on its own. The tunnel is cut through the lap as well: that part
    # of it is buried in the plate, which fills it back in, and the plate's own
    # face is what the strap runs on.
    #
    # The clevis end's arch is the one thing on this piece the saddle moves. A
    # closed box reaching 36 mm from the joint axis swallows an arch at 30.5 and
    # leaves its tunnel inside the cavity, so that end uses limbTieArchZClevis
    # instead; cad/parameters.py carries the reason beside both numbers.
    arches = []
    archOuterX = rotorHubInnerX - limbTieArchHeight
    lowerArchZ = limbTieArchZClevis if lowerEnd == "clevis" else limbTieArchZ
    for side, station in ((1, limbTieArchZ), (-1, lowerArchZ)):
        archZ = jointZ - station
        archBlank = Pos(archOuterX, limbTieArchY, side * archZ) * Box(
            limbTieArchHeight + limbTieArchLap,
            limbTieArchWidth,
            limbTieArchLength,
            align=(Align.MIN, Align.CENTER, Align.CENTER),
        )
        tunnel = Pos(
            rotorHubInnerX - limbTieArchTunnel,
            limbTieArchY,
            side * archZ,
        ) * Box(
            limbTieArchTunnel + limbTieArchLap + 1.0,
            limbTieArchWidth + 2.0,
            limbTieSlotWidth,
            align=(Align.MIN, Align.CENTER, Align.CENTER),
        )
        arches.append(archBlank - tunnel)

    return [waistPlate, gussetFront, gussetRear, upperDisc, lowerJoint, *arches]
