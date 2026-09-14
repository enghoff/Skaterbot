# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9", "shapely>=2.0", "matplotlib>=3.8", "numpy>=1.26"]
# ///
"""Write the carrier out as a KiCad board, so KiCad's own DRC can agree with ours.

    uv run electrical/carrier_kicad.py

electrical/carrier_pcb.py is where the board is designed and checked. This file
translates what it produces -- the outline, every footprint and pad, every track,
every via and the two ground pours -- into electrical/kicad/carrier.kicad_pcb,
which KiCad 7 or 8 opens directly. From there come the Gerbers, the drill files,
the 3D view and a second opinion on the design rules.

WHY A TRANSLATION AND NOT A SECOND DESIGN. Everything here is read from
carrier_pcb.py and nothing is decided here, so the two cannot disagree about
where a pad is. What KiCad adds is not geometry, it is INDEPENDENCE: its DRC was
written by other people and it does not share a bug with ours. If it complains,
one of the two is wrong and the disagreement is the finding.

WHAT THIS FILE DOES NOT CARRY ACROSS, and both are deliberate:

  * THE POURS ARE DECLARED, NOT COPIED. A KiCad zone is an outline plus a set of
    rules, and KiCad fills it itself. The outline written here is the board, the
    rules are the ones carrier_pcb.py poured to, and pressing B in KiCad gives
    its own answer. That answer SHOULD look like carrier_pcb.svg. If it does not,
    read the difference rather than the file.
  * THE SILKSCREEN IS REFERENCE DESIGNATORS ONLY. Nothing here draws part
    outlines, pin-one marks or polarity. That is a job for KiCad, where it can be
    seen while it is done.

THE Y AXIS TURNS OVER. This project measures the board with y forward and up the
page; KiCad measures it with y down the page. Both look at the board from above,
so the same physical board has y negated between them, and every coordinate here
is written as BOARD_D - y for that reason. It is a change of convention and not a
mirror: a footprint's rotation turns over with it, which is why the angles below
come out negative.
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "electrical"))

import carrier_pcb as pcb  # noqa: E402

OUT = ROOT / "electrical" / "kicad"

# Where the board is put on KiCad's page. A4 landscape with the board an inch in
# from the corner, which is where KiCad's own templates put things.
OFFSET_X = 25.0
OFFSET_Y = 25.0


def place(x: float, y: float) -> tuple[float, float]:
    """A point on the board, in KiCad's frame."""
    return (OFFSET_X + x, OFFSET_Y + pcb.BOARD_D - y)


LAYERS = """  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (42 "Eco1.User" user "User.Eco1")
    (43 "Eco2.User" user "User.Eco2")
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user)
    (49 "F.Fab" user)
  )"""


def setup() -> str:
    """The design rules, taken from carrier_pcb.py rather than typed again."""
    return """  (setup
    (pad_to_mask_clearance 0.05)
    (allow_soldermask_bridges_in_footprints no)
    (pcbplotparams
      (layerselection 0x00010fc_ffffffff)
      (plot_on_all_layers_selection 0x0000000_00000000)
      (disableapertmacros no)
      (usegerberextensions no)
      (usegerberattributes yes)
      (usegerberadvancedattributes yes)
      (creategerberjobfile yes)
      (dashed_line_dash_ratio 12.000000)
      (dashed_line_gap_ratio 3.000000)
      (svgprecision 4)
      (plotframeref no)
      (viasonmask no)
      (mode 1)
      (useauxorigin no)
      (hpglpennumber 1)
      (hpglpenspeed 20)
      (hpglpendiameter 15.000000)
      (pdf_front_fp_property_popups yes)
      (pdf_back_fp_property_popups yes)
      (dxfpolygonmode yes)
      (dxfimperialunits yes)
      (dxfusepcbnewfont yes)
      (psnegative no)
      (psa4output no)
      (plotreference yes)
      (plotvalue no)
      (plotfptext yes)
      (plotinvisibletext no)
      (sketchpadsonfab no)
      (subtractmaskfromsilk no)
      (outputformat 1)
      (mirror no)
      (drillshape 1)
      (scaleselection 1)
      (outputdirectory "gerber/")
    )
  )
  (net 0 "")"""


def nets(parts) -> tuple[dict[str, int], str]:
    """Every net in the netlist, numbered the way the board file wants them."""
    named = sorted(
        {net for net in pcb.net_of_pads(parts).values() if not net.startswith("~")}
    )
    index = {net: n + 1 for n, net in enumerate(named)}
    lines = "\n".join(f'  (net {n} "{net}")' for net, n in index.items())
    return index, lines


def pad_shape(pad: pcb.Pad) -> str:
    if pad.shape == "rect":
        return "rect"
    if pad.shape == "oval" and abs(pad.w - pad.h) > 1e-9:
        return "oval"
    return "circle"


