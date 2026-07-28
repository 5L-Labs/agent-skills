---
name: car_tracker
description: Publishes a daily bulletin of new arrivals and cheapest listings for specified vehicle trims on the market, tracking seen units in a state file.
version: 1.1.0
author: Antigravity Agent
license: MIT
metadata:
  hermes:
    tags: [monitoring, tracking, daily-bulletin, visor-api, auto-pricing]
---

# Daily Car Tracker Skill

This skill tracks and publishes a daily bulletin of new arrivals and cheapest active listings for your monitored vehicle target profiles. It compares fresh API listings against a local database of already-seen VINs (`data/seen_listings.json`) to identify brand-new inventory alerts as they hit the market.

## Setup & Credentials

Configure the following environment variables or add them to your `.env` file:
*   `VISOR.VIN_API_KEY` (or `VISOR_API_KEY`): Required. Bearer token to fetch live listings.

## Target Config

The tracker monitors target profiles specified in `config/target_profiles.json` (or passed via `--trims`). If this file is missing, it automatically falls back to default monitored targets:
1.  **Toyota Grand Highlander (Hybrid Limited AWD)** — Baseline OTD Target: $58,450.85
2.  **Toyota Grand Highlander (Hybrid Nightshade AWD)** — Baseline OTD Target: $56,109.95
3.  **Chrysler Pacifica (Pinnacle AWD)** — Baseline OTD Target: TBD
4.  **Lexus TX (350 AWD)** — Baseline OTD Target: TBD

### Target Profiles Config Schema (`config/target_profiles.json`)
```json
{
  "grand_highlander_hybrid_limited_awd": {
    "key": "grand_highlander_hybrid_limited_awd",
    "year": 2026,
    "make": "Toyota",
    "model": "Grand Highlander",
    "trim": "Hybrid Limited AWD",
    "target_otd_price": 58450.85,
    "sample_vin": "5TDACAB53TS25G407",
    "must_haves": [
      "Hybrid powertrain",
      "AWD",
      "Limited trim",
      "Panoramic Moonroof",
      "Panoramic View Monitor (360 Cam)",
      "7-Passenger Seating (Captain's Chairs)"
    ],
    "required_trim_keywords": ["LIMITED"],
    "requires_awd": true,
    "requires_hybrid": true
  }
}
```
*   **`year`**: Strictly constrains matching to vehicles matching the specified model year.
*   **`must_haves`**: Defines the required and optional equipment criteria evaluated for the `Features (C/O)` summary count column.

## How to Run

Execute the tool via Python:

```bash
python research/car_tracker/scripts/publish_deals.py
```

### Output Format & Rules

Running `publish_deals.py` generates a structured Markdown bulletin with:
*   **🆕 New Arrivals (Since Last Check)**: Unseen listings first observed since the previous tracker run, sorted by proximity/distance to Yonkers, NY coordinates.
*   **🏆 Top 5 Cheapest Active Deals**: Active market deals sorted by listed price.
*   **Columns**: `Loc / Dist` | `Price (% off MSRP)` | `Delta` | `Color` | `Features (C/O)` | `Visor Link` | `Dealer Site`
    *   **`Delta`**: Market delta relative to the cheapest active listing on the market (`+$0`, `+$1,500`). Baseline OTD target prices are displayed in the profile headers.
    *   **`Color`**: Algorithmic paint abbreviation (first 3 letters per word for multi-word paints, e.g. `WinChiPea`; first 6 letters for single-word paints, e.g. `Cement`).
*   **Details & State Caching**: Vehicle colors, MSRPs, and feature summary counts (`C: X/Total | O: Y/Total`) are cached locally in `data/seen_listings.json` for zero-latency execution.
