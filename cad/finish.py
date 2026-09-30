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

Per body, every one of them succeeds. So that is what this does, and the bodies
are chamfered as the interpenetrating bodies they are drawn as.

A body whose chamfers were applied one group at a time comes back reporting
itself VALID, and then segfaults OCCT the moment it takes part in any boolean --
even a union with a body it does not touch. clean() and fix() do not help. So a
union straight after this pass does not fail, it takes the process down, and no
try/except can catch that. Chamfering the union first instead is no escape: it
segfaults on the pelvis too, and on the thighs it leaves a quarter of the arrises
sharp.

WHICH IS WHY THE PIECES USED TO SHIP AS SEVERAL BODIES, AND WHY THEY NO LONGER DO.
The argument was that a slicer merges them into the single part they really are.
The first printed pelvis came back without all but one of its floor posts, both
battery rails, the battery-board guides and the IMU seat: sixteen of its
twenty-two bodies only rested face-to-face on the shell, sharing no material with
it, and what a slicer does with that is not something this project gets to
assume. So a piece now leaves as ONE solid, made by one_solid() below: the bodies
are chamfered here as before, written to a STEP file and read back -- which is
what rebuilds them into solids OCCT can take a boolean of; the round trip is the
whole trick, and every piece here unions cleanly after it and none of the
crowded ones does without it -- and then united. What comes out is checked by
problems() rather than trusted, and tools/export.py does that union in a child
process so that if the segfault ever returns it refuses the piece rather than
dying.

What is left un-chamfered by working per body is the edges the union WOULD have
created where two bodies interpenetrate. Those are re-entrant corners, which is
exactly where a chamfer does not belong, so nothing is lost. And a chamfer cut on
an edge buried inside a neighbouring body is filled back in by the union that
makes the piece one solid, so nothing is gained there either.

WHAT THAT ARGUMENT MISSED, AND IT MATTERED. It asked what the union would ADD and
never what the union would TAKE AWAY. A body that is half buried in its
neighbours has edges the finished part does not have at all -- the limb's waist
plate has a top arris only because the gussets and the rotor disc above it are
separate bodies, and on the merged part that line is a join, not an edge.
Chamfering it cuts a 0.5 mm groove along the join, and at the gusset root it cuts
into the stress relief the gusset is there to provide. Half the edges this module
used to accept on a limb were of that kind and two of them were plainly visible.
So the merged solid is now consulted for which arrises are real; see the Merge
class below.

AN EDGE THE CHAMFER WOULD SWALLOW IS NOT OFFERED TO OCCT AT ALL.

A chamfer takes its own length off the far end of every edge that runs into the
one being cut, so an edge shorter than twice the chamfer has nothing left of it
once its two neighbours have been broken. Cutting it is not a finish, it is
three chamfers trying to occupy the same corner.

THAT CASE DOES NOT FAIL, IT CRASHES. Everywhere else in this module an
impossible chamfer raises and the bisection below absorbs it. These do not:
OCCT dies with an access violation and takes the interpreter with it, which no
try/except can catch and which therefore cannot be recovered from or reported --
the tool simply disappears. It was found on the stator clevis, on a 0.935 mm
sliver where the rear cheek's connector relief meets its neck, cut onto a solid
that already carried other chamfers. The same piece with three fewer edges on it
finished perfectly well, so nothing about that sliver announces itself: which
edges are attempted together is decided by how the bisection happens to split,
and any geometry change reshuffles it. That makes this a landmine rather than a
defect of one part, and the guard is what removes it.

What it costs is reported rather than hidden. A refused edge is counted as
SKIPPED, exactly like one OCCT declines, so tools/finish_report.py's "left
sharp" column still means every arris that should have been broken and was not.
At 0.5 mm the floor is 1 mm, which is under two layers at this nozzle and below
anything a finger or an eye finds on a printed part.

WHEN OCCT REFUSES A SET ANYWAY.

The set is bisected and the halves are tried in turn, down to single edges, so one
awkward edge costs one chamfer rather than the whole part. Edges are re-found on
each new solid by THE PAIR OF FACES THEY LIE BETWEEN rather than by position,
because a chamfer shortens its neighbours and moves their midpoints, while the
faces either side of them do not move at all.

