# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""The diagnostics link's framing and messages: firmware/diag_link in Python.

    python3 diag_link.py        check it against the bytes firmware/diag_link holds

docs/DIAGNOSTICS.md is the specification. A message is a type byte and a body;
on the wire it is followed by a CRC-16/CCITT-FALSE of the two, little-endian,
the whole COBS-encoded and ended with a zero byte. diagd.py speaks it to the
controller, and diag_sim.py speaks it back as the controller would.

Only the standard library, so that it runs on the Pi as it stands.
"""

from __future__ import annotations

import binascii
import struct
import sys

# The Pi's messages to the controller.
HELLO, PING, STOP, SHUTDOWN = 0x01, 0x02, 0x03, 0x04
CAN_SEND, IMU_WRITE, I2C = 0x10, 0x20, 0x21
# The controller's messages to the Pi.
INFO, STATUS, STOPPED = 0x81, 0x82, 0x83
CAN_RECV, IMU_PACKET, I2C_RESULT, LOG = 0x90, 0xA0, 0xA1, 0xE0
IMU_DIAG = 0xA2

IMU_DIAG_FIELDS = (
    "version",
    "header_reads",
    "empty_reads",
    "header_errors",
    "payload_errors",
    "write_errors",
    "nack",
    "timeouts",
    "bus_errors",
    "arbitration",
    "other_errors",
    "invalid_lengths",
    "resets",
    "input_packets",
    "last_input_ms",
    "ina_errors",
    "searches",
    "max_i2c_us",
    "max_service_gap_us",
    "last_header",
    "last_error_ms",
    "pins",
    "isr",
)


def parse_imu_diag(body: bytes) -> dict:
    if len(body) < 4:
        raise ValueError("unexpected IMU diagnostic packet size")
    version = struct.unpack_from("<I", body)[0]
    if version not in (1, 2):
        raise ValueError("unsupported IMU diagnostic version")
    fields = IMU_DIAG_FIELDS + (("host_resets",) if version == 2 else ())
    if len(body) != 4 * len(fields):
        raise ValueError("unexpected IMU diagnostic packet size")
    return dict(zip(fields, struct.unpack(f"<{len(fields)}I", body)))


PROTOCOL = 1
MAX_MESSAGE = 600
MAX_IMU_PACKET = 512
MAX_WIRE = MAX_MESSAGE + 2 + MAX_MESSAGE // 254 + 2

BUSES = "ABC"
STOP_REASONS = {0: "asked", 1: "silent", 2: "button", 3: "starting"}
I2C_STATUS = {0: "done", 1: "refused", 2: "timed out", 3: "failed"}
BUS_STATES = {0: "error active", 1: "error passive", 2: "bus off"}


def crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE, which is binascii's CRC-CCITT started at 0xFFFF."""
    return binascii.crc_hqx(data, 0xFFFF)


def cobs_encode(data: bytes) -> bytes:
    out = bytearray()
    # Each zero ends a run; the last run has none after it.
    for run in data.split(b"\0"):
        while len(run) >= 254:
            out.append(0xFF)
            out += run[:254]
            run = run[254:]
        out.append(len(run) + 1)
        out += run
    return bytes(out)


def cobs_decode(data: bytes) -> bytes | None:
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        code = data[i]
        if code == 0:
            return None
        i += 1
        if i + code - 1 > n:
            return None
        out += data[i : i + code - 1]
        i += code - 1
        if code != 0xFF and i < n:
            out.append(0)
    return bytes(out)


def encode(kind: int, body: bytes = b"") -> bytes:
    """One message as it goes on the wire, its ending zero included."""
    message = bytes([kind]) + body
    if len(message) > MAX_MESSAGE:
        raise ValueError(f"a message of {len(message)} bytes; {MAX_MESSAGE} at most")
    message += crc16(message).to_bytes(2, "little")
    return cobs_encode(message) + b"\0"


class Decoder:
    """Bytes off the wire in, messages out, with what went wrong counted."""

    def __init__(self):
        self.pending = bytearray()
        self.frames = self.crc_errors = self.overruns = 0

    def feed(self, data: bytes) -> list[tuple[int, bytes]]:
        out = []
        self.pending += data
        *whole, rest = bytes(self.pending).split(b"\0")
        self.pending = bytearray(rest)
        if len(self.pending) > MAX_WIRE:
            self.overruns += 1
            self.pending.clear()
        for wire in whole:
            if not wire:
                continue
            if len(wire) > MAX_WIRE:
                self.overruns += 1
                continue
            message = cobs_decode(wire)
            if (
                message is None
                or len(message) < 3
                or crc16(message[:-2]) != int.from_bytes(message[-2:], "little")
            ):
                self.crc_errors += 1
                continue
            self.frames += 1
            out.append((message[0], message[1:-2]))
        return out


# ---- the bodies --------------------------------------------------------------


def can_send(bus: int, can_id: int, data: bytes, extended: bool = False) -> bytes:
    return struct.pack("<BBI", bus, int(extended), can_id) + bytes(data)


CAN_HEAD = struct.Struct("<IBBI")  # time, bus, flags, id


