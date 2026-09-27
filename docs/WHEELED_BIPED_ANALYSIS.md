# Wheeled-Biped Conversion Study

**Status:** design study only — **does not change the current 8-DOF walking baseline**  
**Date:** 2026-08-31  
**Baseline reviewed:** `main` after the 2026-08-30 flat-plate limb/BOM reconciliation  
**Primary recommendation:** prototype the wheel conversion with the existing eight DAMIAO actuators, then consider a six-motor wheel-first architecture using **hip pitch + knee + wheel** on each leg.

---

## 1. Purpose

This note evaluates replacing the current feet with driven wheels and asks two related questions:

1. What wheel and motor hardware is mechanically and electrically appropriate for this 380 mm robot?
2. Once a wheel replaces the foot, can any of the existing joints be removed and the robot simplified rather than merely adding wheels to the existing design?

The conclusion is unusually favourable because the present ankle actuator can itself become the wheel motor. The lowest-risk conversion therefore does **not** add a motor, gearbox or motor controller. It repurposes the existing ankle-pitch DAMIAO DM-J3507-2EC as a continuous wheel actuator.

A more aggressive wheel-first redesign can then delete the two hip-roll joints as well, producing a six-motor robot:

```text
pelvis
  └─ hip pitch
       └─ thigh
            └─ knee pitch
                 └─ shin
                      └─ driven wheel
```

per leg.

This is a proposal, not an approved change to the frozen project kinematics in `AGENTS.md`. No CAD files or baseline BOM entries are changed by this study.

---

## 2. Current baseline relevant to the conversion

The current robot is approximately:

- 380 mm tall
- 96 mm hip spacing
- 105 mm thigh + 105 mm shin per side
- 8 actuators total
- per leg: **hip roll + hip pitch + knee pitch + ankle pitch**
- DAMIAO DM-J3507-2EC, 24 V, at every joint
- tethered 24 V + CAN
- measured CAD mass baseline: **2,024.6 g**
- torque-derived mass ceiling: **2,300 g**

Relevant current mass entries from `tools/mass_baseline.json` and `tools/mass_budget.toml` are:

| Item | Current mass |
|---|---:|
| All 8 actuators | 1,200 g |
| Printed feet, pair | 149.3 g |
| Hip carriers, pair | 74.4 g |
| 4 bearing/journal/carrier sets | 65.2 g |
| Whole robot baseline | 2,024.6 g |

The current ankle axis is only **36 mm above the floor**. This makes an 80–90 mm wheel geometrically convenient: its axle height would be 40–45 mm, only 4–9 mm above the existing ankle axis.

The present foot is already the moving side of the ankle joint. `foot.kcl` states explicitly that the foot is the ankle rotor and bolts directly to the actuator output circle. That means the wheel conversion follows the existing load path rather than inventing a new one: remove the foot rotor structure and bolt a wheel hub to the same actuator output.

The current foot is 115 × 65 mm with four force sensors. Those features become unnecessary for a pure wheeled contact.

---

## 3. Architecture options

### 3.1 Current walking baseline

```text
hip roll → hip pitch → knee pitch → ankle pitch → foot
```

Per leg:

- 4 actuators
- 4 articulated joints

Whole robot:

- 8 motors
- 8 articulated joints

This remains the active walking-oriented baseline.

### 3.2 Low-risk wheel conversion — recommended first prototype

```text
hip roll → hip pitch → knee pitch → wheel
```

The existing ankle actuator remains in exactly the same broad location but its rotor drives the wheel continuously instead of pitching a foot.

Whole robot:

- **8 motors remain**
- **6 articulated leg joints** remain
- 2 additional continuous wheel rotations
- no ankle-pitch articulation
- no conventional feet

This is the preferred first prototype because it changes the minimum number of variables at once.

### 3.3 Wheel-first architecture — preferred eventual simplification

```text
hip pitch → knee pitch → wheel
```

The two hip-roll actuators and their joints are removed. Hip-pitch actuators mount directly to fixed pelvis brackets.

Whole robot:

- **6 motors total**
- 4 articulated leg joints
- 2 wheel rotations
- no hip-roll joints
- no ankle joints
- no conventional feet

