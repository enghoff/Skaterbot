# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy>=1.26", "mujoco>=3.2", "onnxruntime>=1.18",
#                 "pyyaml>=6.0", "pygame>=2.5"]
# ///
"""Drive the robot with a trained policy, locally, in MuJoCo.

    uv run simulation/mujoco/drive.py
    uv run simulation/mujoco/drive.py --run exports/rl/<run>
    uv run simulation/mujoco/drive.py --rough 1
    uv run simulation/mujoco/drive.py --check

--rough lays the robot's ground out as the rough task trained it: 4 m tiles of
bumps, waves, blocks, rails and pyramid slopes, around the flat tile it starts
on. 1 is the hardest the curriculum reached (15 mm bumps, blocks and rails,
30 mm waves, 1 in 4 slopes), and it scales in proportion, so 2 is twice what
the policy has ever seen.

Free, offline, and on the CPU: Isaac Sim needs an NVIDIA card and this runs on
anything. It loads the robot from the URDF and runs the policy exactly as it
was trained -- the same inputs in the same order, the same 100 Hz, the same
motor model -- with a keyboard or a game controller giving the commands.

A RUN DIRECTORY is what exports/rl/ holds: the exported policy and the
configuration Isaac Lab saved when it trained it (params/env.yaml). Everything
this script needs to know about the task -- action scales, leg gains, the
crouch the legs are held around, the motor's torque-speed line, the physics
step -- is read from that file, so a policy is always driven the way it was
trained and nothing here is a second copy of a number. A jump policy (one with
the trigger among its inputs) gets a jump button.

TO THE LIMITS. Commands run over everything the policy was trained on, which
for the jump task is the wheels' whole envelope: full stick is the top speed or
the fastest turn, and a jump at full trigger is the highest target. Speed and
turn share the wheels, so for a policy trained that way a command asking for
more of both than the wheels have is scaled back into the envelope, as it was
in training. The overlay shows how close the motors are to their own limits:
wheel speed against the no-load speed, and the peak torque of the last half
second against the 3 Nm peak.

--check runs the same limits without a window: stand, half and full speed each
way, half and fastest turn on the spot, an arc, and -- for a jump policy --
jumps from the lowest target to the highest, standing and at speed. For each
it reports what was held against what was asked, the motors' peaks, and
whether the robot stayed up.

KEYBOARD, with the viewer focused:

    up / down          forward speed, a tenth of the trained range a press
    left / right       turn rate, a tenth of the trained range a press
    page up / down     ride height, 5 mm a press
    enter              stop: speed and turn to zero
    insert             jump (jump policies), at the clearance below
    - / =              jump clearance, 5 mm a press
    delete             put the robot back on its wheels

GAME CONTROLLER (an Xbox layout; anything SDL recognises):

    left stick         forward speed
    right stick        turn rate
    d-pad up / down    ride height
    A                  jump; how hard the right trigger is held sets the
                       clearance, from the smallest trained to the largest
    B                  put the robot back on its wheels

WHAT THIS IS WORTH. MuJoCo is not PhysX: its contact is soft where PhysX's is
rigid, and its friction is a different model. A policy that only works in the
simulator it was trained in has learned that simulator, and would not work on
the robot either -- so a policy that drives here as it did in training has
passed a test that matters, and one that does not has found a problem cheaply.
It is not evidence about the real robot, whose unmeasured numbers are the
same guesses here as there.
"""

from __future__ import annotations

import argparse
import math
import sys
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np
import onnxruntime as ort
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
URDF_PATH = HERE.parent / "urdf" / "wheeled_biped.urdf"
DEFAULT_RUN = ROOT / "exports" / "rl" / "jump-2026-09-25_01-32-22_ramp"

# The order the policy sees and commands the joints in: plant.LEG_JOINTS and
# plant.WHEEL_JOINTS. Not imported, because plant.py reads the CAD, and this
# needs nothing from it.
LEG_JOINTS = ("hip_pitch_right", "knee_right", "hip_pitch_left", "knee_left")
WHEEL_JOINTS = ("wheel_drive_right", "wheel_drive_left")

# Isaac Lab's ground is rigid with a friction of 2.0, combined with the wheel's
# by taking the smaller, so the wheel's own figure is what grips. MuJoCo takes
# the larger of the two, so the floor here is given the wheel's figure.
FLOOR_FRICTION = 0.9

# How long a fallen robot lies there before it is put back.
FALLEN_RESET_S = 1.5

