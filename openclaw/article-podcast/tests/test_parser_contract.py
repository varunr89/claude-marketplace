"""Tests for parser contract validation."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from parsers.contract import validate_parser_output


def test_valid_output_passes():
    data = {
        "source_type": "web",
        "title": "Test Article",
        "metadata": {"source_url": "https://example.com"},
        "sections": [
            {"title": "Section 1", "text": "Some content here.", "word_count": 4, "index": 0}
        ],
        "total_words": 4,
    }
    assert validate_parser_output(data) is True


def test_missing_sections_fails():
    data = {"source_type": "web", "title": "Test", "metadata": {}, "total_words": 0}
    assert validate_parser_output(data) is False


def test_empty_text_fails():
    data = {
        "source_type": "web",
        "title": "Test",
        "metadata": {},
        "sections": [{"title": "S1", "text": "", "word_count": 0, "index": 0}],
        "total_words": 0,
    }
    assert validate_parser_output(data) is False


def test_missing_title_fails():
    data = {
        "source_type": "web",
        "metadata": {},
        "sections": [{"title": "S1", "text": "Content", "word_count": 1, "index": 0}],
        "total_words": 1,
    }
    assert validate_parser_output(data) is False
