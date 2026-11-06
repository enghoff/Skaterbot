# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Serve the controller's diagnostics link to programs on the Pi, and through SSH to a PC.

    python3 diagd.py                         UART4 at 1.5 Mbaud; clients on 127.0.0.1:7700
    python3 diagd.py --listen 0.0.0.0:7700   open to the network: anyone on it can drive
                                             the motors, so only on a network of your own
    python diagd.py --sim                    a simulated controller and motors, on any
                                             computer (diag_sim.py)

docs/DIAGNOSTICS.md is the specification. The commands start_diagd and
stop_diagd, beside this, start it detached and stop it. The controller has to
be running firmware/diag, which flash_mcu.py puts there; stop this first, since
it holds UART4 for as long as it runs:

    python3 flash_mcu.py diag.elf --listen 0

It turns the controller's frames into one JSON object a line, for any number of
clients: every CAN frame on the three buses, the IMU's reports decoded, the
controller's status ten times a second, and its log. One client at a time holds
control, and only that one may put anything on a bus or the I2C; any client may
stop every motor. diag_client.py is a client, and the library bench/motor_gui.py
uses.

What it watches: a client holding control that goes away, or says nothing for
half a second, has every motor stopped and loses control. It pings the
controller every 50 ms, and the controller stops every motor itself if those
stop coming. Everything it hears and does that matters is printed here as well.

It also shows the robot's health on the Pi's status LED, as the controller
shows it on its own: the heartbeat while all is well, and a fault's blink
while the IMU, the battery monitor, a CAN bus or the link between the two
boards is not (docs/DIAGNOSTICS.md, "The heartbeat LEDs"). --led names the
LED's sysfs directory; --led none leaves it alone.

Only the standard library. On the Pi it reaches UART4 through flash_mcu.py's
Port, which wants that file beside this one.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

import diag_link as dl

PORT = 7700
BAUD = 1_500_000
PING_S = 0.05
# No status for this long and the controller is taken to be gone.
LINK_TIMEOUT_S = 0.5
HELLO_S = 1.0
CONTROL_SILENCE_S = 0.5
# A can.request's own timeout: the controller answers in about a millisecond.
REQUEST_DEFAULT_S, REQUEST_MOST_S = 0.02, 1.0
IMU_ANSWER_S = 0.5
# Lines held for a client that is not reading; past this, events are dropped.
BACKLOG = 20_000

STREAMS = {"can", "imu", "imu.raw", "imu.diag", "status", "log", "drive"}

# SH-2's input reports: name, fixed-point Q, values. The rotation vector's fifth
# value is its accuracy estimate, in Q12 radians.
REPORTS = {
    0x01: ("accel", 8, 3),
    0x02: ("gyro", 9, 3),
    0x03: ("mag", 4, 3),
    0x04: ("linear", 8, 3),
    0x05: ("rotation", 14, 5),
    0x06: ("gravity", 8, 3),
    0x08: ("game", 14, 4),
}
REPORT_IDS = {name: rid for rid, (name, _, _) in REPORTS.items()}
# Every record that can share a report packet, so that one can be walked.
LENGTHS = {0x01: 10, 0x02: 10, 0x03: 10, 0x04: 10, 0x05: 14, 0x06: 10}
LENGTHS |= {0x07: 16, 0x08: 12, 0x09: 14, 0x0F: 16, 0x28: 14, 0x29: 12}
LENGTHS |= {0x2A: 14, 0xFA: 5, 0xFB: 5}


class Refused(Exception):
    pass


# ---- the robot's health, on the Pi's LED -------------------------------------

# As firmware/diag/src/health.rs has them, for a controller without HEALTH.
GRACE_S = 3.0
BUS_OFF_HOLD_S = 5.0
# No status at all for this long after starting is a link fault too.
FIRST_STATUS_S = 5.0
# The controller sends HEALTH every second; older than this, it has stopped.
HEALTH_FRESH_S = 2.5
HEALTH_S = 0.2
# The M4 Zero's red status LED, which robot_poweroff.py restores at boot.
LED = "/sys/class/leds/red:status"
# diagd's own condition, never on the wire.
LINK_DOWN = 1 << 8
CONDITIONS = dl.HEALTH_NAMES | {LINK_DOWN: "link down"}
EXPLAINED = {
    dl.IMU_MISSING: "the IMU has not answered on I2C for 3 s",
    dl.IMU_SILENT: "the IMU answers on I2C but has sent no report since it was "
    "found; power-cycle the robot",
    dl.INA_MISSING: "the INA226 battery monitor has not answered for 3 s",
    dl.BUS_OFF: "a CAN bus has gone bus-off",
    dl.PI_SILENT: "the controller hears nothing from the Pi",
    LINK_DOWN: "no status from the controller",
}
# Each fault's (lit ms, dark ms), the same on both boards' LEDs.
PATTERNS = {"link": (500, 500), "imu": (100, 100), "hardware": (1000, 200)}
# The heartbeat with a third, shorter flash: the fast speed mode, as the controller's
# health.rs FAST has it. (lit, ms) in turn, at the controller's idle period of 1260 ms.
FAST_BEAT = [(1, 70), (0, 245), (1, 70), (0, 140), (1, 40), (0, 695)]
# A word that the fast mode is on holds this long unless it is said again.
FAST_HOLD_S = 2.0
SHOWN_AS = {
    "link": "an even blink once a second",
    "imu": "a fast flicker",
    "hardware": "lit with a short wink dark",
}


def fault_of(flags: int) -> str | None:
    """The fault an LED shows for these conditions: the link first, then the
    IMU, then the rest, as the controller's own LED chooses."""
    if flags & (LINK_DOWN | dl.PI_SILENT):
        return "link"
    if flags & (dl.IMU_MISSING | dl.IMU_SILENT):
        return "imu"
    if flags & (dl.INA_MISSING | dl.BUS_OFF):
        return "hardware"
    return None


