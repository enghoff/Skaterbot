"""The simulator-facing choices, in one place and framework-independent.

The URDF says what the mechanism IS: links, masses, inertia tensors, joint
axes, travel. None of that is a choice, and none of it belongs here. This
module holds the things that ARE choices -- how hard the actuator may push,
what the wheels grip, how finely the solver integrates, where the robot starts
-- so that the Isaac Sim scripts and the Isaac Lab config cannot drift apart by
being edited separately.

Nothing in here is typed in twice either. The actuator numbers come from
robot.py, which is where this project already keeps them; the geometry comes
from the CAD by way of cad/dimensions.py, so a change to the CAD moves it. What is
genuinely new -- contact, solver settings, randomisation ranges -- is written
once, below, with its provenance.

IT IMPORTS NOTHING BUT THE STANDARD LIBRARY. That is deliberate: Isaac Sim
ships its own Python, and this module has to be importable inside it without
installing anything. numpy, trimesh and the rest stay on the build side.

READ THE UNMEASURED MARKERS. Three numbers here decide whether a policy trained
against this plant has any chance of transferring, and all three are currently
guesses: the actuator's reflected rotor inertia, its torque-speed curve below
the vendor's no-load speed, and the friction of urethane on whatever the robot
is driven on.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from robot import ACTUATOR  # noqa: E402

if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from cad.dimensions import load as load_dimensions  # noqa: E402

# --------------------------------------------------------------------------
# Where the description is

ROBOT_NAME = "wheeled_biped"

# Where Isaac Sim's own Python lives on this machine. Nothing here imports it.
# It is recorded so that the scripts which DO need it can say where it is when
# they are started with the system interpreter instead -- which is much the
# commonest way to trip over this directory, and the resulting
# "No module named 'omni'" points nowhere useful.
ISAAC_PYTHON = Path(r"Z:\IsaacSim\venv\Scripts\python.exe")


def needs_isaac_python(script: str) -> str:
    """The message for someone who ran an Isaac script with the wrong Python."""
    interpreter = ISAAC_PYTHON if ISAAC_PYTHON.exists() else Path("<isaac>/python.exe")
    return (
        f"\n{script} needs Isaac Sim's own Python, not the system one."
        f"\n\n    {interpreter} -u {script}"
        "\n\nor activate that environment first:"
        f"\n\n    {ISAAC_PYTHON.parent / 'activate'}"
        "\n\nPass -u either way: Kit shuts down hard enough to discard buffered"
        "\noutput, so without it a finished run can print nothing at all.\n"
    )


URDF_PATH = HERE / "urdf" / f"{ROBOT_NAME}.urdf"
USD_DIR = HERE / "isaacsim" / "usd"

# Isaac Sim 6.0's URDF importer takes an output DIRECTORY and writes
# <dir>/<robot name>/<robot name>.usda inside it, so the path below is the
# importer's choice rather than ours. It also refuses to overwrite: given a
# directory that already exists it invents wheeled_biped_01 beside it, which is
# why import_urdf.py clears the old one before every build.
ROBOT_USD_PATH = USD_DIR / ROBOT_NAME / f"{ROBOT_NAME}.usda"

# The one edge in this pipeline nothing used to watch. build_urdf.py refuses to
# build a URDF against a mesh older than the KCL it came from, so CAD-to-URDF is
# gated; URDF-to-USD was not. That is the worse of the two to leave open,
# because a stale USD does not fail -- Isaac Sim loads it, every rig check
# passes, and the numbers faithfully describe a robot that no longer exists.
URDF_MESH_DIR = URDF_PATH.parent / "meshes"

# How much newer an input may be than the USD built from it before the USD is
# called stale. build_urdf.py allows the same slack for the same reason: a
# checkout rewrites every mtime at once and would otherwise fire this on a
# fresh clone.
USD_GRACE_SECONDS = 2.0


def usd_inputs() -> list[Path]:
    """Everything import_urdf.py reads to build the robot USD."""
    meshes = sorted(URDF_MESH_DIR.glob("*.stl")) if URDF_MESH_DIR.is_dir() else []
    return [URDF_PATH, *meshes]


def stale_usd(usd_path: Path | None = None) -> list[tuple[str, float]]:
    """Which of the USD's inputs are newer than the USD itself, newest first.

    Empty when the USD is current. A MISSING USD is not stale, it is absent,
    and the caller reports that separately -- there is a different thing to do
    about it.
    """
    usd = usd_path or ROBOT_USD_PATH
    if not usd.exists():
        return []
    built = usd.stat().st_mtime
    behind = [
        (source.name, source.stat().st_mtime - built)
        for source in usd_inputs()
        if source.exists() and source.stat().st_mtime - built > USD_GRACE_SECONDS
    ]
    return sorted(behind, key=lambda item: -item[1])


def isaac_interpreter() -> Path:
    """Isaac Sim's Python where this machine has it, a placeholder where not.

    Printed into advice, so it has to degrade on a machine that keeps Isaac
    somewhere else rather than name a path that is not there.
    """
    return ISAAC_PYTHON if ISAAC_PYTHON.exists() else Path("<isaac>/python.exe")


def rebuild_command() -> str:
    """What to run when the USD is stale, with this machine's interpreter."""
    return f"{isaac_interpreter()} -u simulation/isaacsim/import_urdf.py"


