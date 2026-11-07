"""diagd sets the port's speed again until the controller answers, without hardware.

On 7 November 2026 the robot powered up with diagd hearing nothing: the controller
streams from power-on, and the Pi's DesignWare UART ignores a change of speed while it
is receiving, so the port stayed at its old speed and both directions were garbled until
diagd was restarted by hand. diagd now sets the speed again every RESET_PORT_S until the
controller's INFO arrives.
"""

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sbc"))

import diag_link as dl
import diagd


def run_timer(daemon: diagd.Daemon, seconds: float) -> None:
    daemon.running = True
    thread = threading.Thread(target=daemon.timer_loop, daemon=True)
    thread.start()
    time.sleep(seconds)
    daemon.running = False
    thread.join(1.0)


INFO = "firmware=diag\nuid=1\nreset=power-on\nimu=0x4B\nina226=0x40\nlast_crash="


class LinkResetTests(unittest.TestCase):
    def daemon(self) -> diagd.Daemon:
        daemon = diagd.Daemon(Mock())
        daemon.log = Mock()
        return daemon

    def test_silence_sets_the_port_again_until_the_controller_answers(self):
        daemon = self.daemon()
        with patch.object(diagd, "RESET_PORT_S", 0.05):
            run_timer(daemon, 0.4)
            silent = daemon.stream.reset.call_count
            self.assertGreaterEqual(silent, 3)
            daemon.heard(dl.INFO, INFO.encode())
            self.assertTrue(daemon.info)
            run_timer(daemon, 0.3)
        self.assertEqual(daemon.stream.reset.call_count, silent)
        said = " ".join(str(c.args[0]) for c in daemon.log.call_args_list)
        self.assertIn("port set again", said)
        self.assertIn(f"up after setting the port again {silent} times", said)

    def test_a_controller_that_answers_at_once_is_left_alone(self):
        daemon = self.daemon()
        daemon.heard(dl.INFO, INFO.encode())
        with patch.object(diagd, "RESET_PORT_S", 0.05):
            run_timer(daemon, 0.3)
        daemon.stream.reset.assert_not_called()

    def test_the_first_reset_waits_its_interval(self):
        daemon = self.daemon()
        run_timer(daemon, 0.3)
        daemon.stream.reset.assert_not_called()

    def test_the_serial_port_goes_through_another_speed_and_back(self):
        seen = []
        port = Mock(baud=1_500_000)
        port.configure.side_effect = lambda parity: seen.append((port.baud, parity))
        stream = diagd.SerialStream.__new__(diagd.SerialStream)
        stream.port = port
        stream.reset()
        self.assertEqual(seen, [(9600, False), (1_500_000, False)])
        self.assertEqual(port.baud, 1_500_000)


if __name__ == "__main__":
    unittest.main()
