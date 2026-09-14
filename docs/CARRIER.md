# The controller carrier

The carrier is the only board on this robot that nobody sells. It is 76 × 46 mm
of 2.54 mm perfboard standing on four M3 pillars on the electronics deck, and it
holds the WeAct core board on sockets, three CAN-FD transceivers in DIP-8
sockets, a handful of passives, and the connectors that every other piece of
electronics in the torso plugs into. [`cad/electronics.py`](../cad/electronics.py)
draws its envelope so the torso can be packed around it. This document and
[`electrical/carrier.py`](../electrical/carrier.py) say what is soldered to what.

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

All JST-XH, 2.54 mm, which is what the bill already buys for the logic harness.

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

**The header line follows from that.** "2 × 2.54 mm 1 × 20 female header" is
right for the long board and wrong for this one, which needs two 2 × 12 sockets
— 48 pins, four rows — plus a 1 × 4 for SWD.

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

**The CAD still draws two transceivers.** The bill went to three buses on
2026-09-14 and `cad/electronics.py` was not part of that change, so the packing
still shows a pair. Three do fit — see below — but the drawing has to catch up
before gate F means anything about this corner of the torso.

## Fitting three of them

The transceivers are drawn as a pair at 13 mm centres, 10 mm in from the
carrier's outboard edge, in the piece of board to the right of the SBC's posts.
That piece is 28.85 mm wide and 46 mm deep. Three socketed DIP-8s at 12.7 mm
centres — five perfboard holes — span 35.8 mm of that 46, which fits, but in the
column where two sit today the outer two foul the M3 corner holes by 0.3 mm.
Moving the column 2.5 mm inboard gives 1.9 mm of clearance all round and still
leaves 7.4 mm to the board edge.

One layout note that is not about fitting. The connector bank
`cad/electronics.py` draws for the actuator harnesses is 40 mm long and sits at
the *left* end of the carrier, under the core board, while the transceivers are
at the right end. Every CAN pair therefore crosses the whole board. Three 4-pin
JST-XH housings are about 40 mm laid end to end, which is exactly the bank as
drawn, so the tidy answer is to move that bank to the right-hand piece beside
the transceivers rather than to make it longer.

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
