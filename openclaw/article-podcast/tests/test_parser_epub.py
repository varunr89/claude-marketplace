"""Tests for EPUB parser internal helpers."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from parsers.epub import _html_to_text


def test_html_to_text_strips_tags():
    html = "<html><body><h1>Title</h1><p>Content here.</p></body></html>"
    text = _html_to_text(html)
    assert "Content here." in text
    assert "<" not in text
