# Provisional Bill of Materials — India Hobbyist Build

**Status:** revised 2026-08-28 after the stressed-shell rebuild and the decision to run the robot tethered — the carbon tubes, the PETG structure and the whole battery/charger line are retired  
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
| Actuator | 8 | **DAMIAO DM-J3507-2EC, 24 V** | Foxtech **US$89–95**; Indian trader listings can be substantially higher | Specialist/import | 🔴 | **Buy 2 now; remaining 6 after actuator/knee validation** | 7:1 low-ratio servo, integrated driver, dual encoders, CAN/CAN-FD, torque feedback/control. Foxtech package includes the 8-pin power/CAN and 3-pin tuning cables plus STEP model. |
| Actuator power/CAN pigtail | 10–12 | SH1.0 **8-pin** compatible harness, preferably OEM DAMIAO | Usually supplied with actuator | Exact connector is less common locally | 🟠 | **Order spares with motors** | Avoid having the project blocked by tiny proprietary-ish harnesses. |
| Actuator tuning pigtail | 2–3 | SH1.0 **3-pin** tuning cable | Usually supplied with actuator | Specialist | 🟠 | With motors | Two/three are enough; not required per joint in the finished robot. |
| USB-CAN-FD debug interface | 1 | Waveshare USB-CAN/CAN-FD or DAMIAO-compatible interface | ~₹8k class locally for Waveshare | Available in India | 🟠 | With first 2 motors | Development/debug tool. Final robot should use MCU-native CAN-FD rather than depend on this adapter. |
| Realtime MCU dev board | 2 | **STM32G474** development/core board | ~**₹859** for WeAct board on Robu; Nucleo alternatives ~₹1.9k+ | Easy | 🟢 | Early | Buy two so one can remain on bench while the other is integrated. Native FDCAN is a good fit. |
| CAN-FD transceiver | 4 | MCP2542FD / TCAN1042-class, 3.3 V MCU compatible | Typically low hundreds of rupees or less per channel | Easy via Indian electronics distributors | 🟢 | Early | Two installed + spares. Consider isolation only if testing shows it useful. |
| Main IMU | 1–2 | **BNO085** breakout | ~₹2.5–4k breakout; bare IC ~₹1.2–1.3k from Mouser/DigiKey India | Easy | 🟢 | Early | Breakout preferred for V0; move to PCB integration later. |
| ~~Carbon-fibre leg members~~ | — | — | — | — | — | **Do not buy** | **Retired.** The carbon tubes are gone: each limb is now a closed printed shell that carries the load itself. See `PLAN.md` §2. |
| **PA12-CF filament** | 2–3 kg | Carbon-filled PA12, 1.75 mm | ~₹4,000–7,000/kg | Import or specialist | 🟠 | **With the printer** | The structural material. Needs a hardened nozzle, drying, and an enclosed printer. PA6-CF is an acceptable substitute but takes up several times as much water. |
| PETG filament | 1 kg | Quality PETG, 1.75 mm | ~₹800–1,500/kg typical | Very easy | 🟢 | As needed | **Fit mock-ups only.** It creeps under sustained load and softens near 80 °C next to a motor at its continuous limit. Nothing structural. |
| TPU filament / sole material | 0.25–0.5 kg | TPU ~95A | ~₹400–1,000 equivalent quantity | Easy | 🟢 | Later | Replaceable sole / traction layer. |
| Support bearings | 8 + 2 spare | **6800-2RS** — 10 mm bore, 19 mm OD, 5 mm wide | ~₹50–200 ea | Very easy | 🟢 | **Decided; buy anytime** | One per joint, on the far side of the actuator. Common stock size, deliberately chosen over thin-section. |
| Joint journals | 8 + 2 spare | **Ø10 × 8 mm** ground steel or SS shaft stub | ~₹50–200 ea | Standard shaft stock, easy | 🟢 | **Decided** | Seats 2.2 mm into the rotor hub, runs in the 6800. Standard shaft stock cut and faced. |
| Bearing carriers | 8 + 2 spare | Aluminium flanged ring, Ø30 × 3 with a Ø36 × 1.5 flange, Ø19 bore | Turned part, ~₹150–400 ea | Local machining | 🟠 | **After the coupon** | The bearing seat is metal because printed pockets ovalise and this one sets the coaxiality of the whole joint. Bonded into the printed cheek with retaining compound — no screws through a 3 mm printed wall. |
| Retaining compound | 1 | Loctite 638 or equivalent | ~₹600–1,200 | Easy | 🟢 | Before assembly | Bonds the bearing carrier into the cheek bore. Verify plastic compatibility on a coupon first. |
| M3 fasteners | assortment | SHCS, washers, nyloc nuts, through-bolts | ~₹500–1,000 starter assortment | Very easy | 🟢 | Anytime | Structural joints should preferentially use through-bolts/locknuts, not heat-set inserts alone. |
| M4 structural hardware | assortment | High-tensile SHCS / axle-related hardware as selected | ~₹300–1,000 assortment | Easy | 🟢 | After joint design | Keep to standard metric lengths where possible. |
| Heat-set inserts | assortment | M3 brass inserts | ~₹200–500 | Very easy | 🟢 | Anytime | Covers/light-duty interfaces only; not primary structural load paths. |
| ~~Structural epoxy~~ | — | — | — | — | — | **Do not buy** | **Retired** with the carbon tubes. There is no CF-to-printed bond any more. Retaining compound for the bearing carriers replaces it. |
| Threadlocker | 1 | Loctite 243 or equivalent medium strength | ~₹300–700 | Easy | 🟢 | Before assembly | Verify compatibility where screws enter plastics/inserts. |
| Foot pressure sensors | 10 | FSR402 or equivalent (8 installed + 2 spare) | ~₹200 ea class | Easy | 🟢 | Later | Good for V0 contact/COP indication; not precision force measurement. |
| ~~LiPo battery~~ | — | — | — | — | — | **Do not buy** | **Retired: the robot is tethered.** It could not have been bought anyway — the keel between the hip roll actuators is only 63 mm long inside, every off-the-shelf 6S pack is 70–110 mm, and even a single 18650 is 65 mm, so it would have had to be hand-built from pouch cells. Removing it also returns the 190 g that was the whole of the mass headroom. See `PLAN.md` Phase 5a. |
| ~~LiPo balance charger~~ | 1 | — | — | — | — | **Do not buy** | **Retired** with the pack. Only buy one if the robot later goes free-running. |
| **Tether / umbilical** | 1, about 3 m | 2 × 14 AWG silicone power + 24 AWG twisted CAN pair, braided sleeve, ~12 mm OD | ~₹800–2,000 made up | Easy from stock wire | 🟠 | **Before powered standing tests** | Carries 24 V and CAN from the bench supply. `parameters.kcl` holds the 12 mm diameter the keel's entry slot is cut from, and that figure is estimated from these wire sizes, not measured — **measure the made-up cable before printing the pelvis.** 14 AWG is 8.3 milliohm per metre, so 3 m at the 32 A simultaneous peak drops about 0.8 V in each conductor -- 1.6 V round trip off a 24 V bus. Tolerable, but check it against the actuator's voltage window and go heavier or shorter if it is marginal. |
| **Tether boom / gantry** | 1 | Overhead arm or spring balancer taking the cable's weight | Shop-built | Your labour | 🟠 | **Before powered standing tests** | Not optional. An unsupported umbilical hangs a moving, unmodelled load on a 2.165 kg biped whose hip roll actuator is already at 88 per cent of continuous in single support. Not yet designed. |
| Main connector | 3–4 pairs | Genuine AMASS XT60 | ~₹50–150/pair | Very easy | 🟢 | Anytime | Tether disconnect at the robot and at the supply. |
| Branch connectors | 10–12 pairs | XT30 or locking equivalent, final choice TBD | ~₹30–100/pair | Easy | 🟢 | After harness design | Avoid bulky connectors at moving joints if direct harness routing is cleaner. |
| Main bus wire | 3 m | 14 AWG high-strand silicone wire | ~₹50–150/m | Easy | 🟢 | Later | Size against measured simultaneous peak current and cable length. |
| Motor branch wire | 5–8 m | 16–18 AWG high-strand silicone wire | ~₹30–100/m | Easy | 🟢 | Later | Final gauge after measured motor current. |
| CAN wiring | 5 m | Flexible twisted pair ~24–26 AWG | Low | Easy | 🟢 | Later | Keep CAN topology/termination deliberate; avoid star wiring unless validated. |
| Logic DC/DC | 1–2 | 24 V-bus buck to 5 V, >=5 A provisional | ~₹300–1,500 | Easy | 🟢 | Early | Use a known-quality module; exact rating depends on SBC/peripherals. Rate it for the supply's full range plus whatever the bus overshoots to under regeneration, not for 24 V nominal. |
| Main fuse | 2 | Automotive blade fuse + holder, initial ~20–30 A range | ~₹100–300 | Very easy | 🟢 | Before powered multi-joint tests | Fuse value must be revisited after current measurements. |
| Emergency stop | 1 | Latching mushroom E-stop controlling motor-power contactor/switching path | ~₹300–1,500 depending implementation | Easy | 🟢 | **Before multi-motor tests** | E-stop should remove motor power independently of software. |
| Power switch / contactor | 1 | DC-rated switching solution appropriate for a 24 V bus and measured current | TBD | Available | 🟠 | Before full-robot power | Do not assume an AC-rated switch is safe for DC interruption. |
| **Bulk bus capacitance** | 1 bank | Low-ESR electrolytic bank at the robot end of the tether, plus a clamp or brake-resistor strategy | TBD until sized | Easy components | 🔴 | **Before multi-joint powered tests** | **Now required, not deferred.** The pack used to be the bus's energy store and its only sink for regeneration; a tether is neither, and a bench supply generally cannot sink current at all. Eight backdrivable actuators peak near 32 A together and push current back whenever a limb is driven by gravity or the ground. Size it from measured bus excursion and the real tether length — the mass budget carries a 60 g allowance for the bank, fuse and terminal together, which is an estimate. It lives in the keel, reserved as 38 × 62 × 30 in `payload_envelopes.kcl`. |
| Heatshrink / braided sleeve / strain relief | assortment | Flexible harness consumables | ~₹500–1,500 total | Very easy | 🟢 | Gradually | Critical around moving joints despite low cost. |

