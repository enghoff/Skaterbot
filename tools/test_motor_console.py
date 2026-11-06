# /// script
# requires-python = ">=3.11"
# dependencies = ["aiohttp>=3.9,<4", "pyserial>=3.5"]
# ///
"""Exercise the browser transport through the real daemon and simulated MCU."""

import asyncio
import contextlib
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, call

import aiohttp
from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sbc"))
import console_bluetooth  # noqa: E402
import diag_client  # noqa: E402
import motor_console as console  # noqa: E402


class Browser:
    def __init__(self, client, url):
        self.client, self.url = client, url
        self.state = {}
        self.replies = {}
        self.seq = 0

    async def open(self):
        self.ws = await self.client.ws_connect(self.url + "/ws")
        self.reader = asyncio.create_task(self.read())
        self.pinger = asyncio.create_task(self.ping())
        return self

    async def ping(self):
        while True:
            await self.ws.send_json({"op": "ping"})
            await asyncio.sleep(0.08)

    async def read(self):
        async for packet in self.ws:
            message = packet.json()
            if message["type"] == "state":
                self.state = message
            elif message["type"] == "reply":
                self.replies[message.get("req")] = message

    async def until(self, condition, timeout=6):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            await asyncio.sleep(0.03)
        raise AssertionError(f"state never reached condition: {self.state}")

    async def action(self, op, ok=True, **fields):
        self.seq += 1
        req = self.seq
        await self.ws.send_json({"req": req, "op": op, **fields})
        await self.until(lambda: req in self.replies, timeout=12)
        reply = self.replies.pop(req)
        if reply["ok"] != ok:
            raise AssertionError(reply)
        return reply

    async def close(self):
        self.pinger.cancel()
        await self.ws.close()
        self.reader.cancel()
        for task in (self.pinger, self.reader):
            with contextlib.suppress(asyncio.CancelledError):
                await task


class ConsoleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if console.DaemonManager.listening():
            self.skipTest(
                "port 7700 is already occupied; refusing to touch that daemon"
            )
        self.app = console.create_app(sim=True)
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.url = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        self.client = aiohttp.ClientSession()
        self.browsers = []

    async def browser(self):
        browser = await Browser(self.client, self.url).open()
        self.browsers.append(browser)
        return browser

    async def asyncTearDown(self):
        for browser in self.browsers:
            await browser.close()
        manager = self.app["manager"]
        if manager.process and manager.process.poll() is None:
            await manager.action(False)
        await self.client.close()
        await self.runner.cleanup()

    async def test_browser_to_controller(self):
        for path in ("/", "/console.js", "/console.css"):
            async with self.client.get(self.url + path) as response:
                self.assertEqual(response.status, 200)
        with self.assertRaises(aiohttp.WSServerHandshakeError):
            await self.client.ws_connect(
                self.url + "/ws", origin="http://unrelated.invalid"
            )
        browser = await self.browser()
        await browser.action("daemon.start")
        await browser.until(lambda: browser.state.get("connected"))
        await browser.action("take")
        await browser.action("scan", last=6)
        await browser.until(lambda: len(browser.state.get("motors", [])) == 6)
        self.assertEqual({m["bus"] for m in browser.state["motors"]}, set("ABC"))
        target = "A:1"

        def motor():
            return next(m for m in browser.state["motors"] if m["key"] == target)

        await browser.until(lambda: motor()["feedback"] is not None)
        observer = await self.browser()
        await observer.until(lambda: observer.state.get("connected"))
        await observer.action("take", ok=False)
        await observer.action("power.off", ok=False)
        await browser.action("read", motor=target)
        await browser.action("write", motor=target, rid=9, value="500")
        await browser.action("write", motor=target, rid=35, value="4", ok=False)
        await browser.action("write", motor=target, rid=21, value="nan", ok=False)
        await browser.action("write", motor=target, rid=21, value="0", ok=False)
        await browser.action("write", motor=target, rid=7, value="0x101", ok=False)
        await browser.action("save", motor=target)
        for mode in range(1, 5):
            await browser.action("write", motor=target, rid=10, value=mode)
            await browser.action("enable", motor=target)
            await browser.until(lambda: motor()["command"]["active"])
            self.assertEqual(motor()["command"]["kp"], 1)
            self.assertEqual(motor()["command"]["kd"], 0.05 if mode == 1 else 0.1)
            await browser.action(
                "command",
                motor=target,
                p=0,
                v=0.2,
                kp=1,
                kd=0.1,
                t=0.01,
                vlim=0.3,
                ilim=0.1,
                amp=0.01,
                freq=0.5,
                wave="sine",
            )
            await browser.action("write", motor=target, rid=9, value="50", ok=False)
            await browser.action("write", motor=target, rid=10, value=1, ok=False)
            await observer.action("stop")
            await browser.until(
                lambda: (
                    not motor()["command"]["active"] and motor()["state"] == "disabled"
                )
            )
        await browser.action("imu.on", hz=50)
        await browser.until(lambda: len(browser.state.get("imu", {})) == 4)
        supports_imu_diag = any(
            session.robot and "imu.diag" in session.robot.daemon.get("streams", ())
            for session in self.app["sessions"]
        )
        await browser.action("imu.diagnostics", ok=supports_imu_diag)
        await browser.action("imu.info")
        await browser.action("i2c", addr="0x40", write="fe", read=2)
        await browser.action("imu.off")
        # A live TCP socket without application heartbeats must lose control.
        await browser.action("enable", motor=target)
        browser.pinger.cancel()
        await browser.until(lambda: not browser.state["control"])
        await observer.action("take")
        await observer.action("release")
        # Reacquire and scan; long actions must not delay STOP.
        browser.pinger = asyncio.create_task(browser.ping())
        await browser.action("take")
        scan = asyncio.create_task(browser.action("scan", last=32))
        await asyncio.sleep(0.1)
        started = time.monotonic()
        await browser.action("stop")
        self.assertLess(time.monotonic() - started, 0.5)
        await scan
        await browser.action("id", motor=target, new_id=7, master="0x17")
        await browser.until(
            lambda: any(m["key"] == "A:7" for m in browser.state["motors"])
        )
        await browser.close()
        await observer.action("take")
        await observer.action("daemon.stop")
        await observer.until(lambda: not observer.state["connected"])
        await observer.action("daemon.start")
        await observer.until(lambda: observer.state["connected"])
        self.assertFalse(observer.state["control"])
        self.assertEqual(observer.state["motors"], [])

    async def test_finding_a_controller_leaves_anothers_motors_running(self):
        browser = await self.browser()
        await browser.action("daemon.start")
        await browser.until(lambda: browser.state.get("connected"))
        balance = await asyncio.to_thread(diag_client.Robot, name="balance")
        self.addCleanup(balance.close)
        stops = []
        balance.on("stopped", stops.append)
        await asyncio.to_thread(balance.request, "control", take=True)
        await browser.action("bluetooth.scan")
        await browser.action(
            "bluetooth.pair", address=console_bluetooth.SimulatedBluetooth.CONTROLLER
        )
        await asyncio.sleep(0.3)
        self.assertEqual(stops, [], "a click on the page stopped somebody else's run")

    async def test_finding_a_controller_stops_this_pages_own_motors(self):
        browser = await self.browser()
        await browser.action("daemon.start")
        await browser.until(lambda: browser.state.get("connected"))
        listener = await asyncio.to_thread(diag_client.Robot, name="listener")
        self.addCleanup(listener.close)
        stops = []
        listener.on("stopped", stops.append)
        await browser.action("take")
        await browser.until(lambda: browser.state.get("control"))
        await browser.action("bluetooth.scan")
        await browser.until(lambda: stops, timeout=3)

    async def test_power_off_without_manual_control(self):
        import diagd

        if "power.off" not in diagd.OPS:
            self.skipTest("this diagnostics daemon has no power.off operation")
        browser = await self.browser()
        await browser.action("daemon.start")
        await browser.until(lambda: browser.state.get("connected"))
        self.assertFalse(browser.state["control"])
        # Native browser confirmation pauses JS timers. The confirmed action
        # must count as fresh liveness even after application pings expired.
        browser.pinger.cancel()
        await asyncio.sleep(console.DEADMAN + 0.2)
        reply = await browser.action("power.off")
        self.assertTrue(reply["result"]["shutting_down"])
        # The simulator acknowledges power-off without shutting down the test host.
        await browser.action("take", ok=False)

    async def test_wifi_saved_networks_survive_browser_sessions(self):
        browser = await self.browser()
        await browser.action("wifi.scan")
        await browser.until(lambda: not self.app["wifi"].state["busy"])
        reply = await browser.action("wifi.status")
        self.assertEqual(len(reply["result"]["networks"]), 3)
        await browser.action("wifi.connect", ssid="Workshop", password="test-password")
        await browser.close()
        await browser.until(lambda: not self.app["wifi"].state["busy"])
        other = await self.browser()
        reply = await other.action("wifi.status")
        self.assertEqual(reply["result"]["current"], "Workshop")
        self.assertEqual(reply["result"]["preferred"], "Workshop")
        self.assertIn("Workshop", reply["result"]["saved"])
        self.assertNotIn("test-password", str(reply))
        await other.action("wifi.forget", ssid="Workshop")
        await other.until(lambda: not self.app["wifi"].state["busy"])
        reply = await other.action("wifi.status")
        self.assertNotIn("Workshop", reply["result"]["saved"])

    async def test_set_zero_preserves_other_motor_streams_in_every_mode(self):
        browser = await self.browser()
        await browser.action("daemon.start")
        await browser.until(lambda: browser.state.get("connected"))
        await browser.action("take")
        await browser.action("scan", last=2)

        def motor(key):
            return next(m for m in browser.state["motors"] if m["key"] == key)

        await browser.until(lambda: all(m["feedback"] for m in browser.state["motors"]))
        await browser.action("enable", motor="A:2")
        for mode in range(1, 5):
            await browser.until(lambda: not motor("A:1")["command"]["active"])
            await browser.action("write", motor="A:1", rid=10, value=mode)
            await browser.action("enable", motor="A:1")
            before = motor("A:2")["feedback"]["t"]
            await browser.action("zero", motor="A:1")
            await browser.until(
                lambda: motor("A:1")["command"]["zero_revision"] == mode
            )
            target = motor("A:1")
            self.assertTrue(target["command"]["active"])
            self.assertEqual(target["feedback"]["state"], 1)
            self.assertAlmostEqual(target["feedback"]["pos"], 0, delta=0.01)
            self.assertEqual(target["command"]["p"], 0)
            self.assertFalse(target["command"]["homing"])
            self.assertTrue(motor("A:2")["command"]["active"])
            self.assertEqual(motor("A:2")["feedback"]["state"], 1)
            await browser.until(lambda: motor("A:2")["feedback"]["t"] > before)
            await browser.action("disable", motor="A:1")
            await browser.until(lambda: motor("A:1")["feedback"]["state"] == 0)
        await browser.action("zero", motor="A:1")
        await browser.until(lambda: motor("A:1")["command"]["zero_revision"] == 5)
        self.assertFalse(motor("A:1")["command"]["active"])
        self.assertTrue(motor("A:2")["command"]["active"])


