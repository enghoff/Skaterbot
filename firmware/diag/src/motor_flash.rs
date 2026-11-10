//! The controller's fault on the motors' own LEDs as well as on its own, while
//! nothing is using the motors, without GPIO or executor dependencies.
//! docs/DIAGNOSTICS.md, "The motors' LEDs", is the specification.
//!
//! Host checks: rustc --test --edition=2024 diag/src/motor_flash.rs
//!
//! Times are the controller's milliseconds since it started.
//!
//! A DAMIAO motor's LED cannot be set. It is green while the motor is enabled,
//! red while it is disabled, and flashing red in a fault of the motor's own
//! (the DM-J3507-2EC manual's "LED indicator states"), and no command or
//! register reaches it otherwise. So a lit phase of a fault's pattern is the
//! motor enabled with no gains and no torque asked of it, and a dark phase is
//! the motor disabled.
//!
//! Enabling a motor is the one thing this controller does to a motor without
//! being told to, so it is held to these:
//!
//! - A motor the Pi is using is left alone. Anything the Pi sends a motor, and
//!   its stop, ends the flash there and then, with every motor disabled ahead of
//!   the Pi's frame, and nothing shows again until the Pi has left the motors
//!   alone for [`HANDS_OFF_MS`].
//! - A fault that begins while the Pi is using the motors is not shown at all,
//!   until it has cleared and come back. The run carries on as it always did.
//! - A motor that is enabled hears a no-torque command every [`KEEP_EVERY_MS`],
//!   well inside the 200 ms its TIMEOUT register allows, so that the register
//!   drops it only if the controller has stopped.
//! - Only a motor that has just said it is in MIT mode is touched. The no-torque
//!   command means no torque only there: a motor left in velocity mode, say by
//!   the motor console, would read the same bytes as a speed far past its top.
//!   Each showing begins by asking, and a motor that does not answer stays dark.
//! - It stops for good once shutdown is asked for, but for the one blink below.
//!
//! A long press is answered on the LEDs. Every motor is stopped, as it always
//! was, so one that was running goes from green to red. If none was, they would
//! show nothing, so those that say MIT blink green once. The blink waits for
//! Linux to accept the shutdown, or for [`BLINK_WAIT_MS`] if it does not, since
//! the Pi's stops come in between and each one disables every motor. By then the
//! controller is refusing everything the Pi sends a motor, so nothing can
//! contend with it.

/// A cycle of a pattern, as `health::Fault::pattern` has it: lit or dark, for so
/// many milliseconds.
pub type Pattern = &'static [(bool, u64)];

/// How long after the Pi last touched a motor they still count as the Pi's. A
/// run sends every motor a command at 125 Hz, or the motors' 200 ms TIMEOUT
/// would drop them, and between a run's stages it is gone for less than this.
/// Over the deadman's 300 ms, so that the Pi dying mid-drive is a fault that
/// began while it was using the motors.
pub const HANDS_OFF_MS: u64 = 3_000;
/// How often an enabled motor hears a no-torque command; its TIMEOUT is 200 ms.
pub const KEEP_EVERY_MS: u64 = 50;
/// How long the motors get to say which mode they are in, before the first Light.
pub const MODE_WAIT_MS: u64 = 100;
/// CTRL_MODE's value for MIT mode.
pub const MIT_MODE: u32 = 1;
/// A test ends by itself, after at most this long.
pub const TEST_MOST_S: u8 = 60;
/// Bit n is motor n + 1.
pub const EVERY_MOTOR: u8 = 0b11_1111;
/// A motor that said it was enabled this recently counts as running. An enabled
/// motor answers every command it hears, and its TIMEOUT register drops it after
/// 200 ms of hearing none.
pub const RUNNING_WITHIN_MS: u64 = 300;
/// How long the Pi gets to accept the shutdown before a long press's blink goes
/// anyway. Of the 83 long presses in diagd.log to 2026-11-10 it was accepted
/// within 1 s, in the log's whole seconds, in all but one, which took 5 s. A blink
/// begun before a late acceptance is lost to the stop that comes with it.
pub const BLINK_WAIT_MS: u64 = 3_000;
/// How long the blink is lit.
pub const BLINK_LIT_MS: u64 = 500;
/// How long past the blink the motors can still be told something, for the
/// frames that disable them to reach the bus.
pub const BLINK_CLOSE_MS: u64 = 100;

