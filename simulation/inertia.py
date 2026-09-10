"""Mass, centre of mass and inertia tensor for everything the robot is made of.

This is the part the CAD cannot give you. Zoo will measure a solid's volume,
its mass and its centre of mass, but it has no call that returns an inertia
tensor, and a physics engine needs one per link. So the printed parts are
integrated from their exported meshes here, and the bought parts -- which have
no mesh, only a catalogue line and a mass -- are given the tensor of the
primitive they most nearly are.

UNITS, ONCE. Everything in this module is millimetres and grams going in,
because that is what the CAD and the mass budget speak, and kilograms and
metres coming out, because that is what a URDF wants. The conversion happens
in `to_si` and nowhere else.

A mesh is integrated at the material density in tools/mass_budget.toml, which
is how tools/mass.py weighs the same parts on the engine. That gives a free and
rather valuable cross-check: if the mass this module computes off a mesh
disagrees with what the engine reports for the same file, one of the two is
wrong, and check_model.py says so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh

# g/mm^3 per kg/m^3. 1060 kg/m^3 is 1.06e-3 g/mm^3.
G_PER_MM3_FROM_KG_PER_M3 = 1e-6

# g mm^2 -> kg m^2
KG_M2_FROM_G_MM2 = 1e-9

# The CAD frame is +X right, +Y forward, +Z up (tools/views.py). A URDF is
# expected in the ROS convention, +X forward, +Y left, +Z up. One rotation
# takes one to the other, and this is it: -90 degrees about Z.
CAD_TO_ROS = np.array(
    [
        [0.0, 1.0, 0.0],
        [-1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
)


def ros_point(cad: tuple[float, float, float]) -> np.ndarray:
    """A point in the CAD frame, expressed in the ROS frame."""
    return CAD_TO_ROS @ np.asarray(cad, dtype=float)


def ros_tensor(cad: np.ndarray) -> np.ndarray:
    """An inertia tensor in the CAD frame, expressed in the ROS frame."""
    return CAD_TO_ROS @ cad @ CAD_TO_ROS.T


# --------------------------------------------------------------------------
# Primitives
#
# Each returns an inertia tensor about the solid's own centre, in g mm^2, for a
# mass in grams and dimensions in millimetres. The X axis is the one every
# rotating part on this robot turns about, so the cylinders are along X.


def cylinder_x(grams: float, diameter: float, length: float) -> np.ndarray:
    r = diameter / 2.0
    axial = grams * r * r / 2.0
    transverse = grams * (3.0 * r * r + length * length) / 12.0
    return np.diag([axial, transverse, transverse])


def tube_x(grams: float, outer: float, inner: float, length: float) -> np.ndarray:
    ro, ri = outer / 2.0, inner / 2.0
    axial = grams * (ro * ro + ri * ri) / 2.0
    transverse = grams * (3.0 * (ro * ro + ri * ri) + length * length) / 12.0
    return np.diag([axial, transverse, transverse])


def box(grams: float, x: float, y: float, z: float) -> np.ndarray:
    return np.diag(
        [
            grams * (y * y + z * z) / 12.0,
            grams * (x * x + z * z) / 12.0,
            grams * (x * x + y * y) / 12.0,
        ]
    )


def parallel_axis(grams: float, offset: np.ndarray) -> np.ndarray:
    """The tensor a point mass of `grams` at `offset` adds about the origin."""
    d = np.asarray(offset, dtype=float)
    return grams * (float(d @ d) * np.eye(3) - np.outer(d, d))


# --------------------------------------------------------------------------
# Meshes


@dataclass(frozen=True)
class MeshFacts:
    """What one printed piece weighs and how its mass is distributed."""

    grams: float  # of the resolved solid -- what the part really weighs
    centre_mm: np.ndarray
    tensor_g_mm2: np.ndarray
    triangles: int
    solid: object  # the resolved trimesh, for writing out
    summed_grams: float  # before the overlaps were resolved; see below
    shells: int


class MeshLibrary:
    """The exported STLs, resolved and integrated once each, then reused.

    Four of the robot's six printed pieces are used twice, so caching here is
    not an optimisation so much as a guarantee that the left thigh and the
    right shin -- which are the same print -- get identical numbers.

    RESOLVING IS NOT OPTIONAL. These parts are exported as several separate
    closed shells, not as one solid, and the KCL leaves them that way
    deliberately: docs/KCL_GOTCHAS.md records that unioning a drilled body back
    onto another fills its holes in, so this project would rather interpenetrate
    than boolean. Two things follow. The overlap where two shells meet is inside
    both of them, so simply adding the shells up counts it twice -- a bias
    tools/mass.py names and accepts, because it errs upward against a ceiling.
    And the pelvis goes further: its clevis pockets are exported as INWARD
    facing shells with negative volume, which are cavities to be subtracted
    rather than bodies to be added.

    A mass budget can live with counting an overlap twice. A dynamics model
    should not, so this unions the positive shells, subtracts the negative
    ones, and integrates the single watertight solid that comes out. It keeps
    the summed figure alongside so the two tools can still be reconciled.
    """

    def __init__(self, directory: Path, density_kg_m3: float) -> None:
        self.directory = directory
        self.density = density_kg_m3 * G_PER_MM3_FROM_KG_PER_M3
        self._cache: dict[str, MeshFacts] = {}

    def _resolve(self, mesh, name: str):
        """One watertight solid from however many shells the export contains."""
        shells = mesh.split(only_watertight=False)
        for shell in shells:
            if not shell.is_watertight:
                raise ValueError(
                    f"{name} contains a shell that is not closed, so its volume "
                    "and inertia are undefined. Re-export it."
                )

        bodies = [shell for shell in shells if shell.volume > 0]
        cavities = [shell for shell in shells if shell.volume < 0]
        if not bodies:
            raise ValueError(f"{name} has no solid shell at all")

        solid = (
            bodies[0]
            if len(bodies) == 1
            else trimesh.boolean.union(bodies, engine="manifold")
        )
        if cavities:
            for cavity in cavities:
                cavity.invert()
            hollow = (
                cavities[0]
                if len(cavities) == 1
                else trimesh.boolean.union(cavities, engine="manifold")
            )
            solid = trimesh.boolean.difference([solid, hollow], engine="manifold")

        if not solid.is_watertight:
            raise ValueError(f"{name} did not resolve to a watertight solid")
        return solid, len(shells)

    def properties(self, piece: str) -> MeshFacts:
        if piece in self._cache:
            return self._cache[piece]

        path = self.directory / f"{piece}.stl"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing. Regenerate the meshes with\n"
                f"    uv run tools/export.py --format stl --out simulation/meshes\n"
                "which runs on the engine and spends API credits."
            )

        raw = trimesh.load_mesh(path)
        summed = float(raw.volume) * self.density
        solid, shells = self._resolve(raw, path.name)
        solid.density = self.density

        facts = MeshFacts(
            grams=float(solid.mass),
            centre_mm=np.asarray(solid.center_mass, dtype=float),
            tensor_g_mm2=np.asarray(solid.moment_inertia, dtype=float),
            triangles=len(solid.faces),
            solid=solid,
            summed_grams=summed,
            shells=shells,
        )
        self._cache[piece] = facts
        return facts


# --------------------------------------------------------------------------
# Rolling a link up


def solid_properties(
    solid, meshes: MeshLibrary
) -> tuple[float, np.ndarray, np.ndarray]:
    """One solid's (grams, centre in the link's CAD frame, tensor about it)."""
    at = np.asarray(solid.at, dtype=float)

    if solid.shape == "mesh":
        facts = meshes.properties(solid.piece)
        return facts.grams, at + facts.centre_mm, facts.tensor_g_mm2
    if solid.shape == "cylinder_x":
        return solid.grams, at, cylinder_x(solid.grams, *solid.dims)
    if solid.shape == "tube_x":
        return solid.grams, at, tube_x(solid.grams, *solid.dims)
    if solid.shape == "box":
        return solid.grams, at, box(solid.grams, *solid.dims)
    if solid.shape == "point":
        return solid.grams, at, np.zeros((3, 3))
    raise ValueError(f"unknown shape {solid.shape!r} on {solid.label!r}")


def link_properties(
    solids, meshes: MeshLibrary
) -> tuple[float, np.ndarray, np.ndarray]:
    """A link's total mass, its centre of mass, and its tensor about that centre.

    In the link's own CAD frame, in grams and millimetres.
    """
    parts = [solid_properties(solid, meshes) for solid in solids]
    total = sum(grams for grams, _, _ in parts)
    if total <= 0.0:
        raise ValueError("a link with no mass cannot have a centre of mass")

    centre = sum(grams * position for grams, position, _ in parts) / total

    tensor = np.zeros((3, 3))
    for grams, position, own in parts:
        tensor += own + parallel_axis(grams, position - centre)
    return total, centre, tensor


def to_si(
    grams: float, centre_mm: np.ndarray, tensor_g_mm2: np.ndarray
) -> tuple[float, np.ndarray, np.ndarray]:
    """Millimetres and grams in the CAD frame, to metres and kilograms in ROS."""
    return (
        grams / 1000.0,
        ros_point(centre_mm) / 1000.0,
        ros_tensor(tensor_g_mm2) * KG_M2_FROM_G_MM2,
    )


def is_plausible(tensor: np.ndarray) -> tuple[bool, str]:
    """Does this tensor describe a real rigid body?

    Two ways it can fail to. It must be positive definite -- a body with a zero
    or negative principal moment does not exist -- and its principal moments
    must satisfy the triangle inequality, which is what stops a physics engine
    integrating a body that behaves like nothing physical.
    """
    moments = np.linalg.eigvalsh(tensor)
    if np.any(moments <= 0.0):
        return False, f"a principal moment is not positive: {moments}"
    a, b, c = sorted(moments)
    if a + b < c * (1.0 - 1e-9):
        return False, f"principal moments break the triangle inequality: {moments}"
    return True, ""


def skew_of(tensor: np.ndarray) -> float:
    """How far off-diagonal the tensor is, as a fraction of its largest term."""
    off = tensor - np.diag(np.diag(tensor))
    scale = float(np.max(np.abs(tensor)))
    return float(np.max(np.abs(off))) / scale if scale > 0 else 0.0


def rpy_from_axis_x() -> tuple[float, float, float]:
    """Roll-pitch-yaw that lays a URDF cylinder's Z axis along the CAD X axis.

    A URDF cylinder is built about Z. Every rotating part here turns about the
    CAD's X, which the CAD-to-ROS rotation carries onto the ROS Y, so the
    primitive is rolled a quarter turn about X.
    """
    return (math.pi / 2.0, 0.0, 0.0)
