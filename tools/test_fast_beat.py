# /// script
# requires-python = ">=3.11"
# dependencies = ["pyserial>=3.5"]
# ///
"""diagd's side of the fast speed mode's heartbeat: the Pi's LED written as the kernel's
pattern trigger wants it, on a sysfs LED faked in a folder, and the word expiring.
Free, offline, no robot.

    uv run tools/test_fast_beat.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbc"))

import diagd  # noqa: E402


def fake_led(folder: Path, triggers: str) -> Path:
    led = folder / "red_status"
    led.mkdir()
    (led / "trigger").write_text(triggers)
    (led / "max_brightness").write_text("255\n")
    for name in ("invert", "brightness", "pattern", "delay_on", "delay_off"):
        (led / name).write_text("0")
    return led


class FastBeat(unittest.TestCase):
    def test_the_pattern_is_three_flashes_held_and_stepped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = fake_led(Path(folder), "none timer [heartbeat] pattern")
            led = diagd.Led(str(path), inverted=False)
            led.show("fast")
            self.assertEqual((path / "trigger").read_text(), "pattern")
            steps = (path / "pattern").read_text().split()
            pairs = list(zip(steps[::2], steps[1::2], strict=True))
            self.assertEqual(len(pairs), 2 * len(diagd.FAST_BEAT))
            lit = [p for p in pairs[::2] if p[0] == "255"]
            self.assertEqual(len(lit), 3)
            self.assertTrue(all(p[1] == "0" for p in pairs[1::2]))
            total = sum(int(p[1]) for p in pairs)
            self.assertEqual(total, sum(ms for _, ms in diagd.FAST_BEAT))

    def test_inverted_lit_is_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            path = fake_led(Path(folder), "none [heartbeat] pattern")
            diagd.Led(str(path), inverted=True).show("fast")
            first = (path / "pattern").read_text().split()[0]
            self.assertEqual(first, "0")

    def test_without_the_pattern_trigger_it_beats_as_ever(self):
        with tempfile.TemporaryDirectory() as folder:
            path = fake_led(Path(folder), "none timer [heartbeat]")
            led = diagd.Led(str(path), inverted=False)
            led.show("link")
            led.show("fast")
            self.assertEqual((path / "trigger").read_text(), "heartbeat")
            self.assertEqual(led.shown, "heartbeat")

    def test_the_beat_is_the_controllers(self):
        self.assertEqual(sum(ms for _, ms in diagd.FAST_BEAT), 300 + 6720 // 7)
        self.assertEqual(sum(lit for lit, _ in diagd.FAST_BEAT), 3)

    def test_the_word_expires(self):
        daemon = diagd.Daemon.__new__(diagd.Daemon)
        daemon.lock = diagd.threading.RLock()
        daemon.fast_until = 0.0
        daemon.health_due = diagd.threading.Event()
        daemon.mcu = lambda *a: None
        daemon.check_health = lambda now: self.fail(
            "changed the LED on the asker's thread"
        )
        with patch.object(diagd.time, "monotonic", return_value=100.0):
            daemon.op_indicate(None, {"fast": True})
        self.assertTrue(daemon.health_due.is_set())
        self.assertAlmostEqual(daemon.fast_until, 100.0 + diagd.FAST_HOLD_S)
        daemon.health_due.clear()
        with patch.object(diagd.time, "monotonic", return_value=101.0):
            daemon.op_indicate(None, {"fast": False})
        self.assertTrue(daemon.health_due.is_set())
        self.assertEqual(daemon.fast_until, 0.0)

    def test_the_health_thread_answers_at_once(self):
        """INDICATE leaves the LED to the health thread, which looks straight away
        rather than at its next tick."""
        daemon = diagd.Daemon.__new__(diagd.Daemon)
        daemon.running = True
        daemon.health_due = diagd.threading.Event()
        looked = diagd.threading.Event()
        daemon.check_health = lambda now: looked.set()
        thread = diagd.threading.Thread(target=daemon.health_loop, daemon=True)
        thread.start()
        try:
            looked.wait(1.0)
            looked.clear()
            daemon.health_due.set()
            self.assertTrue(looked.wait(diagd.HEALTH_S / 4))
        finally:
            daemon.running = False
            daemon.health_due.set()
            thread.join(1.0)


if __name__ == "__main__":
    unittest.main()
