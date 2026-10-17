# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1"]
# ///
"""Gate I -- can the torso and a wheel be put together, in order, by hand?

WHY THIS GATE EXISTS. Gates E to H check the robot ASSEMBLED: every part where
it ends up, clear of every other. None of them asks whether a part can GET
there. A board that fits in its bay but has to pass through a connector on the
way in, or a lid that closes over a boss it cannot clear on the way down, is
invisible to all of them, and the torso is the one assembly on this robot where
that is likely: sixty-odd bought parts in a 149 x 67 x 81 mm box, put in from
the top one layer at a time.

AND THE WHEEL, since 14 October 2026, because it turned out to be the other
one. The adapter's spigot is printed on the output disc, over the six screws
that hold the disc to the motor, and its scallops were drawn to pass the key
and not the head: Ø4.5 down to a Ø5.5 head. Every gate passed it, because no
screw was drawn. So the six screws are drawn now (cad/hardware.py's
outputScrews) and the wheel module is walked here in its build order too --
adapter, screws, wheel, cap, clamp -- which fails at Ø4.5 and passes at the
Ø6.5 the scallops are now.

So this gate walks each build order. Each step names what goes in and
the path it comes in on, and the gate runs that path BACKWARDS -- from where
the part ends up, out to free air -- in steps of STEP_MM, measuring the moving
part against everything that went in before it. A path is clear if the moving
part never shares volume with any of it. Touching is allowed at every point,
so the battery block sliding up past the wall pads, or the deck's pads lifting
off the packs, is fine; passing through anything is not.

STEP_MM is small enough that nothing slips through between samples: two solids
at least a millimetre thick always overlap at one sample or another if one's
path crosses the other.

WHAT IT DOES NOT CHECK:

* The looms and leads. The CAN loom, the actuator harness runs and the
  battery's leads are chases for flexible wire, dressed in after the parts they
  connect, and are left out of every step.
* The legs, and the hip actuators under the pelvis floor. Those joints were
  worked through for assembly one at a time in docs/NOTES.md (see "The joint
  could not be assembled, so the journal is bought again"). Their output
  screws are drawn now, and walking each joint here is the next step.
* Hands and tools. A clear path for the part says nothing about room for the
  fingers holding it or the key turning its screw; docs/BUILD_REVIEW.md lists
  the screws whose access has been looked at. Where a screw goes in head first
  down a bore, as the wheel's output screws do, the head is wider than the key
  that follows it, so the screw's own path answers for the key's.
* Anything not drawn, like every other gate.

The deck goes in with the actuator harness plugs disconnected. Fit the charge
inlet, then connect the harness plugs: moving the inlet inward to clear the
lid boss puts the mated plugs across its insertion path. The rear button goes
in after the deck. The side SMA has a
9.5 mm internal shoulder, so it goes in from inside with its nut outside.
Install the SMA before the button body, which otherwise blocks the inward
installation path. The SMA moves 12 mm inward before lifting clear of the lid
boss; this avoids the corner boss that blocked the old nut's straight drop.

    uv run tools/gate_i.py

Free, offline, no engine.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# How far a part moves between two measurements. See the module docstring.
STEP_MM = 1.0

# A shared volume below this is two faces sliding over each other, measured
# through an inexact boolean -- contact, not interference. It is larger than
# gate H's cubic micron because a face that slides picks up the boolean's
# tolerance at every sample.
CONTACT_MM3 = 1e-3

# How far clear of the shell a part has to get before its path is over.
EXIT_MM = 1.0

UP = (0.0, 0.0, 1.0)
OUT = (0.0, -1.0, 0.0)  # through the rear wall, which is the -y wall
IN = (0.0, 1.0, 0.0)
INBOARD = (-1.0, 0.0, 0.0)  # from the power bay towards the robot's middle

# Everything that rides on the deck and goes in with it.
DECK = [
    "deck",
    ("battery foam", 0),
    ("battery foam", 1),
    # The IMU since 2026-10-14, slid into the rails under the plate and plugged
    # in before the deck goes in, and hanging under it into the power bay as it
    # does. It went in first of everything, onto its floor seat, until then. Its
    # lead is left out, as every lead is.
    "IMU board",
    "IMU jumpers",
    "IMU sensor",
    "IMU socket",
    "IMU plug",
    "controller standoffs",
    "controller carrier board",
    "WeAct core board",
    "CAN transceivers",
    "SBC standoffs",
    "SBC board",
    "SBC 40-pin header",
    "SBC ports",
    "SBC microSD slot",
    "bus monitor standoffs",
    "bus monitor",
    "logic BEC",
]


def steps() -> list[tuple[str, list, list, tuple]]:
    """(what goes in, what moves, its path out, the groups it threads into) in
    build order. A path is a list of legs, (direction, distance), run from the
    part's final place outwards; a distance of None means until the part is
    clear of the shell. What a part threads into is left out of what it is
    measured against, because a thread is drawn as an overlap."""
    return [
        # ONE BOARD IN THE POWER BAY since 2026-10-07, where a bought
        # distribution board went in first and this one followed it on spacers.
        #
        # ITS FOUR SPACERS GO IN FIRST, each dropped onto its post, since
        # 2026-10-15. The board stood on four nuts until then, which went down
        # with it threaded on its screws -- and a nut is never a spacer. An
        # unthreaded spacer will not stay on a screw pointing down, so it is
        # put on the post and the board comes down onto it.
        (
            "power switch spacers onto the posts",
            ["power switch standoffs"],
            [(UP, None)],
            (),
        ),
        # AND THE BOARD DOES NOT GO STRAIGHT DOWN. It reaches both long walls,
        # under the deck's two ledges on this side, and its outboard corners
        # stand under the lid's two screw bosses. It goes in SIDEWAYS instead,
        # while the battery bay beside it is still empty: down 30 mm inboard of
        # its station, outboard under the ledges and the bosses, and the last
        # 5 mm down onto the spacers. The screws go in from above after it.
        # Run backwards, that is this path. It was notched round the ledges for
        # a day so that it could drop past them, 2026-10-07.
        (
            "power switch board onto its spacers",
            [
                "power switch board",
                "power switch parts",
                "capacitor bank",
            ],
            [(UP, 5.0), (INBOARD, 30.0), (UP, None)],
            (),
        ),
        # The end pads go onto the left wall first. Then the battery goes in as
        # ONE BLOCK, since 2026-10-05: both packs and the BMS between them,
        # assembled beforehand, straight down between the wall pads, which bear
        # on its outer faces with no foam since 2026-10-06.
        (
            "end pads onto the left wall",
            [("battery foam", 2), ("battery foam", 3)],
            [(UP, None)],
            (),
        ),
        (
            "the battery block",
            [
                ("battery packs", 0),
                ("battery packs", 1),
                "BMS board",
            ],
            [(UP, None)],
            (),
        ),
        # Each pack's XT60 mated with its male of the series harness, laid into
        # the strip beside it from above.
        ("the packs' two XT60s", ["battery pack connectors"], [(UP, None)], ()),
        ("the deck, harness plugs disconnected", DECK, [(UP, None)], ()),
        # THE CHARGE INLET GOES IN FROM INSIDE, since it became an XT60E-M on
        # 2026-10-05: its ears bear on the inside face, so it comes down in
        # front of the wall and goes back until its nose is out through the
        # cutout. The female it replaced went in from outside, flange first.
        (
            "charge inlet, nose out through the wall",
            [("charge inlet", 0), ("charge inlet", 1), ("charge inlet", 2)],
            [(IN, 8.5), (UP, None)],
            (),
        ),
        # Then its nuts onto the back of its ears, beside its body, held there
        # while the screws come in from outside. They come down in front of the
        # rear right cover boss and go back to the ear plate, as the female's
        # nuts did to the wall, which tweezers do easily.
        (
            "charge inlet's two nuts, behind its ears",
            [("charge inlet", 3), ("charge inlet", 4)],
            [(IN, 8.5), (UP, None)],
            (),
        ),
        # The inlet moved inward to clear the lid boss, 2026-10-12. Fit it
        # while the actuator harness plugs are disconnected, then bring the
        # plugs in from above, clear of the flange.
        (
            "actuator harness plugs, after the inlet",
            ["actuator harness bank"],
            [(UP, None)],
            (),
        ),
        (
            "on/off button's nut, held on the wall",
            [("on/off button", 2)],
            [(UP, None)],
            (),
        ),
        (
            "SMA shoulder from inside, shank out through the wall",
            [("antenna bulkhead", 0)],
            [((1.0, 0.0, 0.0), 12.0), (UP, None)],
            (),
        ),
        (
            "SMA nut onto its shank from outside",
            [("antenna bulkhead", 1)],
            [((-1.0, 0.0, 0.0), None)],
            ("antenna bulkhead",),
        ),
        (
            "on/off button, into its nut from outside",
            [("on/off button", 0), ("on/off button", 1)],
            [(OUT, None)],
            ("on/off button",),
        ),
        ("the lid", ["cover"], [(UP, None)], ()),
    ]


def parts() -> dict[str, list]:
    """Every torso part, torso-local, by group name."""
    from cad import deck, torso
    from cad import electronics as e

    groups = dict(e.torsoElectronicsGroups())
    groups["pelvis"] = torso.pelvisShell()
    groups["deck"] = deck.electronicsDeck()
    groups["cover"] = [torso.torsoCover()]
    return groups


OUTBOARD = (1.0, 0.0, 0.0)  # off the wheel motor's output face, in joint axes


def wheel_steps() -> list[tuple[str, list, list, tuple]]:
    """The right wheel onto its motor, in the joint's own frame, as steps()."""
    return [
        # The insert is melted in from the motor side on the bench, so it rides
        # in with the adapter.
        (
            "adapter, insert in, onto the motor",
            ["wheel adapter", "M5 insert"],
            [(OUTBOARD, None)],
            (),
        ),
        # HEAD FIRST DOWN THE SPIGOT'S SCALLOPS, which is the step that was
        # missing: at Ø4.5 they passed the key and stopped the Ø5.5 head. The
        # motor's threads are drawn at the screw's own Ø3, so the screws slide
        # out of them touching and are measured against the motor like anything
        # else.
        (
            "six output screws, down the scallops",
            ["output screws"],
            [(OUTBOARD, None)],
            (),
        ),
        # The hub covers the screws, so the screws are in first.
        ("the wheel, onto the spigot", ["skate wheel"], [(OUTBOARD, None)], ()),
        ("the cap, into the outboard seat", ["wheel cap"], [(OUTBOARD, None)], ()),
        ("the washer, into the cap", ["clamp washer"], [(OUTBOARD, None)], ()),
        (
            "the M5 clamp screw, into the insert",
            ["clamp screw"],
            [(OUTBOARD, None)],
            ("M5 insert",),
        ),
    ]


