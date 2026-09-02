# /// script
# requires-python = ">=3.11"
# ///
"""Throw away Zoo Design Studio's caches so it rebuilds them from the sources.

Design Studio is an Electron app, so it keeps a Chromium profile beside its own
state. Its index of the project -- the file paths, their hashes and when it last
saw them -- lives in that profile's IndexedDB store, next to the HTTP and shader
caches. When that index goes bad the app opens on stale or missing geometry, and
the cure is to delete the caches and let it build them again from the .kcl files,
which are the only real source of truth here.

    uv run tools/clear_cache.py              # clear them, stay signed in
    uv run tools/clear_cache.py --dry-run    # list what would go, delete nothing
    uv run tools/clear_cache.py --all        # take the session stores too

Nothing here touches the KCL sources or the design in any way. Every directory it
removes is one the app writes again by itself on the next start; the cost of
running it needlessly is a slower first load.

The default deliberately leaves Local Storage, Session Storage and the network
cookie jar alone, so you stay signed in to your Zoo account and the app's
unsaved-file recovery snapshot survives. `--all` takes those as well, which signs
you out and drops the snapshot. Neither mode touches settings.toml.

That surviving snapshot is worth knowing about, because it is not merely stale
cache: Design Studio restores it over the file on disk and executes that instead.
A snapshot left behind by an edit made before a commit can therefore make a file
draw the old design, or draw nothing at all when the old code imports a module
the commit has since deleted. That last case cost a morning on 2026-09-02 --
main.kcl rendered nothing while a byte-identical copy under another name rendered
the whole robot, because the snapshot still imported a deleted hip carrier. So
every run now lists which files hold a snapshot and whether it still agrees with
disk. Only `--all` can actually remove one.

It refuses to run while Design Studio is open. Deleting a live Chromium's cache
out from under it is a good way to produce the next corruption rather than fix
one, and on Windows the files are locked anyway.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_DIR_NAME = "dev.zoo.modeling-app"

# Rebuilt on the next start, and between them they hold everything the app has
# cached about the model. IndexedDB is the one that actually carries the project
# index; the rest are Chromium's HTTP, compiled-code and shader caches, which are
# cleared alongside it because a half-cleared profile is its own kind of stale.
CACHE_DIRS = [
    "IndexedDB",
    "Cache",
    "Code Cache",
    "GPUCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "Shared Dictionary",
]

# Also rebuilt, but these carry the signed-in session and the recovery snapshot,
# so they go only when asked for.
SESSION_DIRS = [
    "Local Storage",
    "Session Storage",
    "Network",
    "WebStorage",
]

# Substrings of a running process name that mean the app is open. "zoo" alone is
# not one of them: it matches Zoom, which most machines have.
RUNNING_MARKERS = ["zoo design studio", "zoo modeling", "modeling-app", "modeling app"]


def profile_dir() -> Path:
    """Where this platform's Electron apps keep their per-user profile."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if not base:
            raise SystemExit("APPDATA is not set; cannot find the Design Studio profile")
        return Path(base) / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_DIR_NAME


def running_processes() -> list[str]:
    """Lowercased names of the processes currently running, or [] if unknown."""
    if sys.platform == "win32":
        command = ["tasklist", "/fo", "csv", "/nh"]
    else:
        command = ["ps", "-A", "-o", "comm="]
    try:
        out = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip().strip('"').split('","')[0].lower() for line in out.stdout.splitlines() if line.strip()]


def design_studio_is_open() -> bool:
    names = running_processes()
    return any(marker in name for name in names for marker in RUNNING_MARKERS)


def size_of(path: Path) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


# Design Studio keeps an unsaved-file recovery buffer per file, in the Chromium
# Local Storage store, under a key of this shape followed by the file's full
# path. The value beside it is a small JSON record carrying the path again and
# the whole of the code it saved. Chromium writes local storage values as either
# Latin-1 or UTF-16LE depending on the string, so the store is read under both.
RECOVERY_KEY = "kclRecovery:"
RECOVERY_JSON = '{"version":'

RECOVERY_NOTES = {
    "stale": "differs from disk -- this shadows your file",
    "gone": "the file it belongs to no longer exists",
    "matches": "agrees with disk",
    "unreadable": "present, contents could not be read",
}
RECOVERY_LABELS = {"stale": "STALE ", "gone": "ORPHAN", "matches": "ok    ", "unreadable": "?     "}


def _decodings(raw: bytes) -> list[str]:
    """The store's bytes as text, under both encodings Chromium uses."""
    return [raw.decode("latin-1", "replace"), raw.decode("utf-16-le", "replace")]


def _records(text: str):
    """Every recovery record in one decoding, as (path, saved code).

    Parsed with the JSON decoder rather than matched with a pattern: the values
    are real JSON, and a compacted log leaves enough truncated look-alikes around
    that a pattern gets them wrong.
    """
    decoder = json.JSONDecoder()
    index = 0
    while True:
        index = text.find(RECOVERY_JSON, index)
        if index == -1:
            return
        try:
            record, end = decoder.raw_decode(text, index)
        except ValueError:
            index += len(RECOVERY_JSON)
            continue
        index = end
        if not isinstance(record, dict):
            continue
        path, code = record.get("path"), record.get("code")
        if isinstance(path, str) and isinstance(code, str):
            yield path, code


