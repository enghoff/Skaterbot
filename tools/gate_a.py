# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9"]
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
    # an XT90-S disconnect, a 6S balance port and a charge port, whose dimensions
    # are connector
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
    # M5 cap screw and the insert the spigot's bore was already cut for, except
    # the screw's LENGTH, which follows from the pocket: see the derivation in
    # cad/wheeled_parameters.py.
    "wheelClampScrewDiameter": 5.0,
    "wheelClampScrewLength": 12.0,
    "wheelClampSocketAcrossFlats": 4.0,
    "wheelClampSocketDepth": 2.5,
    "wheelClampWasherBore": 5.5,
    "wheelInsertLength": 9.5,
    "wheelInsertThreadDiameter": 4.5,
    # The stations those put on the axis, alongside the washerInnerX and
    # washerOuterX the KCL already named: where the head's outer face sits,
    # where the screw's tip stops, and the washer's mid-plane.
    "capHeadOuterX": 55.95,
    "screwTipX": 38.95,
    "washerCenterX": 49.95,
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
    # cad/parameters.py: heat-set inserts, for the board mounts and the deck's
    # SBC posts. Catalogue dimensions for the brass parts docs/BOM.md already
    # stocks; each bore is the insert's outside diameter, not its thread.
    "m25InsertBore": 3.2,
    "m25InsertDepth": 5.0,
    # cad/electronics.py: the pack, in TORSO axes rather than catalogue axes,
    # because the packs are stood on edge and the two frames do not agree. A
    # Gens Ace class 3S 2200 mAh brick is 76 x 33 x 25 and 144 g.
    "batteryPackLength": 76.0,
    "batteryPackThickness": 25.0,
    "batteryPackWidth": 33.0,
    "batteryPackGap": 2.0,
    "batteryWidth": 78.0,
    "batteryDepth": 54.0,
    "batteryHeight": 36.0,
    "batteryX": -33.55,
    "batteryLeadZ": -14.5,
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
    "pdbBoardZ": -28.0,
    "pdbTopZ": -26.4,
    "bayGap": 15.099999999999994,
    "panelX": 36.55,
    "packLeadZ": -9.399999999999999,
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
    "deckZ": 5.0,
    "deckBandZ": 8.0,
    "interiorHalfDepth": 33.6,
    "deckLedgeWidth": 12.0,
    "deckLedgeDepth": 5.0,
    "deckLedgeHeight": 5.0,
    "deckLedgeX": 52.0,
    "deckLedgeY": 31.1,
    "deckWidth": 148.29999999999998,
    "deckDepth": 66.4,
    "deckDropClearance": 0.4,
    "deckCornerNotch": 9.0,
    "controllerScrewX": 34.0,
    "controllerScrewY": 19.0,
    # Standoffs, and the plane each board therefore sits on. A reserved volume
    # says where a board may be and nothing about what holds it there; these are
    # the other half of that answer, and the KCL had none of them.
    "standoffHeight": 3.0,
    "standoffDiameter": 6.0,
    "sbcStandoffHeight": 2.0,
    "sbcStandoffDiameter": 5.0,
    "powerBoardZ": -28.0,
    "controllerBoardZ": 11.0,
    # The SBC's four posts, part of the deck print. Two pass THROUGH the
    # controller carrier, because 76 + 85 is more than the shell is wide however
    # the two boards are arranged.
    "sbcPostDiameter": 8.0,
    "sbcPostHeight": 14.0,
    "sbcPostClearance": 8.6,
    # Where the WeAct core board sits on the carrier, derived from the post that
    # crosses it rather than from the board it sits on. The posts cut the carrier
    # into two unequal pieces; this is the centre of the larger one. It is a
    # derived name rather than a placement because the shell's width now moves on
    # its own -- cad/wheeled_parameters.py builds it from the hip clevises -- and
    # a number typed into the drawing function would go stale in silence.
    "weActX": -52.775,
    # Bought electrical hardware at catalogue size, none of it in reference/:
    # connector shells and converter modules are commodity parts and every maker
    # builds them to the same table. The panel cutouts are cut to these, so they
    # are the figures to measure before the pelvis is printed.
    "xt60Length": 16.0,
    "xt60Width": 8.1,
    "xt60Height": 7.5,
    "xt90Length": 20.5,
    "xt90Width": 15.5,
    "xt90Depth": 21.0,
    # ONE 7-WAY BALANCE PORT WHERE THERE WERE TWO 4-WAY ONES, September 2026:
    # the packs' tails are joined inside the shell so a charger sees the 6S pack
    # they are wired as and charges it in a single session. 19.5 is the 7-pin
    # JST-XH shell against 12.5 for the 4-pin, and it is a catalogue-class figure
    # to be measured before the pelvis is printed, like every other moulding here.
    "balancePortWidth": 19.5,
    "balancePortHeight": 7.0,
    "balancePortDepth": 8.0,
    "balancePortOffset": 15.0,
    # The charge port that came with it: an XT30 across the pack, ahead of the
    # disconnect, so the cells can be charged with the bus dead. Charging through
    # the XT90-S would leave the actuators, the BEC and the SBC across the
    # charger, and a constant-voltage taper never falls below that load.
    "chargePortWidth": 11.0,
    "chargePortHeight": 6.2,
    "chargePortDepth": 15.0,
    "chargePortOffset": 24.0,
    "chargePortZ": -20.0,
    "dcdcWidth": 26.0,
    "dcdcDepth": 42.0,
    "dcdcHeight": 14.0,
    "busSenseWidth": 24.0,
    "busSenseDepth": 18.0,
    "busSenseHeight": 8.0,
    # The looms, reserved as chases rather than drawn as routed wire.
    "busWireDiameter": 3.5,
    "canWireDiameter": 2.6,
    "balanceLeadWidth": 6.0,
    "balanceLeadThickness": 2.0,
    "harnessBundleWidth": 9.0,
    "harnessBundleHeight": 7.0,
    "harnessRunY": -27.0,
    # cad/torso.py: what the pelvis grew to hold all of that. Two rails under the
    # packs, four posts under the power-entry board, and the service panel that
    # replaced the tether slot in the rear wall.
    "batteryRailThickness": 3.0,
    "batteryRailY": 20.0,
    "batteryRailEndX": 5.450000000000003,
    "boardPostSize": 8.0,
    "powerPostX": 22.5,
    "powerPostY": 22.5,
    "panelClearance": 0.5,
    "panelWallY": -34.8,
    "disconnectZ": -25.4,
    "disconnectPortWidth": 21.5,
    "disconnectPortHeight": 16.5,
    "disconnectPortZ": -17.65,
    "balancePortZ": -8.899999999999999,
    "balanceSlotWidth": 20.5,
    "balanceSlotHeight": 8.0,
    "balanceSlotZ": -5.399999999999999,
    "balanceSlotX": 15.0,
    "chargeSlotWidth": 12.0,
    "chargeSlotHeight": 7.2,
    "chargeSlotZ": -16.9,
    "chargeSlotX": 24.0,
    # Two colours, for the two things in the torso that are neither board nor
    # can: the cells themselves and the copper that leaves them.
    "cellGrey": "#4a4f57",
    "copperRed": "#a8452a",
}


