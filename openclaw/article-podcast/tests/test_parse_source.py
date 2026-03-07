"""Tests for parse_source dispatcher."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from parse_source import detect_source_type, resolve_parser


def test_detect_pdf_file():
    assert detect_source_type("/path/to/book.pdf") == ("file_ext", ".pdf")


def test_detect_youtube_url():
    stype, val = detect_source_type("https://www.youtube.com/watch?v=abc123")
    assert stype == "url_pattern"
    assert "youtube.com" in val


def test_detect_youtube_short_url():
    stype, val = detect_source_type("https://youtu.be/abc123")
    assert stype == "url_pattern"
    assert "youtu.be" in val


def test_detect_epub_file():
    assert detect_source_type("/path/to/book.epub") == ("file_ext", ".epub")


def test_detect_docx_file():
    assert detect_source_type("/path/to/doc.docx") == ("file_ext", ".docx")


def test_detect_txt_file():
    assert detect_source_type("/path/to/notes.txt") == ("file_ext", ".txt")


def test_detect_web_url():
    stype, val = detect_source_type("https://example.com/article")
    assert stype == "fallback"


def test_resolve_parser_pdf():
    parser_path = resolve_parser("file_ext", ".pdf")
    assert parser_path.endswith("pdf.py")


def test_resolve_parser_fallback():
    parser_path = resolve_parser("fallback", "anything")
    assert parser_path.endswith("web.py")


def test_resolve_parser_no_match():
    result = resolve_parser("url_pattern", "notion.so")
    assert result is None