def describe(flags: int) -> str:
    fault = fault_of(flags)
    if fault is None:
        return "all clear; the LEDs beat their heartbeat"
    why = "; ".join(text for bit, text in EXPLAINED.items() if flags & bit)
    return f"{fault} fault, shown as {SHOWN_AS[fault]}: {why}"


class Health:
    """The robot's health: the controller's own verdict, from HEALTH, or for an
    image that does not send it what STATUS and IMU_DIAG show. Either way the
    link is diagd's to judge, since a controller it cannot hear says nothing."""

    def __init__(self, now: float):
        self.started = now
        self.firmware: tuple[float, int] | None = None
        self.imu_missing_since: float | None = None
        self.imu_found_since: float | None = None
        self.ina_missing_since: float | None = None
        self.bus_off_at: float | None = None

    def heard(self, flags: int, now: float) -> None:
        self.firmware = (now, flags)

    def status(self, status: dict, now: float) -> None:
        def since(held: bool, t: float | None) -> float | None:
            return (now if t is None else t) if held else None

        found = bool(status.get("imu_found"))
        self.imu_missing_since = since(not found, self.imu_missing_since)
        self.imu_found_since = since(found, self.imu_found_since)
        ina = bool(status.get("ina_found"))
        self.ina_missing_since = since(not ina, self.ina_missing_since)
        buses = status.get("buses", {}).values()
        if any(b.get("state") == "bus off" for b in buses):
            self.bus_off_at = now

    def flags(self, now: float, link_up: bool, ever_up: bool, imu_diag: dict) -> int:
        if not link_up:
            late = ever_up or now - self.started >= FIRST_STATUS_S
            return LINK_DOWN if late else 0
        if self.firmware and now - self.firmware[0] < HEALTH_FRESH_S:
            return self.firmware[1]

        def held(t: float | None) -> bool:
            return t is not None and now - t >= GRACE_S

        flags = 0
        if held(self.imu_missing_since):
            flags |= dl.IMU_MISSING
        # Without HEALTH, silence is what IMU_DIAG shows: found, and not one
        # input report since the controller started.
        if held(self.imu_found_since) and imu_diag.get("input_packets") == 0:
            flags |= dl.IMU_SILENT
        if held(self.ina_missing_since):
            flags |= dl.INA_MISSING
        if self.bus_off_at is not None and now - self.bus_off_at < BUS_OFF_HOLD_S:
            flags |= dl.BUS_OFF
        return flags


def board_model() -> str:
    try:
        return Path("/proc/device-tree/model").read_text()
    except OSError:
        return ""


class Led:
    """The Pi's status LED, through sysfs. While all is well it runs the
    kernel's heartbeat trigger, exactly as robot_poweroff.py --start-heartbeat
    leaves it; a fault is the timer trigger's square wave; and shutdown leaves
    it dark, as --stop-heartbeat does. A path of None writes nothing and only
    remembers what it would show.

    The M4 Zero's red LED is lit at brightness 0, so on it the heartbeat is
    inverted, dark is max_brightness, and a fault's lit and dark times swap
    places in the timer's delays. Writes go through sudo when diagd may not
    make them itself, as on the Pi, where it runs as admin."""

    RETRY_S = 30.0

    def __init__(self, path: str | None, inverted: bool | None = None):
        self.path = Path(path) if path else None
        if inverted is None:
            inverted = self.path is not None and (
                self.path.name == "red:status" and "BPI-M4-Zero" in board_model()
            )
        self.inverted = inverted
        self.lock = threading.Lock()
        self.held = False
        self.sudo = False
        self.failed = False
        self.retry_at = 0.0
        self.shown: str | None = self.current()
        self.can_pattern = self.offers("pattern")

    def offers(self, trigger: str) -> bool:
        if self.path is None:
            return True
        try:
            return (
                trigger
                in (self.path / "trigger")
                .read_text()
                .replace("[", " ")
                .replace("]", " ")
                .split()
            )
        except OSError:
            return False

    def current(self) -> str | None:
        """heartbeat, if that is what the LED already shows; else unknown."""
        if self.path is None:
            return None
        try:
            if "[heartbeat]" not in (self.path / "trigger").read_text():
                return None
            invert = self.path / "invert"
            if self.inverted and invert.read_text().strip() != "1":
                return None
        except OSError:
            return None
        return "heartbeat"

    def writes(self, pattern: str) -> list[tuple[str, str]]:
        if pattern == "fast":
            # The pattern trigger ramps from each entry to the next, so each holds
            # for its time and then steps in no time.
            top = (self.path / "max_brightness").read_text().strip()
            steps = []
            for lit, ms in FAST_BEAT:
                level = (
                    ("0" if lit else top) if self.inverted else (top if lit else "0")
                )
                steps += [f"{level} {ms}", f"{level} 0"]
            return [("trigger", "pattern"), ("pattern", " ".join(steps))]
        if pattern == "heartbeat":
            return [("trigger", "heartbeat")] + [("invert", "1")] * self.inverted
        if pattern == "dark":
            if self.inverted:
                dark = (self.path / "max_brightness").read_text().strip()
            else:
                dark = "0"
            return [("trigger", "none"), ("brightness", dark)]
        lit, dark = PATTERNS[pattern]
        on, off = (dark, lit) if self.inverted else (lit, dark)
        return [("trigger", "timer"), ("delay_on", str(on)), ("delay_off", str(off))]

    def write(self, name: str, value: str) -> None:
        target = self.path / name
        if not self.sudo:
            try:
                target.write_text(value)
                return
            except PermissionError:
                self.sudo = True
        result = subprocess.run(
            ["sudo", "-n", "tee", str(target)],
            input=value,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=3,
        )
        if result.returncode:
            raise OSError(result.stderr.strip() or f"sudo tee {target} refused")

    def show(self, pattern: str, hold: bool = False) -> None:
        """heartbeat, dark, or a fault in PATTERNS. hold keeps it whatever is
        asked for after, which is what shutdown wants."""
        with self.lock:
            if self.held:
                return
            if pattern == "fast" and not self.can_pattern:
                pattern = "heartbeat"
            self.held = hold
            if pattern == self.shown:
                return
            if self.path is None:
                self.shown = pattern
                return
            if time.monotonic() < self.retry_at:
                return
            try:
                for name, value in self.writes(pattern):
                    self.write(name, value)
            except (OSError, subprocess.SubprocessError) as error:
                self.shown = None
                self.retry_at = time.monotonic() + self.RETRY_S
                if not self.failed:
                    say(f"led: could not show {pattern} on {self.path}: {error}")
                self.failed = True
                return
            self.shown = pattern

    def release(self) -> None:
        """On diagd's way out a fault's blink would outlive its judge, so the
        heartbeat comes back. Dark, for a shutdown, stays."""
        with self.lock:
            leave = self.held or self.shown in (None, "heartbeat")
        if not leave:
            self.show("heartbeat")


