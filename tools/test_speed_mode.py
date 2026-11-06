# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "pyserial>=3.5"]
# ///
"""sbc/balance.py's Operator: the controller's select button toggling the speed limits, and
the diamond an envelope policy was trained inside. Free, offline, no robot.

    uv run tools/test_speed_mode.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbc"))

import balance  # noqa: E402

META = {
    "default_height": 0.2035,
    "height_range": [0.17, 0.207],
    "speed_range": [-1.8, 1.8],
    "turn_range": [-15.0, 15.0],
    "envelope": True,
}


def operator(**changes) -> balance.Operator:
    args = SimpleNamespace(height=None, max_speed=1.0, max_turn=2.0, drive=False)
    for k, v in changes.items():
        setattr(args, k, v)
    op = balance.Operator(None, META, args)
    op.reset()
    return op


def heard(op, now, forward=1.8, turn=0.0, mode=0) -> tuple[float, float]:
    op.last = (
        now,
        {
            "forward": forward,
            "turn": turn,
            "height": 0.2035,
            "live": True,
            "mode": mode,
        },
    )
    return op.wanted(now)


class SpeedMode(unittest.TestCase):
    def test_it_starts_slow(self):
        op = operator()
        self.assertAlmostEqual(heard(op, 0.0)[0], 1.0)
        self.assertAlmostEqual(heard(op, 0.0, forward=0.9)[0], 0.5)

    def test_select_makes_it_fast_and_again_slow(self):
        op = operator()
        heard(op, 0.0, mode=7)
        self.assertAlmostEqual(heard(op, 0.1, mode=8)[0], 1.8)
        self.assertAlmostEqual(heard(op, 0.2, mode=8)[0], 1.8)
        self.assertAlmostEqual(heard(op, 0.3, mode=9)[0], 1.0)

    def test_two_presses_between_looks_cancel(self):
        op = operator()
        heard(op, 0.0, mode=3)
        self.assertAlmostEqual(heard(op, 0.1, mode=5)[0], 1.0)

    def test_the_count_wrapping_still_counts(self):
        op = operator()
        heard(op, 0.0, mode=255)
        self.assertAlmostEqual(heard(op, 0.1, mode=0)[0], 1.8)

    def test_a_press_from_before_taking_over_changes_nothing(self):
        op = operator()
        op.last = (0.0, {"forward": 0.0, "turn": 0.0, "live": True, "mode": 4})
        op.reset()
        self.assertAlmostEqual(heard(op, 0.1, mode=4)[0], 1.0)

    def test_taking_over_again_is_slow_again(self):
        op = operator()
        heard(op, 0.0, mode=0)
        heard(op, 0.1, mode=1)
        self.assertTrue(op.fast)
        op.reset()
        self.assertFalse(op.fast)
        self.assertAlmostEqual(heard(op, 0.2, mode=1)[0], 1.0)

    def test_turns_follow_the_mode_too(self):
        op = operator()
        heard(op, 0.0, turn=15.0, forward=0.0, mode=0)
        self.assertAlmostEqual(heard(op, 0.0, turn=15.0, forward=0.0)[1], 2.0)
        self.assertAlmostEqual(
            heard(op, 0.1, turn=-15.0, forward=0.0, mode=1)[1], -15.0
        )

    def test_fast_inside_the_diamond(self):
        op = operator()
        heard(op, 0.0, mode=0)
        speed, turn = heard(op, 0.1, forward=1.8, turn=15.0, mode=1)
        self.assertAlmostEqual(speed, 0.9)
        self.assertAlmostEqual(turn, 7.5)

    def test_slow_untouched_by_the_diamond(self):
        speed, turn = heard(operator(), 0.0, forward=1.8, turn=15.0)
        self.assertAlmostEqual(speed, 1.0)
        self.assertAlmostEqual(turn, 2.0)

    def test_fast_limits_can_be_set(self):
        op = operator(fast_speed=1.5, fast_turn=6.0)
        heard(op, 0.0, mode=0)
        self.assertAlmostEqual(heard(op, 0.1, mode=1)[0], 1.5)

    def test_nothing_past_the_trained_range_unless_asked(self):
        op = operator(fast_speed=3.0)
        heard(op, 0.0, mode=0)
        self.assertAlmostEqual(heard(op, 0.1, mode=1)[0], 1.8)

    def test_a_controller_with_no_mode_still_drives(self):
        op = operator()
        op.last = (0.0, {"forward": 1.8, "turn": 0.0, "live": True})
        self.assertAlmostEqual(op.wanted(0.0)[0], 1.0)

    def test_stale_still_stops_it_whatever_the_mode(self):
        op = operator()
        heard(op, 0.0, mode=0)
        heard(op, 0.1, mode=1)
        self.assertEqual(op.wanted(1.0), (0.0, 0.0))


class Ramps(unittest.TestCase):
    ramp = staticmethod(balance.Operator.ramp)

    def test_speeding_up_at_the_gentle_rate(self):
        self.assertAlmostEqual(self.ramp(0.0, 1.0, 0.6, 1.5, 0.01), 0.006)
        self.assertAlmostEqual(self.ramp(-0.5, -1.0, 0.6, 1.5, 0.01), -0.506)

    def test_slowing_at_the_braking_rate(self):
        self.assertAlmostEqual(self.ramp(1.0, 0.0, 0.6, 1.5, 0.01), 0.985)
        self.assertAlmostEqual(self.ramp(-1.0, -0.5, 0.6, 1.5, 0.01), -0.985)

    def test_reversing_brakes_to_nought_then_speeds_up(self):
        self.assertAlmostEqual(self.ramp(1.0, -1.0, 0.6, 1.5, 0.01), 0.985)
        self.assertAlmostEqual(self.ramp(0.01, -1.0, 0.6, 1.5, 0.01), -0.006)
        self.assertAlmostEqual(self.ramp(0.0, -1.0, 0.6, 1.5, 0.01), -0.006)

    def test_it_reaches_what_is_wanted(self):
        self.assertAlmostEqual(self.ramp(0.004, 0.0, 0.6, 1.5, 0.01), 0.0)
        self.assertAlmostEqual(self.ramp(0.998, 1.0, 0.6, 1.5, 0.01), 1.0)

    def test_letting_go_from_full_speed_stops_in_the_time_it_should(self):
        v, t = 1.8, 0.0
        while v > 0.0:
            v = self.ramp(v, 0.0, 0.6, 1.5, 0.01)
            t += 0.01
        self.assertAlmostEqual(t, 1.2, places=1)


if __name__ == "__main__":
    unittest.main()
