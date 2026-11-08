# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "pyserial>=3.5"]
# ///
"""The scripted jump on the robot's side: sbc/policy_loop.py's ScriptedJump behind the A
button, and the settings that choose it in sbc/balance.py and sbc/launcher.py. That both
legs are always sent the same, that nothing it sends leaves the legs' windows or the
motors' torque, the order of its phases, how it feels the floor, and that it hands back
when it does not; the wheels' level push, and jumping while driving. Free, offline, no
robot and no network: the driving policy is a stand-in that answers what it is told, and
the readings are made up step by step.

    uv run tools/test_scripted_jump.py
"""

from __future__ import annotations

import dataclasses
import math
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbc"))
sys.path.insert(0, str(ROOT / "tools"))

import balance  # noqa: E402
import launcher  # noqa: E402
import policy_loop as pl  # noqa: E402
import sysid_tests as st  # noqa: E402
from test_jump import DRIVING, Answers, pair  # noqa: E402

UP = np.array([0.0, 0.0, -1.0])
STILL = np.zeros(3)
# D8's trained heights.
D8 = DRIVING | {"height_range": [0.165, 0.207], "leg_scale": [0.6, 1.0, 0.6, 1.0]}
SCRIPT = pl.JumpScript()


def legs(
    down: float,
    forward: float | None = None,
    knee_v: float = 0.0,
    knee_nm: float = 0.0,
    wheel_v: float = 0.0,
) -> dict:
    """Both legs alike, each axle `down` below its hip and `forward` of it (by default
    under the centre of mass, standing level)."""
    if forward is None:
        forward = pl.under_mass(down, (0.0, 1.0))
    hip, knee = pl.leg_for(forward, down)
    fb = {}
    for j in st.LEGS:
        if "hip" in j:
            fb[j] = st.Fb(at=0.0, p=hip, v=knee_v / 2.0, tau=0.0)
        else:
            fb[j] = st.Fb(at=0.0, p=knee, v=knee_v, tau=knee_nm)
    for j in st.WHEELS:
        fb[j] = st.Fb(at=0.0, p=0.0, v=wheel_v, tau=0.0)
    return fb


def jumper(push: float = pl.JUMP_PUSH_NM):
    answers = Answers(D8)
    return pl.ScriptedJump(pl.Balancer(answers), push), answers


def step(two, fb, g=UP, speed=0.0, height=0.2035):
    obs = two.observe(fb, STILL, g, speed, 0.0, height)
    return two.decide(obs)


def to_push(two) -> list[dict]:
    """Pressed standing, crouched and held until it pushes: each step's commands."""
    assert two.press(UP, 0.0, True) is None
    out = []
    while two.state == "crouch":
        out.append(step(two, legs(SCRIPT.crouch_m)))
        assert len(out) < 500, two.events
    assert two.phase == "push", two.events
    return out


def to_flight(two, knee_v: float = -20.0) -> list[dict]:
    """On from the push: the knees at the brake, extending at knee_v, then held there."""
    out = to_push(two)
    brake = pl.leg_for(two._along(SCRIPT.takeoff_m), SCRIPT.takeoff_m)[1]
    down = 2.0 * pl.LEG_LINK_M * math.cos(brake / 2.0)
    out.append(step(two, legs(down, two._along(down), knee_v=knee_v)))
    while two.phase == "brake":
        out.append(step(two, legs(SCRIPT.takeoff_m, two._along(SCRIPT.takeoff_m))))
    assert two.phase == "flight", two.events
    return out


class Symmetry(unittest.TestCase):
    def test_both_legs_and_both_wheels_alike_through_every_phase(self):
        two, _ = jumper()
        to_push(two)
        sent = []
        # The legs a little apart, as the robot's are, and a wheel spinning: the
        # commands are the same all the same.
        brake = pl.leg_for(two._along(SCRIPT.takeoff_m), SCRIPT.takeoff_m)[1]
        down = 2.0 * pl.LEG_LINK_M * math.cos(brake / 2.0)
        for fb in [legs(SCRIPT.crouch_m)] * 3 + [legs(down, two._along(down), -20.0)]:
            fb = dict(fb)
            fb["knee_left"] = st.Fb(0.0, fb["knee_left"].p + 0.03, 0.0, 0.0)
            fb["wheel_drive_left"] = st.Fb(0.0, 0.0, 4.0, 0.0)
            sent.append((two.phase, step(two, fb)))
        while two.state == "jump":
            sent.append(
                (two.phase, step(two, legs(SCRIPT.land_m, two._along(SCRIPT.land_m))))
            )
        phases = {p for p, _ in sent}
        self.assertTrue({"push", "brake", "flight"} <= phases, phases)
        for _, cmds in sent:
            for a, b in (
                ("hip_pitch_right", "hip_pitch_left"),
                ("knee_right", "knee_left"),
            ):
                self.assertEqual(cmds[a], cmds[b], (a, cmds[a], cmds[b]))

    def test_the_driving_policys_own_crouch_is_its_own(self):
        """Until the push the legs are the driving policy's, whatever it asks: only from
        the push are they the script's."""
        two, answers = jumper()
        answers.out[:] = [0.1, 0.2, -0.1, 0.3, 0.0, 0.0]
        two.press(UP, 0.0, True)
        cmds = step(two, legs(0.2))
        self.assertEqual(two.state, "crouch")
        self.assertNotEqual(cmds["knee_right"].p, cmds["knee_left"].p)


