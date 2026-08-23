# Provisional Bill of Materials — India Hobbyist Build

**Status:** provisional / pre-knee-design  
**Sourcing check:** 2026-08-23  
**Project baseline:** 380 mm, 8-DOF torque-controlled biped using DAMIAO DM-J3507-2EC actuators.

This BOM is intentionally split between parts that should be sourced early and commodity parts that should remain flexible until the CAD is mature. Prices are indicative and can change. Imported prices exclude shipping, customs duty, IGST, payment/FX charges, and courier handling unless explicitly stated.

## Sourcing risk legend

- 🔴 **High** — specialist/imported; can become a schedule blocker. Source early.
- 🟠 **Medium** — available, but exact variant/geometry may have lead-time or compatibility issues.
- 🟢 **Low** — commodity or readily available from Indian suppliers. Do not over-constrain the design around a particular listing.

## 1. Core BOM

| Subsystem | Qty | Provisional part / specification | Indicative unit price | India availability | Risk | When to buy | Notes |
|---|---:|---|---:|---|:---:|---|---|
| Actuator | 8 | **DAMIAO DM-J3507-2EC, 24 V** | Foxtech **US$89–95**; Indian trader listings can be substantially higher | Specialist/import | 🔴 | **Buy 2 now; remaining 6 after actuator/knee validation** | 7:1 low-ratio servo, integrated driver, dual encoders, CAN/CAN-FD, torque feedback/control. Foxtech package includes 3-pin power/CAN and 8-pin tuning cables plus STEP model. |
| Actuator power/CAN pigtail | 10–12 | SH1.0 3-pin compatible harness, preferably OEM DAMIAO | Usually supplied with actuator | Exact connector is less common locally | 🟠 | **Order spares with motors** | Avoid having the project blocked by tiny proprietary-ish harnesses. |
| Actuator tuning pigtail | 2–3 | SH1.0 8-pin tuning cable | Usually supplied with actuator | Specialist | 🟠 | With motors | Two/three are enough; not required per joint in the finished robot. |
| USB-CAN-FD debug interface | 1 | Waveshare USB-CAN/CAN-FD or DAMIAO-compatible interface | ~₹8k class locally for Waveshare | Available in India | 🟠 | With first 2 motors | Development/debug tool. Final robot should use MCU-native CAN-FD rather than depend on this adapter. |
| Realtime MCU dev board | 2 | **STM32G474** development/core board | ~**₹859** for WeAct board on Robu; Nucleo alternatives ~₹1.9k+ | Easy | 🟢 | Early | Buy two so one can remain on bench while the other is integrated. Native FDCAN is a good fit. |
| CAN-FD transceiver | 4 | MCP2542FD / TCAN1042-class, 3.3 V MCU compatible | Typically low hundreds of rupees or less per channel | Easy via Indian electronics distributors | 🟢 | Early | Two installed + spares. Consider isolation only if testing shows it useful. |
| Main IMU | 1–2 | **BNO085** breakout | ~₹2.5–4k breakout; bare IC ~₹1.2–1.3k from Mouser/DigiKey India | Easy | 🟢 | Early | Breakout preferred for V0; move to PCB integration later. |
| Carbon-fibre leg members | 2 × 1 m | **8 × 8 mm OD pultruded square CF tube**, Robu listing has 6.5 mm round ID | **₹1,009 / 1 m** | Available domestically | 🟢 | **Buy now** | Measure actual OD, straightness and wall geometry; feed measurements back into CAD before final tube sockets. Two metres gives prototype/spare material. |
| PETG filament | 1–2 kg | Quality PETG, 1.75 mm | ~₹800–1,500/kg typical | Very easy | 🟢 | As needed | Prototype joint structures. Print coupons before trusting published material data. |
| TPU filament / sole material | 0.25–0.5 kg | TPU ~95A | ~₹400–1,000 equivalent quantity | Easy | 🟢 | Later | Replaceable sole / traction layer. |
| Support bearings | ~8–12 | **TBD after knee CAD**; prefer common 6800/6900/miniature metric families | Typically ~₹50–500 ea depending brand | Very easy | 🟢 | **Do not buy yet** | Select after real actuator STEP, axle and yoke geometry are resolved. Prefer common Indian-stock sizes over exotic thin-section bearings. |
| Joint axles | ~8 | **TBD** precision shaft/shoulder-bolt architecture | ~₹50–500+ depending solution | Standard shaft stock easy; exact shoulder screws less consistent | 🟠 | After knee CAD | Prefer standard hardened/SS shaft stock plus simple retention over rare imported shoulder-bolt sizes. |
| M3 fasteners | assortment | SHCS, washers, nyloc nuts, through-bolts | ~₹500–1,000 starter assortment | Very easy | 🟢 | Anytime | Structural joints should preferentially use through-bolts/locknuts, not heat-set inserts alone. |
| M4 structural hardware | assortment | High-tensile SHCS / axle-related hardware as selected | ~₹300–1,000 assortment | Easy | 🟢 | After joint design | Keep to standard metric lengths where possible. |
| Heat-set inserts | assortment | M3 brass inserts | ~₹200–500 | Very easy | 🟢 | Anytime | Covers/light-duty interfaces only; not primary structural load paths. |
| Structural epoxy | 1 | Slow/medium-cure epoxy suitable for CF-to-printed-part bond | ~₹300–1,000 | Easy | 🟢 | Before leg assembly | Bonding should be supplemented by positive mechanical tube retention. |
| Threadlocker | 1 | Loctite 243 or equivalent medium strength | ~₹300–700 | Easy | 🟢 | Before assembly | Verify compatibility where screws enter plastics/inserts. |
| Foot pressure sensors | 10 | FSR402 or equivalent (8 installed + 2 spare) | ~₹200 ea class | Easy | 🟢 | Later | Good for V0 contact/COP indication; not precision force measurement. |
| LiPo battery | 1–2 | **6S 2200 mAh, >=40 C, XT60** | **~₹2,659** for GenX 6S 2200 mAh 40C/80C | Easy domestically | 🟢 | Later | 22.2 V nominal / 25.2 V full. Buy battery in India rather than import. Final capacity may change after measured current consumption. |
| LiPo balance charger | 1 | Reputable 1–6S balance charger | ~₹2,500–5,000 | Easy | 🟢 | Before battery testing | Do not use a no-name charger for repeated prototype work. |
| Main connector | 3–4 pairs | Genuine AMASS XT60 | ~₹50–150/pair | Very easy | 🟢 | Anytime | Battery/main power disconnect. |
| Branch connectors | 10–12 pairs | XT30 or locking equivalent, final choice TBD | ~₹30–100/pair | Easy | 🟢 | After harness design | Avoid bulky connectors at moving joints if direct harness routing is cleaner. |
| Main bus wire | 3 m | 14 AWG high-strand silicone wire | ~₹50–150/m | Easy | 🟢 | Later | Size against measured simultaneous peak current and cable length. |
| Motor branch wire | 5–8 m | 16–18 AWG high-strand silicone wire | ~₹30–100/m | Easy | 🟢 | Later | Final gauge after measured motor current. |
| CAN wiring | 5 m | Flexible twisted pair ~24–26 AWG | Low | Easy | 🟢 | Later | Keep CAN topology/termination deliberate; avoid star wiring unless validated. |
| Logic DC/DC | 1–2 | 6S-compatible buck to 5 V, >=5 A provisional | ~₹300–1,500 | Easy | 🟢 | Early | Use a known-quality module; exact rating depends on SBC/peripherals. |
| Main fuse | 2 | Automotive blade fuse + holder, initial ~20–30 A range | ~₹100–300 | Very easy | 🟢 | Before powered multi-joint tests | Fuse value must be revisited after current measurements. |
| Emergency stop | 1 | Latching mushroom E-stop controlling motor-power contactor/switching path | ~₹300–1,500 depending implementation | Easy | 🟢 | **Before multi-motor tests** | E-stop should remove motor power independently of software. |
| Power switch / contactor | 1 | DC-rated switching solution appropriate for 6S and measured current | TBD | Available | 🟠 | Before full-robot power | Do not assume an AC-rated switch is safe for DC interruption. |
| Bulk bus capacitance / surge handling | TBD | Low-ESR electrolytic bank and/or clamp strategy | TBD | Easy components; design not frozen | 🟠 | After actuator bench tests | Backdrivable motors can regenerate onto the DC bus; log bus-voltage excursions during tests. |
| Heatshrink / braided sleeve / strain relief | assortment | Flexible harness consumables | ~₹500–1,500 total | Very easy | 🟢 | Gradually | Critical around moving joints despite low cost. |

