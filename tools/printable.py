"""What a printer will be handed, checked the way a printer reads it.

Shared by tools/export.py, which will not write a file that fails it, and
tools/gate_g.py, which holds every printed piece to it on every run.

WHY A SECOND LIBRARY, when OCCT already answers these questions. Because OCCT
answered the one that mattered wrongly, and every check in this repository
asked OCCT. The first printed pelvis came back without all but one of its floor
posts, both battery rails, the battery-board guides and the IMU seat: sixteen of
its twenty-two bodies only rested face-to-face on the shell. Gates B and E unite
a piece before measuring it, OCCT happily unites bodies that merely touch, and
so every gate saw one part where the printer was handed twenty-two. The checks
here run on a TRIANGLE MESH, which is what a slicer actually receives, and
decide connectivity, closure and thickness with trimesh rather than with the
kernel that drew the part.

THE LIMITS ARE THE STRICTEST OF THE PROCESSES THIS ROBOT MIGHT BE PRINTED BY,
so that a piece that passes here prints on any of them: FDM at a 0.4 mm nozzle,
SLS and MJF nylon, and resin.

* MIN_WALL_MM, 1.0. FDM needs two perimeters of a 0.4 mm nozzle, 0.8 mm, to
  close a wall at all; the nylon bureaus publish 0.7 to 1.0 as a minimum for
  a wall that survives depowdering; resin is happier thinner. 1.0 covers them
  all with a fifth to spare on the tightest.
* MIN_GAP_MM, 0.5. Two faces of the same part closer than this fuse shut in a
  powder bed -- the laser's heat sinters the powder between them -- and bridge
  or string shut in FDM. It is a gap WITHIN one piece; the air between two
  parts that have to fit together is tools/gate_h.py's subject.
* An ISLAND, in the orientation the piece is declared to print in, is a part
  of a layer that has nothing under it in the layer below: a feature that
  starts in mid-air. FDM cannot print one without support, and support in a
  closed cavity cannot be got out. Printed rim-down, the pelvis has nine of
  them, which is the other way its floor posts could have been lost.

What is NOT checked here, and should not be mistaken for covered: overhang
angle (a vendor adds support for that and support is routine), strength (an
FDM part is far weaker across its layers than along them, which is a margin
question for each part, not a rule), and the fit of a hole to what goes in it
(tools/gate_e.py asserts those feature by feature).
"""

from __future__ import annotations

import numpy as np
import trimesh

MIN_WALL_MM = 1.0
MIN_GAP_MM = 0.5

# The layer the island search slices at. A layer thinner than any process
# prints finds every island a real one would; a coarser one could step over a
# thin feature's first layer.
LAYER_MM = 0.2

# How finely a solid is turned into triangles for these checks. A chord across a
# convex round lies inside the material by at most the tolerance, which makes a
# wall there read thinner than it is, so the wall limit is relaxed by exactly
# that much and no more.
TESSELLATE_MM = 0.02
TESSELLATE_ANGLE = 0.2
SAG_ALLOWANCE_MM = 0.025

# How far a sliced island has to be from the layer below before it counts, and
# how big it has to be. Both are there to keep tessellation noise out, and both
# are far below any feature that could be printed.
ISLAND_TOUCH_MM = 0.05
ISLAND_MIN_AREA_MM2 = 0.05

# How many surface samples the ray checks cast, on top of one per triangle. The
# triangles alone are dense exactly where features are small, which is where a
# thin wall hides; the even samples cover the big flat faces.
SAMPLES = 40000

ORIENTATIONS = ("+Z", "-Z", "+X", "-X", "+Y", "-Y")


def mesh_of(shape) -> trimesh.Trimesh:
    """A build123d shape as one triangle mesh, vertices shared across faces."""
    vertices, triangles = shape.tessellate(TESSELLATE_MM, TESSELLATE_ANGLE)
    return trimesh.Trimesh(
        np.array([[v.X, v.Y, v.Z] for v in vertices], dtype=float),
        np.array(triangles, dtype=np.int64),
        process=True,
    )


