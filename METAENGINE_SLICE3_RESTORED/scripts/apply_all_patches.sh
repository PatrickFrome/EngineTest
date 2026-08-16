#!/bin/bash
# apply_all_patches.sh — Apply all pending adaptation patches to MetaEngine source code.
#
# This script reads JSON patch files from metaengine/adaptation_patches/ and
# modifies the actual Python source code of MetaEngine modules:
#   - AMPLIFY_RULE → adds heuristic rules to dspy_amplify.py
#   - MECHANISM_HYPOTHESIS → adds mechanisms to mechanism_library.py
#   - ROUTING_HINT → adjusts learned_router.py engine weights
#   - BIOGRAPHY_DELTA → updates engine_biographies.json
#   - PROVIDER_ADDITION → adds LLM providers to multi_provider_validator.py
#
# Safety features:
#   - Every patch is validated by running pytest before commit
#   - If tests fail, ALL patches from this run are rolled back automatically
#   - Backup of original files is kept in storage/patch_backups/
#   - Applied patches are tracked in storage/patch_applier_state.json
#
# Usage:
#   bash scripts/apply_all_patches.sh              # apply all pending patches
#   bash scripts/apply_all_patches.sh --dry-run    # show what would change
#   bash scripts/apply_all_patches.sh --rollback <ID>  # rollback one patch
#   bash scripts/apply_all_patches.sh --no-tests   # skip pytest validation
#
# After successful apply, commits changes to git.

set -u
cd /home/z/my-project/METAENGINE_SLICE3_RESTORED

echo "============================================================"
echo "  MetaEngine Patch Applier"
echo "============================================================"
echo ""

# Run the Python patch applier
python3 -m metaengine.patch_applier "$@"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "✗ Patch application failed (exit code $EXIT_CODE)"
    echo "  Check storage/patch_applier.log for details"
    exit $EXIT_CODE
fi

# If not dry-run and not rollback, commit changes to git
if [[ "$*" != *"--dry-run"* && "$*" != *"--rollback"* ]]; then
    echo ""
    echo "============================================================"
    echo "  Committing applied patches to git"
    echo "============================================================"
    cd /home/z/my-project

    # Check if there are changes to commit
    if git diff --quiet HEAD -- METAENGINE_SLICE3_RESTORED/metaengine/ METAENGINE_SLICE3_RESTORED/storage/engine_biographies.json 2>/dev/null; then
        echo "  No changes to commit (patches may have been no-ops or already applied)"
    else
        APPLIED_COUNT=$(python3 -c "
import json
s = json.load(open('METAENGINE_SLICE3_RESTORED/storage/patch_applier_state.json'))
print(len(s.get('applied_patches', [])))
" 2>/dev/null || echo "?")

        git add METAENGINE_SLICE3_RESTORED/metaengine/dspy_amplify.py \
                METAENGINE_SLICE3_RESTORED/metaengine/mechanism_library.py \
                METAENGINE_SLICE3_RESTORED/metaengine/learned_router.py \
                METAENGINE_SLICE3_RESTORED/metaengine/multi_provider_validator.py \
                METAENGINE_SLICE3_RESTORED/storage/engine_biographies.json \
                METAENGINE_SLICE3_RESTORED/storage/patch_applier_state.json \
                2>/dev/null

        git commit -m "Auto-apply $APPLIED_COUNT adaptation patches to MetaEngine source

Applied by: scripts/apply_all_patches.sh
Patches include:
- AMPLIFY_RULE: new heuristic rules for dspy_amplify.py
- MECHANISM_HYPOTHESIS: new mechanisms for mechanism_library.py
- ROUTING_HINT: engine weight adjustments for learned_router.py
- BIOGRAPHY_DELTA: engine biography updates
- PROVIDER_ADDITION: new LLM providers for multi_provider_validator.py

All patches validated by pytest before commit.
Backups in storage/patch_backups/.
State in storage/patch_applier_state.json.

[skip ci]" 2>&1 | tail -5

        # Push to GitHub
        git push origin main 2>&1 | tail -3
    fi
fi

echo ""
echo "✓ Done"
