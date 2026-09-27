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
    uv run simulation/mujoco/drive.py --delay-ms 5,2.5,2.5 --battery 0.8

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
the fastest turn, and every jump is as high as it was trained to. Speed and
turn share the wheels, so for a policy trained that way a command asking for
more of both than the wheels have is scaled back into the envelope, as it was
in training. The overlay shows how close the motors are to their own limits:
wheel speed against the no-load speed, and the peak torque of the last half
second against the 3 Nm peak.

--check runs the same limits without a window: stand, half and full speed each
way, half and fastest turn on the spot, an arc, and -- for a jump policy --
a jump, standing and at speed. For each it reports what was held against
what was asked, the motors' peaks, and whether the robot stayed up.

KEYBOARD, with the viewer focused:

    up / down          forward speed, a tenth of the trained range a press
    left / right       turn rate, a tenth of the trained range a press
    page up / down     ride height, 5 mm a press
    enter              stop: speed and turn to zero
    shift or insert    jump (jump policies)
    delete             put the robot back on its wheels

GAME CONTROLLER (an Xbox layout; anything SDL recognises):

    left stick         forward speed
    right stick        turn rate
    d-pad up / down    ride height
    A                  jump
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
DEFAULT_RUN = ROOT / "exports" / "rl" / "jump-2026-09-26_20-38-29_heightstepsfast"

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
BATTERY_SCALE = 5.0  # the pack's voltage: (V / 24 - 1) x 5

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


# A pyramid of steps to drive down (--steps), on the treads the jump task's
# step tiles use: a 1 m platform at the top and 0.6 m treads falling away.
STEPS_COUNT = 4
STEPS_TREAD_M = 0.6
STEPS_PLATFORM_M = 1.0


