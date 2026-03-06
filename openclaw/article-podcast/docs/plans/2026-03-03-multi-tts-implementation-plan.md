# Multi-TTS Podcast Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace NotebookLM podcast generation with a two-stage pipeline (LLM script generation + multi-TTS audio synthesis) supporting Gemini 2.5 Flash, Azure OpenAI TTS-HD, and Edge TTS backends with dynamic voice selection.

**Architecture:** URL is fetched and classified, then Stage 1 generates a structured JSON transcript via OpenClaw's LLM, then Stage 2 synthesizes audio using a fallback chain (Gemini -> Azure TTS-HD -> Edge TTS). The existing publish/RSS/notification pipeline is untouched.

**Tech Stack:** Python 3.11+, trafilatura, google-genai, edge-tts, pydub, requests, mutagen

---

## File Map

```
plugin-article-podcast/
  skills/article-podcast/scripts/
    generate.py          # MODIFY: rewrite generate() to orchestrate stages
    scriptgen.py         # CREATE: content fetch + classify + LLM transcript
    synthesize.py        # CREATE: multi-backend TTS with fallback chain
    voices.py            # CREATE: voice pool management + history tracking
    worker.py            # UNCHANGED
    publish.py           # UNCHANGED
    feed.py              # UNCHANGED
    notifier.py          # UNCHANGED
    job_manager.py       # UNCHANGED
  tests/
    test_title_resolution.py  # MODIFY: update imports (title helpers move)
    test_scriptgen.py         # CREATE: script generation tests
    test_synthesize.py        # CREATE: TTS synthesis tests
    test_voices.py            # CREATE: voice selection tests
  requirements.txt            # MODIFY: swap notebooklm-py for new deps
```

---

### Task 1: Update Dependencies

**Files:**
- Modify: `requirements.txt`

**Step 1: Update requirements.txt**

Replace contents with:
```
trafilatura>=1.6.0
beautifulsoup4>=4.12.0
google-genai>=1.0.0
edge-tts>=6.1.0
pydub>=0.25.0
azure-storage-blob>=12.0.0
mutagen>=1.47.0
requests>=2.28.0
```

**Step 2: Verify the file**

Run: `cat plugin-article-podcast/requirements.txt`
Expected: `notebooklm-py` is gone, new deps are listed.

**Step 3: Commit**

```bash
git add plugin-article-podcast/requirements.txt
git commit -m "chore: replace notebooklm-py with multi-TTS dependencies

Swap out NotebookLM for trafilatura (article extraction), google-genai
(Gemini Flash TTS), edge-tts, and pydub (audio concatenation)."
```

---

### Task 2: Voice Pool Management (`voices.py`)

**Files:**
- Create: `plugin-article-podcast/skills/article-podcast/scripts/voices.py`
- Create: `plugin-article-podcast/tests/test_voices.py`

**Step 1: Write the failing tests**

Create `plugin-article-podcast/tests/test_voices.py`:

```python
"""Tests for voice pool management and selection."""

import json
import os
import sys
import tempfile

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"),
)

from voices import (
    VOICE_POOLS,
    pick_voices,
    record_voice_usage,
    load_voice_history,
)


def test_voice_pools_have_all_backends():
    assert "gemini" in VOICE_POOLS
    assert "azure-openai" in VOICE_POOLS
    assert "edge" in VOICE_POOLS


def test_each_pool_has_at_least_4_voices():
    for backend, pool in VOICE_POOLS.items():
        assert len(pool) >= 4, f"{backend} pool has only {len(pool)} voices"


def test_pick_voices_two_speaker_returns_two_distinct():
    v1, v2 = pick_voices("gemini", num_speakers=2)
    assert v1 != v2
    assert v1 in VOICE_POOLS["gemini"]
    assert v2 in VOICE_POOLS["gemini"]


def test_pick_voices_solo_returns_one():
    result = pick_voices("gemini", num_speakers=1)
    assert len(result) == 1
    assert result[0] in VOICE_POOLS["gemini"]


def test_pick_voices_avoids_recent(tmp_path):
    history_file = tmp_path / "voice_history.json"
    # Fill history with all but 2 voices for gemini
    pool = VOICE_POOLS["gemini"]
    # Record all but last 2 voices as recently used
    history = [pool[i] for i in range(len(pool) - 2)]
    history_file.write_text(json.dumps(history))
    v1, v2 = pick_voices(
        "gemini", num_speakers=2, history_path=str(history_file)
    )
    # Should strongly prefer the 2 unused voices
    assert v1 in pool
    assert v2 in pool
    assert v1 != v2


def test_pick_voices_works_with_no_history_file(tmp_path):
    history_file = tmp_path / "nonexistent.json"
    result = pick_voices("gemini", num_speakers=2, history_path=str(history_file))
    assert len(result) == 2


def test_record_voice_usage_creates_file(tmp_path):
    history_file = tmp_path / "voice_history.json"
    record_voice_usage(["Kore", "Puck"], history_path=str(history_file))
    data = json.loads(history_file.read_text())
    assert "Kore" in data
    assert "Puck" in data


def test_record_voice_usage_caps_history(tmp_path):
    history_file = tmp_path / "voice_history.json"
    # Write 20 entries
    history_file.write_text(json.dumps(["v" + str(i) for i in range(20)]))
    record_voice_usage(["new1", "new2"], history_path=str(history_file))
    data = json.loads(history_file.read_text())
    # Should keep last 10 entries (5 episodes * 2 voices) = 10, plus 2 new = 12, capped at 10
    assert len(data) <= 12
    assert "new1" in data
    assert "new2" in data


def test_pick_voices_with_override():
    result = pick_voices("gemini", num_speakers=2, override=["Kore", "Puck"])
    assert result == ["Kore", "Puck"]


def test_pick_voices_azure_backend():
    v1, v2 = pick_voices("azure-openai", num_speakers=2)
    assert v1 in VOICE_POOLS["azure-openai"]
    assert v2 in VOICE_POOLS["azure-openai"]
    assert v1 != v2


def test_pick_voices_edge_backend():
    v1, v2 = pick_voices("edge", num_speakers=2)
    assert v1 in VOICE_POOLS["edge"]
    assert v2 in VOICE_POOLS["edge"]
    assert v1 != v2
```

**Step 2: Run tests to verify they fail**

Run: `cd plugin-article-podcast && python -m pytest tests/test_voices.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'voices'`

**Step 3: Implement voices.py**

Create `plugin-article-podcast/skills/article-podcast/scripts/voices.py`:

```python
#!/usr/bin/env python3
"""Voice pool management and dynamic voice selection."""

import json
import random
from pathlib import Path
from typing import Optional

VOICE_POOLS = {
    "gemini": [
        "Aoede", "Charon", "Enceladus", "Fenrir",
        "Kore", "Leda", "Orbit", "Puck",
    ],
    "azure-openai": [
        "alloy", "ash", "ballad", "coral", "echo",
        "fable", "nova", "onyx", "sage", "shimmer",
        "verse", "marin", "cedar",
    ],
    "edge": [
        "en-US-JennyNeural", "en-US-AriaNeural", "en-US-SaraNeural",
        "en-US-GuyNeural", "en-US-DavisNeural", "en-US-TonyNeural",
        "en-GB-SoniaNeural", "en-GB-RyanNeural",
        "en-AU-NatashaNeural", "en-AU-WilliamNeural",
        "en-IN-NeerjaNeural", "en-IN-PrabhatNeural",
        "en-IE-EmilyNeural", "en-IE-ConnorNeural",
        "en-ZA-LeahNeural", "en-ZA-LukeNeural",
    ],
}

_DEFAULT_HISTORY_PATH = (
    Path.home() / ".openclaw" / "plugins"
    / "openclaw-plugin-article-podcast" / "voice_history.json"
)

MAX_HISTORY = 10  # Track last ~5 episodes (2 voices each)


def load_voice_history(history_path: Optional[str] = None) -> list[str]:
    """Load the list of recently used voice names."""
    path = Path(history_path) if history_path else _DEFAULT_HISTORY_PATH
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def record_voice_usage(
    voices: list[str], history_path: Optional[str] = None
) -> None:
    """Append voices to history and trim to MAX_HISTORY."""
    path = Path(history_path) if history_path else _DEFAULT_HISTORY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    history = load_voice_history(history_path)
    history.extend(voices)
    # Keep only the most recent entries
    history = history[-MAX_HISTORY:]
    path.write_text(json.dumps(history))


def pick_voices(
    backend: str,
    num_speakers: int,
    history_path: Optional[str] = None,
    override: Optional[list[str]] = None,
) -> list[str]:
    """Pick voices from the pool, preferring ones not recently used.

    Args:
        backend: "gemini", "azure-openai", or "edge"
        num_speakers: 1 for solo, 2 for dialogue
        history_path: path to voice_history.json (default: ~/.openclaw/...)
        override: if provided, return these voices directly

    Returns:
        List of voice names (length = num_speakers)
    """
    if override:
        return list(override)

    pool = list(VOICE_POOLS[backend])
    recent = set(load_voice_history(history_path))

    # Partition into unused and recently-used
    unused = [v for v in pool if v not in recent]
    used = [v for v in pool if v in recent]

    # Prefer unused voices, fall back to used if not enough
    candidates = unused if len(unused) >= num_speakers else pool

    selected = random.sample(candidates, min(num_speakers, len(candidates)))
    return selected
```

