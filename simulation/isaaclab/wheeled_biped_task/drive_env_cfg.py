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

import isaaclab.envs.mdp as mdp
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import SceneEntityCfg
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
    RoughEventCfg,
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
    # The ride height, m/s; nothing, a new height asked at once.
    command_slew_height_m_s = 0.0

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


# -- the motors as measured (plant.MOTOR_CURVE, 6 November 2026), legs and wheels alike:
# full torque to about 22 rad/s, then falling to nothing at 55. The battery's spread is
# around that pack's 24.8 V: full is 25.2, and the robot is run down to about 20.
CURVE = plant.MOTOR_CURVE
MEASURED_BATTERY = (0.8, 1.02)


def measured_curve(actuators: dict) -> dict:
    """These actuators with the measured torque-speed line in place of the rated one."""
    return {
        name: act.replace(
            saturation_effort=CURVE["saturation_nm"],
            velocity_limit=CURVE["no_load_rad_s"],
        )
        for name, act in actuators.items()
    }


@configclass
class WheeledBipedDriveMeasuredEnvCfg(WheeledBipedDriveEnvCfg):
    """D3's task on the measured motors, to fine-tune D3 on: at 40 rad/s the rated line
    allowed 0.5 Nm where the motor gives 1.2-1.4, so D3 learned to drive a weaker robot
    than it has. Its envelope, already open, is kept open."""

    robot = WheeledBipedDriveEnvCfg().robot.replace(
        actuators=measured_curve(DRIVE_ACTUATORS)
    )
    battery_speed_scale = MEASURED_BATTERY
    command_envelope_start = 1.0


@configclass
class WheeledBipedDriveLowEnvCfg(WheeledBipedDriveMeasuredEnvCfg):
    """D4's task, down to a 155 mm ride height where it stopped at 170.

    The knee's 0.8 rad of action about the crouch's 0.5 reached 1.3 rad and 170 mm, and
    no lower. The owner's limit is the shin 90 degrees forward, which the robot's window
    puts at 1.55 rad (sbc/sysid_tests.py's WINDOWS); the knee's action is now 1.0 rad,
    to 1.5, and the hip's 0.5, to 0.75, so that the wheel can stay under the hip at the
    bottom: 2 x 0.105 m x cos 0.75 is 154 mm. The other way the knee reaches -0.5,
    which the URDF's own limit holds at 0, inside the window's -0.35, so
    sbc/pack_policy.py takes it as it takes D3.

    On the robot on 2026-11-06 D3 stood at 170 mm rocking at 1.5 Hz, five times the
    pitch rate it stands with at 205, and calm driving there; training's evaluation saw
    the same, 16-17 degrees of rock at 170-180 mm against 10 above 190.
    """

    leg_action_scale_rad = (0.5, 1.0, 0.5, 1.0)
    command_leg_height_m = (0.155, 0.207)


# -- D6: the robot as its driving on 6 November 2026 showed it (plant.py, after
# MOTOR_CURVE): the wheels' torque late and short, their friction at speed, the IMU's zero
# and the torso's centre of mass unsure, and the IMU's own 16 ms back in place of the
# longer delay that stood in for the wheels' lag.

D6_ACTUATORS = measured_curve(DRIVE_ACTUATORS)
D6_ACTUATORS["wheels"] = D6_ACTUATORS["wheels"].replace(
    coulomb_nm=plant.ON_THE_FLOOR_DRIVING["wheel_coulomb_nm"],
    viscous_nm_s_rad=plant.ON_THE_FLOOR_DRIVING["wheel_viscous_nm_s_rad"],
    static_nm=plant.ON_THE_FLOOR_DRIVING["wheel_static_nm"],
    torque_lag_s=plant.WHEEL_RESPONSE["lag_s"],
    torque_gain=plant.WHEEL_RESPONSE["gain"],
    step_s=plant.PHYSICS_DT,
)


@configclass
class D6EventCfg(RoughEventCfg):
    # The torso's centre of mass fore and aft, drawn again each episode from the
    # model's own (randomize_rigid_body_com starts from the default every time).
    torso_com = EventTerm(
        func=mdp.randomize_rigid_body_com,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="base_link"),
            "com_range": {"x": plant.TORSO_COM_X_M},
        },
    )
    # A place for what is found next: a further randomisation of the robot as it
    # drives goes here, with its provenance in plant.py.


