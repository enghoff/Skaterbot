# India purchasing guide for the current BOM

**Checked:** 2026-08-30  
**Applies to:** `docs/BOM.md` on `main` after the `cad-baseline` merge (`c2be3b7`).  
**Purpose:** purchasing links and price/stock snapshots for the *current* CAD-reconciled BOM. This deliberately does not revive the pre-CAD root `BOM.md`; items retired or changed by the CAD are marked accordingly.

Prices and stock change quickly. Re-check GST, shipping, stock and seller immediately before ordering. Imported prices exclude shipping, customs duty, IGST, payment/FX charges and courier handling unless explicitly stated. No links are affiliate links.

## Key corrections versus the earlier sourcing pass

- Carbon-fibre tubes, structural epoxy, M4 hardware, LiPo battery and LiPo charger are **retired**. Do not buy them.
- Support bearings are now **6800-2RS, 10 × 19 × 5 mm**, **4 installed + 2 spare**, not an unresolved 8–12 bearing assortment.
- Journals are now **Ø10 × 8 mm**, **4 installed + 2 spare**.
- The fastener schedule is fixed: buy **100 each M3 × 6, M3 × 8, M3 × 12 and M3 × 14 SHCS**, plus 1 mm and 2 mm M3 washers. M3 × 8 is bought only because the actuator output-thread depth still needs measuring.
- Foot sensors are **FSR400**, not FSR402.
- The robot is tethered, so the BOM now requires tether hardware and regenerative-energy handling rather than a battery.
- The current BOM's statement that a BNO085 breakout does not fit is too broad. The **7Semi BNO085 Nano is 11 × 10 × 6 mm and fits the 22 × 22 × 6 mm CAD reservation**. The Adafruit 25.6 × 22.7 mm board and 7Semi Qwiic 28 × 21 mm board do not.

## A. Buy now / source early

