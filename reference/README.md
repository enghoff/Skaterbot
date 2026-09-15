# Vendor reference material

Authoritative supplier data, tracked deliberately. These are design *inputs*, so
unlike the exported STEP and STL files in the repository root they are not
gitignored — see the exception at the bottom of `.gitignore`.

Do not edit anything here. If a vendor publishes a revision, add it alongside
under its own filename rather than overwriting, so that older geometry stays
reproducible.

**[`DATASHEETS.md`](DATASHEETS.md) is the catalogue**: every component and module
on the robot, where it is documented, what is stored here and what is only a
link, and how much each source is worth. Eight datasheets were added on
2026-09-15 -- the MCU, the core board's schematic, outline and pin-label drawing,
the CAN transceiver, the bus monitor's chip, the IMU's chip and the XH connector
series. The two parts with no drawing published anywhere are the two the
controller carrier lands on pins, and that file says so.

## `dm_3507_3d-241021.STEP`

3D model of the DAMIAO DM-J3507-2EC actuator.

| | |
|---|---|
| Source | `gitee.com/kit-miao/DM-J3507-2EC`, path `3D模型/` |
| Retrieved | 2026-08-23 |
| Size | 4,440,459 bytes |
| SHA-256 | `583b499c3a9331614956861780ea5259597d39582d91ad0310fe0e447049d1db` |
| Format | STEP AP214, written by SolidWorks 2020 via SwSTEP 2.0 |

Three things to know before relying on it.

**The main body is a surface model, not a solid.** The file contains six
`MANIFOLD_SOLID_BREP` solids — two end plates, two M2.5 screws and two small
imported parts — plus one `SHELL_BASED_SURFACE_MODEL` of open shells that
carries the actuator body itself. It may therefore not import as usable solid
geometry, and boolean operations against it may fail.

**It is an assembly, so sub-part coordinates are local.** Reading the raw
`CARTESIAN_POINT` values as if they shared one frame gives a bounding box around
48 mm long, which is wrong. Resolving the 15 assembly transforms gives the
correct envelope of Ø46.000 mm by 37.9 mm overall, with the mounting face at the
origin and the far face at Y = 37.9.

**The part names read `3505`, not `3507`.** The internal `FILE_NAME` is
`dm_3505_3d-241021.STEP` and every `PRODUCT` entry is a `3505` variant. The
vendor's own 2D print is likewise titled "DM 3508-7". This appears to be the
base stator designation being reused rather than a wrong file, but confirm the
envelope when opening it.

### Interface dimensions taken from this file

These are mirrored into `lib/parameters.kcl` so the CAD references them by name.
They were read from the hole geometry and cross-checked against the vendor 2D
print, not from a dimensioned drawing directly, so confirm them on screen.

- Output face: 6 x M3 tapped 5 mm deep on a Ø24 mm bolt circle, inside a Ø30 mm
  register, with concentric bores around Ø8-10 mm.
- Housing: 4 x M3 on a Ø41 mm bolt circle at 90° spacing.
- A three-hole pattern on a Ø17.5 mm circle near the centre of the output face.
- Radial cable exit 31.7 mm from the output face. Its radial extent is not
  modelled anywhere because it has not been measured.
- Four M2.5 screws on a Ø42 mm circle entering the rear face are internal
  assembly fasteners, not mounting points.
- There is **no rear spigot**, so an opposite support bearing needs a stub axle
  supplied by the surrounding structure.

## `DM-J3507-2EC减速电机说明书V1.0.pdf`

The vendor user manual, V1.0 dated 2024-11-19, from `说明书/` in the same Gitee
repository. Chinese only. This is the most reliable of the three vendor sources:
where it and the STEP have disagreed, the manual has been right.

## `DM-J3507-2EC_manual_V1.0_EN.pdf`

An **unofficial English translation** of the above, produced here for working use.
Not from the vendor, and not authoritative — where a number matters, check it
against the Chinese original sitting beside it.

The translation is layout-preserving rather than a re-typeset document. Original
text runs were removed and English inserted into the same boxes, so pagination,
tables, gridlines and all eleven figures are unchanged and the two documents can
be read side by side. All 15 pages are translated with no Chinese text remaining.

