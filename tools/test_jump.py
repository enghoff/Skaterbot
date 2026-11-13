# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "pyserial>=3.5"]
# ///
"""The jump on the robot's side: sbc/policy_loop.py's TwoPolicies and JumpBalancer, and
sbc/balance.py's Operator counting the A button. The hand-over's timing, what refuses a
press, the actions carried across, the jump policy's inputs and gains. Free, offline,
no robot and no network: the policies here are stand-ins that answer what they are told.

    uv run tools/test_jump.py
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbc"))

import balance  # noqa: E402
import policy_loop as pl  # noqa: E402
import sysid_tests as st  # noqa: E402

COMMON = {
    "legs": list(st.LEGS),
    "wheels": list(st.WHEELS),
    "crouch": [0.25, 0.5, 0.25, 0.5],
    "leg_lo": [-0.7, -0.35, -0.7, -0.35],
    "leg_hi": [0.9, 1.55, 0.9, 1.55],
    "kp": 12.0,
    "kd": 0.4,
    "wheel_scale": 1.0,
    "wheel_radius": 0.04,
    "default_height": 0.2035,
    "elu_alpha": 1.0,
    "layers": 1,
}
DRIVING = COMMON | {
    "leg_scale": [0.4, 0.8, 0.4, 0.8],
    "height_range": [0.17, 0.207],
    "speed_range": [-1.8, 1.8],
    "turn_range": [-15.0, 15.0],
    "scale_height": False,
    "n_obs": 25,
    "n_act": 6,
}
JUMPING = COMMON | {
    "leg_scale": [0.6, 1.2, 0.6, 1.2],
    "height_range": [0.15, 0.207],
    "speed_range": [-1.2, 1.2],
    "turn_range": [-4.0, 4.0],
    "scale_height": True,
    "n_obs": 29,
    "n_act": 8,
    "jump": {
        "clearance_m": [0.02, 0.12],
        "leg_gain_range": 2.0,
        "crouch_s": 0.6,
        "crouch_tolerance_m": 0.005,
        "window_s": 1.5,
        "takeoff_window_s": 0.8,
        "observe_battery": True,
        "score_to_target": True,
    },
}


class Answers:
    """A stand-in network: answers `out`, and keeps what it was shown."""

    def __init__(self, meta: dict):
        self.meta = meta
        self.out = np.zeros(meta["n_act"], dtype=np.float32)
        self.seen: list[np.ndarray] = []

    def __call__(self, obs):
        self.seen.append(obs.copy())
        return self.out.copy()


def legs_at(hip: float, knee: float, wheel_v: float = 0.0) -> dict:
    fb = {}
    for j in st.LEGS:
        fb[j] = st.Fb(at=0.0, p=hip if "hip" in j else knee, v=0.0, tau=0.0)
    for j in st.WHEELS:
        fb[j] = st.Fb(at=0.0, p=0.0, v=wheel_v, tau=0.0)
    return fb


def knee_for(height: float, hip: float = 0.25) -> float:
    """The knee angle that puts a leg at this height with this hip."""
    return hip + math.acos(height / pl.LEG_LINK_M - math.cos(hip))


UP = np.array([0.0, 0.0, -1.0])
STILL = np.zeros(3)


def pair(clearance=0.03, volts=None):
    dn, jn = Answers(DRIVING), Answers(JUMPING)
    two = pl.TwoPolicies(pl.Balancer(dn), pl.JumpBalancer(jn), clearance, volts=volts)
    return two, dn, jn


def step(two, fb, speed=0.0, height=0.2035, g=UP):
    obs = two.observe(fb, STILL, g, speed, 0.0, height)
    return obs, two.decide(obs)


class Sequence(unittest.TestCase):
    def test_a_press_crouches_on_the_jump_policy_with_the_trigger_down(self):
        two, _, jn = pair()
        self.assertIsNone(two.press(UP, 0.0, True))
        self.assertEqual(two.state, "crouch")
        obs, _ = step(two, legs_at(0.25, 0.5))
        self.assertIs(two.active, two.jumping)
        self.assertEqual(obs[25], 0.0)
        # The lowest ride height asked for, on the jump policy's -1 to 1.
        self.assertAlmostEqual(float(obs[8]), -1.0, places=5)

    def test_the_trigger_comes_when_the_legs_are_down(self):
        two, _, _ = pair()
        two.press(UP, 0.0, True)
        low = legs_at(0.25, knee_for(0.152))
        obs, _ = step(two, low)
        self.assertEqual(two.state, "jump")
        self.assertEqual(obs[25], 1.0)
        self.assertAlmostEqual(float(obs[26]), 0.3, places=5)

    def test_or_at_the_crouch_s_if_they_never_get_there(self):
        two, _, _ = pair()
        two.press(UP, 0.0, True)
        n = 0
        while two.state == "crouch":
            step(two, legs_at(0.25, 0.5))
            n += 1
        self.assertAlmostEqual(n * pl.PERIOD_S, 0.6, delta=0.011)

    def test_the_bottom_held_half_a_second_then_the_operators_height(self):
        two, _, _ = pair()
        two.press(UP, 0.0, True)
        low = legs_at(0.25, knee_for(0.152))
        heights = []
        while two.state != "drive":
            obs, _ = step(two, low, height=0.2035)
            if two.active is two.jumping and two.state == "jump":
                heights.append((two.t, float(obs[8])))
        early = [h for t, h in heights if t < 0.49]
        late = [h for t, h in heights if t > 0.51]
        self.assertTrue(all(abs(h + 1.0) < 1e-5 for h in early))
        want = (0.2035 - 0.1785) / 0.0285
        self.assertTrue(all(abs(h - want) < 1e-4 for h in late))

    def test_handed_back_landed_and_settling_after(self):
        two, _, _ = pair()
        two.press(UP, 0.0, True)
        low = legs_at(0.25, knee_for(0.152))
        step(two, low)
        jumping = 0
        while two.state == "jump":
            step(two, low)
            jumping += 1
        # The run's window is 1.5 s; the robot's own hand-back is sooner.
        self.assertAlmostEqual(
            (jumping + 1) * pl.PERIOD_S, pl.JUMP_HAND_BACK_S, delta=0.011
        )
        self.assertIs(two.active, two.driving)
        self.assertTrue(two.busy)
        for _ in range(int(pl.JUMP_SETTLE_S / pl.PERIOD_S) + 1):
            step(two, legs_at(0.25, 0.5))
        self.assertFalse(two.busy)

    def test_the_timer_and_the_battery(self):
        two, _, _ = pair(volts=lambda: 25.2)
        two.press(UP, 0.0, True)
        low = legs_at(0.25, knee_for(0.152))
        step(two, low)
        for _ in range(30):
            obs, _ = step(two, low)
        self.assertAlmostEqual(float(obs[27]), two.t, places=5)
        self.assertAlmostEqual(float(obs[28]), (25.2 / 24.0 - 1.0) * 5.0, places=5)

    def test_events_say_what_happened(self):
        two, _, _ = pair()
        two.press(UP, 0.0, True)
        low = legs_at(0.25, knee_for(0.152))
        while two.state != "drive":
            step(two, low)
        words = " | ".join(two.events)
        for part in ("pressed", "crouching", "jump:", "handed back"):
            self.assertIn(part, words)


class Refusals(unittest.TestCase):
    def test_tilted(self):
        two, _, _ = pair()
        g = np.array([math.sin(math.radians(20)), 0.0, -math.cos(math.radians(20))])
        self.assertIn("tilted", two.press(g, 0.0, True))
        self.assertEqual(two.state, "drive")

    def test_a_wheel_off_the_floor(self):
        two, _, _ = pair()
        self.assertIn("floor", two.press(UP, 0.0, False))

    def test_already_jumping(self):
        two, _, _ = pair()
        two.press(UP, 0.0, True)
        self.assertIn("already", two.press(UP, 0.0, True))

    def test_too_fast_brakes_first(self):
        two, _, _ = pair()
        self.assertIsNone(two.press(UP, 1.5, True))
        self.assertEqual(two.state, "braking")
        self.assertEqual(two.speed_cap, pl.JUMP_SPEED_CAP_M_S)
        # 1.5 m/s on 40 mm wheels is 37.5 rad/s.
        step(two, legs_at(0.25, 0.5, wheel_v=37.5))
        self.assertIs(two.active, two.driving)
        # Under 1 m/s, and then half a second more before the crouch.
        for _ in range(int(pl.JUMP_BRAKED_S / pl.PERIOD_S) - 1):
            step(two, legs_at(0.25, 0.5, wheel_v=20.0))
        self.assertEqual(two.state, "braking")
        step(two, legs_at(0.25, 0.5, wheel_v=20.0))
        step(two, legs_at(0.25, 0.5, wheel_v=20.0))
        self.assertEqual(two.state, "crouch")

    def test_and_gives_up_if_it_will_not_slow(self):
        two, _, _ = pair()
        two.press(UP, 1.5, True)
        for _ in range(int(pl.JUMP_BRAKE_GIVE_UP_S / pl.PERIOD_S) + 2):
            step(two, legs_at(0.25, 0.5, wheel_v=37.5))
        self.assertEqual(two.state, "drive")
        self.assertIn("refused", two.events[-1])

    def test_a_target_held_to_what_was_trained(self):
        self.assertEqual(pair(clearance=0.5)[0].clearance, 0.12)
        self.assertEqual(pair(clearance=0.0)[0].clearance, 0.02)


class Carried(unittest.TestCase):
    def test_the_same_leg_angles_either_way(self):
        two, dn, jn = pair()
        dn.out[:] = [0.3, -0.5, 0.1, 0.9, 0.2, -0.4]
        step(two, legs_at(0.25, 0.5))
        two.press(UP, 0.0, True)
        j = two.jumping
        d = two.driving
        asked_d = d.crouch + d.leg_scale * d.actions[:4]
        asked_j = j.crouch + j.leg_scale * j.actions[:4]
        np.testing.assert_allclose(asked_j, asked_d, atol=1e-6)
        np.testing.assert_allclose(j.actions[4:6], d.actions[4:6])
        np.testing.assert_allclose(j.actions[6:8], 0.0)
        # And what the jump policy is then shown as its last outputs.
        carried = j.actions[:6].copy()
        obs, _ = step(two, legs_at(0.25, 0.5))
        np.testing.assert_allclose(obs[19:25], carried, atol=1e-6)

    def test_back_clipped_to_what_the_driving_policy_can_ask(self):
        two, dn, jn = pair()
        two.press(UP, 0.0, True)
        jn.out[:] = [0.0, 1.0, 0.0, -1.0, 0.5, 0.5, 0.0, 0.0]
        low = legs_at(0.25, knee_for(0.152))
        while two.state != "drive":
            step(two, low)
        # What the driving policy was shown as its last outputs, at the hand-back: the
        # knees' 1.7 and -0.7 rad are past its 0.8 rad of reach, so held at +/-1.
        shown = dn.seen[-1][19:25]
        np.testing.assert_allclose(shown, [0.0, 1.0, 0.0, -1.0, 0.5, 0.5], atol=1e-6)

    def test_gains_as_powers_of_the_range(self):
        two, _, jn = pair()
        two.press(UP, 0.0, True)
        jn.out[:] = [0, 0, 0, 0, 0, 0, 1.0, -1.0]
        _, cmds = step(two, legs_at(0.25, 0.5))
        for j in st.LEGS:
            self.assertAlmostEqual(cmds[j].kp, 24.0, places=4)
            self.assertAlmostEqual(cmds[j].kd, 0.2, places=4)

    def test_the_jump_policys_legs_held_inside_the_windows(self):
        two, _, jn = pair()
        two.press(UP, 0.0, True)
        jn.out[:] = [-1.0, 1.0, -1.0, -1.0, 0, 0, 0, 0]
        _, cmds = step(two, legs_at(0.25, 0.5))
        for j in st.LEGS:
            lo, hi = st.WINDOWS[j]
            self.assertTrue(lo <= cmds[j].p <= hi, (j, cmds[j].p))


class Presses(unittest.TestCase):
    def operator(self):
        args = SimpleNamespace(height=None, max_speed=1.0, max_turn=2.0, drive=False)
        meta = {
            "default_height": 0.2035,
            "height_range": [0.17, 0.207],
            "speed_range": [-1.8, 1.8],
            "turn_range": [-15.0, 15.0],
            "envelope": True,
        }
        return balance.Operator(None, meta, args)

    def heard(self, op, now, jump, forward=0.0):
        op.last = (now, {"forward": forward, "turn": 0.0, "live": True, "jump": jump})
        return op.ask(now)

    def test_a_press_from_before_taking_over_is_not_a_jump(self):
        op = self.operator()
        op.last = (0.0, {"forward": 0.0, "turn": 0.0, "live": True, "jump": 7})
        op.reset()
        self.heard(op, 0.0, 7)
        self.assertEqual(op.take_jumps(), 0)

    def test_presses_counted_once_each_and_through_the_wrap(self):
        op = self.operator()
        op.last = (0.0, {"forward": 0.0, "turn": 0.0, "live": True, "jump": 254})
        op.reset()
        self.heard(op, 0.0, 255)
        self.heard(op, 0.01, 1)
        # 255, then 0 and 1.
        self.assertEqual(op.take_jumps(), 3)
        self.assertEqual(op.take_jumps(), 0)

    def test_held_is_bit_8_and_not_a_press(self):
        """gamepad.py sets bit 8 over the count while A is held: pressed, held and let go
        of is one press, held while it is, and let go of once not."""
        op = self.operator()
        op.last = (0.0, {"forward": 0.0, "turn": 0.0, "live": True, "jump": 3})
        op.reset()
        self.assertIsNone(op.jump_held)
        seen = []
        for k, jump in enumerate([3, 4 | balance.JUMP_HELD, 4 | balance.JUMP_HELD, 4]):
            self.heard(op, k * 0.02, jump)
            seen.append((op.take_jumps(), op.jump_held))
        self.assertEqual(seen, [(0, False), (1, True), (0, True), (0, False)])

    def test_held_through_the_wrap(self):
        op = self.operator()
        op.last = (0.0, {"forward": 0.0, "turn": 0.0, "live": True, "jump": 255})
        op.reset()
        self.heard(op, 0.0, 0 | balance.JUMP_HELD)
        self.assertEqual((op.take_jumps(), op.jump_held), (1, True))

    def test_held_from_before_taking_over_is_no_press(self):
        op = self.operator()
        op.last = (0.0, {"forward": 0.0, "turn": 0.0, "live": True, "jump": 0x107})
        op.reset()
        self.heard(op, 0.0, 0x107)
        self.heard(op, 0.02, 7)
        self.assertEqual(op.take_jumps(), 0)

    def test_held_is_not_known_stale_or_not_live(self):
        """The controller gone quiet, or Linux having taken it away, is not a let-go."""
        op = self.operator()
        op.reset()
        self.heard(op, 0.0, 1 | balance.JUMP_HELD)
        self.assertTrue(op.jump_held)
        op.ask(op.FRESH_S + 0.01)
        self.assertIsNone(op.jump_held)
        m = {"forward": 0.0, "turn": 0.0, "live": False, "jump": 1 | balance.JUMP_HELD}
        op.last = (1.0, m)
        op.ask(1.0)
        self.assertIsNone(op.jump_held)

    def test_a_controller_from_before_is_never_held(self):
        op = self.operator()
        op.reset()
        for k, jump in enumerate([0, 1, 1, 2]):
            self.heard(op, k * 0.02, jump)
            self.assertIs(op.jump_held, False)
        self.assertEqual(op.take_jumps(), 2)

    def test_the_speed_cap_brakes_at_the_braking_rate(self):
        op = self.operator()
        op.reset()
        op.set_fast(True)
        t = 0.0
        while t < 4.0:
            speed, _, _ = self.heard(op, t, 0, forward=1.8)
            t += 0.01
        self.assertGreater(speed, 1.7)
        op.speed_cap = 0.9
        steps = 0
        while speed > 0.9 + 1e-9:
            speed, _, _ = self.heard(op, t, 0, forward=1.8)
            t += 0.01
            steps += 1
        self.assertAlmostEqual(
            steps * 0.01, (1.8 - 0.9) / op.STOP_RAMP_M_S2, delta=0.03
        )

    def test_the_turn_cap_brings_the_turn_down_and_back_at_the_ramps(self):
        """The scripted jump's: a spin let go of at A's let-go, and given back after the
        landing, both at the rates a stick moved does."""
        op = self.operator()
        op.reset()
        op.set_fast(True)

        def turn_at(t: float) -> float:
            op.last = (t, {"forward": 0.0, "turn": 15.0, "live": True, "jump": 0})
            return op.ask(t)[1]

        t, turn = 0.0, 0.0
        while t < 6.0:
            turn = turn_at(t)
            t += 0.01
        self.assertAlmostEqual(turn, 15.0)
        for cap, want, rate in (
            (0.0, 0.0, op.TURN_STOP_RAD_S2),
            (None, 15.0, op.TURN_RAMP_RAD_S2),
        ):
            op.turn_cap = cap
            steps = 0
            while abs(turn - want) > 1e-9:
                turn = turn_at(t)
                t += 0.01
                steps += 1
                self.assertLess(steps, 1000)
            self.assertAlmostEqual(steps * 0.01, 15.0 / rate, delta=0.03)
        op.turn_cap = 0.0
        op.reset()
        self.assertIsNone(op.turn_cap)


if __name__ == "__main__":
    unittest.main()
