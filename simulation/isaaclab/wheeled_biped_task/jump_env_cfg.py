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


STEPS_BORDER_M = 0.25


def stairs_platform_m(cfg) -> float:
    """The platform Isaac Lab's pyramid of steps actually builds at the top.

    Its ring count, from mesh_terrains.pyramid_stairs_terrain, can leave less
    than the platform asked for, or less than nothing (step_platform_m).
    """
    span = WHEELED_TERRAINS_CFG.size[0] - 2 * STEPS_BORDER_M
    rings = (span - cfg.step_platform_m) // (2 * cfg.step_width_m) + 1
    return span - 2 * rings * cfg.step_width_m


def steps_terrain(cfg) -> TerrainGeneratorCfg:
    """The flat field with a share of its columns made pyramids of steps.

    Each step tile is a flat platform at the top with steps falling away on
    all four sides, so a robot starting on it can only drive down. Rows are
    difficulty, so a curriculum raises the steps as it copes.
    """
    platform = stairs_platform_m(cfg)
    if platform < 0.8:
        raise ValueError(
            f"steps: the platform would be {platform:.2f} m across; see step_platform_m"
        )
    return WHEELED_TERRAINS_CFG.replace(
        curriculum=True,
        num_rows=10,
        sub_terrains={
            "flat": terrain_gen.MeshPlaneTerrainCfg(
                proportion=1.0 - cfg.steps_fraction
            ),
            "steps_down": terrain_gen.MeshPyramidStairsTerrainCfg(
                proportion=cfg.steps_fraction,
                step_height_range=cfg.step_height_range_m,
                step_width=cfg.step_width_m,
                platform_width=cfg.step_platform_m,
                border_width=STEPS_BORDER_M,
            ),
        },
    )


TOP_SPEED_M_S = plant.MAX_VELOCITY_RAD_S * plant.wheel_radius_m()
TOP_YAW_RATE_RAD_S = 2.0 * TOP_SPEED_M_S / plant.geometry()["track_m"]


