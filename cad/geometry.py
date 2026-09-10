"""Shape helpers that keep build123d's results well formed.

One function so far, and it exists because of a real defect rather than for
convenience.

THE DOUBLE-MIRROR VOLUME BUG. `build123d.mirror()` returns its result wrapped in
a new Compound every time it is called. Mirror a shape once and you have a
Compound holding a Solid; mirror that result again -- which is exactly what this
robot does, because a limb builds its rear gusset off its front one and then the
whole limb is mirrored to make the opposite hand -- and you have a Compound
holding a Compound holding a Solid.

`Compound.volume` is implemented as

    sum(i.volume for i in [*self.get_type(Solid), *self.get_type(Shell)])

and `get_type` looks only at the compound's DIRECT children. Two levels down it
finds nothing, so it sums nothing, and the volume comes back as **0.0**.

Nothing else complains. The shape is geometrically perfect: `BRepCheck_Analyzer`
calls it valid, its faces are correctly oriented, the raw OCCT
`BRepGProp.VolumeProperties` returns the right number, `.solids()` finds the
solid because it uses a full explorer, its bounding box is right, and every
boolean involving it behaves. Only the convenience property is blind, and it is
the property everything reads.

That is a nasty failure mode for this project in particular, because the mass
budget is measured off `.volume` and a part that silently weighs nothing makes
the robot look lighter than it is -- against a ceiling. It was caught by gate C,
which adds the bodies up; gate B never saw it, because a union re-nests what it
swallows and the volume comes back.

So every mirror in cad/ goes through `mirrored()`, which flattens the nesting
back to one level and refuses to hand back a shape that measures nothing.

Reported against build123d 0.11.1 / cadquery-ocp-novtk. If a later version
returns a flat result the flattening here becomes a no-op and stays harmless.
"""

from __future__ import annotations

from build123d import Compound, Part, Plane, Shape, mirror


def flattened(shape: Shape) -> Part:
    """The same solids, in a compound exactly one level deep.

    Rebuilt from `.solids()`, which explores the whole tree rather than the top
    of it, so nesting introduced by repeated transforms is discarded.
    """
    return Part(Compound(shape.solids()).wrapped)


def mirrored(shape: Shape, plane: Plane) -> Part:
    """Mirror a shape and hand back something that can still be measured.

    Use this rather than build123d's `mirror` anywhere in cad/. See the module
    docstring for why -- the short version is that mirroring twice makes
    `.volume` return zero while everything else about the shape stays correct.
    """
    result = flattened(mirror(shape, plane))
    if result.volume <= 0.0:
        raise ValueError(
            "mirrored() produced a shape measuring zero volume; the flattening "
            "that works around build123d's nested-compound bug has stopped "
            "working, and nothing downstream will notice on its own"
        )
    return result
