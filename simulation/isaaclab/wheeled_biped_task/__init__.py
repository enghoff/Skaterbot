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
    return None
