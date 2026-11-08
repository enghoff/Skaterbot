# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "pyserial>=3.5"]
# ///
"""sbc/balance.py's lean: the driving policy told it leans back in proportion to the speed
it is sent, and nothing else told so. Free, offline, no robot and no network: the policies
here are stand-ins that keep what they are shown.

    uv run tools/test_lean.py
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbc"))
sys.path.insert(0, str(ROOT / "tools"))

import balance  # noqa: E402
import policy_loop as pl  # noqa: E402
import sysid_tests as st  # noqa: E402
from test_jump import DRIVING, JUMPING, Answers, legs_at  # noqa: E402

UP = np.array([0.0, 0.0, -1.0])
STILL = np.zeros(3)
# 2 degrees at D9's top of 1.6 m/s.
PER_M_S = 1.25


def nose_up_deg(g) -> float:
    return -math.degrees(pl.nose_down(np.asarray(g, dtype=float)))


def leaning(per_m_s: float = PER_M_S):
    net = Answers(DRIVING)
    return balance.LeanedBalancer(net, lean_per_m_s=per_m_s), net


def fed(bal, speed: float, g=UP) -> np.ndarray:
    fb = legs_at(0.25, 0.5)
    return bal.observe(fb, STILL, g, speed, 0.0, 0.2035)[3:6].copy()


def pitched(nose_up: float, roll_right: float = 0.0) -> np.ndarray:
    """Gravity's direction in a torso pitched nose-up and rolled right side down."""
    p, r = math.radians(nose_up), math.radians(roll_right)
    return np.array(
        [-math.sin(p), -math.cos(p) * math.sin(r), -math.cos(p) * math.cos(r)]
    )


class TheLean(unittest.TestCase):
    def test_nothing_standing(self):
        bal, _ = leaning()
        g = pitched(3.0, 1.0)
        np.testing.assert_array_equal(fed(bal, 0.0, g), g.astype(np.float32))
        self.assertEqual(bal.lean_deg, 0.0)

    def test_nothing_by_default(self):
        bal, _ = leaning(0.0)
        g = pitched(-4.0)
        np.testing.assert_array_equal(fed(bal, 1.6, g), g.astype(np.float32))

    def test_forwards_it_reads_nose_up(self):
        bal, _ = leaning()
        self.assertAlmostEqual(nose_up_deg(fed(bal, 1.6)), 2.0, places=5)
        # Nose-up is gravity towards the tail: policy_loop.nose_down's sign.
        self.assertLess(fed(bal, 1.6)[0], 0.0)

    def test_backwards_it_reads_nose_down(self):
        bal, _ = leaning()
        self.assertAlmostEqual(nose_up_deg(fed(bal, -1.6)), -2.0, places=5)

    def test_in_proportion_to_the_speed_sent(self):
        bal, _ = leaning()
        for speed in (0.1, 0.5, 0.8, 1.2, 1.6, 1.8):
            self.assertAlmostEqual(
                nose_up_deg(fed(bal, speed)), PER_M_S * speed, places=5
            )
            self.assertAlmostEqual(bal.lean_deg, PER_M_S * speed)

    def test_added_to_the_pitch_it_has(self):
        bal, _ = leaning()
        self.assertAlmostEqual(
            nose_up_deg(fed(bal, 0.8, pitched(-5.0))), -4.0, places=5
        )

    def test_a_turn_and_still_a_unit_direction(self):
        bal, _ = leaning()
        g = pitched(3.0, 4.0)
        out = fed(bal, 1.6, g)
        self.assertAlmostEqual(float(np.linalg.norm(out)), 1.0)
        self.assertAlmostEqual(out[1], g[1])
        self.assertAlmostEqual(nose_up_deg(out), nose_up_deg(g) + 2.0, places=5)

    def test_the_rest_of_the_input_untouched(self):
        plain = pl.Balancer(Answers(DRIVING))
        bal, _ = leaning()
        fb = legs_at(0.3, 0.6, wheel_v=20.0)
        w = np.array([0.1, -0.2, 0.3])
        a = plain.observe(fb, w, UP, 1.2, 0.5, 0.19).copy()
        b = bal.observe(fb, w, UP, 1.2, 0.5, 0.19).copy()
        same = [k for k in range(len(a)) if k not in (3, 5)]
        np.testing.assert_array_equal(a[same], b[same])
        self.assertNotEqual(a[3], b[3])


