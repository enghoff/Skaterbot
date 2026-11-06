"""Finding, pairing and forgetting game controllers, for the console.

Everything goes through bluetoothctl, as the account the console runs as: BlueZ
lets the `bluetooth` group do all of this, so unlike Wi-Fi it wants no helper
running as root. Almost everything is one command to a process, and a bluetoothctl
given a command registers no pairing agent. Pairing needs one, even though nobody
is asked anything. A real Xbox controller's "just works" pairing reaches a
confirmation, BlueZ wants an agent to put it to, and with none it tells the
controller the comparison failed, which comes back as AuthenticationFailed
(on the robot, 2026-11-04; bluetoothd logs "No agent available for request type
2"). With an agent there BlueZ accepts for itself, since this client asked for the
pairing. So pairing alone keeps a bluetoothctl open over a pipe, as its default
agent, claiming no keyboard or display: a device wanting a PIN typed does not pair.
Pairing also opens the adapter for its own length and shuts it again: left open,
anything nearby could bond with the robot.

A device found by a scan is forgotten by BlueZ about 30 s after the scan ends,
while a controller stays in pairing mode for longer, so a scan runs through the
whole of a pairing and BlueZ goes on knowing the controller between tries.

There are tries because most of them fail, and why is not known. The link is made, no
packet from the controller reaches the host on it, and after six connection events,
0.33 s at the 48.75 ms a link starts with, it ends with "Connection Failed to be
Established": 160 of 168 traced attempts on the robot, 2026-11-04 and 05 (`sudo btmon
-T`). An Xbox controller in pairing mode sends Microsoft's Swift Pair beacon three times
in four and the HID service every 136 ms, and attempts worked after 4 of 114 and 4 of 54
of them, too few to say either matters. So pairing is a matter of trying until one
lands, at 0.7 s each: it has taken 1, 2, 9, 10, 14, 23, about 22 and 63 tries.

A link is not a controller. BlueZ makes the input device only once it has read the
controller's report map, so `Connected: yes` comes first, and for good if the controller
hangs up before then. That is what happens to 40:8E:2C:42:E2:45, a 045E:0B13. It publishes preferred
connection parameters of 332.5 to 500 ms, BlueZ's GAP plugin loads them, this kernel
applies that to the live link, and each request takes about a second at 498.75 ms. It
ended the link itself 14 s after pairing with the report map unread (2026-11-05, one
trace; why it ends the link is not known). 045E:0B20 and C0:D6:D5:EF:99:F0, the other
045E:0B13, publish 7.5 ms and are done in about a second. So here `ready` is the kernel
having an input device for that address.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from pathlib import Path

# Long enough to pick up a controller and put it into pairing mode. Choosing one
# to pair ends the scan, so nobody waits this out.
SCAN_S = 20
# The most a scan's results are looked into, each one a process on a small board.
MOST_DEVICES = 24
FIND_AGAIN_S = 10
LOOK_EVERY_S = 1
PAIR_S = 30
AGENT_S = 8
# Most tries at an Xbox controller fail, for the reason at the top of this file, and
# the next may work. Pairing mode was still running 35 s in, when it was last measured.
TRY_FOR_S = 60
TRY_AGAIN_S = 0.2
TRY_AGAIN = ("ConnectionAttemptFailed", "AuthenticationCanceled", "not available")
CONNECT_S = 15
# How long a process gets to end when asked, before it is made to.
STOP_S = 3
INPUT_DEVICES = Path("/proc/bus/input/devices")
# A pairing can lose its link at once: on the robot, 2026-11-05, 0.4 s after the keys
# were exchanged and before BlueZ had read the controller's services, under the 420 ms
# link timeout a link starts with. Connecting again is the same lottery as pairing, and
# until it has worked BlueZ does not know this is a controller and will not reconnect
# to it by itself.
CONNECT_FOR_S = 30
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x01|\x02")
ADDRESS = re.compile(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}")
DEVICE_LINE = re.compile(rf"^Device ({ADDRESS.pattern}) (.*)$", re.MULTILINE)
# A device with no name is listed under its address, with dashes. Most of what a scan
# hears is like this and of no interest, but not all: a newer Xbox controller in pairing
# mode advertises that it is a gamepad and gives no name (C0:D6:D5:EF:99:F0, on the
# robot, 2026-11-05).
NAMELESS = re.compile(r"[0-9A-F]{2}(?:-[0-9A-F]{2}){5}")
# How bluetoothctl says a step did not work.
WENT_WRONG = re.compile(r"Failed to|not available|No default controller")


async def stop(process) -> None:
    """Ends a process, by asking and then by not asking, and collects it."""
    with contextlib.suppress(ProcessLookupError):
        process.terminate()
    try:
        await asyncio.wait_for(process.communicate(), STOP_S)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        await process.communicate()


class Agent:
    """A bluetoothctl kept open over a pipe, where it takes commands as it would at its
    prompt. Its agent, which is what lets a pairing through, goes when it does."""

    def __init__(self, process):
        self.process = process
        self.failed = ""

    async def until(self, done: str) -> str:
        while line := await self.process.stdout.readline():
            text = ANSI.sub("", line.decode(errors="replace")).strip()
            if done in text:
                return ""
            if WENT_WRONG.search(text):
                return text.rpartition("org.bluez.Error.")[2]
        return "bluetoothctl stopped"

    async def say(self, command: str, done: str) -> str:
        self.process.stdin.write(f"{command}\n".encode())
        return await self.until(done)

    async def start(self, timeout: float) -> None:
        try:
            async with asyncio.timeout(timeout):
                self.failed = await self.until("Agent registered") or await self.say(
                    "default-agent", "Default agent request successful"
                )
        except TimeoutError:
            self.failed = "no answer"

    async def pair(self, address: str, timeout: float) -> str:
        """One try. Returns what went wrong, or "" if nothing did."""
        if self.failed:
            return self.failed
        async with asyncio.timeout(timeout):
            return await self.say(f"pair {address}", "Pairing successful")


class Tool:
    """bluetoothctl itself. Each method a process; tests replace this class."""

    @staticmethod
    async def start(*args: str):
        return await asyncio.create_subprocess_exec(
            "bluetoothctl",
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

    async def run(self, *args: str, timeout: float = 8) -> tuple[int, str]:
        process = await self.start(*args)
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout)
        except (TimeoutError, asyncio.CancelledError):
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            raise
        return process.returncode, ANSI.sub("", output.decode(errors="replace"))

    @contextlib.asynccontextmanager
    async def agent(self):
        """An Agent standing by for as long as the block runs."""
        process = await asyncio.create_subprocess_exec(
            "bluetoothctl",
            "--agent",
            "NoInputNoOutput",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            agent = Agent(process)
            await agent.start(AGENT_S)
            yield agent
        finally:
            await stop(process)

    @staticmethod
    def has_input(address: str) -> bool:
        """True once the kernel has an input device for this Bluetooth address."""
        try:
            lines = INPUT_DEVICES.read_text().splitlines()
        except OSError:
            return False
        return f"U: Uniq={address.lower()}" in lines

    async def scan(self, seconds: float):
        """Scans in the background for `seconds`. Returns what finish() takes. Nothing
        reads what it prints, and a full pipe would stop it before its timeout."""
        return await asyncio.create_subprocess_exec(
            "bluetoothctl",
            "--timeout",
            str(seconds),
            "scan",
            "on",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

    @staticmethod
    async def wait(scan, timeout: float) -> bool:
        """True once the scan has ended by itself."""
        try:
            await asyncio.wait_for(scan.wait(), timeout)
        except TimeoutError:
            return False
        return True

    @staticmethod
    def failed(scan) -> bool:
        """True if a scan that has ended did so with an error."""
        return scan.returncode not in (0, None)

    @staticmethod
    async def finish(scan) -> None:
        await stop(scan)


def controllers_first(device: dict) -> tuple[bool, str]:
    return (not device["gamepad"], device["name"].lower())


def fields(text: str) -> dict[str, str]:
    """`Key: value` lines, the first of each key (a device has many a UUID)."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        key, colon, value = line.strip().partition(": ")
        if colon:
            found.setdefault(key, value.strip())
    return found


