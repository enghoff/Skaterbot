# Provisional Bill of Materials — India Hobbyist Build

**Status:** revised 2026-08-30 against the flat-plate limb. Reconciled part by part with the model: bearing, journal and carrier counts halved to four sets; the M3 schedule is now exact rather than an assortment (section 12); M4 retired; the control board, IMU and foot sensor are specified against the volumes actually reserved for them, and three of those do not currently fit. Earlier revisions retired the carbon tubes, the PETG structure and the battery/charger line.  
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
| Realtime MCU dev board | 2 | **WeAct STM32G474CEU6 core board, 36.3 × 28.1 mm** | ~**₹859** on Robu | Easy | 🟢 | Early | Buy two so one can stay on the bench while the other is integrated. Native FDCAN is a good fit. **The board is now specified, not the family:** the torso reserves 76 × 46 × 12 mm for it and the WeAct fits with room alongside for the transceivers. **A Nucleo-G474RE does not fit** — Nucleo-64 boards are 82.5 × 70 mm, which is 6.5 mm too long and 24 mm too wide for that reservation, and too wide for the SBC reservation as well. Check the assembled height against the 12 mm reserved before committing to stacked headers. |
| CAN-FD transceiver | 4 | MCP2542FD / TCAN1042-class, 3.3 V MCU compatible | Typically low hundreds of rupees or less per channel | Easy via Indian electronics distributors | 🟢 | Early | Two installed + spares. Consider isolation only if testing shows it useful. |
| Main IMU | 1–2 | **BNO085** breakout | ~₹2.5–4k breakout; bare IC ~₹1.2–1.3k from Mouser/DigiKey India | Easy | 🟢 | Early | Breakout preferred for V0; move to PCB integration later. **Does not currently fit.** The Adafruit BNO085 breakout is 25.6 × 22.7 × 4.6 mm and `payload_envelopes.kcl` reserves 22 × 22 × 6, so it is 3.6 mm over in length and 0.7 mm over in width. Either grow the reservation to about 28 × 25 × 6 or plan on the bare IC. |
| ~~Carbon-fibre leg members~~ | — | — | — | — | — | **Do not buy** | **Retired.** The carbon tubes are gone, and so is the closed shell that briefly replaced them: each limb is now a flat printed plate that carries the load itself. See `PLAN.md` §2. |
| **PA12-CF filament** | 2–3 kg | Carbon-filled PA12, 1.75 mm | ~₹4,000–7,000/kg | Import or specialist | 🟠 | **With the printer** | The structural material. Needs a hardened nozzle, drying, and an enclosed printer. PA6-CF is an acceptable substitute but takes up several times as much water. |
| PETG filament | 1 kg | Quality PETG, 1.75 mm | ~₹800–1,500/kg typical | Very easy | 🟢 | As needed | **Fit mock-ups only.** It creeps under sustained load and softens near 80 °C next to a motor at its continuous limit. Nothing structural. |
| TPU filament / sole material | 0.25–0.5 kg | TPU ~95A | ~₹400–1,000 equivalent quantity | Easy | 🟢 | Later | Replaceable sole / traction layer. |
| Support bearings | 4 + 2 spare | **6800-2RS** — 10 mm bore, 19 mm OD, 5 mm wide | ~₹50–200 ea | Very easy | 🟢 | **Decided; buy anytime** | **Four, not eight.** Only the hip roll and the hip pitch are straddled now; the knee and the ankle bolt the limb straight to the actuator and have no far bearing. Common stock size, deliberately chosen over thin-section. |
| Joint journals | 4 + 2 spare | **Ø10 × 8 mm** ground steel or SS shaft stub | ~₹50–200 ea | Standard shaft stock, easy | 🟢 | **Decided** | Seats 2.2 mm into the rotor hub, runs in the 6800. Standard shaft stock cut and faced. |
| Bearing carriers | 4 + 2 spare | Aluminium flanged ring, Ø30 × 3 with a Ø36 × 1.5 flange, Ø19 bore | Turned part, ~₹150–400 ea | Local machining | 🟠 | **After the coupon** | The bearing seat is metal because printed pockets ovalise and this one sets the coaxiality of the whole joint. Bonded into the printed cheek with retaining compound — no screws through a 3 mm printed wall. |
| Retaining compound | 1 | Loctite 638 or equivalent | ~₹600–1,200 | Easy | 🟢 | Before assembly | Bonds the bearing carrier into the cheek bore. Verify plastic compatibility on a coupon first. |
| **M3 fasteners** | 80 + spares | Socket-head cap screws in three lengths, plus washers — **see section 12 for the exact schedule** | ~₹500–1,000 | Very easy | 🟢 | Anytime | No longer an assortment: the joint interfaces fix the count and the lengths. 48 × output, 16 × M3 × 14, 16 × M3 × 12, 32 washers. Buy 100 of each length. |
| ~~M4 structural hardware~~ | — | — | — | — | — | **Do not buy** | **Retired.** There is no M4 anywhere on the robot. Every printed interface is M3 on one of the actuator's two bolt patterns, and the only shaft is the Ø10 journal. Confirmed by search across the whole model. |
| Heat-set inserts | assortment | M3 brass inserts | ~₹200–500 | Very easy | 🟢 | Anytime | Covers/light-duty interfaces only; not primary structural load paths. |
| ~~Structural epoxy~~ | — | — | — | — | — | **Do not buy** | **Retired** with the carbon tubes. There is no CF-to-printed bond any more. Retaining compound for the bearing carriers replaces it. |
| Threadlocker | 1 | Loctite 243 or equivalent medium strength | ~₹300–700 | Easy | 🟢 | Before assembly | Verify compatibility where screws enter plastics/inserts. |
| Foot pressure sensors | 10 | **FSR400** (8 installed + 2 spare) — *not* FSR402, see note | ~₹200 ea class | Easy | 🟢 | Later | Good for V0 contact/COP indication; not precision force measurement. **Corrected against the CAD.** `foot.kcl` models four 10 × 10 mm seats per foot, and an FSR402 is Ø18.28 mm overall — it does not fit. The smaller FSR400 does. If the FSR402's larger active area is wanted instead, the seats have to grow to about 20 mm square and the foot's rib spacing has to be re-checked. Also unresolved: the seats currently sit inside the tray floor rather than under the sole, so how the load actually reaches the sensor is not yet designed. |
| ~~LiPo battery~~ | — | — | — | — | — | **Do not buy** | **Retired: the robot is tethered.** It could not have been bought anyway — the keel between the hip roll actuators is only 63 mm long inside, every off-the-shelf 6S pack is 70–110 mm, and even a single 18650 is 65 mm, so it would have had to be hand-built from pouch cells. Removing it also returns the 190 g that was the whole of the mass headroom. See `PLAN.md` Phase 5a. |
| ~~LiPo balance charger~~ | 1 | — | — | — | — | **Do not buy** | **Retired** with the pack. Only buy one if the robot later goes free-running. |
| **Tether / umbilical** | 1, about 3 m | 2 × 14 AWG silicone power + 24 AWG twisted CAN pair, braided sleeve, ~12 mm OD | ~₹800–2,000 made up | Easy from stock wire | 🟠 | **Before powered standing tests** | Carries 24 V and CAN from the bench supply. `parameters.kcl` holds the 12 mm diameter the keel's entry slot is cut from, and that figure is estimated from these wire sizes, not measured — **measure the made-up cable before printing the pelvis.** 14 AWG is 8.3 milliohm per metre, so 3 m at the 32 A simultaneous peak drops about 0.8 V in each conductor -- 1.6 V round trip off a 24 V bus. Tolerable, but check it against the actuator's voltage window and go heavier or shorter if it is marginal. |
| **Tether boom / gantry** | 1 | Overhead arm or spring balancer taking the cable's weight | Shop-built | Your labour | 🟠 | **Before powered standing tests** | Not optional. An unsupported umbilical hangs a moving, unmodelled load on a 2.05 kg biped whose hip roll actuator is already at 88 per cent of continuous in single support. Not yet designed. |
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