# Observation scales, from wheeled_biped_task/env.py and jump_env.py. These
# are the task's code rather than its configuration, so they are not in
# env.yaml.
ANG_VEL_SCALE = 0.25
JOINT_VEL_SCALE = 0.05
CLEARANCE_SCALE = 10.0
TIMER_CLIP_S = 2.0

# The rough ground at its hardest level, from the rough task's terrain
# generator in env.yaml. Not read from it, because the flat and jump tasks'
# runs do not have one and should still be drivable over it.
TERRAIN_TILE_M = 4.0
TERRAIN_TILES = 5  # a side: 20 m of ground, the start in the middle tile
TERRAIN_GRID_M = 0.05  # horizontal_scale
TERRAIN_STEP_M = 0.0025  # vertical_scale
TERRAIN_PLATFORM_M = 1.0
TERRAIN_HARDEST = dict(bump=0.015, wave=0.03, block=0.015, rail=0.015, slope=0.25)


# --------------------------------------------------------------------------
# The training configuration


class _Loader(yaml.SafeLoader):
    """env.yaml as Isaac Lab writes it: tuples tagged, and the odd object."""


_Loader.add_constructor(
    "tag:yaml.org,2002:python/tuple",
    lambda loader, node: tuple(loader.construct_sequence(node)),
)
_Loader.add_multi_constructor("tag:yaml.org,2002:python/", lambda *_: None)


def load_run(run: Path) -> tuple[dict, Path]:
    cfg = yaml.load((run / "params" / "env.yaml").read_text(), Loader=_Loader)
    policy = run / "exported" / "policy.onnx"
    if not policy.exists():
        sys.exit(f"{policy} does not exist: export the policy with train.sh --play")
    return cfg, policy


# --------------------------------------------------------------------------
# The robot


def urdf_visuals(urdf: Path):
    """Each link's visual shapes and colours, which MuJoCo's URDF import drops."""
    root = ET.parse(urdf).getroot()
    colours = {
        m.get("name"): [float(v) for v in m.find("color").get("rgba").split()]
        for m in root.iter("material")
        if m.find("color") is not None
    }
    for link in root.iter("link"):
        for visual in link.iter("visual"):
            origin = visual.find("origin")
            xyz = [float(v) for v in origin.get("xyz", "0 0 0").split()]
            rpy = [float(v) for v in origin.get("rpy", "0 0 0").split()]
            material = visual.find("material")
            rgba = colours.get(material.get("name"), [0.7, 0.7, 0.7, 1.0])
            yield link.get("name"), xyz, rpy, visual.find("geometry")[0], rgba


def rough_ground(level: float, seed: int = 0) -> np.ndarray:
    """Heights on a 5 cm grid, rows along y: tiles of the trained kinds.

    Each tile rises from zero at its edges, so neighbours meet with no more
    than a bump's step between them, and the middle one is left flat to start
    on.
    """
    rng = np.random.default_rng(seed)
    hard = {k: v * level for k, v in TERRAIN_HARDEST.items()}
    n = round(TERRAIN_TILE_M / TERRAIN_GRID_M)
    xy = (np.arange(n) + 0.5) * TERRAIN_GRID_M - TERRAIN_TILE_M / 2
    x, y = np.meshgrid(xy, xy)
    ring = np.maximum(abs(x), abs(y))  # distance out from the tile's middle
    platform = ring < TERRAIN_PLATFORM_M / 2

    def bumps():
        return rng.uniform(0, hard["bump"], (n, n))

    def waves():
        k = 2 * np.pi * 3 / TERRAIN_TILE_M  # num_waves
        return hard["wave"] / 2 * (np.sin(k * x) + np.sin(k * y))

    def blocks():
        h = np.zeros((n, n))
        for _ in range(30):
            w, d = rng.uniform(0.05, 0.4, 2)
            cx, cy = rng.uniform(-TERRAIN_TILE_M / 2, TERRAIN_TILE_M / 2, 2)
            h[(abs(x - cx) < w / 2) & (abs(y - cy) < d / 2)] = hard["block"]
        h[platform] = 0
        return h

    def rails():
        h = np.zeros((n, n))
        for r in (0.75, 1.25, 1.75):
            h[abs(ring - r) < rng.uniform(0.03, 0.08) / 2] = hard["rail"]
        return h

    def slope(sign):
        top = hard["slope"] * (TERRAIN_TILE_M - TERRAIN_PLATFORM_M) / 2
        return sign * np.clip(
            top - hard["slope"] * (ring - TERRAIN_PLATFORM_M / 2), 0, top
        )

    kinds = [bumps, waves, blocks, rails, lambda: slope(1), lambda: slope(-1)]
    rows = []
    for i in range(TERRAIN_TILES):
        row = []
        for j in range(TERRAIN_TILES):
            middle = i == j == TERRAIN_TILES // 2
            row.append(
                np.zeros((n, n)) if middle else kinds[rng.integers(len(kinds))]()
            )
        rows.append(np.hstack(row))
    h = np.vstack(rows)
    return np.round(h / TERRAIN_STEP_M) * TERRAIN_STEP_M


