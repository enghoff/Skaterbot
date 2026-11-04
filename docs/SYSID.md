# Measuring the robot for the simulator

The policies were trained on a simulated robot whose motors are partly guessed.
This is how the real ones get measured, and the software that does it: a runner
on the Banana Pi that plays scripted inputs to the motors and logs everything
that comes back, and fitting tools on a PC that replay each log through a model
and find the numbers that make the model move as the robot did. What comes out
replaces the guesses before the next round of training.

## What is guessed, and what measures it

| The simulator assumes | Now | Measured by |
|---|---|---|
| The motor's rotor inertia, felt at the joint | 2.3e-4 kg m², estimated; several times a wheel's own | A2, B1, B2 |
| Torque at speed | a straight line from 3 Nm at standstill to none at 48.2 rad/s | A3 |
| Delays | IMU 0–10 ms, encoders 0–5, commands 0–5 | A2, A4, B4 |
| Joint friction and damping | zero | A2, B1, B2 |
| Torque delivered against torque commanded | equal | A1, A2, B1 |
| The battery's effect on top speed | ×0.75–1.05 | A3, full and near cut-off |
| The motors' own position loop on the legs | an ideal spring and damper | B1 |
| Floor grip | 1.0, trained across 0.6–1.4 | C1 |
| Sensor noise and bias | 2 % of each reading's range | B3 |
| How the mass is spread | weighed, inertia from the CAD | B3's free swing |

## What exists, and what it has been checked against

Nothing here has run on the robot yet.

- `sbc/sysid_tests.py` holds the tests: each a list of segments, each segment a
  few seconds of MIT-mode commands, and the limits that stop the test. It also
  defines the log format. Standard library only.
- `sbc/sysid.py` runs a test on the robot through diagd, and `map` (below).
  Standard library and pyserial, which the Pi already has.
- `simulation/sysid/fit_bench.py` fits stage A, `fit_hung.py` stage B,
  `logfile.py` reads a log, `actuator.py` is the motor model, `rig.py` the
  hanging robot in MuJoCo.
- `simulation/sysid/synth.py` runs any bench or hanging test against a model
  whose answers are known, with the robot's timing, quantisation and clocks,
  and writes the log the robot would.

On synthetic logs the fits find what was put in:

| | Put in | Found |
|---|---|---|
| Motor's inertia at the output (A2, two loads) | 3.10e-4 kg m² | 3.10e-4 |
| Coulomb friction | 0.035 Nm | 0.0349 |
| Viscous friction | 6.0e-4 Nm s/rad | 6.1e-4 |
| Torque delivered / commanded (A1 and A2 agree) | 0.93 | 0.930 |
| Command to torque | 0.9 ms | 1.0 ms |
| Torque-speed line (A3) | 2.79 Nm, 44.0 rad/s | 2.79, 43.9 |
| Leg armature (B1, hanging) | 3.0e-4 kg m² | 3.06e-4 |
| Leg friction | 0.030 Nm | 0.0300 |
| Leg damping | 0.0020 Nm s/rad | 0.0013 |
| Torque scale, from gravity on the hanging legs | 0.95 | 0.951 |
| Wheel armature (B2, wheels spinning in the air) | 2.8e-4 kg m² | 2.77e-4 |
| Wheel friction | 0.025 Nm | 0.0254 |
| Wheel damping | 8.0e-4 Nm s/rad | 8.1e-4 |
| IMU lag (B1, B4) | 4 ms | 4.0 |
| Free swing on the rail (B3) | 0.984 s, the model's | 0.980 |

Leg damping is the weak one: small, and partly traded against friction. Each
hanging test fits only what it moves: B1 and B4 the legs, B2 the wheels, B3
nothing of the motors. B3 prints instead how much each reading wanders while
the robot is held still, against what training already covers.

The runner has been run through diagd against `sbc/diag_sim.py`'s simulated
controller: tests A2 and A4 at 500 Hz and 1 kHz, every command answered,
nothing dropped. Whether the real link carries 1 kHz with six motors on it is
for the robot to say; the end of every run prints what was dropped.

## Equipment

