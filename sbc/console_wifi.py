#!/usr/bin/python3
"""Root-owned Wi-Fi helper for the console's Netplan/networkd installation.

JSON requests and replies use stdin/stdout. Credentials never enter argv.
Install with install_console_wifi.sh; do not grant sudo to a writable checkout.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

INTERFACE = "wlan0"
NETPLAN = Path("/etc/netplan")
PREFERENCE = Path("/var/lib/bipedal-console/wifi.json")
UNCONFIGURED = "bipedal-console-unconfigured"


def unescape_ssid(text):
    raw = bytearray()
    index = 0
    while index < len(text):
        if text[index : index + 2] == "\\x" and re.fullmatch(
            "[0-9a-fA-F]{2}", text[index + 2 : index + 4]
        ):
            raw.append(int(text[index + 2 : index + 4], 16))
            index += 4
        elif text[index : index + 2] == "\\\\":
            raw.append(92)
            index += 2
        else:
            raw.extend(text[index].encode())
            index += 1
    return raw.decode("utf-8", errors="replace")


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


class Profiles:
    def documents(self):
        return {
            path: yaml.safe_load(path.read_text()) or {}
            for path in sorted(NETPLAN.glob("*.yaml"))
        }

    def saved(self):
        saved = {}
        for document in self.documents().values():
            config = document.get("network", {}).get("wifis", {}).get(INTERFACE, {})
            saved.update(config.get("access-points", {}) or {})
        saved.pop(UNCONFIGURED, None)
        return saved

    def preferred(self):
        if PREFERENCE.exists():
            return json.loads(PREFERENCE.read_text()).get("ssid")
        return None

    def prefer(self, ssid):
        atomic_write(PREFERENCE, json.dumps({"ssid": ssid}) + "\n")

    def update(self, ssid, profile=None):
        documents = self.documents()
        original = copy.deepcopy(documents)
        target = NETPLAN / "90-motor-console-wifi.yaml"
        for path, document in documents.items():
            config = document.get("network", {}).get("wifis", {}).get(INTERFACE)
            if config is not None:
                target = path
                config.setdefault("access-points", {}).pop(ssid, None)
                config["access-points"].pop(UNCONFIGURED, None)
        if profile is not None:
            document = documents.setdefault(target, {"network": {"version": 2}})
            config = (
                document["network"]
                .setdefault("wifis", {})
                .setdefault(INTERFACE, {"dhcp4": True, "optional": True})
            )
            config.setdefault("access-points", {})[ssid] = profile
        configurations = [
            document.get("network", {}).get("wifis", {}).get(INTERFACE)
            for document in documents.values()
        ]
        configurations = [config for config in configurations if config is not None]
        if configurations and not any(
            config.get("access-points") for config in configurations
        ):
            # Netplan refuses an adapter with no AP definitions. Keep its
            # supplicant alive for future scans using an unconnectable entry,
            # excluded from saved networks and disabled by the restore hook.
            configurations[-1]["access-points"] = {
                UNCONFIGURED: {
                    "password": secrets.token_hex(32),
                    "bssid": "02:00:00:00:00:00",
                }
            }
        # Validate a private staging copy; never expose Netplan's errors, which
        # may include credential-bearing YAML, to a browser or service log.
        with tempfile.TemporaryDirectory(prefix="console-netplan-") as root:
            directory = Path(root) / "etc/netplan"
            directory.mkdir(parents=True)
            for path, document in documents.items():
                atomic_write(directory / path.name, yaml.safe_dump(document))
            result = subprocess.run(
                ["/usr/sbin/netplan", "generate", "--root-dir", root],
                capture_output=True,
                timeout=15,
                check=False,
            )
            if result.returncode:
                raise ValueError("Wi-Fi configuration was rejected by Netplan")
        for path, document in documents.items():
            if document != original.get(path):
                if path.exists():
                    backup = path.with_suffix(".yaml.console-backup")
                    if not backup.exists():
                        atomic_write(backup, path.read_text())
                atomic_write(path, yaml.safe_dump(document, sort_keys=False))
        generated = subprocess.run(
            ["/usr/sbin/netplan", "generate"],
            capture_output=True,
            timeout=15,
            check=False,
        )
        if generated.returncode:
            for path, document in documents.items():
                if document != original.get(path):
                    if path in original:
                        atomic_write(
                            path, yaml.safe_dump(original[path], sort_keys=False)
                        )
                    else:
                        path.unlink()
            subprocess.run(
                ["/usr/sbin/netplan", "generate"],
                capture_output=True,
                timeout=15,
                check=False,
            )
            raise ValueError(
                "Could not save Wi-Fi configuration; original settings restored"
            )


class Control:
    def __init__(self):
        self.directory = tempfile.TemporaryDirectory(prefix="console-wpa-", dir="/run")
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.socket.settimeout(3)
        try:
            self.socket.bind(str(Path(self.directory.name) / "client"))
            self.socket.connect(f"/run/wpa_supplicant/{INTERFACE}")
        except Exception:
            self.close()
            raise

    def close(self):
        self.socket.close()
        self.directory.cleanup()

    def command(self, command):
        self.socket.send(command.encode())
        while True:
            result = self.socket.recv(65536).decode(errors="replace").strip()
            if not result.startswith("<"):
                break
        if result.startswith(("FAIL", "UNKNOWN COMMAND")):
            raise ValueError("Wi-Fi operation was refused by the adapter")
        return result

    def status(self):
        result = dict(
            line.split("=", 1)
            for line in self.command("STATUS").splitlines()
            if "=" in line
        )
        result["ssid"] = unescape_ssid(result.get("ssid", ""))
        return result

    def networks(self):
        result = {}
        for line in self.command("LIST_NETWORKS").splitlines()[1:]:
            fields = line.split("\t")
            if len(fields) >= 4:
                result[int(fields[0])] = unescape_ssid(fields[1])
        return result

    def scan(self):
        self.command("ATTACH")
        try:
            try:
                self.command("SCAN")
            except ValueError:
                pass  # An adapter scan may already be in progress.
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                try:
                    if b"CTRL-EVENT-SCAN-RESULTS" in self.socket.recv(65536):
                        return
                except TimeoutError:
                    continue
            raise ValueError("Wi-Fi scan timed out; try again")
        finally:
            self.command("DETACH")

    def access_points(self):
        found = {}
        for line in self.command("SCAN_RESULTS").splitlines()[1:]:
            fields = line.split("\t", 4)
            if len(fields) != 5 or not fields[4]:
                continue
            _, frequency, signal, flags, name = fields
            ssid = unescape_ssid(name)
            security = (
                "Enterprise"
                if "EAP" in flags
                else "WPA2/WPA3"
                if "SAE" in flags and "PSK" in flags
                else "WPA3"
                if "SAE" in flags
                else "WPA/WPA2"
                if "PSK" in flags
                else "Unsupported"
                if any(key in flags for key in ("WEP", "OWE"))
                else "Open"
            )
            point = dict(
                ssid=ssid, dbm=int(signal), frequency=int(frequency), security=security
            )
            if ssid not in found or point["dbm"] > found[ssid]["dbm"]:
                found[ssid] = point
        return sorted(found.values(), key=lambda point: -point["dbm"])

    def prefer(self, ssid):
        for network_id, name in self.networks().items():
            self.command(
                f"SET_NETWORK {network_id} priority {100 if name == ssid else 0}"
            )
        self.command("ENABLE_NETWORK all")
        for network_id, name in self.networks().items():
            if name == UNCONFIGURED:
                self.command(f"DISABLE_NETWORK {network_id}")


class Wifi:
    def __init__(self, control, profiles=None):
        self.control = control
        self.profiles = profiles or Profiles()

    def snapshot(self):
        status = self.control.status()
        saved = self.profiles.saved()
        connected = status.get("wpa_state") == "COMPLETED" or (
            status.get("wpa_state") == "SCANNING" and status.get("ip_address")
        )
        current = status["ssid"] if connected else None
        return dict(
            interface=INTERFACE,
            current=current,
            ip=status.get("ip_address"),
            preferred=self.profiles.preferred(),
            saved=sorted(saved),
            networks=self.control.access_points(),
        )

    def connect(self, request):
        ssid = request.get("ssid")
        if (
            not isinstance(ssid, str)
            or not 1 <= len(ssid.encode()) <= 32
            or ssid == UNCONFIGURED
        ):
            raise ValueError("Select a valid Wi-Fi network")
        password = request.get("password", "")
        if not isinstance(password, str) or any(ord(c) < 32 for c in password):
            raise ValueError("Invalid Wi-Fi password")
        saved = self.profiles.saved()
        networks = self.control.networks()
        old = self.control.status()
        existing = next((key for key, name in networks.items() if name == ssid), None)
        created = None
        profile = saved.get(ssid)
        try:
            if password or existing is None:
                point = next(
                    (p for p in self.control.access_points() if p["ssid"] == ssid), None
                )
                if point is None:
                    raise ValueError("Network is no longer visible; scan again")
                security = point["security"]
                if security in ("Enterprise", "Unsupported"):
                    raise ValueError(
                        "This network needs settings beyond a Wi-Fi password"
                    )
                if security != "Open" and not password:
                    # A saved profile can be restored if the supplicant restarted.
                    password = (profile or {}).get("password", "")
                    password = password or (profile or {}).get("auth", {}).get(
                        "password", ""
                    )
                if security != "Open" and not (
                    8 <= len(password.encode()) <= 63
                    or re.fullmatch("[a-fA-F0-9]{64}", password)
                ):
                    raise ValueError(
                        "Wi-Fi password must be 8–63 bytes (or a 64-digit PSK)"
                    )
                created = int(self.control.command("ADD_NETWORK"))
                self.control.command(
                    f"SET_NETWORK {created} ssid {ssid.encode().hex()}"
                )
                if security == "Open":
                    self.control.command(f"SET_NETWORK {created} key_mgmt NONE")
                    profile = {}
                elif security == "WPA3":
                    self.control.command(f"SET_NETWORK {created} key_mgmt SAE")
                    self.control.command(f'SET_NETWORK {created} psk "{password}"')
                    self.control.command(f"SET_NETWORK {created} ieee80211w 2")
                    profile = {"auth": {"key-management": "sae", "password": password}}
                else:
                    psk = (
                        password
                        if len(password) == 64
                        else hashlib.pbkdf2_hmac(
                            "sha1", password.encode(), ssid.encode(), 4096, 32
                        ).hex()
                    )
                    self.control.command(f"SET_NETWORK {created} key_mgmt WPA-PSK")
                    self.control.command(f"SET_NETWORK {created} psk {psk}")
                    profile = {"password": psk}
                existing = created
            self.control.command(f"SELECT_NETWORK {existing}")
            deadline = time.monotonic() + 35
            while time.monotonic() < deadline:
                status = self.control.status()
                if (
                    status.get("wpa_state") == "COMPLETED"
                    and status["ssid"] == ssid
                    and status.get("ip_address")
                ):
                    self.profiles.update(ssid, profile or {})
                    self.profiles.prefer(ssid)
                    for network_id, name in networks.items():
                        if name == ssid and network_id != existing:
                            self.control.command(f"REMOVE_NETWORK {network_id}")
                    self.control.prefer(ssid)
                    return
                time.sleep(0.5)
            raise ValueError(
                "Connection failed. Check the password and signal; previous network restored."
            )
        except Exception:
            if created is not None:
                with contextlib.suppress(Exception):
                    self.control.command(f"REMOVE_NETWORK {created}")
            if old.get("id"):
                with contextlib.suppress(Exception):
                    self.control.command(f"SELECT_NETWORK {int(old['id'])}")
            with contextlib.suppress(Exception):
                self.control.prefer(self.profiles.preferred())
            raise

    def forget(self, request):
        ssid = request.get("ssid")
        if not isinstance(ssid, str) or ssid not in self.profiles.saved():
            raise ValueError("Select a saved Wi-Fi network")
        self.profiles.update(ssid)
        if self.profiles.preferred() == ssid:
            self.profiles.prefer(None)
        for network_id, name in self.control.networks().items():
            if name == ssid:
                self.control.command(f"REMOVE_NETWORK {network_id}")
        self.control.prefer(self.profiles.preferred())


def main():
    import fcntl

    with Path("/run/bipedal-console-wifi.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restore = sys.argv[1:] == ["--restore"]
        request = {"op": "restore"} if restore else json.loads(sys.stdin.read(8193))
        control = None
        try:
            for attempt in range(20 if restore else 1):
                try:
                    control = Control()
                    break
                except OSError:
                    if attempt == 19 or not restore:
                        raise ValueError("The Wi-Fi adapter is unavailable") from None
                    time.sleep(0.25)
            wifi = Wifi(control)
            op = request.get("op")
            if op == "restore":
                control.prefer(wifi.profiles.preferred())
                if wifi.profiles.preferred():
                    control.command("REASSOCIATE")
            elif op == "scan":
                control.scan()
            elif op == "connect":
                wifi.connect(request)
            elif op == "forget":
                wifi.forget(request)
            elif op != "status":
                raise ValueError("Unknown Wi-Fi action")
            print(json.dumps({"ok": True, "result": wifi.snapshot()}))
        except Exception as error:
            # No arbitrary exception text: YAML and command errors can contain secrets.
            message = (
                str(error)
                if isinstance(error, ValueError)
                else "Wi-Fi operation failed"
            )
            print(json.dumps({"ok": False, "error": message}))
        finally:
            if control:
                control.close()


if __name__ == "__main__":
    main()
