"""Derived geometry for the six-motor wheeled robot.

Ported from lib/wheeled_parameters.kcl. Everything here follows from
cad/parameters.py and cad/joint.py; nothing is a free choice except where a
comment says so, and the torso's height is derived from what has to fit inside
it rather than being picked.
"""

from __future__ import annotations

from cad.joint import clevisOuterX, statorEndHeight
from cad.parameters import (
    hipCenterX,
    jointKeepOut,
    lowerLegLength,
    rotorHubOuterX,
    torsoFloorThickness,
    upperLegLength,
)

# ---------------------------------------------------------------------------
# The donor wheel
#
# PROVENANCE. These are the dimensions of a generic 80 mm inline-skate wheel,
# which is a consumer part: no vendor publishes a STEP for one, so unlike the
# DM-J3507 in reference/ there is no CAD to check this against. What is solid
# is the interface, because it is standardised by the bearing rather than by
# the wheel maker:
#
# * every skate wheel in this size takes a pair of 608 bearings, 8 x 22 x 7 mm
# (ISO 15 / ABEC 608), pressed into the hub from each side;
# * the two bearing seats are Ø22 and 24 mm apart across the hub, which is what
# fixes the 24 mm width;
# * the seats stop against a ridge of hub between them, 10 mm long, which is
# the length every inline bearing spacer is made to (10.1 to 10.3 mm as sold):
# the spacer lives inside that ridge, between the two inner races;
# * the 8 mm bore and the 24 mm width are the two dimensions an 8 mm skate axle
# relies on, so they are the same across brands.
#
# The hub outside diameter, the ridge's bore and the tread profile are NOT
# standardised. Ø45, Ø16 and a 20 mm crown radius are representative of an
# 80 mm wheel; all three need confirming with calipers against whichever wheel
# is actually bought, and so do the two seat depths, which the adapter's spigot
# and the cap are both drawn against.
skateWheelDiameter = 80.0
skateWheelWidth = 24.0
skateWheelHubDiameter = 45.0
skateWheelBearingBore = 22.0
# THE BORE IS NOT STRAIGHT THROUGH, and until 6 October 2026 this file and
# cad/skate_wheel.py both said it was: pull the 608s and "the seats and the 8 mm
# bore between them become one bore". They do not. The 8 mm bore was the
# bearings' own, and what is left between the seats is the ridge the outer races
# stopped against. Each seat is one bearing's width deep, so the ridge starts
# 7 mm in from either face -- where the 23 mm spigot this adapter used to carry
# would have stopped dead, with the wheel standing 16 mm off the motor.
skateWheelBearingSeatDepth = 7.0
# The ridge's bore, which has NOT been measured. It has to clear the spacer and
# the inner race, whose shoulder on a 608 is about Ø12, and stop the outer race,
# whose shoulder is about Ø19; Ø16 is the middle of that window. Nothing on the
# robot depends on it except how wide a hole the cap's floor has to span, and
# that floor is sized for the top of the window -- see wheelCapFloor below.
skateWheelRidgeBore = 16.0

# The tread is crowned rather than flat: it stands 4 mm proud at the centre
# line and falls to Ø72 at the sidewalls. A 20 mm radius through those two
# points is what puts the arc there, and it is close to the "round" profile
# sold for recreational skating. A flat or bullet profile would change the
# contact patch but not the envelope, which is what this model is used for.
skateWheelShoulderDiameter = 72.0
skateWheelCrownRadius = 20.0
skateWheelCrownCenterRadius = skateWheelDiameter / 2 - skateWheelCrownRadius

