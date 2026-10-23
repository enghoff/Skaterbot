# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Talk to diagd.py: a library, and a command line for looking at the robot from the Pi or a PC.

    python3 diag_client.py status                   the controller's status, once
    python3 diag_client.py info                     what the controller is and found
    python3 diag_client.py candump [--bus A]        every CAN frame, until Ctrl-C
    python3 diag_client.py scan [--to 16]           which motor IDs answer, on each bus
    python3 diag_client.py imu [--hz 50]            the IMU's reports, until Ctrl-C
    python3 diag_client.py i2c 0x40 --write fe --read 2
    python3 diag_client.py stop                     every motor off

--robot says where diagd is. host:port is TCP, 127.0.0.1:7700 if not given;
ssh:DEST goes through `ssh -W 127.0.0.1:7700 DEST`, so that from a PC the Pi
needs no port open and the key and options are the PC's own SSH configuration's
for DEST. Options for ssh go before DEST: `ssh:-i ~/.ssh/key admin@pi`.
docs/DIAGNOSTICS.md is the specification.

The library is Robot, one connection, and CanBus, one of its buses in the shape
bench/damiao.py's Bus drives. A Robot pings every 0.1 s from a thread of its own,
which is what keeps control: diagd stops every motor and takes control back from
a client it has not heard from for half a second. Every time it hands on has
been moved onto this machine's time.monotonic().

Only the standard library.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import shlex
import socket
import subprocess
import sys
import threading
import time

PORT = 7700
DEFAULT_ROBOT = f"127.0.0.1:{PORT}"
PING_S = 0.1
# How fast the mapping of the controller's clock onto this one may creep later,
# for the two clocks' drift: 100 ppm, against the 15 measured.
CREEP = 1e-4
# Windows' own OpenSSH, rather than whichever ssh is first on the PATH.
WINDOWS_SSH = r"C:\Windows\System32\OpenSSH\ssh.exe"


class RobotError(RuntimeError):
    pass


class _Tcp:
    def __init__(self, host: str, port: int):
        self.sock = socket.create_connection((host, port), timeout=5)
        self.sock.settimeout(None)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.reader = self.sock.makefile("rb")
        self.where = f"{host}:{port}"

    def write(self, data: bytes) -> None:
        self.sock.sendall(data)

    def why_closed(self) -> str:
        return "diagd closed the connection"

    def close(self) -> None:
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


