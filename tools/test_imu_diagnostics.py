"""Known diagnostic layout and captured IMU error parsing, without hardware."""

import struct
import sys
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


if __name__ == "__main__":
    unittest.main()
