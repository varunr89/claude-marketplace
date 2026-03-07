"""Tests for PDF parser."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from parsers.pdf import _split_by_bookmarks, _split_by_headings


def test_split_by_bookmarks():
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
    full_text = (
        "CHAPTER 1\nIntroduction to the topic with some text.\n\n"
        "CHAPTER 2\nMore advanced material goes here.\n\n"
        "CHAPTER 3\nFinal conclusions and summary."
    )
    sections = _split_by_headings(full_text)
    assert len(sections) == 3
    assert "Introduction" in sections[0]["text"]


def test_single_section_when_no_structure():
    full_text = "Just a regular document with no chapters or headings at all. " * 50
    sections = _split_by_headings(full_text)
    assert len(sections) == 1
