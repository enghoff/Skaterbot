# /// script
# requires-python = ">=3.11"
# dependencies = ["aiohttp>=3.9,<4", "pyserial>=3.5"]
# ///
"""BPI diagnostics console: python3 sbc/motor_console.py, then http://bpi:8080.

Only connects to diagd on loopback. --sim changes what the Start button launches,
not the API destination. See motor_console/README.md for installation and tests.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import math
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

import diag_client
from aiohttp import WSMsgType, web

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "bench"))
import damiao as dm  # noqa: E402

ASSETS = HERE / "motor_console"
DEADMAN = 0.5
REPORTS = ("accel", "gyro", "gravity", "game")


def number(value, low, high):
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"value must be between {low:g} and {high:g}")
    return value


def integer(value, low, high):
    parsed = int(str(value), 0) if isinstance(value, str) else int(value)
    if (not isinstance(value, str) and value != parsed) or not low <= parsed <= high:
        raise ValueError(f"integer must be between {low} and {high}")
    return parsed


def clamp(value, low, high):
    return min(max(value, low), high)


@dataclass
class Command:
    active: bool = False
    p: float = 0
    v: float = 0
    kp: float = 1
    kd: float = 0.05
    t: float = 0
    vlim: float = 1
    ilim: float = 0.2
    wave: str = "constant"
    amp: float = 0
    freq: float = 0.5
    t0: float = 0
    enabled_at: float = 0


class Session:
    """One browser, one diagd client and one independent browser watchdog.

    Blocking register requests never run on the websocket or watchdog thread.
    The lock orders stop/enable/drive so no command can follow a local stop.
    """

    def __init__(self):
        self.lock = threading.RLock()
        self.robot = None
        self.buses = {}
        self.commands = {}
        self.events = deque(maxlen=160)
        self.imu = {}
        self.imu_times = {}
        self.control = False
        self.running = True
        self.last_ping = time.monotonic()
        self.error = "diagd is not running"
        self.rate = 200.0
        self.limits = dict(torque=0.5, kp=10.0, kd=1.0, speed=5.0, current=0.3)
        self.seq = 0
        self.worker = threading.Thread(target=self.loop, daemon=True)
        self.worker.start()

    def event(self, message):
        with self.lock:
            self.seq += 1
            self.events.append(dict(message, seq=self.seq))

    def heard(self, message):
        kind = message["ev"]
        with self.lock:
            if kind == "imu":
                report = message["report"]
                self.imu[report] = message
                self.imu_times.setdefault(report, deque(maxlen=200)).append(
                    message["t"]
                )
            elif kind in ("stopped", "closed") or (
                kind == "link" and not message["up"]
            ):
                for command in self.commands.values():
                    command.active = False
                if kind == "closed":
                    self.control = False
            if kind != "imu":
                self.event(message)

    def connect(self):
        robot = diag_client.Robot(
            name=f"web console {id(self):x}",
            streams=("status", "log", "can", "imu"),
        )
        # Older daemons have the core streams without the IMU diagnostic extension.
        if "imu.diag" in robot.daemon.get("streams", ()):
            try:
                robot.request(
                    "subscribe", streams=["status", "log", "can", "imu", "imu.diag"]
                )
            except Exception:
                robot.close()
                raise
        with self.lock:
            if not self.running:
                robot.close()
                return
            self.robot = robot
            self.buses = {b: dm.Bus(robot.can(b), b) for b in "ABC"}
            self.commands = {}
            self.imu.clear()
            self.imu_times.clear()
            self.control = False
            self.error = ""
            for kind in ("log", "can", "imu", "imu.diag", "stopped", "link", "closed"):
                robot.on(kind, self.heard)

    def stop(self, release=False):
        with self.lock:
            for command in self.commands.values():
                command.active = False
            if self.robot and not self.robot.error:
                if release:
                    # The daemon stops motors when their owner releases control.
                    # send() avoids waiting on the same reader that calls heard().
                    self.robot.send("control", take=False)
                else:
                    self.robot.stop()
            if release:
                self.control = False

    def close(self):
        self.running = False
        with contextlib.suppress(Exception):
            self.stop(release=True)
        if self.robot:
            self.robot.close()

    def loop(self):
        next_connect = last_poll = 0.0
        while self.running:
            now = time.monotonic()
            try:
                if self.robot is None or self.robot.error:
                    if now >= next_connect:
                        if self.robot:
                            self.robot.close()
                        next_connect = now + 1
                        self.connect()
                with self.lock:
                    if self.control and now - self.last_ping > DEADMAN:
                        self.stop(release=True)
                        self.event(
                            {
                                "ev": "log",
                                "text": "browser heartbeat lost; control released",
                            }
                        )
                    if self.control and self.robot and not self.robot.error:
                        poll = now - last_poll >= 0.05
                        for name, bus in self.buses.items():
                            for motor in list(bus.motors.values()):
                                command = self.commands.setdefault(
                                    f"{name}:{motor.can_id}", Command()
                                )
                                if command.active:
                                    self.drive(bus, motor, command, now)
                                elif poll:
                                    bus.request_status(motor)
                        if poll:
                            last_poll = now
            except (OSError, ValueError, diag_client.RobotError) as error:
                self.error = str(error)
                with contextlib.suppress(Exception):
                    self.stop(release=True)
            time.sleep(1 / self.rate)

    def drive(self, bus, motor, command, now):
        fb = motor.feedback
        if fb is None or now - fb.t > 0.3 or fb.fault:
            command.active = False
            bus.disable(motor)
            self.event(
                {
                    "ev": "log",
                    "text": f"{bus.name}:{motor.can_id} stopped: stale feedback or fault",
                }
            )
            return
        lim = self.limits
        sp = command.v if motor.mode == dm.VELOCITY else command.p
        if command.wave != "constant":
            wave = math.sin(2 * math.pi * command.freq * (now - command.t0))
            sp += command.amp * (
                wave if command.wave == "sine" else math.copysign(1, wave)
            )
        speed = min(lim["speed"], motor.vmax)
        sp = (
            clamp(sp, -motor.pmax, motor.pmax)
            if motor.mode != dm.VELOCITY
            else clamp(sp, -speed, speed)
        )
        if motor.mode == dm.MIT:
            kp = min(command.kp, lim["kp"])
            if kp:
                reach = lim["torque"] / kp
                sp = clamp(sp, fb.pos - reach, fb.pos + reach)
            bus.mit(
                motor,
                sp,
                clamp(command.v, -speed, speed),
                kp,
                min(command.kd, lim["kd"]),
                clamp(command.t, -lim["torque"], lim["torque"]),
            )
        elif motor.mode == dm.POS_VEL:
            bus.pos_vel(motor, sp, min(command.vlim, speed))
        elif motor.mode == dm.VELOCITY:
            bus.velocity(motor, sp)
        elif motor.mode == dm.HYBRID:
            bus.hybrid(
                motor, sp, min(command.vlim, speed), min(command.ilim, lim["current"])
            )

    def require_control(self):
        if not self.robot or self.robot.error:
            raise ValueError("diagd is not connected")
        if not self.control or time.monotonic() - self.last_ping > DEADMAN:
            raise ValueError("take control first")

    def target(self, message):
        name, can_id = message["motor"].split(":")
        bus = self.buses[name]
        motor = bus.motors[int(can_id)]
        return bus, motor, self.commands.setdefault(message["motor"], Command())

    @staticmethod
    def disabled(motor, command):
        fb = motor.feedback
        if command.active or fb is None or time.monotonic() - fb.t > 0.5 or fb.enabled:
            raise ValueError("motor must have recent disabled feedback")

    def action(self, message):
        op = message["op"]
        if op in ("take", "power.off"):
            if not self.robot or self.robot.error:
                raise ValueError("diagd is not connected")
            self.robot.take_control()
            with self.lock:
                if not self.running or time.monotonic() - self.last_ping > DEADMAN:
                    self.stop(release=True)
                    raise ValueError("browser heartbeat lost")
                self.control = True
            if op == "take":
                return "control acquired"
        self.require_control()
        if op == "scan":
            with self.lock:
                if any(c.active for c in self.commands.values()):
                    raise ValueError("disable all motors before scanning")
            last = integer(message.get("last", 16), 1, 127)
            for bus in self.buses.values():
                for can_id in range(1, last + 1):
                    self.require_control()
                    motor = bus.probe(can_id)
                    if motor:
                        motor.registers[dm.RID["TIMEOUT"]] = bus.read(
                            can_id, dm.RID["TIMEOUT"]
                        )
            return "scan complete"
        if op == "limits":
            spans = dict(
                torque=(0, 5), kp=(0, 500), kd=(0, 5), speed=(0, 100), current=(0, 1)
            )
            values = {k: number(message[k], *span) for k, span in spans.items()}
            with self.lock:
                self.limits = values
                self.rate = number(message.get("rate", self.rate), 10, 500)
            return "limits updated"
        if op in ("imu.on", "imu.off"):
            hz = number(message.get("hz", 100), 1, 400) if op == "imu.on" else 0
            return [self.robot.request("imu.enable", report=r, hz=hz) for r in REPORTS]
        if op in ("imu.info", "imu.reset", "imu.diagnostics", "power.off", "i2c"):
            if op == "i2c":
                return self.robot.request(
                    op,
                    addr=integer(message["addr"], 0, 127),
                    write=message.get("write", ""),
                    read=integer(message.get("read", 0), 0, 64),
                )
            if op == "power.off":
                self.stop()
            return self.robot.request(op, wait=15 if op == "power.off" else 2)
        bus, motor, command = self.target(message)
        if op == "read":
            missed = []
            for reg in dm.REGISTERS:
                self.require_control()
                value = bus.read(motor.can_id, reg.rid)
                if value is None:
                    missed.append(reg.name)
                else:
                    motor.registers[reg.rid] = value
            return {"missed": missed}
        if op in ("write", "save", "id"):
            with self.lock:
                self.disabled(motor, command)
            if op == "write":
                return self.write_register(bus, motor, message)
            if op == "save":
                if not bus.save(motor.can_id):
                    raise ValueError("save not confirmed")
                return "settings saved to flash"
            return self.change_id(bus, motor, message)
        with self.lock:
            self.require_control()
            if op == "enable":
                if command.active:
                    raise ValueError("motor is already enabled")
                fb = motor.feedback
                if not fb or time.monotonic() - fb.t > 0.3 or fb.fault:
                    raise ValueError("no recent healthy feedback")
                if motor.mode not in dm.MODE_NAMES:
                    raise ValueError("unknown motor mode")
                command = Command(
                    p=fb.pos,
                    kp=command.kp,
                    kd=command.kd,
                    enabled_at=time.monotonic(),
                    t0=time.monotonic(),
                )
                self.commands[message["motor"]] = command
                self.drive(bus, motor, command, time.monotonic())
                bus.enable(motor)
                self.drive(bus, motor, command, time.monotonic())
                command.active = True
            elif op == "disable":
                command.active = False
                bus.disable(motor)
            elif op == "hold":
                if not motor.feedback or time.monotonic() - motor.feedback.t > 0.3:
                    raise ValueError("no recent feedback")
                command.p, command.wave, command.amp = motor.feedback.pos, "constant", 0
            elif op == "clear":
                command.active = False
                bus.disable(motor)
                bus.clear_error(motor)
            elif op == "zero":
                self.disabled(motor, command)
                bus.set_zero(motor)
            elif op == "command":
                spans = dict(
                    p=(-motor.pmax, motor.pmax),
                    v=(-motor.vmax, motor.vmax),
                    kp=(0, 500),
                    kd=(0, 5),
                    t=(-motor.tmax, motor.tmax),
                    vlim=(0, 100),
                    ilim=(0, 1),
                    amp=(0, 100),
                    freq=(0.01, 20),
                )
                values = {k: number(message[k], *span) for k, span in spans.items()}
                if message["wave"] not in ("constant", "sine", "square"):
                    raise ValueError("unknown waveform")
                for key, value in values.items():
                    setattr(command, key, value)
                command.wave = message["wave"]
            else:
                raise ValueError(f"unknown action {op}")
        return f"{op} accepted"

    def write_register(self, bus, motor, message):
        reg = dm.REGISTER[integer(message["rid"], 0, 255)]
        if not reg.writable or reg.name in ("ESC_ID", "can_br"):
            raise ValueError("register is read-only here; use Change ID for ESC_ID")
        value = (
            number(message["value"], -3.4e38, 3.4e38)
            if reg.kind == "f"
            else integer(message["value"], 0, 0xFFFFFFFF)
        )
        if reg.name in ("PMAX", "VMAX", "TMAX") and value <= 0:
            raise ValueError("mapping ranges must be positive")
        if reg.name == "CTRL_MODE" and value not in dm.MODE_NAMES:
            raise ValueError("mode must be 1 to 4")
        if reg.name == "MST_ID":
            self.check_master(integer(value, 0, 0x7FF), bus.motors)
            if any(
                m.can_id != motor.can_id and m.master_id == value
                for m in bus.motors.values()
            ):
                raise ValueError("another motor uses that feedback ID")
        echo = bus.write(motor.can_id, reg.rid, value)
        if echo is None:
            raise ValueError("write not confirmed")
        motor.registers[reg.rid] = echo
        attr = {
            "MST_ID": "master_id",
            "CTRL_MODE": "mode",
            "PMAX": "pmax",
            "VMAX": "vmax",
            "TMAX": "tmax",
        }.get(reg.name)
        if attr:
            setattr(motor, attr, echo)
        return f"{reg.name} = {echo} (RAM)"

    @staticmethod
    def check_master(master, ids):
        if master == dm.CONFIG_ID or any(i & 255 == master & 255 for i in ids):
            raise ValueError(
                "feedback ID collides with a motor command or configuration ID"
            )

    def change_id(self, bus, motor, message):
        new_id = integer(message["new_id"], 1, 15)
        master = integer(message["master"], 0, 0x7FF)
        old = motor.can_id
        self.check_master(master, (set(bus.motors) - {old}) | {new_id})
        if any(m.can_id != old and m.master_id == master for m in bus.motors.values()):
            raise ValueError("another motor uses that feedback ID")
        if new_id != old and bus.read(new_id, dm.RID["ESC_ID"], tries=1) is not None:
            raise ValueError("another motor answers at that ID")
        if bus.write(old, dm.RID["MST_ID"], master) is None:
            raise ValueError("feedback ID write not confirmed")
        motor.master_id = master
        bus.write(old, dm.RID["ESC_ID"], new_id)
        now = new_id if bus.read(new_id, dm.RID["ESC_ID"]) is not None else old
        saved = bus.save(now)
        bus.motors.pop(old, None)
        self.commands.pop(f"{bus.name}:{old}", None)
        at_new = bus.probe(new_id)
        at_old = old != new_id and bus.probe(old)
        return {
            "saved": saved,
            "at_new": bool(at_new),
            "at_old": bool(at_old),
            "result": "scan after a power cycle if the new ID is not answering",
        }

    def snapshot(self, after):
        with self.lock:
            now = time.monotonic()
            robot = self.robot
            motors = []
            for name, bus in self.buses.items():
                for m in list(bus.motors.values()):
                    fb = m.feedback
                    key = f"{name}:{m.can_id}"
                    motors.append(
                        dict(
                            key=key,
                            bus=name,
                            id=m.can_id,
                            master=m.master_id,
                            mode=m.mode,
                            registers=dict(m.registers),
                            feedback=asdict(fb) if fb else None,
                            age=now - fb.t if fb else None,
                            state=fb.state_name if fb else "no feedback",
                            command=asdict(self.commands.get(key, Command())),
                        )
                    )
            imu = {}
            for report, message in self.imu.items():
                stamps = list(self.imu_times[report])
                hz = (
                    (len(stamps) - 1) / (stamps[-1] - stamps[0])
                    if len(stamps) > 1 and stamps[-1] > stamps[0]
                    else 0
                )
                imu[report] = dict(message, age=now - message["t"], hz=hz)
            return dict(
                connected=bool(robot and not robot.error),
                error=(robot.error if robot and robot.error else self.error),
                control=self.control,
                status=robot.status if robot else None,
                info=robot.info if robot else {},
                motors=motors,
                imu=imu,
                limits=self.limits,
                rate=self.rate,
                events=[e for e in self.events if e["seq"] > after],
                seq=self.seq,
            )


class DaemonManager:
    def __init__(self, sim=False):
        self.sim = sim
        self.process = None
        self.lock = asyncio.Lock()

    @staticmethod
    def listening():
        try:
            with socket.create_connection(("127.0.0.1", diag_client.PORT), timeout=0.2):
                return True
        except OSError:
            return False

    async def action(self, start):
        async with self.lock:
            if start and await asyncio.to_thread(self.listening):
                return "diagd is already running"
            if self.sim:
                if start:
                    with (HERE / "diagd.log").open("ab") as log:
                        self.process = subprocess.Popen(
                            [sys.executable, "-u", str(HERE / "diagd.py"), "--sim"],
                            stdout=log,
                            stderr=log,
                            stdin=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        )
                    for _ in range(40):
                        await asyncio.sleep(0.1)
                        if self.process.poll() is not None:
                            raise ValueError("diagd failed to start; see sbc/diagd.log")
                        if await asyncio.to_thread(self.listening):
                            return "diagd started (simulation)"
                    raise ValueError("diagd did not become ready; see sbc/diagd.log")
                if self.process and self.process.poll() is None:
                    self.process.terminate()
                    await asyncio.to_thread(self.process.wait, 5)
                    return "diagd stopped"
                raise ValueError("no simulator started by this console")
            script = HERE / ("start_diagd.sh" if start else "stop_diagd.sh")
            proc = await asyncio.create_subprocess_exec(
                "bash",
                str(script),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            output, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            text = output.decode(errors="replace").strip()
            if proc.returncode:
                raise ValueError(text)
            return text


class WifiManager:
    """Network jobs outlive their initiating browser's network connection."""

    def __init__(self, sim=False):
        self.sim = sim
        self.task = None
        self.state = dict(busy=False, message="", error="", saved=[], networks=[])
        if sim:
            self.state.update(
                interface="wlan0",
                current="Bench Wi-Fi",
                ip="127.0.0.1",
                preferred="Bench Wi-Fi",
                saved=["Bench Wi-Fi"],
                networks=[
                    dict(ssid="Bench Wi-Fi", dbm=-40, security="WPA/WPA2"),
                    dict(ssid="Workshop", dbm=-60, security="WPA/WPA2"),
                    dict(ssid="Guest", dbm=-70, security="Open"),
                ],
            )

    async def run(self, request):
        if self.sim:
            await asyncio.sleep(0.05)
            op, ssid = request["op"], request.get("ssid")
            if op == "connect":
                if ssid not in [p["ssid"] for p in self.state["networks"]]:
                    raise ValueError("Network is no longer visible")
                if (
                    ssid != "Guest"
                    and ssid not in self.state["saved"]
                    and len(request.get("password", "")) < 8
                ):
                    raise ValueError("Wi-Fi password must be at least 8 bytes")
                self.state.update(current=ssid, preferred=ssid)
                if ssid not in self.state["saved"]:
                    self.state["saved"].append(ssid)
            elif op == "forget":
                if ssid not in self.state["saved"]:
                    raise ValueError("Select a saved network")
                self.state["saved"].remove(ssid)
                for key in ("current", "preferred"):
                    if self.state.get(key) == ssid:
                        self.state[key] = None
            return dict(self.state)
        process = await asyncio.create_subprocess_exec(
            "sudo",
            "-n",
            "/usr/lib/bipedal-console/wifi-helper",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            output, _ = await asyncio.wait_for(
                process.communicate(json.dumps(request).encode()), 65
            )
        except (TimeoutError, asyncio.CancelledError):
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        if process.returncode:
            raise ValueError("Wi-Fi helper unavailable; run install_console_wifi.sh")
        reply = json.loads(output)
        if not reply["ok"]:
            raise ValueError(reply["error"])
        return reply["result"]

    async def job(self, request):
        try:
            self.state.update(await self.run(request))
            if request["op"] != "status":
                self.state.update(
                    error="",
                    message={
                        "scan": "Wi-Fi scan complete",
                        "connect": "Connected; network saved",
                        "forget": "Network forgotten",
                    }[request["op"]],
                )
        except Exception as error:
            self.state.update(error=str(error), message="")
        finally:
            self.state["busy"] = False

    async def action(self, message):
        op = message["op"].removeprefix("wifi.")
        if op not in ("scan", "connect", "forget", "status"):
            raise ValueError("Unknown Wi-Fi action")
        # Polling during a job returns cached progress without competing with it.
        if self.state["busy"]:
            if op != "status":
                raise ValueError("Another Wi-Fi action is running")
        else:
            self.state.update(
                busy=True,
                message={
                    "scan": "Scanning Wi-Fi…",
                    "connect": "Connecting… The console may disconnect while Wi-Fi changes.",
                    "forget": "Forgetting network…",
                    "status": self.state["message"],
                }[op],
            )
            self.task = asyncio.create_task(self.job(dict(message, op=op)))
            if op == "status":
                await asyncio.shield(self.task)
        return dict(self.state)


async def websocket(request):
    # Reject cross-origin browser control, including CSRF from unrelated sites.
    origin = request.headers.get("Origin")
    if origin and origin != f"{request.scheme}://{request.host}":
        raise web.HTTPForbidden(text="same-origin connections only")
    ws = web.WebSocketResponse(max_msg_size=8192, heartbeat=5)
    await ws.prepare(request)
    session = Session()
    request.app["sessions"].add(session)
    busy = asyncio.Lock()
    tasks = set()

    async def execute(message):
        rid = message.get("req")
        try:
            op = message["op"]
            if op.startswith("wifi."):
                if op in ("wifi.connect", "wifi.forget"):
                    await asyncio.to_thread(session.stop, True)
                result = await request.app["wifi"].action(message)
            elif op == "stop":
                await asyncio.to_thread(session.stop)
                result = "all motors stopped"
            elif op == "release":
                await asyncio.to_thread(session.stop, True)
                result = "control released"
            else:
                if busy.locked():
                    raise ValueError("another action is still running")
                async with busy:
                    if op in ("daemon.start", "daemon.stop"):
                        if op == "daemon.stop":
                            # Quiesce all browser streamers before stopping the API.
                            for other in list(request.app["sessions"]):
                                await asyncio.to_thread(other.stop, True)
                        result = await request.app["manager"].action(
                            op == "daemon.start"
                        )
                    else:
                        result = await asyncio.to_thread(session.action, message)
            await ws.send_json(dict(type="reply", req=rid, ok=True, result=result))
        except Exception as error:
            if not ws.closed:
                await ws.send_json(
                    dict(type="reply", req=rid, ok=False, error=str(error))
                )

    async def push():
        after = 0
        while not ws.closed:
            state = session.snapshot(after)
            after = state["seq"]
            await ws.send_json(dict(type="state", **state))
            await asyncio.sleep(0.1)

    sender = asyncio.create_task(push())
    try:
        await ws.send_json(
            dict(
                type="schema",
                registers=[asdict(r) for r in dm.REGISTERS],
                modes=dm.MODE_NAMES,
            )
        )
        async for packet in ws:
            if packet.type == WSMsgType.TEXT:
                try:
                    message = json.loads(packet.data)
                    if not isinstance(message, dict) or not isinstance(
                        message.get("op"), str
                    ):
                        raise ValueError("expected an action object")
                    # A native confirm() dialog suspends the browser's ping
                    # timer. Its subsequent action is fresh proof of liveness.
                    # This does not restore control or resume stopped motors.
                    session.last_ping = time.monotonic()
                    if message["op"] == "ping":
                        continue
                    elif len(tasks) >= 4:
                        await ws.send_json(
                            dict(
                                type="reply",
                                req=message.get("req"),
                                ok=False,
                                error="too many pending actions",
                            )
                        )
                    else:
                        task = asyncio.create_task(execute(message))
                        tasks.add(task)
                        task.add_done_callback(tasks.discard)
                except (ValueError, TypeError):
                    await ws.send_json(
                        dict(type="reply", ok=False, error="invalid JSON action")
                    )
    finally:
        session.close()
        request.app["sessions"].discard(session)
        sender.cancel()
        with contextlib.suppress(asyncio.CancelledError, ConnectionError):
            await sender
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    return ws


async def asset(request):
    name = request.match_info.get("name", "index.html")
    if name not in ("index.html", "console.js", "console.css"):
        raise web.HTTPNotFound()
    return web.FileResponse(ASSETS / name, headers={"Cache-Control": "no-cache"})


def create_app(sim=False):
    app = web.Application()
    app["manager"] = DaemonManager(sim)
    app["sessions"] = set()
    app["wifi"] = WifiManager(sim)
    app.router.add_get("/", asset)
    app.router.add_get("/ws", websocket)
    app.router.add_get("/{name}", asset)

    async def shutdown(app):
        for session in list(app["sessions"]):
            session.close()
        if app["wifi"].task:
            await app["wifi"].task

    app.on_shutdown.append(shutdown)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--sim", action="store_true")
    args = parser.parse_args()
    web.run_app(create_app(args.sim), host=args.listen, port=args.port)
