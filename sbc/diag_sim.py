# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""A controller board running firmware/diag, in software, with motors behind it.

    python diagd.py --sim                        the daemon against this
    python diagd.py --sim --sim-motors "A:1,2 C:5"
    python diagd.py --sim --sim-faults imu-dead  an IMU that never reports

What it is for: running diagd.py, diag_client.py and bench/motor_gui.py end to
end on any computer, with nothing plugged in. It speaks the controller's half of
docs/DIAGNOSTICS.md over a socket, and behind it each CAN bus carries
simulated DM-J3507-2EC motors that answer the way bench/damiao.py says the real
ones do: register reads, writes and saves, the status request, enable, disable,
set zero and clear error sent to any mode's frame ID, and all four control
modes, each answered with a feedback frame. An IMU on it answers SH-2's Set
Feature, Get Feature, product ID and reset, and reports a robot standing still
and level. As the firmware does, it asks for the IMU's default reports when it
finds it and after every reset, and judges its own health and sends it in
HEALTH the way firmware/diag/src/health.rs does.

Faults it can be given, at the start or with Controller.set_fault: imu-dead, an
IMU that is found and answers its product ID but takes no Set Feature and sends
no report, as the robot's has after some power-ons; imu-missing; ina-missing;
and bus-off, bus C seen in bus-off.

