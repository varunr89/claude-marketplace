#!/usr/bin/env python3
"""Send Signal messages via signal-cli JSON-RPC."""

import json
import os
import time

import requests

SIGNAL_RPC_URL = os.environ.get("SIGNAL_RPC_URL", "http://127.0.0.1:8080/api/v1/rpc")
MAX_RETRIES = 3


def _send_signal(account: str, recipient: str, message: str) -> None:
    """Send a Signal message with retries and exponential backoff."""
    payload = {
        "jsonrpc": "2.0",
        "method": "send",
        "params": {
            "account": account,
            "recipient": [recipient],
            "message": message,
        },
        "id": 1,
    }

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                SIGNAL_RPC_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            if "error" in result:
                raise RuntimeError(f"Signal RPC error: {result['error']}")
            return
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

    raise RuntimeError(f"Failed to send Signal message after {MAX_RETRIES} attempts: {last_error}")


def _title_looks_suspect(title: str) -> bool:
    """Check if a title looks like it wasn't properly resolved."""
    if not title or title == "Untitled Episode":
        return True
    if title.startswith(("http://", "https://")):
        return True
    # Single word with no spaces (likely a cleaned filename)
    if " " not in title and len(title) < 30:
        return True
    return False


def notify_success(
    notification: dict,
    title: str,
    duration_seconds: int,
    spotify_url: str,
) -> None:
    """Notify user of successful podcast generation."""
    minutes = duration_seconds // 60
    warning = ""
    if _title_looks_suspect(title):
        warning = "\n\u26a0\ufe0f Title may need manual fix"
    message = (
        f"Podcast ready!\n"
        f"Title: {title}{warning}\n"
        f"Duration: {minutes} min\n"
        f"Listen: {spotify_url}"
    )
    _send_signal(
        account=notification["account"],
        recipient=notification["recipient"],
        message=message,
    )


def notify_failure(notification: dict, url: str, error: str) -> None:
    """Notify user of failed podcast generation."""
    message = f"Podcast failed for {url}\nError: {error}"
    _send_signal(
        account=notification["account"],
        recipient=notification["recipient"],
        message=message,
    )
