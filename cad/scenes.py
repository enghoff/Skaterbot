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
from cad.hardware import boltedToOutput, jointHardware
from cad.parameters import hipCenterX, kneeOutboardOffset, upperLegLength
from cad.poses import (
    knee_limit_check,
    knee_prelimit_check,
    pose_check,
    squat_check,
)
from cad.shin import shinLeft, shinLeftOutput, shinRight, shinRightOutput
from cad.thigh import thighLeft, thighLeftOutput, thighRight, thighRightOutput
from cad.torso import pelvisShell, torsoCover
from cad.wheel import (
    wheelLeft,
    wheelLeftOutput,
    wheelRight,
    wheelRightGroups,
    wheelRightOutput,
)
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
    # EVERYTHING FROM THE KNEE DOWN IS AT ITS OWN STATION ACROSS THE ROBOT. The
    # knee is the only joint with a fork, and the fork's cheek is 3 mm where
    # every other joint lands a 6 mm plate, so the fork ended inside the leg's
    # own exterior face. The joint moves rather than the fork: knee actuator,
    # shin, wheel motor and wheel all stand kneeOutboardOffset further out, which
    # is what cad/limb.py puts the thigh's clevis at. Nothing here changes in Y
    # or Z, so the pose is the pose.
    kneeX = side * (hipCenterX + kneeOutboardOffset)
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

    left = hand == "left"
    thigh = thighLeft if left else thighRight
    shin = shinLeft if left else shinRight
    wheel = wheelLeft if left else wheelRight
    thighOutput = thighLeftOutput if left else thighRightOutput
    shinOutput = shinLeftOutput if left else shinRightOutput
    wheelOutput = wheelLeftOutput if left else wheelRightOutput

    # Where each limb goes, as a function, because the output screws and the
    # motor's threads have to go exactly where the limb's disc does: they turn
    # with it, not with the motor's housing.
    def atThigh(bodies: list) -> list:
        return _turned(
            bodies,
            Axis.X,
            hipAngle,
            x=x,
            y=named("thighCenterY"),
            z=named("thighCenterZ"),
        )

    def atShin(bodies: list) -> list:
        return _turned(
            bodies,
            Axis.X,
            shinAngle,
            x=kneeX,
            y=named("shinCenterY"),
            z=named("shinCenterZ"),
        )

    def atWheel(bodies: list) -> list:
        return _at(bodies, x=kneeX, y=wheelY, z=wheelZ)

    hipMotor, hipScrews = boltedToOutput(
        _turned(actuatorAssembly(), Axis.Y, -spin, x=x, z=hipZ),
        lambda bodies: atThigh(thighOutput(bodies)),
    )
    kneeMotor, kneeScrews = boltedToOutput(
        _turned(actuatorAssembly(), Axis.Y, spin, x=kneeX, y=kneeY, z=kneeZ),
        lambda bodies: atShin(shinOutput(bodies)),
    )
    wheelMotor, wheelScrews = boltedToOutput(
        _turned(actuatorAssembly(), Axis.Y, -spin, x=kneeX, y=wheelY, z=wheelZ),
        lambda bodies: atWheel(wheelOutput(bodies)),
    )

    return {
        f"{hand} hip motor": hipMotor,
        f"{hand} knee motor": kneeMotor,
        f"{hand} wheel motor": wheelMotor,
        # The six M3 that hold each output disc to its motor, a group to a joint
        # so that gate H measures them against the disc, the motor and whatever
        # lands over their heads.
        f"{hand} hip screws": hipScrews,
        f"{hand} knee screws": kneeScrews,
        f"{hand} wheel screws": wheelScrews,
        # The bearing and journal that close each hip pitch joint. They hang off
        # the stationary side, so they do not move with the thigh.
        f"{hand} hip hardware": _turned(
            jointHardware(), Axis.Z, 180 if hand == "left" else 0, x=x, z=hipZ
        ),
        # And the same at the knee, which the thigh's clevis now straddles. The
        # hand is REVERSED against the hip's because the knee motor is turned
        # round: the set that needs no turn at the right hip needs one at the
        # right knee. This one hangs off the thigh, which moves, so it is placed
        # at the knee station the pose computes rather than at a fixed height.
        f"{hand} knee hardware": _turned(
            jointHardware(),
            Axis.Z,
            0 if hand == "left" else 180,
            x=kneeX,
            y=kneeY,
            z=kneeZ,
        ),
        f"{hand} thigh": atThigh(thigh()),
        f"{hand} shin": atShin(shin()),
        # The wheel is a solid of revolution bolted to its motor's output, so how
        # far it has turned changes nothing anyone can measure off a scene: it is
        # placed, not rotated.
        f"{hand} wheel": atWheel(wheel()),
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

    THE THIGH IS THE PIECE AT x = 0 AND EVERYTHING ELSE IS OFFSET, which is the
    same relation the full assembly has the other way round. The knee joint
    stands kneeOutboardOffset outboard of the hip's, so with the thigh drawn in
    its own frame the motor, the far bearing and the shin all sit at that
    offset.
    """

    def atShin(bodies: list) -> list:
        return _turned(
            bodies,
            Axis.X,
            -kneeAngle,
            x=kneeOutboardOffset,
            y=pose["lowerLinkCenterY"],
            z=pose["lowerLinkCenterZ"],
        )

    motor, screws = boltedToOutput(
        _turned(actuatorAssembly(), Axis.Y, -90, x=kneeOutboardOffset),
        lambda bodies: atShin(shinRightOutput(bodies)),
    )
    return {
        "motor": motor,
        "output screws": screws,
        # The far bearing and its journal, on the knee axis. This is the right
        # knee, so the set is turned like the right knee's in the full assembly.
        "hardware": _turned(jointHardware(), Axis.Z, 180, x=kneeOutboardOffset),
        "thigh": _at(thighRight(), z=pose["upperLinkCenterZ"]),
        "shin": atShin(shinRight()),
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
    """One thigh with the actuator at each end of it, and the knee's bearing.

    THIS IS THE THIGH NOW, not the generic limb it used to be. The scene exists
    to look at one change narrowly, and the change is at this piece's lower end:
    a clevis straddling the knee motor with a 6800 bonded into its far cheek,
    where every limb on this robot had a flat plate. The shin still has that
    plate, and what holds it is a row in tools/gate_f.py against the wheel motor
    in the squat rather than a scene of its own.

    The hardware is back. It went when the clevises did, and the note that stood
    here said so; the knee has it again because the knee is straddled again.

    THE UPPER ACTUATOR IS HERE BECAUSE OF THE CABLE-TIE ARCHES. This scene held
    only the lower one while the limb was a plate and nothing stood off its
    faces: one joint was the whole of what there was to look at. The arches
    stand 4 mm proud of the inboard face at BOTH ends, on the same side as the
    actuators and 30.5 mm from each joint axis, so each of them has a Ø46 body
    to miss and tools/gate_f.py now measures both.
    """
    # The motor above is the hip's, and the thigh's disc is bolted to it, so it
    # has its threads and its six screws. The knee motor below has no shin on
    # it in this scene, so nothing is bolted to it and it is left plain.
    motorAbove, screwsAbove = boltedToOutput(
        _turned(actuatorAssembly(), Axis.Y, 90, z=upperLegLength / 2),
        thighRightOutput,
    )
    return {
        "limb": thighRight(),
        # The knee motor and its far bearing stand kneeOutboardOffset out along
        # the joint axis, because the fork does; the hip's actuator above does
        # not, because that end of the limb is a plate.
        "motor": _turned(
            actuatorAssembly(),
            Axis.Y,
            -90,
            x=kneeOutboardOffset,
            z=-upperLegLength / 2,
        ),
        "motor above": motorAbove,
        "screws above": screwsAbove,
        "hardware": _turned(
            jointHardware(), Axis.Z, 180, x=kneeOutboardOffset, z=-upperLegLength / 2
        ),
    }


def wheelModuleGroups() -> dict[str, list]:
    """One wheel motor and the wheel on it, on their own.

    The narrow scene to look at first: motor-to-tread clearance, how the hub lands
    on the output disc, and that the left/right mirror is the right way round.

    It does NOT show whether the six output holes are open, and never did -- the
    motor stands directly behind them, and structure behind a hole makes an open
    one look closed. tools/gate_e.py counts them on the solid instead.

    THE WHEEL IS FOUR GROUPS HERE, not one, since 6 October 2026: the adapter,
    the bought wheel, the printed cap and the clamp hardware. tools/gate_h.py
    measures groups against each other and never within one, so as a single
    group nothing ever asked whether the spigot stops short of the hub's ridge
    or the cap lands on it. This is the one scene that splits it; the stances
    keep each wheel whole, because what they look at is the wheel against the
    leg.
    """
    motor, screws = boltedToOutput(
        _turned(actuatorAssembly(), Axis.Y, 90), wheelRightOutput
    )
    return {
        "motor": motor,
        "output screws": screws,
        **wheelRightGroups(),
    }


def torsoPackingGroups() -> dict[str, list]:
    """The pelvis with its lid off and the four payload items standing in it.

    The 65 mm torso is sized by its contents rather than by a round number, so
    "does it fit" is a question about this scene and not about a table. From the
    bottom up -- the IMU stood first, on the shell floor between the two hip pitch
    saddles, until 2026-10-14, and hangs under the deck over the power bay now --
    the power-entry block and the controller carrier
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
