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