def integrity(mesh: trimesh.Trimesh, volume: float | None = None) -> list[str]:
    """Why this mesh is not one closed printable body, or nothing if it is.

    `volume` is the solid's own volume, when there is one to compare with: a
    mesh that encloses much less than the solid it came from has lost faces.
    """
    found = []
    parts = mesh.split(only_watertight=False)
    if len(parts) != 1:
        found.append(
            f"{len(parts)} separate pieces of surface where there must be one -- "
            "a body that does not reach the rest, or a sealed cavity"
        )
    if not mesh.is_watertight:
        found.append("the surface is not closed")
    if not mesh.is_winding_consistent:
        found.append("the surface's faces are not consistently oriented")
    if mesh.volume <= 0.0:
        found.append("the surface encloses no volume -- turned inside out")
    elif volume is not None and abs(mesh.volume - volume) > 0.005 * volume:
        found.append(
            f"the surface encloses {mesh.volume:.1f} mm3 where the solid is "
            f"{volume:.1f} -- faces lost on the way out"
        )
    return found


def _rays(mesh: trimesh.Trimesh, outward: bool, limit: float) -> tuple:
    """(points, distances) where a ray off the surface meets an OPPOSING face
    within `limit`.

    Inward along the normal measures the wall a point is on; outward measures
    the air in front of it. Only a hit on a face turned back towards the ray
    counts -- two faces of one wall, or the two sides of one gap -- which is
    what stops a ray grazing the next face round a corner from reading as a
    wall of nothing.
    """
    points, which = trimesh.sample.sample_surface_even(mesh, SAMPLES, seed=0)
    points = np.vstack([points, mesh.triangles_center])
    which = np.concatenate([which, np.arange(len(mesh.faces))])
    normals = mesh.face_normals[which]
    direction = normals if outward else -normals
    origins = points + direction * 1e-4
    hits, ray, face = mesh.ray.intersects_location(
        origins, direction, multiple_hits=False
    )
    distance = np.linalg.norm(hits - origins[ray], axis=1)
    opposing = (mesh.face_normals[face] * normals[ray]).sum(axis=1) < -0.5
    keep = (distance < limit) & opposing
    return points[ray][keep], distance[keep]


def _worst(points: np.ndarray, values: np.ndarray, count: int = 5) -> list:
    """The worst few, one per 2 mm cell, so one thin web is not reported fifty times."""
    order = np.argsort(values)
    seen = set()
    out = []
    for i in order:
        cell = tuple(np.round(points[i] / 2.0).astype(int))
        if cell in seen:
            continue
        seen.add(cell)
        out.append((tuple(round(float(c), 1) for c in points[i]), float(values[i])))
        if len(out) == count:
            break
    return out


def thin_walls(mesh: trimesh.Trimesh, limit: float = MIN_WALL_MM) -> list:
    """[(where, thickness), ...] for every wall thinner than `limit`, worst first."""
    points, distance = _rays(mesh, outward=False, limit=limit - SAG_ALLOWANCE_MM)
    return _worst(points, distance)


def narrow_gaps(mesh: trimesh.Trimesh, limit: float = MIN_GAP_MM) -> list:
    """[(where, gap), ...] for every gap within the part narrower than `limit`."""
    points, distance = _rays(mesh, outward=True, limit=limit)
    return _worst(points, distance)


def islands(mesh: trimesh.Trimesh, up: str) -> list:
    """[(height above the bed, area, where), ...]: what starts in mid-air.

    The piece is sliced every LAYER_MM along `up`, which is one of ORIENTATIONS
    and names the part's own axis that points away from the bed. A region of a
    slice that neither overlaps nor touches the slice below it is an island.
    """
    from shapely.ops import unary_union

    axis = "XYZ".index(up[1])
    sign = -1.0 if up[0] == "-" else 1.0
    normal = np.zeros(3)
    normal[axis] = sign
    low, high = mesh.bounds
    start = low[axis] if sign > 0 else -high[axis]
    end = high[axis] if sign > 0 else -low[axis]
    heights = np.arange(start + LAYER_MM / 2, end, LAYER_MM)
    sections = mesh.section_multiplane(
        plane_origin=np.zeros(3), plane_normal=normal, heights=heights
    )
    found = []
    below = None
    for height, section in zip(heights, sections):
        regions = list(section.polygons_full) if section is not None else []
        if below is not None:
            for region in regions:
                if region.area < ISLAND_MIN_AREA_MM2:
                    continue
                if not region.buffer(ISLAND_TOUCH_MM).intersects(below):
                    # The slice is in its own plane's frame; say where the island
                    # is in the part's, which is where anyone will look for it.
                    x, y = region.centroid.coords[0]
                    to_3d = section.metadata.get("to_3D", np.eye(4))
                    where = (to_3d @ np.array([x, y, 0.0, 1.0]))[:3]
                    found.append(
                        (
                            round(float(height - start), 1),
                            round(float(region.area), 1),
                            tuple(round(float(c), 1) for c in where),
                        )
                    )
        below = unary_union(regions) if regions else unary_union([])
    return found
