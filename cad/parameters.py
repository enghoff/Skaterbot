"""Shared robot layout parameters.

Global actuator, kinematic, packaging, and material-envelope dimensions. This is
the port of lib/parameters.kcl and it is the single source of mechanical
dimensions, exactly as that file was: the comments carry the provenance -- which
vendor STEP, which 2D print, which measurement, and where two sources were
cross-checked against each other -- and they transfer word for word.

NAMES ARE THE KCL'S, NOT PYTHON'S. Every constant below keeps the camelCase name
it had in the KCL rather than being renamed to snake_case. That is deliberate and
it is worth more than the style points it costs. Gate A of
docs/BUILD123D_MIGRATION.md compares this module against
reference/golden/parameters.json name for name, so keeping the names identical
removes the mapping layer that would otherwise be the easiest thing in the
migration to get quietly wrong. It also keeps roughly 290 KB of existing
documentation -- NOTES.md, PLAN.md, the BOM, every comment in this file --
pointing at names that still exist.

UNITS. Lengths are MILLIMETRES and angles are DEGREES, plain floats, matching the
KCL's own convention and simulation/kcl_params.py's. build123d works in
millimetres by default, so a length here is passed straight into it. Angles are
converted at the point of use, which is why the trigonometry below spells
radians() out.
"""

from __future__ import annotations

from math import cos, radians

actuatorDiameter = 46.0
actuatorDepth = 37.9
actuatorClearance = 0.3

# THE OUTPUT REGISTER STANDS PROUD OF THE HOUSING, and actuatorDepth above is
# the OVERALL length rather than the length of the body. The vendor 2D print
# calls out both figures -- 36.90 to the housing's front face and 37.90 to the
# output face -- and the vendor STEP is unambiguous about which is which: a Ø46
# cylinder runs from the rear face to 1.00 mm short of the output end, and a Ø30
# register fills that last millimetre on its own. Nothing else is in that plane.
#
# WHY IT MATTERS, AND WHAT IT COST. A plate bolted to the Ø24 output circle
# seats on the REGISTER and has to CLEAR the housing, which is not what this
# model assumed until 14 September 2026: the register was taken to fill a 1.2 mm
# pocket in the plate while the plate itself landed on the housing's front face,
# and that face was believed to be at actuatorDepth / 2. With the housing
# 1.00 mm shorter than that, the plate's seating annulus was 1.0 mm out in free
# air, the register's face sat under an empty pocket, and the six M3 that carry
# the joint's whole output torque were clamping across the gap. The nut captive
# in that pocket was floating in it too.
#
# Nothing on the robot moves because of it. The correction is local to the
# plate: the register pocket is retired -- see the block further down where its
# two dimensions used to be declared -- and the plate lands flat on the register
# where it always sat, one of these projections clear of the housing behind it.
# Had the plate been moved OUT to meet a register believed to fill a 1.2 mm
# pocket, its two ends would have finished 0.7 mm apart along the joint axis --
# the limb lands a plate on a rear cover at one end and on this register at the
# other -- and the flat limb's whole point is that its exterior is one plane.
actuatorHousingDepth = 36.9
actuatorOutputProjection = 1.0

# DM-J3507-2EC mounting interface, measured from the vendor STEP
# (gitee.com/kit-miao/DM-J3507-2EC, dm_3507_3d-241021.STEP) and cross-checked
# against the 2D print and manual V1.0. Axial stations are measured from the
# output face towards the rear. These replace the guessed flange and boss the
# proxy used to carry; both bolt circles sit inside the actuator's 46 mm
# diameter, so a cheek that clears the body at Ø46.6 has no material where the
# actuator actually attaches.
actuatorOutputBoltCircle = 24.0
actuatorOutputBoltCount = 6
actuatorOutputRegister = 30.0
actuatorHousingBoltCircle = 41.0
actuatorHousingBoltCount = 4

# Rear face. Confirmed twice over: the vendor 2D print calls out 4xM3 tapped
# 4 mm deep with 4 x Ø3.20 clearance on the same four locations, and the STEP
# agrees exactly -- Ø3.20 through the 3.20 mm rear cover (3505_0002) into
# Ø2.50 tapped holes (the M3 tap drill) in the plate beneath (3505_00), both
# on Ø41.00 at 45°, 135°, 225° and 315°. A screw therefore crosses the cover
# before it reaches thread, so useful length is bracket + cover + engagement.
# Not to be confused with the 4 x M2.5 on Ø42.00 at 33.5°/146.5°/213.5°/326.5°,
# which hold the driver compartment shut.
actuatorRearBoltCircle = 41.0
actuatorRearBoltCount = 4
actuatorRearBoltPhase = 45.0
actuatorRearBoltDepth = 4.0
actuatorRearCoverThickness = 3.2
# The same four bolts as Cartesian offsets. At 45 degrees on Ø41 both offsets
# are the same number, so every printed part that has to keep clear of the rear
# pattern measures against this one value rather than recomputing the trig.
actuatorRearBoltOffset = (
    actuatorRearBoltCircle / 2 * cos(radians(actuatorRearBoltPhase))
)

# The connector flat: a chord 19.0 mm from the axis, about 25.9 mm wide,
# subtending about 69°. The connectors sit at the rear end against it. An
# earlier actuatorConnectorStation = 31.7mm was wrong -- it was plate 3505_00's
# placement origin misread as a connector -- and has been removed. How far a
# mated plug stands off the flat is estimated below rather than measured.
actuatorConnectorFlatOffset = 19.0
actuatorConnectorFlatArc = 69.0
# How far a mated plug stands off the flat. THIS IS AN ESTIMATE, not a
# measurement: no actuator has been in hand to measure. What the manual does
# give is which connectors they are -- the supply and CAN come in on an SH1.0
# 3-pin and the debug serial on an SH1.0 8-pin, both 200 mm flying leads. JST
# SH is a 1.0 mm pitch series whose mated housing stands about 3 mm off its
# header, and 28 AWG lead needs roughly 5 mm to leave and turn, so 8 mm is the
# working figure. It puts the keep-out at r 27, outside the Ø52 cheek, which is
# why the cheek is truncated on the flat rather than trimmed to it. Measure
# this on the first actuator that arrives and correct it here.
actuatorConnectorPlugProjection = 8.0
hipSpacing = 96.0
hipCenterX = hipSpacing / 2

