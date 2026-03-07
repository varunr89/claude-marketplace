#!/usr/bin/env python3
"""DOCX parser: extract text with heading-based section detection."""

import json
import sys


def _group_by_headings(paragraphs: list[dict]) -> list[dict]:
    """Group paragraphs by heading styles."""
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
