# Provisional Bill of Materials — India Hobbyist Build

**Status:** revised 2026-08-30 against the current flat-plate limb CAD. Historical knee-module and carbon-tube BOM sections have been removed; this document describes the current build only.  
**Sourcing check:** 2026-08-30  
**Project baseline:** 380 mm, 8-DOF torque-controlled biped using DAMIAO DM-J3507-2EC actuators.

This BOM is intentionally split between parts that should be sourced early and commodity parts that should remain flexible until the CAD/electrical design is mature. Purchase links are practical India-oriented sourcing references, not immutable approved vendors. Re-check price, GST, shipping, stock and seller immediately before ordering. Imported prices exclude shipping, customs duty, IGST, payment/FX charges and courier handling unless explicitly stated.

Printed structural parts will be fabricated offsite. The BOM therefore keeps the required material/specification information but does not attempt to source printers, dryers, filament or printed parts.

## Sourcing risk legend

- 🔴 **High** — specialist/imported; can become a schedule blocker. Source early.
- 🟠 **Medium** — available, but exact variant/geometry may have lead-time or compatibility issues.
- 🟢 **Low** — commodity or readily available from Indian suppliers.
- ⏸️ **WAIT** — design/test dependency is not frozen; do not select a product merely to complete the BOM.

## 1. Core BOM