def check_command() -> str:
    """What to run to measure what PhysX made of the rebuilt USD."""
    return f"{isaac_interpreter()} -u simulation/isaacsim/run.py --check"


# --------------------------------------------------------------------------
# The actuator, all six of them the same.
#
# DAMIAO DM-J3507-2EC, 7:1, 24 V, CAN-FD, MIT-mode torque control. These are
# robot.py's own figures, re-exported so that a simulator config never states
# an actuator number in its own right.

PEAK_TORQUE_NM = ACTUATOR["peak_torque_nm"]
CONTINUOUS_TORQUE_NM = ACTUATOR["continuous_torque_nm"]
MAX_VELOCITY_RAD_S = ACTUATOR["max_velocity_rad_s"]
ARMATURE_KG_M2 = ACTUATOR["armature_kg_m2"]
JOINT_FRICTION_NM = ACTUATOR["friction_nm"]
JOINT_DAMPING_NM_S_RAD = ACTUATOR["damping_nm_s_rad"]

# --------------------------------------------------------------------------
# The joints, in the order this project names them.
#
# Isaac Sim reports degrees of freedom in ITS OWN order, which is a depth-first
# walk of the articulation and is not this one. Every script here resolves by
# name and never by index; this tuple exists so that a report can be printed in
# an order a person recognises, and so that a missing joint is noticed.

LEG_JOINTS = (
    "hip_pitch_right",
    "knee_right",
    "hip_pitch_left",
    "knee_left",
)
WHEEL_JOINTS = (
    "wheel_drive_right",
    "wheel_drive_left",
)
JOINT_ORDER = (
    "hip_pitch_right",
    "knee_right",
    "wheel_drive_right",
    "hip_pitch_left",
    "knee_left",
    "wheel_drive_left",
)

# --------------------------------------------------------------------------
# Where it starts
#
# base_link's origin is the torso centre. A centimetre of clearance keeps the
# wheels off the ground plane at reset, so the first contact is resolved rather
# than penetrated.

RESET_CLEARANCE_M = 0.01

# --------------------------------------------------------------------------
# Ground contact
#
# UNMEASURED, ALL OF IT. 85A skate urethane on a hard floor is a high-friction,
# fairly lossy contact, and none of these numbers come from a measurement of
# this wheel on any surface. They are a starting point to randomise around, not
# a description of anything.
#
# The wheel collides as a cylinder rather than as its crowned tread, because
# every solver resolves a cylinder against a plane cleanly and none of them
# resolves a crowned mesh cleanly. What that loses is the contact patch
# narrowing as the robot leans, which is real; if a policy turns out to depend
# on it, that is the assumption to revisit first.