class Limits(unittest.TestCase):
    def test_the_push_held_to_its_range(self):
        lo, hi = pl.JUMP_PUSH_RANGE_NM
        self.assertEqual(jumper(5.0)[0].push, hi)
        self.assertEqual(jumper(0.0)[0].push, lo)
        self.assertLess(hi, st.PEAK_NM)

    def test_every_command_inside_the_windows_and_the_torque(self):
        for push in pl.JUMP_PUSH_RANGE_NM:
            two, _ = jumper(push)
            sent = to_flight(two, knee_v=-30.0)
            while two.state == "jump":
                sent.append(step(two, legs(SCRIPT.land_m, two._along(SCRIPT.land_m))))
            for cmds in sent[-30:]:
                for j in st.LEGS:
                    c = cmds[j]
                    low, high = st.WINDOWS[j]
                    self.assertTrue(low <= c.p <= high, (j, c.p))
                    self.assertLessEqual(abs(c.t), st.PEAK_NM, (j, c.t))
                    self.assertLessEqual(c.kp, 500.0)
                    self.assertLessEqual(c.kd, 5.0)
                # The knees' push is the setting, extending, and no more.
                self.assertGreaterEqual(cmds["knee_right"].t, -push - 1e-9)

    def test_the_knees_never_asked_past_the_take_off_height(self):
        """Folded back always, and never asked straighter than the take-off height: the
        knees' direction is never changed, and the shins never go forward."""
        two, _ = jumper(pl.JUMP_PUSH_RANGE_NM[1])
        to_flight(two, knee_v=-30.0)
        sent = [dict(two.legs)]
        while two.state == "jump":
            sent.append(step(two, legs(SCRIPT.land_m, two._along(SCRIPT.land_m))))
        straightest = pl.leg_for(two._along(SCRIPT.takeoff_m), SCRIPT.takeoff_m)[1]
        for cmds in sent[:-1]:
            if cmds["knee_right"].kp > 0.0:
                self.assertGreaterEqual(cmds["knee_right"].p, straightest - 1e-6)
            self.assertGreater(cmds["knee_right"].p, 0.5)
            shin = cmds["hip_pitch_right"].p - cmds["knee_right"].p
            self.assertLess(shin, 0.0)


class Sequence(unittest.TestCase):
    def test_crouch_hold_push_brake_flight_and_back(self):
        two, _ = jumper()
        two.press(UP, 0.0, True)
        step(two, legs(0.2035, 0.0))
        phases = [two.phase]
        fb = legs(SCRIPT.crouch_m)
        while two.phase in ("crouch", "hold"):
            step(two, fb)
            phases.append(two.phase)
        to_brake = pl.leg_for(two._along(SCRIPT.takeoff_m), SCRIPT.takeoff_m)[1]
        down = 2.0 * pl.LEG_LINK_M * math.cos(to_brake / 2.0)
        step(two, legs(down, two._along(down), knee_v=-20.0))
        phases.append(two.phase)
        while two.phase in ("brake", "flight"):
            step(two, legs(SCRIPT.land_m, two._along(SCRIPT.land_m)))
            phases.append(two.phase or two.state)
        order = [p for i, p in enumerate(phases) if i == 0 or p != phases[i - 1]]
        self.assertEqual(
            order, ["crouch", "hold", "push", "brake", "flight", "drive"], order
        )
        words = " | ".join(two.events)
        for part in ("pressed", "crouching", "jump:", "braking at", "handed back"):
            self.assertIn(part, words)
        self.assertIs(two.active, two.driving)
        self.assertTrue(two.busy)

    def test_the_crouch_asks_the_driving_policy_for_its_lowest_height(self):
        two, answers = jumper()
        two.press(UP, 0.0, True)
        heights = []
        for _ in range(40):
            step(two, legs(0.2035, 0.0))
            heights.append(float(answers.seen[-1][8]))
        self.assertAlmostEqual(heights[0], 0.2035 - SCRIPT.crouch_rate_m_s * 0.01, 4)
        self.assertAlmostEqual(heights[-1], SCRIPT.crouch_m, 6)
        self.assertTrue(all(b <= a for a, b in zip(heights, heights[1:])))
        # Asked for no speed and no turn while it does.
        self.assertTrue(all(o[6] == 0.0 and o[7] == 0.0 for o in answers.seen))

    def test_the_hold_waits_for_balance(self):
        """Further off balance than it allows it does not push; brought over the axles it
        does."""
        two, _ = jumper()
        two.press(UP, 0.0, True)
        # The axles 50 mm ahead, the centre of mass 31 mm behind them: the legs' own
        # mass goes with them.
        forward = pl.under_mass(SCRIPT.crouch_m, (0.0, 1.0)) + 0.05
        hip, knee = pl.leg_for(forward, SCRIPT.crouch_m)
        self.assertLess(pl.off_balance(hip, knee, (0.0, 1.0)), -SCRIPT.over_m)
        off = legs(SCRIPT.crouch_m, forward)
        for _ in range(int(1.0 / pl.PERIOD_S)):
            step(two, off)
        self.assertEqual(two.phase, "hold")
        for _ in range(int(0.3 / pl.PERIOD_S)):
            step(two, legs(SCRIPT.crouch_m))
        self.assertEqual(two.phase, "push")

    def test_the_hold_waits_for_steady_not_still(self):
        """Rolling steadily it pushes; its speed changing, it does not."""
        two, _ = jumper()
        two.press(UP, 0.0, True)
        for k in range(int(1.0 / pl.PERIOD_S)):
            step(two, legs(SCRIPT.crouch_m, wheel_v=4.0 * (-1) ** k))
        self.assertEqual(two.phase, "hold")
        for _ in range(int(0.3 / pl.PERIOD_S)):
            step(two, legs(SCRIPT.crouch_m, wheel_v=25.0))
        self.assertEqual(two.phase, "push")
        self.assertIn("rolling +1.00 m/s", two.events[-1])

    def test_never_steady_and_it_stands_up_again(self):
        two, _ = jumper()
        two.press(UP, 0.0, True)
        n = 0
        while two.state != "drive":
            step(two, legs(SCRIPT.crouch_m, wheel_v=5.0 * (-1) ** n))
            n += 1
        self.assertIn("never steady", two.events[-1])
        self.assertAlmostEqual(
            n * pl.PERIOD_S, SCRIPT.hold_most_s + pl.PERIOD_S, delta=0.3
        )
        self.assertFalse(any(e.startswith("jump:") for e in two.events))

    def test_tipped_crouching_and_it_gives_up(self):
        two, _ = jumper()
        two.press(UP, 0.0, True)
        a = math.radians(pl.JUMP_TILT_DEG + 5.0)
        g = np.array([math.sin(a), 0.0, -math.cos(a)])
        step(two, legs(0.19), g=g)
        self.assertEqual(two.state, "drive")
        self.assertIn("tilted", two.events[-1])

    def test_handed_back_told_it_asked_for_what_the_script_did(self):
        two, answers = jumper()
        to_flight(two)
        last = dict(two.legs)
        for _ in range(int(0.2 / pl.PERIOD_S)):
            fb = legs(SCRIPT.land_m, two._along(SCRIPT.land_m), knee_nm=-1.0)
            step(two, fb)
            if two.state == "drive":
                break
            last = dict(two.legs)
        # What the driving policy is shown as its last outputs as it takes over.
        d = two.driving
        shown = answers.seen[-1][19:23]
        asked = d.crouch + d.leg_scale * shown
        for k, j in enumerate(st.LEGS):
            self.assertAlmostEqual(float(asked[k]), last[j].p, places=5)


