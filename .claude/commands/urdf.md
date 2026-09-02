---
description: Regenerate the simulation URDF from the CAD and check it. Free, offline, no engine.
allowed-tools: Bash(uv run simulation/build_urdf.py:*), Bash(uv run simulation/check_model.py:*)
---

Rebuild the URDF and check it against the CAD:

```
uv run simulation/build_urdf.py $ARGUMENTS
uv run simulation/check_model.py
```

Both are free and offline. Dimensions are re-read from the KCL on every build,
so the kinematics can never be stale — but the meshes are engine output, and
`build_urdf.py` **refuses to build against a mesh older than the KCL it came
from**, naming the file that moved and printing the exact re-export command for
just the affected pieces. That export is the only metered step:

```
uv run tools/export.py --format stl --out simulation/meshes --pieces <the ones it named>
```

Only a printed part changing *shape* needs it. A change to a joint height, an
axis or a mass allowance does not — rebuild and the numbers move on their own.

Then:

- Read the pose check at the top of `check_model.py`. It drives the tree to the
  angles in `pose_check.kcl` and `squat_check.kcl` and compares where the wheel
  lands with where those scenes independently compute it. Agreement is real
  evidence: it exercises every link length, joint origin and axis sign at once,
  and a flipped sign shows up as tens of millimetres. A MISMATCH there means the
  model no longer describes the robot — say so and do not use the URDF.
- Report the mass and the delta the same way a `/mass` run would. This model and
  `tools/mass.py` differ on purpose by the interpenetration allowance, which the
  table names; anything beyond that is a part dropped or double-counted.
- Read the provenance table at the end before quoting any simulation result.
  Four fifths of this robot's mass has never been weighed, and that is what a
  trained policy is actually resting on.

Editing `simulation/urdf/wheeled_biped.urdf` by hand is always wrong. It carries
a do-not-edit banner and the next build overwrites it. Kinematics and masses
come from the CAD; anything that is a *choice* rather than a measurement —
joint travel, the actuator model, contact friction — belongs in
`simulation/robot.py` or `simulation/isaaclab/wheeled_biped_cfg.py`.
