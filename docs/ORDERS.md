# Purchase records

These records preserve what was actually ordered, including items that may not
match the current BOM. An order does not establish delivery or suitability for
the robot.

## Recording a 3D print order

A print cart is recorded **when it is built**, read off the bureau's page, and
not after it is placed. A Zbotic print cart was cleared unplaced on 2026-10-14
because nothing recorded the infill and quality it had been set to, and a STEP
file carries neither.

**The default, unless the owner asks for something else for an order:** black
PLA, FDM at a 0.12 mm layer (Zbotic's "FDM 0.12mm High Quality"), 100 % infill.
Set by the owner on 2026-10-14. The mass roll-up still prices the parts in
PA12 at 0.93 g/cm³; solid PLA at about 1.24 makes the printed structure
roughly a third heavier, about 140 g on the 430 g it counts, which leaves the
robot near 175 g under its ceiling rather than 317.

Every print order here records:

- **The release it was built from.** Upload only files written by
  `uv run tools/export.py --release`, which writes them into
  `exports/releases/<commit>/` named for the commit they were built from, such
  as `pelvis-shell_8c6cfe4.step`, and refuses while `cad/` has uncommitted
  changes. Paste the table it prints: file, prints, which way up, volume and
  SHA-256. A file from `exports/` itself is a working copy and is not a version
  of anything.
- **The settings, per file where they differ:** process and machine (FDM, SLA,
  SLS, MJF), material and colour, layer height or the bureau's quality preset
  by its own name, infill percentage and pattern, wall or perimeter count, top
  and bottom layers, supports, orientation if the bureau asks, and finishing.
  Where the page offers a setting and it was left at its default, record the
  default's value, not "default".
- **Quantity, unit and line price, GST, shipping, and the quoted lead time,**
  as for any other order.

## QuartzComponents — order #433538

- **Confirmed:** 2026-10-05.
- **Status:** received, reported by the owner on 2026-10-15.
- **Previous shipping status:** on its way, 2026-10-06 at 4:43 pm.
- **Courier:** Delhivery, tracking **57996610232772**.
- **Source:** order screenshots supplied by the owner on 2026-10-08.

| Item as ordered | Quantity | Unit price | Line amount |
|---|---:|---:|---:|
| 4mm Banana Plug Male High-Quality Terminal Connector (Red & Black Pair) | 1 pair | ₹46.00 | ₹46.00 |
| BHT-3.5 Heat Shrink Butt Splice Connector 2.5–4.0 sqmm (14–12 AWG) — Black | 6 | ₹26.00 | ₹156.00 |
| XT90 Female to 4.0mm Banana Plug with 14AWG Silicone Wire | 1 | ₹151.00 | ₹151.00 |
| 14AWG Silicone Wire Black (1 meter) — High Quality Ultra Flexible for Battery Packs | 2 × 1 m | ₹115.00 | ₹230.00 |
| 14AWG Silicone Wire Red (1 meter) — High Quality Ultra Flexible for Battery Packs | 2 × 1 m | ₹139.00 | ₹278.00 |
| XT60 Male Connector with 14AWG Silicone Wire | 1 | ₹62.00 | ₹62.00 |
| XT60 Female Connector with 14AWG Silicone Wire | 1 | ₹62.00 | ₹62.00 |

The seven visible lines total **₹985.00**. Shipping, tax breakdown and the final
order total are not visible in the supplied screenshots.

Both male and female XT60 pigtails were ordered. The ready-made banana lead is
**XT90 female**, as shown in the order; it is recorded as purchased without
substituting it for the BOM's XT60 charge lead.

## ThinkRobotics — order #TR65279

- **Ordered:** 2026-10-06.
- **Status:** delivered, reported by the owner on 2026-10-08.
- **Source:** order confirmation and delivery update supplied by the owner on 2026-10-08.

| Item as ordered | Quantity | Line amount |
|---|---:|---:|
| Brass heat-set knurled inserts, M5 × 6 mm | 1 pack of 10 | ₹99.99 |

Subtotal **₹99.99**, shipping **₹95.00**, including IGST **₹15.25**;
**total ₹194.99**.

The M2.5 × 10 standoffs and JST-XH crimp kit were not part of this order.
Insert dimensions and installation strength have not yet been measured or tested.

## fastdep — 2026-10-08

- **Placed:** 2026-10-08, reported by the owner; order number not yet recorded.
- **Status:** received, reported by the owner on 2026-10-15.
- **Source:** checkout summary supplied by the owner on 2026-10-08.

| Item as ordered | Quantity | Line amount |
|---|---:|---:|
| M3 × 8 Allen socket head screws (high tensile), 10 pcs | 5 | ₹110.00 |
| M3 × 12 Allen socket head screws (high tensile), 10 pcs | 1 | ₹26.00 |
| M2.5 × 6 stainless Allen socket head screw, pack of 10 | 1 | ₹38.00 |
| M3 × 10 Allen socket head screws (high tensile), 10 pcs | 2 | ₹46.00 |
| M3 hex nut (high tensile), 25 pcs | 1 | ₹18.00 |
| M2.5 × 8 stainless Allen socket head screw, pack of 10 | 1 | ₹38.00 |
| M2 × 10 stainless Allen socket head screw, pack of 10 | 1 | ₹42.00 |
| M2 hex nut (high tensile), 25 pcs | 1 | ₹28.00 |
| M2.5 washer, 25 pcs | 1 | ₹28.00 |
| M5 hex nut (high tensile), 25 pcs | 1 | ₹24.00 |
| M5 washer, 25 pcs | 1 | ₹28.00 |
| M5 × 30 Allen socket head screws (high tensile), 10 pcs | 1 | ₹40.00 |

Items **₹466.00**, packing and shipping **₹89.00**; **total ₹555.00**.

No M3 × 6 and no M3 × 20 were ordered. The 20 M3 × 10 leave no spare: a spare
M3 × 12 can stand in for a lid screw, not for a motor stator screw.

## Robu — 2026-10-08

- **Placed:** 2026-10-08, reported by the owner; order number not yet recorded.
- **Status:** received, reported by the owner on 2026-10-15.
- **Source:** the cart as read in the browser on 2026-10-08, before the owner
  placed it; the placed order itself has not been seen.

| Item as in the cart | Quantity | Unit price | Line amount |
|---|---:|---:|---:|
| JST-SH 1 mm 8-pin female housing connector with 300 mm wire (28 AWG) | 2 | ₹44.00 | ₹88.00 |
| 1N4148 Onsemi 100 V 200 mA DO-35 switching diode | 6 | ₹3.37 | ₹20.22 |

Cart total **₹108.22** including GST. Under Robu's ₹999 free-delivery
threshold, so shipping is charged; the amount is not recorded.

These quantities assume the one JST-SH lead and three 1N4148s from order
#3736678 are in hand, which makes three leads and nine diodes in all.

## Robocraze — 2026-10-08

- **Placed:** 2026-10-08, reported by the owner; order number not yet recorded.
- **Status:** received, reported by the owner on 2026-10-15.
- **Source:** the cart as read in the browser on 2026-10-08, before the owner
  placed it; the placed order itself has not been seen.

| Item as in the cart | Quantity | Line amount |
|---|---:|---:|
| BNO085 9-DOF orientation IMU sensor fusion Nano breakout board | 1 | ₹2,095.00 |

Cart total **₹2,095.00**; shipping, if any, is not recorded. One fitted, no spare.

## element14 India — 2026-10-08

- **Placed:** reported by the owner on 2026-10-08.
- **Status:** **cancelled by element14**, reported by the owner on 2026-10-13.
  Nothing from it is coming.
- **Source:** owner's explicit confirmation in this conversation: “element14 order has been placed”.
- **Order number:** element14 ref **26013728**, PO number 20261008185525,
  from element14's “order has been received” email of 2026-10-08 to the
  owner's Hotmail address. No invoice was issued: the detailed confirmation
  waits on stock allocation, and the order was cancelled first.
- **Charged:** **₹2,887.70** to the owner's ICICI Visa debit card on 2026-10-08 at 18:56, card
  reference 628113396699, read from the owner's bank statement on 2026-10-22.
  That is ₹124.82 less than the reviewed basket's ₹3,012.52, and one Keystone
  3568 holder fewer, ₹105.98 + 18 % GST, accounts for it to within 25 paise.
  **Refund not yet seen**, 2026-10-22.

Its parts were re-sourced from shops that sell to an individual without a
GSTIN and ordered on 2026-10-13: see [Robu](#robu--2026-10-13) and
[LionCircuits](#lioncircuits--2026-10-13). The table is what this order held,
kept as a record, with the quantities read from the order-received email on
2026-10-22. They match the last reviewed 17-line basket on every line but the
Keystone holder, which went in at one, not two.

| Selected part | element14 order code | Quantity ordered |
|---|---|---:|
| MCP2562FD-E/P CAN transceiver | 2434898 | 4 |
| BZX79-C15,133 zener | 1097217 | 5 |
| Keystone 3568 fuse holder | 2504685 | 1 |
| Vishay PR01 1 kΩ 1 W, R26 | 2614498 | 2 |
| KEMET C315C104K5R5TA 100 nF | 4552016 | 10 |
| TE LR0204 10 Ω | 2329856 | 10 |
| TE LR0204 1 kΩ | 2329885 | 10 |
| TE LR0204 10 kΩ | 2329855 | 10 |
| TE LR0204 15 kΩ | 2329873 | 10 |
| TE LR0204 22 kΩ | 2329901 | 10 |
| TE LR0204 47 kΩ | 2329944 | 10 |
| TE LR0204 100 kΩ | 2329853 | 10 |
| TE LR0204 1 MΩ | 2329894 | 10 |
| Vishay MBA0204 470 kΩ | 4177865 | 10 |
| Vishay MBA0204 10 MΩ | 4177856 | 10 |
| KEMET R82DC3220AA60K 220 nF, C1 | 2763209 | 10 |
| KEMET MMK5225K63J06L4BULK 2.2 µF, C7 | 2429330 | 10 |

Last reviewed basket: **₹2,552.98 before GST**, **₹3,012.52 including GST**,
with ₹0 shipping shown, and two Keystone holders where the order took one.

## Evelta — 2026-10-08

- **Placed:** reported by the owner on 2026-10-08.
- **Status:** received, reported by the owner on 2026-10-15.
- **Source:** owner's confirmation in this conversation: “the Evelta order has been placed”.
- **Order number and final invoice:** not yet supplied.

The last reviewed cart held two Daier GQ-12B/S 12 mm momentary buttons and
two AMASS XT60E-M.G.Y male panel-mount inlets: one installed and one spare of
each. These selections belong to the received Evelta order and must
not be reordered. Quantities have not been independently checked against the
placed-order invoice.

The reviewed cart subtotal was **₹472 before GST** (₹380 for the buttons and
₹92 for the inlets); final charged amount, shipping and invoice quantities
are not yet recorded. Order placement does not establish delivery.

## Indian Hobby Center — 2026-10-08

- **Placed:** reported by the owner on 2026-10-08.
- **Status:** received, reported by the owner on 2026-10-15.
- **Source:** owner's confirmation in this conversation: “the indian hobby shop order has been placed”.
- **Order number and final invoice:** not yet supplied.

This is the leads and sockets order, separate from the earlier battery and wire
order. The last reviewed basket contained the following selections, now
allocated to this received order; do not reorder them. Invoice quantities
have not been independently verified.

| Reviewed selection | Basket quantity |
|---|---:|
| DIP-8 sockets | 5 |
| Female-female jumper wire set | 1 |
| JST-XH 2-pin bare-ended leads | 3 |
| JST-XH 3-pin bare-ended leads | 2 |
| JST-XH 4-pin bare-ended leads | 4 |
| JST-XH 4-pin double-ended leads | 2 |
| JST-XH 6-pin bare-ended leads | 2 |
| JST-XH 8-pin bare-ended lead | 1 |

Last reviewed basket subtotal: **₹227**, plus shipping. The final charged
amount is not yet reported. Receipt was confirmed by the owner on 2026-10-15.

## Robu — 2026-10-13

- **Placed:** reported by the owner on 2026-10-13; order number not yet recorded.
- **Status:** received, reported by the owner on 2026-10-16.
- **Source:** the cart as read in the browser on 2026-10-13, before the owner
  placed it; the placed order itself has not been seen.

Half of the cancelled element14 order. Each part went to whichever of Robu and
LionCircuits was cheaper with GST, except the 220 nF film, which went to
LionCircuits because only the KEMET part is known to fit C1. None is on both
orders.

| Item as in the cart | Quantity | Unit price | Line amount |
|---|---:|---:|---:|
| onsemi 1N5245BTR, 15 V 500 mW zener, DO-35 | 2 | ₹11.00 | ₹22.00 |
| 2.2 µF 35 V tantalum capacitor, dipped, generic | 2 | ₹15.00 | ₹30.00 |
| Yageo MFR-25FRF52-10R, 1 % metal film | 10 | ₹1.08 | ₹10.80 |
| Yageo MFR-25FRF52-10K | 5 | ₹2.45 | ₹12.25 |
| Yageo MFR-25FRF52-15K | 10 | ₹1.08 | ₹10.80 |
| Yageo MFR-25FRF52-22K | 4 | ₹2.52 | ₹10.08 |
| Yageo MFR-25FRF52-47K | 10 | ₹1.08 | ₹10.80 |
| Yageo MFR-25FRF52-100K | 10 | ₹1.08 | ₹10.80 |
| Yageo MFR-25FRF52-1M | 10 | ₹1.08 | ₹10.80 |
| Multicomp Pro MCF 0.25 W 1K, 5 % metal film | 5 | ₹2.12 | ₹10.60 |
| Multicomp Pro MCF 0.25 W 470K, 5 % | 6 | ₹1.89 | ₹11.34 |
| Multicomp Pro MCF 0.25 W 10M, 5 % | 11 | ₹0.99 | ₹10.89 |

Cart total **₹161.16** including GST. Under Robu's ₹999 free-delivery
threshold, so shipping is charged; the amount is not recorded.

**Robu will not check out a line worth under ₹10**, so each resistor line is the
smallest count that reaches it rather than fitted plus one spare. Three parts
here are substitutes, recorded in their BOM rows: the zener for the BZX79-C15
(D1), the tantalum for the KEMET MMK5 film (C7, + to VSRC), and 0207 bodies for
the 0204 resistors, with R3 and R7 stood over their second hole. The 1 kΩ line
covers R18 and R26.

## LionCircuits — sales order ETPSO-58883

- **Placed:** 2026-10-13, and paid the same day.
- **Status:** “On Track”, procurement in progress and not shipped, as read in
  the account on 2026-10-18 and unchanged on 2026-10-19, still at procurement,
  the first of six steps between confirmation and delivery. **Expected shipping 28 October**, where every line
  read “In Stock, ships in 7–10 days” when it was ordered and still does: that
  is stock at LionCircuits' own suppliers, and 7–10 days from 13 October would
  have been 20–23 October. Its own notice puts the gap down to Dussehra: back-end
  operations limited on 17, 19 and 20 October and shipments resuming on the 21st.
  All four lines read “Ready”, none unavailable or awaiting input.
- **Source:** the cart as read in the browser on 2026-10-13, and the order's
  page in the owner's LionCircuits account (project NextCart-797018), read on
  2026-10-18. Signed in, it is at
  <https://order.lioncircuits.com/bomScrub/project/6ace09d4848c1c5df6797018>;
  the account's project list shows nothing, so go by the link.

The other half of the cancelled element14 order.

| Item as in the cart | Quantity | Unit price before GST | Line amount |
|---|---:|---:|---:|
| Microchip MCP2562FD-E/P CAN-FD transceiver, PDIP-8 | 4 | ₹175.89 | ₹703.55 |
| Keystone 3568 mini blade fuse holder | 2 | ₹141.38 | ₹282.76 |
| KEMET C315C104K5R5TA 100 nF 50 V X7R | 10 | ₹27.43 | ₹274.30 |
| KEMET R82DC3220AA60K 220 nF 63 V film | 3 | ₹36.38 | ₹109.13 |

Components **₹1,369.74**, GST ₹246.55, shipping free; **total ₹1,616.00**.

Three R82s because LionCircuits' minimum is three. Ten C315s because ten cost
₹274.30 where nine cost ₹788.36; eight are fitted.

## ElectronicsComp — order #3304076

- **Placed:** 2026-10-16, the day it was recommended; invoice INV/26-27/2668.
- **Status:** Confirmed, and nothing since, as read in the account on
  2026-10-18: not yet dispatched. **Still not dispatched on 2026-10-24**, eight
  days after payment, and the shop's phone, +91-8796538800, goes unanswered.
  That is the outcome most of its reviews describe — Trustpilot 1.1 of 5 from
  434, 96 % one-star — which was not checked before it was recommended. Being
  cancelled for a refund; the shop is not to be used again.
- **Source:** the order page in the owner's ElectronicsComp account, read in
  the browser on 2026-10-18.

| Item as ordered | Quantity | Unit price | Line amount |
|---|---:|---:|---:|
| YIHUA 948-III 3 in 1 desoldering rework station, 110 W iron and vacuum desoldering gun, model EC-19054 | 1 | ₹7,568.00 | ₹7,568.00 |

Subtotal **₹7,568.00**, free shipping, CGST and SGST ₹681.12 each; **total
₹8,930.24**, paid by UPI or card. The listing does not state the mains voltage: read
the plate for 220–240 V before plugging it in. The Yihua 853AAA-I preheater
recommended with it was not ordered.

## Bengaluru instant estimates — release 2e89fd7, 2026-11-02

The shell, the deck and both shins, one of each, in PLA, read off each shop's
own calculator. None is an order and none is a quote anyone has to honour. The
STLs were written for these with `uv run tools/export.py --release --format stl`
into the same release folder, since neither calculator takes STEP:

| File | Prints | Up | cm³ | SHA-256 |
|---|---:|---|---:|---|
| pelvis-shell_2e89fd7.stl | 1 | +Z | 184.54 | e627920d6212 |
| electronics-deck_2e89fd7.stl | 1 | -Z | 27.42 | 364dc5c1975a |
| limb-105-unmirrored_2e89fd7.stl | 1 | -X | 33.55 | 46bced1fea0f |
| limb-105-mirrored_2e89fd7.stl | 1 | +X | 33.55 | 520b8df5f3a1 |

| Shop | Settings | Shell | Deck | Shin, each | Total | Leaves out |
|---|---|---:|---:|---:|---:|---|
| Dr.PrinT, drprint.in/calculator | PLA ₹6/g, Bambu A1, "Fine" 0.1 mm, 100 % infill, grid, 2 walls, no supports | ₹1,539.00 (256.5 g) | ₹211.80 (35.3 g) | ₹250.20 (41.7 g) | **₹2,301.20** with ₹50 setup | GST not stated; ±15 % |
| Anuveshana, anuveshanatechnologies.in/upload | PLA, 100 % infill; no layer or colour setting priced | ₹686.49 (228.83 g) | ₹102.00 (34.00 g) | ₹124.81 (41.60 g) | **₹1,038.11** | supports, setup, tax, delivery: material only |
| Rapid 3D, quote.rapid3d.co.in, the owner's account | FDM, PLA+ (no plain PLA offered), black, 100 % infill, "As Printed", no brass inserts, standard inspection; no layer height offered | ₹1,863.82 | ₹276.91 | ₹338.86 | **₹2,818.47**; with SGST and CGST at 9 % each and ₹200 shipping, ₹3,561.79 | nothing; whether collection drops the ₹200 is not stated |

The Rapid 3D quote was saved with "Generate Quotation", which left the page
unresponsive behind what is most likely a browser dialog, so its quotation
number was not read.

## Makenica — 3D print quote RH0AD5, release 2088e6f

- **Quote built:** 2026-11-02, at console.makenica.com/quotes/18393. **Not
  ordered**: about 2.6 times Zbotic's price for the same four pieces.
- **Release:** `exports/releases/2088e6f/`, the same files as the Zbotic cart
  below: the pelvis shell, the electronics deck and both shins. `cad/` carried
  uncommitted work at the time (the spot faces off the wheel motors' stator
  plates, which are on the shins), so the shins quoted are not the working copy.
- **Settings, the same on every line:** FDM, PLA, black. Infill "Solid (50% -
  80%)", the highest Makenica offers, and layer height "Standard (200 μm)", the
  finest; the other choices are 250 and 300 μm. Threaded inserts 0. No finishing
  chosen. Each part's note asks for 100 % infill and 0.12 mm if possible, gives
  the orientation as in the Zbotic notes below, and says the parts will be
  collected from the JC Industrial Estate shop, not couriered. Every note was
  read back after a fresh load: the site saves a note typed after its
  next-part arrow onto the previous part.

| Piece | Makenica read, mm | Line, before discount and GST |
|---|---|---:|
| pelvis-shell × 1 | 178 × 72 × 137 | ₹3,367.83 |
| electronics-deck × 1 | 148 × 66 × 9 | ₹381.11 |
| limb-105-unmirrored (left shin) × 1 | 10 × 46 × 149 | ₹623.47 |
| limb-105-mirrored (right shin) × 1 | 10 × 46 × 149 | ₹623.47 |

₹4,995.88, less a 10 % offer of ₹499.59, is ₹4,496.29, plus GST at 18 %
₹809.33: **₹5,305.62**. Shipping shown as "-". Zbotic priced the same four at
₹2,054 with 18 % GST, at 0.12 mm and 100 % infill.

## Zbotic — 3D print cart, release 2088e6f

- **Cart built:** 2026-10-20, through zbotic.in/3d-print-order/. **Not placed.**
- **Source:** Zbotic's quote page and cart, read in the browser as each line was
  added.
- **Release:** `exports/releases/2088e6f/`, commit
  2088e6f09ddd9cc9878ea205cd1b89c2da3dee23 of 2026-10-18, finished form (arrises
  broken at 0.5 mm). The seven files uploaded, as the release table printed them;
  the journal sleeves, the wheel caps and the torso cover are not in this cart:

| File | Prints | Up | cm³ | SHA-256 |
|---|---:|---|---:|---|
| pelvis-shell_2088e6f.step | 1 | +Z | 184.54 | 21a85b358a65 |
| electronics-deck_2088e6f.step | 1 | -Z | 27.42 | afa6cfc6be10 |
| wheel-adapter_2088e6f.step | 2 | +X | 6.96 | 5a6683f3c226 |
| thigh-105-unmirrored_2088e6f.step | 1 | -X | 42.18 | 9b58d726f8f7 |
| thigh-105-mirrored_2088e6f.step | 1 | +X | 42.18 | 41228f41a10f |
| limb-105-unmirrored_2088e6f.step | 1 | -X | 33.41 | b62f7af8568d |
| limb-105-mirrored_2088e6f.step | 1 | +X | 33.41 | a32cacfd5af0 |

**Settings, the same on every line:** FDM, which Zbotic says it runs on its own
Bambu Lab machines; PLA (₹1.32/cm³ as listed); black; "FDM 0.12mm High Quality"
(₹20/hr as listed); infill 100 %; supports "Auto", shown on the review and not
selectable; rush order off. The page offers no infill pattern, wall count,
top and bottom layers, orientation or finishing, so none was set. Which way up
each piece prints went into each line's Special Instructions box:

- Pelvis shell: *Print in the orientation uploaded (+Z up): upright, standing on
  the two hip saddles. Not rim-down. The 0.5 mm edge chamfers are intentional.*
- Electronics deck: *Print upside down from the orientation uploaded (-Z up):
  the plate's top face on the bed, the IMU rails on its underside standing up.
  The 0.5 mm edge chamfers are intentional.*
- Wheel adapter: *Print with the flat disc on the bed and the spigot standing up
  (the file's +X axis up). Two identical prints. The 0.5 mm edge chamfers are
  intentional.*
- Right thigh: *Right thigh. Print lying on its side with the file's -X axis
  pointing up (resting on its +X face, the tie arches' face uppermost). The left
  thigh is a separate, mirrored file. The 0.5 mm edge chamfers are
  intentional.*
- Left thigh: *Left thigh. Print lying on its side with the file's +X axis
  pointing up (resting on its -X face, the tie arches' face uppermost). The
  right thigh is a separate, mirrored file. The 0.5 mm edge chamfers are
  intentional.*
- Left shin: *Left shin. Print lying on its side with the file's -X axis
  pointing up (resting on its +X face, the tie arches' face uppermost). The
  right shin is a separate, mirrored file. The 0.5 mm edge chamfers are
  intentional.*
- Right shin: *Right shin. Print lying on its side with the file's +X axis
  pointing up (resting on its -X face, the tie arches' face uppermost). The
  left shin is a separate, mirrored file. The 0.5 mm edge chamfers are
  intentional.*

The box is cleared when a slice finishes, so a note typed while the page is
still slicing is lost; the right thigh's had to be typed twice. Every note above
was read back out of the box before its line was added.

| Piece | Zbotic read, mm | Zbotic cm³ | Quote: material + print time + GST 18 % | Print time | Weight | Delivery | Cart line |
|---|---|---:|---|---:|---:|---|---:|
| Pelvis shell × 1 | 177.9 × 72 × 136.6 | 184.537 | ₹329 + ₹783 + ₹200 = **₹1,312** | 17.3 h | 309 g | ~4 days | ₹1,167.17 (₹1,111.59 + GST) |
| Electronics deck × 1 | 148.3 × 66.4 × 9.15 | 27.4172 | ₹61 + ₹167 + ₹41 = **₹269** | 3.6 h | 53.2 g | ~3 days | ₹238.94 (₹227.56 + GST) |
| Wheel adapter × 2 | 12 × 35.99 × 36 | 6.9606 | ₹31 + ₹81 + ₹20 = **₹132** for two | 0.8 h each | 10.1 g each | ~3 days | ₹117.53 (₹111.93 + GST) |
| Right thigh × 1 | 54.7 × 52 × 149 | 42.1723 | ₹82 + ₹211 + ₹53 = **₹345** | 4.6 h | 73.1 g | ~3 days | ₹307.04 (₹292.42 + GST) |
| Left thigh × 1 | 54.7 × 52 × 149 | 42.1725 | ₹83 + ₹216 + ₹54 = **₹353** | 4.7 h | 74 g | ~3 days | ₹313.74 (₹298.80 + GST) |
| Left shin × 1 | 10 × 46 × 149 | 33.4058 | ₹61 + ₹140 + ₹36 = **₹237** | 3.1 h | 53 g | ~3 days | ₹210.85 (₹200.81 + GST) |
| Right shin × 1 | 10 × 46 × 149 | 33.4058 | ₹61 + ₹139 + ₹36 = **₹236** | 3.0 h | 53 g | ~3 days | ₹209.86 (₹199.87 + GST) |

Cart **₹2,442.98 + ₹122.15 GST at 5 % = ₹2,565.13**, shipping free, read
after the last line went in. The quote page prices at 18 % GST and the cart
charges 5 %; the figures before tax agree to within a few rupees. The 5 % coupon
the cart shows is for a Bambu Lab A1 printer and does not apply.

**A quote can be read before it reflects the settings.** The left thigh first
priced at ₹246 — 2.6 h, 54.1 g — with every setting already showing as chosen,
and at ₹353 once it was sliced again. So each line after that was sliced twice
and added only when both agreed, and the deck and the wheel adapters, added
before this was found, were quoted again afterwards: ₹269 and ₹132, the same as
their lines. The pelvis was not quoted again; its slice was seen to start after
its last setting changed. The right thigh was not either, and agrees with the
left to ₹8.

Three things about this cart are unproven:

- **The cart does not show the quality preset, the infill or the special
  instructions.** Each line shows technology, material, colour, size, model and
  quantity only. The price matches the 0.12 mm, 100 % quote, which is the only
  evidence those settings went with it. Confirm with Zbotic that the orientation
  notes reached the order.
- **Zbotic flagged every file "Non-manifold mesh — may need repair"** and
  offered an Auto Repair, which was not used. Its volumes match the release's to
  the figure it prints, and the export read each file back as one closed
  surface, so the flag is most likely from Zbotic's own conversion of the STEP.
- **Zbotic's weights are 17 to 56 % above solid PLA** at about 1.24 g/cm³:
  309 g for a pelvis whose solid is 229 g, the deck 53.2 for 34.0, an adapter
  10.1 for 8.6, a thigh 74 for 52.3 and a shin 53 for 41.4. The surplus is most
  likely support material in whatever orientation its slicer chose, which need
  not be the one asked for.
