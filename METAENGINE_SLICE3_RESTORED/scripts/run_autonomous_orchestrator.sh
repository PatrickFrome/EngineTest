#!/bin/bash
# run_autonomous_orchestrator.sh — Launch the autonomous self-improving agent.
#
# This agent runs ON TOP of the improvement_loop and:
#   1. Probes LLM providers every 10 minutes (finds which actually work)
#   2. Snapshots system resources
#   3. Restarts dead improvement_loop process if needed
#   4. Generates meta-patches that tune the improvement_loop itself
#   5. Publishes status to Turso every 5 cycles
#
# Logs:
#   storage/autonomous_orchestrator.log         — human-readable progress
#   storage/autonomous_orchestrator_state.json  — cycle history
#   storage/llm_provider_probe_results.json     — which LLMs are working
#   storage/autonomous_orchestrator.nohup.out   — stderr capture
#
# To stop:
#   pkill -f "autonomous_orchestrator"
#
# To monitor:
#   tail -f storage/autonomous_orchestrator.log
#   cat storage/autonomous_orchestrator_state.json | python3 -m json.tool
#   cat storage/llm_provider_probe_results.json | python3 -m json.tool

set -u
cd /home/z/my-project/METAENGINE_SLICE3_RESTORED

# Load .env.local if present (for LLM API keys)
if [ -f .env.local ]; then
    set -a
    source .env.local 2>/dev/null || true
    set +a
fi

mkdir -p storage

# Kill any existing orchestrator to avoid duplicates
pkill -f "metaengine.autonomous_orchestrator" 2>/dev/null
sleep 2

# Launch the orchestrator in fully detached background
setsid -f python3 -m metaengine.autonomous_orchestrator \
    --forever \
    --interval ${1:-600} \
    > storage/autonomous_orchestrator.nohup.out 2>&1 < /dev/null

sleep 5
ORCH_PID=$(pgrep -f "autonomous_orchestrator" | head -1)
echo "Autonomous orchestrator started (PID: $ORCH_PID)"
echo "  Logs: storage/autonomous_orchestrator.log"
echo "  State: storage/autonomous_orchestrator_state.json"
echo "  Probe results: storage/llm_provider_probe_results.json"
echo "  Stop: pkill -f autonomous_orchestrator"
echo ""
echo "=== Last 15 log lines ==="
tail -15 storage/autonomous_orchestrator.log 2>/dev/null