## 2. Source-early shortlist

These are the items most likely to delay the project if left until the mechanical CAD is finished.

### A. DAMIAO DM-J3507-2EC actuators — highest priority

**Recommended action:** source **two 24 V units now**, characterize them, and order the remaining six as soon as the knee architecture is validated.

Current international reference:

- Foxtech DM-J3507-2EC: **US$89–95**
- Product page: https://store.foxtech.com/dm-j3507-2ec-24v-mit-driven-brushless-servo-joint-motor/
- The listing states that each motor includes:
  - 1 × SH1.0 8-pin power + CAN cable (200 mm)
  - 1 × SH1.0 3-pin tuning cable (200 mm)
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

**Pin counts corrected 2026-08-23.** The manual's parts list on page 3 states a 3-pin
power/CAN cable and an 8-pin tuning cable. Its own pinout figures on page 4 show the
opposite: power/CAN is **8-pin** (3 x VCC, 3 x GND, CAN_L, CAN_H) and the debug UART is
**3-pin** (GND, RX, TX). The figures are authoritative, and tripling VCC and GND is
consistent with the 4 A peak supply current. The rows above use the figure values.

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
| Bench DC supply | 1 | 0–30 V with current limiting; **size for the real robot, not just for commissioning** | **Critical** | This is now the robot's only power source, not a commissioning convenience. Continuous draw across eight actuators is about 10 A, but the simultaneous peak is near 32 A at 24 V — roughly 770 W. Decide deliberately whether to buy for the peak or to rely on the bulk capacitor bank to ride it out, and note that most bench supplies cannot *sink* the current a backdriven limb pushes back. |
| USB-CAN-FD adapter | 1 | Waveshare or DAMIAO compatible | High | Needed to commission/characterize motors independently of robot firmware. |
| Digital caliper | 1 | 0.01 mm display class | High | Measure received tubes, printed fits, spacers and hardware. |
| Torque test arm | 1 | Printed/metal lever of accurately measured radius | High | Combined with hanging masses/load cell for actuator torque calibration. |
| Luggage/load cell scale | 1 | ~0–20/50 kg range | Medium | Cheap way to validate static joint torque and friction. |
| IR thermometer or thermocouples | 1+ | — | High | Characterize actuator/printed-joint thermal behaviour. |
| Logic analyser / oscilloscope | 1 | Existing if available | Medium | CAN/MCU timing/debug. |
| ~~LiPo-safe charging/storage setup~~ | — | — | — | **Retired** with the pack. Reinstate before any free-running build. |

