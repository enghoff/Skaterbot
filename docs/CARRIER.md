# The controller carrier

The carrier is the only board on this robot that nobody sells. It is 140 × 46 mm
standing on six M3 pillars on the electronics deck, and it holds the WeAct core
board on sockets, three CAN-FD transceivers in DIP-8 sockets, the logic BEC and
the bus monitor, a handful of passives, and the connectors that every other
piece of electronics in the torso plugs into. It was a sheet of 2.54 mm
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
| **J1** | 2-pin | 1 `+5V`, 2 `GND` — in from the Matek BEC |
| **J2** | 4-pin | bus A: 1 H, 2 L to the left hip; 3 H, 4 L to the right hip |
| **J3** | 4-pin | bus B, the two knees, same order |
| **J4** | 4-pin | bus C, the two wheels, same order |
| **J5** | 5-pin | 1 `GND`, 2 MCU→SBC, 3 SBC→MCU, 4 `BOOT0`, 5 `NRST` |
| **J6** | 6-pin | IMU: 1 supply, 2 `GND`, 3 `SCL`, 4 `SDA`, 5 `INT`, 6 `RST` |
| **J7** | 5-pin | bus monitor: 1 `+3V3`, 2 `GND`, 3 `SCL`, 4 `SDA`, 5 `ALERT` |
| **JP1** | 3 pads | IMU supply link: bridge 1–2 for 5 V, 2–3 for 3.3 V |

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

5 V arrives from the BEC on J1 and does two things: it feeds the three
transceivers' `VDD` directly, and it feeds the core board's own regulator
through P1-1/2. The 3.3 V that regulator makes comes back out on P2-1/2 and sets
the logic level on every transceiver's `VIO`. That split is the whole reason the
bill buys MCP2562FD rather than MCP2561FD — the 2561 has no separate I/O supply
and would drive 5 V logic into a 3.3 V microcontroller.

Two things about the core board's supply that are easy to be bitten by. Its
regulator is small, so the 3.3 V rail is for the MCU, the `VIO` pins and the
pull-ups and not for anything that draws real current — which is why the IMU's
link defaults to 5 V. And `SB9` on the core board ties the rail you are feeding
to the USB-C connector's `VBUS` pin, so either do not plug a host into the core
board while the robot is powered, or cut `SB9`.

Decoupling is 10 µF of bulk on the 5 V at J1, and 100 nF at both `VDD` and `VIO`
of every transceiver — nine capacitors in total with the one by the sensor
connectors. The two 4.7 kΩ I²C pull-ups go on only if neither sensor module
brings its own.

The transceivers' `STBY` pins are tied to ground rather than driven. They have
about 1.1 MΩ of pull-up inside, so a pin left floating is standby and not normal
mode, and nothing on this robot wants a transceiver asleep. A line that has to
be driven correctly before any bus works is one more thing to get wrong at
bring-up.

## Four places this disagrees with docs/BOM.md

**The bill names two different core boards.** Its purchase link is WeAct's
*long type*, which is 63.06 × 18.24 mm with two 1 × 20 headers. Its quoted
dimension, its carrier assembly note and `cad/electronics.py` all describe the
compact board, 36.53 × 28.40 mm with two 2 × 12 headers. Both numbers were
measured off the vendor STEP files, so this is not a rounding disagreement — it
is two boards. **This schematic is drawn to the compact one**, because that is
what the CAD packs and what the carrier layout has room for; a 63 mm board does
not fit the piece of carrier the SBC's posts leave. The purchase link is what
needs correcting, and it is worth doing before anything is ordered.

**The header line followed from that, and it is corrected.** It said
"2 × 2.54 mm 1 × 20 female header", which is right for the long board and wrong
for this one, which needs two 2 × 12 sockets — 48 pins, four rows. Since
2026-09-14 the bill buys two 1 × 40 female strips and cuts them into the four
rows. The purchase link above is still the long board's.

**Bus A is on PA11/PA12, not PB8/PB9.** The bill puts FDCAN1 on PB8 and reads
the cost as the BOOT0 button. The cost is worse than that. PB8 *is* the boot
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
mounting hole, a post or a drilled hole; and that every part, and every plug with
its wires leaving it, clears every drawn thing in the torso, measured in the
CAD's own frame rather than asserted. A track that stops a tenth of a millimetre
short of its pad fails it.

**140 × 46 mm, two layers, 1.6 mm FR-4.** 0.25 mm signal tracks, 0.6 mm for the
5 V run and 0.5 mm for the other rails, 0.2 mm clearance, 245 holes in six sizes
and 103 vias at Ø0.4 — every figure well inside what any hobby board house builds
as standard, because the margin is what makes hand soldering forgiving.

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
come up here and it has not: it stays at the distribution board and its IN+ and
IN− go into the monitor's own screw terminals on a twisted pair, about 75 mV at
25 V of common mode over 150 mm. Twist it, filter it at the inputs, and expect a
noisier reading than a monitor sitting on the shunt would give.

**And the raw bus is now on the controller board.** It arrives on J1, goes
through a resettable fuse and into the BEC and nowhere else. The pack's own fuse
is sized for 30 A and this lead draws under two, which is why there is a fuse at
the board at all.

### Why the board is 140 mm and not 96

