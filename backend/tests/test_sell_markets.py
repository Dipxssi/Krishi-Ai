"""Sell-to markets are named, and the mock label stays off the farmer reply."""

from app.agents.market_agent import market_agent
from app.schemas.models import FarmContext
from app.services.sell_markets import sell_markets_for
from app.tools.agriculture import get_market_price, register_all_tools
from app.tools.registry import tool_registry


def test_bengaluru_lists_yards_a_tomato_grower_can_use():
    names = sell_markets_for("Bengaluru Urban, Karnataka")
    assert "Yeshwanthpur APMC" in names
    assert "K.R. Market (City Market)" in names
    assert "HOPCOMS" in names


def test_mock_price_still_carries_the_yard_names():
    out = get_market_price("tomato", "Bengaluru", "2026-10-31")
    assert out["is_mock"] is True
    assert "Yeshwanthpur APMC" in out["sell_markets"]


def test_market_answer_names_yards_and_hides_the_mock_label(monkeypatch):
    from app.services import llm

    monkeypatch.setattr(llm, "is_llm_available", lambda: False)
    register_all_tools(tool_registry)
    ctx = FarmContext(
        farmer_id="f1",
        location="Bengaluru",
        farm_area_acres=1.0,
        crop="tomato",
        growth_stage="fruiting",
        soil_type="loam",
        irrigation_available=True,
        budget=50000,
        preferred_language="English",
        season="rabi",
    )
    result = market_agent("Where can I sell my tomatoes in Bengaluru?", ctx)
    text = result.recommendation
    assert "Yeshwanthpur APMC" in text
    assert "K.R. Market (City Market)" in text
    assert "HOPCOMS" in text
    assert "mock_market_service" not in text
    assert any(item.unit == "markets" and "Yeshwanthpur APMC" in str(item.value) for item in result.tool_evidence)