class MotorEnableTests(unittest.TestCase):
    def test_enable_uses_current_position_and_preserves_only_tuned_gains(self):
        session = console.Session.__new__(console.Session)
        session.lock = console.threading.RLock()
        session.robot = Mock(error=None)
        session.control = True
        session.last_ping = time.monotonic()
        session.limits = dict(torque=0.5, kp=10, kd=1, speed=5, current=0.3)
        previous = console.Command(
            p=-3, v=0.7, kp=0.8, kd=0.03, t=0.1, wave="sine", amp=0.1
        )
        session.commands = {"A:1": previous}
        feedback = console.dm.Feedback(
            t=time.monotonic(),
            state=0,
            pos=1.234567,
            vel=0,
            torque=0,
            t_mos=25,
            t_rotor=25,
        )
        motor = console.dm.Motor(1, feedback=feedback)
        bus = Mock()
        session.target = Mock(return_value=(bus, motor, previous))
        session.action(dict(op="enable", motor="A:1"))
        command = session.commands["A:1"]
        self.assertEqual(command.p, feedback.pos)
        self.assertEqual((command.kp, command.kd), (0.8, 0.03))
        self.assertEqual((command.v, command.t, command.amp), (0, 0, 0))
        self.assertEqual(command.wave, "constant")
        self.assertTrue(command.active)
        bus.enable.assert_called_once_with(motor)


