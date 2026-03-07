"""Tests for web parser."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from parsers.web import _extract_from_html


def test_web_parser_output_format():
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
    html = """<html><head><title>Multi Section</title></head><body>
    <h1>Multi Section</h1>
    <h2>Part One</h2><p>Content of part one goes here with enough words.</p>
    <h2>Part Two</h2><p>Content of part two is also here with words.</p>
    </body></html>"""

    result = _extract_from_html(html, "https://example.com/multi")
    assert result["source_type"] == "web"
    assert len(result["sections"]) >= 2
