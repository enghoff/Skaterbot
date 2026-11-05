# What the policy reads and what it asks for

The contract between a trained policy and the robot's electronics: what the
firmware has to hand the policy every 10 ms, in what order, units, frames and
signs, and what it has to do with the answer. A policy trained in Isaac Lab
knows nothing about the robot beyond this, so anything here the robot gets
wrong -- a flipped sign, a zero in the wrong place, a speed that clips -- is a
robot the policy has never met.

The reference implementation is the MuJoCo driver,
[`simulation/mujoco/drive.py`](../simulation/mujoco/drive.py):
`Controller.reading()` and `observe()` build the input exactly as training
did, `act()` turns the output into motor commands, and `motor_torques()` is
what the motors do with them. Firmware that produces the same numbers from the
real sensors is correct by construction. Every number below that is a task
setting is read by that driver from the run's own `params/env.yaml`, so the
exported run, not this page, is the authority for a given policy.

**Nothing here has been checked against hardware.** It is what the policy was
trained on and what the vendor documents say the parts can do.

## Timing

| | |
|---|---|
| Policy | 100 Hz, one input in, one output out, every 10 ms |
| Physics it was trained against | 400 Hz |
| Delays it is trained to tolerate (jump task, from September 2026) | IMU reading up to 10 ms old, encoder readings up to 5 ms, a command taking effect up to 5 ms late, each wandering by 2.5 ms now and then, and one command in a hundred lost |
| Delays the robot measured, and the driving policy for it is trained on (November 2026) | IMU reading 12.5-20 ms old, encoder readings up to 2.5 ms, a command taking effect 2.5-10 ms late, with the same wander and losses |

The policies before that were trained with no delay at all. In MuJoCo the
adopted jump policy stands with 1.2° of rocking at no delay, 1.5° at
5 / 2.5 / 2.5 ms, and 13° at 10 / 5 / 5 ms. **Measure the real chain on the
bench** -- a motor step, timed to its own encoder and to the IMU -- and narrow
the training ranges around the answer.

## Frames and signs

The policy's frame is the URDF's, not the CAD's: **+X forward, +Y left, +Z
up**, fixed to the torso (`base_link`). The CAD is +Y forward and +X to the
robot's right; nothing below is in CAD axes.

| Joint | Axis in the URDF | Positive means | Travel (rad) |
|---|---|---|---|
| `hip_pitch_right`, `hip_pitch_left` | −Y | thigh swings forward | ±1.047, provisional |
| `knee_right`, `knee_left` | +Y | shin folds back, relative to the thigh | 0 to 1.745, the measured stop |
| `wheel_drive_right`, `wheel_drive_left` | +Y | wheel rolls the robot forward | continuous |

The knee's angle is **relative to the thigh**, not to the torso. Both sides
share one axis in the URDF, so a positive number means the same motion on
both legs, but the motors on the two sides are mounted mirrored: **the
firmware flips the sign of one side of every pair**, whichever the bench shows
reads backwards.

**Zero is the leg hanging straight down**, knee straight, as in the URDF.
Each leg motor's encoder zero has to be set there (DAMIAO's set-zero command,
with the leg held in a jig) or offset in firmware. The encoders are
single-turn absolute on the output shaft, so a zero set once survives a power
cycle. The wheels' angle is never used, so their zero does not matter.

## The input

Every value is a 32-bit float, in this order. "Scale" is what the reading is
multiplied by before it goes in; the policy's own normaliser is inside the
exported network and is not the firmware's business.

