# KCL and Zoo engine gotchas

Things this project has already learned the hard way, collected so nobody has to
learn them twice. Each one was hit while building the robot; the engineering log
in [`NOTES.md`](NOTES.md) has the surrounding story.

Add to this file whenever the engine refuses something, or accepts something and
produces the wrong thing.

## The one that matters most

**Mock execution does not exercise the booleans.** Every geometry limitation
below passes `tools/check.py` and the MCP `mock_execute_kcl` without a word of
complaint, and only fails when the real engine tries to build the solid. Mock
execution proves the KCL is valid; it does not prove the part exists.

So: mock-execute while iterating, engine-execute before believing anything about
geometry.

## The one that is worse than a refusal

**A boolean the engine accepts can still have built the wrong solid, and nothing
will tell you.** The rotor hub unioned its arm onto the output disc *after* the
disc had been drilled. The arm lies in the disc's own plane, so it filled four of
the six M3 holes straight back in — two buried outright, two half filled with
their counterbores ruined — leaving two usable bolts out of six on the joint that
carries the actuator's whole output torque. `tools/check.py` was clean. The
engine executed it without a murmur. `tools/mass.py` printed a number. It
survived several rebuilds that way and was found by eye in Design Studio.

A refusal is the good case: it stops you. This does not.

**So any feature that lives where two bodies overlap has to be looked at, not
assumed.** If you cut a hole, a pocket or a relief into a body that something
else is unioned to or interpenetrates, execution is not evidence. Get one of
these two before believing it:

- **See through it.** Render the part *on its own*, looking straight down the
  feature's axis, so empty background shows through. On its own matters: three
  renders of this hub were read wrongly because other structure sat behind the
  holes and made open ones look closed. `renders/` is untracked, so a one-line
  throwaway model that exports just the part is the cheapest way to isolate it.
- **Or measure across the change.** Take the volume before and after and check
  the difference is the size *and the sign* of the feature you meant to make.
  Wrong size or wrong sign means the engine did something else, whatever the
  picture looks like.

## Geometry the engine refuses

- **Blind pockets cut from a large combined solid.** Rejected. Make every cut on
  the simple body it belongs to, before anything is unioned.
- **Blind *cylindrical* pockets, full stop.** Rejected in the torso shell in
  either order, and unioning the ports into the cavity tool first does not help.
  A blind ***rectangular*** pocket in the same place is accepted. The cable ports
  are slots for exactly this reason, which suits a moulded connector anyway.
- **Holes must exit both ends.** A hole through a stepped solid is fine, but a
  cutter that stops inside the material is the blind-pocket case again. The cover
  screw cutters were originally too short and had to be run right through.
- **Blind cylinders ending inside a block** come back as `cannot handle this 3D
  subtraction yet`. Cutting the full block height instead is accepted: the lower
  part of the cylinder falls inside a pocket that is removed afterwards, so the
  finished part is identical.
- **A pocket cut into an already-hollowed shell.** Cut the pockets into the plain
  blank *first*, then hollow it. This is the ordering the torso shell needed and
  then the keel needed again.
- **A union whose two bodies share *both* of their faces in one axis.**
  Rejected as `cannot handle this 3D union yet`. The limb's rotor plate is
  exactly `rotorHubThickness` and sits exactly where the output disc sits, so
  its two x-faces are coplanar with the disc's; unioning them fails. The arm it
  replaced got away with the same construction because only its outer face was
  shared. One coincident face is tolerated, two are not — and this is the same
  family as the fillet cutter that was refused for being tangent to two faces of
  a block. The workaround is either to make one body wider than the other, or to
  leave them as interpenetrating bodies, which is what `limb.kcl` does.
- **Any feature cut through the plane where two bodies join.** The rotor hub's
  arm is coplanar with its output disc and used to cross the bolt circle, and
  every way of drilling that pattern was refused but one. Cut the pattern into
  both bodies and then union: refused, because the two then meet on the walls of
  six coincident cylinders. Union first and drill the result: `cannot handle this
  3D subtraction yet` — with the holes pre-cut or not, and with the bridge in the
  union or not. Cut an *oversized* relief into the crossing body so that no wall
  coincides and the disc's own material closes it back down: the union is
  **accepted**, and returns five holes open and one filled. That is the worst
  outcome of the three, because it looks like it worked. What works is not to
  have the overlap at all — the arm now stops below the bolt circle.
- **A union where one body's end face is part buried and part proud.** Rejected
  as `cannot handle this 3D union yet`. Truncating the rotor arm below the bolt
  circle left its top corners just outside the disc's edge while the middle of
  the same face was inside, and the union failed; narrowing the arm until the
  whole face sat inside the disc fixed it. Wholly inside is fine — the arm did
  that for years — and so is wholly outside. Half and half is not.
- **A cutter tangent to two faces of a block.** Rejected. A fillet drawn as a
  block minus a cylinder hits this every time; draw the profile with an `arc` in
  it instead and no boolean is needed at all.
- **A union of two hollow boxes meeting at right angles.** Rejected. The hip
  carrier, the torso hip mounts and the foot frame are therefore left as
  **interpenetrating bodies** rather than single solids. Every overlap is
  millimetres of real material, so a slicer that merges coincident shells prints
  each as the single part it is — but that has to be verified in the slicer
  before printing, and it means the exported STL is not manufacturing-ready on
  its own.

## Profiles that build the wrong shape

Both of these produce a solid, silently, so `tools/check.py` and the engine are
both happy and only a render shows the mistake.

