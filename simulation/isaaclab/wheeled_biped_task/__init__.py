"""The wheeled biped's reinforcement-learning tasks, for Isaac Lab 3.0.

Isaac Lab's own training script finds a task outside its tree through
--external_callback, which imports a function and calls it before the task is
looked up. So nothing here is copied into Isaac Lab:

    cd /workspace/IsaacLab
    PYTHONPATH=/workspace/biped/simulation/isaaclab \\
    python scripts/reinforcement_learning/rsl_rl/train.py --headless \\
        --external_callback wheeled_biped_task.register \\
        --task Biped-Wheeled-Balance-v0

simulation/isaaclab/runpod/train.sh does exactly that. Two tasks: the flat
balance-and-drive task, and the same on rough ground at a commanded ride
height (Biped-Wheeled-Rough-v0).
"""

TASK_ID = "Biped-Wheeled-Balance-v0"
ROUGH_TASK_ID = "Biped-Wheeled-Rough-v0"
JUMP_TASK_ID = "Biped-Wheeled-Jump-v0"
DRIVE_TASK_ID = "Biped-Wheeled-Drive-v0"
# The driving and jump tasks on the motors as measured (plant.MOTOR_CURVE).
DRIVE_MEASURED_TASK_ID = "Biped-Wheeled-Drive-Measured-v0"
JUMP_MEASURED_TASK_ID = "Biped-Wheeled-Jump-Measured-v0"
# The measured driving task down to a 155 mm ride height (WheeledBipedDriveLowEnvCfg).
DRIVE_LOW_TASK_ID = "Biped-Wheeled-Drive-Low-v0"
# D6: the low task on the robot as its driving showed it (WheeledBipedDriveD6EnvCfg).
DRIVE_D6_TASK_ID = "Biped-Wheeled-Drive-D6-v0"
# D6 and the jump with the legs' torque as late as the robot's (plant.LEG_RESPONSE).
DRIVE_D6_LEGS_TASK_ID = "Biped-Wheeled-Drive-D6-Legs-v0"
JUMP_LAG_TASK_ID = "Biped-Wheeled-Jump-Lag-v0"
# D7: D6 with the robot's 11 Hz shake in it (plant.SHAKE, WheeledBipedDriveD7EnvCfg).
DRIVE_D7_TASK_ID = "Biped-Wheeled-Drive-D7-v0"
# D8: D7 with the robot's slow sway in it too (plant.SWAY, WheeledBipedDriveD8EnvCfg).
DRIVE_D8_TASK_ID = "Biped-Wheeled-Drive-D8-v0"