# ---- the controller's end ----------------------------------------------------


class SerialStream:
    def __init__(self, path: str | None, baud: int):
        from flash_mcu import Port, uart4

        self.port = Port(path or uart4(), baud)
        self.where = f"{self.port.path} at {baud} baud"

    def read(self, timeout: float) -> bytes:
        if select.select([self.port.fd], [], [], timeout)[0]:
            return os.read(self.port.fd, 4096)
        return b""

    def write(self, data: bytes) -> None:
        self.port.write(data, drain=False)


class SocketStream:
    def __init__(self, sock: socket.socket, where: str):
        self.sock = sock
        self.where = where

    def read(self, timeout: float) -> bytes:
        if select.select([self.sock], [], [], timeout)[0]:
            data = self.sock.recv(4096)
            if not data:
                raise OSError("the simulated controller has gone")
            return data
        return b""

    def write(self, data: bytes) -> None:
        self.sock.sendall(data)


# ---- the clients' end --------------------------------------------------------


def line(message: dict) -> bytes:
    return (json.dumps(message, separators=(",", ":")) + "\n").encode()


class Client:
    def __init__(self, daemon: Daemon, sock: socket.socket, peer: str):
        self.daemon = daemon
        self.sock = sock
        self.peer = peer
        self.name = peer
        self.streams = {"status", "log"}
        self.last_heard = time.monotonic()
        self.out: deque[bytes] = deque()
        self.ready = threading.Condition()
        self.dropped = 0
        self.closed = False

    def __str__(self) -> str:
        return self.name if self.name == self.peer else f"{self.name} ({self.peer})"

    def push(self, data: bytes) -> None:
        with self.ready:
            if len(self.out) >= BACKLOG:
                self.dropped += 1
                return
            self.out.append(data)
            self.ready.notify()

    def reply(self, rid, ok: bool = True, **fields) -> None:
        if rid is None:
            return
        message = {"req": rid, "ok": ok, **fields}
        self.push(line(message))

    def write_loop(self) -> None:
        while True:
            with self.ready:
                while not self.out and not self.closed:
                    self.ready.wait()
                if self.closed:
                    return
                batch = b"".join(self.out)
                self.out.clear()
            try:
                self.sock.sendall(batch)
            except OSError:
                self.daemon.drop(self)
                return

    def read_loop(self) -> None:
        try:
            for raw in self.sock.makefile("rb"):
                self.last_heard = time.monotonic()
                self.daemon.request(self, raw)
        except OSError:
            pass
        self.daemon.drop(self)

    def close(self) -> None:
        with self.ready:
            self.closed = True
            self.ready.notify()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


def say(text: str) -> None:
    print(f"{time.strftime('%H:%M:%S')}  {text}", flush=True)