### B. Carbon-fibre square tube — RETIRED, August 28, 2026

Nothing to buy. The carbon tubes went when the limbs became printed structure,
and the flat-plate limb that replaced the stressed shell does not reinstate
them. The Robu listing this section used to carry is left out deliberately so
it cannot be ordered by habit.

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

- M3 fasteners
- 6800/6900-series and common miniature bearings
- PA12-CF, PETG and TPU
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
| **3D printer, PA12-CF capable** | 1 | Enclosed chamber, hardened nozzle, dried-filament path; 0.6 mm nozzle assumed by the 2.4 mm walls | **Critical** | Not optional and not a detail. Every structural part on the robot is PA12-CF, which needs all three of those; a PETG-class open printer cannot make this robot. The wall thicknesses in the model are drawn as four perimeters of a 0.6 mm nozzle, so changing nozzle size changes what the walls mean. |
| Filament dryer | 1 | Active dryer able to hold the spool at temperature while printing | **Critical** | Nylon is hygroscopic enough that a wet spool prints visibly weaker parts, and layer strength is already the limiting property on this design. |
| Digital caliper | 1 | 0.01 mm display class | High | Measure printed fits, the made-up tether, spacers and hardware. |
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
| Printed materials + prototype mechanical consumables | **~₹10k–18k** — PA12-CF is several times the price of PETG, and a PA12-CF-capable printer is a separate purchase |
| Bearings, journals, carriers and fasteners | **~₹3k–6k** — the joint stack is frozen and the counts are now four sets, not eight |
| MCU, CAN, IMU and foot sensors | **~₹6k–12k** |
| USB-CAN-FD development interface | **~₹8k class** |
| ~~Battery + charger~~ | **retired — tethered** |
| Tether, boom and bulk capacitor bank | **~₹3k–6k**, excluding the bench supply |
| Wiring, connectors, DC/DC, fuse/E-stop/power hardware | **~₹4k–10k** |

