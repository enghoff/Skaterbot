# BOM and procurement audit — 8 October 2026

This audit covers one complete six-motor wheeled robot, with one populated
carrier and one populated power board. The additional bare PCBs are replacement
boards, not a reason to order three sets of components.

**Purchase status is unresolved.** The owner disputed the reported order and
delivery statuses on 8 October. Existing BOM cart snapshots are historical
records, not evidence that an item still needs buying. No live browser was
available during this audit; the carts were read and corrected afterwards, the
same day (below). Do not place orders from this document until the disputed
statuses and quantities have been reconciled. An email search found only the
ThinkRobotics insert confirmation; absence of other emails establishes nothing
about other purchases.

## Carts as read in the browser, 8 October 2026

Nothing was ordered while the carts were corrected. Every cart below was read
live; quantities are what the cart then held.

| Store | Changed | Cart now |
|---|---|---|
| fastdep | M3 × 20 removed; M3 × 10 three packs to two; **both M3 × 6 lines removed** (two packs 12.9, two stainless), held until the first motor's output thread is measured | ×8 five packs, ×10 two, ×12 one; M2.5 × 6 and × 8, M2 × 10, M3/M2/M5 nuts, M2.5 and M5 washers, M5 × 30, one pack each. **₹555** with shipping, from ₹728. **Ordered by the owner the same day**; see [ORDERS.md](ORDERS.md#fastdep--2026-10-08) |
| ThinkRobotics | The cart was empty: no standoffs and no crimp kit to remove. **One four-pack of black M2.5 × 10 F-F standoffs added**, in stock | ₹109.99 before shipping |
| Amazon.in | The six lines moved from "saved for later" into the cart, each in stock; the unrelated USB-C cable left saved; no inserts present | Loctite 638 and 243, ESD foam, Kapton, 3M acrylic foam tape, tie mounts, one each: ₹2,458.10 |
| Robu (then unplaced) | None | Two JST-SH 8-pin leads, six 1N4148: ₹108.22. Correct only if the one lead and three diodes from order #3736678 are in hand. **Ordered by the owner the same day**; see [ORDERS.md](ORDERS.md#robu--2026-10-08) |
| Indian Hobby Center | None | **Ordered, owner confirmed 2026-10-08**; [purchase record](ORDERS.md#indian-hobby-center--2026-10-08). Reviewed basket: five DIP-8 sockets, one jumper set, XH leads 2-pin × 3, 3-pin × 2, 4-pin × 4, 4-pin double-ended × 2, 6-pin × 2, 8-pin × 1: ₹227. Delivery not yet reported. |
| element14 | None. Minimums read on each product page: ten for every resistor, C315, R82 and MMK5; five for BZX79-C15; one for 3568, PR01 and MCP2562FD | **Ordered by the owner 2026-10-08 and cancelled by element14, reported 2026-10-13**; [order record](ORDERS.md#element14-india--2026-10-08). Its parts were ordered from Robu and LionCircuits on 2026-10-13. |
| Evelta | None | **Ordered by the owner, confirmed 2026-10-08**; [order record](ORDERS.md#evelta--2026-10-08). Reviewed cart: two Daier buttons and two XT60E-M male inlets, ₹472 before GST. Delivery not yet reported. |
| Robocraze | None | One BNO085 Nano: ₹2,095. **Ordered by the owner the same day**; see [ORDERS.md](ORDERS.md#robocraze--2026-10-08) |
| Probots | None | No cart in this browser session |

**Latest remaining carts without a recorded placed order:** ThinkRobotics standoffs and Amazon.in supplies. Indian Hobby Center and Evelta are ordered; element14 was ordered and then cancelled, and its parts are on the Robu and LionCircuits orders of 2026-10-13.

## Quantity rule

Count installed demand first, then deduct confirmed usable stock and confirmed
incoming quantities. Keep one spare by default, at most two per exact part or
value. Do not automatically add spares to consumable rolls, sheets, bottles or
sets. If units are only sold in packs or subject to a minimum order, buy the
smallest permissible quantity that covers the requirement. Do not add another
whole pack just to get a discretionary spare. Record pack size separately from
the number of packs. A cheap part or a free-shipping threshold does not justify
extra stock. Historical purchases cannot be undone by editing a cart.

Pack sizes and minimum quantities below come from the saved sourcing records;
they require confirmation in the seller's current cart before an actual order.

## Changes to make to any remaining carts

**element14 cancelled its 2026-10-08 order, reported by the owner 2026-10-13.** Its lines are allocated below to the Robu and LionCircuits orders placed that day instead: incoming stock, not purchase requests. Do not reorder them.

| Store | Item | Design requirement and action |
|---|---|---|
| fastdep | M3 × 20 | Remove. Zero current uses: the power board now takes M3 × 8 directly on nut/washer spacers. |
| fastdep | M3 × 10 | 20 installed: 16 motor stator screws + 4 cover screws. Two ten-packs cover all 20; reduce the recorded three packs to two. |
| fastdep | M3 × 8 | 46 installed: 36 rotor screws + 6 carrier mounting screws + 4 power-board mounting screws. Five ten-packs are the minimum, leaving four because of pack size. |
| fastdep | M3 × 6 | Conditional substitute for the 36 rotor screws only. Hold the alternative full set until the first motor's output thread is measured; it is not another 36 screws installed beside the ×8s. Record the compatibility decision before buying. |
| fastdep | M3 × 12 | 8 installed on the wheel stator plates. One ten-pack gives two spare. |
| fastdep | Other fasteners | Keep one minimum pack of each item in the fastener table below, less confirmed stock. Do not reorder the M3 washers or journal screws merely because their status is uncertain. |
| ThinkRobotics | M2.5 × 10 standoffs | Four installed. One four-pack covers them; reduce the recorded two packs to one. A second pack would create four discretionary spares. |
| ThinkRobotics | JST-XH crimp kit | Remove. Ready-made plug leads replace it; no remaining assembly step requires this kit. |
| ThinkRobotics / Amazon / Robu | M5 inserts | No further inserts if the confirmed ten M5 × 6 inserts cover the two wheel adapters. Remove the superseded Amazon 10 mm and Robu 8 mm insert selections. |
| Robu | JST-SH 8-pin motor pigtails | Two wheel-motor leads + one spare is the allowed total. The saved record says one usable lead exists, so two additional leads would meet that target **only if that stock record is correct**. Motor-supplied leads cover hip/knee motors; verify the supplied cable set on receipt. |
| Robu | 1N4148 | Seven fitted, target eight or nine total. Six additional units are justified only if exactly three are already secured; target then is nine, with two spare. |
| Indian Hobby Center | DIP-8 sockets | Four fitted: carrier U1–U3 + power U1. Five total gives one spare. They are not five installed sockets. **Allocated to the Indian Hobby Center order confirmed 2026-10-08; do not reorder.** |
| Indian Hobby Center | XH plug leads and jumper set | Retain only quantities allocated in the harness table below, deducting confirmed stock/incoming leads. The recorded quantities give one spare per lead type, not unallocated duplicates. **Allocated to the Indian Hobby Center order confirmed 2026-10-08; do not reorder.** |
| LionCircuits | Four MCP2562FD-E/P | Three fitted on carrier U1–U3, one spare. **Ordered 2026-10-13.** |
| LionCircuits | Ten C315 100 nF | Eight fitted across both boards, two spare; ten cost less than nine. **Ordered 2026-10-13.** |
| LionCircuits | Two Keystone 3568 | One fitted, one spare. **Ordered 2026-10-13.** |
| LionCircuits | Three R82 220 nF | One fitted at power C1; three is the shop's minimum. **Ordered 2026-10-13.** |
| Robu | Two 1N5245B zeners | One fitted at power D1, one spare; replaces the BZX79-C15. **Ordered 2026-10-13.** |
| Robu | Two 2.2 µF 35 V tantalums | One fitted at power C7, + to VSRC, one spare; replaces the MMK5 film. **Ordered 2026-10-13.** |
| Robu | Ten resistor values, 0207 bodies | 23 fitted plus R26; quantities are Robu's ₹10 line minimum, not spares by choice. R3 and R7 stand over their second hole. **Ordered 2026-10-13.** |
| Evelta | Buttons / XT60E-M inlet | One fitted of each, one spare of each is allowed. XT60E-F female inlets have no current design use. **Evelta order placed, owner confirmed 2026-10-08: allocate the reviewed selections to that order; do not reorder.** |
| Robocraze | BNO085 Nano | One installed on the shell's adhesive seat. One extra is permitted but the recorded one-unit selection already covers the design. Use the Nano, not the larger Adafruit board. |
| Amazon | Adhesives / foam / tape / tie mounts | One bottle each of Loctite 638 and 243, one foam pack, one Kapton roll, one acrylic foam tape roll and one minimum tie-mount pack. The six items all have uses below. Leave unrelated household items untouched. |
| Probots / MISUMI / other old selections | Obsolete parts | Remove any remaining female panel inlets, XT30 motor branch pairs, M3 × 14, Ø30 fender washers, loop-key parts, external shunts, SH breakout boards, bought distribution boards, brass board spacers or M2.5 heat-set inserts. They are not part of this robot. Already purchased surplus stays in the purchase ledger. |

## Fasteners traced to the design

| Exact item | Installed | Named use / evidence | Smallest recorded pack quantity if none secured |
|---|---:|---|---:|
| M3 × 8 SHCS, 12.9 | 46 | Six rotor holes per actuator × six actuators; six `carrier_screw_xy()` deck stations; four `power_switch_screw_xy()` shell stations | 50 (five × ten) |
| M3 × 10 SHCS, 12.9 | 20 | Four rear screws per hip/knee actuator × four; four cover-boss pilots | 20 (two × ten) |
| M3 × 12 SHCS, 12.9 | 8 | Four rear screws per wheel motor × two, through the shin stator plates | 10 |
| M3 × 6 SHCS | 0 by default; 36 instead of rotor ×8 if required | Conditional fallback for short output threads; never an additional installed set | Hold pending measurement |
| M3 × 20 | 0 | Former stacked distribution/power-board assembly is gone | 0 |
| M3 nuts | 10 | Six carrier + four power-board spacers | 25 |
| M3 plain washers, 0.5 mm | 34 | 24 stator screws + ten nut spacers | Deduct the recorded 100-pack first |
| M2.5 × 8 SHCS | 4 | Deck slots into four printed wall ledges | 10 |
| M2.5 × 6 SHCS | 8 | Four SBC standoffs, one screw into each end | 10 |
| M2.5 × 10 female-female hex standoffs, 5 mm A/F | 4 | `sbc_standoff_xy()`, carrier to Banana Pi | 4 (one pack) |
| M2 × 10 SHCS | 4 | Two inlet ears + two INA226 mounting holes | 10 |
| M2 nuts | 8 | Two inlet nuts + six on INA226 (two under each hole, one above) | 25 |
| M2.5 plain washers | 2 | Under the two inlet screw heads; no washers behind its ears | 25 |
| M5 × 12 ISO 7380 button-head screws | 4 | Hip/knee journal screws in `cad/hardware.py`; already recorded separately from obsolete clamp screws | Deduct secured journal screws first |
| M5 nuts, as bought (unfiled since 2026-10-14) | 4 | Captive journal nut pockets, hip/knee | 25 |
| M5 × 30 SHCS, 12.9 | 2 | One wheel cap/adapter clamp per side | 10 |
| M5 plain washer, Ø11 × 1.5 | 2 | Under wheel clamp heads, inside printed caps | 25 |
| M5 heat-set inserts, Ø7 knurl | 2 | Back-fed wheel adapter insert pockets | Deduct the confirmed ten-pack first |

The installed M3 total remains **78 = 46 + 20 + 8 + 4**. Conditional ×6s replace
36 of the ×8s, without changing that total. Printed pilots use ordinary socket
screws self-tapped into the print; coarse sheet-metal screws would not pass the
nut spacers. Button and antenna use their supplied bushing nuts, not additional
mounting screws. The four 6800 bearings support hip/knee joints; wheel joints
have no additional support bearing. Journal sleeves, wheel caps and the torso
mounts are printed parts, not purchased machined spacers.

## Harness allocation

References are board-specific. These are installed demands, before inventory
deduction; the recorded balance merge is separate from the CAN harness.

| Lead / connector | Installed demand | Known endpoints | Allowed target including one spare |
|---|---:|---|---:|
| XH 2-pin, bare other end | 2 | Carrier J1 bus feed; power J3 to button terminals | 3 |
| XH 3-pin, bare other end | 1 | Power J10, spliced to carrier J1 with the two positive pins joined | 2 |
| XH 4-pin, bare other end | 3 | Carrier J2/J3/J4, CAN to hip/knee/wheel motor pairs | 4 |
| XH 4-pin, double-ended | 1 | Power J2 to carrier J7; pin 4 branches to SBC HOLD | 2 |
| XH 6-pin, bare other end | 1 | Carrier J6 to BNO085 pads | 2 |
| XH 8-pin, bare other end | 1 | Carrier J5 to SBC power/UART/programming pins | 2 total; one is recorded as secured |
| PH 4-pin, 24 AWG | 6 | Power J4–J9 to six motor power harnesses | 7; seven already recorded as ordered |
| SH 8-pin, 300 mm | 2 | Wheel motors; extend along limbs and into torso | 3 total; use confirmed stock first |
| Pack balance XH 4-pin tails | 2 | The two 3S pack balance outputs into the six-cell merge | Use secured tails; no additional duplicate pair |
| Six-cell balance tail | 1 | Merge to Daly balance input | Use the BMS-supplied tail if present; check its actual connector |
| Female-female jumper wires | One minimum set | SBC's 40-pin header, UART/SWD/HOLD connections | One set; no second spare set |
| XT60 2M1F series harness | 1 | Two battery packs; output leads land at power P1/P3 | No spare, per recorded owner preference |
| Female XT60 charge pigtail + banana pair | 1 of each | Charger outputs to male shell inlet | Deduct the recorded Quartz order first |

The extra XH 8-pin lead is a spare, not a second SBC lead. Cable gauges on
unpublished hobby-shop leads and actual JST-XH fit remain unverified. The
300 mm motor leads require extensions; a known role does not make them long
enough on their own. Adapter boards/debug leads have a bench commissioning use,
not a seventh motor branch. No external shunt sense harness is required.

## Electrical components traced to circuit references

The complete reference-by-reference register is in
[PROCUREMENT_COMPONENTS.csv](PROCUREMENT_COMPONENTS.csv). It is generated from
the current `electrical/carrier.py` and `electrical/power.py` `PARTS` lists and
includes each part's stated function and matching native KiCad footprint.
Both board netlist checks pass. All 26 carrier and 62 power references are
present in their native PCB files; the additional PCB references are exactly
the ten carrier and four power mounting holes. Wire pads and links are design
features, not extra catalogue components.

| Component | Installed demand | Circuit reference(s) / role |
|---|---:|---|
| MCP2562FD-E/P | 3 | Carrier U1/U2/U3, hip/knee/wheel CAN buses |
| DIP-8 sockets | 4 | Carrier U1/U2/U3; power U1 |
| 100 nF KEMET C315 | 8 | Carrier C2–C8; power C2, supply decoupling |
| 10 µF 50 V electrolytics | 2 | Carrier C1/C9, 5 V and bus input bulk |
| 4.7 kΩ resistors | Up to 2 | Carrier R1/R2, conditional I²C pull-ups |
| RXEF185 PTC | 1 | Carrier F1, logic branch protection |
| IRF4905PbF | 4 | Power Q1/Q2/Q6/Q7, parallel high-side switch |
| Keystone 3568 + 20 A mini blade fuse | 1 each | Power F1, main fuse assembly |
| 470 µF 35 V, 10 × 16 mm | 2 | Power C5/C6, bus capacitance |
| LM393P | 1 | Power U1, undervoltage and hold comparators |
| TL431 reference | 1 | Power U2, cutoff reference; purchased ST TL431ACZ tolerance needs checking against design assumption |
| BC546B | 3 | Power Q3 hold, Q4 turn-off, Q5 C1 reset |
| 1N4148 DO-35 | 7 | Power D2–D8, hold/button/turn-off/Miller paths |
| BZX79-C15 DO-35 | 1 | Power D1, gate clamp |
| R82 220 nF 63 V film | 1 | Power C1, soft-start |
| MMK5 2.2 µF 63 V film | 1 | Power C7, gate reset delay |
| 22 µF 16 V tantalum | 1 | Power C3, cutoff filter |
| 10 µF 16 V tantalum | 1 | Power C4, hold-through reset |
| PR01 1 kΩ 1 W | 1 | Power R26, reset current limit; separate from R18's quarter-watt 1 kΩ |
| XH headers | 10 total | Carrier J1–J7 (seven); power J2/J3/J10 (three) |
| PH 4-pin headers | 6 | Power J4–J9, one per motor |
| Female header strips | Four 12-pin socket rows | Carrier A1, two 2 × 12 WeAct sockets; two 40-pin strips are cut stock, not two spare core boards |
| Male header strip | Eight pins + four separate pins | Carrier A3 INA226 header + A2 BEC pad pins |

| 0204 resistor value | Fitted | Power board references | Saved element14 minimum |
|---|---:|---|---:|
| 10 Ω | 2 | R3, R4 | 10 |
| 1 kΩ, 0.25 W | 1 | R18 | 10 |
| 10 kΩ | 1 | R25 | 10 |
| 15 kΩ, 1% | 2 | R10, R12 | 10 |
| 22 kΩ | 2 | R13, R20 | 10 |
| 47 kΩ | 3 | R6, R8, R15 | 10 |
| 100 kΩ, 1% | 7 | R7, R11, R16, R17, R19, R22, R23 | 10 |
| 470 kΩ | 1 | R5 | 10 |
| 1 MΩ | 2 | R2, R9 | 10 |
| 10 MΩ | 2 | R14, R21 | 10 |

Total: 23 quarter-watt resistors plus the separate 1 W R26. The 14.7 kΩ,
680 kΩ, BAT46, old WIMA C7 and obsolete Vishay power MOSFET selections have no
remaining circuit references. Do not order them. The two 120 Ω bench spares
are optional external CAN termination substitutes, not carrier footprints;
the motor termination switches supply normal termination.

## Remaining modules, parts and consumables

| Item | Known use |
|---|---|
| Six DAMIAO actuators | Left/right hip, knee and wheel axes in `cad/main.py` |
| Two wheels; four support bearings | Two direct-drive wheel adapters; four hip/knee bearing seats |
| Two 3S battery packs + Daly BMS | Lower battery block in `cad/electronics.py`; series 6S supply, charge-only BMS |
| WeAct + Banana Pi + Matek BEC + INA226 | Carrier A1, SBC standoff pattern / J5, A2, A3; compute, logic power and bus voltage |
| BNO085 Nano | IMU floor seat and carrier J6 |
| Male XT60E-M + button + antenna bulkhead/antenna | Rear wall inlet ears and 15.7 × 8.4 nose cut, Ø12.4 button hole, and the Ø6.5 D antenna hole |
| 14 AWG wire | Battery/series input, charge inlet P5, charge lead |
| 16 AWG wire | Motor power extensions and BMS B− connection at P4 |
| 26 AWG CAN wire | Three motor-pair CAN buses and harness extensions |
| 22 AWG / light signal wire | Logic power and sensor/UART/HOLD connections |
| Loctite 638 | Retains four bearings in printed cheeks; polymer compatibility remains to be tested |
| Loctite 243 | Journal and wheel clamp metal threads |
| ESD foam sheet(s) | Four battery hold-down/end pads; one minimum pack only |
| Kapton tape | Two pack pull tabs |
| Acrylic foam tape | IMU seat and balance-lead restraint; not under battery foam |
| Adhesive tie mounts | Torso looms and pack leads; printed arches hold limb looms |
| 2.5 mm cable ties | Eight limb arches, BEC tie holes, bus capacitors and torso tie mounts; use existing stock |
| Thermal sheet | Electrically insulating support under BEC; recorded 0.5 mm sheet differs from 1 mm reservation |
| IMAX charger / charge lead | Battery charging/storage and capacity work; external, no robot mount |
| 22 Ω 50 W discharge resistor + cell checker | External pack capacity/storage checks; no onboard function |
| DAMIAO debugger, adapter and GH lead | External motor configuration/commissioning chain; verify exact tool/cable pairing on receipt |
| Printed structure, sleeves, adapters and caps | Current printable pieces in `tools/mass_budget.toml`; order one robot set, not obsolete machined hardware |
| PETG mock-ups | Fit checks only; quantity conditional, no unallocated full set |

## Unresolved evidence and missing allocations

- Order/delivery reconciliation is required before calculating additional units.
  Owner reports take precedence; do not replace them with old prose or missing emails.
- Battery foam is explicitly specified to attach with thin double-sided tissue
  tape, while the old cart narrative says that tape is off the bill. It has a
  known current use; check stock before adding one roll.
- Splices require appropriately sized heat-shrink, and capacitor restraint
  requires flexible adhesive. These have stated uses but no confirmed stock or
  separately sourced BOM rows. Do not substitute oversized BHT-3.5 connectors
  for signal-wire insulation; the recorded Quartz order is purchase history.
- The recorded thermal pad's electrical insulation, tantalum lead pitch,
  TL431ACZ tolerance/pinout, wheel hub dimensions, motor cable set and output
  thread depth still need confirming. This audit establishes allocation, not
  physical fit or electrical qualification of delivered parts.
- Bare-PCB replacement counts of two per board comply with the user's limit;
  they do not authorize extra populated assemblies.

## Validation

`tools/check.py` passed (all CAD modules, parts/scenes, lint and format).
`carrier.check()` and `power.check()` returned no errors. Gate E passed, including
rotor/stator holes, deck pilots/slots, board mounting holes, inlet cutout and
wheel clamp features. The native PCB files contain every current circuit
reference with no unexplained extra component references. Geometry, fabrication
files and order statuses were not changed by this audit. Live cart quantities,
current minimum orders and actual deliveries remain unverified.
