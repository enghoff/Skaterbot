# Provisional Bill of Materials — India Hobbyist Build

**Status:** revised 2026-09-11 against the **six-motor wheeled CAD**, which is `cad/` on this branch. Until this revision the document described the 8-DOF walking biped; that machine and its BOM now live on the `walking` branch, and nothing below refers to it except where a line says so.  
**Sourcing check:** 2026-08-30 for everything carried over; the wheel and clamp lines added 2026-09-11, and the journal line respecified the same day, have not been price-checked. **The battery lines were re-checked 2026-09-13 against live stock**, which is when the BMS was chosen and when the charger's price moved: two things on this table are not on a shelf today, and both say so in their own rows. **The transceiver line was respecified 2026-09-13** to a through-hole part, and the carrier's passives were added beside it; neither is price-checked. **EVERY PURCHASE LINK ON THIS BILL WAS OPENED ON 2026-09-13** and the table now says what each vendor's page said that day. Five links were dead or pointed abroad and are replaced; ten named a part the vendor had run out of, and those moved to an Indian shop that had it. Six items had **no Indian stock at all** that day and each says so on its own line: the six DAMIAO actuators, the adapter board and the debug lead, none of which any Indian seller carries; the WeAct MCU board; the Matek BEC; the Daly BMS; M3 × 14 screws; and the wheel clamp's Ø30 penny washer. Prices marked *checked* are that day's listed price including GST where the vendor shows it. **The electrical table was then swept for completeness on the same day**, against `cad/electronics.py`'s drawn hardware, `tools/mass_budget.toml` and the motor's own manual. Six required components had no row at all — the carrier's board and passives, the DAMIAO adapter board, the SBC's boot media, the logic and sensor harness, the INA226's external shunt and the motor-power contactor — and all six are rows now. Three of them are marked WAIT rather than specified, because what they are depends on a measurement nobody has taken. **The three DAMIAO cable and adapter lines were then re-linked on 2026-09-13**, because all three pointed at Foxtech's DAMIAO category page, which sells motors and no cables: they now name the cable set's own product page and the dropdown option to pick from it. The adapter board carries a price for the first time — **US$2.30, in stock** — and is a line item of its own rather than a motor bundle, which is a change of instruction, not just a link.  **The charge inlet line was corrected on 2026-09-13 because it named a part that will not fit the robot**, which is a different class of error from a stale price: it linked the GX16 with a **3-hole circular flange**, while the CAD cuts a bare Ø16 hole for a threaded bushing and has no flange screw holes and nowhere to put them. The same shop sells the plain panel mount for ₹50 less and has it in stock, and that is now what this bill says. **The contact gender on that line reversed at the same time**, and for a reason worth reading before ordering. **The two actuator pigtail lines were then deleted the same day.** Both cables exist, both arrive with every motor, and neither is sold separately by anyone, so neither was ever something to buy; what mattered on those rows — the quantities, the request for spares, and why a generic SH1.0 lead will not do for the power one — moved onto the actuator line, which is the thing actually being bought. **A bill of materials lists what is ordered**, and a row nobody can order is a note pretending to be a purchase. Checking that turned up two things nobody had asked for. **A cable the tuning chain needs and this bill never bought**, the GH1.25 3-pin lead from the adapter board out to the debug tool, which is now a row at US$0.90. And **the newer V1.1 manual reverses the motors' termination-resistor default**, which the actuator line had stated as fact; that line now says to read the switch rather than trust either revision. **The bulk bus capacitance was sized on 2026-09-13**, from the drivers and the lead run rather than from a measurement, and it is the first number that line has ever carried; the cans are neither price-checked nor sourced to a listing, and the same pass found **the main disconnect row stale against the CAD**, which has moved to an XT60 with no anti-spark in it. That row now says so and has to be re-sourced. **The emergency stop line was deleted on 2026-09-14.** It had no home in the CAD, and with it gone **nothing on this bill stops the motors short of pulling the loop key**, which the section on the disconnect says is not an emergency stop.  **The CAN wiring was rearranged on 2026-09-14**, and it is a simplification rather than a purchase. The G474 has three CAN controllers and the bill was using two of them, so the six motors now sit **two to a bus, paired left and right by joint** — both hips, both knees, both wheels. Every bus is then a straight line from one motor through the carrier to the other, with no junction anywhere in it, which is what lets all six harnesses run home to the torso without a splice. Three consequences on this table: **one MCU board runs the robot** and the second is a spare, **three transceivers are fitted** and the fourth is a spare, and **no termination resistor goes on the carrier at all**, because both ends of every bus are motors and all six of their own switches stay ON. **It costs the BOOT0 button**, since the third bus’s receive pin is PB8, and that is why a **SWD probe** is now a line in the development-equipment table rather than something assumed to be on the bench.  **The SBC boot media line was deleted on 2026-09-14.** The Banana Pi variant this bill buys is the one with **8 GB of onboard eMMC**, so the board boots with nothing plugged into it and a microSD card was never a part of the robot. Anyone who wants a recovery card can buy a ₹900 one off any shelf, which is not a thing a bill of materials needs to say. The 2 mm standoff under the board stays for the slot itself, which is still on the underside whether or not a card is in it.  **The controller carrier was rebuilt on 2026-09-14** as a 140 × 46 mm two-layer printed board that carries the logic BEC and the bus monitor as well as the core board and the transceivers, and every row it touches was re-sourced the same day: the perfboard is gone and the board itself is a row, and the fuse, the thermal pad, the board's JST-XH headers, heavier wire for the two leads that carry current, and the made-up 8-pin lead the SBC now takes its power through are rows or parts of rows. Every link added that day was opened and its price and stock read, **except two**: the fuse's element14 page and the thermal pad's Robu page both refuse automated reads, so those two rows carry a link found by search and say plainly that neither price nor stock was seen.  **The SBC came off the electronics deck and onto the controller carrier later the same day**, which is three rows on this bill: the four printed posts it stood on are gone, it stands on four bought M2.5 × 10 standoffs screwed to the carrier instead, and **the carrier's four Ø8.6 mm holes went with them** — that was the one hole on the board bigger than the board house can drill, so the carrier no longer needs anything done to its Gerbers before it is ordered. The M2.5 heat-set inserts are off the bill and the M2.5 screw count doubles to eight.  **The whole bill was then re-read link by link on 2026-09-14**, all 101 of them. Seventy-four answered. The rest refuse automated reads, and they are the same shops every time: **all nineteen Robu links, element14's three, Mouser's one and Flipkart's four**, so wherever this bill quotes a price from one of those it is an older reading rather than today's. Where a readable shop sells the same part, it is now named on the row beside the one that will not open. Four things had moved: the cell alarm is ₹95 rather than ₹86, Robocraze is out of 100 nF capacitors, and the Daly BMS and the Matek BEC are still out of stock at the vendors this bill prices them from. **Prices marked *checked 2026-09-14* were read from the vendor's own page that day.**  **The motor-power contactor line was deleted on 2026-09-14.** It had been on WAIT from the day it was written: no part, no size, no price and no home in the CAD, waiting on a bus-current measurement nobody has taken. That is the same rule that removed the emergency stop — a row nobody can order is a note pretending to be a purchase — and it costs the same two things. **Nothing on this bill switches motor power**, so the loop key pulled by hand is the whole of it, and **the pre-charge resistor loses the row it was homed on**, which leaves the inrush the XT60 change created as an open gap with no part waiting to close it.  **The power switch board became section 1b on 2026-09-16, and its parts were sourced in India for the first time.** Until then its six lines sat among the general electrical ones carrying the word *generic* where a link should be, which hid what sourcing them actually found: **five of them cannot be bought in India at all.** The four-terminal shunt is stocked by nobody here in any package at any resistance near 1 mΩ; the P-channel MOSFET has one domestic alternative, the IRF4905, whose 20 mΩ against the design's 6.7 would dissipate 4.7 W per device in free air; the BAT46 Schottkys have no axial substitute in stock at any voltage; the BZX79-C15 has a stocked equivalent in a fatter body; and the 14.7 kΩ 1 %, one of the two resistors that set the cutoff voltage, turned up nowhere. **One substitution was measured rather than guessed**: silicon diodes in place of the Schottkys shorten the hold-through from 0.97 s to 0.84 s. Two further things are unconfirmed rather than missing, and both could cost a board revision — **no Indian resistor listing states a body size**, and the usual 1/4 W part sold here is the 0207 rather than the 0204 the layout is drawn around, twenty-three of them standing upright on a 2.54 mm pitch; and neither tantalum listing says whether it is through-hole. **The blade-fuse holder could not be priced at all**, because every Indian page selling one refused to open. **Every entry in the "Current part / specification" column was cut to twenty words or fewer the same day**, across all three tables; what left that column moved into the notes beside it or into prose under the table, and nothing was dropped.  **THE MAIN DISCONNECT WAS DELETED ON 2026-09-16 AND A MOMENTARY BUTTON TOOK ITS PLACE IN THE REAR WALL**, which reverses what the section below used to argue and is recorded there rather than quietly rewritten. The half of that argument about amps stands — no 12–16 mm panel switch will carry 24 A, so a switch can only command the bus — and the power switch board is what commands it. What went is the case for keeping a pull-link beside the button: a wall with both asks the user which one turns the robot off, the button had nowhere else to go, and the standing-current worry turned out not to exist, since the switch board has no DC path from the pack at all when it is off. **The cost is that nothing isolates the pack any more** except unplugging one inside the lid, and a failed-short MOSFET looks exactly like a working one. **The station moved with the part**: there is 11.2 mm of clear depth behind the disconnect's old x 18 and a panel switch needs more, so the button is at x −44 where the wall offers 21.4 mm. The part is a **Daier GQ-12B/S**, ₹190 and in stock in Mumbai, and it is the first thing on this bill whose only dimensioned figure is a maker's drawing rather than a listing. **The wall lost two M2 screw holes with the disconnect**, and the thinnest material on the shell with them. **And the bus shunt was re-specified in the same pass**: it had been a Vishay CPSL axial part, and that family does not exist at 1 mΩ, so the board had been laid out to a footprint for a shunt nobody makes. It is an Isabellenhuette PBV-R001-F1-1.0 now, which is +6 g and the whole of this pass's mass change.  **AND THE CURRENT MEASUREMENT WAS DELETED LATER THE SAME DAY, WHICH TAKES THAT SHUNT BACK OFF THE BILL ENTIRELY.** Sourcing it is what made the case: at €14 in Germany, $18.60 at LCSC and $43.37 at DigiKey, with no Indian stock of any four-terminal shunt in any package, it was the most expensive and least available part on this bill by a wide margin — more than the rest of the power switch board put together. What it bought was never protection, since the low-battery cutoff is a comparator on bus VOLTAGE and never looked at current, and the six actuators report their own torque over CAN; what it bought was the runtime figure `docs/NOTES.md` is still waiting on, and that is a characterisation taken once on a bench, where a clamp meter round the pack lead answers it as well. **What is given up is coulomb counting**, which nothing on this robot does yet, and the cheap way back is a two-terminal shunt on a future board revision with a one-off software calibration. The INA226 stays on the carrier as a voltmeter: it reads the bus on its own VBS pin, which never went through the shunt. The board is −8 g, its sense plug J1 is gone, and the shunt's row, the twisted sense pair and the "buy later" line that waited on a bus-current measurement are all off this bill.  **THE WHOLE "NO INDIAN STOCK" CLAIM WAS RE-TESTED ON 2026-09-22 AND MOSTLY COLLAPSED.** Every such finding on this bill came from surveying hobby shops — Robu, Robocraze, ElectronicsComp, Kitsguru, Probots — and none of them from the catalogue distributors that have Indian operations: **element14 India, Mouser India, RS India and TME India**, which serve the same global inventory at a rupee price in three to six days. Four parts this bill called unbuyable are on element14 India with order codes: the **BAT46** at ₹64.05 with **9 459 in stock**, the **Keystone 3568** holder at ₹109.62, the **BZX79-C15** in the DO-35 the board is drawn for, and the **RXEF185**. The substitutions this bill argued about — 1N4148s for the Schottkys, a fat-bodied 1N4744A for the zener, an unknown-pitch holder for the Keystone — are all unnecessary. **So is the import.** What survives is one line, and it is not on the power switch board: **the Matek BEC12S-PRO logic converter**, which on 2026-09-22 was sold out at RC Mumbai, pre-order at Indian Robo Store, and in stock at two European shops. The domestic alternative beside it is down to two units. **And one thing the collapse does not touch is body size:** the power board stands twenty-three resistors on end and is drawn around an 0204, where the Indian hobby-shop quarter-watt is the fatter 0207, so those want buying as a named series from a distributor rather than by wattage from a shop.
**Project baseline:** 360 mm, six-motor wheeled biped — hip pitch, knee and a driven wheel on each leg — using DAMIAO DM-J3507-2EC actuators. Hip roll and the ankles are deleted, and there are no feet. **It carries its own 6S 2200 mAh battery** and the umbilical is gone; the torso grew from 125 × 68 × 65 mm to 153.9 × 72 × 86 to hold one and the power hardware beside it, which is where the 21 mm of extra height came from. **Its width is no longer a chosen number** — `cad/wheeled_parameters.py` derives it from the hip clevises, so the shell now ends exactly where they do.

This BOM is intentionally split between parts that should be sourced early and commodity parts that should remain flexible until the CAD/electrical design is mature. Purchase links are practical India-oriented sourcing references, not immutable approved vendors. Re-check price, GST, shipping, stock and seller immediately before ordering. Imported prices exclude shipping, customs duty, IGST, payment/FX charges and courier handling unless explicitly stated.

Printed structural parts will be fabricated offsite. The BOM therefore keeps the required material/specification information and still does not attempt to source printers, dryers or filament. **It does now name the bureaus that would print the parts — section 12, added 2026-09-21** — because "quote separately" had stood against the printed structure in section 5 since this bill was written with nobody named to ask. None of those rows is a quote; no file has been sent to anybody.

**One caveat that sits above the whole table.** The 2,300 g ceiling and the actuator size were both derived for the walking robot, and **the wheeled robot's torque envelope has not been re-derived**. The answer does change with wheels. Nothing here should be read as confirming that six DM-J3507s are the right size for this machine; it records what the current CAD is built around.

## Sourcing risk legend

- 🔴 **High** — specialist/imported; can become a schedule blocker. Source early.
- 🟠 **Medium** — available, but exact variant/geometry may have lead-time or compatibility issues.
- 🟢 **Low** — commodity or readily available from Indian suppliers.
- ⏸️ **WAIT** — design/test dependency is not frozen; do not select a product merely to complete the BOM.

## 1. Core BOM

**Split into electrical and mechanical, 2026-09-11.** It was one table until the
battery went back in, and one table stopped working the moment the power system
grew from "a socket in the back wall" into nine line items of its own. The split
is by WHAT A LINE IS, not by who buys it: anything that carries current or makes
a decision is electrical, anything that carries load or holds something in place
is mechanical. A few lines could sit either side -- the connectors are mouldings
as much as they are conductors -- and those went electrical, because what decides
whether they are right is a voltage and a current rather than a fit.

**Then split again on 2026-09-16, and the power switch board took a table of its
own.** That is a different kind of split from the first: not a class of line but
a single assembly, twenty-odd parts that are built together, fail together and
are ordered together. Scattered through the electrical table they read as
commodities, and the thing that actually matters about them was invisible --
**five of those lines have no Indian source at all**, and the board cannot be
built without an import. Section 1b says which, and what each substitution
costs.

**Every entry in the "Current part / specification" column is twenty words or
fewer**, from the same day. That column had grown into the place where a line's
history, its warnings and its provenance all went, which made the tables
unreadable as tables: what a thing IS now sits in that column, why it is that
and what to watch for sits in the notes beside it or in the prose under the
table. Nothing was deleted to make the count -- it moved.

### 1a. Electrical

**The robot carries a battery again.** It was tethered from August 2026 to
September 2026 and the umbilical is now deleted, along with the boom that was
supposed to carry it and never got designed. The nine battery lines head this
table because none of them existed a week ago and nothing else can be bought
until they are settled.

**Everything on the power switch board moved out of this table on 2026-09-16**
and is section 1b. That board is a single assembly with a single set of
problems, and having its twenty-odd parts scattered through the general
electrical table hid the thing that matters about it: most of it cannot be
bought in India.

