"""The poses the check scenes stand in, as numbers rather than as pictures.

Ported from pose_check.kcl, squat_check.kcl, knee_limit_check.kcl and
knee_prelimit_check.kcl. Each of those scenes worked out a pose from the robot's
dimensions -- a hip angle, where the knee and the axle land, how far the torso
drops -- and then placed bodies at it. This module is the first half of that, and
cad/scenes.py is the second.

WHY THE SPLIT IS HERE AND NOT INSIDE THE SCENES. Two things need these numbers
and only one of them wants geometry. simulation/check_model.py drives the joint
tree to a scene's angles and requires the wheel to land where the scene
independently says it should, which is the strongest regression test in the
project and needs no solids at all; cad/scenes.py needs the same numbers to stand
parts at. Computing them once, here, is what keeps those two from drifting apart.

WHY EACH SCENE IS A FUNCTION RETURNING A DICT. The scenes reuse names -- both
knee checks have an `upperLinkCenterZ`, and `kneeY` means one thing in the squat
and nothing in the pose check -- so a module full of constants would have to
rename half of them, and the frozen reference they are checked against is keyed
by the KCL's own names. A dict per scene keeps every name exactly as the engine
knew it.

WHAT PINS THEM. reference/golden/scenes.json is what the KCL computed for these
same poses, frozen before it was deleted, and tools/gate_f.py compares against it
name by name at zero tolerance. So the tree comes out of cad/parameters.py, the
pose comes out of here, and both are held against a reference neither had a hand
in.

Angles are degrees and lengths are millimetres, in the robot's own frame: +Y
forward, +Z up, +X the robot's right.
"""

from __future__ import annotations

from math import cos, radians, sin

from cad.parameters import lowerLegLength, upperLegLength
from cad.wheeled_parameters import (
    wheeledHipPitchAxisHeight,
    wheeledTorsoCenterHeight,
)

# HOW FAR THE KNEE MAY FOLD, and it is geometry again rather than a number
# inherited from the walking robot.
#
# 110 degrees was a commissioning recommendation carried over from the machine
# this one descends from, and for a year nothing on the leg argued with it: the
# flat limbs put thigh and shin in disjoint planes on either side of the knee
# actuator, so the fold had no structural limit at all and 110 was simply where
# the number had always been.
#
# Straddling the knee ends that, necessarily and not by oversight. A second
# bearing on the far side of an actuator means reaching around it, and the thing
# that reaches is the clevis's saddle -- a closed box spanning the joint 24 to
# 36 mm above the axis, which is squarely in the plane the shin sweeps. The shin
# is a 40 mm plate whose top corners stand 24.4 mm from the knee axis, so as the
# leg folds they rise into the saddle's floor: measured, they touch at 103.0
# degrees and share 62 mm3 at 110.
#
# 100 is where the gap between them is exactly 1.0 mm, which is also the air
# between the shin's rotor disc and the far cheek -- so at this angle the fold
# is no tighter than the joint's own assembly clearance, and tools/gate_f.py
# holds both with one margin. Three degrees of the fold are given away to reach
# it and the squat is 14.5 mm shallower for it; docs/NOTES.md carries what that
# was weighed against.
kneeCommissioningStop = 100.0


def _leg(hipPitchZ: float, hipAngle: float, shinAngle: float) -> dict[str, float]:
    """Where one leg's knee, axle and two link centres land, from two angles.

    The chain is hip pitch, knee, wheel, with nothing between the knee and the
    axle but the shin -- which is why a wheeled leg is two angles where the
    walking one was four. Both angles are measured from straight down and are
    positive forward, so a positive hip swings the thigh's lower end towards +Y.
    """
    kneeY = upperLegLength * sin(radians(hipAngle))
    kneeZ = hipPitchZ - upperLegLength * cos(radians(hipAngle))
    wheelY = kneeY + lowerLegLength * sin(radians(shinAngle))
    wheelZ = kneeZ - lowerLegLength * cos(radians(shinAngle))
    return {
        "kneeY": kneeY,
        "kneeZ": kneeZ,
        "wheelY": wheelY,
        "wheelZ": wheelZ,
        "thighCenterY": kneeY / 2,
        "thighCenterZ": (hipPitchZ + kneeZ) / 2,
        "shinCenterY": (kneeY + wheelY) / 2,
        "shinCenterZ": (kneeZ + wheelZ) / 2,
    }


