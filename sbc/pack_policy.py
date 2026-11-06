# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "onnx>=1.16", "onnxruntime>=1.18", "pyyaml>=6.0"]
# ///
"""Write a trained policy as the one file sbc/balance.py needs on the robot.

    uv run sbc/pack_policy.py exports/rl/<run>

Reads the run's exported/policy.onnx and params/env.yaml, and writes
<run>/exported/policy.npz: the network's numbers, and every setting of the task's
that the loop on the robot needs, so that nothing about a policy is typed in by
hand and only numpy is needed to run it. The network is read by
firmware/policy/export.py's reader, which holds it against onnxruntime before
this writes anything, as it does for the firmware.

It refuses a balance policy whose commands could take a leg outside its window in
sbc/sysid_tests.py, the owner's limit on the shins among them. A jump policy's legs
reach further, 0.6 and 1.2 rad about the crouch, so its targets are held inside the
windows instead, and the pack says so (`leg_held_to_windows`).

A jump policy's pack carries a `jump` section as well: what docs/POLICY_INTERFACE.md's
hand-over needs from its run (sbc/policy_loop.py's TwoPolicies).
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "firmware" / "policy"))
sys.path.insert(0, str(HERE))

import export  # noqa: E402
import sysid_tests as st  # noqa: E402

URDF = ROOT / "simulation" / "urdf" / "wheeled_biped.urdf"


class _Loader(yaml.SafeLoader):
    """env.yaml as Isaac Lab writes it: tuples tagged, and the odd object."""


_Loader.add_constructor(
    "tag:yaml.org,2002:python/tuple",
    lambda loader, node: tuple(loader.construct_sequence(node)),
)
_Loader.add_multi_constructor("tag:yaml.org,2002:python/", lambda *_: None)


def urdf_facts() -> tuple[dict, float]:
    """Each joint's travel, and the wheel's rolling radius."""
    root = ET.parse(URDF).getroot()
    travel = {}
    for joint in root.iter("joint"):
        limit = joint.find("limit")
        if limit is not None and limit.get("lower") is not None:
            travel[joint.get("name")] = (
                float(limit.get("lower")),
                float(limit.get("upper")),
            )
    radius = None
    for link in root.iter("link"):
        if "wheel" in link.get("name", ""):
            for shape in link.iter("cylinder"):
                collision = shape
                radius = max(radius or 0.0, float(collision.get("radius")))
    if radius is None:
        sys.exit(f"{URDF}: no wheel with a cylinder for its radius")
    return travel, radius


def settings(cfg: dict) -> dict:
    robot = cfg["robot"]
    pose = robot["init_state"]["joint_pos"]
    legs = robot["actuators"]["legs"]
    wheels = robot["actuators"]["wheels"]
    if wheels["stiffness"] != 0.0:
        sys.exit("this run's wheels are not torque-driven")
    if legs["stiffness"] != st.HOLD_KP or legs["damping"] != st.HOLD_KD:
        sys.exit(
            f"this run's legs are at kp {legs['stiffness']}, kd {legs['damping']}. The "
            "robot's hips buzz at 39 Hz at higher gains (docs/SYSID.md): look first."
        )
    jumps = cfg.get("jump_clearance_m") is not None
    if cfg.get("observe_battery") and not jumps:
        sys.exit("this loop runs a balance or a jump policy, and this run is neither")
    travel, radius = urdf_facts()
    factor = robot["soft_joint_pos_limit_factor"]
    crouch = [pose["hip_pitch_.*"] if "hip" in j else pose["knee_.*"] for j in st.LEGS]
    leg_scale = list(cfg["leg_action_scale_rad"])
    lo, hi = [], []
    for j in st.LEGS:
        a, b = travel[j]
        mid, half = (a + b) / 2, (b - a) / 2 * factor
        lo.append(mid - half)
        hi.append(mid + half)
    held = False
    for k, j in enumerate(st.LEGS):
        least = max(crouch[k] - abs(leg_scale[k]), lo[k])
        most = min(crouch[k] + abs(leg_scale[k]), hi[k])
        low, high = st.WINDOWS[j]
        if least < low or most > high:
            if not jumps:
                sys.exit(
                    f"{j}: its commands reach {least:.2f} to {most:.2f}, "
                    f"outside {low} to {high}"
                )
            lo[k], hi[k] = max(lo[k], low), min(hi[k], high)
            held = True
    meta = {
        "legs": list(st.LEGS),
        "wheels": list(st.WHEELS),
        "crouch": crouch,
        "leg_scale": leg_scale,
        "leg_lo": lo,
        "leg_hi": hi,
        "kp": legs["stiffness"],
        "kd": legs["damping"],
        "wheel_scale": cfg["wheel_action_scale_nm"],
        "wheel_radius": radius,
        "default_height": cfg["default_leg_height_m"],
        "height_range": list(cfg["command_leg_height_m"]),
        "speed_range": list(cfg["command_lin_vel_x"]),
        "turn_range": list(cfg["command_yaw_rate"]),
        # Trained inside the diamond between the two tops, not the rectangle.
        "envelope": "command_envelope_start" in cfg,
        "scale_height": bool(cfg.get("scale_height_command", False)),
        "max_tilt_rad": cfg["max_tilt_rad"],
        "decimation": cfg["decimation"],
        "leg_held_to_windows": held,
    }
    if jumps:
        meta["jump"] = {
            "clearance_m": list(cfg["jump_clearance_m"]),
            "leg_gain_range": cfg["leg_gain_range"],
            "crouch_s": cfg.get("jump_crouch_s", 0.0),
            "crouch_tolerance_m": cfg.get("jump_crouch_tolerance_m", 0.005),
            "window_s": cfg.get("jump_window_s", 1.5),
            "takeoff_window_s": cfg["jump_takeoff_window_s"],
            "observe_battery": bool(cfg.get("observe_battery", False)),
            "score_to_target": bool(cfg.get("jump_score_to_target", False)),
        }
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run", type=Path)
    args = ap.parse_args()

    policy = args.run / "exported" / "policy.onnx"
    cfg = yaml.load((args.run / "params" / "env.yaml").read_text(), Loader=_Loader)
    if cfg["decimation"] != 4 or abs(cfg["sim"]["dt"] - 0.0025) > 1e-9:
        sys.exit(
            "this loop runs at 100 Hz, and this run's policy step is something else"
        )
    net = export.load(policy)
    ours, theirs = export.check(net, policy)
    meta = settings(cfg)
    meta.update(
        run=args.run.name,
        digest=export.digest(policy),
        n_obs=net.n_obs,
        n_act=net.n_act,
        layers=len(net.layers),
        elu_alpha=net.elu_alpha,
    )
    arrays = {
        "offset": net.offset,
        "divisor": net.divisor,
        "meta": np.array(json.dumps(meta)),
    }
    for k, (w, b) in enumerate(net.layers):
        arrays[f"w{k}"], arrays[f"b{k}"] = w.astype(np.float32), b.astype(np.float32)
    out = args.run / "exported" / "policy.npz"
    np.savez(out, **arrays)
    print(
        f"{out}: {meta['run']}, {net.n_obs} inputs, {net.n_act} outputs, "
        f"{sum(w.size + b.size for w, b in net.layers)} weights, {out.stat().st_size} bytes. "
        f"Against the exact answer, this reading is off by {ours:.1e}, onnxruntime by {theirs:.1e}."
    )
    print(
        json.dumps(
            {k: v for k, v in meta.items() if k not in ("legs", "wheels")}, indent=1
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
