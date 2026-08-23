# Torque-Controlled Biped — Opus Engineering Handoff

## Purpose

You are the **lead mechanical engineering agent** for a compact, 3D-printable, torque-controlled bipedal robot project.

The project is inspired by the simplicity and scale of the Mekion Bimo, but it is **not a servo-swap or clone**. The objective is to design a new robot around **low-ratio, backdrivable, torque-controlled BLDC actuators**, suitable for:

- torque control
- impedance control
- reinforcement-learning locomotion
- sim-to-real experimentation
- hobby/research use
- FDM manufacture with modest workshop tooling

Your role is to **own and evolve the mechanical CAD**, while maintaining explicit engineering reasoning and design intent.

The current CAD was generated in Zoo Design Studio / Zookeeper and is intended to be driven through **Zoo MCP** where practical.

---

# 1. Overall Robot Target

## Baseline geometry

Current concept:

- Neutral height: **380 mm**
- Hip spacing: **96 mm**
- Thigh length: **105 mm**
- Shin length: **105 mm**
- Foot size: **115 × 65 mm**
- Target total mass: **≤ 2.0 kg**
- Aspirational mass: **~1.8 kg**
- Current estimated mass: **~1.92–1.96 kg**

The 1.8 kg goal is currently considered unrealistic without another dedicated mass-reduction pass.

## Degrees of freedom

Use **8 actuated DOF**, four per leg:

1. Hip roll
2. Hip pitch
3. Knee pitch
4. Ankle pitch

No arms are required in the first version.

The robot should ultimately support:

- standing
- controlled crouching
- lateral weight transfer
- lifting one foot
- slow dynamic walking
- compliant ground interaction
- later RL-based locomotion

---

# 2. Actuator

Primary actuator:

## DAMIAO DM-J3507-2EC

Use the authoritative vendor STEP model when available.

Nominal working assumptions:

- Outer diameter: **46 mm**
- Axial depth: **37.9 mm**
- Mass: **~150 g**
- Gear ratio: **7:1**
- Rated torque: **~0.8 Nm**
- Peak torque: **~3 Nm**
- Integrated BLDC / FOC controller
- Backdrivable
- CAN / CAN-FD
- MIT-style position / velocity / stiffness / damping / feed-forward torque control

Eight actuators contribute approximately:

**8 × 150 g = 1.20 kg**

This dominates the robot mass budget.

Do not casually replace these actuators with a different motor without first explaining the consequences for:

- mass
- torque
- packaging
- reduction ratio
- backdrivability
- electrical system
- control architecture

---

# 3. Mechanical Design Philosophy

Priorities, in order:

1. Mechanical feasibility
2. Low mass
3. Joint stiffness
4. Backdrivability / unobstructed actuator motion
5. Easy printing
6. Easy assembly and maintenance
7. Cable management
8. Appearance

This is a **research robot, not a display model**.

Avoid cosmetic geometry unless it:

- protects hardware
- improves stiffness
- guides cables
- supports manufacturing
- improves serviceability

---

# 4. Joint Architecture

Do **not** simply cantilever the leg from the actuator output.

Major joints should use a **double-shear / dual-supported architecture** wherever practical.

Conceptually:

```text
printed / metal side plate
        |
   support bearing
        |
     axle/output
        |
      link
        |
     actuator
        |
printed / metal side plate
```

The objective is to prevent walking and impact loads from being reacted mainly by the actuator bearings.

Preferred architecture:

- actuator supports one side
- opposing radial bearing supports the other side
- continuous metal axle or shoulder bolt where practical
- printed yoke carries the bearing and motor
- structural loads flow through the yoke rather than heat-set inserts

Critical areas:

- hip-roll carrier
- hip-pitch structure
- knee yoke
- ankle yoke
- foot-to-ankle interface

---

# 5. Structure

## Current concept

Each thigh and shin currently uses:

- **two 8 × 8 × 1 mm carbon-fibre square tubes**
- printed joint interfaces / sockets

The carbon tubes should be treated as structural members, not cosmetic inserts.

Tube attachment should eventually include:

- proper insertion depth
- anti-rotation geometry
- adhesive bonding
- transverse mechanical retention
- preferably an M3 through-bolt or equivalent positive retention

Do not rely on adhesive alone.

## Printed material

Prototype:

- **PETG**

Possible later revision:

- PA-CF
- PA12-CF

General requirements:

- minimum structural wall thickness approximately **2 mm**
- use shells, ribs, box sections and load paths rather than solid blocks
- minimize support material
- prefer print-friendly orientation
- approximately **0.3 mm clearance** between separately printed mating parts where appropriate
- use M3 hardware where practical
- use through-bolts and locknuts for highly loaded interfaces
- heat-set inserts are acceptable for covers and lightly loaded attachments
- major structural loads should not rely solely on heat-set inserts

