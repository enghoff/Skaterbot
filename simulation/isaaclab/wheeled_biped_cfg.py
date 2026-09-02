"""Isaac Lab articulation config for the wheeled biped.

Copy this into an Isaac Lab extension, or add simulation/ to PYTHONPATH and
import it. It is written against the Isaac Lab 2.x namespace (`isaaclab.*`);
before 2.0 the same classes lived under `omni.isaac.lab.*`.

    from wheeled_biped_cfg import WHEELED_BIPED_CFG
    robot = Articulation(WHEELED_BIPED_CFG.replace(prim_path="/World/Robot"))

WHAT THIS FILE IS FOR. The URDF describes the mechanism: links, masses, inertia
tensors, joint axes, travel. None of that is a choice. This file holds the
things that ARE choices -- how the actuator is modelled, what the joints are
told to do, where the robot starts -- and every one of them is either taken
from the project's documents or flagged below as a guess.

THE NUMBERS MARKED "UNMEASURED" ARE NOT PLACEHOLDERS YOU CAN IGNORE. Three of
them decide whether a policy trained here has any chance of transferring: the
actuator's rotor inertia reflected through its 7:1 reduction, its velocity
limit, and the friction of urethane on whatever the robot is driven on. All
three are currently guesses, and simulation/check_model.py says so every time
it runs.

WHAT KIND OF ROBOT THIS IS. Six actuators: hip pitch, knee and a driven wheel
on each leg. There is no hip roll, so nothing can lean the torso over a wheel
and the only lateral authority the robot has is driving the two wheels
differentially. It is a wheeled inverted pendulum with a two-joint leg under
each wheel, not a walking biped, and a locomotion task written for a biped will
not fit it.
"""

from __future__ import annotations

import isaaclab.sim as sim_utils
from isaaclab.actuators import DCMotorCfg
from isaaclab.assets import ArticulationCfg

# --------------------------------------------------------------------------
# Where the robot description is. Regenerate it with
#     uv run simulation/build_urdf.py
# after any change to the CAD.

URDF_PATH = "${SIMULATION_DIR}/urdf/wheeled_biped.urdf"

# --------------------------------------------------------------------------
# The actuator, all six of them the same
#
# DAMIAO DM-J3507-2EC, 7:1, 24 V, CAN-FD, MIT-mode torque control.

# docs/PLAN.md. The peak is what the joint may briefly reach; the continuous
# figure is a THERMAL limit and cannot be expressed as a saturation at all --
# hold 0.8 Nm long enough and the actuator derates rather than refusing. It
# belongs in the reward as a cost, and there is a term for it below.
PEAK_TORQUE_NM = 3.0
CONTINUOUS_TORQUE_NM = 0.8

# UNMEASURED. No vendor no-load speed has been recorded in this project. This
# figure sets the robot's top speed -- 20 rad/s on a 40 mm wheel is 0.8 m/s --
# so a policy will learn against whatever is written here. Replace it.
MAX_VELOCITY_RAD_S = 20.0

# UNMEASURED, AND THE MOST IMPORTANT OF THE THREE. A 7:1 reduction reflects the
# rotor's own inertia to the joint multiplied by 49. Estimated from a 3507
# outrunner rotor of roughly 30 g at a 15 mm radius: J_rotor about 4.7e-6, so
# about 2.3e-4 kg m2 at the output. That is several times the wheel's own spin
# inertia, which means leaving it out does not make the model slightly wrong,
# it makes the wheels a different plant. Measure it by spin-down.
ARMATURE_KG_M2 = 2.3e-4

# UNMEASURED. Joint friction and damping have never been characterised on this
# actuator. These are zero because inventing them would be worse, not because
# they are zero. Identify them on the first joint that runs.
JOINT_FRICTION_NM = 0.0
JOINT_DAMPING_NM_S_RAD = 0.0

# --------------------------------------------------------------------------
# Where it starts
#
# base_link's origin is the torso centre, which stands 0.3065 m above the floor
# with the legs straight. A centimetre of clearance keeps the wheels off the
# ground plane at reset so the first contact is resolved rather than penetrated.

STANDING_BASE_HEIGHT_M = 0.3065
RESET_CLEARANCE_M = 0.01


