#!/bin/bash
# setup_all_llm_keys.sh — Interactive setup for ALL discovered LLM providers.
#
# This script:
#   1. Reads the discovered_providers.json (written by resource_discovery_agent)
#   2. Shows which providers have working endpoints
#   3. Prompts for API keys for each provider (with signup URLs)
#   4. Tests each key via LiteLLM
#   5. Saves all keys to .env.local (gitignored)
#   6. Pushes keys as GitHub secrets (via API)
#
# Usage:
#   bash scripts/setup_all_llm_keys.sh
#
# Non-interactive mode (keys pre-set in env):
#   GROQ_API_KEY=... OPENROUTER_API_KEY=... bash scripts/setup_all_llm_keys.sh --non-interactive

set -u

cd /home/z/my-project/METAENGINE_SLICE3_RESTORED

ENV_FILE=.env.local
NON_INTERACTIVE="${1:-}"

# Load existing keys if .env.local exists
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE" 2>/dev/null || true
    set +a
fi

echo "============================================================"
echo "  MetaEngine — All LLM Provider Key Setup"
echo "============================================================"
echo ""

# === Provider registry with signup URLs + free tier info ===
# (mirrors multi_provider_validator.py PROVIDERS list)
declare -A PROVIDER_INFO
PROVIDER_INFO["groq"]="https://console.groq.com/keys|500 req/min FREE|groq/llama-3.1-70b-versatile"
PROVIDER_INFO["openrouter"]="https://openrouter.ai/keys|20 req/min free tier|openrouter/meta-llama/llama-3.1-8b-instruct:free"
PROVIDER_INFO["together"]="https://api.together.xyz/settings/api-keys|\$5 free credit|together_ai/Meta-Llama-3.1-70B-Instruct-Turbo"
PROVIDER_INFO["gemini"]="https://aistudio.google.com/app/apikey|60 req/min FREE|gemini/gemini-1.5-flash"
PROVIDER_INFO["huggingface"]="https://huggingface.co/settings/tokens|10 req/min free|huggingface/meta-llama/Meta-Llama-3-70B-Instruct"
PROVIDER_INFO["cohere"]="https://dashboard.cohere.com/api-keys|trial key free|cohere/command-r"
PROVIDER_INFO["anthropic"]="https://console.anthropic.com/settings/keys|\$5 free credit|anthropic/claude-3-5-sonnet-20240620"
PROVIDER_INFO["openai"]="https://platform.openai.com/api-keys|pay per use|openai/gpt-4o-mini"
PROVIDER_INFO["mistral"]="https://console.mistral.ai/api-keys|free tier|mistral/mistral-large-latest"

# Env var name for each provider
declare -A PROVIDER_ENV
PROVIDER_ENV["groq"]="GROQ_API_KEY"
PROVIDER_ENV["openrouter"]="OPENROUTER_API_KEY"
PROVIDER_ENV["together"]="TOGETHER_API_KEY"
PROVIDER_ENV["gemini"]="GEMINI_API_KEY"
PROVIDER_ENV["huggingface"]="HUGGINGFACE_API_KEY"
PROVIDER_ENV["cohere"]="COHERE_API_KEY"
PROVIDER_ENV["anthropic"]="ANTHROPIC_API_KEY"
PROVIDER_ENV["openai"]="OPENAI_API_KEY"
PROVIDER_ENV["mistral"]="MISTRAL_API_KEY"