A sensible planning figure for the finished V0 robot and core development electronics is roughly **₹1.0–1.3 lakh before uncertain actuator import/shipping costs**, assuming the motors are acquired near international list price rather than high domestic reseller pricing. This is not a procurement quote.

## 6. Immediate procurement recommendation

Buy now / very soon:

1. **2 × DAMIAO DM-J3507-2EC 24 V** — and measure the output thread depth on
   arrival; section 12 depends on it and it is the one interface figure this
   project has never confirmed
2. **2+ spare DAMIAO 8-pin power/CAN pigtails**, if available separately
3. **1 × USB-CAN-FD interface**
4. **2 × WeAct STM32G474CEU6 core boards** — not Nucleos, which do not fit
5. **1–2 × BNO085 breakouts** — and check them against the 22 × 22 × 6 mm
   reservation, which is currently too small for the Adafruit board
6. **M3 SHCS to the section 12 schedule**: 100 each of × 6, × 8, × 12, × 14,
   plus 1 mm and 2 mm washers
7. **A PA12-CF-capable printer and a filament dryer**, if not already owned —
   this gates every structural part and is not a consumable
8. PETG for fit mock-ups only

The joint stack is frozen, so these are decided and can be bought whenever
convenient:

- **4 + 2 × 6800-2RS** support bearings
- **4 + 2 ×** Ø10 × 8 mm journals
- **4 + 2 ×** flanged bearing carriers — get a machining quote first, this is the
  only non-commodity part on the robot

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
- STM32G474 WeAct board — Robu, observed around ₹859 during sourcing check:  
  https://robu.in/
- BNO085 — available through Indian electronics distributors including Mouser/DigiKey/7Semi and breakout-board retailers. Adafruit breakout is 25.6 × 22.7 × 4.6 mm:  
  https://www.adafruit.com/product/4754
- WeAct STM32G474 core board, 36.3 × 28.1 mm:  
  https://github.com/WeActStudio/WeActStudio.STM32G474CoreBoard
- FSR 400 series data sheet — FSR402 is Ø18.28 mm overall, Ø12.7 mm active:  
  https://cdn.sparkfun.com/assets/8/a/1/2/0/2010-10-26-DataSheet-FSR402-Layout2.pdf
- ~~GenX 22.2 V 6S 2200 mAh 40C/80C LiPo — observed around ₹2,659 from Robokits India during sourcing check.~~ Kept only as a record of the sourcing check; the robot is tethered and buys no pack.

Prices and availability are snapshots, not guarantees. Re-check immediately before ordering.

