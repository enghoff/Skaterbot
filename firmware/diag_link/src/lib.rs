//! The framing of the diagnostics link between the controller and the Banana
//! Pi, docs/DIAGNOSTICS.md: what turns a message into bytes on J5 and back.
//!
//! A message is a type byte and a body. On the wire it is followed by a
//! CRC-16/CCITT-FALSE of the two, little-endian, the whole COBS-encoded, and a
//! zero byte to end it. COBS leaves no zero inside a message, so a receiver
//! that has lost its place finds the next message at the next zero.
//!
//! `sbc/diag_link.py` is the same thing in Python. The tests at the bottom hold
//! both to the same bytes: the vectors in them are the ones that file's own
//! check prints, and neither side was written from the other's output.

#![no_std]

/// The Pi's messages to the controller.
pub mod host {
    pub const HELLO: u8 = 0x01;
    pub const PING: u8 = 0x02;
    pub const STOP: u8 = 0x03;
    pub const SHUTDOWN: u8 = 0x04;
    pub const CAN_SEND: u8 = 0x10;
    /// Additive: what the operator asks the policy for, [`super::Drive`]. A
    /// daemon sends it only to an image whose INFO says `drive=1`.
    pub const DRIVE: u8 = 0x11;
    pub const IMU_WRITE: u8 = 0x20;
    pub const I2C: u8 = 0x21;
}

/// The controller's messages to the Pi.
pub mod mcu {
    pub const INFO: u8 = 0x81;
    pub const STATUS: u8 = 0x82;
    pub const STOPPED: u8 = 0x83;
    pub const CAN_RECV: u8 = 0x90;
    pub const IMU_PACKET: u8 = 0xA0;
    pub const IMU_DIAG: u8 = 0xA2;
    /// Additive: version u8, fault u8, condition flags u16. An image that
    /// predates it never sends one, and a daemon that predates it ignores it.
    pub const HEALTH: u8 = 0xA3;
    pub const I2C_RESULT: u8 = 0xA1;
    pub const LOG: u8 = 0xE0;
}

/// The protocol's version, which INFO reports. Raised with any change to a
/// message's layout.
pub const PROTOCOL: u32 = 1;

/// The longest message, type and body: an IMU packet of [`MAX_IMU_PACKET`]
/// and its timestamp, with room to spare.
pub const MAX_MESSAGE: usize = 600;
/// The longest SHTP packet passed either way.
pub const MAX_IMU_PACKET: usize = 512;

/// What the operator is asking the policy for, from a DRIVE's body.
/// docs/POLICY_INTERFACE.md sets out what is to be done with it, and above all
/// that one more than 200 ms old counts as not live.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Drive {
    /// Forward speed, mm/s.
    pub forward_mm_s: i16,
    /// Turn rate, positive to the left, mrad/s.
    pub turn_mrad_s: i16,
    /// Leg height, hip to axle, in tenths of a millimetre.
    pub height_tenth_mm: u16,
    /// A controller is connected. One held still sends nothing and is still live.
    /// When false, the speed and the turn are zero.
    pub live: bool,
    /// Counts jump presses: a jump is asked for when this changes while live.
    pub jump: u8,
}

impl Drive {
    /// None if the body is too short. A later version may append to it.
    pub fn parse(body: &[u8]) -> Option<Drive> {
        if body.len() < 8 {
            return None;
        }
        Some(Drive {
            forward_mm_s: i16::from_le_bytes([body[0], body[1]]),
            turn_mrad_s: i16::from_le_bytes([body[2], body[3]]),
            height_tenth_mm: u16::from_le_bytes([body[4], body[5]]),
            live: body[6] & 1 != 0,
            jump: body[7],
        })
    }
}

