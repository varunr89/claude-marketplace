"""Tests for voice pool management and selection."""

import json
import os
import sys
import tempfile

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"),
)

from voices import (
    VOICE_POOLS,
    pick_voices,
    record_voice_usage,
    load_voice_history,
)


def test_voice_pools_have_all_backends():
    assert "gemini" in VOICE_POOLS
    assert "azure-openai" in VOICE_POOLS
    assert "edge" in VOICE_POOLS


def test_each_pool_has_at_least_4_voices():
    for backend, pool in VOICE_POOLS.items():
        assert len(pool) >= 4, f"{backend} pool has only {len(pool)} voices"


def test_pick_voices_two_speaker_returns_two_distinct():
    v1, v2 = pick_voices("gemini", num_speakers=2)
    assert v1 != v2
    assert v1 in VOICE_POOLS["gemini"]
    assert v2 in VOICE_POOLS["gemini"]


def test_pick_voices_solo_returns_one():
    result = pick_voices("gemini", num_speakers=1)
    assert len(result) == 1
    assert result[0] in VOICE_POOLS["gemini"]


def test_pick_voices_avoids_recent(tmp_path):
    history_file = tmp_path / "voice_history.json"
    # Fill history with all but 2 voices for gemini
    pool = VOICE_POOLS["gemini"]
    # Record all but last 2 voices as recently used
    history = [pool[i] for i in range(len(pool) - 2)]
    history_file.write_text(json.dumps(history))
    v1, v2 = pick_voices(
        "gemini", num_speakers=2, history_path=str(history_file)
    )
    # Should strongly prefer the 2 unused voices
    assert v1 in pool
    assert v2 in pool
    assert v1 != v2


def test_pick_voices_works_with_no_history_file(tmp_path):
    history_file = tmp_path / "nonexistent.json"
    result = pick_voices("gemini", num_speakers=2, history_path=str(history_file))
    assert len(result) == 2


def test_record_voice_usage_creates_file(tmp_path):
    history_file = tmp_path / "voice_history.json"
    record_voice_usage(["Kore", "Puck"], history_path=str(history_file))
    data = json.loads(history_file.read_text())
    assert "Kore" in data
    assert "Puck" in data


def test_record_voice_usage_caps_history(tmp_path):
    history_file = tmp_path / "voice_history.json"
    # Write 20 entries
    history_file.write_text(json.dumps(["v" + str(i) for i in range(20)]))
    record_voice_usage(["new1", "new2"], history_path=str(history_file))
    data = json.loads(history_file.read_text())
    # Should keep last 10 entries (5 episodes * 2 voices) = 10, plus 2 new = 12, capped at 10
    assert len(data) <= 12
    assert "new1" in data
    assert "new2" in data


def test_pick_voices_with_override():
    result = pick_voices("gemini", num_speakers=2, override=["Kore", "Puck"])
    assert result == ["Kore", "Puck"]


def test_pick_voices_azure_backend():
    v1, v2 = pick_voices("azure-openai", num_speakers=2)
    assert v1 in VOICE_POOLS["azure-openai"]
    assert v2 in VOICE_POOLS["azure-openai"]
    assert v1 != v2


def test_pick_voices_edge_backend():
    v1, v2 = pick_voices("edge", num_speakers=2)
    assert v1 in VOICE_POOLS["edge"]
    assert v2 in VOICE_POOLS["edge"]
    assert v1 != v2