For an indoor robot operating primarily on flat floors, this is the strongest long-term architecture considered in this study.

### 3.4 More radical reductions

A four-motor version using **hip pitch + wheel** on each side is possible. It loses knee articulation, body-height adjustment and much of the useful leg compliance. A two-motor fixed-leg version becomes essentially a self-balancing differential-drive platform.

Those architectures save still more mass but give up enough leg functionality that they are not recommended unless absolute simplicity becomes more important than wheel-leg research capability.

---

## 4. Wheel-motor selection

## 4.1 Recommended motor: reuse the DM-J3507-2EC

The current DAMIAO motor is a good wheel actuator for a robot of this size.

Published 24 V figures are approximately:

| Parameter | DM-J3507-2EC |
|---|---:|
| Mass | 150 g |
| Reduction | 7:1 |
| Rated output torque | 0.8 Nm |
| Peak output torque | 3 Nm |
| Rated output speed | 150 rpm |
| No-load maximum | 460 rpm |
| Diameter × depth | 46 × 37.9 mm |
| Encoder | dual magnetic, 14-bit |
| Control | MIT / torque-position hybrid, speed, position |
| Bus | CAN; CAN-FD supported in current project documentation/vendor material |

The output interface is already modelled from the vendor STEP/manual:

- Ø30 register
- 6 × M3 on Ø24 PCD

Those are exactly the features a wheel drive flange should use.

### Why reusing it is better than adding a conventional wheel motor

The robot already has:

- the motor
- integrated gearbox
- integrated driver
- encoder
- CAN interface
- 24 V distribution
- torque feedback/control
- software infrastructure for the actuator family

Changing to another wheel motor would introduce another driver, connector ecosystem, control protocol and spare-part family without solving a present torque problem.

## 4.2 Alternative: CubeMars AK40-10

The AK40-10 is a credible alternative if substantially greater wheel speed becomes a requirement.

Published figures are approximately:

| Parameter | AK40-10 |
|---|---:|
| Mass | 185 g |
| Rated torque | 1.3 Nm |
| Peak torque | 4.1 Nm |
| Rated speed | 370 rpm |
| No-load speed | 435 rpm |
| Reduction | 10:1 |
| Voltage | 24 V |

It provides more rated torque and much greater rated wheel speed, but adds about 35 g per wheel motor and introduces a second actuator ecosystem. There is no current evidence that the robot needs the extra torque or speed.

**Recommendation:** do not use the AK40-10 initially. Retain it as the fallback if testing proves that 150 rpm rated wheel speed is too restrictive.

## 4.3 Why common scooter hub motors are a poor fit

Typical scooter hub motors are designed around 36–48 V, hundreds of watts and substantially larger wheel diameters. Their mass alone can approach or exceed the complete mass allowance available to this robot.

They also place a large amount of unsprung mass at the contact point and would force a second voltage/driver ecosystem.

They are not appropriate for the current 380 mm, ~2 kg platform.

## 4.4 Why a bare outrunner + gearbox is not preferred

A small BLDC outrunner could achieve excellent power-to-mass ratio, but a usable wheel actuator would still require:

- reduction gearbox
- output bearing arrangement
- encoder
- motor driver
- current sensing
- torque-control implementation
- mechanical housing

The DM-J3507 already integrates all of those functions. There is no obvious system-level mass or complexity saving in replacing it at this stage.

---

## 5. Wheel diameter

For wheel diameter `D` and wheel speed `n`:

```text
v = π D n / 60
```

Using the DM-J3507's 150 rpm rated speed and 460 rpm published no-load maximum:

| Wheel diameter | Axle height | Change from current 36 mm ankle axis | Speed @ 150 rpm | Theoretical @ 460 rpm |
|---:|---:|---:|---:|---:|
| 70 mm | 35 mm | -1 mm | 0.55 m/s | 1.69 m/s |
| **80 mm** | **40 mm** | **+4 mm** | **0.63 m/s** | **1.93 m/s** |
| 85 mm | 42.5 mm | +6.5 mm | 0.67 m/s | 2.05 m/s |
| **90 mm** | **45 mm** | **+9 mm** | **0.71 m/s** | **2.17 m/s** |
| 100 mm | 50 mm | +14 mm | 0.79 m/s | 2.41 m/s |

