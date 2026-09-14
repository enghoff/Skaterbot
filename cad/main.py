"""The neutral 339 mm assembly of the six-motor wheeled robot.

Ported from the main.kcl that used to sit beside it. Each leg is hip pitch, knee pitch and a driven wheel --
six DM-J3507 actuators in total, on a robot that used to carry eight and stand
380 mm. Hip roll is gone: the hip pitch clevis is part of the pelvis now, rooted
in a shell floor that came down 51 mm to meet it, so nothing below the hip moved.
Thigh and shin are still 105 mm and the wheel axle is still 40 mm off the floor.

WHAT IS IN HERE THAT IS NOT PRINTED. The six actuators, the bearing and journal
that close each of the four straddled joints -- two hips and, since the knee was
given its second support, two knees -- and the four reserved payload volumes
standing in the pelvis. None of them is made here -- they are bought or
they are envelopes -- but the assembly is the place you find out whether they
collide with anything, so it places them. tools/mass.py counts them from
tools/mass_budget.toml's allowances rather than from this geometry.

The check scenes -- the crouch, the squat, the knee at its stop, the packing of
the torso -- are in cad/scenes.py, and they are the ones that catch interference
this neutral pose hides.
"""

from __future__ import annotations

from build123d import Axis, Pos

from cad.actuator import actuatorAssembly
from cad.deck import electronicsDeck
from cad.electronics import torsoPayload
from cad.hardware import jointHardware
from cad.parameters import hipCenterX, kneeOutboardOffset
from cad.shin import shinLeft, shinRight
from cad.thigh import thighLeft, thighRight
from cad.torso import torsoAssembly
from cad.wheel import wheelLeft, wheelRight
from cad.wheeled_parameters import (
    prototypeWheelAxisHeight,
    wheeledHipPitchAxisHeight,
    wheeledKneeAxisHeight,
    wheeledShinCenterZ,
    wheeledThighCenterZ,
    wheeledTorsoCenterHeight,
)


def _motor(x: float, z: float, spin: float) -> list:
    """One actuator, axis across the robot, at a joint station."""
    return [Pos(x, 0, z) * body.rotate(Axis.Y, spin) for body in actuatorAssembly()]


def robotAssembly() -> list:
    """Every body in the neutral standing pose, in the robot's own frame.

    +Y is forward, +Z is up, +X is the robot's right.
    """
    bodies: list = []

    # Six actuators, all with their axes across the robot. The hip roll pair,
    # which were the only two turned fore-and-aft, are what this build deleted.
    #
    # EVERYTHING FROM THE KNEE DOWN STANDS kneeOutboardOffset FURTHER OUT. The
    # knee is the only joint with a fork, and a 3 mm cheek held 0.3 mm off the
    # rear cover ends 2.7 mm inside the 6 mm plate every other joint lands, which
    # put a step in the side of the leg. The joint moves rather than the fork, so
    # the knee actuator and everything it carries -- shin, wheel motor, wheel --
    # share the offset and every printed part keeps its shape.
    kneeX = hipCenterX + kneeOutboardOffset
    bodies += _motor(-hipCenterX, wheeledHipPitchAxisHeight, -90)
    bodies += _motor(-kneeX, wheeledKneeAxisHeight, 90)
    bodies += _motor(-kneeX, prototypeWheelAxisHeight, -90)
    bodies += _motor(hipCenterX, wheeledHipPitchAxisHeight, 90)
    bodies += _motor(kneeX, wheeledKneeAxisHeight, -90)
    bodies += _motor(kneeX, prototypeWheelAxisHeight, 90)

    # There is no hip carrier. The clevis that holds each hip pitch actuator is
    # part of the pelvis now, so the printed chain from torso to wheel is torso,
    # thigh, shin, wheel adapter.
    bodies += [Pos(-hipCenterX, 0, wheeledThighCenterZ) * b for b in thighLeft()]
    bodies += [Pos(hipCenterX, 0, wheeledThighCenterZ) * b for b in thighRight()]
    bodies += [Pos(-kneeX, 0, wheeledShinCenterZ) * b for b in shinLeft()]
    bodies += [Pos(kneeX, 0, wheeledShinCenterZ) * b for b in shinRight()]
    bodies += [Pos(-kneeX, 0, prototypeWheelAxisHeight) * b for b in wheelLeft()]
    bodies += [Pos(kneeX, 0, prototypeWheelAxisHeight) * b for b in wheelRight()]

    # The bearing, journal and carrier that close the two hip pitch joints. Each
    # hangs off the stationary side, in the clevis rooted in the pelvis floor, and
    # the left one is the right one turned round.
    bodies += [
        Pos(-hipCenterX, 0, wheeledHipPitchAxisHeight) * body.rotate(Axis.Z, 180)
        for body in jointHardware()
    ]
    bodies += [
        Pos(hipCenterX, 0, wheeledHipPitchAxisHeight) * body for body in jointHardware()
    ]

    # AND THE SAME SET AT EACH KNEE, September 2026. The knee carries the shin,
    # the wheel motor, the adapter and the wheel on a plate 22 mm off its axis,
    # which is the largest overhung moment on the robot and the one DAMIAO have
    # never answered for; so the thigh's lower end is a clevis now and there is a
    # second bearing on the far side of it. Four bearing-journal sets rather than
    # two.
    #
    # THE HANDS ARE THE OTHER WAY ROUND FROM THE HIPS, and that is the knee motor
    # being turned round rather than anything about the hardware: the right hip's
    # bearing is outboard at +x and the right knee's is inboard at -x, so it is
    # the LEFT knee that takes the set as drawn.
    bodies += [Pos(-kneeX, 0, wheeledKneeAxisHeight) * body for body in jointHardware()]
    bodies += [
        Pos(kneeX, 0, wheeledKneeAxisHeight) * body.rotate(Axis.Z, 180)
        for body in jointHardware()
    ]

    bodies += [Pos(0, 0, wheeledTorsoCenterHeight) * b for b in torsoAssembly()]
    bodies += [Pos(0, 0, wheeledTorsoCenterHeight) * b for b in electronicsDeck()]
    # The payload: each board, and the volume reserved around it that nothing may
    # be designed through. The torso's height is derived from these.
    bodies += [Pos(0, 0, wheeledTorsoCenterHeight) * b for b in torsoPayload()]
    return bodies
