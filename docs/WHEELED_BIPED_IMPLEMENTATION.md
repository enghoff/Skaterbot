# Wheeled-Biped Implementation Branch

**Branch:** `feature/wheeled-biped`
**Status:** the wheeled robot is now this branch's `main.kcl`; geometry executes on the engine and the mass is measured
**Walking robot:** preserved as `walking_main.kcl`, unchanged, and still `main.kcl` on the `main` branch

This document records what has been implemented from [`WHEELED_BIPED_ANALYSIS.md`](WHEELED_BIPED_ANALYSIS.md), what has been verified and how, and what remains open.

---

## 1. Architecture

The conservative conversion, per leg, on the same eight DAMIAO DM-J3507-2EC actuators the walking robot used:

```text
hip pitch -> knee pitch -> wheel
```

The ankle actuator becomes the wheel motor. Nothing is added: no extra motor, gearbox or driver.

Hip roll has since been deleted outright. `torso.kcl` is now the six-motor pelvis — one closed box from the hip pitch axes to the cover, with each hip pitch clevis rooted in its floor — and the eight-motor pelvis moved to `walking_torso.kcl` for the walking robot. The prototype hanger that was going to bridge between the two is gone; closing the freed volume made it unnecessary, because the shell floor simply came down 51 mm to meet the saddle.

---

## 2. The wheel is bought, not printed

The wheel is an **off-the-shelf 80 × 24 mm inline-skate wheel**. That was the right answer to "is there something we can buy": the size the geometry wanted is the commonest stocked skate size, it comes with a crowned polyurethane tread in a choice of durometers, and it costs about what a bolt costs.

There is no vendor STEP to import — skate wheels are a consumer part and nobody publishes CAD for them — so `skate_wheel.kcl` models one from its standard dimensions. What is standard is the *interface*, because the bearing fixes it: every wheel in this size takes two 608 bearings, 8 × 22 × 7 mm, pressed into a Ø22 seat at each end of a 24 mm hub. Those numbers are the same across brands and the adapter depends only on them. The hub's Ø45 outside diameter and the 20 mm crown radius are representative rather than standard, and both are marked in `wheeled_parameters.kcl` as needing calipers on the wheel that is actually bought.

**The bearings are thrown away.** A direct drive has one bearing — the actuator's own output bearing — and a second race in series with it would only add slop. Pulling the 608s leaves a clean Ø22 bore through the hub, which is what the adapter fills.

### How the wheel is driven

`wheel_adapter.kcl` is the printed part: the shared output disc from `joint.kcl`, a Ø22 spigot that fills the hub bore, and a plug tying the two together. The hub lands flat on the disc and one M5 on the axis clamps it there through a Ø30 washer.

Torque crosses that **clamped face**, not the spigot. An M5 at a modest 1 kN preload on the disc's r11–r18 annulus is worth about 4 Nm of friction against the actuator's 3 Nm peak. A press fit alone would have depended on how the print came off the bed, which is not a thing to hang a drive on.

### The six scallops

The spigot carries six axial scallops on the output bolt centres, and they are not decoration. The actuator's own mounting screws sit on Ø24; the wheel bore that has to pass over them is Ø22. A plain spigot walls its own mounting screws in and **the adapter cannot be fitted to the motor at all**. A 2.5 mm hex key is 2.89 mm across corners, so at r12 its shaft sweeps r10.56 to r13.44 and the spigot's r11 surface stands a fraction of a millimetre inside that. The scallops open the path down the spigot's whole length; what is left is 19 mm of Ø22 on six pads, which is ample, because the spigot only centres the wheel.

---

## 3. What was verified, and how

Everything below was run on this branch, not asserted.