CONTACT = {
    "static_friction": 1.0,
    "dynamic_friction": 0.9,
    "restitution": 0.1,
}

# Ranges worth randomising over, since the true value is unknown. Urethane on a
# painted concrete floor and urethane on a rug are not the same robot.
DOMAIN_RANDOMISATION = {
    "static_friction": (0.6, 1.4),
    "dynamic_friction": (0.5, 1.2),
    # The capacitor bank has never been sized and most of the torso has never
    # been weighed, so the mass this model carries is uncertain by a good deal
    # more than the usual few per cent. Randomise the base mass accordingly. The
    # wheels and motors were weighed on 2026-11-02, so the wheel's range is now
    # wider than its mass needs; it is left as it was so that policies trained
    # before and after stay comparable.
    "base_mass_scale": (0.85, 1.15),
    "wheel_mass_scale": (0.8, 1.2),
    "armature_scale": (0.5, 2.0),
}

# --------------------------------------------------------------------------
# Measured on the robot, 4 November 2026
#
# Hung from strings and driven through sbc/sysid.py; the logs are in the
# untracked exports/sysid/2026-11-04/ and docs/SYSID.md says what each test
# found. Each figure is a range here, wide enough for what one day's fits on
# one robot can claim. The driving task trains on these (rough_env_cfg.py);
# the flat and jump tasks do not, so that what they were trained on stays as
# their runs record it.
MEASURED = {
    # A friction torque on every leg joint, each way: 0.042 to 0.049 Nm from
    # the slow sweeps (B5) on all four, 0.040 from the leg fit with the torso
    # held (B1). The joints also stick before they move, which a torque that
    # turns over smoothly through zero speed leaves out.
    "leg_coulomb_nm": (0.03, 0.06),
    # B1's fit puts 0.066 on top of the commanded damping, with the rotor's
    # inertia pinned at its lower bound -- a fit that has not settled -- so
    # this runs from none to a little past it.
    "leg_viscous_nm_s_rad": (0.0, 0.07),
    # B5: holding the legs up takes 9 to 14 per cent more torque than the
    # model's legs ask for. Heavier or lower-slung legs, or a torque reading
    # that runs high; the legs are made heavier, up to a fifth, to cover it.
    "leg_mass_scale": (0.95, 1.2),
    # The wheels in the air (B2): 0.010 to 0.018 Nm of friction and 0.005 Nm
    # s/rad of drag, against none in the simulator, and the wheel spinning up
    # like one with 8.4e-4 to 8.9e-4 kg m2 on its joint where the simulator had
    # 2.3e-4 -- two fits, the command's lag searched to 4 ms and to 14. That
    # was at a torque 1.07 times the command, which is what the legs measured,
    # so per newton-metre commanded it is about 8.3e-4; armature_scale spreads
    # it.
    "wheel_coulomb_nm": (0.005, 0.02),
    "wheel_viscous_nm_s_rad": (0.003, 0.008),
    "wheel_armature_kg_m2": 8.3e-4,
    # The IMU reads 16 ms behind the motors' reports, which arrive about
    # 1.5 ms after their command: three runs agree, from the torso's jolts
    # against the hips' torque. In 2.5 ms physics steps, 12.5 to 20 ms.
    "imu_delay_steps": (5, 8),
    "joint_delay_steps": (0, 1),
    # The wheels' fit put the command's lag at 4 ms, the top of what it was
    # first allowed to search, and at 8 ms searched to 14, hardly better: 2.5
    # to 10 ms.
    "action_delay_steps": (1, 4),
}

