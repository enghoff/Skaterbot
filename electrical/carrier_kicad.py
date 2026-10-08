# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1", "shapely>=2.0", "matplotlib>=3.8", "numpy>=1.26"]
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
  * THE SILKSCREEN IS DRAWN HERE, and it is the one thing on this board that is
    not copper and not a hole. Each part gets its outline, a pin-one dot and its
    reference designator, and each connector gets its function spelled out beside
    it, because this is a board with three identical four-way plugs on one edge.
    Every line is clipped off every pad first, so the DRC's silk-over-pad rule
    has nothing to say.

THE Y AXIS TURNS OVER. This project measures the board with y forward and up the
page; KiCad measures it with y down the page. Both look at the board from above,
so the same physical board has y negated between them, and every coordinate here
is written as BOARD_D - y for that reason. It is a change of convention and not a
mirror. A FOOTPRINT'S ANGLE IS NOT NEGATED WITH IT: the pad offsets inside a
footprint are already written y-flipped, and KiCad turns them with the same
handedness this project does, so the angle goes out as it stands. footprint()
carries what happened when it did not.
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
import carrier_sch  # noqa: E402

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


def export_net_of(parts):
    """Match Eeschema's local-label and explicit no-connect net names."""
    connected = carrier_sch.net_of_pin()
    components = {p.refdes: p for p in pcb.carrier.PARTS}
    return {
        (part.refdes, pad.name): connected.get(
            (part.refdes, pad.name),
            f"unconnected-({part.refdes}-{components[part.refdes].pins[pad.name]}-Pad{pad.name})",
        )
        for part in parts
        for pad in part.footprint.pads
    }


def net_name(net: str) -> str:
    return net if net.startswith("unconnected-(") else "/" + net


def nets(parts) -> tuple[dict[str, int], str]:
    """Every net in the netlist, numbered the way the board file wants them."""
    named = sorted(set(export_net_of(parts).values()))
    index = {net: n + 1 for n, net in enumerate(named)}
    lines = "\n".join(f'  (net {n} "{net_name(net)}")' for net, n in index.items())
    return index, lines


def pad_shape(pad: pcb.Pad) -> str:
    if pad.shape == "rect":
        return "rect"
    if pad.shape == "oval" and abs(pad.w - pad.h) > 1e-9:
        return "oval"
    return "circle"


# WHAT THE SILKSCREEN IS DRAWN FROM. A part's outline is the bodies it occupies,
# which carrier_pcb.py already knows because it measures them against the torso.
# The three below are excluded from it: a plug is not on the board, a cable tie
# is not the part it holds, and a thermal sheet is cut from a roll rather than
# placed on a mark.
NOT_AN_OUTLINE = ("plug", "wires", "cable tie", "thermal sheet")
SILK_WIDTH = 0.15
SILK_PAD_AIR = 0.2
# Silk to silk. KiCad measures this one edge to edge as well, and silk to the
# board's edge, where anything printed is half cut off by the router.
SILK_AIR = 0.2
SILK_EDGE = 0.3


def _outline_box(part: pcb.Placed):
    """The part's own extent in its own frame: x0 y0 x1 y1, or None."""
    boxes = [
        body.box
        for body in part.footprint.bodies
        if not any(word in body.what for word in NOT_AN_OUTLINE)
    ]
    if not boxes:
        pads = part.footprint.pads
        if not pads:
            return None
        return (
            min(p.x - p.w / 2 for p in pads) - 0.5,
            min(p.y - p.h / 2 for p in pads) - 0.5,
            max(p.x + p.w / 2 for p in pads) + 0.5,
            max(p.y + p.h / 2 for p in pads) + 0.5,
        )
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