class Daemon:
    def __init__(self, stream, poweroff=None, led: Led | None = None):
        self.stream = stream
        self.lock = threading.RLock()
        self.write_lock = threading.Lock()
        self.clients: list[Client] = []
        self.owner: Client | None = None
        self.decoder = dl.Decoder()
        self.info: dict[str, str] = {}
        self.status: dict | None = None
        self.status_at = 0.0
        self.uptime = 0.0
        self.link_up = False
        self.last_sent = 0.0
        self.last_hello = 0.0
        self.started = time.monotonic()
        self.warned_silent = False
        # (client, id, bus, expect, deadline): can.requests in the order sent.
        self.requests: list[tuple] = []
        # tag: (client, id, deadline)
        self.i2c: dict[int, tuple] = {}
        self.tag = 0
        # (client, id, what, deadline): imu.enable and imu.info, waiting.
        self.imu_waiting: list[tuple] = []
        self.shtp_seq = [0] * 6
        self.epoch = 0
        self.last_raw: int | None = None
        self.running = True
        self.poweroff = poweroff
        self.shutting_down = False
        self.button_shutdown_pending = False
        self.button_shutdown_retry_at = 0.0
        self.fast_until = 0.0
        self.imu_diag: dict = {}
        self.imu_control: deque = deque(maxlen=32)
        self.imu_internal_errors: deque = deque(maxlen=32)
        self.imu_features: dict = {}
        self.imu_parse_errors = 0
        self.led = led or Led(None)
        self.health = Health(self.started)
        self.health_flags = 0

    # -- to the controller -------------------------------------------------------

    def mcu(self, kind: int, body: bytes = b"") -> None:
        data = dl.encode(kind, body)
        with self.write_lock:
            self.stream.write(data)
            self.last_sent = time.monotonic()

    def shtp(self, channel: int, payload: bytes) -> None:
        with self.lock:
            seq = self.shtp_seq[channel]
            self.shtp_seq[channel] = (seq + 1) & 0xFF
        header = struct.pack("<HBB", len(payload) + 4, channel, seq)
        self.mcu(dl.IMU_WRITE, header + payload)

    def stop(self, why: str) -> None:
        self.mcu(dl.STOP)
        self.log(f"stop: {why}")

    # -- to the clients ----------------------------------------------------------

    def broadcast(self, stream: str | None, message: dict, skip: Client | None = None):
        """To every client subscribed to stream, or to every client if None."""
        data = line(message)
        with self.lock:
            clients = list(self.clients)
        for c in clients:
            if c is not skip and (stream is None or stream in c.streams):
                c.push(data)

    def log(self, text: str, t: float | None = None) -> None:
        say(text)
        self.broadcast("log", {"ev": "log", "t": t, "text": text})

    # -- what the controller says ------------------------------------------------

    def unwrap(self, t_us: int) -> float:
        """The controller's 32-bit microseconds as seconds since it started."""
        with self.lock:
            last = self.last_raw
            if last is not None and t_us > last and t_us - last > 1 << 31:
                # From just before a wrap, heard just after it.
                return (self.epoch - (1 << 32) + t_us) / 1e6
            if last is not None and t_us < last and last - t_us > 1 << 31:
                self.epoch += 1 << 32
            self.last_raw = t_us
            return (self.epoch + t_us) / 1e6

    def read_loop(self) -> None:
        while self.running:
            try:
                data = self.stream.read(0.1)
            except OSError as error:
                self.log(f"link: {error}")
                self.running = False
                break
            if not data:
                continue
            for kind, body in self.decoder.feed(data):
                try:
                    self.heard(kind, body)
                except (struct.error, IndexError, ValueError) as error:
                    self.log(
                        f"link: a message of type {kind:#04x} made no sense: {error}"
                    )

    def heard(self, kind: int, body: bytes) -> None:
        if kind == dl.CAN_RECV:
            self.can_frame(body)
        elif kind == dl.STATUS:
            self.got_status(dl.parse_status(body))
        elif kind == dl.IMU_PACKET:
            t = self.unwrap(int.from_bytes(body[:4], "little"))
            self.imu_packet(t, body[4:])
        elif kind == dl.IMU_DIAG:
            with self.lock:
                self.imu_diag = dl.parse_imu_diag(body)
            self.broadcast("imu.diag", {"ev": "imu.diag", **self.imu_diag})
        elif kind == dl.HEALTH:
            _, flags = dl.parse_health(body)
            with self.lock:
                self.health.heard(flags, time.monotonic())
        elif kind == dl.INFO:
            info = dl.parse_info(body)
            if info != self.info:
                self.info = info
                keys = ("firmware", "uid", "reset", "imu", "ina226", "last_crash")
                self.log(
                    "controller: " + ", ".join(f"{k} {info.get(k, '?')}" for k in keys)
                )
        elif kind == dl.STOPPED:
            why = dl.STOP_REASONS.get(body[0], f"reason {body[0]}")
            self.log(f"controller: every motor stopped ({why})")
            self.broadcast(None, {"ev": "stopped", "why": why})
        elif kind == dl.LOG:
            t = self.unwrap(int.from_bytes(body[:4], "little"))
            self.log("controller: " + body[4:].decode(errors="replace"), t)
        elif kind == dl.I2C_RESULT:
            with self.lock:
                waiting = self.i2c.pop(body[0], None)
            if waiting:
                client, rid, _ = waiting
                status = dl.I2C_STATUS.get(body[1], f"status {body[1]}")
                if body[1] == 0:
                    client.reply(rid, data=body[2:].hex())
                else:
                    client.reply(rid, False, error=f"i2c: {status}")

    def got_status(self, status: dict) -> None:
        if status["uptime"] < self.uptime - 1:
            with self.lock:
                self.epoch, self.last_raw = 0, None
            self.log("controller: it has restarted")
        self.uptime = status["uptime"]
        status["t"] = self.unwrap(status.pop("t_us"))
        with self.lock:
            self.status = status
            self.status_at = time.monotonic()
            self.health.status(status, self.status_at)
            came_up = not self.link_up
            self.link_up = True
        if came_up:
            self.log(f"link: controller up, {self.stream.where}")
            self.broadcast(None, {"ev": "link", "up": True})
            self.mcu(dl.HELLO)
        self.broadcast("status", self.status_event())
        with self.lock:
            button_shutdown = (
                status.get("off", False)
                and not self.shutting_down
                and not self.button_shutdown_pending
                and time.monotonic() >= self.button_shutdown_retry_at
            )
            if button_shutdown:
                self.button_shutdown_pending = True
        if button_shutdown:
            # Scheduling systemd must not block the UART reader or its status flow.
            threading.Thread(target=self.power_button_shutdown, daemon=True).start()

    def power_button_shutdown(self) -> None:
        try:
            self.shutdown("power button")
        except Refused as error:
            self.log(f"power: button shutdown failed: {error}; retrying in 1 s")
        finally:
            with self.lock:
                self.button_shutdown_pending = False
                self.button_shutdown_retry_at = time.monotonic() + 1

    def status_event(self) -> dict:
        with self.lock:
            status = dict(self.status or {})
            status["ev"] = "status"
            status["link_up"] = self.link_up
            status["shutting_down"] = self.shutting_down
            status["pi"] = {
                "frames": self.decoder.frames,
                "crc_errors": self.decoder.crc_errors,
                "overruns": self.decoder.overruns,
                "clients": len(self.clients),
                "control": str(self.owner) if self.owner else None,
            }
            status["imu_diag"] = dict(self.imu_diag)
            status["health"] = self.health_event()
        return status

    def health_event(self) -> dict:
        flags = self.health_flags
        return {
            "fault": fault_of(flags),
            "conditions": [name for bit, name in CONDITIONS.items() if flags & bit],
            "led": self.led.shown,
        }

    def health_loop(self) -> None:
        while self.running:
            time.sleep(HEALTH_S)
            self.check_health(time.monotonic())

    def check_health(self, now: float) -> None:
        """Judges the robot's health, says so when it changes, and shows it
        on the Pi's LED unless a shutdown has the LED."""
        with self.lock:
            ever_up = self.status is not None
            flags = self.health.flags(now, self.link_up, ever_up, self.imu_diag)
            before, self.health_flags = self.health_flags, flags
            shutting_down = self.shutting_down
        if flags != before:
            self.log(f"health: {describe(flags)}")
        if not shutting_down:
            fast = now < self.fast_until
            self.led.show(fault_of(flags) or ("fast" if fast else "heartbeat"))

    def can_frame(self, body: bytes) -> None:
        t_us, bus, flags, can_id, data = dl.parse_can_recv(body)
        name = dl.BUSES[bus]
        frame = {
            "bus": name,
            "t": self.unwrap(t_us),
            "id": can_id,
            "ext": bool(flags & 1),
            "data": data.hex(),
        }
        if flags & 2:
            frame["rtr"] = True
        asker = None
        with self.lock:
            for i, (client, rid, rbus, expect, _) in enumerate(self.requests):
                if rbus == name and data.startswith(expect):
                    del self.requests[i]
                    asker = client
                    asker.reply(rid, frame=frame)
                    break
        self.broadcast("can", {"ev": "can", **frame}, skip=asker)

    def imu_packet(self, t: float, packet: bytes) -> None:
        self.broadcast("imu.raw", {"ev": "imu.raw", "t": t, "data": packet.hex()})
        if len(packet) < 4:
            return
        length = int.from_bytes(packet[:2], "little") & 0x7FFF
        channel, payload = packet[2], packet[4:length]
        if channel in (0, 1, 2):
            with self.lock:
                self.imu_control.append({"t": t, "data": packet.hex()})
        if channel in (3, 4):
            i = 0
            while i < len(payload):
                rid = payload[i]
                size = LENGTHS.get(rid)
                if size is None or i + size > len(payload):
                    self.imu_parse_errors += 1
                    break
                if rid in REPORTS:
                    name, q, count = REPORTS[rid]
                    raw = struct.unpack_from(f"<{count}h", payload, i + 4)
                    values = [v / (1 << q) for v in raw]
                    if rid == 0x05:
                        values[4] = raw[4] / (1 << 12)
                    self.broadcast(
                        "imu",
                        {
                            "ev": "imu",
                            "t": t,
                            "report": name,
                            "status": payload[i + 2] & 3,
                            "v": [round(v, 6) for v in values],
                        },
                    )
                i += size
        elif channel == 2 and payload[:1] == b"\xfc" and len(payload) >= 9:
            report = payload[1]
            interval = struct.unpack_from("<I", payload, 5)[0]
            hz = round(1e6 / interval, 3) if interval else 0
            with self.lock:
                self.imu_features[report] = {"t": t, "interval_us": interval, "hz": hz}
            self.imu_answer(
                ("feature", report), report=REPORTS.get(report, (report,))[0], hz=hz
            )
        elif channel == 2 and payload[:1] == b"\xf8" and len(payload) >= 14:
            major, minor, part, build, patch = struct.unpack_from("<BBIIH", payload, 2)
            self.imu_answer(
                ("product",), part=part, version=f"{major}.{minor}.{patch}", build=build
            )
        elif channel == 1 and payload[:1] == b"\x01":
            with self.lock:
                self.imu_features.clear()
            self.log("imu: reset complete", t)
        elif (
            channel == 2
            and len(payload) >= 16
            and payload[0] == 0xF1
            and payload[2] == 1
        ):
            error = dict(
                zip(
                    ("severity", "sequence", "source", "error", "module", "code"),
                    payload[5:11],
                )
            )
            if error["source"] != 255:
                error["t"] = t
                with self.lock:
                    self.imu_internal_errors.append(error)
                self.log(f"imu: internal error {error}", t)

    def imu_answer(self, what: tuple, **fields) -> None:
        with self.lock:
            answered = [w for w in self.imu_waiting if w[2] == what]
            self.imu_waiting = [w for w in self.imu_waiting if w[2] != what]
        for client, rid, _, _ in answered:
            client.reply(rid, **fields)

    # -- what the clients ask ----------------------------------------------------

    def request(self, client: Client, raw: bytes) -> None:
        rid = None
        try:
            message = json.loads(raw)
            if not isinstance(message, dict):
                raise Refused("a request is a JSON object")
            rid = message.get("req")
            op = message.get("op")
            handler = OPS.get(op)
            if handler is None:
                raise Refused(f"no such op {op!r}: {', '.join(sorted(OPS))}")
            result = handler(self, client, message)
        except KeyError as error:
            client.reply(rid, False, error=f"bad request: {error} missing")
            return
        except (ValueError, TypeError) as error:
            client.reply(rid, False, error=f"bad request: {error}")
            return
        except Refused as error:
            client.reply(rid, False, error=str(error))
            return
        if result is not None:
            client.reply(rid, **result)

    def need_control(self, client: Client) -> None:
        with self.lock:
            if self.shutting_down or (self.status and self.status.get("off")):
                raise Refused("the robot is shutting down")
            if self.owner is client:
                return
            held = f"; {self.owner} holds it" if self.owner else ""
        raise Refused(f"take control first{held}")

    def op_hello(self, client: Client, m: dict) -> dict:
        client.name = str(m.get("name", client.peer))
        self.log(f"client: {client} said hello")
        return {
            "info": self.info,
            "daemon": {
                "link": self.stream.where,
                "link_up": self.link_up,
                "port": PORT,
                "streams": sorted(STREAMS),
            },
            "control": str(self.owner) if self.owner else None,
        }

    def op_subscribe(self, client: Client, m: dict) -> dict:
        streams = set(m["streams"])
        if unknown := streams - STREAMS:
            raise Refused(f"no stream {', '.join(sorted(unknown))}: {sorted(STREAMS)}")
        client.streams = streams
        return {"streams": sorted(streams)}

    def op_ping(self, client: Client, m: dict) -> dict:
        return {}

    def op_status(self, client: Client, m: dict) -> dict:
        if self.status is None:
            raise Refused("no status from the controller yet")
        return {"status": self.status_event()}

    def op_imu_diagnostics(self, client: Client, m: dict) -> dict:
        """Read-only snapshots; never send sensor commands or take control."""
        with self.lock:
            return {
                "firmware": dict(self.imu_diag),
                "features": dict(self.imu_features),
                "internal_errors": list(self.imu_internal_errors),
                "control_packets": list(self.imu_control),
                "parse_errors": self.imu_parse_errors,
            }

    def op_control(self, client: Client, m: dict) -> dict:
        take = m.get("take", True)
        taken_from = None
        with self.lock:
            if take:
                if self.shutting_down or (self.status and self.status.get("off")):
                    raise Refused("the robot is shutting down")
                if self.owner not in (None, client):
                    if not m.get("force"):
                        raise Refused(f"{self.owner} holds control")
                    taken_from = self.owner
                self.owner = client
            elif self.owner is client:
                self.owner = None
            else:
                return {}
        if taken_from is not None:
            self.stop(f"{client} took control from {taken_from}")
        if take:
            self.log(f"control: {client} has it")
        else:
            # Whoever gives control up leaves nothing running behind them.
            self.stop(f"{client} gave up control")
        return {}

    def op_stop(self, client: Client, m: dict) -> dict:
        self.stop(f"asked by {client}")
        return {}

    def op_drive(self, client: Client, m: dict) -> dict:
        """What the operator is asking the policy for. It moves nothing by itself,
        so it needs no control: it goes to whatever runs the policy, the
        controller if its image says it takes it, and to the `drive` stream."""
        forward, turn = float(m["forward"]), float(m["turn"])
        height, live, jump = float(m["height"]), bool(m["live"]), int(m["jump"])
        mode = int(m.get("mode", 0))
        # What the message can carry, not what the robot may do: the limits on
        # the operator are gamepad.py's, and the firmware's own.
        if not (abs(forward) <= 30 and abs(turn) <= 30 and 0 <= height <= 1):
            raise Refused("a drive command out of all range")
        if not live:
            forward = turn = 0.0
        with self.lock:
            if self.shutting_down or (self.status and self.status.get("off")):
                raise Refused("the robot is shutting down")
            taken = self.info.get("drive") == "1"
        self.broadcast(
            "drive",
            {
                "ev": "drive",
                "forward": forward,
                "turn": turn,
                "height": height,
                "live": live,
                "jump": jump,
                "mode": mode,
            },
        )
        if taken:
            self.mcu(dl.DRIVE, dl.drive(forward, turn, height, live, jump))
        return {"taken": taken}

    def op_indicate(self, client: Client, m: dict) -> dict:
        """The robot is in its fast speed mode, or not: both LEDs add a short flash
        to the heartbeat for FAST_HOLD_S, unless it is said again."""
        fast = bool(m.get("fast"))
        with self.lock:
            self.fast_until = time.monotonic() + FAST_HOLD_S if fast else 0.0
        self.mcu(dl.INDICATE, bytes([1 if fast else 0]))
        self.check_health(time.monotonic())
        return {}

    def op_power_off(self, client: Client, m: dict) -> dict:
        self.need_control(client)
        return self.shutdown(f"power-off asked by {client}")

    def shutdown(self, why: str) -> dict:
        """One shutdown sequence for an API request and the physical button."""
        if self.poweroff is None:
            raise Refused("power-off is not configured on this daemon")
        with self.lock:
            if self.shutting_down:
                raise Refused("the robot is already shutting down")
            self.shutting_down = True
        try:
            self.stop(why)
            self.poweroff()
        except (OSError, subprocess.SubprocessError) as error:
            with self.lock:
                self.shutting_down = False
            raise Refused(f"could not schedule power-off: {error}") from error
        self.log("power: motors stopped; system shutdown scheduled")
        # The hook has darkened a heartbeat; a fault's blink is diagd's own.
        self.led.show("dark", hold=True)
        # Notify only after Linux accepted shutdown. Failure to stop an LED
        # must not undo a successfully queued system power-off.
        if self.info.get("shutdown_led") == "1":
            try:
                self.mcu(dl.SHUTDOWN)
            except OSError as error:
                self.log(f"power: could not notify MCU of shutdown: {error}")
        return {"shutting_down": True}

    def can_frame_from(self, m: dict) -> tuple[int, bytes]:
        bus = m["bus"]
        if bus not in dl.BUSES:
            raise Refused(f"no bus {bus!r}: A, B or C")
        can_id, extended = int(m["id"]), bool(m.get("ext", False))
        data = bytes.fromhex(m.get("data", ""))
        if len(data) > 8 or not 0 <= can_id < (1 << 29 if extended else 1 << 11):
            raise Refused("a classic CAN frame: up to 8 bytes, an 11-bit or 29-bit ID")
        return dl.BUSES.index(bus), dl.can_send(
            dl.BUSES.index(bus), can_id, data, extended
        )

    def op_can_send(self, client: Client, m: dict) -> dict:
        self.need_control(client)
        _, body = self.can_frame_from(m)
        self.mcu(dl.CAN_SEND, body)
        return {}

    def op_can_request(self, client: Client, m: dict) -> None:
        self.need_control(client)
        _, body = self.can_frame_from(m)
        expect = bytes.fromhex(m.get("expect", ""))
        wait = min(
            max(float(m.get("timeout", REQUEST_DEFAULT_S)), 0.001), REQUEST_MOST_S
        )
        with self.lock:
            entry = (client, m.get("req"), m["bus"], expect, time.monotonic() + wait)
            self.requests.append(entry)
        self.mcu(dl.CAN_SEND, body)
        return None

    def op_imu_enable(self, client: Client, m: dict) -> None:
        self.need_control(client)
        report = m["report"]
        report = REPORT_IDS.get(report, report)
        if not isinstance(report, int):
            raise Refused(f"no report {m['report']!r}: {', '.join(REPORT_IDS)}")
        hz = float(m.get("hz", 100))
        interval = round(1e6 / hz) if hz > 0 else 0
        self.wait_imu(client, m, ("feature", report))
        self.shtp(2, struct.pack("<BBBHIII", 0xFD, report, 0, 0, interval, 0, 0))
        return None

    def op_imu_info(self, client: Client, m: dict) -> None:
        self.need_control(client)
        self.wait_imu(client, m, ("product",))
        self.shtp(2, b"\xf9\x00")
        return None

    def wait_imu(self, client: Client, m: dict, what: tuple) -> None:
        with self.lock:
            deadline = time.monotonic() + IMU_ANSWER_S
            self.imu_waiting.append((client, m.get("req"), what, deadline))

    def op_imu_reset(self, client: Client, m: dict) -> dict:
        self.need_control(client)
        self.shtp(1, b"\x01")
        return {}

    def op_imu_write(self, client: Client, m: dict) -> dict:
        self.need_control(client)
        channel = int(m["channel"])
        if not 0 <= channel < 6:
            raise Refused("SHTP channels are 0 to 5")
        self.shtp(channel, bytes.fromhex(m["data"]))
        return {}

    def op_i2c(self, client: Client, m: dict) -> None:
        self.need_control(client)
        address, read = int(m["addr"]), int(m.get("read", 0))
        write = bytes.fromhex(m.get("write", ""))
        if not 0 <= address < 0x80 or not 0 <= read <= 64 or len(write) > 64:
            raise Refused("a 7-bit address, and up to 64 bytes each way")
        with self.lock:
            self.tag = tag = (self.tag + 1) & 0xFF
            self.i2c[tag] = (client, m.get("req"), time.monotonic() + 0.5)
        self.mcu(dl.I2C, dl.i2c_request(tag, address, write, read))
        return None

    # -- coming and going --------------------------------------------------------

    def accept_loop(self, server: socket.socket) -> None:
        while self.running:
            try:
                sock, peer = server.accept()
            except OSError:
                break
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            client = Client(self, sock, f"{peer[0]}:{peer[1]}")
            with self.lock:
                self.clients.append(client)
            threading.Thread(target=client.read_loop, daemon=True).start()
            threading.Thread(target=client.write_loop, daemon=True).start()

    def drop(self, client: Client) -> None:
        with self.lock:
            if client not in self.clients:
                return
            self.clients.remove(client)
            had_control = self.owner is client
            if had_control:
                self.owner = None
            self.requests = [r for r in self.requests if r[0] is not client]
            self.imu_waiting = [w for w in self.imu_waiting if w[0] is not client]
        client.close()
        self.log(f"client: {client} went away")
        if had_control:
            self.stop(f"{client}, which held control, went away")

    def timer_loop(self) -> None:
        while self.running:
            time.sleep(0.01)
            now = time.monotonic()
            try:
                if now - self.last_sent >= PING_S:
                    self.mcu(dl.PING)
                if not self.info and now - self.last_hello > HELLO_S:
                    self.last_hello = now
                    self.mcu(dl.HELLO)
                if not self.info and not self.warned_silent and now - self.started > 3:
                    # Said once: the usual reason is the wrong image, not a fault.
                    self.warned_silent = True
                    self.log(
                        f"link: no answer from the controller on {self.stream.where}. "
                        "Is it running firmware/diag? python3 flash_mcu.py diag.elf "
                        "--listen 0 puts it there, with diagd stopped"
                    )
            except OSError as error:
                self.log(f"link: {error}")
                self.running = False
                return
            self.expire(now)

    def expire(self, now: float) -> None:
        with self.lock:
            went_down = self.link_up and now - self.status_at > LINK_TIMEOUT_S
            if went_down:
                self.link_up = False
            late = [r for r in self.requests if r[4] < now]
            self.requests = [r for r in self.requests if r[4] >= now]
            late_i2c = [(t, w) for t, w in self.i2c.items() if w[2] < now]
            for tag, _ in late_i2c:
                del self.i2c[tag]
            late_imu = [w for w in self.imu_waiting if w[3] < now]
            self.imu_waiting = [w for w in self.imu_waiting if w[3] >= now]
            owner = self.owner
            silent = owner is not None and now - owner.last_heard > CONTROL_SILENCE_S
            if silent:
                self.owner = None
        for client, rid, *_ in late:
            client.reply(rid, False, error="timeout")
        for _, (client, rid, _) in late_i2c:
            client.reply(rid, False, error="i2c: no answer from the controller")
        for client, rid, _, _ in late_imu:
            client.reply(rid, False, error="no answer from the IMU")
        if went_down:
            self.log(f"link: no status from the controller for {LINK_TIMEOUT_S} s")
            self.broadcast(None, {"ev": "link", "up": False})
        if silent:
            self.stop(
                f"{owner} held control and said nothing for {CONTROL_SILENCE_S} s"
            )


