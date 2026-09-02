"""UPAg (Unified Portal for Agricultural Statistics) yield data client."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.crop_yield_data import HECTARES_PER_ACRE, kg_per_hectare_to_kg_per_acre

UPAG_BASE_URL = "https://data.upag.gov.in"
UPAG_LOGIN_PATH = "/v1/upag/api-data-share/login"
UPAG_STATEWISE_PATH = "/v1/upag/api-data-share/apy/statewise"

# Map UPAg / Dataful crop labels to KrishiAi crop_id
UPAG_CROP_ALIASES: dict[str, str] = {
    "tomato": "tomato",
    "tomatoes": "tomato",
    "potato": "potato",
    "potatoes": "potato",
    "onion": "onion",
    "onions": "onion",
    "maize": "maize",
    "wheat": "wheat",
    "rice": "rice",
    "paddy": "rice",
    "cotton": "cotton",
    "cotton(lint)": "cotton",
    "cotton (lint)": "cotton",
}

SUPPORTED_CROP_IDS = ("tomato", "potato", "onion", "maize", "wheat", "rice", "cotton")


def _data_dir() -> Path:
    return Path(get_settings().knowledge_dir).parent


def default_snapshot_csv_path() -> Path:
    return _data_dir() / "sources" / "upag_all_india_apy_snapshot.csv"


def scraped_csv_path() -> Path:
    return _data_dir() / "scraped" / f"upag_apy_{date.today().isoformat()}.csv"


def _csv_origin(path: Path) -> str:
    parts = {p.lower() for p in path.parts}
    if "scraped" in parts:
        return "upag_scraped_csv"
    if path.resolve() == default_snapshot_csv_path().resolve() or "sources" in parts:
        return "upag_snapshot_csv"
    return "upag_csv"


def _normalize_upag_crop(name: str | None) -> str | None:
    if not name:
        return None
    key = str(name).strip().lower()
    if key in UPAG_CROP_ALIASES:
        return UPAG_CROP_ALIASES[key]
    for crop_id in SUPPORTED_CROP_IDS:
        if crop_id in key:
            return crop_id
    return None


def _yield_unit_to_kg_per_ha(value: float, unit: str) -> float:
    u = (unit or "").strip().lower().replace(" ", "_")
    if "tonne" in u or u in ("t/ha", "tonnes_per_hectare"):
        return value * 1000.0
    if "quintal" in u:
        return value * 100.0
    return value  # assume kg/ha


def parse_upag_csv_rows(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Parse UPAg/Dataful CSV rows into per-crop yield facts (latest fiscal year per crop)."""
    parsed: list[tuple[str, str, float, str, str]] = []
    for row in rows:
        crop_id = _normalize_upag_crop(row.get("crop") or row.get("Crop"))
        if not crop_id:
            continue
        try:
            raw_yield = float(row.get("crop_yield") or row.get("yield") or row.get("Value") or 0)
        except (TypeError, ValueError):
            continue
        if raw_yield <= 0:
            continue
        fiscal_year = str(row.get("fiscal_year") or row.get("Year") or row.get("year") or "").strip()
        unit = str(
            row.get("yield_unit")
            or row.get("unit")
            or row.get("UOM")
            or row.get("Unit Of Measure")
            or "tonnes_per_hectare"
        )
        state = str(row.get("state") or row.get("State") or "").strip()
        parsed.append((fiscal_year, crop_id, raw_yield, unit, state))

    if not parsed:
        return {}

    # Prefer All India rows; else latest year
    all_india = [p for p in parsed if p[4].lower() in ("all india", "india", "")]
    pool = all_india or parsed
    latest_year = max(p[0] for p in pool if p[0])

    out: dict[str, dict[str, Any]] = {}
    for fiscal_year, crop_id, raw_yield, unit, _state in pool:
        if fiscal_year != latest_year:
            continue
        if crop_id in out:
            continue
        kg_ha = _yield_unit_to_kg_per_ha(raw_yield, unit)
        out[crop_id] = _yield_row_from_kg_ha(
            crop_id=crop_id,
            kg_ha=kg_ha,
            source_year=fiscal_year,
            data_origin="upag_csv",
        )
    return out


def _yield_row_from_kg_ha(
    *,
    crop_id: str,
    kg_ha: float,
    source_year: str,
    data_origin: str,
    sample_count: int | None = None,
) -> dict[str, Any]:
    return {
        "crop_id": crop_id,
        "official_name": crop_id.title(),
        "yield_kg_per_hectare": round(kg_ha, 1),
        "expected_yield_kg_per_acre": kg_per_hectare_to_kg_per_acre(kg_ha),
        "source_organization": "Ministry of Agriculture & Farmers Welfare (UPAg)",
        "dataset_title": "Area, Production and Yield — All India (UPAg)",
        "source_year": source_year,
        "reference_urls": [
            "https://upag.gov.in/",
            "https://data.upag.gov.in/",
            "https://dataful.in/datasets/4889/",
        ],
        "data_origin": data_origin,
        "sample_count": sample_count,
    }


def load_upag_csv(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"UPAg CSV not found: {path}")
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    return parse_upag_csv_rows(rows)


