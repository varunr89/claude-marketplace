---
description: "Resume Copilot Collab auto-reviews"
allowed-tools: ["Bash(sed:*)"]
---

# Copilot Resume

```!
if [ -z "${CLAUDE_SESSION_ID:-}" ]; then echo "ERROR: No session ID."; exit 1; fi
STATE_FILE=".claude/copilot-collab/sessions/${CLAUDE_SESSION_ID}.md"
if [ -f "$STATE_FILE" ]; then
  sed -i '' 's/^paused: true/paused: false/' "$STATE_FILE"
  echo "Copilot Collab resumed. Auto-reviews are active again."
else
  echo "No active Copilot Collab session."
fi
```
