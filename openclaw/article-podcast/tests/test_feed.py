"""Tests for RSS feed generation and management."""
import os
import sys
from xml.etree import ElementTree as ET

# Add scripts dir to path for direct import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"))

from feed import create_feed, add_episode, parse_feed


def test_create_feed_produces_valid_rss():
    """A new feed has the correct root structure and channel metadata."""
    xml = create_feed(
        title="Test Podcast",
        description="A test feed",
        author="Tester",
        feed_url="https://example.com/feed.xml",
        image_url="https://example.com/cover.jpg",
    )
    root = ET.fromstring(xml)
    assert root.tag == "rss"
    channel = root.find("channel")
    assert channel is not None
    assert channel.find("title").text == "Test Podcast"
    assert channel.find("description").text == "A test feed"


def test_add_episode_prepends_item():
    """Adding an episode puts it at the top of the feed."""
    xml = create_feed(
        title="Test Podcast",
        description="A test feed",
        author="Tester",
        feed_url="https://example.com/feed.xml",
        image_url="https://example.com/cover.jpg",
    )
    updated = add_episode(
        feed_xml=xml,
        title="Episode 1",
        description="First episode",
        audio_url="https://example.com/ep1.mp3",
        duration_seconds=600,
        source_url="https://example.com/article",
    )
    root = ET.fromstring(updated)
    items = root.find("channel").findall("item")
    assert len(items) == 1
    assert items[0].find("title").text == "Episode 1"

    # Add second episode -- should be first in feed
    updated2 = add_episode(
        feed_xml=updated,
        title="Episode 2",
        description="Second episode",
        audio_url="https://example.com/ep2.mp3",
        duration_seconds=1200,
        source_url="https://example.com/article2",
    )
    root2 = ET.fromstring(updated2)
    items2 = root2.find("channel").findall("item")
    assert len(items2) == 2
    assert items2[0].find("title").text == "Episode 2"


def test_parse_feed():
    """parse_feed returns title and episode count."""
    xml = create_feed(
        title="My Podcast",
        description="desc",
        author="Author",
        feed_url="https://example.com/feed.xml",
        image_url="https://example.com/cover.jpg",
    )
    info = parse_feed(xml)
    assert info["title"] == "My Podcast"
    assert info["episode_count"] == 0

    updated = add_episode(
        feed_xml=xml,
        title="Ep 1",
        description="desc",
        audio_url="https://example.com/ep1.mp3",
        duration_seconds=300,
        source_url="https://example.com/article",
    )
    info2 = parse_feed(updated)
    assert info2["episode_count"] == 1
