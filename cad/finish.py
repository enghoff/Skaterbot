"""Breaking the edges: what the printed parts look like when they are finished.

Every printed piece on this robot leaves the modeller as sharp arrises. This
module is the last step before one is printed or exported: it puts a 0.5 mm
chamfer on the OUTER edges of every body of the piece.

WHY THIS IS A SEPARATE MODULE AND NOT PART OF THE PART.

Because the gates depend on it being separate. tools/gate_b.py proves the ported
geometry is identical to what the Zoo engine built, edge for edge, and a chamfer
is by definition a change to that geometry. So the part modules keep building the
faithful shape, gate B keeps meaning what it meant, and the chamfer is applied
here, on top, where its cost can be measured on its own. That is the discipline
docs/BUILD123D_MIGRATION.md asks for in phase 3: one change, one measured delta.

WHICH EDGES, AND WHY NOT ALL OF THEM.

"Outer edges only." An edge is chamfered when every face meeting at it is either
flat or a CONVEX cylinder -- an outside rim, a boss, the circumference of a disc.
An edge on a CONCAVE cylinder is inside a hole, and those are left alone: the
Ø30.2 carrier bore, the Ø30 output register, the Ø22 spigot, the Ø10.2 journal
seat, every M3 clearance hole and every cap counterbore locate or fasten
something, and a chamfer on any of them changes a fit rather than breaking an
arris.

Convex or concave is decided from the geometry rather than guessed: take the
face's own outward normal where it sits, and the radial direction from the
cylinder's axis to the same point. Pointing the same way is a boss, pointing
opposite is a bore.

WHY IT IS DONE PER BODY, AND WHY THE PIECE IS NOT UNIONED AFTERWARDS.

A printed piece is modelled as several interpenetrating bodies. Chamfering their
union directly is what you would try first, and OCCT refuses it on every piece
here but the cover -- not because 0.5 mm is too big (it refuses 0.05 mm just as
firmly) and not because any single edge is bad (every one of them chamfers
alone), but because the chamfers interact once there are sixty of them on one
crowded solid.

Per body, every one of them succeeds. So that is what this does, and the piece is
left as the interpenetrating bodies it already was -- which is the form the whole
project ships in, the form mass_budget.toml counts and the STEP exports carry,
and the form a slicer merges into the single part it really is.

NOT UNIONING IS NOT LAZINESS, IT IS FORCED. A body whose chamfers were applied
one group at a time comes back reporting itself VALID, and then segfaults OCCT
the moment it takes part in any boolean -- even a union with a body it does not
touch. clean() and fix() do not help. So a union here does not fail, it takes the
process down, and no try/except can catch that. Pieces chamfered in a single pass
union perfectly well; it is only the ones that needed the fallback below.

What is left un-chamfered by working per body is the edges the union WOULD have
created where two bodies interpenetrate. Those are re-entrant corners, which is
exactly where a chamfer does not belong, so nothing is lost. And a chamfer cut on
an edge buried inside a neighbouring body is filled back in by the slicer's merge
just as a union would have filled it, so nothing is gained there either.

WHEN OCCT REFUSES A SET ANYWAY.

The set is bisected and the halves are tried in turn, down to single edges, so one
awkward edge costs one chamfer rather than the whole part. Edges are re-found on
each new solid by THE PAIR OF FACES THEY LIE BETWEEN rather than by position,
because a chamfer shortens its neighbours and moves their midpoints, while the
faces either side of them do not move at all.

A part that comes back with skipped edges is still correct. It has a few arrises
left sharp, and tools/finish_report.py says how many rather than passing over it.
"""

from __future__ import annotations

import build123d as bd
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_SurfaceType
from OCP.TopAbs import TopAbs_ShapeEnum
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS
from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape

# What a printed edge is broken by. 0.5 mm is a deburr, not a feature: it is
# about one and a half layers at this nozzle, enough to kill the sharp arris and
# the elephant-foot lip without touching anything structural.
CHAMFER = 0.5

