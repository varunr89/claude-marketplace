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