**Step 4: Run tests to verify they pass**

Run: `cd plugin-article-podcast && python -m pytest tests/test_voices.py -v`
Expected: All 11 tests PASS

**Step 5: Commit**

```bash
git add plugin-article-podcast/skills/article-podcast/scripts/voices.py \
       plugin-article-podcast/tests/test_voices.py
git commit -m "feat: add voice pool management with recent-avoidance

Dynamic voice selection from pools per TTS backend (Gemini, Azure
OpenAI, Edge TTS). Tracks last 5 episodes to avoid repetition.
Supports user override via explicit voice list."
```

---

### Task 3: Content Fetching & Classification (`scriptgen.py` - Part 1)

**Files:**
- Create: `plugin-article-podcast/skills/article-podcast/scripts/scriptgen.py`
- Create: `plugin-article-podcast/tests/test_scriptgen.py`

This task covers the content fetching and classification logic. The LLM prompt + transcript generation is Task 4.

**Step 1: Write failing tests for classification**

Create `plugin-article-podcast/tests/test_scriptgen.py`:

```python
"""Tests for script generation: content fetching and classification."""

import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"),
)

import pytest
from scriptgen import (
    classify_content, parse_transcript_response,
    FORMAT_INTERVIEW, FORMAT_DISCUSSION, FORMAT_NARRATOR,
)


# --- classify_content ---

def test_arxiv_url_gets_interview():
    fmt = classify_content("https://arxiv.org/abs/2401.12345", "Attention Is All You Need")
    assert fmt == FORMAT_INTERVIEW


def test_github_url_gets_interview():
    fmt = classify_content("https://github.com/org/repo", "Kubernetes Autoscaler Design")
    assert fmt == FORMAT_INTERVIEW


def test_acm_url_gets_interview():
    fmt = classify_content("https://dl.acm.org/doi/paper", "Database Query Optimization")
    assert fmt == FORMAT_INTERVIEW


def test_news_domain_gets_discussion():
    fmt = classify_content("https://www.nytimes.com/article", "Fed Raises Rates Again")
    assert fmt == FORMAT_DISCUSSION


def test_bbc_gets_discussion():
    fmt = classify_content("https://www.bbc.com/news/article", "Climate Summit Updates")
    assert fmt == FORMAT_DISCUSSION


def test_blog_gets_narrator():
    fmt = classify_content("https://paulgraham.com/think.html", "How to Think for Yourself")
    assert fmt == FORMAT_NARRATOR


def test_substack_gets_narrator():
    fmt = classify_content("https://someone.substack.com/p/my-take", "My Take on Remote Work")
    assert fmt == FORMAT_NARRATOR


def test_medium_gets_narrator():
    fmt = classify_content("https://medium.com/@user/my-essay", "Why I Left Big Tech")
    assert fmt == FORMAT_NARRATOR


def test_technical_keywords_in_title_get_interview():
    fmt = classify_content("https://example.com/post", "Distributed Database Algorithm Design")
    assert fmt == FORMAT_INTERVIEW


def test_generic_url_defaults_to_discussion():
    fmt = classify_content("https://example.com/page", "Some Random Topic")
    assert fmt == FORMAT_DISCUSSION


# --- parse_transcript_response ---

def test_parse_valid_json():
    raw = '{"title": "Test", "segments": []}'
    result = parse_transcript_response(raw)
    assert result["title"] == "Test"


def test_parse_json_with_markdown_fences():
    raw = '```json\n{"title": "Test", "segments": []}\n```'
    result = parse_transcript_response(raw)
    assert result["title"] == "Test"


def test_parse_malformed_json_raises():
    with pytest.raises(Exception):
        parse_transcript_response("not valid json at all")
```

**Step 2: Run tests to verify they fail**

Run: `cd plugin-article-podcast && python -m pytest tests/test_scriptgen.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scriptgen'`

**Step 3: Write the classification logic in scriptgen.py**

Create `plugin-article-podcast/skills/article-podcast/scripts/scriptgen.py`:

```python
#!/usr/bin/env python3
"""Stage 1: Fetch article content, classify, and generate podcast transcript."""

import json
import sys
from typing import Optional

import trafilatura

FORMAT_INTERVIEW = "interview"
FORMAT_DISCUSSION = "discussion"
FORMAT_NARRATOR = "narrator"

# Domain-based classification
TECHNICAL_DOMAINS = [
    "arxiv.org", "github.com", "engineering.", "eng.",
    "developer.", "devblogs.", "research.", "dl.acm.org",
    "ieeexplore.", "proceedings.", "openreview.net",
]

NEWS_DOMAINS = [
    "nytimes.com", "washingtonpost.com", "bbc.com", "bbc.co.uk",
    "cnn.com", "reuters.com", "apnews.com", "theguardian.com",
    "bloomberg.com", "ft.com", "wsj.com", "economist.com",
    "politico.com", "thehill.com", "npr.org",
]

OPINION_DOMAINS = [
    "substack.com", "medium.com", "paulgraham.com",
    "stratechery.com", "danluu.com", "blog.",
]

TECHNICAL_KEYWORDS = [
    "algorithm", "distributed", "kubernetes", "docker", "api",
    "microservice", "database", "compiler", "runtime", "latency",
    "throughput", "scalab", "concurren", "parallel", "machine learning",
    "neural", "transformer", "LLM", "GPU", "CPU", "memory",
    "cache", "protocol", "encryption", "authentication",
]


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def classify_content(url: str, title: str) -> str:
    """Classify content to pick a podcast format.

    Returns FORMAT_INTERVIEW, FORMAT_DISCUSSION, or FORMAT_NARRATOR.
    """
    text = (url + " " + title).lower()

    # Technical/academic -> interview
    if any(domain in text for domain in TECHNICAL_DOMAINS):
        return FORMAT_INTERVIEW
    if sum(1 for kw in TECHNICAL_KEYWORDS if kw.lower() in text) >= 2:
        return FORMAT_INTERVIEW

    # News -> two-host discussion
    if any(domain in text for domain in NEWS_DOMAINS):
        return FORMAT_DISCUSSION

    # Opinion/essay/blog -> solo narrator
    if any(domain in text for domain in OPINION_DOMAINS):
        return FORMAT_NARRATOR

    # Default: two-host discussion
    return FORMAT_DISCUSSION


def fetch_article(url: str) -> str:
    """Fetch and extract clean article text from a URL.

    Tries trafilatura first, falls back to requests + BeautifulSoup.
    """
    _log(f"Fetching article: {url}")

    # Primary: trafilatura
    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
        if text:
            _log(f"Extracted {len(text)} chars via trafilatura")
            return text

    # Fallback: requests + BeautifulSoup
    _log("trafilatura extraction failed, trying BeautifulSoup fallback")
    import requests as req
    from bs4 import BeautifulSoup

    resp = req.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # Remove script/style tags
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    if not text:
        raise RuntimeError(f"Failed to extract text from URL: {url}")
    _log(f"Extracted {len(text)} chars via BeautifulSoup fallback")
    return text


def build_transcript_prompt(
    article_text: str,
    fmt: str,
    source_url: str,
    length_minutes: Optional[int] = None,
) -> str:
    """Build the LLM prompt for generating a podcast transcript.

    Args:
        article_text: extracted article text
        fmt: FORMAT_INTERVIEW, FORMAT_DISCUSSION, or FORMAT_NARRATOR
        source_url: original article URL
        length_minutes: target length in minutes (None = auto based on article length)
    """
    # Estimate target length from article size if not specified
    if length_minutes is None:
        word_count = len(article_text.split())
        if word_count < 1000:
            length_minutes = 5
        elif word_count < 3000:
            length_minutes = 10
        elif word_count < 6000:
            length_minutes = 20
        elif word_count < 12000:
            length_minutes = 40
        else:
            length_minutes = 60

    # Approx words per minute of speech
    target_words = length_minutes * 150

    format_instructions = {
        FORMAT_INTERVIEW: (
            "Format: Interview between a curious host and a knowledgeable expert.\n"
            "The host asks thoughtful questions and the expert explains clearly.\n"
            "The host should push back on jargon and ask for real-world examples.\n"
            "Speaker names: Host and Expert."
        ),
        FORMAT_DISCUSSION: (
            "Format: Lively discussion between two co-hosts who have different perspectives.\n"
            "They should build on each other's points, occasionally disagree, and bring "
            "different angles to the topic. Keep it conversational and engaging.\n"
            "Speaker names: Alex and Sam."
        ),
        FORMAT_NARRATOR: (
            "Format: Solo narrator presenting the key ideas in an engaging, story-like way.\n"
            "Use vivid language, rhetorical questions, and a clear narrative arc.\n"
            "Speaker name: Narrator."
        ),
    }

    num_speakers_for_format = {
        FORMAT_INTERVIEW: 2,
        FORMAT_DISCUSSION: 2,
        FORMAT_NARRATOR: 1,
    }

    speakers_json = {
        FORMAT_INTERVIEW: [
            {"id": "S1", "role": "host"},
            {"id": "S2", "role": "expert"},
        ],
        FORMAT_DISCUSSION: [
            {"id": "S1", "role": "co-host"},
            {"id": "S2", "role": "co-host"},
        ],
        FORMAT_NARRATOR: [
            {"id": "S1", "role": "narrator"},
        ],
    }

    prompt = f"""You are a podcast script writer. Generate a natural, engaging podcast transcript from the following article.

{format_instructions[fmt]}

Target length: approximately {target_words} words ({length_minutes} minutes of speech).

IMPORTANT RULES:
- Write natural speech, not written prose. Use contractions, filler words sparingly, and conversational tone.
- Do NOT include stage directions, sound effects, or non-speech annotations.
- Each segment should be 1-4 sentences. Avoid monologues longer than ~50 words.
- Cover the key points of the article but make it accessible and interesting.
- Start with a brief, engaging hook -- do not say "welcome to the podcast."

Output ONLY valid JSON in this exact format (no markdown code fences, no commentary):
{{
  "title": "<catchy episode title, 5-10 words>",
  "format": "{fmt}",
  "speakers": {json.dumps(speakers_json[fmt])},
  "segments": [
    {{"speaker": "S1", "text": "..."}},
    {{"speaker": "S2", "text": "..."}}
  ],
  "source_url": "{source_url}",
  "estimated_duration_minutes": {length_minutes}
}}

Article content:
---
{article_text[:50000]}
---"""
    return prompt


def parse_transcript_response(llm_output: str) -> dict:
    """Parse the LLM response into a transcript dict.

    Handles cases where the LLM wraps JSON in markdown code fences.
    """
    text = llm_output.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)
```

**Step 4: Run tests to verify they pass**

Run: `cd plugin-article-podcast && python -m pytest tests/test_scriptgen.py -v`
Expected: All 13 tests PASS

**Step 5: Commit**

```bash
git add plugin-article-podcast/skills/article-podcast/scripts/scriptgen.py \
       plugin-article-podcast/tests/test_scriptgen.py
git commit -m "feat: add content classification and article fetching

Stage 1 of the two-stage pipeline. Classifies URLs into interview,
discussion, or narrator formats. Fetches article text via trafilatura.
Builds structured LLM prompts for transcript generation."
```

---

### Task 4: TTS Synthesis Engine (`synthesize.py`)

**Files:**
- Create: `plugin-article-podcast/skills/article-podcast/scripts/synthesize.py`
- Create: `plugin-article-podcast/tests/test_synthesize.py`

#### Key API Constraints Driving the Design

| Backend | Max Input | Max Audio Output | Rate Limit |
|---|---|---|---|
| **Gemini Flash TTS** | 8,192 tokens | ~5 min 27 sec (hard cutoff, no warning) | 10 RPM (free), 300 RPM (paid) |
| **Azure OpenAI TTS-HD** | 4,096 characters (hard error) | ~5-6 min | 3 RPM default (Azure) |
| **Edge TTS** | ~15K chars safe | ~10 min | No formal limit (throttle risk) |

All three backends need chunking for episodes longer than ~5 minutes. The chunking
strategy is:
- **Batch consecutive same-speaker segments** into chunks up to the backend's limit
- **Gemini:** additionally chunk into ~5-min blocks (est. ~750 words per block)
- **300ms silence** between speaker changes, **30ms crossfade** within same speaker
- **Rate limiting:** Azure calls sleep to stay under 3 RPM; Gemini respects per-tier RPM
- Generate intermediate audio as WAV (lossless), stitch, convert to MP3

**Step 1: Write failing tests**

Create `plugin-article-podcast/tests/test_synthesize.py`:

```python
"""Tests for TTS synthesis engine (unit tests with mocked backends)."""

import json
import os
import sys
import tempfile

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"),
)

from synthesize import (
    build_gemini_prompt,
    batch_segments,
    chunk_for_gemini,
    TTS_BACKENDS,
)


SAMPLE_TRANSCRIPT = {
    "title": "Test Episode",
    "format": "discussion",
    "speakers": [
        {"id": "S1", "role": "co-host"},
        {"id": "S2", "role": "co-host"},
    ],
    "segments": [
        {"speaker": "S1", "text": "Hello and welcome."},
        {"speaker": "S2", "text": "Great to be here."},
        {"speaker": "S1", "text": "Let's dive in."},
    ],
    "source_url": "https://example.com",
    "estimated_duration_minutes": 5,
}


def test_tts_backends_list():
    assert "gemini" in TTS_BACKENDS
    assert "azure-openai" in TTS_BACKENDS
    assert "edge" in TTS_BACKENDS


def test_build_gemini_prompt_two_speakers():
    prompt = build_gemini_prompt(SAMPLE_TRANSCRIPT["segments"], "discussion")
    # The prompt should contain the dialogue text
    assert "Hello and welcome" in prompt
    assert "Great to be here" in prompt


def test_build_gemini_prompt_solo():
    segments = [{"speaker": "S1", "text": "Once upon a time."}]
    prompt = build_gemini_prompt(segments, "narrator")
    assert "Once upon a time" in prompt


def test_build_gemini_prompt_uses_speaker_names():
    prompt = build_gemini_prompt(SAMPLE_TRANSCRIPT["segments"], "discussion")
    # Should map S1->Alex, S2->Sam for discussion format
    assert "Alex:" in prompt
    assert "Sam:" in prompt


# --- batch_segments tests ---

def test_batch_same_speaker_segments():
    segments = [
        {"speaker": "S1", "text": "Hello."},
        {"speaker": "S1", "text": "How are you?"},
        {"speaker": "S2", "text": "I'm fine."},
    ]
    batches = batch_segments(segments, max_chars=1000)
    # S1's two segments should be batched together
    assert len(batches) == 2
    assert batches[0]["speaker"] == "S1"
    assert "Hello." in batches[0]["text"]
    assert "How are you?" in batches[0]["text"]
    assert batches[1]["speaker"] == "S2"


def test_batch_respects_char_limit():
    segments = [
        {"speaker": "S1", "text": "A" * 3000},
        {"speaker": "S1", "text": "B" * 3000},
    ]
    batches = batch_segments(segments, max_chars=4096)
    # Each segment is 3000 chars; combined would be 6001 (with space).
    # Should split into 2 batches.
    assert len(batches) == 2


def test_batch_speaker_change_forces_new_batch():
    segments = [
        {"speaker": "S1", "text": "Hello."},
        {"speaker": "S2", "text": "Hi there."},
        {"speaker": "S1", "text": "How's it going?"},
    ]
    batches = batch_segments(segments, max_chars=1000)
    assert len(batches) == 3  # Each speaker change = new batch


def test_batch_empty_segments():
    assert batch_segments([], max_chars=4096) == []


def test_batch_oversized_single_segment():
    """A single segment larger than max_chars should be split."""
    segments = [{"speaker": "S1", "text": "Word. " * 1000}]  # ~6000 chars
    batches = batch_segments(segments, max_chars=2000)
    assert len(batches) >= 3
    for b in batches:
        assert len(b["text"]) <= 2000
        assert b["speaker"] == "S1"


# --- chunk_for_gemini tests ---

def test_chunk_for_gemini_short_transcript():
    """Short transcript should be a single chunk."""
    segments = [
        {"speaker": "S1", "text": "Hello."},
        {"speaker": "S2", "text": "Hi."},
    ]
    chunks = chunk_for_gemini(segments, max_words=750)
    assert len(chunks) == 1
    assert len(chunks[0]) == 2


def test_chunk_for_gemini_long_transcript():
    """Long transcript should be split into multiple chunks."""
    segments = []
    for i in range(100):
        speaker = "S1" if i % 2 == 0 else "S2"
        # Each segment ~20 words
        segments.append({"speaker": speaker, "text": "This is a test sentence with about twenty words in it for testing purposes. " * 1})
    chunks = chunk_for_gemini(segments, max_words=150)
    assert len(chunks) > 1
    # All segments should be accounted for
    total = sum(len(c) for c in chunks)
    assert total == 100


def test_chunk_for_gemini_preserves_order():
    segments = [
        {"speaker": "S1", "text": "First."},
        {"speaker": "S2", "text": "Second."},
        {"speaker": "S1", "text": "Third."},
    ]
    chunks = chunk_for_gemini(segments, max_words=750)
    flat = [seg for chunk in chunks for seg in chunk]
    assert flat[0]["text"] == "First."
    assert flat[1]["text"] == "Second."
    assert flat[2]["text"] == "Third."
```

