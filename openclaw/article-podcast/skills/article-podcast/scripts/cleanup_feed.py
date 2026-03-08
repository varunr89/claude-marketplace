#!/usr/bin/env python3
"""One-off script to clean up test episodes and organize the feed into seasons.

Usage:
    python cleanup_feed.py --dry-run   # Preview changes (default)
    python cleanup_feed.py --apply     # Push changes to Azure
"""

import argparse
import os
import sys

from azure.storage.blob import BlobServiceClient, ContentSettings

sys.path.insert(0, os.path.dirname(__file__))
from feed import (
    list_episodes,
    remove_episodes,
    set_episode_season,
    set_feed_type,
)

# Load env vars from worker env file
ENV_FILE = os.path.expanduser("~/.config/article-podcast-worker/env")
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key, val)

# --- Configuration ---

CONTAINER = "podcasts"

TEST_EPISODE_TITLES = [
    "Deep RL Intro (Azure: fable/shimmer)",
    "Deep RL Intro (Azure: nova/onyx)",
    "Deep RL Intro (Edge: Jenny/Aria)",
    "Deep RL Intro (Azure: alloy/echo)",
    "Deep RL Intro (Edge: William/Natasha)",
    "Deep RL Intro (Edge: Ryan/Sonia)",
    "Deep RL Intro (Gemini: Fenrir/Leda)",
    "Deep RL Intro (Gemini: Charon/Aoede)",
    "Deep RL Intro (Gemini: Puck/Kore)",
]

# Season definitions: (season_num, name, title_regex)
SEASONS = [
    (1, "AOSA Vol 1", r"Architecture of Open Source Applications \(Volume 1\)"),
    (2, "AOSA Vol 2", r"Architecture of Open Source Applications \(Volume 2\)"),
    (3, "AOSA Performance", r"Performance of Open Source Software"),
    (4, "500 Lines or Less", r"500 Lines or Less"),
    (5, "Stanford CS234", r"Stanford CS234"),
    (6, "Sutton & Barto RL", r"Reinforcement Learning \(\d+/13\)"),
    (7, "Netflix TechBlog", r"Netflix"),
]

# Articles season is everything that doesn't match the above.
ARTICLES_SEASON = 8


def get_container_client():
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    if not conn_str:
        print("ERROR: AZURE_STORAGE_CONNECTION_STRING not set")
        sys.exit(1)
    blob_service = BlobServiceClient.from_connection_string(conn_str)
    return blob_service.get_container_client(CONTAINER)


def blob_name_from_url(audio_url: str) -> str:
    """Extract blob name (e.g., episodes/slug.m4a) from full Azure URL."""
    # URL format: https://account.blob.core.windows.net/podcasts/episodes/slug.ext
    parts = audio_url.split(f"/{CONTAINER}/", 1)
    return parts[1] if len(parts) == 2 else ""


def main():
    parser = argparse.ArgumentParser(description="Clean up podcast feed and organize seasons")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True,
                       help="Preview changes without modifying Azure (default)")
    group.add_argument("--apply", action="store_true",
                       help="Apply changes to Azure")
    args = parser.parse_args()
    apply = args.apply

    container_client = get_container_client()

    # 1. Download current feed
    print("Downloading feed.xml...")
    feed_blob = container_client.get_blob_client("feed.xml")
    feed_xml = feed_blob.download_blob().readall().decode("utf-8")

    episodes_before = list_episodes(feed_xml)
    print(f"Found {len(episodes_before)} episodes in feed\n")

    # 2. Identify test episode audio blobs to delete
    test_titles_set = set(TEST_EPISODE_TITLES)
    blobs_to_delete = []
    for ep in episodes_before:
        if ep["title"] in test_titles_set:
            blob_name = blob_name_from_url(ep["audio_url"])
            if blob_name:
                blobs_to_delete.append(blob_name)

    # 3. Remove test episodes from feed
    print("--- Removing test episodes ---")
    feed_xml, removed = remove_episodes(feed_xml, TEST_EPISODE_TITLES)
    print(f"Removed {removed} test episodes from feed")
    for title in TEST_EPISODE_TITLES:
        print(f"  - {title}")

    print(f"\nAudio blobs to delete: {len(blobs_to_delete)}")
    for blob in blobs_to_delete:
        print(f"  - {blob}")

    # 4. Set channel type to serial
    print("\n--- Setting feed type to serial ---")
    feed_xml = set_feed_type(feed_xml, "serial")

    # 5. Assign seasons
    print("\n--- Assigning seasons ---")
    import re
    remaining = list_episodes(feed_xml)
    assigned_titles = set()

    for season_num, season_name, pattern in SEASONS:
        regex = re.compile(pattern)
        matches = [ep for ep in remaining if regex.search(ep["title"])]
        if matches:
            feed_xml = set_episode_season(feed_xml, pattern, season_num, episode_num=1)
            for ep in matches:
                assigned_titles.add(ep["title"])
            print(f"Season {season_num} ({season_name}): {len(matches)} episodes")
            for ep in matches:
                print(f"    {ep['title']}")

    # Season 6: Articles -- everything not yet assigned
    unassigned = [ep for ep in remaining if ep["title"] not in assigned_titles]
    if unassigned:
        # Build a regex that matches any of the unassigned titles exactly
        escaped = [re.escape(ep["title"]) for ep in unassigned]
        articles_pattern = "^(?:" + "|".join(escaped) + ")$"
        feed_xml = set_episode_season(feed_xml, articles_pattern, ARTICLES_SEASON, episode_num=1)
        print(f"Season {ARTICLES_SEASON} (Articles): {len(unassigned)} episodes")
        for ep in unassigned:
            print(f"    {ep['title']}")

    # 6. Summary
    episodes_after = list_episodes(feed_xml)
    print(f"\n--- Summary ---")
    print(f"Episodes before: {len(episodes_before)}")
    print(f"Episodes after:  {len(episodes_after)}")
    print(f"Removed:         {removed}")
    print(f"Blobs to delete: {len(blobs_to_delete)}")

    if not apply:
        print("\n[DRY RUN] No changes made. Use --apply to push changes to Azure.")
        return

    # 7. Apply changes
    print("\n--- Applying changes ---")

    # Upload updated feed
    print("Uploading updated feed.xml...")
    feed_blob.upload_blob(
        feed_xml.encode("utf-8"),
        overwrite=True,
        content_settings=ContentSettings(content_type="application/rss+xml"),
    )
    print("  Done.")

    # Delete test audio blobs
    for blob_name in blobs_to_delete:
        print(f"Deleting blob: {blob_name}...")
        try:
            container_client.delete_blob(blob_name)
            print("  Deleted.")
        except Exception as e:
            print(f"  Warning: {e}")

    print("\nAll changes applied successfully.")


if __name__ == "__main__":
    main()
