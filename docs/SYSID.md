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
- **The wheels** (B2, in the air) spin up like a wheel with 8.4 to 8.9e-4 kg m2
  on its joint, nearly four times the simulator's 2.3e-4, and lose 0.010 to
  0.018 Nm to friction and 0.005 Nm s/rad to drag, so that 0.1 Nm holds one
  at about 15 rad/s rather than taking it to full speed. The command reaches
  the torque 4 to 8 ms late; the fits can hardly tell the two apart. Those
  numbers, as ranges, are simulation/plant.py's MEASURED, which the driving
  task trains on.
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
    python3 sysid.py W1 --joint wheel_drive_right --hold-torque 1.5 --hot-c 70 --yes

W1 measures a motor's torque against speed with nothing taken off the robot, since there is no spare motor for A3: one wheel, the robot on a table with its legs off, spun up from standstill at full torque hands-off, then pushed at a steady 1.5 Nm while a gloved hand slows the tread from its top speed. The wheel motors are the knees' model, so this is the knees' curve too.

**What W1 found, 6 November 2026**, on the right wheel with the pack at 24.7-24.9 V
(nearly full), the winding never past 60 °C. Pushing at 1.5 Nm while a hand slowed
the wheel, the torque it delivered was:

| Speed, rad/s | up to 37.5 | 37.5-40 | 40-42.5 | 42.5-45 | 45-47.5 | 47.5-50 | 50-52.5 | 52.5-55 |
|---|---|---|---|---|---|---|---|---|
| Torque, Nm (median) | all 1.5 asked | 1.41 | 1.20 | 0.99 | 0.81 | 0.52 | 0.29 | 0.10 |

Above 37.5 rad/s that is a straight line, 0.09 Nm less for every rad/s, reaching
nothing at 54-55 rad/s, which is also the top it reached spinning free. In Isaac
Lab's DC-motor form that is a saturation torque of 4.95 Nm and a speed limit of
55 rad/s, under the 3 Nm effort limit, where the simulator has had 3 Nm and
48.2 rad/s: at 40 rad/s the motor gives 1.2-1.4 Nm and the simulator allowed 0.5.
Where the line meets 3 Nm, about 22 rad/s, is extrapolated: the full-torque
spin-ups were over too quickly, about 40 ms, for the motor's torque to rise to
3 Nm, so the peak itself is still the manual's figure. A nearly flat pack has not
been measured; top speed should fall about in proportion to its voltage.

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

## Running the policy on the robot

The policy runs on the Pi, through diagd, on the same path every test here runs
on. That is the path whose delays training was given, and its wiring and zeros
were proven on the rail; if its timing proves too loose, the network already runs
on the controller (`firmware/policy`). `sbc/policy_loop.py` is the loop, and
`simulation/mujoco/balance_check.py` runs that same code against MuJoCo, through
a robot that answers it as the real one does.

    uv run sbc/pack_policy.py exports/rl/<run>             on the PC: the file the Pi needs
    uv run simulation/mujoco/balance_check.py              on the PC: does it stay up?
    python3 balance.py dry                                 motors off: tip it by hand
    python3 balance.py hold                                on the floor, steadied: legs to the crouch
    python3 balance.py run                                 on the floor, on slack strings
    python3 balance.py lower                               held up, then lowered: what touch feels like
    python3 balance.py launch                              held up, lowered and let go: it takes over

The Pi needs `python3-numpy`, and `policy.npz` from the first command beside
`balance.py`. In that order: each stage is there to catch what would make the next
one violent. `dry` proves the IMU's axes and the wheels' signs against the policy
itself with nothing enabled; in MuJoCo a robot with one wheel reversed, or its gyro
reversed, is out of control within a second. Anything that stops `run` cuts the
motors at once, so it must only run with something to catch the robot.