| Index | What | Unit before scaling | Scale | From |
|---|---|---|---|---|
| 0-2 | torso angular velocity, x y z, in the torso frame | rad/s | 0.25 | IMU gyro |
| 3-5 | gravity's direction in the torso frame, a unit vector: (0, 0, −1) standing level | -- | 1 | IMU, gravity or orientation report |
| 6 | forward speed command | m/s | 1 | the operator, or the heading loop |
| 7 | turn rate command, positive to the left | rad/s | 1 | the operator, or the heading loop |
| 8 | leg height command, hip to axle, as (h − 0.1785) / 0.0285: −1 at 150 mm, +1 at 207 | m | see left | the operator; 0.2035 is the crouch trained around. Followed from about 172 to 197 mm. Policies up to `comjump` take h itself, unscaled, over 0.185-0.207 (`scale_height_command` in the run's `params/env.yaml` says which) |
| 9-12 | leg angles minus the crouch: hip R, knee R, hip L, knee L | rad | 1 | encoders; the crouch is hip 0.25, knee 0.50 |
| 13-16 | leg joint speeds, same order | rad/s | 0.05 | encoders |
| 17-18 | wheel speeds, right then left | rad/s | 0.05 | encoders |
| 19-24 | the policy's own last six outputs, after clipping to ±1 | -- | 1 | the firmware's memory; zero at start |
| 25 | jump trigger: 1 for 1.5 s from the trigger (see the jump, below), or until 0.8 s have passed without leaving the ground; else 0 | -- | 1 | jump policies only |
| 26 | jump target clearance, while triggered, else 0 | m | 10 | jump policies only |
| 27 | seconds since the trigger, capped at 2, while triggered, else 0 | s | 1 | jump policies only |
| 28 | the pack's voltage, as V / 24 − 1 | -- | 5 | the carrier's INA226; jump policies from September 2026 on |

A balance policy has the first 25; a jump policy 28, or 29 once it is told the
battery. The exported network says which: its input is named `obs` and its
width is the count.

**The battery is an input because without it the policy drives as if the pack
were flat.** A motor's no-load speed goes with its supply, so at speed a low
pack leaves less torque to balance with; a policy that cannot tell kept back
enough for the worst case, and topped out at 1.05 m/s where it had held 1.43.
Feed it the voltage as read, sag and all: a pack that sags under a hard push
really does have less speed to give at that moment. 0.25 is a full 25.2 V pack,
0 the rated 24 V, −1 the 19.2 V cut-off.

**The IMU's position does not matter, its orientation does.** Angular velocity
and gravity's direction are the same everywhere on a rigid torso, so the
BNO085 30 mm above the hip axis reads what the torso's origin would. But its
axes have to be mapped onto the torso's, through the chip's orientation record
or in firmware, and a seat a degree or two off level is a standing bias in
index 3-5. Training carries a random bias of about that size, so a small one
is survivable; calibrate it out anyway, standing the robot level.

**Use the gravity report or a 6-axis orientation, not the magnetometer.** The
BNO085's game rotation vector and gravity report both leave the magnetometer
out, which six motors beside it would upset. Gravity from the game rotation
vector q is the third row of its rotation matrix, negated.

## The output

Eight numbers from a jump policy, six from a balance policy. **Clip every one
to ±1 first**; the policy was trained with that clip and has learnt to ask
for more than it gets.

| Index | What | Becomes |
|---|---|---|
| 0-3 | leg targets: hip R, knee R, hip L, knee L | angle = crouch + scale × output, scale 0.6 rad for a hip and 1.2 for a knee (jump task; 0.3 in the balance task), then held inside 95 % of the joint's travel about its middle |
| 4-5 | wheel torque, right then left | 0.6 Nm × output |
| 6 | leg stiffness | 12 Nm/rad × 4^output, so 3 to 48 |
| 7 | leg damping | 0.4 Nm·s/rad × 4^output, so 0.1 to 1.6 |

All of it goes out in DAMIAO's **MIT mode**, one frame per motor per policy
step, and held until the next:

* **legs**: position = the angle above, velocity = 0, Kp = the stiffness,
  Kd = the damping, feed-forward torque = 0. The motor closes that loop
  itself, many times faster than the policy, which is what training assumed.
  A balance policy has no index 6-7; send 12 and 0.4.
* **wheels**: position and velocity = 0, Kp = Kd = 0, feed-forward torque = the
  torque above.

Both gains fall well inside MIT mode's 0-500 and 0-5.

**Do not add a torque-speed limit of your own.** In simulation the motor model
takes torque down to zero at the no-load speed; the real motor does that
physically, because it runs out of voltage. A second limit in firmware would
be one the policy never trained against. The motor's own current limit, at
the 3 Nm peak, is the one to keep.

## The motors' settings

The feedback frame maps each reading linearly over ±P_MAX, ±V_MAX and ±T_MAX,
set in registers 0x15-0x17. Their factory values are not recorded in this
repository. Before anything else, read them, and set them to cover the
policy's range:

| Register | At least | Why |
|---|---|---|
| V_MAX | 55 rad/s | a wheel reaches 50.6 rad/s with the pack full; below that its speed clips at speed, and the policy is blind to it |
| T_MAX | 3 Nm | the peak torque the policy commands through |
| P_MAX | π | the leg joints' whole travel |

The same range has to be used to decode the feedback and encode the commands.
At V_MAX 55 the 12-bit speed is resolved to 0.027 rad/s, which is finer than
the noise training assumes.

Also set: each motor's **communication time-out**, so a crashed controller
leaves the motors off rather than holding the last torque; and its
**undervoltage threshold**, which the bill of materials puts at 21.6 V.

## Two policies: one drives, one jumps

For now the robot needs only the first, and it is the smaller shape: the driving
policy for the robot (`rough-2026-11-04_09-01-34_measured_fix`) is a balance
policy, 25 inputs and 6 outputs. What follows is the plan for when it jumps.

No single policy both drove well and jumped well: every fine-tune that tried
traded one for the other
([TRAINING_HISTORY.md](../simulation/isaaclab/TRAINING_HISTORY.md)). So the
robot carries two networks of the same shape, 29 inputs and 8 outputs, 193 KB
each, which both fit the G474's 512 KB of flash. The driving policy runs until
a jump is asked for. The jump policy then takes the robot through the crouch,
the jump and the landing, and hands it back. `TwoPolicies` in the MuJoCo
driver is the reference, and `drive.py --jump-run RUN` drives on the default
policy and jumps on RUN.

**Nothing is reset at a handover.** The incoming policy is fed exactly what the
outgoing one would have been: the same readings, and as its last outputs
(index 19-24) the ones the outgoing policy last sent. The motors hold their
command until the incoming policy's first answer replaces it. The driving
policy is always fed a trigger of zero (index 25-27).

**The jump, in the order the jump policy was trained to expect it:**

1. On the press, hand over to the jump policy and ask for the lowest ride
   height, index 8 = −1 (150 mm), with the trigger still 0.
2. As soon as the legs are within 5 mm of it -- a mean hip-to-axle height of
   155 mm or less -- or 0.6 s after the press at the latest, raise the trigger:
   index 25 = 1, index 26 = the clearance (0.12 m, as trained) × 10, index 27 =
   the seconds since this moment. Each leg's height comes from its joint
   angles alone, 0.105 cos(hip) + 0.105 cos(knee − hip) m, so it needs no
   estimate of where the ground is. In MuJoCo the crouch takes 0.1 s.
3. Hold the ride height at the bottom until 0.5 s after the trigger, then
   give the operator's height back.
4. 1.5 s after the trigger, drop it to 0 and hand back to the driving policy.

**No landing detection is needed.** Training held the crouch until both wheels
were back on the ground, which the simulator knows and the robot does not. But
the timing hardly matters. In MuJoCo, with the robot's delays, releasing it at
take-off, at touchdown, up to 0.2 s after touchdown, or at a fixed 0.4-0.6 s
after the trigger gave the same falls, within 6 mm of the same clearance, and
legs back at ride height. At 0.7 s the robot starts to sink back into a
second crouch.

**Jump only below about 1 m/s.** The jump policy does not drive fast: asked
for 1.45 m/s it holds 0.5, and a robot handed to it faster than it can drive
lands in trouble. In MuJoCo, with the robot's delays, quickcrouch fell in 3 of
40 randomised jumps, every one of them at 1.2-1.4 m/s, and jumpsym300 in 2.
With jumps held below 1.1 m/s, jumpsym300 fell in none of 60. Refuse the jump
above 1 m/s, or slow down first.

## The operator's command

A game controller paired through the console gives index 6, 7 and 8 and the jump
press, by way of `sbc/gamepad.py`, diagd, and a DRIVE message over J5
([DIAGNOSTICS.md](DIAGNOSTICS.md#the-controllers-link-j5)). `diag_link::Drive`
parses it. **The firmware at the far end of that does not exist yet**, so today
the path ends at diagd, where a policy on the Pi, `sbc/balance.py --drive`, can read it.

| In DRIVE | Unit | Becomes |
|---|---|---|
| forward | mm/s, i16 | index 6, in m/s |
| turn, positive to the left | mrad/s, i16 | index 7, in rad/s |
| height | 0.1 mm, u16 | index 8, scaled as that index says |
| live | bit 0 of flags | see below |
| jump | u8, counts presses | a change while live is a press: the jump, above |

They come fifty times a second for as long as a controller is connected, and
what the firmware does with them is this:

1. **Announce it.** diagd sends a DRIVE only to an image whose INFO says
   `drive=1`, so that today's `firmware/diag` is never sent one.
2. **Not live, or nothing for 200 ms, is a speed and a turn of zero.** It is not
   a reason to stop the motors: a robot told to stand still stays up, and a robot
   with its motors cut falls over. Keep the last height. Not live means Linux has lost the
   controller; a control held still sends nothing, and goes on counting until then, or
   until it is let go of. A live DRIVE is not leave to start the motors, or
   to go on after a fall.
3. **Nothing on the controller stops the motors**, since that would drop the robot.
   Stopping is the link's ordinary STOP, which every image already obeys.
4. **Refuse a jump above 1 m/s**, measured, as the jump's section says. The
   press is counted on the Pi, which does not know the robot's speed.

A stick's end asks for 0.5 m/s and 1.5 rad/s on starting, which the console can
lower and not raise, and the height runs from 185 to 207 mm, starting at 203.5.
Those are the trained ranges of the driving policy for the robot
(`rough-2026-11-04_09-01-34_measured_fix`), kept as constants in `gamepad.py`:
**change them with the run that is deployed**, and for a run with
`command_envelope` set `ENVELOPE` too. That policy cannot jump, so it has no use
for the jump count yet. Something
running a policy off the controller can have the same numbers from diagd's
`drive` stream, and owes them the same 200 ms rule.

## What the policy does not do

It does not know where it is or which way it faces: holding a heading or a
place has to be a loop outside it, turning a target into speed and turn
commands. It does not see motor temperatures or fault codes, the battery, or
whether it has fallen. **A tilt beyond about 20° cutting the motors** (NOTES.md; `sbc/balance.py`
uses 30°, and [SYSID.md](SYSID.md#running-the-policy-on-the-robot) says why),
fault handling and any limit on the commands a person can give all belong to
the firmware, around the policy, not in it.
