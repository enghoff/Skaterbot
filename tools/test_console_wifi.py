# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Exercise Wi-Fi persistence and recovery without changing host networking."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sbc"))
import console_wifi as wifi  # noqa: E402


class WifiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.netplan = root / "netplan"
        self.netplan.mkdir()
        self.preference = root / "wifi.json"
        self.file = self.netplan / "30-wifi.yaml"
        self.file.write_text(
            yaml.safe_dump(
                {
                    "network": {
                        "version": 2,
                        "wifis": {
                            "wlan0": {
                                "dhcp4": True,
                                "regulatory-domain": "IN",
                                "access-points": {
                                    "Original": {"password": "original-password"}
                                },
                            }
                        },
                    }
                }
            )
        )
        for target, value in (
            ("NETPLAN", self.netplan),
            ("PREFERENCE", self.preference),
        ):
            patcher = patch.object(wifi, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(wifi.subprocess, "run", return_value=Mock(returncode=0))
        self.generate = patcher.start()
        self.addCleanup(patcher.stop)

    def test_save_prefer_and_forget_survive_new_instances(self):
        profiles = wifi.Profiles()
        profiles.update("New: Network", {"password": "new-password"})
        profiles.prefer("New: Network")
        reopened = wifi.Profiles()
        self.assertEqual(set(reopened.saved()), {"Original", "New: Network"})
        self.assertEqual(reopened.preferred(), "New: Network")
        self.assertNotIn("password", self.preference.read_text())
        reopened.update("New: Network")
        self.assertEqual(set(wifi.Profiles().saved()), {"Original"})
        document = yaml.safe_load(self.file.read_text())
        self.assertEqual(
            document["network"]["wifis"]["wlan0"]["regulatory-domain"], "IN"
        )

    def test_forget_final_network_keeps_adapter_available(self):
        profiles = wifi.Profiles()
        profiles.update("Original")
        self.assertEqual(profiles.saved(), {})
        profiles.update("New", {"password": "new-password"})
        self.assertEqual(set(profiles.saved()), {"New"})
        self.assertNotIn(wifi.UNCONFIGURED, self.file.read_text())

    def test_validation_failure_does_not_write_credentials(self):
        original = self.file.read_bytes()
        self.generate.return_value.returncode = 1
        with self.assertRaisesRegex(ValueError, "rejected by Netplan"):
            wifi.Profiles().update("Bad", {"password": "secret-password"})
        self.assertEqual(self.file.read_bytes(), original)

    def test_generate_failure_restores_original(self):
        self.generate.side_effect = [
            Mock(returncode=0),
            Mock(returncode=1),
            Mock(returncode=0),
        ]
        with self.assertRaisesRegex(ValueError, "original settings restored"):
            wifi.Profiles().update("Bad", {"password": "secret-password"})
        self.assertEqual(set(wifi.Profiles().saved()), {"Original"})

    def control(self):
        control = Mock()
        control.networks.return_value = {0: "Original"}
        control.access_points.return_value = [
            dict(ssid="New", security="WPA/WPA2", dbm=-50)
        ]
        control.command.return_value = "1"
        return control

    def test_success_persists_only_after_association_without_exposing_password(self):
        control = self.control()
        control.status.side_effect = [
            dict(id="0", ssid="Original", wpa_state="COMPLETED"),
            dict(id="1", ssid="New", wpa_state="COMPLETED", ip_address="192.0.2.2"),
        ]
        wifi.Wifi(control).connect(dict(ssid="New", password="new-password"))
        self.assertEqual(wifi.Profiles().preferred(), "New")
        self.assertEqual(len(wifi.Profiles().saved()["New"]["password"]), 64)
        self.assertNotIn("new-password", str(control.command.call_args_list))

    def test_failed_password_restores_old_connection_without_saving(self):
        control = self.control()
        control.status.return_value = dict(
            id="0", ssid="Original", wpa_state="COMPLETED"
        )
        with patch.object(wifi.time, "monotonic", side_effect=[0, 40]):
            with self.assertRaisesRegex(ValueError, "previous network restored"):
                wifi.Wifi(control).connect(dict(ssid="New", password="wrong-password"))
        self.assertEqual(set(wifi.Profiles().saved()), {"Original"})
        self.assertIn(
            unittest.mock.call("SELECT_NETWORK 0"), control.command.call_args_list
        )
        self.assertIn(
            unittest.mock.call("REMOVE_NETWORK 1"), control.command.call_args_list
        )

    def test_status_never_returns_saved_credentials(self):
        control = self.control()
        control.status.return_value = dict(ssid="Original", wpa_state="COMPLETED")
        snapshot = wifi.Wifi(control).snapshot()
        self.assertEqual(snapshot["saved"], ["Original"])
        self.assertNotIn("original-password", json.dumps(snapshot))

    def test_ssid_escaping_preserves_colons_unicode_and_backslashes(self):
        self.assertEqual(
            wifi.unescape_ssid(r"Cafe\x3a \xc3\xa9\\room"), "Cafe: é\\room"
        )


if __name__ == "__main__":
    unittest.main()
