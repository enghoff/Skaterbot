# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1"]
# ///
"""Gate A -- every ported dimension, against what the KCL said, to full precision.

This is the cheapest and widest of the migration gates
(docs/BUILD123D_MIGRATION.md section 4). It compares the build123d parameter
modules under cad/ against reference/golden/parameters.json, which was frozen off
the KCL before the migration started, name for name and as exact floats.

    uv run tools/gate_a.py            # summary, non-zero exit if anything differs
    uv run tools/gate_a.py --verbose  # list every name, including the matches

It reports four things, and only two of them are failures:

  MISMATCH   a name both sides define, with different values. Always a failure.
  EXTRA      a name cad/ defines that the KCL did not. Always a failure: the
             migration is a translation, so a new dimension is either a typo in
             the name or a dimension invented along the way.
  ADDED      a dimension introduced after the port, which the reference cannot
             hold. Allowed only by being named in ADDED below, with its reason.
  CHANGED    a ported dimension whose value has deliberately moved since. Allowed
             only by being named in CHANGED below, which pins BOTH ends of the
             change, so a third value is still a MISMATCH.
  RETIRED    a golden name this branch deliberately dropped, because it
             belonged to the walking robot. Reported as a count, and a failure
             only if one reappears in cad/.
  UNPORTED   a golden name no cad/ module defines yet. Expected while phase 1 is
             in progress, and reported rather than failed. It becomes a failure
             once the last module lands, which is what --strict is for.
  ok         matched exactly.

Free, offline, and no engine. Nothing here executes geometry -- but it does
import the cad/ modules to read their constants, and those import build123d,
which is why it is declared above.
"""

from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "reference" / "golden" / "parameters.json"

# The golden capture holds three exported names that are geometry rather than
# dimensions -- lists of solids that wheeled_electronics.kcl builds. They have no
# parameter to compare against and never will.
NOT_DIMENSIONS = {"torsoElectronics", "torsoReservations", "torsoPayload"}

# Names the KCL defines but the golden capture cannot evaluate, so they are absent
# from the reference through no fault of the port. simulation/kcl_params.py is a
# line evaluator and not an interpreter: it refuses a call into a KCL function
# rather than guessing at it, which is the right behaviour and is why these two
# come out blank.
#
# They are not waved through. Each is checked by hand here, against the same
# arithmetic the KCL function does -- coverBossInset(span) = span / 2 - bossSize / 2:
#
#   bossX = coverBossInset(torsoInnerWidth) = 149.1 / 2 - 8 / 2 = 70.55
#   bossY = coverBossInset(torsoInnerDepth) =  67.2 / 2 - 8 / 2 = 29.6
#
# and cad/torso.py computes 70.55 and 29.6. If either moves, this note is wrong
# and has to be redone rather than extended -- which has now happened twice in
# September 2026: once when the battery went back in and the shell grew from
# 125 x 68 to 141 x 72, and again when the flank was taken out to the hip
# clevis's own end plane and the width went to 153.9. The spans above are the
# cavity's, so both bosses move with it. The arithmetic is the same arithmetic;
# only the two spans changed.
UNEVALUATABLE = {
    "bossX": 149.1 / 2 - 8 / 2,
    "bossY": 67.2 / 2 - 8 / 2,
}

# Names the golden reference holds that this branch has DELIBERATELY retired,
# because the walking robot they belonged to was deleted from it. They are not
# "not ported yet" and reporting them that way would make the unported list grow
# a permanent tail of things nobody intends to port. The gate asserts the
# opposite of what it asserts everywhere else: a retired name reappearing in
# cad/ is the failure, because it would mean the walking robot crept back in.
#
# The numbers themselves survive in reference/golden/parameters.json and on the
# `main` branch. cad/parameters.py carries the reasoning.
RETIRED = {
    # the foot
    "footLength",
    "footWidth",
    "footCenterY",
    "soleThickness",
    "footTrayHeight",
    # the axis chain the foot decided, replaced by the wheel's radius
    "ankleAxisHeight",
    "kneeAxisHeight",
    "hipPitchAxisHeight",
    "hipRollAxisHeight",
    "hipAxisOffset",
    # the walking torso, replaced by one derived from what fits inside it
    "torsoBottom",
    "torsoTop",
    "torsoHeight",
    "torsoCenterHeight",
    "torsoWidth",
    "torsoDepth",
    # the hip carrier, which hung hip pitch off a hip roll actuator. Only its
    # own connector-shroud dimensions: journalCenterX looks like it belongs here
    # and does not -- it is lib/hardware.kcl's journal, which this robot still
    # uses at hip pitch.
    "connectorHeight",
    "connectorInnerDepth",
    "connectorInnerWidth",
    # The bearing carrier: a turned aluminium flanged ring that gave the bearing
    # a metal seat in the front cheek. Deleted because it was the only bespoke
    # machined part on the robot and docs/BOM.md had no supplier for it; the
    # cheek is bored to the bearing itself instead, at bearingSeatDiameter
    # below. carrierThickness was the ring's own thickness and goes with it.
    "bearingCarrierDiameter",
    "bearingCarrierBore",
    "bearingCarrierFlangeDiameter",
    "bearingCarrierFlangeThickness",
    "carrierThickness",
    # The tether. The robot carried no battery from August to September 2026 and
    # took 24 V and CAN down one umbilical, which entered the back of the pelvis
    # through a 12 mm slot with a cable-tie strain relief either side of it.
    # A battery went back in and the umbilical went out, so the cable's diameter
    # and every feature derived from it are gone. What that wall carries now is
    # an XT90-S disconnect and a charge port (it carried a 6S balance port too
    # until a BMS took the cell taps over), whose dimensions are connector
    # mouldings and live in cad/electronics.py -- they are ADDED below rather
    # than replacements for these, because a panel cutout is not a cable slot.
    "tetherCableDiameter",
    "tetherPortWidth",
    "tetherPortHeight",
    "tetherPortZ",
    "tetherWallY",
    "tieSlotWidth",
    "tieSlotHeight",
    "tieSlotX",
    # THE Ø30.4 REGISTER POCKET, retired 14 September 2026 -- and the only pair
    # here that has nothing to do with the walking robot. The rotor plate used
    # to pilot on the actuator's Ø30 output register through a pocket in its own
    # face, and it has no pilot at all now: it lands flat on the register and is
    # located by the six M3 on Ø24. The pocket was drawn on the reading that the
    # register stood 1.2 mm INTO the plate while the plate landed on the
    # housing; the register stands 1.0 mm PROUD of the housing instead, so the
    # plate seats on it. Cutting the pocket on the other side of the seating
    # face works on paper and not in a printed part -- the pilot's depth and the
    # plate's clearance over the housing are the same millimetre shared out, and
    # 0.3 mm of clearance is inside what SLS holds on the feature that sets it.
    # cad/parameters.py carries the whole of it where these two were declared.
    "rotorRegisterDiameter",
    "rotorRegisterDepth",
}