/// Validate the BNO08x SHTP header before treating a read as a live sensor.
/// Length includes the header; zero denotes no pending packet. In particular,
/// a floating/stale all-ones read must not keep discovery latched as present.
pub fn imu_header_length(header: &[u8], max_length: usize) -> Option<usize> {
    if header.len() < 4 || header[2] >= 6 {
        return None;
    }
    let length = (u16::from_le_bytes([header[0], header[1]]) & 0x7FFF) as usize;
    if (length != 0 && length < 4) || length > max_length {
        return None;
    }
    Some(length)
}
/// The most a message of [`MAX_MESSAGE`] takes on the wire: its CRC, one COBS
/// code byte for every 254 bytes and one more, and the zero that ends it.
pub const MAX_WIRE: usize = MAX_MESSAGE + 2 + MAX_MESSAGE / 254 + 2;

/// CRC-16/CCITT-FALSE: polynomial 0x1021, initial 0xFFFF, not reflected. Its
/// check value, over "123456789", is 0x29B1.
pub fn crc16(data: &[u8]) -> u16 {
    let mut crc: u16 = 0xFFFF;
    for &byte in data {
        crc ^= (byte as u16) << 8;
        for _ in 0..8 {
            crc = if crc & 0x8000 != 0 {
                (crc << 1) ^ 0x1021
            } else {
                crc << 1
            };
        }
    }
    crc
}

/// Writes one message onto `wire` as it goes on J5, and returns how many bytes
/// that is, or None if the message is longer than [`MAX_MESSAGE`]. The message
/// is `kind` and the parts of its body laid end to end, so a caller need not
/// gather them first.
pub fn encode(kind: u8, body: &[&[u8]], wire: &mut [u8; MAX_WIRE]) -> Option<usize> {
    let mut message = [0u8; MAX_MESSAGE + 2];
    message[0] = kind;
    let mut n = 1;
    for part in body {
        if n + part.len() > MAX_MESSAGE {
            return None;
        }
        message[n..n + part.len()].copy_from_slice(part);
        n += part.len();
    }
    let crc = crc16(&message[..n]);
    message[n..n + 2].copy_from_slice(&crc.to_le_bytes());
    n += 2;
    let len = cobs_encode(&message[..n], &mut wire[..MAX_WIRE - 1]);
    wire[len] = 0;
    Some(len + 1)
}

/// COBS: each run of up to 254 bytes that are not zero is sent after a byte
/// giving its length plus one, and a run shorter than 254 stands for itself
/// and the zero after it. `out` has to hold `data.len() + data.len() / 254 + 1`.
fn cobs_encode(data: &[u8], out: &mut [u8]) -> usize {
    let mut code_at = 0;
    let mut n = 1;
    let mut code = 1u8;
    for &byte in data {
        if byte == 0 {
            out[code_at] = code;
            code_at = n;
            n += 1;
            code = 1;
        } else {
            out[n] = byte;
            n += 1;
            code += 1;
            if code == 0xFF {
                out[code_at] = code;
                code_at = n;
                n += 1;
                code = 1;
            }
        }
    }
    out[code_at] = code;
    n
}

/// Undoes [`cobs_encode`] into `out`, or None if `data` is not COBS or does not
/// fit.
fn cobs_decode(data: &[u8], out: &mut [u8]) -> Option<usize> {
    let mut i = 0;
    let mut n = 0;
    while i < data.len() {
        let code = data[i] as usize;
        if code == 0 {
            return None;
        }
        i += 1;
        let run = code - 1;
        if i + run > data.len() || n + run > out.len() {
            return None;
        }
        out[n..n + run].copy_from_slice(&data[i..i + run]);
        n += run;
        i += run;
        if code != 0xFF && i < data.len() {
            if n == out.len() {
                return None;
            }
            out[n] = 0;
            n += 1;
        }
    }
    Some(n)
}

/// What became of the bytes [`Decoder::push`] was given, counted.
#[derive(Clone, Copy, Default)]
pub struct Counts {
    /// Messages decoded whole, with a CRC that held.
    pub frames: u32,
    /// Messages that were not COBS, were too short to carry a CRC, or whose
    /// CRC failed.
    pub crc_errors: u32,
    /// Messages longer than [`MAX_WIRE`], dropped to their end.
    pub overruns: u32,
}

