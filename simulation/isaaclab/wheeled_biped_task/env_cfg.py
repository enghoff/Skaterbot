"""Balance and drive: the first reinforcement-learning task for the wheeled biped.

The policy is asked to stay upright on its two wheels while tracking a commanded
forward speed and turn rate. That is the whole of it. It does not jump, it does
not stand up after a fall, and it does not change height on command -- those
are later tasks, and each needs this one to work first.

WHAT THE POLICY SEES is what the robot will actually have: an IMU on the torso
(turn rate and the direction of gravity), the six encoders, the command, and
what it asked for last time. It is NOT given the torso's linear velocity or
height, because nothing on the robot measures either. The critic is -- it only
exists during training, so it may use anything the simulator knows, and a
critic that can see the velocity it is scoring learns far faster.

WHAT IT COMMANDS follows the actuator's MIT mode, which takes a position target,
a stiffness, a damping and a feed-forward torque:

  * the four leg joints get POSITION TARGETS around a slight crouch, held by a
    stiffness and damping stated below. That is what the leg actuators will be
    told on the robot, and it keeps the legs from being a second balancing
    problem the policy has to solve from scratch;
  * the two wheels get TORQUE, which is what a wheeled inverted pendulum
    balances with, and what simulation/isaacsim/balance.py's LQR commands.

WHAT IT IS REWARDED FOR, roughly in order of weight: tracking the commanded
speed and turn rate, keeping the torso level, and not falling. It is charged
for time spent above the actuator's 0.8 Nm thermal rating, for jerky commands,
and for folding its legs far from the crouch it started in.

EVERY PLANT NUMBER COMES FROM plant.py by way of wheeled_biped_cfg.py. The
numbers stated here are the TASK's choices -- gains, scales, reward weights,
command ranges -- and none of them is a claim about the robot.


THIS FILE IS IMPORTED BEFORE THE SIMULATOR STARTS. Isaac Lab reads a task's
configuration first and launches Kit from it, and anything that loads USD
before Kit exists -- the environment class, Articulation, warp -- crashes the
launch with nothing better than "free(): invalid pointer". So this file holds
the configuration only, and env.py, which is imported afterwards, holds the
environment.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import isaaclab.envs.mdp as mdp
import isaaclab.sim as sim_utils
from isaaclab.actuators import DCMotorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.envs import DirectRLEnvCfg, ViewerCfg
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sim import SimulationCfg
from isaaclab.terrains import TerrainImporterCfg
from isaaclab.utils.configclass import configclass
from isaaclab_physx.physics import PhysxCfg

# wheeled_biped_cfg.py sits one directory up, and plant.py one above that.
for _path in Path(__file__).resolve().parents[1:3]:
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import plant  # noqa: E402
from wheeled_biped_cfg import (  # noqa: E402
    ARMATURE_KG_M2,
    DOMAIN_RANDOMISATION,
    JOINT_FRICTION_NM,
    MAX_VELOCITY_RAD_S,
    PEAK_TORQUE_NM,
    WHEELED_BIPED_CFG,
)

# --------------------------------------------------------------------------
# Where it starts
#
# A slight crouch rather than the straight-legged neutral pose. With the legs
# straight the knee sits on its 0 degree stop, so a position target there is a
# target on a hard limit, and the policy has no room to extend. Knee at twice
# the hip keeps the axle directly under the hip, so the crouch does not move
# the wheel fore or aft of the centre of mass.

CROUCH_HIP_RAD = 0.25
CROUCH_KNEE_RAD = 2.0 * CROUCH_HIP_RAD


def crouched_base_height_m() -> float:
    """How high base_link stands in the crouch, from the CAD's leg lengths."""
    g = plant.geometry()
    straight = g["upper_leg_m"] + g["lower_leg_m"]
    crouched = g["upper_leg_m"] * math.cos(CROUCH_HIP_RAD) + g[
        "lower_leg_m"
    ] * math.cos(CROUCH_KNEE_RAD - CROUCH_HIP_RAD)
    return plant.standing_base_height_m() - (straight - crouched)