_ROUND = 6


def _edge_faces(solid) -> list:
    """[(edge, [faces it lies between]), ...] for every edge of `solid`.

    Built from OCC's own ancestor map rather than by asking each face for its
    edges and comparing. The naive version is edges x faces comparisons and the
    bisection below rebuilds this on every recursion, which is what made the
    first working version take a hundred seconds on one clevis.
    """
    mapping = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(
        solid.wrapped,
        TopAbs_ShapeEnum.TopAbs_EDGE,
        TopAbs_ShapeEnum.TopAbs_FACE,
        mapping,
    )
    # The EDGES come from solid.edges(), not from the map. An edge re-wrapped
    # out of the map is geometrically right but has no idea which solid it
    # belongs to, and build123d's chamfer finds its target through exactly that
    # link -- so a chamfer asked for on one comes back "Nothing to chamfer".
    # The map is used only to look the adjacent faces up, which it does by shape
    # rather than by comparison, so this stays linear.
    out = []
    for edge in solid.edges():
        faces = [bd.Face(TopoDS.Face_s(f)) for f in mapping.FindFromKey(edge.wrapped)]
        out.append((edge, faces))
    return out


def _cylinder_is_convex(face) -> bool | None:
    """True for an outside rim, False for a bore, None if the face is not round."""
    adaptor = BRepAdaptor_Surface(face.wrapped)
    if adaptor.GetType() != GeomAbs_SurfaceType.GeomAbs_Cylinder:
        return None
    axis = adaptor.Cylinder().Axis()
    origin = bd.Vector(axis.Location().X(), axis.Location().Y(), axis.Location().Z())
    direction = bd.Vector(
        axis.Direction().X(), axis.Direction().Y(), axis.Direction().Z()
    )
    offset = face.center() - origin
    radial = offset - direction * offset.dot(direction)
    if radial.length < 1e-9:
        return None
    return face.normal_at(face.center()).dot(radial.normalized()) > 0


def _is_outer(face) -> bool:
    """A face an outer edge is allowed to touch: flat, or the outside of a round."""
    kind = BRepAdaptor_Surface(face.wrapped).GetType()
    if kind == GeomAbs_SurfaceType.GeomAbs_Plane:
        return True
    if kind == GeomAbs_SurfaceType.GeomAbs_Cylinder:
        return _cylinder_is_convex(face) is True
    # Cones, spheres, tori and splines. The only one on this robot is the wheel's
    # crowned tread, which is not printed, so being conservative costs nothing.
    return False


def _surface_key(face) -> tuple:
    """A descriptor of the SURFACE a face lies on, not of the face's extent.

    This is the part that survives chamfering. Cutting a chamfer somewhere on a
    plane makes that plane's face smaller but does not move the plane, so a key
    built from the plane's own normal and offset still identifies it afterwards.
    """
    adaptor = BRepAdaptor_Surface(face.wrapped)
    kind = adaptor.GetType()
    if kind == GeomAbs_SurfaceType.GeomAbs_Plane:
        plane = adaptor.Plane()
        n = plane.Axis().Direction()
        p = plane.Location()
        nx, ny, nz = n.X(), n.Y(), n.Z()
        d = nx * p.X() + ny * p.Y() + nz * p.Z()
        # A plane and its opposite normal are the same plane; pick one.
        if (nx, ny, nz) < (0.0, 0.0, 0.0):
            nx, ny, nz, d = -nx, -ny, -nz, -d
        return (
            "plane",
            round(nx, _ROUND),
            round(ny, _ROUND),
            round(nz, _ROUND),
            round(d, _ROUND),
        )
    if kind == GeomAbs_SurfaceType.GeomAbs_Cylinder:
        cyl = adaptor.Cylinder()
        axis = cyl.Axis()
        p, dvec = axis.Location(), axis.Direction()
        return (
            "cyl",
            round(cyl.Radius(), _ROUND),
            round(p.X(), _ROUND),
            round(p.Y(), _ROUND),
            round(p.Z(), _ROUND),
            round(abs(dvec.X()), _ROUND),
            round(abs(dvec.Y()), _ROUND),
            round(abs(dvec.Z()), _ROUND),
        )
    return ("other", id(kind))


