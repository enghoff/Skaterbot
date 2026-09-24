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

THE SIMULATOR DECIDES HOW HIGH, AND IT IS STILL PESSIMISTIC. The actuator's
no-load speed is the vendor's 48.2 rad/s now, but the torque-speed line under
it is a straight fall from the 3 Nm peak, which JUMPING.md reckons costs a
good third of the height. The target range is set inside what that line
allows; widen it when the actuator has been measured.
"""

from __future__ import annotations

import isaaclab.terrains as terrain_gen
from isaaclab.terrains import TerrainGeneratorCfg
from isaaclab.utils.configclass import configclass

from .rough_env_cfg import WHEELED_TERRAINS_CFG, WheeledBipedRoughEnvCfg

# Flat ground, in the rough task's tile grid so the same environment code runs
# on it; the curriculum is off because every tile is the same.
FLAT_TERRAINS_CFG: TerrainGeneratorCfg = WHEELED_TERRAINS_CFG.replace(
    curriculum=False,
    sub_terrains={"flat": terrain_gen.MeshPlaneTerrainCfg(proportion=1.0)},
)


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

    # -- the jump command
    jump_interval_s = (3.0, 6.0)
    # Low to begin with: the first run never left the ground, and a small hop
    # is easier to land than a big one. A scripted squat and push in this
    # simulator clears 17 mm from a moderate squat and 62 mm from a deep one,
    # so there is room to raise this once the policy jumps at all.
    jump_clearance_m = (0.01, 0.04)
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
    jump_clearance_sigma_m = 0.015
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