# Dimensions ADDED after the port, which the golden reference cannot hold because
# the KCL never had them. The migration proper invents nothing -- that is what the
# EXTRA rule enforces -- so every entry here is a deliberate design change made on
# top of a finished, gated translation, and it names the change it belongs to.
#
# A name may only be added here alongside the commit that introduces it, and with
# a reason. If this list ever grows without one, the EXTRA rule has stopped
# meaning anything.
ADDED = {
    # ---- THE POWER SWITCH BOARD, September 2026 -----------------------------
    #
    # A second board of our own, in the pack's positive lead between the loop key
    # and the distribution board: the main fuse, the bus shunt, and a MOSFET
    # switch that is the robot's on/off and its low-battery cutoff.
    # electrical/power.py is the circuit and electrical/power_pcb.py is the
    # board; these are the dimensions the CAD needs to pack it and to print the
    # one feature that carries it.
    #
    # The outline and its height: an 8 mm spacer over the bought distribution
    # board, and THE BOUGHT BOARD'S OWN 50 x 50 FOOTPRINT. It was a 54 x 32.5
    # rectangle over the rear half of that board until the board went from
    # surface mount to through-hole, which wants about half again the area; the
    # rest came from the capacitor bank, which had reserved four positions of
    # 16 x 25 for the two 10 x 16 cans docs/BOM.md buys. Landing on the bought
    # board's outline also buys the mount: four screws where there were two and a
    # printed pad on the wall, so powerSwitchPadScrewY, powerSwitchPadHeight and
    # powerSwitchPadWidth are gone with it.
    #
    # AND THE BOUGHT BOARD WENT, 2026-10-07. This board stands on its nuts where
    # it stood, 9.6 mm lower, and carries the six motor outputs and the carrier's
    # feed on JST-XH headers, so it reaches both long walls: 50 x 66 on the same
    # four holes, powerSwitchWallGap off each wall. powerSwitchSpacer and
    # powerSwitchSpacerDiameter went with the spacers. xhDepth and xhPinOffset
    # are a JST-XH header's courtyard across its pin row, which every XH header
    # on the board shares and which the two that stood there before typed out;
    # phDepth, phPinOffset and phHeight are the same for the JST-PH motor
    # outputs.
    "powerSwitchBoardZ": -29.5,
    "powerSwitchRightX": 71.55,
    "powerSwitchRearY": -33.0,
    "powerSwitchFrontY": 33.0,
    "powerSwitchLeftX": 21.55,
    "powerSwitchWallGap": 0.6,
    "xhDepth": 6.75,
    "xhPinOffset": -0.525,
    "phDepth": 5.5,
    "phPinOffset": -0.55,
    "phHeight": 11.0,
    # The bank's lead pitch, which is what places a can by its first lead the way
    # every other footprint on that board is placed.
    "capacitorPitch": 5.0,
    # ---- THE SADDLE'S POWDER DRAIN, September 2026 -------------------------
    #
    # cad/joint.py's saddle is a closed box, and on the union of the finished
    # bodies that box measured as a genuinely sealed cavity: 7.66 cm3 in each
    # thigh and 7.53 cm3 in each of the pelvis's two hip clevises. In a sintered
    # part that is un-fused powder with no way out -- about 14 g of it across
    # the robot -- and it is the kind of thing an SLS house either refuses or
    # fixes to suit itself. One Ø4 bore through both side walls opens each one.
    # Nothing the KCL ever had, so it can only be declared here.
    "saddleDrainDiameter": 4.0,
    # ---- THE LID FITS, September 2026 ---------------------------------------
    #
    # The lid's locating lip filled the cavity's whole mouth and the four cover
    # bosses stood in its corners flush with the rim, so the lid rode on the
    # bosses rather than sitting down. The first printed prototype found it;
    # tools/gate_h.py is what finds the next one. The lid was already printed,
    # so the bosses came down instead: the lip's height and this much air.
    "coverLipBossClearance": 0.4,
    "coverBossDrop": 2.8,
    # ---- THE DECK'S FOUR SCREWS, September 2026 -----------------------------
    #
    # M3 on the ledges' centre line put every stock M3 head 0.25 mm into the
    # wall and left 0.4 mm of deck between its clearance hole and the plate's
    # edge. M2.5 now, placed by its 4.5 mm head with this much air to the wall,
    # through an open slot in the deck and into a pilot run through the ledge.
    "m25Clearance": 2.9,
    "m25Pilot": 2.1,
    "deckScrewHeadAir": 0.5,
    "deckScrewY": 30.85,
    # ---- THE WHEEL ADAPTER'S SEALED WAFER, September 2026 --------------------
    #
    # The plug stopped 0.2 mm short of the floor of the disc's old journal seat,
    # which united into a closed 16 mm3 void -- powder kept for good. It now
    # reaches this far past the floor, and tools/check.py counts shells so that
    # the next closed void fails on the edit that makes it.
    "plugSeatOverlap": 1.0,
    # cad/finish.py: the 0.5 mm chamfer put on every printed part's outer edges.
    # About one and a half layers at this nozzle -- a deburr, not a feature.
    "CHAMFER": 0.5,
    # cad/finish.py again: how short an edge has to be before the chamfer refuses
    # to attempt it, as a multiple of the chamfer itself. A chamfer takes its own
    # length off the far end of every edge running into the one being cut, so an
    # edge under twice the chamfer has nothing left once both neighbours are
    # broken. That case does not raise, it kills OCCT outright, so this is a
    # guard rather than a preference -- the reasoning is in cad/finish.py's own
    # docstring, and a refused edge is reported as SKIPPED rather than hidden.
    "SLIVER": 2.0,
    # cad/wheel.py: the wheel clamp modelled as the three bought items it is.
    # The KCL drew two blanks -- a solid Ø30 disc and a cylinder the size of a
    # cap head -- and never drew the screw or the heat-set insert at all, so it
    # had no dimensions for either. These are catalogue figures for an ISO 4762
    # M5 cap screw and the insert the adapter's bore is cut for, except the
    # screw's LENGTH, which follows from what it passes through: see the
    # derivation in cad/wheeled_parameters.py.
    #
    # THE SCREW IS A 30 AND THE INSERT IS 8 since 6 October 2026, when the
    # penny washer became a printed cap (below) and the insert moved to the
    # motor side of the adapter. The screw was 12 while the washer lay on the
    # hub's face; it crosses the cap's floor, the hub's centre ridge and the
    # whole adapter now. The insert is ThinkRobotics' M5, drawn at its own
    # drawing's 8 mm though its listing says 6; it was the 10 mm Amazon.in one,
    # and 9.5 before that.
    "wheelClampScrewDiameter": 5.0,
    "wheelClampScrewLength": 30.0,
    "wheelClampSocketAcrossFlats": 4.0,
    "wheelClampSocketDepth": 2.5,
    "wheelClampWasherBore": 5.5,
    "wheelInsertLength": 8.0,
    "wheelInsertThreadDiameter": 4.5,
    # The stations those put on the axis, alongside the washerInnerX and
    # washerOuterX the KCL already named: where the head's outer face sits,
    # where the screw's tip stops, and the washer's mid-plane. All three moved
    # with the cap: the washer lies on its floor and the head is flush with its
    # outer end.
    "capHeadOuterX": 54.45,
    "screwTipX": 19.450000000000003,
    "washerCenterX": 48.7,
    # ---- THE WHEEL CLAMP LOST ITS PENNY WASHER, 6 October 2026 --------------
    #
    # The clamp's Ø30 penny washer could not be bought in India at a sane price,
    # and looking for a printed replacement found that the hub it lay on was
    # drawn wrong: a skate wheel's two bearing seats stop against a ridge of hub
    # between them, and cad/skate_wheel.py had the bore Ø22 straight through.
    # The adapter's 23 mm spigot would have met that ridge 7 mm in. So the spigot
    # is 6 mm now (CHANGED below), and a printed cap in the outboard seat lands
    # on the ridge and takes the washer's place, squeezed end-on rather than
    # bent across a hole. These are the hub's seat and ridge, and the cap.
    #
    # The seat depth is the 608's width; the ridge's bore is unmeasured and
    # drawn in the middle of the window the bearing allows. Both are in
    # cad/wheeled_parameters.py with their provenance, and both are on the list
    # of what to measure before the adapter is printed.
    "skateWheelBearingSeatDepth": 7.0,
    "skateWheelRidgeBore": 16.0,
    "skateWheelRidgeInnerX": 31.95,
    "skateWheelRidgeOuterX": 41.95,
    # The cap: Ø22 to the seat, a 6 mm floor sized for the widest ridge bore the
    # bearing allows, an M5 clearance through it, and a pocket for the washer
    # with half a millimetre round it. It stands on the ridge and is as tall as
    # its floor, the washer and the screw head.
    "wheelCapDiameter": 22.0,
    "wheelCapFloor": 6.0,
    "wheelCapBore": 5.5,
    "wheelCapCounterbore": 12.0,
    "wheelCapInnerX": 41.95,
    "wheelCapOuterX": 54.45,
    # The adapter's bore since the insert went in from the motor side: the
    # screw's clearance on from the step the insert is pressed against to the
    # spigot's end. The step is the point of it -- with the insert bearing on
    # it, failing means punching out the adapter in front of the insert as
    # well as shearing the insert's own length -- and cad/wheeled_parameters.py
    # carries that arithmetic.
    "wheelSpigotClearance": 5.5,
    # ---- THE JOURNAL GOES IN LAST, AND ON ITS OWN SCREW, September 2026 ------
    #
    # journalRootFillet was here and is gone with the stub it relieved. What
    # replaced both is a bought Ø10 sleeve fitted from OUTSIDE once the motor is
    # in its fork, because nothing that stands proud of the rotor disc before
    # then can be brought into the far bearing: the fork is a single print whose
    # cheeks stand 45.2 mm apart and the motor with its disc bolted on measures
    # 49.9 mm to the journal's tip. cad/parameters.py carries that arithmetic
    # beside journalDiameter, and says plainly what the new anchor is worth.
    #
    # These are the sleeve, the screw that holds it and the nut it pulls against.
    # The journal's length is journalLength, which the golden already holds and
    # which has not moved since the stub. THE SLEEVE IS A MILLIMETRE LONGER since
    # 2026-09-30 and stands that far past the bearing's outer face, where the
    # DIN 433 washer used to sit: nobody in India stocks that washer.
    "journalSleeveProud": 1.0,
    "journalSleeveLength": 7.0,
    "journalSleeveBore": 5.3,
    "journalScrewClearance": 5.5,
    "journalScrewDiameter": 5.0,
    "journalScrewLength": 12.0,
    "journalScrewHeadDiameter": 9.5,
    "journalScrewHeadHeight": 2.75,
    "journalNutAcrossFlats": 8.0,
    "journalNutThickness": 2.7,
    # 1.3 mm over the nut's flats, not 0.3: cad/finish.py chamfers the floor of
    # this pocket, being all flat faces, and 0.5 mm round its perimeter left the
    # nut sitting on the chamfer rather than on the seat.
    "journalNutPocketFlats": 9.3,
    "journalNutPocketDepth": 3.3,
    # cad/hardware.py: the stations those put on the joint axis. The sleeve lands
    # on the rotor disc's outer face and ends flush with the bearing's outer face
    # -- the same 5 mm of Ø10 the dowel and the stub both ran in -- and the nut
    # sits against the outboard end of its pocket, which is the face the sleeve
    # clamps the disc's web against.
    #
    # THE NUT MOVED 1.2 mm INBOARD on 14 September 2026 and the web went from
    # 1.5 mm to 2.7. Neither is a decision about the nut: its pocket opens into
    # the register pocket's floor, and that floor came back to the plate's own
    # seating face when the register turned out to stand 1.0 mm proud of the
    # housing rather than 1.2 mm into the plate. See actuatorOutputProjection in
    # cad/parameters.py. The mouth is closed by the actuator's own output face
    # either way -- that is what makes the nut captive -- but it is closed
    # against the nut now instead of across 1.2 mm of air.
    "journalInnerX": 24.95,
    # A millimetre further out since the sleeve took the washer's place.
    "journalOuterX": 31.95,
    "journalNutOuterX": 22.25,
    # cad/poses.py: how far the knee may fold. It was 110 degrees, inherited from
    # the walking robot and never disputed by the geometry because the flat limbs
    # left thigh and shin in disjoint planes. Straddling the knee puts the
    # clevis's saddle back in the plane the shin sweeps -- unavoidably: a far
    # bearing means reaching round the actuator -- and the two touch at 103.0
    # degrees. 100 is where the gap is 1.0 mm, which is also the air the shin's
    # rotor disc has against the far cheek, so one margin covers both. The squat
    # and both knee review scenes are derived from it, and so is the URDF's knee
    # limit; tools/gate_f.py carries the poses that moved with it.
    # ---- THE MOTOR'S OUTPUT REGISTER STANDS PROUD, 14 September 2026 --------
    #
    # The actuator is 37.9 mm long and its Ø46 body is 36.9: the Ø30 output
    # register fills the last millimetre alone. Both figures are on the vendor
    # 2D print and the vendor STEP agrees, and the KCL had neither -- it carried
    # the overall length and nothing else, so the proxy put solid motor where the
    # step is and the rotor plate was drawn landing on a face that is not there.
    # cad/parameters.py carries the finding beside actuatorOutputProjection.
    "actuatorHousingDepth": 36.9,
    "actuatorOutputProjection": 1.0,
    "kneeCommissioningStop": 100.0,
    # cad/limb.py: where the cable-tie arch sits at a limb's CLEVIS end. The
    # 30.5 mm station the plate end uses was chosen against a Ø52 disc and
    # nothing else; a clevis puts a closed saddle box out to 36 mm from the joint
    # axis, which swallows an arch at 30.5 and leaves its tunnel inside the
    # cavity with no way to pass a tie. 42 stands the whole 10 mm block clear of
    # the saddle's top face. Only the thigh uses it -- the shins are unchanged,
    # which is why their golden STEP still holds.
    "limbTieArchZClevis": 42.0,
    # cad/parameters.py: how far the knee joint stands outboard of every other.
    # A flat limb lands a 6 mm plate on its lower actuator's rear cover and that
    # plate is the leg's exterior face; the straddled knee lands a 3 mm cheek
    # held the actuator's 0.3 mm off it, so the fork ended 2.7 mm inside the
    # leg's own surface. The whole joint moves rather than the fork -- actuator,
    # fork, shin, wheel motor and wheel together -- so every printed part keeps
    # its shape and the fork stays the part gate B holds. limbPlateThickness less
    # cheekThickness less actuatorClearance, all three already held here.
    "kneeOutboardOffset": 2.7,
    # cad/joint.py: the front cheek's bore, now cut to the bearing rather than to
    # the deleted carrier. Ø19 outside diameter plus the same 0.2 mm bond
    # allowance the Ø10.2 journal seat carries. The four carrier dimensions it
    # replaces are in RETIRED above.
    "bearingSeatDiameter": 19.2,
    # cad/joint.py: the shoulder that took over the deleted carrier flange's job,
    # and the boss on the cheek's outer face that carries it. A 3 mm cheek cannot
    # seat a 5 mm bearing, so the boss makes up the 2 mm and carries 1.5 mm of
    # shoulder past it; the bore lands on the outer race only. cad/hardware.py's
    # bearingCenterX is where the bearing sits in the finished seat, 1 mm further
    # outboard than the cheek's own mid-plane, where it used to be drawn.
    "bearingSeatShoulderBore": 17.5,
    "bearingSeatShoulderThickness": 1.5,
    "bearingSeatBossDiameter": 26.0,
    "bearingSeatBossThickness": 3.5,
    "bearingCenterX": 28.45,
    # cad/joint.py: the outboard end of the clevis -- the plane the front cheek's
    # outer face and the saddle's end share, and the last plane of printed
    # structure on a joint. The KCL computed it inline inside the clevis function
    # and so had no name for it. It is a name now because a second part depends on
    # it: cad/wheeled_parameters.py builds the pelvis's width on this plane so the
    # torso's flank comes out flush with the hip saddle instead of 6.45 mm inside
    # it. The value is frontCheekX + cheekThickness / 2, both of them ported
    # dimensions this gate already holds.
    "clevisOuterX": 28.95,
    # cad/electronics.py: where the payload boards are screwed down. The KCL drew
    # every board as a plain slab and so had no hole anywhere in the torso, which
    # left the packing half answered -- a reserved volume says where a board may
    # be and nothing about where a standoff lands. The SBC's pattern is the
    # Banana Pi BPI-M4 Zero's, inherited from its Raspberry Pi Zero W form-factor
    # claim; the 4 mm inset is ours, on the two boards we design ourselves. The
    # provenance for each is in cad/electronics.py beside the dimension.
    "sbcBoardWidth": 65.0,
    "sbcBoardDepth": 30.0,
    "sbcHoleInset": 3.5,
    "sbcHolePitchX": 58.0,
    "sbcHolePitchY": 23.0,
    "sbcHoleDiameter": 2.75,
    "boardHoleInset": 4.0,
    # ---- THE BATTERY WENT BACK IN, September 2026 --------------------------
    #
    # Everything from here down belongs to one change, and it is the largest this
    # branch has made on top of the translation. The robot was tethered from
    # August 2026 because no 6S brick fits a cavity whose longest dimension is
    # across the robot, and because 190 g was the whole of the mass headroom;
    # deleting hip roll gave 700 g back, and two 3S bricks on edge are 52 mm
    # across where one 6S is 108 to 125 long. cad/electronics.py carries the
    # reasoning, cad/wheeled_parameters.py the height it costs, and docs/NOTES.md
    # the decision. The CHANGED register below holds what the same change moved.
    # cad/parameters.py: the M2.5 heat-set insert that was here -- m25InsertBore
    # 3.2, m25InsertDepth 5.0 -- went with the deck's SBC posts in September 2026.
    # What replaced it is the socket head of the M2.5 that holds each SBC
    # standoff down, drawn because it hangs in the 3 mm under the carrier. ISO
    # 4762 catalogue figures.
    "m25CapHeadDiameter": 4.5,
    "m25CapHeadHeight": 2.5,
    # cad/electronics.py: the pack, in TORSO axes rather than catalogue axes,
    # because the packs are stood on edge and the two frames do not agree. It was
    # "a Gens Ace class 3S 2200 mAh brick, 76 x 33 x 25", which does not exist:
    # real 2200 mAh 3S packs are 105 to 108 mm long. Since 2026-09-30 it is a
    # Bonka 3S 1000 mAh 35C, 75 x 32 x 17 and 95 g as ElectronicsComp lists it,
    # in a bay kept at the old size so nothing else moved.
    #
    # MEASURED, 2026-10-05, when the packs arrived: 77 x 38 x 19 at most, but
    # only the 12 mm where the leads come out is that big, and the 65 mm of body
    # furthest from them is within 35 x 17. The pack is drawn as those two
    # blocks, and the band over it went from 36 to 39 for the body's 35 and the
    # lead end's 38 -- which is the torso's 3 mm and the CHANGED register's
    # second decision.
    "batteryPackLength": 77.0,
    "batteryPackThickness": 17.0,
    "batteryPackWidth": 35.0,
    "batteryPackBodyLength": 65.0,
    "batteryPackLeadThickness": 19.0,
    "batteryPackLeadWidth": 38.0,
    "batteryPackGap": 11.0,
    "batteryWidth": 78.0,
    "batteryDepth": 54.0,
    "batteryHeight": 39.0,
    "batteryX": -33.55,
    # THE BATTERY'S HOLD-DOWN, 2026-09-30, cad/electronics.py -- and its fin,
    # fences and their four names went on 2026-10-05; see the block after next.
    # There was none:
    # the deck was said to hold the packs by 3 mm of squeeze that was air. A rail
    # under each pack, a stop on its end, a fin between the two and fences down
    # their outer faces place them; foam cut from one 5 mm sheet pushes them there
    # and takes up whatever the bought pack differs from the drawn one by. The fin
    # and fences hung from the deck for a day and stand on the pelvis now, 1.5
    # thick to reach the actuator harness run and no further, and stopping 6 mm
    # under the pack tops. The foam down the block's two sides went on
    # 2026-10-06, and batteryFoamSide and batteryFoamFaceY with it: the wall
    # pads bear on the block's own faces, 45 mm apart.
    "batteryFoamFree": 5.0,
    "batteryPackOuterY": 22.5,
    "batteryPackTopZ": 2.5,
    "batteryFoamTop": 4.0,
    "batteryPackLeftX": -71.55,
    "batteryPackRightX": 5.450000000000003,
    "batteryFoamEnd": 3.0,
    "batteryRailStopHeight": 3.0,
    "batteryFoamLeadAir": 2.0,
    # Since the packs were measured, 2026-10-05: where each body ends and every
    # face and every piece of foam beside it stops; the air kept round the lead
    # end's worst case; and the rails' sill under the lead end and the stop at
    # its foot, which stands in the bay gap now rather than inside the bay.
    "batteryPackBodyEndX": -6.549999999999997,
    "batteryLeadEndAir": 1.0,
    "batteryRailStopLength": 2.5,
    "batteryRailSillTopZ": -36.5,
    # THE BATTERY'S WIRING SPACE, 2026-10-05, cad/electronics.py. The BMS went
    # between the two packs and the three are one block, 45 mm across by the
    # owner's figure; the fin and the two fences went, and eight pads off the
    # long walls bear on the side foam instead, so that the strip beside each
    # pack is clear at the height its XT60 lies at. The connectors and the
    # chases the leads turn in are placed from these, and the CAN loom moved to
    # the back of the bay gap to give the rear connector its strip.
    "batteryBlockWidth": 45.0,
    "xt60Span": 15.6,
    "batteryConnectorLength": 30.0,
    "batteryConnectorY": 28.05,
    "batteryConnectorZ": -19.0,
    "batteryConnectorRightX": -7.549999999999997,
    "batteryConnectorLeftX": -37.55,
    "batteryLegLaneZ": -2.4000000000000004,
    "batteryLeadInset": 7.0,
    "batteryLeadReach": 10.0,
    "batteryLegReach": 10.0,
    "harnessAir": 0.5,
    "batteryPadWidth": 6.0,
    "batteryPadHeight": 5.0,
    # The owner's limit, 2026-10-06: no wall pad reaches more than 17 mm up the
    # pack from its bottom face. It brought the high pad down 10.5 mm.
    "batteryPadReach": 17.0,
    "batteryPadLowZ": -25.0,
    "batteryPadHighZ": -20.5,
    "batteryPadHighX": -55.949999999999996,
    "batteryPadLeadIn": 1.5,
    "loomRunX": 18.5,
    # THE BOUGHT DISTRIBUTION BOARD, September 2026, and the parts it displaced.
    # The power-entry PCB this project was going to lay out and have fabricated
    # is gone: a SwiftWing PDB-02-XT60 does the same job -- pack in through an
    # XT60, six branches out on solder tabs -- for about three hundred rupees and
    # no design time. Its 50 mm square is 12 mm wider than the bay the custom
    # board needed, which is what took the shell from 135 to 141 and what took
    # the 10.2 mm lead chase with it. The pack's connectors live above the board
    # instead, and what is left between the bays is ordinary clearance.
    "pdbWidth": 50.0,
    "pdbDepth": 50.0,
    "pdbThickness": 1.6,
    "pdbHolePitch": 45.0,
    "pdbY": 0.0,
    "pdbBoardZ": -29.5,
    "pdbTopZ": -27.9,
    "bayGap": 15.099999999999994,
    "panelX": 36.55,
    # The Matek 12S Pro BEC, which replaced the generic buck module this file
    # used to reserve 26 x 42 x 14 for on the deck. 9-55 V in, 5 V at 5 A out,
    # and a fifth of the volume -- so it moved down into the power bay, where its
    # input already is.
    "becWidth": 35.0,
    "becDepth": 24.0,
    "becHeight": 5.5,
    # The only floor-to-deck path left once the board took the chase: the strip
    # between the battery's rear face and the shell wall.
    "loomRunY": -30.3,
    # The fourth band and the plate that makes it possible. The cavity is full at
    # floor level, so the upper two boards have nothing to stand on and
    # cad/deck.py bridges to four ledges on the walls instead.
    "deckThickness": 3.0,
    "deckZ": 6.5,
    "deckBandZ": 9.5,
    "interiorHalfDepth": 33.6,
    "deckLedgeWidth": 12.0,
    # 6 since 2026-09-30, for 2 mm of ledge outside each screw's thread.
    "deckLedgeDepth": 6.0,
    "deckLedgeHeight": 5.0,
    "deckLedgeX": 52.0,
    "deckLedgeY": 30.6,
    "deckWidth": 148.29999999999998,
    "deckDepth": 66.4,
    "deckDropClearance": 0.4,
    "deckCornerNotch": 9.0,
    "controllerScrewX": 66.0,
    "controllerScrewY": 19.0,
    # ---- THE CONTROLLER BAY TOOK THE BEC AND THE MONITOR, September 2026 -----
    #
    # The rear outboard corner the charge socket passes over, cut out of the
    # reservation and out of the board alike rather than promising 12 mm of
    # height there that the socket has already taken. cad/electronics.py says
    # why the bay is 140 mm wide and why this corner is the one that goes.
    "controllerNotchWidth": 21.45,
    # ---- WHAT THE CARRIER CARRIES, September 2026 ---------------------------
    #
    # Stations on the controller carrier, every one of them read off
    # electrical/carrier_pcb.py -- which is where the board is laid out and where
    # each of these is measured against its neighbours in three dimensions --
    # and turned from the board's frame into the torso's by onCarrier(). They are
    # here rather than derived because the board's layout is the authority: a
    # part that moves there moves here to match, and a number that no longer
    # matches is exactly what this gate is for.
    "transceiverX": 17.450000000000003,
    "transceiverY": 0.0,
    "transceiverPitch": 11.0,
    "becX": -6.049999999999997,
    "becY": 0.0,
    "becOnCarrierHeight": 6.5,
    "busSenseStandoff": 3.0,
    "harnessX": 21.450000000000003,
    "harnessY": -19.5,
    "harnessWidth": 47.0,
    "harnessDepth": 5.75,
    "harnessHeight": 12.8,
    "controllerNotchDepth": 5.0,
    # Standoffs, and the plane each board therefore sits on. A reserved volume
    # says where a board may be and nothing about what holds it there; these are
    # the other half of that answer, and the KCL had none of them.
    "standoffHeight": 3.0,
    "standoffDiameter": 6.0,
    # The SBC's standoffs, which since September 2026 are bought M2.5 x 10 hex
    # pillars standing on the controller carrier. This name held 2.0 while the
    # deck's posts stood there instead; 10 is a stocked length, and the next one
    # down puts the SBC's microSD socket onto the BEC's cable ties.
    "sbcStandoffHeight": 10.0,
    "sbcStandoffDiameter": 5.0,
    # The carrier's hole for the screw under each one, drilled in laminate.
    "sbcStandoffHole": 2.7,
    "powerBoardZ": -28.0,
    "controllerBoardZ": 12.5,
    # THE SBC'S FOUR POSTS WERE HERE -- sbcPostDiameter 8.0, sbcPostHeight 14.0,
    # sbcPostClearance 8.6 -- printed with the deck and passing THROUGH the
    # controller carrier. They went in September 2026, when the SBC moved onto
    # standoffs on the carrier itself.
    #
    # Where the WeAct core board sits on the carrier: the centre of the strip
    # between the carrier's outboard edge and the SBC's own edge, because the
    # core board stands taller than the SBC's underside. It was derived from the
    # post, whose face was half a millimetre further out, and moved 0.25 mm
    # inboard when the posts went. A derived name rather than a placement because
    # the shell's width now moves on its own and a typed number would go stale.
    "weActX": -52.525,
    # Bought electrical hardware at catalogue size, none of it in reference/:
    # connector shells and converter modules are commodity parts and every maker
    # builds them to the same table. The panel cutouts are cut to these, so they
    # are the figures to measure before the pelvis is printed.
    "xt60Length": 16.0,
    "xt60Width": 8.1,
    "xt60Height": 7.5,
    # THE XT90'S THREE NAMES ARE GONE, September 2026, and this is where they
    # were: xt90Length 20.5, xt90Width 15.5, xt90Depth 21.0, the bare connector
    # the main disconnect used to be. They went with the part. The rear wall was
    # swept position by position against every solid in the cavity and the
    # flanged XT90E-M -- 42.0 x 22.8 x 15.1 on AMASS's own drawing, 19.7 mm of it
    # inside the wall -- clears 6 mm at x 50 to 53 and nowhere else, which is the
    # patch the charge inlet already holds. An XT60E-M took its place: same 30 A
    # contact rating from the same maker, 8.3 mm inside the wall instead of 19.7.
    # THE BALANCE PORT WAS HERE AND IS GONE, September 2026, and this is the only
    # place its figures survive. It was added as ONE 7-way JST-XH where the packs
    # offer two 4-way tails -- 19.5 wide, 7.0 high, 8.0 deep, at +15.0 outboard of
    # the disconnect -- because joining those tails inside the shell let a bench
    # charger see the single 6S pack the pair are wired as. It was removed in the
    # same month, when a balancing BMS went onto those same cell taps in the bay
    # gap: the socket then presented nothing the board inside did not already
    # hold, and a second path to an unfused pack is a liability rather than a
    # convenience. Four names left cad/ with it, and balancePortZ, balanceSlot*
    # below went too. Put a port back in that wall and every one of them has to be
    # re-derived, not retyped -- the panel's outline is computed from whatever
    # connectorOpenings() returns.
    # The charge port's height, which has not moved through any of this. The rule
    # that was learned above it is worth keeping even though the pair it was
    # learned on is now a single connector: each opening is its connector plus
    # half a millimetre all round, so ONE MILLIMETRE BETWEEN TWO BODIES IS ZERO
    # MILLIMETRES BETWEEN TWO OPENINGS. The disconnect's socket and the balance
    # port's ran into one another along a six-millimetre edge on that arithmetic,
    # which was equally true of the bare 2.4 mm wall and had never been measured;
    # it surfaced when the connector panel was drawn, because a knife edge is the
    # one thing cad/finish.py cannot chamfer. Anything put back in this wall wants
    # two bond gaps plus a socket wall -- 2.5 mm -- from its neighbour.
    "dcdcWidth": 26.0,
    "dcdcDepth": 42.0,
    "dcdcHeight": 14.0,
    # THE BUS MONITOR'S TWO PLAN FIGURES MOVED, September 2026, and the reason is
    # that the board was finally looked at. It had been a guessed 24 x 18 block
    # since the day it went on the bill; the vendor's own front and back views
    # show a square board of about 22 a side, scaled against the 2.54 mm header
    # pitch that is the only hard dimension a photograph of it carries. A
    # PHOTOGRAPH IS NOT A CALIPER and cad/electronics.py says so at length -- but
    # a measured 22 is a better input than an invented 24, and correcting it later
    # moves the two posts with it because they are derived rather than typed.
    "busSenseWidth": 22.0,
    "busSenseDepth": 22.0,
    "busSenseHeight": 8.0,
    # WHERE THAT BOARD SITS AND WHAT HOLDS IT, all new with the same change. The
    # same two views show it carries two mounting holes -- the outer pair of the
    # column of four, the inner pair being the shunt terminals -- so it is
    # screwed to two pads on the pelvis's rear wall instead of taped to the
    # distribution board. The pitch and the inset are the photograph's; the
    # pilot, the pad and the setback are ours, and cad/electronics.py gives each
    # a reason.
    #
    # IT HUNG UNDER THE ELECTRONICS DECK FOR ONE REVISION and those names are
    # gone with it -- busSensePostDiameter and busSenseStandoff. The deck was
    # wrong for a reason no gate measures: the board's leads run down into the
    # bay, so a deck carrying it is a deck tied to the torso by wiring.
    "busSenseHolePitch": 16.7,
    "busSenseHoleInset": 2.5,
    # The stations, DERIVED AND NOT CHOSEN, pinned here at their computed values
    # the way pdbTopZ and packLeadZ above are. x is the rear deck ledge's own
    # edge, less the room a driver needs beside it, plus half the hole pitch;
    # y and z are the wall and the pads. Move the ledge, the wall or the bought
    # board's standoff and this gate says so rather than letting the monitor
    # follow silently.
    "busSenseX": 53.45,
    "busSenseY": -1.0,
    # The looms, reserved as chases rather than drawn as routed wire.
    "busWireDiameter": 3.5,
    "canWireDiameter": 2.6,
    "harnessBundleWidth": 9.0,
    "harnessBundleHeight": 7.0,
    "harnessRunY": -27.0,
    # cad/torso.py: what the pelvis grew to hold all of that. Two rails under the
    # packs, four posts under the power-entry board, and the service panel that
    # replaced the tether slot in the rear wall.
    # THE WHEEL MOTOR'S FOUR REAR SCREWS SIT IN SPOT FACES, 2026-09-30, a
    # millimetre deep for a 0.5 mm DIN 125 washer, so an M3 x 12 from any shelf
    # takes the thread MISUMI's M3 x 14 did.
    "statorScrewSpotFaceDiameter": 7.6,
    "statorScrewSpotFaceDepth": 1.0,
    "batteryRailThickness": 3.0,
    # 20 until 2026-09-30, outside the thinner packs; now just outboard of the
    # IMU's reservation, and starting at the left hip saddle's inboard face,
    # because a rail through the saddle's hollow seals a void inside it.
    "batteryRailY": 12.5,
    "batteryRailStartX": -25.75,
    "batteryRailEndX": 7.950000000000003,
    # The fin between the packs stops at the IMU's reservation.
    "boardPostSize": 8.0,
    "powerPostX": 22.5,
    "powerPostY": 22.5,
    "panelWallY": -34.8,
    # Two colours, for the two things in the torso that are neither board nor
    # can: the cells themselves and the copper that leaves them.
    "cellGrey": "#4a4f57",
    "copperRed": "#a8452a",
    # ---- EVERYTHING GETS A MOUNT, September 2026 ---------------------------
    #
    # A sweep of the torso for hardware that was DRAWN but not HELD, prompted by
    # a plain question -- are the external connectors mounted, or are they wires
    # through holes? They were neither: the rear wall passed three connector
    # bodies and nothing retained any of them. Two more items were found in the
    # same state, and the three answers below are the printed half of the fix.
    # docs/BOM.md carries the rest, which is a method per item rather than
    # geometry, because tape and epoxy are the right answer for most of them.
    #
    # THE REAR WALL'S PANEL HARDWARE, September 2026, and it replaced a printed
    # part rather than joining one. cad/connector_panel.py was a 6 mm plate that
    # the three external connectors were epoxied into, because an XT90-S, a
    # JST-XH and an XT30 are constant-section prisms that nothing cut in a 2.4 mm
    # wall can capture. The panel is deleted and so are its fifteen names --
    # connectorPanelThickness, ...ApertureGap, ...Seat, ...Edge, the four fixing
    # stations, the four outline figures and ...FrontY -- along with
    # panelClearance, the bond gap they existed to carry, and the XT30's own
    # catalogue block.
    #
    # What answered the same problem is bought hardware that retains itself: an
    # AMASS XT60E-M and XT60E-F that bolt through the wall by their own ears and
    # flange, and an SMA antenna bulkhead that clamps it between a shoulder and a
    # nut. The connector figures below are the maker's drawings and not
    # measured; the station figures are this robot's own.
    #
    # z = 22 IS THE ONLY BAND THAT WORKS and it is measured rather than chosen.
    # Below the electronics deck the rear wall is committed end to end -- the bus
    # monitor comes within 12.6 mm of it, and the deck's own wall ledges stand ON
    # it between x 46 and 58 -- so a bushing whose nut wants a clear 22 mm circle
    # 6 mm deep fits nowhere down there. Above the deck the same wall has 18 to
    # 67 mm of clear depth, between the deck's top face at z = 8 and the cover's
    # lip at 38.2, which puts a 20 mm window's centre between 19 and 30.
    # THE DISCONNECT'S OWN FIGURES ARE OFF AMASS'S DIMENSIONED DRAWING and the
    # ones they replaced were off a marketplace listing. That is the whole reason
    # this block was rewritten: the listing gave the XT90E-M a 25 x 16 cutout
    # with its screws 29 mm apart, the maker's drawing gives 32.4 mm and a flange
    # 42.0 across, and a pelvis drilled at 29 is a 182 g part no screw goes into.
    # The XT60E-M below is measured the same way -- 27.00 tip to tip, ears 20.00
    # apart, 16.70 along its axis in three sections. Measure one even so.
    # THE DISCONNECT'S TWELVE NAMES WENT WITH IT on 2026-09-16, when the loop
    # key was replaced by a momentary button that commands the switch board
    # instead of breaking the pack lead by hand. What is left is a bushing, a
    # nut and a body -- the antenna's way of mounting rather than the
    # disconnect's, and no screws at all.
    #
    # THE STATION IS THE INTERESTING NUMBER. It is x -44 and not the
    # disconnect's 18, because the depth behind this wall decides it: a sweep
    # at the station height found 11.2 mm of clear air behind x 18 before the
    # actuator harness bank, which took a connector reaching 8.3 mm in and will
    # take no panel switch at all. 21.4 is the most the wall offers anywhere,
    # outboard of x -44, and buttonClearDepth carries it so that a deeper
    # switch has something to be checked against.
    # Daier's own Ø12.4 panel cutout since 2026-10-12; it was the thread plus
    # two tenths, 12.2, which nobody had held against the maker's drawing.
    "buttonHoleDiameter": 12.4,
    "buttonNutDiameter": 17.5,
    "buttonNutDepth": 3.0,
    "buttonBodyDepth": 16.0,
    "buttonOutboardDepth": 6.0,
    "buttonClearDepth": 21.4,
    # The one M2 clearance on this robot, and the nuts it takes, in
    # cad/parameters.py with the M3 ones. Forced by the disconnect's nuts: they
    # sit 2.25 mm from its body, which an M2 clears by 0.25 and an M2.5 fouls by
    # the same. It was m25Clearance, 2.8, for one revision before anybody asked
    # where the nut went.
    # THE M2 IS RETIRED, 2026-10-12. It was 2.4, then 2.2 for a day so the wall
    # to the measured nose's wider cut kept 1.05 mm, at the price of drilling
    # the holes out; m2NutAcrossFlats 4.0 and m2NutThickness 1.6 went with it.
    # The inlet takes M2.5 on m25Clearance now, each screw 0.25 mm outboard in
    # the connector's Ø3.00 ear hole so that the M2.5 nut's flat lands on its
    # body. ISO 4032 M2.5: 5.0 across the flats, 2.0 thick.
    "m25NutAcrossFlats": 5.0,
    "m25NutThickness": 2.0,
    # THE CHARGE INLET IS AN XT60E-M, 2026-10-05, and its names say inlet
    # because it is no longer a socket. It was the female XT60E-F for three
    # weeks, and those nine names went with it: chargeSocketFlangeWidth 34.0,
    # FlangeHeight 15.8, FlangeThickness 3.1, BodyWidth 18.7, BodyHeight 11.5,
    # BodyDepth 17.1, CutWidth 19.2, CutHeight 12.0 and FixingPitch 25.0, plus
    # chargeSocketPanelX 55.5, which is chargeInletPanelX below at 59.0.
    # Before the female it was a GX16-2, whose five figures were
    # chargeSocketHoleDiameter 16.0, NutDiameter 22.0, NutDepth 6.0, BodyDepth
    # 19.0 and OutboardDepth 12.0. The male's figures are the ones the main
    # disconnect was drawn to until 2026-09-16, under the names xt60Panel*: the
    # same AMASS drawing, the same part, the same caveat that its three axial
    # sections are the view's proportions and not its labels.
    # THE NOSE WAS MEASURED ON THE PART, 2026-10-12: 15.3 x 8.0 with calipers,
    # where the untraceable drawing figure was 14.2 x 6.7 and the pelvis printed
    # to it would not take the connector. The cutout is the nose plus the 0.2 mm
    # a side gate H accepts, computed rather than typed.
    "chargeInletNoseWidth": 15.3,
    "chargeInletNoseHeight": 8.0,
    "chargeInletCutAir": 0.2,
    "chargeInletCutWidth": 15.3 + 2 * 0.2,
    "chargeInletCutHeight": 8.0 + 2 * 0.2,
    # Owner-selected trial curvature from the datasheet outline, 2026-10-12;
    # not a manufacturer-specified radius, pending measurement of the part.
    "chargeInletKeyRadius": 3.0,
    "chargeInletFixingPitch": 20.0,
    # The play an M2.5 has in the connector's Ø3.00 ear hole, all of it spent
    # standing each screw outboard so its nut lands on the body, 2026-10-12.
    "chargeInletScrewOffset": 0.25,
    "chargeInletEarSpan": 27.0,
    # Owner assumes a 12 mm interior flange after the real part fouled the boss.
    "chargeInletEarWidth": 12.0,
    "chargeInletBossClearance": 0.5,
    "chargeInletEarThickness": 3.2,
    "chargeInletBodyWidth": 15.5,
    "chargeInletBodyDepth": 5.1,
    "chargeInletOutboardDepth": 6.0,
    "chargeInletInboardDepth": 8.3,
    "antennaHoleDiameter": 6.5,
    "antennaNutDiameter": 11.0,
    # The antenna's nut had borrowed chargeSocketNutDepth, the GX16's; it has its
    # own name now that the figure it borrowed is gone, at the same 6.0.
    "antennaNutDepth": 6.0,
    "antennaBodyDepth": 15.0,
    "antennaOutboardDepth": 8.0,
    # THE SMA MOVED TO THE LEFT FLANK, 2026-10-10, with a D-flat facing down,
    # and these nine went in without being declared here -- gate A failed from
    # that commit until 2026-10-12, when the audit in docs/DIMENSION_AUDIT.md
    # found it. Registered now with where each comes from. NONE IS MEASURED: the
    # pigtail in hand is a generic u.FL-to-SMA bulkhead, not the Amphenol part
    # the hole is drawn to, and a 1/4-36 thread with no flat will not pass a
    # 6.0 mm D.
    #   the D-hole's flat to the opposite arc, Amphenol 132203 panel drawing
    "antennaHoleFlatSpan": 6.0,
    #   1/4-36 UNS major diameter, and the flat on the bushing that keys in it
    "antennaBodyDiameter": 6.35,
    "antennaBodyFlatSpan": 5.85,
    #   the owner's 9.5 mm for the body inside the wall, unmeasured
    "antennaInboardDiameter": 9.5,
    #   a 12 mm antenna base outside, with 2 mm round it to the flank
    "antennaBaseDiameter": 12.0,
    "antennaBaseClearance": 2.0,
    #   where it stands on the left flank, and the flank's mid-wall plane
    "antennaSideY": -21.5,
    "antennaSideZ": 21.0,
    "sideWallX": 75.75,
    "panelHardwareZ": 23.5,
    "buttonPanelX": -44.0,
    # BOTH OTHER STATIONS MOVED WITH THE CHARGE SOCKET, and were solved for:
    # swept across the wall against every solid in the cavity and each other.
    # The socket went outboard from 50.0 to where its flange still lands on the
    # wall, and the antenna from 68.0 to the far side of the disconnect, because
    # nothing fits beyond a 34 mm flange before the wall ends. The male inlet
    # went 3.5 further out on 2026-10-05, because it goes in from inside: at 55.5
    # its ear plate could not pass the actuator harness bank's plugs, and beyond
    # 59.45 its nose cannot pass under the rear right cover boss. 58.7 since
    # 2026-10-12: the measured nose is 1.1 mm wider, gate I passes 58.5 to 58.85
    # and fails at 58.4 and 58.95, and this is the middle.
    # Owner keeps it level with the button, moving the flange inboard to
    # leave 0.55 mm laterally before the boss begins at x66.55.
    "chargeInletPanelX": 52.5,
    "chargeInletPanelZ": 23.5,
    "antennaPanelX": -8.0,
    # THE CHASE THROUGH THE ELECTRONICS DECK, cad/deck.py, and it is an old gap
    # being closed rather than a cost of the above. That plate has spanned the
    # cavity wall to wall with no way through it since it was drawn, while the
    # actuator harnesses have always had to get from the two floor cable ports to
    # the controller carrier above it. The panel hardware's two power leads share
    # it. 34 mm wide takes the two 9 mm actuator bundles, the 2.6 mm CAN loom and
    # two 14 AWG leads; 6 mm deep stops short of the battery's squeeze, because
    # the packs end at y = -26 and this reaches -27.2; and x = 27 is the only
    # stretch of the rear edge that is neither a fixing nor over the packs.
    "deckChaseWidth": 44.0,
    "deckChaseDepth": 6.0,
    "deckChaseX": 22.0,
    # Dedicated exits for the IMU and front power/sense leads.
    "deckImuChaseX": -20.8,
    "deckImuChaseWidth": 18.0,
    "deckPowerChaseX": 38.0,
    "deckPowerChaseWidth": 12.0,
    # How far the screw taps into the plate, and what the plate is notched by
    # where the deck's rear ledge comes down through its top edge. The second was
    # a real collision before it was measured -- 148 mm3 of printed ledge
    # standing in the plate -- and it is the same 0.4 mm cad/deck.py holds its
    # own corner notches off the cover bosses by.
    "fixingPilotDepth": 5.0,
    "ledgeNotchClearance": 0.4,
    # THE IMU SEAT, three ribs on the shell floor with its five names here, came
    # off the pelvis on 2026-10-14, when the IMU went under the deck.
    # THE IMU UNDER THE DECK, 2026-10-14, cad/electronics.py. The board is
    # 7Semi's ES-12234: 10.5 x 10 off 7Semi's STEP (exports/imu-research/
    # 10297.STEP), where it was an 11 x 10 guess, and 1.50 thick by the owner's
    # calipers. The chip's outline and offset are that STEP's; the socket, plug
    # and lead are JST's SH catalogue. It hangs chip down under the deck over the
    # power bay at x 38, y 5, its socket 0.5 under the plate and its plug edge
    # forward, away from the deck screws and wall ledges at x +/-52; the lead
    # runs 15 mm forward under the plate to the front notch. The socket's 0.5 of
    # air is so that a socket taller than JST's catalogue cannot jam the board in
    # the deck's grooves, which set its height; it bore on the plate until then.
    "imuBoardWidth": 10.5,
    "imuBoardDepth": 10.0,
    "imuBoardThickness": 1.5,
    "imuChipWidth": 3.8,
    "imuChipDepth": 5.2,
    "imuChipHeight": 1.18,
    "imuChipOffsetX": -0.37,
    "imuChipOffsetY": -0.64,
    "imuSocketWidth": 7.0,
    "imuSocketDepth": 4.25,
    "imuSocketTail": 0.7,
    "imuSocketHeight": 2.95,
    "imuSocketInset": 0.6,
    "imuPlugWidth": 7.0,
    "imuPlugThickness": 2.95,
    "imuPlugLength": 2.0,
    "imuLeadWidth": 4.0,
    "imuLeadHeight": 1.0,
    "imuX": 38.0,
    "imuY": 5.0,
    "imuSocketAir": 0.5,
    "imuSocketFaceZ": 3.05,
    "imuZ": 0.3699999999999999,
    "imuLeadRun": 15.0,
    "imuSocketMouthY": 9.4,
    "imuPlugBackY": 11.4,
    "imuLeadExitY": 26.4,
    # Its address jumpers, the ADD pad and the 0 and 1 blobs, on the socket face
    # near its left-hand side as it hangs: off the seller's photograph of that
    # face, scaled by the board's outline. Drawn so that the rail on that side
    # can be measured clear of them; the heights are guesses.
    "imuAddPadFrom": 2.5,
    "imuAddPadTo": 3.5,
    "imuAddPadInset": 0.65,
    "imuAddPadHeight": 0.1,
    "imuJumperFrom": 7.3,
    "imuJumperTo": 9.7,
    "imuJumperInset": 0.85,
    "imuJumperReach": 2.2,
    "imuJumperHeight": 0.5,
    # And the rails it hangs in, cad/deck.py: a 1.5 wall 0.2 off each 10 mm
    # side, a 1.2 lip along the bottom reaching 1.0 in from the groove -- 0.8
    # under the board, which keeps 0.3 flat on it after the finishing chamfer --
    # a stop behind each rear corner reaching 1.5, and a 3 x 3 post over the
    # middle of the rear edge, 0.5 in from it, reaching from the board's socket
    # face to the plate. The walls, stops and post lap 0.5 into the plate.
    "deckImuRailClearance": 0.2,
    "deckImuRailWall": 1.5,
    "deckImuRailLip": 1.0,
    "deckImuRailLipThickness": 1.2,
    "deckImuRailStop": 1.0,
    "deckImuRailStopReach": 1.5,
    "deckImuPostWidth": 3.0,
    "deckImuPostLength": 3.0,
    "deckImuPostInset": 0.5,
    "deckImuLap": 0.5,
    # And the ledge over each lip that makes each rail a groove, the same
    # afternoon: full length on the right, and on the left between the jumpers,
    # this far short of each.
    "deckImuLedgeMargin": 0.3,
    # The 22 mm square of floor the battery rails stand either side of, which was
    # the IMU's reservation until it left the floor. Its own name now, so that the
    # rails -- and the pelvis -- stay where they were.
    "floorSquareDepth": 22.0,
    # THE BATTERY STRAP SLOTS -- strapSlotWidth 16.0, strapSlotHeight 3.0 -- went
    # on 2026-09-30 with the straps. Neither strap route was ever open: one led
    # into the hip saddle and the other into the CAN loom and the harness runs.
    # ---- THE PACK GETS A BMS, September 2026 -------------------------------
    #
    # The robot carries a 6S pack with NO protection of any kind: no cell
    # monitoring beyond the INA226's view of the bus, no over-discharge cutoff,
    # and balancing only when somebody plugs a charger into the 7-way port. A 6S
    # BMS on the cell taps answers two of those three and is the precondition for
    # ever charging the pack in place.
    #
    # WIRED CHARGE-ONLY, which is what lets it be a small board. The discharge
    # path is unchanged, so the BMS sees about 2.2 A rather than the bus's 24 A
    # peak -- a common-port board carrying the whole bus would want 30 to 40 A of
    # FET in a sealed box, and no board that size fits this torso anyway: the
    # cavity was swept for free volume and the largest box left in it is
    # 38 x 64 x 12 mm. The cost is stated rather than hidden: no over-discharge
    # cutoff, so the main disconnect is still what stops a parked robot flattening
    # its own pack.
    #
    # NOT ONE OF THE BAY'S DIMENSIONS IS CHOSEN. Each is another part's face: the
    # slot the board is held in across the robot; the connector panel behind and
    # the shell wall in front, each less 1.5 mm; the electronics deck above, less
    # the air the board hangs under; and the tops of its own card guides below.
    # It lands on 9 x 58.2 x 29 in the 15.1 mm of slack between the two bays --
    # the gap nobody chose, which exists because the shell is as wide as the hip
    # clevises make it. tools/gate_f.py measures all four bounds.
    #
    # THE RESERVATION IS THE SLOT RATHER THAN THE COLUMN, and it stopped being the
    # column when a board was chosen: 12.1 held the whole gap because nothing had
    # been picked, and 9 is what the board occupies. The three millimetres either
    # side are where its own leads go.
    # THE BAY GOT 6 mm DEEPER when the connector panel went: its rear limit was
    # that panel's front face, and it is the shell wall itself now, less the same
    # 1.5 mm everything in this bay is held off its neighbours by. Nothing was
    # retyped -- both figures are derived, and both moved on their own.
    #
    # AND THE BAY IS GONE, 2026-10-05, with its guides and every name that sized
    # it: the board stands between the two battery packs, its power end at their
    # 65 mm body line, in one block with them. What is left is where it is.
    "bmsX": -35.55,
    "bmsY": 0.0,
    # ---- AND THE BOARD THAT WAS CHOSEN FOR IT, 2026-09-13 ------------------
    #
    # The Daly Li-ion NMC 6S 24V 20A, at its vendor specification table's own
    # figures: 58 long, 33 across, 8.2 over the components, 45 g. It was chosen
    # on two counts, neither of them its current rating -- which is nearly
    # irrelevant on a board wired charge-only and seeing 2.2 A. It BALANCES, at
    # 30 mA from 4.18 V per cell, and it FITS, which between them ruled out
    # everything else on the market: the 30 A boards in its own family are 75 mm
    # long, and the cheap generic 6S protection boards that would fit balance
    # nothing at all.
    "bmsBoardLength": 58.0,
    "bmsBoardHeight": 33.0,
    "bmsBoardThickness": 8.2,
    # THE BOARD HANGS FROM THE DECK, which is the one thing here that is not
    # obvious and is why these two are derived rather than typed. What stops a
    # card lifting out of a slot is the deck over its top edge, so it has to be
    # able to rise by LESS than the slot is deep. Stood on the cavity floor this
    # board leaves 8.5 mm of air under a 4 mm slot and falls out of its guides --
    # found the moment a real board replaced the full-height stand-in that was
    # drawn here while none had been chosen. So the top edge is set 1.5 mm under
    # the deck and the slot floor follows it down the board's own height.
    "bmsBoardTopZ": 0.5,
    "bmsBoardBottomZ": -32.5,
    # The two guides that hold it. THE SLOT IS NOW CUT TO THE WHOLE BOARD AND NOT
    # TO ITS PCB, which is the change a chosen board bought: 2.4 mm took a bare
    # 1.6 mm PCB edge and assumed nothing was soldered within a guide's width of
    # it, which was an assumption about a board nobody had and a way to find out
    # only after printing. 9 mm takes the 8.2 mm envelope however the components
    # fall, and the 0.8 left over is the foam shim that stops it rattling. They
    # stand BELOW the reserved bay, so nothing is designed through a payload
    # volume; the deck 1.5 mm over the board's top is what stops it lifting out.
    # Set in from each END OF THE BOARD rather than placed on the floor, which is
    # what they were while the board was a guess: 6 mm in from each end puts them
    # 46 mm apart under a 58 mm card and symmetric about it, where the IMU's
    # reservation had previously decided them at 35 mm apart and off centre.
    # ---- THE HARNESS GETS SOMETHING TO BE TIED TO, September 2026 ----------
    #
    # cad/limb.py: two arches on each limb's inboard face, one at each end of
    # the waist, each a block standing 4 mm off the plate with a tunnel under it
    # for a 2.5 mm cable tie. Nothing outside the pelvis anchored a lead before
    # them -- docs/BOM.md's adhesive tie mounts were bought for the torso floor,
    # and a limb that swings is not where to trust an adhesive pad.
    #
    # THE ARCH ADDS MATERIAL WHERE A SLOT WOULD HAVE REMOVED IT, which is the
    # first reason for the shape. A tie needs two slots to straddle a bundle,
    # and a 2 mm pair cut through the 40 x 6 waist takes a tenth of the section
    # it stands in and brings a notch with it, on the plate this project already
    # calls the weakest printed thing on the robot: roughly 30 N sideways at the
    # wheel down to 15 or 20. Anything standing ON the plate costs the section
    # nothing.
    #
    # AND IT IS ON THE INBOARD FACE, which is the second. These were ears in the
    # plate's own plane reaching 12 mm aft of the flank, which put the tie point
    # and the bundle on it outside the limb's own silhouette -- inside the
    # robot's only by the 4 mm the wheels and the torso's back stand proud of
    # them, which is a fall onto a flat floor and not a fall onto anything else.
    # On this face the whole run is inside the box the two limb plates and the
    # actuators make, and it is the side every connector on the leg is on. What
    # it costs is a print orientation: this face has to be uppermost on the bed.
    # gate B holds the volume, gate E counts the tunnels and gate F measures the
    # 3.4 mm between each arch and its own actuator.
    "limbTieArchHeight": 4.0,
    "limbTieArchLength": 10.0,
    "limbTieArchWidth": 6.0,
    "limbTieArchTunnel": 2.0,
    "limbTieArchLap": 1.0,
    "limbTieArchY": -10.0,
    "limbTieArchZ": 30.5,
    "limbTieSlotWidth": 3.5,
    # AND TWO MORE GUIDES HANGING OFF THE DECK, over the first two and cut to the
    # same slot. What they buy is not hold-down -- the plate 1.5 mm over the top
    # edge was already doing that -- but LATERAL SUPPORT AT THE FAR END: held only
    # at the bottom, a 33 mm card on 4 mm of engagement is a cantilever and its
    # top edge swings. They drop 4 mm and the board stands 2.5 mm up inside them,
    # so it is still free to rise its 1.5 mm without leaving them.
    # ---- THE ROBOT GETS SOMETHING TO BE HUNG FROM, September 2026 ---------
    #
    # cad/torso.py: a lug on each flank of the pelvis, near the top rim, with a
    # Ø6 eye through it. The robot hangs from the two of them on an overhead
    # rail while it is being developed, and a topple is caught before it
    # reaches the floor. docs/NOTES.md puts the fall at 2.85 J and the limb
    # that has to absorb it at 0.21 J, so this is protecting a failure the
    # project has already measured rather than one it is guessing at.
    #
    # THE LID COULD NOT CARRY IT, which is why this is on the shell. The four
    # cover bosses are the strongest anchorage on the box, each a corner column
    # merged into two walls, but their screws stand 4 mm inboard of the cavity
    # edge and cad/deck.py's electronics deck is 148.3 mm wide in a 149.1 mm
    # opening with 0.4 mm of drop clearance. Anything reaching those screws
    # overhangs the mouth and traps the deck, which is exactly the access that
    # running with the lid off is meant to buy.
    #
    # LONG FORE-AFT AND FLUSH WITH THE RIM, because the lug hangs the wall
    # rather than hanging off it: the load crosses into the wall and runs down
    # it to the floor the hip clevises are rooted in, and 30 mm of length feeds
    # it into 30 mm of the wall's width at once. The underside is relieved at
    # 45 degrees so the wall does not meet a square step. Nothing here is near
    # a limit -- at ten times the robot's weight the wall sees under 1 MPa
    # against 30 across the layers -- so every number is about where the load
    # goes and not how much of it there is.
    #
    # And the outboard face lands at +/-88.95 against wheels at +/-104, so the
    # lug never touches the floor first in the topple it exists to catch. That
    # is the test cad/limb.py's cable-tie arches were moved inboard to pass.
    # gate B holds the volume as a pure addition and gate E counts the eyes.
    "hoistLugLength": 30.0,
    "hoistLugProud": 12.0,
    "hoistLugHeight": 16.0,
    "hoistLugLap": 1.0,
    "hoistLugTaper": 5.0,
    "hoistLugHoleDiameter": 6.0,
    "hoistLugHoleInset": 6.0,
    "hoistLugHoleDrop": 8.0,
    # Both mouths of the eye, broken 45 degrees out to Ø8 IN THE PART rather
    # than by cad/finish.py. That pass takes outer edges only, so it never
    # sees the rim of a bore and left this one sharp; every other bore on the
    # robot is a seat or a clearance hole and wants it that way. This is the
    # one place a rope turns over a printed edge under load.
    "hoistLugEyeChamfer": 1.0,
    # THE HIP ARMS' BRACES, 2026-10-12, after the second PLA pelvis came off
    # the printer with all four hip arms broken at the floor, through the
    # 3 x 24 mm neck every version of the clevis has had. The inboard arms take
    # three ribs each under the floor, placed round the motor's rear screws; the
    # outboard arms, which the thigh swings inside and the flank continues, take
    # a buttress outside that stands no prouder than the bearing boss. None of
    # these is measured from anything: they are sized to the room the screws,
    # the key and the thigh leave, and cad/parameters.py carries that.
    "hipArmGussetReach": 12.0,
    "hipArmGussetDrop": 16.0,
    "hipArmGussetInnerY": 7.0,
    "hipArmButtressDrop": 8.0,
    "hipArmButtressRise": 8.0,
}