OPS = {
    "hello": Daemon.op_hello,
    "subscribe": Daemon.op_subscribe,
    "ping": Daemon.op_ping,
    "status": Daemon.op_status,
    "imu.diagnostics": Daemon.op_imu_diagnostics,
    "control": Daemon.op_control,
    "indicate": Daemon.op_indicate,
    "stop": Daemon.op_stop,
    "drive": Daemon.op_drive,
    "power.off": Daemon.op_power_off,
    "can.send": Daemon.op_can_send,
    "can.request": Daemon.op_can_request,
    "imu.enable": Daemon.op_imu_enable,
    "imu.info": Daemon.op_imu_info,
    "imu.reset": Daemon.op_imu_reset,
    "imu.write": Daemon.op_imu_write,
    "i2c": Daemon.op_i2c,
}


def address(text: str) -> tuple[str, int]:
    host, _, port = text.rpartition(":")
    return (host or "127.0.0.1"), int(port or PORT)


def interrupt(*_) -> None:
    raise KeyboardInterrupt


def schedule_poweroff() -> None:
    hook = "/usr/lib/systemd/system-shutdown/robot-poweroff"
    if not os.access(hook, os.X_OK):
        raise OSError("install the robot-poweroff shutdown hook first")
    # Queue in systemd so it survives this daemon stopping. The brief delay
    # allows the client to receive its acknowledgement before SSH closes.
    result = subprocess.run(
        [
            "sudo",
            "-n",
            "/usr/bin/systemd-run",
            "--quiet",
            "--collect",
            "--unit=robot-gui-poweroff",
            "--on-active=2s",
            "--timer-property=AccuracySec=100ms",
            "/usr/bin/systemctl",
            "--no-block",
            "poweroff",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode:
        raise OSError(result.stderr.strip() or "systemd refused power-off")
    try:
        leds = subprocess.run(
            ["sudo", "-n", hook, "--stop-heartbeat"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if leds.returncode:
            say(f"power: heartbeat LED: {leds.stderr.strip()}")
    except (OSError, subprocess.SubprocessError) as error:
        say(f"power: heartbeat LED: {error}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", help="the controller's tty (default: find UART4)")
    ap.add_argument("--baud", type=int, default=BAUD, help=f"default {BAUD}")
    ap.add_argument(
        "--listen",
        default=f"127.0.0.1:{PORT}",
        help=f"where clients connect (default 127.0.0.1:{PORT})",
    )
    ap.add_argument("--sim", action="store_true", help="a simulated controller")
    ap.add_argument(
        "--sim-motors",
        default=None,
        help='the simulated motors\' CAN IDs, by bus (default "A:1,2 B:3,4 C:5,6")',
    )
    ap.add_argument(
        "--sim-faults",
        default="",
        help="faults for the simulated controller to have, comma-separated: "
        "imu-dead, imu-missing, ina-missing, bus-off",
    )
    ap.add_argument(
        "--sim-drive",
        action="store_true",
        help="the simulated controller takes DRIVE, as firmware running a policy "
        "will; firmware/diag does not",
    )
    ap.add_argument(
        "--led",
        default=None,
        help=f"the status LED's sysfs directory, or none (default {LED} on the "
        "robot, none with --sim)",
    )
    args = ap.parse_args()

    if args.sim:
        import diag_sim

        sock = diag_sim.start(
            args.sim_motors or diag_sim.DEFAULT_MOTORS,
            args.sim_faults.split(","),
            args.sim_drive,
        )
        stream = SocketStream(sock, "a simulated controller (diag_sim.py)")
    else:
        stream = SerialStream(args.port, args.baud)
    led_path = args.led
    if led_path is None:
        led_path = None if args.sim or not os.path.isdir(LED) else LED
    elif led_path == "none":
        led_path = None
    host, port = address(args.listen)
    try:
        server = socket.create_server((host, port))
    except OSError as error:
        sys.exit(f"cannot listen on {host}:{port}: {error}. Is diagd already running?")

    daemon = Daemon(
        stream,
        poweroff=(lambda: say("power: simulated shutdown; this computer stays on"))
        if args.sim
        else schedule_poweroff,
        led=Led(led_path),
    )
    say(f"diagd: {stream.where}; clients on {host}:{port}. Ctrl-C to stop.")
    if host not in ("127.0.0.1", "localhost", "::1"):
        say("diagd: open to the network: anyone who can reach it can drive the motors")
    if led_path:
        say(f"diagd: health on {led_path}")
    for loop in (daemon.read_loop, daemon.timer_loop, daemon.health_loop):
        threading.Thread(target=loop, daemon=True).start()
    threading.Thread(target=daemon.accept_loop, args=(server,), daemon=True).start()
    # stop_diagd's SIGTERM ends it the way Ctrl-C does, motors stopped first.
    signal.signal(signal.SIGTERM, interrupt)
    lost = False
    try:
        while daemon.running:
            time.sleep(0.2)
        lost = True
    except KeyboardInterrupt:
        pass
    try:
        daemon.stop("diagd is stopping")
        time.sleep(0.05)
    except OSError:
        pass
    daemon.running = False
    daemon.led.release()
    server.close()
    sys.exit("diagd: the link to the controller failed" if lost else 0)


if __name__ == "__main__":
    main()
