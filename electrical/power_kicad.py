"""Build the power switch board in KiCad, from what electrical/power_pcb.py found.

    <KiCad>/bin/python.exe electrical/power_kicad.py electrical/kicad_power/power_board.json

THIS ONE RUNS INSIDE KICAD'S OWN PYTHON and nowhere else, which is the whole
point of it: the footprints are loaded from KiCad's libraries by KiCad, the
zones are filled by KiCad's own filler, and the file is written by KiCad's
writer. Nothing here re-implements a board format, so there is no second
opinion about what a pad is for KiCad's design rule check to disagree with.

electrical/power_pcb.py calls this as a subprocess and then reads back
pads.json, which is where every pad ended up, and holds it against where it
meant to put them. The two frames have to agree to a hundredth of a millimetre
or the board is not accepted.
"""

from __future__ import annotations

import json
import sys

import pcbnew

MM = pcbnew.FromMM
LAYER = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}


def point(x: float, y: float):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def build(spec: dict) -> None:
    board = pcbnew.BOARD()
    settings = board.GetDesignSettings()
    settings.SetCopperLayerCount(2)
    settings.m_TrackMinWidth = MM(0.2)
    settings.m_MinClearance = MM(0.2)
    settings.m_ViasMinSize = MM(0.6)
    settings.m_MinThroughDrill = MM(0.3)
    settings.m_HoleToHoleMin = MM(0.25)
    settings.m_CopperEdgeClearance = MM(0.3)

    nets = {}

    def net(name: str):
        if name not in nets:
            item = pcbnew.NETINFO_ITEM(board, name)
            board.Add(item)
            nets[name] = item
        return nets[name]

    # The outline, drawn as segments so the shape is whatever was passed in.
    outline = spec["outline"]
    for (ax, ay), (bx, by) in zip(outline, outline[1:] + outline[:1]):
        edge = pcbnew.PCB_SHAPE(board)
        edge.SetShape(pcbnew.SHAPE_T_SEGMENT)
        edge.SetStart(point(ax, ay))
        edge.SetEnd(point(bx, by))
        edge.SetLayer(pcbnew.Edge_Cuts)
        edge.SetWidth(MM(0.1))
        board.Add(edge)

    # The three mounting holes, each its own footprint with one unplated pad.
    for hole in spec["holes"]:
        holder = pcbnew.FOOTPRINT(board)
        holder.SetReference(hole["name"])
        holder.SetPosition(point(hole["x"], hole["y"]))
        pad = pcbnew.PAD(holder)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetSize(point(hole["d"], hole["d"]))
        pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_CIRCLE)
        pad.SetDrillSize(point(hole["d"], hole["d"]))
        pad.SetLayerSet(pad.UnplatedHoleMask())
        pad.SetPosition(point(hole["x"], hole["y"]))
        holder.Add(pad)
        board.Add(holder)

    placed = {}
    for part in spec["parts"]:
        footprint = pcbnew.FootprintLoad(part["lib"], part["fp"])
        if footprint is None:
            raise SystemExit(
                f"{part['ref']}: no footprint {part['fp']} in {part['lib']}"
            )
        board.Add(footprint)
        footprint.SetReference(part["ref"])
        footprint.SetValue(part["value"])
        # THE REFERENCES GO ON THE FABRICATION LAYER, not the silkscreen. On a
        # board this dense the library footprints' own outlines already fill the
        # silk, and forty-nine reference texts on top of them are forty-nine
        # things KiCad correctly reports as printed over each other. The
        # assembly drawing carries them instead.
        for text in (footprint.Reference(), footprint.Value()):
            text.SetLayer(pcbnew.F_Fab)
            text.SetVisible(text is footprint.Reference())
        footprint.SetPosition(point(part["x"], part["y"]))
        footprint.SetOrientationDegrees(part["rot"])
        # KEYED BY ORDER AND NOT BY PIN NUMBER, because a footprint may carry
        # the same number twice: the fuse holder has two pads on each of its
        # pins. Keyed by number, the second would overwrite the first and the
        # check on the far side would compare a pad against its neighbour.
        for index, pad in enumerate(footprint.Pads()):
            name = pad.GetNumber()
            if name in part["pads"]:
                pad.SetNet(net(part["pads"][name]))
            placed[f"{part['ref']}#{index}"] = [
                pcbnew.ToMM(pad.GetPosition().x),
                pcbnew.ToMM(pad.GetPosition().y),
            ]

    for track in spec["tracks"]:
        points = track["points"]
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            segment = pcbnew.PCB_TRACK(board)
            segment.SetStart(point(ax, ay))
            segment.SetEnd(point(bx, by))
            segment.SetWidth(MM(track["width"]))
            segment.SetLayer(LAYER[track["layer"]])
            segment.SetNet(net(track["net"]))
            board.Add(segment)

    for via in spec["vias"]:
        through = pcbnew.PCB_VIA(board)
        through.SetPosition(point(via["x"], via["y"]))
        through.SetViaType(pcbnew.VIATYPE_THROUGH)
        through.SetWidth(MM(via["d"]))
        through.SetDrill(MM(via["drill"]))
        through.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        through.SetNet(net(via["net"]))
        board.Add(through)

    for spec_zone in spec["zones"]:
        zone = pcbnew.ZONE(board)
        layers = pcbnew.LSET()
        for layer in spec_zone["layers"]:
            layers.addLayer(LAYER[layer])
        zone.SetLayerSet(layers)
        zone.SetNet(net(spec_zone["net"]))
        zone.SetAssignedPriority(spec_zone["priority"])
        zone.SetLocalClearance(MM(spec_zone["clearance"]))
        zone.SetMinThickness(MM(spec_zone["min_width"]))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in spec_zone["polygon"]:
            outline.Append(MM(x), MM(y))
        for index, hole in enumerate(spec_zone.get("holes", [])):
            outline.NewHole(0)
            for x, y in hole:
                outline.Append(MM(x), MM(y), 0, index)
        board.Add(zone)

    title = pcbnew.PCB_TEXT(board)
    title.SetText(spec["title"])
    title.SetLayer(pcbnew.Cmts_User)
    lowest = max(y for _, y in spec["outline"])
    title.SetPosition(point(spec["outline"][0][0], lowest + 4.0))
    title.SetTextSize(point(1.2, 1.2))
    board.Add(title)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(spec["board"], board)
    with open(spec["pads_out"], "w", encoding="utf-8") as out:
        json.dump(placed, out, indent=1)


if __name__ == "__main__":
    build(json.loads(open(sys.argv[1], encoding="utf-8").read()))
