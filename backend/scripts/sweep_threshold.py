#!/usr/bin/env python3
"""Sweep router threshold (keyword mode only — no Gemini calls)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.orchestrator.metrics import aggregate_scores, score_sets
from app.orchestrator.router import score_query


def load_queries(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> int:
    data = BACKEND_ROOT / "data" / "eval" / "queries.jsonl"
    queries = load_queries(data)
    print("mode=keyword (no Gemini embeds)")
    print(f"{'threshold':>10} {'f1':>8} {'recall':>8} {'prec':>8} {'exact':>8} {'avg_n':>8}")
    for thr in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]:
        rows = []
        for item in queries:
            pred, _ = score_query(
                item["query"],
                mode="keyword",
                threshold=thr,
                cost_lambda=0.02,
                allow_remote_embeddings=False,
            )
            rows.append(score_sets(pred, item["required_agents"]))
        summary = aggregate_scores(rows)
        print(
            f"{thr:10.2f} {summary['f1']:8.4f} {summary['recall']:8.4f} "
            f"{summary['precision']:8.4f} {summary['exact_match_accuracy']:8.4f} "
            f"{summary['avg_agents_selected']:8.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
