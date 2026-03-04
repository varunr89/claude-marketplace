# Copilot Collab Plugin Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a unified Claude Code plugin that uses GitHub Copilot CLI for automated code reviews (replaces codex-collab) and interactive consultations (replaces phone-a-friend).

**Architecture:** Shell scripts invoke `copilot --model $MODEL --silent --no-color -p "$(cat $PROMPT_FILE)"` for all AI interactions. A Stop hook drives the designing/implementing state machine. A `/consult` command enables interactive consultations. Model resolution parses `copilot help config` output with caching.

**Tech Stack:** Bash scripts, jq for JSON, `copilot` CLI (v0.0.421+), Claude Code plugin API (hooks.json, commands, skills)

**Design doc:** `docs/plans/2026-03-03-copilot-collab-design.md`

---

### Task 1: Create Plugin Manifest and Directory Structure

**Files:**
- Create: `plugins/copilot-collab/.claude-plugin/plugin.json`

**Step 1: Create directories**

```bash
mkdir -p plugins/copilot-collab/.claude-plugin
mkdir -p plugins/copilot-collab/hooks
mkdir -p plugins/copilot-collab/scripts
mkdir -p plugins/copilot-collab/commands
mkdir -p plugins/copilot-collab/skills/copilot-collab
```

**Step 2: Write plugin.json**

```json
{
  "name": "copilot-collab",
  "description": "Automated GitHub Copilot CLI reviews and interactive consultations via Stop hooks",
  "version": "1.0.0",
  "author": { "name": "Varun R" },
  "repository": "https://github.com/varunr89/claude-marketplace",
  "license": "MIT",
  "keywords": ["copilot", "code-review", "consultation", "multi-model"]
}
```

**Step 3: Commit**

```bash
git add plugins/copilot-collab/.claude-plugin/plugin.json
git commit -m "feat(copilot-collab): scaffold plugin directory and manifest"
```

---

### Task 2: Write Model Resolution Script

**Files:**
- Create: `plugins/copilot-collab/scripts/resolve-model.sh`

**Step 1: Write resolve-model.sh**

This script resolves the best available model for a given vendor. It:
1. Checks `model_override` in session state frontmatter
2. Parses `copilot help config` for available model IDs
3. Filters by vendor (openai or google) and picks the latest
4. Caches the parsed model list for 7 days
5. Falls back to hardcoded defaults