## 2. Source-early shortlist

These are the items most likely to delay the project if left until the mechanical CAD is finished.

### A. DAMIAO DM-J3507-2EC actuators — highest priority

**Recommended action:** source **two 24 V units now**, characterize them, and order the remaining six as soon as the knee architecture is validated.

Current international reference:

- Foxtech DM-J3507-2EC: **US$89–95**
- Product page: https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/
- The listing states that each motor includes:
  - 1 × SH1.0 3-pin power + CAN cable (200 mm)
  - 1 × SH1.0 8-pin tuning cable (200 mm)
  - manual
  - STEP file

India-specific concern:

- Domestic specialist listings exist, but price can be much higher than direct/international channels.
- Treat the actuator as an import/specialist component until a reliable Indian stockist is confirmed.
- When ordering, buy **extra pigtails/connectors** at the same time.

### B. Carbon-fibre square tube — buy early to lock actual geometry

Robu currently lists:

- Pultruded square inner-round carbon-fibre hollow tube
- **8 × 8 mm OD**
- **6.5 mm round ID**
- **1000 mm length**
- **₹1,009**
- Category/source: https://robu.in/product-category/tubes-and-rods/

This is no longer considered a supply blocker, but actual measured dimensions matter to the printed sockets. Buy two lengths and make the CAD fit the material actually received.

