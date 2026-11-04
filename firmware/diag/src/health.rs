//! What the controller makes of its own health, and how its LED shows it,
//! without GPIO or executor dependencies. docs/DIAGNOSTICS.md, "The heartbeat
//! LEDs", is the specification; `sbc/diagd.py` shows the same verdict on the
//! Pi's LED.
//!
//! Host checks: rustc --test --edition=2024 diag/src/health.rs
//!
//! Times are the controller's milliseconds since it started.

/// How long the IMU may be missing, or found and silent, before either is a
/// fault. A reset takes it away for the 300 ms quiet period and a search finds
/// it again within a second, so neither shows.
pub const IMU_GRACE_MS: u64 = 3_000;
pub const INA_GRACE_MS: u64 = 3_000;
/// A bus recovers from bus-off by itself in about 1.4 ms at 1 Mbit/s, so a
/// bus-off is only ever seen in passing, and once seen is shown for this long.
pub const BUS_OFF_HOLD_MS: u64 = 5_000;
/// How long after starting the controller waits for the Pi before its silence
/// is a fault. The Pi boots in about 15 s.
pub const FIRST_CONTACT_MS: u64 = 30_000;

/// board::heartbeat's timing, which a healthy controller beats exactly: the
/// diag image asserts the two agree.
pub const HEARTBEAT_PERIOD_MS: u64 = 300 + 6720 / 7;
pub const HEARTBEAT_FLASH_MS: u64 = 70;

/// What HEALTH carries, one bit a condition.
pub const IMU_MISSING: u16 = 1 << 0;
pub const IMU_SILENT: u16 = 1 << 1;
pub const INA_MISSING: u16 = 1 << 2;
pub const BUS_OFF: u16 = 1 << 3;
pub const LINK_LOST: u16 = 1 << 4;

/// Each condition's name, as the log gives it.
pub const NAMES: [(u16, &str); 5] = [
    (IMU_MISSING, "IMU missing"),
    (IMU_SILENT, "IMU silent"),
    (INA_MISSING, "INA226 missing"),
    (BUS_OFF, "a bus went bus-off"),
    (LINK_LOST, "nothing from the Pi"),
];

/// What the LED shows: the first of these that holds.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Fault {
    Healthy = 0,
    Link = 1,
    Imu = 2,
    Hardware = 3,
}

const HEARTBEAT: [(bool, u64); 4] = [
    (true, HEARTBEAT_FLASH_MS),
    (false, HEARTBEAT_PERIOD_MS / 4 - HEARTBEAT_FLASH_MS),
    (true, HEARTBEAT_FLASH_MS),
    (
        false,
        HEARTBEAT_PERIOD_MS - HEARTBEAT_PERIOD_MS / 4 - HEARTBEAT_FLASH_MS,
    ),
];
/// An even blink, once a second.
const LINK: [(bool, u64); 2] = [(true, 500), (false, 500)];
/// A fast flicker, five times a second.
const IMU: [(bool, u64); 2] = [(true, 100), (false, 100)];
/// Lit, with a short wink dark.
const HARDWARE: [(bool, u64); 2] = [(true, 1000), (false, 200)];

impl Fault {
    pub fn of(flags: u16) -> Self {
        if flags & LINK_LOST != 0 {
            Self::Link
        } else if flags & (IMU_MISSING | IMU_SILENT) != 0 {
            Self::Imu
        } else if flags & (INA_MISSING | BUS_OFF) != 0 {
            Self::Hardware
        } else {
            Self::Healthy
        }
    }

    /// One cycle of the LED: lit or dark, for so many milliseconds.
    pub fn pattern(self) -> &'static [(bool, u64)] {
        match self {
            Self::Healthy => &HEARTBEAT,
            Self::Link => &LINK,
            Self::Imu => &IMU,
            Self::Hardware => &HARDWARE,
        }
    }
}

/// Whether the Pi counts as gone: the deadman has tripped, or it has never
/// been heard and has had time to boot.
pub fn link_lost(deadman_tripped: bool, ever_heard: bool, now: u64) -> bool {
    deadman_tripped || (!ever_heard && now >= FIRST_CONTACT_MS)
}

/// When each condition began, if it holds.
pub struct Health {
    imu_missing_since: Option<u64>,
    /// Armed when the IMU is found, which is when its reports are asked for,
    /// and disarmed by its first input report. A rediscovery leaves it armed,
    /// so an IMU that is found, reset and found again without ever reporting
    /// is still silent. Reports a host turns off later are not a fault.
    imu_silent_since: Option<u64>,
    ina_missing_since: Option<u64>,
    bus_off_at: Option<u64>,
}

impl Default for Health {
    fn default() -> Self {
        Self::new()
    }
}

impl Health {
    /// Nothing has been found when the controller starts.
    pub const fn new() -> Self {
        Self {
            imu_missing_since: Some(0),
            imu_silent_since: None,
            ina_missing_since: Some(0),
            bus_off_at: None,
        }
    }

    pub fn imu_found(&mut self, now: u64) {
        self.imu_missing_since = None;
        self.imu_silent_since.get_or_insert(now);
    }

    pub fn imu_lost(&mut self, now: u64) {
        self.imu_missing_since.get_or_insert(now);
    }

    pub fn imu_input(&mut self) {
        self.imu_silent_since = None;
    }

    pub fn ina_found(&mut self) {
        self.ina_missing_since = None;
    }

