---
name: When2Meet Scheduling
description: >
  This skill should be used when the user asks to "create a when2meet",
  "set up a when2meet poll", "schedule a meeting poll", "pre-fill availability
  on when2meet", "create a sign-up sheet for meetings", "use when2meet API",
  "automate when2meet", or needs to programmatically create When2Meet events
  and fill in availability for participants. Provides the reverse-engineered
  When2Meet API and a ready-to-run Python script.
version: 0.1.0
---

# When2Meet Scheduling

Programmatically create When2Meet events and pre-fill participant availability
using When2Meet's reverse-engineered HTTP API. This avoids manual data entry
when organizers already know some participants' schedules.

## When to Use

- Creating a When2Meet event from the command line
- Pre-filling known availability for instructors, organizers, or team leads
- Automating recurring scheduling polls
- Any scenario where a When2Meet link needs participants' times baked in

## Core Workflow

### 1. Gather Requirements

Before writing any code, collect from the user:

| Parameter | Example |
|-----------|---------|
| Event name | "Project Meeting Sign-Up" |
| Dates (specific) | Feb 9, 11, 12, 13 2026 |
| Time window | 10:00 AM to 6:00 PM |
| Timezone | America/Los_Angeles |
| Participants + availability | Keith: Mon 11-11:30, Wed 10-10:45... |

### 2. Create the Event

POST multipart form data to `https://www.when2meet.com/SaveNewEvent.php`.

Key fields: `NewEventName`, `DateTypes` ("SpecificDates"), `PossibleDates`
(pipe-delimited YYYY-MM-DD), `NoEarlierThan` / `NoLaterThan` (hours 0-23),
`TimeZone` (IANA name).

The response HTML contains `window.location='./?SLUG'` with the event slug.
Normalize the relative path (strip leading `./`) to build the full URL.

### 3. Fetch Slot Timestamps

GET the event page at `https://www.when2meet.com/?SLUG`. Parse
`TimeOfSlot[n]=<unix_timestamp>;` from the embedded JavaScript. These
timestamps are the canonical slot IDs; never compute them manually.

### 4. Login Each Participant

POST to `https://www.when2meet.com/ProcessLogin.php` with `id` (numeric event
ID), `name`, `password` ("" for open events), and `_` (""). The response body
is the plain-text person ID.

### 5. Save Availability

POST to `https://www.when2meet.com/SaveTimes.php`. **Critical**: send ALL
event slots in the `slots` field (each timestamp followed by `%`), with a
positional `availability` string of `0`s and `1`s marking which slots are
available. The server uses position-based mapping, so sending only available
slots will misalign the data.

Fields: `person`, `event`, `slots`, `availability`, `_` ("").

## Critical Gotchas

1. **Send ALL slots, not just available ones.** `SaveTimes.php` maps the
   `availability` string positionally against the full slot list. Sending a
   subset causes silent misalignment.
2. **Event creation uses multipart/form-data**, not URL-encoded. In Python
   `requests`, use `files=` parameter with `(None, value)` tuples.
3. **Dates are pipe-delimited** YYYY-MM-DD strings, not Unix timestamps.
4. **The redirect path is relative** (e.g. `./?34954911-FtY36`). Strip the
   `./` prefix before constructing the full URL.
5. **No cookies or sessions needed.** The person ID from login is the sole
   auth token for saving availability.
6. **Timezone awareness**: Always fetch `TimeOfSlot` values from the server
   rather than computing timestamps manually. The server handles timezone
   conversion when the event specifies a `TimeZone` field.

## Ready-to-Run Script

A complete, tested Python script is available at:

**`scripts/when2meet_setup.py`**

To customize for a new event, edit the configuration block at the top of the
script: `EVENT_NAME`, `DATES`, `NO_EARLIER_THAN`, `NO_LATER_THAN`,
`TIMEZONE`, and the `PARTICIPANTS` dictionary.

Run with: `python scripts/when2meet_setup.py` (requires `requests` in a venv).

## Additional Resources

### Reference Files

- **`references/api-reference.md`**: Complete When2Meet API documentation
  with all endpoints, field formats, response parsing, and slot timestamp
  details

### Scripts

- **`scripts/when2meet_setup.py`**: Full working script for creating events
  and pre-filling availability. Edit the config block and run.
