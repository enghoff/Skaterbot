# /// script
# requires-python = ">=3.11"
# dependencies = ["aiohttp>=3.9,<4", "pyserial>=3.5"]
# ///
"""The game controller: what it asks for, pairing it, and the path to the policy.

    uv run tools/test_gamepad.py

No Bluetooth and no controller: real bluetoothctl output is stood in for by what
Tool returns here, and tools/test_gamepad_linux.py holds the real thing to it.
"""

import asyncio
import contextlib
import json
import os
import re
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sbc"))
import console_bluetooth as cb  # noqa: E402
import diag_client  # noqa: E402
import diag_link as dl  # noqa: E402
import diag_sim  # noqa: E402
import diagd  # noqa: E402
import gamepad as gp  # noqa: E402

PLAYSTATION = {
    gp.ABS_X: (0, 255),
    gp.ABS_Y: (0, 255),
    gp.ABS_Z: (0, 255),  # a trigger, on this one
    gp.ABS_RX: (0, 255),
    gp.ABS_RZ: (0, 255),
    gp.ABS_HAT0Y: (-1, 1),
}
ON_GENERIC_HID = {
    gp.ABS_X: (0, 65535),
    gp.ABS_Y: (0, 65535),
    gp.ABS_Z: (0, 65535),  # the right stick, on this one
    gp.ABS_RZ: (0, 65535),
}


GAS, BRAKE = gp.ABS_RZ, gp.ABS_Z  # on PLAYSTATION
JUMP = gp.BTN_SOUTH  # on PLAYSTATION, through the generic driver


def ready(ranges=PLAYSTATION, now=0.0):
    operator = gp.Operator(ranges, now)
    operator.command(now)
    return operator


