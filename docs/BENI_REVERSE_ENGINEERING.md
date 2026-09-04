# Beni Reverse-Engineering Study

**Status:** public-source engineering reconstruction; no physical Beni has been inspected  
**Date:** 2026-09-04  
**Target:** Mondo Robotics Beni all-terrain camera robot  
**Relevance to this repository:** Beni appears to use the same high-level six-axis architecture as the current wheeled branch: hip pitch + knee pitch + driven wheel on each side.

---

## 1. Executive summary

Beni is a useful reference design for this project because, behind the consumer shell and camera features, it appears to be a compact two-wheel, two-link-per-side robot with approximately six driven axes:

```text
left:  hip pitch -> knee pitch -> wheel
right: hip pitch -> knee pitch -> wheel
```

The available public material is sufficient to reconstruct the broad mechanical and electrical architecture with reasonably high confidence, but not to reproduce the product exactly. No public CAD, PCB design, BOM, firmware, motor drawings or production URDF have been found. Mondo has stated that the product itself is closed-source, while an RL training framework and a developer interface/SDK are on the roadmap.

The most interesting likely difference between Beni and the current Biped design is actuator packaging. A teardown posted in August 2026 prompted an experienced observer to note that both hip and knee actuators appear to be housed inside the main body with belt drives to the leg joints, reminiscent of the original MIT Mini Cheetah packaging. This is not yet confirmed by Mondo and should be treated as a **medium-confidence inference**, but it would explain Beni's unusually low moving-leg inertia and violent jump/self-righting performance.

Mondo has directly disclosed much more about the control stack than about the mechanics. Their locomotion work began from Unitree's `unitree_rl_gym`/ETH `legged_gym`, uses Isaac Gym and PPO, validates sim-to-sim in MuJoCo, and runs an RL policy above conventional joint PD control. Inputs include IMU data, joint positions, joint velocities and command inputs. Mondo says there is no separate hard-coded balance controller. They also state that off-the-shelf actuators created a large sim-to-real gap and that they moved to custom actuators using a low-latency RS485 protocol with DMA-based communication.

A Beni-like research platform is therefore realistically reproducible without cloning Beni exactly. The geometry, six-axis kinematic structure, RL architecture and likely electrical partitioning can all be reconstructed. The main challenge is not making a robot with the same topology; it is reaching Beni's combination of low mass, actuator bandwidth, approximately 18 mph claimed top speed, 25 cm claimed jump capability and reliable dynamic recovery.

For this repository, the most important lessons are:

1. **The six-motor wheel-first architecture is strongly validated by an independently developed real product.**
2. **Centralising hip/knee actuators may be worth investigating** because reducing leg inertia matters enormously for jumping and recovery.
3. **The present DM-J3507 direct-wheel concept cannot approach Beni's claimed speed.** At 80 mm wheel diameter, 460 rpm corresponds to about 1.93 m/s (6.9 km/h, 4.3 mph), while 18 mph would require roughly 1,920 rpm. Beni therefore almost certainly uses a much higher-speed wheel drive than the present direct-drive DAMIAO arrangement.
4. **Actuator dynamics and bus latency are first-order design parameters for RL sim-to-real**, not implementation details to defer until later.
5. Beni's camera stabilization was developed independently on an older parallel-leg test rig, suggesting that locomotion and camera/gimbal stabilization should remain modular subsystems.

---

## 2. What is publicly known

### 2.1 Product-level specifications

Mondo currently publishes the following Beni specifications:

| Parameter | Published value | Confidence |
|---|---:|---|
| Mass | 1.75 kg / 3.86 lb | High — manufacturer specification |
| Envelope | 215 x 180 x 180 mm | High — manufacturer specification |
| Maximum speed | up to ~18 mph / 29 km/h | Medium-high — manufacturer claim, repeated in independent coverage |
| Jump/obstacle height | up to 10 in / 25 cm | Medium-high — manufacturer claim with extensive demonstration footage |
| Battery endurance | ~1.5 h per battery | High as a product specification; real-world duty-cycle performance not independently measured |
| Main camera | 4K30 / 3K60 / 1080p100 | High — manufacturer specification |
| Storage | 32 GB + microSD | High — manufacturer specification |
| Tracking | on-device | High — manufacturer statement |
| Internet required for core following/filming | No | High — manufacturer statement |

The physical scale is particularly notable compared with this project. Beni is only about 180 mm tall but weighs roughly 1.75 kg; the current wheeled Biped branch is substantially taller while being in a similar mass class. Beni is therefore a very dense machine, with a large fraction of its mass concentrated in the central body.

