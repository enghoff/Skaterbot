"""Known diagnostic layout and captured IMU error parsing, without hardware."""

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sbc"))

import diag_link as dl
import diagd


class ImuDiagnosticsTests(unittest.TestCase):
    def test_firmware_layout_and_pins(self):
        # Independent values in the firmware's documented wire order.
        wire = struct.pack(
            "<23I",
            1,
            100,
            40,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13000,
            14,
            15,
            16000,
            17000,
            0x01020304,
            18000,
            3,
            0x8000,
        )
        values = dl.parse_imu_diag(wire)
        self.assertEqual(values["timeouts"], 6)
        self.assertEqual(values["resets"], 11)
        self.assertEqual(values["last_input_ms"], 13000)
        self.assertEqual(values["max_service_gap_us"], 17000)
        self.assertEqual(values["last_header"], 0x01020304)
        self.assertEqual(values["pins"], 3)
        self.assertEqual(values["isr"], 0x8000)
        with self.assertRaises(ValueError):
            dl.parse_imu_diag(wire[:-1])
        with self.assertRaises(ValueError):
            dl.parse_imu_diag(struct.pack("<I", 2) + wire[4:])
        v2 = struct.pack("<I", 2) + wire[4:] + struct.pack("<I", 19)
        self.assertEqual(dl.parse_imu_diag(v2)["host_resets"], 19)
        with self.assertRaises(ValueError):
            dl.parse_imu_diag(struct.pack("<I", 3) + v2[4:])

    def test_real_internal_error_and_end_marker(self):
        daemon = diagd.Daemon(Mock())
        daemon.imu_packet(1, bytes.fromhex("14800205f100010000000004020000000a000000"))
        error = daemon.imu_internal_errors[0]
        self.assertEqual(
            {k: error[k] for k in ("severity", "source", "error", "module", "code")},
            dict(severity=0, source=4, error=2, module=0, code=0),
        )
        daemon.imu_packet(2, bytes.fromhex("14800207f1010100010000ff000000000a000000"))
        self.assertEqual(len(daemon.imu_internal_errors), 1)
        self.assertEqual(len(daemon.imu_control), 2)
        daemon.op_imu_diagnostics(Mock(), {})
        daemon.stream.write.assert_not_called()

    def test_feature_snapshot_clears_after_reset_and_trace_is_bounded(self):
        daemon = diagd.Daemon(Mock())
        packet = bytes.fromhex("15000200fc02000000102700000000000000000000")
        for n in range(40):
            daemon.imu_packet(n, packet)
        self.assertEqual(daemon.imu_features[2]["hz"], 100)
        self.assertEqual(len(daemon.imu_control), 32)
        daemon.imu_packet(41, bytes.fromhex("0500010001"))
        self.assertEqual(daemon.imu_features, {})


def command_response(command: int, results: list[int], seq: int = 0) -> bytes:
    """An SH-2 Command Response packet on the control channel: 0xF1, its
    sequence, the command, the command's and the response's sequences, R0-R10."""
    payload = bytes([0xF1, seq, command, seq, 0]) + bytes(
        results + [0] * (11 - len(results))
    )
    return struct.pack("<HBB", len(payload) + 4, 2, seq) + payload


def report(rid: int, values, q: int) -> bytes:
    payload = bytes([rid, 0, 3, 0]) + struct.pack(
        "<3h", *(round(v * (1 << q)) for v in values)
    )
    return struct.pack("<HBB", len(payload) + 4, 3, 0) + payload


