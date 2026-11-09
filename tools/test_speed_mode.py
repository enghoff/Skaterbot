# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "pyserial>=3.5"]
# ///
"""sbc/balance.py's Operator: the controller's select button toggling the speed limits, and
the diamond an envelope policy was trained inside. Free, offline, no robot.

    uv run tools/test_speed_mode.py
"""

from __future__ import annotations

import json
import sys
import tempfile
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


class HeightOnTakingOver(unittest.TestCase):
    """The crouch's height first, whatever is asked, then the D-pad's rate: the D-pad's
    low height kept from the run before folded D5's knees under the owner's hand on
    2026-11-06."""

    def ride(self, op, height, seconds, t0=0.0):
        t, seen = t0, []
        while t < t0 + seconds - 1e-9:
            op.last = (t, {"forward": 0.0, "turn": 0.0, "live": True, "height": height})
            seen.append((t, op.ask(t)[2]))
            t += 0.01
        return seen

    def test_it_starts_at_the_crouch_whatever_is_asked(self):
        op = operator()
        seen = self.ride(op, 0.17, op.HEIGHT_HOLD_S - 0.01)
        self.assertTrue(all(h == META["default_height"] for _, h in seen))

    def test_then_it_goes_down_at_the_dpads_rate(self):
        op = operator()
        seen = self.ride(op, 0.17, op.HEIGHT_HOLD_S + 1.0)
        self.assertAlmostEqual(seen[-1][1], 0.2035 - 0.025 * 1.0, places=6)
        steps = [a[1] - b[1] for a, b in zip(seen, seen[1:])]
        self.assertLessEqual(max(steps), 0.025 * 0.01 + 1e-12)

    def test_it_gets_there_and_stays(self):
        op = operator()
        seen = self.ride(op, 0.17, op.HEIGHT_HOLD_S + 2.0)
        self.assertAlmostEqual(seen[-1][1], 0.17)
        self.assertTrue(all(h >= 0.17 for _, h in seen))

    def test_up_again_at_the_same_rate(self):
        op = operator()
        self.ride(op, 0.17, op.HEIGHT_HOLD_S + 2.0)
        seen = self.ride(op, 0.207, 0.5, t0=op.HEIGHT_HOLD_S + 2.0)
        self.assertAlmostEqual(seen[-1][1], 0.17 + 0.025 * 0.5, places=6)

    def test_taking_over_again_starts_at_the_crouch_again(self):
        op = operator()
        self.ride(op, 0.17, op.HEIGHT_HOLD_S + 2.0)
        op.reset()
        seen = self.ride(op, 0.17, 1.0, t0=10.0)
        self.assertTrue(all(h == META["default_height"] for _, h in seen))

    def test_a_height_from_the_command_line_is_gone_to_the_same_way(self):
        op = operator(height=0.18)
        t = 0.0
        while t < op.HEIGHT_HOLD_S - 1e-9:
            self.assertEqual(op.ask(t)[2], 0.2035)
            t += 0.01
        while t < op.HEIGHT_HOLD_S + 2.0:
            h = op.ask(t)[2]
            t += 0.01
        self.assertAlmostEqual(h, 0.18)

    def test_a_height_past_the_trained_range_is_held_to_it(self):
        op = operator()
        seen = self.ride(op, 0.155, op.HEIGHT_HOLD_S + 3.0)
        self.assertAlmostEqual(seen[-1][1], META["height_range"][0])


