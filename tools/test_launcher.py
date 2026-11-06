# /// script
# requires-python = ">=3.11"
# dependencies = ["pyserial>=3.5"]
# ///
"""sbc/launcher.py, by its rules and then against the simulated diagd. Free, offline, and
touches no robot: the only one it speaks to is on this computer.

    uv run tools/test_launcher.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbc"))

import launcher  # noqa: E402

failed = []


def check(name: str, good: bool) -> None:
    print(f"{'ok    ' if good else 'FAILED'} {name}")
    if not good:
        failed.append(name)


def rules() -> None:
    a = launcher.Tap()
    check("a press is not a tap yet", not a.heard({"button": True}))
    check("nor is holding it", not a.heard({"button": True}))
    check("up again is a tap", a.heard({"button": False}))
    check("up and staying up is nothing more", not a.heard({"button": False}))
    for _ in range(19):
        a.heard({"button": True})
    check("held just short of off is still a tap", a.heard({"button": False}))
    a.heard({"button": True})
    a.heard({"button": True, "off": True})
    check("turning the robot off is not", not a.heard({"button": False}))


def ending() -> None:
    """A run saving its log takes a moment after it is told to stop, which the stand-in
    against diagd, killed outright on Windows, does not."""

    class Child:
        code = None
        returncode = 0

        def poll(self):
            return self.code

        def terminate(self):
            pass

        def kill(self):
            self.killed = True

    with tempfile.TemporaryDirectory() as folder:
        tmp = Path(folder)
        it = launcher.Launcher(
            SimpleNamespace(robot="", log=tmp / "log", phase_file=tmp / "phase"), []
        )
        started = []
        it.start = lambda: started.append(True)
        it.warm = lambda: Child()
        it.spare_at = time.monotonic()
        child = it.child = Child()
        it.stopping_at = time.monotonic()
        it.asked(None)
        check("a tap while it ends arms it after", it.again and not started)
        it.asked(None)
        check("and another takes that back", not it.again)
        it.asked(None)
        child.code = 0
        it.watch_child()
        check("once it has gone, it does", bool(started) and not it.again)
        it.child = child = Child()
        it.stopping_at = time.monotonic() - launcher.ENDING_S - 1
        it.watch_child()
        check("one that will not go is killed", getattr(child, "killed", False))
        it.out.close()


def wait_until(good, seconds: float = 8.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if good():
            return True
        time.sleep(0.05)
    return False


def phase_is(path: Path, text: str) -> bool:
    return wait_until(lambda: path.exists() and path.read_text().strip() == text)


def wait_for(log: Path, text: str, seconds: float = 8.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if log.exists() and text in log.read_text():
            return True
        time.sleep(0.05)
    return False


def against_diagd() -> None:
    """A stand-in for balance.py that waits for the word and sleeps, since this is about
    what starts it. The simulated robot has no button, so the taps go straight to what
    status would call."""
    tmp = Path(tempfile.mkdtemp())
    log = tmp / "launcher.log"
    phase_file = tmp / "phase"
    woke = tmp / "woke"
    port = "127.0.0.1:18765"
    standin = tmp / "standin.py"
    standin.write_text(
        "import sys, time, threading\n"
        "from pathlib import Path\n"
        "if not sys.stdin.readline(): raise SystemExit\n"
        f"phase, woke = Path({str(phase_file)!r}), Path({str(woke)!r})\n"
        "time.sleep(0.5)\n"
        "phase.write_text('limp')\n"
        "def hear():\n"
        "    for line in sys.stdin:\n"
        "        if line.strip() == 'wake':\n"
        "            woke.write_text('yes')\n"
        "            phase.write_text('ease')\n"
        "threading.Thread(target=hear, daemon=True).start()\n"
        "time.sleep(60)\n"
    )
    sleeper = [sys.executable, str(standin)]
    daemon = subprocess.Popen(
        ["uv", "run", "sbc/diagd.py", "--sim", "--listen", port],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(4)
    it = launcher.Launcher(
        SimpleNamespace(robot=port, log=log, phase_file=phase_file), sleeper
    )
    thread = threading.Thread(target=it.run)
    thread.start()

    def tap() -> None:
        it._status({"button": True})
        time.sleep(0.05)
        it._status({"button": False})
        time.sleep(0.2)

    try:
        check("it finds diagd", wait_for(log, "connected to diagd"))
        time.sleep(0.3)
        check("nothing starts it unasked", "asked" not in log.read_text())
        tap()
        check("a tap does", wait_for(log, "the button asked:"))
        tap()
        check("one while it starts leaves it to", wait_for(log, "while it starts"))
        check("and does not stop it", "asked for it to stop" not in log.read_text())
        check(
            "it gets to limp", wait_for(log, "x", 0.0) or phase_is(phase_file, "limp")
        )
        tap()
        check("one while it is limp wakes it", wait_for(log, "waking it"))
        check("and it heard", phase_is(woke, "yes"))
        tap()
        check("one once it is awake stops it", wait_for(log, "asked for it to stop"))
        check("it notices the end", wait_for(log, "it ended, with exit code"))
        tap()
        check(
            "and the next starts it again at once",
            wait_until(lambda: log.read_text().count("the button asked:") == 2),
        )
        check("it has gone to limp again", phase_is(phase_file, "limp"))
        tap()
        check(
            "waking it again",
            wait_until(lambda: log.read_text().count("waking it") == 2),
        )
        tap()
        check(
            "stopping it again",
            wait_until(lambda: log.read_text().count("asked for it to stop") == 2),
        )
        check(
            "it ends with nothing to come",
            wait_until(lambda: log.read_text().count("it ended") == 2),
        )
        tap()
        check(
            "and no wait before the next",
            wait_until(lambda: log.read_text().count("the button asked:") == 3),
        )
        if it.child is not None:
            real = it.child
            before = log.read_text().count("it ended")

            class Lost:
                def stop(self):
                    raise launcher.diag_client.RobotError("gone")

            phase_is(phase_file, "limp")
            phase_file.write_text("policy")
            try:
                it.stop(Lost())
            except launcher.diag_client.RobotError:
                pass
            check(
                "losing diagd as it stops still ends it",
                wait_until(lambda: real.poll() is not None),
            )
            check(
                "and it knows",
                wait_until(lambda: log.read_text().count("it ended") == before + 1),
            )
    finally:
        it.running = False
        thread.join(20)
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(daemon.pid)]
            if sys.platform == "win32"
            else ["kill", str(daemon.pid)],
            capture_output=True,
        )
    check("it says it stopped", wait_for(log, "stopped", 1.0))
    print(log.read_text())


rules()
ending()
against_diagd()
print("FAILED: " + ", ".join(failed) if failed else "passed")
raise SystemExit(1 if failed else 0)