## 5. Provisional cost envelope

These figures are intentionally broad because actuator shipping/import treatment dominates uncertainty.

| Area | Rough provisional cost |
|---|---:|
| 8 × DM-J3507-2EC at Foxtech list price | **US$712–760 before shipping/import charges** |
| Carbon structure + printed materials + prototype mechanical consumables | **~₹5k–10k** |
| Bearings, axles and fasteners | **~₹3k–8k**, depending final joint stack |
| MCU, CAN, IMU and foot sensors | **~₹6k–12k** |
| USB-CAN-FD development interface | **~₹8k class** |
| ~~Battery + charger~~ | **retired — tethered** |
| Tether, boom and bulk capacitor bank | **~₹3k–6k**, excluding the bench supply |
| Wiring, connectors, DC/DC, fuse/E-stop/power hardware | **~₹4k–10k** |

A sensible planning figure for the finished V0 robot and core development electronics is roughly **₹1.0–1.3 lakh before uncertain actuator import/shipping costs**, assuming the motors are acquired near international list price rather than high domestic reseller pricing. This is not a procurement quote.

## 6. Immediate procurement recommendation

Buy now / very soon:

1. **2 × DAMIAO DM-J3507-2EC 24 V**
2. **2+ spare DAMIAO 8-pin power/CAN pigtails**, if available separately
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

