#!/usr/bin/env python3
"""Source dispatcher: detect source type, find matching parser, run it."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

PARSERS_DIR = Path(__file__).parent / "parsers"
REGISTRY_PATH = PARSERS_DIR / "_registry.json"


def _load_registry() -> list[dict]:
    with open(REGISTRY_PATH) as f:
        return json.load(f)["patterns"]


def detect_source_type(source: str) -> tuple[str, str]:
    """Detect source type from a URL or file path.

    Returns (type, value) where type is one of:
    - "file_ext": value is the extension (e.g., ".pdf")
    - "url_pattern": value is the matched domain
    - "fallback": value is the source itself
    """
    if not source.startswith(("http://", "https://")):
        ext = Path(source).suffix.lower()
        if ext:
            return ("file_ext", ext)
        return ("fallback", source)

    parsed = urlparse(source)
    hostname = parsed.hostname or ""

    for entry in _load_registry():
        if entry["type"] != "url_pattern":
            continue
        domains = entry["match"].split("|")
        for domain in domains:
            if domain in hostname:
                return ("url_pattern", hostname)

    return ("fallback", source)


def resolve_parser(source_type: str, value: str) -> str | None:
    """Find the parser script for a given source type and value.

    Returns absolute path to parser script, or None if no match.
    """
    for entry in _load_registry():
        if entry["type"] == "fallback" and source_type == "fallback":
            return str(PARSERS_DIR / entry["parser"])

        if entry["type"] == source_type:
            if source_type == "file_ext":
                exts = [e.strip() for e in entry["match"].replace("*", "").split("|")]
                if value in exts:
                    return str(PARSERS_DIR / entry["parser"])
            elif source_type == "url_pattern":
                domains = entry["match"].split("|")
                if any(d in value for d in domains):
                    return str(PARSERS_DIR / entry["parser"])

    return None


def parse(source: str) -> dict:
    """Parse a source and return structured JSON."""
    source_type, value = detect_source_type(source)
    parser_path = resolve_parser(source_type, value)

    if parser_path is None:
        return {
            "status": "no_parser",
            "detected_type": value,
            "raw_input": source,
        }

    result = subprocess.run(
        [sys.executable, parser_path, "--source", source],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Parser {parser_path} failed: {result.stderr}")

    data = json.loads(result.stdout)

    from parsers.contract import validate_parser_output
    if not validate_parser_output(data):
        raise ValueError(f"Parser output from {parser_path} does not match contract")

    return data


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Parse any source into structured JSON")
    parser.add_argument("--source", required=True, help="URL or file path")
    args = parser.parse_args()

    result = parse(args.source)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