class Silk:
    """Everything printed on the board, placed once and knowing about itself.

    SILK IS THE ONE LAYER WHERE EVERY PART HAS TO SEE THE OTHERS. A footprint
    drawn on its own puts its outline 0.2 mm off its own pads and prints it
    straight over its neighbour's, and KiCad calls both of those an error: silk
    over a pad is scraped off by the fab, and silk over silk cannot be read. So
    this collects every pad and hole on the board first, then lays each part's
    outline, its pin-one dot and every legend down in turn, cutting each against
    what is already there.
    """

    def __init__(self, parts: list[pcb.Placed]) -> None:
        from shapely.geometry import Point
        from shapely.geometry import box as rectangle
        from shapely.ops import unary_union

        self.parts = parts
        pads = []
        for part in parts:
            for pad, x, y, w, h in part.pads():
                pads.append(Point(x, y).buffer(max(w, h) / 2 + SILK_PAD_AIR, 8))
            for hx, hy, diameter in part.holes():
                pads.append(Point(hx, hy).buffer(diameter / 2 + SILK_PAD_AIR, 8))
        for x, y in pcb.MOUNTS:
            pads.append(Point(x, y).buffer(pcb.MOUNT_COPPER_KEEPOUT, 8))
        for x, y in pcb.STANDOFFS:
            pads.append(Point(x, y).buffer(pcb.STANDOFF_COPPER_KEEPOUT, 8))
        self.copper = unary_union(pads)
        self.drawn = []  # what is already printed, buffered by SILK_AIR
        self.room = rectangle(0, 0, pcb.BOARD_W, pcb.BOARD_D).buffer(-SILK_EDGE)

    def clear(self, shape) -> bool:
        """Room for this on the silkscreen: off the pads, off the other silk,
        and inside the board rather than half printed over its routed edge."""
        return (
            shape.within(self.room)
            and not shape.intersects(self.copper)
            and not any(shape.intersects(other) for other in self.drawn)
        )

    def take(self, shape) -> None:
        self.drawn.append(shape.buffer(SILK_AIR))

    def reference(self, part: pcb.Placed) -> tuple[float, float]:
        """Where the part's own name goes: the first clear station round it.

        In the part's own frame, because that is where it is written. A refdes
        printed over the part next door is as unreadable as one printed over a
        pad, and on this board the gaps are 3 mm.
        """
        box = _outline_box(part)
        if box is None:
            return (0.0, -3.0)
        x0, y0, x1, y1 = box
        middle = ((x0 + x1) / 2, (y0 + y1) / 2)
        stations = [
            (middle[0], y1 + 1.2),
            (middle[0], y0 - 1.2),
            (middle[0], y1 + 2.4),
            (middle[0], y0 - 2.4),
            (x1 + 2.0, middle[1]),
            (x0 - 2.0, middle[1]),
        ]
        for at in stations:
            shape = _text_box(part.refdes, *part.at(*at))
            if self.clear(shape):
                self.take(shape)
                return at
        # Nowhere clear: put it inside the part's own outline, which is legible
        # on the two modules big enough for this to happen to and is at least on
        # the board.
        return middle

    def part_silk(self, part: pcb.Placed) -> list[str]:
        """One part's outline and pin-one dot, in the part's own frame."""
        from shapely.geometry import LineString, Point

        box = _outline_box(part)
        if box is None:
            return []
        x0, y0, x1, y1 = box
        out = []
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        for a, b in zip(corners, corners[1:]):
            line = LineString([part.at(*a), part.at(*b)])
            cut = line.difference(self.copper)
            for other in self.drawn:
                cut = cut.difference(other)
            for piece in getattr(cut, "geoms", [cut]):
                if piece.is_empty or piece.length < 0.6:
                    continue
                self.take(piece)
                (ax, ay), (bx, by) = piece.coords[0], piece.coords[-1]
                (ux, uy), (vx, vy) = part.un(ax, ay), part.un(bx, by)
                out.append(
                    f"    (fp_line (start {ux:.4f} {-uy:.4f}) (end {vx:.4f} {-vy:.4f})"
                    f' (stroke (width {SILK_WIDTH}) (type solid)) (layer "F.SilkS"))'
                )
        # A dot outside the outline at pin 1, on the diagonal away from the
        # middle, so that a part with its pads under it still says which end is
        # which.
        first = next(
            (pad for pad in part.footprint.pads if pad.name in ("1", "P1-1")), None
        )
        if first is None:
            return out
        dx = -1.0 if first.x < (x0 + x1) / 2 else 1.0
        dy = -1.0 if first.y < (y0 + y1) / 2 else 1.0
        at = (first.x + dx * (first.w / 2 + 0.7), first.y + dy * (first.h / 2 + 0.7))
        dot = Point(*part.at(*at)).buffer(0.25, 8)
        if self.clear(dot):
            self.take(dot)
            out.append(
                f"    (fp_circle (center {at[0]:.4f} {-at[1]:.4f})"
                f" (end {at[0] + 0.25:.4f} {-at[1]:.4f})"
                f" (stroke (width {SILK_WIDTH}) (type solid)) (fill solid)"
                ' (layer "F.SilkS"))'
            )
        return out


