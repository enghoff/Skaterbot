# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1", "pyvista>=0.44", "numpy>=1.26", "pillow>=10"]
# ///
"""Render the README's pictures of the robot from the CAD itself.

    uv run docs/images/render_robot.py [--cache DIR] [anatomy moves]

Nothing here is drawn by hand: every body comes out of cad/, in a pose worked out
from the two leg angles the way cad/poses.py does it, and every height written on
a picture is measured from the meshes in that picture. So a picture cannot show a
robot the CAD does not describe.

The printed parts are orange because that is what the colour says here, printed
as against bought. The real robot's are black.

The meshes are tessellated once and kept in --cache, because tessellating takes
about a minute a pose and framing a picture takes many attempts.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from math import acos, degrees
from pathlib import Path

import numpy as np
import pyvista as pv
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from vtkmodules.vtkRenderingCore import vtkCoordinate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

SUPERSAMPLE = 2
GROUND = "#ece8df"
INK = "#232019"
QUIET = "#5f584c"
LEADER = "#8c8371"

MATERIALS = {
    "printed": dict(
        color="#d9822b", ambient=0.30, diffuse=0.75, specular=0.12, specular_power=18
    ),
    "cover": dict(
        color="#d9822b", ambient=0.30, diffuse=0.75, specular=0.12, specular_power=18
    ),
    "motor": dict(
        color="#4d565e", ambient=0.30, diffuse=0.75, specular=0.35, specular_power=30
    ),
    "steel": dict(
        color="#c9d0d5", ambient=0.30, diffuse=0.70, specular=0.50, specular_power=40
    ),
    "tyre": dict(
        color="#d3d0c8", ambient=0.34, diffuse=0.70, specular=0.10, specular_power=12
    ),
    "board": dict(
        color="#1c6b42", ambient=0.30, diffuse=0.75, specular=0.20, specular_power=24
    ),
    "dark": dict(
        color="#20232a", ambient=0.32, diffuse=0.75, specular=0.15, specular_power=20
    ),
    "cell": dict(
        color="#4a4f57", ambient=0.30, diffuse=0.75, specular=0.20, specular_power=20
    ),
    "copper": dict(
        color="#a8452a", ambient=0.30, diffuse=0.75, specular=0.15, specular_power=20
    ),
    "can": dict(
        color="#8c939c", ambient=0.30, diffuse=0.75, specular=0.30, specular_power=30
    ),
    "terminal": dict(
        color="#2f5fb4", ambient=0.30, diffuse=0.75, specular=0.20, specular_power=24
    ),
}

# Hip-to-axle length and how far the wheels are off the floor, in millimetres.
# 203.5 and 165 are the two ends of the ride height the controller's D-pad sets
# (sbc/gamepad.py, HEIGHT_RANGE_M). The jump's 37 mm is the median clearance over
# 24 jumps on 8 November 2026, worked out from the logged joint angles.
POSES = {"ride": (203.5, 0.0), "crouch": (165.0, 0.0), "air": (205.0, 37.0)}

# Mounted through the pelvis wall, so they stay with it when the torso is opened.
ON_THE_WALL = {"on-off button", "charge inlet", "antenna bulkhead"}
LOOSE_ENDS = {"actuator harness bank", "actuator harness runs"}
LEGS = ("motor", "screws", "thigh", "shin", "wheel", "hardware")


def material_of(group: str, body) -> str | None:
    """What a body is made of, from its group's name and, for a wheel, its size."""
    if group == "reservations":
        return None
    if group == "cover":
        return "cover"
    if "motor" in group:
        return "motor"
    if "hardware" in group or "screws" in group:
        return "steel"
    if "wheel" in group:
        size = body.bounding_box().size
        across = max(size.Y, size.Z)
        if across > 70:
            return "tyre"
        if across < 14:
            return "steel"
        return "printed"
    if group in ("pelvis", "deck") or group.endswith(("thigh", "shin", "limb")):
        return "printed"
    if group.endswith("board"):
        return "board"
    if group == "battery packs":
        return "cell"
    if "lead" in group or group == "battery series link" or group.endswith("loom"):
        return "copper"
    if group == "capacitor bank":
        return "can"
    if group in (
        "bus terminal",
        "fuse holder",
        "on/off button",
        "charge inlet",
        "antenna bulkhead",
    ):
        return "terminal"
    return "dark"