def _edge_keys(solid) -> dict:
    """Map each edge to a key made of the faces it lies between.

    Where two faces meet along more than one edge the key would collide, so the
    duplicates are numbered by their position along the shared boundary -- an
    ordering that is stable because it does not depend on any length.

    ALWAYS KEYED OVER THE WHOLE EDGE SET. That numbering is positional within a
    key group, so keying a filtered subset numbers its duplicates differently
    from the full map the bisection resolves against, and every key then misses.
    Callers filter afterwards, against this map.
    """
    by_key: dict = {}
    for edge, faces in _edge_faces(solid):
        key = tuple(sorted(_surface_key(f) for f in faces))
        by_key.setdefault(key, []).append(edge)
    out = {}
    for key, group in by_key.items():
        if len(group) == 1:
            out[(key, 0)] = group[0]
        else:
            ordered = sorted(
                group,
                key=lambda e: (
                    round(e.center().X, _ROUND),
                    round(e.center().Y, _ROUND),
                    round(e.center().Z, _ROUND),
                ),
            )
            for i, edge in enumerate(ordered):
                out[(key, i)] = edge
    return out


def outer_edges(part) -> list:
    """Every edge of `part` whose faces are all outer faces."""
    return [
        edge
        for edge, faces in _edge_faces(part)
        if faces and all(_is_outer(f) for f in faces)
    ]


def _apply(solid, keys: list, size: float) -> tuple:
    """Chamfer as many of `keys` as OCCT will accept. Returns (solid, done, skipped)."""
    if not keys:
        return solid, 0, 0
    available = _edge_keys(solid)
    edges = [available[k] for k in keys if k in available]
    if edges:
        try:
            return bd.chamfer(edges, length=size), len(edges), len(keys) - len(edges)
        except Exception:
            pass
    if len(keys) == 1:
        return solid, 0, 1
    middle = len(keys) // 2
    solid, done_a, skipped_a = _apply(solid, keys[:middle], size)
    solid, done_b, skipped_b = _apply(solid, keys[middle:], size)
    return solid, done_a + done_b, skipped_a + skipped_b


def chamfer_body(body, size: float = CHAMFER) -> tuple:
    """One body with its outer edges broken. Returns (solid, done, skipped)."""
    wanted = outer_edges(body)
    if not wanted:
        return body, 0, 0
    try:
        return bd.chamfer(wanted, length=size), len(wanted), 0
    except Exception:
        pass
    numbered = _edge_keys(body)
    keys = [
        key
        for key, edge in numbered.items()
        if any(edge.wrapped.IsSame(w.wrapped) for w in wanted)
    ]
    return _apply(body, keys, size)


def united(bodies):
    """The single solid a piece would be if its bodies were merged.

    Safe on the FAITHFUL bodies -- gate B unions every piece this way. NOT safe on
    the output of chamfered() below, where it segfaults; see the module docstring.
    """
    if not isinstance(bodies, (list, tuple)):
        return bodies
    merged = bodies[0]
    for body in bodies[1:]:
        merged = merged + body
    return merged


def chamfered(bodies, size: float = CHAMFER) -> tuple:
    """The finished piece: every body's outer edges broken.

    Returns (list_of_bodies, chamfered_edge_count, skipped_edge_count). A LIST,
    the same shape the piece came in as, because these must not be unioned.
    """
    if not isinstance(bodies, (list, tuple)):
        bodies = [bodies]
    done = skipped = 0
    finished = []
    for body in bodies:
        solid, d, s = chamfer_body(body, size)
        finished.append(solid)
        done += d
        skipped += s
    return finished, done, skipped
