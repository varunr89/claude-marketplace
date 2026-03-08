---
name: article-podcast
description: "This skill converts any content source into podcast episodes. Triggers: sending a URL, PDF, YouTube link, book, or file with intent to listen; phrases like 'podcast this', 'make this a podcast', 'listen to this', 'generate a podcast'; sending content with instructions like 'split by chapters', 'make a series'. Handles single articles, multi-chapter books, YouTube playlists, and any document format."
version: 3.0.0
---

# Article Podcast -- Any Source to Published Podcast Episodes

## Overview

This skill converts any content source (URLs, PDFs, YouTube videos/playlists,
EPUBs, DOCX files, plain text) into podcast episodes published to an RSS feed.
You orchestrate the full pipeline: parse the source, decide how to split it,
generate transcripts via subagents, synthesize audio, and publish.

## When to Use

Activate this skill when:
- The user sends a URL, file, or YouTube link and wants it as a podcast
- The user says "podcast this", "listen to this", "queue this up"
- The user sends a book/PDF and says "split by chapters"
- The user sends a YouTube playlist
- The user sends any content with podcast-related intent

## Tool Scripts

All tools are in `${OPENCLAW_PLUGIN_ROOT}/skills/article-podcast/scripts/`.
The venv is at `${OPENCLAW_PLUGIN_ROOT}/skills/article-podcast/venv/`.
Activate it before running any script: `source ${OPENCLAW_PLUGIN_ROOT}/skills/article-podcast/venv/bin/activate`

| Tool | Purpose | Usage |
|------|---------|-------|
| `parse_source.py` | Extract text + structure from any source | `python3 parse_source.py --source <url-or-path>` |
| `synthesize_chunk.py` | TTS synthesis from transcript JSON | `python3 synthesize_chunk.py --transcript <path> --backend <name> --voices <v1,v2>` |
| `publish_episode.py` | Upload audio + update RSS feed | `python3 publish_episode.py --mp3 <path> --title <title> --description <desc> --duration <secs> --source-url <url> --config <path>` |

Config path: `~/.openclaw/plugins/openclaw-plugin-article-podcast/config.json`

## Workflow

### Step 1: Parse the Source

Run parse_source.py to extract text and detect structure:

```bash
python3 ${OPENCLAW_PLUGIN_ROOT}/skills/article-podcast/scripts/parse_source.py \
  --source "<url-or-file-path>"
```

This returns JSON with:
- `source_type`: what kind of source (web, pdf, youtube, epub, docx, text)
- `title`: detected title
- `sections[]`: array of `{title, text, word_count, index}`
- `total_words`: total word count across all sections

**If it returns `{"status": "no_parser"}:`** You need to write a new parser.
See "Writing New Parsers" below.

### Step 2: Plan the Episodes

Read the parsed structure and the user's instructions to decide:

1. **How many episodes?** Each section can become an episode, or sections
   can be merged/split based on instructions.
2. **Episode titles?** For multi-part sources use: `{Source Title} ({N}/{Total}): {Section Title}`
   For single episodes, use the source title or a catchy variant.
3. **Format?** Choose interview (Host + Expert), discussion (two co-hosts),
   or narrator (solo) based on content type or user request.
4. **Long sections?** If a section exceeds ~10,000 words, plan to split it
   into overlapping windows (~8,000 words with ~500 word overlap) for
   transcript generation, then stitch the results.

**Complexity Assessment and Knowledge Gap Analysis:**

Before generating transcripts, analyze each episode's content:

- **Target audience:** The listener has an undergraduate-level understanding.
  Anything beyond that must be explained in the podcast.
- **Identify knowledge gaps:** Read the content and list the concepts,
  techniques, or background knowledge the article *assumes* but does not
  explain. For example, if a paper discusses "policy gradient methods,"
  the listener needs to understand what a policy is, what gradients are
  in this context, and why they matter.
