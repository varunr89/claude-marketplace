#!/usr/bin/env python3
"""Background worker daemon: poll jobs, generate, publish, notify."""

import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from job_manager import ensure_dirs, get_next_pending, mark_completed, mark_failed
from notifier import notify_failure, notify_success

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("worker")

POLL_INTERVAL = 30  # seconds


def process_job(job: dict) -> None:
    """Process a single job: generate audio, publish, notify."""
    job_id = job["job_id"]
    url = job["url"]
    fmt = job.get("format", "deep-dive")
    length = job.get("length", "long")
    instructions = job.get("instructions", "auto")
    config_path = job.get("config_path", "")
    notification = job.get("notification")

    log.info(f"Processing job {job_id}: {url}")

    # Load config
    config = {}
    if config_path and os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)

    try:
        from generate import generate
        from publish import publish

        # Generate audio
        result = generate(url, fmt, length, instructions, config)
        mp3_path = result["mp3_path"]
        title = result["title"]
        description = result["description"]
        duration = result["duration_seconds"]
        source_url = result["source_url"]

        log.info(f"Generated: {title} ({duration}s)")

        # Publish to Azure + RSS
        pub_result = publish(
            mp3_path=mp3_path,
            title=title,
            description=description,
            duration_seconds=duration,
            source_url=source_url,
            config=config,
        )

        log.info(f"Published: {pub_result['audio_url']}")

        # Mark completed
        full_result = {**result, **pub_result}
        mark_completed(job_id, full_result)

        # Send notification
        if notification:
            spotify_url = config.get("spotify_url", pub_result.get("feed_url", ""))
            notify_success(notification, title, duration, spotify_url)
            log.info(f"Notification sent for job {job_id}")

        # Clean up temp audio files
        try:
            tmp_dir = str(Path(mp3_path).parent)
            if tmp_dir.startswith(("/tmp", "/var/tmp")) or "podcast-" in tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    except Exception as e:
        log.error(f"Job {job_id} failed: {e}")
        mark_failed(job_id, str(e))

        if notification:
            try:
                notify_failure(notification, url, str(e))
            except Exception as notify_err:
                log.error(f"Failed to send failure notification: {notify_err}")


def main():
    log.info("Worker starting, polling every %ds", POLL_INTERVAL)
    ensure_dirs()

    while True:
        job = get_next_pending()
        if job:
            process_job(job)
        else:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
