"""Balance and drive over rough ground, at a commanded ride height.

The flat task's robot, rewards and randomisation, with four things added:

  * GROUND THAT IS NOT FLAT. A generated grid of 4 m tiles in seven kinds --
    flat, bumpy, slopes up and down, long waves, scattered low blocks, and
    thresholds ringing the start -- each in ten rows of rising difficulty. No
    stairs: a 40 mm wheel cannot climb a step, and this robot cannot step.
  * A CURRICULUM. Robots start on the easy rows. One that finishes its episode
    tracking its command moves a row harder; one that falls moves a row
    easier. How far up the rows the population gets is itself a result.
  * A RIDE HEIGHT to hold. The legs stop being a fixed crouch and become
    something the policy uses: it is told how long to make them, and on
    uneven ground it may make them differ, because with no hip roll a longer
    leg on one side is the ONLY way this robot can level its torso.
  * WORSE SENSING AND HARDER SHOVES. The policy's observations carry noise and
    a per-episode bias, as an IMU and encoders do, and the shoves are larger
    and include a twist.

The policy is still blind. It is given nothing about the ground, because the
robot will have no terrain sensor; it has to feel the ground through its
wheels and IMU. The critic, which exists only in training, is given a height
map of the ground around the robot, so it can tell a policy that did badly
from one that met a slope.

THE TERRAIN NUMBERS ARE CHOSEN AGAINST THE WHEEL. A wheel of radius r can
roll up a step of height h only if friction can supply the push, which takes
a coefficient of about tan(acos((r - h) / r)). For a 40 mm wheel that is 0.88
at a 10 mm step and 1.24 at 15 mm -- so with the urethane's guessed friction
of about 1, somewhere around a centimetre is the most this robot can climb
from a standstill, and the hardest rows here go past that on purpose, to find
out where the edge is.
"""

from __future__ import annotations

import math

import isaaclab.envs.mdp as mdp
import isaaclab.sim as sim_utils
import isaaclab.terrains as terrain_gen
from isaaclab.envs import ViewerCfg
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.sensors import ContactSensorCfg, RayCasterCfg, patterns
from isaaclab.sim import SimulationCfg
from isaaclab.terrains import TerrainGeneratorCfg, TerrainImporterCfg
from isaaclab.utils.configclass import configclass
from isaaclab.utils.noise import GaussianNoiseCfg, NoiseModelWithAdditiveBiasCfg
from isaaclab_physx.physics import PhysxCfg

from .env_cfg import (
    CROUCH_HIP_RAD,
    CROUCH_KNEE_RAD,
    ROBOT_CFG,
    EventCfg,
    WheeledBipedBalanceEnvCfg,
    crouched_base_height_m,
    plant,
)

# --------------------------------------------------------------------------
# The ground

WHEELED_TERRAINS_CFG = TerrainGeneratorCfg(
    size=(4.0, 4.0),
    border_width=5.0,
    num_rows=10,
    num_cols=16,
    # Finer than Isaac Lab's legged defaults, because the features that matter
    # to a 40 mm wheel are centimetres, not decimetres.
    horizontal_scale=0.05,
    vertical_scale=0.0025,
    slope_threshold=0.75,
    use_cache=False,
    curriculum=True,
    sub_terrains={
        "flat": terrain_gen.MeshPlaneTerrainCfg(proportion=0.10),
        # Floor-texture roughness: up to 15 mm of random height at 5 cm pitch.
        "bumpy": terrain_gen.HfRandomUniformTerrainCfg(
            proportion=0.20,
            noise_range=(0.0, 0.015),
            noise_step=0.0025,
            border_width=0.25,
        ),
        # Up to a 0.25 grade, 14 degrees, climbing out of the start and
        # descending into it.
        "slope_up": terrain_gen.HfPyramidSlopedTerrainCfg(
            proportion=0.15,
            slope_range=(0.0, 0.25),
            platform_width=1.0,
            border_width=0.25,
        ),
        "slope_down": terrain_gen.HfInvertedPyramidSlopedTerrainCfg(
            proportion=0.15,
            slope_range=(0.0, 0.25),
            platform_width=1.0,
            border_width=0.25,
        ),
        # Long gentle undulation, up to 30 mm, the kind a yard or a car park has.
        "waves": terrain_gen.HfWaveTerrainCfg(
            proportion=0.10, amplitude_range=(0.0, 0.03), num_waves=3, border_width=0.25
        ),
        # Scattered raised blocks, a cable or a mat edge, up to 15 mm.
        "blocks": terrain_gen.HfDiscreteObstaclesTerrainCfg(
            proportion=0.15,
            obstacle_height_mode="fixed",
            obstacle_width_range=(0.05, 0.4),
            obstacle_height_range=(0.0025, 0.015),
            num_obstacles=30,
            platform_width=1.0,
            border_width=0.25,
        ),
        # A ring of rails round the start that has to be crossed to go
        # anywhere: a door threshold, up to 15 mm.
        "thresholds": terrain_gen.MeshRailsTerrainCfg(
            proportion=0.15,
            rail_thickness_range=(0.03, 0.08),
            rail_height_range=(0.0025, 0.015),
            platform_width=1.0,
        ),
    },
)


