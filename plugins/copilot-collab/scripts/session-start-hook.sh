#!/bin/bash
# Copilot Collab SessionStart Hook
# Persists CLAUDE_SESSION_ID and checks for CLI updates.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Read hook input from stdin
HOOK_INPUT=$(cat)

# Extract session_id (requires jq)
if ! command -v jq &>/dev/null; then
  exit 0
fi

SESSION_ID=$(echo "$HOOK_INPUT" | jq -r '.session_id // empty')
if [[ -z "${SESSION_ID:-}" ]]; then
  exit 0
fi

# Write to CLAUDE_ENV_FILE so the session ID persists
if [[ -n "${CLAUDE_ENV_FILE:-}" ]]; then
  printf 'export CLAUDE_SESSION_ID=%q\n' "$SESSION_ID" >> "$CLAUDE_ENV_FILE"
fi

# Run update check (non-blocking, ignore failures)
"$SCRIPT_DIR/update-check.sh" 2>/dev/null || true
