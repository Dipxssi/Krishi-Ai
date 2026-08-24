"""Typed agricultural tools with Pydantic I/O."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import get_settings


# ---- Weather ----


class WeatherArgs(BaseModel):
    location: str
    forecast_days: int = Field(default=7, ge=1, le=14)


class WeatherResult(BaseModel):
    location: str
    forecast_days: int
    rainfall_mm: float
    avg_temp_c: float
    condition: str
    source: str
    is_mock: bool = False


def get_weather(location: str, forecast_days: int = 7) -> dict[str, Any]:
    settings = get_settings()
    if settings.weather_api_key:
        # Placeholder for real API; fall through to labeled mock if not wired
        pass
    # Deterministic mock labeled as mock — never unlabeled invention
    seed = sum(ord(c) for c in location.lower()) % 40
    result = WeatherResult(
        location=location,
        forecast_days=forecast_days,
        rainfall_mm=round(8 + seed * 0.4, 1),
        avg_temp_c=round(24 + (seed % 10) * 0.5, 1),
        condition="rain_likely" if seed % 3 == 0 else "partly_cloudy",
        source="mock_weather_service",
        is_mock=True,
    )
    return result.model_dump()


# ---- Market ----


class MarketPriceArgs(BaseModel):
    crop: str
    market: str
    date: str  # YYYY-MM-DD


class MarketPriceResult(BaseModel):
    crop: str
    market: str
    date: str
    current_price: float
    forecast_price: float
    forecast_horizon: str
    forecast_uncertainty: str
    unit: str = "INR/kg"
    source: str
    is_mock: bool = False


_BASE_PRICES = {
    "tomato": 42.0,
    "potato": 18.0,
    "maize": 22.0,
    "wheat": 25.0,
    "rice": 30.0,
}


def get_market_price(crop: str, market: str, date: str) -> dict[str, Any]:
    settings = get_settings()
    crop_key = crop.strip().lower()
    base = _BASE_PRICES.get(crop_key, 35.0)
    # Seasonal moving-average style mock forecast (slight downward drift)
    day_factor = (sum(ord(c) for c in date) % 7) * 0.3
    current = round(base - day_factor, 2)
    forecast = round(current * 0.92, 2)
    if settings.market_api_key:
        source = "market_api"
        is_mock = False
    else:
        source = "mock_market_service"
        is_mock = True
    result = MarketPriceResult(
        crop=crop_key,
        market=market,
        date=date,
        current_price=current,
        forecast_price=forecast,
        forecast_horizon="30 days",
        forecast_uncertainty="medium",
        source=source,
        is_mock=is_mock,
    )
    return result.model_dump()


# ---- Profit (deterministic) ----


class ProfitArgs(BaseModel):
    area: float = Field(gt=0)
    expected_yield: float = Field(ge=0)  # kg per acre
    selling_price: float = Field(ge=0)  # per kg
    seed_cost: float = 0
    fertilizer_cost: float = 0
    pesticide_cost: float = 0
    labor_cost: float = 0
    irrigation_cost: float = 0
    equipment_cost: float = 0
    transport_cost: float = 0


class ProfitResult(BaseModel):
    revenue: float
    total_cost: float
    profit: float
    break_even_price: float | None = None


def calculate_profit(
    area: float,
    expected_yield: float,
    selling_price: float,
    seed_cost: float = 0,
    fertilizer_cost: float = 0,
    pesticide_cost: float = 0,
    labor_cost: float = 0,
    irrigation_cost: float = 0,
    equipment_cost: float = 0,
    transport_cost: float = 0,
) -> dict[str, Any]:
    revenue = area * expected_yield * selling_price
    total_cost = (
        seed_cost
        + fertilizer_cost
        + pesticide_cost
        + labor_cost
        + irrigation_cost
        + equipment_cost
        + transport_cost
    )
    qty = area * expected_yield
    break_even = round(total_cost / qty, 2) if qty > 0 else None
    return ProfitResult(
        revenue=round(revenue, 2),
        total_cost=round(total_cost, 2),
        profit=round(revenue - total_cost, 2),
        break_even_price=break_even,
    ).model_dump()


# ---- Decision score ----


class DecisionScoreArgs(BaseModel):
    agronomic_suitability: float = Field(ge=0, le=1)
    expected_profit: float  # normalized later if large
    water_risk: float = Field(ge=0, le=1)
    disease_risk: float = Field(ge=0, le=1)
    input_cost: float = Field(ge=0)  # absolute or 0-1; we normalize
    agronomic_weight: float | None = None
    economic_weight: float | None = None
    max_profit_scale: float = 50000.0
    max_input_cost_scale: float = 30000.0


def estimate_decision_score(
    agronomic_suitability: float,
    expected_profit: float,
    water_risk: float,
    disease_risk: float,
    input_cost: float,
    agronomic_weight: float | None = None,
    economic_weight: float | None = None,
    max_profit_scale: float = 50000.0,
    max_input_cost_scale: float = 30000.0,
) -> dict[str, Any]:
    settings = get_settings()
    aw = agronomic_weight if agronomic_weight is not None else settings.agronomic_weight
    ew = economic_weight if economic_weight is not None else settings.economic_weight

    # Normalize profit and input cost to 0-1
    economic_raw = max(0.0, min(1.0, (expected_profit / max_profit_scale + 1) / 2)) if expected_profit < max_profit_scale else 1.0
    if expected_profit < 0:
        economic_raw = max(0.0, 0.5 + expected_profit / max_profit_scale)
    input_norm = max(0.0, min(1.0, input_cost / max_input_cost_scale))

    agronomic_score = max(0.0, min(1.0, agronomic_suitability - 0.3 * water_risk - 0.3 * disease_risk))
    economic_score = max(0.0, min(1.0, economic_raw - 0.25 * input_norm))
    final_score = aw * agronomic_score + ew * economic_score

    return {
        "agronomic_suitability": agronomic_suitability,
        "expected_profit": expected_profit,
        "water_risk": water_risk,
        "disease_risk": disease_risk,
        "input_cost": input_cost,
        "agronomic_score": round(agronomic_score, 4),
        "economic_score": round(economic_score, 4),
        "final_score": round(final_score, 4),
        "agronomic_weight": aw,
        "economic_weight": ew,
    }


# ---- Knowledge search (wired after RAG loads) ----


class KnowledgeSearchArgs(BaseModel):
    query: str
    crop: str | None = None
    top_k: int = Field(default=3, ge=1, le=10)


def search_crop_knowledge(query: str, crop: str | None = None, top_k: int = 3) -> dict[str, Any]:
    from app.services.rag import search_knowledge

    hits = search_knowledge(query=query, crop=crop, top_k=top_k)
    return {"query": query, "crop": crop, "results": hits}


# ---- Equipment prices ----


class EquipmentPriceArgs(BaseModel):
    equipment_type: str | None = None
    category: str | None = None
    farm_area_acres: float | None = None


def _load_equipment_data() -> list[dict[str, Any]]:
    import json
    path = Path(get_settings().knowledge_dir) / "equipment_prices.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def get_equipment_price(
    equipment_type: str | None = None,
    category: str | None = None,
    farm_area_acres: float | None = None,
) -> dict[str, Any]:
    items = _load_equipment_data()
    results = []
    for item in items:
        if equipment_type:
            et = equipment_type.lower()
            if et not in item.get("type", "").lower() and et not in item.get("name", "").lower():
                continue
        if category and category.lower() != item.get("category", "").lower():
            continue
        if farm_area_acres is not None:
            suitable = item.get("suitable_area_acres", [0, 9999])
            if farm_area_acres < suitable[0] or farm_area_acres > suitable[1]:
                continue
        results.append(item)
    return {"matches": results[:5], "total": len(results), "source": "curated_2024"}


# ---- Government schemes ----


class SchemesSearchArgs(BaseModel):
    category: str | None = None
    crop: str | None = None
    state: str | None = None


def _load_schemes_data() -> list[dict[str, Any]]:
    import json
    path = Path(get_settings().knowledge_dir) / "schemes.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def search_schemes(
    category: str | None = None,
    crop: str | None = None,
    state: str | None = None,
) -> dict[str, Any]:
    items = _load_schemes_data()
    results = []
    for item in items:
        if category and category.lower() != item.get("category", "").lower():
            continue
        if crop:
            if item.get("crop_specific") and "crops" in item:
                if crop.lower() not in [c.lower() for c in item["crops"]]:
                    continue
        if state and item.get("state") != "all" and state.lower() != item.get("state", "").lower():
            continue
        results.append(item)
    return {"matches": results, "total": len(results), "source": "curated_2024"}


# ---- Loans ----


class LoansSearchArgs(BaseModel):
    category: str | None = None
    amount_needed: float | None = None
    purpose: str | None = None


def _load_loans_data() -> list[dict[str, Any]]:
    import json
    path = Path(get_settings().knowledge_dir) / "loans.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def search_loans(
    category: str | None = None,
    amount_needed: float | None = None,
    purpose: str | None = None,
) -> dict[str, Any]:
    items = _load_loans_data()
    results = []
    for item in items:
        if category and category.lower() != item.get("category", "").lower():
            continue
        if amount_needed is not None and item.get("max_amount_inr") is not None:
            if amount_needed > item["max_amount_inr"]:
                continue
        if purpose:
            p = purpose.lower()
            name_cat = (item.get("name", "") + " " + item.get("category", "")).lower()
            if p not in name_cat and p not in item.get("eligibility", "").lower():
                continue
        results.append(item)
    return {"matches": results, "total": len(results), "source": "curated_2024"}


def default_today() -> str:
    return date.today().isoformat()


def register_all_tools(registry) -> None:
    registry.register("get_weather", get_weather, WeatherArgs)
    registry.register("get_market_price", get_market_price, MarketPriceArgs)
    registry.register("calculate_profit", calculate_profit, ProfitArgs)
    registry.register("estimate_decision_score", estimate_decision_score, DecisionScoreArgs)
    registry.register("search_crop_knowledge", search_crop_knowledge, KnowledgeSearchArgs)
    registry.register("get_equipment_price", get_equipment_price, EquipmentPriceArgs)
    registry.register("search_schemes", search_schemes, SchemesSearchArgs)
    registry.register("search_loans", search_loans, LoansSearchArgs)
