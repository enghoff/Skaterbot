# Isaac Lab

Reinforcement learning for the wheeled biped: a task that teaches it to balance
and drive, the scripts that train it on a rented GPU, and an evaluation that
says what the trained policy actually does.

Isaac Lab needs an NVIDIA RTX card, and the development laptop has an Intel
one, so this runs on a [RunPod](https://www.runpod.io) pod. Everything that
must outlive the pod lives on a network volume.

## Where it stands

**The rough-ground balance policy is the one to use.** Trained from scratch on
24 September 2026 with 16 384 robots for 1 200 iterations -- 470 million steps,
1 h 53 min on an RTX PRO 4500 -- with the costs on wheelspin, wheel stagger and
out-of-range actions that the earlier policies needed (see Traps). On 1 280
robots spread over every kind of ground and difficulty, each with its own
friction, masses and rotor inertia, with the observation noise on:

```
  phase                    upright  speed err  turn err   torque, Nm: peak / RMS (time above 0.8 Nm)
                                                                      wheel                hip               knee
  stand, shoved at 2 s       99.7%   0.061m/s  0.046r/s   1.00 / 0.08 (  0%) 2.04 / 0.18 (  0%) 3.00 / 0.26 (  0%)
  forward 0.4 m/s            98.4%   0.072m/s  0.066r/s   1.00 / 0.09 (  0%) 3.00 / 0.17 (  0%) 3.00 / 0.27 (  0%)
  back 0.3 m/s               97.9%   0.087m/s  0.059r/s   1.00 / 0.09 (  0%) 3.00 / 0.18 (  0%) 3.00 / 0.25 (  0%)
  turn 1 rad/s               97.7%   0.053m/s  0.162r/s   0.99 / 0.10 (  0%) 2.79 / 0.26 (  0%) 3.00 / 0.30 (  0%)
  arc 0.3 m/s, 0.8 rad/s     97.2%   0.073m/s  0.167r/s   1.00 / 0.10 (  0%) 2.51 / 0.27 (  0%) 3.00 / 0.30 (  0%)
  crouched, forward 0.2      96.3%   0.055m/s  0.046r/s   1.00 / 0.09 (  0%) 2.62 / 0.17 (  0%) 3.00 / 0.25 (  0%)

  wheels 22-30 mm apart fore and aft; a tyre skidding in 0.4-2.3% of robots

  still upright after 24 s: 96.3%

  ground              rows 0-2        rows 3-5        rows 6-7        rows 8-9           all
  flat              100% ( 41)      100% ( 59)      100% ( 26)      100% ( 34)    100% (160)
  bumpy             100% ( 75)       99% ( 72)      100% ( 50)      100% ( 43)    100% (240)
  slope_up          100% ( 75)       99% ( 67)      100% ( 44)      100% ( 54)    100% (240)
  slope_down         98% ( 53)      100% ( 41)      100% ( 31)       97% ( 35)     99% (160)
  waves             100% ( 50)      100% ( 50)      100% ( 32)      100% ( 28)    100% (160)
  blocks            100% ( 43)      100% ( 45)      100% ( 44)       93% ( 28)     99% (160)
  thresholds        100% ( 45)       94% ( 50)       61% ( 28)       27% ( 37)     74% (160)
```

It balances and drives on everything but the tallest thresholds, holds a
ride height, and turns within a sixth of the command. The wheels average
0.1 Nm RMS and never pass the 0.8 Nm rating. Thresholds of 12-15 mm stop
three robots in four, which is about what a 40 mm wheel should manage when it
cannot cheat -- the earlier, cheating policies crossed more of them by
spinning a wheel. Checkpoint, exported `policy.pt` and `policy.onnx`, video and
TensorBoard log are under
`/workspace/runs/logs/rsl_rl/wheeled_biped_rough/2026-09-24_17-06-40_fixed/`,
and copied to the untracked `exports/rl/` of the checkout.

Everything before it is superseded: the flat-ground policy of the first run
(99.4% upright on the flat, turned badly, 0.6 Nm wheel limit), and two rough
policies that scored 99% by standing with their wheels staggered and one
spinning -- kept on the volume for the record, not for use.

**The jump is learning.** See `JUMPING.md` and the jump task below.

## What is here

| | |
|---|---|
| `wheeled_biped_cfg.py` | the robot as Isaac Lab sees it: the rigged USD, and the actuator model. Every number is `../plant.py`'s |
| `wheeled_biped_task/env_cfg.py` | the task's configuration: what the policy sees, commands and is rewarded for, and what is randomised. Its docstring is the design |
| `wheeled_biped_task/env.py` | the environment that runs it |
| `wheeled_biped_task/rough_env_cfg.py`, `rough_env.py` | the same task on generated rough ground with a curriculum, at a commanded ride height, with noisy sensing and harder shoves |
| `wheeled_biped_task/jump_env_cfg.py`, `jump_env.py` | the jump: a trigger, a target wheel clearance and a timer as inputs, leg stiffness and damping as outputs, on flat ground, while driving |
| `wheeled_biped_task/agent.py` | PPO settings, in rsl_rl's terms |
| `widen_checkpoint.py` | gives a trained policy the extra inputs and outputs a follow-on task needs, without changing what it does, so the jump starts from the balance policy |
| `evaluate_jump.py` | one jump per robot across a grid of target clearances and speeds: take-off, peak clearance against target, landings |
| `runpod/benchmark.sh` | how many robots to simulate on this GPU; refuses results with PhysX errors |
| `evaluate.py` | runs an exported policy through a fixed script of commands on hundreds of randomised robots and reports what happened; `--rough` spreads them over every kind of ground and difficulty |
| `runpod/setup_pod.sh` | stands a pod up: Isaac Sim 6.0.1, Isaac Lab 3.0, rsl_rl, and the CAD's own dependencies |
| `runpod/train.sh` | train, replay, or evaluate, with the environment set up the way it has to be |
| `JUMPING.md` | notes for the jump task not yet written: how high the actuators allow, what the simulator must fix first, and how to land |

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

## The rough-ground task

`Biped-Wheeled-Rough-v0` puts the same robot on a generated grid of 4 m tiles:
flat, bumpy, slopes up and down to a 0.25 grade, long waves, scattered blocks
and thresholds up to 15 mm, each in ten rows of difficulty. There are no
stairs, because the robot cannot step and a 40 mm wheel cannot climb one.
Robots start on the easy rows and move up after an episode survived with the
speed tracked, or down after a fall. The policy is also told a ride height --
hip to axle, 185 to 207 mm -- and is free to make its legs unequal, which with
no hip roll is the only way the robot can level its torso on uneven ground.
Its observations carry noise and a per-episode bias, and the shoves are larger
and twist it. It is still blind; only the critic gets a height map of the
ground. `rough_env_cfg.py` has the reasoning, including why about a centimetre
is the tallest step the wheel should be able to climb.

```
TASK=Biped-Wheeled-Rough-v0 bash $R --num_envs 4096 --max_iterations 3000
bash $R --evaluate --rough --policy .../wheeled_biped_rough/<run>/exported/policy.pt
```

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
bash $R --num_envs 4096 --max_iterations 1000        # about 20 minutes on a 4090;
                                                     # see Performance for the count
bash $R --play --num_envs 16 --video --video_length 600   # exports policy.pt and .onnx, films it
bash $R --evaluate --policy /workspace/runs/logs/rsl_rl/wheeled_biped_balance/<run>/exported/policy.pt
```

Runs land in `/workspace/runs/logs/rsl_rl/wheeled_biped_balance/`, with
TensorBoard logs, checkpoints every hundred iterations, and after `--play` the
exported policy and a video.

## Performance: how many robots, on which GPU

The right number of robots to simulate at once depends on the GPU and on the
CPU behind it, so measure it on every new kind of pod before a long run:

```
TASK=Biped-Wheeled-Rough-v0 RESUME=/workspace/runs/logs/rsl_rl/wheeled_biped_rough/<run>/model_<n>.pt bash /workspace/biped/simulation/isaaclab/runpod/benchmark.sh
```

It runs twenty training iterations at each robot count and appends the result
to `/workspace/runs/benchmarks.tsv` on the volume, which is the record across
cards. Give it a trained checkpoint: from scratch, robots fall and are reset
constantly, resets are the slow part of a step, and the numbers come out
upside down -- more robots measured slower.

| GPU, CPU | task | robots | steps/s | GPU busy | GPU memory |
|---|---|---:|---:|---:|---:|
| RTX PRO 4500 Blackwell, EPYC 7663 | rough | 4 096 | 47 400 | 47% | 6.2 GiB |
| | | 8 192 | 66 900 | 55% | 10.2 GiB |
| | | **16 384** | **87 400** | 63% | 19.6 GiB |
| RTX 4090 | flat | 4 096 | 75 000 | -- | 4.2 GiB |

On the RTX PRO 4500, train with 16 384 robots.

The RTX 4090 row is from the first training run's own log, not the benchmark.

**The GPU is never the limit here.** It sits near half busy at any robot
count, because every step is a long sequence of small GPU jobs launched one
after another by a single CPU thread -- physics substeps, sensors, the task's
observations and rewards -- and the GPU waits between them. More robots
make each job bigger for nearly the same launch cost, which is why throughput
rises with the count until memory or the thread gives out. A faster CPU core
helps as much as a faster GPU. And anything in the task that makes the CPU
wait on the GPU -- `.item()`, `.nonzero()`, `len()` of a mask -- costs a
little on every step; the task has none of its own, and should keep it that
way.

### Where a step's time goes, and what would shorten it

Timed phase by phase at 8 192 robots on the RTX PRO 4500, with the rough-ground
policy driving (129 ms a policy step):

| | ms per step | share |
|---|---:|---:|
| physics, four 2.5 ms substeps | 82 | 63% |
| reward terms | 13.5 | 10% |
| writing actuator commands to PhysX, four times | 11.7 | 9% |
| resets and the curriculum | 10.4 | 8% |
| observations, actions, sensors, terminations, policy | 11 | 9% |

Nothing is saturated: the GPU is 20-60% busy at half its power, memory
bandwidth about 10%, PCIe a few hundred MB/s, and the process uses about 1.6
of the pod's 28 cores -- while physics runs, mostly PhysX's own threads. It is
latency-bound: each stage waits for the one before, on whichever side of the
bus it runs. What would shorten it, largest first:

- **Physics at 200 Hz rather than 400.** Validated for balancing and driving:
  at 5 ms steps `run.py --check` passes with the robot standing at exactly
  317.0 mm and rolling on 39.3 mm, and `run.py --balance` recovers from its
  shove the same as at 2.5 ms, on the same 0.37 Nm peak and 0.02 Nm RMS. It
  halves the largest cost. NOT validated for landings, which are impacts, so
  the jump task stays at 400 Hz until it is.
- **Less physics per substep**: self-collision off, four position iterations
  rather than eight. Neither measured yet.
- **Leaner task code**: the reward terms, the command writes and the resets
  are over a quarter of the step.
- **A second training run on the same GPU**, which fills the gaps each leaves.

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
- **Rough ground overflows PhysX's contact buffer.** Four thousand robots on a
  terrain meshed at 5 cm need about 2.7 million contact patches against a
  default of 160 000, and the overflow ends a few seconds later in a CUDA
  illegal memory access. `rough_env_cfg.py` sizes the buffers.
- **Environments collide unless told not to.** With terrain, some twenty
  robots share each tile's start point, and on the GPU they were spawned
  inside one another -- every robot "fell" on its first step, with 2 800 N on
  its torso, and the simulation crawled. `rough_env.py` calls
  `scene.filter_collisions` explicitly; Isaac Lab's own examples only do so on
  the CPU.
- **More robots overflow more than the contact buffer.** At 16 384 robots
  PhysX's broad-phase pair buffers overflowed too, and those do not stop the
  run: PhysX logs one error saying it "will miss interactions" and carries
  on, wheels drop through the ground, and the resumed policy fell a hundred
  times as often as at 8 192 -- while the benchmark reported its best
  throughput yet. The pairs grow with the square of the robots sharing a
  tile's start point, so the terrain grid now widens with the robot count to
  keep 26 to a tile, and every buffer is sized per robot (`scale_terrain` and
  `size_gpu_buffers` in `rough_env_cfg.py`). `benchmark.sh` now refuses any
  result with a PhysX error in its log. Look for one in any run's log.
- **A policy that looks robust can be cheating.** The first two rough-ground
  policies scored 99% upright and had learned to stand with one wheel 11 cm
  ahead of the other -- two contacts in a line, so almost no pitch to balance --
  held there by one wheel spinning on the floor at up to 46 rad/s, in half the
  robots at any moment. Nothing in the survival or tracking numbers showed it;
  the wheel torque's RMS did, and a step-by-step trace of one robot explained
  it. The task now charges the fore-aft distance between the wheels and the
  speed of each tyre's contact point over the ground, and `evaluate.py
  --rough` reports both. Behind it was a third problem: with actions clipped
  at +/-1 before the environment saw them, the policy's wheel output had grown
  to +/-20 -- bang-bang control -- and its exploration noise to 1.56 at no cost.
  The wrapper no longer clips; the environment clamps and charges for asking
  beyond the range. Adding those costs to the cheating policy and resuming it
  did not work: it lost its balance unlearning them. It had to be retrained.
- **Isaac Sim 6.0 needs pre-releases.** Its core pins a release candidate of
  tinyobjloader, so `uv pip install` needs `--prerelease=allow`.

## What it does not establish

That the policy would work on the robot. It is trained against a plant whose
rotor inertia, velocity limit, wheel mass and ground friction are all
estimates, randomised because they are unknown. Randomising widens what the
policy tolerates; it does not tell anyone where the real robot sits in those
ranges. Measuring the actuator is still the most valuable next step for sim to
real, and `../README.md` lists what is unmeasured.
