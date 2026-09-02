"""Crop yield data: UPAg CSV/API, government reference, optional data.gov.in API."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any

import httpx

from app.core.config import get_settings

HECTARES_PER_ACRE = 2.47105381

# Configurable OGD resource for state/district APY when published on data.gov.in
DEFAULT_APY_RESOURCE_ID = "ead44f5f-6471-48ec-a488-4b5894302aaa"

_CROP_NAME_ALIASES: dict[str, list[str]] = {
    "tomato": ["tomato", "tomatoes"],
    "potato": ["potato", "potatoes"],
    "onion": ["onion", "onions"],
    "maize": ["maize", "corn"],
    "wheat": ["wheat"],
    "rice": ["rice", "paddy"],
    "cotton": ["cotton", "cotton lint"],
}


def _sources_dir() -> Path:
    return Path(get_settings().knowledge_dir).parent / "sources"


def _reference_path() -> Path:
    return _sources_dir() / "apy_national_reference.json"


def kg_per_hectare_to_kg_per_acre(kg_per_ha: float) -> float:
    return round(float(kg_per_ha) / HECTARES_PER_ACRE, 1)


def load_apy_reference() -> dict[str, Any]:
    path = _reference_path()
    if not path.exists():
        raise FileNotFoundError(f"Missing government APY reference: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if "crops" not in data:
        raise ValueError(f"Invalid APY reference format in {path}")
    return data


def reference_yield_by_crop() -> dict[str, dict[str, Any]]:
    """Return per-crop yield facts from bundled DAC&FW reference data."""
    ref = load_apy_reference()
    out: dict[str, dict[str, Any]] = {}
    for crop_id, row in ref.get("crops", {}).items():
        kg_ha = float(row["yield_kg_per_hectare"])
        out[crop_id] = {
            "crop_id": crop_id,
            "official_name": row.get("official_name", crop_id),
            "yield_kg_per_hectare": kg_ha,
            "expected_yield_kg_per_acre": kg_per_hectare_to_kg_per_acre(kg_ha),
            "source_organization": ref.get("source_organization"),
            "dataset_title": ref.get("dataset_title"),
            "source_year": ref.get("year_label"),
            "reference_urls": list(ref.get("reference_urls", [])),
            "data_origin": "government_reference_file",
        }
    return out


def _match_crop_id(name: str | None) -> str | None:
    if not name:
        return None
    lowered = str(name).strip().lower()
    for crop_id, aliases in _CROP_NAME_ALIASES.items():
        if lowered in aliases or lowered == crop_id:
            return crop_id
        if any(alias in lowered for alias in aliases):
            return crop_id
    return None


def _parse_yield_value(record: dict[str, Any]) -> float | None:
    """Best-effort parse of productivity from heterogeneous OGD field names."""
    candidates = (
        "yield",
        "productivity",
        "productivity_kg_per_hectare",
        "yield_kg_per_hectare",
        "yield_quintal_per_hectare",
        "productivity_quintal_per_hectare",
        "avg_yield",
    )
    for key in candidates:
        if key not in record:
            continue
        try:
            val = float(record[key])
        except (TypeError, ValueError):
            continue
        if val <= 0:
            continue
        if "quintal" in key:
            return val * 100.0
        return val

    for key, raw in record.items():
        kl = str(key).lower()
        if "yield" not in kl and "productivity" not in kl:
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if val <= 0:
            continue
        if "quintal" in kl or "q/ha" in kl:
            return val * 100.0
        if val < 500 and "tonne" in kl:
            return val * 1000.0
        return val
    return None


def _crop_name_from_record(record: dict[str, Any]) -> str | None:
    for key in ("crop", "commodity", "crop_name", "Crop", "Commodity"):
        if record.get(key):
            return str(record[key])
    return None


def fetch_apy_records_live(
    api_key: str,
    *,
    resource_id: str | None = None,
    state: str | None = None,
    limit: int = 500,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Fetch raw APY records from data.gov.in (when API is reachable)."""
    rid = (resource_id or DEFAULT_APY_RESOURCE_ID).strip()
    url = f"https://api.data.gov.in/resource/{rid}"
    params: dict[str, Any] = {
        "api-key": api_key,
        "format": "json",
        "limit": limit,
    }
    if state:
        params["filters[state]"] = state.strip().title()

    owns = client is None
    http = client or httpx.Client(timeout=45.0)
    try:
        resp = http.get(url, params=params)
        resp.raise_for_status()
        ctype = (resp.headers.get("content-type") or "").lower()
        if "json" not in ctype:
            raise ValueError(f"Non-JSON response from data.gov.in APY API (content-type={ctype})")
        data = resp.json()
        return list(data.get("records") or [])
    finally:
        if owns:
            http.close()


def aggregate_live_yields(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Median yield kg/ha per crop from live OGD records."""
    buckets: dict[str, list[float]] = {}
    for rec in records:
        crop_id = _match_crop_id(_crop_name_from_record(rec))
        kg_ha = _parse_yield_value(rec)
        if not crop_id or kg_ha is None:
            continue
        buckets.setdefault(crop_id, []).append(kg_ha)

    out: dict[str, dict[str, Any]] = {}
    for crop_id, values in buckets.items():
        mid = float(median(values))
        out[crop_id] = {
            "crop_id": crop_id,
            "yield_kg_per_hectare": round(mid, 1),
            "expected_yield_kg_per_acre": kg_per_hectare_to_kg_per_acre(mid),
            "sample_count": len(values),
            "data_origin": "data.gov.in_live_api",
            "source_organization": "data.gov.in",
            "dataset_title": "Area, Production and Yield (live fetch)",
        }
    return out


def resolve_yields(
    *,
    prefer_live: bool = True,
    api_key: str | None = None,
    resource_id: str | None = None,
    state: str | None = None,
    prefer_upag: bool = True,
) -> tuple[dict[str, dict[str, Any]], str]:
    """
    Resolve yields with priority:
      1. UPAg live API or UPAg CSV (snapshot/scraped)
      2. data.gov.in APY API (legacy)
      3. Bundled DAC&FW reference file

    Returns (yields_by_crop, mode).
    """
    if prefer_upag:
        try:
            from app.services.upag_apy import resolve_upag_yields

            yields, mode = resolve_upag_yields(prefer_live=prefer_live)
            if yields:
                return yields, mode
        except Exception:
            pass

    key = (api_key or get_settings().data_gov_api_key or get_settings().market_api_key or "").strip()
    if prefer_live and key:
        try:
            records = fetch_apy_records_live(key, resource_id=resource_id, state=state)
            live = aggregate_live_yields(records)
            if live:
                return live, "data_gov_live"
        except Exception:
            pass

    return reference_yield_by_crop(), "reference"
