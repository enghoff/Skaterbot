# Wheeled-Biped Implementation Branch

**Branch:** `feature/wheeled-biped`  
**Status:** first CAD pass committed; engine regeneration still required  
**Baseline preserved:** `main.kcl`, `foot.kcl`, `hip_carrier.kcl` and the walking parameter set are unchanged

This document records what has actually been implemented from [`WHEELED_BIPED_ANALYSIS.md`](WHEELED_BIPED_ANALYSIS.md), what is analytical only, and what remains before the branch can be treated as buildable.

---

## 1. Architecture being implemented

The branch takes the conservative conversion first:

```text
hip roll -> hip pitch -> knee pitch -> wheel
```

per leg, still using eight DAMIAO DM-J3507-2EC actuators total.

The existing ankle actuator becomes the wheel motor. The walking foot is not modified or deleted; a separate wheel module and a separate complete assembly are added so the two architectures can be compared side-by-side.

The branch also starts the six-motor concept:

```text
fixed torso mount -> hip pitch -> knee pitch -> wheel
```

per leg. That work is deliberately stopped at an isolated fixed-hip module until the eight-motor wheel geometry has regenerated successfully. The current torso contains real hip-roll clevises and gussets, so a six-motor whole-robot assembly would require a proper torso variant rather than hiding old geometry under new parts.

---

## 2. Files added

### `wheeled_parameters.kcl`

Wheel-specific dimensions and derived axis heights without changing `parameters.kcl`.

First prototype:

- wheel diameter: **80 mm**
- tread width: **24 mm**
- radial tread thickness: **6 mm**
- structural core width: **8 mm**
- core ID / OD: **32 / 68 mm**
- wheel axis: **40 mm** above floor
- knee axis: **145 mm**
- hip-pitch axis: **250 mm**
- hip-roll axis remains **301 mm**
- hip-roll to hip-pitch separation becomes **51 mm**, from 55 mm on the walking robot

The 380 mm torso height and both 105 mm leg segments are unchanged.

### `wheel.kcl`

Direct-drive wheel module.

Important design choice: it uses `outputDisc()` rather than `rotorHub()`.

The walking foot needs the offset rotor arm and bridge because a flat sole must be brought back under the leg centreline. A wheel does not. Its structural core therefore grows directly from the actuator output disc.

The wheel centre plane is at `rotorHubOuterX`, close to the motor output face. The 24 mm-wide tyre partly overlaps the motor axially, but only at radii 34-40 mm, outside the Ø46 motor body. This is intentional: it keeps the ground-load plane close to the actuator bearing rather than cantilevering the wheel on a long axle.

The core's inner radius is 16 mm. The six output screws are on radius 12 mm with Ø6 counterbores, so their outer edge is radius 15 mm. The core therefore leaves 1 mm of radial clearance around the fastener-head/driver envelope and overlaps the Ø36 output disc only at its outer rim.

The tread is currently a simple annular **envelope**, not a geometrically crowned tyre. A selected inline-skate donor wheel or final moulded tread should replace that envelope later.

### `wheeled_hip_carrier.kcl`

A copy of the existing orthogonal hip carrier using the wheeled 51 mm axis separation. The original walking carrier remains unchanged.

### `wheeled_main.kcl`

Complete eight-motor neutral wheeled assembly:

- existing torso and payload envelopes
- existing hip-roll motors and support hardware
- hip-pitch and knee axes shifted upward 4 mm
- ankle motors renamed/re-purposed as wheel motors at z = 40 mm
- new 51 mm hip carriers
- existing thighs and shins translated to the new axis centres
- direct-drive wheels in place of feet

No ankle far bearing is added; the walking baseline already relies on the DM-J3507 output bearing at the ankle.

### `wheel_module_check.kcl`

Small review scene containing one right-hand DM-J3507 and one wheel. This should be opened before the full assembly to verify:

1. wheel/motor radial and axial clearance;
2. output-disc placement;
3. all six M3 counterbores remain open;
4. the structural core really overlaps the output disc outside the fastener circle;
5. left/right mirroring is correct.

### `fixed_hip_mount.kcl`

First mechanical part for the six-motor architecture.

It retains the existing `statorClevis()` around the hip-pitch actuator and replaces the powered hip-roll stage above it with a 30 × 30 mm closed PA12-CF box rising to the current torso shell floor. A thin 46 × 42 mm flange represents the area that should ultimately merge into the torso floor and distribute hip-pitch reaction into the closed shell.

This is intentionally a concept part. The torso integration, exact floor load path, local ribbing and service access are not frozen.

### `fixed_hip_mount_check.kcl`

Isolated right hip-pitch actuator plus fixed mount for geometry review before attempting a six-motor torso.

---

## 3. First-order mass estimate

This is analytical because the Zoo engine has not measured the new files yet.

For one 80 mm wheel, before subtracting bolt/register pockets:

