#!/usr/bin/env python3
"""
Create a When2Meet event and pre-fill participant availability.

Usage:
    1. Edit the CONFIGURATION section below with your event details
    2. Run: python when2meet_setup.py
    3. Share the printed URL with participants

Requires: pip install requests
"""

import re
import requests
from datetime import datetime
from zoneinfo import ZoneInfo


# == CONFIGURATION ==========================================================
# Edit this section for each new event.

EVENT_NAME = "Project Meeting Sign-Up"

# Dates in YYYY-MM-DD format (skip any days with no slots)
DATES = ["2026-02-09", "2026-02-11", "2026-02-12", "2026-02-13"]

# Time window (hours, 0-23)
NO_EARLIER_THAN = 10  # 10:00 AM
NO_LATER_THAN = 18    # 6:00 PM

# IANA timezone name (handles DST transitions automatically)
TIMEZONE = "America/Los_Angeles"

# Participant availability: {name: {date: [24h time strings]}}
# Times are 15-minute slots in the event's local timezone.
PARTICIPANTS = {
    "Keith": {
        "2026-02-09": ["11:00", "11:15", "11:30"],
        "2026-02-11": [
            "10:00", "10:15", "10:30", "10:45",
            "13:00", "13:15", "13:30", "13:45", "14:00",
        ],
        "2026-02-13": [
            "11:00", "11:15", "11:30",
            "13:15", "13:30", "13:45", "14:00",
        ],
    },
    "David": {
        "2026-02-11": ["13:30", "13:45", "14:00", "14:15", "17:00"],
        "2026-02-13": ["13:30", "13:45", "14:00", "14:15", "14:45", "15:00"],
    },
    "Akshay": {
        "2026-02-12": [
            "14:00", "14:15", "14:30", "14:45",
            "15:00", "15:15", "15:30", "15:45",
            "16:00", "16:15", "16:30", "16:45",
            "17:00", "17:15", "17:30", "17:45",
        ],
    },
}

# == END CONFIGURATION ======================================================


BASE_URL = "https://www.when2meet.com"


def ts_to_local(ts: int) -> datetime:
    """Convert Unix timestamp to datetime in the configured timezone."""
    return datetime.fromtimestamp(ts, tz=ZoneInfo(TIMEZONE))


def create_event() -> tuple:
    """Create event via SaveNewEvent.php. Returns (event_url, event_id, slug)."""
    url = f"{BASE_URL}/SaveNewEvent.php"

    # Must use multipart/form-data (files= in requests)
    fields = {
        "NewEventName": (None, EVENT_NAME),
        "DateTypes": (None, "SpecificDates"),
        "PossibleDates": (None, "|".join(DATES)),
        "NoEarlierThan": (None, str(NO_EARLIER_THAN)),
        "NoLaterThan": (None, str(NO_LATER_THAN)),
        "TimeZone": (None, TIMEZONE),
    }

    print(f"Creating event: {EVENT_NAME}")
    print(f"  Dates: {', '.join(DATES)}")
    print(f"  Hours: {NO_EARLIER_THAN}:00 - {NO_LATER_THAN}:00")

    resp = requests.post(url, files=fields, allow_redirects=False)

    # Extract redirect path from JS: window.location='./?SLUG'
    m = re.search(r"window\.location\s*=\s*['\"]([^'\"]+)['\"]", resp.text)
    if not m:
        if "Location" in resp.headers:
            path = resp.headers["Location"]
        else:
            raise RuntimeError(
                f"Could not find event URL. Response:\n{resp.text[:2000]}"
            )
    else:
        path = m.group(1)

    # Normalize relative path: './?SLUG' -> '/?SLUG'
    path = re.sub(r"^\./", "/", path)
    if not path.startswith("/"):
        path = "/" + path

    event_url = f"{BASE_URL}{path}"

    m = re.search(r"\??(\d{5,}-\S+)", path)
    if not m:
        raise RuntimeError(f"Could not parse slug from: {path}")
    slug = m.group(1)
    event_id = re.match(r"(\d+)", slug).group(1)

    print(f"  URL:  {event_url}")
    print(f"  ID:   {event_id}")
    return event_url, event_id, slug


def fetch_slot_timestamps(slug: str) -> list:
    """GET event page and parse TimeOfSlot[n]=<ts>; from embedded JS."""
    print(f"\nFetching slot timestamps...")
    resp = requests.get(f"{BASE_URL}/?{slug}")

    slots = {}
    for m in re.finditer(r"TimeOfSlot\[(\d+)\]\s*=\s*(\d+)\s*;", resp.text):
        slots[int(m.group(1))] = int(m.group(2))

    if not slots:
        raise RuntimeError("No TimeOfSlot entries found on event page")

    ordered = [slots[i] for i in sorted(slots)]
    first = ts_to_local(ordered[0])
    last = ts_to_local(ordered[-1])
    print(f"  {len(ordered)} slots: {first:%Y-%m-%d %H:%M} to {last:%Y-%m-%d %H:%M}")
    return ordered


def login_user(event_id: str, name: str) -> str:
    """Sign in via ProcessLogin.php. Returns person ID (plain text)."""
    data = {"id": event_id, "name": name, "password": "", "_": ""}
    resp = requests.post(f"{BASE_URL}/ProcessLogin.php", data=data)
    person_id = resp.text.strip()
    print(f"  Logged in as '{name}' (person_id={person_id})")
    return person_id


def save_availability(
    event_id: str,
    person_id: str,
    name: str,
    available_ts: list,
    all_slots: list,
) -> None:
    """POST all slots with positional 0/1 availability to SaveTimes.php."""
    available_set = set(available_ts)

    slots_str = "".join(f"{ts}%" for ts in all_slots)
    avail_str = "".join("1" if ts in available_set else "0" for ts in all_slots)
    n = avail_str.count("1")

    data = {
        "person": person_id,
        "event": event_id,
        "slots": slots_str,
        "availability": avail_str,
        "_": "",
    }

    resp = requests.post(f"{BASE_URL}/SaveTimes.php", data=data)
    print(f"  Saved {n}/{len(all_slots)} slots for '{name}' (HTTP {resp.status_code})")


def resolve_timestamps(schedule: dict, all_slots: list) -> list:
    """Map {date: [time, ...]} to slot timestamps using server data."""
    lookup = {}
    for ts in all_slots:
        dt = ts_to_local(ts)
        lookup[(dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M"))] = ts

    result = []
    for date_str, times in sorted(schedule.items()):
        for t in times:
            key = (date_str, t)
            if key in lookup:
                result.append(lookup[key])
            else:
                print(f"  WARNING: no slot for {date_str} {t}")
    return result


def main():
    event_url, event_id, slug = create_event()
    all_slots = fetch_slot_timestamps(slug)

    for name, schedule in PARTICIPANTS.items():
        print(f"\n--- {name} ---")
        person_id = login_user(event_id, name)
        available_ts = resolve_timestamps(schedule, all_slots)
        save_availability(event_id, person_id, name, available_ts, all_slots)

    print(f"\n{'=' * 60}")
    print(f"Event ready: {event_url}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
