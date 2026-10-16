#!/bin/bash
# Let flash_mcu.py reach the controller board, then reboot. Once, as root:
#
#     sudo bash setup_flash.sh
#
# Switches on UART4, on header pins 8 and 10, which is where the carrier's J5
# brings the MCU's USART1 -- Armbian's overlay for that, plus uart4-fix.dts
# beside this script, without which the port runs with no pins (see its
# comment); and gives the GPIO chips to a gpio group with the calling user in
# it, so BOOT0 and NRST can be driven without sudo. Safe to run again: it adds
# nothing that is already there.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run it with sudo"; exit 1; }

env=/boot/armbianEnv.txt
overlay=bananapi-m4-pi-13-14-uart4
cp -n "$env" "$env.bak-before-uart4"
if ! grep -q "^overlays=.*\b$overlay\b" "$env"; then
    if grep -q '^overlays=' "$env"; then
        sed -i "/^overlays=/ s/\$/ $overlay/" "$env"
    else
        echo "overlays=$overlay" >> "$env"
    fi
fi
fix=uart4-fix
mkdir -p /boot/overlay-user
dtc -@ -I dts -O dtb -o "/boot/overlay-user/$fix.dtbo" "$(dirname "$0")/$fix.dts"
if grep -q '^user_overlays=' "$env"; then
    sed -i "/^user_overlays=/{/\b$fix\b/!s/\$/ $fix/}" "$env"
else
    echo "user_overlays=$fix" >> "$env"
fi
grep -E '^(user_)?overlays=' "$env"

groupadd -f gpio
usermod -aG gpio "${SUDO_USER:-admin}"
echo 'SUBSYSTEM=="gpio", KERNEL=="gpiochip*", GROUP="gpio", MODE="0660"' \
    > /etc/udev/rules.d/60-gpiochip.rules

echo "rebooting"
systemctl reboot