- PA12-CF core annulus, 68/32 mm × 8 mm: approximately **24.0 g** at 1.06 g/cm³
- Ø36 × 6 mm output-disc upper bound: approximately **6.5 g** before holes
- 80/68 mm × 24 mm tread: approximately **40.2 g** at an assumed 1.20 g/cm³ elastomer density
- total upper-order estimate: approximately **70.6 g per wheel**

Two wheels are therefore about **141 g** versus the current measured **149.3 g** pair of complete walking feet.

Starting from the current measured 2,024.6 g walking baseline gives approximately **2,016 g** for the eight-motor wheeled robot before accounting for the slightly shorter hip carriers. The real figure should be measured with the engine; this is not a committed mass value.

The six-motor architecture additionally removes, at minimum:

- two DM-J3507 actuators: **300 g**
- two hip-roll bearing/journal/carrier sets: **32.6 g**

and replaces the current orthogonal hip carriers with static mounts. A final integrated six-motor torso should therefore plausibly fall in the **1.65-1.75 kg** region, but that remains a design estimate until the torso and mounts exist as measured CAD.

---

## 4. Mechanical checks required before this becomes a baseline candidate

### Wheel module

- engine-execute `wheel_module_check.kcl`
- render down the wheel axis and verify **all six output holes/counterbores remain visibly open**
- inspect the inboard tyre sidewall against the Ø46 motor envelope
- measure wheel core/output-disc overlap rather than trusting the union visually
- add actual crown/profile after a physical wheel is selected
- decide whether the final tyre is a commercial donor, bonded PU ring, cast PU or printed TPU test part
- review core strength at the narrow annular connection outside the bolt heads
- measure output-bearing moment capability with DAMIAO / bench testing before accepting unsupported wheel loads

### Whole robot

- engine-execute `wheeled_main.kcl`
- front/back/side renders
- verify both wheel tangent planes reach z = 0
- check wheel-to-shin and wheel-to-opposite-wheel clearance throughout hip/knee motion
- re-run knee and hip-roll extrema using wheel geometry
- create a pitch-balance pose with the body COM fore/aft of the wheel contact line
- check cable routing to a continuously rotating wheel motor; unlike the old ankle, the actuator housing is stationary, so the existing motor-side harness does not itself rotate, but routing around the wheel must remain outside the tread envelope

### 80 mm versus 90 mm

The branch starts at 80 mm because it only changes the lower-chain height by 4 mm. If testing supports the concept, repeat the same clearance and carrier analysis at 85 and 90 mm. A 90 mm wheel would move the axle to 45 mm and reduce the hip carrier separation to 46 mm while preserving the 301 mm hip-roll axis and 380 mm torso height.

---

## 5. Electrical/control consequences already fixed by the architecture

No new motor driver is needed. The two former ankle DMs remain on the 24 V + CAN system and become wheel velocity/torque actuators.

Before balancing tests:

- treat wheel commands as the highest-priority realtime traffic;
- consider assigning the two wheel motors to a dedicated CAN/CAN-FD bus if measured bus timing warrants it;
- measure command-to-torque and encoder feedback latency rather than choosing controller rates from theory alone;
- validate raw IMU gyro latency/jitter; the wheel robot is more sensitive to sensing delay than the walking static poses;
- finish the local bulk-capacitance and brake/clamp design before aggressive wheel braking.

Regeneration is a stronger requirement with balancing wheels than it is with static standing. The tethered bench supply cannot be assumed to absorb reverse current. The motor-side DC link therefore needs to retain an energy sink even if an emergency-stop contactor opens upstream.

---

## 6. Six-motor work: what has and has not been done

### Done

- identified a static load path from the hip-pitch `statorClevis()` to the existing torso shell-floor datum;
- replaced the 51 mm powered roll/pitch carrier conceptually with a short closed-box hanger;
- added a broad top flange to spread reaction into the torso floor;
- added an isolated actuator/mount review scene.

### Not done deliberately

- no `six_motor_main.kcl` yet;
- no fake deletion of hip-roll motors while leaving their clevises in the torso;
- no torso mass claim;
- no assertion that lateral balancing/control works without hip roll;
- no manufacturing interface between the hanger and torso has been frozen.

The next six-motor CAD step should be a dedicated torso variant that removes both hip-roll clevises, their far-bearing hardware and their gussets, closes the newly free lower shell volume, and integrates the two fixed hip-pitch hangers directly into the shell floor. That model then needs lateral load and tip-over analysis before it replaces the eight-motor version as the preferred architecture.

---

## 7. Validation status

The repository has no GitHub Actions workflow that runs `tools/check.py`, and this execution environment does not have the Zoo `zoo-kcl` package available. The new KCL has therefore been reviewed against the syntax and construction patterns already used by the project, but **has not been mock-executed or engine-executed here**.

Treat successful Design Studio regeneration as the immediate gate. Start with:

1. `wheel_module_check.kcl`
2. `fixed_hip_mount_check.kcl`
3. `wheeled_main.kcl`

Only after those render correctly should the branch proceed to pose checks, mass measurement and the six-motor torso rewrite.
