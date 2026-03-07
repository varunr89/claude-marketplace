#!/usr/bin/env python3
"""YouTube parser: extract captions from single videos or playlists via yt-dlp."""

import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Optional
from urllib.parse import parse_qs, urlparse


def _extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from a YouTube URL."""
    parsed = urlparse(url)
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/")
    qs = parse_qs(parsed.query)
    return qs.get("v", [None])[0]


def _is_playlist_url(url: str) -> bool:
    """Check if URL is a YouTube playlist."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "list" in qs:
        return True
    if "/playlist" in parsed.path:
        return True
    return False


def _parse_vtt(vtt_content: str) -> str:
    """Parse VTT subtitle content into clean text, deduplicating repeated lines."""
    lines = []
    prev_line = ""
    for line in vtt_content.split("\n"):
        line = line.strip()
        if not line or line == "WEBVTT" or "-->" in line or re.match(r"^\d+$", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and line != prev_line:
            lines.append(line)
            prev_line = line
    return " ".join(lines)


def _download_captions(video_url: str, work_dir: str) -> tuple[str, str]:
    """Download auto-captions for a video. Returns (title, transcript_text)."""
    info_result = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-download", video_url],
        capture_output=True, text=True, timeout=30,
    )
    title = "Untitled Video"
    if info_result.returncode == 0:
        info = json.loads(info_result.stdout)
        title = info.get("title", title)

    result = subprocess.run(
        ["yt-dlp", "--write-auto-sub", "--sub-lang", "en,en-US",
         "--skip-download", "--sub-format", "vtt",
         "-o", os.path.join(work_dir, "%(id)s"), video_url],
        capture_output=True, text=True, timeout=60,
    )

    vtt_files = [f for f in os.listdir(work_dir) if f.endswith(".vtt")]
    if not vtt_files:
        raise RuntimeError(f"No captions found for {video_url}")

    with open(os.path.join(work_dir, vtt_files[0])) as f:
        vtt_content = f.read()

    return title, _parse_vtt(vtt_content)


def _list_playlist_videos(playlist_url: str) -> list[dict]:
    """List all videos in a playlist."""
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--dump-json", playlist_url],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to list playlist: {result.stderr}")

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        info = json.loads(line)
        vid_url = f"https://www.youtube.com/watch?v={info['id']}"
        videos.append({"url": vid_url, "title": info.get("title", "Untitled")})
    return videos


def parse(source: str) -> dict:
    """Extract captions from YouTube video or playlist."""
    with tempfile.TemporaryDirectory(prefix="yt-parse-") as work_dir:
        if _is_playlist_url(source):
            videos = _list_playlist_videos(source)
            result = subprocess.run(
                ["yt-dlp", "--dump-json", "--no-download", "--playlist-items", "1", source],
                capture_output=True, text=True, timeout=30,
            )
            playlist_title = "YouTube Playlist"
            if result.returncode == 0:
                info = json.loads(result.stdout)
                playlist_title = info.get("playlist_title", info.get("playlist", playlist_title))

            sections = []
            for i, video in enumerate(videos):
                try:
                    title, text = _download_captions(video["url"], work_dir)
                    wc = len(text.split())
                    sections.append({"title": title, "text": text, "word_count": wc, "index": i})
                except Exception as e:
                    print(f"Warning: skipping {video['title']}: {e}", file=sys.stderr)

            total_words = sum(s["word_count"] for s in sections)
            return {
                "source_type": "youtube_playlist",
                "title": playlist_title,
                "metadata": {"source_url": source, "video_count": len(videos)},
                "sections": sections,
                "total_words": total_words,
            }
        else:
            title, text = _download_captions(source, work_dir)
            wc = len(text.split())
            return {
                "source_type": "youtube",
                "title": title,
                "metadata": {"source_url": source},
                "sections": [{"title": title, "text": text, "word_count": wc, "index": 0}],
                "total_words": wc,
            }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    print(json.dumps(parse(args.source), indent=2))


if __name__ == "__main__":
    main()
