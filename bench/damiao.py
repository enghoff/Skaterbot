"""DAMIAO joint motors, through DAMIAO's own USB-to-CAN debugger.

The debugger is a USB serial port to the PC (USB ID 2E88:4603, a CDC device, so
Windows needs no driver for it). Every CAN frame goes to it as a 30-byte record
and every frame it hears comes back as a 16-byte one. That framing is DAMIAO's,
from their Python example driver (DM_CAN.py), and was first confirmed against a
DM-J3507-2EC on 2026-10-20: it answered a register read at CAN ID 1.

The motor side is the DM-J3507-2EC manual V1.0 in reference/, pages 7 to 15:
the feedback frame, the four control frames, register read, write and save, and
the register list. Three things are not in that manual and come from DAMIAO's
later protocol notes and the same driver: the enable, disable, set-zero and
clear-error frames (seven 0xFF and a code, sent to the frame ID of the mode the
motor is in), and the status request (0xCC, sent to 0x7FF), which asks a motor
for a feedback frame without commanding it.

One property of the motor shapes everything here. It answers any frame whose
low eight ID bits are its own ID, so a frame meant for another mode's ID still
reaches it, and is read as a command in the mode it is in. Control frames are
therefore only ever sent for the mode the motor last reported.

Nothing in this module enables a motor on its own. Reading and scanning use
register reads and status requests only.
"""

from __future__ import annotations

import struct
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import serial
from serial.tools import list_ports

ADAPTER_VID, ADAPTER_PID = 0x2E88, 0x4603
ADAPTER_BAUD = 921600

# Control modes, and the offset each adds to the motor's CAN ID for its frames.
MIT, POS_VEL, VELOCITY, HYBRID = 1, 2, 3, 4
MODE_NAMES = {
    MIT: "MIT",
    POS_VEL: "Position-velocity",
    VELOCITY: "Velocity",
    HYBRID: "Force-position",
}
MODE_OFFSET = {MIT: 0x000, POS_VEL: 0x100, VELOCITY: 0x200, HYBRID: 0x300}

# The state nibble of every feedback frame.
STATES = {
    0x0: "disabled",
    0x1: "enabled",
    0x8: "overvoltage",
    0x9: "undervoltage",
    0xA: "overcurrent",
    0xB: "MOSFET over-temperature",
    0xC: "winding over-temperature",
    0xD: "communication lost",
    0xE: "overload",
}

# MIT-mode gain ranges, fixed by the protocol (manual p.9).
KP_MAX, KD_MAX = 500.0, 5.0

ENABLE, DISABLE, SET_ZERO, CLEAR_ERROR = 0xFC, 0xFD, 0xFE, 0xFB
REG_READ, REG_WRITE, REG_SAVE, STATUS = 0x33, 0x55, 0xAA, 0xCC
CONFIG_ID = 0x7FF


@dataclass(frozen=True)
class Register:
    rid: int
    name: str
    kind: str  # "f" float32, "u" uint32
    writable: bool
    span: str
    text: str


