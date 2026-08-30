# /// script
# requires-python = ">=3.11"
# dependencies = ["zoo-kcl>=0.3.181"]
# ///
"""Render a model from several sides in one engine run.

The view names here are the robot's, not the camera's. `front` shows the face
the robot walks towards. Zoo's own view named "front" does the opposite — it
puts the camera on -Y and therefore shows the robot's back — which is the
ordinary CAD convention and a reliable way to mislead yourself. The frame is
fixed by foot.kcl, which puts the rear pressure pads at y = -40 and the front
pads at y = +51: **+Y is forward, +Z is up, +X is the robot's right.**

    uv run tools/views.py main.kcl
    uv run tools/views.py pose_check.kcl --views front,right,iso
    uv run tools/views.py torso.kcl --views all --out renders/torso

This executes on the real engine and therefore spends API credits: one
execution per model, plus one snapshot per view. Renders land in renders/,
which is untracked.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import kcl

ROOT = Path(__file__).resolve().parent.parent

# name -> (vantage direction, up). With zoom on, only the direction matters.
VIEWS: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "front": ((0, 1, 0), (0, 0, 1)),
    "back": ((0, -1, 0), (0, 0, 1)),
    "right": ((1, 0, 0), (0, 0, 1)),
    "left": ((-1, 0, 0), (0, 0, 1)),
    "top": ((0, 0, 1), (0, 1, 0)),
    "bottom": ((0, 0, -1), (0, 1, 0)),
    "iso": ((1, 1, 0.8), (0, 0, 1)),
    "iso_back": ((-1, -1, 0.8), (0, 0, 1)),
}

DEFAULT_VIEWS = ["front", "right", "iso"]
DISTANCE = 1000.0


def camera(view: str) -> kcl.SnapshotOptions:
    vantage, up = VIEWS[view]
    return kcl.SnapshotOptions(
        kcl.CameraLookAt(
            kcl.Point3d(*(component * DISTANCE for component in vantage)),
            kcl.Point3d(0.0, 0.0, 0.0),
            kcl.Point3d(*up),
        ),
        0.1,
    )


async def render(model: Path, views: list[str], out_dir: Path, edges: bool) -> list[Path]:
    images = await kcl.execute_and_snapshot_views(
        str(model),
        kcl.ImageFormat.Png,
        [camera(v) for v in views],
        zoom=True,
        highlight_edges=edges,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for view, image in zip(views, images):
        path = out_dir / f"{model.stem}-{view}.png"
        path.write_bytes(bytes(image))
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", help="the .kcl file to render")
    parser.add_argument(
        "--views",
        default=",".join(DEFAULT_VIEWS),
        help=f"comma-separated, or 'all'. One of: {', '.join(VIEWS)}",
    )
    parser.add_argument("--out", default="renders", help="output directory")
    parser.add_argument(
        "--edges", action="store_true", help="draw edge highlights on the render"
    )
    args = parser.parse_args()

    views = list(VIEWS) if args.views == "all" else args.views.split(",")
    unknown = [v for v in views if v not in VIEWS]
    if unknown:
        print(f"unknown view(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"known views: {', '.join(VIEWS)}", file=sys.stderr)
        return 2

    model = Path(args.model)
    if not model.is_absolute():
        model = ROOT / args.model
    if not model.exists():
        print(f"no such model: {model}", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / args.out

    print(f"engine run: {model.name}, {len(views)} views — this spends API credits")
    try:
        written = asyncio.run(render(model, views, out_dir, args.edges))
    except Exception as exc:  # noqa: BLE001 - the engine diagnostic is the payload
        cause = getattr(exc, "args", ())
        message = cause[0] if cause and isinstance(cause[0], str) else str(exc)
        print(message, file=sys.stderr)
        if "auth_token_missing" in message:
            print(
                "\nauth_token_missing is a BILLING failure, not an authentication one."
                "\nCheck https://zoo.dev/account/billing — see docs/KCL_GOTCHAS.md.",
                file=sys.stderr,
            )
        return 1

    for path in written:
        print(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
