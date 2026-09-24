"""Give a trained policy more inputs and outputs without changing what it does.

    python simulation/isaaclab/widen_checkpoint.py SRC DST \\
        --actor-inputs 3 --critic-inputs 25:3,64:5 --outputs 2 \\
        --scale-outputs 0:0.6667,1:0.6667,2:0.6667,3:0.6667 \
        --set-std 0:0.3,1:0.3,2:0.3,3:0.3

A new task that extends an old one -- the jump task adds a trigger, a target
clearance and a timer to the balance task's inputs, and leg stiffness and
damping to its outputs -- should start from the old task's policy rather than
from nothing. But the networks are different shapes, so the checkpoint cannot
be loaded as it is. This widens it:

  * new INPUTS are appended at the end of the actor's and critic's
    observations, with zero weights into the first layer and a normaliser of
    mean 0 and variance 1. The widened network computes exactly what the old
    one did until training gives the new inputs some weight -- so the task
    must append its new observations after the old ones, in the same order.
  * new OUTPUTS are appended at the end of the actor's actions, with zero
    weights and zero bias, so each starts at the middle of its range, and a
    small exploration noise of its own.
  * EXISTING OUTPUTS can be rescaled (--scale-outputs), for a task that widens
    an action's range: the jump task moves the legs 1.5 times as far per unit
    of action, so the balance policy's leg outputs are multiplied by 2/3.
  * the optimiser's running moments are dropped, because their shapes no
    longer match; its settings are kept. Adam rebuilds them within a few
    iterations.

Torch only; it runs anywhere torch does. It checks the widened actor against
the original on random inputs before it writes anything.
"""

from __future__ import annotations

import argparse

import torch


def parse_inserts(spec: str, width: int) -> list[tuple[int, int]]:
    """'3' appends three inputs; '25:3,64:5' inserts three before old input 25
    and five before old input 64 (which, for 64 inputs, is the end)."""
    if not spec:
        return []
    inserts = []
    for item in spec.split(","):
        if ":" in item:
            at, count = item.split(":")
            inserts.append((int(at), int(count)))
        else:
            inserts.append((width, int(item)))
    return sorted(inserts)


def insert_columns(t: torch.Tensor, inserts: list[tuple[int, int]], fill: float):
    """Insert `count` columns of `fill` before each old column index `at`."""
    pieces, last = [], 0
    for at, count in inserts:
        pieces += [t[:, last:at], t.new_full((t.shape[0], count), fill)]
        last = at
    pieces.append(t[:, last:])
    return torch.cat(pieces, dim=1)


def widen_inputs(state: dict, inserts: list[tuple[int, int]]) -> None:
    state["mlp.0.weight"] = insert_columns(state["mlp.0.weight"], inserts, 0.0)
    for name, fill in (("_mean", 0.0), ("_var", 1.0), ("_std", 1.0)):
        key = "obs_normalizer." + name
        state[key] = insert_columns(state[key], inserts, fill)


def last_layer(state: dict) -> str:
    layers = sorted(
        {
            k.rsplit(".", 1)[0]
            for k in state
            if k.startswith("mlp.") and k.endswith("weight")
        },
        key=lambda name: int(name.split(".")[1]),
    )
    return layers[-1]


