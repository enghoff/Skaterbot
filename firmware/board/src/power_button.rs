//! Power-button timing, without GPIO or executor dependencies.
//!
//! Host checks: rustc --test --edition=2024 board/src/power_button.rs

pub const TICK_MS: u32 = 10;
pub const OFF_PRESS_MS: u32 = 500;
pub const RELEASE_MS: u32 = 50;
pub const FORCE_OFF_MS: u32 = 8_000;
pub const SHUTDOWN_GRACE_MS: u32 = 20_000;

#[derive(Clone, Copy)]
pub enum Button {
    Starting {
        up_ms: u32,
    },
    Up,
    Down {
        held_ms: u32,
        up_ms: u32,
    },
    Waiting {
        elapsed_ms: u32,
        held_ms: u32,
        up_ms: u32,
    },
    Spent,
}

#[derive(Default, Debug, PartialEq, Eq)]
pub struct Action {
    pub request_off: bool,
    pub cut_power: bool,
}

impl Button {
    pub fn step(self, pressed: bool, graceful: bool) -> (Self, Action) {
        let none = Action::default();
        match self {
            Self::Starting { up_ms } => {
                let up_ms = if pressed { 0 } else { up_ms + TICK_MS };
                (
                    if up_ms >= RELEASE_MS {
                        Self::Up
                    } else {
                        Self::Starting { up_ms }
                    },
                    none,
                )
            }
            Self::Up if pressed => (
                Self::Down {
                    held_ms: TICK_MS,
                    up_ms: 0,
                },
                none,
            ),
            Self::Down { held_ms, up_ms } => {
                let held_ms = held_ms + TICK_MS;
                let up_ms = if pressed { 0 } else { up_ms + TICK_MS };
                if up_ms >= RELEASE_MS {
                    (Self::Up, none)
                } else if pressed && held_ms >= OFF_PRESS_MS {
                    let next = if graceful {
                        Self::Waiting {
                            elapsed_ms: 0,
                            held_ms,
                            up_ms: 0,
                        }
                    } else {
                        Self::Spent
                    };
                    (
                        next,
                        Action {
                            request_off: true,
                            cut_power: !graceful,
                        },
                    )
                } else {
                    (Self::Down { held_ms, up_ms }, none)
                }
            }
            Self::Waiting {
                elapsed_ms,
                held_ms,
                up_ms,
            } => {
                let elapsed_ms = elapsed_ms + TICK_MS;
                let up_ms = if pressed {
                    0
                } else {
                    (up_ms + TICK_MS).min(RELEASE_MS)
                };
                let held_ms = if up_ms >= RELEASE_MS {
                    0
                } else {
                    held_ms + TICK_MS
                };
                if elapsed_ms >= SHUTDOWN_GRACE_MS || (pressed && held_ms >= FORCE_OFF_MS) {
                    (
                        Self::Spent,
                        Action {
                            request_off: false,
                            cut_power: true,
                        },
                    )
                } else {
                    (
                        Self::Waiting {
                            elapsed_ms,
                            held_ms,
                            up_ms,
                        },
                        none,
                    )
                }
            }
            other => (other, none),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn advance(button: &mut Button, pressed: bool, ms: u32, graceful: bool) -> (u32, u32) {
        let (mut requests, mut cuts) = (0, 0);
        for _ in 0..ms / TICK_MS {
            let (next, action) = button.step(pressed, graceful);
            *button = next;
            requests += action.request_off as u32;
            cuts += action.cut_power as u32;
        }
        (requests, cuts)
    }

    #[test]
    fn ignores_startup_press_and_short_press() {
        let mut b = Button::Starting { up_ms: 0 };
        assert_eq!(advance(&mut b, true, FORCE_OFF_MS + 1000, true), (0, 0));
        advance(&mut b, false, RELEASE_MS, true);
        assert_eq!(advance(&mut b, true, OFF_PRESS_MS - TICK_MS, true), (0, 0));
        assert_eq!(advance(&mut b, false, RELEASE_MS, true), (0, 0));
    }

    #[test]
    fn graceful_press_requests_once_and_waits_for_linux() {
        let mut b = Button::Up;
        assert_eq!(advance(&mut b, true, OFF_PRESS_MS, true), (1, 0));
        assert_eq!(
            advance(&mut b, false, SHUTDOWN_GRACE_MS - TICK_MS, true),
            (0, 0)
        );
        assert_eq!(advance(&mut b, false, TICK_MS, true), (0, 1));
        assert_eq!(advance(&mut b, true, FORCE_OFF_MS, true), (0, 0));
    }

    #[test]
    fn continued_eight_second_press_forces_off() {
        let mut b = Button::Up;
        assert_eq!(advance(&mut b, true, FORCE_OFF_MS - TICK_MS, true), (1, 0));
        assert_eq!(advance(&mut b, true, TICK_MS, true), (0, 1));
    }

    #[test]
    fn a_second_press_needs_its_own_eight_seconds() {
        let mut b = Button::Up;
        advance(&mut b, true, 2000, true);
        advance(&mut b, false, RELEASE_MS, true);
        assert_eq!(advance(&mut b, true, FORCE_OFF_MS - TICK_MS, true), (0, 0));
        assert_eq!(advance(&mut b, true, TICK_MS, true), (0, 1));
    }

    #[test]
    fn bounce_does_not_count_as_a_release() {
        let mut b = Button::Up;
        advance(&mut b, true, 1000, true);
        advance(&mut b, false, RELEASE_MS - TICK_MS, true);
        assert_eq!(
            advance(&mut b, true, FORCE_OFF_MS - 1000 - RELEASE_MS, true),
            (0, 0)
        );
        assert_eq!(advance(&mut b, true, TICK_MS, true), (0, 1));
    }

    #[test]
    fn other_images_keep_the_original_immediate_cut() {
        let mut b = Button::Up;
        assert_eq!(advance(&mut b, true, OFF_PRESS_MS, false), (1, 1));
    }
}
