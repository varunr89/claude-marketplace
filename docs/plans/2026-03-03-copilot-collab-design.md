# Copilot Collab Plugin Design

**Date:** 2026-03-03
**Status:** Approved
**Replaces:** codex-collab plugin + phone-a-friend plugin

## Overview

A unified Claude Code plugin that uses GitHub Copilot CLI (`copilot`) for automated code reviews during development and interactive consultations (second opinions). Replaces both the codex-collab plugin (automated stop-hook reviews) and the phone-a-friend plugin (interactive AI consultations).

## Target Models

- **GPT-5.3-Codex** (`gpt-5.3-codex`) -- OpenAI frontier, with `reasoning_effort: "xhigh"` via `~/.copilot/config.json`
- **Gemini 3 Pro** (`gemini-3-pro-preview`) -- Google frontier, no thinking mode configuration needed
- No Claude models -- Claude Code is used directly, not routed through Copilot CLI

## Plugin Structure

```
plugins/copilot-collab/
├── .claude-plugin/
│   └── plugin.json
├── hooks/
│   ├── hooks.json              # SessionStart, SessionEnd, Stop
│   └── stop-hook.sh            # State machine: designing -> implementing
├── scripts/
│   ├── setup-session.sh        # /copilot-collab entry point
│   ├── design-review.sh        # Sends plan to copilot -p
│   ├── task-review.sh          # Sends diff to copilot -p
│   ├── resolve-model.sh        # Parses copilot help config, caches models
│   ├── consult.sh              # Interactive consultation (Phone a Friend replacement)
│   ├── update-check.sh         # Weekly copilot CLI update check
│   ├── session-start-hook.sh   # Persists CLAUDE_SESSION_ID
│   └── session-end-hook.sh     # Cleans up session state
├── commands/
│   ├── copilot-collab.md       # Start automated review session
│   ├── copilot-status.md       # Show session state + reviews
│   ├── copilot-pause.md        # Pause automated reviews
│   ├── copilot-resume.md       # Resume automated reviews
│   ├── copilot-skip.md         # Skip next review only
│   ├── copilot-cancel.md       # End session
│   └── consult.md              # Interactive consultation
└── skills/
    └── copilot-collab/
        └── SKILL.md            # Guides Claude's behavior
```

## Model Resolution (`resolve-model.sh`)

Priority order:
1. `model_override` in session state frontmatter
2. Parse `copilot help config` output for valid model IDs
3. Filter to GPT Codex (`gpt-*-codex`) and Gemini (`gemini-*`) models
4. Pick latest version per vendor (highest version number)
5. Cache in `~/.cache/copilot-collab/models.json` with 7-day TTL
6. Fallback: `gpt-5.3-codex`

Accepts `--vendor openai|google` flag to select provider.

### CLI Update Check (`update-check.sh`)

- Runs `copilot update` at most once per week
- Tracked via timestamp file at `~/.cache/copilot-collab/last-update-check`
- Called from SessionStart hook
- Surfaces update availability message to user

## Core Copilot CLI Invocation Pattern

```bash
# Standard (prompt fits in args)
REVIEW_OUTPUT=$(copilot \
  --model "$MODEL" \
  --silent \
  --no-color \
  -p "$(cat "$PROMPT_FILE")" 2>/dev/null || true)

# Large prompts (diffs > ARG_MAX)
REVIEW_OUTPUT=$(cat "$PROMPT_FILE" | copilot \
  --silent \
  --no-color \
  -p "" 2>/dev/null || true)
```

### Prerequisite: `~/.copilot/config.json`

Must contain `"reasoning_effort": "xhigh"` for GPT Codex models to use full reasoning depth. Without this, GPT-5.3-Codex defaults to `medium` reasoning (28 thinking tokens vs 523 with xhigh). Verified empirically on v0.0.421.

## Automated Review Workflow (Stop Hook)

### State File

Per-session state at `.claude/copilot-collab/sessions/${SESSION_ID}.md`:

```yaml
---
phase: designing          # designing | implementing | complete | idle
task_index: 0
git_checkpoint: <SHA>
plan_file: ""
paused: false
model_override: ""        # optional: force a specific model
vendor: "openai"          # "openai" or "google"
started_at: "2026-..."
---
```

### Stop Hook State Machine

```
Stop event received
       |
       v
  SESSION_ID from stdin JSON
       |
       v
  .skip flag? -> yes -> rm flag, exit 0
       |
       v
  state file exists? -> no -> exit 0
       |
       v
  paused: true? -> yes -> exit 0
       |
       v
  PHASE:
  |
  |-- idle/complete/"" -> (complete) rm state, exit 0
  |
  |-- designing
  |     -> find plan file (state frontmatter or latest docs/plans/*.md)
  |     -> run design-review.sh <plan-file>
  |     -> update state: phase -> implementing, git_checkpoint -> HEAD
  |     -> output JSON: decision: "block", reason: review text
  |
  |-- implementing
        -> git diff checkpoint..HEAD
        -> if diff <= 1 line: exit 0
        -> run task-review.sh <checkpoint> <task-desc>
        -> update state: task_index++, git_checkpoint -> HEAD
        -> output JSON: decision: "block", reason: review text
```