- **`arc(start, end, center)` always sweeps counter-clockwise from start to
  end.** Write a quarter arc the other way round and you get the other three
  quarters of the same circle. A flange with a blend at each end, written
  backwards, came back as a dumbbell: a disc at each end joined by a thin bar.
  Check the sweep by taking the angle of `start` about `center`, the angle of
  `end`, and reading counter-clockwise between them. It costs nothing to put the
  arc in the sketch "backwards" relative to the way the outline is traversed --
  `coincident` is what wires the loop together, not declaration order -- so write
  each arc whichever way makes its counter-clockwise sweep the one you want.
- **`region(segments = [a, b])` traces `a` from its start to where it meets `b`,
  then turns `direction` at every corner until it comes back.** So the two
  segments have to *touch*, and `direction` has to be the way the outline is
  actually written: `CCW` for a counter-clockwise loop, `CW` for a clockwise one.
  Give it two segments on opposite sides of the profile and it still returns a
  region -- some other region -- and the part comes out empty or wrong.

## Mirroring

- **`mirror3d` copies, it does not transform.** The original stays in the scene,
  even in pipeline form, so a mirrored part measures double. `hide()` the source
  afterwards; the mirrored body survives and the hidden one drops out of both the
  render and the mass. `delete()` works too but lints as experimental.
- **`scale(x = -1)` is not a mirror.** It appears to reflect about the body's own
  centroid and leaves it where it started.
- **A 180° spin about Z is a true mirror only for a fore-and-aft symmetric part.**
  It flips X and Y together. The limb fails that test — its stator plate has a
  connector relief on one side — so the limbs are mirrored with `mirror3d`.

## Which way the robot faces

**+Y is forward, +Z is up, +X is the robot's right.** Fixed by `foot.kcl`, which
puts the rear pressure pads at y = −40 and the front pads at y = +51, and
confirmed by `walk_pose_check.kcl`, where the leading leg's knee swings to +Y.

**Zoo's camera view named "front" shows the robot's back**, because it puts the
camera on −Y looking back at the origin. That is the ordinary CAD convention
rather than a bug, and it is a good way to mislead yourself for ten minutes. The
tether entry was once drawn on the robot's front, between its shins; it executed
without complaint, and only a rendered back-and-front pair caught it.

`tools/views.py` names its views in the robot's frame instead, so `front` there
means the robot's front.

## What the measurement API can and cannot tell you

- **Volume and mass are trustworthy.** They have agreed with hand calculation.
- **The bounding box and centre of mass are not.** The same call returned a
  bounding box 173 mm long in y for a 115 mm foot. Do not quote extents or a
  centre of mass from it without checking them against the geometry.
- **Interpenetrating bodies are counted twice**, so a measured part comes out
  slightly heavy — which is at least the safe direction when checking a ceiling.

## Engine and MCP failures, and what they actually mean

- **`auth_token_missing` is a billing problem, not an authentication one.** The
  same call over REST returns HTTP 402 and says so. Check
  <https://zoo.dev/account/billing> rather than debugging the setup.
- **`Too many active connections, only 2 allowed per user`** means something else
  is holding an engine connection — Design Studio, the MCP server's modeling
  session, or another script. Close one and retry; the limit is per account, not
  per tool.
- **A `RequestError` against `api.zoo.dev/ws/modeling/commands`** is a dropped
  request rather than a KCL error. Retry it; the same file passes.
- **The MCP server reads `ZOO_API_TOKEN` once, when it is spawned.** After
  rotating the token, VS Code has to be restarted or calls keep using the old one.
- **A `CONNECT_TIMEOUT` after 30 s at MCP startup is a cold `uvx` cache**, not a
  credentials problem — the spawn spends its whole budget downloading packages.
  Warm it once by running `uvx zoo-mcp` from a shell, then restart VS Code. The
  timing tells the two apart: a billing failure comes back fast, this one runs
  out the clock.
- **The full assembly is slow on the engine.** `main.kcl` has taken over two
  minutes to execute and snapshot. That is normal, not a hang.

## Exporting one part out of a file that builds several

- **Export takes the whole scene, and there is no way to ask for one body.** So a
  file that builds a handed pair, or a shell and its cover, cannot be exported as
  one printable piece directly. The way round it is a wrapper scene that imports
  the piece and hides its siblings, which is what `tools/export.py` generates.
- **`hide()` does reach the exporter, not only the renderer.** Confirmed
  2026-08-31 on the eight-motor pelvis, which `torso.kcl` then built from 12
  bodies alongside a 1-body cover: isolating each gave a STEP with exactly 12 and
  exactly 1 `MANIFOLD_SOLID_BREP`, where a leak would have put 13 in both. Both
  hands of each mirrored pair likewise came out with mirrored x extents rather
  than the symmetric range a leak gives. That pelvis is now `walking_torso.kcl`
  and the six-motor one in `torso.kcl` is 7 bodies, so the numbers to compare
  against are the declared counts in the register, not the ones written here.
- **Do not assume it, though — count.** `tools/export.py` compares every written
  file against a declared body count in `tools/mass_budget.toml` and reports the
  bounding extents, and `--verify` repeats both checks on the files already on
  disk for free.
- **One body per `MANIFOLD_SOLID_BREP`, and per `PRODUCT`, and per
  `ADVANCED_BREP_SHAPE_REPRESENTATION`.** All three appear exactly once per solid
  in what this exporter writes, so counting two of them together reads as double.
- **`execute_and_export` wants a `FileExportFormat`, not the `*ExportOptions`
  class of the same name.** Passing `StepExportOptions()` fails with *not an
  instance of `FileExportFormat`*, before the engine is touched.

## Local tooling

`tools/check.py` runs the same KCL interpreter locally through the `zoo-kcl`
package, so mock execution, linting and formatting cost nothing, need no token
and work when the MCP server does not. `tools/mass.py`, `tools/views.py` and
`tools/export.py` do use the engine and do spend credits, though `export.py`'s
`--list`, `--mock` and `--verify` modes do not.
