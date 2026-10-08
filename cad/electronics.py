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
# THE BATTERY, and the orientation is the whole design: two 3S soft-case packs
# in series for the 6S bus, stood ON EDGE side by side in the bottom band, the
# catalogue length across the robot, the catalogue width standing up and the
# catalogue height fore and aft. Laid flat, two packs are too wide for the cavity.
#
# THE PACK IS 1000 mAh SINCE 2026-09-30, AND THE 2200 mAh PACK THIS WAS DRAWN
# FOR NEVER EXISTED. This block described "a Gens Ace class 3S 2200 mAh brick"
# of 76 x 33 x 25 mm and 144 g, and nobody makes one. Every 3S 2200 mAh pack on
# sale in India is 105 to 108 mm long -- GenX 105 x 34 x 25 at Indian Hobby
# Center and 108 x 35 x 22 at Robokits, Bonka 105 x 34 x 25 -- and would have
# missed this bay by 30 mm. 76 mm is the length of a 1000 to 1500 mAh pack. The
# bay was kept and the pack came down to it, which costs more than half the
# energy: 6S 1000 mAh is 22.2 Wh, where 48.8 was planned.
#
# WHAT IS BOUGHT is a Bonka 11.1 V 1000 mAh 35C 3S with an XT60, in stock at
# Indian Hobby Center on 2026-09-30: the only 3S pack short enough for this bay
# that any readable Indian shop had on the shelf that day. Neither that shop nor
# Bonka publishes its size, and the one figure published for it, ElectronicsComp's
# 7.5 x 3.2 x 1.7 cm, is what was drawn until the packs came.
#
# MEASURED ON THE PACKS THEMSELVES, 2026-10-05, the day both arrived, and the
# listing was short on every side: 77 x 38 x 19 mm overall. But the pack is not a
# brick of that size. ITS BODY IS 17 x 35 FOR THE 65 mm FURTHEST FROM ITS LEADS,
# and only the last 12 mm, where the leads come out, grows to the 19 x 38 -- the
# tabs folded under the wrap and the leads' exit. So the pack is drawn as those
# two blocks, and the rule that comes with it is the one everything round it is
# placed by: THE FIN, THE FENCES, THE RAILS AND THE FOAM STOP AT THE 65 mm, where
# the 17 x 35 is a promise, and nothing printed comes alongside the lead end at all.
# Nobody knows how the lead end's extra is split between its faces, so it is
# drawn centred on the body, a millimetre proud each side and 1.5 above and
# below, and everything round it clears it however the split falls: the deck by
# a millimetre if all 3 mm of it are on top, the rail under it by a millimetre if
# they are all underneath. Fore and aft the two lead ends meet in the middle at
# full size, which is two wrapped ends touching and harmless; if more of the
# extra is on the inner faces than the outer, the pair want up to 2 mm more than
# the fin leaves and will splay outwards, where nothing stands beside the lead
# ends.
#
# The names below are in TORSO axes, not catalogue axes, because that is the
# only way to read them against anything else in this file. Each says which
# catalogue dimension it is.
batteryPackLength = 77.0  # catalogue length, across the robot: overall
batteryPackThickness = 17.0  # catalogue height, fore and aft, the body: on edge
batteryPackWidth = 35.0  # catalogue width, standing up, the body
# How far from the end opposite the leads the body's 17 x 35 holds, and the most
# the lead end comes to past it. Measured, 2026-10-05.
batteryPackBodyLength = 65.0
batteryPackLeadThickness = 19.0
batteryPackLeadWidth = 38.0
# THE BMS, because it stands between the two packs since 2026-10-05 and its
# thickness is the gap between them. The Daly 6S 24V 20A, whose vendor table
# gives length 58, width 33 and height 8.2 mm; those are the three numbers drawn,
# in torso axes: its length across the robot, its width standing up and its
# height fore and aft. The board's own section further down says why this board.
bmsBoardLength = 58.0
bmsBoardHeight = 33.0
bmsBoardThickness = 8.2
# THE TWO PACKS AND THE BOARD ARE ONE BLOCK, 45 mm across, assembled securely
# before it goes in: pack, board, pack. 45 is the owner's figure for the block as
# it is built, 2026-10-05, and it is what the torso is laid out to; how the board
# and the two packs share it inside is the builder's, and what is drawn is the
# board at its catalogue thickness in the middle of the 11 mm the packs leave.
# They are soft-case cells that swell in service, so what is between them is a
# flat, rigid board, never each other. The block is what the wall pads hold, and
# since 2026-10-06 they hold it by its own outer faces, 45 mm apart, with no foam
# between: the owner's call. A pack that swells now pushes on printed pads.
batteryBlockWidth = 45.0
# Between the two packs, and it is the BMS now, where it was a 2 mm printed fin.
batteryPackGap = batteryBlockWidth - 2 * batteryPackThickness
# The reservation around them is the bay the 2200 mAh packs were meant to fill,
# kept at its size so that nothing else in this torso moved when the pack
# shrank. The packs sit ON cad/torso.py's two rails, whose top faces are this
# band's own floor, so nothing is reserved beneath them. What the smaller packs
# leave inside it is the hold-down's: the fences, the fin and the foam.
#
# The bay's 1 mm to the deck ledges at each side is still what set the shell's
# depth: the ledges stand 5 mm proud of the front and rear walls beside it.
# cad/torso_shell.py says why the shell went from 68 mm deep to 72.
#
# 39 TALL SINCE 2026-10-05, where it was 36, and it is the measured pack that
# moved it. A 35 mm body under 4 mm of squeezed foam is 39, which is the same
# 4 mm the top pads had over the 32 mm the listing claimed, so the pads still
# push the way they did. And 39 is also what the lead end needs: 38 mm at most,
# with a millimetre to the deck if every bit of its extra is on top. At 36 the
# lead end ran into the deck by up to 2 mm. The 3 mm go straight into the
# robot's height -- cad/wheeled_parameters.py adds it up.
batteryWidth = 78.0
batteryDepth = 54.0
batteryHeight = 39.0