def footprint(part: pcb.Placed, index: dict[str, int], net_of, silk: Silk) -> str:
    """One placed part, with its pads where carrier_pcb.py puts them.

    The footprint is written at the part's own station with the pads at their
    offsets in its frame, so it stays a part that can be picked up and moved in
    KiCad rather than a scatter of pads at absolute coordinates.
    """
    x, y = place(part.x, part.y)
    # THE ANGLE IS NOT NEGATED, and the header above used to say it was. KiCad
    # turns a footprint's own geometry about its origin with x' = x cos + y sin,
    # y' = -x sin + y cos, which is the SAME handedness as this project's once
    # the pad offsets go in as (x, -y) -- the y flip is already in the offsets,
    # so negating the angle as well flips it back. EVERY PART ON THIS BOARD STOOD
    # AT 0 OR 180 UNTIL SEPTEMBER 2026, where the two signs agree, so nothing
    # showed it. The first capacitor placed at 270 came out reflected about its
    # own origin, 5.08 mm from where this file's own checks put it, with its
    # ground pad sitting on an I2C track -- which KiCad reported as a short
    # between two nets and carrier_pcb.py could not see, because the geometry it
    # checks was right and only what was written out was wrong.
    angle = part.rotation % 360
    box = _outline_box(part)
    item = next((p for p in pcb.carrier.PARTS if p.refdes == part.refdes), None)
    # THE REFDES IS AN fp_text AND NOT A PROPERTY. In the board format this file
    # writes, a footprint's (property ...) is a key and a value and nothing is
    # drawn from it; the reference and the value are fp_text items. Written the
    # other way round the board opens, passes DRC, and plots with no part names
    # on it at all -- which is how this was found, by plotting the silkscreen and
    # looking at it.
    silk_items = silk.part_silk(part)
    rx, ry = silk.reference(part)
    vx, vy = (box[0] + box[2]) / 2 if box else 0.0, (box[3] + 1.2) if box else 3.0
    out = [
        f'  (footprint "carrier:{part.refdes}"',
        '    (layer "F.Cu")',
        f"    (at {x:.4f} {y:.4f}{'' if angle == 0 else f' {angle}'})",
        f'    (descr "{part.footprint.name}")',
        "    (attr through_hole)",
        f'    (fp_text reference "{part.refdes}"',
        f"      (at {rx:.4f} {-ry:.4f}{'' if angle == 0 else f' {angle}'})",
        '      (layer "F.SilkS")',
        "      (effects (font (size 0.9 0.9) (thickness 0.14)))",
        "    )",
        f'    (fp_text value "{item.partNumber if item else part.footprint.name}"',
        f"      (at {vx:.4f} {-vy:.4f}{'' if angle == 0 else f' {angle}'})",
        '      (layer "F.Fab")',
        "      (effects (font (size 1 1) (thickness 0.15)))",
        "    )",
        *silk_items,
    ]
    for pad in part.footprint.pads:
        net = net_of.get((part.refdes, pad.name))
        number = index.get(net, 0)
        name = net_name(net) if number else ""
        # Solid connection on the two returns whose thermals were starved.
        connection = (
            " (zone_connect 2)"
            if f"{part.refdes}-{pad.name}" in pcb.SOLID_GROUND_PADS
            else ""
        )
        out.append(
            f'    (pad "{pad.name}" thru_hole {pad_shape(pad)}'
            f" (at {pad.x:.4f} {-pad.y:.4f}{'' if angle == 0 else f' {angle}'})"
            f" (size {pad.w:.4f} {pad.h:.4f}) (drill {pad.drill:.4f})"
            f' (layers "*.Cu" "*.Mask")'
            f' (net {number} "{name}"){connection})'
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
            "    (attr through_hole board_only exclude_from_pos_files exclude_from_bom)",
            f'    (fp_text reference "H_{name}" (at 0 0) (layer "F.Fab") hide'
            " (effects (font (size 1 1) (thickness 0.15))))",
            '    (pad "" np_thru_hole circle (at 0 0)'
            f" (size {diameter:.4f} {diameter:.4f}) (drill {diameter:.4f})"
            ' (layers "F&B.Cu" "*.Mask"))',
            "  )",
        ]
    )


# WHAT EACH CONNECTOR IS, PRINTED BESIDE IT. This board has three four-way plugs
# in a row on its rear edge and they are mechanically identical, so the only
# thing that stops a knee harness going into the wheel bus is what is written on
# the laminate. Short enough to fit the strip each connector leaves.
# Each one is tried in order and the first that fits is printed, because the
# rear edge has room for "BUS A HIP" beside one connector and not beside the next.
LEGENDS = {
    "J1": ("PWR IN", "PWR"),
    "J2": ("BUS A HIP", "BUS A"),
    "J3": ("BUS B KNEE", "BUS B"),
    "J4": ("BUS C WHEEL", "BUS C"),
    "J5": ("SBC",),
    "J6": ("IMU",),
    "J7": ("HOLD",),
    "JP1": ("IMU V",),
    "A2": ("BEC 5V",),
    "A3": ("INA226",),
}


