# /// script
# requires-python = ">=3.11"
# dependencies = ["pyserial>=3.5"]
# ///
"""A window for configuring and testing DAMIAO motors, through the USB-to-CAN debugger or the robot.

    uv run bench/motor_gui.py
    uv run bench/motor_gui.py --robot ssh:admin@<the Pi>

It reaches motors two ways. Through DAMIAO's USB-to-CAN debugger, found by its
USB ID, one bus. Or through the robot itself: the controller board running
firmware/diag and the Banana Pi running sbc/diagd.py, which carry all three of
the robot's buses and its IMU and battery bus (docs/DIAGNOSTICS.md). The box
offers the Banana Pi as ssh:bpi-m4zero, which the PC's SSH configuration
resolves; any other robot is typed in, as host:port for diagd directly, or
ssh:DEST to reach it through SSH, which is how a PC should. `python
sbc/diagd.py --sim` gives a robot with simulated motors to try this on.

Connect scans CAN IDs 1 to 16 on every bus with register reads, which cannot
move anything. Pick a motor on the left. The Registers tab reads, writes and
saves its settings and gives it a new CAN ID; the Drive tab enables it and
commands it in whichever of its four modes it is set to, with a sine or square
wave on the setpoint if asked, and plots what it reports. Connected to the
robot, the System tab shows the controller, its buses, the battery and the IMU.

What keeps it safe:

- Esc, or the red button, disables every motor on every bus, on every mode's
  frame ID, from anywhere in the window. So does closing it. On the robot it
  also has the controller stop every motor itself.
- Enabling starts from nothing: in MIT mode no stiffness, no damping and no
  torque, holding the present position; in the position modes the present
  position at a slow speed; in velocity mode zero speed.
- Every command is clamped to the limits on the Drive tab before it is sent. In
  MIT mode the target position is also kept within the torque limit's reach of
  where the motor is, so the spring never pulls harder than that limit however
  far away the slider is set; the feedforward can add the same again, and the
  damping more, since it is not bounded by anything but Kd.
- A motor that reports a fault stops being driven.
- Settings change only while a motor is disabled, and only in its RAM until Save
  to flash. The CAN bit rate is not offered at all, since the debugger or the
  controller would stop hearing the motor.
- On the robot, the Pi stops every motor if this window stops talking to it for
  half a second, and the controller does if the Pi stops talking to it.

What it cannot do: if this program dies while a motor is enabled on the
debugger, the motor holds its last command unless its TIMEOUT register is set,
and the first motor read arrived with it at 0, which is off. The Drive tab says
so when it is.

The protocol is in damiao.py beside this file.
"""

from __future__ import annotations

import argparse
import math
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import damiao as dm
import serial

# The robot's client is the Pi's own, in sbc/, and needs nothing installed.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sbc"))
import diag_client  # noqa: E402

PLOT_WINDOW_S = 10.0
POLL_HZ = 20  # status requests to motors that are not being driven
STALE_S = 0.3  # feedback older than this, from a driven motor, is a fault
WAVES = ("constant", "sine", "square")
LINK_ERRORS = (serial.SerialException, OSError, diag_client.RobotError)
DEBUGGER_BUS = "USB"
IMU_REPORTS = ("accel", "gyro", "gravity", "game")
IMU_HZ = 100
# The robots offered in the box, after any --robot or $DIAG_ROBOT, and what each
# is. The Pi by the name the PC's SSH configuration gives it, which carries its
# key and finds its address.
ROBOTS = {
    "ssh:bpi-m4zero": "the Banana Pi, through SSH",
    diag_client.DEFAULT_ROBOT: "diagd --sim on this PC",
}


def clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


@dataclass
class Limits:
    """Nothing beyond these is ever sent, whatever the sliders say."""

    torque: float = 0.5
    kp: float = 10.0
    kd: float = 1.0
    speed: float = 5.0
    current: float = 0.3


@dataclass
class Command:
    """What one motor is being told, set from the window and sent by the streamer."""

    active: bool = False
    p: float = 0.0
    v: float = 0.0
    kp: float = 0.0
    kd: float = 0.0
    t: float = 0.0
    vlim: float = 1.0
    ilim: float = 0.2
    wave: str = "constant"
    amp: float = 0.0
    freq: float = 0.5
    t0: float = 0.0
    enabled_at: float = 0.0
    trace: deque = field(default_factory=lambda: deque(maxlen=4000))

    def setpoint(self, mode: int, now: float) -> float:
        """Position, or speed in velocity mode, with the wave on top."""
        base = self.v if mode == dm.VELOCITY else self.p
        if self.wave == "constant" or not self.amp:
            return base
        s = math.sin(2 * math.pi * self.freq * (now - self.t0))
        return base + self.amp * (s if self.wave == "sine" else math.copysign(1, s))

    def start_from(self, m: dm.Motor, fb: dm.Feedback) -> None:
        self.p, self.v, self.kp, self.kd, self.t = fb.pos, 0.0, 0.0, 0.0, 0.0
        self.vlim, self.wave, self.amp = 1.0, "constant", 0.0


def key_of(bus: dm.Bus, m: dm.Motor) -> tuple[str, int]:
    """A motor's name in this window: its bus and its CAN ID."""
    return (bus.name, m.can_id)


class Streamer(threading.Thread):
    """Sends every driven motor its command at the set rate, and polls the rest."""

    def __init__(self, app: App):
        super().__init__(daemon=True)
        self.app = app
        self.rate = 200.0
        self.running = True

    def run(self) -> None:
        next_tick = time.perf_counter()
        last_poll = 0.0
        while self.running and self.app.link_error() is None:
            now = time.monotonic()
            poll = now - last_poll >= 1 / POLL_HZ
            if poll:
                last_poll = now
            try:
                for bus in list(self.app.buses.values()):
                    for m in list(bus.motors.values()):
                        cmd = self.app.commands.get(key_of(bus, m))
                        if cmd is not None and cmd.active:
                            self.drive(bus, m, cmd, now)
                        elif poll:
                            bus.request_status(m)
            except LINK_ERRORS as e:
                self.app.lost = f"link lost: {e}"
                break
            next_tick += 1 / self.rate
            delay = next_tick - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                next_tick = time.perf_counter()

    def drive(self, bus: dm.Bus, m: dm.Motor, cmd: Command, now: float) -> None:
        fb = m.feedback
        if fb is not None and fb.fault and fb.t > cmd.enabled_at:
            cmd.active = False
            bus.disable(m)
            self.app.say(
                f"motor {self.app.label(bus, m)} tripped ({fb.state_name}); disabled"
            )
            return
        lim = self.app.limits
        sp = cmd.setpoint(m.mode, now)
        if m.mode == dm.MIT:
            kp = clamp(cmd.kp, 0.0, lim.kp)
            sp = clamp(sp, -m.pmax, m.pmax)
            if kp > 0 and fb is not None:
                # The spring pulls with Kp times the distance to the target, so
                # keep the target within the torque limit's reach of where the
                # motor is: a far target is then a gentle pull, never a snap.
                reach = lim.torque / kp
                sp = clamp(sp, fb.pos - reach, fb.pos + reach)
            bus.mit(
                m,
                sp,
                clamp(cmd.v, -lim.speed, lim.speed),
                kp,
                clamp(cmd.kd, 0.0, lim.kd),
                clamp(cmd.t, -lim.torque, lim.torque),
            )
        elif m.mode == dm.POS_VEL:
            bus.pos_vel(m, sp, clamp(cmd.vlim, 0.0, lim.speed))
        elif m.mode == dm.VELOCITY:
            sp = clamp(sp, -lim.speed, lim.speed)
            bus.velocity(m, sp)
        elif m.mode == dm.HYBRID:
            bus.hybrid(
                m, sp, clamp(cmd.vlim, 0.0, lim.speed), clamp(cmd.ilim, 0, lim.current)
            )
        with bus.history_lock:
            cmd.trace.append((now, sp))