def _bare_keys(text: str):
    """The file paths named by recovery keys, whether or not a record survived."""
    index = 0
    while True:
        index = text.find(RECOVERY_KEY, index)
        if index == -1:
            return
        cursor = index + len(RECOVERY_KEY)
        start = cursor
        while cursor < len(text) and text[cursor] >= " " and text[cursor] != '"':
            cursor += 1
        tail = text[start:cursor]
        index = cursor if cursor > start else start + 1
        cut = tail.rfind(".kcl")
        if cut != -1:
            yield tail[: cut + 4]


def recovery_snapshots(profile: Path) -> list[tuple[str, str]]:
    """Every recovery snapshot in the profile, as (file path, verdict).

    The verdict is "stale" when the saved code differs from what is on disk --
    the case that shadows the real file -- "matches" when it agrees, "gone" when
    the file it belongs to has been deleted, and "unreadable" when the key is
    there but no record could be parsed out beside it.
    """
    store = profile / "Local Storage" / "leveldb"
    if not store.is_dir():
        return []

    found: dict[str, str] = {}
    for entry in sorted(store.iterdir()):
        if not entry.is_file():
            continue
        try:
            raw = entry.read_bytes()
        except OSError:
            continue
        for text in _decodings(raw):
            if RECOVERY_KEY not in text:
                continue
            for path in _bare_keys(text):
                found.setdefault(path, "unreadable")
            for path, code in _records(text):
                target = Path(path)
                if not target.is_file():
                    found[path] = "gone"
                    continue
                try:
                    on_disk = target.read_text(encoding="utf-8")
                except OSError:
                    found[path] = "unreadable"
                    continue
                agrees = on_disk.replace("\r\n", "\n") == code.replace("\r\n", "\n")
                found[path] = "matches" if agrees else "stale"
    return sorted(found.items())


def report_recovery(profile: Path, removed: bool) -> bool:
    """Print the snapshot roll-up. True if one of them is shadowing a file."""
    snapshots = recovery_snapshots(profile)
    if not snapshots:
        return False

    if removed:
        print(f"\n  dropped {len(snapshots)} recovery snapshot(s) along with Local Storage")
        return False

    print("\n  recovery snapshots, which the app restores over the file on disk:")
    for path, verdict in snapshots:
        try:
            shown = str(Path(path).relative_to(Path.cwd()))
        except ValueError:
            shown = path
        print(f"    {RECOVERY_LABELS[verdict]}  {shown:<26} {RECOVERY_NOTES[verdict]}")

    if not any(verdict in ("stale", "gone") for _, verdict in snapshots):
        return False
    print("\n  A stale snapshot is opened INSTEAD of the file on disk, so the app can")
    print("  show the old design, or draw nothing at all when the old code imports a")
    print("  module that has since been deleted. Clear it with:")
    print("      uv run tools/clear_cache.py --all      (signs you out of Zoo)")
    return True


def human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:,.0f} {unit}" if unit == "B" else f"{value:,.1f} {unit}"
        value /= 1024
    return f"{value:,.1f} GB"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be removed and its size, then stop",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="also clear the session stores; this signs you out of Zoo",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="clear even if Design Studio looks like it is running",
    )
    args = parser.parse_args()

    profile = profile_dir()
    if not profile.is_dir():
        print(f"no Design Studio profile at {profile}", file=sys.stderr)
        print("nothing to clear -- has the app ever been run on this machine?", file=sys.stderr)
        return 1

    if not args.dry_run and not args.force and design_studio_is_open():
        print("Zoo Design Studio is running. Close it first, or pass --force.", file=sys.stderr)
        print("Clearing a live profile is how the next corruption gets made.", file=sys.stderr)
        return 1

    wanted = CACHE_DIRS + (SESSION_DIRS if args.all else [])
    present = [(name, profile / name) for name in wanted if (profile / name).is_dir()]
    if not present:
        print(f"{profile}\nalready clear -- none of the cache directories exist")
        return 0

    print(profile)
    cleared = 0
    failed = []
    for name, path in present:
        size = size_of(path)
        if args.dry_run:
            print(f"  would clear  {name:<20} {human(size):>10}")
            cleared += size
            continue
        try:
            shutil.rmtree(path)
        except OSError as exc:
            failed.append(name)
            print(f"  FAILED       {name:<20} {exc.strerror or exc}", file=sys.stderr)
            continue
        print(f"  cleared      {name:<20} {human(size):>10}")
        cleared += size

    verb = "would free" if args.dry_run else "freed"
    print()
    print(f"  {verb} {human(cleared)}")
    if not args.dry_run and not args.all:
        print("  left the session stores alone; you are still signed in")
    report_recovery(profile, removed=args.all and not args.dry_run)
    if failed:
        print(f"\n{len(failed)} directory(ies) would not delete -- is the app still open?", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