# --------------------------------------------------------------------------
# The legs, in position control
#
# Stiffness and damping are what the leg actuators will be sent in MIT mode.
# 12 Nm/rad reaches the 3 Nm peak at a quarter of a radian of error, which is
# stiff enough to carry the robot and soft enough that a landing is absorbed
# rather than transmitted. Damping puts the leg near critical with the thigh,
# shin and wheel hanging off it. Both are a starting point, not a result.

LEG_STIFFNESS_NM_RAD = 12.0
LEG_DAMPING_NM_S_RAD = 0.4

ROBOT_CFG: ArticulationCfg = WHEELED_BIPED_CFG.replace(
    prim_path="/World/envs/env_.*/Robot",
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, crouched_base_height_m() + plant.RESET_CLEARANCE_M),
        joint_pos={
            "hip_pitch_.*": CROUCH_HIP_RAD,
            "knee_.*": CROUCH_KNEE_RAD,
            "wheel_drive_.*": 0.0,
        },
        joint_vel={".*": 0.0},
    ),
    actuators={
        "legs": DCMotorCfg(
            joint_names_expr=["hip_pitch_.*", "knee_.*"],
            effort_limit=PEAK_TORQUE_NM,
            saturation_effort=PEAK_TORQUE_NM,
            velocity_limit=MAX_VELOCITY_RAD_S,
            stiffness=LEG_STIFFNESS_NM_RAD,
            damping=LEG_DAMPING_NM_S_RAD,
            friction=JOINT_FRICTION_NM,
            armature=ARMATURE_KG_M2,
        ),
        # Unchanged from wheeled_biped_cfg.py: torque in, torque out, with the
        # DC motor's torque falling to zero at the velocity limit.
        "wheels": WHEELED_BIPED_CFG.actuators["wheels"],
    },
)


# --------------------------------------------------------------------------
# Randomisation over what nobody has measured
#
# The ranges are plant.py's, so the plain Isaac Sim scripts and this task
# randomise over the same uncertainty.


@configclass
class EventCfg:
    wheel_friction = EventTerm(
        func=mdp.randomize_rigid_body_material,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="wheel_.*"),
            "static_friction_range": DOMAIN_RANDOMISATION["static_friction"],
            "dynamic_friction_range": DOMAIN_RANDOMISATION["dynamic_friction"],
            "restitution_range": (0.0, plant.CONTACT["restitution"]),
            "num_buckets": 64,
            "make_consistent": True,
        },
    )

    torso_mass = EventTerm(
        func=mdp.randomize_rigid_body_mass,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="base_link"),
            "mass_distribution_params": DOMAIN_RANDOMISATION["base_mass_scale"],
            "operation": "scale",
        },
    )

    wheel_mass = EventTerm(
        func=mdp.randomize_rigid_body_mass,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="wheel_.*"),
            "mass_distribution_params": DOMAIN_RANDOMISATION["wheel_mass_scale"],
            "operation": "scale",
        },
    )

    # The reflected rotor inertia, the number that matters most and is known
    # least. Randomised across a factor of four.
    armature = EventTerm(
        func=mdp.randomize_joint_parameters,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=".*"),
            "armature_distribution_params": DOMAIN_RANDOMISATION["armature_scale"],
            "operation": "scale",
        },
    )

    # A shove every few seconds, so the policy learns to recover rather than
    # only to hold still. 0.3 m/s is the shove balance.py's LQR was shown to
    # survive.
    push = EventTerm(
        func=mdp.push_by_setting_velocity,
        mode="interval",
        interval_range_s=(4.0, 8.0),
        params={"velocity_range": {"x": (-0.3, 0.3), "y": (-0.15, 0.15)}},
    )


# --------------------------------------------------------------------------
# The task


