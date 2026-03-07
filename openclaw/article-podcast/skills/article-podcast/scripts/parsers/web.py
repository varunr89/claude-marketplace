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

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    sections = []
    heading_tags = soup.find_all(["h2", "h3"])

    if heading_tags:
        for i, heading in enumerate(heading_tags):
            section_title = heading.get_text(strip=True)
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

    downloaded = trafilatura.fetch_url(source)
    if downloaded:
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
        if text:
            wc = len(text.split())
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
