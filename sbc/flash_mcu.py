# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Flash the controller board from the Banana Pi, through the carrier's J5.

    sudo python3 flash_mcu.py serial_check.elf     # flash, start it, listen 5 s
    sudo python3 flash_mcu.py --listen 10          # restart what is there, listen
    sudo python3 flash_mcu.py --listen 0           # only restart it

The STM32's ROM bootloader does the writing. The Pi holds BOOT0 high, pulses
NRST, and talks to the bootloader over USART1 -- ST's AN3155 protocol at
115 200 baud, 8 data bits, EVEN parity -- then drops BOOT0, pulses NRST again,
and listens to what the new image says at 8N1. Nothing here needs installing:
GPIO goes through the kernel's character-device interface and the serial port
through termios.

Where the wires go is docs/CARRIER.md's "J5 at the Banana Pi", checked in
electrical/carrier.py: BOOT0 on header pin 7 (PI12), NRST on header pin 11
(PH2), the MCU's transmit on pin 10 (UART4 RX) and its receive on pin 8
(UART4 TX). NRST is only ever pulled low or let go, never driven high: the core
board's reset button and the MCU's own resets pull the same line down.

On the robot the Pi also holds the power on, on header pin 12 (PI1), the
power switch board's second hold input. The ROM bootloader holds nothing, and
the Pi's own supply comes through that switch, so without it an update cuts the
power to the Pi doing it. The hold goes up before anything else and comes down
last, once the MCU is running an image again and holding for itself. If the
flash fails after erasing, the MCU has nothing to run, so this keeps holding and
offers another try rather than letting the robot and the Pi go off.

Root, or a udev rule, for /dev/gpiochip*; and UART4 switched on with its pins,
which on Armbian takes its bananapi-m4-pi-13-14-uart4 overlay and our
uart4-fix.dts both. setup_flash.sh, beside this, does all of it once.