def upag_login(
    username: str,
    password: str,
    *,
    client: httpx.Client | None = None,
) -> str:
    owns = client is None
    http = client or httpx.Client(timeout=45.0)
    try:
        resp = http.post(
            f"{UPAG_BASE_URL}{UPAG_LOGIN_PATH}",
            data={
                "grant_type": "password",
                "username": username,
                "password": password,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise ValueError("UPAg login response missing access_token")
        return str(token)
    finally:
        if owns:
            http.close()


def fetch_upag_statewise_apy(
    token: str,
    *,
    from_year: int = 2024,
    to_year: int = 2024,
    crops: list[str] | None = None,
    states: list[str] | None = None,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Fetch APY records from UPAg API (requires registered API account)."""
    body = {
        "from_year": from_year,
        "to_year": to_year,
        "crop": crops or list(SUPPORTED_CROP_IDS),
        "crop_category": [],
        "state": states or ["All India"],
        "season": [],
        "metric": ["Yield"],
        "uom": [],
    }
    owns = client is None
    http = client or httpx.Client(timeout=60.0)
    try:
        resp = http.post(
            f"{UPAG_BASE_URL}{UPAG_STATEWISE_PATH}",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("data", "records", "results", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []
    finally:
        if owns:
            http.close()


def _records_to_yield_map(records: list[dict[str, Any]], source_year: str) -> dict[str, dict[str, Any]]:
    """Normalize UPAg API JSON records to yield map."""
    rows: list[dict[str, str]] = []
    for rec in records:
        crop_name = rec.get("Crop") or rec.get("crop") or rec.get("crop_name")
        value = rec.get("Value") or rec.get("value") or rec.get("crop_yield")
        if crop_name is None or value is None:
            continue
        rows.append(
            {
                "crop": str(crop_name),
                "crop_yield": str(value),
                "fiscal_year": str(rec.get("Year") or rec.get("fiscal_year") or source_year),
                "unit": str(rec.get("UOM") or rec.get("Unit Of Measure") or rec.get("unit") or ""),
                "state": str(rec.get("State") or rec.get("state") or "All India"),
            }
        )
    result = parse_upag_csv_rows(rows)
    for row in result.values():
        row["data_origin"] = "upag_live_api"
    return result


def fetch_upag_yields_live(
    *,
    username: str | None = None,
    password: str | None = None,
    from_year: int = 2024,
    to_year: int = 2024,
) -> dict[str, dict[str, Any]]:
    settings = get_settings()
    user = (username or settings.upag_api_username or "").strip()
    pwd = (password or settings.upag_api_password or "").strip()
    if not user or not pwd:
        raise ValueError("UPAg API credentials not configured (UPAG_API_USERNAME / UPAG_API_PASSWORD)")

    token = upag_login(user, pwd)
    records = fetch_upag_statewise_apy(token, from_year=from_year, to_year=to_year)
    if not records:
        raise ValueError("UPAg API returned no APY records")
    year_label = f"{from_year}-{str(to_year)[-2:]}" if from_year != to_year else f"{from_year}-25"
    return _records_to_yield_map(records, source_year=year_label)


def resolve_upag_yields(
    *,
    prefer_live: bool = True,
    csv_path: Path | None = None,
) -> tuple[dict[str, dict[str, Any]], str]:
    """
    Resolve yields from UPAg.

    Priority:
      1. Live UPAg API (if credentials set and prefer_live)
      2. Latest file in data/scraped/upag_apy_*.csv
      3. Bundled snapshot data/sources/upag_all_india_apy_snapshot.csv
    """
    settings = get_settings()
    if prefer_live and settings.upag_api_username and settings.upag_api_password:
        try:
            return fetch_upag_yields_live(), "upag_live"
        except Exception:
            pass

    scraped_dir = _data_dir() / "scraped"
    if csv_path is None and scraped_dir.exists():
        candidates = sorted(scraped_dir.glob("upag_apy_*.csv"), reverse=True)
        if candidates:
            csv_path = candidates[0]

    if csv_path is None:
        csv_path = default_snapshot_csv_path()

    yields = load_upag_csv(csv_path)
    if not yields:
        raise ValueError(f"No supported crops parsed from UPAg CSV: {csv_path}")

    origin = _csv_origin(csv_path)
    for row in yields.values():
        if row.get("data_origin") == "upag_csv":
            row["data_origin"] = origin
    return yields, origin


def save_upag_csv(rows: list[dict[str, Any]], path: Path | None = None) -> Path:
    """Write UPAg records to CSV in data/scraped/."""
    out = path or scraped_csv_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["fiscal_year", "state", "crop", "crop_yield", "yield_unit", "source"]
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for rec in rows:
            writer.writerow(
                {
                    "fiscal_year": rec.get("Year") or rec.get("fiscal_year") or "2024-25",
                    "state": rec.get("State") or rec.get("state") or "All India",
                    "crop": rec.get("Crop") or rec.get("crop"),
                    "crop_yield": rec.get("Value") or rec.get("crop_yield"),
                    "yield_unit": rec.get("UOM") or rec.get("unit") or "tonnes_per_hectare",
                    "source": "upag_live_api",
                }
            )
    return out


def write_snapshot_metadata(path: Path | None = None) -> None:
    meta_path = (path or default_snapshot_csv_path()).with_suffix(".json")
    meta = {
        "title": "UPAg All-India APY snapshot (KrishiAi seed)",
        "source_organization": "Ministry of Agriculture & Farmers Welfare (UPAg / DAC&FW)",
        "reference_urls": [
            "https://upag.gov.in/",
            "https://dataful.in/datasets/4889/",
            "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2241379",
        ],
        "notes": (
            "Cereals/cotton yields from UPAg master data via Dataful dataset 4889 (2024-25). "
            "Horticulture yields computed from DA&FW final horticulture estimates (production/area)."
        ),
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
