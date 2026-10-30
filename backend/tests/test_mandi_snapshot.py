"""Weekly Agmarknet → DB snapshot: serve from DB, skip stale, write-through on live fetch."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlmodel import select

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.core.config import get_settings
from app.db.mandi_prices import (
    MandiPriceSnapshotRow,
    list_fresh_records_for_crop,
    upsert_mandi_records,
)
from app.db.session import get_session, init_db, reset_engine
from app.services.live_market import clear_market_cache, fetch_market_price_live


@pytest.fixture(autouse=True)
def _db_and_caches(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.delenv("MARKET_API_KEY", raising=False)
    monkeypatch.delenv("DATA_GOV_API_KEY", raising=False)
    get_settings.cache_clear()
    reset_engine()
    init_db()
    clear_market_cache()
    yield
    clear_market_cache()
    get_settings.cache_clear()
    reset_engine()


def _iso_days_ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def test_serve_from_fresh_db_without_api_key():
    upsert_mandi_records(
        [
            {
                "commodity": "Tomato",
                "market": "Nashik",
                "district": "Nashik",
                "state": "Maharashtra",
                "modal_price_per_kg": 40.0,
                "modal_price_quintal": 4000.0,
                "arrival_date": "30/08/2026",
            },
            {
                "commodity": "Tomato",
                "market": "Lasalgaon",
                "district": "Nashik",
                "state": "Maharashtra",
                "modal_price_per_kg": 42.0,
                "modal_price_quintal": 4200.0,
                "arrival_date": "30/08/2026",
            },
        ],
        crop="tomato",
        scraped_at=_iso_days_ago(1),
    )

    out = fetch_market_price_live("tomato", "Nashik", "2026-08-31")
    assert out is not None
    assert out["is_mock"] is False
    assert out["current_price"] == 41.0
    assert out["source"] == "agmarknet_db_snapshot"
    assert out["crop"] == "tomato"


def test_stale_db_skipped_without_api_key():
    upsert_mandi_records(
        [
            {
                "commodity": "Tomato",
                "market": "Nashik",
                "district": "Nashik",
                "state": "Maharashtra",
                "modal_price_per_kg": 40.0,
                "modal_price_quintal": 4000.0,
                "arrival_date": "01/01/2026",
            }
        ],
        crop="tomato",
        scraped_at=_iso_days_ago(10),
    )

    assert list_fresh_records_for_crop("tomato", max_age_days=7) == []
    assert fetch_market_price_live("tomato", "Nashik", "2026-08-31") is None


def test_live_api_write_through_to_db(monkeypatch):
    monkeypatch.setenv("MARKET_API_KEY", "test-market-key")
    get_settings.cache_clear()
    clear_market_cache()

    payload = {
        "records": [
            {
                "commodity": "Tomato",
                "market": "Nashik",
                "district": "Nashik",
                "state": "Maharashtra",
                "min_price": "3500",
                "max_price": "4500",
                "modal_price": "4000",
                "arrival_date": "30/08/2026",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        live = fetch_market_price_live("tomato", "Nashik", "2026-08-31", client=client)

    assert live is not None
    assert live["source"] == "data.gov.in/agmarknet"
    assert live["current_price"] == 40.0

    with get_session() as session:
        rows = list(session.exec(select(MandiPriceSnapshotRow)).all())
    assert len(rows) >= 1
    assert rows[0].crop == "tomato"
    assert rows[0].market == "Nashik"

    clear_market_cache()
    monkeypatch.delenv("MARKET_API_KEY", raising=False)
    get_settings.cache_clear()
    from_db = fetch_market_price_live("tomato", "Nashik", "2026-09-01")
    assert from_db is not None
    assert from_db["source"] == "agmarknet_db_snapshot"
    assert from_db["current_price"] == 40.0