# What the wheels did with the robot's weight on them, on a hard floor, from its first
# drives on 5 November 2026 (docs/SYSID.md, "Why it wobbled"). Mean torque against
# speed steps at zero, to 0.035 to 0.045 Nm either way; a steady 5 rad/s, with nothing
# accelerating, takes 0.05 to 0.06, which puts the drag at about 0.003 Nm s/rad; a
# stuck wheel breaks away at 0.05 to 0.07 (medians, four run-ups each way, from 0.043 to
# 0.09 by quartile). All of it read from the motors' own torque, which at those slow
# speeds was within 8 per cent of the command.
ON_THE_FLOOR = {
    "wheel_coulomb_nm": (0.025, 0.05),
    "wheel_viscous_nm_s_rad": (0.002, 0.006),
    "wheel_static_nm": (0.05, 0.07),
    # The wheels' torque reading follows the logged command by 18 to 20 ms, and the
    # phases round the robot's 7 Hz yaw shake close at about 30 ms in all. The IMU is
    # 16 of that, and a command cannot be drawn later than 10 ms in training, so the
    # IMU's range carries what is left over: 12.5 to 27.5 ms.
    "imu_delay_steps": (5, 11),
}

# The motors' torque against speed, measured on the robot on 6 November 2026 (sysid.py
# W1, docs/SYSID.md): a wheel pushed at 1.5 Nm while a hand slowed it, the pack at
# 24.7-24.9 V. Full torque to 37.5 rad/s, then a straight fall of 0.09 Nm per rad/s to
# nothing at 54-55 rad/s, the free top speed too. As Isaac Lab's DC motor, torque =
# saturation x (1 - speed / no-load), under the 3 Nm peak: the rated figures' line
# from 3 Nm to 48.2 rad/s gave 0.5 Nm at 40 rad/s where the motor gives 1.2-1.4. The
# peak itself is the manual's: the spin-ups were too quick to reach it. The wheels are
# the same motor as the legs, so this is the legs' curve as well. A nearly flat pack
# was not measured; top speed should fall about with its voltage.
MOTOR_CURVE = {
    "saturation_nm": 4.95,
    "no_load_rad_s": 55.0,
    "pack_v": 24.8,
}

