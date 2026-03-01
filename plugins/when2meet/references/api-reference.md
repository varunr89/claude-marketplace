# When2Meet API Reference

When2Meet has no public API. These endpoints are reverse-engineered from the
website's form submissions and confirmed working as of February 2026.

Base URL: `https://www.when2meet.com`

## 1. Create Event

**Endpoint:** `POST /SaveNewEvent.php`

**Content-Type:** `multipart/form-data` (not URL-encoded)

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `NewEventName` | string | yes | Event title |
| `DateTypes` | string | yes | Always `"SpecificDates"` |
| `PossibleDates` | string | yes | Pipe-delimited dates: `"2026-02-09\|2026-02-11"` |
| `NoEarlierThan` | string | yes | Start hour (0-23), e.g. `"10"` for 10 AM |
| `NoLaterThan` | string | yes | End hour (0-23), e.g. `"18"` for 6 PM |
| `TimeZone` | string | no | IANA timezone, e.g. `"America/Los_Angeles"` |

### Python Example

```python
fields = {
    "NewEventName": (None, "My Event"),
    "DateTypes": (None, "SpecificDates"),
    "PossibleDates": (None, "2026-02-09|2026-02-11|2026-02-12"),
    "NoEarlierThan": (None, "10"),
    "NoLaterThan": (None, "18"),
    "TimeZone": (None, "America/Los_Angeles"),
}
resp = requests.post("https://www.when2meet.com/SaveNewEvent.php",
                     files=fields, allow_redirects=False)
```

### Response

HTTP 200 with HTML body. The body contains JavaScript:

```
window.location='./?34954911-FtY36'
```

**Parsing the event URL:**

```python
m = re.search(r"window\.location\s*=\s*['\"]([^'\"]+)['\"]", resp.text)
path = m.group(1)                    # './?34954911-FtY36'
path = re.sub(r"^\./", "/", path)    # '/?34954911-FtY36'
event_url = f"https://www.when2meet.com{path}"
```

**Extracting the slug and numeric ID:**

```python
slug = re.search(r"\??(\d{5,}-\S+)", path).group(1)  # '34954911-FtY36'
event_id = re.match(r"(\d+)", slug).group(1)          # '34954911'
```

The slug is needed for fetching the event page. The numeric ID is needed for
login and save-availability calls.

---

## 2. Fetch Event Page (Slot Timestamps)

**Endpoint:** `GET /?{slug}`

Example: `GET https://www.when2meet.com/?34954911-FtY36`

### Response

HTML page with embedded JavaScript containing the `TimeOfSlot` array:

```javascript
TimeOfSlot[0]=1770660000;
TimeOfSlot[1]=1770660900;
TimeOfSlot[2]=1770661800;
// ... one entry per 15-minute slot
```

**Parsing:**

```python
resp = requests.get(f"https://www.when2meet.com/?{slug}")
slots = {}
for m in re.finditer(r'TimeOfSlot\[(\d+)\]\s*=\s*(\d+)\s*;', resp.text):
    slots[int(m.group(1))] = int(m.group(2))
ordered_slots = [slots[i] for i in sorted(slots)]
```

### Slot Timestamp Details

- Each timestamp is a Unix timestamp (seconds since epoch)
- Slots are 15 minutes apart (900 seconds)
- The number of slots = days x hours x 4
- Example: 4 dates, 10 AM to 6 PM = 4 x 8 x 4 = 128 slots
- Timestamps respect the event's timezone setting

### Converting Timestamps to Local Time

```python
from datetime import datetime, timezone, timedelta

def ts_to_local(ts, utc_offset_hours):
    tz = timezone(timedelta(hours=utc_offset_hours))
    return datetime.fromtimestamp(ts, tz=tz)

# PST example (UTC-8, before DST in March)
dt = ts_to_local(1770660000, -8)  # 2026-02-09 10:00 PST
```

Note: For dates that may span a DST transition, use `zoneinfo` or `pytz`
instead of a fixed offset.

---

## 3. Login (Sign In as Participant)

**Endpoint:** `POST /ProcessLogin.php`

