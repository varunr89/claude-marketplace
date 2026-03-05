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

# Save consultation log
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="$CONSULT_DIR/${TIMESTAMP}-${CONSULT_TYPE}.md"
cat > "$LOG_FILE" <<LOG_EOF
---
type: $CONSULT_TYPE
model: $MODEL
timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)
---

# Consultation: $CONSULT_TYPE

## Prompt
$(cat "$PROMPT_FILE" 2>/dev/null || echo "[prompt file already cleaned up]")

## Response
$RESPONSE
LOG_EOF

# Output the response
echo "$RESPONSE"
