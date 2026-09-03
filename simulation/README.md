# Simulation

The CAD, turned into something a physics engine can integrate: a URDF of the
six-motor wheeled robot, with the mass and inertia of every link worked out
from the same geometry the printer would get, and two ways of loading it — an
Isaac Sim project in [`isaacsim/`](isaacsim/) and an Isaac Lab articulation
config in [`isaaclab/`](isaaclab/).

Nothing here is typed in twice. Every dimension is read out of the KCL, every
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

Dimensions are re-read from the KCL on every build, so the kinematics can never
be stale. The meshes can be, because they are engine output — so the build
**refuses** to run against a mesh older than any KCL file in its import closure,
names the file that moved, and prints the re-export command for just the pieces
affected:

```
uv run tools/export.py --format stl --out simulation/meshes --pieces <those>
```

That is the only metered step in the pipeline, and only a printed part changing
*shape* needs it. Everything else is arithmetic.

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

All of it currently passes. The robot loads with the URDF's own masses and
inertia, its joints turn the way the CAD says, and it stands and rolls on a
40 mm wheel to within a third of a millimetre. See
[`isaacsim/README.md`](isaacsim/README.md) for the numbers and for what a
passing check still does not cover.

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
`wheeled_electronics.kcl` packs the pelvis with. Two of them are honest
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
`tools/views.py` fixes and what every KCL file assumes. A URDF is expected in
the ROS convention, **+X forward, +Y left, +Z up**, so everything in the URDF
has been turned a quarter turn out of the frame the mesh files are still in.
That rotation happens in exactly one place, `inertia.CAD_TO_ROS`, and the
meshes carry it as an `rpy` on each visual.

`base_link`'s origin is the **torso centre**, 306.5 mm above the floor with the
legs straight, because that is the frame `torso.kcl` and
`wheeled_electronics.kcl` are already drawn in.

Both leg joints are **positive in flexion**, the same sign as the angles in
`pose_check.kcl` and `squat_check.kcl`, so a pose read off one of those scenes
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
- **The actuator's velocity limit.** No vendor figure has ever been recorded in
  this project. The placeholder sets the robot's top speed.
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
`pose_check.kcl` and `squat_check.kcl` and compares where the wheel lands with
where those scenes independently compute it. That is a real test rather than a
restatement: the scenes do their own trigonometry in KCL, so agreement to a
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

What it cannot check is whether the geometry itself is right. That is `/check`
and `/views`' job, and it is unchanged by anything here.

## Files

| | |
|---|---|
| `kcl_params.py` | reads dimensions, and the palette, straight out of the KCL sources |
| `robot.py` | the kinematic tree and every gram, with provenance. The only file here carrying engineering judgement |
| `inertia.py` | mass, centre of mass and inertia tensors, from meshes and from primitives |
| `build_urdf.py` | writes `urdf/wheeled_biped.urdf` and the binary meshes it points at |
| `check_model.py` | the checks above |
| `plant.py` | the simulator-facing choices — actuator limits, contact, solver, where it starts. Both simulators read it, so neither states a number of its own |
| `isaacsim/` | an Isaac Sim project: the URDF turned into a rigged USD, and the checks that say whether PhysX agrees. See its own README |
| `isaaclab/wheeled_biped_cfg.py` | Isaac Lab articulation config, actuator model and contact settings |
| `meshes/` | raw engine output, untracked, regenerate with `/step --format stl` |
| `urdf/meshes/` | binary copies, tracked, so a checkout can be simulated without spending credits |