## 9. Knee actuator-interface hardware — SUPERSEDED, August 24, 2026

> Kept as a record only. This describes the PETG `knee_module.kcl` bracket,
> which no longer exists: the knee is now the same flat-plate interface as every
> other joint and has no bracket, no far bearing and no journal. Section 11 and
> section 12 replace it. Its M3 x 6 output screw is also wrong for the current
> 6 mm hub — see section 12 for the arithmetic.


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
| Output screws | 6 | M3 x 6 socket head — **not x 8**, see section 12 | ~2.8 g | Commodity | Ø6 x 3.2 counterbores in the 6 mm hub leave 2.8 mm of clearance hole, so an M3 x 8 bottoms out in a 5 mm thread. That 5 mm figure is itself unverified. |
| Rear screws | 4 | M3 x 12 socket head + washers | ~4 g | Commodity | Through the 3 mm cheek, the 3.2 mm rear cover, into 4 mm of thread. |
| **Per joint** | | | **≈ 23 g** | | But see below: the bearing, journal and carrier are fitted at **four** joints, not eight, so the metal totals 65 g and not 130. |

Printed parts, PA12-CF at 1.06 g/cm3, measured from the CAD:

| Part | Each | Count | Total |
|---|---:|---:|---:|
| Limb plate, thigh or shin — two distinct prints, used crosswise | 36.4 g | 4 | 145.6 g |
| Hip carrier — a left and a right | 37.5 g | 2 | 75.0 g |
| Foot tray with sole and sensor pads — a left and a right | 71.6 g | 2 | 143.1 g |
| Pelvis and torso shell with removable cover | 198.4 g | 1 | 198.4 g |
| **Printed structure** | | | **562 g** |

Measured 30 August 2026, after the ankle actuator was seated on the foot, the
limb flanges were removed and the waist was widened to 40 mm.

With the metal, fasteners, electronics and a 60 g allowance for the power-entry
block — capacitors, fuse and terminal, since the robot is tethered and carries no
battery — it comes to **2 047 g against a 2 300 g ceiling**, which is 253 g of
headroom where the battery build had 5 g. Run `uv run tools/mass.py` rather than
trusting this table: it measures every printed part on the engine and rolls the
whole robot up against the ceiling.

**The bearing count halved, from eight to four.** The limbs are now flat plates
that bolt straight to the actuator at the knee and the ankle, so only the hip
roll and the hip pitch are straddled and only they need a carrier, a bearing and
a journal. Buy four sets, not eight. The flanged carrier was the only
non-commodity item on this list, so that is the single biggest simplification
here — see `docs/PLAN.md` decisions 7 and 8.

**Two screw lengths change.** The limb's stator plate is 6 mm where the old
cheek was 3, and it still crosses the actuator's 3.2 mm rear cover into 4 mm of
thread, so the rear fasteners go from M3 x 12 to **M3 x 14** at the knee and the
ankle. The hip roll and hip pitch clevises are unchanged at M3 x 12. Section 12
now carries the full schedule, the washer stacks and the engagement arithmetic.

**Mirroring adds two prints, not four.** Both leg segments are 105 mm, so the
right thigh and the left shin are the same part and there are still two limb
prints. The foot and the hip carrier become a left and a right.

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


## 12. Fastener schedule and print specification — August 30, 2026

The joint interfaces now fix the fastener count and the lengths exactly, so this
replaces "an M3 assortment" in section 1. Every printed part on the robot
attaches to an actuator through one of the two patterns the vendor offers, and
nothing else on the machine is threaded.

### Where the screws go

Eight joints, each with a rotor side and a stator side:

| | Rotor side — 6 × M3 on the Ø24 output circle | Stator side — 4 × M3 on the Ø41 rear pattern |
|---|---|---|
| Hip roll ×2 | hip carrier's upper hub | torso clevis |
| Hip pitch ×2 | thigh's upper disc | hip carrier's lower clevis |
| Knee ×2 | shin's upper disc | thigh's stator plate |
| Ankle ×2 | foot's rotor hub | shin's stator plate |

That is **8 rotor attachments × 6 = 48** and **8 stator attachments × 4 = 32**,
so **80 M3 socket-head cap screws** in total.

