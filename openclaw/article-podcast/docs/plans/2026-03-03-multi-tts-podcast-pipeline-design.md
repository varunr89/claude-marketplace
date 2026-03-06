# Multi-TTS Podcast Pipeline Design

**Date:** 2026-03-03
**Status:** Approved
**Replaces:** NotebookLM-based generation via `notebooklm-py`

## Problem

The current podcast generation uses Google NotebookLM's unofficial Python API (`notebooklm-py`). This is:
- **Unreliable** -- unofficial API, 900s timeouts, frequent failures
- **Boring** -- always the same two voices, same discussion format
- **Inflexible** -- no control over length, format, or voice selection

## Solution: Two-Stage Pipeline with Multi-TTS Backends

Decouple podcast generation into **script generation** (LLM) and **audio synthesis** (TTS), with three TTS backends and dynamic voice/format selection.

## Architecture

```
URL -> Fetch Article -> Classify Content -> Select Format
    -> Stage 1: Script Generation (OpenClaw LLM)
    -> Stage 2: Audio Synthesis (Gemini Flash / Azure TTS-HD / Edge TTS)
    -> Existing Pipeline (publish.py -> Azure Blob -> RSS -> Spotify)
```

### What Changes
- `generate.py` -- `generate()` rewritten to orchestrate the two stages
- New: `scriptgen.py` -- LLM-based transcript generation
- New: `synthesize.py` -- Multi-backend TTS audio synthesis
- New: `voice_history.json` -- tracks recent voice assignments
- Removed dependency: `notebooklm-py`

### What Stays the Same
- `worker.py` -- still calls `generate()`, manages jobs
- `publish.py` -- uploads to Azure Blob + updates RSS feed
- `feed.py` -- RSS XML management
- `notifier.py` -- Signal notifications
- `job_manager.py` -- filesystem job queue
- Job queue directory structure
- Azure Blob Storage configuration
- RSS feed format and URL

## Stage 1: Script Generation (`scriptgen.py`)

### Content Fetching
- Extract clean article text from URL using `trafilatura`
- Fallback to `requests` + `beautifulsoup4` if trafilatura fails

### Content Classification
Extend existing technical-vs-general heuristics to auto-select format:
- **Technical/academic** (arxiv, IEEE, ACM, research papers) -> **Interview** (host + expert)
- **News/current events** (news domains, recent dates) -> **Two-host discussion**
- **Opinion/essay/blog** -> **Solo narrator**
- User can override via `--format` flag

### Transcript Generation
- Call OpenClaw's LLM routing (Gemini/Claude/GPT with fallbacks)
- Prompt includes: article content, format instructions, length guidance, tone guidance
- Length scales proportionally to article length; supports episodes up to 1 hour+

### Output: Structured JSON Transcript
```json
{
  "title": "Why Transformers Changed Everything",
  "format": "interview",
  "speakers": [
    {"id": "S1", "role": "host", "voice_style": "warm, curious"},
    {"id": "S2", "role": "expert", "voice_style": "knowledgeable, measured"}
  ],
  "segments": [
    {"speaker": "S1", "text": "Today we're diving into a paper that..."},
    {"speaker": "S2", "text": "Thanks for having me. This paper..."}
  ],
  "source_url": "https://arxiv.org/...",
  "estimated_duration_minutes": 12
}
```

Solo narrator format uses one speaker with longer segments.

## Stage 2: Audio Synthesis (`synthesize.py`)

### TTS Backend Fallback Chain
1. **Gemini 2.5 Flash TTS** (primary) -- best quality-to-cost, native 2-speaker
2. **Azure OpenAI TTS-HD** (fallback) -- reliable, good quality
3. **Edge TTS** (emergency fallback) -- free, always available

If primary fails, automatically retry with next backend. Log which backend was used.

### Azure OpenAI TTS-HD Endpoint
- URL: `https://varun-mmbhqa1x-swedencentral.cognitiveservices.azure.com/openai/deployments/tts-hd/audio/speech`
- API version: `2025-03-01-preview`
- Auth: `api-key` header via `AZURE_API_KEY` env var

### API Limits (Critical for Long Episodes)

| Backend | Max Input | Max Audio Output | Rate Limit |
|---|---|---|---|
| **Gemini Flash TTS** | 8,192 tokens | ~5 min 27 sec (hard cutoff) | 10 RPM free, 300 RPM paid |
| **Azure OpenAI TTS-HD** | 4,096 characters | ~5-6 min | 3 RPM default (Azure) |
| **Edge TTS** | ~15K chars safe | ~10 min | No formal limit (throttle risk) |

### Chunking Strategy

All three backends need chunking for episodes longer than ~5 minutes.

**Segment batching:** Consecutive same-speaker segments are batched into chunks
up to the backend's character limit. This minimizes API calls and preserves
natural speech flow within a speaker's turn.

**Audio stitching:**
- 300ms silence inserted at speaker changes (natural conversation pause)
- 30-50ms crossfade within same-speaker batches (eliminates click artifacts)
- All intermediate audio generated as WAV/PCM (lossless), final output as MP3

**Gemini-specific:** Transcript split into ~4.3-minute blocks (est. ~650 words, safety margin for 5:27 hard cutoff).
Each block sent as a complete multi-speaker prompt with voice configs.
Speaker names maintained across blocks for voice assignment continuity.

