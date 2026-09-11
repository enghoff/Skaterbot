"""What goes inside the pelvis, and therefore how tall the pelvis is.

Ported from wheeled_electronics.kcl -- its RESERVED VOLUMES, which are the part
that matters. The six-motor torso's height is not a chosen number: it is derived
in cad/wheeled_parameters.py from what has to fit inside, and these are the
things that have to fit. Anything that changes a reserved volume changes the
robot's height.

The boards themselves -- the slabs that stand in for a battery, a power-entry
block, a controller carrier, an SBC and an IMU so the packing can be looked at
rather than asserted -- are the rest of this file. The envelopes below are what
the simulation reads for its payload masses, so they come first.

WHAT THE BOARDS NOW CARRY, AND WHY IT IS HERE. A reserved volume says where a
board may be; it says nothing about where its screws are, and until a standoff
has somewhere to land the packing is only half answered. So each mock board is
cut with the mounting holes it actually has, and that pattern is a named
dimension rather than a number buried in a drawing function, because a printed
boss has to agree with it. Two of the boards have no holes at all, which is a
finding rather than an omission: the provenance block below says so, board by
board.

THE BATTERY CAME BACK, September 2026, and it is why this file grew. The robot
was tethered from August 2026 because no 6S brick fits a torso whose longest
interior dimension is across the robot, and because the 190 g a pack would weigh
was the whole of the mass headroom at the time. Deleting hip roll gave 700 g
back, and a pack made of TWO 3S BRICKS IN SERIES, STOOD ON EDGE, is 52 mm across
where one 6S brick is 108 to 125 mm long. Both objections are answered, so the
umbilical goes and the wiring that replaces it is drawn here: the leads, the
series link, the panel connectors, the looms and every standoff they stand on.

WHAT IS DRAWN AND WHAT IS ONLY RESERVED. The packs, the boards, the connectors
and the modules are drawn at their catalogue sizes and are meant to be believed.
The looms are NOT a routed harness -- they are the chases the harness has to run
in, drawn as bodies so gate F can measure whether anything else was designed
through them. A wire that has to be somewhere is worth reserving; a wire drawn
to three decimal places would be a lie.

Nothing here is printed and nothing here is weighed from the CAD. The one
printed thing this layout needs, the deck the upper two boards stand on, is
cad/deck.py.
"""

from __future__ import annotations

from build123d import Align, Box, Cylinder, Pos

from cad.parameters import m3Clearance, shellWall
from cad.torso_shell import cablePortX, torsoShellDepth
from cad.wheeled_parameters import (
    wheeledHipSaddleRise,
    wheeledTorsoInteriorFloorZ,
    wheeledTorsoShellWidth,
)

interiorHalfWidth = (wheeledTorsoShellWidth - (shellWall * 2)) / 2
interiorHalfDepth = (torsoShellDepth - (shellWall * 2)) / 2
floorZ = wheeledTorsoInteriorFloorZ
saddleTopZ = floorZ + wheeledHipSaddleRise

# How much air each item leaves against the side wall it is pushed up to. The
# battery and power entry need 116 of the 130.2 mm available, so 2 mm at each
# wall leaves 10.2 mm between them -- and that gap is not slack, it is the lead
# chase. See leadChaseWidth below.
wallClearance = 2.0
bandGap = 2.0

# ---- the reserved volumes, which are the requirement ------------------------
#
# THE BATTERY, and the orientation is the whole design. A Gens Ace class 3S
# 2200 mAh soft-case brick is 76 x 33 x 25 mm and 144 g; two of them in series
# make 6S 2200 mAh, 48.8 Wh, 288 g. Laid FLAT and side by side the pair is
# 33 + 33 = 66 mm across the robot against 63.2 mm of interior depth, and misses.
# Stood ON EDGE -- the 25 mm catalogue height lying fore and aft, the 33 mm
# catalogue width standing up -- the pair is 52 mm and fits with 11 to spare.
# That is why the packs are on edge and why the robot can carry a battery at all.
#
# The three names below are in TORSO axes, not catalogue axes, because that is
# the only way to read them against anything else in this file. Each says which
# catalogue dimension it is.
batteryPackLength = 76.0  # catalogue length, across the robot
batteryPackThickness = 25.0  # catalogue height, fore and aft: the packs are on edge
batteryPackWidth = 33.0  # catalogue width, standing up
# Between the two packs. They are soft-case cells and they swell in service, so
# they are not laid against each other.
batteryPackGap = 2.0
# The reservation around them: a millimetre at each end of the 76, one at each
# side of the 52, and three above. The packs sit ON cad/torso.py's two rails,
# whose top faces are this band's own floor, so nothing is reserved beneath them;
# the three millimetres over them are the squeeze, and the squeeze is what holds
# them down, because cad/deck.py's plate lands on it.
#
# THE ONE MILLIMETRE AT EACH SIDE IS THE TIGHTEST FIGURE IN THIS TORSO, and it
# is what set the shell's depth: the deck's ledges stand 5 mm proud of the front
# and rear walls right beside these packs. cad/torso_shell.py says why the shell
# went from 68 mm deep to 72. Measure a pack before printing the pelvis.
batteryWidth = 78.0
batteryDepth = 54.0
batteryHeight = 36.0

