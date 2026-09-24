# Isaac Lab

Reinforcement learning for the wheeled biped: a task that teaches it to balance
and drive, the scripts that train it on a rented GPU, and an evaluation that
says what the trained policy actually does.

Isaac Lab needs an NVIDIA RTX card, and the development laptop has an Intel
one, so this runs on a [RunPod](https://www.runpod.io) pod. Everything that
must outlive the pod lives on a network volume.

## Where it stands

The first run, on 24 September 2026, trained 4 096 robots for 1 000 iterations
-- 98 million steps, 22 minutes on an RTX 4090 -- and `evaluate.py` then put the
exported policy through its script on 512 robots, each with its own friction,
masses and rotor inertia:

```
  phase                    upright  speed err  turn err   peak torque, Nm (and time above 0.8 Nm)
                                                                 wheel           hip          knee
  stand, shoved at 2 s      100.0%   0.016m/s  0.015r/s    0.60 (  0%)  1.79 (  0%)  2.44 (  0%)
  forward 0.4 m/s            99.6%   0.031m/s  0.066r/s    0.60 (  0%)  3.00 (  0%)  3.00 (  1%)
  back 0.3 m/s               99.6%   0.023m/s  0.021r/s    0.60 (  0%)  1.22 (  0%)  1.57 (  0%)
  turn 1 rad/s               99.6%   0.012m/s  0.278r/s    0.60 (  0%)  1.48 (  7%)  1.56 (  0%)
  arc 0.3 m/s, 0.8 rad/s     99.4%   0.066m/s  0.455r/s    0.60 (  0%)  3.00 (  4%)  2.85 (  1%)

still upright after 20 s: 99.4%
```

It balances, takes a shove, and drives forward and back to within a few
centimetres a second. It turns badly: a quarter of the commanded rate short on
the spot, and half on an arc. The wheels sit at the task's 0.6 Nm action limit
at their peak, and the legs touch the 3 Nm actuator peak in brief bursts while
driving. Those three are the first things to look at in the next run -- the
yaw reward is weighted half the speed reward, and the wheel scale may be what
limits the turn.

The recording `play.py` makes shows the robots upright and driving, but the
camera meant to follow one of them frames it badly; `viewer` in `env_cfg.py`
needs adjusting.

The run, its exported `policy.pt` and `policy.onnx`, the video and the
TensorBoard log are on the volume under
`/workspace/runs/logs/rsl_rl/wheeled_biped_balance/2026-09-24_11-05-50/`, and a
copy is in the untracked `exports/rl/` of the checkout it was run from.

## What is here

| | |
|---|---|
| `wheeled_biped_cfg.py` | the robot as Isaac Lab sees it: the rigged USD, and the actuator model. Every number is `../plant.py`'s |
| `wheeled_biped_task/env_cfg.py` | the task's configuration: what the policy sees, commands and is rewarded for, and what is randomised. Its docstring is the design |
| `wheeled_biped_task/env.py` | the environment that runs it |
| `wheeled_biped_task/agent.py` | PPO settings, in rsl_rl's terms |
| `evaluate.py` | runs an exported policy through a fixed script of commands on 512 randomised robots and reports what happened |
| `runpod/setup_pod.sh` | stands a pod up: Isaac Sim 6.0.1, Isaac Lab 3.0, rsl_rl, and the CAD's own dependencies |
| `runpod/train.sh` | train, replay, or evaluate, with the environment set up the way it has to be |

## The task, in one paragraph

The policy is told a forward speed and a turn rate and has to hold the robot
upright while following them. It sees only what the robot will have -- an IMU on
the torso and the six encoders -- while the critic, which exists only in
training, also sees the torso's velocity and height. The legs take position
targets around a slight crouch, held by a stiffness and damping, which is what
the actuator's MIT mode will be sent; the wheels take torque. Friction, the torso
and wheel masses, and the actuator's reflected rotor inertia are randomised over
`plant.py`'s ranges, because none of them has been measured, and the robot is
shoved every four to eight seconds. `env_cfg.py` gives the reason for every
number.

## Running it

### A pod

The volume `biped-isaaclab` (id `ysamdjew9w`, 60 GB, EU-RO-1) holds everything.
A pod has to be in the same datacenter to mount it:

```
runpodctl pod create --name biped-isaaclab \
    --image runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404 \
    --gpu-id "NVIDIA GeForce RTX 4090" --data-center-ids EU-RO-1 \
    --network-volume-id ysamdjew9w --container-disk-in-gb 60 \
    --ports '22/tcp' --min-cuda-version 12.8 \
    --env '{"NVIDIA_DRIVER_CAPABILITIES":"all"}'
runpodctl ssh info <pod id>
```

`NVIDIA_DRIVER_CAPABILITIES=all` is not optional: without it the container gets
no Vulkan driver and Kit will not start, even headless. An RTX 4090 on the
secure cloud was $0.74 an hour in September 2026. Terminate the pod when done;
the volume survives it and costs about $4 a month.

### Setting it up

```
bash /workspace/biped/simulation/isaaclab/runpod/setup_pod.sh
```

On a fresh volume this installs everything, about fifteen minutes. On a new pod
over the existing volume it unpacks a snapshot of the environment instead, a
couple of minutes. The reason for the snapshot is in the script: the volume is
a network filesystem that writes big files quickly and small files at forty a
second, and Isaac Sim is a hundred thousand small files.

The project itself is at `/workspace/biped`, copied up from a checkout rather
than cloned, so that uncommitted work can be trained on. Copy it up again after
changing anything.

### The robot, rebuilt and checked

The task trains on the USD that `../isaacsim/import_urdf.py` builds, not on a
second conversion of the URDF, so build it and measure it first -- on the pod,
with the same checks as anywhere else:

```
cd /workspace/biped && source /opt/isaac-venv/bin/activate
export OMNI_KIT_ACCEPT_EULA=YES
python simulation/isaacsim/preflight.py
python -u simulation/isaacsim/import_urdf.py
python -u simulation/isaacsim/run.py --check
python -u simulation/isaacsim/run.py --balance --headless
```

### Training, replaying, scoring

```
R=/workspace/biped/simulation/isaaclab/runpod/train.sh
bash $R --num_envs 4096 --max_iterations 1000        # about 20 minutes on a 4090
bash $R --play --num_envs 16 --video --video_length 600   # exports policy.pt and .onnx, films it
bash $R --evaluate --policy /workspace/runs/logs/rsl_rl/wheeled_biped_balance/<run>/exported/policy.pt
```

Runs land in `/workspace/runs/logs/rsl_rl/wheeled_biped_balance/`, with
TensorBoard logs, checkpoints every hundred iterations, and after `--play` the
exported policy and a video.

## Traps, each of which cost a run

- **OpenBLAS and Kit's fork.** The task reads the robot's dimensions out of
  `cad/`, which imports build123d, which loads SciPy's OpenBLAS and starts its
  thread pool. Kit forks while it starts, and OpenBLAS's fork handler crashes
  shutting the pool down: `free(): invalid pointer`, then a hang, or a segfault
  in `blas_thread_shutdown_`. `train.sh` sets `OPENBLAS_NUM_THREADS=1`. Anything
  else that starts Isaac Lab after reading `plant.py` needs the same.
- **The configuration must not load USD.** Isaac Lab imports a task's
  configuration before it launches Kit. Anything in that module that pulls in
  `pxr` -- the environment class, `Articulation`, warp -- crashes the launch with
  the same unhelpful message. Hence `env_cfg.py` and `env.py` are separate files.
- **Isaac Lab 3.0 is not 2.x.** Asset data are warp arrays, read through
  `.torch`; writes are `write_root_pose_to_sim_index` and friends; quaternions
  are (x, y, z, w). The installer no longer takes a framework name, so rsl_rl
  comes from `isaaclab_rl[rsl_rl]`.
- **Isaac Sim 6.0 needs pre-releases.** Its core pins a release candidate of
  tinyobjloader, so `uv pip install` needs `--prerelease=allow`.

## What it does not establish

That the policy would work on the robot. It is trained against a plant whose
rotor inertia, velocity limit, wheel mass and ground friction are all
estimates, randomised because they are unknown. Randomising widens what the
policy tolerates; it does not tell anyone where the real robot sits in those
ranges. Measuring the actuator is still the most valuable next step for sim to
real, and `../README.md` lists what is unmeasured.
