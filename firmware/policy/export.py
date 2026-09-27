# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "onnx>=1.16", "onnxruntime>=1.18"]
# ///
"""Write a trained policy's network into the policy firmware.

    uv run firmware/policy/export.py exports/rl/<run>

Reads the run's exported/policy.onnx -- the observation normaliser and the
network rsl_rl exported -- and writes firmware/policy/net/: net.bin, every
parameter as a little-endian 32-bit float, and net.rs, the shapes the firmware
reads them with. Nothing else about the policy is the firmware's business: the
observation is built and the actions used on the far side of the link, as
docs/POLICY_INTERFACE.md sets out.

Before it writes anything it runs the network as it has read it against
onnxruntime, so a graph misread fails here rather than on the board. The
default policy is simulation/mujoco/drive.py's, which is what hil.py drives:

    uv run firmware/policy/export.py exports/rl/jump-2026-09-26_08-23-24_comjump
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import numpy_helper

HERE = Path(__file__).resolve().parent
NET = HERE / "net"


@dataclass
class Net:
    """The policy as the firmware runs it: (obs - offset) / divisor, then
    fully connected layers with an ELU after every one but the last."""

    offset: np.ndarray  # (n_obs,)
    divisor: np.ndarray  # (n_obs,)
    layers: list[tuple[np.ndarray, np.ndarray]]  # (weight [out, in], bias [out])
    elu_alpha: float

    @property
    def n_obs(self) -> int:
        return self.offset.size

    @property
    def n_act(self) -> int:
        return self.layers[-1][1].size

    def forward(self, obs: np.ndarray, dtype=np.float32) -> np.ndarray:
        """The network on a batch of observations, in `dtype` throughout."""
        x = (obs.astype(dtype) - self.offset.astype(dtype)) / self.divisor.astype(dtype)
        for k, (w, b) in enumerate(self.layers):
            x = x @ w.T.astype(dtype) + b.astype(dtype)
            if k + 1 < len(self.layers):
                x = np.where(
                    x > 0, x, dtype(self.elu_alpha) * np.expm1(np.minimum(x, 0))
                )
        return x


def digest(policy: Path) -> str:
    """What the firmware and the host compare to know they hold one policy."""
    return hashlib.sha256(policy.read_bytes()).hexdigest()[:16]


def load(policy: Path) -> Net:
    """The normaliser and the layers, out of the graph rsl_rl exports:
    Sub, Div, then Gemm and Elu in turn, ending on a Gemm."""
    graph = onnx.load(str(policy)).graph
    consts = {t.name: numpy_helper.to_array(t) for t in graph.initializer}
    nodes = []
    for node in graph.node:
        if node.op_type == "Constant":
            consts[node.output[0]] = numpy_helper.to_array(node.attribute[0].t)
        else:
            nodes.append(node)
    (source,) = graph.input
    ops = [n.op_type for n in nodes]
    body = ops[2:]
    expected = ["Gemm", "Elu"] * (len(body) // 2) + ["Gemm"]
    if ops[:2] != ["Sub", "Div"] or body != expected:
        sys.exit(f"{policy}: not the graph this reads, {' '.join(ops)}")

    def const(node, i):
        return consts[node.input[i]].astype(np.float64).ravel()

    sub, div = nodes[0], nodes[1]
    if sub.input[0] != source.name or div.input[0] != sub.output[0]:
        sys.exit(f"{policy}: the normaliser is not applied to {source.name}")
    offset, divisor = const(sub, 1), const(div, 1)

    layers, alphas, previous = [], set(), div.output[0]
    for node in nodes[2:]:
        attrs = {a.name: onnx.helper.get_attribute_value(a) for a in node.attribute}
        if node.input[0] != previous:
            sys.exit(f"{policy}: {node.name} does not follow the node before it")
        previous = node.output[0]
        if node.op_type == "Elu":
            alphas.add(float(attrs.get("alpha", 1.0)))
            continue
        if attrs.get("transA", 0) or attrs.get("alpha", 1.0) != 1.0:
            sys.exit(f"{policy}: {node.name} is not a plain x W^T + b")
        if attrs.get("beta", 1.0) != 1.0:
            sys.exit(f"{policy}: {node.name} scales its bias")
        w = consts[node.input[1]].astype(np.float64)
        if not attrs.get("transB", 0):
            w = w.T
        layers.append((w, consts[node.input[2]].astype(np.float64)))
    if len(alphas) != 1:
        sys.exit(f"{policy}: the ELUs do not share one alpha, {alphas}")
    for (w, b), (w_next, _) in zip(layers, layers[1:]):
        assert w.shape[0] == b.size == w_next.shape[1], "layer widths do not chain"
    assert layers[0][0].shape[1] == offset.size == divisor.size
    return Net(offset, divisor, layers, alphas.pop())


def check(net: Net, policy: Path, n: int = 4096, seed: int = 0) -> tuple[float, float]:
    """How far this reading of the network and onnxruntime each are from the
    exact answer, worked in 64 bits, over observations spread as the
    normaliser says the policy's were and some far outside that.

    Neither is exact: the raw outputs run to the hundreds before they are
    clipped to +/-1, and 32-bit rounding of numbers that size is 1e-4 on its
    own. A graph misread is off by whole units, so the test is that this is
    about as close as onnxruntime is.
    """
    rng = np.random.default_rng(seed)
    spread = rng.normal(size=(n, net.n_obs)) * rng.choice([0.5, 1, 3], (n, 1))
    obs = (net.offset + spread * net.divisor).astype(np.float32)
    session = ort.InferenceSession(str(policy))
    theirs = np.concatenate([session.run(None, {"obs": o[None]})[0] for o in obs])
    exact = net.forward(obs.astype(np.float64), np.float64)
    ours = net.forward(obs)
    return float(np.abs(ours - exact).max()), float(np.abs(theirs - exact).max())


def write(net: Net, policy: Path, run: Path) -> Path:
    NET.mkdir(exist_ok=True)
    params = [net.offset, net.divisor]
    for w, b in net.layers:
        params += [w.ravel(), b]
    blob = np.concatenate(params).astype("<f4")
    (NET / "net.bin").write_bytes(blob.tobytes())
    shapes = ", ".join(f"({w.shape[1]}, {w.shape[0]})" for w, _ in net.layers)
    widest = max(max(w.shape) for w, _ in net.layers)
    alpha = np.float32(net.elu_alpha).view(np.uint32)
    (NET / "net.rs").write_text(
        f"""// Written by firmware/policy/export.py from {run.name}. Do not edit: run
