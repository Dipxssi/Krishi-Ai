"""Question bank size, safety, routing, and next-step replies."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from app.orchestrator.orchestrator import UNSAFE_CHEMICAL_PATTERNS
from app.orchestrator.question_bank import bank_dir, best_for_agent, clear_cache

BACKEND = Path(__file__).resolve().parents[1]
AGENTS = [
    "crop_health",
    "finance",
    "equipment",
    "market",
    "weather",
    "soil",
    "knowledge_retriever",
]
LANGS = ("en", "hi", "kn")
_BANNED = re.compile(r"%|₹|\bRs\b|\bINR\b|\d|Kisan Vikas", re.IGNORECASE)


def _rows(agent: str, lang: str) -> list[dict]:
    path = bank_dir() / f"{agent}.{lang}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_each_file_has_index_and_holdout_counts():
    for agent in AGENTS:
        for lang in LANGS:
            rows = _rows(agent, lang)
            counts = Counter(row["split"] for row in rows)
            assert counts["index"] == 1000
            assert counts["holdout"] == 50
            questions = [row["question"] for row in rows]
            assert len(questions) == len(set(questions))


def test_next_steps_are_safe_and_loan_links_exist():
    loans = {item["id"] for item in json.loads((BACKEND / "data" / "knowledge" / "loans.json").read_text(encoding="utf-8"))}
    for agent in AGENTS:
        for lang in LANGS:
            for row in _rows(agent, lang):
                step = row["next_step"]
                assert not _BANNED.search(step), row["id"]
                for pattern in UNSAFE_CHEMICAL_PATTERNS:
                    assert re.search(pattern, step, flags=re.IGNORECASE) is None, row["id"]
                if row["linked_record_id"] is not None:
                    assert row["linked_record_id"] in loans


def test_holdout_rows_are_not_in_the_loaded_index():
    clear_cache()
    from app.orchestrator.question_bank import _load

    loaded = {row.question for bucket in _load().values() for row in bucket.rows}
    for agent in AGENTS:
        for lang in LANGS:
            for row in _rows(agent, lang):
                if row["split"] == "holdout":
                    assert row["question"] not in loaded
                else:
                    assert row["question"] in loaded


def test_bengaluru_tomato_loan_selects_finance_and_names_documents(monkeypatch):
    from types import SimpleNamespace

    from app.agents.finance_agent import finance_agent
    from app.orchestrator.router import route_query
    from app.schemas.models import FarmContext
    from app.services import llm
    from app.tools.agriculture import register_all_tools
    from app.tools.registry import tool_registry

    monkeypatch.setattr(llm, "is_llm_available", lambda: False)
    monkeypatch.setattr(
        "app.orchestrator.router.get_settings",
        lambda: SimpleNamespace(router_mode="keyword", router_threshold=0.60, router_cost_lambda=0.05),
    )
    register_all_tools(tool_registry)
    query = (
        "Earlier notes: Tomato Septoria leaf disease. The leaf needs treatment.\n\n"
        "Farmer question:\n"
        "What agricultural loan options are there for my tomato farm in Bengaluru?"
    )
    selected, _ = route_query(query)
    assert "finance" in selected
    assert "crop_health" not in selected

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
    result = finance_agent(query, ctx)
    assert "Kisan Credit Card" in result.recommendation
    assert "Bengaluru" in result.recommendation
    assert "documents" in result.recommendation.lower()
    assert any(item.source.startswith("loan:kcc-crop-loan") for item in result.tool_evidence)


def test_kannada_question_returns_a_kannada_next_step():
    row = next(item for item in _rows("finance", "kn") if item["split"] == "index")
    hit = best_for_agent("finance", row["question"], "kn")
    assert hit is not None
    assert hit.score >= 0.55
    step = hit.row.next_step
    assert any("\u0c80" <= char <= "\u0cff" for char in step)
    assert "Take land records" not in step


def test_holdout_questions_select_their_agent(monkeypatch):
    from types import SimpleNamespace

    from app.orchestrator.router import route_query

    monkeypatch.setattr(
        "app.orchestrator.router.get_settings",
        lambda: SimpleNamespace(router_mode="keyword", router_threshold=0.60, router_cost_lambda=0.05),
    )
    for agent in AGENTS:
        for lang in LANGS:
            holds = [row for row in _rows(agent, lang) if row["split"] == "holdout"]
            hits = sum(1 for row in holds if agent in route_query(row["question"])[0])
            assert hits >= 45, f"{agent}.{lang} matched {hits} of {len(holds)}"


def test_missing_bank_directory_does_not_break_routing(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from app.orchestrator.router import route_query

    monkeypatch.setattr(
        "app.orchestrator.router.get_settings",
        lambda: SimpleNamespace(router_mode="keyword", router_threshold=0.60, router_cost_lambda=0.05),
    )
    monkeypatch.setattr("app.orchestrator.question_bank.bank_dir", lambda: tmp_path / "missing-bank")
    clear_cache()
    try:
        selected, _ = route_query("How can I improve the growth of tomato plants?")
    finally:
        clear_cache()
    assert "crop_health" in selected
    assert "finance" not in selected
