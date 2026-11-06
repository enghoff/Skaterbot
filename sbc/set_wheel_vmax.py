"""Sets the wheels' VMAX, the range their speed is reported in, and stores it.

    python3 set_wheel_vmax.py            read the wheels' VMAX, MAX_SPD and gear ratio
    python3 set_wheel_vmax.py 70         set VMAX to 70 rad/s on both, and save it

A report's speed wraps round past VMAX and reads backwards, which is why balance.py cuts
a wheel past VMAX less 5. At 55, set on every motor before the first tests, that was
50 rad/s, 2 m/s on a 40 mm wheel, and it dropped the robot three times on 2026-11-05.
VMAX is a range and no limit: what holds a motor's speed is MAX_SPD over the gear ratio.

Only with the robot disarmed: it takes control, which stops every motor, and a motor
stores its registers only while disabled. Run it through flash_robot.sh's check first.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "bench"))

import damiao  # noqa: E402
import diag_client  # noqa: E402
import sysid_tests as st  # noqa: E402

LOWEST, HIGHEST = 55.0, 100.0


def main(argv: list[str]) -> int:
    want = float(argv[1]) if len(argv) > 1 else None
    if want is not None and not LOWEST <= want <= HIGHEST:
        print(f"VMAX from {LOWEST:g} to {HIGHEST:g} rad/s")
        return 2
    wiring = st.load_robot()["joints"]
    robot = diag_client.Robot(name="set_wheel_vmax")
    try:
        held = (
            (robot.request("status").get("status") or {}).get("pi", {}).get("control")
        )
        if held:
            print(f"REFUSED: armed, {held} holds control")
            return 1
        robot.take_control()
        buses = {}
        for joint in st.WHEELS:
            w = wiring[joint]
            letter = w.bus if hasattr(w, "bus") else w["bus"]
            can_id = w.id if hasattr(w, "id") else w["id"]
            bus = buses.get(letter) or buses.setdefault(
                letter, damiao.Bus(robot.can(letter), letter)
            )
            m = bus.probe(can_id)
            if m is None:
                print(f"{joint}: nothing answers at bus {letter}, ID {can_id}")
                return 1
            regs = {
                r: m.registers.get(damiao.RID[r]) for r in ("VMAX", "MAX_SPD", "Gr")
            }
            print(
                f"{joint}: VMAX {regs['VMAX']}, MAX_SPD {regs['MAX_SPD']}, Gr {regs['Gr']}, "
                f"so held to {m.speed_cap and round(m.speed_cap, 1)} rad/s"
            )
            if want is None:
                continue
            for _ in range(3):
                bus.disable(m)
                time.sleep(0.005)
            echo = bus.write(can_id, damiao.RID["VMAX"], want)
            if echo is None or abs(float(echo) - want) > 1e-3:
                print(f"{joint}: the write was not confirmed ({echo})")
                return 1
            if not bus.save(can_id):
                print(f"{joint}: the save was not confirmed")
                return 1
            back = bus.read(can_id, damiao.RID["VMAX"])
            print(f"{joint}: VMAX now {back}, saved")
    finally:
        try:
            robot.release_control()
        except diag_client.RobotError:
            pass
        robot.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