class ImuCalibrationTests(unittest.TestCase):
    """The answers to what firmware/diag's start_imu_reports sends the hub: set its
    calibration, stop it saving, ask the settings back."""

    def test_the_readback_is_the_second_me_calibration_answer(self):
        daemon = diagd.Daemon(Mock())
        # Configure's answer, whose settings may be anything; a DCD answer, which the
        # robot's hub never sent but changes nothing if one comes; then Get's:
        # accelerometer, gyro, magnetometer and planar off, on-table on.
        daemon.imu_packet(1, command_response(0x07, [0, 1, 1, 1, 1, 1]))
        self.assertNotIn("readback", daemon.imu_calibration)
        self.assertTrue(daemon.imu_calibration["configured"])
        daemon.imu_packet(2, command_response(0x09, [0], seq=1))
        self.assertTrue(daemon.imu_calibration["dcd_save_off"])
        daemon.imu_packet(3, command_response(0x07, [0, 0, 0, 0, 0, 1], seq=2))
        readback = daemon.imu_calibration["readback"]
        self.assertTrue(readback["ok"])
        self.assertFalse(readback["accel"])
        self.assertFalse(readback["mag"])
        self.assertTrue(readback["on_table"])
        status = daemon.status_event()
        self.assertFalse(status["imu_cal"]["readback"]["accel"])
        self.assertIn("gravity", status["imu_cal"])
        daemon.stream.write.assert_not_called()

    def test_the_robots_own_packets_several_answers_to_one(self):
        # As the robot's hub sent them on 2026-11-06 at 20:42 after a reset: the
        # Initialize answer and both ME Calibration answers in one packet; a Get
        # Feature answer and the next round's two in the next. No DCD answer at all.
        daemon = diagd.Daemon(Mock())
        said = []
        daemon.log = lambda text, t=None: said.append(text)

        def answer(command, cmd_seq, results):
            return bytes([0xF1, 0, command, cmd_seq, 0]) + bytes(
                results + [0] * (11 - len(results))
            )

        first = (
            answer(0x84, 0, [0, 1])
            + answer(0x07, 6, [0, 0, 0, 0, 0, 0])
            + answer(0x07, 8, [0, 0, 0, 0, 0, 0])
        )
        feature = bytes.fromhex("fc01000000401f0000" + "00" * 8)
        second = feature + answer(0x07, 9, [0]) + answer(0x07, 11, [0, 0, 0, 0, 0, 0])
        daemon.imu_packet(1, struct.pack("<HBB", len(first) + 4 | 0x8000, 2, 2) + first)
        self.assertTrue(daemon.imu_calibration["configured"])
        self.assertFalse(daemon.imu_calibration["readback"]["accel"])
        self.assertEqual(said[-1], "imu: calibrating by itself: nothing")
        daemon.imu_packet(
            2, struct.pack("<HBB", len(second) + 4 | 0x8000, 2, 4) + second
        )
        self.assertIn(1, daemon.imu_features)
        self.assertEqual(daemon.imu_calibration["readback"]["t"], 2)

    def test_an_accelerometer_still_calibrating_is_said(self):
        daemon = diagd.Daemon(Mock())
        said = []
        daemon.log = lambda text, t=None: said.append(text)
        daemon.imu_packet(1, command_response(0x07, [0]))
        daemon.imu_packet(2, command_response(0x07, [0, 1, 0, 1, 0, 0]))
        self.assertTrue(daemon.imu_calibration["readback"]["accel"])
        self.assertIn("ACCELEROMETER", said[-1])

    def test_a_reset_forgets_the_settings(self):
        daemon = diagd.Daemon(Mock())
        daemon.imu_packet(1, command_response(0x07, [0]))
        daemon.imu_packet(2, command_response(0x07, [0, 0, 0, 0, 0, 1]))
        self.assertIn("readback", daemon.imu_calibration)
        daemon.imu_packet(3, bytes.fromhex("0500010001"))
        self.assertEqual(daemon.imu_calibration, {})
        daemon.imu_packet(4, command_response(0x07, [0]))
        self.assertNotIn("readback", daemon.imu_calibration)


class GravityWatchTests(unittest.TestCase):
    """The gravity report's length standing still and upright, against the levelled."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "sysid_robot.json"
        # The chip's axes the torso's, gravity read with its sign flipped: upright is
        # +z in the chip.
        self.path.write_text(
            json.dumps(
                {
                    "imu_axes": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                    "imu_gravity_sign": -1,
                    "imu_gravity_m_s2": 9.75,
                }
            )
        )
        self.watch = diagd.GravityWatch(self.path)

    def tearDown(self):
        self.dir.cleanup()

    def stand(self, g, seconds=2.2, t0=0.0, w=(0.0, 0.0, 0.0)):
        said = []
        for k in range(int(seconds * 100)):
            self.watch.gyro(w)
            words = self.watch.gravity(t0 + k * 0.01, g)
            if words:
                said.append(words)
        return said

    def test_as_levelled_says_nothing(self):
        self.assertEqual(self.stand([0.0, 0.0, 9.76]), [])
        self.assertAlmostEqual(self.watch.summary()["standing_m_s2"], 9.76, places=3)
        self.assertFalse(self.watch.summary()["off"])

    def test_a_step_is_said_once_and_its_return(self):
        said = self.stand([0.0, 0.0, 9.95])
        self.assertEqual(len(said), 1)
        self.assertIn("level it again", said[0].lower())
        self.assertEqual(self.stand([0.0, 0.0, 9.95], t0=10.0), [])
        back = self.stand([0.0, 0.0, 9.74], t0=20.0)
        self.assertEqual(len(back), 1)
        self.assertIn("back within", back[0])

    def test_lying_or_moving_is_not_compared(self):
        self.assertEqual(self.stand([9.95, 0.0, 0.0]), [])
        self.assertEqual(self.stand([0.0, 0.0, 9.95], w=(0.3, 0.0, 0.0)), [])
        self.assertIsNone(self.watch.summary()["standing_m_s2"])

    def test_no_levelled_length_says_nothing(self):
        self.path.write_text(
            json.dumps({"imu_axes": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]})
        )
        watch = diagd.GravityWatch(self.path)
        for k in range(300):
            watch.gyro((0.0, 0.0, 0.0))
            self.assertIsNone(watch.gravity(k * 0.01, [0.0, 0.0, -9.95]))

    def test_the_daemon_reads_the_reports(self):
        daemon = diagd.Daemon(Mock())
        daemon.gravity = diagd.GravityWatch(self.path)
        said = []
        daemon.log = lambda text, t=None: said.append(text)
        for k in range(230):
            daemon.imu_packet(k * 0.01, report(0x02, [0.0, 0.0, 0.0], 9))
            daemon.imu_packet(k * 0.01, report(0x06, [0.0, 0.0, 9.95], 8))
        self.assertEqual(len(said), 1)
        self.assertTrue(daemon.status_event()["imu_cal"]["gravity"]["off"])


if __name__ == "__main__":
    unittest.main()