def wheel_parts() -> dict[str, list]:
    """The right wheel module's parts, joint-local, by group name."""
    from build123d import Rot

    from cad import wheel
    from cad.actuator import actuatorAssembly
    from cad.hardware import boltedToOutput
    from cad.wheel_adapter import wheelAdapterRight
    from cad.wheel_cap import wheelCapRight

    # Turned onto +X, as cad/scenes.py's wheel module turns it, and threaded
    # where the adapter's holes are.
    motor, screws = boltedToOutput(
        [Rot(0, 90, 0) * b for b in actuatorAssembly()], wheel.wheelRightOutput
    )
    return {
        "motor": motor,
        "wheel adapter": wheelAdapterRight(),
        "M5 insert": [wheel.heatSetInsert()],
        "output screws": screws,
        "skate wheel": wheel.wheelRightGroups()["skate wheel"],
        "wheel cap": [wheelCapRight()],
        "clamp washer": [wheel.clampWasher()],
        "clamp screw": [wheel.clampScrew()],
    }


def bodies_of(groups: dict, names: list) -> list[tuple[str, object]]:
    out = []
    for name in names:
        if isinstance(name, tuple):
            group, index = name
            out.append((group, groups[group][index]))
        else:
            out.extend((name, b) for b in groups[name])
    return out