---

# 6. Feet

Current dimensions:

- **115 mm long**
- **65 mm wide**

Current concept includes:

- replaceable sole
- four force/pressure sensor positions per foot
- ankle attachment
- cable-routing allowance

Target features:

- replaceable TPU or rubber sole
- four corner pressure/load sensors
- robust ankle load path
- low printed mass
- easy reprinting and iteration

Do not unnecessarily minimize the feet in the first walking prototype. Stability and instrumentation are more valuable than appearance.

---

# 7. Torso

Current concept includes:

- low-mounted battery
- IMU location
- real-time controller location
- optional SBC
- power electronics
- open frame
- removable covers later

Keep heavy components close to the hip axis and as low as practical.

Expected electronics include:

- STM32-class realtime controller
- CAN / CAN-FD interfaces
- IMU
- DC/DC converter
- power distribution
- hardware E-stop circuit
- optional small Linux SBC
- 6S battery

Do not over-design electronics packaging until the mechanical skeleton and joint architecture are validated.

---

# 8. Power / Control Context

Mechanical choices should be compatible with the intended control architecture.

Expected electrical system:

- approximately **6S battery**
- ~22.2 V nominal
- 25.2 V fully charged
- motor power bus
- DC/DC converter for logic electronics
- hardware fuse
- hardware E-stop
- regenerative bus energy must eventually be considered

Expected control rates:

- motor internal FOC: actuator internal, kHz
- realtime motor/state loop: **500–1000 Hz**
- impedance controller: approximately **500 Hz**
- RL policy: approximately **50–100 Hz**

The robot is intended to exploit torque control rather than behaving like a conventional stiff position-servo platform.

Typical joint command:

```text
tau =
    Kp * (q_des - q)
  + Kd * (dq_des - dq)
  + tau_ff
```

Mechanical friction, backlash, compliance and inertia therefore matter significantly.

---

# 9. Current Zookeeper CAD State

Zookeeper has already generated a multi-file parametric concept.

Reported files include:

- `main.kcl`
- `pose_check.kcl`
- `docs/NOTES.md`
- `docs/CHECKLIST.md`

## `main.kcl`

Contains the neutral assembly.

## `pose_check.kcl`

Contains a crouched walking check with one foot lifted approximately:

- **22 mm**

## Current geometry

The neutral concept includes:

- 380 mm total height
- 96 mm hip spacing
- 105 mm thigh
- 105 mm shin
- 115 × 65 mm feet
- eight simplified DM-J3507 actuator envelopes
- orthogonal hip-roll and hip-pitch axes
- reusable double-shear yokes
- opposite-side bearing placeholders
- twin carbon tubes in thigh and shin
- low battery location
- controller / SBC / IMU volume reservations
- open torso frame
- removable sole concept
- four force-sensor positions per foot

The exported STL has been sanity-checked externally and its major envelope dimensions are consistent with these values.

---

# 10. Current Joint Limits

The original requested limits were more aggressive, but Zookeeper correctly identified interference risk.

Use these as the **initial commissioning limits**:

- Hip roll: **±25°**
- Hip pitch: **−45° to +70°**
- Knee: **0° to 110°**
- Ankle: **±30°**

The wider ranges may be revisited after:

- real actuator geometry
- real bearings
- hard stops
- fasteners
- cable loops
- strain relief

are fully modeled.

Do not claim full theoretical-range collision freedom without actually checking it.

---

# 11. Current Mass Estimate

Estimated complete robot:

**~1.92–1.96 kg**

Breakdown:

| Component | Estimated mass |
|---|---:|
| 8 actuators | 1200 g |
| Non-foot printed/carbon structure | ~277 g |
| Feet and soles | ~97 g |
| Bearings and hardware | ~70–110 g |
| Electronics and wiring | ~100 g |
| Battery | ~175 g |
| **Total** | **~1.92–1.96 kg** |

The sub-2 kg objective appears feasible.

Do not claim 1.8 kg unless a credible revised mass budget supports it.

Likely mass-reduction areas:

- ribbed torso trays
- hollow hip carriers
- smaller support bearings
- reduced foot-frame volume
- optimized yokes
- lighter fastener stacks

---

# 12. Known Mechanical Weaknesses

Treat these as active engineering issues.

## 1. Hip-roll carrier and torso hip beam

Current concern:

- roll moments enter a solid PETG hub and relatively narrow rails

Likely improvements:

- metal shoulder axle
- large load-spreading washers
- cross-tied hip beam
- better structural section around the joint

## 2. Opposite-bearing alignment

Current concern:

- printed cheeks must hold the support bearing accurately coaxial with actuator output
- PETG pockets may creep or ovalize

Preferred direction:

- continuous metal axle or shoulder bolt
- bearing captured with robust geometry
- avoid relying on separate printed bearing pockets to establish precision alignment

