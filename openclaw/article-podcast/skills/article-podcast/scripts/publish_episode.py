#!/usr/bin/env python3
"""CLI wrapper for publishing episodes. Called by the AI agent as a tool.

Thin wrapper around publish.py that also loads env vars from the worker env file.
"""

import json
import os
import sys

# Load env vars from worker env file (handles semicolons in connection strings)
ENV_FILE = os.path.expanduser("~/.config/article-podcast-worker/env")
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key, val)

sys.path.insert(0, os.path.dirname(__file__))
from publish import publish, main

if __name__ == "__main__":
    main()