def _overlap(a, b) -> bool:
    return not (
        a.min.X >= b.max.X
        or b.min.X >= a.max.X
        or a.min.Y >= b.max.Y
        or b.min.Y >= a.max.Y
        or a.min.Z >= b.max.Z
        or b.min.Z >= a.max.Z
    )


class _Box:
    """A bounding box translated, without building a shape to get it."""

    def __init__(self, box, dx, dy, dz):
        self.min = _V(box.min.X + dx, box.min.Y + dy, box.min.Z + dz)
        self.max = _V(box.max.X + dx, box.max.Y + dy, box.max.Z + dz)


class _V:
    def __init__(self, x, y, z):
        self.X, self.Y, self.Z = x, y, z


def travel(moving, obstacles, path, shell_box) -> tuple[float, str | None, float]:
    """Run one path backwards. (distance run, what it met or None, shared mm3)"""
    from build123d import Pos

    boxes = [(b, b.bounding_box()) for _, b in moving]
    obstacle_boxes = [(name, b, b.bounding_box()) for name, b in obstacles]
    ox = oy = oz = 0.0
    run = 0.0
    for direction, distance in path:
        dx, dy, dz = direction
        t = 0.0
        while True:
            t += STEP_MM
            px, py, pz = ox + dx * t, oy + dy * t, oz + dz * t
            moved = [_Box(k, px, py, pz) for _, k in boxes]
            if distance is None:
                if dz > 0 and min(m.min.Z for m in moved) >= shell_box.max.Z + EXIT_MM:
                    break
                if dy < 0 and max(m.max.Y for m in moved) <= shell_box.min.Y - EXIT_MM:
                    break
                if dx > 0 and min(m.min.X for m in moved) >= shell_box.max.X + EXIT_MM:
                    break
                if dx < 0 and max(m.max.X for m in moved) <= shell_box.min.X - EXIT_MM:
                    break
                if t > 400.0:
                    return run + t, "nothing -- never left the shell", 0.0
            elif t > distance:
                break
            for (body, _), mbox in zip(boxes, moved):
                for name, other, obox in obstacle_boxes:
                    if not _overlap(mbox, obox):
                        continue
                    common = (Pos(px, py, pz) * body) & other
                    try:
                        volume = abs(common.volume) if common is not None else 0.0
                    except (ValueError, AttributeError, TypeError):
                        volume = 0.0
                    if volume > CONTACT_MM3:
                        return run + t, name, volume
        step = t if distance is None else distance
        ox, oy, oz = ox + dx * step, oy + dy * step, oz + dz * step
        run += step
    return run, None, 0.0