It is a model, and a coarse one: a motor is an inertia with some friction, a
mode is a loop with round numbers in it, and nothing here was measured. What it
proves is that the plumbing carries what it should, not how a motor behaves.
"""

from __future__ import annotations

import math
import random
import socket
import struct
import threading
import time
from dataclasses import dataclass, field

import diag_link as dl

# ---- the motor ---------------------------------------------------------------

MIT, POS_VEL, VELOCITY, HYBRID = 1, 2, 3, 4
ENABLE, DISABLE, SET_ZERO, CLEAR_ERROR = 0xFC, 0xFD, 0xFE, 0xFB
REG_READ, REG_WRITE, REG_SAVE, STATUS_REQUEST = 0x33, 0x55, 0xAA, 0xCC
CONFIG_ID = 0x7FF
KP_MAX, KD_MAX = 500.0, 5.0
PEAK_NM = 3.0

# Registers that hold integers; every other is a float.
INTEGER_REGISTERS = {0x07, 0x08, 0x09, 0x0A, 0x0D, 0x0E, 0x0F, 0x10, 0x23, 0x24}
READ_ONLY = {0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x24}
READ_ONLY |= set(range(0x32, 0x38)) | {0x50, 0x51}


def default_registers(can_id: int) -> dict[int, float | int]:
    return {
        0x00: 15.0, 0x01: 0.0717, 0x02: 120.0, 0x03: 0.95, 0x04: 30.0,
        0x05: -30.0, 0x06: 300.0, 0x07: can_id + 0x10, 0x08: can_id, 0x09: 0,
        0x0A: MIT, 0x0B: 0.0, 0x0C: 0.0, 0x0D: 0, 0x0E: 5013, 0x0F: 0,
        0x10: 14, 0x11: 0.95, 0x12: 0.00042, 0x13: 0.0045, 0x14: 7.0,
        0x15: 12.5, 0x16: 50.0, 0x17: 5.0, 0x18: 1000.0, 0x19: 0.003,
        0x1A: 0.002, 0x1B: 30.0, 0x1C: 0.0, 0x1D: 32.0, 0x1E: 1.0,
        0x1F: 4.0, 0x20: 100.0, 0x21: 1000.0, 0x22: 1000.0, 0x23: 4,
        0x24: 1, 0x32: 0.0, 0x33: 0.0, 0x34: 0.0, 0x35: 0.0, 0x36: 0.0,
        0x37: 1.0, 0x50: 0.0, 0x51: 0.0,
    }  # fmt: skip


def to_uint(x: float, lo: float, hi: float, bits: int) -> int:
    x = min(max(x, lo), hi)
    return int((x - lo) * ((1 << bits) - 1) / (hi - lo))


def to_float(u: int, lo: float, hi: float, bits: int) -> float:
    return u * (hi - lo) / ((1 << bits) - 1) + lo


@dataclass
class Motor:
    can_id: int
    registers: dict = field(default_factory=dict)
    saved: dict = field(default_factory=dict)
    enabled: bool = False
    fault: int = 0
    pos: float = 0.0
    vel: float = 0.0
    torque: float = 0.0
    command: tuple = ()
    # The output's inertia with a skate wheel on it, kg m^2, and its friction.
    inertia: float = 0.0015
    viscous: float = 0.01
    coulomb: float = 0.015

    def __post_init__(self):
        if not self.registers:
            self.registers = default_registers(self.can_id)
        self.saved = dict(self.registers)
        self.pos = random.uniform(-0.5, 0.5)

    @property
    def esc_id(self) -> int:
        return int(self.registers[0x08])

    @property
    def master_id(self) -> int:
        return int(self.registers[0x07])

    @property
    def mode(self) -> int:
        return int(self.registers[0x0A])

    def range(self, rid: int) -> float:
        return float(self.registers[rid])

    def state(self) -> int:
        return self.fault or (1 if self.enabled else 0)

    def feedback(self) -> bytes:
        pmax, vmax, tmax = self.range(0x15), self.range(0x16), self.range(0x17)
        p = to_uint(self.pos, -pmax, pmax, 16)
        v = to_uint(self.vel, -vmax, vmax, 12)
        t = to_uint(self.torque, -tmax, tmax, 12)
        hot = abs(self.torque)
        return bytes(
            [
                self.state() << 4 | (self.esc_id & 0x0F),
                p >> 8,
                p & 0xFF,
                v >> 4,
                (v & 0xF) << 4 | t >> 8,
                t & 0xFF,
                int(32 + 4 * hot),
                int(31 + 6 * hot),
            ]
        )

    def register_bytes(self, rid: int) -> bytes:
        value = self.registers[rid]
        if rid in INTEGER_REGISTERS:
            return int(value).to_bytes(4, "little")
        return struct.pack("<f", float(value))

    def step(self, dt: float) -> None:
        """One step of a model with round numbers in it: each mode closes its
        loop as a spring and a damper on the output."""
        tau = 0.0
        if self.enabled and self.command:
            mode, c = self.mode, self.command
            if mode == MIT:
                p, v, kp, kd, t = c
                tau = kp * (p - self.pos) + kd * (v - self.vel) + t
                tau = max(-self.range(0x17), min(self.range(0x17), tau))
            elif mode in (POS_VEL, HYBRID):
                p, vlim = c[0], c[1]
                want = max(-vlim, min(vlim, 8.0 * (p - self.pos)))
                tau = self.inertia * (want - self.vel) / 0.02 + self.drag(want)
                limit = PEAK_NM if mode == POS_VEL else c[2] * self.range(0x17)
                tau = max(-limit, min(limit, tau))
            elif mode == VELOCITY:
                cap = self.range(0x06) / self.range(0x14)
                want = max(-cap, min(cap, c[0]))
                tau = self.inertia * (want - self.vel) / 0.03 + self.drag(want)
            tau = max(-PEAK_NM, min(PEAK_NM, tau))
        friction = self.viscous * self.vel + math.copysign(self.coulomb, self.vel)
        if not self.enabled and abs(self.vel) < 0.05:
            friction, self.vel = 0.0, 0.0
        self.vel += (tau - friction) / self.inertia * dt
        self.pos += self.vel * dt
        pmax = self.range(0x15)
        # The position reading wraps round at the ends of its range.
        if abs(self.pos) > pmax:
            self.pos = (self.pos + pmax) % (2 * pmax) - pmax
        self.torque = tau

    def drag(self, speed: float) -> float:
        """The friction at a speed, which a speed loop's integral learns to
        push against; the model's loops are given it outright."""
        return self.viscous * speed + math.copysign(self.coulomb, speed) * (speed != 0)

    def take(self, can_id: int, data: bytes) -> bytes | None:
        """A frame addressed to this motor, and the frame it answers with."""
        if can_id == CONFIG_ID:
            return self.configure(data)
        if data[:7] == b"\xff" * 7 and len(data) == 8:
            code = data[7]
            if code == ENABLE and not self.fault:
                self.enabled, self.command = True, ()
            elif code == DISABLE:
                self.enabled, self.command = False, ()
            elif code == SET_ZERO:
                self.pos = 0.0
                if self.command and self.mode != VELOCITY:
                    self.command = (0.0, *self.command[1:])
            elif code == CLEAR_ERROR:
                self.fault = 0
            return self.feedback()
        # Whatever frame ID it came on, it is a command in the motor's mode.
        mode = self.mode
        if mode == MIT and len(data) == 8:
            pmax, vmax, tmax = self.range(0x15), self.range(0x16), self.range(0x17)
            p = to_float(data[0] << 8 | data[1], -pmax, pmax, 16)
            v = to_float(data[2] << 4 | data[3] >> 4, -vmax, vmax, 12)
            kp = to_float((data[3] & 0xF) << 8 | data[4], 0, KP_MAX, 12)
            kd = to_float(data[5] << 4 | data[6] >> 4, 0, KD_MAX, 12)
            t = to_float((data[6] & 0xF) << 8 | data[7], -tmax, tmax, 12)
            self.command = (p, v, kp, kd, t)
        elif mode == POS_VEL and len(data) == 8:
            self.command = struct.unpack("<ff", data)
        elif mode == VELOCITY and len(data) >= 4:
            self.command = struct.unpack("<f", data[:4])
        elif mode == HYBRID and len(data) == 8:
            p, v16, i16 = struct.unpack("<fHH", data)
            self.command = (p, v16 / 100, i16 / 10000)
        return self.feedback()

    def configure(self, data: bytes) -> bytes | None:
        op, rid = data[2], data[3]
        head = bytes([data[0], data[1], op, rid])
        if op == STATUS_REQUEST:
            return self.feedback()
        if op == REG_READ and rid in self.registers:
            return head + self.register_bytes(rid)
        if op == REG_WRITE and rid in self.registers and rid not in READ_ONLY:
            raw = data[4:8]
            if rid in INTEGER_REGISTERS:
                self.registers[rid] = int.from_bytes(raw, "little")
            else:
                self.registers[rid] = struct.unpack("<f", raw)[0]
            return head + self.register_bytes(rid)
        if op == REG_SAVE and not self.enabled:
            self.saved = dict(self.registers)
            return head + bytes(4)
        return None