def footprint(part: pcb.Placed, index: dict[str, int], net_of) -> str:
    """One placed part, with its pads where carrier_pcb.py puts them.

    The footprint is written at the part's own station with the pads at their
    offsets in its frame, so it stays a part that can be picked up and moved in
    KiCad rather than a scatter of pads at absolute coordinates.
    """
    x, y = place(part.x, part.y)
    angle = (-part.rotation) % 360
    out = [
        f'  (footprint "{part.refdes}"',
        '    (layer "F.Cu")',
        f"    (at {x:.4f} {y:.4f}{'' if angle == 0 else f' {angle}'})",
        f'    (descr "{part.footprint.name}")',
        "    (attr through_hole)",
        f'    (property "Reference" "{part.refdes}"',
        f"      (at 0 -{pcb.BOARD_D / 46 * 3:.2f} {angle})",
        '      (layer "F.SilkS")',
        "      (effects (font (size 1 1) (thickness 0.15)))",
        "    )",
    ]
    for pad in part.footprint.pads:
        net = net_of.get((part.refdes, pad.name))
        number = index.get(net, 0)
        name = net if number else ""
        out.append(
            f'    (pad "{pad.name}" thru_hole {pad_shape(pad)}'
            f" (at {pad.x:.4f} {-pad.y:.4f}{'' if angle == 0 else f' {angle}'})"
            f" (size {pad.w:.4f} {pad.h:.4f}) (drill {pad.drill:.4f})"
            f' (layers "*.Cu" "*.Mask")'
            f' (net {number} "{name}"))'
        )
    for hx, hy, diameter in part.footprint.holes:
        out.append(
            f'    (pad "" np_thru_hole circle (at {hx:.4f} {-hy:.4f})'
            f" (size {diameter:.4f} {diameter:.4f}) (drill {diameter:.4f})"
            f' (layers "F&B.Cu" "*.Mask"))'
        )
    out.append("  )")
    return "\n".join(out)


def bare_hole(x: float, y: float, diameter: float, name: str) -> str:
    """A drilled hole with nothing on it: a mounting hole, or an SBC post's."""
    px, py = place(x, y)
    return "\n".join(
        [
            f'  (footprint "{name}"',
            '    (layer "F.Cu")',
            f"    (at {px:.4f} {py:.4f})",
            "    (attr through_hole exclude_from_pos_files exclude_from_bom)",
            '    (pad "" np_thru_hole circle (at 0 0)'
            f" (size {diameter:.4f} {diameter:.4f}) (drill {diameter:.4f})"
            ' (layers "F&B.Cu" "*.Mask"))',
            "  )",
        ]
    )


def outline() -> str:
    """The board's edge, as four lines."""
    corners = [(0, 0), (pcb.BOARD_W, 0), (pcb.BOARD_W, pcb.BOARD_D), (0, pcb.BOARD_D)]
    out = []
    for i in range(4):
        ax, ay = place(*corners[i])
        bx, by = place(*corners[(i + 1) % 4])
        out.append(
            f"  (gr_line (start {ax:.4f} {ay:.4f}) (end {bx:.4f} {by:.4f})"
            ' (stroke (width 0.1) (type solid)) (layer "Edge.Cuts"))'
        )
    return "\n".join(out)


def tracks(routed, index) -> str:
    out = []
    for track in routed:
        layer = "F.Cu" if track.layer == "top" else "B.Cu"
        number = index.get(track.net, 0)
        for (ax, ay), (bx, by) in zip(track.points, track.points[1:]):
            sx, sy = place(ax, ay)
            ex, ey = place(bx, by)
            out.append(
                f"  (segment (start {sx:.4f} {sy:.4f}) (end {ex:.4f} {ey:.4f})"
                f' (width {track.width:.4f}) (layer "{layer}") (net {number}))'
            )
    return "\n".join(out)


def vias(placed, index) -> str:
    out = []
    for via in placed:
        x, y = place(via.x, via.y)
        out.append(
            f"  (via (at {x:.4f} {y:.4f}) (size {pcb.VIA_PAD:.4f})"
            f" (drill {pcb.VIA_DRILL:.4f})"
            f' (layers "F.Cu" "B.Cu") (net {index.get(via.net, 0)}))'
        )
    return "\n".join(out)