# Dimensions the port carried FAITHFULLY and that have since been CHANGED on
# purpose. Different from ADDED: the golden reference does hold these names, so
# both ends of the change are pinned here -- what the KCL said, and what cad/ now
# says. A value that matches neither is still a MISMATCH, so this records a
# decision without loosening the gate. The reason lives with the dimension in
# cad/parameters.py; the sentence here is the index entry.
CHANGED = {
    # ---- THE JOURNAL STANDS 6 mm PROUD, WHATEVER IT IS, September 2026 -------
    #
    # It was a Ø10 x 8 hardened dowel bonded 2.2 mm into a blind seat in the
    # limb's output disc, so its length was seat plus air plus bearing. It became
    # a printed stub, and then -- once it turned out that neither can be got into
    # the far bearing at all, the fork being one print 4.7 mm too narrow for the
    # motor and disc that have to enter it -- a bought sleeve fitted from outside
    # at the end. All three run in the same race in the same place, and this is
    # what stands PROUD of the disc: across the 1 mm of air and through the
    # bearing's 5 mm, ending flush with its outer face.
    "journalLength": (
        8.0,
        6.0,
        "the sleeve stands 6 mm proud of the disc where the dowel was 8 long",
    ),
    # Follows arithmetically. The forked rotor is still DRAWN BUT NOT FITTED and
    # nothing imports it, but it measures its rear journal off the front one's
    # length, so it moves with it rather than being left saying 8.
    "rearJournalCenterX": (
        -23.45,
        -24.45,
        "the forked rotor's rear journal follows the front one's length",
    ),
    # ---- THE TORSO GREW TO CARRY A BATTERY, September 2026 ------------------
    #
    # Twenty-three names and ONE decision. They are listed one by one rather than
    # waved through together because that is exactly what this register is for: a
    # value matching neither end is still a MISMATCH, so a second change to any of
    # these cannot hide inside the first.
    #
    # Only the first three are decisions in their own right. Every other line
    # follows from them arithmetically -- the shell's own stations, the cavity's,
    # the payload bands' -- and says which.
    #
    # A SECOND DECISION MOVED THE SAME NAMES, 2026-10-05: the packs were measured
    # on arrival and the battery's band went from 36 to 39, which made the torso
    # 89 where it was 86. Each value below is where cad/ stands after both, and
    # the reasons carry the totals.
    "wheeledTorsoHeight": (
        65.0,
        89.0,
        "the battery's 39 mm band and the 3 mm deck over it, which is 24 mm more "
        "interior than the tethered torso needed -- 21 until the measured packs "
        "took the band from 36 to 39. Derived and not chosen: "
        "cad/wheeled_parameters.py adds up what has to fit",
    ),
    "wheeledTorsoShellWidth": (
        125.0,
        153.9,
        "THE PAYLOAD NO LONGER SETS THIS. 125 held two boards lying flat, 135 "
        "the pack and a 38 mm power block of our own, 141 the pack and a bought "
        "50 x 50 distribution board -- and 136.2 mm of interior is still all the "
        "payload asks for. 153.9 is the hip clevis instead: twice the hip half-"
        "spacing plus the clevis's outboard face, so the shell's flank lands on "
        "the plane the saddle ends at rather than 6.45 mm inside it. The 12.9 mm "
        "is slack, and all of it falls in the gap between the two bays",
    ),
    "torsoShellDepth": (
        68.0,
        72.0,
        "the four ledges carrying the electronics deck stand 5 mm proud of the "
        "front and rear walls, right beside the packs. 68 leaves pack and ledge a "
        "tenth of a millimetre apart; 72 opens it to 1.6",
    ),
    "wheeledTorsoTop": (
        339.0,
        363.0,
        "the same 24 mm, on a floor that has not moved",
    ),
    "wheeledTorsoCenterHeight": (306.5, 318.5, "half of that 24 mm"),
    "wheeledTorsoInteriorFloorZ": (-29.5, -41.5, "torso-local, so half the height"),
    "floorZ": (-29.5, -41.5, "the same floor, as the payload layout reads it"),
    "torsoShellWidth": (125.0, 153.9, "cad/torso.py reading the width above"),
    "torsoInnerWidth": (120.2, 149.1, "the same width, less two walls"),
    "torsoInnerDepth": (63.2, 67.2, "the same depth, less two walls"),
    "interiorHalfWidth": (
        60.1,
        74.55,
        "half the cavity, as the payload layout reads it",
    ),
    "shellFloorZ": (-32.5, -44.5, "torso-local, so half the height"),
    "shellTopZ": (30.1, 42.1, "torso-local, so half the height"),
    "shellHeight": (62.6, 86.6, "that height, less the cover"),
    "cavityBottomZ": (-29.5, -41.5, "the inside face of the floor, torso-local"),
    "cavityLength": (61.6, 85.6, "the cavity between that floor and the lid"),
    "hipPitchZ": (
        -56.5,
        -68.5,
        "the hip axis in torso-local terms. THE JOINT HAS NOT MOVED: the axis is "
        "still 250 mm off the floor and the torso still sits one keep-out above "
        "it. What moved is the torso centre this is measured from",
    ),
    "saddleTopZ": (-20.5, -32.5, "the saddle plane, torso-local"),
    "lowerBandZ": (
        -20.5,
        -32.5,
        "the same plane, which is where the bottom band starts",
    ),
    "upperBandZ": (
        11.5,
        24.1,
        "the SBC now stands above a battery, a deck and the controller rather "
        "than above the controller alone, and since September 2026 it stands on "
        "M2.5 x 10 standoffs on the controller carrier, which put it 0.6 mm higher "
        "than the deck's 14 mm posts did",
    ),
    "capacitorZ": (
        -18.9,
        -27.9,
        "the bank stands on the power switch board, not on the bought one: a 16 "
        "mm can on the bought board would have been inside a board 8 mm above it. "
        "And that board stands where the bought one stood since 2026-10-07, on its "
        "nuts on the posts, so the cans came down 9.6 mm with it from -18.3",
    ),
    "capacitorDiameter": (
        16.0,
        10.0,
        "the size of the cans the bill actually buys. 16 x 25 was a reservation "
        "four times over, against two Panasonic EEU-FR1V471B that are 10 x 16, "
        "and it was holding the whole front of the power bay -- which is the "
        "power switch board now",
    ),
    "capacitorHeight": (
        25.0,
        16.0,
        "the same two cans, in the other axis",
    ),
    "powerX": (
        39.1,
        46.55,
        "still 2 mm off the right wall, which is where this bay has always been "
        "pinned. The wall went out 14.45 mm in two steps -- 8 for the bought "
        "board, 6.45 to meet the hip clevis -- and the bay went 14 wider, so it "
        "rides out with the wall",
    ),
    "controllerWidth": (
        76.0,
        140.0,
        "the logic BEC and the bus monitor moved onto the carrier, and the only "
        "air on this deck deep enough for the monitor is outboard of the SBC's "
        "right-hand posts, which is 67.45 mm from where this bay starts",
    ),
    "controllerX": (
        -20.1,
        -2.549999999999997,
        "still 2 mm off the left wall, and it has moved up onto the deck. It "
        "rides out with that wall for the same reason the power bay does, and "
        "its centre moved inboard when the bay went from 76 mm wide to 140",
    ),
    "powerWidth": (
        38.0,
        52.0,
        "a bought 50 x 50 distribution board where a 38 mm PCB of our own used to be",
    ),
    "powerDepth": (
        62.0,
        54.0,
        "the battery's depth rather than the old block's, so that both bays "
        "clear the deck's wall ledges by the same 1.6 mm",
    ),
    "powerHeight": (
        30.0,
        39.0,
        "the full height of a band the battery already sets, which costs "
        "nothing and gives the bank room it has still not been sized for",
    ),
    "statorPlateFlatOffset": (
        19.0,
        20.0,
        "the connector relief is cut flush with the limb's flank rather than on "
        "the housing's connector flat, because widening the waist to 40 mm had "
        "left the limb standing a millimetre proud of the relief",
    ),
    "plugInnerX": (
        22.95,
        21.75,
        "the plug reaches a millimetre past the floor of the disc's journal seat "
        "instead of stopping 0.2 mm short of it, which sealed a 16 mm3 void into "
        "every wheel adapter",
    ),
    "plugCenterX": (
        25.95,
        25.35,
        "follows plugInnerX: the plug's outer end has not moved",
    ),
    # ---- THE WHEEL'S SPIGOT AND CLAMP, 6 October 2026 -----------------------
    #
    # One decision and the names that follow from it. The spigot ran the hub's
    # whole width on the reading that the hub was bored Ø22 straight through; a
    # skate wheel's hub has a ridge between its two bearing seats, so the spigot
    # stops a millimetre short of it, and the Ø30 penny washer that lay on the
    # hub's face became a printed cap standing on the ridge (ADDED above).
    "wheelSpigotLength": (
        23.0,
        6.0,
        "the spigot fills the inboard bearing seat and stops a millimetre short "
        "of the hub's centre ridge, where it used to run the hub's width",
    ),
    "spigotOuterX": (
        47.95,
        30.95,
        "follows wheelSpigotLength",
    ),
    "spigotCenterX": (
        36.45,
        27.95,
        "follows wheelSpigotLength",
    ),
    "insertOuterX": (
        47.95,
        27.45,
        "the insert is pressed in from the motor side now and stops against a "
        "step 8.5 mm in from the adapter's back face, where it used to sit "
        "flush with the spigot's end",
    ),
    "wheelSpigotInsertDepth": (
        12.0,
        8.5,
        "the insert's pocket runs in from the motor side to the step it is "
        "pressed against: deep enough for the 8 mm the insert's drawing gives "
        "and half a millimetre clear of the back face",
    ),
    "insertInnerX": (
        35.95,
        18.95,
        "the insert's pocket opens on the disc's back face now, which is the "
        "side it is pressed in from",
    ),
    "washerInnerX": (
        48.95,
        47.95,
        "the washer is a plain M5 one lying on the cap's floor, inside the cap, "
        "where the penny washer lay on the hub's outer face",
    ),
    "washerOuterX": (
        50.95,
        49.45,
        "follows washerInnerX and the plain washer's 1.5 mm",
    ),
    "wheelClampWasherDiameter": (
        30.0,
        11.0,
        "a plain M5 washer, Ø11 as fastdep sells it, where the Ø30 penny washer "
        "nobody in India sells used to be",
    ),
    "wheelClampWasherThickness": (
        2.0,
        1.5,
        "the plain M5 washer's 1.5 mm, as fastdep lists it",
    ),
    # ---- THE IMU LEAVES THE FLOOR, 14 October 2026 ---------------------------
    #
    # Its reservation was 22 x 22 x 6 on the shell floor, room for any breakout
    # up to that size. The board is chosen and hangs under the deck now, and the
    # reservation is the board itself: its outline, and from the top of its
    # socket to the bottom of its chip.
    "imuWidth": (22.0, 10.5, "the board's own 10.5, see imuBoardWidth"),
    "imuDepth": (22.0, 10.0, "the board's own 10.0, see imuBoardDepth"),
    "imuHeight": (
        6.0,
        5.63,
        "socket 2.95, board 1.5 and chip 1.18: the board hanging under the deck",
    ),
}


