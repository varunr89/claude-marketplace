"""Tests for YouTube parser."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from parsers.youtube import _parse_vtt, _is_playlist_url, _extract_video_id


def test_parse_vtt_cleans_timestamps():
    vtt = """WEBVTT

00:00:00.000 --> 00:00:05.000
Hello world this is a test.

00:00:05.000 --> 00:00:10.000
Hello world this is a test.

00:00:10.000 --> 00:00:15.000
Another line of content here.
"""
    text = _parse_vtt(vtt)
    assert "Hello world this is a test." in text
    assert "Another line of content here." in text
    assert "-->" not in text
    assert text.count("Hello world this is a test.") == 1


def test_is_playlist_url():
    assert _is_playlist_url("https://www.youtube.com/watch?v=abc&list=PLxyz") is True
    assert _is_playlist_url("https://www.youtube.com/playlist?list=PLxyz") is True
    assert _is_playlist_url("https://www.youtube.com/watch?v=abc") is False
    assert _is_playlist_url("https://youtu.be/abc") is False


def test_extract_video_id():
    assert _extract_video_id("https://www.youtube.com/watch?v=abc123") == "abc123"
    assert _extract_video_id("https://youtu.be/abc123") == "abc123"
    assert _extract_video_id("https://youtube.com/watch?v=abc123&t=10") == "abc123"
