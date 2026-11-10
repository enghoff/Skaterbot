# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d==0.11.1", "cadquery-ocp-novtk==7.9.3.1.1", "shapely>=2.0", "matplotlib>=3.8", "numpy>=1.26"]
# ///
"""Write the carrier's netlist out as a KiCad schematic, one sheet, all of it.

    uv run electrical/carrier_sch.py

electrical/carrier.py is the netlist and it is the thing that is checked. This
file draws it, so that somebody can read the board the way an electrical drawing
is read rather than by following a dictionary of nets in a Python file -- and so
that KiCad's own ERC gets a second look at it.

IT IS DRAWN WITH LABELS AND NOT WITH WIRES, and that is a deliberate choice
rather than a shortcut. A net here is a name shared by up to thirteen pins spread
across a board; drawing that as a line between symbols means routing a schematic,
which is the same problem as routing the board and produces a drawing nobody can
follow. So every pin gets a stub and the net's name on the end of it, which is
how a dense board is drawn by hand anyway. Two pins with the same name are the
same net, and KiCad joins them.

EVERY PIN IS PASSIVE, which is the honest declaration. Marking supply pins as
power inputs would make ERC ask for power flags and then report on a model of
this board that nobody maintains; what is actually checked -- that every pin is
on a net, that no net is a dead end, that no pin is on two nets, and that the
copper reaches all of it -- is checked in carrier.py and carrier_pcb.py against
the real geometry. What ERC adds here is a reading of the drawing itself.

THE SHEET IS A2 and the symbols are laid out in columns by kind: the core board
alone on the left because it has forty-eight pins, then the transceivers and the
links, the modules and the power parts, the connectors, and the passives.
"""

from __future__ import annotations

import sys
import uuid as uuidlib
from dataclasses import replace
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "electrical"))

import carrier  # noqa: E402

OUT = ROOT / "electrical" / "kicad"

PITCH = 2.54
STUB = 5.08
FONT = "(effects (font (size 1.27 1.27)))"


# WHERE EACH PART IS DOCUMENTED. A symbol carries its datasheet as a property, so
# double-clicking a part in KiCad opens the page it was designed from. Every one
# of these is in reference/DATASHEETS.md as well, which is where the reasoning
# about which document is authoritative lives.
DATASHEETS = {
    "A1": "https://github.com/WeActStudio/WeActStudio.STM32G474CoreBoard",
    "A2": "https://www.mateksys.com/?portfolio=bec12s-pro",
    "A3": "https://www.ti.com/lit/ds/symlink/ina226.pdf",
    "U1": "https://ww1.microchip.com/downloads/en/DeviceDoc/MCP2561-2FD-Hi"
    "gh-Speed-CAN-Flexible-Data-Rate-Transceiver-20005284A.pdf",
    "U2": "https://ww1.microchip.com/downloads/en/DeviceDoc/MCP2561-2FD-Hi"
    "gh-Speed-CAN-Flexible-Data-Rate-Transceiver-20005284A.pdf",
    "U3": "https://ww1.microchip.com/downloads/en/DeviceDoc/MCP2561-2FD-Hi"
    "gh-Speed-CAN-Flexible-Data-Rate-Transceiver-20005284A.pdf",
    "F1": "https://www.littelfuse.com/assetdocs/pptc-through-hole-rxef-dat"
    "asheet?assetguid=53c5fbc6-c9d5-4b4b-b2a9-0d6b2b17e9d5",
}


def board_parts():
    """Only the pins landed on this PCB; SWD P3 stays on the core board."""
    return [
        replace(
            part,
            pins={
                pin: name
                for pin, name in part.pins.items()
                if (part.refdes, pin) not in carrier.OFF_BOARD_PINS
            },
        )
        for part in carrier.PARTS
    ]


def _uuid(seed: str) -> str:
    """A stable uuid, so that rewriting the file does not churn every id."""
    return str(uuidlib.uuid5(uuidlib.NAMESPACE_URL, f"carrier-sch/{seed}"))


