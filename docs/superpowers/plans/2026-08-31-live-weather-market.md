# Live Weather & Market Data Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox syntax.

**Goal:** Wire WeatherAPI.com and Agmarknet into tools with TTL cache and mock fallback.

**Architecture:** Shared live clients (`live_weather`, `live_market`) + `ttl_cache`; tools try live then mock; scrape scripts reuse fetch helpers.

**Tech Stack:** Python 3.12, httpx, pydantic-settings, pytest

## Global Constraints

- Never set `is_mock=False` without a successful live payload
- Weather TTL default 3600s; market TTL default 21600s
- Market match: substring on market/district; median modal INR/kg
- Fall back to labeled mock on missing key / HTTP failure / empty matches

---

### Task 1: TTL cache + config knobs

**Files:**
- Create: `backend/app/services/ttl_cache.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_live_data.py`

- [ ] Implement `TtlCache` with `get`, `set`, `clear`
- [ ] Add `weather_cache_ttl_seconds`, `market_cache_ttl_seconds` to Settings
- [ ] Test expiry behavior with monkeypatched time or tiny TTL

### Task 2: Live weather client

**Files:**
- Create: `backend/app/services/live_weather.py`
- Modify: `backend/scripts/scrape_weather.py` (reuse fetch)
- Test: `backend/tests/test_live_data.py`

- [ ] `fetch_weather_live(api_key, location, days) -> dict | None`
- [ ] Cache by `(location.lower(), days)`
- [ ] MockTransport test: success path returns `is_mock=False`

### Task 3: Live market client

**Files:**
- Create: `backend/app/services/live_market.py`
- Modify: `backend/scripts/scrape_market_prices.py`
- Test: `backend/tests/test_live_data.py`

- [ ] `fetch_market_price_live(api_key, crop, market) -> dict | None`
- [ ] Substring filter + median modal/100
- [ ] Empty matches → None

### Task 4: Wire tools

**Files:**
- Modify: `backend/app/tools/agriculture.py`
- Test: `backend/tests/test_v1.py` (existing mock test still passes)
- Test: `backend/tests/test_live_data.py`

- [ ] `get_weather` / `get_market_price` call live clients when keys set
- [ ] On None → existing mock
- [ ] Fix false `is_mock=False` when key set but no live data

### Task 5: Docs + verify

- [ ] Update `backend/README.md` live-data notes
- [ ] `uv run pytest -q` passes
