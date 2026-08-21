"""Multi-label routing evaluation metrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SetScores:
    precision: float
    recall: float
    f1: float
    jaccard: float
    exact_match: bool
    predicted_count: int
    required_count: int
    unnecessary: int
    missing: int


def score_sets(predicted: list[str] | set[str], required: list[str] | set[str]) -> SetScores:
    pred = set(predicted)
    req = set(required)
    tp = len(pred & req)
    fp = len(pred - req)
    fn = len(req - pred)
    precision = tp / len(pred) if pred else 0.0
    recall = tp / len(req) if req else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    union = len(pred | req)
    jaccard = (tp / union) if union else 1.0
    return SetScores(
        precision=precision,
        recall=recall,
        f1=f1,
        jaccard=jaccard,
        exact_match=pred == req,
        predicted_count=len(pred),
        required_count=len(req),
        unnecessary=fp,
        missing=fn,
    )


def aggregate_scores(rows: list[SetScores]) -> dict[str, float]:
    n = len(rows) or 1
    return {
        "n": float(len(rows)),
        "precision": sum(r.precision for r in rows) / n,
        "recall": sum(r.recall for r in rows) / n,
        "f1": sum(r.f1 for r in rows) / n,
        "jaccard": sum(r.jaccard for r in rows) / n,
        "exact_match_accuracy": sum(1.0 for r in rows if r.exact_match) / n,
        "avg_agents_selected": sum(r.predicted_count for r in rows) / n,
        "avg_required_agents": sum(r.required_count for r in rows) / n,
        "unnecessary_agent_rate": sum(r.unnecessary for r in rows) / max(sum(r.predicted_count for r in rows), 1),
        "missing_agent_rate": sum(r.missing for r in rows) / max(sum(r.required_count for r in rows), 1),
    }