def build_model(cfg: dict, rough: float = 0.0) -> mujoco.MjModel:
    spec = mujoco.MjSpec.from_file(str(URDF_PATH))
    spec.option.timestep = cfg["sim"]["dt"]
    spec.option.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    spec.option.cone = mujoco.mjtCone.mjCONE_ELLIPTIC
    spec.compiler.degree = False
    # A URDF import defaults to discarding every shape that does not collide,
    # which is every visual one added below.
    spec.compiler.discardvisual = False

    base = spec.body("base_link")
    base.add_freejoint(name="root")

    # What the URDF imported is the collision shapes. Hide them (group 3) and
    # draw the visual meshes over them, which do not collide.
    for geom in spec.geoms:
        geom.group = 3
        geom.friction[0] = FLOOR_FRICTION
    meshes = {}
    for link, xyz, rpy, shape, rgba in urdf_visuals(URDF_PATH):
        body = spec.body(link)
        kw = dict(
            pos=xyz,
            quat=_quat_from_rpy(rpy),
            rgba=rgba,
            contype=0,
            conaffinity=0,
            group=0,
            mass=0.0,
            density=0.0,
        )
        if shape.tag == "mesh":
            file = URDF_PATH.parent / shape.get("filename")
            if file.name not in meshes:
                scale = [float(v) for v in shape.get("scale", "1 1 1").split()]
                spec.add_mesh(name=file.stem, file=str(file), scale=scale)
                meshes[file.name] = file.stem
            body.add_geom(
                type=mujoco.mjtGeom.mjGEOM_MESH, meshname=meshes[file.name], **kw
            )
        elif shape.tag == "cylinder":
            size = [float(shape.get("radius")), float(shape.get("length")) / 2, 0]
            body.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=size, **kw)
        elif shape.tag == "box":
            half = [float(v) / 2 for v in shape.get("size").split()]
            body.add_geom(type=mujoco.mjtGeom.mjGEOM_BOX, size=half, **kw)

    # The motors. Every one is a bare torque source: the PD and the
    # torque-speed line are computed below, as Isaac Lab's DCMotor does.
    actuators = cfg["robot"]["actuators"]
    for name in LEG_JOINTS + WHEEL_JOINTS:
        group = actuators["wheels" if name in WHEEL_JOINTS else "legs"]
        joint = spec.joint(name)
        joint.armature = group["armature"]
        joint.frictionloss = group["friction"]
        spec.add_actuator(
            name=name,
            target=name,
            trntype=mujoco.mjtTrn.mjTRN_JOINT,
            ctrllimited=False,
        )

    # The world: a floor, a light, a sky.
    spec.add_texture(
        name="grid",
        type=mujoco.mjtTexture.mjTEXTURE_2D,
        builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER,
        rgb1=[0.32, 0.36, 0.40],
        rgb2=[0.26, 0.29, 0.32],
        width=512,
        height=512,
    )
    spec.add_material(name="grid", texrepeat=[2, 2], texuniform=True).textures[
        mujoco.mjtTextureRole.mjTEXROLE_RGB
    ] = "grid"
    spec.add_texture(
        name="sky",
        type=mujoco.mjtTexture.mjTEXTURE_SKYBOX,
        builtin=mujoco.mjtBuiltin.mjBUILTIN_GRADIENT,
        rgb1=[0.55, 0.65, 0.75],
        rgb2=[0.1, 0.12, 0.15],
        width=256,
        height=256,
    )
    friction = [FLOOR_FRICTION, 0.005, 0.0001]
    if rough > 0:
        h = rough_ground(rough)
        lo, span = h.min(), max(np.ptp(h), 1e-4)
        half = h.shape[0] * TERRAIN_GRID_M / 2
        spec.add_hfield(
            name="rough",
            size=[half, half, span, 0.1],
            nrow=h.shape[0],
            ncol=h.shape[1],
            userdata=((h - lo) / span).ravel().tolist(),
        )
        spec.worldbody.add_geom(
            name="floor",
            type=mujoco.mjtGeom.mjGEOM_HFIELD,
            hfieldname="rough",
            pos=[0, 0, lo],
            material="grid",
            friction=friction,
        )
        # Flat ground all round it, level with the tiles' edges. Not a plane,
        # which would stand above the ground in a sunken tile.
        for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            spec.worldbody.add_geom(
                type=mujoco.mjtGeom.mjGEOM_BOX,
                size=[
                    50 if sy else (50 - half) / 2,
                    50 if sx else (50 - half) / 2,
                    0.05,
                ],
                pos=[sx * (50 + half) / 2, sy * (50 + half) / 2, -0.05],
                material="grid",
                friction=friction,
            )
    else:
        spec.worldbody.add_geom(
            name="floor",
            type=mujoco.mjtGeom.mjGEOM_PLANE,
            # Drawn without end, as it collides: at 1.9 m/s a finite floor
            # runs out.
            size=[0, 0, 0.1],
            material="grid",
            friction=friction,
        )
    spec.worldbody.add_light(
        pos=[0, 0, 3],
        dir=[0, 0, -1],
        type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL,
        castshadow=True,
    )
    # The viewer's near clip is a fraction of the model's extent, which the
    # rough ground's 100 m surround would make 17 m: a 1.7 m near clip, with
    # the camera 1.2 m from the robot. Held at what the flat floor gives.
    spec.stat.extent = 10.0
    spec.visual.global_.offwidth = 1280
    spec.visual.global_.offheight = 720
    return spec.compile()