### 2.2 Prototype timeline

Mondo publishes a useful development sequence:

- **April 2025 — Concept:** rough model used to test the idea.
- **July 2025 — “The Skeleton”:** first working prototype, with exposed bolts and wiring and no cosmetic shell.
- **October 2025 — “It's Alive”:** design described as finalized and a workable Beni form established.
- **December 2025 — outdoor testing.**
- **March 2026 — reliable self-righting milestone.**
- **May 2026 — 30+ beta units reportedly placed with users.**

This evolution footage is more valuable for reverse engineering than polished launch material because early chassis expose link geometry, transmissions, wiring paths and actuator placement that later shells obscure.

### 2.3 Older camera-stabilization prototype

Mondo has also published an older **parallel-leg prototype** that predates the current wheel-legged chassis. They explicitly say this rig was used to isolate and stress-test gimbal stabilization and camera point-of-view behavior, and that the stabilization logic transferred to Beni even though the mechanical platform changed completely.

That is a strong architectural clue:

```text
                 Beni system
                     |
          +----------+----------+
          |                     |
   locomotion stack       camera stack
          |                     |
      RL policy           stabilization
          |                     |
  hip/knee/wheels       gimbal / horizon
```

For a research clone, the camera subsystem should therefore be treated as separable from the locomotion controller rather than embedded into it.

---

## 3. Likely mechanical architecture

## 3.1 Degrees of freedom

The visible motion is consistent with six powered axes:

| Axis | Quantity | Function | Confidence |
|---|---:|---|---|
| Hip pitch | 2 | Rotates complete leg fore/aft relative to body | High |
| Knee pitch | 2 | Changes effective leg length and wheel position | High |
| Wheel rotation | 2 | Propulsion and differential steering | High |
| Hip roll/yaw | 0 apparent | No clear evidence of an additional lateral leg DOF | Medium-high |

The resulting per-side kinematic chain is:

```text
body
  |
  +-- hip pitch
        |
       thigh
        |
        +-- knee pitch
              |
             shin
              |
              +-- wheel rotation
```

This is effectively the same gross topology as the six-motor wheeled architecture already adopted on the current Biped branch.

## 3.2 Body-mounted joint actuators: leading hypothesis

The August 2026 teardown is currently the strongest public clue about the hidden transmission. A commenter familiar with legged-robot mechanisms observed that the layout looked “very reminiscent of the initial MIT Mini Cheetah,” with **both hip and knee actuators in the main body and belt drives**.

This is not an official schematic, so it must not be recorded as established fact. However, it is mechanically plausible and consistent with Beni's behavior.

A likely arrangement is approximately:

```text
                    MAIN BODY
          +--------------------------+
          | hip motor   knee motor   |
          +----+-----------+---------+
               |           |
          hip shaft       belt / remote drive
               |           |
             thigh =================== knee pulley
                                       |
                                      shin
                                       |
                                  wheel motor
                                       O
```

Possible variants include coaxial shafts, nested pulleys, belts running through hollow links, or a linkage rather than a continuous belt. Better teardown imagery is required before committing to a specific implementation.

### Why centralising the knee motor matters

Moving the knee actuator from the knee to the body:

- reduces moving leg mass;
- lowers rotational inertia about the hip;
- reduces energy required to swing the leg rapidly;
- makes high-acceleration recovery motions easier;
- protects expensive actuators inside the body;
- can improve impact survivability;
- allows the outer leg to be predominantly lightweight links and transmission components.

The costs are:

- more complex transmission geometry;
- belt compliance and possible backlash;
- bearing and pulley alignment requirements;
- more difficult tensioning/service access;
- coupling between structural deflection and joint accuracy;
- more complex routing across a moving hip joint.

For this project this is worth a dedicated design study, but not an immediate CAD change. The current repository instructions require whole-robot architectural changes to be proposed rather than silently implemented.

## 3.3 Wheel motors

Beni's claimed speed imposes a very different wheel-drive requirement from the present DM-J3507 wheel concept.

At 18 mph:

```text
v ~= 8.05 m/s
```

For an estimated 70–80 mm wheel diameter:

```text
70 mm wheel: ~2,195 rpm
80 mm wheel: ~1,921 rpm
```

Even with a 100 mm wheel, approximately 1,537 rpm is required.

By comparison, the current DM-J3507-2EC figures used in this repository are approximately:

```text
rated output speed   ~150 rpm
no-load maximum      ~460 rpm
```

At 80 mm diameter:

```text
150 rpm -> ~0.63 m/s -> ~2.3 km/h -> ~1.4 mph
460 rpm -> ~1.93 m/s -> ~6.9 km/h -> ~4.3 mph
```

Therefore a Beni-speed machine cannot simply use the present DAMIAO joint actuator directly as an 80 mm wheel drive. A clone targeting Beni's dynamic envelope would need one of:

- a substantially higher-speed integrated wheel actuator;
- a different reduction ratio optimized for wheel rotation;
- a separate high-speed BLDC + reduction stage;
- a custom actuator family with separate wheel and joint variants.

This does **not** invalidate the DM-J3507 wheel choice for the current Biped objectives. It only means the current design is a low-speed research platform rather than a Beni-speed camera robot.

## 3.4 Jump energy

For a 1.75 kg robot raising its centre of mass by 0.25 m, the minimum gravitational potential-energy increase alone is:

```text
E = m g h
  = 1.75 * 9.81 * 0.25
  ~= 4.3 J
```

That ignores:

- kinetic energy retained after takeoff;
- acceleration of the legs and wheels;
- actuator, transmission and electrical losses;
- body pitch/rotation used for flips;
- spring compression or other energy storage if present.

The number is therefore a lower bound, not an actuator-sizing result. High peak power and excellent torque bandwidth are still implied by the observed motion.

---

## 4. Electronics and communications

Mondo has not published a production schematic or board-level architecture, but its engineering posts provide enough information for a plausible partitioning:

```text
                 application / vision compute
                  tracking, camera, UI
                         |
                         | commands / state
                         v
                  real-time controller
                    MCU + IMU
                         |
                  low-latency RS485
             +-----------+-----------+
             |           |           |
          actuator    actuator    actuator ...
             |           |           |
          encoder      encoder     encoder
             |           |           |
            BLDC        BLDC        BLDC
```

Mondo explicitly reports moving away from off-the-shelf actuators and working with a motor supplier on custom actuators using **RS485**. They describe using DMA on both the main controller and motor driver to reduce communication overhead/latency.

### Why this matters

Their own sim-to-real account identifies the actuation system as one of the largest determinants of transfer quality. The desired properties were effectively:

- low command latency;
- high torque bandwidth;
- repeatable actuator response;
- close-to-linear current/torque behavior;
- dynamics that resemble the simulation model.

This is important for the Biped project because CAN versus RS485 is less important than the underlying engineering requirement: **the complete command-to-torque path must be characterized and deterministic enough that simulation can represent it.**

A CAN actuator can still be suitable if its latency, update rate, internal filtering and torque response are understood and modeled. Conversely, merely choosing RS485 does not automatically produce Unitree-like performance.

---

## 5. Locomotion control stack

Mondo has publicly described the main control approach.

### 5.1 Training pipeline

They report starting from:

- Unitree `unitree_rl_gym`;
- ETH Zurich `legged_gym` heritage;
- Isaac Gym for simulation/training;
- PPO for the policy optimization;
- MuJoCo for sim-to-sim validation before hardware deployment.

### 5.2 Runtime structure

The disclosed control stack is approximately:

```text
IMU
joint position
joint velocity
motion command
      |
      v
   RL POLICY
      |
      v
joint position targets
      |
      v
  joint PD control
      |
      v
motor current / torque
```

Mondo explicitly says that balance, jumping and recovery are learned behaviors rather than separate hard-coded balance modules.

### 5.3 Sim-to-real lesson

Mondo initially attempted to compensate for hardware mismatch by increasing domain randomization, including concepts such as motor delay, mass variation and friction variation. They found that excessive randomization made policies more conservative and could prevent learning highly dynamic motions such as flips.

Their reported breakthrough was improving the real hardware until it behaved more like the simulated actuator model. After reducing communication latency and improving actuator behavior, less randomization was required and flipping became substantially more stable.

This is probably the single most transferable lesson for this repository:

> Do not treat the actuator, bus and embedded control loops as a black box and expect aggressive domain randomization to compensate for unknown dynamics.

A useful development loop would instead be:

```text
characterize hardware
       |
       v
fit/update actuator model
       |
       v
train in simulation
       |
       v
deploy to robot
       |
       v
measure discrepancy
       +----------> repeat
```

---

## 6. Vision and camera subsystem

Beni's core following and filming functions are stated to run on-device. Mondo has not disclosed the application processor in enough detail to reconstruct the production compute board.