class BluetoothManager:
    """Jobs outlive the browser that started them, as Wi-Fi's do."""

    def __init__(self, tool=None):
        self.tool = tool or Tool()
        self.task = None
        # Whether the job running is only the page asking how things stand.
        self.polling = False
        # The controller the message on show says is connected.
        self.announced: str | None = None
        # What the last scan saw: BlueZ forgets it long before a person chooses.
        self.seen: dict[str, dict] = {}
        self.state = dict(
            busy=False,
            scanning=False,
            message="",
            error="",
            available=None,
            powered=False,
            paired=[],
            found=[],
        )

    async def run(self, *args: str, timeout: float = 8) -> tuple[int, str]:
        try:
            return await self.tool.run(*args, timeout=timeout)
        except FileNotFoundError:
            raise ValueError(
                "BlueZ is not installed: run install_console_bluetooth.sh"
            ) from None
        except TimeoutError:
            if args[0] in ("show", "devices", "power"):
                # It waits for bluetoothd for as long as it is let.
                raise ValueError("The Bluetooth service is not answering") from None
            raise ValueError(f"Bluetooth {args[0]} took too long") from None

    async def device(self, address: str, name: str | None = None) -> dict | None:
        code, text = await self.run("info", address)
        if code or "not available" in text:
            return None
        info = fields(text)
        gamepad = info.get("Icon") == "input-gaming"
        connected = info.get("Connected") == "yes"
        called = info.get("Name") or info.get("Alias") or name or address
        if gamepad and NAMELESS.fullmatch(called):
            called = f"Unnamed controller {address}"
        return dict(
            address=address,
            name=called,
            gamepad=gamepad,
            paired=info.get("Paired") == "yes",
            trusted=info.get("Trusted") == "yes",
            connected=connected,
            ready=connected and self.tool.has_input(address),
        )

    async def devices(self) -> list[dict]:
        _, text = await self.run("devices")
        # Only looking into one says whether a nameless device is a controller.
        listed = sorted(
            DEVICE_LINE.findall(text),
            key=lambda device: bool(NAMELESS.fullmatch(device[1].strip())),
        )[:MOST_DEVICES]
        found = await asyncio.gather(*(self.device(a, n) for a, n in listed))
        return [
            device
            for device in found
            if device and (device["paired"] or not NAMELESS.fullmatch(device["name"]))
        ]

    async def refresh(self) -> None:
        code, text = await self.run("show")
        adapter = fields(text)
        available = code == 0 and "Powered" in adapter
        self.state.update(available=available, powered=adapter.get("Powered") == "yes")
        if not available:
            self.state.update(paired=[], found=[])
            return
        devices = await self.devices()
        self.seen.update({d["address"]: d for d in devices if not d["paired"]})
        paired = [d for d in devices if d["paired"]]
        for device in paired:
            self.seen.pop(device["address"], None)
        self.state.update(
            paired=sorted(paired, key=controllers_first),
            found=sorted(self.seen.values(), key=controllers_first),
        )
        # A pairing's message is true until the controller goes.
        if self.announced and not any(
            d["address"] == self.announced and d["ready"] for d in paired
        ):
            self.announced = None
            self.state["message"] = ""

    async def power(self) -> None:
        code, text = await self.run("power", "on")
        if code:
            raise ValueError(
                "The Bluetooth adapter is switched off and would not come on: "
                "it may be blocked (rfkill unblock bluetooth)"
                if "Blocked" in text or "rfkill" in text
                else "The Bluetooth adapter would not switch on"
            )

    async def scan(self) -> None:
        await self.power()
        self.seen.clear()
        scan = await self.tool.scan(SCAN_S)
        try:
            # The list fills as the scan goes, so a controller shows when heard.
            while not await self.tool.wait(scan, 2):
                await self.refresh()
            if self.tool.failed(scan):
                raise ValueError("The scan stopped with an error")
        finally:
            await self.tool.finish(scan)
        await self.refresh()

    async def heard(self, address: str) -> None:
        """Returns once BlueZ knows of the device, which needs a scan running."""
        clock = asyncio.get_running_loop().time
        give_up = clock() + FIND_AGAIN_S
        while not await self.device(address):
            if clock() >= give_up:
                raise ValueError(
                    "That controller has gone: put it back in pairing mode and scan"
                )
            await asyncio.sleep(LOOK_EVERY_S)

    async def tries(self, agent, address: str) -> str:
        """Tries until one lands. Returns what the last one said went wrong."""
        scan = await self.tool.scan(FIND_AGAIN_S + TRY_FOR_S + PAIR_S)
        try:
            clock = asyncio.get_running_loop().time
            give_up = clock() + TRY_FOR_S
            while True:
                await self.heard(address)
                try:
                    reason = await agent.pair(address, PAIR_S)
                except TimeoutError:
                    return "no answer"
                if clock() >= give_up or not any(w in reason for w in TRY_AGAIN):
                    return reason
                await asyncio.sleep(TRY_AGAIN_S)
        finally:
            await self.tool.finish(scan)

    async def connects(self, address: str) -> bool:
        """Tries until the kernel has an input device for it. False if it never does."""
        clock = asyncio.get_running_loop().time
        give_up = clock() + CONNECT_FOR_S
        while True:
            device = await self.device(address)
            if not device or not device["paired"]:
                return False
            if device["ready"]:
                return True
            if clock() >= give_up:
                return False
            # Linked is BlueZ still reading it, which asking again does not hurry.
            if not device["connected"]:
                with contextlib.suppress(ValueError):
                    await self.run("connect", address, timeout=CONNECT_S)
            await asyncio.sleep(TRY_AGAIN_S)

    async def close_to_pairing(self) -> None:
        """Shuts the adapter again, or says that it did not shut."""
        with contextlib.suppress(ValueError):
            await self.run("pairable", "off")
        _, text = await self.run("show")
        if fields(text).get("Pairable") != "no":
            raise ValueError(
                "Bluetooth is still open to pairing, so anything nearby could bond "
                "with the robot: restart its Bluetooth service"
            )

    async def pair(self, address: str) -> None:
        await self.power()
        try:
            await self.run("pairable", "on")
            async with self.tool.agent() as agent:
                reason = await self.tries(agent, address)
                device = await self.device(address)
                if not device or not device["paired"]:
                    said = f" ({reason})" if reason else ""
                    raise ValueError(
                        f"Pairing failed{said}. "
                        "Is the controller still in pairing mode?"
                    )
                # Trusted is what lets it connect again by itself after this.
                await self.run("trust", address)
                device = await self.device(address)
                if not device or not device["trusted"]:
                    raise ValueError("Paired, but it would not take being trusted")
                if not await self.connects(address):
                    # It says to forget it, which needs it on the list to press.
                    await self.refresh()
                    raise ValueError(
                        "Paired, but it never finished connecting: "
                        "forget it and pair it again"
                    )
        finally:
            await self.close_to_pairing()
        await self.refresh()

    async def forget(self, address: str) -> None:
        await self.run("remove", address)
        self.seen.pop(address, None)
        if await self.device(address):
            raise ValueError("The controller would not be forgotten")
        await self.refresh()

    async def job(self, op: str, address: str | None) -> None:
        try:
            if op == "scan":
                await self.scan()
            elif op == "pair":
                await self.pair(address)
                name = next(
                    (
                        d["name"]
                        for d in self.state["paired"]
                        if d["address"] == address
                    ),
                    address,
                )
                self.announced = address
                message = f"{name} is paired and connected"
            elif op == "forget":
                await self.forget(address)
            else:
                await self.refresh()
            if op != "status":
                self.state.update(
                    error="",
                    message=message
                    if op == "pair"
                    else {
                        "scan": "Scan complete",
                        "forget": "Controller forgotten",
                    }[op],
                )
        except Exception as error:
            self.state.update(
                error=str(error) if isinstance(error, ValueError) else repr(error),
                message="",
            )
        finally:
            self.state.update(busy=False, scanning=False)
            self.polling = False

    async def action(self, message: dict) -> dict:
        op = message["op"].removeprefix("bluetooth.")
        if op not in ("status", "scan", "pair", "forget"):
            raise ValueError("Unknown Bluetooth action")
        address = message.get("address")
        if op in ("pair", "forget") and not (
            isinstance(address, str) and ADDRESS.fullmatch(address)
        ):
            raise ValueError("Choose a device")
        # A controller's pairing mode runs out, so a scan gives way to a pairing.
        if op == "pair" and self.state["scanning"]:
            self.state["scanning"] = False
            self.task.cancel()
            await asyncio.wait([self.task])
        # The page's own polling is no reason to refuse somebody's click.
        if op != "status" and self.polling:
            await asyncio.wait([self.task])
        # Polling during a job returns its progress without competing with it.
        if self.state["busy"]:
            if op != "status":
                raise ValueError("Another Bluetooth action is running")
        else:
            self.state.update(
                busy=True,
                scanning=op == "scan",
                message={
                    "scan": "Scanning. Put the controller in pairing mode now.",
                    "pair": "Pairing…",
                    "forget": "Forgetting…",
                    "status": self.state["message"],
                }[op],
            )
            self.polling = op == "status"
            self.task = asyncio.create_task(self.job(op, address))
            if op == "status":
                await asyncio.shield(self.task)
        return dict(self.state)