- **Assess complexity:** Based on the density of assumed knowledge, decide
  how much background explanation is needed. A Paul Graham essay needs
  little background. A systems paper assuming distributed consensus
  knowledge needs significant background. A math-heavy ML paper needs
  the most.
- **Decide episode length from complexity, not word count.** A simple
  20K-word opinion piece might need only 10 minutes. A dense 3K-word
  paper with many knowledge gaps might need 45-60 minutes. Let the
  content's complexity and the amount of background explanation needed
  drive the length.

Include your knowledge gap analysis in the subagent prompt (Step 3) so
the transcript writer knows exactly what to explain.

**Decision guidelines:**
- User says "split by chapters" -> one episode per section
- User says "make one episode" -> merge all sections
- User says nothing specific -> if sections > 3 and each > 1,000 words, split; otherwise merge
- Sections under 500 words -> merge with adjacent section
- Skip sections that are clearly front matter, table of contents, or index

Tell the user your plan before proceeding: "Found 12 chapters, generating
12 episodes titled 'Book Title (1/12): Chapter Name'..."

### Step 3: Generate Transcripts (use subagents)

For each planned episode, dispatch a subagent to write the transcript.
**Do NOT read the full text into your context.** Save each section's text
to a temp file and tell the subagent where to find it.

For each episode chunk:

1. Save the section text to a temp file:
   ```bash
   # Write section text to temp file (use Write tool, not bash)
   ```

2. Dispatch a subagent with this prompt:
   ```
   Read the content at <temp_file_path>. Write a podcast transcript in
   <format> format (interview/discussion/narrator).
   This is episode <X> of <Y> in a series about <topic>.

   TARGET AUDIENCE: The listener has an undergraduate-level understanding.
   Any concept beyond that must be explained clearly in the podcast.

   KNOWLEDGE GAPS TO FILL:
   <List the specific concepts/prerequisites you identified in Step 2 that
   the article assumes but the listener likely doesn't know. Be specific,
   e.g., "Bellman equations and why they matter for value functions",
   "how distributed consensus works at a high level", "what policy
   gradients are and why they're used in RL".>

   DEPTH AND LENGTH:
   - Do NOT skim the surface. Explain fewer concepts deeply rather than
     many concepts shallowly.
   - Weave background explanations naturally into the conversation. When
     the article introduces an advanced concept, have the speakers pause
     to build understanding from first principles before proceeding.
   - Let the content's complexity determine the length. A simple opinion
     piece might be 1,500 words (~10 minutes). A dense technical paper
     with many knowledge gaps might need 7,000-9,000 words (~45-60
     minutes). Use your judgment.
   - Report your chosen length in estimated_duration_minutes.

   Output ONLY valid JSON:
   {
     "title": "<episode title>",
     "format": "<format>",
     "speakers": [{"id": "S1", "role": "host"}, {"id": "S2", "role": "expert"}],
     "segments": [{"speaker": "S1", "text": "..."}, {"speaker": "S2", "text": "..."}],
     "estimated_duration_minutes": <number>
   }

   Rules:
   - Natural speech, not written prose. Use contractions, conversational tone.
   - No stage directions or sound effects.
   - Each segment 1-4 sentences, avoid monologues over ~50 words.
   - Start with a brief hook, do not say "welcome to the podcast."

   Save the JSON to <output_path>.
   ```

3. Collect the transcript JSON file path from the subagent.

**Parallelism:** Dispatch multiple subagents concurrently for different episodes.
Each writes to a separate output file.

**Sliding window for long sections:** If a section is >10k words, split into
overlapping windows, dispatch a subagent for each window, then stitch the
transcript segments together (removing overlap).

### Step 4: Synthesize Audio

For each transcript JSON, call synthesize_chunk.py:

```bash
python3 ${OPENCLAW_PLUGIN_ROOT}/skills/article-podcast/scripts/synthesize_chunk.py \
  --transcript <transcript.json> \
  --backend gemini \
  --config ~/.openclaw/plugins/openclaw-plugin-article-podcast/config.json
```

