# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "pyserial>=3.5"]
# ///
"""Run the trained policy on the robot, from the Banana Pi, through diagd.

    python3 balance.py dry              motors off: tip it by hand and see what it would do
    python3 balance.py hold             on the floor, on slack strings, steadied by hand:
                                        legs into the crouch and held, no policy
    python3 balance.py run              on the floor, on slack strings: the policy
    python3 balance.py lower            held in the air, then lowered until it stands and
                                        steadied by hand: measures what touch feels like
    python3 balance.py launch           held in the air, then lowered and let go: it
                                        feels the floor and starts the policy itself

`dry` never enables a motor and is safe anywhere. It asks for each move in turn,
sees it happen and says what the policy would do, which proves the IMU's axes and
the wheels' signs against the policy itself. It says what it sees as it goes, and
moves on by itself.

`hold` enables the motors, eases the legs to the crouch over three seconds at low
stiffness, and holds them at the policy's kp 12, kd 0.4, with no torque on the
wheels. The policy runs alongside and is logged, but is not obeyed.

`run` does the same, then waits for Enter with the robot upright on its wheels,
and hands over to the policy for --seconds. Stop it with Enter, or Ctrl-C, or the
power button. All of them, like anything
else that stops it, cut the motors at once, so the robot drops onto its strings:
never run this on a robot that nothing will catch. --drive takes speed and turn
from the game controller, capped by --max-speed and --max-turn; without it the
robot stands, holding its place.

`lower` and `launch` start with the robot held clear of the floor, by the torso,
legs hanging. The legs ease to the crouch as they do for `hold`, but in about a second
and a half, since they carry nothing and somebody is holding the robot up, and the
wheels stay free. `lower` only watches for --seconds, and from what it saw writes launch.json,
which `launch` needs: how much each knee has to feel. `launch` waits for that, for at
most --touch-wait, and starts the policy the moment both knees have it, with no word
from anyone. Picked up while running it stops the wheels, puts the legs back in the
crouch and waits for the floor again; fallen over it lets go of everything and waits
to be picked up, which it knows by being upright with its legs hanging. So one tap arms
it for as long as it runs, and that goes for being armed on the floor as well: a tap
always sends the legs to the crouch, gently, wherever they are. --once makes either of
those the end of the run. docs/SYSID.md has what to do with your hands.

--button is how launcher.py runs it. It loads, and then waits for launcher.py's word to
begin, so that a tap is answered without the second loading takes; it takes control from
whatever holds it, the button being the nearer hand; it says what it is doing in
--phase-file; and told to wake while limp, it does.

It stops the motors if the torso tilts past --tilt, a motor faults, overheats,
overspeeds or stops answering, a leg leaves its window, the IMU stops, or a step
runs very late. If this program dies, diagd stops them within half a second, and
the motors drop out by themselves 200 ms after their last command.

Run it on the Pi, in the same place as sysid.py, with policy.npz beside it, which
sbc/pack_policy.py writes. sbc/policy_loop.py is the loop itself, and
simulation/mujoco/balance_check.py runs that same code against MuJoCo. Everything
goes in ~/sysid_logs in sysid.py's format, with a "p" record for each policy step.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import signal
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import diag_client  # noqa: E402
import numpy as np  # noqa: E402
import policy_loop as pl  # noqa: E402
import sysid  # noqa: E402
import sysid_tests as st  # noqa: E402

clock = sysid.clock

# What the rail tests ran, so the IMU is as it was when it was measured. Asked without
# waiting for an answer, since the answer about gravity went missing on the robot at
# every start on 2026-11-05, and cost half a second each time while the report it was
# about came through, at 92 Hz. Whether it worked is whether the readings come.
IMU_REPORTS = {"gravity": 100.0, "gyro": 400.0}
# Asked off for the run, before the two above, and back on at IMU_DEFAULT_HZ at its end,
# as the controller leaves them: nothing in a run reads them, and the hub makes fewer of
# the others while it makes them. The rail tests ran with accel off. One boot on
# 2026-11-04 gave gravity at 31 Hz with game on and 60-65 Hz with it off, and since
# 2026-11-05 every run has left both on, with gravity at 31-71 Hz on most boots, 97-99 on
# the best. On 2026-11-07 such a boot gave gravity at 45 Hz and the gyro 12-20 ms later
# than on a good one, and D7 swung the robot into a wall on it.
IMU_OFF_IN_RUN = ("accel", "game")
IMU_ASK_GAP_S = 0.02
# The gyro has reached what was asked of it, well enough to stop looking. As the
# controller leaves it, it is at IMU_DEFAULT_HZ.
IMU_SETTLED_GYRO_HZ = 200.0
IMU_LOOKS = 4
# As the controller leaves them when it finds the IMU.
IMU_DEFAULT_HZ = 100.0
# The rail saw gravity at 25 to 60 Hz when it asked for 100, and the gyro at 250 to
# 490. Below these it is not the IMU the policy was shown to stand up with.
# Gravity's floor raised from 15 to 40 Hz on 2026-11-07: the robot's boots give it at
# 76-80 Hz, and a bad one at 16-20 (36 seen once), which only a power-cycle clears.
# policy_loop.Attitude holds the last gravity report, so at 18 Hz the angle the policy
# reads is up to about 60 ms old: that boot's runs rocked at 2 Hz, and in MuJoCo D7
# standing at 207 mm sways at 0.40 rad/s rms at 18 Hz against 0.14 at 30.
IMU_LEAST_HZ = {"gyro": 100.0, "gravity": 40.0}

EASE_S = 3.0
EASE_KP, EASE_KD = 6.0, 0.3
FIRM_S = 1.0
LETDOWN_S = 2.0
# The same in the air, where a leg holds up only a shin and a wheel and somebody is
# holding up the robot, waiting. The knees' 0.6 rad at most, in a second, peaks at 1.1
# rad/s against the 15 a leg is allowed.
AIR_EASE_S = 1.0
AIR_FIRM_S = 0.25

# What there is no running without. Anything else in the robot's health is for its
# LEDs to show, and not for keeping a press from being answered: no battery reading, say.
CANNOT_RUN = {"imu missing", "imu silent", "bus off", "link down"}
# A look that finds something wrong gets this many more before it counts: a request can
# go missing, and readings can stop for a moment, in the traffic of a robot being handled.
READY_LOOKS = 3
READY_AGAIN_S = 0.2

# How near the start training was, loosened a little: it starts within 3 degrees
# and exactly in the crouch. A robot further off than this is not being started.
START_TILT_DEG = 10.0
START_LEGS_RAD = 0.2
LOWEST_VOLTS = 21.6

# The cut-off, but for a robot armed for good and driving, which goes on to
# policy_loop.FALLEN_DEG. POLICY_INTERFACE.md's 20 degrees is too near: in MuJoCo this
# policy rests about 8 degrees nose-up, and a 0.3 m/s shove takes it to 16.
# Training only gave up at 60, and the strings catch it anyway.
TILT_DEG = 30.0
# Driving, the controller stopping the motors for these is put right, and it drives on:
# the Pi silent past its deadman, and the controller restarted. A stop asked for, which
# is a tap of the button or the console's, and the power button, are obeyed.
RESTART_AFTER = {"silent", "starting"}
# Driving, a step that raises something unforeseen is skipped, for at most this long.
FAILING_S = 0.5

# Waiting for the floor, in the crouch. A lower bend makes the weight show more, and
# handling show as much more, and the policy starts far harder from it: 0.55 Nm on
# the wheels in MuJoCo where the crouch needs 0.25. The readings it learns from are the
# second half of this: on the robot on 2026-11-05 the knees were within 0.004 Nm of
# where they stayed from 0.1 s after firming, against 0.18 for the weight to count.
SETTLE_S = 0.4
TOUCH_WAIT_S = 120.0
# What launch.json is made of, by touch_numbers. A knee feels half the robot, 0.27 Nm
# in MuJoCo, and it stood from 0.3 of that to 0.75. Early is what does harm: a hand
# still carrying most of it leaves the wheels little grip, and they spin up.
TOUCH_SHARE = 0.55
# Over what handling alone made both knees feel.
TOUCH_MARGIN = 1.5
# A jolt could leave a knee's reading 0.04 away on the rail, held by friction.
TOUCH_LEAST_NM = 0.08
# Past this share of the weight there is too little left to act on.
TOUCH_MOST_SHARE = 0.8
# This little and the weight never got as far as the knees.
FULL_LEAST_NM = 0.12
STOOD_LEAST_S = 3.0
# A half-second's median, for what stays rather than what passes.
SMOOTH_STEPS = 50
# Back to waiting, once picked up: the legs home at the policy's gains, the wheels slowed
# by damping alone, 0.6 Nm at most at the 30 rad/s they might be doing.
LIFTED_S = 0.5
WHEEL_BRAKE_KD = 0.02
# Fallen over and let go of, this long upright with its legs hanging and still means
# somebody is holding it up.
PICKED_UP_S = 0.5
HANGING_STILL_RAD_S = 1.0

LAUNCH_FILE = HERE / "launch.json"
LOG_ALL_S = 300.0
# Each time it takes over it gets LOG_ALL_S more, up to this much in all: about 500 MB.
LOG_MOST_S = 1800.0
# Past those, the readings of the last few seconds are still kept in memory, and
# written out ahead of anything that happens -- a fall, a lift, a recovery -- so a
# fall at any hour comes with what led up to it.
LOG_RING_S = 5.0

# Past the policy's own resting lean, so that its answer is a clear one.
DRY_TIP_DEG = 12.0
DRY_SPIN_RAD_S = 3.0
DRY_WAIT_S = 45.0


class QueuedWriter:
    """sysid_tests' LogWriter on a thread of its own: a slow SD card, or the
    time to format a record, must never hold up a policy step. After LOG_ALL_S it
    keeps only what happened, not every reading: at over 1 GB an hour, a run with no
    end would otherwise fill the card. The last LOG_RING_S of readings are held all
    the same, and go into the log just ahead of whatever happens next."""

    READINGS = {"f", "c", "i", "p", "s"}

    def __init__(self, path: Path, header: dict, ring_s: float = LOG_RING_S):
        self.inner = st.LogWriter(path, header)
        self.all_until = clock() + LOG_ALL_S
        self.all_left = LOG_MOST_S - LOG_ALL_S
        self.ring_s = ring_s
        self.ring: deque = deque()  # (when, reading) past all_until
        self.lock = threading.Lock()
        self.queue: deque = deque()
        self.running = True
        self.thread = threading.Thread(target=self._drain, daemon=True)
        self.thread.start()

    def write(self, record: dict) -> None:
        now = clock()
        with self.lock:
            if record.get("k") in self.READINGS:
                if now > self.all_until:
                    self.ring.append((now, record))
                    while self.ring and self.ring[0][0] < now - self.ring_s:
                        self.ring.popleft()
                    return
            elif self.ring:
                self.queue.extend(r for _, r in self.ring)
                self.ring.clear()
            self.queue.append(record)

    def more(self) -> None:
        """It is about to do something worth keeping every reading of."""
        grant = min(LOG_ALL_S, self.all_left)
        self.all_left -= grant
        self.all_until = max(self.all_until, clock() + grant)

    def _drain(self) -> None:
        while self.running or self.queue:
            while self.queue:
                self.inner.write(self.queue.popleft())
            time.sleep(0.05)

    @property
    def lines(self) -> int:
        return self.inner.lines

    def close(self, footer: dict) -> None:
        self.running = False
        self.thread.join(5.0)
        self.inner.close(footer)


class Operator:
    """What somebody asks for. POLICY_INTERFACE.md's rule: not live, or nothing
    for 200 ms, is a speed and a turn of zero, keeping the last height. The controller
    sends its figures out of the policy's whole range, so a trigger's full pull means
    --max-speed, and a stick's end --max-turn. What is asked moves towards that at a
    limited rate, stopping included, because it is a change of command that sets the
    robot swinging, not the speed (docs/SYSID.md): in MuJoCo at 0.5 m/s a sudden one
    leans it to 17 degrees, and this to 14.

    The controller's select button toggles between two pairs of limits: --max-speed and
    --max-turn, which it starts with each time it takes over, and --fast-speed and
    --fast-turn, by default the whole of what the policy was trained on. A press counts
    only while it is running: one from before it took over changes nothing.

    The ride height starts each take-over at the crouch's, whatever is asked, stays
    there HEIGHT_HOLD_S, and then goes to what is asked, the controller's or --height,
    no faster than the D-pad moves it."""

    FRESH_S = 0.2
    SPEED_RAMP_M_S2 = 0.6
    TURN_RAMP_RAD_S2 = 3.0
    # Slowing, the command falls as fast as training moved it, the operator having let
    # go to stop. In MuJoCo from 1 m/s it stopped in 0.84 s over 0.57 m, against 1.77 s
    # and 0.98 m at 0.6, leaning 6 degrees back where it had 3. Faster still gained
    # nothing: at 2.5 it stopped in 0.81 s, the policy's own braking the limit.
    STOP_RAMP_M_S2 = 1.5
    TURN_STOP_RAD_S2 = 8.0
    # Speed times turn, the sideways acceleration of a turn. It fell over sideways twice
    # on 2026-11-06 turning hard at speed, in fast mode, where the diamond allows 6.75
    # m/s2. The logs had it through 5 rolling 4 degrees, three or four times what MuJoCo
    # rolls, which no turn there tips: its legs do not flex sideways and the robot's
    # do. So the turn gives way past this, the speed kept; on the spot it is untouched.
    # It was 4.0 until D8 fell at that on 2026-11-07, below: the inner knee's load
    # had gone at 2-2.5 m/s2 measured, twice in that run, so 2.5 now.
    SIDEWAYS_M_S2 = 2.5
    # And the speed asked times how fast the body really turns, the gyro about gravity,
    # which the cap above cannot see. D8 fell over outwards on 2026-11-07 at 21:08 with
    # the cap above, then 4.0, exactly met, 1.29 m/s and 3.1 rad/s asked. From 0.4 s
    # into the turn the inner (right) knee carried nothing, the outer all of it, for
    # 1.2 s: it was turning on its outer wheel, at up to 4.9 rad/s where its wheels
    # made 4.0, and still at 4 when the turn asked came back to nought. The speed it
    # had shed in the turn then came back as 1.1 m/s straight ahead while it spun,
    # about 4 m/s2 sideways, and it rolled over in half a second. The inner knee had
    # first let go at 2.0-2.5 m/s2 of wheel speed times gyro, in a left turn a second
    # before as well; MuJoCo's rigid legs hold to 4.6. So while the body spins the
    # speed asked comes down at the braking rate and does not climb back until it stops.
    SPINNING_M_S2 = 2.0
    # The height asked from the first step was the D-pad's 155 mm, kept from the run
    # before, at three take-overs on 2026-11-06 at 19:41-19:43: D5 folded its knees
    # 0.85 rad in 0.15 s under a hand still on the torso, its wheels came off the floor
    # and spun to 55 rad/s, and the lift rule stopped it each time. MuJoCo did the same
    # with a hand letting go over a second and the torso 6 degrees nose-down, and stood
    # this way, the crouch's height held and then the D-pad's rate, gamepad.py's
    # HEIGHT_RATE_M_S (launch_check.py's case 18).
    HEIGHT_HOLD_S = 1.5
    HEIGHT_RATE_M_S = 0.025

    def __init__(self, robot, meta: dict, args):
        self.lo, self.hi = meta["height_range"]
        self.start_height = min(max(meta["default_height"], self.lo), self.hi)
        self.height = self.start_height
        asked = self.start_height if args.height is None else args.height
        self.asked_height = min(max(asked, self.lo), self.hi)
        self.took_over: float | None = None
        self.top_speed = max(map(abs, meta["speed_range"]))
        self.top_turn = max(map(abs, meta["turn_range"]))
        self.envelope = bool(meta.get("envelope", False))
        # A policy goes on answering past what it was trained on, for a while: the one
        # trained to 0.5 m/s and 1.5 rad/s stays up at 1 m/s and 3 rad/s in both simulators.
        beyond = getattr(args, "past_trained", False)

        def within(asked, top):
            return asked if beyond else min(asked, top)

        self.slow = (
            within(args.max_speed, self.top_speed),
            within(args.max_turn, self.top_turn),
        )
        fast_speed = getattr(args, "fast_speed", None) or self.top_speed
        fast_turn = getattr(args, "fast_turn", None) or self.top_turn
        self.quick = (
            within(fast_speed, self.top_speed),
            within(fast_turn, self.top_turn),
        )
        self.sideways = getattr(args, "max_sideways", None) or self.SIDEWAYS_M_S2
        self.robot = robot
        self.fast = False
        self.told_at = -1.0
        self.presses: int | None = None
        self.max_speed, self.max_turn = self.slow
        # The jump button, counted as select is: presses since taking over, for the
        # loop to take; and a cap on the speed asked for while a jump is under way.
        self.jumps: int | None = None
        self.jump_presses = 0
        self.speed_cap: float | None = None
        self.last: tuple[float, dict] | None = None
        self.speed = self.turn = 0.0
        self.stepped: float | None = None
        if args.drive:
            robot.on("drive", self._heard)

    def _heard(self, m: dict) -> None:
        self.last = (clock(), m)

    def ask(self, now: float, spin: float = 0.0) -> tuple[float, float, float]:
        """spin: how fast the body is turning about the vertical, rad/s."""
        speed, turn = self.wanted(now)
        if self.speed_cap is not None:
            # Under the cap at the braking rate, being a fall towards nought.
            speed = min(max(speed, -self.speed_cap), self.speed_cap)
        if abs(spin * speed) > self.SPINNING_M_S2:
            # Before the ramp, so the speed falls at the braking rate as well.
            speed = math.copysign(self.SPINNING_M_S2 / abs(spin), speed)
        dt = 0.0 if self.stepped is None else now - self.stepped
        self.stepped = now
        self.speed = self.ramp(
            self.speed, speed, self.SPEED_RAMP_M_S2, self.STOP_RAMP_M_S2, dt
        )
        self.turn = self.ramp(
            self.turn, turn, self.TURN_RAMP_RAD_S2, self.TURN_STOP_RAD_S2, dt
        )
        # On what it is doing, after the ramps, so a turn while still rolling counts.
        if abs(self.speed * self.turn) > self.sideways:
            self.turn = math.copysign(self.sideways / abs(self.speed), self.turn)
        if self.took_over is None:
            self.took_over = now
        if now - self.took_over >= self.HEIGHT_HOLD_S:
            step = self.HEIGHT_RATE_M_S * dt
            self.height += min(max(self.asked_height - self.height, -step), step)
        return self.speed, self.turn, self.height

    @staticmethod
    def ramp(now: float, want: float, rise: float, fall: float, dt: float) -> float:
        """Towards what is wanted, at `fall` while it heads for nought, `rise` away."""
        if want * now < 0.0 or abs(want) < abs(now):
            target = 0.0 if want * now < 0.0 else want
            step = fall * dt
            now += min(max(target - now, -step), step)
            if now != 0.0 or target == want:
                return now
        step = rise * dt
        return now + min(max(want - now, -step), step)

    def reset(self) -> None:
        """Taking over: from a standstill, slow, and at the crouch's height."""
        self.speed = self.turn = 0.0
        self.stepped = None
        self.height = self.start_height
        self.took_over = None
        self.set_fast(False)
        self.presses = None if self.last is None else self.last[1].get("mode")
        self.jumps = None if self.last is None else self.last[1].get("jump")
        self.jump_presses = 0
        self.speed_cap = None

    def take_jumps(self) -> int:
        """The jump button's presses since this was last asked."""
        n, self.jump_presses = self.jump_presses, 0
        return n

    def set_fast(self, fast: bool) -> None:
        if fast != self.fast:
            print(f"speed mode: {'fast' if fast else 'slow'}", flush=True)
            self.fast = fast
            self.tell(0.0, force=True)
        self.max_speed, self.max_turn = self.quick if fast else self.slow

    def tell(self, now: float, force: bool = False) -> None:
        """The LEDs add a flash to the heartbeat while it is fast. diagd forgets in
        2 s, so it is said again each second, and a run that has died says nothing."""
        if self.robot is None or not (
            force or (self.fast and now - self.told_at > 1.0)
        ):
            return
        self.told_at = now
        try:
            self.robot.send("indicate", fast=self.fast)
        except diag_client.RobotError:
            pass

    def wanted(self, now: float) -> tuple[float, float]:
        if self.last is None:
            return 0.0, 0.0
        heard, m = self.last
        if m.get("height"):
            self.asked_height = min(max(float(m["height"]), self.lo), self.hi)
        presses = m.get("mode")
        if presses is not None:
            if self.presses is not None and (int(presses) - self.presses) % 2:
                self.set_fast(not self.fast)
            self.presses = int(presses)
        jumps = m.get("jump")
        if jumps is not None:
            if self.jumps is not None:
                self.jump_presses += (int(jumps) - self.jumps) % 256
            self.jumps = int(jumps)
        self.tell(now)
        if now - heard > self.FRESH_S or not m.get("live"):
            return 0.0, 0.0
        # The controller sends the policy's whole range; this is that share of the limit.
        speed = float(m["forward"]) * self.max_speed / self.top_speed
        turn = float(m["turn"]) * self.max_turn / self.top_turn
        speed = min(max(speed, -self.max_speed), self.max_speed)
        turn = min(max(turn, -self.max_turn), self.max_turn)
        share = abs(speed) / self.top_speed + abs(turn) / self.top_turn
        if self.envelope and share > 1.0:
            speed, turn = speed / share, turn / share
        return speed, turn