```bash
#!/bin/bash
# Resolves the best Copilot CLI model for a given vendor.
# Args: --vendor openai|google (default: openai)
# Output: model ID string (e.g., "gpt-5.3-codex")
# Priority: session override > cached discovery > fallback

set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
CACHE_DIR="${HOME}/.cache/copilot-collab"
CACHE_FILE="${CACHE_DIR}/models.json"
CACHE_MAX_AGE=604800  # 7 days in seconds

FALLBACK_OPENAI="gpt-5.3-codex"
FALLBACK_GOOGLE="gemini-3-pro-preview"

# Parse args
VENDOR="openai"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --vendor) VENDOR="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# ── Check session override ────────────────────────────────────────
SESSION_ID="${COPILOT_COLLAB_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
if [[ -n "${SESSION_ID:-}" ]]; then
  STATE_FILE="$REPO_ROOT/.claude/copilot-collab/sessions/${SESSION_ID}.md"
  if [[ -f "$STATE_FILE" ]]; then
    OVERRIDE=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE" | grep '^model_override:' | sed 's/model_override: *//' | sed 's/^"\(.*\)"$/\1/' || true)
    if [[ -n "${OVERRIDE:-}" ]] && [[ "$OVERRIDE" != "null" ]] && [[ "$OVERRIDE" != "" ]]; then
      echo "$OVERRIDE"
      exit 0
    fi
  fi
fi

# ── Check cache freshness ─────────────────────────────────────────
USE_CACHE=false
if [[ -f "$CACHE_FILE" ]]; then
  if [[ "$(uname)" = "Darwin" ]]; then
    FILE_AGE=$(( $(date +%s) - $(stat -f%m "$CACHE_FILE") ))
  else
    FILE_AGE=$(( $(date +%s) - $(stat -c%Y "$CACHE_FILE") ))
  fi
  if [[ $FILE_AGE -lt $CACHE_MAX_AGE ]]; then
    USE_CACHE=true
  fi
fi

# ── Discover models from copilot help config ──────────────────────
if [[ "$USE_CACHE" = "false" ]]; then
  mkdir -p "$CACHE_DIR"
  if command -v copilot &>/dev/null; then
    # Extract model IDs from help output
    OPENAI_MODELS=$(copilot help config 2>&1 | grep -oE '"gpt-[^"]*-codex"' | tr -d '"' | sort -t. -k2 -rn | head -5 || echo "")
    GOOGLE_MODELS=$(copilot help config 2>&1 | grep -oE '"gemini-[^"]*"' | tr -d '"' | sort -rn | head -5 || echo "")

    # Write cache
    cat > "$CACHE_FILE" <<CACHE_EOF
{
  "openai": "$(echo "$OPENAI_MODELS" | head -1)",
  "google": "$(echo "$GOOGLE_MODELS" | head -1)",
  "openai_all": "$(echo "$OPENAI_MODELS" | paste -sd ',' -)",
  "google_all": "$(echo "$GOOGLE_MODELS" | paste -sd ',' -)",
  "cached_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
CACHE_EOF
  fi
fi

# ── Read from cache ───────────────────────────────────────────────
if [[ -f "$CACHE_FILE" ]] && command -v jq &>/dev/null; then
  MODEL=$(jq -r ".${VENDOR} // empty" "$CACHE_FILE")
  if [[ -n "${MODEL:-}" ]]; then
    echo "$MODEL"
    exit 0
  fi
fi

# ── Fallback ──────────────────────────────────────────────────────
case "$VENDOR" in
  openai) echo "$FALLBACK_OPENAI" ;;
  google) echo "$FALLBACK_GOOGLE" ;;
  *) echo "$FALLBACK_OPENAI" ;;
esac
```

**Step 2: Make executable and commit**

```bash
chmod +x plugins/copilot-collab/scripts/resolve-model.sh
git add plugins/copilot-collab/scripts/resolve-model.sh
git commit -m "feat(copilot-collab): add model resolution with discovery and caching"
```

---

### Task 3: Write Update Check Script

**Files:**
- Create: `plugins/copilot-collab/scripts/update-check.sh`

**Step 1: Write update-check.sh**

Runs `copilot update` at most once per week. Called from SessionStart hook.

```bash
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
```

**Step 2: Make executable and commit**

```bash
chmod +x plugins/copilot-collab/scripts/update-check.sh
git add plugins/copilot-collab/scripts/update-check.sh
git commit -m "feat(copilot-collab): add weekly CLI update check script"
```

---

### Task 4: Write Session Start and End Hooks

**Files:**
- Create: `plugins/copilot-collab/scripts/session-start-hook.sh`
- Create: `plugins/copilot-collab/scripts/session-end-hook.sh`

**Step 1: Write session-start-hook.sh**

Same as codex-collab's but also calls update-check.sh.

```bash
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
  echo "export CLAUDE_SESSION_ID=\"$SESSION_ID\"" >> "$CLAUDE_ENV_FILE"
fi

# Run update check (non-blocking, ignore failures)
"$SCRIPT_DIR/update-check.sh" 2>/dev/null || true
```

**Step 2: Write session-end-hook.sh**

```bash
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

REPO_ROOT=$(cd "$CWD" && git rev-parse --show-toplevel 2>/dev/null || echo "$CWD")

rm -f "$REPO_ROOT/.claude/copilot-collab/sessions/${SESSION_ID}.md"
rm -f "$REPO_ROOT/.claude/copilot-collab/sessions/${SESSION_ID}.skip"
```

**Step 3: Make executable and commit**

```bash
chmod +x plugins/copilot-collab/scripts/session-start-hook.sh
chmod +x plugins/copilot-collab/scripts/session-end-hook.sh
git add plugins/copilot-collab/scripts/session-start-hook.sh plugins/copilot-collab/scripts/session-end-hook.sh
git commit -m "feat(copilot-collab): add session start/end hooks"
```

