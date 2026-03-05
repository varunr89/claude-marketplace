---
description: "Pause Copilot Collab auto-reviews"
allowed-tools: ["Bash(sed:*)"]
---

# Copilot Pause

```!
if [ -z "${CLAUDE_SESSION_ID:-}" ]; then echo "ERROR: No session ID."; exit 1; fi
STATE_FILE=".claude/copilot-collab/sessions/${CLAUDE_SESSION_ID}.md"
if [ -f "$STATE_FILE" ]; then
  sed -i '' 's/^paused: false/paused: true/' "$STATE_FILE"
  echo "Copilot Collab paused. Reviews will not trigger until you run /copilot-resume."
else
  echo "No active Copilot Collab session."
fi
```
