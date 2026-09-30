# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1", "shapely>=2.0", "matplotlib>=3.8", "numpy>=1.26"]
# ///
"""Generate, check and package the carrier fabrication files as one release.

    uv run electrical/fabricate.py
    uv run electrical/fabricate.py --verify

Requires KiCad 10's kicad-cli. No files are sent to a manufacturer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import carrier_kicad

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "electrical" / "kicad"
OUTPUT = PROJECT / "gerber"
MANIFEST = OUTPUT / "manifest.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources() -> dict[str, str]:
    paths = sorted((ROOT / "cad").glob("*.py")) + sorted(
        (ROOT / "electrical").glob("*.py")
    )
    paths += [
        PROJECT / f"carrier.kicad_{suffix}" for suffix in ("pcb", "sch", "pro", "sym")
    ]
    paths += sorted((PROJECT / "carrier.pretty").glob("*.kicad_mod"))
    paths += [PROJECT / "fp-lib-table", PROJECT / "sym-lib-table"]
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}


def verify() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["sources"] != sources():
        raise RuntimeError(
            "Fabrication files are stale: regenerate with electrical/fabricate.py"
        )
    for name, sha in manifest["files"].items():
        if digest(OUTPUT / name) != sha:
            raise RuntimeError(f"Fabrication file changed: {name}")
    archive = PROJECT / "carrier-fabrication.zip"
    with zipfile.ZipFile(archive) as package:
        for name, sha in manifest["files"].items():
            if hashlib.sha256(package.read(name)).hexdigest() != sha:
                raise RuntimeError(f"Archive disagrees with checked file: {name}")
        if package.read("manifest.json") != MANIFEST.read_bytes():
            raise RuntimeError("Archive manifest is stale")
    print("Fabrication release: source hashes, files and ZIP all match")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify()
        return 0
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
    if carrier_kicad.main():
        return 1

    def run(*arguments):
        subprocess.run([cli, *map(str, arguments)], check=True)

    board = PROJECT / "carrier.kicad_pcb"
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
            "--exit-code-violations",
            "--output",
            stage / "drc.txt",
            board,
        )
        run(
            "sch",
            "erc",
            "--exit-code-violations",
            "--output",
            stage / "erc.txt",
            PROJECT / "carrier.kicad_sch",
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
            board,
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
            board,
        )
        silk = stage / "carrier-F_Silkscreen.gbr"
        if "%ADD" not in silk.read_text(encoding="utf-8"):
            raise RuntimeError("Top silkscreen has no drawing apertures")
        for suffix in ("F_Cu.gbr", "B_Cu.gbr", "Edge_Cuts.gbr", "PTH.drl", "NPTH.drl"):
            if not (stage / f"carrier-{suffix}").is_file():
                raise RuntimeError(f"Missing fabrication output: {suffix}")
        manifest = {
            "sources": sources(),
            "files": {p.name: digest(p) for p in sorted(stage.iterdir())},
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        OUTPUT.mkdir(exist_ok=True)
        for path in stage.iterdir():
            shutil.copy2(path, OUTPUT / path.name)
        with zipfile.ZipFile(
            PROJECT / "carrier-fabrication.zip", "w", zipfile.ZIP_DEFLATED
        ) as package:
            for path in sorted(stage.iterdir()):
                package.write(path, path.name)
    verify()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
