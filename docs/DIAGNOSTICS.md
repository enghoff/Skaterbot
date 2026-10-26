# The diagnostics link

How a program on the Banana Pi, or on a PC through it, sees and drives
everything the controller board is wired to: the three CAN buses and the six
motors on them, the IMU, the battery bus and the power switch. It is the robot's
own replacement for DAMIAO's USB-to-CAN debugger on the bench, and
`bench/motor_gui.py` drives the motors through it with every feature it has
through the debugger.

**On the robot, 2026-10-23**, `firmware/diag` was flashed through J5 and the
link came up at 1.5 Mbaud: 243 messages to the controller and 125 back with no
CRC failure and no UART error either way. Its stop as it started reached both
wheel motors on bus C, and a scan through it found them at IDs 1 and 2. Buses A
and B acknowledged nothing, having no motors on them, and nothing answered on
I2C at any address. No motor has been enabled through it yet. The firmware is
58 KB of flash and 24 KB of RAM, clean under clippy.

**IMU on the robot, 2026-10-25:** direct I2C reads answered at 0x4B while
automatic discovery still reported no IMU. The INA226 discovery loop was
sending its one-byte register request to the IMU's SHTP address. Excluding
0x4A and 0x4B from that register scan, rebuilding and flashing made discovery
succeed. The IMU returned product 10004148, version 3.2.13, build 6. A ten-second
test received 654 accelerometer reports (62.5 Hz granted), 501 gyro, 501 game
rotation and 500 gravity reports (50 Hz granted), with zero IMU errors and
zero UART or CRC errors. The INA226 remains absent. Do not strap an INA226
to either reserved IMU address on this shared bus.

Other checks have run against `sbc/diag_sim.py`, a software controller with
simulated motors behind it:

- the GUI, driven by a script, through every feature it has -- scan, enable,
  MIT and velocity mode, a sine, Esc, read all, write, save to flash, a new CAN
  ID, set zero, the IMU -- 24 checks of 24, on the PC and again from the PC
  through SSH and Wi-Fi to the daemon on the Banana Pi;
- the same GUI through a fake of DAMIAO's debugger, 9 of 9, so the bench's
  own path still works;
- the watches below, 12 of 12;
- one motor driven at 200 Hz for three minutes through SSH and Wi-Fi: 36 000
  frames out, 36 000 answers back, nothing stopped.

The framing is held to the same known-answer bytes in Rust
(`cargo test -p diag_link`) and in Python (`python3 sbc/diag_link.py`), neither
written from the other's output. What only the hardware can settle is listed at
the end.

## The three hops

```text
 motor_gui, scripts           Banana Pi                     controller board
 ------------------   JSON   -----------------   binary   ---------------------
 diag_client.py  <--lines--> sbc/diagd.py   <--frames-->  firmware/diag
 (PC or Pi)        TCP 7700   owns UART4      J5, 1.5 Mbaud  FDCAN1-3, I2C1, J7
```

**The controller** runs `firmware/diag`. It forwards every frame it hears on
any bus, puts on a bus any frame it is given, polls the IMU and passes on its
packets whole, reads the battery bus, and reports its own health ten times a
second. It knows nothing of DAMIAO's protocol beyond how to switch a motor off.

**The Pi** runs `sbc/diagd.py`, the only program that opens UART4 while it
runs. It turns the controller's frames into JSON, decodes the IMU's reports,
matches register replies to the requests that asked for them, and serves any
number of clients on `127.0.0.1:7700`. One client at a time holds control; the
others watch.

**A client** is `sbc/diag_client.py`, a library and a command line. It reaches
the daemon over TCP, or from a PC through SSH (`ssh -W`), which needs no port
opened on the Pi and no second password. `bench/motor_gui.py` uses it.

## What keeps the motors safe

A diagnostics link puts motor commands on a wireless network, and every way that
network can fail has to end with the motors off. Three watches, each at the hop
it can see:

| Who | Watches | After | Then |
|---|---|---|---|
| diagd | the client holding control: closed, or silent | 0.5 s | stops every motor, and takes control back |
| controller | the Pi: no valid frame on the link | 0.3 s | stops every motor |
| controller | the power button: the half-second press | at once | stops every motor |

The client library pings every 0.1 s and the daemon every 50 ms, so a link that
is only slow does not trip either. Against the simulator, a controlling client
that went quiet had every motor stopped 0.41 s later, one whose connection
closed at once, and the controller stopped everything 0.31 s after the Pi went
quiet. A client that gives up control has every motor stopped as it does.