A part that comes back with skipped edges is still correct. It has a few arrises
left sharp, and tools/finish_report.py says how many rather than passing over it.

AND WHEN OCCT ACCEPTS A SET IT SHOULD HAVE REFUSED.

This is the same lesson as "a boolean that succeeds is not a boolean that worked",
one pass further down. A chamfer can return without raising and hand back a solid
whose faces run through each other: on the pelvis, one aperture's side wall came
back SIX MILLIMETRES TALLER than the aperture it belongs to, overlapping the flat
above it, with two edges lying on top of one another along the same line. Nothing
complained. BRepCheck_Analyzer, which is what `Shape.is_valid` asks, called it
valid -- it checks each face against its own geometry and has no opinion about two
faces occupying the same space. The part built, the gates passed, and the only
thing that ever noticed was the exporter: a tessellator cannot triangulate an
overlap, so it left a degenerate sliver and the STL came out with a hole in it,
which simulation/inertia.py refused. That is three passes and a day's work
downstream of the thing that was actually wrong.

So every accepted chamfer is now asked the stronger question, BRepAlgoAPI_Check
with the self-intersection tests on, and a set that fails it is rejected exactly
as if OCCT had raised: bisect, try the halves, and leave the edge sharp if it
comes to that. It costs about a second on the pelvis's main body and nothing
measurable on anything else, because the check is only as expensive as the solid
is complicated.