The no-load values are not usable design speeds; they show only the gearing envelope. Normal operation should stay comfortably below that limit.

### Recommendation

- **First prototype:** 80 mm
- **Likely final size:** 85–90 mm

80 mm minimizes the change from the existing geometry. A 90 mm wheel gives better obstacle roll-over and a little more useful linear speed while remaining proportionate to the robot.

A 90 mm wheel also recovers roughly 9 mm of vertical stack relative to the current 36 mm ankle axis. If the wheeled variant is required to remain at approximately 380 mm overall height, the current 55 mm hip offset could therefore be investigated around the mid-40 mm range. That is only a first-order kinematic observation; it requires a full CAD collision/clearance pass before any parameter is changed.

---

## 6. Wheel type and tread

A narrow crowned wheel is preferred over a broad flat rover tyre.

Target characteristics:

| Property | Target |
|---|---:|
| Diameter | 80–90 mm |
| Tread width | about 22–25 mm |
| Tread material | cast polyurethane or comparable high-grip elastomer |
| Hardness | roughly 84–86A for initial indoor testing |
| Profile | rounded/crowned |
| Complete wheel + drive adapter | ideally <= 50–70 g each |
| Runout | ideally below ~0.2 mm after assembly |

### Why an inline-skate wheel is attractive

Inline wheels are:

- narrow
- crowned
- concentric
- designed for meaningful radial loads
- readily available in polyurethane
- cheap enough to treat as consumable prototype parts

A wide robot wheel is easier to adapt mechanically but gives a larger flat contact patch and more scrub during yaw/roll motions.

### India-available prototype candidates checked 2026-08-31

#### Decathlon/Oxelo 80 mm, 84A

Current India listing:

- 80 mm
- 84A polyurethane
- 4-pack
- ₹899 at the time of review

Suitable as an inexpensive first wheel/tread donor.

#### Cosco inline wheel family

Cosco India currently lists cast PU inline wheels without bearings in:

- 70 mm / 82A
- 72 mm / 82A
- 76 mm / 78A
- 80 mm / 86A
- 84 mm / 84A
- **90 mm / 85A**

The 90 mm / 85A version is especially interesting as a final-size donor if its measured width, mass, core geometry and concentricity are satisfactory.

### Important: a skate wheel is not a bolt-on motor wheel

A standard inline wheel is built around 608 bearing seats. The bearings must not simply be retained and driven through a conventional 8 mm axle, because that would discard the DAMIAO's robust output register and add unnecessary shaft/bearing hardware.

Instead, use the polyurethane wheel/core as the rolling element and make a dedicated drive adaptor.

---

## 7. Proposed wheel hub / drive adaptor

The preferred architecture is a **short direct drive flange** from the DAMIAO rotor to the wheel core.

Motor side:

- locate on the motor's Ø30 output register
- fasten with the existing 6 × M3 on Ø24 PCD
- keep the flange close to the output face

Wheel side:

- positively locate in the wheel core/bearing-seat geometry
- do not rely on friction against polyurethane alone
- clamp or mechanically key the core
- retain the wheel independently of the motor screws where practical

For a commercial inline wheel, one plausible prototype arrangement is:

1. remove the two 608 bearings;
2. use precision inserts that locate in the 22 mm bearing seats;
3. make the motor-side insert part of a larger drive flange carrying the Ø30/Ø24 DAMIAO interface;
4. clamp the wheel core between motor-side and outboard inserts through the wheel's central axle passage;
5. keep the wheel centre plane as close as practical to the motor output bearing.

The exact insert geometry depends on the selected wheel core and must be measured before CAD is frozen.

### Final-production alternative

A purpose-designed PA12-CF or aluminium hub with a replaceable moulded/cast PU tread is mechanically cleaner than adapting a skate wheel, but it is a later-stage choice. The off-the-shelf skate wheel is valuable because tread roundness, hardness and bonding are already solved.

---

## 8. Wheel torque and traction

Using the present 2.0246 kg robot mass on level ground, approximately half the static load is carried by each wheel:

```text
N_wheel ≈ m g / 2
        ≈ 2.0246 × 9.81 / 2
        ≈ 9.9 N
```

