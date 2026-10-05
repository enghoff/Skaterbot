# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy>=1.26"]
# ///
"""C1 reset regression using KiCad's shared ngspice (Windows).

Run: uv run electrical/power_reset.py
Simplified semiconductor models: this regression is NOT an SOA qualification,
a thermal/leakage qualification, or a guaranteed hardware inrush specification.
It checks cold connection with ON held and rapid restart with a resistive load.
"""

import ctypes as ct
import os

import numpy as np
import power

kicad_bin = os.path.join(
    os.environ.get("KICAD_ROOT", "C:/Program Files/KiCad/10.0"), "bin"
)
dll_directory = os.add_dll_directory(kicad_bin)
lib = ct.CDLL(os.path.join(kicad_bin, "ngspice.dll"))
messages = []


@ct.CFUNCTYPE(ct.c_int, ct.c_char_p, ct.c_int, ct.c_void_p)
def output(s, i, u):
    messages.append(s.decode(errors="replace"))
    return 0


@ct.CFUNCTYPE(ct.c_int, ct.c_int, ct.c_bool, ct.c_bool, ct.c_int, ct.c_void_p)
def exited(s, a, b, i, u):
    messages.append(f"exit {s}")
    return 0


lib.ngSpice_Init(output, None, exited, None, None, None, None)


class Vector(ct.Structure):
    _fields_ = [
        ("name", ct.c_char_p),
        ("type", ct.c_int),
        ("flags", ct.c_short),
        ("real", ct.POINTER(ct.c_double)),
        ("complex", ct.c_void_p),
        ("length", ct.c_int),
    ]


lib.ngGet_Vec_Info.restype = ct.POINTER(Vector)
lib.ngGet_Vec_Info.argtypes = [ct.c_char_p]


def run(net):
    messages.clear()
    lib.ngSpice_Command(b"destroy all")
    lines = [s.encode() for s in net.splitlines()] + [None]
    arr = (ct.c_char_p * len(lines))(*lines)
    if lib.ngSpice_Circ(arr):
        raise RuntimeError(messages)
    lib.ngSpice_Command(b"run")

    def vec(name):
        ptr = lib.ngGet_Vec_Info(name.encode())
        if not ptr:
            raise RuntimeError(messages)
        v = ptr.contents
        return np.ctypeslib.as_array(v.real, shape=(v.length,)).copy()

    return {n: vec(n) for n in ["time", "v(s)", "v(g)", "v(m)", "v(d)", "i(vsense)"]}


def fixture(
    new=True,
    bus=25.2,
    beta=200,
    cscale=1,
    gscale=1,
    threshold=2,
    off=0.4,
    gap=0.001,
    rload=1000,
):
    extra = ""
    if new:
        extra = f"C7 s g {power.C_GATE_SOURCE * gscale}\nR25 g rb {power.R_RESET_BASE}\nR26 s rc {power.R_RESET_COLLECTOR}\nQ5 rc rb m reset"
    # FOUR DEVICES ON TWO GATE RESISTORS since 2026-09-22, which is how the board
    # is built: R3 feeds Q1 and Q6, R4 feeds Q2 and Q7. The per-gate capacitances
    # are therefore two devices' worth of an IRF4905 -- Ciss 3400 pF less Crss
    # 640 leaves 2.76 nF of Cgs each, and Crss is 640 pF each -- against the one
    # device's worth of the obsolete Vishay part they replace. rs and rd carry
    # the 20 mOhm channel the same way, five times the 6.7 that was here.
    return f"""Reset probe - simplified analytical MOSFET, not a manufacturer model
Vbat s 0 PWL(0 0 1u {bus})
Vcmd cmd 0 PWL(0 1 {off} 1 {off + 1e-7} 0 {off + gap} 0 {off + gap + 1e-7} 1)
Srequest pull 0 cmd 0 sw
.model sw sw(ron=.1 roff=1e12 vt=.5 vh=.1)
R2 s g {power.R_GATE_SOURCE}
R5 g pull {power.R_GATE_PULL}
D1 g s z15
.model z15 d(is=1e-12 bv=15 ibv=1u)
R8 s fb {power.R_FAST_OFF_BASE}
R9 fb fe 1meg
D3 fb pull si
Q4 s fb fe fast
D2 fe g si
D8 m g si
C1 m d {power.C_MILLER * cscale}
{"" if new else "R24 s m 10meg"}
{extra}
.model si d(is=2.5n n=1.75 rs=.6 cjo=4p tt=4n bv=100)
.model fast npn(is=1e-14 bf={beta} vaf=100 ikf=.1 cje=12p cjc=4p tf=.5n)
.model reset npn(is=1e-14 bf={beta} vaf=100 ikf=.1 cje=12p cjc=4p tf=.5n)
R3 g g1 10
R4 g g2 10
M1 x g1 s s pm
M6 x g1 s s pm
M2 x g2 s s pm
M7 x g2 s s pm
.model pm pmos(level=1 vto=-{threshold} kp=30 rs=.01 rd=.01)
Cgs1 s g1 5.52n
Cgs2 s g2 5.52n
Cgd1 g1 d 1280p
Cgd2 g2 d 1280p
Cds s d 2n
Vsense x d 0
Cload d 0 1540u
Rload d 0 {rload}
.options reltol=1e-4 abstol=1e-10 method=gear
.tran 2u {off + gap + 0.4} 0 2u
.end
"""


