# BNO085 reporting failure: investigation and online findings

Date: 2026-10-25 (Asia/Calcutta)

Resolution reported: 2026-10-26 (Asia/Calcutta)

## Current conclusion

**Resolved on the assembled robot:** the owner confirmed that removing the
carrier's two **4.7 kΩ I2C pull-up resistors, R1 and R2**, fixed the IMU
reporting problem. Leave R1/R2 unpopulated for this hardware configuration.
This outcome was reported on 2026-10-26; the removal date was not specified.

The logs below document the investigation before that hardware correction.
The IMU answered at **0x4B**, including product-ID, Get Feature and Report
Errors requests, while measurement reports failed intermittently or did not
start. Earlier software changes produced temporary recovery but did not
establish a complete fix.

Host transaction cleanup, bounded transfers, malformed-header rejection and
diagnostic counters remain in the firmware. They are retained robustness and
observability changes; the owner-confirmed resolution is removal of R1/R2.
The electrical mechanism and the sensor's internal error tuple were not
characterized by the recorded tests.

## Hardware and connection

- Module: 7Semi BNO085 Nano breakout, identified in project records as ES-12234.
- Controller: WeAct STM32G474 on the carrier, running `firmware/diag`.
- Bus: I2C1, SCL on PA15 and SDA on PB7; normal configuration is 400 kHz.
- Battery monitor: INA226, subsequently detected at 0x40 on the same bus.
- Host path: motor GUI -> Pi diagnostics daemon -> controller -> IMU.

The photographed cable connects as follows. These colours apply to this cable,
not to a general wire-colour convention.

| Wire | IMU signal | Carrier |
|---|---|---|
| Black | SCL | J6-1 |
| Yellow | GND | J6-2 |
| Blue | 3V3 | J6-3 |
| Red | SDA | J6-6 |

J6-4 (INT) and J6-5 (RST) are unused. JP1 2-3 selects 3.3 V.
There is no physical IMU reset connection through the four-wire cable.
See [carrier wiring](CARRIER.md) and the
[connector investigation](../exports/imu-research/connector-identification.md).

During the earlier investigation, the user measured **3.299 V directly between
blue and yellow**, confirmed both carrier 4.7 kΩ pull-ups R1/R2 fitted, and
removed the power-monitoring PCB for isolation. That PCB measured 10 kΩ from
VCC to each I2C signal. Removing it left the carrier's external pull-ups fitted.
These measurements establish
the DC supply and fitted pull-ups, not startup transients or signal rise time.
That recovery test used the IMU-only bus; INA226 was correctly absent.
The subsequent confirmed fix was to remove the carrier's R1/R2 pull-ups.

## Observations from the robot

In the failing state the GUI showed `IMU found, 3 packets, 0 errors`.
Those packets were startup traffic, not a continuing measurement stream.

Direct requests returned:

| Request or observation | Result |
|---|---|
| Product ID | Part 10004148, version 3.2.13, build 6 |
| Get Feature for calibrated gyro | Reply received; report interval zero |
| Set Feature / report enable | No granted-rate response or input reports in the failing runs |
| Report Errors | An internal error record, followed by the end-of-queue marker |
| Subsequent Report Errors queries | End-of-queue marker with no further error records |
| INA226 manufacturer ID | `5449` (TI) at 0x40 |

The controller's flash was checked through the ROM bootloader without erasing:
the first 4096 bytes matched `diag-imu-autostart.elf` and differed from the
older `diag.elf` and `diag-imu-fix.elf`. This distinguished the installed
autostart image from those older candidates in that run.

The Pi's network connection was intermittent during investigation, and it
rebooted during an earlier test. Those events interrupted diagnostics; they
have not been established as the cause of the IMU reporting failure.

## Captured internal error

Raw SHTP packet, in hexadecimal:

```text
14 80 02 05  f1 00 01 00 00 00 00 04 02 00 00 00 0a 00 00 00
```

The four-byte SHTP header is followed by a Report Errors command response:

| Field | Value | Interpretation supported by public documentation |
|---|---|---|
| Report ID | 0xF1 | Command response |
| Command | 0x01 | Report Errors |
| Severity (R0) | 0 | Most severe category in CEVA's public driver header |
| Error sequence (R1) | 0 | Error sequence number |
| Source (R2) | 4 | Chip-level executable |
| Error (R3) | 2 | Specific meaning not verified |
| Module (R4) | 0 | Specific meaning not verified |
| Code (R5) | 0 | Specific meaning not verified |

