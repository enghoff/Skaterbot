#!/usr/bin/env bash
# Train, replay or score the wheeled biped's balance policy on a RunPod pod.
#
#     bash train.sh [extra train.py arguments]         # train
#     bash train.sh --play [extra play.py arguments]   # replay the latest run,
#                                                       # export it, film it
#     bash train.sh --evaluate --policy <policy.pt>    # score an exported policy
#     bash train.sh --evaluate-jump --policy <policy.pt>   # score a jump policy
#
# Runs land in /workspace/runs/logs/rsl_rl/wheeled_biped_balance/<timestamp>/ on
# the network volume, so they outlive the pod. setup_pod.sh must have run first,
# and simulation/isaacsim/import_urdf.py must have built the robot's USD -- the
# task loads that file rather than converting the URDF a second time.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISAACLAB=/workspace/IsaacLab
# TASK=Biped-Wheeled-Rough-v0 in the environment picks the rough-ground task.
TASK=${TASK:-Biped-Wheeled-Balance-v0}

# shellcheck disable=SC1091
source /opt/isaac-venv/bin/activate
export OMNI_KIT_ACCEPT_EULA=YES
export PYTHONPATH="$HERE/..:${PYTHONPATH:-}"
# The task reads the robot's dimensions out of cad/, which imports build123d,
# which loads SciPy's OpenBLAS and starts its thread pool. Kit then forks while
# it starts, and OpenBLAS's fork handler crashes shutting that pool down --
# "free(): invalid pointer", or a segfault in blas_thread_shutdown_. One BLAS
# thread means there is no pool to shut down.
export OPENBLAS_NUM_THREADS=1

# Where runs are logged. benchmark.sh points this elsewhere, so its short runs
# never become the "latest run" that --play picks up.
RUNS_DIR=${RUNS_DIR:-/workspace/runs}
mkdir -p "$RUNS_DIR"
cd "$RUNS_DIR"

if [ "${1:-}" = "--evaluate-jump" ]; then
    shift
    exec python -u "$HERE/../evaluate_jump.py" --headless "$@"
fi

if [ "${1:-}" = "--evaluate-envelope" ]; then
    shift
    exec python -u "$HERE/../evaluate_envelope.py" --headless "$@"
fi

if [ "${1:-}" = "--evaluate" ]; then
    shift
    exec python -u "$HERE/../evaluate.py" --headless "$@"
fi

script=train.py
if [ "${1:-}" = "--play" ]; then
    script=play.py
    shift
fi

exec python -u "$ISAACLAB/scripts/reinforcement_learning/rsl_rl/$script" \
    --headless \
    --external_callback wheeled_biped_task.register \
    --task "$TASK" \
    "$@"