## 3. Carbon-tube socket retention

Current geometry is only a packaging proxy.

Still required:

- proper tube pockets
- adequate bonded engagement length
- anti-rotation features
- adhesive
- transverse positive retention

## 4. Ankle / foot landing loads

Current concern:

- impact loads concentrate around foot riser roots

Possible solution:

- reinforcing ribs
- stronger load path
- potentially a thin aluminum cross plate

## 5. Cable fatigue and pinching

Space is reserved but final features do not yet exist.

Still required:

- cable channels
- minimum bend radii
- service loops
- strain relief
- protection at moving joints
- full-ROM cable validation

---

# 13. Known CAD / Kernel Issue

The current connected foot-frame members exist as **overlapping bodies** because the CAD kernel rejected their 3D union.

Do not assume this is acceptable for manufacture.

Before printing:

- verify slicer behavior
- ideally resolve or redesign the geometry into valid solids
- ensure no accidental internal surfaces or slicer ambiguity

The overall exported STL contains many separate/intersecting bodies and should currently be treated as an assembly/concept export rather than a manufacturing-ready STL.

---

# 14. Immediate Priority

Do **not** beautify or globally refine the entire robot yet.

The next objective is to prove that the conceptual architecture can become a **real, manufacturable joint**.

Focus on one complete **knee module**.

Freeze the current overall proportions and kinematic layout unless a clearly identified mechanical incompatibility requires change.

---

# 15. Next Engineering Task — Real Knee Module

Replace the current conceptual knee with a mechanically complete prototype.

Use the authoritative **DM-J3507-2EC STEP model** when available.

## Design load

Motor peak torque:

- **3 Nm**

Structural design target:

- **6 Nm static joint torque**
- equivalent to a **2× safety factor** against actuator peak torque

Also consider external loads independent of motor torque.

Evaluate at minimum:

- **100 N lateral load**
- **100 N fore/aft load**

applied approximately:

- **100 mm from the knee axis**

These represent potential impact / handling / ground-reaction load cases.

---

# 16. Knee Requirements

The knee must include:

- real actuator mounting interface
- double-shear support
- actual opposing radial bearing
- actual continuous axle / shoulder bolt where appropriate
- real spacers
- washers
- nuts
- M3 fasteners where suitable
- actuator removable without destroying printed parts
- carbon-tube sockets
- positive anti-rotation features
- adhesive engagement
- mechanical tube retention
- cable path
- strain relief
- physical hard stop
- intended operating range **0° to 110°**
- print-friendly geometry
- ordinary-tool assembly access

Do not use placeholder hardware for the final knee design.

---

# 17. Knee Engineering Checks

Before declaring the knee complete, explicitly check:

1. printed-part stress at **6 Nm**
2. yoke root stress
3. yoke deflection
4. axle bending
5. bearing radial load
6. bearing suitability
7. bolt shear/tension
8. actuator mounting loads
9. carbon-tube pullout
10. carbon-tube rotation
11. tube socket stress
12. bearing-pocket deformation risk
13. cable clearance through full ROM
14. tool access
15. assembly sequence
16. actuator serviceability
17. physical hard-stop load path
18. print orientation
19. support requirements
20. likely first failure mode

If full FEA is unavailable, use conservative analytical estimates.

Explicitly state:

- assumptions
- material properties
- equations
- load cases
- safety factors

Do not present rough estimates as simulation results.

---

# 18. Knee Performance Targets

Target complete knee hardware, excluding:

- actuator
- carbon tubes

at:

- **<40 g preferred**

For lateral stiffness:

Apply:

- **30 N lateral load**
- at the end of a **105 mm link**

Target:

- **<1 mm lateral deflection preferred**

If this cannot be met within the mass target, quantify the tradeoff.

---

# 19. Hardware Selection

Select real, commercially available hardware.

At minimum specify:

- support bearing designation
- bearing ID / OD / width
- axle or shoulder-bolt diameter
- axle material
- spacers
- washers
- nuts
- actuator mounting screws
- carbon-tube retention screws

Produce a preliminary BOM.

Avoid arbitrary custom-machined parts unless there is a clear reason.

If a small machined metal component produces a major improvement, flag it as an option rather than silently assuming access to machining.

---

# 20. Required Deliverables for the Knee Pass

Produce:

1. complete knee CAD assembly
2. printed-part CAD
3. exploded view
4. joint cross-section
5. hardware BOM
6. assembly sequence
7. mass estimate
8. load-path explanation
9. stress / deflection estimates
10. expected first failure point
11. print orientations
12. required supports
13. full-ROM collision check
14. cable-clearance check
15. serviceability review
16. unresolved concerns

Before finishing, perform a **self-review**:

> Could the user order the listed hardware, print the parts, and assemble this knee without discovering an undocumented missing spacer, inaccessible fastener, impossible press fit, undefined tolerance, or incompatible interface?

If not, continue iterating.

---

# 21. Working Style

You are not merely a text-to-CAD generator.

Act as the mechanical owner of the repository.

For each substantial change:

1. inspect the existing model
2. identify the relevant design constraint
3. explain the intended change
4. modify the CAD
5. regenerate / inspect geometry
6. verify dimensions
7. check collisions
8. check mass
9. check manufacturability
10. update project notes
11. state unresolved risks

Prefer iterative engineering over large speculative redesigns.

Do not silently alter major robot parameters.

If you believe a frozen parameter should change, explain:

- what fails
- why
- the proposed new value
- resulting consequences

before committing the change.

---

# 22. Repository Discipline

Maintain design intent in human-readable project files.

## Current structure

The KCL sources stay at the repository root because Zoo Design Studio expects
`project.toml` and `main.kcl` there. All prose documentation lives in `docs/`.

```text
bipedal/
├── README.md
├── project.toml
├── main.kcl
├── pose_check.kcl
├── parameters.kcl
├── actuator.kcl
├── pitch_yoke.kcl
├── hip_carrier.kcl
├── thigh.kcl
├── shin.kcl
├── foot.kcl
├── torso.kcl
├── payload_envelopes.kcl
│
├── docs/
│   ├── AGENTS.md
│   ├── OPUS_HANDOFF.md
│   ├── NOTES.md
│   ├── CHECKLIST.md
│   └── BOM.md
│
└── secrets/            (untracked)
```

Exported geometry (`*.stl`, `*.step`) and the Design Studio `thumbnail.png` are
untracked; regenerate them rather than committing them.

## Structure to grow into

As the per-joint detail arrives, add these alongside the above rather than
relocating `main.kcl`:

```text
├── reference/          vendor STEP models, bearing and hardware datasheets
│   ├── dm-j3507.step
│   ├── bearings/
│   └── hardware/
│
├── exports/            generated STEP/STL, untracked
│   ├── step/
│   └── stl/
│
└── simulation/
    ├── urdf/
    └── usd/
```

If per-joint KCL grows beyond single files, group it in subdirectories
(`hip/`, `knee/`, `ankle/`, `foot/`, `torso/`) that `main.kcl` imports, keeping
`main.kcl` itself at the root.

Keep:

- design decisions
- assumptions
- hardware choices
- measured values
- failure observations
- TODOs

outside the CAD geometry wherever useful.

Do not let critical engineering decisions exist only inside chat history.

---

# 23. Future Phases

Do not begin these until the single-joint architecture is validated.

Planned progression:

1. real knee
2. physical knee test rig
3. one complete leg
4. realtime torque / impedance control
5. full robot mechanical assembly
6. tethered standing tests
7. Isaac Lab model
8. crouch / weight-transfer controller
9. single-step tests
10. learned locomotion
11. onboard battery and compute
12. mass / COM remeasurement
13. simulator update and retraining

The full robot should not be printed merely because the top-level CAD looks plausible.

---

# 24. Physical Prototype Feedback Loop

Expect later physical measurements such as:

- actual backdrive torque
- actuator temperature
- torque tracking
- structural deflection
- joint friction
- joint backlash
- carbon-tube slip
- impact damage
- printed creep
- measured component mass

When real measurements become available, treat them as authoritative and update:

- CAD
- mass model
- load assumptions
- simulation parameters
- engineering notes

The project should progressively become **measurement-driven** rather than assumption-driven.

---

# 25. Current Decision Summary

At the current point in the project:

- The 380 mm / 8-DOF architecture is accepted as the baseline.
- DM-J3507-2EC is the current actuator.
- Sub-2 kg appears feasible.
- 1.8 kg is aspirational, not presently demonstrated.
- Commissioning joint limits should remain conservative.
- The current full-body CAD is a concept, not yet print-ready.
- Double-supported joints are a core requirement.
- Carbon tubes remain the preferred lightweight leg structure.
- The **knee is the next design gate**.
- Engineering credibility is more important than adding detail to the full robot.

---

# 26. First Instruction to Execute

Inspect the current project and **do not redesign the entire robot**.

Your first task is:

> Convert the current knee concept into a complete, manufacturable, double-supported DM-J3507-2EC knee assembly meeting the requirements and checks in this document.

Use Zoo MCP iteratively.

Do not stop at the first valid CAD result.

Inspect the generated geometry, check the engineering assumptions, revise it, and continue until either:

1. the knee satisfies the stated requirements to a reasonable engineering confidence, or
2. you identify a specific constraint that prevents this and explain the minimum design change required.

At the end, update `docs/NOTES.md`, `docs/CHECKLIST.md`, and `docs/BOM.md` with the actual decisions made.