def leg_pose(hip_to_axle: float, lift: float) -> dict[str, float]:
    """A symmetric stance, each axle under its hip, named the way the squat scene is."""
    from cad.poses import _leg, lowerLegLength, upperLegLength
    from cad.wheeled_parameters import (
        wheeledHipPitchAxisHeight,
        wheeledTorsoCenterHeight,
    )

    reach = upperLegLength + lowerLegLength
    half = degrees(acos(hip_to_axle / reach))
    drop = reach - hip_to_axle - lift
    hip_z = wheeledHipPitchAxisHeight - drop
    pose = {
        "squatKneeAngle": 2 * half,
        "squatHipAngle": half,
        "squatShinAngle": -half,
        "squatHipPitchZ": hip_z,
        "squatTorsoCenterZ": wheeledTorsoCenterHeight - drop,
    }
    pose.update(_leg(hip_z, half, -half))
    return pose


def scene_groups(name: str) -> dict[str, list]:
    if name == "neutral":
        from cad.main import robotAssemblyGroups

        return robotAssemblyGroups()
    from cad.scenes import _leg_groups, _torso_groups

    pose = leg_pose(*POSES[name])
    groups = _torso_groups(pose["squatTorsoCenterZ"])
    groups.update(_leg_groups(pose, "left"))
    groups.update(_leg_groups(pose, "right"))
    return groups


def to_mesh(body) -> pv.PolyData:
    verts, tris = body.tessellate(0.04, 0.15)
    points = np.array([(v.X, v.Y, v.Z) for v in verts], dtype=float)
    faces = np.column_stack(
        [np.full(len(tris), 3), np.array(tris, dtype=np.int64)]
    ).ravel()
    return pv.PolyData(points, faces)


def meshes(scene: str, cache: Path) -> dict[tuple[str, str], pv.PolyData]:
    """Every body of a scene, merged by (group, material), from the cache if it can be."""
    folder = cache / scene
    if folder.is_dir() and any(folder.iterdir()):
        found = {}
        for path in folder.glob("*.vtp"):
            group, material = path.stem.split("__")
            found[group.replace("_", " "), material] = pv.read(path)
        return found
    print(f"tessellating {scene} ...", flush=True)
    bags: dict[tuple[str, str], list[pv.PolyData]] = defaultdict(list)
    for group, bodies in scene_groups(scene).items():
        for body in bodies:
            material = material_of(group, body)
            if material is not None:
                bags[group, material].append(to_mesh(body))
    folder.mkdir(parents=True, exist_ok=True)
    merged = {}
    for (group, material), parts in bags.items():
        mesh = parts[0].merge(parts[1:]) if len(parts) > 1 else parts[0]
        mesh = mesh.compute_normals(
            feature_angle=32.0, split_vertices=True, auto_orient_normals=False
        )
        safe = group.replace(" ", "_").replace("/", "-")
        merged[safe.replace("_", " "), material] = mesh
        mesh.save(folder / f"{safe}__{material}.vtp")
    return merged


def stage(size: tuple[int, int]) -> pv.Plotter:
    plotter = pv.Plotter(
        off_screen=True,
        window_size=(size[0] * SUPERSAMPLE, size[1] * SUPERSAMPLE),
        lighting="none",
    )
    plotter.set_background(GROUND)
    return plotter


def lights(plotter: pv.Plotter, focal, key) -> None:
    fx, fy, fz = focal
    kx, ky, kz = key
    for position, intensity in (
        ((fx + kx, fy + ky, fz + kz), 0.85),
        ((fx - kx * 1.1, fy + ky * 0.6, fz + kz * 0.3), 0.30),
        ((fx - kx * 0.2, fy - ky * 1.2, fz + kz * 0.9), 0.35),
    ):
        plotter.add_light(
            pv.Light(
                position=position,
                focal_point=focal,
                intensity=intensity,
                light_type="scene light",
            )
        )


def nearest_surface(mesh: pv.PolyData, point) -> tuple[float, float, float]:
    """The vertex of a part closest to a point, so a label's dot lands on the part."""
    points = np.asarray(mesh.points)
    return tuple(points[np.argmin(np.linalg.norm(points - np.asarray(point), axis=1))])


def shoot(plotter, anchors, shadows=(), ssao: float | None = 22.0):
    """The picture at full size, on its soft floor shadows, and where each anchor landed.

    `shadows` are (x, y, height off the floor) under each wheel. There is no floor in
    the 3D scene: drawn at a grazing angle it banded, and all it was for is these.
    """
    if ssao:
        plotter.enable_ssao(radius=ssao, bias=0.6, kernel_size=128, blur=True)
    shot = Image.fromarray(
        plotter.screenshot(transparent_background=True, return_img=True)
    ).convert("RGBA")
    height = plotter.window_size[1]
    coordinate = vtkCoordinate()
    coordinate.SetCoordinateSystemToWorld()

    def project(point):
        coordinate.SetValue(*point)
        x, y = coordinate.GetComputedDoubleDisplayValue(plotter.renderer)
        return (x, height - y)

    pixels = {name: project(point) for name, point in anchors.items()}
    per_mm = abs(project((100.0, 0.0, 0.0))[0] - project((0.0, 0.0, 0.0))[0]) / 100.0
    mask = Image.new("L", shot.size, 0)
    draw = ImageDraw.Draw(mask)
    for x, y, lift in shadows:
        cx, cy = project((x, y, 0.0))
        rx, ry = 66.0 * per_mm, 24.0 * per_mm
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=int(150 - 1.6 * lift))
    mask = mask.filter(ImageFilter.GaussianBlur(11.0 * per_mm))
    canvas = Image.new("RGBA", shot.size, GROUND)
    canvas.paste(Image.new("RGBA", shot.size, "#8a8272"), mask=mask)
    canvas.alpha_composite(shot)
    plotter.close()
    return canvas.convert("RGB"), pixels


