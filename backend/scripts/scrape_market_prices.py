#!/usr/bin/env python3
"""Scrape mandi prices from data.gov.in Agmarknet API.

Requires MARKET_API_KEY (free from https://data.gov.in).

Usage:
  uv run python scripts/scrape_market_prices.py --crop tomato --state Maharashtra
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BACKEND_ROOT / "data" / "scraped"

AGMARKNET_RESOURCE = "9ef84268-d588-465a-a308-a864a43d0070"
BASE_URL = f"https://api.data.gov.in/resource/{AGMARKNET_RESOURCE}"


def fetch_prices(api_key: str, commodity: str, state: str | None, limit: int = 50) -> list[dict]:
    params = {
        "api-key": api_key,
        "format": "json",
        "limit": limit,
        "filters[commodity]": commodity.capitalize(),
    }
    if state:
        params["filters[state]"] = state.capitalize()

    resp = httpx.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    records = data.get("records", [])
    results = []
    for r in records:
        results.append({
            "commodity": r.get("commodity"),
            "market": r.get("market"),
            "district": r.get("district"),
            "state": r.get("state"),
            "min_price_quintal": float(r.get("min_price", 0)),
            "max_price_quintal": float(r.get("max_price", 0)),
            "modal_price_quintal": float(r.get("modal_price", 0)),
            "modal_price_per_kg": round(float(r.get("modal_price", 0)) / 100, 2),
            "arrival_date": r.get("arrival_date"),
            "source": "data.gov.in/agmarknet",
        })
    return results


def main() -> int:
    import os
    parser = argparse.ArgumentParser()
    parser.add_argument("--crop", default="Tomato")
    parser.add_argument("--state", default=None)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    api_key = os.environ.get("MARKET_API_KEY") or os.environ.get("DATA_GOV_API_KEY")
    if not api_key:
        print("Set MARKET_API_KEY or DATA_GOV_API_KEY env var (free from data.gov.in)")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = fetch_prices(api_key, args.crop, args.state, args.limit)
    out_path = OUTPUT_DIR / f"market_{args.crop.lower()}_{date.today().isoformat()}.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(results)} records → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