# The manual's appendix, "Register list and ranges" (p.14-15). Its table prints
# ESC_ID at 0x0A, beside CTRL_MODE, but numbers it 8 in decimal; 0x08 is the
# address the motor answers to.
REGISTERS = [
    Register(0x00, "UV_Value", "f", True, "(10.0, fmax]", "Undervoltage trip, V"),
    Register(0x01, "KT_Value", "f", True, "[0.0, fmax]", "Torque constant"),
    Register(0x02, "OT_Value", "f", True, "[80.0, 200)", "Over-temperature trip, °C"),
    Register(0x03, "OC_Value", "f", True, "(0.0, 1.0)", "Overcurrent trip, per unit"),
    Register(0x04, "ACC", "f", True, "(0.0, fmax)", "Acceleration"),
    Register(0x05, "DEC", "f", True, "[-fmax, 0.0)", "Deceleration"),
    Register(0x06, "MAX_SPD", "f", True, "(0.0, fmax]", "Speed limit, rotor rad/s"),
    Register(0x07, "MST_ID", "u", True, "[0, 0x7FF]", "Feedback ID (master ID)"),
    Register(0x08, "ESC_ID", "u", True, "[0, 0x7FF]", "Receive ID (the CAN ID)"),
    Register(0x09, "TIMEOUT", "u", True, "[0, 2^32-1]", "Communication-loss timeout"),
    Register(0x0A, "CTRL_MODE", "u", True, "[1, 4]", "Control mode"),
    Register(0x0B, "Damp", "f", False, "", "Viscous coefficient"),
    Register(0x0C, "Inertia", "f", False, "", "Rotor inertia"),
    Register(0x0D, "hw_ver", "u", False, "", "Hardware version (reserved)"),
    Register(0x0E, "sw_ver", "u", False, "", "Software version"),
    Register(0x0F, "SN", "u", False, "", "Serial number (reserved)"),
    Register(0x10, "NPP", "u", False, "", "Pole pairs"),
    Register(0x11, "Rs", "f", False, "", "Phase resistance, Ω"),
    Register(0x12, "Ls", "f", False, "", "Phase inductance, H"),
    Register(0x13, "Flux", "f", False, "", "Flux linkage"),
    Register(0x14, "Gr", "f", False, "", "Gear ratio"),
    Register(0x15, "PMAX", "f", True, "(0.0, fmax]", "Position mapping range, rad"),
    Register(0x16, "VMAX", "f", True, "(0.0, fmax]", "Speed mapping range, rad/s"),
    Register(0x17, "TMAX", "f", True, "(0.0, fmax]", "Torque mapping range, Nm"),
    Register(0x18, "I_BW", "f", True, "[100.0, 1.0e4]", "Current loop bandwidth"),
    Register(0x19, "KP_ASR", "f", True, "[0.0, fmax]", "Speed loop Kp"),
    Register(0x1A, "KI_ASR", "f", True, "[0.0, fmax]", "Speed loop Ki"),
    Register(0x1B, "KP_APR", "f", True, "[0.0, fmax]", "Position loop Kp"),
    Register(0x1C, "KI_APR", "f", True, "[0.0, fmax]", "Position loop Ki"),
    Register(0x1D, "OV_Value", "f", True, "TBD", "Overvoltage trip, V"),
    Register(0x1E, "GREF", "f", True, "(0.0, 1.0]", "Gear torque efficiency"),
    Register(0x1F, "Deta", "f", True, "[1.0, 30.0]", "Speed loop damping"),
    Register(0x20, "V_BW", "f", True, "(0.0, 500.0)", "Speed loop filter bandwidth"),
    Register(0x21, "IQ_c1", "f", True, "[100.0, 1.0e4]", "Current loop boost"),
    Register(0x22, "VL_c1", "f", True, "(0.0, 1.0e4]", "Speed loop boost"),
    Register(0x23, "can_br", "u", True, "[0, 9]", "CAN bit rate code (4 = 1M)"),
    Register(0x24, "sub_ver", "u", False, "", "Sub-version"),
    Register(0x32, "u_off", "f", False, "", "U-phase offset"),
    Register(0x33, "v_off", "f", False, "", "V-phase offset"),
    Register(0x34, "k1", "f", False, "", "Calibration k1"),
    Register(0x35, "k2", "f", False, "", "Calibration k2"),
    Register(0x36, "m_off", "f", False, "", "Calibration m_off"),
    Register(0x37, "dir", "f", False, "", "Calibration direction"),
    Register(0x50, "p_m", "f", False, "", "Position, read before a position mode"),
    Register(0x51, "xout", "f", False, "", "xout"),
]
REGISTER = {r.rid: r for r in REGISTERS}
RID = {r.name: r.rid for r in REGISTERS}


