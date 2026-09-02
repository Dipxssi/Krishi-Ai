"""Supervised one-vs-rest router (Phase 2.4) using TF-IDF + sklearn."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.svm import LinearSVC

from app.core.config import get_settings
from app.orchestrator.catalog import AGENTS
from app.orchestrator.router import apply_cost_penalty, select_agents


def _eval_path() -> Path:
    backend = Path(__file__).resolve().parents[2]
    return backend / "data" / "eval" / "queries.jsonl"


@lru_cache(maxsize=1)
def _load_training_data() -> tuple[list[str], list[list[str]]]:
    path = _eval_path()
    queries: list[str] = []
    labels: list[list[str]] = []
    if not path.exists():
        return queries, labels
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        queries.append(row["query"])
        labels.append(row.get("required_agents", []))
    return queries, labels


@lru_cache(maxsize=1)
def _fitted_model():
    queries, label_lists = _load_training_data()
    if len(queries) < 10:
        return None, None, None
    mlb = MultiLabelBinarizer(classes=AGENTS)
    y = mlb.fit_transform(label_lists)
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=8000)
    x = vectorizer.fit_transform(queries)
    clf = OneVsRestClassifier(LinearSVC(max_iter=5000, class_weight="balanced"))
    clf.fit(x, y)
    return vectorizer, clf, mlb


def supervised_scores(query: str) -> dict[str, float]:
    vectorizer, clf, mlb = _fitted_model()
    if vectorizer is None or clf is None or mlb is None:
        return {a: 0.0 for a in AGENTS}
    x = vectorizer.transform([query])
    # decision_function gives margin per label
    margins = clf.decision_function(x)[0]
    if hasattr(margins, "__len__"):
        raw = {agent: float(margins[i]) for i, agent in enumerate(mlb.classes_)}
    else:
        raw = {mlb.classes_[0]: float(margins)}
    # squash to 0-1 via sigmoid-ish
    import math

    return {k: 1 / (1 + math.exp(-v)) for k, v in raw.items()}


def route_supervised(query: str, *, threshold: float, cost_lambda: float) -> tuple[list[str], dict[str, float]]:
    scores = supervised_scores(query)
    adjusted = apply_cost_penalty(scores, cost_lambda)
    selected = select_agents(adjusted, threshold)
    return selected, adjusted


def clear_supervised_cache() -> None:
    _load_training_data.cache_clear()
    _fitted_model.cache_clear()