# Function to prompt for a key
prompt_key() {
    local provider="$1"
    local info="${PROVIDER_INFO[$provider]}"
    local env_var="${PROVIDER_ENV[$provider]}"
    IFS='|' read -r signup_url free_tier model <<< "$info"
    local current_val="${!env_var:-}"
    local input

    echo "---"
    echo "Provider: $provider"
    echo "  Model:    $model"
    echo "  Free tier: $free_tier"
    echo "  Sign up:  $signup_url"
    echo "  Env var:  $env_var"

    if [ -n "$current_val" ]; then
        echo "  Current:  ${current_val:0:8}...${current_val: -4} (set)"
        if [ "$NON_INTERACTIVE" != "--non-interactive" ]; then
            read -p "  Update? [y/N] " -r update
            if [[ ! "$update" =~ ^[Yy]$ ]]; then
                return 0
            fi
        else
            echo "  (non-interactive mode — keeping existing key)"
            return 0
        fi
    fi

    if [ "$NON_INTERACTIVE" != "--non-interactive" ]; then
        read -p "  Enter $env_var (or press Enter to skip): " -r input
        if [ -n "$input" ]; then
            # Write to env file
            if grep -q "^$env_var=" "$ENV_FILE" 2>/dev/null; then
                sed -i "s|^$env_var=.*|$env_var=$input|" "$ENV_FILE"
            else
                echo "$env_var=$input" >> "$ENV_FILE"
            fi
            export "$env_var=$input"
            echo "  ✓ Saved $env_var to $ENV_FILE"
        else
            echo "  Skipped $provider"
        fi
    fi
}

# Make sure env file exists
touch "$ENV_FILE"

echo "Discovered providers from resource_discovery_agent:"
echo ""
python3 -c "
import json
try:
    d = json.load(open('storage/resource_discovery_state.json'))
    providers = d.get('all_discovered_providers', [])
    print(f'  Total discovered: {len(providers)}')
    for p in providers:
        works = '✓' if p.get('works') else '✗'
        print(f'  {works} {p[\"provider_name\"]:15s} endpoint={p.get(\"api_endpoint\",\"?\")}')
except Exception as e:
    print(f'  Could not read discovery state: {e}')
" 2>/dev/null
echo ""

echo "============================================================"
echo "  Setting up API keys for all providers"
echo "============================================================"
echo ""

# Prompt for each provider
for provider in groq openrouter together gemini huggingface cohere anthropic openai mistral; do
    prompt_key "$provider"
done

echo ""
echo "============================================================"
echo "  Verifying keys via LiteLLM"
echo "============================================================"
set -a
source "$ENV_FILE" 2>/dev/null || true
set +a

# Test each key via LiteLLM
python3 << 'PYEOF'
import os
import sys
import time

sys.path.insert(0, '/home/z/my-project/METAENGINE_SLICE3_RESTORED')

try:
    import litellm
    litellm.suppress_debug_info = True
except ImportError:
    print("litellm not installed — skipping verification")
    sys.exit(0)

providers = [
    ("groq", "groq/llama-3.1-70b-versatile", "GROQ_API_KEY"),
    ("openrouter", "openrouter/meta-llama/llama-3.1-8b-instruct:free", "OPENROUTER_API_KEY"),
    ("together", "together_ai/Meta-Llama-3.1-70B-Instruct-Turbo", "TOGETHER_API_KEY"),
    ("gemini", "gemini/gemini-1.5-flash", "GEMINI_API_KEY"),
    ("huggingface", "huggingface/meta-llama/Meta-Llama-3-70B-Instruct", "HUGGINGFACE_API_KEY"),
    ("cohere", "cohere/command-r", "COHERE_API_KEY"),
    ("anthropic", "anthropic/claude-3-5-sonnet-20240620", "ANTHROPIC_API_KEY"),
    ("openai", "openai/gpt-4o-mini", "OPENAI_API_KEY"),
    ("mistral", "mistral/mistral-large-latest", "MISTRAL_API_KEY"),
]