class OperatorTests(unittest.TestCase):
    def test_nothing_is_asked_of_a_controller_left_alone(self):
        operator = gp.Operator(PLAYSTATION, 0.0)
        command = operator.command(0.0)
        self.assertEqual((command["forward"], command["turn"]), (0.0, 0.0))
        self.assertEqual(operator.why_not(0.0), "")

    def test_nor_by_the_left_stick_up_or_a_shoulder(self):
        operator = ready()
        operator.event(gp.EV_KEY, gp.BTN_TL, 1, 0.0)
        operator.event(gp.EV_ABS, gp.ABS_Y, 0, 0.0)
        command = operator.command(0.0)
        self.assertEqual((command["forward"], command["turn"]), (0.0, 0.0))

    def test_gas_is_forward_brake_is_back_and_left_is_a_positive_turn(self):
        # POLICY_INTERFACE.md: index 6 forward, index 7 positive to the left.
        operator = ready()
        operator.event(gp.EV_ABS, GAS, 255, 0.0)
        operator.event(gp.EV_ABS, gp.ABS_X, 0, 0.0)
        command = operator.command(0.0)
        self.assertAlmostEqual(command["forward"], gp.START_SPEED_M_S)
        self.assertAlmostEqual(command["turn"], gp.START_TURN_RAD_S)
        self.assertTrue(command["live"])
        operator.event(gp.EV_ABS, GAS, 0, 0.1)
        operator.event(gp.EV_ABS, BRAKE, 255, 0.1)
        self.assertAlmostEqual(operator.command(0.1)["forward"], -gp.START_SPEED_M_S)

    def test_how_far_a_trigger_is_pulled_is_how_fast(self):
        operator = ready()
        operator.event(gp.EV_ABS, GAS, round(0.1 * 255), 0.0)
        self.assertEqual(operator.command(0.0)["forward"], 0.0)
        operator.event(gp.EV_ABS, GAS, round(0.56 * 255), 0.0)
        want = gp.START_SPEED_M_S * (0.56 - 0.12) / (1 - 0.12)
        self.assertAlmostEqual(operator.command(0.0)["forward"], want, places=2)

    def test_both_triggers_together_ask_for_nothing(self):
        operator = ready()
        operator.event(gp.EV_ABS, GAS, 255, 0.0)
        operator.event(gp.EV_ABS, BRAKE, 255, 0.0)
        self.assertEqual(operator.command(0.0)["forward"], 0.0)

    def test_letting_go_brings_it_to_zero_at_once(self):
        operator = ready()
        operator.event(gp.EV_ABS, GAS, 255, 0.0)
        self.assertGreater(operator.command(0.0)["forward"], 0)
        operator.event(gp.EV_ABS, GAS, 0, 0.1)
        self.assertEqual(operator.command(0.1)["forward"], 0.0)

    def test_a_trigger_already_pulled_asks_for_nothing_until_let_go_of(self):
        operator = gp.Operator(PLAYSTATION, 0.0, values={GAS: 255})
        command = operator.command(0.0)
        self.assertEqual((command["forward"], command["live"]), (0.0, True))
        self.assertIn("rest", operator.why_not(0.0))
        operator.event(gp.EV_ABS, GAS, 0, 0.1)
        operator.command(0.1)
        operator.event(gp.EV_ABS, GAS, 255, 0.2)
        self.assertAlmostEqual(operator.command(0.2)["forward"], gp.START_SPEED_M_S)

    def test_a_stick_already_pushed_asks_for_nothing_until_it_has_been_centred(self):
        operator = gp.Operator(PLAYSTATION, 0.0, values={gp.ABS_X: 0})
        self.assertEqual(operator.command(0.0)["turn"], 0.0)
        self.assertIn("rest", operator.why_not(0.0))
        operator.event(gp.EV_ABS, gp.ABS_X, 128, 0.1)
        operator.command(0.1)
        operator.event(gp.EV_ABS, gp.ABS_X, 0, 0.2)
        self.assertAlmostEqual(operator.command(0.2)["turn"], gp.START_TURN_RAD_S)

    def test_a_quick_pull_after_a_long_idle_counts(self):
        operator = ready()
        later = 100.0
        self.assertEqual(operator.why_not(later), "")
        operator.command(later)
        operator.event(gp.EV_ABS, GAS, 255, later)
        self.assertAlmostEqual(operator.command(later)["forward"], gp.START_SPEED_M_S)

    def test_a_trigger_taken_for_a_stick_cannot_drive(self):
        # Where this kernel's generic driver would have put a PlayStation
        # controller's left trigger, which a driver of its own has as the right
        # stick: at rest it reads as that stick pushed hard over, and that must not
        # spin the robot.
        operator = gp.Operator(
            {gp.ABS_Y: (0, 255), gp.ABS_RX: (0, 255)},
            0.0,
            values={gp.ABS_Y: 128, gp.ABS_RX: 0},
        )
        self.assertEqual(operator.command(0.0)["turn"], 0.0)
        self.assertEqual(operator.command(0.1)["turn"], 0.0)

    def test_the_left_stick_turns_on_either_layout_and_the_right_does_not(self):
        for ranges, right in ((PLAYSTATION, gp.ABS_RX), (ON_GENERIC_HID, gp.ABS_Z)):
            operator = ready(ranges)
            self.assertEqual(operator.layout.turn, gp.ABS_X)
            high = ranges[gp.ABS_X][1]
            operator.event(gp.EV_ABS, right, high, 0.0)
            self.assertEqual(operator.command(0.0)["turn"], 0.0)
            operator.event(gp.EV_ABS, gp.ABS_X, high, 0.0)
            want = -gp.START_TURN_RAD_S
            self.assertAlmostEqual(operator.command(0.0)["turn"], want)

    def test_a_trigger_is_not_taken_for_the_turn(self):
        operator = ready()
        operator.event(gp.EV_ABS, gp.ABS_Z, 255, 0.0)
        self.assertEqual(operator.command(0.0)["turn"], 0.0)

    def test_the_dead_zone_matches_the_simulator(self):
        operator = ready()
        # 0.1 of the way: inside the driver's 0.12.
        operator.event(gp.EV_ABS, gp.ABS_X, round(127.5 - 12.75), 0.0)
        self.assertEqual(operator.command(0.0)["turn"], 0.0)
        # Half way: rescaled from the zone's edge, as drive.py's axis() does.
        operator.event(gp.EV_ABS, gp.ABS_X, round(127.5 - 63.75), 0.0)
        want = (0.5 - 0.12) / (1 - 0.12)
        turn = operator.command(0.0)["turn"] / gp.START_TURN_RAD_S
        self.assertAlmostEqual(turn, want, places=2)

    def test_a_control_held_still_goes_on_counting_however_long(self):
        # It has nothing to report: a held turn stopped after two revolutions.
        for gas, stick in ((255, 0), (128, 64)):
            operator = ready(now=0.0)
            operator.event(gp.EV_ABS, GAS, gas, 0.0)
            operator.event(gp.EV_ABS, gp.ABS_X, stick, 0.0)
            first = operator.command(0.0)
            command = operator.command(600.0)
            self.assertTrue(command["live"])
            self.assertGreater(command["forward"], 0.0)
            self.assertEqual(command["forward"], first["forward"])
            self.assertEqual(command["turn"], first["turn"])
            self.assertEqual(operator.why_not(600.0), "")

    def test_a_key_repeating_is_not_a_press(self):
        operator = ready()
        operator.event(gp.EV_KEY, gp.BTN_SOUTH, 1, 0.0)
        operator.event(gp.EV_KEY, gp.BTN_SOUTH, 2, 0.1)
        self.assertEqual(operator.jump, 1)

    def jumps(self, events, start: int = 0) -> list[int]:
        """What "jump" says after each of these A events, None a frame with none, from
        `start` presses."""
        operator = ready()
        operator.jump = start
        sent = []
        for value in events:
            if value is not None:
                operator.event(gp.EV_KEY, gp.BTN_SOUTH, value, 0.0)
            sent.append(operator.command(0.0)["jump"])
        return sent

    def test_the_jump_button_held_sets_bit_8_over_the_count(self):
        held = gp.JUMP_HELD
        self.assertEqual(
            self.jumps([1, 2, None, 0, 1, 0]),
            [1 | held, 1 | held, 1 | held, 1, 2 | held, 2],
        )

    def test_a_tap_inside_a_frame_is_a_press_without_the_bit(self):
        operator = ready()
        operator.event(gp.EV_KEY, gp.BTN_SOUTH, 1, 0.0)
        operator.event(gp.EV_KEY, gp.BTN_SOUTH, 0, 0.0)
        self.assertEqual(operator.command(0.0)["jump"], 1)

    def test_only_the_jump_button_sets_it(self):
        operator = ready()
        for code in range(0x130, 0x140):
            if code != gp.BTN_SOUTH:
                operator.event(gp.EV_KEY, code, 1, 0.0)
        self.assertEqual(operator.command(0.0)["jump"], 0)

    def test_a_balance_from_before_counts_one_jump_a_press_and_none_a_let_go(self):
        """balance.py's Operator until 8 November 2026 (196e59a) counted the jump as
        this, which a robot not yet updated still runs: the change modulo 256."""

        def old_balance(values) -> int:
            presses, jumps = 0, None
            for jump in values:
                if jumps is not None:
                    presses += (int(jump) - jumps) % 256
                jumps = int(jump)
            return presses

        press, hold, let_go = 1, 2, 0
        once = [press, hold, hold, None, let_go, None]
        # From the frame before the first press.
        self.assertEqual(old_balance([0, *self.jumps(once)]), 1)
        self.assertEqual(old_balance([0, *self.jumps(once * 3)]), 3)
        # Through the count's wrap past 255.
        sent = self.jumps(once * 2, start=254)
        self.assertIn(0 | gp.JUMP_HELD, sent)
        self.assertEqual(old_balance([254, *sent]), 2)
        # Taking over while it is held, and then let go of: nothing.
        self.assertEqual(old_balance(self.jumps(once)[1:]), 0)

    def test_no_button_changes_what_is_asked(self):
        operator = ready()
        operator.event(gp.EV_ABS, GAS, 255, 0.0)
        for code in range(0x130, 0x140):
            if code != gp.BTN_SOUTH:
                operator.event(gp.EV_KEY, code, 1, 0.0)
        command = operator.command(0.0)
        self.assertTrue(command["live"])
        self.assertAlmostEqual(command["forward"], gp.START_SPEED_M_S)

    def full_stick_both_ways(self):
        operator = ready()
        operator.speed_limit, operator.turn_limit = gp.TOP_SPEED_M_S, gp.TOP_TURN_RAD_S
        operator.event(gp.EV_ABS, GAS, 255, 0.0)
        operator.event(gp.EV_ABS, gp.ABS_X, 0, 0.0)
        return operator.command(0.0)

    def test_select_is_counted_as_the_speed_mode(self):
        operator = ready()
        self.assertEqual(operator.command(0.0)["mode"], 0)
        for _ in range(2):
            operator.event(gp.EV_KEY, gp.BTN_SELECT, 1, 0.0)
            operator.event(gp.EV_KEY, gp.BTN_SELECT, 2, 0.0)
            operator.event(gp.EV_KEY, gp.BTN_SELECT, 0, 0.0)
        command = operator.command(0.1)
        self.assertEqual(command["mode"], 2)
        self.assertEqual(command["jump"], 0)

    def test_the_driving_policy_takes_full_speed_and_turn_together(self):
        # Its run has no command_envelope: each was trained over its whole range.
        command = self.full_stick_both_ways()
        self.assertAlmostEqual(command["forward"], gp.TOP_SPEED_M_S)
        self.assertAlmostEqual(command["turn"], gp.TOP_TURN_RAD_S)

    def test_an_envelope_policy_shares_the_wheels_between_them(self):
        with patch.object(gp, "ENVELOPE", True):
            command = self.full_stick_both_ways()
        self.assertAlmostEqual(command["forward"], gp.TOP_SPEED_M_S / 2, places=2)
        self.assertAlmostEqual(command["turn"], gp.TOP_TURN_RAD_S / 2, places=2)

    def test_the_ranges_are_the_deployed_runs(self):
        run = "rough-2026-11-07_11-52-47_d8"
        path = (
            Path(__file__).resolve().parents[1] / "exports/rl" / run / "params/env.yaml"
        )
        if not path.exists():
            self.skipTest(f"{run} is not here")
        text = path.read_text()

        def pair(name):
            found = re.search(
                rf"^{name}:(?: !!python/tuple)?\n- (.+)\n- (.+)$", text, re.M
            )
            return float(found[1]), float(found[2])

        self.assertEqual(
            pair("command_lin_vel_x"), (-gp.TOP_SPEED_M_S, gp.TOP_SPEED_M_S)
        )
        # To the thousandth a command is sent to: D6's task has 25.0998.
        for task, here in zip(
            pair("command_yaw_rate"), (-gp.TOP_TURN_RAD_S, gp.TOP_TURN_RAD_S)
        ):
            self.assertAlmostEqual(task, here, places=3)
        # The floor is the task's; the top is held at the crouch the run was trained
        # from, inside the task's own top, since D7 swayed standing above it.
        low, high = pair("command_leg_height_m")
        self.assertEqual(gp.HEIGHT_RANGE_M[0], low)
        self.assertLessEqual(gp.HEIGHT_RANGE_M[1], high)
        self.assertNotIn("command_envelope: true", text)
        height = re.search(r"^default_leg_height_m: (.+)$", text, re.M)
        self.assertAlmostEqual(float(height[1]), gp.DEFAULT_HEIGHT_M, places=3)
        self.assertAlmostEqual(gp.HEIGHT_RANGE_M[1], gp.DEFAULT_HEIGHT_M, places=4)

    def test_leg_height_moves_with_the_dpad_and_stays_in_range(self):
        operator = ready()
        operator.event(gp.EV_ABS, gp.ABS_HAT0Y, -1, 0.0)  # up
        start = operator.command(0.0)["height"]
        self.assertAlmostEqual(start, gp.DEFAULT_HEIGHT_M)
        now = 0.0
        for _ in range(200):
            now += 0.02
            high = operator.command(now)["height"]
        self.assertEqual(high, gp.HEIGHT_RANGE_M[1])
        operator.event(gp.EV_ABS, gp.ABS_HAT0Y, 1, now)  # down
        for _ in range(500):
            now += 0.02
            low = operator.command(now)["height"]
        self.assertEqual(low, gp.HEIGHT_RANGE_M[0])

    def test_motion_sensors_and_touchpad_are_not_a_controller(self):
        sticks = {gp.ABS_X, gp.ABS_Y}
        self.assertTrue(gp.game_controller(sticks, {gp.BTN_SOUTH}))
        self.assertFalse(gp.game_controller(sticks, set()))
        self.assertFalse(gp.game_controller(sticks, {0x110}))
        self.assertFalse(gp.game_controller(set(), {gp.BTN_SOUTH}))

    def test_a_bitmap_is_read_as_linux_writes_it(self):
        self.assertEqual(gp.bits(bytes([0b101, 0, 0b1])), {0, 2, 16})

    def test_the_ioctls_are_linuxs(self):
        # EVIOCGID, EVIOCGNAME(256) and EVIOCGABS(ABS_Y), as a C program gets them.
        self.assertEqual(gp.eviocg(gp.EVIOCGID, 8), 0x80084502)
        self.assertEqual(gp.eviocg(gp.EVIOCGNAME_BASE, 256), 0x81004506)
        self.assertEqual(gp.eviocg(gp.EVIOCGABS_BASE + gp.ABS_Y, 24), 0x80184541)


