"""Tests for TTL cache and live weather/market clients."""

from __future__ import annotations

import time

import httpx
import pytest

from app.core.config import get_settings
from app.services.live_market import (
    clear_market_cache,
    fetch_market_price_live,
    select_price_for_location,
)
from app.services.live_weather import clear_weather_cache, fetch_weather_live
from app.services.ttl_cache import TtlCache
from app.tools.agriculture import get_market_price, get_weather


@pytest.fixture(autouse=True)
def _clear_caches_and_settings(monkeypatch):
    monkeypatch.delenv("WEATHER_API_KEY", raising=False)
    monkeypatch.delenv("MARKET_API_KEY", raising=False)
    monkeypatch.delenv("DATA_GOV_API_KEY", raising=False)
    get_settings.cache_clear()
    clear_weather_cache()
    clear_market_cache()
    yield
    get_settings.cache_clear()
    clear_weather_cache()
    clear_market_cache()


def test_ttl_cache_expires():
    cache = TtlCache()
    cache.set("k", {"v": 1}, ttl_seconds=0.05)
    assert cache.get("k") == {"v": 1}
    time.sleep(0.06)
    assert cache.get("k") is None


def test_select_price_median_for_location():
    records = [
        {"market": "Nashik", "district": "Nashik", "modal_price_per_kg": 40.0, "arrival_date": "01/01/2026"},
        {"market": "Nashik", "district": "Nashik", "modal_price_per_kg": 50.0, "arrival_date": "02/01/2026"},
        {"market": "Pune", "district": "Pune", "modal_price_per_kg": 99.0, "arrival_date": "02/01/2026"},
    ]
    selected = select_price_for_location(records, "Nashik")
    assert selected is not None
    assert selected["current_price"] == 45.0
    assert selected["is_mock"] is False
    assert selected["source"] == "data.gov.in/agmarknet"


def test_get_weather_mock_without_key():
    out = get_weather("Nashik", 7)
    assert out["is_mock"] is True
    assert out["source"] == "mock_weather_service"


def test_get_market_price_mock_without_key():
    out = get_market_price("tomato", "Nashik", "2026-08-21")
    assert out["is_mock"] is True
    assert out["source"] == "mock_market_service"


def test_live_weather_success(monkeypatch):
    monkeypatch.setenv("WEATHER_API_KEY", "test-weather-key")
    get_settings.cache_clear()

    payload = {
        "forecast": {
            "forecastday": [
                {
                    "date": "2026-08-31",
                    "day": {
                        "totalprecip_mm": 12.5,
                        "avgtemp_c": 28.0,
                        "maxtemp_c": 32.0,
                        "mintemp_c": 24.0,
                        "condition": {"text": "Light rain"},
                    },
                },
                {
                    "date": "2026-09-01",
                    "day": {
                        "totalprecip_mm": 5.0,
                        "avgtemp_c": 27.0,
                        "maxtemp_c": 31.0,
                        "mintemp_c": 23.0,
                        "condition": {"text": "Patchy rain possible"},
                    },
                },
            ]
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "weatherapi.com" in str(request.url)
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        live = fetch_weather_live("Nashik", 2, client=client)
    assert live is not None
    assert live["is_mock"] is False
    assert live["source"] == "weatherapi.com"
    assert live["rainfall_mm"] == 17.5
    assert live["condition"] == "rain_likely"

    out = get_weather("Nashik", 2)
    # without injecting client into get_weather, second call uses cache from live fetch above
    assert out["is_mock"] is False
    assert out["rainfall_mm"] == 17.5


def test_live_weather_http_failure_falls_back(monkeypatch):
    monkeypatch.setenv("WEATHER_API_KEY", "bad-key")
    get_settings.cache_clear()
    clear_weather_cache()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="error")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        live = fetch_weather_live("Nashik", 7, client=client)
    assert live is None
    out = get_weather("Nashik", 7)
    assert out["is_mock"] is True


def test_live_market_success(monkeypatch):
    monkeypatch.setenv("MARKET_API_KEY", "test-market-key")
    get_settings.cache_clear()

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
            },
            {
                "commodity": "Tomato",
                "market": "Lasalgaon",
                "district": "Nashik",
                "state": "Maharashtra",
                "min_price": "3600",
                "max_price": "4600",
                "modal_price": "4200",
                "arrival_date": "30/08/2026",
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "data.gov.in" in str(request.url)
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        live = fetch_market_price_live("tomato", "Nashik", "2026-08-31", client=client)
    assert live is not None
    assert live["is_mock"] is False
    assert live["current_price"] == 41.0  # median of 40 and 42
    assert live["source"] == "data.gov.in/agmarknet"

    out = get_market_price("tomato", "Nashik", "2026-08-31")
    assert out["is_mock"] is False
    assert out["current_price"] == 41.0


def test_live_market_no_location_match_returns_none(monkeypatch):
    monkeypatch.setenv("MARKET_API_KEY", "test-market-key")
    get_settings.cache_clear()
    clear_market_cache()

    payload = {
        "records": [
            {
                "commodity": "Tomato",
                "market": "Bengaluru",
                "district": "Bengaluru",
                "state": "Karnataka",
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
    assert live is None
    out = get_market_price("tomato", "Nashik", "2026-08-31")
    assert out["is_mock"] is True