class Refusals(unittest.TestCase):
    def test_tilted(self):
        two, _ = jumper()
        a = math.radians(20.0)
        g = np.array([math.sin(a), 0.0, -math.cos(a)])
        self.assertIn("tilted", two.press(g, 0.0, True))
        self.assertEqual(two.state, "drive")

    def test_a_wheel_off_the_floor(self):
        self.assertIn("floor", jumper()[0].press(UP, 0.0, False))

    def test_already_jumping(self):
        two, _ = jumper()
        two.press(UP, 0.0, True)
        self.assertIn("already", two.press(UP, 0.0, True))

    def test_driving_it_crouches_at_once(self):
        two, _ = jumper()
        self.assertIsNone(two.press(UP, 1.2, True))
        self.assertEqual(two.state, "crouch")
        self.assertIsNone(two.speed_cap)
        self.assertFalse(two.assist)

    def test_faster_than_it_jumps_it_brakes_to_under_the_top_first(self):
        two, answers = jumper()
        top = pl.JUMP_RUN_TOP_M_S
        self.assertIsNone(two.press(UP, top + 0.3, True))
        self.assertEqual(two.state, "braking")
        self.assertEqual(two.speed_cap, top)
        self.assertTrue(two.assist)
        # On 40 mm wheels, then slowing to under the top, and not to a stop.
        fast = (top + 0.3) / 0.04
        step(two, legs(0.2035, 0.0, wheel_v=fast), speed=top)
        self.assertEqual(two.state, "braking")
        slower = (top - 0.1) / 0.04
        for _ in range(int(pl.JUMP_SLOWED_S / pl.PERIOD_S) + 1):
            step(two, legs(0.2035, 0.0, wheel_v=slower), speed=top)
        self.assertEqual(two.state, "crouch")
        self.assertFalse(two.assist)
        self.assertIsNone(two.speed_cap)


def heard(two, fb, held, loaded=True, w=STILL, speed=0.0, turn=0.0) -> dict:
    """One step as balance.py makes it: the button told, then the step."""
    two.button(held, loaded)
    obs = two.observe(fb, w, UP, speed, turn, 0.2035)
    return two.decide(obs)


def seconds(s: float) -> int:
    return round(s / pl.PERIOD_S)


