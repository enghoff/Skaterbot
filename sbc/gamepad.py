"""The game controller, and what its sticks and buttons ask of the robot.

The console runs this whether or not a browser is open: a robot being driven by
a controller should not need a phone beside it. It reads the first game
controller Linux offers, however it arrived, turns what it reads into the three
numbers and the one press the policy takes from an operator, and sends them to
diagd fifty times a second for as long as a controller is there. Sending them on
to the policy, and every rule for what the policy's side does with them, is in
docs/POLICY_INTERFACE.md, "The operator's command". Until something runs a
policy, nothing moves when a stick does. No button on it stops the motors, because
that would drop the robot: letting go stops the driving and leaves it standing, and
stopping the motors is the robot's own power button.

Speed is on the analog triggers, the right (gas) forward and the left (brake) back:
how far one is pulled asks for that much, and letting go asks for none. The turn,
D-pad and jump are the MuJoCo driver's (simulation/mujoco/drive.py, Input.poll_pad).
Select is the speed mode: each press is counted and sent, and what runs the policy
toggles between its slow limit and its fast one, starting slow each time it takes over.
Once the daemon says the policy has changed it, the controller rumbles twice going
fast and once going slow, so a press nothing took is answered by nothing.

The D-pad's ride height goes back to the top of its range whenever the robot is
disarmed, so that every run starts high, however low the last one was left: the
owner's rule, 6 November 2026. A run that took over already low had been D5's fall.
Disarmed is what flash_robot.sh means by it, nothing holding control, as diagd's
status says; while that lasts the height is held at the top, and the D-pad moves it
again once a run holds control.

A dropped controller must not leave the robot driving, and two things watch for
that. Linux taking the device away ends it: at once when a controller is switched off,
and when the link times out when one is carried out of range, Linux going on reporting
its last state until then, for a time not yet measured. Letting go ends it too, since
both spring back. And each counts only once it has been seen at rest, so one already
pulled, or a trigger mistaken for a stick, asks for nothing. Silence ended it as well
until 5 November 2026, but a control held still has nothing to report, so on the robot
a held turn stopped after two revolutions, and it took letting go to start it again.
"""

from __future__ import annotations

import contextlib
import glob
import math
import os
import select
import struct
import threading
import time
from dataclasses import dataclass

import diag_client

# Linux's event codes, linux/input-event-codes.h.
EV_KEY, EV_ABS = 0x01, 0x03
ABS_X, ABS_Y, ABS_Z, ABS_RX, ABS_RY, ABS_RZ = 0x00, 0x01, 0x02, 0x03, 0x04, 0x05
ABS_GAS, ABS_BRAKE = 0x09, 0x0A
EV_SYN, SYN_REPORT, SYN_DROPPED = 0x00, 0x00, 0x03
ABS_HAT0Y = 0x11
BTN_SOUTH, BTN_EAST, BTN_C, BTN_WEST = 0x130, 0x131, 0x132, 0x134
BTN_Z, BTN_TL, BTN_TR = 0x135, 0x136, 0x137
BTN_TL2, BTN_SELECT = 0x138, 0x13A
SONY, MICROSOFT = 0x054C, 0x045E