def _quat_from_rpy(rpy) -> list[float]:
    q = np.zeros(4)
    mujoco.mju_euler2Quat(q, np.asarray(rpy, dtype=float), "XYZ")
    return q.tolist()


# --------------------------------------------------------------------------
# The robot's controller: the policy and the motor model around it


class Controller:
    def __init__(self, model: mujoco.MjModel, cfg: dict, policy: Path):
        self.m, self.cfg = model, cfg
        self.session = ort.InferenceSession(str(policy))
        self.n_obs = cfg["observation_space"]
        self.n_act = cfg["action_space"]
        self.jumps = self.n_act == 8
        self.decimation = cfg["decimation"]
        self.dt = cfg["sim"]["dt"] * self.decimation

        def addr(names, table):
            return np.array([table[model.joint(n).id] for n in names])

        self.leg_q = addr(LEG_JOINTS, model.jnt_qposadr)
        self.leg_v = addr(LEG_JOINTS, model.jnt_dofadr)
        self.wheel_v = addr(WHEEL_JOINTS, model.jnt_dofadr)
        self.leg_act = np.array([model.actuator(n).id for n in LEG_JOINTS])
        self.wheel_act = np.array([model.actuator(n).id for n in WHEEL_JOINTS])
        self.base = model.body("base_link").id
        self.wheels = [
            model.body(n.replace("wheel_drive", "wheel")).id for n in WHEEL_JOINTS
        ]
        wheel_geom = next(
            g
            for g in range(model.ngeom)
            if model.geom_bodyid[g] == self.wheels[0] and model.geom_contype[g]
        )
        self.wheel_radius = model.geom_size[wheel_geom][0]

        robot = cfg["robot"]
        pose = robot["init_state"]["joint_pos"]
        self.default_legs = np.array(
            [
                pose["hip_pitch_.*"] if "hip" in n else pose["knee_.*"]
                for n in LEG_JOINTS
            ]
        )
        self.spawn_z = robot["init_state"]["pos"][2]
        # Isaac Lab's soft limits: the travel shrunk about its middle.
        factor = robot["soft_joint_pos_limit_factor"]
        lo, hi = model.jnt_range[[model.joint(n).id for n in LEG_JOINTS]].T
        mid, half = (lo + hi) / 2, (hi - lo) / 2 * factor
        self.leg_lo, self.leg_hi = mid - half, mid + half

        legs, wheels = robot["actuators"]["legs"], robot["actuators"]["wheels"]
        self.kp0, self.kd0 = legs["stiffness"], legs["damping"]
        self.peak = legs["effort_limit"]
        self.saturation = legs["saturation_effort"]
        self.vmax = legs["velocity_limit"]
        assert wheels["stiffness"] == 0.0, "the wheels are torque-driven"
        self.leg_scale = np.asarray(cfg["leg_action_scale_rad"], dtype=float)
        self.wheel_scale = cfg["wheel_action_scale_nm"]

        self.command = np.array([0.0, 0.0, cfg["default_leg_height_m"]])
        self.height_range = cfg["command_leg_height_m"]
        self.speed_range = cfg["command_lin_vel_x"]
        self.yaw_range = cfg["command_yaw_rate"]
        # Trained on speed and turn sharing the wheels (jump_env_cfg.py).
        self.envelope = bool(cfg.get("command_envelope", False))
        if self.jumps:
            self.clearance_range = cfg["jump_clearance_m"]
            self.clearance = sum(self.clearance_range) / 2
        self.reset_state()

    def reset_state(self):
        self.actions = np.zeros(self.n_act)
        self.leg_targets = self.default_legs.copy()
        self.wheel_torque = np.zeros(2)
        self.kp = np.full(4, self.kp0)
        self.kd = np.full(4, self.kd0)
        self.jump_active = False
        self.jump_t = 0.0
        self.jump_target = 0.0
        self.took_off = False
        self.peak_clearance = 0.0
        self.last_peak = None
        self.touch_t = [-1.0, -1.0]
        self.landed_t = -1.0
        # The motors against their limits: peak |torque| per joint and peak
        # |wheel speed|, since the last read_peaks().
        self.torque_peak = np.zeros(6)
        self.wheel_speed_peak = 0.0

    def read_peaks(self) -> tuple[np.ndarray, float]:
        peaks = self.torque_peak, self.wheel_speed_peak
        self.torque_peak, self.wheel_speed_peak = np.zeros(6), 0.0
        return peaks

    def limit_command(self):
        """Into the trained ranges, and for an envelope-trained policy into
        the diamond the wheels' speed allows, keeping the command's direction."""
        cmd = self.command
        cmd[0] = np.clip(cmd[0], *self.speed_range)
        cmd[1] = np.clip(cmd[1], *self.yaw_range)
        cmd[2] = np.clip(cmd[2], *self.height_range)
        if self.envelope:
            share = abs(cmd[0]) / self.speed_range[1] + abs(cmd[1]) / self.yaw_range[1]
            if share > 1.0:
                cmd[:2] /= share

    def place(self, d: mujoco.MjData):
        """On its wheels at the origin, in the crouch it was trained from."""
        mujoco.mj_resetData(self.m, d)
        d.qpos[2] = self.spawn_z
        d.qpos[3:7] = [1, 0, 0, 0]
        d.qpos[self.leg_q] = self.default_legs
        mujoco.mj_forward(self.m, d)
        self.reset_state()

    # -- sensing

    def clearance_now(self, d) -> np.ndarray:
        return d.xpos[self.wheels, 2] - self.wheel_radius

    def observe(self, d) -> np.ndarray:
        rot = d.xmat[self.base].reshape(3, 3)
        gravity_b = rot.T @ np.array([0.0, 0.0, -1.0])
        # A free joint's angular velocity is in the body's own frame already.
        obs = [
            d.qvel[3:6] * ANG_VEL_SCALE,
            gravity_b,
            self.command,
            d.qpos[self.leg_q] - self.default_legs,
            d.qvel[self.leg_v] * JOINT_VEL_SCALE,
            d.qvel[self.wheel_v] * JOINT_VEL_SCALE,
            self.actions[:6],
        ]
        if self.jumps:
            a = float(self.jump_active)
            obs.append(
                [
                    a,
                    self.jump_target * CLEARANCE_SCALE * a,
                    min(self.jump_t, TIMER_CLIP_S) * a,
                ]
            )
        obs = np.concatenate(obs).astype(np.float32)
        assert obs.shape == (self.n_obs,), obs.shape
        return obs

    def tilt(self, d) -> float:
        return math.acos(np.clip(d.xmat[self.base][8], -1.0, 1.0))

    # -- acting

    def act(self, d):
        """One policy step: read the robot, run the policy, set the targets."""
        self.update_jump(d)
        raw = self.session.run(None, {"obs": self.observe(d)[None]})[0][0]
        self.actions = np.clip(raw, -1.0, 1.0)
        self.leg_targets = np.clip(
            self.default_legs + self.leg_scale * self.actions[:4],
            self.leg_lo,
            self.leg_hi,
        )
        self.wheel_torque = self.wheel_scale * self.actions[4:6]
        if self.jumps:
            span = self.cfg["leg_gain_range"]
            self.kp = np.full(4, self.kp0 * span ** self.actions[6])
            self.kd = np.full(4, self.kd0 * span ** self.actions[7])
            if self.jump_active:
                self.jump_t += self.dt

    def motor_torques(self, d):
        """Isaac Lab's DCMotor, every physics step: PD, then the torque-speed line."""
        q, v = d.qpos[self.leg_q], d.qvel[self.leg_v]
        legs = self.kp * (self.leg_targets - q) - self.kd * v
        d.ctrl[self.leg_act] = self._saturate(legs, v)
        wheel_v = d.qvel[self.wheel_v]
        d.ctrl[self.wheel_act] = self._saturate(self.wheel_torque, wheel_v)
        tau = np.abs(np.concatenate((d.ctrl[self.leg_act], d.ctrl[self.wheel_act])))
        self.torque_peak = np.maximum(self.torque_peak, tau)
        self.wheel_speed_peak = max(self.wheel_speed_peak, np.abs(wheel_v).max())

    def _saturate(self, tau, v):
        hi = np.clip(self.saturation * (1.0 - v / self.vmax), 0.0, self.peak)
        lo = np.clip(self.saturation * (-1.0 - v / self.vmax), -self.peak, 0.0)
        return np.clip(tau, lo, hi)

    # -- the jump, as wheeled_biped_task/jump_env.py runs it

    def trigger_jump(self, clearance: float):
        if self.jumps and not self.jump_active:
            self.jump_active, self.jump_t = True, 0.0
            self.jump_target = float(np.clip(clearance, *self.clearance_range))
            self.took_off, self.peak_clearance = False, 0.0
            self.touch_t, self.landed_t = [-1.0, -1.0], -1.0

    def update_jump(self, d):
        if not self.jump_active:
            return
        c = self.cfg
        clear = self.clearance_now(d)
        on_ground = clear < c["wheel_contact_tolerance_m"]
        if not on_ground.any():
            self.took_off = True
            self.peak_clearance = max(self.peak_clearance, clear.min())
        if self.took_off:
            for i in range(2):
                if on_ground[i] and self.touch_t[i] < 0:
                    self.touch_t[i] = self.jump_t
            if min(self.touch_t) >= 0 and self.landed_t < 0:
                self.landed_t = self.jump_t
                self.last_peak = self.peak_clearance
        missed = not self.took_off and self.jump_t > c["jump_takeoff_window_s"]
        recovered = (
            self.landed_t >= 0 and self.jump_t > self.landed_t + c["jump_recovery_s"]
        )
        if missed:
            self.last_peak = 0.0
        if missed or recovered:
            self.jump_active = False


