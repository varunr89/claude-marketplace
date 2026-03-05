---
name: article-podcast
description: This skill should be used when the user wants to convert an article, blog post, research paper, or any URL into a podcast episode. Triggers include sending a URL with intent to listen, phrases like "podcast this", "make this a podcast", "turn this into audio", "queue this up", "listen to this", "generate a podcast", or "add this to my feed". Also triggers when the user sends an arXiv link, a PDF URL, or a news article URL and wants audio content generated from it.
version: 1.0.0
---

# Article Podcast -- URL to Published Podcast Episode

## Overview

Convert any URL (article, paper, blog post) into a published podcast episode with
multi-voice TTS audio. The pipeline fetches article content, generates a podcast
transcript, synthesizes audio using Gemini/Azure OpenAI/Edge TTS with voice variety,
and publishes to an RSS feed via Azure Blob Storage.

## Prerequisites

Before first use, run the setup script to create a virtual environment and install dependencies:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh
```

Required environment variables (set in shell or `~/.article-podcast/env`):
- `GEMINI_API_KEY` -- Google Gemini API key (primary TTS backend)
- `AZURE_STORAGE_CONNECTION_STRING` -- Azure Blob Storage connection string (for publishing)

Optional:
- `AZURE_API_KEY` -- Azure OpenAI key (fallback TTS)
- `PODCAST_DATA_DIR` -- data directory (default: `~/.article-podcast/`)
- `SIGNAL_RPC_URL` -- Signal notification endpoint

A config file at `~/.article-podcast/config.json` must exist with at minimum:
```json
{
  "azure_storage_account": "your-account-name",
  "feed_url": "https://your-account.blob.core.windows.net/podcasts/feed.xml"
}
```

## Workflow

### Single URL -- Standard Flow

When the user provides a URL to podcast:

#### Step 1: Fetch and classify the article

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/venv/bin/activate && \
python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from scriptgen import fetch_article, classify_content, build_transcript_prompt
import json

url = '<URL>'
text = fetch_article(url)
fmt = classify_content(url, text[:500])
prompt = build_transcript_prompt(text, fmt, url)
print(json.dumps({'format': fmt, 'word_count': len(text.split()), 'prompt_length': len(prompt)}))
" 2>/dev/null
```

This outputs the detected format (`interview`, `discussion`, or `narrator`) and article stats.

#### Step 2: Generate the transcript

Generate a podcast transcript JSON based on the article content. The transcript must follow this exact schema:

```json
{
  "title": "<catchy episode title, 5-10 words>",
  "format": "<interview|discussion|narrator>",
  "speakers": [
    {"id": "S1", "role": "<host|expert|co-host|narrator>"},
    {"id": "S2", "role": "<expert|co-host>"}
  ],
  "segments": [
    {"speaker": "S1", "text": "..."},
    {"speaker": "S2", "text": "..."}
  ],
  "source_url": "<original URL>"
}
```

Format guidelines:
- **interview**: Host (S1) asks questions, Expert (S2) explains. 2 speakers.
- **discussion**: Two co-hosts (S1=Alex, S2=Sam) with different perspectives. 2 speakers.
- **narrator**: Solo narrator (S1) telling the story. 1 speaker.

Writing rules:
- Natural speech, not written prose. Use contractions and conversational tone.
- No stage directions, sound effects, or non-speech annotations.
- Each segment: 1-4 sentences, avoid monologues longer than ~50 words.
- Cover key points accessibly. Start with an engaging hook, not "welcome to the podcast."
- Target ~150 words per minute of desired episode length.

Write the transcript JSON to a temporary file:

```bash
cat > /tmp/podcast-transcript.json << 'TRANSCRIPT_EOF'
<generated transcript JSON>
TRANSCRIPT_EOF
```

#### Step 3: Synthesize audio and publish

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/venv/bin/activate && \
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate.py \
  --url "<URL>" \
  --transcript-file /tmp/podcast-transcript.json \
  --publish
```

This synthesizes audio via the TTS fallback chain (Gemini -> Azure OpenAI -> Edge),
uploads to Azure Blob Storage, and updates the RSS feed. Output is JSON with
`audio_url`, `feed_url`, `title`, `duration_seconds`, and `backend_used`.

#### Step 4: Report results

Tell the user the episode title, duration, which TTS backend was used, and the
audio URL. Clean up the temp transcript file.

### Multiple URLs

When the user provides multiple URLs, process each one independently as a separate
episode. Run all steps for each URL sequentially.

### Background Worker Mode

For automated/scheduled use (e.g., email-triggered), enqueue jobs for the background worker:

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/venv/bin/activate && \
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate.py \
  --url "<URL>" \
  --enqueue \
  --notification-recipient "<Signal UUID>"
```

The worker daemon (`worker.py`) polls for jobs, generates audio using a configured
LLM backend (via `LLM_COMMAND` or `OPENCLAW_BIN` env vars), publishes, and sends
Signal notifications. Start the worker via systemd or manually:

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/venv/bin/activate && \
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/worker.py
```

## Per-Request Overrides

Users can override defaults via natural language:
- "make this brief" or "keep it short" -> generate a ~5 min episode
- "do a deep interview" -> use interview format
- "have two hosts discuss this" -> use discussion format
- "narrate this like a story" -> use narrator format
- "use voices Puck and Kore" -> pass specific voice names

## TTS Backend Details

The pipeline tries backends in order (configurable via `tts_fallback_order` in config):

1. **Gemini 2.5 Flash** (default primary) -- best quality multi-speaker, 650 words/chunk, 10 RPM free tier
2. **Azure OpenAI TTS-HD** -- high quality, 4096 chars/request, 3 RPM limit
3. **Edge TTS** -- free, good quality, 10K chars/request, no rate limit

Each backend has its own voice pool (8 Gemini, 13 Azure, 16 Edge voices). Voices are
selected randomly with recent-avoidance to prevent repetition across episodes.

## Error Handling

- If article fetch fails, report to the user and ask if it is paywalled or requires login
- If TTS synthesis fails on primary backend, the pipeline automatically falls back to the next backend
- If publishing fails, the audio file path is still returned so the user can retry or publish manually

## Configuration Reference

Full `~/.article-podcast/config.json` options:

```json
{
  "azure_storage_account": "account-name",
  "azure_container": "podcasts",
  "feed_url": "https://account.blob.core.windows.net/podcasts/feed.xml",
  "feed_title": "My Reading List",
  "feed_author": "Author Name",
  "feed_description": "AI-generated podcast episodes",
  "feed_image_url": "https://example.com/cover.jpg",
  "tts_fallback_order": ["gemini", "azure-openai", "edge"],
  "spotify_url": "https://open.spotify.com/show/...",
  "azure_tts_endpoint": "https://your-endpoint.cognitiveservices.azure.com/openai/deployments/tts-hd/audio/speech",
  "azure_tts_api_version": "2025-03-01-preview"
}
```