# THE LEAN. The driving policy told that it leans back, by --lean-per-m-s degrees for
# each m/s it is sent, so that it leans forward to straighten up and goes faster; going
# backwards, the other way. Its speed follows what it reads as level: on the robot's 3
# degrees nose-down on 2026-11-05, D3 drove 25 per cent slow (drive_env_cfg.py's
# WheeledBipedDriveD6EnvCfg). D9 (rough-2026-11-07_17-10-09_d9), trained for 1.6 m/s,
# holds 1.24 asked for it on launch_check.py's rig, as D8 holds 1.11-1.17 asked anything
# from 1.4 to 2.2, using 0.1 Nm of the 1 Nm and more its wheels could make there and 31
# rad/s of their 55: the limit is the policy's own, and the same without the motor's
# curve. Training taught it: there an IMU tilt of up to 2 degrees and sensor offsets it
# could not see moved each robot's speed by 0.15-0.25 m/s, and the fastest ran their
# wheels into Isaac's 48.2 rad/s, so the policy keeps the rest slow.
#
# On launch_check.py's rig on 8 November 2026, fast mode's full pull at the launcher's
# 1.8 m/s (session scratchpad d9why/): D8 held 1.17 m/s with no lean, 1.32 at 1.11 per
# m/s (2 degrees at 1.8) and 1.41 at 1.67 (3 degrees; 3.25 with Trim's 0.15 on top),
# passing every case at 1.67, the jump from 1.5 m/s on jd8 included; it stopped from
# there in 1.43 s over 1.31 m, the wheels at 37 rad/s at most. D9 at 1.25 (2 degrees at
# its 1.6) held 1.43, but on jd8 its jump hands back to a fall, lean or none. With the
# wheels' torque at 0.8 of asked, the IMU 40 ms late and the pack at 23.4 V, D8 at 1.67
# held 1.52 and stopped with its wheels at 41 rad/s; at 0.7 of asked as well, the
# loop took it for lifted at 0.4 m/s every time, where without the lean it stood.
# 3 degrees is past the 2 D8 was trained on. Only the policy's input is turned: the
# tilt cut-off, the fall, the lift and the IMU's own checks read gravity as it is, and
# a jump policy is fed it as it is. NOT YET TRIED ON THE ROBOT.