# THE POWER BAY. 52 wide for a bought 50 x 50 distribution board, where it was
# 38 for a PCB we would have drawn ourselves -- and the board in it is our own
# again since 2026-10-07, on the same 50 mm and the same posts -- and as tall as
# the battery's band rather than 30 because the battery beside it already sets
# this band's height
# and there is no reason to reserve less than the band holds: 36 until the
# measured pack made the band 39 on 2026-10-05. The bank has not been sized, so
# the extra 9 mm of height is headroom rather than a decision.
#
# 54 DEEP AND NOT 62, which is the battery's depth rather than the old block's,
# and for the same reason: the four ledges carrying the electronics deck stand
# 5 mm proud of the front and rear walls, and a 62 mm bay reaching a 36 mm band's
# full height runs 270 mm3 of reserved volume straight through two of them. That
# was found by tools/gate_f.py after its shared-volume test was fixed -- see the
# note on measure() there, which had been reporting every such overlap as zero.
powerWidth = 52.0
powerDepth = 54.0
powerHeight = 39.0
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
# THE REAR OUTBOARD CORNER IS CUT AWAY. The charge socket's body reached 17.1 mm
# in from the rear wall and passed 3.65 mm over this board, so the last 21 mm of
# the rear edge could not hold the 12 mm this bay otherwise claims. The notch is
# in the reservation and in the board alike, which is cheaper than a reservation
# that promises height it has not got. THE NOTCH OUTLIVED ITS REASON on
# 2026-10-05: the male inlet that replaced that socket reaches 10.7 mm in from
# the outer face and stops 2.3 mm short of this board's rear edge in plan. It
# stays because electrical/carrier_pcb.py lays the board out round it, and a
# corner of air costs nothing.
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
# foam over the battery; cad/deck.py is the part.
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
# all of it lands here, and the gap is 15.1 mm.
#
# AND IT IS THE BATTERY'S WIRING SPACE, since 2026-10-05, and nothing else's. The
# BMS stood across the whole of it for three weeks, which made it a wall between
# the packs and the power board: the packs' own leads come out of their end faces
# straight into it, and the board's leads come out of its two ends, which faced
# the shell walls 4.6 mm away. The BMS went in between the packs and the gap was
# cleared, so that each pack's 14 AWG leads have the room to turn into the strip
# beside it. The battery harness further down is drawn through it.
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
# deck the boards do. 5 mm proud of the wall cleared the packs by 1.6 mm and
# 5 mm tall clears the power block by 1 -- cad/torso_shell.py records that those
# two numbers are what set the shell's depth.
#
# SIX MILLIMETRES PROUD SINCE 2026-09-30, where they were five. The screw is
# placed by its head, half a millimetre off the wall, so the only way to put more
# ledge round its thread is to bring the open face further out -- and at five
# that face was 1.0 mm outside the thread, under the 1.25 or so a screw cutting
# its own thread into plastic wants, and the face a firm tightening would split.
# At six it is 2.0. The bays beside the ledges are 0.6 mm off them now rather
# than 1.6, and nothing drawn in either comes within 5.5 mm, so the shell's depth
# stands.
deckLedgeWidth = 12.0
deckLedgeDepth = 6.0
deckLedgeHeight = 5.0
deckLedgeX = 52.0
deckLedgeY = interiorHalfDepth - (deckLedgeDepth / 2)

# THE SCREW IS NOT ON THE LEDGE'S CENTRE LINE ANY MORE, September 2026. It is
# placed by its head: an M2.5 cap head with half a millimetre of air to the
# wall, which leaves 2.2 mm of ledge round its pilot on the open side -- 2.0
# outside the thread the screw cuts. cad/parameters.py's m25Clearance says
# why the size came down from M3. The pilot runs the ledge's whole height, so an
# M2.5 x 8 through the 3 mm deck has 5 mm of thread -- twice its diameter, and
# the tip ends flush with the ledge's underside. The M3 x 10 it replaces would
# have wanted 7 mm of a ledge 5 mm tall.
deckScrewHeadAir = 0.5
deckScrewY = interiorHalfDepth - (m25CapHeadDiameter / 2 + deckScrewHeadAir)

# THE BATTERY'S HOLD-DOWN, 2026-09-30, and until then there was none. This file
# said the deck held the packs down by landing on 3 mm of squeeze over them, and a
# gap is not a squeeze: nothing filled it, so a pack could lift 3 mm, slide
# 2.5 to 3 mm endwise and swing its foot 7 mm towards a wall, and what stopped it
# was whatever happened to be in the way.
#
# THE PACKS AND THE BMS ARE ONE BLOCK, since 2026-10-05, and the block is held
# in all six directions:
#   - down, on cad/torso.py's two rails, which stand under the packs' centre lines;
#   - to the right, on a stop at each rail's end, which catches the foot of the
#     end face and leaves the top of it, where the leads come out, clear;
#   - outwards, directly, on the pads cad/torso.py stands off each long wall;
#   - up, through foam, on the deck's underside;
#   - to the left, through foam, on the left wall.
# Towards each other is no longer a direction anything has to hold: the packs and
# the board between them are assembled into one piece, and the pads on the two
# long walls hold it between them across its whole 45 mm. Elsewhere the
# printed faces say where the block is and the foam pushes it there, taking up
# what one pack differs from another by. Across the block nothing takes that up
# now -- a block built over 45 will not go in, and one under it is free by the
# difference -- so it is the builder's 45 that has to be right. Everything here follows
# the pack dimensions above, so a different pack moves the rails, the pads and
# the stops with it.
#
# ALL OF IT BEARS ON THE BODY, since the packs were measured on 2026-10-05: the
# rails, the pads, the board between the packs and every piece of foam stop at
# the 65 mm the body's 17 x 35 is good for, and past it the lead end has air on
# every side but one. The one is the stop, which it bears on end-on rather than
# beside -- the stop stands past the 77 mm, so however the lead end is shaped it
# is never alongside it -- and the rails drop away under the lead end on their
# way to it, so the stop is braced without anything coming under the part of
# the pack that is not a promise.
#
# THE FIN AND THE TWO FENCES ARE GONE, 2026-10-05. The fin is the BMS now, and
# the fences were what stood between the packs and the two strips along the long
# walls -- which is where each pack's XT60 has to lie, and where the actuator
# harness runs along the back of the floor. A fence standing on the floor along
# the whole of a pack took both. Four pads off each wall bear on the block
# instead, lifted clear of the harness and placed round the connector, so at
# the connector's height the strip runs clear from the block's face to the
# wall, 11.1 mm.
#
# THE SIDE STRIPS WENT ON 2026-10-06. Until then the pads bore on 3 mm of
# squeezed foam down each outer face, cut to the pads, and stood 51 mm apart;
# the owner wants the block held at its own 45. The pads came 3 mm in from each
# wall, and because a deeper pad's 45 degree underside reaches 3 mm lower at the
# wall, the low ones and the connectors over them went 3 mm up to keep their
# half millimetre over the harness.
#
# What foam is left is cut from one 5 mm sheet of closed-cell foam, docs/BOM.md's.
# Squeezed to 3 mm at the end and 4 on top: 40 and 20 %, so none of it has been
# squeezed flat and every piece still pushes. The end
# pad was 3.5 until the measured pack came 2 mm longer than the listing, and it
# is 3 rather than less because the pack grew towards the left wall and not
# into the bay gap -- see where its ends are placed below. The block goes down
# between the pads, whose top edges are chamfered for it.
batteryFoamFree = 5.0
# Each pack's outer face, which is the block's, and where the wall pads bear.
batteryPackOuterY = (batteryPackGap / 2) + batteryPackThickness
batteryPackTopZ = lowerBandZ + batteryPackWidth
batteryFoamTop = deckZ - batteryPackTopZ
# THE LEAD END IS FLUSH WITH THE BAY'S INBOARD END, and the pack is laid off
# leftwards from there. Centred in the bay as it used to be, a 77 mm pack leaves
# the end pad 2.5 mm, half its free thickness; held at the bay's end it leaves
# 3. The lead end is 1.5 mm further right than it was, and the stops moved out
# of the bay into the gap with it -- cad/torso.py says how far that leaves them
# from the BMS.
batteryPackRightX = batteryX + (batteryWidth / 2)
batteryPackLeftX = batteryPackRightX - batteryPackLength
# Where the body ends and the lead end begins. Every printed face and every piece
# of foam that bears on a pack beside it stops short of here.
batteryPackBodyEndX = batteryPackLeftX + batteryPackBodyLength
batteryFoamEnd = batteryPackLeftX + interiorHalfWidth
# The stop on each rail's end stands this far over the rail, into the foot of the
# pack's end face and no higher. 3 mm SINCE THE PACKS WERE MEASURED, where it was
# 5: a pack's two main leads come out of its end face about 7 mm in from its
# bottom and top edges, at mid-thickness, which is right over the rail, and at 5
# the stop came within a quarter of a millimetre of the bottom lead.
batteryRailStopHeight = 3.0
# What is kept clear round the lead end's worst case, wherever its extra falls:
# the deck over it, and the rails where they drop away under it.
batteryLeadEndAir = 1.0

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
# what shrank is the reservation, not the bank. AND IT CANNOT SIMPLY GROW:
# electrical/power_reset.py puts the soft start's worst restart at 1.97 A of its
# 2 A limit with these two cans, and a third takes it over -- found 2026-10-07,
# when the board had room for the bill's two spares at the ends of its rows of
# motor plugs.
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
# with the rest of the wall's hardware -- an AMASS XT60E-M since 2026-10-05,
# after an XT60E-F, a GX16 bushing and an AMASS XT30. What has not changed is why
# there are two connectors rather than one: it lands on the BMS's charge input AHEAD OF THE DISCONNECT,
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
# sit in series with the pack. WHAT IS LEFT IS A LIVE CONNECTOR: the charge
# inlet lands on the BMS's charge input, which is on the pack side of
# everything, so it is at pack voltage whenever cells are connected. It carried
# recessed sockets for that reason until 2026-10-05, and carries pins now, inside
# the XT60's own shroud, because the female went onto the charger's lead
# instead. The inlet's own block further down says what that costs.
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
harnessBundleWidth = 9.0
harnessBundleHeight = 7.0
harnessRunY = -27.0
# WHERE ANYTHING GETS FROM THE FLOOR TO THE DECK. The bought board took the lead
# chase with it, so the only clear column left is the 6.6 mm strip between the
# battery's rear face and the shell wall. It is enough for a sleeved pair and it
# is where the CAN loom runs -- and it is worth knowing that it is now the ONLY
# such path, so anything else crossing the deck plane has to share it.
#
# IT RISES AT THE BACK OF THE BAY GAP SINCE 2026-10-05, at the power bay's
# inboard end, where it stood 40 mm further left until the rear pack's XT60 took
# the strip it stood in. That is what its own comment further down always said it
# did, and the deck's rear notch is already open over it.
loomRunY = -30.3
loomRunX = 18.5

