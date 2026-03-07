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
