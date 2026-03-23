#!/bin/bash
# Codex Collab SessionStart Hook
# Reads session_id from stdin JSON and persists CLAUDE_SESSION_ID
# via multiple mechanisms for reliability:
#   1. CLAUDE_ENV_FILE (official API -- sets env var for Bash tool)
#   2. Sentinel file (~/.claude/.codex-collab-session) as fallback
#   3. hookSpecificOutput JSON (injects session ID into conversation context)

set -euo pipefail

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

# 1. Write to CLAUDE_ENV_FILE so the session ID persists for all Bash commands
if [[ -n "${CLAUDE_ENV_FILE:-}" ]]; then
  printf 'export CLAUDE_SESSION_ID=%q\n' "$SESSION_ID" >> "$CLAUDE_ENV_FILE"
fi

# 2. Write sentinel file as fallback (commands read this if env var is missing)
SENTINEL_FILE="${HOME}/.claude/.codex-collab-session"
mkdir -p "$(dirname "$SENTINEL_FILE")"
printf '%s' "$SESSION_ID" > "$SENTINEL_FILE"

# 3. Output hookSpecificOutput so Claude sees the session ID in context
jq -n --arg sid "$SESSION_ID" '{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": ("Codex Collab: session started. CLAUDE_SESSION_ID=" + $sid)
  }
}'
