# /// script
# requires-python = ">=3.11,<3.13"
# ///
"""Read symbols out of KiCad's own libraries, so a drawing can use the real ones.

A schematic that draws its own boxes is legible only to whoever wrote it. A
resistor should be a resistor, a diode should point somewhere, and a MOSFET
should show which terminal is the gate -- and KiCad ships all of that in
share/kicad/symbols. This module lifts a named symbol out of those files, tells
the caller where each of its pins is, and works out where a pin lands once the
symbol is placed on a sheet at some position and rotation.

TWO THINGS ABOUT THE COORDINATES, both of which cost an afternoon if they are
guessed at:

  A LIBRARY'S Y AXIS POINTS UP AND A SHEET'S POINTS DOWN. A pin drawn at y
  +3.81 in the library sits 3.81 mm ABOVE the symbol's origin on the sheet,
  which is y - 3.81 in sheet coordinates.

  ROTATION IS COUNTER-CLOCKWISE IN LIBRARY SPACE, applied before that flip.

Both are asserted rather than believed: the transform below was checked against
kicad-cli's own netlist export, at all four rotations and both mirrors, by
wiring each pin of a placed symbol to a uniquely named label and confirming
KiCad put that label on that pin.

A SYMBOL MAY EXTEND ANOTHER ONE. Most named parts do -- Transistor_BJT:BC546 is
Q_NPN_CBE with a part number on it, Comparator:LM393 is LM2903 -- and a
schematic file has to carry the finished symbol rather than the reference, so
`symbol()` flattens the two together.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path


def library_root() -> Path:
    """Where KiCad keeps the symbol libraries it ships with."""
    if os.name == "nt":
        candidates = [
            Path(r"C:\Program Files\KiCad"),
            Path(r"C:\Program Files (x86)\KiCad"),
        ]
        for base in candidates:
            if not base.is_dir():
                continue
            versions = sorted(
                (p for p in base.iterdir() if (p / "share/kicad/symbols").is_dir()),
                key=lambda p: p.name,
                reverse=True,
            )
            if versions:
                return versions[0] / "share/kicad/symbols"
    for guess in (
        Path("/usr/share/kicad/symbols"),
        Path("/usr/local/share/kicad/symbols"),
        Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"),
    ):
        if guess.is_dir():
            return guess
    raise SystemExit("cannot find KiCad's symbol libraries")


@dataclass(frozen=True)
class Pin:
    """One pin of a library symbol, in the library's own coordinates."""

    number: str
    name: str
    kind: str
    unit: int
    x: float
    y: float
    angle: float


def _blocks(text: str) -> dict[str, str]:
    """Every `(symbol "name" ...)` at a library's top level, by name."""
    out: dict[str, str] = {}
    for match in re.finditer(r'\n\t\(symbol "([^"]+)"', text):
        start = match.start() + 1
        depth, i = 0, start
        while i < len(text):
            char = text[i]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
            elif char == '"':
                i += 1
                while text[i] != '"':
                    i += 2 if text[i] == "\\" else 1
            i += 1
        out[match.group(1)] = text[start : i + 1]
    return out


_LIBRARIES: dict[str, dict[str, str]] = {}


def _library(name: str) -> dict[str, str]:
    if name not in _LIBRARIES:
        path = library_root() / f"{name}.kicad_sym"
        if not path.exists():
            raise SystemExit(f"no such KiCad symbol library: {name}")
        _LIBRARIES[name] = _blocks(path.read_text(encoding="utf-8"))
    return _LIBRARIES[name]


