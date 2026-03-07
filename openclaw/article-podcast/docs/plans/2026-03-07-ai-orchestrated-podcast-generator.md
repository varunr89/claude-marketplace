# AI-Orchestrated Podcast Generator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the article-podcast plugin so the AI agent orchestrates the full pipeline using individual tool scripts, with a self-extending parser registry for any source type.

**Architecture:** A thin `parse_source.py` dispatcher routes sources to parser scripts in `parsers/`. The AI agent (following SKILL.md) calls parse_source -> decides splitting -> dispatches subagents for transcript generation -> calls synthesize_chunk.py -> calls publish_episode.py. Existing `synthesize.py` and `publish.py` library code stays intact; new scripts are CLI wrappers.

**Tech Stack:** Python 3.12, PyMuPDF (fitz), ebooklib, python-docx, yt-dlp, trafilatura, BeautifulSoup4

---

## Task 1: Parser Contract and Registry

**Files:**
- Create: `skills/article-podcast/scripts/parsers/__init__.py`
- Create: `skills/article-podcast/scripts/parsers/_registry.json`
- Create: `skills/article-podcast/scripts/parsers/contract.py`
- Test: `tests/test_parser_contract.py`

**Step 1: Write the failing test**

```python
# tests/test_parser_contract.py
"""Tests for parser contract validation."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from parsers.contract import validate_parser_output


def test_valid_output_passes():
    data = {
        "source_type": "web",
        "title": "Test Article",
        "metadata": {"source_url": "https://example.com"},
        "sections": [
            {"title": "Section 1", "text": "Some content here.", "word_count": 4, "index": 0}
        ],
        "total_words": 4,
    }
    assert validate_parser_output(data) is True


def test_missing_sections_fails():
    data = {"source_type": "web", "title": "Test", "metadata": {}, "total_words": 0}
    assert validate_parser_output(data) is False


def test_empty_text_fails():
    data = {
        "source_type": "web",
        "title": "Test",
        "metadata": {},
        "sections": [{"title": "S1", "text": "", "word_count": 0, "index": 0}],
        "total_words": 0,
    }
    assert validate_parser_output(data) is False


def test_missing_title_fails():
    data = {
        "source_type": "web",
        "metadata": {},
        "sections": [{"title": "S1", "text": "Content", "word_count": 1, "index": 0}],
        "total_words": 1,
    }
    assert validate_parser_output(data) is False
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/varunr/projects/openclaw/plugin-article-podcast && python3 -m pytest tests/test_parser_contract.py -v`
Expected: FAIL -- `ModuleNotFoundError: No module named 'parsers'`

**Step 3: Write implementation**

```python
# skills/article-podcast/scripts/parsers/__init__.py
# Parser registry package
```

```python
# skills/article-podcast/scripts/parsers/contract.py
"""Parser output contract: all parsers must produce output matching this schema."""

REQUIRED_TOP_KEYS = {"source_type", "title", "metadata", "sections", "total_words"}
REQUIRED_SECTION_KEYS = {"title", "text", "word_count", "index"}


def validate_parser_output(data: dict) -> bool:
    """Validate that parser output conforms to the contract."""
    if not isinstance(data, dict):
        return False
    if not REQUIRED_TOP_KEYS.issubset(data.keys()):
        return False
    sections = data.get("sections")
    if not isinstance(sections, list) or len(sections) == 0:
        return False
    for section in sections:
        if not REQUIRED_SECTION_KEYS.issubset(section.keys()):
            return False
        if not section["text"].strip():
            return False
    return True
```

```json
// skills/article-podcast/scripts/parsers/_registry.json
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

**Step 4: Run test to verify it passes**

Run: `cd /Users/varunr/projects/openclaw/plugin-article-podcast && python3 -m pytest tests/test_parser_contract.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add skills/article-podcast/scripts/parsers/ tests/test_parser_contract.py
git commit -m "feat: add parser contract and registry skeleton"
```

---

## Task 2: parse_source.py Dispatcher

**Files:**
- Create: `skills/article-podcast/scripts/parse_source.py`
- Test: `tests/test_parse_source.py`

**Step 1: Write the failing test**

```python
# tests/test_parse_source.py
"""Tests for parse_source dispatcher."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from parse_source import detect_source_type, resolve_parser


def test_detect_pdf_file():
    assert detect_source_type("/path/to/book.pdf") == ("file_ext", ".pdf")


def test_detect_youtube_url():
    stype, val = detect_source_type("https://www.youtube.com/watch?v=abc123")
    assert stype == "url_pattern"
    assert "youtube.com" in val


def test_detect_youtube_short_url():
    stype, val = detect_source_type("https://youtu.be/abc123")
    assert stype == "url_pattern"
    assert "youtu.be" in val


def test_detect_epub_file():
    assert detect_source_type("/path/to/book.epub") == ("file_ext", ".epub")


def test_detect_docx_file():
    assert detect_source_type("/path/to/doc.docx") == ("file_ext", ".docx")


def test_detect_txt_file():
    assert detect_source_type("/path/to/notes.txt") == ("file_ext", ".txt")


def test_detect_web_url():
    stype, val = detect_source_type("https://example.com/article")
    assert stype == "fallback"


def test_resolve_parser_pdf():
    parser_path = resolve_parser("file_ext", ".pdf")
    assert parser_path.endswith("pdf.py")


def test_resolve_parser_fallback():
    parser_path = resolve_parser("fallback", "anything")
    assert parser_path.endswith("web.py")


def test_resolve_parser_no_match():
    result = resolve_parser("url_pattern", "notion.so")
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_parse_source.py -v`
Expected: FAIL -- `ModuleNotFoundError: No module named 'parse_source'`

**Step 3: Write implementation**

```python
# skills/article-podcast/scripts/parse_source.py
#!/usr/bin/env python3
"""Source dispatcher: detect source type, find matching parser, run it."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

