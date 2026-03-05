---
description: "Skip the next Copilot review only"
---

# Copilot Skip

```!
if [ -z "${CLAUDE_SESSION_ID:-}" ]; then echo "ERROR: No session ID."; exit 1; fi
mkdir -p .claude/copilot-collab/sessions
touch ".claude/copilot-collab/sessions/${CLAUDE_SESSION_ID}.skip"
echo "Next review will be skipped. The flag auto-clears after one use."
```