def can_recv(t_us: int, bus: int, can_id: int, data: bytes, flags: int = 0) -> bytes:
    return CAN_HEAD.pack(t_us & 0xFFFFFFFF, bus, flags, can_id) + bytes(data)


def parse_can_recv(body: bytes) -> tuple[int, int, int, int, bytes]:
    """(time in µs, bus, flags, id, data)."""
    t, bus, flags, can_id = CAN_HEAD.unpack_from(body)
    return t, bus, flags, can_id, body[CAN_HEAD.size :]


def i2c_request(tag: int, address: int, write: bytes, read: int) -> bytes:
    return struct.pack("<BBH", tag, address, read) + bytes(write)


def parse_info(body: bytes) -> dict[str, str]:
    text = body.decode(errors="replace")
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


# STATUS: time, uptime, flags, battery; the link's six counters; the IMU's two;
# then each bus's state, error counters, a pad and six counters.
STATUS_HEAD = struct.Struct("<IIBH6I2I")
STATUS_BUS = struct.Struct("<4B6I")
STATUS_SIZE = STATUS_HEAD.size + 3 * STATUS_BUS.size
assert STATUS_SIZE == 127


def status(fields: dict) -> bytes:
    """The body of a STATUS, from the same names parse_status gives back; for
    diag_sim.py."""
    flags = sum(
        1 << bit
        for bit, name in enumerate(
            ("hold", "button", "off", "lost", "imu_found", "ina_found")
        )
        if fields[name]
    )
    link, imu = fields["link"], fields["imu"]
    body = STATUS_HEAD.pack(
        fields["t_us"] & 0xFFFFFFFF,
        int(fields["uptime"] * 1000) & 0xFFFFFFFF,
        flags,
        round((fields["vbus"] or 0) * 1000),
        *(link[k] for k in LINK_COUNTS),
        imu["packets"],
        imu["errors"],
    )
    for name in BUSES:
        b = fields["buses"][name]
        state = {v: k for k, v in BUS_STATES.items()}[b["state"]]
        body += STATUS_BUS.pack(
            state, b["tec"], b["rec"], 0, *(b[k] for k in BUS_COUNTS)
        )
    return body


LINK_COUNTS = (
    "frames",
    "crc_errors",
    "overruns",
    "uart_errors",
    "malformed",
    "dropped",
)
BUS_COUNTS = ("tx", "tx_fail", "rx", "rx_errors", "rx_drop", "queue_drop")


def parse_status(body: bytes) -> dict:
    head = STATUS_HEAD.unpack_from(body)
    t_us, uptime_ms, flags, vbus_mv = head[:4]
    link = dict(zip(LINK_COUNTS, head[4:10]))
    out = {
        "t_us": t_us,
        "uptime": uptime_ms / 1000,
        "hold": bool(flags & 1),
        "button": bool(flags & 2),
        "off": bool(flags & 4),
        "lost": bool(flags & 8),
        "imu_found": bool(flags & 16),
        "ina_found": bool(flags & 32),
        "vbus": vbus_mv / 1000 if flags & 32 and vbus_mv else None,
        "link": link,
        "imu": {"packets": head[10], "errors": head[11]},
        "buses": {},
    }
    for i, name in enumerate(BUSES):
        state, tec, rec, _, *counts = STATUS_BUS.unpack_from(
            body, STATUS_HEAD.size + i * STATUS_BUS.size
        )
        out["buses"][name] = {
            "state": BUS_STATES.get(state, f"state {state}"),
            "tec": tec,
            "rec": rec,
            **dict(zip(BUS_COUNTS, counts)),
        }
    return out


# ---- the check ---------------------------------------------------------------

# The same as firmware/diag_link's known_answers test: the CRCs from
# binascii.crc_hqx, the COBS done by hand.
VECTORS = [
    (PING, b"", "04 02 b2 c1 00"),
    (
        CAN_SEND,
        can_send(2, 0x7FF, bytes([0x01, 0x00, 0x33, 0x08])),
        "03 10 02 03 ff 07 01 02 01 05 33 08 c9 75 00",
    ),
]


def check() -> bool:
    ok = crc16(b"123456789") == 0x29B1
    print(f"crc16 check value {crc16(b'123456789'):#06x}, want 0x29b1")
    for kind, body, want in VECTORS:
        got = encode(kind, body).hex(" ")
        ok &= got == want
        print(f"type {kind:#04x}: {got}" + ("" if got == want else f"  WANT {want}"))
    bodies = [b"", b"\0", b"\0\0\0", b"\1" * 253, b"\1" * 254, bytes(range(256)) * 2]
    stream = b"".join(encode(0x40 + k, body) for k, body in enumerate(bodies))
    stream = stream[:2] + bytes([stream[2] ^ 0x20]) + stream[3:]  # spoil the first
    decoder = Decoder()
    got = decoder.feed(stream[:7]) + decoder.feed(stream[7:])
    want = [(0x40 + k, body) for k, body in enumerate(bodies)][1:]
    ok &= got == want and decoder.crc_errors == 1
    print(
        f"round trip: {len(got)} of {len(want)} back whole, "
        f"{decoder.crc_errors} spoilt one caught"
    )
    print("PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    sys.exit(0 if check() else 1)