**Because of the monitor's height, and nothing else.** The INA226 is a bought
22 mm breakout and it stands about 11 mm over a board once it is on standoffs,
where the SBC leaves 9.4 mm of air over this one. The only air on this deck
deeper than that is outboard of the SBC's own two edges — and outboard to the
left is where the core board already stands. So the monitor has to go to the
right of the SBC's right-hand posts, which with their clearance allowed for is
x +33.8 in the torso, and 22 mm of board past that puts the edge at x +67.45.

**The rear outboard corner is cut out of the reservation.** The charge socket's
body reaches 17.1 mm in from the rear wall and passes 3.65 mm over this board, so
the last 21 mm of the rear edge carries copper, a mounting screw and nothing
taller. The board itself is a plain rectangle; it is the reserved volume that has
the notch in it, because a reservation promising height it has not got is worse
than an awkward shape.

### Why everything is where it is

**Three things fix the layout, and none of them is electrical.**

**The SBC leaves 9.4 mm of air** over everything between x 40 and x 105 of this
board, and a mated JST-XH plug is 9.8 mm tall with its wires still to leave — so
no connector stands under the SBC, and neither does anything else tall: the core
board on its sockets, the monitor on its standoffs, the two pull-ups and the
fuse are all outboard of the SBC's edges or in the strips beyond its front and
rear ones.

**The SBC's four posts come up through this board** in two pairs, at x 43.55 and
x 101.55, 23 mm apart. Each pair is a wall 9.6 mm wide with a 14.4 mm gate in the
middle. That is what puts the core board outboard of the left pair, the monitor
outboard of the right pair, and the BEC between them — and it is why **nothing at
all stands in the left-hand gate**. A transceiver socket was there, and it cost
four nets their route: eighteen nets have to cross that pair of posts to get from
the core board to the rest of the board, and a socket standing in the gate left
two slots of 2 mm. The gate is a corridor.

**What comes up through the deck comes up at the rear**, through the deck's 34 mm
cable chase. The three bus connectors sit over it. That is the whole reason this
layout was redone rather than extended: on the 76 mm board the connectors were at
the far outboard end and the loom came up the chase and then crossed the entire
torso to reach them, which is most of half a metre of wire that is not made now.

The front edge carries what goes up rather than down — the SBC's own cable, and
the bus feed.

### How the copper runs

**It is searched for, not typed.** The 76 mm board was hand routed and that was
reasonable for what it was. This one is 140 mm with six more parts and four posts
through it, and a table of two hundred hand-typed vertices is a table nobody
dares change. So the tracks are found by a maze router on a 0.2 mm grid, in
[`electrical/carrier_pcb.py`](../electrical/carrier_pcb.py), and then held to
exactly the checks the hand-routed ones were held to. **A router that cheats
still fails the check**, which is the only reason it is allowed to do the work.

**Ground is poured on both layers and not routed**, except where the pour comes
out in pieces: a bundle of signals crossing both layers in the same place cuts
both planes there, and a pad on the far side of that is on an island. Those are
found after the pour is built and joined by a few short hops. 103 vias stitch the
two planes together.

### What it measures against the torso

Every part and every mated plug, against every drawn thing in the pelvis. The
tightest, in millimetres:

| gap | between |
|---|---|
| 0.45 | the BEC's cable tie and the SBC's microSD socket |
| 0.85 | the IMU plug and the antenna's bulkhead |
| 1.10 | the IMU and bus-B headers and the SBC's posts |
| 1.25 | the bus-A connector and the charge socket |
| 1.30 | the BEC and the SBC's microSD socket |
| 2.01 | the core board and the edge of the SBC |

### Taking it to KiCad

[`electrical/carrier_kicad.py`](../electrical/carrier_kicad.py) writes
`electrical/kicad/carrier.kicad_pcb`: the outline, every footprint and pad, every
track, every via, the netlist and the two ground pours. KiCad 7 or 8 opens it,
and the Gerbers, the drill files and the 3D view come from there.

**It is a translation and not a second design.** Everything in it is read from
the layout, so the two cannot disagree about where a pad is. What KiCad adds is
independence: its DRC was written by other people and does not share a bug with
ours, so if it complains, one of the two is wrong and the disagreement is the
finding. **Fill the zones before reading the DRC** — the pours are declared with
this board's rules rather than copied, and KiCad fills them itself.

Nothing has been fabricated and nobody has opened this file in KiCad yet.

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

- **There is no spare transceiver socket.** 140 × 46 mm with the posts through it
  and the modules on it has no room for a fourth DIP-8. The spare stays in its
  bag.
- **Bus B's two decoupling capacitors are 16 mm from their chip**, in the channel
  beside the right-hand posts, because the two 1.78 mm slots between the three
  sockets are the only way across that column for anything heading for the
  monitor and a capacitor standing in one costs three nets their route. The
  ground plane under the pair is what makes that tolerable rather than the lead
  length. The other two pairs are 5 to 9 mm away.
- **No silkscreen has been drawn** beyond reference designators in the KiCad
  file, and it is the cheapest thing on the board to get right: every connector
  wants its pin 1 and its function on it, because this is a board whose three
  four-wire harnesses are all the same shape.
- **The BEC's outline is a catalogue figure and its hold-down is a guess.** It is
  a moulded brick with flying leads and no published hole pattern, so it lies on
  a 1 mm thermal pad under two cable ties through four Ø3 holes drilled to that
  catalogue. Measure the part when it arrives: a brick 2 mm wider than the
  catalogue says will not sit between the ties.

## What is not settled

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