**Step 2: Run tests to verify they fail**

Run: `cd plugin-article-podcast && python -m pytest tests/test_synthesize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synthesize'`

**Step 3: Implement synthesize.py**

Create `plugin-article-podcast/skills/article-podcast/scripts/synthesize.py`:

```python
#!/usr/bin/env python3
"""Stage 2: Multi-backend TTS audio synthesis with chunking and fallback."""

import io
import os
import sys
import tempfile
import time
import wave
from typing import Optional

import requests

TTS_BACKENDS = ["gemini", "azure-openai", "edge"]

# Speaker name mapping for Gemini prompts
_SPEAKER_NAMES = {
    "interview": {"S1": "Host", "S2": "Expert"},
    "discussion": {"S1": "Alex", "S2": "Sam"},
    "narrator": {"S1": "Narrator"},
}

# Backend-specific limits
GEMINI_MAX_WORDS_PER_CHUNK = 650       # ~4.3 min of speech (safety margin for 5:27 hard cutoff)
AZURE_MAX_CHARS_PER_REQUEST = 4096     # Hard API limit
EDGE_MAX_CHARS_PER_REQUEST = 10000     # Conservative safe limit
AZURE_RPM_LIMIT = 3                    # Default Azure rate limit
CROSSFADE_MS = 30                      # Crossfade between same-speaker chunks
SPEAKER_CHANGE_SILENCE_MS = 300        # Silence at speaker changes


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# --- Chunking utilities ---

def _split_oversized_text(text: str, max_chars: int) -> list[str]:
    """Split text that exceeds max_chars at sentence boundaries.

    Falls back to splitting at word boundaries if no sentence break fits.
    """
    if len(text) <= max_chars:
        return [text]

    import re
    # Split on sentence boundaries (period/exclamation/question followed by space)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""
    for sentence in sentences:
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= max_chars:
            current += " " + sentence
        else:
            chunks.append(current)
            current = sentence

    # If a single sentence is still too long, split at word boundaries
    if current:
        if len(current) <= max_chars:
            chunks.append(current)
        else:
            words = current.split()
            buf = ""
            for word in words:
                if not buf:
                    buf = word
                elif len(buf) + 1 + len(word) <= max_chars:
                    buf += " " + word
                else:
                    chunks.append(buf)
                    buf = word
            if buf:
                chunks.append(buf)

    return chunks


def batch_segments(
    segments: list[dict], max_chars: int
) -> list[dict]:
    """Batch consecutive same-speaker segments into chunks up to max_chars.

    Returns a list of {"speaker": str, "text": str} dicts where consecutive
    same-speaker segments are merged, respecting the character limit.
    Handles oversized single segments by splitting at sentence boundaries.
    """
    if not segments:
        return []

    batches = []
    current_speaker = segments[0]["speaker"]
    current_text = segments[0]["text"]

    for seg in segments[1:]:
        if seg["speaker"] == current_speaker:
            combined = current_text + " " + seg["text"]
            if len(combined) <= max_chars:
                current_text = combined
                continue
        # Speaker changed or char limit reached: flush current batch
        # Split oversized text if needed
        for chunk in _split_oversized_text(current_text, max_chars):
            batches.append({"speaker": current_speaker, "text": chunk})
        current_speaker = seg["speaker"]
        current_text = seg["text"]

    # Flush last batch (also handle oversized)
    for chunk in _split_oversized_text(current_text, max_chars):
        batches.append({"speaker": current_speaker, "text": chunk})
    return batches


def chunk_for_gemini(
    segments: list[dict], max_words: int = GEMINI_MAX_WORDS_PER_CHUNK
) -> list[list[dict]]:
    """Split transcript segments into ~5-min chunks for Gemini TTS.

    Each chunk is a list of segments that together contain <= max_words words.
    Chunks never split mid-segment.
    """
    chunks = []
    current_chunk = []
    current_words = 0

    for seg in segments:
        seg_words = len(seg["text"].split())
        if current_words + seg_words > max_words and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_words = 0
        current_chunk.append(seg)
        current_words += seg_words

    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def build_gemini_prompt(segments: list[dict], fmt: str) -> str:
    """Build a TTS prompt for Gemini from a list of segments.

    Gemini expects conversational text with speaker names matching the
    speaker_voice_configs.
    """
    names = _SPEAKER_NAMES.get(fmt, {"S1": "Speaker1", "S2": "Speaker2"})
    is_multi = len(set(seg["speaker"] for seg in segments)) > 1

    lines = []
    lines.append(f"TTS the following {'conversation' if is_multi else 'narration'}:")
    lines.append("")
    for seg in segments:
        name = names.get(seg["speaker"], seg["speaker"])
        lines.append(f"{name}: {seg['text']}")
    return "\n".join(lines)


def _wave_bytes(
    pcm_data: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2
) -> bytes:
    """Convert raw PCM data to WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def _stitch_audio_segments(
    audio_segments: list, speaker_changes: list[bool]
) -> "AudioSegment":
    """Stitch pydub AudioSegments with crossfade or silence at boundaries.

    Args:
        audio_segments: list of pydub AudioSegment objects
        speaker_changes: list of bools, same length as audio_segments.
            True if this segment starts a new speaker turn.
    """
    from pydub import AudioSegment as AS

    if not audio_segments:
        return AS.silent(duration=0)

    combined = audio_segments[0]
    for i in range(1, len(audio_segments)):
        if speaker_changes[i]:
            # Speaker change: insert silence gap
            combined += AS.silent(duration=SPEAKER_CHANGE_SILENCE_MS)
            combined += audio_segments[i]
        else:
            # Same speaker continuation: crossfade for smooth join
            if len(combined) > CROSSFADE_MS and len(audio_segments[i]) > CROSSFADE_MS:
                combined = combined.append(audio_segments[i], crossfade=CROSSFADE_MS)
            else:
                combined += audio_segments[i]
    return combined


# --- Error classification and retries ---

_FATAL_ERRORS = (
    "authentication", "unauthorized", "forbidden", "api key",
    "invalid_api_key", "permission",
)


def _is_fatal_error(error: Exception) -> bool:
    """Check if an error is fatal (no point retrying)."""
    msg = str(error).lower()
    return any(term in msg for term in _FATAL_ERRORS)


def _retry_with_backoff(fn, max_retries: int = 2, initial_wait: float = 2.0):
    """Call fn() with exponential backoff retries on transient errors."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as e:
            last_error = e
            if _is_fatal_error(e):
                raise  # Don't retry auth/permission errors
            if attempt < max_retries:
                wait = initial_wait * (2 ** attempt)
                _log(f"  Retry {attempt + 1}/{max_retries} after {wait:.1f}s: {e}")
                time.sleep(wait)
    raise last_error


# --- Backend implementations ---

def synthesize_gemini(transcript: dict, voices: list[str], config: dict) -> str:
    """Generate audio using Gemini 2.5 Flash TTS with chunking.

    Splits transcript into ~5-min chunks, generates each chunk separately
    with consistent voice assignments, then stitches with crossfade.
    """
    from google import genai
    from google.genai import types
    from pydub import AudioSegment

    _log(f"Gemini TTS: synthesizing with voices {voices}")

    api_key = os.environ.get(config.get("gemini_api_key_env", "GEMINI_API_KEY"), "")
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=api_key)

    fmt = transcript["format"]
    names = _SPEAKER_NAMES.get(fmt, {"S1": "Speaker1", "S2": "Speaker2"})

    # Build speaker voice configs (same for all chunks)
    speaker_configs = []
    for i, speaker in enumerate(transcript["speakers"]):
        voice_name = voices[i] if i < len(voices) else voices[0]
        name = names.get(speaker["id"], speaker["id"])
        speaker_configs.append(
            types.SpeakerVoiceConfig(
                speaker=name,
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name,
                    )
                ),
            )
        )

    if len(speaker_configs) == 1:
        speech_config = types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=voices[0],
                )
            )
        )
    else:
        speech_config = types.SpeechConfig(
            multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                speaker_voice_configs=speaker_configs,
            )
        )

    # Chunk the transcript into ~5-min blocks
    chunks = chunk_for_gemini(transcript["segments"])
    _log(f"Gemini TTS: split into {len(chunks)} chunks")

    audio_parts = []
    for ci, chunk_segments in enumerate(chunks):
        prompt = build_gemini_prompt(chunk_segments, fmt)
        _log(f"Gemini TTS: generating chunk {ci + 1}/{len(chunks)} "
             f"({len(chunk_segments)} segments, {len(prompt)} chars)")

        def _gemini_call():
            resp = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=speech_config,
                ),
            )
            return resp.candidates[0].content.parts[0].inline_data.data

        pcm_data = _retry_with_backoff(_gemini_call)
        wav_bytes = _wave_bytes(pcm_data)
        segment = AudioSegment.from_wav(io.BytesIO(wav_bytes))
        audio_parts.append(segment)

        # Rate limiting: 10 RPM free tier = 6s between requests
        if ci < len(chunks) - 1:
            time.sleep(7)  # Stay safely under 10 RPM free tier

    # Determine speaker changes at chunk boundaries by checking
    # the last segment of each chunk vs the first segment of the next
    speaker_changes = [True]  # First chunk always starts fresh
    for ci in range(1, len(chunks)):
        prev_last_speaker = chunks[ci - 1][-1]["speaker"]
        curr_first_speaker = chunks[ci][0]["speaker"]
        speaker_changes.append(prev_last_speaker != curr_first_speaker)
    combined = _stitch_audio_segments(audio_parts, speaker_changes)

    tmp_dir = tempfile.mkdtemp(prefix="podcast-")
    mp3_path = os.path.join(tmp_dir, "episode.mp3")
    combined.export(mp3_path, format="mp3", bitrate="192k")

    _log(f"Gemini TTS: wrote {os.path.getsize(mp3_path)} bytes, "
         f"duration {len(combined) / 1000:.1f}s")
    return mp3_path


def synthesize_azure_openai(transcript: dict, voices: list[str], config: dict) -> str:
    """Generate audio using Azure OpenAI TTS-HD with batching and rate limiting.

    Batches consecutive same-speaker segments up to 4,096 chars per request.
    Respects Azure's 3 RPM default rate limit with sleep between calls.
    """
    from pydub import AudioSegment

    endpoint = config.get(
        "azure_tts_endpoint",
        "https://varun-mmbhqa1x-swedencentral.cognitiveservices.azure.com"
        "/openai/deployments/tts-hd/audio/speech",
    )
    api_version = config.get("azure_tts_api_version", "2025-03-01-preview")
    api_key_env = config.get("azure_tts_api_key_env", "AZURE_API_KEY")
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        raise RuntimeError(f"Environment variable {api_key_env} not set")

    url = f"{endpoint}?api-version={api_version}"
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }

    # Map speaker IDs to voices
    speaker_voice_map = {}
    for i, speaker in enumerate(transcript["speakers"]):
        speaker_voice_map[speaker["id"]] = voices[i] if i < len(voices) else voices[0]

    # Batch segments to minimize API calls
    batches = batch_segments(transcript["segments"], max_chars=AZURE_MAX_CHARS_PER_REQUEST)
    _log(f"Azure TTS: {len(transcript['segments'])} segments -> {len(batches)} batches "
         f"(voices: {voices})")

    audio_parts = []
    speaker_changes = []
    prev_speaker = None
    request_times = []  # Track timestamps for rate limiting

    for idx, batch in enumerate(batches):
        voice = speaker_voice_map.get(batch["speaker"], voices[0])
        speaker_changes.append(batch["speaker"] != prev_speaker)
        prev_speaker = batch["speaker"]

        # Rate limiting: ensure we don't exceed 3 RPM
        now = time.time()
        request_times = [t for t in request_times if now - t < 60]
        if len(request_times) >= AZURE_RPM_LIMIT:
            wait = 60 - (now - request_times[0]) + 0.5
            _log(f"Azure TTS: rate limit hit, waiting {wait:.1f}s")
            time.sleep(wait)

        payload = {
            "model": "tts-hd",
            "input": batch["text"],
            "voice": voice,
        }

        def _azure_call():
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            r.raise_for_status()
            return r

        resp = _retry_with_backoff(_azure_call)
        request_times.append(time.time())

        segment_audio = AudioSegment.from_mp3(io.BytesIO(resp.content))
        audio_parts.append(segment_audio)

        if (idx + 1) % 5 == 0 or idx == len(batches) - 1:
            _log(f"Azure TTS: completed batch {idx + 1}/{len(batches)}")

    combined = _stitch_audio_segments(audio_parts, speaker_changes)

    tmp_dir = tempfile.mkdtemp(prefix="podcast-")
    mp3_path = os.path.join(tmp_dir, "episode.mp3")
    combined.export(mp3_path, format="mp3", bitrate="192k")

    _log(f"Azure TTS: wrote {os.path.getsize(mp3_path)} bytes, "
         f"duration {len(combined) / 1000:.1f}s")
    return mp3_path


async def _synthesize_edge_async(transcript: dict, voices: list[str]) -> str:
    """Internal async implementation for Edge TTS with batching."""
    import edge_tts
    from pydub import AudioSegment

    speaker_voice_map = {}
    for i, speaker in enumerate(transcript["speakers"]):
        speaker_voice_map[speaker["id"]] = voices[i] if i < len(voices) else voices[0]

    # Batch segments (Edge can handle larger chunks)
    batches = batch_segments(transcript["segments"], max_chars=EDGE_MAX_CHARS_PER_REQUEST)
    _log(f"Edge TTS: {len(transcript['segments'])} segments -> {len(batches)} batches "
         f"(voices: {voices})")

    audio_parts = []
    speaker_changes = []
    prev_speaker = None

    for idx, batch in enumerate(batches):
        voice = speaker_voice_map.get(batch["speaker"], voices[0])
        speaker_changes.append(batch["speaker"] != prev_speaker)
        prev_speaker = batch["speaker"]

        communicate = edge_tts.Communicate(batch["text"], voice)

        audio_bytes = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.write(chunk["data"])

        audio_bytes.seek(0)
        segment_audio = AudioSegment.from_mp3(audio_bytes)
        audio_parts.append(segment_audio)

        if (idx + 1) % 5 == 0 or idx == len(batches) - 1:
            _log(f"Edge TTS: completed batch {idx + 1}/{len(batches)}")

    combined = _stitch_audio_segments(audio_parts, speaker_changes)

    tmp_dir = tempfile.mkdtemp(prefix="podcast-")
    mp3_path = os.path.join(tmp_dir, "episode.mp3")
    combined.export(mp3_path, format="mp3", bitrate="192k")

    _log(f"Edge TTS: wrote {os.path.getsize(mp3_path)} bytes, "
         f"duration {len(combined) / 1000:.1f}s")
    return mp3_path


def synthesize_edge(transcript: dict, voices: list[str], config: dict) -> str:
    """Generate audio using Microsoft Edge TTS (free) with batching."""
    import asyncio
    return asyncio.run(_synthesize_edge_async(transcript, voices))


# --- Main synthesis entry point ---

def synthesize(
    transcript: dict,
    voices: list[str],
    backend: str,
    config: dict,
    fallback_order: Optional[list[str]] = None,
) -> tuple[str, str]:
    """Synthesize audio with fallback chain.

    Args:
        transcript: structured transcript dict
        voices: voice names for primary backend
        backend: primary backend ("gemini", "azure-openai", "edge")
        config: plugin config dict
        fallback_order: ordered list of backends to try

    Returns:
        Tuple of (audio_file_path, backend_used, voices_used)
    """
    from voices import pick_voices

    if fallback_order is None:
        fallback_order = [backend]

    backends = {
        "gemini": synthesize_gemini,
        "azure-openai": synthesize_azure_openai,
        "edge": synthesize_edge,
    }

    num_speakers = len(transcript["speakers"])
    last_error = None

    for be in fallback_order:
        fn = backends.get(be)
        if not fn:
            _log(f"Unknown backend: {be}, skipping")
            continue

        # Pick voices for this backend (primary voices are for the first backend)
        if be == fallback_order[0]:
            be_voices = voices
        else:
            be_voices = pick_voices(be, num_speakers)

        try:
            _log(f"Trying TTS backend: {be}")
            audio_path = fn(transcript, be_voices, config)
            return audio_path, be, be_voices
        except Exception as e:
            if _is_fatal_error(e):
                _log(f"Backend {be} fatal error (skipping retries): {e}")
            else:
                _log(f"Backend {be} failed: {e}")
            last_error = e
            continue

    raise RuntimeError(f"All TTS backends failed. Last error: {last_error}")
```

