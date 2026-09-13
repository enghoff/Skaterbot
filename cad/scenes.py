"""The check scenes: the robot in configurations the neutral assembly cannot show.

Ported from pose_check.kcl, squat_check.kcl, knee_limit_check.kcl,
knee_prelimit_check.kcl, torso_packing_check.kcl, limb_check.kcl and
wheel_module_check.kcl. The poses they stand in are computed in cad/poses.py;
this module only places bodies at them.

These are the project's regression suite as much as the neutral assembly is. A
change to a shared dimension reaches all of them, and interference that the
standing pose hides -- a shin plate against a thigh plate at the knee stop, a
Ø80 wheel folded up towards its own thigh, a torso floor against a thigh swung
35 degrees forward -- only appears here.

WHAT CHANGED IN THE PORT, AND IT IS THE POINT. In the KCL these were scenes you
looked at, and looking at a part is the weakest evidence there is. Every
clearance they were drawn to show is now measured instead, by tools/gate_f.py,
which computes the real distance between the two solids in question and holds it
against the margin the scene was drawn to prove. The scenes stay because a
picture is still how you find the thing you did not think to measure.

WHY EVERY SCENE COMES IN TWO FORMS. A viewer wants one flat list of bodies; a
clearance wants to know which of them is the thigh. So each scene is built as
NAMED GROUPS -- `poseCheckGroups()` -- and the flat assembly is those groups
poured into a list. Nothing chooses bodies by index or by bounding box, which is
how a measurement stays attached to the part it is about.

TWO SCENES USED TO HIDE A BODY. Importing a name from a KCL module ran the whole
module, so the wheel module review had to import the left wheel purely to hide
it, and the packing check had to hide the torso cover it never wanted. Calling a
function builds only what you asked for, so both hide() calls are simply gone --
the left wheel and the lid are not built here at all.

Every scene is in the robot's own frame: +Y forward, +Z up, +X the robot's right.
"""

from __future__ import annotations

from build123d import Axis, Pos

from cad.actuator import actuatorAssembly
from cad.deck import electronicsDeck
from cad.electronics import torsoElectronicsGroups, torsoReservations
from cad.hardware import jointHardware
from cad.limb import limbAssembly
from cad.parameters import hipCenterX, upperLegLength
from cad.poses import (
    knee_limit_check,
    knee_prelimit_check,
    pose_check,
    squat_check,
)
from cad.shin import shinLeft, shinRight
from cad.thigh import thighLeft, thighRight
from cad.torso import pelvisShell, torsoCover
from cad.wheel import wheelLeft, wheelRight
from cad.wheeled_parameters import wheeledTorsoCenterHeight