- **Bench (A):** a spare motor, or one off the robot, clamped. A bar bolted to
  its output (six M3) and a kitchen scale, for A1 and A5. A balanced disc or bar
  of known inertia, about 0.005 to 0.02 kg m², for A2 and A3: a steel plate
  Ø200 × 6 mm is 0.009 kg m². Work its inertia out from its weight and
  dimensions, and guard it: A3 spins it to 50 rad/s.
- **Hanging (B):** a rod through both hoist lugs' eyes, resting on the rail, so
  the robot can only pitch about the line between them. Legs and wheels free of
  everything.
- **Floor (C):** a luggage scale, the slack safety line, and a hand on the
  robot.

## Running it

First, once and again whenever a motor is moved or re-zeroed:

    python3 sysid.py map

With the motors off, it asks for each joint to be moved by hand, finds which
motor turned and which way, takes each leg's zero hanging straight down, and
finds the IMU's axes. Its accelerometer says which way is up, and its gyro,
while you tip the robot nose-down on the rail, says which way is left. It
writes `sbc/sysid_robot.json`, and no robot test runs until it exists.

Then, straight after it:

    python3 sysid.py level

`map` takes the IMU's up and the legs' zeros from the robot as it hangs, and the
first run, on 4 November 2026, showed neither is good enough that way. The
joints' friction holds a hanging leg anywhere in a band several degrees wide:
the left knee came back 6 degrees from where it started. And the IMU's forward
came out 10 degrees off, because the gyro also counted the robot turning on the
rail as it was tipped. So `level` takes the IMU's up with the torso held level
by a phone's level app, read both ways round so the phone's own error cancels,
and its forward from the accelerometer alone. Then each leg joint is pushed
one way and let settle, then the other, and its zero is the middle of the two,
allowing for the torso's pitch and, at the hip, for the shin hanging off
straight. Driven against a made-up robot it finds the zeros exactly and the
IMU's axes to within a quarter of the rail's own side-to-side slope. What `map`
found is kept in the file under `map`. `level --legs` does the legs alone and
keeps the file's IMU axes; every place a leg settled is kept with the
accelerometer as read, so `leg_zeros` can work the zeros again from better
axes.

The leg motors' own zeros were set on 4 November 2026, legs straight down by
eye, because at power-up a motor knows its position only within one turn and
the right knee's factory zero put the edge of that turn where its leg hangs
(reference/motors/README.md). The IMU board sits about 6 degrees nose-up and 5
degrees turned on its mount: the torso hung level to half a degree by a phone
while the accelerometer read that far off its own axes.

### What the first day on the rail found, 4 November 2026

Hung by a string from each hoist lug, 55 cm to a fixed anchor, and later by a
V of two strings per lug; the logs are named by date and test.

- **The rig.** On single strings the robot swings as a double pendulum, string
  and all: 1.65 s measured, 1.71 s from the model with the strings in it, which
  is the first check of the robot's mass and its distribution. In the V it no
  longer swings, but its legs' kicks still pitch it through a few degrees.
- **Leg friction** about 0.045 Nm on every leg joint, from the slow sweeps
  (B5) and the leg fit alike; the simulator has none. The joints also stick
  before they move.
- **Gravity on the legs** takes 9 to 14 per cent more torque than the model
  says: the legs heavier or lower-slung than modelled, or the torque reading
  high.
- **Zeros.** The hips are where they were set, within 0.3 degrees; the knees
  3.1 (right) and 1.4 (left) degrees more folded than they read, corrected in
  sysid_robot.json. Over the hips' sweep a zero error and a torque-reading
  offset are indistinguishable; the knees show no offset, and the hips are
  taken to have none.
- **The IMU reads about 16 ms behind the motors**: three runs agree, from the
  torso's jolts against the hips' own torque reports, and so does a fit of the
  swinging robot. Training allows at most 10 ms.