# HOW BIG A LETTER IS ON THIS BOARD. KiCad's stroke font advances about one size
# per character and stands its size plus its stroke tall, and a legend has to be
# placed knowing that: silk printed over a pad is scraped off by the fab, and
# silk printed over other silk cannot be read. MEASURED BY KICAD AND NOT BY US --
# the first estimate here was 0.65 mm a character and its DRC found the overlap
# the 0.15 mm difference caused.
LEGEND_SIZE = 0.8
LEGEND_CHAR = 0.85
LEGEND_TALL = 1.25
LEGEND_AIR = 0.3


def _text_box(text: str, x: float, y: float):
    """What a centred legend occupies on the board, in board coordinates."""
    from shapely.geometry import box

    half = LEGEND_CHAR * len(text) / 2
    return box(x - half, y - LEGEND_TALL / 2, x + half, y + LEGEND_TALL / 2)


def legends(silk: Silk) -> str:
    """The function of each connector, beside it, and the board's own name.

    PLACED AGAINST THE BOARD RATHER THAN BESIDE THE PART. A first cut put each
    legend a fixed distance inboard of its connector, and KiCad's DRC found five
    of them printed over a pad and six over another part's outline: on a board
    whose parts stand 3 mm apart there is no offset that is always clear. So each
    is tried at a series of stations out from its part and along it, measured
    against every pad, every hole and everything already printed, and the first
    clear one wins. One that will not fit anywhere is left off rather than
    printed over a pin, and it says which, because a legend that cannot be read
    is worse than no legend at all.
    """
    out, missed = [], []
    for part in silk.parts:
        choices = LEGENDS.get(part.refdes)
        box = _outline_box(part)
        if choices is None or box is None:
            continue
        ends = [part.at(0.0, box[1])[1], part.at(0.0, box[3])[1]]
        low, high = min(ends), max(ends)
        middle = part.at(0.0, 0.0)[0]
        inward = -1.0 if low > pcb.BOARD_D / 2 else 1.0
        edge = low if inward < 0 else high
        stations = [
            (text, (middle + along, edge + inward * step))
            for text in choices
            for step in (1.4, 2.5, 3.6, 4.7, 5.8)
            for along in (0.0, -3.0, 3.0, -6.0, 6.0)
        ]
        for text, at in stations:
            shape = _text_box(text, *at)
            if silk.clear(shape):
                silk.take(shape)
                tx, ty = place(*at)
                out.append(
                    f'  (gr_text "{text}" (at {tx:.4f} {ty:.4f})'
                    ' (layer "F.SilkS")'
                    f" (effects (font (size {LEGEND_SIZE} {LEGEND_SIZE})"
                    f" (thickness 0.12))))"
                )
                break
        else:
            missed.append(f"{part.refdes} ({choices[-1]})")
    # The board's own name, in the one clear strip: the rear edge, left of the
    # IMU connector, where no part stands and no plug swings.
    tx, ty = place(20.0, 2.0)
    out.append(
        f'  (gr_text "BIPED CONTROLLER CARRIER" (at {tx:.4f} {ty:.4f})'
        ' (layer "F.SilkS")'
        " (effects (font (size 1.2 1.2) (thickness 0.2))))"
    )
    if missed:
        print(f"  note  no clear room for the legend on {', '.join(missed)}")
    return "\n".join(out)


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
                    f'  (zone (net {number}) (net_name "{net_name(pcb.POUR_NET)}")'
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
    parts, routed, placedVias, items = pcb.lay_out(report)
    pcb.check_against_cad(report, parts)
    pcb.check_leads_down(report, parts)
    if report.faults:
        return "", {"faults": report.faults}
    pcb.draw(pcb.SVG, parts, items)

    index, netLines = nets(parts)
    net_of = export_net_of(parts)
    body = [
        '(kicad_pcb (version 20221018) (generator "carrier_kicad.py")',
        f"  (general (thickness {pcb.e.pcbThickness}))",
        '  (paper "A4")',
        LAYERS,
        setup(),
        netLines,
    ]
    silk = Silk(parts)
    for part in parts:
        body.append(footprint(part, index, net_of, silk))
    for n, (x, y) in enumerate(pcb.MOUNTS, start=1):
        body.append(bare_hole(x, y, pcb.e.m3Clearance, f"MountingHole_M3_{n}"))
    for n, (x, y) in enumerate(pcb.STANDOFFS, start=1):
        body.append(bare_hole(x, y, pcb.e.sbcStandoffHole, f"SBC_Standoff_M2.5_{n}"))
    body.append(outline())
    body.append(legends(silk))
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