### Lengths, and the arithmetic behind them

| Where | Qty | Screw | Washer | Pass-through | Thread | Engagement |
|---|---:|---|---|---:|---:|---:|
| Output circle, all 8 rotor ends | 48 | **M3 × 6** — see caution | none, counterbored | 2.8 mm | ~5 mm | 3.2 mm |
| Stator plate, knee and ankle | 16 | **M3 × 14** | 1.0 mm | 9.2 mm | 4 mm | 3.8 mm |
| Rear cheek, hip roll and hip pitch | 16 | **M3 × 12** | 2.0 mm | 6.2 mm | 4 mm | 3.8 mm |

The pass-through figures come straight from the model. The rotor hub is
`rotorHubThickness` 6 mm with a Ø6 × 3.2 counterbore, leaving 2.8 mm of
clearance hole under the head. The limb's stator plate is `limbPlateThickness`
6 mm and the clevis cheek is `cheekThickness` 3 mm, and both cross the
actuator's 3.2 mm rear cover into 4 mm of tapped thread.

**Caution on the output screws.** The 5 mm output thread depth is quoted in
sections 9 and 11 but it is **not in `parameters.kcl` and has no cited source** —
unlike the rear pattern's 4 mm, which the vendor 2D print and the STEP confirm
independently. If it really is 5 mm then M3 × 8 bottoms out at 5.2 mm and must
not be used; M3 × 6 gives a light 3.2 mm. Buy both lengths, measure the thread
on the first actuator that arrives, fit whichever gives about 4 mm without
bottoming, and record the measured depth in `parameters.kcl` next to
`actuatorRearBoltDepth`. Section 11's "M3 × 8" was written against this
unverified figure.

Washers are wanted on the rear patterns regardless of length, because the head
bears on printed plastic there. They are what tunes the engagement to 3.8 mm in
a 4 mm thread.

**Buy:** 100 each of M3 × 6, M3 × 8, M3 × 12 and M3 × 14 SHCS; 50 each of 1 mm
and 2 mm M3 washers. Threadlocker on every one of them — none of these screws is
in a position that can be inspected once the leg is assembled.

### How the limb plates must be printed

This is a specification, not a preference. Each limb is a flat profile 6 mm
thick from end to end, and how it is laid on the bed decides its strength by a
factor of two and a half.

- **Flat on the bed**, the 6 mm in the build direction, footprint about
  180 × 52 mm. Every bending load on a limb runs along its long axis, so that
  axis must lie in the bed plane. Printed upright the same loads are carried by
  layer adhesion instead — 30 MPa rather than 75 — and that is the orientation
  in which a sideways fall breaks a limb.
- **Outboard face down.** The inboard face carries the Ø30.4 register that
  pilots the hub on the actuator's boss, only 1.2 mm deep; face-down it becomes
  a sagging 30 mm bridge across a precision feature, face-up it is an open
  pocket. What is left to bridge is the six Ø6 counterbores and the Ø10.2
  journal seat, which are short easy spans.
- **Solid-layer raster along the limb.** Printed flat, the outermost fibres in
  sideways bending are the top and bottom solid layers, so their fill direction
  is the tension path; the usual ±45° default wastes it.
- **Solid, or near it.** The part is about 36 g and the mass budget already
  models it solid.

The foot prints sole-face-down for the same class of reason — it puts the layer
lines across the landing load — and in that orientation its open top needs no
support anywhere.

See `docs/NOTES.md`, 30 August 2026, for the analysis these follow from,
including why the limb's flanges were removed rather than enlarged.

### The fastener allowance is light

Weighing the schedule above rather than allowing for it: 48 M3 × 6, 16 M3 × 14
and 16 M3 × 12 in steel, with 32 washers, comes to roughly **90 g**. The mass
budget in `tools/mass_budget.toml` carries a flat **60 g** allowance for
fasteners, written before the joints were specified.

That is about 30 g of the 253 g headroom, unbudgeted. It does not threaten the
ceiling, but the allowance should be corrected rather than left to be discovered
on a scale. Titanium or aluminium screws would give most of it back if it ever
matters; nothing here is a high-load fastener except the six on each output
circle, which carry the actuator's full torque.
