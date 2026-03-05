"""Tests for job queue management."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

import job_manager


def test_enqueue_creates_pending_job(tmp_path, monkeypatch):
    """enqueue writes a valid JSON file to pending/."""
    monkeypatch.setenv("PODCAST_JOBS_DIR", str(tmp_path))

    job_id = job_manager.enqueue(
        url="https://example.com/article",
        fmt="deep-dive",
        instructions="auto",
        config_path="/tmp/config.json",
        notification={"type": "signal", "account": "+1234", "recipient": "uuid"},
    )

    job_path = tmp_path / "pending" / f"{job_id}.json"
    assert job_path.exists()

    with open(job_path) as f:
        job = json.load(f)
    assert job["job_id"] == job_id
    assert job["url"] == "https://example.com/article"
    assert job["notification"]["recipient"] == "uuid"


def test_get_next_pending_moves_to_processing(tmp_path, monkeypatch):
    """get_next_pending atomically moves job from pending to processing."""
    monkeypatch.setenv("PODCAST_JOBS_DIR", str(tmp_path))

    job_id = job_manager.enqueue(
        url="https://example.com",
        fmt="brief",
        instructions="auto",
        config_path="/tmp/config.json",
    )

    job = job_manager.get_next_pending()
    assert job is not None
    assert job["job_id"] == job_id

    # Pending should be empty, processing should have the job
    assert not (tmp_path / "pending" / f"{job_id}.json").exists()
    assert (tmp_path / "processing" / f"{job_id}.json").exists()


def test_mark_completed(tmp_path, monkeypatch):
    """mark_completed moves job to completed with result."""
    monkeypatch.setenv("PODCAST_JOBS_DIR", str(tmp_path))

    job_id = job_manager.enqueue(
        url="https://example.com",
        fmt="deep-dive",
        instructions="auto",
        config_path="/tmp/config.json",
    )
    job_manager.get_next_pending()
    job_manager.mark_completed(job_id, {"audio_url": "https://example.com/ep.mp3"})

    completed_path = tmp_path / "completed" / f"{job_id}.json"
    assert completed_path.exists()
    assert not (tmp_path / "processing" / f"{job_id}.json").exists()

    with open(completed_path) as f:
        job = json.load(f)
    assert job["result"]["audio_url"] == "https://example.com/ep.mp3"
    assert "completed_at" in job


def test_mark_failed(tmp_path, monkeypatch):
    """mark_failed moves job to failed with error."""
    monkeypatch.setenv("PODCAST_JOBS_DIR", str(tmp_path))

    job_id = job_manager.enqueue(
        url="https://example.com",
        fmt="deep-dive",
        instructions="auto",
        config_path="/tmp/config.json",
    )
    job_manager.get_next_pending()
    job_manager.mark_failed(job_id, "NotebookLM timeout")

    failed_path = tmp_path / "failed" / f"{job_id}.json"
    assert failed_path.exists()

    with open(failed_path) as f:
        job = json.load(f)
    assert job["error"] == "NotebookLM timeout"
    assert "failed_at" in job