# --------------------------------------------------------------------------
# Input


class Input:
    """Keyboard through the viewer, and a game controller if one is plugged in."""

    KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT = 265, 264, 263, 262
    KEY_PAGE_UP, KEY_PAGE_DOWN, KEY_ENTER = 266, 267, 257
    KEY_INSERT, KEY_DELETE, KEY_MINUS, KEY_EQUAL = 260, 261, 45, 61

    def __init__(self, ctl: Controller):
        self.ctl = ctl
        self.lock = threading.Lock()
        self.reset = False
        self.pad = None
        try:
            import os

            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            import pygame

            pygame.init()
            pygame.joystick.init()
            if pygame.joystick.get_count():
                self.pad = pygame.joystick.Joystick(0)
                self.pad.init()
                self.pygame = pygame
                print(f"controller: {self.pad.get_name()}")
        except Exception as error:  # a missing controller is not an error
            print(f"no controller ({error})")
        self.jump_button_was = False

    def key(self, code: int):
        c = self.ctl
        speed_step = c.speed_range[1] / 10
        turn_step = c.yaw_range[1] / 10
        with self.lock:
            cmd = c.command
            if code == self.KEY_UP:
                cmd[0] += speed_step
            elif code == self.KEY_DOWN:
                cmd[0] -= speed_step
            elif code == self.KEY_LEFT:
                cmd[1] += turn_step
            elif code == self.KEY_RIGHT:
                cmd[1] -= turn_step
            elif code == self.KEY_PAGE_UP:
                cmd[2] += 0.005
            elif code == self.KEY_PAGE_DOWN:
                cmd[2] -= 0.005
            elif code == self.KEY_ENTER:
                cmd[:2] = 0.0
            elif code == self.KEY_DELETE:
                self.reset = True
            elif c.jumps and code == self.KEY_EQUAL:
                c.clearance = min(c.clearance + 0.005, c.clearance_range[1])
            elif c.jumps and code == self.KEY_MINUS:
                c.clearance = max(c.clearance - 0.005, c.clearance_range[0])
            elif code == self.KEY_INSERT:
                c.trigger_jump(c.clearance)
            c.limit_command()

    def poll_pad(self):
        if self.pad is None:
            return
        pg = self.pygame
        pg.event.pump()
        c = self.ctl

        def axis(i, dead=0.12):
            x = self.pad.get_axis(i) if i < self.pad.get_numaxes() else 0.0
            return 0.0 if abs(x) < dead else (x - math.copysign(dead, x)) / (1 - dead)

        with self.lock:
            c.command[0] = -axis(1) * c.speed_range[1]
            c.command[1] = -axis(2) * c.yaw_range[1]
            if self.pad.get_numhats():
                c.command[2] += 0.0005 * self.pad.get_hat(0)[1]
            if self.pad.get_button(1):
                self.reset = True
            pressed = self.pad.get_button(0)
            if c.jumps and pressed and not self.jump_button_was:
                # The trigger rests at -1 and is fully pulled at +1.
                pull = (axis(5, 0.0) + 1) / 2 if self.pad.get_numaxes() > 5 else 0.5
                lo, hi = c.clearance_range
                c.clearance = lo + pull * (hi - lo)
                c.trigger_jump(c.clearance)
            self.jump_button_was = pressed
            c.limit_command()


# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument(
        "--check",
        action="store_true",
        help="no window: run the robot to its limits, and report",
    )
    parser.add_argument(
        "--rough",
        type=float,
        default=0.0,
        metavar="LEVEL",
        help="rough ground: 1 is the hardest trained, 0 (the default) flat",
    )
    args = parser.parse_args()

    cfg, policy = load_run(args.run)
    model = build_model(cfg, args.rough)
    data = mujoco.MjData(model)
    ctl = Controller(model, cfg, policy)
    ctl.place(data)
    print(
        f"{args.run.name}: {ctl.n_obs} inputs, {ctl.n_act} outputs,"
        f" {1 / ctl.dt:.0f} Hz policy, {1 / model.opt.timestep:.0f} Hz physics"
        + (", jumps" if ctl.jumps else "")
    )

    if args.check:
        return check(model, data, ctl)

    inp = Input(ctl)
    print(
        "keys: arrows speed and turn, page up/down ride height, enter stop,"
        " delete reset"
        + (", insert jump, -/= jump clearance" if ctl.jumps else "")
        + ("" if inp.pad else "  (no controller found: keyboard only)")
    )
    fallen_since = None
    with mujoco.viewer.launch_passive(model, data, key_callback=inp.key) as viewer:
        viewer.cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
        viewer.cam.trackbodyid = ctl.base
        viewer.cam.distance, viewer.cam.elevation, viewer.cam.azimuth = 1.2, -15, 135
        next_tick = time.perf_counter()
        steps, peaks = 0, (np.zeros(6), 0.0)
        while viewer.is_running():
            inp.poll_pad()
            with inp.lock:
                if inp.reset:
                    ctl.place(data)
                    inp.reset, fallen_since = False, None
                ctl.act(data)
            for _ in range(ctl.decimation):
                ctl.motor_torques(data)
                mujoco.mj_step(model, data)

            if ctl.tilt(data) > cfg["max_tilt_rad"]:
                fallen_since = fallen_since or time.perf_counter()
                if time.perf_counter() - fallen_since > FALLEN_RESET_S:
                    ctl.place(data)
                    fallen_since = None
            else:
                fallen_since = None

            # The motors' peaks over each half second.
            steps += 1
            if steps % round(0.5 / ctl.dt) == 0:
                peaks = ctl.read_peaks()
            show_status(viewer, data, ctl, peaks)
            viewer.sync()
            next_tick += ctl.dt
            lag = next_tick - time.perf_counter()
            if lag > 0:
                time.sleep(lag)
            elif lag < -0.1:  # fell behind (a window drag): do not try to catch up
                next_tick = time.perf_counter()
    return 0