def build_model(cfg: dict, rough: float = 0.0, steps: float = 0.0) -> mujoco.MjModel:
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
        # A hard stop, as PhysX's is. MuJoCo's default limit is a spring with a
        # 20 ms time constant, and a jump that folded the knee fast drove it to
        # 114 degrees against a 100 degree stop -- 14 degrees of travel the
        # joint does not have, and wheel clearance that came with it.
        joint.solref_limit = [2.0 * spec.option.timestep, 1.0]
        joint.solimp_limit = [0.99, 0.999, 0.001, 0.5, 2.0]
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
    for i in range(1, STEPS_COUNT + 1) if steps > 0 else ():
        # Nested boxes, the lowest and widest first; the robot starts on top.
        half = STEPS_PLATFORM_M / 2 + (STEPS_COUNT - i) * STEPS_TREAD_M
        spec.worldbody.add_geom(
            type=mujoco.mjtGeom.mjGEOM_BOX,
            size=[half, half, i * steps / 2],
            pos=[0, 0, i * steps / 2],
            rgba=[0.45, 0.48, 0.52, 1] if i % 2 else [0.38, 0.41, 0.45, 1],
            friction=friction,
        )
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
        self.vmax_rated = legs["velocity_limit"]
        self.vmax = self.vmax_rated
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
            # No height to choose: a policy scored on its highest jump sees
            # one fixed target, and an older one trained to targets is asked
            # for the highest of them.
            self.clearance = cfg["jump_clearance_m"][1]
        # The robot's delays, in physics steps: the IMU's reading, the
        # encoders', and a command's taking effect (set_conditions).
        self.delay = (0, 0, 0)
        # The ground's height where the robot is placed (the top of --steps).
        self.floor_z = 0.0
        self.battery = 1.0
        # Told the pack's voltage, as the last input (jump_env_cfg.py).
        self.observes_battery = bool(cfg.get("observe_battery", False))
        self.reset_state()

    def set_conditions(self, delay_ms=(0.0, 0.0, 0.0), battery: float = 1.0):
        """The robot's delays, IMU, encoders and command, and its battery.

        A delay is rounded to whole physics steps, up to one policy step. The
        battery is the motors' no-load speed as a share of the rated one.
        """
        step_ms = self.m.opt.timestep * 1000.0
        self.delay = tuple(
            int(np.clip(round(ms / step_ms), 0, self.decimation)) for ms in delay_ms
        )
        self.vmax = self.vmax_rated * battery
        self.battery = battery

    def reset_state(self):
        self.actions = np.zeros(self.n_act)
        self.leg_targets = self.default_legs.copy()
        self.wheel_torque = np.zeros(2)
        self.kp = np.full(4, self.kp0)
        self.kd = np.full(4, self.kd0)
        self.held = (self.leg_targets, self.wheel_torque, self.kp, self.kd)
        # What the sensors read after each physics step of the last policy
        # step, by how many steps old; empty until the first look.
        self.history = None
        self.substep = 0
        self.jump_active = False
        self.jump_t = 0.0
        self.jump_target = 0.0
        self.took_off = False
        self.peak_clearance = 0.0
        self.last_peak = None
        self.last_rise = self.last_air = 0.0
        self.last_pitch = self.last_skew = 0.0
        self.pitch_peak, self.lift_t = 0.0, [-1.0, -1.0]
        self.start_z = self.apex_z = self.air_t = 0.0
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
        d.qpos[2] = self.spawn_z + self.floor_z
        d.qpos[3:7] = [1, 0, 0, 0]
        d.qpos[self.leg_q] = self.default_legs
        mujoco.mj_forward(self.m, d)
        self.reset_state()

    # -- sensing

    def clearance_now(self, d) -> np.ndarray:
        return d.xpos[self.wheels, 2] - self.wheel_radius

    def reading(self, d) -> np.ndarray:
        """What the robot's own sensors read now, scaled as the policy sees it:
        the IMU's turn rate and gravity direction, then the encoders."""
        rot = d.xmat[self.base].reshape(3, 3)
        gravity_b = rot.T @ np.array([0.0, 0.0, -1.0])
        # A free joint's angular velocity is in the body's own frame already.
        return np.concatenate(
            (
                d.qvel[3:6] * ANG_VEL_SCALE,
                gravity_b,
                d.qpos[self.leg_q] - self.default_legs,
                d.qvel[self.leg_v] * JOINT_VEL_SCALE,
                d.qvel[self.wheel_v] * JOINT_VEL_SCALE,
            )
        )

    def observe(self, d) -> np.ndarray:
        now = self.reading(d)
        if self.history is None:
            self.history = np.tile(now, (self.decimation + 1, 1))
        self.history[0] = now
        imu = self.history[self.delay[0], :6]
        encoders = self.history[self.delay[1], 6:]
        command = self.command.copy()
        if self.cfg.get("scale_height_command", False):
            # The ride height as -1 to 1 over its range (env.py).
            lo, hi = self.height_range
            command[2] = (command[2] - (lo + hi) / 2) / ((hi - lo) / 2)
        obs = [imu, command, encoders, self.actions[:6]]
        if self.jumps:
            a = float(self.jump_active)
            obs.append(
                [
                    a,
                    self.jump_target * CLEARANCE_SCALE * a,
                    min(self.jump_t, TIMER_CLIP_S) * a,
                ]
            )
        if self.observes_battery:
            obs.append([(self.battery - 1.0) * BATTERY_SCALE])
        obs = np.concatenate(obs).astype(np.float32)
        assert obs.shape == (self.n_obs,), obs.shape
        return obs

    def tilt(self, d) -> float:
        return math.acos(np.clip(d.xmat[self.base][8], -1.0, 1.0))

    # -- acting

    def act(self, d):
        """One policy step: read the robot, run the policy, set the targets."""
        self.update_jump(d)
        # What the motors run until this step's command reaches them.
        self.held = (self.leg_targets, self.wheel_torque, self.kp, self.kd)
        self.substep = 0
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
        if self.history is not None:
            self.history[self.decimation - self.substep] = self.reading(d)
        late = self.substep < self.delay[2]
        self.substep += 1
        targets, wheel_torque, kp, kd = (
            self.held
            if late
            else (self.leg_targets, self.wheel_torque, self.kp, self.kd)
        )
        q, v = d.qpos[self.leg_q], d.qvel[self.leg_v]
        legs = kp * (targets - q) - kd * v
        d.ctrl[self.leg_act] = self._saturate(legs, v)
        wheel_v = d.qvel[self.wheel_v]
        d.ctrl[self.wheel_act] = self._saturate(wheel_torque, wheel_v)
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
            self.jump_target = float(clearance)
            self.took_off, self.peak_clearance = False, 0.0
            self.touch_t, self.landed_t = [-1.0, -1.0], -1.0
            # How far the torso pitches, and when each wheel leaves the ground.
            self.pitch_peak, self.lift_t = 0.0, [-1.0, -1.0]

    def update_jump(self, d):
        if not self.jump_active:
            return
        c = self.cfg
        torso_z = d.xpos[self.base, 2]
        if self.jump_t == 0.0:
            # The torso's height at the trigger, to measure its rise from.
            self.start_z = self.apex_z = torso_z
            self.air_t = 0.0
        clear = self.clearance_now(d)
        on_ground = clear < c["wheel_contact_tolerance_m"]
        forward = d.xmat[self.base].reshape(3, 3)[:, 0]
        self.pitch_peak = max(self.pitch_peak, abs(math.asin(forward[2])))
        for i in range(2):
            if not on_ground[i] and self.lift_t[i] < 0:
                self.lift_t[i] = self.jump_t
        if not on_ground.any():
            self.took_off = True
            self.peak_clearance = max(self.peak_clearance, clear.min())
            self.apex_z = max(self.apex_z, torso_z)
            self.air_t += self.dt
        if self.took_off:
            for i in range(2):
                if on_ground[i] and self.touch_t[i] < 0:
                    self.touch_t[i] = self.jump_t
            if min(self.touch_t) >= 0 and self.landed_t < 0:
                self.landed_t = self.jump_t
                self.last_peak = self.peak_clearance
                self.last_rise = self.apex_z - self.start_z
                self.last_air = self.air_t
                self.last_pitch = self.pitch_peak
                self.last_skew = abs(self.lift_t[0] - self.lift_t[1])
        missed = not self.took_off and self.jump_t > c["jump_takeoff_window_s"]
        recovered = (
            self.landed_t >= 0 and self.jump_t > self.landed_t + c["jump_recovery_s"]
        )
        if c.get("jump_score_max", False):
            # Held to a fixed window after the trigger, as it was trained.
            recovered = self.jump_t >= c["jump_window_s"]
        if missed:
            self.last_peak = 0.0
            self.last_rise = self.last_air = 0.0
            self.last_pitch = self.last_skew = 0.0
        if missed or recovered:
            self.jump_active = False