working = []
for name, model, env_var in providers:
    api_key = os.getenv(env_var, "")
    if not api_key:
        print(f"  {name:15s} NO KEY — skipped")
        continue
    try:
        t0 = time.perf_counter()
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "Reply with: OK"}],
            api_key=api_key,
            max_tokens=10,
            temperature=0.0,
            timeout=15,
        )
        latency = (time.perf_counter() - t0) * 1000
        content = response.choices[0].message.content or ""
        ok = "ok" in content.lower()
        status = "✓ WORKS" if ok else f"✗ unexpected response: {content[:50]}"
        print(f"  {name:15s} {status} ({latency:.0f}ms)")
        if ok:
            working.append(name)
    except Exception as e:
        err = str(e)[:80]
        print(f"  {name:15s} ✗ {err}")

print()
print(f"Working providers: {len(working)}/{len([p for p in providers if os.getenv(p[2])])}")
print(f"  {working}")
PYEOF

echo ""
echo "============================================================"
echo "  Pushing keys as GitHub secrets"
echo "============================================================"

# Push all set keys as GitHub secrets
python3 << 'PYEOF'
import os
import sys
import json
import base64
import urllib.request

# Use python3.13 for nacl (libsodium)
sys.path.insert(0, '/home/z/.local/lib/python3.13/site-packages')

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
REPO = "PatrickFrome/EngineTest"

try:
    from nacl import encoding, public
except ImportError:
    print("  pynacl not available — skipping GitHub secrets push")
    sys.exit(0)

def api_call(method, endpoint, data=None):
    url = f"https://api.github.com/repos/{REPO}/{endpoint}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, json.loads(resp.read().decode())

# Get repo public key
try:
    status, key_data = api_call("GET", "actions/secrets/public-key")
    print(f"  Repo public key: {key_data['key_id']}")
except Exception as e:
    print(f"  Could not get repo public key: {e}")
    sys.exit(1)

# Encrypt and set each secret
pub_key = public.PublicKey(key_data["key"].encode(), encoder=encoding.Base64Encoder())
sealed = public.SealedBox(pub_key)

secrets_to_set = [
    ("GROQ_API_KEY", os.getenv("GROQ_API_KEY", "")),
    ("OPENROUTER_API_KEY", os.getenv("OPENROUTER_API_KEY", "")),
    ("TOGETHER_API_KEY", os.getenv("TOGETHER_API_KEY", "")),
    ("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", "")),
    ("HUGGINGFACE_API_KEY", os.getenv("HUGGINGFACE_API_KEY", "")),
    ("COHERE_API_KEY", os.getenv("COHERE_API_KEY", "")),
    ("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY", "")),
    ("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", "")),
    ("MISTRAL_API_KEY", os.getenv("MISTRAL_API_KEY", "")),
]

set_count = 0
for name, value in secrets_to_set:
    if not value:
        print(f"  {name}: no key set — skipping")
        continue
    try:
        encrypted = sealed.encrypt(value.encode())
        b64_encrypted = base64.b64encode(encrypted).decode()
        status, _ = api_call("PUT", f"actions/secrets/{name}", {
            "encrypted_value": b64_encrypted,
            "key_id": key_data["key_id"],
        })
        print(f"  {name}: ✓ set (HTTP {status})")
        set_count += 1
    except Exception as e:
        print(f"  {name}: ✗ failed: {e}")

print()
print(f"✓ Pushed {set_count} secrets to GitHub repo {REPO}")
PYEOF

echo ""
echo "============================================================"
echo "  Setup complete!"
echo "============================================================"
echo ""
echo "Keys saved to: $ENV_FILE"
echo ""
echo "Next steps:"
echo "  1. Restart benchmark cluster to pick up new keys:"
echo "     bash scripts/run_benchmark_cluster.sh restart"
echo "  2. Restart improvement_loop to use LLM judges:"
echo "     bash scripts/run_improvement_loop.sh"
echo "  3. Monitor LLM provider status:"
echo "     cat storage/llm_provider_probe_results.json | python3 -m json.tool"
echo ""
echo "To verify GitHub secrets:"
echo "  curl -sS -H 'Authorization: token $GITHUB_TOKEN' \\"
echo "    https://api.github.com/repos/PatrickFrome/EngineTest/actions/secrets"