@configclass
class WheeledBipedJumpEnvCfg(WheeledBipedRoughEnvCfg):
    # the rough task's 25, then trigger, target clearance, time since trigger,
    # and the battery's voltage (observe_battery)
    observation_space = 29
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
    # That was (0.01, 0.12); since jump_score_max it is a single 120 mm, and
    # a jump is scored on how high it goes (see rew_jump_com_rise).
    jump_clearance_m = (0.12, 0.12)
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

    # -- the ride height. NO POLICY EVER FOLLOWED IT: every one, the balance
    # policy included, stood at one height whatever it was asked, because the
    # observation noise over the whole input put 0.02 m of noise on a command
    # whose range was 0.022 m. The noise is now on the sensors alone, the
    # command reaches the policy as -1 to 1 over its range, and the range is
    # wider: from nearly straight down to 150 mm, where the knee is near 90
    # degrees and holding the robot takes about its 0.8 Nm thermal rating --
    # somewhere the thermal cost lets it visit rather than live.
    command_leg_height_m = (0.150, 0.207)
    scale_height_command = True
    # AND STILL LITTLE: with the noise gone and the range widened, a policy
    # asked for 150 to 207 mm stood at 178 to 187, because the tracking
    # reward's kernel is 10 mm wide and pays nothing at the 30 mm it had to
    # move. Paid in proportion now, as the speed error is. At -30 (push,
    # 2026-09-26) it stood at 168 to 199, at -100 (heightcost) 171 to 197:
    # the bottom 20 mm of the range it will not go to, at any price tried.
    # A policy that rode low for steps stood at 151 when asked for 150, so
    # the legs can; what stops it is not known.
    rew_leg_height_error = -100.0

    # -- what a wheel on the ground is, on flat ground, from its axle height
    wheel_contact_tolerance_m = 0.003

    # -- rewards, in the rough task's units
    rew_jump_clearance = 0.0  # 15 while jumps had targets
    # 15 mm at first, which taught the jump to follow its target -- and then
    # left it there: by iteration 600 it cleared 18 mm when asked for 10 and
    # 31 mm when asked for 40, and a 9 mm miss still earned seven tenths of
    # the reward, so nothing pushed it further. The squat-and-push test
    # clears 62 mm, so 40 is not the robot's limit. The second stage, resumed
    # from 800, pays for a closer match.
    jump_clearance_sigma_m = 0.008
    # Per metre short of the target, at landing. The Gaussian above gives
    # nothing, and so no direction, to a jump 30 mm short; this does.
    rew_jump_shortfall = 0.0  # -200 while jumps had targets
    # THE ENVELOPE POLICY DID NOT REALLY JUMP. Asked for 120 mm it snapped its
    # knees from 0.9 to 1.8 rad in 40 ms and pulled the wheels up faster than
    # the body could fall: 93 mm of wheel clearance with the torso rising
    # 15 mm, and a tenth of a second off the ground. Wheel clearance was all
    # it was paid for. This pays, at landing, for the torso's own rise above
    # where it was at the trigger, as a share of the target -- capped there,
    # so a 10 mm hop is not pushed higher than asked -- which only a crouch
    # and a push can earn, and which is what keeps the wheels up for longer.
    # At 10 the first run with it lifted the torso 20 mm on small jumps and
    # 11 on big ones: snapping the legs up still paid better than learning to
    # crouch and push. Tripled. AND OFF AGAIN: at 30, alone, the torso rose
    # 17-21 mm, no more than without it; with a five-fold shortfall cost
    # beside it, 30 mm on small jumps and still 101 mm at most, for a quarter
    # of the top speed. 101 mm is where every run has stopped.
    rew_jump_rise = 0.0
    # AND IT STILL DID NOT CROUCH: the wheels left the ground 30 ms after the
    # trigger with the torso dipping under a millimetre. A crouch costs time,
    # and time cost reward three ways: the landing's pay is discounted about
    # 1 % per step it comes later, a tuck earns the clearance soonest, and the
    # vertical-speed cost charged the dip and the push. And the riding stance
    # is 7 mm short of straight legs, so without a crouch there is nothing to
    # push through: folding to the knee stop lifts the wheels 68 mm, and the
    # 101 mm every run stopped at is that fold plus a small hop.
    # So, with jump_score_max on, a jump is paid per metre of its highest
    # wheel clearance, once, at jump_window_s after the trigger whenever it
    # took off and landed -- no target to match and no reason to hurry -- and
    # nothing charges vertical speed while it jumps. The target terms above
    # are then weighted to zero by the run's overrides, not deleted.
    jump_score_max = True
    rew_jump_height = 100.0  # 400 when it was all that was scored
    jump_window_s = 1.5
    # AND SO EVERY JUMP WAS AS HIGH AS IT COULD GO, which is no way to start on a
    # robot that has never landed one: the owner wants to begin small and work up.
    # With this on, clearance and the centre of mass's rise are paid only up to
    # the target (the centre of mass up to jump_com_share of it), and every metre
    # past the target costs rew_jump_overshoot. The target is still drawn from
    # jump_clearance_m. The tuck that scored on clearance alone is why the centre
    # of mass is paid as well; the cap keeps a small jump from being a push.
    jump_score_to_target = False
    jump_com_share = 0.6
    rew_jump_overshoot = 0.0
    # AND STILL NO CROUCH: scored so, at 400 and at 1000 per metre, it took
    # off 30 ms after the trigger as before and cleared 95 and 103 mm. The
    # tuck was already learned, and a half-learned crouch pays less than it:
    # a scripted squat and push clears 62 mm, under the fold's 68, so a push
    # only pays together with a tuck in the air. So the torso's own rise in
    # flight is paid as well, per metre, at the same moment -- which the
    # tuck earns nothing of -- and the run starts with more exploration
    # noise on the legs (widen_checkpoint.py --set-std).
    rew_jump_body_rise = 0.0
    # AND THE TUCK WAS NEVER A JUMP. Traced in MuJoCo, every policy scored on
    # wheel clearance cleared about 100 mm by folding its knees to the 100
    # degree stop, which pulls each axle up about 108 mm toward its hip,
    # while the torso rose 15-30 mm, pitched about 50 degrees as the legs
    # swung up, and the wheels left the ground 20-30 ms apart. So, with
    # jump_score_max on, the whole robot's centre of mass is paid for its
    # rise in flight, per metre, at the same moment as jump_height; the
    # torso's pitch is charged, squared, for as long as a jump lasts; and the
    # gap between the two wheels leaving the ground is charged once, per
    # second. Fine-tuned so from the battery policy, with the legs'
    # exploration noise raised to 0.4, the pitch fell from about 50 degrees
    # to 20-25, the centre of mass rose 31-33 mm, the wheels cleared 82 mm
    # (84 in MuJoCo, where the tuck had cleared 101), and it drove faster than
    # any policy before it, 1.29 / -1.36 m/s -- but slow turns went weak, 0.5
    # rad/s asked giving 0.1. Without the clearance term (rew_jump_height 0)
    # it fell after four jumps in five and forgot how to turn.
    rew_jump_com_rise = 2000.0
    rew_jump_pitch = -200.0
    rew_liftoff_skew = -200.0
    # THE JUMP IS A TUCK, and cannot use a crouch. Of the 80 mm the wheels
    # clear, the centre of mass rises about 30; the rest is the shins pulled
    # up. Asked for its lowest ride height first, the default policy jumped
    # worse, 8 mm of rise; a policy that happened to ride at 160 mm (steps,
    # 2026-09-26) pushed off from it for 67-74 mm, and for 109 mm from its
    # lowest, pitching 35-42 degrees (MuJoCo). So a wind-up: for
    # jump_windup_s after the trigger the legs are charged per metre above
    # the bottom of the ride height's range, and the jump is scored as
    # before, its rise measured from where the centre of mass was at the
    # trigger -- so sinking first costs nothing if the push goes higher. The
    # policy sees the time since the trigger, so the firmware need do nothing.
    # It has to be felt: the rise pays once, about 60 a jump at 31 mm, and a
    # charge per second over 0.3 s is small beside it -- at -100 /m, 1.4 a
    # jump for not crouching at all; at -1000, 14.
    # IT SANK AND DID NOT PUSH. At -3000 for 1 500 iterations from the
    # default (windupcont, 2026-09-27) the policy learned the sink, and in
    # MuJoCo pushed off from a 150 mm stance for 58 mm of rise -- but from
    # 45 mm lower, so its apex stayed below the tuck's from standing, and the
    # score, rightly measured from the trigger, kept the tuck: 26-31 mm, as
    # before. With the legs' exploration reset (windupexplore) the same.
    # What it did do was follow the ride height over the whole range, 148
    # to 202 mm, and drive faster, 1.34 / -1.45 m/s -- losing slow turns and
    # angled steps. The strong push is the steps policy's, 109 mm from 150.
    jump_windup_s = 0.3
    rew_jump_windup = 0.0
    # SO THE CROUCH IS ASKED FOR, NOT LEARNED. Made to follow the ride height
    # (mergeheight, -1000 /m, 2026-09-27), the steps policy kept its push but
    # only from low: asked for 150 mm and then to jump, its centre of mass
    # rose 86 mm and the wheels cleared 113 mm (MuJoCo); from 203, 32 and 84.
    # So for jump_crouch_s before each trigger, and until the jump is over,
    # the ride height asked for is the bottom of its range -- in training as
    # the firmware will do it on the robot -- and the policy jumps from where
    # its push works. 0 is off: the trigger comes as the operator presses.
    # At 0.6 s, with clearance paid 1000 /m to bring the tuck back on top of
    # the push and the pitch charged -400, from mergeheight (crouchmerge,
    # 2026-09-27): 152-155 mm cleared, the centre of mass 84 mm above where
    # it stood, 36 degrees of pitch -- MuJoCo, with the robot's delays, 143 to
    # 164 mm -- but it drove at 0.84 m/s, turned weakly and spun on one wheel
    # standing at 150 mm. From the default instead (crouchdefault) it never
    # learned to push from the crouch. The jump and the driving would not
    # share one policy; handed over between two in MuJoCo, they do.
    # Now the longest the crouch may take: the jump comes the moment the
    # legs' mean height is within jump_crouch_tolerance_m of the bottom --
    # a waiting crouch looked like hesitation -- and the operator's height is
    # asked for again from the landing, not after the jump's whole window,
    # which had the robot sink back into a second crouch. The firmware can
    # do both: the height is the joint angles' alone (_leg_geometry).
    jump_crouch_s = 0.0
    jump_crouch_tolerance_m = 0.005
    # AND IT CROUCHED IN THE SPLITS: at 150 mm, before the trigger, one wheel
    # 101 mm ahead of its hip and the other 66 mm behind, one of them off the
    # ground (crouchmerge, MuJoCo); its parent crouched there evenly. The only
    # cost on it, wheel_stagger, was about 1 a crouch against some 200 for
    # the jump, and off in the jump itself. This charges the split per metre
    # through the crouch and the jump.
    rew_jump_stagger = 0.0
    # And it turned in the air: across a jump its heading swung 53 degrees
    # at the median and up to 164 (crouchmerge, 40 in MuJoCo with the
    # robot's delays), the default's 14 and 43. The turn-rate cost charged
    # about 1 for 53 degrees. This charges, per radian, the heading turned
    # beyond the turn asked for since the crouch, for as long as it is off.
    rew_jump_heading = 0.0
    # AND IT JUMPED LOPSIDED, every jump policy there has been: the right knee
    # folded 50-90 degrees further than the left and the right hip 25-45,
    # pushing off and tucking alike (MuJoCo, 2026-09-28). Low jumps got away
    # with it, 2 degrees of roll at 80 mm; quickcrouch's 130 mm rolled 14
    # degrees in the air and turned 66. No cost could tell which leg did the
    # work, and every run inherited the habit from the one before. This
    # charges the legs' difference, per radian squared, through the crouch and
    # the jump; the always-on leg_asymmetry below is 2, too little to notice.
    # rsl_rl's mirror loss would be the general cure, but the policy's
    # stiffness and damping outputs run to +/-250 behind their clip, and the
    # difference there would swamp it. At -300 the knees went from 78 degrees
    # apart to 13, the roll from 14 to 4 and the turn from 66 to 8, for a
    # sixth of the clearance (jumpsym300); -100 went halfway (jumpsym100).
    rew_jump_leg_asymmetry = 0.0
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
    # AND THEN IT WOULD NOT LEAN INTO A TURN. Level whatever it did, at 1 m/s
    # and 3 rad/s its inside wheel carried 4 N against 17 and was off the
    # ground a quarter of the time, and at 4 m/s2 more than half -- close to
    # rolling over, with a 170 mm track under a torso 0.3 m up. So the lean is
    # now measured against the lean the turn needs, the tilt that puts gravity
    # and the centripetal acceleration together down between the wheels and
    # loads them equally; driving straight, that is level, as before. Taken
    # from the commanded speed and turn: from the measured ones, the first
    # run with it stopped driving fast altogether (0.2 m/s when asked 1.9),
    # because at speed the turn rate's wobble made the target unfollowable.
    rew_torso_roll = -200.0
    # AND LEANING INTO THE TURN DID NOT LOAD THE WHEELS: told to, the run with
    # it lean on alone leaned 13 to 17 degrees in arcs by tipping the whole
    # robot onto its outside wheel, with the inside one in the air all the
    # time. With no hip roll, tipping is cheaper than shortening a leg. So the
    # wheels themselves are charged for leaving the ground, per wheel per
    # second, when not jumping. Off: at -4 it changed nothing. In MuJoCo the
    # inside wheel still fell to 2-4 N of 20 at 3-4 m/s2, as before -- the
    # tipping limit of a 170 mm track under that centre of mass -- and the
    # run lost 0.1 m/s of top speed. Isaac Lab saw neither policy lift a wheel
    # in those arcs; MuJoCo's soft contact chatters, even spinning on the spot.
    rew_wheel_lift = 0.0
    wheel_lift_full_m = 0.01
    # The most the target lean may ask for. The commanded speed times turn rate
    # runs past 1 g at the envelope's middle -- 1 m/s at 11 rad/s -- and a run
    # asked to lean that far fell sixteen times as often. Unequal legs across
    # the 170 mm track lean the torso about 20 degrees at most.
    max_turn_lean_rad = 0.35
    # Off, the lean cost holds the torso level whatever the turn, as the
    # envelope policy was trained. Off: see rew_wheel_lift.
    lean_into_turns = False
    # THE ENVELOPE RUN LEFT TWO FAULTS, both where a reward had gone flat.
    # Told to drive straight at 1 m/s it turned at 1.2 rad/s, and told to
    # turn at 2.2 rad/s it turned at 0.4: past about 1 rad/s of error the
    # tracking kernel pays nothing either way, so nothing pulls it back.
    # These pay in proportion to the error, per m/s and per rad/s, so there
    # is always a direction to improve. Tripled with the battery input: at -1
    # the fine-tune from the stand-still policy held 1.03 / -1.04 m/s at the
    # top command, at -3 1.12 / -1.20. Doubled again with the steps
    # (heightstepsfast, 2026-09-26), and it changed nothing: 1.12 / -1.23
    # against 1.13 / -1.28 at -3. Forward top speed has fallen from 1.29 since
    # the ride height's range widened, and it is the policy's choice, not the
    # motors': driving forward flat out, its wheels turn at two thirds of
    # their no-load speed, and it drives slower asked for 1.93 m/s than for
    # 1.45.
    rew_lin_vel_error = -6.0
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
    # Eased from -2 when the lean began to follow the turn: leaning into a turn
    # is done with unequal legs, and the lean cost now holds the stance level
    # when the robot is not turning. Back to -2 with the lean.
    rew_leg_asymmetry = -2.0

    # STANDING STILL IT ROCKED: 1.2 degrees at 2.6 Hz with the legs working
    # 3.5, where the balance policy stands dead still -- nothing here paid for
    # being still. And it creeps and turns, which it cannot see and no reward
    # can fix: holding a heading and a place is a loop outside the policy.
    # Fine-tuned from it for 1500 iterations with the delays and battery
    # below, at 1 and at 3 both stood dead still in MuJoCo -- under 0.2
    # degrees at the worst delays, where it had rocked 13 -- and 3 kept the
    # jump's accuracy and did not fall reaching for 150 mm. BOTH LOST TOP
    # SPEED: 1.0-1.1 m/s asked for 1.9, where it held 1.43, with the wheels
    # at 58 % of no-load and asking for no torque. Not yet explained.
    rew_stand_still = 3.0

    # THE ROBOT'S DELAYS, which a policy trained without them meets for the
    # first time on the robot. From the datasheets, until a bench measures
    # them: the BNO085's fused output is 3.7 ms old at 200 Hz and 6.6 at 100,
    # before the I2C read; a motor's position and speed are its reply to the
    # last command, a bus round trip old; and a command crosses the UART to
    # the MCU and the CAN bus before it takes effect. Each is drawn per
    # episode, in physics steps of 2.5 ms, and wanders by a step now and then;
    # one command in a hundred is lost, and the last one runs on.
    imu_delay_steps = (0, 4)
    joint_delay_steps = (0, 2)
    action_delay_steps = (0, 2)
    delay_jitter_prob = 0.1
    command_drop_prob = 0.01
    # THE BATTERY. The motors' 48.2 rad/s no-load speed is the vendor's at
    # 24 V, and a motor's no-load speed goes with its supply: the 6S pack is
    # 25.2 V full and cut off at 19.2, 1.05 to 0.8 of that, and it sags under
    # a hard push. The current limit, not the voltage, sets the 3 Nm at low
    # speed, so only the speed scales. Physics, not a measurement.
    # AND IT COST MOST OF THE TOP SPEED: the same run with the battery held
    # full held 1.30 m/s at the top command, against 1.05 with it drawn and
    # 1.11 with the delays off instead. The policy cannot see the battery, so
    # it keeps back the torque a flat pack would need to balance at speed.
    battery_speed_scale = (0.75, 1.05)
    # So it is told: the carrier's INA226 reads the pack's voltage already.
    # Appended last, so a policy without it can be widened into one with it.
    # NOT YET USED: fine-tuned from the stand-still policy, which had already
    # learnt to keep torque back, it drove as fast at 0.8 of the rated voltage
    # as at 1.05 -- 1.17 m/s both. The input's weights start at zero, and
    # 1500 iterations from a policy that never needed it did not grow them.
    # From the envelope policy instead, widened to take it, with everything
    # else as here: 1.27 m/s at 1.05 and 1.17 at 0.8 in MuJoCo, so the input
    # is used, if weakly; Isaac Lab, full pack, 1.19 / -1.06 m/s, and jumps
    # to 110 mm where every earlier run stopped at 101. At 0.8 it fell in the
    # fastest arc, which asks the wheels for more than the pack can give.
    observe_battery = True

    # -- steps, driven down. This share of the field's columns is pyramids of
    # steps (steps_terrain), the rest flat; 0 is the flat field alone.
    # The policy sees no terrain, so a step is something it meets, not plans
    # for: a robot on a step tile starts at the top and is reset, as a
    # time-out, once it has driven off its tile, so it only ever meets steps
    # going down; one on the flat is reset before it can drive into a
    # staircase from below. No jumps are asked for on the steps, where the
    # wheels' clearance would be measured from the wrong floor. From the
    # ride-height policy, 1 500 iterations of it took 60-80 mm steps from
    # 40-90 % made at 0.7 m/s and over to 92-100 %, square or at 30 degrees
    # (evaluate_steps.py); slow and at an angle it still falls. With the
    # height cost at -30 (steps, 2026-09-26) it did better on steps by riding
    # at 160 mm whatever it was asked, and stopped turning below 2 rad/s.
    steps_fraction = 0.3
    step_height_range_m = (0.02, 0.10)
    # Wide treads: one drop at a time rather than a staircase to fall down.
    step_width_m = 0.6
    # Isaac Lab counts one ring of steps more than the platform leaves room
    # for, (tile - 2 border - platform) // (2 tread) + 1, and the platform is
    # what is left over: on a 4 m tile with a 0.25 m border, a 1.0 m platform
    # asked for three rings and left a platform -0.1 m across, a post a step
    # high that every robot started on. From 1.2 (to 2.3) it is two rings and
    # a 1.1 m platform, three drops to the floor. The pushsteps run of
    # 2026-09-26 trained on the post, and its step results are void.
    step_platform_m = 1.2
    steps_init_level = 2
    # -- pushes, fore and aft. None keeps the rough task's +/-0.5 m/s. At
    # +/-1.0 (push, pushsteps, 2026-09-26) top speed fell from 1.18 to 0.94
    # m/s, which is 1.93 less 1.0: the policy kept a shove's worth of wheel
    # speed in hand, since a shove past the motors' top speed cannot be
    # caught. And it bought nothing: the policy it started from already stood
    # up to 1.5 m/s shoves standing, and fell at 2.0 as the trained ones did.
    push_x_m_s = None