class MotorZeroTests(unittest.TestCase):
    def setUp(self):
        self.session = console.Session.__new__(console.Session)
        self.session.lock = console.threading.RLock()
        self.session.require_control = Mock()
        self.session.robot = Mock(error=None)
        self.session.limits = dict(torque=0.5, kp=10, kd=1, speed=5, current=0.3)
        self.command = console.Command(
            active=True, p=2, v=1, t=0.1, wave="sine", amp=0.2
        )
        self.other = console.Command(active=True, p=-0.4)
        self.session.commands = {"A:1": self.command, "A:2": self.other}
        self.motor = console.dm.Motor(1)
        self.motor.feedback = console.dm.Feedback(
            time.monotonic(), 1, 0.6, 0, 0, 25, 25
        )
        self.bus = Mock()
        self.bus.history_lock = console.threading.Lock()
        self.bus.request_status.side_effect = self.confirm

    def confirm(self, _motor):
        self.motor.feedback = console.dm.Feedback(time.monotonic(), 1, 0, 0, 0, 25, 25)

    def test_zero_drops_old_motion_without_disabling_either_motor(self):
        self.bus.set_zero.side_effect = self.confirm
        self.session.set_zero(self.bus, self.motor, self.command)
        self.assertTrue(self.command.active)
        self.assertTrue(self.other.active)
        self.assertEqual(
            (self.command.p, self.command.v, self.command.t, self.command.amp),
            (0, 0, 0, 0),
        )
        self.assertEqual(self.command.wave, "constant")
        self.assertEqual(self.command.zero_revision, 1)
        self.assertFalse(self.command.homing)
        self.bus.disable.assert_not_called()
        self.session.robot.stop.assert_not_called()
        self.session.robot.send.assert_not_called()

    def test_stop_during_zero_is_never_undone(self):
        def stop_and_confirm(motor):
            self.session.stop()
            self.confirm(motor)

        self.bus.set_zero.side_effect = stop_and_confirm
        self.session.set_zero(self.bus, self.motor, self.command)
        self.assertFalse(self.command.active)
        self.assertFalse(self.other.active)
        self.bus.enable.assert_not_called()

    def test_unconfirmed_zero_disables_only_selected_motor(self):
        self.bus.request_status.side_effect = None
        with self.assertRaisesRegex(ValueError, "zero not confirmed"):
            self.session.set_zero(self.bus, self.motor, self.command)
        self.assertFalse(self.command.active)
        self.assertTrue(self.other.active)
        self.assertEqual(self.command.zero_revision, 0)
        self.assertFalse(self.command.homing)
        self.bus.disable.assert_called_once_with(self.motor)
        self.session.robot.stop.assert_not_called()

    def test_stale_feedback_rejects_zero_without_sending_it(self):
        self.motor.feedback.t -= 1
        with self.assertRaisesRegex(ValueError, "no recent healthy feedback"):
            self.session.set_zero(self.bus, self.motor, self.command)
        self.bus.set_zero.assert_not_called()
        self.bus.disable.assert_not_called()


class PowerOffControlTests(unittest.TestCase):
    def session(self, control=False):
        session = console.Session.__new__(console.Session)
        session.robot = Mock(error=None)
        session.robot.request.return_value = {"shutting_down": True}
        session.control = control
        session.running = True
        session.last_ping = time.monotonic()
        session.lock = console.threading.RLock()
        session.commands = {"A:1": console.Command(active=True)}
        return session

    def test_power_off_reacquires_then_stops_before_shutdown(self):
        for previous_control in (False, True):
            with self.subTest(previous_control=previous_control):
                session = self.session(previous_control)
                result = session.action({"op": "power.off"})
                self.assertTrue(result["shutting_down"])
                self.assertFalse(session.commands["A:1"].active)
                self.assertEqual(
                    session.robot.mock_calls,
                    [
                        call.take_control(),
                        call.stop(),
                        call.request("power.off", wait=15),
                    ],
                )

    def test_other_owner_prevents_shutdown(self):
        session = self.session()
        session.robot.take_control.side_effect = console.diag_client.RobotError(
            "another client holds control"
        )
        with self.assertRaisesRegex(console.diag_client.RobotError, "holds control"):
            session.action({"op": "power.off"})
        session.robot.stop.assert_not_called()
        session.robot.request.assert_not_called()

    def test_expired_browser_cannot_request_shutdown(self):
        session = self.session()
        session.last_ping -= 2 * console.DEADMAN
        with self.assertRaisesRegex(ValueError, "heartbeat lost"):
            session.action({"op": "power.off"})
        session.robot.request.assert_not_called()
        session.robot.send.assert_called_once_with("control", take=False)


if __name__ == "__main__":
    unittest.main()