First run 2026-10-16: bootloader 3.1, product ID 0x469, serial_check's 14 232
bytes erased, written and read back, then its lines and its echo heard. On the
robot with the hold, 2026-10-18: the same, the Pi up throughout. The first try
that day had no answer from the bootloader on any attempt, and the next run
worked unchanged. Every try failed that way on 2026-11-04 until the wait for
the bootloader to start went from 0.1 s to 0.5 s (Control.reset), and even then
the first of the three attempts went unanswered and the second worked, so the
wait is not all of it.
"""

from __future__ import annotations

import argparse
import ctypes
import fcntl
import glob
import os
import select
import struct
import sys
import termios
import time
from pathlib import Path

# ---- the wiring --------------------------------------------------------------

# The H618's main pin controller, by its device-tree label: the /dev/gpiochip
# number it gets depends on probe order, and on this board it is 1, not 0.
PIN_CONTROLLER = "300b000.pinctrl"


def line_of(pin: str) -> int:
    """A sunxi pin name to its line on PIN_CONTROLLER: 32 lines a bank."""
    return (ord(pin[1]) - ord("A")) * 32 + int(pin[2:])


BOOT0 = line_of("PI12")  # header pin 7
NRST = line_of("PH2")  # header pin 11
# electrical/carrier.py's SBC_HOLD_HEADER: the power switch board's J2-4.
SBC_HOLD = line_of("PI1")  # header pin 12

# UART4 is at this address in the H618; its tty is found by it, not assumed.
UART4 = "5001000.serial"

# ---- the flash ---------------------------------------------------------------

FLASH = 0x0800_0000
FLASH_SIZE = 512 * 1024
# Dual-bank, as the board's option bytes came (firmware/Cargo.toml): 2 KB pages,
# bank 1 the first 256 KB. Were the part single-bank its pages are 4 KB, and
# erasing pages 0..n by this size still covers the image, twice over.
PAGE = 2048
BANK1 = 256 * 1024
# The G47x/G48x's product ID, as the bootloader's Get ID returns it.
G474_PID = 0x469


# ---- GPIO, through the kernel's v2 character-device interface ---------------
#
# linux/gpio.h, by hand: the struct sizes are asserted below, since a layout that
# is wrong by a word is an ioctl the kernel rejects or, worse, misreads.

LINE_FLAG_INPUT = 1 << 2
LINE_FLAG_OUTPUT = 1 << 3
LINE_FLAG_OPEN_DRAIN = 1 << 6
ATTR_ID_OUTPUT_VALUES = 2


class ChipInfo(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * 32),
        ("label", ctypes.c_char * 32),
        ("lines", ctypes.c_uint32),
    ]


class LineAttribute(ctypes.Structure):
    # The union of flags, values and debounce period is one u64.
    _fields_ = [
        ("id", ctypes.c_uint32),
        ("padding", ctypes.c_uint32),
        ("value", ctypes.c_uint64),
    ]


class LineConfigAttribute(ctypes.Structure):
    _fields_ = [("attr", LineAttribute), ("mask", ctypes.c_uint64)]


class LineConfig(ctypes.Structure):
    _fields_ = [
        ("flags", ctypes.c_uint64),
        ("num_attrs", ctypes.c_uint32),
        ("padding", ctypes.c_uint32 * 5),
        ("attrs", LineConfigAttribute * 10),
    ]


class LineRequest(ctypes.Structure):
    _fields_ = [
        ("offsets", ctypes.c_uint32 * 64),
        ("consumer", ctypes.c_char * 32),
        ("config", LineConfig),
        ("num_lines", ctypes.c_uint32),
        ("event_buffer_size", ctypes.c_uint32),
        ("padding", ctypes.c_uint32 * 5),
        ("fd", ctypes.c_int32),
    ]


class LineValues(ctypes.Structure):
    _fields_ = [("bits", ctypes.c_uint64), ("mask", ctypes.c_uint64)]


assert ctypes.sizeof(ChipInfo) == 68
assert ctypes.sizeof(LineConfig) == 272
assert ctypes.sizeof(LineRequest) == 592
assert ctypes.sizeof(LineValues) == 16


def _ioc(direction: int, nr: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (0xB4 << 8) | nr


GET_CHIPINFO = _ioc(2, 0x01, ctypes.sizeof(ChipInfo))
GET_LINE = _ioc(3, 0x07, ctypes.sizeof(LineRequest))
SET_CONFIG = _ioc(3, 0x0D, ctypes.sizeof(LineConfig))
SET_VALUES = _ioc(3, 0x0F, ctypes.sizeof(LineValues))


def open_controller() -> int:
    """The /dev/gpiochip that is PIN_CONTROLLER, opened."""
    for path in sorted(glob.glob("/dev/gpiochip*")):
        try:
            fd = os.open(path, os.O_RDWR | os.O_CLOEXEC)
        except PermissionError:
            sys.exit(
                f"{path}: permission denied. Run with sudo, or give your user "
                "the GPIO chips with a udev rule."
            )
        info = ChipInfo()
        fcntl.ioctl(fd, GET_CHIPINFO, info)
        if info.label.decode() == PIN_CONTROLLER:
            return fd
        os.close(fd)
    sys.exit(f"no GPIO chip labelled {PIN_CONTROLLER}")


class Line:
    """One GPIO line, held for as long as the object is open."""

    def __init__(self, chip: int, offset: int, value: int, open_drain: bool):
        request = LineRequest()
        request.offsets[0] = offset
        request.num_lines = 1
        request.consumer = b"flash_mcu"
        flags = LINE_FLAG_OUTPUT
        if open_drain:
            # The kernel emulates it: 1 makes the line an input, 0 drives it low.
            flags |= LINE_FLAG_OPEN_DRAIN
        request.config.flags = flags
        request.config.num_attrs = 1
        request.config.attrs[0].attr.id = ATTR_ID_OUTPUT_VALUES
        request.config.attrs[0].attr.value = value
        request.config.attrs[0].mask = 1
        try:
            fcntl.ioctl(chip, GET_LINE, request)
        except OSError as error:
            sys.exit(
                f"GPIO line {offset}: {error.strerror}; is something else using it?"
            )
        self.fd = request.fd

    def set(self, value: int) -> None:
        fcntl.ioctl(self.fd, SET_VALUES, LineValues(value, 1))

    def release(self) -> None:
        """Back to an input, so the line is let go when the request closes,
        whatever the kernel would otherwise leave it as."""
        config = LineConfig()
        config.flags = LINE_FLAG_INPUT
        fcntl.ioctl(self.fd, SET_CONFIG, config)
        os.close(self.fd)


class Control:
    """BOOT0, NRST and the SBC's hold, all let go when this closes: the hold
    last, and only once the MCU is out of its bootloader."""

    def __enter__(self) -> Control:
        self.chip = open_controller()
        # The hold first: once the MCU is reset nothing else holds the power.
        self.hold = Line(self.chip, SBC_HOLD, 1, open_drain=False)
        self.boot0 = Line(self.chip, BOOT0, 0, open_drain=False)
        self.nrst = Line(self.chip, NRST, 1, open_drain=True)
        self.in_bootloader = False
        # Between an erase and a verified write the MCU has nothing to run.
        self.erased = False
        return self

    def reset(self, bootloader: bool) -> None:
        """Reset the MCU with BOOT0 high for its ROM bootloader, or low for
        the image in flash. BOOT0 is sampled as NRST rises."""
        self.boot0.set(1 if bootloader else 0)
        time.sleep(0.005)
        self.nrst.set(0)
        time.sleep(0.02)
        self.nrst.set(1)
        # The MCU's internal pull-up has the board's 100 nF to charge, a few
        # milliseconds, and the bootloader then wants a moment to start: more
        # than 0.1 s, as on 2026-11-04 it missed every 0x7F sent that soon, and
        # answered the first one at 0.5 s. An image raises its own hold at once.
        time.sleep(0.5 if bootloader else 0.1)
        if not bootloader:
            self.boot0.set(0)
        self.in_bootloader = bootloader

    def __exit__(self, *exc) -> None:
        try:
            # Never left in the bootloader, which holds nothing. An image
            # raises its own hold in its first instructions, and reset() waits
            # 0.1 s after starting it, so the power is held throughout.
            if self.in_bootloader:
                self.reset(bootloader=False)
        finally:
            # The board's own 10 kOhm holds BOOT0 low once it is let go, and
            # the power board's R17 holds the hold off.
            self.nrst.release()
            self.boot0.release()
            self.hold.release()
            os.close(self.chip)


# ---- the serial port ---------------------------------------------------------


def uart4() -> str:
    for tty in sorted(glob.glob("/sys/class/tty/ttyS*")):
        if UART4 in os.path.realpath(f"{tty}/device"):
            return f"/dev/{Path(tty).name}"
    sys.exit("UART4 is not switched on: run setup_flash.sh once, with sudo.")


class Port:
    def __init__(self, path: str, baud: int = 115200):
        self.path = path
        self.baud = baud
        # Opened without waiting for a carrier, which this port has no line for,
        # then told to ignore it and made blocking again.
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK | os.O_CLOEXEC)
        # Two programs reading one port each get some of its bytes, and neither
        # makes sense of them; diagd.py holds it for as long as it runs.
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.fd)
            sys.exit(
                f"{path} is in use by another program: diagd.py, flash_mcu.py or "
                "wheel_check.py. Stop it first."
            )
        self.configure(parity=False)
        flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)

    def configure(self, parity: bool) -> None:
        """8 bits, raw, at the port's rate: 115 200 unless it was opened at
        another. Even parity for the bootloader, none for the firmware."""
        attrs = termios.tcgetattr(self.fd)
        attrs[0] = 0  # iflag
        attrs[1] = 0  # oflag
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        if parity:
            attrs[2] |= termios.PARENB
        attrs[3] = 0  # lflag
        attrs[4] = attrs[5] = getattr(termios, f"B{self.baud}")
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        self.flush()

    def flush(self) -> None:
        termios.tcflush(self.fd, termios.TCIOFLUSH)

    def write(self, data: bytes, drain: bool = True) -> None:
        """Writes all of data, and with drain waits until it has left: the
        bootloader's handshake wants that, and a stream of messages does not,
        since the wait can be a whole scheduler tick."""
        view = memoryview(data)
        while view:
            view = view[os.write(self.fd, view) :]
        if drain:
            termios.tcdrain(self.fd)

    def read(self, n: int, timeout: float) -> bytes:
        """Up to n bytes, waiting at most timeout for all of them."""
        data = b""
        end = time.monotonic() + timeout
        while len(data) < n:
            left = end - time.monotonic()
            if left <= 0 or not select.select([self.fd], [], [], left)[0]:
                break
            data += os.read(self.fd, n - len(data))
        return data

    def close(self) -> None:
        os.close(self.fd)


# ---- ST's bootloader, AN3155 -------------------------------------------------

ACK = 0x79
NACK = 0x1F


class BootloaderError(RuntimeError):
    pass


def xor(data: bytes) -> int:
    out = 0
    for b in data:
        out ^= b
    return out


class Bootloader:
    def __init__(self, port: Port):
        self.port = port

    def ack(self, what: str, timeout: float = 1.0) -> None:
        reply = self.port.read(1, timeout)
        if reply != bytes([ACK]):
            heard = reply.hex() if reply else "nothing"
            raise BootloaderError(f"{what}: wanted ACK, heard {heard}")

    def byte(self, what: str) -> int:
        reply = self.port.read(1, 1.0)
        if not reply:
            raise BootloaderError(f"{what}: the bootloader stopped answering")
        return reply[0]

    def sync(self) -> None:
        self.port.flush()
        self.port.write(b"\x7f")
        reply = self.port.read(1, 0.5)
        if reply == bytes([ACK]):
            return
        if reply == bytes([NACK]):
            return  # already synchronised: it took 0x7F for a command
        heard = reply.hex() if reply else "nothing"
        raise BootloaderError(
            f"no bootloader on {self.port.path}: sent 0x7F, heard {heard}"
        )

    def command(self, code: int) -> None:
        self.port.write(bytes([code, code ^ 0xFF]))
        self.ack(f"command {code:#04x}")

    def address(self, address: int) -> None:
        raw = address.to_bytes(4, "big")
        self.port.write(raw + bytes([xor(raw)]))
        self.ack(f"address {address:#010x}")

    def get(self) -> tuple[int, bytes]:
        self.command(0x00)
        n = self.byte("Get")
        body = self.port.read(n + 1, 1.0)
        self.ack("Get")
        return body[0], body[1:]

    def get_id(self) -> int:
        self.command(0x02)
        n = self.byte("Get ID")
        pid = self.port.read(n + 1, 1.0)
        self.ack("Get ID")
        return int.from_bytes(pid, "big")

    def erase(self, pages: list[int]) -> None:
        self.command(0x44)
        body = (len(pages) - 1).to_bytes(2, "big")
        body += b"".join(page.to_bytes(2, "big") for page in pages)
        self.port.write(body + bytes([xor(body)]))
        self.ack("Extended Erase", timeout=10.0)

    def write(self, address: int, data: bytes) -> None:
        self.command(0x31)
        self.address(address)
        body = bytes([len(data) - 1]) + data
        self.port.write(body + bytes([xor(body)]))
        self.ack(f"Write Memory at {address:#010x}")

    def read(self, address: int, n: int) -> bytes:
        self.command(0x11)
        self.address(address)
        self.port.write(bytes([n - 1, (n - 1) ^ 0xFF]))
        self.ack("Read Memory length")
        return self.port.read(n, 1.0)


# ---- the image ---------------------------------------------------------------


def load_elf(path: Path) -> tuple[int, bytes]:
    """The flash image an ELF describes: every loadable segment at its load
    address, gaps filled with erased flash, as one run from its start."""
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        sys.exit(f"{path}: not a 32-bit little-endian ELF")
    phoff = struct.unpack_from("<I", data, 28)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 42)
    segments = []
    for i in range(phnum):
        kind, offset, _, paddr, filesz = struct.unpack_from(
            "<5I", data, phoff + i * phentsize
        )
        if kind == 1 and filesz and FLASH <= paddr < FLASH + FLASH_SIZE:
            segments.append((paddr, data[offset : offset + filesz]))
    if not segments:
        sys.exit(f"{path}: nothing in it loads into flash")
    start = min(a for a, _ in segments)
    end = max(a + len(d) for a, d in segments)
    image = bytearray(b"\xff" * (end - start))
    for address, chunk in segments:
        image[address - start : address - start + len(chunk)] = chunk
    return start, bytes(image)


def flash(control: Control, port: Port, start: int, image: bytes) -> None:
    # Flash is programmed 64 bits at a time, so the image goes in whole
    # double words.
    image += b"\xff" * (-len(image) % 8)
    if start != FLASH or start + len(image) > FLASH + BANK1:
        sys.exit("this writes images that start at 0x08000000 and fit in bank 1")

    port.configure(parity=True)
    control.reset(bootloader=True)
    boot = Bootloader(port)
    boot.sync()
    version, commands = boot.get()
    pid = boot.get_id()
    print(f"bootloader {version >> 4}.{version & 15}, product ID {pid:#05x}")
    if pid != G474_PID:
        sys.exit(f"expected the G474's {G474_PID:#05x}; stopping")
    if 0x44 not in commands:
        sys.exit("this bootloader has no Extended Erase")

    pages = list(range((len(image) + PAGE - 1) // PAGE))
    control.erased = True
    boot.erase(pages)
    print(f"erased {len(pages)} page(s)")

    for offset in range(0, len(image), 256):
        boot.write(start + offset, image[offset : offset + 256])
    print(f"wrote {len(image)} bytes at {start:#010x}")

    for offset in range(0, len(image), 256):
        chunk = image[offset : offset + 256]
        if boot.read(start + offset, len(chunk)) != chunk:
            raise BootloaderError(f"verify failed at {start + offset:#010x}")
    control.erased = False
    print("read back and verified")


ATTEMPTS = 3

STRANDED = """
The controller's flash is erased and not written back, so it has nothing to
run, and nothing will hold the power once this lets go of it: the robot, and
this Pi, turn off about a second later. Holding it on.

