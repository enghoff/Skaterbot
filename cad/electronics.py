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

Nothing here is printed and nothing here is weighed from the CAD. Two printed
pieces exist because of this layout: cad/deck.py, the plate the upper two boards
stand on; and, inside cad/torso.py, the rails, posts, ledges, guides and seat
that everything else in here is held by. A third one did -- a plate the external
connectors were bonded into -- and it is gone, because the parts on the wall now
are bought ones that bolt or clamp themselves to it.
"""

from __future__ import annotations

import math

from build123d import Align, Box, Cylinder, Pos, Rot

from cad.parameters import (
    m2NutAcrossFlats,
    m2NutThickness,
    m3Clearance,
    m25CapHeadDiameter,
    m25CapHeadHeight,
    shellWall,
)
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

# THE POWER BAY. 52 wide for a bought 50 x 50 distribution board, where it was
# 38 for a PCB we would have drawn ourselves, and 36 tall rather than 30 because
# the battery beside it already sets this band's height and there is no reason to
# reserve less than the band holds. The bank has not been sized, so the extra
# 6 mm of height is headroom rather than a decision.
#
# 54 DEEP AND NOT 62, which is the battery's depth rather than the old block's,
# and for the same reason: the four ledges carrying the electronics deck stand
# 5 mm proud of the front and rear walls, and a 62 mm bay reaching a 36 mm band's
# full height runs 270 mm3 of reserved volume straight through two of them. That
# was found by tools/gate_f.py after its shared-volume test was fixed -- see the
# note on measure() there, which had been reporting every such overlap as zero.
powerWidth = 52.0
powerDepth = 54.0
powerHeight = 36.0
# THE CONTROLLER BAY, 140 mm wide since September 2026 where it was 76. It grew
# to take the logic BEC and the bus monitor, which were two separately mounted
# boards in the power bay with cables running up to the carrier; both ride on the
# carrier now and their cables went with them.
#
# THE WIDTH IS NOT A PREFERENCE. The bus monitor is a bought 22 mm breakout and
# it stands about 11 mm over a board once it is on standoffs, where the SBC
# leaves 10 mm of air over this one -- 9.4 when this was worked out. The only air on this deck deeper than that
# is outboard of the SBC's own edges -- electrical/carrier_pcb.py measures the
# headroom over every square millimetre of it -- and outboard to the LEFT is
# where the core board already stands. So the monitor goes to the right of the
# SBC's right-hand posts, which with their clearance allowed for is x +33.8.
# (Posts then; standoffs since, and narrower, but the monitor still cannot
# stand under the SBC and the SBC's edge is at +32.5, so the width stood.)
# What has to stand past them is the monitor, the last of the three CAN
# transceivers and the BEC's own input hardware, and 33.65 mm of board is what
# holds them, which puts this bay's edge at x +67.45.
#
# THE REAR OUTBOARD CORNER IS CUT AWAY. The charge socket's body reaches 17.1 mm
# in from the rear wall and passes 3.65 mm over this board, so the last 21 mm of
# the rear edge cannot hold the 12 mm this bay otherwise claims. The notch is in
# the reservation and in the board alike, which is cheaper than a reservation
# that promises height it has not got.
controllerWidth = 140.0
controllerDepth = 46.0
controllerHeight = 12.0
controllerNotchWidth = 21.45
controllerNotchDepth = 5.0
sbcWidth = 85.0
sbcDepth = 58.0
sbcHeight = 16.0
imuWidth = 22.0
imuDepth = 22.0
imuHeight = 6.0
# The board inside that reservation, and it is a named dimension now rather than
# a number typed into a drawing function, for the reason every board's outline
# here is one: cad/torso.py prints a seat to it. A 7Semi-class BNO085 Nano
# breakout is about 11 x 10 mm, which is too small to carry a screw -- see the
# seat in cad/torso.py for what holds it instead.
imuBoardWidth = 11.0
imuBoardDepth = 10.0

# The deck is a printed plate, so its thickness is a structural number and not a
# reservation. 3 mm of PA12-CF spanning 130 mm and carrying two boards and the
# battery's hold-down; cad/deck.py is the part.
deckThickness = 3.0

batteryX = -interiorHalfWidth + wallClearance + (batteryWidth / 2)
powerX = interiorHalfWidth - wallClearance - (powerWidth / 2)
controllerX = -interiorHalfWidth + wallClearance + (controllerWidth / 2)

# THE GAP BETWEEN THE TWO BAYS, AND IT HAS BEEN A CHASE, THEN NOT, THEN A CHASE
# AGAIN. It was 10.2 mm of deliberate cable chase while the shell's width was a
# number somebody picked. The bought 50 x 50 distribution board then took that
# width back, and the pack's connectors moved INSIDE the power bay, into the
# 23 mm of air above the board -- which is still where they are drawn, and still
# where they should be, because that is the shortest route from a pack to a fuse.
#
# Then the shell's width stopped being anybody's choice: it is derived from the
# hip clevises now, and it comes out 12.9 mm wider than the payload needs. None
# of the slack is spent on either bay -- both stay 2 mm off their own wall -- so
# all of it lands here, and the gap is 15.1 mm. It is a chase again by accident
# rather than by design, and that is the honest way to describe it: nothing is
# routed through it on purpose, and there is room if anything needs to be.
bayGap = (powerX - powerWidth / 2) - (batteryX + batteryWidth / 2)

# THE BANDS. Four of them now where there were three, and the deck is what makes
# the fourth possible: the battery fills the bottom band across most of the
# robot, so the two upper boards have nothing to stand on and are given a plate
# that bridges to the side walls instead.
lowerBandZ = saddleTopZ
deckZ = lowerBandZ + batteryHeight
deckBandZ = deckZ + deckThickness
# upperBandZ, the plane the SBC sits on, is below the standoffs: it was
# deckBandZ + controllerHeight + bandGap while the SBC stood on the deck's own
# posts, and it is the carrier's top face plus a bought standoff now.

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
# a board.
standoffHeight = 3.0
standoffDiameter = 6.0
# THE SBC STANDS ON THE CONTROLLER CARRIER, September 2026, on four M2.5 x 10
# female-female hex standoffs: an M2.5 x 6 up through the carrier into each one's
# foot, and the SBC's own four screws down into its head. It stood on four posts
# printed with cad/deck.py until then, and the posts came up THROUGH the carrier
# in Ø8.6 holes, which cost the board two walls of copper-free laminate 9.6 mm
# wide and a drill the board house does not own.
#
# M2.5 AND NOT M3, although the rest of this torso is M3. The SBC's holes are
# 2.75 mm -- see the provenance block below -- and an M3 does not pass them.
#
# 10 mm BECAUSE IT IS A LENGTH SOMEBODY SELLS. The posts put the SBC's underside
# 9.4 mm over the carrier; stock M2.5 standoffs come in 6, 8, 10 and 12, and 8
# puts the SBC's microSD socket onto the BEC's cable ties, which stand 8.5 mm
# over the board. So the SBC went up 0.6 mm, with 2 mm still clear under the lid
# over its reservation. 5 mm across the flats, drawn round as every standoff
# here is. The 2 mm this name used to hold was the band gap the posts spent,
# and see the microSD note below for why that gap had to exist.
sbcStandoffHeight = 10.0
sbcStandoffDiameter = 5.0
# The carrier's hole for the M2.5 up through it: a drilled hole in laminate
# rather than a printed one, so the ISO 273 medium figure for M2.5 and not the
# 0.4 mm over nominal a print needs.
sbcStandoffHole = 2.7

controllerBoardZ = deckBandZ + standoffHeight

pcbThickness = 1.6
upperBandZ = controllerBoardZ + pcbThickness + sbcStandoffHeight
# THE BANK IS WHAT THE BILL BUYS, September 2026, and it used to be four times
# that. It was drawn as four cans of 16 x 25 standing along the front of the power
# bay while docs/BOM.md specified TWO Panasonic EEU-FR1V471B -- 470 uF 35 V, and
# 10 x 16 on a 5 mm lead pitch. That reserve was eight times the volume of the
# parts it was reserving for, and it was the whole of the front half of the bay.
# The two cans the bill names stand on the power switch board now; the strip they
# held is that board. THE CAPACITANCE ITSELF IS UNCHANGED and still unmeasured:
# what shrank is the reservation, not the bank.
capacitorDiameter = 10.0
capacitorHeight = 16.0
capacitorPitch = 5.0

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
# THE DISTRIBUTION BOARD, and it is the reason this file no longer draws a
# power-entry PCB of its own. SwiftWing PDB-02-XT60: 50 x 50 x 1.6 mm, 13 g,
# four M3 holes on a 45 mm square, a factory-fitted XT60 socket for the bus and
# six pairs of solder tabs for the motor branches. 3S-6S, direct battery bus --
# no active parts on it at all, which is why it needs the BEC below and why its
# stated 26 V maximum is a statement of scope rather than a dielectric limit.
# THAT 26 V IS THE ONE FIGURE ON THIS PART THAT DOES NOT MATCH THE APPLICATION:
# the actuators tolerate 30 and regeneration pushes the bus up, so confirm it
# with the vendor before trusting it.
#
# Solder tabs rather than the sibling board's six XT30 sockets, deliberately: the
# tabs are flat, the sockets are not, and the connectors belong at the motor end
# of each branch where they are actually undone.
pdbWidth = 50.0
pdbDepth = 50.0
pdbThickness = 1.6
pdbHolePitch = 45.0
# The Matek 12S Pro BEC, which is what makes the bus into a logic rail: 9-55 V in,
# 5 V at 5 A out, 35 x 24 x 5.5 mm and 5 g. It replaces the generic buck module
# this file used to reserve 26 x 42 x 14 for on the deck, and it moves down here
# because its input is the raw bus and it belongs with the rest of power entry.
# It is a switching regulator in a sealed box under a deck, so watch its
# temperature on the first sustained run -- about 3 W at full output.
becWidth = 35.0
becDepth = 24.0
becHeight = 5.5
# AMASS XT60, the pack and series-link connector.
xt60Length = 16.0
xt60Width = 8.1
xt60Height = 7.5
# THE MAIN DISCONNECT IS AN XT60 AND NOT AN XT90, September 2026, and the reason
# is that an XT90 does not fit this torso. It is the same XT60 shell as the two
# lines above: the series break that arms the robot, and where a bench supply
# goes in, which is how the robot stays bench-runnable. The panel-mount variant
# actually fitted is further down, with the rest of what this wall carries.
#
# THE XT90'S OWN FIGURES WERE 20.5 x 15.5 x 21.0 and they are recorded here
# because the reasoning that reached for a 90 still holds: 8-12 AWG terminations
# and a great deal of thermal mass against a bus nobody has measured. What ended
# it was arithmetic rather than preference. The flanged XT90E-M is 42.0 x 22.8 x
# 15.1 to AMASS's own drawing, and 19.7 mm of that stands inside the wall; the
# rear wall was swept position by position against every solid in this cavity
# and the part clears 6 mm at x 50 to 53 and nowhere else, which is the patch the
# charge inlet already holds. The two cannot both have it. Rated current is not
# what was given up: AMASS rate the XT60 and the XT90 alike at 30 A, and the
# difference between them is wire gauge and thermal headroom, not contact rating.
# WHAT WAS GIVEN UP IS THE ANTI-SPARK KEY -- see the panel-mount block below.
# THERE IS NO BALANCE PORT IN THIS WALL ANY MORE, and the whole of why it was
# there is worth keeping, because it is also why it could go.
#
# It was a JST-XH 7-pin, and there was ONE of it where the battery's own leads
# offer two: the two packs' 4-pin tails were merged inside the shell instead of
# outside it, so a bench charger saw the pair as the single 6S string they are
# wired as and balanced them in one session. That merge could have been a
# two-into-one adapter on the bench, but nothing of the sort is stocked in India,
# and everything sold as a "2S-6S balance board" is a parallel breakout, which
# across a series pair is a short. Made once, inside, it could be metered and
# then left alone. The merge left one pin out: pack A's negative tap and pack B's
# positive tap are the same node only because the series harness joins them, so
# only one of them was wired to the 7-pin, or 22 AWG sense wire would have stood
# in for that harness the moment it was unplugged.
#
# ALL OF THAT WAS ONE THING -- getting the cell taps out to a charger -- AND THE
# BMS IS NOW ON THE CELL TAPS. A 6S balancing BMS stands in the bay gap (see its
# own section below), permanently wired to the same seven nodes this port
# presented, and it balances the string on every charge whether or not anybody
# plugs anything in. A socket in the wall that reaches the same wires the board
# inside already holds is not redundancy, it is a second path to the cells that
# has to be got right and kept insulated, on the one circuit here that cannot be
# fused. So the port is gone, the merge stays -- it is now the BMS's own
# seven-way tail -- and the wall carries two connectors instead of three.
#
# WHAT WOULD BRING IT BACK is a decision to charge this pack off the robot, or a
# BMS chosen without balancing. Either would want these dimensions again, and
# they were: 19.5 wide, 7.0 high, 8.0 deep, at x +15.0 from the disconnect.
# THE CHARGE INLET IS THE ONLY WAY INTO THE PACK, and what it is is further down
# with the rest of the wall's hardware -- an AMASS XT60E-F, after a GX16 bushing,
# after an AMASS XT30. What has not changed is why there are two connectors
# rather than one: it lands on the BMS's charge input AHEAD OF THE DISCONNECT,
# because charging through the disconnect instead leaves six actuator
# controllers, the BEC and the SBC sitting across the charger at something like
# half an amp, and a constant-voltage taper never falls below that, so the charge
# never terminates and the pack is held at 25.2 V for as long as it stays plugged
# in.
#
# The XT30's figures were 11.0 wide, 6.2 high and 15.0 deep, and they are kept
# here because the reasoning that picked it still holds: 2.2 A at 1C needs
# nothing bigger. THE RULE THAT NO PLUG MEANT FOR ONE PORT IN THIS WALL MAY FIT
# THE OTHER is met by there being only one port now: the disconnect went in
# September 2026 and the button that replaced it takes no plug at all. While
# both were here the rule was met by gender -- the disconnect male and its key a
# bridged female, the charge socket female and the charger's lead male -- so
# that a bridged key could not short the charge port and a charger could not
# sit in series with the pack. WHAT IS LEFT IS STILL A LIVE SOCKET: the charge
# inlet lands on the BMS's charge input, which is on the pack side of
# everything, so it is at pack voltage whenever cells are connected. That is
# why it carries recessed sockets rather than pins.
# INA226 bus monitor. New hardware: the controller has had no way to read pack
# state, which matters on a battery in a way it never did on a bench supply. It
# reads VOLTAGE ONLY since 2026-09-16, on its own VBS pin, which never went
# through a shunt: the current measurement and the Kelvin shunt it needed were
# deleted from the design that day.
#
# THE BOARD IS DRAWN FROM THE VENDOR'S OWN PHOTOGRAPHS NOW rather than as a
# guessed block, and both plan figures moved: it is square at about 22 mm a side
# and not 24 x 18. PROVENANCE, AND IT IS THE WEAKEST ON THIS PAGE. The module's
# front and back views were scaled against the one hard dimension a photograph of
# it carries, the 2.54 mm pitch of its eight-way header, and cross-checked
# against the 2010-size shunt lying beside it. NOBODY HAS PUT A CALIPER ON THIS
# PART. Every number in this block and the two below it is a photograph's answer
# and wants replacing with a measured one -- which is cheap, because the only
# things derived from them are the two posts cad/deck.py hangs the board on.
busSenseWidth = 22.0
busSenseDepth = 22.0
busSenseHeight = 8.0

# WHAT THE PHOTOGRAPHS SETTLED, and it is why this board is screwed down now
# rather than taped. It carries FOUR large plated holes in one column near its
# right-hand edge, and they are two different things: the inner pair, boxed in
# silkscreen on the front and labelled IN+ and IN- on the back, are the shunt
# terminals and no use to a mount. The outer pair carry no label or copper on
# either face, and those are the mounting holes.
#
# THE INSET IS WHAT RULES THE SCREW SIZE, not the hole. Each sits about 2.5 mm in
# from its own edge, and an M3 clearance hole at 3.4 mm breaks out of a board
# edge that close with nothing left round it. M2 fits and M2 is what the
# disconnect's ears already buy, so nothing new goes on the bill.
busSenseHolePitch = 16.7
busSenseHoleInset = 2.5

# HOW IT IS HELD, AND IT IS NOT HELD BY THIS PELVIS ANY MORE. It was two piloted
# pads off the rear wall, with an M2 self-tapping screw down through each of the
# board's two mounting holes; the board is on the controller carrier now, on two
# standoffs, and the pads went with it in September 2026. tools/gate_b.py records
# the 705 mm3 of PA12 that came back off the pelvis.
#
# WHAT THE REAR WALL WAS FOR is worth keeping, because it is the argument that
# has to be answered again if the monitor ever comes off the carrier. It hung
# under cad/deck.py's plate for one revision and that was wrong: its leads run
# DOWN, to the shunt and the bus, so a deck carrying it is a deck tied to the
# torso by wiring, and the deck is the one assembly that has to come straight up
# and out. The rear wall answered that, and so does the carrier -- but only
# because everything the carrier takes down into the bay goes on a plug.
#
# THE SHUNT DID NOT MOVE AND CANNOT. It stands in the main bus path carrying the
# whole pack current, so it stays at the distribution board, and what reaches the
# monitor is a twisted pair into its own screw terminals. electrical/carrier.py
# says what that costs.

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
# WHERE ANYTHING GETS FROM THE FLOOR TO THE DECK. The bought board took the lead
# chase with it, so the only clear column left is the 6.6 mm strip between the
# battery's rear face and the shell wall. It is enough for a sleeved pair and it
# is where the CAN loom runs -- and it is worth knowing that it is now the ONLY
# such path, so anything else crossing the deck plane has to share it.
loomRunY = -30.3

# WHERE THE BOUGHT BOARD SITS IN THE POWER BAY. It fills the floor of the bay and
# reaches 50 mm forward of a wall that is only 67.2 from the other one, which is
# most of why nothing with a nut on it fits the rear wall below the deck -- see
# the panel-hardware section further down, where that is measured rather than
# asserted.
pdbY = 0.0
pdbBoardZ = lowerBandZ + standoffHeight
pdbTopZ = pdbBoardZ + pdbThickness
# A RULE LEARNED IN THIS WALL AND WORTH KEEPING THOUGH ITS OCCASION HAS GONE.
# While the connectors were bonded into a printed panel, each opening was its
# connector plus half a millimetre all round -- so ONE MILLIMETRE BETWEEN TWO
# BODIES WAS ZERO MILLIMETRES BETWEEN TWO OPENINGS. Two bond gaps ate all of it
# and two sockets ran into one another along a six-millimetre edge. Nothing had
# ever measured it; it surfaced because a knife edge is also the one thing
# cad/finish.py cannot chamfer, and the panel's mesh came out unclosed. Bought
# bushings carry their own clearances now, but the arithmetic is the same
# wherever two holes are cut near each other.
batteryLeadZ = saddleTopZ + (batteryPackWidth / 2)
# Both cutouts sit over the board's REAR six millimetres, which is the strip of
# it nothing stands on: the board is pushed 6 mm forward in the bay for exactly
# that, and the connectors straddle the wall rather than hanging off its inside
# face, so each reaches about 10 mm in rather than its full body length.
panelX = powerX - 10.0
# Where the pack's own connectors sit: above the fuse and the monitor, clear of
# the disconnect that reaches in over the board's rear edge.
packLeadZ = pdbTopZ + 17.0


# ---- what the rear wall carries, and how it is held --------------------------
#
# THE CONNECTOR PANEL IS GONE, September 2026, and this section is what took its
# place. Keep why it existed, because the finding behind it is permanent: an
# XT90-S, a JST-XH and an XT30 are all constant-section prisms with no flange, no
# shoulder and no thread anywhere on them, so NOTHING CUT IN A 2.4 mm WALL CAN
# CAPTURE ONE. A hole smaller than the body will not pass it and a hole that
# passes it cannot stop it. A wall could only locate those connectors; retaining
# one meant bonding it, a bond wants area and area wants depth, so 6 mm of
# printed plate went behind this wall and they were epoxied into it.
#
# WHAT CHANGED IS THE HARDWARE, NOT THE ARGUMENT. Every item in this wall now
# retains itself: an eared XT60 that screws to the wall through its own two
# ears, and two threaded bushings that clamp the wall between a shoulder and
# their own nuts. That answers the panel's whole purpose without a printed part,
# without epoxy, and without a cut that has to be right first time -- a round
# hole 0.2 mm oversize is a good hole, where a prismatic socket 0.2 mm undersize
# is scrap.
#
# WHY ALL THREE STAND ABOVE THE ELECTRONICS DECK, which is not where connectors
# used to live and is not a preference. Below the deck this wall is spoken for
# end to end: the bus monitor lies across its lower half from x 42.5 to 66.5 and
# comes within 12.6 mm of it, and the deck's own wall ledges stand ON it between
# x 46 and 58 from z 0 to 5. A bare prism can thread between those -- which is
# how an XT90-S and an XT30 fitted there at all -- but a bushing cannot, because
# its nut wants a clear circle 22 mm across and 6 mm deep and there is nowhere
# below the deck with one. Above the deck the same wall has 18 to 67 mm of clear
# depth and nothing standing on it. That was measured across the whole wall
# rather than guessed, and tools/gate_f.py holds it.
#
# THE PRICE IS A CHASE THROUGH THE DECK, and it is an old debt rather than a new
# cost: the deck is a full-width plate with no way through it at all, and the
# actuator harnesses have always had to get from the cavity floor to the
# controller carrier above it. cad/deck.py draws that chase now, and these two
# power leads share it.

# THE ON/OFF BUTTON, September 2026, in place of the XT60E-M loop key that stood
# in this wall before it. WHAT WENT AND WHY IS NOT A GEOMETRY ARGUMENT: the power
# switch board turns the robot on and off electronically, and a wall that carries
# both a switch and a pull-link asks the user which one turns the robot off. The
# button is the answer to that question and the loop key was the older one.
#
# WHAT IT COSTS IS REAL AND IS NOT DRAWN HERE. A loop key is a MECHANICAL break
# in the pack's positive lead and a transistor is not, and a MOSFET fails shorted
# far more often than it fails open. With the key gone there is nothing that
# isolates this pack except unplugging it inside the shell, and docs/BOM.md
# argues that trade rather than burying it. What the change does NOT cost is
# standing current: electrical/power.py's off state has no DC path from the pack
# at all -- every divider, comparator and reference hangs off the SWITCHED side
# -- so a pack left connected is drained by leakage rather than by this board.
#
# IT IS A THREADED BUSHING AND A NUT, which is the antenna's way of mounting and
# not the disconnect's: the switch passes through a round hole and its own nut
# clamps the wall from inside, so THIS WALL LOSES TWO SCREW HOLES. The M2 pair
# 20 mm apart that held the disconnect's ears is gone, and with it the 1.45 mm
# bridge between each of those screws and the cutout, which was the thinnest
# material anywhere on this shell.
#
# THE STATION MOVED, AND THE DEPTH BEHIND THE WALL IS WHY. The disconnect sat at
# x 18 with 11.2 mm of clear air behind it before the actuator harness bank's
# mated plugs -- enough for a connector that reaches 8.3 mm in, and not enough
# for any panel-mount switch, which is a bushing plus a body plus its terminals.
# The whole wall was swept at the station height for the depth a round bushing
# can reach, and it is 11.2 mm at the old station, 18.6 mm over the SBC, and
# 21.4 mm anywhere outboard of x -44, where what stands in front is the WeAct
# core board on the far side of the carrier. So the button goes at x -44, which
# is the closest-in station that buys the full 21.4, and it leaves 30.5 mm of
# wall between its own nut and the antenna's.
#
# 12 mm AND NOT 16. A 16 mm anti-vandal switch is the part anybody reaches for
# and the common ones are 21 to 27 mm behind the panel, which does not clear
# 21.4 with anything to spare. A 12 mm one is 17 to 20, so it fits with a
# couple of millimetres in hand. THE BODY DEPTH BELOW IS A CLASS FIGURE AND NOT
# A PART'S: it is what the reservation is drawn to, and the first thing to
# measure on a real switch. If a measured part is deeper than 18 mm this station
# still works up to 21.4 and nothing beyond that does.
#
# M12 x 1 is the thread, the hole is that plus two tenths, and the nut is
# reserved at 17 mm across corners, which errs large for an M12. The button
# stands 10 mm proud, which covers the bushing left outside the wall and the
# actuator on top of it.
buttonHoleDiameter = 12.2
buttonNutDiameter = 17.5
buttonNutDepth = 3.0
buttonBodyDepth = 16.0
buttonOutboardDepth = 6.0
# What the sweep found behind this wall, kept as a dimension because it is the
# thing that chose the station and the thing a bigger switch would have to be
# checked against. tools/gate_f.py measures it on the built scene.
buttonClearDepth = 21.4

# THE CHARGE INLET IS AN AMASS XT60E-F, the female twin of the disconnect's
# XT60E-M, September 2026. It was a GX16-2 before that and an XT30 before that.
#
# WHY THE GX16 WENT, and it was not the panel hole: THE PANEL HALF CARRIED PINS.
# This side is live at 25.2 V whenever the pack is connected, since it lands on
# the BMS's charge input, so the socket-contact half is the one that belongs on
# the machine. Every stocked GX16 pair put the pins on the panel instead -- the
# series datasheet's own package list is a male panel socket and a female wire
# plug -- and the reverse part was on no Indian shelf. The XT60E-F puts recessed
# sockets on the robot and is on the shelf at the same shop as the disconnect.
# Two more things the GX16 taught are worth keeping: it was also sold with a
# 3-hole circular flange that this wall was never drilled for, and docs/BOM.md
# linked that wrong variant until 2026-09-13; and its figures were an M16 x 1
# thread, an S19 hex 21.94 across corners, and 19 mm reserved inboard.
#
# EVERY FIGURE BELOW IS OFF AMASS'S DIMENSIONED DRAWING OF THE XT60E-F, and none
# is borrowed from the XT60E-M: the two genders are different mouldings, and
# assuming they match is the exact mistake the XT90E-M's listing figures made.
# The female is 34.00 across its ears where the male is 27.00, with its screws
# 25.00 apart where the male's are 20.00 -- so the assumption would have been
# wrong on both counts again.
#
# IT IS A FLANGE AT THE MATING END, NOT EARS PARTWAY ALONG, so it mounts the
# opposite way round from the disconnect. The socket recess is in the flange's
# own face; the flange lies on the OUTSIDE of the wall and the body passes
# through. Along its axis it is 20.20 overall: a 3.10 flange, then 17.10 of body
# and solder cups behind it -- so the body stands 14.7 mm into the cavity past
# the wall's inner face, which at this station has nothing in front of it.
#
# The flange is 34.00 x 15.80 at its tallest, stepping down to 11.80 across the
# ears, and it is drawn here as the 34.00 x 15.80 envelope: that errs large at
# four corners, which on this wall is the safe direction to err. The body behind
# it is 18.70 x 11.50 on the drawing, and the cutout is that plus half a
# millimetre all round, exactly as the disconnect's is.
#
# THE WALL BETWEEN THE CUTOUT AND EACH SCREW IS 1.7 mm AT M2, and 1.2 at M3. The
# charge socket would take an M2.5 happily -- its nuts sit on the wall's face,
# 3.15 mm clear of its body -- but the disconnect cannot, so M2 serves the whole
# wall. The part's own holes are 3.10 with a 6.70 recess on the flange face for
# the head: put an M2 washer under each head, because a 3.8 mm head alone bears
# on 0.35 mm of plastic round a 3.10 hole, and the washer's 5.0 fits the recess.
chargeSocketFlangeWidth = 34.0
chargeSocketFlangeHeight = 15.8
chargeSocketFlangeThickness = 3.1
chargeSocketBodyWidth = 18.7
chargeSocketBodyHeight = 11.5
chargeSocketBodyDepth = 17.1
chargeSocketCutWidth = 19.2
chargeSocketCutHeight = 12.0
chargeSocketFixingPitch = 25.0

# AN SMA BULKHEAD FOR THE RADIO, which this robot has never had. The SBC keeps
# its WiFi on a module inside a sealed PA12 box with six motors in it, and a u.FL
# lead out to a bulkhead jack is what gets the antenna into open air. It is the
# one item in this wall that is not a power part, and above the deck it is on the
# same side of the plate as the board it plugs into.
#
# IT IS ON THE OTHER SIDE OF THE DISCONNECT NOW, and not by choice. It sat
# furthest outboard until the charge inlet became a 34 mm flange; there is no
# room for an 11 mm nut beyond that flange before the wall ends. Inboard it
# stands over the SBC, which fixes its clearance to that board at 6.0 mm
# whatever x it takes -- that is its own 15 mm of depth against the board's rear
# edge -- so the station was chosen on the two things x does change: 7 mm from
# the disconnect's ear, and in the gap between the SBC's mini-HDMI and its first
# USB-C rather than square in front of either.
#
# 1/4-36 UNS is the SMA bulkhead thread: a 6.5 mm hole, an 8 mm A/F nut, and
# about 11 mm of thread, which is four of these walls. RP-SMA or plain SMA
# follows whatever the module presents -- match the pigtail to the board, not to
# this file. The nut is reserved 6 mm deep, which is the figure it inherited
# from the GX16's and which errs deep for a 2 mm nut.
antennaHoleDiameter = 6.5
antennaNutDiameter = 11.0
antennaNutDepth = 6.0
antennaBodyDepth = 15.0
antennaOutboardDepth = 8.0

# THE THREE STATIONS, all at one height so the back of the robot reads as a row
# rather than a scatter. z = 22 is the only band that works: a window 20 mm tall
# has to clear the deck's top face at z = 8 underneath and the cover's lip at
# z = 38.2 above, which leaves its centre between 19 and 30.
#
# THE x FIGURES WERE SOLVED FOR, NOT LAID OUT BY HAND, September 2026. With the
# disconnect held where it was gated, the charge socket and the antenna were swept
# across the whole wall against every solid in the cavity and against each
# other -- inside the wall, outside it, and the strip of wall left between any
# two holes. The charge socket goes where its body clears the SBC and its flange
# still lands on the wall: at x 55.5 it is 8.6 mm from the disconnect inside,
# 8.25 from the deck and 4.45 short of the wall's edge, where 57.5 would have
# left 2.45 and 53.5 would have taken the disconnect down to 6.25 outside. The
# antenna's reasons are in its own block above. THE 1.5 mm THAT BOUND THIS WALL
# IS GONE: the tightest strip of wall is now each connector's own bridge between
# its cutout and its screws, 1.25 and 1.5, which the parts set and no layout can
# change. Move one station and all three want re-checking -- tools/gate_f.py
# measures the lot.
panelHardwareZ = 22.0
buttonPanelX = -44.0
chargeSocketPanelX = 55.5
antennaPanelX = -8.0
# Negative Y is the rear: the foot's front pressure pads sat at y = +51 and its
# rear pads at y = -40, and the leading leg swings to +Y.
panelWallY = -(torsoShellDepth / 2 - (shellWall / 2))


def rearWallCutouts() -> list[tuple[str, float, float, float, float]]:
    """(what it is, centre x, centre z, width, height) for every hole in the wall.

    One definition for three consumers: cad/torso.py cuts them, tools/gate_e.py
    asserts each is open with material round it, and tools/gate_f.py places the
    bought part that fills it. A round hole is square in this table -- width
    equals height -- because a hole is a hole to everything that reads this, and
    cad/torso.py is the one place that has to know the difference.
    """
    return [
        (
            "on/off button",
            buttonPanelX,
            panelHardwareZ,
            buttonHoleDiameter,
            buttonHoleDiameter,
        ),
        (
            "XT60E-F charge socket",
            chargeSocketPanelX,
            panelHardwareZ,
            chargeSocketCutWidth,
            chargeSocketCutHeight,
        ),
        (
            "SMA antenna bulkhead",
            antennaPanelX,
            panelHardwareZ,
            antennaHoleDiameter,
            antennaHoleDiameter,
        ),
    ]


def chargeSocketFixings() -> list[tuple[float, float]]:
    """The XT60E-F's two flange screws, in the pelvis's own x and z.

    Clamped the other way round from the disconnect's: the flange is outside,
    so the screw heads sit in the recesses on its face and the nuts are on the
    wall's inner face. M2 like the disconnect's, which leaves 1.7 mm of wall
    between each screw and the body's cutout, with a washer under each head.
    """
    half = chargeSocketFixingPitch / 2
    return [
        (chargeSocketPanelX - half, panelHardwareZ),
        (chargeSocketPanelX + half, panelHardwareZ),
    ]


# ---- the BMS bay, in the gap nothing was using ------------------------------
#
# THE PACK HAS NO PROTECTION AT ALL TODAY, and that is the hole this fills. Two
# 3S bricks are wired in series and taken straight to a distribution board: no
# cell monitoring beyond the INA226's view of the bus, no over-discharge cutoff,
# and balancing only when somebody plugs a charger into the 7-way port. A 6S BMS
# on the cell taps answers the first and the third, and it is the precondition
# for ever charging this pack in place.
#
# WIRED CHARGE-ONLY, WHICH IS WHY A SMALL BOARD WILL DO. The discharge path stays
# exactly as it is -- pack to the switch board's fuse and MOSFETs to the
# distribution board -- and the
# BMS sees only the charge current, about 2.2 A at 1C. A common-port BMS carrying
# the whole bus would need 30 to 40 A of FET dissipating into a sealed box that
# already has the BEC's 3 W in it, and no board of that size fits this torso
# anyway. The cost of the choice is honest and worth stating: NO OVER-DISCHARGE
# CUTOFF OF ITS OWN. The pack can still be flattened by leaving the robot
# switched on, and since September 2026 what prevents that is the power switch
# board's hardware cutoff at 19.2 V rather than a hand on a loop key -- a
# PACK-level cutoff, where this board sees each cell and cannot act on the
# discharge path at all. A single weak cell falls between the two of them.
#
# WHERE IT GOES, AND IT IS THE LAST FREE COLUMN IN THIS TORSO. The gap between
# the battery bay and the power bay is 15.1 mm of slack nobody chose -- the shell
# is as wide as the hip clevises make it, which is 12.9 mm more than the payload
# needs, and all of it lands here. The drawing has called it "a chase again by
# accident rather than by design"; this is the thing that needed the room.
#
# THE BOARD IS THE DALY Li-ion NMC 6S 24V 20A, chosen 2026-09-13, and everything
# below is drawn to it. Its vendor specification table gives length 58, width 33,
# height 8.2 mm and 45 g, and those are the three numbers this file uses. It was
# chosen on two counts and neither of them is its current rating, which is very
# nearly irrelevant on a charge-only board seeing 2.2 A: it BALANCES -- 30 mA
# passive, from 4.18 V per cell -- and it is the only balancing 6S board found
# that FITS. The 30 A boards in the same family are 75 mm long, and the cheap
# generic protection boards that would fit balance nothing at all, which is the
# one job this board is here to do.
#
# THE BAY WAS SWEPT AND RESERVED BEFORE THE BOARD EXISTED, and the board lands in
# it with 0.1 mm to spare at each end. That is a fit, not a clearance, which is
# why docs/BOM.md still says to put calipers on one before the pelvis is printed.
bmsBoardLength = 58.0
bmsBoardHeight = 33.0
bmsBoardThickness = 8.2

# THE CARD SLOT, which is the cross-section of the whole mount. It is cut to the
# WHOLE BOARD and not to its PCB, and that is the change a chosen board bought:
# a 2.4 mm slot takes a bare 1.6 mm PCB edge and assumes nothing is soldered
# within a guide's width of it -- an assumption about a board nobody had, and a
# way to find out only after printing. 9 mm takes the board's whole 8.2 mm
# envelope however the components fall on it, and the 0.8 mm left over is the
# strip of foam tape that stops it rattling. Two guides off the cavity floor and
# two off the deck's underside are all cut to this one number.
bmsGuideShim = 0.8
bmsGuideWall = 1.5
bmsGuideSlot = bmsBoardThickness + bmsGuideShim
bmsGuideWidth = bmsGuideSlot + (bmsGuideWall * 2)
bmsGuideDepth = 6.0

# EVERY BOUND BELOW IS SOMETHING ELSE'S FACE, which is why none of them is typed:
#
#   across the robot   the slot the board is held in, top and bottom
#   fore and aft       the connector panel's front face behind, the shell wall in
#                      front, less 1.5 mm each
#   above              the electronics deck, less the air the board hangs under
#   underneath         the tops of the two card guides, which the board's own
#                      height puts where they are
#
# THE RESERVATION IS THE SLOT RATHER THAN THE COLUMN, and it stopped being the
# column when a board was chosen. It was 12.1 mm wide -- the 15.1 mm of slack
# between the two bays, less 1.5 each side -- because nothing had been chosen and
# the whole gap was being held. It is 9 mm now, which is what the board actually
# occupies, and the three millimetres left either side are where its own leads
# go: the balance tail on one flank and the charge pair on the other. That gap
# exists because the shell is as wide as the hip clevises make it, which is
# 12.9 mm more than the payload asks for, and all of it lands here.
bmsBayClearance = 1.5
bmsWidth = bmsGuideSlot
bmsX = ((batteryX + (batteryWidth / 2)) + (powerX - (powerWidth / 2))) / 2
bmsDepth = (interiorHalfDepth * 2) - (bmsBayClearance * 2)
bmsY = 0.0

# THE BOARD HANGS FROM THE DECK RATHER THAN STANDING ON THE FLOOR, and it is the
# only thing in this torso that does. The reason is the retention: what stops a
# card lifting out of a slot is the deck over its top edge, so the board has to
# be able to rise by LESS than the slot is deep. Stood on the cavity floor a
# 33 mm board leaves 8.5 mm of air under a 4 mm slot and simply falls out of its
# guides -- which is what the sweep found when a real board replaced the
# full-height stand-in drawn here before one was chosen. So the top edge is set
# first, 1.5 mm under the deck, and the slot floor follows it down the board's
# own height. The board can then rise 1.5 mm and is still 2.5 mm into its slot.
bmsDeckGap = 1.5
bmsGuideSlotDepth = 4.0
bmsBoardTopZ = deckZ - bmsDeckGap
bmsBoardBottomZ = bmsBoardTopZ - bmsBoardHeight
bmsZ = bmsBoardBottomZ + bmsGuideSlotDepth
bmsHeight = bmsBoardTopZ - bmsZ

# WHERE THE FOUR GUIDES STAND. Set in from each END OF THE BOARD rather than
# placed on the floor, which is what they were when the board was still a guess:
# 6 mm in from each end puts them 46 mm apart under a 58 mm card, and symmetric
# about it. Both are then well clear of the IMU's reservation on the centre line,
# which used to be what decided them and pushed them 35 mm apart and off centre.
bmsGuideInset = 6.0
bmsGuideY = tuple(
    bmsY + (side * ((bmsBoardLength / 2) - bmsGuideInset)) for side in (-1, 1)
)

# AND TWO MORE OF THEM HANGING OFF THE DECK, directly over the first two. The
# board has no mounting holes, like most of its class, so it is not screwed to
# anything and everything holding it is a slot: cad/torso.py's two off the cavity
# floor take its bottom edge, and cad/deck.py's two off the plate's underside
# take its top. What that buys is not hold-down -- the plate 1.5 mm over the top
# edge was already doing that -- but LATERAL SUPPORT AT THE FAR END. Held only at
# the bottom, a 33 mm card standing on 4 mm of engagement is a cantilever and its
# top edge swings; held at both ends it is a card in a cage, and 45 g of board
# stops depending on how stiff a 4 mm slot is.
#
# They drop 4 mm below the plate and the top edge stands 2.5 mm up inside them,
# so the board is still free to rise its 1.5 mm without leaving them either. The
# deck goes on last and comes straight down, so the guides swallow the top edge
# as it lands -- and if the board is not standing where it should, the deck will
# not sit down, which is a better way to find out than closing the lid on it.
bmsTopGuideDrop = 4.0


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


# WHERE THE SBC STANDS: ON THE CARRIER, on four standoffs on its own 58 by 23 mm
# hole pattern about the centre line. The carrier reaches from x -72.55 to
# +67.45, so all four land on it, and this asks rather than assumes that.
#
# IT STOOD ON FOUR POSTS UNTIL SEPTEMBER 2026, printed with cad/deck.py and
# 14 mm tall, and they came up THROUGH the carrier in Ø8.6 clearance holes:
# sbcPostDiameter 8.0, sbcPostClearance 8.6, sbcPostHeight 14.0, which were
# retired with them. What that cost is worth keeping, because it is what a
# standoff bought back. A post and its clearance was a wall 9.6 mm across, the
# pair stood 23 mm apart, so nothing taller than the board and wider than 13 mm
# crossed the line they stood on, and every net between the core board and the
# rest of the carrier had to be routed through that gate. And Ø8.6 is past the
# largest drill the board house in docs/BOM.md owns, so four holes would have had
# to be routed out of the outline. A 5 mm standoff on a Ø2.7 hole narrows each
# wall to under 7 mm and takes the problem hole off the drawing altogether.
def sbc_standoff_xy() -> list[tuple[float, float]]:
    """The four SBC standoffs, on the board's own hole pattern, in torso x and y.

    Checked against the carrier's outline rather than taken on trust: a standoff
    with no board under it is a mount that does not exist, and moving either
    board should say so here rather than in a clearance nobody reads.
    """
    stations = [
        (dx, dy)
        for dx in (-sbcHolePitchX / 2, sbcHolePitchX / 2)
        for dy in (-sbcHolePitchY / 2, sbcHolePitchY / 2)
    ]
    for dx, dy in stations:
        if not (
            abs(dx - controllerX) < controllerWidth / 2 - sbcStandoffDiameter
            and abs(dy) < controllerDepth / 2 - sbcStandoffDiameter
        ):
            raise ValueError(f"the SBC standoff at ({dx}, {dy}) is off the carrier")
    return stations


# WHERE THE WeAct SITS ON THE CARRIER, and it is derived rather than placed. The
# core board on its sockets stands taller than the SBC's underside, so it cannot
# go under the SBC and has to stand outboard of it, in the strip between the
# carrier's left-hand edge and the SBC's own left-hand edge; this is that
# strip's centre line. It moves if the shell's width moves, which it now does
# on its own -- cad/wheeled_parameters.py builds it from the hip clevises -- so a
# number typed here would go stale silently and tools/gate_f.py would be the only
# thing to notice.
#
# THE STRIP WAS BOUNDED BY THE POSTS until they went, whose outboard faces were
# half a millimetre outboard of the SBC's edge. The standoffs are 1 mm inside
# it, so the SBC's edge is what bounds the strip now and the core board moved
# 0.25 mm inboard.
weActX = ((controllerX - (controllerWidth / 2)) - (sbcBoardWidth / 2)) / 2


# ---- what the carrier carries, and where ------------------------------------
#
# READ OFF electrical/carrier_pcb.py, which is where this board is laid out and
# where every one of these is checked against its neighbours in three dimensions.
# They are quoted in ITS frame -- origin at the board's rear outboard corner, x
# across the robot, y forward -- and turned into this one here, so that a part
# that moves on the board moves here by changing one number to match.


def onCarrier(x: float, y: float) -> tuple[float, float]:
    """A station on the carrier, in torso coordinates."""
    return (
        controllerX - (controllerWidth / 2) + x,
        y - (controllerDepth / 2),
    )


def carrier_screw_xy() -> list[tuple[float, float]]:
    """Where the carrier is screwed down to the deck, in torso coordinates.

    SIX, AND NOT AT FOUR CORNERS. A 140 mm board wants more than four screws,
    and two of the four corners are not available anyway: the rear edge carries
    connectors from board x 43 to x 118, and the rear outboard corner passes
    under the charge socket. electrical/carrier_pcb.py places the holes and
    measures each one clear of what stands near it; cad/deck.py drills its
    bosses to this list, so the two cannot disagree about where the board bolts.
    """
    inset = boardHoleInset
    board = (
        (inset, inset),
        (inset, controllerDepth - inset),
        (65.5, inset),
        (100.0, controllerDepth - inset),
        (controllerWidth - inset, inset),
        (controllerWidth - inset, controllerDepth - inset),
    )
    return [onCarrier(x, y) for x, y in board]


# The three CAN transceivers, stacked in a column at board x 90.
transceiverX, transceiverY = onCarrier(90.0, 23.0)
transceiverPitch = 11.0
# The BEC, lying flat on a thermal sheet between the two pairs of SBC standoffs,
# COMPONENT SIDE UP: its bare laminate face is what lands on the sheet, which is
# the only way the sheet takes any real heat out of it. The 6.5 is 1 mm of sheet,
# then 1.6 of its own board, then its parts standing to 5.5 above that board's
# underside; electrical/carrier_pcb.py has the whole of why it lies this way up.
# And the bus monitor on its standoffs outboard of the right-hand pair.
becX, becY = onCarrier(66.5, 23.0)
becOnCarrierHeight = 6.5
busSenseX, busSenseY = onCarrier(126.0, 22.0)
busSenseStandoff = 3.0
# Where the three actuator harnesses land: the rear connector row, from board
# x 70.55 to 117.45, with a mated plug and 3 mm for the wires to leave it.
harnessX, harnessY = onCarrier(94.0, 3.5)
harnessWidth = 47.0
harnessDepth = 5.75
harnessHeight = 12.8


# ---- the power switch board, over the distribution board ---------------------
#
# A SECOND BOARD OF OUR OWN, September 2026, and electrical/power.py says what is
# on it: the main fuse, the bus shunt and a MOSFET switch that is the robot's
# on/off and its low-battery cutoff. It sits in the pack's positive lead between
# the pack and the distribution board, which is why it is down here in the power
# bay rather than on the deck with the carrier. SINCE THE LOOP KEY WENT it is
# the only thing in that lead: the pack's own connector, mated inside the shell,
# is what makes and breaks it now.
#
# WHERE IT GOES IS DIRECTLY OVER THE BOUGHT BOARD, covering it exactly: the
# outline below is that board's own 50 x 50 footprint, 8 mm above it, which is
# over its XT60 input socket and clears the plug that goes into it by half a
# millimetre. It held the rear half of the bay and the capacitor bank held the
# front until the bank's reservation was cut to what the bill buys; the note
# further down says where that area came from.
#
# HOW IT IS HELD. Four M3 self-tapping screws from above, which is the only
# direction a screwdriver has in this bay: each goes through this board, an 8 mm
# spacer and the distribution board into the printed post that already carries
# that board's corner. They are the bought board's own four screws, made longer,
# so this board costs the print nothing at all.
#
# 8 mm OF SPACER is what clears the bought board's own solder joints and the
# motor leads leaving them, and it is as much as the deck above allows: the
# tallest parts on this board are the two TO-220 switches, 18.8 mm over it.
#
# TEN WAS TRIED WHEN THE BOARD WENT THROUGH-HOLE and it is worse. A trimmed lead
# hangs about 2 mm under the board and the bought board's XT60 input socket
# stands to within half a millimetre of the underside, so at 8 mm nothing with a
# lead may stand over that socket. Ten clears it -- and takes two millimetres off
# the far side, where the pack's own connectors hang 7.4 mm over this board and
# an upright resistor is 5.5. That trade buys 180 mm2 of board at one end and
# spends the inboard column at the other, and it leaves 1 mm over the switches
# instead of 3. So the socket stays a keepout, and electrical/power_pcb.py takes
# its rectangle from bus_input_socket_box() below.
powerSwitchSpacer = 8.0
powerSwitchSpacerDiameter = 6.0
powerSwitchBoardZ = pdbTopZ + powerSwitchSpacer
# The bank stands on THIS board now, not on the bought one: a can on the bought
# board would be 16 mm tall under a board whose underside is 8 mm above it.
capacitorZ = round(powerSwitchBoardZ + pcbThickness, 6)
# IT IS THE BOUGHT BOARD'S OWN FOOTPRINT, September 2026, and it was a 54 x 32.5
# rectangle over the rear half of that board until this file's second pass. Two
# things drove the change and the second is the interesting one.
#
# THE BOARD WENT FROM SURFACE MOUNT TO THROUGH-HOLE, so that it can be built by
# hand with an iron, and a through-hole part wants about half again the area of
# the surface-mount one it replaces. The four-terminal shunt is the extreme case:
# the original axial placeholder was later replaced by the real PBV-F1 part.
#
# AND THE CAPACITOR BANK HAD RESERVED FOUR TIMES WHAT IT BUYS. The bank was drawn
# as four cans of 16 x 25 across the whole front of this bay while the bill
# specifies TWO Panasonic EEU-FR1V471B, which are 10 x 16. Those two cans stand on
# THIS board now, on the bus copper that feeds them, and the strip they used to
# reserve is board. That is where the area came from, and it is why this change
# costs the robot nothing: the outline lands exactly on the bought board under it.
#
# WHICH BUYS THE MOUNT AS WELL, on the bought board's own four screws as above.
# The wall pad that used to stop a two-screw board turning about its own edge is
# gone with it, and so is the only printed material this board ever cost.
powerSwitchRightX = round(powerX + (pdbWidth / 2), 6)
powerSwitchLeftX = round(powerX - (pdbWidth / 2), 6)
powerSwitchRearY = pdbY - (pdbDepth / 2)
powerSwitchFrontY = pdbY + (pdbDepth / 2)


def power_switch_outline() -> list[tuple[float, float]]:
    """The board's edge, anticlockwise from its rear inboard corner, torso x and y."""
    return [
        (powerSwitchLeftX, powerSwitchRearY),
        (powerSwitchRightX, powerSwitchRearY),
        (powerSwitchRightX, powerSwitchFrontY),
        (powerSwitchLeftX, powerSwitchFrontY),
    ]