PARSERS_DIR = Path(__file__).parent / "parsers"
REGISTRY_PATH = PARSERS_DIR / "_registry.json"


def _load_registry() -> list[dict]:
    with open(REGISTRY_PATH) as f:
        return json.load(f)["patterns"]


def detect_source_type(source: str) -> tuple[str, str]:
    """Detect source type from a URL or file path.

    Returns (type, value) where type is one of:
    - "file_ext": value is the extension (e.g., ".pdf")
    - "url_pattern": value is the matched domain
    - "fallback": value is the source itself
    """
    # Check if it's a file path (not a URL)
    if not source.startswith(("http://", "https://")):
        ext = Path(source).suffix.lower()
        if ext:
            return ("file_ext", ext)
        return ("fallback", source)

    # It's a URL -- check domain patterns
    parsed = urlparse(source)
    hostname = parsed.hostname or ""

    # Load registry and check url_pattern entries
    for entry in _load_registry():
        if entry["type"] != "url_pattern":
            continue
        domains = entry["match"].split("|")
        for domain in domains:
            if domain in hostname:
                return ("url_pattern", hostname)

    return ("fallback", source)


def resolve_parser(source_type: str, value: str) -> str | None:
    """Find the parser script for a given source type and value.

    Returns absolute path to parser script, or None if no match.
    """
    for entry in _load_registry():
        if entry["type"] == "fallback" and source_type == "fallback":
            return str(PARSERS_DIR / entry["parser"])

        if entry["type"] == source_type:
            if source_type == "file_ext":
                exts = [e.strip() for e in entry["match"].replace("*", "").split("|")]
                if value in exts:
                    return str(PARSERS_DIR / entry["parser"])
            elif source_type == "url_pattern":
                domains = entry["match"].split("|")
                if any(d in value for d in domains):
                    return str(PARSERS_DIR / entry["parser"])

    return None


