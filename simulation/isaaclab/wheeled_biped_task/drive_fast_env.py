"""Driving, with a share of the commands straight and fast. The design is in
drive_env_cfg.py's WheeledBipedDriveD9EnvCfg; this is the driving environment with that
share added to its commands.

A file of its own so that drive_env.py, which every driving task before D9 runs, stays as
they ran it. Folded into drive_env.py's own sampler behind a command_fast_fraction of
nothing, it would do the same.

Imported after the simulator has started -- see env_cfg.py for why.
"""

from __future__ import annotations

import torch

from .drive_env import WheeledBipedDriveEnv
from .drive_env_cfg import WheeledBipedDriveD9EnvCfg


class WheeledBipedDriveFastEnv(WheeledBipedDriveEnv):
    cfg: WheeledBipedDriveD9EnvCfg

    def _sample_commands(self, n: int) -> torch.Tensor:
        commands = super()._sample_commands(n)
        c = self.cfg
        dev = self.device
        # The standing robots' commands were zeroed; they stay standing.
        moving = (commands[:, :2] != 0.0).any(dim=1)
        fast = moving & (torch.rand(n, device=dev) < c.command_fast_fraction)
        lo, hi = c.command_fast_speed_m_s
        speed = torch.rand(n, device=dev) * (hi - lo) + lo
        ahead = torch.rand(n, device=dev) < c.command_fast_forward_share
        speed = torch.where(ahead, speed, -speed)
        lo, hi = c.command_fast_yaw_rate
        turn = torch.rand(n, device=dev) * (hi - lo) + lo
        commands[:, 0] = torch.where(fast, speed, commands[:, 0])
        commands[:, 1] = torch.where(fast, turn, commands[:, 1])
        return commands
