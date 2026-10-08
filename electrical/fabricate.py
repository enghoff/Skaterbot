# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1", "shapely>=2.0", "matplotlib>=3.8", "numpy>=1.26"]
# ///
"""Generate, check and package each board's fabrication files as one release.

    uv run electrical/fabricate.py                 # both boards
    uv run electrical/fabricate.py power           # or carrier
    uv run electrical/fabricate.py --verify

Requires KiCad 10's kicad-cli. No files are sent to a manufacturer.

The carrier is redrawn by carrier_kicad.py in seconds. The power switch board is
redrawn by power_sch.py and power_pcb.py, and power_pcb.py routes it, which
takes several minutes.

What the order form has to say, because nothing in these files says it: the
power switch board is 2 oz copper, and the carrier 1 oz.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import carrier_kicad

ROOT = Path(__file__).resolve().parent.parent
ELECTRICAL = ROOT / "electrical"


def build_power() -> int:
    for script in ("power_sch.py", "power_pcb.py"):
        if subprocess.run([sys.executable, str(ELECTRICAL / script)]).returncode:
            return 1
    return 0


@dataclass(frozen=True)
class Board:
    name: str
    project: Path
    files: tuple[str, ...]  # the project's own inputs, beside the shared Python
    build: Callable[[], int]  # redraws the board and its schematic; nonzero on failure
    # The power board carries thirteen silkscreen warnings that power_pcb.py
    # reports and accepts, so its release refuses errors only.
    severity: str = "--severity-all"

    @property
    def output(self) -> Path:
        return self.project / "gerber"

    @property
    def manifest(self) -> Path:
        return self.output / "manifest.json"

    @property
    def archive(self) -> Path:
        return self.project / f"{self.name}-fabrication.zip"

    def sources(self) -> dict[str, str]:
        paths = sorted((ROOT / "cad").glob("*.py")) + sorted(ELECTRICAL.glob("*.py"))
        paths += [self.project / name for name in self.files]
        paths += sorted(self.project.glob("*.pretty/*.kicad_mod"))
        return {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}


BOARDS = {
    "carrier": Board(
        "carrier",
        ELECTRICAL / "kicad",
        (
            "carrier.kicad_pcb",
            "carrier.kicad_sch",
            "carrier.kicad_pro",
            "carrier.kicad_sym",
            "fp-lib-table",
            "sym-lib-table",
        ),
        carrier_kicad.main,
    ),
    "power": Board(
        "power",
        ELECTRICAL / "kicad_power",
        ("power.kicad_pcb", "power.kicad_sch", "power.kicad_pro", "fp-lib-table"),
        build_power,
        "--severity-error",
    ),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(board: Board) -> None:
    manifest = json.loads(board.manifest.read_text(encoding="utf-8"))
    if manifest["sources"] != board.sources():
        raise RuntimeError(
            f"{board.name} fabrication files are stale: regenerate with "
            f"electrical/fabricate.py {board.name}"
        )
    for name, sha in manifest["files"].items():
        if digest(board.output / name) != sha:
            raise RuntimeError(f"Fabrication file changed: {name}")
    with zipfile.ZipFile(board.archive) as package:
        for name, sha in manifest["files"].items():
            if hashlib.sha256(package.read(name)).hexdigest() != sha:
                raise RuntimeError(f"Archive disagrees with checked file: {name}")
        if package.read("manifest.json") != board.manifest.read_bytes():
            raise RuntimeError("Archive manifest is stale")
    print(f"{board.name} release: source hashes, files and ZIP all match")


def kicad_cli() -> str:
    cli = shutil.which("kicad-cli")
    if not cli:
        candidate = (
            Path(os.environ.get("ProgramFiles", "C:/Program Files"))
            / "KiCad/10.0/bin/kicad-cli.exe"
        )
        if candidate.is_file():
            cli = str(candidate)
    if not cli:
        raise RuntimeError("KiCad 10 kicad-cli was not found")
    return cli


def release(board: Board, cli: str) -> int:
    if board.build():
        return 1

    def run(*arguments):
        subprocess.run([cli, *map(str, arguments)], check=True)

    pcb = board.project / f"{board.name}.kicad_pcb"
    with tempfile.TemporaryDirectory(prefix="biped-fabrication-") as folder:
        stage = Path(folder).resolve()
        # Only generated files in this dedicated temporary directory are cleaned up.
        assert stage.parent == Path(tempfile.gettempdir()).resolve()
        run(
            "pcb",
            "drc",
            "--refill-zones",
            "--save-board",
            "--schematic-parity",
            board.severity,
            "--exit-code-violations",
            "--output",
            stage / "drc.txt",
            pcb,
        )
        run(
            "sch",
            "erc",
            "--exit-code-violations",
            "--output",
            stage / "erc.txt",
            board.project / f"{board.name}.kicad_sch",
        )
        run(
            "pcb",
            "export",
            "gerbers",
            "--no-protel-ext",
            "--layers",
            "F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,F.Paste,B.Paste,Edge.Cuts",
            "--output",
            str(stage) + os.sep,
            pcb,
        )
        run(
            "pcb",
            "export",
            "drill",
            "--excellon-separate-th",
            "--generate-report",
            "--report-path",
            stage / "drill-report.txt",
            "--output",
            str(stage) + os.sep,
            pcb,
        )
        silk = stage / f"{board.name}-F_Silkscreen.gbr"
        if "%ADD" not in silk.read_text(encoding="utf-8"):
            raise RuntimeError("Top silkscreen has no drawing apertures")
        for suffix in ("F_Cu.gbr", "B_Cu.gbr", "Edge_Cuts.gbr", "PTH.drl", "NPTH.drl"):
            if not (stage / f"{board.name}-{suffix}").is_file():
                raise RuntimeError(f"Missing fabrication output: {suffix}")
        manifest = {
            "sources": board.sources(),
            "files": {p.name: digest(p) for p in sorted(stage.iterdir())},
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        board.output.mkdir(exist_ok=True)
        for path in stage.iterdir():
            shutil.copy2(path, board.output / path.name)
        with zipfile.ZipFile(board.archive, "w", zipfile.ZIP_DEFLATED) as package:
            for path in sorted(stage.iterdir()):
                package.write(path, path.name)
    verify(board)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("boards", nargs="*", metavar="board", help="carrier or power")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    unknown = sorted(set(args.boards) - set(BOARDS))
    if unknown:
        parser.error(f"no such board: {', '.join(unknown)}")
    boards = [BOARDS[name] for name in args.boards or BOARDS]
    if args.verify:
        for board in boards:
            verify(board)
        return 0
    cli = kicad_cli()
    for board in boards:
        if release(board, cli):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
