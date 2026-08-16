#!/bin/bash
# run_benchmark_cluster.sh — Launch N parallel infinite benchmark shards.
#
# Each shard runs as an independent detached process via setsid -f.
# All shards share the same codebase + Turso DB; each gets its own:
#   - log file         (storage/massive_benchmark_shardN.log)
#   - status file      (storage/massive_benchmark_status_shardN.json)
#   - per-task dir     (storage/massive_benchmark_tasks_shardN/)
#   - rounds JSONL log (storage/massive_benchmark_rounds_shardN.jsonl)
#
# Total task bank = 105 tasks. With N shards, each processes 105/N tasks per round.
# Combined throughput = N × (1 task / ~50s) = N×0.02 tasks/sec.
#
# Resource limits on this sandbox:
#   - 2 CPU cores (hard limit) → use --max-workers 2 to share CPU across shards
#   - 3.9 GB RAM total, ~500 MB per orchestrator instance → max ~5 shards
#   - Each shard auto-restarts via the wrapper if the python process dies.
#
# Usage:
#   bash scripts/run_benchmark_cluster.sh start   [N=3] [MAX_WORKERS=2]
#   bash scripts/run_benchmark_cluster.sh status
#   bash scripts/run_benchmark_cluster.sh stop
#
# Default N=3 shards, MAX_WORKERS=2 each → 6 threads competing for 2 cores
# (oversubscribed but fine since most time is in subprocess I/O).

set -u

cd /home/z/my-project/METAENGINE_SLICE3_RESTORED
STORAGE_DIR=storage
mkdir -p "$STORAGE_DIR"

CMD="${1:-status}"

case "$CMD" in
  start)
    N="${2:-3}"
    MAX_WORKERS="${3:-2}"
    echo "=== Starting cluster of $N shards (max_workers=$MAX_WORKERS each) ==="
    # Clean any previous cluster state
    rm -f "$STORAGE_DIR"/massive_benchmark_*shard*.pid 2>/dev/null
    rm -f "$STORAGE_DIR"/cluster_*.json 2>/dev/null

    # Load .env.local if present (for LLM API keys: GROQ, OPENROUTER, etc.)
    if [ -f .env.local ]; then
        set -a
        source .env.local 2>/dev/null || true
        set +a
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] loaded .env.local"
    fi

    for i in $(seq 0 $((N-1))); do
      SHARD_ID=$i
      INSTANCE_ID="shard${i}"
      LOG_FILE="$STORAGE_DIR/massive_benchmark_${INSTANCE_ID}.nohup.out"
      STATUS_FILE="$STORAGE_DIR/massive_benchmark_status_${INSTANCE_ID}.json"
      TASKS_DIR="$STORAGE_DIR/massive_benchmark_tasks_${INSTANCE_ID}"
      ROUNDS_LOG="$STORAGE_DIR/massive_benchmark_rounds_${INSTANCE_ID}.jsonl"

      # Clean previous artifacts for this shard
      rm -rf "$TASKS_DIR" "$STATUS_FILE" "$ROUNDS_LOG" "$LOG_FILE" 2>/dev/null

      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] launching shard $i (instance_id=$INSTANCE_ID, shard_id=$SHARD_ID, shard_count=$N)..."
      setsid -f python3 scripts/run_massive_benchmark.py \
        --rounds 0 \
        --tasks-per-round 0 \
        --max-workers "$MAX_WORKERS" \
        --sleep-between-rounds 5 \
        --no-zai --minimal-output \
        --instance-id "$INSTANCE_ID" \
        --shard-id "$SHARD_ID" \
        --shard-count "$N" \
        > "$LOG_FILE" 2>&1 < /dev/null
    done

    # Save cluster config
    cat > "$STORAGE_DIR/cluster_config.json" << EOF
{
  "shard_count": $N,
  "max_workers_per_shard": $MAX_WORKERS,
  "launched_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "task_bank_size": 105,
  "tasks_per_shard": $((105 / N)),
  "total_max_workers": $((N * MAX_WORKERS))
}
EOF
    echo ""
    echo "✓ Cluster launched: $N shards × $MAX_WORKERS workers = $((N * MAX_WORKERS)) total threads"
    echo "  Status: bash scripts/run_benchmark_cluster.sh status"
    echo "  Stop:   bash scripts/run_benchmark_cluster.sh stop"
    ;;

  status)
    echo "=== Cluster status @ $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
    echo ""
    if [ -f "$STORAGE_DIR/cluster_config.json" ]; then
      cat "$STORAGE_DIR/cluster_config.json"
    else
      echo "Cluster config not found — cluster may not be running."
    fi
    echo ""
    echo "=== Per-shard status ==="
    for SHARD_LOG in "$STORAGE_DIR"/massive_benchmark_status_shard*.json; do
      [ -f "$SHARD_LOG" ] || continue
      SHARD_NAME=$(basename "$SHARD_LOG" | sed 's/massive_benchmark_status_//; s/.json//')
      echo ""
      echo "--- $SHARD_NAME ---"
      cat "$SHARD_LOG"
    done
    echo ""
    echo "=== Live processes ==="
    ps aux | grep -E "run_massive_benchmark" | grep -v grep | awk '{print $2, $4"%MEM", $11, $12, $13, $14, $15, $16, $17, $18, $19, $20}' | head -20
    echo ""
    echo "=== Combined task completion ==="
    for d in "$STORAGE_DIR"/massive_benchmark_tasks_shard*; do
      [ -d "$d" ] || continue
      SHARD=$(basename "$d" | sed 's/massive_benchmark_tasks_//')
      # Count latest round tasks
      LATEST_ROUND=$(ls "$d" 2>/dev/null | sort | tail -1)
      if [ -n "$LATEST_ROUND" ]; then
        COUNT=$(ls "$d/$LATEST_ROUND" 2>/dev/null | wc -l)
        echo "  $SHARD: $COUNT tasks in $LATEST_ROUND"
      fi
    done
    ;;

  stop)
    echo "=== Stopping cluster ==="
    # Kill python processes running run_massive_benchmark
    pkill -f "run_massive_benchmark" 2>/dev/null && echo "✓ killed python benchmark processes" || echo "no python processes found"
    sleep 2
    # Force-kill if any survived
    pkill -9 -f "run_massive_benchmark" 2>/dev/null
    rm -f "$STORAGE_DIR"/massive_benchmark_*shard*.pid 2>/dev/null
    echo "✓ Cluster stopped"
    ;;

  restart)
    bash "$0" stop
    sleep 3
    bash "$0" start "${2:-3}" "${3:-2}"
    ;;

  *)
    echo "Usage: bash $0 {start|status|stop|restart} [N=3] [MAX_WORKERS=2]"
    echo ""
    echo "Commands:"
    echo "  start [N] [W]   Launch N shards with W max_workers each (default: 3 shards × 2 workers)"
    echo "  status          Show live status of all shards"
    echo "  stop            Kill all benchmark processes"
    echo "  restart         Stop and restart"
    exit 1
    ;;
esac
