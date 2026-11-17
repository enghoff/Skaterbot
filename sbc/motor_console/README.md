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
  Set zero acts immediately on the selected motor, preserving its enabled
  state and the other motors' streams. It clears that motor's position,
  velocity, torque feedforward and waveform setpoints, confirms the new origin
  from fresh motor feedback, then refreshes the command fields and plot history.
  If zero cannot be confirmed, only the selected motor is disabled and the
  console reports the failure. There is no blocking zero-confirmation dialog
  to interrupt browser heartbeats, and no action asks with the browser's own
  confirm box: it stops the heartbeat while open, and half a second without
  one releases control, so the confirmed action was refused. The console asks
  in a dialog of its own instead.
- **Registers:** read all, write RAM, save flash, change CAN and feedback IDs.
  Writes and saves require fresh disabled feedback. Bit rate is blocked;
  CAN ID changes use the dedicated action and check for address collisions.
  Typing a new CAN ID fills in the feedback ID as CAN ID + 0x10, which can
  still be edited before saving. A change waits for a running scan instead of
  being refused, and the selection follows the motor to its new ID. Each
  browser keeps its own motor list, so a console rescans whenever it takes
  control, and a scan drops motors that no longer answer.
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
- **Controller:** find, pair and forget Bluetooth game controllers, see what the
  connected one is asking for, and set what a stick's end means. See
  [Game controller](#game-controller).

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

## Game controller

The console reads the first game controller Linux offers whether or not a page
is open, and sends what it asks for to diagd fifty times a second. It moves nothing
unless something is running a policy that listens, as `balance.py --drive` and
`launcher.py` do. No button on the controller stops the motors, because that would
drop the robot: letting go only stops the driving.

| On the controller | Does |
|---|---|
| Right trigger | Forward, as far as it is pulled: letting go brings the speed to zero |
| Left trigger | Back, the same |
| Right stick, left and right | Turn |
| D-pad, up and down | Leg height |
| Bottom face button (A, Cross) | Jump |

The turn, D-pad and jump are the MuJoCo driver's. The speed limits start at the
top of what the robot's driving policy was trained on, 0.5 m/s and 1.5 rad/s. The
page can lower them, and a restart puts them back rather than keeping what somebody
last set. That policy cannot jump, so the jump button only counts for now. A controller stops counting as soon as Linux removes it,
as switching it off does, or after 3 s without a single event, which is the only
sign of one carried out of range until Bluetooth's own timeout. A trigger held hard
against its stop sends nothing either, so after 3 s it has to be let go of and pulled
again. What the firmware
must do with all this is in
[POLICY_INTERFACE.md](../../docs/POLICY_INTERFACE.md#the-operators-command).

The installer runs `sbc/install_console_bluetooth.sh`. For an existing console,
run that as root once, with the new files in place, and restart the console. It
installs BlueZ and adds the service user to the `bluetooth` and `input` groups, so
the console needs no helper running as root and no Python package beyond its own.
It also keeps the adapter on at boot, so that a controller reconnects with no page
open, and asks for a 2 s link timeout where the default is 20 s, on classic Bluetooth
only: it does nothing for a low-energy controller, as the Xbox ones are. The Pi as it
stood on 2026-11-04 already had BlueZ, the groups and the adapter on, and pairing and
driving input work without this.

The Pi's kernel has no drivers for particular controllers, so most reach it
through the generic one, which reports buttons in a different order and has a
PlayStation controller's triggers where its own driver has the right stick.
`gamepad.py`'s `layout_of` allows for that. A stick also counts only once it has
been seen in its middle since driving began, so a stick already pushed, or a
trigger taken for one, asks for nothing.

**On the robot, 2026-11-04, with no real controller.** Bluetooth comes up under
the Pi's image: a BCM4345C0 radio, Bluetooth 5.0, with BlueZ 5.82. A 12 s scan from
this console worked, and left the adapter not discoverable and not pairable. Wi-Fi
lost nothing during it, though its round trip to the access point went from 7 ms on
average and 32 at worst to 18 and 260. A virtual controller made through
`/dev/uinput` was read by the running console: its command reached diagd and went
no further, the controller's count of messages making no sense staying at 0, and
the stop button it had then stopped the motors at the real controller.

On a PC, pairing and forgetting ran against the real `bluetoothctl` 5.72 talking to
python-dbusmock's copy of BlueZ, and a simulated controller that takes DRIVE
received what the sticks asked for.

**On the robot, 2026-11-04, with a real Xbox Wireless Controller** (045E:0B20,
firmware 5.23). It has paired from test scripts and, since 2026-11-05, **from this
page**, in 9 and 63 connection attempts, staying connected for the 90 s it was watched.
Another (C0:D6:D5:EF:99:F0, 045E:0B13) advertises itself as a gamepad and gives no name
until paired, and is listed as an unnamed controller. A test script paired it on the 14th
try, it had an input device 1.1 s later and kept it for the 60 s watched; it has not yet
been paired from this page, and none of its controls has been pressed and read. A third
(40:8E:2C:42:E2:45, also 045E:0B13) pairs and does not work: see below. The first one's
buttons were read one at a time, which is where
`layout_of`'s Xbox line comes from. Three things were found:

- BlueZ refuses this controller's pairing if no agent is registered, however it
  looks ("No agent available for request type 2", then AuthenticationFailed).
  Pairing therefore keeps a `bluetoothctl` open as the default agent.
- Most connection attempts fail, and why is not known: 160 of 168 traced made a link
  nothing from the controller reached the host on, ending after six connection events,
  0.33 s at 48.75 ms, with "Connection Failed to be Established". For about its first 10 s after switch-on the controller sends only an
  advertisement with the HID service; once its pairing button is held it sends Swift
  Pair beacons as well, three to each HID one. 4 of 114 worked after a beacon and 4 of
  54 after the HID one, too few to say either matters. Bluetooth shares its chip with
  Wi-Fi, which is plausible as a cause and has not been tested. So pairing holds one
  agent and a scan open and tries until one lands, which has taken 1, 2, 9, 10, 23,
  14, about 22 and 63 tries, the last 42 s of the 60 s it allows.
- 40:8E:2C:42:E2:45 pairs and then fails. It publishes preferred connection parameters of 332.5
  to 500 ms, BlueZ's GAP plugin loads them, the kernel applies them to the live link,
  and each setup request takes about a second. The controller ended the link 14 s after
  pairing with the report map unread, so no input device was made (one trace,
  2026-11-05; why it ends the link is not known). The other 045E:0B13 publishes 7.5 ms and
  works, so the product number does not settle which a controller does. Whether the slow
  link is the cause is untested: stopping that update, or correcting it at once, on this
  controller would show it. Stopping it needs a change to the Bluetooth service on the
  robot.
- The page calls a controller connected only once the kernel has an input device for
  its address. Before 2026-11-05 it went by `Connected: yes`, which is only a link, and
  its message stayed up after the link had gone.
- A pairing can lose its link at once. From this page on 2026-11-05 the keys were
  exchanged after 15 s of tries, the controller then fell silent, and the link ended
  0.4 s later under the 420 ms timeout a link starts with; three script pairings kept
  it long enough for the controller to ask for 7.5 ms and a 3 s timeout. Pairing
  therefore goes on connecting for 30 s and reports it if the controller never does.
- One script pairing vanished from the Pi within about 15 s. A later one that vanished
  was an Unpair command, which only Forget sends, so this may have been the same; its
  trace ended too soon to say.

Still to be seen:

- that a pairing stays beyond the few minutes it has been watched;
- which way the controls go on a real controller: the right trigger should be forward
  and the right stick to the left a positive turn, read off the Forward and Turn readings;
- whether a paired controller reconnects by itself when switched on, which it did
  once, 5 s after dropping;
- why the link dropped by itself that once, and how long a controller carried out
  of range goes on being believed;
- whether 3 s of silence ever cuts in on a thumb holding a stick at its end;
- how Wi-Fi fares with a controller connected, rather than a scan running.

```text
uv run tools/test_gamepad.py
sudo python3 tools/test_gamepad_linux.py    # on Linux; on the Pi too, without dbusmock
```

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