WHEELED_BIPED_CFG = ArticulationCfg(
    spawn=sim_utils.UrdfFileCfg(
        asset_path=URDF_PATH,
        fix_base=False,
        merge_fixed_joints=True,
        # The URDF's joints are all actuated; none should come in as a fixed or
        # a free joint.
        joint_drive=sim_utils.UrdfConverterCfg.JointDriveCfg(
            gains=sim_utils.UrdfConverterCfg.JointDriveCfg.PDGainsCfg(
                stiffness=None, damping=None
            ),
            target_type="none",
        ),
        rigid_props=sim_utils.RigidBodyPropertiesCfg(
            disable_gravity=False,
            retain_accelerations=False,
            # This robot is small and light, and a wheel at 20 rad/s on a 4 ms
            # step moves 3 mm at the contact patch. Leave CCD on until it is
            # shown to be unnecessary.
            max_depenetration_velocity=1.0,
        ),
        articulation_props=sim_utils.ArticulationRootPropertiesCfg(
            enabled_self_collisions=True,
            solver_position_iteration_count=8,
            solver_velocity_iteration_count=2,
        ),
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, STANDING_BASE_HEIGHT_M + RESET_CLEARANCE_M),
        joint_pos={
            # Legs straight, which is the neutral pose main.kcl draws and the
            # only pose the mass budget has ever been checked in. It is also
            # the worst pose to balance from -- the centre of mass is at its
            # highest -- so a curriculum may want to start crouched.
            "hip_pitch_.*": 0.0,
            "knee_.*": 0.0,
            "wheel_drive_.*": 0.0,
        },
        joint_vel={".*": 0.0},
    ),
    actuators={
        # Both leg joints. Positive is flexion on each, matching the CAD's own
        # pose scenes; the knee's 110 degree stop is in the URDF.
        "legs": DCMotorCfg(
            joint_names_expr=["hip_pitch_.*", "knee_.*"],
            effort_limit=PEAK_TORQUE_NM,
            saturation_effort=PEAK_TORQUE_NM,
            velocity_limit=MAX_VELOCITY_RAD_S,
            stiffness=0.0,
            damping=JOINT_DAMPING_NM_S_RAD,
            friction=JOINT_FRICTION_NM,
            armature=ARMATURE_KG_M2,
        ),
        # The wheels, which are the only thing holding the robot up. They are
        # a separate group because they are the joints a balance policy really
        # commands, and because they are the ones whose armature matters most.
        "wheels": DCMotorCfg(
            joint_names_expr=["wheel_drive_.*"],
            effort_limit=PEAK_TORQUE_NM,
            saturation_effort=PEAK_TORQUE_NM,
            velocity_limit=MAX_VELOCITY_RAD_S,
            stiffness=0.0,
            damping=JOINT_DAMPING_NM_S_RAD,
            friction=JOINT_FRICTION_NM,
            armature=ARMATURE_KG_M2,
        ),
    },
    soft_joint_pos_limit_factor=0.95,
)


# --------------------------------------------------------------------------
# Ground contact
#
# UNMEASURED, ALL OF IT. 85A skate urethane on a hard floor is a high-friction,
# fairly lossy contact, and none of these numbers come from a measurement of
# this wheel on any surface. They are a starting point to randomise around, not
# a description of anything.
#
# The wheel collides as a cylinder rather than as its crowned tread, because
# every solver resolves a cylinder against a plane cleanly and none of them
# resolves a crowned mesh cleanly. What that loses is the contact patch
# narrowing as the robot leans, which is real; if a policy turns out to depend
# on it, that is the assumption to revisit first.

WHEEL_MATERIAL_CFG = sim_utils.RigidBodyMaterialCfg(
    static_friction=1.0,
    dynamic_friction=0.9,
    restitution=0.1,
)

# Ranges worth randomising over, since the true value is unknown. Urethane on a
# painted concrete floor and urethane on a rug are not the same robot.
DOMAIN_RANDOMISATION = {
    "static_friction": (0.6, 1.4),
    "dynamic_friction": (0.5, 1.2),
    # The wheels have never been weighed and the capacitor bank has never been
    # sized, so the mass this model carries is uncertain by a good deal more
    # than the usual few per cent. Randomise the base mass accordingly.
    "base_mass_scale": (0.85, 1.15),
    "wheel_mass_scale": (0.8, 1.2),
    "armature_scale": (0.5, 2.0),
}


# --------------------------------------------------------------------------
# The continuous torque limit
#
# The URDF carries the 3 Nm peak because that is the only limit a URDF can
# express. The 0.8 Nm continuous rating is thermal, and docs/PLAN.md already
# records that the knee crosses it at about 47 degrees of sustained flexion
# just holding the robot up. A policy given a 3 Nm ceiling and no cost will
# happily learn a gait that sits above 0.8 Nm indefinitely, and the hardware
# will derate and then stop.
#
# Add this as a reward term rather than a hard limit, so that brief excursions
# stay available where they are actually needed.


def continuous_torque_penalty(applied_torque, weight: float = 1.0):
    """Cost for holding a joint above its thermal rating.

    `applied_torque` is (num_envs, num_joints). Returns (num_envs,). Zero
    inside the continuous rating, growing quadratically outside it, so the
    3 Nm peak stays reachable for the fraction of a second it is meant for.
    """
    excess = (applied_torque.abs() - CONTINUOUS_TORQUE_NM).clamp(min=0.0)
    return weight * (excess**2).sum(dim=-1)
