#!/bin/bash
# Start diagd.py on the Pi, detached, so that it outlives the SSH session that
# started it. Installed as a command, so that from the Pi or the PC it is
#
#     start_diagd                          UART4 at 1.5 Mbaud; clients on 127.0.0.1:7700
#     start_diagd --sim                    a simulated controller, for trying it out
#     ssh admin@bpi-m4zero start_diagd     the same, from the PC
#
# and stop_diagd stops it. Anything after the command goes to diagd.py as it
# stands (see its --help). It writes to diagd.log beside diagd.py, says whether
# it came up, and does nothing if one is already running. It holds UART4 until
# it is stopped, so stop it before flash_mcu.py or wheel_check.py.
#
# Installing it, once, with the files beside it in the admin account's home:
#
#     chmod +x start_diagd.sh stop_diagd.sh
#     sudo ln -sf ~/start_diagd.sh /usr/local/bin/start_diagd
#     sudo ln -sf ~/stop_diagd.sh /usr/local/bin/stop_diagd
#
# /usr/local/bin because it is on the PATH that SSH gives a command, where
# ~/bin is not. No sudo to run it: admin is in dialout, which is all UART4 needs.
set -euo pipefail
# Through the link in /usr/local/bin to where this file and diagd.py are.
here=$(dirname "$(readlink -f "$0")")
log="$here/diagd.log"

if pid=$(pgrep -f 'python3 .*diagd\.py'); then
    echo "diagd is already running (pid $pid); its log is $log"
    exit 0
fi

echo "--- started $(date '+%Y-%m-%d %H:%M:%S')" >> "$log"
# Only what this start writes, after the line above: an earlier run's lines
# say nothing about this one.
from=$(($(wc -l < "$log") + 1))
cd "$here"
setsid nohup python3 -u "$here/diagd.py" "$@" >> "$log" 2>&1 < /dev/null &
pid=$!

# It says where clients connect once it is serving, or dies saying why.
for _ in $(seq 30); do
    sleep 0.1
    if ! kill -0 "$pid" 2> /dev/null; then
        echo "diagd did not start:"
        tail -n "+$from" "$log" | tail -n 5
        exit 1
    fi
    if tail -n "+$from" "$log" | grep -q "clients on"; then
        echo "diagd is running (pid $pid); its log is $log"
        tail -n "+$from" "$log" | grep -E "diagd:|link:|controller:" || true
        exit 0
    fi
done
echo "diagd is running (pid $pid) but has not said it is serving; see $log"
