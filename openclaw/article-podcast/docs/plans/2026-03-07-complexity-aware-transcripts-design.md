# Complexity-Aware Transcript Generation

## Problem

Podcast episodes are too short and shallow. The transcript generation uses a hardcoded word-count-to-length mapping that doesn't account for content complexity. A dense 3K-word ML paper and a 20K-word opinion piece get treated similarly. Articles that assume advanced knowledge don't get the background explanations listeners need.

## Goal

Episodes should be as long as the content demands. A simple opinion piece can be 10 minutes. A dense academic paper that assumes specialized knowledge should be 45-60 minutes with background explanations woven in. The AI decides depth and length based on complexity and knowledge gaps, not word count.

## Target Audience

Undergraduate-level understanding. Anything beyond that needs explanation. If an article assumes familiarity with Bellman equations, policy gradients, or distributed consensus, the podcast should explain those concepts before building on them.

## Approach: Single-Pass LLM Self-Assessment (Approach A)

The LLM assesses complexity, identifies knowledge gaps, and decides episode length in a single call. No separate classification step.

## Changes

### SKILL.md (Orchestrated Path)

- **Step 2 (Plan Episodes):** Add instructions for AI agent to assess complexity relative to undergraduate audience, identify prerequisite concepts the article assumes, and decide length based on complexity + gaps.
- **Step 3 (Generate Transcripts):** Update subagent prompt to include identified knowledge gaps, instruct undergraduate-level audience assumption, and let subagent decide length.

### scriptgen.py (Quick Mode / Worker Path)

- Remove hardcoded word-count-to-length mapping from `build_transcript_prompt()`.
- Replace with prompt instructions that mirror the SKILL.md approach.
- LLM decides `estimated_duration_minutes` in its JSON output.

### No changes to

- `generate.py` (passes through)
- `synthesize.py`, `publish.py`, `voices.py`

## Principle

Qualitative decisions (complexity, depth, length, knowledge gaps) belong in the skill/prompt layer where the AI reasons. Python scripts are dumb executors. As models improve, the same instructions produce better results without code changes.
