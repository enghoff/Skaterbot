# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "pyserial>=3.5"]
# ///
"""sbc/policy_loop.py's Attitude: a gravity report the gyro cannot account for is not
believed, and the gyro carries the last one that was. On the robot on 2026-11-06 a jump
shook the IMU into starting its estimate over, its gravity read the robot upside down
for half a second, and the fall check let go of a robot standing at 4 degrees.
Free, offline, no robot.

    uv run tools/test_attitude.py
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbc"))

import policy_loop as pl  # noqa: E402

# The robot's own chip: mounted about 6 degrees off, gravity read with its sign flipped.
AXES = [
    [0.99448, -0.01618, 0.10369],
    [-0.01771, -0.99975, 0.01384],
    [0.10344, -0.0156, -0.99451],
]
SIGN = -1
RESTART = [0.0, 0.0, 9.800781]


def chip(g_torso) -> list[float]:
    """What the chip reports for gravity along `g_torso`, a direction in the torso."""
    a = np.array(AXES)
    v = a.T @ (np.asarray(g_torso, dtype=float) * pl.GRAVITY_M_S2) * SIGN
    return [float(x) for x in v]


def pitched(rad: float) -> np.ndarray:
    """Gravity in the torso, nose down by `rad`."""
    return np.array([math.sin(rad), 0.0, -math.cos(rad)])


def gyro_chip(w_torso) -> list[float]:
    return [float(x) for x in np.array(AXES).T @ np.asarray(w_torso, dtype=float)]


class Believed(unittest.TestCase):
    def setUp(self):
        self.att = pl.Attitude(pl.Imu(AXES, SIGN))

    def test_a_good_reading_is_taken_as_it_is(self):
        _, g = self.att.read(0.0, [0, 0, 0], chip(pitched(0.1)))
        self.assertAlmostEqual(math.degrees(pl.nose_down(g)), math.degrees(0.1), 3)
        self.assertEqual(self.att.doubted_for, 0.0)

    def test_a_fast_turn_the_gyro_saw_is_believed(self):
        rate = 6.0
        self.att.read(0.0, gyro_chip([0, rate, 0]), chip(pitched(0.0)))
        for k in range(1, 30):
            t = k * 0.01
            _, g = self.att.read(t, gyro_chip([0, rate, 0]), chip(pitched(rate * t)))
            self.assertEqual(self.att.doubted_for, 0.0, f"doubted at {t:.2f} s")
        self.assertAlmostEqual(pl.nose_down(g), rate * 0.29, 3)

    def test_reports_coming_slower_than_the_steps_are_believed_turning_fast(self):
        # Gravity 30 times a second, the steps 100: each new report has moved 20
        # degrees on from the last, which the gyro saw.
        rate = 10.0
        report = chip(pitched(0.0))
        for k in range(0, 40):
            t = k * 0.01
            if k % 3 == 0:
                report = chip(pitched(rate * t))
            self.att.read(t, gyro_chip([0, rate, 0]), report)
            self.assertEqual(self.att.doubted_for, 0.0, f"doubted at {t:.2f} s")

    def test_level_exactly_is_not_mistaken_for_starting_over(self):
        att = pl.Attitude(pl.Imu(np.eye(3), 1))
        _, g = att.read(0.0, [0, 0, 0], [0.0, 0.0, -9.8])
        self.assertEqual(att.doubted_for, 0.0)
        self.assertAlmostEqual(math.degrees(pl.tilt(g)), 0.0)


class Doubted(unittest.TestCase):
    def setUp(self):
        self.att = pl.Attitude(pl.Imu(AXES, SIGN))
        self.att.read(0.0, [0, 0, 0], chip(pitched(math.radians(4))))

    def test_the_chip_starting_over_is_not_a_fall(self):
        _, g = self.att.read(0.01, [0, 0, 0], RESTART)
        self.assertLess(math.degrees(pl.tilt(g)), 5.0)
        self.assertGreater(self.att.doubted_for, 0.0)
        self.assertIn("starting over", self.att.why)

    def test_the_gyro_carries_it_meanwhile(self):
        rate = 1.0
        for k in range(1, 51):
            _, g = self.att.read(k * 0.01, gyro_chip([0, rate, 0]), RESTART)
        self.assertAlmostEqual(
            math.degrees(pl.nose_down(g)), 4.0 + math.degrees(rate * 0.5), delta=0.5
        )
        self.assertAlmostEqual(self.att.doubted_for, 0.5, places=6)

    def test_the_wrong_length_is_not_believed(self):
        _, g = self.att.read(0.01, [0, 0, 0], [1.6 * x for x in chip(pitched(1.0))])
        self.assertLess(math.degrees(pl.tilt(g)), 5.0)
        self.assertIn("long", self.att.why)

    def test_a_turn_the_gyro_did_not_see_is_not_believed(self):
        _, g = self.att.read(0.01, [0, 0, 0], chip(pitched(math.radians(40))))
        self.assertLess(math.degrees(pl.tilt(g)), 5.0)
        self.assertIn("more than the gyro saw", self.att.why)

    def test_after_starting_over_a_long_report_is_not_believed(self):
        # At 20:13 on 8 November 2026 they came back 11 to 12 m/s2 long, and 10 degrees
        # out, for the last 0.8 s, inside the length that is otherwise believed.
        self.att.read(0.01, [0, 0, 0], RESTART)
        self.att.read(
            0.02, [0, 0, 0], [1.15 * x for x in chip(pitched(math.radians(14)))]
        )
        self.assertIn("long", self.att.why)
        _, g = self.att.read(0.03, [0, 0, 0], chip(pitched(math.radians(5))))
        self.assertEqual(self.att.doubted_for, 0.0)
        self.assertFalse(self.att.restarted)
        self.assertAlmostEqual(math.degrees(pl.nose_down(g)), 5.0, 3)

    def test_without_starting_over_a_long_report_is_believed(self):
        _, g = self.att.read(
            0.01, [0, 0, 0], [1.15 * x for x in chip(pitched(math.radians(5)))]
        )
        self.assertEqual(self.att.doubted_for, 0.0)
        self.assertAlmostEqual(math.degrees(pl.nose_down(g)), 5.0, 3)

    def test_the_gyro_carries_it_for_longer_than_the_chip_took(self):
        # The chip was back 2.9 s after starting over, on 8 November 2026.
        self.assertGreater(pl.GYRO_CARRY_S, 2.9)

    def test_believed_again_once_it_agrees(self):
        self.att.read(0.01, [0, 0, 0], RESTART)
        self.att.read(0.02, [0, 0, 0], chip(pitched(math.radians(5))))
        self.assertEqual(self.att.doubted_for, 0.0)

    def test_believing_anyway_takes_the_next_report(self):
        self.att.read(0.01, [0, 0, 0], chip(pitched(math.radians(50))))
        self.att.believe_anyway()
        _, g = self.att.read(0.02, [0, 0, 0], chip(pitched(math.radians(50))))
        self.assertAlmostEqual(math.degrees(pl.nose_down(g)), 50.0, 3)
        self.assertEqual(self.att.doubted_for, 0.0)

    def test_a_long_gap_is_not_turned_through(self):
        _, g = self.att.read(5.0, gyro_chip([0, 3.0, 0]), RESTART)
        self.assertLessEqual(self.att.doubted_for, pl.CARRY_STEP_MAX_S + 1e-9)


class AWheelOnTheFloor(unittest.TestCase):
    """FreeWheels: a wheel turning free counts towards a lift, unless the other is
    plainly on the floor."""

    def fed(self, said, steps):
        fw = pl.FreeWheels()
        verdict = iter(said * steps)
        fw._one = lambda k, fb, rate, dt: next(verdict)
        fired = False
        for k in range(steps):
            fired = fw.update({}, 0.0, k * 0.01)
        return fw, fired

    def test_one_free_with_the_other_on_the_floor_is_no_lift(self):
        # The inside wheel in a hard turn at speed, 20:12 on 8 November 2026.
        fw, fired = self.fed([1, -1], 100)
        self.assertFalse(fired)
        self.assertEqual(fw.sure, 0.0)

    def test_both_free_is_a_lift(self):
        self.assertTrue(self.fed([1, 1], 60)[1])

    def test_one_free_with_the_other_saying_nothing_is_a_lift(self):
        self.assertTrue(self.fed([1, 0], 60)[1])


if __name__ == "__main__":
    unittest.main()