def _flatten(library: str, name: str) -> str:
    """The symbol's own text, with an extended parent's drawing folded in."""
    blocks = _library(library)
    if name not in blocks:
        raise SystemExit(f"no symbol {name} in KiCad's {library} library")
    block = blocks[name]
    parent = re.search(r'\(extends "([^"]+)"\)', block)
    if parent is None:
        return block
    # TAKE THE PARENT WHOLE AND PUT THE CHILD'S PROPERTIES ON IT, which is what
    # KiCad itself does when it resolves an `extends`. Building the other way
    # round -- the child's body with the parent's drawing appended -- loses the
    # parent's pin-name and pin-number settings, and KiCad then reports every
    # such part as not matching its own library.
    out = _flatten(library, parent.group(1))
    out = out.replace(f'(symbol "{parent.group(1)}"', f'(symbol "{name}"', 1)
    out = out.replace(f'"{parent.group(1)}_', f'"{name}_')
    for prop in re.finditer(r'\n(\t\t\(property "([^"]+)".*?\n\t\t\))', block, re.S):
        pattern = r'\n\t\t\(property "' + re.escape(prop.group(2)) + r'".*?\n\t\t\)'
        if re.search(pattern, out, re.S):
            out = re.sub(pattern, "\n" + prop.group(1), out, count=1, flags=re.S)
        else:
            out = (
                out[: out.index('\n\t\t(symbol "')]
                + "\n"
                + prop.group(1)
                + (out[out.index('\n\t\t(symbol "') :])
            )
    return out


def symbol(lib_id: str) -> str:
    """One library symbol's definition, named by its lib_id, ready for a sheet.

    A schematic carries a copy of every symbol it places, under the full
    `Library:Name`, so the file opens on a machine that has never seen the
    library it came from.
    """
    library, name = lib_id.split(":", 1)
    block = _flatten(library, name)
    return block.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)


def pins(lib_id: str) -> dict[str, Pin]:
    """Every pin of a symbol, by pin number, in library coordinates."""
    library, name = lib_id.split(":", 1)
    block = _flatten(library, name)
    out: dict[str, Pin] = {}
    for unit_match in re.finditer(
        r'\(symbol "' + re.escape(name) + r'_(\d+)_\d+"(.*?)\n\t\t\)', block, re.S
    ):
        unit = int(unit_match.group(1))
        for pin in re.finditer(
            r"\(pin (\w+) \w+\s*\n\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)"
            r'.*?\(name "([^"]*)".*?\(number "([^"]*)"',
            unit_match.group(2),
            re.S,
        ):
            out[pin.group(6)] = Pin(
                number=pin.group(6),
                name=pin.group(5),
                kind=pin.group(1),
                unit=unit,
                x=float(pin.group(2)),
                y=float(pin.group(3)),
                angle=float(pin.group(4)),
            )
    return out


def units(lib_id: str) -> int:
    """How many drawable units the symbol has -- 1 for most, 3 for a dual op-amp."""
    return max((pin.unit for pin in pins(lib_id).values()), default=1)


def place(
    pin: Pin, at: tuple[float, float], angle: float = 0.0, mirror: str | None = None
) -> tuple[float, float]:
    """Where a pin lands on the sheet once its symbol is placed.

    Rotate counter-clockwise in library space, mirror if asked, then flip Y for
    the sheet. Verified against kicad-cli's netlist export; see the module note.
    """
    radians = math.radians(angle)
    cos, sin = math.cos(radians), math.sin(radians)
    x = pin.x * cos - pin.y * sin
    y = pin.x * sin + pin.y * cos
    if mirror == "x":
        y = -y
    elif mirror == "y":
        x = -x
    return (round(at[0] + x, 4), round(at[1] - y, 4))


def outward(
    pin: Pin, at: tuple[float, float], angle: float = 0.0, mirror: str | None = None
) -> tuple[float, float]:
    """The unit vector pointing away from the symbol along the pin, on the sheet.

    A stub, a label or a ground symbol hangs off the end of a pin, and this is
    which way that is. Taken from the pin's own drawn direction rather than from
    where it sits, because a symbol's origin is not always inside it.

    A KICAD PIN'S ANGLE POINTS INWARD, from its connection end back at the body
    it belongs to -- a resistor's pin 1 sits at y +3.81 and is drawn at 270, and
    270 is the way back down to the origin. So outward is the other way, and
    getting this backwards puts every ground symbol inside the part it grounds.
    """
    tip = place(pin, at, angle, mirror)
    inward = place(
        Pin(
            pin.number,
            pin.name,
            pin.kind,
            pin.unit,
            pin.x + math.cos(math.radians(pin.angle)),
            pin.y + math.sin(math.radians(pin.angle)),
            pin.angle,
        ),
        at,
        angle,
        mirror,
    )
    dx, dy = tip[0] - inward[0], tip[1] - inward[1]
    length = math.hypot(dx, dy) or 1.0
    return (round(dx / length), round(dy / length))