def finish(image: Image.Image, path: Path) -> None:
    shot = image.resize(
        (image.width // SUPERSAMPLE, image.height // SUPERSAMPLE), Image.LANCZOS
    )
    shot.save(path, optimize=True)
    print(
        f"wrote {path.relative_to(ROOT)}  {path.stat().st_size // 1024} kB", flush=True
    )


def font(size: int, bold: bool = False):
    names = (
        ("segoeuib.ttf", "DejaVuSans-Bold.ttf")
        if bold
        else ("segoeui.ttf", "DejaVuSans.ttf")
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size * SUPERSAMPLE)
        except OSError:
            continue
    raise SystemExit("no font found")


def centre(mesh: pv.PolyData, offset: float = 0.0) -> tuple[float, float, float]:
    b = mesh.bounds
    return ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2 + offset)


@dataclass
class Callout:
    anchor: str
    title: str
    detail: str
    side: str


def draw_callouts(
    image: Image.Image, pixels: dict, items: list[Callout], margin: int = 40
) -> None:
    """Labels down each side, each with an elbowed leader to its part."""
    draw = ImageDraw.Draw(image)
    scale = SUPERSAMPLE
    gap = 74 * scale
    for side in ("left", "right"):
        group = sorted(
            (i for i in items if i.side == side), key=lambda i: pixels[i.anchor][1]
        )
        ys: list[float] = []
        for item in group:
            wanted = pixels[item.anchor][1]
            ys.append(max(wanted, ys[-1] + gap) if ys else max(wanted, 40 * scale))
        overflow = ys[-1] - (image.height - 56 * scale)
        if overflow > 0:
            ys = [y - overflow for y in ys]
            for k in range(len(ys) - 2, -1, -1):
                ys[k] = min(ys[k], ys[k + 1] - gap)
        for item, y in zip(group, ys):
            bold = font(23, bold=True)
            plain = font(19)
            title_w = draw.textlength(item.title, font=bold)
            detail_w = draw.textlength(item.detail, font=plain)
            width = max(title_w, detail_w)
            if side == "left":
                x = margin * scale
                start = x + width + 12 * scale
                elbow = start + 26 * scale
            else:
                x = image.width - margin * scale - width
                start = x - 12 * scale
                elbow = start - 26 * scale
            ax, ay = pixels[item.anchor]
            line = [(start, y), (elbow, y), (ax, ay)]
            draw.line(line, fill=LEADER, width=2 * scale, joint="curve")
            radius = 6 * scale
            draw.ellipse(
                (ax - radius, ay - radius, ax + radius, ay + radius),
                fill="white",
                outline=INK,
                width=2 * scale,
            )
            draw.text((x, y - 28 * scale), item.title, font=bold, fill=INK)
            if item.detail:
                draw.text((x, y + 2 * scale), item.detail, font=plain, fill=QUIET)


def torso_lift(group: str, contents: float, lid: float) -> float:
    """How far a torso part is raised to open the robot up."""
    if group == "cover":
        return lid
    if group == "pelvis" or group in ON_THE_WALL or any(word in group for word in LEGS):
        return 0.0
    return contents


