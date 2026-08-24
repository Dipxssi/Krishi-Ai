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

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BACKEND_ROOT / "data" / "scraped"

BASE_URL = "https://api.weatherapi.com/v1/forecast.json"


def fetch_weather(api_key: str, location: str, days: int) -> dict:
    resp = httpx.get(
        BASE_URL,
        params={"key": api_key, "q": location, "days": days, "aqi": "no"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    forecast_days = data.get("forecast", {}).get("forecastday", [])
    total_rain = sum(d["day"].get("totalprecip_mm", 0) for d in forecast_days)
    avg_temp = sum(d["day"].get("avgtemp_c", 0) for d in forecast_days) / max(len(forecast_days), 1)

    conditions = [d["day"].get("condition", {}).get("text", "") for d in forecast_days]
    rain_days = sum(1 for c in conditions if "rain" in c.lower())
    condition = "rain_likely" if rain_days >= days // 2 else "partly_cloudy"

    return {
        "location": location,
        "forecast_days": days,
        "rainfall_mm": round(total_rain, 1),
        "avg_temp_c": round(avg_temp, 1),
        "condition": condition,
        "daily": [
            {
                "date": d["date"],
                "rain_mm": d["day"].get("totalprecip_mm", 0),
                "max_temp_c": d["day"].get("maxtemp_c"),
                "min_temp_c": d["day"].get("mintemp_c"),
                "condition": d["day"].get("condition", {}).get("text", ""),
            }
            for d in forecast_days
        ],
        "source": "weatherapi.com",
        "is_mock": False,
    }


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
    result = fetch_weather(api_key, args.location, args.days)
    out_path = OUTPUT_DIR / f"weather_{args.location.lower()}_{date.today().isoformat()}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved → {out_path}")
    print(f"  Rainfall: {result['rainfall_mm']} mm, Avg temp: {result['avg_temp_c']}°C, Condition: {result['condition']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
