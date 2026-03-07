#!/bin/bash
# Reviews code changes for a specific implementation task via Copilot CLI.
# Args: $1 = git checkpoint SHA, $2 = task description (optional)
# Output: review text to stdout
# Side effect: Saves full review to reviews/ directory

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
CHECKPOINT="${1:?Usage: task-review.sh <git-checkpoint-sha> [task-description]}"
TASK_DESC="${2:-Implementation task}"

# ── Session ID resolution ───────────────────────────────────────────
SESSION_ID="${COPILOT_COLLAB_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"

# Get the diff
DIFF=$(git diff "$CHECKPOINT"..HEAD 2>/dev/null || echo "")
if [[ -z "$DIFF" ]]; then
  echo "No changes since checkpoint $CHECKPOINT. Skipping review."
  exit 0
fi

# Get changed files list
CHANGED_FILES=$(git diff --name-only "$CHECKPOINT"..HEAD 2>/dev/null || echo "")
LINES_CHANGED=$(echo "$DIFF" | wc -l | tr -d ' ')

# Resolve vendor from session state (default: openai)
VENDOR="openai"
if [[ -n "${SESSION_ID:-}" ]]; then
  STATE_FILE="$REPO_ROOT/.claude/copilot-collab/sessions/${SESSION_ID}.md"
  if [[ -f "$STATE_FILE" ]]; then
    VENDOR=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE" | grep '^vendor:' | sed 's/vendor: *//' | sed 's/^"\(.*\)"$/\1/' || echo "openai")
  fi
fi

# Resolve model
MODEL=$("$SCRIPT_DIR/resolve-model.sh" --vendor "$VENDOR")

# Create reviews directory
REVIEW_DIR="$REPO_ROOT/.claude/copilot-collab/reviews"
mkdir -p "$REVIEW_DIR"

# Determine task index from session state
TASK_INDEX="0"
if [[ -n "${SESSION_ID:-}" ]]; then
  STATE_FILE="$REPO_ROOT/.claude/copilot-collab/sessions/${SESSION_ID}.md"
  if [[ -f "$STATE_FILE" ]]; then
    TASK_INDEX=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE" | grep '^task_index:' | sed 's/task_index: *//' || echo "0")
  fi
fi

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REVIEW_FILE="$REVIEW_DIR/task-${TASK_INDEX}-review-$TIMESTAMP.md"

# Build prompt in a temp file
PROMPT_FILE=$(mktemp)
trap 'rm -f "$PROMPT_FILE"' EXIT

# Write prompt to temp file
{
  cat <<'PROMPT_EOF'
Review these code changes for an implementation task.
PROMPT_EOF
  printf '\nTASK: %s\n\nCHANGED FILES:\n%s\n\nLINES CHANGED: %s\n' "$TASK_DESC" "$CHANGED_FILES" "$LINES_CHANGED"
  cat <<'PROMPT_EOF'

Evaluate:
1. CORRECTNESS: Bugs, logic errors, off-by-one errors?
2. PERFORMANCE: Unnecessary allocations, O(n^2) where O(n) is possible, blocking calls?
3. MAINTAINABILITY: Unclear naming, missing error handling, tight coupling?
4. BEST PRACTICES: Language/framework idioms, consistent patterns?
5. EDGE CASES: Null/empty inputs, concurrency issues, error paths?

Format your response as:
For each issue:
SEVERITY: FILE:LINE - description and recommendation

Then a brief summary line: N issues found (X critical, Y warning, Z info).

DIFF:
PROMPT_EOF
  printf '%s\n' "$DIFF"
} > "$PROMPT_FILE"

# Send to Copilot CLI
PROMPT_SIZE=$(wc -c < "$PROMPT_FILE" | tr -d ' ')
if [[ "$PROMPT_SIZE" -gt 100000 ]]; then
  REVIEW_OUTPUT=$(copilot \
    --model "$MODEL" \
    --silent \
    --no-color \
    -p "" 2>/dev/null < "$PROMPT_FILE" || echo "Copilot review unavailable. Proceeding without task review.")
else
  REVIEW_OUTPUT=$(copilot \
    --model "$MODEL" \
    --silent \
    --no-color \
    -p "$(cat "$PROMPT_FILE")" 2>/dev/null || echo "Copilot review unavailable. Proceeding without task review.")
fi

# Save full review
cat > "$REVIEW_FILE" <<EOF
---
type: task_review
task_index: $TASK_INDEX
task_description: "$TASK_DESC"
model: $MODEL
vendor: $VENDOR
timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)
files_reviewed: $CHANGED_FILES
lines_changed: $LINES_CHANGED
---

# Task $TASK_INDEX Review

$REVIEW_OUTPUT
EOF

# Output the review text
echo "$REVIEW_OUTPUT"