# What the robot's driving on 6 November 2026 showed that the tasks before D6 had wrong,
# from its logs and MuJoCo held against them (the robot's own loop, 16 ms IMU, 6 ms
# commands). Together these put MuJoCo on the robot in every column measured: the hold
# asking +0.13 m/s standing (the robot +0.12 to +0.19), 0.80 m/s at 1.15 asked (0.6 to
# 0.85), 1.14 at a full pull (0.85 to 1.3), -1.01 in reverse at -1.0 (-1.0 to -1.1), the
# torso 2.4 degrees back driving (2.0 to 2.6). Without them MuJoCo drove D3 at 1.0 and
# 1.55 m/s, stood it at 170 mm rocking at half the robot's rate, and missed the rock's
# frequency.
#
# THE WHEELS' TORQUE, which follows what is sent late and short. The torque each wheel
# reports, against the command, fitted as gain x a first-order lag of the command 4 to
# 8 ms late (the link's delay, which the tasks' action delay already draws), standing at
# 207 and 170 mm, both wheels alike: lag 12 to 15 ms, gain 0.79 to 0.91, residual 0.006
# to 0.034 Nm. The tasks before had a pure 2.5 to 10 ms delay and stood a longer IMU
# delay in for the rest (ON_THE_FLOOR's imu_delay_steps), which rocks at 2.5 to 2.7 Hz
# where the robot rocks at 1.5 to 1.7. The reported torque is the motor's own estimate
# and may be filtered itself, so the lag is fitted and not proven; that MuJoCo with it
# rocks as the robot does is the case for it.
WHEEL_RESPONSE = {
    "lag_s": (0.005, 0.020),
    "gain": (0.75, 1.0),
}
# THE LEGS' TORQUE, AS LATE. Fitted on 6 November 2026 from the robot's own logs (session
# scratchpad leglag/): the torque each hip and knee reported against what the motor's
# position-and-damping law asked for, rebuilt from the command and the motor's own
# position and speed on the controller's clock. 0-2.5 ms of delay and an 8-12 ms first-
# order lag on the robot driving (kp 12) and jumping (kp 6), 8-16 ms on the rail, at
# 0.9-1.05 of what is asked; the lag explains 90-99 % of the torque's variance, none
# 0-46 %, and holds from about 2 to 30 Hz (above that the motor gives less still: 0.2 of
# the asked at 39 Hz, the old kp 40 buzz). It is real torque, not a filtered reading: on
# the rail the joints' acceleration, from the encoders alone, is in step with the
# reported torque and 30-55 degrees behind the law's. In a jump the knees limit at about
# 3.25 Nm before the lag. The robot's torso shake at 11-22 Hz in its jumps is driven
# through the legs (the hips' and knees' speeds predict 96 % of it), and MuJoCo with
# this lag got halfway to it where the wheels' lag alone added nothing. The motor also
# damps on a speed it reports about 4 ms late, at 0.9 of the true rate, which is not
# drawn here.
LEG_RESPONSE = {
    "lag_s": (0.008, 0.014),
    "gain": (0.9, 1.05),
}
# THE WHEELS' FRICTION ON THE FLOOR at speed, from the torque they held driving steadily:
# 0.06-0.07 Nm a wheel at 16-18 rad/s, 0.09-0.10 at 29, which is 0.03 Nm and 0.002 Nm
# s/rad, the low end of ON_THE_FLOOR's (fitted from slow run-ups on 5 November). Drawn
# about those. The breakaway is ON_THE_FLOOR's, which this did not measure.
ON_THE_FLOOR_DRIVING = {
    "wheel_coulomb_nm": (0.02, 0.04),
    "wheel_viscous_nm_s_rad": (0.001, 0.003),
    "wheel_static_nm": ON_THE_FLOOR["wheel_static_nm"],
}
# THE IMU'S ZERO. The BNO085 reads the torso about 3 degrees more nose-down than it is
# since its accelerometer calibrated itself again on 5 November at about 16:10: the length
# of gravity it reports stepped from 9.95 to 9.75 m/s2 then, and the robot has driven
# slower forward than asked and faster back ever since, where on the 5th it overshot.
# MuJoCo with the IMU 2.7 degrees off reproduced the speeds; D3 fell braking from a full
# pull with it 1.2 degrees the other way, and at a full pull at -2.7. The chip may
# calibrate itself again, so the tasks draw the zero each episode rather than learn one
# value; the robot's own calibration is a separate fix. And the torso's centre of mass,
# which nothing has measured fore and aft and which looks to the policy much the same:
# 14 mm back in MuJoCo drove D3 at 0.91 and 1.42 m/s, the IMU 2.7 degrees off at 0.88
# and 1.37. The IMU is the one the gravity length's step dates.
IMU_TILT_DEG = {"pitch": 2.0, "roll": 2.0}
TORSO_COM_X_M = (-0.010, 0.010)