// the export again.

/// The run the network came from, and the first 16 hex digits of its
/// policy.onnx's SHA-256, which the host checks against its own copy.
pub const RUN: &str = "{run.name}";
pub const DIGEST: &str = "{digest(policy)}";

pub const N_OBS: usize = {net.n_obs};
pub const N_ACT: usize = {net.n_act};
/// Each fully connected layer's (inputs, outputs), in order. An ELU follows
/// every one but the last.
pub const LAYERS: [(usize, usize); {len(net.layers)}] = [{shapes}];
pub const WIDEST: usize = {widest};
pub const ELU_ALPHA: f32 = f32::from_bits({alpha:#010x});

/// Every parameter as a 32-bit float: the normaliser's offset and divisor,
/// then each layer's weights, one output's row at a time, and its biases.
pub const PARAM_COUNT: usize = {blob.size};
pub static PARAMS: Params = Params(*include_bytes!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/net/net.bin"
)));

#[repr(C, align(4))]
pub struct Params(pub [u8; {blob.nbytes}]);
""",
        newline="\n",
    )
    return NET


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run", type=Path, help="a run directory under exports/rl/")
    args = parser.parse_args()
    policy = args.run / "exported" / "policy.onnx"
    if not policy.exists():
        sys.exit(f"{policy} does not exist")
    net = load(policy)
    ours, theirs = check(net, policy)
    widths = " -> ".join([str(net.n_obs)] + [str(b.size) for _, b in net.layers])
    count = 2 * net.n_obs + sum(w.size + b.size for w, b in net.layers)
    print(
        f"{args.run.name}: {widths}, ELU alpha {net.elu_alpha:g},"
        f" {count} parameters ({count * 4 / 1024:.0f} KB)"
    )
    print(
        f"largest difference from the exact answer: {ours:.1e} as read here,"
        f" {theirs:.1e} from onnxruntime"
    )
    if ours > 4 * theirs:
        sys.exit("that is not a network read correctly; nothing written")
    out = write(net, policy, args.run)
    print(f"wrote {out.relative_to(HERE.parents[1])}, digest {digest(policy)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