### Design Review (`design-review.sh`)

- Reads plan file content
- Resolves model via `resolve-model.sh --vendor $VENDOR`
- Builds prompt evaluating: completeness, performance, security, maintainability, simplicity
- Invokes `copilot --model $MODEL --silent --no-color -p "$(cat $PROMPT_FILE)"`
- Fallback: retry with alternate vendor model if primary fails
- Saves review to `.claude/copilot-collab/reviews/design-review-TIMESTAMP.md`

### Task Review (`task-review.sh`)

- Computes `git diff checkpoint..HEAD`
- Resolves model (uses stronger model for security-sensitive files or diffs > 200 lines)
- Builds prompt evaluating: correctness, performance, maintainability, best practices, edge cases
- Invokes copilot same as above
- Saves review to `.claude/copilot-collab/reviews/task-N-review-TIMESTAMP.md`

## Interactive Consultation (`/consult`)

Replaces the Phone a Friend plugin.

### Command: `/consult [task description]`

### Consultation Types

| Type | Trigger | Max Turns | Context |
|------|---------|-----------|---------|
| code-review | After implementation, before commit | 3 | Full (all modified files + diff) |
| second-opinion | Architectural decisions | 5 | Relevant files only |
| bug-analysis | Test failures, complex debugging | 3 | Full + error logs |

### Flow

1. Claude detects need (auto-suggest at complexity threshold, or user requests)
2. Claude asks permission via AskUserQuestion:
   - Shows files to be shared, line counts
   - Shows model options (GPT-5.3-Codex or Gemini 3 Pro)
   - Notes any redacted secrets
3. Claude runs `scripts/consult.sh --model $MODEL --type $TYPE`
4. `consult.sh` invokes: `copilot --model "$MODEL" --silent --no-color -p "$(cat "$PROMPT_FILE")"`
5. Claude presents objective comparison (Claude's view vs Copilot model's view)
6. User picks approach via AskUserQuestion
7. For follow-up turns: Claude re-invokes with accumulated context (previous turns included in prompt)
8. Consultation logged to `.claude/copilot-collab/consultations/YYYY-MM-DD-HHMMSS-type.md`

### Multi-Turn Context Accumulation

No session resume. Each follow-up turn builds the full prompt:

```
Previous exchange:
Q: [turn 1 question]
A: [turn 1 response]

Follow-up: [turn 2 question]
```

### Auto-Suggest Triggers

- Files changed >= 3
- Lines changed >= 100
- User says "done", "finished", "ready to commit"
- Test failures detected

### Secret Scrubbing

Before sharing context, scan for API keys, tokens, passwords, PII. Redact and note in the permission prompt.

## Commands

| Command | Purpose |
|---------|---------|
| `/copilot-collab [task]` | Start automated review session |
| `/copilot-status` | Show session state and recent reviews |
| `/copilot-pause` | Pause automated reviews |
| `/copilot-resume` | Resume automated reviews |
| `/copilot-skip` | Skip next review only |
| `/copilot-cancel` | End session |
| `/consult [topic]` | Interactive consultation |

## Hooks

| Event | Script | Purpose |
|-------|--------|---------|
| SessionStart | `session-start-hook.sh` | Persist SESSION_ID, run update check |
| SessionEnd | `session-end-hook.sh` | Clean up session state files |
| Stop | `stop-hook.sh` | State machine driver (timeout: 900s) |

## Skill (SKILL.md)

Guides Claude's behavior:
- When to auto-suggest consultations
- How to behave during designing/implementing phases
- How to present results objectively (never advocate)
- How to handle review feedback (auto-fix CRITICAL/WARNING, flag conflicts with approved design)
- Escape hatches: /copilot-pause, /copilot-resume, /copilot-skip, /copilot-cancel

## Empirical Findings (from testing on v0.0.421)

- `reasoning_effort: "xhigh"` in `~/.copilot/config.json` confirmed working for GPT models
- Without config: GPT-5.3-codex defaults to `medium` (28 reasoning tokens)
- With `xhigh`: 523 reasoning tokens, 3x API time
- Gemini has no configurable thinking mode (expected, different architecture)
- `copilot help config` provides the canonical model list for the installed binary
- stdin piping works: `cat file | copilot -p ""`
- stdin + inline `-p "text"` does NOT work (issue #683)
- `--silent --no-color` gives clean scriptable output