- **Stiff legs buzz.** At kp 40 kd 1.0 (B4) and kp 48 kd 1.6 (B1's stiffest)
  the hips settle into a 39 Hz shake near 1 Nm that lasts as long as the
  command. At the policies' kp 12 kd 0.4, and at kp 3, they are quiet. The
  simulator shows no such thing, so training must stay well below it. B4 is
  not to be run at its present gains again; B1 runs with `--gains
  3,0.1,12,0.4`.
- **Sensor noise** is far under what training assumes: gyro 0.007 rad/s
  against 0.08, gravity 0.001 against 0.02, leg angle 0.0001 rad against 0.02.
- **The IMU board's attitude**, measured afterwards on a table
  (reference/motors/imu_captures_2026-11-04.json): 5.9 degrees nose-up, 1.0
  turned right, 0.8 rolled. The shell was level to 0.4 degrees by a phone read
  at two headings, and the forward axis came from a 43.2 degree nose-down tip
  with the side-to-side reading held at zero. The rail had given the same tilt
  to 0.3 degrees but a 4.7 degree turn, from a tip by hand that was not purely
  about the side-to-side axis. These are the axes in sysid_robot.json.
- **The IMU over-reads a big tilt by about 7 per cent**: the 43.2 degree tip
  read 46.5, and on the rail a tip the hips put at 44 to 48 read 50.6, its
  accelerometer reading 2.5 per cent less in total when tipped than level. Near
  upright that is well inside what training tolerates; the BNO085's own
  accelerometer calibration is where to look if it matters.
- **The IMU sometimes starts dead after power-up**: found, answering its
  product ID, but taking no feature request and sending nothing, until a
  power cycle. Once running it has not failed.

Then the tests, on the Pi, beside diagd; `python3 sysid.py list` describes each:

    python3 sysid.py A1 --motor C:1 --arm-mm 150           # and again with --negative
    python3 sysid.py A2 --motor C:1                        # bare
    python3 sysid.py A2 --motor C:1 --load-inertia 0.009 --label disc
    python3 sysid.py A3 --motor C:1 --load-inertia 0.009   # full pack; again near cut-off
    python3 sysid.py A4 --motor C:1
    python3 sysid.py A5 --motor C:1 --arm-mm 150
    python3 sysid.py B1                                    # or --joint knee_right
    python3 sysid.py B2
    python3 sysid.py B3
    python3 sysid.py B4 --repeats 10
    python3 sysid.py C1 --repeats 5

Each writes `~/sysid_logs/<when>_<test>.jsonl`. Copy them to the PC and fit:

    uv run simulation/sysid/fit_bench.py A1*.jsonl A2*.jsonl A3*.jsonl A4*.jsonl A5*.jsonl
    uv run simulation/sysid/fit_hung.py B1.jsonl --bench fit/fit_bench.json
    uv run simulation/sysid/fit_hung.py B2.jsonl --bench fit/fit_bench.json
    uv run simulation/sysid/fit_hung.py B3.jsonl
    uv run simulation/sysid/fit_hung.py B4.jsonl --bench fit/fit_bench.json

A wheel spinning in the air shows only the ratio of torque to inertia, so B2
holds the torque scale rather than fitting it: the bench's from `--bench`, or
B1's from `--scale`. Without either it says the scale is assumed.

Each prints its results against the simulator's current figures, and writes
them as JSON with plots beside them. To see what a test will do before running
it, or to check a fit, run it synthetically first:

    uv run simulation/sysid/synth.py B1 --out runs/B1.jsonl

Before the hanging and bench tests, set every motor's VMAX to 55, its
communication timeout and its undervoltage trip, as
[POLICY_INTERFACE.md](POLICY_INTERFACE.md) says. The runner refuses a test that
could pass VMAX, since a report's speed wraps round past it.

## What stops a test

Every motor is stopped, and the log says why, if one faults, its winding passes
90 °C, it goes faster than its test allows, a leg leaves its window (hips −0.7
to 0.9 rad, knees −0.15 to 1.55), or it stops answering for 0.1 s; and on
Ctrl-C. diagd stops them if the runner goes quiet for half a second, the
controller if diagd does for 0.3 s, and the power button at any time.

## Not built yet

- **C2 and D**, the balance controller and the policy on the floor, need
  something on the robot that runs them and logs as this does. That is the
  robot firmware, which does not exist yet; its telemetry should be this log
  format, so the same tools read it.
- **Coast-down** on the floor needs the robot balancing, so it waits for that
  too.
- **Feeding the results into training** is by hand, once there are results:
  the armature, friction and damping go into `simulation/robot.py`'s
  `ACTUATOR`; the torque-speed line into its peak and no-load speed; the
  delays, battery range and noise into the task configuration and
  `simulation/plant.py`'s `DOMAIN_RANDOMISATION`, narrowed to a little more
  than the spread between repeat runs; and the training history records the
  fine-tune that follows.
