#!/bin/bash
# Initializes a copilot-collab session.
# Creates the per-session state file and prints activation message.
# Args: $@ = task description (all remaining args joined)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# ── Session ID resolution ───────────────────────────────────────────
SESSION_ID="${COPILOT_COLLAB_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
if [[ -z "$SESSION_ID" ]]; then
  echo "ERROR: No session ID available. CLAUDE_SESSION_ID must be set by the SessionStart hook." >&2
  exit 1
fi

# Session-scoped paths
SESSIONS_DIR="$REPO_ROOT/.claude/copilot-collab/sessions"
STATE_FILE="$SESSIONS_DIR/${SESSION_ID}.md"

# Check if already active
if [[ -f "$STATE_FILE" ]]; then
  PHASE=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE" | grep '^phase:' | sed 's/phase: *//')
  if [[ "$PHASE" != "idle" ]] && [[ "$PHASE" != "complete" ]]; then
    echo "A copilot-collab session is already active (phase: $PHASE)."
    echo "Use /copilot-cancel to end it first, or /copilot-status to check progress."
    exit 1
  fi
fi

# Check copilot CLI is available
if ! command -v copilot &>/dev/null; then
  echo "ERROR: copilot CLI not found. Install with: brew install copilot-cli" >&2
  exit 1
fi

# Check jq is available
if ! command -v jq &>/dev/null; then
  echo "ERROR: jq not found. Install with: brew install jq" >&2
  exit 1
fi

# Resolve and cache model
MODEL=$("$SCRIPT_DIR/resolve-model.sh" --vendor openai 2>/dev/null || echo "gpt-5.3-codex")

# Get current git SHA as initial checkpoint
GIT_SHA=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

# Parse task description
TASK_DESC="${*:-}"

# Create state directories
mkdir -p "$SESSIONS_DIR"
mkdir -p "$REPO_ROOT/.claude/copilot-collab/reviews"
mkdir -p "$REPO_ROOT/.claude/copilot-collab/consultations"

# ── Create session state ────────────────────────────────────────────
cat > "$STATE_FILE" <<EOF
---
phase: designing
task_index: 0
git_checkpoint: $GIT_SHA
plan_file: ""
paused: false
model_override: ""
vendor: "openai"
started_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
---

$TASK_DESC
EOF

# Output activation message
cat <<EOF
Copilot Collab session activated!

Session: ${SESSION_ID:0:12}...
Model: $MODEL
Vendor: openai (GPT Codex)
Git checkpoint: ${GIT_SHA:0:8}

WORKFLOW:
1. Design phase (current) -- work on your design/plan as normal
2. When you finish designing, Copilot will automatically review the plan
3. Implementation phase -- work through tasks one at a time
4. After each task, Copilot will automatically review your code changes

CONTROLS:
  /copilot-status  -- check session state
  /copilot-pause   -- pause auto-reviews
  /copilot-resume  -- resume auto-reviews
  /copilot-skip    -- skip the next review only
  /copilot-cancel  -- end session
  /consult         -- interactive consultation (second opinion)
EOF

if [[ -n "$TASK_DESC" ]]; then
  echo ""
  echo "TASK: $TASK_DESC"
fi