**Azure/Edge-specific:** Batched segments sent one API call per batch.
Rate limiting: 3 RPM for Azure with exponential backoff. A 30-min episode
with batching needs ~20 calls (~7 minutes at 3 RPM).

### Per-Backend Synthesis Approach
- **Gemini 2.5 Flash**: Native 2-speaker mode. Transcript chunked into ~5-min blocks. Each block sent with speaker voice configs. Audio stitched with crossfade.
- **Azure TTS-HD**: Consecutive same-speaker segments batched up to 4,096 chars. Each batch is one API call. Rate-limited to 3 RPM with backoff. Audio concatenated with pydub.
- **Edge TTS**: Same batching approach as Azure. Batches up to ~10K chars per call. Async API via edge-tts library.

### Dynamic Voice Selection

**Goal:** Every episode sounds different. No fixed voice pairings.

**Voice pools (expanded with accents and mixed genders):**

**Gemini Flash** -- all available voices:
`Aoede, Charon, Enceladus, Fenrir, Kore, Leda, Orbit, Puck` (+ more as Google adds them)

**Azure OpenAI TTS-HD** -- all 13 voices:
`alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin, cedar`

**Edge TTS** -- curated ~16 English neural voices across accents:
- US: `en-US-JennyNeural`, `en-US-AriaNeural`, `en-US-SaraNeural`, `en-US-GuyNeural`, `en-US-DavisNeural`, `en-US-TonyNeural`
- British: `en-GB-SoniaNeural`, `en-GB-RyanNeural`
- Australian: `en-AU-NatashaNeural`, `en-AU-WilliamNeural`
- Indian: `en-IN-NeerjaNeural`, `en-IN-PrabhatNeural`
- Irish: `en-IE-EmilyNeural`, `en-IE-ConnorNeural`
- South African: `en-ZA-LeahNeural`, `en-ZA-LukeNeural`

**Selection algorithm:**
1. For two-speaker formats: pick 2 distinct voices at random from the pool
2. For solo narrator: pick 1 voice at random
3. Recent-avoidance: track last 5 episodes in `voice_history.json`, prefer voices not recently used
4. User override: `--voices "nova,echo"` flag to force specific voices

## Configuration

Added to `config.json`:
```json
{
  "tts_backend": "auto",
  "tts_fallback_order": ["gemini", "azure-openai", "edge"],
  "gemini_api_key_env": "GEMINI_API_KEY",
  "azure_tts_endpoint": "https://varun-mmbhqa1x-swedencentral.cognitiveservices.azure.com/openai/deployments/tts-hd/audio/speech",
  "azure_tts_api_key_env": "AZURE_API_KEY",
  "azure_tts_api_version": "2025-03-01-preview",
  "voice_pools": {
    "gemini": ["Aoede", "Charon", "Enceladus", "Fenrir", "Kore", "Leda", "Orbit", "Puck"],
    "azure-openai": ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse", "marin", "cedar"],
    "edge": ["en-US-JennyNeural", "en-US-AriaNeural", "en-US-SaraNeural", "en-US-GuyNeural", "en-US-DavisNeural", "en-US-TonyNeural", "en-GB-SoniaNeural", "en-GB-RyanNeural", "en-AU-NatashaNeural", "en-AU-WilliamNeural", "en-IN-NeerjaNeural", "en-IN-PrabhatNeural", "en-IE-EmilyNeural", "en-IE-ConnorNeural", "en-ZA-LeahNeural", "en-ZA-LukeNeural"]
  }
}
```

## New Dependencies

```
trafilatura>=1.6.0      # Article text extraction
beautifulsoup4>=4.12.0  # Fallback article extraction
edge-tts>=6.1.0         # Microsoft Edge TTS (free)
pydub>=0.25.0           # Audio segment concatenation (requires ffmpeg)
google-genai>=1.0.0     # Gemini 2.5 Flash TTS API
```

Removed: `notebooklm-py>=0.3.0`

## Cost Estimate (per episode)

| Duration | Gemini Flash | Azure TTS-HD | Edge TTS |
|----------|-------------|--------------|----------|
| 15 min   | ~$0.29      | ~$0.68       | $0.00    |
| 30 min   | ~$0.58      | ~$1.36       | $0.00    |
| 60 min   | ~$1.16      | ~$2.72       | $0.00    |

Plus LLM cost for script generation (~$0.02-0.10 per episode via OpenClaw).

## Generation Time Estimates (per episode)

| Duration | Gemini Flash | Azure TTS-HD (3 RPM) | Edge TTS |
|----------|-------------|----------------------|----------|
| 15 min   | ~3 min (3 chunks) | ~7 min (10 batches) | ~2 min |
| 30 min   | ~5 min (6 chunks) | ~14 min (20 batches) | ~4 min |
| 60 min   | ~10 min (12 chunks) | ~28 min (40 batches) | ~7 min |

Azure is the bottleneck due to 3 RPM rate limit. Consider requesting quota
increase from Azure if Azure becomes the primary backend.

## Deployment

Same as current -- rsync to both paths on Surface Pro, restart worker service.
No gateway restart needed (plugin config schema unchanged at the skill level).
New env vars needed on Surface Pro: `GEMINI_API_KEY`, `AZURE_API_KEY`.
