"""The jump task on the robot as measured, jumping as high as it is asked.

Every jump policy so far was trained before the robot was measured, and the driving
policy trained in September stood 96 % of the time on its own model and 45 % on the
measured one (TRAINING_HISTORY.md). So this is the jump task with the robot the
driving policy now drives on:

  * THE MOTORS' MEASURED CURVE (plant.MOTOR_CURVE), legs and wheels, and the battery
    around the 24.8 V it was measured at;
  * THE FLOOR'S WHEEL FRICTION AND THE DELAYS the robot showed driving
    (plant.ON_THE_FLOOR, plant.MEASURED), where the jump task kept September's guesses;

and two changes for putting a jump on the robot at all:

  * A JUMP AS HIGH AS ASKED, 20 to 120 mm (jump_score_to_target), so the first ones on
    the robot can be small and the height raised as they land well;
  * THE LEGS' GAINS HELD TO TWICE AND HALF the driving policy's 12 Nm/rad and
    0.4 Nm s/rad, where the jump task allowed four times: on the robot, gains above 12
    set the hips buzzing at 39 Hz (docs/SYSID.md). 12 Nm/rad on the 1.2 rad of a knee's
    action is 14 Nm asked, past the 3 Nm the motor has, so a push does not need more.

The rest is the candidate jump policy's own task, jumpsym300 (TRAINING_HISTORY.md),
whose run overrode the class's defaults on the command line; they are set here.
"""

from __future__ import annotations

from isaaclab.utils.configclass import configclass

from .drive_env_cfg import (
    D6_LEG_ACTUATORS,
    DRIVE_ACTUATORS,
    MEASURED_BATTERY,
    measured_curve,
)
from .env_cfg import plant
from .jump_env_cfg import WheeledBipedJumpEnvCfg
from .rough_env_cfg import MEASURED


@configclass
class WheeledBipedJumpMeasuredEnvCfg(WheeledBipedJumpEnvCfg):
    robot = WheeledBipedJumpEnvCfg().robot.replace(
        actuators=measured_curve(DRIVE_ACTUATORS)
    )
    imu_delay_steps = plant.ON_THE_FLOOR["imu_delay_steps"]
    joint_delay_steps = MEASURED["joint_delay_steps"]
    action_delay_steps = MEASURED["action_delay_steps"]
    battery_speed_scale = MEASURED_BATTERY

    # -- driving: the jump policy only has the robot below about 1 m/s, where the
    # driving policy hands it over (POLICY_INTERFACE.md, two policies)
    command_lin_vel_x = (-1.2, 1.2)
    command_yaw_rate = (-4.0, 4.0)
    command_envelope_start = 1.0

    # -- jumpsym300's overrides
    rew_leg_height_error = -1000.0
    rew_jump_height = 1000.0
    rew_jump_pitch = -400.0
    jump_crouch_s = 0.6
    rew_jump_stagger = -300.0
    rew_jump_heading = -50.0
    rew_jump_leg_asymmetry = -300.0

    # -- as high as asked
    jump_clearance_m = (0.02, 0.12)
    jump_score_to_target = True
    jump_com_share = 0.6
    rew_jump_overshoot = -1000.0

    # -- gains no further than twice or half the driving policy's
    leg_gain_range = 2.0


@configclass
class WheeledBipedJumpLagEnvCfg(WheeledBipedJumpMeasuredEnvCfg):
    """The jump task with the motors' torque as late as the robot's.

    jm_smooth, trained on the task above, shook on the robot on 6 November 2026: its
    wheels reversed 29-55 times in each 0.6 s jump, against 13-17 in MuJoCo, answering
    a torso shaking at 11-22 Hz. That shake is driven through the legs, whose torque
    the robot makes through an 8-12 ms lag on what their position loop asks
    (plant.LEG_RESPONSE), as its wheels make theirs through 5-20 ms
    (plant.WHEEL_RESPONSE); this task had neither. D6's actuators have both, and the
    wheels' friction as they drove. With the wheels' lag in, the IMU's delay is the
    measured one again, not the longer one that stood in for it, as in D6. And
    jm_smooth's own override, the cost on jerky commands kept through the jump.
    """

    robot = WheeledBipedJumpEnvCfg().robot.replace(actuators=D6_LEG_ACTUATORS)
    imu_delay_steps = MEASURED["imu_delay_steps"]
    jump_action_rate_scale = 1.0