def leaned(g: np.ndarray, nose_up_deg: float) -> np.ndarray:
    """Gravity's direction as a torso pitched `nose_up_deg` further nose-up reads it,
    its roll left as it is."""
    if not nose_up_deg:
        return g
    a = math.radians(nose_up_deg)
    c, s = math.cos(a), math.sin(a)
    x, y, z = (float(v) for v in g)
    return np.array([x * c + z * s, y, z * c - x * s])


class LeanedBalancer(pl.Balancer):
    """The driving policy, fed gravity turned nose-up by `lean_per_m_s` degrees for each
    m/s of the speed it is sent, after the Operator's caps and ramps and the stepper's
    governor, Trim and Hold: nothing standing, and coming and going with the speed.
    THE LEAN, above, has why. `lean_deg` is the last step's."""

    def __init__(self, net: pl.Net, wheel_limit: float | None = None, lean_per_m_s=0.0):
        super().__init__(net, wheel_limit)
        self.lean_per_m_s = float(lean_per_m_s)
        self.lean_deg = 0.0

    def observe(self, fb: dict, w, g, speed: float, turn: float, height: float):
        self.lean_deg = self.lean_per_m_s * speed
        g = leaned(np.asarray(g, dtype=float), self.lean_deg)
        return super().observe(fb, w, g, speed, turn, height)


