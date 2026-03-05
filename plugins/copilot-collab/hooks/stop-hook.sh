#!/bin/bash
# Copilot Collab Stop Hook
# Manages the review lifecycle state machine.
# Uses the advanced Stop hook API: outputs JSON with decision/reason/systemMessage.
# Exit 0 always -- decision: "block" prevents stop, no output allows stop.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# Read hook input from stdin
HOOK_INPUT=$(cat)

# ── Preflight checks ────────────────────────────────────────────────
if ! command -v jq &>/dev/null; then
  echo "copilot-collab: jq not found, skipping review" >&2
  exit 0
fi

# ── Session ID resolution ───────────────────────────────────────────
SESSION_ID=$(echo "$HOOK_INPUT" | jq -r '.session_id // empty')
if [[ -z "${SESSION_ID:-}" ]]; then
  exit 0
fi

export COPILOT_COLLAB_SESSION_ID="$SESSION_ID"

# Session-scoped paths
SESSIONS_DIR="$REPO_ROOT/.claude/copilot-collab/sessions"
STATE_FILE="$SESSIONS_DIR/${SESSION_ID}.md"
SKIP_FLAG="$SESSIONS_DIR/${SESSION_ID}.skip"

# ── Escape hatches ──────────────────────────────────────────────────
if [[ -f "$SKIP_FLAG" ]]; then
  rm -f "$SKIP_FLAG"
  exit 0
fi

if [[ ! -f "$STATE_FILE" ]]; then
  exit 0
fi

# Parse frontmatter
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")

PAUSED=$(echo "$FRONTMATTER" | grep '^paused:' | sed 's/paused: *//' || echo "false")
if [[ "$PAUSED" = "true" ]]; then
  exit 0
fi

PHASE=$(echo "$FRONTMATTER" | grep '^phase:' | sed 's/phase: *//' || true)
TASK_INDEX=$(echo "$FRONTMATTER" | grep '^task_index:' | sed 's/task_index: *//' || echo "0")
GIT_CHECKPOINT=$(echo "$FRONTMATTER" | grep '^git_checkpoint:' | sed 's/git_checkpoint: *//' || echo "")
PLAN_FILE=$(echo "$FRONTMATTER" | grep '^plan_file:' | sed 's/plan_file: *//' | sed 's/^"\(.*\)"$/\1/' || echo "")

