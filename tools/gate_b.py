# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9"]
# ///
"""Gate B -- is the ported solid the same solid the Zoo engine built?

The load-bearing gate of docs/BUILD123D_MIGRATION.md. For each piece it imports
the golden STEP that KCL produced, builds the build123d part, and computes the
SYMMETRIC DIFFERENCE between them: the volume of (new - old) plus the volume of
(old - new). Two solids that occupy the same space difference to nothing.

    uv run tools/gate_b.py                   # every piece with a port
    uv run tools/gate_b.py joint-rotor-hub   # just one

Why symmetric difference and not volume. Matching volumes prove very little: a
part that is mirrored, or shifted 5 mm along its axis, or has a hole in the wrong
place, has exactly the volume it should. The symmetric difference is zero only if
every point inside one solid is inside the other.

Why the golden shells are unioned first. A KCL piece exports as several
interpenetrating bodies -- five for a limb, seven for the pelvis shell -- because
the engine would not union them. Adding their volumes counts every overlap twice,
so the reference here is the union, which is also what simulation/ resolves.

The tolerance. reference/golden/step round-trips through OCCT exactly -- STEP is
a BREP format and carries analytic surfaces, not a mesh -- so the noise floor
measured in task 0.3 was 0.0 on every piece. What is left is the difference
between two constructions of nominally the same shape, which shows up as thin
slivers along coincident faces. TOLERANCE is set well below anything that could
be a real feature and well above that.

Free, offline, no engine.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import build123d as bd

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "reference" / "golden" / "step"

sys.path.insert(0, str(ROOT))

# Relative to the part's own volume. A 1e-6 slice of the smallest piece here is
# under 0.01 mm3, which is far smaller than any feature the robot has.
TOLERANCE = 1e-6

# Absolute, for the deviations below, whose whole point is that they are a known
# number rather than a proportion.
DEVIATION_TOLERANCE_MM3 = 1e-3

# DELIBERATE DEPARTURES FROM THE GOLDEN REFERENCE.
#
# A piece listed here is EXPECTED to differ from what the Zoo engine built, by a
# stated amount, for a stated reason. This is not a way of silencing the gate --
# it is the opposite. An unlisted piece must match exactly; a listed one must
# differ by exactly the volume recorded here AND by nothing else. A change that
# removes the intended material and also moves something else fails, because the
# symmetric difference then exceeds what was declared.
#
# Each piece carries a LIST, one entry per change, because a piece accumulates
# them: the migration's discipline is one change, one measured delta, and adding
# a second correction must not blur the first one's figure into a net total that
# no longer says what either change did.
#
# ADDED AND REMOVED ARE DECLARED SEPARATELY, and that is what makes the "and
# nothing else" half of the check work. A net delta is not enough once a piece
# has changes of both signs -- the limb's connector relief adds 206 mm3 and its
# register pocket takes 11 away, and a gate that only knew the net +195 would
# have accepted any pair of numbers 195 apart. So the totals are checked twice
# over: the volume must move by (added - removed), and the symmetric difference
# must be exactly (added + removed), which is only true if nothing else moved.
#
# The golden STEPs are never regenerated to make a gate pass. They are the frozen
# record of what the KCL built, and an entry here is how the project says "we
# changed this on purpose, and here is how much".
DEVIATIONS = {
    "joint-rotor-hub": [
        {
            "removed_mm3": 4.2979372781,
            "why": (
                "the arm-root blend is now a true 1 mm fillet tangent to both "
                "faces, where the KCL's solver had built an unconstrained "
                "sqrt(8.5) = 2.9155 mm arc tangent to neither. Carries less "
                "material and relieves more."
            ),
        },
        {
            "removed_mm3": 8.9406906219,
            "why": (
                "the Ø30.4 register pocket is re-cut after the arm is unioned "
                "on. The arm's top face sits 14.18 mm below the joint axis, "
                "inside the pocket's own 15.2 mm radius, so the union had filled "
                "a 42 degree segment of it back in -- 11 mm wide and the pocket's "
                "full 1.2 mm deep -- and the actuator's Ø30 output register would "
                "have landed on that instead of in the pocket. Same class of "
                "failure as the six bolt holes, missed when those were caught, "
                "and it hid longer because a part-filled pocket still leaves one "
                "cylindrical face for gate E to count."
            ),
        },
    ],
    # Both hands of the limb, and the same two changes on each: the numbers are
    # one mirror image of the other and agree to 1e-5.
    "limb-105-unmirrored": [
        {
            "added_mm3": 92.2586125,
            "removed_mm3": 195.3062914,
            "why": (
                "THE DISC CARRIES THE JOURNAL'S ANCHOR, NOT THE JOURNAL. The "
                "golden's Ø10.2 x 2.2 blind seat took a bonded dowel; a printed "
                "Ø10 stub replaced it on 13 September 2026; and NEITHER CAN BE "
                "ASSEMBLED -- both stand proud of this face before the joint is "
                "closed, and the fork is one print whose cheeks are 4.7 mm closer "
                "together than the motor and this disc are long. So the journal "
                "is a bought sleeve fitted from outside at the end, and what is "
                "left here is what it screws into: the seat is not cut at all "
                "(92.3 mm3 of it is material the golden does not have) and a "
                "Ø5.5 clearance hole and the hex pocket for a captive M5 thin nut "
                "are cut from the motor side instead (195.3 mm3). The pocket is "
                "1.3 mm over the nut's flats rather than 0.3 because the "
                "finishing chamfer takes 0.5 mm off the floor's perimeter, which "
                "had left the nut seated on the chamfer. Both signs on one "
                "feature, so both are declared. cad/parameters.py carries the "
                "interference that forced it and what the anchor is worth against "
                "the stub -- which is less, and is said plainly there."
            ),
        },
        {
            "added_mm3": 206.3020897,
            "why": (
                "the stator plate's connector relief is cut flush with the "
                "waist's flank at 20 mm rather than on the housing's connector "
                "flat at 19 -- which flank is the entry below's business, and "
                "does not change this figure: the plate is a disc and the two "
                "segments are the same segment. Widening the waist from 30 mm "
                "to 40 in August 2026 "
                "had put the limb's edge a millimetre PROUD of the relief, which "
                "is the 1 mm step in the silhouette above the lower joint. See "
                "statorPlateFlatOffset in cad/parameters.py for why the "
                "millimetre is given to the plate rather than taken off the limb."
            ),
        },
        {
            "removed_mm3": 11.4582296,
            "why": (
                "the waist plate is cut clear of the Ø30.4 register pocket, "
                "which it filled a 45.8 degree segment of -- 11.8 mm across and "
                "the pocket's full depth. Same defect as the rotor hub's above, "
                "on the piece the wheeled robot actually prints."
            ),
        },
        {
            "added_mm3": 817.8668634,
            "removed_mm3": 817.8668634,
            "why": (
                "THE CONNECTOR RELIEF IS ON THE AFT FLANK NOW. The lower plate "
                "is reflected across YZ to bring it to the near side rather than "
                "spun half a turn about Z, which leaves its relief facing aft "
                "with the hip actuators' connectors and both floor ports into "
                "the pelvis, instead of forward and away from them. The two "
                "figures are the same number to 1e-5 mm3 and that is the check "
                "rather than the cost: the forward segment the relief used to "
                "take is filled back in and the identical segment is taken off "
                "the aft one, so if anything but the side of the cut had moved, "
                "they would differ. No material, no mass, one silhouette "
                "mirrored about the limb's own plane of symmetry."
            ),
        },
        {
            "added_mm3": 396.0000000,
            "why": (
                "two cable-tie arches, one at each end of the waist, standing "
                "4 mm off the limb's INBOARD face with a 3.5 x 2.0 tunnel under "
                "each for a 2.5 mm tie. 237 mm3 apiece as drawn, of which 39 is "
                "the millimetre it laps into the plate, so 198 each is material "
                "the golden does not have. Nothing outside the pelvis anchored a "
                "lead before this. They were ears in the plate's own plane for "
                "one revision, reaching 12 mm aft of the flank, and they moved "
                "to this face because that put the tie point and the bundle on "
                "it outside the limb's silhouette, where a doorway or a bench "
                "leg reaches them. A slot through the waist instead was never "
                "an option: it costs section on the plate that already breaks "
                "first. See cad/parameters.py."
            ),
        },
        {
            "added_mm3": 8.5686735,
            "why": (
                "the waist's two bottom corners carry down to where the Ø52 "
                "stator plate's rim has come out to the waist's own 20 mm. The "
                "end of the waist is held a cap head clear of the rear bolts, "
                "1.28 mm short of that, so the limb's outline dipped in to "
                "follow the rim and then stepped back out to the flank: a notch "
                "1.14 mm deep at each corner with the waist's end face showing "
                "as a ledge in the floor of it. Same class of accident as the "
                "1 mm silhouette step above, one corner away on the same joint, "
                "and found the same way -- by looking at the finished part."
            ),
        },
    ],
    "joint-stator-clevis": [
        {
            "added_mm3": 1280.3560859705,
            "why": (
                "the front cheek is bored Ø19.2 for the bearing itself, where it "
                "was bored Ø30.2 for a turned aluminium carrier that the bearing "
                "then sat in. The carrier was the only bespoke machined part on "
                "the robot and docs/BOM.md had no supplier for it, so it is "
                "deleted and the bearing is bonded into the print with the same "
                "retaining compound. The material is the annulus between the two "
                "bores through a 3 mm cheek, and it goes back INTO the cheek, "
                "which is the wall the joint's load crosses."
            ),
        },
        {
            "added_mm3": 918.4014153780,
            "why": (
                "the boss on the cheek's outer face that carries the bearing's "
                "shoulder: Ø26 x 3.5 mm, with the seat cut 2 mm into it and a "
                "Ø17.5 bore through the 1.5 mm that is left. A 3 mm cheek cannot "
                "seat a 5 mm bearing, so this is what makes the seat full depth "
                "and gives the race a face to sit against, which the deleted "
                "carrier's flange used to be. It stands proud of the pelvis at "
                "±77 mm and the wheels are at ±104, so it costs no envelope."
            ),
        },
    ],
    "pelvis-shell": [
        # A WHOLE-PART RESIZE, and it is a different kind of entry from every
        # other one in this register. The rest are features: a bore, a boss, a
        # relief, each a number you can go and measure on the part. This is the
        # box being a different box -- 125 x 68 x 65 tethered, 153.9 x 72 x 86
        # now -- plus the ten mounting features that came with the battery.
        #
        # IT IS ONE ENTRY COVERING TWO DECISIONS, which every other line in this
        # register would call a failure of discipline, and the reason is worth
        # stating rather than hiding. The battery resize took the box to
        # 141 x 72 x 86; taking the flank out to the hip clevis's own end plane
        # then took the width to 153.9. Against a FROZEN 125 mm reference those
        # two cannot be separated: the second change moves material that the
        # first change had already moved, so its own add and remove against the
        # golden are not the difference between the two entries -- asked for
        # separately it comes out as +4945.899 added and -977.109 removed, and a
        # negative removal is not a thing that can be written down. Folding is
        # the honest answer; splitting would have meant inventing a pair of
        # numbers that summed correctly and described nothing.
        #
        # BE CLEAR ABOUT WHAT IS AND IS NOT STILL BEING CHECKED. For a change of
        # this shape the two halves of the test can always be satisfied, because
        # any pair of numbers with the right sum and difference will do, and
        # these two were computed from the built part rather than derived from
        # intent. So this entry proves nothing about either DECISION. What it does
        # still do, and the reason it is written out to ten places rather than
        # waved through, is PIN THE RESULT: the next change to this part, however
        # small, breaks both sums at once and has to come back here. The decisions
        # themselves are checked elsewhere -- gate A holds every dimension that
        # moved against both of its values, gate E counts the new features on the
        # finished solid, and gate F measures the packing the height was derived
        # from.
        {
            "added_mm3": 127436.3830903076,
            "removed_mm3": 84174.3145427769,
            "why": (
                "the torso grew to carry a battery and then grew again to meet "
                "its own hip joints: 153.9 x 72 x 86 where it was 125 x 68 x 65. "
                "Sixteen millimetres of width for the pack and a bought 50 x 50 "
                "distribution board beside it, four of depth for the electronics "
                "deck's ledges, twenty-one of height for the packs and the deck "
                "over them, and then a further 12.9 of width to bring the flank "
                "out to the plane the hip saddle ends at, which is where the "
                "saddle had been standing 6.45 mm proud of its own wall. All of "
                "it derived in cad/wheeled_parameters.py -- the first three from "
                "what has to fit inside, the last from cad/joint.py. The added "
                "figure also carries the ten mounting features that came with the "
                "battery -- two battery rails, four posts under the distribution "
                "board and four deck ledges -- and the removed one carries the "
                "tether slot and its two cable-tie slots, which went when the "
                "umbilical did, and the material the two bays' posts and rails "
                "vacated when they rode outboard with the wall."
            ),
        },
        # THE ONLY NEGATIVE FIGURE IN THIS REGISTER, and it is not a typo. This
        # change takes 82.56 mm3 of wall out, and 71.5 of that is wall the resize
        # entry above had counted as ADDED -- the panel sits where the old 125 mm
        # box had no material at all -- so against the golden it shows up as
        # material un-added rather than material removed. The other 11.1 mm3 is
        # the sliver of the cut that does fall inside the old box's own rear wall,
        # and that is a removal like any other. Two figures rather than one
        # because the gate checks the volume and the symmetric difference
        # separately, and only this pair satisfies both.
        {
            "added_mm3": -71.5039978891,
            "removed_mm3": 11.0559978414,
            "why": (
                "the service panel now carries ONE 7-way balance port where it "
                "carried two 4-way ones, and a charge port beside them. Joining "
                "the two packs' balance tails inside the shell is what lets a "
                "charger see the single 6S pack they are wired as and finish in "
                "one session; the charge port is the other half of that decision, "
                "because the bus has to be dead while the cells charge and so the "
                "charger cannot come in through the disconnect. The arithmetic is "
                "three cuts through a 2.4 mm wall -- 20.5 x 8 and 12 x 7.2 in, "
                "two of 13.5 x 8 out -- which is 600.96 mm3 against 518.4."
            ),
        },
        # THE SECOND NEGATIVE ADDED FIGURE, and for exactly the reason the first
        # one carries: almost all of this change happens in the rear wall and in
        # the battery rails, and both of those stand where the old 125 x 68 x 65
        # box had no material at all. Cutting them shows up against the golden as
        # material UN-ADDED rather than material removed. The 152.4 mm3 that is a
        # genuine removal is the sliver of the three apertures falling inside the
        # old box's own rear wall, which overlaps the new one by 0.4 mm.
        #
        # The net is -862.36 mm3 and it is accounted for feature by feature:
        # three apertures where three precision cutouts were, four Ø3.4 fixings
        # through the wall, and four strap slots through the two battery rails
        # (-576.0), against two things this change ADDS -- the IMU's seat
        # (+132.0) and the two BMS card guides (+784.8). The apertures also moved
        # with the balance port when that rose 1.5 mm off the disconnect, which is
        # part of the same change.
        {
            "added_mm3": -698.7569845061,
            "removed_mm3": 163.6033622137,
            "why": (
                "EVERYTHING IN THE TORSO GETS A MOUNT. The rear wall's three "
                "precision cutouts are three coarse apertures now, because the "
                "connectors they passed were held by nothing: all three housings "
                "are constant-section prisms, so no cut in 2.4 mm of wall can "
                "capture one. They are bonded into cad/connector_panel.py "
                "instead, which lands on this wall's inner face and is screwed "
                "through it -- hence the four Ø3.4 fixings. The rails gained a "
                "strap slot each end, because docs/BOM.md buys two cinch straps "
                "for the packs and this shell gave them nothing to thread "
                "through; and the floor gained a three-rib seat for the IMU, "
                "which at 11 x 10 is too small to screw and is the one board "
                "whose orientation is half its worth, and two card guides for a "
                "6S BMS standing on edge in the gap between the two bays -- a "
                "bare PCB with no mounting holes, so its bottom edge drops into "
                "a 2.4 mm slot and the electronics deck over it stops it rising."
            ),
        },
        # A NEGATIVE REMOVED FIGURE, which is the third odd sign in this register
        # and the mirror of the two above it. This change puts material BACK: the
        # balance port's aperture is not cut any more, so 703.2 mm3 of rear wall
        # that the cad had been losing is present again. 107.84 of it stands
        # where the old 125 x 68 x 65 box had wall of its own -- the 0.4 mm the
        # two rear walls overlap by, across the 269.6 mm2 the aperture covered
        # that the disconnect's does not -- so against the golden that part reads
        # as material UN-REMOVED, hence the minus. The other 595.36 is in the
        # 28.9 mm the new box stands proud of the old, and reads as added.
        #
        # 703.2 is arithmetic and not a measurement: the aperture is the port's
        # opening plus a socket wall, an aperture gap and a seat all round --
        # 25.5 x 13 -- through 2.4 mm of wall, less the 11 x 3.5 of it the
        # disconnect's own aperture had already taken.
        {
            "added_mm3": 595.3600000000,
            "removed_mm3": -107.8400000000,
            "why": (
                "THE BALANCE PORT IS NOT IN THIS WALL ANY MORE. A 6S BMS now "
                "sits on the same seven cell taps inside the shell and balances "
                "the string on every charge, so a socket presenting those taps "
                "to the outside offered nothing the board already held -- and a "
                "second path to an unfused pack is a thing to insulate rather "
                "than a convenience. The wall keeps two connectors: the XT90-S "
                "that arms the robot, and the charge port that feeds the BMS "
                "with the bus dead. Everything downstream followed on its own, "
                "because cad/electronics.py's connectorOpenings() is what the "
                "aperture, the socket, the collar and the panel's outline are "
                "all derived from."
            ),
        },
        # THE CARD GUIDES WERE CUT TO A BOARD THAT DID NOT EXIST, and both things
        # wrong with them only became measurable when one was chosen. The Daly
        # 6S 20 A is 58 x 33 x 8.2 mm, and against it:
        #
        #   THE BOARD FELL OUT. A 33 mm card standing on the bay floor left its
        #   top edge 8.5 mm under the deck, and the deck is the whole of the
        #   hold-down -- lift it 4 mm and it clears a 4 mm slot with 4.5 to
        #   spare. The stand-in drawn here was full height, so it touched the
        #   deck and the defect could not show. The board now hangs 1.5 mm under
        #   the deck and the guides rise to meet it: 14.5 mm tall where they were
        #   7.5, and it can rise 1.5 mm while still 2.5 mm into its slot.
        #
        #   THE SLOT ASSUMED A BARE EDGE. 2.4 mm took a 1.6 mm PCB and assumed
        #   nothing was soldered within a guide's width of it. 9 mm takes the
        #   whole 8.2 mm board however its components fall, which needed the
        #   guides 12 mm wide rather than 10 to keep 1.5 mm of wall either side.
        #
        # +871.2 mm3 of material, and that much is arithmetic: two guides of
        # 12 x 6 x 14.5 less a 9 x 6 x 4 slot each is 1 656, against 10 x 6 x 7.5
        # less 2.4 x 6 x 4 each, which was 784.8. They also moved 46 mm apart and
        # symmetric under the card, from 35 mm apart and off centre, which the
        # IMU's reservation had decided when there was no board to set them to.
        #
        # IT SPLITS +439.2 / -432.0 AGAINST THE GOLDEN, and the reason is worth
        # writing down because it is not an error. The guides now rise through
        # z = -32.5 to -29.5, which is where the TETHERED torso's cavity floor
        # was: 12 x 6 x 3 of each guide stands in material the golden already
        # had, twice over, and material that was already there cannot be added
        # to it. So 1 224 of the 1 656 reads as added and 432 reads as material
        # the golden holds that this pelvis does not. The old guides stopped at
        # -32.5 and never reached that band, which is why the split is new.
        {
            "added_mm3": 439.2000000000,
            "removed_mm3": -432.0000000000,
            "why": (
                "THE BMS CARD GUIDES ARE CUT TO A CHOSEN BOARD. They were drawn "
                "to a class -- a bare 1.6 mm PCB of unknown height -- and a "
                "chosen board made two things measurable that had not been: a "
                "33 mm card stood on the bay floor lifts clear of a 4 mm slot "
                "before the deck stops it, and a 2.4 mm slot only works if "
                "nothing is soldered near the board's bottom edge. So the board "
                "now hangs 1.5 mm under the deck with the guides risen to meet "
                "it, and the slot takes its whole 8.2 mm envelope rather than "
                "the laminate inside it."
            ),
        },
        # THE FOURTH ODD SIGN IN THIS REGISTER, and by now the pattern is worth
        # stating once: almost everything that happens in this rear wall happens
        # where the old 125 x 68 x 65 box had no material at all. The two walls
        # overlap by 0.4 mm -- the golden's runs y -34.0 to -31.6 and this one
        # -36.0 to -33.6 -- so a sixth of any cut in it lands inside the golden
        # solid and five sixths outside. Material this change PUTS BACK therefore
        # reads as added where it is outside and as UN-REMOVED where it is
        # inside, which is the minus below.
        #
        # The net is +1022.28 mm3 and every part of it is arithmetic:
        #
        #   back in   the disconnect's old aperture   26.5 x 21.5 x 2.4  1367.40
        #             the charge port's old aperture  17.0 x 12.2 x 2.4   497.76
        #             four Ø3.4 panel fixings                             87.16
        #   cut out   the XT60E-M's nose              14.7 x  7.2 x 2.4  -254.02
        #             its two Ø2.4 ear holes                             -21.71
        #             the XT60E-F's body              19.2 x 12.0 x 2.4  -552.96
        #             its two Ø2.4 flange holes                          -21.71
        #             the SMA's Ø6.5 hole                                -79.64
        #
        # THE CHARGE SOCKET'S TWO LINES AND BOTH SCREW SIZES MOVED THIS ENTRY
        # AGAIN, the same month. The charge socket was a GX16's Ø16 hole at x 50
        # and is an XT60E-F's body at x 55.5, square, 19.2 x 12.0, with two
        # screws; the antenna crossed from x 68 to x -8; and the disconnect's ear
        # holes went from Ø2.8 to Ø2.4 when M2.5 nuts turned out not to fit beside
        # its body. THE SPLIT BELOW IS WHAT MAKES THAT MOVE WORTH WRITING DOWN:
        # the socket's cut runs from x 45.9 to 65.1 and the old box's flank is at
        # 62.5, so 2.6 mm of it is outside the band, and so are its outer screw
        # at x 68 and the antenna's old hole -- while the antenna's new one is
        # inside. Worked feature by feature that way, the two figures came out of
        # the arithmetic and matched the measured difference first time.
        #
        # THE DISCONNECT'S TWO LINES ARE WHY THIS ENTRY MOVED, September 2026,
        # and the movement is the whole point of having it. They read 25.0 x 16.0
        # and Ø3.4 while this wall was cut for an AMASS XT90E-M on a marketplace
        # listing's figures. Against the maker's own drawing that part is 42.0
        # across with its screws 32.4 apart and 19.7 mm of it inside the wall --
        # so the cut was wrong, the drilling was wrong, and the connector fouled
        # the SBC. What is here now is an XT60E-M, cut to its 14.20 nose rather
        # than to its body, and the wall keeps 720.01 mm3 it used to lose.
        #
        # Of that, 145.44 mm3 falls in the 0.4 mm the two walls share -- which
        # everything inside the old box's flank at |x| = 62.5 does, and the
        # charge socket's outermost 2.6 mm and its outer screw do not. It was
        # 38.47 while the disconnect was cut 25 x 16, and 158.47 while the charge
        # socket was still a GX16 and the antenna still stood outboard at x 68.
        {
            "added_mm3": 876.8341449586,
            "removed_mm3": -145.4414830802,
            "why": (
                "THE CONNECTOR PANEL IS GONE AND THE WALL CARRIES ITS OWN "
                "HOLES AGAIN. Three coarse apertures and four screw holes went "
                "back in, and what replaced them is one hole per bought part: a "
                "14.7 x 7.2 nose cut and two Ø2.4 ear holes for an AMASS "
                "XT60E-M disconnect, a 19.2 x 12.0 body cut and two Ø2.4 flange "
                "holes for its female twin the XT60E-F as the charge socket, and "
                "a Ø6.5 for an SMA antenna bulkhead. Every one of those parts "
                "retains itself -- ears or a flange bolted through the wall, or "
                "a shoulder and a nut clamping it -- which is what the 6 mm "
                "printed plate existed to do for connectors that could not. There "
                "is no bonded joint anywhere on this robot now. All three stand "
                "at z = 22, above the electronics deck, because below it this "
                "wall is committed end to end: the bus monitor comes within "
                "12.6 mm of it and the deck's own ledges stand on it."
            ),
        },
        {
            "added_mm3": 2560.7121719410,
            "why": (
                "the same bore, on the two hip pitch clevises the pelvis carries: "
                "exactly twice the clevis figure above, which is also the check "
                "that the added material lands in the cheeks and nowhere else."
            ),
        },
        {
            "added_mm3": 1836.8028307560,
            "why": (
                "the same shoulder boss, twice: exactly twice the clevis figure "
                "above again, on the two hips."
            ),
        },
        {
            "added_mm3": 368.3737348558,
            "removed_mm3": -232.9282582224,
            "why": (
                "TWO PADS ON THE REAR WALL FOR THE BUS MONITOR, which had been "
                "held by tape on the bought distribution board's top face until "
                "the vendor's own photographs turned out to show two mounting "
                "holes in it. Each pad is 6 x 6.5 x 8 with a Ø1.7 pilot 5 deep "
                "for an M2: 352.65 mm3 as drawn, 705.30 for the pair, and the "
                "part gains every one of those cubic millimetres. "
                "THE FIFTH ODD SIGN IN THIS REGISTER, for the reason the four "
                "above turn on. The golden's rear wall runs y -34.0 to -31.6 and "
                "these stand from y -33.6 forward, so 232.93 mm3 of them falls "
                "inside wall the old box already had and this one does not -- "
                "material UN-REMOVED rather than material added, which is why "
                "the two figures here are 368.37 and -232.93 and sum to the "
                "705.30 the pads actually weigh. "
                "THEY ARE ON THIS PART AND NOT ON THE DECK, where two posts "
                "carried the board for one revision: its leads run down into the "
                "bay, and the deck is the assembly that has to come straight out "
                "with nothing tethering it. And on the rear wall rather than the "
                "flank because the distribution board's edge is 3 mm off the "
                "flank, too little to hold a pilot without overhanging the "
                "bought board and trapping it on its standoffs; behind it there "
                "are 8.6 mm of floor nothing stands on."
            ),
        },
    ],
    # The lid, and this is the cleanest example of what a resize does to this
    # test: the figures below are EXACTLY the new lid's volume and exactly the
    # old lid's, because the two do not overlap at all. The shell's top face went
    # from 30.1 mm above the torso centre to 40.6, which is more than the lid is
    # thick, so the new one stands entirely clear of where the old one was. The
    # part is otherwise the same design at a new size -- cad/torso_shell.py's
    # torsoLid drawn to a 153.9 x 72 box instead of a 125 x 68 one.
    #
    # It also shows why the shell above had to fold its two resizes into one
    # entry and this one did not. The lid does not overlap the reference at all,
    # so widening it again adds material and removes none, and the second change
    # states its own figure cleanly.
    "torso-cover": [
        {
            "added_mm3": 45961.9353068376,
            "removed_mm3": 38281.9353068376,
            "why": (
                "the same lid on the same four bosses with the same lip and the "
                "same four screws, drawn to the taller, wider box the battery "
                "made of this pelvis. It shares no volume with the lid it "
                "replaces because the shell's top face moved further than the "
                "lid is thick."
            ),
        },
        {
            "added_mm3": 4297.2480000000,
            "why": (
                "the 12.9 mm the shell gained when its flank was taken out to "
                "the hip clevis's end plane, on a lid that is simply drawn to "
                "whatever box it closes: 12.9 mm of the lid's own 333.12 mm2 "
                "section, and nothing else about it changes."
            ),
        },
    ],
}
DEVIATIONS["limb-105-mirrored"] = DEVIATIONS["limb-105-unmirrored"]


def registry() -> dict[str, callable]:
    """Piece name -> the function that builds it. Grows as phase 1 lands.

    A builder may return a single solid or a list of interpenetrating bodies,
    which is what the printed pieces are while phase 1 lasts. Either is unioned
    before the comparison, the same way the golden shells are.
    """
    from cad import joint, shin, torso, wheel_adapter

    return {
        "joint-stator-clevis": joint.statorClevis,
        "joint-rotor-hub": joint.rotorHub,
        # THE SHIN IS THE PIECE THESE TWO NAMES NOW MEAN, and it is the same
        # solid they always meant. `limb-105-unmirrored` was the right thigh and
        # the left shin, one print serving both, because both leg segments are
        # 105 mm and both ended in a plate. Straddling the knee ends that: a
        # thigh finishes in a clevis and a shin still finishes in a plate, so
        # they are two pieces. The SHIN is the one that did not change -- it is
        # `limbAssembly(105)` exactly as it was -- so it keeps the name and the
        # golden STEP, and this gate goes on holding the geometry it always held.
        # The thighs are new pieces with no golden to be held against, like the
        # electronics deck, and gate E is what counts their features instead.
        "limb-105-unmirrored": shin.shinLeft,
        "limb-105-mirrored": shin.shinRight,
        "wheel-adapter-right": wheel_adapter.wheelAdapterRight,
        "wheel-adapter-left": wheel_adapter.wheelAdapterLeft,
        "pelvis-shell": torso.pelvisShell,
        "torso-cover": torso.torsoCover,
    }


def golden_union(path: Path):
    """The golden STEP with its interpenetrating shells resolved into one solid."""
    shape = bd.import_step(str(path))
    solids = shape.solids()
    part = solids[0]
    for extra in solids[1:]:
        part = part + extra
    return part, len(solids)


def volume_of(shape) -> float:
    if shape is None:
        return 0.0
    try:
        return abs(shape.volume)
    except (AttributeError, ValueError):
        return 0.0


def compare(name: str, build) -> tuple[bool, str]:
    step = GOLDEN / f"{name}.step"
    if not step.exists():
        return False, f"{name:<24} no golden STEP at {step.relative_to(ROOT)}"

    old, shells = golden_union(step)

    built = build()
    if isinstance(built, (list, tuple)):
        new = built[0]
        for body in built[1:]:
            new = new + body
    else:
        new = built

    sym = volume_of(new - old) + volume_of(old - new)
    rel = sym / old.volume

    changes = DEVIATIONS.get(name)
    if changes is None:
        ok = rel <= TOLERANCE
        note = ""
    else:
        # Two things have to hold: the volume moved by the stated amount, and
        # nothing moved that was not meant to. The second is the symmetric
        # difference matching added + removed -- if anything else changed, it
        # exceeds that.
        added = sum(c.get("added_mm3", 0.0) for c in changes)
        removed = sum(c.get("removed_mm3", 0.0) for c in changes)
        expected = added - removed
        actual = new.volume - old.volume
        moved_right = abs(actual - expected) <= DEVIATION_TOLERANCE_MM3
        confined = abs(sym - (added + removed)) <= DEVIATION_TOLERANCE_MM3
        ok = moved_right and confined
        if not moved_right:
            note = f"  <-- expected {expected:+.4f} mm3, got {actual:+.4f}"
        elif not confined:
            note = (
                f"  <-- {sym:.4f} mm3 changed, but only "
                f"{added + removed:.4f} was intended"
            )
        else:
            note = (
                f"  ({len(changes)} deviation(s): +{added:.4f} -{removed:.4f} mm3, "
                "as intended)"
            )

    ob, nb = old.bounding_box(), new.bounding_box()
    dbox = max(abs(getattr(nb.min, ax) - getattr(ob.min, ax)) for ax in ("X", "Y", "Z"))
    dbox = max(
        dbox,
        max(abs(getattr(nb.max, ax) - getattr(ob.max, ax)) for ax in ("X", "Y", "Z")),
    )

    verdict = "pass" if ok else "FAIL"
    line = (
        f"{name:<24} {shells:>2} shell(s)  kcl {old.volume:11.4f}  "
        f"cad {new.volume:11.4f}  sym {sym:10.4f} mm3  rel {rel:8.2e}  "
        f"dbox {dbox:7.4f} mm  {verdict}{note}"
    )
    return ok, line


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pieces", nargs="*", help="piece names; default is all ported")
    args = parser.parse_args()

    built = registry()
    wanted = args.pieces or sorted(built)

    failures = 0
    for name in wanted:
        if name not in built:
            print(f"{name:<24} not ported yet")
            failures += 1
            continue
        ok, line = compare(name, built[name])
        print(line)
        failures += 0 if ok else 1

    print()
    deviating = [n for n in wanted if n in DEVIATIONS]
    if deviating:
        print("deliberate departures from the golden reference:")
        for n in deviating:
            for change in DEVIATIONS[n]:
                moved = change.get("added_mm3", -change.get("removed_mm3", 0.0))
                print(f"  {n} {moved:+.4f} mm3: {change['why']}")
        print()
    print(
        f"gate B: {len(wanted) - failures}/{len(wanted)} pieces as expected "
        f"({len(wanted) - len(deviating)} identical to the engine's, "
        f"{len(deviating)} deliberately changed)"
    )
    print("        FAIL" if failures else "        pass")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
