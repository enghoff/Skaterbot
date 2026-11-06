#!/bin/bash
# Bluetooth, and the game controller it brings, for the console. Run once from a
# checkout on the BPI: sudo bash sbc/install_console_bluetooth.sh
# Then restart the console, which picks up the two new groups only on starting:
# sudo systemctl restart motor-console
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
owner=${SUDO_USER:-admin}
id "$owner" >/dev/null
conf=/etc/bluetooth/main.conf

apt-get install -y bluez
# BlueZ lets its group pair and forget, and input lets the console read a
# controller, so this needs no root helper as Wi-Fi does.
usermod -aG bluetooth,input "$owner"

# Bluetooth's low-energy controllers reach Linux through uhid, and some kernels
# do not load it by themselves.
modprobe uhid || echo "no uhid module: a low-energy controller may not appear"
echo uhid > /etc/modules-load.d/bipedal-controller.conf

# Sets one key in one section of main.conf, leaving the rest as it was found.
option() {
    local section=$1 key=$2 value=$3
    grep -q "^\[$section\]" "$conf" || printf '\n[%s]\n' "$section" >> "$conf"
    sed -i "/^$key *=/d" "$conf"
    sed -i "0,/^\[$section\]/s//[$section]\n$key = $value/" "$conf"
}
[ -f "$conf" ] && [ ! -f "$conf.console-backup" ] && cp "$conf" "$conf.console-backup"
# On at every boot, for a controller to reconnect to with no page open.
option Policy AutoEnable true
# A controller gone out of range is otherwise reported for 20 s as still holding
# whatever it last held. 3200 slots of 0.625 ms is 2 s. Whether it takes effect
# depends on the kernel and on which end of the link is its master: gamepad.py's
# own watch on silence does not rely on it. This is classic Bluetooth's setting and
# does nothing for a low-energy controller: the Xbox ones are, and start at 420 ms
# and go to the 3 s they ask for.
option BR LinkSupervisionTimeout 3200

rfkill unblock bluetooth 2>/dev/null || true
systemctl enable bluetooth
systemctl restart bluetooth
if bluetoothctl --timeout 3 show 2>/dev/null | grep -q "Powered:"; then
    echo "Bluetooth adapter found."
else
    # The M4 Zero's radio hangs off a serial port, which an image may not bring up.
    echo "BlueZ is installed but sees no adapter: see 'journalctl -u bluetooth'."
fi
