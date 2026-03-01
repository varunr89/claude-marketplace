---
name: flight-search
description: "Search and score multi-leg flight itineraries using Duffel API with cost-duration-stop optimization"
---

# Flight Search

Searches for multi-leg flight itineraries (e.g., Seattle -> Milan -> Hyderabad -> Seattle) using the Duffel API (with optional fast-flights Google Flights scraper fallback). Applies hard constraints and a weighted scoring model to rank results.

## When to use

Use this skill when the user wants to search for flight options across multiple legs with constraint filtering and convenience-adjusted scoring.

## Usage

```bash
DUFFEL_API_KEY=<your-key> python3 ${CLAUDE_PLUGIN_ROOT}/scripts/flight_optimizer.py
```

The script currently targets a specific trip (SEA -> MXP -> HYD -> SEA), but the functions are reusable for any multi-leg itinerary.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DUFFEL_API_KEY` | Yes | Duffel API access token (live or test mode) |

## Constraints model

The optimizer applies hard constraints to filter out unsuitable flights:

- **Max stops**: 1 stop per leg (configurable via `MAX_STOPS`)
- **Max layover**: 4 hours (configurable via `MAX_LAYOVER_HOURS`)
- **Single carrier per leg**: No itineraries with unconnected carriers (comma in airline name)
- **Valid pricing**: Flights with unparseable prices are excluded

## Scoring formula

Each flight leg is scored as:

```
leg_score = price + (duration_hours * $20) + (stops * $200)
```

Complete itineraries add a childcare penalty:

```
total_score = sum(leg_scores) + (weekdays_away * $200)
```

Scoring weights are configurable constants: `COST_PER_HOUR`, `COST_PER_STOP`, `COST_PER_WEEKDAY`.

## Search strategies

The optimizer tries two strategies and ranks all results together:

1. **Three one-way flights** -- Independent one-way searches for each leg
2. **Two round-trips** -- SEA<->MXP and MXP<->HYD as round-trip bookings (often cheaper due to airline RT pricing)

## Output

- Prints top 10 itineraries to stdout with detailed leg information
- Saves raw results to `flight_results_spring2026.json` (top 30 itineraries)

## Dependencies

- requests (pip install requests) -- Duffel API calls
- fast-flights (pip install fast-flights) -- Optional Google Flights scraper fallback