The remaining bytes are reserved in the public response layout. Do not assign
a diagnostic meaning to the `0a` in that reserved area without vendor evidence.

The GUI's IMU error counter records controller-side communication/packet-read
failures. It does **not** incorporate the sensor's internal error queue, so
`0 errors` in the GUI does not contradict this record. A later empty queue
does not establish that measurement reporting recovered.

The positive device error value **2** must not be confused with
`SH2_ERR_BAD_PARAM = -2`, which is a separate host-library return code.

## Changes and tests so far

| Change or test | Observed outcome |
|---|---|
| Remove carrier R1/R2, the two 4.7 kΩ I2C pull-ups | Owner confirmed on 2026-10-26 that this fixed the IMU reporting problem. This is the resolved hardware configuration. |
| Exclude 0x4A/0x4B from the INA226 register scan | Discovery and streaming succeeded in earlier runs. Committed as `4c0f256`. The previous scan sent register-style commands to the SHTP IMU. |
| Reacquire GUI control when an IMU button is pressed | Fixed the separate `take control first` rejection after client timeout. Does not explain the later failure with direct diagnostic clients. |
| Automatically request accel, gyro, gravity and game rotation at 100 Hz | One five-second observer-only run received 647 accel reports and 500 of each other report, with zero controller IMU errors. Later cold starts failed. |
| Software reset over SHTP executable channel 1 | Command submission succeeded, but the failing module did not resume measurement reporting. |
| Explicit sensor-hub initialization command | Did not restore reports in the failing run. |
| Slow I2C to 100 kHz with a longer timeout | Did not restore reports; experiment reverted. |
| Use a polled IMU write instead of DMA | Did not restore reports; experiment reverted. |
| Add a 300 ms quiet period at startup and after software reset | Flashed and tested; did not restore reports from the currently failing module. Not a demonstrated fix. |

The earlier quiet-period image identifies itself with
`imu_startup=quiet-300ms` in INFO. It retains 400 kHz and asynchronous I2C
writes. Firmware build, clippy and the project check passed, but these software
checks do not validate sensor operation.

The GUI's `reset sent` message confirms submission, not a confirmed sensor
reset. Software reset leaves the 3.3 V supply applied. It is not a physical
reset or a power cycle.

## Instrumented host I2C investigation

Firmware now reports header/payload/write failures separately, NACK, timeout,
bus/arbitration errors, invalid headers, input age, sensor and host resets,
maximum I2C call time, maximum supervisor service gap, line levels and raw ISR.
The daemon separately retains internal sensor errors and feature responses;
`imu.diagnostics` is read-only. `sbc/imu_watch.py` records summaries and a bounded
raw-packet history around a stall without taking control or resetting anything.

| Experiment | Evidence |
|---|---|
| Original DMA RX with instrumentation | Repeated `ff ff ff ff`, 25 ms read timeouts and payload bus errors. A read-only 240-second trace recorded no measurement recovery. |
| Reject malformed headers in discovery and polling | Prevents all-ones reads from keeping `found` true indefinitely; rediscovery now follows failed reads. A regression test covers this case. |
| Polled RX alone | Initially accepted stale zero headers and selected 0x4A incorrectly. Local HAL inspection found the reader can treat old STOPF as read completion before receiving new data. |
| Polled RX plus clean STOP/error/RX state | Restored gyro, gravity and game at 100 Hz with no errors in a five-second sample; acceleration remained absent. |
| Longer run of that image | Relapsed after about 102 seconds. SCL low, SDA high; ISR `0x00008005` (BUSY, RXNE, TXE). 250 header timeouts and maximum supervisor gap 369,371 µs. |
| Full transaction cleanup and host timeout reset | Initial five-second sample: accel 647, gyro 500, gravity 501, game 501; no transport or parse errors. Maximum service gap 27,754 µs. Longer validation below. |

The pinned `embassy-stm32` 0.6.0 implementation waits synchronously for START
in part of its asynchronous path, and the DMA RX path waits on the transfer
without promptly resolving a NACK. Its blocking read can observe stale STOPF.
An unsuccessful write may leave a preloaded TXDR byte; the new preparation uses
the HAL's TXDR flush sequence before the next transaction. These are host-side
failure mechanisms found by code inspection; they do not decode the sensor's
internal error or establish the electrical trigger of every stall.