/// What the motors are to be told at this tick.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Action {
    Nothing,
    /// Each motor asked which mode it is in.
    AskMode,
    /// A no-torque command, enable, and a no-torque command again.
    Light,
    /// A no-torque command, so that an enabled motor is not timed out.
    Keep,
    /// Disable.
    Darken,
}

/// A pattern shown with no fault there, to see it do no harm.
#[derive(Clone, Copy)]
struct Test {
    pattern: Pattern,
    mask: u8,
    until: u64,
}

/// Where the green blink that answers a long press has got to.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Blink {
    /// No long press, or no answer decided.
    None,
    /// A long press with the motors off: waiting for the Pi to accept it.
    Waiting {
        since: u64,
    },
    Accepted,
    Asked {
        at: u64,
    },
    Lit {
        until: u64,
    },
    Closing {
        until: u64,
    },
    /// Over, or never to be.
    Done,
}

pub struct MotorFlash {
    /// When the Pi last sent a motor anything, or stopped them.
    pi_at: Option<u64>,
    /// When a motor last said it was enabled, if nothing has stopped them since.
    enabled_at: Option<u64>,
    blink: Blink,
    /// The fault that stands, and whether it began with the motors left alone.
    fault: Option<Pattern>,
    may_show: bool,
    test: Option<Test>,
    /// The motors have been told to enable, and not to disable since.
    lit: bool,
    zero_at: u64,
    showing: bool,
    /// When this showing asked the motors their mode, and those that said MIT.
    asked_at: Option<u64>,
    mit: u8,
}

impl Default for MotorFlash {
    fn default() -> Self {
        Self::new()
    }
}

fn lit_at(pattern: Pattern, now: u64) -> bool {
    let cycle: u64 = pattern.iter().map(|&(_, ms)| ms).sum();
    let mut left = now % cycle.max(1);
    for &(lit, ms) in pattern {
        if left < ms {
            return lit;
        }
        left -= ms;
    }
    false
}

impl MotorFlash {
    pub const fn new() -> Self {
        Self {
            pi_at: None,
            enabled_at: None,
            blink: Blink::None,
            fault: None,
            may_show: false,
            test: None,
            lit: false,
            zero_at: 0,
            showing: false,
            asked_at: None,
            mit: 0,
        }
    }

    fn pi_has_them(&self, now: u64) -> bool {
        self.pi_at.is_some_and(|t| now < t + HANDS_OFF_MS)
    }

    /// The Pi has sent a motor a frame. True if the motors are lit, and every one
    /// must be told to disable ahead of that frame.
    pub fn pi_frame(&mut self, now: u64) -> bool {
        self.pi_at = Some(now);
        if self.blink != Blink::None {
            self.blink = Blink::Done;
        }
        self.test = None;
        self.showing = false;
        self.asked_at = None;
        core::mem::take(&mut self.lit)
    }

    /// Every motor has just been stopped, and the queues emptied. `by_pi` is the
    /// Pi or the button asking, which is someone having the motors; the deadman
    /// and the controller starting are not.
    pub fn stopped(&mut self, now: u64, by_pi: bool) {
        self.lit = false;
        self.test = None;
        self.showing = false;
        self.asked_at = None;
        self.enabled_at = None;
        // One that has begun, by asking the motors anything, is over: a stop wins.
        // One still to come is not, since the stops are what it is waiting out.
        if self.blinking() {
            self.blink = Blink::Done;
        }
        if by_pi {
            self.pi_at = Some(now);
        }
    }

    /// The button has been held long enough to turn the robot off. To be called
    /// before the stop that follows. True if the motors were off, and will blink.
    pub fn long_press(&mut self, now: u64) -> bool {
        if self.blink != Blink::None {
            return false;
        }
        let running = self.enabled_at.is_some_and(|t| now < t + RUNNING_WITHIN_MS);
        self.blink = if running {
            Blink::Done
        } else {
            Blink::Waiting { since: now }
        };
        !running
    }

    /// Linux has accepted the shutdown. `by_button` is whether a long press came
    /// first: one the Pi started by itself is not answered by a blink.
    pub fn shutdown_accepted(&mut self, by_button: bool) {
        match (by_button, self.blink) {
            (true, Blink::Waiting { .. }) => self.blink = Blink::Accepted,
            (false, Blink::None) => self.blink = Blink::Done,
            _ => {}
        }
    }

    /// Whether the motors are being told something for the blink, which is all
    /// that may reach them once shutdown has been asked for.
    pub fn blinking(&self) -> bool {
        matches!(
            self.blink,
            Blink::Asked { .. } | Blink::Lit { .. } | Blink::Closing { .. }
        )
    }