ROOT_UUID = _uuid("sheet/root")


def net_of_pin() -> dict[tuple[str, str], str]:
    return {
        endpoint: net
        for net, endpoints in carrier.NETS.items()
        for endpoint in endpoints
    }


def sides(part: carrier.Part) -> tuple[list[str], list[str]]:
    """Which pins go down the left of the symbol and which down the right.

    Up to eight and they all go on the left, which reads as a connector and is
    what most of this board is. More than that and they split in order, so the
    core board comes out as its two headers side by side.
    """
    pins = list(part.pins)
    if len(pins) <= 8:
        return pins, []
    half = (len(pins) + 1) // 2
    return pins[:half], pins[half:]


def symbol_width(part: carrier.Part) -> float:
    """Wide enough for the pin names inside it, both columns of them.

    A pin name is drawn inside the box from its own side, so a two-column symbol
    needs room for a name from the left and a name from the right without the
    two meeting in the middle. The core board is the one that cares: 24 pins a
    side, and at 25 mm wide its two columns of names run into each other.
    """
    left, right = sides(part)
    widest = [
        max((len(part.pins[pin]) for pin in column), default=0)
        for column in (left, right)
    ]
    wanted = 1.5 * (widest[0] + widest[1]) + 8.0
    return max(25.4, PITCH * round(wanted / PITCH))


def stub_length(part: carrier.Part) -> float:
    """How far the pin stands off the box: far enough to print its number on.

    Most of this board numbers its pins 1 to 8. The core board numbers them
    P1-13, and five characters do not fit over a 5 mm stub.
    """
    longest = max((len(pin) for pin in part.pins), default=1)
    return STUB if longest <= 3 else STUB + PITCH


def lib_symbol(
    part: carrier.Part, indent: str = "    ", prefix: str = "carrier:"
) -> str:
    """One symbol for one part: a box, its pins, and nothing else.

    Every part on this board is its own symbol rather than an instance of a
    library one. A 1 x 8 header and a DIP-8 socket are the same drawing and
    different pin names, and the names are the whole value of the sheet.
    """
    left, right = sides(part)
    width = symbol_width(part)
    tall = max(len(left), len(right))
    height = PITCH * (tall + 1)
    half_w, half_h = width / 2, height / 2
    stub = stub_length(part)
    inner = indent + "  "
    out = [
        f'{indent}(symbol "{prefix}{part.refdes}"',
        f"{inner}(pin_names (offset 0.762)) (in_bom yes) (on_board yes)",
        f'{inner}(property "Reference" "{part.refdes}"'
        f" (at 0 {half_h + 2.54:.2f} 0) {FONT})",
        f'{inner}(property "Value" "{part.partNumber}"'
        f" (at 0 {-half_h - 2.54:.2f} 0) {FONT})",
        f'{inner}(property "Footprint" "carrier:{part.refdes}" (at 0 0 0)'
        " (effects (font (size 1.27 1.27)) hide))",
        f'{inner}(property "Datasheet" "{DATASHEETS.get(part.refdes, "")}"'
        " (at 0 0 0) (effects (font (size 1.27 1.27)) hide))",
        f'{inner}(property "Description" "{part.description.replace(chr(34), chr(39))}"'
        " (at 0 0 0) (effects (font (size 1.27 1.27)) hide))",
        f'{inner}(symbol "{part.refdes}_0_1"',
        f"{inner}  (rectangle (start {-half_w:.2f} {half_h:.2f})"
        f" (end {half_w:.2f} {-half_h:.2f})"
        "    (stroke (width 0.254) (type default)) (fill (type background)))",
        f"{inner})",
        f'{inner}(symbol "{part.refdes}_1_1"',
    ]
    for pins, sign, angle in ((left, -1, 0), (right, 1, 180)):
        for row, pin in enumerate(pins):
            y = half_h - PITCH * (row + 1)
            x = sign * (half_w + stub)
            name = part.pins[pin].replace('"', "")
            out.append(
                f"{inner}  (pin passive line (at {x:.2f} {y:.2f} {angle})"
                f" (length {stub:.2f})"
                f' (name "{name}" {FONT}) (number "{pin}" {FONT}))'
            )
    out += [f"{inner})", f"{indent})"]
    return "\n".join(out)


