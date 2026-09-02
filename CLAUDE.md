# Reporting

Report in plain English.

Write for the person who owns the rover but does not carry its code in their head. They
want the conclusion and the decision, not the workings.

- Lead with what is the case now: what works, what does not, and what it means for the
  project.
- Anything they cannot act on — the investigation, the options weighed, the names of
  files and settings — is a supporting clause at most, and usually is not needed at all.
- Say plainly when something is unproven, failed, or was skipped.
- Two sentences beat two paragraphs.
- Finish with the next step if there is one.

# CAD work

This repository is a Zoo Design Studio / KCL project: plain-text parametric CAD.
Zoo MCP is available, which means the actual Zoo CAD engine is reachable. Use it.
Never conclude a KCL change is good because it looks right — syntactically
plausible KCL is routinely invalid, and only execution tells you.

## Validate every change, cheaply first

There are two kinds of execution and the difference matters:

- **Mock execution** runs the full KCL interpreter locally. It is free and fast,
  and it still catches real errors: bad arguments, type errors, unresolved
  imports, broken sketch constraints. Use it as the default check, and on every
  file you touched. `/check` sweeps the whole project this way in a couple of
  seconds; `mock_execute_kcl` over MCP does one file at a time.
- **Engine execution** produces real geometry. It is **metered against the Zoo
  account's API credits**, so reach for it when geometry actually has to be
  correct — a change to a profile, a transform, a clearance — and not as a
  reflex after every edit. `execute_kcl` over MCP, or `/views` for a rendered
  sheet and `/mass` for the mass roll-up.

So: mock-execute while iterating, engine-execute to confirm the result. Resolve
every execution error before reporting a change as complete.

Mock execution **never evaluates the booleans**, so a cut this engine will
refuse passes it silently. [`docs/KCL_GOTCHAS.md`](docs/KCL_GOTCHAS.md) lists
every refusal this project has already hit — read it before designing a pocket,
a hole or a union, and add to it when you find a new one.

## A boolean that succeeds is not a boolean that worked

Worse than a refusal is a boolean the engine **accepts** having built the wrong
solid. Union a body onto a disc after the disc is drilled and the holes are
filled back in, and nothing reports it: `/check` is clean, the engine executes,
`/mass` prints a number. The rotor hub carried four filled bolt holes that way
through several rebuilds, on the joint that takes the actuator's full torque.

So for any feature that lives where two bodies overlap — a hole, a pocket, a
relief in a plane something else is unioned to or interpenetrates — **execution
is not evidence**. Confirm the feature exists, by one of:

- rendering the part **on its own**, looking straight down the feature's axis so
  empty background shows through it. Not in its assembly: structure behind a hole
  makes an open one look closed, which has already wasted a session's renders.
- or measuring volume across the change and checking the difference is the size
  and the sign of the feature you intended.

Say which of the two you did when reporting the change. "It executed" is not an
answer, and neither is "it looks right".

## Tools in this repository

Six commands, run with `uv run`, which fetches what they need on its own. Five
are in [`tools/`](tools/) and are about the CAD; the sixth is in
[`simulation/`](simulation/) and is about what the CAD is turned into.

| | | |
|---|---|---|
| `/check` | `tools/check.py` | mock-execute, lint and format-check every KCL file. Free, offline, no token. Works when the MCP server does not. |
| `/mass` | `tools/mass.py` | measure the printed parts and roll the robot's mass up against its 2 300 g ceiling, with the delta from the committed baseline. Engine, metered. |
| `/views` | `tools/views.py` | render a model from several sides, named in the robot's frame rather than the camera's. Engine, metered. |
| `/cache` | `tools/clear_cache.py` | clear Design Studio's caches when its model index goes bad and it opens on stale geometry. Free, offline, no engine. Refuses while the app is running. |
| `/step` | `tools/export.py` | write one STEP file per printable piece into `exports/`, checking each against its declared body count. Engine, metered. |
| `/urdf` | `simulation/build_urdf.py` | regenerate the simulation URDF from the CAD and check it against the pose scenes. Free, offline, no engine. |

Report the mass delta of every geometry change, and make `/check` clean before
saying a change is done.

## The simulation model is downstream of the CAD, never beside it

[`simulation/`](simulation/) turns the CAD into a URDF the wheeled robot can be
simulated and trained in. Nothing in it is a second copy of a dimension: the
kinematics are read out of the KCL by `simulation/kcl_params.py`, the printed
masses and inertia tensors are integrated from the exported meshes, and the
bought masses come from `tools/mass_budget.toml`. **A change to the CAD is
followed by regenerating it, not by editing the URDF**, which carries a
do-not-edit banner for that reason.

`/urdf` is the whole workflow, and it is free. It refuses to build against a
mesh older than the KCL it came from, names the file that moved, and prints the
re-export command for just the affected pieces — which is the only metered step,
and is needed only when a printed part changes SHAPE. A joint height, an axis or
a mass allowance moving needs no export at all.