class Button(unittest.TestCase):
    """THE BUTTON: pressed with A held it crouches and waits, however long; let go, it
    jumps as a press without the bit does; the controller lost while it waits, it stands
    up and never jumps."""

    def held_in_the_crouch(self, s: float = 5.0):
        two, answers = jumper()
        self.assertIsNone(two.press(UP, 0.0, True, held=True))
        self.assertTrue(two.waiting)
        for _ in range(seconds(s)):
            heard(two, legs(SCRIPT.crouch_m), True)
        self.assertEqual((two.state, two.phase), ("crouch", "hold"), two.events)
        return two, answers

    def test_held_it_waits_however_long_and_jumps_once_let_go(self):
        two, _ = self.held_in_the_crouch(30.0)
        self.assertTrue(two.waiting)
        self.assertFalse(
            any(e.startswith(("jump:", "handed back")) for e in two.events)
        )
        heard(two, legs(SCRIPT.crouch_m), False)
        # Ready all along, it goes at once.
        self.assertEqual(two.phase, "push", two.events)
        self.assertIn("let go after 30.0", " | ".join(two.events))

    def test_let_go_it_gives_up_as_long_after_the_let_go_as_a_press_without(self):
        two, _ = self.held_in_the_crouch(4.0)
        n = 0
        while two.state != "drive":
            heard(two, legs(SCRIPT.crouch_m, wheel_v=5.0 * (-1) ** n), n == 0)
            n += 1
        self.assertIn("never steady", two.events[-1])
        self.assertAlmostEqual(n * pl.PERIOD_S, SCRIPT.hold_most_s, delta=0.05)
        self.assertFalse(any(e.startswith("jump:") for e in two.events))

    def test_let_go_on_the_way_down_it_jumps_once_crouched(self):
        two, _ = jumper()
        two.press(UP, 0.0, True, held=True)
        for _ in range(3):
            heard(two, legs(0.2035, 0.0), True)
        heard(two, legs(0.2035, 0.0), False)
        self.assertFalse(two.waiting)
        self.assertIn("on the way down", two.events[-1])
        n = 0
        while two.state == "crouch":
            heard(two, legs(SCRIPT.crouch_m), False)
            n += 1
        self.assertEqual(two.phase, "push", two.events)
        self.assertLess(n * pl.PERIOD_S, 0.3)

    def test_a_press_without_the_bit_jumps_as_every_press_did(self):
        """A tap between two of the controller's frames, or a controller from before."""
        two, _ = jumper()
        two.press(UP, 0.0, True, held=False)
        self.assertFalse(two.waiting)
        n = 0
        while two.state == "crouch":
            heard(two, legs(SCRIPT.crouch_m), False)
            n += 1
        self.assertEqual(two.phase, "push")
        self.assertLess(n * pl.PERIOD_S, 0.3)
        self.assertNotIn("held", " | ".join(two.events))

    def test_the_controller_lost_while_held_and_it_stands_up(self):
        for after in (0.05, 3.0):
            two, answers = jumper()
            two.press(UP, 0.0, True, held=True)
            for _ in range(seconds(after)):
                heard(two, legs(SCRIPT.crouch_m), True)
            heard(two, legs(SCRIPT.crouch_m), None)
            self.assertEqual(two.state, "drive")
            self.assertFalse(two.waiting)
            self.assertIn("controller went quiet", two.events[-1])
            self.assertTrue(two.events[-1].startswith("handed back"))
            for _ in range(seconds(2.0)):
                heard(two, legs(SCRIPT.crouch_m), False)
            self.assertFalse(any(e.startswith("jump:") for e in two.events))
            # Standing up again from the crouch, at the rise's rate.
            self.assertGreater(float(answers.seen[-1][8]), SCRIPT.crouch_m + 0.03)

    def test_the_controller_lost_while_held_braking_and_it_drives_on(self):
        two, _ = jumper()
        two.press(UP, pl.JUMP_RUN_TOP_M_S + 0.3, True, held=True)
        self.assertEqual(two.state, "braking")
        heard(two, legs(0.2035, 0.0, wheel_v=45.0), None, speed=1.5)
        self.assertEqual(two.state, "drive")
        self.assertIsNone(two.speed_cap)
        self.assertIn("controller went quiet", two.events[-1])

    def test_held_braking_and_never_slow_enough_it_waits_no_more(self):
        two, _ = jumper()
        fast = pl.JUMP_RUN_TOP_M_S + 0.3
        two.press(UP, fast, True, held=True)
        while two.state == "braking":
            heard(two, legs(0.2035, 0.0, wheel_v=fast / 0.04), True, speed=fast)
        self.assertIn("refused: still at", two.events[-1])
        self.assertFalse(two.waiting)
        self.assertIsNone(two.speed_cap)
        heard(two, legs(0.2035, 0.0), None)
        self.assertEqual(two.since_back, math.inf)

    def test_lost_after_the_let_go_it_jumps_as_before(self):
        two, _ = jumper()
        two.press(UP, 0.0, True, held=True)
        heard(two, legs(0.2035, 0.0), False)
        while two.state == "crouch":
            heard(two, legs(SCRIPT.crouch_m), None)
        self.assertEqual(two.phase, "push")

    def test_steered_while_held_and_straight_on_once_let_go(self):
        two, answers = jumper()
        two.press(UP, 0.4, True, held=True)
        rolling = 0.4 / 0.04
        for _ in range(seconds(1.0)):
            heard(
                two, legs(SCRIPT.crouch_m, wheel_v=rolling), True, speed=0.4, turn=1.0
            )
            self.assertEqual(float(answers.seen[-1][6]), np.float32(0.4))
            self.assertEqual(float(answers.seen[-1][7]), 1.0)
        # Let go, a little unsteady, so that it holds on and asks the driving policy.
        fb = legs(SCRIPT.crouch_m, wheel_v=rolling + 5.0)
        heard(two, fb, False, speed=0.4, turn=1.0)
        self.assertEqual(two.phase, "hold")
        self.assertEqual(float(answers.seen[-1][7]), 0.0)

    def test_let_go_it_waits_for_the_turn_to_die_away_and_both_wheels_down(self):
        turning = np.array([0.0, 0.0, 1.0])
        for w, loaded in ((turning, True), (STILL, False)):
            two, _ = self.held_in_the_crouch(1.0)
            for k in range(seconds(1.0)):
                heard(two, legs(SCRIPT.crouch_m), k == 0, loaded=loaded, w=w)
            self.assertEqual(two.phase, "hold", (w, loaded))
            for _ in range(seconds(0.1)):
                heard(two, legs(SCRIPT.crouch_m), False)
            self.assertEqual(two.phase, "push", (w, loaded))

    def test_held_in_the_crouch_a_lift_is_looked_for(self):
        """As driving once it has been held there JUMP_SETTLE_S; not on the way down, and
        not once let go of, as a press without the bit."""
        two, _ = jumper()
        two.press(UP, 0.0, True, held=True)
        busy = []
        while two.phase != "push":
            held = len(busy) < seconds(2.0)
            heard(two, legs(SCRIPT.crouch_m if busy else 0.2035, 0.0), held)
            busy.append((two.phase, two.pt, two.waiting, two.busy))
            self.assertLess(len(busy), 500)
        for phase, pt, waiting, b in busy[:-1]:
            looks = waiting and phase == "hold" and pt >= pl.JUMP_SETTLE_S
            self.assertEqual(b, not looks, (phase, pt, waiting))
        self.assertTrue(any(not b for *_, b in busy))
        self.assertTrue(two.busy)

    def test_held_trim_hold_and_the_speed_cap_act_as_driving(self):
        two, _ = self.held_in_the_crouch(1.0)
        self.assertTrue(two.assist)
        self.assertEqual(two.speed_cap, pl.JUMP_RUN_TOP_M_S)
        heard(two, legs(SCRIPT.crouch_m, wheel_v=5.0), False)
        self.assertEqual(two.state, "crouch")
        self.assertFalse(two.assist)
        self.assertIsNone(two.speed_cap)

    def test_a_jump_policy_jumps_at_the_press_held_or_not(self):
        two, _, _ = pair()
        self.assertIsNone(two.press(UP, 0.0, True, held=True))
        two.button(True, True)
        self.assertEqual(two.state, "crouch")
        two.button(None, True)
        self.assertEqual(two.state, "crouch")

    def through_balance(self, messages):
        """balance.py's Operator and jump_presses, one step per (time, jump, live), and
        the jump stepped after each, as powered does: what was logged."""
        two, _ = jumper()
        args = SimpleNamespace(height=None, max_speed=1.0, max_turn=2.0, drive=False)
        op = balance.Operator(None, D8 | {"default_height": 0.2035}, args)
        notes = []
        rig = SimpleNamespace(
            latest=legs(SCRIPT.crouch_m), writer=SimpleNamespace(write=notes.append)
        )
        view = balance.View()
        view.step = {"g": UP, "w": STILL}
        op.last = (0.0, {"forward": 0.0, "turn": 0.0, "live": True, "jump": 0})
        op.reset()
        for now, jump, live in messages:
            if jump is not None:
                m = {"forward": 0.0, "turn": 0.0, "live": live, "jump": jump}
                op.last = (now, m)
            op.ask(now)
            balance.jump_presses(two, op, rig, view, None, now)
            step(two, legs(SCRIPT.crouch_m))
        return two, [n["jump"] for n in notes]

    def test_balance_tells_it_held_and_let_go(self):
        held = 1 | balance.JUMP_HELD
        steps = [(k * 0.01, held, True) for k in range(300)]
        steps += [(3.0 + k * 0.01, 1, True) for k in range(5)]
        two, said = self.through_balance(steps)
        self.assertEqual(two.phase, "push", said)
        self.assertTrue(any(w.startswith("let go after 3.00") for w in said), said)

    def test_balance_stands_it_up_when_the_controller_goes_quiet_held(self):
        held = 1 | balance.JUMP_HELD
        steps = [(k * 0.01, held, True) for k in range(100)]
        # Nothing more heard: stale 0.2 s on.
        steps += [(1.0 + k * 0.01, None, True) for k in range(100)]
        two, said = self.through_balance(steps)
        self.assertEqual(two.state, "drive")
        self.assertIn("controller went quiet", said[-1])
        self.assertFalse(any(w.startswith("jump:") for w in said))
        # And Linux taking it away, held: not live.
        two, said = self.through_balance(
            [(0.0, held, True), (0.01, held, True), (0.02, held, False)]
        )
        self.assertEqual(two.state, "drive")
        self.assertIn("controller went quiet", said[-1])


