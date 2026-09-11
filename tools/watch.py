# /// script
# requires-python = ">=3.11,<3.13"
# ///
"""Hold the OCP CAD Viewer on the current CAD, and re-push it after every save.

    uv run tools/watch.py                     # the whole robot, redrawn on save
    uv run tools/watch.py pelvis-shell        # one printed piece, on its own
    uv run tools/watch.py --finished --size 2
    uv run tools/watch.py --serve            # and bring a viewer up first

Everything the watcher does not recognise is handed to tools/view.py unchanged,
so whatever `uv run tools/view.py ...` shows, this shows and then keeps current.

The scripts at the project root -- watch.cmd on Windows, watch.sh anywhere else
-- are the one-command version of this: they are `--serve --finished` plus
whatever you give them, so `watch.cmd pelvis-shell` opens a viewer and watches
that piece as it would be printed. They take `--raw` to drop the --finished
again, which is worth doing on the whole robot, where the chamfer is about a
minute of every redraw.

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
nowhere to send, and if the viewer goes away mid-session it waits again. With
`--serve` it starts that standalone viewer itself -- unless the port is already
answering, because an open panel in VS Code is a viewer and a second server
would only fail to bind -- and stops it again when you stop watching.

AND IT STILL PROVES NOTHING. Watching a part rebuild is not evidence that a
feature is there; structure behind a hole makes an open one look closed, which is
how four filled bolt holes survived several rebuilds here. tools/gate_e.py counts
the holes on the finished solid and tools/gate_f.py measures the clearances.
Those are the checks. This is for looking at the machine while you work on it.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
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


def wait_for_viewer(port: int, server: subprocess.Popen | None = None) -> bool:
    """Block until something holds the port, and say so if it never does.

    With no viewer of our own there is nothing to do but wait for a human to
    open one, so the message is the instruction. With one, the wait is a second
    or two -- unless it dies on the way up, which is the False.
    """
    if viewer_listening(port):
        return True
    if server is None:
        print(f"nothing is listening on port {port}.")
        print("Open the OCP CAD Viewer panel in VS Code, or start the standalone one:")
        print(
            "  uv run --with ocp_vscode --with build123d python -m ocp_vscode"
            f" --port {port}"
        )
    while not viewer_listening(port):
        if server is not None and server.poll() is not None:
            print(f"the viewer exited with {server.returncode} before it listened")
            return False
        time.sleep(1.0)
    print("viewer is up.")
    return True


def serve_viewer(port: int) -> subprocess.Popen | None:
    """Start the standalone viewer ourselves, unless something already answers.

    An open OCP CAD Viewer panel in VS Code is a viewer, and a second server on
    the same port would only fail to bind it, so a port that answers is left
    alone and there is then nothing of ours to stop afterwards.
    """
    if viewer_listening(port):
        print(f"a viewer already holds port {port}; using that one")
        return None
    uv = shutil.which("uv")
    if uv is None:
        command = [sys.executable, "-m", "ocp_vscode", "--port", str(port)]
    else:
        command = [uv, "run", "--with", "ocp_vscode", "--with", "build123d"]
        command += ["python", "-m", "ocp_vscode", "--port", str(port)]
    print(f"starting the standalone viewer on port {port}; it opens a browser tab")
    # Its own process group on POSIX, so that stopping it later stops the
    # interpreter uv started underneath it instead of orphaning the server.
    group = {} if sys.platform == "win32" else {"start_new_session": True}
    return subprocess.Popen(command, cwd=ROOT, **group)


def stop_viewer(server: subprocess.Popen | None) -> None:
    """Take a viewer we started down with us, children and all.

    uv runs the server in a grandchild, so killing the process we hold is not
    enough on either platform: Windows needs the tree, POSIX the group.
    """
    if server is None or server.poll() is not None:
        return
    print("stopping the viewer")
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(server.pid)], capture_output=True
        )
    else:
        os.killpg(os.getpgid(server.pid), signal.SIGTERM)
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()


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
        "--serve",
        action="store_true",
        help="start the standalone viewer first if nothing is listening on the"
        " port, and stop it again on the way out -- which is all the watch.cmd"
        " and watch.sh scripts at the project root do",
    )
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
    server = serve_viewer(args.port) if args.serve else None

    try:
        if not wait_for_viewer(args.port, server):
            return 1

        watched = sources()
        print(f"watching {len(watched)} files under cad/; ctrl-c to stop")
        print(f"{time.strftime('%H:%M:%S')} first view")
        drawn = draw(command)

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
            drawn = draw(command)
            if not drawn:
                wait_for_viewer(args.port, server)  # a closed panel recovers
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        stop_viewer(server)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
