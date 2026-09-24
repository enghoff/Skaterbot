# Isaac Sim

The robot, rigged and simulating. `../urdf/wheeled_biped.urdf` says what the
mechanism is; this directory turns it into a USD robot Isaac Sim can integrate,
puts it on a floor, and then measures whether the thing on the floor is still
the robot the CAD describes.

It is. Every check passes — see [what is proven](#what-is-proven) for the
numbers and for what they do not cover.

## Running it

Three steps, in order. The first is free and needs nothing but NumPy; the other
two need Isaac Sim's own Python, which on this machine is the pip venv at
`Z:\IsaacSim\venv` (Isaac Sim **6.0.1**).

```
python simulation/isaacsim/preflight.py

Z:\IsaacSim\venv\Scripts\python.exe -u simulation/isaacsim/import_urdf.py
Z:\IsaacSim\venv\Scripts\python.exe -u simulation/isaacsim/run.py --check
```

Then, to see it balance — legs frozen, upright on its wheels:

```
Z:\IsaacSim\venv\Scripts\python.exe simulation/isaacsim/balance.py        # the design, no simulator
Z:\IsaacSim\venv\Scripts\python.exe -u simulation/isaacsim/run.py --balance
Z:\IsaacSim\venv\Scripts\python.exe -u simulation/isaacsim/run.py         # no controller, so it falls
```

`balance.py` needs only NumPy and SciPy — no `SimulationApp` — so it runs in a
second and the whole control design can be checked before a simulator is
started.

**Pass `-u`.** Kit shuts the process down hard enough to discard buffered
stdout, so without it a completed run can print nothing at all and look like a
silent crash.

Rebuild after every `/urdf` run. The USD is generated output, is not tracked,
and editing it by hand is wrong for the same reason editing the URDF is.

## What "rigging" adds that the URDF cannot say

A URDF describes a mechanism. It has no way to say how that mechanism should be
simulated, and four of those choices decide whether the simulation means
anything:

- **Torque control.** Every joint in force mode with zero stiffness and zero
  damping, because a DM-J3507 in MIT mode takes a torque. The 6.0 importer can
  do this itself and is asked to, via `joint_drive_type="force"` and
  `joint_target_type="none"`. Left at the default the joints arrive with a
  position drive, and a robot quietly holding its own pose looks like it
  balances.
- **The reflected rotor inertia.** 7:1 multiplies the rotor's own inertia by 49
  at the joint, which on these wheels is several times the wheel's spin
  inertia. Applied as joint armature. The importer has no setting for it at
  all, and leaving it out does not make the model slightly wrong — it makes the
  wheels a different plant.
- **The contact.** A urethane friction material bound to the two wheel
  colliders, which are the only things touching the floor.
- **Solver settings.** 2.5 ms steps, so a wheel at full speed covers 2 mm a
  step; CCD on; nothing allowed to fall asleep, because a balancing robot that
  goes to sleep has fallen over.

All four come from [`../plant.py`](../plant.py), which the Isaac Lab config
reads as well. Neither simulator states a number in its own right, so they
cannot be given different robots by someone editing one of them.

## What is proven

Everything below was run. `run.py --check` exits non-zero on any failure.

| | |
|---|---|
| The URDF is loadable and agrees with the CAD | **passes** — `preflight.py`, offline |
| The USD carries the URDF's own masses and inertia | **passes** — all seven links match mass, centre of mass and principal moments; `import_urdf.py` refuses to save otherwise |
| All six joints exist with the declared travel | **passes** |
| The armature reached PhysX | **passes** — 2.300e-04 kg m² read back off every joint |
| The joint signs match the CAD | **passes** — hip +17° moves the wheel **+62.1 mm forward**, knee +17° moves it **−31.0 mm back** |
| The wheel is a 40 mm cylinder, statically | **passes** — settles at **306.5 mm**, the CAD's figure, to **+0.0 mm** |
| It rolls on 40 mm | **passes** — **40.3 mm** measured over 11.4 rad and 459 mm of travel |
| It balances, legs frozen | **passes** — 15 s upright, recovers a 0.3 m/s shove, peak 0.28 Nm a wheel. See [below](#it-balances) |
| It can walk, steer, or recover from a real fall | **no**, and nothing here claims it |

The rolling figure is 0.3 mm above the CAD's 40.0, which is tyre slip over the
0.8 s window rather than a geometry error; the static check, which cannot slip,
lands exactly.

## It balances

With the hips and knees frozen the robot is a wheeled inverted pendulum, and
`run.py --balance` holds it up on wheel torque alone. It survives 15 s, absorbs
a 0.3 m/s shove at 2 s, and comes back to within 10 mm of where it started:

```
  t=  2.0s  SHOVED at 0.3 m/s
  t=  2.5s  lean  -1.98 deg  ground  +103.5 mm
  t=  4.5s  lean  -0.03 deg  ground  +100.6 mm
  t= 14.5s  lean  -0.05 deg  ground    +9.4 mm
  upright after 15 s: lean -0.06 deg, base at 306.5 mm
  torque per wheel: peak 0.28 Nm, rms 0.01 Nm
```

Two numbers out of that are worth carrying into the design.

**The robot falls with a 106 ms time constant.** That is the open-loop unstable
pole, and it is how long any controller — or any policy, or any CAN round trip
— has to notice a lean and answer it.

**It is traction-limited, not torque-limited, and by a wide margin.** Peak
usable torque is μ·m·g·r ≈ **0.56 Nm across both wheels**, against a 1.6 Nm
thermal budget and a 6 Nm peak. The wheels break loose long before the
actuators strain, so balancing costs about a third of the thermal rating at
worst and a hundredth of it at rest. On this evidence the DM-J3507 is
comfortably oversized for balancing; what it is sized for is the leg joints and
whatever the robot does besides stand still.

That second point was learned the hard way. The first controller was weighted
against the 3 Nm actuator peak, saturated from the first step, turned the loop
bang-bang, and lost the robot after 6.8 s. Weighting against traction instead
dropped the fastest closed-loop mode from 275 rad/s to 39 and the RMS torque to
0.01 Nm.

Caveats worth keeping in view: this is a linear controller about upright, so it
says nothing about recovering from a large fall; both wheels are driven
together, so it cannot steer; and the friction it is tuned against is a guess,
which matters more here than anywhere else, because friction is what sets the
ceiling.

## Why the checks are built the way they are

This project's rule is that execution is not evidence. Isaac Sim will happily
simulate a robot whose wheels are the wrong radius, whose joints turn the wrong
way, or whose armature never arrived, and none of that raises an error. So
`--check` measures rather than asks, and the first version of it was wrong in
two instructive ways:

- **The robot fell over.** Released on its wheels it is an inverted pendulum
  with no controller, so after a 1.5 s settle it was on its side: 89° of torso
  pitch, a "standing height" of 34 mm and a rolling radius of 25 mm. All three
  numbers were real and all three were meaningless. The checks now run the
  robot on a **gantry** — a world joint that lets it slide but not rotate. Like
  locking the legs, that is a property of the test and never of the robot.
- **The wheel angle wraps.** `wheel_drive_*` is a continuous joint, so PhysX
  reports its position folded into ±π. A wheel that had turned 11.4 rad read as
  −1.2, and the rolling radius came out as −389 mm. The test now accumulates
  per-step differences instead of differencing the total.

## Two Isaac Sim traps worth knowing

Both cost a run to find, and neither produces a useful error message.

- **Never wrap an articulation link in a `SingleRigidPrim`.** Creating a
  rigid-body tensor view over a prim that is already part of an articulation
  view invalidates the articulation's view. The run then dies at the next step
  with the wheel's collider reported as *deleted*, which is not what happened.
  Ask the articulation for its own link transforms instead — `LinkProbe` in
  [`run.py`](run.py).
- **`GroundPlane` takes a `PhysicsMaterial` object**, not `static_friction=` /
  `dynamic_friction=` keywords.

Also version-specific: the 6.0 importer is `URDFImporter` / `URDFImporterConfig`.
The `URDFParseAndImportFile` kit command that 4.5 and 5.x used is gone, so this
will not run on those without being rewritten back to it. `isaacsim.core.api`
still works in 6.0 but has moved to `extsDeprecated`.

## Files

| | |
|---|---|
| `preflight.py` | everything checkable without Isaac Sim. Free, offline, needs only NumPy |
| `import_urdf.py` | URDF to a rigged USD, with a mass-and-travel comparison it refuses to save past |
| `balance.py` | the wheeled-inverted-pendulum model and its LQR gains, both derived from the URDF. NumPy and SciPy only, no simulator |
| `run.py` | the floor, the checks, and the balancing |
| `usd/` | generated output, untracked. Rebuild it after every `/urdf` |

## What it still turns on that nobody has measured

A passing rig check makes this easy to forget, so it is worth repeating: the
check proves the simulator is integrating the robot the CAD describes. It says
nothing about whether that description is right where the CAD never knew.

The actuator's rotor inertia and torque-speed curve have never been measured, the
wheels have never been weighed, and the friction of this urethane on any floor
is a guess. Randomise over them — the ranges are in `plant.py` — rather than
trusting them. Hip pitch also has no established travel: the ±60° in the URDF
is provisional, and the knee's 110° commissioning stop is the only joint limit
this project has ever justified.