# ---------------------------------------------------------------------------
# Where the wheel sits on the actuator
#
# The hub cannot come any further inboard than the output disc's outer face,
# and diameters have nothing to do with it. The wheel is coaxial with the
# motor, so any plane the motor body occupies is a plane the hub cannot be in
# at all -- a Ø45 hub sharing x with the Ø46 body would be buried inside it,
# not clearing it by half a millimetre of radius. The Ø46 body ends at
# actuatorDepth / 2 less the millimetre its output register stands proud by,
# the register fills that millimetre, and the output disc fills the 6 mm beyond
# it -- so the first free plane is the disc's outer face. The hub lands flat on
# it and the wheel's centre plane ends up 12 mm outboard.
#
# That 12 mm is the whole of the overhang this design adds. Standing, each
# wheel carries about 10 N, so the extra moment on the actuator's output
# bearing is 0.12 Nm, and about 0.36 Nm at three times body weight. Both are
# inside the 0.45 / 1.35 Nm the flat limbs already ask of the same bearing --
# the open question recorded in NOTES.md -- so the wheel does not become the
# governing case.
skateWheelInnerX = rotorHubOuterX
skateWheelCenterX = skateWheelInnerX + skateWheelWidth / 2
skateWheelOuterX = skateWheelInnerX + skateWheelWidth
# The two faces of the centre ridge: the inboard seat's floor, which the
# spigot stops short of, and the outboard seat's, which the cap lands on.
skateWheelRidgeInnerX = skateWheelInnerX + skateWheelBearingSeatDepth
skateWheelRidgeOuterX = skateWheelOuterX - skateWheelBearingSeatDepth

# ---------------------------------------------------------------------------
# The printed adapter
#
# A Ø22 spigot centres the wheel in its INBOARD bearing seat once the 608s are
# pulled out, and an M5 on the axis clamps the hub back against the output
# disc. Torque reaches the wheel through that clamped face, not through the
# spigot: an M5 at a modest 1 kN preload on the disc's r11-r18 annulus is good
# for about 4 Nm of friction against the actuator's 3 Nm peak, where a press
# fit alone would depend on how the printed spigot came off the bed.
#
# THE SPIGOT IS 6 mm LONG, NOT 23, since 6 October 2026. It ran the hub's whole
# width on the reading that the bore went straight through, and it does not:
# the hub's centre ridge starts one seat's depth in. So the spigot stops a
# millimetre short of the ridge, which leaves the hub's inboard face to land on
# the disc exactly as it did, and the printed cap in the OUTBOARD seat is what
# presses the hub down -- see the clamp below. The millimetre is what the seat
# may measure shallow by before the spigot, rather than the disc, takes the hub.
#
# THE SIX SCALLOPS ARE NOT DECORATION. The actuator's own output screws sit on
# Ø24, which is two millimetres bigger than the wheel bore that has to pass
# over them, so a plain Ø22 spigot walls its own mounting screws in and the
# adapter cannot be fitted to the motor at all. A 2.5 mm key is 2.89 mm across
# corners, so at r12 its shaft sweeps r10.56 to r13.44 and the spigot's r11
# surface stands a fraction of a millimetre inside that.
#
# Six axial scallops on the bolt centres open that path the whole length of the
# spigot. What is left is 6 mm of Ø22 on six pads, which is plenty: the spigot
# only centres the wheel, it does not drive it.
wheelSpigotDiameter = skateWheelBearingBore
wheelKeyAccessDiameter = 4.5
# The plug is what ties the spigot to the disc, and it has to stay inside r9.25
# or it fills the screw heads' own counterbores back in -- the failure this
# project has been caught by before, and the reason the adapter is left as
# interpenetrating bodies rather than a union. Ø17 clears them by half a
# millimetre.
wheelSpigotPlugDiameter = 17.0
wheelSpigotLength = skateWheelBearingSeatDepth - 1.0
# The M5 heat-set insert's pocket: Ø6.4 is what a 7 mm knurl wants.
#
# THE INSERT GOES IN FROM THE MOTOR SIDE, since 6 October 2026, and the clamp
# pushes it further in rather than pulling it out. Pressed in from the wheel's
# side, as it was, the screw pulls the insert back the way it came, and all that
# holds it is the plastic its knurl melted into. Pressed in from the back until
# it stops against the step below, it can only fail by shearing that same length
# of plastic AND punching out the plug of adapter in front of it, which is the
# 3.5 mm between the step and the spigot's end. So a 6 mm insert carries about
# what the 10 mm one did the other way round, 9.5 mm of shear against 10, and an
# 8 mm one more. That is what lets the clamp use ThinkRobotics' insert, whose
# only M5 is that short. It is arithmetic, not a test: a printed coupon with an
# insert set in it and the screw torqued up is what proves it.
#
# The insert has to be in before the adapter goes onto the motor, which it is:
# the back face is open on the bench and covered once it is bolted down.
wheelSpigotInsertBore = 6.4
# How deep the pocket runs in from the back face, to the step the insert stops
# against. Deep enough for the longest the insert might be -- the listing says 6
# and its own drawing 8 -- with half a millimetre of the back face left clear,
# so the melt the iron pushes back up the pocket stays below the face that lands
# on the motor's output register. A 6 mm insert simply sits 2.5 mm down.
wheelSpigotInsertDepth = 8.5
# The screw's clearance on from the step to the spigot's end, the same Ø5.5 the
# cap's floor and the journal screw use. The step it leaves is what the insert
# is pressed against.
wheelSpigotClearance = 5.5

