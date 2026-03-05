#!/bin/bash
# Checks for Copilot CLI updates at most once per week.
# Output: update status message (or nothing if check not needed)

set -euo pipefail

CACHE_DIR="${HOME}/.cache/copilot-collab"
TIMESTAMP_FILE="${CACHE_DIR}/last-update-check"
CHECK_INTERVAL=604800  # 7 days

mkdir -p "$CACHE_DIR"

# Check if we've checked recently
if [[ -f "$TIMESTAMP_FILE" ]]; then
  LAST_CHECK=$(cat "$TIMESTAMP_FILE")
  NOW=$(date +%s)
  ELAPSED=$((NOW - LAST_CHECK))
  if [[ $ELAPSED -lt $CHECK_INTERVAL ]]; then
    exit 0
  fi
fi

# Record this check
date +%s > "$TIMESTAMP_FILE"

# Run update check
if command -v copilot &>/dev/null; then
  UPDATE_OUTPUT=$(copilot update 2>&1 || true)
  if echo "$UPDATE_OUTPUT" | grep -qi "update.*available\|updating\|updated"; then
    echo "copilot-collab: Copilot CLI update available. Run 'copilot update' or 'brew upgrade copilot-cli'."
    # Invalidate model cache since new version may have new models
    rm -f "${CACHE_DIR}/models.json"
  fi
fi