class LevelPush(unittest.TestCase):
    """The wheels drive forward through the push, both alike, more the further ahead the
    centre of mass starts, and only through the push."""

    def pushing(self, back_m: float = 0.0):
        """Held with the axles `back_m` behind where they balance it, until it pushes."""
        two, _ = jumper()
        two.press(UP, 0.0, True)
        forward = pl.under_mass(SCRIPT.crouch_m, (0.0, 1.0)) - back_m
        fb = legs(SCRIPT.crouch_m, forward)
        sent = []
        while two.phase != "push":
            sent.append(step(two, fb))
            self.assertLess(len(sent), 300, two.events)
        ahead = pl.off_balance(*pl.leg_for(forward, SCRIPT.crouch_m), (0.0, 1.0))
        return two, sent[-1], ahead

    def test_forward_and_both_alike(self):
        _, cmds, _ = self.pushing()
        right, left = cmds["wheel_drive_right"].t, cmds["wheel_drive_left"].t
        self.assertEqual(right, left)
        self.assertAlmostEqual(right, SCRIPT.level_nm, delta=0.01)
        self.assertLess(right, st.PEAK_NM)

    def test_more_with_the_centre_of_mass_ahead(self):
        levels = []
        for back in (-0.02, 0.0, 0.02):
            two, _, ahead = self.pushing(back)
            want = SCRIPT.level_nm + SCRIPT.level_nm_per_m * ahead
            self.assertAlmostEqual(two.level, want, places=6)
            levels.append(two.level)
        self.assertLess(levels[0], levels[1])
        self.assertLess(levels[1], levels[2])
        self.assertIn("mm off balance", two.events[-1])
        self.assertIn(f"the wheels {two.level:+.2f} Nm", two.events[-1])

    def test_in_proportion_to_the_push(self):
        levels = {}
        for push in pl.JUMP_PUSH_RANGE_NM:
            two, _ = jumper(push)
            two.press(UP, 0.0, True)
            while two.phase != "push":
                step(two, legs(SCRIPT.crouch_m))
            levels[push] = two.level
        lo, hi = pl.JUMP_PUSH_RANGE_NM
        self.assertAlmostEqual(levels[lo], SCRIPT.level_nm * lo / pl.JUMP_PUSH_NM, 6)
        self.assertAlmostEqual(levels[hi], SCRIPT.level_nm * hi / pl.JUMP_PUSH_NM, 6)

    def test_only_in_the_push(self):
        """The same jump with no level push sends the wheels the same in the brake and
        the flight, and differs by the level push in the push."""
        level = jumper()[0]
        plain = pl.ScriptedJump(
            pl.Balancer(Answers(D8)), script=dataclasses.replace(SCRIPT, level_nm=0.0)
        )
        sent = {}
        for name, two in (("level", level), ("plain", plain)):
            two.press(UP, 0.0, True)
            out = []

            def sending(fb, two=two, out=out):
                cmds = step(two, fb)
                out.append((two.phase, cmds))

            while two.phase != "push":
                sending(legs(SCRIPT.crouch_m))
            brake = pl.leg_for(two._along(SCRIPT.takeoff_m), SCRIPT.takeoff_m)[1]
            down = 2.0 * pl.LEG_LINK_M * math.cos(brake / 2.0)
            sending(legs(SCRIPT.crouch_m))
            sending(legs(down, two._along(down), knee_v=-20.0))
            for _ in range(8):
                sending(legs(SCRIPT.land_m, two._along(SCRIPT.land_m)))
            sent[name] = out
        phases = set()
        for (phase, a), (_, b) in zip(sent["level"], sent["plain"], strict=True):
            phases.add(phase)
            diff = a["wheel_drive_right"].t - b["wheel_drive_right"].t
            if phase == "push":
                self.assertAlmostEqual(diff, SCRIPT.level_nm, places=6)
            elif phase in ("brake", "flight"):
                self.assertAlmostEqual(diff, 0.0, places=9)
        self.assertTrue({"push", "brake", "flight"} <= phases, phases)


