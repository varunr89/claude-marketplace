#!/bin/bash
# Copilot Collab SessionEnd Hook
# Cleans up per-session state files.

set -euo pipefail

HOOK_INPUT=$(cat)

if ! command -v jq &>/dev/null; then
  exit 0
fi

SESSION_ID=$(echo "$HOOK_INPUT" | jq -r '.session_id // empty')
CWD=$(echo "$HOOK_INPUT" | jq -r '.cwd // empty')

if [[ -z "${SESSION_ID:-}" ]] || [[ -z "${CWD:-}" ]]; then
  exit 0
fi

# Validate session ID format
if ! [[ "$SESSION_ID" =~ ^[A-Za-z0-9._-]+$ ]]; then
  exit 0
fi

REPO_ROOT=$(cd "$CWD" && git rev-parse --show-toplevel 2>/dev/null || echo "$CWD")

rm -f "$REPO_ROOT/.claude/copilot-collab/sessions/${SESSION_ID}.md"
rm -f "$REPO_ROOT/.claude/copilot-collab/sessions/${SESSION_ID}.skip"
