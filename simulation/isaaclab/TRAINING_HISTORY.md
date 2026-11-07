# How the policy was trained, and what it was trained for

The policy on the robot will not be trained once. It is the last link of a
chain of fine-tunes, each starting from the one before and adding a thing to
learn, and when the robot's own numbers are measured -- its delays, its motor
curve, its masses -- the chain gets one more link. This is the record that
makes that possible: every adopted stage, what it started from and what it
changed, what the policy has been trained across and what it has not, the
experiments that were tried and dropped and why, and where every run is kept.

The authority for any run is its own `params/env.yaml` and `params/agent.yaml`,
which Isaac Lab writes when it starts and which hold every setting it trained
with. The "what it changed" column below was made by diffing each stage's
`env.yaml` against its parent's, not from memory. The reasoning for each
setting is in the comment beside it, in `wheeled_biped_task/*_cfg.py`.

## Where the runs are

Every run is on the network volume `ysamdjew9w` (EU-RO-1) under
`/workspace/runs/logs/rsl_rl/<task>/<run>/`, and every run named here is also
in the checkout's `exports/rl/`, which git ignores (159 MB in September 2026).
A run directory holds the final checkpoint `model_N.pt` (actor, critic and
optimiser, what a fine-tune resumes from), the exported `policy.pt` and
`policy.onnx` (the observation normaliser baked in), `params/`, a video, the
TensorBoard log and the evaluations' output.

The policies the robot has driven on, D2 and D3, are also in git under
`../../policies/` since 6 November 2026: their exported files, params and git
record, not their checkpoints. Everything else lives only on the volume and in
this machine's `exports/`.

## The adopted chain

Each stage resumes from its parent's checkpoint unless it says otherwise.
"Widened" means `widen_checkpoint.py` gave the checkpoint new inputs or
outputs with zero weights first, so it behaved exactly as before until
training used them.

| Stage | Run | From | Iterations x robots | What it added |
|---|---|---|---|---|
| 1 | `rough-2026-09-24_17-06-40_fixed` | scratch | 1 200 x 16 384 | Balance and drive on rough ground: bumps, slopes up and down, waves, blocks and door thresholds to 15 mm, in a difficulty curriculum. Speed +/-0.5 m/s, turn +/-1.5 rad/s, ride height, shoves. Costs on wheelspin, wheel stagger, out-of-range actions, heat. |
| 2 | `jump`, `jump2` (on the volume only; their `params/` hold the rest) | stage 1, widened: +3 inputs (trigger, target, timer), +2 outputs (leg stiffness and damping), leg outputs x2/3 | to model_800 x 16 384 | The jump task, on flat ground: jumps to 10-40 mm while driving. The first run never left the ground; the missed-jump, take-off and upward-speed rewards are why the second did. |
| 3 | `jump-2026-09-24_19-51-17_jump3` | `jump2` model_800 | 500 x 16 384 | Tighter clearance matching. |
| 4 | `jump-2026-09-24_20-24-52_jump4` | jump3 | 400 x 16 384 | Sideways lean charged (`rew_torso_roll` -50): it had been standing with one knee locked on its stop, torso rolled 12°. |
| 5 | `jump-2026-09-25_01-32-22_ramp` | jump4 | 2 500 x 16 384 | Drive commands to the motors' envelope, 1.93 m/s and 22 rad/s, opened gradually from a quarter; half of all commands kept everyday-sized; errors paid in proportion; jump targets to 120 mm; roll cost -200, leg asymmetry -2; a 26-row flat field. |
| 6 | `jump-2026-09-26_05-08-32_rampbattery` | ramp, widened: +1 input (battery voltage) | 1 500 x 8 192 | The robot's delays (IMU 0-10 ms, encoders 0-5, commands 0-5, with jitter and 1 % lost), a battery from cut-off to full (motor speed x0.75-1.05) and its voltage as an input, a reward for standing still (3.0), speed error cost x3. |
| 7 | `jump-2026-09-26_08-23-24_comjump` | rampbattery, leg and gain exploration noise raised to 0.4 | 1 500 x 12 288 | The jump scored as a jump: one 120 mm target, paid on the whole robot's centre-of-mass rise (2 000 /m) and wheel clearance (100 /m) at 1.5 s, with the torso's pitch (-200) and the two wheels leaving the ground apart (-200 /s) charged. The default on 26 September 2026. |
| 8 | `jump-2026-09-26_12-28-54_height` | comjump | 1 500 x 8 192 | The ride height made something a policy can follow: the noise and per-episode bias (0.02 each) on the sensors alone, no longer on the commands and last actions; the height command given as -1 to 1 over its range; the range widened from 185-207 to 150-207 mm. |
| 9 | `jump-2026-09-26_18-50-39_heightcost` | height | 1 500 x 12 288 | The ride height's error paid in proportion as well, -100 /m, where the 10 mm-wide reward had paid nothing past 20 mm off. |
| 10 | `jump-2026-09-26_20-38-29_heightstepsfast` | heightcost | 1 500 x 8 192 | Steps: 30 % of the field's columns pyramids of steps 20-100 mm high on 0.6 m treads, three drops each, driven down, raised by a curriculum; the speed error cost doubled to -6. **The default policy from 27 September 2026.** |

Every fine-tune from stage 6 on passed `env.command_envelope_start=1.0` on
the command line, since the envelope was already open; the default of 0.25 is
for a policy that has never seen it.

What each stage measured when it was adopted, on the numbers that decided it:

