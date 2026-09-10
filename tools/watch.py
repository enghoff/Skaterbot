# /// script
# requires-python = ">=3.11,<3.13"
# ///
"""Hold the OCP CAD Viewer on the current CAD, and re-push it after every save.

    uv run tools/watch.py                     # the whole robot, redrawn on save
    uv run tools/watch.py pelvis-shell        # one printed piece, on its own
    uv run tools/watch.py --finished --size 2

Everything the watcher does not recognise is handed to tools/view.py unchanged,
so whatever `uv run tools/view.py ...` shows, this shows and then keeps current.

It watches every .py under cad/ -- and tools/view.py itself -- and when one of
them changes it draws the view again in a FRESH interpreter. That is the whole
reason this is a subprocess and not a reload loop: cad/ is a web of modules that
read dimensions from each other, and reloading one in place leaves the rest
holding the old constants, which is a viewer that lies to you.

A build that fails does not stop it. The traceback prints and the watch carries
on, so the loop is edit, save, look, with no command in between.

Free and offline, exactly like tools/view.py: the geometry is tessellated here
and pushed over a socket to a viewer on port 3939 -- either the OCP CAD Viewer
panel in VS Code, or the standalone one this repository can start for itself:

    uv run --with ocp_vscode --with build123d python -m ocp_vscode --port 3939

If nothing is listening it waits for a viewer rather than building a robot it has
nowhere to send, and if the viewer goes away mid-session it waits again.

AND IT STILL PROVES NOTHING. Watching a part rebuild is not evidence that a
feature is there; structure behind a hole makes an open one look closed, which is
how four filled bolt holes survived several rebuilds here. tools/gate_e.py counts
the holes on the finished solid and tools/gate_f.py measures the clearances.
Those are the checks. This is for looking at the machine while you work on it.
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEW = ROOT / "tools" / "view.py"


def sources() -> dict[Path, float]:
    """Every file whose change should redraw, with the time it last changed."""
    stamps: dict[Path, float] = {}
    for path in sorted(ROOT.joinpath("cad").rglob("*.py")) + [VIEW]:
        try:
            stamps[path] = path.stat().st_mtime
        except OSError:
            continue  # deleted between the glob and the stat; the next pass sees it
    return stamps


def viewer_listening(port: int) -> bool:
    """Whether anything holds the viewer's port, which is all we can ask cheaply."""
    with socket.socket() as probe:
        probe.settimeout(0.25)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def wait_for_viewer(port: int) -> None:
    if viewer_listening(port):
        return
    print(f"nothing is listening on port {port}.")
    print("Open the OCP CAD Viewer panel in VS Code, or start the standalone one:")
    print(
        "  uv run --with ocp_vscode --with build123d python -m ocp_vscode"
        f" --port {port}"
    )
    while not viewer_listening(port):
        time.sleep(1.0)
    print("viewer found.")


def viewer_command() -> list[str]:
    """How to run tools/view.py so that it gets the dependencies it declares.

    Through uv, which reads view.py's own metadata block, rather than pinning a
    second copy of that dependency list here.
    """
    uv = shutil.which("uv")
    if uv is not None:
        return [uv, "run", "--script", str(VIEW)]
    print("uv is not on PATH; running tools/view.py with this interpreter instead")
    return [sys.executable, str(VIEW)]


def draw(command: list[str]) -> bool:
    """Build and push the view once, letting its own output through."""
    started = time.time()
    done = subprocess.run(command, cwd=ROOT)
    seconds = time.time() - started
    if done.returncode == 0:
        print(f"  drawn in {seconds:.1f}s")
        return True
    print(f"  FAILED after {seconds:.1f}s (exit {done.returncode}); still watching")
    return False


def changed_names(before: dict[Path, float], after: dict[Path, float]) -> str:
    """The files that moved, for the one line printed before each redraw."""
    names = sorted(
        {p.name for p, when in after.items() if before.get(p) != when}
        | {p.name for p in before if p not in after}
    )
    head = ", ".join(names[:3])
    return head if len(names) <= 3 else f"{head} and {len(names) - 3} more"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=3939)
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="seconds between checks of the CAD's timestamps (default 0.5)."
        " An editor writes a file in bursts, so a change is drawn once its"
        " timestamps have held still for one interval.",
    )
    args, forwarded = parser.parse_known_args()

    # The view runs as a child that writes to this same stdout, so a buffered
    # parent would print its own lines out of order behind the child's -- and a
    # watcher's whole job is to say what it is doing as it does it.
    sys.stdout.reconfigure(line_buffering=True)

    command = viewer_command() + ["--port", str(args.port), *forwarded]
    wait_for_viewer(args.port)

    watched = sources()
    print(f"watching {len(watched)} files under cad/; ctrl-c to stop")
    print(f"{time.strftime('%H:%M:%S')} first view")
    ok = draw(command)

    try:
        while True:
            time.sleep(args.interval)
            now = sources()
            if now == watched:
                continue
            while True:  # let the burst finish before building anything
                time.sleep(args.interval)
                settled = sources()
                if settled == now:
                    break
                now = settled
            print(f"{time.strftime('%H:%M:%S')} {changed_names(watched, now)}")
            watched = now
            ok = draw(command)
            if not ok:
                wait_for_viewer(args.port)  # a closed panel is recoverable
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
