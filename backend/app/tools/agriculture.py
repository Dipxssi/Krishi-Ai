"""Typed agricultural tools with Pydantic I/O."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
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
    from app.services.live_weather import fetch_weather_live

    live = fetch_weather_live(location, forecast_days)
    if live is not None:
        # Keep tool schema lean: drop daily breakdown from agent evidence path
        return {
            "location": live["location"],
            "forecast_days": live["forecast_days"],
            "rainfall_mm": live["rainfall_mm"],
            "avg_temp_c": live["avg_temp_c"],
            "condition": live["condition"],
            "source": live["source"],
            "is_mock": False,
        }

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


def _mock_market_price(crop: str, market: str, date: str) -> dict[str, Any]:
    crop_key = crop.strip().lower()
    base = _BASE_PRICES.get(crop_key, 35.0)
    day_factor = (sum(ord(c) for c in date) % 7) * 0.3
    current = round(base - day_factor, 2)
    forecast = round(current * 0.92, 2)
    result = MarketPriceResult(
        crop=crop_key,
        market=market,
        date=date,
        current_price=current,
        forecast_price=forecast,
        forecast_horizon="30 days",
        forecast_uncertainty="medium",
        source="mock_market_service",
        is_mock=True,
    )
    return result.model_dump()


def _attach_sell_markets(payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.sell_markets import sell_markets_for

    names: list[str] = []
    for name in list(payload.get("matched_markets") or []) + sell_markets_for(str(payload.get("market") or "")):
        label = str(name).strip()
        if label and label not in names:
            names.append(label)
    payload["sell_markets"] = names[:6]
    return payload


def get_market_price(crop: str, market: str, date: str) -> dict[str, Any]:
    from app.services.live_market import fetch_market_price_live

    live = fetch_market_price_live(crop, market, date)
    if live is not None:
        return _attach_sell_markets(
            {
                "crop": live["crop"],
                "market": live["market"],
                "date": live["date"],
                "current_price": live["current_price"],
                "forecast_price": live["forecast_price"],
                "forecast_horizon": live["forecast_horizon"],
                "forecast_uncertainty": live["forecast_uncertainty"],
                "unit": live.get("unit", "INR/kg"),
                "source": live["source"],
                "is_mock": bool(live.get("is_mock", False)),
                "matched_markets": list(live.get("matched_markets") or []),
            }
        )

    return _attach_sell_markets(_mock_market_price(crop, market, date))


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
    disease_risk: float | None = None
    input_cost: float = Field(ge=0)  # absolute or 0-1; we normalize
    agronomic_weight: float | None = None
    economic_weight: float | None = None
    max_profit_scale: float = 50000.0
    max_input_cost_scale: float = 30000.0


def estimate_decision_score(
    agronomic_suitability: float,
    expected_profit: float,
    water_risk: float,
    disease_risk: float | None,
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

    disease_penalty = 0.3 * disease_risk if disease_risk is not None else 0.0
    agronomic_score = max(0.0, min(1.0, agronomic_suitability - 0.3 * water_risk - disease_penalty))
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
    query: str | None = None
    category: str | None = None
    crop: str | None = None
    state: str | None = None


def _scheme_match_score(item: dict[str, Any], query: str) -> float:
    q = query.lower().replace("-", " ")
    blob = " ".join(
        str(item.get(k, ""))
        for k in ("name", "benefit", "eligibility", "how_to_apply", "notes", "category")
    ).lower()
    keywords = [str(k).lower().replace("-", " ") for k in item.get("keywords", [])]
    score = 0.0
    for kw in keywords:
        if kw in q or q in kw:
            score += 2.0
        elif any(part in q for part in kw.split() if len(part) >= 4):
            score += 1.0
    for token in [t for t in q.split() if len(t) >= 4]:
        if token in blob:
            score += 0.25
    return score


def _load_schemes_data() -> list[dict[str, Any]]:
    path = Path(get_settings().knowledge_dir) / "schemes.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def search_schemes(
    query: str | None = None,
    category: str | None = None,
    crop: str | None = None,
    state: str | None = None,
) -> dict[str, Any]:
    items = _load_schemes_data()
    results: list[tuple[float, dict[str, Any]]] = []
    for item in items:
        if category and category.lower() != item.get("category", "").lower():
            continue
        if crop:
            if item.get("crop_specific") and "crops" in item:
                if crop.lower() not in [c.lower() for c in item["crops"]]:
                    continue
        if state and item.get("state") != "all" and state.lower() != item.get("state", "").lower():
            continue
        if query:
            score = _scheme_match_score(item, query)
            if score <= 0:
                continue
            results.append((score, item))
        else:
            results.append((0.0, item))
    results.sort(key=lambda x: x[0], reverse=True)
    matches = [item for _, item in results]
    return {"matches": matches, "total": len(matches), "source": "curated_2024"}


# ---- Loans ----


class LoansSearchArgs(BaseModel):
    category: str | None = None
    amount_needed: float | None = None
    purpose: str | None = None


def _load_loans_data() -> list[dict[str, Any]]:
    path = Path(get_settings().knowledge_dir) / "loans.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


_LOAN_PURPOSE_WORDS = (
    "kcc",
    "kisan credit",
    "gold",
    "tractor",
    "mechanization",
    "equipment",
    "dairy",
    "mudra",
    "allied",
)


def _loan_purpose_terms(purpose: str | None) -> list[str]:
    """Keep only product words. A full farmer question must not be a substring filter."""
    if not purpose:
        return []
    text = purpose.lower()
    return [word for word in _LOAN_PURPOSE_WORDS if word in text]


def search_loans(
    category: str | None = None,
    amount_needed: float | None = None,
    purpose: str | None = None,
) -> dict[str, Any]:
    items = _load_loans_data()
    terms = _loan_purpose_terms(purpose)
    results = []
    for item in items:
        if category and category.lower() != item.get("category", "").lower():
            continue
        if amount_needed is not None and item.get("max_amount_inr") is not None:
            if amount_needed > item["max_amount_inr"]:
                continue
        if terms:
            blob = " ".join(
                str(item.get(key, ""))
                for key in ("id", "name", "category", "eligibility", "where_to_apply")
            ).lower()
            if not any(term in blob for term in terms):
                continue
        results.append(item)
    results.sort(key=lambda item: (item.get("category") != "crop_loan", item.get("name", "")))
    return {"matches": results, "total": len(results), "source": "curated_2024"}


# ---- Soil NPK interpretation ----

KG_HA_TO_KG_ACRE = 1 / 0.404686

_STAGE_NPK_EMPHASIS: dict[str, dict[str, dict[str, float]]] = {
    "potato": {
        "tuber_initiation": {"k": 1.2},
        "tuber_bulking": {"k": 1.25},
        "maturation": {"k": 1.15},
    },
    "tomato": {
        "flowering": {"k": 1.1, "p": 1.1},
        "fruiting": {"k": 1.15},
    },
    "onion": {
        "bulb_formation": {"k": 1.15},
        "maturity": {"k": 1.1},
    },
    "maize": {
        "tasseling": {"n": 1.1},
        "silking": {"k": 1.1},
        "grain_filling": {"k": 1.15},
    },
    "wheat": {
        "jointing": {"n": 1.1},
        "grain_filling": {"k": 1.1},
    },
    "rice": {
        "panicle_initiation": {"n": 1.1, "k": 1.1},
        "flowering": {"k": 1.15},
    },
    "cotton": {
        "flowering": {"k": 1.1},
        "boll_formation": {"k": 1.15},
    },
}


class SoilNpkArgs(BaseModel):
    crop: str
    n: float = Field(ge=0)
    p: float = Field(ge=0)
    k: float = Field(ge=0)
    ph: float | None = Field(default=None, ge=0, le=14)
    growth_stage: str | None = None
    nutrient_units: str = "kg_per_ha"


def _nutrient_status(ratio: float) -> str:
    if ratio < 0.7:
        return "low"
    if ratio > 1.3:
        return "high"
    return "adequate"


def interpret_soil_npk(
    crop: str,
    n: float,
    p: float,
    k: float,
    ph: float | None = None,
    growth_stage: str | None = None,
    nutrient_units: str = "kg_per_ha",
) -> dict[str, Any]:
    """Compare farmer soil NPK to crop registry targets; return structured gaps."""
    from app.services.crop_registry import get_crop_defaults, normalize_crop_name

    crop_id = normalize_crop_name(crop) or crop.lower()
    defaults = get_crop_defaults(crop_id)
    targets = defaults.get("npk_targets") or {}

    if nutrient_units == "kg_per_acre":
        n_acre, p_acre, k_acre = n, p, k
    else:
        n_acre = n * KG_HA_TO_KG_ACRE
        p_acre = p * KG_HA_TO_KG_ACRE
        k_acre = k * KG_HA_TO_KG_ACRE

    stage_key = (growth_stage or "").lower().replace(" ", "_")
    emphasis = _STAGE_NPK_EMPHASIS.get(crop_id, {}).get(stage_key, {})

    n_target = float(targets.get("n_kg_per_acre", 0)) * emphasis.get("n", 1.0)
    p_target = float(targets.get("p_kg_per_acre", 0)) * emphasis.get("p", 1.0)
    k_target = float(targets.get("k_kg_per_acre", 0)) * emphasis.get("k", 1.0)

    nutrients = [
        ("nitrogen", "N", n_acre, n_target),
        ("phosphorus", "P", p_acre, p_target),
        ("potassium", "K", k_acre, k_target),
    ]

    gaps: list[dict[str, Any]] = []
    recommendations: list[str] = []

    for name, symbol, farmer_val, target in nutrients:
        if target <= 0:
            continue
        ratio = farmer_val / target
        status = _nutrient_status(ratio)
        gap_pct = round((1 - ratio) * 100, 1) if ratio < 1 else round((ratio - 1) * 100, 1)
        entry = {
            "nutrient": name,
            "symbol": symbol,
            "status": status,
            "farmer_kg_per_acre": round(farmer_val, 1),
            "target_kg_per_acre": round(target, 1),
            "ratio": round(ratio, 3),
        }
        gaps.append(entry)
        if status == "low":
            recommendations.append(
                f"Low {name} ({symbol}): farmer ~{entry['farmer_kg_per_acre']} kg/acre vs "
                f"target ~{entry['target_kg_per_acre']} kg/acre for {defaults['display_name']}"
                + (f" at {growth_stage}" if growth_stage else "")
                + f" (~{abs(gap_pct)}% below target)."
            )
        elif status == "high":
            recommendations.append(
                f"High {name} ({symbol}): ~{gap_pct}% above target — avoid excess {symbol} application."
            )

    ph_assessment: dict[str, Any] | None = None
    ph_min = targets.get("optimal_ph_min")
    ph_max = targets.get("optimal_ph_max")
    if ph is not None and ph_min is not None and ph_max is not None:
        ph_min_f = float(ph_min)
        ph_max_f = float(ph_max)
        if ph < ph_min_f:
            ph_status = "low"
            recommendations.append(
                f"Soil pH {ph} is below optimal range {ph_min_f}-{ph_max_f} for {defaults['display_name']} — consider liming."
            )
        elif ph > ph_max_f:
            ph_status = "high"
            recommendations.append(
                f"Soil pH {ph} is above optimal range {ph_min_f}-{ph_max_f} for {defaults['display_name']}."
            )
        else:
            ph_status = "optimal"
        ph_assessment = {
            "ph": ph,
            "optimal_min": ph_min_f,
            "optimal_max": ph_max_f,
            "status": ph_status,
        }

    low_nutrients = [g["nutrient"] for g in gaps if g["status"] == "low"]
    summary = (
        f"{defaults['display_name']}: "
        + (f"low {', '.join(low_nutrients)}." if low_nutrients else "NPK within indicative targets.")
    )

    return {
        "crop": crop_id,
        "display_name": defaults["display_name"],
        "growth_stage": growth_stage,
        "nutrient_units_input": nutrient_units,
        "gaps": gaps,
        "ph_assessment": ph_assessment,
        "recommendations": recommendations,
        "summary": summary,
        "source": "crop_registry",
    }


class TreatmentCostArgs(BaseModel):
    crop: str
    disease: str
    severity: str = "moderate"
    area_acres: float = Field(gt=0)


def estimate_treatment_cost(crop: str, disease: str, severity: str = "moderate", area_acres: float = 1.0) -> dict[str, Any]:
    """Phase 4: crop + disease severity → indicative spray/labor cost."""
    from app.services.crop_registry import get_crop_defaults

    defaults = get_crop_defaults(crop)
    per_acre = defaults.get("default_input_costs_per_acre") or {}
    base_pesticide = float(per_acre.get("pesticide_cost", 3000))
    labor = float(per_acre.get("labor_cost", 5000)) * 0.15
    severity_mult = {"low": 0.6, "moderate": 1.0, "high": 1.4, "none": 0.0, "uncertain": 0.8}.get(
        severity.lower(), 1.0
    )
    if disease == "healthy":
        severity_mult = 0.0
    spray = round(base_pesticide * severity_mult * area_acres, 2)
    labor_cost = round(labor * severity_mult * area_acres, 2)
    total = round(spray + labor_cost, 2)
    return {
        "crop": defaults["crop_id"],
        "disease": disease,
        "severity": severity,
        "area_acres": area_acres,
        "spray_cost_inr": spray,
        "labor_cost_inr": labor_cost,
        "total_treatment_cost_inr": total,
        "source": "crop_registry_indicative",
    }


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
    registry.register("interpret_soil_npk", interpret_soil_npk, SoilNpkArgs)
    registry.register("estimate_treatment_cost", estimate_treatment_cost, TreatmentCostArgs)
