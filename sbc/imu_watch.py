#!/usr/bin/env python3
"""Read-only IMU flight recorder. Never takes control or resets the sensor.

python3 imu_watch.py --seconds 180 --output imu-trace.jsonl
python sbc/imu_watch.py --robot ssh:bpi-m4zero --output exports/imu-trace.jsonl
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

from diag_client import Robot, RobotError


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--robot", default="127.0.0.1:7700")
    ap.add_argument("--seconds", type=float, default=180)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    counts = Counter()
    recent = deque(maxlen=2000)
    events = deque(maxlen=2000)
    last_input = [None]
    robot = Robot(
        args.robot,
        name="IMU flight recorder",
        streams=("status", "imu", "imu.raw", "imu.diag", "log"),
    )

    def report(message):
        with lock:
            counts[message["report"]] += 1
            last_input[0] = time.monotonic()

    def raw(message):
        with lock:
            recent.append(dict(message))
            if bytes.fromhex(message["data"])[2] in (0, 1, 2):
                events.append(dict(message))

    def event(message):
        with lock:
            events.append(dict(message))

    robot.on("imu", report)
    robot.on("imu.raw", raw)
    robot.on("imu.diag", event)
    robot.on("log", event)
    start = time.monotonic()
    fault_recorded = False
    with args.output.open("w", encoding="utf-8", buffering=1) as out:

        def write(kind, **fields):
            out.write(
                json.dumps(
                    {
                        "kind": kind,
                        "utc": datetime.now(timezone.utc).isoformat(),
                        "elapsed": round(time.monotonic() - start, 6),
                        **fields,
                    }
                )
                + "\n"
            )

        write("start", info=robot.info)
        print(f"Recording to {args.output}; no control or sensor commands", flush=True)
        try:
            while time.monotonic() - start < args.seconds and robot.error is None:
                time.sleep(1)
                now = time.monotonic()
                with lock:
                    snapshot = dict(counts)
                    age = now - last_input[0] if last_input[0] else None
                    queued = list(events)
                    events.clear()
                    history = list(recent)
                for message in queued:
                    write("event", message=message)
                write("summary", counts=snapshot, input_age_s=age, status=robot.status)
                stalled = age > 1 if age is not None else now - start > 5
                if stalled and not fault_recorded:
                    write("stall", input_age_s=age, before_fault=history)
                    try:
                        write("diagnostics", data=robot.request("imu.diagnostics"))
                    except RobotError as error:
                        write("diagnostics_error", error=str(error))
                    print(
                        f"IMU stalled at {now - start:.1f}s; context saved", flush=True
                    )
                    fault_recorded = True
                elif not stalled and fault_recorded:
                    write("recovered", counts=snapshot)
                    print("IMU reports resumed", flush=True)
                    fault_recorded = False
        except KeyboardInterrupt:
            pass
        finally:
            write("end", error=robot.error, counts=dict(counts))
            robot.close()


if __name__ == "__main__":
    main()
