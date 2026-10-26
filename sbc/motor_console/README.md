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
The installer enables diagd at boot so the physical button can request shutdown
without a browser. Launching the web server manually does not start diagd.
Console restarts leave diagd running. Stop diagd before flashing the controller.

## Using it

Opening the console automatically acquires control when it is available and
scans IDs 1–16 on buses A, B and C. Pick a motor. If another browser or the
desktop GUI owns control, the console waits for it to finish. The page
renders state pushed by the server ten times per second; application heartbeats
travel back every 100 ms. Actions are acknowledged by the server, and motor
readouts come from actual feedback.

- **Drive:** enable/disable, hold position, clear error, set zero, all four modes,
  constant/sine/square setpoints, numeric command fields, command rate and limits,
  side-by-side position/speed/torque plots and winding/MOSFET temperatures.
  The Drive operating-mode selector writes `CTRL_MODE` in RAM while disabled;
  use Save to flash in Registers to persist it. Valid command edits apply
  immediately, including command limits, with no Apply buttons. MIT defaults
  to Kp 1 and Kd 0.05 as starting values to tune for the attached load.
- **Registers:** read all, write RAM, save flash, change CAN and feedback IDs.
  Writes, saves and zeroing require fresh disabled feedback. Bit rate is blocked;
  CAN ID changes use the dedicated action and check for address collisions.
- **System:** controller identity, reset/crash details, link counters, power
  state, battery voltage, bus errors, IMU values/rate/accuracy/age, IMU report
  controls/product/reset/diagnostic snapshot, I²C transactions and robot power-off.
- **CAN & log:** live traffic, bus/ID filters (use `0x123` for hex), pause,
  clear, and bounded JSONL export of the latest 2,000 events.
- **Wi-Fi:** scan nearby APs, connect to open or password-protected personal
  networks, reuse saved credentials and forget saved networks. Successful
  connections are saved in Netplan; the preferred SSID survives browser and
  BPI restarts. WPA/WPA2 and WPA3 personal are supported where the adapter
  supports them; enterprise networks need their additional settings configured
  outside this page. A failed connection restores the previous network.

Each browser has its own diagd client. The daemon arbitrates control with other
browsers and the desktop GUI. Other clients may always stop motors. Scans and
register reads require control because they send CAN frames. Only the browser
holding control polls discovered motors. Browser reconnects clear commands and
automatically acquire control and scan again when the controller is available.

**Power off robot** acquires control when confirmed, including when this browser's
previous ownership has expired. Another client's ownership is still respected.
It stops motors and asks the daemon for orderly Linux shutdown; the installed
final shutdown hook cuts the power latch afterward. On success the page shows
shutdown progress; refresh after physically turning the robot on again.
The confirmed action refreshes browser liveness after the native dialog pauses
JavaScript timers; this never resumes motor commands stopped by the watchdog.

With the diagnostics firmware, holding the physical button for half a second
stops the motors and requests the same Linux shutdown. The controller holds power
until the final shutdown hook releases the latch. Holding the button for eight
seconds forces off; if shutdown never completes, the controller releases its
hold after 20 seconds. Release the button for power to go off. If diagd has been
explicitly stopped, only the forced-off fallbacks are available.

The MCU heartbeat LED goes dark when shutdown is requested. The BPI heartbeat
LED goes dark when Linux accepts shutdown. Both the physical button and console
power-off do this; UART heartbeats and the safety watchdog continue until halt.
The M4 Zero v2's red status LED uses the inverted dark level, and diagd restores
its heartbeat when starting so the shutdown state does not persist after boot.
Startup also restores the heartbeat trigger's `invert=1` setting, keeping the
original brief flashes against a dark background.

Timing on 25 October 2026: the BPI reached the filesystem-unmount stage in
10.55 seconds including the two-second acknowledgement delay. An earlier run
exposed a 49-second systemd timer tolerance delay; the scheduler now explicitly
sets `AccuracySec=100ms`. The late power-cut hook ran and the owner confirmed
the robot switched off; Wi-Fi was already down before its final timing packet.
The physical-button test reached the same stage in 8.07 seconds, with both
heartbeat LEDs stopping and the robot subsequently power-cycled by the owner.

Older daemons can serve the core console without the optional `imu.diag` stream.
IMU diagnostic snapshots and robot power-off require a daemon that provides
those operations; an older daemon reports an unsupported operation when asked.

Motor streaming runs on the BPI at 200 Hz by default, independently of browser
rendering. Enabling discards the old command and starts at rest at the current
position; MIT preserves the selected gains (initially Kp 1, Kd 0.05) and starts
with zero feedforward torque. Limits and MIT spring reach are
clamped on the server. A motor fault or feedback older than 300 ms disables that
motor. **STOP ALL** and Escape use a separate action path that bypasses long scans
or register reads. The daemon and controller retain their own watchdogs.

Closing or hiding a controlling tab releases control and stops its motors.
Missing browser application heartbeats for 500 ms also releases control. A
visible tab automatically reacquires available control; it never resumes motion.
Timing depends on OS scheduling, so physical
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
uv run tools/test_console_wifi.py
node --check sbc/motor_console/console.js
```

The integration tests use the real WebSocket server, local API and simulated
controller. They need port 7700 to be free, refuse to use an existing daemon,
and stop their simulator when finished.

## Wi-Fi helper

The installer also runs `sbc/install_console_wifi.sh`. For an existing console,
copy `console_wifi.py` and `install_console_wifi.sh` beside `motor_console.py`
and run `sudo bash sbc/install_console_wifi.sh` (adjust the path on the BPI).
This installs a root-owned helper in `/usr/lib/bipedal-console/`, a sudo rule
allowing only that helper without arguments, and a supplicant startup hook that
restores the preferred network. It does not restart Wi-Fi during installation.
The interface is the BPI's `wlan0`, managed by Netplan, networkd and
wpa_supplicant; NetworkManager is not needed.

Passwords travel in the helper's stdin and never appear in command arguments,
API replies or browser storage. Netplan files and the preference file are
root-only. Changes preserve unrelated Netplan settings and existing APs;
original files have a root-only `.yaml.console-backup` copy. The last forgotten
AP is replaced by a disabled, unconnectable internal entry because Netplan
requires an AP definition to keep the supplicant available for future scans.

Connection jobs run independently of the browser socket, so changing networks
can complete after the page disconnects. Reopen the console from the new
network using `bpi-m4zero.local:8080` or its new IP. Switching or forgetting a
network releases this browser's motor control and stops its commands.
