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
# carries an XT90-S disconnect, a 6S balance port and a charge port instead,
# which are
# cad/electronics.py's dimensions and not this file's: they are connector
# mouldings, and a connector is payload rather than structure. What the robot
# lost with the umbilical is a moving external load that was never modelled and
# a boom that was never designed; docs/NOTES.md carries the decision.

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
rotorHubInnerX = actuatorDepth / 2
rotorHubOuterX = rotorHubInnerX + rotorHubThickness
rotorRegisterDiameter = actuatorOutputRegister + 0.4
rotorRegisterDepth = 1.2
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
journalDiameter = 10.0
journalSeatDiameter = 10.2
journalSeatDepth = 2.2
journalLength = 8.0
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

# HEAT-SET INSERTS, for the board mounts and the electronics deck.
#
# PROVENANCE: catalogue dimensions for the brass knurled inserts docs/BOM.md
# already stocks for "covers/light-duty interfaces", which is what every mount
# that uses these is. The M3 is the common Ø4.0 x 5.7 short-body part and the
# M2.5 the Ø3.2 x 4.0 -- both are the same table at every maker, which is why
# neither is in reference/. The BORE is the insert's outside diameter, not its
# thread: the brass melts its own knurl into the wall.
#
# The depths are the bore, not the insert: an insert wants a little room under
# it for displaced material, so each is a millimetre or so deeper than the part
# it takes. The same allowance the wheel spigot's M5 bore already carries.
# The M3 pair that used to be here is gone. Every board on this robot is held by
# a self-tapping M3 into a Ø2.5 pilot instead -- the same fastener the cover
# bosses have always used -- because none of the walls a board mount lands on is
# thick enough to sink a 5.7 mm insert: the deck plate is 3 mm and its wall
# ledges are 5. The M2.5 pair below survives because the deck's SBC posts are
# 14 mm tall and have the depth for one.
m25InsertBore = 3.2
m25InsertDepth = 5.0
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