# ---- the battery's wiring, which is the reason this layout exists ------------
#
# WHAT HAS TO FIT, from the parts in hand on 2026-10-05. Each pack's two main
# leads are 14 AWG silicone, 3.5 mm over the insulation, about 76 mm from its end
# face to the back of its own female XT60, and they leave the end face at
# mid-thickness about 7 mm in from its bottom and top edges. A 14 AWG lead is
# stiff, so every turn below is drawn at a radius of about 8 mm and none tighter.
# The BMS's leads leave its two short ends, not its faces: B-, the NTC pair and
# P- at one end, its 7-way balance socket at the other. Its B- and P- are about
# 16 AWG and nearly as stiff as the packs'; the balance and NTC wires are thin and
# go where they are put.
#
# WHAT IS BULKY IS NOT THE WIRE BUT THE CONNECTOR. Each pack's female XT60 mates
# with one male of the series harness, and the mated pair is a rigid block about
# 30 mm long and 15.6 x 8.1 across, with a stiff, heat-shrunk joint at each end.
# There are two of them and they are the most awkward things in this torso.
# There is no third: the harness's own female output is cut off, docs/BOM.md
# says so, and its two loose legs are soldered to the power switch board's pack
# inputs, P1 and P3.
#
# EACH PACK'S CONNECTOR LIES IN THE STRIP BESIDE IT, along the long wall, above
# the lower wall pads. Its leads come out of the end face, turn through the bay
# gap in one U of about 8 mm radius and run back into the connector, and the
# harness's legs come out of the other end, turn up over it and run back along
# the top of the strip to the bay gap, which they cross to the power bay.
xt60Span = 15.6  # AMASS XT60, the long side of its mating face
batteryConnectorLength = 30.0
batteryLeadReach = 10.0
batteryLegReach = 10.0
# What every chase below keeps clear of the faces it runs beside.
harnessAir = 0.5

# THE WALL PADS, which replaced the battery's two fences on 2026-10-05: four on
# each long wall, bearing on the block's faces at batteryPackOuterY. Three low and
# one high. The low ones are as low as the actuator harness along the back of the
# floor lets them be -- each has a 45 degree underside running down to the wall,
# because it prints upright, and that underside has to clear the harness's top
# by harnessAir where the harness comes nearest the wall -- and the connector
# lies over them. The high one is at the left, where the connector and its legs
# are not. Placed by the pack's own length rather than typed stations, so a
# different pack moves them.
#
# NO PAD REACHES MORE THAN 17 mm UP THE PACK, measured from its bottom face: the
# owner's limit, 2026-10-06. A pad may stand up to that line and not past it,
# and tools/gate_f.py measures every one against it. The low pads stop at 12.5
# and were never near it; the high one stood 7.5 mm under the pack's top, 27.5
# up, and now stands with its top on the line.
batteryPadReach = 17.0
batteryPadWidth = 6.0
batteryPadHeight = 5.0
batteryPadLowZ = (
    floorZ
    + harnessBundleHeight
    + harnessAir
    + (abs(harnessRunY) + harnessBundleWidth / 2 - batteryPackOuterY)
)
batteryPadHighZ = lowerBandZ + batteryPadReach - batteryPadHeight
batteryPadLowX = tuple(
    batteryPackLeftX + batteryPackBodyLength * share for share in (0.12, 0.43, 0.74)
)
batteryPadHighX = batteryPackLeftX + batteryPackBodyLength * 0.24

# Where each connector lies: in the middle of the strip between the block's face
# and the wall, which is clear at its height; a millimetre over the low pads;
# and wholly beside the pack's body, ending a millimetre short of its lead end.
batteryConnectorY = (batteryPackOuterY + interiorHalfDepth) / 2
batteryConnectorZ = batteryPadLowZ + batteryPadHeight + 1.0
batteryConnectorRightX = batteryPackBodyEndX - 1.0
batteryConnectorLeftX = batteryConnectorRightX - batteryConnectorLength
# And the lane the harness's legs come back along, a millimetre over it.
batteryLegLaneZ = batteryConnectorZ + xt60Span + 1.0

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
#
# Both cutouts sit over the board's REAR six millimetres, which is the strip of
# it nothing stands on: the board is pushed 6 mm forward in the bay for exactly
# that, and the connectors straddle the wall rather than hanging off its inside
# face, so each reaches about 10 mm in rather than its full body length.
panelX = powerX - 10.0


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

