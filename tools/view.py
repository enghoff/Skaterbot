# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9", "ocp_vscode"]
# ///
"""Show a model in the OCP CAD Viewer -- the interactive half of what /views did.

    uv run tools/view.py                     # the whole robot, neutral pose
    uv run tools/view.py pelvis-shell        # one printed piece, on its own
    uv run tools/view.py --list              # what can be shown
    uv run tools/view.py pelvis-shell --finished   # with its edges broken
    uv run tools/view.py --finished          # the whole robot, edges broken

A 0.5 mm chamfer on a 339 mm robot is about a seventh of one per cent of its
height, so it is not visible until you zoom into an edge. It is not meant to be
seen from across the room; tools/finish_report.py is how you check it is there,
and `--finished --count` reports the faces and volume it changed.

Free and offline: the geometry is tessellated locally and pushed to a viewer over
a socket, so unlike /views this spends no API credits and takes about a second.

WHERE THE VIEWER COMES FROM. Either the OCP CAD Viewer extension in VS Code --
open its panel and it listens on port 3939 -- or the standalone browser viewer,
which this repository can start for itself:

    uv run --with ocp_vscode --with build123d python -m ocp_vscode --port 3939

Colours are the robot's own palette, read from cad/parameters.py, for the same
reason the URDF reads it: a colour retyped here would be a second source of it.

A NOTE ON WHAT A RENDER PROVES. Nothing, on its own. CLAUDE.md is explicit that a
boolean which succeeds is not a boolean that worked, and looking at a part is the
weakest way to check it -- structure behind a hole makes an open one look closed.
tools/gate_e.py counts the holes on the finished solid instead, and that is the
check. This is for looking at the machine.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def whole_robot(finished: bool = False, size: float = 0.5):
    """The neutral assembly, grouped so each material reads as itself.

    With `finished`, the two PRINTED groups get their outer edges broken. The
    actuators, the wheels and the clamp hardware are bought and are left alone --
    nothing chamfers a motor casing.
    """
    from build123d import Axis, Plane, Pos, mirror

    from cad import parameters as P
    from cad.actuator import actuatorAssembly
    from cad.parameters import hipCenterX
    from cad.shin import shinLeft, shinRight
    from cad.skate_wheel import skateWheelHub, skateWheelTread
    from cad.thigh import thighLeft, thighRight
    from cad.torso import pelvisShell, torsoCover
    from cad.wheel import _clampHardware
    from cad.wheel_adapter import wheelAdapterLeft, wheelAdapterRight
    from cad.wheeled_parameters import (
        prototypeWheelAxisHeight,
        wheeledHipPitchAxisHeight,
        wheeledKneeAxisHeight,
        wheeledShinCenterZ,
        wheeledThighCenterZ,
        wheeledTorsoCenterHeight,
    )

    def motor(x, z, spin):
        return [Pos(x, 0, z) * b.rotate(Axis.Y, spin) for b in actuatorAssembly()]

    motors = (
        motor(-hipCenterX, wheeledHipPitchAxisHeight, -90)
        + motor(-hipCenterX, wheeledKneeAxisHeight, 90)
        + motor(-hipCenterX, prototypeWheelAxisHeight, -90)
        + motor(hipCenterX, wheeledHipPitchAxisHeight, 90)
        + motor(hipCenterX, wheeledKneeAxisHeight, -90)
        + motor(hipCenterX, prototypeWheelAxisHeight, 90)
    )

    printed = (
        [Pos(-hipCenterX, 0, wheeledThighCenterZ) * b for b in thighLeft()]
        + [Pos(hipCenterX, 0, wheeledThighCenterZ) * b for b in thighRight()]
        + [Pos(-hipCenterX, 0, wheeledShinCenterZ) * b for b in shinLeft()]
        + [Pos(hipCenterX, 0, wheeledShinCenterZ) * b for b in shinRight()]
        + [
            Pos(-hipCenterX, 0, prototypeWheelAxisHeight) * b
            for b in wheelAdapterLeft()
        ]
        + [
            Pos(hipCenterX, 0, prototypeWheelAxisHeight) * b
            for b in wheelAdapterRight()
        ]
        + [Pos(0, 0, wheeledTorsoCenterHeight) * b for b in pelvisShell()]
    )

    hubs, treads, clamps = [], [], []
    for sign in (-1, 1):
        at = Pos(sign * hipCenterX, 0, prototypeWheelAxisHeight)
        hub, tread = skateWheelHub(), skateWheelTread()
        clamp = _clampHardware()
        if sign < 0:
            hub = mirror(hub, Plane.YZ)
            tread = mirror(tread, Plane.YZ)
            clamp = [mirror(c, Plane.YZ) for c in clamp]
        hubs.append(at * hub)
        treads.append(at * tread)
        clamps += [at * c for c in clamp]

    cover = [Pos(0, 0, wheeledTorsoCenterHeight) * torsoCover()]

    if finished:
        from cad.finish import chamfered

        printed, cut_a, sharp_a = chamfered(printed, size)
        cover, cut_b, sharp_b = chamfered(cover, size)
        print(
            f"finished: {cut_a + cut_b} edges chamfered, "
            f"{sharp_a + sharp_b} left sharp (printed parts only)"
        )

    return {
        "printed structure": (printed, P.printedOrange),
        "torso cover": (cover, P.printedDark),
        "actuators": (motors, P.motorGrey),
        "wheel hubs": (hubs, P.printedDark),
        "tyres": (treads, P.soleBlack),
        "clamp hardware": (clamps, P.bearingSteel),
    }


def _describe(raw, finished) -> str:
    """What the chamfer actually did to what is being shown.

    Face count, not face shape. A chamfer adds a face per edge it cuts, so the
    difference between the raw part and the finished one is a direct count of
    the work -- where guessing at a chamfer face by its dimensions is a heuristic
    that gets the geometry wrong (the face's bounding box is one chamfer leg in
    each of two axes, not one chamfer width in one).
    """

    def faces(bodies):
        if not isinstance(bodies, (list, tuple)):
            bodies = [bodies]
        return sum(len(b.faces()) for b in bodies)

    def volume(bodies):
        if not isinstance(bodies, (list, tuple)):
            bodies = [bodies]
        return sum(b.volume for b in bodies)

    return (
        f"faces {faces(raw)} -> {faces(finished)} "
        f"(+{faces(finished) - faces(raw)}), "
        f"volume {volume(finished) - volume(raw):+.2f} mm3"
    )


def pieces() -> dict[str, callable]:
    from cad import joint, thigh, torso, wheel_adapter

    return {
        "joint-stator-clevis": joint.statorClevis,
        "joint-rotor-hub": joint.rotorHub,
        "limb-105-unmirrored": thigh.thighRight,
        "limb-105-mirrored": thigh.thighLeft,
        "wheel-adapter-right": wheel_adapter.wheelAdapterRight,
        "wheel-adapter-left": wheel_adapter.wheelAdapterLeft,
        "pelvis-shell": torso.pelvisShell,
        "torso-cover": torso.torsoCover,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "piece", nargs="?", help="a printed piece; default is the robot"
    )
    parser.add_argument("--list", action="store_true", help="list what can be shown")
    parser.add_argument(
        "--finished",
        action="store_true",
        help="show it as it would be printed: outer edges chamfered"
        " (cad/finish.py). Works on a single piece or on the whole robot, and on"
        " the robot it takes about a minute because the pelvis is slow.",
    )
    parser.add_argument("--port", type=int, default=3939)
    parser.add_argument(
        "--size",
        type=float,
        default=None,
        help="chamfer size in mm for --finished (default 0.5). Push an"
        " exaggerated 2 or 3 to SEE that the chamfer is being applied; 0.5 is"
        " under a pixel at any zoom that fits a whole part on screen.",
    )
    parser.add_argument(
        "--count",
        action="store_true",
        help="with --finished, report how many faces and how much volume the"
        " chamfer changed, so 'I cannot see it' is settled by a number",
    )
    args = parser.parse_args()

    if args.list:
        print("robot        the neutral 339 mm assembly (default)")
        for name in sorted(pieces()):
            print(f"{name}")
        return 0

    import ocp_vscode
    from build123d import Color

    ocp_vscode.set_port(args.port)

    if args.piece and args.piece != "robot":
        built = pieces()
        if args.piece not in built:
            print(f"no such piece: {args.piece}; try --list", file=sys.stderr)
            return 2
        from cad.parameters import printedOrange

        bodies = built[args.piece]()
        if args.finished:
            from cad.finish import chamfered

            raw = bodies
            bodies, cut, sharp = chamfered(bodies, args.size or 0.5)
            print(f"finished: {cut} edges chamfered, {sharp} left sharp")
            if args.count:
                print("  " + _describe(raw, bodies))
        if not isinstance(bodies, (list, tuple)):
            bodies = [bodies]
        for body in bodies:
            body.color = Color(printedOrange)
        ocp_vscode.show(
            *bodies, names=[f"{args.piece}-{i}" for i in range(len(bodies))]
        )
        print(f"showing {args.piece}: {len(bodies)} bodies")
        return 0

    grouped = whole_robot(finished=args.finished, size=args.size or 0.5)
    objs, names = [], []
    for label, (bodies, colour) in grouped.items():
        for i, body in enumerate(bodies):
            body.color = Color(colour)
            objs.append(body)
            names.append(f"{label} {i}")
    ocp_vscode.show(*objs, names=names)
    print(f"showing the robot: {len(objs)} bodies in {len(grouped)} groups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
