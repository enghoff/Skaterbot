"""Derived geometry for the six-motor wheeled robot.

Ported from lib/wheeled_parameters.kcl. Everything here follows from
cad/parameters.py and cad/joint.py; nothing is a free choice except where a
comment says so, and the torso's height is derived from what has to fit inside
it rather than being picked.
"""

from __future__ import annotations

from cad.joint import statorEndHeight
from cad.parameters import (
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
# not clearing it by half a millimetre of radius. The motor's front face is at
# actuatorDepth / 2 and the output disc fills the next 6 mm, so the first free
# plane is the disc's outer face. The hub lands flat on it and the wheel's
# centre plane ends up 12 mm outboard.
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
# WHAT SETS THE 65 mm, measured up from the inside face of the floor:
#
# * 9 mm of hip pitch saddle. The clevises stand that far proud of the floor
# across |x| = 26 to 60, so only the 51.5 mm between them is clear at this
# level. Nothing reserved is narrow enough to use it except the IMU, which
# goes there -- it is the stiffest spot in the pelvis, directly between the
# two hip joints, which is where an IMU wants to be anyway.
# * 30 mm for the power-entry block, 38 x 62 x 30, which therefore starts above
# the saddles rather than on the floor. The controller carrier, 76 x 46 x 12,
# sits BESIDE it in the same band.
# * 16 mm for the SBC, 85 x 58 x 16. It is wider than either of the other two,
# so it cannot share a band with them and has to go over the top.
#
# THAT SIDE-BY-SIDE PAIR IS WHY THE SHELL IS 125 mm WIDE and not the walking
# robot's 118. Power entry and the controller need 114 mm of interior between
# them; a 118 mm shell leaves 113.2 and misses by eight tenths of a millimetre.
# Widening to 125 leaves 120.2, which fits them with 6 mm to spare, and costs
# nothing in envelope: the robot is already 148 mm across at the hip saddles,
# so the torso is not what makes it wide. Stacking that pair instead would have
# cost 14 mm of height for the 7 mm of width it saved.
#
# With 2 mm between bands and 2.6 mm under the cover that is 59.6 mm of
# interior; 3 mm of floor and 2.4 mm of cover make 65 mm of torso, and the
# robot stands 339 mm rather than 380.
wheeledTorsoShellWidth = 125.0
wheeledTorsoBottom = wheeledHipPitchAxisHeight + jointKeepOut
wheeledTorsoHeight = 65.0
wheeledTorsoTop = wheeledTorsoBottom + wheeledTorsoHeight
wheeledTorsoCenterHeight = wheeledTorsoBottom + wheeledTorsoHeight / 2

# Torso-local, because that is the frame the payload is laid out in: the inside
# face of the floor, and the height of the saddles above it.
wheeledTorsoInteriorFloorZ = -wheeledTorsoHeight / 2 + torsoFloorThickness
wheeledHipSaddleRise = statorEndHeight - jointKeepOut - torsoFloorThickness
