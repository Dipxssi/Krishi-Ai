"""Routing metrics and labeled eval tests."""

import os
from pathlib import Path

os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("GROQ_API_KEY", "")

from app.orchestrator.metrics import aggregate_scores, score_sets
from app.orchestrator.router import score_query


EVAL_PATH = Path(__file__).resolve().parents[1] / "data" / "eval" / "queries.jsonl"


def test_score_sets_perfect():
    s = score_sets(["finance", "market"], ["market", "finance"])
    assert s.exact_match
    assert s.f1 == 1.0
    assert s.jaccard == 1.0


def test_score_sets_partial():
    s = score_sets(["finance", "weather"], ["finance", "market"])
    assert s.precision == 0.5
    assert s.recall == 0.5
    assert s.unnecessary == 1
    assert s.missing == 1


def test_aggregate_scores():
    rows = [
        score_sets(["a"], ["a"]),
        score_sets(["a", "b"], ["a"]),
    ]
    agg = aggregate_scores(rows)
    assert agg["n"] == 2
    assert agg["exact_match_accuracy"] == 0.5
    assert agg["avg_agents_selected"] == 1.5


def test_eval_file_exists_and_has_50_plus():
    assert EVAL_PATH.exists()
    lines = [ln for ln in EVAL_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) >= 50


def test_keyword_router_demo_query_covers_core_agents():
    q = (
        "Tomato market price is falling, limited budget, rain expected next week. "
        "Treat, continue, or sell early?"
    )
    selected, _ = score_query(
        q,
        mode="keyword",
        threshold=0.40,
        cost_lambda=0.02,
        allow_remote_embeddings=False,
    )
    assert "market" in selected
    assert "finance" in selected
    assert "weather" in selected
    assert "crop_health" in selected


def test_keyword_mode_skips_remote_path():
    # Smoke: planting query should multi-route without needing Gemini
    selected, _ = score_query(
        "Should I plant tomatoes now with my current budget?",
        mode="keyword",
        threshold=0.45,
        cost_lambda=0.02,
        allow_remote_embeddings=False,
    )
    assert "finance" in selected
    assert "market" in selected
    assert "weather" in selected