    fn blink_tick(&mut self, now: u64) -> Action {
        match self.blink {
            Blink::Waiting { since } if now < since + BLINK_WAIT_MS => Action::Nothing,
            Blink::Waiting { .. } | Blink::Accepted => {
                self.blink = Blink::Asked { at: now };
                self.mit = 0;
                Action::AskMode
            }
            Blink::Asked { at } if now < at + MODE_WAIT_MS => Action::Nothing,
            Blink::Asked { .. } if self.mit == 0 => {
                self.blink = Blink::Done;
                Action::Nothing
            }
            Blink::Asked { .. } => {
                self.blink = Blink::Lit {
                    until: now + BLINK_LIT_MS,
                };
                self.lit = true;
                self.zero_at = now;
                Action::Light
            }
            Blink::Lit { until } if now >= until => {
                self.blink = Blink::Closing {
                    until: now + BLINK_CLOSE_MS,
                };
                self.lit = false;
                Action::Darken
            }
            Blink::Lit { .. } if now >= self.zero_at + KEEP_EVERY_MS => {
                self.zero_at = now;
                Action::Keep
            }
            Blink::Closing { until } if now >= until => {
                self.blink = Blink::Done;
                Action::Nothing
            }
            _ => Action::Nothing,
        }
    }

    /// Shows `pattern` on the motors in `mask` for `seconds`, with no fault, by
    /// the road a fault takes. False, and nothing starts, if it may not, a fault
    /// standing being one reason: it is a test of the pattern with none there.
    pub fn start_test(
        &mut self,
        now: u64,
        pattern: Pattern,
        mask: u8,
        seconds: u8,
        shutting_down: bool,
    ) -> bool {
        let mask = mask & EVERY_MOTOR;
        if shutting_down
            || self.pi_has_them(now)
            || self.fault.is_some()
            || mask == 0
            || seconds == 0
        {
            return false;
        }
        self.test = Some(Test {
            pattern,
            mask,
            until: now + seconds.min(TEST_MOST_S) as u64 * 1000,
        });
        true
    }

    pub fn end_test(&mut self) {
        self.test = None;
    }

    /// The motors this showing is for.
    pub fn target(&self) -> u8 {
        self.test.map_or(EVERY_MOTOR, |t| t.mask)
    }

    /// The motors a Light or a Keep is for: those it is for that said MIT.
    pub fn mask(&self) -> u8 {
        self.target() & self.mit
    }

    /// A motor has reported, with the state in the top of its first byte: 1 is
    /// enabled. By what the motors say, since the Pi's frames do not tell: the motor
    /// console asks disabled motors for their status twenty times a second. What
    /// the flash has lit itself is not anybody running them.
    pub fn motor_said(&mut self, state: u8, now: u64) {
        if state == 1 && !self.showing && !self.blinking() {
            self.enabled_at = Some(now);
        }
    }

    /// A motor, 1 to 6, has said which mode it is in.
    pub fn mode_heard(&mut self, motor: u8, mode: u32) {
        if (1..=6).contains(&motor) {
            let bit = 1 << (motor - 1);
            if mode == MIT_MODE {
                self.mit |= bit;
            } else {
                self.mit &= !bit;
            }
        }
    }

    /// Whether a pattern is being shown, lit or dark, as of the last tick.
    pub fn showing(&self) -> bool {
        self.showing
    }

