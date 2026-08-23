# Torque-Controlled Biped

A compact, approximately 380 mm, 8-DOF, 3D-printable biped designed around low-ratio, backdrivable, torque-controlled actuators.

The current baseline uses DAMIAO DM-J3507-2EC actuators, lightweight carbon-fibre leg members, and a PETG prototype structure. The immediate engineering gate is a manufacturable double-supported knee joint before committing to the complete robot.

## Key documents

All project documentation lives in [`docs/`](docs/):

- [`docs/AGENTS.md`](docs/AGENTS.md) — binding instructions for any agent working this CAD. **Read this first.**
- [`docs/OPUS_HANDOFF.md`](docs/OPUS_HANDOFF.md) — full mechanical engineering handoff and current design state.
- [`docs/NOTES.md`](docs/NOTES.md) — as-built notes on the current skeleton: dimensions, mass estimates, known weaknesses.
- [`docs/CHECKLIST.md`](docs/CHECKLIST.md) — what is done and what the next refinement pass must cover.
- [`docs/BOM.md`](docs/BOM.md) — provisional bill of materials with India-focused sourcing notes and supply-risk flags.

## Repository layout

The KCL sources sit at the repository root because Zoo Design Studio expects
`project.toml` and `main.kcl` there.

```text
bipedal/
├── project.toml           Zoo Design Studio project file
├── main.kcl               neutral standing assembly
├── pose_check.kcl         crouched single-step pose / clearance check
├── parameters.kcl         shared dimensions and joint angles
├── actuator.kcl           simplified DM-J3507-2EC envelope
├── pitch_yoke.kcl         reusable double-supported pitch joint
├── hip_carrier.kcl        orthogonal hip roll/pitch carrier
├── thigh.kcl, shin.kcl    twin carbon-tube leg modules
├── foot.kcl               foot frame, sole, sensor seats
├── torso.kcl              torso frame
├── payload_envelopes.kcl  reserved battery/electronics volumes
├── docs/                  project documentation (see above)
└── secrets/               local credentials, not committed
```

Exported geometry (`*.stl`, `*.step`) and the Design Studio `thumbnail.png` are
deliberately untracked.

## Current baseline

- Height: 380 mm
- DOF: 8 (hip roll, hip pitch, knee pitch, ankle pitch per leg)
- Actuator: DAMIAO DM-J3507-2EC, 24 V
- Target mass: <= 2.0 kg
- Current estimated mass: ~1.92–1.96 kg
- Power: provisional 6S LiPo
- Mechanical prototype: PETG + carbon-fibre tubes

## Development order

1. Characterise 1–2 actuators.
2. Engineer and print one real knee assembly.
3. Validate loads, stiffness, thermal behaviour and backdrivability.
4. Build one complete leg.
5. Build realtime torque/impedance control.
6. Only then commit to the complete robot.
