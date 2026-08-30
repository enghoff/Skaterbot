# Provisional Bill of Materials — India Hobbyist Build

**Status:** provisional / pre-knee-design  
**Sourcing check:** 2026-08-30  
**Project baseline:** 380 mm, 8-DOF torque-controlled biped using DAMIAO DM-J3507-2EC actuators.

This BOM is deliberately split between parts that are sensible to source now and parts that must remain flexible until the CAD or electrical measurements are mature. Prices and stock are snapshots from the sourcing date; re-check GST, shipping, stock and seller before ordering. Imported prices exclude shipping, customs duty, IGST, payment/FX charges and courier handling unless explicitly stated.

No supplier links below are affiliate links.

## Sourcing risk legend

- 🔴 **High** — specialist/imported; can become a schedule blocker. Source early.
- 🟠 **Medium** — available, but exact variant/geometry may have lead-time or compatibility issues.
- 🟢 **Low** — commodity or readily available in India.
- ⏸️ **WAIT** — deliberately do not purchase until a design/test dependency is resolved.

## 1. Core BOM and India purchasing links

| Subsystem | Qty | Provisional part / specification | Current source / indicative price | Risk | When to buy | Notes |
|---|---:|---|---|:---:|---|---|
| Actuator | 8 | **DAMIAO DM-J3507-2EC, 24 V** | [Foxtech](https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/) — **US$89–95** | 🔴 | **Buy 2 now; remaining 6 after knee validation** | 7:1 low-ratio servo, integrated driver, dual encoders, CAN/CAN-FD. Each motor includes one 3-pin power/CAN cable and one 8-pin tuning cable. |
| Actuator power/CAN pigtail | 10–12 | SH1.0 3-pin, preferably OEM DAMIAO | [Foxtech DAMIAO range](https://store.foxtech.com/damiao/) — ask for spare OEM harnesses with motor order | 🟠 | **Order spares with motors** | No convincing cheap India source for the exact known-correct harness was found. Do not assume a generic SH1.0 cable has the correct pinout/current capability. |
| Actuator tuning pigtail | 2–3 | SH1.0 8-pin tuning cable | Included with each Foxtech motor; ask Foxtech for spares if desired | 🟠 | With motors | Two/three are enough for the finished project. |
| USB-CAN-FD debug interface | 1 | Waveshare USB-CAN-FD | [Sharvi Electronics](https://sharvielectronics.com/product/usb-can-fd-industrial-grade-can-can-fd-bus-data-analyzer-usb-to-can-fd-adapter-can-can-fd-bus-communication-interface-card-waveshare/) — ~**₹7,079 ex tax / ₹8.35k incl. 18% GST** | 🟠 | With first 2 motors | Full dual-channel isolated CAN/CAN-FD bench tool. Standard USB-CAN-FD is Windows-only; use the **USB-CAN-FD-B** variant if Linux support is required. |
| Realtime MCU dev board | 2 | **STM32G474** board | [Robu — WeAct STM32G474CEU6](https://robu.in/product/weact-studio-long-type-stm32g474ceu6/) or [DigiKey — NUCLEO-G474RE](https://www.digikey.in/en/products/detail/stmicroelectronics/NUCLEO-G474RE/10231585) — **₹1,923** for Nucleo | 🟢 | Early | WeAct is compact; Nucleo is the safer official-ST bench option. Native FDCAN is a good fit. |
| CAN-FD transceiver | 4 | **MCP2542FD-E/SN** or equivalent 3.3 V-MCU-compatible CAN-FD transceiver | [Mouser India](https://www.mouser.in/en/ProductDetail/Microchip-Technology/MCP2542FD-E-SN?qs=qdgZG5p0FZ5pNizBl1u80Q%3D%3D) — ~₹100-class | 🟢 | Early | SOIC package is convenient for prototypes/adapter PCBs. Two installed + spares. |
| Main IMU | 1–2 | **BNO085** breakout | [Robocraze — BNO085 Nano](https://robocraze.com/products/bno085-9-dof-orientation-imu-sensor-fusion-nano-breakout-board) — **₹2,089**, stock observed | 🟢 | Early | Nano board is preferable to the larger Qwiic board for final packaging. |
| Carbon-fibre leg members | 2 × 1 m | **8 × 8 mm OD pultruded square CF tube**, 6.5 mm round ID listing | [Robu — tubes/rods](https://robu.in/product-category/tubes-and-rods/) — **₹1,009 / m** | 🟢 | **Buy now** | Measure actual OD, straightness and wall geometry; measured dimensions override catalogue assumptions in CAD. |
| PETG filament | 1–2 kg | Quality PETG, 1.75 mm | [Robu — Numakers PETG](https://robu.in/product-category/numakers-petg-filaments/) — **~₹695 / kg** | 🟢 | As needed | Competitive prototype material. Print coupons and characterize actual settings before trusting published properties. |
| TPU filament / sole material | 1 spool | TPU ~95A | [Robu — Pro-Range TPU 95A](https://robu.in/product-category/pro-range-tpu-95a/) — **₹1,019–1,089 / kg** | 🟢 | Later | One spool is ample for soles and traction experiments. |
| Support bearings | ~8–12 | **TBD after knee CAD**; common 6800/6900/miniature metric families preferred | [IndustryBuying — 6800 bearing reference](https://www.industrybuying.com/lp/6800-bearing/) — **reference only** | ⏸️ | **Do not buy yet** | Exact ID/OD/width follows the actuator STEP, axle and yoke geometry. Avoid exotic thin-section sizes. |
| Joint axles | ~8 | **TBD** precision shaft / retained axle architecture | [Fastdep — 8 mm linear shaft reference](https://www.fastdep.in/product/linear-shaft-8mm/) — **reference only** | ⏸️ | **Do not buy yet** | 8 mm is only a sourcing example, not a frozen design dimension. Prefer standard shaft stock over unusual shoulder screws. |
| M3 fasteners | assortment | SHCS, washers, nyloc nuts, through-bolts | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) + [Asensar — M3 nyloc, 25 pcs](https://shop.asensar.in/product/nyloc-nut-m3/) — **₹28** for nylocs | 🟢 | Anytime | Structural joints should preferentially use through-bolts/locknuts, not heat-set inserts alone. |
| M4 structural hardware | assortment | SHCS / axle-related hardware | [Robu — SHCS](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) — common packs ~₹80–220 | 🟢 | Generic lengths now; final lengths after CAD | Keep to standard metric lengths. |
| Heat-set inserts | assortment | M3 brass heat-set inserts | [Robu — inserts](https://robu.in/product-category/nut-insert/) — **M3×6, 25 pcs ~₹91** | 🟢 | Anytime | Covers/light-duty interfaces only; not primary joint load paths. |
| Structural epoxy | 1 | Slow/medium-cure epoxy for CF-to-printed-part bond | [Flipkart — Araldite Standard 90 g](https://www.flipkart.com/araldite-standard-90g-epoxy-adhesive-resin-hardener/p/itmd0418b0cea16c) — **~₹336** | 🟢 | Before leg assembly | **PETG bonding must be coupon-tested.** Abrade/clean surfaces and use positive mechanical tube retention; adhesive is secondary. |
| Threadlocker | 1 | **Loctite 243**, medium strength | [Moglix — Loctite 243 50 ml](https://www.moglix.com/loctite-243-50ml-thread-locker/mp/msni6w4i8m0s) — **₹823 incl. tax** | 🟢 | Before assembly | Prefer credible industrial sellers; use on metal threaded interfaces. |
| Foot pressure sensors | 10 | FSR402 or equivalent, 8 installed + 2 spare | [Robu — force/flex sensors](https://robu.in/product-category/flex-sensor/) — **SOUSHINE FSR402 short-tail ₹195** | 🟢 | Later | Suitable for V0 contact/COP indication, not precision force measurement. |
| LiPo battery | 1 initially | **6S ~850 mAh high-C, XT60**, capacity provisional | [Anubis RC — DOGCOM 6S 850 mAh 150C](https://anubisrc.com/product/dogcom-6s-850mah-150c-22-2v-lipo-battery-xt60/) — **₹2,100, in stock, ~193 g** | 🟢 | After first motor-current tests | Replaces the old 420 g 2200 mAh recommendation. 193 g is still ~18 g above the current 175 g battery allowance, so re-measure mass budget. A lighter ~152 g DOGCOM UCELL 850 exists but the checked Indian listing was out of stock. |
| LiPo balance charger | 1 | Reputable 1–6S charger | [FPVMatrix — HOTA T6](https://fpvmatrix.in/product/hota-t6-dc-300w-pd-90w-15a-1-6s-lipo-battery-charger/) — **₹3,399, 8 in stock** | 🟢 | Before battery testing | Strong value; 1–6S, 300 W DC / 90 W USB-PD input. Requires suitable DC or USB-PD source. |
| Main connector | 3–4 pairs | Genuine **AMASS XT60** | [Robokits — original XT60 M/F](https://robokits.co.in/batteries-chargers/plugs-and-connectors/amass-xt60-male-and-female-connector-original) — **₹54/pair, in stock** | 🟢 | Anytime | Main battery/power disconnect. |
| Branch connectors | 10–12 pairs | Genuine **AMASS XT30** or locking equivalent | [Robokits — original XT30 M/F](https://robokits.co.in/batteries-chargers/accessories/plugs-and-connectors/amass-xt30-male-and-female-connector-original-xt30-f-m?cPath=67_618_623) — **₹41/pair, in stock** | 🟢 | After harness design | Compact branch connector; verify measured branch current before standardizing. |
| Main bus wire | ~3 m | 14 AWG high-strand silicone | [Robu — 12–16 AWG silicone wire](https://robu.in/product-category/12-to-16-awg/) — **~₹56–66/m per colour** | 🟢 | Later | Size against measured simultaneous peak current and cable length. |
| Motor branch wire | 5–8 m | 16–18 AWG high-strand silicone | [Robu — 12–16 AWG](https://robu.in/product-category/12-to-16-awg/) / [18–22 AWG](https://robu.in/product-category/batteries/wires-and-cables/silicone-wires/18-to-22-awg/) — **~₹46–49/m for 16–18 AWG** | 🟢 | Later | Final gauge after motor-current measurement. |
| CAN wiring | ~5 m | Flexible twisted pair ~24–26 AWG | [Robu — 24–30 AWG silicone](https://robu.in/product-category/24-to-30-awg/) — **~₹7–9/m per conductor** | 🟢 | Later | For early short harnesses, twist a matched pair consistently. If CAN-FD testing shows margin problems, move to proper flexible ~120 Ω twisted pair. |
| Logic DC/DC | 1–2 | 6S-compatible 5 V, >=5 A buck | [Hubtronics — XY-3606 5 V / 5 A](https://www.hubtronics.in/xy-3606-dc-dc-converter) — **₹129, 486 in stock** | 🟢 | Early for bench/V0 | Very cheap prototype candidate only. Bench-validate 25.2 V input, ripple, transient response and thermal behaviour before final use. |
| Main fuse | 2 | Automotive blade fuse + holder, initial 15/20/25/30 A test values | [Robu — fuse kits/holders](https://robu.in/product-category/fuse-kits/) — low-cost commodity | 🟢 | Before multi-joint power tests | Final fuse value must follow measured current. Use a holder with DC voltage rating safely above 25.2 V. |
| Emergency stop | 1 | Latching 22 mm mushroom E-stop controlling motor-power switch path | [Robocraze — YWBL-WH](https://robocraze.com/products/ywbl-wh-mushroom-emergency-stop-push-button-switch-22mm) — **₹93, stock observed** | 🟢 | **Before multi-motor tests** | **Control signal only.** Do not route the full motor bus through this small panel switch. |
| Power switch / contactor | 1 | DC-rated switching solution appropriate for 6S and measured current | **WAIT — no purchase link intentionally** | ⏸️ | After current/inrush/regeneration tests | Do not buy an arbitrary automotive relay or AC contactor just to complete the BOM. |
| Bulk bus capacitance / surge handling | TBD | Low-ESR capacitor bank and/or clamp strategy | **WAIT — no purchase link intentionally** | ⏸️ | After actuator bus-voltage logging | Backdrivable motors can regenerate onto the bus; size protection from measured excursions. |
| Heat-shrink | assortment | Heat-shrink kit | [Robu — heat-shrink kits](https://robu.in/product-category/heat-shrink-combos/) — **from ~₹146–177** for useful starter kits | 🟢 | Anytime | Workshop consumable. |
| Braided sleeve / strain relief | assortment | Expandable braid, grommets, ties | [Robu — cable-management range](https://robu.in/product-category/heat-shrink-tubing-sleeve/) — commodity | 🟢 | Gradually | Final braid diameter follows actual harness bundle. |

## 2. BOM review findings / corrections

### A. Battery recommendation corrected

The old BOM specified a **GenX 6S 2200 mAh 40C/80C** pack around ₹2,659. The checked pack is roughly **420 g**, whereas the robot mass model had allocated about **175 g** for the battery. That choice would materially break the sub-2 kg target.

The current practical placeholder is the **DOGCOM 6S 850 mAh 150C XT60** pack from Anubis at about **193 g**. It is currently purchasable in India and much closer to the mass budget. Capacity is **not frozen**: use actuator/whole-leg current measurements to decide whether 650, 850, 1050 or ~1300 mAh is the best runtime/mass tradeoff.

A DOGCOM **850 mAh UCELL** variant is about **152 g**, but the checked Indian FPVStore listing was out of stock. This is worth revisiting before the final battery purchase.

### B. PETG / TPU sources made more price-competitive

The previous draft used eSUN references around ₹1,200/kg PETG and ₹2,200/kg TPU. For prototype work, current Robu listings are materially cheaper:

- Numakers PETG: ~**₹695/kg**
- Pro-Range TPU 95A: **₹1,019–1,089/kg**

These are sensible V0 materials provided actual print coupons are tested.

### C. Bearings and axles remain intentionally unpurchased

Freeze in this order:

1. authoritative DM-J3507-2EC STEP geometry,
2. joint cross-section and support architecture,
3. axle diameter and retention,
4. bearing ID / OD / width,
5. bearing brand/seal choice,
6. final spacers and fastener lengths.

Only then replace the reference links with exact bearing/shaft SKUs.

### D. E-stop architecture clarified

The mushroom switch is the operator control. It should command a **properly DC-rated motor-power disconnect**, not interrupt the complete motor current itself.

### E. CAN wiring remains provisional

High-flex silicone conductors are convenient through moving joints but do not guarantee characteristic impedance. Short consistently twisted 24–26 AWG prototype pairs are reasonable; validate CAN-FD error rate/signal integrity at the chosen bit rate before freezing the final harness.

### F. ₹129 buck converter is not automatically a final-robot regulator

The XY-3606 is attractive for bench/V0 work, but a finished robot regulator should be selected only after checking ripple, EMI, thermal rise and transient behaviour with the actual SBC/sensor load.

## 3. Source-early shortlist

### Buy now / very soon

1. **2 × DAMIAO DM-J3507-2EC 24 V**.
2. **2+ spare DAMIAO 3-pin power/CAN pigtails**, requested with the motor order.
3. **1 × USB-CAN-FD interface** if the first motor tests need a general CAN-FD analyzer.
4. **2 × 1 m 8 × 8 mm carbon-fibre square tubes**.
5. **2 × STM32G474 development boards**.
6. **1–2 × BNO085 breakouts**.
7. Basic M3/M4 fasteners, M3 inserts and PETG.
8. Loctite 243 and epoxy before joint assembly.

### Wait for knee CAD

- support bearings
- joint axles / shoulder hardware
- spacers
- final structural fastener lengths

### Wait for motor-current / bus tests

- final battery capacity
- final motor wire gauges
- final fuse value
- final regulator architecture
- full cable-harness connector count
- power switch/contactor
- regenerative-energy handling components

## 4. Development-only equipment

| Item | Qty | Recommended India source / price | Priority | Notes |
|---|---:|---|---|---|
| Bench DC supply | 1 | [MakerBazar — OWON SPE3102 30 V / 10 A](https://makerbazar.in/products/owon-spe3102-dc-power-supply-variable-30v-10a) — **₹10,100 incl. tax**; [budget 30 V / 10 A](https://makerbazar.in/products/3010-programmable-dc-power-supply-30v-10a-digital-display) — **₹8,999** | High | Current-limited bench supply is safer for initial commissioning than LiPo. 300 W still cannot reproduce every whole-robot transient. |
| USB-CAN-FD adapter | 1 | [Sharvi — Waveshare USB-CAN-FD](https://sharvielectronics.com/product/usb-can-fd-industrial-grade-can-can-fd-bus-data-analyzer-usb-to-can-fd-adapter-can-can-fd-bus-communication-interface-card-waveshare/) | High | Commission motors independently of final firmware. |
| Digital caliper | 1 | [Insize India — digital calipers](https://www.insizeindia.in/caliper-1.html) — ~₹2.4k class for 150 mm reference | High | Worth using a credible metrology brand for received tubes, printed fits, spacers and shafts. |
| Torque test arm | 1 | **Custom printed/metal lever — no purchase link** | High | Accurately measure arm radius and combine with known masses/load scale. |
| Luggage/load scale | 1 | [Slovic 50 kg digital luggage scale](https://slovic.com/products/slovic-50kg-digital-luggage-scale-with-lcd-indicator-black-silver-travel-friendly) — **₹449** | Medium | Calibrate against known masses before using it for torque measurements. |
| IR thermometer / thermocouples | 1+ | [Moglix — Metravi IR thermometer range](https://www.moglix.com/brands/metravi/measurement-testing/temperature-humidity-meters/ir-thermometers/115153900) | High | Contact thermocouples are preferable for logged thermal tests. |
| Logic analyser | 1 | [Robokits — USB 24 MHz 8-channel logic analyser](https://robokits.co.in/programmers/logic-analyser/usb-logic-analyzer-24m-8ch-debug-tool?cPath=12) — **₹392** when stocked | Medium | Good for MCU-side SPI/UART/CAN-controller debugging; use an oscilloscope for CAN physical-layer integrity. |
| LiPo-safe charging/storage | 1 | [Robu — LiPo safety bags](https://robu.in/product-category/lipo-battery-sack-covers-mats/) — **~₹240–610** for useful bag sizes | High before battery phase | Never charge LiPo unattended. |

## 5. Provisional cost envelope

| Area | Rough provisional cost |
|---|---:|
| 8 × DM-J3507-2EC at Foxtech list price | **US$712–760 before shipping/import charges** |
| Carbon structure + printed materials + prototype mechanical consumables | **~₹4k–8k** |
| Bearings, axles and final fasteners | **~₹3k–8k**, depending final joint stack |
| MCU, CAN, IMU and foot sensors | **~₹6k–12k** |
| USB-CAN-FD development interface | **~₹8k–9k incl. GST class** |
| Lightweight battery + charger | **~₹5.5k** at current references |
| Wiring, connectors, DC/DC, fuse/E-stop/power hardware | **~₹3k–8k**, excluding final contactor/regen solution |

The earlier overall planning figure of roughly **₹1.0–1.3 lakh before uncertain actuator import/shipping costs** remains a useful order-of-magnitude budget, not a procurement quote. Recalculate once knee hardware, battery and power disconnect are frozen.

## 6. Design-for-India sourcing rules

1. Prefer **standard metric bearings** readily stocked in India.
2. Prefer **standard precision shaft stock** over exotic shoulder bolts.
3. Prefer M3/M4 standard fasteners and commonly stocked lengths.
4. Do not choose a rare component merely to save a few grams unless the benefit is quantified.
5. Maintain at least one domestic or broad-distribution alternative for commodity electronics.
6. Keep actuator-specific connectors/harnesses documented because these are disproportionately likely to cause delays.
7. Once a physical component is purchased, its **measured dimensions override catalogue assumptions** in CAD.
8. Record supplier, order date, actual landed cost, measured mass and measured dimensions in this BOM as the project progresses.
9. Treat links as sourcing aids, not immutable approved vendors; re-check price and stock immediately before purchase.
10. Do not turn a design-dependent placeholder into a purchased part merely to make the BOM look complete.

## 7. Current sourcing snapshot

Checked **2026-08-30**:

- DM-J3507-2EC — Foxtech **US$89–95**, with both required harnesses included.
- NUCLEO-G474RE — DigiKey India **₹1,923**, large stock observed.
- BNO085 Nano — Robocraze **₹2,089**, stock observed.
- 8 × 8 × 1000 mm square carbon tube — Robu **₹1,009**.
- Numakers PETG — Robu **~₹695/kg**.
- Pro-Range TPU 95A — Robu **₹1,019–1,089/kg**.
- DOGCOM 6S 850 mAh 150C XT60 — Anubis **₹2,100, in stock, ~193 g**.
- HOTA T6 1–6S charger — FPVMatrix **₹3,399, 8 in stock**.
- Genuine AMASS XT60 pair — Robokits **₹54**; XT30 pair — **₹41**.
- XY-3606 5 V/5 A buck — Hubtronics **₹129, 486 in stock**.
- SOUSHINE FSR402 short-tail — Robu **₹195**.
- YWBL-WH mushroom E-stop — Robocraze **₹93**.

Prices and availability are snapshots, not guarantees. Re-check immediately before ordering.