For a research clone there is little reason to duplicate the consumer compute stack. A more open architecture would be preferable:

```text
              Jetson Orin-class SBC
                     |
         +-----------+-----------+
         |           |           |
     main camera   perception  high-level planner
         |           |           |
         +-----------+-----------+
                     |
              real-time MCU
                     |
              motor bus
```

This would make it much easier to experiment with tracking, VLMs, mapping, ROS 2, logging and policy deployment while preserving a deterministic MCU-level locomotion loop.

Mondo's older parallel-leg stabilization rig also argues for keeping camera/gimbal stabilization independent of the balance policy. The robot body will necessarily pitch and translate during aggressive locomotion; the camera system should compensate for that rather than forcing locomotion to optimize every frame directly.

---

## 7. Open-source and developer-access status

As of **2026-09-04**, no public production Beni repository containing the following has been found:

- CAD;
- BOM;
- URDF/MJCF for the production chassis;
- PCB schematics/layout;
- motor design files;
- motor firmware;
- locomotion firmware;
- trained production policy;
- camera/tracking source code.

Mondo has publicly described the **product itself as closed-source**. However, several later statements indicate increasing developer support:

- they plan to release an RL training environment/framework;
- they have said printable accessory files are planned;
- a top USB port is intended to support attachments;
- developer/API access was not available at Kickstarter launch;
- in August 2026 a Mondo response said an SDK is planned for Q4, with the final form (SDK versus CLI) still undecided;
- a July response said the RL framework would be open-sourced and the robot would receive an SDK after Kickstarter shipping.

Until those releases actually appear, any reproduction should be treated as a **clean-room, public-source reconstruction**, not as a fork of an open Beni hardware project.

---

## 8. What can realistically be reverse engineered

### From public footage and documentation alone

| Subsystem | Estimated recoverability | Notes |
|---|---:|---|
| Overall envelope | ~95% | Published dimensions provide scale |
| Gross kinematics | ~90–95% | Six-axis topology is visually clear |
| Link lengths/joint centres | ~80–90% | Can be solved from calibrated frames and multiple poses |
| Wheel size | ~80–90% | Scale from known body envelope |
| Actuator placement | ~70–80% | Teardown materially improves visibility |
| Remote knee transmission topology | ~60–75% | Belt-drive hypothesis credible but not confirmed |
| Reduction ratios | ~30–50% | Requires frame-by-frame motion/geometry analysis |
| Structural materials | ~40–60% | Some parts can be inferred visually; internal reinforcement unknown |
| Electrical partitioning | ~70% | Mondo's technical posts give useful clues |
| PCB implementation | <20% | Package markings and board photos required |
| Battery chemistry/configuration | ~30% | Endurance known, pack internals not yet established |
| Motor constants/windings | <20% | Essentially impossible from external footage alone |
| RL architecture | ~85–90% | Mondo has disclosed framework and runtime structure |
| Exact production policy | 0% | Not public and unnecessary for a functional clone |
| Camera/tracking implementation | low | Product behavior is visible but detailed algorithms are proprietary |

### With a physical production Beni

A non-destructive dimensional inspection plus teardown would raise most hardware categories above 90% confidence. Useful measurements would include:

- mass and centre of mass;
- exact joint centres and link lengths;
- wheel diameter/width/tire material;
- actuator dimensions and labels;
- pulley tooth counts and belt pitch;
- joint bearing arrangement;
- output-axis reductions;
- battery voltage, capacity and discharge rating;
- MCU/application-processor/IMU markings;
- motor-driver topology;
- bus physical layer and update frequency;
- command/feedback packet timing;
- static torque/current relation;
- step response and latency.

The trained policy itself would still not be necessary. An independently trained controller can target the reconstructed plant.

---

## 9. Recommended reverse-engineering workflow

### Phase 1 — Source archive and frame extraction

Collect and preserve:

1. July 2025 “Skeleton” imagery;
2. early-prototype evolution video;
3. August 2026 teardown footage;
4. stair-jump and self-righting videos;
5. side-on high-speed running footage;
6. official orthographic/product images;
7. the older parallel-leg camera-stabilization prototype.

For each video, extract frames at mechanically useful poses: full extension, maximum crouch, wheels level, body approximately horizontal, and frames where belts/pulleys/shafts are exposed.

### Phase 2 — Photogrammetric geometry reconstruction

Use the published 215 x 180 x 180 mm envelope as an initial scale reference.

Estimate:

- hip-axis locations;
- knee-axis locations;
- hip-to-knee length;
- knee-to-wheel-axis length;
- wheel diameter/width;
- left/right track width;
- body clearance;
- maximum joint ranges.

Multiple frames should be solved simultaneously rather than measuring one image. Perspective distortion can otherwise create large errors.

### Phase 3 — Transmission reconstruction

From teardown/Skeleton footage:

- identify actuator cans;
- identify belt runs and pulley diameters;
- determine whether knee output is remote-driven from the torso;
- determine whether hip and knee drives are coaxially packaged;
- estimate reduction ratios from pulley tooth counts;
- identify tensioners/idlers;
- identify bearings and structural load paths.

Do not CAD a detailed belt mechanism until the central-actuator hypothesis is verified from more than one view.

### Phase 4 — Dynamic inference from video

Use high-frame-rate clips where available to estimate:

- wheel angular velocity;
- joint angular velocity;
- jump takeoff time;
- body pitch rate during flips;
- landing/recovery joint trajectories;
- approximate acceleration envelopes.

These measurements can constrain actuator requirements even before exact motor specifications are known.

### Phase 5 — Build a parameterized simulation model

Create a Beni-inspired model rather than a nominal exact clone:

```text
body
  hip_L -> thigh_L -> knee_L -> shin_L -> wheel_L
  hip_R -> thigh_R -> knee_R -> shin_R -> wheel_R
```

The first simulation should expose uncertain values as parameters:

- link lengths;
- body mass/inertia;
- leg mass distribution;
- wheel radius;
- motor torque limits;
- motor velocity limits;
- command latency;
- PD gains;
- transmission compliance.

This allows uncertainty to be explored directly rather than hidden in guessed CAD dimensions.

### Phase 6 — COTS physical mule

The first physical prototype should optimize observability and modifiability, not cosmetic resemblance:

- machined or printed central frame;
- COTS BLDC actuators with known feedback/control interfaces;
- replaceable pulleys/belts;
- exposed test points;
- real-time MCU;
- separate high-level compute;
- comprehensive logging of command, encoder, IMU and bus timing.

Initial targets should be:

1. static balancing;
2. normal driving;
3. body-height changes;
4. rough-terrain wheel placement;
5. controlled low jump;
6. self-recovery;
7. only then flips/high-speed running.

### Phase 7 — Optimize only after the plant is understood

Once the COTS mule can reproduce the desired dynamics:

- centralize actuators where beneficial;
- reduce link inertia;
- optimize belt ratios;
- raise wheel speed;
- reduce communication latency;
- integrate custom electronics;
- package the battery and compute into a compact torso.

This sequence mirrors Mondo's own published lesson: dynamic RL performance became much easier when the physical plant was made predictable rather than merely increasing simulation randomization.

---

## 10. Specific implications for the current Biped design

The current wheeled branch already converges on Beni's apparent topology, which is significant independent validation of the architectural choice.

### 10.1 What aligns well

Current Biped:

```text
hip pitch -> knee pitch -> wheel
```

Beni, inferred:

```text
hip pitch -> knee pitch -> wheel
```

Both eliminate hip roll and conventional feet, using differential wheel torque plus sagittal leg motion.

### 10.2 Main mechanical difference to investigate

The current Biped places integrated actuators at the joints. Beni may centralize both hip and knee actuation in the body.

That suggests a future design study:

**Question:** can the current knee actuator be moved into the pelvis/torso and drive the knee remotely without giving up torque control quality or adding excessive belt compliance?

Before changing CAD, compare:

- removed distal mass;
- added pulley/belt/bearing mass;
- reflected inertia;
- belt stiffness;
- backlash;
- torsional compliance;
- tensioning method;
- manufacturability;
- service access;
- effect on control bandwidth.

The answer is not automatically “yes”; Beni's solution may depend on custom motors and a packaging/manufacturing capability beyond the present project constraints.

### 10.3 Main electrical/control lesson

The current project should log and eventually measure, per actuator:

- command period;
- one-way/round-trip bus latency;
- jitter;
- current/torque response;
- internal filtering;
- velocity saturation;
- temperature dependence;
- position/velocity feedback delay.

These values should enter the simulation explicitly. Beni's published RL experience suggests this is more important than simply increasing domain randomization.

### 10.4 Main speed lesson

If the objective remains modest indoor mobility, the existing DM-J3507 wheel arrangement is reasonable.

If the objective shifts toward Beni-like running speed, the wheel actuator must become a separate design problem. The joint actuator's output-speed range is far too low to reach anything close to 18 mph with an ~80 mm wheel.