WHAT THIS DOES NOT DO is make the chamfer deterministic. Which edges survive still
depends on how the bisection splits, and that still reshuffles when the geometry
changes. What it guarantees is that the part that comes out is sound -- the
alternative was a part that was quietly corrupt.
"""

from __future__ import annotations

import build123d as bd
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Check
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.GeomAbs import GeomAbs_SurfaceType
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_ShapeEnum, TopAbs_State
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


def _face_pair_key(faces) -> tuple:
    """The key an edge is identified by: the surfaces it lies between."""
    return tuple(sorted(_surface_key(f) for f in faces))


def outer_edges(part, merge=None) -> list:
    """Every edge of `part` whose faces are all outer faces.

    With a Merge, an edge must also survive what the body's neighbours in the
    same piece do to it -- see Merge for why a fifth of a limb's did not.
    """
    return [
        edge
        for edge, faces in _edge_faces(part)
        if faces
        and all(_is_outer(f) for f in faces)
        and (merge is None or merge.keeps(edge, faces))
    ]


# How short is too short, as a multiple of the chamfer. Two, because a short edge
# has two ends and each of them loses the chamfer's own length to the cut that
# runs into it. See the module docstring: these edges crash OCCT rather than
# being refused by it.
SLIVER = 2.0


def _long_enough(edges: list, size: float) -> tuple[list, list]:
    """Split `edges` into the ones a chamfer leaves something of, and the slivers."""
    floor = SLIVER * size
    keep = [edge for edge in edges if edge.length >= floor]
    slivers = [edge for edge in edges if edge.length < floor]
    return keep, slivers


def _sound(solid) -> bool:
    """Is this solid free of faces running through one another?

    Asked of every chamfer this module accepts, because a chamfer that returns
    without raising can still hand back a solid whose faces overlap -- see the
    module docstring for the one that did, and for why `Shape.is_valid` says
    nothing about it. This is the check that has an opinion.
    """
    try:
        return BRepAlgoAPI_Check(solid.wrapped, True, True).IsValid()
    except Exception:
        return False


def _apply(solid, keys: list, size: float) -> tuple:
    """Chamfer as many of `keys` as OCCT will accept. Returns (solid, done, skipped).

    "Accept" means both halves of the question: the call returned, and what it
    returned is sound. A set that fails the second is put back exactly as if it
    had failed the first.
    """
    if not keys:
        return solid, 0, 0
    available = _edge_keys(solid)
    edges = [available[k] for k in keys if k in available]
    if edges:
        try:
            cut = bd.chamfer(edges, length=size)
            if _sound(cut):
                return cut, len(edges), len(keys) - len(edges)
        except Exception:
            pass
    if len(keys) == 1:
        return solid, 0, 1
    middle = len(keys) // 2
    solid, done_a, skipped_a = _apply(solid, keys[:middle], size)
    solid, done_b, skipped_b = _apply(solid, keys[middle:], size)
    return solid, done_a + done_b, skipped_a + skipped_b


def chamfer_body(body, size: float = CHAMFER, merge=None) -> tuple:
    """One body with its outer edges broken. Returns (solid, done, skipped).

    The slivers are taken out before anything is attempted and counted as
    skipped, so they are reported as the sharp arrises they are.
    """
    wanted, slivers = _long_enough(outer_edges(body, merge), size)
    if not wanted:
        return body, 0, len(slivers)
    try:
        cut = bd.chamfer(wanted, length=size)
        if _sound(cut):
            return cut, len(wanted), len(slivers)
    except Exception:
        pass
    numbered = _edge_keys(body)
    keys = [
        key
        for key, edge in numbered.items()
        if any(edge.wrapped.IsSame(w.wrapped) for w in wanted)
    ]
    solid, done, skipped = _apply(body, keys, size)
    return solid, done, skipped + len(slivers)


def united(bodies):
    """The single solid a piece would be if its bodies were merged.

    Safe on the FAITHFUL bodies -- gate B unions every piece this way. NOT safe on
    the output of chamfered() below, where it segfaults, unless they have been
    through a STEP file first; see the module docstring and one_solid().
    """
    if not isinstance(bodies, (list, tuple)):
        return bodies
    merged = bodies[0]
    for body in bodies[1:]:
        merged = merged + body
    return merged


def surviving_keys(bodies) -> set | None:
    """The face-pair keys of every edge the MERGED piece actually has.

    Returns None for a single body, which has no neighbours to lose edges to.
    """
    if not isinstance(bodies, (list, tuple)) or len(bodies) < 2:
        return None
    merged = united(list(bodies))
    return {_face_pair_key(faces) for _, faces in _edge_faces(merged) if faces}


# How many points along an edge are asked whether the chamfer there would be
# filled by a neighbour, and how close to the ends the asking starts. The
# interesting edges are PART buried -- the limb's waist runs 40 mm along the
# underside of the rotor disc and two gussets and is covered by them for the
# middle 22 mm only -- so one sample in the middle would get the wrong answer on
# exactly the edges this test exists for. The ends matter as much: the gussets'
# inner chord is buried for all but its last third of a millimetre, where it
# reaches the disc's rim, and that third of a millimetre was one of the two
# slivers visible on the finished limb.
_SAMPLES = 25
_END_MARGIN = 0.01

# Where in the wedge the chamfer would cut away the filling is checked, as
# fractions of the chamfer size along each of the two faces. Three points, biased
# towards the wedge's outer corners, because the middle of a wedge is the last
# part of it to emerge from a neighbour.
_WEDGE = ((0.70, 0.15), (0.15, 0.70), (0.35, 0.35))

# An edge shorter than this many chamfers is never withheld, however phantom it
# is. Two reasons, and the second is the harder one. A groove no longer than the
# chamfer that cuts it is not a groove. And withholding a stub while chamfering
# the long edges either side of it leaves those chamfers to close on the stub,
# which is where OCCT stops raising exceptions and starts taking the process
# down: the pelvis shell's second hip cheek segfaults on exactly that, and a
# segfault cannot be caught and retried. Withholding the stub alone, or the long
# edge alone, is fine -- it is the combination that kills it.
_STUB = 2.0


class Merge:
    """What a body's neighbours in the same piece do to its edges.

    THE OTHER HALF OF "OUTER EDGES ONLY", and the half that was missing. Working
    per body means each body is chamfered as though it were alone, and a body
    that is half buried in its neighbours has edges that the finished part does
    not have: the limb's waist plate has a top arris only because the two gussets
    and the rotor disc sitting on it are separate bodies, and the gussets have
    lower arrises only because the waist they are seated on is.

    Two of those phantom edges were plainly visible -- a bevel with a sliver at
    each end, at both gusset roots, on both faces of the limb -- which is a
    0.5 mm groove cut into the join, and at the gusset root a groove cut into the
    stress relief the gusset exists to provide.

    WHICH PHANTOMS ARE SKIPPED, AND WHY NOT ALL OF THEM. An edge the union does
    not have is not an arris. But the module docstring is right that a chamfer
    BURIED inside a neighbour costs nothing -- the merge fills it back in exactly
    as it fills the rest of the overlap -- so cutting those makes no difference
    to the part, and asking OCCT to cut fewer chamfers is not free: the pelvis
    shell's second hip cheek takes OCCT DOWN, not to an exception but to a
    segfault, when three of its buried phantoms are withheld and the chamfers
    either side of them have to close on a 0.6 mm stub instead.

    So the test is what the chamfer would LEAVE, not what the edge is: an edge is
    skipped when the union has no such edge AND the material the chamfer would
    remove is not replaced by a neighbour somewhere along it. That is exactly the
    set that leaves a groove, it is 21 edges on a limb, and it leaves every
    buried phantom to be cut as before.
    """

    def __init__(self, bodies, index: int, size: float, surviving: set | None):
        self.size = size
        self.surviving = surviving
        self.siblings = [b for i, b in enumerate(bodies) if i != index]
        self._classifiers = [
            BRepClass3d_SolidClassifier(b.wrapped) for b in self.siblings
        ]

    def _inside_a_sibling(self, point) -> bool:
        for classifier in self._classifiers:
            classifier.Perform(gp_Pnt(point.X, point.Y, point.Z), 1e-7)
            if classifier.State() == TopAbs_State.TopAbs_IN:
                return True
        return False

    def keeps(self, edge, faces) -> bool:
        """Is this edge one the finished part actually has an arris at?

        Anything the union has, yes. Anything else only if the wedge the chamfer
        would cut away is filled by a neighbour along the whole edge, so that
        cutting it changes nothing -- or if the edge is too short to withhold.
        """
        if self.surviving is None or _face_pair_key(faces) in self.surviving:
            return True
        if len(faces) != 2 or not self._classifiers:
            return True
        if edge.length < self.size * _STUB:
            return True
        span = 1.0 - 2 * _END_MARGIN
        for i in range(_SAMPLES):
            at = _END_MARGIN + span * i / (_SAMPLES - 1)
            try:
                point = edge.position_at(at)
                # Away from the edge along each face is the OTHER face's inward
                # normal, which is what the chamfer eats into.
                along = [-faces[1].normal_at(point), -faces[0].normal_at(point)]
            except Exception:
                return True
            for a, b in _WEDGE:
                probe = point + along[0] * (a * self.size) + along[1] * (b * self.size)
                if not self._inside_a_sibling(probe):
                    return False
        return True


def chamfered(bodies, size: float = CHAMFER) -> tuple:
    """ONE finished piece: every body's outer edges broken.

    Returns (list_of_bodies, chamfered_edge_count, skipped_edge_count). A LIST,
    the same shape the piece came in as, because these must not be unioned.

    THE ARGUMENT IS ONE PIECE, and that is not a formality. Which arrises are
    real is decided by merging the bodies given (see Merge), so handing this two
    pieces at once asks it to merge two parts into one and answer about that --
    which changes the answer for both. Use chamfered_pieces() for more than one.
    """
    if not isinstance(bodies, (list, tuple)):
        bodies = [bodies]
    bodies = list(bodies)

    # The union is taken ONCE for the piece, not once per body.
    surviving = surviving_keys(bodies)
    done = skipped = 0
    finished = []
    for i, body in enumerate(bodies):
        merge = Merge(bodies, i, size, surviving) if surviving is not None else None
        solid, d, s = chamfer_body(body, size, merge)
        finished.append(solid)
        done += d
        skipped += s
    return finished, done, skipped


def chamfered_pieces(pieces, size: float = CHAMFER) -> tuple:
    """Several pieces, each finished as itself, and handed back piece by piece.

    The pieces stay separate on the way in AND on the way out. Separate on the
    way in because nothing can work out where one piece ends from a flat list of
    bodies: two parts of an assembly are as interpenetrating as two bodies of one
    part, and guessing from that is how a thigh and a shin end up merged into a
    single "piece" at the knee and lose the arrises where they meet. Separate on
    the way out because the caller knows what each piece is -- tools/view.py puts
    each one under its own name in the viewer's tree -- and re-splitting a
    flattened list by counting bodies is a way to get that wrong.

    Returns (list_of_pieces, chamfered_edge_count, skipped_edge_count), where
    each piece is the list of bodies chamfered() gave back for it.
    """
    finished_pieces: list = []
    done = skipped = 0
    for piece in pieces:
        finished, d, s = chamfered(piece, size)
        finished_pieces.append(finished)
        done += d
        skipped += s
    return finished_pieces, done, skipped


def _through_step(bodies: list) -> list:
    """The same bodies, written to a STEP file and read back.

    This is what makes a body chamfered by the fallback above safe to take a
    boolean of. Whatever the writer and reader rebuild on the way -- tolerances,
    p-curves, the shared edges the bisection left fragile -- every piece on this
    robot unions cleanly after it, where the pelvis and the deck take OCCT down
    without it. Found by trying, not derived, which is why problems() checks the
    result and tools/export.py runs the union in a process it can lose.
    """
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "piece.step"
        shape = bodies[0] if len(bodies) == 1 else bd.Compound(children=bodies)
        bd.export_step(shape, str(path))
        return list(bd.import_step(str(path)).solids())


def one_solid(bodies, size: float = CHAMFER, finished: bool = True) -> tuple:
    """ONE printed piece as the single solid it is printed as.

    Returns (solid, chamfered_edge_count, skipped_edge_count). Finished, the
    bodies are chamfered by chamfered() above and taken through a STEP file
    before they are united; as drawn, they are united as they are, which is
    always safe. Either way the result can still be wrong -- two bodies that do
    not touch unite into two solids, and a pocket closed over unites into a
    sealed void -- so ask problems() about it before using it.
    """
    if not isinstance(bodies, (list, tuple)):
        bodies = [bodies]
    bodies = list(bodies)
    if not finished:
        return united(bodies), 0, 0
    done_bodies, done, skipped = chamfered(bodies, size)
    return united(_through_step(done_bodies)), done, skipped


def problems(shape) -> list[str]:
    """Why `shape` is not one printable solid, or nothing if it is.

    THE RULE EVERY PRINTED PIECE IS HELD TO, whatever process prints it: exactly
    one solid, bounded by exactly one closed shell, sound, and with positive
    volume. Each clause is a failure this project has had or nearly had:

    * MORE THAN ONE SOLID is a body that does not reach the rest of the piece. It
      prints as a loose part, or not at all.
    * MORE THAN ONE SHELL is a sealed cavity inside the part. A sintered or resin
      part keeps its powder or its resin in there for good; the wheel adapter
      carried a 16 mm3 one until September 2026, and the joint saddles about
      14 g of powder across the robot until drains were cut in them.
    * NOT SOUND is faces running through each other, which a tessellator turns
      into a hole in the mesh -- see _sound().
    * NO VOLUME is a solid turned inside out by a double mirror.

    Touching faces are NOT a problem here, and that is deliberate: a post drawn
    standing on a floor unites with it into one solid, and one solid is one print.
    The failure was never that the post only touched the floor; it was that the
    post was handed to the printer as a separate body and nobody could say what
    would be done with it.
    """
    solids = list(shape.solids()) if hasattr(shape, "solids") else [shape]
    found = []
    if len(solids) != 1:
        found.append(
            f"{len(solids)} separate solids where there must be one -- a body that "
            "does not reach the rest of the piece"
        )
    for i, solid in enumerate(solids):
        shells = len(solid.shells())
        where = f"solid {i}: " if len(solids) > 1 else ""
        if shells != 1:
            found.append(
                f"{where}{shells - 1} sealed cavit{'y' if shells == 2 else 'ies'} "
                "inside it, which trap powder or resin"
            )
        if solid.volume <= 0.0:
            found.append(f"{where}no volume -- turned inside out")
    if not _sound(shape):
        found.append("faces running through one another")
    return found