def register() -> list[str] | None:
    """Register the tasks with gymnasium. Isaac Lab calls this by name.

    It returns None because it consumes no command-line arguments; the
    training script treats None as "leave them all for Hydra".
    """
    import gymnasium as gym

    if TASK_ID not in gym.registry:
        gym.register(
            id=TASK_ID,
            entry_point=f"{__name__}.env:WheeledBipedBalanceEnv",
            disable_env_checker=True,
            kwargs={
                "env_cfg_entry_point": f"{__name__}.env_cfg:WheeledBipedBalanceEnvCfg",
                "rsl_rl_cfg_entry_point": f"{__name__}.agent:WheeledBipedPPORunnerCfg",
            },
        )
    if ROUGH_TASK_ID not in gym.registry:
        gym.register(
            id=ROUGH_TASK_ID,
            entry_point=f"{__name__}.rough_env:WheeledBipedRoughEnv",
            disable_env_checker=True,
            kwargs={
                "env_cfg_entry_point": f"{__name__}.rough_env_cfg:WheeledBipedRoughEnvCfg",
                "rsl_rl_cfg_entry_point": f"{__name__}.agent:WheeledBipedRoughPPORunnerCfg",
            },
        )
    if JUMP_TASK_ID not in gym.registry:
        gym.register(
            id=JUMP_TASK_ID,
            entry_point=f"{__name__}.jump_env:WheeledBipedJumpEnv",
            disable_env_checker=True,
            kwargs={
                "env_cfg_entry_point": f"{__name__}.jump_env_cfg:WheeledBipedJumpEnvCfg",
                "rsl_rl_cfg_entry_point": f"{__name__}.agent:WheeledBipedJumpPPORunnerCfg",
            },
        )
    if DRIVE_TASK_ID not in gym.registry:
        gym.register(
            id=DRIVE_TASK_ID,
            entry_point=f"{__name__}.drive_env:WheeledBipedDriveEnv",
            disable_env_checker=True,
            kwargs={
                "env_cfg_entry_point": f"{__name__}.drive_env_cfg:WheeledBipedDriveEnvCfg",
                "rsl_rl_cfg_entry_point": f"{__name__}.agent:WheeledBipedRoughPPORunnerCfg",
                "rsl_rl_mirror_cfg_entry_point": f"{__name__}.agent:WheeledBipedDriveMirrorPPORunnerCfg",
                "rsl_rl_fresh_cfg_entry_point": f"{__name__}.agent:WheeledBipedDriveFreshPPORunnerCfg",
            },
        )
    if DRIVE_MEASURED_TASK_ID not in gym.registry:
        gym.register(
            id=DRIVE_MEASURED_TASK_ID,
            entry_point=f"{__name__}.drive_env:WheeledBipedDriveEnv",
            disable_env_checker=True,
            kwargs={
                "env_cfg_entry_point": f"{__name__}.drive_env_cfg:WheeledBipedDriveMeasuredEnvCfg",
                "rsl_rl_cfg_entry_point": f"{__name__}.agent:WheeledBipedRoughPPORunnerCfg",
                "rsl_rl_fresh_cfg_entry_point": f"{__name__}.agent:WheeledBipedDriveFreshPPORunnerCfg",
            },
        )
    if DRIVE_LOW_TASK_ID not in gym.registry:
        gym.register(
            id=DRIVE_LOW_TASK_ID,
            entry_point=f"{__name__}.drive_env:WheeledBipedDriveEnv",
            disable_env_checker=True,
            kwargs={
                "env_cfg_entry_point": f"{__name__}.drive_env_cfg:WheeledBipedDriveLowEnvCfg",
                "rsl_rl_cfg_entry_point": f"{__name__}.agent:WheeledBipedRoughPPORunnerCfg",
                "rsl_rl_fresh_cfg_entry_point": f"{__name__}.agent:WheeledBipedDriveFreshPPORunnerCfg",
            },
        )
    if DRIVE_D6_TASK_ID not in gym.registry:
        gym.register(
            id=DRIVE_D6_TASK_ID,
            entry_point=f"{__name__}.drive_env:WheeledBipedDriveEnv",
            disable_env_checker=True,
            kwargs={
                "env_cfg_entry_point": f"{__name__}.drive_env_cfg:WheeledBipedDriveD6EnvCfg",
                "rsl_rl_cfg_entry_point": f"{__name__}.agent:WheeledBipedRoughPPORunnerCfg",
                "rsl_rl_fresh_cfg_entry_point": f"{__name__}.agent:WheeledBipedDriveFreshPPORunnerCfg",
            },
        )
    if DRIVE_D6_LEGS_TASK_ID not in gym.registry:
        gym.register(
            id=DRIVE_D6_LEGS_TASK_ID,
            entry_point=f"{__name__}.drive_env:WheeledBipedDriveEnv",
            disable_env_checker=True,
            kwargs={
                "env_cfg_entry_point": f"{__name__}.drive_env_cfg:WheeledBipedDriveD6LegsEnvCfg",
                "rsl_rl_cfg_entry_point": f"{__name__}.agent:WheeledBipedRoughPPORunnerCfg",
                "rsl_rl_fresh_cfg_entry_point": f"{__name__}.agent:WheeledBipedDriveFreshPPORunnerCfg",
            },
        )
    if DRIVE_D7_TASK_ID not in gym.registry:
        gym.register(
            id=DRIVE_D7_TASK_ID,
            entry_point=f"{__name__}.drive_env:WheeledBipedDriveEnv",
            disable_env_checker=True,
            kwargs={
                "env_cfg_entry_point": f"{__name__}.drive_env_cfg:WheeledBipedDriveD7EnvCfg",
                "rsl_rl_cfg_entry_point": f"{__name__}.agent:WheeledBipedRoughPPORunnerCfg",
                "rsl_rl_fresh_cfg_entry_point": f"{__name__}.agent:WheeledBipedDriveFreshPPORunnerCfg",
            },
        )
    if DRIVE_D8_TASK_ID not in gym.registry:
        gym.register(
            id=DRIVE_D8_TASK_ID,
            entry_point=f"{__name__}.drive_env:WheeledBipedDriveEnv",
            disable_env_checker=True,
            kwargs={
                "env_cfg_entry_point": f"{__name__}.drive_env_cfg:WheeledBipedDriveD8EnvCfg",
                "rsl_rl_cfg_entry_point": f"{__name__}.agent:WheeledBipedRoughPPORunnerCfg",
                "rsl_rl_fresh_cfg_entry_point": f"{__name__}.agent:WheeledBipedDriveFreshPPORunnerCfg",
            },
        )
    if JUMP_LAG_TASK_ID not in gym.registry:
        gym.register(
            id=JUMP_LAG_TASK_ID,
            entry_point=f"{__name__}.jump_env:WheeledBipedJumpEnv",
            disable_env_checker=True,
            kwargs={
                "env_cfg_entry_point": f"{__name__}.jump_measured_env_cfg:WheeledBipedJumpLagEnvCfg",
                "rsl_rl_cfg_entry_point": f"{__name__}.agent:WheeledBipedJumpPPORunnerCfg",
            },
        )
    if JUMP_MEASURED_TASK_ID not in gym.registry:
        gym.register(
            id=JUMP_MEASURED_TASK_ID,
            entry_point=f"{__name__}.jump_env:WheeledBipedJumpEnv",
            disable_env_checker=True,
            kwargs={
                "env_cfg_entry_point": f"{__name__}.jump_measured_env_cfg:WheeledBipedJumpMeasuredEnvCfg",
                "rsl_rl_cfg_entry_point": f"{__name__}.agent:WheeledBipedJumpPPORunnerCfg",
            },
        )
    return None
