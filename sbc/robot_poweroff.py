#!/usr/bin/python3
"""Final systemd shutdown hook for the carrier's power latch.

Install as /usr/lib/systemd/system-shutdown/robot-poweroff, with flash_mcu.py
in /usr/local/lib/bipedal. Only systemd's 'poweroff' argument cuts power;
reboot, halt and kexec leave the latch alone. --check performs no GPIO writes.
--stop-heartbeat stops Linux heartbeat LEDs without touching the power latch.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def board_model() -> str:
    try:
        return Path("/proc/device-tree/model").read_text()
    except OSError:
        return ""


def stop_heartbeat(
    leds: Path = Path("/sys/class/leds"), model: str | None = None
) -> int:
    """Stop heartbeat LEDs only; no GPIO or power-latch changes."""
    if model is None:
        model = board_model()
    changed = 0
    for led in leds.iterdir():
        trigger = led / "trigger"
        if trigger.exists() and "[heartbeat]" in trigger.read_text():
            trigger.write_text("none")
            # This BPI's DT marks the red LED active-high; measured at the
            # board, its dark level is 1. Keep the quirk local to this LED/model.
            inverted = led.name == "red:status" and "BPI-M4-Zero" in model
            dark = (led / "max_brightness").read_text().strip() if inverted else "0"
            (led / "brightness").write_text(dark)
            changed += 1
    return changed


def start_heartbeat(
    leds: Path = Path("/sys/class/leds"), model: str | None = None
) -> None:
    trigger = leds / "red:status/trigger"
    if trigger.exists():
        trigger.write_text("heartbeat")
        # Re-selecting a trigger resets its invert setting. On this board the
        # normal brief flashes need invert=1, with the same dark level as above.
        invert = leds / "red:status/invert"
        if (
            "BPI-M4-Zero" in (model if model is not None else board_model())
            and invert.exists()
        ):
            invert.write_text("1")


def main() -> None:
    if sys.argv[1:] == ["--start-heartbeat"]:
        start_heartbeat()
        return
    if sys.argv[1:] == ["--stop-heartbeat"]:
        print(f"shutdown: stopped {stop_heartbeat()} heartbeat LED(s)")
        return
    if sys.argv[1:] not in (["poweroff"], ["--check"]):
        return
    # /home may already be unmounted at this stage of shutdown.
    sys.path.insert(0, "/usr/local/lib/bipedal")
    from flash_mcu import NRST, SBC_HOLD, Line, open_controller

    chip = open_controller()
    if sys.argv[1:] == ["--check"]:
        os.close(chip)
        print("power-off hook: GPIO controller available; no pins changed")
        return
    # systemd invokes this after stopping services and unmounting/remounting
    # filesystems read-only. Keep the MCU in reset so it cannot raise HOLD
    # again, and lower the Pi's separate HOLD. The latch opens in ~0.9 s.
    reset = Line(chip, NRST, 0, open_drain=True)
    hold = Line(chip, SBC_HOLD, 0, open_drain=False)
    time.sleep(5)
    # Reaching this point means the latch did not cut power. Let Linux finish
    # halting and report the fault rather than hanging shutdown indefinitely.
    print("robot-poweroff: power latch did not cut power", file=sys.stderr)
    hold.release()
    reset.release()
    os.close(chip)


if __name__ == "__main__":
    main()