@configclass
class WheeledBipedBalanceEnvCfg(DirectRLEnvCfg):
    # 400 Hz physics, which plant.py chose for the rolling contact, and a
    # 100 Hz policy. The robot falls with a 106 ms time constant, so 10 ms
    # between decisions leaves room for the CAN round trip.
    decimation = 4
    episode_length_s = 20.0

    # hip_r, knee_r, hip_l, knee_l, wheel_r, wheel_l
    action_space = 6
    # ang vel 3, gravity 3, command 2, leg pos 4, joint vel 6, last action 6
    observation_space = 24
    # torso linear velocity 3 and height 1, for the critic only
    state_space = 4

    sim: SimulationCfg = SimulationCfg(
        dt=plant.PHYSICS_DT,
        render_interval=decimation,
        physics=PhysxCfg(),
    )

    # The floor is deliberately grippier than any wheel and combines by
    # minimum, so the wheel's own (randomised) material always decides the
    # friction. That is the same arrangement run.py uses.
    terrain = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="plane",
        collision_group=-1,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            friction_combine_mode="min",
            restitution_combine_mode="min",
            static_friction=2.0,
            dynamic_friction=2.0,
            restitution=0.0,
        ),
        debug_vis=False,
    )

    scene: InteractiveSceneCfg = InteractiveSceneCfg(
        num_envs=4096, env_spacing=1.5, replicate_physics=True
    )
    events: EventCfg = EventCfg()
    robot: ArticulationCfg = ROBOT_CFG

    # The camera a recorded video sees: close on the first robot, following it.
    viewer: ViewerCfg = ViewerCfg(
        eye=(1.0, -1.0, 0.5),
        lookat=(0.0, 0.0, 0.0),
        origin_type="asset_root",
        asset_name="robot",
    )

    # -- action scales
    leg_action_scale_rad = 0.3
    # Traction, not the actuator, is the ceiling: run.py found about 0.28 Nm a
    # wheel usable before the tyre breaks loose. 0.6 Nm lets the policy find
    # that limit without a unit action being a wheelspin.
    wheel_action_scale_nm = 0.6

    # -- commands. 0.5 m/s is well inside the 1.9 m/s the actuator's no-load
    # speed allows; a fifth of the robots are told to stand still.
    command_lin_vel_x = (-0.5, 0.5)
    command_yaw_rate = (-1.5, 1.5)
    command_standing_fraction = 0.2
    # Tracking tolerance as a fraction of the command, on top of the fixed
    # one: off here, where every command is well inside what the robot can do.
    command_tracking_relative = 0.0
    command_resample_s = 5.0

    # -- termination
    max_tilt_rad = math.radians(50.0)
    min_base_height_m = 0.12

    # -- reward weights
    rew_track_lin_vel = 2.0
    rew_track_yaw_rate = 1.0
    rew_alive = 0.5
    rew_upright = -5.0
    rew_lin_vel_z = -2.0
    rew_ang_vel_xy = -0.05
    rew_thermal = -2.0
    rew_torque = -1.0e-3
    rew_action_rate = -0.01
    rew_leg_posture = -1.0
    rew_leg_asymmetry = -0.5
    rew_terminated = -20.0
    # Off here: the flat task's policy was trained with its actions clipped
    # before it saw them. The rough task switches it on.
    rew_action_bound = 0.0
    # Being still when told to stand: paid when the speed and turn commands
    # are both zero, and falling off with the joints' and the torso's motion.
    # Bounded, so a shove is recovered from rather than ridden out stiffly.
    rew_stand_still = 0.0
    stand_still_tolerance = 0.5

    # -- the time between sensing and acting, in physics steps of 2.5 ms,
    # drawn per episode from each range; off here. The IMU's reading and the
    # encoders' are handed to the policy that many steps late, and a command
    # takes effect that many steps into the policy step. Up to decimation.
    imu_delay_steps = (0, 0)
    joint_delay_steps = (0, 0)
    action_delay_steps = (0, 0)
    # The chance, each policy step, of each delay being one step off its
    # episode's value, and of a command being lost altogether.
    delay_jitter_prob = 0.0
    command_drop_prob = 0.0

    # -- the sensors: Gaussian noise each step and an offset drawn per
    # episode, on the IMU's and the encoders' readings as the policy sees
    # them (scaled). Off here.
    sensor_noise_std = 0.0
    sensor_bias_std = 0.0
    # Whether the ride-height command reaches the policy as -1 to 1 over its
    # range rather than in metres (a task with one says so).
    scale_height_command = False

    # -- the battery: the motors' no-load speed as a share of the rated
    # figure's, drawn per episode. Off here.
    battery_speed_scale = (1.0, 1.0)
    # Whether the policy is told the pack's voltage (a task that appends it
    # to its observations says where).
    observe_battery = False