class Slider:
    """A labelled value with a slider and a spinbox on the same variable."""

    def __init__(self, parent, row, label, lo, hi, step, on_change):
        self.step = step
        self.var = tk.DoubleVar(value=0.0)
        self.label = ttk.Label(parent, text=label)
        self.scale = ttk.Scale(
            parent,
            from_=lo,
            to=hi,
            variable=self.var,
            orient="horizontal",
            length=300,
            command=self._snap,
        )
        self.spin = ttk.Spinbox(
            parent,
            from_=lo,
            to=hi,
            increment=step,
            textvariable=self.var,
            width=9,
        )
        self.widgets = (self.label, self.scale, self.spin)
        for col, w in enumerate(self.widgets):
            w.grid(row=row, column=col, sticky="ew", padx=4, pady=2)
        self.var.trace_add("write", lambda *_: on_change())

    def _snap(self, value: str) -> None:
        snapped = round(round(float(value) / self.step) * self.step, 6)
        if snapped != self.get():
            self.var.set(snapped)

    def set_range(self, lo: float, hi: float) -> None:
        self.scale.configure(from_=lo, to=hi)
        self.spin.configure(from_=lo, to=hi)

    def get(self) -> float | None:
        try:
            return float(self.var.get())
        except (tk.TclError, ValueError):
            return None

    def set(self, value: float) -> None:
        self.var.set(round(value, 4))

    def show(self, visible: bool) -> None:
        for w in self.widgets:
            w.grid() if visible else w.grid_remove()