**Stopping** is the controller's own act: it throws away every frame the Pi had
queued for a bus before the stop, then sends DAMIAO's disable to every motor ID
it has addressed and to IDs 1 to 16, on all four modes' frame IDs, three times,
on all three buses -- the bench GUI's Esc, done where nothing can delay it.
Frames the Pi sends after a stop are kept and go after it. A client can ask for
a stop at any time without holding control, and the GUI's Esc does, as well as
disabling over the bus itself. Every client is told of every stop, and why.

**The controller also stops everything as it starts**, because a motor enabled
by an image that has since reset is holding a command nobody is sending any more.

What this cannot do: a motor that has lost its CAN bus entirely hears no
disable, and holds its last command unless its own TIMEOUT register is set.
That register is the fourth watch, and it is still 0 on the motors read so far.

## The controller's link, J5

USART1 to UART4 at **1 500 000 baud**, 8N1. 115 200 carries about 570 CAN frames
a second each way, and the GUI driving six motors at 200 Hz wants 1 200 each
way. 1.5 Mbaud is exact on the Pi's 24 MHz UART clock and 0.3 % off on the
STM32's 170 MHz, and carries about 7 000.

Every message is COBS-encoded and ends with a zero byte, so a receiver that
loses its place finds the next message at the next zero. Inside the COBS is a
type byte, a body, and a CRC-16/CCITT-FALSE (polynomial 0x1021, initial 0xFFFF)
of the two, little-endian. A message whose CRC fails is dropped and counted: a
bit flipped in a motor's position target is exactly what the CRC is there to
stop. All numbers are little-endian.

The Pi sends:

| Type | Name | Body |
|---|---|---|
| 0x01 | HELLO | nothing; the controller answers with INFO |
| 0x02 | PING | nothing. Every valid message counts as one |
| 0x03 | STOP | nothing; stop every motor |
| 0x04 | SHUTDOWN | nothing; Linux has accepted shutdown: stop motors, latch OFF, stop the MCU heartbeat LED and start the grace period unless already running |
| 0x10 | CAN_SEND | bus u8 (0 A, 1 B, 2 C), flags u8 (bit 0 extended ID), id u32, then 0 to 8 data bytes |
| 0x20 | IMU_WRITE | one SHTP packet, header included, written to the IMU as it stands |
| 0x21 | I2C | tag u8, address u8, read length u16, then the bytes to write |

The controller sends:

| Type | Name | Body |
|---|---|---|
| 0x81 | INFO | text, one `key=value` a line: firmware, protocol, uid, reset cause, last crash, what it found |
| 0x82 | STATUS | every 100 ms; the layout is below |
| 0x83 | STOPPED | why u8: 0 the Pi asked, 1 the Pi fell silent, 2 the power button, 3 starting |
| 0x90 | CAN_RECV | time u32 µs, bus u8, flags u8, id u32, then the data |
| 0xA0 | IMU_PACKET | time u32 µs, then one SHTP packet as the IMU sent it |
| 0xA1 | I2C_RESULT | tag u8, status u8 (0 done, 1 refused, 2 timed out, 3 failed), then what was read |
| 0xE0 | LOG | time u32 µs, then a line of text |

STATUS is fixed at 127 bytes: time u32 µs; uptime u32 ms; flags u8 (bit 0 HOLD
high, 1 button down, 2 off asked for, 3 link lost, 4 IMU found, 5 INA226 found);
the battery bus u16 in mV; what the controller made of the Pi's bytes -- whole
messages, CRC failures, messages too long, UART errors, messages that held
together but made no sense -- and messages to the Pi dropped for want of room,
u32 each; IMU packets and IMU errors, u32 each; then for each bus its state u8 (0 error active, 1 error
passive, 2 bus off), transmit and receive error counters u8 each, a pad byte,
and frames sent, frames that no node took within 5 ms, frames received, receive
errors, frames dropped for want of room to the Pi and frames dropped for want of
room in the bus's own queue, u32 each.

Times are the controller's microsecond clock, which wraps every 71.6 minutes;
the daemon unwraps it.

The IMU is the BNO085 on I2C1 at 0x4A or 0x4B, and the battery monitor the INA226
between 0x40 and 0x4F, both found by asking, and looked for again once a second
while either is missing or after it stops answering; the controller polls the
IMU every 2 ms, because J6 does not carry its interrupt line. Anything the IMU says goes to
the Pi whole, and anything the Pi writes goes to the IMU whole, so the Pi can
use any part of SH-2 without the firmware changing.

