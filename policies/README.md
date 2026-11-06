# Policies the robot has run

Each folder is one training run's record, kept so that a policy the robot has
driven on can be rebuilt, checked and compared without the run itself. The runs
whole -- checkpoints, TensorBoard logs, videos, 13-19 MB each -- live in
`exports/rl/`, which is not tracked; these are the parts that define the policy.

| | Run | On the robot | What it is |
|---|---|---|---|
| D2 | `rough-2026-11-04_09-01-34_measured_fix` | 2026-11-04 to 2026-11-06, kept on the Pi as `sbc/policy_d2.npz` | the first policy trained on the measured robot; 0.5 m/s and 1.5 rad/s |
| D3 | `rough-2026-11-05_10-37-59_fresh2_18` | from 2026-11-06 07:18, as `sbc/policy.npz` | trained from scratch to 1.8 m/s and 15 rad/s inside a diamond envelope, ride height 170-207 mm |

How each was trained and what it measured is in
[`simulation/isaaclab/TRAINING_HISTORY.md`](../simulation/isaaclab/TRAINING_HISTORY.md),
and what the robot feeds it and takes from it in
[`docs/POLICY_INTERFACE.md`](../docs/POLICY_INTERFACE.md).

In each folder:

- `exported/policy.npz` is what the robot loads: the network's weights and the
  `meta` the robot reads (crouch, gains, ranges), packed by `sbc/pack_policy.py`.
  Its MD5 begins `f54c9fd86ff4` for D2 and `3c7fa4adf863` for D3, matched to the
  robot's copies when each was installed.
- `exported/policy.onnx` and `policy.onnx.data` are the same network for the
  MuJoCo checks; `policy.pt` is it as TorchScript.
- `params/env.yaml` and `agent.yaml` are the task and the learner exactly as the
  run used them. Paths in them are the pod's.
- `git/IsaacLab.diff` is the training code's commit and state at the start.

The scripts that read a run (`simulation/mujoco/drive.py`, `launch_check.py`)
take its folder; point them here or at `exports/rl/` alike.