powerWidth = 38.0
powerDepth = 62.0
powerHeight = 30.0
controllerWidth = 76.0
controllerDepth = 46.0
controllerHeight = 12.0
sbcWidth = 85.0
sbcDepth = 58.0
sbcHeight = 16.0
imuWidth = 22.0
imuDepth = 22.0
imuHeight = 6.0

# The deck is a printed plate, so its thickness is a structural number and not a
# reservation. 3 mm of PA12-CF spanning 130 mm and carrying two boards and the
# battery's hold-down; cad/deck.py is the part.
deckThickness = 3.0

batteryX = -interiorHalfWidth + wallClearance + (batteryWidth / 2)
powerX = interiorHalfWidth - wallClearance - (powerWidth / 2)
controllerX = -interiorHalfWidth + wallClearance + (controllerWidth / 2)

# WHAT THE GAP BETWEEN BATTERY AND POWER ENTRY IS FOR. Both packs bring their
# leads out of the same end, the end that faces the power block, and an XT60 is
# 16 x 8.1 x 7.5 mm of moulded body. Two pack leads, the series link that joins
# them and the pair that leaves for the panel connector all live in this chase,
# stacked up its 36 mm rather than laid across it. Two tenths of a millimetre --
# what the 125 mm shell would have left once both blocks are off their walls --
# is not a chase, it is an interference, and 130 would leave 5.2 mm, which still
# will not take a connector body lying in it.
leadChaseWidth = (powerX - powerWidth / 2) - (batteryX + batteryWidth / 2)
leadChaseX = (powerX - powerWidth / 2 + batteryX + batteryWidth / 2) / 2

# THE BANDS. Four of them now where there were three, and the deck is what makes
# the fourth possible: the battery fills the bottom band across most of the
# robot, so the two upper boards have nothing to stand on and are given a plate
# that bridges to the side walls instead.
lowerBandZ = saddleTopZ
deckZ = lowerBandZ + batteryHeight
deckBandZ = deckZ + deckThickness
upperBandZ = deckBandZ + controllerHeight + bandGap

# WHERE THE DECK LANDS. Four pads on the front and rear inner walls, built by
# cad/torso.py and screwed into by cad/deck.py, which is why the stations are
# here rather than in either of them: two parts have to agree on these and a
# number typed twice is a number that will disagree once.
#
# They are at the only height in this cavity where a wall is not behind
# something: below the deck the battery and the power block fill it, above the
# deck the boards do. 5 mm proud of the wall clears the packs by 1.6 mm and
# 5 mm tall clears the power block by 1 -- cad/torso_shell.py records that those
# two numbers are what set the shell's depth.
deckLedgeWidth = 12.0
deckLedgeDepth = 5.0
deckLedgeHeight = 5.0
deckLedgeX = 52.0
deckLedgeY = interiorHalfDepth - (deckLedgeDepth / 2)

# Standoffs. Every board is held off what it sits on, and these are the gaps.
# 3 mm is a stock M3 brass standoff and clears the leads that have to pass under
# a board; the SBC's 2 mm is not a choice at all -- see the microSD note below.
standoffHeight = 3.0
standoffDiameter = 6.0
sbcStandoffHeight = bandGap
sbcStandoffDiameter = 5.0

powerBoardZ = lowerBandZ + standoffHeight
controllerBoardZ = deckBandZ + standoffHeight