The controller automatically requests acceleration, calibrated gyro, gravity
and game rotation reports at 100 Hz when it discovers the IMU and whenever the
IMU reports a completed reset. No GUI or client command is needed after power-on.
The IMU can grant a nearby supported rate. The GUI can still change rates or
turn reports off; off lasts until the next IMU reset or controller restart.
The controller assigns outgoing SHTP sequence numbers to both its defaults
and host IMU commands so they share one sequence per channel.

Verified on 2026-10-25 after flashing and restarting the controller: an
observer sent no enable commands and received 647 acceleration reports and
500 each of gyro, gravity and game rotation in five seconds, with zero IMU
errors. Explicitly switching reports off stopped them. Reset recovery
verification was interrupted when the Pi became unreachable.

Later cold-start testing on 2026-10-25 did **not** reproduce reliable IMU
startup: the controller found 0x4B but received only three startup packets.
Product ID, Get Feature and Report Errors requests answered, while Set Feature
requests left the requested interval at zero and produced no input reports.
The first 4096 bytes of controller flash matched `diag-imu-autostart.elf`,
ruling out an older installed image in that run. Temporary 100 kHz and polled
write experiments did not restore reporting; the 400 kHz async configuration
was restored. The cause remains unresolved pending IMU supply measurements
and a decoded I2C capture. The earlier warm-run success does not validate
reliable cold-start behavior.

A subsequent test added a 300 ms quiet period at MCU startup and after
host-requested IMU reset, deferring rediscovery and setup until afterward.
The flashed image reports `imu_startup=quiet-300ms` in INFO. It built and
passed clippy and the project check, but did not recover reports from the
currently failing module: reset and report-enable requests still yielded no
input reports. This timing change is not a demonstrated fix for the fault.

Subsequent instrumented testing found invalid `ff ff ff ff` headers, read
timeouts, and a relapse after about 102 seconds with SCL low and the host I2C
peripheral BUSY. The host service gap reached 369 ms, exceeding its 300 ms
deadman. The current `imu_bus=clean-boundaries-v1` image uses bounded polled
transactions for both devices, clears old STOP/error flags and stale RX/TX
data between transactions, waits asynchronously for bus idle, yields between
missing-device probes, and resets the host I2C peripheral after a timeout.
It rejects malformed headers during discovery and polling. This host reset
does not power-cycle or physically reset the IMU. Hardware test results and
remaining limits are recorded in [the investigation](IMU_TROUBLESHOOTING_2026-10-25.md).

The additive `IMU_DIAG` controller message (`0xA2`, once a second) leaves the
127-byte STATUS and protocol version unchanged. Version 2 is 24 little-endian
u32 values, in this order:

```text
version header_reads empty_reads header_errors payload_errors write_errors
nack timeouts bus_errors arbitration other_errors invalid_lengths resets
input_packets last_input_ms ina_errors searches max_i2c_us max_service_gap_us
last_header last_error_ms pins isr host_resets
```

Version 1 omits `host_resets`; the daemon accepts both lengths. `resets` counts
received IMU reset-complete packets; `host_resets` counts I2C peripheral resets.
The maximum durations are since controller startup, in microseconds. Input and
error timestamps use the controller's wrapping u32 millisecond clock. `pins`
has SCL in bit 0 and SDA in bit 1; `3` means both were high when sampled.
`isr` is the raw STM32 I2C1 ISR; `last_header` packs the four received bytes
little-endian. Empty headers are normal polling, not measurement packets.

`imu.diagnostics` reads cached counters, feature responses, internal error
records and the last 32 control packets. It takes no control and sends no bus
commands. The GUI shows transport counters and input age in System. For a
bounded read-only flight recording on the Pi:

```sh
python3 ~/imu_watch.py --seconds 300 --output ~/imu-traces/session.jsonl
```

This saves one-second summaries and recent raw packets around a stall; it
never enables reports, resets the module or takes motor control.

## The daemon's API

The System panel's **Power off...** button confirms the action, acquires
control, and sends `power.off`. The daemon stops all motors, blocks further
control commands and queues normal Linux shutdown after two seconds. The
client disconnects after acknowledgement. In simulation this only stops
the simulated robot; the host computer remains on.

Install the power-cut hook once on the Pi with
`bash ~/setup_poweroff.sh`, with `robot_poweroff.py` and `flash_mcu.py` beside
it. This copies root-owned files to `/usr/lib/systemd/system-shutdown/` and
`/usr/local/lib/bipedal/`; it does not turn anything off. The daemon needs
passwordless sudo for `/usr/bin/systemd-run` (the current admin account has
passwordless sudo). The hook runs only for `poweroff`, after systemd has
stopped services and unmounted or made filesystems read-only. It holds the
MCU in reset using the existing J5 NRST connection and lowers SBC HOLD on
header pin 12, releasing both power-latch holds. Reboot and halt do not cut
the latch. Start the robot again with its physical power button.