class LayoutTests(unittest.TestCase):
    ALL_AXES = PLAYSTATION

    def test_a_controller_with_its_own_driver_is_named_for_position(self):
        layout = gp.layout_of(
            PLAYSTATION, [gp.BTN_SOUTH, gp.BTN_EAST, gp.BTN_TL], 0x054C
        )
        self.assertEqual(layout.turn, gp.ABS_X)
        self.assertEqual((layout.gas, layout.brake), (gp.ABS_RZ, gp.ABS_Z))
        self.assertEqual(layout.jump, gp.BTN_SOUTH)

    def test_a_playstation_controller_on_the_generic_driver(self):
        # What this kernel would make of one: Square, Cross, Circle, Triangle,
        # L1, R1, numbered from BTN_SOUTH; triggers on RX and RY.
        keys = range(gp.BTN_SOUTH, gp.BTN_SOUTH + 14)
        layout = gp.layout_of(PLAYSTATION, keys, gp.SONY)
        self.assertEqual(layout.jump, gp.BTN_EAST)  # Cross
        self.assertEqual((layout.gas, layout.brake), (gp.ABS_RY, gp.ABS_RX))
        self.assertEqual(layout.turn, gp.ABS_X)
        operator = gp.Operator(
            PLAYSTATION,
            0.0,
            layout,
            values={
                gp.ABS_X: 128,
                gp.ABS_Y: 128,
                gp.ABS_Z: 128,
                gp.ABS_RX: 0,
                gp.ABS_RZ: 128,
            },
        )
        self.assertEqual(operator.command(0.0)["turn"], 0.0)
        operator.event(gp.EV_ABS, gp.ABS_RX, 255, 0.1)  # L2 pulled
        self.assertEqual(operator.command(0.1)["turn"], 0.0)
        operator.event(gp.EV_ABS, gp.ABS_Z, 0, 0.2)  # right stick, left
        self.assertEqual(operator.command(0.2)["turn"], 0.0)
        operator.event(gp.EV_ABS, gp.ABS_X, 0, 0.2)  # left stick, left
        self.assertAlmostEqual(operator.command(0.2)["turn"], gp.START_TURN_RAD_S)
        operator.event(gp.EV_KEY, gp.BTN_EAST, 1, 0.3)  # Cross
        self.assertEqual(operator.jump, 1)

    def test_the_real_xbox_controller_as_the_robots_kernel_reports_it(self):
        # 045E:0B20, firmware 5.23, read on the Pi on 2026-11-04. It claims every
        # code from BTN_SOUTH up and KEY_RECORD; pressed one at a time, LB, RB, A,
        # B, X and Y sent 0x136, 0x137, 0x130, 0x131, 0x133 and 0x134.
        ranges = {
            axis: (0, 65535) for axis in (gp.ABS_X, gp.ABS_Y, gp.ABS_Z, gp.ABS_RZ)
        } | {9: (0, 1023), 10: (0, 1023), 0x10: (-1, 1), 0x11: (-1, 1)}
        rest = {gp.ABS_X: 31700, gp.ABS_Y: 33379, gp.ABS_Z: 31034, gp.ABS_RZ: 30605}
        layout = gp.layout_of(ranges, [*range(0x130, 0x13F), 167], gp.MICROSOFT)
        self.assertEqual((layout.gas, layout.brake), (9, 10))
        self.assertEqual(layout.turn, gp.ABS_X)
        self.assertEqual(layout.jump, 0x130)
        operator = gp.Operator(ranges, 0.0, layout, rest | {9: 0, 10: 0})
        # Its sticks at rest are in the dead zone, so they count from the start.
        self.assertEqual(operator.command(0.1)["forward"], 0.0)
        # A shoulder, which used to be held to drive, does nothing.
        operator.event(gp.EV_KEY, 0x136, 1, 0.1)
        self.assertEqual(operator.command(0.1)["forward"], 0.0)
        operator.event(gp.EV_KEY, 0x136, 0, 0.1)
        operator.event(gp.EV_ABS, 9, 1023, 0.2)
        operator.event(gp.EV_ABS, gp.ABS_X, 0, 0.2)
        command = operator.command(0.2)
        self.assertAlmostEqual(command["forward"], gp.TOP_SPEED_M_S)
        self.assertAlmostEqual(command["turn"], gp.TOP_TURN_RAD_S)
        operator.event(gp.EV_ABS, 9, 0, 0.3)
        operator.event(gp.EV_ABS, 10, 1023, 0.3)
        command = operator.command(0.3)
        self.assertAlmostEqual(command["forward"], -gp.TOP_SPEED_M_S)
        self.assertAlmostEqual(command["turn"], gp.TOP_TURN_RAD_S)

    def test_any_other_controller_numbered_straight_through(self):
        keys = range(gp.BTN_SOUTH, gp.BTN_SOUTH + 10)
        layout = gp.layout_of(ON_GENERIC_HID, keys, 0x057E)
        self.assertEqual((layout.gas, layout.brake), (None, None))
        self.assertIn(
            "no analog", gp.Operator(ON_GENERIC_HID, 0.0, layout).why_not(0.0)
        )
        self.assertEqual(layout.jump, gp.BTN_SOUTH)

    def test_what_is_held_is_named_by_what_it_does(self):
        operator = gp.Operator(PLAYSTATION, 0.0)
        operator.event(gp.EV_KEY, gp.BTN_TL, 1, 0.0)
        operator.event(gp.EV_KEY, 0x13A, 1, 0.0)
        self.assertEqual(
            gp.PadManager.held_names(operator), ["button 0x136", "speed mode"]
        )