`check_model.py` is the regression test. It drives the tree to the exact angles
in `pose_check.kcl` and `squat_check.kcl` and checks the wheel lands where those
scenes independently compute it, which exercises every link length, joint origin
and axis sign at once. It also totals the robot's mass **by provenance**, and
that table is the point: four fifths of this robot has never been on a scale, so
a simulation result is worth what those figures are worth and no more.

Two things the CAD frame and a URDF disagree about, both handled in one place
each and both easy to reintroduce by hand. The CAD is +Y forward and +X to the
robot's right; a URDF is +X forward, +Y left. And the printed parts export as
several interpenetrating shells, so simply adding their volumes counts the
overlaps twice — `tools/mass.py` accepts that bias on purpose because it errs
upward against a ceiling, but the simulation resolves the union instead, which
is 19 g lighter across the robot.

## The models are the regression suite

`main.kcl` is the neutral 339 mm assembly and exports `robotAssembly`. **On this
branch it is the six-motor wheeled robot**: hip pitch, knee and a driven wheel
per leg, with no hip roll at all. The walking robot is `walking_main.kcl` beside
it, unchanged and still the `main.kcl` of the `main` branch.

The two robots no longer share a pelvis. `torso.kcl` is the six-motor one, whose
hip pitch clevises are rooted straight in its shell floor; `walking_torso.kcl` is
the eight-motor one, with hip roll clevises, a keel and cheek gussets. They are
no longer even the same size: 125 x 68 x 65 against 118 x 68 x 106. What they
still share is a design rather than a part, so `torso_shell.kcl` holds the lid
and the cover boss as FUNCTIONS taking a box size, and a change to the lid is one
change and not two.

The six-motor torso's height is not a chosen number. It is derived in
`wheeled_parameters.kcl` from what has to fit inside, and `wheeled_electronics.kcl`
draws those boards so the packing can be looked at rather than asserted --
`torso_packing_check.kcl` is that scene. **Anything that changes a reserved
volume changes the robot's height**, which is the opposite of how it worked
while the torso was 106 mm.

Four more files are independent top-level models that exercise the same modules
in other configurations:

- `pose_check.kcl` — crouched stance with one wheel lifted, for sagittal
  clearance and joint-chain validation
- `squat_check.kcl` — the deepest squat the knee stop allows with both wheels
  still on the ground, which is where a Ø80 wheel comes closest to its own thigh
- `knee_limit_check.kcl` — the knee at its 110° hard stop
- `knee_prelimit_check.kcl` — the same knee at 100°, just before contact
- `torso_packing_check.kcl` — the pelvis with its lid off and the four payload
  items standing in it, which is the only place the 65 mm torso's height is
  actually justified rather than asserted

The knee checks are limb-against-limb and belong to both robots. Three further
scenes — `walk_pose_check.kcl`, `roll_limit_check.kcl` and
`torque_limit_pose.kcl` — are about walking specifically and still carry the
walking geometry; they import `walking_torso.kcl` and `walking_hip_carrier.kcl`,
which is what marks them. `roll_limit_check.kcl` no longer describes any joint
this robot has. **The wheeled robot's torque envelope has not been re-derived**,
and that answer does change with wheels.

A change to `parameters.kcl` or to any shared module reaches all of them.
Executing `main.kcl` alone is not sufficient evidence and must not be reported as
if it were — the pose and knee-limit checks exist precisely to catch interference
that the neutral stance hides.

## Dimensions live in parameters.kcl

`parameters.kcl` is the single source of mechanical dimensions, and its comments
carry the provenance — which vendor STEP, which 2D print, which measurement, and
where two sources were cross-checked against each other. Honour that:

- Keep important dimensions as named exported parameters. Do not inline magic
  numbers into part files.
- Never delete or weaken a provenance comment. If a dimension changes, say where
  the new value came from in the same style.
- Where a dimension comes from vendor geometry, it is in `reference/` — that
  directory is a tracked input, not an export.
- Prefer reusable functions and modules over duplicated geometry, and preserve
  the existing parametric relationships rather than substituting constants.

Avoid destructive rewrites unless they materially simplify the model, and
summarize dimensional or structural changes after each substantial edit.

Do not commit unless asked.

## Failure modes worth recognising

- The engine rejecting work with `auth_token_missing` is **a billing problem, not
  an authentication one**. The same call over REST returns HTTP 402 and says so.
  Check https://zoo.dev/account/billing rather than debugging the setup.
- The MCP server reads `ZOO_API_TOKEN` once, when it is spawned. After rotating
  the token, VS Code has to be restarted or engine calls keep using the old one.
- `Too many active connections, only 2 allowed per user` means something else
  holds an engine connection — Design Studio, an MCP modeling session, or another
  script. It is a queueing problem, not a fault.

[`docs/KCL_GOTCHAS.md`](docs/KCL_GOTCHAS.md) collects these along with every
geometry refusal, and `docs/claude-code-zoo-design-studio-mcp.md` has the full
setup and verification detail.
