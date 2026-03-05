---
name: copilot-collab
description: "Guides Claude's behavior during Copilot-collaborative development sessions: automated reviews (designing/implementing phases) and interactive consultations (/consult)"
---

# Copilot Collab

You are in a Copilot-collaborative development environment. GitHub Copilot CLI provides automated code reviews during development and interactive consultations for second opinions.

## Automated Review Phases

### Designing Phase
- Work on the design/plan normally (brainstorming, writing plans)
- When writing a plan file, update the state file's `plan_file` field:
  ```bash
  sed -i '' "s|^plan_file: .*|plan_file: \"docs/plans/YOUR-FILE.md\"|" .claude/copilot-collab/sessions/${CLAUDE_SESSION_ID}.md
  ```
- When you stop, the hook automatically sends the plan to Copilot for design review
- After review, the session transitions to implementing phase

### Implementing Phase
- Work through implementation tasks one at a time
- After each task, the hook triggers a Copilot code review of your changes
- **Auto-fix CRITICAL/WARNING issues**: When the review contains CRITICAL or WARNING severity items, fix them immediately and show a brief summary of what you changed
- **Flag design conflicts**: If a review suggestion conflicts with the approved design, note the conflict rather than blindly applying the suggestion
- Continue to the next task after addressing review feedback

## Interactive Consultations (/consult)

Use `/consult` for on-demand second opinions from GPT-5.3-Codex or Gemini 3 Pro.

### Consultation Types

| Type | When | Max Turns | Context to Share |
|------|------|-----------|-----------------|
| code-review | After implementation, before commit | 3 | All modified files + diff |
| second-opinion | Architectural decisions | 5 | Relevant files only |
| bug-analysis | Test failures, complex debugging | 3 | Full context + error logs |

### Auto-Suggest Triggers

Proactively suggest a consultation when:
- Files changed >= 3 (check: `git diff --name-only | wc -l`)
- Lines changed >= 100 (check: `git diff --stat`)
- User says "done", "finished", "ready to commit"
- Test failures detected

When auto-suggesting, phrase it as: "Would you like a Copilot consultation before proceeding? [files/lines changed summary]"

### Consultation Flow

1. **Gather context**: Collect relevant files, diffs, error logs
2. **Secret scrubbing**: Before sharing, scan for and redact:
   - API keys (patterns: `sk-`, `ghp_`, `github_pat_`, `AKIA`, `Bearer`)
   - Passwords and tokens in config files
   - Email addresses and PII
   - Note redactions in the permission prompt
3. **Ask permission**: Use AskUserQuestion showing:
   - Files to be shared with line counts
   - Model choice (GPT-5.3-Codex or Gemini 3 Pro)
   - Any redacted secrets
4. **Run consultation**: Write prompt to temp file, invoke consult.sh
5. **Present objectively**: Show both your perspective and the consulted model's perspective side by side. Never advocate for one over the other.
6. **User decides**: Use AskUserQuestion to let user pick approach
7. **Multi-turn follow-up**: For follow-ups, include previous Q&A in the prompt:
   ```
   Previous exchange:
   Q: [question]
   A: [response]

   Follow-up: [new question]
   ```
8. **Log**: Save consultation to `.claude/copilot-collab/consultations/YYYY-MM-DD-HHMMSS-type.md`

### Presentation Format

```markdown
## Consultation: [type]
**Model:** [model used]

### [Model Name]'s Analysis
[Their response]

### Claude's Analysis
[Your perspective]

### Key Differences
- [Point of agreement or disagreement]

### Recommendation
Both perspectives are presented above. Which approach would you prefer?
```

## Escape Hatches

| Command | Effect |
|---------|--------|
| `/copilot-pause` | Pause auto-reviews (keep session) |
| `/copilot-resume` | Resume auto-reviews |
| `/copilot-skip` | Skip next review only |
| `/copilot-cancel` | End session entirely |

Remind users of these if reviews feel disruptive.

## Important Rules

1. **Never advocate** in consultations -- present both perspectives equally
2. **Auto-fix** CRITICAL and WARNING review items without asking
3. **Always ask permission** before sharing code with external models
4. **Scrub secrets** before every consultation
5. **Log everything** -- reviews to `.claude/copilot-collab/reviews/`, consultations to `.claude/copilot-collab/consultations/`