| Stage | Top speed fwd / back | Slow turn, 1.1 rad/s asked | Jump | Standing, MuJoCo, 5 / 2.5 / 2.5 ms delays |
|---|---|---|---|---|
| 5 ramp | 1.44 / -1.46 m/s | 1.0 | 101 mm clearance, a tuck, torso pitching ~50° | rocks 1.5° (13° at twice the delays) |
| 6 rampbattery | 1.19 / -1.06 (1.27 in MuJoCo) | 1.2 | 108-110 mm, the same tuck | dead still |
| 7 comjump | 1.29 / -1.36 | 0.8 (0.5 asked gives 0.1) | 82 mm clearance, centre of mass up 31-33 mm, pitch 20-25° | dead still |
| 8 height | 1.18 / -1.39 | 1.3 (0.5 asked gives 0.3) | 82-84 mm, centre of mass up 31 mm | not measured |
| 9 heightcost | 1.08 / -1.29 | 1.1 (0.5 gives 0.5) | 82 mm, centre of mass up 30-32 mm, pitch 22° | not measured |
| 10 heightstepsfast | 1.12 / -1.23 (0.99 / -1.23 in MuJoCo) | 1.1 (0.5 gives 0.5) | 81 mm, centre of mass up 28-31 mm, pitch 22-24° | still; with the hold loop and the pack at 0.8, 19 mm and 3° of drift in 20 s |

From stage 8 on, three more measures, all in Isaac Lab
(`evaluate_envelope.py`, `evaluate_steps.py`, `evaluate_push.py`):

| Stage | Ride height, asked 150 / 207 mm | Down 60-80 mm steps at 0.7-1.0 m/s, square / at 30° | Fore-and-aft shove survived, standing |
|---|---|---|---|
| 7 comjump | not followed | 62-85 % / 23-54 % | not measured |
| 8 height | 178 / 187 | 77-92 % / 54-85 % | 1.5 m/s either way |
| 9 heightcost | 171 / 197 | 77-100 % / 38-92 % | 1.5 m/s |
| 10 heightstepsfast | 172 / 197 | 92-100 % / 100 % | 1.5 m/s |

Stage 10's weak points: tall steps met slowly and at an angle (60-80 mm at
0.2-0.4 m/s and 30°: 8-69 % made it), a forward top speed below stage 7's,
which is the policy's choice and not the motors' (see `rew_lin_vel_error`),
and the bottom 20 mm of the ride height's range, which no cost tried has
moved it into.

## The driving policy for the robot

The policy to put on the robot first. It branches from stage 1, not from the
jump chain, since nothing here needs a jump: 25 inputs and 6 outputs, the legs
at a fixed kp 12, kd 0.4, which the robot was shown to run quietly (higher
gains set the hips buzzing at 39 Hz, ../../docs/SYSID.md).