# --------------------------------------------------------------------------
# Holding still: the loop outside the policy


class Hold:
    """Heading and place, held while the operator asks for no speed and no turn.

    The policy sees only its turn rate, so a slow steady turn and a small creep
    look to it like standing still, and it drifts: the jump policy turned 111
    degrees and crept 36 cm in 25 s. This holds what the robot's own sensors
    can -- the heading from the IMU's orientation, the distance rolled from the
    wheels -- and asks for the speed and turn that take it back. Sideways it
    cannot hold, having no way to move sideways.

    Most of the time it asks for exactly nothing, which is the command the
    policy is trained to stand still on: it steps in past an outer band and
    lets go inside an inner one.
    """

    HEADING_BAND_RAD = (math.radians(0.5), math.radians(2.0))
    PLACE_BAND_M = (0.005, 0.02)
    HEADING_GAIN = 4.0  # rad/s per rad
    # Gently: the policy's speed loop is slow, and at 3 m/s per metre the two
    # together rocked 5 degrees at 1.4 Hz.
    PLACE_GAIN = 1.0  # m/s per m
    MAX_TURN_RAD_S = 0.5
    MAX_SPEED_M_S = 0.2

    def __init__(self, ctl: Controller):
        self.ctl = ctl
        self.holding = False

    def ground_speed(self, d) -> float:
        """Forward speed from the wheels: each wheel's spin against the ground
        is its own joint's plus the leg's and the torso's pitching."""
        c = self.ctl
        pitch_rate = d.qvel[4]  # the free joint's angular velocity is body-frame
        hips, knees = d.qvel[c.leg_v[[0, 2]]], d.qvel[c.leg_v[[1, 3]]]
        spin = pitch_rate - hips + knees + d.qvel[c.wheel_v]
        return float(c.wheel_radius * spin.mean())

    @staticmethod
    def heading(d, base) -> float:
        rot = d.xmat[base].reshape(3, 3)
        return math.atan2(rot[1, 0], rot[0, 0])

    def command(self, d, asked: np.ndarray) -> np.ndarray:
        """The speed and turn to send: the operator's, or the hold's."""
        if asked.any():
            self.holding = False
            return asked
        c = self.ctl
        if not self.holding:
            self.holding = True
            self.target = self.heading(d, c.base)
            self.rolled = 0.0
            self.turning = self.moving = False
        self.rolled += self.ground_speed(d) * c.dt
        error = (self.target - self.heading(d, c.base) + math.pi) % (2 * math.pi)
        error -= math.pi
        lo, hi = self.HEADING_BAND_RAD
        self.turning = abs(error) > (lo if self.turning else hi)
        lo, hi = self.PLACE_BAND_M
        self.moving = abs(self.rolled) > (lo if self.moving else hi)
        turn = np.clip(
            self.HEADING_GAIN * error, -self.MAX_TURN_RAD_S, self.MAX_TURN_RAD_S
        )
        speed = np.clip(
            -self.PLACE_GAIN * self.rolled, -self.MAX_SPEED_M_S, self.MAX_SPEED_M_S
        )
        return np.array([speed * self.moving, turn * self.turning])