def real_time(args) -> str:
    """This thread ahead of everything else on the Pi, if allowed."""
    if not args.rt:
        return "normal priority"
    tid = threading.get_native_id()
    done = subprocess.run(
        ["sudo", "-n", "chrt", "-f", "-p", "50", str(tid)],
        capture_output=True,
        text=True,
    )
    return (
        "real-time priority"
        if done.returncode == 0
        else "normal priority (chrt refused)"
    )


# ---- getting ready ---------------------------------------------------------------


def connect(args):
    streams = ["status", "log", "can", "imu"]
    if args.drive:
        streams.append("drive")
    try:
        robot = sysid.LoggingRobot(args.robot, name="balance", streams=tuple(streams))
    except diag_client.RobotError as error:
        raise SystemExit(str(error))
    try:
        robot.take_control(force=getattr(args, "button", False))
    except diag_client.RobotError as error:
        robot.close()
        raise SystemExit(
            f"cannot take control: {error}. Close the motor console's tab, or whatever "
            "else holds it, and try again."
        )
    return robot


def imu_rates(rig, seconds: float = 0.25) -> dict[str, float]:
    """How often each report the policy needs is actually arriving."""
    last = {r: rig.imu.get(r, (None,))[0] for r in IMU_REPORTS}
    seen = dict.fromkeys(IMU_REPORTS, 0)
    end = clock() + seconds
    while clock() < end:
        for r in IMU_REPORTS:
            heard = rig.imu.get(r, (None,))[0]
            if heard != last[r]:
                seen[r] += 1
                last[r] = heard
        time.sleep(0.0005)
    return {r: n / seconds for r, n in seen.items()}


def ask_imu(robot, hz_of) -> None:
    for report, hz in hz_of.items():
        try:
            robot.send("imu.enable", report=report, hz=hz)
        except diag_client.RobotError:
            pass
        time.sleep(IMU_ASK_GAP_S)


def get_ready(rig, robot, powered: bool) -> dict:
    """Refuses, in plain words, a robot that should not be started, and only that, having
    looked more than once."""
    for left in range(READY_LOOKS - 1, -1, -1):
        try:
            return looks_ready(rig, robot, powered)
        except (SystemExit, diag_client.RobotError) as why:
            if not left:
                raise SystemExit(str(why)) from None
            print(f"  not ready yet: {why}")
            time.sleep(READY_AGAIN_S)
    raise AssertionError


def looks_ready(rig, robot, powered: bool) -> dict:
    rig.find()
    regs = rig.registers()
    for joint, r in regs.items():
        if float(r.get("VMAX", 0.0)) < 55.0:
            raise SystemExit(f"{joint}: VMAX is {r.get('VMAX')}, and has to be 55")
        if powered and not float(r.get("TIMEOUT", 0.0)):
            raise SystemExit(f"{joint}: no communication time-out set (docs/SYSID.md)")
    status = diag_client.wait_for_status(robot)
    conditions = (status.get("health") or {}).get("conditions", [])
    serious = [c for c in conditions if c in CANNOT_RUN]
    if serious:
        raise SystemExit(
            f"the robot reports a fault: {', '.join(serious)}. "
            "If it is the IMU, power-cycle the robot."
        )
    if conditions:
        print(f"  carrying on past: {', '.join(conditions)}")
    volts = status.get("vbus")
    if powered and volts is not None and volts < LOWEST_VOLTS:
        raise SystemExit(f"the battery is at {volts:.1f} V: charge it first")
    # Whether the IMU is alive is whether its readings come. Its answer to a
    # request can go missing under the traffic of a healthy one, as it did on the
    # robot on 2026-11-04 with 300 packets a second arriving: sysid.py carries on
    # past that too.
    ask_imu(robot, {**dict.fromkeys(IMU_OFF_IN_RUN, 0.0), **IMU_REPORTS})
    for _ in range(IMU_LOOKS):
        rates = imu_rates(rig)
        if rates["gyro"] >= IMU_SETTLED_GYRO_HZ and rates["gravity"] > 0:
            break
    for report, least in IMU_LEAST_HZ.items():
        if rates[report] < least:
            raise SystemExit(
                f"the IMU's {report} report is arriving at {rates[report]:.0f} Hz, where it "
                f"needs at least {least:g}: power-cycle the robot."
            )
    print("  IMU: " + ", ".join(f"{r} {hz:.0f} Hz" for r, hz in rates.items()))
    size = float(np.linalg.norm(rig.imu["gravity"][1]))
    if not 9.0 < size < 10.6:
        raise SystemExit(
            f"the IMU's gravity reads {size:.2f} m/s2, and should read 9.81"
        )
    if not rig.wait_fresh(st.JOINTS):
        raise SystemExit("not every motor answered a status request")
    return regs


# ---- what it says as it goes -----------------------------------------------------


class View:
    """What the loop last saw, for a slower thread to print: a terminal that
    stalls must not stall the loop."""

    def __init__(self):
        self.phase = "starting"
        self.step: dict | None = None
        self.running = True
        self.note = ""

    def line(self) -> str:
        s = self.step
        if s is None:
            return f"{self.phase}: waiting for the first reading"
        g, fb = s["g"], s["fb"]
        legs = " ".join(f"{fb[j].p:+.2f}" for j in st.LEGS)
        wheels = " ".join(f"{fb[j].v:+5.1f}" for j in st.WHEELS)
        want = " ".join(f"{s['want'][k]:+.2f}" for k in range(2))
        text = (
            f"{self.phase:<7} pitch {math.degrees(pl.nose_down(g)):+5.1f} "
            f"roll {math.degrees(pl.right_down(g)):+5.1f} | legs {legs} | "
            f"wheels {wheels} rad/s, policy wants {want} Nm"
        )
        if abs(s["speed"]) + abs(s["turn"]) > 0:
            text += f" | asked {s['speed']:+.2f} m/s {s['turn']:+.2f} rad/s"
        return text + (f" | {self.note}" if self.note else "")


def printer(view: View) -> None:
    while view.running:
        print(view.line(), flush=True)
        time.sleep(0.5)


def settle_process(args) -> str:
    sys.setswitchinterval(0.0005)
    gc.collect()
    gc.freeze()
    gc.set_threshold(50000, 50, 50)
    return real_time(args)


# ---- motors off ------------------------------------------------------------------