class NotTheJump(unittest.TestCase):
    def pair(self):
        dn, jn = Answers(DRIVING), Answers(JUMPING)
        driving = balance.LeanedBalancer(dn, lean_per_m_s=PER_M_S)
        two = pl.TwoPolicies(driving, pl.JumpBalancer(jn), 0.03)
        return two

    def test_the_driving_policy_leans_inside_two_policies(self):
        two = self.pair()
        obs = two.observe(legs_at(0.25, 0.5), STILL, UP, 0.8, 0.0, 0.2035)
        self.assertAlmostEqual(nose_up_deg(obs[3:6]), 1.0, places=5)

    def test_the_jump_policy_is_fed_gravity_as_it_is(self):
        two = self.pair()
        self.assertIsNone(two.press(UP, 0.5, True))
        self.assertIs(two.active, two.jumping)
        g = pitched(3.0)
        obs = two.observe(legs_at(0.25, 0.5), STILL, g, 0.8, 0.0, 0.2035)
        np.testing.assert_array_equal(obs[3:6], g.astype(np.float32))


class FakeRig:
    """Every motor in the crouch and answering, and an IMU reading `gravity`."""

    def __init__(self, gravity_m_s2):
        self.now = 0.0
        self.gravity = list(gravity_m_s2)
        self.latest: dict = {}
        self.imu: dict = {}
        self.sent: list = []
        self._report()

    def _report(self):
        self.latest = {
            j: st.Fb(at=self.now, p=p, v=0.0, tau=0.0)
            for j, p in zip(st.JOINTS, (0.25, 0.5, 0.25, 0.5, 0.0, 0.0), strict=True)
        }
        self.imu = {
            "gyro": (self.now, [0.0, 0.0, 0.0]),
            "gravity": (self.now, self.gravity),
        }

    def send(self, joint, cmd):
        self.sent.append((joint, cmd))
        self._report()

    def ask_status(self, joints):
        self._report()

    def clock(self):
        return self.now

    def nap(self):
        self.now += 0.0005


class TheSafetyChecksDoNotSeeIt(unittest.TestCase):
    """At 9 degrees nose-up, under a 10 degree cut-off, told it leans 2 more."""

    def stepper(self, recover: bool):
        rig = FakeRig(pl.GRAVITY_M_S2 * pitched(9.0))
        bal, _ = leaning()
        guard = pl.Guard(10.0, pl.limits())
        guard.recover = recover
        stepper = pl.Stepper(
            bal,
            pl.Imu(np.eye(3), 1),
            rig,
            guard,
            clock=rig.clock,
            wait=lambda t: None,
            nap=rig.nap,
        )
        return stepper, rig, bal, guard

    def test_the_cut_off_reads_the_imu(self):
        stepper, rig, bal, guard = self.stepper(recover=False)
        step = stepper.step(0.0, 1.6, 0.0, 0.2035)  # past 10 would raise Tipped
        self.assertAlmostEqual(nose_up_deg(step["g"]), 9.0, places=5)
        self.assertAlmostEqual(nose_up_deg(step["obs"][3:6]), 11.0, places=5)
        self.assertAlmostEqual(bal.lean_deg, 2.0)
        with self.assertRaises(pl.Tipped):
            guard.check(rig.now, rig.latest, step["obs"][3:6])

    def test_driving_armed_the_tilt_is_the_imu_s(self):
        stepper, _, _, guard = self.stepper(recover=True)
        step = stepper.step(0.0, 1.6, 0.0, 0.2035)
        self.assertNotIn("tilt", guard.trouble)
        self.assertAlmostEqual(math.degrees(pl.tilt(step["g"])), 9.0)

    def test_what_the_loop_hands_on_is_the_imu_s(self):
        # balance.powered's limp and picked-up checks, Touch's feeling the floor and a
        # jump's tilt refusal all read step["g"], and Trim and Hold are handed the same.
        stepper, _, _, _ = self.stepper(recover=True)
        step = stepper.step(0.0, 1.6, 0.0, 0.2035)
        np.testing.assert_allclose(step["g"], pitched(9.0), atol=1e-12)
        self.assertGreater(abs(step["obs"][3] - step["g"][0]), 0.03)

    def test_the_imu_checks_judge_its_own_report(self):
        stepper, _, _, _ = self.stepper(recover=True)
        stepper.step(0.0, 1.6, 0.0, 0.2035)
        self.assertEqual(stepper.attitude.why, "")
        np.testing.assert_allclose(stepper.attitude.believed, pitched(9.0), atol=1e-12)


if __name__ == "__main__":
    unittest.main()
