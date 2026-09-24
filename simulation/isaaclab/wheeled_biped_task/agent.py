"""PPO settings for the balance task, in rsl_rl's terms.

Sized like Isaac Lab's own flat-ground locomotion agents, which is the right
order for a robot with six joints and a 24-number observation. Nothing here has
been tuned against this robot yet.
"""

from isaaclab.utils.configclass import configclass
from isaaclab_rl.rsl_rl import (
    RslRlMLPModelCfg,
    RslRlOnPolicyRunnerCfg,
    RslRlPpoAlgorithmCfg,
)


@configclass
class WheeledBipedPPORunnerCfg(RslRlOnPolicyRunnerCfg):
    num_steps_per_env = 24
    max_iterations = 1500
    save_interval = 100
    experiment_name = "wheeled_biped_balance"
    # The actor sees only what the robot can sense; the critic also sees the
    # torso's velocity and height, which only the simulator knows.
    obs_groups = {"actor": ["policy"], "critic": ["policy", "critic"]}
    clip_actions = 1.0
    actor = RslRlMLPModelCfg(
        hidden_dims=[256, 128, 64],
        activation="elu",
        obs_normalization=True,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=0.5),
    )
    critic = RslRlMLPModelCfg(
        hidden_dims=[256, 128, 64],
        activation="elu",
        obs_normalization=True,
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.005,
        num_learning_epochs=5,
        num_mini_batches=4,
        learning_rate=1.0e-3,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.01,
        max_grad_norm=1.0,
    )


@configclass
class WheeledBipedRoughPPORunnerCfg(WheeledBipedPPORunnerCfg):
    # Rough ground and a curriculum take longer to climb than the flat did to
    # learn: the first run was still improving at 1 000 iterations.
    max_iterations = 3000
    experiment_name = "wheeled_biped_rough"
    # The environment clamps, and charges for asking beyond the range
    # (rew_action_bound). Clipping here as well hid that from the policy.
    clip_actions = None

    # The first rough run's exploration noise grew from 0.5 to 1.56. The
    # environment clips actions to +/-1, so past that the noise costs the
    # policy nothing and the entropy bonus keeps buying more of it, and the
    # policy learned against saturated, bang-bang wheels. A fifth of the bonus
    # lets the noise come back down.
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.001,
        num_learning_epochs=5,
        num_mini_batches=4,
        learning_rate=1.0e-3,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.01,
        max_grad_norm=1.0,
    )


@configclass
class WheeledBipedJumpPPORunnerCfg(WheeledBipedRoughPPORunnerCfg):
    # Started from the balance policy, widened by widen_checkpoint.py, so it
    # already drives; what it has to learn is the jump.
    max_iterations = 1500
    experiment_name = "wheeled_biped_jump"
    # The balance run's exploration fell to 0.08 once actions were no longer
    # clipped; a jump has to be found, so more entropy is paid for.
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.004,
        num_learning_epochs=5,
        num_mini_batches=4,
        learning_rate=1.0e-3,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.01,
        max_grad_norm=1.0,
    )
