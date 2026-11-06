# The six DM-J3507-2EC, as read off the robot

Every register of every motor, read through diagd with the motors disabled, so
that anything changed on them can be put back.

- `registers_as_found_2026-11-04.json` — all 45 registers and a status report
  for each motor, before anything was written: the factory settings, except
  that the CAN IDs had already been set to 1 to 6 (hips on bus A, knees on B,
  wheels on C). Hip 1's feedback ID is 0 where the others are their ID plus 16;
  it works, because the software falls back to matching the motor ID.
- `registers_after_vmax_2026-11-04.json` — the same read again, and the one
  change made that day: VMAX 50 to 55 rad/s on all six, written and saved to
  each motor's flash, and read back. Its `registers` were read before the write;
  its `changes` say what each became.

- `zero_set_2026-11-04.json` — the four leg motors re-zeroed with the robot
  hanging from the rail and its legs straight down by eye. `was` is what each
  read there against the zero it came with, so adding it back to a reading
  gives the factory frame. The wheels were left alone. Why: the motor knows its
  position only within one turn at power-up, and the right knee's factory zero
  put the edge of that turn where its leg hangs straight -- after a power cycle
  that morning it read a full turn, 2 pi, from where it had read before, at the
  same pose.

- `timeout_set_2026-11-04.json` — TIMEOUT 0 (off) to 4000 on all six, saved.
  It counts in 50 us: 2000 dropped a motor quiet for between 0.08 and 0.12 s
  into state 0xD, so 4000 is 200 ms. A status request does not count as
  hearing from the host; only a command does.
- `sysid_robot_2026-11-04.json` — the Pi's `sbc/sysid_robot.json` at the end
  of that day: which motor is which joint and which way, the knees' zeros as
  the slow sweeps corrected them, and the IMU's axes as the table measured them.
- `imu_captures_2026-11-04.json` — the three accelerometer readings those axes
  come from, each with what the phone read at the time.

Each motor also reports what it identified of itself. `Inertia` is about
6.6e-6 kg m² on all six, which, if it is the rotor's at the motor side, is about
3.2e-4 kg m² through the 7:1 at the joint, against the 2.3e-4 the simulator
estimated. `Damp` is about 1.1e-4. Neither register's units are stated in the
manual, so both wait on docs/SYSID.md's bench tests to say what they mean.