def power_switch_screw_xy() -> list[tuple[float, float]]:
    """All four of the bought board's screws, made longer to carry this one too."""
    return [
        (powerX + sx * (pdbHolePitch / 2), pdbY + sy * (pdbHolePitch / 2))
        for sx in (-1, 1)
        for sy in (-1, 1)
    ]


# WHERE THE TALL PARTS STAND, and they are the only parts this file places: the
# torso decides where a TO-220 or a plugged connector can go, so the stations are
# here and electrical/power_pcb.py reads them, and everything under 2 mm tall is
# placed there around them. (x, y, KiCad rotation), in torso coordinates.
#
#   P1  the pack's positive in, soldered through, where the pack's own lead
#       comes down behind the bay
#   F1  the fuse, in a mini-blade holder, with its blade clear of the pack leads'
#       chase over the rear corner
#   Q1  the two switches in a row with their sources meeting in the middle, so one
#   Q2  pour behind them feeds both and one in front takes both drains
#   R1  PBV-F1 shunt, four inline terminals spanning 17.78 mm; 20.7 mm high
#   P2  the switched bus out, on the inboard side where the distribution board's
#       input is
#   P3  ground in, a 22 AWG lead
#   C5  the bulk bank, two cans on the bus copper they damp -- they stood on the
#   C6  bought board until this board covered it
#   J3  the button, J1 the shunt's sense pair and J2 both holds, along the front
#
# NOTHING TALLER THAN 7.4 mm GOES INBOARD OF x 29.6 below y 4, because that is
# where the pack's own XT60s hang over this board. electrical/power_pcb.py
# measures every part against the drawn torso rather than trusting this note.
powerSwitchStations = {
    "P1": (33.0, -21.5, 0),
    "F1": (41.0, -19.5, 0),
    "Q1": (50.0, -15.0, 0),
    "Q2": (66.08, -15.0, 180),
    "P2": (34.8, -7.5, 0),
    "P3": (28.0, -18.0, 0),
    "C5": (33.0, 3.0, 0),
    "C6": (44.0, 3.0, 0),
    "J3": (34.0, 20.5, 0),
    "J2": (54.5, 20.5, 0),
}


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

    `extraHoles` is (x, y, diameter) in the board's own frame, for the holes
    the controller carrier has that are not on a corner.
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