# The trained ranges of the driving policy for the robot, from its run's
# params/env.yaml (exports/rl/rough-2026-11-07_11-52-47_d8, D8, which has D6's ranges):
# command_lin_vel_x, command_yaw_rate and command_leg_height_m. The exported run is
# the authority: check these against whichever is deployed. A trigger's or a stick's
# end sends the whole of it, and balance.py scales that to its own limits. That
# policy was trained inside the diamond between the two tops, which balance.py
# holds it to after scaling, so ENVELOPE, which would hold it here, is off: here it
# would halve a slow limit's full turn and full speed together for nothing.
# launcher.py's --fast-speed 1.8 and --fast-turn 15 keep fast mode where D3 had it. The
# turn is the task's, twice the top speed over the wheels' track, 25.0998, to the
# thousandth a command is sent to.
TOP_SPEED_M_S = 2.2
TOP_TURN_RAD_S = 25.1
# The top is the crouch D7 and D8 were trained from, not the task's 207 mm: on the robot
# on 2026-11-07 D7 stood at 0.05-0.13 rad/s rms at 203 mm and swayed at 1.2-1.6 Hz,
# 0.43-0.45 rad/s and about 5 degrees each way, at 207, as MuJoCo had it sway there.
# D8's checks stood it at 204 mm and no higher.
HEIGHT_RANGE_M = (0.165, 0.2035)
ENVELOPE = False
# default_leg_height_m in the same file: the crouch trained around.
DEFAULT_HEIGHT_M = 0.2035
# What a trigger's or stick's end means on starting. The console can lower these, and a restart
# puts them back, on purpose.
START_SPEED_M_S = TOP_SPEED_M_S
START_TURN_RAD_S = TOP_TURN_RAD_S
# The MuJoCo driver's dead zone.
DEAD_ZONE = 0.12
# Holding the D-pad moves the leg height this fast.
HEIGHT_RATE_M_S = 0.025
SEND_HZ = 50
# Whoever reads the command needs to know the path is alive, not every frame:
# the daemon's answer, saying whether the controller takes it, comes this often.
ASK_S = 1.0
RECONNECT_S = 1.0
RESCAN_S = 1.0
# A change of speed mode is answered on the controller: two pulses of rumble going
# fast, one going slow. Only once the daemon says the policy has changed it, so that
# a press nothing took is answered by nothing. A press is watched this long for that,
# with the daemon asked every frame meanwhile.
MODE_WATCH_S = 1.0
# Each pulse and the gap after it, and its strength out of the controller's 100.
PULSE_S, PULSE_GAP_S, PULSE_STRENGTH = 0.15, 0.15, 60


@dataclass(frozen=True)
class Layout:
    """Which of a controller's codes does what."""

    turn: int
    gas: int | None
    brake: int | None
    jump: int
    # Select on an Xbox controller, by its report's order after the gaps; Share on a
    # PlayStation one. Neither yet seen pressed on the robot: the console shows the
    # code of whatever is held.
    mode: int = BTN_SELECT


def triggers_of(axes, turn: int) -> tuple[int | None, int | None]:
    """Which axes are the right and left triggers: GAS and BRAKE where the controller
    says so, or Z and RZ with the right stick on RX. Otherwise it has none to drive
    with, and can only turn."""
    if {ABS_GAS, ABS_BRAKE} <= set(axes):
        return ABS_GAS, ABS_BRAKE
    if turn == ABS_RX and {ABS_Z, ABS_RZ} <= set(axes):
        return ABS_RZ, ABS_Z
    return None, None


def layout_of(axes, keys, vendor: int = 0) -> Layout:
    """A controller's own Linux driver names its buttons for where they are, and
    its right stick RX and RY. The robot's kernel has none of those drivers
    (CONFIG_HID_SONY, _MICROSOFT and _NINTENDO are off), so most controllers reach
    it through hid-generic, which numbers a report's buttons in order from
    BTN_SOUTH.

    An Xbox controller's report leaves gaps so that its codes come out named for
    position anyway. It declares the gaps as buttons too, so that it claims BTN_C
    and BTN_Z and never sends them. Read off a real one on this kernel (045E:0B20,
    firmware 5.23, on 2026-11-04): A 0x130, B 0x131, X 0x133, Y 0x134, LB 0x136,
    RB 0x137, left trigger BRAKE, right trigger GAS, which leaves Z and RZ the right
    stick.

    On any other controller BTN_C or BTN_Z makes the shoulders the fifth and sixth.
    A PlayStation controller's report starts Square, Cross, Circle, Triangle, and
    has its triggers on RX and RY, with Z and RZ its right stick. That is from what
    the drivers and the controllers' reports are documented to do, not from
    watching one.
    """
    turn = ABS_RX if ABS_RX in axes else ABS_Z
    if vendor == SONY and {BTN_C, BTN_Z} & set(keys):
        return Layout(ABS_Z, ABS_RY, ABS_RX, BTN_EAST, BTN_TL2)
    return Layout(turn, *triggers_of(axes, turn), BTN_SOUTH)