| Subsystem | Qty | Current part / specification | Indicative price | Purchase / source link | Risk | When to buy | Notes |
|---|---:|---|---:|---|:---:|---|---|
| Actuator | 8 | **DAMIAO DM-J3507-2EC, 24 V** | Foxtech **US$89–95** reference | [Foxtech](https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/) | 🔴 | **Buy 2 now; remaining 6 after actuator/knee validation** | 7:1 low-ratio servo, integrated driver, dual encoders, CAN/CAN-FD and torque feedback/control. Foxtech package includes the 8-pin power/CAN and 3-pin tuning cables plus STEP model. |
| Actuator power/CAN pigtail | 10–12 | SH1.0 **8-pin** compatible harness, preferably OEM DAMIAO | Usually supplied with actuator | [Foxtech DAMIAO range](https://store.foxtech.com/damiao/) | 🟠 | **Order spares with motors** | Ask for at least two spare known-correct OEM pigtails. Do not assume a generic SH1.0 cable has the right pinout/current capability. |
| Actuator tuning pigtail | 2–3 | SH1.0 **3-pin** tuning cable | Usually supplied with actuator | [Foxtech DAMIAO range](https://store.foxtech.com/damiao/) | 🟠 | With motors | Two or three are sufficient; not required per joint in the finished robot. |
| USB-CAN-FD debug interface | 1 | Waveshare USB-CAN-FD or DAMIAO-compatible interface | ~₹7k–8k class | [Sharvi — Waveshare USB-CAN-FD](https://sharvielectronics.com/product/usb-can-fd-industrial-grade-can-can-fd-bus-data-analyzer-usb-to-can-fd-adapter-can-can-fd-bus-communication-interface-card-waveshare/) | 🟠 | With first 2 motors | Development/debug tool. Final robot should use MCU-native CAN-FD. Verify exact Waveshare variant if Linux support matters. |
| Realtime MCU dev board | 2 | **WeAct STM32G474CEU6 core board, 36.3 × 28.1 mm** | ~₹0.7k–0.9k class | [Robu — WeAct STM32G474CEU6](https://robu.in/product/weact-studio-long-type-stm32g474ceu6/) | 🟢 | Early | Buy two so one can remain on the bench. The compact WeAct board fits the reserved torso volume; **NUCLEO-G474RE does not fit**. |
| CAN-FD transceiver | 4 | **MCP2542FD-E/SN** / TCAN1042-class, 3.3 V MCU compatible | ~₹100-class per IC | [Mouser India — MCP2542FD-E/SN](https://www.mouser.in/en/ProductDetail/Microchip-Technology/MCP2542FD-E-SN?qs=qdgZG5p0FZ5pNizBl1u80Q%3D%3D) | 🟢 | Early | Two installed + two spare. Bare SOIC IC assumes adapter/PCB integration. |
| Main IMU | 1–2 | **BNO085 Nano breakout** | ~₹2.1k | [Robocraze — BNO085 Nano](https://robocraze.com/products/bno085-9-dof-orientation-imu-sensor-fusion-nano-breakout-board) | 🟢 | Early | Prefer the compact Nano board. The 7Semi-style Nano is approximately 11 × 10 × 6 mm and fits the 22 × 22 × 6 mm reservation; the larger Adafruit breakout does not. |
| Printed structural parts | 1 robot set | **PA12-CF**, geometry/orientation per CAD and fabrication notes | Offsite fabrication | **Offsite fabrication — no purchase link required** | 🟠 | As CAD releases mature | Structural prints are outsourced. Supplier must meet the specified PA12-CF material and print-orientation requirements. |
| PETG fit mock-ups | As needed | PETG, 1.75 mm equivalent | Offsite fabrication | **Offsite fabrication — no purchase link required** | 🟢 | As needed | Fit mock-ups only; not structural. |
| TPU sole / traction parts | As needed | TPU ~95A | Offsite fabrication | **Offsite fabrication — no purchase link required** | 🟢 | Later | Replaceable sole / traction layer. |
| Support bearings | 4 + 2 spare | **6800-2RS — 10 × 19 × 5 mm** | Local bearing-shop pricing preferred; online references can be much higher | [IndustryBuying — 6800-2RS reference](https://www.industrybuying.com/special-bearing-monotaro-BEA.SPE.238091927) | 🟢 | **Decided; buy anytime** | Only hip roll and hip pitch are straddled. Prefer SKF/NTN/Koyo/NSK or another reputable equivalent if locally available at a better price. |
| Joint journals | 4 + 2 spare | **Ø10 × 8 mm** ground steel or stainless shaft stub | ~₹500/m shaft-stock reference | [Fastdep — 10 mm linear shaft](https://www.fastdep.in/product/linear-shaft-10mm/) | 🟢 | **Decided** | Cut and face six 8 mm stubs from standard shaft stock. Buy locally if the linked stock is unavailable. |
| Bearing carriers | 4 + 2 spare | Aluminium flanged ring, Ø30 × 3 with Ø36 × 1.5 flange, Ø19 bore | ~₹150–400 ea estimate | **Local machine shop / turned part — no useful retail SKU** | 🟠 | After fit coupon | This is the only bespoke metal part in the joint stack. Get a quote before committing to the exact carrier architecture. |
| Retaining compound | 1 | **Loctite 638**, 50 ml or equivalent | ~₹713 checked | [Moglix — Loctite 638 50 ml](https://www.moglix.com/loctite-638-50ml-retaining-compound/mp/msni6sci8m0s) | 🟢 | Before assembly | Bonds the metal bearing carrier into the printed cheek. Verify polymer compatibility on a coupon. |
| M3 fasteners | 80 installed + spares | 12.9 SHCS in M3 × 6, ×8 validation stock, ×12 and ×14; washers — see section 10 | ~₹500–1,000 total class | [Robu — socket-head cap screws](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | 🟢 | Anytime | Final robot uses 48 output screws, 16 × M3 × 14 and 16 × M3 × 12. Buy M3 × 8 only until the actuator output-thread depth is measured. |
| Heat-set inserts | Assortment | M3 brass inserts | ~₹100–500 | [Robu — nut inserts](https://robu.in/product-category/nut-insert/) | 🟢 | Anytime | Covers/light-duty interfaces only; not primary structural load paths. |
| Threadlocker | 1 | **Loctite 243**, medium strength | ~₹742 checked | [Moglix — Loctite 243 50 ml](https://www.moglix.com/loctite-243-50ml-thread-locker-retaining-compounds/mp/msnvk13yw2y891) | 🟢 | Before assembly | For metal threaded interfaces. |
| Foot pressure sensors | 10 | **FSR400** — 8 installed + 2 spare | ~₹208 ea checked | [Aryabot — FSR400](https://aryabot.in/sensors/load-pressure-force-flex-sensor/) | 🟢 | Later | Correct small sensor family for the 10 × 10 mm foot-pad geometry. The larger FSR402 does not fit. Load path into the sensor still needs physical validation. |
| Tether / umbilical | 1, about 3 m | 2 × 14 AWG silicone power + 24 AWG twisted CAN pair, braided sleeve, ~12 mm OD | ~₹800–2,000 made up | [Robu — 12–16 AWG silicone wire](https://robu.in/product-category/12-to-16-awg/) + [24–30 AWG wire](https://robu.in/product-category/24-to-30-awg/) + [sleeving](https://robu.in/product-category/heat-shrink-tubing-sleeve/) | 🟠 | Before powered standing tests | Make the cable and measure the real bundle OD before printing/finalising the pelvis entry feature. Voltage drop must be checked against the actual actuator voltage window. |
| Tether boom / gantry | 1 | Overhead arm or spring-balancer arrangement carrying cable weight | Shop-built | **Local fabrication / hardware — no fixed SKU** | 🟠 | Before powered standing tests | Prevents the umbilical from becoming a moving external load on the robot. |
| Main connector | 3–4 pairs | Genuine **AMASS XT60** | **₹54/pair** checked | [Robokits — original AMASS XT60](https://robokits.co.in/batteries-chargers/plugs-and-connectors/amass-xt60-male-and-female-connector-original) | 🟢 | Anytime | Tether disconnect at the robot and supply. |
| Branch connectors | 10–12 pairs provisional | Genuine **AMASS XT30** or locking equivalent | **₹41/pair** checked | [Robokits — original AMASS XT30](https://robokits.co.in/batteries-chargers/accessories/plugs-and-connectors/amass-xt30-male-and-female-connector-original-xt30-f-m?cPath=67_618_623) | 🟢 | After harness design | Do not bulk-buy until routing confirms the connector count. |
| Main bus wire | ~3 m robot-side allowance | 14 AWG high-strand silicone wire | ~₹50–70/m class | [Robu — 12–16 AWG silicone wire](https://robu.in/product-category/12-to-16-awg/) | 🟢 | Later | Size against measured simultaneous current and actual cable length. |
| Motor branch wire | 5–8 m | 16–18 AWG high-strand silicone wire | ~₹40–60/m class | [Robu — 12–16 AWG](https://robu.in/product-category/12-to-16-awg/) / [18–22 AWG](https://robu.in/product-category/batteries/wires-and-cables/silicone-wires/18-to-22-awg/) | 🟢 | Later | Final gauge after measured motor current. |
| CAN wiring | ~5 m | Flexible twisted pair ~24–26 AWG | Low | [Robu — 24–30 AWG silicone wire](https://robu.in/product-category/24-to-30-awg/) | 🟢 | Later | Twist a matched pair consistently for early harnesses; move to proper flexible ~120 Ω cable if CAN-FD signal-integrity testing requires it. |
| Logic DC/DC | 1–2 | 24 V bus to 5 V, >=5 A provisional | TBD | **WAIT — final bus/load envelope not frozen** | ⏸️ | After electrical measurements | Must tolerate the supply's full range plus regenerative bus overshoot; do not choose from nominal 24 V alone. |
| Main fuse | 2 | Automotive blade fuse + holder, initial ~20–30 A range | ~₹100–300 | [Robu — fuse kits / holders](https://robu.in/product-category/fuse-kits/) | 🟢 | Before powered multi-joint tests | Final fuse value follows measured current and fault strategy. |
| Emergency stop | 1 | Latching 22 mm mushroom switch commanding motor-power disconnect | ~₹100-class switch reference | [Robocraze — 22 mm mushroom E-stop](https://robocraze.com/products/ywbl-wh-mushroom-emergency-stop-push-button-switch-22mm) | 🟢 | Before multi-motor tests | Operator control only; do not route the complete motor current through a small panel switch. |
| Power switch / contactor | 1 | DC-rated switching solution appropriate for 24 V and measured current | TBD | **WAIT — current/inrush/regen architecture not frozen** | ⏸️ | Before full-robot power | Do not substitute an arbitrary AC contactor or automotive relay. |
| Bulk bus capacitance / regen handling | 1 bank | Low-ESR capacitor bank plus clamp/brake-resistor strategy | TBD | **WAIT — size from measured bus excursion** | 🔴 | Before multi-joint powered tests | Required because the tether/bench source generally cannot absorb regenerated energy. Reserved volume is 38 × 62 × 30 mm in `payload_envelopes.kcl`. |
| Heatshrink / braided sleeve / strain relief | Assortment | Flexible harness consumables | ~₹500–1,500 total | [Robu — heat-shrink kits](https://robu.in/product-category/heat-shrink-combos/) / [sleeving](https://robu.in/product-category/heat-shrink-tubing-sleeve/) | 🟢 | Gradually | Critical around moving joints despite low cost. |

## 2. Source-early shortlist

### A. DAMIAO DM-J3507-2EC actuators — highest priority

**Recommended action:** source **two 24 V units now**, characterize them, and order the remaining six once actuator/knee validation is complete.

- Product: [Foxtech DM-J3507-2EC](https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/)
- Reference price: **US$89–95** before shipping/import charges.
- Listing includes one 8-pin power/CAN cable and one 3-pin tuning cable per motor.
- Ask for at least **two additional 8-pin power/CAN pigtails** with the order.

### B. Exact DAMIAO connector ecosystem

The motor-side connector is small enough that spare harnesses are disproportionately valuable. The pinout figures show power/CAN on the **8-pin** connector (3 × VCC, 3 × GND, CAN_L, CAN_H) and the debug UART on the **3-pin** connector.

Avoid repeatedly disconnecting the miniature motor-side connector during prototyping; use the larger harness-side connection whenever practical.

### C. Current joint support hardware

The joint stack is now frozen enough to buy:

- 4 + 2 spare **6800-2RS, 10 × 19 × 5 mm** bearings.
- 4 + 2 spare **Ø10 × 8 mm** ground-shaft journals.
- 4 + 2 spare flanged aluminium bearing carriers, after obtaining a local machining quote.

Only hip roll and hip pitch are straddled. Knee and ankle bolt their limb plate directly to the actuator and therefore do not use the far bearing/journal/carrier set.

## 3. Components that should not constrain the CAD

These are readily sourced enough in India that the design should select them on engineering merit while staying in common families:

- M3 fasteners
- 6800-series bearings
- silicone wire
- XT30 / XT60 connectors
- FSR sensors
- STM32 MCUs / compact development boards
- CAN transceivers
- buck regulators
- fuses
- E-stop switches
- heatshrink and cable sleeve

Avoid saving a few grams by specifying a rare bearing or fastener that creates an import dependency.

## 4. Development-only equipment

Printed-part production equipment is intentionally omitted because fabrication is handled offsite.

| Item | Qty | Current requirement | Purchase / source link | Priority | Notes |
|---|---:|---|---|---|---|
| Bench DC supply / source | 1 | 24 V-class source sized deliberately for robot testing; whole-robot simultaneous peak is near 32 A and regeneration must be handled | **WAIT — source architecture must be selected with regen handling** | **Critical** | A 30 V / 10 A bench supply is useful for commissioning but is not a full-robot source. Most supplies cannot sink regenerated current. |
| USB-CAN-FD adapter | 1 | Waveshare USB-CAN-FD or equivalent | [Sharvi — Waveshare USB-CAN-FD](https://sharvielectronics.com/product/usb-can-fd-industrial-grade-can-can-fd-bus-data-analyzer-usb-to-can-fd-adapter-can-can-fd-bus-communication-interface-card-waveshare/) | High | Commission motors independently of final firmware. |
| Digital caliper | 1 | 0.01 mm display class | [Insize India — digital calipers](https://www.insizeindia.in/caliper-1.html) | High | Measure received hardware, printed fits, spacers, journals and tether OD. |
| Torque test arm | 1 | Printed/metal lever of accurately measured radius | **Custom / local fabrication** | High | Combine with known masses or a load scale for actuator torque calibration. |
| Luggage/load scale | 1 | ~0–20/50 kg range | [Slovic — 50 kg digital luggage scale](https://slovic.com/products/slovic-50kg-digital-luggage-scale-with-lcd-indicator-black-silver-travel-friendly) | Medium | Calibrate against known masses before using for torque measurements. |
| IR thermometer / thermocouples | 1+ | Temperature measurement for actuator and joint tests | [Moglix — IR thermometer range](https://www.moglix.com/brands/metravi/measurement-testing/temperature-humidity-meters/ir-thermometers/115153900) | High | Contact thermocouples are preferable when logged data matters. |
| Logic analyser | 1 | 8-channel USB logic analyser class | [Robokits — 24 MHz 8-channel analyser](https://robokits.co.in/programmers/logic-analyser/usb-logic-analyzer-24m-8ch-debug-tool?cPath=12) | Medium | Useful for MCU-side SPI/UART/timing. Use an oscilloscope for CAN physical-layer integrity. |

## 5. Provisional cost envelope

These figures are intentionally broad because actuator shipping/import treatment dominates uncertainty and printed-part fabrication will be quoted separately.

| Area | Rough provisional cost |
|---|---:|
| 8 × DM-J3507-2EC at Foxtech list price | **US$712–760 before shipping/import charges** |
| Offsite printed structure | **Quote separately** |
| Bearings, journals, carriers and fasteners | **~₹3k–6k** |
| MCU, CAN, IMU and foot sensors | **~₹6k–12k** |
| USB-CAN-FD development interface | **~₹8k class** |
| Tether, boom and bulk capacitor bank | **~₹3k–6k**, excluding the bench source |
| Wiring, connectors, DC/DC, fuse/E-stop/power hardware | **~₹4k–10k** |

A sensible planning figure for the finished V0 robot and core development electronics remains roughly **₹1.0–1.3 lakh before uncertain actuator import/shipping costs and offsite-printing charges**, assuming the motors are acquired near international list price rather than high domestic reseller pricing. This is not a procurement quote.

## 6. Immediate procurement recommendation

Buy now / very soon:

1. **2 × DAMIAO DM-J3507-2EC 24 V**, plus 2 or more spare OEM 8-pin power/CAN pigtails.
2. **1 × USB-CAN-FD interface**.
3. **2 × WeAct STM32G474CEU6 core boards**.
4. **4 × CAN-FD transceivers**.
5. **1–2 × compact BNO085 Nano breakouts**.
6. **6 × 6800-2RS bearings** and short 10 mm ground-shaft stock for six journal stubs.
7. **M3 SHCS**: 100 each of M3 × 6, ×8, ×12 and ×14, plus 1 mm and 2 mm M3 washers.
8. **Loctite 638** and **Loctite 243**.

Buy later / after validation:

- 10 × FSR400 when the foot load path is ready to prototype.
- final tether conductor gauge/length after voltage-drop and drag checks.
- full XT30 branch-connector quantity after harness routing.
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

## 8. Engineering source references

- DAMIAO DM-J3507-2EC product / STEP source: [Foxtech](https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/)
- WeAct STM32G474 board geometry/reference: [WeActStudio GitHub](https://github.com/WeActStudio/WeActStudio.STM32G474CoreBoard)
- FSR400/FSR402 family geometry reference: [Interlink FSR datasheet mirror](https://cdn.sparkfun.com/assets/8/a/1/2/0/2010-10-26-DataSheet-FSR402-Layout2.pdf)

## 9. Current joint hardware

Only hip roll and hip pitch use the far-side bearing/journal/carrier support. Knee and ankle bolt the flat limb plate directly to the actuator.

| Item | Installed qty | Current specification | Estimated mass | Purchase / source link | Notes |
|---|---:|---|---:|---|---|
| Support bearing | 4 | **6800-2RS, 10 × 19 × 5 mm** | 5.0 g ea | [IndustryBuying — 6800-2RS reference](https://www.industrybuying.com/special-bearing-monotaro-BEA.SPE.238091927) | Buy 2 spares. Prefer reputable local bearing stock if cheaper. |
| Journal | 4 | **Ø10 × 8 mm** hardened/ground steel | 4.9 g ea | [Fastdep — 10 mm shaft stock](https://www.fastdep.in/product/linear-shaft-10mm/) | Cut and face from standard shaft stock; buy 2 spare stubs. |
| Bearing carrier | 4 | Ø30 × 3 mm aluminium ring, Ø36 × 1.5 mm flange, Ø19 bore | 6.4 g ea | **Local machine shop — custom turned part** | Bonded into the cheek with retaining compound. Get a quote for 6 pieces including spares. |
| Output screws | 48 | M3 × 6 SHCS provisional, pending first-actuator thread-depth measurement | ~2.8 g per six | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | Also buy M3 × 8 validation stock; see section 10. |
| Stator screws, knee + ankle | 16 | M3 × 14 SHCS + 1 mm washers | Included in fastener mass | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | Through 6 mm limb plate + 3.2 mm rear cover into 4 mm thread. |
| Rear screws, hip roll + hip pitch | 16 | M3 × 12 SHCS + 2 mm washers | Included in fastener mass | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | Through 3 mm cheek + 3.2 mm rear cover into 4 mm thread. |

Printed-part masses, PA12-CF at 1.06 g/cm³, measured from the CAD:

| Part | Each | Count | Total |
|---|---:|---:|---:|
| Limb plate, thigh or shin — two distinct prints, used crosswise | 36.4 g | 4 | 145.6 g |
| Hip carrier — left and right | 37.5 g | 2 | 75.0 g |
| Foot tray with sole and sensor pads — left and right | 71.6 g | 2 | 143.1 g |
| Pelvis and torso shell with removable cover | 198.4 g | 1 | 198.4 g |
| **Printed structure** | | | **562 g** |

With metal, fasteners, electronics and a 60 g allowance for the power-entry block — capacitors, fuse and terminal — the current model comes to approximately **1,607 g against a 2,300 g ceiling**, leaving roughly **693 g** headroom. That is the six-motor wheeled robot; it was 2,047 g before hip roll was deleted and the torso shortened, and the eight-motor walking robot on `main` is still near the older figure. Use `uv run tools/mass.py` as the authoritative roll-up rather than this static table.

## 10. Fastener schedule

The joint interfaces fix the fastener count and final nominal lengths. Eight joints each have a rotor side and a stator side.

### Where the screws go

| Joint | Rotor side — 6 × M3 on Ø24 output circle | Stator side — 4 × M3 on Ø41 rear pattern |
|---|---|---|
| Hip roll ×2 | hip carrier upper hub | torso clevis |
| Hip pitch ×2 | thigh upper disc | hip carrier lower clevis |
| Knee ×2 | shin upper disc | thigh stator plate |
| Ankle ×2 | foot rotor hub | shin stator plate |

That is **48 rotor-side screws + 32 stator-side screws = 80 installed M3 SHCS**.

### Lengths and engagement

| Where | Qty | Screw | Washer | Pass-through | Thread | Engagement | Purchase link |
|---|---:|---|---|---:|---:|---:|---|
| Output circle, all 8 rotor ends | 48 | **M3 × 6** provisional | none, counterbored | 2.8 mm | ~5 mm unverified | 3.2 mm | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) |
| Stator plate, knee and ankle | 16 | **M3 × 14** | 1.0 mm | 9.2 mm | 4 mm | 3.8 mm | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) |
| Rear cheek, hip roll and hip pitch | 16 | **M3 × 12** | 2.0 mm | 6.2 mm | 4 mm | 3.8 mm | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) |

The output-thread depth still needs to be measured on the first physical actuator. If it is really 5 mm, M3 × 8 bottoms at approximately 5.2 mm while M3 × 6 gives only about 3.2 mm engagement. **Buy both M3 × 6 and M3 × 8 initially**, measure the motor, then standardise on whichever gives roughly 4 mm engagement without bottoming.

**Purchase quantity:** 100 each of M3 × 6, M3 × 8, M3 × 12 and M3 × 14 12.9 SHCS; at least 50 each of approximately 1 mm and 2 mm M3 washer stack thicknesses. Measure actual washer thickness before relying on the engagement arithmetic.

The installed steel fastener schedule plus washers is estimated around **90 g**, roughly 30 g above the current 60 g fastener allowance in `tools/mass_budget.toml`. This does not threaten the 2.3 kg ceiling but the mass allowance should be updated rather than left as an untracked discrepancy.