class Brake(unittest.TestCase):
    def test_the_hips_held_whatever_the_knees_do(self):
        """Following the knees as they overshot swung the legs, and the torso, in the
        air: the hips are held where the take-off height puts them."""
        two, _ = jumper()
        to_push(two)
        brake = pl.leg_for(two._along(SCRIPT.takeoff_m), SCRIPT.takeoff_m)[1]
        down = 2.0 * pl.LEG_LINK_M * math.cos(brake / 2.0)
        step(two, legs(down, two._along(down), knee_v=-20.0))
        self.assertEqual(two.phase, "brake")
        hip = pl.leg_for(two._along(SCRIPT.takeoff_m), SCRIPT.takeoff_m)[0]
        for overshoot in (0.0, 0.1, 0.2):
            fb = legs(down + overshoot * 0.05, two._along(down), knee_v=-10.0)
            cmds = step(two, fb)
            if two.phase != "brake":
                break
            self.assertAlmostEqual(cmds["hip_pitch_right"].p, hip, places=6)


class Driving(unittest.TestCase):
    """Pressed while driving, it jumps at the speed it is going: the driving policy goes on
    being asked for it through the crouch, is told the speed it pushed at through the push
    and the flight, and is asked for the operator's again as it lands."""

    def test_the_speed_asked_through_the_jump(self):
        two, answers = jumper()
        self.assertIsNone(two.press(UP, 1.0, True))
        rolling = 1.0 / 0.04
        while two.phase in ("crouch", "hold"):
            step(two, legs(SCRIPT.crouch_m, wheel_v=rolling), speed=1.0)
            self.assertEqual(float(answers.seen[-1][6]), np.float32(1.0))
            self.assertEqual(float(answers.seen[-1][7]), 0.0)
            self.assertLess(len(answers.seen), 300, two.events)
        self.assertEqual(two.phase, "push")
        # The operator lets go mid-jump: the driving policy is told the speed it pushed
        # at until it lands, and the operator's from then on.
        brake = pl.leg_for(two._along(SCRIPT.takeoff_m), SCRIPT.takeoff_m)[1]
        down = 2.0 * pl.LEG_LINK_M * math.cos(brake / 2.0)
        step(two, legs(down, two._along(down), knee_v=-20.0), speed=0.4)
        while two.state == "jump":
            fb = legs(SCRIPT.land_m, two._along(SCRIPT.land_m), knee_nm=-1.0)
            step(two, fb, speed=0.4)
            if two.state == "jump":
                self.assertEqual(float(answers.seen[-1][6]), np.float32(1.0))
        step(two, legs(SCRIPT.land_m), speed=0.4)
        self.assertEqual(float(answers.seen[-1][6]), np.float32(0.4))

    def test_the_wheels_hold_their_speed_over_the_floor(self):
        """In the air each wheel holds the speed it pushed at: one slower is driven up,
        one faster held back, so that it lands rolling at it."""
        sent = {}
        for wheel_v in (20.0, 25.0, 30.0):
            two, _ = jumper()
            two.press(UP, 1.0, True)
            rolling = 1.0 / 0.04
            while two.phase != "push":
                step(two, legs(SCRIPT.crouch_m, wheel_v=rolling), speed=1.0)
            brake = pl.leg_for(two._along(SCRIPT.takeoff_m), SCRIPT.takeoff_m)[1]
            down = 2.0 * pl.LEG_LINK_M * math.cos(brake / 2.0)
            fb = legs(down, two._along(down), knee_v=-20.0, wheel_v=rolling)
            step(two, fb, speed=1.0)
            while two.phase == "brake":
                fb = legs(
                    SCRIPT.takeoff_m, two._along(SCRIPT.takeoff_m), wheel_v=rolling
                )
                step(two, fb)
            # Past the legs' drawing up, when their rotors' turning is done.
            for _ in range(int(SCRIPT.tuck_s / pl.PERIOD_S) + 2):
                fb = legs(SCRIPT.land_m, two._along(SCRIPT.land_m), wheel_v=wheel_v)
                cmds = step(two, fb)
            self.assertEqual(two.phase, "flight")
            self.assertEqual(cmds["wheel_drive_right"].t, cmds["wheel_drive_left"].t)
            sent[wheel_v] = cmds["wheel_drive_right"].t
        self.assertGreater(sent[20.0], 0.05)
        self.assertAlmostEqual(sent[25.0], 0.0, places=6)
        self.assertLess(sent[30.0], -0.05)

    def test_the_lean_goes_on_through_the_jump(self):
        """balance.py's lean, on the speed it is going, is the driving policy's all the
        way: never dropped to none as the jump starts and back as it lands."""
        net = Answers(D8)
        bal = balance.LeanedBalancer(net, lean_per_m_s=1.67, gyro_mean_of=1)
        two = pl.ScriptedJump(bal)
        two.press(UP, 1.2, True)
        rolling = 1.2 / 0.04
        leans = []
        while two.state != "drive" and len(leans) < 200:
            step(two, legs(SCRIPT.crouch_m, wheel_v=rolling), speed=1.2)
            leans.append(bal.lean_deg)
        self.assertGreater(len(leans), 10)
        for lean in leans:
            self.assertAlmostEqual(lean, 1.67 * 1.2, places=6)