# ---------------------------------------------------------------------------
# The foot, the ankle, and the walking robot's axis chain -- RETIRED
#
# footLength, footWidth, footCenterY, soleThickness, footTrayHeight,
# ankleAxisHeight, kneeAxisHeight, hipPitchAxisHeight, hipRollAxisHeight,
# hipAxisOffset, torsoBottom, torsoTop, torsoHeight, torsoCenterHeight,
# torsoWidth and torsoDepth are gone, with the walking robot they described.
# This branch is the wheeled robot and nothing on it stands on a foot.
#
# The reasoning is kept here because it is the useful part and because the
# numbers themselves are recoverable from the `main` branch, where the walking
# robot still lives, and from reference/golden/parameters.json, which froze
# every one of them before this migration began. tools/gate_a.py knows they are
# retired rather than unported, and checks that they are still absent.
#
# WHAT THE FOOT DECIDED, AND WHERE THAT DECISION WENT. The foot was a
# replaceable 2 mm sole under a 10 mm open-topped tray, and those two
# thicknesses are what set the ankle axis: the actuator's body came to rest on
# the tray's top plane, so the axis sat a body radius plus one clearance above
# it -- 23 + 1 + 2 + 10 = 36 mm. It had been 44 mm, which is where the axis
# lands if the rotor bridge is stacked ON TOP of the tray rather than nested
# inside it; that arrangement left the motor floating 9 mm clear of the foot and
# 5.6 mm of trapped air under the spreader, so the ankle's load reached the
# floor only through two transverse ribs. Dropping to 36 closed both, and cost
# 8 mm of leg.
#
# The wheeled robot answers the same question with a wheel instead of a foot,
# and the answer is simply the wheel's radius: prototypeWheelAxisHeight in
# cad/wheeled_parameters.py is skateWheelDiameter / 2, and the knee and hip pitch
# axes are stacked on that. So the whole chain above has a replacement, one
# module over, derived from a bought part rather than from a printed one.
#
# The walking torso ran 274 to 380 mm at 126 x 74. The wheeled one is derived
# rather than chosen and comes out 125 x 68 x 65 with its floor still at 274.

# How much air every printed part leaves against the O46 housing: one
# millimetre. jointKeepOut further down is this same figure written as a
# radius. The ankle stack used to be the other place it was spent.
jointBodyClearance = 1.0

# Both leg segments are the same length, which is why the right thigh and the
# left shin are one print. They outlived the foot: the wheeled robot stacks them
# on the wheel axis instead of the ankle axis, and neither number moved.
lowerLegLength = 105.0
upperLegLength = 105.0

# The two skins of the pelvis box. They live here rather than in the pelvis
# files because both pelvises use them and because the wheeled robot's torso
# height is derived from them -- its ceiling is the reserved payload plus these
# two thicknesses, so they are an input to a dimension rather than a detail of
# one part. 3 mm of floor is what the hip saddles root into; 2.4 mm of cover is
# two perimeters and a skin either side at this nozzle.
torsoFloorThickness = 3.0
torsoCoverThickness = 2.4

# ---------------------------------------------------------------------------
# Tether -- DELETED, September 2026
#
# The robot was tethered from August 2026 to September 2026: 24 V and CAN came
# down one umbilical from a bench supply and there was no pack on board.
# tetherCableDiameter lived here, 12 mm, an estimate from the wire the BOM
# specifies rather than a measurement of a made-up cable, and the entry slot and
# both tie-down slots in the pelvis were derived from it.
#
# It is gone because the battery came back. The wall it entered through now
# carries an XT90-S disconnect and a charge port instead -- it carried a 6S
# balance port as well until an on-board BMS took the cell taps over -- which are
# cad/electronics.py's dimensions and not this file's: they are connector
# mouldings, and a connector is payload rather than structure. What the robot
# lost with the umbilical is a moving external load that was never modelled and
# a boom that was never designed; docs/NOTES.md carries the decision.

# ---------------------------------------------------------------------------
# The hoist lugs -- a SAFETY tether, September 2026
#
# The power tether above is gone. What the pelvis carries now is a different
# tether entirely, and the only thing the two share is the word: two lugs on the
# flanks so the robot can be hung from an overhead rail while it is being
# developed, and so a topple is caught before it reaches the floor.
#
# WHY IT IS WORTH 9.3 g. docs/NOTES.md puts the centre of mass at 202 mm and a
# sideways topple at 2.85 J arriving at 1.65 m/s, and the table under it is the
# argument: on a hard floor the limb's worst section fails at 0.44x across the
# layers, and the leg can absorb 0.21 J of that 2.85 before it breaks. The robot
# survives falls because the floor gives, not because anything on it is tough.
# A balancing machine falls over as a matter of routine during bring-up, so the
# choice is a catch or a supply of spare limbs.
#
# NOT THE LID, and that is the first decision. The four cover bosses are the
# strongest anchorage on this box -- each is a corner column merged into two
# walls -- but their screws stand 4 mm inboard of the cavity edge, so anything
# reaching them overhangs the mouth. cad/deck.py's electronics deck is 148.3 mm
# wide in a 149.1 mm opening with 0.4 mm of drop clearance and lifts straight
# out or not at all, so a bracket on those bosses seals the battery in. Running
# the robot with the lid off for access is exactly what the lugs are for, so the
# attachment cannot be on the lid or on anything bolted through it.
#
# ON THE FLANK, WHICH IS FREE. Each side wall is plain 2.4 mm shell from the top
# of the hip saddle at 286 mm up to the rim at 357.6 -- the cable ports are in
# the floor and every connector is in the back -- and the whole lug stands
# outside the 153.9 mm the lid covers, so the lid still fits over it.
#
# LONG FORE-AFT RATHER THAN TALL, which is the second decision. The lug is
# loaded upwards and the box hangs below it, so the load leaves the lug, crosses
# into the wall and runs DOWN the wall to the floor the hip clevises are rooted
# in. 30 mm of length feeds it into 30 mm of the wall's width at once; the same
# material stood on end would feed the same load into half of that. The top face
# is flush with the shell's rim for the same reason -- the lug is hanging the
# wall, not hanging off it -- and the underside is tapered back so the wall does
# not meet a square step. None of it is close to a limit: at ten times the
# robot's weight the wall sees under 1 MPa against the 30 this project assumes
# across the layers, so the shape is about where the load goes and not how much
# of it there is.
#
# INSIDE THE WHEELS, which is what stops it becoming the thing that breaks. The
# outboard face lands at +/-88.95 against wheels at +/-104, so in the topple it
# exists to catch the lug never touches the floor first. That is the same test
# cad/limb.py's cable-tie arches were moved inboard to pass.
#
# THE HOLE IS NOT A SLOT. A slot would let the hang point slide to wherever the
# robot balances fore-and-aft, which is what the lid-mounted version of this
# wanted; on two lugs it is not worth the material, because the robot hangs from
# the LINE between them and any fore-aft error in the centre of mass shows up as
# a couple of degrees of hang rather than as a load. O6 takes a small shackle's
# pin or a 4 mm screw-gate.
hoistLugLength = 30.0
hoistLugProud = 12.0
hoistLugHeight = 16.0
# How far the lug reaches INTO the wall, so the two shells merge in the slicer
# the way every other overlap on this robot does. The same 1 mm the limb's tie
# arches use, and it stops inside a 2.4 mm wall rather than breaking into the
# cavity.
hoistLugLap = 1.0
# The 45 degree relief under the outboard corner. 5 mm leaves the bottom face
# 8 mm wide, and its plane passes 6.4 mm from the eye's centre, so 3.4 mm clear
# of the bore.
hoistLugTaper = 5.0
# The eye, and where it sits in the lug: 6 mm out from the flank and 8 mm below
# the rim, which leaves 3 mm of material on each side of it, 5 mm above and
# 5 mm below. tools/gate_e.py counts the two of them.
hoistLugHoleDiameter = 6.0
hoistLugHoleInset = 6.0
hoistLugHoleDrop = 8.0
# AND BOTH MOUTHS OF IT ARE BROKEN, 45 degrees to O8, WHICH IS DRAWN HERE RATHER
# THAN LEFT TO cad/finish.py. That pass breaks OUTER edges only -- an edge is
# taken when every face it touches is flat or the outside of a round, which by
# construction excludes the mouth of a bore -- so the eye came off the printer
# with two sharp rims on it and the finish report counted them among the 77 it
# skips. Every other bore on this robot is a seat or a clearance hole and wants
# them sharp. This one is the only place on the machine where a rope turns over
# a printed edge under load, and the whole point of the lug is that it is the
# thing that does not fail, so the relief is part of the part and gate B holds
# it. 1 mm leaves 2 mm of material outboard of the mouth and 4 mm above it.
hoistLugEyeChamfer = 1.0