### C. Exact DAMIAO connector ecosystem

The motors use small SH1.0 harness connectors. The supplied OEM cables solve the immediate problem, but individual housings/crimps and pre-made replacements can be much more annoying to source than XT/JST commodity parts.

**Recommendation:** obtain at least **two spare motor pigtails** during the actuator purchase and avoid repeatedly disconnecting the motor-side miniature connector during prototyping.

### D. Precision axle solution

India has abundant bearing and shaft stock, but very specific metric shoulder screws can be surprisingly awkward or expensive.

**Design constraint for Opus/Zoo:** prefer:

1. a standard precision/hardened shaft diameter,
2. common metric bearing IDs,
3. simple washers/spacers/circlips or threaded retention,
4. standard M3/M4 fasteners,

rather than designing around an unusual imported shoulder bolt.

Do **not** purchase axles until the real knee cross-section is frozen.

## 3. Components that should not constrain the CAD

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

## 4. Development-only equipment

| Item | Qty | Provisional choice | Priority | Notes |
|---|---:|---|---|---|
| Bench DC supply | 1 | 0–30 V, preferably >=10 A with current limiting | High | Safer initial motor/joint commissioning than a LiPo. Higher-current transient testing may require battery or larger supply later. |
| USB-CAN-FD adapter | 1 | Waveshare or DAMIAO compatible | High | Needed to commission/characterize motors independently of robot firmware. |
| Digital caliper | 1 | 0.01 mm display class | High | Measure received tubes, printed fits, spacers and hardware. |
| Torque test arm | 1 | Printed/metal lever of accurately measured radius | High | Combined with hanging masses/load cell for actuator torque calibration. |
| Luggage/load cell scale | 1 | ~0–20/50 kg range | Medium | Cheap way to validate static joint torque and friction. |
| IR thermometer or thermocouples | 1+ | — | High | Characterize actuator/printed-joint thermal behaviour. |
| Logic analyser / oscilloscope | 1 | Existing if available | Medium | CAN/MCU timing/debug. |
| LiPo-safe charging/storage setup | 1 | LiPo bag/metal storage + charger | High before battery phase | Battery handling safety. |