---

### Task 5: Write Design Review Script

**Files:**
- Create: `plugins/copilot-collab/scripts/design-review.sh`

**Step 1: Write design-review.sh**

Mirrors codex-collab's `design-review.sh` but uses `copilot` CLI. Key change: uses `copilot --model $MODEL --silent --no-color -p "$(cat $PROMPT_FILE)"` instead of `cat $PROMPT_FILE | codex exec ...`.

```bash
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
```

**Step 2: Make executable and commit**

```bash
chmod +x plugins/copilot-collab/scripts/design-review.sh
git add plugins/copilot-collab/scripts/design-review.sh
git commit -m "feat(copilot-collab): add design review script using Copilot CLI"
```

---

### Task 6: Write Task Review Script

**Files:**
- Create: `plugins/copilot-collab/scripts/task-review.sh`

**Step 1: Write task-review.sh**

Mirrors codex-collab's `task-review.sh`. Key change: uses model tiers instead of reasoning effort tiers (security-sensitive files -> stronger model from same vendor, or alternate vendor).

```bash
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

cat > "$PROMPT_FILE" <<PROMPT_EOF
Review these code changes for an implementation task.

TASK: $TASK_DESC

CHANGED FILES:
$CHANGED_FILES

LINES CHANGED: $LINES_CHANGED

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
$DIFF
PROMPT_EOF

# Send to Copilot CLI
PROMPT_SIZE=$(wc -c < "$PROMPT_FILE" | tr -d ' ')
if [[ "$PROMPT_SIZE" -gt 100000 ]]; then
  REVIEW_OUTPUT=$(cat "$PROMPT_FILE" | copilot \
    --model "$MODEL" \
    --silent \
    --no-color \
    -p "" 2>/dev/null || echo "Copilot review unavailable. Proceeding without task review.")
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
```

**Step 2: Make executable and commit**

```bash
chmod +x plugins/copilot-collab/scripts/task-review.sh
git add plugins/copilot-collab/scripts/task-review.sh
git commit -m "feat(copilot-collab): add task review script using Copilot CLI"
```

---

### Task 7: Write Consultation Script (Phone a Friend Replacement)

**Files:**
- Create: `plugins/copilot-collab/scripts/consult.sh`

**Step 1: Write consult.sh**

Interactive consultation script. Takes a prompt file and model, returns response. Supports accumulated multi-turn context.

```bash
#!/bin/bash
# Runs an interactive consultation via Copilot CLI.
# Args: --model <model-id> --type <consultation-type> --prompt-file <path>
# Output: consultation response to stdout
# Side effect: Saves consultation log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# Parse args
MODEL=""
CONSULT_TYPE="code-review"
PROMPT_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --type) CONSULT_TYPE="$2"; shift 2 ;;
    --prompt-file) PROMPT_FILE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

if [[ -z "$PROMPT_FILE" ]] || [[ ! -f "$PROMPT_FILE" ]]; then
  echo "ERROR: --prompt-file is required and must exist" >&2
  exit 1
fi

# Resolve model if not provided
if [[ -z "$MODEL" ]]; then
  MODEL=$("$SCRIPT_DIR/resolve-model.sh" --vendor openai)
fi

# Create consultations directory
CONSULT_DIR="$REPO_ROOT/.claude/copilot-collab/consultations"
mkdir -p "$CONSULT_DIR"

# Send to Copilot CLI
PROMPT_SIZE=$(wc -c < "$PROMPT_FILE" | tr -d ' ')
if [[ "$PROMPT_SIZE" -gt 100000 ]]; then
  RESPONSE=$(cat "$PROMPT_FILE" | copilot \
    --model "$MODEL" \
    --silent \
    --no-color \
    -p "" 2>/dev/null || echo "Consultation failed. Copilot CLI returned no response.")
else
  RESPONSE=$(copilot \
    --model "$MODEL" \
    --silent \
    --no-color \
    -p "$(cat "$PROMPT_FILE")" 2>/dev/null || echo "Consultation failed. Copilot CLI returned no response.")
fi

# Output the response
echo "$RESPONSE"
```