class SimulatedBluetooth(BluetoothManager):
    """For --sim: one controller to find, and something else that will not pair.
    `connected` tells a SimPad whether it is there."""

    CONTROLLER = "AA:BB:CC:00:00:01"
    SPEAKER = "AA:BB:CC:00:00:02"

    def __init__(self):
        super().__init__(tool=object())
        self.known = {
            self.CONTROLLER: "Simulated controller",
            self.SPEAKER: "Somebody's speaker",
        }
        self.paired_set: set[str] = set()
        self.heard = False

    @property
    def connected(self) -> bool:
        return self.CONTROLLER in self.paired_set

    def describe(self, address: str) -> dict:
        paired = address in self.paired_set
        return dict(
            address=address,
            name=self.known[address],
            gamepad=address == self.CONTROLLER,
            paired=paired,
            trusted=paired,
            connected=paired,
            ready=paired,
        )

    async def refresh(self) -> None:
        self.state.update(
            available=True,
            powered=True,
            paired=[self.describe(a) for a in sorted(self.paired_set)],
            found=[self.describe(a) for a in self.known if a not in self.paired_set]
            if self.heard
            else [],
        )

    async def scan(self) -> None:
        await asyncio.sleep(0.05)
        self.heard = True
        await self.refresh()

    async def pair(self, address: str) -> None:
        await asyncio.sleep(0.05)
        if address != self.CONTROLLER:
            raise ValueError("Pairing failed. Is the controller still in pairing mode?")
        self.paired_set.add(address)
        await self.refresh()

    async def forget(self, address: str) -> None:
        await asyncio.sleep(0.02)
        self.paired_set.discard(address)
        await self.refresh()
