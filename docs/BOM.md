# Provisional Bill of Materials — India Hobbyist Build

**Status:** revised 2026-09-11 against the **six-motor wheeled CAD**, which is `cad/` on this branch. Until this revision the document described the 8-DOF walking biped; that machine and its BOM now live on the `walking` branch, and nothing below refers to it except where a line says so.  
**Sourcing check:** 2026-08-30 for everything carried over; the wheel and clamp lines added 2026-09-11, and the journal line respecified the same day, have not been price-checked. **The battery lines were re-checked 2026-09-13 against live stock**, which is when the BMS was chosen and when the charger's price moved: two things on this table are not on a shelf today, and both say so in their own rows. **The transceiver line was respecified 2026-09-13** to a through-hole part, and the carrier's passives were added beside it; neither is price-checked. **EVERY PURCHASE LINK ON THIS BILL WAS OPENED ON 2026-09-13** and the table now says what each vendor's page said that day. Five links were dead or pointed abroad and are replaced; ten named a part the vendor had run out of, and those moved to an Indian shop that had it. Six items have **no Indian stock at all** today and each says so on its own line: the six DAMIAO actuators, the adapter board and the debug lead, none of which any Indian seller carries; the WeAct MCU board; the Matek BEC; the Daly BMS; M3 × 14 screws; and the wheel clamp's Ø30 penny washer. Prices marked *checked* are that day's listed price including GST where the vendor shows it. **The electrical table was then swept for completeness on the same day**, against `cad/electronics.py`'s drawn hardware, `tools/mass_budget.toml` and the motor's own manual. Six required components had no row at all — the carrier's board and passives, the DAMIAO adapter board, the SBC's boot media, the logic and sensor harness, the INA226's external shunt and the contactor the E-stop commands — and all six are rows now. Three of them are marked WAIT rather than specified, because what they are depends on a measurement nobody has taken. **The three DAMIAO cable and adapter lines were then re-linked on 2026-09-13**, because all three pointed at Foxtech's DAMIAO category page, which sells motors and no cables: they now name the cable set's own product page and the dropdown option to pick from it. The adapter board carries a price for the first time — **US$2.30, in stock** — and is a line item of its own rather than a motor bundle, which is a change of instruction, not just a link.  **The charge inlet line was corrected on 2026-09-13 because it named a part that will not fit the robot**, which is a different class of error from a stale price: it linked the GX16 with a **3-hole circular flange**, while the CAD cuts a bare Ø16 hole for a threaded bushing and has no flange screw holes and nowhere to put them. The same shop sells the plain panel mount for ₹50 less and has it in stock, and that is now what this bill says. **The contact gender on that line reversed at the same time**, and for a reason worth reading before ordering. **The two actuator pigtail lines were then deleted the same day.** Both cables exist, both arrive with every motor, and neither is sold separately by anyone, so neither was ever something to buy; what mattered on those rows — the quantities, the request for spares, and why a generic SH1.0 lead will not do for the power one — moved onto the actuator line, which is the thing actually being bought. **A bill of materials lists what is ordered**, and a row nobody can order is a note pretending to be a purchase. Checking that turned up two things nobody had asked for. **A cable the tuning chain needs and this bill never bought**, the GH1.25 3-pin lead from the adapter board out to the debug tool, which is now a row at US$0.90. And **the newer V1.1 manual reverses the motors' termination-resistor default**, which the actuator line had stated as fact; that line now says to read the switch rather than trust either revision. **The bulk bus capacitance was sized on 2026-09-13**, from the drivers and the lead run rather than from a measurement, and it is the first number that line has ever carried; the cans are neither price-checked nor sourced to a listing, and the same pass found **the main disconnect row stale against the CAD**, which has moved to an XT60 with no anti-spark in it. That row now says so and has to be re-sourced.  
**Project baseline:** 360 mm, six-motor wheeled biped — hip pitch, knee and a driven wheel on each leg — using DAMIAO DM-J3507-2EC actuators. Hip roll and the ankles are deleted, and there are no feet. **It carries its own 6S 2200 mAh battery** and the umbilical is gone; the torso grew from 125 × 68 × 65 mm to 153.9 × 72 × 86 to hold one and the power hardware beside it, which is where the 21 mm of extra height came from. **Its width is no longer a chosen number** — `cad/wheeled_parameters.py` derives it from the hip clevises, so the shell now ends exactly where they do.

This BOM is intentionally split between parts that should be sourced early and commodity parts that should remain flexible until the CAD/electrical design is mature. Purchase links are practical India-oriented sourcing references, not immutable approved vendors. Re-check price, GST, shipping, stock and seller immediately before ordering. Imported prices exclude shipping, customs duty, IGST, payment/FX charges and courier handling unless explicitly stated.

Printed structural parts will be fabricated offsite. The BOM therefore keeps the required material/specification information but does not attempt to source printers, dryers, filament or printed parts.

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

### 1a. Electrical

**The robot carries a battery again.** It was tethered from August 2026 to
September 2026 and the umbilical is now deleted, along with the boom that was
supposed to carry it and never got designed. The nine battery lines head this
table because none of them existed a week ago and nothing else can be bought
until they are settled.

