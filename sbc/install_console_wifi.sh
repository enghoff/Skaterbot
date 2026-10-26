#!/bin/bash
# Install the narrow, root-owned helper without restarting Wi-Fi.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
here=$(dirname "$(readlink -f "$0")")
owner=${SUDO_USER:-admin}
id "$owner" >/dev/null
apt-get install -y python3-yaml
install -d -m 755 /usr/lib/bipedal-console
install -o root -g root -m 755 "$here/console_wifi.py" /usr/lib/bipedal-console/wifi-helper
install -d -o root -g root -m 700 /var/lib/bipedal-console
rule=$(mktemp)
trap 'rm -f "$rule"' EXIT
printf '%s ALL=(root) NOPASSWD: /usr/lib/bipedal-console/wifi-helper ""\n' "$owner" > "$rule"
visudo -cf "$rule"
install -o root -g root -m 440 "$rule" /etc/sudoers.d/bipedal-console-wifi
install -d -m 755 /etc/systemd/system/netplan-wpa-wlan0.service.d
cat > /etc/systemd/system/netplan-wpa-wlan0.service.d/console-preference.conf <<'EOF'
[Service]
ExecStartPost=-/usr/lib/bipedal-console/wifi-helper --restore
EOF
systemctl daemon-reload
echo "Wi-Fi helper installed; existing Wi-Fi connection preserved."
