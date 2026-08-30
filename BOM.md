# Provisional Bill of Materials — India Hobbyist Build

**Status:** provisional / pre-knee-design  
**Sourcing check:** 2026-08-30  
**Project baseline:** 380 mm, 8-DOF torque-controlled biped using DAMIAO DM-J3507-2EC actuators.

This BOM is intentionally split between parts that should be sourced early and commodity parts that should remain flexible until the CAD is mature. Purchase links and prices below are snapshots from the sourcing date, not guarantees. Re-check stock, GST, shipping and seller before ordering. Imported prices exclude shipping, customs duty, IGST, payment/FX charges and courier handling unless explicitly stated.

No supplier links below are affiliate links.

## Sourcing risk legend

- 🔴 **High** — specialist/imported; can become a schedule blocker. Source early.
- 🟠 **Medium** — available, but exact variant/geometry may have lead-time or compatibility issues.
- 🟢 **Low** — commodity or readily available from Indian suppliers. Do not over-constrain the design around a particular listing.
- ⏸️ **WAIT** — deliberately do not purchase until a design/test dependency is resolved.

## 1. Core BOM

| Subsystem | Qty | Provisional part / specification | Indicative unit price | India availability | Risk | When to buy | Notes |
|---|---:|---|---:|---|:---:|---|---|
| Actuator | 8 | **DAMIAO DM-J3507-2EC, 24 V** | Foxtech **US$89–95**; Indian trader quote ~**₹19,000** | Specialist/import | 🔴 | **Buy 2 now; remaining 6 after actuator/knee validation** | 7:1 low-ratio servo, integrated driver, dual encoders, CAN/CAN-FD, torque feedback/control. Foxtech package includes 3-pin power/CAN and 8-pin tuning cables plus STEP model. |
| Actuator power/CAN pigtail | 10–12 | SH1.0 3-pin compatible harness, preferably OEM DAMIAO | Included with each motor; spare price TBD | Exact connector is less common locally | 🟠 | **Order spares with motors** | Do not assume generic SH1.0 harness pinout/quality. |
| Actuator tuning pigtail | 2–3 | SH1.0 8-pin tuning cable | Included with each motor | Specialist | 🟠 | With motors | Two/three are enough; not required per joint in finished robot. |
| USB-CAN-FD debug interface | 1 | Waveshare USB-CAN-FD or DAMIAO-compatible interface | ~₹7k–8k locally for Waveshare | Available in India | 🟠 | With first 2 motors | Full CAN/CAN-FD bench/debug tool. A cheaper DAMIAO CAN debugger is also available direct from Foxtech. |
| Realtime MCU dev board | 2 | **STM32G474** development/core board | ~₹0.8–2.0k depending WeAct/Nucleo | Easy | 🟢 | Early | Native FDCAN is a good fit. Buy two so one can remain on bench. |
| CAN-FD transceiver | 4 | **MCP2542FD** / TCAN1042-class, 3.3 V MCU compatible | ~₹100–200 ea for bare IC | Easy via Indian distributors | 🟢 | Early | Bare SMD IC assumes PCB/adapter. Two installed + spares. |
| Main IMU | 1–2 | **BNO085** breakout | ~₹2.1–2.5k | Easy | 🟢 | Early | Breakout preferred for V0; move to PCB integration later. |
| Carbon-fibre leg members | 2 × 1 m | **8 × 8 mm OD pultruded square CF tube**, Robu listing has 6.5 mm round ID | **₹1,009 / 1 m** | Available domestically | 🟢 | **Buy now** | Measure actual OD, straightness and wall geometry; measured dimensions override catalogue assumptions in CAD. |
| PETG filament | 1–2 kg | Quality PETG, 1.75 mm | ~₹1,200/kg for eSUN reference | Very easy | 🟢 | As needed | Prototype joint structures. Print coupons before trusting published material data. |
| TPU filament / sole material | 0.25–0.5 kg used | TPU ~95A | ~₹2,200/kg for eSUN reference | Easy | 🟢 | Later | Replaceable sole / traction layer. One spool provides ample spare material. |
| Support bearings | ~8–12 | **TBD after knee CAD**; prefer common 6800/6900/miniature metric families | Typically ~₹50–500 ea depending brand | Very easy | ⏸️ | **Do not buy yet** | Exact ID/OD/width must follow the real actuator STEP, axle and yoke geometry. Avoid exotic thin-section bearings. |
| Joint axles | ~8 | **TBD** precision shaft/shoulder-bolt architecture | ~₹50–500+ depending solution | Standard shaft stock easy | ⏸️ | **Do not buy yet** | Prefer common hardened/SS shaft stock plus simple retention over rare shoulder screws. |
| M3 fasteners | assortment | 12.9-grade or SS SHCS, washers, nyloc nuts, through-bolts | ~₹400 starter screw kit + nuts/washers | Very easy | 🟢 | Anytime | Structural joints should preferentially use through-bolts/locknuts, not heat-set inserts alone. |
| M4 structural hardware | assortment | SHCS / axle-related hardware as selected | ~₹100–500 per useful assortment | Easy | 🟢 | After joint design | Keep to standard metric lengths where possible; final lengths wait for CAD. |
| Heat-set inserts | assortment | M3 brass heat-set inserts | ~₹91 / 25 pcs for common sizes | Very easy | 🟢 | Anytime | Covers/light-duty interfaces only; not primary structural load paths. |
| Structural epoxy | 1 | Slow/medium-cure epoxy suitable for CF-to-printed-part bond | ~₹336 for Araldite Standard 90 g reference | Easy | 🟢 | Before leg assembly | **PETG bonding must be coupon-tested.** Abrade/clean surfaces and retain tubes mechanically; adhesive is not the sole load path. |
| Threadlocker | 1 | **Loctite 243** or equivalent medium strength | ~₹742–823 / 50 ml | Easy | 🟢 | Before assembly | For metal threaded interfaces. Verify compatibility where screws enter plastics/inserts. |
| Foot pressure sensors | 10 | FSR402 or equivalent (8 installed + 2 spare) | ~₹195 ea for SOUSHINE FSR402 short-tail | Easy | 🟢 | Later | Good for V0 contact/COP indication; not precision force measurement. |
| LiPo battery | 1 initially | **6S 850 mAh, high-C, XT60** provisional | **₹2,100** DOGCOM 6S 850 mAh 150C at current India source | Easy domestically | 🟢 | After first motor-current tests | **Revised from 2200 mAh.** Current source lists ~193 g, much closer to the robot mass budget than the previous 420 g 2200 mAh pack. 22.2 V nominal / 25.2 V full. Runtime/capacity remains provisional. |
| LiPo balance charger | 1 | Reputable 1–6S balance charger, preferably DC/USB-PD input | **₹3,399** HOTA T6 current reference | Easy | 🟢 | Before battery testing | HOTA T6 supports 1–6S and 300 W DC. Requires a suitable DC or USB-PD input source. |
| Main connector | 3–4 pairs | Genuine **AMASS XT60H** | **₹65/pair** | Very easy | 🟢 | Anytime | Battery/main power disconnect; rated well above expected V0 current. |
| Branch connectors | 10–12 pairs | Genuine **AMASS XT30** or locking equivalent | **₹41/pair** | Easy | 🟢 | After harness design | XT30 is compact; current source rates it around 35 A continuous. Avoid unnecessary connectors at moving joints. |
| Main bus wire | 3 m | 14 AWG high-strand silicone wire | **₹47/m per colour** | Easy | 🟢 | Later | Size against measured simultaneous peak current and cable length. |
| Motor branch wire | 5–8 m | 16–18 AWG high-strand silicone wire | ~₹30–50/m | Easy | 🟢 | Later | Final gauge after measured motor current. |
| CAN wiring | ~5 m | Flexible twisted pair ~24–26 AWG | ~₹9/m/conductor for 24 AWG silicone prototype wire | Easy | 🟢 | Later | For prototype, twist a matched pair consistently. Final harness should use proper ~120 Ω twisted pair if signal-integrity testing at chosen CAN-FD rate requires it. |
| Logic DC/DC | 1–2 | 6S-compatible buck/UBEC to 5 V, >=5 A provisional | **₹353** generic 5 V / 5 A UBEC reference | Easy | 🟢 | Early for bench use | Bench-validate voltage, ripple, thermal behaviour and input rating. Final robot should use a known-quality regulator once SBC/peripheral load is frozen. |
| Main fuse | 2 | Automotive blade fuse + holder, initial ~20–30 A range | ~₹100–500 depending holder | Very easy | 🟢 | Before powered multi-joint tests | Fuse value must be revisited after current measurements. Use DC-rated holder above full 6S voltage. |
| Emergency stop | 1 | Latching 22 mm mushroom E-stop controlling motor-power contactor/switch path | ~₹93 switch reference | Easy | 🟢 | **Before multi-motor tests** | **Do not route full motor current through a small panel E-stop contact.** Use it to control the DC-rated switching element. |
| Power switch / contactor | 1 | DC-rated switching solution appropriate for 6S and measured current | TBD | Available | ⏸️ | **Do not buy yet** | Select after measured current/inrush/regeneration. Do not assume an AC-rated switch is safe for DC interruption. |
| Bulk bus capacitance / surge handling | TBD | Low-ESR electrolytic bank and/or clamp strategy | TBD | Components easy; design not frozen | ⏸️ | **Do not buy yet** | Backdrivable motors can regenerate onto the DC bus; log bus-voltage excursions during tests before sizing protection. |
| Heatshrink / braided sleeve / strain relief | assortment | Heat-shrink kit, braided sleeve, cable ties, grommets | ~₹150–500 starter material | Very easy | 🟢 | Gradually | Critical around moving joints despite low cost. |