# ---------------------------------------------------------------------------
# Stressed-shell limb architecture -- see PLAN.md
#
# The carbon tubes and their bonded sockets are gone. Each limb is now a closed
# printed box that carries the load itself, and the actuator hangs in an open
# clevis at the limb's lower end so it can still radiate.
#
# Section chosen from a stiffness calculation rather than by eye. The old pair
# of 8 x 8 tubes gave 467 mm^4 in the sagittal plane, because both tubes sat on
# the centre line and neither helped the other. A closed 30 x 30 box with a
# 2.4 mm wall gives 33 894 mm^4 -- 73 times as much -- for 29.5 g per 105 mm
# link, and 0.13 mm of tip deflection at three times body weight in a 45 degree
# crouch. That is far inside the joint clearances, so there is no case for
# going heavier.
#
# The depth is not free to grow, which is why the section is square rather than
# the deeper-than-wide shape a leg would otherwise want. The shin has to fold
# against the thigh's saddle, and a deeper shell reaches it sooner: at 34 mm
# first contact comes at 108.5 degrees, inside the 110 degree commissioning
# limit, and at 30 mm it moves out to 112.8 degrees, so the structure backs the
# stop up instead of pre-empting it.
#
# Those angles were originally attributed to the shin's rotor arm, which was
# wrong: the arm was shellInnerDepth and never the first thing to touch. What
# governs is whichever body at the rotor end is the full shellDepth -- the
# bridge then, the rotor plate now -- so the contact angle is unchanged by the
# move into the output plane. A 2D sweep of the rotating sections against the
# saddle puts structural contact at 116 degrees, which agrees with the hard-stop
# note in PLAN.md. Any change to shellDepth, jointKeepOut or rotorEndHeight
# moves it and must be re-checked against the knee_limit_check scene, which
# tools/gate_f.py measures rather than draws.
#
# 2.4 mm is four perimeters of a 0.6 mm nozzle, which is the practical way to
# print carbon-filled nylon. Wall thickness is therefore a manufacturing choice
# as much as a structural one, and must be re-checked if the material changes.
# Densities: PA12-CF about 1.06 g/cm3, which is lighter than the PETG it
# replaces, not heavier.
shellWidth = 30.0
shellDepth = 30.0
shellWall = 2.4

# THE SADDLE'S POWDER DRAIN, September 2026. cad/joint.py builds the saddle as a
# closed box on purpose -- it is the only path the joint load has into the limb
# above -- but a closed box in a sintered part is a sealed cavity full of powder
# that was never fused. Measured on the union of each piece's bodies, not on a
# drawing: 7.66 cm3 inside each thigh and 7.53 cm3 inside each of the pelvis's
# two hip clevises, which at PA12's loose bulk density of about 0.45 g/cm3 is
# roughly 14 g of dead powder across the robot that nothing in this file counts.
# An SLS house will either refuse the part or open the cavity wherever suits its
# own process rather than wherever suits this joint.
#
# 4 mm is the smallest escape hole PA12 vendors quote for a cavity of this size,
# and it is bored straight through so it opens both side walls at once: powder
# can then be blown through rather than worked out of a blind pocket. It fits
# the 7.2 mm cavity with 1.6 mm of wall left above and below it, and it goes in
# the side walls because the load runs from the four rear bolts up the cheek
# necks and out through the saddle's top face -- the sides carry none of it.
saddleDrainDiameter = 4.0

# The joint clevis. The actuator only offers a grip on two faces -- 4 x M3 on
# Ø41 at the rear and 6 x M3 on Ø24 at the front -- so the stationary side has
# to reach around the body to support the moving side, and the moving side is
# necessarily a single plate on the output face. That is forced by the
# actuator, not chosen: nothing can pass through it.
#
# So every joint is the same shape. The limb below a joint carries a rotor hub
# on the output face; the limb above carries a two-cheek clevis, anchored on the
# rear pattern and reaching past the body to a bearing on the far side.
cheekThickness = 3.0
cheekDiameter = 52.0
cheekNeckWidth = 24.0
rearCheekX = -(actuatorDepth / 2 + actuatorClearance + cheekThickness / 2)

rotorHubThickness = 6.0
rotorHubDiameter = 36.0
# The plate's inboard face, and the face that lands on the register: the
# register's own face is one overall length from the rear cover, so this plane
# and it are the same plane. The plate lands on it FLAT, across the whole Ø30
# the register presents, and everything else on this face of the limb -- the
# rest of the disc out to Ø36, the waist, the gussets -- stands one
# actuatorOutputProjection clear of the housing behind it. Nothing is in that
# millimetre.
rotorHubInnerX = actuatorDepth / 2
rotorHubOuterX = rotorHubInnerX + rotorHubThickness

