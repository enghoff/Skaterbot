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
    D8_ACTUATORS,
    DRIVE_ACTUATORS,
    MEASURED_BATTERY,
    D6EventCfg,
    WheeledBipedDriveD8EnvCfg,
    measured_curve,
)
from .env_cfg import plant
from .jump_env_cfg import WheeledBipedJumpEnvCfg, roll_mode
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


# D8's task as it stands, for its plant: the driving policy on the robot since 7 November
# 2026, which hands each jump over and takes it back.
D8_TASK = WheeledBipedDriveD8EnvCfg()


@configclass
class WheeledBipedJumpD8EnvCfg(WheeledBipedJumpLagEnvCfg):
    """jl_lag's jump task on D8's plant, with the robot's roll answer to its knees.

    Every jump on the robot failed, eleven by three policies on 6 and 7 November 2026,
    while every one in MuJoCo passed (session scratchpad jumpwhy/). Two things this task
    had wrong:

      * THE ROLL LOOP (simulation/roll_mode.py). A fast change in the knees' target
        difference rolls the robot's torso about 10 rad/s per rad at 25 Hz, 15 ms after
        it is sent, where the rigid model rolls a fortieth of that; the jump policy
        answers the roll rate with more knee difference 10 ms later, and around the
        loop that is 20-25 Hz positive feedback. Its knee targets chatter 0.27-0.46 rad
        a step, the push-off is cut short, and it tips over backwards 0.7 s after the
        trigger. MuJoCo with the mode in the IMU's readings does the same
        (simulation/mujoco/jump_roll_check.py fails jl_lag on every seed with it, and
        passes it on every seed without). Here the mode is drawn per robot per episode
        about the robot's fit, the whole episode, driving and jumping alike, and the
        policy reads it as the robot's IMU does.
      * THE PLANT. jl_lag was trained before the motors were measured on 7 November:
        it never met a wheel inertia under 4.2e-4 kg m2, a wheel making more torque than
        asked, legs later than 14 ms or an IMU later than 20 ms. D8, which drives the
        robot now, was trained on plant.SHAKE and plant.SWAY; this is D8's plant exactly
        as D8 draws it, from D8's own objects: its actuators (the wheel's 3e-4 kg m2,
        which every task's armature event then scales by 0.5-2, the wheels' torque
        0.7-1.3 of asked through 10-20 ms, the legs' 0.95-1.2 through 12-20 ms after
        their position loop), its events (the torso's centre of mass 10 mm either way),
        its delays (the IMU 12.5 to 40 ms), the IMU's zero 2 degrees either way, its
        sensor noise and its battery.

    Everything else is jl_lag's task, and its 29 inputs and 8 outputs, so jl_lag's
    checkpoint resumes into it as it is.
    """

    robot = WheeledBipedJumpEnvCfg().robot.replace(actuators=D8_ACTUATORS)
    events: D6EventCfg = D6EventCfg()
    imu_delay_steps = D8_TASK.imu_delay_steps
    joint_delay_steps = D8_TASK.joint_delay_steps
    action_delay_steps = D8_TASK.action_delay_steps
    delay_jitter_prob = D8_TASK.delay_jitter_prob
    command_drop_prob = D8_TASK.command_drop_prob
    imu_tilt_deg = D8_TASK.imu_tilt_deg
    sensor_noise_std = D8_TASK.sensor_noise_std
    sensor_bias_std = D8_TASK.sensor_bias_std
    battery_speed_scale = D8_TASK.battery_speed_scale

    # -- the roll mode, drawn about the robot's fit (roll_mode.DRAWN)
    roll_mode_gain = roll_mode.DRAWN["gain_rad_s_per_rad"]
    roll_mode_hz = roll_mode.DRAWN["hz"]
    roll_mode_zeta = roll_mode.DRAWN["zeta"]
    roll_mode_delay_steps = roll_mode.delay_steps(
        roll_mode.DRAWN["delay_s"], plant.PHYSICS_DT
    )

    # -- and charged. Against what a jump earns: about 70 for 30 mm, once (clearance at
    # 1000 per metre, the centre of mass's rise at 2000 to 0.6 of it, and the take-off's
    # 5). Against what chatter buys: answering roll rate holds the torso level if the
    # roll is real, which the roll cost (-200 per gravity's y squared, a second) prices
    # at 1.5 a second for 5 degrees, about 1 over a 0.6 s jump. And against jl_lag in
    # MuJoCo: with the loop its knee targets move 0.28-0.40 rad a step, their difference
    # 0.5-1.0 rad rms a step, and the roll rate seen is 2.2-3.9 rad/s rms; without it
    # 0.15-0.17 a step, the difference 0.13-0.14, the roll 0.5-0.8.
    #
    # Per rad squared of the difference's change a step, charged a second as every rate
    # is: chatter of 0.3 rad a step costs 18 a second, 11 a jump, ten times what it buys;
    # jl_lag's 0.5-1.0 costs 50-200 a second, as much as the jump earns or more. A jump
    # as jl_lag makes one without the loop pays 2 for the whole of it, and driving,
    # hundredths of a radian a step, nothing.
    rew_knee_difference_rate = -200.0
    # Per (rad/s) squared of the mode's rate: 0.3 rad a step of difference at 25 Hz
    # rings the robot's mode at 2.3 rad/s rms, 26 a second, 16 a jump; jl_lag's 2.2-3.9,
    # 24-76 a second. A calm jump's 0.5, about 1 a second. The mode is the robot rolling,
    # so this is a cost on rolling that the policy can only lower by leaving the knees
    # alone at 20-30 Hz, which is the point.
    rew_roll_mode_rate = -5.0