| Check | Result |
|---|---|
| `/check` — mock-execute, lint, format, every file | 32/32 execute, lint clean, formatting clean |
| `wheel_adapter.kcl` engine-executed and rendered **on its own, down the wheel axis** | all six M3 output holes open, background visible through them; the six key scallops line up with them |
| `wheel.kcl` engine-executed and rendered | crowned tread revolved correctly, axial stack correct, mirroring correct |
| `main.kcl` engine-executed and rendered front/right/iso | wheels on the ground, mirroring correct, no visible interference |
| `wheel_module_check.kcl` rendered | one wheel and one motor — the second, mirrored wheel that used to stand at the origin is gone |
| `/mass` — engine measurement of every printed part | 2,059.0 g, 241 g under the ceiling; see §4 |

The hole check is the one that matters and it was done the way [`KCL_GOTCHAS.md`](KCL_GOTCHAS.md) asks: the part alone, looking straight down the feature's axis, with nothing but background behind it. It is **not** done in `wheel_module_check.kcl`, where the motor stands directly behind the disc and would make a filled hole look open — that scene now says so in its own header.

### The adapter is not a union

The disc, spigot and plug are left as interpenetrating bodies. That is the project's existing convention where the kernel is fragile, and here it also removes the risk outright: an unioned body across a drilled disc has silently filled its holes back in on this project before. The plug is held inside Ø17 for the same reason — anything wider would reach into the screw heads' own counterbores.

---

## 4. Mass

Measured on the engine, not estimated. **2,059.0 g against the 2,300 g ceiling — 241 g of headroom.**

| | each g | n | total g |
|---|---:|---:|---:|
| Thighs, the pair | 72.8 | 1 | 72.8 |
| Shins, the pair | 72.8 | 1 | 72.8 |
| Hip carriers, the pair | 75.0 | 1 | 75.0 |
| Wheel adapters, the pair | 28.9 | 1 | 28.9 |
| Pelvis, torso shell, cover | 198.4 | 1 | 198.4 |
| **printed structure** | | | **447.8** |
| Actuators | 150.0 | 8 | 1200.0 |
| Bearing, journal, carrier | 16.3 | 4 | 65.2 |
| Wheels — 80 mm skate, the pair | 60.0 | 2 | 120.0 |
| Fasteners | | | 66.0 |
| Electronics and wiring | | | 100.0 |
| Power entry | | | 60.0 |
| **total** | | | **2059.0** |

### What the conversion actually costs

`/mass` reports +34.4 g against the committed baseline, and **most of that is not the wheels.** The baseline in `tools/mass_baseline.json` predates changes already on `main`: thighs and shins each measure 8.6 g more than it records and the torso 11.1 g more, none of which this branch touched. That drift is +28.3 g on its own.

Measuring the walking parts as they stand today gives the honest comparison:

| | walking | wheeled |
|---|---:|---:|
| Feet / wheel adapters, the pair | 143.1 | 28.9 |
| Bought wheels, the pair | — | 120.0 |
| Hip carriers, the pair | 75.0 | 75.0 |
| Fasteners | 60.0 | 66.0 |
| | **278.1** | **289.9** |

**The wheeled conversion costs 11.8 g.** The printed part at the bottom of each leg drops from 143.1 g the pair to 28.9 g — a 114 g saving in printing, since an adapter is a disc and a spigot where a foot was a ribbed tray, a sole and four sensor pads — and 120 g of bought wheel comes straight back. The hip carriers come out identical: the 4 mm of span the wheel takes away does not change any wall, and the small difference in measured mass is the double-counted overlap between the three bodies, which grows as the two ends come closer.

The soft number is the 60 g wheel. It is a catalogue-typical figure for an 80 × 24 mm 85A skate wheel and it has not been weighed; the brand-to-brand range is roughly 55–65 g, so the pair could move ±10 g. Weigh one when it arrives.

---

## 5. Layout changes on this branch

`main.kcl` is now the wheeled robot, because that is what this branch is about and rendering `main.kcl` should show it. The walking robot moved to `walking_main.kcl` and is otherwise untouched.

Three things were cleaned up along the way:

**The hip carrier is no longer forked.** There was a `wheeled_hip_carrier.kcl` that was a whole copy of `hip_carrier.kcl` with one number changed, and the copy had dropped the original's provenance comments — including the warning that its three bodies are deliberately not unioned and a slicer must merge them before printing. `hip_carrier.kcl` is now a function taking the axis span, with all of that history in one place, and `walking_hip_carrier.kcl` and `wheeled_hip_carrier.kcl` are four-line wrappers that pick 55 mm and 51 mm. This mirrors how `limb.kcl` serves `thigh.kcl` and `shin.kcl`.

**The review scenes no longer show parts that are not there.** Importing any name from a module runs the whole module, so `wheel_module_check.kcl` was standing a second, mirrored wheel at the origin — coaxial with the wheel under review and directly behind the features the scene existed to inspect. Both it and `fixed_hip_mount_check.kcl` now import the other hand explicitly and hide it.

**The mass budget describes the wheeled robot.** `tools/mass_budget.toml` swapped feet for wheel adapters and added the bought wheels; the branch is the variant mechanism, since one budget file describes one machine.

---

## 6. Regression scenes

- `pose_check.kcl` — ported to wheels. Same hip and knee angles as the walking version so the clearance figures stay comparable; the ankle and the foot angle are gone. The standing wheel's axle lands at exactly 40 mm, so it is tangent to the floor rather than drawn near it, and the lifted wheel clears by 27.3 mm.
- `squat_check.kcl` — **new**, and a scene the walking robot never needed. A wheeled leg folds a Ø80 disc up towards its own thigh, where a foot swept its own flat silhouette. The knee's 110° stop and both axles staying at 40 mm leave no freedom once the squat is symmetric: 55° of hip, 110° of knee. The torso drops 89.6 mm to stand 290 mm, and the knees come 86 mm forward of the hip axis.
- `knee_limit_check.kcl`, `knee_prelimit_check.kcl` — unchanged and still valid. They are limb-against-limb and never touched the ankle, so they belong to both robots.

---

## 7. What is still open

**Not re-derived for wheels, and both answers change:**

- **Hip-roll inward limit.** `roll_limit_check.kcl` still carries walking geometry, where the answer was 7° inward — set by the feet touching, not by the actuator's ±25°. Wheels are 24 mm wide where feet were 65, so the limit should improve substantially, but it has not been drawn and the arithmetic in that file's header is about feet.
- **Torque envelope.** `torque_limit_pose.kcl` likewise. The 2 300 g ceiling is derived from knee torque in a walking crouch; a balancing robot spends its time near vertical but pays continuously to hold station.

**Needs hardware, not CAD:**

- Weigh a real wheel and replace the 60 g estimate in the budget.
- Confirm the hub Ø45 and the crown radius with calipers.
- Prove the clamped-face drive on the bench at the actuator's peak torque before trusting the friction figure.
- Measure the output bearing's moment capability with DAMIAO. The wheel adds 0.12 Nm standing and about 0.36 Nm at three times body weight, which sits inside what the flat limbs already ask of the same bearing — but that question was already open before the wheel arrived, and it stays open.

**Control, unchanged from the analysis:**

Wheel commands are the highest-priority realtime traffic; a dedicated CAN bus for the two wheel motors may be warranted once bus timing is measured. Regeneration matters more with balancing wheels than with static standing — the tethered supply cannot be assumed to absorb reverse current, so the motor-side DC link needs an energy sink even if an upstream contactor opens.

**Six-motor work** is done in CAD: both hip-roll clevises, their hardware, their gussets and the keel are gone, the freed volume is closed at full width, and the hip pitch joints are integrated into the shell floor. The robot measures 1.638 kg against a 2.3 kg ceiling. What is still not claimed is the control side — nothing here shows that lateral balancing works without hip roll, and the robot can no longer lean or place a wheel sideways at all.

---

## 8. Physical width

Worth knowing before crates and doorways: the stack outboard of each output face is 24 mm of wheel, 2 mm of washer and 5 mm of M5 cap head, which puts the robot at **208 mm across the screw heads** against the walking robot's 161 mm across the feet. Nothing is near those heads — they point into free air — and the wider track is worth having on a machine that balances.
