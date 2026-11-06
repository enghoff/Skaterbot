"""Driving and turning as fast as the motors allow, on the robot as it drove.

A fine-tune of the driving policy (`rough-2026-11-04_09-01-34_measured_fix`, whose
25 inputs and 6 outputs this keeps, so the firmware and sbc/policy_loop.py need nothing
new) from what its first runs on the floor found on 5 November 2026, in docs/SYSID.md:

  * THE WHEELS' FRICTION ON THE FLOOR, about three times what the rail measured in the
    air. Near standstill the policy and the friction rock the robot at 1 Hz.
  * ITS ANSWER TO A CHANGE OF COMMAND. Held steady it is as calm as MuJoCo; each move of
    a trigger or the stick swings it 3 to 6 degrees, ringing at 1.56 Hz for 2 to 3 s. A
    longer delay in training, and a cost on pitching, ask for a better-damped answer.
    Commands now arrive at a limited rate, as the robot's operator gives them.
  * TRACKING. On an arc of 0.5 m/s and 1.5 rad/s it did 0.67 m/s and 2.0 rad/s. A tracking
    reward as wide as this task's pays half for that, so errors are charged in proportion.
  * THE RIDE HEIGHT, which the policy ignores: over all of its 22 mm range the legs move
    3 mm in MuJoCo. Charged in proportion, as stages 9 and `mergeheight` found it has to be.
  * THE SCISSOR. It stands with its hips 7 degrees apart and one wheel 25 mm ahead of the
    other, in MuJoCo as on the robot. Nothing asks otherwise: the cost on unequal legs is
    off in the rough task and the stagger's is too small to notice at that size.

And it opens the commands out to what the motors allow, as stage 5 of the jump chain did:
evenly over the diamond |speed| / top + |turn| / top <= 1, half of them everyday ones,
and opening from a quarter over 1 500 iterations. Stage 5 keeps the reasons for those.

Fine-tuned from that policy's checkpoint it kept its stance and its lean to one side, and
turned twice as fast one way as the other, so it is trained from nothing instead:
agent.py's WheeledBipedDriveFreshPPORunnerCfg says why.
"""

from __future__ import annotations

from isaaclab.utils.configclass import configclass

from .env_cfg import (
    ARMATURE_KG_M2,
    LEG_DAMPING_NM_S_RAD,
    LEG_STIFFNESS_NM_RAD,
    MAX_VELOCITY_RAD_S,
    PEAK_TORQUE_NM,
    plant,
)
from .friction_actuator import FrictionDCMotorCfg
from .rough_env_cfg import (
    MEASURED,
    WheeledBipedRoughEnvCfg,
)

# UNMEASURED. The vendor's manual says 48.2 rad/s with no load. The owner expects these
# motors to reach 50 to 60, so that is the range drawn from, about this middle, and what
# the robot does reach is still to be measured: a wheel spun in the air, torque against
# speed. A report's speed wraps at the motors' VMAX of 55, and sbc/policy_loop.py stops
# at 50, so the robot cannot go past that until VMAX is raised.
TOP_WHEEL_RAD_S = 55.0
MOTOR_SPREAD = (50.0 / TOP_WHEEL_RAD_S, 60.0 / TOP_WHEEL_RAD_S)

TOP_SPEED_M_S = TOP_WHEEL_RAD_S * plant.wheel_radius_m()
TOP_YAW_RATE_RAD_S = 2.0 * TOP_SPEED_M_S / plant.geometry()["track_m"]