# ---------------------------------------------------------------------------
# THE Ø30.4 REGISTER POCKET -- RETIRED, 14 September 2026
#
# rotorRegisterDiameter and rotorRegisterDepth are gone and so is the feature.
# The plate has no pilot on the actuator at all now; it is located by the six
# M3 on Ø24 and by nothing else.
#
# WHAT IT WAS. A Ø30.4 x 1.2 pocket cut OUTBOARD of the seating face, on the
# reading that the plate landed on the housing and the register stood up into
# it. The housing ends 1.0 mm short of the output face -- see
# actuatorOutputProjection -- so that reading had the plate seating on nothing
# at all, with the six screws that carry the joint's whole output torque
# clamping across the gap.
#
# WHY IT WAS NOT SIMPLY TURNED ROUND. It was, for one revision: cut INBOARD of
# the seating face instead, in a Ø36 x 0.7 rim the plate carried, bored Ø30.4.
# The arithmetic is sound and the part is not. The rim's height and the air
# over the housing are the same millimetre shared out -- they always add to
# actuatorOutputProjection -- so a 0.7 mm rim leaves 0.3 mm of clearance, and
# 0.3 mm is inside what SLS holds on a 0.7 mm feature before the plate's own
# flatness over Ø36 is counted at all. A rim that prints long does not merely
# rub: it lands on the housing and stops the plate seating on the register,
# which is the exact defect it was drawn to cure, on a face that turns.
#
# AND THE PILOT WAS WORTH LESS THAN IT LOOKED. At a straddled joint the plate is
# already located twice -- by the six M3 and by its own journal in the far
# bearing -- and that bearing sits in a printed clevis bolted to the rear cover
# through Ø3.4 clearance holes, so the coaxiality a 0.2 mm pilot would protect
# is not available at the other end of the joint anyway. A third radial
# location on one rigid plate is over-constraint, and in a printed assembly
# over-constraint is something binding. On the wheel adapter there is no far
# bearing, and +/-0.2 mm of runout on an Ø80 wheel is half a per cent.
#
# So the plate is flat, and lands flat. actuatorOutputRegister stays above as
# the vendor dimension it is -- the Ø30 the plate seats on is still the reason
# the disc is Ø36 and the bolt circle Ø24 -- but nothing is derived from it any
# more. tools/gate_a.py carries both retired names.
frontCheekX = rotorHubOuterX + 1.0 + cheekThickness / 2

# ---------------------------------------------------------------------------
# The flat limb
#
# A limb is a plate in one plane, not a beam between two clevises. It works
# because the knee actuator is turned round: with the knee's output facing the
# robot's left, the thigh meets the hip pitch rotor and the knee's rear face on
# the same side, and the shin meets the knee rotor and the ankle's rear face on
# the other. Every attachment is either the six-bolt Ø24 output circle or the
# four-bolt Ø41 rear pattern -- the two the vendor 2D print and the STEP both
# confirm. The unused Ø41 front-housing pattern is not needed for any of it.
#
# What it deletes: the two-cheek clevis, the saddle, the closed shell, the
# arm-and-bridge, and the far bearing at the knee and the ankle.
#
# What it assumes: that the actuator's own output bearing carries the joint
# moment, because nothing reaches around the motor any more. The plate sits
# about 22 mm off the joint axis, so the overhung moment is 0.45 Nm standing on
# one foot and about 1.35 Nm landing at three times body weight. DAMIAO have
# not confirmed the bearing will take it. That question is open and the design
# is proceeding on the assumption it is answered favourably -- see NOTES.md.
limbPlateThickness = rotorHubThickness
statorPlateDiameter = cheekDiameter
# The plate lands flat on the rear cover; there is no clearance to give, this
# is a mating face. Screws cross 3.2 mm of cover into 4 mm of thread, so a
# 6 mm plate wants M3 x 14 where the old 3 mm cheek wanted M3 x 12.
statorPlateInnerX = -(actuatorDepth / 2)
statorPlateOuterX = statorPlateInnerX - limbPlateThickness
statorPlateCenterX = statorPlateInnerX - (limbPlateThickness / 2)
# statorPlateFlatOffset -- the connector relief -- is below, with the waist
# width it is now cut flush with.

# HOW FAR THE KNEE JOINT STANDS OUTBOARD OF EVERY OTHER, September 2026.
#
# A flat limb lands a 6 mm plate on its lower actuator's rear cover, and that
# plate's outer face is the leg's exterior surface. The straddled knee lands a
# 3 mm cheek there instead, held the actuator's own 0.3 mm off the cover, so the
# fork's outer face sat 2.7 mm inside the thigh plate's exterior face: a step in
# the side of the leg at the one joint that has a fork. Those three dimensions
# ARE the offset.
#
# THE JOINT MOVES, NOT THE FORK. Sliding the fork on its own motor is not
# available -- the cheek bolts to the rear cover through that 0.3 mm, and the far
# cheek has exactly 1.0 mm of air against the shin's rotor disc -- and reshaping
# the fork's saddle to reach the plate is worse: it is cad/joint.py's part, the
# one gate B holds against its golden STEP and the pelvis carries at both hips,
# and OCCT's chamfer will not finish a clevis whose saddle has been moved off
# the cheek faces. So the knee actuator, the fork, the shin, the wheel motor and
# the wheel all stand this much further out, and every printed part keeps the
# shape it had.
#
# WHAT IT COSTS IS TRACK: each wheel moves 2.7 mm outboard, so the robot is
# 5.4 mm wider across the wheels. Nothing moves in the sagittal plane, so every
# pose, joint angle and fold clearance the check scenes measure is untouched.
kneeOutboardOffset = limbPlateThickness - cheekThickness - actuatorClearance