def ported_values() -> tuple[
    dict[str, float], dict[str, str], dict[str, str], list[str]
]:
    """Every constant the cad/ package defines, and which module defined it."""
    sys.path.insert(0, str(ROOT))
    import cad  # noqa: F401

    clashes: list[str] = []
    numbers: dict[str, float] = {}
    colors: dict[str, str] = {}
    origin: dict[str, str] = {}

    for info in pkgutil.iter_modules([str(ROOT / "cad")]):
        module = importlib.import_module(f"cad.{info.name}")
        for name, value in vars(module).items():
            if name.startswith("_"):
                continue
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                # Two modules may legitimately define the same name -- the torso
                # and the electronics both derive saddleTopZ, from different
                # directions, and agreeing is the point. Two modules defining it
                # DIFFERENTLY is a real fault, and a flat dict would hide it, so
                # it is caught here rather than silently resolved by import order.
                if name in numbers and numbers[name] != float(value):
                    clashes.append(
                        f"  CLASH     {name}: cad/{origin[name]}.py says "
                        f"{numbers[name]!r}, cad/{info.name}.py says {float(value)!r}"
                    )
                numbers[name] = float(value)
                origin[name] = info.name
            elif isinstance(value, str) and value.startswith("#") and len(value) == 7:
                colors[name] = value.lower()
                origin[name] = info.name
    return numbers, colors, origin, clashes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="list the matches too")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail on UNPORTED as well; for the end of phase 1",
    )
    args = parser.parse_args()

    if not GOLDEN.exists():
        print(f"no golden reference at {GOLDEN.relative_to(ROOT)}", file=sys.stderr)
        print("run: uv run tools/capture_golden.py", file=sys.stderr)
        return 2

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    gold_numbers: dict[str, float] = golden["dimensions"]
    gold_colors = {
        k: "#" + "".join(f"{round(c * 255):02x}" for c in v)
        for k, v in golden["colors"].items()
    }

    numbers, colors, origin, clashes = ported_values()

    mismatch: list[str] = []
    extra: list[str] = []
    changed: list[str] = []
    unported: list[str] = []
    matched = 0

    for name, value in sorted(numbers.items()):
        if name in ADDED:
            if value != ADDED[name]:
                mismatch.append(
                    f"  MISMATCH  {name} (added after the port, see ADDED):"
                    f" expected {ADDED[name]!r}, cad says {value!r}"
                )
            else:
                matched += 1
            continue
        if name in RETIRED:
            extra.append(
                f"  RETIRED   {name} is back in cad/{origin[name]}.py"
                f" -- it belongs to the deleted walking robot"
            )
            continue
        if name in UNEVALUATABLE:
            if value != UNEVALUATABLE[name]:
                mismatch.append(
                    f"  MISMATCH  {name} (hand-checked, see UNEVALUATABLE):"
                    f" expected {UNEVALUATABLE[name]!r},"
                    f" cad says {value!r}  (cad/{origin[name]}.py)"
                )
            else:
                matched += 1
            continue
        if name not in gold_numbers:
            extra.append(f"  EXTRA     {name}  = {value!r}  (cad/{origin[name]}.py)")
            continue
        if name in CHANGED:
            was, now, _ = CHANGED[name]
            if gold_numbers[name] == was and value == now:
                matched += 1
                changed.append(f"  CHANGED   {name}  {was!r} -> {now!r}")
            else:
                mismatch.append(
                    f"  MISMATCH  {name} (changed on purpose, see CHANGED):"
                    f" expected {was!r} -> {now!r},"
                    f" kcl says {gold_numbers[name]!r} and cad says {value!r}"
                )
            continue
        if value != gold_numbers[name]:
            mismatch.append(
                f"  MISMATCH  {name}\n"
                f"              kcl {gold_numbers[name]!r}\n"
                f"              cad {value!r}   (cad/{origin[name]}.py)"
            )
        else:
            matched += 1
            if args.verbose:
                print(f"  ok        {name:<34} {value!r}")

    for name, value in sorted(colors.items()):
        # A colour added after the port is declared in ADDED like any other new
        # name. It had never come up until the battery arrived and two of them
        # did, and the rule is the same one: the migration invents nothing, so a
        # name the reference cannot hold is either a typo or a decision, and a
        # decision goes in the register with its reason.
        if name in ADDED:
            if value != ADDED[name]:
                mismatch.append(
                    f"  MISMATCH  {name} (added after the port, see ADDED):"
                    f" expected {ADDED[name]!r}, cad says {value!r}"
                )
            else:
                matched += 1
            continue
        if name not in gold_colors:
            extra.append(f"  EXTRA     {name}  = {value!r}  (cad/{origin[name]}.py)")
        elif value != gold_colors[name]:
            mismatch.append(
                f"  MISMATCH  {name}   kcl {gold_colors[name]}   cad {value}"
            )
        else:
            matched += 1

    for name in sorted(set(gold_numbers) | set(gold_colors)):
        if name in NOT_DIMENSIONS or name in RETIRED:
            continue
        if name in numbers or name in colors:
            continue
        unported.append(name)

    for line in clashes:
        print(line)
    for line in mismatch:
        print(line)
    for line in extra:
        print(line)
    for line in changed:
        print(line)

    # The two UNEVALUATABLE names are checked and counted as matches, but the
    # golden capture could not evaluate them so they are not in its key set.
    golden_names = set(gold_numbers) | set(gold_colors)
    total_golden = (
        len(golden_names - NOT_DIMENSIONS - RETIRED) + len(UNEVALUATABLE) + len(ADDED)
    )
    print()
    print(f"gate A: {matched}/{total_golden} live golden names matched exactly")
    print(f"        {len(RETIRED)} retired on purpose, correctly absent")
    print(f"        {len(ADDED)} added after the port, by name and with a reason")
    if changed:
        print(f"        {len(changed)} changed on purpose since the port:")
        for name, (was, now, why) in sorted(CHANGED.items()):
            print(f"          {name} {was!r} -> {now!r}: {why}")
    if unported:
        print(f"        {len(unported)} not ported yet:")
        for i in range(0, len(unported), 4):
            print("          " + "  ".join(f"{n:<30}" for n in unported[i : i + 4]))
    if mismatch:
        print(f"        {len(mismatch)} MISMATCH")
    if extra:
        print(f"        {len(extra)} EXTRA")

    if clashes:
        print(f"        {len(clashes)} CLASH")
    failed = bool(mismatch or extra or clashes) or (args.strict and bool(unported))
    print("        FAIL" if failed else "        pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
