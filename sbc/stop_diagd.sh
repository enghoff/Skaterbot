#!/bin/bash
# Stop diagd.py, which start_diagd started. On its way out it tells the
# controller to stop every motor, as Ctrl-C would have.
#
#     stop_diagd
#     ssh admin@bpi-m4zero stop_diagd      the same, from the PC
#
# start_diagd.sh says how both are installed as commands.
#
# The pattern names python3 so that, sent through ssh, it does not match the
# shell running it.
pattern='python3 .*diagd\.py'
if ! pkill -f "$pattern"; then
    echo "diagd was not running"
    exit 0
fi
for _ in $(seq 30); do
    sleep 0.1
    if ! pgrep -f "$pattern" > /dev/null; then
        echo "diagd stopped, and every motor with it"
        exit 0
    fi
done
echo "diagd has not stopped after 3 s; pkill -9 -f '$pattern' will"
exit 1