# THE CHARGE INLET IS AN AMASS XT60E-M, 2026-10-05: the eared male panel mount,
# the same part the main disconnect was until the button replaced it. It was the
# female XT60E-F for three weeks before that, a GX16-2 before that and an XT30
# before that.
#
# THE GENDER WAS TURNED ROUND BY CHOICE, AND AGAINST THE RULE THAT CHOSE THE
# FEMALE. That rule still holds: this inlet lands on the BMS's charge input, so
# it is live at pack voltage whenever cells are connected, and the half with the
# pins is the one that would rather be dead. The female is on the charger's lead
# instead, which is live only while the charger is on. What that costs is two
# pins at up to 25.2 V on the back of the robot, shrouded by the XT60's own
# housing but not recessed, and a short across them reaches the pack through the
# BMS's charge input and nothing else: nothing on this path is fused, and
# whether the BMS cuts a short on that input is untested. It also means the lead
# that charges the robot ends in a female XT60, where the lead that charges a
# bare pack ends in a male.
#
# WHY THE GX16 WENT, and it was not the panel hole: THE PANEL HALF CARRIED PINS,
# which was the same rule. Every stocked GX16 pair put the pins on the panel --
# the series datasheet's own package list is a male panel socket and a female
# wire plug -- and the reverse part was on no Indian shelf. Two more things the
# GX16 taught are worth keeping: it was also sold with a 3-hole circular flange
# that this wall was never drilled for, and docs/BOM.md linked that wrong variant
# until 2026-09-13; and its figures were an M16 x 1 thread, an S19 hex 21.94
# across corners, and 19 mm reserved inboard.
#
# EVERY FIGURE BELOW IS OFF AMASS'S DIMENSIONED DRAWING OF THE XT60E-M, the
# figures the disconnect was drawn to, and none is borrowed from the female: the
# two genders are different mouldings. The female's were a flange 34.00 x 15.80
# x 3.10 on the outside face, screws 25.00 apart, and 17.10 of body reaching
# 14.7 mm past the inner face through a 19.2 x 12.0 cut; the male is 27.00
# across, 20.00 between screws and 8.3 mm deep inside the wall.
#
# IT IS NOT A FLANGE, IT IS TWO EARS PARTWAY ALONG THE BODY, so it mounts the
# opposite way round from the female and goes in from inside. Along its axis it
# is 16.70 overall in three pieces: the mating nose stands 8.40 proud of the ear
# plate, the ear plate is 3.20 thick, and the rear body with its solder tabs is
# 5.10 behind that. So the ears bear on the INSIDE face of the wall, the nose
# passes through the cutout and stands 6.0 mm outside it, and the tabs the leads
# land on stay in the cavity.
#
# THOSE THREE AXIAL FIGURES ARE THE ONE THING HERE NOT READ STRAIGHT OFF A LABEL,
# and they are the first thing to measure on a real connector. The drawing's own
# side view labels the tab end to the ear plate 9.50 and the plate 4.00, which
# leaves 3.20 of nose -- and that cannot be right: it is contradicted by the same
# view's proportions, by AMASS's own photograph, in which the nose is plainly
# the longest section, and by the part's purpose, since 3.2 mm of nose through a
# 2.4 mm wall is 0.8 mm for a plug to grip. The figures above are the view's
# proportions at its 16.70 scale. IF A MEASURED PART SAYS THE LABELS WERE RIGHT,
# the body reaches 13.5 mm in, which this station has room for -- the female
# reached 14.7 -- but the nose would want the ears on the outside instead.
#
# THE CUTOUT IS CUT TO THE NOSE, NOT TO THE BODY -- 14.20 x 6.70 plus half a
# millimetre all round -- and that is forced rather than chosen. The ear holes
# are 20.00 apart and the body is 15.50 long, so a cutout sized to the body would
# run into them. AT 14.7 THERE IS 1.45 mm OF WALL BETWEEN THE CUTOUT AND EACH
# SCREW HOLE, the thinnest bridge on this wall again, at M2 -- and M2 is forced
# by the nuts, which cad/parameters.py sets out: each sits behind an ear, 2.25 mm
# from the side of the body.
#
# THE STATION MOVED 3.5 mm OUTBOARD, to x 59.0, AND 1 mm DOWN, AND IT IS THE WAY
# IN THAT MOVED IT. The male goes in from inside: it comes down in front of the
# wall and goes back until its nose is through the cutout, so before it can come
# down at all it has to stand 8.4 mm off the inner face with nothing in the way.
# Two things bound that. The ear plate's inboard tip has to pass the actuator
# harness bank's mated plugs, which end at x 44.95, and the nose, still under the
# rear right cover boss at that depth, has to pass inboard of the boss, which
# starts at x 66.55. That leaves x 58.45 to 59.45 and nothing else on this wall:
# at the female's 55.5 the ear plate sat 3 mm into those plugs, and tools/gate_i.py
# could find no straight way in. 59.0 is the middle, half a millimetre from each.
# It puts the rear body 0.2 mm under the boss in plan, which is what the
# millimetre down clears; chargeInletPanelZ says so where it is set.
chargeInletNoseWidth = 14.2
chargeInletNoseHeight = 6.7
chargeInletCutWidth = 14.7
chargeInletCutHeight = 7.2
chargeInletFixingPitch = 20.0
# The ear plate, which is what actually holds the connector: 27.00 tip to tip,
# 6.13 across and 3.20 thick, bearing on the inside face either side of the
# cutout. The rear body behind it is the 15.50 x 8.10 of the XT60 shell.
chargeInletEarSpan = 27.0
chargeInletEarWidth = 6.13
chargeInletEarThickness = 3.2
chargeInletBodyWidth = 15.5
chargeInletBodyDepth = 5.1
# How far the connector reaches either side of the wall it is bolted to. Outboard
# is the nose the charger's lead goes onto, measured from the wall's OUTER face;
# inboard is the ear plate and the rear body, measured from its inner face.
chargeInletOutboardDepth = 6.0
chargeInletInboardDepth = chargeInletEarThickness + chargeInletBodyDepth

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
# rather than a scatter. z = 23.5 is the only band that works: a window 20 mm
# tall has to clear the deck's top face at z = 9.5 underneath and the cover's lip
# at z = 39.7 above, which leaves its centre between 20.5 and 31.5. It was 22
# until the torso grew 3 mm under the deck on 2026-10-05, and 23.5 is the same
# place relative to the deck and the cover: this frame is the torso's centre,
# which rose by half of it.
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
# measures the lot. THE CHARGE INLET MOVED TO x 59.0 when it became a male on
# 2026-10-05, for its way in rather than for its place; its own block above says
# why, and the bridge it binds is its own 1.45 again.
panelHardwareZ = 23.5
buttonPanelX = -44.0
chargeInletPanelX = 59.0
# THE ONE STATION A MILLIMETRE OUT OF THE ROW, 2026-10-05. At x 59.0 the
# inlet's rear body stands 0.2 mm under the rear right cover boss, which comes
# down to z 27.3, and at the row's height the body's top edge is 27.55. A millimetre
# lower it is 0.75 clear, and the row the back of the robot reads as does not
# notice a millimetre.
chargeInletPanelZ = panelHardwareZ - 1.0
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
            "XT60E-M charge inlet",
            chargeInletPanelX,
            chargeInletPanelZ,
            chargeInletCutWidth,
            chargeInletCutHeight,
        ),
        (
            "SMA antenna bulkhead",
            antennaPanelX,
            panelHardwareZ,
            antennaHoleDiameter,
            antennaHoleDiameter,
        ),
    ]


