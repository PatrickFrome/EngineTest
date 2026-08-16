#!/bin/bash
# push_to_github.sh — Push MetaEngine repo to GitHub.
#
# USAGE:
#   GITHUB_USER=<your-username> GITHUB_REPO=<new-repo-name> GITHUB_TOKEN=<PAT> \
#     bash scripts/push_to_github.sh
#
# REQUIRED ENVIRONMENT VARIABLES:
#   GITHUB_USER  — your GitHub username (e.g., "PatrickFrome")
#   GITHUB_REPO  — new repo name (e.g., "metaengine")
#   GITHUB_TOKEN — Personal Access Token with repo:public_repo + workflow scope
#                  Create at: https://github.com/settings/tokens
#
# WHAT THIS SCRIPT DOES:
#   1. Validates env vars are set
#   2. Tests the GitHub token via API
#   3. Creates a new PUBLIC repo via the GitHub REST API
#   4. Sets the git remote to https://github.com/<user>/<repo>.git
#   5. Pushes the main branch with --force-with-lease (safe first push)
#   6. Prints the repo URL
#
# The repo will be PUBLIC (required for free GitHub Actions minutes).
# After push, the distributed-benchmark.yml workflow runs automatically
# every 6 hours (8 parallel shards).
#
# To enable cloud LLM judges on GitHub, set these as repo secrets:
#   GROQ_API_KEY (recommended — 500 req/min free)
#   TURSO_DB_TOKEN + TURSO_DB_HOST (already have these)

set -eu

cd /home/z/my-project

# --- Validate env vars ---
if [ -z "${GITHUB_USER:-}" ]; then
    echo "ERROR: GITHUB_USER is not set"
    echo "  export GITHUB_USER=<your-username>"
    exit 1
fi
if [ -z "${GITHUB_REPO:-}" ]; then
    echo "ERROR: GITHUB_REPO is not set"
    echo "  export GITHUB_REPO=<new-repo-name>"
    exit 1
fi
if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "ERROR: GITHUB_TOKEN is not set"
    echo "  Get a Personal Access Token at:"
    echo "    https://github.com/settings/tokens?scopes=repo,workflow"
    echo "  Then: export GITHUB_TOKEN=<paste-token>"
    exit 1
fi

REPO_URL="https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${GITHUB_REPO}.git"
PUBLIC_URL="https://github.com/${GITHUB_USER}/${GITHUB_REPO}"

echo "============================================================"
echo "  MetaEngine GitHub Push"
echo "============================================================"
echo "  User     : $GITHUB_USER"
echo "  Repo     : $GITHUB_REPO"
echo "  Visibility: PUBLIC (required for free Actions minutes)"
echo "  Token    : ${GITHUB_TOKEN:0:8}...${GITHUB_TOKEN: -4}"
echo "============================================================"
echo ""

# --- Step 1: Test token ---
echo "[1/5] Testing GitHub token..."
RESP=$(curl -sS -o /tmp/gh_test.json -w "%{http_code}" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/user)
if [ "$RESP" != "200" ]; then
    echo "ERROR: token test failed (HTTP $RESP)"
    cat /tmp/gh_test.json
    exit 1
fi
USER_LOGIN=$(python3 -c "import json; print(json.load(open('/tmp/gh_test.json'))['login'])")
echo "  ✓ Token valid — authenticated as $USER_LOGIN"
if [ "$USER_LOGIN" != "$GITHUB_USER" ]; then
    echo "  ⚠ Warning: token username ($USER_LOGIN) != GITHUB_USER ($GITHUB_USER)"
    echo "    Using $USER_LOGIN as the actual username..."
    GITHUB_USER="$USER_LOGIN"
    REPO_URL="https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${GITHUB_REPO}.git"
    PUBLIC_URL="https://github.com/${GITHUB_USER}/${GITHUB_REPO}"
fi
echo ""