**Step 4: Run tests to verify they pass**

Run: `cd plugin-article-podcast && python -m pytest tests/test_synthesize.py -v`
Expected: All 14 tests PASS

**Step 5: Commit**

```bash
git add plugin-article-podcast/skills/article-podcast/scripts/synthesize.py \
       plugin-article-podcast/tests/test_synthesize.py
git commit -m "feat: add multi-backend TTS synthesis with chunking

Handles API limits for all three backends:
- Gemini: chunks transcript into ~5-min blocks (hard 5:27 cutoff)
- Azure: batches same-speaker segments to 4096 chars, rate-limits to 3 RPM
- Edge: batches to 10K chars per call
Audio stitching uses 300ms silence at speaker changes, 30ms crossfade
within same-speaker sections. Automatic fallback chain."
```

---

### Task 5: Rewrite `generate.py` to Orchestrate Both Stages

**Files:**
- Modify: `plugin-article-podcast/skills/article-podcast/scripts/generate.py`
- Modify: `plugin-article-podcast/tests/test_title_resolution.py`

**Step 1: Rewrite generate.py**

Replace the entire contents of `generate.py` with the new two-stage orchestrator. The key changes:
- Remove all NotebookLM imports and code
- Keep `is_technical()`, `get_duration_seconds()`, `_log()` helpers
- Remove the 6-step title cascade (LLM generates the title now)
- Keep `_is_url_or_filename()` and `_clean_filename_title()` as fallback title cleaners
- New `generate()` calls `scriptgen` then `synthesize`
- Keep the `main()` CLI interface and `--enqueue` behavior