def dry(rig, stepper, bal, view: View, stop, args) -> list[tuple[str, str]]:
    """Each check waits for its move and passes or fails by itself. The legs hang
    or rest anywhere with the motors off, so the policy is told they are in the
    crouch: this is the IMU's axes and the wheels' signs, and only those."""
    crouch = dict(zip(st.LEGS, bal.crouch, strict=True))

    def as_if_crouched(fb: dict) -> dict:
        out = dict(fb)
        for j, p in crouch.items():
            out[j] = st.Fb(fb[j].at, float(p), 0.0, 0.0)
        return out

    stepper.send_commands = False
    stepper.pretend = as_if_crouched
    height = bal.meta["default_height"]
    checks = [
        ("Tip the torso NOSE-DOWN about 15 degrees and hold it there", "nose"),
        ("Tip the torso NOSE-UP about 15 degrees and hold it there", "tail"),
        ("Tip the torso RIGHT side down about 15 degrees", "right"),
        (
            "Level it again, then spin the RIGHT wheel FORWARD by hand",
            "wheel_drive_right",
        ),
        ("Spin the LEFT wheel FORWARD by hand", "wheel_drive_left"),
    ]
    results = []
    t0 = clock()
    gyro_says = 0.0
    last_pitch = None
    for words, what in checks:
        print(f"\n>>> {words}", flush=True)
        view.note = ""
        started = clock()
        wanted = deque(maxlen=30)
        seen = None
        while clock() - started < args.wait and seen is None:
            if stop.is_set():
                raise st.Abort("stopped")
            step = stepper.step(t0, 0.0, 0.0, height)
            step["want"] = bal.last_wheels
            view.step = step
            t0 += pl.PERIOD_S
            if clock() - t0 > 5 * pl.PERIOD_S:
                t0 = clock()
            pitch = pl.nose_down(step["g"])
            roll = pl.right_down(step["g"])
            if last_pitch is not None:
                gyro_says += (pitch - last_pitch) * float(step["w"][1])
            last_pitch = pitch
            limit = math.radians(DRY_TIP_DEG)
            wanted.append(bal.last_wheels)
            held = len(wanted) == wanted.maxlen
            if what == "nose" and pitch > limit and held:
                seen = (pitch, sum(a + b for a, b in wanted))
            elif what == "tail" and pitch < -limit and held:
                seen = (pitch, sum(a + b for a, b in wanted))
            elif what == "right" and roll > limit:
                seen = (roll, 0.0)
            elif what in st.WHEELS and abs(step["fb"][what].v) > DRY_SPIN_RAD_S:
                seen = (step["fb"][what].v, 0.0)
        if seen is None:
            results.append((words, "NOT SEEN: nothing like that happened in time"))
        elif what == "nose":
            good = seen[1] > 0
            results.append(
                (
                    words,
                    f"read {math.degrees(seen[0]):+.0f} deg; the policy drives its wheels "
                    + ("forward, as it should" if good else "BACKWARD: WRONG"),
                )
            )
        elif what == "tail":
            good = seen[1] < 0
            results.append(
                (
                    words,
                    f"read {math.degrees(seen[0]):+.0f} deg; the policy drives its wheels "
                    + ("backward, as it should" if good else "FORWARD: WRONG"),
                )
            )
        elif what == "right":
            results.append(
                (words, f"read {math.degrees(seen[0]):+.0f} deg right side down: right")
            )
        else:
            good = seen[0] > 0
            results.append(
                (
                    words,
                    f"read {seen[0]:+.1f} rad/s: "
                    + ("forward, right" if good else "BACKWARD: WRONG"),
                )
            )
        print(f"    {results[-1][1]}", flush=True)
    if abs(gyro_says) < 0.01:
        results.append(("gyro against gravity", "NOT SEEN: it never turned"))
    else:
        results.append(
            ("gyro against gravity", "agree" if gyro_says > 0 else "DISAGREE: WRONG")
        )
    return results


# ---- motors on -------------------------------------------------------------------


def soften(fb: dict, kp: float, span: float = LETDOWN_S) -> dict:
    """Stiffness to nothing from wherever the legs are, damping kept, so they sink."""

    def one(p: float):
        return lambda t, _: st.Cmd(p=p, kp=kp * (1.0 - min(t / span, 1.0)), kd=0.3)

    return {j: one(fb[j].p) for j in st.LEGS}


def powered(rig, stepper, bal, op, view: View, args, go, stop, touch=None) -> str:
    """Ease, firm up, hold, the policy if there is to be one, and let down. With a
    `touch`, the holding is done in the air, until the floor comes up to meet it."""
    meta = bal.meta
    crouch = dict(zip(st.LEGS, meta["crouch"], strict=True))
    wheels_off = {j: st.Cmd() for j in st.WHEELS}
    holding = {j: st.Cmd(p=p, kp=bal.kp, kd=bal.kd) for j, p in crouch.items()}
    holding |= wheels_off
    brakes = {j: st.Cmd(kd=WHEEL_BRAKE_KD) for j in st.WHEELS}
    limp = {j: st.Cmd() for j in st.JOINTS}
    ease_s, firm_s = (EASE_S, FIRM_S) if touch is None else (AIR_EASE_S, AIR_FIRM_S)
    # Waits to be stood up for as long as it runs. Only a launch can, knowing the floor.
    rearm = touch is not None and getattr(args, "rearm", False)
    woken = getattr(args, "woken", None)
    phase_file = getattr(args, "phase_file", None)

    def easing():
        return {j: st.ease(j, crouch[j], ease_s, EASE_KP, EASE_KD) for j in st.LEGS}

    ease = easing()
    back = {}
    # A stop from before the motors come on has nothing to do with this run: taking control
    # from a console's tab makes one. On 2026-11-05 one ended a run as it began, and the
    # press that started it looked as if it had done nothing.
    rig.stopped_by = None
    rig.enable(st.JOINTS)
    phase, began = "ease", clock()
    t0 = clock()
    letdown = None
    ending = "done"
    hanging_since = None

    def to(name: str, now: float):
        nonlocal phase, began
        phase, began = name, now
        view.phase = name
        stepper.guard.free = rearm and name != "policy"
        stepper.guard.recover = rearm and name == "policy"
        rig.writer.write({"k": "n", "h": round(now, 6), "seg": name})
        if woken is not None:
            woken.clear()
        if phase_file is not None:
            try:
                phase_file.write_text(name)
            except OSError:
                pass

    # Whatever the pose: somebody has just asked for it, and limp legs can stay where they
    # were left, 73 degrees the wrong way on 2026-11-05, which lifting it did not change.
    # That run lay limp for 170 s after its tap, until a hand had moved them.
    to("ease", began)

    def let_down(now: float, why: str = "done"):
        nonlocal letdown, ending
        ending = why
        letdown = soften(rig.latest, bal.kp)
        to("letdown", now)
        return {j: f(0.0, rig.latest) for j, f in letdown.items()} | wheels_off

    jumper = bal if isinstance(bal, pl.TwoPolicies) else None
    failing_since = None
    while True:
        now = clock()
        t = now - began
        if rig.stopped_by:
            why = getattr(rig, "stopped_why", None)
            if not (stepper.guard.recover and why in RESTART_AFTER):
                raise st.Abort(rig.stopped_by)
            # The motors are stopped and it is falling: on again, at once.
            rig.writer.write(
                {"k": "n", "h": round(now, 6), "recovering": rig.stopped_by}
            )
            rig.stopped_by = rig.stopped_why = None
            rig.enable(st.JOINTS)
        speed, turn, height = 0.0, 0.0, op.height
        if phase == "limp":
            cmds = limp
            g = view.step["g"] if view.step else None
            if woken is not None and woken.is_set():
                hanging_since = None
                ease = easing()
                to("ease", now)
                g = None
            hangs = (
                g is not None
                and math.degrees(pl.tilt(g)) < pl.TOUCH_TILT_DEG
                and all(
                    low <= rig.latest[j].p <= high
                    and abs(rig.latest[j].v) < HANGING_STILL_RAD_S
                    for j, (low, high) in st.WINDOWS.items()
                )
            )
            if not hangs:
                hanging_since = None
            elif hanging_since is None:
                hanging_since = now
            elif now - hanging_since >= PICKED_UP_S:
                hanging_since = None
                ease = easing()
                to("ease", now)
        elif phase == "lifted":
            cmds = {j: f(t, rig.latest) for j, f in back.items()} | brakes
            if t >= LIFTED_S:
                to("settle", now)
        elif phase == "ease":
            cmds = {j: f(t, rig.latest) for j, f in ease.items()} | wheels_off
            if t >= ease_s:
                to("firm", now)
        elif phase == "firm":
            s = min(t / firm_s, 1.0)
            kp = EASE_KP + (bal.kp - EASE_KP) * s
            kd = EASE_KD + (bal.kd - EASE_KD) * s
            cmds = {
                j: st.Cmd(p=p, kp=kp, kd=kd) for j, p in crouch.items()
            } | wheels_off
            if t >= firm_s:
                to("hold" if touch is None else "settle", now)
        elif phase == "hold":
            cmds = holding
            if args.mode == "hold":
                if t >= args.seconds or stop.is_set():
                    cmds = let_down(now)
            elif stop.is_set():
                return "stopped before starting"
            elif go.is_set():
                why = not_ready(view.step, crouch)
                if why:
                    go.clear()
                    view.note = f"not starting: {why}"
                else:
                    view.note = ""
                    bal.reset()
                    if stepper.hold is not None:
                        stepper.hold.holding = False
                    to("policy", now)
                    cmds = None
        elif phase == "settle":
            cmds = holding
            if t >= SETTLE_S / 2:
                touch.learn(rig.latest)
            if t >= SETTLE_S:
                before = touch.air
                why = touch.learned()
                if why and rearm and (before or touch.usual):
                    # Already on the floor, or put down before it could tell: the knees
                    # read 0.1 to 0.3 Nm low within 2 s of a tap on 2026-11-05, and it then
                    # went limp each time. What they read in the air last time will do.
                    touch.air = before or touch.usual
                    why = None
                rig.writer.write(
                    {"k": "n", "h": round(now, 6), "air": touch.air, "each": touch.each}
                )
                if why:
                    cmds = let_down(now, f"not started: {why}")
                else:
                    view.note = ""
                    to("air", now)
        elif phase == "air":
            cmds = holding
            fb = view.step["fb"] if view.step else rig.latest
            pulls = touch.pulls(fb)
            view.note = f"knees feel {pulls[0]:+.2f} {pulls[1]:+.2f} Nm"
            if args.mode == "lower":
                touch.samples.append((now, *pulls))
                left = args.seconds - t
                view.note += f", {left:.0f} s to go"
                if left <= 0 or stop.is_set():
                    cmds = let_down(now)
            elif stop.is_set():
                cmds = let_down(now, "stopped before starting")
            elif args.touch_wait and t >= args.touch_wait:
                cmds = let_down(now, f"nothing touched in {args.touch_wait:g} s")
            elif view.step and touch.felt(now, fb, view.step["g"]):
                view.note = ""
                rig.writer.write(
                    {
                        "k": "n",
                        "h": round(now, 6),
                        "touched": [round(x, 3) for x in pulls],
                    }
                )
                bal.reset()
                op.reset()
                if stepper.hold is not None:
                    stepper.hold.holding = False
                if hasattr(rig.writer, "more"):
                    rig.writer.more()
                to("policy", now)
                cmds = None
        elif phase == "policy":
            cmds = None
            if jumper is not None:
                op.speed_cap = jumper.speed_cap
            last = view.step
            yawing = 0.0 if last is None else abs(float(np.dot(last["w"], last["g"])))
            speed, turn, height = op.ask(now, yawing)
            if op.fast != getattr(op, "logged_fast", False):
                # Into the log as well as the launcher's: a jerk at the switch was
                # reported on 2026-11-07, and nothing in the run's log marked when.
                op.logged_fast = op.fast
                rig.writer.write(
                    {
                        "k": "n",
                        "h": round(now, 6),
                        "speed mode": "fast" if op.fast else "slow",
                    }
                )
            if jumper is not None:
                jump_presses(jumper, op, rig, view, touch, now)
            busy = jumper is not None and jumper.busy
            if touch is not None and busy:
                # Its own take-off and landing are not somebody picking it up.
                touch.light_since = None
                touch.wheels.reset()
            if touch is not None and not busy:
                spin = max(abs(rig.latest[j].v) for j in st.WHEELS)
                last = view.step
                free = last is not None and touch.wheels.update(
                    last["fb"], float(last["w"][1]), last["t"]
                )
                if touch.lifted(now, rig.latest, spin, t) or free:
                    words = f"it is off the floor, the wheels at {spin:.0f} rad/s"
                    if not rearm:
                        raise st.Abort(words)
                    rig.writer.write({"k": "n", "h": round(now, 6), "lifted": words})
                    back = {
                        j: st.ease(j, crouch[j], LIFTED_S, bal.kp, bal.kd)
                        for j in st.LEGS
                    }
                    to("lifted", now)
                    t = 0.0
                    cmds = {j: f(t, rig.latest) for j, f in back.items()} | brakes
            if stop.is_set():
                raise st.Abort("Enter pressed")
            if args.seconds and t >= args.seconds:
                cmds = let_down(now)
        elif phase == "letdown":
            cmds = {j: f(t, rig.latest) for j, f in letdown.items()} | wheels_off
            if t >= LETDOWN_S:
                if not rearm:
                    return ending
                to("limp", now)
        try:
            step = stepper.step(t0, speed, turn, height, override=cmds)
            failing_since = None
        except pl.Lost as why:
            if not rearm:
                raise
            # Not lying down, but unable to balance: down gently, rather than dropped.
            rig.writer.write({"k": "n", "h": round(now, 6), "lost": str(why)})
            view.note = str(why)
            let_down(now, str(why))
            t0 += pl.PERIOD_S
            continue
        except pl.Tipped as why:
            if not rearm:
                raise
            # It has fallen. The commands to let go of everything are the next step's.
            rig.writer.write({"k": "n", "h": round(now, 6), "fell": str(why)})
            view.note = str(why)
            to("limp", now)
            t0 += pl.PERIOD_S
            continue
        except st.Abort:
            raise
        except Exception as error:  # noqa: BLE001 - driving, anything is tried again
            if not stepper.guard.recover:
                raise
            failing_since = now if failing_since is None else failing_since
            if now - failing_since > FAILING_S:
                raise
            rig.writer.write({"k": "n", "h": round(now, 6), "recovering": repr(error)})
            t0 += pl.PERIOD_S
            continue
        step["want"] = bal.last_wheels
        view.step = step
        t0 += pl.PERIOD_S
        if clock() - t0 > 5 * pl.PERIOD_S:
            t0 = clock()