| Stage | Run | From | Iterations x robots | What it added |
|---|---|---|---|---|
| D1 | `rough-2026-11-04_07-15-51_measured` | stage 1 model_1199 | 1 500 x 8 192 | The robot as measured on 4 November 2026 (`plant.py`'s `MEASURED`): friction and drag on every joint, the wheels' inertia at 8.3e-4 kg m2 where the simulator had 2.3e-4, the legs 0.95 to 1.2 times as heavy, the IMU 12.5-20 ms late, the encoders 0-2.5, commands 2.5-10, one command in a hundred lost. Trained with the bug below. |
| D2 | **`rough-2026-11-04_09-01-34_measured_fix`** | D1 model_2698 | 600 x 8 192 | The same with the bug fixed. **The policy for the robot.** |

**The bug.** `env.py` used a command a whole policy step late as its mark for
a lost command, so every robot drawn 10 ms late lost all of its commands, held
its starting pose and fell within two seconds. That was a quarter of the robots
in training and in evaluation, and no earlier task could reach it: their
commands were at most 7.5 ms late. It showed as falls in every row of every
ground, nearly all of them in the first two seconds. Timing the falls, and
setting them against each robot's draw, gave 100 % at 10 ms and 0 % at 2.5 to
7.5. A lost command now has its own flag. The first figure given for stage 1 on
the measured robot, 35.5 %, carried this bug; 44.6 % is the fair one.

All scored by `evaluate.py --rough` on the measured robot, 1 280 robots:

| | Upright after 24 s | Flat | Bumpy | Thresholds | Speed error, driving |
|---|---|---|---|---|---|
| Stage 1, on its own model (September) | 96.3 % | 100 % | 100 % | 74 % | 0.07-0.09 m/s |
| Stage 1, on the measured robot | 44.6 % | 64 % | 15 % | 26 % | 0.15-0.22 m/s |
| D1, on the measured robot, bug fixed | 96.3 % | 100 % | 100 % | 72 % | 0.05-0.06 m/s |
| D2, on the measured robot | 96.9 % | 99 % | 100 % | 79 % | 0.05 m/s |

Stage 1 lost robots in every phase of the script, most of them once it was
asked to drive: 92 % were up after standing, 70 % after going forward, 55 %
after backing. Most of what D2 still loses is on the taller thresholds, about 34 of
its 40 falls, which is a 40 mm wheel's limit as it was in September.

In MuJoCo (`drive.py --check`, using the run's friction, drag and wheel inertia
at the middle of their ranges), D2 did not fall at 15 / 2.5 / 5 ms or at the
longest delays trained, 20 / 2.5 / 10 ms, and held 0.46-0.48 m/s of the 0.5
asked. Told to stand for 20 s it wanders 336 mm on its own and 7 to 22 mm with
the hold loop, so the firmware wants the hold loop. Stage 1 in MuJoCo, given
only the delays and none of the friction or inertia, stayed up with the IMU
10 ms late and fell in 8 of 9 phases at 15, so the IMU's lag alone, past a
policy step, was enough to topple it.

**What this does not prove.** Neither simulator has met the robot's real
stiction, whose form is a guess (`friction_actuator.py`'s tanh), nor its floor;
the IMU's 7 per cent over-read of big tilts is not modelled; the motors'
torque-speed line and the battery are still the rated figures, though at
+/-0.5 m/s the wheels use only about 40 % of their speed. **No policy has yet
run on the robot.**

**D3, trained from nothing for the motors' whole envelope (5 November 2026).** D2 on the
robot leaned 8 degrees back standing and up to 18 turning, turned faster one way than
the other, and fell in Isaac Lab past 6 rad/s. Fine-tuning it towards a wider envelope
and mirror symmetry (`drive_sym5`, `drive_mirror`) kept its lean and its lopsided turns,
probably because its exploration noise had all but gone, so two runs were trained from
nothing instead, on the driving task (`Biped-Wheeled-Drive-v0`,
`WheeledBipedDriveFreshPPORunnerCfg`): mirrored data and a mirror loss, the torso's lean
charged -30, and the envelope opening over 48 000 steps. 3 800 iterations each.

| Run | Envelope's tips | Upright after 24 s, rough | Held, asked 1.5 / 2.0 m/s | Spins held | Lean standing |
|---|---|---|---|---|---|
| `rough-2026-11-05_10-36-30_fresh2_full` | 2.2 m/s, 25 rad/s | 99.1 % | 1.25 / 1.34 m/s | to 20 rad/s, overshooting by a third | +0.9° |
| **`rough-2026-11-05_10-37-59_fresh2_18`** | 1.8 m/s, 15 rad/s | 97.4 % | 1.26 / 1.54 m/s | to 12 rad/s, within 1 % | -0.6° |

Both follow the ride height from 170 to 207 mm and turn alike either way. The second is
the one to put on the robot: its turns are what is asked. In MuJoCo on the floor's
measured friction, with `Trim`, it held 0.5 to 1.5 m/s and turns to 6 rad/s within 1
degree of upright, where D2 leaned 8 to 16 degrees back and tipped past 30 at 1.5 m/s
and 3 rad/s; `balance_check.py` and all fourteen cases of `launch_check.py` pass on it.
Picked up while running it is cut 1.1 s after the lift, against D2's 0.3 s: lifted, it
pumps its legs at 2 Hz before its wheels spin up. A rule on the knees' average load
caught it sooner in MuJoCo, and was dropped: replayed over the robot's runs of that
morning it fired with the robot on the floor, whose knees carry less than MuJoCo's.
It has been on the robot since 5 November.

**D4, D3 on the motors as measured (6 November 2026).** The wheel motors' curve was
measured on the robot that morning (`../../docs/SYSID.md`'s W1): full torque to 37.5
rad/s, then falling to nothing at 55, where training had assumed a straight line to
48.2. `Biped-Wheeled-Drive-Measured-v0` puts that curve into the actuators, scales the
no-load speed with the battery from 0.8 to 1.02, and opens the whole envelope at once,
to 2.2 m/s and 25 rad/s. `rough-2026-11-06_05-54-42_d4_measured` is D3 model_3799 with
1 000 iterations x 8 192 robots of it. Both scored by `evaluate_drive.py --measured
--motor 55`:

| | Upright, spun at 20 / 25 rad/s | Upright, asked 2.2 m/s | Held, asked 1.0 / 1.5 / 2.0 m/s | Spins asked 6 / 12 rad/s |
|---|---|---|---|---|
| D3 | 39-41 % / 2-3 % | 75 % forward, 89 % back | 0.92 / 1.27 / 1.56 m/s | 6.3 / 12.1 rad/s |
| D4 | 94-97 % / 70-88 % | 98 % forward, 97 % back | 0.87 / 1.20 / 1.42 m/s | 7.0 / 13.9 rad/s |

Inside the envelope the robot is driven in, 1.8 m/s and 15 rad/s, both stay up
throughout; D4 is the better of the two outside it, and tracks speed slightly worse and
spins a sixth faster than asked. Cases 1-16 of `launch_check.py` pass on it. Case 17,
the September jump policy handed over from it, fell jumping from standing where it had
landed from D3; that jump policy is a stand-in and falls at the robot's delays either
way. D4 has not run on the robot.

**D5, down to 155 mm (6 November 2026).** On the robot D3 stood at 170 mm rocking at
1.5 Hz and drove there calmly. `Biped-Wheeled-Drive-Low-v0` gives the knee 1.0 rad of
action and the hip 0.5, so the legs reach 155 mm with the shin short of the owner's 90
degrees forward, and asks for 155 to 207 mm. Two fine-tunes of D4 model_4798, 1 500
iterations each: `rough-2026-11-06_11-42-09_d5_low` as D4 was trained, and
`rough-2026-11-06_11-43-08_d5_low_calm` with the cost on pitching and rolling three
times as high (`rew_ang_vel_xy` -0.6). Standing still in MuJoCo on the robot's own loop
(16 ms IMU, 6 ms commands), pitch rate in rad/s, and the speed reached at a full pull in
fast mode (1.8 m/s asked):

| | 155 mm | 160 | 170 | 185 | 204 | Full pull at 155 / 170 / 204 mm |
|---|---|---|---|---|---|---|
| D3 | | | 0.27 | 0.11 | 0.02 | - / 1.54 / 1.59 m/s |
| d5_low | 0.03 | 0.03 | 0.22 | 0.08 | 0.12 | 1.31 / 1.18 / 1.25 m/s |
| d5_low_calm | 0.10 | 0.17 | 0.10 | 0.07 | 0.10 | 1.22 / 1.37 / 1.27 m/s |

Training's own scoring agrees on the speed: asked 2.0 m/s the two hold 1.19 and 1.28,
where D3 held 1.56 and D4 1.42. So both give up about a fifth of D3's top speed for the
lower stance. Cases 1-16 of `launch_check.py` pass on both; case 17's stand-in jump falls
from both, as from D4. d5_low_calm went on the robot that evening, and came off it half an hour
later. Lowered to 155 mm while standing it leant back 8-12 degrees with the knees at the
end of their action, rocked, and after 2.5 s fell. Taken over with the height already at
155, as the controller keeps it between runs, it pitched 13-21 degrees nose-down within
half a second with the wheels at their 55 rad/s, the knees swinging through their whole
range, three times running. MuJoCo had shown neither. D3 went back on, and the
controller's height back to 170-207 mm.

Note on that speed: D3 on the robot reaches 1.1-1.3 m/s at a full pull and about 0.7 at
1.0 m/s asked, against 1.55 and 1.0 in MuJoCo at any height. Riding low it loses less of
that, so it drives faster low; the shortfall is the robot's, not the stance's, and is not
explained yet.

**D6, prepared (6 November 2026), not yet trained.** `Biped-Wheeled-Drive-D6-v0`
(`WheeledBipedDriveD6EnvCfg`) is the low task on the robot as that evening's logs showed
it (plant.py, after MOTOR_CURVE): the wheels' torque through a 5-20 ms lag at 0.75-1.0 of
what is asked, the IMU back to its measured 12.5-20 ms, the IMU's zero 2 degrees either
way and the torso's centre of mass 10 mm fore or aft per episode, the wheels' friction at
the speeds it drove; and of its own making, the ride height slewed at 50 mm/s from the
crouch's, and a floor of 165 mm with the hip's action 0.6, off the corner of the legs'
reach. launch_check.py's rig has the wheels' lag too (13 ms, 0.85) since then.
`evaluate_drive.py --d6` scores it. To be fine-tuned from D5 or D4 on a pod.

The same evening the robot, its IMU levelled, drove D3 low: at 170 mm both hips' actions
sat at their end and the knees' at 0.92, and it pitched three to five times as fast
standing there as at 207 mm. So D6 also charges a leg's action past 0.9 of its range
(`rew_leg_action_reserve`, -50). And the robot's logs showed the legs' torque as late as
the wheels', 8-12 ms (plant.LEG_RESPONSE), which the friction actuator can now put after
the position loop (`lag_after_pd`): `Biped-Wheeled-Drive-D6-Legs-v0` is D6 with it, and
`Biped-Wheeled-Jump-Lag-v0` the measured jump task with both motors' lags. Training from
d5_low_calm model_6297, 1 500 iterations each: `d6` on D6, and `d6_legs` on D6 with the
legs' lag; and `jl_lag` from jm_smooth model_15988 on the lagged jump task.

**D6 and jl_lag, trained (7 November 2026), not yet on the robot.**
`rough-2026-11-06_17-35-45_d6` and `jump-2026-11-06_19-35-39_jl_lag` are the pair
launch_check.py now judges by default; in MuJoCo, with the legs' lag at 1.0 and 0.9 of
what is asked, against D3:

- Standing at 170 mm it pitches at 0.07-0.08 rad/s rms against D3's 0.71-0.78, with no
  leg's action past 0.89 at any height from 165 mm; at 207 mm, 0.15 against 0.10-0.16.
- At 170 mm it holds 0.99 m/s at 1.0 asked and 1.43 at 1.8, as D3 does. At 207 mm it is
  slower: 0.83 and 1.06, against D3's 0.97 and 1.43.
- It passes launch_check.py's every case at both leg strengths, the hard shove while
  driving among them, which D3 fails at 1.0; and with jl_lag case 17's jump, at the
  robot's delays, IMU 16 ms and commands 6: it clears 46-64 mm and is back on D6
  standing 0.6 s after the press, 1.6 s from 1.5 m/s braking first.
- jl_lag, on its own lagged task, overshoots a 20 mm jump by 5 mm where jm_smooth
  overshoots by 11, and pitches 8 degrees at its peak where jm_smooth pitches 12.

`d6_legs` is faster at 207 mm (0.97 and 1.31 m/s) and no steadier, but at the legs' full
strength the hard shove tips it over, and cases 12 and 14 could not knock it down to see it
get up again. D6 it is.

**D6 on the robot (7 November 2026, 07:29): it rocked, and came off again.** Placed on
the floor at the crouch's 203 mm, asked nothing, it drove its wheels back and forth at
11-12 Hz for as long as it stood: pitch rate 1.0-1.5 rad/s rms, the torso about +/-1
degree, the wheels about +/-4 degrees, the hips and knees only +/-0.25-0.4. D3 at the same
height the evening before measured 0.15-0.17 rad/s rms, and its small rocking was at
11-13 Hz as well; the IMU's rates and the loop's timing were the same in both runs. In
MuJoCo, placed the same way, D6 rocks at 1.5 Hz and 0.14-0.24 rad/s, and it stays calm
with the wheels' lag at 20 ms or the IMU's at 24 ms. So the robot has a lightly damped
mode near 11-12 Hz that the model lacks, whatever it is: the printed legs or the tyres
flexing, or play in the wheels' drive. D3 sits just inside it. Open loop, from pitch rate
to wheel action, D6's gain is 0.45-0.48 at 1-12 Hz against D3's 0.34-0.36 (D4 0.35-0.38,
D5 0.32-0.34, d6_legs 0.39-0.41), and that 30 % is enough. D6 with its wheels' torque
scaled to three quarters, D3's gain, rocks at 1 Hz in MuJoCo and falls when the IMU is
silent for 0.3 s while driving, so it was not tried. D3 went back on at 07:46. A policy
for this robot needs that mode in the model, or a pitch-rate gain no higher than D3's.

**D6's rock in the model, and D7 (7 November 2026).** It is not a mode of the robot's
own: it is the loop from the pitch rate the policy reads to its wheels' torque, too strong
for the robot at 11 Hz. Read off that morning's logs (plant.SHAKE has the detail): the
commands as sent against what each motor reported say every motor makes its torque about
15 ms late (the hips 18), and the robot's leg targets and wheel torques replayed into
MuJoCo say the wheel carries about 3e-4 kg m2 on its joint, not the 8.3e-4 every task has
drawn about. With those MuJoCo's torso still answers a push 0.81 as strongly as the
robot's, for a reason not found, and the wheels' gain stands in for it at 1.15:
launch_check.py's defaults are now that loop, and on it D6 rocks 1.0-1.5 rad/s rms as it
did on the robot while D3 stands at 0.05, and still at a gain of 1.3. Around the robot's
loop D6 comes to about 1.0-1.15 and D3 to 0.75-0.9, which is why D3 tipped over when the
link was held up 40-70 ms that morning.

`Biped-Wheeled-Drive-D7-v0` (`WheeledBipedDriveD7EnvCfg`) is D6's task with the wheel's
inertia at 3e-4, the legs' torque 12-20 ms late at 0.95-1.2 after their position loop,
and the wheels' 10-20 ms late at 0.8-1.3, so that a policy that rocks the robot rocks
here first. Two runs from D6's model_7796, 1 500 iterations each, side by side on one
RTX PRO 4500: `d7` as it is, and `d7_rate` with the action-rate cost at -0.15 for -0.05.
D6 itself is scored on the task first, to see whether Isaac Lab now rocks it too.

**D7, trained (7 November 2026): `d7_rate` it is, not yet on the robot.** Isaac Lab
rocks D6 on D7's task as the robot did: 40-78 deg/s rms standing, against 9-12 on its
own, and 6 per cent of robots down. `rough-2026-11-07_06-31-50_d7` and
`rough-2026-11-07_06-32-50_d7_rate` (model_9295 each) stand on it at 11-15 deg/s at
every height with none down. From pitch rate to wheel torque at 11 Hz they ask 0.24 and
0.23 Nm a wheel per rad/s, against D6's 0.43 and D3's 0.34: about 0.55-0.65 around the
robot's loop where D3 is 0.75-0.9. In MuJoCo on launch_check.py's new loop:

- Standing, pitch rate rms: d7_rate 0.11 at 165-170 mm (D3 0.36 at 170, hips pinned),
  0.10 at 185, 0.14 at 207 in a 1.3 Hz sway (D3 0.04); with the wheels' gain at 1.3,
  0.08 and 0.09 (D3 0.60 and 0.05). d7 sways 0.26 at 207.
- Driving at 1.0 and 1.8 asked, 0.02-0.03 rad/s against D3's 0.15-0.34; 1.00 and 1.25
  m/s against D3's 1.00 and 1.50. launch_check.py's full gas in fast mode, 1.42.
- launch_check.py: d7_rate passes every case but the jump from 1.5 m/s braking first,
  where it lands, hands back and is taken for lifted; it passes the hard shove and the
  low let-go that D3 fails. d7 fails case 15, 0.94 m/s in fast mode. The jump policy,
  jl_lag, is still the old plant's and stays off.

**D7 on the robot (7 November 2026, 14:39-15:27): it swung, and came off again.** The 11 Hz
rock was gone, but it swung at 1-1.5 Hz at every height: 0.3-0.58 rad/s rms at 204 mm,
the legs through their whole action each half swing, about 10 degrees and the wheels
±35 rad/s (1.4 m/s) each way with nothing asked. At 15:26 one swing put the wheels at
their 50 rad/s and it ran into a wall at about 2 m/s. D3 on the same robot the night
before stood at 207 mm at 0.03 rad/s. D7 asks 0.7 of D3's wheel torque per rad/s of
pitch rate at every frequency from 1 to 25 Hz, so it is D3 turned down, which the 11 Hz
loop wanted and the slow balance could not spare. In MuJoCo at 204 mm D7 sways 0.50
rad/s at 1.1 Hz with the wheels' torque at 0.8 of asked and 0.25 at 1.6 Hz with the IMU
40 ms late, where D3 holds 0.04-0.05 under both. Both are plausible on the robot: every
D7 run was on a boot whose IMU gave gravity at 45 Hz and gyro at 335 (97-99 and 400 on
good boots), and on such a boot the gyro's yaw lagged the wheels' by 34-44 ms against
22.5 the night before. The gravity report itself is true: against the gyro's integral
its gain is 0.95-1.02 at 1-4 Hz with no lag. D3 went back on. The next driving policy
has to hold D3's slow balance with D7's margin at 11 Hz, so its gate is standing at 204
mm with the wheels at 0.8 and the IMU at 40 ms.

**D8, trained (7 November 2026): `d8` it is.** `Biped-Wheeled-Drive-D8-v0`
(`WheeledBipedDriveD8EnvCfg`) is D7's task with plant.SWAY: the wheels' torque drawn from
0.7 to 1.3 of asked and the IMU 12.5 to 40 ms late. Two fine-tunes of d7_rate's model_9295,
1 500 iterations each with d7_rate's action-rate cost: `rough-2026-11-07_11-52-47_d8`, and
`rough-2026-11-07_11-53-48_d8_calm` with the cost on pitching and rolling doubled (-1.2).
Scored on D8's task in Isaac Lab, standing they rock 12-14 and 11-14 deg/s at every height
where d7_rate rocks 16-21, and asked 2.2 m/s hold 1.22 and 0.89 m/s against its 1.37. In
MuJoCo on launch_check.py's loop, pitch rate RMS in rad/s, IMU at 99 Hz and gyro at 400
unless said:

| | D3 | d7_rate | d8 | d8_calm |
|---|---|---|---|---|
| Standing 170 / 185 / 204 mm | 0.41 / 0.15 / 0.04 | 0.10 / 0.09 / 0.03 | 0.07 / 0.08 / 0.09 | 0.09 / 0.08 / 0.05 |
| Wheels at 0.8 | 0.40 / 0.13 / 0.04 | 0.24 / 0.24 / 0.47 | 0.15 / 0.18 / 0.21 | 0.20 / 0.20 / 0.14 |
| IMU 40 ms late, gravity 46 Hz | falls / falls / 0.15 | 0.19 / 0.15 / 0.25 | 0.13 / 0.13 / 0.17 | 0.15 / 0.14 / 0.14 |
| Wheels at 1.3 | 2.05 / 0.09 / 0.11 | 0.07 / 0.07 / 0.03 | 0.06 / 0.07 / 0.07 | 0.07 / 0.07 / 0.04 |
| Driving at 1.0 and 1.8 asked | 0.7-1.5 | 0.01-0.12 | 0.01-0.03 | 0.01-0.10 |
| Speed held at 1.8 asked, 170 / 204 mm | 1.48 / 1.56 | 1.22 / 1.35 | 1.25 / 1.17 | 1.26 / 0.94 |

d8 halves d7_rate's sway with weak wheels without D3's shake. Its wheels answer the pitch
rate as d7_rate's do (0.42 Nm a wheel per rad/s at 1 Hz, 0.22 at 11, D3 0.69 and 0.33), so
what it learned against the sway is elsewhere, unidentified. launch_check.py passes every
case on d8, D3's two failures (the hard shove, a slow let-go at 170 mm) among them; d8_calm
fails case 15 at 0.80 m/s in fast mode. d8 is the one for the robot, its height's top held
at 203.5 mm as D7's was.


From 27 September 2026 the robot drives on stage 10 and jumps on a second
policy, handing over between them (`TwoPolicies` in
`simulation/mujoco/drive.py`; the firmware's side is in
`docs/POLICY_INTERFACE.md`). Every run that tried to teach one policy both,
the tried runs below from `windup1k` to `crouchdefault`, traded the driving
for the jump or the jump for the driving. The jump policy only has to crouch,
jump, land and hand back, so it is free to drive badly, and does: asked for
1.45 m/s it holds 0.5-0.6.

Its chain branches from stage 8 through `steps`, `stepsheightwindup` and
`mergeheight` (below):

| Run | From | Iterations x robots | What it added |
|---|---|---|---|
| `jump-2026-09-27_09-38-04_crouchmerge` | mergeheight | 1 500 x 8 192 | A crouch to 150 mm asked for 0.6 s before each jump (`jump_crouch_s`), clearance paid 1 000 /m, pitch charged -400: the push-off jump |
| `jump-2026-09-27_17-19-09_nosplit300` | crouchmerge | 500 x 6 144 | The wheels' fore-and-aft split charged through the crouch and the jump, -300 /m (`rew_jump_stagger`): it had crouched in the splits |
| `jump-2026-09-27_17-52-53_heading50` | nosplit300 | 1 000 x 8 192 | The heading turned in the jump charged, -50 /rad (`rew_jump_heading`) |
| `jump-2026-09-27_19-53-09_quickcrouch` | heading50 | 1 000 x 6 144 | The jump started the moment the legs reach the crouch rather than after 0.6 s, and the operator's height asked for again from the landing: no pause at the bottom, no second crouch after |
| `jump-2026-09-28_06-13-36_jumpsym300` | quickcrouch | 1 500 x 8 192 | The two legs bending differently charged through the crouch and the jump, -300 /rad² (`rew_jump_leg_asymmetry`). **The candidate jump policy, 28 September 2026** |

Every run passed `env.command_envelope_start=1.0 env.rew_leg_height_error=-1000.0`
and each run's additions carried on to the next. What they measured,
handed over from stage 10 in MuJoCo with random delays up to 10 / 5 / 5 ms
and a random battery, and the clearance in Isaac Lab standing and at 1 m/s:

| Run | Clearance, Isaac Lab / MuJoCo | Knees apart, pushing off / in the air | Roll in the air | Heading turned | Falls in MuJoCo, jumps to 1.5 m/s / to 1.1 m/s |
|---|---|---|---|---|---|
| crouchmerge | 152-155 / 143-164 mm | 22 / 84° | 18° | 119° | not measured with the quick crouch |
| heading50 | 121-130 / 133 mm | 88 / 70° | 12° | 22° | 2 in 40 / -- |
| quickcrouch | 124-133 / 128-131 mm | 78 / 68° | 14° | 66° | 3 in 40 / 1 in 60 |
| jumpsym300 | 103-112 / 105-109 mm | 13-16 / 5-9° | 4° | 8° | 2 in 40 / 0 in 60 |

Every jump policy until jumpsym300 folded its right leg far further than its
left, a habit each inherited from its parent; the higher the jump the more it
rolled and turned. Evening the legs out cost a sixth of the clearance, 105 mm
against the 120 asked for, and the runs that won it back lost robustness in
MuJoCo (symlong, symhigh, below). Every fall above was on landing, most of
them faster than the jump policy can drive, which is why the firmware should
not jump above 1 m/s.

**The jump on the measured robot, at a height asked (6 November 2026).** jumpsym300,
handed over from D3 in MuJoCo, landed at the delays it was trained to (IMU 4 ms,
commands 2 ms) and fell half a second after landing at the robot's (16 / 6 ms).
`Biped-Wheeled-Jump-Measured-v0` is the jump task on D4's robot: the measured motor
curve and battery, the delays measured on the robot, and the height asked anywhere from 20 to 120
mm, paid for reaching it and charged for passing it (`jump_score_to_target`,
`rew_jump_overshoot`). Two runs from jumpsym300 model_12990, 1 500 iterations x 8 192
robots each: `jump-2026-11-06_05-55-42_jm_target` charging overshoot -1 000 /m, and
`jump-2026-11-06_05-56-42_jm_soft` at -300. Scored by `evaluate_jump.py --measured
--crouch-s 0.6`, 64 robots a cell, standing, at 0.5 and at 1 m/s:

| Run | Asked 20 / 30 / 50 mm | Asked 80 / 120 mm | Upright | Pitch at peak | Turned |
|---|---|---|---|---|---|
| jm_target | 25-27 / 32-35 / 43-47 mm | 54-61 / 60-65 mm | 95-100 % | 8-12° | 7-15° |
| jm_soft | 31-32 / 36-39 / 47 mm | 59-60 / 65-69 mm | 95-100 % | 10-20° | 11-27° |

Both follow the height asked to 50 mm and top out at 60-70 mm, which on the measured
motors is the most there is; jumpsym300 cleared 105 mm on the rated ones. Then case 17
of `launch_check.py`, the A button handed over from the driving policy, one try each of
standing, at 0.5 m/s, braking from 1.5 m/s, and pressed twice, at 30 and 60 mm:

| Driving + jump | IMU 16 / commands 6 ms | 26 / 10 ms | Cleared, asked 30 mm |
|---|---|---|---|
| D3 + jm_target | 8 of 8 | 7 of 8 | 30-34 mm |
| D3 + jm_soft | 8 of 8 | 6 of 8 | 35-39 mm |
| D4 + jm_target | 8 of 8 | 6 of 8 | 31-46 mm |
| D4 + jm_soft | 8 of 8 | 6 of 8 | 45-48 mm |

Every fall was at the longer delays, past the 12.5-20 ms the robot's IMU was measured
at, and all but two of them jumping just after braking from 1.5 m/s. D3 with jm_target
is the pair for the robot's first jumps: it lands every case at the robot's delays and
clears what is asked.

**On the robot, and smoother (6 November 2026, afternoon).** D3 with jm_target fell
both times it was tried, standing still at 30 mm. The jump shook the torso at up to 7 g,
buzzing at about 50 Hz: the jump policy reversed its wheel torques almost every step,
which it does in MuJoCo too, where it costs nothing. The first time the IMU started its
estimate over and the tilt guard let go of a robot standing at 4 degrees
(`../../docs/POLICY_INTERFACE.md`, "Jumping on the Pi", has what was done about it);
the second time it landed, stood itself up and tipped over backwards 0.7 s after the
trigger, still on the jump policy. Two runs from jm_target model_14489, 1 500
iterations x 8 192 robots each, charged the change of command in the jump as much as
when driving (`jump_action_rate_scale=1.0`, where it had been a fifth):
`jump-2026-11-06_08-52-38_jm_smooth` at the usual `rew_action_rate` of -0.05, and
`jump-2026-11-06_08-53-36_jm_smooth_hard` at -0.25.

| Run | Asked 20 / 30 / 50 mm | Asked 80 / 120 mm | Upright | Pitch at peak | Wheel command's change a step, MuJoCo | Reversals in 1.5 s |
|---|---|---|---|---|---|---|
| jm_target | 25-27 / 32-35 / 43-47 mm | 54-61 / 60-65 mm | 95-100 % | 8-12° | 0.27 | 43 |
| jm_smooth | 23 / 30-31 / 41-44 mm | 59-63 / 63-69 mm | 97-100 % | 10-13° | 0.15 | 18 |
| jm_smooth_hard | 21-25 / 28-32 / 41-43 mm | 54-60 / 63-66 mm | 97-100 % | 12-16° | 0.16 | 24 |

Half the jitter, not none of it, and five times the charge bought no more. Both landed
all sixteen of case 17 with D3, at 16 / 6 ms and at 26 / 10, tilting 4-10 degrees where
jm_target had tilted 10-18; jm_smooth cleared 29-30 mm asked for 30. Handed back 0.5 s
after the trigger rather than 1.5, landed and still crouched, it landed all sixteen too,
and that is how the robot now hands back. jm_smooth is the one for the robot.

## What the policy is trained across

The training distribution of the default policy, stage 10, as `jump_env_cfg.py`
and its parents set it. Anything the robot will meet that is outside this
list is something the policy has never seen.

- **Drive commands**, resampled every 5 s: half over the diamond
  |speed|/1.93 + |turn|/22 <= 1, half everyday (+/-0.5 m/s, +/-1.5 rad/s); a
  fifth of robots told to stand still. The tracking tolerance widens by a
  fifth of the command.
- **Ride height**, drawn over 150-207 mm with every command and paid in
  proportion to its error. Followed from about 172 to 197 mm. Through stage 7
  the range was 185-207 mm and, buried in observation noise, never followed
  by any policy.
- **Jumps**, every 3-6 s, at whatever speed and turn it is being driven at.
- **Ground**: a field of 4 m tiles in 10 rows, 70 % of its columns flat and
  30 % pyramids of steps -- a 1.1 m platform, then three drops of 20-100 mm
  on 0.6 m treads, raised a row at a time as the robots cope -- only ever
  driven down (stage 10). Stages 2 to 9 were on nothing but flat. The rough
  ground of stage 1 is in its ancestry only; stage 7 drove MuJoCo's hardest
  generated rough ground with no falls, but Isaac Lab's rough suite,
  thresholds included, has not been run on stages 7 to 10.
- **Shoves** every 3-6 s: the torso's velocity changed by up to +/-0.5 m/s
  fore and aft, +/-0.3 sideways, +/-0.8 rad/s in yaw. Stages 8 to 10 stand
  up to 1.5 m/s fore and aft; 2 m/s is past what the motors can catch, and
  training on shoves to 1.0 m/s only cost top speed (push, below).
- **Delays**, per episode: IMU 0-4 physics steps (0-10 ms), encoders 0-2,
  commands 0-2 late, each a step off one step in ten, one command in a
  hundred lost.
- **Battery**: motor no-load speed 0.75-1.05 of the rated 48.2 rad/s, per
  episode, and the voltage fed to the policy.
- **Sensors**: Gaussian noise 0.02 and a per-episode offset 0.02 on every
  scaled sensor reading -- through stage 7 on the commands and last actions
  too; from stage 8, the sensors alone.
- **The robot itself**, drawn at startup: wheel friction, torso and wheel
  mass scale, rotor inertia (armature) over a factor of four, from `plant.py`'s
  `DOMAIN_RANDOMISATION`.
- **Episodes** of 20 s, ending on a tilt past 60° or the torso touching the
  ground, or, without penalty, near the field's edge.

**Never trained on**: steps over 100 mm, or driving onto a step from below;
climbing anything above 15 mm; side
slopes; carrying a payload; the real motor's torque-speed curve (a straight
line from 3 Nm to zero at the no-load speed is assumed); a real CAN bus, IMU
or battery; the robot's measured masses, of which four fifths are estimates.

## Tried and not adopted

Each has its lesson in the comment of the setting it concerns.

| Run | From | Tried | Why not |
|---|---|---|---|
| measured_scratch | scratch | D1's robot, from nothing, 2 400 iterations at 8 192 | stopped near iteration 350, at terrain level 0.6 where D1 was at 3 after the same half hour; it was also training with the bug |
| envelope, envelope2-4 | jump4 | the whole envelope at once, then fine-tunes to recover | spun at 17 rad/s and stopped turning below 2.5 rad/s; never recovered. The ramp fixed it. |
| rise2, rise5 | ramp | paying the torso's rise; leaning into turns | driving collapsed (rise2); top speed fell to 1.14, slow turns went, arcs rode on one wheel (rise5) |
| jumponly, leanonly | ramp | each of rise5's changes alone | neither helped; leaning tipped the robot onto its outside wheel |
| wheellift, jumphigh | ramp | a cost on a lifted wheel; a heavy shortfall cost to jump higher | no change to wheel loading; 101 mm stayed the ceiling |
| still1 | ramp | delays, battery, stand-still at 1.0 | still3 (3.0) jumped more cleanly |
| still3 | ramp | the same at 3.0 | stood still under delay, but lost a quarter of the top speed |
| nobatt, nodelay | ramp | still3 without the battery, without the delays | diagnostics: the battery cost the speed, because the policy could not see it |
| battery, batterytrack | still3, widened | the voltage as an input | not used: a policy that had already learnt caution never grew the new input's weights |
| maxjump, maxjump2 | still3 | scoring the highest clearance, no target (by a second session) | still the tuck, 103-105 mm |
| bodyrise | batterytrack | paying the torso's rise, more exploration (by a second session) | 115 mm but the same tuck, leaning 2.7° standing, 0.95 m/s top speed |
| comonly | rampbattery | stage 7's scoring without the clearance term | fell after four jumps in five; stopped turning |
| heightturn | comjump | the ride height's fixes (below) and a stronger reward for turning | ignored the ride height; top speed 0.95 m/s |
| push | height | shoves fore and aft to +/-1.0 m/s, twice the usual | top speed fell to 0.94 m/s, the motors' 1.93 less a shove: it kept that much wheel speed in hand. Survival unchanged: its parent already stood up to 1.5 m/s shoves standing and fell at 2.0, as this did |
| pushsteps | height | the same, and steps | void for steps: the platform every step robot started on was a post 10 cm across, a step high (`step_platform_m`); the pushes as above |
| steps | height | steps, with the height cost at -30 | the best on steps, and the only real push-off jump yet (centre of mass up 68 mm, 114 mm clearance, but pitching 44°) -- both by riding at 160 mm whatever it was asked; slow turns gone (0.5 and 1.1 rad/s asked gave 0.0 and 0.2) |
| heightsteps | heightcost | stage 10 without the doubled speed cost | the same within the noise, but worse on 40 mm steps at 0.2 m/s (23-54 % made it, against 77-85 %) |
| windup1k, windup3k, windupcont, windupexplore | heightstepsfast | a crouch charged for (`rew_jump_windup`) for 0.3 s after the trigger, at two strengths, continued to 1 500 iterations, and again with the legs' exploration reset | it sank but did not push: the jump stayed at 26-31 mm of rise. It did follow the ride height over its whole range and drove at 1.34 m/s, but lost slow turns and angled steps |
| stepsheight, stepsheightwindup | steps | the steps policy, which pushes off, with stage 10's costs, and with the wind-up | kept the push -- 70-83 mm of rise, 100-131 mm cleared, pitching 35-50° -- and the steps, but rode at 150-165 mm whatever it was asked and would not turn slowly |
| mergeheight, mergeturn | stepsheightwindup | the ride height's cost at -1000, and with the turn's tripled | followed the ride height exactly, but jumped 16-22 mm from standing, drove at 0.9-1.1 m/s and still would not turn slowly. From a 150 mm stance, though, it pushed for 86 mm: the idea behind `jump_crouch_s` |
| crouchmerge | mergeheight | a crouch asked for 0.6 s before each jump, clearance paid 1 000 /m, pitch charged -400 | **the best jump: 152-155 mm cleared (143-164 in MuJoCo with delays), 84 mm of rise above standing**, 36° of pitch -- and poor driving: 0.84 m/s, weak turns, a wheel up standing at 150 mm |
| crouchdefault | heightstepsfast | the same | kept the driving, and 1.40 m/s, but never learned to push from the crouch: 86 mm, wheels leaving 0.2 s apart |
| nosplit1000 | crouchmerge | the split charged at -1 000 /m | no better on the split than -300 (44 mm against 56), and pitched more, 37-40° |
| heading150 | nosplit300 | the heading charged at -150 /rad | stopped jumping: half took off standing, and none stayed up jumping at 1 m/s |
| quickcrouchlevel | heading50 | quickcrouch with the pitch at -800 | flew more level, 20-22° against 37°, but cleared 112-117 mm and fell 6 times in 40 in MuJoCo |
| jumpsym100 | quickcrouch | the legs' difference at -100 | halfway: knees 48° apart pushing off, 9° of roll, 116-129 mm |
| symlong | jumpsym300 | 1 500 iterations more | 112-117 mm and level, but fell 6 times in 40 in MuJoCo, and 7 in 60 below 1.1 m/s, some of them backing slowly |
| symhigh | jumpsym300 | the same, clearance paid 2 000 /m | 119-126 mm, but rolled 7° (16° at worst), 21° between the knees pushing off, and fell 3 times in 60 below 1.1 m/s |

## Before fine-tuning for the robot

Written before the robot existed. For the driving policy, D1 and D2 above have
since done the first and most of the third, from the robot on the rail, and
the fifth was measured and left alone: the sensors are far quieter than
training assumes, which errs safe. The motor's curve and the battery are still
open, and the jump task has had none of it.

The settings that stand in for things nobody has measured, and what would
replace each, in the order they matter:

1. **The delays** (`imu_delay_steps` and the rest): measure the chain on the
   bench -- a motor step, timed to its own encoder and to the IMU -- and
   narrow the ranges around it. A policy trained over a wide range is robust
   but less crisp.
2. **The motor's torque-speed curve** (`wheeled_biped_cfg.py`'s DCMotor line):
   measure torque at a few speeds on one motor. It decides top speed and jump
   height, and whether a crouch before a jump would pay
   (`../mujoco/scripted_jump.py`).
3. **Masses and rotor inertia** (`plant.py`, `tools/mass_budget.toml`): weigh
   the parts; narrow `DOMAIN_RANDOMISATION` around what is measured.
4. **The battery range** (`battery_speed_scale`): check the no-load speed at
   two voltages.
5. **Sensor noise** (`sensor_noise_std`, `sensor_bias_std`): from the IMU and
   encoders standing still.

Then fine-tune the default policy with those, a few hundred to 1 500
iterations, and check it the way every stage here was checked:
`evaluate_envelope.py`, `evaluate_jump.py`, and, from stage 8 on,
`evaluate_push.py` and `evaluate_steps.py` on the pod, then
`../mujoco/drive.py --check` with the measured delays. What the firmware must
hand the policy is in `../../docs/POLICY_INTERFACE.md`.