# --------------------------------------------------------------------------
# Events: the flat task's randomisation, and harder shoves


@configclass
class RoughEventCfg(EventCfg):
    push = EventTerm(
        func=mdp.push_by_setting_velocity,
        mode="interval",
        interval_range_s=(3.0, 6.0),
        params={
            "velocity_range": {"x": (-0.5, 0.5), "y": (-0.3, 0.3), "yaw": (-0.8, 0.8)}
        },
    )


# --------------------------------------------------------------------------
# The ride height
#
# Commanded as the vertical distance from hip axis to wheel axle, averaged over
# the two legs, which the policy can see in its own joint angles -- a height
# above the ground would need a sensor the robot does not have. The crouch
# the flat task starts in is 203.5 mm; the range runs from nearly straight down
# to a knee of about 57 degrees. docs/PLAN.md puts the knee past its 0.8 Nm
# thermal rating at about 47 degrees sustained, so the bottom of the range is
# somewhere the thermal cost makes the policy visit, not live.

LEG_HEIGHT_RANGE_M = (0.185, 0.207)


def leg_height_m(hip_rad: float, knee_rad: float) -> float:
    """Hip axis to wheel axle, vertically, with the torso level."""
    g = plant.geometry()
    return g["upper_leg_m"] * math.cos(hip_rad) + g["lower_leg_m"] * math.cos(
        knee_rad - hip_rad
    )


# --------------------------------------------------------------------------
# The task


@configclass
class WheeledBipedRoughEnvCfg(WheeledBipedBalanceEnvCfg):
    episode_length_s = 20.0

    # the flat task's 24, and the ride height command
    observation_space = 25
    # velocity 3, height above the ground 1, a 7 x 5 height map
    state_space = 39

    # PhysX sizes its GPU contact buffers for a flat floor. Four thousand
    # robots on a terrain meshed at 5 cm need about 2.7 million contact
    # patches, against a default of 160 000, and the overflow is not an error
    # the run survives: it ends in a CUDA illegal memory access a few seconds
    # later. The buffers therefore scale with the number of robots -- see
    # size_gpu_buffers below, which the environment calls before it builds the
    # simulation, once the robot count is final.
    sim: SimulationCfg = SimulationCfg(
        dt=plant.PHYSICS_DT,
        render_interval=4,
        physics=PhysxCfg(),
    )

    terrain = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="generator",
        terrain_generator=WHEELED_TERRAINS_CFG,
        # Everyone starts on the easy rows and earns the rest.
        max_init_terrain_level=3,
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
    terrain_curriculum = True
    # Move a row harder after an episode survived with the speed tracked to
    # within this, on average; a row easier after a fall.
    curriculum_speed_error_m_s = 0.15

    events: RoughEventCfg = RoughEventCfg()

    # Three centimetres more drop than on the flat, so a robot never starts
    # inside a bump.
    robot = ROBOT_CFG.replace(
        init_state=ROBOT_CFG.init_state.replace(
            pos=(0.0, 0.0, crouched_base_height_m() + plant.RESET_CLEARANCE_M + 0.03)
        )
    )

    # Termination by the torso touching anything, which on uneven ground is a
    # better test of a fall than a height would be.
    contact_sensor = ContactSensorCfg(
        prim_path="/World/envs/env_.*/Robot/Geometry/base_link",
        history_length=3,
        update_period=0.0,
    )
    # The critic's map of the ground: 60 x 40 cm around the robot at 10 cm,
    # aligned with its heading, cast down from well above it.
    height_scanner = RayCasterCfg(
        prim_path="/World/envs/env_.*/Robot/Geometry/base_link",
        offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 5.0)),
        ray_alignment="yaw",
        pattern_cfg=patterns.GridPatternCfg(resolution=0.1, size=(0.6, 0.4)),
        mesh_prim_paths=["/World/ground"],
        debug_vis=False,
    )

    # An IMU and encoders are noisy and a little off; so is what the policy
    # sees here. The critic's observations are left clean.
    observation_noise_model = NoiseModelWithAdditiveBiasCfg(
        noise_cfg=GaussianNoiseCfg(std=0.02, operation="add"),
        bias_noise_cfg=GaussianNoiseCfg(std=0.02, operation="abs"),
    )

    viewer: ViewerCfg = ViewerCfg(
        eye=(1.6, -1.6, 1.0),
        lookat=(0.0, 0.0, 0.0),
        origin_type="asset_root",
        asset_name="robot",
    )

    # -- actions. Each leg joint needs more room than on the flat to reach
    # the bottom of the ride-height range, the knee twice the hip.
    leg_action_scale_rad = (0.4, 0.8, 0.4, 0.8)
    # Slopes cost torque: 2.1 kg up a 0.25 grade on 40 mm wheels is about
    # 0.2 Nm before any balancing, and the first run's wheels sat on their
    # 0.6 Nm limit even on the flat.
    wheel_action_scale_nm = 1.0

    # -- commands
    command_leg_height_m = LEG_HEIGHT_RANGE_M
    default_leg_height_m = leg_height_m(CROUCH_HIP_RAD, CROUCH_KNEE_RAD)

    # -- termination
    max_tilt_rad = math.radians(60.0)

    # -- rewards. Turning was the first run's weak point, so it is weighted
    # closer to speed.
    rew_track_yaw_rate = 1.5
    rew_track_leg_height = 1.0
    # The wheel is allowed fore and aft of the hip -- it is a way to balance
    # -- but not for free.
    rew_wheel_fore_aft = -5.0
    # THE STAGGER. Both rough policies found they could stand with one wheel
    # 11 cm ahead of the other -- two contacts in a line, so hardly any pitch
    # to balance -- which the fore-aft cost above barely touched. The distance
    # between the two wheels' fore-aft positions is charged on its own.
    rew_wheel_stagger = -50.0
    # WHEELSPIN. The same policies held that stance with one wheel spinning on
    # the floor at up to 46 rad/s, half the robots at any moment. Charged as
    # the speed of each tyre's contact point over the ground, which is zero
    # for a wheel that rolls and grows with any skid, in any direction.
    rew_wheel_slip = -1.0
    # Out-of-range actions, now that the training wrapper passes them through.
    rew_action_bound = -1.0
    # The first rough run balanced well on a chattering wheel torque: 0.53 Nm
    # RMS standing still, where balance.py's LQR holds the same robot on
    # 0.02, and a fifth of the time above the 0.8 Nm rating. Inside the
    # thermal rating on average, but heat, battery and gearbox spent on
    # nothing. Heat and chatter are charged harder: the thermal excess and
    # torque five times over, the change in command between steps five times.
    rew_thermal = -10.0
    rew_torque = -5.0e-3
    rew_action_rate = -0.05
    # Off: with no hip roll, unequal legs are how the torso is levelled.
    rew_leg_posture = 0.0
    rew_leg_asymmetry = 0.0