DRIVE_ACTUATORS = {
    "legs": FrictionDCMotorCfg(
        joint_names_expr=["hip_pitch_.*", "knee_.*"],
        effort_limit=PEAK_TORQUE_NM,
        saturation_effort=PEAK_TORQUE_NM,
        velocity_limit=MAX_VELOCITY_RAD_S,
        stiffness=LEG_STIFFNESS_NM_RAD,
        damping=LEG_DAMPING_NM_S_RAD,
        friction=0.0,
        armature=ARMATURE_KG_M2,
        coulomb_nm=MEASURED["leg_coulomb_nm"],
        viscous_nm_s_rad=MEASURED["leg_viscous_nm_s_rad"],
    ),
    "wheels": FrictionDCMotorCfg(
        joint_names_expr=["wheel_drive_.*"],
        effort_limit=PEAK_TORQUE_NM,
        saturation_effort=PEAK_TORQUE_NM,
        velocity_limit=TOP_WHEEL_RAD_S,
        stiffness=0.0,
        damping=0.0,
        friction=0.0,
        armature=MEASURED["wheel_armature_kg_m2"],
        coulomb_nm=plant.ON_THE_FLOOR["wheel_coulomb_nm"],
        viscous_nm_s_rad=plant.ON_THE_FLOOR["wheel_viscous_nm_s_rad"],
        static_nm=plant.ON_THE_FLOOR["wheel_static_nm"],
        # A sharper turnover would chatter at the higher friction: 0.07 Nm over 0.3
        # rad/s on a wheel at half its armature, in a 2.5 ms step, is 1.3, under 2.
        coulomb_speed_rad_s=0.3,
    ),
}


@configclass
class WheeledBipedDriveEnvCfg(WheeledBipedRoughEnvCfg):
    robot = WheeledBipedRoughEnvCfg().robot.replace(actuators=DRIVE_ACTUATORS)

    # The torso's reading later than the 16 ms measured, to the 28 ms that also stands
    # for a command about 15 ms late rather than the 10 this task's steps can draw: the
    # wheels' torque follows the logged command by 18 to 20 ms.
    imu_delay_steps = plant.ON_THE_FLOOR["imu_delay_steps"]

    battery_speed_scale = MOTOR_SPREAD

    # -- the drive command, to the motors' envelope
    command_lin_vel_x = (-TOP_SPEED_M_S, TOP_SPEED_M_S)
    command_yaw_rate = (-TOP_YAW_RATE_RAD_S, TOP_YAW_RATE_RAD_S)
    command_tracking_relative = 0.2
    command_everyday_fraction = 0.5
    command_everyday_lin_vel_x = (-0.5, 0.5)
    command_everyday_yaw_rate = (-1.5, 1.5)
    command_envelope_start = 0.25
    # 24 policy steps an iteration, so 1 500 iterations.
    command_envelope_ramp_steps = 36_000
    # What is asked moves towards a new command no faster than this, and starts each
    # episode from a standstill: the robot's operator does the same, more gently, and
    # at the top of this range a step of the command is more than anything can follow.
    command_slew_m_s2 = 1.5
    command_slew_rad_s2 = 8.0

    # -- the ride height: 37 mm, as far down as the knee's 0.8 rad of action reaches
    command_leg_height_m = (0.170, 0.207)
    rew_leg_height_error = -300.0

    # -- tracking, in proportion as well as by the kernel
    rew_lin_vel_error = -3.0
    rew_yaw_rate_error = -0.5

    # -- symmetry. Unequal legs are how it levels itself across a slope, and with these
    # it will lean more and level less there: a price paid on purpose, for a robot that
    # mostly drives on the flat. They are costs and not rules, so it still can.
    rew_leg_asymmetry = -5.0
    rew_wheel_stagger = -200.0

    # -- the torso upright. On the robot it stood 8 degrees back and turned at up to 18,
    # which at the -5 before this cost next to nothing. The legs can do it: one fine-tune
    # stood 2 degrees back without being asked to. And it has to lean to
    # accelerate, 6 degrees to 1 m/s2, so this is a cost and not a rule.
    rew_upright = -30.0

    # -- a better-damped answer, and a stiller stand
    rew_ang_vel_xy = -0.2
    rew_stand_still = 1.0

    # A robot this close to the field's edge is reset, as a time-out: at top speed one
    # crosses half the field in an episode.
    edge_margin_m = 2.0