class Sideways(unittest.TestCase):
    """Speed times turn held under SIDEWAYS_M_S2, on what is being done, not asked."""

    def drive(self, op, forward, turn, seconds, t0=0.0):
        t = t0
        top = 0.0
        while t < t0 + seconds:
            op.last = (t, {"forward": forward, "turn": turn, "live": True, "mode": 1})
            speed, yaw, _ = op.ask(t)
            top = max(top, abs(speed * yaw))
            t += 0.01
        return speed, yaw, top

    def fast(self):
        op = operator()
        heard(op, 0.0, mode=0)
        heard(op, 0.0, mode=1)
        return op

    def test_a_hard_turn_at_speed_gives_way(self):
        op = self.fast()
        self.drive(op, 1.8 * 0.6, 0.0, 3.0)
        speed, yaw, top = self.drive(op, 1.8 * 0.6, 15.0, 3.0, t0=3.0)
        self.assertLessEqual(top, op.SIDEWAYS_M_S2 + 1e-9)
        self.assertAlmostEqual(abs(speed * yaw), op.SIDEWAYS_M_S2, places=6)

    def test_the_speed_is_kept(self):
        op = self.fast()
        before, _, _ = self.drive(op, 1.0, 0.0, 4.0)
        speed, _, _ = self.drive(op, 1.0, 6.0, 2.0, t0=4.0)
        self.assertAlmostEqual(speed, before)

    def test_turning_on_the_spot_untouched(self):
        op = self.fast()
        speed, yaw, _ = self.drive(op, 0.0, 15.0, 6.0)
        self.assertEqual(speed, 0.0)
        self.assertAlmostEqual(yaw, 15.0)

    def test_still_rolling_after_letting_go_counts(self):
        op = self.fast()
        self.drive(op, 1.8, 0.0, 4.0)
        _, _, top = self.drive(op, 0.0, 15.0, 1.5, t0=4.0)
        self.assertLessEqual(top, op.SIDEWAYS_M_S2 + 1e-9)

    def test_slow_mode_never_reaches_it(self):
        op = operator()
        _, _, top = self.drive(op, 1.8, 15.0, 5.0)
        self.assertLessEqual(top, 1.0 * 2.0 + 1e-9)


class Spinning(unittest.TestCase):
    """The speed asked times the body's measured turn held under SPINNING_M_S2: D8's
    fall of 2026-11-07, the turn let go at 1.29 m/s with the body still at 4 rad/s."""

    def drive(self, op, forward, turn, spin, seconds, t0=0.0):
        t = t0
        speeds = []
        while t < t0 + seconds:
            op.last = (t, {"forward": forward, "turn": turn, "live": True, "mode": 1})
            speed, _, _ = op.ask(t, spin)
            speeds.append(speed)
            t += 0.01
        return speeds

    def at_speed(self):
        op = operator()
        heard(op, 0.0, mode=0)
        heard(op, 0.0, mode=1)
        self.drive(op, 1.29, 0.0, 0.0, 4.0)
        return op

    def test_still_spinning_after_the_turn_is_let_go_brakes(self):
        op = self.at_speed()
        speeds = self.drive(op, 1.29, 0.0, 4.0, 1.0, t0=4.0)
        self.assertAlmostEqual(speeds[-1], op.SPINNING_M_S2 / 4.0)
        # At the braking rate, not a step.
        steps = [a - b for a, b in zip(speeds, speeds[1:])]
        self.assertLessEqual(max(steps), op.STOP_RAMP_M_S2 * 0.01 + 1e-9)

    def test_it_does_not_climb_back_while_spinning(self):
        op = self.at_speed()
        self.drive(op, 1.29, 0.0, 4.0, 1.0, t0=4.0)
        speeds = self.drive(op, 1.0, 0.0, 4.0, 1.0, t0=5.0)
        self.assertLessEqual(max(speeds), op.SPINNING_M_S2 / 4.0 + 1e-9)

    def test_back_up_at_the_gentle_rate_once_it_stops(self):
        op = self.at_speed()
        self.drive(op, 1.29, 0.0, 4.0, 1.0, t0=4.0)
        speeds = self.drive(op, 1.29, 0.0, 0.0, 0.5, t0=5.0)
        rises = [b - a for a, b in zip(speeds, speeds[1:])]
        self.assertLessEqual(max(rises), op.SPEED_RAMP_M_S2 * 0.01 + 1e-9)
        self.assertGreater(speeds[-1], speeds[0])

    def test_backwards_too(self):
        op = self.at_speed()
        self.drive(op, -1.29, 0.0, 0.0, 6.0, t0=4.0)
        speeds = self.drive(op, -1.29, 0.0, 4.0, 1.0, t0=10.0)
        self.assertAlmostEqual(speeds[-1], -op.SPINNING_M_S2 / 4.0)

    def test_driving_straight_untouched(self):
        op = self.at_speed()
        speeds = self.drive(op, 1.29, 0.0, 0.1, 1.0, t0=4.0)
        self.assertAlmostEqual(speeds[-1], 1.29)