| Subsystem | Qty | Current part / specification | Indicative price | Purchase / source link | Risk | Notes |
|---|---:|---|---:|---|:---:|---|
| **Battery** | 2 + 1 spare | **3S 2200 mAh 35–40C soft-case LiPo, XT60**, ~76 × 33 × 25 mm, ~144 g. Two wired in series make the robot's 6S 2200 mAh, 48.8 Wh pack | **₹1,465** checked (GenX) · **₹2,199** checked (Bonka) | [Robokits — GenX 3S 2200 mAh](https://robokits.co.in/batteries-chargers/drone-batteries/genx-power-premium-lipo-battery/genxpower-11.1v-lipo-batteries/genx-11.1v-3s-2200mah-40c-80c-premium-lipo-lithium-polymer-battery) · [Indian Hobby Center — Bonka 3S 2200 mAh 35C](https://www.indianhobbycenter.com/products/bonka-2200mah-35c-3s1p-11-1v-lipo-battey) | 🟠 | Two 3S weigh ~100 g less than one 6S. Buy a matched pair; measure one before printing the pelvis. |
| **Battery series harness** | 1 + 1 spare | **Ready-made 2-into-1 XT60 series harness**, 14 AWG silicone | ~₹200-class, not price-checked | [Robu — XT60 series harness, 2 packs](https://robu.in/product/xt60-harness-for-2-packs-in-series-1pc) · [Robu — SafeConnect series harness 2M1F](https://robu.in/product/safeconnect-xt60-harness-for-series-connection-2m1f) | 🟢 | Buy, don't make. A straight XT60 jumper puts packs in parallel or shorts them. Match harness gender to the packs. |
| **Main disconnect** | 1 panel mount + 1 loop key, spares of both | **AMASS XT60E-M eared panel mount** in the rear wall, armed by a **plain XT60 female with its two terminals bridged** | **₹199** checked, in stock (Probots) | [Probots — AMASS XT60E-M panel mount](https://probots.co.in/xt60e-m-male-panel-mount-connector-for-lipo-battery-esc-brushless-motor.html) · [The Engineer Store — XT60E-M](https://www.theengineerstore.in/products/xt60e-m-male-panel-mount-connector-for-lipo-battery-esc-brushless-motor) | 🟠 | Loop key, not a pack plug. XT60 has no anti-spark, so inspect contacts. Measure the housing before printing the pelvis. |
| **Charge inlet** | 1 panel socket + 1 spare | **AMASS XT60E-F female panel mount**, flange outside the rear wall, 2 × M2 with washers and nuts. The charger's lead needs a **male** XT60 | **₹199** checked 2026-09-13, in stock (Probots) | [Probots — AMASS XT60E-F panel mount](https://probots.co.in/xt60e-f-female-black-connector-for-lipo-battery-esc-brushless-motor.html) | 🟠 | Female on purpose: the loop key can't fit it and the charger lead can't fit the disconnect. Sockets, not pins, on the live side. Measure the body before printing — part of its cut is read off the drawing's scale. |
| **Antenna lead and bulkhead** | 1 + 1 spare | **u.FL/IPEX to SMA (or RP-SMA) female bulkhead pigtail**, ~10–20 cm RG178, plus a matching antenna | ~₹100–200 | [Probots — u.FL to RP-SMA bulkhead pigtail](https://probots.co.in/ipex-1-u-fl-to-rp-sma-female-bulkhead-pigtail-10cm-rg178-11mm-thread.html) · [Robokits — SMA to IPEX](https://robokits.co.in/wireless-solutions/wireless-accessories-and-antenna/female-sma-to-ipex-connector) | 🟠 | Gets the radio out of the sealed shell. SMA and RP-SMA don't mate; match the SBC's connector. |
| **Balance leads, and the merge** | 2 × 3S + 1 × 6S | Two JST-XH 3S (4-pin) leads for the packs' own tails, and one JST-XH 6S (7-pin) lead spliced to them inside the shell, landing on the BMS | **₹12** (4-pin) · **₹15** (7-pin), checked | [Indian Hobby Center — 4-pin JST-XH lead, 25 cm](https://www.indianhobbycenter.com/products/4-pin-jst-xh-2515-rmc-female-connector-with-wire-25cm-2-54mm-pitch-1-pc) · [Indian Hobby Center — 7-pin JST-XH lead, 25 cm](https://www.indianhobbycenter.com/products/7-pin-jst-xh-2515-rmc-female-connector-with-wire-25cm-2-54mm-pitch-1-pc) | 🟢 | Merges both packs' taps into one 7-pin for the BMS; omit the upper pack's negative. Meter before connecting. |
| **Cell alarm** | 1–2 | 1S–8S balance-lead voltage checker with buzzer | **₹86** checked | [Robokits — 1–8S checker](https://robokits.co.in/batteries-chargers/accessories/charge-protection-circuit/li-po-li-ion-1-8s-voltage-checker-and-low-voltage-alarm) · [Robu](https://robu.in/product/lipo-battery-voltage-checker-1s-8s-with-buzzer/) | 🟢 | Backstop only. Real protection is setting each motor's undervoltage threshold to 21.6 V. |
| **Bus monitor** | 1 | **INA226** I²C voltage/current/power monitor, 36 V bus, with an external shunt sized for the bus | **₹120** checked | [Techtonics — INA226 module](https://techtonics.in/product/ina226-i2c-voltage-current-and-power-monitor-module/) | 🟠 | Gives the controller pack state. On-board shunt reads only ~20 A against a 24 A peak; see next row. |
| **Bus shunt** | 1 + 1 spare | ⏸️ **WAIT** — external current-sense shunt for the INA226, of the order of 1–2 mΩ, rated for the bus's 24 A peak and its I²R heat | TBD | **WAIT — value follows the measured peak, and the measurement needs the monitor** | 🟠 | Replaces the module's shunt; rewrite the INA226 calibration to match. Stock shunt suffices for a first stand, not driving. |
| **Battery management system** | 1 + 1 spare | **Daly Li-ion NMC 6S 24V 20A**, 58 × 33 × 8.2 mm, 45 g, passive balancing at 30 mA from 4.18 V/cell, wired **charge-only** | **₹867** checked 2026-09-13 — **and out of stock there on the day** · **₹475–600** from an IndiaMART reseller, the only Indian listing showing stock | [QuartzComponents — Daly 6S 24V 20A NMC](https://quartzcomponents.com/products/daly-li-ion-6s-24v-20a-battery-management-system) · [IndiaMART — Daly 6S 24V 20A, Noida](https://www.indiamart.com/proddetail/daly-li-ion-6s-24v-20a-waterproof-battery-management-system-bms-protection-board-2852913515255.html) | 🟠 | Wired charge-only to balance the pack; gives no over-discharge cutoff. Two printed parts are cut to it: measure first. |
| **Charger** | 1 | **IMAX B6AC, 80 W, 1–6S** charge/discharge/storage | **₹2,285** checked, in stock (B6AC, Robokits RKI-1369) · **₹2,079** (B6, DC only, Robu) | [Robokits — IMAX B6AC 80 W](https://robokits.co.in/batteries-chargers/chargers/imax-chargers/imax-b6ac-80w-charger-discharger-1-6-cells) · [Robu](https://robu.in/product/imax-b6-80w-6a-charger-discharger-1-6-cells/) | 🟢 | Charge via the inlet, loop key pulled, 6S at 2.2 A. A balance board plus series harness shorts a pack. |
| **Charge and storage bag** | 1–2 | Fire-resistant LiPo sack, 30 × 23 cm | **₹859** checked | [Robu — large fire- and water-resistant LiPo bag](https://robu.in/product/large-space-fire-and-water-resistant-lipo-battery-bag/) | 🟢 | Non-negotiable once there are cells in the building. |
| **Power distribution board** | 1 + 1 spare | **SwiftWing PDB-02-XT60**, 3S–6S direct battery bus: 50 × 50 × 1.6 mm, 4-layer 2 oz copper, 13 g, factory XT60 input, six pairs of ESC solder tabs, 4 × M3 on a 45 mm square | ~₹300–600 class, not price-checked | [Robu — SwiftWing PDB-02-XT60](https://robu.in/product/swiftwing-pdb02-xt60-power-distribution-board/) · [datasheet v1.2](https://swiftwingtech.io/downloads/datasheets/swiftwing-pdb-02-xt60-6xt30-power-distribution-board-datasheet-v1-2.pdf) | 🟠 | Replaces a custom PCB; pelvis posts follow its 45 mm hole square. Confirm its 26 V rating with the vendor. |
| **Debug serial lead to the PC** | 1 + 1 spare | **GH1.25 3-pin cable, 300 mm**, from the adapter board to the USB debug tool | **US$0.90** checked (Foxtech), in stock | [Foxtech — DAMIAO joint motor cables](https://store.foxtech.com/damiao-joint-motor-cables/), option **GH1.25-3Pin Reverse Cable (300mm)** | 🟠 | Links adapter board to USB debug tool; nothing else supplies it. Buy on the same Foxtech order. |
| **DAMIAO adapter board** | 1 + 1 spare | **SH1.0 3-pin + 8-pin to XT30 + GH1.25 adapter board**, DAMIAO's own | **US$2.30** checked (Foxtech), in stock | [Foxtech — DAMIAO joint motor cables](https://store.foxtech.com/damiao-joint-motor-cables/), the option named **SH1.0 3Pin + 8Pin to XT30 + GH1.25 Adapter Cable** | 🟠 | Not included with the motor; the only route to the tuning assistant. Do not substitute the XT30 (2+2) power adapter. |
| Realtime MCU dev board | 2 | **WeAct STM32G474CEU6 core board, 36.53 × 28.40 mm** | ₹859 (Robu) · ₹748 (ElectroPi) — **out of stock at both, 2026-09-13** | [Robu — WeAct STM32G474CEU6](https://robu.in/product/weact-studio-long-type-stm32g474ceu6/) · [ElectroPi](https://www.electropi.in/weact-studio-long-type-stm32g474ceu6-stm32g474-stm32g4-stm32-core-board-demo-board) | 🟠 | No mounting holes; it hangs on its headers from the carrier. NUCLEO-G474RE does not fit the torso. |
| **Single-board computer** | 1 | **Banana Pi BPI-M4 Zero, 65 × 30 mm** | **₹8,899** checked (2 GB + 8 GB eMMC) | [Tanna TechBiz — BPI-M4 Zero 2 GB/8 GB](https://tannatechbiz.com/banana-pi-m4-zero-2g-ram-8g-emmc.html) · [Banana Pi wiki](https://wiki.banana-pi.org/Banana_Pi_BPI-M4_Zero) | 🟠 | Mounting holes inferred from Pi Zero 2 W drawing; measure before cutting. Underside microSD needs 2 mm standoff. |
| **SBC boot media** | 2 | **microSD 32 GB, UHS-I class 10 or better** — unless the BPI-M4 Zero variant bought carries onboard eMMC | **₹1,499** checked (SanDisk Ultra) · **₹899** (Geonix) | [QuartzComponents — SanDisk Ultra 32 GB microSD](https://quartzcomponents.com/products/32gb-ultra-microsd-memory-card-red-grey) · [Indian Hobby Center — Geonix 32 GB](https://www.indianhobbycenter.com/products/32gb-geonix-micro-sd-card-class-v30-150mb-s-memory-card) | 🟢 | Check whether the board variant has eMMC; if so the card is recovery only. Two, because cards fail quietly. |
| CAN-FD transceiver | 4 | **MCP2562FD-E/P — 8-pin PDIP**, 8 Mbps CAN-FD, with a separate **VIO** pin for 3.3 V logic | **₹131 each** (1+), checked | [element14 India — MCP2562FD-E/P](https://in.element14.com/microchip/mcp2562fd-e-p/can-transceiver-8mbps-1-tx-rx/dp/2434898) · [RS India](https://in.rsdelivers.com/product/microchip/mcp2562fd-e/p/microchip-can-transceiver-8-mbps-8-pin-pdip/8243129) | 🟢 | Two fitted, two spare. Through-hole for the perfboard carrier; VDD to 5 V, VIO to 3.3 V. Socket them. |
| **Carrier passives, sockets and perfboard** | 1 set | Per CAN bus: **one 120 Ω** 1 % 0.25 W metal film, terminating the carrier end only — the far motor's own switch is the other end — and **100 nF** X7R at both VDD and VIO of every transceiver, plus one **10 µF** low-ESR bulk on the carrier's 5 V. For the I²C bus, **2 × 4.7 kΩ** pull-ups to 3.3 V, fitted only if neither sensor module carries its own. Then 4 × **DIP-8 sockets**, 4 × **2.54 mm 1×20 female header** for the two MCU boards, and one **10 × 10 cm sheet of 2.54 mm perfboard** | **~₹250 for the lot**, checked | [Robu — 8-pin DIP socket, 10 pcs](https://robu.in/product/8-pin-dip-ic-socket-base-adaptor-pack-of-10/) · [Robocraze — 100 nF 50 V, 10 pcs](https://robocraze.com/products/0-1-uf-50v-ceramic-capacitor) · [QuartzComponents — 10 µF 50 V](https://quartzcomponents.com/products/10uf-50v-electrolytic-capacitor) · [Indian Hobby Center — 120 Ω 1/4 W](https://www.indianhobbycenter.com/products/120-ohm-carbon-film-resistors-25-watt-tolerance-5-percent) · [QuartzComponents — 40-pin female header](https://quartzcomponents.com/products/40-pin-straight-female-berg-strips) · [Indian Hobby Center — 10 × 10 cm perfboard](https://www.indianhobbycenter.com/products/10x10-cm-double-sided-universal-pcb-prototype-veroboard-green-pcb-board-4x4-inch) | 🟢 | Terminate at carrier and far motor only: two motor switches ON, four OFF. STBY floats high: drive it low. |
| Main IMU | 1–2 | **BNO085 Nano breakout** | ~₹2.1k | [Robocraze — BNO085 Nano](https://robocraze.com/products/bno085-9-dof-orientation-imu-sensor-fusion-nano-breakout-board) | 🟢 | Nano board only; the Adafruit breakout does not fit. The pelvis prints an 11 × 10 mm adhesive seat for it. |
| USB-CAN-FD debug interface | 1 | Waveshare USB-CAN-FD or DAMIAO-compatible interface | **₹12,975** checked | [Robocraze — Waveshare USB-CAN-FD-B](https://robocraze.com/products/waveshare-industrial-can-can-fd-bus-data-analyzer) | 🟠 | -B variant for Linux. May not run DAMIAO's tuning assistant; check with first motors. Switch its 120 Ω off. |
| Branch connectors | 8–10 pairs provisional | Genuine **AMASS XT30** or locking equivalent | **₹41/pair** checked | [Robokits — original AMASS XT30](https://robokits.co.in/batteries-chargers/accessories/plugs-and-connectors/amass-xt30-male-and-female-connector-original-xt30-f-m?cPath=67_618_623) | 🟢 | Six motor branches plus spares. Do not bulk-buy until routing confirms the connector count. |
| Main bus wire | ~1 m robot-side | 14 AWG high-strand silicone wire | **₹103–105/m** checked | [QuartzComponents — 14 AWG silicone, red](https://quartzcomponents.com/products/14awg-silicone-wire-red-1-meter-high-quality-ultra-flexible-for-battery-packs) · [black](https://quartzcomponents.com/products/14awg-silicone-wire-black-1-meter-high-quality-ultra-flexible-for-battery-packs) | 🟢 | Down from ~3 m now the tether is gone; all runs are inside the torso. |
| Motor branch wire | 4–6 m | 16–18 AWG high-strand silicone wire | **₹65/m** (16 AWG) · **₹40/m** (18 AWG), checked | [QuartzComponents — 16 AWG silicone](https://quartzcomponents.com/products/16awg-silicone-wire-black-1-meter-high-quality-ultra-flexible-for-battery-packs) · [18 AWG](https://quartzcomponents.com/products/high-quality-ultra-flexible-18awg-silicone-wire-black-1-meter) | 🟢 | Final gauge after measured motor current. |
| CAN wiring | ~4 m | Flexible twisted pair ~24–26 AWG | **₹18/m** checked | [QuartzComponents — 26 AWG silicone](https://quartzcomponents.com/products/26awg-silicone-wire-black-1-meter-high-quality-ultra-flexible-wire) | 🟢 | Twist matched pairs; move to proper 120 Ω cable if signal-integrity testing demands it. |
| **Logic and sensor harness** | ~2 m + a connector kit | Flexible **26–28 AWG** hook-up wire, and **2.54 mm JST-XH housings with crimp terminals** to land both ends | **₹18/m** wire · **₹500** kit, checked | [QuartzComponents — 26 AWG silicone](https://quartzcomponents.com/products/26awg-silicone-wire-black-1-meter-high-quality-ultra-flexible-wire) · [ThinkRobotics — 460-piece JST PH/XH kit](https://thinkrobotics.com/products/460pcs-jst-ph-2-0-connector-kit-2-to-6-pin-male-female-plug-housing-with-crimp-terminal-assortment-box) | 🟢 | Covers the IMU, bus monitor and 5 V feeds. Use plugs, not solder joints, so the deck stack lifts out. |
| **Logic DC/DC** | 1 + 1 spare | **Matek BEC12S-PRO**, 9–55 V in, 5 V/8 V/12 V selectable at 5 A continuous (9 A peak), 35 × 24 × 5.5 mm, 5 g | ₹1,729 (Robu) · ₹1,694 (RC Mumbai) — **out of stock at both, 2026-09-13** | [Robu — MATEKSYS 12S Pro BEC](https://robu.in/product/rts-mateksys-12s-pro-bec-9-55v-to-5v-8v-12v-5a/) · [RC Mumbai](https://www.rcmumbai.com/products/matek-12s-pro-bec-12s-9-55v-input-5v-8v-12v-5a-output) · [Matek BEC12S-PRO](https://www.mateksys.com/?portfolio=bec12s-pro) | 🟢 | Set it to 5 V. 9–55 V input covers the pack's full swing; it is the torso's main heat source. |
| Main fuse | 2 | Automotive blade fuse + holder, initial ~15–25 A range | **₹5** per fuse · **₹149** holder, checked | [QuartzComponents — 20 A blade fuse](https://quartzcomponents.com/products/automotive-blade-fuse-20a) · [Indian Hobby Center — in-line blade fuse holder](https://www.indianhobbycenter.com/products/waterproof-in-line-blade-fuse-with-holders-for-car-fuse-replacement) | 🟢 | Final value follows measured current and fault strategy. |
| Emergency stop | 1 | Latching 22 mm mushroom switch commanding motor-power disconnect | ~₹100-class switch reference | [Robocraze — 22 mm mushroom E-stop](https://robocraze.com/products/ywbl-wh-mushroom-emergency-stop-push-button-switch-22mm) | 🟠 | Commands the contactor; never carry motor current through it. No home in the CAD yet: needs a Ø22 hole. |
| Motor-power contactor | 1 | ⏸️ **WAIT** — a **DC**-rated contactor or high-current relay in the bus, held closed by the E-stop | TBD | **WAIT — follows the measured bus current and the fault strategy** | 🟠 | Must be DC-rated or it welds. Needs a coil flyback diode and a precharge resistor; makes the bus clamp mandatory. |
| **Bulk bus capacitance** / regen clamp | 2 cans + 2 spare | **2 × 470 µF, 35 V, low-ESR aluminium electrolytic**, 105 °C, at least 0.8 A RMS of ripple each at 100 kHz, Ø10–12.5 × 20–25 mm, soldered across the distribution board's bus copper. **The clamp and brake resistor beside them are still ⏸️ WAIT** | **~₹100 the pair**, not price-checked | **Not sourced to a listing** — a Panasonic FR or Nichicon UPW class part from any of the shops above. **Not a polymer and not a ceramic**: an electrolytic's ESR damps the bus ringing | 🟠 | Starting value, not measured; more risks welding the disconnect. Clamp is required: pulling the key while rolling over-volts the bus. |
| Heatshrink / braided sleeve / strain relief | Assortment | Flexible harness consumables | **₹322** checked (530-piece kit) | [Robocraze — 530-piece heat-shrink kit](https://robocraze.com/products/530-pcs-color-shrink-tube-wire-insulation-sleeve) | 🟢 | Critical around moving joints despite low cost. |

### 1b. Mechanical

| Subsystem | Qty | Current part / specification | Indicative price | Purchase / source link | Risk | Notes |
|---|---:|---|---:|---|:---:|---|
| Actuator | 6 | **DAMIAO DM-J3507-2EC, 24 V** | Foxtech **US$89–95** reference | [Foxtech](https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/) | 🔴 | Buy two first, four after validation. Adapter board not included. Read each motor's termination switch; manuals disagree on its default. |
| **Drive wheels** | 2 + 2 spare | **80 × 24 mm inline-skate wheel, ~85A cast PU, bearings removed** | **₹1,026** checked for the 4-pack | [Cosco — inline skate wheels, 80 mm](https://store.cosco.in/products/skating-inline-skate-wheels) · Decathlon/Oxelo 80 mm 84A 4-pack | 🟠 | Remove and discard the 608 bearings. Hub and crown figures are representative: measure the bought wheel before printing the adapter. |
| Support bearings | 2 + 2 spare | **6800-2RS — 10 × 19 × 5 mm** | Local bearing-shop pricing preferred; online references can be much higher | [IndustryBuying — 6800-2RS reference](https://www.industrybuying.com/special-bearing-monotaro-BEA.SPE.238091927) | 🟢 | Hip pitch only; knee and wheel need none. Prefer SKF, NTN, Koyo or NSK locally. |
| Joint journals | 2 + 2 spare | **MISUMI MSGSS10-8** — Ø10 × 8 mm hardened ground dowel pin, **g6 undersized**, one end chamfered and one radiused | Not price-checked | [MISUMI India — MSGSS g6 dowel pins](https://in.misumi-ec.com/vona2/detail/110302390620/) · fallback [Fastdep Ø10 linear shaft](https://www.fastdep.in/product/linear-shaft-10mm/), sold out 2026-09-13 | 🟠 | g6 is a hand fit in the bearing; stocked m6 pins interfere. Take 10 mm if 8 isn't offered. |
| Retaining compound | 1 | **Loctite 638**, 50 ml or equivalent | **₹677** checked | [Amazon.in — Loctite 638 50 ml](https://www.amazon.in/Loctite-638-Strength-Retaining-Compound/dp/B0074NAX8A) | 🟢 | Bonds bearings into printed cheeks. Test polymer compatibility and retention on a coupon first. |
| Printed structural parts | 1 robot set | **PA12-CF**, geometry/orientation per CAD and fabrication notes | Offsite fabrication | **Offsite fabrication — no purchase link required** | 🟠 | Nine prints: four limbs, two wheel adapters, pelvis shell, cover and electronics deck. Supplier must meet material and orientation spec. |
| PETG fit mock-ups | As needed | PETG, 1.75 mm equivalent | Offsite fabrication | **Offsite fabrication — no purchase link required** | 🟢 | Fit mock-ups only; not structural. |
| M3 fasteners | 76 installed + spares | 12.9 SHCS in M3 × 6, ×8 validation stock, ×10, ×12 and ×14; washers — see section 10 | ~₹500–1,000 total class | [Robu — M3 × 6 set](https://robu.in/product/easymech-set-m3-x-6mm-socket-head-cap-allen-bolt-nut-12-pcs/) · [QuartzComponents — M3 × 8](https://quartzcomponents.com/products/m3-x-8mm-hex-allen-socket-head-screwpack-of-10) · [Robu — M3 × 10 set](https://robu.in/product/easymech-set-m3-x-10mm-socket-head-cap-allen-bolt-nut-12-pcs/) · [Indian Hobby Center — M3 × 12](https://www.indianhobbycenter.com/products/m3x12mm-hex-allen-socket-head-ss202-screw-dia-3mm-length-12mm) | 🟢 | No Indian stock of M3 × 14, and hobby shops lack 12.9; order from a fastener supplier. |
| **M5 wheel clamp set** | 2 + spares | **M5 × 12 SHCS**, **Ø30 × 2 penny washer** (Ø5.5 bore), **M5 heat-set insert Ø6.4 × 9.5** | **₹78** screw set · **₹159** inserts, checked | [Robu — EasyMech M5 × 12 cheese-head set](https://robu.in/product/easymech-m5-x-12mm-chhd-bolt-nut-and-washer-set-25pcs/) · [Robu — M5 × 8 heat-set insert](https://robu.in/product/m5-x-8-mm-brass-heat-set-threaded-round-insert-nut-25-pcs/) | 🟢 | Drives the wheel by clamping. Stocked inserts are 8 mm, not 9.5; Ø30 penny washers come from hardware shops. |
| **M2.5 fasteners** | 4 + spares | M2.5 SHCS and M2.5 brass inserts, provisional | **₹26** screws · **₹39** inserts, checked | [QuartzComponents — M2.5 × 8 SHCS](https://quartzcomponents.com/products/m2-5-x-8mm-hex-allen-socket-head-ss202-bolt) · [Indian Hobby Center — M2.5 × 4 brass insert](https://www.indianhobbycenter.com/products/m2-5x4mm-brass-threaded-inserts-dia-2-5mm-length-4mm) | 🟢 | Banana Pi mounts. Length follows the measured standoff height; don't buy in quantity. |
| Threadlocker | 1 | **Loctite 243**, medium strength | **₹628** checked | [Amazon.in — Loctite 243 50 ml](https://www.amazon.in/Medium-strength-Threadlocker-Thixotropic-temperature-performance/dp/B014MMG3AM) | 🟢 | For metal threaded interfaces. |
| **Board standoffs** | 8 + spares | **M3 brass, 6 mm A/F × 3 mm** — four under the distribution board, four under the controller carrier | ~₹300-class assortment | [Robu — M3 × 5 brass pillar standoff](https://robu.in/product/m3-x-5mm-male-female-brass-hex-threaded-pillar-standoff-spacer-24-pcs/) | 🟢 | Shortest stocked brass pillar is 5 mm, not 3; accept 2 mm higher boards or use nylon spacers. |
| **Battery strap** | 2 | Hook-and-loop cinch strap, ~15 × 250 mm | ~₹150-class | **Local hardware — no fixed SKU** | 🟢 | Backup for when the deck is off; threads through the battery rails' slots under the packs. |

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

- 2 + 2 spare **6800-2RS, 10 × 19 × 5 mm** bearings.
- 2 + 2 spare **Ø10 × 8 mm g6 dowel pins** for the journals, ordered to length rather than cut to it.
- No bearing carrier: the cheek is bored Ø19.2, a printed boss on its outer face carries the shoulder the bearing seats against, and the bearing is bonded into that. **Nothing in this section needs a machine shop, and since 2026-09-11 nothing needs a bench operation either** — the journals were the last thing that did, and they are now a catalogue dowel pin ordered at Ø10 × 8 rather than a stub sawn and faced from shaft stock.

**Hip pitch is the only straddled joint on this robot.** Knee and wheel bolt their flat limb plate directly to the actuator's rear cover and therefore use no far bearing or journal at all.

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
- E-stop switches
- heatshrink and cable sleeve
- inline-skate wheels

Avoid saving a few grams by specifying a rare bearing or fastener that creates an import dependency.

## 4. Development-only equipment

Printed-part production equipment is intentionally omitted because fabrication is handled offsite.

| Item | Qty | Current requirement | Purchase / source link | Priority | Notes |
|---|---:|---|---|---|---|
| Bench DC supply / source | 1 | 24 V-class source sized deliberately for robot testing, with regeneration handled | **WAIT — source architecture must be selected with regen handling** | **Critical** | The whole-robot simultaneous peak was estimated near **32 A for eight actuators**; six on the same per-motor basis is about **24 A**, and neither figure has been measured. A 30 V / 10 A bench supply is useful for commissioning but is not a full-robot source. Most supplies cannot sink regenerated current. |
| USB-CAN-FD adapter | 1 | Waveshare **USB-CAN-FD-B** — the variant with Linux drivers | [Robocraze — Waveshare USB-CAN-FD-B](https://robocraze.com/products/waveshare-industrial-can-can-fd-bus-data-analyzer) | High | Commission motors independently of final firmware. ₹12,975 checked; the Windows-only plain USB-CAN-FD is ₹9,150 at [ThinkRobotics](https://thinkrobotics.com/products/industrial-grade-can-can-fd-bus-data-analyzer). |
| Digital caliper | 1 | 0.01 mm display class | [Indian Hobby Center — INGCO HDCD28150, 150 mm](https://www.indianhobbycenter.com/products/ingco-hdcd28150-digital-vernier-caliper-150mm-6-inches) | High | ₹1,499 checked; 0.01 mm resolution, ±0.03 mm accuracy on the vendor's own specification. Measure received hardware, printed fits, spacers, journals, **the skate wheel's hub and bore**, a battery pack, **the BMS board** and **an XT90E-M's panel cutout** before the pelvis is printed. Those four are the figures in the CAD with no vendor drawing behind them, and all four are now cut into the pelvis itself — the printed panel that used to absorb a wrong connector dimension is gone, so a wrong figure is a 183 g reprint again. The two bushings are the exception and the reason to prefer them: a round hole 0.2 mm oversize is still a good hole. |
| Torque test arm | 1 | Printed/metal lever of accurately measured radius | **Custom / local fabrication** | High | Combine with known masses or a load scale for actuator torque calibration. Still outstanding, and now doubly so: the wheeled robot's torque envelope has not been re-derived. |
| Luggage/load scale | 1 | ~0–20/50 kg range | [Slovic — 50 kg digital luggage scale](https://slovic.com/products/slovic-50kg-digital-luggage-scale-with-lcd-indicator-black-silver-travel-friendly) | Medium | Calibrate against known masses before using for torque measurements. Also the quickest way to settle the 60 g wheel estimate, which is the softest figure in the mass table. |
| IR thermometer / thermocouples | 1+ | Temperature measurement for actuator and joint tests | [QuartzComponents — Fluke 59 Mini](https://quartzcomponents.com/products/fluke-59-mini-infrared-thermometer-18c-to-275c) · [Fluke 59 MAX](https://quartzcomponents.com/products/fluke-59-max-infrared-thermometer-30-c-to-350-c-with-1-year-warranty) | High | ₹3,610 and ₹5,496 checked. Contact thermocouples are preferable when logged data matters. A continuously driven wheel motor is a thermal duty cycle the walking robot never had. |
| Logic analyser | 1 | 8-channel USB logic analyser class | [Indian Hobby Center — 24 MHz 8-channel analyser](https://www.indianhobbycenter.com/products/usb-logic-analyze-24m-8ch-mcu-arm-fpga-dsp-debug-tool) | Medium | ₹599 checked; Robokits list the same tool but were showing it pre-order on 2026-09-13. Useful for MCU-side SPI/UART/timing. Use an oscilloscope for CAN physical-layer integrity. |

## 5. Provisional cost envelope

These figures are intentionally broad because actuator shipping/import treatment dominates uncertainty and printed-part fabrication will be quoted separately.

| Area | Rough provisional cost |
|---|---:|
| 6 × DM-J3507-2EC at Foxtech list price | **US$534–570 before shipping/import charges** |
| Offsite printed structure | **Quote separately** |
| Wheels and wheel clamp hardware | **~₹1k–2k** |
| Bearings, journals and fasteners | **~₹2k–4k** |
| MCU, SBC, CAN and IMU | **~₹8k–14k** |
| USB-CAN-FD development interface | **₹13k** checked, for the Linux-capable -B |
| Battery, charger, safety gear and pack harness | **~₹8k–11k** — two packs, an IMAX B6AC, safe bags, the XT90-S, the BMS, balance leads and the series harness |
| Bulk capacitor bank and regen handling | **~₹2k–4k**, excluding the bench source — and **almost none of that is the capacitors**, which are ~₹100 for the pair. The clamp, the contactor and the brake resistor are what carry this figure |
| Wiring, connectors, DC/DC, fuse/E-stop/power hardware | **~₹4k–10k** |

A sensible planning figure for the finished V0 robot and core development electronics is roughly **₹0.9–1.2 lakh before uncertain actuator import/shipping costs and offsite-printing charges**, assuming the motors are acquired near international list price rather than high domestic reseller pricing. Two fewer actuators is the whole of the saving against the walking robot; the rest roughly cancels, because the SBC arrived as the foot sensors left. This is not a procurement quote.

## 6. Immediate procurement recommendation

Buy now / very soon:

1. **2 × DAMIAO DM-J3507-2EC 24 V**, plus 2 or more spare OEM 8-pin power/CAN pigtails asked for on the same order, plus **2 × adapter board** at US$2.30 from Foxtech's cable set page — the dropdown entry reading exactly `SH1.0 3Pin + 8Pin to XT30 + GH1.25 Adapter Cable`, which is section B's table row — and **2 × `GH1.25-3Pin Reverse Cable (300mm)`** at US$0.90 from the same page, the lead from that board out to the debug tool, which nothing else on this bill supplies. The board is not supplied with a bare motor, Foxtech offer no bundle that includes it, and without it the tuning assistant cannot be reached.
2. **1 × Waveshare USB-CAN-FD-B interface** — the -B, not the plain one, which has no Linux driver. ₹12,975 at Robocraze.
3. **2 × WeAct STM32G474CEU6 core boards** — **out of stock at both Indian listings on 2026-09-13**, so this is the line most likely to hold the electronics up.
4. **4 × MCP2562FD-E/P CAN-FD transceivers**, through-hole, with DIP-8 sockets, decoupling capacitors, a sheet of 2.54 mm perfboard, and just **two** 120 Ω termination resistors — the motors terminate the far end of each bus themselves, and four of the six have to be switched OFF.
5. **1–2 × compact BNO085 Nano breakouts**, plus the 26–28 AWG wire and JST-XH crimp kit that lands them, the bus monitor and the 5 V feeds.
6. **1 × four-pack of 80 × 24 mm skate wheels** — cheap, and the adapter cannot be finalised without one to measure.
7. **4 × 6800-2RS bearings** and **4 × Ø10 × 8 mm g6 dowel pins** (MISUMI MSGSS10-8) for the journals.
8. **M3 SHCS**: 100 each of M3 × 6, ×8, ×12 and ×14, plus 1 mm and 2 mm M3 washers. The ×14 is not on an Indian shelf today and 12.9 is a fastener-supplier grade in these lengths, so treat the whole M3 order as one enquiry to a fastener supplier rather than four hobby-shop baskets.
9. **M5 clamp set**: 10 × M5 × 12 SHCS, 10 × Ø30 penny washers, 10 × M5 heat-set inserts. The penny washer comes from a hardware shop and the stocked insert is 8 mm rather than 9.5.
10. **Loctite 638** and **Loctite 243**.
11. **A LiPo safe bag and an IMAX B6AC** — before the first cell arrives, not after. Both were in stock on 2026-09-13; the B6AC had been showing pre-order earlier and is not now.
12. **1 × Daly 6S 24V 20A BMS** — out of stock at the vendor whose outline the pelvis is cut to, and the pelvis cannot be printed until one has been measured. It is a cheap part on a long string.

Buy with the first packs, and not before the pelvis is printed:

The battery hardware is cheap and none of it is a schedule blocker, but four of
its dimensions are cut into printed parts. **Measure a pack, the BMS board, an XT60E-M and an XT60E-F before the pelvis
goes to print**: `cad/electronics.py` reserves 78 × 54 × 36 mm for the packs
with a millimetre of side clearance, and `cad/torso.py` cuts the rear wall to the
XT60E-M's 14.20 × 6.70 nose with its screws 20 mm apart and the XT60E-F's
18.70 × 11.50 body with its screws 25 mm apart, from AMASS's own dimensioned
drawings. **On the XT60E-M, measure how far the nose stands in front of the ears
first.** AMASS's drawing labels only 3.2 mm of nose, which its own proportions and
photograph contradict; the model uses 8.4. If the label is right, that station
does not work as drawn. **The connector figures on this
bill were listing figures until 2026-09-13 and the listing was wrong** — it gave
the XT90E-M a 25 × 16 cutout with 29 mm screw centres against a real 32.4, which
would have been a 182 g reprint rather than a 9 g one. Measure anyway.
Everything else in the battery list can be bought late.

Buy later / after validation:

- the Banana Pi, once the MCU is talking to a motor and the software stack is a real question.
- full XT30 branch-connector quantity after harness routing.
- M2.5 hardware, once a board is in hand and the standoff height is measured.
- the INA226 shunt, once the peak bus current has actually been seen rather than computed.
- final DC/DC converter, fuse rating, DC contactor/switch and regenerative-energy hardware after electrical measurements.

## 7. Design-for-India sourcing rules

1. Prefer **standard metric bearings** readily stocked in India.
2. Prefer a **catalogue part ordered to size** over stock cut to size, and let the **fit class** choose between catalogues — the journal is a g6 dowel pin rather than the stocked DIN 6325 m6 one because m6 is an interference fit in a bearing bore. Still no exotic shoulder bolts.
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
| Support bearing | 2 | **6800-2RS, 10 × 19 × 5 mm** | 5.0 g ea | [IndustryBuying — 6800-2RS reference](https://www.industrybuying.com/special-bearing-monotaro-BEA.SPE.238091927) | Bonded into the pelvis cheek's Ø19.2 bore with Loctite 638, seating against the shoulder of the printed Ø26 boss on the cheek's outer face. That boss's Ø17.5 bore lands on the **outer race only**, clearing the seal and the inner race, and it doubles as the way a pin reaches the bearing to push it out — a bonded seat has no other exit. Buy 2 spares. |
| Journal | 2 | **Ø10 × 8 mm g6 hardened ground dowel pin**, MISUMI MSGSS10-8 | 4.9 g ea | [MISUMI India — MSGSS g6 dowel pins](https://in.misumi-ec.com/vona2/detail/110302390620/) | Seats 2.2 mm into the thigh's output disc, crosses 1 mm of air and runs 4.8 mm into the bearing's 5 mm width, stopping 0.2 mm short of its outer face. Ordered at length rather than cut from shaft stock, and g6 rather than the stocked m6, which would be a press fit into a bearing already bonded into a printed seat. Buy 2 spares. |
| Output screws | 36 | M3 × 6 SHCS provisional, pending first-actuator thread-depth measurement | ~2.8 g per six | [Robu — M3 × 6 set](https://robu.in/product/easymech-set-m3-x-6mm-socket-head-cap-allen-bolt-nut-12-pcs/) | Six joints, six screws each. Also buy M3 × 8 validation stock; see section 10. |
| Stator screws, knee + wheel | 16 | M3 × 14 SHCS + 1 mm washers | Included in fastener mass | **No Indian stock of M3 × 14 on 2026-09-13** — fastener supplier | Through 6 mm limb plate + 3.2 mm rear cover into 4 mm thread. |
| Rear screws, hip pitch | 8 | M3 × 12 SHCS + 2 mm washers | Included in fastener mass | [Indian Hobby Center — M3 × 12](https://www.indianhobbycenter.com/products/m3x12mm-hex-allen-socket-head-ss202-screw-dia-3mm-length-12mm) | Through the pelvis clevis's 3 mm cheek + 3.2 mm rear cover into 4 mm thread. |
| Wheel clamp screw | 2 | **M5 × 12 SHCS** | ~2 g ea with washer and insert | [Robu — EasyMech M5 × 12 set](https://robu.in/product/easymech-m5-x-12mm-chhd-bolt-nut-and-washer-set-25pcs/) | One on each wheel axis. Section 10 says why 12 and not 20. |
| Wheel clamp washer | 2 | **Ø30 × 2 penny washer, Ø5.5 bore** | Included above | **Not stocked by any hobby supplier** — hardware shop; [QuartzComponents — plain M5 flat washer](https://quartzcomponents.com/products/m5-flat-ss-washer-pack-of-4) is what the shelves have, and it is too small | Deliberately oversized: it bridges the millimetre the spigot is held short and lands on the **wheel's** hub face, so the preload crosses the hub rather than the end of a printed spigot. |
| Wheel clamp insert | 2 | **M5 heat-set, Ø6.4 × 9.5 nominal** | Included above | [Robu — M5 × 8 heat-set insert](https://robu.in/product/m5-x-8-mm-brass-heat-set-threaded-round-insert-nut-25-pcs/), 1.5 mm shorter than drawn | Seated flush with the spigot's outer end, in a bore drawn 14 mm deep for the 9.5 mm insert. |
| Board mount screws | 8 | **M3 × 8, self-tapping into printed PA12**, through 3 mm standoffs | Negligible | [QuartzComponents — M3 × 8](https://quartzcomponents.com/products/m3-x-8mm-hex-allen-socket-head-screwpack-of-10) | Four into the pelvis posts under the power-entry board, four into the deck under the controller carrier. **Piloted Ø2.5, not inserted:** a 3 mm deck plate and a 5 mm ledge will not sink a 5.7 mm insert, and the cover bosses have always been self-tapped at the same Ø2.5. `tools/gate_e.py` counts all twelve pilots on the finished pelvis. |
| Deck fixing screws | 4 | **M3 × 10, self-tapping** — down through the deck into the shell's wall ledges | Negligible | [Robu — M3 × 10 set](https://robu.in/product/easymech-set-m3-x-10mm-socket-head-cap-allen-bolt-nut-12-pcs/) | These four hold the whole upper stack. Undo them and the deck, the controller, the SBC and the battery's hold-down come out together. |
| SBC mount inserts | 4 | **M2.5 heat-set brass, Ø3.2 × 4 nominal** | Negligible | [Indian Hobby Center — M2.5 × 4 brass insert](https://www.indianhobbycenter.com/products/m2-5x4mm-brass-threaded-inserts-dia-2-5mm-length-4mm) | In the tops of the deck's four Ø8 posts — the only inserts above the shell floor, and they are there because a 14 mm post has depth for one where a plate does not. |
| SBC mount screws | 4 | M2.5 × 6 | Negligible | [QuartzComponents — M2.5 × 8](https://quartzcomponents.com/products/m2-5-x-8mm-hex-allen-socket-head-ss202-bolt), the nearest stocked length | Into the Banana Pi's Ø2.75 holes, at the top of the deck's four printed posts, which hold the board the 2 mm off the deck its underside microSD slot needs. |
| Rear wall connector screws | 4 + spares | **M2 × 10 SHCS with nuts**, and 4 M2 flat washers — two for the disconnect's ears, two for the charge socket's flange | Negligible, not price-checked | [Robu — EasyMech M2 × 10 SHCS with nuts](https://robu.in/product/easymech-set-m2-x-10mm-socket-head-cap-allen-bolt-nut-12-pcs/) | **The only fasteners on the outside of this robot, and the only M2.** M2 is forced by the disconnect's nuts: they sit 2.25 mm from its body, which an M2 nut clears and an M2.5 fouls. The body then stops the nut turning. Wall between each screw and its cutout: 1.45 mm at the disconnect, 1.7 at the charge socket. |

Printed-part masses, PA12-CF at 1.06 g/cm³, measured from the CAD by `uv run tools/mass.py`:

| Print | Each | Count | Total |
|---|---:|---:|---:|
| Limb, 105 mm, unmirrored — right thigh and left shin | 36.6 g | 2 | 73.2 g |
| Limb, 105 mm, mirrored — left thigh and right shin | 36.6 g | 2 | 73.2 g |
| Wheel adapter — left and right | 14.4 g | 2 | 28.9 g |
| Pelvis shell — both hip clevises, the cover bosses, the bearing-seat bosses, two battery rails, four distribution-board posts, four deck ledges, four strap slots, two BMS card guides, the IMU seat and the rear wall's panel-mount cutouts | 182.8 g | 1 | 182.8 g |
| Torso cover | 53.3 g | 1 | 53.3 g |
| Electronics deck — plate, four SBC posts, two BMS card guides and the cable chase | 32.6 g | 1 | 32.6 g |
| **Printed structure** | | | **444.1 g** |

Both leg segments are 105 mm, so there are only **two distinct limb prints on the robot** and each is printed twice. There is no hip carrier and no foot tray: the first went with hip roll, the second with the ankle. The **electronics deck** is the one part on this robot the pre-migration engine never built, so it is the piece `tools/gate_b.py` has nothing to compare against; the arithmetic behind it is `tools/gate_e.py`'s count of its twelve holes and its cable chase.

With the six actuators, the metal, the wheels, the fasteners, the electronics and a 60 g allowance for the power-entry block, the current model comes to **2 105.9 g against the 2 300 g ceiling**, leaving **194.1 g** of headroom.

**The battery cost 454 g all in**, which is most of what deleting hip roll had bought back: 288 g of cells, 65 g of wiring and mounts, 13 g of distribution board, 66 g of extra pelvis and cover, and 33 g of deck. That is the trade in one line — the robot went from 700 g of margin to 240 in exchange for cutting the umbilical, and for not needing the boom that was supposed to carry it. **Giving everything in that torso a mount cost about a gram in the end, and for a fortnight it cost nine.** The connector panel was 8.6 g of that; deleting it and letting the rear wall carry panel-mount hardware directly gave all of it back, plus 0.4 g of wall where the old apertures were, against 0.5 g out of the deck for the cable chase. What is left on the bill is a 0.1 g IMU seat and 0.8 g of BMS card guides. **Cutting those guides to a chosen board then cost 0.9 g more**: a 33 mm card stood on the bay floor lifts clear of a 4 mm slot before the deck over it can stop it, so the guides rise 7 mm to hang the board 1.5 mm under the deck and the slot opens from a bare PCB to the board's whole 8.2 mm. **Supporting that card at the top as well cost 0.2 g more**, on the deck rather than the pelvis: two more guides on the plate's underside, cut to the same slot, so a card held at one end is held at both. **The BMS itself is a further 45 g**, which since 2026-09-13 is the vendor's catalogue figure rather than a class estimate, and 15 g heavier than the estimate was. Run `uv run tools/mass.py` for the live figure; the headroom is **185 g** as this is written.

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
| Stator plate, knee and wheel | 16 | **M3 × 14** | 1.0 mm | 9.2 mm | 4 mm | 3.8 mm | **no Indian stock, 2026-09-13** |
| Pelvis clevis cheek, hip pitch | 8 | **M3 × 12** | 2.0 mm | 6.2 mm | 4 mm | 3.8 mm | [Indian Hobby Center — M3 × 12](https://www.indianhobbycenter.com/products/m3x12mm-hex-allen-socket-head-ss202-screw-dia-3mm-length-12mm) |
| Wheel axis | 2 | **M5 × 12** | Ø30 × 2.0 | 3.0 mm | 9.5 mm insert | 9.0 mm | [Robu — EasyMech M5 × 12 set](https://robu.in/product/easymech-m5-x-12mm-chhd-bolt-nut-and-washer-set-25pcs/) |

The output-thread depth still needs to be measured on the first physical actuator. If it is really 5 mm, M3 × 8 bottoms at approximately 5.2 mm while M3 × 6 gives only about 3.2 mm engagement. **Buy both M3 × 6 and M3 × 8 initially**, measure the motor, then standardise on whichever gives roughly 4 mm engagement without bottoming.

### Why the wheel screw is 12 mm and not 20

This one was wrong and is worth recording rather than silently fixing. Earlier notes asked for **M5 × 20**, and modelling the screw showed it cannot work. Under the head sit the 2 mm washer and the 1 mm the spigot is deliberately held short of the hub's outer face, and then a **blind** bore: the reach below the head is 15 mm against the pocket as dimensioned and 17 mm against the pocket as actually cut. A 20 mm screw therefore lands on the bottom of the bore before the head ever reaches the washer, and the clamp never sees preload. Measured rather than reasoned: a Ø5 shank 20 mm under the head shares 58.9 mm³ with the printed adapter, which is 3 mm of screw buried in solid plastic.

**M5 × 12** is the standard length that fits both readings. It threads through 9 of the insert's 9.5 mm and stops 3 mm clear of the nominal bore bottom, 5 mm clear of the drawn one.

That clamp is not incidental hardware. **Torque reaches the wheel through the clamped face, not through the spigot**: an M5 at a modest 1 kN preload on the output disc's r11–r18 annulus is worth about 4 Nm of friction against the actuator's 3 Nm peak, where a press fit alone would have depended on how the printed spigot came off the bed.

### Purchase quantity

100 each of M3 × 6, M3 × 8, M3 × 12 and M3 × 14 12.9 SHCS, and 25 of M3 × 10 for the electronics deck; at least 50 each of approximately 1 mm and 2 mm M3 washer stack thicknesses; 10 each of M5 × 12 SHCS, Ø30 penny washers and M5 heat-set inserts. Measure actual washer thickness before relying on the engagement arithmetic.

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
| **Distribution board** | 4 × M3 × 8 self-tapping into four printed pelvis posts, through 3 mm brass standoffs, on the board's **own 45 mm datasheet square** | 4 screws, 4 standoffs |
| Capacitor bank | Soldered to the board's bus copper, plus a cable tie round the cans and a bead of flexible adhesive at each base. **Two 470 µF cans are specified now**, and the four drawn positions stay reserved against a measured answer, so a tie and a bead are still what holds them | tie, adhesive |
| **Battery management system** | **A card in a cage.** Four printed guides, 46 mm apart and cut to one 9 mm slot that takes the board's whole 8.2 mm thickness: two off the cavity floor take its bottom edge 4 mm deep, two off the deck's underside take its top edge 2.5 mm deep, and the deck plate 1.5 mm over that edge is what stops it lifting out. **The guides hang it from the deck rather than standing it on the floor** — on the floor a 33 mm board lifts clear of its slot before the deck stops it. The deck goes on last and comes straight down, so its guides swallow the top edge as it lands, and if the board is not standing where it should the deck will not sit down | foam tape shim |
| Main fuse holder | Double-sided acrylic foam tape to the distribution board's top face, with a tie through the loom beside it | VHB tape |
| INA226 bus monitor | The same tape, on the same face | VHB tape |
| **Matek BEC** | Tape to the **electronics deck's underside**, which is 0.9 mm above where it is drawn. It is the one item in this torso that makes real heat — about 3 W — so check its temperature on the first sustained run before trusting the joint | VHB tape |
| **XT60E-M disconnect** | Bolted through the rear wall by its own two ears, 2 × **M2** × 10 with washers under the heads outside and nuts behind the ears **inside** the shell. Its nose passes through the wall and stands 6 mm proud; the solder tabs stay in the cavity. Above the deck, at z 22. See below | 2 screws, 2 washers, 2 nuts |
| **XT60E-F charge inlet** | The other way round: its flange lies **outside** the wall and its body passes through. 2 × **M2** × 10 with washers under the heads, which sit in the flange's own recesses, and nuts on the inside face | 2 screws, 2 washers, 2 nuts |
| **SMA antenna bulkhead** | Its own thread and nut, clamping the wall on a 6.5 mm hole — now on the far side of the disconnect, at x −8. The u.FL pigtail behind it is a flying lead; tie it clear of the SBC's heatsink | tie mount |
| Pack leads and series harness | Nothing fixes these and nothing should: they are flying leads in the air above the distribution board. Restrain them with adhesive-backed tie mounts once the harness is made up | tie mounts |
| Balance leads, packs to BMS | **Taped flat to the tops of the packs.** This is the only route from the battery bay into the bay gap and it is 3 mm of air — the packs end at z 2 and the deck's underside is at z 5 — so the joined seven-way tail has to lie down, not stand proud, or the deck will not close on it | VHB tape |
| **Electronics deck** | 4 × M3 × 10 self-tapping down through the plate into four printed wall ledges. Undo these four and the deck, both upper boards, the battery's hold-down and the BMS's top guides come out together | 4 screws |
| **Controller carrier** | 4 × M3 × 8 into pilots in the deck, through 3 mm brass standoffs | 4 screws, 4 standoffs |
| WeAct STM32G474 core board | Its own two 20-pin headers into the carrier. **The board has no mounting holes at all** — the vendor STEP was measured and the largest hole in its outline is a 0.9 mm via — so the carrier under it is what gets screwed down | — |
| CAN transceivers, harness bank | DIP-8 sockets soldered to the controller carrier, **clear of the WeAct board's footprint**: the core board stands about 8.5 mm up on its headers inside a 12 mm band and a socketed DIP is about 7 mm tall, so the air under it is not usable. The carrier is 76 × 46 mm and the core board covers 36.5 × 28.4 of it, less one Ø8.6 hole for an SBC post, so there is room beside it and not much to spare | 4 sockets |
| **Banana Pi BPI-M4 Zero** | 4 × M2.5 × 6 into heat-set inserts in the tops of the deck's four printed posts. Those posts **are** the standoff; there is no separate pillar | 4 screws, 4 inserts |
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
than chosen.** Below the deck the rear wall is committed end to end: the bus monitor
lies across its lower half and comes within 12.6 mm of it, and the deck's own wall
ledges stand *on* it between x 46 and 58. A bare prism can thread between those —
which is how an XT90-S and an XT30 fitted down there at all — but the GX16 bushing
that was here could not, because its nut wanted a clear circle 22 mm across. Above
the deck the same wall has 18 to 67 mm of clear depth and nothing standing on it.

| In the wall | Hole | Held by |
|---|---|---|
| **SMA antenna bulkhead**, x −8 | Ø6.5 | its own nut |
| **XT60E-M disconnect** (male), x 18 | 14.7 × 7.2 nose cut | 2 × **M2** at 20 mm centres, nuts inside |
| **XT60E-F charge inlet** (female), x 55.5 | 19.2 × 12.0 body cut | 2 × **M2** at 25 mm centres, nuts inside |

**The two XT60s are a male and a female on purpose.** The loop key is a bridged
female, so it only fits the disconnect; the charger's lead ends in a male, so it
only fits the charge inlet. Two identical males would have let the key go into the
charge port, which is a dead short across the pack, and the charger onto the
disconnect, which stands it in series with the pack and puts about 50 V onto
drivers rated for 30.

**The stations were solved, not laid out.** With the disconnect held, the charge
inlet and antenna were swept across the whole wall against everything in the
cavity. The inlet went as far outboard as its 34 mm flange still lands on the wall,
and the antenna had to cross to the far side of the disconnect, because nothing fits
beyond that flange. The tightest figure is now **6.0 mm from the antenna to the
SBC**, fixed by the bushing's own depth. The thinnest wall is each connector's strip
between its cutout and its screws: 1.45 and 1.7 mm. Move any station and
`tools/gate_f.py` re-measures every pair.

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
| **Acrylic foam tape**, 1 mm × 12 mm | 1 roll | The fuse holder, the bus monitor, the BEC, the IMU, and a shim in each BMS card guide | The ordinary 3M VHB class. Degrease the printed surface — PA12 comes off a machine dusty. The guide slots are cut 9 mm for the BMS board's whole 8.2 mm thickness, and the 0.8 mm is what the shim takes up |
| **Adhesive tie mounts**, ~20 mm | ~10 | The actuator harnesses, the CAN loom and the pack leads | With a tie through each. Nothing printed anchors the looms; they are drawn as chases, not as a routed harness |
| **Cable ties**, 2.5 mm | ~25 | The above, plus the capacitor bank | — |

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
insulate and keep clean rather than a convenience. **So the wall carries two
connectors: the male XT60 loop key that arms the robot, and the female XT60 that
feeds the BMS's charge input with the bus dead.** What plugs into the charge inlet is
a plain 25.2 V constant-current/constant-voltage supply rather than a balance
charger, on a lead ending in a male XT60.

**The two packs are still joined into one 6S string inside the shell** — the same
splice, made in the same place, landing on the BMS's seven-way connector instead of
on a panel socket. Meter it before it ever sees a charger.

**It does not replace the main disconnect.** There is no over-discharge cutoff on
the discharge path, so a robot left switched on will still flatten its own pack,
and a LiPo taken flat is a damaged LiPo. Pull the loop key when the robot is
parked.

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

### Why the disconnect is a loop key and not a switch

This was asked directly in September 2026 — could a torso-mounted switch replace
the main disconnect — and the answer is no, not on its own, for a reason that is
about amps rather than about room.

**Nothing in a 12–16 mm panel bushing will CARRY this bus.** A 16 mm anti-vandal
switch is rated about 2 A at 24 V DC; the best "high current" parts in that shell are
15 A at 24 V. The robot's estimated simultaneous peak is **24 A** — estimated, never
measured, and that is its own problem — so a switch of that class would cap the
machine below what it was designed for. Carrying is the hard requirement: it applies
whenever the robot is on, not only when somebody operates the switch. Breaking 24 A
at 25 V DC is worse again, because there is no zero crossing to help the contacts
part.

**A switch could command the bus instead of carrying it**, and that is the sensible
version of the idea: a small latching switch driving a DC-rated contactor or a
solid-state high-side switch, which is exactly the part the **Motor-power contactor**
row above already says is needed for the E-stop. One device would then serve both.
It is not drawn, because that contactor has never been chosen or sized and has no
home in the CAD — see below.

So the wall keeps a pull-link, and what changed is only how it is held: an eared
XT60E-M bolted through the wall in place of a bare XT90-S bonded into a printed
panel. **Pulling a connector by hand is a disconnect, not an emergency stop**, and
that sentence still stands.

**The contactor row is no longer only about the E-stop.** Dropping to an XT60 in
September 2026 — because no XT90 panel mount fits this torso, see the disconnect
row — took the anti-spark with it, since AMASS make the pre-charge only in the
XT90-S. The pre-charge this robot used to get free with the key now has to come
from somewhere, and the **precharge resistor** already listed as one of the three
parts that travel with the contactor is that somewhere. Until it exists, every
connection of the loop key is an unlimited inrush into the capacitor bank.

### What still has no mount

Two items, and both are honest gaps rather than oversights.

**The capacitor bank is sized provisionally, and not measured.** Two 470 µF 35 V
cans are what the electrical table buys, reasoned from six drivers and a short lead
run rather than read off a scope. Its restraint is still a tie and a bead of
adhesive, because a bank whose count may yet double is not something to design a
clamp to. Measure the bus excursion, then come back here.

**The emergency stop has no home at all.** A 22 mm mushroom switch wants a 22 mm
hole and about 30 mm behind it, and this pelvis has neither to spare. The risk is up
rather than down since the robot started carrying its own energy: on a tether the
bench supply was always the stop of last resort, and on a battery there is no such
thing. This needs solving before multi-motor tests, and it will probably mean
hanging the switch off the outside of the shell rather than finding room inside it.