New `generate.py`:

```python
#!/usr/bin/env python3
"""Generate a podcast episode from a URL using multi-TTS pipeline."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mutagen import File as MutagenFile


def get_duration_seconds(audio_path: str) -> int:
    """Get duration of an audio file in seconds (supports MP3, M4A, WAV)."""
    audio = MutagenFile(audio_path)
    if audio and audio.info.length > 0:
        return int(audio.info.length)
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", audio_path],
            capture_output=True, text=True, timeout=10,
        )
        return int(float(result.stdout.strip()))
    except Exception:
        return 0


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _is_url_or_filename(text: str) -> bool:
    """Check if text looks like a URL or raw filename rather than a title."""
    text = text.strip()
    if text.startswith(("http://", "https://", "ftp://")):
        return True
    if "." in text and " " not in text and text.split(".")[-1].lower() in (
        "pdf", "html", "htm", "txt", "md", "doc", "docx",
    ):
        return True
    return False


def _clean_filename_title(text: str) -> str:
    """Best-effort conversion of a filename/URL into a readable title."""
    import re
    from urllib.parse import urlparse, unquote

    if text.startswith(("http://", "https://")):
        path = urlparse(text).path
        text = unquote(path.rstrip("/").split("/")[-1])
    text = re.sub(r"\.(pdf|html?|txt|md|docx?)$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[-_]+", " ", text)
    text = text.strip().title()
    return text or "Untitled Episode"


def generate(
    url: str, fmt: str, length: str, instructions: str, config: dict,
    voice_override: list[str] | None = None,
) -> dict:
    """Generate podcast audio from a URL using the two-stage pipeline.

    Stage 1: Fetch article, classify content, generate transcript via LLM.
    Stage 2: Synthesize audio via TTS fallback chain.

    Args:
        voice_override: explicit voice names to use (skips random selection)

    Returns dict with: mp3_path, title, description, duration_seconds, source_url
    """
    from scriptgen import (
        fetch_article, classify_content, build_transcript_prompt,
        parse_transcript_response, FORMAT_INTERVIEW, FORMAT_DISCUSSION, FORMAT_NARRATOR,
    )
    from synthesize import synthesize
    from voices import pick_voices, record_voice_usage

    # --- Stage 1: Script Generation ---
    _log("=== Stage 1: Script Generation ===")

    # Fetch article
    article_text = fetch_article(url)

    # Classify content and pick format
    # Map old format names to new ones for backwards compat
    format_map = {
        "deep-dive": None,  # auto-classify
        "brief": None,      # auto-classify (length handled separately)
        "critique": FORMAT_INTERVIEW,
        "debate": FORMAT_DISCUSSION,
        "interview": FORMAT_INTERVIEW,
        "discussion": FORMAT_DISCUSSION,
        "narrator": FORMAT_NARRATOR,
    }
    podcast_format = format_map.get(fmt)
    if podcast_format is None:
        podcast_format = classify_content(url, article_text[:500])
    _log(f"Format: {podcast_format}")

    # Determine target length (supports extended episodes up to 1 hour+)
    length_map = {"short": 5, "default": 15, "long": None}
    length_minutes = length_map.get(length, 15)
    # "long" scales with article length (auto-detect in build_transcript_prompt)

    # Build prompt and call LLM
    prompt = build_transcript_prompt(
        article_text, podcast_format, url, length_minutes=length_minutes,
    )
    _log(f"Calling LLM for transcript ({len(prompt)} char prompt)...")

    # Call OpenClaw's LLM via subprocess
    # openclaw agent generates the transcript using its configured LLM routing
    try:
        result = subprocess.run(
            ["openclaw", "agent", "--json", "--prompt", prompt],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"LLM call failed: {result.stderr}")
        llm_output = result.stdout.strip()
        # openclaw agent --json returns {"response": "..."} wrapper
        try:
            wrapper = json.loads(llm_output)
            llm_text = wrapper.get("response", llm_output)
        except json.JSONDecodeError:
            llm_text = llm_output
    except subprocess.TimeoutExpired:
        raise RuntimeError("LLM call timed out after 300s")

    transcript = parse_transcript_response(llm_text)
    _log(f"Transcript: {len(transcript['segments'])} segments, "
         f"title={transcript['title']!r}")

    # Save transcript for debugging
    transcript_dir = Path(tempfile.mkdtemp(prefix="podcast-transcript-"))
    transcript_path = transcript_dir / "transcript.json"
    transcript_path.write_text(json.dumps(transcript, indent=2))
    _log(f"Transcript saved: {transcript_path}")

    # --- Stage 2: Audio Synthesis ---
    _log("=== Stage 2: Audio Synthesis ===")

    num_speakers = len(transcript["speakers"])
    fallback_order = config.get("tts_fallback_order", ["gemini", "azure-openai", "edge"])
    primary_backend = fallback_order[0] if fallback_order else "gemini"

    # Pick voices for primary backend
    voices = pick_voices(primary_backend, num_speakers, override=voice_override)
    _log(f"Voices: {voices} (backend: {primary_backend})")

    audio_path, backend_used, voices_used = synthesize(
        transcript=transcript,
        voices=voices,
        backend=primary_backend,
        config=config,
        fallback_order=fallback_order,
    )
    _log(f"Audio generated via {backend_used}: {audio_path}")

    # Record the ACTUAL voices used (may differ if fallback backend was used)
    record_voice_usage(voices_used)

    # Extract title and description
    title = transcript.get("title", "")
    if not title or _is_url_or_filename(title):
        title = _clean_filename_title(url)

    description = f"Podcast {podcast_format} about: {url}"
    duration = get_duration_seconds(audio_path)

    result = {
        "mp3_path": audio_path,
        "title": title,
        "description": description,
        "duration_seconds": duration,
        "source_url": url,
        "backend_used": backend_used,
        "format": podcast_format,
        "transcript_path": str(transcript_path),
    }

    # Clean up transcript temp dir (audio temp dir cleaned after publish)
    import shutil
    try:
        shutil.rmtree(transcript_dir, ignore_errors=True)
    except Exception:
        pass

    return result


def main():
    parser = argparse.ArgumentParser(description="Generate podcast from URL")
    parser.add_argument("--url", required=True, help="Article URL")
    parser.add_argument("--format", default="deep-dive",
                        choices=["deep-dive", "brief", "critique", "debate",
                                 "interview", "discussion", "narrator"])
    parser.add_argument("--length", default="long",
                        choices=["short", "default", "long"],
                        help="Audio length: short, default, or long (default: long)")
    parser.add_argument("--instructions", default="auto",
                        help="Custom instructions or 'auto' for content-based selection")
    parser.add_argument("--config", default=None,
                        help="Path to JSON config file with plugin settings")
    parser.add_argument("--enqueue", action="store_true",
                        help="Queue the job for background processing")
    parser.add_argument("--notification-account", default="+13603069264",
                        help="Signal account phone number for notifications")
    parser.add_argument("--notification-recipient", default=None,
                        help="Signal recipient UUID for notifications")
    parser.add_argument("--voices", default=None,
                        help="Comma-separated voice names to override auto-selection")
    args = parser.parse_args()

    config_path = args.config
    if config_path is None:
        config_path = str(
            Path.home() / ".openclaw" / "plugins"
            / "openclaw-plugin-article-podcast" / "config.json"
        )

    if args.enqueue:
        sys.path.insert(0, os.path.dirname(__file__))
        from job_manager import enqueue

        notification = None
        if args.notification_recipient:
            notification = {
                "type": "signal",
                "account": args.notification_account,
                "recipient": args.notification_recipient,
            }

        job_id = enqueue(
            url=args.url,
            fmt=args.format,
            length=args.length,
            instructions=args.instructions,
            config_path=config_path,
            notification=notification,
        )
        print(json.dumps({"job_id": job_id, "status": "queued"}))
        return

    config = {}
    if config_path and os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)

    voice_override = None
    if args.voices:
        voice_override = [v.strip() for v in args.voices.split(",")]

    result = generate(args.url, args.format, args.length, args.instructions, config,
                      voice_override=voice_override)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
```

