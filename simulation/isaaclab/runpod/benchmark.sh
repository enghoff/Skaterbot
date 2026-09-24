#!/usr/bin/env bash
# How many robots should this GPU simulate at once? Measure it.
#
#     bash benchmark.sh                                  # the flat task
#     TASK=Biped-Wheeled-Rough-v0 bash benchmark.sh      # the rough one
#     SIZES="4096 8192" ITERATIONS=40 bash benchmark.sh
#
# Runs a short training at each robot count and reports simulation throughput,
# how busy the GPU was and how much of its memory was used. Throughput rises
# with the robot count until the GPU is busy or its memory is full, and the
# right count is the knee of that curve. Run it on every new kind of GPU:
# a card with more memory or more cores moves the knee, and a pod with slower
# CPU cores moves it too, because at small counts the simulation is limited by
# the one CPU thread that launches the GPU's work, not by the GPU.
#
# It refuses a result with any PhysX error in its log, and prints the fall
# rate, because an overflowed contact buffer makes the simulation faster and
# wrong at once. Compare the falls across sizes: they should not grow.
#
# Results are printed and appended to /workspace/runs/benchmarks.tsv, so the
# numbers for every card this project has run on stay together.
#
# BENCHMARK A TRAINED POLICY. From scratch, robots fall within half a second
# and are reset constantly, and resets are the slow part of a step: the rough
# task measured 21 000 steps/s at 4 096 robots and 14 700 at 8 192 that way,
# against 43 000 once the same run had learned to stay up. So point RESUME at
# a checkpoint of the task being measured, and it measures the steady state
# training actually spends its time in:
#
#     RESUME=/workspace/runs/logs/rsl_rl/wheeled_biped_rough/<run>/model_2999.pt

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK=${TASK:-Biped-Wheeled-Balance-v0}
SIZES=${SIZES:-"2048 4096 8192 16384"}
ITERATIONS=${ITERATIONS:-30}
SCRATCH=/tmp/isaac-bench
TSV=/workspace/runs/benchmarks.tsv
mkdir -p "$SCRATCH"

# Isaac Lab resumes from <cwd>/logs/rsl_rl/<experiment>/<run>/<checkpoint>, so
# the checkpoint's run is linked into the scratch directory under its own name.
resume_args=()
if [ -n "${RESUME:-}" ]; then
    run_dir=$(dirname "$RESUME")
    experiment=$(basename "$(dirname "$run_dir")")
    mkdir -p "$SCRATCH/logs/rsl_rl/$experiment"
    ln -sfn "$run_dir" "$SCRATCH/logs/rsl_rl/$experiment/resumed"
    resume_args=(--resume --load_run resumed --checkpoint "$(basename "$RESUME")")
    echo "from $RESUME"
fi

gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
cpu=$(grep -m1 "model name" /proc/cpuinfo | cut -d: -f2 | sed 's/^ *//')
echo "$gpu, $cpu, task $TASK, $ITERATIONS iterations each"
[ -f "$TSV" ] || printf "date\tgpu\ttask\tnum_envs\tsteps_per_s\tgpu_util_pct\tgpu_mem_gib\titer_s\n" > "$TSV"
printf "\n  %8s %12s %10s %10s %9s %12s\n" robots steps/s "gpu busy" "gpu mem" "s/iter" "falls/reset"

for n in $SIZES; do
    log="$SCRATCH/bench_$n.log"
    smi="$SCRATCH/smi_$n.csv"
    nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits -l 1 > "$smi" &
    smi_pid=$!
    RUNS_DIR="$SCRATCH" TASK="$TASK" timeout 1800 bash "$HERE/train.sh" \
        --num_envs "$n" --max_iterations "$ITERATIONS" "${resume_args[@]}" > "$log" 2>&1
    status=$?
    kill "$smi_pid" 2>/dev/null
    if [ $status -ne 0 ] || ! grep -q "Training time" "$log"; then
        printf "  %8s   failed -- see %s\n" "$n" "$log"
        continue
    fi
    # A fast simulation that has stopped simulating is not a result. PhysX
    # reports an overflowed buffer once, as an error, and then carries on
    # missing contacts -- which at 16 384 robots looked like 72 000 steps/s and
    # robots falling over at a hundred times the rate of 8 192.
    errors=$(grep -ac "PhysX error" "$log")
    if [ "$errors" -gt 0 ]; then
        printf "  %8s   INVALID -- %s PhysX errors, first: %s\n" "$n" "$errors" \
            "$(grep -a -m1 "PhysX error" "$log" | sed 's/.*PhysX error: //' | cut -c1-90)"
        continue
    fi
    fell=$(grep -a "Termination/fell" "$log" | tail -5 | awk '{s += $NF} END {printf "%.2f", s / NR}')
    # The second half of the iterations, past start-up and the first resets.
    read -r sps iter < <(grep -a "Steps per second\|Iteration time" "$log" |
        awk -v half=$((ITERATIONS / 2)) '
            /Steps per second/ { s[++i] = $NF }
            /Iteration time/   { t[++j] = $(NF) + 0 }
            END { for (k = half; k <= i; k++) { ss += s[k]; tt += t[k]; c++ }
                  printf "%d %.2f\n", ss / c, tt / c }')
    # GPU load over the same stretch: the busy samples' second half.
    read -r util mem < <(awk -F', ' '$2 > 500 { u[++n] = $1; m[n] = $2 }
        END { h = int(n / 2) + 1; for (k = h; k <= n; k++) { uu += u[k]; if (m[k] > mm) mm = m[k] }
              printf "%d %.1f\n", uu / (n - h + 1), mm / 1024 }' "$smi")
    printf "  %8s %12s %9s%% %7s GiB %9s %12s\n" "$n" "$sps" "$util" "$mem" "$iter" "$fell"
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$(date -u +%F)" "$gpu" "$TASK" "$n" \
        "$sps" "$util" "$mem" "$iter" >> "$TSV"
done
echo
echo "appended to $TSV"