def anatomy(cache: Path) -> None:
    size = (1500, 1320)
    contents, lid = 112.0, 192.0
    parts = meshes("neutral", cache)
    plotter = stage(size)
    focal = (0.0, 0.0, 262.0)
    lights(plotter, focal, (-900.0, 1100.0, 1500.0))
    lookup: dict[str, tuple[float, float, float]] = {}
    wheels: list[tuple[float, float, float]] = []
    eye = (-880.0, 1500.0, 760.0)
    for (group, material), mesh in parts.items():
        if group in LOOSE_ENDS:
            continue
        rise = torso_lift(group, contents, lid)
        moved = mesh.translate((0, 0, rise), inplace=False)
        plotter.add_mesh(
            moved,
            smooth_shading=True,
            split_sharp_edges=True,
            feature_angle=32.0,
            **MATERIALS[material],
        )
        if group not in lookup or material == "tyre":
            middle = np.asarray(centre(mesh, rise))
            towards = np.asarray(eye) - middle
            lookup[group] = nearest_surface(
                moved, middle + 45.0 * towards / np.linalg.norm(towards)
            )
        if material == "tyre":
            wheels.append((*centre(mesh)[:2], 0.0))
    camera = plotter.camera
    camera.position = eye
    camera.focal_point = focal
    camera.up = (0.0, 0.0, 1.0)
    camera.view_angle = 20.5
    camera.clipping_range = (100.0, 14000.0)

    items = [
        Callout("cover", "Lid", "3D-printed", "left"),
        Callout(
            "controller carrier board",
            "Controller board",
            "our own circuit board",
            "left",
        ),
        Callout("battery packs", "Battery", "two packs, about 24 V", "left"),
        Callout("right thigh", "Thigh", "3D-printed, 105 mm", "left"),
        Callout("right shin", "Shin", "3D-printed, 105 mm", "left"),
        Callout("right wheel", "Wheel", "80 mm inline skate", "left"),
        Callout("SBC board", "Banana Pi computer", "runs the neural network", "right"),
        Callout("IMU board", "Motion sensor", "knows which way is up", "right"),
        Callout("power switch board", "Power board", "our own circuit board", "right"),
        Callout("left hip motor", "Hip motor", "one of six identical motors", "right"),
        Callout("left knee motor", "Knee motor", "bends the leg", "right"),
        Callout("left wheel motor", "Wheel motor", "balances and drives", "right"),
    ]
    image, pixels = shoot(plotter, {i.anchor: lookup[i.anchor] for i in items}, wheels)
    draw_callouts(image, pixels, items)
    finish(image, HERE / "anatomy.png")


def moves(cache: Path) -> None:
    size = (1600, 740)
    spacing = 440.0
    turn = -58.0
    captions = {
        "ride": "Riding tall",
        "crouch": "Crouching",
        "air": "Jumping",
    }
    plotter = stage(size)
    focal = (0.0, 0.0, 165.0)
    lights(plotter, focal, (-500.0, 1400.0, 1400.0))
    anchors: dict[str, tuple[float, float, float]] = {}
    wheels: list[tuple[float, float, float]] = []
    heights: dict[str, float] = {}
    for index, name in enumerate(captions):
        x = (1 - index) * spacing
        top = 0.0
        bottom = 1e9
        for (group, material), mesh in meshes(name, cache).items():
            if group in LOOSE_ENDS:
                continue
            placed = mesh.rotate_z(turn, point=(0, 0, 0), inplace=False).translate(
                (x, 0, 0), inplace=False
            )
            plotter.add_mesh(
                placed,
                smooth_shading=True,
                split_sharp_edges=True,
                feature_angle=32.0,
                **MATERIALS[material],
            )
            top = max(top, placed.bounds[5])
            if material == "tyre":
                wheels.append((*centre(placed)[:2], placed.bounds[4]))
            bottom = min(bottom, placed.bounds[4])
        heights[name] = top
        anchors[f"{name} base"] = (x, 0.0, 0.0)
        anchors[f"{name} wheel"] = (x, 0.0, bottom)
        anchors[f"{name} top"] = (x, 0.0, top)
    camera = plotter.camera
    camera.position = (0.0, 3200.0, 620.0)
    camera.focal_point = focal
    camera.up = (0.0, 0.0, 1.0)
    camera.enable_parallel_projection()
    camera.parallel_scale = 262.0
    camera.clipping_range = (100.0, 14000.0)
    image, pixels = shoot(plotter, anchors, wheels, ssao=None)

    draw = ImageDraw.Draw(image)
    scale = SUPERSAMPLE
    bold = font(27, bold=True)
    plain = font(21)
    notes = {
        "ride": f"{heights['ride']:.0f} mm tall",
        "crouch": f"{heights['crouch']:.0f} mm tall",
        "air": "wheels about 4 cm off the floor",
    }
    for name, title in captions.items():
        cx, _ = pixels[f"{name} base"]
        y = image.height - 96 * scale
        draw.text((cx, y), title, font=bold, fill=INK, anchor="ma")
        draw.text(
            (cx, y + 40 * scale), notes[name], font=plain, fill=QUIET, anchor="ma"
        )
    finish(image, HERE / "moves.png")
    print({k: round(v, 1) for k, v in heights.items()})


JOBS = {"anatomy": anatomy, "moves": moves}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jobs", nargs="*", default=list(JOBS))
    parser.add_argument(
        "--cache", type=Path, default=Path(tempfile.gettempdir()) / "skaterbot-render"
    )
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    for job in args.jobs:
        JOBS[job](args.cache)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
