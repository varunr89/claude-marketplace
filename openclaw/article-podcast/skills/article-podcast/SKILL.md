---
name: article-podcast
description: This skill should be used when the user wants to convert an article, blog post, research paper, or any URL into a podcast episode. Triggers include sending a URL with intent to listen, phrases like "podcast this", "make this a podcast", "queue this up", "listen to this", "generate a podcast", or "add this to my feed". Also triggers when the user sends an arXiv link, a PDF URL, or a news article URL and wants audio content generated from it.
version: 2.0.0
---

# Article Podcast -- URL to Published Podcast Episode

## Overview

This skill converts articles, papers, and blog posts into podcast episodes
published to an RSS feed. It uses a multi-TTS pipeline (Gemini 2.5 Flash,
Azure OpenAI TTS-HD, Edge TTS) with automatic content classification,
voice variety, and fallback. Generation runs in the background -- the user
gets a confirmation that the job is queued and receives a Signal notification
when the episode is ready (~3-5 minutes).

## When to Use

Activate this skill when:
- The user sends a URL and wants it converted to a podcast
- The user says "podcast this", "listen to this", "queue this up"
- The user sends an article/paper URL and wants audio content

## Workflow

### Step 1: Tell the user you are queueing the podcast(s)

Let the user know you are submitting their URL(s) for background processing.

### Step 2: Queue the podcast for generation

**IMPORTANT: When the user provides multiple URLs or PDFs, queue each one
as a separate podcast episode.** Run the generate.py command once per URL.
Each URL becomes its own independent episode. Never combine multiple URLs
into a single episode.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/article-podcast/scripts/generate.py \
  --url "<article_url>" \
  --format "<interview|discussion|narrator|deep-dive|brief|critique|debate>" \
  --length "<short|default|long>" \
  --instructions "<custom instructions or auto>" \
  --enqueue \
  --notification-recipient "d4e31a04-c781-45d8-ad2c-bb826fc80574"
```

The `--enqueue` flag writes a job to the background queue and returns
immediately with a JSON response containing the job_id.

Format options:
- **interview**: Host asks questions, expert explains (technical content)
- **discussion**: Two co-hosts with different perspectives (news, current events)
- **narrator**: Solo narrator telling the story (opinion, essays, blogs)
- **deep-dive**: Auto-classifies based on content (default)
- **brief**: Auto-classifies, shorter episode
- **critique**: Maps to interview format
- **debate**: Maps to discussion format

The `--length` flag controls episode duration. Default is `long`. Only use
`short` or `default` if the user explicitly asks for a shorter episode.
- **short**: ~5 minutes
- **default**: ~15 minutes
- **long**: Scales with article length (up to 60 minutes for very long articles)

The `--instructions` flag accepts either `auto` (default, selects based on
content type) or a custom string.

### Step 3: Confirm to the user

Tell the user the podcast has been queued and they will receive a Signal
notification when it is ready (typically 3-5 minutes). There is nothing
else to do -- the background worker handles generation, publishing, and
notification automatically.

If multiple URLs were queued, confirm the count (e.g., "Queued 3 podcasts").
Each will generate and notify independently.

## Per-Request Overrides

Users can override defaults via natural language:
- "make this an interview" -> `--format interview`
- "have two hosts discuss this" -> `--format discussion`
- "narrate this" -> `--format narrator`
- "keep it short" -> `--length short`
- "focus on the methodology" -> `--instructions "Focus on the methodology"`

Unless the user asks for something shorter, always use `--length long`.

## TTS Backend Details

The pipeline tries backends in order (configurable in plugin config):

1. **Gemini 2.5 Flash** (default primary) -- best quality multi-speaker, 650 words/chunk
2. **Azure OpenAI TTS-HD** -- high quality, 4096 chars/request
3. **Edge TTS** -- free, good quality, 10K chars/request

Each backend has its own voice pool (8 Gemini, 13 Azure, 16 Edge voices).
Voices are selected randomly with recent-avoidance to prevent repetition.
If the primary backend fails, the pipeline automatically falls back to the next.

## Error Handling

- If the URL is inaccessible, report to the user and ask if it is paywalled
- If enqueue fails, report the error and offer to retry
- TTS failures automatically fall back to the next backend in the chain

## Configuration

All defaults come from the plugin config in openclaw.plugin.json. Required
environment variables on the worker:
- `GEMINI_API_KEY` -- for Gemini TTS (primary)
- `AZURE_STORAGE_CONNECTION_STRING` -- for publishing
- `AZURE_API_KEY` -- for Azure OpenAI TTS (fallback, optional)
- `OPENCLAW_BIN` -- path to openclaw binary (if not in PATH)
