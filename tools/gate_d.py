# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.9", "numpy", "trimesh"]
# ///
"""Gate D -- the kinematic chain, unchanged by the migration.

simulation/check_model.py is the best regression test in this project and it
survived the port without an edit to what it asserts. It drives the joint tree to
the angles of the two pose scenes and requires the wheel to land within
TOLERANCE_MM = 1e-6 of where those scenes independently compute it, which
exercises every link length, joint origin and axis sign at once.

    uv run tools/gate_d.py

WHAT MOVED, AND WHAT KEEPS THIS HONEST. Both halves of the comparison are Python
now: the tree is built by simulation/robot.py out of cad/dimensions.py, and the
pose is computed by cad/poses.py. Two Python modules agreeing with each other
would be weaker evidence than the KCL-against-port comparison this gate started
as -- so the pose is pinned separately. reference/golden/scenes.json is what the
KCL computed for these scenes, frozen before it was deleted, and tools/gate_f.py
holds cad/poses.py against it name by name at zero tolerance.

So the chain of evidence is: gate A pins the dimensions to the engine-era
reference, gate F pins the poses to it, and this gate requires the tree built
from the first to reach the positions computed by the second.

WHAT THIS GATE IS AND IS NOT. It proves the joint tree the simulation builds is
correct. It does not touch the meshes -- the inertia tensors are integrated from
exported geometry -- so a pass here means the kinematics are right, not that the
whole URDF is. `uv run simulation/check_model.py` is the fuller check, and it
needs the meshes exported first.

Free, offline, no engine.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "simulation"))


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    import check_model
    import robot as robot_model

    links, joints, dimensions = robot_model.build()
    problems = check_model.check_poses(joints, dimensions)

    print()
    if problems:
        for problem in problems:
            print(f"  {problem}")
        print("gate D: FAIL")
        return 1
    print("gate D: pass -- the tree lands where the check scenes put it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
