"""Read mechanical dimensions straight out of the KCL sources.

lib/parameters.kcl is the single source of mechanical dimensions for this project,
and a URDF with those numbers retyped into it is a second source that goes
stale the first time the CAD moves. So nothing here is typed in: this module
evaluates the top-level assignments in the KCL files and hands back a plain
name -> number mapping that the URDF generator reads.

WHAT IT UNDERSTANDS, AND WHAT IT DOES NOT. This is deliberately not a KCL
interpreter. It walks each file once, in order, and evaluates every assignment
that starts in column zero -- which is where parameters live and where nothing
else does, because sketch and function bodies are always indented. An
assignment it cannot evaluate (a sketch, a solid, a call into geometry) is
skipped rather than guessed at, so the mapping holds dimensions only.

UNITS. Every length comes back in MILLIMETRES and every angle in DEGREES,
matching the files themselves. Converting to the metres a URDF wants happens
once, at the point of writing, so that unit slips have exactly one place to
hide. Trigonometry takes degrees, as KCL's does.

Because a silently skipped line would look the same as a missing dimension,
build_urdf.py asserts the RELATIONSHIPS between the values it reads -- that the
hip height really is the two limbs plus the wheel radius, and so on -- rather
than asserting the numbers themselves. A parse failure breaks a relationship;
a legitimate design change does not.
"""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The files that between them carry every dimension this model needs. Order
# matters: a file may only use names the ones before it have defined.
SOURCES = (
    "lib/parameters.kcl",
    "lib/joint.kcl",
    "lib/torso_shell.kcl",
    "lib/wheeled_parameters.kcl",
    "wheeled_electronics.kcl",
)

# `name = expr` or `export name = expr`, starting hard against the left margin.
ASSIGNMENT = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")

# The same, for the palette: `export printedOrange = "#d9822b"`. The KCL hands
# every body its colour through `appearance(...)`, so the robot already has a
# palette and the URDF has no business inventing a second one.
COLOR = re.compile(
    r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"#([0-9a-fA-F]{6})"\s*$'
)

# KCL writes units as a suffix on the literal: 46mm, 45deg, 2.4mm.
UNIT_SUFFIX = re.compile(r"(\d(?:\.\d+)?(?:[eE][-+]?\d+)?)(mm|cm|m|deg|rad)\b")

# Lengths are kept in millimetres and angles in degrees, so mm and deg are
# identities and the others scale onto them.
UNIT_SCALE = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "deg": 1.0,
    "rad": 180.0 / math.pi,
}

# KCL's trigonometry is in degrees, so this module's is too.
FUNCTIONS = {
    "cos": lambda x: math.cos(math.radians(x)),
    "sin": lambda x: math.sin(math.radians(x)),
    "tan": lambda x: math.tan(math.radians(x)),
    "sqrt": math.sqrt,
    "abs": abs,
    "min": min,
    "max": max,
}


class Unevaluatable(Exception):
    """The line is not a dimension. Skip it and move on."""


def _strip_units(source: str) -> str:
    return UNIT_SUFFIX.sub(
        lambda m: repr(float(m.group(1)) * UNIT_SCALE[m.group(2)]), source
    )


def _rewrite_pow(source: str) -> str:
    """KCL spells exponentiation `pow(base, exp = n)`; Python spells it `**`."""
    return re.sub(r"\bpow\(\s*([^,()]+?)\s*,\s*exp\s*=\s*([^,()]+?)\s*\)", r"((\1)**(\2))", source)


def _evaluate(node: ast.AST, names: dict[str, float]) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise Unevaluatable("not a number")
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in names:
            raise Unevaluatable(f"unknown name {node.id}")
        return names[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate(node.operand, names)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left, names)
        right = _evaluate(node.right, names)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left**right
        raise Unevaluatable("unsupported operator")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
            raise Unevaluatable("unsupported call")
        if node.keywords:
            raise Unevaluatable("keyword argument")
        args = [_evaluate(arg, names) for arg in node.args]
        return float(FUNCTIONS[node.func.id](*args))
    raise Unevaluatable(f"unsupported syntax {type(node).__name__}")


def _value_of(expression: str, names: dict[str, float]) -> float:
    prepared = _rewrite_pow(_strip_units(expression))
    try:
        tree = ast.parse(prepared, mode="eval")
    except SyntaxError as exc:  # a sketch, a pipeline, a list -- not a dimension
        raise Unevaluatable(str(exc)) from exc
    return _evaluate(tree.body, names)


# `import * from "lib/parameters.kcl"`, `import a, b from "lib/joint.kcl"`.
IMPORT = re.compile(r'^\s*import\s+.+?\s+from\s+"([^"]+)"')


def import_closure(filename: str, root: Path = ROOT) -> set[Path]:
    """Every KCL file that `filename` is built from, including itself.

    A piece's geometry depends on far more than the file that exports it: a
    limb is drawn by lib/limb.kcl out of lib/joint.kcl's discs on lib/parameters.kcl's
    dimensions, and a change to any of those changes the printed part. This
    walks the import graph so that "is this mesh still current" can be asked
    about the right set of files rather than about one of them.
    """
    seen: set[Path] = set()
    pending = [filename]
    while pending:
        name = pending.pop()
        path = root / name
        if path in seen or not path.exists():
            continue
        seen.add(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            match = IMPORT.match(line)
            if match:
                pending.append(match.group(1))
    return seen


def load(sources: tuple[str, ...] = SOURCES, root: Path = ROOT) -> dict[str, float]:
    """Every dimension the listed KCL files define, in millimetres and degrees."""
    names: dict[str, float] = {}
    for filename in sources:
        text = (root / filename).read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith((" ", "\t", "//", "@")) or not line.strip():
                continue
            match = ASSIGNMENT.match(line)
            if match is None:
                continue
            name, expression = match.group(1), match.group(2)
            # A trailing line comment is common on these; drop it.
            expression = expression.split("//")[0].strip()
            try:
                names[name] = _value_of(expression, names)
            except Unevaluatable:
                continue
    return names


def load_colors(
    sources: tuple[str, ...] = SOURCES, root: Path = ROOT
) -> dict[str, tuple[float, float, float]]:
    """Every `name = "#rrggbb"` the listed KCL files define, as fractions of 1.

    lib/parameters.kcl carries the robot's palette and wheeled_electronics.kcl adds
    the board colours, and both are read here for the same reason the
    dimensions are: a colour retyped into the URDF is a second source of it.
    """
    colors: dict[str, tuple[float, float, float]] = {}
    for filename in sources:
        for line in (root / filename).read_text(encoding="utf-8").splitlines():
            match = COLOR.match(line)
            if match:
                hexadecimal = match.group(2)
                colors[match.group(1)] = tuple(
                    int(hexadecimal[i : i + 2], 16) / 255.0 for i in (0, 2, 4)
                )
    return colors


if __name__ == "__main__":
    import sys

    found = load()
    wanted = sys.argv[1:]
    for key in sorted(found):
        if not wanted or any(w.lower() in key.lower() for w in wanted):
            print(f"{key:<34} {found[key]:12.4f}")
    print(f"\n{len(found)} dimensions read from {len(SOURCES)} files.")
