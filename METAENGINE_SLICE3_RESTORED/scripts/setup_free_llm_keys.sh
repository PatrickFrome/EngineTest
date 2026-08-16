#!/bin/bash
# setup_free_llm_keys.sh — Interactive setup for free external LLM API keys.
#
# This script:
#   1. Explains each free provider
#   2. Asks for API keys (or lets user skip)
#   3. Writes them to .env.local (gitignored)
#   4. Verifies each key works via LiteLLM
#
# Once .env.local exists, all benchmark runners automatically pick up the keys
# and use multi-provider failover for LLM judging.
#
# Free providers (as of 2026):
#   Groq         — https://console.groq.com/keys         (500 req/min, Llama 3.1 70B)
#   OpenRouter   — https://openrouter.ai/keys            (free Llama 3.1 8B, Mistral 7B)
#   Together AI  — https://api.together.xyz/settings/api-keys  ($5 free credit)
#   Google Gemini— https://aistudio.google.com/app/apikey (60 req/min, Gemini 1.5 Flash)
#   Hugging Face  — https://huggingface.co/settings/tokens (free for some models)
#   Cohere       — https://dashboard.cohere.com/api-keys  (trial key, Command R)

set -u

cd /home/z/my-project/METAENGINE_SLICE3_RESTORED
ENV_FILE=.env.local

echo "============================================================"
echo "  MetaEngine — Free LLM API Key Setup"
echo "============================================================"
echo ""
echo "This script configures free external LLM providers for"
echo "the benchmark runner's LLM-as-judge validator."
echo ""
echo "Each provider has a FREE tier sufficient for benchmarking:"
echo "  Groq          — 500 req/min, Llama 3.1 70B (BEST)"
echo "  OpenRouter    — free Llama/Mistral models"
echo "  Together AI   — \$5 free credit"
echo "  Gemini        — 60 req/min, Gemini 1.5 Flash"
echo "  Hugging Face  — free for some models"
echo "  Cohere        — trial key, Command R"
echo ""
echo "You can skip any provider — the validator uses failover."
echo "At least ONE working key is enough to enable LLM judging."
echo ""

# Load existing keys if any
if [ -f "$ENV_FILE" ]; then
    echo "Found existing $ENV_FILE — loading current values..."
    set -a
    source "$ENV_FILE" 2>/dev/null || true
    set +a
fi

# Function to prompt for a key
prompt_key() {
    local var_name="$1"
    local provider_name="$2"
    local signup_url="$3"
    local current_val="${!var_name:-}"
    local input

    echo "---"
    echo "Provider: $provider_name"
    echo "Sign up:  $signup_url"
    if [ -n "$current_val" ]; then
        echo "Current:  ${current_val:0:8}...${current_val: -4} (set)"
        read -p "Update? [y/N] " -r update
        if [[ ! "$update" =~ ^[Yy]$ ]]; then
            return 0
        fi
    fi
    read -p "Enter $var_name (or press Enter to skip): " -r input
    if [ -n "$input" ]; then
        # Write to env file
        if grep -q "^$var_name=" "$ENV_FILE" 2>/dev/null; then
            sed -i "s|^$var_name=.*|$var_name=$input|" "$ENV_FILE"
        else
            echo "$var_name=$input" >> "$ENV_FILE"
        fi
        export "$var_name=$input"
        echo "✓ Saved $var_name to $ENV_FILE"
    else
        echo "Skipped $provider_name"
    fi
}

# Make sure env file exists
touch "$ENV_FILE"

prompt_key GROQ_API_KEY          "Groq (Llama 3.1 70B, 500 req/min)" "https://console.groq.com/keys"
prompt_key OPENROUTER_API_KEY     "OpenRouter (free Llama/Mistral)"   "https://openrouter.ai/keys"
prompt_key TOGETHER_API_KEY      "Together AI (\$5 free credit)"    "https://api.together.xyz/settings/api-keys"
prompt_key GEMINI_API_KEY        "Google Gemini (60 req/min)"        "https://aistudio.google.com/app/apikey"
prompt_key HUGGINGFACE_API_KEY   "Hugging Face (some models free)"   "https://huggingface.co/settings/tokens"
prompt_key COHERE_API_KEY         "Cohere (trial, Command R)"         "https://dashboard.cohere.com/api-keys"

echo ""
echo "============================================================"
echo "  Verifying keys via LiteLLM..."
echo "============================================================"
set -a
source "$ENV_FILE" 2>/dev/null || true
set +a

python3 metaengine/multi_provider_validator.py 2>&1 | head -20

echo ""
echo "============================================================"
echo "  Setup complete"
echo "============================================================"
echo ""
echo "Keys saved to: $ENV_FILE"
echo ""
echo "To enable these keys for benchmark runners, either:"
echo "  1. Source the file before launching:  source $ENV_FILE"
echo "  2. Restart the benchmark cluster:"
echo "     bash scripts/run_benchmark_cluster.sh restart"
echo ""
echo "The multi-provider validator will use these keys with automatic"
echo "failover: Groq first (fastest), then OpenRouter, Together, etc."
echo ""
echo "To verify keys work end-to-end, run:"
echo "  python3 -c \\"
echo "  \"from metaengine.multi_provider_validator import MultiProviderValidator; \\"
echo "  v = MultiProviderValidator(); print(v.judge('What is 2+2?', '4', 'The answer is 4.'))\""
