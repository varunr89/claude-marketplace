"""Tests for plain text parser."""
import os, sys
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
