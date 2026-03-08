#!/usr/bin/env python3
"""RSS feed management for podcast episodes."""

import uuid
from datetime import datetime, timezone
from email.utils import formatdate
from xml.etree import ElementTree as ET


ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ET.register_namespace("itunes", ITUNES_NS)


def create_feed(
    title: str,
    description: str,
    author: str,
    feed_url: str,
    image_url: str,
    email: str = "",
    language: str = "en",
) -> str:
    """Create a new empty RSS feed with podcast metadata."""
    rss = ET.Element("rss", {
        "version": "2.0",
    })
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "description").text = description
    ET.SubElement(channel, "language").text = language
    ET.SubElement(channel, "link").text = feed_url

    ET.SubElement(channel, f"{{{ITUNES_NS}}}author").text = author
    owner = ET.SubElement(channel, f"{{{ITUNES_NS}}}owner")
    ET.SubElement(owner, f"{{{ITUNES_NS}}}name").text = author
    if email:
        ET.SubElement(owner, f"{{{ITUNES_NS}}}email").text = email

    if image_url:
        ET.SubElement(channel, f"{{{ITUNES_NS}}}image", {"href": image_url})
        # Also add standard RSS image element
        image_el = ET.SubElement(channel, "image")
        ET.SubElement(image_el, "url").text = image_url
        ET.SubElement(image_el, "title").text = title
        ET.SubElement(image_el, "link").text = feed_url

    ET.SubElement(channel, f"{{{ITUNES_NS}}}explicit").text = "false"
    ET.SubElement(channel, f"{{{ITUNES_NS}}}category", {"text": "Technology"})

    return ET.tostring(rss, encoding="unicode", xml_declaration=True)


def add_episode(
    feed_xml: str,
    title: str,
    description: str,
    audio_url: str,
    duration_seconds: int,
    source_url: str,
    audio_type: str = "audio/mpeg",
) -> str:
    """Add a new episode to the feed, prepended as the first item."""
    root = ET.fromstring(feed_xml)
    channel = root.find("channel")

    item = ET.Element("item")
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "description").text = description
    ET.SubElement(item, "link").text = source_url
    ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = str(uuid.uuid4())
    ET.SubElement(item, "pubDate").text = formatdate(usegmt=True)
    ET.SubElement(item, "enclosure", {
        "url": audio_url,
        "type": audio_type,
        "length": "0",  # updated after upload if size known
    })

    # Format duration as HH:MM:SS
    hours, remainder = divmod(duration_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    ET.SubElement(item, f"{{{ITUNES_NS}}}duration").text = duration_str
    ET.SubElement(item, f"{{{ITUNES_NS}}}summary").text = description

    # Prepend: insert before first existing item, or at end of channel
    existing_items = channel.findall("item")
    if existing_items:
        idx = list(channel).index(existing_items[0])
        channel.insert(idx, item)
    else:
        channel.append(item)

    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def parse_feed(feed_xml: str) -> dict:
    """Parse feed and return metadata and episode count."""
    root = ET.fromstring(feed_xml)
    channel = root.find("channel")
    return {
        "title": channel.find("title").text,
        "episode_count": len(channel.findall("item")),
    }


def list_episodes(feed_xml: str) -> list[dict]:
    """Return a list of episode dicts with title, guid, pubDate, and audio URL."""
    root = ET.fromstring(feed_xml)
    channel = root.find("channel")
    episodes = []
    for item in channel.findall("item"):
        enclosure = item.find("enclosure")
        episodes.append({
            "title": item.findtext("title", ""),
            "guid": item.findtext("guid", ""),
            "pub_date": item.findtext("pubDate", ""),
            "audio_url": enclosure.get("url", "") if enclosure is not None else "",
        })
    return episodes


def remove_episodes(feed_xml: str, titles: list[str]) -> tuple[str, int]:
    """Remove episodes whose titles match any in the given list.

    Returns (updated_xml, count_removed).
    """
    root = ET.fromstring(feed_xml)
    channel = root.find("channel")
    titles_set = set(titles)
    to_remove = [item for item in channel.findall("item")
                 if item.findtext("title", "") in titles_set]
    for item in to_remove:
        channel.remove(item)
    return ET.tostring(root, encoding="unicode", xml_declaration=True), len(to_remove)


def set_episode_season(feed_xml: str, title_pattern: str,
                       season_num: int, episode_num: int | None = None) -> str:
    """Add itunes:season (and optionally itunes:episode) to episodes matching a regex.

    If episode_num is provided, it is assigned to the first match. Subsequent
    matches get episode_num+1, episode_num+2, etc. (ordered by pubDate ascending).
    """
    import re
    from email.utils import parsedate_to_datetime

    root = ET.fromstring(feed_xml)
    channel = root.find("channel")
    regex = re.compile(title_pattern)

    matches = [item for item in channel.findall("item")
               if regex.search(item.findtext("title", ""))]

    # Sort by pubDate ascending so oldest gets the lowest episode number
    def parse_date(item):
        try:
            return parsedate_to_datetime(item.findtext("pubDate", ""))
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    matches.sort(key=parse_date)

    for i, item in enumerate(matches):
        # Remove existing season/episode tags if present
        for tag in [f"{{{ITUNES_NS}}}season", f"{{{ITUNES_NS}}}episode"]:
            existing = item.find(tag)
            if existing is not None:
                item.remove(existing)

        ET.SubElement(item, f"{{{ITUNES_NS}}}season").text = str(season_num)
        if episode_num is not None:
            ET.SubElement(item, f"{{{ITUNES_NS}}}episode").text = str(episode_num + i)

    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def set_feed_type(feed_xml: str, feed_type: str = "serial") -> str:
    """Set the channel-level itunes:type (e.g., 'serial' for season support)."""
    root = ET.fromstring(feed_xml)
    channel = root.find("channel")
    tag = f"{{{ITUNES_NS}}}type"
    existing = channel.find(tag)
    if existing is not None:
        existing.text = feed_type
    else:
        ET.SubElement(channel, tag).text = feed_type
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