Returns JSON: `{audio_path, backend_used, voices_used, duration_seconds}`

**Backend notes:**
- **Gemini**: Best quality, ~2 min generation time, can parallelize freely
- **Azure OpenAI**: High quality, but 3 RPM rate limit -- serialize these calls
- **Edge TTS**: Free, good quality, fast -- can parallelize

### Step 5: Publish Episodes

For each audio file, call publish_episode.py:

```bash
python3 ${OPENCLAW_PLUGIN_ROOT}/skills/article-podcast/scripts/publish_episode.py \
  --mp3 <audio_path> \
  --title "<episode title>" \
  --description "<description>" \
  --duration <seconds> \
  --source-url "<original_url>" \
  --config ~/.openclaw/plugins/openclaw-plugin-article-podcast/config.json
```

Returns JSON: `{audio_url, feed_url}`

Publish episodes in order (episode 1 first) so they appear correctly in
podcast apps.

### Step 6: Report Results

Tell the user what was published:
- Number of episodes
- Total duration
- Episode titles
- Feed URL (for first-time users)

## Writing New Parsers

When parse_source.py returns `{"status": "no_parser"}`, write a new parser:

1. Create `${OPENCLAW_PLUGIN_ROOT}/skills/article-podcast/scripts/parsers/<name>.py`
2. It must have a `parse(source: str) -> dict` function
3. It must have a `main()` that accepts `--source` and prints JSON to stdout
4. Output must follow this contract:

```json
{
  "source_type": "<type>",
  "title": "<title>",
  "metadata": {"source_url": "<url>", "author": "<optional>"},
  "sections": [
    {"title": "<section title>", "text": "<full text>", "word_count": 1234, "index": 0}
  ],
  "total_words": 1234
}
```

5. Install any needed packages: `pip install <package>` (in the venv)
6. Add an entry to `parsers/_registry.json`
7. Call parse_source.py again

## Quick Mode (single article, no splitting)

For a simple single-URL podcast with no special instructions, you can
use the legacy background queue for faster turnaround:

```bash
python3 ${OPENCLAW_PLUGIN_ROOT}/skills/article-podcast/scripts/generate.py \
  --url "<article_url>" \
  --format "<interview|discussion|narrator|deep-dive>" \
  --length "<short|default|long>" \
  --enqueue \
  --notification-recipient "d4e31a04-c781-45d8-ad2c-bb826fc80574"
```

This queues the job for the background worker (~3-5 minutes, sends Signal
notification when done). Use this for simple single-article requests where
the user doesn't need splitting or custom orchestration.

## Format Options

- **interview**: Host asks questions, expert explains (best for technical content)
- **discussion**: Two co-hosts with different perspectives (news, opinion)
- **narrator**: Solo narrator (essays, stories, blogs)
- **deep-dive**: Auto-classifies based on content (default for quick mode)

## TTS Backend Details

The pipeline tries backends in order (configurable):

1. **Gemini 2.5 Flash** (default) -- best multi-speaker quality, 650 words/chunk
2. **Azure OpenAI TTS-HD** -- high quality, 4096 chars/request, 3 RPM limit
3. **Edge TTS** -- free, good quality, 10K chars/request

Each backend has its own voice pool. Voices are auto-selected with
recent-avoidance to prevent repetition across episodes.

## Error Handling

- **Source inaccessible:** Report to user, ask if paywalled or if they can provide the file directly
- **No parser found:** Write one (see "Writing New Parsers")
- **Transcript generation fails:** Retry the subagent with simplified instructions
- **TTS fails:** synthesize_chunk.py has built-in fallback chain
- **Publish fails:** Check AZURE_STORAGE_CONNECTION_STRING env var, retry

## Configuration

Required env vars on the worker machine:
- `GEMINI_API_KEY` -- for Gemini TTS
- `AZURE_STORAGE_CONNECTION_STRING` -- for Azure Blob publishing
- `AZURE_API_KEY` -- for Azure OpenAI TTS (optional, fallback)
