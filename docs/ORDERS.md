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
- **Order number and final invoice:** not yet supplied.

Its parts were re-sourced from shops that sell to an individual without a
GSTIN and ordered on 2026-10-13: see [Robu](#robu--2026-10-13) and
[LionCircuits](#lioncircuits--2026-10-13). The table is what this order held,
kept as a record. The following are the quantities in the last reviewed
17-line basket, not independently verified invoice quantities. The two film
capacitor lines were also shown at ten each in the owner's cart screenshot.

| Selected part | element14 order code | Reviewed basket quantity |
|---|---|---:|
| MCP2562FD-E/P CAN transceiver | 2434898 | 4 |
| BZX79-C15,133 zener | 1097217 | 5 |
| Keystone 3568 fuse holder | 2504685 | 2 |
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
with ₹0 shipping shown. Final charged amount and invoice quantities remain to
be recorded; order placement does not establish delivery.

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
- **Status:** delivery not yet recorded.
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

## LionCircuits — 2026-10-13

- **Placed:** reported by the owner on 2026-10-13; order number not yet recorded.
- **Status:** delivery not yet recorded; every line read “In Stock, ships in
  7–10 days”, which is stock at LionCircuits' own suppliers.
- **Source:** the cart as read in the browser on 2026-10-13, before the owner
  placed it; the placed order itself has not been seen.

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