For a representative tyre/floor friction coefficient of 0.8:

```text
F_traction ≈ μ N
           ≈ 0.8 × 9.9
           ≈ 7.9 N per wheel
```

With a 90 mm wheel (`r = 0.045 m`):

```text
τ_at_slip ≈ F r
          ≈ 7.9 × 0.045
          ≈ 0.36 Nm
```

The DM-J3507 is rated at **0.8 Nm continuous** and **3 Nm peak**.

Therefore, on a high-grip indoor floor the wheel is likely to reach its traction limit well before reaching the actuator's continuous torque rating. Wheel torque is not the limiting factor for normal flat-floor operation.

At 90 mm diameter, nominal torque corresponds to a theoretical tangential force of:

```text
0.8 / 0.045 ≈ 17.8 N per wheel
```

and peak torque to:

```text
3.0 / 0.045 ≈ 66.7 N per wheel
```

Those figures substantially exceed the static friction force available to a ~2 kg robot. This is useful margin for control authority but must not be interpreted as usable sustained propulsion force.

---

## 9. Output-bearing and overhung-load considerations

The current flat-limb project already carries an unresolved risk: the DAMIAO output bearing's allowable radial and overturning moment have not yet been confirmed by the manufacturer.

That remains relevant to the wheel.

However, a well-packaged wheel can improve the geometry relative to a badly overhung foot or long axle because the wheel load plane can be kept close to the motor face.

At approximately three times static vertical load:

```text
F_3g ≈ 3 × 9.9 ≈ 30 N per wheel
```

Approximate bending moment from wheel-centre offset alone:

| Centre-plane offset from support | Moment at ~30 N |
|---:|---:|
| 10 mm | 0.30 Nm |
| **15 mm** | **0.45 Nm** |
| 20 mm | 0.60 Nm |
| 25 mm | 0.75 Nm |

The design rule is therefore simple:

> **Keep the wheel narrow and put its centre plane as close as practical to the DAMIAO output bearing.**

Do not mount the wheel on a long cantilevered axle merely because commercial robot wheels commonly use one.

Lateral impacts and falls may govern bearing moment rather than vertical landing load. This must be measured/validated on hardware before the motor bearing is accepted as the final wheel support.

If DAMIAO's output-bearing capacity proves inadequate, an outboard support bearing and fork can be added. That should be a fallback, not the starting architecture, because it recreates much of the mechanical complexity the wheel conversion is intended to remove.

---

## 10. Mechanical simplification with eight motors

Repurposing each ankle actuator as a wheel motor removes the **ankle articulation**, even though the actuator itself remains.

The following current features disappear:

- ankle-pitch joint function
- printed foot tray
- replaceable sole
- foot load-spreader structure
- ankle hard-stop geometry
- four FSR seats per foot
- eight FSR sensors total
- flat-foot pose constraints

The current ankle already has no far-side 6800 support bearing, so there is no bearing-count saving at the ankle. The present four support-bearing assemblies are used only by the hip-roll and hip-pitch joints.

### Existing kinematic constraints that disappear

The present walking geometry has two notable foot-driven restrictions:

1. the trailing ankle reaches about **27.5° against its 30° commissioning limit** in the current 84 mm walking stance;
2. inward hip roll is limited to about **6.9°** because the two 65 mm-wide soles collide.

A narrow wheel removes the first limitation entirely and should substantially reduce the second because the contact geometry is much narrower than the existing foot.

---

## 11. Mechanical simplification with six motors

If the robot becomes wheel-first rather than walking-first, the next joint to question is **hip roll**.

A flat-floor wheeled biped does not inherently need a powered hip-roll joint to remain upright in roll: the two laterally separated wheel contacts form a support line, and the centre of mass can remain laterally between them. Fore-aft balance still requires active wheel control because there is effectively no support polygon depth.

Removing hip roll gives:

```text
fixed pelvis mount → hip pitch → knee → wheel
```

on each side.

### Parts removed

Potentially removed from the current robot:

- 2 × DM-J3507 hip-roll actuators: **300 g**
- 2 × hip-roll bearing/journal/carrier assemblies: **32.6 g**
- current orthogonal hip-carrier geometry: pair currently **74.4 g**, though some replacement structure is still required
- associated fasteners and wiring

