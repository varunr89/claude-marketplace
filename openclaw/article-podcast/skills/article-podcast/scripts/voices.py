#!/usr/bin/env python3
"""Voice pool management and dynamic voice selection."""

import json
import random
from pathlib import Path
from typing import Optional

VOICE_POOLS = {
    "gemini": [
        "Aoede", "Charon", "Enceladus", "Fenrir",
        "Kore", "Leda", "Orbit", "Puck",
    ],
    "azure-openai": [
        "alloy", "ash", "ballad", "coral", "echo",
        "fable", "nova", "onyx", "sage", "shimmer",
        "verse", "marin", "cedar",
    ],
    "edge": [
        "en-US-JennyNeural", "en-US-AriaNeural", "en-US-SaraNeural",
        "en-US-GuyNeural", "en-US-DavisNeural", "en-US-TonyNeural",
        "en-GB-SoniaNeural", "en-GB-RyanNeural",
        "en-AU-NatashaNeural", "en-AU-WilliamNeural",
        "en-IN-NeerjaNeural", "en-IN-PrabhatNeural",
        "en-IE-EmilyNeural", "en-IE-ConnorNeural",
        "en-ZA-LeahNeural", "en-ZA-LukeNeural",
    ],
}

_DEFAULT_HISTORY_PATH = (
    Path.home() / ".openclaw" / "plugins"
    / "openclaw-plugin-article-podcast" / "voice_history.json"
)

MAX_HISTORY = 10  # Track last ~5 episodes (2 voices each)


def load_voice_history(history_path: Optional[str] = None) -> list[str]:
    """Load the list of recently used voice names."""
    path = Path(history_path) if history_path else _DEFAULT_HISTORY_PATH
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def record_voice_usage(
    voices: list[str], history_path: Optional[str] = None
) -> None:
    """Append voices to history and trim to MAX_HISTORY."""
    path = Path(history_path) if history_path else _DEFAULT_HISTORY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    history = load_voice_history(history_path)
    history.extend(voices)
    # Keep only the most recent entries
    history = history[-MAX_HISTORY:]
    path.write_text(json.dumps(history))


def pick_voices(
    backend: str,
    num_speakers: int,
    history_path: Optional[str] = None,
    override: Optional[list[str]] = None,
) -> list[str]:
    """Pick voices from the pool, preferring ones not recently used.

    Args:
        backend: "gemini", "azure-openai", or "edge"
        num_speakers: 1 for solo, 2 for dialogue
        history_path: path to voice_history.json (default: ~/.openclaw/...)
        override: if provided, return these voices directly

    Returns:
        List of voice names (length = num_speakers)
    """
    if override:
        return list(override)

    pool = list(VOICE_POOLS[backend])
    recent = set(load_voice_history(history_path))

    # Partition into unused and recently-used
    unused = [v for v in pool if v not in recent]
    used = [v for v in pool if v in recent]

    # Prefer unused voices, fall back to used if not enough
    candidates = unused if len(unused) >= num_speakers else pool

    selected = random.sample(candidates, min(num_speakers, len(candidates)))
    return selected
