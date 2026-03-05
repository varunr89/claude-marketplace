---
description: "Cancel the current Copilot Collab session"
---

# Copilot Cancel

```!
if [ -z "${CLAUDE_SESSION_ID:-}" ]; then echo "ERROR: No session ID."; exit 1; fi
rm -f ".claude/copilot-collab/sessions/${CLAUDE_SESSION_ID}.md"
rm -f ".claude/copilot-collab/sessions/${CLAUDE_SESSION_ID}.skip"
echo "Copilot Collab session cancelled. Auto-reviews disabled."
```
