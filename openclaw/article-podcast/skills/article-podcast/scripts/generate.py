#!/usr/bin/env python3
"""Generate a podcast episode from a URL using multi-TTS pipeline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mutagen import File as MutagenFile


def get_duration_seconds(audio_path: str) -> int:
    """Get duration of an audio file in seconds (supports MP3, M4A, WAV)."""
    audio = MutagenFile(audio_path)
    if audio and audio.info.length > 0:
        return int(audio.info.length)
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", audio_path],
            capture_output=True, text=True, timeout=10,
        )
        return int(float(result.stdout.strip()))
    except Exception:
        return 0


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _is_url_or_filename(text: str) -> bool:
    """Check if text looks like a URL or raw filename rather than a title."""
    text = text.strip()
    if text.startswith(("http://", "https://", "ftp://")):
        return True
    if "." in text and " " not in text and text.split(".")[-1].lower() in (
        "pdf", "html", "htm", "txt", "md", "doc", "docx",
    ):
        return True
    return False


def _clean_filename_title(text: str) -> str:
    """Best-effort conversion of a filename/URL into a readable title."""
    import re
    from urllib.parse import urlparse, unquote

    if text.startswith(("http://", "https://")):
        path = urlparse(text).path
        text = unquote(path.rstrip("/").split("/")[-1])
    text = re.sub(r"\.(pdf|html?|txt|md|docx?)$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[-_]+", " ", text)
    text = text.strip().title()
    return text or "Untitled Episode"


def generate(
    url: str, fmt: str, length: str, instructions: str, config: dict,
    voice_override: list[str] | None = None,
) -> dict:
    """Generate podcast audio from a URL using the two-stage pipeline.

    Stage 1: Fetch article, classify content, generate transcript via LLM.
    Stage 2: Synthesize audio via TTS fallback chain.

    Args:
        voice_override: explicit voice names to use (skips random selection)

    Returns dict with: mp3_path, title, description, duration_seconds, source_url
    """
    from scriptgen import (
        fetch_article, classify_content, build_transcript_prompt,
        parse_transcript_response, FORMAT_INTERVIEW, FORMAT_DISCUSSION, FORMAT_NARRATOR,
    )
    from synthesize import synthesize
    from voices import pick_voices, record_voice_usage

    # --- Stage 1: Script Generation ---
    _log("=== Stage 1: Script Generation ===")

    # Fetch article
    article_text = fetch_article(url)

    # Classify content and pick format
    # Map old format names to new ones for backwards compat
    format_map = {
        "deep-dive": None,  # auto-classify
        "brief": None,      # auto-classify (length handled separately)
        "critique": FORMAT_INTERVIEW,
        "debate": FORMAT_DISCUSSION,
        "interview": FORMAT_INTERVIEW,
        "discussion": FORMAT_DISCUSSION,
        "narrator": FORMAT_NARRATOR,
    }
    podcast_format = format_map.get(fmt)
    if podcast_format is None:
        podcast_format = classify_content(url, article_text[:500])
    _log(f"Format: {podcast_format}")

    # Let the LLM decide length based on complexity (None = AI decides)
    length_map = {"short": 10, "default": None, "long": None}
    length_minutes = length_map.get(length)

    # Build prompt and call LLM
    prompt = build_transcript_prompt(
        article_text, podcast_format, url, length_minutes=length_minutes,
    )
    _log(f"Calling LLM for transcript ({len(prompt)} char prompt)...")

    # Call OpenClaw's LLM via subprocess
    # openclaw agent generates the transcript using its configured LLM routing
    openclaw_bin = os.environ.get("OPENCLAW_BIN", "openclaw")
    openclaw_agent = os.environ.get("OPENCLAW_AGENT", "main")
    try:
        result = subprocess.run(
            [openclaw_bin, "agent", "--agent", openclaw_agent, "--json", "--message", prompt],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"LLM call failed: {result.stderr}")
        llm_output = result.stdout.strip()
        # openclaw agent --json returns nested structure:
        # {"result": {"payloads": [{"text": "..."}]}}
        try:
            wrapper = json.loads(llm_output)
            payloads = wrapper.get("result", {}).get("payloads", [])
            if payloads:
                llm_text = payloads[0].get("text", llm_output)
            else:
                llm_text = wrapper.get("response", llm_output)
        except json.JSONDecodeError:
            llm_text = llm_output
    except subprocess.TimeoutExpired:
        raise RuntimeError("LLM call timed out after 300s")

    transcript = parse_transcript_response(llm_text)
    _log(f"Transcript: {len(transcript['segments'])} segments, "
         f"title={transcript['title']!r}")

    # Save transcript for debugging
    transcript_dir = Path(tempfile.mkdtemp(prefix="podcast-transcript-"))
    transcript_path = transcript_dir / "transcript.json"
    transcript_path.write_text(json.dumps(transcript, indent=2))
    _log(f"Transcript saved: {transcript_path}")

    # --- Stage 2: Audio Synthesis ---
    _log("=== Stage 2: Audio Synthesis ===")

    num_speakers = len(transcript["speakers"])
    fallback_order = config.get("tts_fallback_order", ["gemini", "azure-openai", "edge"])
    primary_backend = fallback_order[0] if fallback_order else "gemini"

    # Pick voices for primary backend
    voices = pick_voices(primary_backend, num_speakers, override=voice_override)
    _log(f"Voices: {voices} (backend: {primary_backend})")

    audio_path, backend_used, voices_used = synthesize(
        transcript=transcript,
        voices=voices,
        backend=primary_backend,
        config=config,
        fallback_order=fallback_order,
    )
    _log(f"Audio generated via {backend_used}: {audio_path}")

    # Record the ACTUAL voices used (may differ if fallback backend was used)
    record_voice_usage(voices_used)

    # Extract title and description
    title = transcript.get("title", "")
    if not title or _is_url_or_filename(title):
        title = _clean_filename_title(url)

    description = f"Podcast {podcast_format} about: {url}"
    duration = get_duration_seconds(audio_path)

    result = {
        "mp3_path": audio_path,
        "title": title,
        "description": description,
        "duration_seconds": duration,
        "source_url": url,
        "backend_used": backend_used,
        "format": podcast_format,
        "transcript_path": str(transcript_path),
    }

    # Clean up transcript temp dir (audio temp dir cleaned after publish)
    import shutil
    try:
        shutil.rmtree(transcript_dir, ignore_errors=True)
    except Exception:
        pass

    return result


def main():
    parser = argparse.ArgumentParser(description="Generate podcast from URL")
    parser.add_argument("--url", required=True, help="Article URL")
    parser.add_argument("--format", default="deep-dive",
                        choices=["deep-dive", "brief", "critique", "debate",
                                 "interview", "discussion", "narrator"])
    parser.add_argument("--length", default="long",
                        choices=["short", "default", "long"],
                        help="Audio length: short, default, or long (default: long)")
    parser.add_argument("--instructions", default="auto",
                        help="Custom instructions or 'auto' for content-based selection")
    parser.add_argument("--config", default=None,
                        help="Path to JSON config file with plugin settings")
    parser.add_argument("--enqueue", action="store_true",
                        help="Queue the job for background processing")
    parser.add_argument("--notification-account", default="+13603069264",
                        help="Signal account phone number for notifications")
    parser.add_argument("--notification-recipient", default=None,
                        help="Signal recipient UUID for notifications")
    parser.add_argument("--voices", default=None,
                        help="Comma-separated voice names to override auto-selection")
    args = parser.parse_args()

    config_path = args.config
    if config_path is None:
        config_path = str(
            Path.home() / ".openclaw" / "plugins"
            / "openclaw-plugin-article-podcast" / "config.json"
        )

    if args.enqueue:
        sys.path.insert(0, os.path.dirname(__file__))
        from job_manager import enqueue

        notification = None
        if args.notification_recipient:
            notification = {
                "type": "signal",
                "account": args.notification_account,
                "recipient": args.notification_recipient,
            }

        job_id = enqueue(
            url=args.url,
            fmt=args.format,
            length=args.length,
            instructions=args.instructions,
            config_path=config_path,
            notification=notification,
        )
        print(json.dumps({"job_id": job_id, "status": "queued"}))
        return

    config = {}
    if config_path and os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)

    voice_override = None
    if args.voices:
        voice_override = [v.strip() for v in args.voices.split(",")]

    result = generate(args.url, args.format, args.length, args.instructions, config,
                      voice_override=voice_override)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
