#!/usr/bin/env python3
"""Fetch mandi prices from data.gov.in Agmarknet API.

Requires MARKET_API_KEY (free from https://data.gov.in).

Usage:
  uv run python scripts/scrape_market_prices.py --crop tomato --state Maharashtra
  uv run python scripts/scrape_market_prices.py --upsert-db --priority
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

from app.core.config import get_settings  # noqa: E402
from app.db.mandi_prices import upsert_mandi_records  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.services.live_market import fetch_agmarknet_records  # noqa: E402

OUTPUT_DIR = BACKEND_ROOT / "data" / "scraped"

# Crops / states covered by KrishiAi farm tools and demos.
PRIORITY_CROPS = ("Tomato", "Potato", "Maize", "Wheat", "Rice")
PRIORITY_STATES = (
    "Maharashtra",
    "Karnataka",
    "Uttar Pradesh",
    "Punjab",
    "Gujarat",
    "Madhya Pradesh",
)


def _api_key() -> str | None:
    settings = get_settings()
    key = (settings.market_api_key or settings.data_gov_api_key or "").strip()
    if key:
        return key
    return (os.environ.get("MARKET_API_KEY") or os.environ.get("DATA_GOV_API_KEY") or "").strip() or None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crop", default="Tomato")
    parser.add_argument("--state", default=None)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--upsert-db",
        action="store_true",
        help="Write/update rows in mandi_price_snapshots (Neon/SQLite via DATABASE_URL)",
    )
    parser.add_argument(
        "--priority",
        action="store_true",
        help="Fetch PRIORITY_CROPS × PRIORITY_STATES (for weekly job)",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Skip writing JSON under data/scraped/",
    )
    args = parser.parse_args()

    get_settings.cache_clear()
    api_key = _api_key()
    if not api_key:
        print("Set MARKET_API_KEY or DATA_GOV_API_KEY (free from data.gov.in)")
        return 1

    if args.upsert_db:
        init_db()

    jobs: list[tuple[str, str | None]] = []
    if args.priority:
        for crop in PRIORITY_CROPS:
            for state in PRIORITY_STATES:
                jobs.append((crop, state))
    else:
        jobs.append((args.crop, args.state))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total_api = 0
    total_db = 0
    for crop, state in jobs:
        results = fetch_agmarknet_records(api_key, crop, state=state, limit=args.limit)
        total_api += len(results)
        label = f"{crop.lower()}_{(state or 'all').lower()}"
        if not args.no_json:
            out_path = OUTPUT_DIR / f"market_{label}_{date.today().isoformat()}.json"
            out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Saved {len(results)} records → {out_path}")
        if args.upsert_db:
            n = upsert_mandi_records(results, crop=crop)
            total_db += n
            print(f"Upserted {n} DB rows for {crop}" + (f" / {state}" if state else ""))

    if args.upsert_db:
        print(f"Done. API rows={total_api}, DB upserts={total_db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