`dry` was not needed by hand the first time, on 4 November 2026, because the rail
had already recorded the same moves. Replayed through this loop's code, the 52
degree nose-down tip in `map` asked for +0.31 and +0.98 Nm, forward, and the most
nose-up moment in `level`, 6.5 degrees, asked for -0.05 and -0.10 Nm, backward. The
gyro agreed in sign with the change in pitch on all 1 293 moving samples of `level`.
The wheels' signs came from being rolled forward in `map`, and in B2 a torque
command changed the speed its own way 94 to 97 per cent of the time. The axes are
not mirrored (determinant +1), so right side down follows. What the replay does not
exercise is the live loop reading a moving robot: `dry`'s motors-off run read the
gravity report correctly, at rest. Run `dry` by hand after any change to the wiring
file, the IMU's mounting or a motor's direction.

How it gets to its feet was tried in MuJoCo on 4 November 2026 from the pose it was
then sitting in on the strings: hips 58 and 69 degrees, knees 106. The policy cannot
do it: obeyed from there it asks for 8 to 12 Nm at once, and it was never trained
there. Easing the legs up with the policy on the wheels stood at the expected delays
but only 3 of 12 times at the longest (IMU 26 ms, commands 10 ms). Nor
does it work to start the policy as the wheels touch, with the strings still carrying
weight: it fights them and rolls 0.5 to 1 m without ever getting free, and the weight
passes from strings to wheels within a few millimetres of lowering, so there is no
moment to aim for. What works is to lower it first, then start: legs firm in the
crouch while it hangs, lowered until the strings are about 5 cm slack, resting against
one finger on the front of the torso, since it leans forward with the wheels free. It
pulls itself off the finger, so the hand needs no timing: 10 of 10 across both delays,
hand away after 0 to 10 s, at most 2 N on the finger. Released from a hold it stood 24
of 24 for 25 s and rolled at most 61 mm, at any string length tried; with only 1 cm of
slack the strings pulled and some runs failed, so the slack matters and the length
does not. `run --go-file` holds the crouch until a file appears, for this. It is the
fallback: lowered by hand and let go, below, is how it is meant to start.

`hold` belongs on the floor, with the robot's weight on its legs. In the air it would
repeat the rail: B2 held the legs at this crouch and these gains for 45 seconds with
no leg over 0.037 rad/s RMS. The crouch is only 14 degrees at the hip and 29 at the
knee, and lowers the robot 6.5 mm from straight, with the wheel still under the hip.

### Lowered by hand and let go

This is how the robot is meant to start: picked up by the torso, lowered until the
wheels touch and let go, with the strings slack, there only to catch it. The hand
carries the weight, so nothing holds the wheels off the floor as the strings did
above. But nobody can say go in time: with nothing taking over it passes 30 degrees
0.5 s after the hand has gone, in MuJoCo. So the robot feels the floor for itself.

The hands, for both of these. Lift it by the torso so that the legs hang, and start
it: about 1.3 s of getting ready, the legs in the crouch a little over a second later,
and it has learned what its knees read in the air 0.4 s after that, so hold it fairly
still for those 3 s.

    lower     Move it about as you would carrying it, for about 15 s. Lower it until it
              stands, take your weight off but keep steadying it, since nothing drives
              the wheels, for 10 s. Lift it clear. At 60 s the legs go soft. It writes
              launch.json, or says why it cannot.
    launch    Lower it. Let go as the wheels touch. A hand slow to let go, or a wheel down
              first, does no harm. Hold it by the torso, not the legs: a hand on both
              legs can feel to it like the floor.

A motor's report of its own torque is good enough for this. In B2, in this crouch at
these gains with the wheels free, the knees read +0.109 and +0.078 Nm, still to 0.001,
and within 0.02 of what their position error implies. A 0.4 Nm kick on a wheel left
one of them 0.036 away, held there by friction, which is why the air's reading is
learned afresh each time. In MuJoCo full weight moves each knee 0.27 to 0.30 Nm, and
a floor reading is the other side of zero, about -0.15, so a robot armed with its
weight already on its legs says so. Carrying it moves both knees far less: over a
whole 100 ms, 0.05 Nm at most, shaken 2 cm at 3 Hz or tipped 15 degrees nose-down. A
hard 2 cm shake at 6 Hz reaches 0.13 for 40 ms, and is gone by 100.