# --------------------------------------------------------------------------
# Input


class Input:
    """Keyboard through the viewer, and a game controller if one is plugged in."""

    KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT = 265, 264, 263, 262
    KEY_PAGE_UP, KEY_PAGE_DOWN, KEY_ENTER = 266, 267, 257
    KEY_INSERT, KEY_DELETE = 260, 261
    KEY_LEFT_SHIFT, KEY_RIGHT_SHIFT = 340, 344

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
            elif code in (self.KEY_LEFT_SHIFT, self.KEY_RIGHT_SHIFT, self.KEY_INSERT):
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
    parser.add_argument(
        "--delay-ms",
        default="0,0,0",
        metavar="IMU,ENCODERS,COMMAND",
        help="the robot's delays, rounded to physics steps; 5,2.5,2.5 is typical",
    )
    parser.add_argument(
        "--battery",
        type=float,
        default=1.0,
        metavar="SHARE",
        help="motor no-load speed as a share of rated: 1.05 full, 0.8 at cutoff",
    )
    parser.add_argument(
        "--no-hold",
        action="store_true",
        help="do not hold heading and place while no speed or turn is asked for",
    )
    parser.add_argument(
        "--steps",
        type=float,
        default=0.0,
        metavar="HEIGHT_M",
        help=f"start on a pyramid of {STEPS_COUNT} steps this high, to drive down",
    )
    args = parser.parse_args()

    cfg, policy = load_run(args.run)
    model = build_model(cfg, args.rough, args.steps)
    data = mujoco.MjData(model)
    ctl = Controller(model, cfg, policy)
    ctl.floor_z = STEPS_COUNT * args.steps
    delay_ms = [float(v) for v in args.delay_ms.split(",")]
    ctl.set_conditions(delay_ms, args.battery)
    ctl.place(data)
    print(
        f"{args.run.name}: {ctl.n_obs} inputs, {ctl.n_act} outputs,"
        f" {1 / ctl.dt:.0f} Hz policy, {1 / model.opt.timestep:.0f} Hz physics"
        + (", jumps" if ctl.jumps else "")
        + f"; delays {args.delay_ms} ms, battery {args.battery:.2f} of rated speed"
    )

    if args.check:
        return check(model, data, ctl)
    hold = None if args.no_hold else Hold(ctl)

    inp = Input(ctl)
    print(
        "keys: arrows speed and turn, page up/down ride height, enter stop,"
        " delete reset"
        + (", shift to jump" if ctl.jumps else "")
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
                    if hold is not None:
                        hold.holding = False
                asked = ctl.command[:2].copy()
                if hold is not None:
                    ctl.command[:2] = hold.command(data, asked)
                ctl.act(data)
                ctl.command[:2] = asked
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
            show_status(viewer, data, ctl, peaks, hold)
            viewer.sync()
            next_tick += ctl.dt
            lag = next_tick - time.perf_counter()
            if lag > 0:
                time.sleep(lag)
            elif lag < -0.1:  # fell behind (a window drag): do not try to catch up
                next_tick = time.perf_counter()
    return 0


def show_status(viewer, d, ctl: Controller, peaks, hold=None):
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
        last = (
            ""
            if ctl.last_peak is None
            else f", last {ctl.last_peak * 1000:.0f} mm (torso"
            f" +{ctl.last_rise * 1000:.0f} mm, {ctl.last_air:.2f} s up)"
        )
        lines.append(("jump", f"{state}{last}"))
    if hold is not None and hold.holding:
        drift = math.degrees(hold.target - Hold.heading(d, ctl.base))
        drift = (drift + 180.0) % 360.0 - 180.0
        lines.append(
            ("holding", f"heading {drift:+.1f} deg, place {hold.rolled * 1000:+.0f} mm")
        )
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
        script.append(("jump", 2.5, 0.0, 0.0, ctl.clearance))
        script.append(("jump at speed", 3.0, v / 2, 0.0, ctl.clearance))

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
            cleared = (
                "  no take-off"
                if not got
                else f"  cleared {got * 1000:.0f} mm, torso"
                f" +{ctl.last_rise * 1000:.0f} mm, {ctl.last_air:.2f} s up,"
                f" pitched {math.degrees(ctl.last_pitch):.0f} deg,"
                f" wheels off {ctl.last_skew * 1000:.0f} ms apart"
            )
        print(
            f"  {name:<24} {asked:>17} {outcome:>18}"
            f" {wheel_speed / ctl.vmax * 100:9.0f} %"
            f"   {torque[[0, 2]].max():4.1f} / {torque[[1, 3]].max():4.1f}"
            f" / {torque[4:].max():4.1f} Nm{cleared}"
        )
    # Standing, first on the policy alone and then with the hold around it.
    for held in (False, True):
        hold = Hold(ctl) if held else None
        ctl.command[:2] = 0.0
        start = data.xpos[ctl.base, :2].copy()
        heading = Hold.heading(data, ctl.base)
        for _ in range(round(20.0 / ctl.dt)):
            if hold is not None:
                ctl.command[:2] = hold.command(data, np.zeros(2))
            ctl.act(data)
            for _ in range(ctl.decimation):
                ctl.motor_torques(data)
                mujoco.mj_step(model, data)
        simulated += 20.0
        turned = math.degrees(Hold.heading(data, ctl.base) - heading)
        turned = (turned + 180.0) % 360.0 - 180.0
        moved = np.linalg.norm(data.xpos[ctl.base, :2] - start)
        name = "stand 20 s, " + ("holding" if held else "policy alone")
        print(f"  {name:<24} moved {moved * 1000:4.0f} mm, turned {turned:+6.1f} deg")
    print(
        f"{falls} falls. Wheel speed is against the {ctl.vmax:.1f} rad/s no-load"
        f" speed, torque against the {ctl.peak:.1f} Nm peak."
        f" {simulated / (time.perf_counter() - t0):.0f}x real time."
    )
    return 1 if falls else 0


if __name__ == "__main__":
    raise SystemExit(main())