class _Ssh:
    def __init__(self, spec: str, port: int):
        # The destination last, and any of ssh's own options before it.
        *options, destination = shlex.split(spec, posix=os.name != "nt")
        ssh = WINDOWS_SSH if os.name == "nt" and os.path.exists(WINDOWS_SSH) else "ssh"
        # Ten seconds, for a name found by a proxy: bpi-m4zero takes four.
        command = [ssh, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
        command += ["-o", "ServerAliveInterval=2", "-o", "ServerAliveCountMax=3"]
        command += [*options, "-W", f"127.0.0.1:{port}", destination]
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.reader = self.proc.stdout
        self.where = f"ssh {destination}"
        self.errors: list[str] = []
        threading.Thread(target=self._stderr, daemon=True).start()

    def _stderr(self) -> None:
        for raw in self.proc.stderr:
            self.errors.append(raw.decode(errors="replace").strip())

    def write(self, data: bytes) -> None:
        view = memoryview(data)
        while view:
            view = view[self.proc.stdin.write(view) :]

    def why_closed(self) -> str:
        time.sleep(0.1)  # for ssh's last words
        said = "; ".join(e for e in self.errors if e)
        if "open failed" in said:
            # ssh got in, and nothing on the far side took the connection.
            return (
                f"ssh reached {self.where[4:]}, but diagd is not running there. "
                "Start it on the Pi: start_diagd"
            )
        return f"ssh ended: {said}" if said else "ssh ended"

    def close(self) -> None:
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        self.proc.terminate()


def _open(robot: str):
    if robot.startswith("ssh:"):
        return _Ssh(robot[4:], PORT)
    host, _, port = robot.rpartition(":")
    if not host:
        host, port = robot, ""
    return _Tcp(host or "127.0.0.1", int(port or PORT))


class Robot:
    """One connection to diagd."""

    def __init__(
        self,
        robot: str = DEFAULT_ROBOT,
        name: str = "diag_client",
        streams=("status", "log"),
    ):
        self.robot = robot
        try:
            self._link = _open(robot)
        except ConnectionRefusedError as error:
            raise RobotError(
                f"nothing is listening at {robot}: diagd is not running there. "
                "On this computer, python sbc/diagd.py --sim runs a simulated "
                "robot; the real one is ssh:admin@<the Pi>, with diagd running "
                "on the Pi"
            ) from error
        except OSError as error:
            raise RobotError(f"cannot reach diagd at {robot}: {error}") from error
        self.where = self._link.where
        self._write_lock = threading.Lock()
        self._ids = itertools.count(1)
        self._waiting: dict[int, list] = {}
        self._handlers: dict[str, list] = {}
        self._offset: float | None = None
        self._offset_at = 0.0
        self.error: str | None = None
        self.status: dict | None = None
        self.on("status", self._keep_status)
        threading.Thread(target=self._read_loop, daemon=True).start()
        try:
            # Long enough that ssh's own account of a failure comes first: a
            # name found by a proxy takes ten seconds to fail.
            hello = self.request("hello", name=name, wait=30.0)
            self.request("subscribe", streams=list(streams))
        except RobotError:
            self.close()
            raise
        self.info: dict = hello["info"]
        self.daemon: dict = hello["daemon"]
        self.control_holder: str | None = hello.get("control")
        self._running = True
        threading.Thread(target=self._ping_loop, daemon=True).start()

    # -- plumbing ----------------------------------------------------------------

    def on(self, event: str, handler) -> None:
        """Call handler(message) for every event of this kind, on the reader
        thread. "closed" comes once, when the connection goes."""
        self._handlers.setdefault(event, []).append(handler)

    def _write(self, message: dict) -> None:
        data = (json.dumps(message, separators=(",", ":")) + "\n").encode()
        try:
            with self._write_lock:
                self._link.write(data)
        except (OSError, ValueError) as error:
            raise RobotError(f"connection to diagd lost: {error}") from error

    def send(self, op: str, **fields) -> None:
        """A request that wants no answer."""
        self._write({"op": op, **fields})

    def request(self, op: str, wait: float = 2.0, **fields) -> dict:
        """A request, and its answer; RobotError if it is refused or none comes."""
        if self.error:
            raise RobotError(self.error)
        rid = next(self._ids)
        slot = [threading.Event(), None]
        self._waiting[rid] = slot
        try:
            self._write({"op": op, "req": rid, **fields})
            if not slot[0].wait(wait):
                raise RobotError(
                    self.error or f"{op}: no answer from diagd in {wait:g} s"
                )
        finally:
            self._waiting.pop(rid, None)
        answer = slot[1]
        if not answer.get("ok"):
            raise RobotError(answer.get("error", f"{op} refused"))
        return answer

    def to_host(self, t: float) -> float:
        """The controller's time as this machine's time.monotonic(), by the
        smallest gap yet seen between the two: the message that took least
        time to arrive, which is the best guess at when anything happened."""
        now = time.monotonic()
        gap = now - t
        if self._offset is None:
            self._offset = gap
        else:
            self._offset = min(gap, self._offset + CREEP * (now - self._offset_at))
        self._offset_at = now
        return t + self._offset

    def _read_loop(self) -> None:
        try:
            for raw in self._link.reader:
                try:
                    message = json.loads(raw)
                except ValueError:
                    continue
                if "ev" in message:
                    if message.get("t") is not None:
                        message["t"] = self.to_host(message["t"])
                    for handler in self._handlers.get(message["ev"], ()):
                        handler(message)
                    continue
                frame = message.get("frame")
                if frame and frame.get("t") is not None:
                    frame["t"] = self.to_host(frame["t"])
                slot = self._waiting.get(message.get("req"))
                if slot:
                    slot[1] = message
                    slot[0].set()
        except (OSError, ValueError):
            pass
        self.error = self.error or self._link.why_closed()
        self._running = False
        for slot in list(self._waiting.values()):
            slot[0].set()
            slot[1] = {"ok": False, "error": self.error}
        for handler in self._handlers.get("closed", ()):
            handler({"ev": "closed", "why": self.error})

    def _ping_loop(self) -> None:
        while self._running:
            time.sleep(PING_S)
            try:
                self.send("ping")
            except RobotError:
                return

    def _keep_status(self, message: dict) -> None:
        self.status = message

    def close(self) -> None:
        self._running = False
        self.error = self.error or "closed"
        self._link.close()

    # -- the API, by name --------------------------------------------------------

    def take_control(self) -> None:
        self.request("control", take=True)

    def release_control(self) -> None:
        self.request("control", take=False)

    def stop(self) -> None:
        """Every motor off, at the controller. Needs no control."""
        self.send("stop")

    def can(self, bus: str) -> CanBus:
        return CanBus(self, bus)


class CanBus:
    """One of the robot's three CAN buses, in the shape bench/damiao.py's Bus
    wants a link: frames out, frames in, and a request answered at diagd."""

    def __init__(self, robot: Robot, bus: str):
        self.robot = robot
        self.bus = bus
        self.where = f"bus {bus}, {robot.where}"
        self._handler = None
        robot.on("can", self._heard)

    @property
    def error(self) -> str | None:
        return self.robot.error

    def set_handler(self, handler) -> None:
        """handler(can_id, data, t) for every frame heard on this bus."""
        self._handler = handler

    def _heard(self, message: dict) -> None:
        if message["bus"] == self.bus and self._handler is not None:
            self._handler(message["id"], bytes.fromhex(message["data"]), message["t"])

    def send(self, can_id: int, data: bytes) -> None:
        self.robot.send("can.send", bus=self.bus, id=can_id, data=bytes(data).hex())

    def request(
        self, can_id: int, data: bytes, expect: bytes, timeout: float
    ) -> bytes | None:
        """Sends a frame, and returns the data of the first frame on this bus
        whose data starts with expect, or None if none came within timeout."""
        try:
            answer = self.robot.request(
                "can.request",
                wait=timeout + 2.0,
                bus=self.bus,
                id=can_id,
                data=bytes(data).hex(),
                expect=bytes(expect).hex(),
                timeout=timeout,
            )
        except RobotError as error:
            if str(error) == "timeout":
                return None
            raise
        return bytes.fromhex(answer["frame"]["data"])

    def close(self) -> None:
        self._handler = None


# ---- the command line --------------------------------------------------------


def show_status(s: dict) -> None:
    vbus = f"{s['vbus']:.2f} V" if s.get("vbus") is not None else "not read"
    print(f"controller up {s['uptime']:.1f} s, link {'up' if s['link_up'] else 'DOWN'}")
    print(
        f"  power   HOLD {'high' if s['hold'] else 'low'}, button "
        f"{'down' if s['button'] else 'up'}{', OFF asked for' if s['off'] else ''}"
        f"{', DEADMAN TRIPPED' if s['lost'] else ''}"
    )
    print(
        f"  battery {vbus}   IMU {'found' if s['imu_found'] else 'not found'}, "
        f"{s['imu']['packets']} packets, {s['imu']['errors']} errors"
    )
    link, pi = s["link"], s["pi"]
    print(
        f"  link    controller heard {link['frames']}, {link['crc_errors']} bad CRC, "
        f"{link['uart_errors']} UART errors, {link['dropped']} dropped for room; "
        f"the Pi heard {pi['frames']}, {pi['crc_errors']} bad CRC"
    )
    for name, b in s["buses"].items():
        print(
            f"  bus {name}   {b['state']}, TEC {b['tec']} REC {b['rec']}; sent {b['tx']}, "
            f"{b['tx_fail']} not taken, heard {b['rx']}, {b['rx_errors']} errors"
        )
    print(f"  clients {pi['clients']}, control: {pi['control'] or 'nobody'}")


def wait_for_status(robot: Robot) -> dict:
    deadline = time.monotonic() + 2
    while robot.status is None and time.monotonic() < deadline:
        time.sleep(0.05)
    if robot.status is None:
        return robot.request("status")["status"]
    return robot.status


def scan(robot: Robot, buses: str, last: int) -> None:
    """Which motor IDs answer a register read of their own ID, on each bus."""
    robot.take_control()
    try:
        for bus in buses:
            can = robot.can(bus)
            found = []
            for i in range(1, last + 1):
                ask = bytes([i & 0xFF, i >> 8, 0x33, 0x08, 0, 0, 0, 0])
                if can.request(0x7FF, ask, ask[:4], 0.02) is not None:
                    found.append(i)
            print(f"bus {bus}: {', '.join(map(str, found)) if found else 'nothing'}")
    finally:
        robot.release_control()


def hold(robot: Robot) -> None:
    """Until Ctrl-C, or the connection goes."""
    while robot.error is None:
        time.sleep(0.2)
    raise RobotError(robot.error)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--robot",
        default=os.environ.get("DIAG_ROBOT", DEFAULT_ROBOT),
        help=f"host:port or ssh:DEST (default {DEFAULT_ROBOT}, or $DIAG_ROBOT)",
    )
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="the controller's status, once")
    sub.add_parser("info", help="what the controller is and what it found")
    p = sub.add_parser("candump", help="every CAN frame, until Ctrl-C")
    p.add_argument("--bus", default="ABC", help="A, B, C or any of them (default all)")
    p = sub.add_parser("scan", help="which motor IDs answer, on each bus")
    p.add_argument("--bus", default="ABC")
    p.add_argument("--to", type=int, default=16, help="the last ID tried (default 16)")
    p = sub.add_parser("imu", help="the IMU's reports, until Ctrl-C")
    p.add_argument("--hz", type=float, default=50)
    p.add_argument("--reports", default="accel,gyro,game,gravity")
    p = sub.add_parser("i2c", help="one I2C transaction")
    p.add_argument("addr", type=lambda s: int(s, 0))
    p.add_argument("--write", default="", help="bytes to write, in hex")
    p.add_argument("--read", type=int, default=0, help="bytes to read")
    sub.add_parser("stop", help="every motor off")
    args = ap.parse_args()

    streams = {"candump": ("can", "log"), "imu": ("imu", "log")}.get(
        args.command, ("status", "log")
    )
    try:
        robot = Robot(args.robot, name=f"diag_client {args.command}", streams=streams)
    except RobotError as error:
        sys.exit(str(error))
    try:
        run(robot, args)
    except RobotError as error:
        sys.exit(str(error))
    except KeyboardInterrupt:
        pass
    finally:
        robot.close()