class TheReverseCap(unittest.TestCase):
    """A full pull backwards, under what forwards asks: at 2.2 m/s it went over on
    2026-11-09 with the wheels at their top."""

    def fast(self, **changes) -> balance.Operator:
        op = operator(fast_speed=1.8, fast_turn=6.0, **changes)
        heard(op, 0.0, mode=0)
        heard(op, 0.1, mode=1)
        return op

    def test_a_full_pull_backwards_is_the_cap(self):
        self.assertAlmostEqual(
            heard(self.fast(fast_reverse=1.2), 0.2, forward=-1.8, mode=1)[0], -1.2
        )

    def test_forwards_keeps_its_own_limit(self):
        self.assertAlmostEqual(
            heard(self.fast(fast_reverse=1.2), 0.2, forward=1.8, mode=1)[0], 1.8
        )

    def test_a_part_pull_is_its_share_of_the_cap(self):
        self.assertAlmostEqual(
            heard(self.fast(fast_reverse=1.2), 0.2, forward=-0.9, mode=1)[0], -0.6
        )

    def test_slow_mode_under_the_cap_is_untouched(self):
        self.assertAlmostEqual(
            heard(operator(fast_reverse=1.2), 0.0, forward=-1.8)[0], -1.0
        )

    def test_none_set_it_is_the_same_both_ways(self):
        self.assertAlmostEqual(heard(self.fast(), 0.2, forward=-1.8, mode=1)[0], -1.8)