def actor_forward(state: dict, obs: torch.Tensor) -> torch.Tensor:
    """The deterministic actor, from its state dict: normalise, then the MLP."""
    x = (obs - state["obs_normalizer._mean"]) / (state["obs_normalizer._std"] + 1e-2)
    layers = sorted(
        {
            k.rsplit(".", 1)[0]
            for k in state
            if k.startswith("mlp.") and k.endswith("weight")
        },
        key=lambda name: int(name.split(".")[1]),
    )
    for i, name in enumerate(layers):
        x = x @ state[name + ".weight"].T + state[name + ".bias"]
        if i < len(layers) - 1:
            x = torch.nn.functional.elu(x)
    return x


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("src")
    parser.add_argument("dst")
    parser.add_argument(
        "--actor-inputs",
        default="",
        help="N to append N inputs, or at:N,... to insert N before old input at",
    )
    parser.add_argument(
        "--critic-inputs",
        default="",
        help="the same, for the critic -- whose inputs are the actor's followed by"
        " its own, so a new actor input lands in the middle of them",
    )
    parser.add_argument("--outputs", type=int, default=0)
    parser.add_argument("--output-std", type=float, default=0.3)
    parser.add_argument(
        "--scale-outputs",
        default="",
        help="index:factor,... -- multiply existing outputs, for a task whose"
        " action scale grew: an output that meant 0.8 rad at 1.0 means 1.2 rad in"
        " a task that scales it by 1.2, so it is multiplied by 0.8 / 1.2",
    )
    parser.add_argument(
        "--set-std",
        default="",
        help="index:std,... -- reset the exploration noise of existing outputs, for"
        " a task that has to explore where the old one had settled",
    )
    args = parser.parse_args()

    ckpt = torch.load(args.src, map_location="cpu", weights_only=False)
    actor = {k: v.clone() for k, v in ckpt["actor_state_dict"].items()}
    critic = {k: v.clone() for k, v in ckpt["critic_state_dict"].items()}
    original = {k: v.clone() for k, v in actor.items()}

    actor_inserts = parse_inserts(args.actor_inputs, actor["mlp.0.weight"].shape[1])
    critic_inserts = parse_inserts(args.critic_inputs, critic["mlp.0.weight"].shape[1])
    widen_inputs(actor, actor_inserts)
    widen_inputs(critic, critic_inserts)
    head = last_layer(actor)
    for item in filter(None, args.scale_outputs.split(",")):
        index, factor = item.split(":")
        index, factor = int(index), float(factor)
        actor[head + ".weight"][index] *= factor
        actor[head + ".bias"][index] *= factor
        actor["distribution.std_param"][index] *= factor
    for item in filter(None, args.set_std.split(",")):
        index, value = item.split(":")
        actor["distribution.std_param"][int(index)] = float(value)
    if args.outputs:
        w, b = actor[head + ".weight"], actor[head + ".bias"]
        actor[head + ".weight"] = torch.cat((w, w.new_zeros(args.outputs, w.shape[1])))
        actor[head + ".bias"] = torch.cat((b, b.new_zeros(args.outputs)))
        std = actor["distribution.std_param"]
        actor["distribution.std_param"] = torch.cat(
            (std, std.new_full((args.outputs,), args.output_std))
        )

    # The widened actor must do what the old one did on the old inputs,
    # whatever the new inputs are.
    n_old = original["obs_normalizer._mean"].shape[1]
    obs = torch.randn(64, n_old)
    before = actor_forward(original, obs)
    for item in filter(None, args.scale_outputs.split(",")):
        index, factor = item.split(":")
        before[:, int(index)] *= float(factor)
    widened = insert_columns(obs, actor_inserts, 0.0)
    added = widened.shape[1] - n_old
    # whatever the new inputs hold: fill them with noise
    mask = insert_columns(torch.zeros(1, n_old), actor_inserts, 1.0).bool()
    widened[:, mask[0]] = torch.randn(64, added)
    after = actor_forward(actor, widened)
    # Relative to the outputs' own size: float rounding alone is about 1e-6 of it.
    scale = before.abs().max().item() + 1.0
    drift = (after[:, : before.shape[1]] - before).abs().max().item() / scale
    if drift > 1e-5:
        raise SystemExit(f"widened actor differs from the original by {drift:.2e}")
    if args.outputs and after[:, before.shape[1] :].abs().max().item() > 1e-6:
        raise SystemExit("the new outputs do not start at zero")

    ckpt["actor_state_dict"] = actor
    ckpt["critic_state_dict"] = critic
    ckpt["optimizer_state_dict"]["state"] = {}
    ckpt["iter"] = 0
    torch.save(ckpt, args.dst)
    print(
        f"{args.src} -> {args.dst}: actor {n_old} -> {widened.shape[1]} inputs,"
        f" {before.shape[1]} -> {after.shape[1]} outputs; critic"
        f" {critic['mlp.0.weight'].shape[1]} inputs. Old behaviour reproduced to"
        f" {drift:.1e}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
