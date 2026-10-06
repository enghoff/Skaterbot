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
-- are the one-command version of this: they are `--finished` plus whatever you
give them, so `watch.cmd pelvis-shell` watches that piece as it would be
printed. They take `--raw` to drop the --finished again, which is worth doing on
the whole robot, where the chamfer is about a minute of every redraw, and
`--browser` to pass `--serve` through.

It watches every .py under cad/ -- and tools/view.py itself -- and when one of
them changes it draws the view again in a FRESH interpreter. That is the whole
reason this is a subprocess and not a reload loop: cad/ is a web of modules that
read dimensions from each other, and reloading one in place leaves the rest
holding the old constants, which is a viewer that lies to you.

A build that fails does not stop it. The traceback prints and the watch carries
on, so the loop is edit, save, look, with no command in between.

Free and offline, exactly like tools/view.py: the geometry is tessellated here
and pushed over a socket to a viewer -- either the OCP CAD Viewer panel in VS
Code, or the standalone one this repository can start for itself:

    uv run --with ocp_viewer --with build123d python -m ocp_viewer --port 3970

THE SERVER AND THE CLIENT ARE TWO PACKAGES SINCE OCP CAD Viewer 4.1, and only
one of them was renamed. What pushes geometry is still `ocp_vscode`, which is
what tools/view.py imports; the standalone server moved out of it into
`ocp_viewer`. `python -m ocp_vscode` did not start failing when that happened --
it prints where the viewer went and exits 0 -- so the symptom was this script
reporting "the viewer exited with 0 before it listened" and nothing else. The
browser tab the old server opened as it came up went the same way, and is opened
by `open_viewer_page` below instead.

THE VS CODE PANEL IS THE DEFAULT and the browser is the fallback, because a
model beside the code it is drawn from is the point of watching it at all. So
this waits for a viewer rather than building a robot it has nowhere to send, and
waits again if the viewer goes away mid-session. `--serve` is the other way:
it starts the standalone server itself and opens a tab on it -- unless the port
is already answering, because an open panel in VS Code is a viewer and a second
server would only fail to bind -- and stops it again when you stop watching.

NOTHING HERE CAN OPEN THE VS CODE PANEL, which is why the wait is a printed
instruction rather than a command. Opening it is `ocpCadViewer.ocpCadViewer`,
a VS Code command, and the extension registers no URI handler, so there is no
`code --open-url` or any other way in from a terminal. What can drive it is VS
Code itself: .vscode/tasks.json's "watch the CAD" opens the panel and then runs
this, and it is the default build task, so ctrl-shift-B is the whole gesture.

AND IT STILL PROVES NOTHING. Watching a part rebuild is not evidence that a
feature is there; structure behind a hole makes an open one look closed, which is
how four filled bolt holes survived several rebuilds here. tools/gate_e.py counts
the holes on the finished solid and tools/gate_f.py measures the clearances.
Those are the checks. This is for looking at the machine while you work on it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEW = ROOT / "tools" / "view.py"
# Where every viewer announces itself.
REGISTRY = Path.home() / ".ocpvscode"
# Where THIS project's viewer starts, which is .vscode/settings.json's
# OcpCadViewer.advanced.initialPort and has to stay the same number. The
# extension's own default is 3939, and every other project's panel starts there;
# the registry above is shared by all of them, so a watcher that took any viewer
# it found drew this robot into another project's window. The panel takes this
# port if it is free and the next one up if not.
PROJECT_PORT = 3970


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


def registered_ports() -> list[int]:
    """Every viewer that has announced itself, whether or not it is still there.

    `~/.ocpvscode` is the registry all of this shares: the VS Code extension
    writes it from TypeScript as its panel opens, the standalone server writes
    it too, and every Python client reads it to find a viewer. A viewer removes
    its own line as it stops -- but one that is killed rather than stopped
    leaves it behind, so this is the candidate list and `find_viewer` is the
    answer.
    """
    try:
        config = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    ports = []
    for name in config.get("services", {}):
        try:
            ports.append(int(name))
        except ValueError:
            continue  # a malformed line is somebody else's to clean up
    return sorted(ports)


def find_viewer(pinned: int | None = None) -> int | None:
    """The port of THIS project's viewer, if one is answering, or None.

    WHY THIS IS NOT A CONSTANT. PROJECT_PORT is only where the extension STARTS
    looking for a free port. Anything already holding it -- a standalone viewer
    in a browser tab, a second panel, a viewer that outlived the editor that
    opened it -- pushes the panel one port up, and then a watcher aimed at the
    first port sits waiting with the viewer open on screen in front of it. So
    the registry is asked which viewers exist rather than asserting where one
    ought to be.

    AND WHY ONLY FROM PROJECT_PORT UP. The registry holds every project's
    viewers, not this one's, and another project's panel on 3939 is a viewer
    that answers. Taking whichever answered drew this robot into it.
    """
    if pinned is not None:
        return pinned if viewer_listening(pinned) else None
    live = [
        port
        for port in registered_ports()
        if port >= PROJECT_PORT and viewer_listening(port)
    ]
    if not live:
        # A viewer old enough not to register, or one whose line was lost.
        return PROJECT_PORT if viewer_listening(PROJECT_PORT) else None
    return live[0]  # the lowest, which is PROJECT_PORT whenever that is up


