"""The robot seen in a mirror, for training a policy that treats left and right alike.

The robot is close enough to mirror-symmetric, and a policy trained without this is not:
on the robot on 5 November 2026 this task's parent stood with its hips 7 degrees apart,
and at 0.5 m/s turning at 1.5 rad/s it did 0.65 m/s and 2.07 rad/s to the left and 0.44
m/s and 1.60 rad/s to the right, leaning back 18 degrees one way and 8 the other. MuJoCo
shows the same bias, more mildly. So each batch PPO learns from is given its mirror image,
which is Isaac Lab's and rsl_rl's `symmetry_cfg`, as its ANYmal tasks use it.

The mirror is the x-z plane, with y across the robot:

  * the turn rate about x and about z change sign, the rate about y does not;
  * gravity's y changes sign, and so does the turn command;
  * right and left swap, in the joints' positions, speeds and actions. Both sides share
    one axis in the URDF, so a joint's number means the same motion on either side and
    nothing changes sign;
  * in what only the critic sees, the torso's sideways speed changes sign and the height
    map turns over, its rows running across the robot (sideways, 0.4 m at 0.1 m, five
    rows of seven: rough_env_cfg.py's height_scanner, in grid_pattern's "xy" order).

drive_env.py and env.py set out those inputs. What keeps it from being exact is the IMU's
place and the wiring's weight, neither of which the simulator holds.
"""

from __future__ import annotations

import torch

# rough_env.py's "critic" group: the torso's speed, the height over the ground, the map.
_MAP_ROWS, _MAP_COLUMNS = 5, 7
_MAP_FROM = 4

# Right hip, right knee, left hip, left knee; then the two wheels.
_LEGS = (2, 3, 0, 1)
_WHEELS = (1, 0)


def _policy(obs: torch.Tensor) -> torch.Tensor:
    out = obs.clone()
    out[:, 0] = -obs[:, 0]  # turning about x
    out[:, 2] = -obs[:, 2]  # about z
    out[:, 4] = -obs[:, 4]  # gravity's y
    out[:, 7] = -obs[:, 7]  # the turn asked for
    out[:, 9:13] = obs[:, [9 + k for k in _LEGS]]
    out[:, 13:17] = obs[:, [13 + k for k in _LEGS]]
    out[:, 17:19] = obs[:, [17 + k for k in _WHEELS]]
    out[:, 19:25] = _actions(obs[:, 19:25])
    return out


def _critic(obs: torch.Tensor) -> torch.Tensor:
    out = obs.clone()
    out[:, 1] = -obs[:, 1]  # sideways speed
    rows = obs[:, _MAP_FROM:].reshape(-1, _MAP_ROWS, _MAP_COLUMNS)
    out[:, _MAP_FROM:] = rows.flip(dims=(1,)).reshape(-1, _MAP_ROWS * _MAP_COLUMNS)
    return out


def _actions(actions: torch.Tensor) -> torch.Tensor:
    return actions[:, [*_LEGS, *(4 + k for k in _WHEELS)]]


def mirrored(env, obs=None, actions=None):
    """The batch and its mirror image, as rsl_rl asks for them."""
    if obs is None:
        obs_out = None
    else:
        n = obs.batch_size[0]
        obs_out = obs.repeat(2)
        obs_out["policy"][n:] = _policy(obs["policy"])
        obs_out["critic"][n:] = _critic(obs["critic"])
    if actions is None:
        actions_out = None
    else:
        actions_out = torch.cat((actions, _actions(actions)), dim=0)
    return obs_out, actions_out
