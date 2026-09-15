# Where every part on this robot is documented

**Written for whoever has to build, debug or re-source this robot** — not for
whoever wrote it. It answers one question per row: if you need to know what this
part actually does, where do you look, and how much is that source worth?

Eight documents are **stored here**, because a link is not a source: vendors move
pages, and half of the ones this bill was priced from already refuse an automated
read. Everything else is a link, and every link says plainly what it is worth.

`docs/BOM.md` says what to buy and for how much. This file says what to read.

## What is on the shelf here

| File | What it is | Where it came from | Bytes | SHA-256 |
|---|---|---|---|---|
| `STM32G474xE_DS12288.pdf` | ST's datasheet for the MCU that runs the robot — pinout, alternate functions, absolute maxima | WeAct's own repository, `Doc/`, which is where the core board's documents live | 3,062,163 | `b018e20d…c1add` |
| `WeAct_STM32G474CoreBoard_SCH.pdf` | The core board's schematic: what the module does to the MCU before the pins reach the carrier | `github.com/WeActStudio/WeActStudio.STM32G474CoreBoard`, `Hardware/QFN48/` | 216,548 | `f67f2dec…6bded` |
| `WeAct_STM32G474CoreBoard_outline.pdf` | The board-shape drawing: the 36.53 × 28.40 outline and the header geometry `cad/electronics.py` measures | the same repository | 1,681,770 | `c0161419…f97902` |
| `WeAct_STM32G474CoreBoard_pinout.png` | **The pin-label drawing the netlist's row question was settled from.** Each column carries two port names and the lower one is the odd pin — see "Which row of each header carries the odd pins" in `docs/CARRIER.md` | the same repository, `Images/` | 265,448 | `7fefec6d…0c57b3` |
| `MCP2561-2FD_DS20005284A.pdf` | The CAN-FD transceiver's datasheet: the split supply that decides `VIO`, and the standby pin that has to be pulled down | Microchip | 1,320,551 | `79321323…69fc14` |
| `INA226_SBOS547.pdf` | The bus monitor's own chip: the 36 V bus input, the shunt input's common-mode range, the alert pin and the I²C addresses | Texas Instruments | 1,516,957 | `c9b67f88…03ca2d` |
| `BNO080_085-Datasheet.pdf` | The IMU's chip: supply range, the reset and interrupt lines on J6, and what its I²C address depends on | CEVA / Hillcrest Labs | 1,508,684 | `34ac0ca1…c502ca` |
| `JST_XH_eXH.pdf` | The XH connector series: **2.50 mm pitch, not 2.54**, which is what this board is drilled to and what every clone has to be measured against | JST | 1,253,694 | `b3013c9b…70ab5e` |
| `DM-J3507-2EC_manual_V1.0_EN.pdf` | The actuator's manual: CAN protocol, termination switch, ratings. Its V1.1 revision **reverses the termination default** — see `docs/BOM.md` | DAMIAO, translated; the Chinese original is beside it | 782,158 | (see `README.md`) |
| `dm_3507_3d-241021.STEP` | The actuator's 3D model, and the three things wrong with it | DAMIAO's Gitee | 4,440,459 | (see `README.md`) |

Retrieved 2026-09-15, except the two DAMIAO files and the transceiver, which were
already here.

## What is a link and not a file

Each of these is either a page rather than a document, or a download that refuses
an automated fetch. The column that matters is the last one.

| Part | Where it is documented | How much it is worth |
|---|---|---|
| **Matek BEC12S-PRO** — the 5 V rail | [mateksys.com](https://www.mateksys.com/?portfolio=bec12s-pro) | **A product page, not a datasheet.** It gives 9–55 V in, 5 A out and 35 × 24 × 5.5 mm and nothing else. There is no drawing of the four-pad row the carrier lands it on: that pitch is dimensioned on the vendor's photograph and its inset is scaled off it. **Measure one before ordering the board.** |
| **INA226 breakout** — the bus monitor | [the vendor's product page](https://techtonics.in/product/ina226-i2c-voltage-current-and-power-monitor-module/) | **The module, as opposed to the chip above.** Its photograph is where the eight-way header's order comes from — VCC, GND, SDA, SCL, ALE, VBS, IN−, IN+ — and where the four large holes on the opposite edge were read. It carries its own 0.1 Ω shunt across IN+/IN−, which stays in parallel with the external one. Nobody has measured the board. |
| **Banana Pi BPI-M4 Zero** — the SBC | [the Banana Pi wiki](https://wiki.banana-pi.org/Banana_Pi_BPI-M4_Zero) | Board dimensions and the 40-pin header. **Which UART its header exposes, and whether the OS leaves it free, is not settled** — see "What is not settled" in `docs/CARRIER.md`. |
| **Littelfuse RXEF185** — the carrier's fuse | [element14's listing](https://in.element14.com/littelfuse/rxef185-2/pptc-resettable-fuse-1-85a-72v/dp/3296311) · [Littelfuse's RXEF series page](https://www.littelfuse.com/products/resettable-ptcs/radial-leaded/rxef) | Littelfuse's own asset server refuses an automated read, so the hold and trip currents here come from the distributor's listing. The number that matters is the **72 V rating**: a 30 V part on a 25.2 V pack is not enough. |
| **AMASS XT60E-M / XT60E-F / XT60 / XT30** | AMASS publish per-part drawings through their distributors rather than one catalogue | The panel parts' cut-outs in `cad/parameters.py` come from the maker's drawing, not a marketplace listing — **which is how the disconnect was caught**: the XT90E-M this design first cut for is 42.0 mm across and 19.7 mm deep inside the wall, and does not fit this torso at any station. |
| **SwiftWing PDB-02-XT60** — the distribution board | the vendor's listing | A bought board with no published drawing; its 45 mm square hole pattern is measured in `cad/electronics.py` and marked as such. |
| **Daly 6S BMS** | the vendor's listing | Catalogue size 58 × 33 × 8.2 and nothing more. It stands on edge in printed guides cut to that envelope. |
| **608 and 6800-2RS bearings** | ISO 15 / ABEC | Standard dimensions, so there is nothing to fetch: 8 × 22 × 7 and 10 × 19 × 5. The wheel's Ø22 seats at 24 mm centres follow from the 608. |

## Three things this collection is not

**It is not a parts library.** Nothing here is imported by `cad/` or `electrical/`
except the actuator's STEP. The rest is read by people.

**It is not evidence that a part was chosen correctly.** A datasheet says what a
part does; whether it suits this robot is argued in `docs/BOM.md` and in the
comments beside the dimensions in `cad/parameters.py`.

**It is not complete where it matters most.** The two bought modules the carrier
depends on — the BEC and the bus monitor — are the two with no drawing at all,
and both are landed on pins whose positions were scaled off photographs. That is
the single largest unverified assumption on this robot's electronics, and it is
cheap to remove: measure both parts before the board is ordered.