/// Takes the bytes off J5 one at a time and hands back each message whole.
pub struct Decoder {
    wire: [u8; MAX_WIRE],
    held: usize,
    /// Set once a message has run past [`MAX_WIRE`]: the rest of it, up to its
    /// zero, is thrown away.
    skipping: bool,
    message: [u8; MAX_MESSAGE + 2],
    pub counts: Counts,
}

impl Default for Decoder {
    fn default() -> Self {
        Self::new()
    }
}

impl Decoder {
    pub const fn new() -> Self {
        Self {
            wire: [0; MAX_WIRE],
            held: 0,
            skipping: false,
            message: [0; MAX_MESSAGE + 2],
            counts: Counts {
                frames: 0,
                crc_errors: 0,
                overruns: 0,
            },
        }
    }

    /// Forgets a message half heard: after a framing error on the UART, say.
    pub fn reset(&mut self) {
        self.held = 0;
        self.skipping = true;
    }

    /// Takes one byte, and returns the message it ends, as its type and body,
    /// if it ends one with a CRC that holds.
    pub fn push(&mut self, byte: u8) -> Option<(u8, &[u8])> {
        if byte != 0 {
            if self.skipping {
                return None;
            }
            if self.held == MAX_WIRE {
                self.counts.overruns += 1;
                self.held = 0;
                self.skipping = true;
                return None;
            }
            self.wire[self.held] = byte;
            self.held += 1;
            return None;
        }
        let held = core::mem::replace(&mut self.held, 0);
        if core::mem::replace(&mut self.skipping, false) || held == 0 {
            return None;
        }
        let n = match cobs_decode(&self.wire[..held], &mut self.message) {
            Some(n) if n >= 3 => n,
            _ => {
                self.counts.crc_errors += 1;
                return None;
            }
        };
        let crc = u16::from_le_bytes([self.message[n - 2], self.message[n - 1]]);
        if crc16(&self.message[..n - 2]) != crc {
            self.counts.crc_errors += 1;
            return None;
        }
        self.counts.frames += 1;
        Some((self.message[0], &self.message[1..n - 2]))
    }
}

#[cfg(test)]
mod tests {
    extern crate std;
    use super::*;
    use std::vec::Vec;

    #[test]
    fn imu_headers_reject_floating_and_malformed_reads() {
        assert_eq!(imu_header_length(&[0xFF; 4], 1024), None);
        assert_eq!(imu_header_length(&[3, 0, 2, 0], 1024), None);
        assert_eq!(imu_header_length(&[5, 0, 6, 0], 1024), None);
        assert_eq!(imu_header_length(&[1, 4, 2, 0], 1024), None);
        assert_eq!(imu_header_length(&[0, 0, 0, 0], 1024), Some(0));
        assert_eq!(imu_header_length(&[5, 0x80, 1, 12], 1024), Some(5));
        assert_eq!(imu_header_length(&[20, 0, 2, 3], 1024), Some(20));
        assert_eq!(imu_header_length(&[5, 0, 1], 1024), None);
    }

    fn wire(kind: u8, body: &[u8]) -> Vec<u8> {
        let mut out = [0u8; MAX_WIRE];
        let n = encode(kind, &[body], &mut out).unwrap();
        out[..n].to_vec()
    }

    fn decode_all(bytes: &[u8]) -> Vec<(u8, Vec<u8>)> {
        let mut decoder = Decoder::new();
        let mut out = Vec::new();
        for &b in bytes {
            if let Some((kind, body)) = decoder.push(b) {
                out.push((kind, body.to_vec()));
            }
        }
        out
    }

    #[test]
    fn crc_check_value() {
        assert_eq!(crc16(b"123456789"), 0x29B1);
    }