| BOM item | Qty | Recommended source | Checked price/status | Purchase note |
|---|---:|---|---|---|
| DAMIAO DM-J3507-2EC, 24 V | 2 now, 6 later | [Foxtech](https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/) | US$89–95 reference | Best current reference found. Buy two first for validation. Ask for at least two spare **8-pin power/CAN** pigtails with the order. |
| DAMIAO spare harnesses | 2+ power/CAN spares | [Foxtech DAMIAO range](https://store.foxtech.com/damiao/) | Ask with motor order | No convincing Indian source for a known-correct OEM SH1.0 harness was found. Do not substitute generic SH1.0 cable without checking current capacity and pinout. |
| USB-CAN-FD debug adapter | 1 | [Sharvi — Waveshare USB-CAN-FD](https://sharvielectronics.com/product/usb-can-fd-industrial-grade-can-can-fd-bus-data-analyzer-usb-to-can-fd-adapter-can-can-fd-bus-communication-interface-card-waveshare/) | ~₹7–8k class | Appropriate bench/debug interface. If Linux support is required, verify the exact Waveshare variant before ordering. |
| Realtime MCU board | 2 | [Robu — WeAct STM32G474CEU6](https://robu.in/product/weact-studio-long-type-stm32g474ceu6/) | Current Indian listing; product confirmed | This is the compact board the CAD is dimensioned around. **Do not buy NUCLEO-G474RE for installation; it does not fit.** |
| CAN-FD transceiver | 4 | [Mouser India — MCP2542FD-E/SN](https://www.mouser.in/en/ProductDetail/Microchip-Technology/MCP2542FD-E-SN?qs=qdgZG5p0FZ5pNizBl1u80Q%3D%3D) | ~₹100-class per IC reference | Two installed + two spare. Bare SOIC IC: use adapter/PCB as appropriate. |
| BNO085 IMU | 1–2 | [Evelta — 7Semi BNO085 Nano](https://evelta.com/7semi-bno085-9-dof-orientation-imu-fusion-nano-breakout/) | ~₹2,094.50 incl. GST; stock observed | **Preferred geometry:** 11 × 10 × 6 mm, so it fits the CAD's 22 × 22 × 6 mm reservation. Also sold by 7Semi/Robocraze. |
| PA12-CF filament | 2–3 kg eventually | [3D Printers Depot India — QIDI PA12-CF](https://3dprintersdepot.com/en-in/collections/carbon-fiber-filament/filaments) | ~₹4,200 reference | Strong current India price for true PA12-CF. Buy one spool first and validate coupons/process before buying the full 2–3 kg. Requires hardened nozzle and continuous drying. |
| 6800-2RS bearings | 6 | [IndustryBuying — 6800-2RS 10×19×5](https://www.industrybuying.com/special-bearing-monotaro-BEA.SPE.238091927) | ~₹907 each for the checked MonotaRO listing | Geometry matches. This listing is relatively expensive/direct-import; local bearing shops may beat it substantially. Prefer SKF/NTN/Koyo/NSK or another reputable equivalent if available locally. |
| 10 mm journal stock | enough for 6 × 8 mm stubs | [Fastdep — 10 mm linear shaft](https://www.fastdep.in/product/linear-shaft-10mm/) | ₹498/m reference; checked listing currently sold out | Correct diameter/material class, but buy locally if Fastdep remains OOS. Cut/facing six 8 mm pieces from a short length is cheap. |
| Bearing carriers | 6 | Local machine shop | quote required | **No off-the-shelf purchase link recommended.** Current part is Ø30 × 3 ring, Ø36 × 1.5 flange, Ø19 bore. Get a quote before committing; this is the only bespoke metal part. |
| Loctite 638 retaining compound | 1 | [Moglix](https://www.moglix.com/loctite-638-50ml-retaining-compound/mp/msni6sci8m0s) | ~₹713 incl. tax | For bonding metal bearing carriers into the printed cheeks. |
| Loctite 243 threadlocker | 1 | [Moglix](https://www.moglix.com/loctite-243-50ml-threadlocker-retaining-compounds/mp/msnvk13yw2y891) | ~₹742 incl. tax | Use on metal threaded interfaces; verify compatibility where it can contact polymer. |
| FSR400 | 10 | [Aryabot — FSR 400](https://aryabot.in/sensors/load-pressure-force-flex-sensor/) | ~₹208 each | Competitive domestic listing. Correct small sensor family for the 10 × 10 mm foot-pad geometry. DigiKey has genuine Interlink parts but at much higher single-unit cost. |

## B. Exact fastener / workshop hardware

| BOM item | Qty to buy | Recommended source | Price/status | Note |
|---|---:|---|---|---|
| M3 × 6 SHCS | 100 | [Robu — socket-head cap screws](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | Commodity | Rotor attachment candidate. |
| M3 × 8 SHCS | 100 | [Robu — socket-head cap screws](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | Commodity | **Validation stock only:** measure actual DAMIAO output thread depth before choosing ×6 vs ×8. |
| M3 × 12 SHCS | 100 | [Robu — socket-head cap screws](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | Commodity | Hip roll / hip pitch rear pattern. |
| M3 × 14 SHCS | 100 | [Robu — socket-head cap screws](https://robu.in/product-category/socket-head-cap-screw-allen-bolt/) | Commodity | Knee / ankle stator plate. |
| M3 washers, ~1 mm and ~2 mm stack thickness | 50 each minimum | Local fastener shop / industrial supplier | Commodity | Thickness matters more than vendor. Measure actual washers and stack to the engagement arithmetic in BOM §12. |
| M3 heat-set inserts | assortment | [Robu — nut inserts](https://robu.in/product-category/nut-insert/) | ~₹100-class small packs | Covers/light-duty interfaces only, not primary joints. |

For the joint screws, prefer **12.9 alloy-steel SHCS** from a credible fastener supplier over decorative/button-head hobby screws. The current Robu category is a convenient source/search starting point, but exact stock changes by length.

## C. Tether, wiring and connectors

| BOM item | Qty | Recommended source | Checked price/status | Purchase note |
|---|---:|---|---|---|
| XT60 pairs | 3–4 | [Robokits — genuine AMASS XT60](https://robokits.co.in/batteries-chargers/plugs-and-connectors/amass-xt60-male-and-female-connector-original) | ₹54/pair, in stock observed | Good value and credible genuine-AMASS listing. |
| XT30 pairs | 10–12 if harness design retains them | [Robokits — genuine AMASS XT30](https://robokits.co.in/batteries-chargers/accessories/plugs-and-connectors/amass-xt30-male-and-female-connector-original-xt30-f-m?cPath=13_840) | ₹41/pair, in stock observed | Do not bulk-buy until branch-connector count is final. |
| 14 AWG silicone power wire | ~6 m conductor length for 3 m tether, plus robot wiring | [Robu — 12–16 AWG silicone wire](https://robu.in/product-category/12-to-16-awg/) | ~₹50–70/m class | Buy red/black separately. **Before printing the pelvis, make the cable and measure real bundle OD.** |
| 16–18 AWG motor branch wire | 5–8 m | [Robu — silicone wire](https://robu.in/product-category/12-to-16-awg/) / [18–22 AWG](https://robu.in/product-category/batteries/wires-and-cables/silicone-wires/18-to-22-awg/) | ~₹40–60/m class | Final gauge remains measurement-dependent. |
| CAN pair | ~5 m | [Robu — 24–30 AWG silicone wire](https://robu.in/product-category/24-to-30-awg/) | ~₹7–10/m per conductor | For early harnesses, twist a matched pair consistently. For final CAN-FD, use proper flexible ~120 Ω twisted pair if signal-integrity testing demands it. |
| Heat-shrink | assortment | [Robu — heat-shrink kits](https://robu.in/product-category/heat-shrink-combos/) | ~₹150+ starter kits | Commodity. |
| Braided sleeve / strain relief | assortment | [Robu — tubing/sleeve](https://robu.in/product-category/heat-shrink-tubing-sleeve/) | commodity | Final sleeve diameter waits for the real bundle. |
| Main fuse + holder | 2 | [Robu — fuse kits/holders](https://robu.in/product-category/fuse-kits/) | commodity | Do not freeze fuse current until whole-leg/whole-robot current is measured. |
| E-stop operator switch | 1 | [Robocraze — 22 mm mushroom E-stop](https://robocraze.com/products/ywbl-wh-mushroom-emergency-stop-push-button-switch-22mm) | ~₹100-class reference | **Operator control only.** It should command the DC-rated power switching path, not carry the whole motor bus. |

## D. Deliberately WAIT — no purchase link yet

These entries are in the BOM, but selecting a product now would be false precision and could create an unsafe or incompatible purchase.

| Item | Why no product is recommended yet |
|---|---|
| Logic DC/DC | Final SBC/peripheral load and regenerative bus overshoot are not frozen. Select only after the 24 V bus envelope is measured. |
| Power switch / contactor | Must be DC-rated for measured current/inrush and the final E-stop architecture. Do not buy an arbitrary AC contactor or automotive relay. |
| Bulk bus capacitor bank / clamp / brake resistor | Must be sized from measured bus excursion and the actual tether/source impedance. This is safety-critical and design-dependent. |
| Final fuse value | Depends on measured current and fault strategy. |
| Final tether gauge/length | The current 14 AWG / ~3 m figure is a starting point; verify voltage drop and mechanical drag. |
| Branch connector count | Depends on final harness routing. |
| Tether boom / gantry | Mechanical support layout is not frozen. A shop-built frame or spring-balancer arrangement is likely cheaper than buying a dedicated robot gantry. |

## E. Development equipment

| Item | Recommendation / source | Note |
|---|---|---|
| Bench supply | **Do not buy the old 30 V / 10 A recommendation as the robot's final source.** It is useful for commissioning only. The current robot can demand ~32 A peak at 24 V and can regenerate into the bus. Final source selection belongs with the capacitor/clamp/brake strategy. |
| USB-CAN-FD | [Sharvi — Waveshare USB-CAN-FD](https://sharvielectronics.com/product/usb-can-fd-industrial-grade-can-can-fd-bus-data-analyzer-usb-to-can-fd-adapter-can-can-fd-bus-communication-interface-card-waveshare/) | Same unit as core BOM. |
| PA12-CF-capable 3D printer | Buy only a machine with an enclosure, hardened nozzle and suitable hotend; the process also needs an actively dried filament path. | The structural CAD assumes 0.6 mm nozzle / four perimeters for 2.4 mm walls. Do not casually substitute a 0.4 mm process without revisiting the print specification. |
| Filament dryer | Active dryer capable of feeding the printer while maintaining nylon drying temperature | PA12-CF must be dried before printing and kept dry during printing. |
| Digital caliper | [Insize India](https://www.insizeindia.in/caliper-1.html) | Prefer a credible metrology brand; this project depends on received hardware dimensions. |
| Luggage/load scale | [Slovic 50 kg scale](https://slovic.com/products/slovic-50kg-digital-luggage-scale-with-lcd-indicator-black-silver-travel-friendly) | Cheap static torque test instrument; calibrate against known masses. |
| Logic analyser | [Robokits — 24 MHz 8-channel](https://robokits.co.in/programmers/logic-analyser/usb-logic-analyzer-24m-8ch-debug-tool?cPath=12) | MCU-side debug. Use an oscilloscope for CAN physical-layer integrity. |

## F. Retired items — do not buy

The earlier India sourcing pass contained valid links for these at the time, but they no longer belong to the robot and are intentionally omitted from the active shopping list:

- 8 × 8 mm carbon-fibre tubes
- structural epoxy for tube bonding
- M4 structural hardware
- FSR402 sensors
- 6S LiPo battery
- LiPo balance charger / LiPo storage setup

## Recommended first order

A low-regret first procurement batch is:

1. 2 × DM-J3507-2EC 24 V + 2 or more spare OEM 8-pin power/CAN pigtails.
2. 1 × USB-CAN-FD adapter.
3. 2 × WeAct STM32G474CEU6 boards.
4. 4 × CAN-FD transceivers.
5. 1 × 7Semi BNO085 Nano (buy the second only after confirming the first board/connector geometry in the torso).
6. 6 × 6800-2RS bearings.
7. Short 10 mm precision shaft stock for six journals.
8. One 1 kg spool of PA12-CF for coupons and the first leg, plus the required printer/drying setup if not already available.
9. M3 fasteners to the exact BOM §12 schedule, Loctite 638 and Loctite 243.
10. 10 × FSR400 only when the foot load-path detail is ready to prototype.

## Sources re-checked on 2026-08-30

- 7Semi BNO085 Nano: 11 × 10 × 6 mm; Indian stock around ₹2.1k at Evelta/Robocraze.
- Robokits original AMASS XT60: ₹54/pair; XT30: ₹41/pair.
- Moglix Loctite 638: ~₹713/50 ml; Loctite 243: ~₹742/50 ml.
- Aryabot FSR400: ~₹208.
- QIDI PA12-CF: ~₹4,200 reference through the India storefront/listing of 3D Printers Depot.
- Fastdep 10 mm hard-chrome linear shaft: ₹498/m reference, but sold out at check time.
- IndustryBuying MonotaRO 6800-2RS 10 × 19 × 5: ~₹907 each; use as a geometry/source reference and compare with local bearing suppliers before purchase.

The purchasing document should be refreshed whenever a CAD change retires, resizes or adds a BOM line, rather than copying old source links forward mechanically.
