"""Load per-crop agronomic defaults from crop_registry.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
import re
from typing import Any

from app.core.config import get_settings

_CROP_ALIASES: dict[str, str] = {
    "tomatoes": "tomato",
    "potatoes": "potato",
    "onions": "onion",
    "corn": "maize",
    "paddy": "rice",
}


def normalize_crop_name(crop: str | None) -> str | None:
    """Return canonical crop id (e.g. 'tomato') or None if empty/unknown."""
    if not crop or not str(crop).strip():
        return None
    key = str(crop).strip().lower().replace("-", "_").replace(" ", "_")
    return _CROP_ALIASES.get(key, key)


def extract_crop_from_text(text: str | None) -> str | None:
    """Return the last recognized crop name in text, if any.

    The last mention wins so a new question can name maize after older notes
    mentioned tomato.
    """
    if not text or not str(text).strip():
        return None
    lowered = text.lower()
    found: list[tuple[int, str]] = []
    names = [(alias, canonical) for alias, canonical in _CROP_ALIASES.items()]
    names.extend((crop, crop) for crop in list_supported_crops())
    for alias, canonical in names:
        for match in re.finditer(rf"\b{re.escape(alias)}\b", lowered):
            found.append((match.start(), canonical))
    if not found:
        return None
    found.sort(key=lambda item: item[0])
    return found[-1][1]


@lru_cache(maxsize=1)
def load_crop_registry() -> dict[str, Any]:
    path = Path(get_settings().knowledge_dir) / "crop_registry.json"
    if not path.exists():
        return {"version": "1.0", "crops": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if "crops" not in data or not isinstance(data["crops"], dict):
        raise ValueError(f"Invalid crop registry format in {path}")
    return data


def list_supported_crops() -> list[str]:
    """Return sorted canonical crop ids defined in the registry."""
    return sorted(load_crop_registry().get("crops", {}).keys())


def get_crop_profile(crop: str) -> dict[str, Any]:
    """
    Return the full profile for a crop.

    Raises KeyError if the crop is not in the registry.
    """
    crop_id = normalize_crop_name(crop)
    if not crop_id:
        raise KeyError("crop name is empty")
    crops = load_crop_registry().get("crops", {})
    if crop_id not in crops:
        raise KeyError(f"unsupported crop: {crop}")
    profile = dict(crops[crop_id])
    profile["crop_id"] = crop_id
    return profile


def get_crop_defaults(crop: str) -> dict[str, Any]:
    """
    Return the fields agents and tools need most often: yield, costs, market name.

    This is the primary entry point for finance/soil/market agents (Step 1.2+).
    """
    profile = get_crop_profile(crop)
    costs = profile.get("default_input_costs_per_acre", {})
    return {
        "crop_id": profile["crop_id"],
        "display_name": profile.get("display_name", profile["crop_id"]),
        "expected_yield_kg_per_acre": profile["expected_yield_kg_per_acre"],
        "default_input_costs_per_acre": dict(costs),
        "market_commodity_name": profile.get("market_commodity_name", profile["display_name"]),
        "growth_stages": list(profile.get("growth_stages", [])),
        "common_diseases": list(profile.get("common_diseases", [])),
        "npk_targets": dict(profile.get("npk_targets", {})),
        "yield_provenance": dict(profile.get("yield_provenance", {})),
        "input_cost_source": profile.get("input_cost_source"),
    }


_COST_KEYS = (
    "seed_cost",
    "fertilizer_cost",
    "pesticide_cost",
    "labor_cost",
    "irrigation_cost",
    "equipment_cost",
    "transport_cost",
)

_HARVEST_COST_KEYS = ("labor_cost", "equipment_cost", "transport_cost")


def build_profit_inputs(
    crop: str,
    *,
    area_acres: float,
    selling_price: float,
    irrigation_available: bool | None = None,
    budget: float | None = None,
) -> dict[str, Any]:
    """
    Build typed arguments for calculate_profit() from crop registry defaults.

    Kisan AI: revenue and cost must come from structured crop parameters, not LLM guesses.
    """
    try:
        defaults = get_crop_defaults(crop)
    except KeyError:
        defaults = get_crop_defaults("tomato")

    area = max(float(area_acres), 0.01)
    per_acre = defaults.get("default_input_costs_per_acre") or {}

    costs = {key: float(per_acre.get(key, 0.0)) * area for key in _COST_KEYS}

    if irrigation_available is True:
        costs["irrigation_cost"] = round(costs["irrigation_cost"] * 0.75, 2)

    if budget is not None and budget < 15000 * area:
        costs["pesticide_cost"] = min(costs["pesticide_cost"], max(0.0, budget * 0.15))
        costs["fertilizer_cost"] = min(costs["fertilizer_cost"], max(0.0, budget * 0.2))

    return {
        "crop_id": defaults["crop_id"],
        "area": area,
        "expected_yield": float(defaults["expected_yield_kg_per_acre"]),
        "selling_price": float(selling_price),
        "yield_provenance": dict(defaults.get("yield_provenance", {})),
        "input_cost_source": defaults.get("input_cost_source"),
        **costs,
    }


def estimate_harvest_related_costs(crop: str, *, area_acres: float) -> dict[str, Any]:
    """
    Indicative harvest-related costs from crop registry (labor + equipment + transport).

    These are national curated defaults per acre, not state-specific mandi quotes.
    """
    try:
        defaults = get_crop_defaults(crop)
    except KeyError:
        defaults = get_crop_defaults("tomato")

    area = max(float(area_acres), 0.01)
    per_acre = defaults.get("default_input_costs_per_acre") or {}
    breakdown = {key: float(per_acre.get(key, 0.0)) for key in _HARVEST_COST_KEYS}
    total_per_acre = sum(breakdown.values())
    return {
        "crop_id": defaults["crop_id"],
        "display_name": defaults.get("display_name", defaults["crop_id"]),
        "area_acres": area,
        "per_acre": breakdown,
        "total_per_acre": total_per_acre,
        "total_farm": round(total_per_acre * area, 2),
        "input_cost_source": defaults.get("input_cost_source"),
        "note": "Indicative all-India defaults; verify labor and transport rates locally.",
    }


def clear_crop_registry_cache() -> None:
    """Clear cached registry (for tests)."""
    load_crop_registry.cache_clear()