class LostRelease(unittest.TestCase):
    """Linux's queue overflowing: what it says, and what linux/input.h says to do."""

    def pad(self, stands):
        pad = gp.EvdevPad.__new__(gp.EvdevPad)
        pad.ranges = dict.fromkeys(stands, (0, 1023))
        pad.dropping = False
        pad.stands = stands.__getitem__
        return pad

    def test_where_the_axes_stand_is_asked_for_afresh(self):
        pad = self.pad({gp.ABS_GAS: 0, gp.ABS_BRAKE: 0})
        got = pad.after_drops(
            [
                (gp.EV_ABS, gp.ABS_Y, 7),
                (gp.EV_SYN, gp.SYN_DROPPED, 0),
                (gp.EV_ABS, gp.ABS_GAS, 900),  # from before: thrown away
                (gp.EV_SYN, gp.SYN_REPORT, 0),
            ]
        )
        self.assertEqual(
            got,
            [
                (gp.EV_ABS, gp.ABS_Y, 7),
                (gp.EV_ABS, gp.ABS_GAS, 0),
                (gp.EV_ABS, gp.ABS_BRAKE, 0),
            ],
        )
        operator = gp.Operator(
            {gp.ABS_GAS: (0, 1023), gp.ABS_BRAKE: (0, 1023)},
            0.0,
            values={gp.ABS_GAS: 1023},
        )
        for event in got:
            operator.event(*event, 0.1)
        self.assertEqual(operator.command(0.1)["forward"], 0.0)

    def test_a_drop_across_two_reads_still_waits_for_the_report(self):
        pad = self.pad({gp.ABS_GAS: 0})
        self.assertEqual(pad.after_drops([(gp.EV_SYN, gp.SYN_DROPPED, 0)]), [])
        self.assertEqual(pad.after_drops([(gp.EV_ABS, gp.ABS_GAS, 900)]), [])
        self.assertEqual(
            pad.after_drops([(gp.EV_SYN, gp.SYN_REPORT, 0)]),
            [(gp.EV_ABS, gp.ABS_GAS, 0)],
        )


class ScriptedPad:
    name = "Scripted"
    ranges = PLAYSTATION
    values = {}
    layout = gp.layout_of(PLAYSTATION, ())

    def __init__(self):
        self.events = []
        self.gone = threading.Event()
        self.closed = False

    def read(self, timeout):
        if self.gone.is_set():
            raise OSError(19, "No such device")
        events, self.events = self.events, []
        time.sleep(0.005)
        return events

    def close(self):
        self.closed = True


class RecordingRumble:
    why_not = ""

    def __init__(self):
        self.played = []

    def pulses(self, n):
        self.played.append(n)

    def close(self):
        pass


class RumbleTests(unittest.TestCase):
    def test_the_report_is_hid_microsofts(self):
        # report 3, both motors, triggers off, 60 of 100, 150 ms, no delay, once.
        self.assertEqual(gp.rumble_report(0.15), bytes([3, 3, 0, 0, 60, 60, 15, 0, 0]))
        self.assertEqual(gp.rumble_report(9.0)[6], 255)

    def test_pulses_are_written_one_report_each(self):
        fd, name = tempfile.mkstemp()
        os.close(fd)
        path = Path(name)
        self.addCleanup(path.unlink)
        rumble = gp.Rumble(str(path))
        self.assertEqual(rumble.why_not, "")
        rumble.pulses(2)
        self.assertTrue(until(lambda: path.stat().st_size == 18))
        rumble.close()
        self.assertEqual(path.read_bytes(), gp.rumble_report(gp.PULSE_S) * 2)

    def test_a_node_it_may_not_write_is_said_and_never_written(self):
        rumble = gp.Rumble("/no/such/hidraw")
        self.assertIn("cannot write", rumble.why_not)
        rumble.pulses(1)  # nothing to write to, and no error

    def test_a_controller_with_none_says_so(self):
        self.assertTrue(gp.Rumble().why_not)


