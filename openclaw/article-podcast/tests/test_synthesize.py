"""Tests for TTS synthesis engine (unit tests with mocked backends)."""

import json
import os
import sys
import tempfile

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"),
)

from synthesize import (
    build_gemini_prompt,
    batch_segments,
    chunk_for_gemini,
    TTS_BACKENDS,
)


SAMPLE_TRANSCRIPT = {
    "title": "Test Episode",
    "format": "discussion",
    "speakers": [
        {"id": "S1", "role": "co-host"},
        {"id": "S2", "role": "co-host"},
    ],
    "segments": [
        {"speaker": "S1", "text": "Hello and welcome."},
        {"speaker": "S2", "text": "Great to be here."},
        {"speaker": "S1", "text": "Let's dive in."},
    ],
    "source_url": "https://example.com",
    "estimated_duration_minutes": 5,
}


def test_tts_backends_list():
    assert "gemini" in TTS_BACKENDS
    assert "azure-openai" in TTS_BACKENDS
    assert "edge" in TTS_BACKENDS


def test_build_gemini_prompt_two_speakers():
    prompt = build_gemini_prompt(SAMPLE_TRANSCRIPT["segments"], "discussion")
    # The prompt should contain the dialogue text
    assert "Hello and welcome" in prompt
    assert "Great to be here" in prompt


def test_build_gemini_prompt_solo():
    segments = [{"speaker": "S1", "text": "Once upon a time."}]
    prompt = build_gemini_prompt(segments, "narrator")
    assert "Once upon a time" in prompt


def test_build_gemini_prompt_uses_speaker_names():
    prompt = build_gemini_prompt(SAMPLE_TRANSCRIPT["segments"], "discussion")
    # Should map S1->Alex, S2->Sam for discussion format
    assert "Alex:" in prompt
    assert "Sam:" in prompt


# --- batch_segments tests ---

def test_batch_same_speaker_segments():
    segments = [
        {"speaker": "S1", "text": "Hello."},
        {"speaker": "S1", "text": "How are you?"},
        {"speaker": "S2", "text": "I'm fine."},
    ]
    batches = batch_segments(segments, max_chars=1000)
    # S1's two segments should be batched together
    assert len(batches) == 2
    assert batches[0]["speaker"] == "S1"
    assert "Hello." in batches[0]["text"]
    assert "How are you?" in batches[0]["text"]
    assert batches[1]["speaker"] == "S2"


def test_batch_respects_char_limit():
    segments = [
        {"speaker": "S1", "text": "A" * 3000},
        {"speaker": "S1", "text": "B" * 3000},
    ]
    batches = batch_segments(segments, max_chars=4096)
    # Each segment is 3000 chars; combined would be 6001 (with space).
    # Should split into 2 batches.
    assert len(batches) == 2


def test_batch_speaker_change_forces_new_batch():
    segments = [
        {"speaker": "S1", "text": "Hello."},
        {"speaker": "S2", "text": "Hi there."},
        {"speaker": "S1", "text": "How's it going?"},
    ]
    batches = batch_segments(segments, max_chars=1000)
    assert len(batches) == 3  # Each speaker change = new batch


def test_batch_empty_segments():
    assert batch_segments([], max_chars=4096) == []


def test_batch_oversized_single_segment():
    """A single segment larger than max_chars should be split."""
    segments = [{"speaker": "S1", "text": "Word. " * 1000}]  # ~6000 chars
    batches = batch_segments(segments, max_chars=2000)
    assert len(batches) >= 3
    for b in batches:
        assert len(b["text"]) <= 2000
        assert b["speaker"] == "S1"


# --- chunk_for_gemini tests ---

def test_chunk_for_gemini_short_transcript():
    """Short transcript should be a single chunk."""
    segments = [
        {"speaker": "S1", "text": "Hello."},
        {"speaker": "S2", "text": "Hi."},
    ]
    chunks = chunk_for_gemini(segments, max_words=750)
    assert len(chunks) == 1
    assert len(chunks[0]) == 2


def test_chunk_for_gemini_long_transcript():
    """Long transcript should be split into multiple chunks."""
    segments = []
    for i in range(100):
        speaker = "S1" if i % 2 == 0 else "S2"
        # Each segment ~20 words
        segments.append({"speaker": speaker, "text": "This is a test sentence with about twenty words in it for testing purposes. " * 1})
    chunks = chunk_for_gemini(segments, max_words=150)
    assert len(chunks) > 1
    # All segments should be accounted for
    total = sum(len(c) for c in chunks)
    assert total == 100


def test_chunk_for_gemini_preserves_order():
    segments = [
        {"speaker": "S1", "text": "First."},
        {"speaker": "S2", "text": "Second."},
        {"speaker": "S1", "text": "Third."},
    ]
    chunks = chunk_for_gemini(segments, max_words=750)
    flat = [seg for chunk in chunks for seg in chunk]
    assert flat[0]["text"] == "First."
    assert flat[1]["text"] == "Second."
    assert flat[2]["text"] == "Third."