The remaining hip-pitch joints still need support and therefore retain the other two bearing/journal/carrier assemblies unless their architecture is changed separately.

### Replacement structure

The existing hip carrier cannot simply vanish without replacement. A fixed bracket or integrated pelvis feature must:

- hold each hip-pitch stator
- preserve the correct left/right leg planes
- carry sagittal and lateral loads into the torso
- keep the motor barrel exposed for cooling
- maintain connector access

A plausible fixed-mount pair should be substantially simpler and lighter than the present two-axis hip carriers, but its mass must be obtained from actual CAD rather than assumed.

### Mass estimate

Starting from the eight-motor wheeled version, a six-motor conversion approximately removes:

- 300 g of actuators
- 32.6 g of hip-roll support hardware
- some or most of the 74.4 g hip-carrier pair
- some wiring and fasteners

and adds a simpler fixed hip-pitch mount.

A realistic preliminary range is therefore approximately **1.60–1.70 kg** for the six-motor wheeled robot, depending primarily on wheel/adaptor mass and the new fixed hip structure.

This is an estimate, not a CAD mass result.

### What is lost by deleting hip roll

The main losses are:

- active lateral body shift
- active lateral wheel placement
- better adaptation to cross-slopes
- some single-wheel/one-leg recovery behaviours
- better handling of uneven left/right terrain
- walking-oriented side-step capability

For a flat indoor robot, these may be acceptable. For a hybrid intended to retain true stepping/walking experiments, hip roll should remain.

---

## 12. Why hip pitch and knee should remain

If the design is simplified beyond the ankle, the recommended stopping point is still **hip pitch + knee + wheel** per leg.

Keeping both sagittal leg joints provides:

- body-height control
- wheel placement relative to the torso
- crouching
- disturbance absorption
- terrain compliance
- jumping/landing experiments
- independent left/right leg length
- centre-of-mass shaping during acceleration/braking

Removing the knee is possible but makes the robot much less useful as a wheel-legged research platform. It becomes closer to an articulated self-balancing base than a biped with meaningful leg kinematics.

---

## 13. Mass comparison

The current baseline is **2,024.6 g**, and the current printed feet weigh **149.3 g per pair**.

### Eight-motor wheeled variant

If the feet are deleted and replaced by two complete wheel/adaptor assemblies:

| Wheel + adaptor mass | Approx whole-robot mass |
|---:|---:|
| 50 g each | 1.975 kg |
| 70 g each | 2.015 kg |
| 80 g each | 2.035 kg |
| 100 g each | 2.075 kg |

So the conservative wheel conversion is likely to be approximately mass-neutral or slightly lighter while remaining well under the current 2.3 kg ceiling.

### Six-motor wheeled variant

After additionally deleting the two hip-roll actuators and simplifying their support structure, the expected region is approximately:

**1.60–1.70 kg**

subject to CAD verification.

This is a materially different robot from the current ~2.0 kg machine: lower inertia, lower required knee torque, lower hip-pitch loads and lower peak electrical demand.

---

## 14. Electrical architecture

Reusing the existing DAMIAO motors keeps the electrical architecture unusually simple.

The current robot already has:

- 24 V motor bus
- CAN/CAN-FD architecture
- STM32G474-class realtime controller
- motor-side integrated drivers
- tethered power
- planned local bulk capacitance / regeneration handling

No separate wheel motor driver is required.

### Eight-motor wheel conversion

Electrical changes are mainly software/control changes:

- two ankle node roles become `left_wheel` and `right_wheel`
- wheel command mode becomes torque/velocity-oriented rather than bounded joint position
- FSR channels can be removed
- balance IMU becomes more safety-critical
- CAN scheduling should prioritize wheel traffic

### Six-motor variant

Removing the hip-roll motors also reduces:

- motor count from 8 to 6
- high-current branches by 2
- CAN actuator traffic by 25%
- wiring/connector count
- worst-case simultaneous bus-current envelope

The current project uses an approximate 4 A peak bus-current figure per DM-J3507. On that assumption:

```text
8 motors: about 32 A aggregate theoretical peak
6 motors: about 24 A aggregate theoretical peak
```