# The waist between the two discs. It carried two stiffening flanges on its
# outboard face until 30 August 2026; the retirement note below says why they
# came off and what they were actually worth.
# The waist was shellDepth, 30 mm, inherited from the closed box the flat limb
# replaced. It is now 40 -- widened on 30 August 2026 to buy back some of the
# lateral strength the flanges never delivered.
#
# Width is the only lever left at the rotor end. Thickness would be worth more,
# going as the square, but the plate cannot grow outboard there: the hip
# carrier's cheek and its bearing carrier occupy everything within 26 mm of the
# hip pitch axis, one millimetre off the plate's face, and the peak stress sits
# 12 to 18 mm below that axis. Width runs fore-and-aft instead, where the cheek
# is not, so it is free of that obstacle.
#
# 40 mm takes the worst section from 1.27 to 0.99 MPa per newton at the foot --
# the limb breaks at 30.4 N sideways rather than 23.4, printed across the
# layers -- for 4.6 g a limb. It stops there because the return falls off: 44 mm
# would buy 1.89x against 40's 1.73x, and the limb is already a third deeper
# than it was.
limbWaistDepth = 40.0
# The connector relief on the stator plate, and it is cut FLUSH WITH THE WAIST
# rather than on the housing's own connector flat.
#
# The connectors seat against a chord 19 mm from the axis and the plate is
# truncated on a chord rather than covering them, which is why the relief
# exists at all. It was at exactly 19 -- actuatorConnectorFlatOffset -- from the
# day it was drawn, and that was right while the waist was 30 mm and its flank
# sat 4 mm inside the chord. Widening the waist to 40 on 30 August 2026 pushed
# that flank to 20 and put it a millimetre PROUD of the relief, so the limb's
# edge stood over the cut the relief had just made. That is the 1 mm step in the
# silhouette above the lower joint, and it was nobody's decision.
#
# The two are now one number, which is the only way they stay matched. The
# millimetre is given to the plate rather than taken off the limb because it
# costs nothing on this side and 10 % of the limb's lateral section on the
# other: the plate lies entirely OUTBOARD of the rear cover, at x -18.95 to
# -24.95, while the connectors and their plugs are inboard of x -18.95 on the
# housing itself. So the extra material is a 1 mm lip standing BESIDE a
# radially-mating plug, not over it, on a disc that already overhangs the Ø46
# housing by 3 mm everywhere else. Losing 2 mm of waist instead would have taken
# the limb's sideways breaking load from 30.4 N to 27.4, at the rotor end where
# it actually breaks.
#
# THE LIMIT ON THIS. The relief may follow the waist while the lip stays small
# enough to be beside the connectors rather than over them; a millimetre is, and
# the plug projection it is judged against is an ESTIMATE (see
# actuatorConnectorPlugProjection). A waist much past 42 mm needs the plug
# measured on a real actuator first, and until then this goes back to
# actuatorConnectorFlatOffset rather than growing with it.
statorPlateFlatOffset = limbWaistDepth / 2
# How far the waist reaches past the limb centre towards the rotor end. It is
# not symmetric: the far end is derived in cad/limb.py from the rear bolt circle,
# because a waist this long would sit on the bolts. This end is set by the two
# features that squeeze it -- it must reach the Ø36 disc, whose lower edge is
# 18 mm below the joint centre, without touching the nearest output counterbore,
# whose edge is 13.4 mm below it. 38.5 mm buys 4 mm of engagement and leaves
# 0.6 mm of counterbore clearance, which is the whole of the available window.
limbWaistUpperZ = 38.5
# ---------------------------------------------------------------------------
# The limb flanges, retired 30 August 2026
#
# limbFlangeReach, limbFlangeThickness, limbFlangeBlendRadius and
# limbFlangeRotorClearance are gone. The waist is a plain plate again. What they
# were and what they were worth is kept here because the reasoning is the useful
# part, and because the obvious instinct -- put a rib on it -- is wrong here for
# a reason that is not obvious.
#
# They were two ribs standing proud of the plate's outboard face, 4 mm thick,
# reaching 12 mm at first, then 8.4, then 4.2. They were never introduced to
# cure a measured weakness.
#
# A rib on a plate adds material away from the centroid, which raises the second
# moment; but it also moves the outermost fibre out by nearly as much, and
# section modulus is the second moment divided by that distance. So the two
# effects very nearly cancel for strength while compounding for stiffness. At
# 4.2 mm reach the flanges were worth 2.5x on the section's lateral second
# moment (540 mm^4 to 1 326) and 15 per cent on its section modulus (180 mm^3 to
# 207). At 8.4 mm they were worth 6.4x and 2.0x respectively.
#
# And whatever they were worth, they were not present where it counts. The
# weakest printed thing on the robot is the short run of bare plate just under
# the thigh's hip-pitch hub, and the flange had to stop a cheek radius short of
# that joint because the hip carrier's front cheek stands 1 mm outboard of the
# plate there. So the limb's breaking load was identical with them and without:
# 23.7 N applied sideways at the foot across the layers, 59.2 N in the print
# plane.
#
# What the robot can actually do to itself: a lateral push tips it at about 2 N
# and puts 4 MPa in that section, seven times inside the across-layer figure. A
# sideways topple from one-leg stance releases 2.85 J and is marginal -- it
# breaks a limb on a hard floor printed across the layers, and survives printed
# in plane. The actuators are what do it; they are 1 200 g of the 2 089 g total
# and they sit at the ends of the links.
#
# So the levers that matter, in order, are print orientation (2.5x, free) and
# plate thickness (6 mm to 8 is 1.78x, and unlike a flange it lifts the bare run
# under the hub as well). Neither is a rib. Full working in NOTES.md.
#
# All of it is arithmetic against 75 MPa in plane and 30 MPa across layers for
# PA12-CF, which this project has still never measured on a coupon.

# ---------------------------------------------------------------------------
# Where the harness is tied down, September 2026
#
# Each limb carries two arches on its INBOARD face, one at each end of the
# waist: a block standing 4 mm off the plate with a 3.5 x 2.0 tunnel under it,
# so a cable tie passes through and closes round the bundle lying beside it.
# Nothing else on this robot anchors a lead outside the pelvis; docs/BOM.md's
# adhesive tie mounts were bought for the torso floor and are not what should
# hold a loom on a limb that swings.
#
# NOT A SLOT THROUGH THE PLATE, and this is the first of the two decisions. The
# waist is 40 x 6 and takes its load ACROSS the plate, where the whole section
# is 240 mm3. A tie needs two slots to straddle a bundle; a 2 mm pair costs a
# tenth of that and brings a notch of 1.5 to 2 with it, which lands the stress
# at the slot above the 0.99 MPa per newton that the limb's worst section
# carries today. The tie point would become the weakest thing on the robot --
# roughly 30 N sideways at the wheel down to 15 or 20. Anything standing ON the
# plate adds material instead, carries no load, and costs the section nothing.
#
# ON THE INBOARD FACE RATHER THAN OFF THE AFT FLANK, and this is the second.
# These were ears in the plate's own plane for a few hours, reaching 12 mm aft
# of the flank, which is the cheapest thing to print and the most exposed thing
# on the limb: the ear and the bundle on it were the aft-most material at their
# own station by 12 mm, inside the robot's silhouette only by the 4 mm the
# wheels and the torso's back stand proud of them. A fall onto a flat floor
# would not reach them; an edge, a doorway or a bench leg would. On this face
# the whole run is inside the box the two limb plates and the actuators make,
# which is also the side every connector on the leg is on.
#
# WHAT IT COSTS IS A PRINT ORIENTATION. The arch is 4 mm proud of one face, so
# that face has to be uppermost on the bed or it needs support. That is the
# face the Ø30.4 register pocket is in -- in a rim 0.7 mm proud of it, which
# wants the same way up for the same reason -- so it wants to be uppermost
# anyway rather than bridged, and which way up a flat plate lies costs nothing
# structurally -- the layers run along the limb either way.
#
# AND THE HARNESS NOW RUNS ON THE FACE, inside the flank line, which the
# actuators make room for only in the middle: a Ø46 body sits against this face
# at each end of the limb. At the bundle's station -- 17 mm off the centre line,
# on the aft side, beside the arches -- it is clear of both bodies from z -35 to
# +35 and swings out past the flank over the last 17 mm at each end, which is
# where its connector is anyway. The arches are the rigid part and they are held
# further off: the nearest corner of one stands 26.4 mm from its joint axis
# against the Ø46 body's 23.
limbTieArchHeight = 4.0
limbTieArchLength = 10.0
limbTieArchWidth = 6.0
limbTieArchTunnel = 2.0
# How far the arch's root runs INTO the plate, so the two shells merge in the
# slicer the way every other overlap on this piece does.
limbTieArchLap = 1.0
# Where the two arches sit. 10 mm aft of the limb's centre line keeps the
# bundle beside them inside the flank and off the rear bolt heads; and each
# arch is placed from ITS OWN JOINT AXIS rather than from the limb's centre,
# because what it has to miss is the actuator at that joint and not the middle
# of the leg. 30.5 mm clears the Ø46 body by 3.4 mm at the arch's nearest
# corner, clears the Ø52 plate's rim, and stays out of the 12 to 18 mm band
# under the rotor hub where the peak stress is.
limbTieArchY = -10.0
limbTieArchZ = 30.5
# AND WHERE THE CLEVIS END'S ARCH SITS INSTEAD, September 2026, once the knee
# was straddled. 30.5 mm is a station chosen against a Ø52 plate and nothing
# else; the clevis puts a closed saddle box there, reaching from jointKeepOut
# out to 36 mm from the joint axis, and an arch at 30.5 is inside its cavity --
# buried, with no way to pass a tie through the tunnel at all. 42 mm stands the
# whole 10 mm block clear of the saddle's top face, with the tunnel's lower edge
# 4.25 mm above it, and it is still a plate the arch lands on: the waist runs
# the full length of the limb. Only the limb's clevis end uses this; the plate
# end is unchanged, which is why the shins are the print they always were.
limbTieArchZClevis = 42.0
# The strap's own width, which is what the tunnel is cut to: a 2.5 mm tie.
limbTieSlotWidth = 3.5