# Dimensions the port carried FAITHFULLY and that have since been CHANGED on
# purpose. Different from ADDED: the golden reference does hold these names, so
# both ends of the change are pinned here -- what the KCL said, and what cad/ now
# says. A value that matches neither is still a MISMATCH, so this records a
# decision without loosening the gate. The reason lives with the dimension in
# cad/parameters.py; the sentence here is the index entry.
CHANGED = {
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
    "wheeledTorsoHeight": (
        65.0,
        86.0,
        "the battery's 36 mm band and the 3 mm deck over it, which is 21 mm more "
        "interior than the tethered torso needed. Derived and not chosen: "
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
        360.0,
        "the same 21 mm, on a floor that has not moved",
    ),
    "wheeledTorsoCenterHeight": (306.5, 317.0, "half of that 21 mm"),
    "wheeledTorsoInteriorFloorZ": (-29.5, -40.0, "torso-local, so half the height"),
    "floorZ": (-29.5, -40.0, "the same floor, as the payload layout reads it"),
    "torsoShellWidth": (125.0, 153.9, "cad/torso.py reading the width above"),
    "torsoInnerWidth": (120.2, 149.1, "the same width, less two walls"),
    "torsoInnerDepth": (63.2, 67.2, "the same depth, less two walls"),
    "interiorHalfWidth": (
        60.1,
        74.55,
        "half the cavity, as the payload layout reads it",
    ),
    "shellFloorZ": (-32.5, -43.0, "torso-local, so half the height"),
    "shellTopZ": (30.1, 40.6, "torso-local, so half the height"),
    "shellHeight": (62.6, 83.6, "that height, less the cover"),
    "cavityBottomZ": (-29.5, -40.0, "the inside face of the floor, torso-local"),
    "cavityLength": (61.6, 82.6, "the cavity between that floor and the lid"),
    "hipPitchZ": (
        -56.5,
        -67.0,
        "the hip axis in torso-local terms. THE JOINT HAS NOT MOVED: the axis is "
        "still 250 mm off the floor and the torso still sits one keep-out above "
        "it. What moved is the torso centre this is measured from",
    ),
    "saddleTopZ": (-20.5, -31.0, "the saddle plane, torso-local"),
    "lowerBandZ": (
        -20.5,
        -31.0,
        "the same plane, which is where the bottom band starts",
    ),
    "upperBandZ": (
        11.5,
        22.0,
        "the SBC now stands above a battery, a deck and the controller rather "
        "than above the controller alone",
    ),
    "capacitorZ": (
        -18.9,
        -26.4,
        "the saddle plane, plus the 3 mm standoff the power-entry board now "
        "stands on, plus the board's own thickness",
    ),
    "powerX": (
        39.1,
        46.55,
        "still 2 mm off the right wall, which is where this bay has always been "
        "pinned. The wall went out 14.45 mm in two steps -- 8 for the bought "
        "board, 6.45 to meet the hip clevis -- and the bay went 14 wider, so it "
        "rides out with the wall",
    ),
    "controllerX": (
        -20.1,
        -34.55,
        "still 2 mm off the left wall, and it has moved up onto the deck. It "
        "rides out with that wall for the same reason the power bay does",
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
        36.0,
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