The recovery image reports `imu_bus=clean-boundaries-v1`,
`imu_diagnostics=2` and retains `imu_startup=quiet-300ms`. It applies bounded
polled transfers to IMU, INA226 and raw diagnostic transactions, clears old
transaction state at an idle bus, yields between absent-device probes and
toggles I2C1 PE after timeouts. Before/after pin levels are logged on host
resets. This reset preserves the peripheral's timing configuration and does
not remove sensor power. No clock-pulse bus clear is implemented.

The upstream project independently documents CPU starvation waiting for START
in [issue #7052](https://github.com/embassy-rs/embassy/issues/7052), fixed on
its main branch by [PR #7101](https://github.com/embassy-rs/embassy/pull/7101),
merged 2026-10-11. The pinned dependency predates that change. The local fix
keeps the pinned dependency rather than importing unrelated upstream changes.

Saved baseline: `exports/imu-research/diagnostics-2026-10-25/before-header-validation.jsonl`.

## Online sources checked

### Manufacturer definitions

1. [CEVA SH-2 public driver header](https://github.com/ceva-dsp/sh2/blob/main/sh2.h)
   defines severity zero as most severe and source four as chip-level. The
   error-record fields do not provide a numeric decoding table for our tuple.
2. [CEVA host-library return codes](https://github.com/ceva-dsp/sh2/blob/main/sh2_err.h)
   define negative API return codes, including -2 for a bad parameter. These
   are not the device's internal error-record namespace.
3. [SH-2 Reference Manual, section 6.4.1](https://cdn.sparkfun.com/assets/4/d/9/3/8/SH-2-Reference-Manual-v1.2.pdf)
   describes the error response fields and source values, but refers the
   detailed error/module/code meanings to the library API. The sources checked
   did not yield a verified meaning for source 4 / error 2 / module 0 / code 0.
4. [Adafruit's BNO08x I2C driver](https://github.com/adafruit/Adafruit_BNO08x/blob/master/src/Adafruit_BNO08x.cpp)
   uses a 300 ms delay after its I2C software reset. This motivated the quiet
   period test; it does not prove timing is the cause here.

### First-hand reports with related symptoms

5. [SlimeVR issue #240](https://github.com/SlimeVR/SlimeVR-Tracker-ESP/issues/240)
   reports a BNO085 at 0x4B returning version **3.2.13**, build 6, then failing
   to provide measurements. It also reports an ESP32 I2C read error 263 and an
   all-zero last-error record. **It is not an exact match to our error tuple**
   and does not establish a shared root cause.
6. [SparkFun: BNO085 cannot get started](https://community.sparkfun.com/t/bno085-cant-get-started/47558)
   contains related initialization failures. One participant traced their
   failure to an incorrect host-side I2C read call corrupting received data.
   This is evidence that similar symptoms can arise in the host, not a
   diagnosis of this installation.
7. [SparkFun BNO080 library issue #72](https://github.com/sparkfun/SparkFun_BNO080_Arduino_Library/issues/72)
   discusses I2C hangs on an Artemis host and possible hard-reset recovery.
   It concerns a different host and provides no verified decoding of our
   device error.

No confirmed online match or authoritative decoding of the complete captured
tuple was found in this investigation. Similar symptoms alone are insufficient
to diagnose defective hardware, bad parameters, calibration failure or a
particular internal firmware fault.

## Earlier follow-up questions

These were open before the owner reported the pull-up removal fix. They are
retained as optional electrical characterization and historical context.

1. The DC supply at the module is measured at **3.299 V**. Startup and stalled
   signal waveforms remain unmeasured; a DC measurement does not exclude dips.
2. Capture SCL and SDA at that connector with I2C decoding while sending a
   report-enable command. Compare the address, header, payload, ACKs and STOP
   with the intended SHTP packet. This is needed to distinguish intact host
   commands from wire-level corruption or transaction-boundary problems.
3. Capture startup packets, initialization/reset responses and the internal
   error queue from a controlled cold start. The setup sequence must be
   validated on actual cold starts, not inferred from warm-run success.
4. If the tuple remains reproducible, obtain its firmware-specific decoding
   from CEVA or 7Semi, supplying the raw packet and firmware 3.2.13/build 6.

The reporting issue is resolved by the owner-confirmed removal of R1/R2.
The earlier logs alone did not establish that outcome or an electrical
mechanism, and do not justify replacing the IMU.