def show_status(viewer, d, ctl: Controller, peaks):
    speed = (d.xmat[ctl.base].reshape(3, 3).T @ d.qvel[:3])[0]
    torque, wheel_speed = peaks
    lines = [
        ("speed", f"{ctl.command[0]:+.2f} m/s  (doing {speed:+.2f})"),
        ("turn", f"{ctl.command[1]:+.2f} rad/s  (doing {d.qvel[5]:+.2f})"),
        ("ride height", f"{ctl.command[2] * 1000:.0f} mm"),
        (
            "wheel speed",
            f"{wheel_speed:.0f} of {ctl.vmax:.0f} rad/s"
            f" ({wheel_speed / ctl.vmax * 100:.0f}% of no-load)",
        ),
        (
            "peak torque",
            f"hip {torque[[0, 2]].max():.1f}, knee {torque[[1, 3]].max():.1f},"
            f" wheel {torque[4:].max():.1f} of {ctl.peak:.1f} Nm",
        ),
    ]
    if ctl.jumps:
        state = (
            "in the air"
            if ctl.jump_active and ctl.took_off
            else ("jumping" if ctl.jump_active else "ready")
        )
        last = "" if ctl.last_peak is None else f", last {ctl.last_peak * 1000:.0f} mm"
        lines.append(("jump", f"{ctl.clearance * 1000:.0f} mm, {state}{last}"))
    try:
        viewer.set_texts(
            (
                mujoco.mjtFontScale.mjFONTSCALE_150,
                mujoco.mjtGridPos.mjGRID_TOPLEFT,
                "\n".join(k for k, _ in lines),
                "\n".join(v for _, v in lines),
            )
        )
    except AttributeError:  # an older viewer without overlays
        pass


