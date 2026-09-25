"""Jump on command, to a commanded wheel clearance, while driving.

The rough-ground balance task with a jump added, on flat ground to begin with
-- JUMPING.md's order. Three inputs join the policy's observations, appended
after the balance task's so its trained policy can be widened into this one
(widen_checkpoint.py) and start from what it already knows:

  * the TRIGGER, 1 from the moment a jump is asked for until the robot has
    landed, or given up;
  * the TARGET CLEARANCE, how far the lowest wheel should rise off the ground
    at the top of the flight -- the clearance, not the torso's rise, because
    clearing an obstacle is the point and the legs tuck in flight;
  * the TIME since the trigger, so the policy knows where in the jump it is.

Jumps are asked for at random, every three to six seconds, at whatever speed
and turn the robot is being driven at -- JUMPING.md asks for jumps on the move,
not only from a standstill.

Two outputs join the actions: a stiffness scale and a damping scale for the
leg joints, each a factor of up to four either way around the balance task's
gains. The actuator's MIT mode takes both with every command, so a policy may
push stiff and land soft without having to detect contact first.

WHAT IS REWARDED is the flight's peak clearance against the target, once, at
touchdown; landing with both wheels together, slowly, and with the wheels
already turning at ground speed; and getting back to balance. Missing the
take-off costs a fixed amount. During the jump the thermal cost is suspended
-- the push lasts under a tenth of a second, against a rating that is a
matter of minutes -- and the cost on changing commands is eased.

TO THE MOTORS' ENVELOPE, NOT A CHOSEN ONE. The policy should never be what
limits the robot; a limit can be put on the commands later, outside it. So
drive commands run to what the wheels can do at their no-load speed, forward
and turning together, and jump targets run past anything the legs have been
seen to reach, with a cost for falling short so that an unreachable target
still means "as high as you can". Where the robot actually tops out is
measured by evaluate_envelope.py and evaluate_jump.py, not assumed.

THE SIMULATOR DECIDES HOW FAR THAT IS, AND IT IS STILL PESSIMISTIC. The
actuator's no-load speed is the vendor's 48.2 rad/s, but the torque-speed line
under it is a straight fall from the 3 Nm peak, unmeasured, which JUMPING.md
reckons costs a good third of the jump height.
"""

from __future__ import annotations

import isaaclab.terrains as terrain_gen
from isaaclab.terrains import TerrainGeneratorCfg
from isaaclab.utils.configclass import configclass

from .env_cfg import plant
from .rough_env_cfg import WHEELED_TERRAINS_CFG, WheeledBipedRoughEnvCfg

# Flat ground, in the rough task's tile grid so the same environment code runs
# on it; the curriculum is off because every tile is the same. Square rather
# than the rough task's 10 rows: at 1.9 m/s a robot crosses a 40 m field in
# twenty seconds, and scale_terrain adds columns, so 26 rows makes 16 384
# robots a field of about 100 by 130 m. Robots that near its edge are reset
# without penalty (edge_margin_m).
FLAT_TERRAINS_CFG: TerrainGeneratorCfg = WHEELED_TERRAINS_CFG.replace(
    curriculum=False,
    num_rows=26,
    sub_terrains={"flat": terrain_gen.MeshPlaneTerrainCfg(proportion=1.0)},
)

# The wheels' envelope. Top speed is the actuator's no-load speed on the 40 mm
# wheel; the fastest turn is both wheels at it in opposite directions, across
# the track. Speed and turn share the wheels, so a command can have all of
# one or all of the other, or a share of each (command_envelope).
TOP_SPEED_M_S = plant.MAX_VELOCITY_RAD_S * plant.wheel_radius_m()
TOP_YAW_RATE_RAD_S = 2.0 * TOP_SPEED_M_S / plant.geometry()["track_m"]


