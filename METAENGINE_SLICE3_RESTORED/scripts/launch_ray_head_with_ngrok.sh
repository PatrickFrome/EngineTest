#!/bin/bash
# launch_ray_head_with_ngrok.sh — Start Ray head node + ngrok tunnel for Colab GPU worker.
#
# This script:
#   1. Installs Ray if needed
#   2. Starts Ray head node on port 6379
#   3. Installs ngrok if needed
#   4. Starts ngrok TCP tunnel on port 6379
#   5. Prints the ngrok URL to paste into the Colab notebook
#
# After this runs:
#   - Open colab_gpu_worker.ipynb in Google Colab
#   - Set RAY_ADDRESS to the printed ngrok URL
#   - Run all cells → Colab T4 GPU joins our Ray cluster
#
# Prerequisites:
#   - ngrok auth token (free at https://dashboard.ngrok.com/get-started/your-authtoken)
#     Set it via: export NGROK_AUTHTOKEN=your_token_here
#     Or run: ngrok config add-authtoken YOUR_TOKEN

set -u

cd /home/z/my-project/METAENGINE_SLICE3_RESTORED

echo "============================================================"
echo "  MetaEngine Ray Head + ngrok Tunnel Launcher"
echo "============================================================"
echo ""

# --- Step 1: Install Ray if needed ---
if ! python3 -c "import ray" 2>/dev/null; then
    echo "[1/5] Installing Ray..."
    pip install --quiet --break-system-packages ray 2>&1 | tail -3
fi
echo "[1/5] ✓ Ray available: $(python3 -c 'import ray; print(ray.__version__)')"
echo ""

# --- Step 2: Stop any existing Ray head ---
echo "[2/5] Stopping any existing Ray head..."
ray stop --force 2>/dev/null || true
sleep 2
echo ""

# --- Step 3: Start Ray head node ---
# We have 2 CPUs locally. Ray will use them for driver-side work.
# The Colab GPU worker will add 2 more CPUs + 1 GPU via Ray.
echo "[3/5] Starting Ray head node on port 6379..."
ray start --head --port=6379 --num-cpus=2 --include-dashboard=false 2>&1 | tail -10
sleep 3

# Verify Ray is running
if ray status 2>&1 | grep -q "Running"; then
    echo "  ✓ Ray head node is running"
else
    echo "  ✗ Ray head failed to start"
    exit 1
fi
echo ""

# --- Step 4: Install ngrok if needed ---
echo "[4/5] Checking for ngrok..."
if ! command -v ngrok &> /dev/null; then
    echo "  ngrok not found — installing..."
    # Try snap first, then direct download
    if command -v snap &> /dev/null; then
        sudo snap install ngrok 2>&1 | tail -3 || true
    fi
    if ! command -v ngrok &> /dev/null; then
        # Direct download
        curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok-v3-stable-linux-amd64.tgz -o /tmp/ngrok.tgz
        tar -xzf /tmp/ngrok.tgz -C /tmp
        chmod +x /tmp/ngrok
        export PATH=$PATH:/tmp
        NGROK_BIN=/tmp/ngrok
    else
        NGROK_BIN=ngrok
    fi
else
    NGROK_BIN=ngrok
fi
echo "  ✓ ngrok: $($NGROK_BIN --version 2>&1 || echo 'installed')"
echo ""

# Set ngrok auth token if provided
if [ -n "${NGROK_AUTHTOKEN:-}" ]; then
    echo "  Setting ngrok auth token..."
    $NGROK_BIN config add-authtoken "$NGROK_AUTHTOKEN" 2>&1 | tail -2
fi
echo ""

# --- Step 5: Start ngrok TCP tunnel on port 6379 ---
echo "[5/5] Starting ngrok TCP tunnel on port 6379..."
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ⚠️  ACTION REQUIRED:                                     ║"
echo "║                                                          ║"
echo "║  ngrok URL will appear below in a few seconds.          ║"
echo "║  Copy it and paste into colab_gpu_worker.ipynb           ║"
echo "║  (replace RAY_ADDRESS value)                             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Start ngrok in background, capture its output
$NGROK_BIN tcp 6379 --log=stdout > /tmp/ngrok_ray.log 2>&1 &
NGROK_PID=$!
echo $NGROK_PID > /tmp/ngrok_ray.pid
sleep 5

# Query ngrok's local API to get the public URL
echo "Waiting for ngrok tunnel to establish..."
for i in $(seq 1 12); do
    TUNNEL_JSON=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null)
    if [ -n "$TUNNEL_JSON" ]; then
        PUBLIC_URL=$(echo "$TUNNEL_JSON" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for t in d.get('tunnels', []):
        if t.get('proto') == 'tcp':
            print(t.get('public_url', ''))
            break
except: pass
" 2>/dev/null)
        if [ -n "$PUBLIC_URL" ]; then
            break
        fi
    fi
    sleep 2
done

if [ -n "$PUBLIC_URL" ]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  ✓ NGROK TUNNEL ACTIVE                                    ║"
    echo "║                                                          ║"
    echo "║  RAY_ADDRESS = \"$PUBLIC_URL\"               ║"
    echo "║                                                          ║"
    echo "║  Paste this URL into colab_gpu_worker.ipynb              ║"
    echo "║  (config cell, RAY_ADDRESS variable)                     ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo "ngrok PID: $NGROK_PID (saved to /tmp/ngrok_ray.pid)"
    echo ""
    echo "Next steps:"
    echo "  1. Upload scripts/colab_gpu_worker.ipynb to Google Drive"
    echo "  2. Open in Colab (Runtime → Change runtime type → T4 GPU)"
    echo "  3. Set RAY_ADDRESS = \"$PUBLIC_URL\""
    echo "  4. Runtime → Run all"
    echo "  5. Colab T4 GPU joins this Ray cluster for 12 hours"
    echo ""
    echo "To stop ngrok: kill \$(cat /tmp/ngrok_ray.pid)"
    echo "To stop Ray: ray stop"
else
    echo "✗ Could not get ngrok public URL."
    echo "  Check /tmp/ngrok_ray.log for details."
    echo "  You may need to set NGROK_AUTHTOKEN env var."
    echo "  Get one at: https://dashboard.ngrok.com/get-started/your-authtoken"
    echo ""
    echo "ngrok log:"
    tail -20 /tmp/ngrok_ray.log 2>/dev/null
fi