# THE ROBOT'S 11 HZ SHAKE, from D6 on the floor on the morning of 7 November 2026 (session
# scratchpad tap/). D6 rocked the whole robot in pitch at 10.5-11 Hz, 1.0-1.5 rad/s RMS,
# the wheels pushing 0.25 Nm RMS each, where D3 stands calm. The loop is the pitch rate
# the policy reads into the wheels' torque: D6 asks 0.43 Nm a wheel per rad/s there, D3
# 0.34 and D5 0.31, flat from 5 to 25 Hz, and around the robot's loop that is a gain of
# about 1.0-1.15 for D6 and 0.75-0.9 for D3. MuJoCo had D6 calm for three reasons:
#
#   * THE WHEEL'S INERTIA on its joint. The robot's own leg targets and wheel torques
#     replayed into MuJoCo move its wheels as the robot's moved at 2.8e-4 to 3.5e-4 kg m2,
#     where MEASURED's 8.3e-4 (a fit of the wheels spinning in the air, B2) moves them
#     half as far; training then drew x0.5-2 about 8.3e-4 and never met the robot's.
#   * EVERY MOTOR'S TORQUE, the commands logged as sent against what each motor reported,
#     at 11 Hz: a first-order lag of about 15 ms on the wheels and knees and 18 on the
#     hips, delivering 0.64-0.83 of what is asked; the legs' lag sits after their position
#     loop, as LEG_RESPONSE's. D6 trained with none on the legs.
#   * WHAT IS LEFT. With both, MuJoCo's torso still rocks 0.81 of the robot's under the
#     same push, and 33 degrees early. The IMU is not late (the fore-aft acceleration
#     follows the wheels' push within 2 ms), and a spring hidden in the hips, the contact's
#     stiffness and the torso's inertia do not account for it; a softer knee or the
#     torso's centre of mass 30 mm higher account for part. Unidentified, so it is stood
#     in for by the wheels' gain: at 1.15 MuJoCo's D6 rocks 1.0-1.5 rad/s RMS as the
#     robot's did, and D3 stays calm (0.05) at 1.15 and at 1.3.
#
# Drawn per episode in D7, the gain to 1.3 so that a policy keeps a margin over the robot.
SHAKE = {
    "wheel_armature_kg_m2": 3.0e-4,
    "wheel_lag_s": (0.010, 0.020),
    "wheel_gain": (0.8, 1.3),
    "leg_lag_s": (0.012, 0.020),
    "leg_gain": (0.95, 1.2),
}

# THE ROBOT'S SLOW SWAY, from D7 on the floor on the afternoon of 7 November 2026 (session
# scratchpad wobble/, wall/). D7, trained on SHAKE, swung the robot at 1-1.5 Hz with nothing
# asked: 0.3-0.58 rad/s RMS standing at 204 mm, about 10 degrees and the wheels 35 rad/s
# each way, the legs through their whole action each half swing, until a swing put the
# wheels at their 50 rad/s and it ran into a wall. D3 the night before stood at 207 mm at
# 0.03. D7 asks 0.7 of D3's wheel torque per rad/s of pitch rate at every frequency from 1
# to 25 Hz: SHAKE taught it to be gentler, which the 11 Hz loop wanted and the slow
# balance could not spare. In MuJoCo on launch_check.py's loop at 204 mm it sways 0.50
# rad/s at 1.1 Hz with the wheels' torque at 0.8 of asked, and 0.16 and 0.25 at 1.6 Hz with
# the IMU 30 and 40 ms late, where D3 holds 0.04-0.05 under each. Both were plausible on
# the robot that afternoon: every D7 run was on a boot whose IMU sent gravity at 45 Hz and
# the gyro 12-20 ms later than a good boot's (the hub short of time with four reports on;
# sbc/balance.py now turns two of them off for a run, which gave 99 Hz and 400 the same
# boot), and the wheels' gain is the unidentified stand-in described above.
#
# Drawn per episode in D8, so that a policy which sways with weak wheels or a late IMU
# sways here first, while SHAKE's top keeps the 11 Hz margin. In 2.5 ms physics steps the
# IMU's delay runs from MEASURED's 12.5 ms to 40.
SWAY = {
    "wheel_gain": (0.7, 1.3),
    "imu_delay_steps": (5, 16),
}

# --------------------------------------------------------------------------
# The solver
#
# A 40 mm wheel at the actuator's 48 rad/s no-load speed covers 5 mm of ground
# in a 2.5 ms step, which is still small against the wheel's own radius and is
# what a rolling contact needs to stay a rolling contact. That is tighter than the 4 ms the
# Isaac Lab config's CCD note assumes, and it is cheap on a robot with seven
# links.
#
# The iteration counts are the Isaac Lab config's, unchanged. A six-degree-of-
# freedom articulation standing on two point-ish contacts is not a hard solve;
# raise the position count first if the wheels start sinking.

PHYSICS_DT = 1.0 / 400.0
RENDER_DT = 1.0 / 60.0

