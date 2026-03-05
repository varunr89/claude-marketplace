---
description: "Consult other AI models for second opinions, code reviews, and collaborative problem-solving"
argument-hint: "[topic or question]"
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/scripts/consult.sh:*)", "Bash(${CLAUDE_PLUGIN_ROOT}/scripts/resolve-model.sh:*)"]
---

# Consult

This command triggers an interactive consultation with another AI model via Copilot CLI.

Before running the consultation:
1. Determine the consultation type: code-review, second-opinion, or bug-analysis
2. Gather relevant context (files, diffs, error logs)
3. Ask the user for permission using AskUserQuestion, showing what will be shared and offering model choice (GPT-5.3-Codex or Gemini)
4. Build the prompt and run the consultation

To resolve available models:
```!
echo "OpenAI: $(${CLAUDE_PLUGIN_ROOT}/scripts/resolve-model.sh --vendor openai)"
echo "Google: $(${CLAUDE_PLUGIN_ROOT}/scripts/resolve-model.sh --vendor google)"
```

After getting the user's model choice, write the prompt to a temp file and run:
```bash
PROMPT_FILE=$(mktemp)
cat > "$PROMPT_FILE" <<'PROMPT_EOF'
[Your constructed prompt here]
PROMPT_EOF
${CLAUDE_PLUGIN_ROOT}/scripts/consult.sh --model MODEL_ID --type CONSULTATION_TYPE --prompt-file "$PROMPT_FILE"
rm -f "$PROMPT_FILE"
```

After receiving the response:
- Present an objective comparison between your perspective and the consulted model's perspective
- Use AskUserQuestion to let the user choose an approach
- Log the consultation to `.claude/copilot-collab/consultations/`