**Step 2: Make executable and commit**

```bash
chmod +x plugins/copilot-collab/scripts/consult.sh
git add plugins/copilot-collab/scripts/consult.sh
git commit -m "feat(copilot-collab): add consultation script (phone-a-friend replacement)"
```

---

### Task 8: Write Stop Hook (State Machine)

**Files:**
- Create: `plugins/copilot-collab/hooks/stop-hook.sh`

**Step 1: Write stop-hook.sh**

Same state machine as codex-collab but references `copilot-collab` paths and exports `COPILOT_COLLAB_SESSION_ID`. Identical logic, different directory names.

```bash
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
```

**Step 2: Make executable and commit**

```bash
chmod +x plugins/copilot-collab/hooks/stop-hook.sh
git add plugins/copilot-collab/hooks/stop-hook.sh
git commit -m "feat(copilot-collab): add stop hook state machine"
```

---

### Task 9: Write Hooks Registration

**Files:**
- Create: `plugins/copilot-collab/hooks/hooks.json`

**Step 1: Write hooks.json**

```json
{
  "description": "Copilot collab hooks for session isolation and automated reviews",
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/session-start-hook.sh"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/session-end-hook.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/stop-hook.sh",
            "timeout": 900
          }
        ]
      }
    ]
  }
}
```

**Step 2: Commit**

```bash
git add plugins/copilot-collab/hooks/hooks.json
git commit -m "feat(copilot-collab): register session and stop hooks"
```

---

### Task 10: Write Session Setup Script

**Files:**
- Create: `plugins/copilot-collab/scripts/setup-session.sh`

**Step 1: Write setup-session.sh**

Initializes a copilot-collab session. Same as codex-collab's but checks for `copilot` instead of `codex`, uses copilot-collab paths, and adds the `vendor` field.

```bash
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
```

**Step 2: Make executable and commit**

```bash
chmod +x plugins/copilot-collab/scripts/setup-session.sh
git add plugins/copilot-collab/scripts/setup-session.sh
git commit -m "feat(copilot-collab): add session setup script"
```

---

### Task 11: Write All Commands

**Files:**
- Create: `plugins/copilot-collab/commands/copilot-collab.md`
- Create: `plugins/copilot-collab/commands/copilot-status.md`
- Create: `plugins/copilot-collab/commands/copilot-pause.md`
- Create: `plugins/copilot-collab/commands/copilot-resume.md`
- Create: `plugins/copilot-collab/commands/copilot-skip.md`
- Create: `plugins/copilot-collab/commands/copilot-cancel.md`
- Create: `plugins/copilot-collab/commands/consult.md`

**Step 1: Write all 7 command files**

Follow the exact same frontmatter pattern as the codex-collab commands but with copilot-collab paths. The `/consult` command is new.

**copilot-collab.md:**
```markdown
---
description: "Start a Copilot-collaborative development session with automated reviews"
argument-hint: "[task description]"
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/scripts/setup-session.sh:*)"]
---

# Copilot Collab

Execute the setup script to initialize the session:

\`\`\`!
if [ -z "${CLAUDE_SESSION_ID:-}" ]; then echo "ERROR: No session ID. The SessionStart hook may not be registered."; exit 1; fi
${CLAUDE_PLUGIN_ROOT}/scripts/setup-session.sh $ARGUMENTS
\`\`\`

You are now in a Copilot Collab session. The Stop hook will automatically trigger Copilot reviews at key points.

**Your current phase is DESIGNING.** Work on the design/plan for this task using your normal brainstorming and planning workflow. When you finish the design and try to stop, the hook will automatically send it to Copilot for review before you begin implementation.

IMPORTANT: When you write the design plan to a file, update the state file's plan_file field so the hook knows where to find it:

\`\`\`bash
sed -i '' "s|^plan_file: .*|plan_file: \"docs/plans/YOUR-PLAN-FILE.md\"|" .claude/copilot-collab/sessions/${CLAUDE_SESSION_ID}.md
\`\`\`
```

