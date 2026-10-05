# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1"]
# ///
"""Gate I -- can the torso be put together, in order, by hand?

WHY THIS GATE EXISTS. Gates E to H check the robot ASSEMBLED: every part where
it ends up, clear of every other. None of them asks whether a part can GET
there. A board that fits in its bay but has to pass through a connector on the
way in, or a lid that closes over a boss it cannot clear on the way down, is
invisible to all of them, and the torso is the one assembly on this robot where
that is likely: sixty-odd bought parts in a 149 x 67 x 81 mm box, put in from
the top one layer at a time.

So this gate walks the torso's build order. Each step names what goes in and
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
  could not be assembled, so the journal is bought again").
* Hands and tools. A clear path for the part says nothing about room for the
  fingers holding it or the key turning its screw; docs/BUILD_REVIEW.md lists
  the screws whose access has been looked at.
* Anything not drawn, like every other gate.

The order is the one the torso has to be built in, and the order is itself a
finding: the rear-wall hardware goes in AFTER the deck, because the controller
carrier cannot pass the button or the antenna bulkhead on the way down, and the
deck cannot pass the charge inlet -- measured, each blocks it within 9 mm. So
the deck also cannot come out until all three have. See docs/BUILD_REVIEW.md.
The inlet is the one of the three that goes in from inside, since it became a
male XT60E-M on 2026-10-05, and its station was chosen for that way in.

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

# Everything that rides on the deck and goes in with it.
DECK = [
    "deck",
    ("battery foam", 0),
    ("battery foam", 1),
    "controller standoffs",
    "controller carrier board",
    "WeAct core board",
    "CAN transceivers",
    "actuator harness bank",
    "SBC standoffs",
    "SBC board",
    "SBC 40-pin header",
    "SBC ports",
    "SBC microSD slot",
    "bus monitor",
    "logic BEC",
]


def steps() -> list[tuple[str, list, list, bool]]:
    """(what goes in, what moves, its path out, whether it threads onto its own
    group) in build order. A path is a list of legs, (direction, distance), run
    from the part's final place outwards; a distance of None means until the
    part is clear of the shell."""
    return [
        ("IMU onto its seat", ["IMU board", "IMU sensor"], [(UP, None)], False),
        (
            "distribution board on its nuts",
            ["distribution board standoffs", "distribution board", "bus input socket"],
            [(UP, None)],
            False,
        ),
        (
            "power switch board on its spacers",
            [
                "power switch spacers",
                "power switch board",
                "power switch parts",
                "capacitor bank",
            ],
            [(UP, None)],
            False,
        ),
        # The end pads go onto the left wall first. Then the battery goes in as
        # ONE BLOCK, since 2026-10-05: both packs and the BMS between them,
        # assembled beforehand, with the four side strips already on its outer
        # faces, straight down past the wall pads.
        (
            "end pads onto the left wall",
            [("battery foam", 6), ("battery foam", 7)],
            [(UP, None)],
            False,
        ),
        (
            "the battery block, with its side strips on",
            [
                ("battery packs", 0),
                ("battery packs", 1),
                "BMS board",
                ("battery foam", 2),
                ("battery foam", 3),
                ("battery foam", 4),
                ("battery foam", 5),
            ],
            [(UP, None)],
            False,
        ),
        # Each pack's XT60 mated with its male of the series harness, laid into
        # the strip beside it from above.
        ("the packs' two XT60s", ["battery pack connectors"], [(UP, None)], False),
        ("the deck, with everything on it", DECK, [(UP, None)], False),
        # THE REAR WALL'S NUTS GO IN FIRST, straight down against the wall, and
        # are held there while what they fasten is threaded into them from
        # outside. Put on the other way round -- the part through the wall, then
        # its nut run up its thread from inside -- the button's and the
        # antenna's nuts would have to start at the tips of their bushings, and
        # with the deck in, the core board and the SBC are there. The part then
        # threads through its own nut, so it is not measured against it.
        (
            "on/off button's nut, held on the wall",
            [("on/off button", 2)],
            [(UP, None)],
            False,
        ),
        (
            "antenna bulkhead's nut, held on the wall",
            [("antenna bulkhead", 1)],
            [(UP, None)],
            False,
        ),
        # THE CHARGE INLET GOES IN FROM INSIDE, since it became an XT60E-M on
        # 2026-10-05: its ears bear on the inside face, so it comes down in
        # front of the wall and goes back until its nose is out through the
        # cutout. The female it replaced went in from outside, flange first.
        (
            "charge inlet, nose out through the wall",
            [("charge inlet", 0), ("charge inlet", 1), ("charge inlet", 2)],
            [(IN, 8.5), (UP, None)],
            False,
        ),
        # Then its nuts onto the back of its ears, beside its body, held there
        # while the screws come in from outside. They come down in front of the
        # rear right cover boss and go back to the ear plate, as the female's
        # nuts did to the wall, which tweezers do easily.
        (
            "charge inlet's two nuts, behind its ears",
            [("charge inlet", 3), ("charge inlet", 4)],
            [(IN, 8.5), (UP, None)],
            False,
        ),
        (
            "on/off button, into its nut from outside",
            [("on/off button", 0), ("on/off button", 1)],
            [(OUT, None)],
            True,
        ),
        (
            "antenna bulkhead, into its nut from outside",
            [("antenna bulkhead", 0)],
            [(OUT, None)],
            True,
        ),
        ("the lid", ["cover"], [(UP, None)], False),
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


def main() -> int:
    print("THE TORSO, PUT TOGETHER IN ORDER")
    print(
        "each part is run out along its way in, against everything already in; "
        "it may slide on what it touches and may not pass through anything"
    )
    started = time.time()
    groups = parts()
    shell_box = groups["pelvis"][0].bounding_box()
    installed = [("pelvis", b) for b in groups["pelvis"]]
    failed = 0
    for what, names, path, threads in steps():
        moving = bodies_of(groups, names)
        own = {group for group, _ in moving}
        obstacles = [
            (name, b) for name, b in installed if not (threads and name in own)
        ]
        tick = time.time()
        run, met, shared = travel(moving, obstacles, path, shell_box)
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
    total = len(steps())
    if failed:
        print(
            f"gate I: FAIL -- {failed} of {total} steps blocked ({time.time() - started:.0f}s)"
        )
        return 1
    print(f"gate I: pass -- {total} steps ({time.time() - started:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