def run(robot: Robot, args) -> None:
    if args.command == "status":
        show_status(wait_for_status(robot))
    elif args.command == "info":
        for key, value in robot.info.items():
            print(f"{key:>12}  {value}")
        print(f"{'diagd':>12}  {robot.daemon['link']}")
    elif args.command == "stop":
        robot.request("stop")
        print("every motor stopped")
    elif args.command == "scan":
        scan(robot, args.bus, args.to)
    elif args.command == "i2c":
        robot.take_control()
        try:
            answer = robot.request(
                "i2c", addr=args.addr, write=args.write, read=args.read
            )
            print(answer.get("data") or "done")
        finally:
            robot.release_control()
    elif args.command == "candump":
        buses = set(args.bus)

        def frame(m):
            if m["bus"] in buses:
                print(
                    f"{m['t']:12.6f}  {m['bus']}  {m['id']:03X}  [{len(m['data']) // 2}]  {m['data']}"
                )

        robot.on("can", frame)
        robot.on("log", lambda m: print(f"# {m['text']}"))
        hold(robot)
    elif args.command == "imu":
        robot.take_control()
        reports = args.reports.split(",")
        try:
            for report in reports:
                answer = robot.request("imu.enable", report=report, hz=args.hz)
                print(f"# {report}: granted {answer['hz']} Hz")
            robot.on(
                "imu",
                lambda m: print(
                    f"{m['t']:12.6f}  {m['report']:8s} {m['status']}  "
                    + "  ".join(f"{v:9.4f}" for v in m["v"])
                ),
            )
            hold(robot)
        finally:
            for report in reports:
                try:
                    robot.request("imu.enable", report=report, hz=0)
                except RobotError:
                    pass
            robot.release_control()


if __name__ == "__main__":
    main()
