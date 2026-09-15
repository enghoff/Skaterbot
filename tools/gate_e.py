# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9"]
# ///
"""Gate E -- the features that must exist, counted on the finished solid.

This is the gate the migration CREATES rather than one it has to pass, and it is
the answer to the rule in CLAUDE.md that a boolean which succeeds is not a
boolean that worked. The rotor hub carried four filled bolt holes through several
rebuilds, on the joint that takes the actuator's full torque, and nothing
reported it: the KCL executed, the mass looked right, and the only evidence
available was a render taken down the feature's axis with nothing behind it.

Here the finished part is an object with faces, so the question is arithmetic. A
Ø3.4 through-hole leaves a cylindrical face of radius 1.7; six of them leave six.
A hole that a union filled back in leaves none, and this fails.

COUNTING IS NOT ALWAYS ENOUGH, and the second check exists because counting was
not. A pocket a union has eaten a SEGMENT out of still leaves one face at the
right radius, so it passes the count while the thing it locates no longer fits.
Features that have to be whole rather than merely present are listed separately,
in complete_pockets(), and are checked by how far round the circle actually goes.

    uv run tools/gate_e.py                   # every ported piece
    uv run tools/gate_e.py joint-rotor-hub   # just one

These assertions are written against the DRAWING INTENT, not against the golden
reference, so unlike gates A to D they can fail on a part that is a faithful
translation. That is the point: a gate E failure on a piece that passes gate B
means the KCL was wrong and the finding stands on its own. Record it and fix it
in phase 3.

WHAT BELONGS IN HERE, AND WHAT DOES NOT. Assert HOLES, BORES AND POCKETS --
features a boolean can silently fill back in, which is the failure this gate
exists to catch. Do not assert rims and outside diameters. Nothing fills a rim,
and a rim's FACE COUNT is not a property of the design: whatever crosses it
splits it. The clevis makes the point twice over -- the Ø52 cheek rim survives as
one face on the front cheek, and as two on the rear, where the connector flat cuts
it -- so an assertion about how many rim faces there are would be encoding
topology rather than intent, and would break the next time the flat moved.

Free, offline, no engine.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_SurfaceType

# The parts carry Ø in their feature names and Windows consoles default to a
# codepage that cannot print it.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Radii are compared to this many decimal places before being counted, so that a
# Ø3.4 hole and a Ø3.4000001 hole are the same hole.
PLACES = 4


def open_arc(part, radius: float) -> float:
    """How much of the circle at `radius` is still open, in degrees.

    WHY COUNTING FACES IS NOT ENOUGH, learned the hard way twice. A bore that a
    union has eaten a segment out of still leaves ONE cylindrical face at the
    right radius, so the count above passes it. Both the limb's waist plate and
    the rotor hub's arm reach far enough into the rotor disc to fill part of the
    Ø30.4 register pocket, and both did, for as long as the parts have existed:
    314 and 318 degrees open instead of 360, with the actuator's Ø30 register due
    to land on what was left. Nothing said so until the angular span was asked
    for.

    So this is the assertion for a pocket that has to be COMPLETE rather than
    merely present, and it is summed over faces because a boolean is free to
    split one cylinder into several.
    """
    from math import degrees

    total = 0.0
    for face in part.faces():
        surface = BRepAdaptor_Surface(face.wrapped)
        if surface.GetType() != GeomAbs_SurfaceType.GeomAbs_Cylinder:
            continue
        if round(surface.Cylinder().Radius(), PLACES) != round(radius, PLACES):
            continue
        total += surface.LastUParameter() - surface.FirstUParameter()
    return degrees(total)


def cylinder_radii(part) -> Counter:
    """How many cylindrical faces of each radius the finished solid carries.

    The radius is read off the underlying surface rather than from
    Face.radius, which returns None for a face a boolean has trimmed --
    and a trimmed face is exactly what a hole through a curved rim, or a
    cheek cut on the connector chord, leaves behind. Those are the faces
    this gate most needs to see, so the convenience property is not enough.
    """
    found: Counter = Counter()
    for face in part.faces():
        surface = BRepAdaptor_Surface(face.wrapped)
        if surface.GetType() != GeomAbs_SurfaceType.GeomAbs_Cylinder:
            continue
        found[round(surface.Cylinder().Radius(), PLACES)] += 1
    return found


def expectations() -> dict[str, list[tuple[str, float, int]]]:
    """piece -> [(what it is, the radius that proves it, how many), ...]

    Each row is a feature the part must have, named so a failure reads as a
    sentence rather than as a number.
    """
    from cad.electronics import (
        antennaHoleDiameter,
        sbcHoleDiameter,
        sbcStandoffHole,
    )
    from cad.parameters import (
        bearingSeatBossDiameter,
        bearingSeatDiameter,
        bearingSeatShoulderBore,
        journalScrewClearance,
        journalSeatDiameter,
        m2Clearance,
        m3CapCounterbore,
        m3Clearance,
        rotorFilletRadius,
    )
    from cad.torso_shell import bossHoleDiameter

    rows = {
        "joint-rotor-hub": [
            # The six that were filled. This is the whole reason the gate exists.
            ("M3 clearance holes on the Ø24 output circle", m3Clearance / 2, 6),
            ("cap counterbores over them", m3CapCounterbore / 2, 6),
            ("Ø10.2 journal seat", journalSeatDiameter / 2, 1),
            # Not a hole, and the one exception to the rule below. It is here
            # because this blend was wrong for as long as the part existed -- the
            # KCL's solver left the arc's centre unconstrained and built radius
            # 2.9155 where the parameter said 1 -- and nothing measured it. A
            # radius IS a property of the design, unlike a rim's face count, so
            # asserting it is meaningful and it stays asserted.
            ("arm-root blend, tangent both faces", rotorFilletRadius, 1),
        ],
        "joint-stator-clevis": [
            ("M3 clearance holes on the Ø41 rear pattern", m3Clearance / 2, 4),
            (
                "Ø19.2 bearing seat in the front cheek",
                bearingSeatDiameter / 2,
                1,
            ),
            # The seat is 5 mm deep and the cheek is 3, so both of these are
            # the boss that makes up the difference. If a rebuild ever unions the
            # boss on AFTER the seat is cut, the seat fills back in and the
            # shoulder bore is the only cylinder left -- so they are asserted
            # together on purpose.
            (
                "Ø17.5 shoulder the bearing seats against",
                bearingSeatShoulderBore / 2,
                1,
            ),
            (
                "Ø26 boss carrying that shoulder",
                bearingSeatBossDiameter / 2,
                1,
            ),
        ],
        # The limb is the piece the wheeled robot actually prints, and it is here
        # because the register pocket defect bit it as well as the hub, back when
        # there was a register pocket. Its
        # ten M3 holes are the six on the Ø24 output circle plus the four on the
        # Ø41 rear pattern, which are the same clearance and so the same radius.
        #
        # `limb-105` MEANS THE SHIN NOW. Both leg segments are still 105 mm, but
        # the thigh ends in a clevis and the shin in a plate, so they are two
        # pieces; the shin is the one that did not change and it keeps the name.
        # The thigh's own row is below, and its whole reason for being there is
        # that it carries three features this one does not.
        "limb-105-unmirrored": [
            (
                "M3 clearance holes, six on the output circle and four on the rear",
                m3Clearance / 2,
                10,
            ),
            ("cap counterbores over the output six", m3CapCounterbore / 2, 6),
            # WHAT THE JOURNAL SCREWS INTO. There was a Ø10.2 seat here for a
            # bonded dowel, and then a Ø10 stub printed with the disc, and
            # neither could be got into the far bearing at all -- the fork is one
            # print and the motor with this disc bolted on is 4.7 mm too long to
            # enter it. So the journal is bought and fitted from outside, and
            # what has to be on this piece is the hole its screw passes through.
            # The nut's pocket has no arc in it and is asserted as an opening
            # below, in panel_openings(), for the same reason the tie tunnels
            # are: a pocket closed back over leaves nothing here to count.
            ("Ø5.5 clearance for the journal screw", journalScrewClearance / 2, 1),
        ],
        # The payload boards are not printed, and they are here anyway. They are
        # mocks, but they are mocks that a printed standoff is going to be drawn
        # against, and they are built the one way this gate exists to police --
        # a slab with holes cut in it, standing in a list beside the components
        # that sit on top of it. Union one of those components on by accident and
        # the holes fill back in exactly as the rotor hub's did, with nothing to
        # report it but this count.
        # THE BOUGHT BOARD, and it is here for a reason the others are not: its
        # four holes are the only thing on this robot that a printed feature has
        # to agree with and that NOBODY HERE CHOSE. cad/torso.py stands four
        # posts on a 45 mm square because a datasheet says so, and if the board
        # is ever swapped for another the posts move with it. Counting them on
        # the drawn board is what keeps the two in step.
        "pcb-distribution": [
            ("M3 clearance holes on the datasheet's 45 mm square", m3Clearance / 2, 4),
        ],
        "pcb-controller-carrier": [
            # SIX, where this row said four corners until September 2026: the
            # board is screwed down at six stations, and the drawn board was
            # only drilled at the four corners until this count asked.
            ("M3 clearance holes, the six it is screwed down by", m3Clearance / 2, 6),
            # The SBC's four standoffs. Asserted separately from the six above
            # and not merely counted with them, because they are a different
            # diameter and a different job: lose these and the SBC has nothing
            # to stand on, while the board still looks right.
            #
            # THEY WERE Ø8.6 CLEARANCES FOR THE DECK'S POSTS until the SBC moved
            # onto standoffs on this board, and before that there were two.
            (
                "Ø2.7 holes for the SBC's four standoff screws",
                sbcStandoffHole / 2,
                4,
            ),
        ],
        "pcb-sbc": [
            (
                "Ø2.75 mounting holes on the Pi Zero 58 x 23 pattern",
                sbcHoleDiameter / 2,
                4,
            ),
        ],
        # THE PELVIS, asserted here for the first time. It had nothing in this
        # gate while its only round features were the two bearing seats its
        # clevises bring with them, and those are already counted on the clevis
        # itself. The battery gave it ten mounting features of its own, every one
        # of them a pilot hole in a body that stands in a list beside sixteen
        # others -- which is precisely the arrangement that filled the rotor
        # hub's six bolt holes back in. Four of the eight are under the
        # power-entry board and four carry the electronics deck.
        #
        # Each clevis contributes its own bearing seat, shoulder and boss, so
        # those come in twos here where they come in ones on the clevis.
        "pelvis-shell": [
            # Twelve at this radius, not eight: the four cover bosses have
            # carried the same Ø2.5 pilot since the pelvis was first drawn, and
            # they are on the same part. Counting only the new eight would fail
            # the moment anyone looked, so all twelve are named here.
            (
                "pilots: four cover bosses, four power-entry posts, four deck ledges",
                bossHoleDiameter / 2,
                12,
            ),
            # There were two more pilots here, Ø1.7 in two pads for the bus
            # monitor's M2 screws. The monitor went onto the controller carrier
            # in September 2026 and the pads came off this part with it.
            ("Ø19.2 bearing seats, one per hip", bearingSeatDiameter / 2, 2),
            (
                "Ø17.5 shoulders the bearings seat against",
                bearingSeatShoulderBore / 2,
                2,
            ),
            ("Ø26 bosses carrying those shoulders", bearingSeatBossDiameter / 2, 2),
            # Eight, not ten: the two Ø41 rear patterns carry eight between them
            # and nothing else on this piece is an M3 clearance any more. It was
            # twelve while a printed connector panel hung on four screws and ten
            # while the disconnect's two ear screws were M3; the rear wall's
            # screws are M2 now and are counted separately below, because a
            # wrong size is exactly what this gate is for.
            ("M3 clearances: two Ø41 rear patterns", m3Clearance / 2, 8),
            # THE TWO XT60s' FOUR SCREWS, the only M2 on the robot. Four and not
            # two: a pair 20.00 apart for the disconnect and a pair 25.00 apart
            # for the charge socket, each 1.45 or 1.7 mm from the edge of its
            # own cutout. If one of those bridges ever closes, that pair merges
            # into its cutout and this reads two rather than four.
            ("M2 clearances: two XT60E-M ear screws, two XT60E-F", m2Clearance / 2, 4),
            # THE ANTENNA'S BUSHING, counted here rather than as an opening below
            # because a round hole leaves a cylindrical face and this is what
            # reads those. One: a hole that closed back over would leave none,
            # and a hole cut twice would leave two. The charge socket's Ø16 hole
            # used to be counted beside it; the XT60E-F is cut square and is
            # asked about as an opening instead.
            ("Ø6.5 for the SMA antenna bulkhead", antennaHoleDiameter / 2, 1),
        ],
        # THE ELECTRONICS DECK, which is the one piece on this robot with no
        # golden STEP behind it -- the KCL never had it, so gate B cannot say
        # anything about it and this is the only arithmetic it answers to.
        "electronics-deck": [
            ("M3 clearances onto the four wall ledges", m3Clearance / 2, 4),
            (
                # Six since September 2026, where it was four: the carrier
                # went to 140 mm and its screws are a table in
                # cad/electronics.py rather than a corner pattern.
                "pilots under the controller's standoffs",
                bossHoleDiameter / 2,
                6,
            ),
            # The four SBC posts and the M2.5 insert bores in their tops were
            # counted here until September 2026. The SBC stands on standoffs on
            # the controller carrier now, and the posts are not printed.
        ],
    }
    rows["limb-105-mirrored"] = rows["limb-105-unmirrored"]

    # THE THIGH, WHICH IS THE SHIN'S TEN HOLES PLUS THE STRADDLE'S THREE. The
    # four rear bolts are in a 3 mm cheek now rather than through a 6 mm plate,
    # which changes nothing this gate can see; what is new is the far cheek's
    # bearing seat, the shoulder it lands on and the boss that carries it, and
    # those are here for exactly the reason they are on joint-stator-clevis. The
    # seat is 5 mm deep in a 3 mm cheek, so it only exists because the boss is
    # unioned on BEFORE it is cut. Union it after -- which is the one ordering
    # this project has actually shipped wrong -- and the seat fills back in,
    # leaving the shoulder bore as the only cylinder of the three. Asserting all
    # three together is what makes that visible.
    #
    # There is no golden STEP for a thigh, so unlike the shin this piece has
    # nothing in gate B to fall back on. This count is the whole of its
    # arithmetic.
    from cad.parameters import (
        bearingSeatBossDiameter,
        bearingSeatDiameter,
        bearingSeatShoulderBore,
    )

    rows["thigh-105-unmirrored"] = [
        *rows["limb-105-unmirrored"],
        (
            "Ø19.2 bearing seat in the knee clevis's front cheek",
            bearingSeatDiameter / 2,
            1,
        ),
        ("Ø17.5 shoulder the bearing seats against", bearingSeatShoulderBore / 2, 1),
        ("Ø26 boss carrying that shoulder", bearingSeatBossDiameter / 2, 1),
    ]
    rows["thigh-105-mirrored"] = rows["thigh-105-unmirrored"]
    return rows


def complete_pockets() -> dict[str, list[tuple[str, float]]]:
    """piece -> [(what it is, the radius that must be a WHOLE circle), ...]

    Features that have to be complete and not merely present, because something
    is going to be piloted in them. See open_arc() for what filled them in.

    EMPTY, AND THAT IS A DESIGN CHANGE RATHER THAN A GAP. The only entry this
    ever had was the Ø30.4 register pocket, on all five pieces that carry an
    output plate, and the pocket is retired: the plate lands flat on the
    actuator's Ø30 register and pilots on nothing. cad/parameters.py says why
    where its dimensions used to be declared. What replaced the check is in
    panel_openings() below -- the register needs a clear millimetre in front of
    the plate now rather than a clear pocket in it, and that is the assertion
    that matters.

    The machinery stays because the question it answers -- is this locating
    feature all the way round, or has a union eaten a segment out of it -- is
    the one that caught the defect, and the next pilot drawn on this robot wants
    asking it on the day it is drawn.
    """
    return {}


def panel_openings() -> dict[str, list[tuple]]:
    """piece -> [(what it is, centre, the box the opening must clear, axis), ...]

    RECTANGULAR CUTS, WHICH cylinder_radii() CANNOT SEE AT ALL. A rectangular
    cutout leaves four planar faces and not one arc, so a wall that closed back
    over one would pass every assertion above it in this file. The round holes in
    this wall are counted above, where their cylindrical faces can be; what is
    left for here is the two cuts that have no arc in them at all -- the
    XT60E-M's nose and the XT60E-F's body -- and the chase through the
    electronics deck.

    Each opening is asked two questions rather than one -- is it empty, and is
    there material round it -- because an opening drawn off the end of a part
    would answer the first perfectly and mean nothing.

    THE DECK'S CHASE IS ASKED A WEAKER SECOND QUESTION, and deliberately: it is a
    notch in the plate's rear edge rather than a hole in the middle of it, so
    there is material on three sides and open air on the fourth. The frame test
    is given the three, which is the whole of what holds it.

    THE LIMB'S TIE TUNNELS ARE HERE FOR THE SAME REASON, and they are why each
    row now carries the axis it is pierced along -- theirs runs across the limb
    rather than through a wall. They are the whole of what a harness can be tied
    to outside the pelvis, each is a gap under an arch that is unioned into the
    piece afterwards, and an arch drawn a millimetre lower would close one
    without leaving an arc for cylinder_radii() to find.
    """
    from cad.deck import deckChaseDepth, deckChaseWidth, deckChaseX, deckThickness
    from cad.electronics import deckZ, interiorHalfDepth, panelWallY, rearWallCutouts
    from cad.hardware import journalInnerX
    from cad.parameters import (
        actuatorOutputProjection,
        actuatorOutputRegister,
        journalLength,
        journalNutPocketDepth,
        limbTieArchTunnel,
        limbTieArchWidth,
        limbTieArchY,
        limbTieArchZ,
        limbTieArchZClevis,
        limbTieSlotWidth,
        rotorHubInnerX,
        shellWall,
        upperLegLength,
    )

    pelvis = [
        (
            f"{what}: its own cut in the rear wall",
            (atX, panelWallY, atZ),
            (width, shellWall, height),
        )
        for what, atX, atZ, width, height in rearWallCutouts()
        if width != height
    ]

    deck = [
        (
            "cable chase through the electronics deck",
            (
                deckChaseX,
                -(interiorHalfDepth) + (deckChaseDepth / 2),
                deckZ + (deckThickness / 2),
            ),
            (deckChaseWidth, deckChaseDepth, deckThickness),
        )
    ]

    # The two ends do not use the same station on a thigh. A clevis puts a closed
    # saddle box where the plate end's 30.5 mm arch would stand, so that arch
    # moves out to limbTieArchZClevis -- and an arch inside a saddle is exactly
    # the failure this test exists for, a tunnel with the piece closed over it.
    def tieTunnels(hand: int, lowerStation: float) -> list:
        return [
            (
                f"cable-tie tunnel, {end} arch",
                (
                    hand * (rotorHubInnerX - limbTieArchTunnel / 2),
                    limbTieArchY,
                    side * (upperLegLength / 2 - station),
                ),
                (limbTieArchTunnel, limbTieArchWidth, limbTieSlotWidth),
                "Y",
            )
            for end, side, station in (
                ("rotor-end", 1, limbTieArchZ),
                ("stator-end", -1, lowerStation),
            )
        ]

    # THE JOURNAL'S NUT POCKET, which is a hexagon and so has no arc anywhere in
    # it for cylinder_radii() to find. It is cut from the disc's motor side and
    # the nut has to be in it before the disc goes onto the actuator, so a pocket
    # that closed over -- or was never cut, the waist plate reaching into this
    # disc as it reaches into the register pocket beside it -- would leave the
    # joint with nothing to screw its journal into and nothing here to say so.
    # The probe is a 5.5 mm square, which fits inside the hexagon's 8.3 mm across
    # its flats whichever way round the nut went in.
    #
    # It starts at rotorHubInnerX and not rotorRegisterDepth outboard of it,
    # because the pocket's mouth IS that face now: the register pocket is cut on
    # the inboard side of it, so the nut pocket opens straight onto the plane the
    # actuator's output register lands on. See cad/parameters.py beside
    # actuatorOutputProjection.
    nutProbe = 5.5

    def nutPocket(hand: int) -> list:
        return [
            (
                "the journal nut's pocket, open to the motor side",
                (
                    hand * (rotorHubInnerX + journalNutPocketDepth / 2),
                    0.0,
                    upperLegLength / 2,
                ),
                (journalNutPocketDepth, nutProbe, nutProbe),
                "X",
            )
        ]

    # THE MILLIMETRE IN FRONT OF THE PLATE, which is what replaced the register
    # pocket's own check when the pocket was retired.
    #
    # The actuator's Ø30 output register stands 1.0 mm proud of its housing and
    # the plate lands flat on it, so the plate's whole inboard face has to be one
    # plane and there has to be NOTHING between that plane and the housing for
    # the register to occupy. Anything at all there -- a pilot rim, a waist that
    # crept towards the joint, a boss somebody added -- lands on the housing
    # before the plate reaches the register, which stops the plate seating on the
    # motor at all and does it on a face that turns. That is the failure this
    # joint has already had twice in other forms, and it is cheap to assert: a
    # probe filling the register's own footprint, with nothing allowed to stand
    # in it.
    #
    # It is a square probe rather than a Ø30 one, which makes it stronger than
    # the register is wide and costs nothing -- the plate begins outboard of this
    # box and the nearest thing on the inboard side, the cable-tie arch, is
    # 30.5 mm from the joint axis.
    def seatingFace(hand: int, atZ: float) -> list:
        return [
            (
                "the millimetre the output register needs in front of the plate",
                (
                    hand * (rotorHubInnerX - actuatorOutputProjection / 2),
                    0.0,
                    atZ,
                ),
                (
                    actuatorOutputProjection,
                    actuatorOutputRegister,
                    actuatorOutputRegister,
                ),
                "X",
            )
        ]

    # AND THE ONE BOUGHT PART IN THIS GATE, which is here because it was wrong.
    # The journal sleeve is a tube the screw passes through, its bore was cut by
    # a cylinder centred on the wrong station, and it came out capped a
    # millimetre from the end with the screw modelled straight through the cap.
    # Nothing had an opinion: a blind bore still leaves one cylindrical face for
    # the radius count above, gate F measures this hardware against the printed
    # parts it sits in rather than against itself, and a bought part is in no
    # other gate at all. Asking the bore to be OPEN is what says it.
    sleeve = [
        (
            "the journal sleeve's bore, open end to end for its screw",
            (journalInnerX + journalLength / 2, 0.0, 0.0),
            (journalLength, 3.4, 3.4),
            "X",
        )
    ]

    return {
        "journal-sleeve": sleeve,
        "pelvis-shell": pelvis,
        "electronics-deck": deck,
        "joint-rotor-hub": seatingFace(1, 0.0),
        "limb-105-unmirrored": tieTunnels(1, limbTieArchZ)
        + nutPocket(1)
        + seatingFace(1, upperLegLength / 2),
        "limb-105-mirrored": tieTunnels(-1, limbTieArchZ)
        + nutPocket(-1)
        + seatingFace(-1, upperLegLength / 2),
        "thigh-105-unmirrored": tieTunnels(1, limbTieArchZClevis)
        + nutPocket(1)
        + seatingFace(1, upperLegLength / 2),
        "thigh-105-mirrored": tieTunnels(-1, limbTieArchZClevis)
        + nutPocket(-1)
        + seatingFace(-1, upperLegLength / 2),
    }


def opening_material(
    part, centre, size, margin: float = 1.0, through: str = "Y"
) -> tuple[float, float]:
    """(material standing in the opening, material in the frame around it), mm3.

    `through` is the axis the opening is pierced along -- the wall's normal --
    and it is the one dimension the inner probe keeps in full, because the
    probe is held off the opening's SIDES and has to run right through it.
    """
    from build123d import Box, Pos

    axis = {"X": 0, "Y": 1, "Z": 2}[through]

    def shared(solid):
        both = part & solid
        return 0.0 if both is None else both.volume

    # Inside the opening, held 0.1 mm off its own faces so a coincident face is
    # not mistaken for material.
    inner = [length - 0.2 for length in size]
    inner[axis] = size[axis]
    return (
        shared(Pos(*centre) * Box(*inner)),
        shared(
            (Pos(*centre) * Box(*[length + margin * 2 for length in size]))
            - (Pos(*centre) * Box(*inner))
        ),
    )


def registry() -> dict[str, callable]:
    from cad import deck, electronics, hardware, joint, shin, thigh, torso

    return {
        # Not a printed piece, and the only bought one here. See the note beside
        # its row in panel_openings().
        "journal-sleeve": hardware.journalSleeve,
        "joint-stator-clevis": joint.statorClevis,
        "joint-rotor-hub": joint.rotorHub,
        "limb-105-unmirrored": shin.shinLeft,
        "limb-105-mirrored": shin.shinRight,
        "thigh-105-unmirrored": thigh.thighRight,
        "thigh-105-mirrored": thigh.thighLeft,
        "pelvis-shell": torso.pelvisShell,
        "electronics-deck": deck.electronicsDeck,
        "pcb-distribution": electronics.distributionBoard,
        "pcb-controller-carrier": electronics.controllerCarrierBoard,
        "pcb-sbc": electronics.sbcBoard,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pieces", nargs="*")
    args = parser.parse_args()

    from cad.finish import united

    built = registry()
    declared = expectations()
    pockets = complete_pockets()
    openings = panel_openings()
    wanted = args.pieces or sorted(set(declared) | set(pockets) | set(openings))

    failures = 0
    for name in wanted:
        rows = declared.get(name, [])
        whole = pockets.get(name, [])
        cuts = openings.get(name, [])
        if not (rows or whole or cuts) or name not in built:
            print(f"{name}: nothing declared yet")
            failures += 1
            continue

        # A printed piece is several interpenetrating bodies, and the features
        # this gate is about are exactly the ones a merge can fill in, so the
        # question is asked of the merged solid rather than of any one body.
        part = united(built[name]())
        found = cylinder_radii(part)
        print(name)
        for what, radius, count in rows:
            got = found.get(round(radius, PLACES), 0)
            ok = got == count
            failures += 0 if ok else 1
            mark = "  ok  " if ok else " FAIL "
            print(f" {mark} {count:>2} x r{radius:<7.3f}  found {got:>2}   {what}")
        for what, radius in whole:
            span = open_arc(part, radius)
            ok = abs(span - 360.0) <= 0.01
            failures += 0 if ok else 1
            mark = "  ok  " if ok else " FAIL "
            print(f" {mark} 360 deg at r{radius:<7.3f}  found {span:6.2f}   {what}")
        for what, centre, size, *axis in cuts:
            standing, frame = opening_material(
                part, centre, size, through=axis[0] if axis else "Y"
            )
            ok = standing <= 1e-6 and frame > 1.0
            failures += 0 if ok else 1
            mark = "  ok  " if ok else " FAIL "
            print(
                f" {mark} opening {size[0]:5.1f} x {size[2]:4.1f}"
                f"  {standing:7.3f} mm3 standing in it, {frame:8.1f} mm3 of wall round it"
                f"   {what}"
            )

    print()
    print("gate E: FAIL" if failures else "gate E: pass")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