Those are not expected continuous currents, but they matter to fuse, contactor, connector, tether-drop and fault analysis.

---

## 15. Wheel-control update rate and CAN loading

A walking joint can tolerate somewhat more command latency than the wheel of an inverted-pendulum balancer. Wheel torque therefore becomes the highest-priority realtime traffic.

Reasonable initial targets for testing are:

| Loop / signal | Initial target range |
|---|---:|
| wheel torque/control | 500–1000 Hz |
| raw gyro/IMU update | 500–1000 Hz desirable |
| balance/state controller | 250–500+ Hz |
| hip/knee impedance | 100–500 Hz |
| supervisory planning | 20–100 Hz |

These are engineering starting points, not frozen requirements. Actual rates must follow measured bus utilization, actuator response, sensor latency and controller jitter.

If classic 1 Mbps CAN becomes congested, preferred solutions are:

1. use CAN-FD where supported and validated;
2. place the two wheel motors on a dedicated CAN/CAN-FD bus;
3. run hip/knee control at a lower rate than the wheel inner loop.

The existing design already allows multiple CAN-FD transceivers, so splitting the wheel bus does not require a fundamental controller redesign.

---

## 16. Regeneration becomes more important

This is the most important electrical consequence of the wheel conversion.

The robot is tethered. The bench supply generally cannot absorb regenerated energy, while a backdrivable balancing wheel repeatedly alternates between motoring and generating.

The current project already treats a robot-side low-ESR capacitor bank plus over-voltage clamp/brake strategy as required because the battery has been removed. Wheel balancing makes that requirement stronger.

### First-order capacitor sizing relationship

For a capacitor bank absorbing energy `E` while the bus rises from `V1` to `V2`:

```text
E = 1/2 C (V2² - V1²)

C = 2E / (V2² - V1²)
```

Illustrative only, for a 24 V bus allowed to rise to 28 V:

| Energy to absorb | Required capacitance |
|---:|---:|
| 1 J | ~9.6 mF |
| 2 J | ~19 mF |
| 3 J | ~29 mF |

This does **not** establish the final capacitor bank because real regeneration occurs over time and should also be handled by a brake/clamp path. The table only demonstrates that balancing events can put the required local capacitance into the tens-of-millifarads range surprisingly quickly.

Final sizing must use:

- measured wheel/motor regenerative current
- measured tether inductance/resistance
- actual bench-supply sink behaviour
- acceptable DAMIAO bus-voltage ceiling
- brake-resistor/clamp design

### E-stop implication

The energy absorber should remain connected to the motor-side DC bus when the system enters a fault state. Simply opening the tether while mechanically driven wheel motors are regenerating can create the over-voltage event the protection system is intended to prevent.

The final contactor/E-stop topology must therefore be designed together with the regen clamp rather than independently.

---

## 17. Sensors and state estimation

The current eight foot FSRs are unnecessary for a pure wheel contact and can be removed.

Useful wheel-ground information can instead come from:

- wheel encoder position/velocity
- commanded motor torque
- measured/estimated motor torque/current
- body gyro and accelerometer
- kinematic state of hip/knee joints

The IMU becomes a primary balance sensor rather than merely a body-orientation sensor.

The current BNO085 may be adequate, but it should not be assumed adequate without measuring **end-to-end latency and jitter** through the actual MCU interface.

If its fused orientation path is too slow or irregular for the balance loop, use a low-latency raw SPI gyro/IMU for the inner controller and retain the BNO085 for slower absolute orientation/state fusion.

---

## 18. Passive stability and development rig

The current feet provide a 115 × 65 mm support area. A crowned wheel reduces sagittal support to essentially a point contact at each side.

The wheeled robot therefore cannot stand upright in pitch with the controller disabled. Power loss means it falls unless physically supported.

Development should therefore use the planned overhead tether/gantry, ideally with a second loose safety line that catches a failed balance controller without carrying the robot during normal operation.

A removable parking stand may also be worthwhile for bench work, calibration and power-up.

This is not merely convenience: repeated uncontrolled falls are likely to become the dominant mechanical abuse case for the wheel hub, motor bearings and PA12-CF limb plates.

---

## 19. Failure modes to validate

