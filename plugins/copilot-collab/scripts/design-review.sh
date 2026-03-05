#!/bin/bash
# Sends a design plan to Copilot CLI for review.
# Args: $1 = path to design plan file
# Output: review text to stdout
# Side effect: Saves full review to reviews/ directory

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
PLAN_FILE="${1:?Usage: design-review.sh <plan-file-path>}"

if [[ ! -f "$PLAN_FILE" ]]; then
  echo "ERROR: Plan file not found: $PLAN_FILE" >&2
  exit 1
fi

# Resolve vendor from session state (default: openai)
SESSION_ID="${COPILOT_COLLAB_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
VENDOR="openai"
if [[ -n "${SESSION_ID:-}" ]]; then
  STATE_FILE="$REPO_ROOT/.claude/copilot-collab/sessions/${SESSION_ID}.md"
  if [[ -f "$STATE_FILE" ]]; then
    VENDOR=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE" | grep '^vendor:' | sed 's/vendor: *//' | sed 's/^"\(.*\)"$/\1/' || echo "openai")
  fi
fi

# Resolve model
MODEL=$("$SCRIPT_DIR/resolve-model.sh" --vendor "$VENDOR")

# Read plan content
PLAN_CONTENT=$(cat "$PLAN_FILE")

# Create reviews directory
REVIEW_DIR="$REPO_ROOT/.claude/copilot-collab/reviews"
mkdir -p "$REVIEW_DIR"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REVIEW_FILE="$REVIEW_DIR/design-review-$TIMESTAMP.md"

# Build prompt in a temp file
PROMPT_FILE=$(mktemp)
trap 'rm -f "$PROMPT_FILE"' EXIT

cat > "$PROMPT_FILE" <<PROMPT_EOF
Review this design plan for a software project. Be thorough and specific.

Evaluate:
1. COMPLETENESS: Missing components, edge cases, or integration points?
2. PERFORMANCE: Will this scale? Any bottlenecks?
3. SECURITY: Attack vectors, data exposure, or auth gaps?
4. MAINTAINABILITY: Will this be easy to change later? Proper separation of concerns?
5. SIMPLICITY: Is anything over-engineered? Can anything be simplified?

Format your response as:
## Issues Found
For each issue:
### [CRITICAL|WARNING|INFO]: Brief title
Description of the issue and specific recommendation.

## Strengths
What's good about this design (brief).

## Summary
N issues found (X critical, Y warning, Z info).

---

DESIGN PLAN:

$PLAN_CONTENT
PROMPT_EOF

# Send to Copilot CLI
PROMPT_SIZE=$(wc -c < "$PROMPT_FILE" | tr -d ' ')
if [[ "$PROMPT_SIZE" -gt 100000 ]]; then
  # Large prompt: pipe via stdin
  REVIEW_OUTPUT=$(cat "$PROMPT_FILE" | copilot \
    --model "$MODEL" \
    --silent \
    --no-color \
    -p "" 2>/dev/null || true)
else
  # Normal: pass via -p flag
  REVIEW_OUTPUT=$(copilot \
    --model "$MODEL" \
    --silent \
    --no-color \
    -p "$(cat "$PROMPT_FILE")" 2>/dev/null || true)
fi

# Fallback: try alternate vendor if primary failed
if [[ -z "$REVIEW_OUTPUT" ]]; then
  ALT_VENDOR="google"
  [[ "$VENDOR" = "google" ]] && ALT_VENDOR="openai"
  ALT_MODEL=$("$SCRIPT_DIR/resolve-model.sh" --vendor "$ALT_VENDOR")
  REVIEW_OUTPUT=$(copilot \
    --model "$ALT_MODEL" \
    --silent \
    --no-color \
    -p "$(cat "$PROMPT_FILE")" 2>/dev/null || echo "Copilot review failed. Proceeding without design review.")
fi

# Save full review
cat > "$REVIEW_FILE" <<EOF
---
type: design_review
model: $MODEL
vendor: $VENDOR
timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)
plan_file: $PLAN_FILE
---

# Design Review

$REVIEW_OUTPUT
EOF

# Output the review text
echo "$REVIEW_OUTPUT"