def until(condition, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


class RideHeight(unittest.TestCase):
    """The D-pad's height back at the top whenever the robot is disarmed."""

    def attached(self, height=None):
        manager = gp.PadManager(find=lambda: None)
        manager.attach(ScriptedPad(), 0.0)
        if height is not None:
            manager.operator.height = height
        return manager

    def test_the_first_controller_starts_at_the_top(self):
        self.assertEqual(self.attached().operator.height, gp.HEIGHT_RANGE_M[1])

    def test_nothing_holding_control_puts_it_back_at_the_top(self):
        manager = self.attached(gp.HEIGHT_RANGE_M[0])
        manager.control({"status": {"pi": {"control": None}}})
        self.assertEqual(manager.operator.command(0.0)["height"], gp.HEIGHT_RANGE_M[1])
        self.assertIs(manager.snapshot()["armed"], False)

    def test_a_run_holding_control_keeps_the_dpads_height(self):
        manager = self.attached(0.18)
        manager.control({"status": {"pi": {"control": "balance (127.0.0.1:35918)"}}})
        self.assertAlmostEqual(manager.operator.command(0.0)["height"], 0.18)
        self.assertIs(manager.snapshot()["armed"], True)

    def test_a_controller_coming_back_mid_run_keeps_its_height(self):
        manager = self.attached(0.18)
        manager.detach()
        manager.attach(ScriptedPad(), 1.0)
        self.assertAlmostEqual(manager.operator.height, 0.18)

    def test_a_daemon_with_no_status_yet_leaves_it(self):
        manager = self.attached(0.18)
        refusing = Mock()
        refusing.request.side_effect = diag_client.RobotError("no status yet")
        manager.ask_control(refusing)
        self.assertAlmostEqual(manager.operator.height, 0.18)
        self.assertIsNone(manager.snapshot()["armed"])


class PathToThePolicy(unittest.TestCase):
    """The real daemon and the simulated controller, over a real socket."""

    def daemon(self, takes_drive):
        ours, controller = diag_sim.simulate(takes_drive=takes_drive)
        daemon = diagd.Daemon(
            diagd.SocketStream(ours, "simulated"), led=diagd.Led(None)
        )
        server = socket.create_server(("127.0.0.1", 0))
        port = server.getsockname()[1]
        for loop in (daemon.read_loop, daemon.timer_loop):
            threading.Thread(target=loop, daemon=True).start()
        threading.Thread(target=daemon.accept_loop, args=(server,), daemon=True).start()
        self.addCleanup(server.close)
        self.addCleanup(setattr, controller, "running", False)
        return daemon, controller, f"127.0.0.1:{port}"

    def manager(self, where, pad):
        found = [pad]
        manager = gp.PadManager(
            find=lambda: found.pop() if found else None,
            connect=lambda: diag_client.Robot(
                where, name="game controller", streams=()
            ),
        )
        manager.start()
        self.addCleanup(manager.close)
        return manager

    def hold(self, manager, pad):
        """Attached, with the triggers and the turn seen at rest."""

        def driving():
            sent = manager.snapshot()["command"]
            return sent and sent["live"]

        self.assertTrue(until(driving), "never went live")

    def test_a_stick_reaches_a_controller_that_takes_it(self):
        daemon, controller, where = self.daemon(takes_drive=True)
        self.assertTrue(until(lambda: daemon.info.get("drive") == "1"))
        pad = ScriptedPad()
        manager = self.manager(where, pad)
        self.hold(manager, pad)
        pad.events = [(gp.EV_ABS, GAS, 255), (gp.EV_ABS, gp.ABS_X, 255)]
        self.assertTrue(
            until(lambda: controller.drive and controller.drive["forward"] > 0),
            controller.drive,
        )
        self.assertTrue(until(lambda: controller.drive["turn"] != 0), controller.drive)
        self.assertAlmostEqual(controller.drive["forward"], gp.START_SPEED_M_S)
        self.assertAlmostEqual(controller.drive["turn"], -gp.START_TURN_RAD_S)
        self.assertAlmostEqual(controller.drive["height"], gp.HEIGHT_RANGE_M[1])
        self.assertTrue(until(lambda: manager.snapshot()["taken"] is True))
        # Letting go is seen at the controller as speed and turn of nothing.
        pad.events = [(gp.EV_ABS, GAS, 0), (gp.EV_ABS, gp.ABS_X, 128)]
        self.assertTrue(until(lambda: controller.drive["forward"] == 0.0))
        self.assertTrue(until(lambda: controller.drive["turn"] == 0.0))
        self.assertEqual(controller.malformed, 0)

    def test_todays_firmware_is_sent_nothing_it_would_call_nonsense(self):
        daemon, controller, where = self.daemon(takes_drive=False)
        self.assertTrue(until(lambda: daemon.info))
        pad = ScriptedPad()
        manager = self.manager(where, pad)
        self.hold(manager, pad)
        pad.events = [(gp.EV_ABS, GAS, 255)]
        self.assertTrue(until(lambda: manager.snapshot()["taken"] is False))
        time.sleep(0.2)
        self.assertEqual(controller.malformed, 0)
        self.assertIsNone(controller.drive)

    def test_the_stream_carries_it_for_anything_else_that_runs_a_policy(self):
        daemon, _, where = self.daemon(takes_drive=False)
        heard = []
        listener = diag_client.Robot(where, name="listener", streams=("drive",))
        self.addCleanup(listener.close)
        listener.on("drive", heard.append)
        pad = ScriptedPad()
        manager = self.manager(where, pad)
        self.hold(manager, pad)
        pad.events = [(gp.EV_ABS, GAS, 255)]
        self.assertTrue(until(lambda: heard and heard[-1]["forward"] > 0))
        self.assertAlmostEqual(heard[-1]["forward"], gp.START_SPEED_M_S)

    def test_no_button_stops_the_motors_another_client_is_driving(self):
        daemon, _, where = self.daemon(takes_drive=False)
        owner = diag_client.Robot(where, name="bench", streams=("status",))
        self.addCleanup(owner.close)
        owner.take_control()
        stopped = []
        owner.on("stopped", stopped.append)
        pad = ScriptedPad()
        self.manager(where, pad)
        self.assertTrue(until(lambda: daemon.info))
        time.sleep(0.1)
        pad.events = [(gp.EV_KEY, code, 1) for code in range(0x130, 0x140)]
        time.sleep(0.3)
        self.assertEqual(stopped, [])

    def test_a_command_from_before_connecting_is_not_sent_after_it(self):
        daemon, controller, where = self.daemon(takes_drive=True)
        self.assertTrue(until(lambda: daemon.info.get("drive") == "1"))
        pad = ScriptedPad()
        released = threading.Event()

        def slow_to_connect():
            # The trigger is let go of while the connection is being made.
            pad.events = [(gp.EV_ABS, GAS, 0)]
            time.sleep(0.1)
            released.set()
            return diag_client.Robot(where, name="game controller", streams=())

        found = [pad]
        manager = gp.PadManager(
            find=lambda: found.pop() if found else None, connect=slow_to_connect
        )
        pad.events = [(gp.EV_ABS, GAS, 255)]
        manager.start()
        self.addCleanup(manager.close)
        self.assertTrue(until(released.is_set))
        self.assertTrue(until(lambda: controller.drive is not None))
        self.assertEqual(controller.drive["forward"], 0.0)

    def test_a_controller_taken_away_ends_at_once_and_says_so_last(self):
        daemon, controller, where = self.daemon(takes_drive=True)
        self.assertTrue(until(lambda: daemon.info.get("drive") == "1"))
        pad = ScriptedPad()
        manager = self.manager(where, pad)
        pad.events = [(gp.EV_ABS, GAS, 255)]
        self.assertTrue(until(lambda: controller.drive and controller.drive["live"]))
        pad.gone.set()
        self.assertTrue(until(lambda: manager.snapshot()["name"] is None))
        self.assertTrue(pad.closed)
        self.assertTrue(
            until(lambda: not controller.drive["live"]),
            "the controller was left believing it is still being driven",
        )

    def test_disarmed_the_height_goes_back_to_the_top(self):
        daemon, _, where = self.daemon(takes_drive=False)
        heard = []
        listener = diag_client.Robot(where, name="listener", streams=("drive",))
        self.addCleanup(listener.close)
        listener.on("drive", heard.append)
        self.assertTrue(until(lambda: daemon.status is not None))
        run = diag_client.Robot(where, name="balance", streams=())
        self.addCleanup(run.close)
        run.take_control()
        pad = ScriptedPad()
        manager = self.manager(where, pad)
        self.hold(manager, pad)
        self.assertTrue(until(lambda: manager.snapshot()["armed"] is True))
        pad.events = [(gp.EV_ABS, gp.ABS_HAT0Y, 1)]  # down
        self.assertTrue(until(lambda: heard and heard[-1]["height"] < 0.2))
        pad.events = [(gp.EV_ABS, gp.ABS_HAT0Y, 0)]
        time.sleep(1.2)
        self.assertLess(heard[-1]["height"], 0.2, "a run's height was put back")
        run.release_control()
        self.assertTrue(
            until(lambda: heard[-1]["height"] == gp.HEIGHT_RANGE_M[1]), heard[-1]
        )
        self.assertIs(manager.snapshot()["armed"], False)

    def test_a_shutting_down_robot_refuses_it(self):
        daemon, controller, where = self.daemon(takes_drive=True)
        client = diag_client.Robot(where, name="c", streams=())
        self.addCleanup(client.close)
        daemon.shutting_down = True
        with self.assertRaises(diag_client.RobotError):
            client.request(
                "drive", forward=0.1, turn=0.0, height=0.2, live=True, jump=0
            )

    def test_the_daemon_will_not_pass_on_what_the_wire_cannot_carry(self):
        _, _, where = self.daemon(takes_drive=True)
        client = diag_client.Robot(where, name="c", streams=())
        self.addCleanup(client.close)
        for bad in (dict(forward=1e9), dict(forward=float("nan")), dict(height=-1)):
            fields = dict(forward=0.0, turn=0.0, height=0.2, live=True, jump=0) | bad
            with self.assertRaises(diag_client.RobotError):
                client.request("drive", **fields)

    def test_not_live_never_carries_a_speed(self):
        daemon, controller, where = self.daemon(takes_drive=True)
        self.assertTrue(until(lambda: daemon.info.get("drive") == "1"))
        client = diag_client.Robot(where, name="c", streams=())
        self.addCleanup(client.close)
        client.request("drive", forward=1.0, turn=1.0, height=0.2, live=False, jump=0)
        self.assertTrue(until(lambda: controller.drive is not None))
        self.assertEqual(controller.drive["forward"], 0.0)
        self.assertEqual(controller.drive["turn"], 0.0)

    def test_the_held_bit_reaches_the_stream_and_only_the_count_the_link(self):
        """diagd passes "jump" on whole to whatever runs the policy, and J5's DRIVE
        carries a byte of it."""
        daemon, controller, where = self.daemon(takes_drive=True)
        self.assertTrue(until(lambda: daemon.info.get("drive") == "1"))
        heard = []
        listener = diag_client.Robot(where, name="listener", streams=("drive",))
        self.addCleanup(listener.close)
        listener.on("drive", heard.append)
        client = diag_client.Robot(where, name="c", streams=())
        self.addCleanup(client.close)
        jump = 7 | gp.JUMP_HELD
        client.request("drive", forward=0.0, turn=0.0, height=0.2, live=True, jump=jump)
        self.assertTrue(until(lambda: heard and controller.drive is not None))
        self.assertEqual(heard[-1]["jump"], jump)
        self.assertEqual(controller.drive["jump"], 7)

    def policy(self, where):
        """What runs the policy, as balance.py does it: select's presses since it
        started toggle the speed mode, and each change is told to the daemon."""
        robot = diag_client.Robot(where, name="policy", streams=("drive",))
        self.addCleanup(robot.close)
        state = {"base": None, "fast": False}

        def heard(m):
            if state["base"] is None:
                state["base"] = m["mode"]
            fast = (m["mode"] - state["base"]) % 2 == 1
            if fast != state["fast"]:
                state["fast"] = fast
                robot.send("indicate", fast=fast)

        robot.on("drive", heard)
        return state

    def press_select(self, pad):
        pad.events = [(gp.EV_KEY, gp.BTN_SELECT, 1), (gp.EV_KEY, gp.BTN_SELECT, 0)]

    def test_the_controller_buzzes_twice_going_fast_and_once_going_slow(self):
        _, _, where = self.daemon(takes_drive=True)
        self.policy(where)
        pad = ScriptedPad()
        pad.rumble = RecordingRumble()
        manager = self.manager(where, pad)
        self.hold(manager, pad)
        self.assertTrue(until(lambda: manager.snapshot()["fast"] is False))
        self.press_select(pad)
        self.assertTrue(until(lambda: pad.rumble.played == [2]), pad.rumble.played)
        self.press_select(pad)
        self.assertTrue(until(lambda: pad.rumble.played == [2, 1]), pad.rumble.played)
        time.sleep(0.3)
        self.assertEqual(pad.rumble.played, [2, 1], "buzzed for nothing")

    def test_a_press_that_nothing_takes_is_answered_by_nothing(self):
        _, _, where = self.daemon(takes_drive=True)
        pad = ScriptedPad()
        pad.rumble = RecordingRumble()
        manager = self.manager(where, pad)
        self.hold(manager, pad)
        self.assertTrue(until(lambda: manager.snapshot()["fast"] is False))
        self.press_select(pad)
        self.assertTrue(until(lambda: manager.snapshot()["command"]["mode"] == 1))
        time.sleep(gp.MODE_WATCH_S + 0.2)
        self.assertEqual(pad.rumble.played, [])

    def test_a_controller_coming_back_does_not_count_its_presses_again(self):
        _, _, where = self.daemon(takes_drive=True)
        first, second = ScriptedPad(), ScriptedPad()
        found = [second, first]
        manager = gp.PadManager(
            find=lambda: found.pop() if found else None,
            connect=lambda: diag_client.Robot(where, name="c", streams=()),
        )
        manager.start()
        self.addCleanup(manager.close)
        self.hold(manager, first)
        self.press_select(first)
        first.events += [(gp.EV_KEY, JUMP, 1), (gp.EV_KEY, JUMP, 0)]
        self.assertTrue(until(lambda: manager.snapshot()["command"]["mode"] == 1))
        first.gone.set()
        self.hold(manager, second)
        sent = manager.snapshot()["command"]
        self.assertEqual((sent["mode"], sent["jump"]), (1, 1))

    def test_limits_stay_inside_what_the_policy_was_trained_on(self):
        manager = gp.PadManager(find=lambda: None, connect=Mock())
        self.assertEqual(manager.limits(dict(speed=0.3, turn=1.0))["speed_limit"], 0.3)
        for bad in (
            dict(speed=gp.TOP_SPEED_M_S + 0.01, turn=1),
            dict(speed=1, turn=gp.TOP_TURN_RAD_S + 0.01),
            dict(speed=-1, turn=1),
            dict(speed=float("nan"), turn=1),
        ):
            with self.assertRaises(ValueError):
                manager.limits(bad)
        self.assertEqual(manager.snapshot()["speed_limit"], 0.3)


class FakeTool:
    """bluetoothctl's half, as BlueZ 5 prints it. The fields are the ones
    tools/test_gamepad_linux.py reads off the real program."""

    def __init__(self, adapter=True):
        self.adapter = adapter
        self.devices = {}
        self.calls = []
        self.scans = 0
        self.pair_works = True
        self.pair_says = ""
        self.pair_fails_first = 0
        self.connect_fails_first = 0
        self.pairable_stuck = False
        self.input_appears = True
        self.scan_fails = False
        self.agents = 0
        self.finished = 0
        self.pairable = False
        self.appears_after_scan = {}

    async def run(self, *args, timeout=8):
        self.calls.append(args)
        command = args[0]
        if command == "show":
            if not self.adapter:
                return 1, "No default controller available\n"
            pairable = "yes" if self.pairable or self.pairable_stuck else "no"
            return 0, (
                "Controller 00:11:22:33:44:55 (public)\n"
                f"\tPowered: yes\n\tPairable: {pairable}\n"
            )
        if command == "power":
            return 0, "Changing power on succeeded\n"
        if command == "pairable":
            self.pairable = args[1] == "on"
            return 0, f"Changing pairable {args[1]} succeeded\n"
        if command == "devices":
            return 0, "".join(
                f"Device {a} {d.get('Name', a.replace(':', '-'))}\n"
                for a, d in self.devices.items()
            )
        address = args[1]
        device = self.devices.get(address)
        if command == "info":
            if device is None:
                return 1, f"Device {address} not available\n"
            lines = [f"Device {address} (public)"]
            lines += [f"\t{k}: {v}" for k, v in device.items()]
            return 0, "\n".join(lines) + "\n"
        if command == "trust":
            device["Trusted"] = "yes"
            return 0, ""
        if command == "connect":
            if self.connect_fails_first:
                self.connect_fails_first -= 1
                return 1, "Failed to connect: org.bluez.Error.Failed\n"
            device["Connected"] = "yes"
            return 0, ""
        if command == "remove":
            self.devices.pop(address, None)
            return 0, ""
        raise AssertionError(args)

    @contextlib.asynccontextmanager
    async def agent(self):
        self.agents += 1
        yield self

    async def pair(self, address, timeout):
        self.calls.append(("pair", address))
        self.pairable_while_pairing = self.pairable
        self.scanning_while_pairing = self.scans > self.finished
        if self.pair_fails_first:
            self.pair_fails_first -= 1
            return "ConnectionAttemptFailed"
        if self.pair_works:
            self.devices[address]["Paired"] = "yes"
            return ""
        return self.pair_says

    def has_input(self, address):
        return self.input_appears

    def failed(self, scan):
        return self.scan_fails

    async def scan(self, seconds):
        self.scans += 1
        self.devices.update(self.appears_after_scan)
        return "scan"

    @staticmethod
    async def wait(scan, timeout):
        return True

    async def finish(self, scan):
        self.finished += 1


PAD = "AA:BB:CC:00:00:01"
SPEAKER = "AA:BB:CC:00:00:02"
BEACON = "AA:BB:CC:00:00:03"


def pad_device(**extra):
    return {
        "Name": "Wireless Controller",
        "Icon": "input-gaming",
        "Paired": "no",
        "Trusted": "no",
        "Connected": "no",
        "UUID": "Human Interface Device (00001124-0000-1000-8000-00805f9b34fb)",
    } | extra


class BluetoothTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tool = FakeTool()
        self.manager = cb.BluetoothManager(self.tool)

    async def act(self, op, **fields):
        state = await self.manager.action({"op": f"bluetooth.{op}", **fields})
        if self.manager.task:
            await self.manager.task
        return dict(self.manager.state) if state else state

    async def test_no_adapter_says_so_and_does_not_list_anything(self):
        self.tool.adapter = False
        state = await self.act("status")
        self.assertIs(state["available"], False)
        self.assertEqual(state["paired"], [])

    async def test_no_bluez_is_an_answer_not_a_crash(self):
        self.tool.run = Mock(side_effect=FileNotFoundError)
        state = await self.act("status")
        self.assertIn("not installed", state["error"])

    async def test_a_service_that_never_answers_is_an_answer_too(self):
        self.tool.run = Mock(side_effect=TimeoutError)
        state = await self.act("status")
        self.assertIn("not answering", state["error"])

    async def test_a_controller_that_gives_no_name_is_listed_all_the_same(self):
        unnamed = pad_device(Alias=PAD.replace(":", "-"))
        del unnamed["Name"]
        self.tool.appears_after_scan = {PAD: unnamed, BEACON: {"Paired": "no"}}
        state = await self.act("scan")
        self.assertEqual([d["address"] for d in state["found"]], [PAD])
        self.assertTrue(state["found"][0]["gamepad"])
        self.assertEqual(state["found"][0]["name"], f"Unnamed controller {PAD}")

    async def test_a_nameless_device_once_paired_can_still_be_forgotten(self):
        self.tool.devices[BEACON] = {"Paired": "yes"}
        state = await self.act("status")
        self.assertEqual([d["address"] for d in state["paired"]], [BEACON])

    async def test_a_scan_lists_controllers_first_and_nameless_things_not_at_all(self):
        self.tool.appears_after_scan = {
            SPEAKER: {"Name": "A speaker", "Paired": "no"},
            PAD: pad_device(),
            BEACON: {"Paired": "no"},
        }
        state = await self.act("scan")
        self.assertEqual([d["address"] for d in state["found"]], [PAD, SPEAKER])
        self.assertTrue(state["found"][0]["gamepad"])
        self.assertEqual(state["message"], "Scan complete")

    async def test_found_outlasts_bluez_forgetting_it(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.devices.clear()
        state = await self.act("status")
        self.assertEqual([d["address"] for d in state["found"]], [PAD])

    async def test_pairing_trusts_it_connects_it_and_moves_it_across(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        state = await self.act("pair", address=PAD)
        self.assertEqual(state["error"], "")
        self.assertEqual([d["address"] for d in state["paired"]], [PAD])
        self.assertEqual(state["found"], [])
        self.assertTrue(state["paired"][0]["trusted"])
        self.assertIn("paired and connected", state["message"])
        verbs = [c[0] for c in self.tool.calls]
        self.assertLess(verbs.index("pair"), verbs.index("trust"))
        self.assertLess(verbs.index("trust"), verbs.index("connect"))
        self.assertTrue(self.tool.pairable_while_pairing)
        self.assertFalse(self.tool.pairable, "left open to anything nearby")

    async def test_pairing_finds_again_what_bluez_has_forgotten(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.devices.clear()
        state = await self.act("pair", address=PAD)
        self.assertEqual(state["error"], "")
        self.assertEqual(len(state["paired"]), 1)
        self.assertEqual(self.tool.scans, 2)

    async def test_a_scan_runs_through_the_tries_and_stops_after(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.pair_fails_first = 2
        with patch.object(cb, "TRY_AGAIN_S", 0):
            state = await self.act("pair", address=PAD)
        self.assertEqual(state["error"], "")
        self.assertTrue(self.tool.scanning_while_pairing)
        self.assertEqual(self.tool.scans, 2)
        self.assertEqual(self.tool.finished, 2, "scan left running")

    async def test_a_scan_stops_after_tries_that_all_fail(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.pair_works = False
        self.tool.pair_says = "AuthenticationFailed"
        await self.act("pair", address=PAD)
        self.assertEqual(self.tool.finished, self.tool.scans, "scan left running")

    async def test_a_controller_that_never_comes_back_is_reported(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.devices.clear()
        self.tool.appears_after_scan = {}
        with (
            patch.object(cb, "FIND_AGAIN_S", 0.02),
            patch.object(cb, "LOOK_EVERY_S", 0.005),
        ):
            state = await self.act("pair", address=PAD)
        self.assertIn("has gone", state["error"])
        self.assertFalse(self.tool.pairable, "left open after a failure")
        self.assertEqual(self.tool.finished, self.tool.scans, "scan left running")

    async def test_missed_connections_are_tried_again(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.pair_fails_first = 5
        with patch.object(cb, "TRY_AGAIN_S", 0):
            state = await self.act("pair", address=PAD)
        self.assertEqual(state["error"], "")
        self.assertEqual(self.tool.calls.count(("pair", PAD)), 6)
        self.assertEqual(self.tool.agents, 1, "one agent for all of the tries")
        self.assertEqual([d["address"] for d in state["paired"]], [PAD])

    async def test_connections_missed_for_too_long_are_reported(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.pair_fails_first = 10**9
        with patch.object(cb, "TRY_FOR_S", 0.05), patch.object(cb, "TRY_AGAIN_S", 0):
            state = await self.act("pair", address=PAD)
        self.assertIn("(ConnectionAttemptFailed)", state["error"])
        self.assertFalse(self.tool.pairable, "left open after a failure")
        self.assertFalse(state["busy"])

    async def test_a_controller_forgotten_between_tries_is_found_again(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        real_pair = self.tool.pair

        async def forgotten_once(address, timeout):
            self.tool.pair = real_pair
            self.tool.devices.clear()
            # The scan running through the tries hears it again.
            asyncio.get_running_loop().call_later(
                0.02, self.tool.devices.update, {PAD: pad_device()}
            )
            return "Device AA:BB:CC:00:00:01 not available"

        self.tool.pair = forgotten_once
        with (
            patch.object(cb, "TRY_AGAIN_S", 0),
            patch.object(cb, "LOOK_EVERY_S", 0.005),
        ):
            state = await self.act("pair", address=PAD)
        self.assertEqual(state["error"], "")
        self.assertEqual(self.tool.scans, 2)

    async def test_a_link_lost_after_pairing_is_connected_again(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.connect_fails_first = 4
        with patch.object(cb, "TRY_AGAIN_S", 0):
            state = await self.act("pair", address=PAD)
        self.assertEqual(state["error"], "")
        self.assertTrue(state["paired"][0]["connected"])
        self.assertIn("paired and connected", state["message"])
        self.assertEqual(self.tool.calls.count(("connect", PAD)), 5)
        self.assertFalse(self.tool.pairable, "left open to anything nearby")

    async def test_a_controller_that_never_connects_is_not_called_done(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.connect_fails_first = 10**9
        with (
            patch.object(cb, "TRY_AGAIN_S", 0),
            patch.object(cb, "CONNECT_FOR_S", 0.05),
        ):
            state = await self.act("pair", address=PAD)
        self.assertIn("never finished connecting", state["error"])
        self.assertEqual(state["message"], "")
        self.assertEqual([d["address"] for d in state["paired"]], [PAD])
        self.assertFalse(self.tool.pairable, "left open after a failure")
        self.assertFalse(state["busy"])

    async def test_a_link_with_no_input_device_is_not_called_connected(self):
        # 045E:0B13: linked, BlueZ still reading it, then the controller hangs up.
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.input_appears = False
        with (
            patch.object(cb, "TRY_AGAIN_S", 0),
            patch.object(cb, "CONNECT_FOR_S", 0.05),
        ):
            state = await self.act("pair", address=PAD)
        self.assertIn("never finished connecting", state["error"])
        self.assertNotIn("connected", state["message"])
        self.assertTrue(state["paired"][0]["connected"])
        self.assertFalse(state["paired"][0]["ready"])
        self.assertEqual(self.tool.calls.count(("connect", PAD)), 1, "asked again")

    async def test_the_message_goes_when_the_controller_does(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        state = await self.act("pair", address=PAD)
        self.assertIn("paired and connected", state["message"])
        state = await self.act("status")
        self.assertIn("paired and connected", state["message"], "still true")
        self.tool.devices[PAD]["Connected"] = "no"
        state = await self.act("status")
        self.assertEqual(state["message"], "")
        self.assertFalse(state["paired"][0]["ready"])

    async def test_an_adapter_that_will_not_shut_is_reported(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.pairable_stuck = True
        state = await self.act("pair", address=PAD)
        self.assertIn("still open to pairing", state["error"])
        self.assertFalse(state["busy"])

    async def test_an_adapter_is_shut_when_opening_it_fails(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        real_run = self.tool.run

        async def opening_times_out(*args, timeout=8):
            if args == ("pairable", "on"):
                self.tool.pairable = True  # it took effect, and the answer was lost
                raise TimeoutError
            return await real_run(*args, timeout=timeout)

        self.tool.run = opening_times_out
        state = await self.act("pair", address=PAD)
        self.assertIn("took too long", state["error"])
        self.assertFalse(self.tool.pairable, "left open to anything nearby")

    async def test_a_scan_that_fails_says_so(self):
        self.tool.scan_fails = True
        state = await self.act("scan")
        self.assertIn("scan stopped with an error", state["error"])
        self.assertNotEqual(state["message"], "Scan complete")

    async def test_a_click_is_not_refused_by_the_pages_own_polling(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        await self.manager.action({"op": "bluetooth.status"})
        # action() has awaited the status job for a real poll, so hold one open.
        release = asyncio.Event()
        real_refresh = self.manager.refresh

        async def slow_refresh():
            await release.wait()
            self.manager.refresh = real_refresh
            await real_refresh()

        self.manager.refresh = slow_refresh
        poll = asyncio.create_task(self.manager.action({"op": "bluetooth.status"}))
        await asyncio.sleep(0)
        self.assertTrue(self.manager.polling)
        click = asyncio.create_task(
            self.manager.action({"op": "bluetooth.pair", "address": PAD})
        )
        await asyncio.sleep(0)
        release.set()
        await poll
        state = await click
        await self.manager.task
        self.assertEqual(state["message"], "Pairing…")
        self.assertEqual(self.manager.state["error"], "")

    def test_an_input_device_is_found_by_the_address_it_gives(self):
        # /proc/bus/input/devices on the robot, 045E:0B20 connected, 2026-11-05.
        text = (
            'I: Bus=001e Vendor=0000 Product=0000 Version=0001\nN: Name="dw_hdmi"\n'
            "U: Uniq=\nH: Handlers=kbd event0\n\n"
            "I: Bus=0005 Vendor=045e Product=0b20 Version=0523\n"
            'N: Name="Xbox Wireless Controller"\nU: Uniq=ec:83:50:eb:0b:50\n'
            "H: Handlers=kbd js0 event1\n"
        )
        fake = Mock()
        fake.read_text.return_value = text
        with patch.object(cb, "INPUT_DEVICES", fake):
            self.assertTrue(cb.Tool.has_input("EC:83:50:EB:0B:50"))
            self.assertFalse(cb.Tool.has_input("40:8E:2C:42:E2:45"))
        fake.read_text.side_effect = OSError
        with patch.object(cb, "INPUT_DEVICES", fake):
            self.assertFalse(cb.Tool.has_input("EC:83:50:EB:0B:50"))

    async def test_any_other_refusal_is_not_tried_again(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.pair_works = False
        self.tool.pair_says = "AuthenticationFailed"
        await self.act("pair", address=PAD)
        self.assertEqual(self.tool.calls.count(("pair", PAD)), 1)

    async def test_a_failed_pairing_says_so_whatever_the_tool_returned(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.pair_works = False  # and the fake still returns 0
        state = await self.act("pair", address=PAD)
        self.assertIn("Pairing failed", state["error"])
        self.assertEqual(state["paired"], [])
        self.assertFalse(self.tool.pairable, "left open after a failure")

    async def test_a_failed_pairing_gives_bluezs_reason(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.pair_works = False
        self.tool.pair_says = "AuthenticationFailed"
        state = await self.act("pair", address=PAD)
        self.assertIn("(AuthenticationFailed)", state["error"])

    async def test_a_pairing_that_never_finishes_is_an_answer(self):
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.act("scan")
        self.tool.pair = Mock(side_effect=TimeoutError)
        state = await self.act("pair", address=PAD)
        self.assertIn("Pairing failed (no answer)", state["error"])
        self.assertFalse(self.tool.pairable, "left open after a failure")
        self.assertFalse(state["busy"])

    async def scan_that_goes_on(self):
        async def not_yet(scan, timeout):
            await asyncio.sleep(0.005)
            return False

        self.tool.wait = not_yet
        self.tool.appears_after_scan = {PAD: pad_device()}
        await self.manager.action({"op": "bluetooth.scan"})
        for _ in range(200):
            if self.manager.state["found"]:
                return
            await asyncio.sleep(0.005)
        self.fail("the scan found nothing")

    async def test_a_scan_gives_way_to_pairing_what_it_found(self):
        await self.scan_that_goes_on()
        state = self.manager.state
        self.assertTrue(state["busy"] and state["scanning"])
        self.assertEqual([d["address"] for d in state["found"]], [PAD])
        state = await self.manager.action({"op": "bluetooth.pair", "address": PAD})
        self.assertEqual(state["message"], "Pairing…")
        self.assertFalse(state["scanning"])
        self.assertEqual(self.tool.finished, 1, "the scan was not stopped")
        await self.manager.task
        state = self.manager.state
        self.assertEqual(state["error"], "")
        self.assertEqual([d["address"] for d in state["paired"]], [PAD])
        self.assertFalse(state["busy"] or state["scanning"])

    async def test_two_pair_presses_during_a_scan_pair_once(self):
        await self.scan_that_goes_on()
        press = {"op": "bluetooth.pair", "address": PAD}
        first, second = await asyncio.gather(
            self.manager.action(press),
            self.manager.action(press),
            return_exceptions=True,
        )
        self.assertIsInstance(second, ValueError)
        self.assertEqual(first["message"], "Pairing…")
        await self.manager.task
        self.assertEqual(self.tool.calls.count(("pair", PAD)), 1)

    async def test_only_pairing_interrupts_a_scan(self):
        await self.scan_that_goes_on()
        with self.assertRaises(ValueError):
            await self.manager.action({"op": "bluetooth.scan"})
        with self.assertRaises(ValueError):
            await self.manager.action({"op": "bluetooth.forget", "address": PAD})
        self.assertTrue(self.manager.state["scanning"])
        await self.manager.action({"op": "bluetooth.pair", "address": PAD})
        await self.manager.task

    async def test_forgetting_removes_it(self):
        self.tool.devices[PAD] = pad_device(Paired="yes", Trusted="yes")
        state = await self.act("status")
        self.assertEqual(len(state["paired"]), 1)
        state = await self.act("forget", address=PAD)
        self.assertEqual(state["paired"], [])
        self.assertEqual(state["message"], "Controller forgotten")
        self.assertIn(("remove", PAD), self.tool.calls)

    async def test_only_an_address_gets_to_the_command_line(self):
        for bad in ("--help", "AA:BB", "aa:bb:cc:00:00:01; rm", None, 7):
            with self.assertRaises(ValueError):
                await self.manager.action({"op": "bluetooth.pair", "address": bad})
        self.assertEqual(self.tool.calls, [])

    async def test_one_job_at_a_time(self):
        self.manager.state["busy"] = True
        with self.assertRaises(ValueError):
            await self.manager.action({"op": "bluetooth.scan"})
        with self.assertRaises(ValueError):
            await self.manager.action({"op": "bluetooth.pair", "address": PAD})
        state = await self.manager.action({"op": "bluetooth.status"})
        self.assertTrue(state["busy"])


class SimulatedConsole(unittest.TestCase):
    def test_pairing_the_simulated_controller_makes_it_appear(self):
        bluetooth = cb.SimulatedBluetooth()

        async def go():
            await bluetooth.action({"op": "bluetooth.scan"})
            await bluetooth.task
            self.assertEqual(len(bluetooth.state["found"]), 2)
            self.assertFalse(bluetooth.connected)
            await bluetooth.action(
                {"op": "bluetooth.pair", "address": bluetooth.SPEAKER}
            )
            await bluetooth.task
            self.assertIn("Pairing failed", bluetooth.state["error"])
            await bluetooth.action(
                {"op": "bluetooth.pair", "address": bluetooth.CONTROLLER}
            )
            await bluetooth.task
            self.assertTrue(bluetooth.connected)
            await bluetooth.action(
                {"op": "bluetooth.forget", "address": bluetooth.CONTROLLER}
            )
            await bluetooth.task
            self.assertFalse(bluetooth.connected)

        asyncio.run(go())

    def test_the_drive_message_round_trips(self):
        body = dl.drive(-0.25, 1.5, 0.2, False, 300)
        self.assertEqual(
            dl.parse_drive(body),
            dict(forward=-0.25, turn=1.5, height=0.2, live=False, jump=44),
        )
        self.assertEqual(len(json.dumps(dl.parse_drive(body))) > 0, True)


if __name__ == "__main__":
    unittest.main()
