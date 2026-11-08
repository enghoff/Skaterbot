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


# -- D7: D6's task on the robot as its 11 Hz shake measured it (plant.SHAKE): the wheel's
# own inertia, and every motor's torque late, the wheels' effect drawn up to 1.3.
D7_ACTUATORS = dict(D6_ACTUATORS)
D7_ACTUATORS["wheels"] = D6_ACTUATORS["wheels"].replace(
    armature=plant.SHAKE["wheel_armature_kg_m2"],
    torque_lag_s=plant.SHAKE["wheel_lag_s"],
    torque_gain=plant.SHAKE["wheel_gain"],
)
D7_ACTUATORS["legs"] = D6_ACTUATORS["legs"].replace(
    torque_lag_s=plant.SHAKE["leg_lag_s"],
    torque_gain=plant.SHAKE["leg_gain"],
    step_s=plant.PHYSICS_DT,
    lag_after_pd=True,
)


@configclass
class WheeledBipedDriveD7EnvCfg(WheeledBipedDriveD6EnvCfg):
    """D6's task with the robot's 11 Hz shake in it (plant.SHAKE).

    D6 on the robot on 7 November 2026 rocked it at 10.5-11 Hz, its wheels answering the
    pitch rate 25 per cent harder than D3's do, and MuJoCo and this task both had it calm:
    the wheel's inertia drawn about 8.3e-4 where the robot's is about 3e-4, the legs'
    torque made at once where the robot's comes 12-20 ms late, and the torso answering a
    push 0.81 as strongly as the robot's. The wheel's inertia is the robot's here, the
    legs' torque is late after their position loop, and the wheels' torque is drawn from
    0.8 to 1.3 of what is asked through a 10-20 ms lag, so that a policy that rocks the
    robot rocks it here first.
    """

    robot = WheeledBipedDriveEnvCfg().robot.replace(actuators=D7_ACTUATORS)


D8_ACTUATORS = dict(D7_ACTUATORS)
D8_ACTUATORS["wheels"] = D7_ACTUATORS["wheels"].replace(
    torque_gain=plant.SWAY["wheel_gain"],
)


@configclass
class WheeledBipedDriveD8EnvCfg(WheeledBipedDriveD7EnvCfg):
    """D7's task with the robot's slow sway in it as well (plant.SWAY).

    D7 on the robot on 7 November 2026 swung it at 1-1.5 Hz until it ran into a wall,
    where D3 had stood still: it is D3 turned down to 0.7 at every frequency. MuJoCo sways
    it the same way with the wheels' torque at 0.8 of asked or the IMU 30-40 ms late, and
    D3 not. Here the wheels' torque is drawn down to 0.7 and the IMU's delay up to 40 ms,
    so that the balance has to stay firm at 1 Hz while SHAKE's top keeps it gentle at 11.
    """

    robot = WheeledBipedDriveEnvCfg().robot.replace(actuators=D8_ACTUATORS)

    imu_delay_steps = plant.SWAY["imu_delay_steps"]


# -- D9: D8's robot, asked for the speed it can hold, and asked for it often.
#
# The top of the speed asked. The motor makes 1.5 Nm to 37.5 rad/s, 1.5 m/s on the 40 mm
# wheel, and nothing at 55 (plant.MOTOR_CURVE); a balancing robot has to speed its wheels
# up past the body to stop, and D3 braking from 1.54 m/s in MuJoCo spun them to 50 rad/s
# with 0.44 Nm left there (7 November 2026, session scratchpad topspeed/). So about 1.5
# m/s is as fast as this motor drives and still stops. D8's 2.2 was the no-load speed,
# where the motor makes nothing at all.
D9_TOP_SPEED_M_S = 1.6
# The battery as the robot's packs have really been run: 23.35 to 25.21 V over the 19
# runs logged on 5-7 November 2026 (vbus in each run's log), 0.94 to 1.02 of the 24.8 V
# the curve was measured on. The floor is 22.3 V, 3.72 V a cell, where a LiPo's flat
# stretch ends: 1 V under the lowest any run reached, for a pack further down than any
# yet and for its sag under load (the most one run fell was 0.56 V, 24.80 to 24.24, on
# 6 November at 22:48). From D4 to D8 it was 0.8, 19.8 V, under the 21.6 V below which
# sbc/balance.py will not start a run: there the motor stops at 1.76 m/s and makes 0.73
# Nm at 1.5 where at 0.9 it makes 1.2. balance.py would still start one at 21.6-22.3 V,
# 0.87-0.9, which this has not trained on.
D9_BATTERY = (0.9, 1.02)


