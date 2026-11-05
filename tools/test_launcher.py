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
    check("a press is not a tap yet", not a.heard({"button": True}, 10.0))
    check("nor is holding it", not a.heard({"button": True}, 10.1))
    check("up again soon is a tap", a.heard({"button": False}, 10.2))
    check("up and staying up is nothing more", not a.heard({"button": False}, 10.3))
    a.heard({"button": True}, 20.0)
    check("held too long is not", not a.heard({"button": False}, 20.5))
    a.heard({"button": True}, 30.0)
    a.heard({"button": True, "off": True}, 30.1)
    check("turning the robot off is not", not a.heard({"button": False}, 30.2))


def wait_for(log: Path, text: str, seconds: float = 8.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if log.exists() and text in log.read_text():
            return True
        time.sleep(0.05)
    return False


def against_diagd() -> None:
    """A stand-in for balance.py that sleeps, since this is about what starts it. The
    simulated robot has no button, so the taps go straight to what status would call."""
    tmp = Path(tempfile.mkdtemp())
    log = tmp / "launcher.log"
    port = "127.0.0.1:18765"
    sleeper = [sys.executable, "-c", "import time; time.sleep(4)"]
    daemon = subprocess.Popen(
        ["uv", "run", "sbc/diagd.py", "--sim", "--listen", port],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(4)
    it = launcher.Launcher(SimpleNamespace(robot=port, log=log), sleeper)
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
        check("another stops it", wait_for(log, "asked for it to stop"))
        check("it notices the end", wait_for(log, "it ended, with exit code"))
        tap()
        check("too soon after is ignored", wait_for(log, "too soon"))
        time.sleep(launcher.QUIET_S)
        tap()
        check("then it starts again", log.read_text().count("the button asked:") == 2)
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
against_diagd()
print("FAILED: " + ", ".join(failed) if failed else "passed")
raise SystemExit(1 if failed else 0)
