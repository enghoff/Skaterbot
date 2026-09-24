#!/usr/bin/env bash
# Bring a RunPod GPU pod up to Isaac Sim 6.0.1 + Isaac Lab 3.0.
#
#     bash /workspace/biped/simulation/isaaclab/runpod/setup_pod.sh
#
# WHERE THINGS LIVE, AND WHY. The network volume at /workspace survives the pod;
# the container disk does not. But the volume is a network filesystem that
# writes a large file at 500 MB/s and creates small files at about forty a
# second, and Isaac Sim is well over a hundred thousand small files. Installed
# onto the volume it takes hours, and Kit then starts slowly every time from it.
#
# So the Python environment is built on the container disk at /opt/isaac-venv,
# and a single compressed snapshot of it is kept on the volume. A new pod over
# the same volume unpacks the snapshot -- a couple of minutes -- instead of
# reinstalling. Isaac Lab's source, the project, and every training run stay on
# the volume, because those are few files and are what must not be lost.
#
# Idempotent: run it on every new pod. --resnapshot rebuilds the snapshot after
# a change to the environment.
#
# The pod needs NVIDIA_DRIVER_CAPABILITIES=all in its environment, or the
# container gets no Vulkan driver and Kit cannot start even headless. The image
# this was written against is runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404:
# Ubuntu 24.04 and Python 3.12, which Isaac Sim 6.0 requires.

set -euo pipefail

ISAACSIM_VERSION="6.0.1.0"
ISAACLAB_TAG="v3.0.0-beta2.patch1"   # the Isaac Lab release built for Isaac Sim 6.0
TORCH_INDEX="https://download.pytorch.org/whl/cu128"

WS=/workspace
VENV=/opt/isaac-venv
SNAPSHOT=$WS/snapshots/isaac-venv.tar.zst
ISAACLAB=$WS/IsaacLab

export UV_CACHE_DIR=/root/.cache/uv
export UV_HTTP_TIMEOUT=300
# Importing isaacsim asks to accept NVIDIA's Omniverse licence, and with no
# terminal to answer it the import fails.
export OMNI_KIT_ACCEPT_EULA=YES

echo "== container packages"
# Kit's runtime libraries that the slim image leaves out. Lost with the pod,
# so this runs every time.
if ! dpkg -s libglu1-mesa libvulkan1 zstd >/dev/null 2>&1; then
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        libglu1-mesa libvulkan1 libxt6 libxrandr2 libxi6 libxkbcommon0 \
        libsm6 libice6 libegl1 zstd >/dev/null
fi

if [ ! -x "$VENV/bin/python" ] && [ -f "$SNAPSHOT" ] && [ "${1:-}" != "--resnapshot" ]; then
    echo "== unpacking the environment from $SNAPSHOT"
    mkdir -p "$VENV"
    zstd -d -T0 -c "$SNAPSHOT" | tar -xf - -C /opt
fi

echo "== python environment"
if [ ! -x "$VENV/bin/python" ]; then
    uv venv --seed --python /usr/bin/python3.12 "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
changed=0

echo "== torch"
if ! python -c "import torch" 2>/dev/null; then
    uv pip install "torch==2.10.*" torchvision --index-url "$TORCH_INDEX"
    changed=1
fi

echo "== isaac sim $ISAACSIM_VERSION"
if ! python -c "import isaacsim" 2>/dev/null; then
    uv pip install "isaacsim[all,extscache]==$ISAACSIM_VERSION" \
        --extra-index-url https://pypi.nvidia.com --index-strategy unsafe-best-match \
        --prerelease=allow
    changed=1
fi

echo "== isaac lab $ISAACLAB_TAG"
if [ ! -d "$ISAACLAB" ]; then
    git clone --depth 1 --branch "$ISAACLAB_TAG" https://github.com/isaac-sim/IsaacLab.git "$ISAACLAB"
fi
if ! python -c "import isaaclab_rl" 2>/dev/null; then
    (cd "$ISAACLAB" && OMNI_KIT_ACCEPT_EULA=YES ./isaaclab.sh --install)
    changed=1
fi
# 3.0's installer no longer takes a framework name, so rsl_rl -- the PPO
# implementation Isaac Lab's own locomotion agents use -- is added through
# isaaclab_rl's extra, which pins the version its train.py checks for.
if ! python -c "import rsl_rl" 2>/dev/null; then
    uv pip install -e "$ISAACLAB/source/isaaclab_rl[rsl_rl]"
    changed=1
fi

echo "== the CAD's own dependencies"
# simulation/plant.py reads its dimensions out of cad/, which imports
# build123d, so the project's numbers need it even inside Isaac's interpreter.
if ! python -c "import build123d, trimesh, scipy" 2>/dev/null; then
    uv pip install build123d trimesh scipy
    changed=1
fi

if [ "$changed" = 1 ] || [ ! -f "$SNAPSHOT" ] || [ "${1:-}" = "--resnapshot" ]; then
    echo "== snapshotting the environment to $SNAPSHOT"
    mkdir -p "$(dirname "$SNAPSHOT")"
    tar -cf - -C /opt isaac-venv | zstd -T0 -3 -q -o "$SNAPSHOT.partial" -f
    mv "$SNAPSHOT.partial" "$SNAPSHOT"
    ls -lh "$SNAPSHOT"
fi

echo "== done"
python -c "import isaacsim, torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