## 5. Provisional cost envelope

These figures are intentionally broad because actuator shipping/import treatment dominates uncertainty.

| Area | Rough provisional cost |
|---|---:|
| 8 × DM-J3507-2EC at Foxtech list price | **US$712–760 before shipping/import charges** |
| Carbon structure + printed materials + prototype mechanical consumables | **~₹5k–10k** |
| Bearings, axles and fasteners | **~₹3k–8k**, depending final joint stack |
| MCU, CAN, IMU and foot sensors | **~₹6k–12k** |
| USB-CAN-FD development interface | **~₹8k class** |
| Battery + charger | **~₹5k–8k** |
| Wiring, connectors, DC/DC, fuse/E-stop/power hardware | **~₹4k–10k** |

A sensible planning figure for the finished V0 robot and core development electronics is roughly **₹1.0–1.3 lakh before uncertain actuator import/shipping costs**, assuming the motors are acquired near international list price rather than high domestic reseller pricing. This is not a procurement quote.

## 6. Immediate procurement recommendation

Buy now / very soon:

1. **2 × DAMIAO DM-J3507-2EC 24 V**
2. **2+ spare DAMIAO 3-pin power/CAN pigtails**, if available separately
3. **1 × USB-CAN-FD interface**
4. **2 × 1 m 8 × 8 mm Robu carbon-fibre square tubes**
5. **2 × STM32G474 development boards**
6. **1–2 × BNO085 breakouts**
7. Basic M3/M4 fastener assortment
8. PETG for joint prototypes

Wait for knee CAD before buying:

- support bearings
- joint axles / shoulder hardware
- spacers
- final structural fastener lengths

Wait for measured current and final packaging before buying:

- final battery quantity/capacity
- final wire gauges
- final fuse value
- final DC/DC converter
- full cable harness connectors
- power switch/contactor
- regenerative-energy handling components

## 7. Design-for-India sourcing rules

The CAD/design agent should treat the following as explicit constraints:

1. Prefer **standard metric bearings** readily stocked in India.
2. Prefer **standard precision shaft stock** over exotic shoulder bolts.
3. Prefer M3/M4 standard fasteners and commonly stocked lengths.
4. Do not choose a rare component merely to save a few grams unless the benefit is quantified.
5. Maintain at least one domestic or broad-distribution alternative for commodity electronics.
6. Keep actuator-specific connectors/harnesses documented because these are disproportionately likely to cause delays.
7. Once a physical component is purchased, its **measured dimensions override catalogue assumptions** in the CAD.
8. Record supplier, order date, actual landed cost, measured mass and measured dimensions in this BOM as the project progresses.

## 8. Current source references

Checked 2026-08-23:

- DAMIAO DM-J3507-2EC, Foxtech — US$89–95:  
  https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/
- Robu carbon-fibre tubes category; 8 × 8 × 1000 mm square tube shown at ₹1,009:  
  https://robu.in/product-category/tubes-and-rods/
- STM32G474 WeAct board — Robu, observed around ₹859 during sourcing check:  
  https://robu.in/
- BNO085 — available through Indian electronics distributors including Mouser/DigiKey/7Semi and breakout-board retailers.
- GenX 22.2 V 6S 2200 mAh 40C/80C LiPo — observed around ₹2,659 from Robokits India during sourcing check.

Prices and availability are snapshots, not guarantees. Re-check immediately before ordering.
