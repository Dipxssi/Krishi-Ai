"""Step 1.5 — interpret_soil_npk tool and soil agent."""

import os

import pytest

os.environ["GROQ_API_KEY"] = ""

from app.agents.soil_agent import soil_agent
from app.schemas.models import FarmContext
from app.tools.agriculture import interpret_soil_npk, register_all_tools
from app.tools.registry import tool_registry


@pytest.fixture(autouse=True)
def _tools():
    register_all_tools(tool_registry)


def test_potato_low_potassium_at_tuber_stage():
    out = interpret_soil_npk(
        crop="potato",
        n=40,
        p=30,
        k=40,
        growth_stage="tuber_bulking",
        nutrient_units="kg_per_ha",
    )
    k_gap = next(g for g in out["gaps"] if g["symbol"] == "K")
    assert k_gap["status"] == "low"
    assert any("potassium" in r.lower() or "Low" in r for r in out["recommendations"])


def test_tomato_vs_potato_npk_gaps_differ():
    potato = interpret_soil_npk("potato", n=40, p=30, k=40, nutrient_units="kg_per_ha")
    maize = interpret_soil_npk("maize", n=40, p=30, k=40, nutrient_units="kg_per_ha")
    potato_k = next(g for g in potato["gaps"] if g["symbol"] == "K")
    maize_k = next(g for g in maize["gaps"] if g["symbol"] == "K")
    assert potato_k["target_kg_per_acre"] != maize_k["target_kg_per_acre"]


def test_soil_agent_mentions_potassium_for_low_k():
    ctx = FarmContext(
        farmer_id="f1",
        location="Hooghly",
        farm_area_acres=1.0,
        crop="potato",
        growth_stage="tuber_bulking",
        soil_type="loam",
        soil_npk={"n": 40, "p": 30, "k": 40},
        irrigation_available=True,
        budget=30000,
        preferred_language="English",
        season="rabi",
    )
    result = soil_agent("Is my soil potassium enough for potato tubers?", ctx)
    recs = [e for e in result.tool_evidence if e.unit == "recommendation"]
    assert recs
    combined = " ".join(str(e.value) for e in result.tool_evidence).lower()
    assert "potassium" in combined or " k" in combined
