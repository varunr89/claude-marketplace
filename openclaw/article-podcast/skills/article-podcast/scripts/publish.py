#!/usr/bin/env python3
"""Upload podcast episode to Azure and update RSS feed."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from azure.storage.blob import BlobServiceClient, ContentSettings

# Add parent for feed module import
sys.path.insert(0, os.path.dirname(__file__))
from feed import add_episode, create_feed


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:80]


AUDIO_TYPES = {
    ".mp3": ("audio/mpeg", ".mp3"),
    ".m4a": ("audio/x-m4a", ".m4a"),
    ".mp4": ("audio/x-m4a", ".m4a"),
}


def detect_audio_type(file_path: str) -> tuple[str, str]:
    """Detect audio content type and extension from file contents."""
    with open(file_path, "rb") as f:
        header = f.read(12)
    # MP4/M4A files start with ftyp box
    if b"ftyp" in header[:12]:
        return "audio/x-m4a", ".m4a"
    return "audio/mpeg", ".mp3"


def publish(
    mp3_path: str,
    title: str,
    description: str,
    duration_seconds: int,
    source_url: str,
    config: dict,
) -> dict:
    """Upload audio and update RSS feed. Returns public URLs."""

    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    if not conn_str:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING not set")

    container = config.get("azure_container", "podcasts")
    feed_url = config["feed_url"]
    account = config["azure_storage_account"]
    base_url = f"https://{account}.blob.core.windows.net/{container}"

    blob_service = BlobServiceClient.from_connection_string(conn_str)
    container_client = blob_service.get_container_client(container)

    # Detect audio format and upload
    content_type, ext = detect_audio_type(mp3_path)
    slug = slugify(title)
    blob_name = f"episodes/{slug}{ext}"
    audio_url = f"{base_url}/{blob_name}"

    with open(mp3_path, "rb") as f:
        container_client.upload_blob(
            blob_name,
            f,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )

    # Download or create feed.xml
    feed_blob = container_client.get_blob_client("feed.xml")
    try:
        feed_xml = feed_blob.download_blob().readall().decode("utf-8")
    except Exception:
        # First episode -- create the feed
        feed_xml = create_feed(
            title=config.get("feed_title", "My Podcast"),
            description=config.get("feed_description", "AI-generated podcast"),
            author=config.get("feed_author", ""),
            feed_url=feed_url,
            image_url=config.get("feed_image_url", ""),
        )

    # Add episode
    updated_feed = add_episode(
        feed_xml=feed_xml,
        title=title,
        description=description,
        audio_url=audio_url,
        duration_seconds=duration_seconds,
        source_url=source_url,
        audio_type=content_type,
    )

    # Upload updated feed
    feed_blob.upload_blob(
        updated_feed.encode("utf-8"),
        overwrite=True,
        content_settings=ContentSettings(content_type="application/rss+xml"),
    )

    return {
        "audio_url": audio_url,
        "feed_url": feed_url,
    }


def main():
    parser = argparse.ArgumentParser(description="Publish podcast episode")
    parser.add_argument("--mp3", required=True, help="Path to MP3 file")
    parser.add_argument("--title", required=True, help="Episode title")
    parser.add_argument("--description", required=True, help="Episode description")
    parser.add_argument("--duration", required=True, type=int,
                        help="Duration in seconds")
    parser.add_argument("--source-url", required=True, help="Original article URL")
    parser.add_argument("--config", required=True, help="Path to JSON config file")
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    result = publish(
        mp3_path=args.mp3,
        title=args.title,
        description=args.description,
        duration_seconds=args.duration,
        source_url=args.source_url,
        config=config,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
