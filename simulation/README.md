# Simulation

The CAD, turned into something a physics engine can integrate: a URDF of the
six-motor wheeled robot, with the mass and inertia of every link worked out
from the same geometry the printer would get, and two ways of loading it — an
Isaac Sim project in [`isaacsim/`](isaacsim/) and an Isaac Lab articulation
config in [`isaaclab/`](isaaclab/).

Nothing here is typed in twice. Every dimension is read out of `cad/`, every
printed mass is integrated from the exported mesh at PA12-CF density, and every
bought mass comes from `tools/mass_budget.toml` — the same table `/mass` rolls
up against the robot's 2 300 g ceiling. Change the CAD and regenerate; do not
edit the URDF.

## Regenerating it

`/urdf` does the whole thing, and it is free:

```
uv run simulation/build_urdf.py
uv run simulation/check_model.py
```

Dimensions are re-read from `cad/` on every build, so the kinematics can never
be stale. The meshes can be, because they are exported output — so the build
**refuses** to run against a mesh older than any file in `cad/`,
names the file that moved, and prints the re-export command for just the pieces
affected:

```
uv run tools/export.py --format stl --out simulation/meshes --pieces <those>
```

That used to be the one metered step in the pipeline and is now free, and only a printed part changing
*shape* needs it. Everything else is arithmetic.

The meshes are the pieces **as they would be printed**, arrises broken at 0.5 mm
by `cad/finish.py`, which is the exporter's default rather than something this
pipeline asks for. It costs about a gram across the robot, and it means the
collision geometry is the part that gets made rather than the part before it is
finished.

## Simulating it

Rebuild the Isaac Sim robot after every `/urdf` run, and check what PhysX made
of it:

```
python simulation/isaacsim/preflight.py                             # free, offline
Z:\IsaacSim\venv\Scripts\python.exe -u simulation/isaacsim/import_urdf.py
Z:\IsaacSim\venv\Scripts\python.exe -u simulation/isaacsim/run.py --check
```

`preflight.py` is worth running on its own after a rebuild: it needs nothing
but NumPy and it catches a URDF that was never going to load. The other two
need Isaac Sim's own Python — here, the 6.0.1 venv at `Z:\IsaacSim\venv`.

**You cannot forget the rebuild.** The USD is not the URDF, and a USD left
behind by a `/urdf` run is the one failure here that raises nothing: it loads,
the rig checks pass, and every number faithfully describes the robot as it was
before the CAD moved. So `run.py` now refuses a USD older than the URDF or
meshes it was built from — naming what moved and printing the rebuild command,
the same way `build_urdf.py` refuses a mesh older than the CAD it came from — and
`preflight.py` says so for free before anyone spends five minutes starting Kit.
`--allow-stale` overrides it and prints a warning that the numbers are not the
current CAD.

All of it currently passes. The robot loads with the URDF's own masses and
inertia, its joints turn the way the CAD says, and it stands and rolls on a
40 mm wheel to within a third of a millimetre. See
[`isaacsim/README.md`](isaacsim/README.md) for the numbers and for what a
passing check still does not cover.

### Driving a trained policy, on this machine

```
uv run simulation/mujoco/drive.py                       # a window; keyboard or game controller
uv run simulation/mujoco/drive.py --check               # no window: the robot run to its limits
uv run simulation/mujoco/drive.py --run exports/rl/<run>
uv run simulation/mujoco/drive.py --rough 1             # the rough task's ground, at its hardest
```

Isaac Sim will not run here, so a trained policy is driven in MuJoCo instead,
on the CPU, free. It takes a run directory from `exports/rl/` — the exported
policy and the `params/env.yaml` Isaac Lab saved when it trained it — and reads
from that file everything about how the policy was trained: its action scales,
leg gains, the crouch it balances around, the motor's torque-speed line and the
physics step. So nothing in it is a second copy of a task number. The robot is
this directory's URDF. The keys are printed when it starts and listed at the top
of the script; a jump policy gets a jump button.

Full stick, or the last key press, is the most the policy was trained on, and
for the jump task that is the motors' whole envelope — the wheels at their
no-load speed, and every jump as high as it was trained to — so the robot can
be driven to its mechanical limits and to the policy's. The overlay shows how near the motors
are to theirs: wheel speed against the no-load speed, and peak torque against
the 3 Nm peak. `--check` does the same without a window: top speed each way,
the fastest spin, an arc, and a jump standing and one at speed, with
what was held against what was asked and the motors' peaks for each.

