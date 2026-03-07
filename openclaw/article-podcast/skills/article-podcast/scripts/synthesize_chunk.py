#!/usr/bin/env python3
"""CLI wrapper for TTS synthesis. Called by the AI agent as a tool."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from synthesize import synthesize
from generate import get_duration_seconds


def main():
    parser = argparse.ArgumentParser(description="Synthesize audio from a transcript JSON")
    parser.add_argument("--transcript", required=True, help="Path to transcript JSON file")
    parser.add_argument("--backend", default="gemini", choices=["gemini", "azure-openai", "edge"],
                        help="TTS backend to use (default: gemini)")
    parser.add_argument("--voices", default=None,
                        help="Comma-separated voice names (default: auto-select)")
    parser.add_argument("--config", default=None, help="Path to JSON config file")
    parser.add_argument("--fallback", default=None,
                        help="Comma-separated fallback backend order (default: backend only)")
    args = parser.parse_args()

    # Load transcript
    with open(args.transcript) as f:
        transcript = json.load(f)

    # Load config
    config = {}
    if args.config and os.path.exists(args.config):
        with open(args.config) as f:
            config = json.load(f)

    # Resolve voices
    voices = None
    if args.voices:
        voices = [v.strip() for v in args.voices.split(",")]
    else:
        from voices import pick_voices
        num_speakers = len(transcript.get("speakers", [{"id": "S1"}, {"id": "S2"}]))
        voices = pick_voices(args.backend, num_speakers)

    # Resolve fallback order
    fallback_order = [args.backend]
    if args.fallback:
        fallback_order = [b.strip() for b in args.fallback.split(",")]

    audio_path, backend_used, voices_used = synthesize(
        transcript=transcript,
        voices=voices,
        backend=args.backend,
        config=config,
        fallback_order=fallback_order,
    )

    duration = get_duration_seconds(audio_path)

    result = {
        "audio_path": audio_path,
        "backend_used": backend_used,
        "voices_used": voices_used,
        "duration_seconds": duration,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
