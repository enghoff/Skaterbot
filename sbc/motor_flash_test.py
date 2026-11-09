#!/usr/bin/env python3
"""Plays a fault's pattern on the motors' own LEDs with no fault there, and watches what
the motors do meanwhile: that they switch as the pattern says, and that they move and
push no more than they do switched off. docs/DIAGNOSTICS.md, "The motors' LEDs".

Only while disarmed: it takes control, and will not start if anyone holds it. It sends the
motors nothing during the pattern, since anything the Pi sends one ends it, and reads the
answers they give the controller's own frames.

    python3 motor_flash_test.py imu --motors 5 --seconds 4     motor 5, the left wheel
    python3 motor_flash_test.py link                           every motor
    python3 motor_flash_test.py hardware --seconds 6
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import diag_client  # noqa: E402

FAULTS = {"link": 1, "imu": 2, "hardware": 3}
# A cycle of each, firmware/diag/src/health.rs's.
CYCLE_S = {"link": 1.0, "imu": 0.2, "hardware": 1.2}
BUS_OF = {1: "A", 2: "A", 3: "B", 4: "B", 5: "C", 6: "C"}
DISABLE = bytes([0xFF] * 7 + [0xFD])
# As the controller's motor_flash.rs has it: what the Pi sends a motor keeps a pattern off
# for this long.
HANDS_OFF_S = 3.0
# The motors' registers, reference/motors/registers_after_vmax_2026-11-04.json.
PMAX, VMAX, TMAX = 12.566, 50.0, 5.0
# Past these it is stopped at once.
STOP_NM, STOP_RAD_S, STOP_RAD = 0.5, 3.0, 0.2
# What a motor told no torque and switched on should stay inside.
FINE_NM, FINE_RAD_S, FINE_RAD = 0.15, 1.0, 0.05
ENABLED, DISABLED = 1, 0
NAME = "motor_flash_test"


class Motors:
    """What the motors say, as the controller's CAN frames bring it."""

    def __init__(self, wanted: list[int]):
        self.wanted = wanted
        self.lock = threading.Lock()
        self.rows: dict[int, list[tuple[float, int, float, float, float]]] = {
            m: [] for m in wanted
        }
        self.start: dict[int, float] = {}
        self.stop_why: str | None = None
        self.refused: str | None = None
        self.said: list[str] = []

    def heard(self, message: dict) -> None:
        d = bytes.fromhex(message["data"])
        # An answer about a register, such as the controller's asking each motor its
        # mode, has the ID's high byte, 0, where a report has the position's.
        if len(d) != 8 or (d[1] == 0 and d[2] in (0x33, 0x55)):
            return
        m = d[0] & 0x0F
        if m not in self.rows or message["bus"] != BUS_OF[m]:
            return
        state = d[0] >> 4
        p = (d[1] << 8 | d[2]) / 65535 * 2 * PMAX - PMAX
        v = (d[3] << 4 | d[4] >> 4) / 4095 * 2 * VMAX - VMAX
        t = ((d[4] & 0x0F) << 8 | d[5]) / 4095 * 2 * TMAX - TMAX
        with self.lock:
            self.rows[m].append((time.monotonic(), state, p, v, t))
            if self.start and self.stop_why is None:
                if abs(t) > STOP_NM:
                    self.stop_why = f"motor {m} pushing {t:+.2f} Nm"
                elif abs(v) > STOP_RAD_S:
                    self.stop_why = f"motor {m} turning {v:+.2f} rad/s"
                elif m in self.start and abs(p - self.start[m]) > STOP_RAD:
                    self.stop_why = f"motor {m} moved {p - self.start[m]:+.3f} rad"

    def log(self, message: dict) -> None:
        text = message["text"]
        if "motor flash" in text:
            self.said.append(text)
            if "refused" in text:
                self.refused = text

    def last_position(self, m: int) -> float | None:
        with self.lock:
            return self.rows[m][-1][2] if self.rows[m] else None


def poke(robot: diag_client.Robot, motors: list[int]) -> None:
    """Asks each motor where it is, by the one frame that cannot start anything."""
    for m in motors:
        robot.send("can.send", bus=BUS_OF[m], id=m, data=DISABLE.hex())
    time.sleep(0.2)