    /// One tick. `fault` is the pattern of the fault that stands, if one does.
    pub fn tick(&mut self, now: u64, fault: Option<Pattern>, shutting_down: bool) -> Action {
        if shutting_down && !matches!(self.blink, Blink::None | Blink::Done) {
            return self.blink_tick(now);
        }
        if self.test.is_some_and(|t| now >= t.until) {
            self.test = None;
        }
        // Each fault judged as it begins, so that one that replaces another during
        // a drive is not let through by the one before.
        if fault != self.fault {
            self.fault = fault;
            self.may_show = fault.is_some() && !self.pi_has_them(now);
        }
        let pattern = match (self.test, fault) {
            (Some(test), _) => Some(test.pattern),
            (None, Some(pattern)) if self.may_show => Some(pattern),
            _ => None,
        };
        let wanted = match pattern {
            Some(pattern) if !shutting_down && !self.pi_has_them(now) => Some(lit_at(pattern, now)),
            _ => None,
        };
        self.showing = wanted.is_some();
        let Some(lit_now) = wanted else {
            self.asked_at = None;
            return if core::mem::take(&mut self.lit) {
                Action::Darken
            } else {
                Action::Nothing
            };
        };
        let Some(asked_at) = self.asked_at else {
            self.asked_at = Some(now);
            self.mit = 0;
            return Action::AskMode;
        };
        if now < asked_at + MODE_WAIT_MS {
            return Action::Nothing;
        }
        match (self.lit, lit_now) {
            (false, true) => {
                self.lit = true;
                self.zero_at = now;
                Action::Light
            }
            (true, true) if now >= self.zero_at + KEEP_EVERY_MS => {
                self.zero_at = now;
                Action::Keep
            }
            (true, false) => {
                self.lit = false;
                Action::Darken
            }
            _ => Action::Nothing,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const LINK: Pattern = &[(true, 500), (false, 500)];
    const IMU: Pattern = &[(true, 100), (false, 100)];
    const HARDWARE: Pattern = &[(true, 1000), (false, 200)];
    const TICK: u64 = 20;

    /// Every tick from `from` to `to`, and what each said to do.
    fn run(f: &mut MotorFlash, from: u64, to: u64, fault: Option<Pattern>) -> Vec<(u64, Action)> {
        (from..to)
            .step_by(TICK as usize)
            .map(|t| {
                let action = f.tick(t, fault, false);
                if action == Action::AskMode {
                    for motor in 1..=6 {
                        f.mode_heard(motor, MIT_MODE);
                    }
                }
                (t, action)
            })
            .filter(|&(_, a)| a != Action::Nothing && a != Action::AskMode)
            .collect()
    }

    fn lights(done: &[(u64, Action)]) -> usize {
        done.iter().filter(|&&(_, a)| a == Action::Light).count()
    }

    fn darks(done: &[(u64, Action)]) -> usize {
        done.iter().filter(|&&(_, a)| a == Action::Darken).count()
    }

    /// The Pi driving: a frame from every tick.
    fn driven(f: &mut MotorFlash, from: u64, to: u64, fault: Option<Pattern>) -> usize {
        let mut asked = 0;
        for t in (from..to).step_by(TICK as usize) {
            assert!(!f.pi_frame(t), "lit while the Pi has the motors, at {t}");
            if f.tick(t, fault, false) != Action::Nothing {
                asked += 1;
            }
        }
        asked
    }

    #[test]
    fn healthy_leaves_the_motors_alone() {
        let mut f = MotorFlash::new();
        assert!(run(&mut f, 0, 60_000, None).is_empty());
        assert!(!f.showing());
    }

    #[test]
    fn a_fault_with_the_motors_left_alone_shows() {
        let mut f = MotorFlash::new();
        let done = run(&mut f, 0, 2_000, Some(LINK));
        assert_eq!(lights(&done), 2, "{done:?}");
        assert_eq!(darks(&done), 2, "{done:?}");
        assert!(f.showing());
    }

    #[test]
    fn it_follows_each_pattern() {
        // The first of IMU's lit phases passes while the motors are answering.
        for (pattern, on) in [(IMU, 9), (LINK, 2), (HARDWARE, 2)] {
            let mut f = MotorFlash::new();
            let done = run(&mut f, 0, 2_000, Some(pattern));
            assert_eq!(lights(&done), on, "{done:?}");
        }
    }

    #[test]
    fn a_lit_motor_is_never_left_near_its_timeout() {
        let mut f = MotorFlash::new();
        let done = run(&mut f, 0, 10_000, Some(HARDWARE));
        let mut last = None;
        for &(t, a) in &done {
            match a {
                Action::Light | Action::Keep => {
                    if let (Some(was), Action::Keep) = (last, a) {
                        assert!(t - was <= 80, "{was} to {t}");
                    }
                    last = Some(t);
                }
                _ => last = None,
            }
        }
    }

    #[test]
    fn a_clearing_fault_goes_dark() {
        let mut f = MotorFlash::new();
        let done = run(&mut f, 0, 400, Some(LINK));
        assert_eq!(done.last().unwrap().1, Action::Keep);
        assert_eq!(f.tick(420, None, false), Action::Darken);
        assert!(!f.showing());
        assert!(run(&mut f, 440, 5_000, None).is_empty());
    }

    #[test]
    fn a_fault_during_a_drive_is_never_shown() {
        let mut f = MotorFlash::new();
        assert_eq!(driven(&mut f, 0, 2_000, Some(IMU)), 0);
        assert_eq!(driven(&mut f, 2_000, 4_000, Some(IMU)), 0);
        // The drive ends, and the fault still stands.
        assert!(run(&mut f, 4_000, 30_000, Some(IMU)).is_empty());
        assert!(!f.showing());
    }

    #[test]
    fn that_fault_shows_if_it_clears_and_comes_back_with_the_motors_left_alone() {
        let mut f = MotorFlash::new();
        driven(&mut f, 0, 2_000, Some(IMU));
        assert!(run(&mut f, 2_000, 8_000, None).is_empty());
        assert!(lights(&run(&mut f, 8_000, 9_000, Some(IMU))) > 0);
    }

    /// The Pi dying mid-drive: it sent a frame 300 ms before the deadman trips,
    /// and the stop it causes is not the Pi asking.
    #[test]
    fn the_pi_dying_during_a_drive_is_never_shown() {
        let mut f = MotorFlash::new();
        driven(&mut f, 0, 2_000, None);
        run(&mut f, 2_000, 2_300, None);
        f.stopped(2_300, false);
        assert!(run(&mut f, 2_300, 30_000, Some(LINK)).is_empty());
    }

    #[test]
    fn the_pi_dying_with_the_motors_left_alone_is_shown() {
        let mut f = MotorFlash::new();
        run(&mut f, 0, 5_000, None);
        f.stopped(5_000, false);
        assert!(lights(&run(&mut f, 5_000, 7_000, Some(LINK))) > 0);
    }

    #[test]
    fn the_pis_frame_puts_every_motor_out_first() {
        let mut f = MotorFlash::new();
        run(&mut f, 0, 200, Some(LINK));
        assert!(f.pi_frame(200), "lit, so the motors must be disabled first");
        assert!(!f.pi_frame(201), "and only the once");
    }

    #[test]
    fn nothing_is_lit_while_the_pi_has_them_then_it_goes_on() {
        let mut f = MotorFlash::new();
        run(&mut f, 0, 200, Some(IMU));
        f.pi_frame(200);
        assert!(run(&mut f, 200, 200 + HANDS_OFF_MS, Some(IMU)).is_empty());
        assert!(!f.showing());
        assert!(lights(&run(&mut f, 200 + HANDS_OFF_MS, 4_000, Some(IMU))) > 0);
    }

    #[test]
    fn the_pis_stop_is_the_pi_having_them() {
        let mut f = MotorFlash::new();
        run(&mut f, 0, 200, Some(IMU));
        f.stopped(200, true);
        assert!(run(&mut f, 200, 200 + HANDS_OFF_MS, Some(IMU)).is_empty());
    }

    #[test]
    fn a_stop_leaves_nothing_to_put_out() {
        let mut f = MotorFlash::new();
        run(&mut f, 0, 200, Some(LINK));
        f.stopped(200, true);
        assert!(!f.pi_frame(201));
    }

    #[test]
    fn shutdown_puts_it_out_and_it_stays_out() {
        let mut f = MotorFlash::new();
        run(&mut f, 0, 200, Some(LINK));
        assert_eq!(f.tick(200, Some(LINK), true), Action::Darken);
        for t in (220..30_000).step_by(20) {
            assert_eq!(f.tick(t, Some(LINK), true), Action::Nothing);
        }
        assert!(!f.start_test(30_000, IMU, EVERY_MOTOR, 5, true));
    }

    #[test]
    fn a_test_shows_with_no_fault_and_ends_by_itself() {
        let mut f = MotorFlash::new();
        assert!(f.start_test(0, IMU, EVERY_MOTOR, 2, false));
        let done = run(&mut f, 0, 2_000, None);
        assert_eq!(lights(&done), 9, "{done:?}");
        assert!(f.showing());
        // It ended in a dark phase, so there is nothing more to put out.
        assert!(run(&mut f, 2_000, 10_000, None).is_empty());
        assert!(!f.showing());
    }

    #[test]
    fn a_test_ending_on_a_lit_phase_goes_dark() {
        let mut f = MotorFlash::new();
        assert!(f.start_test(0, HARDWARE, EVERY_MOTOR, 1, false));
        run(&mut f, 0, 980, None);
        assert_eq!(f.tick(1_000, None, false), Action::Darken);
    }

    #[test]
    fn a_test_is_for_the_motors_it_names() {
        let mut f = MotorFlash::new();
        f.start_test(0, IMU, 0b10000, 2, false);
        assert_eq!(f.target(), 0b10000);
        f.end_test();
        assert_eq!(f.target(), EVERY_MOTOR);
        assert!(!f.start_test(0, IMU, 0b1000000, 2, false), "no such motor");
    }

    #[test]
    fn a_test_is_refused_while_the_pi_has_them() {
        let mut f = MotorFlash::new();
        f.pi_frame(1_000);
        assert!(!f.start_test(1_000 + HANDS_OFF_MS - 1, IMU, EVERY_MOTOR, 5, false));
        assert!(f.start_test(1_000 + HANDS_OFF_MS, IMU, EVERY_MOTOR, 5, false));
    }

    #[test]
    fn the_pi_ends_a_test_at_once() {
        let mut f = MotorFlash::new();
        f.start_test(0, HARDWARE, EVERY_MOTOR, 30, false);
        run(&mut f, 0, 200, None);
        assert!(f.pi_frame(200));
        assert!(run(&mut f, 200, 40_000, None).is_empty());
    }

    #[test]
    fn a_stop_ends_a_test() {
        let mut f = MotorFlash::new();
        f.start_test(0, HARDWARE, EVERY_MOTOR, 30, false);
        run(&mut f, 0, 200, None);
        f.stopped(200, false);
        assert!(run(&mut f, 200, 40_000, None).is_empty());
    }

    #[test]
    fn a_test_is_held_to_its_most() {
        let mut f = MotorFlash::new();
        f.start_test(0, HARDWARE, EVERY_MOTOR, 200, false);
        run(&mut f, 0, TEST_MOST_S as u64 * 1000 + 40, None);
        assert!(!f.showing());
    }

    #[test]
    fn a_test_is_refused_with_a_fault_standing() {
        let mut f = MotorFlash::new();
        run(&mut f, 0, 200, Some(LINK));
        assert!(!f.start_test(200, IMU, 0b1, 1, false));
    }

    #[test]
    fn it_asks_the_motors_first_and_lights_none_before_they_answer() {
        let mut f = MotorFlash::new();
        assert_eq!(f.tick(0, Some(LINK), false), Action::AskMode);
        for t in (20..MODE_WAIT_MS).step_by(20) {
            assert_eq!(f.tick(t, Some(LINK), false), Action::Nothing, "at {t}");
        }
        assert_eq!(f.tick(MODE_WAIT_MS, Some(LINK), false), Action::Light);
    }

    #[test]
    fn only_a_motor_that_said_mit_is_touched() {
        let mut f = MotorFlash::new();
        f.tick(0, Some(LINK), false);
        f.mode_heard(3, MIT_MODE);
        f.mode_heard(4, 3);
        f.mode_heard(9, MIT_MODE);
        assert_eq!(
            f.mask(),
            0b100,
            "motor 3 said MIT, 4 velocity, the rest nothing"
        );
    }

    #[test]
    fn a_motor_that_changes_its_answer_is_dropped() {
        let mut f = MotorFlash::new();
        f.tick(0, Some(LINK), false);
        f.mode_heard(3, MIT_MODE);
        f.mode_heard(3, 2);
        assert_eq!(f.mask(), 0);
    }

    #[test]
    fn a_test_touches_only_its_motors_that_said_mit() {
        let mut f = MotorFlash::new();
        f.start_test(0, IMU, 0b11, 2, false);
        f.tick(0, None, false);
        f.mode_heard(2, MIT_MODE);
        f.mode_heard(5, MIT_MODE);
        assert_eq!(f.mask(), 0b10);
    }

    #[test]
    fn every_showing_asks_again() {
        let mut f = MotorFlash::new();
        run(&mut f, 0, 200, Some(LINK));
        assert_eq!(f.mask(), EVERY_MOTOR);
        f.pi_frame(200);
        run(&mut f, 200, 200 + HANDS_OFF_MS, Some(LINK));
        let t = 200 + HANDS_OFF_MS;
        assert_eq!(f.tick(t, Some(LINK), false), Action::AskMode);
        assert_eq!(
            f.mask(),
            0,
            "what was said before the Pi had them counts for nothing"
        );
    }

    /// Every tick of a shutdown from `from` to `to`, the motors answering as they do.
    fn off_ticks(f: &mut MotorFlash, from: u64, to: u64, said: u32) -> Vec<(u64, Action)> {
        (from..to)
            .step_by(TICK as usize)
            .map(|t| {
                let action = f.tick(t, None, true);
                if action == Action::AskMode {
                    for motor in 1..=6 {
                        f.mode_heard(motor, said);
                    }
                }
                (t, action)
            })
            .filter(|&(_, a)| a != Action::Nothing)
            .collect()
    }

    fn pressed(f: &mut MotorFlash, now: u64) -> bool {
        let blink = f.long_press(now);
        f.stopped(now, true);
        blink
    }

    #[test]
    fn a_long_press_with_the_motors_off_blinks_once() {
        let mut f = MotorFlash::new();
        assert!(pressed(&mut f, 10_000));
        f.shutdown_accepted(true);
        let done = off_ticks(&mut f, 10_020, 40_000, MIT_MODE);
        assert_eq!(done[0], (10_020, Action::AskMode), "{done:?}");
        assert_eq!(done[1], (10_020 + MODE_WAIT_MS, Action::Light), "{done:?}");
        assert_eq!(lights(&done), 1, "{done:?}");
        assert_eq!(darks(&done), 1, "{done:?}");
        let on = done[1].0;
        let off = done.iter().find(|&&(_, a)| a == Action::Darken).unwrap().0;
        assert_eq!(off, on + BLINK_LIT_MS, "{done:?}");
        assert_eq!(done.last().unwrap().1, Action::Darken, "and nothing after");
    }

    #[test]
    fn a_blink_is_never_left_near_its_timeout() {
        let mut f = MotorFlash::new();
        pressed(&mut f, 0);
        f.shutdown_accepted(true);
        let done = off_ticks(&mut f, 20, 2_000, MIT_MODE);
        let held: Vec<u64> = done
            .iter()
            .filter(|&&(_, a)| a != Action::AskMode)
            .map(|&(t, _)| t)
            .collect();
        assert!(held.len() >= 8, "lit, kept alive, and put out: {done:?}");
        for pair in held.windows(2) {
            assert!(pair[1] - pair[0] <= 80, "{held:?}");
        }
    }

    #[test]
    fn running_motors_only_stop() {
        let mut f = MotorFlash::new();
        driven(&mut f, 0, 2_000, None);
        f.motor_said(1, 1_995);
        assert!(!pressed(&mut f, 2_000));
        f.shutdown_accepted(true);
        assert!(off_ticks(&mut f, 2_020, 30_000, MIT_MODE).is_empty());
        assert!(!f.blinking());
    }

    #[test]
    fn motors_the_pi_stopped_just_now_are_off() {
        let mut f = MotorFlash::new();
        driven(&mut f, 0, 2_000, None);
        f.motor_said(1, 1_995);
        f.stopped(2_000, true);
        assert!(pressed(&mut f, 2_010), "a tap's stop, then a long press");
    }

    #[test]
    fn the_pi_asking_disabled_motors_is_not_running_them() {
        let mut f = MotorFlash::new();
        for t in (0..2_000).step_by(50) {
            f.pi_frame(t);
            f.motor_said(0, t + 1);
        }
        assert!(f.long_press(2_000), "a motor console tab left open");
    }

    #[test]
    fn its_own_pattern_is_not_running_them() {
        let mut f = MotorFlash::new();
        run(&mut f, 0, 300, Some(LINK));
        f.motor_said(1, 290);
        assert!(f.long_press(300));
    }

    #[test]
    fn motors_the_pi_left_alone_are_off_after_their_timeout() {
        let mut f = MotorFlash::new();
        f.motor_said(1, 1_000);
        let mut g = MotorFlash::new();
        g.motor_said(1, 1_000);
        assert!(!f.long_press(1_000 + RUNNING_WITHIN_MS - 1));
        assert!(g.long_press(1_000 + RUNNING_WITHIN_MS));
    }

    #[test]
    fn it_waits_out_the_pis_stops_and_for_the_shutdown() {
        let mut f = MotorFlash::new();
        pressed(&mut f, 0);
        for t in (20..500).step_by(20) {
            assert_eq!(f.tick(t, None, true), Action::Nothing, "at {t}");
        }
        f.stopped(500, true);
        assert!(off_ticks(&mut f, 500, 700, MIT_MODE).is_empty());
        f.stopped(700, true);
        f.shutdown_accepted(true);
        assert_eq!(f.tick(720, None, true), Action::AskMode);
    }

    #[test]
    fn a_pi_that_never_accepts_still_gets_a_blink() {
        let mut f = MotorFlash::new();
        pressed(&mut f, 0);
        let done = off_ticks(&mut f, 20, 5_000, MIT_MODE);
        assert_eq!(done[0], (BLINK_WAIT_MS, Action::AskMode), "{done:?}");
        assert_eq!(lights(&done), 1, "{done:?}");
    }

    #[test]
    fn a_stop_during_the_blink_ends_it() {
        let mut f = MotorFlash::new();
        pressed(&mut f, 0);
        f.shutdown_accepted(true);
        let done = off_ticks(&mut f, 20, 300, MIT_MODE);
        assert_eq!(lights(&done), 1, "{done:?}");
        assert!(f.blinking());
        f.stopped(300, true);
        assert!(!f.blinking());
        assert!(off_ticks(&mut f, 300, 30_000, MIT_MODE).is_empty());
    }

    #[test]
    fn a_stop_after_the_motors_are_asked_ends_it_too() {
        let mut f = MotorFlash::new();
        pressed(&mut f, 0);
        f.shutdown_accepted(true);
        assert_eq!(off_ticks(&mut f, 20, 40, MIT_MODE).len(), 1, "asked");
        f.stopped(40, true);
        assert!(off_ticks(&mut f, 40, 30_000, MIT_MODE).is_empty());
    }

    #[test]
    fn a_blink_touches_only_motors_that_said_mit() {
        let mut f = MotorFlash::new();
        pressed(&mut f, 0);
        f.shutdown_accepted(true);
        assert_eq!(f.tick(20, None, true), Action::AskMode);
        f.mode_heard(2, MIT_MODE);
        f.mode_heard(3, 3);
        assert_eq!(f.tick(20 + MODE_WAIT_MS, None, true), Action::Light);
        assert_eq!(f.mask(), 0b10);
    }

    #[test]
    fn no_motor_saying_mit_is_no_blink() {
        let mut f = MotorFlash::new();
        pressed(&mut f, 0);
        f.shutdown_accepted(true);
        let done = off_ticks(&mut f, 20, 5_000, 3);
        assert_eq!(done, vec![(20, Action::AskMode)]);
        assert!(!f.blinking());
    }

    #[test]
    fn a_shutdown_the_pi_started_is_no_blink() {
        let mut f = MotorFlash::new();
        f.shutdown_accepted(false);
        f.stopped(0, true);
        assert!(!f.long_press(20), "the controller then sees it as off");
        assert!(off_ticks(&mut f, 20, 30_000, MIT_MODE).is_empty());
    }

    #[test]
    fn it_counts_as_blinking_until_the_last_frames_have_had_time() {
        let mut f = MotorFlash::new();
        pressed(&mut f, 0);
        assert!(!f.blinking(), "nothing may go out while it waits");
        f.shutdown_accepted(true);
        let done = off_ticks(&mut f, 20, 1_000, MIT_MODE);
        let off = done.iter().find(|&&(_, a)| a == Action::Darken).unwrap().0;
        let mut g = MotorFlash::new();
        pressed(&mut g, 0);
        g.shutdown_accepted(true);
        off_ticks(&mut g, 20, off + TICK, MIT_MODE);
        assert!(
            g.blinking(),
            "the frames that disable them are still queued"
        );
        off_ticks(
            &mut g,
            off + TICK,
            off + BLINK_CLOSE_MS + 2 * TICK,
            MIT_MODE,
        );
        assert!(!g.blinking());
    }

    #[test]
    fn only_the_first_long_press_counts() {
        let mut f = MotorFlash::new();
        assert!(f.long_press(0));
        assert!(!f.long_press(100));
    }

    /// The INA226 missing at idle, which a run carries on past, then the IMU
    /// failing during the drive.
    #[test]
    fn a_fault_that_replaces_another_during_a_drive_is_not_shown() {
        let mut f = MotorFlash::new();
        run(&mut f, 0, 1_000, Some(HARDWARE));
        assert!(f.showing());
        f.pi_frame(1_000);
        driven(&mut f, 1_000, 3_000, Some(HARDWARE));
        driven(&mut f, 3_000, 5_000, Some(IMU));
        assert!(run(&mut f, 5_000, 30_000, Some(IMU)).is_empty());
    }

    #[test]
    fn a_fault_that_replaces_another_with_the_motors_left_alone_shows() {
        let mut f = MotorFlash::new();
        run(&mut f, 0, 1_000, Some(HARDWARE));
        assert!(lights(&run(&mut f, 1_000, 2_000, Some(IMU))) > 0);
    }
}
