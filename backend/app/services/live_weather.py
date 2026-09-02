"""Live weather via WeatherAPI.com with TTL cache."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.services.ttl_cache import TtlCache

BASE_URL = "https://api.weatherapi.com/v1/forecast.json"

_cache = TtlCache()


def clear_weather_cache() -> None:
    _cache.clear()


def normalize_weather_payload(data: dict[str, Any], location: str, days: int) -> dict[str, Any]:
    forecast_days = data.get("forecast", {}).get("forecastday", [])
    total_rain = sum(d["day"].get("totalprecip_mm", 0) for d in forecast_days)
    avg_temp = sum(d["day"].get("avgtemp_c", 0) for d in forecast_days) / max(len(forecast_days), 1)

    conditions = [d["day"].get("condition", {}).get("text", "") for d in forecast_days]
    rain_days = sum(1 for c in conditions if "rain" in c.lower())
    condition = "rain_likely" if rain_days >= max(days // 2, 1) else "partly_cloudy"

    return {
        "location": location,
        "forecast_days": days,
        "rainfall_mm": round(float(total_rain), 1),
        "avg_temp_c": round(float(avg_temp), 1),
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


def fetch_weather_from_api(
    api_key: str,
    location: str,
    days: int,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    owns_client = client is None
    http = client or httpx.Client(timeout=15.0)
    try:
        resp = http.get(
            BASE_URL,
            params={"key": api_key, "q": location, "days": days, "aqi": "no"},
        )
        resp.raise_for_status()
        return normalize_weather_payload(resp.json(), location, days)
    finally:
        if owns_client:
            http.close()


def fetch_weather_live(
    location: str,
    forecast_days: int = 7,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any] | None:
    settings = get_settings()
    api_key = (settings.weather_api_key or "").strip()
    if not api_key:
        return None

    cache_key = (location.strip().lower(), int(forecast_days))
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        result = fetch_weather_from_api(api_key, location, forecast_days, client=client)
    except Exception:
        return None

    _cache.set(cache_key, result, float(settings.weather_cache_ttl_seconds))
    return result