def jump_presses(jumper, op, rig, view: View, touch, now: float) -> None:
    """Each press of the jump button answered, a jump or why not, and whatever the jump
    has done since, into the log: a note is what keeps the readings around it."""
    notes = []
    for _ in range(op.take_jumps()):
        step = view.step
        fb = rig.latest
        g = step["g"] if step else None
        speed = (
            pl.ground_speed(fb, float(step["w"][1]), jumper.meta["wheel_radius"])
            if step
            else 0.0
        )
        loaded = None
        if touch is not None and touch.air is not None:
            loaded = min(touch.pulls(fb)) >= pl.JUMP_KNEE_LOADED_NM
        why = jumper.press(g, speed, loaded)
        if why:
            notes.append(f"refused: {why}")
    notes += jumper.events
    jumper.events.clear()
    for words in notes:
        rig.writer.write({"k": "n", "h": round(now, 6), "jump": words})
        view.note = f"jump: {words}"


def not_ready(step: dict | None, crouch: dict) -> str | None:
    if step is None:
        return "no reading yet"
    angle = math.degrees(pl.tilt(step["g"]))
    if angle > START_TILT_DEG:
        return f"tilted {angle:.0f} degrees: hold it within {START_TILT_DEG:g}"
    for j, p in crouch.items():
        off = step["fb"][j].p - p
        if abs(off) > START_LEGS_RAD:
            return f"{j} is {off:+.2f} rad from the crouch: is something holding it?"
    return None


# ---- what a lowering showed ------------------------------------------------------