**Step 2: Update test imports**

Modify `tests/test_title_resolution.py` -- the title helpers `_is_url_or_filename`, `_clean_filename_title` stay in generate.py, but `_title_from_summary` and `_title_from_fulltext` are no longer needed (LLM generates titles). Remove those tests and keep the ones for helpers that remain:

Remove tests for `_title_from_summary` and `_title_from_fulltext` (lines 11-16 imports, lines 63-137 tests). Keep tests for `_is_url_or_filename` and `_clean_filename_title`.

Updated `tests/test_title_resolution.py`:

```python
"""Tests for title resolution helpers in generate.py."""

import sys
import os

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"),
)

from generate import (
    _is_url_or_filename,
    _clean_filename_title,
)


# --- _is_url_or_filename ---

def test_detects_https_url():
    assert _is_url_or_filename("https://example.com/paper.pdf") is True


def test_detects_http_url():
    assert _is_url_or_filename("http://arxiv.org/abs/1234") is True


def test_detects_filename():
    assert _is_url_or_filename("neumann-btw2025.pdf") is True


def test_rejects_normal_title():
    assert _is_url_or_filename("Improving Unnesting of Complex Queries") is False


def test_rejects_title_with_colon():
    assert _is_url_or_filename("Spanner: Google's Database") is False


# --- _clean_filename_title ---

def test_clean_url_to_title():
    url = "https://example.com/papers/neumann-btw2025.pdf"
    assert _clean_filename_title(url) == "Neumann Btw2025"


def test_clean_filename_with_underscores():
    assert _clean_filename_title("my_great_paper.pdf") == "My Great Paper"


def test_clean_empty_returns_untitled():
    assert _clean_filename_title("") == "Untitled Episode"


def test_clean_url_with_path():
    url = "https://www.scs.stanford.edu/26wi-cs244c/sched/readings/causalsim.pdf"
    assert _clean_filename_title(url) == "Causalsim"
```

**Step 3: Run all tests**

Run: `cd plugin-article-podcast && python -m pytest tests/ -v`
Expected: All tests pass across test_title_resolution.py, test_voices.py, test_scriptgen.py, test_synthesize.py

**Step 4: Commit**

```bash
git add plugin-article-podcast/skills/article-podcast/scripts/generate.py \
       plugin-article-podcast/tests/test_title_resolution.py
git commit -m "feat: rewrite generate.py to use two-stage pipeline

Replace NotebookLM with: Stage 1 (scriptgen.py) fetches article and
generates transcript via OpenClaw LLM, Stage 2 (synthesize.py) converts
transcript to audio via Gemini/Azure/Edge TTS fallback chain.

Preserves CLI interface and --enqueue behavior. Adds --voices override.
Removes _title_from_summary and _title_from_fulltext (LLM generates
titles now). Keeps _is_url_or_filename and _clean_filename_title as
fallback title cleaners."
```

---

### Task 6: Update worker.py for New Return Fields

**Files:**
- Modify: `plugin-article-podcast/skills/article-podcast/scripts/worker.py`

**Step 1: Review what changed**

The new `generate()` returns additional fields: `backend_used`, `format`, `transcript_path`. The worker already passes `result` through to `mark_completed()`, so the extra fields flow through automatically. The `mp3_path` key is the same.

The only change needed: `generate()` is no longer async. Remove `asyncio.run()` wrapper.

**Step 2: Edit worker.py line 52**

Change:
```python
        result = asyncio.run(generate(url, fmt, length, instructions, config))
```
To:
```python
        result = generate(url, fmt, length, instructions, config)
```

Also remove the `import asyncio` on line 4 since it's no longer used.

**Step 3: Commit**

```bash
git add plugin-article-podcast/skills/article-podcast/scripts/worker.py
git commit -m "fix: remove asyncio.run from worker since generate() is now sync

The new two-stage pipeline is synchronous (subprocess calls to openclaw
agent for LLM, direct API calls for TTS)."
```

---

### Task 7: Integration Test -- End-to-End Local Test

**Files:**
- No new files -- this is a manual testing task

**Step 1: Install dependencies in a local venv**

