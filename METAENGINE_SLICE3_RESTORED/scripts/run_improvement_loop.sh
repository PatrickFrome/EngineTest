#!/bin/bash
# run_improvement_loop.sh — Infinite autonomous MetaEngine improvement loop.
#
# Runs metaengine/improvement_loop.py --forever in a fully detached process
# (setsid -f). The loop:
#   1. Runs a small benchmark batch (6 tasks, ~5 minutes)
#   2. Analyzes results and generates improvement patches
#   3. Applies patches to metaengine/adaptation_patches/
#   4. Runs the test suite to verify nothing broke
#   5. Measures post-improvement fitness
#   6. If fitness regressed >5%, rolls back the patches
#   7. Publishes cycle result to Turso cloud DB
#   8. Sleeps 5 minutes, then repeats
#
# Logs:
#   storage/improvement_loop.log         — human-readable progress
#   storage/improvement_loop_state.json  — cycle history + best fitness
#   storage/improvement_loop.nohup.out   — stderr/stdout capture
#
# To stop:
#   pkill -f "improvement_loop"
#
# To monitor:
#   tail -f storage/improvement_loop.log
#   cat storage/improvement_loop_state.json | python3 -m json.tool

set -u
cd /home/z/my-project/METAENGINE_SLICE3_RESTORED

# Clean up any stale state if requested
if [ "${1:-}" = "--restart" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] clearing improvement_loop state" >> storage/improvement_loop.nohup.out
    rm -f storage/improvement_loop_state.json
fi

mkdir -p storage

# Launch the improvement loop in the background, fully detached
setsid -f python3 -m metaengine.improvement_loop --forever --interval 300 \
    > storage/improvement_loop.nohup.out 2>&1 < /dev/null

LOOP_PID=$(pgrep -f "metaengine.improvement_loop" | head -1)
echo "Improvement loop started (PID: $LOOP_PID)"
echo "  Logs: storage/improvement_loop.log"
echo "  State: storage/improvement_loop_state.json"
echo "  Stop:  pkill -f improvement_loop"
echo ""
sleep 5
if kill -0 $LOOP_PID 2>/dev/null; then
    echo "✓ Process alive"
else
    echo "✗ Process died — check storage/improvement_loop.nohup.out"
fi
echo ""
echo "=== Last 10 log lines ==="
tail -10 storage/improvement_loop.log 2>/dev/null