Before accepting the wheel architecture, test the following explicitly.

### Mechanical

- DAMIAO output-bearing radial load and overturning moment
- wheel adaptor retention under repeated acceleration reversal
- wheel/core creep around an adaptor insert
- wheel runout
- PU tread/core bonding
- lateral wheel impact from a fall
- shaft/output-face fastener loosening
- clearance between wheel and shin through full knee/hip-pitch motion
- left/right wheel alignment and toe error

### Electrical

- regenerative bus overshoot
- wheel-current transients
- bench supply behaviour during regeneration
- CAN/CAN-FD latency and packet loss
- E-stop behaviour while wheels are generating
- motor thermal behaviour during continuous balance corrections

### Control

- encoder velocity noise at low speed
- gearbox backlash/deadband
- torque-command deadband
- gyro latency/jitter
- balance-loop stability across battery/supply voltage range
- controller behaviour at wheel saturation
- recovery after brief loss of ground contact

---

## 20. Recommended development sequence

### Phase W1 — bench wheel module

Use one of the six DM-J3507 actuators, before the rest are fitted to the legs.

Build:

- one DM-J3507
- one 80 mm commercial PU wheel
- one short direct wheel adaptor
- rigid bench fixture

Measure:

- wheel runout
- motor speed response
- torque deadband
- backlash
- CAN latency
- current
- regen voltage excursion
- output-bearing temperature/noise under radial load

This validates the wheel hardware without involving the complete biped.

### Phase W2 — two-wheel balance rig

Use two DMs and a simple rigid frame before finishing the complete robot.

Purpose:

- validate IMU path
- validate state estimator
- establish wheel-loop update rate
- establish CAN architecture
- characterize regeneration
- establish safe E-stop behaviour

This is much cheaper than debugging basic inverted-pendulum control on the finished articulated robot.

### Phase W3 — eight-motor wheel-leg prototype

Modify the current robot concept only at the ankle/foot:

- retain hip roll
- retain hip pitch
- retain knee
- convert ankle motor to wheel
- delete foot/FSR structure

This preserves maximum optionality and allows direct comparison with the walking architecture.

### Phase W4 — assess hip-roll value

Once the eight-motor wheeled robot is controllable, test whether hip roll materially improves the behaviours actually wanted:

- cross-slope handling
- lateral disturbance recovery
- one-wheel loading
- terrain transitions
- deliberate lateral body movement

If those capabilities are not important, proceed to the six-motor variant.

### Phase W5 — six-motor wheel-first CAD

Only after W4:

- delete hip-roll actuators
- integrate fixed hip-pitch mounts into the pelvis
- re-run all collision models
- re-run mass model
- re-derive knee/hip torque envelopes at the reduced mass
- revise harness and CAN node count
- revise power/fuse/current calculations

---

## 21. CAD work required if the concept is approved

The present study deliberately does not alter CAD. An approved wheel branch should include at least:

1. `wheel.kcl`
   - wheel envelope
   - measured donor-wheel dimensions
   - DAMIAO Ø30 register interface
   - 6 × M3 Ø24 output pattern
   - adaptor / retention geometry

2. wheel-specific shared parameters
   - diameter
   - width
   - tread radius/profile
   - centre-plane offset
   - mass allowance

3. replacement of `foot.kcl` in wheeled assembly models

4. new neutral and crouched wheel poses

5. wheel/shin collision checks throughout knee and hip-pitch ROM

6. track-width and left/right wheel-plane verification

7. revised overall-height derivation from wheel radius

8. wheel-specific mass entries

9. optional six-motor pelvis variant with fixed hip-pitch mounts

10. new fall/parking/support envelopes as required

The walking baseline should remain intact; the wheel configuration is better represented as an explicit variant than as a destructive overwrite until the concept proves itself.

---

## 22. Provisional parts shortlist

These are candidates for testing, not additions to the approved BOM.