def list_adapters() -> list[tuple[str, str, bool]]:
    """Every serial port as (device, description, is_damiao_debugger)."""
    ports = []
    for p in list_ports.comports():
        ours = p.vid == ADAPTER_VID and p.pid == ADAPTER_PID
        ports.append((p.device, p.description, ours))
    return sorted(ports, key=lambda p: (not p[2], p[0]))


def to_uint(x: float, lo: float, hi: float, bits: int) -> int:
    x = min(max(x, lo), hi)
    return int((x - lo) * ((1 << bits) - 1) / (hi - lo))


def to_float(u: int, lo: float, hi: float, bits: int) -> float:
    return u * (hi - lo) / ((1 << bits) - 1) + lo


@dataclass
class Feedback:
    t: float
    state: int
    pos: float
    vel: float
    torque: float
    t_mos: int
    t_rotor: int

    @property
    def state_name(self) -> str:
        return STATES.get(self.state, f"state {self.state:X}")

    @property
    def enabled(self) -> bool:
        return self.state == 0x1

    @property
    def fault(self) -> bool:
        return self.state >= 0x8


@dataclass
class Motor:
    """What the bus knows of one motor: its IDs, its mode and its mapping ranges."""

    can_id: int
    master_id: int = 0
    mode: int = MIT
    pmax: float = 12.566
    vmax: float = 50.0
    tmax: float = 5.0
    registers: dict[int, float | int] = field(default_factory=dict)
    feedback: Feedback | None = None
    history: deque = field(default_factory=lambda: deque(maxlen=4000))

    @property
    def speed_cap(self) -> float | None:
        """The output speed MAX_SPD holds the motor to, in rad/s, if it is known.

        MAX_SPD is at the rotor, so the output's limit is it over the gear ratio.
        Measured 2026-10-20 in velocity mode: at MAX_SPD 300 and Gr 7, asked for
        50 rad/s, the motor held 42.7 against the 42.9 this gives; at 450 it
        followed to 48.
        """
        spd, gr = self.registers.get(RID["MAX_SPD"]), self.registers.get(RID["Gr"])
        return spd / gr if spd and gr else None

    def decode(self, d: bytes, t: float) -> Feedback:
        # Speed is packed against VMAX, and past it wraps round rather than
        # stopping: on 2026-10-20 a motor commanded to 52 rad/s, having followed
        # 48 exactly, read -48 with VMAX at 50.
        p = d[1] << 8 | d[2]
        v = d[3] << 4 | d[4] >> 4
        q = (d[4] & 0xF) << 8 | d[5]
        return Feedback(
            t,
            d[0] >> 4,
            to_float(p, -self.pmax, self.pmax, 16),
            to_float(v, -self.vmax, self.vmax, 12),
            to_float(q, -self.tmax, self.tmax, 12),
            d[6],
            d[7],
        )


class _Pending:
    __slots__ = ("event", "data")

    def __init__(self):
        self.event = threading.Event()
        self.data: bytes | None = None


