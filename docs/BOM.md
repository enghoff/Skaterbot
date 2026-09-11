# Provisional Bill of Materials — India Hobbyist Build

**Status:** revised 2026-09-11 against the **six-motor wheeled CAD**, which is `cad/` on this branch. Until this revision the document described the 8-DOF walking biped; that machine and its BOM now live on the `walking` branch, and nothing below refers to it except where a line says so.  
**Sourcing check:** 2026-08-30 for everything carried over; the wheel and clamp lines added 2026-09-11 have not been price-checked.  
**Project baseline:** 360 mm, six-motor wheeled biped — hip pitch, knee and a driven wheel on each leg — using DAMIAO DM-J3507-2EC actuators. Hip roll and the ankles are deleted, and there are no feet. **It carries its own 6S 2200 mAh battery** and the umbilical is gone; the torso grew from 125 × 68 × 65 mm to 135 × 72 × 86 to hold one, which is where the 21 mm of extra height came from.

This BOM is intentionally split between parts that should be sourced early and commodity parts that should remain flexible until the CAD/electrical design is mature. Purchase links are practical India-oriented sourcing references, not immutable approved vendors. Re-check price, GST, shipping, stock and seller immediately before ordering. Imported prices exclude shipping, customs duty, IGST, payment/FX charges and courier handling unless explicitly stated.

Printed structural parts will be fabricated offsite. The BOM therefore keeps the required material/specification information but does not attempt to source printers, dryers, filament or printed parts.

**One caveat that sits above the whole table.** The 2,300 g ceiling and the actuator size were both derived for the walking robot, and **the wheeled robot's torque envelope has not been re-derived**. The answer does change with wheels. Nothing here should be read as confirming that six DM-J3507s are the right size for this machine; it records what the current CAD is built around.

## What went, and why

Four lines have been deleted outright rather than edited, and they are kept as struck-through rows below so that a reader who remembers them can see where they went rather than wondering whether they were forgotten.

| Deleted | Reason |
|---|---|
| Hip roll and ankle actuators, 2 of each | The wheeled architecture is hip pitch + knee + wheel per leg. Eight actuators became six. |
| Foot pressure sensors (FSR400) | There is no foot. The wheel is the ground contact and it is a bought polyurethane tread. |
| TPU sole / traction parts | Same reason. The tread is part of the bought wheel. |
| Bearing carriers | The one bespoke machined part on the robot, with no supplier. The cheek is bored Ø19.2 and the bearing is bonded into the print instead. |
| Tether / umbilical | The robot carries a battery again. Two 3S packs in series fit where no 6S brick ever did, and deleting hip roll gave back the mass headroom that killed the first pack. |
| Tether boom / gantry | Went with the umbilical, and it is the line worth noticing: it was a rig requirement nobody had designed, hanging a moving unmodelled load on a 1.6 kg biped with a 170 mm track and no hip roll. The battery costs 438 g and removes that problem entirely. |

Two printed parts went with them — the foot trays and the hip carriers — and two arrived: the wheel adapter, and the electronics deck that carries the SBC and the controller over the battery. Section 9 is the current list.

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

