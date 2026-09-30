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
# * the 8 mm bore and the 24 mm width are the two dimensions an 8 mm skate axle
# relies on, so they are the same across brands.
#
# The hub outside diameter and the tread profile are NOT standardised. Ø45 and
# a 20 mm crown radius are representative of an 80 mm wheel; both need
# confirming with calipers against whichever wheel is actually bought, and the
# adapter's Ø22 spigot is the only dimension that has to be right first time.
skateWheelDiameter = 80.0
skateWheelWidth = 24.0
skateWheelHubDiameter = 45.0
skateWheelBearingBore = 22.0

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

# ---------------------------------------------------------------------------
# The printed adapter
#
# A Ø22 spigot fills both bearing bores once the 608s are pulled out, and an
# M5 on the axis clamps the hub back against the output disc. Torque reaches
# the wheel through that clamped face, not through the spigot: an M5 at a
# modest 1 kN preload on the disc's r11-r18 annulus is good for about 4 Nm of
# friction against the actuator's 3 Nm peak, where a press fit alone would
# depend on how the printed spigot came off the bed.
#
# THE SIX SCALLOPS ARE NOT DECORATION. The actuator's own output screws sit on
# Ø24, which is two millimetres bigger than the wheel bore that has to pass
# over them, so a plain Ø22 spigot walls its own mounting screws in and the
# adapter cannot be fitted to the motor at all. A 2.5 mm key is 2.89 mm across
# corners, so at r12 its shaft sweeps r10.56 to r13.44 and the spigot's r11
# surface stands a fraction of a millimetre inside that.
#
# Six axial scallops on the bolt centres open that path the whole length of the
# spigot. What is left is 19 mm of Ø22 on six pads, which is plenty: the spigot
# only centres the wheel, it does not drive it.
wheelSpigotDiameter = skateWheelBearingBore
wheelKeyAccessDiameter = 4.5
# The plug is what ties the spigot to the disc, and it has to stay inside r9.25
# or it fills the screw heads' own counterbores back in -- the failure this
# project has been caught by before, and the reason the adapter is left as
# interpenetrating bodies rather than a union. Ø17 clears them by half a
# millimetre.
wheelSpigotPlugDiameter = 17.0
# One millimetre short of the hub's outer face, so the clamp washer lands on
# the hub and not on the end of the spigot.
wheelSpigotLength = skateWheelWidth - 1.0
# M5 heat-set insert, Ø6.4 x 9.5 nominal, given a little depth to seat into.
wheelSpigotInsertBore = 6.4
wheelSpigotInsertDepth = 12.0
wheelClampWasherDiameter = 30.0
wheelClampWasherThickness = 2.0

# ---------------------------------------------------------------------------
# What the clamp is made of
#
# Three bought items on the wheel's axis, and two of them were drawn as plain
# cylinders standing in for the space they occupy until the screw and the insert
# were modelled properly.
#
# PROVENANCE: ISO 4762 (DIN 912) socket cap screw, M5 -- head Ø8.5 x 5.0 across a
# 4 mm hex socket -- and the heat-set insert the spigot's bore was already cut
# for, Ø6.4 x 9.5 nominal. Neither is in reference/: a cap screw and a heat-set
# insert are catalogue parts and every maker builds them to the same table.
wheelClampScrewDiameter = 5.0
# HOW LONG THE SCREW CAN BE, which is not a free choice. Under the head sits the
# 2 mm washer, then the millimetre the spigot is held short of the hub's face,
# and then a BLIND bore: 12 mm deep as this file declares it, 14 as
# cad/wheel_adapter.py actually cuts it, because that cutter's 2 mm overrun goes
# inboard past the pocket's bottom rather than outward past its open mouth. So
# the reach is 15 mm against the nominal pocket and 17 mm against the drawn one,
# and either way a screw longer than that lands on the bottom and the joint
# never sees preload -- the M5 x 20 the bill of materials asks for stands 3 mm
# of its shank inside solid printed spigot. 12 is the standard length that fits
# both readings: it threads through 9 of the insert's 9.5 mm and stops 3 mm
# clear of the nominal bottom, 5 mm clear of the drawn one.
wheelClampScrewLength = 12.0
# The socket is drawn only so the head reads as a cap head. 4 mm across the
# flats is the M5 key; the depth is nominal.
wheelClampSocketAcrossFlats = 4.0
wheelClampSocketDepth = 2.5
# M5 clearance through a washer this size, which is a penny washer rather than
# anything in the ISO 7089 series -- no standard flat washer for M5 is Ø30.
wheelClampWasherBore = 5.5
# The insert itself, seated flush with the spigot's outer end. The bore it goes
# into is 12 mm deep for the 9.5 mm insert, which is the seating allowance the
# comment above records -- and 14 as drawn, for the overrun reason below.
wheelInsertLength = 9.5
# Its thread is drawn at pitch diameter rather than as a helix, so a screw in it
# overlaps by a quarter of a millimetre the way an engaged thread does. M5 pitch
# diameter is 4.48.
wheelInsertThreadDiameter = 4.5
# The cap head. These two moved here from cad/wheel.py, which is where the port
# left them: they are the screw's dimensions and they belong with the rest of it.
capHeadDiameter = 8.5
capHeadLength = 5.0

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
# WHAT SETS THE 86 mm, measured up from the inside face of the floor:
#
# * 9 mm of hip pitch saddle. The clevises stand that far proud of the floor
# across |x| = 26 to 60, so only the 51.5 mm between them is clear at this
# level. Nothing reserved is narrow enough to use it except the IMU, which
# goes there -- it is the stiffest spot in the pelvis, directly between the
# two hip joints, which is where an IMU wants to be anyway.
# * 36 mm for the battery, 78 x 54 x 36, which was drawn for two 3S 2200 mAh
# bricks ON EDGE side by side -- a size of brick nobody makes, it turned out on
# 2026-09-30, so the bay now holds two 1000 mAh packs and the foam round them,
# and kept its size so that nothing here moved. That orientation is the whole
# reason a pack fits at all:
# laid flat the pair is 66 mm across the robot against 67.2 mm of interior
# depth, and on edge it is 52. The power bay, 52 x 62 x 36, sits BESIDE it in
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
# 80.6 mm of interior; 3 mm of floor and 2.4 mm of cover make 86 mm of torso,
# and the robot stands 360 mm rather than 339. Those 21 mm are what the battery
# costs in height, and cad/electronics.py's bands are where they went.
wheeledTorsoShellWidth = (hipCenterX + clevisOuterX) * 2
wheeledTorsoBottom = wheeledHipPitchAxisHeight + jointKeepOut
wheeledTorsoHeight = 86.0
wheeledTorsoTop = wheeledTorsoBottom + wheeledTorsoHeight
wheeledTorsoCenterHeight = wheeledTorsoBottom + wheeledTorsoHeight / 2

# Torso-local, because that is the frame the payload is laid out in: the inside
# face of the floor, and the height of the saddles above it.
wheeledTorsoInteriorFloorZ = -wheeledTorsoHeight / 2 + torsoFloorThickness
wheeledHipSaddleRise = statorEndHeight - jointKeepOut - torsoFloorThickness
