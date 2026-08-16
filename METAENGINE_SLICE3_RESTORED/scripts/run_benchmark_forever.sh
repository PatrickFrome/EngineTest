#!/bin/bash
# run_benchmark_forever.sh — wrapper that restarts the benchmark runner on exit.
#
# This wrapper survives parent shell exit by using setsid. If the Python
# benchmark runner crashes or finishes a round, the wrapper sleeps briefly
# then restarts it — so testing NEVER stops until the user manually kills
# this wrapper (or its child python process).
#
# Logs are appended (not truncated) on each restart so progress is preserved.
#
# Usage:
#   setsid bash scripts/run_benchmark_forever.sh &
#   disown
#
# To stop:
#   pkill -f run_massive_benchmark
#   pkill -f run_benchmark_forever

set -u

cd /home/z/my-project/METAENGINE_SLICE3_RESTORED

LOG_FILE=storage/massive_benchmark.nohup.out
PID_FILE=storage/massive_benchmark.pid
WRAPPER_PID_FILE=storage/massive_benchmark_wrapper.pid

echo $$ > "$WRAPPER_PID_FILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] === BENCHMARK WRAPPER STARTED (PID $$) ===" >> "$LOG_FILE"

# Infinite restart loop
while true; do
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] --- starting python benchmark runner ---" >> "$LOG_FILE"
    # --rounds 0 means INFINITE inside the python script, but if the python
    # process dies anyway, we restart it.
    python3 scripts/run_massive_benchmark.py \
        --rounds 0 \
        --tasks-per-round 0 \
        --max-workers 4 \
        --sleep-between-rounds 5 \
        >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] --- python runner exited with code $EXIT_CODE — restarting in 10s ---" >> "$LOG_FILE"
    # Save current python PID placeholder (none, between restarts)
    echo "" > "$PID_FILE"
    sleep 10
done
