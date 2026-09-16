# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["schemdraw>=0.19"]
# ///
"""The controller carrier board, as a netlist that can be checked and drawn.

The carrier is the one piece of electronics on this robot that nobody sells: a
140 x 46 mm two-layer board on the electronics deck, carrying the WeAct core
board on sockets, three CAN-FD transceivers in DIP-8 sockets, the logic BEC and
the bus monitor, and the connectors everything else in the torso lands on. cad/electronics.py draws its envelope so
the torso can be packed around it; this file says what is soldered to what.

    uv run electrical/carrier.py            # check, then print the tables
    uv run electrical/carrier.py --draw     # also rewrite electrical/carrier.svg

WHY A NETLIST AND NOT A DRAWING. The same reason the CAD is a program. A drawing
can only be looked at, and looking is what let four filled bolt holes through
several rebuilds of the rotor hub. The equivalent mistake here is a pin that
cannot do the job it has been given -- FDCAN2 asked for on a pin that has no
FDCAN2 on it, or two peripherals quietly sharing one pin -- and check() below
answers that by table lookup rather than by eye. The drawing is generated from
the same data, so it cannot disagree with it.

PROVENANCE. Every pin number here came off a vendor document, read on
2026-09-14, and not off a shop listing or a pinout picture:

  * the core board's headers, from WeAct's own schematic, in
    WeActStudio.STM32G474CoreBoard, Hardware/QFN48/
    WeAct-STM32G474CoreBoard_V10_SchDoc.pdf;
  * which board that is, settled by measuring the vendor STEP beside it --
    WeAct-STM32G47x_CoreBoard_3D.step is 36.53 x 28.40 mm, the size
    cad/electronics.py draws and the size docs/BOM.md quotes;
  * the transceiver's pinout, from Microchip DS20005284A table 1-2, mirrored at
    reference/MCP2561-2FD_DS20005284A.pdf, which also gives the internal
    pull-ups on TXD and STBY that decide what this board does before any
    firmware runs;
  * which STM32G474 pin can carry which peripheral, from Zephyr's hal_stm32,
    dts/st/g4/stm32g474c(b-c-e)tx-pinctrl.dtsi, generated from ST's own database;
  * the motor's connector and its default bus speed, from
    reference/DM-J3507-2EC_manual_V1.0_EN.pdf.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "electrical" / "carrier.svg"


# ---- the core board ---------------------------------------------------------
#
# WeAct's STM32G474CEU6 core board, the 36.53 x 28.40 mm one. Two 2 x 12 headers
# and a 1 x 4 for SWD, numbered as the vendor schematic numbers them: odd pins
# down one row, even pins down the other.
#
# WHICH BOARD THIS IS MATTERS, and docs/BOM.md currently names two of them. Its
# purchase link points at WeAct's LONG type, a different board -- 63.06 x 18.24
# mm, two 1 x 20 headers, and PB8 not brought out to a header at all -- while
# its quoted dimension, its header note and cad/electronics.py all describe this
# one. This file is drawn to the board the CAD packs. docs/CARRIER.md has it.

WEACT_P1 = {
    1: "VCC",
    2: "VCC",
    3: "GND",
    4: "GND",
    5: "PB12",
    6: "PB13",
    7: "PB14",
    8: "PB15",
    9: "PC6",
    10: "PA8",
    11: "PA9",
    12: "PA10",
    13: "PA11",
    14: "PA12",
    15: "PA15",
    16: "PC10",
    17: "PC11",
    18: "PB3",
    19: "PB4",
    20: "PB5",
    21: "PB6",
    22: "PB7",
    23: "PB8",
    24: "PB9",
}

WEACT_P2 = {
    1: "3V3",
    2: "3V3",
    3: "GND",
    4: "GND",
    5: "PB11",
    6: "PB10",
    7: "PB2",
    8: "VREF+",
    9: "PB0",
    10: "PB1",
    11: "PA7",
    12: "PC4",
    13: "PA5",
    14: "PA6",
    15: "PA3",
    16: "PA4",
    17: "PA1",
    18: "PA2",
    19: "NRST",
    20: "PA0",
    21: "PC14",
    22: "PC15",
    23: "VB",
    24: "PC13",
}

WEACT_P3 = {1: "3V3", 2: "SWDIO", 3: "SWCLK", 4: "GND"}
# P3 is accessed on the removable core board, not soldered to the carrier.
OFF_BOARD_PINS = frozenset(("A1", f"P3-{n}") for n in WEACT_P3)

# VCC is the core board's pre-regulator rail. Its ME6239A33M3G takes 3.3-20 V in
# and makes the 3.3 V that comes back out on P2-1/2, so feeding the carrier's
# 5 V into P1-1/2 is how the board is powered here. SB9 on the core board ties
# VCC to the USB-C VBUS pin: 5 V fed in this way appears on that connector, so
# either do not plug a host in while the robot is powered, or cut SB9.


# ---- what each STM32G474 pin is allowed to be -------------------------------
#
# Only the peripherals this board uses, and only pins that exist on the 48-pin
# package. This is the table check() looks a signal up in, and it is what makes
# an assignment below a claim rather than a hope.

AF_TABLE = {
    "FDCAN1_RX": ("PA11", "PB8"),
    "FDCAN1_TX": ("PA12", "PB9"),
    "FDCAN2_RX": ("PB5", "PB12"),
    "FDCAN2_TX": ("PB6", "PB13"),
    "FDCAN3_RX": ("PA8", "PB3"),
    "FDCAN3_TX": ("PA15", "PB4"),
    "I2C1_SCL": ("PA13", "PA15", "PB8"),
    "I2C1_SDA": ("PA14", "PB7", "PB9"),
    "USART1_TX": ("PA9", "PB6"),
    "USART1_RX": ("PA10", "PB7"),
    "SYS": ("PB8", "NRST"),
}

# Pins whose reset state is a JTAG function. The debugger is SWD, which needs
# only PA13 and PA14, so these are free -- but only after firmware has taken
# them off JTAG, and until it does they sit as inputs with weak pull-ups. That
# is the safe direction for both of them: a CAN TXD pulled high is recessive,
# and an I2C clock pulled high is idle. PB3 is left unused on purpose so that
# SWO tracing still has a pin.
JTAG_AT_RESET = ("PA15", "PB3", "PB4")


@dataclass(frozen=True)
class Part:
    """One thing soldered to the carrier, and what its pins are called."""

    refdes: str
    description: str
    partNumber: str
    pins: dict[str, str] = field(default_factory=dict)


def _header_pins() -> dict[str, str]:
    """Every core board header pin, named the way the netlist refers to it."""
    pins = {}
    for header, table in (("P1", WEACT_P1), ("P2", WEACT_P2), ("P3", WEACT_P3)):
        for number, signal in table.items():
            pins[f"{header}-{number}"] = signal
    return pins


TRANSCEIVER_PINS = {
    "1": "TXD",
    "2": "VSS",
    "3": "VDD",
    "4": "RXD",
    "5": "VIO",
    "6": "CANL",
    "7": "CANH",
    "8": "STBY",
}

PARTS = [
    Part(
        "A1",
        "MCU core board, on two 2 x 12 sockets plus a 1 x 4 for SWD",
        "WeAct STM32G474CEU6 core board, 36.53 x 28.40 mm",
        _header_pins(),
    ),
    Part(
        "U1",
        "CAN-FD transceiver, bus A -- the two hips",
        "MCP2562FD-E/P in a DIP-8 socket",
        dict(TRANSCEIVER_PINS),
    ),
    Part(
        "U2",
        "CAN-FD transceiver, bus B -- the two knees",
        "MCP2562FD-E/P in a DIP-8 socket",
        dict(TRANSCEIVER_PINS),
    ),
    Part(
        "U3",
        "CAN-FD transceiver, bus C -- the two wheels",
        "MCP2562FD-E/P in a DIP-8 socket",
        dict(TRANSCEIVER_PINS),
    ),
    Part(
        "C1",
        "bulk, on the carrier's 5 V",
        "10 uF low-ESR electrolytic",
        {"1": "+", "2": "-"},
    ),
    Part("C2", "U1 VDD decoupling", "100 nF X7R", {"1": "1", "2": "2"}),
    Part("C3", "U1 VIO decoupling", "100 nF X7R", {"1": "1", "2": "2"}),
    Part("C4", "U2 VDD decoupling", "100 nF X7R", {"1": "1", "2": "2"}),
    Part("C5", "U2 VIO decoupling", "100 nF X7R", {"1": "1", "2": "2"}),
    Part("C6", "U3 VDD decoupling", "100 nF X7R", {"1": "1", "2": "2"}),
    Part("C7", "U3 VIO decoupling", "100 nF X7R", {"1": "1", "2": "2"}),
    Part(
        "C8",
        "3.3 V decoupling, by the sensor connectors",
        "100 nF X7R",
        {"1": "1", "2": "2"},
    ),
    Part(
        "R1",
        "I2C clock pull-up -- fit only if no sensor module has its own",
        "4.7 kOhm",
        {"1": "1", "2": "2"},
    ),
    Part(
        "R2",
        "I2C data pull-up -- fit only if no sensor module has its own",
        "4.7 kOhm",
        {"1": "1", "2": "2"},
    ),
    Part(
        "JP1",
        "IMU supply link: bridge 1-2 for 5 V, 2-3 for 3.3 V",
        "three holes on 2.54 mm, wire link",
        {"1": "+5V", "2": "IMU_V", "3": "+3V3"},
    ),
    # ---- what came up onto the carrier in September 2026 --------------------
    #
    # THE BEC AND THE BUS MONITOR ARE ON THIS BOARD NOW. Both were separately
    # mounted down in the power bay -- the BEC on a bracket over the harness
    # bank, the monitor on two printed pads off the rear wall -- with cables
    # running up to this one. Seven wires between the three of them became four,
    # and the I2C bus stopped leaving the board to reach the monitor at all,
    # which is the part that matters: an open-drain bus running 150 mm through a
    # torso is the classic way to lose an IMU to a locked-up monitor.
    #
    # WHAT DID NOT COME UP IS THE SHUNT, and it cannot: it stands in the main bus
    # path and carries the whole pack current. It stays at the distribution
    # board, and the monitor's IN+ and IN- are its own screw terminals with a
    # twisted pair run down to it. That pair carries about 75 mV at 25 V of
    # common mode, so it is twisted, it is not on this board's copper anywhere,
    # and it is the one measurement this move makes harder rather than easier.
    Part(
        "J1",
        "battery bus in, from the distribution board",
        "JST-XH 2-pin",
        {"1": "VBAT", "2": "GND"},
    ),
    Part(
        "F1",
        "branch protection on the bus feed -- the pack's own fuse is 30 A and "
        "this lead draws under two",
        "resettable PTC, 1.85 A hold, 72 V, radial -- Littelfuse RXEF185",
        {"1": "in", "2": "out"},
    ),
    Part(
        "C9",
        "bus input bulk, for the lead's inductance on a hot plug",
        "10 uF 50 V electrolytic",
        {"1": "+", "2": "-"},
    ),
    Part(
        "A2",
        "the logic BEC, lying flat on the carrier on a thermal sheet under two "
        "cable ties, component side up; its four pads face up and drop over four "
        "pins standing out of the board, in the order the module prints them",
        "Matek BEC12S-PRO, on four pins at 3.81 mm",
        {"1": "IN", "2": "G", "3": "G", "4": "OUT"},
    ),
    # THE MONITOR LANDS ON ALL EIGHT OF ITS PINS, September 2026. It was drawn as
    # five of them into a header standing beside the module, which is not a thing
    # that can be built: a module's pins go where its pins are. All eight come
    # down into this board now, its shunt inputs included, so the twisted pair
    # from the shunt lands on J7 here rather than in the screw terminals on the
    # module. REMOVE THE MODULE'S R100 (0.1 OHM) before connecting the external
    # Kelvin pair. Otherwise sense-wire current corrupts the measurement;
    # even ideal zero-ohm sense wires would cause about 0.99 percent error.
    Part(
        "A3",
        "the bus monitor, on two M2 standoffs, landed on all eight of its pins; "
        "its screw terminals are left empty and the shunt pair comes in on J7",
        "INA226 breakout, on a 1 x 8 header",
        {
            "1": "VCC",
            "2": "GND",
            "3": "SDA",
            "4": "SCL",
            "5": "ALE",
            "6": "VBS",
            "7": "IN-",
            "8": "IN+",
        },
    ),
    Part(
        "J7",
        "the shunt's sense pair, down to the shunt at the distribution board -- "
        "twisted, and about 75 mV at pack common mode",
        "JST-XH 2-pin",
        {"1": "IN+", "2": "IN-"},
    ),
    Part(
        "J2",
        "bus A out -- left hip on 1/2, right hip on 3/4",
        "JST-XH 4-pin",
        {"1": "H", "2": "L", "3": "H", "4": "L"},
    ),
    Part(
        "J3",
        "bus B out -- left knee on 1/2, right knee on 3/4",
        "JST-XH 4-pin",
        {"1": "H", "2": "L", "3": "H", "4": "L"},
    ),
    Part(
        "J4",
        "bus C out -- left wheel on 1/2, right wheel on 3/4",
        "JST-XH 4-pin",
        {"1": "H", "2": "L", "3": "H", "4": "L"},
    ),
    # THE SBC'S POWER TRAVELS WITH ITS SERIAL LINK NOW, because the BEC that
    # used to feed it directly is on this board. Two pins for the 5 V and two
    # for its return: a JST-XH contact is rated 3 A and the Banana Pi draws
    # something under 2, so one pin would carry it, and two is what makes the
    # pair a pair rather than a single point of failure on the rail that holds
    # the whole computer up. GND is on pin 1 and again on pin 4, between the
    # power and the four signals. THE PAIRS ARE ADJACENT rather than interleaved,
    # which halves the loop the SBC's supply current runs in and is also the only
    # arrangement the board can wire: a ground pin with a 5 V pin either side of it
    # is 0.8 mm from each, and nothing reaches it -- not a track, and not the
    # ground plane either.
    Part(
        "J5",
        "the SBC: its 5 V, its serial link, and the two lines that let it "
        "reflash the MCU",
        "JST-XH 8-pin",
        {
            "1": "GND",
            "2": "GND",
            "3": "+5V",
            "4": "+5V",
            "5": "TXD",
            "6": "RXD",
            "7": "BOOT0",
            "8": "NRST",
        },
    ),
    # THE TWO I2C LINES ARE AT THE ENDS OF THIS CONNECTOR and the rest is in the
    # middle, which is a layout decision showing through into the netlist and is
    # worth saying so. A row of six pads on 2.5 mm pitch leaves 0.8 mm between
    # neighbours, and nothing goes through a 0.8 mm gap at this board's rules --
    # not a track and not the ground plane -- so an interior pin can only be
    # reached from in front of the row or behind it, and those two lanes are the
    # most congested copper on the board. The clock could not be routed at all
    # with it in the middle of the row.
    Part(
        "J6",
        "IMU",
        "JST-XH 6-pin",
        {"1": "SCL", "2": "GND", "3": "V", "4": "INT", "5": "RST", "6": "SDA"},
    ),
]


# ---- what the MCU's pins are doing ------------------------------------------
#
# The net, the port pin, the peripheral function it has to be, and the header
# pin it comes out on. check() holds all four against each other and against
# AF_TABLE, so a pin that cannot do its job fails here rather than on the bench.
#
# BUS A IS ON PA11/PA12 AND NOT ON PB8/PB9, which is the one place this differs
# from the arrangement docs/BOM.md describes, and the reason is a power-up race
# rather than a preference. PB8 is the BOOT0 pin. A transceiver's RXD idles high
# on a quiet bus, so wiring RXD to PB8 means the level the MCU samples to decide
# where to boot from is whatever the transceiver happens to be doing at that
# instant -- flash if the 5 V rail is still below the transceiver's 4 V
# undervoltage threshold, the system bootloader if it is not. The cure is to
# take the boot source off the pin in the option bytes, which works, but it is a
# step that has to be done before the robot will start at all and it cannot be
# undone without a debugger. Putting bus A on PA11/PA12 costs the core board's
# USB instead, and nothing in this robot uses it: the SBC link is serial and the
# programmer is SWD.

MCU_SIGNALS = [
    ("CANA_TX", "PA12", "FDCAN1_TX", "P1-14"),
    ("CANA_RX", "PA11", "FDCAN1_RX", "P1-13"),
    ("CANB_TX", "PB13", "FDCAN2_TX", "P1-6"),
    ("CANB_RX", "PB12", "FDCAN2_RX", "P1-5"),
    ("CANC_TX", "PB4", "FDCAN3_TX", "P1-19"),
    ("CANC_RX", "PA8", "FDCAN3_RX", "P1-10"),
    ("I2C_SCL", "PA15", "I2C1_SCL", "P1-15"),
    ("I2C_SDA", "PB7", "I2C1_SDA", "P1-22"),
    ("SBC_MCU_TXD", "PA9", "USART1_TX", "P1-11"),
    ("SBC_MCU_RXD", "PA10", "USART1_RX", "P1-12"),
    ("IMU_INT", "PB5", "GPIO", "P1-20"),
    ("IMU_RST", "PB6", "GPIO", "P1-21"),
    ("INA_ALERT", "PB15", "GPIO", "P1-8"),
    ("BOOT0", "PB8", "SYS", "P1-23"),
    ("NRST", "NRST", "SYS", "P2-19"),
]


# ---- the netlist ------------------------------------------------------------

NETS: dict[str, list[tuple[str, str]]] = {
    # THE BUS, from the connector to the BEC's input, and it is the only thing on
    # this board that is not a logic rail. It arrives at pack voltage -- 25.2 V
    # on a full 6S string, and higher than that while a leg is regenerating --
    # so it is fused at the board rather than relying on the 30 A fuse that
    # protects the pack. Past the fuse it feeds the BEC, and it is also what the
    # monitor measures its bus voltage against: VBS is a high-impedance input, so
    # it costs nothing to take it off the fused side, and what it reads is the
    # pack less the fuse's own drop -- about 50 mV of 25 V at the 1.3 A this lead
    # carries. A pack reading that is 0.2 % low is worth more than an unfused
    # track across the board.
    "VBAT": [("J1", "1"), ("F1", "1")],
    "VBAT_F": [("F1", "2"), ("C9", "1"), ("A2", "1"), ("A3", "6")],
    # Power. 5 V comes out of the BEC and feeds the transceivers, the SBC and
    # the core board through its own regulator; the 3.3 V that regulator makes
    # comes back out and is what sets the logic level on every VIO pin. That
    # split is the whole reason the bill buys MCP2562FD rather than MCP2561FD.
    "+5V": [
        ("A2", "4"),
        ("J5", "3"),
        ("J5", "4"),
        ("C1", "1"),
        ("A1", "P1-1"),
        ("A1", "P1-2"),
        ("U1", "3"),
        ("C2", "1"),
        ("U2", "3"),
        ("C4", "1"),
        ("U3", "3"),
        ("C6", "1"),
        ("JP1", "1"),
    ],
    "+3V3": [
        ("A1", "P2-1"),
        ("A1", "P2-2"),
        ("C8", "1"),
        ("U1", "5"),
        ("C3", "1"),
        ("U2", "5"),
        ("C5", "1"),
        ("U3", "5"),
        ("C7", "1"),
        ("R1", "1"),
        ("R2", "1"),
        ("JP1", "3"),
        ("A3", "1"),
    ],
    "GND": [
        ("J1", "2"),
        ("A2", "2"),
        ("A2", "3"),
        ("C9", "2"),
        ("C1", "2"),
        ("C2", "2"),
        ("C3", "2"),
        ("C4", "2"),
        ("C5", "2"),
        ("C6", "2"),
        ("C7", "2"),
        ("C8", "2"),
        ("A1", "P1-3"),
        ("A1", "P1-4"),
        ("A1", "P2-3"),
        ("A1", "P2-4"),
        # STBY is pulled up inside the transceiver, about 1.1 MOhm to VIO, so a
        # pin left floating is standby and not normal mode. Tied down rather
        # than driven from a GPIO: nothing here wants a transceiver asleep, and
        # a line that has to be driven correctly before any bus works is one
        # more thing to get wrong at bring-up.
        ("U1", "2"),
        ("U1", "8"),
        ("U2", "2"),
        ("U2", "8"),
        ("U3", "2"),
        ("U3", "8"),
        ("J5", "1"),
        ("J5", "2"),
        ("J6", "2"),
        ("A3", "2"),
    ],
    "IMU_V": [("JP1", "2"), ("J6", "3")],
    # The three buses. Each one is a single line: a motor at one end, the
    # carrier in the middle, that joint's opposite number at the other end. Both
    # ends are motors, both motors' own termination switches stay ON, and that
    # is why there is no 120 Ohm anywhere on this board.
    "CANA_TX": [("A1", "P1-14"), ("U1", "1")],
    "CANA_RX": [("A1", "P1-13"), ("U1", "4")],
    "CANA_H": [("U1", "7"), ("J2", "1"), ("J2", "3")],
    "CANA_L": [("U1", "6"), ("J2", "2"), ("J2", "4")],
    "CANB_TX": [("A1", "P1-6"), ("U2", "1")],
    "CANB_RX": [("A1", "P1-5"), ("U2", "4")],
    "CANB_H": [("U2", "7"), ("J3", "1"), ("J3", "3")],
    "CANB_L": [("U2", "6"), ("J3", "2"), ("J3", "4")],
    "CANC_TX": [("A1", "P1-19"), ("U3", "1")],
    "CANC_RX": [("A1", "P1-10"), ("U3", "4")],
    "CANC_H": [("U3", "7"), ("J4", "1"), ("J4", "3")],
    "CANC_L": [("U3", "6"), ("J4", "2"), ("J4", "4")],
    # One I2C bus for both sensors: the IMU in its seat on the shell floor, and
    # the INA226 on this board watching the battery bus through the shunt.
    "I2C_SCL": [("A1", "P1-15"), ("R1", "2"), ("J6", "1"), ("A3", "4")],
    "I2C_SDA": [("A1", "P1-22"), ("R2", "2"), ("J6", "6"), ("A3", "3")],
    "IMU_INT": [("A1", "P1-20"), ("J6", "4")],
    "IMU_RST": [("A1", "P1-21"), ("J6", "5")],
    "INA_ALERT": [("A1", "P1-8"), ("A3", "5")],
    # THE SHUNT'S SENSE PAIR, and it is the only differential measurement on this
    # robot. It leaves on J7, twisted, down to the shunt in the main bus path at
    # the distribution board, and it carries about 75 mV riding on pack voltage.
    # Keep the two tracks beside each other over the plane: what they pick up
    # between here and the connector is what the monitor reads as current.
    "SHUNT_P": [("A3", "8"), ("J7", "1")],
    "SHUNT_N": [("A3", "7"), ("J7", "2")],
    # The SBC. A serial link rather than USB, and BOOT0 and reset travel with it
    # so the Banana Pi can drop the MCU into its own bootloader and reflash it
    # over the same wires. That matters on a robot whose controller sits under a
    # screwed-down lid: USART1 is one of the ports the STM32's ROM bootloader
    # listens on, so no other access is needed to change firmware.
    "SBC_MCU_TXD": [("A1", "P1-11"), ("J5", "5")],
    "SBC_MCU_RXD": [("A1", "P1-12"), ("J5", "6")],
    "BOOT0": [("A1", "P1-23"), ("J5", "7")],
    "NRST": [("A1", "P2-19"), ("J5", "8")],
}

# Pins left unconnected on purpose, and why. check() reports every pin that is
# on neither a net nor this list, so a pin that was forgotten cannot hide among
# the pins that were left out deliberately.
UNCONNECTED = {
    ("A1", f"P3-{n}"): "SWD header -- the ST-Link lands here, not on the carrier"
    for n in WEACT_P3
}
UNCONNECTED.update(
    {
        ("A1", f"P1-{n}"): "spare"
        for n in WEACT_P1
        if f"P1-{n}" not in {row[3] for row in MCU_SIGNALS}
        and WEACT_P1[n] not in ("VCC", "GND")
    }
)
UNCONNECTED.update(
    {
        ("A1", f"P2-{n}"): "spare"
        for n in WEACT_P2
        if f"P2-{n}" not in {row[3] for row in MCU_SIGNALS}
        and WEACT_P2[n] not in ("3V3", "GND")
    }
)


# ---- the checks -------------------------------------------------------------


def check() -> list[str]:
    """Everything that can be decided by table lookup. Returns the complaints."""
    faults: list[str] = []
    parts = {part.refdes: part for part in PARTS}

    # 1. Every endpoint names a part and a pin that exists on it.
    for net, endpoints in NETS.items():
        for refdes, pin in endpoints:
            if refdes not in parts:
                faults.append(f"{net}: no such part {refdes}")
            elif pin not in parts[refdes].pins:
                faults.append(f"{net}: {refdes} has no pin {pin}")

    # 2. No net is a dead end, and no pin is on two nets.
    seen: dict[tuple[str, str], str] = {}
    for net, endpoints in NETS.items():
        if len(endpoints) < 2:
            faults.append(f"{net}: only {len(endpoints)} endpoint, so it goes nowhere")
        for endpoint in endpoints:
            if endpoint in seen:
                faults.append(
                    f"{endpoint[0]}-{endpoint[1]}: on both {seen[endpoint]} and {net}"
                )
            seen[endpoint] = net

    # 3. Every pin of every part is either on a net or excused.
    for part in PARTS:
        for pin in part.pins:
            if (part.refdes, pin) not in seen and (part.refdes, pin) not in UNCONNECTED:
                faults.append(f"{part.refdes}-{pin} is on no net and is not excused")

    # 4. The MCU signals. The port pin must be able to carry the function, the
    #    header pin must actually be that port pin, the net must reach the
    #    header pin, and no port pin may be asked to do two jobs.
    ports: dict[str, str] = {}
    for net, port, function, header in MCU_SIGNALS:
        if function != "GPIO" and port not in AF_TABLE.get(function, ()):
            allowed = ", ".join(AF_TABLE.get(function, ())) or "nothing"
            faults.append(f"{net}: {port} cannot be {function} -- only {allowed}")
        table = WEACT_P1 if header.startswith("P1") else WEACT_P2
        number = int(header.split("-")[1])
        if table.get(number) != port:
            faults.append(
                f"{net}: {header} is {table.get(number)} on the core board, not {port}"
            )
        if ("A1", header) not in NETS.get(net, []):
            faults.append(f"{net}: the netlist does not connect A1-{header}")
        if port in ports:
            faults.append(f"{port}: asked to be both {ports[port]} and {net}")
        ports[port] = net

    # 5. Every transceiver is fully supplied. A CAN transceiver with VIO left
    #    off still transmits and never receives, which is the failure this
    #    catches before it is diagnosed on the bench.
    for refdes in ("U1", "U2", "U3"):
        for pin, rail in (("3", "+5V"), ("5", "+3V3"), ("2", "GND"), ("8", "GND")):
            if (refdes, pin) not in NETS[rail]:
                name = parts[refdes].pins[pin]
                faults.append(f"{refdes} {name} is not on {rail}")

    return faults


# ---- the tables -------------------------------------------------------------


def pin_map() -> str:
    lines = ["MCU pin map", ""]
    lines.append(f"  {'net':<14}{'port':<7}{'function':<12}{'header':<9}note")
    for net, port, function, header in MCU_SIGNALS:
        note = "JTAG at reset; needs SWD-only" if port in JTAG_AT_RESET else ""
        lines.append(f"  {net:<14}{port:<7}{function:<12}{header:<9}{note}")
    return "\n".join(lines)


def connectors() -> str:
    lines = ["Connectors", ""]
    net_of = {
        (refdes, pin): net
        for net, endpoints in NETS.items()
        for refdes, pin in endpoints
    }
    for part in PARTS:
        if not part.refdes.startswith(("J", "JP")):
            continue
        lines.append(f"  {part.refdes}  {part.partNumber} -- {part.description}")
        for pin, name in part.pins.items():
            net = net_of.get((part.refdes, pin), "--")
            lines.append(f"      {pin}  {name:<8}{net}")
        lines.append("")
    return "\n".join(lines).rstrip()


def netlist() -> str:
    lines = ["Netlist", ""]
    for net, endpoints in NETS.items():
        joined = "  ".join(f"{refdes}-{pin}" for refdes, pin in endpoints)
        lines.append(f"  {net:<14}{joined}")
    return "\n".join(lines)


def parts_list() -> str:
    lines = ["Parts", ""]
    for part in PARTS:
        lines.append(f"  {part.refdes:<5}{part.partNumber}")
        lines.append(f"       {part.description}")
    # There was a U4 here, an empty DIP-8 socket for the spare transceiver. The
    # printed board has no room for it: electrical/carrier_pcb.py puts the SBC's
    # standoffs, the BEC and the monitor on a 140 x 46 mm board and a fourth
    # socket does not fit. The spare stays in its bag.
    return "\n".join(lines)


# ---- the drawing ------------------------------------------------------------


# schemdraw places a block by the BOTTOM LEFT corner of its body and grows it up
# and to the right, and a block widens on its own to fit the longest pin name --
# so nothing below assumes a height or a width. Each block is placed, then asked
# where its pins actually ended up, and the captions and the wires are hung off
# that. It is the same habit as the rest of this repository: measure the thing
# that was built rather than the thing that was intended.

PIN_PITCH = 0.8
EDGE_PAD = 0.9
LEAD = 1.0


def _extent(block) -> tuple[float, float, float, float]:
    """Where a placed block's leads reach: left, right, bottom, top."""
    points = list(block.absanchors.values())
    return (
        min(point[0] for point in points),
        max(point[0] for point in points),
        min(point[1] for point in points),
        max(point[1] for point in points),
    )


