#!/usr/bin/env python3
"""Scrape mandi prices from data.gov.in Agmarknet API.

Requires MARKET_API_KEY (free from https://data.gov.in).

Usage:
  uv run python scripts/scrape_market_prices.py --crop tomato --state Maharashtra
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

from app.services.live_market import fetch_agmarknet_records  # noqa: E402

OUTPUT_DIR = BACKEND_ROOT / "data" / "scraped"


def main() -> int:
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
    results = fetch_agmarknet_records(api_key, args.crop, state=args.state, limit=args.limit)
    out_path = OUTPUT_DIR / f"market_{args.crop.lower()}_{date.today().isoformat()}.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(results)} records → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