def placed_symbol(part: carrier.Part, at: tuple[float, float]) -> list[str]:
    """The symbol on the sheet, with a stub and a net label on every pin."""
    left, right = sides(part)
    width = symbol_width(part)
    tall = max(len(left), len(right))
    height = PITCH * (tall + 1)
    half_w, half_h = width / 2, height / 2
    stub = stub_length(part)
    x, y = at
    nets = net_of_pin()
    out = [
        f'  (symbol (lib_id "carrier:{part.refdes}") (at {x:.2f} {y:.2f} 0) (unit 1)',
        "    (in_bom yes) (on_board yes) (dnp no)",
        f'    (uuid "{_uuid("sym/" + part.refdes)}")',
        f'    (property "Reference" "{part.refdes}"'
        f" (at {x:.2f} {y - half_h - 2.54:.2f} 0) {FONT})",
        f'    (property "Value" "{part.partNumber}"'
        f" (at {x:.2f} {y + half_h + 2.54:.2f} 0) {FONT})",
        f'    (property "Footprint" "carrier:{part.refdes}" (at {x:.2f} {y:.2f} 0)'
        " (effects (font (size 1.27 1.27)) hide))",
    ]
    for pin in part.pins:
        out.append(f'    (pin "{pin}" (uuid "{_uuid(f"pin/{part.refdes}/{pin}")}"))')
    out += [
        '    (instances (project "carrier"',
        f'      (path "/{ROOT_UUID}" (reference "{part.refdes}") (unit 1))',
        "    ))",
        "  )",
    ]
    for pins, sign, label_angle in ((left, -1, 180), (right, 1, 0)):
        for row, pin in enumerate(pins):
            py = y + PITCH * (row + 1) - half_h
            px = x + sign * (half_w + stub)
            end = px + sign * PITCH
            out.append(
                f"  (wire (pts (xy {px:.2f} {py:.2f}) (xy {end:.2f} {py:.2f}))"
                " (stroke (width 0) (type default))"
                f' (uuid "{_uuid(f"wire/{part.refdes}/{pin}")}"))'
            )
            net = nets.get((part.refdes, pin))
            if net is None:
                out.append(
                    f"  (no_connect (at {end:.2f} {py:.2f})"
                    f' (uuid "{_uuid(f"nc/{part.refdes}/{pin}")}"))'
                )
                continue
            justify = "right" if sign < 0 else "left"
            out.append(
                f'  (label "{net}" (at {end:.2f} {py:.2f} {label_angle})'
                f" (effects (font (size 1.27 1.27)) (justify {justify} bottom))"
                f' (uuid "{_uuid(f"label/{part.refdes}/{pin}")}"))'
            )
    return out


# WHERE EACH PART GOES ON THE SHEET. By kind, left to right, because that is the
# order somebody reads the board in: what computes, what talks on the bus, what
# it is made of, what plugs into it, and what hangs off a rail.
COLUMNS = [
    ("the controller", lambda r: r == "A1"),
    ("the buses", lambda r: r[0] == "U" or r == "JP1"),
    ("power and sense", lambda r: r in ("A2", "A3", "F1", "C1", "C9")),
    ("what plugs in", lambda r: r[0] == "J" and r != "JP1"),
    ("decoupling and pull-ups", lambda r: r[0] in "CR"),
]
COLUMN_X = [68.58, 218.44, 327.66, 449.58, 550.926]
TOP_Y = 40.64
GAP = 12.7
# KiCad joins a wire to a pin only where both land on its connection grid, which
# is 1.27 mm. Everything below is built out of 2.54 and 1.27, so the only thing
# that can push a pin off it is where a symbol is put; hence this.
GRID = 1.27


def snap(value: float) -> float:
    return round(value / GRID) * GRID