class App(tk.Tk):
    def __init__(self, robots: list[str] | None = None):
        super().__init__()
        self.title("DAMIAO motors")
        ttk.Style(self).configure(
            "TNotebook.Tab", padding=(18, 6), font=("Segoe UI", 10, "bold")
        )
        self.geometry("1400x980")
        self.minsize(1100, 700)
        self.robots = list(dict.fromkeys([*(robots or []), *ROBOTS]))
        # One bus through the debugger, or the robot's three through diagd.
        self.buses: dict[str, dm.Bus] = {}
        self.debugger: dm.Debugger | None = None
        self.robot: diag_client.Robot | None = None
        self.lost: str | None = None
        self.streamer: Streamer | None = None
        self.commands: dict[tuple[str, int], Command] = {}
        self.limits = Limits()
        self.selected: tuple[str, int] | None = None
        self.jobs = ThreadPoolExecutor(max_workers=1)
        self.inbox: queue.Queue = queue.Queue()
        self.imu: dict[str, tuple[float, list[float], int]] = {}
        self.imu_counts: dict[str, deque] = {}
        self._loading = False
        self._ticks = 0
        self._build()
        self.refresh_ports()
        self.bind_all("<Escape>", lambda e: self.stop_all())
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(50, self.tick)

    # -- layout ----------------------------------------------------------------

    def _build(self) -> None:
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Label(top, text="Connect to").pack(side="left")
        self.port_var = tk.StringVar()
        # Typed into as well as picked from: a robot's address is typed.
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, width=54)
        self.port_box.pack(side="left", padx=4)
        ttk.Button(top, text="↻", width=3, command=self.refresh_ports).pack(side="left")
        self.connect_btn = ttk.Button(top, text="Connect", command=self.toggle_connect)
        self.connect_btn.pack(side="left", padx=8)
        ttk.Label(top, text="Scan IDs 1 to").pack(side="left")
        self.scan_to = tk.IntVar(value=16)
        ttk.Spinbox(top, from_=1, to=127, textvariable=self.scan_to, width=4).pack(
            side="left", padx=2
        )
        ttk.Button(top, text="Scan", command=self.scan).pack(side="left", padx=4)
        ttk.Label(top, text="Command rate, Hz").pack(side="left", padx=(16, 2))
        self.rate_var = tk.IntVar(value=200)
        rate = ttk.Spinbox(
            top, from_=20, to=500, increment=10, textvariable=self.rate_var, width=5
        )
        rate.pack(side="left")
        self.rate_var.trace_add("write", lambda *_: self._set_rate())
        tk.Button(
            top,
            text="STOP ALL  (Esc)",
            bg="#c62828",
            fg="white",
            activebackground="#8e0000",
            activeforeground="white",
            font=("Segoe UI", 11, "bold"),
            padx=14,
            command=self.stop_all,
        ).pack(side="right")

        body = ttk.PanedWindow(self, orient="vertical")
        body.pack(fill="both", expand=True, padx=6)

        motors = ttk.Frame(body)
        body.add(motors, weight=0)
        cols = ("bus", "id", "master", "mode", "state", "pos", "vel", "torque")
        cols += ("mos", "wind")
        heads = (
            "Bus",
            "CAN ID",
            "Master",
            "Mode",
            "State",
            "Pos °",
            "rad/s",
            "Nm",
            "MOS",
            "Wdg",
        )
        widths = (50, 70, 70, 140, 220, 90, 90, 90, 70, 70)
        self.tree = ttk.Treeview(motors, columns=cols, show="headings", height=6)
        for c, h, w in zip(cols, heads, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="center")
        self.tree.pack(fill="both", expand=True, pady=(0, 6))
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        self.notebook = ttk.Notebook(body)
        body.add(self.notebook, weight=1)
        self._build_drive(self.notebook)
        self._build_registers(self.notebook)
        self._build_system(self.notebook)

        bottom = ttk.Frame(self, padding=(6, 4))
        bottom.pack(fill="x")
        self.log_box = ScrolledText(bottom, height=7, font=("Consolas", 9))
        self.log_box.pack(fill="x")
        self.log_box.configure(state="disabled")
        self.status = ttk.Label(self, text="not connected", anchor="w", padding=(8, 2))
        self.status.pack(fill="x")

    def _build_drive(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text="Drive")
        ctl = ttk.Frame(tab)
        ctl.pack(side="left", fill="y")

        row = ttk.Frame(ctl)
        row.pack(fill="x", pady=(0, 6))
        ttk.Label(row, text="Mode").pack(side="left")
        self.mode_var = tk.StringVar()
        ttk.Combobox(
            row,
            textvariable=self.mode_var,
            values=list(dm.MODE_NAMES.values()),
            state="readonly",
            width=18,
        ).pack(side="left", padx=4)
        ttk.Button(row, text="Set mode", command=self.set_mode).pack(side="left")
        ttk.Label(row, text="in RAM until saved", foreground="#666").pack(
            side="left", padx=6
        )

        row = ttk.Frame(ctl)
        row.pack(fill="x", pady=(0, 6))
        for text, fn in (
            ("Enable", self.enable),
            ("Disable", self.disable),
            ("Hold here", self.hold_here),
            ("Clear error", self.clear_error),
            ("Set zero…", self.set_zero),
        ):
            ttk.Button(row, text=text, command=fn).pack(side="left", padx=(0, 4))

        box = ttk.LabelFrame(ctl, text="Command", padding=6)
        box.pack(fill="x", pady=4)
        on = self.on_command_edit
        # One turn either way: across the motor's whole ±4π range a pixel of
        # slider was 0.1 rad, and catching the handle moved the target by that.
        self.s_p = Slider(box, 0, "Position, rad", -math.pi, math.pi, 0.01, on)
        self.s_v = Slider(box, 1, "Speed, rad/s", -50, 50, 0.05, on)
        self.s_kp = Slider(box, 2, "Kp", 0, 50, 0.5, on)
        self.s_kd = Slider(box, 3, "Kd", 0, 5, 0.01, on)
        self.s_t = Slider(box, 4, "Torque, Nm", -5, 5, 0.01, on)
        self.s_vlim = Slider(box, 5, "Speed limit, rad/s", 0, 50, 0.05, on)
        self.s_ilim = Slider(box, 6, "Current limit, p.u.", 0, 1, 0.01, on)
        self.sliders = {
            "p": self.s_p,
            "v": self.s_v,
            "kp": self.s_kp,
            "kd": self.s_kd,
            "t": self.s_t,
            "vlim": self.s_vlim,
            "ilim": self.s_ilim,
        }
        wave = ttk.Frame(box)
        wave.grid(row=7, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.wave_label = ttk.Label(wave, text="Wave on position")
        self.wave_label.pack(side="left")
        self.wave_var = tk.StringVar(value="constant")
        ttk.Combobox(
            wave, textvariable=self.wave_var, values=WAVES, state="readonly", width=9
        ).pack(side="left", padx=4)
        ttk.Label(wave, text="amplitude").pack(side="left")
        self.amp_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(
            wave, from_=0, to=50, increment=0.05, textvariable=self.amp_var, width=7
        ).pack(side="left", padx=4)
        ttk.Label(wave, text="Hz").pack(side="left")
        self.freq_var = tk.DoubleVar(value=0.5)
        ttk.Spinbox(
            wave, from_=0.05, to=20, increment=0.05, textvariable=self.freq_var, width=6
        ).pack(side="left", padx=4)
        for var in (self.amp_var, self.freq_var):
            var.trace_add("write", lambda *_: self.on_command_edit())
        self.wave_var.trace_add("write", lambda *_: self.on_wave_kind())

        box = ttk.LabelFrame(ctl, text="Never send more than", padding=6)
        box.pack(fill="x", pady=4)
        self.limit_vars = {}
        for i, (key, text, hi, step) in enumerate(
            (
                ("torque", "|torque|, Nm", 5, 0.05),
                ("kp", "Kp", 500, 1),
                ("kd", "Kd", 5, 0.05),
                ("speed", "|speed|, rad/s", 50, 0.5),
                ("current", "current, p.u.", 1, 0.05),
            )
        ):
            var = tk.DoubleVar(value=getattr(self.limits, key))
            ttk.Label(box, text=text).grid(row=i // 3, column=(i % 3) * 2, sticky="e")
            ttk.Spinbox(
                box, from_=0, to=hi, increment=step, textvariable=var, width=6
            ).grid(row=i // 3, column=(i % 3) * 2 + 1, padx=(2, 10), pady=2)
            var.trace_add("write", lambda *_, k=key, v=var: self._set_limit(k, v))
            self.limit_vars[key] = var

        self.readout = ttk.Label(
            ctl, text="", font=("Consolas", 12), justify="left", padding=(0, 8)
        )
        self.readout.pack(fill="x")
        self.warning = ttk.Label(
            ctl, text="", foreground="#b71c1c", wraplength=520, justify="left"
        )
        self.warning.pack(fill="x")

        self.canvas = tk.Canvas(tab, bg="white", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True, padx=(10, 0))

    def _build_registers(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text="Registers")
        cols = ("addr", "name", "value", "rw", "range", "text")
        heads = ("Addr", "Name", "Value", "R/W", "Range", "Meaning")
        widths = (50, 90, 150, 40, 110, 280)
        frame = ttk.Frame(tab)
        frame.pack(fill="both", expand=True)
        self.regs = ttk.Treeview(frame, columns=cols, show="headings")
        for c, h, w in zip(cols, heads, widths):
            self.regs.heading(c, text=h)
            self.regs.column(
                c, width=w, anchor="w" if c in ("name", "text", "range") else "center"
            )
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.regs.yview)
        self.regs.configure(yscrollcommand=scroll.set)
        self.regs.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")
        for r in dm.REGISTERS:
            self.regs.insert(
                "",
                "end",
                iid=str(r.rid),
                values=(
                    f"0x{r.rid:02X}",
                    r.name,
                    "",
                    "RW" if r.writable else "R",
                    r.span,
                    r.text,
                ),
            )
        self.regs.bind("<<TreeviewSelect>>", self.on_register_select)

        row = ttk.Frame(tab, padding=(0, 6))
        row.pack(fill="x")
        ttk.Button(row, text="Read all", command=self.read_all).pack(side="left")
        self.reg_name = ttk.Label(row, text="(pick a register)", width=16)
        self.reg_name.pack(side="left", padx=(16, 4))
        self.reg_value = tk.StringVar()
        ttk.Entry(row, textvariable=self.reg_value, width=14).pack(side="left")
        ttk.Button(row, text="Write", command=self.write_register).pack(
            side="left", padx=4
        )
        ttk.Button(row, text="Save to flash…", command=self.save_flash).pack(
            side="right"
        )

        box = ttk.LabelFrame(tab, text="Give this motor a new CAN ID", padding=6)
        box.pack(fill="x")
        ttk.Label(box, text="New CAN ID").pack(side="left")
        self.new_id = tk.IntVar(value=2)
        ttk.Spinbox(box, from_=1, to=15, textvariable=self.new_id, width=4).pack(
            side="left", padx=4
        )
        ttk.Label(box, text="feedback (master) ID").pack(side="left", padx=(12, 0))
        self.new_master = tk.IntVar(value=0x12)
        ttk.Spinbox(box, from_=0, to=0x7FF, textvariable=self.new_master, width=5).pack(
            side="left", padx=4
        )
        ttk.Button(box, text="Change and save…", command=self.change_id).pack(
            side="left", padx=12
        )
        ttk.Label(
            box,
            text="IDs 1-15: feedback names a motor by the low four bits of its ID.",
            foreground="#666",
        ).pack(side="left")
        self.new_id.trace_add("write", lambda *_: self._suggest_master())

    def _build_system(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text="System")
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=(0, 6))
        for text, fn in (
            (f"IMU on, {IMU_HZ} Hz", self.imu_on),
            ("IMU off", self.imu_off),
            ("Reset IMU", self.imu_reset),
        ):
            ttk.Button(row, text=text, command=fn).pack(side="left", padx=(0, 4))
        ttk.Label(
            row,
            text="the robot's controller, its buses, the battery and the IMU",
            foreground="#666",
        ).pack(side="left", padx=8)
        self.system = ttk.Label(
            tab, text="", font=("Consolas", 11), justify="left", anchor="nw"
        )
        self.system.pack(fill="both", expand=True)
        self.poweroff_btn = ttk.Button(
            row, text="Power off\u2026", command=self.power_off
        )
        self.poweroff_btn.pack(side="right")

    # -- plumbing --------------------------------------------------------------

    def post(self, fn) -> None:
        self.inbox.put(fn)

    def say(self, text: str) -> None:
        """Log from any thread."""
        self.post(lambda: self.log(text))

    def log(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{time.strftime('%H:%M:%S')}  {text}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def job(self, fn, done=None, failed=None) -> None:
        """Run fn on the worker thread, and done(result) back on this one, or
        failed(error) if it raised."""

        def run():
            try:
                result = fn()
            except Exception as e:  # a failed job must not take the worker with it
                if failed is None:
                    self.say(f"error: {e}")
                else:
                    # Bound now: Python unbinds e when the except block ends.
                    self.post(lambda e=e: failed(e))
                return
            if done is not None:
                self.post(lambda: done(result))

        self.jobs.submit(run)

    def label(self, bus: dm.Bus, m: dm.Motor | int) -> str:
        """How the log names a motor: its CAN ID, and its bus on the robot."""
        can_id = m if isinstance(m, int) else m.can_id
        return str(can_id) if bus.name == DEBUGGER_BUS else f"{bus.name}{can_id}"

    def target(self) -> tuple[dm.Bus, dm.Motor, Command] | None:
        """The selected motor, its bus and its command, if one is selected."""
        if self.selected is None:
            return None
        bus = self.buses.get(self.selected[0])
        m = None if bus is None else bus.motors.get(self.selected[1])
        cmd = self.commands.get(self.selected)
        if bus is None or m is None or cmd is None:
            return None
        return bus, m, cmd

    def motor(self) -> dm.Motor | None:
        t = self.target()
        return None if t is None else t[1]

    def command(self) -> Command | None:
        return None if self.selected is None else self.commands.get(self.selected)

    def is_disabled(self, bus: dm.Bus, m: dm.Motor) -> bool:
        cmd = self.commands.get(key_of(bus, m))
        if (cmd and cmd.active) or (m.feedback and m.feedback.enabled):
            self.log(f"motor {self.label(bus, m)}: disable it first")
            return False
        return True

    def link_error(self) -> str | None:
        if self.lost:
            return self.lost
        for bus in self.buses.values():
            if bus.error:
                return bus.error
        return None

    def _set_rate(self) -> None:
        try:
            rate = clamp(float(self.rate_var.get()), 20, 500)
        except (tk.TclError, ValueError):
            return
        if self.streamer:
            self.streamer.rate = rate

    def _set_limit(self, key: str, var: tk.DoubleVar) -> None:
        try:
            value = float(var.get())
        except (tk.TclError, ValueError):
            return
        if value >= 0:
            setattr(self.limits, key, value)

    def _suggest_master(self) -> None:
        try:
            self.new_master.set(int(self.new_id.get()) + 0x10)
        except (tk.TclError, ValueError):
            pass

    # -- connection ------------------------------------------------------------

    def refresh_ports(self) -> None:
        ports = dm.list_adapters()
        values = [
            f"{dev}  {desc}" + ("  [DAMIAO debugger]" if ours else "")
            for dev, desc, ours in ports
        ]
        robots = [
            f"robot  {r}" + (f"   ({ROBOTS[r]})" if r in ROBOTS else "")
            for r in self.robots
        ]
        self.port_box.configure(values=values + robots)
        if not self.port_var.get():
            # The debugger if one is plugged in, and the robot if not: the
            # other serial ports are anything at all, Bluetooth's among them.
            debuggers = [v for v, (_, _, ours) in zip(values, ports) if ours]
            self.port_var.set((debuggers + robots)[0])

    def toggle_connect(self) -> None:
        if self.buses:
            self.disconnect()
        else:
            self.connect()

    def connect(self) -> None:
        text = self.port_var.get().strip()
        if not text:
            self.log("nothing to connect to")
            return
        devices = {dev for dev, _, _ in dm.list_adapters()}
        first = text.split()[0]
        if first in devices:
            self.connect_debugger(first)
        else:
            robot = text[len("robot") :].strip() if first == "robot" else text
            # Without the note on what it is, if it carries one.
            self.connect_robot(re.sub(r"\s+\([^()]*\)$", "", robot))

    def connect_debugger(self, port: str) -> None:
        try:
            self.debugger = dm.Debugger(port)
        except (serial.SerialException, OSError) as e:
            messagebox.showerror("Could not open the debugger", str(e))
            return
        self.buses = {DEBUGGER_BUS: dm.Bus(self.debugger, DEBUGGER_BUS)}
        self.connected(port)

    def connect_robot(self, address: str) -> None:
        """Connects on the worker thread: through SSH, finding the Pi can take
        ten seconds, and the window stays alive meanwhile."""
        self.log(f"connecting to the robot at {address}…")
        self.connect_btn.configure(state="disabled")

        def work():
            robot = diag_client.Robot(
                address, name="motor_gui", streams=("can", "imu", "status", "log")
            )
            try:
                robot.take_control()
            except diag_client.RobotError:
                robot.close()
                raise
            return robot

        def failed(e):
            self.connect_btn.configure(state="normal")
            self.log(f"could not reach the robot: {e}")
            messagebox.showerror("Could not reach the robot", str(e))

        self.job(work, lambda robot: self.robot_connected(address, robot), failed)

    def robot_connected(self, address: str, robot: diag_client.Robot) -> None:
        self.connect_btn.configure(state="normal")
        self.robot = robot
        robot.on("stopped", self.on_stopped)
        robot.on(
            "link",
            lambda m: self.say(f"robot: controller {'up' if m['up'] else 'DOWN'}"),
        )
        robot.on("log", lambda m: self.say(f"robot: {m['text']}"))
        robot.on("imu", self.on_imu)
        self.buses = {name: dm.Bus(robot.can(name), name) for name in "ABC"}
        info = robot.info
        self.log(
            f"robot: {info.get('firmware', '?')} on the controller, "
            f"uid {info.get('uid', '?')}, reset by {info.get('reset', '?')}, "
            f"through {robot.where}"
        )
        if address not in self.robots:
            self.robots.insert(0, address)
        self.connected(address)

    def connected(self, where: str) -> None:
        self.lost = None
        self.streamer = Streamer(self)
        self._set_rate()
        self.streamer.start()
        self.connect_btn.configure(text="Disconnect")
        self.log(f"connected to {where}")
        self.scan()

    def disconnect(self) -> None:
        if not self.buses:
            return
        self.stop_all()
        if self.streamer:
            self.streamer.running = False
            self.streamer.join(timeout=1)
        for bus in self.buses.values():
            bus.close()
        if self.robot is not None:
            try:
                self.robot.release_control()
            except diag_client.RobotError:
                pass
            self.robot.close()
        self.buses, self.debugger, self.robot, self.streamer = {}, None, None, None
        self.selected = None
        self.imu.clear()
        self.tree.delete(*self.tree.get_children())
        self.connect_btn.configure(text="Connect")
        self.log("disconnected")

    def scan(self) -> None:
        buses = list(self.buses.values())
        if not buses:
            self.log("connect first")
            return
        if any(c.active for c in self.commands.values()):
            self.log("disable every motor before scanning")
            return
        try:
            last = int(self.scan_to.get())
        except (tk.TclError, ValueError):
            last = 16
        on = "" if len(buses) == 1 else f" on buses {', '.join(self.buses)}"
        self.log(f"scanning CAN IDs 1 to {last}{on}…")

        def work():
            found = []
            for bus in buses:
                for m in bus.scan(range(1, last + 1)):
                    v = bus.read(m.can_id, dm.RID["TIMEOUT"])
                    if v is not None:
                        m.registers[dm.RID["TIMEOUT"]] = v
                    found.append((bus, m))
            return found

        def done(found):
            for bus, m in found:
                self.commands.setdefault(key_of(bus, m), Command())
            if not found:
                s = self.robot.status if self.robot else None
                if self.robot is not None and not (s and s["link_up"]):
                    self.log(
                        "no motor answered, and the controller is not answering "
                        "diagd either: is it running firmware/diag?"
                    )
                else:
                    self.log(
                        "no motor answered: is it powered, and is CAN H/L connected?"
                    )
                return
            for bus, m in found:
                self.log(
                    f"motor {self.label(bus, m)}: master 0x{m.master_id:X}, "
                    f"{dm.MODE_NAMES.get(m.mode, m.mode)} mode, "
                    f"PMAX {m.pmax:g} rad, VMAX {m.vmax:g} rad/s, TMAX {m.tmax:g} Nm"
                )
            self.update_tree()
            if self.target() is None:
                bus, m = found[0]
                self.tree.selection_set(self.iid(bus, m.can_id))

        self.job(work, done)

    @staticmethod
    def iid(bus: dm.Bus | str, can_id: int) -> str:
        return f"{bus if isinstance(bus, str) else bus.name}:{can_id}"

    # -- the robot's own events, on its reader thread --------------------------

    def on_stopped(self, message: dict) -> None:
        # At once, before the streamer sends another command.
        for cmd in self.commands.values():
            cmd.active = False
        why = {
            "asked": "it was asked to",
            "silent": "it stopped hearing from the Pi",
            "button": "the power button was held",
            "starting": "it has just started",
        }.get(message["why"], message["why"])
        self.say(f"robot: the controller stopped every motor: {why}")

    def on_imu(self, message: dict) -> None:
        report = message["report"]
        self.imu[report] = (message["t"], message["v"], message["status"])
        self.imu_counts.setdefault(report, deque(maxlen=200)).append(message["t"])

    # -- driving ---------------------------------------------------------------

    def enable(self) -> None:
        t = self.target()
        if t is None:
            return
        bus, m, cmd = t
        fb = m.feedback
        if fb is None or time.monotonic() - fb.t > 0.5:
            self.log(
                f"motor {self.label(bus, m)}: no recent feedback, so not enabling it"
            )
            return
        if fb.fault:
            self.log(
                f"motor {self.label(bus, m)}: {fb.state_name}; clear the error first"
            )
            return
        if cmd.active:
            self.log(f"motor {self.label(bus, m)} is already enabled")
            return
        # Start from nothing, and say so before and after the enable, so that
        # whatever command the motor last held is never acted on.
        cmd.start_from(m, fb)
        self.load_motor()
        now = time.monotonic()
        cmd.t0 = cmd.enabled_at = now
        self.streamer.drive(bus, m, cmd, now)
        bus.enable(m)
        self.streamer.drive(bus, m, cmd, now)
        cmd.active = True
        self.log(
            f"motor {self.label(bus, m)} enabled in {dm.MODE_NAMES[m.mode]} mode, "
            "starting from rest at its present position"
        )

    def disable(self) -> None:
        t = self.target()
        if t is None:
            return
        bus, m, cmd = t
        cmd.active = False
        for _ in range(3):
            bus.disable(m)
        self.log(f"motor {self.label(bus, m)} disabled")

    def stop_all(self) -> None:
        for cmd in self.commands.values():
            cmd.active = False
        if not self.buses:
            return
        if self.robot is not None:
            # The controller's own stop, first: it throws away whatever is
            # queued for the buses and disables every motor it knows of.
            try:
                self.robot.stop()
            except diag_client.RobotError as e:
                self.log(f"STOP could not reach the robot: {e}")
        for bus in self.buses.values():
            try:
                bus.disable_everything()
            except LINK_ERRORS as e:
                self.log(f"STOP could not reach bus {bus.name}: {e}")
                return
        self.log("STOP: every motor disabled")

    def hold_here(self) -> None:
        m, cmd = self.motor(), self.command()
        if m is None or cmd is None or m.feedback is None:
            return
        cmd.p = m.feedback.pos
        cmd.wave, cmd.amp = "constant", 0.0
        self.load_motor()

    def clear_error(self) -> None:
        t = self.target()
        if t is None:
            return
        bus, m, _ = t
        bus.clear_error(m)
        self.log(f"motor {self.label(bus, m)}: clear error sent")

    def set_zero(self) -> None:
        t = self.target()
        if t is None or not self.is_disabled(t[0], t[1]):
            return
        bus, m, _ = t
        if not messagebox.askyesno(
            "Set zero",
            f"Make motor {self.label(bus, m)}'s present position its zero?\n\n"
            "This replaces the zero the motor holds.",
        ):
            return
        bus.set_zero(m)
        self.log(f"motor {self.label(bus, m)}: zero set at the present position")

    def set_mode(self) -> None:
        t = self.target()
        names = {v: k for k, v in dm.MODE_NAMES.items()}
        mode = names.get(self.mode_var.get())
        if t is None or mode is None or mode == t[1].mode:
            return
        bus, m, _ = t
        if not self.is_disabled(bus, m):
            return

        def done(echo):
            if echo != mode:
                self.log(f"motor {self.label(bus, m)}: mode change not confirmed")
                return
            m.mode = mode
            m.registers[dm.RID["CTRL_MODE"]] = mode
            self.log(
                f"motor {self.label(bus, m)}: now in {dm.MODE_NAMES[mode]} mode (RAM)"
            )
            self.load_motor()

        self.job(lambda: bus.write(m.can_id, dm.RID["CTRL_MODE"], mode), done)

    # -- the System tab, the robot's IMU ---------------------------------------

    def power_off(self) -> None:
        robot = self.robot
        if robot is None:
            self.log("connect to the robot before powering it off")
            return
        if not messagebox.askyesno(
            "Power off robot",
            "Stop every motor, shut down the Banana Pi, and turn the robot off?\n\n"
            "Use the physical power button to turn it on again.",
            parent=self,
        ):
            return
        self.poweroff_btn.configure(state="disabled")

        def work():
            robot.take_control()
            return robot.request("power.off", wait=15)

        def done(_):
            self.disconnect()
            self.poweroff_btn.configure(state="normal")
            self.log("power-off accepted: the robot is shutting down")

        def failed(error):
            self.poweroff_btn.configure(state="normal")
            self.log(f"power-off failed: {error}")

        self.job(work, done, failed)

    def imu_job(self, what: str, fn) -> None:
        robot = self.robot
        if robot is None:
            self.log("the System tab is the robot's: connect to it first")
            return
        self.job(lambda: fn(robot), lambda result: self.log(f"imu: {what}{result}"))

    def imu_on(self) -> None:
        def work(robot):
            granted = [
                robot.request("imu.enable", report=r, hz=IMU_HZ) for r in IMU_REPORTS
            ]
            return ", ".join(f"{g['report']} {g['hz']:g} Hz" for g in granted)

        self.imu_job("granted ", work)

    def imu_off(self) -> None:
        def work(robot):
            for r in IMU_REPORTS:
                robot.request("imu.enable", report=r, hz=0)
            return ""

        self.imu_job("reports off", work)

    def imu_reset(self) -> None:
        def work(robot):
            robot.request("imu.reset")
            return ""

        self.imu_job("reset sent", work)

    # -- registers -------------------------------------------------------------

    def update_registers(self) -> None:
        m = self.motor()
        for r in dm.REGISTERS:
            value = "" if m is None else m.registers.get(r.rid, "")
            if isinstance(value, float):
                text = f"{value:.6g}"
            elif isinstance(value, int):
                text = f"{value}  (0x{value:X})" if value > 9 else str(value)
                if r.name == "CTRL_MODE":
                    text = f"{value}  {dm.MODE_NAMES.get(value, '?')}"
                if r.name == "TIMEOUT" and value == 0:
                    text = "0  (off)"
            else:
                text = ""
            self.regs.set(str(r.rid), "value", text)

    def on_register_select(self, _event=None) -> None:
        sel = self.regs.selection()
        if not sel:
            return
        r = dm.REGISTER[int(sel[0])]
        self.reg_name.configure(text=r.name)
        m = self.motor()
        value = None if m is None else m.registers.get(r.rid)
        self.reg_value.set("" if value is None else f"{value:.6g}")

    def read_all(self) -> None:
        t = self.target()
        if t is None:
            return
        bus, m, _ = t

        def work():
            missed = 0
            for r in dm.REGISTERS:
                v = bus.read(m.can_id, r.rid)
                if v is None:
                    missed += 1
                else:
                    m.registers[r.rid] = v
            return missed

        def done(missed):
            self.update_registers()
            note = f", {missed} did not answer" if missed else ""
            self.log(f"motor {self.label(bus, m)}: registers read{note}")

        self.job(work, done)

    def write_register(self) -> None:
        t = self.target()
        sel = self.regs.selection()
        if t is None or not sel or not self.is_disabled(t[0], t[1]):
            return
        bus, m, _ = t
        r = dm.REGISTER[int(sel[0])]
        if not r.writable:
            self.log(f"{r.name} is read-only")
            return
        if r.name == "ESC_ID":
            self.log("use 'Give this motor a new CAN ID' to change ESC_ID")
            return
        if r.name == "can_br":
            self.log(
                "the CAN bit rate is not changed here: the debugger or the "
                "controller would lose the motor"
            )
            return
        text = self.reg_value.get().strip()
        try:
            value = float(text) if r.kind == "f" else int(text, 0)
        except ValueError:
            self.log(f"{text!r} is not a value for {r.name}")
            return
        if r.name == "CTRL_MODE" and value not in dm.MODE_NAMES:
            self.log("CTRL_MODE is 1 to 4")
            return
        if r.name == "MST_ID" and (why := self.feedback_clash(value, bus.motors)):
            self.log(why)
            return

        def done(echo):
            if echo is None:
                self.log(f"motor {self.label(bus, m)}: no answer writing {r.name}")
                return
            m.registers[r.rid] = echo
            if r.name in ("PMAX", "VMAX", "TMAX"):
                setattr(m, r.name.lower(), float(echo))
            elif r.name == "MST_ID":
                m.master_id = int(echo)
            elif r.name == "CTRL_MODE":
                m.mode = int(echo)
            self.log(
                f"motor {self.label(bus, m)}: {r.name} = {echo:.6g} (RAM until saved)"
            )
            self.load_motor()

        self.job(lambda: bus.write(m.can_id, r.rid, value), done)

    @staticmethod
    def feedback_clash(master: int, ids) -> str | None:
        """Why a feedback ID is unsafe beside motors at these CAN IDs, or None.

        Each CAN ID must have one sender, and a motor takes any frame whose low
        eight ID bits are its own as addressed to it.
        """
        if master == dm.CONFIG_ID:
            return "0x7FF is the ID the controller configures motors on"
        hit = sorted(i for i in ids if i & 0xFF == master & 0xFF)
        if hit:
            return (
                f"feedback ID 0x{master:X} would reach motor {hit[0]} as a command: "
                "a motor reads only the low 8 bits of an ID"
            )
        return None

    def save_flash(self) -> None:
        t = self.target()
        if t is None or not self.is_disabled(t[0], t[1]):
            return
        bus, m, _ = t
        if not messagebox.askyesno(
            "Save to flash",
            f"Store motor {self.label(bus, m)}'s present settings in its flash?\n\n"
            "The flash is good for about 10,000 writes.",
        ):
            return
        self.job(
            lambda: bus.save(m.can_id),
            lambda ok: self.log(
                f"motor {self.label(bus, m)}: "
                + ("settings saved to flash" if ok else "save not confirmed")
            ),
        )

    def change_id(self) -> None:
        t = self.target()
        if t is None or not self.is_disabled(t[0], t[1]):
            return
        bus, m, _ = t
        try:
            new_id, master = int(self.new_id.get()), int(self.new_master.get())
        except (tk.TclError, ValueError):
            return
        old = m.can_id
        if not 1 <= new_id <= 15 or not 0 <= master <= 0x7FF:
            self.log("the CAN ID is 1 to 15 and the master ID 0 to 0x7FF")
            return
        if new_id != old and new_id in bus.motors:
            self.log(f"motor {self.label(bus, new_id)} is already on the bus")
            return
        if why := self.feedback_clash(master, (set(bus.motors) - {old}) | {new_id}):
            self.log(why)
            return
        if not messagebox.askyesno(
            "New CAN ID",
            f"Give motor {self.label(bus, old)} CAN ID {new_id} and feedback ID "
            f"0x{master:X}, and save them to its flash?",
        ):
            return

        def work():
            answers = bus.read(new_id, dm.RID["ESC_ID"], tries=1) is not None
            if new_id != old and answers:
                return f"something already answers at {new_id}; nothing changed"
            if bus.write(old, dm.RID["MST_ID"], master) is None:
                return "no answer writing the master ID; nothing changed"
            m.master_id = master
            bus.write(old, dm.RID["ESC_ID"], new_id)
            # The new ID may hold at once or only after a restart: save at
            # whichever ID the motor answers to now.
            now = new_id if bus.read(new_id, dm.RID["ESC_ID"]) is not None else old
            saved = bus.save(now)
            bus.motors.pop(old, None)
            at_new = bus.probe(new_id) is not None
            at_old = old != new_id and bus.probe(old) is not None
            if not saved:
                return "the save was not confirmed; power-cycle and scan to see"
            if at_new:
                return f"saved; the motor answers at {new_id}"
            if at_old:
                return f"saved; it answers at {old} until it is power-cycled"
            return "saved, and it answers at neither ID; power-cycle it and scan"

        def done(result):
            self.log(f"motor {self.label(bus, old)}: {result}")
            for i in bus.motors:
                self.commands.setdefault((bus.name, i), Command())
            self.update_tree()
            if new_id in bus.motors:
                self.tree.selection_set(self.iid(bus, new_id))

        self.job(work, done)

    # -- selection -------------------------------------------------------------

    def on_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if sel:
            name, _, can_id = sel[0].partition(":")
            self.selected = (name, int(can_id))
        else:
            self.selected = None
        self.load_motor()

    def load_motor(self) -> None:
        """Point the Drive and Registers tabs at the selected motor."""
        m, cmd = self.motor(), self.command()
        if m is None or cmd is None:
            return
        self._loading = True
        try:
            self.mode_var.set(dm.MODE_NAMES.get(m.mode, ""))
            self.s_v.set_range(-m.vmax, m.vmax)
            self.s_t.set_range(-m.tmax, m.tmax)
            hi = 100.0 if m.mode == dm.HYBRID else m.vmax
            self.s_vlim.set_range(0, hi)
            for key, slider in self.sliders.items():
                slider.set(getattr(cmd, key))
            self.wave_var.set(cmd.wave)
            self.amp_var.set(cmd.amp)
            self.freq_var.set(cmd.freq)
            shown = {
                dm.MIT: {"p", "v", "kp", "kd", "t"},
                dm.POS_VEL: {"p", "vlim"},
                dm.VELOCITY: {"v"},
                dm.HYBRID: {"p", "vlim", "ilim"},
            }[m.mode]
            for key, slider in self.sliders.items():
                slider.show(key in shown)
            self.wave_label.configure(
                text="Wave on speed" if m.mode == dm.VELOCITY else "Wave on position"
            )
            self.new_id.set(m.can_id)
            self.new_master.set(m.master_id)
        finally:
            self._loading = False
        self.update_registers()

    def on_command_edit(self) -> None:
        cmd = self.command()
        if self._loading or cmd is None:
            return
        for key, slider in self.sliders.items():
            value = slider.get()
            if value is not None:
                setattr(cmd, key, value)
        for key, var in (("amp", self.amp_var), ("freq", self.freq_var)):
            try:
                setattr(cmd, key, max(0.0, float(var.get())))
            except (tk.TclError, ValueError):
                pass

    def on_wave_kind(self) -> None:
        cmd = self.command()
        if self._loading or cmd is None:
            return
        cmd.wave = self.wave_var.get()
        cmd.t0 = time.monotonic()

    # -- the periodic refresh --------------------------------------------------

    def tick(self) -> None:
        while True:
            try:
                fn = self.inbox.get_nowait()
            except queue.Empty:
                break
            fn()
        if self.buses and (error := self.link_error()):
            self.log(error)
            for cmd in self.commands.values():
                cmd.active = False
            self.disconnect()
        self.update_tree()
        self.update_readout()
        self._ticks += 1
        if self._ticks % 2 == 0:
            self.draw_plot()
        if self._ticks % 4 == 0:
            self.update_system()
        self.status.configure(text=self.status_text())
        self.after(50, self.tick)

    def status_text(self) -> str:
        if not self.buses:
            return "not connected"
        counts = "   ".join(
            f"{'' if name == DEBUGGER_BUS else name + ': '}sent {b.tx}  heard {b.rx}  "
            f"unmatched {b.unmatched}  late {b.late}"
            for name, b in self.buses.items()
        )
        rate = f"{self.streamer.rate:.0f} Hz to driven motors, {POLL_HZ} Hz polls"
        if self.debugger is not None:
            where = f"{self.debugger.port}   other {self.debugger.foreign}"
        else:
            s = self.robot.status if self.robot else None
            vbus = (
                f"battery {s['vbus']:.2f} V   "
                if s and s.get("vbus") is not None
                else ""
            )
            where = f"robot via {self.robot.where}   {vbus}"
        return f"{where}   {counts}   {rate}"

    def update_system(self) -> None:
        robot = self.robot
        if robot is None:
            self.system.configure(
                text="Connect to the robot (its address in the box above) to see "
                "its controller, buses, battery and IMU here."
            )
            return
        s, info = robot.status, robot.info
        lines = [
            f"controller  {info.get('firmware', '?')}, uid {info.get('uid', '?')}, "
            f"reset by {info.get('reset', '?')}"
        ]
        if info.get("last_crash"):
            lines.append(f"            last crash: {info['last_crash']}")
        if s is None:
            lines.append("no status from the controller yet")
            self.system.configure(text="\n".join(lines))
            return
        link, pi = s["link"], s["pi"]
        vbus = f"{s['vbus']:.2f} V" if s.get("vbus") is not None else "not read"
        lines += [
            f"            up {s['uptime']:.1f} s, link "
            f"{'up' if s['link_up'] else 'DOWN'}, through {robot.where}",
            f"power       HOLD {'high' if s['hold'] else 'low'}, button "
            f"{'down' if s['button'] else 'up'}"
            f"{', OFF asked for' if s['off'] else ''}"
            f"{', DEADMAN TRIPPED' if s['lost'] else ''}",
            f"battery     {vbus}",
            f"J5          the controller heard {link['frames']} "
            f"({link['crc_errors']} bad CRC, {link['uart_errors']} UART errors, "
            f"{link['dropped']} dropped for room); the Pi heard {pi['frames']} "
            f"({pi['crc_errors']} bad CRC)",
            f"control     {pi['control'] or 'nobody'}, {pi['clients']} client(s)",
            "",
        ]
        for name, b in s["buses"].items():
            lines.append(
                f"bus {name}       {b['state']:13s} TEC {b['tec']:3d} REC {b['rec']:3d}   "
                f"sent {b['tx']:8d}  not taken {b['tx_fail']:5d}   heard "
                f"{b['rx']:8d}  errors {b['rx_errors']:4d}  dropped "
                f"{b['rx_drop'] + b['queue_drop']}"
            )
        lines += [
            "",
            f"IMU         {'found' if s['imu_found'] else 'not found'}, "
            f"{s['imu']['packets']} packets, {s['imu']['errors']} errors",
        ]
        now = time.monotonic()
        for report in IMU_REPORTS:
            if report not in self.imu:
                continue
            t, v, status = self.imu[report]
            stamps = self.imu_counts[report]
            hz = (len(stamps) - 1) / (stamps[-1] - stamps[0]) if len(stamps) > 1 else 0
            old = "  (old)" if now - t > 0.5 else ""
            if report == "game":
                roll, pitch, yaw = euler(*v[:4])
                values = f"roll {roll:6.1f}°  pitch {pitch:6.1f}°  yaw {yaw:6.1f}°"
            elif report == "gyro":
                values = "  ".join(f"{math.degrees(x):7.2f}" for x in v) + "  °/s"
            else:
                values = "  ".join(f"{x:7.3f}" for x in v) + "  m/s²"
            lines.append(
                f"  {report:9s} {values}   accuracy {status}, {hz:5.1f} Hz{old}"
            )
        self.system.configure(text="\n".join(lines))

    def state_text(self, key: tuple[str, int], m: dm.Motor) -> str:
        cmd, fb = self.commands.get(key), m.feedback
        stale = fb is None or time.monotonic() - fb.t > STALE_S
        if cmd and cmd.active:
            if stale:
                return "NO FEEDBACK"
            if not fb.enabled:
                return f"{fb.state_name} (told on)"
        if fb is None:
            return "?"
        return fb.state_name + ("  (old)" if stale else "")

    def update_tree(self) -> None:
        motors = {
            self.iid(bus, i): (bus, m)
            for bus in self.buses.values()
            for i, m in sorted(bus.motors.items())
        }
        for iid in self.tree.get_children():
            if iid not in motors:
                self.tree.delete(iid)
        for iid, (bus, m) in motors.items():
            fb = m.feedback
            values = (
                bus.name,
                m.can_id,
                f"0x{m.master_id:X}",
                dm.MODE_NAMES.get(m.mode, m.mode),
                self.state_text(key_of(bus, m), m),
                f"{math.degrees(fb.pos):.1f}" if fb else "",
                f"{fb.vel:.2f}" if fb else "",
                f"{fb.torque:.2f}" if fb else "",
                fb.t_mos if fb else "",
                fb.t_rotor if fb else "",
            )
            if self.tree.exists(iid):
                self.tree.item(iid, values=values)
            else:
                self.tree.insert("", "end", iid=iid, values=values)

    def update_readout(self) -> None:
        t = self.target()
        if t is None:
            self.readout.configure(text="no motor selected")
            self.warning.configure(text="")
            return
        bus, m, cmd = t
        fb = m.feedback
        if fb is None:
            self.readout.configure(text=f"motor {self.label(bus, m)}: no feedback yet")
        else:
            self.readout.configure(
                text=(
                    f"position {fb.pos:+8.3f} rad  {math.degrees(fb.pos):+7.1f}°\n"
                    f"speed    {fb.vel:+8.3f} rad/s\n"
                    f"torque   {fb.torque:+8.3f} Nm\n"
                    f"MOSFET {fb.t_mos:3d} °C   winding {fb.t_rotor:3d} °C\n"
                    f"state    {self.state_text(key_of(bus, m), m)}"
                )
            )
        notes = []
        if m.registers.get(dm.RID["TIMEOUT"]) == 0:
            notes.append(
                "TIMEOUT is 0 (off): if this program stops while the motor is "
                "enabled, the motor keeps its last command. Esc still disables it."
                + (
                    " On the robot the Pi and the controller stop it too, unless "
                    "its bus itself is cut."
                    if self.robot is not None
                    else ""
                )
            )
        lim = self.limits
        asked = self.asked_speed(m, cmd)
        if asked > lim.speed:
            notes.append(
                f"Speed held to {lim.speed:g} rad/s by the |speed| box under "
                "'Never send more than'."
            )
        cap = m.speed_cap
        if cap is not None and min(asked, lim.speed) > cap:
            notes.append(
                f"The motor holds itself to {cap:.1f} rad/s: MAX_SPD "
                f"{m.registers[dm.RID['MAX_SPD']]:g} at the rotor, over gearing "
                f"{m.registers[dm.RID['Gr']]:g}. Raise MAX_SPD to go faster."
            )
        if lim.speed > m.vmax:
            notes.append(
                f"VMAX is {m.vmax:g} rad/s: past ±{m.vmax:g} the motor's speed "
                f"reading wraps round to the other sign ({m.vmax + 2:g} reads as "
                f"{m.vmax + 2 - 2 * m.vmax:g}). Raise VMAX on the Registers tab "
                "before driving faster."
            )
        self.warning.configure(text="\n\n".join(notes))

    @staticmethod
    def asked_speed(m: dm.Motor, cmd: Command) -> float:
        """The fastest the sliders ask this motor to turn, before any limit."""
        if m.mode == dm.MIT:
            return abs(cmd.v)
        if m.mode == dm.VELOCITY:
            return abs(cmd.v) + (cmd.amp if cmd.wave != "constant" else 0.0)
        return cmd.vlim

    def draw_plot(self) -> None:
        c = self.canvas
        c.delete("all")
        t = self.target()
        w, h = c.winfo_width(), c.winfo_height()
        if t is None or w < 50 or h < 50:
            return
        bus, m, cmd = t
        now = time.monotonic()
        start = now - PLOT_WINDOW_S
        with bus.history_lock:
            hist = [f for f in m.history if f.t >= start]
            trace = [s for s in cmd.trace if s[0] >= start]
        vel_mode = m.mode == dm.VELOCITY
        strips = (
            (
                "position, rad",
                [(f.t, f.pos) for f in hist],
                None if vel_mode else trace,
            ),
            ("speed, rad/s", [(f.t, f.vel) for f in hist], trace if vel_mode else None),
            ("torque, Nm", [(f.t, f.torque) for f in hist], None),
        )
        left, right, top, gap = 54, 10, 40, 26
        sh = (h - top - 6 - gap * (len(strips) - 1)) / len(strips)
        for i, (label, data, ref) in enumerate(strips):
            y0 = top + i * (sh + gap)
            c.create_text(left, y0 - 4, text=label, anchor="sw", fill="#333")
            c.create_rectangle(left, y0, w - right, y0 + sh, outline="#ccc")
            values = [v for _, v in data] + [v for _, v in (ref or ())]
            if not values:
                continue
            lo, hi = min(values), max(values)
            span = max(hi - lo, 0.05)
            mid = (hi + lo) / 2
            lo, hi = mid - span * 0.6, mid + span * 0.6
            c.create_text(left - 4, y0, text=f"{hi:.2f}", anchor="ne", fill="#666")
            c.create_text(left - 4, y0 + sh, text=f"{lo:.2f}", anchor="se", fill="#666")

            def xy(points, y0=y0, lo=lo, hi=hi):
                step = max(1, len(points) // int(w - left - right))
                out = []
                for t, v in points[::step]:
                    out.append(left + (t - start) / PLOT_WINDOW_S * (w - left - right))
                    out.append(y0 + sh - (v - lo) / (hi - lo) * sh)
                return out

            if ref and len(ref) > 1:
                c.create_line(*xy(ref), fill="#e67e22", width=1.5, dash=(4, 2))
            if len(data) > 1:
                c.create_line(*xy(data), fill="#1565c0", width=1.5)
        c.create_text(
            w - right,
            4,
            anchor="ne",
            fill="#666",
            text="blue: reported   orange: commanded   last 10 s",
        )

    def on_close(self) -> None:
        self.stop_all()
        time.sleep(0.05)
        self.disconnect()
        self.jobs.shutdown(wait=False, cancel_futures=True)
        self.destroy()


def euler(i: float, j: float, k: float, r: float) -> tuple[float, float, float]:
    """Roll, pitch and yaw in degrees from a quaternion, as sbc/imu_test.py has it."""
    roll = math.atan2(2 * (r * i + j * k), 1 - 2 * (i * i + j * j))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (r * j - k * i))))
    yaw = math.atan2(2 * (r * k + i * j), 1 - 2 * (j * j + k * k))
    return tuple(math.degrees(a) for a in (roll, pitch, yaw))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--robot",
        action="append",
        help="the robot's diagd, as host:port or ssh:DEST; offered in the box "
        "first, before $DIAG_ROBOT and the Banana Pi",
    )
    args = ap.parse_args()
    env = os.environ.get("DIAG_ROBOT")
    app = App([*(args.robot or []), *([env] if env else [])])
    if args.robot:
        app.port_var.set(f"robot  {args.robot[0]}")
    app.mainloop()


if __name__ == "__main__":
    main()