def _envelope(bodies):
    """One bounding box round all of `bodies`."""
    from build123d import Compound

    return Compound([b for _, b in bodies]).bounding_box()


def walk(title: str, groups: dict, first: str, sequence: list) -> int:
    """Put one assembly together in order, and return how many steps were blocked.

    A part's way out ends once it is clear of the pelvis, which everything in
    the torso goes inside; for an assembly built outwards along an axis, like
    the wheel, it ends once it is clear of everything already in."""
    print(title)
    installed = [(first, b) for b in groups[first]]
    pelvis_box = groups["pelvis"][0].bounding_box() if first == "pelvis" else None
    failed = 0
    for what, names, path, into in sequence:
        moving = bodies_of(groups, names)
        obstacles = [(name, b) for name, b in installed if name not in into]
        tick = time.time()
        exit_box = pelvis_box or _envelope(installed)
        run, met, shared = travel(moving, obstacles, path, exit_box)
        if met is None:
            print(
                f"   ok   {what:<38} clear over {run:5.0f} mm ({time.time() - tick:.0f}s)"
            )
        else:
            failed += 1
            print(
                f"  FAIL  {what:<38} meets the {met} {run:.0f} mm out, sharing "
                f"{shared:.2f} mm3"
            )
        installed.extend(moving)
    print()
    return failed


def main() -> int:
    print(
        "each part is run out along its way in, against everything already in; "
        "it may slide on what it touches and may not pass through anything"
    )
    print()
    started = time.time()
    failed = walk("THE TORSO, PUT TOGETHER IN ORDER", parts(), "pelvis", steps())
    failed += walk(
        "A WHEEL ONTO ITS MOTOR, IN ORDER", wheel_parts(), "motor", wheel_steps()
    )

    total = len(steps()) + len(wheel_steps())
    if failed:
        print(
            f"gate I: FAIL -- {failed} of {total} steps blocked ({time.time() - started:.0f}s)"
        )
        return 1
    print(f"gate I: pass -- {total} steps ({time.time() - started:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