def parse(source: str) -> dict:
    """Parse a source and return structured JSON.

    Detects source type, finds the matching parser, runs it, validates output.
    """
    source_type, value = detect_source_type(source)
    parser_path = resolve_parser(source_type, value)

    if parser_path is None:
        return {
            "status": "no_parser",
            "detected_type": value,
            "raw_input": source,
        }

    # Run the parser as a subprocess
    result = subprocess.run(
        [sys.executable, parser_path, "--source", source],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Parser {parser_path} failed: {result.stderr}")

    data = json.loads(result.stdout)

    from parsers.contract import validate_parser_output
    if not validate_parser_output(data):
        raise ValueError(f"Parser output from {parser_path} does not match contract")

    return data


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Parse any source into structured JSON")
    parser.add_argument("--source", required=True, help="URL or file path")
    args = parser.parse_args()

    result = parse(args.source)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_parse_source.py -v`
Expected: 10 PASSED

**Step 5: Commit**

```bash
git add skills/article-podcast/scripts/parse_source.py tests/test_parse_source.py
git commit -m "feat: add parse_source.py dispatcher with type detection"
```

---

## Task 3: Web Parser (extract from existing fetch_article)

**Files:**
- Create: `skills/article-podcast/scripts/parsers/web.py`
- Test: `tests/test_parser_web.py`

**Step 1: Write the failing test**

```python
# tests/test_parser_web.py
"""Tests for web parser."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

import subprocess

PARSER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts", "parsers", "web.py"
)


def test_web_parser_output_format(tmp_path):
    """Test that web parser produces valid contract output for a simple HTML file."""
    # Create a test HTML file served via file path won't work for trafilatura,
    # so we test the internal _extract_from_html function directly.
    from parsers.web import _extract_from_html

    html = """<html><head><title>Test Article</title></head>
    <body><article><h1>Test Article</h1><p>This is the first paragraph.</p>
    <p>This is the second paragraph with more content.</p></article></body></html>"""

    result = _extract_from_html(html, "https://example.com/test")
    assert result["source_type"] == "web"
    assert result["title"] == "Test Article"
    assert len(result["sections"]) == 1
    assert result["sections"][0]["word_count"] > 0
    assert result["total_words"] > 0


def test_web_parser_multi_heading_sections():
    from parsers.web import _extract_from_html

    html = """<html><head><title>Multi Section</title></head><body>
    <h1>Multi Section</h1>
    <h2>Part One</h2><p>Content of part one goes here with enough words.</p>
    <h2>Part Two</h2><p>Content of part two is also here with words.</p>
    </body></html>"""

    result = _extract_from_html(html, "https://example.com/multi")
    assert result["source_type"] == "web"
    # Should detect h2 sections
    assert len(result["sections"]) >= 2
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_parser_web.py -v`
Expected: FAIL -- `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# skills/article-podcast/scripts/parsers/web.py
#!/usr/bin/env python3
"""Web parser: extract article text from URLs using trafilatura/BeautifulSoup."""

import json
import re
import sys
from urllib.parse import urlparse


def _extract_from_html(html: str, url: str) -> dict:
    """Parse HTML and return structured output following parser contract."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
    if not title:
        title = urlparse(url).hostname or "Untitled"

    # Remove non-content tags
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Try to split by headings (h2 or h3)
    sections = []
    heading_tags = soup.find_all(["h2", "h3"])

    if heading_tags:
        for i, heading in enumerate(heading_tags):
            section_title = heading.get_text(strip=True)
            # Collect text until next heading
            parts = []
            for sibling in heading.next_siblings:
                if sibling.name in ("h2", "h3"):
                    break
                text = sibling.get_text(strip=True) if hasattr(sibling, "get_text") else str(sibling).strip()
                if text:
                    parts.append(text)
            text = " ".join(parts)
            if text.strip():
                wc = len(text.split())
                sections.append({"title": section_title, "text": text, "word_count": wc, "index": i})

    # Fallback: single section with all text
    if not sections:
        full_text = soup.get_text(separator="\n", strip=True)
        wc = len(full_text.split())
        sections = [{"title": title, "text": full_text, "word_count": wc, "index": 0}]

    total_words = sum(s["word_count"] for s in sections)

    return {
        "source_type": "web",
        "title": title,
        "metadata": {"source_url": url},
        "sections": sections,
        "total_words": total_words,
    }


def parse(source: str) -> dict:
    """Fetch URL and extract content."""
    import trafilatura
    import requests

    # Try trafilatura first for clean extraction
    downloaded = trafilatura.fetch_url(source)
    if downloaded:
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
        if text:
            wc = len(text.split())
            # trafilatura returns flat text, try to get title from HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(downloaded, "html.parser")
            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
            if not title:
                title = urlparse(source).hostname or "Untitled"

            return {
                "source_type": "web",
                "title": title,
                "metadata": {"source_url": source},
                "sections": [{"title": title, "text": text, "word_count": wc, "index": 0}],
                "total_words": wc,
            }

    # Fallback: requests + BeautifulSoup with section detection
    resp = requests.get(source, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return _extract_from_html(resp.text, source)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    print(json.dumps(parse(args.source), indent=2))


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_parser_web.py -v`
Expected: 2 PASSED

**Step 5: Commit**

```bash
git add skills/article-podcast/scripts/parsers/web.py tests/test_parser_web.py
git commit -m "feat: add web parser with heading-based section detection"
```

---

## Task 4: PDF Parser

**Files:**
- Create: `skills/article-podcast/scripts/parsers/pdf.py`
- Test: `tests/test_parser_pdf.py`

**Step 1: Write the failing test**

```python
# tests/test_parser_pdf.py
"""Tests for PDF parser."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from parsers.pdf import _split_by_bookmarks, _split_by_headings


def test_split_by_bookmarks():
    """Simulate bookmark-based splitting."""
    pages_text = {0: "Intro text", 1: "Chapter 1 content", 2: "More ch1", 3: "Chapter 2 content"}
    bookmarks = [
        {"title": "Introduction", "page": 0},
        {"title": "Chapter 1: Basics", "page": 1},
        {"title": "Chapter 2: Advanced", "page": 3},
    ]
    sections = _split_by_bookmarks(pages_text, bookmarks, total_pages=4)
    assert len(sections) == 3
    assert sections[0]["title"] == "Introduction"
    assert sections[1]["title"] == "Chapter 1: Basics"
    assert "More ch1" in sections[1]["text"]
    assert sections[2]["title"] == "Chapter 2: Advanced"


def test_split_by_headings_fallback():
    """When no bookmarks, split by detected heading patterns in text."""
    full_text = (
        "CHAPTER 1\nIntroduction to the topic with some text.\n\n"
        "CHAPTER 2\nMore advanced material goes here.\n\n"
        "CHAPTER 3\nFinal conclusions and summary."
    )
    sections = _split_by_headings(full_text)
    assert len(sections) == 3
    assert "Introduction" in sections[0]["text"]


def test_single_section_when_no_structure():
    """No bookmarks, no heading patterns -> single section."""
    full_text = "Just a regular document with no chapters or headings at all. " * 50
    sections = _split_by_headings(full_text)
    assert len(sections) == 1
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_parser_pdf.py -v`
Expected: FAIL -- `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# skills/article-podcast/scripts/parsers/pdf.py
#!/usr/bin/env python3
"""PDF parser: extract text with chapter detection via bookmarks or heading patterns."""

import json
import re
import sys


def _split_by_bookmarks(pages_text: dict[int, str], bookmarks: list[dict], total_pages: int) -> list[dict]:
    """Split PDF text using bookmark/TOC entries.

    Args:
        pages_text: {page_number: text} mapping
        bookmarks: [{"title": str, "page": int}, ...]
        total_pages: total number of pages
    """
    sections = []
    for i, bm in enumerate(bookmarks):
        start_page = bm["page"]
        end_page = bookmarks[i + 1]["page"] if i + 1 < len(bookmarks) else total_pages

        text_parts = []
        for p in range(start_page, end_page):
            if p in pages_text:
                text_parts.append(pages_text[p])

        text = "\n".join(text_parts).strip()
        wc = len(text.split()) if text else 0
        sections.append({"title": bm["title"], "text": text, "word_count": wc, "index": i})

    return [s for s in sections if s["text"]]


CHAPTER_PATTERN = re.compile(
    r"^(CHAPTER\s+\d+|Chapter\s+\d+|PART\s+[IVXLCDM\d]+|Part\s+[IVXLCDM\d]+)\b",
    re.MULTILINE,
)


def _split_by_headings(full_text: str) -> list[dict]:
    """Split text by detected heading patterns (CHAPTER 1, Part II, etc.)."""
    matches = list(CHAPTER_PATTERN.finditer(full_text))

    if len(matches) < 2:
        wc = len(full_text.split())
        return [{"title": "Full Document", "text": full_text.strip(), "word_count": wc, "index": 0}]

    sections = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        title = match.group(0).strip()
        text = full_text[start:end].strip()
        # Remove the heading line itself from the text body
        lines = text.split("\n", 1)
        body = lines[1].strip() if len(lines) > 1 else text
        wc = len(body.split())
        sections.append({"title": title, "text": body, "word_count": wc, "index": i})

    return [s for s in sections if s["text"]]


def parse(source: str) -> dict:
    """Extract text and structure from a PDF file."""
    import fitz  # PyMuPDF

    doc = fitz.open(source)

    # Extract title from metadata
    meta = doc.metadata or {}
    title = meta.get("title", "").strip()
    author = meta.get("author", "").strip()

    # Extract text per page
    pages_text = {}
    for i, page in enumerate(doc):
        pages_text[i] = page.get_text()

    # Try bookmark-based splitting first
    toc = doc.get_toc()  # [[level, title, page], ...]
    bookmarks = [{"title": entry[1], "page": entry[2] - 1} for entry in toc if entry[0] <= 2]

    if bookmarks:
        sections = _split_by_bookmarks(pages_text, bookmarks, len(doc))
    else:
        full_text = "\n".join(pages_text.get(i, "") for i in range(len(doc)))
        sections = _split_by_headings(full_text)

    if not title:
        # Try first line of first page
        first_page = pages_text.get(0, "")
        first_line = first_page.strip().split("\n")[0].strip() if first_page else ""
        title = first_line[:100] if first_line else source.split("/")[-1]

    total_words = sum(s["word_count"] for s in sections)
    doc.close()

    return {
        "source_type": "pdf",
        "title": title,
        "metadata": {"author": author, "source_url": source},
        "sections": sections,
        "total_words": total_words,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    print(json.dumps(parse(args.source), indent=2))


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_parser_pdf.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add skills/article-podcast/scripts/parsers/pdf.py tests/test_parser_pdf.py
git commit -m "feat: add PDF parser with bookmark and heading-based chapter detection"
```

---

## Task 5: YouTube Parser

**Files:**
- Create: `skills/article-podcast/scripts/parsers/youtube.py`
- Test: `tests/test_parser_youtube.py`

**Step 1: Write the failing test**

```python
# tests/test_parser_youtube.py
"""Tests for YouTube parser."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from parsers.youtube import _parse_vtt, _is_playlist_url, _extract_video_id


def test_parse_vtt_cleans_timestamps():
    vtt = """WEBVTT

00:00:00.000 --> 00:00:05.000
Hello world this is a test.

00:00:05.000 --> 00:00:10.000
Hello world this is a test.

00:00:10.000 --> 00:00:15.000
Another line of content here.
"""
    text = _parse_vtt(vtt)
    assert "Hello world this is a test." in text
    assert "Another line of content here." in text
    assert "-->" not in text
    # Should deduplicate consecutive identical lines
    assert text.count("Hello world this is a test.") == 1


def test_is_playlist_url():
    assert _is_playlist_url("https://www.youtube.com/watch?v=abc&list=PLxyz") is True
    assert _is_playlist_url("https://www.youtube.com/playlist?list=PLxyz") is True
    assert _is_playlist_url("https://www.youtube.com/watch?v=abc") is False
    assert _is_playlist_url("https://youtu.be/abc") is False


def test_extract_video_id():
    assert _extract_video_id("https://www.youtube.com/watch?v=abc123") == "abc123"
    assert _extract_video_id("https://youtu.be/abc123") == "abc123"
    assert _extract_video_id("https://youtube.com/watch?v=abc123&t=10") == "abc123"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_parser_youtube.py -v`
Expected: FAIL -- `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# skills/article-podcast/scripts/parsers/youtube.py
#!/usr/bin/env python3
"""YouTube parser: extract captions from single videos or playlists via yt-dlp."""

import json
import os
import re
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlparse


def _extract_video_id(url: str) -> str | None:
    """Extract video ID from a YouTube URL."""
    parsed = urlparse(url)
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/")
    qs = parse_qs(parsed.query)
    return qs.get("v", [None])[0]


def _is_playlist_url(url: str) -> bool:
    """Check if URL is a YouTube playlist."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "list" in qs:
        return True
    if "/playlist" in parsed.path:
        return True
    return False


def _parse_vtt(vtt_content: str) -> str:
    """Parse VTT subtitle content into clean text, deduplicating repeated lines."""
    lines = []
    prev_line = ""
    for line in vtt_content.split("\n"):
        line = line.strip()
        # Skip VTT header, timestamps, empty lines
        if not line or line == "WEBVTT" or "-->" in line or re.match(r"^\d+$", line):
            continue
        # Remove VTT tags
        line = re.sub(r"<[^>]+>", "", line)
        if line and line != prev_line:
            lines.append(line)
            prev_line = line
    return " ".join(lines)


def _download_captions(video_url: str, work_dir: str) -> tuple[str, str]:
    """Download auto-captions for a video. Returns (title, transcript_text)."""
    # Get video info first
    info_result = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-download", video_url],
        capture_output=True, text=True, timeout=30,
    )
    title = "Untitled Video"
    if info_result.returncode == 0:
        info = json.loads(info_result.stdout)
        title = info.get("title", title)

    # Download captions
    result = subprocess.run(
        ["yt-dlp", "--write-auto-sub", "--sub-lang", "en,en-US",
         "--skip-download", "--sub-format", "vtt",
         "-o", os.path.join(work_dir, "%(id)s"), video_url],
        capture_output=True, text=True, timeout=60,
    )

    # Find the VTT file
    vtt_files = [f for f in os.listdir(work_dir) if f.endswith(".vtt")]
    if not vtt_files:
        raise RuntimeError(f"No captions found for {video_url}")

    with open(os.path.join(work_dir, vtt_files[0])) as f:
        vtt_content = f.read()

    return title, _parse_vtt(vtt_content)


def _list_playlist_videos(playlist_url: str) -> list[dict]:
    """List all videos in a playlist. Returns [{"url": ..., "title": ...}, ...]."""
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--dump-json", playlist_url],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to list playlist: {result.stderr}")

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        info = json.loads(line)
        vid_url = f"https://www.youtube.com/watch?v={info['id']}"
        videos.append({"url": vid_url, "title": info.get("title", "Untitled")})
    return videos


def parse(source: str) -> dict:
    """Extract captions from YouTube video or playlist."""
    with tempfile.TemporaryDirectory(prefix="yt-parse-") as work_dir:
        if _is_playlist_url(source):
            videos = _list_playlist_videos(source)
            # Get playlist title from first result's playlist field
            result = subprocess.run(
                ["yt-dlp", "--dump-json", "--no-download", "--playlist-items", "1", source],
                capture_output=True, text=True, timeout=30,
            )
            playlist_title = "YouTube Playlist"
            if result.returncode == 0:
                info = json.loads(result.stdout)
                playlist_title = info.get("playlist_title", info.get("playlist", playlist_title))

            sections = []
            for i, video in enumerate(videos):
                try:
                    title, text = _download_captions(video["url"], work_dir)
                    wc = len(text.split())
                    sections.append({
                        "title": title, "text": text,
                        "word_count": wc, "index": i,
                    })
                except Exception as e:
                    print(f"Warning: skipping {video['title']}: {e}", file=sys.stderr)

            total_words = sum(s["word_count"] for s in sections)
            return {
                "source_type": "youtube_playlist",
                "title": playlist_title,
                "metadata": {"source_url": source, "video_count": len(videos)},
                "sections": sections,
                "total_words": total_words,
            }
        else:
            title, text = _download_captions(source, work_dir)
            wc = len(text.split())
            return {
                "source_type": "youtube",
                "title": title,
                "metadata": {"source_url": source},
                "sections": [{"title": title, "text": text, "word_count": wc, "index": 0}],
                "total_words": wc,
            }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    print(json.dumps(parse(args.source), indent=2))


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_parser_youtube.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add skills/article-podcast/scripts/parsers/youtube.py tests/test_parser_youtube.py
git commit -m "feat: add YouTube parser with VTT caption extraction and playlist support"
```

---

## Task 6: EPUB, DOCX, and Text Parsers

**Files:**
- Create: `skills/article-podcast/scripts/parsers/epub.py`
- Create: `skills/article-podcast/scripts/parsers/docx.py`
- Create: `skills/article-podcast/scripts/parsers/text.py`
- Test: `tests/test_parser_epub.py`
- Test: `tests/test_parser_docx.py`
- Test: `tests/test_parser_text.py`

**Step 1: Write the failing tests**

```python
# tests/test_parser_text.py
"""Tests for plain text parser."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from parsers.text import parse


def test_plain_text_single_section(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("Just a simple document with no structure at all. " * 20)
    result = parse(str(f))
    assert result["source_type"] == "text"
    assert len(result["sections"]) == 1
    assert result["total_words"] > 0


def test_markdown_heading_sections(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# My Document\n\n## Section One\n\nContent one.\n\n## Section Two\n\nContent two.\n")
    result = parse(str(f))
    assert result["source_type"] == "text"
    assert len(result["sections"]) >= 2
```

```python
# tests/test_parser_docx.py
"""Tests for DOCX parser internal helpers."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from parsers.docx import _group_by_headings


def test_group_by_headings():
    paragraphs = [
        {"style": "Heading 1", "text": "Chapter One"},
        {"style": "Normal", "text": "First paragraph of chapter one."},
        {"style": "Normal", "text": "Second paragraph."},
        {"style": "Heading 1", "text": "Chapter Two"},
        {"style": "Normal", "text": "Content of chapter two."},
    ]
    sections = _group_by_headings(paragraphs)
    assert len(sections) == 2
    assert sections[0]["title"] == "Chapter One"
    assert "First paragraph" in sections[0]["text"]
    assert sections[1]["title"] == "Chapter Two"
```

```python
# tests/test_parser_epub.py
"""Tests for EPUB parser internal helpers."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from parsers.epub import _html_to_text


def test_html_to_text_strips_tags():
    html = "<html><body><h1>Title</h1><p>Content here.</p></body></html>"
    text = _html_to_text(html)
    assert "Content here." in text
    assert "<" not in text
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_parser_text.py tests/test_parser_docx.py tests/test_parser_epub.py -v`
Expected: FAIL -- `ModuleNotFoundError`

**Step 3: Write implementations**

```python
# skills/article-podcast/scripts/parsers/text.py
#!/usr/bin/env python3
"""Plain text and markdown parser."""

import json
import re
import sys
from pathlib import Path


def parse(source: str) -> dict:
    """Parse a plain text or markdown file."""
    path = Path(source)
    content = path.read_text(encoding="utf-8", errors="replace")
    title = path.stem.replace("-", " ").replace("_", " ").title()

    # Try markdown heading-based splitting
    sections = []
    if path.suffix.lower() == ".md":
        heading_pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
        matches = list(heading_pattern.finditer(content))
        if len(matches) >= 2:
            for i, match in enumerate(matches):
                start = match.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
                section_title = match.group(1).strip()
                text = content[start:end].strip()
                wc = len(text.split())
                if text:
                    sections.append({"title": section_title, "text": text, "word_count": wc, "index": i})

    if not sections:
        wc = len(content.split())
        sections = [{"title": title, "text": content.strip(), "word_count": wc, "index": 0}]

    total_words = sum(s["word_count"] for s in sections)
    return {
        "source_type": "text",
        "title": title,
        "metadata": {"source_url": source},
        "sections": sections,
        "total_words": total_words,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    print(json.dumps(parse(args.source), indent=2))


if __name__ == "__main__":
    main()
```

```python
# skills/article-podcast/scripts/parsers/docx.py
#!/usr/bin/env python3
"""DOCX parser: extract text with heading-based section detection."""

import json
import sys


def _group_by_headings(paragraphs: list[dict]) -> list[dict]:
    """Group paragraphs by heading styles.

    Args:
        paragraphs: [{"style": "Heading 1", "text": "..."}, ...]
    """
    sections = []
    current_title = None
    current_parts = []

    for para in paragraphs:
        if para["style"] and "heading" in para["style"].lower():
            if current_title is not None and current_parts:
                text = "\n".join(current_parts)
                wc = len(text.split())
                sections.append({"title": current_title, "text": text, "word_count": wc, "index": len(sections)})
            current_title = para["text"]
            current_parts = []
        elif para["text"].strip():
            current_parts.append(para["text"])

    # Last section
    if current_title is not None and current_parts:
        text = "\n".join(current_parts)
        wc = len(text.split())
        sections.append({"title": current_title, "text": text, "word_count": wc, "index": len(sections)})

    return sections


def parse(source: str) -> dict:
    """Parse a DOCX file."""
    from docx import Document

    doc = Document(source)
    title = doc.core_properties.title or source.split("/")[-1].replace(".docx", "")
    author = doc.core_properties.author or ""

    paragraphs = []
    for para in doc.paragraphs:
        paragraphs.append({"style": para.style.name if para.style else "", "text": para.text})

    sections = _group_by_headings(paragraphs)

    if not sections:
        full_text = "\n".join(p["text"] for p in paragraphs if p["text"].strip())
        wc = len(full_text.split())
        sections = [{"title": title, "text": full_text, "word_count": wc, "index": 0}]

    total_words = sum(s["word_count"] for s in sections)
    return {
        "source_type": "docx",
        "title": title,
        "metadata": {"author": author, "source_url": source},
        "sections": sections,
        "total_words": total_words,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    print(json.dumps(parse(args.source), indent=2))


if __name__ == "__main__":
    main()
```

```python
# skills/article-podcast/scripts/parsers/epub.py
#!/usr/bin/env python3
"""EPUB parser: extract text with chapter detection."""

import json
import sys


def _html_to_text(html: str) -> str:
    """Strip HTML tags and return plain text."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def parse(source: str) -> dict:
    """Parse an EPUB file."""
    import ebooklib
    from ebooklib import epub

    book = epub.read_epub(source)
    title = book.get_metadata("DC", "title")
    title = title[0][0] if title else source.split("/")[-1].replace(".epub", "")
    author_meta = book.get_metadata("DC", "creator")
    author = author_meta[0][0] if author_meta else ""

    sections = []
    for i, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
        html = item.get_content().decode("utf-8", errors="replace")
        text = _html_to_text(html)
        if not text.strip() or len(text.split()) < 20:
            continue
        # Try to extract chapter title from first heading or first line
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.find(["h1", "h2", "h3"])
        section_title = heading.get_text(strip=True) if heading else text.split("\n")[0][:80]
        wc = len(text.split())
        sections.append({"title": section_title, "text": text, "word_count": wc, "index": len(sections)})

    total_words = sum(s["word_count"] for s in sections)
    return {
        "source_type": "epub",
        "title": title,
        "metadata": {"author": author, "source_url": source},
        "sections": sections,
        "total_words": total_words,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    print(json.dumps(parse(args.source), indent=2))


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_parser_text.py tests/test_parser_docx.py tests/test_parser_epub.py -v`
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add skills/article-podcast/scripts/parsers/text.py skills/article-podcast/scripts/parsers/docx.py skills/article-podcast/scripts/parsers/epub.py tests/test_parser_text.py tests/test_parser_docx.py tests/test_parser_epub.py
git commit -m "feat: add EPUB, DOCX, and plain text parsers"
```

---

## Task 7: synthesize_chunk.py CLI Wrapper

**Files:**
- Create: `skills/article-podcast/scripts/synthesize_chunk.py`
- Test: manual -- calls existing `synthesize()` which is already tested

**Step 1: Write implementation**

```python
# skills/article-podcast/scripts/synthesize_chunk.py
#!/usr/bin/env python3
"""CLI wrapper for TTS synthesis. Called by the AI agent as a tool."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from synthesize import synthesize
from generate import get_duration_seconds


def main():
    parser = argparse.ArgumentParser(description="Synthesize audio from a transcript JSON")
    parser.add_argument("--transcript", required=True, help="Path to transcript JSON file")
    parser.add_argument("--backend", default="gemini", choices=["gemini", "azure-openai", "edge"],
                        help="TTS backend to use (default: gemini)")
    parser.add_argument("--voices", default=None,
                        help="Comma-separated voice names (default: auto-select)")
    parser.add_argument("--config", default=None, help="Path to JSON config file")
    parser.add_argument("--fallback", default=None,
                        help="Comma-separated fallback backend order (default: backend only)")
    args = parser.parse_args()

    # Load transcript
    with open(args.transcript) as f:
        transcript = json.load(f)

    # Load config
    config = {}
    if args.config and os.path.exists(args.config):
        with open(args.config) as f:
            config = json.load(f)

    # Resolve voices
    voices = None
    if args.voices:
        voices = [v.strip() for v in args.voices.split(",")]
    else:
        from voices import pick_voices
        num_speakers = len(transcript.get("speakers", [{"id": "S1"}, {"id": "S2"}]))
        voices = pick_voices(args.backend, num_speakers)

    # Resolve fallback order
    fallback_order = [args.backend]
    if args.fallback:
        fallback_order = [b.strip() for b in args.fallback.split(",")]

    audio_path, backend_used, voices_used = synthesize(
        transcript=transcript,
        voices=voices,
        backend=args.backend,
        config=config,
        fallback_order=fallback_order,
    )

    duration = get_duration_seconds(audio_path)

    result = {
        "audio_path": audio_path,
        "backend_used": backend_used,
        "voices_used": voices_used,
        "duration_seconds": duration,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add skills/article-podcast/scripts/synthesize_chunk.py
git commit -m "feat: add synthesize_chunk.py CLI wrapper for AI agent"
```

---

## Task 8: publish_episode.py CLI Wrapper

`publish.py` already has a `main()` with CLI args. We just need to rename/alias for clarity and ensure env var loading.

**Files:**
- Create: `skills/article-podcast/scripts/publish_episode.py`

**Step 1: Write implementation**

```python
# skills/article-podcast/scripts/publish_episode.py
#!/usr/bin/env python3
"""CLI wrapper for publishing episodes. Called by the AI agent as a tool.

Thin wrapper around publish.py that also loads env vars from the worker env file.
"""

import json
import os
import sys

# Load env vars from worker env file (handles semicolons in connection strings)
ENV_FILE = os.path.expanduser("~/.config/article-podcast-worker/env")
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key, val)

sys.path.insert(0, os.path.dirname(__file__))
from publish import publish, main

if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add skills/article-podcast/scripts/publish_episode.py
git commit -m "feat: add publish_episode.py CLI wrapper for AI agent"
```

---

## Task 9: Update requirements.txt

**Files:**
- Modify: `requirements.txt`

**Step 1: Update**

Add to `requirements.txt`:
```
PyMuPDF>=1.24.0
ebooklib>=0.18
python-docx>=1.0.0
```

Note: `yt-dlp` is a system tool (installed via pip/brew globally), not a library dep.

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "deps: add PyMuPDF, ebooklib, python-docx for new parsers"
```

---

## Task 10: Rewrite SKILL.md for AI-Orchestrated Flow

**Files:**
- Modify: `skills/article-podcast/SKILL.md`

**Step 1: Write the new SKILL.md**

The new SKILL.md guides the AI agent through the full orchestrated pipeline. It replaces the current "just call generate.py --enqueue" flow with a multi-step process where the agent uses tool scripts and makes splitting/formatting decisions.

Key sections:
1. **When to use** -- same triggers plus new ones (PDF, book, YouTube playlist, local files)
2. **Step 1: Parse the source** -- call `parse_source.py`, handle `no_parser` response by writing a new parser
3. **Step 2: Plan episodes** -- read the parsed structure, apply user instructions, decide splitting, handle long sections (sliding window), determine series naming
4. **Step 3: Generate transcripts** -- dispatch subagents with chunk text files, each writes transcript JSON
5. **Step 4: Synthesize audio** -- call `synthesize_chunk.py` per transcript
6. **Step 5: Publish episodes** -- call `publish_episode.py` per audio file, with series naming
7. **Step 6: Report results** -- summarize what was published
8. **Parser contract reference** -- for when the AI needs to write a new parser
9. **Error handling** -- what to do when parsing fails, TTS fails, publish fails

This is a significant rewrite. The full content should be written during implementation.

**Step 2: Commit**

```bash
git add skills/article-podcast/SKILL.md
git commit -m "feat: rewrite SKILL.md for AI-orchestrated pipeline"
```

---

## Task 11: Integration Test -- End-to-End with Text File

**Files:**
- Test: `tests/test_integration_text.py`

**Step 1: Write the test**

```python
# tests/test_integration_text.py
"""Integration test: parse a text file through parse_source.py."""
import os, sys, json, subprocess, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))


def test_parse_source_text_file(tmp_path):
    """parse_source.py correctly dispatches to text parser."""
    f = tmp_path / "test.txt"
    f.write_text("This is a test document with enough words to be valid. " * 20)

    from parse_source import parse
    result = parse(str(f))

    assert result["source_type"] == "text"
    assert result["total_words"] > 0
    assert len(result["sections"]) >= 1
    assert result["sections"][0]["text"].startswith("This is a test")


def test_parse_source_unknown_type_returns_no_parser():
    """parse_source.py returns no_parser for unknown URL patterns."""
    from parse_source import detect_source_type, resolve_parser

    stype, val = detect_source_type("https://notion.so/some-page")
    parser = resolve_parser(stype, val)
    # notion.so should fall through to web.py fallback
    assert parser is not None
    assert parser.endswith("web.py")
```

**Step 2: Run test**

Run: `python3 -m pytest tests/test_integration_text.py -v`
Expected: 2 PASSED

**Step 3: Commit**

```bash
git add tests/test_integration_text.py
git commit -m "test: add integration test for parse_source text file flow"
```

---

## Task 12: Deploy to Surface Pro

**Step 1: Install new dependencies in worker venv**

```bash
ssh moltbot@100.107.15.52 'source ~/.openclaw/extensions/openclaw-plugin-article-podcast/skills/article-podcast/venv/bin/activate && pip install PyMuPDF ebooklib python-docx'
```

**Step 2: Sync files to both deployment paths**

```bash
rsync -avz --exclude='.git' --exclude='venv' --exclude='__pycache__' --exclude='node_modules' --exclude='.DS_Store' \
  plugin-article-podcast/ \
  moltbot@100.107.15.52:~/.openclaw/extensions/openclaw-plugin-article-podcast/

rsync -avz --exclude='.git' --exclude='venv' --exclude='__pycache__' --exclude='node_modules' --exclude='.DS_Store' \
  plugin-article-podcast/ \
  moltbot@100.107.15.52:~/projects/openclaw-plugin-article-podcast/
```

**Step 3: Restart services**

```bash
ssh moltbot@100.107.15.52 'systemctl --user restart article-podcast-worker.service && systemctl --user restart openclaw-gateway.service'
```

**Step 4: Verify**

```bash
ssh moltbot@100.107.15.52 'source ~/.openclaw/extensions/openclaw-plugin-article-podcast/skills/article-podcast/venv/bin/activate && python3 ~/.openclaw/extensions/openclaw-plugin-article-podcast/skills/article-podcast/scripts/parse_source.py --source "https://paulgraham.com/think.html"'
```

Expected: JSON output with source_type, title, sections.
