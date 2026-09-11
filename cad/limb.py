"""Flat-plate limb.

Ported from lib/limb.kcl, comments and all.

One parametric limb, used for the thigh and the shin. It is a plate lying in a
single plane: a Ø52 disc bolted flat to one actuator's rear cover, a Ø36 disc
bolted to the next actuator's output, and a channel waist between them. There is
no clevis, no saddle and no closed shell, and nothing reaches around an actuator
any more.

Local frame: the limb axis is Z, both joint axes are X, and the two joint centres
sit at z = +/- limbLength/2. The plate lies on the +X side with both actuators
inboard of it. That works because the knee actuator is turned round -- see the
note in parameters.py -- so the upper joint presents its output face and the
lower joint presents its rear cover on the same side.

A limb for the other hand is this one mirrored across YZ. cad/thigh.py and
cad/shin.py each export both hands; and because the two leg segments are the
same 105 mm, the right thigh and the left shin are the same print, as are the
right shin and the left thigh. Two distinct limb parts.

The waist is a plain plate. It carried two stiffening flanges on its outboard
face for a while; they came off on 30 August 2026 once the numbers were run,
because they bought stiffness and almost no strength, and none at all at the
section that decides whether a limb breaks. The reasoning is kept in
cad/parameters.py beside the waist dimensions, and in NOTES.md.

What is left is a single flat profile, 6 mm thick from one end to the other,
which is both the cheapest thing to print and the strongest way to print it:
laid flat, every fibre runs along the limb and no load crosses a layer line.

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
    Rot,
    extrude,
    make_face,
)

from cad.geometry import mirrored
from cad.joint import outputDisc, outputRegisterCutter, statorPlate
from cad.parameters import (
    actuatorRearBoltOffset,
    limbPlateThickness,
    limbWaistDepth,
    limbWaistUpperZ,
    m3CapHeadStandoff,
    rotorHubDiameter,
    rotorHubInnerX,
    statorPlateDiameter,
)


def limbAssembly(limbLength: float) -> list:
    """One limb, as five interpenetrating bodies.

    Returns a LIST, not a single solid, because that is what the KCL returned
    and what the golden STEP contains: the waist plate occupies exactly the same
    band in X as both discs, which is the union the Zoo engine refused. Every
    overlap is millimetres of real material, so a slicer that merges coincident
    shells prints this as the single plate it is -- verify that before printing.
    Unioning them for real is a phase 3 change; see docs/BUILD123D_MIGRATION.md.
    """
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
    waistUpperZ = limbWaistUpperZ
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
    cornerHalfWidth = limbWaistDepth / 2
    cornerDepth = cornerHalfWidth - (actuatorRearBoltOffset + m3CapHeadStandoff)
    cornerFlushZ = -jointZ + sqrt((statorPlateDiameter / 2) ** 2 - cornerHalfWidth**2)
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

    upperDisc = Pos(0, 0, jointZ) * outputDisc()
    # The stator plate is drawn behind an actuator whose output faces +X. This
    # limb's lower actuator is turned round, so the plate is spun to the near side
    # to land on the rear cover that now faces +X with everything else.
    lowerPlate = Pos(0, 0, -jointZ) * (Rot(0, 0, 180) * statorPlate())

    return [waistPlate, gussetFront, gussetRear, upperDisc, lowerPlate]