class TheTurnLearned(unittest.TestCase):
    """policy_loop.py's Trim: what the gyro says of the turn is learned whatever the speed
    asked is doing, and what going straight needs is kept, by how fast it is rolling."""

    DT = 0.01

    def setUp(self):
        self.trim = balance.pl.Trim(0.04)

    def go(self, seconds, speed=1.5, turn=0.0, yawing=0.087, rolling=None):
        """speed may be a function of time; rolling is what the wheels say, the speed by
        default."""
        out = (0.0, 0.0)
        for i in range(max(1, round(seconds / self.DT))):
            v = speed(i * self.DT) if callable(speed) else speed
            r = v if rolling is None else rolling
            fb = {j: SimpleNamespace(v=0.0) for j in balance.st.JOINTS}
            for wheel in ("wheel_drive_right", "wheel_drive_left"):
                fb[wheel].v = r / 0.04
            out = self.trim.command(
                v, turn, fb, (0.0, 0.0, yawing), (0.0, 0.0, -1.0), self.DT
            )
        return out

    @staticmethod
    def ramp(t):
        return 0.5 + 0.6 * t

    def test_the_turn_is_learned_while_the_speed_ramps(self):
        self.assertLess(self.go(1.5, self.ramp, rolling=1.5)[1], -0.05)

    def test_it_steers_against_the_yaw(self):
        self.assertLess(self.go(1.5)[1], 0.0)
        self.trim = balance.pl.Trim(0.04)
        self.assertGreater(self.go(1.5, yawing=-0.087)[1], 0.0)

    def test_the_speed_still_waits_for_a_steady_speed(self):
        self.go(1.5, self.ramp)
        self.assertEqual(self.trim.speed, 0.0)

    def test_nothing_is_learned_for_the_first_half_second(self):
        self.assertEqual(self.go(0.4, self.ramp)[1], 0.0)

    def test_a_touch_of_the_stick_keeps_what_was_learned(self):
        learned = self.go(2.0)[1]
        self.go(0.3, turn=-0.8, yawing=-0.5)
        self.assertAlmostEqual(self.go(self.DT, yawing=0.0)[1], learned, delta=0.03)

    def test_it_is_kept_by_speed(self):
        learned = self.go(2.0)[1]
        self.assertLess(learned, -0.05)
        self.assertEqual(self.go(self.DT, speed=0.5, yawing=0.0)[1], 0.0)

    def test_between_two_speeds_it_is_in_proportion(self):
        learned = self.go(2.0)[1]
        at = self.go(self.DT, speed=1.375, yawing=0.0)[1]
        self.assertAlmostEqual(at, learned / 2.0, delta=0.01)

    def test_faster_speeds_not_reached_yet_carry_it(self):
        learned = self.go(2.0, speed=1.0)[1]
        self.assertAlmostEqual(self.go(self.DT, speed=1.75, yawing=0.0)[1], learned)

    def test_backwards_the_same_way_out(self):
        learned = self.go(2.0, speed=-0.5)[1]
        self.assertLess(learned, -0.05)
        self.assertAlmostEqual(self.go(self.DT, speed=-1.5, yawing=0.0)[1], learned)
        self.assertEqual(self.go(self.DT, speed=1.5, yawing=0.0)[1], 0.0)

    def test_a_speed_learned_keeps_its_own(self):
        self.go(2.0, speed=1.0)
        first = self.go(self.DT, speed=1.75, yawing=0.0)[1]
        self.go(2.0, speed=1.75, yawing=-0.087)
        again = self.go(self.DT, speed=1.0, yawing=0.0)[1]
        self.assertAlmostEqual(again, first, delta=0.002)

    def test_a_stop_and_a_jump_leave_it(self):
        learned = self.go(2.0)[1]
        self.assertEqual(self.go(self.DT, speed=0.0), (0.0, 0.0))
        self.trim.reset()
        self.assertAlmostEqual(self.go(self.DT, yawing=0.0)[1], learned, delta=0.01)

    def test_going_straight_it_is_held_small(self):
        self.go(6.0, yawing=0.4)
        self.assertAlmostEqual(self.go(self.DT)[1], -self.trim.MAX_STRAIGHT_RAD_S)

    def test_a_shove_is_not_remembered(self):
        self.go(2.0, yawing=1.0)
        self.assertEqual(self.go(self.DT, yawing=0.0)[1], 0.0)

    def test_nothing_is_learned_at_a_crawl(self):
        self.go(2.0, speed=0.2)
        self.assertEqual(self.go(self.DT, speed=1.5, yawing=0.0)[1], 0.0)

    def test_steering_steadily_it_has_the_wider_limit(self):
        self.go(5.0, turn=1.0, yawing=5.0)
        self.assertAlmostEqual(self.trim.turn, -self.trim.MAX_TURN_RAD_S)

    def test_centring_the_stick_brings_it_inside_at_once(self):
        self.go(5.0, turn=1.0, yawing=5.0)
        self.go(self.DT, turn=0.0)
        self.assertLessEqual(abs(self.trim.turn), self.trim.MAX_STRAIGHT_RAD_S)

    def test_steering_learns_nothing_for_going_straight(self):
        self.go(3.0, turn=1.0, yawing=0.2)
        self.assertEqual(self.go(self.DT, yawing=0.0)[1] - self.trim.turn, 0.0)