It is also a test. MuJoCo's contact and friction are not PhysX's, so a policy
that drives here as it did in training has not merely learned PhysX. The
rough-ground balance policy passed first time, with no tuning: 20 s of standing,
driving at ±0.3 m/s and turning, never tilting past 7.5°. The default policy
is now nine fine-tunes on from it (`isaaclab/TRAINING_HISTORY.md`
has the chain): the jump policy trained to the motors' envelope, then with
the robot's delays, a battery it is told the voltage of, a reward for standing
still, the jump scored on the whole robot's rise, a ride height it follows,
and steps to drive down. In `--check` it holds any slow turn it is asked
for, spins at 19 rad/s, and tops out at 0.99 m/s forward and 1.23 back, with
no falls; top speed is its weak point, and stage 7 reached 1.33 m/s
forward. `--steps 0.06` starts it on a pyramid of 60 mm steps.

**Its jump is mostly a tuck.** The wheels clear about 80 mm, but the torso
rises only 22-30 mm and the whole robot's centre of mass about 30: the rest
is the shins pulled up. The policies before stage 7 cleared about 100 mm the
same way, pitching about 50° as the legs swung up. `--check` reports the
rise, the pitch and how far apart the wheels left the ground for each jump.
`scripted_jump.py`, which holds the torso level through the jump, found a
crouch first would not raise it much on the simulator's torque-speed line;
but a policy that happened to ride at 160 mm (`steps`, in the training
history) pushed off for real, its centre of mass up 68 mm and its wheels
clearing 101-114 mm, pitching 39-44°. So a better jump is there, and that
search was too narrow. None of
it says anything about the real robot's unmeasured numbers, which are the same guesses here.

```
uv run simulation/mujoco/drive.py --delay-ms 5,2.5,2.5  # IMU, encoders, command
uv run simulation/mujoco/drive.py --battery 0.8         # motors at the pack's cut-off
uv run simulation/mujoco/drive.py --no-hold             # the policy alone when standing
```

Three things the robot will add that training once left out can be put back.
**The delays** between a sensor reading and the policy seeing it, and between
the policy's answer and the motors acting on it, rounded to 2.5 ms physics
steps; the adopted policy, trained without any, rocks 1.5° at 5 / 2.5 / 2.5 ms
and 13° at twice that. **The battery**, as the motors' no-load speed against
the rated 24 V's. And **a hold** on heading and place while no speed or turn is
asked for, on by default: the policy sees only its turn rate, so standing
alone it creeps and turns — 557 mm and 93° in 20 s — and the hold, from the
IMU's heading and the wheels' odometry alone, keeps that to 27 mm and 1.3°.
It is the loop outside the policy the robot needs, and `--check` ends with a
stand each way. [`docs/POLICY_INTERFACE.md`](../docs/POLICY_INTERFACE.md) is
what the firmware has to reproduce.

## What it says the robot is

| | |
|---|---|
| Six actuated joints | hip pitch, knee and a driven wheel on each leg |
| Standing height | 339 mm |
| Track, contact patch to patch | 170 mm |
| Wheel | Ø80 skate wheel, so a 40 mm rolling radius |
| Mass | see `check_model.py`; the ceiling is 2 300 g |
| Actuator | DAMIAO DM-J3507-2EC, 7:1, 3 Nm peak and 0.8 Nm continuous |

There is no hip roll. Nothing on this robot can lean the torso over a wheel, so
its only lateral authority is driving the two wheels differentially. It is a
wheeled inverted pendulum with a two-joint leg under each wheel, and a
locomotion task written for a walking biped will not fit it.

## What is in it, and not only what it weighs

The whole robot is drawn, not just the six printed pieces. The actuators, the
skate wheels, the bearings and journals, the boards and the power entry are all
in the URDF as geometry, in the CAD's own colours — so a simulator shows the
machine rather than an orange skeleton with invisible wheels, and anyone opening
the file can see that the thing accelerating the robot is mostly motor.

None of that is a second drawing of the CAD. Each bought part is the SAME
primitive its mass and inertia were computed from, so the picture and the
physics cannot drift apart: the actuator is the 46 x 37.9 can the vendor manual
gives, the wheel is the Ø80 x 24 tread, the boards are the reserved envelopes
`cad/electronics.py` packs the pelvis with. Two of them are honest
approximations and the URDF says so where they appear — the wheel's urethane is
an annulus drawn as a solid cylinder, because a URDF has no tube, and the wiring
is 27 g spread through the cavity, so it has mass but nothing to draw. Every
visual also carries a comment naming the part, its mass and where that mass came
from, which puts the provenance in front of the person loading the robot rather
than only in `check_model.py`'s output.

Collision is still deliberately coarse — a box for the pelvis, a box for each
limb, a cylinder for each wheel — with one addition the shell does not cover:
the two hip actuators hang below the pelvis floor and stick out past its sides,
so they collide as their own cylinders. Everything else bought is inside a
primitive that is already there.

## Conventions, because they are the easiest thing to get wrong