class Operator:
    """One controller's sticks and buttons, turned into a command.

    Not thread-safe: PadManager holds a lock around it. `ranges` gives each axis's
    (lowest, highest), which differ from one controller to the next, and `values`
    where each stands on opening, which is how a trigger at rest is told from a
    stick that has not moved.
    """

    def __init__(
        self,
        ranges: dict[int, tuple[int, int]],
        now: float,
        layout: Layout | None = None,
        values: dict[int, int] | None = None,
    ):
        self.ranges = ranges
        self.layout = layout or layout_of(ranges, ())
        self.axes: dict[int, int] = dict(values or {})
        # The triggers and the turn, once seen at rest.
        self.armed: set[int] = set()
        self.held: set[int] = set()
        self.hat = 0
        self.height = DEFAULT_HEIGHT_M
        self.jump = 0
        self.mode = 0
        self.speed_limit = START_SPEED_M_S
        self.turn_limit = START_TURN_RAD_S
        self.stepped = now

    def event(self, kind: int, code: int, value: int, now: float) -> None:
        if kind == EV_ABS:
            if code == ABS_HAT0Y:
                self.hat = -value
            else:
                self.axes[code] = value
        elif kind == EV_KEY and value != 2:  # 2 is a key repeating
            (self.held.add if value else self.held.discard)(code)
            if value and code == self.layout.jump:
                self.jump = (self.jump + 1) & 0xFF
            if value and code == self.layout.mode:
                self.mode = (self.mode + 1) & 0xFF

    def position(self, code: int) -> float:
        """An axis from -1 to 1, its middle 0."""
        if code not in self.axes or code not in self.ranges:
            return 0.0
        low, high = self.ranges[code]
        if high <= low:
            return 0.0
        x = (self.axes[code] - (low + high) / 2) / ((high - low) / 2)
        return max(-1.0, min(1.0, x))

    def stick(self, code: int) -> float:
        """The same past a dead zone, or nothing if not yet seen in its middle."""
        x = self.position(code)
        if code not in self.armed or abs(x) < DEAD_ZONE:
            return 0.0
        return (x - math.copysign(DEAD_ZONE, x)) / (1 - DEAD_ZONE)

    def pull(self, code: int | None) -> float:
        """A trigger from 0 at rest to 1 pulled all the way."""
        if code not in self.axes or code not in self.ranges:
            return 0.0
        low, high = self.ranges[code]
        if high <= low:
            return 0.0
        return max(0.0, min(1.0, (self.axes[code] - low) / (high - low)))

    def trigger(self, code: int | None) -> float:
        """The same past a dead zone, or nothing if not yet seen at rest."""
        x = self.pull(code)
        if code not in self.armed or x < DEAD_ZONE:
            return 0.0
        return (x - DEAD_ZONE) / (1 - DEAD_ZONE)

    def resting(self) -> set:
        """Which of the triggers and the turn are at rest now."""
        turn = self.layout.turn
        found = {turn} if abs(self.position(turn)) < DEAD_ZONE else set()
        triggers = (self.layout.gas, self.layout.brake)
        return found | {code for code in triggers if self.pull(code) < DEAD_ZONE}

    def why_not(self, now: float) -> str:
        layout = self.layout
        inputs = {layout.turn, layout.gas, layout.brake}
        if layout.gas is None:
            return "this controller has no analog triggers to drive with"
        if self.resting() == inputs:
            return ""
        if inputs - self.armed:
            return "let the triggers and the stick come back to rest"
        return ""

    def command(self, now: float) -> dict:
        """What is being asked for now, inside the trained ranges."""
        dt, self.stepped = now - self.stepped, now
        layout = self.layout
        # What is at rest may start at any time, so that a quick pull after a long idle
        # counts.
        self.armed |= self.resting()
        forward = self.trigger(layout.gas) - self.trigger(layout.brake)
        forward *= self.speed_limit
        # Left on a stick is its lowest value, as the policy's turn wants positive.
        turn = -self.stick(layout.turn) * self.turn_limit
        share = abs(forward) / TOP_SPEED_M_S + abs(turn) / TOP_TURN_RAD_S
        if ENVELOPE and share > 1:
            forward /= share
            turn /= share
        low, high = HEIGHT_RANGE_M
        self.height = min(
            high, max(low, self.height + self.hat * HEIGHT_RATE_M_S * min(dt, 0.1))
        )
        return {
            # -0.0 is not a thing to send to a person, or a log.
            "forward": round(forward, 3) + 0.0,
            "turn": round(turn, 3) + 0.0,
            "height": round(self.height, 4),
            "live": True,
            "jump": self.jump,
            "mode": self.mode,
        }