class Bus:
    """One debugger, and the motors found behind it."""

    def __init__(self, port: str):
        self.port = port
        self._serial = serial.Serial(port, ADAPTER_BAUD, timeout=0.02)
        self._write_lock = threading.Lock()
        self._pending: dict[tuple[int, int, int], _Pending] = {}
        self._pending_lock = threading.Lock()
        self.history_lock = threading.Lock()
        self.motors: dict[int, Motor] = {}
        self.tx = self.rx = self.unmatched = self.foreign = self.late = 0
        self.error: str | None = None
        self._running = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    # -- the debugger's framing ------------------------------------------------

    def send(self, can_id: int, data: bytes | list[int]) -> None:
        data = bytes(data).ljust(8, b"\0")
        record = bytearray(30)
        record[0:4] = b"\x55\xaa\x1e\x03"  # header, record length, "send"
        record[4:8] = (1).to_bytes(4, "little")  # send once
        record[8:12] = (10).to_bytes(4, "little")  # interval
        record[12] = 0  # standard 11-bit ID
        record[13:17] = can_id.to_bytes(4, "little")
        record[17] = 0  # data frame
        record[18] = 8  # length
        record[21:29] = data
        with self._write_lock:
            self._serial.write(record)
        self.tx += 1

    def _read_loop(self) -> None:
        buf = bytearray()
        while self._running:
            try:
                buf += self._serial.read(self._serial.in_waiting or 1)
            except (serial.SerialException, OSError) as e:
                self.error = f"debugger lost: {e}"
                self._running = False
                break
            while len(buf) >= 16:
                if buf[0] != 0xAA or buf[15] != 0x55:
                    del buf[0]
                    continue
                packet = bytes(buf[:16])
                del buf[:16]
                if packet[1] == 0x11:
                    self._dispatch(int.from_bytes(packet[3:7], "little"), packet[7:15])
                else:
                    self.foreign += 1

    def _dispatch(self, can_id: int, d: bytes) -> None:
        self.rx += 1
        if d[2] in (REG_READ, REG_WRITE, REG_SAVE):
            key = (d[0] | d[1] << 8, d[2], d[3])
            with self._pending_lock:
                pending = self._pending.pop(key, None)
            if pending:
                pending.data = d
                pending.event.set()
                return
            if key[0] in self.motors:
                # A reply that arrived after its read gave up. Feedback can look
                # the same, about one frame in twenty thousand; losing that one
                # beats plotting a reply as a position.
                self.late += 1
                return
        motor = self._motor_for_feedback(can_id, d[0] & 0x0F)
        if motor is None:
            self.unmatched += 1
            return
        fb = motor.decode(d, time.monotonic())
        motor.feedback = fb
        with self.history_lock:
            motor.history.append(fb)

    def _motor_for_feedback(self, can_id: int, nibble: int) -> Motor | None:
        if can_id:
            hits = [m for m in self.motors.values() if m.master_id == can_id]
            if len(hits) == 1:
                return hits[0]
        hits = [m for m in self.motors.values() if m.can_id & 0x0F == nibble]
        return hits[0] if len(hits) == 1 else None

    def close(self) -> None:
        self._running = False
        self._reader.join(timeout=1)
        self._serial.close()

    # -- registers -------------------------------------------------------------

    def _request(self, can_id, op, rid, payload=b"\0\0\0\0", timeout=0.05):
        key = (can_id, op, rid)
        pending = _Pending()
        with self._pending_lock:
            self._pending[key] = pending
        self.send(CONFIG_ID, bytes([can_id & 0xFF, can_id >> 8, op, rid]) + payload)
        if pending.event.wait(timeout):
            return pending.data
        with self._pending_lock:
            self._pending.pop(key, None)
        return None

    def read(self, can_id: int, rid: int, timeout=0.05, tries=2):
        """A register's value, or None if the motor did not answer."""
        for _ in range(tries):
            d = self._request(can_id, REG_READ, rid, timeout=timeout)
            if d is not None:
                return self._unpack(rid, d[4:8])
        return None

    def write(self, can_id: int, rid: int, value, timeout=0.1):
        """Write a register (in RAM only) and return the value echoed, or None."""
        reg = REGISTER[rid]
        payload = (
            struct.pack("<f", float(value))
            if reg.kind == "f"
            else int(value).to_bytes(4, "little")
        )
        d = self._request(can_id, REG_WRITE, rid, payload, timeout=timeout)
        return None if d is None else self._unpack(rid, d[4:8])

    def save(self, can_id: int, timeout=0.3) -> bool:
        """Store every register to flash. The motor only does it while disabled."""
        return self._request(can_id, REG_SAVE, 0x01, timeout=timeout) is not None

    @staticmethod
    def _unpack(rid: int, raw: bytes):
        reg = REGISTER.get(rid)
        if reg and reg.kind == "f":
            return struct.unpack("<f", raw)[0]
        return int.from_bytes(raw, "little")

    def probe(self, can_id: int, timeout=0.03) -> Motor | None:
        """The motor at a CAN ID, with its IDs, mode and ranges read, or None."""
        if self.read(can_id, RID["ESC_ID"], timeout=timeout, tries=1) is None:
            return None
        m = Motor(can_id)
        for name in ("MST_ID", "CTRL_MODE", "PMAX", "VMAX", "TMAX", "MAX_SPD", "Gr"):
            v = self.read(can_id, RID[name])
            if v is not None:
                m.registers[RID[name]] = v
        m.master_id = int(m.registers.get(RID["MST_ID"], 0))
        m.mode = int(m.registers.get(RID["CTRL_MODE"], MIT))
        m.pmax = float(m.registers.get(RID["PMAX"], m.pmax))
        m.vmax = float(m.registers.get(RID["VMAX"], m.vmax))
        m.tmax = float(m.registers.get(RID["TMAX"], m.tmax))
        self.motors[can_id] = m
        return m

    def scan(self, ids=range(1, 17)) -> list[Motor]:
        found = [m for i in ids if (m := self.probe(i)) is not None]
        here = {m.can_id for m in found}
        for i in [i for i in self.motors if i in ids and i not in here]:
            del self.motors[i]
        return found

    # -- commands --------------------------------------------------------------

    def _special(self, m: Motor, code: int) -> None:
        self.send(m.can_id + MODE_OFFSET[m.mode], b"\xff" * 7 + bytes([code]))

    def enable(self, m: Motor) -> None:
        self._special(m, ENABLE)

    def disable(self, m: Motor) -> None:
        self._special(m, DISABLE)

    def set_zero(self, m: Motor) -> None:
        self._special(m, SET_ZERO)

    def clear_error(self, m: Motor) -> None:
        self._special(m, CLEAR_ERROR)

    def request_status(self, m: Motor) -> None:
        self.send(CONFIG_ID, [m.can_id & 0xFF, m.can_id >> 8, STATUS, 0, 0, 0, 0, 0])

    def mit(self, m: Motor, p: float, v: float, kp: float, kd: float, t: float):
        assert m.mode == MIT
        p16 = to_uint(p, -m.pmax, m.pmax, 16)
        v12 = to_uint(v, -m.vmax, m.vmax, 12)
        kp12 = to_uint(kp, 0.0, KP_MAX, 12)
        kd12 = to_uint(kd, 0.0, KD_MAX, 12)
        t12 = to_uint(t, -m.tmax, m.tmax, 12)
        self.send(
            m.can_id,
            [
                p16 >> 8,
                p16 & 0xFF,
                v12 >> 4,
                (v12 & 0xF) << 4 | kp12 >> 8,
                kp12 & 0xFF,
                kd12 >> 4,
                (kd12 & 0xF) << 4 | t12 >> 8,
                t12 & 0xFF,
            ],
        )

    def pos_vel(self, m: Motor, p: float, v: float) -> None:
        assert m.mode == POS_VEL
        self.send(m.can_id + 0x100, struct.pack("<ff", p, v))

    def velocity(self, m: Motor, v: float) -> None:
        assert m.mode == VELOCITY
        self.send(m.can_id + 0x200, struct.pack("<f", v))

    def hybrid(self, m: Motor, p: float, v: float, i: float) -> None:
        """Position p, speed limit v (0-100 rad/s), current limit i (0-1 per unit)."""
        assert m.mode == HYBRID
        v16 = int(min(max(v, 0.0), 100.0) * 100)
        i16 = int(min(max(i, 0.0), 1.0) * 10000)
        self.send(m.can_id + 0x300, struct.pack("<fHH", p, v16, i16))

    def disable_everything(self, repeat: int = 3) -> None:
        """Disable every known motor, on every mode's frame ID, a few times over."""
        for _ in range(repeat):
            for m in list(self.motors.values()):
                for offset in MODE_OFFSET.values():
                    self.send(m.can_id + offset, b"\xff" * 7 + bytes([DISABLE]))
            time.sleep(0.002)