| Function | Preferred candidate | Why |
|---|---|---|
| Wheel motor | **Existing DAMIAO DM-J3507-2EC 24 V** | already fitted, torque controlled, integrated driver/encoder, appropriate torque and speed |
| Prototype wheel | **Oxelo/Decathlon 80 mm 84A inline wheel** | inexpensive India stock, close to existing ankle height |
| Final-size donor | **Cosco 90 mm 85A cast PU inline wheel** | narrow crowned PU, available without bearing, useful 90 mm geometry |
| Higher-speed motor fallback | **CubeMars AK40-10** | 1.3 Nm rated, 370 rpm rated, 185 g; only if speed requirement justifies second ecosystem |
| Hub/adaptor | custom PA12-CF prototype, aluminium if required | direct Ø30 register / Ø24 PCD interface and short overhang |
| Outboard support | none initially | add only if DAMIAO bearing validation requires it |

---

## 23. Recommendation

### Immediate recommendation

Do **not** buy a separate wheel motor.

Use two of the six DAMIAO DM-J3507-2EC units as a wheel-control test platform and design an 80 mm wheel adaptor around the existing output register/bolt pattern.

### First robot architecture

Build the wheel conversion as:

```text
hip roll + hip pitch + knee + DM-driven wheel
```

per leg.

This removes the mechanical ankle joint and foot while preserving the rest of the current design. It should remain around 2.0 kg and requires minimal electrical change.

### Preferred wheel-first architecture

If the project becomes primarily a wheeled biped rather than a walking biped that can also roll, the strongest simplification is:

```text
hip pitch + knee + DM-driven wheel
```

per leg.

That gives **six motors total** and removes:

- both ankle articulations/feet
- both hip-roll actuators
- both hip-roll joints
- two support-bearing assemblies
- the orthogonal hip-carrier architecture
- all eight foot FSRs

A preliminary whole-robot mass around **1.60–1.70 kg** appears realistic, subject to new CAD.

This retains the two sagittal leg joints that provide most of the useful wheel-leg functionality while eliminating the two joint classes that become least valuable once the feet are replaced by wheels.

---

## 24. Source references

### Project-local sources

- `README.md` — current robot baseline and development state
- `parameters.kcl` — authoritative current kinematics and DAMIAO mounting geometry
- `foot.kcl` — current foot/ankle rotor load path
- `docs/PLAN.md` — active structural plan, torque envelope, ankle and hip-roll analysis, tether/regen rationale
- `docs/BOM.md` — current electrical and actuator BOM
- `tools/mass_budget.toml` — fixed masses and 2.3 kg ceiling
- `tools/mass_baseline.json` — current measured CAD mass baseline

### External component references checked 2026-08-31

- DAMIAO DM-J3507-2EC specifications and documentation mirror:  
  https://robotopian.com/products/damiao-dm-j3507-2ec-servo-motor
- DAMIAO product selector entry showing 24 V, 0.8 Nm rated, 3 Nm peak, 150 rpm rated, 460 rpm no-load, 150 g and CAN/CAN-FD:  
  https://www.worldrobotconference.com/profile/robot/download/2025/06/30/%E8%BE%BE%E5%A6%99%E7%A7%91%E6%8A%80DAMIAO%20-%202025%E5%B9%B4%E4%BA%A7%E5%93%81%E9%80%89%E5%9E%8B%E6%89%8B%E5%86%8C_20250630192546A441.pdf
- CubeMars AK40-10 official product page:  
  https://www.cubemars.com/product/ak40-10-robotic-actuator.html
- Decathlon India, Oxelo 80 mm 84A inline wheels:  
  https://www.decathlon.in/p/8540195/80mm-84a-inline-skating-wheels-4-pack-white
- Cosco India inline wheel range, including 90 mm / 85A:  
  https://store.cosco.in/products/skating-inline-skate-wheels

---

## 25. Open decisions

Before this becomes an implementation branch, settle these explicitly:

- Is the objective a **walking/rolling hybrid** or a **wheel-first biped**?
- Is 80 mm or 90 mm the target wheel after measuring donor-wheel width/mass?
- Does the DAMIAO output bearing tolerate the wheel's radial/lateral load without an outboard support?
- Is a single CAN-FD bus sufficient, or should the two wheel motors receive a dedicated bus?
- What measured bus energy/regen current must the local capacitor + brake system absorb?
- Does hip roll add enough real wheel-mode capability to justify 300+ g of actuators/support structure?

Until those are answered, the current walking baseline remains unchanged.