pcbThickness = 1.6
capacitorDiameter = 16.0
capacitorHeight = 25.0
capacitorZ = powerBoardZ + pcbThickness

pcbGreen = "#1c6b42"
componentBlack = "#20232a"
canSilver = "#8c939c"
terminalBlue = "#2f5fb4"
copperRed = "#a8452a"
cellGrey = "#4a4f57"

# ---- the bought electrical hardware, at catalogue size ----------------------
#
# PROVENANCE. Every dimension in this block is a catalogue figure for a part
# docs/BOM.md names, and none of them is in reference/: a connector shell and a
# buck converter are commodity parts and the shops that sell them publish the
# same numbers. Measure them when they arrive -- the panel cutouts in
# cad/torso.py are cut to these, and a cutout is the one thing that cannot be
# adjusted after the pelvis is printed.
#
# AMASS XT60, the pack and series-link connector.
xt60Length = 16.0
xt60Width = 8.1
xt60Height = 7.5
# AMASS XT90-S, the anti-spark main disconnect, panel mounted in the rear wall.
# This is the connector that replaces the tether: a pack plugs into it, and so
# does a bench supply, which is how the robot stays bench-runnable. Its housing
# is the part the wall is cut for.
xt90Length = 20.5
xt90Width = 15.5
xt90Depth = 21.0
# JST-XH 4-pin, the balance-lead port. Two of them, one per 3S pack, brought out
# through the rear wall so that charging does not mean opening the torso.
balancePortWidth = 12.5
balancePortHeight = 7.0
balancePortDepth = 8.0
# 24 V bus to 5 V logic, >= 5 A: docs/BOM.md's "Logic DC/DC", which had no
# reserved volume at all until now. A synchronous buck module in this class is
# about this size; it sits on the deck beside the controller where it can be
# reached and where its heat is not under anything.
# It stands with its long side fore and aft, which is not cosmetic: the SBC's
# right-hand posts come up through this band on a 58 mm pitch, and a module lying
# the other way runs straight into them.
dcdcWidth = 26.0
dcdcDepth = 42.0
dcdcHeight = 14.0
# INA226 bus monitor and its shunt, on the power-entry board. New hardware: the
# controller has had no way to read pack state, which matters on a battery in a
# way it never did on a bench supply.
busSenseWidth = 24.0
busSenseDepth = 18.0
busSenseHeight = 8.0

# The looms, as chases rather than as wires. 14 AWG silicone for the bus, a
# sleeved twisted pair for CAN, and the six actuator harnesses bundled in two
# runs of three that come up through the two floor cable ports.
busWireDiameter = 3.5
canWireDiameter = 2.6
balanceLeadWidth = 6.0
balanceLeadThickness = 2.0
harnessBundleWidth = 9.0
harnessBundleHeight = 7.0
harnessRunY = -27.0

# WHERE THE PANEL SITS IN THE REAR WALL. Both cutouts have to land inside the
# battery band -- below the deck, above the shell floor -- because that is the
# only height at which the wall is not behind something. The disconnect is
# centred on the packs' own lead height and the balance ports go straight above
# it, which is also the order a hand meets them.
batteryLeadZ = saddleTopZ + (batteryPackWidth / 2)
disconnectZ = batteryLeadZ - (xt90Width / 2)
balancePortZ = disconnectZ + xt90Width + 2.0

