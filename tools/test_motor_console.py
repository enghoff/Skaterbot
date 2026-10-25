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
            self.assertEqual(motor()["command"]["kp"], 0)
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
