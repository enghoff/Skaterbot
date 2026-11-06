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

**Nothing in git holds a trained policy.** Lose the volume and this machine's
`exports/`, and the chain has to be retrained from scratch -- about ten GPU
hours. The adopted runs are small (1.3 MB a checkpoint); keeping them
somewhere durable is worth deciding before the robot is built.

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
It has not run on the robot.


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