# --- Step 2: Check if repo already exists, create if not ---
echo "[2/5] Checking if repo $GITHUB_USER/$GITHUB_REPO exists..."
RESP=$(curl -sS -o /tmp/gh_repo.json -w "%{http_code}" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$GITHUB_USER/$GITHUB_REPO")
if [ "$RESP" = "200" ]; then
    echo "  ✓ Repo already exists"
    IS_PRIVATE=$(python3 -c "import json; print(json.load(open('/tmp/gh_repo.json'))['private'])")
    if [ "$IS_PRIVATE" = "True" ]; then
        echo "  ⚠ Repo is PRIVATE — GitHub Actions will count against your paid minutes."
        echo "    To make it PUBLIC (for free Actions), visit:"
        echo "    $PUBLIC_URL/settings → Danger Zone → Change visibility"
    fi
elif [ "$RESP" = "404" ]; then
    echo "  → Creating new PUBLIC repo $GITHUB_USER/$GITHUB_REPO..."
    RESP=$(curl -sS -o /tmp/gh_create.json -w "%{http_code}" \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        -X POST \
        -d "{\"name\":\"$GITHUB_REPO\",\"description\":\"MetaEngine 2.3 — 16-engine dialectical AI system with constitutional core, BoTorch GP surrogate, LangGraph orchestrator, multi-provider LLM validation\",\"private\":false,\"has_issues\":true,\"has_projects\":false,\"has_wiki\":false,\"auto_init\":false}" \
        https://api.github.com/user/repos)
    if [ "$RESP" != "201" ]; then
        echo "ERROR: repo creation failed (HTTP $RESP)"
        cat /tmp/gh_create.json
        exit 1
    fi
    echo "  ✓ Created PUBLIC repo"
else
    echo "ERROR: unexpected HTTP $RESP"
    cat /tmp/gh_repo.json
    exit 1
fi
echo ""

# --- Step 3: Configure git remote ---
echo "[3/5] Setting git remote origin..."
if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "$REPO_URL"
    echo "  ✓ Updated existing remote"
else
    git remote add origin "$REPO_URL"
    echo "  ✓ Added new remote"
fi
git remote -v | head -2
echo ""

# --- Step 4: Push ---
echo "[4/5] Pushing main branch (this may take a minute)..."
echo "  Repo size: $(du -sh .git | cut -f1) on disk"
git push --force-with-lease -u origin main 2>&1 | tail -10
echo ""

# --- Step 5: Verify ---
echo "[5/5] Verifying push..."
RESP=$(curl -sS -o /tmp/gh_verify.json -w "%{http_code}" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$GITHUB_USER/$GITHUB_REPO/commits?per_page=1")
if [ "$RESP" = "200" ]; then
    SHA=$(python3 -c "import json; d=json.load(open('/tmp/gh_verify.json')); print(d[0]['sha'][:7]) if d else print('none')")
    MSG=$(python3 -c "import json; d=json.load(open('/tmp/gh_verify.json')); print(d[0]['commit']['message'].split('\n')[0][:80]) if d else print('no commits')")
    echo "  ✓ Push verified — HEAD commit:"
    echo "    $SHA  $MSG"
else
    echo "  ⚠ Could not verify push (HTTP $RESP)"
fi
echo ""

echo "============================================================"
echo "  ✅ Push complete!"
echo "============================================================"
echo ""
echo "Repo URL: $PUBLIC_URL"
echo ""
echo "Next steps:"
echo "  1. Set repository secrets for distributed-benchmark.yml workflow:"
echo "     - TURSO_DB_TOKEN  (already have)"
echo "     - TURSO_DB_HOST   (already have)"
echo "     - GROQ_API_KEY    (free at https://console.groq.com/keys)"
echo ""
echo "  Set secrets via web UI:"
echo "    $PUBLIC_URL/settings/secrets/actions"
echo ""
echo "  2. Manually trigger the distributed benchmark:"
echo "    Go to: $PUBLIC_URL/actions/workflows/distributed-benchmark.yml"
echo "    Click 'Run workflow' → choose shard count (default 8) → Run"
echo ""
echo "  3. Watch the 8 parallel shards run for up to 5h45m each."
echo "     Results sync to Turso cloud DB automatically."
echo ""
echo "  4. Analyze results anytime:"
echo "     python3 scripts/analyze_and_improve.py --use-turso"
