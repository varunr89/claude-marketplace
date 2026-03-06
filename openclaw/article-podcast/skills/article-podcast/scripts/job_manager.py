#!/usr/bin/env python3
"""Filesystem-based job queue for async podcast generation."""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _jobs_dir() -> Path:
    """Get the jobs directory from env or default path."""
    env_dir = os.environ.get("PODCAST_JOBS_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".openclaw" / "plugins" / "openclaw-plugin-article-podcast" / "jobs"


def ensure_dirs() -> Path:
    """Create job subdirectories if they don't exist. Returns the jobs root."""
    base = _jobs_dir()
    for sub in ("pending", "processing", "completed", "failed"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


def enqueue(
    url: str,
    fmt: str,
    instructions: str,
    config_path: str,
    length: str = "long",
    notification: Optional[dict] = None,
) -> str:
    """Write a job to pending/ and return the job_id."""
    base = ensure_dirs()
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "url": url,
        "format": fmt,
        "length": length,
        "instructions": instructions,
        "config_path": config_path,
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
        "notification": notification,
    }

    job_path = base / "pending" / f"{job_id}.json"
    tmp_path = job_path.with_suffix(".tmp")

    with open(tmp_path, "w") as f:
        json.dump(job, f, indent=2)

    os.rename(tmp_path, job_path)
    return job_id


def get_next_pending() -> Optional[dict]:
    """Atomically move the oldest pending job to processing/ and return it."""
    base = _jobs_dir()
    pending_dir = base / "pending"

    if not pending_dir.exists():
        return None

    # Sort by modification time (oldest first)
    jobs = sorted(pending_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)

    for job_path in jobs:
        processing_path = base / "processing" / job_path.name
        try:
            os.rename(job_path, processing_path)
        except FileNotFoundError:
            # Another worker grabbed it
            continue

        with open(processing_path) as f:
            return json.load(f)

    return None


def mark_completed(job_id: str, result: dict) -> None:
    """Move job from processing/ to completed/ with result attached."""
    base = _jobs_dir()
    processing_path = base / "processing" / f"{job_id}.json"
    completed_path = base / "completed" / f"{job_id}.json"

    with open(processing_path) as f:
        job = json.load(f)

    job["completed_at"] = datetime.now(timezone.utc).isoformat()
    job["result"] = result

    tmp_path = completed_path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(job, f, indent=2)

    os.rename(tmp_path, completed_path)

    try:
        os.remove(processing_path)
    except FileNotFoundError:
        pass


def mark_failed(job_id: str, error: str) -> None:
    """Move job from processing/ to failed/ with error attached."""
    base = _jobs_dir()
    processing_path = base / "processing" / f"{job_id}.json"
    failed_path = base / "failed" / f"{job_id}.json"

    with open(processing_path) as f:
        job = json.load(f)

    job["failed_at"] = datetime.now(timezone.utc).isoformat()
    job["error"] = error

    tmp_path = failed_path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(job, f, indent=2)

    os.rename(tmp_path, failed_path)

    try:
        os.remove(processing_path)
    except FileNotFoundError:
        pass
