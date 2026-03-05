#!/usr/bin/env python3
"""Generate a podcast episode from a URL using multi-TTS pipeline.

Supports two modes:
  1. Full pipeline: fetch article -> LLM transcript -> TTS -> publish
  2. Transcript-provided: skip LLM, use pre-generated transcript JSON

In Claude Code plugin mode, Claude itself generates the transcript and passes
it via --transcript-file, making this script LLM-agnostic.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mutagen import File as MutagenFile


def _data_dir() -> Path:
    return Path(os.environ.get("PODCAST_DATA_DIR", str(Path.home() / ".article-podcast")))


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


def _call_llm(prompt: str) -> str:
    """Call an LLM to generate the transcript.

    Tries in order:
      1. LLM_COMMAND env var (custom command, receives prompt on stdin)
      2. openclaw agent (if OPENCLAW_BIN is set or openclaw is in PATH)

    For Claude Code plugin usage, the skill instructs Claude to generate the
    transcript directly and pass it via --transcript-file, bypassing this.
    """
    # Option 1: Custom LLM command
    llm_command = os.environ.get("LLM_COMMAND")
    if llm_command:
        _log(f"Calling LLM via custom command: {llm_command}")
        result = subprocess.run(
            llm_command, shell=True,
            input=prompt, capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"LLM command failed: {result.stderr}")
        return result.stdout.strip()

    # Option 2: OpenClaw agent
    openclaw_bin = os.environ.get("OPENCLAW_BIN", "openclaw")
    openclaw_agent = os.environ.get("OPENCLAW_AGENT", "main")
    _log(f"Calling LLM via {openclaw_bin} agent...")
    try:
        result = subprocess.run(
            [openclaw_bin, "agent", "--agent", openclaw_agent, "--json", "--message", prompt],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"LLM call failed: {result.stderr}")
        llm_output = result.stdout.strip()
        try:
            wrapper = json.loads(llm_output)
            payloads = wrapper.get("result", {}).get("payloads", [])
            if payloads:
                return payloads[0].get("text", llm_output)
            return wrapper.get("response", llm_output)
        except json.JSONDecodeError:
            return llm_output
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(
            f"No LLM backend available. Set LLM_COMMAND env var, or provide "
            f"a pre-generated transcript via --transcript-file. Error: {e}"
        )


def generate(
    url: str, fmt: str, length: str, instructions: str, config: dict,
    voice_override: list[str] | None = None,
    transcript_data: dict | None = None,
) -> dict:
    """Generate podcast audio from a URL using the two-stage pipeline.

    Stage 1: Fetch article, classify content, generate transcript via LLM.
             (Skipped if transcript_data is provided.)
    Stage 2: Synthesize audio via TTS fallback chain.

    Args:
        voice_override: explicit voice names to use (skips random selection)
        transcript_data: pre-generated transcript dict (skips LLM call)

    Returns dict with: mp3_path, title, description, duration_seconds, source_url
    """
    from scriptgen import (
        fetch_article, classify_content, build_transcript_prompt,
        parse_transcript_response, FORMAT_INTERVIEW, FORMAT_DISCUSSION, FORMAT_NARRATOR,
    )
    from synthesize import synthesize
    from voices import pick_voices, record_voice_usage

    if transcript_data:
        # Skip Stage 1 -- transcript provided externally (e.g., by Claude)
        _log("=== Skipping Stage 1: Using provided transcript ===")
        transcript = transcript_data
    else:
        # --- Stage 1: Script Generation ---
        _log("=== Stage 1: Script Generation ===")

        article_text = fetch_article(url)

        format_map = {
            "deep-dive": None,
            "brief": None,
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

        length_map = {"short": 5, "default": 15, "long": None}
        length_minutes = length_map.get(length, 15)

        prompt = build_transcript_prompt(
            article_text, podcast_format, url, length_minutes=length_minutes,
        )
        _log(f"Calling LLM for transcript ({len(prompt)} char prompt)...")

        llm_text = _call_llm(prompt)
        transcript = parse_transcript_response(llm_text)

    _log(f"Transcript: {len(transcript['segments'])} segments, "
         f"title={transcript.get('title', 'N/A')!r}")

    # --- Stage 2: Audio Synthesis ---
    _log("=== Stage 2: Audio Synthesis ===")

    num_speakers = len(transcript["speakers"])
    fallback_order = config.get("tts_fallback_order", ["gemini", "azure-openai", "edge"])
    primary_backend = fallback_order[0] if fallback_order else "gemini"

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

    record_voice_usage(voices_used)

    title = transcript.get("title", "")
    if not title or _is_url_or_filename(title):
        title = _clean_filename_title(url)

    podcast_format = transcript.get("format", fmt)
    description = f"Podcast {podcast_format} about: {url}"
    duration = get_duration_seconds(audio_path)

    return {
        "mp3_path": audio_path,
        "title": title,
        "description": description,
        "duration_seconds": duration,
        "source_url": url,
        "backend_used": backend_used,
        "format": podcast_format,
    }


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
                        help="Path to JSON config file")
    parser.add_argument("--transcript-file", default=None,
                        help="Path to pre-generated transcript JSON (skips LLM call)")
    parser.add_argument("--enqueue", action="store_true",
                        help="Queue the job for background processing")
    parser.add_argument("--notification-account", default="+13603069264",
                        help="Signal account phone number for notifications")
    parser.add_argument("--notification-recipient", default=None,
                        help="Signal recipient UUID for notifications")
    parser.add_argument("--voices", default=None,
                        help="Comma-separated voice names to override auto-selection")
    parser.add_argument("--publish", action="store_true", default=True,
                        help="Publish to Azure Blob + RSS (default: true)")
    parser.add_argument("--no-publish", dest="publish", action="store_false",
                        help="Skip publishing (just generate audio)")
    args = parser.parse_args()

    config_path = args.config
    if config_path is None:
        config_path = str(_data_dir() / "config.json")

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

    transcript_data = None
    if args.transcript_file:
        with open(args.transcript_file) as f:
            transcript_data = json.load(f)

    result = generate(
        args.url, args.format, args.length, args.instructions, config,
        voice_override=voice_override,
        transcript_data=transcript_data,
    )

    if args.publish:
        from publish import publish
        pub_result = publish(
            mp3_path=result["mp3_path"],
            title=result["title"],
            description=result["description"],
            duration_seconds=result["duration_seconds"],
            source_url=result["source_url"],
            config=config,
        )
        result.update(pub_result)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
