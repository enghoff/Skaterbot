#!/bin/bash
# Runs sbc/launcher.py from boot, so the robot can be started with no computer: a tap of
# its power button. Run from a full checkout on the BPI, once
# `balance.py lower` has written launch.json: sudo bash sbc/install_launcher.sh
# To take it off again: sudo systemctl disable --now robot-launcher
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
here=$(dirname "$(readlink -f "$0")")
owner=${SUDO_USER:-admin}
id "$owner" >/dev/null
test -f "$here/policy.npz" || { echo "no $here/policy.npz: run sbc/pack_policy.py"; exit 1; }
test -f "$here/launch.json" || { echo "no $here/launch.json: run balance.py lower"; exit 1; }
cat > /etc/systemd/system/robot-launcher.service <<EOF
[Unit]
Description=Bipedal launcher: starts the policy when somebody asks
After=diagd.service

[Service]
Type=simple
User=$owner
SupplementaryGroups=dialout
WorkingDirectory=$here
ExecStart=/usr/bin/python3 "$here/launcher.py" --rt $*
Restart=on-failure
RestartSec=2
TimeoutStopSec=15
KillMode=mixed

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
# One started by hand would answer every press as well, and undo what this one did.
pkill -f '^python3 l[a]uncher' || true
systemctl enable --now robot-launcher.service
systemctl --no-pager status robot-launcher.service | head -5