def write_footprint_library(board_text: str) -> None:
    """Export the same footprints as a local library for ERC and board updates."""
    import re

    library = OUT / "carrier.pretty"
    library.mkdir(exist_ok=True)
    for refdes in (p.refdes for p in pcb.carrier.PARTS):
        start = board_text.index(f'  (footprint "carrier:{refdes}"')
        # Generated footprints end at this indentation; nested items are deeper.
        end = board_text.index("\n  )", start) + len("\n  )")
        text = board_text[start:end].strip()
        text = text.replace(f'"carrier:{refdes}"', f'"{refdes}"', 1)
        text = text.replace(
            "\n    (layer",
            '\n    (version 20221018)\n    (generator "carrier_kicad.py")\n    (layer',
            1,
        )
        text = re.sub(r"\n    \(at [^\n]+\)", "", text, count=1)
        # Board pad/text angles include placement rotation; library parts sit
        # at zero. Keep coordinates local and remove only that angle.
        rotation = pcb.PLACEMENT[refdes][2]

        def local_angle(match):
            x, y, *angle = match.group(1).split()
            value = (float(angle[0]) if angle else 0.0) - rotation
            return f"(at {x} {y} {value % 360:g})"

        text = re.sub(r"\(at ([^)]*)\)", local_angle, text)
        text = re.sub(r' \(net \d+ "[^"]*"\)', "", text)
        (library / f"{refdes}.kicad_mod").write_text(text + "\n", encoding="utf-8")
    (OUT / "fp-lib-table").write_text(
        '(fp_lib_table\n  (lib (name "carrier")(type "KiCad")'
        '(uri "${KIPRJMOD}/carrier.pretty")(options "")(descr "Generated carrier footprints"))\n)\n',
        encoding="utf-8",
    )


def main() -> int:
    text, counts = build()
    if not text:
        print("carrier board: FAILED, not exporting a board that does not check out")
        for fault in counts["faults"]:
            print(f"  {fault}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "carrier.kicad_pcb").write_text(text, encoding="utf-8")
    write_footprint_library(text)
    # THE PROJECT FILE IS SEEDED ONCE AND THEN LEFT ALONE. It carries the design
    # rules this board is poured to, which is why it is written at all -- but it
    # is also where KiCad keeps its own migrated settings, its pinned libraries
    # and its window state, and KiCad rewrites it whenever the project is open.
    # Writing it on every run meant the two took turns overwriting each other.
    # Delete it to have the rules laid down again.
    project = OUT / "carrier.kicad_pro"
    seeded = not project.exists()
    if seeded:
        project.write_text(PROJECT, encoding="utf-8")
    # The schematic comes from the netlist rather than from the board, so it is
    # written by its own file -- but it is written here too, because a project
    # whose sheet and whose board were generated from different runs is exactly
    # the kind of disagreement this whole arrangement exists to prevent.
    if carrier_sch.main():
        return 1
    print(f"wrote {OUT / 'carrier.kicad_pcb'}")
    print(
        f"  {counts['parts']} parts, {counts['pads']} pads, {counts['nets']} nets, "
        f"{counts['tracks']} track segments, {counts['vias']} vias"
    )
    print()
    if not seeded:
        print("  kept the existing carrier.kicad_pro -- delete it to re-seed the rules")
    # KICAD READS A PROJECT'S LIBRARY TABLES ONCE, WHEN THE PROJECT OPENS. Write
    # a new schematic and a new symbol library under an editor that is already
    # holding the project and it goes on using the configuration it loaded, which
    # surfaces as "the current configuration does not include the symbol library"
    # on a library that is sitting right there. The lock files say whether that
    # has just happened, so say so rather than leaving it to be discovered.
    held = sorted(f.name for f in OUT.glob("~*.lck"))
    if held:
        print()
        print("  KICAD HAS THIS PROJECT OPEN: " + ", ".join(held))
        print("  Close the project and open it again before reading anything here.")
        print("  It is still using the library table it loaded when it started.")
    print()
    print("IN KICAD, IN THIS ORDER:")
    print("  0. open electrical/kicad/carrier.kicad_sch to read the netlist drawn")
    print("  1. open electrical/kicad/carrier.kicad_pcb")
    print("  2. Edit > Fill All Zones (B) -- the pours are declared, not copied")
    print("  3. Inspect > Design Rules Checker, and read what it says")
    print("  4. File > Fabrication Outputs > Gerbers, and again for the drill files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