So it takes over when both knees have felt 0.55 of their share, or 1.5 times what
handling made them feel if that is more, for 100 ms, with the torso within 20 degrees
and the legs within 0.2 rad of the crouch. `simulation/mujoco/launch_check.py` runs
balance.py's own loop against a scripted hand, and on 5 November 2026 it stood in all
19 ways down: from 1 to 6 cm/s, letting go at once or over 2 s, let go 3 cm early, at
both sets of delays, and held up to 6 degrees rolled or 8 pitched. It took over 0.1 to
1.4 s after touching. Held straight it tilted at most 14.9 degrees and asked at most
0.33 Nm of the wheels, and rolled about 5 cm; held crooked, 18.4 degrees and 0.49 Nm.
Shaken and tipped in the air it never started. That is MuJoCo.

On the robot, on 5 November 2026, in `exports/sysid/2026-11-05/`. The first `lower` was
never stood on its legs and measured nothing. In the second, full weight moved the knees
0.33 and 0.39 Nm, against 0.27 to 0.30 in MuJoCo, and before the first touch both
together never passed 0.09, so launch takes over at 0.182 each
(`reference/motors/launch_2026-11-05.json`). It went straight from holding still to
lowering, so carrying the robot about is still unmeasured. It tipped past the cut-off
at 31 s with nothing driving the wheels, which lost the report, and the number was
worked out from its log; `lower` now reports from a run cut short too.

The first `launch` took over about 1 s after the weight began to arrive, with the knees
at 0.21 and 0.30, and stood out its 30 s with the cut-off never reached. It went from
5 degrees nose-down at the touch to 13.3 nose-up at most, asked at most 0.39 Nm of the
wheels, reached 8 and 14 rad/s, rolled at most 19 cm and came back to within 5 cm. It
swung for about 15 s, and from 22 s stood dead still at 9.2 degrees nose-up, against
about 8 in MuJoCo, the policy asking 0.01 Nm of wheels whose friction holds more than
that. It ran at normal priority, since `chrt` was refused on the Pi: a step every 9.5 ms,
99th percentile 21, worst 36.

It first drove the same morning, at 0.2 m/s and 0.5 rad/s, for the 120 s it was given
(`2026-11-05_075104_balance_launch.jsonl`): 31 s forward, 5.5 s back and 20.6 s turning.
Asked for 0.20 m/s, the wheels read 0.16 to 0.21. Asked for 0.50 rad/s to the left the
torso turned at 0.60, and asked for 0.47 to the right, at 0.67. The trigger took 40
different speeds on the way, so it is analog on the real thing, and full gas held for
12 s never went silent, the stick being moved meanwhile. It leaned between 1.5 and 14
degrees nose-up throughout, against 14 in MuJoCo. That run ended when its time ran out
and the legs went soft under it, which nobody wants of a robot being driven. So
`launcher.py` has no time limit and takes no option for one: a run ends at the robot's
power button, tapped or held, or at a safety cut. No button on the controller stops the
motors, since that would drop the robot too, so letting go of the triggers is all it
can do, and it leaves the robot standing. Nothing watches the battery during a
run, only at its start, so the motors' own undervoltage at 21.6 V would drop it.

