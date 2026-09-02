# Live Weather & Market Data — Design

**Date:** 2026-08-31  
**Status:** Approved (approach B + matching A + shared clients)

## Goal

Wire real WeatherAPI.com and data.gov.in Agmarknet feeds into `get_weather` and `get_market_price`, with short TTL caching and labeled mock fallback when keys are missing or requests fail.

## Decisions

| Topic | Choice |
|-------|--------|
| Scope | Weather + market in one slice |
| Fetch strategy | On-demand HTTP with in-process TTL cache |
| Weather TTL | 1 hour |
| Market TTL | 6 hours |
| Market match | Substring match on market/district vs FarmContext `location`; median of recent modal prices |
| Failure mode | Fall back to existing labeled mock (`is_mock: true`); never invent unlabeled live numbers |
| Structure | Shared live clients under `app/services/`; tools call them; scrape scripts reuse fetch helpers |

## Architecture

```text
get_weather / get_market_price
        ↓
live_weather.py / live_market.py  (+ ttl_cache.py)
        ↓
httpx → WeatherAPI.com / data.gov.in
        ↓ on miss/error/no key
labeled mock (existing agriculture.py logic)
```

### Components

1. **`app/services/ttl_cache.py`** — simple thread-safe dict cache with TTL  
2. **`app/services/live_weather.py`** — fetch + normalize to `WeatherResult` fields; cache key `(location, forecast_days)`  
3. **`app/services/live_market.py`** — fetch Agmarknet records, filter by location substring, median `modal_price` / 100 → INR/kg; cache key `(crop, market)`  
4. **`agriculture.get_weather` / `get_market_price`** — try live when key set; else mock. Never set `is_mock=False` without a successful live payload  
5. **Scrape scripts** — import shared fetch/normalize helpers so offline scrape stays aligned  

### Config

Existing env vars:

- `WEATHER_API_KEY` → WeatherAPI.com  
- `MARKET_API_KEY` (or `DATA_GOV_API_KEY`) → data.gov.in  

Optional knobs (defaults above): `WEATHER_CACHE_TTL_SECONDS=3600`, `MARKET_CACHE_TTL_SECONDS=21600`.

### Market matching (A)

1. Query Agmarknet filtered by commodity (capitalized crop name).  
2. Keep records where `location.lower()` is contained in `market` or `district` (case-insensitive), or vice versa for short tokens (≥4 chars).  
3. Prefer records with `arrival_date` when present; take up to N recent matches.  
4. `current_price` = median of `modal_price_quintal / 100`.  
5. `forecast_price` = heuristic `current * 0.92` (same as mock; no live forecast API). Label `forecast_uncertainty` as `high` when live current is used (forecast still estimated).  
6. If zero matches → mock fallback + warning path via `is_mock`.

### Weather mapping

Reuse scrape script mapping: sum precip, avg temp, `rain_likely` vs `partly_cloudy`. Source `weatherapi.com`, `is_mock=False`.

### Error handling

- Missing key → mock (no HTTP)  
- HTTP/timeout/parse error → mock; do not raise to agent  
- Empty Agmarknet matches → mock  

### Testing

- Unit tests with `httpx.MockTransport` / monkeypatched clients  
- Assert: no key → `is_mock=True`; success → `is_mock=False` + real source; failure → mock  
- Existing `test_market_price_labeled_mock` keeps passing without keys  

## Out of scope

- Persistent disk cache / Redis  
- Background refresh worker  
- Full geo / mandi gazetteer  
- Live multi-day price forecast models  