def _bulkhead(diameter, depth, atX, atY, atZ):
    """A round panel-mount body lying across the wall: axis fore and aft.

    On its centre in all three, because a bulkhead is placed by its hole and the
    hole is in the middle of it. `can` above stands things up on the floor, which
    is the wrong axis for anything screwed into a wall.
    """
    return Pos(atX, atY, atZ) * Rot(90, 0, 0) * Cylinder(diameter / 2, depth)


def standoff(diameter, height, atX, atY, atZ):
    """One board standoff, standing on atZ. A stock threaded pillar, not printed."""
    return Pos(atX, atY, atZ) * Cylinder(
        diameter / 2, height, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )


def distributionBoard():
    """The bought distribution board on its own, so its holes can be counted.

    NOT OURS ANY MORE. This was a 38 x 62 PCB the project would have laid out and
    had fabricated, whose entire job was to join a pack to six branches through a
    fuse. It is a SwiftWing PDB-02-XT60 now -- 50 x 50, four M3 holes on a 45 mm
    square, an XT60 socket and six pairs of solder tabs -- so the hole pattern
    below is READ OFF A DATASHEET rather than chosen, which is the difference
    between this function and the controller carrier beside it.

    It is still drawn as a slab with its holes cut and nothing unioned back on,
    for the reason every board here is: tools/gate_e.py counts them, and a
    component unioned over one would fill it in with nothing else to report it.
    """
    blank = Pos(powerX, pdbY, pdbBoardZ) * Box(
        pdbWidth, pdbDepth, pdbThickness, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    for dx in (-pdbHolePitch / 2, pdbHolePitch / 2):
        for dy in (-pdbHolePitch / 2, pdbHolePitch / 2):
            blank -= Pos(
                powerX + dx, pdbY + dy, pdbBoardZ + (pdbThickness / 2)
            ) * Cylinder(m3Clearance / 2, pdbThickness * 3)
    return blank


def _bus_input_socket_slab():
    """The bought board's XT60 input: width, depth, height and where it stands."""
    return (
        xt60Width,
        xt60Length,
        xt60Height,
        powerX - (pdbWidth / 2) + (xt60Width / 2) + 2.0,
        pdbY - 8.0,
        pdbTopZ,
    )


def bus_input_socket_box() -> tuple[float, float, float, float]:
    """That socket's footprint in x and y, and how far under the power board it
    reaches.

    NAMED BECAUSE TWO FILES NEED IT. The group above draws it; electrical/
    power_pcb.py keeps the power switch board's through-hole leads out of it,
    because this socket stands to within half a millimetre of that board's
    underside and a trimmed lead is 2 mm long. A part with a drilled pad over
    this rectangle is a part whose leads land inside the socket.
    """
    width, depth, height, atX, atY, atZ = _bus_input_socket_slab()
    return (atX - width / 2, atY - depth / 2, atX + width / 2, atY + depth / 2)


def bus_input_socket_top() -> float:
    width, depth, height, atX, atY, atZ = _bus_input_socket_slab()
    return atZ + height


def powerSwitchBoard():
    """The power switch board on its own, so its three holes can be counted.

    A plain rectangle with its screw holes cut and nothing unioned back on, for
    the reason every board here is drawn that way: tools/gate_e.py counts the
    holes on the finished solid, and a component unioned over one would fill it
    in with nothing else to report it.
    """
    width = powerSwitchRightX - powerSwitchLeftX
    depth = powerSwitchFrontY - powerSwitchRearY
    blank = Pos(
        (powerSwitchLeftX + powerSwitchRightX) / 2,
        (powerSwitchRearY + powerSwitchFrontY) / 2,
        powerSwitchBoardZ,
    ) * Box(width, depth, pcbThickness, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for atX, atY in power_switch_screw_xy():
        blank -= Pos(atX, atY, powerSwitchBoardZ + (pcbThickness / 2)) * Cylinder(
            m3Clearance / 2, pcbThickness * 3
        )
    return blank


# WHAT EACH TALL PART ON THAT BOARD OCCUPIES, in its own unturned frame: width
# across the robot, depth fore and aft, height above the board's top face, and
# where its centre sits from the station electrical/power_pcb.py places it by --
# which for a footprint is its first pin, not its middle.
#
# EVERY FIGURE IS A CATALOGUE ONE or is KiCad's own 3D model of the part, which
# is the same rule the rest of this file follows for a bought part: a TO-220
# standing on its leads is 18.8 mm tall and 10 wide, a mini blade fuse stands
# 9 mm over a 7.4 mm holder, and a JST-XH with its plug in and 3 mm for the wires
# to leave is 12.8 -- the figure the controller carrier already uses.
powerSwitchBodies = {
    "P1": [(4.4, 4.4, 12.0, 0.0, 0.0, 0.0)],
    "P2": [(4.4, 4.4, 12.0, 0.0, 0.0, 0.0)],
    "P3": [(2.3, 2.3, 6.0, 0.0, 0.0, 0.0)],
    "F1": [
        (16.0, 6.74, 7.37, 4.96, -1.7, 0.0),
        (10.9, 3.8, 9.0, 4.96, -1.7, 7.37),
    ],
    "Q1": [(10.0, 4.4, 18.8, 2.54, 0.95, 0.0)],
    "Q2": [(10.0, 4.4, 18.8, 2.54, 0.95, 0.0)],
    "J2": [(13.4, 6.75, 12.8, 3.75, -0.525, 0.0)],
    "J3": [(8.4, 6.75, 12.8, 1.25, -0.525, 0.0)],
}

# The bank's two cans, drawn round rather than as slabs because they are round and
# because they are the only round thing in this torso. They stand at their own
# stations above, on the lead nearest the station -- a radial can is placed by its
# first lead like every other footprint here, and its body is centred half a lead
# pitch along from it.
capacitorRefdes = ("C5", "C6")


def powerSwitchParts() -> list:
    """The parts on that board tall enough for the torso to care about.

    Not all of them, and not the bank: everything under about 9 mm is left to
    electrical/power_pcb.py, which measures the real footprints against the
    drawn torso. These are the stand-ins that let the packing be looked at
    without running that.

    THE SMALL PARTS ARE NO LONGER 2 mm PROUD. This board was surface mount until
    September 2026 and is through-hole now, so its resistors and diodes stand on
    end and its tallest small part is a 9 mm can. That matters in exactly one
    place -- the inboard column, where the pack's connectors leave 7.4 mm -- and
    it is checked there rather than assumed.
    """
    out = []
    for refdes, (atX, atY, rotation) in powerSwitchStations.items():
        if refdes not in powerSwitchBodies:
            continue
        turn = -1 if rotation == 180 else 1
        for width, depth, height, dx, dy, dz in powerSwitchBodies[refdes]:
            out.append(
                slab(
                    width,
                    depth,
                    height,
                    atX + turn * dx,
                    atY + turn * dy,
                    powerSwitchBoardZ + pcbThickness + dz,
                )
            )
    return out


def controllerCarrierBoard():
    """The controller carrier on its own, so its holes can be counted.

    Ten holes: the six it is screwed down by and the four the SBC's standoffs
    are screwed to. Both patterns are counted separately by tools/gate_e.py,
    because they are different diameters and a union that filled either would be
    the same failure as the rotor hub's.

    board() cuts the four corners itself, so what is passed on is the two
    mid-edge stations carrier_screw_xy() adds and the standoffs. THIS DREW ONLY
    THE FOUR CORNERS until September 2026, for a board screwed down at six.
    """
    cornerX = controllerWidth / 2 - boardHoleInset
    cornerY = controllerDepth / 2 - boardHoleInset
    return board(
        controllerWidth,
        controllerDepth,
        controllerX,
        0.0,
        controllerBoardZ,
        m3Clearance,
        boardHoleInset,
        extraHoles=[
            (atX - controllerX, atY, m3Clearance)
            for atX, atY in carrier_screw_xy()
            if not (
                math.isclose(abs(atX - controllerX), cornerX)
                and math.isclose(abs(atY), cornerY)
            )
        ]
        + [(dx - controllerX, dy, sbcStandoffHole) for dx, dy in sbc_standoff_xy()],
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


# ---- what each group is, as a thing you can buy ------------------------------
#
# WHAT THE PARENTHESIS IN A TREE NODE MEANS. cad/scenes.py and tools/view.py name
# every payload body by what it IS -- "distribution board", "on/off button" --
# and that is the right name for a clearance to be reported against, but it is
# not the name on an order. This table is the other half: the designation that
# identifies the part, so a tree node reads "distribution board (SwiftWing
# PDB-02-XT60)" and the thing on the bench can be matched to the thing in the
# drawing without going back to docs/BOM.md.
#
# EVERY ENTRY IS docs/BOM.md's, and that file stays the authority -- quantities,
# prices, links and the reasons for each choice are there and are not duplicated
# here. What is here is only the identity.
#
# THREE KINDS OF ENTRY, AND THE DIFFERENCE MATTERS:
#
#   a manufacturer's designation, where the BOM has settled on one part --
#   SwiftWing PDB-02-XT60, Matek BEC12S-PRO, Banana Pi BPI-M4 Zero;
#
#   a specification, where the BOM deliberately does NOT pin a brand because the
#   part is a commodity -- a 3S 2200 mAh pack, an M3 brass standoff. The BOM
#   says to buy a matched pair of packs from one batch and names no maker, and a
#   maker invented here would be a decision this project has not taken;
#
#   an open question, said plainly. The capacitor bank has never been sized and
#   the fuse's rating waits on a measured bus current, so those two say so. A
#   node that reads "(not sized)" is worth more than a node that reads nothing,
#   because nothing is also what a chase reads.
#
# The chases, the looms and the features of a board that is already named -- the
# SBC's header, its ports, its microSD slot -- are not parts and are not here.
partNumbers = {
    "battery packs": "2 x 3S 2200 mAh 35-40C LiPo, XT60",
    "battery balance leads": "JST-XH 3S, 4-pin",
    "battery series link": "XT60 2-into-1 series harness",
    "battery pack connectors": "AMASS XT60",
    "distribution board": "SwiftWing PDB-02-XT60",
    "distribution board standoffs": "M3 brass, 6 mm A/F x 3 mm",
    "bus input socket": "AMASS XT60, factory-fitted",
    "capacitor bank": "2 x Panasonic EEU-FR1V471B, 470 uF 35 V -- bank not sized",
    "power switch board": "ours -- 50 x 50 mm two-layer PCB, electrical/power_pcb.py",
    "power switch parts": "the fuse, the shunt and the switch -- electrical/power.py",
    "power switch spacers": "M3 nylon spacer, 6 mm across x 8 mm, on M3 x 20 self-tapping",
    "bus monitor": "INA226, bus voltage only -- no external shunt",
    "logic BEC": "Matek BEC12S-PRO",
    "on/off button": "12 mm panel-mount momentary push button, M12 x 1 bushing",
    "charge socket": "AMASS XT60E-F panel mount, socket contacts",
    "antenna bulkhead": "SMA or RP-SMA bulkhead jack on a u.FL pigtail",
    "controller standoffs": "M3 brass, 6 mm A/F x 3 mm",
    "controller carrier board": "ours -- 140 x 46 mm two-layer PCB, electrical/carrier_pcb.py",
    "SBC standoffs": "M2.5 x 10 female-female hex standoff, 5 mm A/F, on M2.5 x 6 SHCS",
    "CAN transceivers": "MCP2562FD-E/P, 8-pin PDIP, in sockets",
    "WeAct core board": "WeAct STM32G474CEU6",
    "SBC board": "Banana Pi BPI-M4 Zero",
    "BMS board": "Daly Li-ion NMC 6S 24V 20A, 58 x 33 x 8.2 mm, 45 g -- balancing, wired charge-only",
    "IMU board": "BNO085 Nano breakout",
}


def labelled(name: str) -> str:
    """A group's name with its part number, for a viewer's tree.

    Applied where a body is LABELLED and not where it is looked up, which is the
    whole point of keeping this a separate table: tools/view.py still colours by
    the bare name, tools/gate_f.py still finds "pelvis" and "reservations" by
    theirs, and a part number added here can never break a measurement.

    A name with no entry comes back unchanged, so this can be handed every group
    in a scene -- the legs and the printed pieces included -- rather than only
    the payload.
    """
    number = partNumbers.get(name)
    return f"{name} ({number})" if number else name


def torsoElectronicsGroups() -> dict[str, list]:
    """The hardware, grouped by what each body IS.

    Two forms for the same reason cad/scenes.py has two: a viewer wants a tree it
    can name and hide branches of, and a clearance wants a flat list. This is the
    tree, and torsoElectronics() below pours it into the list. The names are also
    what tools/view.py colours by, and what labelled() above hangs a part number
    on -- which is why the two are checked against each other before this returns:
    rename a group and the number would otherwise fall off its node in silence.
    """
    upperZ = upperBandZ + pcbThickness
    innerWallY = -interiorHalfDepth
    outerWallY = -(torsoShellDepth / 2)
    packTopZ = lowerBandZ + batteryPackWidth

    groups = {
        # ---- the battery ----------------------------------------------------
        "battery packs": batteryPacks(),
        # Two 4-way balance leads, one per pack, joined into the single seven-way
        # tail the BMS wants. THEY USED TO RUN TO A PORT IN THE REAR WALL and
        # they run to the board in the bay gap instead, which is the whole of
        # what removing that port did to the inside of this robot: the merge is
        # the same merge, made in the same place, and it ends on a connector
        # rather than in one.
        #
        # WHERE THEY GO IS THE 3 mm OF AIR OVER THE PACKS, and it is worth
        # knowing before the harness is made up, because it is the only way from
        # the battery bay into the bay gap. The packs top out at z = 2 and the
        # deck's underside is at 5; the bays themselves are 1.5 mm apart, which
        # no wire lies in. So the tails come off the packs, lie FLAT over them --
        # half a millimetre clear above and below, which is a lead dressed down
        # and taped, not one left proud -- and turn down into the gap at the
        # BMS's inboard face. They stop there: past x = 7 the bay is the board's.
        "battery balance leads": [
            slab(
                10.0,
                balanceLeadWidth,
                balanceLeadThickness,
                1.0,
                dy,
                packTopZ + ((deckZ - packTopZ - balanceLeadThickness) / 2),
            )
            for dy in (-8.0, 8.0)
        ],
        # ---- power entry: a bought board and what stands on it ---------------
        # THERE IS NO BUS TERMINAL HERE ANY MORE. It was a 24 x 10 x 12 block
        # standing in for the strip the six motor branches landed on, and the
        # distribution board's own copper is that strip -- six pairs of solder
        # tabs on a direct battery bus. One bought part removed two drawn ones.
        "distribution board standoffs": [
            standoff(
                standoffDiameter,
                standoffHeight,
                powerX + dx,
                pdbY + dy,
                lowerBandZ,
            )
            for dx in (-pdbHolePitch / 2, pdbHolePitch / 2)
            for dy in (-pdbHolePitch / 2, pdbHolePitch / 2)
        ],
        "distribution board": [distributionBoard()],
        # The pack's own socket, on the board's inboard edge where the leads from
        # the battery reach it.
        "bus input socket": [slab(*_bus_input_socket_slab())],
        # The pack's own two XT60s and the link between them. They used to stand
        # in the lead chase beside the battery; the bought board took that width,
        # so they live here instead, in the air above the fuse and the monitor.
        "battery pack connectors": [
            slab(xt60Width, xt60Length, xt60Height, powerX - 21.0, dy, packLeadZ)
            for dy in (-4.0, -18.0)
        ],
        "battery series link": [
            slab(
                busWireDiameter,
                14.0,
                busWireDiameter,
                powerX - 21.0,
                -11.0,
                packLeadZ + xt60Height + 0.5,
            )
        ],
        # THE PACK'S MAIN LEAD, and where it goes changed twice in September
        # 2026. It used to run across this bay to the fuse; the fuse moved onto
        # the power switch board, and the positive then rose through the deck's
        # rear notch to the loop key above and came back down to that board's
        # input pad. WITH THE LOOP KEY GONE IT DOES NOT LEAVE THIS BAY AT ALL:
        # it runs from the pack's own XT60 straight to the board's input pad,
        # and this chase is the part of it that crosses the bay in free air.
        "battery main leads": [
            slab(
                abs(31.0 - (powerX - 21.0)) + busWireDiameter,
                busWireDiameter,
                busWireDiameter,
                (31.0 + powerX - 21.0) / 2,
                -24.0,
                packLeadZ + xt60Height + 1.0,
            )
        ],
        # The two cans the bill buys, standing on the power switch board. THIS
        # WAS FOUR RESERVED POSITIONS OF 16 x 25 until September 2026, against a
        # bill that has specified two 10 x 16 cans since the day it named a part.
        # STILL NOT SIZED -- cad/wheeled_parameters.py and tools/mass_budget.toml
        # both say so, and neither shrinking the reserve nor moving the cans onto
        # our own board changed that. What changed is that the reserve is now the
        # size of the parts in it.
        "capacitor bank": [
            can(
                capacitorDiameter,
                capacitorHeight,
                powerSwitchStations[refdes][0] + capacitorPitch / 2,
                powerSwitchStations[refdes][1],
                capacitorZ,
            )
            for refdes in capacitorRefdes
        ],
        # ---- the power switch board, on the bought board's own rear screws ----
        #
        # THE FUSE HOLDER USED TO BE HERE, a 20 x 10 x 14 block taped to the
        # bought board's top face. It is a part ON this board now -- a mini blade
        # holder soldered into it -- and so are the shunt, which had no mount at
        # all, and the MOSFET switch, which had no home in the CAD because the
        # bill had never bought one.
        "power switch spacers": [
            standoff(powerSwitchSpacerDiameter, powerSwitchSpacer, atX, atY, pdbTopZ)
            for atX, atY in power_switch_screw_xy()
        ],
        "power switch board": [powerSwitchBoard()],
        "power switch parts": powerSwitchParts(),
        # ON THE CONTROLLER CARRIER, September 2026, on two M2 screws with nuts
        # for standoffs. It lay on the distribution board held by tape, then hung
        # from the deck, then sat on two pads off the rear wall; the dimension
        # block says what its photographs showed, and electrical/carrier_pcb.py
        # places it.
        "bus monitor": [
            slab(
                busSenseWidth,
                busSenseDepth,
                busSenseHeight,
                busSenseX,
                busSenseY,
                controllerBoardZ + pcbThickness + busSenseStandoff,
            )
        ],
        # The logic rail. It was a generic buck module reserved on the deck, then
        # a Matek 12S Pro BEC on a bracket over the capacitor bank, and since
        # September 2026 the same BEC lying on the controller carrier on a thermal
        # sheet, component side up. It is the one item in the torso that makes
        # real heat, and the sheet under its bare laminate face is the whole of
        # what carries that into the carrier's ground plane.
        "logic BEC": [
            slab(
                becWidth,
                becDepth,
                becOnCarrierHeight,
                becX,
                becY,
                controllerBoardZ + pcbThickness,
            )
        ],
        # ---- the rear wall's hardware, above the deck ------------------------
        #
        # All three are drawn STRADDLING the wall, because that is what a panel
        # mount does and because both halves matter: what is outside decides
        # whether a hand can reach it, and what is inside is what everything in
        # the cavity has to keep clear of. The wall's outer face is the datum.
        # THE BUTTON IS A BUSHING, A NUT AND A BODY, drawn the antenna's way
        # rather than the disconnect's: it needs no screws, so the only things
        # here are what a hand reaches outside and what the cavity has to keep
        # clear of inside. The body figure is a class reservation and not a
        # measured part -- cad/electronics.py's block above says so, and says
        # what the wall behind it will take before something is in the way.
        "on/off button": [
            # The actuator a thumb reaches, standing off the OUTER face. It is
            # the nut's diameter and not the thread's, which is why it is drawn
            # outside the wall rather than through it: a dome the size of the
            # nut passed through a 12.2 hole would share volume with the shell,
            # and tools/gate_f.py says so.
            _bulkhead(
                buttonNutDiameter,
                buttonOutboardDepth,
                buttonPanelX,
                outerWallY - (buttonOutboardDepth / 2),
                panelHardwareZ,
            ),
            # The thread through the wall and the body and terminals behind it,
            # which is what the sweep behind this wall was run for.
            _bulkhead(
                buttonHoleDiameter,
                shellWall + buttonBodyDepth,
                buttonPanelX,
                outerWallY + ((shellWall + buttonBodyDepth) / 2),
                panelHardwareZ,
            ),
            # Its nut, clamping the inside face.
            _bulkhead(
                buttonNutDiameter,
                buttonNutDepth,
                buttonPanelX,
                innerWallY + (buttonNutDepth / 2),
                panelHardwareZ,
            ),
        ],
        # The charge inlet, on the BMS's charge input ahead of the disconnect. It
        # is the only connector here that is not part of running the robot, and
        # since the balance port went it is the only way into the pack at all.
        # The flange is outside the wall and the body comes through it, which is
        # the XT60E-F's way round and the opposite of the disconnect's.
        "charge socket": [
            # The flange, flat against the outside face, drawn at its 15.8 mm
            # envelope rather than stepping down to 11.8 at the ears.
            slab(
                chargeSocketFlangeWidth,
                chargeSocketFlangeThickness,
                chargeSocketFlangeHeight,
                chargeSocketPanelX,
                outerWallY - (chargeSocketFlangeThickness / 2),
                panelHardwareZ - (chargeSocketFlangeHeight / 2),
            ),
            # The body and its solder cups, from the wall's outer face inwards.
            # It fills its cutout less the half millimetre each side the cut is
            # given, so it stands clear of the shell rather than inside it.
            slab(
                chargeSocketBodyWidth,
                chargeSocketBodyDepth,
                chargeSocketBodyHeight,
                chargeSocketPanelX,
                outerWallY + (chargeSocketBodyDepth / 2),
                panelHardwareZ - (chargeSocketBodyHeight / 2),
            ),
            *[
                slab(
                    m2NutAcrossFlats,
                    m2NutThickness,
                    m2NutAcrossFlats,
                    atX,
                    innerWallY + (m2NutThickness / 2),
                    atZ - (m2NutAcrossFlats / 2),
                )
                for atX, atZ in chargeSocketFixings()
            ],
        ],
        # The antenna bulkhead and its nut, drawn the same way. The pigtail that
        # runs from here to the SBC is not drawn -- it is a coax lead in free
        # air, and this file draws chases only where something has to be kept
        # clear for one.
        "antenna bulkhead": [
            _bulkhead(
                antennaHoleDiameter,
                antennaOutboardDepth + antennaBodyDepth,
                antennaPanelX,
                outerWallY + ((antennaBodyDepth - antennaOutboardDepth) / 2),
                panelHardwareZ,
            ),
            _bulkhead(
                antennaNutDiameter,
                antennaNutDepth,
                antennaPanelX,
                innerWallY + (antennaNutDepth / 2),
                panelHardwareZ,
            ),
        ],
        # ---- controller carrier, on the deck --------------------------------
        # Six, on carrier_screw_xy()'s stations. They were drawn on the four
        # corners until September 2026, two short of what the board is screwed
        # down by.
        "controller standoffs": [
            standoff(standoffDiameter, standoffHeight, atX, atY, deckBandZ)
            for atX, atY in carrier_screw_xy()
        ],
        "controller carrier board": [controllerCarrierBoard()],
        # The WeAct core board, on headers above the carrier -- headers and not
        # screws, because the board has no mounting holes at all. 36.53 x 28.40
        # is measured off the vendor STEP; docs/BOM.md's 36.3 x 28.1 came off a
        # shop listing and is near enough to be the same board, but this is the
        # drawing.
        # OUTBOARD OF THE SBC, not centred on the carrier. It stands taller than
        # the SBC's underside, so it goes in the strip of carrier the SBC is not
        # over, and weActX is derived from the SBC's edge rather than typed so
        # that it stays there if either moves. It was derived from the post
        # that came up through this board until the posts went.
        "WeAct core board": [
            slab(36.53, 28.40, 6.0, weActX, 2.0, controllerBoardZ + pcbThickness)
        ],
        # And the transceivers go in the smaller piece, on the other side of it.
        # 10.2 x 10.4 x 7.0 IS A SOCKETED DIP-8, NOT A SOIC-8. These were drawn
        # 6 x 4 x 1.5 while docs/BOM.md specified MCP2542FD-E/SN, which Microchip
        # make only in SOIC and DFN -- so the drawing assumed a breakout or a
        # fabricated PCB that nothing on the bill buys. The bill now specifies
        # MCP2562FD-E/P, an 8-pin PDIP, because the carrier is hand-built
        # perfboard. A DIP-8 is 7.62 mm across its rows and four pins long, which
        # is 10.2 x 10.4 over the lead flanges, and a socket lifts the body about
        # 3.3 mm for 7.0 overall.
        #
        # THREE OF THEM, ONE PER BUS. There were two here until 14 September
        # 2026, at 13 mm centres and 10 mm in from the outboard edge, because
        # the robot ran six motors on two buses. It runs them two to a bus now --
        # both hips, both knees, both wheels -- which is three buses, three
        # transceivers and a fourth left as the spare in an empty socket.
        #
        # 12.7 mm on centres is five perfboard holes, which is the closest a
        # hand-built 2.54 mm board can put them, and three of them span 35.8 mm
        # of the 46 available. THE COLUMN MOVED 2.5 mm INBOARD to make room: at
        # the old 10 mm inset the outer two overlap the carrier's own M3 corner
        # holes by 0.3 mm, measured corner to corner rather than per axis. At
        # 12.5 mm in they clear those holes by 1.9 mm and still leave 7.4 mm of
        # board outboard of them.
        #
        # THE COLUMN IS AT BOARD x 90 NOW, on 11 mm centres rather than 12.7:
        # the board is a printed one and its pitch is no longer a perfboard
        # hole. It stands between the BEC and the capacitors that decouple it,
        # and the reason it is HERE rather than in the gate between the SBC's
        # left-hand posts -- which is where one of them was -- is that eighteen
        # nets have to cross that gate and a socket standing in it left two
        # slots of 2 mm. electrical/carrier_pcb.py has the whole of it.
        "CAN transceivers": [
            slab(
                10.2,
                10.4,
                7.0,
                transceiverX,
                transceiverY + dy,
                controllerBoardZ + pcbThickness,
            )
            for dy in (transceiverPitch, 0.0, -transceiverPitch)
        ],
        # Where the six actuator harnesses land: three JST-XH 4-pin on the
        # carrier's rear edge, with a mated plug on each and 3 mm over that for
        # the wires to leave the housing before they bend.
        #
        # IT WAS AT THE OTHER END OF THE BOARD and that was the finding that
        # started this rebuild. cad/deck.py's cable chase is at x 10 to 44 and
        # the bank was drawn from x -70 to -30, so the loom came up through the
        # chase and then crossed the whole torso to reach it. It is over the
        # chase now, which is most of half a metre of wire that is not made.
        "actuator harness bank": [
            slab(
                harnessWidth,
                harnessDepth,
                harnessHeight,
                harnessX,
                harnessY,
                controllerBoardZ + pcbThickness,
            )
        ],
        # ---- SBC: a Banana Pi BPI-M4 Zero, 65 x 30 --------------------------
        # ON FOUR STANDOFFS ON THE CARRIER, and the head of the screw that holds
        # each one down, which hangs under the carrier in the 3 mm between it
        # and the deck plate.
        #
        # THIS GROUP WAS DELETED ONCE, and the reason is still worth knowing: it
        # was four stock pillars drawn inside the four posts cad/deck.py used
        # to print -- the same air modelled twice, which tools/gate_f.py
        # reported as 93 mm3 of shared volume the moment its intersection test
        # was fixed. The posts are gone and the standoffs are the only thing
        # under the SBC now, so they are drawn once, here.
        "SBC standoffs": [
            *(
                standoff(
                    sbcStandoffDiameter,
                    sbcStandoffHeight,
                    dx,
                    dy,
                    controllerBoardZ + pcbThickness,
                )
                for dx, dy in sbc_standoff_xy()
            ),
            *(
                standoff(
                    m25CapHeadDiameter,
                    m25CapHeadHeight,
                    dx,
                    dy,
                    controllerBoardZ - m25CapHeadHeight,
                )
                for dx, dy in sbc_standoff_xy()
            ),
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
        # sit flat on anything: it wants about 2 mm of air beneath it. It hangs
        # over the BEC on the carrier, and it is what decided the standoffs are
        # 10 mm and not 8 -- see sbcStandoffHeight.
        "SBC microSD slot": [slab(12.0, 11.0, 1.6, -26.5, 0.0, upperBandZ - 1.6)],
        # ---- the BMS, on edge in the gap between the two bays ----------------
        # THE DALY 6S 20 A AT ITS CATALOGUE SIZE, 58 x 33 x 8.2, which is this
        # file's rule for a bought part and is what this body could not be until
        # September 2026: it stood here as a full-height stand-in drawn at the
        # bay's own limit for as long as no board had been chosen.
        #
        # The whole envelope is drawn rather than the bare PCB inside it. 8.2 mm
        # is the vendor's own height over the components, and it is the figure
        # the card guides are cut to, so drawing 1.6 mm of laminate instead would
        # measure clearances against a board nobody is going to fit.
        #
        # Its position is not a choice. cad/torso.py's two card guides put it on
        # the bay's centre line and stand its bottom edge on their slot floor,
        # which the deck 1.5 mm over its top edge is what decided.
        "BMS board": [
            slab(
                bmsBoardThickness,
                bmsBoardLength,
                bmsBoardHeight,
                bmsX,
                bmsY,
                bmsBoardBottomZ,
            )
        ],
        # ---- IMU, in the clear floor between the two hip saddles ------------
        # A BNO085 Nano breakout at 11 x 10, too small to carry a screw, so
        # there is no pattern to cut and cad/torso.py prints it a three-sided
        # SEAT instead: adhesive holds it down and the seat decides where it
        # points, which for this one board is the half that matters. An IMU
        # bedded on tape alone is an IMU whose yaw is whatever the tape allowed.
        # It stays on the floor with the battery over it: the shell floor
        # between the hip saddles is the stiffest spot in the pelvis and that has
        # not changed, and cad/torso.py's battery rails are laid across the robot
        # rather than along it so that this square of floor is still open.
        "IMU board": [
            slab(imuBoardWidth, imuBoardDepth, pcbThickness, 0.0, 0.0, floorZ)
        ],
        "IMU sensor": [slab(4.0, 4.0, 1.2, 0.0, 0.0, floorZ + pcbThickness)],
        # ---- the looms, as chases ------------------------------------------
        # Six actuator harnesses in two bundles of three, up through the two
        # floor cable ports and along the back of the cavity under the battery,
        # which is the 9 mm the hip saddles raise everything by. Then up the lead
        # chase to the harness bank on the carrier.
        "actuator harness runs": [
            slab(
                abs(cablePortX - panelX) + harnessBundleWidth,
                harnessBundleWidth,
                harnessBundleHeight,
                (sx * cablePortX + panelX) / 2,
                harnessRunY,
                floorZ,
            )
            for sx in (1, -1)
        ],
        # Up the inboard end of the power bay with the rest of the harness,
        # rather than up the back of it where the disconnect reaches in.
        "CAN loom": [
            Pos(-20.0, loomRunY, floorZ)
            * Box(
                canWireDiameter * 2,
                canWireDiameter * 2,
                deckZ - floorZ,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
        ],
    }

    orphaned = sorted(set(partNumbers) - set(groups))
    if orphaned:
        raise KeyError(
            "partNumbers names groups that do not exist: " + ", ".join(orphaned)
        )
    return groups


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
        )
        - Pos(
            controllerX + (controllerWidth / 2) - (controllerNotchWidth / 2),
            -(controllerDepth / 2) + (controllerNotchDepth / 2),
            deckBandZ + (controllerHeight / 2),
        )
        * Box(controllerNotchWidth, controllerNotchDepth, controllerHeight * 3),
        slab(sbcWidth, sbcDepth, sbcHeight, 0.0, 0.0, upperBandZ),
        slab(imuWidth, imuDepth, imuHeight, 0.0, 0.0, floorZ),
        # Appended rather than slotted in beside the other lower-band bays, and
        # deliberately: tools/gate_f.py and simulation/robot.py both read this
        # list positionally, so a new envelope goes on the end where it cannot
        # silently re-label the five that were already here.
        slab(bmsWidth, bmsDepth, bmsHeight, bmsX, bmsY, bmsZ),
    ]


def torsoPayload() -> list:
    """Both together, and what the assemblies place."""
    return [*torsoElectronics(), *torsoReservations()]