# ---------------------------------------------------------------------------
# What the clamp is made of
#
# A printed cap and three bought items on the wheel's axis.
#
# THE CAP REPLACED A Ø30 PENNY WASHER on 6 October 2026, because nobody in
# India sells an M5 one in a basket and the nearest stand-in was an import. The
# washer lay on the hub's outer face and spanned its Ø22 bore as a plate in
# bending, which is why its thickness was load-bearing. The cap sits in the
# outboard bearing seat instead and lands on the centre ridge, so the preload
# goes into the hub end-on, through the face the bearing used to push on: about
# 6 MPa on the ridge at 1 kN with the Ø16 bore drawn, 10 at the widest the
# bearing allows. The only plate left is the cap's own floor, spanning the
# ridge's bore.
wheelCapDiameter = skateWheelBearingBore
# THE FLOOR IS SIZED FOR THE WIDEST RIDGE BORE THE BEARING ALLOWS. The screw
# head bears on the washer and the washer on the floor, and the ridge holds the
# floor up from its bore outwards, so the floor is an annular plate loaded near
# its middle across whatever the ridge's bore turns out to be. At 1 kN, treating
# the load as a ring under the head's Ø8.5, 6 mm keeps the bending stress under
# 18 MPa across a Ø19 bore and about 14 across the Ø16 drawn -- a plate estimate,
# and a pessimistic one for a floor this thick across a span this short. The
# cap prints floor-down, so its layers lie across that stress rather than
# along it.
wheelCapFloor = 6.0
# M5 clearance through the floor, the same Ø5.5 the journal screw passes.
wheelCapBore = 5.5
# The washer's Ø11 with half a millimetre of air round it.
wheelCapCounterbore = 12.0
#
# PROVENANCE: ISO 4762 (DIN 912) socket cap screw, M5 -- head Ø8.5 x 5.0 across a
# 4 mm hex socket -- which is also what fastdep lists for the screw bought: a
# DIN 912 12.9 M5 x 25 with an 8.28-8.72 head 4.82-5.00 tall, read 2026-10-06.
# A cap screw is a catalogue part and every maker builds it to the same table,
# so it is not in reference/.
wheelClampScrewDiameter = 5.0
# HOW LONG THE SCREW CAN BE, which is still not a free choice. Under the head
# are the 1.5 mm washer, the cap's 6 mm floor, the ridge's 10, the millimetre
# the spigot stops short of the ridge and the spigot's own 6 mm and the disc's
# 6: 30.5 mm to the adapter's back face. So a 30 is the length, and its tip
# stops half a millimetre inside that face, through the whole of an insert
# that sits against the step whichever of its two lengths it turns out to be.
# A floor or a washer that comes out thin moves the tip out towards the motor,
# and the motor's output face is recessed Ø8 x 1.85 deep at its centre in the
# vendor STEP (reference/dm_3507_3d-241021.STEP, read 2026-10-06), so the tip
# has 2.35 mm before it can touch anything -- unmeasured on a real motor, and
# not needed unless the stack is a millimetre thin.
#
# It was 25 for an afternoon, while the insert sat at the spigot's end; 12 while
# the washer lay on the hub's face and the insert sat at the far end of a 23 mm
# spigot; and 20 before that, which bottomed in that spigot's blind bore --
# docs/BOM.md section 10 keeps the history.
wheelClampScrewLength = 30.0
# The socket is drawn only so the head reads as a cap head. 4 mm across the
# flats is the M5 key; the depth is nominal.
wheelClampSocketAcrossFlats = 4.0
wheelClampSocketDepth = 2.5
# The washer under the head, inside the cap: fastdep's plain M5, which it lists
# as Ø11 x 1.5 mild steel (read 2026-10-06). It is what keeps the head off
# printed plastic. 1 kN on the bare Ø8.5 head is 30 MPa on the cap's floor; on
# this washer it is 14.
wheelClampWasherDiameter = 11.0
wheelClampWasherThickness = 1.5
# Drawn at M5 clearance. fastdep gives the hole as 5 mm and ISO 7089 as 5.3 to
# 5.48; nothing bears on that face, and 5.5 keeps the shank from being drawn in
# a slot narrower than any process could tell from contact.
wheelClampWasherBore = 5.5
# The insert as bought: ThinkRobotics' brass heat-set insert, whose M5 is
# listed as "M5 X 6mm" and drawn on the same page as Ø7.0 over the knurl, a Ø5.9
# pilot and 8.0 long (read 2026-10-06). The two disagree, and it is drawn at the
# drawing's 8 because that is the one the pocket has to hold; the step it is
# pressed against fixes its outer end either way. Measure one when it arrives.
# It was the 10 mm Amazon.in insert, sat at the spigot's end, until the same day,
# and 9.5 before that.
wheelInsertLength = 8.0
# Its thread is drawn at pitch diameter rather than as a helix, so a screw in it
# overlaps by a quarter of a millimetre the way an engaged thread does. M5 pitch
# diameter is 4.48.
wheelInsertThreadDiameter = 4.5
# The cap head. These two moved here from cad/wheel.py, which is where the port
# left them: they are the screw's dimensions and they belong with the rest of it.
capHeadDiameter = 8.5
capHeadLength = 5.0
# Where the cap stands on the axis: on the ridge, and as tall as its floor, the
# washer and the head, so the head sits flush with its outer end. It stands
# 5.5 mm proud of the hub's outer face, where the old washer and head stood 7.
wheelCapInnerX = skateWheelRidgeOuterX
wheelCapOuterX = (
    wheelCapInnerX + wheelCapFloor + wheelClampWasherThickness + capHeadLength
)