# Far support. The bearing is bonded straight into the printed front cheek.
#
# It used to sit in a turned aluminium carrier -- a Ø30 x 3 mm flanged ring in a
# Ø30.2 cheek bore -- and that carrier was the only part of this robot with no
# source. docs/BOM.md had it as a bespoke turned part from a local machine shop,
# against a table on which everything else is a catalogue item or a print, and
# docs/OPUS_HANDOFF.md asks for exactly that to be avoided unless there is a
# clear reason. Boring the cheek to the bearing itself deletes the part.
#
# What the carrier was for does not go away with it. NOTES.md records printed
# pockets ovalising, and this seat sets the coaxiality of the whole joint, so the
# case for a printed seat rests on its being BONDED rather than pressed: the
# retaining compound takes up the gap, which removes the interference fit that
# makes a printed pocket creep. That is an argument and not a measurement, and
# docs/BOM.md's fit coupon is where it has to be settled. What the flange did,
# and what nothing does now, is recorded where the seat is cut in cad/joint.py.
# THE JOURNAL IS A BOUGHT SLEEVE, FITTED LAST, September 2026, AND THE REASON IS
# THAT NOTHING ELSE CAN BE ASSEMBLED.
#
# It was a Ø10 hardened dowel bonded into a blind seat in the disc until 13
# September, then a Ø10 stub grown out of the disc and printed with it. Both are
# ONE PIECE WITH THE MOVING SIDE BEFORE THE JOINT IS CLOSED, and that is what
# neither of them survives: the clevis is a single print whose two cheeks stand
# 45.2 mm apart, and an actuator with its limb's disc bolted on measures 49.9 mm
# from its rear face to the journal's tip, so the journal can never be brought
# into the bearing. It is 4.7 mm of interference and there is no path in -- the
# six output screws are behind the far cheek once the motor is in, so the disc
# has to be on the motor before the motor goes into the fork, and the unit then
# has 1.3 mm of axial slack against a journal that needs 5 mm of travel to reach
# the bearing bore. Springing the cheeks apart is not a fix: 4.7 mm strains a
# 3 mm cheek about 2 to 4 per cent at its root, which is at or past what PA12
# takes elastically, on the part that holds the bearing in line with the output.
#
# So the journal is the last thing fitted. It goes in from OUTSIDE, through the
# Ø17.5 shoulder bore in the bearing boss, through the bearing, and lands on the
# disc's outer face, where an M5 button head pulls it down onto a nut captive in
# the disc. Everything printed keeps its shape: the clevis is untouched and so is
# the pelvis that carries two of them.
#
# WHAT IT COSTS IS THE ANCHOR, and this is the honest part. A stub grown out of
# the disc spreads its bending into the whole Ø36 plate; a sleeve landing on the
# face of that plate is held by 4.8 mm of PA12 at the disc's centre, and nothing
# wider can be used because anything that clamps it has to pass the bearing's
# Ø10 bore or fit the 1 mm gap behind it. At the 500-650 N this project records
# at the 6800 for the handoff's 100 N at 100 mm case, the clamp lets go and the
# plastic under the sleeve's rim starts to crush somewhere around 300-400 N --
# an estimate, from the clamped-annulus and embedded-pin arithmetic, not a test.
# By NOTES.md's own figures that is about where the limb plate itself breaks, so
# it is not the first thing to go; it is still less than the stub had.
#
# WHAT WOULD GIVE IT BACK is metal behind the disc: a steel hub between the disc
# and the motor's output register, held by the same six screws, carrying the
# thread.
#
# THAT DISAGREEMENT IS SETTLED, AGAINST THE HUB. This note used to say the
# vendor STEP put the flange 1 mm proud inside the 37.9 mm length while this
# file assumed the register filled a 1.2 mm pocket, that the two disagreed, and
# that a caliper would have to decide. The STEP was right and this file was
# wrong: the Ø46 body is 36.90 long and the Ø30 register fills the last 1.00,
# both figures on the vendor 2D print. So the plate seats ON the register --
# see actuatorOutputProjection above -- and there is no gap behind it for a
# steel hub to live in. A hub would have to be a spacer the six screws pass
# through, lengthening the joint and moving everything outboard of it, which is
# a different change from this one and a dearer one.
journalDiameter = 10.0
# THE BLIND SEAT SURVIVES, and only on the wheel adapter. cad/joint.py's
# outputDisc is the limb's disc AND the adapter's, and the adapter carries no
# journal at all -- it never did. Leaving its seat where it was is what keeps
# that piece identical to the STEP the engine built, and it costs a gram of
# nothing. The forked rotor below still measures from it too.
journalSeatDiameter = 10.2
journalSeatDepth = 2.2
# How far the journal stands proud of the disc's outer face: across the 1 mm of
# air to the bearing, then the bearing's whole 5 mm width, ending flush with its
# outer face. The stub that preceded the sleeve stood exactly this far proud and
# the dowel before it was 8 long, seated 2.2 mm into the disc, so the sleeve runs
# in the same race in the same place as both.
journalLength = 6.0
# The sleeve's bore, and the disc's clearance hole under it. The screw is an M5
# and this is its close clearance: the sleeve is what the bearing runs on, so the
# screw must not decide where it sits.
journalSleeveBore = 5.3
journalScrewClearance = 5.5
journalScrewDiameter = 5.0
# Revised 2026-09-15: the retired register pocket left a 2.7 mm web, not
# 1.5 mm, so M5 x 10 reached only 1.3 mm into the nut. M5 x 12 with a
# DIN 433 / ISO 7092 M5 washer (5.3 x 9 x 1) reaches 2.3 mm and stops
# 1 mm short of the motor. A normal 10 mm OD washer can touch the bearing;
# the small-series washer stays inside its bore. Manufacturer drawing:
# https://belmetric.com/content/A-PDF_Drawings/WF5X9SS.pdf
# Allow +/-0.2 mm each on the printed sleeve and web, +/-0.3 on screw length,
# and +/-0.1 on the washer: at least 1.5 mm engagement and 0.2 mm tip air.
# This is a prototype clamp, not a full-strength M5 bolted connection.
journalScrewLength = 12.0
journalWasherBore = 5.3
journalWasherDiameter = 9.0
journalWasherThickness = 1.0
# An ISO 7380 button head rather than a cap head, and the head diameter is why:
# Ø9.5 lands wholly on the Ø10 sleeve and touches neither the bearing's inner
# race nor its seal, and 2.75 mm of head stands 1.25 mm proud of the bearing
# boss, where a cap head would stand 3.5.
journalScrewHeadDiameter = 9.5
journalScrewHeadHeight = 2.75
# The nut is an ISO 4035 thin hex, captive in a pocket in the disc's motor-side
# face. It had to be a thin one when the register pocket took 1.2 mm of the
# disc's 6: the 4.8 that was left had to hold the nut AND leave a web for the
# sleeve to clamp against, which was 2.7 of nut and 1.5 of web. The pocket is a
# rim outboard of nothing now -- it is cut inboard of the seating face -- so the
# full 6 mm is available and the split is 2.7 of nut, 0.6 of empty pocket and
# 2.7 of web. The thin nut stays: the web is what the sleeve clamps against and
# 2.7 mm of it is worth more than a standard nut's extra thread.
#
# THE POCKET IS CUT 1.3 mm OVER THE FLATS, AND THE FINISHING PASS IS WHY.
# 8.3 was the number this was drawn with -- 0.3 over the nut, meant to be pushed
# in, since SLS holds about +/-0.2 mm and a nominal fit is a nut that will not go
# in as often as it is one that rattles. Then the pocket was measured on the
# FINISHED piece: cad/finish.py breaks every edge whose faces are flat, the floor
# of a hex pocket is one of those, and a 0.5 mm chamfer round its perimeter took
# the seat from 35.9 mm2 to 22.3 against a nut face of 31.6. The nut would have
# landed on the chamfer rather than on the floor, on the one joint in this
# assembly whose preload is already the weak thing about it.
#
# 9.3 leaves 8.3 mm of flat floor across the flats once the chamfer has been cut,
# which is the fit the pocket was meant to have in the first place. What it costs
# is 0.65 mm of lateral slop on a nut that the screw centres anyway and that only
# has to be stopped from turning.
journalNutAcrossFlats = 8.0
journalNutThickness = 2.7
journalNutPocketFlats = 9.3
journalNutPocketDepth = 3.3
bearingBore = 10.0
bearingOuterDiameter = 19.0
bearingWidth = 5.0
# The cheek's bore for it: the bearing's own Ø19 outside diameter plus 0.2 mm for
# the retaining compound. That is the allowance the Ø10 journal's Ø10.2 seat in
# the rotor hub has always carried for the same bond, and the same 0.2 mm the
# deleted carrier had in its Ø30.2 bore. A CLEARANCE, deliberately: an
# interference fit is what makes a printed pocket creep, and a bore this process
# holds to about ±0.2 mm cannot be given a controlled press fit anyway.
bearingSeatDiameter = 19.2

