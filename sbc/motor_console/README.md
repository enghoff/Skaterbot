# BPI motor diagnostics console

Run from a full checkout on the Banana Pi (including `bench/damiao.py`):

```bash
sudo bash sbc/install_motor_console.sh
```

Open `http://<BPI address>:8080/` from a browser on the local network. The
installer enables `motor-console.service` at boot. It needs Python 3.11 or newer
and installs Armbian's `python3-aiohttp` and `python3-serial` packages. For a
manual launch, use `python3 sbc/motor_console.py`. Check service output with
`journalctl -u motor-console -n 60`; restart after an update with
`sudo systemctl restart motor-console`.

The installed BPI is `bpi-m4zero`, currently at `192.168.1.89`; its console is
`http://bpi-m4zero.local:8080/` (or `http://192.168.1.89:8080/`). Avahi advertises
the `.local` name. Its console files are in `/home/admin/bipedal-console/`, with
the existing diagnostics helpers linked from `/home/admin` so it uses the same
daemon, log and start/stop scripts as the desktop GUI.

The console listens on the LAN, with no login: use it on the robot's trusted
local network. Anybody who can open it can drive or power off the robot. The
diagnostics API stays on `127.0.0.1:7700`; there are no remote addresses, SSH,
serial ports or connection settings in the page. `--listen` and `--port` configure
the web server only. Cross-origin browser WebSocket requests are refused.

The web server runs independently of diagd. **Start diagd** and **Stop diagd**
run the existing scripts beside `diagd.py`, as the service user. Startup failures
are reported in the page; UART and firmware details are in `sbc/diagd.log`.
Starting the web server does not automatically start diagd. Console restarts
leave diagd running. Stop diagd before flashing the controller.

## Using it

Take control, then scan IDs 1–16 on buses A, B and C. Pick a motor. The page
renders state pushed by the server ten times per second; application heartbeats
travel back every 100 ms. Actions are acknowledged by the server, and motor
readouts come from actual feedback.

- **Drive:** enable/disable, hold position, clear error, set zero, all four modes,
  constant/sine/square setpoints, numeric command fields, command rate and limits,
  position/speed/torque plots and winding/MOSFET temperatures. Change mode through
  `CTRL_MODE` in Registers. Commands are applied explicitly with **Apply command**.
- **Registers:** read all, write RAM, save flash, change CAN and feedback IDs.
  Writes, saves and zeroing require fresh disabled feedback. Bit rate is blocked;
  CAN ID changes use the dedicated action and check for address collisions.
- **System:** controller identity, reset/crash details, link counters, power
  state, battery voltage, bus errors, IMU values/rate/accuracy/age, IMU report
  controls/product/reset/diagnostic snapshot, I²C transactions and robot power-off.
- **CAN & log:** live traffic, bus/ID filters (use `0x123` for hex), pause,
  clear, and bounded JSONL export of the latest 2,000 events.

Each browser has its own diagd client. The daemon arbitrates control with other
browsers and the desktop GUI. Other clients may always stop motors. Scans and
register reads require control because they send CAN frames. Only the browser
holding control polls discovered motors. Browser reconnects clear commands and
require taking control and scanning again.

Older daemons can serve the core console without the optional `imu.diag` stream.
IMU diagnostic snapshots and robot power-off require a daemon that provides
those operations; an older daemon reports an unsupported operation when asked.

Motor streaming runs on the BPI at 200 Hz by default, independently of browser
rendering. Enabling discards the old command and starts at rest at the current
position; MIT starts with zero gains and torque. Limits and MIT spring reach are
clamped on the server. A motor fault or feedback older than 300 ms disables that
motor. **STOP ALL** and Escape use a separate action path that bypasses long scans
or register reads. The daemon and controller retain their own watchdogs.

Closing or hiding a controlling tab releases control and stops its motors.
Missing browser application heartbeats for 500 ms also releases control. A
reconnect never resumes motion. Timing depends on OS scheduling, so physical
hardware still needs bench verification. MIT's torque limit bounds the spring
and feedforward separately; damping can add torque, as in the desktop GUI.

## Local simulation and checks

```powershell
uv run sbc/motor_console.py --sim --listen 127.0.0.1
```

Open `http://127.0.0.1:8080/` and press **Start diagd**. In simulation mode,
Start/Stop manages only a simulator launched by this console; it will not
terminate an unrelated daemon. Real robot power-off is simulated too.

```text
uv run --with aiohttp --with pyserial tools/test_motor_console.py
node --check sbc/motor_console/console.js
```

The integration tests use the real WebSocket server, local API and simulated
controller. They need port 7700 to be free, refuse to use an existing daemon,
and stop their simulator when finished.
