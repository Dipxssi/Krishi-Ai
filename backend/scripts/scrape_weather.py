#!/usr/bin/env python3
"""Fetch weather forecast from WeatherAPI.com and cache locally.

Requires WEATHER_API_KEY (free from https://www.weatherapi.com).

Usage:
  uv run python scripts/scrape_weather.py --location Nashik --days 7
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.live_weather import fetch_weather_from_api  # noqa: E402

OUTPUT_DIR = BACKEND_ROOT / "data" / "scraped"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--location", default="Nashik")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    api_key = os.environ.get("WEATHER_API_KEY")
    if not api_key:
        print("Set WEATHER_API_KEY env var (free from weatherapi.com)")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result = fetch_weather_from_api(api_key, args.location, args.days)
    out_path = OUTPUT_DIR / f"weather_{args.location.lower()}_{date.today().isoformat()}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved → {out_path}")
    print(
        f"  Rainfall: {result['rainfall_mm']} mm, "
        f"Avg temp: {result['avg_temp_c']}°C, Condition: {result['condition']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