**copilot-status.md:**
```markdown
---
description: "Check current Copilot Collab session status"
---

# Copilot Status

Read and display the current session state:

\`\`\`!
if [ -z "${CLAUDE_SESSION_ID:-}" ]; then echo "ERROR: No session ID."; exit 1; fi
STATE_FILE=".claude/copilot-collab/sessions/${CLAUDE_SESSION_ID}.md"
if [ -f "$STATE_FILE" ]; then
  echo "=== Copilot Collab Status ==="
  echo "Session: ${CLAUDE_SESSION_ID}"
  head -20 "$STATE_FILE"
  echo ""
  echo "=== Reviews ==="
  ls -la .claude/copilot-collab/reviews/ 2>/dev/null || echo "No reviews yet."
  echo ""
  echo "=== Consultations ==="
  ls -la .claude/copilot-collab/consultations/ 2>/dev/null || echo "No consultations yet."
else
  echo "No active Copilot Collab session for this session."
fi
\`\`\`
```

**copilot-pause.md:**
```markdown
---
description: "Pause Copilot Collab auto-reviews"
allowed-tools: ["Bash(sed:*)"]
---

# Copilot Pause

\`\`\`!
if [ -z "${CLAUDE_SESSION_ID:-}" ]; then echo "ERROR: No session ID."; exit 1; fi
STATE_FILE=".claude/copilot-collab/sessions/${CLAUDE_SESSION_ID}.md"
if [ -f "$STATE_FILE" ]; then
  sed -i '' 's/^paused: false/paused: true/' "$STATE_FILE"
  echo "Copilot Collab paused. Reviews will not trigger until you run /copilot-resume."
else
  echo "No active Copilot Collab session."
fi
\`\`\`
```

**copilot-resume.md:**
```markdown
---
description: "Resume Copilot Collab auto-reviews"
allowed-tools: ["Bash(sed:*)"]
---

# Copilot Resume

\`\`\`!
if [ -z "${CLAUDE_SESSION_ID:-}" ]; then echo "ERROR: No session ID."; exit 1; fi
STATE_FILE=".claude/copilot-collab/sessions/${CLAUDE_SESSION_ID}.md"
if [ -f "$STATE_FILE" ]; then
  sed -i '' 's/^paused: true/paused: false/' "$STATE_FILE"
  echo "Copilot Collab resumed. Auto-reviews are active again."
else
  echo "No active Copilot Collab session."
fi
\`\`\`
```

**copilot-skip.md:**
```markdown
---
description: "Skip the next Copilot review only"
---

# Copilot Skip

\`\`\`!
if [ -z "${CLAUDE_SESSION_ID:-}" ]; then echo "ERROR: No session ID."; exit 1; fi
mkdir -p .claude/copilot-collab/sessions
touch ".claude/copilot-collab/sessions/${CLAUDE_SESSION_ID}.skip"
echo "Next review will be skipped. The flag auto-clears after one use."
\`\`\`
```

**copilot-cancel.md:**
```markdown
---
description: "Cancel the current Copilot Collab session"
---

# Copilot Cancel

\`\`\`!
if [ -z "${CLAUDE_SESSION_ID:-}" ]; then echo "ERROR: No session ID."; exit 1; fi
rm -f ".claude/copilot-collab/sessions/${CLAUDE_SESSION_ID}.md"
rm -f ".claude/copilot-collab/sessions/${CLAUDE_SESSION_ID}.skip"
echo "Copilot Collab session cancelled. Auto-reviews disabled."
\`\`\`
```