@configclass
class WheeledBipedDriveD6EnvCfg(WheeledBipedDriveLowEnvCfg):
    """D5's task on the robot as it drove on 6 November 2026, and kept off the end of
    the legs' reach.

    D5 (d5_low_calm) stood in MuJoCo at 155 mm and fell on the robot there, and taken
    over with the height already at 155 pitched 13-21 degrees nose-down with the wheels
    at their 55 rad/s within half a second. Three things the task had wrong:

      * THE WHEELS' TORQUE (plant.WHEEL_RESPONSE): late and short, 5-20 ms of lag at
        0.75-1.0 of what is asked, drawn per episode. The IMU's delay is the measured
        12.5-20 ms again (plant.MEASURED), no longer stretched to 27.5 to stand in for
        it: the stand-in rocked at 2.5 Hz where the robot rocks at 1.5. The command's
        own 2.5-10 ms (MEASURED's action delay, inherited) covers the fit's 4-8.
      * THE ROBOT'S BALANCE POINT: the IMU's zero up to 2 degrees either way in pitch
        and in roll, and the torso's centre of mass 10 mm fore or aft, per episode
        (plant.IMU_TILT_DEG, TORSO_COM_X_M). The robot's IMU read 3 degrees nose-down,
        and D3 drove 25 per cent slow forward and fell braking with 1.2 the other way.
      * THE WHEELS' FRICTION at speed, 0.03 Nm and 0.002 Nm s/rad
        (plant.ON_THE_FLOOR_DRIVING), the low end of what the tasks drew.

    And two of the task's own making:

      * THE HEIGHT ASKED AT ONCE. Each episode started at the crouch, 204 mm, with the
        ride height anywhere from 155, so D5 learned to fold 0.85 rad of knee in 0.15 s;
        under a hand still on the torso that lifted the wheels. The height now moves at
        50 mm/s, twice the controller's D-pad, and each episode starts from the crouch's.
      * THE FLOOR AT THE CORNER OF THE ACTION. At 155 mm D5's hip sat at +0.49 of its
        0.5 and its knee at +0.99 of 1.0, leaving the wheels alone to balance; D3 at 170
        did the same with 0.4 and 0.8. The floor is 165 mm, where the knee needs 1.33 rad
        of its 1.5 (sbc/sysid_tests.py's window stops it at 1.55, the shin 90 degrees
        forward), and the hip's action is 0.6, to 0.85 of its window's 0.9, where 165
        needs 0.67.

    The cost on pitching and rolling is d5_low_calm's, three times D5's.

    And the legs kept off the end of their action (rew_leg_action_reserve), since the
    range alone does not stop a policy pinning them. D3 on the robot on the evening of 6
    November, the IMU levelled: at 170 mm both hips' actions at their end (95th
    percentile 1.00) and both knees' at 0.92, where at 207 all four sit at 0.15-0.30;
    standing still it pitched at 0.25-0.6 rad/s RMS there against 0.07-0.12 at 207, and
    driving at 1.0-1.7 m/s at 0.31-0.41 against 0.22-0.25. In MuJoCo on the robot's loop
    with the wheels' lag D3 standing pitches at 0.74, 0.67, 0.53, 0.33, 0.18 and 0.09 rad/s
    at 170, 175, 180, 185, 190 and 207 mm, its hips pinned at every height to 185. The
    cost starts at 0.9 of a leg's action: 165 mm needs 0.7 of the hip's and 0.83 of the
    knee's, so it holds nothing back that the floor needs.
    """

    robot = WheeledBipedDriveEnvCfg().robot.replace(actuators=D6_ACTUATORS)
    events: D6EventCfg = D6EventCfg()

    imu_delay_steps = MEASURED["imu_delay_steps"]
    imu_tilt_deg = (plant.IMU_TILT_DEG["pitch"], plant.IMU_TILT_DEG["roll"])

    leg_action_scale_rad = (0.6, 1.0, 0.6, 1.0)
    command_leg_height_m = (0.165, 0.207)
    command_slew_height_m_s = 0.05

    rew_ang_vel_xy = -0.6
    # Both hips pinned at 1.0, 0.02 of squared excess, cost 1 a second: twice what
    # standing up earns.
    rew_leg_action_reserve = -50.0


# The legs' torque late as well as the wheels' (plant.LEG_RESPONSE): the lag on what the
# legs' position loop asks for, after the motor's limit.
D6_LEG_ACTUATORS = dict(D6_ACTUATORS)
D6_LEG_ACTUATORS["legs"] = D6_ACTUATORS["legs"].replace(
    torque_lag_s=plant.LEG_RESPONSE["lag_s"],
    torque_gain=plant.LEG_RESPONSE["gain"],
    step_s=plant.PHYSICS_DT,
    lag_after_pd=True,
)


@configclass
class WheeledBipedDriveD6LegsEnvCfg(WheeledBipedDriveD6EnvCfg):
    """D6's task with the legs' torque as late as the robot's (plant.LEG_RESPONSE).

    Found from the robot's logs the night D6 started training: the hips and knees make
    their torque through an 8-12 ms lag on what their position loop asks, as the wheels
    do, where D6 has them make it at once. The jump's shake on the robot runs through
    the legs, and the balance at the bottom of the ride height leans on them.
    """

    robot = WheeledBipedDriveEnvCfg().robot.replace(actuators=D6_LEG_ACTUATORS)