**Why it wobbled.** Rolling straight at a steady 0.2 m/s it was nearly as calm as
MuJoCo says it should be: pitch steady to 0.2 degrees, against 0.08, in
`2026-11-05_080346_balance_launch.jsonl`. At and near standstill it rocked at about
1 Hz, by a degree or more, with the wheels swinging 1 to 2 rad/s, and more after a
shove. The cause is the wheels' friction on the floor, about three times what the
rail measured in the air. Mean torque against speed steps at zero, to 0.035 to 0.045
Nm either way; at a steady 5 rad/s, with nothing accelerating, it takes 0.05 to 0.06;
a stuck wheel breaks away at 0.05 to 0.07. The rail had 0.010 to 0.018 with no weight
on the wheel, and `plant.py`'s MEASURED, which the policy trained on, has 0.005 to
0.02. MuJoCo given 0.04, 0.06 to start moving and 0.004 Nm s/rad of drag rocks as the
robot does when standing, at the same frequency: pitch 0.85 degrees and wheels 1.3 to
1.8 rad/s, against 1.0 and 1.1 to 1.6 in the first stand. It differs in how long the
wheels stay stuck, a quarter of the time where the robot's stayed 70 per cent. With no
place hold at all MuJoCo stops rocking, 0.10 degrees, and creeps backwards at 4 cm/s,
because its wheels then never cross zero: the rocking is the policy and friction
meeting at standstill, which the hold keeps it at. Replaying the loop's real step
times in MuJoCo, 5 to 20 ms apart, changed nothing (0.49 degrees against 0.47), so the
timing is not it.

So `Hold` in `policy_loop.py` no longer corrects for small errors or reels the robot
back to where a trigger was let go, which takes MuJoCo to 0.5 degrees, with the place
kept to about 5 cm in 30 s. It cannot remove the rocking; training on this friction is
what should. Since the wobble belongs to low wheel speeds, and MuJoCo with this friction
holds pitch to 0.1 degrees at 0.5 m/s and at a 1.5 rad/s turn, a full pull now asks for
the 0.5 m/s the policy trained on and a stick's end for its 1.5 rad/s. Friction fed forward at the wheels was tried in MuJoCo and left
out: 0.025 Nm helps little, and at 0.05, not far above the friction, the robot shakes
itself far worse than without it.

**The first drive at those speeds** (`2026-11-05_103837_balance_launch.jsonl`,
`_104049_`, on the Pi; 109 and 43 s) bore that out. With the command held steady it is
as calm as MuJoCo: at 0.5 m/s pitch steady to 0.1 to 0.4 degrees and speed to 0.01 to
0.03 m/s, reading 0.46; on an arc of 0.5 m/s and 1.5 rad/s, 0.2 degrees, though
leaning 18.7 nose-up; turning on the spot at 1.5 rad/s, 0.4 to 0.8. Standing untouched,
0.1 to 0.4 degrees, creeping backwards at 5 cm/s inside the hold's band, against a
degree or more that morning; there were only 15 s of that, and none past the band
for long. Turn rates read high: 1.5 asked gives 1.7 on the spot and 2.0 on the arc.

What is left is the answer to a change of command. For the first second after a trigger
moves pitch swings 3 to 6 degrees, then it rings at 1.56 Hz for 2 to 3 s; a flick of
the stick at speed swings it 2 to 3. MuJoCo answers with about half of that, and
a command 15 ms late, which is what the robot's seems to be, adds a little. Some of it
is physics, since 1 m/s2 takes 6 degrees of lean. So the ramps above went from 1 m/s2
and 5 rad/s2 to 0.6 and 3, about 0.8 s to full speed and 0.5 s to a full turn, which
in MuJoCo takes 40 per cent off the swing on starting. The robot has driven on those
since 10:49 that day, and how much they took off its swing has not been measured.
Both runs ended at a wheel-speed cut of 30 rad/s with the knees going light, which is
what being lifted looks like, the second standing still and the first in full reverse,
after the wheels had reached 29.4 in a full reversal. That cut has gone: see below.

From the tap the first of those runs was ready 1.7 s after its motors came on and took
over at 2.3 s, with about 1.6 s of getting ready before that, half a second of it the
IMU's answer about gravity going missing, which asking for it first did not cure.

**The speed-up on turns is the left turns'.** Averaged over each steady second of the
morning's runs, at 0.5 m/s:

| Asked to turn | Speed, m/s | Turn, rad/s | Nose-up, degrees | Roll, degrees | Right knee, left knee, rad | Leg height right, left, mm |
|---|---|---|---|---|---|---|
| none | 0.45 | +0.10 | 9.6 | +0.7 | 0.76, 0.74 | 190, 195 |
| 1.5 left | 0.65 | +2.07 | 18.3 | +4.9 | 0.92, 0.74 | 182, 195 |
| 1.5 right | 0.44 | -1.60 | 8.0 | -0.7 | 0.69, 0.78 | 197, 193 |

MuJoCo gives the same policy the same bias at about half the size, with no sensor error
at all: 0.49 m/s, +1.57 rad/s and 13 degrees to the left, 0.47 m/s, -1.36 rad/s and 8.2
to the right. So it is the policy's, the turning side of the scissor it stands in, which
nothing in training ever asked it to give up. Turning left the right leg folds, the torso
leans back to keep its weight over wheels now further behind it, and leaning back is
what it answers by driving faster. The roll it reads agrees with its legs, 4.9 degrees
against the 4.2 that 13 mm over the track makes, so the gravity report is not the cause,
as a filter on the accelerometer would have made it. The IMU's place, 38 mm to the right
of centre and 5 mm forward, is not in the simulator, and could be some of why the robot's
bias is the larger: the centripetal pull there is always towards the left, adding to what
a left turn feels and taking from a right turn's. It amounts to 0.15 m/s2 at 2 rad/s, or
under a degree, and goes with the square of the rate, to 4 m/s2 at 10 rad/s, so it has
to be measured before spinning fast, by how the report behaves when spun.

**What it is asked is now nudged towards what it does.** Told to turn on the spot it
backed round a circle, of 33 mm to the left and 87 mm to the right with the wheels' mean
at -0.055 and -0.124 m/s, and at 0.5 m/s straight on it turned +0.12 rad/s, a circle of
4 m. The wheels and the gyro show all of it, and the error changes with what is asked, so
no fixed trim could cover it. `policy_loop.py`'s `Trim` adds up the difference between
what was asked and what the robot does, onto what the policy is told, with time constants
of 2 s for speed and 1 s for turn against the 1.56 Hz it rings at. It learns only once the
command has been steady for half a second, and what it learned fades while the command
changes. In MuJoCo on the floor's friction it takes the turn straight on from +0.042 to
+0.001 rad/s, the wheels' mean on the spot to under 0.005 m/s, and the two arcs above from
+1.57 and -1.36 to +1.46 and -1.48 rad/s. Its first run on the robot
(`2026-11-05_161941`) has only short steady stretches: +0.012 rad/s straight on over 1 s,
and circles of 28 and 12 mm on the spot over 3 s and 0.5 s. The owner found it worked.
The torso's lean is another matter, and is for training.

The ride height reaches the policy and it takes no notice: the D-pad moved it from 185
to 207 mm in one run (`2026-11-05_104936`), and standing the right leg stayed at 193 mm
and the left went from 194 to 197.5. Two of the wheel-speed cuts were wrong: `103837`
in a full reversal after what looks like a collision, and `104936` catching a dive, nose
down 11 degrees with its wheels at 47 rad/s and both knees loaded. The logs of those runs
are on the Pi; the 5 GHz link was too slow to copy them.

**A faster shake, not explained.** Standing, the torso also yaws at 7 Hz, up to about
0.7 degrees either way, far less when rolling. The wheels make it: the yaw rate follows
the difference between them at 0.6 rad/s per rad/s, in phase, coherence 0.98, the torso
turning as a rigid body would. The policy answers with 0.14 Nm per rad/s against the
yaw, and its left wheel's answer is about 2.6 times its right's. The phases close a
loop at 7 Hz if the delay round it is about 30 ms: the IMU's 16 and about 14 from
command to torque, which agrees with the wheels' torque reading following the logged
command by 18 to 20 ms. Training allows 2.5 to 10. But MuJoCo shows no such shake with
the command 20 ms late, so something else is missing from it too.

