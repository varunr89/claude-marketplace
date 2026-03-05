# Article Podcast

Convert any URL into a podcast episode with multi-voice TTS audio, published to an RSS feed.

## Features

- **Multi-TTS synthesis** with automatic fallback: Gemini 2.5 Flash -> Azure OpenAI TTS-HD -> Edge TTS
- **Content-aware formatting**: auto-classifies articles as interview, discussion, or narrator
- **Voice variety**: 37 voices across 3 backends with recent-avoidance to prevent repetition
- **RSS publishing**: uploads audio to Azure Blob Storage and maintains a podcast RSS feed
- **Background worker**: optional daemon for automated/scheduled podcast generation

## Quick Start

### 1. Install the plugin

```bash
# From Claude Code
/install article-podcast
```

### 2. Run setup

```bash
bash ~/.claude/plugins/cache/varunr-marketplace/article-podcast/*/scripts/setup.sh
```

Or in Claude Code, just say "set up the article podcast plugin" and the skill handles it.

### 3. Configure

Edit `~/.article-podcast/config.json` with your Azure Storage details:

```json
{
  "azure_storage_account": "your-account-name",
  "feed_url": "https://your-account.blob.core.windows.net/podcasts/feed.xml"
}
```

Set required environment variables:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
export AZURE_STORAGE_CONNECTION_STRING="your-connection-string"
```

### 4. Generate a podcast

In Claude Code:

```
/podcast https://paulgraham.com/superlinear.html
```

Or just paste a URL and say "podcast this".

## How It Works

1. **Fetch**: extracts clean article text via trafilatura (with BeautifulSoup fallback)
2. **Classify**: determines format (interview, discussion, narrator) based on URL and content
3. **Script**: Claude generates a natural podcast transcript in JSON format
4. **Synthesize**: TTS converts the transcript to audio with speaker-appropriate voices
5. **Publish**: uploads to Azure Blob Storage and updates the RSS feed
6. **Report**: returns the episode URL, title, duration, and backend used

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key for primary TTS |
| `AZURE_STORAGE_CONNECTION_STRING` | Yes | Azure Blob Storage connection string |
| `AZURE_API_KEY` | No | Azure OpenAI key for fallback TTS |
| `PODCAST_DATA_DIR` | No | Data directory (default: `~/.article-podcast/`) |
| `SIGNAL_RPC_URL` | No | Signal notification endpoint |
| `LLM_COMMAND` | No | Custom LLM command for background worker |

### Config File (`~/.article-podcast/config.json`)

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `azure_storage_account` | Yes | - | Azure Storage account name |
| `feed_url` | Yes | - | Public URL of RSS feed XML |
| `azure_container` | No | `podcasts` | Blob container name |
| `feed_title` | No | `My Podcast` | RSS feed title |
| `feed_author` | No | - | RSS feed author |
| `feed_description` | No | - | RSS feed description |
| `feed_image_url` | No | - | Podcast cover art URL |
| `tts_fallback_order` | No | `["gemini", "azure-openai", "edge"]` | TTS backend priority |
| `spotify_url` | No | - | Spotify URL for notifications |

### System Dependencies

- **Python 3.9+**
- **ffmpeg** (for audio processing): `brew install ffmpeg` / `apt install ffmpeg`

## TTS Backends

| Backend | Voices | Quality | Rate Limit | Cost |
|---------|--------|---------|------------|------|
| Gemini 2.5 Flash | 8 | Best | 10 RPM (free tier) | Free |
| Azure OpenAI TTS-HD | 13 | High | 3 RPM | Pay-per-use |
| Edge TTS | 16 | Good | None | Free |

## Background Worker (Advanced)

For automated podcast generation (e.g., triggered by email or cron):

```bash
# Start the worker daemon
source ~/.article-podcast/venv/bin/activate
python3 scripts/worker.py

# Enqueue a job
python3 scripts/generate.py --url "https://example.com/article" --enqueue
```

The worker requires an LLM backend configured via `LLM_COMMAND` env var. See the
source code for details on integrating with your LLM of choice.

## License

MIT
