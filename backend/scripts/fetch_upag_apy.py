#!/usr/bin/env python3
"""Fetch UPAg Area-Production-Yield data and save to data/scraped/.

Requires free UPAg API registration: https://data.upag.gov.in/
Set UPAG_API_USERNAME and UPAG_API_PASSWORD in .env

Usage:
  uv run python scripts/fetch_upag_apy.py
  uv run python scripts/fetch_upag_apy.py --from-year 2023 --to-year 2024
  uv run python scripts/fetch_upag_apy.py --use-snapshot   # copy bundled snapshot to scraped/
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.upag_apy import (  # noqa: E402
    default_snapshot_csv_path,
    fetch_upag_statewise_apy,
    fetch_upag_yields_live,
    save_upag_csv,
    scraped_csv_path,
    upag_login,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch UPAg APY CSV for crop registry build")
    parser.add_argument("--from-year", type=int, default=2024)
    parser.add_argument("--to-year", type=int, default=2024)
    parser.add_argument(
        "--use-snapshot",
        action="store_true",
        help="Copy bundled UPAg snapshot CSV to data/scraped/ (no API credentials needed)",
    )
    args = parser.parse_args()

    get_settings.cache_clear()

    if args.use_snapshot:
        src = default_snapshot_csv_path()
        if not src.exists():
            print(f"Missing snapshot: {src}")
            return 1
        dest = scraped_csv_path()
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"Copied snapshot -> {dest}")
        return 0

    settings = get_settings()
    user = (settings.upag_api_username or "").strip()
    pwd = (settings.upag_api_password or "").strip()
    if not user or not pwd:
        print(
            "Set UPAG_API_USERNAME and UPAG_API_PASSWORD in .env (register at https://data.upag.gov.in/).\n"
            "Or run: uv run python scripts/fetch_upag_apy.py --use-snapshot"
        )
        return 1

    token = upag_login(user, pwd)
    records = fetch_upag_statewise_apy(
        token,
        from_year=args.from_year,
        to_year=args.to_year,
    )
    if not records:
        print("UPAg API returned no records")
        return 1

    out = save_upag_csv(records)
    yields, _ = fetch_upag_yields_live(username=user, password=pwd)
    print(f"Saved {len(records)} UPAg records -> {out}")
    print(f"Parsed {len(yields)} supported crops: {', '.join(sorted(yields.keys()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