| Subsystem | Qty | Current part / specification | Indicative price | Purchase / source link | Risk | When to buy | Notes |
|---|---:|---|---:|---|:---:|---|---|
| **Battery** | 2 + 1 spare | **3S 2200 mAh 35–40C soft-case LiPo, XT60**, ~76 × 33 × 25 mm, ~144 g. Two wired in series make the robot's 6S 2200 mAh, 48.8 Wh pack | **₹1,465** checked (GenX) · ₹1,947 (Bonka) | [Robokits — GenX 3S 2200 mAh](https://robokits.co.in/batteries-chargers/drone-batteries/genx-power-premium-lipo-battery/genxpower-11.1v-lipo-batteries/genx-11.1v-3s-2200mah-40c-80c-premium-lipo-lithium-polymer-battery) · [Robu — 3S range](https://robu.in/product-category/batteries/orange-lipo/3-cell-lipo-11-1v-12-6v/) | 🟠 | **Before any untethered test** | TWO 3S RATHER THAN ONE 6S, and it is a mass decision as much as a packaging one. The same 48.8 Wh in a single 6S brick is 374 g (Gens Ace) to 420 g (GenX) against 288 g for the pair, and every 6S brick is 108–125 mm long against a cavity 130 wide and 67 deep. Buy a matched pair from one batch and keep them together. **Measure one before the pelvis is printed:** `cad/electronics.py` reserves 78 × 54 × 36 mm and the packs have 1 mm of side clearance. |
| **Battery series link** | 1 | XT60 male-to-male, 14 AWG silicone, ~40 mm | ₹45/pair for the connectors | [Robokits — AMASS XT60](https://robokits.co.in/batteries-chargers/plugs-and-connectors/amass-xt60-male-and-female-connector-original) · [Robu — XT60 pigtail](https://robu.in/product/xt60-male-w-12awg-silicon-wire-10cm-1pcsbag) | 🟢 | With the packs | The one item in the power path nobody sells ready-made: two male XT60s back to back. It is what turns two bought 3S packs into this robot's 6S pack, and it lives in the 10.2 mm lead chase between the battery and the power-entry block. |
| **Main disconnect** | 1 pair + 1 spare | **AMASS XT90-S anti-spark**, panel-mounted in the pelvis rear wall | **₹141/pair** checked | [Robokits — AMASS XT90S](https://robokits.co.in/batteries-chargers/plugs-and-connectors/amass-xt90s-anti-spark-connectors-male-female-pair-original) | 🟢 | **With the packs** | Replaces the tether entry, and either a pack or a bench supply plugs into it, so the robot stays bench-runnable. **The anti-spark resistor is the precharge** — without it the first connection welds contacts charging the bulk capacitor bank. `cad/torso.py` cuts the wall to 20.5 × 15.5 mm plus half a millimetre; measure the housing before printing. |
| **Balance-lead extensions** | 2 | JST-XH 3S (4-pin), 20 cm, brought out through the rear wall | ~₹60-class | [Robu — JST-XH 3S extension](https://robu.in/product/jst-xh-3s-wire-extension-20cm-1pcsbag/) | 🟢 | With the packs | Otherwise every charge means taking the lid off, lifting the deck and lifting both boards out with it. |
| **Charge adapter** | 1 | JST-XH 2S–6S balance board | ~₹150-class | [Robu — 2S–6S balance board](https://robu.in/product/jst-xh-balance-board-for-2s-to-6s-battery-packs/) | 🟢 | With the charger | Lets the two 3S packs charge together as one 6S at about 55 W, inside the B6AC's 80. |
| **Cell alarm** | 1–2 | 1S–8S balance-lead voltage checker with buzzer | **₹86** checked | [Robokits — 1–8S checker](https://robokits.co.in/batteries-chargers/accessories/charge-protection-circuit/li-po-li-ion-1-8s-voltage-checker-and-low-voltage-alarm) · [Robu](https://robu.in/product/lipo-battery-voltage-checker-1s-8s-with-buzzer/) | 🟢 | With the packs | Backstop only. **The real protection is a setting:** the DM-J3507's undervoltage threshold is configurable and its floor is 15 V, so six backdrivable motors will drag a 6S pack to destruction unless it is set to about 21.6 V — 3.6 V per cell. That mattered not at all on a bench supply. |
| **Bus monitor** | 1 | **INA226** I²C voltage/current/power monitor, 36 V bus, with an external shunt sized for the bus | TBD | [Robu — INA226 module](https://robu.in/product/ina226-voltage-current-and-power-monitor-module/) | 🟠 | Before the first untethered test | New hardware: the controller has never had a way to read pack state, which did not matter on a tether and does now. **The module's on-board shunt is about ±20 A and this robot's peak is 24**, so it needs an external shunt rather than the module as shipped. It is also what turns the runtime estimate into a number — log bus current through a first stand and a first drive. |
| **Balance charger** | 1 | **IMAX B6AC, 80 W, 1–6S** charge/discharge/storage | **₹2,020** checked (B6AC) · ₹1,358 (B6, DC only) | [Robokits — IMAX B6AC 80 W](https://robokits.co.in/batteries-chargers/chargers/imax-chargers/imax-b6ac-80w-charger-discharger-1-6-cells) · [Robu](https://robu.in/product/imax-b6-80w-6a-charger-discharger-1-6-cells/) | 🟢 | With the packs | One charger covers both packs through the balance board above. Storage-charge them whenever the robot is not being used; a LiPo left full loses capacity. |
| **Charge and storage bag** | 1–2 | Fire-resistant LiPo sack, 30 × 23 cm | **₹419** checked | [Robokits — LiPo safe bag](https://robokits.co.in/index.php?cPath=13_534_555&main_page=product_reviews&products_id=965) · [Robu](https://robu.in/product/large-space-fire-and-water-resistant-lipo-battery-bag/) | 🟢 | **With the packs, not after** | Non-negotiable once there are cells in the building. |
| Actuator power/CAN pigtail | 8–10 | SH1.0 **8-pin** compatible harness, preferably OEM DAMIAO | Usually supplied with actuator | [Foxtech DAMIAO range](https://store.foxtech.com/damiao/) | 🟠 | **Order spares with motors** | Six installed plus spares. Ask for at least two spare known-correct OEM pigtails. Do not assume a generic SH1.0 cable has the right pinout/current capability. |
| Actuator tuning pigtail | 2–3 | SH1.0 **3-pin** tuning cable | Usually supplied with actuator | [Foxtech DAMIAO range](https://store.foxtech.com/damiao/) | 🟠 | With motors | Two or three are sufficient; not required per joint in the finished robot. |
| Realtime MCU dev board | 2 | **WeAct STM32G474CEU6 core board, 36.53 × 28.40 mm** | ~₹0.7k–0.9k class | [Robu — WeAct STM32G474CEU6](https://robu.in/product/weact-studio-long-type-stm32g474ceu6/) | 🟢 | Early | Buy two so one can remain on the bench. **This board has no mounting holes at all** — the vendor STEP was imported and measured, and the largest hole anywhere in its outline is a 0.9 mm via. It hangs off its two 20-pin headers, so the controller carrier underneath it is what actually gets screwed down. The outline above is off that STEP; a shop listing gives 36.3 × 28.1 for the same board. It fits the reserved torso volume; **NUCLEO-G474RE does not fit**. |
| **Single-board computer** | 1 | **Banana Pi BPI-M4 Zero, 65 × 30 mm** | ~₹3k–4k class, not price-checked | [Banana Pi BPI-M4 Zero wiki](https://wiki.banana-pi.org/Banana_Pi_BPI-M4_Zero) | 🟠 | After the MCU is talking to a motor | Chosen 2026-09-11 and drawn into the torso packing, which is what the 16 mm upper band is for. Banana Pi claim Raspberry Pi Zero W form factor and accessory compatibility, so **the mounting holes are inherited from that claim**, taken off Raspberry Pi's Zero 2 W drawing (RP-008358-DS): 3.5 mm in from all four edges, a 58 × 23 pitch, Ø2.75 for M2.5. That is one inference deep — measure a board in hand before cutting a boss to it. The microSD slot is on the **underside**, so it needs about 2 mm of standoff and cannot sit flat on anything. |
| CAN-FD transceiver | 4 | **MCP2542FD-E/SN** / TCAN1042-class, 3.3 V MCU compatible | ~₹100-class per IC | [Mouser India — MCP2542FD-E/SN](https://www.mouser.in/en/ProductDetail/Microchip-Technology/MCP2542FD-E-SN?qs=qdgZG5p0FZ5pNizBl1u80Q%3D%3D) | 🟢 | Early | Two installed + two spare. Bare SOIC IC assumes adapter/PCB integration. |
| Main IMU | 1–2 | **BNO085 Nano breakout** | ~₹2.1k | [Robocraze — BNO085 Nano](https://robocraze.com/products/bno085-9-dof-orientation-imu-sensor-fusion-nano-breakout-board) | 🟢 | Early | Prefer the compact Nano board. The 7Semi-style Nano is approximately 11 × 10 × 6 mm and fits the 22 × 22 × 6 mm reservation; the larger Adafruit breakout does not. At 11 × 10 it is too small to carry a screw, so it is held to the shell floor by its own means. It sits in the clear strip between the two hip saddles, which is the stiffest spot in the pelvis and where an IMU wants to be anyway. |
| USB-CAN-FD debug interface | 1 | Waveshare USB-CAN-FD or DAMIAO-compatible interface | ~₹7k–8k class | [Sharvi — Waveshare USB-CAN-FD](https://sharvielectronics.com/product/usb-can-fd-industrial-grade-can-can-fd-bus-data-analyzer-usb-to-can-fd-adapter-can-can-fd-bus-communication-interface-card-waveshare/) | 🟠 | With first 2 motors | Development/debug tool. Final robot should use MCU-native CAN-FD. Verify exact Waveshare variant if Linux support matters. |
| Main connector | 3–4 pairs | Genuine **AMASS XT60** | **₹54/pair** checked | [Robokits — original AMASS XT60](https://robokits.co.in/batteries-chargers/plugs-and-connectors/amass-xt60-male-and-female-connector-original) | 🟢 | Anytime | Tether disconnect at the robot and supply. |
| Branch connectors | 8–10 pairs provisional | Genuine **AMASS XT30** or locking equivalent | **₹41/pair** checked | [Robokits — original AMASS XT30](https://robokits.co.in/batteries-chargers/accessories/plugs-and-connectors/amass-xt30-male-and-female-connector-original-xt30-f-m?cPath=67_618_623) | 🟢 | After harness design | Six motor branches plus spares. Do not bulk-buy until routing confirms the connector count. |
| Main bus wire | ~3 m robot-side allowance | 14 AWG high-strand silicone wire | ~₹50–70/m class | [Robu — 12–16 AWG silicone wire](https://robu.in/product-category/12-to-16-awg/) | 🟢 | Later | Size against measured simultaneous current and actual cable length. |
| Motor branch wire | 4–6 m | 16–18 AWG high-strand silicone wire | ~₹40–60/m class | [Robu — 12–16 AWG](https://robu.in/product-category/12-to-16-awg/) / [18–22 AWG](https://robu.in/product-category/batteries/wires-and-cables/silicone-wires/18-to-22-awg/) | 🟢 | Later | Final gauge after measured motor current. |
| CAN wiring | ~4 m | Flexible twisted pair ~24–26 AWG | Low | [Robu — 24–30 AWG silicone wire](https://robu.in/product-category/24-to-30-awg/) | 🟢 | Later | Twist a matched pair consistently for early harnesses; move to proper flexible ~120 Ω cable if CAN-FD signal-integrity testing requires it. |
| Logic DC/DC | 1–2 | 24 V bus to 5 V, >=5 A provisional | TBD | **WAIT — final bus/load envelope not frozen** | ⏸️ | After electrical measurements | Must tolerate the supply's full range plus regenerative bus overshoot; do not choose from nominal 24 V alone. The SBC is now a named load on this rail rather than an allowance. Now has a reserved volume, about 26 × 42 × 14 mm on the electronics deck beside the controller, where it can be reached and its heat is under nothing — it is the one item in this torso that makes any. **Choose it for a 6S pack's range rather than for 24 V nominal:** 25.2 V charged down to 19.8 V at the cutoff, plus whatever regeneration puts on top. |
| Main fuse | 2 | Automotive blade fuse + holder, initial ~15–25 A range | ~₹100–300 | [Robu — fuse kits / holders](https://robu.in/product-category/fuse-kits/) | 🟢 | Before powered multi-joint tests | Range revised down with the motor count. Final fuse value follows measured current and fault strategy. |
| Emergency stop | 1 | Latching 22 mm mushroom switch commanding motor-power disconnect | ~₹100-class switch reference | [Robocraze — 22 mm mushroom E-stop](https://robocraze.com/products/ywbl-wh-mushroom-emergency-stop-push-button-switch-22mm) | 🟠 | Before multi-motor tests | Operator control only; do not route the complete motor current through a small panel switch. A wheeled robot can run away in a way a legged one cannot, so this matters more than it did. **Risk is up from green because the robot now carries its own energy.** On a tether the bench supply was the stop of last resort and it was always in reach; there is no such thing on a battery. It also has no home in the CAD — a 22 mm mushroom wants a 22 mm hole and about 30 mm behind it, and this pelvis has neither to spare. |
| Power switch / contactor | 1 | DC-rated switching solution appropriate for 24 V and measured current | TBD | **WAIT — current/inrush/regen architecture not frozen** | ⏸️ | Before full-robot power | Do not substitute an arbitrary AC contactor or automotive relay. **The XT90-S above is now the disconnect that actually gets used** — unplug the pack and the robot is dead. What this line is still for is a switch that can be thrown without opening anything, and it has to break the pack rather than merely signal. |
| Bulk bus capacitance / regen handling | 1 bank | Low-ESR capacitor bank plus clamp/brake-resistor strategy | TBD | **WAIT — size from measured bus excursion** | 🟠 | Before multi-joint powered tests | Was required because a bench source generally cannot absorb regenerated energy, and a wheeled robot regenerates on every deceleration rather than only when a limb is driven by the ground. Reserved volume is 38 × 62 × 30 mm in `cad/electronics.py`, in the lower band above the hip saddles. **Down from red, and not to green.** It was red because a bench supply cannot sink current at all, which made this bank the bus's only home for regenerated energy; the pack is that home now, and what is left for the bank is local decoupling and lead inductance. But nobody has measured the excursion, so nothing here has been sized and the 38 × 62 × 30 mm reservation in `cad/electronics.py` stands at full size until someone does. |
| Heatshrink / braided sleeve / strain relief | Assortment | Flexible harness consumables | ~₹500–1,500 total | [Robu — heat-shrink kits](https://robu.in/product-category/heat-shrink-combos/) / [sleeving](https://robu.in/product-category/heat-shrink-tubing-sleeve/) | 🟢 | Gradually | Critical around moving joints despite low cost. |

### 1b. Mechanical

| Subsystem | Qty | Current part / specification | Indicative price | Purchase / source link | Risk | When to buy | Notes |
|---|---:|---|---:|---|:---:|---|---|
| Actuator | 6 | **DAMIAO DM-J3507-2EC, 24 V** | Foxtech **US$89–95** reference | [Foxtech](https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/) | 🔴 | **Buy 2 now; remaining 4 after actuator/knee validation** | 7:1 low-ratio servo, integrated driver, dual encoders, CAN/CAN-FD and torque feedback/control. Six, not eight: hip pitch, knee and wheel on each leg. The wheel motor is the old ankle motor doing a different job, so the count fell without the part changing. Foxtech package includes the 8-pin power/CAN and 3-pin tuning cables plus STEP model. |
| **Drive wheels** | 2 + 2 spare | **80 × 24 mm inline-skate wheel, ~85A cast PU, bearings removed** | ~₹900 for a 4-pack reference | [Cosco inline wheel range](https://store.cosco.in/products/skating-inline-skate-wheels) · Decathlon/Oxelo 80 mm 84A 4-pack | 🟠 | **With the first wheel adapter print** | The commonest stocked skate size, and the interface is fixed by the bearing rather than by the brand: two 608 seats, Ø22, 24 mm apart. **The two 608 bearings are pulled out and discarded** — the actuator's own output bearing is the only one in the drive. Hub Ø45 and the 20 mm crown radius are representative, not standard: put calipers on the wheel actually bought, because the adapter's Ø22 spigot has to be right first time. A 4-pack gives the pair plus two spares for about the price of one. |
| Support bearings | 2 + 2 spare | **6800-2RS — 10 × 19 × 5 mm** | Local bearing-shop pricing preferred; online references can be much higher | [IndustryBuying — 6800-2RS reference](https://www.industrybuying.com/special-bearing-monotaro-BEA.SPE.238091927) | 🟢 | **Decided; buy anytime** | **Hip pitch is the only straddled joint left**, so two rather than four. Knee and wheel bolt their actuator straight to a flat plate. Prefer SKF/NTN/Koyo/NSK or another reputable equivalent if locally available at a better price. |
| Joint journals | 2 + 2 spare | **Ø10 × 8 mm** ground steel or stainless shaft stub | ~₹500/m shaft-stock reference | [Fastdep — 10 mm linear shaft](https://www.fastdep.in/product/linear-shaft-10mm/) | 🟢 | **Decided** | Cut and face four 8 mm stubs from standard shaft stock. Buy locally if the linked stock is unavailable. |
| ~~Bearing carriers~~ | 0 | **DELETED.** The bearing is bonded straight into the printed cheek, which is bored Ø19.2 for it | — | **No longer purchased — this line had no supplier, which is why it went** | 🟢 | — | Was a bespoke turned aluminium flanged ring, Ø30 × 3 with a Ø36 × 1.5 flange and a Ø19 bore, and the only part of the robot with no catalogue source. The two jobs the carrier did beyond bonding are now done by a printed **Ø26 boss** on the outside of the cheek: a 3 mm cheek cannot seat a 5 mm bearing, so the boss makes up the missing 2 mm of seat and carries 1.5 mm of shoulder past it. The bearing goes in from inboard and seats against that shoulder, which is the direction the journal loads it on assembly. The fit coupon below is still what has to answer for a printed seat. |
| Retaining compound | 1 | **Loctite 638**, 50 ml or equivalent | ~₹713 checked | [Moglix — Loctite 638 50 ml](https://www.moglix.com/loctite-638-50ml-retaining-compound/mp/msni6sci8m0s) | 🟢 | Before assembly | Bonds the bearing directly into the printed cheek, now that the metal carrier is deleted. It also takes up the 0.2 mm seat clearance, which is what removes the interference fit a printed pocket creeps under. The printed shoulder takes the assembly load, so the bond is left holding the bearing against nothing worse than falling back inboard — but that is an argument, not a measurement. Verify polymer compatibility AND seat retention on a coupon before committing to the printed seat. |
| Printed structural parts | 1 robot set | **PA12-CF**, geometry/orientation per CAD and fabrication notes | Offsite fabrication | **Offsite fabrication — no purchase link required** | 🟠 | As CAD releases mature | Six prints: four limbs from two distinct parts, two wheel adapters, the pelvis shell and its cover. Structural prints are outsourced. Supplier must meet the specified PA12-CF material and print-orientation requirements. |
| PETG fit mock-ups | As needed | PETG, 1.75 mm equivalent | Offsite fabrication | **Offsite fabrication — no purchase link required** | 🟢 | As needed | Fit mock-ups only; not structural. The bearing-seat coupon below is the one that matters. |
| ~~TPU sole / traction parts~~ | 0 | **DELETED.** There is no foot; the tread is the bought wheel's own polyurethane | — | — | 🟢 | — | Was a replaceable sole / traction layer under the printed foot tray. If tread wear becomes a problem the answer is another skate wheel, not a printed part. |
| ~~Foot pressure sensors~~ | 0 | **DELETED.** The robot has no feet | — | — | 🟢 | — | Was 8 × FSR400 in a 10 × 10 mm pad in each foot tray. Ground-contact sensing on a wheeled robot, if it is wanted at all, is a different measurement in a different place and is not currently designed. |
| M3 fasteners | 60 installed + spares | 12.9 SHCS in M3 × 6, ×8 validation stock, ×12 and ×14; washers — see section 10 | ~₹500–1,000 total class | [Robu — socket-head cap screws](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | 🟢 | Anytime | Final robot uses 36 output screws, 16 × M3 × 14 and 8 × M3 × 12. Buy M3 × 8 only until the actuator output-thread depth is measured. |
| **M5 wheel clamp set** | 2 + spares | **M5 × 12 SHCS**, **Ø30 × 2 penny washer** (Ø5.5 bore), **M5 heat-set insert Ø6.4 × 9.5** | ~₹300 total class | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) · [Robu — nut inserts](https://robu.in/product-category/nut-insert/) | 🟢 | With the wheels | One per wheel, and this is what actually drives the wheel: the screw pulls the hub flat against the actuator's output disc and torque crosses that clamped face, not the spigot. **12 mm, and the length is not a free choice** — see section 10, where the arithmetic is. The washer is a penny washer; no standard M5 flat washer is Ø30. |
| **M2.5 fasteners** | 4 + spares | M2.5 SHCS and M2.5 brass inserts, provisional | ~₹200 class | [Robu — socket-head cap screws](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | 🟢 | With the SBC | The Banana Pi's Ø2.75 holes are the only M2.5 on the robot. Length follows the standoff height once a board is in hand and the microSD clearance is measured. Do not buy in quantity for four screws. |
| Heat-set inserts | Assortment, 8 M3 installed | M3 brass inserts | ~₹100–500 | [Robu — nut inserts](https://robu.in/product-category/nut-insert/) | 🟢 | Anytime | Covers and light-duty interfaces only; not primary structural load paths. The board mounts are now on this line: the power-entry board and the controller carrier each have four M3 clearance holes, one near each corner, and those land on printed bosses with inserts in them. |
| Threadlocker | 1 | **Loctite 243**, medium strength | ~₹742 checked | [Moglix — Loctite 243 50 ml](https://www.moglix.com/loctite-243-50ml-thread-locker-retaining-compounds/mp/msnvk13yw2y891) | 🟢 | Before assembly | For metal threaded interfaces. |
| **Board standoffs** | 12 + spares | **M3 brass, 6 mm A/F × 3 mm** (8, for the power-entry board and the controller carrier) and **M2.5 × 2 mm** (4, under the SBC) | ~₹300-class assortment | [Robu — standoff and spacer range](https://robu.in/product-category/mechanical-parts-and-tools/standoff-spacers/) | 🟢 | With the boards | The SBC's 2 mm is not a preference: its microSD slot is on the underside and wants the clearance. `cad/electronics.py` draws all twelve. |
| **Battery strap** | 2 | Hook-and-loop cinch strap, ~15 × 250 mm | ~₹150-class | **Local hardware — no fixed SKU** | 🟢 | With the packs | Belt and braces. The packs are actually held by the electronics deck bearing on 3 mm of squeeze above them, which is what `tools/gate_f.py` measures; the straps are for when the deck is off. |

## 2. Source-early shortlist

### A. DAMIAO DM-J3507-2EC actuators — highest priority

**Recommended action:** source **two 24 V units now**, characterize them, and order the remaining four once actuator/knee validation is complete.

- Product: [Foxtech DM-J3507-2EC](https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/)
- Reference price: **US$89–95** before shipping/import charges.
- Listing includes one 8-pin power/CAN cable and one 3-pin tuning cable per motor.
- Ask for at least **two additional 8-pin power/CAN pigtails** with the order.

Six rather than eight, and that is worth stating plainly: nothing about the motor changed. The ankle actuator became the wheel actuator in place, and deleting hip roll took the other two.

### B. Exact DAMIAO connector ecosystem

The motor-side connector is small enough that spare harnesses are disproportionately valuable. The pinout figures show power/CAN on the **8-pin** connector (3 × VCC, 3 × GND, CAN_L, CAN_H) and the debug UART on the **3-pin** connector.

Avoid repeatedly disconnecting the miniature motor-side connector during prototyping; use the larger harness-side connection whenever practical.

### C. Current joint support hardware

The joint stack is frozen enough to buy:

- 2 + 2 spare **6800-2RS, 10 × 19 × 5 mm** bearings.
- 2 + 2 spare **Ø10 × 8 mm** ground-shaft journals.
- No bearing carriers. They were the one machined part here and are deleted; the cheek is bored Ø19.2, a printed boss on its outer face carries the shoulder the bearing seats against, and the bearing is bonded into that. Nothing in this section now needs a machine shop — the journals are cut and faced from standard Ø10 shaft stock.

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
| USB-CAN-FD adapter | 1 | Waveshare USB-CAN-FD or equivalent | [Sharvi — Waveshare USB-CAN-FD](https://sharvielectronics.com/product/usb-can-fd-industrial-grade-can-can-fd-bus-data-analyzer-usb-to-can-fd-adapter-can-can-fd-bus-communication-interface-card-waveshare/) | High | Commission motors independently of final firmware. |
| Digital caliper | 1 | 0.01 mm display class | [Insize India — digital calipers](https://www.insizeindia.in/caliper-1.html) | High | Measure received hardware, printed fits, spacers, journals, **the skate wheel's hub and bore**, and — before the pelvis is printed — a battery pack, an XT90-S housing and a JST-XH shell. Those five are the figures in the CAD with no vendor drawing behind them, and the last three are cut into a wall that cannot be adjusted afterwards. |
| Torque test arm | 1 | Printed/metal lever of accurately measured radius | **Custom / local fabrication** | High | Combine with known masses or a load scale for actuator torque calibration. Still outstanding, and now doubly so: the wheeled robot's torque envelope has not been re-derived. |
| Luggage/load scale | 1 | ~0–20/50 kg range | [Slovic — 50 kg digital luggage scale](https://slovic.com/products/slovic-50kg-digital-luggage-scale-with-lcd-indicator-black-silver-travel-friendly) | Medium | Calibrate against known masses before using for torque measurements. Also the quickest way to settle the 60 g wheel estimate, which is the softest figure in the mass table. |
| IR thermometer / thermocouples | 1+ | Temperature measurement for actuator and joint tests | [Moglix — IR thermometer range](https://www.moglix.com/brands/metravi/measurement-testing/temperature-humidity-meters/ir-thermometers/115153900) | High | Contact thermocouples are preferable when logged data matters. A continuously driven wheel motor is a thermal duty cycle the walking robot never had. |
| Logic analyser | 1 | 8-channel USB logic analyser class | [Robokits — 24 MHz 8-channel analyser](https://robokits.co.in/programmers/logic-analyser/usb-logic-analyzer-24m-8ch-debug-tool?cPath=12) | Medium | Useful for MCU-side SPI/UART/timing. Use an oscilloscope for CAN physical-layer integrity. |

## 5. Provisional cost envelope

These figures are intentionally broad because actuator shipping/import treatment dominates uncertainty and printed-part fabrication will be quoted separately.

| Area | Rough provisional cost |
|---|---:|
| 6 × DM-J3507-2EC at Foxtech list price | **US$534–570 before shipping/import charges** |
| Offsite printed structure | **Quote separately** |
| Wheels and wheel clamp hardware | **~₹1k–2k** |
| Bearings, journals and fasteners | **~₹2k–4k** |
| MCU, SBC, CAN and IMU | **~₹8k–14k** |
| USB-CAN-FD development interface | **~₹8k class** |
| Battery, charger, safety gear and pack harness | **~₹7k–10k** — two packs, an IMAX B6AC, safe bags, the XT90-S, balance leads and the series link |
| Bulk capacitor bank and regen handling | **~₹2k–4k**, excluding the bench source |
| Wiring, connectors, DC/DC, fuse/E-stop/power hardware | **~₹4k–10k** |

A sensible planning figure for the finished V0 robot and core development electronics is roughly **₹0.9–1.2 lakh before uncertain actuator import/shipping costs and offsite-printing charges**, assuming the motors are acquired near international list price rather than high domestic reseller pricing. Two fewer actuators is the whole of the saving against the walking robot; the rest roughly cancels, because the SBC arrived as the foot sensors left. This is not a procurement quote.

## 6. Immediate procurement recommendation

Buy now / very soon:

1. **2 × DAMIAO DM-J3507-2EC 24 V**, plus 2 or more spare OEM 8-pin power/CAN pigtails.
2. **1 × USB-CAN-FD interface**.
3. **2 × WeAct STM32G474CEU6 core boards**.
4. **4 × CAN-FD transceivers**.
5. **1–2 × compact BNO085 Nano breakouts**.
6. **1 × four-pack of 80 × 24 mm skate wheels** — cheap, and the adapter cannot be finalised without one to measure.
7. **4 × 6800-2RS bearings** and short 10 mm ground-shaft stock for four journal stubs.
8. **M3 SHCS**: 100 each of M3 × 6, ×8, ×12 and ×14, plus 1 mm and 2 mm M3 washers.
9. **M5 clamp set**: 10 × M5 × 12 SHCS, 10 × Ø30 penny washers, 10 × M5 heat-set inserts.
10. **Loctite 638** and **Loctite 243**.
11. **A LiPo safe bag and an IMAX B6AC** — before the first cell arrives, not after.

Buy with the first packs, and not before the pelvis is printed:

The battery hardware is cheap and none of it is a schedule blocker, but three of
its dimensions are cut into a part that cannot be adjusted afterwards. **Measure
a pack, an XT90-S housing and a JST-XH shell before the pelvis goes to print**:
`cad/electronics.py` reserves 78 × 54 × 36 mm for the packs with a millimetre of
side clearance, and `cad/torso.py` cuts the rear wall to the connector bodies
plus half a millimetre. Everything else in the battery list can be bought late.

Buy later / after validation:

- the Banana Pi, once the MCU is talking to a motor and the software stack is a real question.
- full XT30 branch-connector quantity after harness routing.
- M2.5 hardware, once a board is in hand and the standoff height is measured.
- the INA226 shunt, once the peak bus current has actually been seen rather than computed.
- final DC/DC converter, fuse rating, DC contactor/switch and regenerative-energy hardware after electrical measurements.

## 7. Design-for-India sourcing rules

1. Prefer **standard metric bearings** readily stocked in India.
2. Prefer **standard precision shaft stock** over exotic shoulder bolts.
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
- WeAct STM32G474 board geometry/reference: [WeActStudio GitHub](https://github.com/WeActStudio/WeActStudio.STM32G474CoreBoard) — the `Hardware/QFN48` STEP is what was measured for the 36.53 × 28.40 outline and the absence of mounting holes.
- Banana Pi BPI-M4 Zero outline and form-factor claim: [Banana Pi wiki](https://wiki.banana-pi.org/Banana_Pi_BPI-M4_Zero)
- Raspberry Pi Zero 2 W mechanical drawing RP-008358-DS, which is where the SBC's inherited hole pattern comes from: [Raspberry Pi documentation](https://datasheets.raspberrypi.com/rpizero2/raspberry-pi-zero-2-w-mechanical-drawing.pdf)
- Inline-skate wheel candidates checked 2026-08-31: [Cosco India inline wheel range](https://store.cosco.in/products/skating-inline-skate-wheels), and a Decathlon/Oxelo 80 mm 84A four-pack at ₹899 at the time of review.
- 608 bearing interface, 8 × 22 × 7 mm (ISO 15 / ABEC 608), which is what fixes the wheel's Ø22 seats and its 24 mm width.
- ~~FSR400/FSR402 family geometry~~ — no longer relevant; the foot is deleted.

## 9. Current joint hardware and printed parts

**Hip pitch is the only joint with far-side support.** Knee and wheel bolt the flat limb plate directly to the actuator's rear cover.

| Item | Installed qty | Current specification | Estimated mass | Purchase / source link | Notes |
|---|---:|---|---:|---|---|
| Support bearing | 2 | **6800-2RS, 10 × 19 × 5 mm** | 5.0 g ea | [IndustryBuying — 6800-2RS reference](https://www.industrybuying.com/special-bearing-monotaro-BEA.SPE.238091927) | Bonded into the pelvis cheek's Ø19.2 bore with Loctite 638, seating against the shoulder of the printed Ø26 boss on the cheek's outer face. That boss's Ø17.5 bore lands on the **outer race only**, clearing the seal and the inner race, and it doubles as the way a pin reaches the bearing to push it out — a bonded seat has no other exit. Buy 2 spares. |
| Journal | 2 | **Ø10 × 8 mm** hardened/ground steel | 4.9 g ea | [Fastdep — 10 mm shaft stock](https://www.fastdep.in/product/linear-shaft-10mm/) | Seats 2.2 mm into the thigh's output disc. Cut and face from standard shaft stock; buy 2 spare stubs. |
| ~~Bearing carrier~~ | 0 | **DELETED** — the front cheek is bored Ø19.2 and the bearing is bonded into a printed seat | — | — | Was 6.4 g of turned aluminium apiece. Removing the pair takes 12.8 g off the robot and puts 4.7 g of PA12 back into the two cheeks — material returned by the smaller bore, plus the boss described below — so the robot is 7.2 g lighter at 1 599.4 g. |
| Output screws | 36 | M3 × 6 SHCS provisional, pending first-actuator thread-depth measurement | ~2.8 g per six | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | Six joints, six screws each. Also buy M3 × 8 validation stock; see section 10. |
| Stator screws, knee + wheel | 16 | M3 × 14 SHCS + 1 mm washers | Included in fastener mass | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | Through 6 mm limb plate + 3.2 mm rear cover into 4 mm thread. |
| Rear screws, hip pitch | 8 | M3 × 12 SHCS + 2 mm washers | Included in fastener mass | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | Through the pelvis clevis's 3 mm cheek + 3.2 mm rear cover into 4 mm thread. |
| Wheel clamp screw | 2 | **M5 × 12 SHCS** | ~2 g ea with washer and insert | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | One on each wheel axis. Section 10 says why 12 and not 20. |
| Wheel clamp washer | 2 | **Ø30 × 2 penny washer, Ø5.5 bore** | Included above | [Robu — washers](https://robu.in/product-category/washer/) | Deliberately oversized: it bridges the millimetre the spigot is held short and lands on the **wheel's** hub face, so the preload crosses the hub rather than the end of a printed spigot. |
| Wheel clamp insert | 2 | **M5 heat-set, Ø6.4 × 9.5 nominal** | Included above | [Robu — nut inserts](https://robu.in/product-category/nut-insert/) | Seated flush with the spigot's outer end, in a bore drawn 14 mm deep for the 9.5 mm insert. |
| Board mount screws | 8 | **M3 × 8, self-tapping into printed PA12**, through 3 mm standoffs | Negligible | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | Four into the pelvis posts under the power-entry board, four into the deck under the controller carrier. **Piloted Ø2.5, not inserted:** a 3 mm deck plate and a 5 mm ledge will not sink a 5.7 mm insert, and the cover bosses have always been self-tapped at the same Ø2.5. `tools/gate_e.py` counts all twelve pilots on the finished pelvis. |
| Deck fixing screws | 4 | **M3 × 10, self-tapping** — down through the deck into the shell's wall ledges | Negligible | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | These four hold the whole upper stack. Undo them and the deck, the controller, the SBC and the battery's hold-down come out together. |
| SBC mount inserts | 4 | **M2.5 heat-set brass, Ø3.2 × 4 nominal** | Negligible | [Robu — nut inserts](https://robu.in/product-category/nut-insert/) | In the tops of the deck's four Ø8 posts — the only inserts above the shell floor, and they are there because a 14 mm post has depth for one where a plate does not. |
| SBC mount screws | 4 | M2.5 × 6 | Negligible | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | Into the Banana Pi's Ø2.75 holes, on 2 mm standoffs that clear the underside microSD slot. |

Printed-part masses, PA12-CF at 1.06 g/cm³, measured from the CAD by `uv run tools/mass.py`:

| Print | Each | Count | Total |
|---|---:|---:|---:|
| Limb, 105 mm, unmirrored — right thigh and left shin | 36.6 g | 2 | 73.2 g |
| Limb, 105 mm, mirrored — left thigh and right shin | 36.6 g | 2 | 73.2 g |
| Wheel adapter — left and right | 14.4 g | 2 | 28.9 g |
| Pelvis shell — both hip clevises, the cover bosses, the bearing-seat bosses, two battery rails, four board posts and four deck ledges | 175.7 g | 1 | 175.7 g |
| Torso cover | 40.6 g | 1 | 40.6 g |
| Electronics deck — plate and four SBC posts | 29.1 g | 1 | 29.1 g |
| **Printed structure** | | | **420.8 g** |

Both leg segments are 105 mm, so there are only **two distinct limb prints on the robot** and each is printed twice. There is no hip carrier and no foot tray: the first went with hip roll, the second with the ankle. The **electronics deck** is new, and it is the only part on this robot the pre-migration engine never built — so it is the one piece `tools/gate_b.py` has nothing to compare against, and the only arithmetic behind it is `tools/gate_e.py`'s count of its twelve holes.

With the six actuators, the metal, the wheels, the fasteners, the electronics and a 60 g allowance for the power-entry block, the current model comes to **2 044.6 g against the 2 300 g ceiling**, leaving **255.4 g** of headroom.

**The battery cost 438 g all in**, which is most of what deleting hip roll had bought back: 288 g of cells, 85 g of wiring and mounts, 48 g of extra pelvis and 29 g of deck. That is the trade in one line — the robot went from 700 g of margin to 255 in exchange for cutting the umbilical, and for not needing the boom that was supposed to carry it.

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
| Output circle, all 6 rotor ends | 36 | **M3 × 6** provisional | none, counterbored | 2.8 mm | ~5 mm unverified | 3.2 mm | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) |
| Stator plate, knee and wheel | 16 | **M3 × 14** | 1.0 mm | 9.2 mm | 4 mm | 3.8 mm | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) |
| Pelvis clevis cheek, hip pitch | 8 | **M3 × 12** | 2.0 mm | 6.2 mm | 4 mm | 3.8 mm | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) |
| Wheel axis | 2 | **M5 × 12** | Ø30 × 2.0 | 3.0 mm | 9.5 mm insert | 9.0 mm | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) |

The output-thread depth still needs to be measured on the first physical actuator. If it is really 5 mm, M3 × 8 bottoms at approximately 5.2 mm while M3 × 6 gives only about 3.2 mm engagement. **Buy both M3 × 6 and M3 × 8 initially**, measure the motor, then standardise on whichever gives roughly 4 mm engagement without bottoming.

### Why the wheel screw is 12 mm and not 20

This one was wrong and is worth recording rather than silently fixing. Earlier notes asked for **M5 × 20**, and modelling the screw showed it cannot work. Under the head sit the 2 mm washer and the 1 mm the spigot is deliberately held short of the hub's outer face, and then a **blind** bore: the reach below the head is 15 mm against the pocket as dimensioned and 17 mm against the pocket as actually cut. A 20 mm screw therefore lands on the bottom of the bore before the head ever reaches the washer, and the clamp never sees preload. Measured rather than reasoned: a Ø5 shank 20 mm under the head shares 58.9 mm³ with the printed adapter, which is 3 mm of screw buried in solid plastic.

**M5 × 12** is the standard length that fits both readings. It threads through 9 of the insert's 9.5 mm and stops 3 mm clear of the nominal bore bottom, 5 mm clear of the drawn one.

That clamp is not incidental hardware. **Torque reaches the wheel through the clamped face, not through the spigot**: an M5 at a modest 1 kN preload on the output disc's r11–r18 annulus is worth about 4 Nm of friction against the actuator's 3 Nm peak, where a press fit alone would have depended on how the printed spigot came off the bed.

### Purchase quantity

100 each of M3 × 6, M3 × 8, M3 × 12 and M3 × 14 12.9 SHCS; at least 50 each of approximately 1 mm and 2 mm M3 washer stack thicknesses; 10 each of M5 × 12 SHCS, Ø30 penny washers and M5 heat-set inserts. Measure actual washer thickness before relying on the engagement arithmetic.

### Mass, and a known discrepancy

The installed steel fastener schedule plus washers works out around **68 g of M3** for six joints — the ~90 g estimated for eight, pro-rated — plus about **6 g** for the two wheel clamps, so roughly **74 g** in total. `tools/mass_budget.toml` carries **51 g**, which is the older 60 g eight-joint allowance pro-rated to six plus the clamps, so the table is about **23 g light**. It does not threaten the 2.3 kg ceiling, but the allowance should be raised rather than left as an untracked discrepancy.