```bash
cd plugin-article-podcast
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Step 2: Test article fetching and classification**

```bash
cd skills/article-podcast/scripts
python3 -c "
from scriptgen import fetch_article, classify_content
text = fetch_article('https://paulgraham.com/superlinear.html')
print(f'Fetched {len(text)} chars')
fmt = classify_content('https://paulgraham.com/superlinear.html', text[:500])
print(f'Format: {fmt}')
"
```

Expected: Fetches article text, classifies as `narrator` (opinion/blog domain).

**Step 3: Test Edge TTS synthesis (free, no API key needed)**

```bash
python3 -c "
from synthesize import synthesize_edge
transcript = {
    'title': 'Test',
    'format': 'discussion',
    'speakers': [{'id': 'S1', 'role': 'co-host'}, {'id': 'S2', 'role': 'co-host'}],
    'segments': [
        {'speaker': 'S1', 'text': 'Hey, have you read this new paper on transformers?'},
        {'speaker': 'S2', 'text': 'Yeah, it is really interesting. The key insight is about attention mechanisms.'},
        {'speaker': 'S1', 'text': 'Right, and they show it scales way better than expected.'},
    ],
    'source_url': 'https://example.com',
    'estimated_duration_minutes': 1,
}
path = synthesize_edge(transcript, ['en-US-JennyNeural', 'en-GB-RyanNeural'], {})
print(f'Audio: {path}')
"
```

Expected: Generates an MP3 file. Play it to verify two different voices alternate.

**Step 4: Test Gemini TTS (requires GEMINI_API_KEY)**

```bash
export GEMINI_API_KEY="your-key-here"
python3 -c "
from synthesize import synthesize_gemini
transcript = {
    'title': 'Test',
    'format': 'discussion',
    'speakers': [{'id': 'S1', 'role': 'co-host'}, {'id': 'S2', 'role': 'co-host'}],
    'segments': [
        {'speaker': 'S1', 'text': 'So what do you think about the new findings?'},
        {'speaker': 'S2', 'text': 'Honestly, I think it changes everything we thought about scaling laws.'},
    ],
    'source_url': 'https://example.com',
    'estimated_duration_minutes': 1,
}
path = synthesize_gemini(transcript, ['Kore', 'Puck'], {})
print(f'Audio: {path}')
"
```

Expected: Generates a WAV file with two distinct Gemini voices.

**Step 5: Test Azure OpenAI TTS (requires AZURE_API_KEY)**

```bash
export AZURE_API_KEY="your-key-here"
python3 -c "
from synthesize import synthesize_azure_openai
transcript = {
    'title': 'Test',
    'format': 'discussion',
    'speakers': [{'id': 'S1', 'role': 'co-host'}, {'id': 'S2', 'role': 'co-host'}],
    'segments': [
        {'speaker': 'S1', 'text': 'Welcome back. Today we are talking about distributed systems.'},
        {'speaker': 'S2', 'text': 'Great topic. The challenge is always consistency versus availability.'},
    ],
    'source_url': 'https://example.com',
    'estimated_duration_minutes': 1,
}
config = {
    'azure_tts_endpoint': 'https://varun-mmbhqa1x-swedencentral.cognitiveservices.azure.com/openai/deployments/tts-hd/audio/speech',
    'azure_tts_api_version': '2025-03-01-preview',
}
path = synthesize_azure_openai(transcript, ['nova', 'echo'], config)
print(f'Audio: {path}')
"
```

Expected: Generates an MP3 file with two Azure voices.

**Step 6: Commit test results**

No code to commit, but note results in a commit message:

```bash
git commit --allow-empty -m "test: verify multi-TTS pipeline locally

Tested: Edge TTS (free), Gemini Flash TTS, Azure OpenAI TTS-HD.
All three backends generate audio from transcript segments."
```

---

### Task 8: Deploy to Surface Pro

**Step 1: Rsync all changed files**

```bash
# Deploy to both locations
for FILE in generate.py scriptgen.py synthesize.py voices.py; do
  rsync -avz plugin-article-podcast/skills/article-podcast/scripts/$FILE \
    moltbot@100.107.15.52:~/.openclaw/extensions/openclaw-plugin-article-podcast/skills/article-podcast/scripts/$FILE

  rsync -avz plugin-article-podcast/skills/article-podcast/scripts/$FILE \
    moltbot@100.107.15.52:~/projects/openclaw-plugin-article-podcast/skills/article-podcast/scripts/$FILE
done

# Deploy updated requirements
rsync -avz plugin-article-podcast/requirements.txt \
  moltbot@100.107.15.52:~/.openclaw/extensions/openclaw-plugin-article-podcast/requirements.txt
rsync -avz plugin-article-podcast/requirements.txt \
  moltbot@100.107.15.52:~/projects/openclaw-plugin-article-podcast/requirements.txt
```

**Step 2: Install new dependencies on Surface Pro**

```bash
# ffmpeg is required by pydub for MP3 export
ssh moltbot@100.107.15.52 'which ffmpeg || echo "NEED TO INSTALL: sudo apt install ffmpeg"'

ssh moltbot@100.107.15.52 '
  cd ~/.openclaw/extensions/openclaw-plugin-article-podcast/skills/article-podcast/venv
  source bin/activate
  pip install trafilatura beautifulsoup4 google-genai edge-tts pydub
  pip uninstall -y notebooklm-py
'
```

**Step 3: Set up new environment variables**

```bash
ssh moltbot@100.107.15.52 '
  echo "GEMINI_API_KEY=your-key-here" >> ~/.config/article-podcast-worker/env
  echo "AZURE_API_KEY=your-key-here" >> ~/.config/article-podcast-worker/env
'
```

**Step 4: Restart the worker**

```bash
ssh moltbot@100.107.15.52 'systemctl --user restart article-podcast-worker.service'
```

**Step 5: Verify worker started**

```bash
ssh moltbot@100.107.15.52 'systemctl --user status article-podcast-worker.service'
ssh moltbot@100.107.15.52 'journalctl --user -u article-podcast-worker.service --since "1 min ago" --no-pager'
```

Expected: Worker is running and logs "Worker starting, polling every 30s"

**Step 6: Test end-to-end by queuing a job**

```bash
ssh moltbot@100.107.15.52 '
  cd ~/.openclaw/extensions/openclaw-plugin-article-podcast/skills/article-podcast/scripts
  source ../venv/bin/activate
  python3 generate.py --url "https://paulgraham.com/superlinear.html" \
    --format deep-dive --length short --enqueue \
    --notification-recipient d4e31a04-c781-45d8-ad2c-bb826fc80574
'
```

Then monitor:
```bash
ssh moltbot@100.107.15.52 'journalctl --user -u article-podcast-worker.service -f'
```

Expected: Worker picks up job, generates transcript via LLM, synthesizes audio, publishes to Azure, sends Signal notification.

---

## Codex Review Fixes Applied

The following issues were identified by Codex (gpt-5.3-codex) review and incorporated into this plan:

| # | Severity | Fix | Location |
|---|----------|-----|----------|
| 1 | Critical | `batch_segments()` splits oversized single segments at sentence boundaries | synthesize.py |
| 2 | Critical | Gemini word budget lowered from 750 to 650 (safety margin for 5:27 hard cutoff) | synthesize.py |
| 3 | Critical | Gemini stitching checks actual speaker at chunk boundaries instead of assuming same | synthesize.py |
| 4 | High | Azure auth header changed from `Authorization: Bearer` to `api-key: <key>` | synthesize.py |
| 5 | High | Gemini rate limit sleep increased from 2s to 7s (safe for 10 RPM free tier) | synthesize.py |
| 6 | High | Added `_retry_with_backoff()` with fatal/retryable error classification | synthesize.py |
| 7 | High | `--voices` CLI arg wired through `generate()` to `pick_voices(override=...)` | generate.py |
| 8 | Medium | `record_voice_usage()` now records actual backend voices, not primary-only | generate.py |
| 9 | Medium | Added trafilatura->BeautifulSoup fallback; length map scales to 60 min | scriptgen.py |
| 10 | Medium | Transcript temp dirs cleaned up; ffmpeg noted as runtime dependency | generate.py, deploy |
| 11 | Medium | Added tests: oversized segments, malformed JSON parsing, markdown fences | test files |

See consultation log: `.claude/phone-a-friend/2026-03-03-multi-tts-code-review.md`
