#!/bin/bash
# run_resource_discovery.sh — Launch the resource discovery agent.
#
# This agent constantly searches the web for new free resources (LLM APIs,
# compute, datasets, CI/CD) and adds working ones to MetaEngine automatically.
#
# Search strategies (no API keys required):
#   1. z-ai web_search (when not rate-limited)
#   2. DuckDuckGo HTML scraping (always available)
#   3. GitHub repos search (for code/benchmark queries)
#   4. HuggingFace model hub (for model/inference queries)
#
# When a new provider is found and tested working:
#   - A patch is written to metaengine/adaptation_patches/provider_addition_*.json
#   - multi_provider_validator.py reads these patches at startup
#   - The provider becomes available to all benchmark shards automatically
#
# Logs:
#   storage/resource_discovery.log
#   storage/resource_discovery_state.json
#   storage/discovered_providers.json
#
# To stop:
#   pkill -f "resource_discovery_agent"
#
# To monitor:
#   tail -f storage/resource_discovery.log
#   cat storage/discovered_providers.json | python3 -m json.tool

set -u
cd /home/z/my-project/METAENGINE_SLICE3_RESTORED

# Load .env.local if present
if [ -f .env.local ]; then
    set -a
    source .env.local 2>/dev/null || true
    set +a
fi

mkdir -p storage

# Kill any existing discovery agent to avoid duplicates
pkill -f "metaengine.resource_discovery_agent" 2>/dev/null
sleep 2

# Launch the discovery agent in fully detached background
# Default: 30 min interval (1800s), can be overridden
INTERVAL=${1:-1800}
setsid -f python3 -m metaengine.resource_discovery_agent \
    --forever \
    --interval $INTERVAL \
    > storage/resource_discovery.nohup.out 2>&1 < /dev/null

sleep 5
DISC_PID=$(pgrep -f "resource_discovery_agent" | head -1)
echo "Resource discovery agent started (PID: $DISC_PID)"
echo "  Interval: ${INTERVAL}s ($(($INTERVAL / 60)) min)"
echo "  Logs: storage/resource_discovery.log"
echo "  State: storage/resource_discovery_state.json"
echo "  Discovered providers: storage/discovered_providers.json"
echo "  Stop: pkill -f resource_discovery_agent"
echo ""
echo "=== Last 15 log lines ==="
tail -15 storage/resource_discovery.log 2>/dev/null