@configclass
class WheeledBipedDriveD9EnvCfg(WheeledBipedDriveD8EnvCfg):
    """D8's task asking for the top speed this motor allows, and asking for it often.

    The robot is D8's, SHAKE and SWAY and all; only the commands and the battery change.
    Its sampler is drive_fast_env.py's, which takes these settings.

    D8 cruises at about 1.15 m/s in MuJoCo on launch_check.py's loop whatever it is asked
    from 1.4 to 2.2, using 0.09 Nm of the 1.15 its wheels could make there, and did 1.14
    on the robot asked 1.8; with the motor's curve taken away it still does 1.11. It is
    the policy that stops, not the motor. D3 holds 1.54. Training's own score asked
    2.0-2.2 m/s fell at every stage after D3's 1.56: D4 1.42, D5 1.19-1.28, d7_rate 1.37,
    D8 1.22. What taught it to hold back is likely, not proven, to be two things it
    cannot see, and one it was asked:

      * THE BATTERY, drawn from D4 on down to 0.8 of the pack, where the wheels stop at
        1.76 m/s and a robot cruising at 1.5 has nothing left to stop with. A policy that
        cannot read the voltage keeps the margin the flattest pack needs. It is drawn now
        as the packs have been run (D9_BATTERY), and is still not something it reads:
        an input would break resuming from D8.
      * HOW SELDOM FAST WAS ASKED. D8's commands are half everyday and half spread over
        the diamond to 2.2 m/s and 25 rad/s, so 2 % of them ask forward above 1.5 m/s,
        and 0.3 % above 1.3 with the turn under 0.5 rad/s; most of its fast commands
        come with a hard turn, a quarter of all commands past 2.5 m/s2 sideways, which
        the robot's launcher no longer passes (its legs flex and the inner wheel lifts at
        about 2). Here a quarter of the moving commands, a fifth of all, are straight
        and fast: 1.3 to 1.6 m/s, three in four forward, and the turn within 0.5 rad/s,
        0.8 m/s2 sideways at the top. Together with the rest, 21 % of commands ask above
        1.3 m/s and 20 % do so straight (D8 6.7 % and 0.6 %).
      * SPEEDS IT COULD NOT REACH. Asked 2.2 the motor gives nothing, so from 1.6 on the
        answer was the same whatever was asked. The top is 1.6 (D9_TOP_SPEED_M_S); the
        diamond's turn stays at 25.1 rad/s.

    The tracking reward is left as it is. Asked 1.5 m/s and holding 1.15, its kernel
    (0.05 + (0.2 x 1.5)^2 = 0.14 wide in m2/s2) pays 0.83 a second of its 2.0 and the
    cost in proportion charges 1.05: 2.2 a second lost against holding 1.5, close to half
    of the 5.0 a second of driving can earn at most. That pays for the speed if reaching
    it is safe; what it did not pay for was a fall, which with the battery at 0.8 a fast
    robot risked.

    The policy reads the speed asked as it is, in m/s, so its range is the policy's
    speed_range in sbc/pack_policy.py's export and the top of sbc/gamepad.py's
    TOP_SPEED_M_S, and both become 1.6. sbc/policy_loop.py's Trim can still ask up to
    0.15 m/s past it, 1.75, to make up the policy's own shortfall.
    """

    command_lin_vel_x = (-D9_TOP_SPEED_M_S, D9_TOP_SPEED_M_S)
    battery_speed_scale = D9_BATTERY

    # The share of moving commands straight and fast, drawn by drive_fast_env.py: a speed
    # evenly within the band, forward this often and otherwise back, which a full brake
    # asks in fast mode, and a turn evenly within its range.
    command_fast_fraction = 0.25
    command_fast_speed_m_s = (1.3, D9_TOP_SPEED_M_S)
    command_fast_forward_share = 0.75
    command_fast_yaw_rate = (-0.5, 0.5)

    # As D8 was trained: pod_d8.sh passed env.rew_action_rate=-0.15 on its command line,
    # as d7_rate's did, and D8's params/env.yaml has it. Here so the command line need not.
    rew_action_rate = -0.15