# ---- where the screws go ----------------------------------------------------
#
# PROVENANCE, board by board, because only one of them brings a hole pattern of
# its own and the others are each a different kind of answer.
#
# THE SBC is a Banana Pi BPI-M4 Zero, chosen 2026-09-11. Banana Pi's own wiki
# gives the outline as 65 x 30 and says the board keeps "the same form factor and
# 40-pin connector as the Raspberry Pi Zero W" and "can fit most of the RPI Zero
# W cases and accessories". They publish no mechanical drawing of their own, so
# the outline is theirs and THE HOLES ARE INHERITED FROM THAT COMPATIBILITY
# CLAIM, taken off Raspberry Pi's Zero 2 W mechanical drawing (RP-008358-DS),
# which dimensions them 3.5 mm in from all four edges -- a 58 x 23 pitch -- and
# the Zero drawing calls the hole itself 2.75 +/- 0.05, for an M2.5 screw. That
# is one inference deep, so measure a board in hand before cutting a boss to it.
#
# THE CONTROLLER CARRIER AND THE POWER-ENTRY BOARD are ours to design, so their
# holes are CHOSEN and not looked up: one M3 clearance hole near each corner. M3
# because docs/BOM.md already stocks M3 screws and M3 brass heat-set inserts for
# "covers/light-duty interfaces", which is exactly what a board mount is, and
# anything else would put a new fastener size on the bill for no gain.
#
# THE WeAct STM32G474 CORE BOARD HAS NO MOUNTING HOLES. Not "none found": the
# vendor STEP (WeActStudio/WeActStudio.STM32G474CoreBoard, Hardware/QFN48) was
# imported and measured, and the largest hole anywhere in its outline is a 0.9 mm
# via. It hangs off its two 20-pin headers, which is how the carrier below
# carries it, and which is why the carrier's own holes are the ones that matter.
#
# THE BNO085 NANO BREAKOUT is 11 x 10 mm and has no room for a screw either. It
# is held to the shell floor by its own means.
sbcBoardWidth = 65.0
sbcBoardDepth = 30.0
sbcHoleInset = 3.5
sbcHolePitchX = sbcBoardWidth - (sbcHoleInset * 2)
sbcHolePitchY = sbcBoardDepth - (sbcHoleInset * 2)
sbcHoleDiameter = 2.75
# Ours, on both boards we design ourselves. 4 mm leaves 2.3 mm of board outside a
# Ø3.4 hole, which is enough to take a washer without spending the board area an
# 8 mm inset would.
boardHoleInset = 4.0

# WHERE THE SBC'S POSTS STAND, AND WHY THE CARRIER IS DRILLED FOR TWO OF THEM.
# The SBC sits 14 mm above the deck on four posts of cad/deck.py's, and the
# controller carrier is in the way of the two on the battery side: the carrier
# spans 76 mm from the left wall and the posts are on a 58 mm pitch about the
# centre line, so x = -29 lands inside it and x = +29 does not. Two Ø5.5
# clearance holes in a board we are designing anyway is the cheap answer;
# shuffling either board to miss both is not possible, because 76 + 85 is more
# than the shell is wide however they are arranged.
sbcPostClearance = 8.6
sbcPostDiameter = 8.0
sbcPostHeight = upperBandZ - deckBandZ


def _sbc_post_xy() -> list[tuple[float, float]]:
    """The four SBC post centres, on the board's own hole pattern."""
    return [
        (dx, dy)
        for dx in (-sbcHolePitchX / 2, sbcHolePitchX / 2)
        for dy in (-sbcHolePitchY / 2, sbcHolePitchY / 2)
    ]


def sbc_posts_through_carrier() -> list[tuple[float, float]]:
    """The posts that have to pass through the controller carrier, if any.

    Asked of the geometry rather than answered with a constant, so that moving
    either board changes the carrier's drilling instead of silently colliding.
    """
    halfWidth = controllerWidth / 2
    halfDepth = controllerDepth / 2
    return [
        (dx, dy)
        for dx, dy in _sbc_post_xy()
        if abs(dx - controllerX) < halfWidth and abs(dy) < halfDepth
    ]


# ---- the boards themselves --------------------------------------------------
#
# Every one of these is a stand-in for a bought board, pack or connector, drawn
# so the packing can be looked at rather than asserted. None is printed and none
# is weighed from the CAD: mass_budget.toml carries them as the battery line, the
# "Electronics and wiring" allowance and the "Power entry" allowance.


def slab(width, depth, height, atX, atY, atZ):
    """A rectangular solid on its centre in x and y, sitting ON atZ."""
    return Pos(atX, atY, atZ) * Box(
        width, depth, height, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )


def board(width, depth, atX, atY, atZ, holeDiameter, holeInset, extraHoles=()):
    """A PCB on its centre in x and y, sitting ON atZ, with its corner holes cut.

    The holes are cut and NOTHING IS UNIONED BACK ON afterwards -- every
    component above the board is a separate body in the list the scene gets,
    which is what stops a cut being filled in behind it. tools/gate_e.py counts
    them on the finished solid rather than taking that on trust.

    `extraHoles` is (x, y, diameter) in the board's own frame, for the two the
    controller carrier needs so the SBC's posts can pass through it.
    """
    blank = Pos(atX, atY, atZ) * Box(
        width, depth, pcbThickness, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    cuts = [
        (dx, dy, holeDiameter)
        for dx in (holeInset - (width / 2), (width / 2) - holeInset)
        for dy in (holeInset - (depth / 2), (depth / 2) - holeInset)
    ]
    cuts += list(extraHoles)
    for dx, dy, diameter in cuts:
        blank -= Pos(atX + dx, atY + dy, atZ + (pcbThickness / 2)) * Cylinder(
            diameter / 2, pcbThickness * 3
        )
    return blank


def can(diameter, height, atX, atY, atZ):
    """An electrolytic can, standing on atZ.

    The capacitor bank is the only round thing in the torso.
    """
    return Pos(atX, atY, atZ) * Cylinder(
        diameter / 2, height, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )


def standoff(diameter, height, atX, atY, atZ):
    """One board standoff, standing on atZ. A stock threaded pillar, not printed."""
    return Pos(atX, atY, atZ) * Cylinder(
        diameter / 2, height, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )


def _corner_standoffs(width, depth, atX, atY, atZ, inset, diameter, height):
    """Four of them, on a board's own hole pattern."""
    return [
        standoff(diameter, height, atX + dx, atY + dy, atZ)
        for dx in (inset - (width / 2), (width / 2) - inset)
        for dy in (inset - (depth / 2), (depth / 2) - inset)
    ]


def powerEntryBoard():
    """The power-entry board on its own, so its holes can be counted."""
    return board(
        powerWidth, powerDepth, powerX, 0.0, powerBoardZ, m3Clearance, boardHoleInset
    )


def controllerCarrierBoard():
    """The controller carrier on its own, so its holes can be counted.

    Six holes, not four: the four it is mounted by and the two the SBC's posts
    pass through. Both patterns are counted separately by tools/gate_e.py,
    because they are different diameters and a union that filled either would be
    the same failure as the rotor hub's.
    """
    return board(
        controllerWidth,
        controllerDepth,
        controllerX,
        0.0,
        controllerBoardZ,
        m3Clearance,
        boardHoleInset,
        extraHoles=[
            (dx - controllerX, dy, sbcPostClearance)
            for dx, dy in sbc_posts_through_carrier()
        ],
    )


def sbcBoard():
    """The Banana Pi on its own, so its holes can be counted."""
    return board(
        sbcBoardWidth,
        sbcBoardDepth,
        0.0,
        0.0,
        upperBandZ,
        sbcHoleDiameter,
        sbcHoleInset,
    )


def batteryPacks() -> list:
    """The two 3S bricks, on edge, side by side.

    Drawn as two bodies and not as one block, because the gap between them is
    real: soft-case cells swell, and a pair laid against each other has nowhere
    to do it.
    """
    offset = (batteryPackGap + batteryPackThickness) / 2
    return [
        slab(
            batteryPackLength,
            batteryPackThickness,
            batteryPackWidth,
            batteryX,
            sy * offset,
            lowerBandZ,
        )
        for sy in (-1, 1)
    ]


def torsoElectronicsGroups() -> dict[str, list]:
    """The hardware, grouped by what each body IS.

    Two forms for the same reason cad/scenes.py has two: a viewer wants a tree it
    can name and hide branches of, and a clearance wants a flat list. This is the
    tree, and torsoElectronics() below pours it into the list. The names are also
    what tools/view.py colours by.
    """
    upperZ = upperBandZ + pcbThickness
    packOffset = (batteryPackGap + batteryPackThickness) / 2
    leadZ = batteryLeadZ
    rearWallY = -interiorHalfDepth

    return {
        # ---- the battery ----------------------------------------------------
        "battery packs": batteryPacks(),
        # Each pack's own XT60, standing in the chase off the end it leaves by.
        "battery pack connectors": [
            slab(
                xt60Length,
                xt60Width,
                xt60Height,
                leadChaseX,
                sy * packOffset,
                leadZ - (xt60Height / 2),
            )
            for sy in (-1, 1)
        ],
        # The series link that makes 6S of two 3S: one male XT60 at each end and
        # about 40 mm of 14 AWG between them, folded in the chase. This is the
        # single item that turns two bought packs into this robot's pack, and it
        # is the one piece of the power path nobody sells ready-made.
        "battery series link": [
            slab(
                busWireDiameter,
                packOffset * 2,
                busWireDiameter,
                leadChaseX,
                0.0,
                leadZ + (xt60Height / 2) + 1.0,
            )
        ],
        # Pack positive and pack negative, up the chase to the panel connector.
        "battery main leads": [
            Pos(leadChaseX + sx * (busWireDiameter / 2 + 0.5), 0.0, disconnectZ)
            * Box(
                busWireDiameter,
                busWireDiameter,
                leadZ - disconnectZ,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
            for sx in (-1, 1)
        ],
        # Two 4-way balance leads, one per pack, run to the ports in the rear
        # wall. They are what makes charging possible without opening the lid.
        "battery balance leads": [
            slab(
                balanceLeadWidth,
                abs(rearWallY) - packOffset,
                balanceLeadThickness,
                leadChaseX + sx * (balancePortWidth / 2 + 1.5),
                (rearWallY - packOffset) / 2,
                balancePortZ + (balancePortHeight / 2),
            )
            for sx in (-1, 1)
        ],
        # ---- power entry: bank, fuse, terminal, monitor ----------------------
        "power entry standoffs": _corner_standoffs(
            powerWidth,
            powerDepth,
            powerX,
            0.0,
            lowerBandZ,
            boardHoleInset,
            standoffDiameter,
            standoffHeight,
        ),
        "power entry board": [powerEntryBoard()],
        "capacitor bank": [
            can(capacitorDiameter, capacitorHeight, powerX + dx, dy, capacitorZ)
            for dx in (-9.0, 9.0)
            for dy in (-11.0, 11.0)
        ],
        # The bus terminal, which is where the main disconnect lands inside. It
        # was the tether terminal until the battery came back and it is the same
        # block doing the same job: the XT90-S in the rear wall is the only thing
        # that changed, and either a pack or a bench supply plugs into it.
        "bus terminal": [slab(24.0, 10.0, 12.0, powerX, -25.0, capacitorZ)],
        "fuse holder": [slab(20.0, 10.0, 14.0, powerX, 25.0, capacitorZ)],
        "bus monitor": [
            slab(busSenseWidth, busSenseDepth, busSenseHeight, powerX, 8.0, capacitorZ)
        ],
        # ---- the panel: what the rear wall is cut for ------------------------
        "main disconnect": [
            slab(xt90Length, xt90Depth, xt90Width, leadChaseX, rearWallY, disconnectZ)
        ],
        "balance ports": [
            slab(
                balancePortWidth,
                balancePortDepth,
                balancePortHeight,
                leadChaseX + sx * (balancePortWidth / 2 + 1.5),
                rearWallY,
                balancePortZ,
            )
            for sx in (-1, 1)
        ],
        # ---- controller carrier, on the deck --------------------------------
        "controller standoffs": _corner_standoffs(
            controllerWidth,
            controllerDepth,
            controllerX,
            0.0,
            deckBandZ,
            boardHoleInset,
            standoffDiameter,
            standoffHeight,
        ),
        "controller carrier board": [controllerCarrierBoard()],
        # The WeAct core board, on headers above the carrier -- headers and not
        # screws, because the board has no mounting holes at all. 36.53 x 28.40
        # is measured off the vendor STEP; docs/BOM.md's 36.3 x 28.1 came off a
        # shop listing and is near enough to be the same board, but this is the
        # drawing.
        "WeAct core board": [
            slab(
                36.53,
                28.40,
                6.0,
                controllerX + 19.0,
                3.0,
                controllerBoardZ + pcbThickness,
            )
        ],
        "CAN transceivers": [
            slab(6.0, 4.0, 1.5, controllerX + 33.0, dy, controllerBoardZ + pcbThickness)
            for dy in (8.0, 0.0)
        ],
        # Where the six actuator harnesses land, facing the rear wall and its
        # ports.
        "actuator harness bank": [
            slab(
                46.0,
                6.0,
                8.0,
                controllerX + 8.0,
                -19.0,
                controllerBoardZ + pcbThickness,
            )
        ],
        # 24 V to 5 V, beside the controller on the deck rather than under
        # anything: it is the one item in here that makes real heat.
        "logic DC/DC": [
            slab(
                dcdcWidth,
                dcdcDepth,
                dcdcHeight,
                interiorHalfWidth - wallClearance - dcdcWidth / 2,
                0.0,
                deckBandZ,
            )
        ],
        # ---- SBC: a Banana Pi BPI-M4 Zero, 65 x 30 --------------------------
        "SBC standoffs": [
            standoff(
                sbcStandoffDiameter, sbcStandoffHeight, dx, dy, upperBandZ - bandGap
            )
            for dx, dy in _sbc_post_xy()
        ],
        "SBC board": [sbcBoard()],
        # The 40-pin header is the tall thing on this board and the only part of
        # it that asks for headroom: 8.5 mm of body over a 1.6 mm board, against
        # the 16 mm reserved. It faces FORWARD so that the connector edge can
        # face the rear wall, where the ports and the disconnect already are.
        "SBC 40-pin header": [
            slab(50.8, 5.08, 8.5, 0.0, (sbcBoardDepth / 2) - 4.75, upperZ)
        ],
        # Mini-HDMI and the two USB-C ports along the rear edge, at the spacing
        # the Pi Zero 2 W drawing gives -- 12.4, 41.4 and 54 mm from the left
        # edge -- which this board inherits along with the form factor.
        "SBC ports": [
            slab(width, 7.5, 3.2, atX, 3.75 - (sbcBoardDepth / 2), upperZ)
            for atX, width in ((-20.1, 11.0), (8.9, 9.0), (21.5, 9.0))
        ],
        # The microSD slot is on the UNDERSIDE, which is why this board cannot
        # sit flat on anything: it wants about 2 mm of air beneath it, and the
        # 2 mm band gap under this band is exactly what the standoffs spend.
        "SBC microSD slot": [slab(12.0, 11.0, 1.6, -26.5, 0.0, upperBandZ - 1.6)],
        # ---- IMU, in the clear floor between the two hip saddles ------------
        # A BNO085 Nano breakout at 11 x 10, too small to carry a screw, so
        # there is no pattern to cut and it is held to the floor by its own
        # means. It stays on the floor with the battery over it: the shell floor
        # between the hip saddles is the stiffest spot in the pelvis and that has
        # not changed, and cad/torso.py's battery rails are laid across the robot
        # rather than along it so that this square of floor is still open.
        "IMU board": [slab(11.0, 10.0, pcbThickness, 0.0, 0.0, floorZ)],
        "IMU sensor": [slab(4.0, 4.0, 1.2, 0.0, 0.0, floorZ + pcbThickness)],
        # ---- the looms, as chases ------------------------------------------
        # Six actuator harnesses in two bundles of three, up through the two
        # floor cable ports and along the back of the cavity under the battery,
        # which is the 9 mm the hip saddles raise everything by. Then up the lead
        # chase to the harness bank on the carrier.
        "actuator harness runs": [
            slab(
                abs(cablePortX - leadChaseX) + harnessBundleWidth,
                harnessBundleWidth,
                harnessBundleHeight,
                (sx * cablePortX + leadChaseX) / 2,
                harnessRunY,
                floorZ,
            )
            for sx in (1, -1)
        ],
        "CAN loom": [
            Pos(leadChaseX, harnessRunY, floorZ)
            * Box(
                canWireDiameter * 2,
                canWireDiameter * 2,
                controllerBoardZ - floorZ,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
        ],
    }


def torsoElectronics() -> list:
    """The hardware on its own, for a scene that wants nothing but the boards."""
    return [body for group in torsoElectronicsGroups().values() for body in group]


def torsoReservations() -> list:
    """The reservations on their own, which are what nothing may be designed through.

    Order matters: tools/gate_f.py names them in this order, and
    simulation/robot.py places a mass in each.
    """
    return [
        slab(batteryWidth, batteryDepth, batteryHeight, batteryX, 0.0, lowerBandZ),
        slab(powerWidth, powerDepth, powerHeight, powerX, 0.0, lowerBandZ),
        slab(
            controllerWidth,
            controllerDepth,
            controllerHeight,
            controllerX,
            0.0,
            deckBandZ,
        ),
        slab(sbcWidth, sbcDepth, sbcHeight, 0.0, 0.0, upperBandZ),
        slab(imuWidth, imuDepth, imuHeight, 0.0, 0.0, floorZ),
    ]


def torsoPayload() -> list:
    """Both together, and what the assemblies place."""
    return [*torsoElectronics(), *torsoReservations()]