# ── State machine ───────────────────────────────────────────────────
case "$PHASE" in
  idle|complete|"")
    if [[ "$PHASE" = "complete" ]]; then
      rm -f "$STATE_FILE"
    fi
    exit 0
    ;;

  designing)
    # Find plan file
    if [[ -z "$PLAN_FILE" ]] || [[ ! -f "$PLAN_FILE" ]]; then
      PLAN_FILE=$(find docs/plans/ -name "*.md" -type f 2>/dev/null | sort -r | head -1 || echo "")
    fi

    if [[ -z "$PLAN_FILE" ]] || [[ ! -f "$PLAN_FILE" ]]; then
      TEMP_FILE="${STATE_FILE}.tmp.$$"
      sed "s/^phase: .*/phase: implementing/" "$STATE_FILE" > "$TEMP_FILE"
      mv "$TEMP_FILE" "$STATE_FILE"

      jq -n '{
        "decision": "block",
        "reason": "No design plan file found for Copilot review. Proceeding to implementation. Start working through the implementation tasks.",
        "systemMessage": "Copilot Collab: Design review skipped (no plan file). Phase: implementing."
      }'
      exit 0
    fi

    REVIEW=$("$PLUGIN_ROOT/scripts/design-review.sh" "$PLAN_FILE" 2>/dev/null || true)
    if [[ -z "$REVIEW" ]]; then
      REVIEW="Design review failed. Proceeding without review."
    fi

    CURRENT_SHA=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    TEMP_FILE="${STATE_FILE}.tmp.$$"
    sed "s/^phase: .*/phase: implementing/" "$STATE_FILE" | \
      sed "s/^git_checkpoint: .*/git_checkpoint: $CURRENT_SHA/" > "$TEMP_FILE"
    mv "$TEMP_FILE" "$STATE_FILE"

    jq -n \
      --arg review "$REVIEW" \
      --arg sysmsg "Copilot Collab: Design review complete. Phase: implementing. Address any CRITICAL issues from the review, then begin implementation tasks." \
      '{
        "decision": "block",
        "reason": ("## Copilot Design Review\n\nCopilot has reviewed your design plan. Here is the feedback:\n\n" + $review + "\n\nPlease address any CRITICAL issues, then begin implementing the tasks. After completing each task, I will automatically trigger a Copilot code review."),
        "systemMessage": $sysmsg
      }'
    exit 0
    ;;

  implementing)
    if [[ -z "$GIT_CHECKPOINT" ]]; then
      GIT_CHECKPOINT=$(git rev-parse HEAD~1 2>/dev/null || echo "")
    fi

    DIFF_SIZE=$(git diff "$GIT_CHECKPOINT"..HEAD --stat 2>/dev/null | wc -l | tr -d ' ' || echo "0")
    if [[ "$DIFF_SIZE" -le 1 ]]; then
      exit 0
    fi

    TASK_DESC=$(git log --oneline "$GIT_CHECKPOINT"..HEAD 2>/dev/null | head -5 | paste -sd '; ' - || echo "Implementation task")

    REVIEW=$("$PLUGIN_ROOT/scripts/task-review.sh" "$GIT_CHECKPOINT" "$TASK_DESC" 2>/dev/null || true)
    if [[ -z "$REVIEW" ]]; then
      REVIEW="Task review unavailable. Proceeding."
    fi

    CURRENT_SHA=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    NEXT_INDEX=$((TASK_INDEX + 1))
    TEMP_FILE="${STATE_FILE}.tmp.$$"
    sed "s/^task_index: .*/task_index: $NEXT_INDEX/" "$STATE_FILE" | \
      sed "s/^git_checkpoint: .*/git_checkpoint: $CURRENT_SHA/" > "$TEMP_FILE"
    mv "$TEMP_FILE" "$STATE_FILE"

    CRITICAL_COUNT=$(echo "$REVIEW" | grep -ci "CRITICAL" || echo "0")
    WARNING_COUNT=$(echo "$REVIEW" | grep -ci "WARNING" || echo "0")

    if [[ "$CRITICAL_COUNT" -eq 0 ]] && [[ "$WARNING_COUNT" -eq 0 ]]; then
      jq -n \
        --arg review "$REVIEW" \
        --argjson task_idx "$NEXT_INDEX" \
        --arg sysmsg "Copilot Collab: Task review complete (clean). Task $NEXT_INDEX. Continue to next task." \
        '{
          "decision": "block",
          "reason": ("## Copilot Task Review (Task " + ($task_idx | tostring) + ")\n\nCopilot reviewed your changes. No critical or warning issues found.\n\n" + $review + "\n\nGood work. Continue to the next task."),
          "systemMessage": $sysmsg
        }'
    else
      jq -n \
        --arg review "$REVIEW" \
        --argjson task_idx "$NEXT_INDEX" \
        --argjson critical "$CRITICAL_COUNT" \
        --argjson warning "$WARNING_COUNT" \
        --arg sysmsg "Copilot Collab: Task review found issues. Fix them before continuing." \
        '{
          "decision": "block",
          "reason": ("## Copilot Task Review (Task " + ($task_idx | tostring) + ")\n\nCopilot found issues in your implementation:\n- " + ($critical | tostring) + " critical\n- " + ($warning | tostring) + " warning\n\n" + $review + "\n\nPlease address the CRITICAL and WARNING issues, then continue to the next task. Show a brief summary of what you fixed."),
          "systemMessage": $sysmsg
        }'
    fi
    exit 0
    ;;

  *)
    exit 0
    ;;
esac
