#!/usr/bin/env python3
"""PDF parser: extract text with chapter detection via bookmarks or heading patterns."""

import json
import re
import sys


def _split_by_bookmarks(pages_text: dict[int, str], bookmarks: list[dict], total_pages: int) -> list[dict]:
    """Split PDF text using bookmark/TOC entries."""
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
        lines = text.split("\n", 1)
        body = lines[1].strip() if len(lines) > 1 else text
        wc = len(body.split())
        sections.append({"title": title, "text": body, "word_count": wc, "index": i})

    return [s for s in sections if s["text"]]


def parse(source: str) -> dict:
    """Extract text and structure from a PDF file."""
    import fitz

    doc = fitz.open(source)
    meta = doc.metadata or {}
    title = meta.get("title", "").strip()
    author = meta.get("author", "").strip()

    pages_text = {}
    for i, page in enumerate(doc):
        pages_text[i] = page.get_text()

    toc = doc.get_toc()
    bookmarks = [{"title": entry[1], "page": entry[2] - 1} for entry in toc if entry[0] <= 2]

    if bookmarks:
        sections = _split_by_bookmarks(pages_text, bookmarks, len(doc))
    else:
        full_text = "\n".join(pages_text.get(i, "") for i in range(len(doc)))
        sections = _split_by_headings(full_text)

    if not title:
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