def _at(bodies: list, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> list:
    """Bodies moved to a station, without turning them."""
    return [Pos(x, y, z) * body for body in bodies]


def _turned(bodies: list, axis, angle: float, x=0.0, y=0.0, z=0.0) -> list:
    """Bodies turned about an axis through the origin, then moved to a station.

    That order is the KCL's: its rotate() with global = true turned about the
    world axis, and the translate() that followed carried the turned body out to
    the joint. A part is drawn centred on its own axis, so turning it first is
    what puts the pivot in the right place.
    """
    return [Pos(x, y, z) * body.rotate(axis, angle) for body in bodies]


def _leg_groups(pose: dict, hand: str) -> dict[str, list]:
    """One leg of a two-angle pose: thigh, shin, wheel, three motors, hardware.

    `hand` is "left" or "right" and picks both the sign of x and which hand of
    each mirrored part is used. Every position is read out of the pose rather
    than recomputed here, so this cannot disagree with cad/poses.py.

    The pose check names its two legs separately -- leftKneeY, rightKneeY -- while
    the squat is symmetric and names one leg for both, so a name is looked up per
    hand first and plain second.
    """
    side = -1 if hand == "left" else 1
    x = side * hipCenterX
    # Each actuator's axis lies across the robot, and the two hands face opposite
    # ways. The sign flips with the hand, and again between a hip and a knee,
    # because the knee motor is turned round to present its rear cover inboard.
    spin = 90 * side

    def named(name: str) -> float:
        return pose.get(hand + name[0].upper() + name[1:], pose.get(name))

    hipZ = pose.get("poseHipPitchZ", pose.get("squatHipPitchZ"))
    kneeY, kneeZ = named("kneeY"), named("kneeZ")
    wheelY, wheelZ = named("wheelY"), named("wheelZ")
    hipAngle = pose.get(f"{hand}HipAngle", pose.get("squatHipAngle"))
    shinAngle = pose.get(f"{hand}ShinAngle", pose.get("squatShinAngle"))

    thigh = thighLeft if hand == "left" else thighRight
    shin = shinLeft if hand == "left" else shinRight
    wheel = wheelLeft if hand == "left" else wheelRight

    return {
        f"{hand} hip motor": _turned(actuatorAssembly(), Axis.Y, -spin, x=x, z=hipZ),
        f"{hand} knee motor": _turned(
            actuatorAssembly(), Axis.Y, spin, x=x, y=kneeY, z=kneeZ
        ),
        f"{hand} wheel motor": _turned(
            actuatorAssembly(), Axis.Y, -spin, x=x, y=wheelY, z=wheelZ
        ),
        # The bearing, journal and carrier set that closes each hip pitch joint.
        # It hangs off the stationary side, so it does not move with the thigh.
        f"{hand} hip hardware": _turned(
            jointHardware(), Axis.Z, 180 if hand == "left" else 0, x=x, z=hipZ
        ),
        f"{hand} thigh": _turned(
            thigh(),
            Axis.X,
            hipAngle,
            x=x,
            y=named("thighCenterY"),
            z=named("thighCenterZ"),
        ),
        f"{hand} shin": _turned(
            shin(),
            Axis.X,
            shinAngle,
            x=x,
            y=named("shinCenterY"),
            z=named("shinCenterZ"),
        ),
        # The wheel is a solid of revolution bolted to its motor's output, so how
        # far it has turned changes nothing anyone can measure off a scene: it is
        # placed, not rotated.
        f"{hand} wheel": _at(wheel(), x=x, y=wheelY, z=wheelZ),
    }


def _torso_groups(centerZ: float) -> dict[str, list]:
    """The pelvis, its lid and what stands inside it, at one height.

    The payload arrives as the named groups cad/electronics.py builds it in --
    one per board and one per thing standing on a board -- rather than as a
    single "electronics" bag. That is what lets a viewer's tree say which board
    is which and hide one without hiding the torso, and it costs nothing here
    because nothing selects a body by index.
    """
    groups = {
        "pelvis": _at(pelvisShell(), z=centerZ),
        "cover": _at([torsoCover()], z=centerZ),
        # A print of its own, like the cover, and placed beside the pelvis rather
        # than inside torsoAssembly() for the same reason: mass_budget.toml
        # weighs it as its own piece.
        "deck": _at(electronicsDeck(), z=centerZ),
        # And a third print beside them: what the three external connectors are
        # bonded into, lying against the rear wall's inner face.
    }
    for name, bodies in torsoElectronicsGroups().items():
        groups[name] = _at(bodies, z=centerZ)
    groups["reservations"] = _at(torsoReservations(), z=centerZ)
    return groups


def poseCheckGroups() -> dict[str, list]:
    """Crouched stance with the right wheel lifted, for sagittal clearance.

    With hip roll deleted the torso hangs straight off the hip pitch axes, so
    this is also the check that its floor clears a thigh swung 35 degrees
    forward. The standing leg's axle lands at exactly 40 mm, which is the wheel's
    own radius, so the left wheel is tangent to the floor and the drop is real
    rather than drawn; the lifted leg clears the ground by about 27 mm.
    """
    pose = pose_check()
    groups = _torso_groups(pose["poseTorsoCenterZ"])
    groups.update(_leg_groups(pose, "left"))
    groups.update(_leg_groups(pose, "right"))
    return groups


def squatCheckGroups() -> dict[str, list]:
    """The deepest legal squat, both wheels on the ground.

    What this is really for is the knee actuator against the torso floor, and the
    wheel against the shin's own stator plate.
    """
    pose = squat_check()
    groups = _torso_groups(pose["squatTorsoCenterZ"])
    groups.update(_leg_groups(pose, "left"))
    groups.update(_leg_groups(pose, "right"))
    return groups


def _knee_review_groups(pose: dict, kneeAngle: float) -> dict[str, list]:
    """The knee joint alone: motor, thigh above it, shin folded under it.

    Not a stance -- the robot is not standing on anything here. It is the joint by
    itself, with the knee axis at the origin.
    """
    return {
        "motor": _turned(actuatorAssembly(), Axis.Y, -90),
        "thigh": _at(thighRight(), z=pose["upperLinkCenterZ"]),
        "shin": _turned(
            shinRight(),
            Axis.X,
            -kneeAngle,
            y=pose["lowerLinkCenterY"],
            z=pose["lowerLinkCenterZ"],
        ),
    }


def kneeLimitGroups() -> dict[str, list]:
    """The knee at its 110 degree commissioning stop.

    The thigh is held upright with the shin at the limit, so the shin's plate can
    be checked against the thigh's. They lie in different planes, on opposite
    sides of the knee actuator, so nothing can touch.
    """
    pose = knee_limit_check()
    return _knee_review_groups(pose, pose["kneeLimitAngle"])


def kneePreLimitGroups() -> dict[str, list]:
    """The same knee at 100 degrees, just short of contact."""
    pose = knee_prelimit_check()
    return _knee_review_groups(pose, pose["kneePreLimitAngle"])


def limbCheckGroups() -> dict[str, list]:
    """One flat limb bolted to the actuator below it.

    There is no hardware left to show at this joint -- the plate lands straight on
    the actuator's rear cover, and the far bearing that used to close the joint
    went with the clevis.
    """
    return {
        "limb": limbAssembly(upperLegLength),
        "motor": _turned(actuatorAssembly(), Axis.Y, -90, z=-upperLegLength / 2),
    }


def wheelModuleGroups() -> dict[str, list]:
    """One wheel motor and the wheel on it, on their own.

    The narrow scene to look at first: motor-to-tread clearance, how the hub lands
    on the output disc, and that the left/right mirror is the right way round.

    It does NOT show whether the six output holes are open, and never did -- the
    motor stands directly behind them, and structure behind a hole makes an open
    one look closed. tools/gate_e.py counts them on the solid instead.
    """
    return {
        "motor": _turned(actuatorAssembly(), Axis.Y, 90),
        "wheel": wheelRight(),
    }


def torsoPackingGroups() -> dict[str, list]:
    """The pelvis with its lid off and the four payload items standing in it.

    The 65 mm torso is sized by its contents rather than by a round number, so
    "does it fit" is a question about this scene and not about a table. From the
    bottom up: the IMU on the shell floor, in the 51.5 mm of clear floor between
    the two hip pitch saddles; the power-entry block and the controller carrier
    side by side on the saddle tops, which is why the shell is 125 mm wide rather
    than 118; and the SBC over both of them, because at 85 mm it is wider than the
    gap either leaves.
    """
    groups = _torso_groups(wheeledTorsoCenterHeight)
    # The lid is what this scene exists to look under, so it is not built.
    del groups["cover"]
    return groups


def _flat(groups: dict[str, list]) -> list:
    return [body for group in groups.values() for body in group]


def poseCheckAssembly() -> list:
    return _flat(poseCheckGroups())


def squatCheckAssembly() -> list:
    return _flat(squatCheckGroups())


def kneeLimitAssembly() -> list:
    return _flat(kneeLimitGroups())


def kneePreLimitAssembly() -> list:
    return _flat(kneePreLimitGroups())


def limbCheckAssembly() -> list:
    return _flat(limbCheckGroups())


def wheelModuleCheck() -> list:
    return _flat(wheelModuleGroups())


def torsoPackingCheck() -> list:
    return _flat(torsoPackingGroups())


# Every scene, by the name its KCL file had: the named groups, and the flat list.
GROUPS = {
    "pose_check": poseCheckGroups,
    "squat_check": squatCheckGroups,
    "knee_limit_check": kneeLimitGroups,
    "knee_prelimit_check": kneePreLimitGroups,
    "limb_check": limbCheckGroups,
    "wheel_module_check": wheelModuleGroups,
    "torso_packing_check": torsoPackingGroups,
}
SCENES = {
    "pose_check": poseCheckAssembly,
    "squat_check": squatCheckAssembly,
    "knee_limit_check": kneeLimitAssembly,
    "knee_prelimit_check": kneePreLimitAssembly,
    "limb_check": limbCheckAssembly,
    "wheel_module_check": wheelModuleCheck,
    "torso_packing_check": torsoPackingCheck,
}
