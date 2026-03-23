---
description: "Start a Codex-collaborative development session with automated reviews"
argument-hint: "[task description]"
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/scripts/setup-codex-collab.sh:*)"]
---

# Codex Collab

Execute the setup script to initialize the session:

```!
CLAUDE_SESSION_ID="${CLAUDE_SESSION_ID:-$(cat ~/.claude/.codex-collab-session 2>/dev/null || true)}"
if [ -z "${CLAUDE_SESSION_ID:-}" ]; then echo "ERROR: No session ID. The SessionStart hook may not be registered."; exit 1; fi
export CLAUDE_SESSION_ID
${CLAUDE_PLUGIN_ROOT}/scripts/setup-codex-collab.sh $ARGUMENTS
```

You are now in a Codex Collab session. The Stop hook will automatically trigger Codex reviews at key points.

**Your current phase is DESIGNING.** Work on the design/plan for this task using your normal brainstorming and planning workflow. When you finish the design and try to stop, the hook will automatically send it to Codex for review before you begin implementation.

IMPORTANT: When you write the design plan to a file, update the state file's plan_file field so the hook knows where to find it:

```bash
sed -i "s|^plan_file: .*|plan_file: \"docs/plans/YOUR-PLAN-FILE.md\"|" .claude/codex-collab/sessions/${CLAUDE_SESSION_ID}.md
```