def chargeInletFixings() -> list[tuple[float, float]]:
    """The XT60E-M's two ear screws, in the pelvis's own x and z.

    They are clearance holes and nothing else: the screw head takes the wall on
    the outside, with a washer under it, the connector's own ear plate sits
    against the inside face, and a nut behind the ear takes the load, so 2.4 mm
    of wall is CLAMPED rather than threaded.

    M2, AND THE NUT IS WHY. Each ear hole is 2.25 mm from the side of the
    connector's own body, and the nut sits in that gap: an M2's flats clear it by
    a quarter of a millimetre, where an M2.5 fouls it by the same, and the body
    then holds the nut square so the screw is turned from outside. No washer
    fits under that nut, which is why the washer is under the head. The wall
    keeps 1.45 mm between each screw and the nose cutout. The connector's own
    holes are 3.00, which leaves an M2 half a millimetre of adjustment each side
    -- the cutout, not the screws, is what locates the part.
    """
    half = chargeInletFixingPitch / 2
    return [
        (chargeInletPanelX - half, chargeInletPanelZ),
        (chargeInletPanelX + half, chargeInletPanelZ),
    ]


# ---- the BMS, between the two packs -------------------------------------------
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
# WHERE IT GOES IS BETWEEN THE TWO PACKS, since 2026-10-05, taped into one block
# with them. For three weeks it stood on edge in the gap between the battery and
# the power bay, in four card guides, and the first board in hand showed what
# that cost: its leads leave its two SHORT ends -- B-, the NTC pair and P- at one,
# the 7-way balance socket at the other -- and stood across the gap those ends
# faced the shell walls 4.6 mm away, while the board itself was a wall across the
# only path the packs' main leads had to the power bay.
#
# Between the packs, its length runs across the robot like theirs and both ends
# have somewhere to go. ITS POWER END IS AT THE PACKS' 65 mm BODY LINE and no
# further: past it the lead ends may be 19 mm thick, and the gap between the two
# lead ends is then 7 mm at worst, which is the lane its three leads pass out
# through, B- at the top and P- at the bottom, into the bay gap.
# ITS BALANCE END IS THEN 10 mm OFF THE LEFT WALL, which takes the 7-way plug and
# the fold of its thin wires up over the board's top edge, where they run back to
# the packs' own balance leads at the other end. It stands on the same plane the
# packs do, on the left hip saddle's top, and is held by being in the block.
#
# THE BOARD IN HAND HAS FOUR HOLES that its vendor table never mentioned. Nothing
# here uses them, because nothing has to: tape and the squeeze of the foam on the
# block hold it, and screws through a board that the packs press on from both
# sides would only be four more things to undo.
#
# THE BOARD IS THE DALY Li-ion NMC 6S 24V 20A, chosen 2026-09-13, and everything
# here is drawn to it. Its vendor specification table gives length 58, width 33,
# height 8.2 mm and 45 g, and the first three are the numbers this file uses --
# up in the battery block, because the board's thickness is the gap between the
# packs; the board in hand weighed 40 g on 2026-10-05. It was
# chosen on two counts and neither of them is its current rating, which is very
# nearly irrelevant on a charge-only board seeing 2.2 A: it BALANCES -- 30 mA
# passive, from 4.18 V per cell -- and it is the only balancing 6S board found
# that FITS. The 30 A boards in the same family are 75 mm long, and the cheap
# generic protection boards that would fit balance nothing at all, which is the
# one job this board is here to do.
#
# ITS THICKNESS NO LONGER MOVES ANYTHING, as long as the block it is built into
# is the 45 mm the torso is laid out to: what the board does not take of the
# 11 mm between the packs is tape and padding, and is the builder's.
bmsX = batteryPackBodyEndX - bmsBoardLength / 2
bmsY = 0.0
bmsBoardBottomZ = lowerBandZ
bmsBoardTopZ = bmsBoardBottomZ + bmsBoardHeight


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
    connectors from board x 43 to x 118, and the rear outboard corner is
    notched for the charge socket that stood over it until 2026-10-05. electrical/carrier_pcb.py places the holes and
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


# ---- the power switch board, which is the distribution board now -------------
#
# A SECOND BOARD OF OUR OWN, September 2026, and electrical/power.py says what is
# on it: the main fuse, a MOSFET switch that is the robot's on/off and its
# low-battery cutoff, and since 2026-10-07 the bus's distribution as well -- six
# motor outputs and the carrier's feed, each on a plug. It takes the pack's leads
# in and hands the switched bus out, which is why it is down here in the power
# bay rather than on the deck with the carrier. SINCE THE LOOP KEY WENT the
# pack's own connector, mated inside the shell, is what makes and breaks it.
#
# THE BOUGHT DISTRIBUTION BOARD IS GONE, 2026-10-07, and this board stands where
# it stood. That board was a SwiftWing PDB-02-XT60 under this one, and every
# motor lead was soldered to its tabs before this board went over it, so changing
# one meant taking both boards out and unsoldering. The robot's own motor plug,
# a JST-SH with three 1 A contacts a side, is what limits a branch's current, so
# the outputs here are JST-PH 4-pin headers, two 2 A contacts a side, on this
# board's own copper. PH is a family nothing else in the robot uses -- every
# other plug on both boards is XH, at 2.5 mm against PH's 2.0 -- so a motor's
# power lead cannot go into a signal socket.
#
# HOW IT IS HELD. Four M3 self-tapping screws from above, which is the only
# direction a screwdriver has in this bay, through an M3 nut on a washer that
# stands the board 3 mm off each printed post: the bought board's own four
# screws and posts, on the same 45 mm square, so the pelvis does not change at
# all. They were M3 x 20 through an 8 mm spacer and both boards while there were
# two; one board on the nuts takes the M3 x 8 the bought board took alone.
#
# THE BOARD IS 9.6 mm LOWER THAN IT WAS, which is the bought board and the
# spacer, and the room went where it was short: the two TO-220 rows had 1.1 mm
# under the deck and the inboard column had 7.4 mm under the pack's connectors.
# And with nothing under it but the posts, its trimmed leads hang into 1 mm of
# air over the post tops rather than over another board's XT60 socket.
powerSwitchBoardZ = pdbBoardZ
# The bank stands on THIS board, as it has since the board covered the bought
# one: a can on that board would have been 16 mm tall under 8 mm of air.
capacitorZ = round(powerSwitchBoardZ + pcbThickness, 6)
# IT WAS THE BOUGHT BOARD'S OWN FOOTPRINT from September 2026, and a 54 x 32.5
# rectangle over the rear half of that board before this file's second pass. Two
# things drove that change and the second is the interesting one.
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
#
# AND IT REACHES BOTH LONG WALLS NOW, 2026-10-07: 50 x 66 rather than 50 x 50,
# still on the same four holes. The bought board's footprint was the limit only
# while this board sat on it. The bay was swept from under the post tops to the
# deck and the two 8.6 mm strips between the old edges and the walls held
# nothing, so the board goes to within powerSwitchWallGap of each wall and the
# six motor outputs stand in those strips, three along each. Across the robot it
# keeps its 50 mm: the shell wall is 3 mm off the outboard edge and the pack's
# leads pass half a millimetre off the inboard one.
#
# IT DOES NOT GO STRAIGHT DOWN, because it cannot: the deck's two ledges on this
# side stand 6 mm proud of each long wall at x 46 to 58, 29 mm over the board,
# and the lid's two screw bosses stand over its outboard corners. So it goes in
# SIDEWAYS, which tools/gate_i.py runs. It is the first thing into the torso, so
# the battery bay beside it is empty: down 30 mm inboard of its station, clear of
# both, then outboard UNDER the ledges and the bosses, and the last 5 mm down onto
# the nuts.
#
# IT WAS NOTCHED ROUND THE LEDGES FOR A DAY, 2026-10-07, so that it could drop
# past them, and the notches split each strip in two. Sliding in under the ledges
# needs no notch. The headers stayed where the notches had put them -- two at
# the inboard end of each strip, one at the outboard end -- because that is
# where the copper that feeds them was already routed.
powerSwitchWallGap = 0.6
powerSwitchRightX = round(powerX + (pdbWidth / 2), 6)
powerSwitchLeftX = round(powerX - (pdbWidth / 2), 6)
powerSwitchRearY = round(-(interiorHalfDepth - powerSwitchWallGap), 6)
powerSwitchFrontY = round(interiorHalfDepth - powerSwitchWallGap, 6)


