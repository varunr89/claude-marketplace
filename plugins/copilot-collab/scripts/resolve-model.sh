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