Three things that look better are not. A lower bend makes the weight show more, but
handling shows as much more, and the policy starts far harder from it: 0.55 Nm on the
wheels, against 0.25. Acting sooner, at under half of its share, stands too, but a hand
still carrying most of it leaves the wheels little grip, and they spin up: 29 rad/s
and 0.7 m rolled with a slow hand. And leaving the policy on in the air stood 3 of 3,
but the wheels are doing 44 rad/s beside the hand when they touch, and it tilts to
23.5 degrees.

What stops it, besides everything that stops `run`: the wheels passing 30 rad/s, which
is about 0.25 s after the policy starts with nothing under them, and 0.14 s after it
is picked up while running. Its hardest start on the floor reaches 25. Left in the air
for 120 s it lets the legs down. Sitting on folded legs it refuses before enabling
anything, and says to lift it.

After the first few minutes of a run it logs only what happened, not every reading,
which is over 1 GB an hour.

### With no computer

`sbc/launcher.py` runs all the time, holding no control and moving nothing, and starts
`balance.py launch` at a tap of the robot's power button, which arms it. Any press
counts that is let go of inside the two seconds that stop every motor and turn the robot
off. Another tap stops every motor and disarms it, unless the robot is lying limp, when
it wakes it. It says what happened in `launcher.log`. `sudo bash sbc/install_launcher.sh`
runs it from boot, once `lower` has written launch.json, and `systemctl disable --now
robot-launcher` takes it off. `tools/test_launcher.py` holds its rules, and starts and
stops it through the simulated diagd.