def end_pattern(robot: diag_client.Robot) -> None:
    """The pattern over. It needs control, so it cannot touch a run that has since taken
    it, where the stop every other tool would use would end that run."""
    try:
        robot.request("motors.flash", fault=0, motors=0, seconds=0)
    except diag_client.RobotError:
        pass


def holder(robot: diag_client.Robot) -> str:
    status = robot.request("status")
    return (status.get("status", status).get("pi") or {}).get("control") or ""


def verdict(rows: list, fault: str, seconds: float) -> tuple[bool, str]:
    states = [r[1] for r in rows]
    if not rows:
        return False, "said nothing"
    ons = sum(1 for a, b in zip(states, states[1:]) if a == DISABLED and b == ENABLED)
    if states[0] == ENABLED:
        ons += 1
    expected = seconds / CYCLE_S[fault]
    odd = sorted({s for s in states if s not in (DISABLED, ENABLED)})
    span = max(r[2] for r in rows) - min(r[2] for r in rows)
    speed = max(abs(r[3]) for r in rows)
    push = max(abs(r[4]) for r in rows)
    switched = 0.7 * expected <= ons <= expected + 1.5
    fine = (
        switched
        and not odd
        and states[-1] == DISABLED
        and span < FINE_RAD
        and speed < FINE_RAD_S
        and push < FINE_NM
    )
    words = (
        f"{len(rows)} answers, switched on {ons} times (about {expected:.0f} expected), "
        f"ended {'off' if states[-1] == DISABLED else 'ON'}, moved {span:.4f} rad, "
        f"to {speed:.2f} rad/s, pushed to {push:.3f} Nm"
        + (f", odd states {odd}" if odd else "")
    )
    return fine, words


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("fault", choices=FAULTS)
    ap.add_argument("--motors", default="1,2,3,4,5,6", help="IDs, comma-separated")
    ap.add_argument("--seconds", type=float, default=5.0)
    args = ap.parse_args()
    motors = sorted(int(m) for m in args.motors.split(","))
    if not motors or any(m not in BUS_OF for m in motors):
        ap.error("motors are 1 to 6")
    seconds = int(args.seconds)
    if not 1 <= seconds <= 60:
        ap.error("1 to 60 seconds")
    mask = sum(1 << (m - 1) for m in motors)

    robot = diag_client.Robot(name=NAME, streams=("status", "log", "can"))
    seen = Motors(motors)
    robot.on("can", seen.heard)
    robot.on("log", seen.log)
    took = False
    try:
        held = holder(robot)
        if held:
            print(f"REFUSED: {held} holds control")
            return 1
        robot.take_control()
        took = True
        poke(robot, motors)
        missing = [m for m in motors if seen.last_position(m) is None]
        if missing:
            print(f"REFUSED: no answer from motors {missing}")
            return 1
        with seen.lock:
            seen.start = {m: seen.rows[m][-1][2] for m in motors}
            for m in motors:
                seen.rows[m].clear()
        time.sleep(HANDS_OFF_S + 0.3)
        robot.request(
            "motors.flash", fault=FAULTS[args.fault], motors=mask, seconds=seconds
        )
        end = time.monotonic() + seconds + 0.6
        while time.monotonic() < end and seen.stop_why is None and seen.refused is None:
            time.sleep(0.01)
        if seen.refused:
            print(f"REFUSED: {seen.refused}")
            return 1
        if seen.stop_why:
            end_pattern(robot)
            print(f"STOPPED: {seen.stop_why}")
            time.sleep(0.3)
        if NAME not in holder(robot):
            print("FAILED: something else has taken the motors; leaving them to it")
            took = False
            return 1
        with seen.lock:
            during = {m: list(seen.rows[m]) for m in motors}
            start = dict(seen.start)
            seen.start = {}  # what comes now is this script's own asking
        good = seen.stop_why is None
        for m in motors:
            fine, words = verdict(during[m], args.fault, seconds)
            good &= fine
            print(f"motor {m}: {'ok' if fine else 'NOT OK'}: {words}")
        time.sleep(0.2)
        poke(robot, motors)
        for m in motors:
            p = seen.last_position(m)
            print(f"motor {m}: {p - start[m]:+.4f} rad from where it started")
        for line in seen.said:
            print(f"# {line}")
        print("PASSED" if good else "FAILED")
        return 0 if good else 1
    finally:
        if took:
            end_pattern(robot)
            try:
                robot.release_control()
            except diag_client.RobotError:
                pass
        robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