Two things to expect. Font size varies within a paragraph, because each source
line was fitted to its own box and English is wider than Chinese at the same
point size. And text baked into the figures is untouched — which costs nothing
here, since the pinout labels (VCC, GND, CAN_L, CAN_H, RX, TX) and the dimension
callouts were already Latin.

Reproducible from the original with the two files kept alongside:

- `translate_manual.py` — extracts text cells with their bounding boxes, removes
  them without disturbing line art or images, and refits the English. Needs
  PyMuPDF.
- `manual_translation_map.json` — the 345 source-string to English pairs. Correct
  a translation here and re-run rather than editing the PDF.

Run as `python translate_manual.py <chinese.pdf> <english.pdf>` with the JSON
files from the script's own directory.

## `MCP2561-2FD_DS20005284A.pdf`

Microchip's datasheet for the MCP2561/2FD high-speed CAN FD transceiver,
DS20005284A, revision A dated 2014-03-25. The robot fits three **MCP2562FD-E/P**
in DIP-8 sockets on the controller carrier, one per CAN bus.

| | |
|---|---|
| Source | `farnell.com/datasheets/1821190.pdf` |
| Retrieved | 2026-09-14 |
| Size | 1,320,551 bytes |
| SHA-256 | `79321323eb3295c5800a1aaabfea595f1486a26e2c17016b70bd26c52369fc14` |
| Format | PDF 1.6, 32 pages, written by Microchip from FrameMaker |

Two things to know. It is **Microchip's own file**, mirrored from the copy
Farnell distributes rather than re-typeset by the distributor, and the PDF
metadata says so. And it is **revision A, from 2014** — the only revision
Farnell serves; if a marginal number ever decides something, check Microchip's
site for a later one first. It carries 40-bit RC4 encryption with an empty user
password, which is how Microchip publishes, so it opens without a password but
some stricter tools will refuse it.

One document covers both family members, and which one this robot buys turns on
a single pin: the **MCP2561FD has SPLIT** on pin 5 and takes its logic level
from `VDD`, while the **MCP2562FD has `VIO`** there and so can sit on 5 V while
talking to a 3.3 V microcontroller. That is the whole reason `docs/BOM.md` names
the 2562.

### What the carrier takes from it

`electrical/carrier.py` cites this document by number, and `docs/CARRIER.md`
explains the choices it drove. All of them were read back against this file on
2026-09-14 and agree with it.

- **Pin descriptions, table 1-2** (page 4): TXD 1, VSS 2, VDD 3, RXD 4, VIO 5,
  CANL 6, CANH 7, STBY 8. This is the netlist's pinout.
- **The internal pull-ups** (section 1.7): TXD has a nominal 33 kΩ pull-up, and
  STBY a MOS pull-up of typically 660 kΩ at 5 V, 1.1 MΩ at 3.3 V and 4.4 MΩ at
  1.8 V. A floating STBY is therefore **standby, not normal mode**, which is why
  the carrier ties all three to ground rather than driving them.
- **Undervoltage thresholds** (section 1.6): typically 4 V on VDD and 1.2 V on
  VIO, below which CANH and CANL stay high-impedance. That 4 V is the threshold
  the carrier's power LED is read against.
- **The common-mode choke** (section 1.8): "might be required for data rates
  greater than 1 Mbps". The motors default to 1 Mbit/s, so the bus sits at the
  speed where that recommendation starts and not past it.
- **Figure 1-2**, the MCP2562FD application circuit, which is 100 nF at VDD and
  100 nF at VIO — the decoupling the carrier fits per transceiver.
- **Permanent dominant detection** (section 1.5): both the stuck-TXD and
  stuck-bus timeouts are 1.25 ms typical.
- **Package drawing C04-018D** (pages 21-22), the 8-lead 300 mil PDIP at 0.100
  in pitch, which is the footprint the carrier is drilled to.

## Not yet mirrored here, from DAMIAO

Also published at the actuator's Gitee repository, and worth adding if needed:

- `2D图纸/` — dimensioned print, titled `DM 3508-7减速电机.PDF`.
- `测试数据/性能曲线/` — performance curves.
