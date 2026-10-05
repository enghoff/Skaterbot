# The controller carrier

The carrier is the only board on this robot that nobody sells. It is 140 × 46 mm
standing on six M3 pillars on the electronics deck, and it holds the WeAct core
board on sockets, three CAN-FD transceivers in DIP-8 sockets, the logic BEC and
the bus monitor, a handful of passives, and the connectors that every other
piece of electronics in the torso plugs into. **The single-board computer stands
on it too**, on four M2.5 standoffs, since 14 September 2026. It was a sheet of 2.54 mm
perfboard until 14 September 2026; it is a two-layer printed board now, still
entirely through-hole, and the section [The printed board](#the-printed-board-2026-09-14)
is the layout. [`cad/electronics.py`](../cad/electronics.py) draws its envelope
so the torso can be packed around it. This document and
[`electrical/carrier.py`](../electrical/carrier.py) say what is soldered to what.

**It was 76 × 46 mm until the same day**, carrying neither the BEC nor the
monitor: both were separately mounted down in the power bay with cables running
up to this board. The section below says what moving them cost and bought.

The netlist is the source, not the drawing:

```
uv run electrical/carrier.py            # check it, then print the tables
uv run electrical/carrier.py --draw     # also rewrite electrical/carrier.svg
```

[`electrical/carrier.svg`](../electrical/carrier.svg) is generated from the same
tables the checks run against, so it cannot disagree with them. Free and
offline, like everything else here.

**What the check actually proves.** That every pin of every part is on exactly
one net or excused by name; that no net is a dead end; that each MCU signal sits
on a pin the STM32G474 can give that peripheral, on the header pin that really
carries that port, with no port asked to do two jobs; and that no transceiver
has lost a supply. Three deliberate mistakes were fed to it — a bus on a pin
with no such peripheral, the right port moved to the wrong header pin, and a
transceiver with `VIO` left off — and it named every one, including the pin
collision the second of them caused two rows further down. It cannot tell you
the design is a good one.

## What the board has to do

Six motors, one IMU, one bus monitor and one single-board computer, and the
carrier is where all of it meets. It carries no motor power at all: each
actuator's OEM pigtail is split in the torso, the three `VCC`/`GND` pairs go to
an XT30 fed from the bought distribution board, and only the CAN pair comes up
here. That is what keeps a hand-soldered perfboard out of a 24 V, 10 A path.

## The three buses, and why nothing here is terminated

The G474 has three CAN controllers and the six motors sit two to a bus, paired
left and right by joint — both hips, both knees, both wheels. Each bus is then a
single line with a motor at each end and the carrier in the middle of it: one
cable in, one cable out, the transceiver tapped on at the junction. Both far ends
are a motor, both motors keep their own 120 Ω switched in, and **no termination
resistor goes on this board**. Keep two 120 Ω in the box anyway, against a motor
whose switch cannot be reached.

The motors default to CAN 2.0B at 1 Mbit/s, so the bus is at the speed where
Microchip stop recommending a common-mode choke rather than past it. If the data
phase is ever raised into CAN FD, that is the point to revisit — and to revisit
the stub length too, though at ~30 mm across the board it is not the thing that
will break first.

## Pin map

Every row was checked against ST's own alternate-function table and against
WeAct's schematic, not against memory.

| Net | STM32 pin | Function | Header | Note |
|---|---|---|---|---|
| `CANA_TX` | PA12 | FDCAN1_TX | P1-14 | |
| `CANA_RX` | PA11 | FDCAN1_RX | P1-13 | |
| `CANB_TX` | PB13 | FDCAN2_TX | P1-6 | |
| `CANB_RX` | PB12 | FDCAN2_RX | P1-5 | |
| `CANC_TX` | PB4 | FDCAN3_TX | P1-19 | JTAG pin at reset |
| `CANC_RX` | PA8 | FDCAN3_RX | P1-10 | |
| `I2C_SCL` | PA15 | I2C1_SCL | P1-15 | JTAG pin at reset |
| `I2C_SDA` | PB7 | I2C1_SDA | P1-22 | |
| `SBC_MCU_TXD` | PA9 | USART1_TX | P1-11 | |
| `SBC_MCU_RXD` | PA10 | USART1_RX | P1-12 | |
| `IMU_INT` | PB5 | GPIO | P1-20 | |
| `IMU_RST` | PB6 | GPIO | P1-21 | |
| `INA_ALERT` | PB15 | GPIO | P1-8 | |
| `BOOT0` | PB8 | boot select | P1-23 | out to the SBC |
| `NRST` | — | reset | P2-19 | out to the SBC |

**PA15 and PB4 are JTAG pins out of reset**, and firmware has to take them off
JTAG before they are a CAN transmitter and an I²C clock. Both sit as inputs with
weak pull-ups until it does, which is the harmless direction for both: a CAN
`TXD` held high is recessive and an I²C clock held high is idle. PB3, the third
JTAG pin, is deliberately left unused so SWO tracing still has somewhere to go.

## Connectors

All JST-XH, **2.50 mm** — which is the pitch JST actually make and not the
2.54 mm this document said until the board was laid out. On perfboard the
difference was absorbed by bending the posts: 0.12 mm over a 4-pin housing is
nothing, 0.2 mm over a 6-pin is a push. On a fabricated board it is simply the
right hole spacing, and the footprints use it.

| | | |
|---|---|---|
| **J1** | 2-pin | 1 `VBAT`, 2 `GND` — the raw battery bus in, from the distribution board |
| **J2** | 4-pin | bus A: 1 H, 2 L to the left hip; 3 H, 4 L to the right hip |
| **J3** | 4-pin | bus B, the two knees, same order |
| **J4** | 4-pin | bus C, the two wheels, same order |
| **J5** | 8-pin | the SBC: 1 and 2 `GND`, 3 and 4 `+5V`, 5 MCU→SBC, 6 SBC→MCU, 7 `BOOT0`, 8 `NRST` |
| **J6** | 6-pin | IMU: 1 `SCL`, 2 `GND`, 3 supply, 4 `INT`, 5 `RST`, 6 `SDA` |
| **J7** | 2-pin | **spare.** It was the shunt's sense pair, 1 `IN+`, 2 `IN−`, until the current measurement was deleted on 2026-09-16. Link both pins to ground rather than leaving the monitor's inputs floating |
| **JP1** | 3 pads | IMU supply link: bridge 1–2 for 5 V, 2–3 for 3.3 V |

**Three of these changed on 14 September 2026, when the BEC and the monitor came
onto the board.** J1 was the 5 V coming in from a BEC mounted elsewhere and is
the raw pack bus now, through the fuse and into the BEC's own input pin. J7 was
the monitor's five-wire I²C lead: that bus no longer leaves the board at all, and
the number has been reused for the shunt's sense pair, which does. J5 grew from 5 pins to
8 because the SBC's 5 V comes off this board as well as its serial link, on two
conductors each. **Two pins that are the same net are always adjacent in these
housings** — 5 V on 3 and 4, ground on 1 and 2 — because a crimp that misses is
then a lost conductor rather than a dead rail.

Each bus connector's pins 1/3 and 2/4 are the same net. That is the junction
that puts the carrier on the line rather than off it, and it is the only place
on this board where two wires meet at a pin.

`BOOT0` and `NRST` leaving on the SBC's connector is worth a sentence of its
own. USART1 is one of the ports the STM32's ROM bootloader listens on, so with
those two lines the Banana Pi can reset the MCU into its bootloader and reflash
it over the same three wires. On a robot whose controller lives under a
screwed-down lid, that is the difference between a firmware update and a
teardown.

## Power

The raw pack bus arrives on J1, passes through a 1.85 A resettable fuse and a
10 µF of bulk, and goes into the BEC and nowhere else. The 5 V the BEC makes
does three things: it feeds the three transceivers' `VDD` directly, it feeds the
SBC out on J5, and it feeds the core board's own regulator through P1-1/2. The 3.3 V that regulator makes comes back out on P2-1/2 and sets
the logic level on every transceiver's `VIO`. That split is the whole reason the
bill buys MCP2562FD rather than MCP2561FD — the 2561 has no separate I/O supply
and would drive 5 V logic into a 3.3 V microcontroller.

Two things about the core board's supply that are easy to be bitten by. Its
regulator is small, so the 3.3 V rail is for the MCU, the `VIO` pins and the
pull-ups and not for anything that draws real current — which is why the IMU's
link defaults to 5 V. And `SB9` on the core board ties the rail you are feeding
to the USB-C connector's `VBUS` pin, so either do not plug a host into the core
board while the robot is powered, or cut `SB9`.

Decoupling is nine capacitors: 100 nF at both `VDD` and `VIO` of every
transceiver, one more on the 3.3 V beside the sensor connectors, 10 µF of bulk
on the 5 V, and a second 10 µF on the bus where it arrives — that last one for
the lead's own inductance when the switch board's MOSFETs open. The two
4.7 kΩ I²C pull-ups go on only if neither sensor module brings its own.

The transceivers' `STBY` pins are tied to ground rather than driven. They have
about 1.1 MΩ of pull-up inside, so a pin left floating is standby and not normal
mode, and nothing on this robot wants a transceiver asleep. A line that has to
be driven correctly before any bus works is one more thing to get wrong at
bring-up.

## Four places this disagreed with docs/BOM.md, and all four are settled

**The bill named two different core boards, and now names one.** Its purchase
link was WeAct's *long type*, which is 63.06 × 18.24 mm with two 1 × 20 headers,
while its quoted dimension, its carrier assembly note and `cad/electronics.py`
all described the compact board, 36.53 × 28.40 mm with two 2 × 12 headers. Both
numbers were measured off the vendor STEP files, so it was not a rounding
disagreement — it was two boards. **This schematic is drawn to the compact one**,
because that is what the CAD packs and what the carrier layout has room for; a
63 mm board does not fit the strip of carrier the SBC leaves. The bill buys the
compact board from WeAct's own shop since 14 September 2026, and says plainly
that both Indian listings are the long one.

**The header line followed from that, and it is corrected.** It said
"2 × 2.54 mm 1 × 20 female header", which is right for the long board and wrong
for this one, which needs two 2 × 12 sockets — 48 pins, four rows. Since
2026-09-14 the bill buys two 1 × 40 female strips and cuts them into the four
rows.

**Bus A is on PA11/PA12, not PB8/PB9, and the bill agrees since 2026-09-14.**
The bill put FDCAN1 on PB8 and read the cost as the BOOT0 button. The cost is worse than that. PB8 *is* the boot
select pin, and a transceiver's `RXD` idles high on a quiet bus, so wiring `RXD`
to PB8 makes the level the MCU samples at reset depend on whether the 5 V rail
has passed the transceiver's 4 V undervoltage threshold yet — flash if it has
not, the system bootloader if it has. That is a race, not a setting, and the
cure is to take the boot source off the pin in the option bytes before the robot
will start at all. Putting bus A on PA11/PA12 costs the core board's USB
instead, which nothing here uses: the SBC link is serial and the programmer is
SWD. If USB is wanted back later it is two wires and an option byte.

**The CAD draws three transceivers as of 2026-09-14.** It drew two for most of
that day: the bill went to three buses in the morning and `cad/electronics.py`
was not part of that change, so the packing showed a pair until the viewer's
tree was read carefully enough to notice. The drawing has caught up, and the
paragraph below is what it was made to.

## Fitting three of them

The transceivers used to be a pair at 13 mm centres, 10 mm in from the carrier's
outboard edge, in the piece of board to the right of the SBC's posts. That piece
is 28.85 mm wide and 46 mm deep. Three socketed DIP-8s at 12.7 mm centres —
five perfboard holes — span 35.8 mm of that 46, which fits, but in the column
where the two sat the outer two foul the M3 corner holes by 0.3 mm. The column
moved 2.5 mm inboard, which measures 1.87 mm of clearance to the nearest of
those holes and leaves 7.4 mm of board outboard of the DIPs. Both numbers are
off the built solids, and the tightest thing near the column is now the 1.7 mm
to a corner standoff and the 2.4 mm of air under the SBC.

One layout note that is not about fitting. The connector bank
`cad/electronics.py` draws for the actuator harnesses is 40 mm long and sits at
the *left* end of the carrier, under the core board, while the transceivers are
at the right end. Every CAN pair therefore crosses the whole board. Three 4-pin
JST-XH housings are about 40 mm laid end to end, which is exactly the bank as
drawn, so the tidy answer is to move that bank to the right-hand piece beside
the transceivers rather than to make it longer.

## The printed board, 2026-09-14

**It is a two-layer PCB, not a sheet of perfboard**, it is 140 × 46 mm, and it
carries the logic BEC and the bus monitor as well as everything it used to. Every
part is still through-hole, so it is soldered by hand with the same iron.
[`electrical/carrier_pcb.py`](../electrical/carrier_pcb.py) is the layout — every
footprint, where it sits, every track and every via — and
[`electrical/carrier_pcb.svg`](../electrical/carrier_pcb.svg) is drawn from it.

```
uv run electrical/carrier_pcb.py            # check it, then print the board
uv run electrical/carrier_pcb.py --draw     # also rewrite the drawing
uv run electrical/carrier_kicad.py          # write electrical/kicad/carrier.kicad_pcb
```

**What the check proves, and it is the part worth trusting.** That every
footprint carries exactly the pins the netlist gives its part; that each net's
copper is ONE connected piece touching every pin on that net and nothing else —
a short and open test run on the drawn copper, ground pour included; that no two
nets come within 0.2 mm on either layer, and no copper comes near the edge, a
mounting hole, a standoff or a drilled hole; **that no two drilled holes come
within 0.25 mm of each other, whatever is on them**, which is the rule two pads
on the same net slip past and the one KiCad caught this board breaking; and that every part, and every plug with
its wires leaving it, clears every drawn thing in the torso, measured in the
CAD's own frame rather than asserted. A track that stops a tenth of a millimetre
short of its pad fails it.

**140 × 46 mm, two layers, 1.6 mm FR-4.** 0.25 mm signal tracks, 0.6 mm for the
5 V run and 0.5 mm for the other rails, 0.2 mm clearance, 249 holes in eight sizes
and 92 vias at Ø0.4, and the largest hole on the board is a Ø3.4 mounting hole —
every figure well inside what any hobby board house builds as standard, because
the margin is what makes hand soldering forgiving.

### The SBC stands on this board, 2026-09-14

**It stood on four posts printed with the electronics deck**, 14 mm pillars that
came up through this board in Ø8.6 clearance holes, and it stands on four M2.5 ×
10 standoffs screwed to this board instead. The Banana Pi is held exactly where
it was, half a millimetre higher.

**What that cost while it lasted, and what changing it bought.** A post and its
clearance was a barrier 9.6 mm across, and the SBC's two pairs stand 23 mm apart
across the middle of this board, so every net between the core board and the
rest of the layout had to go through the gate between them. A 5 mm standoff on a
Ø2.7 hole is 6.8 mm across, which widens each gate by 2.8 mm. **And it takes the
one unbuildable hole off the drawing**: Ø8.6 is past the largest drill the board
house in [`docs/BOM.md`](BOM.md) owns, so those four holes would have had to be
cut out of the board outline as routed slots before anyone could order it. They
are ordinary screw holes now.

**What it costs is two screws per corner rather than one**, and an M2.5 rather
than the M3 the rest of this torso is built with — the Banana Pi's holes are
2.75 mm and an M3 will not pass them. The deck is 2.5 g lighter and has no
heat-set insert anywhere on it.

### Why the BEC and the monitor came up here

**Seven wires between three boards became four, and the I²C bus stopped leaving
the board.** The BEC was on a bracket over the harness bank and fed this board
5 V up a cable; the monitor was on two printed pads off the pelvis's rear wall
and talked to it over a five-wire I²C lead. Both are on this board now. What
comes up from the power bay instead is the raw battery bus, two wires, and the
shunt's sense pair, two more.

**That is a gain in the place it matters.** An open-drain I²C bus running 150 mm
through a torso is the classic way to lose an IMU to a monitor that has locked
the bus up, and there is now only one such run instead of two.

**What it costs is the shunt's measurement, and this is the honest part.** The
shunt stands in the main bus path carrying the whole pack current, so it cannot
come up here and it has not: it stays at the distribution board, and a twisted
pair carrying about 75 mV at 25 V of common mode runs 150 mm up to the carrier.
Twist it, filter it at the inputs, and expect a noisier reading than a monitor
sitting on the shunt would give.

**That pair lands on J7 on this board now, and not in the monitor's own screw
terminals**, which is a change of mind made on 15 September 2026 when the monitor
was landed on all eight of its pins. Its `IN+` and `IN−` are on that header as
well as on the terminals, so the choice is free. What it buys is a pair arriving
in a connector with strain relief on the edge of a board whose whole stack is
meant to lift out on plugs, rather than in two screw terminals in the middle of
it facing the charge socket. What it costs is about 20 mm of this board's copper
under the measurement, drawn as a pair over the plane, where before the 75 mV
never touched the board at all.

**The monitor carries its own 0.1 Ω shunt across those two pins**, and it stays
in circuit in parallel with whatever external shunt is fitted. A milliohm shunt
then reads about half a per cent low. Lift R100 off the module, or take the half
per cent knowingly.

**Its bus-voltage input is connected now too.** `VBS` was not brought out at all
while the monitor sat on five wires, which left the thing that measures the pack
unable to measure its voltage. It is on the fused side of the bus, so what it
reads is the pack less the fuse's own drop — about 50 mV of 25 V at the 1.3 A
this lead carries, or 0.2 % low, which is worth more than an unfused track
across the middle of the board.

**And the raw bus is now on the controller board.** It arrives on J1, goes
through a resettable fuse and into the BEC and nowhere else. The pack's own fuse
is sized for 30 A and this lead draws under two, which is why there is a fuse at
the board at all.

### Which way up the BEC lies, and how it lands, 2026-09-14

**Component side up, laminate face down on the sheet.** This had never been
decided: the BEC was drawn as a featureless brick with flying leads, and a brick
has no sides. The real part is a bare 35 × 24 mm PCB with a shielded inductor, a
diode and a switching FET standing most of its 5.5 mm on one face and nothing but
laminate on the other.

**Turning it over was tried and taken off again.** Face down, the only thing
gained is a flat back for the cable ties to bear on, and what it costs is the
whole reason the thermal sheet exists: the sheet would touch the inductor and the
diode and nothing else, leaving the rest of a 3 W regulator in a closed pocket
3 mm under the SBC. Face up, the sheet takes the module's entire 35 × 24 back —
700-odd mm² of contact through 1.6 mm of laminate with copper planes in it — and
the hot parts stand in the air under the SBC rather than facing the board.
**What it costs is that the two ties cross the parts**: each strap lands on
whatever is tallest in its lane, which on the outboard lane is the inductor's
steel can. Keep them snug rather than tight.

**And the straps were strangling the module's own pins.** Their four Ø3 holes
stood ±12 mm from the module's centre, where its pin column stands at 15 mm —
which leaves 0.65 mm of laminate between a tie hole and the nearest pad's copper,
less than one 0.25 mm track and its clearance. So the only two live pins on the
part could not leave westward at all, and the router paid for that all the way
across the board. Nothing said so: no rule was broken, because there is no rule
that a pin must have somewhere to go. The straps now cross at ±10 mm, which puts
2.65 mm there — two tracks — and takes **13 mm of copper and seven vias** off the
board. Matek publish no hole pattern, so where the straps cross was always ours
to choose; 20 mm apart and 7.5 mm in from each end holds a 35 mm module as well
as 24 and 5.5 did.

**Its four pads face up, and that is what makes the pins work.** Four pins stand
out of the carrier — IN, G, G, OUT, at the module's own 3.81 mm — the module drops
over them past the sheet's cut edge, and they are soldered at the module's own
rings on top, where a joint can be seen. **Solder them from under the carrier**,
not on top: the module's back lies 1 mm off the copper there, and a fillet on the
top face would hold it off the sheet.

**Each tie's head goes under the board**, in the 3 mm the carrier's own standoffs
leave: about 2.4 mm of it. That is why the ties are the 2.5 mm size and not the
4 mm one — a wider tie does not pass a Ø3 hole, and its head does not fit under
the board either.

### Why the board is 140 mm and not 96

**Because of the monitor's height, and nothing else.** The INA226 is a bought
22 mm breakout and it stands about 11 mm over a board once it is on standoffs,
where the SBC leaves 10 mm of air over this one — 9.4 mm when this was worked
out, and the argument did not turn on the half millimetre. The only air on this deck
deeper than that is outboard of the SBC's own two edges — and outboard to the
left is where the core board already stands. So the monitor has to go to the
right of the SBC's right-hand posts, which with their clearance allowed for is
x +33.8 in the torso, and 22 mm of board past that puts the edge at x +67.45.
Those posts are standoffs now and the barrier is narrower, but the SBC's own
edge is at x +32.5 and the monitor still cannot stand under it, so the width
stands.

**The rear outboard corner is cut out of the reservation.** The charge socket's
body reached 17.1 mm in from the rear wall and passed 3.65 mm over this board, so
the last 21 mm of the rear edge carries copper, a mounting screw and nothing
taller. The board itself is a plain rectangle; it is the reserved volume that has
the notch in it, because a reservation promising height it has not got is worse
than an awkward shape. **The notch outlived its reason on 2026-10-05**: the male
inlet that replaced that socket stops 2.3 mm short of this board's rear edge in
plan. It stays, because the layout is built round it and air costs nothing.

### Why everything is where it is

**Three things fix the layout, and none of them is electrical.**

**The SBC leaves 10 mm of air** over everything between x 40 and x 105 of this
board, and a mated JST-XH plug is 9.8 mm tall with its wires still to leave — so
no connector stands under the SBC, and neither does anything else tall: the core
board on its sockets, the monitor on its standoffs, the two pull-ups and the
fuse are all outboard of the SBC's edges or in the strips beyond its front and
rear ones.

**The SBC's four standoffs stand on this board** in two pairs, at x 43.55 and
x 101.55, 23 mm apart. Each pair is a bollard 6.8 mm across with a 16.2 mm gate
in the middle. That is what puts the core board outboard of the left pair, the
monitor outboard of the right pair, and the BEC between them — and it is why
**nothing at all stands in the left-hand gate**. A transceiver socket was there,
and it cost four nets their route: eighteen nets have to cross that pair to get
from the core board to the rest of the board, and a socket standing in the gate
left two slots of 2 mm. The gate is a corridor.

**What comes up through the deck comes up at the rear**, through the deck's 34 mm
cable chase — **and not all of it comes up under its own plug.** That claim used
to be made here and was never measured; `carrier_pcb.py` measures it on every run
now, by asking the deck solid itself rather than the notch's dimensions, so a
second opening cut later counts without this being rewritten. What it finds is
that bus A's and bus B's connectors sit squarely over the chase, bus C's is
2 mm short of its western end, and the IMU's is 24 mm short of it. Those two
looms come up the chase and are dressed westward along the 3 mm under the carrier
before they reach their plugs. It is still far better than what it replaced: on
the 76 mm board every connector was at the far outboard end and the loom came up
the chase and then crossed the entire torso, which is most of half a metre of
wire that is not made now.

The front edge carries what goes up rather than down — the SBC's own cable, and
the bus feed.

### How the copper runs

**It is searched for, not typed.** The 76 mm board was hand routed and that was
reasonable for what it was. This one is 140 mm with six more parts and the SBC standing on it, and a table of two hundred hand-typed vertices is a table nobody
dares change. So the tracks are found by a maze router on a 0.2 mm grid, in
[`electrical/carrier_pcb.py`](../electrical/carrier_pcb.py), and then held to
exactly the checks the hand-routed ones were held to. **A router that cheats
still fails the check**, which is the only reason it is allowed to do the work.

**The order the nets go down in decides how much copper the board ends up with,
and the router used to take the first order that worked.** It lays the wide rails
first and then the rest shortest-first, and if a net cannot be routed it pushes
that net to the front and tries again with the queue shuffled. That is a sound
way to find *an* answer and no way at all to find a good one. It now lays all
eight of its orders down and keeps the cheapest board that routes everything,
counting a via as 5 mm of track. On the placement as it stands two of the eight
succeed — 1968 mm on 92 vias against 2003 on 93 — so today it keeps the one the
early exit would have stopped at anyway. **That is luck rather than design**:
run the same eight seeds against a slightly different set of stations and a
different three of them succeed, spanning five per cent of copper. The search
costs a couple of minutes a run instead of twenty seconds, which is a fair price
on a board that gets fabricated.

**Ground is poured on both layers and not routed**, except where the pour comes
out in pieces: a bundle of signals crossing both layers in the same place cuts
both planes there, and a pad on the far side of that is on an island. Those are
found after the pour is built and joined by a few short hops. 92 vias stitch the
two planes together.

**A stitch that joins nothing is taken out again.** The vias go down on a grid
before there is a pour to judge them by, so a route change can leave one sitting
in a pocket of pour with no ground pad anywhere in it — two pieces of floating
copper on the net that is meant to be one plane. They are found the same way the
islands are, and dropped, and the pockets go with them because a pour piece
nothing anchors is not kept. None is dropped on the board as it stands; one was
while the BEC's pins were being moved, which is what the pass was written for.

### What it measures against the torso

Every part and every mated plug, against every drawn thing in the pelvis. The
tightest, in millimetres:

| gap | between |
|---|---|
| 0.85 | the IMU plug and the antenna's bulkhead |
| 0.95 | bus B's `VIO` capacitor and the nearest SBC standoff |
| 1.50 | the shunt plug, the BEC's cable tie and the IMU header, each against what stands over it |
| 1.60 | three plugs on the rear and front rows, and the edge of the SBC |
| 1.76 | the core board and the edge of the SBC |
| 1.90 | the BEC and the SBC's microSD socket |

**The bus-A connector and the charge socket were 1.25 mm apart** until
2026-10-05, when the inlet became a male XT60E-M reaching 8.3 mm into the
cavity where the female's body reached 14.7, and moved to x 59.0; nothing on
this board is within 3 mm of it now.

**The BEC's outboard cable tie used to head this table at 1.20 mm**, against the
SBC's microSD socket hanging over it. The straps came in from ±12 to ±10 mm for
an unrelated reason — see below — and it stands 3.20 mm off now.

### Taking it to KiCad

[`electrical/carrier_kicad.py`](../electrical/carrier_kicad.py) writes
`electrical/kicad/carrier.kicad_pcb`: the outline, every footprint and pad, every
track, every via, the silkscreen, the netlist and the two ground pours. It also
runs [`electrical/carrier_sch.py`](../electrical/carrier_sch.py), which writes
`carrier.kicad_sch` and the symbol library beside it, so a project opened from
that folder has both. KiCad opens all of it directly, and the Gerbers, the drill
files and the 3D view come from there.

**Close the project and open it again after regenerating.** KiCad reads a
project's symbol library table once, when the project opens, and the schematic's
symbols live in `carrier.kicad_sym` beside it. Write a new schematic under an
editor that already has the project open and it keeps using the configuration it
loaded, which surfaces as *"the current configuration does not include the symbol
library"* pointing at a file that is sitting right there. The exporter looks for
KiCad's lock files now and says so when it finds them. For the same reason
`carrier.kicad_pro` and `sym-lib-table` are **seeded once and then left alone** —
KiCad migrates the first and rewrites the second, and a generator that
overwrote them on every run was simply taking turns with the editor. Delete
either to have it laid down again.

**It is a translation and not a second design.** Everything in it is read from
the layout, so the two cannot disagree about where a pad is. What KiCad adds is
independence: its DRC was written by other people and does not share a bug with
ours, so if it complains, one of the two is wrong and the disagreement is the
finding. **Fill the zones before reading the DRC** — the pours are declared with
this board's rules rather than copied, and KiCad fills them itself.

**And it complained, which is the whole point.** Run against the board on
15 September 2026, KiCad's DRC found sixteen pairs of drilled holes too close
together — three of them overlapping, a via drilled into the edge of a pin's hole
— on a board this repository's own checks called clean. Nothing was wrong with
the copper: a via and a pad on the same net have no clearance to violate, so the
question had never been asked. `carrier_pcb.py` asks it now, before and after
routing, and the board is routed to keep 0.25 mm of laminate between any two
holes. That cost eight stitching vias and no routes.

**And it complained a second time, about the export rather than the board.** When
bus B's decoupling pair was brought in beside its chip, one of the two had to
stand on end, and it was the first part on this board ever placed at a quarter
turn — every other part stands at 0° or 180°, where a rotation and its negative
are the same thing. The exporter was negating the angle on top of the y flip it
had already applied to the pad offsets, so that capacitor came out of the
translation reflected about its own origin, 5.08 mm from where the layout puts
it, with its ground pad on top of an I²C track. **KiCad called it a short between
two nets.** `carrier_pcb.py` could not have seen it: the geometry it checks was
right, and only what was written out was wrong. The angle goes out as it stands
now, and every part at 0° or 180° is unaffected, which is why this sat in the
file unnoticed.

That revision left three starved thermal reliefs. The 2026-09-15 review corrections below remove them:
0 errors, 0 unconnected pads, 0 footprint errors, 0 silkscreen violations. The
schematic passes ERC with 0 violations.

### The silkscreen

**Part outlines, a pin-one dot on every part, the reference designators, and
what each connector is for.** The last of those is the one that matters: three
mechanically identical four-way plugs sit in a row on the rear edge, and the only
thing that stops a knee harness going into the wheel bus is what is printed
beside it. `BUS A HIP`, `BUS B KNEE`, `BUS C WHEEL`, `PWR IN`, `SBC`, `IMU`,
`SHUNT`.

**It is placed by measurement rather than by offset.** Silk printed over a pad is
scraped off by the fab and silk printed over silk cannot be read, so every
outline is clipped off every pad on the board, and every legend is tried at a
series of stations until one is clear of the pads, the holes, the other silk and
the board's own edge. A legend that will not fit anywhere is dropped and named
rather than printed over a pin — and each one has a shorter form to fall back on,
which is what gets `BUS B` onto the middle connector of three.

**The reference designators did not print at all when this was first written.**
In the board format this file writes, a footprint's `(property ...)` is a key and
a value and nothing is drawn from it; a reference is an `fp_text`. The board
opened, passed DRC and plotted with no part names on it. It was found by plotting
the silkscreen and looking at the picture, which is the only way it could have
been found.

### The schematic

[`electrical/carrier_sch.py`](../electrical/carrier_sch.py) draws the netlist as
a single A2 sheet: one symbol per part, laid out in columns by kind, with every
pin's net on the end of a stub.

**It is drawn with labels and not with wires**, deliberately. A net here is a
name shared by up to thirteen pins spread across the board, and drawing that as
lines between symbols is the same problem as routing the board, with a drawing
nobody can follow at the end of it. Two pins carrying the same name are the same
net, which is how a dense board is drawn by hand anyway.

**Every pin is declared passive**, which is the honest declaration rather than a
lazy one: marking supply pins as power inputs makes ERC ask for power flags and
then report against a model of the board that nobody maintains. What is actually
checked — every pin on exactly one net, no dead ends, no pin on two nets, and
copper that reaches all of it — is checked in `carrier.py` and `carrier_pcb.py`
against the real geometry.

Nothing has been fabricated. The board and the schematic have both been opened by
KiCad's own command-line tools, which is where the DRC and ERC figures above come
from.

### Which row of each header carries the odd pins, settled

This was the one assumption the whole netlist hung on, and it is answered. WeAct's
board-shape drawing gives the four rows and the twelve columns without saying
which row is which; **their pin-label drawing of the same board does**. Each
column there carries two port names, one line above the other, and six of those
pairs are pins this netlist already numbers — B12/B13 are P1-5 and P1-6, A11/A12
are P1-13 and P1-14, B4/B5 are P1-19 and P1-20, B6/B7 are P1-21 and P1-22, B8 is
P1-23, and B15 is P1-8. In every one of them the **even** pin is the name on the
upper line. And NRST, which is P2-19 and the odd pin the question turned on, is on
the lower line of the top header, which agrees.

So the odd pins are on the row printed **lower** in each header — and because the
two headers face opposite edges of the board, that is P1's **outer** row and P2's
**inner** row, which is exactly what the layout had assumed. **Nothing needs
beeping with a meter before ordering.**

### Still open on the board itself

- **There is no spare transceiver socket.** 140 × 46 mm with the SBC standing on
  it and the modules on it has no room for a fourth DIP-8. The spare stays in its
  bag.
- **Three of the six decoupling capacitors are 9 to 12 mm from their pin**, where
  a decoupler wants to be within about 5. Every one of the six was placed by
  searching the board for the nearest legal station and keeping the move only if
  the board still routed, which brought bus B's pair in from 19 mm to 2.9 and 3.0
  and bus C's `VIO` cap in from 7.1 mm to 2.5. What holds the other three out is
  the BEC: it lies across the whole flank west of the socket column, from y 11 to
  y 35, and `VDD` is on the sockets' west side. Only bus B's `VDD` pin escapes it,
  because that socket is the southernmost and there are 2 mm of board south of the
  BEC's corner. Bus A's pair does have a legal station 4.6 and 2.5 mm from its
  pins in the channel between the BEC's cable tie and the socket — **and both were
  tried there**: each costs three nets their route, because that channel and the
  strip east of the column are the only two ways past this block of parts, and
  the I²C bus, the SBC's serial link and bus A all need them. Standing off and
  letting the plane carry the return is the lesser evil, not a good answer.
- **J5-2 and J6-2 now connect solidly to ground on both layers.** Their
  starved thermal reliefs are gone. Use board preheat and an appropriately
  sized iron when soldering these pins; the extra copper draws heat away.
  Other ground pads keep thermal reliefs. KiCad checks the actual filled
  board, not the custom pour's approximate spoke count.
- **Every downward plug now has a full-width deck opening (2026-09-15).** The
  motor-bus notch is 44 mm wide, with an 18 mm IMU notch and a 12 mm front
  power/sense notch. The complete pin-row width plus dressing allowance is
  probed through the plate, and any remaining material is a failure. Dress
  the wires over the plate, outside the carrier outline, then down the notch.
- **The carrier's own standoffs are drawn at 3 mm and nobody stocks that.** The
  shortest brass pillar on an Indian shelf is 5 or 6 mm, and every millimetre
  under the carrier lifts the SBC with it — the reserved volume over the SBC has
  2 mm of air under the lid, so a 6 mm pillar spends all of it. Cut spacers, or
  move the whole stack down, but do not buy 6 mm pillars and hope.
- **0.85 mm is the tightest thing on this board**, between the IMU's plug and the
  antenna bulkhead in the shell wall. It is a real clearance rather than a
  computed one, but both ends of it are bought parts nobody has measured — a
  bulkhead jack's body and a mated JST-XH plug with its wires still to leave.
  Measure both before ordering. It took that place from the BEC's outboard cable
  tie, which stood 1.2 mm off the SBC's microSD socket and stands 3.2 mm off it
  now.
- **Where the BEC's four pins are is scaled off a photograph**, and it is the
  softest number on the board. Matek publish no drawing of the part: the 3.81 mm
  pitch is dimensioned on their product photograph, and the row's 2.5 mm inset
  from the module's short edge is measured off the same picture. The tie holes
  can take a millimetre of error and this cannot — a pin row 1 mm out is a module
  that does not go on. **Measure one before the board is ordered.**
- **The BEC's outline is a catalogue figure and its hold-down is a guess.** No
  vendor hole pattern exists to screw it by, so it lies on a 1 mm silicone sheet
  under two 2.5 mm cable ties through four Ø3 holes drilled to the catalogue
  35 × 24. Measure the part when it arrives: a module 2 mm wider than the
  catalogue says will not sit between the ties. **Where the straps land on its
  parts has been reasoned from a photograph and not checked** — and they moved
  in from ±12 mm to ±10 mm to clear the pin column's copper, so what each one
  crosses has moved 2 mm inboard with it. The outboard one was over the
  inductor's can and should still be; the inboard one crosses smaller parts on
  the input side.

## What is not settled

- **Three wires have nowhere to land on this board.** The power switch board
  added on 15 September 2026 — `docs/POWER_SWITCH.md` — wants a hold output from
  the MCU, a button input back to it, and a ground, and this board is at a
  checked fabrication release with no connector for them. Adding one is a change
  to this board and to its release, and it has not been made. Until it is, that
  switch is held closed by a shorting link on its own button connector, which is
  a bench arrangement rather than the robot's. The MCU has spare pins for both
  signals; what it has not got is a plug.
- **Which IMU breakout.** The 7Semi BNO085 nano is listed at 3.6–5 V, so JP1
  defaults to 5 V, and the pin order on J6 follows the names its listing uses
  rather than a pinout anyone has read off the board. Confirm both against the
  module in hand before crimping, and check which rail its I²C pull-ups go to.
- **Which UART the SBC exposes.** J5 assumes a 3.3 V serial port on the Banana
  Pi's 40-pin header. Which one, and whether the OS leaves it free, has not been
  checked.
- **The INA226's alert.** Wired to a GPIO because it costs nothing to wire, not
  because a threshold has been chosen.
- **Nothing here has been built.** Every number in this document came off a
  vendor document or off the CAD. No part of this board exists.

## Checked fabrication release (2026-09-15)

Run `uv run electrical/fabricate.py` to regenerate the carrier and its local
symbol/footprint libraries, refill the zones, require zero DRC/ERC violations
and zero schematic parity issues, then export Gerbers and separate PTH/NPTH
drills. The command packages `electrical/kicad/carrier-fabrication.zip` and
puts individual files, reports and SHA-256 hashes in `electrical/kicad/gerber/`.
`uv run electrical/fabricate.py --verify` rejects changed sources, changed
outputs or an archive that disagrees. Old files are not a fabrication release.
The top silkscreen must contain drawing apertures; an empty layer fails.

The schematic uses local labels, so the PCB now preserves their `/` prefix.
Deliberately unused pins retain Eeschema's no-connect names. P3 is accessed on
the removable WeAct core board and is not a carrier pad; only the 48 pins
actually landed on this PCB appear on its schematic symbol. Mounting holes
have unique references and are marked board-only. These changes make parity
checking useful without suppressing its warnings.

Reload the project in an already-open KiCad editor after regeneration; its
in-memory board and libraries can otherwise predate the checked files.