    /// The same messages and bytes as `sbc/diag_link.py`'s check. The CRCs
    /// are Python's `binascii.crc_hqx(message, 0xFFFF)`, a third
    /// implementation, and the COBS was done by hand.
    #[test]
    fn known_answers() {
        // 02, CRC B2 C1: no zero, so one run of three.
        assert_eq!(wire(host::PING, &[]), [0x04, 0x02, 0xB2, 0xC1, 0x00]);
        // A CAN_SEND to bus C: ID 0x7FF, a register read of ESC_ID at motor 1.
        // 10 02 00 FF 07 00 00 01 00 33 08, CRC C9 75.
        let body = [2, 0, 0xFF, 0x07, 0, 0, 0x01, 0x00, 0x33, 0x08];
        assert_eq!(
            wire(host::CAN_SEND, &body),
            [
                0x03, 0x10, 0x02, 0x03, 0xFF, 0x07, 0x01, 0x02, 0x01, 0x05, 0x33, 0x08, 0xC9, 0x75,
                0x00
            ]
        );
    }

    /// `sbc/diag_link.py`'s check holds the same bytes: 0.5 m/s, a turn of
    /// 1.5 rad/s to the right, 203.5 mm, live, the third jump.
    #[test]
    fn drive_known_answer() {
        let body = [0xF4, 0x01, 0x24, 0xFA, 0xF3, 0x07, 0x01, 0x03];
        assert_eq!(
            wire(host::DRIVE, &body),
            [0x0C, 0x11, 0xF4, 0x01, 0x24, 0xFA, 0xF3, 0x07, 0x01, 0x03, 0x2C, 0x92, 0x00]
        );
        assert_eq!(
            Drive::parse(&body),
            Some(Drive {
                forward_mm_s: 500,
                turn_mrad_s: -1500,
                height_tenth_mm: 2035,
                live: true,
                jump: 3,
            })
        );
        assert_eq!(Drive::parse(&body[..7]), None);
    }

    #[test]
    fn round_trips() {
        let mut long = Vec::new();
        for i in 0..MAX_MESSAGE - 1 {
            long.push((i % 7) as u8);
        }
        let bodies: [&[u8]; 6] = [&[], &[0], &[0, 0, 0], &[1; 253], &[1; 254], &long];
        let mut stream = Vec::new();
        for (k, body) in bodies.iter().enumerate() {
            stream.extend(wire(0x40 + k as u8, body));
        }
        let got = decode_all(&stream);
        assert_eq!(got.len(), bodies.len());
        for (k, body) in bodies.iter().enumerate() {
            assert_eq!(got[k].0, 0x40 + k as u8);
            assert_eq!(&got[k].1[..], *body);
        }
    }

    #[test]
    fn a_damaged_message_is_dropped_and_the_next_is_found() {
        let mut stream = wire(0x10, &[1, 2, 3, 4]);
        stream[3] ^= 0x20;
        stream.extend(wire(0x11, &[5, 6]));
        let got = decode_all(&stream);
        assert_eq!(got, [(0x11, std::vec![5, 6])]);
        let mut decoder = Decoder::new();
        for &b in &stream {
            decoder.push(b);
        }
        assert_eq!(decoder.counts.crc_errors, 1);
        assert_eq!(decoder.counts.frames, 1);
    }

    #[test]
    fn too_long_is_dropped_to_its_end() {
        let mut stream = std::vec![0x55u8; MAX_WIRE + 10];
        stream.push(0);
        stream.extend(wire(0x12, &[9]));
        let mut decoder = Decoder::new();
        let mut got = Vec::new();
        for &b in &stream {
            if let Some((kind, body)) = decoder.push(b) {
                got.push((kind, body.to_vec()));
            }
        }
        assert_eq!(got, [(0x12, std::vec![9])]);
        assert_eq!(decoder.counts.overruns, 1);
    }
}