def draw(path: Path) -> None:
    """Render the netlist as a schematic sheet.

    Net labels rather than a rat's nest of wires, except on the CAN pairs, where
    the shape of the connection is the thing worth seeing: each bus leaves its
    transceiver as one pair and lands on two motors, so the carrier is a point
    on the line and not a spur hanging off it. Everything else is named, which
    is how a sheet this dense stays readable, and which is also why the drawing
    cannot drift from the netlist -- both come off the tables above.
    """
    import schemdraw
    from schemdraw import elements as elm

    schemdraw.use("svg")
    parts = {part.refdes: part for part in PARTS}

    # Heights worked out from the pin counts rather than measured after the
    # fact, so the three columns can be centred against each other before any
    # of them is placed.
    def column(pins: int) -> float:
        return (pins - 1) * PIN_PITCH + 2 * EDGE_PAD

    busPitch = 8.0
    asideGap = 1.8
    mcuHeight = column(len(MCU_SIGNALS))
    busHeight = 2 * busPitch + column(4)

    buses = [
        ("U3", "J4", "C", "wheel", "CANC"),
        ("U2", "J3", "B", "knee", "CANB"),
        ("U1", "J2", "A", "hip", "CANA"),
    ]
    aside = [
        ("J7", ["+3V3", "GND", "I2C_SCL", "I2C_SDA", "INA_ALERT"]),
        ("J6", ["IMU_V", "GND", "I2C_SCL", "I2C_SDA", "IMU_INT", "IMU_RST"]),
        ("J5", ["GND", "SBC_MCU_TXD", "SBC_MCU_RXD", "BOOT0", "NRST"]),
        ("J1", ["+5V", "GND"]),
        ("JP1", ["+5V", "IMU_V", "+3V3"]),
    ]
    # The passives, as rows of one component each: what it is, which rail it
    # sits on, and where its other end goes. Three of the rows stand for three
    # parts apiece, one at each transceiver, because drawing nine identical
    # capacitors would say nothing the caption does not.
    passives = [
        ("C1", "10 uF", "+5V", None, "bulk, by the cable the SBC takes 5 V on"),
        ("C2 C4 C6", "100 nF", "+5V", None, "one at every transceiver's VDD"),
        ("C3 C5 C7", "100 nF", "+3V3", None, "one at every transceiver's VIO"),
        ("C8", "100 nF", "+3V3", None, "by the sensor connectors"),
        ("R1", "4.7 kOhm", "+3V3", "I2C_SCL", "fit only if no module has its own"),
        ("R2", "4.7 kOhm", "+3V3", "I2C_SDA", "fit only if no module has its own"),
    ]
    asideHeight = sum(column(len(nets)) + asideGap for _, nets in aside) - asideGap

    def caption(block, text: str, size: int = 10) -> None:
        left, right, _, top = _extent(block)
        d.add(
            elm.Label()
            .label(text, fontsize=size)
            .at(((left + right) / 2, top + EDGE_PAD + 0.7))
        )

    def stub(anchor, text: str, side: str) -> None:
        loc, align = ("left", "right") if side == "left" else ("right", "left")
        d.add(
            elm.Dot(open=True).at(anchor).label(text, loc=loc, fontsize=9, halign=align)
        )

    with schemdraw.Drawing(file=str(path), show=False) as d:
        d.config(fontsize=11, unit=1.0)

        # ---- A1, the core board ---------------------------------------------
        mcu = elm.Ic(
            pins=[
                # Listed bottom upwards, which is the order schemdraw places
                # them in, so that the buses come out at the top beside the
                # transceivers they feed.
                elm.IcPin(name=net, pin=header, side="right", anchorname=net)
                for net, _, _, header in reversed(MCU_SIGNALS)
            ]
            + [
                elm.IcPin(name="SWD", pin="P3", side="left", anchorname="SWD"),
                elm.IcPin(
                    name="GND", pin="P1-3,4 P2-3,4", side="left", anchorname="GND"
                ),
                elm.IcPin(name="+3V3", pin="P2-1,2", side="left", anchorname="V3"),
                elm.IcPin(name="+5V", pin="P1-1,2", side="left", anchorname="V5"),
            ],
            w=5.0,
            pinspacing=PIN_PITCH,
            edgepadH=EDGE_PAD,
            leadlen=LEAD,
        ).at((0, (asideHeight - mcuHeight) / 2))
        d += mcu
        caption(
            mcu,
            "A1   WeAct STM32G474CEU6 core board, 36.53 x 28.40 mm\n"
            "on two 2 x 12 sockets; SWD on its own 1 x 4",
            11,
        )
        for net, port, _, _ in MCU_SIGNALS:
            stub(getattr(mcu, net), f"  {port}", "right")
        for anchor, text in (
            ("V5", "+5V  "),
            ("V3", "+3V3  "),
            ("GND", "GND  "),
            ("SWD", "ST-Link  "),
        ):
            stub(getattr(mcu, anchor), text, "left")

        mcuLeft, mcuRight, _, mcuTop = _extent(mcu)
        busX = mcuRight + 4.2
        busBase = (asideHeight - busHeight) / 2

        # ---- one transceiver and one pair of motors per bus -----------------
        busTop = 0.0
        for index, (refdes, connector, letter, joint, prefix) in enumerate(buses):
            transceiver = elm.Ic(
                pins=[
                    elm.IcPin(name="STBY", pin="8", side="left", anchorname="STBY"),
                    elm.IcPin(name="VIO", pin="5", side="left", anchorname="VIO"),
                    elm.IcPin(name="VDD", pin="3", side="left", anchorname="VDD"),
                    elm.IcPin(name="RXD", pin="4", side="left", anchorname="RXD"),
                    elm.IcPin(name="TXD", pin="1", side="left", anchorname="TXD"),
                    elm.IcPin(name="CANL", pin="6", side="right", anchorname="CANL"),
                    elm.IcPin(name="CANH", pin="7", side="right", anchorname="CANH"),
                    elm.IcPin(name="VSS", pin="2", side="bottom", anchorname="VSS"),
                ],
                w=4.6,
                pinspacing=PIN_PITCH,
                edgepadH=EDGE_PAD,
                leadlen=LEAD,
            ).at((busX, busBase + index * busPitch))
            d += transceiver
            caption(
                transceiver,
                f"{refdes}   MCP2562FD-E/P in a DIP-8 socket\n"
                f"bus {letter}  --  the two {joint}s",
            )
            for anchor, text in (
                ("TXD", f"{prefix}_TX  "),
                ("RXD", f"{prefix}_RX  "),
                ("VDD", "+5V  "),
                ("VIO", "+3V3  "),
            ):
                stub(getattr(transceiver, anchor), text, "left")

            d += elm.Ground().at(transceiver.VSS)
            d += (
                elm.Ground()
                .at(transceiver.STBY)
                .label("tied low\n= awake", loc="bottom", fontsize=8)
            )

            # The junction that puts the carrier ON each line rather than off
            # it. One pair leaves the transceiver and immediately becomes two,
            # one to each of the joint's two motors, which is why both far ends
            # are a motor and neither end is this board.
            anchors = transceiver.absanchors
            high, low = anchors["CANH"], anchors["CANL"]
            highX = high[0] + 1.0
            lowX = highX + 0.8
            labelX = lowX + 1.4
            for start, joinX, rise, pins, letters in (
                (high, highX, 1.0, (1, 3), "H"),
                (low, lowX, -1.0, (2, 4), "L"),
            ):
                d += elm.Line().at(start).to((joinX, start[1]))
                d += elm.Dot().at((joinX, start[1]))
                d += (
                    elm.Line()
                    .at((joinX, start[1]))
                    .to((labelX, start[1]))
                    .label(
                        f"{connector}-{pins[0]}  {letters}   left {joint}",
                        loc="right",
                        fontsize=9,
                        halign="left",
                    )
                )
                d += elm.Line().at((joinX, start[1])).to((joinX, start[1] + rise))
                d += (
                    elm.Line()
                    .at((joinX, start[1] + rise))
                    .to((labelX, start[1] + rise))
                    .label(
                        f"{connector}-{pins[1]}  {letters}   right {joint}",
                        loc="right",
                        fontsize=9,
                        halign="left",
                    )
                )
            busTop = max(busTop, _extent(transceiver)[3])

        d += (
            elm.Label()
            .label(
                "No 120 Ohm anywhere on this board.\n"
                "Both ends of every bus are a motor, and\n"
                "both motors keep their own termination in.",
                fontsize=10,
            )
            .at((busX + 7.0, busBase - 3.2))
        )

        # ---- everything else that plugs into the carrier --------------------
        asideX = busX + 14.5
        asideY = 0.0
        asideTop = 0.0
        for refdes, nets in aside:
            part = parts[refdes]
            names = list(part.pins.values())
            block = elm.Ic(
                pins=[
                    elm.IcPin(name=name, pin=str(number), side="left")
                    for number, name in reversed(list(enumerate(names, start=1)))
                ],
                w=2.2,
                pinspacing=PIN_PITCH,
                edgepadH=EDGE_PAD,
                leadlen=LEAD,
            ).at((asideX, asideY))
            d += block
            caption(block, f"{refdes}   {part.partNumber}\n{part.description}", 9)
            for index, net in enumerate(nets):
                stub(getattr(block, f"inL{len(nets) - index}"), f"{net}  ", "left")
            asideTop = _extent(block)[3]
            asideY += column(len(nets)) + asideGap

        # ---- the passives, under the core board -----------------------------
        passiveY = (asideHeight - mcuHeight) / 2 - 2.4
        d += (
            elm.Label()
            .label("Decoupling and pull-ups", fontsize=11)
            .at((mcuLeft + 3.4, passiveY + 1.4))
        )
        for refdes, value, rail, sink, why in passives:
            start = (mcuLeft + 0.6, passiveY)
            d += (
                elm.Dot(open=True)
                .at(start)
                .label(f"{rail}  ", loc="left", fontsize=9, halign="right")
            )
            body = elm.Resistor() if refdes.startswith("R") else elm.Capacitor()
            d += (
                body.at(start)
                .right()
                .length(2.0)
                .label(f"{refdes}\n{value}", fontsize=9)
            )
            if sink is None:
                d += elm.Ground().at(body.end)
            else:
                d += (
                    elm.Dot(open=True)
                    .at(body.end)
                    .label(f"  {sink}", loc="right", fontsize=9, halign="left")
                )
            d += elm.Label().label(why, fontsize=8).at((mcuLeft + 6.6, passiveY - 0.55))
            passiveY -= 2.2

        d += (
            elm.Label()
            .label(
                "CONTROLLER CARRIER  --  76 x 46 mm of 2.54 mm perfboard, "
                "on the electronics deck\n"
                "generated by electrical/carrier.py from the netlist it checks"
                "  --  do not edit",
                fontsize=13,
            )
            .at(((mcuLeft + asideX) / 2, max(mcuTop, busTop, asideTop) + 2.6))
        )


# ---- entry point ------------------------------------------------------------


def main() -> int:
    faults = check()
    if faults:
        print("carrier: FAILED")
        for fault in faults:
            print(f"  {fault}")
        return 1

    print("carrier: every pin checks out\n")
    print(pin_map())
    print()
    print(connectors())
    print()
    print(netlist())
    print()
    print(parts_list())

    if "--draw" in sys.argv:
        draw(SVG)
        print(f"\nwrote {SVG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