A future high-speed configuration may therefore use:

```text
hip/knee: high-torque low-speed joint actuators
wheel:    high-speed BLDC optimized for continuous rotation
```

rather than forcing one actuator family to satisfy both tasks.

---

## 11. Suggested next work

The best immediate follow-up is **not** to redesign the Biped around guesses. It is to turn the public Beni footage into measurements.

Recommended next deliverables:

1. `reference/beni/` source index containing URLs, dates and what each clip reveals;
2. calibrated frame captures from the Skeleton and teardown footage;
3. a geometry worksheet with confidence bounds for every inferred dimension;
4. a simple 2D kinematic reconstruction before 3D CAD;
5. a transmission diagram showing confirmed vs inferred belt/shaft paths;
6. an actuator requirement sheet derived from observed joint/wheel speeds;
7. a comparison against DM-J3507 capabilities;
8. only after that, a separate proposal for any Biped architecture change.

A particularly valuable analysis would be to estimate Beni's actual hip/knee angular velocities from the self-righting and flip videos. Combined with approximate geometry and the known 1.75 kg mass, those measurements would provide a much more defensible actuator target than trying to infer motor models from appearance alone.

---

## 12. Source index

### Primary / manufacturer sources

- Mondo Robotics product page — specifications, dimensions, camera, storage, battery:  
  https://mondorobotics.com/

- Mondo Robotics “About Us” — development timeline including Concept, Skeleton, outdoor testing, recovery and beta units:  
  https://mondorobotics.com/pages/about-us

- Mondo Robotics guide — claimed ~18 mph tracking speed and product positioning:  
  https://mondorobotics.com/blogs/guides/meet-beni-the-camera-robot-that-captures-what-youd-otherwise-miss

- Kickstarter campaign:  
  https://www.kickstarter.com/projects/mondorobotics/beni-all-terrain-camera-robot

- Mondo Robotics — early prototypes versus current build:  
  https://www.reddit.com/r/MondoRobotics/comments/1uh7l10/early_prototypes_vs_current_build_the_rd_process/

- Mondo Robotics — RL journey / sim-to-real / custom RS485 actuators / PPO / Unitree stack:  
  https://www.reddit.com/r/MondoRobotics/comments/1szuepv/our_rl_journey_so_far_what_we_learned_what_broke/

- Mondo Robotics — older parallel-leg camera-stabilization prototype:  
  https://www.reddit.com/r/MondoRobotics/comments/1rxuuyu/before_there_were_legs_there_was_this/

- Mondo Robotics discussion of SDK, printable accessories, USB attachment port and planned RL environment:  
  https://www.reddit.com/r/MondoRobotics/comments/1to7zbm/beni_is_coming_early_bird_pricing_available_now/

- Mondo Robotics response describing planned SDK/CLI for Q4 2026:  
  https://www.reddit.com/r/MondoRobotics/comments/1vuwc1f/can_i_connect_codex_to_beni/

- Mondo Robotics response stating product closed-source while an RL training framework is planned:  
  https://www.reddit.com/r/robotics/comments/1tmvczp/stairs_are_hard_part_2/

- Mondo Robotics / robotics discussion stating planned open-source RL framework and SDK after Kickstarter shipping:  
  https://www.reddit.com/r/robotics/comments/1uti96j/im_glad_to_share_the_little_robot_we_designed/

### Teardown / secondary observations

- August 2026 teardown post; commenter identifies apparent body-mounted hip/knee actuators and belt drives. Treat as an informed observation, not an official schematic:  
  https://www.reddit.com/r/MondoRobotics/comments/1vzangn/beni_the_camera_robot_goes_under_the_knife/

- New Atlas launch coverage — published product claims and imagery:  
  https://newatlas.com/consumer-tech/mondo-beni-robot-action-cam/

- Hackster coverage — product architecture/specification summary:  
  https://www.hackster.io/news/this-camera-robot-follows-you-anywhere-to-get-the-perfect-shot-d07ffd7c231e

---

## 13. Confidence convention

Throughout this note:

- **High:** directly published by Mondo or clearly visible across multiple independent views.
- **Medium:** strongly consistent with public imagery/engineering constraints but not explicitly confirmed.
- **Low:** plausible hypothesis requiring better imagery, teardown evidence or measurement.

No inferred dimension, transmission detail or actuator characteristic should be promoted into the main CAD/BOM as fact without either primary documentation or a reproducible measurement.
