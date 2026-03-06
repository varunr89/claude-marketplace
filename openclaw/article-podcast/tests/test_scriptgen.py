"""Tests for script generation: content fetching and classification."""

import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"),
)

import pytest
from scriptgen import (
    classify_content, parse_transcript_response,
    FORMAT_INTERVIEW, FORMAT_DISCUSSION, FORMAT_NARRATOR,
)


# --- classify_content ---

def test_arxiv_url_gets_interview():
    fmt = classify_content("https://arxiv.org/abs/2401.12345", "Attention Is All You Need")
    assert fmt == FORMAT_INTERVIEW


def test_github_url_gets_interview():
    fmt = classify_content("https://github.com/org/repo", "Kubernetes Autoscaler Design")
    assert fmt == FORMAT_INTERVIEW


def test_acm_url_gets_interview():
    fmt = classify_content("https://dl.acm.org/doi/paper", "Database Query Optimization")
    assert fmt == FORMAT_INTERVIEW


def test_news_domain_gets_discussion():
    fmt = classify_content("https://www.nytimes.com/article", "Fed Raises Rates Again")
    assert fmt == FORMAT_DISCUSSION


def test_bbc_gets_discussion():
    fmt = classify_content("https://www.bbc.com/news/article", "Climate Summit Updates")
    assert fmt == FORMAT_DISCUSSION


def test_blog_gets_narrator():
    fmt = classify_content("https://paulgraham.com/think.html", "How to Think for Yourself")
    assert fmt == FORMAT_NARRATOR


def test_substack_gets_narrator():
    fmt = classify_content("https://someone.substack.com/p/my-take", "My Take on Remote Work")
    assert fmt == FORMAT_NARRATOR


def test_medium_gets_narrator():
    fmt = classify_content("https://medium.com/@user/my-essay", "Why I Left Big Tech")
    assert fmt == FORMAT_NARRATOR


def test_technical_keywords_in_title_get_interview():
    fmt = classify_content("https://example.com/post", "Distributed Database Algorithm Design")
    assert fmt == FORMAT_INTERVIEW


def test_generic_url_defaults_to_discussion():
    fmt = classify_content("https://example.com/page", "Some Random Topic")
    assert fmt == FORMAT_DISCUSSION


# --- parse_transcript_response ---

def test_parse_valid_json():
    raw = '{"title": "Test", "segments": []}'
    result = parse_transcript_response(raw)
    assert result["title"] == "Test"


def test_parse_json_with_markdown_fences():
    raw = '```json\n{"title": "Test", "segments": []}\n```'
    result = parse_transcript_response(raw)
    assert result["title"] == "Test"


def test_parse_malformed_json_raises():
    with pytest.raises(Exception):
        parse_transcript_response("not valid json at all")
