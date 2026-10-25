#!/bin/bash
# Run from a full checkout on the BPI: sudo bash sbc/install_motor_console.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
here=$(dirname "$(readlink -f "$0")")
owner=${SUDO_USER:-admin}
id "$owner" >/dev/null
test -f "$here/../bench/damiao.py"
apt-get update
apt-get install -y python3-aiohttp python3-serial avahi-daemon
systemctl enable --now avahi-daemon
usermod -aG dialout "$owner"
# The physical power button needs diagd even before a browser has connected.
cat > /etc/systemd/system/diagd.service <<EOF
[Unit]
Description=Bipedal controller diagnostics and power-button shutdown

[Service]
Type=simple
User=$owner
SupplementaryGroups=dialout
WorkingDirectory=$here
ExecStartPre=-+/usr/lib/systemd/system-shutdown/robot-poweroff --start-heartbeat
ExecStart=/usr/bin/python3 "$here/diagd.py"
StandardOutput=append:$here/diagd.log
StandardError=append:$here/diagd.log
Restart=no
TimeoutStopSec=5

[Install]
WantedBy=multi-user.target
EOF
cat > /etc/systemd/system/motor-console.service <<EOF
[Unit]
Description=Bipedal motor diagnostics web console
After=network.target diagd.service

[Service]
Type=simple
User=$owner
SupplementaryGroups=dialout
WorkingDirectory=$here
ExecStart=/usr/bin/python3 "$here/motor_console.py"
Restart=on-failure
RestartSec=2
TimeoutStopSec=8
KillMode=process

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable diagd.service
# Keep an existing detached daemon; the enabled unit takes over on the next boot.
if ! pgrep -f 'python3 .*diagd\.py' >/dev/null; then
    systemctl start diagd.service
fi
systemctl enable --now motor-console.service
systemctl restart motor-console.service
echo "Console: http://$(hostname -s):8080/"
