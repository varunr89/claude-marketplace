#!/usr/bin/env python3
"""Stage 1: Fetch article content, classify, and generate podcast transcript."""

import json
import sys
from typing import Optional

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
    import trafilatura
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
