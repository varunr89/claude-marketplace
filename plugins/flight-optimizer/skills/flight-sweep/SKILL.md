---
name: flight-sweep
description: "Batch-collect flight data across date ranges and analyze with filtering, scoring, and HTML viewer generation"
---

# Flight Sweep

A two-phase pipeline for comprehensive flight analysis:

1. **Collect** (flight_sweep_collect.py) -- Fetches flight data from Google Flights and Duffel API across multiple departure dates and trip configurations. Caches raw API responses to disk.
2. **Analyze** (flight_sweep_analyze.py) -- Reads cached data, applies constraint filters, builds trip scenarios, scores and ranks them, and generates an interactive HTML viewer.

## When to use

Use this skill when the user wants to do a broad search across multiple departure dates and trip duration options, compare strategies, and generate a comprehensive ranked report.

## Phase 1: Data Collection

```bash
DUFFEL_API_KEY=<your-key> python3 ${CLAUDE_PLUGIN_ROOT}/scripts/flight_sweep_collect.py
```

**What it does:**
- Iterates over configured departure dates (Fridays and Saturdays)
- For each date, calculates leg dates for all combinations of Europe nights (21/22/23) and India nights (5/6/7)
- Searches both one-way flights (Google Flights + Duffel) and round-trip flights (Duffel only)
- Caches each API response as a JSON file in `flight_cache/`
- Skips already-cached searches for incremental re-runs
- Rate-limits Duffel requests (0.5s delay between calls)

**Cache format:** `{source}_{origin}_{dest}_{date}[_rt_{return_date}].json`

## Phase 2: Analysis

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/flight_sweep_analyze.py
```

**What it does:**
- Reads all cached flight data from `flight_cache/`
- Applies constraint filters:
  - Max 1 stop per leg
  - Max 4-hour layover
  - Single carrier per leg
  - Excludes test/synthetic airlines (e.g., "Duffel Airways")
- Builds scenarios for both strategies (3 one-ways, 2 round-trips)
- Scores each scenario: `flight_cost + (hours * $20) + (stops * $200) + (weekdays * $200)`
- Prints top 10 results to terminal
- Generates `flight_sweep_viewer.html` -- an interactive DataTables-powered HTML viewer with sorting and filtering
- Saves full results to `flight_sweep_results.json`

## Configuration

Both scripts share these configurable constants:

| Constant | Default | Description |
|---|---|---|
| `DEPARTURE_DATES` | Apr 24 - May 8, 2026 | List of departure dates to search |
| `EUROPE_NIGHTS_OPTIONS` | [21, 22, 23] | Europe stay duration options |
| `INDIA_NIGHTS_OPTIONS` | [5, 6, 7] | India stay duration options |
| `MAX_STOPS` | 1 | Maximum stops per leg |
| `MAX_LAYOVER_HOURS` | 4 | Maximum layover duration in hours |
| `COST_PER_HOUR` | 20 | Scoring penalty per hour of travel |
| `COST_PER_STOP` | 200 | Scoring penalty per stop |
| `COST_PER_WEEKDAY` | 200 | Scoring penalty per weekday away |

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DUFFEL_API_KEY` | Yes (collect phase) | Duffel API access token |

## Dependencies

- requests (pip install requests) -- Duffel API calls
- fast-flights (pip install fast-flights) -- Optional Google Flights scraper