class TheStraightKept(unittest.TestCase):
    """What going straight needs, carried from one run to the next by a file: used when it
    is what was kept, and otherwise as if there were none, since a file must neither stop a
    run nor steer it."""

    DT = 0.01
    go = TheTurnLearned.go

    def setUp(self):
        self.trim = balance.pl.Trim(0.04)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.file = Path(folder.name) / "kept.json"

    def keep(self, policy="D8"):
        return balance.keep_straight(self.trim, self.file, policy)

    def next_run(self, policy="D8"):
        """The next run's Trim, as self.trim, and what became of the file."""
        self.trim = balance.pl.Trim(0.04)
        return balance.recall_straight(self.trim, self.file, policy)

    def blank(self):
        return not (self.trim.straight.any() or self.trim.known.any())

    def learned_and_kept(self):
        self.go(3.0)
        self.keep()

    def test_the_next_run_starts_with_it(self):
        self.go(3.0)
        learned = self.go(self.DT, yawing=0.0)[1]
        self.assertLess(learned, -0.05)
        self.keep()
        self.assertIn("recalled", self.next_run())
        self.assertAlmostEqual(self.go(self.DT, yawing=0.0)[1], learned, places=2)

    def test_it_adapts_when_the_pull_has_changed(self):
        self.learned_and_kept()
        self.next_run()
        before = self.go(self.DT, yawing=0.0)[1]
        self.assertLess(before, -0.05)
        # The pull now the other way: what was carried is learned away.
        self.assertGreater(self.go(3.0, yawing=-0.087)[1], before + 0.05)

    def test_a_changed_pull_is_kept_for_the_run_after(self):
        self.learned_and_kept()
        self.next_run()
        first = self.go(self.DT, yawing=0.0)[1]
        self.go(3.0, yawing=-0.087)
        self.keep()
        self.next_run()
        self.assertGreater(self.go(self.DT, yawing=0.0)[1], first + 0.05)

    def test_what_was_known_stays_known(self):
        self.learned_and_kept()
        self.next_run()
        at_1_5 = self.trim.straight[self.trim.at == 1.5][0]
        self.go(2.0, speed=1.0, rolling=1.0)
        self.assertEqual(self.trim.straight[self.trim.at == 1.5][0], at_1_5)

    def test_standing_still_it_asks_for_nothing(self):
        self.learned_and_kept()
        self.next_run()
        self.assertEqual(self.go(self.DT, speed=0.0), (0.0, 0.0))

    def test_no_file_is_a_fresh_start(self):
        self.assertEqual(self.next_run(), "nothing kept yet")
        self.assertTrue(self.blank())

    def test_a_damaged_file_is_a_fresh_start(self):
        for text in (
            "",
            "{",
            "[]",
            "null",
            "3",
            '{"at": 1}',
            '{"at": [1], "straight": 2}',
        ):
            self.file.write_text(text)
            self.assertIn("not used", self.next_run(), text)
            self.assertTrue(self.blank(), text)

    def test_unreadable_bytes_are_a_fresh_start(self):
        self.file.write_bytes(b"\xff\xfe\x00")
        self.assertIn("not used", self.next_run())
        self.assertTrue(self.blank())

    def changed(self, **fields):
        self.learned_and_kept()
        kept = json.loads(self.file.read_text())
        kept.update(fields)
        self.file.write_text(json.dumps(kept))
        said = self.next_run()
        self.assertIn("not used", said)
        self.assertTrue(self.blank(), said)

    def test_another_policys_is_not_used(self):
        self.learned_and_kept()
        self.assertIn("not used", self.next_run("D9"))
        self.assertTrue(self.blank())

    def test_other_speeds_are_not_used(self):
        self.changed(at=[s + 0.1 for s in balance.pl.Trim.STRAIGHT_AT_M_S])

    def test_the_wrong_length_is_not_used(self):
        self.changed(straight=[0.0, 0.0], known=[False, False])

    def test_past_the_cap_is_not_used(self):
        n = len(balance.pl.Trim.STRAIGHT_AT_M_S)
        self.changed(straight=[0.21] * n)

    def test_not_a_number_is_not_used(self):
        n = len(balance.pl.Trim.STRAIGHT_AT_M_S)
        self.changed(straight=[float("nan")] * n)

    def test_a_run_that_learned_nothing_leaves_the_file_alone(self):
        self.learned_and_kept()
        before = self.file.read_bytes()
        self.next_run()
        self.assertEqual(self.keep(), "nothing new to keep")
        self.assertEqual(self.file.read_bytes(), before)

    def test_a_crawl_learns_nothing_to_keep(self):
        self.go(3.0, speed=0.1)
        self.assertEqual(self.keep(), "nothing new to keep")
        self.assertFalse(self.file.exists())

    def test_nowhere_to_write_says_so_and_goes_on(self):
        self.go(3.0)
        self.file = self.file.parent / "not there" / "kept.json"
        self.assertIn("could not keep", self.keep())

    def test_nothing_is_left_half_written(self):
        self.learned_and_kept()
        self.assertEqual([p.name for p in self.file.parent.iterdir()], ["kept.json"])


if __name__ == "__main__":
    unittest.main()