def check(model, data, ctl: Controller) -> int:
    """Headless: the robot run to the limits of what it was trained on."""
    v, w = ctl.speed_range[1], ctl.yaw_range[1]
    # (name, seconds, forward, turn, jump clearance or None)
    script = [
        ("stand", 2.0, 0.0, 0.0, None),
        ("forward, half", 3.0, v / 2, 0.0, None),
        ("forward, top", 4.0, v, 0.0, None),
        ("back, top", 5.0, -v, 0.0, None),
        ("stop", 2.0, 0.0, 0.0, None),
        ("spin, half", 3.0, 0.0, w / 2, None),
        ("spin, fastest", 4.0, 0.0, w, None),
        ("arc", 4.0, v / 2, w / 2, None),
        ("stop", 2.0, 0.0, 0.0, None),
    ]
    if ctl.jumps:
        lo, hi = ctl.clearance_range
        script += [
            (f"jump {c * 1000:.0f} mm", 2.5, 0.0, 0.0, c)
            for c in np.linspace(lo, hi, 4)
        ]
        script.append((f"jump {hi * 1000:.0f} mm at speed", 3.0, v / 2, 0.0, hi))

    print(
        f"  {'':<24} {'asked':>17} {'held, last second':>18}"
        f" {'wheel speed':>12}   peak torque hip / knee / wheel"
    )
    falls, t0, simulated = 0, time.perf_counter(), 0.0
    for name, seconds, speed, turn, jump in script:
        ctl.command[:2] = speed, turn
        ctl.limit_command()
        ctl.read_peaks()
        ctl.last_peak = None
        steps = round(seconds / ctl.dt)
        last = round(1.0 / ctl.dt)
        held = np.zeros(2)
        fell = False
        for k in range(steps):
            if jump is not None and k == round(0.5 / ctl.dt):
                ctl.trigger_jump(jump)
            ctl.act(data)
            for _ in range(ctl.decimation):
                ctl.motor_torques(data)
                mujoco.mj_step(model, data)
            if k >= steps - last:
                rot = data.xmat[ctl.base].reshape(3, 3)
                held += [(rot.T @ data.qvel[:3])[0] / last, data.qvel[5] / last]
            if ctl.tilt(data) > ctl.cfg["max_tilt_rad"]:
                fell = True
                break
        simulated += seconds
        torque, wheel_speed = ctl.read_peaks()
        asked = f"{ctl.command[0]:+5.2f} m/s {ctl.command[1]:+5.1f} r/s"
        if fell:
            outcome = "FELL"
            falls += 1
            ctl.place(data)
        else:
            outcome = f"{held[0]:+5.2f} m/s {held[1]:+5.1f} r/s"
        cleared = ""
        if jump is not None:
            got = ctl.last_peak
            cleared = "  no take-off" if not got else f"  cleared {got * 1000:.0f} mm"
        print(
            f"  {name:<24} {asked:>17} {outcome:>18}"
            f" {wheel_speed / ctl.vmax * 100:9.0f} %"
            f"   {torque[[0, 2]].max():4.1f} / {torque[[1, 3]].max():4.1f}"
            f" / {torque[4:].max():4.1f} Nm{cleared}"
        )
    print(
        f"{falls} falls. Wheel speed is against the {ctl.vmax:.1f} rad/s no-load"
        f" speed, torque against the {ctl.peak:.1f} Nm peak."
        f" {simulated / (time.perf_counter() - t0):.0f}x real time."
    )
    return 1 if falls else 0


if __name__ == "__main__":
    raise SystemExit(main())