## 2. India purchasing matrix

This section is the practical shopping list. **“Reference only / WAIT” means the link is useful for price/availability awareness but should not drive the CAD or be purchased yet.**

| Item | Recommended source | Price/status checked 2026-08-30 | Purchase note |
|---|---|---|---|
| DM-J3507-2EC 24 V | [Foxtech direct](https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/) | **US$89–95** | Best observed motor price; imports to India. Each motor includes the 3-pin and 8-pin harnesses. |
| DM-J3507-2EC India fallback | [Yuvvraj Global Traders](https://www.yuvvrajglobaltraders.com/brushless-servo-motors.html) | ~**₹19,000 / motor**, quote-based | Domestic option but currently not price-competitive with Foxtech before import costs. |
| Spare DAMIAO pigtails | [Foxtech motor/DAMIAO source](https://store.foxtech.com/damiao/) | Ask for spare OEM harnesses with motor order | No convincing low-cost India source for the exact OEM harness was found. Prefer known-correct OEM cable to an unverified generic SH1.0 assembly. |
| USB-CAN-FD adapter | [Sharvi Electronics — Waveshare USB-CAN-FD](https://sharvielectronics.com/product/usb-can-fd-industrial-grade-can-can-fd-bus-data-analyzer-usb-to-can-fd-adapter-can-can-fd-bus-communication-interface-card-waveshare/) | ~**₹7,079 before applicable tax** observed | Preferred India full CAN/CAN-FD debug adapter. |
| Lower-cost DAMIAO CAN debugger | [Foxtech DAMIAO products](https://store.foxtech.com/damiao/) | **US$19** | Useful cheaper commissioning option if classic CAN is sufficient; imported rather than India-stocked. |
| STM32G474 core board | [Robu — WeAct STM32G474CEU6](https://robu.in/product/weact-studio-long-type-stm32g474ceu6/) | Exact listing; verify live price/stock | Compact preferred development board. |
| STM32G474 robust alternate | [DigiKey India — NUCLEO-G474RE](https://www.digikey.in/en/products/detail/stmicroelectronics/NUCLEO-G474RE/10231585) | ~**₹1,923**, large stock during check | Larger/heavier but excellent bench board and official ST ecosystem. |
| MCP2542FD CAN-FD transceiver | [Mouser India — MCP2542FD](https://www.mouser.in/en/ProductDetail/Microchip-Technology/MCP2542FD-E-MF?qs=l7cgNqFNU1jog4BwTzULBw%3D%3D) | ~**₹101.57 ea**, in stock | Bare SMD IC. Choose package to suit PCB layout. |
| BNO085 IMU breakout | [Evelta — 7Semi BNO085 Nano](https://evelta.com/7semi-bno085-9-dof-orientation-imu-fusion-nano-breakout/) | ~**₹2.1k**, stock observed | Preferred current India price among checked breakout sources. |
| 8 × 8 × 1000 mm carbon tube | [Robu — tubes/rods](https://robu.in/product-category/tubes-and-rods/) | **₹1,009 / m** observed | Buy **2 lengths now**; measure before final sockets. |
| PETG 1.75 mm | [Ideal3D — eSUN PETG](https://ideal3d.in/collections/esun-petg) | **₹1,200 / kg** | Known-brand reference for structural prototypes. |
| TPU 95A | [Ideal3D — eSUN eTPU-95A](https://ideal3d.in/collections/esun-filaments) | **from ₹2,200 / kg** | Suitable reference for replaceable soles/traction. |
| Support bearings | **Reference only / WAIT** | Exact size TBD | Do **not** buy until knee cross-section is frozen. A 6800 example is 10×19×5 mm, but the project has not selected it. |
| Joint axles/shafts | **Reference only / WAIT** | Exact diameter/retention TBD | Do **not** buy until bearing and joint stack are frozen. |
| M3 SHCS kit | [Robu — socket-head screws](https://robu.in/product-category/mechanical-parts-and-tools/nuts-bolts-and-spacers/socket-head-cap-screw-allen-bolt/) | ~**₹410** for 100 pc M3 12.9-grade kit observed | Useful prototype lengths 6/8/10/12 mm; add longer through-bolts after CAD defines them. |
| M4 SHCS | [Robu — socket-head screws](https://robu.in/product-category/mechanical-parts-and-tools/nuts-bolts-and-spacers/socket-head-cap-screw-allen-bolt/) | typically ~**₹70–170 / pack** depending size | Buy only useful generic lengths now; final structural lengths after knee CAD. |
| M3 heat-set inserts | [Robu — nut inserts](https://robu.in/product-category/nut-insert/) | **₹91 / 25 pcs** for M3×4 or M3×6 observed | Fine for covers/light-duty interfaces, not primary joint load paths. |
| Structural epoxy | [Flipkart — Araldite Standard](https://www.flipkart.com/araldite-standard-epoxy-adhesive/p/itmd0418b0cea16c) | ~**₹336 / 90 g** observed | Provisional readily available adhesive. **Coupon-test PETG/CF bond and use positive mechanical retention.** |
| Loctite 243 | [Moglix — Loctite 243 50 ml](https://www.moglix.com/loctite-243-50ml-threadlocker-retaining-compounds/mp/msnvk13yw2y891) | ~**₹742 incl. tax** observed | Buy from a credible industrial seller; counterfeit threadlocker is not worth the saving. |
| FSR402 pressure sensor | [Robu — force/flex sensors](https://robu.in/product-category/flex-sensor/) | **₹195** SOUSHINE FSR402 short-tail observed | Buy 10 later once foot sensor packaging is stable. |
| 6S 850 mAh LiPo XT60 | [Anubis RC — DOGCOM 6S 850 mAh 150C](https://anubisrc.com/product/dogcom-6s-850mah-150c-22-2v-lipo-battery-xt60/) | **₹2,100, in stock** | Current listing gives ~193 g. This replaces the prior 420 g 2200 mAh recommendation. Buy after initial motor-current testing. |
| LiPo charger | [FPVMatrix — HOTA T6](https://fpvmatrix.in/product/hota-t6-dc-300w-pd-90w-15a-1-6s-lipo-battery-charger/) | **₹3,399, 8 in stock** | Strong current value; supports 1–6S, DC/USB-PD input. |
| XT60H connector pair | [Robokits — genuine AMASS XT60H M/F](https://robokits.co.in/batteries-chargers/plugs-and-connectors/amass-xt60h-male-female-connector-with-housing) | **₹65/pair, in stock** | Preferred main power connector. |
| XT30 connector pair | [Robokits — genuine AMASS XT30 M/F](https://robokits.co.in/batteries-chargers/accessories/plugs-and-connectors/amass-xt30-male-and-female-connector-original-xt30-f-m?cPath=67_618_623) | **₹41/pair, in stock** | Good branch connector where measured current allows. |
| 14 AWG silicone wire | [Robokits — 14 AWG silicone wire](https://robokits.co.in/silicone-wires) | **₹47/m per colour**, in stock | Very competitive current price; buy red and black. |
| 16–18 AWG motor branch wire | [Robokits — silicone wire](https://robokits.co.in/silicone-wires) | gauge-dependent; typically tens of rupees/m | Final gauge after motor-current measurement. |
| 24–26 AWG CAN/prototype wire | [Robu — 24–30 AWG silicone wire](https://robu.in/product-category/24-to-30-awg/) | **~₹9/m** for 24 AWG single conductor observed | Twist pair consistently for early bench/on-robot prototypes. Upgrade to specified 120 Ω cable if testing requires it. |
| 5 V / 5 A UBEC | [FlyRobo — Readytosky 5V/5A UBEC](https://www.flyrobo.in/readytosky-5v-5a-ubec) | **₹353, in stock** | Cheap bench/V0 candidate; validate full 6S input, ripple and thermal performance before relying on it. |
| Main fuse holder | [element14 India — automotive 30 A holders](https://in.element14.com/c/circuit-protection/fuses-fuse-accessories/fuse-holders?fuse-current=30a&fuse-holder-type=automotive-blade-fuse-holder) | from ~**₹124** for simple holder options; better sealed holders cost more | Select a holder with DC voltage rating above 25.2 V; fuse amperage remains provisional. |
| Fuse assortment | [Robu — fuse kits](https://robu.in/product-category/fuse-kits/) | low-cost commodity | Buy 15/20/25/30 A values for test characterization rather than assuming one final value. |
| Mushroom E-stop | [Robocraze — YWBL-WH 22 mm E-stop](https://robocraze.com/products/ywbl-wh-mushroom-emergency-stop-push-button-switch-22mm) | ~**₹93** observed | **Control input only** for the motor-power disconnect element unless its verified DC contact rating safely covers the load. |
| DC main contactor | **WAIT** | Select after measured current/inrush/regeneration | Do not buy an arbitrary relay/AC contactor just because it is inexpensive. |
| Bus capacitor / clamp | **WAIT** | Select after bus-voltage logging | Requires actuator regen measurements first. |
| Heat-shrink assortment | [Robu — heat-shrink kits](https://robu.in/product-category/heat-shrink-combos/) | from **₹159** for useful assorted kits | Good workshop consumable. |
| Braided cable sleeve | [Fastdep — cable sleeve range](https://www.fastdep.in/product/) | 6 mm ~₹125/2 m when stocked; 12 mm ~₹155/2 m; 25 mm ~₹235/2 m | Choose final diameter after harness bundle is known. |

## 3. BOM review findings / corrections

### A. Battery recommendation corrected

The previous BOM suggested a **GenX 6S 2200 mAh 40C/80C** pack at about ₹2,659. The currently checked product is approximately **420 g**, which is incompatible with a robot mass estimate that had assumed roughly **175 g** for the battery.

The V0 BOM therefore moves to a **6S 850 mAh high-C XT60 pack** as the current provisional choice. The current Anubis DOGCOM listing is ₹2,100 and reports about 193 g. DOGCOM's own 850 mAh 6S variants are in the ~146–152 g class depending series, so **measure the exact delivered pack** and update the CAD/mass budget before final packaging.

Capacity is **not frozen**. If measured walking current makes 850 mAh impractically short-lived, choose a larger pack and explicitly trade runtime against mass.

### B. Bearings and axles remain intentionally unpurchased

The earlier BOM was correct to keep these TBD. The project should not select a bearing merely because a convenient Indian listing exists.

Freeze in this order:

1. authoritative DM-J3507-2EC STEP geometry,
2. joint cross-section and support architecture,
3. axle diameter and retention,
4. bearing ID / OD / width,
5. bearing brand/seal choice,
6. final spacers and fastener lengths.

Only then add exact bearing/shaft purchase links.

### C. E-stop architecture clarified

A cheap mushroom switch is suitable as the **operator control**, but the safety function should remove motor power through a properly DC-rated switching element. The small panel switch itself should not be assumed capable of interrupting the full 6S motor bus.

### D. CAN wiring clarified

Generic flexible silicone wire is convenient for moving joints but does not guarantee CAN characteristic impedance. For early short harnesses, a tightly and consistently twisted 24–26 AWG pair is reasonable. If CAN-FD eye-diagram/error-rate testing shows margin problems, move to a proper flexible ~120 Ω twisted pair.

### E. Low-cost UBEC is bench/V0 only

The ₹353 5 V/5 A UBEC is a useful test item, not automatically a finished-robot regulator. Verify:

- 25.2 V fully-charged 6S input compatibility,
- output ripple under SBC/peripheral transients,
- thermal rise,
- startup behaviour,
- conducted noise into IMU/CAN electronics.

## 4. Source-early shortlist

These are the items most likely to delay the project if left until the mechanical CAD is finished.

### A. DAMIAO DM-J3507-2EC actuators — highest priority

**Recommended action:** source **two 24 V units now**, characterize them, and order the remaining six as soon as the knee architecture is validated.

- Foxtech: **US$89–95**
- Product: https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/
- Each motor currently includes:
  - 1 × SH1.0 3-pin power + CAN cable (200 mm)
  - 1 × SH1.0 8-pin tuning cable (200 mm)
  - manual
  - STEP file

India-specific concern:

- Yuvvraj Global Traders currently advertises the same motor around ₹19,000/piece, which is not obviously competitive with direct import before landed costs are known.
- Treat the actuator as an import/specialist component until a better Indian stockist is confirmed.
- Ask Foxtech/DAMIAO for **extra pigtails** with the motor order.

### B. Carbon-fibre square tube — buy early to lock actual geometry

Robu currently lists:

- Pultruded square inner-round carbon-fibre hollow tube
- **8 × 8 mm OD**
- **6.5 mm round ID**
- **1000 mm length**
- **₹1,009**
- Source: https://robu.in/product-category/tubes-and-rods/

Buy two lengths and make the CAD fit the material actually received.

### C. Exact DAMIAO connector ecosystem

The motors use small SH1.0 harness connectors. The supplied OEM cables solve the immediate problem, but standalone replacements are disproportionately easy to get wrong.

**Recommendation:** obtain at least **two spare motor pigtails** during the actuator purchase and avoid repeatedly disconnecting the motor-side miniature connector during prototyping.

### D. Precision axle solution

India has abundant bearing and shaft stock, but very specific metric shoulder screws can be awkward or expensive.

**Design constraint for CAD:** prefer:

1. standard precision/hardened shaft diameter,
2. common metric bearing IDs,
3. simple washers/spacers/circlips or threaded retention,
4. standard M3/M4 fasteners,

rather than designing around an unusual imported shoulder bolt.

Do **not** purchase axles until the real knee cross-section is frozen.

## 5. Components that should not constrain the CAD

These are readily sourced enough in India that the design should select them based on engineering merit while remaining within common families:

- M3/M4 fasteners
- 6800/6900-series and common miniature bearings
- PETG and TPU
- 6S RC LiPo batteries
- silicone wire
- XT30 / XT60 connectors
- FSR sensors
- STM32 development boards / MCUs
- CAN transceivers
- buck regulators
- fuses
- E-stop switches
- heatshrink and cable sleeve

Avoid saving a few grams by specifying a rare bearing or fastener that creates an import dependency.

## 6. Development-only equipment

| Item | Qty | Provisional choice | Current India source / price | Priority | Notes |
|---|---:|---|---|---|---|
| Bench DC supply | 1 | 0–30 V, preferably >=10 A with current limiting | [Robocraze — OWON SPE3102 30 V / 10 A](https://robocraze.com/products/owon-spe3102-30v-10a-programmable-dc-power-supply), **₹10,249 incl. GST** | High | Safer initial motor/joint commissioning than LiPo. 300 W limit means it will not reproduce every multi-joint transient. |
| USB-CAN-FD adapter | 1 | Waveshare USB-CAN-FD | [Sharvi Electronics](https://sharvielectronics.com/product/usb-can-fd-industrial-grade-can-can-fd-bus-data-analyzer-usb-to-can-fd-adapter-can-can-fd-bus-communication-interface-card-waveshare/), ~₹7k class | High | Commission/characterize motors independently of final firmware. |
| Digital caliper | 1 | 0.01 mm display class | [Insize India calipers](https://www.insizeindia.in/caliper-1.html), ~₹2.4k class for 150 mm digital reference | High | A credible metrology brand is worth paying for here. |
| Torque test arm | 1 | Printed/metal lever of accurately measured radius | **Custom part — no purchase link** | High | Combined with hanging masses/load cell for actuator torque calibration. |
| Luggage/load scale | 1 | 0–50 kg digital hanging scale | [Flipkart — representative 50 kg scale](https://www.flipkart.com/getsetnova-50kg-digital-luggage-weighing-scale-portable-travel-weight-machine/p/itmaca1a65f96a82), ~₹426 observed | Medium | Cheap static force checks; verify/calibrate against known masses before trusting measurements. |
| IR thermometer | 1 | Handheld IR thermometer or thermocouples | [Moglix — Metravi IR thermometer range](https://www.moglix.com/brands/metravi/measurement-testing/temperature-humidity-meters/ir-thermometers/115153900) | High | For actuator and printed-joint thermal characterization. Contact thermocouples are better for logged tests. |
| Logic analyser / oscilloscope | 1 | Existing instrument if available | No new purchase required if bench already equipped | Medium | Logic analyser is useful at MCU-side CAN signals; scope is required for physical-bus signal integrity. |
| LiPo-safe storage | 1 | LiPo bag/metal fire-resistant storage + charger | [Robu — LiPo safety bags](https://robu.in/product-category/batteries/battery-accessories/lipo-battery-sack-covers-mats/) | High before battery phase | Never charge unattended. Charger is listed above. |

## 7. Provisional cost envelope

These figures are intentionally broad because actuator shipping/import treatment dominates uncertainty and several final mechanical/electrical parts remain intentionally TBD.

| Area | Rough provisional cost |
|---|---:|
| 8 × DM-J3507-2EC at Foxtech list price | **US$712–760 before shipping/import charges** |
| Carbon structure + printed materials + prototype mechanical consumables | **~₹5k–10k** |
| Bearings, axles and fasteners | **~₹3k–8k**, depending final joint stack |
| MCU, CAN, IMU and foot sensors | **~₹6k–12k** |
| USB-CAN-FD development interface | **~₹7k–8k** |
| Lightweight battery + charger | **~₹5.5k** at current reference prices |
| Wiring, connectors, DC/DC, fuse/E-stop/power hardware | **~₹4k–10k** |

The earlier overall planning figure of roughly **₹1.0–1.3 lakh before uncertain actuator import/shipping costs** remains a useful order-of-magnitude budget, not a procurement quote. The final figure should be recalculated once the knee hardware, power disconnect and battery capacity are frozen.

## 8. Immediate procurement recommendation

### Buy now / very soon

1. **2 × DAMIAO DM-J3507-2EC 24 V** — Foxtech currently gives the best observed base price.
2. **2+ spare DAMIAO 3-pin power/CAN pigtails**, requested with the motor order.
3. **1 × USB-CAN-FD interface** — unless the cheaper DAMIAO debugger fully covers the first bench tests.
4. **2 × 1 m 8 × 8 mm Robu carbon-fibre square tubes**.
5. **2 × STM32G474 development boards**.
6. **1–2 × BNO085 breakouts**.
7. Basic M3 fastener kit + M3 inserts + PETG.
8. Loctite 243 and epoxy before mechanical prototype assembly.

### Wait for knee CAD

- support bearings
- joint axles / shoulder hardware
- spacers
- final structural fastener lengths

### Wait for motor-current / bus tests

- final battery capacity/quantity
- final motor wire gauges
- final fuse value
- final regulator architecture
- full cable-harness connector count
- power switch/contactor
- regenerative-energy handling components

## 9. Design-for-India sourcing rules

The CAD/design agent should treat the following as explicit constraints:

1. Prefer **standard metric bearings** readily stocked in India.
2. Prefer **standard precision shaft stock** over exotic shoulder bolts.
3. Prefer M3/M4 standard fasteners and commonly stocked lengths.
4. Do not choose a rare component merely to save a few grams unless the benefit is quantified.
5. Maintain at least one domestic or broad-distribution alternative for commodity electronics.
6. Keep actuator-specific connectors/harnesses documented because these are disproportionately likely to cause delays.
7. Once a physical component is purchased, its **measured dimensions override catalogue assumptions** in the CAD.
8. Record supplier, order date, actual landed cost, measured mass and measured dimensions in this BOM as the project progresses.
9. Treat links as sourcing aids, not immutable approved vendors; re-check competitive price immediately before purchase.
10. Do not turn a design-dependent placeholder into a purchased part merely to make the BOM look complete.

## 10. Source references / sourcing notes

Checked 2026-08-30. Key current observations:

- DAMIAO DM-J3507-2EC — Foxtech **US$89–95**; each unit includes power/CAN and tuning harnesses.
- Indian DM-J3507-2EC trader listing — ~**₹19,000/piece** quote reference.
- Waveshare USB-CAN-FD — Sharvi around **₹7k class** before applicable taxes.
- BNO085 breakout — Evelta/7Semi around **₹2.1k class**.
- Robu 8 × 8 × 1000 mm square carbon tube — **₹1,009** observed.
- DOGCOM 6S 850 mAh 150C XT60 — Anubis **₹2,100, in stock**; source listing reports about **193 g**.
- HOTA T6 1–6S charger — FPVMatrix **₹3,399, in stock** during check.
- Genuine AMASS XT60H pair — Robokits **₹65**; XT30 pair — **₹41**.
- Robokits 14 AWG silicone wire — **₹47/m per colour**.
- Readytosky 5 V/5 A UBEC — FlyRobo **₹353, in stock**.
- Robu SOUSHINE FSR402 short-tail — **₹195**.

Prices and availability are snapshots, not guarantees. Re-check immediately before ordering.