**Armed and driving, nothing short of lying on the floor cuts the motors** (from 6
November 2026, the owner's rule). Tilted past 30 degrees it drives on, to 60, where
training gave up, though in MuJoCo no shove that took it past 30 was recovered from:
it falls under its own control, not dropped. A leg too fast or out of its window, a step late, a report missing for
up to half a second, the IMU's included, are driven through; a motor in a fault state is
cleared and enabled again while the others drive on; the controller stopping the motors
because the Pi fell silent, or because it restarted, has them enabled again at once; a
wheel within 10 rad/s of its cap, or a winding over 90 C, slows the command until it is
not; and anything unforeseen in a step is skipped, for half a second at most. Only a
sensor silent for longer than that lets it down, gently, over two seconds, rather than
dropping it. A tap of the button, the console's stop and the power button are still
obeyed. `launch_check.py` case 16 holds each of these in MuJoCo; none has yet happened
on the robot. The wheels' VMAX went from 55 to 70 the same day (`sbc/set_wheel_vmax.py`),
so their cap is 65 rad/s, 2.6 m/s, where it was 50: it fired three times on 5 November,
at 15:52, 17:59 and 18:02, and each time dropped the robot. And being picked up now needs
the wheels speeding up while the knees are light: braking hard from 1.6 m/s in MuJoCo
made the knees light for 0.2 s with the wheels slowing, and was taken for a lift.

A press gets an answer unless the robot cannot run, which is an IMU or a CAN bus gone, a
motor not answering or set up wrongly, or a battery under the motors' 21.6 V trip, each
looked at three times before it counts. Until 5 November 2026 much less than that kept a
press from being answered, and most of it left no trace. The launcher did not start at
boot until `install_launcher.sh` had been run. A press was read once in each 100 ms
status, so a quick one could fall between two of them, and one held for 0.4 to 2 s
counted for nothing; the firmware now holds a press of 20 ms or more over until the next
status. A press within a second of the last run ending was ignored, five times that day,
with somebody pressing again each time, and it is now kept and acted on. A motor
console's tab holding control refused it, and now gives way. One second of each start
went on loading, and half a second on an answer from the IMU that always went missing, of
about 2 s from the tap: one run stands loaded and waiting now, and the IMU is not waited
for. And it lay limp if the legs were out of their window, which legs left limp can stay
in however the robot is lifted, with the knees 73 degrees the wrong way at the last of
them: 170 s after its tap, until a hand had moved them.

Armed, it stays armed. Picked up while running, which is the two knees averaging under
0.10 Nm for 0.15 s with the wheels past 20 rad/s, or for a second however slow, it stops
the wheels, puts the legs back in the crouch and waits for the floor. Fallen over, past
30 degrees, with a leg out of its place or moving past its cap, or with a wheel past 50
rad/s, it lets go of every motor at once, and once it has been upright with its legs
hanging still for half a second, which is somebody holding it up, it gets ready and
waits for the floor, and a tap does the same at once, wherever its legs are. A tap on a
robot not armed sends its legs to the crouch in the same gentle second from wherever
they are, which from a slump on the floor is not something it was trained for. A tap on
one with its weight already on its wheels starts it there, on what the knees read in the
air last time or at the measuring run: on 2026-11-05 a re-arm refused eight times over
for being set down within 2 s of the tap, going limp each time with no word why, until
it was held clear. A motor's fault still ends the run, and a robot that has not been tapped stays
limp however it is lifted. The cut on wheel speed alone went with this. Run over all
900 s of that day's driving, this rule fired only when the robot was lifted, three times,
and those knees otherwise stayed light for at most 50 ms, where that cut had stopped two
runs with the knees still loaded, one in a full reversal and one catching a dive with
its wheels at 47 rad/s. In MuJoCo all of it works (`launch_check.py`, 11 to 13). It has
not yet run on the robot.

It always takes speed and turn from the controller: the right trigger forward, the
left back, as far as each is pulled, and the right stick turning. A full pull means
`balance.py`'s `--max-speed`, 0.5 m/s unless told otherwise, and a stick's end
`--max-turn`, 1.5 rad/s, the most the policy trained on. Stopping it
means letting it fall, so it should only run with something to catch it: sitting down
by itself has not been written.

### The strings

The strings also limit how far it can roll. A string's slack lets it travel
sqrt(slack x (2 x length + slack)) before the string pulls: about 24 cm for 5 cm of
slack on 55 cm strings, 45 cm on 2 m strings.

A motor reports only when spoken to, so a step speaks to every motor first, looks
when the reports are in, and then decides: a loop that only sent its commands
would see the encoders about 9 ms late, where training had them at most 2.5 ms.

On the robot on 4 November 2026, motors off, it took a step every 10.0 ms, 12.1 at
the 99th percentile and 14.1 at worst, with the console connected and another
program logging in over ssh every few seconds. The reports were in 4.7 ms after
speaking and the decision took 1.5 ms. Once running, no motor went more than 18 ms
between reports.

The tilt cut-off is 30 degrees and not the 20 POLICY_INTERFACE.md suggests. In
MuJoCo this policy rests about 8 degrees nose-up, and a 0.3 m/s shove takes it to
16. The IMU can be later than it was trained on: in MuJoCo it stands and drives
with the IMU 40 ms late, against the 12.5 to 20 ms of training.

## What stops a test

Every motor is stopped, and the log says why, if one faults, its winding passes
90 °C, it goes faster than its test allows, a leg leaves its window (hips −0.7
to 0.9 rad, knees −0.15 to 1.55), or it stops answering for 0.1 s; and on
Ctrl-C. diagd stops them if the runner goes quiet for half a second, the
controller if diagd does for 0.3 s, and the power button at any time.

## Not built yet

- **C2 and D**, the balance controller and the policy on the floor. The policy
  now has something to run it, `sbc/balance.py`, below, which logs in this
  format. C2's controller, and the tests of D that want it, do not.
- **Coast-down** on the floor needs the robot balancing, so it waits for that
  too.
- **Feeding the results into training** is by hand, once there are results:
  the armature, friction and damping go into `simulation/robot.py`'s
  `ACTUATOR`; the torque-speed line into its peak and no-load speed; the
  delays, battery range and noise into the task configuration and
  `simulation/plant.py`'s `DOMAIN_RANDOMISATION`, narrowed to a little more
  than the spread between repeat runs; and the training history records the
  fine-tune that follows. The driving task has had this, from the first day on
  the rail (`plant.py`'s `MEASURED`).
