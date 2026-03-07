# AI-Orchestrated Podcast Generator

## Overview

Redesign the article-podcast plugin so the AI agent orchestrates the entire pipeline -- from parsing any source to publishing episodes. Python scripts are tools the agent calls; the agent handles all decision-making, splitting, transcript generation, and error recovery.

## Goals

- Accept any input source: URLs, PDFs, YouTube (single + playlist), EPUB, DOCX, local text files
- Automatically detect document structure (chapters, sections, timestamps) and split into episodes
- Follow user instructions to customize splitting, format, and output
- Produce numbered episode series from multi-part sources (e.g., "Book Title (3/12): Chapter 3")
- Self-extending: when the AI encounters an unsupported source type, it writes a parser and registers it

## Architecture

### AI as Orchestrator

The OpenClaw agent follows the `article-podcast` skill, which guides it through the full pipeline. There is no monolithic `generate.py` -- instead the agent calls individual tool scripts and uses subagents for parallelism.

```
User: source + instructions
  |
  v
Main Agent (orchestrator, follows SKILL.md)
  |
  |-- calls parse_source.py
  |     -> extracts text + detects structure
  |     -> returns structured JSON (sections, metadata)
  |
  |-- decides splitting strategy based on:
  |     - user instructions ("split by chapters", "skip appendix")
  |     - detected structure (TOC, bookmarks, headings)
  |     - section word counts (merge short sections, note long ones)
  |
  |-- dispatches transcript subagents (parallel):
  |     Subagent 1: chunk 1 text -> transcript JSON file
  |     Subagent 2: chunk 2 text -> transcript JSON file
  |     ...
  |
  |-- calls synthesize_chunk.py per transcript:
  |     - Gemini/Edge: can parallelize
  |     - Azure: serialize (3 RPM limit)
  |
  |-- calls publish_episode.py per audio file:
  |     - uploads to Azure Blob
  |     - updates RSS feed
  |
  |-- reports results to user
```

### Tool Scripts

All tools are CLI scripts in `skills/article-podcast/scripts/`. Each takes structured input and returns structured JSON output.

| Tool | Called By | Input | Output |
|------|-----------|-------|--------|
| `parse_source.py` | Main agent | `--source <url-or-path>` | JSON: title, metadata, sections[] with text + word_count |
| `synthesize_chunk.py` | Main agent | `--transcript <path> --backend <name> --voices <v1,v2>` | JSON: audio_path, duration_seconds, backend_used |
| `publish_episode.py` | Main agent | `--audio <path> --title <title> --description <desc>` | JSON: audio_url, feed_url |

### Transcript Generation (Subagents)

Transcript generation is delegated to subagents to:
- **Avoid context pollution**: main agent never ingests full chapter text
- **Enable parallelism**: N chapters = N concurrent subagents
- **Isolate failures**: one chapter failing doesn't affect others
- **Maximize quality**: each subagent has full context budget for its chapter

Each subagent receives:
- A file path to the chunk text (not inline)
- Format instructions (interview, discussion, narrator)
- Target length
- Series context (episode N of M, overall topic)

The subagent writes a transcript JSON file and returns the path. The transcript JSON follows the existing format:

```json
{
  "title": "Episode title",
  "format": "interview",
  "speakers": [{"id": "S1", "role": "host"}, {"id": "S2", "role": "expert"}],
  "segments": [
    {"speaker": "S1", "text": "..."},
    {"speaker": "S2", "text": "..."}
  ]
}
```

### Long Chapter Handling (Sliding Window)

For chapters exceeding ~10k words:
1. Split into overlapping windows (~8k words with ~500 word overlap)
2. Each window gets its own subagent transcript generation
3. Main agent stitches the transcript segments, removing overlap at boundaries
4. Result is a single transcript JSON for the chapter

## Parser Architecture

### Self-Extending Parser Registry

`parse_source.py` is a thin dispatcher. Individual parsers live in `scripts/parsers/` and are registered in `_registry.json`.

#### Registry format (`_registry.json`):

```json
{
  "patterns": [
    {"match": "*.pdf", "type": "file_ext", "parser": "pdf.py"},
    {"match": "youtube.com|youtu.be", "type": "url_pattern", "parser": "youtube.py"},
    {"match": "*.epub", "type": "file_ext", "parser": "epub.py"},
    {"match": "*.docx", "type": "file_ext", "parser": "docx.py"},
    {"match": "*.txt|*.md", "type": "file_ext", "parser": "text.py"},
    {"match": "*", "type": "fallback", "parser": "web.py"}
  ]
}
```