@configclass
class WheeledBipedJumpEnvCfg(WheeledBipedRoughEnvCfg):
    # the rough task's 25, then trigger, target clearance, time since trigger
    observation_space = 28
    # the rough task's 39, the same three, the lowest wheel's clearance now,
    # and the highest it has reached in this jump
    state_space = 44
    # the rough task's 6, then leg stiffness and damping scales
    action_space = 8

    terrain = WheeledBipedRoughEnvCfg().terrain.replace(
        terrain_generator=FLAT_TERRAINS_CFG, max_init_terrain_level=None
    )
    terrain_curriculum = False
    # A robot this close to the field's edge is reset, as a time-out rather
    # than a fall: leaving the field is not something to learn to avoid.
    edge_margin_m = 2.0

    # -- the drive command, to the envelope. Sampled evenly over the diamond
    # |speed| / top speed + |turn| / top turn <= 1, so about half of the
    # commands are under 0.5 m/s and every one is something the wheels can do
    # at no load. The tracking tolerance widens by a fifth of the command.
    command_lin_vel_x = (-TOP_SPEED_M_S, TOP_SPEED_M_S)
    command_yaw_rate = (-TOP_YAW_RATE_RAD_S, TOP_YAW_RATE_RAD_S)
    command_envelope = True
    command_tracking_relative = 0.2
    # HALF THE COMMANDS ARE EVERYDAY ONES, drawn as the balance task drew them.
    # Sampled over the envelope alone, a turn of 1 rad/s was a sliver of a
    # range running to 22, and the policy that learned to spin at 17 rad/s
    # would not turn at all below about 2.5 -- the rates a heading controller
    # asks for most.
    command_everyday_fraction = 0.5
    command_everyday_lin_vel_x = (-0.5, 0.5)
    command_everyday_yaw_rate = (-1.5, 1.5)
    # AND THE ENVELOPE OPENS GRADUALLY. Three fine-tunes with the everyday half
    # did not bring slow turns back to a policy that had lost them; the
    # policy before the envelope turned at 0.5-3 rad/s to within a few tenths.
    # So a run from that policy widens the envelope's commands from a quarter
    # of their range to all of it over this many policy steps (24 an
    # iteration), and never asks it to trade one for the other at once.
    command_envelope_start = 0.25
    command_envelope_ramp_steps = 36_000

    # -- the jump command
    jump_interval_s = (3.0, 6.0)
    # 10 to 40 mm to learn on: the first run never left the ground, and a
    # small hop is easier to land than a big one. It now reaches 36 mm when
    # asked for 40, and a scripted squat and push clears 62 mm, so the top of
    # the range is set past anything seen, and rew_jump_shortfall makes a
    # target out of reach mean as high as the legs will go.
    jump_clearance_m = (0.01, 0.12)
    # A jump that has not left the ground this long after the trigger is
    # given up, and costs rew_jump_missed.
    jump_takeoff_window_s = 0.8
    # After touchdown the trigger stays up this long, for the recovery.
    jump_recovery_s = 0.5

    # -- the legs. Wider than the balance task's, to reach a deep squat and
    # full extension: the knee's 0.8 rad becomes 1.2, the hip's 0.4 becomes
    # 0.6. widen_checkpoint.py rescales the balance policy's leg outputs by
    # the same ratio, so its behaviour is unchanged at the start.
    leg_action_scale_rad = (0.6, 1.2, 0.6, 1.2)
    # Each gain may range over a factor of four either way; zero is the
    # balance task's 12 Nm/rad and 0.4 Nm s/rad.
    leg_gain_range = 4.0

    # -- what a wheel on the ground is, on flat ground, from its axle height
    wheel_contact_tolerance_m = 0.003

    # -- rewards, in the rough task's units
    rew_jump_clearance = 15.0
    # 15 mm at first, which taught the jump to follow its target -- and then
    # left it there: by iteration 600 it cleared 18 mm when asked for 10 and
    # 31 mm when asked for 40, and a 9 mm miss still earned seven tenths of
    # the reward, so nothing pushed it further. The squat-and-push test
    # clears 62 mm, so 40 is not the robot's limit. The second stage, resumed
    # from 800, pays for a closer match.
    jump_clearance_sigma_m = 0.008
    # Per metre short of the target, at landing. The Gaussian above gives
    # nothing, and so no direction, to a jump 30 mm short; this does.
    rew_jump_shortfall = -200.0
    # THE FIRST RUN NEVER JUMPED, and these are why. An attempt usually ended
    # in a fall, which costs rew_terminated (-20) and the rest of the episode's
    # alive reward, while not trying cost only the missed jump's -5; so the
    # policy learned not to try. Missing now costs more, leaving the ground is
    # paid for on its own, and rising is paid five times as much.
    rew_jump_missed = -10.0
    rew_jump_takeoff = 5.0
    # A reward paid only at landing is a needle in a haystack for a policy
    # that has never jumped. Until it has left the ground, upward torso speed
    # is paid as it happens, so the first crouch-and-push is found by degrees.
    rew_jump_lift = 10.0
    # Vertical speed of each wheel at touchdown, squared.
    rew_touchdown_speed = -2.0
    # Seconds between the two wheels touching down.
    rew_touchdown_skew = -10.0
    # Wheel rim speed against ground speed at touchdown, squared.
    rew_touchdown_scrub = -2.0
    # The change-in-command cost during a jump, as a fraction of the usual.
    jump_action_rate_scale = 0.2
    # Sideways lean of the torso, squared (the lateral part of gravity in the
    # torso's frame). THE THIRD STAGE STOOD LOPSIDED: one leg locked straight,
    # which carries the robot's weight for no motor torque and so dodges the
    # thermal cost, and the other folded to keep the mean ride height -- with
    # the torso rolled 12 degrees, which the upright cost of -5 on pitch and
    # roll together charged almost nothing for. Found by driving the policy in
    # simulation/mujoco/drive.py; evaluate_jump.py now reports the roll. With
    # no hip roll, unequal legs are the only way to lean, so this is a cost on
    # unequal legs that still lets them differ where the ground does. At -50,
    # 400 iterations brought the lean from 12 degrees to 7.4 and left the
    # locked knee locked, so the lean is still the cheaper choice: -200 makes
    # 7 degrees cost about as much as tracking the speed command earns.
    rew_torso_roll = -200.0
    # THE ENVELOPE RUN LEFT TWO FAULTS, both where a reward had gone flat.
    # Told to drive straight at 1 m/s it turned at 1.2 rad/s, and told to
    # turn at 2.2 rad/s it turned at 0.4: past about 1 rad/s of error the
    # tracking kernel pays nothing either way, so nothing pulls it back.
    # These pay in proportion to the error, per m/s and per rad/s, so there
    # is always a direction to improve.
    rew_lin_vel_error = -1.0
    # Doubled for the fourth stage: after the third, a turn on the spot asked
    # at 0.5 to 1.5 rad/s still came out at a tenth of that -- a few hundredths
    # of a newton-metre between the wheels, where the balance policy turned
    # them against each other and tracked it.
    rew_yaw_rate_error = -1.0
    # And it still stood with one knee resting on its stop, which holds the
    # robot up for no motor torque at all, and the other bent: 3.5 degrees
    # of lean that the roll cost had narrowed and not removed. The rough task
    # leaves unequal legs free because uneven ground needs them; this ground
    # is flat, so here they are charged for directly.
    rew_leg_asymmetry = -2.0