# The shoulder the bearing seats against, and the boss that carries it.
#
# The cheek is 3 mm and the bearing is 5 mm wide, so the seat can be neither deep
# enough nor shouldered within the cheek alone. The boss stands off the cheek's
# outer face, makes up the missing 2 mm of seat and carries 1.5 mm of shoulder
# beyond it. The bearing is then supported across its whole width and cannot be
# pushed outboard, which is the direction the journal loads it on assembly, so
# the bond is left holding it against nothing worse than falling back inboard.
#
# The shoulder lands on the OUTER RACE ONLY. Ø17.5 leaves 0.85 mm of land on a
# race that runs out to Ø19, and clears both the seal and the inner race, which
# turn with the journal and must touch nothing. The same bore is the way a pin
# reaches the bearing to push it out, since a bonded seat has no other exit.
#
# Ø26 keeps 3.4 mm of wall around the seat, about the cheek's own thickness. The
# boss stands proud of the widest part of the pelvis, at ±77 mm, and the wheels
# are at ±104, so it costs nothing in the robot's envelope.
bearingSeatShoulderBore = 17.5
bearingSeatShoulderThickness = 1.5
bearingSeatBossDiameter = 26.0
bearingSeatBossThickness = bearingWidth - cheekThickness + bearingSeatShoulderThickness

# The rear cheek's lightening bore -- REMOVED, and the history kept because it
# is the second time the same hole has had to go.
#
# It began as a Ø26 lightening hole in the cheek, and was opened to carrier size
# (Ø30.2) when the joints were forked, so that one bore served both the front
# cheek's bearing carrier and the rear cheek's weight saving. The flat limb
# plate inherited it and lost it first: on a 6 mm plate the hole left a weaker
# section than the waist it was feeding, 266 mm^4 against the bare waist's 540.
# The cheek kept it on the argument that a 3 mm cheek only saves 0.6 g by
# opening Ø26 out to Ø30.2, so the larger bore was free.
#
# What that argument missed is that the hole itself was never free. The cheek is
# the only path from the four rear bolts up through the neck into the saddle,
# and it is the part that holds the far bearing in line with the output, so it
# is the last place on the joint to remove material from the middle. The whole
# bore is 2.3 g a clevis and there are four clevises, which is 9 g of the
# 2 300 g budget for the section back.
#
# Ø30.2 survives as bearingCarrierBore above, which is what it was measured for:
# the front cheek's bonded-in carrier. If the straddled joint is ever
# reinstated, the rear cheek would take a real carrier at that diameter rather
# than an empty hole.