def pose_check() -> dict[str, float]:
    """Crouched stance with the right wheel lifted.

    The hip and knee angles are exactly the ones the walking pose check used, so
    the clearance figures stay comparable across the two architectures; what has
    gone is the ankle at the bottom of the leg and hip roll at the top.

    The standing leg's axle lands at exactly 40 mm, which is the wheel's own
    radius, so the left wheel is tangent to the floor and the drop is real rather
    than drawn. The lifted leg clears the ground by about 27 mm.
    """
    leftHipAngle = -6.0
    leftKneeAngle = 12.0
    leftShinAngle = leftHipAngle - leftKneeAngle

    rightHipAngle = 35.0
    rightKneeAngle = 65.0
    rightShinAngle = rightHipAngle - rightKneeAngle

    # The whole robot drops by however much the standing leg has shortened, which
    # is what keeps its axle on the floor rather than through it.
    leftLegVerticalReach = upperLegLength * cos(radians(leftHipAngle)) + (
        lowerLegLength * cos(radians(leftShinAngle))
    )
    crouchDrop = upperLegLength + lowerLegLength - leftLegVerticalReach
    poseHipPitchZ = wheeledHipPitchAxisHeight - crouchDrop

    left = _leg(poseHipPitchZ, leftHipAngle, leftShinAngle)
    right = _leg(poseHipPitchZ, rightHipAngle, rightShinAngle)

    scene = {
        "leftHipAngle": leftHipAngle,
        "leftKneeAngle": leftKneeAngle,
        "leftShinAngle": leftShinAngle,
        "rightHipAngle": rightHipAngle,
        "rightKneeAngle": rightKneeAngle,
        "rightShinAngle": rightShinAngle,
        "leftLegVerticalReach": leftLegVerticalReach,
        "crouchDrop": crouchDrop,
        "poseHipPitchZ": poseHipPitchZ,
        "poseTorsoCenterZ": wheeledTorsoCenterHeight - crouchDrop,
    }
    for hand, leg in (("left", left), ("right", right)):
        for name, value in leg.items():
            scene[hand + name[0].upper() + name[1:]] = value
    return scene


def squat_check() -> dict[str, float]:
    """The deepest squat the knee stop allows, both wheels still on the ground.

    Two things set the pose and between them they leave no freedom: the knee
    cannot pass its commissioning stop, and both axles have to stay at 40 mm or
    the wheels are not on the floor. Making the squat symmetric, so each axle sits
    under its own hip rather than thrown fore or aft, then fixes the hip at half
    the knee angle.

    It costs 75.0 mm of height -- the robot stands 264 mm instead of 339 -- and
    brings the knees 80 mm forward of the hip axis, which is the number to watch,
    because that is where the payload envelope and the knee actuators have to miss
    each other.
    """
    squatKneeAngle = kneeCommissioningStop
    squatHipAngle = squatKneeAngle / 2
    squatShinAngle = squatHipAngle - squatKneeAngle

    legVerticalReach = upperLegLength * cos(radians(squatHipAngle)) + (
        lowerLegLength * cos(radians(squatShinAngle))
    )
    squatDrop = upperLegLength + lowerLegLength - legVerticalReach
    squatHipPitchZ = wheeledHipPitchAxisHeight - squatDrop

    scene = {
        "squatKneeAngle": squatKneeAngle,
        "squatHipAngle": squatHipAngle,
        "squatShinAngle": squatShinAngle,
        "legVerticalReach": legVerticalReach,
        "squatDrop": squatDrop,
        "squatHipPitchZ": squatHipPitchZ,
        "squatTorsoCenterZ": wheeledTorsoCenterHeight - squatDrop,
    }
    # Symmetric, so one leg is the whole scene and both sides are placed from it.
    scene.update(_leg(squatHipPitchZ, squatHipAngle, squatShinAngle))
    return scene


def _knee_review(kneeAngle: float) -> dict[str, float]:
    """A thigh held upright with the shin folded under it by one angle.

    Not a stance -- the robot is not standing on anything here. It is the knee
    joint on its own, so the shin's stator plate can be checked against the
    thigh's, and both links are placed about the knee axis at the origin.
    """
    shinAngle = -kneeAngle
    return {
        "shinAngle": shinAngle,
        "upperLinkCenterZ": upperLegLength / 2,
        "lowerLinkCenterY": lowerLegLength / 2 * sin(radians(shinAngle)),
        "lowerLinkCenterZ": -lowerLegLength / 2 * cos(radians(shinAngle)),
    }


def knee_limit_check() -> dict[str, float]:
    """The knee at its commissioning hard stop, which is a measured angle now."""
    kneeLimitAngle = kneeCommissioningStop
    review = _knee_review(kneeLimitAngle)
    return {
        "kneeLimitAngle": kneeLimitAngle,
        "shinLimitAngle": review["shinAngle"],
        "upperLinkCenterZ": review["upperLinkCenterZ"],
        "lowerLinkCenterY": review["lowerLinkCenterY"],
        "lowerLinkCenterZ": review["lowerLinkCenterZ"],
    }


def knee_prelimit_check() -> dict[str, float]:
    """The same knee ten degrees short of the stop, for a look before contact."""
    kneePreLimitAngle = kneeCommissioningStop - 10.0
    review = _knee_review(kneePreLimitAngle)
    return {
        "kneePreLimitAngle": kneePreLimitAngle,
        "shinPreLimitAngle": review["shinAngle"],
        "upperLinkCenterZ": review["upperLinkCenterZ"],
        "lowerLinkCenterY": review["lowerLinkCenterY"],
        "lowerLinkCenterZ": review["lowerLinkCenterZ"],
    }


# The scenes that compute a pose. The three that only place bodies -- the torso
# packing check, the limb review and the wheel module -- define no constants of
# their own and so appear in cad/scenes.py alone.
SCENES = {
    "pose_check": pose_check,
    "squat_check": squat_check,
    "knee_limit_check": knee_limit_check,
    "knee_prelimit_check": knee_prelimit_check,
}
