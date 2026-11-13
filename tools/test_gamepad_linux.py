#!/usr/bin/env python3
"""The real programs behind the game controller, on Linux, with no radio.

    sudo python3 tools/test_gamepad_linux.py

tools/test_gamepad.py stands in for Linux and for bluetoothctl. This holds those
stand-ins to the things themselves, as far as a computer with no Bluetooth can:

  - a real input device, made through /dev/uinput and read by gamepad.py as any
    controller would be, and taken away as a switched-off one is. It needs root,
    for /dev/uinput, and nothing else, so it runs on the Pi as it stands.
  - the real bluetoothctl, driven by console_bluetooth.py as the console does,
    against python-dbusmock's copy of BlueZ's D-Bus interface on a private bus.
    So this shows the commands, and that the pairing goes through an agent, and
    the parsing to be right. It says nothing about pairing itself: only a
    controller and the Pi's radio can settle that.

The second wants python3-dbusmock and bluez. They need not be installed:
BIPEDAL_DEBS names a directory with their packages unpacked into it. A part whose
prerequisites are missing is skipped, and says so.
"""

import asyncio
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(os.environ.get("BIPEDAL_DEBS", "/"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sbc"))
if str(ROOT) != "/":
    sys.path.append(str(ROOT / "usr/lib/python3/dist-packages"))
    os.environ["PATH"] = f"{ROOT}/usr/bin:{os.environ['PATH']}"
    os.environ["PYTHONPATH"] = str(ROOT / "usr/lib/python3/dist-packages")

import console_bluetooth as cb  # noqa: E402
import gamepad as gp  # noqa: E402

STICK = (128, 0, 255, 0, 0, 0)  # value, min, max, fuzz, flat, resolution
AT_REST = (0, 0, 255, 0, 0, 0)
HAT = (0, -1, 1, 0, 0, 0)
ABS_RY, BUS_BLUETOOTH = 0x04, 0x05
EV_SYN = 0


class VirtualDevice:
    """An input device the kernel treats as any other, through /dev/uinput, as
    struct uinput_setup and struct uinput_abs_setup have it."""

    @staticmethod
    def _io(direction, number, size):
        return direction << 30 | size << 16 | ord("U") << 8 | number

    def __init__(self, name, axes, keys, vendor=0x1234, product=0x5678):
        import fcntl

        write, none = 1, 0
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        if keys:
            fcntl.ioctl(self.fd, self._io(write, 100, 4), gp.EV_KEY)
            for key in keys:
                fcntl.ioctl(self.fd, self._io(write, 101, 4), key)
        fcntl.ioctl(self.fd, self._io(write, 100, 4), gp.EV_ABS)
        for axis, info in axes.items():
            fcntl.ioctl(self.fd, self._io(write, 103, 4), axis)
            setup = struct.pack("<H2x6i", axis, *info)
            fcntl.ioctl(self.fd, self._io(write, 4, len(setup)), setup)
        setup = struct.pack(
            "<4H80sI", BUS_BLUETOOTH, vendor, product, 1, name.encode(), 0
        )
        fcntl.ioctl(self.fd, self._io(write, 3, len(setup)), setup)
        fcntl.ioctl(self.fd, self._io(none, 1, 0))
        time.sleep(0.2)  # for the device node to appear

    def press(self, *events):
        for kind, code, value in (*events, (EV_SYN, 0, 0)):
            os.write(self.fd, gp.INPUT_EVENT.pack(0, 0, kind, code, value))

    def close(self):
        if self.fd is not None:
            fd, self.fd = self.fd, None
            os.close(fd)  # which destroys it


def until(condition, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


@unittest.skipUnless(os.access("/dev/uinput", os.W_OK), "needs root and /dev/uinput")
class RealInputDevice(unittest.TestCase):
    """Linux's own events, through the same path a Bluetooth controller takes."""

    KEYS = (gp.BTN_SOUTH, gp.BTN_EAST, gp.BTN_TL, gp.BTN_TR)

    def controller(self, name="Virtual controller", right=(gp.ABS_RX, ABS_RY)):
        axes = {gp.ABS_X: STICK, gp.ABS_Y: STICK, gp.ABS_HAT0Y: HAT}
        axes |= {gp.ABS_GAS: AT_REST, gp.ABS_BRAKE: AT_REST}
        axes |= dict.fromkeys(right, STICK)
        device = VirtualDevice(name, axes, self.KEYS)
        self.addCleanup(device.close)
        return device

    def test_a_motion_sensor_is_passed_over_for_the_controller(self):
        # A PlayStation controller brings its motion sensors as a device of its
        # own, with axes of the same names and no buttons.
        sensors = VirtualDevice(
            "Virtual controller Motion Sensors",
            {gp.ABS_X: STICK, gp.ABS_Y: STICK},
            (),
        )
        self.addCleanup(sensors.close)
        before = gp.find_evdev_pad()
        if before:
            self.addCleanup(before.close)
            self.skipTest(f"a real controller is connected: {before.name}")
        self.controller()
        pad = gp.find_evdev_pad()
        self.addCleanup(pad.close)
        self.assertEqual(pad.name, "Virtual controller")
        self.assertEqual(pad.ranges[gp.ABS_Y], (0, 255))
        self.assertEqual(pad.values[gp.ABS_Y], 128)

    def test_real_events_become_a_command(self):
        device = self.controller()
        sent = []

        class Robot:
            error = None

            def send(self, op, **fields):
                sent.append(fields)

            def request(self, op, wait=0, **fields):
                sent.append(fields)
                return {"taken": True}

            def close(self):
                pass

        manager = gp.PadManager(connect=Robot)
        manager.start()
        self.addCleanup(manager.close)
        self.assertTrue(until(lambda: manager.snapshot()["name"]), "never attached")
        self.assertTrue(until(lambda: sent and sent[-1]["live"]), "never live")
        device.press((gp.EV_ABS, gp.ABS_GAS, 255), (gp.EV_ABS, gp.ABS_X, 255))
        self.assertTrue(until(lambda: sent[-1]["forward"] > 0), "never moved")
        self.assertTrue(until(lambda: sent[-1]["turn"] < 0), "never turned")
        self.assertAlmostEqual(sent[-1]["forward"], gp.START_SPEED_M_S)
        self.assertAlmostEqual(sent[-1]["turn"], -gp.START_TURN_RAD_S)
        device.press((gp.EV_ABS, gp.ABS_HAT0Y, -1))
        self.assertTrue(until(lambda: sent[-1]["height"] > gp.DEFAULT_HEIGHT_M))

        # Switched off: Linux takes the device away, and the path says not live.
        device.close()
        self.assertTrue(until(lambda: manager.snapshot()["name"] is None), "not seen")
        self.assertTrue(until(lambda: not sent[-1]["live"]), "still live")
        self.assertEqual(sent[-1]["forward"], 0.0)

        # Back again: found by itself, and asks for nothing until it is pulled.
        again = self.controller()
        self.assertTrue(until(lambda: manager.snapshot()["name"]), "not found again")
        again.press((gp.EV_ABS, gp.ABS_Y, 0))
        time.sleep(0.1)
        self.assertEqual(sent[-1]["forward"], 0.0)

    def test_the_left_stick_on_a_controller_without_rx(self):
        device = self.controller(right=(gp.ABS_Z, gp.ABS_RZ))
        pad = gp.find_evdev_pad()
        self.addCleanup(pad.close)
        operator = gp.Operator(pad.ranges, time.monotonic(), pad.layout, pad.values)
        self.assertEqual(pad.layout.turn, gp.ABS_X)
        operator.command(time.monotonic())
        device.press((gp.EV_ABS, gp.ABS_X, 0))
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and operator.position(gp.ABS_X) > -0.9:
            for event in pad.read(0.1):
                operator.event(*event, time.monotonic())
        self.assertAlmostEqual(
            operator.command(time.monotonic())["turn"], gp.START_TURN_RAD_S
        )

    def test_the_kernels_own_report_of_a_generic_playstation_controller(self):
        # As hid-generic would present one: buttons numbered from BTN_SOUTH with
        # BTN_C and BTN_Z among them, triggers at rest on RX and RY, and Sony's ID.
        device = VirtualDevice(
            "Wireless Controller",
            {
                gp.ABS_X: STICK,
                gp.ABS_Y: STICK,
                gp.ABS_Z: STICK,
                gp.ABS_RZ: STICK,
                gp.ABS_RX: AT_REST,
                ABS_RY: AT_REST,
            },
            range(gp.BTN_SOUTH, gp.BTN_SOUTH + 14),
            vendor=gp.SONY,
        )
        self.addCleanup(device.close)
        pad = gp.find_evdev_pad()
        self.addCleanup(pad.close)
        self.assertEqual(pad.layout.turn, gp.ABS_X)
        self.assertEqual((pad.layout.gas, pad.layout.brake), (ABS_RY, gp.ABS_RX))
        self.assertEqual(pad.layout.jump, gp.BTN_EAST)
        self.assertEqual(pad.values[gp.ABS_RX], 0)


def have_bluez_mock():
    try:
        import dbus  # noqa: F401
        import dbusmock  # noqa: F401
    except ImportError:
        return False
    return bool(shutil.which("bluetoothctl") and shutil.which("dbus-daemon"))


@unittest.skipUnless(have_bluez_mock(), "needs bluez, dbus-daemon and python3-dbusmock")
class RealBluetoothctl(unittest.IsolatedAsyncioTestCase):
    PAD = "AA:BB:CC:00:00:01"

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        socket_path = f"{self.directory.name}/bus"
        self.bus = subprocess.Popen(
            [
                "dbus-daemon",
                "--session",
                "--nofork",
                f"--address=unix:path={socket_path}",
            ],
        )
        self.addCleanup(self.bus.wait)
        self.addCleanup(self.bus.terminate)
        self.assertTrue(until(lambda: os.path.exists(socket_path)))
        address = f"unix:path={socket_path}"
        os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = address
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = address
        self.mock = subprocess.Popen(
            [sys.executable, "-m", "dbusmock", "--system", "--template", "bluez5"],
            stdout=subprocess.DEVNULL,
        )
        self.addCleanup(self.mock.wait)
        self.addCleanup(self.mock.terminate)
        time.sleep(0.7)
        self.manager = cb.BluetoothManager()
        # This mock has no kernel behind it to make an input device, so a connected
        # device counts; tools/test_gamepad.py holds what the real check reads.
        patcher = patch.object(cb.Tool, "has_input", staticmethod(lambda address: True))
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, method, *args):
        """A call on the mock's own control interface."""
        subprocess.run(
            [
                "dbus-send",
                "--system",
                "--print-reply",
                "--dest=org.bluez",
                "/",
                f"org.bluez.Mock.{method}",
                *[f"string:{a}" for a in args],
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    def adapter(self):
        self.call("AddAdapter", "hci0", "the robot")

    def device(self, address, name):
        self.call("AddDevice", "hci0", address, name)

    async def act(self, op, **fields):
        await self.manager.action({"op": f"bluetooth.{op}", **fields})
        await self.manager.task
        return self.manager.state

    async def test_no_adapter(self):
        state = await self.act("status")
        self.assertIs(state["available"], False, state)

    async def test_the_real_tools_output_is_read_as_intended(self):
        self.adapter()
        self.device(self.PAD, "Wireless Controller")
        self.device("AA:BB:CC:00:00:02", "A speaker")
        state = await self.act("status")
        self.assertEqual(state["error"], "", state)
        self.assertIs(state["available"], True, state)
        names = sorted(d["name"] for d in state["found"])
        self.assertEqual(names, ["A speaker", "Wireless Controller"], state)
        for device in state["found"]:
            self.assertFalse(device["paired"], device)
            self.assertFalse(device["connected"], device)

    def connecting_works(self, address):
        """The mock's Connect does nothing: a real device ends up connected."""
        path = "/org/bluez/hci0/dev_" + address.replace(":", "_")
        subprocess.run(
            [
                "dbus-send",
                "--system",
                "--print-reply",
                "--dest=org.bluez",
                path,
                "org.freedesktop.DBus.Mock.AddMethod",
                "string:org.bluez.Device1",
                "string:Connect",
                "string:",
                "string:",
                "string:self.Set('org.bluez.Device1', 'Connected', dbus.Boolean(True))",
            ],
            check=True,
            capture_output=True,
            timeout=8,
        )

    async def test_a_device_that_will_not_connect_is_not_called_done(self):
        self.adapter()
        self.device(self.PAD, "Wireless Controller")
        before = cb.CONNECT_FOR_S
        cb.CONNECT_FOR_S = 1
        self.addCleanup(setattr, cb, "CONNECT_FOR_S", before)
        state = await self.act("pair", address=self.PAD)
        self.assertIn("never finished connecting", state["error"], state)
        self.assertEqual([d["address"] for d in state["paired"]], [self.PAD], state)

    async def test_pair_trust_connect_and_forget(self):
        self.adapter()
        self.device(self.PAD, "Wireless Controller")
        self.connecting_works(self.PAD)
        state = await self.act("pair", address=self.PAD)
        self.assertEqual(state["error"], "", state)
        self.assertEqual([d["address"] for d in state["paired"]], [self.PAD], state)
        self.assertTrue(state["paired"][0]["trusted"], state)
        self.assertTrue(state["paired"][0]["connected"], state)
        self.assertEqual(state["found"], [], state)
        shown = subprocess.run(
            ["bluetoothctl", "show"], capture_output=True, text=True, timeout=8
        ).stdout
        self.assertIn("Pairable: no", shown, "left open to anything nearby")
        calls = subprocess.run(
            [
                "dbus-send",
                "--system",
                "--print-reply",
                "--dest=org.bluez",
                "/org/bluez",
                "org.freedesktop.DBus.Mock.GetCalls",
            ],
            capture_output=True,
            text=True,
            timeout=8,
        ).stdout
        self.assertIn("RegisterAgent", calls, "a real controller refuses this")
        self.assertIn("RequestDefaultAgent", calls, "a real controller refuses this")
        state = await self.act("forget", address=self.PAD)
        self.assertEqual(state["error"], "", state)
        self.assertEqual(state["paired"], [], state)
        self.assertEqual(state["message"], "Controller forgotten")

    async def test_a_pairing_that_cannot_happen_says_why(self):
        self.adapter()
        async with cb.Tool().agent() as agent:
            self.assertEqual(agent.failed, "")
            reason = await agent.pair("AA:BB:CC:00:00:09", 10)
            self.assertIn("not available", reason)
            again = await agent.pair("AA:BB:CC:00:00:09", 10)
            self.assertIn("not available", again, "one agent, more than one try")

    async def test_scan_runs_the_real_scan_and_stops_it(self):
        self.adapter()
        self.device(self.PAD, "Wireless Controller")
        before = cb.SCAN_S
        cb.SCAN_S = 2
        self.addCleanup(setattr, cb, "SCAN_S", before)
        started = time.monotonic()
        state = await self.act("scan")
        self.assertEqual(state["error"], "", state)
        self.assertGreaterEqual(time.monotonic() - started, 1.5)
        self.assertEqual([d["address"] for d in state["found"]], [self.PAD], state)

    async def test_a_tool_left_waiting_for_a_dead_service_is_an_answer(self):
        self.mock.terminate()
        self.mock.wait()
        await asyncio.sleep(0.2)
        state = await asyncio.wait_for(self.act("status"), 15)
        self.assertTrue(state["error"], state)
        self.assertFalse(state["busy"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