# ---------------------------------------------------------------------------
# The forked rotor -- DRAWN BUT NOT FITTED
#
# Nothing imports rotorYoke or rearJointHardware any more. The straddled joint
# is kept because the case for dropping it rests on one unanswered question --
# what moment the DM-J3507's own output bearing will take -- and if the answer
# from DAMIAO is unfavourable this is what comes back. The parameters below
# are what it needs.
#
# One rotor arm outboard of the output face leaves the moving assembly a
# cantilever: its two supports, the actuator's own internal output bearing and
# the 6800, both sit on the same side of the limb's load line and about 20 mm
# apart. A sideways load at the foot is then reacted as a couple across that
# short span, which is where the 500-650 N at the 6800 comes from.
#
# A second arm on the far side of the motor makes it a straddle about 53 mm
# wide with the load line nearly centred, and the couple reaction falls to
# roughly 240 N -- from 65 per cent of the 6800's static rating to 26.
#
# The layout is forced and cannot be a mirror of the front. The stator's rear
# cheek is bolted flat against the motor's rear face, so the rotor's rear arm
# has to sit outboard of that cheek and reach back in on a journal. The second
# bearing therefore lives in the rear cheek itself, which is why every clevis
# now carries a carrier-sized bore there instead of a plain lightening hole.
rearBearingX = rearCheekX - 1.5
# Half a millimetre of air between the arm and the bearing it drives. The front
# hub has none, which NOTES.md records as a defect rather than a pattern.
rearArmInnerX = rearBearingX - (bearingWidth / 2) - 0.5
rearArmOuterX = rearArmInnerX - rotorHubThickness
rearJournalCenterX = rearArmInnerX - journalSeatDepth + journalLength / 2
# Enough material above the axis to close around the journal seat.
rearArmTopZ = 10.0
# The tie between the two arms passes the Ø52 cheek at every joint angle, so it
# has to run outside the cheek's radius rather than at the bridge's own height.
rearTieTopZ = -(cheekDiameter / 2 + 1.0)
# Two millimetres of overlap into the bridge, so the union has solid to work on.
rearTieInboardX = -(shellWidth / 2) + 2.0

# A sharp re-entrant corner where an arm meets its tie multiplies the bending
# stress there by roughly 2.5, so the corner is radiused. The radius is set by
# the actuator, not by the stress: the corner it fills is the one between the
# arm's inner face, which lies in the actuator's own end plane, and the top of
# the bridge, which sits at jointKeepOut. A fillet there can only grow into the
# gap between those two, and that gap is the one millimetre by which
# jointKeepOut clears the O46 body -- so anything larger is inside the motor.
#
# It was 4 mm until August 2026, chosen to close the 3.95 mm of bridge that
# cantilevers unsupported between the hip carrier's connector wall and the arm
# root. That was the wrong constraint to size it against: the fillet climbed
# 4 mm above the bridge instead of 1, and cut about half a millimetre into the
# bottom rim of the housing over roughly 13 mm of its width, on the hip roll and
# ankle joints. Spotted by eye in Design Studio. The unsupported span is now
# left open -- there is nowhere to put material that is not inside the actuator.
rotorFilletRadius = 1.0

# Two Ø46 actuators 105 mm apart leave only 59 mm of clear span between them,
# so the shell runs joint radius plus 1 mm short of each joint centre and the
# clevis and rotor arm bridge the rest.
jointKeepOut = actuatorDiameter / 2 + jointBodyClearance

m3Clearance = 3.4
m3CapCounterbore = 6.0
m3CapCounterboreDepth = 3.2

# M2 clearance, used in exactly one place: the four screws that clamp the two
# XT60 panel mounts to the rear wall. THE SIZE IS FORCED BY THE DISCONNECT'S
# NUTS, not by the wall. The XT60E-M's ear holes are 2.25 mm from the side of its
# own body, and that is where a nut behind the ear has to sit: an M2.5 nut is
# 2.5 across half its flats and fouls the body by a quarter of a millimetre, an
# M2.5 cap head is 2.25 and touches it, and an M2 nut at 2.0 clears it by 0.25 --
# which also means the body stops the nut turning, so it is tightened from the
# screw head outside. It was M2.5 for one revision, chosen for the wall alone,
# before anybody asked where the nut went. The wall does better at M2 as well:
# 1.45 mm between each screw and the cutout at the disconnect and 1.7 at the
# charge socket, against 0.95 and 1.2 at M3. Same 0.4 mm over nominal as
# m3Clearance above, for the same reason: a printed hole comes out undersize.
m2Clearance = 2.4
# The nuts on those four screws, drawn because they sit inside the cavity beside
# other hardware: an ISO 4032 M2 is 4.0 across flats and 1.6 thick. Drawn across
# its flats and not its corners, because at the disconnect the connector's own
# body holds a flat square to it -- drawn across corners it would read as a
# 0.06 mm clash with the part that is the reason it cannot turn.
m2NutAcrossFlats = 4.0
m2NutThickness = 1.6

# HEAT-SET INSERTS, for the board mounts and the electronics deck -- AND THERE ARE
# NONE LEFT IN THIS FILE. The only one on the robot is the wheel clamp's M5, in
# cad/wheeled_parameters.py, which is a different job: it is what a printed
# spigot is threaded with.
#
# The M3 pair went first. Every board is held by a self-tapping M3 into a Ø2.5
# pilot instead -- the same fastener the cover bosses have always used -- because
# none of the walls a board mount lands on is thick enough to sink a 5.7 mm
# insert: the deck plate is 3 mm and its wall ledges are 5.
#
# The M2.5 pair went in September 2026, and this is the only place its figures
# survive: m25InsertBore 3.2 and m25InsertDepth 5.0, a Ø3.2 x 4.0 brass insert in
# a bore a millimetre deeper than the part. They were in the tops of the deck's
# four 14 mm SBC posts, which were the only printed feature on this robot tall
# enough to take one. The SBC stands on bought standoffs on the controller
# carrier now, the posts are gone, and so is the only reason to melt brass into
# PA12 anywhere.
#
# THE M2.5 SOCKET HEAD that replaced them, which is drawn because it hangs under
# the controller carrier in the 3 mm between that board and the deck. ISO 4762
# M2.5: a Ø4.5 head, 2.5 tall. Catalogue, and the same table at every maker.
m25CapHeadDiameter = 4.5
m25CapHeadHeight = 2.5
# What a printed feature has to leave round a bolt centre for the cap head to
# seat and a driver to reach it: the Ø6 head's own radius plus a 0.4 mm wall.
m3CapHeadStandoff = m3CapCounterbore / 2 + 0.4

printedOrange = "#d9822b"
printedDark = "#27313a"
carbonBlack = "#15191c"
motorGrey = "#59636c"
motorFlange = "#aeb7bf"
bearingSteel = "#c9d0d5"
soleBlack = "#25282b"
sensorBlue = "#2aa8d8"
