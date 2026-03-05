"""Tests for title resolution helpers in generate.py."""

import sys
import os

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"),
)

from generate import (
    _is_url_or_filename,
    _clean_filename_title,
)


# --- _is_url_or_filename ---


def test_detects_https_url():
    assert _is_url_or_filename("https://example.com/paper.pdf") is True


def test_detects_http_url():
    assert _is_url_or_filename("http://arxiv.org/abs/1234") is True


def test_detects_filename():
    assert _is_url_or_filename("neumann-btw2025.pdf") is True


def test_rejects_normal_title():
    assert _is_url_or_filename("Improving Unnesting of Complex Queries") is False


def test_rejects_title_with_colon():
    assert _is_url_or_filename("Spanner: Google's Database") is False


# --- _clean_filename_title ---


def test_clean_url_to_title():
    url = "https://example.com/papers/neumann-btw2025.pdf"
    assert _clean_filename_title(url) == "Neumann Btw2025"


def test_clean_filename_with_underscores():
    assert _clean_filename_title("my_great_paper.pdf") == "My Great Paper"


def test_clean_empty_returns_untitled():
    assert _clean_filename_title("") == "Untitled Episode"


def test_clean_url_with_path():
    url = "https://www.scs.stanford.edu/26wi-cs244c/sched/readings/causalsim.pdf"
    assert _clean_filename_title(url) == "Causalsim"
