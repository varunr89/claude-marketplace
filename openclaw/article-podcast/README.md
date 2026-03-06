# openclaw-plugin-article-podcast

Convert any URL into a podcast episode using multi-TTS synthesis with automatic content classification, voice variety, and RSS publishing.

## Features

- **Multi-TTS synthesis** with automatic fallback: Gemini 2.5 Flash -> Azure OpenAI TTS-HD -> Edge TTS
- **Content-aware formatting**: auto-classifies articles as interview, discussion, or narrator
- **Voice variety**: 37 voices across 3 backends with recent-avoidance to prevent repetition
- **RSS publishing**: uploads audio to Azure Blob Storage and maintains a podcast RSS feed
- **Background worker**: daemon for automated podcast generation with Signal notifications

## Prerequisites

- Python 3.9+
- ffmpeg (`brew install ffmpeg` / `apt install ffmpeg`)
- Azure Storage account with a public-read blob container
- OpenClaw installed

## Installation

```bash
npm install openclaw-plugin-article-podcast
pip install -r requirements.txt
```

## Setup

### 1. Set environment variables

```bash
export GEMINI_API_KEY="your-gemini-api-key"
export AZURE_STORAGE_CONNECTION_STRING="your-connection-string"
# Optional: for Azure OpenAI TTS fallback
export AZURE_API_KEY="your-azure-openai-key"
```

### 2. Create Azure Storage container

```bash
az storage container create --name podcasts --public-access blob
```

### 3. Configure the plugin

Set the required config values in OpenClaw:

- `azure_storage_account` -- your Azure Storage account name
- `feed_url` -- the public URL where feed.xml will be hosted

Optional config:

- `azure_container` -- blob container name (default: `podcasts`)
- `feed_title` -- podcast title
- `feed_author` -- author name
- `feed_description` -- feed description
- `feed_image_url` -- URL to cover art
- `podcast_format` -- default format: `auto`, `interview`, `discussion`, `narrator`
- `tts_fallback_order` -- TTS backend priority (default: `["gemini", "azure-openai", "edge"]`)
- `spotify_url` -- Spotify show URL for notifications
- `azure_tts_endpoint` -- Azure OpenAI TTS endpoint URL
- `azure_tts_api_version` -- Azure API version (default: `2025-03-01-preview`)

### 4. Register with Spotify (optional)

Go to [podcasters.spotify.com](https://podcasters.spotify.com) and submit your feed URL.

## Usage

Send a URL on Signal:

```
https://arxiv.org/abs/2401.12345
```

Or tell the OpenClaw agent: "podcast this", "listen to this", "queue this up".

The plugin will:
1. Fetch and extract article text (trafilatura with BeautifulSoup fallback)
2. Auto-classify content format (interview, discussion, or narrator)
3. Generate a natural podcast transcript via LLM
4. Synthesize audio using multi-TTS with voice variety
5. Upload to Azure Blob Storage and update RSS feed
6. Send a Signal notification with episode title and duration

### Format Overrides

- "make this an interview" -- interview with host and expert
- "have two hosts discuss this" -- two co-host discussion
- "narrate this like a story" -- solo narrator format
- "keep it short" -- ~5 minute episode

## TTS Backends

| Backend | Voices | Quality | Rate Limit | Cost |
|---------|--------|---------|------------|------|
| Gemini 2.5 Flash | 8 | Best | 10 RPM (free tier) | Free |
| Azure OpenAI TTS-HD | 13 | High | 3 RPM | Pay-per-use |
| Edge TTS | 16 | Good | None | Free |

## Project Structure

```
openclaw-plugin-article-podcast/
  openclaw.plugin.json    # plugin manifest and config schema
  package.json
  index.ts                # plugin entry: writes config for Python scripts
  skills/
    article-podcast/
      SKILL.md            # skill definition for OpenClaw
      scripts/
        generate.py       # main orchestrator: fetch -> LLM -> TTS -> publish
        scriptgen.py      # article fetching, classification, prompt building
        synthesize.py     # multi-backend TTS with chunking and fallback
        voices.py         # voice pool management and selection
        publish.py        # Azure Blob upload and RSS feed update
        feed.py           # RSS feed XML management
        notifier.py       # Signal notification sending
        worker.py         # background job processing daemon
        job_manager.py    # filesystem-based job queue
  tests/
    test_voices.py
    test_scriptgen.py
    test_synthesize.py
    test_feed.py
    test_job_manager.py
    test_title_resolution.py
  requirements.txt
```