# ---- where the events come from ----------------------------------------------


# Linux's evdev interface, linux/input.h: the ioctls, and the event as read.
INPUT_EVENT = struct.Struct("@llHHi")
ABSINFO = struct.Struct("<6i")  # value, min, max, fuzz, flat, resolution
EVIOCGID, EVIOCGNAME_BASE, EVIOCGBIT_BASE, EVIOCGABS_BASE = 0x02, 0x06, 0x20, 0x40
KEY_BYTES, ABS_BYTES = 96, 8  # KEY_MAX and ABS_MAX, in bits


def eviocg(number: int, size: int) -> int:
    """_IOC(_IOC_READ, 'E', number, size)."""
    return 2 << 30 | size << 16 | ord("E") << 8 | number


def bits(data: bytes) -> set[int]:
    return {i for i in range(len(data) * 8) if data[i // 8] >> (i % 8) & 1}


def rumble_report(seconds: float, strength: int = PULSE_STRENGTH) -> bytes:
    """A Microsoft controller's rumble over Bluetooth, as Linux's hid-microsoft
    writes it (xb1s_ff_report): report 3; which motors, bit 0 the weak and bit 1 the
    strong; the left and right triggers' strength and the strong and weak motors',
    each out of 100; how long, in 10 ms; a delay before it, in 10 ms; and how many
    times more. It stops by itself, so a program gone mid-pulse leaves nothing on."""
    ticks = max(1, min(255, round(seconds * 100)))
    return bytes([0x03, 0x03, 0, 0, strength, strength, ticks, 0, 0])


def hidraw_of(event_path: str) -> str | None:
    """The hidraw node of the HID device an event node came from, if any."""
    name = os.path.basename(event_path)
    found = sorted(glob.glob(f"/sys/class/input/{name}/device/device/hidraw/hidraw*"))
    return f"/dev/{os.path.basename(found[0])}" if found else None


class Rumble:
    """Pulses on a controller's motors. The robot's kernel has neither hid-microsoft
    nor force feedback through hid-generic, so the report goes to the controller's
    hidraw node as it is. That node is root's alone until install_console_bluetooth.sh
    gives a Microsoft controller's to the input group. `why_not` says why there are
    none."""

    def __init__(self, path: str | None = None, why_not: str = ""):
        self.lock = threading.Lock()
        self.fd = None
        self.why_not = why_not
        if path is None:
            self.why_not = why_not or "no hidraw node for this controller"
            return
        try:
            # Windows, where the tests run, has no O_NONBLOCK.
            self.fd = os.open(path, os.O_WRONLY | getattr(os, "O_NONBLOCK", 0))
        except OSError as error:
            self.why_not = f"cannot write {path}: {error.strerror}"

    def pulses(self, n: int) -> None:
        """n pulses, on a thread of their own, so that nothing waits on the gaps."""
        if self.fd is not None:
            threading.Thread(target=self.play, args=(n,), daemon=True).start()

    def play(self, n: int) -> None:
        for i in range(n):
            if i:
                # A report replaces the one before it, so the next waits for the gap.
                time.sleep(PULSE_S + PULSE_GAP_S)
            with self.lock:
                if self.fd is None:
                    return  # closed: the number may be another file's by now
                try:
                    os.write(self.fd, rumble_report(PULSE_S))
                except OSError as error:
                    self.why_not = f"the controller refused a rumble: {error.strerror}"
                    return

    def close(self) -> None:
        with self.lock:
            fd, self.fd = self.fd, None
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)


class EvdevPad:
    """A real controller, read from its device node with the standard library, so
    that it needs nothing installed on the Pi. The read raises OSError once Linux
    has taken the device away."""

    def __init__(
        self,
        fd: int,
        name: str,
        axes: dict,
        keys: set[int],
        vendor: int,
        rumble: Rumble | None = None,
    ):
        self.fd = fd
        self.name = name
        self.ranges = {axis: info[1:3] for axis, info in axes.items()}
        self.values = {axis: info[0] for axis, info in axes.items()}
        self.layout = layout_of(axes, keys, vendor)
        self.rumble = rumble or Rumble(why_not="none known for this controller")
        self.dropping = False

    def read(self, timeout: float) -> list[tuple[int, int, int]]:
        if not select.select([self.fd], [], [], timeout)[0]:
            return []
        data = os.read(self.fd, INPUT_EVENT.size * 64)
        return self.after_drops(event[2:] for event in INPUT_EVENT.iter_unpack(data))

    def after_drops(self, events) -> list[tuple[int, int, int]]:
        """Linux says SYN_DROPPED when its queue overflowed, and a trigger's release may
        be what went. As linux/input.h says to, what comes before the next report is
        thrown away, and where every axis stands is asked for afresh."""
        out, dropping = [], self.dropping
        for kind, code, value in events:
            if kind == EV_SYN and code == SYN_DROPPED:
                dropping = True
            elif dropping and kind == EV_SYN and code == SYN_REPORT:
                dropping = False
                out += [(EV_ABS, axis, self.stands(axis)) for axis in self.ranges]
            elif not dropping:
                out.append((kind, code, value))
        self.dropping = dropping
        return out

    def stands(self, axis: int) -> int:
        import fcntl

        buffer = bytearray(ABSINFO.size)
        fcntl.ioctl(self.fd, eviocg(EVIOCGABS_BASE + axis, ABSINFO.size), buffer)
        return ABSINFO.unpack(bytes(buffer))[0]

    def close(self) -> None:
        self.rumble.close()
        with contextlib.suppress(OSError):
            os.close(self.fd)


def game_controller(axes, keys) -> bool:
    """A device with sticks and a face button: which leaves out the motion
    sensors and touchpad that a PlayStation controller brings as devices of their
    own, neither of which has that button."""
    return BTN_SOUTH in keys and {ABS_X, ABS_Y} <= set(axes)


def open_pad(path: str) -> EvdevPad | None:
    """The controller at this device node, or None if what is there is not one."""
    import fcntl

    def ask(number: int, size: int) -> bytes:
        buffer = bytearray(size)
        fcntl.ioctl(fd, eviocg(number, size), buffer)
        return bytes(buffer)

    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        keys = bits(ask(EVIOCGBIT_BASE + EV_KEY, KEY_BYTES))
        present = bits(ask(EVIOCGBIT_BASE + EV_ABS, ABS_BYTES))
        if game_controller(present, keys):
            axes = {
                axis: ABSINFO.unpack(ask(EVIOCGABS_BASE + axis, ABSINFO.size))
                for axis in present
            }
            name = ask(EVIOCGNAME_BASE, 256).split(b"\0", 1)[0].decode(errors="replace")
            _, vendor, _, _ = struct.unpack("<4H", ask(EVIOCGID, 8))
            # Report 3 is only known to be a rumble on Microsoft's.
            rumble = Rumble(hidraw_of(path)) if vendor == MICROSOFT else None
            return EvdevPad(fd, name, axes, keys, vendor, rumble)
    except OSError:
        pass  # gone since it was listed, or not a device that answers these
    os.close(fd)
    return None


def device_number(path: str) -> int:
    return int(path.rpartition("event")[2])


def find_evdev_pad() -> EvdevPad | None:
    """The first game controller Linux offers, or None. Raises OSError if this
    account may not read input devices, which wants the `input` group."""
    refused = None
    for path in sorted(glob.glob("/dev/input/event*"), key=device_number):
        try:
            pad = open_pad(path)
        except PermissionError as error:
            refused = error
            continue
        except OSError:
            continue  # gone between being listed and being opened
        if pad:
            return pad
    if refused:
        raise refused
    return None


class SimPad:
    """A controller for --sim, present while `there()` says so: it sweeps its gas
    and its stick slowly, so that the page has something to show. Nothing about it
    is meant to resemble a real controller's timing."""

    def __init__(self, there, name="Simulated controller"):
        self.there = there
        self.name = name
        self.ranges = {
            ABS_X: (0, 255),
            ABS_Y: (0, 255),
            ABS_RX: (0, 255),
            ABS_GAS: (0, 255),
            ABS_BRAKE: (0, 255),
        }
        self.axes = dict.fromkeys(self.ranges, 128) | {ABS_GAS: 0, ABS_BRAKE: 0}
        self.values = dict(self.axes)
        self.layout = layout_of(self.ranges, ())
        self.t0 = time.monotonic()

    def read(self, timeout: float) -> list[tuple[int, int, int]]:
        if not self.there():
            raise OSError("the simulated controller has gone")
        time.sleep(min(timeout, 0.05))
        t = time.monotonic() - self.t0
        events = []
        for code, value in (
            (ABS_GAS, 127 * (1 - math.cos(t / 2))),
            (ABS_RX, 128 - 60 * math.sin(t / 3)),
        ):
            if round(value) != self.axes[code]:
                self.axes[code] = round(value)
                events.append((EV_ABS, code, round(value)))
        return events

    def close(self) -> None:
        pass


class PadManager:
    """Reads the controller on one thread and tells diagd on another, for as long
    as the console runs. diagd is only spoken to while a controller is there."""

    def __init__(self, find=find_evdev_pad, connect=None):
        self.find = find
        self.connect = connect or (
            lambda: diag_client.Robot(name="game controller", streams=())
        )
        self.lock = threading.Lock()
        self.operator: Operator | None = None
        self.name: str | None = None
        self.error = ""
        self.robot = None
        self.taken: bool | None = None
        # Whether anything holds control, as diagd's status last said; None until it
        # has. The ride height, kept across controllers, and put back to the top of
        # its range whenever nothing holds control.
        self.armed: bool | None = None
        self.height = HEIGHT_RANGE_M[1]
        self.sent = None
        self.speed_limit = START_SPEED_M_S
        self.turn_limit = START_TURN_RAD_S
        # Select's and the jump button's presses, kept across controllers: what runs
        # the policy acts on the difference, so a count starting again at nothing
        # when a controller comes back would read as presses, a flipped speed mode or
        # up to 255 jumps.
        self.counts = (0, 0)
        self.rumble: Rumble | None = None
        # The policy's speed mode as the daemon last told it, None if it does not.
        self.fast: bool | None = None
        # Watching for a press to change it: until when, and from what.
        self.watch_until = 0.0
        self.watch_from: bool | None = None
        self.running = False
        self.threads: list[threading.Thread] = []

    def start(self) -> None:
        self.running = True
        for loop in (self.read_loop, self.send_loop):
            thread = threading.Thread(target=loop, daemon=True)
            thread.start()
            self.threads.append(thread)

    def close(self) -> None:
        self.running = False
        for thread in self.threads:
            thread.join(2)
        with self.lock:
            robot, self.robot = self.robot, None
        if robot:
            robot.close()

    def limits(self, message: dict) -> dict:
        """Sets what a stick's end asks for, inside the trained tops."""
        speed = float(message["speed"])
        turn = float(message["turn"])
        if not (0 <= speed <= TOP_SPEED_M_S and 0 <= turn <= TOP_TURN_RAD_S):
            raise ValueError(
                f"top speed runs to {TOP_SPEED_M_S} m/s and turn to "
                f"{TOP_TURN_RAD_S} rad/s, which is what the policy was trained on"
            )
        with self.lock:
            self.speed_limit, self.turn_limit = speed, turn
            if self.operator:
                self.operator.speed_limit = speed
                self.operator.turn_limit = turn
        return self.snapshot()

    def attach(self, pad, now: float) -> None:
        operator = Operator(pad.ranges, now, pad.layout, pad.values)
        with self.lock:
            operator.speed_limit = self.speed_limit
            operator.turn_limit = self.turn_limit
            operator.mode, operator.jump = self.counts
            operator.height = self.height
            self.operator, self.name, self.error = operator, pad.name, ""
            self.rumble = getattr(pad, "rumble", None)

    def detach(self) -> None:
        with self.lock:
            if self.operator:
                self.counts = (self.operator.mode, self.operator.jump)
                self.height = self.operator.height
            self.operator, self.name, self.rumble = None, None, None
            self.watch_until = 0.0

    def pressed(self, before: dict | None, command: dict | None, now: float) -> None:
        """Select pressed since the last frame: watch for the policy to answer it.
        Under the lock."""
        if before and command and command["mode"] != before["mode"]:
            self.watch_until, self.watch_from = now + MODE_WATCH_S, self.fast

    def answered(self, fast: bool | None, now: float) -> None:
        """The daemon's word on the speed mode, and the pulses if a press changed it."""
        with self.lock:
            watching = now < self.watch_until and self.watch_from is not None
            changed = fast is not None and fast != self.watch_from
            self.fast = fast
            rumble = self.rumble if watching and changed else None
            if watching and changed:
                self.watch_until = 0.0
        if rumble:
            rumble.pulses(2 if fast else 1)

    def control(self, status: dict) -> None:
        """diagd's status: with nothing holding control, the robot is disarmed, and
        the ride height goes back to the top."""
        holder = (status.get("status", status).get("pi") or {}).get("control")
        with self.lock:
            self.armed = bool(holder)
            if not holder:
                self.height = HEIGHT_RANGE_M[1]
                if self.operator:
                    self.operator.height = self.height

    def event(self, kind: int, code: int, value: int, now: float) -> None:
        with self.lock:
            if not self.operator:
                return
            self.operator.event(kind, code, value, now)

    def read_loop(self) -> None:
        while self.running:
            try:
                pad = self.find()
            except OSError as error:
                self.say(f"cannot read input devices: {error}")
                pad = None
            if pad is None:
                time.sleep(RESCAN_S)
                continue
            self.attach(pad, time.monotonic())
            try:
                while self.running:
                    for kind, code, value in pad.read(0.2):
                        self.event(kind, code, value, time.monotonic())
            except OSError:
                pass  # Linux has taken it away: switched off, or out of range
            finally:
                self.detach()
                pad.close()

    def say(self, text: str) -> None:
        with self.lock:
            self.error = text

    def send_loop(self) -> None:
        next_connect = next_ask = 0.0
        while self.running:
            time.sleep(1 / SEND_HZ)
            now = time.monotonic()
            with self.lock:
                command = self.operator.command(now) if self.operator else None
                # The controller gone: say so once, sooner than silence would.
                if command is None and self.sent is not None:
                    command = dict(self.sent, forward=0.0, turn=0.0, live=False)
                    self.sent = None
                else:
                    self.pressed(self.sent, command, now)
                    self.sent = command
                robot = self.robot
            if robot is not None and robot.error:
                robot.close()
                robot = None
                with self.lock:
                    self.robot = None
                    self.taken = None
            if command is None:
                continue
            if robot is None:
                if now < next_connect:
                    continue
                next_connect = now + RECONNECT_S
                try:
                    robot = self.connect()
                except diag_client.RobotError:
                    continue
                with self.lock:
                    self.robot = robot
                # Connecting can take a while, and this command was from before it.
                continue
            try:
                if now >= next_ask or now < self.watch_until:
                    due = now >= next_ask
                    next_ask = now + ASK_S
                    answer = robot.request("drive", wait=0.5, **command)
                    self.taken = answer["taken"]
                    # A daemon from before 6 November 2026 says nothing of it.
                    self.answered(answer.get("fast"), time.monotonic())
                    if due:
                        self.ask_control(robot)
                else:
                    robot.send("drive", **command)
            except diag_client.RobotError as error:
                # A daemon refusing it, as one shutting down does, is not a
                # broken connection, and the connection's own error says if it is.
                with self.lock:
                    self.taken = None
                    self.error = "" if robot.error else str(error)

    def ask_control(self, robot) -> None:
        """Whether anything holds control. A daemon with no status yet refuses, and
        that leaves the height as it is; a broken connection says so itself."""
        try:
            status = robot.request("status", wait=0.5)
        except diag_client.RobotError:
            with self.lock:
                self.armed = None
            return
        self.control(status)

    @staticmethod
    def held_names(operator: Operator) -> list[str]:
        """What is being held, by what it does here, and by Linux's code if it
        does nothing: which is how to see a controller's real layout."""
        layout = operator.layout
        roles = {layout.jump: "jump", layout.mode: "speed mode"}
        return sorted(roles.get(code, f"button {code:#x}") for code in operator.held)

    def snapshot(self) -> dict:
        with self.lock:
            now = time.monotonic()
            operator = self.operator
            return dict(
                name=self.name,
                error=self.error,
                command=self.sent,
                why_not=operator.why_not(now) if operator else "",
                held=self.held_names(operator) if operator else [],
                diagd=self.robot is not None and not self.robot.error,
                taken=self.taken,
                armed=self.armed,
                fast=self.fast,
                rumble=(self.rumble.why_not or "ready") if self.rumble else "",
                speed_limit=self.speed_limit,
                turn_limit=self.turn_limit,
                top_speed=TOP_SPEED_M_S,
                top_turn=TOP_TURN_RAD_S,
            )
