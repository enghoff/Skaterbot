"""Power-off ordering, failure handling and shutdown-hook guards; no hardware writes.

Run: uv run --with pyserial python -m unittest discover -s tools -p test_poweroff.py
"""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sbc"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))

import diag_link as dl
import diagd
import motor_gui
import robot_poweroff


class PowerOffTests(unittest.TestCase):
    def daemon(self, callback):
        stream = Mock()
        daemon = diagd.Daemon(stream, poweroff=callback)
        client = Mock()
        daemon.owner = client
        return daemon, client, stream

    def test_stop_precedes_shutdown_and_commands_are_blocked(self):
        def schedule():
            decoder = dl.Decoder()
            messages = []
            for call in stream.write.call_args_list:
                messages.extend(decoder.feed(call.args[0]))
            self.assertEqual(messages[-1][0], dl.STOP)

        daemon, client, stream = self.daemon(schedule)
        self.assertTrue(daemon.op_power_off(client, {})["shutting_down"])
        with self.assertRaisesRegex(diagd.Refused, "shutting down"):
            daemon.need_control(client)
        with self.assertRaisesRegex(diagd.Refused, "shutting down"):
            daemon.op_control(client, {"take": True})

    def test_no_control_cannot_shut_down(self):
        callback = Mock()
        daemon, _, stream = self.daemon(callback)
        with self.assertRaises(diagd.Refused):
            daemon.op_power_off(Mock(), {})
        callback.assert_not_called()
        stream.write.assert_not_called()

    def test_schedule_failure_reports_error_and_allows_retry(self):
        daemon, client, stream = self.daemon(Mock(side_effect=OSError("denied")))
        with self.assertRaisesRegex(diagd.Refused, "denied"):
            daemon.op_power_off(client, {})
        self.assertFalse(daemon.shutting_down)
        stream.write.assert_called_once()

    def test_button_uses_same_shutdown_without_client_control(self):
        callback = Mock()
        daemon = diagd.Daemon(Mock(), poweroff=callback)

        def immediate_thread(**kwargs):
            return SimpleNamespace(start=kwargs["target"])

        with patch.object(diagd.threading, "Thread", side_effect=immediate_thread):
            daemon.got_status({"uptime": 1, "t_us": 1000, "off": True})
            daemon.got_status({"uptime": 2, "t_us": 2000, "off": True})
        callback.assert_called_once()
        self.assertTrue(daemon.status_event()["shutting_down"])
        with self.assertRaisesRegex(diagd.Refused, "shutting down"):
            daemon.op_control(Mock(), {"take": True})

    def test_button_retry_still_blocks_motor_commands(self):
        callback = Mock(side_effect=[OSError("busy"), None])
        daemon, client, _ = self.daemon(callback)

        def immediate_thread(**kwargs):
            return SimpleNamespace(start=kwargs["target"])

        with patch.object(diagd.threading, "Thread", side_effect=immediate_thread):
            daemon.got_status({"uptime": 1, "t_us": 1000, "off": True})
            self.assertFalse(daemon.shutting_down)
            with self.assertRaisesRegex(diagd.Refused, "shutting down"):
                daemon.need_control(client)
            daemon.got_status({"uptime": 2, "t_us": 2000, "off": True})
            self.assertEqual(callback.call_count, 1)
            daemon.button_shutdown_retry_at = 0
            daemon.got_status({"uptime": 3, "t_us": 3000, "off": True})
        self.assertEqual(callback.call_count, 2)
        self.assertTrue(daemon.shutting_down)

    def test_shutdown_timer_has_precise_two_second_delay(self):
        with patch.object(diagd.os, "access", return_value=True):
            with patch.object(diagd.subprocess, "run") as run:
                run.return_value = SimpleNamespace(returncode=0)
                diagd.schedule_poweroff()
        command = run.call_args_list[0].args[0]
        self.assertIn("--on-active=2s", command)
        self.assertIn("--timer-property=AccuracySec=100ms", command)
        self.assertEqual(run.call_args_list[1].args[0][-1], "--stop-heartbeat")

    def test_mcu_notified_only_after_shutdown_is_accepted(self):
        daemon, client, stream = self.daemon(Mock())
        daemon.info["shutdown_led"] = "1"
        daemon.op_power_off(client, {})
        decoder = dl.Decoder()
        kinds = [
            kind
            for call in stream.write.call_args_list
            for kind, _ in decoder.feed(call.args[0])
        ]
        self.assertEqual(kinds, [dl.STOP, dl.SHUTDOWN])

    def test_failed_shutdown_does_not_signal_mcu_shutdown(self):
        daemon, client, stream = self.daemon(Mock(side_effect=OSError("busy")))
        daemon.info["shutdown_led"] = "1"
        with self.assertRaises(diagd.Refused):
            daemon.op_power_off(client, {})
        decoder = dl.Decoder()
        kinds = [
            kind
            for call in stream.write.call_args_list
            for kind, _ in decoder.feed(call.args[0])
        ]
        self.assertEqual(kinds, [dl.STOP])

    def test_only_heartbeat_leds_are_stopped(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, trigger in (
                ("status", "none [heartbeat]"),
                ("disk", "[mmc0] heartbeat"),
            ):
                led = root / name
                led.mkdir()
                (led / "trigger").write_text(trigger)
                (led / "brightness").write_text("1")
            self.assertEqual(robot_poweroff.stop_heartbeat(root), 1)
            self.assertEqual((root / "status/trigger").read_text(), "none")
            self.assertEqual((root / "status/brightness").read_text(), "0")
            self.assertEqual((root / "disk/brightness").read_text(), "1")

    def test_bpi_shutdown_level_is_inverted_and_start_restores_trigger(self):
        # Windows cannot create a path containing ':', as the real sysfs name does.
        led = MagicMock()
        led.name = "red:status"
        trigger = Mock()
        trigger.read_text.return_value = "none [heartbeat]"
        brightness = Mock()
        maximum = Mock()
        maximum.read_text.return_value = "1"
        files = dict(trigger=trigger, brightness=brightness, max_brightness=maximum)
        led.__truediv__.side_effect = files.__getitem__
        root = MagicMock()
        root.iterdir.return_value = [led]
        invert = Mock()
        root.__truediv__.side_effect = {
            "red:status/trigger": trigger,
            "red:status/invert": invert,
        }.__getitem__
        self.assertEqual(
            robot_poweroff.stop_heartbeat(root, "BananaPi BPI-M4-Zero v2"), 1
        )
        brightness.write_text.assert_called_once_with("1")
        robot_poweroff.start_heartbeat(root, "BananaPi BPI-M4-Zero v2")
        trigger.write_text.assert_called_with("heartbeat")
        invert.write_text.assert_called_once_with("1")

    def test_hook_ignores_reboot_and_dry_check_never_touches_pins(self):
        hardware = SimpleNamespace(
            NRST=226, SBC_HOLD=257, Line=Mock(), open_controller=Mock(return_value=42)
        )
        with patch.dict(sys.modules, {"flash_mcu": hardware}):
            with patch.object(sys, "argv", ["hook", "reboot"]):
                robot_poweroff.main()
            hardware.open_controller.assert_not_called()
            with patch.object(sys, "argv", ["hook", "--check"]):
                with patch.object(robot_poweroff.os, "close"):
                    robot_poweroff.main()
            hardware.Line.assert_not_called()
            with patch.object(sys, "argv", ["hook", "poweroff"]):
                with patch.object(robot_poweroff.os, "close"):
                    with patch.object(robot_poweroff.time, "sleep"):
                        robot_poweroff.main()
            self.assertEqual(hardware.Line.call_args_list[0].args, (42, 226, 0))
            self.assertEqual(hardware.Line.call_args_list[1].args, (42, 257, 0))

    def test_gui_cancel_and_confirm(self):
        app = Mock()
        app.job.side_effect = lambda work, done, failed: done(work())
        with patch.object(motor_gui.messagebox, "askyesno", return_value=False):
            motor_gui.App.power_off(app)
        app.robot.request.assert_not_called()
        with patch.object(motor_gui.messagebox, "askyesno", return_value=True):
            motor_gui.App.power_off(app)
        app.robot.take_control.assert_called_once()
        app.robot.request.assert_called_once_with("power.off", wait=15)
        app.disconnect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