# ---- the IMU -----------------------------------------------------------------


class Imu:
    """A BNO085 standing level and still, as far as SHTP goes."""

    REPORTS = {
        0x01: ("<3h", 8, lambda: (0.0, 0.0, 9.81)),
        0x02: ("<3h", 9, lambda: (0.0, 0.0, 0.0)),
        0x03: ("<3h", 4, lambda: (21.0, 0.5, -38.0)),
        0x04: ("<3h", 8, lambda: (0.0, 0.0, 0.0)),
        0x05: ("<5h", 14, lambda: (0.0, 0.0, 0.0, 1.0, 0.1)),
        0x06: ("<3h", 8, lambda: (0.0, 0.0, 9.81)),
        0x08: ("<4h", 14, lambda: (0.0, 0.0, 0.0, 1.0)),
    }

    def __init__(self):
        self.intervals: dict[int, float] = {}
        self.due: dict[int, float] = {}
        self.seq = [0] * 6
        self.report_seq: dict[int, int] = {}
        self.outbox: list[bytes] = []
        # Found and answering, but taking no Set Feature and reporting nothing.
        self.dead = False

    def packet(self, channel: int, payload: bytes) -> bytes:
        header = struct.pack("<HBB", len(payload) + 4, channel, self.seq[channel])
        self.seq[channel] = (self.seq[channel] + 1) & 0xFF
        return header + payload

    def write(self, packet: bytes) -> None:
        if len(packet) < 5:
            return
        channel, payload = packet[2], packet[4:]
        if channel == 1 and payload[:1] == b"\x01":
            self.intervals.clear()
            self.outbox.append(self.packet(1, b"\x01"))
        elif channel == 2 and payload[:1] == b"\xfe" and len(payload) >= 2:
            report = payload[1]
            interval = round(self.intervals.get(report, 0) * 1e6)
            self.outbox.append(
                self.packet(
                    2, struct.pack("<BBBHIII", 0xFC, report, 0, 0, interval, 0, 0)
                )
            )
        elif self.dead:
            if channel == 2 and payload[:1] == b"\xf9":
                body = struct.pack("<BBBBIIH2x", 0xF8, 0, 3, 2, 10004148, 6, 13)
                self.outbox.append(self.packet(2, body))
        elif channel == 2 and payload[:1] == b"\xfd" and len(payload) >= 9:
            report = payload[1]
            interval = struct.unpack_from("<I", payload, 5)[0]
            if report in self.REPORTS and interval:
                # A real hub grants the nearest rate it can; this one, 400 Hz at most.
                interval = max(interval, 2500)
                self.intervals[report] = interval / 1e6
                self.due[report] = time.monotonic()
            else:
                self.intervals.pop(report, None)
                interval = 0
            self.outbox.append(
                self.packet(
                    2, struct.pack("<BBBHIII", 0xFC, report, 0, 0, interval, 0, 0)
                )
            )
        elif channel == 2 and payload[:1] == b"\xf9":
            body = struct.pack("<BBBBIIH2x", 0xF8, 0, 3, 7, 10003606, 450, 11)
            self.outbox.append(self.packet(2, body))

    def poll(self, now: float) -> list[bytes]:
        out, self.outbox = self.outbox, []
        records = b""
        for report, interval in self.intervals.items():
            if now < self.due[report]:
                continue
            self.due[report] += interval
            if now - self.due[report] > 0.1:
                self.due[report] = now + interval
            fmt, q, values = self.REPORTS[report]
            noisy = [v + random.gauss(0, 0.002) for v in values()]
            raw = [max(-32768, min(32767, round(v * (1 << q)))) for v in noisy]
            if report == 0x05:
                raw[4] = round(values()[4] * (1 << 12))
            seq = self.report_seq.get(report, 0)
            self.report_seq[report] = (seq + 1) & 0xFF
            records += bytes([report, seq, 3, 0]) + struct.pack(fmt, *raw)
        if records:
            out.append(self.packet(3, b"\xfb" + bytes(4) + records))
        return out