# ---------------------------------------------------------------------------
# Axis heights
prototypeWheelAxisHeight = skateWheelDiameter / 2

wheeledKneeAxisHeight = prototypeWheelAxisHeight + lowerLegLength
wheeledHipPitchAxisHeight = wheeledKneeAxisHeight + upperLegLength

wheeledShinCenterZ = (wheeledKneeAxisHeight + prototypeWheelAxisHeight) / 2
wheeledThighCenterZ = (wheeledHipPitchAxisHeight + wheeledKneeAxisHeight) / 2

# Hip pitch is the top of this robot's leg, so the chain stops here. There was
# a wheeledHipAxisOffset and a wheeledHipCarrierCenterZ above it -- the 51 mm
# span between hip roll and hip pitch, and the midpoint the carrier sat on --
# and both went when hip roll did. The 51 mm has not disappeared, it has moved
# into the pelvis: cad/torso.py's shell floor is now that much lower.

# ---------------------------------------------------------------------------
# The torso, sized by what goes in it
#
# The walking robot's torso is 274 to 380 mm, and its 106 mm height was settled
# before the electronics were laid out. This one is not a free number at either
# end. Its floor is pinned at 274 -- one joint keep-out above the hip pitch
# axis, because that floor IS the seat the two hip clevises are rooted in -- and
# its ceiling is wherever the reserved payload stops.
#
# THE ROBOT CARRIES A BATTERY AGAIN, and that is what this box is now sized
# around. It was tethered from August 2026, when the on-board pack was deleted
# because no 6S brick would fit the keel and its 190 g was the whole of the mass
# headroom; the height below is what it costs to put one back. Both of those
# objections were answered rather than waved away -- the pack is two 3S bricks
# in series rather than one 6S, which is what makes it fit, and the headroom is
# there now because deleting hip roll gave 700 g back. docs/NOTES.md carries the
# decision.
#
# WHAT SETS THE 89 mm, measured up from the inside face of the floor:
#
# * 9 mm of hip pitch saddle. The clevises stand that far proud of the floor
# across |x| = 26 to 60, so only the 51.5 mm between them is clear at this
# level. Nothing reserved is narrow enough to use it except the IMU, which
# went there -- it is the stiffest spot in the pelvis, directly between the
# two hip joints -- until 2026-10-14, when it moved under the deck because its
# socket is on its underside. The square is empty now; the 9 mm is the saddle's.
# * 39 mm for the battery, 78 x 54 x 39, which was drawn for two 3S 2200 mAh
# bricks ON EDGE side by side -- a size of brick nobody makes, it turned out on
# 2026-09-30, so the bay now holds two 1000 mAh packs and the foam round them.
# It was 36 until the packs arrived and were measured on 2026-10-05: their
# bodies are 35 tall where the listing said 32, and their lead ends up to 38,
# and cad/electronics.py says why that makes 39. That orientation is the whole
# reason a pack fits at all:
# laid flat the pair is 72 mm fore and aft against 67.2 mm of interior depth,
# and on edge it is 36. The power bay, 52 x 54 x 39, sits BESIDE it in
# the same band and is now the same height, because the battery sets it and
# the bay may as well use what the battery has already paid for.
# * 3 mm of electronics deck, cad/deck.py, which is a printed plate screwed to
# four bosses on the side walls. It carries both boards above the battery and
# holds the packs down, and it lifts out to reach them.
# * 12 mm for the controller carrier, 76 x 46 x 12, standing on the deck.
# * 16 mm for the SBC, 85 x 58 x 16. It is wider than either of the other two,
# so it cannot share a band with them and has to go over the top.
#
# THE SHELL'S WIDTH IS NO LONGER SET BY THE PAYLOAD. It was, and the history is
# worth keeping because it is what makes the present number free: 125 held the
# tethered pair of boards lying flat; 135 held the pack and a 38 mm power block
# built around a PCB we would have drawn ourselves; 141 held the pack and a
# BOUGHT 50 x 50 mm distribution board, which is the smallest 3S-6S board on the
# market and 12 mm wider than the bay the custom one needed. The pack is 78 mm of
# reservation and the power bay is 52, which with 2 mm at each wall and 2.2
# between them is the 136.2 mm of interior that asked for 141.
#
# WHAT SETS IT NOW IS THE HIP JOINT, because the payload's requirement is a floor
# and the joint's is a plane. Each hip clevis is rooted in this floor and runs out
# through the lower side wall -- cad/torso.py says why the load wants two faces
# rather than one -- and its saddle ends at the front cheek's outer face, 76.95 mm
# from the centre line. At 141 the shell stopped 6.45 mm short of that, so the
# saddle stood proud of its own wall on both sides: a step in the flank, an
# overhang the printer has to bridge, and a ledge on the outside of a pelvis that
# has to shed a fall. Taking the wall out to the same plane removes all three, and
# the joint's structure runs into a flat side rather than out of one.
#
# So it is derived, and derived from cad/joint.py rather than typed here: twice
# the hip half-spacing plus the clevis's outboard face. Move the hips or change
# the actuator's depth and the pelvis follows, which is the relationship the rest
# of this file already has with the leg.
#
# THE 12.9 mm IT ADDS IS ALL SLACK. The interior goes to 149.1 mm against the
# 136.2 the payload needs, and cad/electronics.py spends none of it: battery and
# power bay each stay 2 mm off their own wall, so the whole of it lands in the gap
# between the two bays, which goes from 2.2 mm to 15.1. That is a lead chase back,
# having been lost to the bought board.
#
# It still costs nothing in envelope, for a better reason than before. The shell
# is now exactly as wide as the hip clevises it carries, and only their Ø26
# bearing bosses stand outside it, at +/-80.45; the wheels are at +/-104 either
# way.
#
# With 2 mm between the two upper bands and 2.6 mm under the cover that is
# 83.6 mm of interior; 3 mm of floor and 2.4 mm of cover make 89 mm of torso,
# and the robot stands 363 mm rather than 339. Those 24 mm are what the battery
# costs in height, and cad/electronics.py's bands are where they went. It was
# 86 and 360 until the measured packs took the battery's band from 36 to 39 on
# 2026-10-05; the 3 mm went in under the deck, so everything over it -- the
# boards, the rear-wall connectors, the cover -- rose with it and kept its place.
wheeledTorsoShellWidth = (hipCenterX + clevisOuterX) * 2
wheeledTorsoBottom = wheeledHipPitchAxisHeight + jointKeepOut
wheeledTorsoHeight = 89.0
wheeledTorsoTop = wheeledTorsoBottom + wheeledTorsoHeight
wheeledTorsoCenterHeight = wheeledTorsoBottom + wheeledTorsoHeight / 2

# Torso-local, because that is the frame the payload is laid out in: the inside
# face of the floor, and the height of the saddles above it.
wheeledTorsoInteriorFloorZ = -wheeledTorsoHeight / 2 + torsoFloorThickness
wheeledHipSaddleRise = statorEndHeight - jointKeepOut - torsoFloorThickness
