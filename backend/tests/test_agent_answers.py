"""Each specialist answers with its own facts and does not leak internal labels."""

import pytest

from app.agents.crop_agent import crop_health_agent
from app.agents.equipment_agent import equipment_agent
from app.agents.knowledge_agent import knowledge_retriever_agent
from app.agents.soil_agent import soil_agent
from app.agents.weather_agent import weather_agent
from app.schemas.models import FarmContext
from app.tools.agriculture import register_all_tools
from app.tools.registry import tool_registry


@pytest.fixture(autouse=True)
def _tools_and_no_llm(monkeypatch):
    from app.services import llm

    monkeypatch.setattr(llm, "is_llm_available", lambda: False)
    register_all_tools(tool_registry)


def _farm(**overrides) -> FarmContext:
    data = dict(
        farmer_id="f1",
        location="Bengaluru",
        farm_area_acres=2.0,
        crop="tomato",
        growth_stage="fruiting",
        soil_type="loam",
        irrigation_available=True,
        budget=50000,
        preferred_language="English",
        season="rabi",
    )
    data.update(overrides)
    return FarmContext(**data)


def test_weather_answer_gives_the_outlook_without_the_mock_label():
    result = weather_agent("Will it rain on my tomato farm this week?", _farm())
    text = result.recommendation
    assert "rainfall" in text.lower()
    assert "Bengaluru" in text
    assert "Krishi Vigyan Kendra" in text
    assert "mock_weather_service" not in text
    assert "source=" not in text


def test_equipment_answer_names_a_machine_and_where_to_ask():
    result = equipment_agent("Which sprayer can I hire for my tomato farm?", _farm())
    text = result.recommendation
    assert "Sprayer" in text
    assert "Krishi Vigyan Kendra" in text
    assert "custom hiring" in text
    assert "Citations:" not in text
    assert "none found" not in text.lower()


def test_soil_answer_sends_the_farmer_to_a_soil_test_when_npk_is_missing():
    result = soil_agent("Is my soil good for tomatoes?", _farm())
    text = result.recommendation
    assert "Krishi Vigyan Kendra" in text
    assert "soil" in text.lower()
    assert "Provide lab NPK" not in text
    assert "Citations:" not in text


def test_knowledge_answer_uses_the_crop_note():
    result = knowledge_retriever_agent("How do I grow tomatoes?", _farm())
    text = result.recommendation
    assert "Retrieved guidance" not in text
    assert "rag:" not in text
    guidance = [item for item in result.tool_evidence if item.unit == "guidance"]
    assert guidance
    assert guidance[0].value[:80] in text or "Crop guidance" in text


def test_crop_health_text_answer_uses_guidance_and_names_the_kvk():
    result = crop_health_agent("What should I watch on my tomato leaves?", _farm())
    text = result.recommendation
    assert "Krishi Vigyan Kendra" in text
    assert "Citations:" not in text
    assert "mock_" not in text
