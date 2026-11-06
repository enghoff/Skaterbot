#!/bin/bash
# Flashes the controller, only with the robot disarmed. Taking diagd down for the flash stops
# every motor, and a robot standing on them falls.
#
#   bash sbc/flash_robot.sh <image.elf>     on the BPI: flash it, if the robot is disarmed
#   bash sbc/flash_robot.sh --check         say whether it is, and do nothing else
#
# Disarmed is nobody holding control, which a run does from its first moment until it ends,
# in the air, limp, or standing, and so does a motor console's tab with motors of its own.
# The launcher is frozen for the look, so that no press can arm it after it, and goes down
# only once the answer is that nothing is running, since taking it down ends any run.
set -u
image=${1:?usage: flash_robot.sh <image.elf> | --check}
here=$(dirname "$(readlink -f "$0")")
service=robot-launcher

holder() {
    (cd "$here" && python3 -c '
import diag_client
r = diag_client.Robot(name="flash_robot")
s = r.request("status")
r.close()
print((s.get("status", s).get("pi") or {}).get("control") or "")')
}

if [ "$image" = --check ]; then
    held=$(holder) || { echo "cannot tell: diagd did not answer"; exit 1; }
    if [ -n "$held" ]; then echo "ARMED: $held holds control"; exit 1; fi
    echo "disarmed"
    exit 0
fi
[ -f "$image" ] || { echo "REFUSED: no image $image"; exit 1; }

# Anchored, or it finds any shell whose command line mentions the launcher, this one's too.
frozen=$(pgrep -f '^(/usr/bin/)?python3 [^ ]*launcher\.py')
thaw() { [ -n "$frozen" ] && kill -CONT $frozen; }
trap thaw EXIT
[ -n "$frozen" ] && kill -STOP $frozen
# A press just before the freeze has taken control by now.
sleep 1
if systemctl is-active --quiet diagd; then
    held=$(holder) || { echo "REFUSED: diagd did not say who holds control"; exit 1; }
    if [ -n "$held" ]; then
        echo "REFUSED: it is armed, $held holds control. Disarm it first."
        exit 1
    fi
fi

# Nothing is running, so this ends only the spare it keeps loaded.
by_hand=""
if systemctl is-active --quiet $service; then
    sudo -n systemctl stop --no-block $service
else
    for pid in $frozen; do by_hand=$(tr '\0' ' ' < /proc/$pid/cmdline); done
    [ -n "$frozen" ] && kill -TERM $frozen
fi
thaw
trap - EXIT
sleep 2

sudo -n systemctl stop diagd
sleep 1
status=0
if python3 "$here/flash_mcu.py" "$image" --listen 0; then
    echo "FLASHED $(date +%T)"
    [ "$image" -ef "$HOME/diag.elf" ] || cp "$image" "$HOME/diag.elf"
else
    echo "FLASH FAILED"
    status=1
fi
sudo -n systemctl start diagd
sleep 3
sudo -n systemctl restart motor-console
if [ -n "$by_hand" ]; then
    (cd "$here" && setsid nohup $by_hand > "$HOME/launch_launcher.err" 2>&1 < /dev/null &)
elif systemctl is-enabled --quiet $service 2> /dev/null; then
    sudo -n systemctl start $service
fi
echo "diagd $(systemctl is-active diagd), motor console $(systemctl is-active motor-console)"
exit $status
