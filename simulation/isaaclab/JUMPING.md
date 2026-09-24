# Before training a jump

Notes for whoever writes the jump task, 24 September 2026. None of this has been
tested on the robot or in the simulator. It is arithmetic on the actuator's published
figures and the CAD's leg geometry, written down so that the task starts from
the right limits rather than discovering them.

## How high it can go

**About 10 cm of body rise is a realistic target, and 14–20 cm is the ceiling
the actuators allow.** That is a straight-up push from the deepest squat the
knee stop permits (knee at 100°, the hip 75 mm below standing) to a nearly
straight leg, with all four leg actuators at their 3 Nm peak, and the wheels
and wheel actuators, 0.46 kg between them, dragged off the floor at the end of
it. The push lasts 55–75 ms, which is short enough that the 0.8 Nm thermal
rating does not come into it.

The actuators run out of speed before they run out of torque. Each leg can push
at least 56 N at the bottom of the squat, against the 10 N a leg needs to hold
the robot up, and the leverage only improves as the knee straightens. So the take-off
speed, and therefore the height, is set almost entirely by how fast the knee can
turn:

| Output speed limit | Where it comes from | Body rise |
|---|---|---:|
| 15.7 rad/s | rated speed, 150 rpm | 3 cm |
| **20 rad/s** | **what the simulator uses today** | **4.6 cm** |
| 30 rad/s | | 8 cm |
| 48 rad/s | vendor no-load speed, 460 rpm | 14 cm |

The wheels can clear an obstacle by a few centimetres more than the body
rises, because the legs can tuck up in flight. They cannot tuck the whole 75 mm,
though: a quarter of the mass is at the bottom of the legs, so pulling the legs up also pulls the body down.

## The simulator has to be fixed first

**The simulator cannot jump more than about 5 cm as it stands.** The actuator's
speed limit in `simulation/robot.py` is a 20 rad/s placeholder, and its comment
says no vendor figure had been recorded. One has: `docs/NOTES.md` quotes the
DAMIAO manual at 460 rpm no-load and 150 rpm rated. A jump policy trained
against the placeholder would learn a 4.6 cm jump and never find out the
hardware could do three times that.

Replacing it with 48 rad/s is not the end of it. Isaac Lab's DC motor model
draws a straight line from 3 Nm at standstill to nothing at the speed limit,
which is a pessimistic reading: a real motor holds its current-limited peak some way up
the speed range before falling off, and that difference is worth 14 cm against
20 in the arithmetic above. The true curve, and the rotor inertia the model
randomises across a factor of four, both want measuring on the bench before a
jump policy is trusted on hardware. Both matter more to a jump than to
balancing, because a jump is spent entirely at the edge of the speed range.

The balance task's action scale also has to change. It lets the legs move 0.3 rad
around a slight crouch, which reaches neither the deep squat nor full extension.

## Landing is the real limit, and the motors cannot solve all of it

The motors can brake a landing comfortably. Stopping a fall in the 75 mm the
legs can fold through takes these loads:

| Drop | Landing speed | Deceleration | Force per leg |
|---:|---:|---:|---:|
| 3 cm | 0.77 m/s | 1.4 g | 14 N |
| 5 cm | 0.99 m/s | 1.7 g | 17 N |
| 10 cm | 1.40 m/s | 2.3 g | 24 N |
| 15 cm | 1.72 m/s | 3.0 g | 31 N |

All of it is well inside what the legs can push, so a controlled landing is not
short of torque.

**What no controller can soften is the first few milliseconds.** When the wheels
touch, the wheel, its actuator and the bottom of the shin stop dead before any
command can respond, and that shock goes through the urethane tyre and the
printed limb. The nearest thing this project has measured is the sideways topple
in `docs/NOTES.md`: it arrives at 1.65 m/s, and on a hard floor the limb's worst
section breaks across its layers. A 10 cm jump lands at 1.4 m/s. The load path
is different, through the tyre and along the leg rather than across it, so this
is a warning and not a prediction. But nothing yet shows that a 10 cm landing
on a hard floor is safe, and the tyre's give is the number that decides it.

The simulator will not tell you either. It models the tyre as a rigid cylinder with a little
bounce and the limbs as unbreakable, so a policy that lands hard will score
well there and break parts on the robot.

## What that means for the task

- **Let the policy soften the legs before touchdown.** The balance task holds the
  legs at a fixed 12 Nm/rad. The actuator's MIT mode takes a stiffness and damping
  with every command, so add them to the action space, bounded, and let the
  policy land soft rather than having to detect contact first. Isaac Lab's
  actuator config will need a per-step gain path for this.
- **Land with the knees bent, never near straight.** A straight leg passes the
  shock into the structure and leaves no stroke to absorb it. Somewhere around
  30–40° of knee bend at touchdown leaves most of the stroke available.
  Landing on the 100° stop is the other thing to avoid.
- **Charge for the impact directly, because nothing else will.** Penalise the
  wheels' vertical speed at touchdown and the peak contact force. The critic can
  see both even though the robot cannot.
- **Keep the torso level and land on both wheels together**, so one leg never
  takes the whole landing.
- **Do not hold the deep squat.** The knee crosses its 0.8 Nm thermal rating at
  about 47° of sustained bend, so a crouch that waits before jumping costs
  heat. Crouch and push in one movement.
- **Command the wheel clearance, and start low.** The command is how far the
  wheels should clear the ground, not how high the torso rises, because
  clearing an obstacle is the point and the legs tuck in flight -- so the
  policy gets the tuck to optimise as well as the push. Reward the flight's
  lowest wheel height at its peak against the target rather than height for
  its own sake, so a small command gets a small, gentle jump. Train from 2 cm
  upward, and put the robot's first real jumps on the hoist with slack in the
  line, starting at 3–5 cm on a soft floor.
- **Jump on the move, not only from a standstill.** The trigger should work at
  any commanded speed, so sample the forward speed and turn rate across their
  whole range when a jump is triggered. Moving changes three things the policy
  has to learn. The wheels must be turning at ground speed when they land, or
  they scrub and the robot pitches -- so hold wheel speed through the flight.
  In the air the only way to correct pitch is to speed the wheels up or slow
  them down, whose reaction turns the body, or to swing the legs. And the
  landing has forward momentum to absorb as well as vertical, so the recovery
  is a balance at speed rather than from rest.

The balance policy should keep working while this is built. A jump is a
wheeled landing followed by a balance recovery, so the jump task should start
from the trained balance policy rather than from scratch.