- final tether gauge and length
- bulk capacitor bank size
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
- ~~GenX 22.2 V 6S 2200 mAh 40C/80C LiPo — observed around ₹2,659 from Robokits India during sourcing check.~~ Kept only as a record of the sourcing check; the robot is tethered and buys no pack.

Prices and availability are snapshots, not guarantees. Re-check immediately before ordering.

## 9. Knee actuator-interface hardware — August 24, 2026

| Item | Qty per knee | Current specification | Estimated mass | Sourcing / status | Notes |
|---|---:|---|---:|---|---|
| Support bearing | 1 | **6800-2RS**, 10 x 19 x 5 mm | 5.0 g | Commodity; KG Bearing India lists 6800 with 1.83 kN dynamic and 0.925 kN static rating | Current rear-bracket module selection. Use sealed 2RS equivalent from NTN, Koyo, SKF, or a reputable Indian supplier. |
| Journal | 1 | Ø10 x 8 mm hardened ground-steel stub | 4.93 g | Commodity precision shaft stock | Modelled as an 8 mm stub seated 2.2 mm into the hub. Retention/fit requires printed coupons and hardware review. |
| Output screws | 6 | M3 x 6 socket-head cap screws | ~2.4 g total | Commodity | Ø6.0 x 3.2 mm hub counterbores; approximately 4.2 mm engagement in the 5 mm output threads. |
| Rear bracket screws | 4 | M3 x 12 fully threaded socket-head cap screws + 1 mm washers | ~4 g total | Commodity | Approximately 3.8 mm engagement after 4 mm bracket, washer, and 3.2 mm rear cover. |
| Printed output hub + fixed bracket + stop pads | 1 set | PETG, current `knee_module.kcl` | 18.37 g | Print-test required | KCL volume calculation at 1.27 g/cm³; not a slicer mass. |
| **Complete module** | **1** | Printed structure + bearing + journal + fasteners | **34–35 g** | Design estimate only | One knee is now modelled. Its all-eight absolute mass is not a robot delta; reconcile it with the legacy yoke's unresolved hardware mass before any rollout. |

**Prototype purchasing recommendation:** buy two 6800-2RS bearings, a short length of 10 mm hardened shaft, and M3 x 6 / M3 x 12 fasteners with washers for one knee plus spares. Do not bulk-buy hardware for all eight joints until the new knee is physically weighed and the mass budget is revisited.

## 10. Carbon-tube link hardware — SUPERSEDED, August 28, 2026

> The carbon tubes and their bonded sockets were removed the same day, when the
> robot moved to a stressed-shell architecture. This section is kept only as the
> record of what that joint would have cost. Section 11 replaces it, and the
> 8 x 8 mm carbon tube in section 1 is no longer needed.



Each link — two thighs and two shins — now ends in a bonded and bolted socket
rather than a butt joint, so the tubes need drilling and each end needs one
screw and one captive nut per tube.

| Item | Qty per link | Current specification | Estimated mass | Sourcing / status | Notes |
|---|---:|---|---:|---|---|
| Clamp screws | 4 | M3 x 20 socket-head cap screws | ~6.6 g total | Commodity | One per tube per end. Crosses the 19.5 mm socket and the drilled tube, and finishes flush with the rear face. |
| Clamp nuts | 4 | M3 hex nuts, ISO 4032, 5.5 mm across flats | ~1.6 g total | Commodity | Dropped into a 5.6 x 5.6 x 2.6 mm trap on the rear face; a nyloc equivalent needs a 4 mm trap and has not been modelled. |
| Structural epoxy | — | Slow/medium-cure, CF to PETG | negligible | Already listed in section 1 | Bond area is 4 x 8.3 x 16 mm = 531 mm² per tube end. |
| Printed sockets, thigh | 2 | PETG, `tube_link.kcl` at 9 mm tube centres | 28.6 g the pair | Print-test required | KCL volume 22 549 mm³ at 1.27 g/cm³; not a slicer mass. |
| Printed sockets, shin | 2 | PETG, `tube_link.kcl` at 7.5 mm tube centres | 25.4 g the pair | Print-test required | KCL volume 19 975 mm³ at 1.27 g/cm³. |
| Carbon tube | 2 | 8 x 8 x 1 mm square, cut to 51 mm | 4.5 g the pair | Already listed in section 1 | Was 47 mm; the tube now runs into both pockets. Each end needs one Ø3.4 cross hole 8 mm in from the tube end. |

