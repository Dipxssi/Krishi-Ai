"""Phase 1 sign-off — multi-crop routing, profit, and soil differ by crop."""

import os

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ROUTER_MODE"] = "keyword"
os.environ["GROQ_API_KEY"] = ""

from app.core.config import get_settings
from app.db.session import init_db, reset_engine
from app.main import app
from app.orchestrator.router import keyword_scores, select_agents
from app.services.crop_registry import build_profit_inputs
from app.tools.agriculture import interpret_soil_npk
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset():
    get_settings.cache_clear()
    reset_engine()
    init_db()
    yield
    reset_engine()


@pytest.mark.parametrize("crop", ["tomato", "potato", "maize"])
def test_planting_query_routes_core_agents(crop: str):
    query = f"Should I plant {crop} now? Market and weather look uncertain."
    scores = keyword_scores(query)
    selected = select_agents(scores, threshold=0.40)
    assert "weather" in selected
    assert "market" in selected or "finance" in selected


def test_profit_differs_across_crops():
    price = 25.0
    area = 2.0
    profits = {}
    for crop in ("tomato", "potato", "maize"):
        args = build_profit_inputs(crop, area_acres=area, selling_price=price)
        from app.tools.agriculture import calculate_profit

        profits[crop] = calculate_profit(
            area=args["area"],
            expected_yield=args["expected_yield"],
            selling_price=args["selling_price"],
            seed_cost=args["seed_cost"],
            fertilizer_cost=args["fertilizer_cost"],
            pesticide_cost=args["pesticide_cost"],
            labor_cost=args["labor_cost"],
            irrigation_cost=args["irrigation_cost"],
            equipment_cost=args["equipment_cost"],
            transport_cost=args["transport_cost"],
        )["profit"]
    assert profits["tomato"] != profits["maize"]
    assert profits["potato"] != profits["maize"]


def test_soil_npk_advice_differs_by_crop():
    potato = interpret_soil_npk("potato", n=40, p=30, k=40, nutrient_units="kg_per_ha")
    maize = interpret_soil_npk("maize", n=40, p=30, k=40, nutrient_units="kg_per_ha")
    assert potato["summary"] != maize["summary"]


def test_query_returns_tool_traces():
    from tests.auth_helpers import signup_and_headers

    client = TestClient(app)
    headers, farmer_id, _ = signup_and_headers(client, email="maize@example.com")
    r = client.put(
        f"/farmers/{farmer_id}",
        headers=headers,
        json={
            "location": "Nashik",
            "farm_area_acres": 2.0,
            "crop": "maize",
            "growth_stage": "vegetative",
            "soil_type": "loam",
            "soil_npk": {"n": 40, "p": 30, "k": 40},
            "irrigation_available": True,
            "budget": 25000,
            "preferred_language": "English",
            "season": "kharif",
        },
    )
    assert r.status_code == 200, r.text
    r = client.post(
        "/query",
        headers=headers,
        json={"farmer_id": farmer_id, "query": "Maize fertilizer plan for low potassium soil?"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tool_traces"]
    assert body["decision_score"] is not None


def test_knowledge_loans_endpoint():
    client = TestClient(app)
    r = client.get("/knowledge/loans")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 5
    assert any("KCC" in item.get("name", "") for item in body["items"])