**Content-Type:** `application/x-www-form-urlencoded`

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Numeric event ID (e.g. `"34954911"`) |
| `name` | string | yes | Display name (e.g. `"Keith"`) |
| `password` | string | yes | Password or `""` for open events |
| `_` | string | yes | Always empty string `""` |

### Python Example

```python
data = {"id": event_id, "name": "Keith", "password": "", "_": ""}
resp = requests.post("https://www.when2meet.com/ProcessLogin.php", data=data)
person_id = resp.text.strip()  # e.g. "140046640"
```

### Response

Plain text body containing just the numeric person ID. Not JSON, not HTML.

### Notes

- No cookies or session tokens are used
- The person ID is the sole authentication for subsequent SaveTimes calls
- Each login creates a new participant entry (calling login twice with the
  same name creates two separate users)

---

## 4. Save Availability

**Endpoint:** `POST /SaveTimes.php`

**Content-Type:** `application/x-www-form-urlencoded`

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `person` | string | yes | Person ID from login response |
| `event` | string | yes | Numeric event ID |
| `slots` | string | yes | ALL slot timestamps, each followed by `%` |
| `availability` | string | yes | Positional `0`/`1` string, one char per slot |
| `_` | string | yes | Always empty string `""` |

### Critical: Send ALL Slots

The `slots` field must contain EVERY slot timestamp from the event (from
`TimeOfSlot`), not just the available ones. The `availability` string is
mapped positionally: character 0 corresponds to the first slot, character 1
to the second, etc.

**Sending only available slots causes silent data corruption.** The server
maps the availability string against the full slot list by position, so
partial slot lists misalign everything.

### Format Details

**slots**: Concatenate all timestamps, each followed by `%`:

```
"1770660000%1770660900%1770661800%..."
```

**availability**: One character per slot, in order:

```
"00001100000000110000..."
```

Where `1` = available, `0` = unavailable.

### Python Example

```python
available_set = set(available_timestamps)

slots_str = "".join(f"{ts}%" for ts in all_event_slots)
avail_str = "".join(
    "1" if ts in available_set else "0"
    for ts in all_event_slots
)

data = {
    "person": person_id,
    "event": event_id,
    "slots": slots_str,
    "availability": avail_str,
    "_": "",
}
requests.post("https://www.when2meet.com/SaveTimes.php", data=data)
```

### Response

HTTP 200 on success. Response body is not meaningful.

---

## 5. Verify Saved Availability

Fetch the event page again and parse the `AvailableAtSlot` array:

```python
resp = requests.get(f"https://www.when2meet.com/?{slug}")

# Parse people
pids = re.findall(r'PeopleIDs\[(\d+)\]\s*=\s*(\d+)', resp.text)
pnames = re.findall(r'PeopleNames\[(\d+)\]\s*=\s*["\x27]([^"\x27]*)["\x27]', resp.text)
pid_to_name = {}
for (idx, pid), (_, name) in zip(pids, pnames):
    pid_to_name[pid] = name

# Parse availability
avail = re.findall(r'AvailableAtSlot\[(\d+)\]\.push\((\d+)\)', resp.text)
for slot_idx_str, person_id in avail:
    ts = slots[int(slot_idx_str)]
    name = pid_to_name.get(person_id, person_id)
    # ts is the Unix timestamp for this available slot
```

---

## Common Patterns

### Mapping Human-Readable Times to Slot Timestamps

Build a lookup from (date, time) to timestamp using the server's `TimeOfSlot`
values:

```python
lookup = {}
for ts in all_slots:
    dt = ts_to_local(ts, utc_offset)
    key = (dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M"))
    lookup[key] = ts

# Then resolve availability:
ts = lookup[("2026-02-09", "11:00")]
```

### DST-Safe Timezone Handling

For events that span a DST boundary, use `zoneinfo` (Python 3.9+):

```python
from zoneinfo import ZoneInfo
from datetime import datetime

tz = ZoneInfo("America/Los_Angeles")
dt = datetime.fromtimestamp(ts, tz=tz)
```

Or with `pytz`:

```python
import pytz
tz = pytz.timezone("America/Los_Angeles")
dt = datetime.fromtimestamp(ts, tz=tz)
```

### Dependencies

Only `requests` is needed. Install in a virtual environment:

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install requests
```