#### Parser contract (all parsers must output):

```json
{
  "source_type": "pdf",
  "title": "Book or Article Title",
  "metadata": {
    "author": "Author Name",
    "date": "2024-01-15",
    "source_url": "https://..."
  },
  "sections": [
    {
      "title": "Chapter 1: Introduction",
      "text": "Full text of this section...",
      "word_count": 8200,
      "index": 0
    }
  ],
  "total_words": 145000
}
```

If a source has no natural sections, the parser returns a single section with all the text. The AI then decides whether to split it.

#### Ships with v1:

| Parser | Library | Handles |
|--------|---------|---------|
| `web.py` | trafilatura, BeautifulSoup | Web articles, blog posts |
| `pdf.py` | PyMuPDF (fitz) | PDFs with bookmark/TOC-based chapter detection |
| `youtube.py` | yt-dlp | Single videos (captions) and playlists (list + per-video captions) |
| `epub.py` | ebooklib | EPUB books with chapter detection |
| `docx.py` | python-docx | Word documents with heading-based sections |
| `text.py` | stdlib | Plain text and markdown files |

#### Self-extension flow:

When `parse_source.py` finds no matching parser:
1. Returns `{"status": "no_parser", "detected_type": "notion.so", "raw_input": "..."}`
2. AI writes a new parser script following the contract
3. AI installs any required packages (`pip install` in venv)
4. AI adds entry to `_registry.json`
5. AI calls `parse_source.py` again -- now it works
6. New parser persists for all future use

## Episode Naming

Multi-part sources use numbered series naming:

```
{Source Title} ({N}/{Total}): {Section Title}
```

Examples:
- "RL: An Introduction (1/12): Multi-armed Bandits"
- "CS224R Playlist (3/10): Policy Gradients"
- "Blog Series: Transformers (2/5): Attention Is All You Need"

Single-source episodes use the existing title logic (no numbering).

## Changes from Current Pipeline

| Current | New |
|---------|-----|
| `generate.py` monolith (fetch + LLM + TTS + publish) | Individual tool scripts, AI orchestrates |
| `fetch_article(url)` -- URLs only, trafilatura | `parse_source.py` -- any source type, extensible registry |
| LLM called via `openclaw agent` subprocess | Subagents write transcripts directly (they are the LLM) |
| One input = one episode | One input = N episodes based on structure + instructions |
| Fixed pipeline, no user control over splitting | AI interprets instructions to customize everything |
| Worker daemon polls job queue | Main agent drives the pipeline directly |

## Files to Create

```
skills/article-podcast/
  SKILL.md                          <- rewrite: full AI-orchestrated pipeline guide
  scripts/
    parse_source.py                 <- dispatcher: detect type, call parser, return JSON
    synthesize_chunk.py             <- extract from current synthesize.py, CLI wrapper
    publish_episode.py              <- extract from current publish.py, CLI wrapper
    parsers/
      _registry.json                <- source type -> parser mapping
      web.py                        <- trafilatura/BS4 (from existing fetch_article)
      pdf.py                        <- PyMuPDF + bookmark detection
      youtube.py                    <- yt-dlp captions + playlist support
      epub.py                       <- ebooklib chapter extraction
      docx.py                       <- python-docx heading detection
      text.py                       <- plain text / markdown
```

## Files to Modify

- `requirements.txt` -- add PyMuPDF, ebooklib, python-docx
- `SKILL.md` -- complete rewrite for AI-orchestrated flow
- `synthesize.py` -- keep as library, add CLI entry point as `synthesize_chunk.py`
- `publish.py` -- keep as library, add CLI entry point as `publish_episode.py`

## Files to Keep (unchanged)

- `voices.py` -- voice pool management
- `feed.py` -- RSS feed generation
- `worker.py` / `job_manager.py` -- still useful for background async jobs via Signal

## Dependencies (new)

- `PyMuPDF` (fitz) -- PDF text extraction + bookmarks
- `ebooklib` -- EPUB parsing
- `python-docx` -- DOCX parsing
- `yt-dlp` -- YouTube (already used in experiments, not yet in requirements)
