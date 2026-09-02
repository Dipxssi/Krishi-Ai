#!/usr/bin/env python3
"""Build crop_registry.json from government yield data + curated agronomic overrides.

Yield priority:
  1. UPAg live API (UPAG_API_USERNAME / UPAG_API_PASSWORD)
  2. UPAg CSV in data/scraped/ or bundled snapshot
  3. data.gov.in APY API (legacy)
  4. Bundled DAC&FW reference file

Usage:
  uv run python scripts/build_crop_registry.py
  uv run python scripts/fetch_upag_apy.py --use-snapshot   # refresh scraped CSV from snapshot
  uv run python scripts/build_crop_registry.py --reference-only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.crop_registry import clear_crop_registry_cache  # noqa: E402
from app.services.crop_yield_data import resolve_yields  # noqa: E402

KNOWLEDGE_DIR = BACKEND_ROOT / "data" / "knowledge"
REGISTRY_PATH = KNOWLEDGE_DIR / "crop_registry.json"
OVERRIDES_PATH = KNOWLEDGE_DIR / "crop_registry.overrides.json"
SCRAPED_DIR = BACKEND_ROOT / "data" / "scraped"


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _base_overrides() -> dict[str, Any]:
    """Curated agronomic fields not available from APY datasets."""
    return _load_json(
        OVERRIDES_PATH,
        {
            "version": "1.0",
            "crops": {},
        },
    )


def _merge_crop(
    crop_id: str,
    yield_row: dict[str, Any],
    existing: dict[str, Any] | None,
    overrides: dict[str, Any] | None,
) -> dict[str, Any]:
    base = dict(existing or {})
    ovr = dict((overrides or {}).get("crops", {}).get(crop_id, {}))
    display_name = (
        ovr.get("display_name")
        or base.get("display_name")
        or yield_row.get("official_name", crop_id.title())
    )

    merged: dict[str, Any] = {
        "display_name": display_name,
        "expected_yield_kg_per_acre": yield_row["expected_yield_kg_per_acre"],
        "yield_provenance": {
            "yield_kg_per_hectare": yield_row.get("yield_kg_per_hectare"),
            "expected_yield_kg_per_acre": yield_row["expected_yield_kg_per_acre"],
            "source_organization": yield_row.get("source_organization"),
            "dataset_title": yield_row.get("dataset_title"),
            "source_year": yield_row.get("source_year"),
            "reference_urls": yield_row.get("reference_urls", []),
            "data_origin": yield_row.get("data_origin"),
            "sample_count": yield_row.get("sample_count"),
            "built_on": date.today().isoformat(),
        },
        "default_input_costs_per_acre": ovr.get("default_input_costs_per_acre")
        or base.get("default_input_costs_per_acre", {}),
        "growth_stages": ovr.get("growth_stages") or base.get("growth_stages", []),
        "common_diseases": ovr.get("common_diseases") or base.get("common_diseases", []),
        "market_commodity_name": ovr.get("market_commodity_name")
        or base.get("market_commodity_name")
        or display_name,
        "npk_targets": ovr.get("npk_targets") or base.get("npk_targets", {}),
        "input_cost_source": ovr.get("input_cost_source")
        or base.get("input_cost_source")
        or "curated_smallholder_indicative",
    }
    return merged


def build_registry(
    *,
    prefer_live: bool = True,
    prefer_upag: bool = True,
    state: str | None = None,
    resource_id: str | None = None,
) -> dict[str, Any]:
    existing = _load_json(REGISTRY_PATH, {"version": "1.0", "crops": {}})
    overrides_doc = _base_overrides()
    if not OVERRIDES_PATH.exists():
        # Seed overrides file from current registry curated fields (one-time migration).
        _write_overrides_from_registry(existing)

    yields, mode = resolve_yields(
        prefer_live=prefer_live,
        prefer_upag=prefer_upag,
        state=state,
        resource_id=resource_id,
    )

    crops_out: dict[str, Any] = {}
    crop_ids = sorted(set(yields.keys()) | set((existing.get("crops") or {}).keys()))

    for crop_id in crop_ids:
        if crop_id not in yields:
            continue
        crops_out[crop_id] = _merge_crop(
            crop_id,
            yields[crop_id],
            (existing.get("crops") or {}).get(crop_id),
            overrides_doc,
        )

    return {
        "version": "1.1",
        "built_with": f"scripts/build_crop_registry.py ({mode})",
        "source_note": (
            "Yields from UPAg / DAC&FW APY statistics (see yield_provenance per crop). "
            "Input costs and NPK from curated extension-aligned overrides. "
            "Agents should prefer farmer-provided values when available."
        ),
        "crops": crops_out,
    }


def _write_overrides_from_registry(existing: dict[str, Any]) -> None:
    crops = existing.get("crops") or {}
    if not crops:
        return
    out = {"version": "1.0", "crops": {}}
    for crop_id, row in crops.items():
        out["crops"][crop_id] = {
            k: row[k]
            for k in (
                "display_name",
                "default_input_costs_per_acre",
                "growth_stages",
                "common_diseases",
                "market_commodity_name",
                "npk_targets",
            )
            if k in row
        }
    OVERRIDES_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build crop_registry.json from government yield data")
    parser.add_argument(
        "--reference-only",
        action="store_true",
        help="Skip live APIs; use bundled DAC&FW reference only (not UPAg)",
    )
    parser.add_argument(
        "--no-upag",
        action="store_true",
        help="Skip UPAg CSV/API even when available",
    )
    parser.add_argument("--state", default=None, help="Optional state filter for live APY API")
    parser.add_argument("--resource-id", default=None, help="Override data.gov.in APY resource UUID")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON to stdout instead of writing file")
    args = parser.parse_args()

    get_settings.cache_clear()
    clear_crop_registry_cache()

    registry = build_registry(
        prefer_live=not args.reference_only,
        prefer_upag=not args.reference_only and not args.no_upag,
        state=args.state,
        resource_id=args.resource_id,
    )

    payload = json.dumps(registry, indent=2, ensure_ascii=False) + "\n"
    if args.dry_run:
        print(payload)
        return 0

    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(payload, encoding="utf-8")
    clear_crop_registry_cache()

    mode = registry.get("built_with", "")
    print(f"Wrote {len(registry.get('crops', {}))} crops -> {REGISTRY_PATH}")
    print(f"Build mode: {mode}")
    for crop_id, row in sorted(registry.get("crops", {}).items()):
        prov = row.get("yield_provenance", {})
        print(
            f"  {crop_id}: {row['expected_yield_kg_per_acre']} kg/acre "
            f"({prov.get('data_origin')}, {prov.get('source_year', 'n/a')})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