**consult.md** (new -- Phone a Friend replacement):
```markdown
---
description: "Consult other AI models for second opinions, code reviews, and collaborative problem-solving"
argument-hint: "[topic or question]"
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/scripts/consult.sh:*)", "Bash(${CLAUDE_PLUGIN_ROOT}/scripts/resolve-model.sh:*)"]
---

# Consult

This command triggers an interactive consultation with another AI model via Copilot CLI.

Before running the consultation:
1. Determine the consultation type: code-review, second-opinion, or bug-analysis
2. Gather relevant context (files, diffs, error logs)
3. Ask the user for permission using AskUserQuestion, showing what will be shared and offering model choice (GPT-5.3-Codex or Gemini)
4. Build the prompt and run the consultation

To resolve available models:
\`\`\`!
echo "OpenAI: $(${CLAUDE_PLUGIN_ROOT}/scripts/resolve-model.sh --vendor openai)"
echo "Google: $(${CLAUDE_PLUGIN_ROOT}/scripts/resolve-model.sh --vendor google)"
\`\`\`

After getting the user's model choice, write the prompt to a temp file and run:
\`\`\`bash
PROMPT_FILE=$(mktemp)
cat > "$PROMPT_FILE" <<'PROMPT_EOF'
[Your constructed prompt here]
PROMPT_EOF
${CLAUDE_PLUGIN_ROOT}/scripts/consult.sh --model MODEL_ID --type CONSULTATION_TYPE --prompt-file "$PROMPT_FILE"
rm -f "$PROMPT_FILE"
\`\`\`

After receiving the response:
- Present an objective comparison between your perspective and the consulted model's perspective
- Use AskUserQuestion to let the user choose an approach
- Log the consultation to `.claude/copilot-collab/consultations/`
```

**Step 2: Commit all commands**

```bash
git add plugins/copilot-collab/commands/
git commit -m "feat(copilot-collab): add all slash commands including /consult"
```

---

### Task 12: Write Skill File

**Files:**
- Create: `plugins/copilot-collab/skills/copilot-collab/SKILL.md`

**Step 1: Write SKILL.md**

This is the behavioral guide for Claude during copilot-collab sessions. It combines the codex-collab skill (phases, auto-fix behavior) with the phone-a-friend skill (consultation triggers, permission flow, presentation). Keep it concise -- the essential behavioral instructions only.

The skill should cover:
- When to auto-suggest consultations (complexity thresholds via git commands)
- How to behave during designing/implementing phases (same as codex-collab skill)
- How to present consultation results objectively
- How to handle review feedback (auto-fix CRITICAL/WARNING, flag design conflicts)
- Secret scrubbing before sharing context
- Escape hatches
- Consultation logging format

Reference the design doc at `docs/plans/2026-03-03-copilot-collab-design.md` for the full spec. The skill should be self-contained (not require reading the design doc) but concise.

**Step 2: Commit**

```bash
git add plugins/copilot-collab/skills/copilot-collab/SKILL.md
git commit -m "feat(copilot-collab): add skill with behavioral guide"
```

---

### Task 13: Smoke Test the Plugin

**Step 1: Verify all scripts are executable**

```bash
ls -la plugins/copilot-collab/scripts/*.sh
ls -la plugins/copilot-collab/hooks/*.sh
```

**Step 2: Test resolve-model.sh in isolation**

```bash
plugins/copilot-collab/scripts/resolve-model.sh --vendor openai
plugins/copilot-collab/scripts/resolve-model.sh --vendor google
```

Expected: prints model IDs like `gpt-5.3-codex` and `gemini-3-pro-preview`

**Step 3: Test consult.sh with a simple prompt**

```bash
PROMPT_FILE=$(mktemp)
echo "What is 2+2? Answer in one word." > "$PROMPT_FILE"
plugins/copilot-collab/scripts/consult.sh --model gpt-5.3-codex --prompt-file "$PROMPT_FILE"
rm -f "$PROMPT_FILE"
```

Expected: a response from Copilot CLI

**Step 4: Verify hooks.json is valid JSON**

```bash
jq . plugins/copilot-collab/hooks/hooks.json
```

**Step 5: Verify plugin.json is valid JSON**

```bash
jq . plugins/copilot-collab/.claude-plugin/plugin.json
```

---

### Task 14: Final Commit and Summary

**Step 1: Review all files**

```bash
find plugins/copilot-collab -type f | sort
```

**Step 2: Ensure .claude/copilot-collab/ is gitignored (runtime state)**

Check if `.gitignore` includes `.claude/` patterns. Add if missing:
```
.claude/copilot-collab/sessions/
.claude/copilot-collab/reviews/
.claude/copilot-collab/consultations/
```

**Step 3: Final commit if any remaining changes**

```bash
git add -A plugins/copilot-collab/
git commit -m "feat(copilot-collab): complete plugin implementation"
```