Fasteners come to about 8.2 g per link, so roughly **33 g across the four
links** — a large bite out of the 30-45 g M3 hardware allowance in `NOTES.md`,
which was written before any of these joints existed. That allowance needs
revisiting once the yoke and hip fasteners are specified too.

**Prototype purchasing recommendation:** the M3 assortment already listed covers
this, but add M3 x 20 screws specifically — they are longer than anything else
on the robot. Drill the tube cross holes on a jig, not freehand: the hole is
Ø3.4 through a face only 8 mm wide, so a drill that wanders by 2 mm breaks out
through the 1 mm side wall.

## 11. Stressed-shell hardware — August 28, 2026

The carbon tubes are gone and so are the printed yokes. What the robot buys now
is the same three metal parts at each of the eight joints, plus fasteners.

| Item | Qty per joint | Specification | Estimated mass | Sourcing / status | Notes |
|---|---:|---|---:|---|---|
| Support bearing | 1 | **6800-2RS**, 10 x 19 x 5 mm | 5.0 g | Commodity | Unchanged from the knee module. |
| Journal | 1 | Ø10 x 8 mm hardened ground steel | 4.9 g | Commodity shaft stock | Seated 2.2 mm into the rotor hub. |
| Bearing carrier | 1 | Ø30 x 3 mm aluminium ring with a Ø36 x 1.5 mm flange, Ø19 bore | 6.4 g | Turned part, or a stock shoulder bush | Bonded into the cheek with retaining compound. **The one part that needs a lathe** -- flag if that is not available and it becomes a stock bush plus a printed retainer. |
| Output screws | 6 | M3 x 8 socket head | ~2.8 g | Commodity | Ø6 x 3.2 counterbores in the hub; into the actuator's 5 mm output threads. |
| Rear screws | 4 | M3 x 12 socket head + washers | ~4 g | Commodity | Through the 3 mm cheek, the 3.2 mm rear cover, into 4 mm of thread. |
| **Per joint** | | | **≈ 23 g** | | Times eight: **184 g** |

Printed parts, PA12-CF at 1.06 g/cm3, measured from the CAD:

| Part | Each | Count | Total |
|---|---:|---:|---:|
| Limb, thigh or shin — the same part at two lengths | 46.3 g | 4 | 185 g |
| Hip carrier | 37.2 g | 2 | 74 g |
| Foot tray with sole and sensor pads | 74.7 g | 2 | 149 g |
| Pelvis and torso shell with removable cover | 187.3 g | 1 | 187 g |
| **Printed structure** | | | **596 g** |

With the metal, fasteners, electronics and a 60 g allowance for the power-entry
block — capacitors, fuse and terminal, since the robot is tethered and carries no
battery — it comes to **2 147 g against a 2 300 g ceiling**, which is 153 g of
headroom where the battery build had 5 g. Run `uv run tools/mass.py` rather than
trusting this table: it measures every printed part on the engine and rolls the
whole robot up against the ceiling.

**The bearing count stayed at eight.** A forked rotor was drawn for the hip
pitch and knee joints, which would have needed twelve sets, and then dropped —
see `docs/PLAN.md` decision 8. Nothing on this list changed as a result, which
is the point of having kept the same three bought parts on both sides.

**Material change.** PETG is no longer the structural material. PA12-CF is
specified instead: it resists creep, tolerates sitting next to a motor at its
continuous limit, and at 1.06 g/cm3 is lighter than PETG. It needs a hardened
nozzle, a dry filament path and an enclosed printer, none of which the PETG
prototype required, so budget for that before ordering material. PA6-CF is an
acceptable substitute if PA12-CF is hard to source domestically, at the cost of
much greater moisture uptake. PETG stays useful for fit mock-ups.

**No longer needed:** the 8 x 8 mm carbon square tube in section 1, the M3 x 20
clamp screws and captive nuts from section 10, and the structural epoxy for
tube bonding. Retaining compound for the bearing carriers replaces it.

**Prototype purchasing recommendation:** buy for one leg first — four bearings,
four journals, four carriers, and the M3 assortment — and print one complete leg
before committing to two. The carrier is the only non-commodity item; get a
quote for four before designing around it.