Press Enter to try again. To give up instead, hold the robot's power button
down, press Ctrl-C, and keep the button down until this Pi has shut down
(sudo poweroff)."""


def flash_until_written(control: Control, port: Port, start: int, image: bytes) -> None:
    """flash(), tried again while it fails. Given up only if nothing was
    erased, since an MCU with no image left cannot hold the power."""
    while True:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                flash(control, port, start, image)
                return
            except BootloaderError as error:
                print(f"attempt {attempt} of {ATTEMPTS}: {error}")
            except KeyboardInterrupt:
                if not control.erased:
                    raise
                print("interrupted")
                break
        if not control.erased:
            raise BootloaderError("gave up before erasing; the old image is intact")
        print(STRANDED, file=sys.stderr)
        try:
            input()
        except EOFError:
            raise BootloaderError("no one to ask; letting go") from None


def listen(control: Control, port: Port, seconds: float) -> None:
    """Start the image in flash and print what it sends. Halfway through, send
    a probe line and say whether it came back: serial_check echoes."""
    port.configure(parity=False)
    control.reset(bootloader=False)
    print(f"--- {port.path} at 115200 8N1, {seconds:g} s ---")
    end = time.monotonic() + seconds
    probe = b"echo-check"
    pending = after = b""
    sent = False
    while time.monotonic() < end:
        chunk = port.read(256, 0.1)
        pending += chunk
        if sent:
            after += chunk
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            print(line.decode(errors="replace").rstrip())
        if not sent and time.monotonic() > end - seconds / 2:
            port.write(probe + b"\r\n")
            sent = True
    print("---")
    print("echo: heard" if probe in after else "echo: NOT heard")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "image", nargs="?", type=Path, help="an ELF to flash; without one, restart"
    )
    ap.add_argument(
        "--listen",
        type=float,
        default=5.0,
        help="seconds to listen once it starts; 0 to only start it (default 5)",
    )
    args = ap.parse_args()

    image = load_elf(args.image) if args.image else None
    port = Port(uart4())
    try:
        with Control() as control:
            if image:
                flash_until_written(control, port, *image)
            if args.listen > 0:
                listen(control, port, args.listen)
            else:
                control.reset(bootloader=False)
                print("started")
    except BootloaderError as error:
        sys.exit(str(error))
    except KeyboardInterrupt:
        sys.exit("interrupted")
    finally:
        port.close()


if __name__ == "__main__":
    main()