    pub fn ina_lost(&mut self, now: u64) {
        self.ina_missing_since.get_or_insert(now);
    }

    pub fn bus_off(&mut self, now: u64) {
        self.bus_off_at = Some(now);
    }

    pub fn flags(&self, now: u64, link_lost: bool) -> u16 {
        let held = |since: Option<u64>, grace: u64| since.is_some_and(|t| now >= t + grace);
        let mut flags = 0;
        if held(self.imu_missing_since, IMU_GRACE_MS) {
            flags |= IMU_MISSING;
        }
        if held(self.imu_silent_since, IMU_GRACE_MS) {
            flags |= IMU_SILENT;
        }
        if held(self.ina_missing_since, INA_GRACE_MS) {
            flags |= INA_MISSING;
        }
        if self.bus_off_at.is_some_and(|t| now < t + BUS_OFF_HOLD_MS) {
            flags |= BUS_OFF;
        }
        if link_lost {
            flags |= LINK_LOST;
        }
        flags
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A controller that found both parts at 300 ms, as it does after its
    /// quiet period, and has heard the Pi.
    fn started() -> Health {
        let mut h = Health::new();
        h.imu_found(300);
        h.ina_found();
        h
    }

    #[test]
    fn healthy_is_the_board_heartbeat() {
        let mut h = started();
        h.imu_input();
        assert_eq!(h.flags(60_000, false), 0);
        assert_eq!(Fault::of(0), Fault::Healthy);
        let beat = Fault::Healthy.pattern();
        assert_eq!(beat.iter().map(|s| s.1).sum::<u64>(), 1260);
        assert_eq!(beat, [(true, 70), (false, 245), (true, 70), (false, 875)]);
    }

    #[test]
    fn found_but_never_reporting_is_silent_after_the_grace() {
        let h = started();
        assert_eq!(h.flags(300 + IMU_GRACE_MS - 1, false), 0);
        assert_eq!(h.flags(300 + IMU_GRACE_MS, false), IMU_SILENT);
        assert_eq!(Fault::of(IMU_SILENT), Fault::Imu);
    }

    #[test]
    fn a_report_clears_silence_and_turning_reports_off_is_not_a_fault() {
        let mut h = started();
        h.imu_input();
        // A host that turns every report off leaves it quiet, and healthy.
        assert_eq!(h.flags(3_600_000, false), 0);
    }

    #[test]
    fn rediscovery_does_not_restart_silence() {
        let mut h = started();
        // Reset, the 300 ms quiet, found again: once a second, never reporting.
        for second in 1..4u64 {
            h.imu_lost(second * 1000);
            h.imu_found(second * 1000 + 300);
        }
        assert_eq!(h.flags(3_400, false), IMU_SILENT);
        // A brief absence is not missing; the silence holds through it.
        h.imu_lost(3_500);
        assert_eq!(h.flags(3_700, false), IMU_SILENT);
    }

    #[test]
    fn a_reset_that_reports_again_is_healthy() {
        let mut h = started();
        h.imu_input();
        h.imu_lost(10_000);
        h.imu_found(10_300);
        h.imu_input();
        assert_eq!(h.flags(20_000, false), 0);
    }

    #[test]
    fn missing_from_the_start_or_later() {
        let mut h = Health::new();
        h.ina_found();
        assert_eq!(h.flags(IMU_GRACE_MS - 1, false), 0);
        assert_eq!(h.flags(IMU_GRACE_MS, false), IMU_MISSING);
        h.imu_found(5_000);
        h.imu_input();
        assert_eq!(h.flags(5_001, false), 0);
        h.imu_lost(9_000);
        assert_eq!(h.flags(9_000 + IMU_GRACE_MS, false), IMU_MISSING);
        // Found again, reporting: clear at once.
        h.imu_found(13_000);
        h.imu_input();
        assert_eq!(h.flags(13_000, false), 0);
    }

    #[test]
    fn ina226_and_bus_off_are_hardware() {
        let mut h = started();
        h.imu_input();
        h.ina_lost(1_000);
        assert_eq!(h.flags(1_000 + INA_GRACE_MS, false), INA_MISSING);
        h.ina_found();
        h.bus_off(8_000);
        assert_eq!(h.flags(8_000 + BUS_OFF_HOLD_MS - 1, false), BUS_OFF);
        assert_eq!(h.flags(8_000 + BUS_OFF_HOLD_MS, false), 0);
        assert_eq!(Fault::of(BUS_OFF | INA_MISSING), Fault::Hardware);
    }

    #[test]
    fn the_link_comes_first_then_the_imu() {
        assert_eq!(Fault::of(LINK_LOST | IMU_SILENT | BUS_OFF), Fault::Link);
        assert_eq!(Fault::of(IMU_MISSING | INA_MISSING), Fault::Imu);
    }

    #[test]
    fn the_pi_is_given_time_to_boot() {
        assert!(!link_lost(false, false, FIRST_CONTACT_MS - 1));
        assert!(link_lost(false, false, FIRST_CONTACT_MS));
        assert!(!link_lost(false, true, 3_600_000));
        assert!(link_lost(true, true, 1_000));
    }

    #[test]
    fn every_fault_pattern_differs_from_the_heartbeat_and_from_dark() {
        for fault in [Fault::Link, Fault::Imu, Fault::Hardware] {
            let p = fault.pattern();
            assert_ne!(p, Fault::Healthy.pattern());
            assert!(p.iter().any(|s| s.0) && p.iter().any(|s| !s.0));
        }
    }
}