def power_switch_outline() -> list[tuple[float, float]]:
    """The board's edge, anticlockwise from its rear inboard corner, torso x and y."""
    left, right = powerSwitchLeftX, powerSwitchRightX
    rear, front = powerSwitchRearY, powerSwitchFrontY
    return [(left, rear), (right, rear), (right, front), (left, front)]


def power_switch_screw_xy() -> list[tuple[float, float]]:
    """The four screws, on the 45 mm square the bought board and its posts used."""
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
#   P5  the shell XT60's charge positive, on the same raw rail as P1
#   F1  the fuse, in a mini-blade holder, with its blade clear of the pack leads'
#       chase over the rear corner
#   Q1  the switches, two rows of two, each row with its sources meeting in the
#   Q2  middle so one pour feeds both and one takes both drains. THE SECOND ROW
#   Q6  IS FED FROM THE BOTTOM LAYER: VBUS is a top-layer pour, so the copper
#   Q7  under it is free for VSRC to run forward to the front row's sources.
#       There are four since 2026-09-22, when the switch became an IRF4905 --
#       20 mOhm against the obsolete part's 6.7, so the current is shared wider.
#   P3  the pack's negative in, 14 AWG, and P4 the BMS's B- beside it, 16 AWG:
#   P4  both on the inboard edge, where the BMS's lane reaches the board. P3 was
#       a 22 AWG ground from the bought board's negative until that board went
#   C5  the bulk bank, two cans on the bus copper they damp -- they stood on the
#   C6  bought board until this board covered it
#   J3  the button and J2 both holds, along the front
#   J4  the six motor outputs, JST-PH 4-pin: 1 and 2 the switched bus, 3 and 4
#   ..  ground. J4 to J6 along the rear strip, J7 to J9 along the front one,
#   J9  turned so each one's bus pins face the copper that feeds them
#   J10 the carrier's feed, JST-XH 3-pin: 1 and 2 the bus, 3 ground. Three so
#       that its one ground pin is all the bus copper under it has to step
#       round; it stands where P2 handed the bus to the bought board
#
# THE OLD RULE FOR THE INBOARD COLUMN IS GONE with the 9.6 mm the board came
# down. It kept anything over 7.4 mm out from under the pack's connectors while
# they hung over this corner; electrical/power_pcb.py measures every part
# against the drawn torso rather than trusting a note either way.
powerSwitchStations = {
    "P1": (33.0, -21.5, 0),
    "P5": (39.0, -21.5, 0),
    "F1": (47.0, -20.5, 0),
    "Q1": (50.0, -15.0, 0),
    "Q2": (66.08, -15.0, 180),
    "Q6": (50.0, -6.0, 0),
    "Q7": (66.08, -6.0, 180),
    "P3": (25.5, -15.5, 0),
    "P4": (24.5, -9.8, 0),
    "C5": (33.0, 3.0, 0),
    "C6": (44.0, 3.0, 0),
    "J3": (34.0, 20.5, 0),
    "J2": (54.5, 20.5, 0),
    "J4": (24.1, -29.6, 0),
    "J5": (36.85, -29.6, 0),
    "J6": (61.95, -29.6, 0),
    "J7": (30.1, 29.6, 180),
    "J8": (42.85, 29.6, 180),
    "J9": (67.95, 29.6, 180),
    "J10": (30.2, -6.0, 0),
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


def powerSwitchBoard():
    """The power switch board on its own, so its four holes can be counted.

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
# to leave is 12.8 -- the figure the controller carrier already uses. A header's
# box is its KiCad courtyard: an XH's 2.95 mm past the end pins and from 2.85
# behind the pin row to 3.9 in front of it, so the three-pin's is 10.9 long; a
# PH four-pin's is 10.9 by 5.5, 2.45 past the end pins, 2.2 behind and 3.3 in
# front. A PH plug stands about 8 mm off the board, and with the same 3 mm for
# its wires that is 11 -- a catalogue-class figure, not a measured one.
xhDepth = 6.75
xhPinOffset = -0.525
phDepth = 5.5
phPinOffset = -0.55
phHeight = 11.0
powerSwitchBodies = {
    "P1": [(4.4, 4.4, 12.0, 0.0, 0.0, 0.0)],
    "P5": [(4.4, 4.4, 12.0, 0.0, 0.0, 0.0)],
    "P3": [(4.4, 4.4, 12.0, 0.0, 0.0, 0.0)],
    "P4": [(3.9, 3.9, 12.0, 0.0, 0.0, 0.0)],
    **{
        f"J{n}": [(10.9, phDepth, phHeight, 3.0, phPinOffset, 0.0)]
        for n in range(4, 10)
    },
    "J10": [(10.9, xhDepth, harnessHeight, 2.5, xhPinOffset, 0.0)],
    "F1": [
        (16.0, 6.74, 7.37, 4.96, -1.7, 0.0),
        (10.9, 3.8, 9.0, 4.96, -1.7, 7.37),
    ],
    "Q1": [(10.0, 4.4, 18.8, 2.54, 0.95, 0.0)],
    "Q2": [(10.0, 4.4, 18.8, 2.54, 0.95, 0.0)],
    "Q6": [(10.0, 4.4, 18.8, 2.54, 0.95, 0.0)],
    "Q7": [(10.0, 4.4, 18.8, 2.54, 0.95, 0.0)],
    "J2": [(13.4, xhDepth, harnessHeight, 3.75, xhPinOffset, 0.0)],
    "J3": [(8.4, xhDepth, harnessHeight, 1.25, xhPinOffset, 0.0)],
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
    """The two 3S packs, on edge, side by side: rear, then front.

    Drawn as two bodies and not as one block, because the gap between them is
    real: cad/torso.py's fin stands in it. Each is its 65 mm body and its lead
    end united, the lead end centred on the body because nobody knows which way
    its extra falls -- see the measured figures above.
    """
    offset = (batteryPackGap + batteryPackThickness) / 2
    leadLength = batteryPackLength - batteryPackBodyLength
    packs = []
    for sy in (-1, 1):
        body = slab(
            batteryPackBodyLength,
            batteryPackThickness,
            batteryPackWidth,
            batteryPackLeftX + batteryPackBodyLength / 2,
            sy * offset,
            lowerBandZ,
        )
        leadEnd = slab(
            leadLength,
            batteryPackLeadThickness,
            batteryPackLeadWidth,
            batteryPackBodyEndX + leadLength / 2,
            sy * offset,
            lowerBandZ - (batteryPackLeadWidth - batteryPackWidth) / 2,
        )
        packs.append(body + leadEnd)
    return packs


# How far every piece of foam beside or over a pack stops short of its lead end,
# so that none of it bears on the part of the pack that is not a promise.
batteryFoamLeadAir = 2.0


def batteryFoam() -> list:
    """The foam round the block, drawn SQUEEZED, as it is with the deck down.

    Four pieces cut from one sheet, each pair front then rear: a pad over each
    pack under the deck, and a pad on each pack's left end against the wall --
    two where there was one across both, because the BMS's balance plug sits
    between them. There were four more until 2026-10-06, a low and a high strip
    down each pack's outer face against the wall pads; the pads bear on the
    block itself now.

    The end pads go onto the left wall and the top pads under the deck. Drawn
    at the thickness each is squeezed to, touching what it is squeezed between,
    so tools/gate_h.py sees every face it bears on as a contact and anything
    else as a clash; tools/gate_f.py holds each thickness to the free sheet,
    which is what says it still pushes.
    """
    topLength = batteryPackBodyEndX - batteryFoamLeadAir - batteryPackLeftX
    pads = [
        slab(
            topLength,
            batteryPackThickness,
            batteryFoamTop,
            batteryPackLeftX + topLength / 2,
            sy * (batteryPackGap / 2 + batteryPackThickness / 2),
            batteryPackTopZ,
        )
        for sy in (1, -1)
    ]
    endPads = [
        slab(
            batteryFoamEnd,
            batteryPackThickness,
            batteryPackWidth - 12.0,
            -interiorHalfWidth + batteryFoamEnd / 2,
            sy * (batteryPackGap / 2 + batteryPackThickness / 2),
            lowerBandZ + 6.0,
        )
        for sy in (1, -1)
    ]
    return [*pads, *endPads]


# Where each pack's two main leads leave its end face: at mid-thickness, this far
# in from the body's bottom and top edges. Read off the packs in hand.
batteryLeadInset = 7.0


def batteryHarness() -> list:
    """The space the battery's wiring needs, as chases: one group of solids.

    NOT A ROUTED HARNESS. Every body here is a volume a set of leads has to pass
    through, sized by the leads' own diameter and the radius a stiff lead turns
    at, so that tools/gate_h.py and tools/gate_f.py can show nothing else was
    designed through it. Where two chases overlap, the leads in them cross.

    For each pack, front then rear: its two main leads turning in the bay gap
    into the strip beside it, the stiff joint into its connector, and the series
    harness's legs turning up off the far end and running back along the top of
    the strip. Then, shared: the top of the bay gap, which the legs cross to the
    power bay and the balance and P- leads use too; the pack positive's run over
    the power switch board's inboard rear corner to its input, P1; the BMS's
    lane out between the packs' lead ends and on to the power switch board's
    inboard edge, which carries B- to its P4, P- and the NTC pair; P- up
    through the deck's rear notch to the charge inlet; and the 7-way balance
    lead, from its plug at the BMS's left end, over the board's top and out
    through the same lane.
    """
    laneHalf = xt60Width / 2
    laneOuterY = batteryConnectorY + laneHalf
    leadMidY = batteryPackGap / 2 + batteryPackThickness / 2
    gapRight = batteryPackRightX + batteryLeadReach
    legsTopZ = batteryLegLaneZ + busWireDiameter
    connectorTopZ = batteryConnectorZ + xt60Span
    uTurnLeftX = batteryConnectorLeftX - batteryLegReach
    leadLow = lowerBandZ + batteryLeadInset - busWireDiameter / 2
    leadHigh = batteryPackTopZ - batteryLeadInset + busWireDiameter / 2
    # The lane between the two lead ends, at their worst, less the air.
    lane = batteryPackGap / 2 - (batteryPackLeadThickness - batteryPackThickness)
    lane -= harnessAir
    bmsLeftX = bmsX - bmsBoardLength / 2

    def box(x0, x1, y0, y1, z0, z1):
        return slab(x1 - x0, y1 - y0, z1 - z0, (x0 + x1) / 2, (y0 + y1) / 2, z0)

    chases = []
    for sy in (1, -1):

        def ys(a, b):
            return (min(sy * a, sy * b), max(sy * a, sy * b))

        chases += [
            # the U from the end face into the strip
            box(
                batteryPackRightX,
                gapRight,
                *ys(leadMidY - busWireDiameter, laneOuterY),
                leadLow,
                leadHigh,
            ),
            # the stiff joint into the pack's own female
            box(
                batteryConnectorRightX,
                batteryPackRightX,
                *ys(batteryConnectorY - laneHalf, laneOuterY),
                batteryConnectorZ,
                connectorTopZ,
            ),
            # the harness's legs, up off the male's far end
            box(
                uTurnLeftX,
                batteryConnectorLeftX,
                *ys(batteryConnectorY - laneHalf, laneOuterY),
                batteryConnectorZ,
                legsTopZ,
            ),
            # and back along the top of the strip to the bay gap
            box(
                uTurnLeftX,
                batteryPackRightX,
                *ys(batteryConnectorY - laneHalf, laneOuterY),
                batteryLegLaneZ,
                legsTopZ,
            ),
        ]

    p1X, p1Y, _ = powerSwitchStations["P1"]
    chases += [
        # the top of the bay gap, wall to wall
        box(
            batteryPackRightX,
            gapRight,
            -laneOuterY,
            laneOuterY,
            batteryLegLaneZ,
            deckZ - harnessAir,
        ),
        # the pack positive, over the power switch board's rear inboard corner
        box(
            gapRight,
            p1X + busWireDiameter / 2,
            p1Y - busWireDiameter / 2,
            p1Y + busWireDiameter / 2,
            batteryLegLaneZ,
            legsTopZ,
        ),
        # the BMS's lane: out between the lead ends and on to the power board
        box(
            batteryPackBodyEndX,
            powerSwitchLeftX - harnessAir,
            -lane,
            lane,
            bmsBoardBottomZ + 1.0,
            bmsBoardTopZ + 3.5,
        ),
        # P- up through the deck's rear notch, towards the charge inlet
        box(
            gapRight - busWireDiameter / 2 - 1.0,
            gapRight,
            -(interiorHalfDepth - 1.0),
            -(interiorHalfDepth - 5.0),
            deckZ - harnessAir,
            deckBandZ,
        ),
        # the 7-way balance lead, over the BMS's top edge
        box(
            bmsLeftX,
            batteryPackBodyEndX,
            -3.0,
            3.0,
            bmsBoardTopZ + harnessAir,
            bmsBoardTopZ + 3.5,
        ),
        # and its plug, and the fold of its wires, at the board's left end
        box(
            -interiorHalfWidth + harnessAir,
            bmsLeftX,
            -3.0,
            3.0,
            bmsBoardBottomZ + 8.0,
            bmsBoardTopZ + 3.5,
        ),
    ]
    return chases


# ---- what each group is, as a thing you can buy ------------------------------
#
# WHAT THE PARENTHESIS IN A TREE NODE MEANS. cad/scenes.py and tools/view.py name
# every payload body by what it IS -- "logic BEC", "on/off button" --
# and that is the right name for a clearance to be reported against, but it is
# not the name on an order. This table is the other half: the designation that
# identifies the part, so a tree node reads "logic BEC (Matek BEC12S-PRO)"
# and the thing on the bench can be matched to the thing in the
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
#   part is a commodity -- an M3 brass standoff, a foam sheet. The battery was
#   one until 2026-09-30, when it turned out that no pack of the capacity named
#   was the size drawn: it is a named pack now, because the bay is only right
#   for one whose size is known;
#
#   an open question, said plainly. The capacitor bank has never been sized and
#   the fuse's rating waits on a measured bus current, so those two say so. A
#   node that reads "(not sized)" is worth more than a node that reads nothing,
#   because nothing is also what a chase reads.
#
# The chases, the looms and the features of a board that is already named -- the
# SBC's header, its ports, its microSD slot -- are not parts and are not here.
partNumbers = {
    "battery packs": "2 x Bonka 3S 1000 mAh 35C LiPo, XT60",
    "battery foam": "5 mm anti-static EVA sheet, cut to fit",
    "battery pack connectors": "2 x AMASS XT60, each pack's female mated with a male of the series harness",
    "battery leads": "XT60 2M1F series harness, its female cut off; the packs' and the BMS's own leads",
    "power switch standoffs": "M3 hex nut on a 0.5 mm washer, 2.9 mm",
    "capacitor bank": "2 x Rubycon 35ZLH470M10X16, 470 uF 35 V -- bank not sized",
    "power switch board": "ours -- 50 x 66 mm two-layer PCB, electrical/power_pcb.py",
    "power switch parts": "the fuse, the switch and the outputs -- electrical/power.py",
    "bus monitor": "INA226, bus voltage only -- no external shunt",
    "logic BEC": "Matek BEC12S-PRO",
    "on/off button": "12 mm panel-mount momentary push button, M12 x 1 bushing",
    "charge inlet": "AMASS XT60E-M panel mount, pin contacts",
    "antenna bulkhead": "SMA or RP-SMA bulkhead jack on a u.FL pigtail",
    "controller standoffs": "M3 brass, 6 mm A/F x 3 mm",
    "controller carrier board": "ours -- 140 x 46 mm two-layer PCB, electrical/carrier_pcb.py",
    "SBC standoffs": "M2.5 x 10 female-female hex standoff, 5 mm A/F, on M2.5 x 6 SHCS",
    "CAN transceivers": "MCP2562FD-E/P, 8-pin PDIP, in sockets",
    "WeAct core board": "WeAct STM32G474CEU6",
    "SBC board": "Banana Pi BPI-M4 Zero",
    "BMS board": "Daly Li-ion NMC 6S 24V 20A, 58 x 33 x 8.2 mm, 40 g -- balancing, wired charge-only",
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

    groups = {
        # ---- the battery ----------------------------------------------------
        "battery packs": batteryPacks(),
        "battery foam": batteryFoam(),
        # EACH PACK'S XT60, mated with one male of the series harness, lying in
        # the strip between that pack's outer face and the long wall, over the
        # low wall pads. Drawn as the mated pair of housings; the stiff joint at
        # each end and everything that bends are battery leads, below.
        "battery pack connectors": [
            slab(
                batteryConnectorLength,
                xt60Width,
                xt60Span,
                (batteryConnectorLeftX + batteryConnectorRightX) / 2,
                sy * batteryConnectorY,
                batteryConnectorZ,
            )
            for sy in (1, -1)
        ],
        # THE BATTERY'S WIRING, as chases rather than wires: the space the leads
        # need to turn in, kept clear of everything else, because a 14 AWG lead
        # cannot be bent into a gap that was never left for it. One group, so the
        # leads may cross one another as real ones do. See batteryHarness().
        "battery leads": batteryHarness(),
        # ---- power entry: our own board and what stands on it ----------------
        # THERE IS NO BOUGHT BOARD HERE ANY MORE, 2026-10-07. A SwiftWing
        # distribution board stood on these nuts with the power switch board 8 mm
        # over it on printed spacers, and every motor lead was soldered to it
        # underneath. The power switch board stands on the nuts itself now and
        # carries the motor outputs as plugs.
        "power switch standoffs": [
            standoff(
                standoffDiameter,
                standoffHeight,
                atX,
                atY,
                lowerBandZ,
            )
            for atX, atY in power_switch_screw_xy()
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
        # ---- the power switch board, on the posts' own four screws -----------
        #
        # THE FUSE HOLDER USED TO BE HERE, a 20 x 10 x 14 block taped to the
        # bought board's top face. It is a part ON this board now -- a mini blade
        # holder soldered into it -- and so is the MOSFET switch, which had no home
        # in the CAD because the bill had never bought one.
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
        # THE INLET IS THREE BODIES AND NOT ONE, because the XT60E-M is three
        # different sections along its axis, and the ears are inside the wall
        # with the nose through it -- the disconnect's way round, and the
        # opposite of the female's flange outside. The nose is what stands
        # outside, the ear plate is what bears on the inside face, and the rear
        # body with its solder tabs is what the cavity has to keep clear of.
        "charge inlet": [
            # The nose, from where the charger's plug meets it to the wall's
            # inner face.
            slab(
                chargeInletNoseWidth,
                chargeInletOutboardDepth + shellWall,
                chargeInletNoseHeight,
                chargeInletPanelX,
                outerWallY - (chargeInletOutboardDepth / 2) + (shellWall / 2),
                chargeInletPanelZ - (chargeInletNoseHeight / 2),
            ),
            # The ear plate, flat against the inside face.
            slab(
                chargeInletEarSpan,
                chargeInletEarThickness,
                chargeInletEarWidth,
                chargeInletPanelX,
                innerWallY + (chargeInletEarThickness / 2),
                chargeInletPanelZ - (chargeInletEarWidth / 2),
            ),
            # The rear body and its solder tabs, which is what reaches furthest
            # into the cavity: 8.3 mm past the inner face, where the female's
            # body reached 14.7.
            slab(
                chargeInletBodyWidth,
                chargeInletBodyDepth,
                xt60Width,
                chargeInletPanelX,
                innerWallY + chargeInletEarThickness + (chargeInletBodyDepth / 2),
                chargeInletPanelZ - (xt60Width / 2),
            ),
            # Its two nuts, on the back of the ear plate beside the body -- the
            # quarter of a millimetre between them is why these screws are M2.
            *[
                slab(
                    m2NutAcrossFlats,
                    m2NutThickness,
                    m2NutAcrossFlats,
                    atX,
                    innerWallY + chargeInletEarThickness + (m2NutThickness / 2),
                    atZ - (m2NutAcrossFlats / 2),
                )
                for atX, atZ in chargeInletFixings()
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
        # Between the two packs, its length across the robot since 2026-10-05.
        "BMS board": [
            slab(
                bmsBoardLength,
                bmsBoardThickness,
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
        # rather than up the back of it where the charge inlet reaches in --
        # which since 2026-10-05 is where it actually is, at the back of the bay
        # gap. It stood under the battery's rear strip until the rear pack's
        # connector needed that strip.
        "CAN loom": [
            Pos(loomRunX, loomRunY, floorZ)
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
        # THE BOARD ITSELF since it went between the packs, 2026-10-05, inside
        # the battery's own reservation: a bay of its own is a bay nothing else
        # may use, and the board needs none.
        slab(
            bmsBoardLength,
            bmsBoardThickness,
            bmsBoardHeight,
            bmsX,
            bmsY,
            bmsBoardBottomZ,
        ),
    ]


def torsoPayload() -> list:
    """Both together, and what the assemblies place."""
    return [*torsoElectronics(), *torsoReservations()]