class Touchdown(unittest.TestCase):
    def flying(self):
        two, _ = jumper()
        to_flight(two)
        self.assertGreater(two.flight_s, 0.05)
        return two

    def test_felt_by_the_knees_torque(self):
        two = self.flying()
        early = int(SCRIPT.earliest * two.flight_s / pl.PERIOD_S) + 1
        air = legs(SCRIPT.land_m, two._along(SCRIPT.land_m))
        for _ in range(early):
            step(two, air)
        self.assertEqual(two.phase, "flight")
        step(two, legs(SCRIPT.land_m, two._along(SCRIPT.land_m), knee_nm=-0.8))
        self.assertEqual(two.state, "drive")
        self.assertIn("landed", two.events[-1])

    def test_felt_by_the_knees_folding_past_where_asked(self):
        two = self.flying()
        early = int(SCRIPT.earliest * two.flight_s / pl.PERIOD_S) + 1
        for _ in range(early):
            step(two, legs(SCRIPT.land_m, two._along(SCRIPT.land_m)))
        hip, knee = pl.leg_for(two._along(SCRIPT.land_m), SCRIPT.land_m)
        pressed = legs(SCRIPT.land_m, two._along(SCRIPT.land_m), knee_v=5.0)
        for j in ("knee_right", "knee_left"):
            pressed[j] = st.Fb(at=0.0, p=knee + 0.03, v=5.0, tau=0.0)
        step(two, pressed)
        self.assertEqual(two.state, "drive")

    def test_not_believed_in_the_first_of_the_flight(self):
        """In the first part of a flight the knees ring from the brake, and read like a
        landing: that is not one."""
        two = self.flying()
        ringing = legs(SCRIPT.land_m, two._along(SCRIPT.land_m), knee_nm=-1.5)
        step(two, ringing)
        step(two, ringing)
        self.assertEqual(two.phase, "flight")

    def test_ringing_back_towards_the_target_is_not_a_landing(self):
        two = self.flying()
        for _ in range(int(SCRIPT.earliest * two.flight_s / pl.PERIOD_S) + 1):
            step(two, legs(SCRIPT.land_m, two._along(SCRIPT.land_m)))
        hip, knee = pl.leg_for(two._along(SCRIPT.land_m), SCRIPT.land_m)
        back = legs(SCRIPT.land_m, two._along(SCRIPT.land_m))
        for j in ("knee_right", "knee_left"):
            back[j] = st.Fb(at=0.0, p=knee + 0.12, v=-4.0, tau=0.5)
        step(two, back)
        self.assertEqual(two.phase, "flight")

    def test_taken_as_landed_at_the_time_out(self):
        two = self.flying()
        latest = SCRIPT.latest * two.flight_s + SCRIPT.latest_s
        n = 0
        while two.state == "jump":
            step(two, legs(SCRIPT.land_m, two._along(SCRIPT.land_m)))
            n += 1
            self.assertLess(n, 200)
        self.assertAlmostEqual(n * pl.PERIOD_S, latest, delta=0.011)
        self.assertIn("no landing felt", two.events[-1])

    def test_after_the_hand_back_the_height_rises_from_where_it_landed(self):
        two, answers = jumper()
        to_flight(two)
        while two.state == "jump":
            step(two, legs(SCRIPT.land_m, two._along(SCRIPT.land_m), knee_nm=-1.0))
        heights = []
        for _ in range(60):
            step(two, legs(SCRIPT.land_m), height=0.2035)
            heights.append(float(answers.seen[-1][8]))
        self.assertLess(heights[0], 0.18)
        self.assertAlmostEqual(heights[-1], 0.2035, places=6)
        self.assertTrue(all(b >= a for a, b in zip(heights, heights[1:])))