The CAD is drawn with **+Y forward and +X to the robot's right**, which is what
`tools/view.py` names and what every module in `cad/` assumes. A URDF is expected in
the ROS convention, **+X forward, +Y left, +Z up**, so everything in the URDF
has been turned a quarter turn out of the frame the mesh files are still in.
That rotation happens in exactly one place, `inertia.CAD_TO_ROS`, and the
meshes carry it as an `rpy` on each visual.

`base_link`'s origin is the **torso centre**, 306.5 mm above the floor with the
legs straight, because that is the frame `cad/torso.py` and
`cad/electronics.py` are already drawn in.

Both leg joints are **positive in flexion**, the same sign as the angles in
`cad/poses.py`, so a pose read off one of those scenes
can be commanded here unchanged. Hip flexion swings the thigh forward and knee
flexion folds the shin back under it; those are opposite senses in the sagittal
plane, which is why the two joints carry opposite axis vectors. A positive
wheel angle rolls the robot forward.

## How much of this is actually known

`check_model.py` ends with a table of mass by provenance, and it is the most
important thing this directory produces. Only a fifth of the robot's mass is
measured geometry; a further 57 per cent is the actuators, on the vendor's
figure, which is trustworthy enough. What is left — about 360 g of estimate and
assumption — is where the risk is, along with four numbers that are not mass at
all and decide whether a policy trained here transfers:

- **The actuator's rotor inertia.** A 7:1 reduction reflects it to the joint
  multiplied by 49, which on these wheels is several times the wheel's own spin
  inertia. Leaving it out does not make the model slightly wrong, it makes the
  wheels a different plant. It is in as an estimate; get it from DAMIAO or from
  a spin-down test.
- **The actuator's torque-speed curve.** The no-load speed is the vendor's,
  48.2 rad/s, but the simulators draw a straight line from the 3 Nm peak down to
  it, and the real curve holds its peak further up the speed range. It decides
  how fast the robot can accelerate and how high it can jump.
- **The wheel's mass.** Catalogue-typical, never weighed, and its spin inertia
  is what the balance controller works against.
- **Ground friction.** 85A urethane on a floor, with the crowned tread modelled
  as a plain cylinder. Randomise over it rather than trusting it.

Two further gaps are geometric rather than physical. **Hip pitch has no
established travel** — the ±60° in the URDF is provisional, and the knee's 110°
commissioning stop is the only joint limit this project has ever justified. And
**the torque envelope has not been re-derived for wheels**: `docs/PLAN.md`'s
figures are the walking robot's.

## What is checked, and how

`check_model.py` drives the kinematic tree to the exact hip and knee angles in
`cad/poses.py`'s `pose_check` and `squat_check` and compares where the wheel lands with
where those scenes independently compute it. That is a real test rather than a
restatement: the scenes do their own trigonometry, and `tools/gate_f.py` holds
that trigonometry against what the KCL computed before it was ported, so
agreement to a
micrometre exercises the link lengths, the joint origins, the axis directions
and the sign of every joint at once. A flipped axis shows up as tens of
millimetres.

It also checks that the model's total mass matches the budget's, that no link
has an inertia tensor whose principal moments break the triangle inequality,
and that every mesh it integrates is watertight.

The check that guards the workflow rather than the physics is the piece count.
Every printed piece the robot is built from is registered in
`tools/mass_budget.toml` with how many of it the robot carries, and the model is
counted for how many it actually places. A part added to the robot and never
added to the model would otherwise pass everything else here, because a link
that does not exist has no mass to be wrong about.

What it cannot check is whether the geometry itself is right. That is the job of
`/check` and the six gates in `tools/`, and it is unchanged by anything here.

## Files

| | |
|---|---|
| `cad/dimensions.py` | reads every dimension, and the palette, straight out of the CAD (in `cad/`, not here) |
| `robot.py` | the kinematic tree and every gram, with provenance. The only file here carrying engineering judgement |
| `inertia.py` | mass, centre of mass and inertia tensors, from meshes and from primitives |
| `build_urdf.py` | writes `urdf/wheeled_biped.urdf` and the binary meshes it points at |
| `check_model.py` | the checks above |
| `plant.py` | the simulator-facing choices — actuator limits, contact, solver, where it starts. Both simulators read it, so neither states a number of its own |
| `isaacsim/` | an Isaac Sim project: the URDF turned into a rigged USD, and the checks that say whether PhysX agrees. See its own README |
| `isaaclab/` | Isaac Lab 3.0: the articulation config, the balance-and-drive training task, the evaluation that scores a trained policy, and the scripts that stand it up on a RunPod GPU. See its own README |
| `mujoco/drive.py` | drives a trained policy locally in MuJoCo, from the keyboard or a game controller |
| `meshes/` | raw exporter output, untracked, regenerate with `/step --format stl` |
| `urdf/meshes/` | binary copies, tracked, so a checkout can be simulated without rebuilding them |