def wait_for_viewer(
    pinned: int | None = None, server: subprocess.Popen | None = None
) -> int | None:
    """Block until a viewer answers, and return the port it answered on.

    The port is discovered rather than assumed, and discovered again on every
    pass of the wait, because the viewer this is waiting for does not exist yet
    and will register whichever port it ends up on. With no viewer of our own
    there is nothing to do but wait for a human to open one, so the message is
    the instruction. With one, the wait is a second or two -- unless it dies on
    the way up, which is the None.
    """
    found = find_viewer(pinned)
    if found is not None:
        return found
    if server is None:
        where = f"port {pinned}" if pinned else "any port"
        print(f"no viewer is listening on {where}; waiting for one.")
        print('In VS Code: ctrl-shift-P, "OCP CAD Viewer: Open viewer".')
        print("  (or ctrl-shift-B, which opens the panel and runs this)")
        print("In a browser: run this again with --browser, or start one yourself:")
        print("  uv run --with ocp_viewer --with build123d python -m ocp_viewer")
    while found is None:
        if server is not None and server.poll() is not None:
            print(f"the viewer exited with {server.returncode} before it listened")
            return None
        time.sleep(1.0)
        found = find_viewer(pinned)
    print(f"viewer is up on port {found}.")
    return found


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
        command = [sys.executable, "-m", "ocp_viewer", "--port", str(port)]
    else:
        command = [uv, "run", "--with", "ocp_viewer", "--with", "build123d"]
        command += ["python", "-m", "ocp_viewer", "--port", str(port)]
    print(f"starting the standalone viewer on port {port}")
    # Its own process group on POSIX, so that stopping it later stops the
    # interpreter uv started underneath it instead of orphaning the server.
    group = {} if sys.platform == "win32" else {"start_new_session": True}
    return subprocess.Popen(command, cwd=ROOT, **group)


def open_viewer_page(port: int) -> None:
    """Put the viewer on screen, which the server no longer does for itself.

    Until OCP CAD Viewer 4.1 the standalone server opened a browser tab as it
    came up. `ocp_viewer` serves the page and waits to be visited instead -- it
    prints its URL, says "No browser registered" and sits there -- so `watch.cmd`
    came up listening, watching and redrawing with nothing on screen to redraw
    onto. Opening the tab is ours to do now, and only when the viewer is ours:
    an OCP CAD Viewer panel in VS Code is already a window.
    """
    url = f"http://127.0.0.1:{port}"
    print(f"opening {url}")
    try:
        opened = webbrowser.open(url)
    except OSError as failure:  # no browser to open, on a headless machine
        opened = False
        print(f"  could not: {failure}")
    if not opened:
        print(f"  open {url} yourself to see the model")


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
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="pin the viewer to draw into. The default is to find this"
        " project's: the lowest port from PROJECT_PORT (3970) up that is"
        " registered in ~/.ocpvscode and still answers, which is how the VS"
        " Code panel is found when it did not get 3970 itself",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="start the standalone viewer first if nothing is listening on the"
        " port, open a browser tab on it, and stop it again on the way out."
        " Without this the wait is for an OCP CAD Viewer panel in VS Code,"
        " which is what watch.cmd does unless you pass it --browser",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="do not open a browser tab on the viewer this script started,"
        " for a machine that has no browser or a tab that is already open",
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

    # A viewer we start is one we choose the port of; one we find is one we ask
    # the registry about. Either way the answer is known before anything is
    # drawn, and view.py is then told the number rather than repeating the
    # search for itself.
    served = args.port or PROJECT_PORT
    server = serve_viewer(served) if args.serve else None
    pinned = served if args.serve else args.port

    try:
        port = wait_for_viewer(pinned, server)
        if port is None:
            return 1
        if server is not None and not args.no_browser and "--list" not in forwarded:
            open_viewer_page(port)
        command = viewer_command() + ["--port", str(port), *forwarded]

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
            # THE VIEWER IS LOOKED FOR AGAIN BEFORE EVERY DRAW, not only after a
            # draw fails. A panel that is closed and reopened, or a VS Code
            # window reloaded, comes back on whatever port is free -- and a draw
            # aimed at the old one does NOT fail: ocp_vscode warns once that it
            # cannot reach a viewer and returns, view.py exits 0, and this loop
            # went on pushing every redraw into a dead port with the panel open
            # beside it. Found that way: drawing to 3939 for a day while the
            # panel sat on 3940.
            found = find_viewer(pinned)
            if found is None:
                found = wait_for_viewer(pinned, server)
                if found is None:
                    return 1
            if found != port:
                print(f"  the viewer is on port {found} now, not {port}")
                port = found
                command = viewer_command() + ["--port", str(port), *forwarded]
            drawn = draw(command)
            if not drawn:
                # A closed panel recovers, and recovers onto whatever port it
                # comes back on, which is why the command is rebuilt with it.
                port = wait_for_viewer(pinned, server)
                if port is None:
                    return 1
                command = viewer_command() + ["--port", str(port), *forwarded]
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        stop_viewer(server)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