| Subsystem | Qty | Current part / specification | Indicative price | Purchase / source link | Risk | Notes |
|---|---:|---|---:|:--|:--:|---|
| **Battery** | 2 + 1 spare | **3S 2200 mAh 35–40C soft-case LiPo, XT60**, 76×33×25 mm, ~144 g. Two in series make 6S | **₹1,465** checked (GenX) · **₹2,199** checked (Bonka) | [Robokits — GenX 3S 2200 mAh](https://robokits.co.in/batteries-chargers/drone-batteries/genx-power-premium-lipo-battery/genxpower-11.1v-lipo-batteries/genx-11.1v-3s-2200mah-40c-80c-premium-lipo-lithium-polymer-battery) · [Indian Hobby Center — Bonka 3S 2200 mAh 35C](https://www.indianhobbycenter.com/products/bonka-2200mah-35c-3s1p-11-1v-lipo-battey) | 🟠 | The pair makes the robot's 6S 2200 mAh, 48.8 Wh, 25.2 V pack. Two 3S weigh ~100 g less than one 6S. Buy a matched pair; measure one before printing the pelvis |
| **Battery series harness** | 1 + 1 spare | **Ready-made 2-into-1 XT60 series harness**, 14 AWG silicone | ~₹200-class, not price-checked | [Robu — XT60 series harness, 2 packs](https://robu.in/product/xt60-harness-for-2-packs-in-series-1pc) · [Robu — SafeConnect series harness 2M1F](https://robu.in/product/safeconnect-xt60-harness-for-series-connection-2m1f) | 🟢 | Buy, don't make. A straight XT60 jumper puts packs in parallel or shorts them. Match harness gender to the packs |
| **Charge inlet** | 1 panel socket + 1 spare | **AMASS XT60E-F female panel mount**, flange outside the rear wall, on 2 × M2 with washers and nuts | **₹199** checked 2026-09-13, in stock (Probots) | [Probots — AMASS XT60E-F panel mount](https://probots.co.in/xt60e-f-female-black-connector-for-lipo-battery-esc-brushless-motor.html) | 🟠 | **Recessed sockets and not pins**, because this side is live at pack voltage whenever cells are connected — it lands on the BMS's charge input, ahead of everything. **The charger's lead needs a male XT60.** Measure the body before printing: its cut is scaled |
| **Antenna lead and bulkhead** | 1 + 1 spare | **u.FL/IPEX to SMA (or RP-SMA) female bulkhead pigtail**, ~10–20 cm RG178, plus a matching antenna | ~₹100–200 | [Probots — u.FL to RP-SMA bulkhead pigtail](https://probots.co.in/ipex-1-u-fl-to-rp-sma-female-bulkhead-pigtail-10cm-rg178-11mm-thread.html) · [Robokits — SMA to IPEX](https://robokits.co.in/wireless-solutions/wireless-accessories-and-antenna/female-sma-to-ipex-connector) | 🟠 | Gets the radio out of the sealed shell. SMA and RP-SMA don't mate; match the SBC's connector |
| **Balance leads, and the merge** | 2 × 3S + 1 × 6S | Two JST-XH 4-pin leads for the packs' tails, and one 7-pin lead spliced to them for the BMS | **₹12** (4-pin) · **₹15** (7-pin), checked | [Indian Hobby Center — 4-pin JST-XH lead, 25 cm](https://www.indianhobbycenter.com/products/4-pin-jst-xh-2515-rmc-female-connector-with-wire-25cm-2-54mm-pitch-1-pc) · [7-pin](https://www.indianhobbycenter.com/products/7-pin-jst-xh-2515-rmc-female-connector-with-wire-25cm-2-54mm-pitch-1-pc) | 🟢 | The splice is made inside the shell and lands on the BMS. Omit the upper pack's negative. Meter before connecting |
| **Cell alarm** | 1–2 | 1S–8S balance-lead voltage checker with buzzer | **₹95** checked 2026-09-14, in stock (Robokits) | [Robokits — 1–8S checker](https://robokits.co.in/batteries-chargers/accessories/charge-protection-circuit/li-po-li-ion-1-8s-voltage-checker-and-low-voltage-alarm) · [Robu](https://robu.in/product/lipo-battery-voltage-checker-1s-8s-with-buzzer/) — page refuses automated reads | 🟢 | Backstop only, and the only thing on this bill that watches a single cell. Real protection is setting each motor's undervoltage threshold to 21.6 V |
| **Bus monitor** | 1 | **INA226** I²C monitor, 36 V bus — **fitted for bus VOLTAGE only, with no external shunt** | **₹120** checked | [Techtonics — INA226 module](https://techtonics.in/product/ina226-i2c-voltage-current-and-power-monitor-module/) | 🟢 | **THE CURRENT MEASUREMENT WAS DELETED ON 2026-09-16** and the four-terminal shunt row in section 1b went with it, so this reads pack voltage on its VBS pin and nothing else. **Leave its on-board R100 in place** — the instruction to lift it existed only for the external Kelvin pair. Its IN+/IN− now go nowhere: tie them to ground at J7 on the carrier rather than leaving them floating. Mounted on the carrier on M2 × 10, landed on all eight header pins |
| **Battery management system** | 1 + 1 spare | **Daly Li-ion NMC 6S 24 V 20 A**, 58×33×8.2 mm, 45 g, passive balancing from 4.18 V/cell, wired **charge-only** | **₹867** — **still out of stock at QuartzComponents on 2026-09-14** · **₹475** from an IndiaMART reseller, the only Indian listing showing stock | [QuartzComponents — Daly 6S 24V 20A NMC](https://quartzcomponents.com/products/daly-li-ion-6s-24v-20a-battery-management-system) · [IndiaMART — Daly 6S 24V 20A, Noida](https://www.indiamart.com/proddetail/daly-li-ion-6s-24v-20a-waterproof-battery-management-system-bms-protection-board-2852913515255.html) | 🟠 | Balances at 30 mA. Gives no over-discharge cutoff of its own — that is the power switch board's, at pack level. Two printed parts are cut to it: measure first |
| **Charger** | 1 | **IMAX B6AC, 80 W, 1–6S** charge/discharge/storage | **₹2,285** checked, in stock (Robokits RKI-1369) · **₹2,079** (B6, DC only, Robu) | [Robokits — IMAX B6AC 80 W](https://robokits.co.in/batteries-chargers/chargers/imax-chargers/imax-b6ac-80w-charger-discharger-1-6-cells) · [Robu](https://robu.in/product/imax-b6-80w-6a-charger-discharger-1-6-cells/) | 🟢 | Charge via the inlet with the robot switched off, 6S at 2.2 A. **Nothing isolates the pack while it charges** since the loop key went — the bus is dead because the MOSFETs are open, not because anything is unplugged. A balance board plus series harness shorts a pack |
| **Power distribution board** | 1 + 1 spare | **SwiftWing PDB-02-XT60**, 3S–6S direct battery bus: 50×50×1.6 mm, 4-layer 2 oz copper, 13 g, XT60 input | ~₹300–600 class, not price-checked | [Robu — SwiftWing PDB-02-XT60](https://robu.in/product/swiftwing-pdb02-xt60-power-distribution-board/) · [datasheet v1.2](https://swiftwingtech.io/downloads/datasheets/swiftwing-pdb-02-xt60-6xt30-power-distribution-board-datasheet-v1-2.pdf) | 🟠 | Six pairs of ESC solder tabs, 4 × M3 on a 45 mm square; the pelvis posts follow that square and so does the power switch board above it. **Solder every motor lead before that board goes on** — it covers this one completely. Confirm its 26 V rating with the vendor |
| **Debug serial lead to the PC** | 1 + 1 spare | **GH1.25 3-pin cable, 300 mm**, from the adapter board to the USB debug tool | **US$0.90** checked (Foxtech), in stock | [Foxtech — DAMIAO joint motor cables](https://store.foxtech.com/damiao-joint-motor-cables/), option **GH1.25-3Pin Reverse Cable (300mm)** | 🟠 | Links adapter board to USB debug tool; nothing else supplies it. Buy on the same Foxtech order |
| **DAMIAO adapter board** | 1 + 1 spare | **SH1.0 3-pin + 8-pin to XT30 + GH1.25 adapter board**, DAMIAO's own | **US$2.30** checked (Foxtech), in stock | [Foxtech — DAMIAO joint motor cables](https://store.foxtech.com/damiao-joint-motor-cables/), the option named **SH1.0 3Pin + 8Pin to XT30 + GH1.25 Adapter Cable** | 🟠 | Not included with the motor; the only route to the tuning assistant. Do not substitute the XT30 (2+2) power adapter |
| Realtime MCU dev board | 2 | **WeAct STM32G474CEU6 core board, 36.28×28.14 mm** — the compact one, two 2×12 headers. **Not the "Long Type"** | **~US$6** on the listing's own description, **not read from the shop** | [WeAct Studio's AliExpress store](https://weactstudio.aliexpress.com) · [the listing](https://www.aliexpress.com/item/1005006170922820.html) · [WeActStudio GitHub, the source of the STEP the CAD measures](https://github.com/WeActStudio/WeActStudio.STM32G474CoreBoard) | 🔴 | The Long Type is the same MCU on a 63.06 × 18.24 mm board with two 1 × 20 headers and does not fit the carrier. **Both Indian listings are that board.** Import the compact one |
| **Single-board computer** | 1 | **Banana Pi BPI-M4 Zero, 65×30 mm**, 2 GB RAM and 8 GB onboard eMMC | **₹8,899** before GST, **₹10,501** with it — checked 2026-09-14, in stock | [Tanna TechBiz — BPI-M4 Zero 2 GB/8 GB](https://tannatechbiz.com/banana-pi-m4-zero-2g-ram-8g-emmc.html) · [Banana Pi wiki](https://wiki.banana-pi.org/Banana_Pi_BPI-M4_Zero) | 🟠 | The eMMC is why no boot card is on this bill. Mounting holes are inferred, not published — measure before drilling. Stands on the carrier on four M2.5 × 10 standoffs |
| CAN-FD transceiver | 4 | **MCP2562FD-E/P — 8-pin PDIP**, 8 Mbps CAN-FD, with a separate **VIO** pin for 3.3 V logic | **₹203** checked 2026-09-14, in stock (RS India) · ₹131 (1+) read at element14 on 2026-09-13 | [RS India — MCP2562FD-E/P](https://in.rsdelivers.com/product/microchip/mcp2562fd-e/p/microchip-can-transceiver-8-mbps-8-pin-pdip/8243129) · [element14 India](https://in.element14.com/microchip/mcp2562fd-e-p/can-transceiver-8mbps-1-tx-rx/dp/2434898) — refuses automated reads | 🟢 | **Three fitted, one per bus; the fourth spare has no seat.** Through-hole, socketed; VDD 5 V, VIO 3.3 V. STBY floats high: drive it low |
| **Carrier board** | 5 — the minimum order | **140×46 mm two-layer PCB, 1.6 mm FR-4, 1 oz copper**, 0.25 mm tracks, 0.2 mm clearance, 249 holes | **from ₹799 for five**, checked — the service's floor; a 140 × 46 board gets its own figure once the Gerbers are uploaded | [LionCircuits — Make in India PCB](https://www.lioncircuits.com/make-in-india-pcb) | 🟠 | Plotted from `electrical/kicad/carrier.kicad_pcb`. Every hole and track is inside the fab's standard 6/6 mil rules, Ø0.4 to Ø3.4. Bengaluru, 5–6 days. Nothing has been fabricated yet |
| **Carrier passives, sockets and headers** | 1 set | **7×100 nF, 2×10 µF 50 V, 2×4.7 kΩ, 3×DIP-8 sockets, 2 header strips, 7 JST-XH headers** | the 2026-09-13 lot less its perfboard, plus **~₹45** of headers, strips and a second 10 µF checked 2026-09-14: headers ₹2–5 each, female strip ₹10, male ₹7, 10 µF ₹4, all in stock | [QuartzComponents — 8-pin DIP socket, ₹2](https://quartzcomponents.com/products/ic-base-8-pin) · [QuartzComponents — 100 nF 50 V, 5 pcs, ₹10](https://quartzcomponents.com/products/10000-pf-0-1uf-ceramic-capacitor) · [QuartzComponents — 10 µF 50 V](https://quartzcomponents.com/products/10uf-50v-electrolytic-capacitor) · [Indian Hobby Center — 120 Ω 1/4 W](https://www.indianhobbycenter.com/products/120-ohm-carbon-film-resistors-25-watt-tolerance-5-percent) · [QuartzComponents — 1 × 40 female strip](https://quartzcomponents.com/products/40-pin-straight-female-berg-strips) · [male strip](https://quartzcomponents.com/products/40-pin-break-away-headers-straight-male-headers) · [Indian Hobby Center — JST-XH 2-pin](https://www.indianhobbycenter.com/products/2-pin-jst-xh-2515-rmc-male-connector-2-54mm-pitch-1-pc) · [4-pin](https://www.indianhobbycenter.com/products/4-pin-jst-xh-2515-rmc-male-connector-2-54mm-pitch-1-pc) · [6-pin](https://www.indianhobbycenter.com/products/6-pin-jst-xh-2515-rmc-male-connector-2-54mm-pitch-1-pc) · [8-pin](https://www.indianhobbycenter.com/products/8-pin-jst-xh-2515-rmc-male-connector-2-54mm-pitch-1-pc) | 🟢 | See **what is in the carrier's parts set** below the table for what each one is for. **Genuine JST-XH is 2.50 mm, not the listed 2.54** — measure before soldering |
| **Carrier bus-feed fuse** | 1 + 1 spare | **Littelfuse RXEF185 resettable PTC, 1.85 A hold, 72 V, radial on 5.1 mm leads** | listed at element14 India, order code 3296311, checked 2026-09-22; price not read | [element14 India — Littelfuse RXEF185-2, order code 3296311](https://in.element14.com/littelfuse/rxef185-2/pptc-resettable-fuse-1-85a-72v/dp/3296311) | 🟢 | Not the Bourns MF-R185 at 30 V: this bus is 25.2 V full and higher while a leg regenerates. Protects the carrier's feed, which the pack's fuse does not. **The row read “page not opened, so no price or stock” until 2026-09-22**; the listing is real and domestic |
| **BEC thermal pad** | 1 sheet | **1 mm silicone thermal pad, electrically insulating**, cut to the BEC's 35×24 mm | **not seen** | [Robu — high-conductivity thermal silicone pad](https://robu.in/product/blue-high-conductivity-whole-piece-of-thermal-silica-gel-cpu-notebook-led-power-heat-sink/) | 🟠 | **Must be the insulating kind**: it lies between the BEC's bare laminate and the ground pour, and it is the module's only heat path. Cut to 30 × 24, clear of its four pins |
| Main IMU | 1–2 | **BNO085 Nano breakout** | ~₹2.1k | [Robocraze — BNO085 Nano](https://robocraze.com/products/bno085-9-dof-orientation-imu-sensor-fusion-nano-breakout-board) | 🟢 | Nano board only; the Adafruit breakout does not fit. The pelvis prints an 11 × 10 mm adhesive seat |
| USB-CAN-FD debug interface | 1 | Waveshare USB-CAN-FD or DAMIAO-compatible interface | **₹12,975** checked | [Robocraze — Waveshare USB-CAN-FD-B](https://robocraze.com/products/waveshare-industrial-can-can-fd-bus-data-analyzer) | 🟠 | -B variant for Linux. May not run DAMIAO's tuning assistant; check with first motors. Switch its 120 Ω off |
| Branch connectors | 8–10 pairs provisional | Genuine **AMASS XT30** or locking equivalent | **₹41/pair** checked | [Robokits — original AMASS XT30](https://robokits.co.in/batteries-chargers/accessories/plugs-and-connectors/amass-xt30-male-and-female-connector-original-xt30-f-m?cPath=67_618_623) | 🟢 | Six motor branches plus spares. Do not bulk-buy until routing confirms the connector count |
| Main bus wire | ~1 m robot-side | 14 AWG high-strand silicone wire | **₹103–105/m** checked | [QuartzComponents — 14 AWG silicone, red](https://quartzcomponents.com/products/14awg-silicone-wire-red-1-meter-high-quality-ultra-flexible-for-battery-packs) · [black](https://quartzcomponents.com/products/14awg-silicone-wire-black-1-meter-high-quality-ultra-flexible-for-battery-packs) | 🟢 | Down from ~3 m now the tether is gone; all runs are inside the torso. The pack lead and the switched output both land on the power switch board |
| Motor branch wire | 4–6 m | 16–18 AWG high-strand silicone wire | **₹65/m** (16 AWG) · **₹40/m** (18 AWG), checked | [QuartzComponents — 16 AWG silicone](https://quartzcomponents.com/products/16awg-silicone-wire-black-1-meter-high-quality-ultra-flexible-for-battery-packs) · [18 AWG](https://quartzcomponents.com/products/high-quality-ultra-flexible-18awg-silicone-wire-black-1-meter) | 🟢 | Final gauge after measured motor current |
| CAN wiring | ~4 m | Flexible twisted pair ~24–26 AWG | **₹18/m** checked | [QuartzComponents — 26 AWG silicone](https://quartzcomponents.com/products/26awg-silicone-wire-black-1-meter-high-quality-ultra-flexible-wire) | 🟢 | Twist matched pairs; move to proper 120 Ω cable if signal-integrity testing demands it |
| **Motor lead pigtails** | 6 + 2 spare | **JST SH 1.0 mm 8-pin socket on 300 mm of 30 AWG wire**, plugged one end, bare the other | not price-checked (Robu) | [Robu — JST-SH 8-pin, 300 mm wire](https://robu.in/product/jst-sh-1mm-8-pin-female-housing-connector-with-300mm-wire30-awg/) | 🟠 | **300 mm does not reach a wheel motor**; buy 800 mm leads for those two. Confirm the motor's pin order |
| SH1.0 8-pin breakout PCB | 2–4 | **JST SH 1.0 mm 8-pin socket on a 2.54 mm 2×4 header**, 1.6 mm FR4, horizontal entry | **US$0.30** listed 2026-09-14, in stock (MKTechnic) | [MKTechnic — JST SH 8-pin adapter](https://mktechnic.com/product/jst-sh-8-pin-1-0mm-horizontal-smd-pcb-adapter-breakout-board/) | 🟠 | The only way an SH socket reaches a through-hole board. **Bench use, not the flight carrier.** Not found in India |
| **Logic and sensor harness** | ~2 m + a connector kit | **26–28 AWG** hook-up wire, **1 m of 22 AWG** red and black, a **JST-XH crimp kit**, one **8-pin JST-XH lead** | **₹18/m** 26 AWG · **₹21–22/m** 22 AWG · **₹500** kit · **₹19** 8-pin lead, checked; the 22 AWG and the lead on 2026-09-14, in stock | [QuartzComponents — 26 AWG silicone](https://quartzcomponents.com/products/26awg-silicone-wire-black-1-meter-high-quality-ultra-flexible-wire) · [22 AWG red](https://quartzcomponents.com/products/22awg-silicone-wire-red-1-meter-high-quality-ultra-flexible-wires) · [22 AWG black](https://quartzcomponents.com/products/22awg-silicone-wire-black-1-meter-high-quality-ultra-flexible) · [ThinkRobotics — 460-piece JST PH/XH kit](https://thinkrobotics.com/products/460pcs-jst-ph-2-0-connector-kit-2-to-6-pin-male-female-plug-housing-with-crimp-terminal-assortment-box) · [Indian Hobby Center — 8-pin JST-XH lead, 25 cm](https://www.indianhobbycenter.com/products/8-pin-jst-xh-2515-rmc-female-connector-with-wire-25cm-2-54mm-pitch-1-pc) | 🟢 | **Four leads:** the IMU, the SBC's made-up 8-pin, the bus feed, and the hold and button lead down to the power switch board. Use plugs, not solder. The two that carry current are the 22 AWG |
| **Logic DC/DC** | 1 + 1 spare | **Matek BEC12S-PRO**, 9–55 V in, 5 V/8 V/12 V selectable at 5 A continuous, 35×24×5.5 mm, 5 g | **₹1,693.66 — “Sold out” at RC Mumbai** · **₹1,875 — “Pre-Order” at Indian Robo Store**, both checked 2026-09-22 · **£19.00 inc VAT, “200+ In Stock Now” (3DXR, UK)** · **€20.19, “In Stock” (Rotorama, Czechia)** | [Indian Robo Store — Noida, pre-order](https://indianrobostore.com/product/rts-mateksys-12s-pro-bec-9-55v-to-5v8v12v-5a) · [RC Mumbai — sold out](https://www.rcmumbai.com/products/matek-12s-pro-bec-12s-9-55v-input-5v-8v-12v-5a-output) · [3DXR, UK — in stock](https://www.3dxr.co.uk/products/matek-systems-bec12s-pro-9-55v-to-5v-8v-12v-5a) · [Rotorama, Czechia — in stock](https://www.rotorama.com/product/matek-bec12s-pro-3-12s-5-8-12v-5a) · [Matek's own page](https://www.mateksys.com/?portfolio=bec12s-pro) | 🔴 | **THE ONE LINE ON THIS BILL WITH NO INDIAN STOCK, 2026-09-22.** Every other row that claimed to be an import turned out to be a hobby shop's gap rather than the country's; this one is real. Three domestic sellers were checked and the best is a pre-order. Two European shops hold it, so **buy it in Europe if anyone is there**; otherwise take the pre-order early, because the alternative below is thinner than it looks. 9 A peak. Set it to 5 V. Rides flat on the carrier, component side up, on four pins. **Matek publish no pad drawing: measure one before ordering** |
| Logic DC/DC — alternative | in place of the Matek | **7Semi AP64500 buck module (BO-10188)**, 7–40 V in, fixed 5 V at 5 A continuous, bare board. Size not published | **₹823**, and **“Only 2 left in stock”** on 2026-09-22 (Robocraze) | [Robocraze — 7Semi AP64500 5 V 5 A](https://robocraze.com/products/7semi-dc-dc-buck-converter-7v-40v-input-to-5v-5a-output-ap64500) | 🟠 | **A domestic source with two units on the shelf is not a second source.** It was “in stock” on 2026-09-14 and is down to two a week later, so it can go the way the Matek did. Its 40 V input also leaves **10 V of margin on a bus that reaches 30 V while a leg regenerates**, where the Matek leaves 25. Check against the 35 × 24 × 5.5 slot; the size is still unpublished |

**What is in the carrier's parts set.** The row above is one line because it is one
order; this is what each part of it does. **No termination resistor goes on the
carrier at all** — both ends of every bus are motors, and all six of their own
switches stay ON — though keep **2 × 120 Ω** 1 % 0.25 W metal film in the box
against a motor whose switch cannot be reached. The **seven 100 nF** X7R go at VDD
and VIO of each transceiver and on the 3.3 V rail; the **two 10 µF 50 V**
electrolytics are bulk on the 5 V and on the bus feed where it arrives; the **two
4.7 kΩ** are I²C pull-ups to 3.3 V, fitted only if neither sensor module carries
its own. **Three DIP-8 sockets**, one per transceiver. For the core board, two
2 × 12 sockets made from **two 1 × 40 female strips** cut into four 1 × 12 lengths;
**one 1 × 40 male strip** gives a 1 × 8 for the bus monitor — all eight of its pins,
not five — and four single pins for the BEC, whose pads are at 3.81 mm and cannot
take a 2.54 mm strip. The **seven JST-XH top-entry headers** are 2 × 2-pin (the bus
feed, and one spare, J7, left over from the deleted shunt's sense pair), 3 × 4-pin
for the three buses, 1 × 6-pin for the IMU and 1 × 8-pin for the SBC.

### 1b. The power switch board

**This is one assembly and it is now its own table, from 2026-09-16.** The board
sits in the pack's positive lead between the pack and the distribution board,
and it is three things at once: the robot's on/off switch, its
low-battery cutoff, and the mount for the main fuse and the bulk capacitors.
**It was four until 2026-09-16**, when the current measurement was deleted: the
four-terminal shunt and its sense plug came off, which is −8 g and about 250 mm²
of the most awkward footprint on the board. `electrical/power.py` is its netlist and computes what these
component values do; `electrical/power_sch.py` draws it; `electrical/power_pcb.py`
lays it out. **Nothing on it is surface mount**, so it can be built by hand with
an iron.

**The shunt is off this board entirely, 2026-09-16, and it went in two steps.** It was first corrected from a Vishay CPSL axial part, which does not exist at 1 mΩ — that family starts at 10 — to an Isabellenhuette PBV-R001-F1-1.0 on a footprint drawn from the maker's own Z-DW-132b. Sourcing that part is what then deleted it: €14 in Germany, $18.60 at LCSC, $43.37 at DigiKey and no Indian stock of any four-terminal shunt in any package, which made it the most expensive and least available line on this bill. **R1 and its sense plug J1 are gone**, and the two pours the shunt used to bridge are one pour from both MOSFET drains to the output pad.

**Read the paragraph under this table before ordering any of it.** **It said five
of these lines had no Indian source at all. The number is nought.** Two things
happened on 2026-09-22. The switch was respecified, because the Vishay part had
gone obsolete, onto an IRF4905 that both countries stock — so the argument that
used to sit here, that the only Indian alternative was a part the board could not
cool, was settled by cooling it differently with four devices instead of two. And
the remaining four lines were re-checked **against the catalogue distributors that
operate in India** rather than against hobby shops, which is all this section had
ever looked at. element14 India holds every one of them, at a rupee price and
three to six days. The BAT46 it called unfindable is there nine thousand deep.

| Subsystem | Qty | Current part / specification | Indicative price | Purchase / source link | Risk | Notes |
|---|---:|---|---:|:--|:--:|---|
| **Power switch board** | 5 — the minimum order | **50×50 mm two-layer PCB, 1.6 mm FR-4, 2 oz copper**, KiCad DRC and ERC both clean | **₹799 for five at 1 oz**; 2 oz wants a Gerber upload before anyone quotes | [LionCircuits — Make in India](https://www.lioncircuits.com/make-in-india-pcb) · [PCB Power](https://www.pcbpower.com/page/pcb-fabrication) · [Zbotic](https://zbotic.in/pcb-manufacturing/) | 🟠 | **2 oz and not 1**: the zones are sized for it, and at 1 oz the switch's copper runs hot at the peak current nobody has measured. **LionCircuits' ₹799 flat tier is 1 oz only.** PCB Power offers 0.5–4 oz and Zbotic 1 or 2 oz in the same dropdown at 15–20 days. **It was 54 × 32.5 mm** until 2026-09-15: it is the bought distribution board's own footprint now, on that board's own four screws |
| **Power switch MOSFETs** | 4 + 2 spare | **Infineon IRF4905PbF, P-channel −55 V, 20 mΩ at −10 V, TO-220AB**, four in parallel | **20.90 kr** checked 2026-09-22, **38 460 in stock** (DigiKey DK) · **₹78**, "Availability: 3351" (ElectronicsComp) | [DigiKey DK — IRF4905PbF](https://www.digikey.dk/en/products/result?keywords=IRF4905PBF) · [ElectronicsComp — IRF4905](https://www.electronicscomp.com/irf4905-55v-74a-p-channel-hexfet-power-mosfet-to-220-package) | 🟢 | **This line stopped being the import, 2026-09-22.** It specified Vishay's SQP120P06-6m7L, which is **discontinued** — the data sheet is still published and no distributor carries it, and the nearest living part in the package, the SUP90P06-09L at 9.3 mΩ, is backordered into 2028. Low-resistance P-channel in a TO-220 is a thin category now. The IRF4905 is 20 mΩ against 6.7, so **there are four devices where there were two** and each carries 6 A rather than 12: 1.26 W apiece, and the continuous rating goes from 21 A to 23.5. It is a twenty-year-old commodity HEXFET stocked on both continents, which is why it was preferred to Vishay's SUM110P06-07L — 6.9 mΩ, 49 653 in stock, and surface mount, which this board is not |
| **Main fuse and holder** | 2 fuses, 1 holder + spares | **Mini (ATM) blade fuse, 20 A to start**, in a **Keystone 3568 PCB-mount clip holder** | **₹5** per fuse · **₹109.62** for the holder, checked 2026-09-22 (element14 India) | [QuartzComponents — 20 A blade fuse](https://quartzcomponents.com/products/automotive-blade-fuse-20a) · [element14 India — Keystone 3568, order code 2504685](https://in.element14.com/keystone/3568/fuse-holder-0-8-x-2-8mm-pcb-mount/dp/2504685) | 🟢 | **The holder was the risk and is not any more.** The board is drawn to the Keystone's own pad pattern, so a substitute with a different pitch means a board revision — and the genuine part is on a domestic shelf, so no substitute is needed. This row read “holder not found in India at a page that would open” until 2026-09-22; the page that would not open was a hobby shop's. Final fuse value follows measured current |
| **Bulk bus capacitance** / regen clamp | 2 cans + 2 spare | **2 × 470 µF 35 V low-ESR aluminium, 105 °C, 10×16 mm radial, 5 mm pitch**, as C5 and C6 | **₹70 for five** listed, "In stock" (rees52) · ~₹63 each (element14), not confirmed at checkout | [rees52 — 470 µF 35 V low-ESR, pack of 5](https://rees52.com/products/470uf-35v-low-esr-aluminum-electrolytic-capacitors-pack-of-5-rs2098) · [element14 India — Panasonic EEU-FR1V471B](https://in.element14.com/panasonic/eeufr1v471b/cap-470-f-35v-20/dp/1800666) · [Mouser India](https://www.mouser.in/ProductDetail/Panasonic/EEU-FR1V471B?qs=n1SRcuzDZT3ftWy1qYjNlA%3D%3D) | 🟠 | The rees52 part claims 19 mΩ and 2.18 A of ripple, better than the Panasonic reference's 28 mΩ and 1.79 A, but **its listing states no diameter or height** and the CAD reserves Ø10 × 16 — measure before printing. **Not the -L suffix**, which is Ø8 × 20 on 3.5 mm. **Not a polymer and not a ceramic**: an electrolytic's ESR damps the bus ringing. **The reserve was four cans of Ø16 × 25 until 2026-09-15** for the two this bill has always bought. The capacitance is unchanged and still unmeasured, and **the clamp and brake resistor beside them are still ⏸️ WAIT** |
| **Comparator and socket** | 2 of each | **LM393P dual comparator in DIP-8**, and an 8-pin DIP socket to stand it in | **₹24** + GST, "Availability: 498" · socket **₹5** for two, "Availability: 72677" | [ElectronicsComp — TI LM393P DIP-8](https://www.electronicscomp.com/lm393p-texas-instruments-analogue-comparator-dual-differential-2-comparators-300-ns-2v-to-36v-dip-8-pins) · [ElectronicsComp — 8-pin IC base](https://www.electronicscomp.com/8-pin-ic-base-dip) | 🟢 | Both open-collector outputs sit on one pull-up, which makes the enable line an AND: either half can hold the robot off. The same shop's unbranded LM393 is ₹14 with 2685 in stock |
| **Voltage reference** | 2 | **TL431ACLP 2.5 V shunt reference, TO-92** — pin 1 REF, 2 anode, 3 cathode | **₹7** + GST, "Availability: 2946" | [ElectronicsComp — TL431 TO-92](https://www.electronicscomp.com/tl431-adjustable-precision-shunt-regulator-to-92-package) | 🟠 | **The TO-92 pinout is not the surface-mount one** and getting it wrong kills the cutoff. The listing says only "TL431" with no grade, so **the A grade's 0.5 % initial tolerance is not confirmed** — the cutoff arithmetic assumes it |
| **Small-signal transistors** | 4 | **BC546B NPN, 65 V, TO-92** — pin 1 collector, 2 base, 3 emitter | **₹9** + GST for five, "Availability: 2101" | [ElectronicsComp — BC546 TO-92](https://www.electronicscomp.com/bc546-npn-general-purpose-transistor-65v-100ma-to-92-package) | 🟠 | Three fitted plus one spare: Q3 holds the gates down, Q4 turns them off, and Q5 resets C1. **The listing is plain BC546 with no B gain bin**, quoting hFE 110–450; the design wants the B group |
| **Schottky diodes** | 6 fitted + 2 spare | **BAT46, 100 V, DO-35 axial** — the two hold inputs, the button's two paths, D2 and D8 | **₹64.05**, **9 459 in stock**, checked 2026-09-22 (element14 India) | [element14 India — BAT46, order code 9801456](https://in.element14.com/stmicroelectronics/bat46/diode-schottky-small-signal/dp/9801456) | 🟢 | **THIS ROW SAID “no Indian stock, of BAT46 or of any axial Schottky” UNTIL 2026-09-22, AND IT WAS WRONG.** That finding came from surveying hobby shops; element14 India is a domestic distributor with a rupee price and 3–6 day delivery, and it holds nine thousand of the exact DO-35 part. The 1N4148 substitute and its measured cost — hold-through down from **0.97 s to 0.84 s**, which `uv run electrical/power.py` with `V_SCHOTTKY = 0.62` shows — is now a fallback nobody needs |
| **Signal diodes** | 1 fitted + 2 spare | **1N4148, DO-35 axial** — D3 clamps the fast turn-off transistor's base | **₹6** each, "In stock" (Probots) | [Probots — 1N4148](https://probots.co.in/1n4148-small-signal-diode.html) | 🟢 | D2 and D8 now use BAT46; only D3 remains 1N4148 |
| **Gate clamp zener** | 2 | **BZX79-C15, 15 V 0.5 W, DO-35** across the gates, idle while the bus is in range | checked 2026-09-22 (element14 India); the ₹2 1N4744A alternative is no longer needed | [element14 India — BZX79-C15,133, order code 1097217](https://in.element14.com/nexperia/bzx79-c15-133/diode-zener-15v-500mw/dp/1097217) | 🟢 | **Buy the DO-35 part, not the DO-41 substitute.** This row said “no Indian stock of BZX79-C15” and pointed at a 1N4744A in a fatter DO-41 body that would have had to be checked against the footprint. element14 India carries the Nexperia DO-35 part the board is actually drawn for, so that check is off the table |
| **Resistors** | 23 + spares | **0.25 W axial metal film**, 0204 body (3.6 × 1.6 mm), mounted **upright** on a 2.54 mm pitch | **₹1** each, "In Stock" (Kitsguru), for nine of the twelve values | [Kitsguru — 10 Ω](https://kitsguru.com/products/10e-resistance-1-4-watt-5-tolerance) · [1 kΩ](https://kitsguru.com/products/1k-resistance-1-4-watt-5-tolerance-1) · [15 kΩ](https://kitsguru.com/products/15k-resistance-1-4-watt-5-tolerance) · [22 kΩ](https://kitsguru.com/products/22k-resistance-1-4-watt-5-tolerance) · [47 kΩ](https://kitsguru.com/products/47k-resistance-1-4-watt-5-tolerance) · [100 kΩ](https://kitsguru.com/products/100k-resistance-1-4-watt-5-tolerance) · [470 kΩ](https://kitsguru.com/products/470k-resistance-1-4-watt-5-tolerance) · [680 kΩ](https://kitsguru.com/products/680k-resistance-1-4-watt-5-tolerance) · [10 MΩ](https://kitsguru.com/products/10-m-resistance-1-4-watt-5-tolerance) · [ElectronicsComp — 1 MΩ](https://www.electronicscomp.com/1m-ohm-resistance) · **for the 1 % values and the right body:** [element14 India — Vishay MBA0204 series](https://in.element14.com/c/passive-components/resistors-fixed-value/through-hole-resistors?st=MBA0204) | 🟠 | Counts: 10 Ω ×2, 1 k, 15 k, **14.7 k 1 %**, 22 k ×2, 47 k ×3, 100 k ×4, **100 k 1 % ×3**, 470 k, 680 k, 1 M, 10 M ×3. **BUY THESE AS A NAMED SERIES, NOT AS “1/4 W METAL FILM”.** The board stands all twenty-three upright on a 2.54 mm pitch and is drawn around an **0204 body, 3.6 × 1.6 mm**; the usual Indian hobby-shop quarter-watt is the **0207 at 6.3 × 2.5**, nine tenths of a millimetre fatter each on a board where `legalize()` finds five legal spots for one more. The cheap shops above are fine for the nine 5 % values if the body is right — **ask, because none of them publishes one**. The two 1 % values set the cutoff voltage and want a catalogue part anyway. This row said the 14.7 kΩ had **no Indian source at all**; that was a hobby-shop survey, and E96 values in this series are ordinary distributor stock |
| **Capacitors, the small four** | 2 of each | **220 nF 63 V film; 100 nF ceramic disc; 22 µF and 10 µF 16 V tantalum, radial** | film **₹9** + GST, "Availability: 7948" · disc **₹3** for five · tantalums **₹13** and **₹12**, 1685 and 1846 in stock | [ElectronicsComp — 220 nF 63 V box film](https://www.electronicscomp.com/220nf-0.22uf-63v-polyester-box-capacitor) · [0.1 µF disc, 5 pcs](https://www.electronicscomp.com/0.1uf-104-ceramic-capacitor) · [Sunrom — 100 nF 50 V](https://www.sunrom.com/p/100nf104-mlcc-50v) · [22 µF 16 V tantalum](https://www.electronicscomp.com/22uf-16v-tantalum-capacitor) · [10 µF 16 V tantalum](https://www.electronicscomp.com/10uf-16v-tantalum-capacitor) | 🟠 | The film one is the soft start and its value sets the ramp. **Two pitch mismatches to check:** the ElectronicsComp disc is 5 mm pitch where the board is drawn for 2.5, and **neither tantalum listing states whether it is through-hole** — Evelta's confirmed through-hole parts are the right thing and both read "Sold Out". Robocraze is still out of 100 nF |
| **Gate reset capacitor C7** | 1 + spare | **WIMA MKS2C042201K00KSSD, 2.2 uF 63 V 10%, 5 mm pitch** | **price and stock not read** | [TME India — MKS2C042201K00KSSD](https://www.tme.com/in/en/details/mks2-2.2u_63/tht-film-capacitors/wima/mks2c042201k00kssd/) · [WIMA datasheet](https://wima.de/wp-content/uploads/media/e_WIMA_MKS_2.pdf) | 🟠 | Through-hole film, 7.2 x 7.2 x 13 mm; keeps the gates off during C1 reset. **The footprint is the generic `C_Rect_L7.2mm_W7.2mm_P5.00mm`, not a WIMA-specific pattern**, so any 2.2 µF 63 V box film on a 5 mm pitch that fits 7.2 × 7.2 × 13.5 will do — which matters, because DigiKey now lists this exact WIMA part as obsolete with its seven substitutes all at zero |
| **Reset current limiter R26** | 1 + spare | **Vishay PR01 1 kohm 1 W axial, DIN0207** | **price and stock not read** | [element14 India — Vishay PR01 series](https://in.element14.com/c/passive-components/resistors-fixed-value/through-hole-resistors?st=PR01) · [Vishay datasheet](https://www.vishay.com/docs/28729/pr010203.pdf) | 🟠 | R25 is a 10 kohm 0204 resistor; the old R24 is removed. The footprint is a **DIN0207 body standing upright**, 6.3 × 2.5 mm, so buy it by series rather than by wattage |
| **Connectors** | 1 set + spares | **2 × JST-XH vertical headers** — 4-pin and 2-pin — plus three solder-through wire pads | 2-pin **₹2.13**, 4-pin **₹4.07** (Sunrom, minimum 50 and 10) · 4-pin **₹20**, "In stock" (Probots) | [Sunrom — 2-pin top entry](https://www.sunrom.com/p/2-pin-jst-xh-25mm-top-entry-header) · [4-pin top entry](https://www.sunrom.com/p/4-pin-jst-xh-25mm-top-entry-header) · [housings](https://www.sunrom.com/p/2-pin-jst-xh-25mm-housing) · [crimp pins](https://www.sunrom.com/p/crimping-pins-for-jst-xh-25mm) · [Probots — 4-pin, in stock](https://probots.co.in/4-pin-jst-xh-2-5mm-top-entry-header-straight.html) | 🟢 | Both holds with the button sense, and the button itself. The wire pads take two 14 AWG and one 22 AWG soldered straight through. **It was three headers** until the shunt's sense plug J1 went with the current measurement on 2026-09-16. Sunrom states the true 2.5 mm pitch; Probots' page says 2.5 in its title and 2.54 in its table |
| **Mounting** | 4 screws, 4 spacers | **4 × M3 × 20 self-tapping** and **4 × Ø6 × 8 mm unthreaded spacers**, on the bought board's screws | **not found at either size**; nearest M3 × 12 **₹40** per 10, "Only a few left in stock", and a 5 mm spacer **₹4** per 10, "168 in stock" | [ThinkRobotics — self-tapping screws, to M3 × 12](https://thinkrobotics.com/products/self-tapping-screws) · [RPI Shop — M3 × 10](https://rpishop.in/products/self-tapping-screw) · [EkaStore — M3 × 5 nylon unthreaded spacer](https://ekastore.in/product/m3-x-5mm-nylon-spacer-female-non-threaded-plastic/) | 🟠 | **Neither length is on a hobby shop's shelf**, which is not the same as not stocked in India — both are ordinary sizes from a fastener supplier, and section 10 already says to treat the whole M3 order as one enquiry to one rather than as four hobby-shop baskets. A screw has to reach through 1.6 mm of this board, 8 mm of spacer, 1.6 mm of the bought board and a 3 mm standoff before it bites, so ×12 is 8 mm too short. The spacer sets the height: **10 mm was tried and rejected** — it leaves 5.4 mm under the pack connectors where an upright resistor is 5.5. All four screws drive from above |
| **On/off button** | 1 + 1 spare | **Daier GQ-12B/S 12 mm stainless anti-vandal momentary, M12 × 1 bushing**, screw terminal | **₹190** + GST, "100 in stock", Mumbai (Evelta) | [Evelta — 12 mm metal push button, momentary](https://evelta.com/12mm-metal-push-button-switch-momentary/) | 🟠 | **It takes the rear-wall station the loop key used to have**, and it is the reason that key is off this bill. It switches microamps: it pulls the MOSFET gates down through a diode and carries no bus current, so any contact rating will do. **12 mm and not 16 because of the depth behind the wall** — the maker's drawing gives 21 mm from its dome to the tip of its terminal, and the CAD reserves 16 mm behind the wall's inner face against 21.4 mm of clear air. **Measure one before printing the pelvis**: no listing states a behind-panel length, so that 21 mm is the only dimensioned figure anybody publishes. The pin-terminal GQ-12BJ is 19.8 mm overall and shallower still, and was sold out |

**What cannot be bought in India, and what that means.** **Nothing that has been
checked properly, as of 2026-09-22.** This paragraph used to name five parts and
argue about which substitutions were survivable, and all five of those arguments
are now void. They
are worth recording because the mistake behind them is easy to repeat.

**The MOSFETs came off the list by being redesigned around.** The Vishay part went
obsolete, and rather than hunt another specialist device the switch was widened:
four IRF4905 at 20 mΩ carry 6 A each where two at 6.7 mΩ carried 12, which is
1.26 W a device against 1.58 and a continuous rating that went up rather than
down. What it cost is two more devices and the last of the board's free area —
`electrical/power_pcb.py` places 54 parts on the 50 × 50 and there is no room for
another.

**The other four came off the list by being looked for properly.** The BAT46, the
Keystone 3568 holder, the BZX79-C15 and the RXEF185 were all called missing on the
strength of a survey of Robu, Robocraze, ElectronicsComp, Kitsguru and Probots.
Those are hobby shops. **element14 India, Mouser India, RS India and TME India are
domestic distributors serving the same global catalogue**, and every one of the
four is on element14 India's shelf with an order code. So the 1N4148 substitute
for the BAT46 and the fatter-bodied 1N4744A for the zener are both fallbacks
nobody needs, and the fuse holder no longer threatens a board revision.

**The four-terminal shunt was a fifth such line and is simply gone**: the current
measurement was deleted on 2026-09-16, so the most expensive, least available part
this bill ever carried is not bought at all.

**The one genuine import on this whole bill is not on this board.** It is the
Matek BEC12S-PRO in section 1a, which three Indian sellers between them could
offer only as a pre-order on 2026-09-22.

**Three lines here are still unconfirmed rather than known good**, and they are
the ones nobody has yet put an order code against: the 14.7 kΩ 1 %, the WIMA film
capacitor C7 and the PR01 1 W resistor R26. All three are ordinary catalogue
parts, and the four lines above them show where such things actually live, so the
expectation is that they are domestic too — but **expectation is not a checked
listing** and these rows say so on their own faces.

**The body size is the thing to get right, and it is an ordering decision rather
than a sourcing one.** Twenty-three resistors stand upright on a 2.54 mm pitch on
a board where `legalize()` can find five legal positions for a twenty-fourth. The
layout is drawn around an **0204 body, 3.6 × 1.6 mm**; the ordinary quarter-watt
part sold in Indian hobby shops is the **0207 at 6.3 × 2.5**, which is nine tenths
of a millimetre fatter apiece on a board with none to give. So buy the resistors
as a named series from a catalogue distributor — Vishay's MBA0204 — and not as
"1/4 W metal film" from a shop that does not publish a dimension. The same rule
settles the two tantalums, which want Ø6.0 and Ø5.0 on a 2.5 mm pitch.

So the realistic order is **one domestic order for this whole board**, with only
the section 1a logic converter needing to come from anywhere else.

### 1c. Mechanical

| Subsystem | Qty | Current part / specification | Indicative price | Purchase / source link | Risk | Notes |
|---|---:|---|---:|:--|:--:|---|
| Actuator | 6 | **DAMIAO DM-J3507-2EC, 24 V** | Foxtech **US$89–95** reference | [Foxtech](https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/) | 🔴 | Buy two first, four after validation. Adapter board not included. Read each motor's termination switch; manuals disagree on its default |
| **Drive wheels** | 2 + 2 spare | **80×24 mm inline-skate wheel, ~85A cast PU, bearings removed** | **₹1,026** for the 4-pack, checked 2026-09-14, **80 mm in stock** | [Cosco — inline skate wheels, 80 mm](https://store.cosco.in/products/skating-inline-skate-wheels) · Decathlon/Oxelo 80 mm 84A 4-pack | 🟠 | Discard the 608 bearings. Measure the bought wheel before printing the adapter. Only 80 mm was in stock on 2026-09-14 |
| Support bearings | 4 + 2 spare | **6800-2RS — 10×19×5 mm** | **₹990** listed 2026-09-14, in stock — local bearing-shop pricing is preferred and much lower | [IndustryBuying — 6800-2RS reference](https://www.industrybuying.com/special-bearing-monotaro-BEA.SPE.238091927) | 🟢 | Hip pitch and knee; the wheel joint needs none. Prefer SKF, NTN, Koyo or NSK locally |
| Retaining compound | 1 | **Loctite 638**, 50 ml or equivalent | **₹677** checked | [Amazon.in — Loctite 638 50 ml](https://www.amazon.in/Loctite-638-Strength-Retaining-Compound/dp/B0074NAX8A) | 🟢 | Bonds bearings into printed cheeks. Test polymer compatibility and retention on a coupon first |
| Printed structural parts | 1 robot set | **SLS PA12**, laser-sintered, geometry per CAD | Offsite fabrication | **Offsite fabrication — no purchase link required** | 🟠 | Nine prints, SLS since 2026-09-13, so no orientation spec. Ask the bureau its part density; the roll-up assumes 0.93 g/cm³ |
| PETG fit mock-ups | As needed | PETG, 1.75 mm equivalent | Offsite fabrication | **Offsite fabrication — no purchase link required** | 🟢 | Fit mock-ups only; not structural |
| M3 fasteners | 78 installed + spares | **M3 SHCS in ×6, ×8, ×12, ×14 and self-tappers in ×8, ×10, ×20**, plus 1 mm and 2 mm washers | ~₹500–1,000 total class | [Robu — M3 × 6 set](https://robu.in/product/easymech-set-m3-x-6mm-socket-head-cap-allen-bolt-nut-12-pcs/) · [QuartzComponents — M3 × 8](https://quartzcomponents.com/products/m3-x-8mm-hex-allen-socket-head-screwpack-of-10) · [Robu — M3 × 10 set](https://robu.in/product/easymech-set-m3-x-10mm-socket-head-cap-allen-bolt-nut-12-pcs/) · [Indian Hobby Center — M3 × 12](https://www.indianhobbycenter.com/products/m3x12mm-hex-allen-socket-head-ss202-screw-dia-3mm-length-12mm) | 🟢 | **Section 10 counts every one and says where it goes.** 12.9 grade where it is a joint screw. Hobby shops carry neither M3 × 14 nor × 20 and none of them 12.9 — both are stock DIN 912 sizes from a fastener supplier, so treat the whole M3 order as one enquiry to one |
| **M5 wheel clamp set** | 2 + spares | **M5 × 12 SHCS**, **Ø30 × 2 penny washer** (Ø5.5 bore), **M5 heat-set insert Ø6.4 × 9.5** | **₹78** screw set · **₹159** inserts, checked | [Robu — EasyMech M5 × 12 cheese-head set](https://robu.in/product/easymech-m5-x-12mm-chhd-bolt-nut-and-washer-set-25pcs/) · [Robu — M5 × 8 heat-set insert](https://robu.in/product/m5-x-8-mm-brass-heat-set-threaded-round-insert-nut-25-pcs/) | 🟢 | Drives the wheel by clamping. Stocked inserts are 8 mm, not 9.5; Ø30 penny washers come from hardware shops |
| **M2.5 fasteners** | 8 screws + 4 standoffs, spares of both | **M2.5 × 6 SHCS**, and **M2.5 × 10 female-female hex standoffs**, 5 mm across the flats | **₹39** per 10 screws · **₹110** per 4 standoffs, both checked 2026-09-14, in stock | [Indian Hobby Center — M2.5 × 6 SHCS, 10 pcs](https://www.indianhobbycenter.com/products/m2-5x6mm-hex-allen-socket-head-ss304-screw-dia-2-5mm-length-6mm-pack-of-10) · [ThinkRobotics — M2.5 hex standoff, pick the 10 mm](https://thinkrobotics.com/products/aluminum-hex-standoff-pack-of-10) | 🟢 | The Banana Pi's mount, the only M2.5 on the robot. **Its holes are 2.75 mm; 8 mm is too short** |
| Threadlocker | 1 | **Loctite 243**, medium strength | **₹628** checked | [Amazon.in — Loctite 243 50 ml](https://www.amazon.in/Medium-strength-Threadlocker-Thixotropic-temperature-performance/dp/B014MMG3AM) | 🟢 | For metal threaded interfaces |
| **Board standoffs** | 10 + spares | **M3 brass, 6 mm A/F × 3 mm** — four under the distribution board, six under the controller carrier | **₹14** per 4 (6 mm, QuartzComponents) checked 2026-09-14, in stock | [QuartzComponents — M3 × 6 brass pillar](https://quartzcomponents.com/products/m3-x-6mm-female-to-female-nickel-plated-brass-hex-threaded-pillar-standoff-spacer) · [Robu — M3 × 5 pillar, 24 pcs](https://robu.in/product/m3-x-5mm-male-female-brass-hex-threaded-pillar-standoff-spacer-24-pcs/) — page refuses automated reads | 🟢 | **Drawn at 3 mm; nobody stocks under 5.** Accept the boards standing higher or cut spacers, and check the lid |
| **Battery strap** | 2 | Hook-and-loop cinch strap, ~15 × 250 mm | ~₹150-class | **Local hardware — no fixed SKU** | 🟢 | Backup for when the deck is off; threads through the battery rails' slots under the packs |

## 2. Source-early shortlist

### A. DAMIAO DM-J3507-2EC actuators — highest priority

**Recommended action:** source **two 24 V units now**, characterize them, and order the remaining four once actuator/knee validation is complete.

- Product: [Foxtech DM-J3507-2EC](https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/)
- Reference price: **US$89–95** before shipping/import charges.
- Listing includes one 8-pin power/CAN cable and one 3-pin tuning cable per motor.
- Ask for at least **two additional 8-pin power/CAN pigtails** with the order. Foxtech list no spare motor pigtail of their own, so this is a request on the order rather than a second line item.
- Add **one, and preferably two, adapter boards** from [Foxtech's DAMIAO cable set](https://store.foxtech.com/damiao-joint-motor-cables/) at US$2.30 each — the **Version** dropdown entry reading exactly `SH1.0 3Pin + 8Pin to XT30 + GH1.25 Adapter Cable`, and not the `XT30 (2+2) to GH1.25 + XT30 Adapter Cable` beside it. The motor does not come with one and the tuning assistant cannot be reached without it.

Six rather than eight, and that is worth stating plainly: nothing about the motor changed. The ankle actuator became the wheel actuator in place, and deleting hip roll took the other two.

### B. Exact DAMIAO connector ecosystem

The motor-side connector is small enough that spare harnesses are disproportionately valuable. The pinout figures show power/CAN on the **8-pin** connector (3 × VCC, 3 × GND, CAN_L, CAN_H) and the debug UART on the **3-pin** connector.

Avoid repeatedly disconnecting the miniature motor-side connector during prototyping; use the larger harness-side connection whenever practical.

Everything on the motor side of that ecosystem that can actually be bought is one Foxtech product, [DAMIAO Joint Motor Cables](https://store.foxtech.com/damiao-joint-motor-cables/) — a single page with a thirteen-entry **Version** dropdown at US$0.60–3.60. **Exactly two of those thirteen are on this bill**, and they are not the two anybody would guess. The whole list is set out below so that nobody has to guess from a name, because several of them are near-misses and two are called adapters:

| Foxtech option, verbatim | What it actually is | On this bill? |
|---|---|---|
| XT30 (2+2) Dual-end Cable (200mm) | XT30 2+2 on both ends | No — the XT30 branch line is bought locally at ₹41/pair |
| 4Pin to Dupont Head Download Cable | debug lead for DAMIAO's **4-pin** motors | No — the J3507's debug port is 3-pin |
| GH1.25-4Pin Reverse Cable (200mm) | GH1.25 signal lead | No |
| GH1.25-2Pin Reverse Cable (300mm) | GH1.25 signal lead | No |
| XT30 Dual-end Cable (200mm) | plain XT30 both ends | No — bought locally |
| **XT30 (2+2) to GH1.25 + XT30 Adapter Cable** | a PCB, but a **power splitter** with no SH1.0 on it | **No, and this is the one to avoid** — it is the wrong adapter and its name is one word from the right one |
| XT30 (2+2) Single-end Cable (100mm) | XT30 2+2 pigtail | No — bought locally |
| GH1.25-4Pin Reverse Cable (100mm) | GH1.25 signal lead | No |
| **GH1.25-3Pin Reverse Cable (300mm)** | the **debug serial lead** from the adapter board out to the USB tool, which is what page 9 of the V1.1 manual calls for. US$0.90, SKU 2510319, in stock | **YES — the *debug serial lead to the PC* line, 1 + 1 spare.** Not to be confused with the motor's own SH1.0 3-pin debug cable, which sits on the far side of the adapter board and comes with the motor |
| GH1.25-2Pin Same-side Cable (300mm) | GH1.25 signal lead | No |
| Type-C Data Cable (USB-A to USB-C, 2.0) | ordinary USB lead | No |
| **SH1.0 3Pin + 8Pin to XT30 + GH1.25 Adapter Cable** | the **adapter board** — a small black PCB carrying an XT30, a GH1.25 and both SH1.0 sockets. US$2.30, SKU 2510307, in stock | **YES — the *DAMIAO adapter board* line, 1 + 1 spare** |
| SHR-8Pin | US$2.00, and **the listing has no photograph of it**; *SHR* is JST's own designation for an SH-series 8-way receptacle housing, so this is very probably a bare crimp shell rather than a made-up lead | No — **and it is not the 8-pin pigtail**, though it is the only entry whose name mentions eight pins |

So the two SH1.0 motor leads — which are no longer rows on this bill, because they come with the motors — are served by **none** of these. Neither an 8-pin power/CAN harness nor a 3-pin debug cable is sold on this page, and a sweep on 2026-09-13 of AIFITLAB's 750-product catalogue, OpenELAB's DAMIAO collection and Seeed's DAMIAO pages found them nowhere else either. That settles the spares question for good: they arrive with motors, six motors bring six of each, and extras are a request on the order rather than a line in a basket.

**AIFITLAB do sell the bundles DAMIAO's packing list describes**, which Foxtech do not: their [DM-J3507-2EC listing](https://aifitlab.com/products/damiao-dm-j3507-2ec-motor) carries an *Accessory Kit — Include Adapter* option at +US$5, and USB-to-CAN or USB-to-CANFD as a second option. It is not the cheaper route — their 24 V base price is **US$120** against Foxtech's US$89, so six motors there cost about US$180 more than six from Foxtech plus a US$2.30 adapter. Worth knowing as the fallback if Foxtech's adapter option goes out of stock, not as the plan.

### C. Current joint support hardware

The joint stack is frozen enough to buy:

- 4 + 2 spare **6800-2RS, 10 × 19 × 5 mm** bearings.
- **Journals, 4 + spares, three bought pieces each:** M5 x 12 ISO 7380 button-head screw (10.9 or A2-70), M5 DIN 433 small-series washer (5.3 x 9 x 1 mm), and M5 ISO 4035 thin nut. The sleeve is still the separately printed 10 x 5.3 x 6 mm tube. See section C for the revised stack.
- **The revised journal screw is M5 x 12.** The existing [Robu EasyMech M5 x 12 listing](https://robu.in/product/easymech-ht-socket-button-head-cap-allen-bolt-m5-x-12-25-pcs/) specifies this size; stock was not rechecked. The earlier M5 x 10 shopping links are superseded. Source the small-series washer and thin nut by their standards, not as an ordinary M5 washer/nut set.
- 🟠 **The thin nut is a trade-channel part in India, not a shelf one.** Amazon and Flipkart carry M5 in DIN 934 standard (4.0 mm thick) and nyloc (taller still); **neither fits the 3.3 mm pocket**, and a nut that does not fit the pocket cannot be got at once the disc is on the motor. ISO 4035 / DIN 439 at 2.7 mm is stocked by fastener houses — [IndiaMART — M5 SS hexagon thin nuts, about ₹3/piece, Mumbai](https://www.indiamart.com/proddetail/5mm-ss-hexagon-thin-nuts-19128384988.html), [Greatbolt, ISO 4035 hexagon thin nuts, Vadodara](https://www.indiamart.com/proddetail/iso-4035-2012-hexagon-thin-nuts-chamfered-style-0-product-grades-a-and-b-2857430135833.html), or the [category listing](https://dir.indiamart.com/impcat/hexagon-thin-nuts.html) — so it belongs in the same enquiry as the M3 × 14 that is already off the shelves, in section 10. **If that enquiry is a nuisance, going to M4 removes it**: a standard DIN 934 M4 nut is 3.2 mm thick and drops into the pocket as drawn, on every shelf in the country, and the screw is not what limits this joint — the PA12 under it is, so M4 costs nothing that matters. Ask before changing it; it moves four dimensions and a gate row.
- 🟠 **The printed sleeve's fit is the open question on this joint.** Strength is not the worry: PA12 carries 25 MPa at the 650 N case against 48, better than the printed stub it replaces. Two other things are. SLS holds about ±0.2 mm where the 6800's bore is held to eight microns, so a printed sleeve has to be **dressed to size before it will enter a bearing at all** — print several, take them down until one slides in and back out without play. And it sits inside a clamped stack, where an M5 at a modest 1 kN puts ~18 MPa of sustained compression on it and PA12 creeps, which costs preload on an anchor that is already the weak thing here. **The steel version is the upgrade if either bites**: a Ø10 h6/g6 × Ø5.3 × 6 ground sleeve — a precision spacer, a hollow dowel or a drill bush — and nothing else about the joint changes.
- **Why the journal is bought at all**, having been a dowel until 2026-09-13 and then nothing: *neither of those can be assembled.* Both are one piece with the moving side before the joint is closed, and the clevis is a single print whose cheeks stand 45.2 mm apart against the 49.9 mm the motor and its disc measure to the journal's tip. The sleeve goes in **last**, from outside, through the boss's Ø17.5 shoulder bore and the bearing, and the screw pulls it onto the nut. 22.8 g of steel back on the robot. `docs/PLAN.md` decision 10 carries the arithmetic, and says plainly that the anchor in the printed disc is weaker than the stub was.
- **The nut goes in first and cannot go in later.** It drops into a hex pocket in the output disc's motor-side face, so it has to be in place before that disc is screwed to the actuator. Push it in; a dab of adhesive if the print comes out generous.
- No bearing carrier: the cheek is bored Ø19.2, a printed boss on its outer face carries the shoulder the bearing seats against, and the bearing is bonded into that. **Nothing in this section needs a machine shop** — the carrier was the last part that did, and everything here is a catalogue item or a print.

**Hip pitch and knee are straddled; the wheel joint is not.** It was hip pitch alone until 2026-09-13, when the knee was given the same clevis the hip uses — the same printed part, the same bonded bearing — because the knee carries the shin, the wheel motor, the adapter and the wheel on a plate 22 mm off its own axis, and nothing but the actuator's internal output bearing was taking that moment. **The wheel joint keeps its flat plate**: it carries the wheel alone on a 12 mm arm, which is a third of the knee's overhang and already inside what the flat limbs ask of the same bearing, and there is nowhere to put a second support that does not mean a fork round a Ø80 wheel. So the count of support bearings went from two to four, which is 10 g of steel — it would have been 19.8 with the dowels, and those went a day later.

**What it cost besides the steel.** 9.6 g of PA12 a thigh, and the two leg segments stopped being the same print — see section 13. And the knee's fold: a saddle reaching round the motor stands in the plane the shin sweeps, the two touch at 103.0°, and the commissioning stop is 100° rather than the 110° carried over from the walking robot. The robot's deepest squat is 14.5 mm shallower for it.

### D. The wheel, and the one dimension that has to be right

Buy a four-pack of 80 × 24 mm skate wheels early and cheaply, because the adapter cannot be finalised without one in hand. Two dimensions are standardised by the 608 bearing and can be trusted: the **Ø22 bearing seats, 24 mm apart**. Two are not: the **Ø45 hub outside diameter** and the **20 mm crown radius**, both of which are representative figures in `cad/wheeled_parameters.py` waiting on calipers.

The adapter's Ø22 spigot is the fit-critical feature. Measure a real wheel's bore before committing a print.

## 3. Components that should not constrain the CAD

These are readily sourced enough in India that the design should select them on engineering merit while staying in common families:

- M3 fasteners
- 6800-series bearings
- silicone wire
- XT30 / XT60 connectors
- STM32 MCUs / compact development boards
- Pi Zero form-factor single-board computers
- CAN transceivers
- buck regulators
- fuses
- inline-skate wheels

Avoid saving a few grams by specifying a rare bearing or fastener that creates an import dependency.

## 4. Development-only equipment

Printed-part production equipment is intentionally omitted because fabrication is handled offsite.

| Item | Qty | Current requirement | Purchase / source link | Priority | Notes |
|---|---:|---|---|---|---|
| Bench DC supply / source | 1 | 24 V-class source sized deliberately for robot testing, with regeneration handled | **WAIT — source architecture must be selected with regen handling** | **Critical** | Six actuators peak near 24 A, estimated and unmeasured. A 10 A supply commissions but cannot run the robot. |
| USB-CAN-FD adapter | 1 | Waveshare **USB-CAN-FD-B** — the variant with Linux drivers | [Robocraze — Waveshare USB-CAN-FD-B](https://robocraze.com/products/waveshare-industrial-can-can-fd-bus-data-analyzer) | High | Commission motors independently of final firmware. ₹12,975 checked; the Windows-only plain USB-CAN-FD is ₹9,150 at [ThinkRobotics](https://thinkrobotics.com/products/industrial-grade-can-can-fd-bus-data-analyzer). |
| **SWD debug probe** | 1 + 1 spare | **ST-LINK/V2**, or a clone of it, onto the core board's SWD pins | [Robocraze — ST-Link V2](https://robocraze.com/products/st-link-v2/1000) · [Robu — ST-Link V2](https://robu.in/product/st-link-v2-programmer-for-stm8-and-stm32/), whose page refuses automated reads | **Critical** | **SWD, not JTAG** — PA15 and PB4 are JTAG pins out of reset. The only way into a lidded board. |
| Digital caliper | 1 | 0.01 mm display class | [Indian Hobby Center — INGCO HDCD28150, 150 mm](https://www.indianhobbycenter.com/products/ingco-hdcd28150-digital-vernier-caliper-150mm-6-inches) | High | Measure everything with no vendor drawing behind it before the pelvis prints. A wrong figure is a 183 g reprint. |
| Torque test arm | 1 | Printed/metal lever of accurately measured radius | **Custom / local fabrication** | High | Combine with known masses for torque calibration. Still outstanding, and the wheeled robot's torque envelope has not been re-derived. |
| Luggage/load scale | 1 | ~0–20/50 kg range | [Slovic — 50 kg digital luggage scale](https://slovic.com/products/slovic-50kg-digital-luggage-scale-with-lcd-indicator-black-silver-travel-friendly) | Medium | **₹381 checked 2026-09-14, in stock.** Calibrate against known masses. The quickest way to settle the soft 60 g wheel estimate. |
| IR thermometer / thermocouples | 1+ | Temperature measurement for actuator and joint tests | [QuartzComponents — Fluke 59 Mini](https://quartzcomponents.com/products/fluke-59-mini-infrared-thermometer-18c-to-275c) · [Fluke 59 MAX](https://quartzcomponents.com/products/fluke-59-max-infrared-thermometer-30-c-to-350-c-with-1-year-warranty) | High | ₹3,610 and ₹5,496 checked. Prefer thermocouples when logged data matters; a driven wheel motor is a new thermal duty cycle. |
| Logic analyser | 1 | 8-channel USB logic analyser class | [Indian Hobby Center — 24 MHz 8-channel analyser](https://www.indianhobbycenter.com/products/usb-logic-analyze-24m-8ch-mcu-arm-fpga-dsp-debug-tool) | Medium | ₹599 checked; Robokits were showing pre-order on 2026-09-13. For MCU-side SPI/UART timing; use a scope for CAN. |

## 5. Provisional cost envelope

These figures are intentionally broad because actuator shipping/import treatment dominates uncertainty and printed-part fabrication will be quoted separately.

| Area | Rough provisional cost |
|---|---:|
| 6 × DM-J3507-2EC at Foxtech list price | **US$534–570 before shipping/import charges** |
| Offsite printed structure | **₹13k–16k a set**, at iamRapid's published ₹32–40 per cm³ over the 406 cm³ the robot's printed parts really are. **Not a quote** — see section 12, including why a bureau that prices by bounding box will say something far larger |
| Wheels and wheel clamp hardware | **~₹1k–2k** |
| Bearings and fasteners | **~₹2k–4k** |
| MCU, SBC, CAN and IMU | **~₹8k–14k** |
| USB-CAN-FD development interface | **₹13k** checked, for the Linux-capable -B |
| Battery, charger, safety gear and pack harness | **~₹8k–11k** — two packs, an IMAX B6AC, the two XT60 panel mounts, the BMS, balance leads and the series harness |
| Bulk capacitor bank and regen handling | **~₹2k–4k**, excluding the bench source — and **almost none of that is the capacitors**, which are ~₹30 for the two cans. The clamp and the brake resistor are what carry this figure |
| Wiring, connectors, DC/DC, fuse/power hardware | **~₹4k–10k** |

A sensible planning figure for the finished V0 robot and core development electronics is roughly **₹0.9–1.2 lakh before uncertain actuator import/shipping costs and offsite-printing charges**, assuming the motors are acquired near international list price rather than high domestic reseller pricing. Two fewer actuators is the whole of the saving against the walking robot; the rest roughly cancels, because the SBC arrived as the foot sensors left. This is not a procurement quote.

## 6. Immediate procurement recommendation

Buy now / very soon:

1. **2 × DAMIAO DM-J3507-2EC 24 V**, plus 2 or more spare OEM 8-pin power/CAN pigtails asked for on the same order, plus **2 × adapter board** at US$2.30 from Foxtech's cable set page — the dropdown entry reading exactly `SH1.0 3Pin + 8Pin to XT30 + GH1.25 Adapter Cable`, which is section B's table row — and **2 × `GH1.25-3Pin Reverse Cable (300mm)`** at US$0.90 from the same page, the lead from that board out to the debug tool, which nothing else on this bill supplies. The board is not supplied with a bare motor, Foxtech offer no bundle that includes it, and without it the tuning assistant cannot be reached.
2. **1 × Waveshare USB-CAN-FD-B interface** — the -B, not the plain one, which has no Linux driver. ₹12,975 at Robocraze.
3. **2 × WeAct STM32G474CEU6 core boards, the compact one**, one fitted and one spare — **from WeAct's own AliExpress store, because both Indian listings are the Long Type and that board does not fit the carrier**. An import on a long string, so this is the line most likely to hold the electronics up.
4. **4 × MCP2562FD-E/P CAN-FD transceivers**, three fitted and one spare, through-hole, with DIP-8 sockets and decoupling capacitors, and **5 × the printed carrier board** from LionCircuits, which wants the Gerbers plotted out of KiCad first and nothing else done to them — every hole on the board is between 0.4 and 3.4 mm. **No termination resistors are needed on the carrier**: with two motors on each of the three buses, both ends of every bus are a motor, and all six of their switches stay ON.
5. **1–2 × compact BNO085 Nano breakouts**, plus the wire and JST-XH crimp kit that land them, the SBC's lead and the bus feed.
6. **1 × four-pack of 80 × 24 mm skate wheels** — cheap, and the adapter cannot be finalised without one to measure.
8. **Joint bearings and fasteners:** six 6800-2RS bearings (four fitted, two spare), and six sets of the journal screw, small-series washer and thin nut specified in section C. The screw is M5 x 12; the M5 x 10 listing is superseded.
8. **M3 SHCS**: 100 each of M3 × 6, ×8, ×12 and ×14, plus 1 mm and 2 mm M3 washers. The ×14 is not on an Indian shelf today and 12.9 is a fastener-supplier grade in these lengths, so treat the whole M3 order as one enquiry to a fastener supplier rather than four hobby-shop baskets.
9. **M5 clamp set**: 10 × M5 × 12 SHCS, 10 × Ø30 penny washers, 10 × M5 heat-set inserts. The penny washer comes from a hardware shop and the stocked insert is 8 mm rather than 9.5.
10. **Loctite 638** and **Loctite 243**.
11. **An IMAX B6AC** — before the first cell arrives, not after. It was in stock on 2026-09-13, having been showing pre-order earlier.
12. **1 × Daly 6S 24V 20A BMS** — out of stock at the vendor whose outline the pelvis is cut to, and the pelvis cannot be printed until one has been measured. It is a cheap part on a long string.

Buy with the first packs, and not before the pelvis is printed:

The battery hardware is cheap and none of it is a schedule blocker, but four of
its dimensions are cut into printed parts. **Measure a pack, the BMS board, an
XT60E-F and the on/off button before the pelvis goes to print**:
`cad/electronics.py` reserves 78 × 54 × 36 mm for the packs with a millimetre of
side clearance, and `cad/torso.py` cuts the rear wall to the XT60E-F's
18.70 × 11.50 body with its screws 25 mm apart, from AMASS's own dimensioned
drawing, and a Ø12.2 hole for the button's M12 bushing. **The button is the one
to measure first**, because it is the one whose behind-panel length nobody
publishes: the CAD reserves 16 mm behind the wall against 21.4 mm of clear air,
and the only figure on any drawing is the 21 mm from the switch's dome to the
tip of its terminal. **The XT60E-M went off this bill on 2026-09-16** with the
loop key, and so did the measuring it needed. **The connector figures on this
bill were listing figures until 2026-09-13 and the listing was wrong** — it gave
the XT90E-M a 25 × 16 cutout with 29 mm screw centres against a real 32.4, which
would have been a 182 g reprint rather than a 9 g one. Measure anyway.
Everything else in the battery list can be bought late.

Buy later / after validation:

- the Banana Pi, once the MCU is talking to a motor and the software stack is a real question.
- full XT30 branch-connector quantity after harness routing.
- M2.5 hardware, once a Banana Pi is in hand: the standoffs are 10 mm because the CAD says the SBC sits 10 mm over the carrier, and the board's own hole size is inherited rather than published.
- final DC/DC converter, fuse rating and regenerative-energy hardware after electrical measurements. **Motor power HAS a switching element since 2026-09-15** — the power switch board, which is the robot's on/off and its low-battery cutoff — so what waits on the measurement is the fuse's rating and the regeneration clamp, not whether the bus can be switched at all. **The shunt's value no longer waits on anything**: the current measurement was deleted on 2026-09-16, and the bus current is to be characterised once on a bench with a clamp meter rather than by a fitted Kelvin shunt.

## 7. Design-for-India sourcing rules

1. Prefer **standard metric bearings** readily stocked in India.
2. Prefer a **catalogue part ordered to size** over stock cut to size, and let the **fit class** choose between catalogues. This rule chose the journal twice — a g6 dowel pin rather than the stocked m6 one, because m6 is an interference fit in a bearing bore — and then the journal stopped being bought at all. Still no exotic shoulder bolts.
3. Prefer standard M3 fasteners and commonly stocked lengths.
4. Do not choose a rare component merely to save a few grams unless the benefit is quantified.
5. Maintain at least one domestic or broad-distribution alternative for commodity electronics.
6. Keep actuator-specific connectors/harnesses documented because these are disproportionately likely to cause delays.
7. Once a physical component is purchased, its **measured dimensions override catalogue assumptions** in the CAD.
8. Record supplier, order date, actual landed cost, measured mass and measured dimensions in this BOM as the project progresses.
9. Treat purchase links as sourcing aids, not immutable approved vendors.
10. Do not turn a design-dependent placeholder into a purchased part merely to make the BOM look complete.
11. Prefer a consumer part with a standardised interface over a bespoke one. The skate wheel is the clearest case on this table: tread roundness, hardness and the PU-to-core bond are already solved by someone else, and what the project supplies is the one printed adapter in between.

## 8. Engineering source references

- DAMIAO DM-J3507-2EC product / STEP source: [Foxtech](https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/)
- DAMIAO cables and the SH1.0-to-XT30+GH1.25 adapter board: [Foxtech — DAMIAO Joint Motor Cables](https://store.foxtech.com/damiao-joint-motor-cables/)
- **Manual revision V1.1**, 50 pages against the 15 of the V1.0 held in `reference/`, and the source for the debug chain's GH1.25 lead: [DM-J3507-2EC User Manual V1.1](https://cdn.shopify.com/s/files/1/0673/6848/5000/files/DM-J3507-2EC_Gear_Motor_User_Manual_V1.1.pdf), hosted by AIFITLAB. It keeps the packing list's pin-count transposition and **reverses the termination-resistor default**.
- Motor bundles that include the adapter board, which Foxtech do not offer: [AIFITLAB — DM-J3507-2EC](https://aifitlab.com/products/damiao-dm-j3507-2ec-motor)
- WeAct STM32G474 board geometry/reference: [WeActStudio GitHub](https://github.com/WeActStudio/WeActStudio.STM32G474CoreBoard) — the `Hardware/QFN48` STEP is what was measured for the 36.53 × 28.40 outline and the absence of mounting holes.
- Banana Pi BPI-M4 Zero outline and form-factor claim: [Banana Pi wiki](https://wiki.banana-pi.org/Banana_Pi_BPI-M4_Zero)
- Raspberry Pi Zero 2 W mechanical drawing RP-008358-DS, which is where the SBC's inherited hole pattern comes from: [Raspberry Pi documentation](https://datasheets.raspberrypi.com/rpizero2/raspberry-pi-zero-2-w-mechanical-drawing.pdf)
- Inline-skate wheel candidates checked 2026-08-31: [Cosco India inline wheel range](https://store.cosco.in/products/skating-inline-skate-wheels), and a Decathlon/Oxelo 80 mm 84A four-pack at ₹899 at the time of review.
- 608 bearing interface, 8 × 22 × 7 mm (ISO 15 / ABEC 608), which is what fixes the wheel's Ø22 seats and its 24 mm width.

## 9. Current joint hardware and printed parts

**Hip pitch is the only joint with far-side support.** Knee and wheel bolt the flat limb plate directly to the actuator's rear cover.

| Item | Installed qty | Current specification | Estimated mass | Purchase / source link | Notes |
|---|---:|---|---:|---|---|
| Support bearing | 4 | **6800-2RS, 10 × 19 × 5 mm** | 5.0 g ea | [IndustryBuying — 6800-2RS reference](https://www.industrybuying.com/special-bearing-monotaro-BEA.SPE.238091927) | Bonded into the cheek's Ø19.2 bore with Loctite 638. The Ø17.5 bore lands on the outer race only. Two spares. |
| Journal sleeve | 4 | **Printed, Ø10 × Ø5.3 × 6 PA12 tube** — `journal-sleeve` | 0.3 g ea | Printed with the rest; steel is the upgrade, see section C | What the bearing turns on, and the last thing fitted at each joint, from outside. A slip fit, never bonded. |
| Journal screw, washer and nut | 4 sets | **M5 x 12 ISO 7380 button head**, **M5 DIN 433 / ISO 7092 small-series washer, 5.3 x 9 x 1 mm**, **M5 ISO 4035 thin nut** | 3.6 g/set estimated | [M5 x 12 screw](https://robu.in/product/easymech-ht-socket-button-head-cap-allen-bolt-m5-x-12-25-pcs/) (existing BOM source; stock not rechecked). Washer and thin nut: local fastener supplier enquiry; [washer drawing](https://belmetric.com/content/A-PDF_Drawings/WF5X9SS.pdf) | Revised 2026-09-15: 2.3 mm nominal engagement and 1 mm tip clearance. Washer must be 9 mm OD; a regular M5 washer is too wide. Buy 6 sets including spares. Do not omit the washer. |
| Output screws | 36 | M3 × 6 SHCS provisional, pending first-actuator thread-depth measurement | ~2.8 g per six | [Robu — M3 × 6 set](https://robu.in/product/easymech-set-m3-x-6mm-socket-head-cap-allen-bolt-nut-12-pcs/) | Six joints, six screws each. Also buy M3 × 8 validation stock; see section 10. |
| Stator screws, knee + wheel | 16 | M3 × 14 SHCS + 1 mm washers | Included in fastener mass | **Not on a hobby shop's shelf, 2026-09-13** — a stock size from a fastener supplier | Through 6 mm limb plate + 3.2 mm rear cover into 4 mm thread. |
| Rear screws, hip pitch | 8 | M3 × 12 SHCS + 2 mm washers | Included in fastener mass | [Indian Hobby Center — M3 × 12](https://www.indianhobbycenter.com/products/m3x12mm-hex-allen-socket-head-ss202-screw-dia-3mm-length-12mm) | Through the pelvis clevis's 3 mm cheek + 3.2 mm rear cover into 4 mm thread. |
| Wheel clamp screw | 2 | **M5 × 12 SHCS** | ~2 g ea with washer and insert | [Robu — EasyMech M5 × 12 set](https://robu.in/product/easymech-m5-x-12mm-chhd-bolt-nut-and-washer-set-25pcs/) | One on each wheel axis. Section 10 says why 12 and not 20. |
| Wheel clamp washer | 2 | **Ø30 × 2 penny washer, Ø5.5 bore** | Included above | **Not stocked by any hobby supplier** — hardware shop; [QuartzComponents — plain M5 flat washer](https://quartzcomponents.com/products/m5-flat-ss-washer-pack-of-4) is what the shelves have, and it is too small | Deliberately oversized, so the preload lands on the wheel's hub face rather than on the end of a printed spigot. |
| Wheel clamp insert | 2 | **M5 heat-set, Ø6.4 × 9.5 nominal** | Included above | [Robu — M5 × 8 heat-set insert](https://robu.in/product/m5-x-8-mm-brass-heat-set-threaded-round-insert-nut-25-pcs/), 1.5 mm shorter than drawn | Seated flush with the spigot's outer end, in a bore drawn 14 mm deep for the 9.5 mm insert. |
| Board mount screws | 10 | **M3 × 8, self-tapping into printed PA12**, through 3 mm standoffs | Negligible | [QuartzComponents — M3 × 8](https://quartzcomponents.com/products/m3-x-8mm-hex-allen-socket-head-screwpack-of-10) | Four into the pelvis posts, six into the deck. **Piloted Ø2.5, self-tapped, not inserted**; `tools/gate_e.py` counts them. |
| Deck fixing screws | 4 | **M3 × 10, self-tapping** — down through the deck into the shell's wall ledges | Negligible | [Robu — M3 × 10 set](https://robu.in/product/easymech-set-m3-x-10mm-socket-head-cap-allen-bolt-nut-12-pcs/) | These four hold the whole upper stack; undo them and deck, controller, SBC and battery hold-down come out together. |
| Cover screws | 4 | **M3 × 10, self-tapping** — down through the lid into the four printed cover bosses | Negligible | [Robu — M3 × 10 set](https://robu.in/product/easymech-set-m3-x-10mm-socket-head-cap-allen-bolt-nut-12-pcs/) | **Length derived, not measured**: 4.8 mm of pass-through leaves about 5 mm of thread in a 12 mm boss. |
| **SBC standoffs** | 4 | **M2.5 × 10 female-female hex, 5 mm A/F** | Negligible | [ThinkRobotics — M2.5 hex standoff, pack of 4](<https://thinkrobotics.com/products/aluminum-hex-standoff-pack-of-10>) | On the carrier, on the Banana Pi's own 58 × 23 mm pattern. They replaced the printed posts on 2026-09-14. |
| SBC mount screws | 8 | **M2.5 × 6 SHCS** | Negligible | [Indian Hobby Center — M2.5 × 6, 10 pcs](<https://www.indianhobbycenter.com/products/m2-5x6mm-hex-allen-socket-head-ss304-screw-dia-2-5mm-length-6mm-pack-of-10>) | Four up through the carrier into the standoffs, four down through the Pi. **The underneath four go in first.** |
| Rear wall connector screws | 2 + spares | **M2 × 10 SHCS with nuts**, and 2 M2 flat washers — both for the charge socket's flange | Negligible, not price-checked | [Robu — EasyMech M2 × 10 SHCS with nuts](https://robu.in/product/easymech-set-m2-x-10mm-socket-head-cap-allen-bolt-nut-12-pcs/) | The only fasteners outside this robot, and the only M2. It was four until the disconnect went: the socket alone would take an M2.5, and keeps M2 because one thread on one wall is worth more than a quarter millimetre of bridge. |

Printed-part masses, **SLS PA12 at 0.93 g/cm³**, measured from the CAD by `uv run tools/mass.py`. Every figure here dropped about 12 per cent on 2026-09-13 for no change of shape at all, when the material moved off FDM PA12-CF — 54 g across the structure:

| Print | Each | Count | Total |
|---|---:|---:|---:|
| Thigh, 105 mm, unmirrored — right thigh | 41.6 g | 1 | 41.6 g |
| Thigh, 105 mm, mirrored — left thigh | 41.6 g | 1 | 41.6 g |
| Limb, 105 mm, unmirrored — left shin | 33.2 g | 1 | 33.2 g |
| Limb, 105 mm, mirrored — right shin | 33.2 g | 1 | 33.2 g |
| Wheel adapter — left and right | 12.7 g | 2 | 25.3 g |
| Pelvis shell — both hip clevises, the cover bosses, the bearing-seat bosses, two battery rails, four distribution-board posts, four deck ledges, four strap slots, two BMS card guides, the IMU seat and the rear wall's panel-mount cutouts | 161.1 g | 1 | 161.1 g |
| Torso cover | 46.8 g | 1 | 46.8 g |
| Electronics deck — plate, two BMS card guides and the cable chase | 26.1 g | 1 | 26.1 g |
| **Printed structure** | | | **411.6 g** |

**There are four distinct limb prints now, one of each.** Both leg segments are still 105 mm, and while both ended in a flat plate the right thigh and the left shin were literally the same solid, so two prints covered four limbs. Straddling the knee ends that: a thigh finishes in a clevis and a shin in a plate. Same number of parts on the robot, twice as many things to slice — and **the thigh is the one piece here with no golden STEP behind it except the electronics deck**, because it did not exist before 2026-09-13. `tools/gate_e.py` counts its thirteen features instead. There is no hip carrier and no foot tray: the first went with hip roll, the second with the ankle.

**A thigh also cannot be printed the way a shin can.** The shin is a flat plate that lies on the bed with every fibre running along the limb. The thigh's far cheek stands 48 mm across the joint from its plate, joined only by the saddle, so laid the same way it has a disc floating in the air. It has to stand on end or on its flank, and either puts layer lines across a section that had none. **That orientation has not been decided** and nothing in the gates can decide it. The **electronics deck** is the one part on this robot the pre-migration engine never built, so it is the piece `tools/gate_b.py` has nothing to compare against; the arithmetic behind it is `tools/gate_e.py`'s count of its twelve holes and its cable chase.

With the six actuators, the metal, the wheels, the fasteners, the electronics and a 60 g allowance for the power-entry block, the current model comes to **2 085.6 g against the 2 300 g ceiling**, leaving **214.4 g** of headroom.

**The battery cost about 450 g all in**, which is most of what deleting hip roll had bought back: 288 g of cells, 65 g of wiring and mounts, 13 g of distribution board, 66 g of extra pelvis and cover, and 26 g of deck — the last of those having shed 7 g since, as the bus monitor's posts and then the SBC's came off it. That is the trade in one line — the robot went from 700 g of margin to 240 in exchange for cutting the umbilical, and for not needing the boom that was supposed to carry it. **Giving everything in that torso a mount cost about a gram in the end, and for a fortnight it cost nine.** The connector panel was 8.6 g of that; deleting it and letting the rear wall carry panel-mount hardware directly gave all of it back, plus 0.4 g of wall where the old apertures were, against 0.5 g out of the deck for the cable chase. What is left on the bill is a 0.1 g IMU seat and 0.8 g of BMS card guides. **Cutting those guides to a chosen board then cost 0.9 g more**: a 33 mm card stood on the bay floor lifts clear of a 4 mm slot before the deck over it can stop it, so the guides rise 7 mm to hang the board 1.5 mm under the deck and the slot opens from a bare PCB to the board's whole 8.2 mm. **Supporting that card at the top as well cost 0.2 g more**, on the deck rather than the pelvis: two more guides on the plate's underside, cut to the same slot, so a card held at one end is held at both. **The BMS itself is a further 45 g**, which since 2026-09-13 is the vendor's catalogue figure rather than a class estimate, and 15 g heavier than the estimate was. Run `uv run tools/mass.py` for the live figure; the headroom is **214.4 g** as this is written.

**The margin is measured against a ceiling that belongs to a different machine.** The 2 300 g figure is a single-leg walking-robot calculation at 40° of sustained knee flexion. This robot always has both wheels on the ground, so the number is conservative here — but the wheeled torque envelope has never been re-derived, so nobody knows by how much. The eight-motor walking robot on `walking` is near 2 047 g. Use `uv run tools/mass.py` as the authoritative roll-up rather than this static table.

The softest figure in that roll-up is the **60 g wheel**, which is catalogue-typical for an 80 × 24 mm 85A skate wheel and has never been weighed; brand to brand the range is roughly 55–65 g, so the pair could move ±10 g either way. It is the **bare** wheel — the 608s come out for the direct drive, so a vendor figure quoted with bearings fitted is about 24 g per wheel too heavy.

## 10. Fastener schedule

Six joints, each with a rotor side and a stator side, fix the count and the nominal lengths.

### Where the screws go

| Joint | Rotor side — 6 × M3 on Ø24 output circle | Stator side — 4 × M3 on Ø41 rear pattern |
|---|---|---|
| Hip pitch ×2 | thigh output disc | pelvis hip clevis, rear cheek |
| Knee ×2 | shin output disc | thigh stator plate |
| Wheel ×2 | wheel adapter output disc | shin stator plate |

That is **36 rotor-side screws + 24 stator-side screws = 60 installed M3 SHCS**, down from 80 on the eight-joint robot.

### Lengths and engagement

| Where | Qty | Screw | Washer | Pass-through | Thread | Engagement | Purchase link |
|---|---:|---|---|---:|---:|---:|---|
| Output circle, all 6 rotor ends | 36 | **M3 × 6** provisional | none, counterbored | 2.8 mm | ~5 mm unverified | 3.2 mm | [Robu — M3 × 6 set](https://robu.in/product/easymech-set-m3-x-6mm-socket-head-cap-allen-bolt-nut-12-pcs/) |
| Stator plate, knee and wheel | 16 | **M3 × 14** | 1.0 mm | 9.2 mm | 4 mm | 3.8 mm | **hobby shops only, 2026-09-13**; a stock DIN 912 size from any fastener supplier |
| Pelvis clevis cheek, hip pitch | 8 | **M3 × 12** | 2.0 mm | 6.2 mm | 4 mm | 3.8 mm | [Indian Hobby Center — M3 × 12](https://www.indianhobbycenter.com/products/m3x12mm-hex-allen-socket-head-ss202-screw-dia-3mm-length-12mm) |
| Wheel axis | 2 | **M5 × 12** | Ø30 × 2.0 | 3.0 mm | 9.5 mm insert | 9.0 mm | [Robu — EasyMech M5 × 12 set](https://robu.in/product/easymech-m5-x-12mm-chhd-bolt-nut-and-washer-set-25pcs/) |

The output-thread depth still needs to be measured on the first physical actuator. If it is really 5 mm, M3 × 8 bottoms at approximately 5.2 mm while M3 × 6 gives only about 3.2 mm engagement. **Buy both M3 × 6 and M3 × 8 initially**, measure the motor, then standardise on whichever gives roughly 4 mm engagement without bottoming.

### Every fastener on the robot, counted

The table above is the four lengths whose engagement had to be worked out. This one
is everything, because "how many of these do I actually need" had never been
answerable from this document in one place, and the joint count is not the whole
robot: nearly one M3 in four holds a board, the deck or the lid rather than any joint.
Those eighteen are counted on the finished pelvis and deck by `tools/gate_e.py`,
which asserts twelve Ø2.5 pilots in the shell — four cover bosses, four board posts,
four deck ledges — and six more under the controller's standoffs in the deck.

| Fastener | Installed | Where they go |
|---|---:|---|
| **M3 × 6 SHCS, 12.9** | 36 | Six screws into each of the six output discs — hip pitch ×2, knee ×2, wheel ×2. Counterbored, no washer. **Either this or the M3 × 8 is installed, never both**: which one follows the measured thread depth |
| **M3 × 8, self-tapping** | 6 | Six into the deck under the controller carrier, each through a 3 mm standoff into a Ø2.5 pilot. **It was ten until 2026-09-15**: the four under the distribution board grew to ×20 when the power switch board went on top of it |
| **M3 × 10, self-tapping** | 8 | Four down through the electronics deck into the shell's wall ledges, four down through the lid into the cover bosses |
| **M3 × 20, self-tapping** | 4 | Four into the pelvis posts under the distribution board, each through the power switch board, a Ø6 × 8 spacer, the bought board and a 3 mm standoff. One screw carries both boards |
| **M3 × 12 SHCS, 12.9** | 8 | Four into each hip pitch stator, through the pelvis clevis cheek, on 2 mm washers |
| **M3 × 14 SHCS, 12.9** | 16 | Four into each knee and each wheel stator — four joints, so **eight per leg** |
| M3 washer, ~1 mm | 16 | One under every M3 × 14 |
| M3 washer, ~2 mm | 8 | One under every M3 × 12 |
| M3 brass standoff, 6 A/F × 3 | 10 | Four under the distribution board, six under the controller carrier |
| Ø6 × 8 unthreaded spacer | 4 | Between the distribution board and the power switch board, on the same four screws |
| **M5 × 12 SHCS** | 2 | One per wheel axis |
| Ø30 × 2 penny washer | 2 | One under each wheel screw's head |
| **M5 heat-set insert, Ø6.4 × 9.5** | 2 | One in each wheel adapter's spigot |
| **M2.5 × 6 SHCS** | 8 | Four up through the controller carrier into the SBC's four standoffs, and four down through the Banana Pi into their tops |
| **M2.5 × 10 hex standoff, 5 A/F** | 4 | One at each of the Banana Pi's four holes, standing on the controller carrier. **The four M2.5 heat-set inserts are off the bill**: they went into the deck's SBC posts, and those posts are gone |
| **M2 × 10 SHCS, nut and washer** | 4 screws, 8 nuts, 2 washers | Two on the charge socket's flange, which are the only fasteners on the outside of this robot; and two up through the controller carrier under the bus monitor, each with two nuts under the board as its standoff and one on top. **It was six screws until 2026-09-16**: the disconnect's two ears went with the disconnect, and the button that replaced it clamps the wall with its own nut |

That totals **78 M3 screws**, which is the number the mechanical table carries: 60 in
the six joints and 18 more holding the boards, the deck and the lid. Beside them go
2 M5, 8 M2.5 and 4 M2 with 8 M2 nuts, 24 M3 washers, 10 M3 standoffs under the two
bought-and-printed board stacks, 4 unthreaded spacers between the distribution board
and the power switch board,
4 M2.5 standoffs under the SBC, and 2 heat-set inserts — both of those in the
wheel adapters, which since 2026-09-14 are the only printed parts on this robot with
brass in them.

### Why the wheel screw is 12 mm and not 20

This one was wrong and is worth recording rather than silently fixing. Earlier notes asked for **M5 × 20**, and modelling the screw showed it cannot work. Under the head sit the 2 mm washer and the 1 mm the spigot is deliberately held short of the hub's outer face, and then a **blind** bore: the reach below the head is 15 mm against the pocket as dimensioned and 17 mm against the pocket as actually cut. A 20 mm screw therefore lands on the bottom of the bore before the head ever reaches the washer, and the clamp never sees preload. Measured rather than reasoned: a Ø5 shank 20 mm under the head shares 58.9 mm³ with the printed adapter, which is 3 mm of screw buried in solid plastic.

**M5 × 12** is the standard length that fits both readings. It threads through 9 of the insert's 9.5 mm and stops 3 mm clear of the nominal bore bottom, 5 mm clear of the drawn one.

That clamp is not incidental hardware. **Torque reaches the wheel through the clamped face, not through the spigot**: an M5 at a modest 1 kN preload on the output disc's r11–r18 annulus is worth about 4 Nm of friction against the actuator's 3 Nm peak, where a press fit alone would have depended on how the printed spigot came off the bed.

### Purchase quantity

What the robot installs is the count table above. What to order is more than that,
and how much more depends on who is selling.

**As one enquiry to a fastener supplier**, which is what 12.9 in these lengths really
wants: 100 each of M3 × 6, M3 × 8, M3 × 12 and M3 × 14, and 25 each of M3 × 10 and
M3 × 20. Those
figures are generous against the installed counts on purpose — minimum order
quantities and a single lot of shipping dominate the price, so asking for 100 costs
little more than asking for 20.

**Bought by the pack**, which is how the hobby shops sell them and how they come from
a marketplace, one 50-piece pack of each of M3 × 6, × 8, × 10, × 12, × 14 and × 20
covers the whole robot with spares to lose: the most-used length installs 36 and the
least installs 4. Six packs, and no reason to double any of them except the pair below.

Either way: at least 50 each of approximately 1 mm and 2 mm M3 washer stack
thicknesses; 10 each of M5 × 12 SHCS, Ø30 penny washers and M5 heat-set inserts;
20 M2.5 × 6 and two packs of four M2.5 × 10 standoffs; 10 M2 × 10 with 20 nuts and
10 washers.
Measure actual washer thickness before relying on the engagement arithmetic.

**Buy both M3 × 6 and M3 × 8 whichever route you take.** Only one of the two ends up
on the robot, and which one is not known until an actuator has been measured.

### Mass, and a known discrepancy

The installed steel fastener schedule plus washers works out around **68 g of M3** for six joints — the ~90 g estimated for eight, pro-rated — plus about **6 g** for the two wheel clamps, so roughly **74 g** in total. `tools/mass_budget.toml` carries **51 g**, which is the older 60 g eight-joint allowance pro-rated to six plus the clamps, so the table is about **23 g light**. It does not threaten the 2.3 kg ceiling, but the allowance should be raised rather than left as an untracked discrepancy.

## 11. How everything in the torso is held

This section exists because of a question nobody had asked in one go: **is each thing
in this robot actually mounted, or is it only drawn where it should be?** A reserved
volume says where a board may sit and nothing about what stops it moving, and the
sweep in September 2026 found three items with no answer at all — the three external
connectors, the IMU, and the battery straps this bill already bought.

Every item is listed, including the ones held by nothing more than tape, because
"held by tape, deliberately, and here is which tape" is an answer and "not mentioned"
is not.

### What holds each thing

| Item | Held by | Needs buying |
|---|---|---|
| **Battery, 2 × 3S pack** | The electronics deck bearing on the 3 mm of squeeze its reservation leaves above the cells; two printed rails carry them from below. `tools/gate_f.py` measures both | — |
| Battery, belt and braces | Two cinch straps, threaded down through the front rail's slot, under the packs and up through the rear rail's | 2 straps |
| **Distribution board** | 4 × M3 × 20 self-tapping into four printed pelvis posts, through 3 mm brass standoffs, on the board's **own 45 mm datasheet square**. The screws are long because they carry the power switch board above it as well; they were M3 × 8 while this board stood alone | 4 screws, 4 standoffs |
| Capacitor bank | **Soldered into the power switch board** as C5 and C6, standing on the bus copper that feeds them, plus a cable tie round the two cans and a bead of flexible adhesive at each base. It was four reserved positions on the bought board until 2026-09-15; the bill has only ever bought two cans, and they now have footprints rather than a reservation | tie, adhesive |
| **Battery management system** | **A card in a cage.** Four printed guides, 46 mm apart and cut to one 9 mm slot that takes the board's whole 8.2 mm thickness: two off the cavity floor take its bottom edge 4 mm deep, two off the deck's underside take its top edge 2.5 mm deep, and the deck plate 1.5 mm over that edge is what stops it lifting out. **The guides hang it from the deck rather than standing it on the floor** — on the floor a 33 mm board lifts clear of its slot before the deck stops it. The deck goes on last and comes straight down, so its guides swallow the top edge as it lands, and if the board is not standing where it should the deck will not sit down | foam tape shim |
| **Power switch board** | **On the distribution board's own four screws.** An M3 × 20 self-tapping down through each corner, an 8 mm spacer and the bought board, into the printed post that already carries it. All four drive from above, which is the only direction this bay has. It covers the bought board exactly and stands 8 mm over it, passing 0.5 mm over that board's XT60 input socket — **measure a real one before ordering**. **It was a 54 × 32.5 board on two screws and a printed wall pad until 2026-09-15**; the pad is off the print | 4 screws, 4 spacers |
| **INA226 bus monitor** | **On the controller carrier**, at its outboard end: 2 × M2 × 10 up through the carrier, two nuts on each under the board as a 3.2 mm standoff, and a nut on top. The two holes are the outer pair of the four in the column on its right-hand edge. **The inner pair are its IN+/IN− shunt terminals and they now go nowhere** — the twisted sense pair and the shunt it ran to were deleted on 2026-09-16, so tie them to ground at J7 rather than leaving them floating. **It came off the pelvis on 2026-09-14**, where two printed pads on the rear wall held it, when the carrier grew to carry it and the BEC; the pads are gone from the print | 2 screws, 6 nuts |
| **Matek BEC** | **On the controller carrier**, between the SBC's two pairs of standoffs: flat on a 1 mm silicone sheet **component side up**, held by two 2.5 mm cable ties through four Ø3 holes, and dropped over four pins that stand out of the carrier under its own pad row. Bare laminate face down, because that is the only way the sheet takes its heat; the ties then cross its parts, the outboard one on the inductor's can, so keep them snug and not tight. Each tie's head goes under the carrier, 2.4 mm of the 3 mm its standoffs leave, and the four pins are soldered from under the carrier so nothing stands proud beneath the module. The module has no mounting holes and no published hole pattern, so the tie holes are drilled to its catalogue 35 × 24 mm and the pin row is scaled off Matek's photograph — **measure one before the board is ordered**. It is the one item in this torso that makes real heat, about 3 W, so check its temperature on the first sustained run | thermal sheet, 2 ties, 4 pins |
| **On/off button** | **Its own thread and nut**, clamping the wall on a Ø12.2 hole at x −44, z 22 — the antenna's way of mounting, and no screws at all. **It took the disconnect's station on the wall and not its position**: there is 11.2 mm of clear depth behind x 18 and 21.4 mm out at x −44, and a panel switch needs the second. Two signal wires drop from it through the deck's rear notch | the switch |
| **XT60E-F charge inlet** | The other way round: its flange lies **outside** the wall and its body passes through. 2 × **M2** × 10 with washers under the heads, which sit in the flange's own recesses, and nuts on the inside face | 2 screws, 2 washers, 2 nuts |
| **SMA antenna bulkhead** | Its own thread and nut, clamping the wall on a 6.5 mm hole at x −8, which it took to clear the charge socket's 34 mm flange. The u.FL pigtail behind it is a flying lead; tie it clear of the SBC's heatsink | tie mount |
| Pack leads and series harness | Nothing fixes these and nothing should: they are flying leads in the air above the distribution board. Restrain them with adhesive-backed tie mounts once the harness is made up | tie mounts |
| Balance leads, packs to BMS | **Taped flat to the tops of the packs.** This is the only route from the battery bay into the bay gap and it is 3 mm of air — the packs end at z 2 and the deck's underside is at z 5 — so the joined seven-way tail has to lie down, not stand proud, or the deck will not close on it | VHB tape |
| **Electronics deck** | 4 × M3 × 10 self-tapping down through the plate into four printed wall ledges. Undo these four and the deck, both upper boards, the battery's hold-down and the BMS's top guides come out together | 4 screws |
| **Controller carrier** | 6 × M3 × 8 into pilots in the deck, through 3 mm brass standoffs. Six and not four corners: the board is 140 mm long, its rear edge is full of connectors, and its rear outboard corner passes under the charge socket | 6 screws, 6 standoffs |
| WeAct STM32G474 core board | Its own two 2 × 12 headers into sockets on the carrier. **The board has no mounting holes at all** — the vendor STEP was measured and the largest hole in its outline is a 0.9 mm via — so the carrier under it is what gets screwed down | — |
| CAN transceivers, harness bank | DIP-8 sockets soldered to the controller carrier in a column of three, between the BEC and the SBC's right-hand standoffs, where the SBC leaves 10 mm of air over a socketed DIP's 7 mm. **Three are fitted**, one per bus, and **there is no position for the spare** on the 140 × 46 mm board, so it stays in its bag. The three bus connectors stand on the carrier's rear edge directly over the deck's cable chase | 3 sockets |
| **Banana Pi BPI-M4 Zero** | **On the controller carrier**, on four M2.5 × 10 hex standoffs: an M2.5 × 6 up through the carrier into each standoff's foot, and another down through the Pi into its top. **It stood on four Ø8 posts printed with the electronics deck until 2026-09-14**, with an M2.5 heat-set insert in each; the posts came up through the carrier in Ø8.6 mm holes, which cost that board two walls of bare laminate and asked the board house for a drill it does not own. The standoff is 10 mm because that is the air the Pi's underside microSD slot and the BEC's cable ties need between them | 8 screws, 4 standoffs |
| **BNO085 IMU** | Adhesive, in a printed three-rib seat on the shell floor that decides which way it faces. The ribs are the mount that matters: tape alone fixes the board but not its yaw | VHB tape |
| Actuator harnesses, CAN loom | Adhesive-backed tie mounts on the shell floor, along the back of the cavity where the two floor cable ports bring them up | tie mounts |
| **Torso cover** | 4 × M3 into the four printed cover bosses | 4 screws |

### Why there is no connector panel

**There was one, for a fortnight, and what it was for is worth keeping.** The three
connectors first fitted to the rear wall — an XT90-S, a 7-way JST-XH and an XT30 —
are constant-section prisms: no flange, no shoulder, no thread anywhere on them.
Each opening was the connector's body plus half a millimetre, which is a clearance
and not a fit, so all three were free to slide in or out, and mating an XT90 pushes
inward hard. **No cut in a 2.4 mm wall could ever have fixed that.** A hole smaller
than the body will not pass it, and a hole that passes it cannot stop it. A wall can
only *locate* such a connector; retaining one means bonding it, a bond wants area,
and area wants depth. So a 6 mm printed plate went behind the wall and the
connectors were epoxied into it.

**The hardware answered it better than the printed part did.** Every item in this
wall now retains itself — an eared XT60 bolted through by its own two ears, and two
threaded bushings each clamping the wall between a shoulder and a nut — so the plate
is deleted, the epoxy is off the bill, and there is no bonded joint anywhere on this
robot. It also takes the one cut that cannot be corrected after printing off a
cheap part and puts it back on the 183 g pelvis, which is why the measure-before-you-
print warnings below point at the pelvis again.

**All three sit above the electronics deck, at z = 22, and that is measured rather
than chosen.** Below the deck the rear wall is committed end to end: the deck's own
wall ledges stand *on* it between x 46 and 58, and the battery and the power bay fill
the rest of its height. (The bus monitor was bolted across its lower half until
2026-09-14 and came within 12.6 mm of it; it is on the controller carrier now, which
frees the wall below the deck but not the two ledges.) A bare prism can thread between those —
which is how an XT90-S and an XT30 fitted down there at all — but the GX16 bushing
that was here could not, because its nut wanted a clear circle 22 mm across. Above
the deck the same wall has 18 to 67 mm of clear depth and nothing standing on it.

| In the wall | Hole | Held by |
|---|---|---|
| **SMA antenna bulkhead**, x −8 | Ø6.5 | its own nut |
| **On/off button**, x −44 | Ø12.2 bushing hole | none — its own M12 nut clamps the wall |
| **XT60E-F charge inlet** (female), x 55.5 | 19.2 × 12.0 body cut | 2 × **M2** at 25 mm centres, nuts inside |

**There is only one connector in this wall now**, and the rule that no plug
meant for one port may fit the other is met by there being nothing to confuse it
with. While the disconnect was here it was met by gender: the loop key was a
bridged female that only fitted the disconnect and the charger's lead a male that
only fitted the inlet, so the key could not short the pack through the charge
port and the charger could not sit in series with the pack and put about 50 V
onto drivers rated for 30. **The inlet is still female for its own reason** — it
lands on the BMS's charge input, ahead of everything, so it is live at pack
voltage whenever cells are connected and the recessed half belongs on the
machine.

**The stations were solved, not laid out.** The charge inlet and the antenna
were swept across the whole wall against everything in the cavity, and the button
was swept the same way in September 2026 when it took the disconnect's place.
The inlet went as far outboard as its 34 mm flange still lands on the wall, and
the antenna sits inboard of it because nothing fits beyond that flange. **The
button was placed on depth rather than on width**: the wall was swept at the
station height for how far a round bushing can reach before it meets something,
and the answer is 11.2 mm behind the disconnect's old x 18, 18.6 mm over the SBC,
and 21.4 mm outboard of x −44 — so the button is at −44 and the CAD reserves
16 mm of it. The tightest figure on the wall is still **6.0 mm from the antenna
to the SBC**, fixed by that bushing's own depth. The thinnest wall is now the
charge socket's own 1.7 mm strip between its cutout and its screws, the
disconnect's 1.45 having gone with it. Move any station and `tools/gate_f.py`
re-measures every pair.

**The price is a chase through the electronics deck**, and it is an old debt rather
than a new cost. That plate has spanned the cavity wall to wall with no way through
it since it was drawn, while the actuator harnesses have always had to get from the
two floor cable ports up to the controller carrier above it — drawn at both ends and
nowhere in between. There is now a 34 × 6 mm notch in its rear edge, and the two
power leads off this wall share it.

**One finding from the panel era is worth carrying forward**, because it will catch
the next person who puts something in this wall: the disconnect and the balance port
once sat 1 mm apart, and with each opening cut 0.5 mm oversize that left *no material
at all* between their two sockets over a 6 mm run — **one millimetre between two
bodies is zero millimetres between two openings.** Nothing had ever measured it. The
same arithmetic applies wherever two holes are cut near each other.

### Consumables this section adds to the bill

| Item | Qty | For | Note |
|---|---|---|---|
| **Two-part epoxy**, 5–30 min | 1 tube | Nothing structural any more | It held the three connectors into the printed panel; that panel is gone and every part in the rear wall now holds itself. Keep a tube for odd jobs, but nothing on this robot depends on a bond |
| **Acrylic foam tape**, 1 mm × 12 mm | 1 roll | The fuse holder, the IMU, and a shim in each BMS card guide | The ordinary 3M VHB class. Degrease the printed surface — PA12 comes off a machine dusty. The guide slots are cut 9 mm for the BMS board's whole 8.2 mm thickness, and the 0.8 mm is what the shim takes up |
| **Adhesive tie mounts**, ~20 mm | ~10 | The actuator harnesses, the CAN loom and the pack leads **inside the pelvis** | With a tie through each. Inside the shell this is still how the looms are held: they are drawn as chases, not as a routed harness. **Do not use these on a limb** — see the row below |
| **Cable ties**, 2.5 mm | ~35 | The above, the capacitor bank, eight printed arches on the limbs, and two holding the BEC down to the controller carrier | Each limb carries two cable-tie arches on its inboard face, 4 mm proud with a 3.5 × 2.0 tunnel under each, sized for this tie. They are printed rather than stuck on because a limb swings through 110° and an adhesive pad on dusty PA12 is not what should hold a loom there |

### Charging, and what the BMS does and does not do

The BMS added in September 2026 — a **Daly 6S 24V 20A**, chosen on the 13th — is **on the cell taps only**. It balances the six
cells and monitors them; the bus still runs direct from the pack to the
distribution board, so the board never sees more than the charge current. That is
what lets it be small, and small is the only thing this torso has room for — the
cavity was swept for free volume and the largest box left anywhere in it is
38 × 64 × 12 mm.

**It is why there is no balance port in the rear wall any more.** That socket had
one job: presenting the seven cell taps to a bench charger so it could balance the
string. The BMS is permanently on those same seven nodes and balances on every
charge whether or not anybody plugs anything in, so the port duplicated a board
that is already inside — and a second path to an unfused pack is something to
insulate and keep clean rather than a convenience. **So the wall carries one connector and one
switch: the female XT60 that feeds the BMS's charge input, and the button that
turns the robot on.** What plugs into the charge inlet is
a plain 25.2 V constant-current/constant-voltage supply rather than a balance
charger, on a lead ending in a male XT60.

**The two packs are still joined into one 6S string inside the shell** — the same
splice, made in the same place, landing on the BMS's seven-way connector instead of
on a panel socket. Meter it before it ever sees a charger.

**It does not replace the main disconnect**, and it never sees the discharge
current at all. What it also does not give is an over-discharge cutoff: that is
the power switch board's job since 2026-09-15, and the two watch different
things. The BMS sees every cell and cannot act on the discharge path; the switch
acts on the discharge path and sees only the pack as a whole, cutting it off at
19.2 V. A single weak cell falls between them, which is what the cell alarm on
the balance tail is for. **AND NOTHING ISOLATES THE PACK ANY MORE.** The advice
here used to be to pull the loop key when the robot is parked, because a
transistor that fails shorted fails quietly; the key went on 2026-09-16 and what
is left is unplugging a pack from the series harness with the lid off. The
switch's own standing draw is not the reason to do it — the board has no DC path
from the pack at all when it is off — the reason is that a failed-short MOSFET
looks exactly like a working one.

**It is the precondition for charging in place**, which is what the barrel-jack
idea needs, but it is not sufficient on its own: the cells are soft-case pouches,
which are the wrong format to charge sealed inside a printed shell. The pack now
charges through one connector with the lid shut, which is exactly the convenience
that makes it tempting to walk away from — **don't, while the cells are pouches.**
Charge it where you can see it, and let charging unattended wait for a change of
cell format.

**Reaching the cell taps now means opening the lid.** A per-cell reading with a
meter or a cell alarm, or a proper storage charge on an IMAX, is a lid-off job:
unplug the seven-way from the BMS and it is the same balance connector it always
was. That is the cost of deleting the port, and it is a bench operation rather than
a routine one.

### Why the disconnect went, and what that costs

**This reversed on 2026-09-16, and the argument it reversed is worth keeping
rather than deleting.** The question asked in September 2026 was whether a
torso-mounted switch could replace the main disconnect, and the answer was no,
for a reason about amps rather than room.

**Nothing in a 12–16 mm panel bushing will CARRY this bus.** A 16 mm anti-vandal
switch is rated about 2 A at 24 V DC; the best "high current" parts in that shell
are 15 A. The robot's estimated simultaneous peak is **24 A** — estimated, never
measured — so a switch of that class would cap the machine below what it was
designed for. Carrying is the hard requirement: it applies whenever the robot is
on, not only when somebody operates the switch. Breaking 24 A at 25 V DC is worse
again, because there is no zero crossing to help the contacts part.

**So the switch commands the bus instead of carrying it**, which is the sensible
version of the idea and is what the power switch board is —
[`docs/POWER_SWITCH.md`](POWER_SWITCH.md) is the whole of it. Two P-channel
MOSFETs in the pack's positive lead, a button that closes them while it is held,
and a comparator that keeps them closed only while the controller says so and the
pack is above 19.2 V.

**What has changed is the second half of that answer.** The wall kept a pull-link
as well, and the reasons given were that pulling a connector by hand is a
disconnect rather than an emergency stop, and that a MOSFET usually fails shorted
and silently — so the robot would still run but would no longer turn off or cut
off, and nothing but a mechanical break would say so. **Both of those are still
true.** The loop key is gone anyway, and these are the three things that decided
it:

- **A wall with a switch and a pull-link asks the user which one turns the robot
  off.** Two controls for one job is how a robot gets left on.
- **The button had nowhere else to go.** The rear wall's stations were solved
  against every solid in the cavity and there were three of them; a fourth had to
  be swept the same way, and what the sweep found is that the depth behind this
  wall is the binding constraint. There is **11.2 mm** of clear air behind the
  disconnect's own station before the actuator harness bank — room for a
  connector that reaches 8.3 mm in, and not enough for any panel switch. The most
  the wall offers anywhere at that height is **21.4 mm**, outboard of x −44, and
  that is where the button now is.
- **Standing current is not a reason to keep it.** With the switch off the board
  has no DC path from the pack at all — every divider, comparator and reference
  hangs off the switched side — so a pack left connected is drained by its own
  leakage, not by this board.

**The cost is real and is not hidden anywhere else in this document.** Nothing
now isolates the pack except unplugging one from the series harness with the lid
off. A failed-short MOSFET looks exactly like a working one, and there is no
longer a hand-operated break to prove otherwise. If that trade is not acceptable,
the fix is not to put the loop key back in this wall — there is no depth for the
button anywhere else on it — but to make the pack's own in-shell connector the
service disconnect and say so in the build notes.

**THE PRE-CHARGE IS UNAFFECTED, and it is now the only thing that limits inrush.**
The switch's gates are pulled down through 470 kΩ against a 220 nF capacitor to
their own drains, which brings the bus up over about 130 ms at roughly a third of
an amp instead of slamming the bank. What the loop key's departure changes is the
first connection: it is the pack's own XT60, mated inside the shell, and it is
made with the switch open, so what it connects is a fuse and two transistor
sources and nothing that draws a spark. Dropping to an XT60 in September 2026 had
already taken the anti-spark away — AMASS make the pre-charge only in the XT90-S
— so the soft start was carrying that job before this change and carries it
still.

### What still has no mount

Nothing, since 2026-09-16 — and one thing that is mounted is still open.

**The capacitor bank is sized provisionally, and not measured.** Two 470 µF 35 V
cans are what section 1b buys, reasoned from six drivers and a short lead run
rather than read off a scope. **It is mounted now** — soldered into the power
switch board as C5 and C6, with a tie round the cans and a bead of adhesive at
each base against vibration — so what is open here is the value and not the
holding. Measure the bus excursion, then come back here.

**THE FUSE HAS A MOUNT AND THE SHUNT HAS NO EXISTENCE**, and those were the two
items this section used to carry. The main fuse is in a PCB-mount holder on the
power switch board beside the switches. **The shunt was deleted on 2026-09-16
along with the current measurement it served**, so it needs neither a mount nor a
row; what reads the bus now is the INA226 as a voltmeter on its own VBS pin,
which never went through a shunt. **The bulk bank moved onto that board too**,
and that is what paid for the board going through-hole: the reserve for it was
four cans of Ø16 × 25 where this bill buys two of Ø10 × 16, so the strip it held
became board.

**THE BUTTON HAS A MOUNT NOW, AND IT TOOK THE DISCONNECT'S.** It was the one
item this section carried on 2026-09-15 and it is a hole in the rear wall on
2026-09-16: a Ø12.2 bushing at x −44, clamped by the switch's own M12 nut, with
no screws. It is not at the disconnect's x because there is 11.2 mm of clear
depth behind that station and a panel switch needs more; the wall was swept and
21.4 mm is the most it offers, outboard of x −44. **The shorting link on J3 is
still what closes the switch on the bench**, and the button is what does it on
the robot.

**What has no mount now is nothing, and what has no ISOLATOR is the pack.**
Deleting the loop key left the two MOSFETs as the only break in the pack's
positive lead, and a MOSFET fails shorted far more often than it fails open. The
section above weighs that trade; it is recorded here because "everything is
mounted" and "everything is safe" are different claims.

### What the power protection now is, and what is still open

**Settled, and checked by arithmetic rather than by intention:**

- **inrush** — the switch's own soft start, about 0.3 A into the bank over 130 ms;
- **low-cell protection** — a hardware cutoff at 19.2 V on the filtered bus,
  3.20 V per cell, latched off until the button is pressed. It is a PACK-level
  cutoff, not a per-cell one: the BMS watches the cells and cannot act on the
  discharge path, and this acts and cannot see a single weak cell. A cell alarm
  on the balance tail is still the thing that catches that;
- **turning the robot off at all** — which it could not do before.

**Still open, and all three want the same measurement:**

- **the regeneration clamp and brake resistor.** This board switches the bus; it
  does not absorb energy coming back into it. With the pack connected the pack is
  the sink, and the case that wants the clamp is the bus being opened while a leg
  is driving — a blown fuse, a pack connector shaken loose, or this switch
  opening under load;
- **the emergency stop.** Nothing about it changes here except that there is now
  a line that can command the bus off. Whether an e-stop should cut the bus or
  command torque off through the controller is the open question, and cutting the
  bus while the legs move is exactly the case the clamp is missing for;
- **the fuse's rating and the shunt's value**, both of which follow the peak bus
  current that has still never been measured.

### Review corrections, 2026-09-15

The journal clamp now uses M5 x 12 with a 1 mm DIN 433 washer. The washer is
5.3 mm ID and 9 mm OD; the ordinary 10 mm OD washer is not interchangeable.
Nominal nut engagement is 2.3 mm; nominal screw-tip clearance is 1.0 mm.
This corrects the screw reach after removing the output register pocket. It
is not a qualification of the printed journal anchor or its creep strength.

The deck now has three edge notches: 44 x 6 mm for all motor buses, 18 x 6 mm
for the IMU, and 12 x 6 mm for the bus feed and shunt leads. Wires turn above
the deck outside the carrier outline, then drop through these notches. Keep
the two power/sense leads separate within their shared opening. No lead needs
to travel sideways under the PCB amongst solder tails. Finish the notch edges
and retain each lead with the existing internal harness ties.

Net budget change: **+1.8 g** (2.4 g of added fastener allowance, 0.6 g removed
from the deck). Total **2087.4 g**, leaving **212.6 g**. These include estimates.
The power switch board's move to the distribution board's footprint on
2026-09-15 then took the capacitor bank's allowance from 60 g to the 20 g two
cans really are, so the roll-up stands at **2077.4 g**, leaving **222.6 g**.

## 12. Where the printed parts get printed

**Added 2026-09-21.** Section 5 has carried "quote separately" against the printed
structure since this bill was written, with nobody named to ask. This section names
them. **Nothing in it is a quote.** No file has been uploaded to anybody and no
vendor has been contacted, so the ranking is built from what each one publishes
about itself — certification, machine fleet, stated lead time and whether it will
show a price at all — and not from anyone's experience of their work. Treat it as
the shortlist to send the STEPs to, and mark a row *checked* only when a real
quote comes back against it.

### What is being sent out

**Thirteen prints from nine STEP files**, which `uv run tools/export.py` writes into
`exports/`. Two handed thighs, two handed shins, two identical wheel adapters, four
journal sleeves, the pelvis shell, the torso cover and the electronics deck.

| | |
|---|---|
| Material | **PA12** — sintered, per the `[material]` block in `tools/mass_budget.toml` |
| Volume of nylon, whole robot | **about 406 cm³**, the union figure from `uv run tools/mass.py --union` |
| Printed mass at 0.93 g/cm³ | **377.6 g** union, 411.0 g by the sum convention this bill's roll-up uses |
| Largest single piece | **pelvis shell, 160.9 × 72.0 × 133.6 mm** — envelope from the 2026-09-14 STL export |

The pelvis shell is the only piece with an envelope worth checking against a machine,
and at 161 mm on its longest side it clears every SLS and MJF bed in the country with
room to spare. **Build volume rules nobody out**, so this decision is service and
price and nothing else.

### The bureaus, ranked

| | Vendor | Process and place | Why it sits here | Cost signal |
|---:|---|---|---|---|
| 1 | [**Amuse3D**](https://www.amuse3d.in/mjf-3d-printing-service) | HP MJF, PA12 / PA11 / PA12 Smooth. Chennai factory, sales in Bengaluru, Hyderabad, Pune, Mumbai, Delhi | Five HP MJF 5620 machines, **HP-certified production partner**, **ISO 9001:2015 and IATF 16949:2016** — the only automotive-grade quality paperwork on this list. 3–5 days to the door in India, 24-hour express if ordered by 14:30 IST | Quote only |
| 2 | [**iamRapid**](https://iamrapid.com/pricing/) | MJF and SLS nylon. Bengaluru, Delhi, Pune, Noida | **The only one that publishes its rates**: [MJF PA12](https://iamrapid.com/3d-printing-services/mjf/) and SLS nylon both **₹32–40 per cm³**, FDM PLA ₹6/gram, instant quote from an upload in under a minute, 3–5 business days | **₹13k–16k a set** at the published rate, before GST |
| 3 | [**Imaginarium**](https://imaginarium.io/additive-manufacturing/) | SLS and eight other processes. Mumbai, trading since 2006 | India's oldest and largest bureau, **17 machines across 24 materials**, and the strongest finishing shop of the five. No instant quote, so it is an email conversation, and on reputation it will be the dearest | Quote only |
| 4 | [**think3D**](https://www.think3d.in/) | FDM, SLA, SLS, MJF, DMLS, plus CNC and **14 injection moulding machines**. Hyderabad | Same printing range as the others with tooling behind it, which matters only if the pelvis ever goes to a mould. ISO certified, quote by email | Quote only |
| 5 | [**Makenica**](https://makenica.com/) | SLA, FDM, SLS, MJF | Upload for an instant quote, priced back by email inside half an hour. Wide range, **no industrial certification stated**, which is what keeps it below the four above | Quote only |
| 6 | [**Tesseract**](https://www.tesseract3d.com/sls-3d-printing/) | SLS nylon, Mumbai | A specialist rather than a full-service shop, and on exactly the process this bill's density figure was taken from. Worth a quote if the parts stay sintered PA12 rather than going to MJF | Quote only |
| — | [**Zbotic**](https://zbotic.in/3d-print-order/) | Industrial SLS and MJF, PA11 / PA12 / glass-filled | **Do not use.** Its industrial line quotes **15–20 days**, three to four times everyone else, for the same parts | — |

The recommendation is **Amuse3D for the parts and an iamRapid instant quote to price
them against**. iamRapid's published ₹32–40 per cm³ is the only number on this table
that did not have to be asked for, and 406 cm³ of nylon puts a whole robot's printed
structure at **₹13,000–16,240 before GST** — which is the first figure this bill has
ever carried against section 5's "quote separately" row.

### Two questions to put to every one of them

**Do you price on the part's own volume, or on its packed bounding box?** This is
worth more than the choice of vendor. The pelvis shell is 173 cm³ of nylon standing
inside a 1,548 cm³ box — it is a nine-tenths-empty open shell — so a bureau that
charges by bounding box or by packing density is quoting a part nine times the size
of the one being made. Ask before uploading, and ask again when the number comes back
looking wrong.

**What density do your finished parts come out at?** `tools/mass_budget.toml` already
says to, and it is the softest number on this whole bill that is not an estimate.
It currently assumes **0.93 g/cm³**, EOS PA2200's published part density for laser
sintering. **Four of the six vendors above are MJF houses, and HP's PA12 finishes
nearer 1.01**, which over 406 cm³ is **about +33 g** on a robot with 222.6 g of
headroom. That is not a rounding error and it is not free: choosing MJF is a change
to the `[material]` block and a re-run of the roll-up, not just a change of supplier.

### The cheap way to fail early

Before committing to sintered parts, the whole printed set in **FDM PLA at ₹6/gram**
— [iamRapid](https://iamrapid.com/3d-printing-services/) or
[3Ding](https://3ding.in/print/), the latter quoting 24–48 hours — comes to roughly
**₹2,500 and a couple of days**. It is the wrong material and will not carry a joint,
but it settles every question this bill cannot answer on paper: whether the 6800
bearings press into a Ø19.2 bore printed to size, whether an actuator with its disc
bolted on actually enters a 45.2 mm clevis, and whether the battery, BMS, carrier and
deck stack into the pelvis in the order section 11 says they do. **A wrong dimension
found in PLA costs ₹200; the same dimension found in PA12 costs a 198.8 g reprint.**