class TheRobot(unittest.TestCase):
    def test_the_masses_are_the_urdfs(self):
        root = ET.parse(ROOT / "simulation" / "urdf" / "wheeled_biped.urdf").getroot()
        links = {}
        for link in root.iter("link"):
            inertial = link.find("inertial")
            if inertial is None:
                continue
            xyz = [float(v) for v in inertial.find("origin").get("xyz").split()]
            links[link.get("name")] = (float(inertial.find("mass").get("value")), xyz)
        mass, com = links["base_link"]
        self.assertAlmostEqual(pl.TORSO_KG, mass, places=5)
        hip_z = 0.0685
        self.assertAlmostEqual(pl.TORSO_COM_M[1], com[2] + hip_z, places=5)
        self.assertAlmostEqual(pl.THIGH_KG, links["thigh_right"][0], places=5)
        self.assertAlmostEqual(pl.THIGH_COM_M, -links["thigh_right"][1][2], places=5)
        self.assertAlmostEqual(pl.SHIN_KG, links["shin_right"][0], places=5)
        self.assertAlmostEqual(pl.SHIN_COM_M, -links["shin_right"][1][2], places=5)
        self.assertAlmostEqual(pl.WHEEL_KG, links["wheel_right"][0], places=5)
        total = sum(m for m, _ in links.values())
        self.assertAlmostEqual(pl.ROBOT_KG, total, places=4)

    def test_the_legs_there_and_back(self):
        for hip, knee in ((0.25, 0.5), (0.75, 1.33), (0.1, 0.9), (0.4, 0.6)):
            ax, az = pl.axle_at(hip, knee)
            h2, k2 = pl.leg_for(ax, -az)
            self.assertAlmostEqual(hip, h2, places=9)
            self.assertAlmostEqual(knee, k2, places=9)
            # leg_heights agrees.
            fb = {j: st.Fb(0.0, hip if "hip" in j else knee, 0.0, 0.0) for j in st.LEGS}
            self.assertAlmostEqual(pl.leg_heights(fb)[0], -az, places=9)

    def test_the_centre_of_mass_over_the_axles_as_asked(self):
        for deg in (-5.0, 0.0, 5.0):
            a = math.radians(deg)
            up = (-math.sin(a), math.cos(a))
            for down in (0.165, 0.18, 0.195):
                hip, knee = pl.leg_for(pl.under_mass(down, up), down)
                self.assertAlmostEqual(pl.off_balance(hip, knee, up), 0.0, places=9)


class Settings(unittest.TestCase):
    def test_balance_takes_scripted_for_a_jump_policy(self):
        self.assertEqual(balance.SCRIPTED, "scripted")

    def test_the_launcher_asks_for_the_scripted_jump_and_keeps_the_lean(self):
        args = SimpleNamespace(phase_file=Path("/dev/shm/x"), rt=False, jump="scripted")
        command = launcher.balance_command(args)
        at = command.index("--jump-policy")
        self.assertEqual(command[at + 1], "scripted")
        push = float(command[command.index("--jump-push") + 1])
        lo, hi = pl.JUMP_PUSH_RANGE_NM
        self.assertTrue(lo <= push <= hi)
        self.assertEqual(command[command.index("--lean-per-m-s") + 1], "1.67")

    def test_the_launcher_sets_the_level_push_inside_its_range(self):
        args = SimpleNamespace(phase_file=Path("/dev/shm/x"), rt=False, jump="scripted")
        command = launcher.balance_command(args)
        level = float(command[command.index("--jump-level-nm") + 1])
        lo, hi = balance.JUMP_LEVEL_RANGE_NM
        self.assertTrue(lo <= level <= hi)
        self.assertEqual(balance.jump_script(level).level_nm, level)

    def test_the_level_push_is_mujoco_s_unless_set_and_held_to_its_range(self):
        self.assertEqual(balance.jump_script(), pl.JumpScript())
        self.assertEqual(balance.jump_script(None).level_nm, pl.JumpScript.level_nm)
        lo, hi = balance.JUMP_LEVEL_RANGE_NM
        self.assertEqual(balance.jump_script(9.0).level_nm, hi)
        self.assertEqual(balance.jump_script(-1.0).level_nm, lo)
        # Nothing else of the script moves with it.
        moved = dataclasses.replace(balance.jump_script(0.35), level_nm=SCRIPT.level_nm)
        self.assertEqual(moved, SCRIPT)

    def test_or_no_jump_at_all(self):
        args = SimpleNamespace(phase_file=Path("/dev/shm/x"), rt=False, jump="none")
        self.assertNotIn("--jump-policy", launcher.balance_command(args))


if __name__ == "__main__":
    unittest.main()
