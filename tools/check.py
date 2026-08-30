# /// script
# requires-python = ">=3.11"
# dependencies = ["zoo-kcl>=0.3.181"]
# ///
"""Mock-execute, lint and format-check the KCL sources.

This runs Zoo's own KCL interpreter locally, through the `zoo-kcl` package the
MCP server is itself built on. Nothing here touches the engine, so it costs no
API credits, needs no token, works offline, and keeps working on the days the
MCP server will not start.

What it does not do: mock execution never evaluates the booleans. A blind pocket
the engine will refuse passes here without complaint. See docs/KCL_GOTCHAS.md.

    uv run tools/check.py                 # every .kcl file in the project
    uv run tools/check.py joint.kcl       # just the files named
    uv run tools/check.py --fix           # rewrite anything badly formatted

Exit status is 1 if any file fails to execute, lints dirty, or is unformatted.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

import kcl

ROOT = Path(__file__).resolve().parent.parent

CRLF = "\r\n"
LF = "\n"


def targets(names: list[str]) -> list[Path]:
    if names:
        return [Path(n) if Path(n).is_absolute() else ROOT / n for n in names]
    return sorted(ROOT.glob("*.kcl"))


async def check_one(path: Path, fix: bool) -> dict:
    result: dict = {"path": path, "error": None, "lints": [], "unformatted": False}
    raw = path.read_bytes().decode("utf-8")
    # The working tree is CRLF here (core.autocrlf) while the formatter speaks
    # LF, so compare on LF and write back whichever ending the file already had.
    was_crlf = CRLF in raw
    source = raw.replace(CRLF, LF)

    formatted = kcl.format(source)
    if formatted != source:
        if fix:
            out = formatted.replace(LF, CRLF) if was_crlf else formatted
            path.write_bytes(out.encode("utf-8"))
            result["fixed"] = True
        else:
            result["unformatted"] = True

    # Lint findings carry a character offset, not a line, so turn it into one.
    result["lints"] = [
        f"line {source.count(LF, 0, d.pos[0]) + 1}: "
        f"{d.finding.code} {d.finding.title} — {d.description}"
        for d in kcl.lint(source)
        if not d.overridden
    ]

    started = time.time()
    try:
        outcome = await kcl.mock_execute(str(path))
        # Anything fatal raises; whatever is reported here is a warning.
        result["warnings"] = outcome.report_all()
    except Exception as exc:  # noqa: BLE001 - the KCL diagnostic is the payload
        # The Rust binding raises with the rendered diagnostic as args[0]; str()
        # on the exception itself would print it as an escaped tuple.
        args = getattr(exc, "args", ())
        result["error"] = args[0] if args and isinstance(args[0], str) else str(exc)
    result["seconds"] = time.time() - started
    return result


def indent(text: str) -> str:
    return LF.join("    " + line for line in text.rstrip().splitlines())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="KCL files; default is all of them")
    parser.add_argument("--fix", action="store_true", help="rewrite unformatted files")
    args = parser.parse_args()

    files = targets(args.files)
    if not files:
        print("no .kcl files found", file=sys.stderr)
        return 1

    results = [asyncio.run(check_one(p, args.fix)) for p in files]

    failed = fixed = unformatted = dirty = 0
    for r in results:
        flags = []
        if r["unformatted"]:
            flags.append("needs formatting")
            unformatted += 1
        if r.get("fixed"):
            flags.append("reformatted")
            fixed += 1
        if r["lints"]:
            flags.append(f"{len(r['lints'])} lint")
            dirty += 1
        if r.get("warnings"):
            flags.append(f"{len(r['warnings'])} warning")

        status = "FAIL" if r["error"] else "ok"
        if r["error"]:
            failed += 1
        print(f"{r['path'].name:26s} {status:5s} {r['seconds']:5.2f}s  {', '.join(flags)}")

        if r["error"]:
            print(indent(r["error"]))
        for lint in r["lints"]:
            print(f"    lint {lint}")
        for warning in r.get("warnings", []):
            print(indent(warning))

    total = len(results)
    summary = [f"{total - failed}/{total} execute"]
    if failed:
        summary.append(f"{failed} FAILED")
    summary.append("lint clean" if not dirty else f"{dirty} files lint dirty")
    if fixed:
        summary.append(f"{fixed} reformatted")
    if unformatted:
        summary.append(f"{unformatted} {'file needs' if unformatted == 1 else 'files need'} formatting (--fix)")
    print(LF + " · ".join(summary))

    return 1 if (failed or dirty or unformatted) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
