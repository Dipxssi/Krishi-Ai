"""Live mandi prices via data.gov.in Agmarknet with TTL cache + weekly DB snapshots."""

from __future__ import annotations

from statistics import median
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.ttl_cache import TtlCache

AGMARKNET_RESOURCE = "9ef84268-d588-465a-a308-a864a43d0070"
BASE_URL = f"https://api.data.gov.in/resource/{AGMARKNET_RESOURCE}"

_cache = TtlCache()


def clear_market_cache() -> None:
    _cache.clear()


def _location_matches(location: str, market: str | None, district: str | None) -> bool:
    loc = (location or "").strip().lower()
    if not loc:
        return False
    fields = [((market or "").strip().lower()), ((district or "").strip().lower())]
    for field in fields:
        if not field:
            continue
        if loc in field or field in loc:
            return True
        # short-token overlap (e.g. "Nashik Road" vs "Nashik")
        loc_parts = [p for p in loc.replace("-", " ").split() if len(p) >= 4]
        field_parts = [p for p in field.replace("-", " ").split() if len(p) >= 4]
        if any(p in field for p in loc_parts) or any(p in loc for p in field_parts):
            return True
    return False


def normalize_agmarknet_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for r in records:
        try:
            modal_q = float(r.get("modal_price") or 0)
        except (TypeError, ValueError):
            continue
        if modal_q <= 0:
            continue
        results.append(
            {
                "commodity": r.get("commodity"),
                "market": r.get("market"),
                "district": r.get("district"),
                "state": r.get("state"),
                "min_price_quintal": float(r.get("min_price") or 0),
                "max_price_quintal": float(r.get("max_price") or 0),
                "modal_price_quintal": modal_q,
                "modal_price_per_kg": round(modal_q / 100.0, 2),
                "arrival_date": r.get("arrival_date"),
                "source": "data.gov.in/agmarknet",
            }
        )
    return results


def fetch_agmarknet_records(
    api_key: str,
    commodity: str,
    *,
    state: str | None = None,
    limit: int = 50,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "api-key": api_key,
        "format": "json",
        "limit": limit,
        "filters[commodity]": commodity.strip().capitalize(),
    }
    if state:
        params["filters[state]"] = state.strip().capitalize()

    owns_client = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        resp = http.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        return normalize_agmarknet_records(data.get("records") or [])
    finally:
        if owns_client:
            http.close()


def select_price_for_location(
    records: list[dict[str, Any]],
    location: str,
) -> dict[str, Any] | None:
    matched = [
        r
        for r in records
        if _location_matches(location, r.get("market"), r.get("district"))
    ]
    if not matched:
        return None

    # Prefer rows that have an arrival_date; keep original order otherwise
    dated = [r for r in matched if r.get("arrival_date")]
    pool = dated or matched
    prices = [float(r["modal_price_per_kg"]) for r in pool]
    current = round(float(median(prices)), 2)
    forecast = round(current * 0.92, 2)
    sources = {str(r.get("source") or "") for r in pool}
    if sources == {"agmarknet_db_snapshot"}:
        source = "agmarknet_db_snapshot"
    else:
        source = "data.gov.in/agmarknet"
    return {
        "current_price": current,
        "forecast_price": forecast,
        "forecast_horizon": "30 days",
        "forecast_uncertainty": "high",
        "unit": "INR/kg",
        "match_count": len(pool),
        "matched_markets": sorted({str(r.get("market")) for r in pool if r.get("market")})[:5],
        "source": source,
        "is_mock": False,
    }


def _try_db_snapshot(crop: str, market: str, date: str) -> dict[str, Any] | None:
    from app.db.mandi_prices import list_fresh_records_for_crop

    settings = get_settings()
    try:
        records = list_fresh_records_for_crop(
            crop,
            max_age_days=int(settings.market_snapshot_max_age_days),
        )
    except Exception:
        return None
    if not records:
        return None
    selected = select_price_for_location(records, market)
    if selected is None:
        return None
    return {
        "crop": crop.strip().lower(),
        "market": market,
        "date": date,
        **selected,
        "source": "agmarknet_db_snapshot",
    }


def _write_through_db(crop: str, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    try:
        from app.db.mandi_prices import upsert_mandi_records

        upsert_mandi_records(records, crop=crop)
    except Exception:
        # Lookup path must not fail if DB write is unavailable.
        return


def fetch_market_price_live(
    crop: str,
    market: str,
    date: str,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any] | None:
    settings = get_settings()
    crop_key = crop.strip().lower()
    cache_key = (crop_key, market.strip().lower())
    cached = _cache.get(cache_key)
    if cached is not None:
        return {**cached, "date": date, "crop": crop_key, "market": market}

    from_db = _try_db_snapshot(crop_key, market, date)
    if from_db is not None:
        _cache.set(cache_key, from_db, float(settings.market_cache_ttl_seconds))
        return from_db

    api_key = (settings.market_api_key or settings.data_gov_api_key or "").strip()
    if not api_key:
        return None

    try:
        records = fetch_agmarknet_records(api_key, crop, client=client)
        selected = select_price_for_location(records, market)
    except Exception:
        return None

    if selected is None:
        return None

    _write_through_db(crop_key, records)

    result = {
        "crop": crop_key,
        "market": market,
        "date": date,
        **selected,
        "source": "data.gov.in/agmarknet",
    }
    _cache.set(cache_key, result, float(settings.market_cache_ttl_seconds))
    return result
