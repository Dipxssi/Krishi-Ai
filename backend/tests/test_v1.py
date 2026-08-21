import os

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

# Isolate test DB before app import
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ROUTER_MODE"] = "keyword"
os.environ["ROUTER_THRESHOLD"] = "0.40"
os.environ["ROUTER_COST_LAMBDA"] = "0.02"
os.environ["GEMINI_API_KEY"] = ""

from app.core.config import get_settings
from app.db.session import init_db, reset_engine
from app.main import app
from app.orchestrator.router import (
    apply_cost_penalty,
    keyword_scores,
    select_agents,
)
from app.tools.agriculture import calculate_profit, estimate_decision_score, get_market_price
from app.tools.registry import ToolRegistry


@pytest.fixture(autouse=True)
def _reset_db():
    get_settings.cache_clear()
    reset_engine()
    init_db()
    yield
    reset_engine()


def test_calculate_profit():
    result = calculate_profit(
        area=2,
        expected_yield=1000,
        selling_price=40,
        seed_cost=1000,
        fertilizer_cost=2000,
        pesticide_cost=500,
        labor_cost=1500,
        irrigation_cost=500,
        equipment_cost=400,
        transport_cost=100,
    )
    assert result["revenue"] == 80000.0
    assert result["total_cost"] == 6000.0
    assert result["profit"] == 74000.0
    assert result["break_even_price"] == 3.0


def test_decision_score_weights():
    score = estimate_decision_score(
        agronomic_suitability=0.8,
        expected_profit=20000,
        water_risk=0.2,
        disease_risk=0.2,
        input_cost=10000,
        agronomic_weight=0.6,
        economic_weight=0.4,
    )
    assert 0 <= score["final_score"] <= 1
    assert score["agronomic_weight"] == 0.6
    assert score["economic_weight"] == 0.4


def test_router_threshold_and_fallback():
    scores = {"finance": 0.2, "market": 0.1, "weather": 0.15}
    selected = select_agents(scores, threshold=0.60)
    assert selected == ["finance"]  # top-1 fallback


def test_router_cost_penalty():
    base = {"weather": 0.7, "crop_health": 0.72}
    adjusted = apply_cost_penalty(base, cost_lambda=0.05)
    assert adjusted["weather"] > adjusted["crop_health"]  # crop_health cost 3 vs weather 1


def test_keyword_multi_label():
    scores = keyword_scores(
        "Tomato market price is falling, limited budget, rain expected — treat or sell early?"
    )
    selected = select_agents(scores, threshold=0.40)
    assert "market" in selected
    assert "finance" in selected
    assert "weather" in selected


def test_tool_invalid_args_and_repair():
    class Args(BaseModel):
        crop: str
        market: str
        date: str

    def fn(crop: str, market: str, date: str):
        return {"crop": crop, "market": market, "date": date}

    reg = ToolRegistry()
    reg.register("get_market_price", fn, Args)
    trace = reg.execute(
        agent="market",
        tool="get_market_price",
        arguments={"crop": "tomato", "market": "Pune"},
        repair_fn=lambda args, _err: {**args, "date": "2026-08-21"},
    )
    assert trace.status == "success"
    assert trace.arguments["date"] == "2026-08-21"


def test_market_price_labeled_mock():
    out = get_market_price("tomato", "Nashik", "2026-08-21")
    assert out["is_mock"] is True
    assert out["current_price"] > 0
    assert out["forecast_uncertainty"] == "medium"


def test_api_farmers_and_query():
    client = TestClient(app)
    payload = {
        "farmer_id": "f1",
        "location": "Nashik",
        "farm_area_acres": 2.0,
        "crop": "tomato",
        "growth_stage": "fruiting",
        "soil_type": "loam",
        "soil_npk": {"n": 40, "p": 30, "k": 40},
        "irrigation_available": True,
        "budget": 20000,
        "preferred_language": "English",
        "season": "kharif",
    }
    r = client.post("/farmers", json=payload)
    assert r.status_code == 201, r.text

    q = client.post(
        "/query",
        json={
            "farmer_id": "f1",
            "query": "Tomato market price is falling, limited budget, rain expected next week. Should I treat, continue, or sell early?",
        },
    )
    assert q.status_code == 200, q.text
    body = q.json()
    assert body["farmer_id"] == "f1"
    assert "market" in body["agents_used"]
    assert "finance" in body["agents_used"]
    assert "weather" in body["agents_used"]
    assert body["evidence"]
    assert body["tool_traces"]
    assert body["final_recommendation"]
    assert body["decision_score"] is not None
    assert body["revision_count"] >= 1


def test_query_requires_farmer():
    client = TestClient(app)
    r = client.post("/query", json={"farmer_id": "missing", "query": "hello"})
    assert r.status_code == 404