# --------------------------------------------------------------------------
# GPU buffers, per robot
#
# Measured: 660 contact patches a robot on this terrain, and at 16 384 robots
# the broad phase wanted 142 aggregate pairs, 181 found/lost pairs and 3 423
# found/lost aggregate pairs a robot. Overflowing the last three is worse than
# overflowing the patches: PhysX says it "will miss interactions" and carries
# on, wheels drop through the ground, and training sees a policy that has
# forgotten how to balance. So every one is sized per robot with headroom,
# rounded up to a power of two, and never below PhysX's own default.

PER_ROBOT = {
    "gpu_max_rigid_patch_count": 1024,
    "gpu_max_rigid_contact_count": 4096,
    "gpu_collision_stack_size": 32768,  # bytes
    "gpu_total_aggregate_pairs_capacity": 256,
    "gpu_found_lost_pairs_capacity": 256,
    "gpu_found_lost_aggregate_pairs_capacity": 4096,
}
FLOOR = {
    "gpu_max_rigid_patch_count": 2**22,
    "gpu_max_rigid_contact_count": 2**24,
    "gpu_collision_stack_size": 2**27,
    "gpu_total_aggregate_pairs_capacity": 2**21,
    "gpu_found_lost_pairs_capacity": 2**21,
    "gpu_found_lost_aggregate_pairs_capacity": 2**25,
}


def size_gpu_buffers(cfg: WheeledBipedRoughEnvCfg) -> None:
    """Size PhysX's GPU contact buffers for cfg.scene.num_envs robots."""

    def pow2(n: int) -> int:
        return 1 << max(0, int(n - 1).bit_length())

    n = cfg.scene.num_envs
    for name, per_robot in PER_ROBOT.items():
        setattr(cfg.sim.physics, name, max(FLOOR[name], pow2(n * per_robot)))


# --------------------------------------------------------------------------
# Tiles, per robot
#
# Every robot on a tile starts from the same point, so the broad phase sees
# every pair of them overlapping: the pairs grow with the square of the robots
# per tile. At 4 096 robots on 160 tiles, 26 a tile, that fits PhysX's
# defaults; at 16 384 on the same 160, a hundred a tile, it wanted 80 million
# aggregate pairs and dropped contacts. So the grid widens with the robot
# count, in whole multiples of its 16 columns so every kind of ground keeps
# its share, and the robots per tile stay where they were proven.

ROBOTS_PER_TILE = 26


def scale_terrain(cfg: WheeledBipedRoughEnvCfg) -> None:
    """Widen the terrain grid so each tile's start holds about 26 robots."""
    gen = cfg.terrain.terrain_generator
    base = WHEELED_TERRAINS_CFG.num_cols
    tiles_wanted = cfg.scene.num_envs / ROBOTS_PER_TILE
    multiple = max(1, math.ceil(tiles_wanted / (gen.num_rows * base)))
    gen.num_cols = base * multiple
