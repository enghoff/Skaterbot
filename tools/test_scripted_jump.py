# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "pyserial>=3.5"]
# ///
"""The scripted jump on the robot's side: sbc/policy_loop.py's ScriptedJump behind the A
button, and the settings that choose it in sbc/balance.py and sbc/launcher.py. That both
legs are always sent the same, that nothing it sends leaves the legs' windows or the
motors' torque, the order of its phases, how it feels the floor, and that it hands back
when it does not. Free, offline, no robot and no network: the driving policy is a
stand-in that answers what it is told, and the readings are made up step by step.

    uv run tools/test_scripted_jump.py
"""

from __future__ import annotations

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
from test_jump import DRIVING, Answers  # noqa: E402

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
        """10 mm off balance it does not push; brought over the axles it does."""
        two, _ = jumper()
        two.press(UP, 0.0, True)
        off = legs(SCRIPT.crouch_m, pl.under_mass(SCRIPT.crouch_m, (0.0, 1.0)) - 0.010)
        for _ in range(int(1.0 / pl.PERIOD_S)):
            step(two, off)
        self.assertEqual(two.phase, "hold")
        for _ in range(int(0.3 / pl.PERIOD_S)):
            step(two, legs(SCRIPT.crouch_m))
        self.assertEqual(two.phase, "push")

    def test_never_still_and_it_stands_up_again(self):
        two, _ = jumper()
        two.press(UP, 0.0, True)
        rolling = legs(SCRIPT.crouch_m, wheel_v=5.0)
        n = 0
        while two.state != "drive":
            step(two, rolling)
            n += 1
        self.assertIn("never still", two.events[-1])
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

    def test_moving_it_brakes_to_a_stop_first(self):
        two, answers = jumper()
        self.assertIsNone(two.press(UP, 0.8, True))
        self.assertEqual(two.state, "braking")
        self.assertEqual(two.speed_cap, 0.0)
        self.assertTrue(two.assist)
        # 0.8 m/s on 40 mm wheels, then slowing to under JUMP_STILL_M_S.
        step(two, legs(0.2035, 0.0, wheel_v=20.0))
        self.assertEqual(two.state, "braking")
        for _ in range(int(pl.JUMP_STILL_S / pl.PERIOD_S) + 1):
            step(two, legs(0.2035, 0.0, wheel_v=2.0))
        self.assertEqual(two.state, "crouch")
        self.assertFalse(two.assist)


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

    def test_or_no_jump_at_all(self):
        args = SimpleNamespace(phase_file=Path("/dev/shm/x"), rt=False, jump="none")
        self.assertNotIn("--jump-policy", launcher.balance_command(args))


if __name__ == "__main__":
    unittest.main()