def layout() -> list[tuple[carrier.Part, tuple[float, float]]]:
    placed = []
    taken: set[str] = set()
    for (_, belongs), x in zip(COLUMNS, COLUMN_X):
        y = TOP_Y
        for part in board_parts():
            if part.refdes in taken or not belongs(part.refdes):
                continue
            taken.add(part.refdes)
            left, right = sides(part)
            height = PITCH * (max(len(left), len(right)) + 1)
            placed.append((part, (snap(x), snap(y + height / 2))))
            y += height + GAP
    missing = [p.refdes for p in board_parts() if p.refdes not in taken]
    if missing:
        raise SystemExit(f"no column for {missing}")
    return placed


def build() -> str:
    placed = layout()
    body = [
        "(kicad_sch",
        "  (version 20230121)",
        '  (generator "carrier_sch.py")',
        f'  (uuid "{ROOT_UUID}")',
        '  (paper "A2")',
        "  (title_block",
        '    (title "Skaterbot controller carrier")',
        f'    (date "{date.today().isoformat()}")',
        '    (company "generated by electrical/carrier_sch.py -- do not edit")',
        '    (comment 1 "Netlist: electrical/carrier.py. Board: electrical/'
        'carrier_pcb.py.")',
        '    (comment 2 "Nets are joined by label, not by wire. Same name, same net.")',
        "  )",
        "  (lib_symbols",
    ]
    for part, _ in placed:
        body.append(lib_symbol(part))
    body.append("  )")
    for part, at in placed:
        body += placed_symbol(part, at)
    body += [
        '  (sheet_instances (path "/" (page "1")))',
        ")",
    ]
    return "\n".join(body) + "\n"


def library() -> str:
    """The same symbols again, as a library KiCad can resolve the sheet against.

    A schematic carries a copy of every symbol it uses, which is what lets it
    open anywhere -- but KiCad still warns on every part whose library it cannot
    find, and twenty-six warnings hide the one that matters. So the library is
    written beside the sheet and registered in a project-local table.
    """
    out = [
        "(kicad_symbol_lib",
        "  (version 20231120)",
        '  (generator "carrier_sch.py")',
    ]
    for part in board_parts():
        out.append(lib_symbol(part, indent="  ", prefix=""))
    out.append(")")
    return "\n".join(out) + "\n"


SYM_LIB_TABLE = """(sym_lib_table
  (version 7)
  (lib (name "carrier")(type "KiCad")(uri "${KIPRJMOD}/carrier.kicad_sym")(options "")(descr "The carrier's own symbols, written by electrical/carrier_sch.py"))
)
"""


def main() -> int:
    faults = carrier.check()
    if faults:
        print("carrier netlist: FAILED, not drawing a schematic of a broken netlist")
        for fault in faults:
            print(f"  {fault}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "carrier.kicad_sch"
    path.write_text(build(), encoding="utf-8")
    (OUT / "carrier.kicad_sym").write_text(library(), encoding="utf-8")
    # THE LIBRARY TABLE IS KICAD'S FILE, NOT OURS, AND IT IS ONLY SEEDED HERE.
    # KiCad reads a project's sym-lib-table once, when the project opens, and
    # writes its own back when you touch Manage Symbol Libraries. Rewriting it
    # on every run meant the generator and the editor took turns clobbering each
    # other, and an editor that had the project open before this file first
    # existed never saw it at all -- which shows up as "the current
    # configuration does not include the symbol library", with the schematic's
    # symbols unresolvable. So it is written when it is absent or when it has
    # lost the carrier entry, and otherwise left exactly as KiCad left it.
    table = OUT / "sym-lib-table"
    if not table.exists() or '(name "carrier")' not in table.read_text(
        encoding="utf-8"
    ):
        table.write_text(SYM_LIB_TABLE, encoding="utf-8")
    pins = sum(len(p.pins) for p in board_parts())
    print(f"wrote {path}")
    print(f"  {len(board_parts())} symbols, {pins} pins, {len(carrier.NETS)} nets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
