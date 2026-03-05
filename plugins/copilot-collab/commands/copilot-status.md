---
description: "Check current Copilot Collab session status"
---

# Copilot Status

Read and display the current session state:

```!
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
```