# ---- the controller ----------------------------------------------------------

DEADMAN_S = 0.3
INA226 = 0x40
IMU_ADDRESS = 0x4A
# The firmware's quiet period after starting and after an IMU reset, and how
# often it looks again for a part it has not found.
QUIET_S, SEARCH_S = 0.3, 1.0
# What it asks the IMU for when it finds it: accel, gyro, gravity, game, 100 Hz.
DEFAULT_REPORTS, DEFAULT_INTERVAL_US = (0x01, 0x02, 0x06, 0x08), 10_000
FAULTS = ("imu-dead", "imu-missing", "ina-missing", "bus-off")


class Health:
    """firmware/diag/src/health.rs, in seconds of time.monotonic()."""

    GRACE_S, BUS_OFF_HOLD_S, FIRST_CONTACT_S = 3.0, 5.0, 30.0

    def __init__(self, now: float):
        self.started = now
        self.imu_missing_since: float | None = now
        self.imu_silent_since: float | None = None
        self.ina_missing_since: float | None = now
        self.bus_off_at: float | None = None

    def imu_found(self, now: float) -> None:
        self.imu_missing_since = None
        if self.imu_silent_since is None:
            self.imu_silent_since = now

    def imu_lost(self, now: float) -> None:
        if self.imu_missing_since is None:
            self.imu_missing_since = now

    def ina_lost(self, now: float) -> None:
        if self.ina_missing_since is None:
            self.ina_missing_since = now

    def flags(self, now: float, lost: bool, ever_heard: bool) -> int:
        def held(t: float | None) -> bool:
            return t is not None and now - t >= self.GRACE_S

        flags = 0
        if held(self.imu_missing_since):
            flags |= dl.IMU_MISSING
        if held(self.imu_silent_since):
            flags |= dl.IMU_SILENT
        if held(self.ina_missing_since):
            flags |= dl.INA_MISSING
        if self.bus_off_at is not None and now - self.bus_off_at < self.BUS_OFF_HOLD_S:
            flags |= dl.BUS_OFF
        if lost or (not ever_heard and now - self.started >= self.FIRST_CONTACT_S):
            flags |= dl.PI_SILENT
        return flags


