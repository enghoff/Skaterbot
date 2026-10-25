#!/bin/bash
# Install the late power-cut hook. Run on the Pi with flash_mcu.py and
# robot_poweroff.py beside this script. Does not shut down or change pins.
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
sudo install -d -m 755 /usr/local/lib/bipedal /usr/lib/systemd/system-shutdown
sudo install -m 644 "$here/flash_mcu.py" /usr/local/lib/bipedal/flash_mcu.py
sudo install -m 755 "$here/robot_poweroff.py" /usr/lib/systemd/system-shutdown/robot-poweroff
sudo /usr/lib/systemd/system-shutdown/robot-poweroff --check
echo 'Power-off hook installed. No shutdown requested.'