This uses systemd's final shutdown hook stage:
https://www.freedesktop.org/software/systemd/man/253/systemd-poweroff.service.html

The diagnostics firmware also uses this sequence for the physical button. A
half-second press latches OFF and stops motors, while MCU HOLD remains high.
`diagd` notices OFF in controller status, blocks further control and runs the
same shutdown callback without needing a client's ownership. Failed scheduling
is retried once a second. The final Linux hook resets the MCU and drops SBC HOLD
after filesystems are safe. The controller's SysTick independently forces its
HOLD low after a continuous eight-second press, or 20 seconds after the request;
the pressed button itself keeps the latch on until released. Other firmware
images retain the original immediate HOLD release. `diagd` must be running for
orderly shutdown; the console installer now enables it at boot, while explicit
Start/Stop still work for flashing and diagnostics.

Measured on 2026-10-25: 10.55 s from API request to the filesystem-unmount stage,
including the two-second acknowledgement delay. The final GPIO hook cut power
and the owner restarted the robot. Its final UDP timestamp was unavailable once
Wi-Fi stopped. An earlier 53.27 s run included 49.31 s waiting for systemd's timer
to fire: its default accuracy was one minute. The timer now sets
`AccuracySec=100ms`; the 20 s MCU fallback leaves margin beyond the observed
shutdown, and is not a guarantee for every possible stalled service.

Shutdown stops the MCU heartbeat LED as soon as OFF is latched. Once Linux
accepts the shutdown, the installed hook's `--stop-heartbeat` mode sets any
active BPI heartbeat LED's trigger to `none` and brightness to zero, without
changing power GPIOs. For software power-off, diagd then sends SHUTDOWN to
firmware advertising `shutdown_led=1`; this does not restart an already running
grace period. Diagnostic PINGs and the MCU watchdog continue until Linux halts.
The M4 Zero v2's red status LED is physically dark at brightness 1 despite its
device-tree polarity, so the hook inverts only that LED on that model. The
diagd service restores its heartbeat trigger on startup. The physical-button
test reached the filesystem-unmount stage in 8.07 s and the owner power-cycled
the robot afterward; both heartbeat LEDs stopped on the shutdown request.

One JSON object a line, both ways, on `127.0.0.1:7700`. A request with a `req`
is answered with the same `req` and `"ok": true` or `"ok": false, "error": ...`;
one without is not answered. (`id` is a CAN ID wherever it appears.) Everything else the daemon sends is an event,
carrying `"ev"`, to the streams the client subscribed to.

| Request | Control | Does |
|---|---|---|
| `hello` `name` | | the controller's INFO, the daemon's settings, and who holds control |
| `subscribe` `streams` | | any of `can`, `imu`, `imu.raw`, `imu.diag`, `status`, `log`; `status` and `log` by default |
| `ping` | | nothing: the keepalive |
| `status` | | the latest status, decoded |
| `control` `take` | | take control, or with `take: false` give it back |
| `stop` | no | stop every motor |
| `can.send` `bus` `id` `data` `ext` | yes | one frame. `bus` is `A`, `B` or `C`, `data` hex |
| `can.request` ... `expect` `timeout` | yes | one frame, answered by the first frame on the same bus whose data starts with `expect`, within `timeout` (0.02 s if not given) |
| `imu.enable` `report` `hz` | yes | ask the IMU for a report at a rate; `hz` 0 stops it |
| `imu.reset`, `imu.info` | yes | reset the IMU; its product ID and firmware |
| `imu.diagnostics` | no | cached firmware counters, features, internal errors and recent control packets |
| `imu.write` `channel` `data` | yes | one SHTP packet's payload, on a channel |
| `i2c` `addr` `write` `read` | yes | one transaction on I2C1 |

A register reply matched to a `can.request` goes to the client that asked, as
its answer, and to every other client as an ordinary frame. Matching at the
daemon is what lets a client over Wi-Fi wait a second for an answer the
controller had in a millisecond.

The events:

| Event | Carries |
|---|---|
| `can` | `bus`, `t`, `id`, `ext`, `data` |
| `imu` | `t`, `report` (`accel`, `gyro`, `mag`, `linear`, `rotation`, `gravity`, `game`), `status` 0-3, `v` in SI units |
| `imu.raw` | `t`, `data`: one SHTP packet |
| `imu.diag` | decoded `IMU_DIAG` fields; also cached under `status.imu_diag` |
| `status` | the controller's STATUS decoded, with the daemon's own counters and the link's state |
| `log` | `t`, `text`: from the controller or the daemon |
| `stopped` | `why`: every motor has just been told to stop |

`t` is seconds of the controller's uptime. The client library moves every `t`
onto its own `time.monotonic()`, by the smallest gap it has seen between a
message's controller time and its arrival, so that a frame delayed on Wi-Fi is
plotted when it happened rather than when it arrived.

## Using it

```text
# on the Pi, once the controller runs firmware/diag
python3 flash_mcu.py diag.elf --listen 0
start_diagd                              # diagd, detached, logging to diagd.log
stop_diagd                               # stopped, motors first, before flashing

# the same from the PC
ssh admin@bpi-m4zero start_diagd

# anywhere the daemon can be reached
python3 diag_client.py status            # one status, decoded
python3 diag_client.py candump           # every frame on every bus
python3 diag_client.py scan              # which motor IDs answer, on each bus
python3 diag_client.py imu --hz 100      # the IMU's reports
python3 diag_client.py stop              # every motor off

# from the PC
uv run bench/motor_gui.py --robot ssh:admin@<the Pi>
```

`diag_client.py` takes `--robot` the same way: `host:port` is TCP, and
`ssh:destination` goes through `ssh -W`, with the key and options the PC's own
SSH configuration gives that destination; options can go before it,
`ssh:-i ~/.ssh/key admin@<the Pi>`. On Windows it uses Windows' own OpenSSH.

**Without hardware**, `python sbc/diagd.py --sim` runs the daemon against
`sbc/diag_sim.py`: a controller with two simulated DM-J3507-2EC on each bus,
answering register reads, writes and saves, enabling, disabling, setting zero
and following all four modes, plus an IMU that reports gravity. The GUI drives
it exactly as it drives the robot.

**Flashing** needs UART4 too. The daemon, `flash_mcu.py` and `wheel_check.py`
all open it through `flash_mcu.py`'s Port, which takes an exclusive lock on it,
so whichever comes second refuses to start rather than both reading the same
wire. Stop the daemon first. Once the controller runs `firmware/diag`,
`flash_mcu.py --listen` hears nothing it can print, since the image talks at
1.5 Mbaud in frames; `--listen 0` and then the daemon is the way to see it.

## What only the hardware can settle

- **1.5 Mbaud on J5, under load.** It has carried a few hundred messages
  without error, not yet a stream at 200 Hz. If it will not, 750 000 is the
  next exact rate on both ends and carries about 3 500 frames a second, which
  still holds the GUI at 200 Hz on six motors.
- **The IMU, by polling.** Tested on J6 on 2026-10-25: empty polls return zero
  length and all four default reports stream. Intermittent stalls required the
  host transaction fixes above. Repeated cold starts, signal waveforms and
  extended operation with the INA226 reconnected remain to be validated.
- **Three buses at once.** Bus C carries frames both ways through `diag`;
  buses A and B and their transceivers have carried nothing yet, since no motor
  is on them. Each counted receive errors only while the controller was trying
  to send to it -- 2 011 and 1 873 after one scan -- which is its own frames
  going unacknowledged, retried for 5 ms each, and not noise.
- **The controller's own watches.** The stop, the deadman and the button are
  the firmware's, and only the simulator's copies of them have been timed.
- **I2C.** The carrier has detected INA226 at 0x40 and BNO085 at 0x4B. The
  battery-monitor PCB is currently removed for isolation; the latest host
  recovery validation therefore covers the IMU-only bus. The user measured
  3.299 V at the IMU and confirmed the carrier's 4.7 kΩ pull-ups fitted.

## Wi-Fi, measured 2026-10-23

The Pi's Wi-Fi power saving was already off. **On the first access point the
link stalled for seconds at a time** -- twice, frames stopped reaching the Pi
between one and thirty seconds into a 200 Hz stream, the daemon stopped the
motors and took control back, as it should, and SSH gave the connection up
after 6 s. **On the second**, 36 000 frames at 200 Hz over three minutes all came back, the median
gap between answers was nothing and the 99.9th percentile 110 ms, but four gaps
passed 250 ms and one reached 515 ms. That is the daemon's half-second watch,
and a gap a little longer stops every motor. That is the safe way to fail, and
it is still an interruption: a bench session that must not be interrupted wants
a wired link to the Pi, which on the M4 Zero means a USB Ethernet adapter.
