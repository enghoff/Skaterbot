# Torque-Controlled Biped

A compact, approximately 380 mm, 8-DOF, 3D-printable biped designed around low-ratio, backdrivable, torque-controlled actuators.

The current baseline uses DAMIAO DM-J3507-2EC actuators, lightweight carbon-fibre leg members, and a PETG prototype structure. The immediate engineering gate is a manufacturable double-supported knee joint before committing to the complete robot.

## Key documents

- [`OPUS_HANDOFF.md`](OPUS_HANDOFF.md) — full mechanical engineering handoff and current design state.
- [`BOM.md`](BOM.md) — provisional bill of materials with India-focused sourcing notes and supply-risk flags.

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