def zones(index) -> str:
    """One ground pour per layer, declared rather than copied.

    The outline is the whole board; the rules are carrier_pcb.py's. KiCad fills
    it, and what it fills should look like the pour in carrier_pcb.svg.
    """
    number = index.get(pcb.POUR_NET, 0)
    corners = [(0, 0), (pcb.BOARD_W, 0), (pcb.BOARD_W, pcb.BOARD_D), (0, pcb.BOARD_D)]
    points = " ".join(
        f"(xy {px:.4f} {py:.4f})" for px, py in (place(*c) for c in corners)
    )
    out = []
    for layer in ("F.Cu", "B.Cu"):
        out.append(
            "\n".join(
                [
                    f'  (zone (net {number}) (net_name "{pcb.POUR_NET}")'
                    f' (layer "{layer}")',
                    "    (hatch edge 0.5)",
                    f"    (connect_pads (clearance {pcb.POUR_CLEARANCE:.4f}))",
                    f"    (min_thickness {pcb.TRACK:.4f})",
                    "    (filled_areas_thickness no)",
                    "    (fill yes (thermal_gap "
                    f"{pcb.THERMAL_GAP:.4f}) (thermal_bridge_width "
                    f"{pcb.THERMAL_SPOKE:.4f}))",
                    f"    (polygon (pts {points}))",
                    "  )",
                ]
            )
        )
    return "\n".join(out)


PROJECT = """{
  "board": {
    "design_settings": {
      "defaults": {
        "board_outline_line_width": 0.1,
        "copper_line_width": 0.25,
        "silk_line_width": 0.15,
        "silk_text_size_h": 1.0,
        "silk_text_size_v": 1.0,
        "silk_text_thickness": 0.15
      },
      "rules": {
        "min_clearance": 0.2,
        "min_copper_edge_clearance": 0.3,
        "min_hole_clearance": 0.25,
        "min_through_hole_diameter": 0.4,
        "min_track_width": 0.25,
        "min_via_annular_width": 0.15,
        "min_via_diameter": 0.8
      }
    }
  },
  "meta": { "filename": "carrier.kicad_pro", "version": 1 },
  "net_settings": {
    "classes": [
      {
        "clearance": 0.2,
        "microvia_diameter": 0.3,
        "microvia_drill": 0.1,
        "name": "Default",
        "track_width": 0.25,
        "via_diameter": 0.8,
        "via_drill": 0.4
      }
    ]
  },
  "sheets": [],
  "text_variables": {}
}
"""


def build() -> tuple[str, dict]:
    report = pcb.Report()
    parts = pcb.placed()
    pcb.check_footprints(report)
    pcb.check_placement(report, parts)
    routed, placedVias = pcb.route(parts, report)
    items = pcb.build_copper(parts, routed, placedVias)
    for _ in range(3):
        islands = pcb.ground_islands(items)
        if len(islands) < 2:
            break
        hop, hopVias = pcb.join_islands(parts, routed, placedVias, islands, report)
        if not hop and not hopVias:
            break
        routed += hop
        placedVias += hopVias
        items = pcb.build_copper(parts, routed, placedVias)
    pcb.check_copper(report, parts, items)
    pcb.check_connectivity(report, items)
    if report.faults:
        return "", {"faults": report.faults}

    index, netLines = nets(parts)
    net_of = {
        endpoint: net
        for net, endpoints in pcb.carrier.NETS.items()
        for endpoint in endpoints
    }
    body = [
        '(kicad_pcb (version 20221018) (generator "carrier_kicad.py")',
        f"  (general (thickness {pcb.e.pcbThickness}))",
        '  (paper "A4")',
        LAYERS,
        setup(),
        netLines,
    ]
    for part in parts:
        body.append(footprint(part, index, net_of))
    for n, (x, y) in enumerate(pcb.MOUNTS, start=1):
        body.append(bare_hole(x, y, pcb.e.m3Clearance, f"MountingHole_M3_{n}"))
    for n, (x, y) in enumerate(pcb.POSTS, start=1):
        body.append(bare_hole(x, y, pcb.e.sbcPostClearance, f"SBC_Post_Clearance_{n}"))
    body.append(outline())
    body.append(tracks(routed, index))
    body.append(vias(placedVias, index))
    body.append(zones(index))
    body.append(")")
    counts = {
        "parts": len(parts),
        "pads": sum(len(p.footprint.pads) for p in parts),
        "tracks": len(routed),
        "vias": len(placedVias),
        "nets": len(index),
    }
    return "\n".join(body) + "\n", counts


def main() -> int:
    text, counts = build()
    if not text:
        print("carrier board: FAILED, not exporting a board that does not check out")
        for fault in counts["faults"]:
            print(f"  {fault}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "carrier.kicad_pcb").write_text(text, encoding="utf-8")
    (OUT / "carrier.kicad_pro").write_text(PROJECT, encoding="utf-8")
    print(f"wrote {OUT / 'carrier.kicad_pcb'}")
    print(
        f"  {counts['parts']} parts, {counts['pads']} pads, {counts['nets']} nets, "
        f"{counts['tracks']} track segments, {counts['vias']} vias"
    )
    print()
    print("IN KICAD, IN THIS ORDER:")
    print("  1. open electrical/kicad/carrier.kicad_pcb")
    print("  2. Edit > Fill All Zones (B) -- the pours are declared, not copied")
    print("  3. Inspect > Design Rules Checker, and read what it says")
    print("  4. File > Fabrication Outputs > Gerbers, and again for the drill files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