def touch_numbers(samples: list[tuple[float, float, float]]) -> dict:
    """From one lowering, watched at each policy step as (time, right, left), how much
    each knee should feel before the robot believes it. `why` says if it cannot tell."""
    a = np.asarray(samples, dtype=float)
    if len(a) < 2 * SMOOTH_STEPS:
        return {"why": "it was hardly watched at all"}
    t, pulls = a[:, 0], a[:, 1:3]
    windows = np.lib.stride_tricks.sliding_window_view(pulls, SMOOTH_STEPS, axis=0)
    smooth = np.median(windows, axis=2)
    full = smooth.max(axis=0)
    less = float(full.min())
    out = {
        "full_nm": [round(float(x), 3) for x in full],
        "watched_s": round(float(t[-1] - t[0]), 1),
    }
    if less < FULL_LEAST_NM:
        return out | {
            "why": f"the knees felt only {full[0]:.2f} and {full[1]:.2f} Nm, so its "
            "weight never reached them: was it let stand?"
        }
    dt = float(np.median(np.diff(t)))
    standing = (smooth > 0.6 * full).all(axis=1)
    out["stood_s"] = round(float(standing.sum() * dt), 1)
    if out["stood_s"] < STOOD_LEAST_S:
        return out | {"why": f"it stood for only {out['stood_s']} s"}
    # The air is what comes before the weight starts to arrive, walking back from
    # the first standing to where the knees last felt next to nothing.
    both = pulls.min(axis=1)
    first = int(np.argmax(standing))
    quiet = np.nonzero(both[: first + SMOOTH_STEPS // 2] < 0.1 * less)[0]
    if len(quiet) == 0:
        return out | {"why": "it was never clear of the floor while being watched"}
    air = both[: int(quiet[-1]) + 1]
    out["air_s"] = round(float(len(air) * dt), 1)
    confirm = max(round(pl.TOUCH_CONFIRM_S / dt), 1)
    if len(air) <= confirm:
        return out | {"why": "it was never clear of the floor while being watched"}
    # What the watch would have seen: the most both knees felt for a whole TOUCH_CONFIRM_S.
    held = np.lib.stride_tricks.sliding_window_view(air, confirm).min(axis=1)
    out["air_peak_nm"] = round(float(max(held.max(), 0.0)), 3)
    each = max(TOUCH_SHARE * less, TOUCH_MARGIN * out["air_peak_nm"], TOUCH_LEAST_NM)
    if each > TOUCH_MOST_SHARE * less:
        return out | {
            "why": f"handling alone made both knees feel {out['air_peak_nm']:.2f} Nm, too "
            f"near the {less:.2f} of standing to tell them apart"
        }
    return out | {"each_nm": round(float(each), 3)}


def report_lowering(touch, args, log_name: str) -> None:
    numbers = touch_numbers(touch.samples)
    print("\nThe lowering: " + json.dumps(numbers))
    if "why" in numbers:
        print(f"NOT USABLE: {numbers['why']}. launch.json is left as it was.")
        return
    saved = numbers | {
        "air_nm": [round(x, 3) for x in touch.air],
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "log": log_name,
    }
    args.touch_file.write_text(json.dumps(saved, indent=2) + "\n")
    print(
        f"{args.touch_file}: launch takes over when both knees feel "
        f"{numbers['each_nm']:.2f} Nm for {pl.TOUCH_CONFIRM_S * 1000:.0f} ms"
    )


def touch_setting(args) -> float | None:
    """How much a knee has to feel, measured, or as given: launch does not guess."""
    if args.mode != "launch":
        return None
    if args.touch_nm is not None:
        return args.touch_nm
    try:
        saved = json.loads(args.touch_file.read_text())
    except FileNotFoundError:
        raise SystemExit(
            f"no {args.touch_file}: run `balance.py lower` first"
        ) from None
    return float(saved["each_nm"])


def usual_air(args) -> list[float] | None:
    """What the measuring run found the knees read in the air, if it says."""
    if args.mode != "launch":
        return None
    try:
        return json.loads(args.touch_file.read_text()).get("air_nm")
    except FileNotFoundError:
        return None


def legs_problem(rig, tilt_deg: float, imu) -> str | None:
    """A robot that would be stopped on its first step is told so before the motors
    are ever enabled. It is usually one sitting on its folded legs."""
    for j, (low, high) in st.WINDOWS.items():
        p = rig.latest[j].p
        if not low <= p <= high:
            return (
                f"{j} is at {math.degrees(p):+.0f} degrees, outside "
                f"{math.degrees(low):+.0f} to {math.degrees(high):+.0f}: "
                "lift the robot so that its legs hang"
            )
    _, g = imu.torso(rig.imu["gyro"][1], rig.imu["gravity"][1])
    angle = math.degrees(pl.tilt(g))
    if angle > tilt_deg:
        return f"the torso is tilted {angle:.0f} degrees: bring it near level"
    return None


# ---- the program -----------------------------------------------------------------


def session(args) -> int:
    net = pl.Net(args.policy)
    robot_file = st.load_robot(args.robot_file) if args.robot_file else st.load_robot()
    if not robot_file["mapped"] or not robot_file.get("imu_axes"):
        raise SystemExit("no robot file: run sysid.py map and level first")
    is_powered = args.mode != "dry"
    wiring = dict(robot_file["joints"])
    robot = connect(args)
    rig = sysid.Rig(robot, wiring)
    view = View()
    reason = "not run"
    results = None
    stepper = None
    moved_motors = False
    go, stop, done = threading.Event(), threading.Event(), threading.Event()
    loop = None
    try:
        regs = get_ready(rig, robot, is_powered)
        bal = LeanedBalancer(
            net, wheel_limit=args.wheel_limit, lean_per_m_s=args.lean_per_m_s
        )
        if args.jump_policy and is_powered:
            bal = pl.TwoPolicies(
                bal,
                pl.JumpBalancer(pl.Net(args.jump_policy), wheel_limit=args.wheel_limit),
                args.jump_height,
                volts=lambda: (robot.status or {}).get("vbus"),
            )
        imu = pl.Imu(robot_file["imu_axes"], robot_file["imu_gravity_sign"])
        # With the motors off a tilt harms nothing, and is what is asked for.
        wheel_vmax = min(float(regs[j].get("VMAX", 55.0)) for j in st.WHEELS)
        guard = pl.Guard(
            args.tilt if is_powered else 180.0,
            pl.limits(legs_limp=not is_powered, wheel_vmax=wheel_vmax),
        )
        hold = (
            pl.Hold(bal.meta["wheel_radius"])
            if args.mode in ("run", "launch") and not args.no_hold
            else None
        )
        touch = None
        if args.mode in ("lower", "launch"):
            touch = pl.Touch(
                touch_setting(args), dict(zip(st.LEGS, bal.meta["crouch"], strict=True))
            )
            touch.usual = usual_air(args)
        args.rearm = args.mode == "launch" and not args.once
        args.woken = threading.Event() if args.button else None
        if args.button:
            threading.Thread(target=listen, args=(args.woken,), daemon=True).start()
        if is_powered and not args.rearm:
            problem = legs_problem(rig, args.tilt, imu)
            if problem:
                raise SystemExit(problem)
        op = Operator(robot, bal.meta, args)
        path = sysid.log_path(args, f"balance_{args.mode}")
        header = {
            "test": f"balance_{args.mode}",
            "title": "the policy on the robot",
            "fixture": "floor",
            "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "host": socket.gethostname(),
            "commit": sysid.commit(),
            "args": {k: str(v) for k, v in vars(args).items()},
            "hz": 1.0 / pl.PERIOD_S,
            "joints": {j: vars(w) for j, w in wiring.items()},
            "registers": regs,
            "controller": robot.info,
            "robot_file": robot_file.get("date"),
            "imu_axes": robot_file["imu_axes"],
            "imu_gravity_sign": robot_file["imu_gravity_sign"],
            "policy": bal.meta,
            "jump_policy": bal.jumping.meta
            if isinstance(bal, pl.TwoPolicies)
            else None,
            "label": args.label,
        }
        rig.writer = QueuedWriter(path, header)
        stepper = pl.Stepper(
            bal,
            imu,
            rig,
            guard,
            clock=clock,
            wait=sysid.pace,
            nap=lambda: time.sleep(0.0002),
            hold=hold,
            writer=rig.writer,
            trim=(
                pl.Trim(bal.meta["wheel_radius"])
                if args.drive and not args.no_trim
                else None
            ),
        )
        print(
            f"{args.mode}: {bal.meta['run']}, policy {bal.meta['digest']}, battery "
            f"{diag_client.wait_for_status(robot).get('vbus')} V, cut-off at {args.tilt:g} "
            f"degrees{'' if is_powered else '; the motors stay off'}"
            + (
                f"; the policy told it leans {args.lean_per_m_s:g} degrees per m/s"
                if args.lean_per_m_s
                else ""
            )
        )
        if is_powered and not args.yes:
            words = {
                "hold": "On slack strings, wheels on the floor, steadied by hand: the legs "
                "will move to the crouch and hold there, then relax onto the strings.",
                "run": "On slack strings, wheels on the floor: the legs will move to the crouch.",
            }.get(
                args.mode,
                "Held by the torso, clear of the floor, legs hanging: the legs will move "
                "to the crouch.",
            )
            input(f"{words}\nEnter to enable the motors, Ctrl-C to leave it. ")

        outcome = {"why": "done", "results": None}

        def worker():
            priority = settle_process(args)
            rig.writer.write({"k": "n", "h": round(clock(), 6), "priority": priority})
            try:
                if is_powered:
                    outcome["why"] = powered(
                        rig, stepper, bal, op, view, args, go, stop, touch
                    )
                else:
                    view.phase = "dry"
                    outcome["results"] = dry(rig, stepper, bal, view, stop, args)
            except st.Abort as why:
                rig.stop()
                outcome["why"] = f"stopped: {why}"
                rig.writer.write({"k": "x", "h": round(clock(), 6), "why": str(why)})
            except Exception as error:  # anything at all stops the motors
                rig.stop()
                outcome["why"] = f"stopped: {error!r}"
                rig.writer.write({"k": "x", "h": round(clock(), 6), "why": repr(error)})
                raise
            finally:
                done.set()

        moved_motors = is_powered
        if not is_powered:
            # A motor its time-out dropped says fault until told otherwise,
            # which enabling does when there is enabling to do.
            for j in st.JOINTS:
                rig.buses[rig.wiring[j].bus].clear_error(rig.motors[j])
            rig.wait_fresh(st.JOINTS)
        talker = threading.Thread(target=printer, args=(view,), daemon=True)
        loop = threading.Thread(target=worker, daemon=True)
        talker.start()
        loop.start()
        operate(args, go, stop, done, view)
        loop.join(5.0)
        reason = outcome["why"]
        results = outcome["results"]
        view.running = False
    except KeyboardInterrupt:
        reason = "stopped: Ctrl-C"
    except SystemExit as why:
        reason = f"not run: {why}"
    finally:
        view.running = False
        rig.stop()
        stop.set()
        if loop is not None:
            loop.join(2.0)
        if moved_motors and rig.motors:
            rig.disable(list(rig.motors))
        time.sleep(0.1)
        ask_imu(robot, dict.fromkeys((*IMU_OFF_IN_RUN, *IMU_REPORTS), IMU_DEFAULT_HZ))
        try:
            robot.send("indicate", fast=False)
        except diag_client.RobotError:
            pass
    try:
        robot.release_control()
    except diag_client.RobotError:
        pass
    robot.close()
    print(f"\n{reason}")
    if results:
        print("\nWhat it saw:")
        for words, what in results:
            print(f"  {words}: {what}")
    if stepper is not None:
        print(stepper.timing())
    if rig.writer is not None:
        rig.writer.close({"ended": reason, "counts": rig.counts})
        print(f"{rig.writer.lines} lines in {rig.writer.inner.path}")
        if args.mode == "lower" and touch is not None:
            report_lowering(touch, args, rig.writer.inner.path.name)
    bad = results and any("WRONG" in r or "NOT SEEN" in r for _, r in results)
    return 0 if reason == "done" and not bad else 1


def listen(woken: threading.Event) -> None:
    """launcher.py's words, once it has begun."""
    for line in sys.stdin:
        if line.strip() == "wake":
            woken.set()


def operate(args, go, stop, done, view) -> None:
    """The operator's end: Enter to start, Enter to stop, or a count to start."""
    if args.mode == "dry" or args.button:
        done.wait()
        return
    if args.mode == "run":
        if args.go_file is not None:
            go_by_file(args.go_file, args.go_wait, go, stop, done, view)
        elif args.start_after is not None:
            view.note = f"starting {args.start_after:g} s after the legs have settled"
            settled = EASE_S + FIRM_S + 0.5
            if done.wait(settled + args.start_after):
                return
            view.note = ""
            go.set()
        else:
            if done.wait(EASE_S + FIRM_S + 0.5):
                return
            if not answered(
                "\nUpright on its wheels? Enter starts the policy; Enter again stops it.\n"
            ):
                done.wait()
                return
            go.set()
    if answered(""):
        stop.set()
    done.wait()


def go_by_file(path: Path, patience: float, go, stop, done, view) -> None:
    """Hold the crouch until the file appears, for a run nobody is at the keyboard
    of, while the robot is lowered and steadied. A file that comes when the robot
    is not ready is used up, and another is waited for."""
    path.unlink(missing_ok=True)
    view.note = f"holding until {path} appears"
    if done.wait(EASE_S + FIRM_S + 0.5):
        return
    deadline = clock() + patience
    while view.phase in ("ease", "firm", "hold"):
        if clock() > deadline:
            stop.set()
            return
        if path.exists():
            path.unlink(missing_ok=True)
            go.set()
        if done.wait(0.05):
            return


def answered(prompt: str) -> bool:
    try:
        input(prompt)
        return True
    except EOFError:
        return False  # nobody at a keyboard: the other ways of stopping still work


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("dry", "hold", "run", "lower", "launch"))
    ap.add_argument("--robot", default=diag_client.DEFAULT_ROBOT)
    ap.add_argument("--policy", type=Path, default=HERE / "policy.npz")
    ap.add_argument(
        "--jump-policy",
        type=Path,
        help="a jump policy's pack: the controller's A button then jumps (with --drive)",
    )
    ap.add_argument(
        "--jump-height",
        type=float,
        default=0.03,
        help="m of wheel clearance a jump is asked for, held to what the policy was "
        "trained on; set here and never from the controller (default 0.03)",
    )
    ap.add_argument("--robot-file", type=Path, help="in place of sysid_robot.json")
    ap.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="how long to run, 0 for as long as it stays up: 30 for run and launch, "
        "20 for hold, 60 for lower",
    )
    ap.add_argument("--tilt", type=float, default=TILT_DEG, help="the cut-off, degrees")
    ap.add_argument(
        "--wheel-limit",
        type=float,
        help="Nm, for trying it with the wheels off the ground; it cannot balance on less than full",
    )
    ap.add_argument(
        "--no-hold", action="store_true", help="do not hold heading and place"
    )
    ap.add_argument(
        "--fast-speed",
        type=float,
        help="m/s at a full pull once select is pressed (default: the policy's top)",
    )
    ap.add_argument(
        "--fast-turn",
        type=float,
        help="rad/s at a stick's end once select is pressed (default: the policy's top)",
    )
    ap.add_argument(
        "--lean-per-m-s",
        type=float,
        default=0.0,
        help="degrees nose-up the driving policy is told it leans for each m/s it is "
        "sent, nose-down backwards, so that it goes faster: 1.25 is 2 degrees at 1.6 "
        "m/s. Its input only; the safety checks read the IMU as it is (default 0)",
    )
    ap.add_argument(
        "--no-trim",
        action="store_true",
        help="do not nudge what the policy is asked towards what it then does",
    )
    ap.add_argument(
        "--drive", action="store_true", help="speed and turn from the game controller"
    )
    ap.add_argument(
        "--max-speed", type=float, default=0.5, help="m/s at a full pull, with --drive"
    )
    ap.add_argument(
        "--max-turn",
        type=float,
        default=1.5,
        help="rad/s at a stick's end, with --drive",
    )
    ap.add_argument(
        "--max-sideways",
        type=float,
        help=f"m/s2 of speed times turn before a turn gives way "
        f"(default {Operator.SIDEWAYS_M_S2:g})",
    )
    ap.add_argument(
        "--past-trained",
        action="store_true",
        help="let --max-speed and --max-turn pass what the policy was trained on",
    )
    ap.add_argument("--height", type=float, help="leg height, hip to axle, m")
    ap.add_argument(
        "--start-after",
        type=float,
        help="start the policy this long after the legs settle, not on Enter",
    )
    ap.add_argument(
        "--go-file",
        type=Path,
        help="hold the crouch until this file appears, then start the policy",
    )
    ap.add_argument(
        "--go-wait",
        type=float,
        default=300.0,
        help="seconds to hold for --go-file before giving up and cutting the motors",
    )
    ap.add_argument(
        "--touch-nm",
        type=float,
        help="launch: what each knee has to feel, in place of what lower measured",
    )
    ap.add_argument(
        "--touch-file",
        type=Path,
        default=LAUNCH_FILE,
        help="where lower puts what it measured, and launch finds it",
    )
    ap.add_argument(
        "--touch-wait",
        type=float,
        default=TOUCH_WAIT_S,
        help="launch: seconds to wait for the floor before letting the legs down, "
        "0 for as long as it takes",
    )
    ap.add_argument(
        "--once",
        action="store_true",
        help="launch: end when picked up or fallen over, rather than waiting to go again",
    )
    ap.add_argument("--rt", action="store_true", help="the loop at real-time priority")
    ap.add_argument(
        "--yes", action="store_true", help="enable the motors without asking"
    )
    ap.add_argument(
        "--wait",
        type=float,
        default=DRY_WAIT_S,
        help="dry: seconds to wait for each move",
    )
    ap.add_argument("--label")
    ap.add_argument("--out")
    ap.add_argument(
        "--button",
        action="store_true",
        help="launcher.py's: wait for its word, take control from whatever holds it",
    )
    ap.add_argument(
        "--phase-file", type=Path, help="where to say what it is doing, for launcher.py"
    )
    args = ap.parse_args(argv)
    if args.seconds is None:
        args.seconds = {"hold": 20.0, "lower": 60.0}.get(args.mode, 30.0)
    if args.mode in ("hold", "lower") and args.seconds <= 0:
        ap.error(f"{args.mode} needs a time")

    def stop_cleanly(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_cleanly)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, stop_cleanly)
    if args.button:
        try:
            if not sys.stdin.readline():
                return 0  # launcher.py went, and never asked
        except KeyboardInterrupt:
            return 0
    return session(args)


if __name__ == "__main__":
    raise SystemExit(main())