def check_connections():
    # Explicitly bind every gate-network terminal in the model to power.py.
    expected = {
        "R2": ("VSRC", "GATE"),
        "R3": ("GATE", "G1"),
        "R4": ("GATE", "G2"),
        "R5": ("GATE", "PULL"),
        "R8": ("VSRC", "FAST_B"),
        "R9": ("FAST_B", "FAST_E"),
        "R25": ("GATE", "RESET_B"),
        "R26": ("VSRC", "RESET_C"),
        "C1": ("MILLER", "VBUS"),
        "C7": ("VSRC", "GATE"),
        "D1": ("VSRC", "GATE"),
        "D2": ("GATE", "FAST_E"),
        "D3": ("PULL", "FAST_B"),
        "D8": ("GATE", "MILLER"),
        "Q4": ("VSRC", "FAST_B", "FAST_E"),
        "Q5": ("RESET_C", "RESET_B", "MILLER"),
        "Q1": ("G1", "VBUS", "VSRC"),
        "Q2": ("G2", "VBUS", "VSRC"),
    }
    actual = {pin: name for name, pins in power.NETS.items() for pin in pins}
    for ref, nets in expected.items():
        assert tuple(actual[(ref, str(i + 1))] for i in range(len(nets))) == nets, ref
    assert not any(p.refdes == "R24" for p in power.PARTS)
    specs = {p.refdes: p.partNumber for p in power.PARTS}
    # The silicon model above stands for both, since the BAT46 they were went
    # out of production in DO-35 and both became 1N4148 on 2026-10-01.
    assert all("1N4148" in specs[r] for r in ("D2", "D8"))


def measure(settings, legacy=False):
    bulk = settings.get("bulk", power.BUS_CAPACITANCE)
    options = {k: v for k, v in settings.items() if k != "bulk"}
    deck = fixture(new=not legacy, **options).replace("1540u", str(bulk))
    a = run(deck)
    assert all(np.isfinite(v).all() for v in a.values())
    t, v, i = a["time"], a["v(d)"], a["i(vsense)"]
    off = 0.4
    gap = settings.get("gap", 0.001)
    load = settings.get("rload", 1000)
    bus = settings.get("bus", 25.2)
    assert v[np.where(t < off)[0][-1]] > 0.97 * bus, "Did not finish initial start"
    assert v[-1] > 0.97 * bus, "Did not finish restart"
    assert max(a["v(s)"] - a["v(g)"]) < power.MOSFET_VGS_MAX
    cap = i - v / load
    cold = float(cap[(t > 1e-5) & (t < off)].max())
    restart = float(cap[t > off + gap].max())
    ix = np.where((t > off) & (t < off + gap) & (i < 0.01))[0]
    off_ms = (t[ix[0]] - off) * 1000 if len(ix) else None
    if gap >= 0.01:
        assert off_ms is not None and off_ms < 10, (settings, off_ms)
    return cold, restart, off_ms


def main():
    check_connections()
    old = measure(dict(rload=1), legacy=True)
    assert old[0] > 2, "Must reproduce the previous cold-start failure"
    print(f"Legacy cold-start capacitor peak: {old[0]:.2f} A", flush=True)
    worst = 0
    count = 0
    for bus in (18, 25.2, 30):
        for gap in (0.0001, 0.0005, 0.001, 0.002, 0.003, 0.005, 0.01, 0.1):
            settings = dict(
                bus=bus,
                beta=50,
                cscale=1.2,
                gscale=0.8,
                threshold=1.5,
                gap=gap,
                rload=1,
                bulk=2200e-6,
            )
            cold, restart, _ = measure(settings)
            assert max(cold, restart) < 2, (settings, cold, restart)
            worst = max(worst, cold, restart)
            count += 1
        print(f"{bus:g} V adverse reset corner PASS", flush=True)
    for settings in (
        dict(gap=0.1),
        dict(bus=30, beta=50, cscale=0.8, gscale=1.2, threshold=1.5, gap=0.1, rload=1),
    ):
        cold, restart, off_ms = measure(settings)
        assert max(cold, restart) < 2, (settings, cold, restart)
        worst = max(worst, cold, restart)
        count += 1
        print(
            f"Additional corner: capacitor peak {max(cold, restart):.3f} A; OFF {off_ms:.3f} ms",
            flush=True,
        )
    print(f"{count} reset cases PASS; maximum capacitor peak {worst:.3f} A")
    print("Simplified-model evidence only; loaded MOSFET SOA remains unverified.")


if __name__ == "__main__":
    main()