class Controller:
    """firmware/diag's half of the link, over one end of a socket pair."""

    def __init__(self, sock: socket.socket, motors: dict[str, list[int]], faults=()):
        self.sock = sock
        self.t0 = time.monotonic()
        self.faults = {f for f in faults if f}
        if unknown := self.faults - set(FAULTS):
            raise ValueError(f"no fault {', '.join(sorted(unknown))}: {FAULTS}")
        self.health = Health(self.t0)
        self.health_flags = 0
        self.imu_found = self.ina_found = False
        self.search_at = self.t0 + QUIET_S
        self.buses = {name: [Motor(i) for i in ids] for name, ids in motors.items()}
        for name in dl.BUSES:
            self.buses.setdefault(name, [])
        self.counts = {name: dict.fromkeys(dl.BUS_COUNTS, 0) for name in dl.BUSES}
        self.tec = dict.fromkeys(dl.BUSES, 0)
        self.addressed = {name: set(range(1, 17)) for name in dl.BUSES}
        self.decoder = dl.Decoder()
        self.malformed = self.sent_dropped = 0
        self.imu = Imu()
        self.imu.dead = "imu-dead" in self.faults
        self.imu_packets = 0
        self.last_host: float | None = None
        self.lost = False
        self.off = False
        self.lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.running = True

    def t_us(self) -> int:
        return int((time.monotonic() - self.t0) * 1e6) & 0xFFFFFFFF

    def send(self, kind: int, body: bytes = b"") -> None:
        try:
            with self.write_lock:
                self.sock.sendall(dl.encode(kind, body))
        except OSError:
            self.running = False

    def log(self, text: str) -> None:
        self.send(dl.LOG, self.t_us().to_bytes(4, "little") + text.encode())

    def start(self) -> None:
        threading.Thread(target=self.listen, daemon=True, name="sim-in").start()
        threading.Thread(target=self.run, daemon=True, name="sim-run").start()

    def info(self) -> None:
        lines = [
            "firmware=diag-sim",
            f"protocol={dl.PROTOCOL}",
            "uid=simulated",
            "baud=1500000",
            "bitrate=1000000",
            "shutdown_led=1",
            "health=1",
            "buses=A FDCAN1 J2 hips,B FDCAN2 J3 knees,C FDCAN3 J4 wheels",
            f"deadman_ms={int(DEADMAN_S * 1000)}",
            # What a search finds, which the firmware has by the time diagd
            # is up to ask.
            "imu=none" if "imu-missing" in self.faults else f"imu=0x{IMU_ADDRESS:02X}",
            "ina226=none" if "ina-missing" in self.faults else f"ina226=0x{INA226:02X}",
            "reset=power-on",
            "last_crash=",
        ]
        self.send(dl.INFO, "\n".join(lines).encode() + b"\n")

    # -- from the Pi -------------------------------------------------------------

    def listen(self) -> None:
        while self.running:
            try:
                data = self.sock.recv(4096)
            except OSError:
                break
            if not data:
                break
            for kind, body in self.decoder.feed(data):
                with self.lock:
                    self.last_host = time.monotonic()
                    back, self.lost = self.lost, False
                if back:
                    self.log("link: the Pi is back")
                self.handle(kind, body)
        self.running = False

    def handle(self, kind: int, body: bytes) -> None:
        if kind == dl.HELLO:
            self.info()
        elif kind == dl.STOP:
            self.stop(0)
        elif kind == dl.SHUTDOWN and not body:
            self.off = True
            self.stop(0)
        elif kind == dl.CAN_SEND and 6 <= len(body) <= 14 and body[0] < 3:
            bus, flags, can_id = struct.unpack_from("<BBI", body)
            self.can_send(dl.BUSES[bus], can_id, body[6:], bool(flags & 1))
        elif kind == dl.IMU_WRITE:
            with self.lock:
                found = self.imu_found
                if found:
                    self.imu.write(body)
            if not found:
                self.log("imu: a write from the Pi dropped: no IMU has answered")
        elif kind == dl.I2C and len(body) >= 4:
            tag, address, read = struct.unpack_from("<BBH", body)
            self.i2c(tag, address, body[4:], read)
        elif kind != dl.PING:
            self.malformed += 1

    def can_send(self, bus: str, can_id: int, data: bytes, extended: bool) -> None:
        if extended or self.off:
            return
        motors = self.buses[bus]
        with self.lock:
            if not motors:
                # Nothing to acknowledge it: the controller retries it for 5 ms
                # and withdraws it, and the error counter climbs to passive.
                self.counts[bus]["tx_fail"] += 1
                self.tec[bus] = min(128, self.tec[bus] + 8)
                return
            self.counts[bus]["tx"] += 1
            target = data[0] if can_id == CONFIG_ID and data else can_id & 0xFF
            self.addressed[bus].add(target)
            replies = []
            for m in motors:
                if can_id == CONFIG_ID:
                    if len(data) >= 4 and (data[0] | data[1] << 8) == m.esc_id:
                        replies.append((m.master_id, m.take(can_id, data)))
                elif can_id & 0xFF == m.esc_id & 0xFF:
                    replies.append((m.master_id, m.take(can_id, data)))
        for master, reply in replies:
            if reply is not None:
                self.receive(bus, master, reply)

    def receive(self, bus: str, can_id: int, data: bytes) -> None:
        with self.lock:
            self.counts[bus]["rx"] += 1
        body = dl.can_recv(self.t_us(), dl.BUSES.index(bus), can_id, data)
        self.send(dl.CAN_RECV, body)

    def i2c(self, tag: int, address: int, write: bytes, read: int) -> None:
        if address != INA226 or not self.ina_found:
            self.send(dl.I2C_RESULT, bytes([tag, 1]))
            return
        registers = {0x00: 0x4127, 0x02: round(self.vbus() / 1.25e-3), 0xFE: 0x5449}
        registers[0xFF] = 0x2260
        value = registers.get(write[0] if write else 0x00, 0)
        data = value.to_bytes(2, "big")[:read] if read else b""
        self.send(dl.I2C_RESULT, bytes([tag, 0]) + data)

    def stop(self, why: int) -> None:
        with self.lock:
            stopped = [
                (bus, m)
                for bus, motors in self.buses.items()
                for m in motors
                if m.esc_id & 0xFF in self.addressed[bus]
            ]
            for _, m in stopped:
                m.enabled, m.command = False, ()
        self.send(dl.STOPPED, bytes([why]))
        for bus, m in stopped:
            self.receive(bus, m.master_id, m.feedback())

    # -- the controller's own work ----------------------------------------------

    def vbus(self) -> float:
        return 24.6 - 0.02 * math.sin(time.monotonic())

    def search(self, now: float) -> None:
        """What the firmware's search finds, and the IMU's default reports
        asked for as soon as it is found."""
        with self.lock:
            ina = not self.ina_found and "ina-missing" not in self.faults
            imu = not self.imu_found and "imu-missing" not in self.faults
            if ina:
                self.ina_found = True
                self.health.ina_missing_since = None
            if imu:
                self.imu_found = True
                self.health.imu_found(now)
                for report in DEFAULT_REPORTS:
                    feature = struct.pack(
                        "<BBBHIII", 0xFD, report, 0, 0, DEFAULT_INTERVAL_US, 0, 0
                    )
                    self.imu.write(struct.pack("<HBB", 21, 2, 0) + feature)
        if ina:
            self.log(f"i2c: INA226 at 0x{INA226:02X}")
        if imu:
            self.log(f"i2c: IMU at 0x{IMU_ADDRESS:02X}")
            self.log("imu: default reports requested at 100 Hz")

    def set_fault(self, fault: str, on: bool = True) -> None:
        """Gives the controller a fault, or takes it away. An IMU that stops
        being dead comes back as a module just powered on would, announcing a
        reset, and the controller asks for its reports again."""
        if fault not in FAULTS:
            raise ValueError(f"no fault {fault!r}: {FAULTS}")
        now = time.monotonic()
        with self.lock:
            (self.faults.add if on else self.faults.discard)(fault)
            if fault == "imu-missing" and on:
                self.imu_found = False
                self.health.imu_lost(now)
            elif fault == "ina-missing" and on:
                self.ina_found = False
                self.health.ina_lost(now)
            elif fault == "imu-dead":
                self.imu.dead = on
                if on:
                    self.imu.intervals.clear()
                else:
                    self.imu.write(struct.pack("<HBB", 5, 1, 0) + b"\x01")

    def judge(self, now: float) -> None:
        with self.lock:
            flags = self.health.flags(now, self.lost, self.last_host is not None)
            changed, self.health_flags = flags != self.health_flags, flags
        if changed:
            names = [name for bit, name in dl.HEALTH_NAMES.items() if flags & bit]
            self.log(f"health: {', '.join(names) or 'all clear'}")
            self.send(dl.HEALTH, dl.health(flags))

    def run(self) -> None:
        self.send(dl.STOPPED, bytes([3]))
        self.info()
        dt = 0.001
        next_step = next_status = next_health = next_judge = time.monotonic()
        while self.running:
            now = time.monotonic()
            if now >= self.search_at:
                self.search_at = now + SEARCH_S
                self.search(now)
            with self.lock:
                for motors in self.buses.values():
                    for m in motors:
                        m.step(dt)
                packets = self.imu.poll(now) if self.imu_found else []
                self.imu_packets += len(packets)
                for packet in packets:
                    if packet[2] in (3, 4, 5):
                        self.health.imu_silent_since = None
                    elif packet[2] == 1 and packet[4:5] == b"\x01":
                        # As the firmware does: look again after the quiet
                        # period, and ask for the defaults again then.
                        self.imu_found = False
                        self.health.imu_lost(now)
                        self.search_at = now + QUIET_S
                silent = (
                    not self.lost
                    and self.last_host is not None
                    and now - self.last_host > DEADMAN_S
                )
                self.lost |= silent
            if silent:
                self.log("link: nothing from the Pi for 300 ms; every motor stopped")
                self.stop(1)
            for packet in packets:
                self.send(dl.IMU_PACKET, self.t_us().to_bytes(4, "little") + packet)
            if now >= next_judge:
                next_judge += 0.02
                self.judge(now)
            if now >= next_status:
                next_status += 0.1
                self.send(dl.STATUS, self.status())
            if now >= next_health:
                next_health += 1.0
                self.send(dl.HEALTH, dl.health(self.health_flags))
            next_step += dt
            time.sleep(max(0.0, next_step - time.monotonic()))

    def status(self) -> bytes:
        with self.lock:
            buses = {
                name: {
                    "state": "error passive"
                    if self.tec[name] >= 128
                    else "error active",
                    "tec": self.tec[name],
                    "rec": 0,
                    **self.counts[name],
                }
                for name in dl.BUSES
            }
            if "bus-off" in self.faults:
                buses["C"].update(state="bus off", tec=255)
                self.health.bus_off_at = time.monotonic()
            return dl.status(
                {
                    "t_us": self.t_us(),
                    "uptime": time.monotonic() - self.t0,
                    "hold": True,
                    "button": False,
                    "off": self.off,
                    "lost": self.lost,
                    "imu_found": self.imu_found,
                    "ina_found": self.ina_found,
                    "vbus": self.vbus() if self.ina_found else None,
                    "link": {
                        "frames": self.decoder.frames,
                        "crc_errors": self.decoder.crc_errors,
                        "overruns": self.decoder.overruns,
                        "uart_errors": 0,
                        "malformed": self.malformed,
                        "dropped": self.sent_dropped,
                    },
                    "imu": {"packets": self.imu_packets, "errors": 0},
                    "buses": buses,
                }
            )


def parse_motors(text: str) -> dict[str, list[int]]:
    """ "A:1,2 B:3,4" to {"A": [1, 2], "B": [3, 4]}."""
    out = {}
    for part in text.split():
        bus, _, ids = part.partition(":")
        if bus not in dl.BUSES:
            raise ValueError(f"no bus {bus!r}: A, B or C")
        out[bus] = [int(i, 0) for i in ids.split(",") if i]
    return out


DEFAULT_MOTORS = "A:1,2 B:3,4 C:5,6"


def simulate(
    motors: str = DEFAULT_MOTORS, faults=()
) -> tuple[socket.socket, Controller]:
    """A simulated controller, running: the Pi's end of its link, and it."""
    ours, theirs = socket.socketpair()
    controller = Controller(theirs, parse_motors(motors), faults)
    controller.start()
    return ours, controller


def start(motors: str = DEFAULT_MOTORS, faults=()) -> socket.socket:
    """A simulated controller, running; returns the Pi's end of its link."""
    return simulate(motors, faults)[0]
