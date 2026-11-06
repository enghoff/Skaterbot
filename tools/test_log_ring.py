# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "pyserial>=3.5"]
# ///
"""sbc/balance.py's QueuedWriter: past its budget of full logging it still keeps the last
few seconds of readings, and writes them out ahead of whatever happens next, so a fall
late in a long run comes with what led up to it. Free, offline, no robot.

    uv run tools/test_log_ring.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbc"))

import balance  # noqa: E402


class Ring(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.real_clock = balance.clock
        balance.clock = lambda: self.now
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "run.jsonl"

    def tearDown(self):
        balance.clock = self.real_clock
        self.dir.cleanup()

    def run_for(self, w, until, rate=100.0):
        while self.now < until:
            w.write({"k": "p", "h": round(self.now, 3)})
            self.now += 1.0 / rate

    def records(self, w):
        w.close({"ended": "done"})
        lines = self.path.read_text().splitlines()
        return [json.loads(x) for x in lines[1:-1]]

    def test_everything_inside_the_budget(self):
        w = balance.QueuedWriter(self.path, {"test": "t"})
        self.run_for(w, 10.0)
        w.write({"k": "n", "h": 10.0, "seg": "x"})
        got = self.records(w)
        self.assertAlmostEqual(sum(r["k"] == "p" for r in got), 1000, delta=1)

    def test_past_it_only_the_seconds_before_an_event(self):
        w = balance.QueuedWriter(self.path, {"test": "t"})
        self.run_for(w, balance.LOG_ALL_S + 60.0)
        w.write({"k": "n", "h": self.now, "fell": "tilted 61 degrees"})
        self.run_for(w, self.now + 30.0)
        got = self.records(w)
        late = [r for r in got if r["k"] == "p" and r["h"] > balance.LOG_ALL_S + 0.01]
        self.assertTrue(late, "nothing kept from before the fall")
        fall_at = next(i for i, r in enumerate(got) if r["k"] == "n")
        self.assertTrue(all(i < fall_at for i, r in enumerate(got) if r in late))
        span = late[-1]["h"] - late[0]["h"]
        self.assertGreater(span, balance.LOG_RING_S - 0.05)
        self.assertLessEqual(span, balance.LOG_RING_S + 0.01)
        self.assertAlmostEqual(late[-1]["h"], balance.LOG_ALL_S + 60.0, delta=0.02)

    def test_nothing_after_the_event_is_kept(self):
        w = balance.QueuedWriter(self.path, {"test": "t"})
        self.now = balance.LOG_ALL_S + 1.0
        self.run_for(w, self.now + 2.0)
        w.write({"k": "n", "h": self.now, "lifted": "x"})
        self.run_for(w, self.now + 20.0)
        got = self.records(w)
        self.assertEqual(got[-1]["k"], "n")


if __name__ == "__main__":
    unittest.main()
