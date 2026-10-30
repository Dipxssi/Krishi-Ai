"""Step 1.2 — finance agent uses crop registry yields and costs."""

import pytest

from app.agents.finance_agent import finance_agent, _is_scheme_focused
from app.schemas.models import FarmContext
from app.services.crop_registry import build_profit_inputs, get_crop_defaults
from app.tools.agriculture import calculate_profit, register_all_tools, search_loans
from app.tools.registry import tool_registry


@pytest.fixture(autouse=True)
def _register_tools():
    register_all_tools(tool_registry)


def test_build_profit_inputs_uses_registry_yields():
    tomato = build_profit_inputs("tomato", area_acres=2.0, selling_price=30.0)
    potato = build_profit_inputs("potato", area_acres=2.0, selling_price=30.0)
    wheat = build_profit_inputs("wheat", area_acres=2.0, selling_price=30.0)

    assert tomato["expected_yield"] == pytest.approx(
        get_crop_defaults("tomato")["expected_yield_kg_per_acre"]
    )
    assert potato["expected_yield"] == pytest.approx(
        get_crop_defaults("potato")["expected_yield_kg_per_acre"]
    )
    assert tomato["expected_yield"] != wheat["expected_yield"]
    assert tomato["crop_id"] == "tomato"


def test_build_profit_inputs_scales_costs_by_area():
    one = build_profit_inputs("onion", area_acres=1.0, selling_price=25.0)
    two = build_profit_inputs("onion", area_acres=2.0, selling_price=25.0)

    assert two["seed_cost"] == pytest.approx(one["seed_cost"] * 2)
    assert two["labor_cost"] == pytest.approx(one["labor_cost"] * 2)


def _profit_kwargs(profit_inputs: dict) -> dict:
    keys = (
        "area",
        "expected_yield",
        "selling_price",
        "seed_cost",
        "fertilizer_cost",
        "pesticide_cost",
        "labor_cost",
        "irrigation_cost",
        "equipment_cost",
        "transport_cost",
    )
    return {k: profit_inputs[k] for k in keys}


def test_tomato_vs_potato_profit_differs_at_same_price():
    price = 20.0
    area = 1.0
    tomato_profit = calculate_profit(**_profit_kwargs(build_profit_inputs("tomato", area_acres=area, selling_price=price)))
    potato_profit = calculate_profit(**_profit_kwargs(build_profit_inputs("potato", area_acres=area, selling_price=price)))

    assert tomato_profit["revenue"] != potato_profit["revenue"]
    assert tomato_profit["profit"] != potato_profit["profit"]


def test_loan_plus_harvest_not_scheme_only():
    query = "What is the cost to take out potato harvest? Can I take a loan?"
    assert _is_scheme_focused(query) is False


def test_loan_plus_harvest_cost_runs_profit_tools():
    ctx = FarmContext(
        farmer_id="f1",
        location="Kolkata",
        farm_area_acres=2.0,
        crop="potato",
        growth_stage="harvest",
        soil_type="loam",
        irrigation_available=True,
        budget=50000,
        preferred_language="English",
        season="rabi",
    )
    query = "What is the cost to take out potato harvest in West Bengal? Can I take a loan?"
    result = finance_agent(query, ctx)
    harvest_evidence = [e for e in result.tool_evidence if e.unit == "INR harvest-related"]
    assert harvest_evidence
    assert harvest_evidence[0].value == pytest.approx(62000.0)  # (22000+4000+5000)*2
    profit_evidence = [e for e in result.tool_evidence if e.unit == "INR profit"]
    assert profit_evidence


def test_finance_agent_emits_crop_yield_evidence():
    ctx = FarmContext(
        farmer_id="f1",
        location="Nashik",
        farm_area_acres=1.0,
        crop="maize",
        growth_stage="vegetative",
        soil_type="loam",
        irrigation_available=True,
        budget=50000,
        preferred_language="English",
        season="kharif",
    )
    result = finance_agent("What is my expected profit this season?", ctx)
    yield_evidence = [e for e in result.tool_evidence if e.unit == "kg/acre yield"]
    assert yield_evidence
    assert yield_evidence[0].source == "crop_registry:maize"
    assert yield_evidence[0].value == pytest.approx(
        get_crop_defaults("maize")["expected_yield_kg_per_acre"]
    )


def test_loan_question_is_not_filtered_out_by_the_full_sentence():
    found = search_loans(
        purpose="What agricultural loan options are there for my tomato farm in Bengaluru?"
    )
    ids = [item["id"] for item in found["matches"]]
    assert "kcc-crop-loan" in ids
    assert found["matches"][0]["id"] == "kcc-crop-loan"


def test_specific_loan_word_still_narrows_the_catalog():
    found = search_loans(purpose="I need a gold loan for this season")
    ids = [item["id"] for item in found["matches"]]
    assert ids == ["agri-gold-loan"]


def test_finance_agent_puts_kcc_in_evidence_for_a_loan_question(monkeypatch):
    from app.services import llm

    monkeypatch.setattr(llm, "is_llm_available", lambda: False)
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
    query = (
        "Earlier notes: Tomato Septoria leaf disease.\n\n"
        "Farmer question:\n"
        "What agricultural loan options are there for my tomato farm in Bengaluru?"
    )
    result = finance_agent(query, ctx)
    sources = [item.source for item in result.tool_evidence]
    assert "loan:kcc-crop-loan" in sources
    assert "Kisan Credit Card" in result.recommendation
    assert "Bengaluru" in result.recommendation
    assert "No matching loan" not in result.recommendation