SOLVER = {
    "position_iterations": 8,
    "velocity_iterations": 2,
    # This robot is small and light, and CCD stays on until it is shown to be
    # unnecessary.
    "max_depenetration_velocity": 1.0,
    "enable_ccd": True,
    # A balancing robot that falls asleep is a balancing robot that has fallen
    # over. Nothing here should ever sleep.
    "sleep_threshold": 0.0,
    "stabilization_threshold": 0.0,
}

# The legs fold under the robot at the knee's 110 degree stop, and the wheel
# comes up close to the thigh there. Self collision is left ON so that the stop
# is enforced by geometry as well as by the joint limit -- but it is the
# setting most likely to make a fresh import behave oddly, so it is named here
# rather than buried.
SELF_COLLISION = True


# --------------------------------------------------------------------------
# Geometry, read out of the CAD


@lru_cache(maxsize=1)
def geometry() -> dict[str, float]:
    """The handful of CAD dimensions a simulator scene needs, in metres.

    Read from the KCL, so a change to the CAD moves the scene without anything
    here being edited. The relationships are asserted rather than the numbers,
    the same way build_urdf.py does it: a dimension that failed to parse breaks
    a relationship, and a legitimate design change does not.
    """
    d = load_dimensions()

    wheel_radius = d["prototypeWheelAxisHeight"] / 1000.0
    standing_base_height = d["wheeledTorsoCenterHeight"] / 1000.0
    standing_height = d["wheeledTorsoTop"] / 1000.0
    # Hip to hip, plus on each side the knee's step outboard -- the straddled
    # knee puts the shin's joint kneeOutboardOffset further out than the
    # thigh's (cad/limb.py) -- plus the wheel's centre plane beyond that.
    track = (
        2.0 * (d["kneeOutboardOffset"] + d["skateWheelCenterX"]) + d["hipSpacing"]
    ) / 1000.0

    assert abs(wheel_radius - d["skateWheelDiameter"] / 2000.0) < 1e-9, (
        "the wheel axis is not at the wheel's own radius"
    )
    assert 0.0 < wheel_radius < standing_base_height < standing_height, (
        "the robot's heights do not stack up"
    )

    return {
        "wheel_radius_m": wheel_radius,
        "wheel_width_m": d["skateWheelWidth"] / 1000.0,
        # Hip to knee and knee to axle, which is all a crouched start needs to
        # know where the torso ends up.
        "upper_leg_m": d["upperLegLength"] / 1000.0,
        "lower_leg_m": d["lowerLegLength"] / 1000.0,
        "standing_base_height_m": standing_base_height,
        "standing_height_m": standing_height,
        "track_m": track,
    }


def standing_base_height_m() -> float:
    """How high base_link's origin sits with the legs straight."""
    return geometry()["standing_base_height_m"]


def spawn_height_m() -> float:
    """Where to drop base_link from, wheels a centimetre clear of the floor."""
    return standing_base_height_m() + RESET_CLEARANCE_M


def wheel_radius_m() -> float:
    """The rolling radius, which run.py measures back out of the simulation."""
    return geometry()["wheel_radius_m"]


# --------------------------------------------------------------------------
# The continuous torque limit
#
# The URDF carries the 3 Nm peak because that is the only limit a URDF can
# express. The 0.8 Nm continuous rating is thermal, and docs/PLAN.md already
# records that the knee crosses it at about 47 degrees of sustained flexion
# just holding the robot up. Anything commanding this robot for long enough to
# matter needs a cost on it, because the hardware will derate and then stop.


def continuous_torque_excess(torques) -> list[float]:
    """How far past the thermal rating each joint is, in Nm, never negative.

    Takes any iterable of applied torques and returns a plain list, so that it
    works the same on a numpy array inside Isaac Sim and on six floats out of a
    log. The framework-specific reward term wrapping this lives with the
    framework.
    """
    return [max(abs(float(t)) - CONTINUOUS_TORQUE_NM, 0.0) for t in torques]
