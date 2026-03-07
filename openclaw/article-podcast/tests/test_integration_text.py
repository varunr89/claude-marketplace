"""Integration test: parse_source.py dispatches to text parser for .txt and .md files."""
import json
import os
import subprocess
import sys

import pytest

SCRIPTS = os.path.join(
    os.path.dirname(__file__), "..", "skills", "article-podcast", "scripts"
)
VENV_PYTHON = os.path.join(
    os.path.dirname(__file__), "..", "skills", "article-podcast", "venv", "bin", "python3"
)


def _run_parse_source(source_path: str) -> dict:
    """Run parse_source.py as a subprocess and return parsed JSON."""
    python = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
    result = subprocess.run(
        [python, os.path.join(SCRIPTS, "parse_source.py"), "--source", source_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"parse_source.py failed: {result.stderr}"
    return json.loads(result.stdout)


def test_plain_text_end_to_end(tmp_path):
    """A .txt file should be dispatched to text parser and return valid output."""
    txt = tmp_path / "sample.txt"
    txt.write_text("This is a simple test document for integration testing. " * 30)

    output = _run_parse_source(str(txt))

    assert output["source_type"] == "text"
    assert output["title"] == "Sample"
    assert len(output["sections"]) == 1
    assert output["total_words"] > 0
    assert "sections" in output
    assert "metadata" in output


def test_markdown_end_to_end(tmp_path):
    """A .md file with headings should be split into multiple sections."""
    md = tmp_path / "guide.md"
    md.write_text(
        "# Guide\n\n"
        "## Getting Started\n\nFirst, install the dependencies.\n\n"
        "## Configuration\n\nSet up your config file.\n\n"
        "## Usage\n\nRun the main command.\n"
    )

    output = _run_parse_source(str(md))

    assert output["source_type"] == "text"
    assert len(output["sections"]) >= 3
    section_titles = [s["title"] for s in output["sections"]]
    assert "Getting Started" in section_titles
    assert "Configuration" in section_titles
    assert "Usage" in section_titles
