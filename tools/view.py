# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9", "ocp_vscode"]
# ///
"""Show a model in the OCP CAD Viewer -- the interactive half of what /views did.

    uv run tools/view.py                     # the whole robot, neutral pose
    uv run tools/view.py pelvis-shell        # one printed piece, on its own
    uv run tools/view.py torso-packing-check # a check scene, its groups named
    uv run tools/view.py --list              # what can be shown
    uv run tools/view.py pelvis-shell --finished   # with its edges broken
    uv run tools/view.py --finished          # the whole robot, edges broken

WHAT THE ROBOT VIEW CARRIES, which is more than it used to. The tree is built
here rather than taken from cad/main.py, and for a long time it was built out of
printed shells and bought hardware only -- so the payload standing inside the
pelvis was in the assembly, in the mass roll-up and in the check scenes, and in
the viewer it was simply absent. It is a "payload" branch under the torso now.
The check scenes are new here too: cad/scenes.py already builds each one as
named groups, which is exactly the tree a viewer wants, so any of them can be
named instead of a piece.

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


def _piece(label: str, bodies, colour):
    """One piece of the machine, as one node of the viewer's tree.

    A piece drawn as several interpenetrating bodies -- which here is most of
    them -- becomes a named node with its shells underneath, so the tree says
    "thigh" once and keeps the five bodies it is made of behind that. A piece
    that is a single body is shown as that body, rather than as a node with one
    thing in it.
    """
    from build123d import Color, Compound

    bodies = list(bodies)
    for i, body in enumerate(bodies):
        body.color = Color(colour)
        body.label = label if len(bodies) == 1 else f"{label} {i + 1}"
    if len(bodies) == 1:
        return bodies[0]
    return Compound(children=bodies, label=label)


def _payload_colour(name: str) -> str:
    """What a payload body is made of, from what cad/electronics.py calls it.

    Four of these colours had been declared in that file since the port with
    nothing drawing them, because nothing had ever drawn these bodies: the viewer
    built its own tree out of shells and legs and never asked what stands inside
    the pelvis. Two more arrived with the battery, for the packs and for copper.
    """
    from cad.electronics import (
        canSilver,
        cellGrey,
        componentBlack,
        copperRed,
        pcbGreen,
        terminalBlue,
    )

    if name.endswith("board"):
        return pcbGreen
    if name == "battery packs":
        return cellGrey
    if "lead" in name or name == "battery series link" or name.endswith("loom"):
        return copperRed
    if name == "capacitor bank":
        return canSilver
    if name in ("bus terminal", "fuse holder", "main disconnect", "balance ports"):
        return terminalBlue
    return componentBlack


def _group_colour(name: str) -> str:
    """What a check scene's named group is, by the name cad/scenes.py gives it.

    Order matters in one place: "left wheel motor" is a motor rather than a
    wheel, so the motor test comes first.
    """
    from cad import parameters as P

    if name == "reservations":
        return P.sensorBlue
    if name == "cover":
        return P.printedDark
    if "motor" in name:
        return P.motorGrey
    if "hardware" in name:
        return P.bearingSteel
    if "wheel" in name:
        return P.soleBlack
    if name == "pelvis" or name.endswith(("thigh", "shin", "limb")):
        return P.printedOrange
    return _payload_colour(name)


def check_scene(name: str):
    """One of cad/scenes.py's configurations, as the tree of its named groups.

    The scenes come in two forms for this exact reason -- the flat assembly for
    a measurement, the named groups for looking -- so the viewer takes the
    groups and the tree writes itself.
    """
    from build123d import Compound

    from cad.scenes import GROUPS

    groups = GROUPS[name]()
    return Compound(
        children=[
            _piece(group, bodies, _group_colour(group))
            for group, bodies in groups.items()
            if bodies
        ],
        label=name,
    )


def whole_robot(finished: bool = False, size: float = 0.5):
    """The neutral assembly, as the tree the machine actually is.

    Torso, left leg, right leg; and within a leg the three actuators, the steel
    that closes the hip, the thigh, the shin and the wheel module, in the order
    they are stacked. Colour still
    says what a thing is made of, but the tree now says what it IS, so hiding a
    leg hides its wheel -- which a flat list of thirty-three bodies all called
    "printed structure" could not do.

    With `finished`, every printed piece gets its outer edges broken. The
    actuators, the wheels and the clamp hardware are bought and are left alone --
    nothing chamfers a motor casing.
    """
    from build123d import Axis, Compound, Plane, Pos, mirror

    from cad import parameters as P
    from cad.actuator import actuatorAssembly
    from cad.electronics import torsoElectronicsGroups
    from cad.hardware import jointHardware
    from cad.parameters import hipCenterX
    from cad.shin import shinLeft, shinRight
    from cad.skate_wheel import skateWheelHub, skateWheelTread
    from cad.thigh import thighLeft, thighRight
    from cad.torso import pelvisShell, torsoCover
    from cad.wheel import clampScrew, clampWasher, heatSetInsert
    from cad.wheel_adapter import wheelAdapterLeft, wheelAdapterRight
    from cad.wheeled_parameters import (
        prototypeWheelAxisHeight,
        wheeledHipPitchAxisHeight,
        wheeledKneeAxisHeight,
        wheeledShinCenterZ,
        wheeledThighCenterZ,
        wheeledTorsoCenterHeight,
    )

    sides = {"left leg": -1, "right leg": 1}
    thigh_of = {-1: thighLeft, 1: thighRight}
    shin_of = {-1: shinLeft, 1: shinRight}
    adapter_of = {-1: wheelAdapterLeft, 1: wheelAdapterRight}

    def motor(x, z, spin):
        return [Pos(x, 0, z) * b.rotate(Axis.Y, spin) for b in actuatorAssembly()]

    # The printed pieces are gathered before anything is assembled, and kept
    # piece by piece, because the finish pass has to know where each piece ends:
    # it decides which arrises are real by merging a piece's bodies, and a thigh
    # and a shin are as interpenetrating at the knee as two bodies of either one.
    torso_at = Pos(0, 0, wheeledTorsoCenterHeight)
    printed = {
        ("torso", "pelvis shell"): [torso_at * b for b in pelvisShell()],
        ("torso", "cover"): [torso_at * torsoCover()],
    }
    for leg, sign in sides.items():
        x = sign * hipCenterX
        printed[leg, "thigh"] = [
            Pos(x, 0, wheeledThighCenterZ) * b for b in thigh_of[sign]()
        ]
        printed[leg, "shin"] = [
            Pos(x, 0, wheeledShinCenterZ) * b for b in shin_of[sign]()
        ]
        printed[leg, "wheel adapter"] = [
            Pos(x, 0, prototypeWheelAxisHeight) * b for b in adapter_of[sign]()
        ]

    if finished:
        from cad.finish import chamfered_pieces

        pieces, cut, sharp = chamfered_pieces(printed.values(), size)
        printed = dict(zip(printed, pieces))
        print(
            f"finished: {cut} edges chamfered, {sharp} left sharp (printed parts only)"
        )

    def hip_joint_hardware(sign):
        """The bought steel that closes the hip: the bearing and its journal.

        The left set is the right one turned round, the same way cad/main.py
        places it. Neither is printed -- tools/mass.py counts them from
        mass_budget.toml at 9.9 g a set -- so the finish pass never sees them.
        """
        at = Pos(sign * hipCenterX, 0, wheeledHipPitchAxisHeight)
        ball_bearing, pin = jointHardware()
        if sign < 0:
            ball_bearing, pin = (b.rotate(Axis.Z, 180) for b in (ball_bearing, pin))
        return Compound(
            children=[
                _piece("bearing", [at * ball_bearing], P.bearingSteel),
                _piece("journal", [at * pin], P.bearingSteel),
            ],
            label="hip joint hardware",
        )

    def wheel_module(leg, sign):
        """The printed adapter, the skate wheel it carries, and its clamp."""
        at = Pos(sign * hipCenterX, 0, prototypeWheelAxisHeight)
        hub, tread = skateWheelHub(), skateWheelTread()
        # Named one by one rather than as a bag of "clamp hardware": these are
        # three bought items and which is which is the thing worth seeing.
        clamp = {
            "cap screw": clampScrew(),
            "washer": clampWasher(),
            "heat-set insert": heatSetInsert(),
        }
        if sign < 0:
            hub = mirror(hub, Plane.YZ)
            tread = mirror(tread, Plane.YZ)
            clamp = {name: mirror(b, Plane.YZ) for name, b in clamp.items()}
        return Compound(
            children=[
                _piece("adapter", printed[leg, "wheel adapter"], P.printedOrange),
                _piece("hub", [at * hub], P.printedDark),
                _piece("tyre", [at * tread], P.soleBlack),
                Compound(
                    children=[
                        _piece(name, [at * body], P.bearingSteel)
                        for name, body in clamp.items()
                    ],
                    label="clamp",
                ),
            ],
            label="wheel module",
        )

    def one_leg(leg, sign):
        """Hip to tyre, in the order the joints are stacked."""
        x = sign * hipCenterX
        return Compound(
            children=[
                _piece(
                    "hip pitch actuator",
                    motor(x, wheeledHipPitchAxisHeight, sign * 90),
                    P.motorGrey,
                ),
                hip_joint_hardware(sign),
                _piece("thigh", printed[leg, "thigh"], P.printedOrange),
                _piece(
                    "knee actuator",
                    motor(x, wheeledKneeAxisHeight, -sign * 90),
                    P.motorGrey,
                ),
                _piece("shin", printed[leg, "shin"], P.printedOrange),
                _piece(
                    "wheel actuator",
                    motor(x, prototypeWheelAxisHeight, sign * 90),
                    P.motorGrey,
                ),
                wheel_module(leg, sign),
            ],
            label=leg,
        )

    # What stands inside the pelvis, which the robot view did not carry at all
    # until the boards were drawn properly. It is a branch of its own so that the
    # lid can be hidden and the payload looked at in place, and the reserved
    # volumes are deliberately NOT here -- four opaque boxes would swallow the
    # boards they are drawn around. cad/scenes.py's torso_packing_check is where
    # the reservations belong, and that scene is now viewable.
    payload = Compound(
        children=[
            _piece(name, [torso_at * body for body in bodies], _payload_colour(name))
            for name, bodies in torsoElectronicsGroups().items()
        ],
        label="payload",
    )
    torso = Compound(
        children=[
            _piece("pelvis shell", printed["torso", "pelvis shell"], P.printedOrange),
            _piece("cover", printed["torso", "cover"], P.printedDark),
            payload,
        ],
        label="torso",
    )
    return Compound(
        children=[torso] + [one_leg(leg, sign) for leg, sign in sides.items()],
        label="robot",
    )


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
        "piece",
        nargs="?",
        help="a printed piece or a check scene; default is the robot",
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
        from cad.scenes import GROUPS

        print("robot        the neutral 339 mm assembly (default)")
        for name in sorted(pieces()):
            print(f"{name}")
        print()
        print("and the check scenes, which come with their groups named:")
        for name in sorted(GROUPS):
            print(f"{name}")
        return 0

    import ocp_vscode

    ocp_vscode.set_port(args.port)

    if args.piece and args.piece != "robot":
        from cad.scenes import GROUPS

        # A scene is named with underscores in cad/scenes.py and the printed
        # pieces are named with hyphens, and nobody types the difference
        # reliably, so either spelling finds the scene.
        scene = args.piece.replace("-", "_")
        if scene in GROUPS:
            if args.finished:
                print("scenes are drawn as modelled; --finished applies to pieces")
            shown = check_scene(scene)
            ocp_vscode.show(shown)
            print(
                f"showing {scene}: {len(shown.solids())} bodies"
                f" in {len(shown.children)} groups"
            )
            return 0

        built = pieces()
        if args.piece not in built:
            print(f"no such piece or scene: {args.piece}; try --list", file=sys.stderr)
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
        ocp_vscode.show(_piece(args.piece, bodies, printedOrange))
        print(f"showing {args.piece}: {len(bodies)} bodies")
        return 0

    robot = whole_robot(finished=args.finished, size=args.size or 0.5)
    # One object, not a list: the viewer's tree is the assembly's own tree, so
    # the names and the nesting come from the labels rather than from a parallel
    # list of strings that has to be kept in step with the bodies.
    ocp_vscode.show(robot)
    parts = sum(len(leg.children) for leg in robot.children)
    print(f"showing the robot: {len(robot.solids())} bodies in {parts} components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
