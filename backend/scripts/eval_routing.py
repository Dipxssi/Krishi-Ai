#!/usr/bin/env python3
"""Multi-label routing evaluation.

Usage (from backend/):
  uv run python scripts/eval_routing.py
  uv run python scripts/eval_routing.py --threshold 0.45 --mode keyword
  uv run python scripts/eval_routing.py --json-out data/eval/last_run.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure backend root is on path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

# Avoid accidental live Gemini during eval unless user wants it
os.environ.setdefault("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

from app.core.config import get_settings
from app.orchestrator.metrics import aggregate_scores, score_sets
from app.orchestrator.router import score_query


def load_queries(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def route_for_eval(query: str, *, mode: str, threshold: float, cost_lambda: float) -> list[str]:
    # Keyword eval never calls Gemini (avoids 429 quota burns).
    allow_remote = mode != "keyword"
    selected, _ = score_query(
        query,
        mode=mode,
        threshold=threshold,
        cost_lambda=cost_lambda,
        allow_remote_embeddings=allow_remote,
    )
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate multi-label agent routing")
    parser.add_argument(
        "--data",
        type=Path,
        default=BACKEND_ROOT / "data" / "eval" / "queries.jsonl",
    )
    parser.add_argument("--mode", choices=["keyword", "embedding", "hybrid"], default=None)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--cost-lambda", type=float, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--show-misses", action="store_true", help="Print per-query mismatches")
    args = parser.parse_args()

    get_settings.cache_clear()
    settings = get_settings()
    mode = args.mode or settings.router_mode
    threshold = args.threshold if args.threshold is not None else settings.router_threshold
    cost_lambda = args.cost_lambda if args.cost_lambda is not None else settings.router_cost_lambda

    queries = load_queries(args.data)
    per_row = []
    details = []

    for item in queries:
        predicted = route_for_eval(
            item["query"],
            mode=mode,
            threshold=threshold,
            cost_lambda=cost_lambda,
        )
        required = item["required_agents"]
        scores = score_sets(predicted, required)
        per_row.append(scores)
        details.append(
            {
                "id": item.get("id"),
                "query": item["query"],
                "required_agents": required,
                "predicted_agents": predicted,
                "precision": scores.precision,
                "recall": scores.recall,
                "f1": scores.f1,
                "jaccard": scores.jaccard,
                "exact_match": scores.exact_match,
                "unnecessary": sorted(set(predicted) - set(required)),
                "missing": sorted(set(required) - set(predicted)),
                "risk_level": item.get("risk_level"),
                "expected_tools": item.get("expected_tools", []),
            }
        )

    summary = aggregate_scores(per_row)
    summary.update(
        {
            "mode": mode,
            "threshold": threshold,
            "cost_lambda": cost_lambda,
            "data": str(args.data),
        }
    )

    print("=== KrishiAi Routing Eval ===")
    print(f"data: {args.data}  n={int(summary['n'])}")
    print(f"mode={mode}  threshold={threshold}  cost_lambda={cost_lambda}")
    print("---")
    for key in (
        "precision",
        "recall",
        "f1",
        "jaccard",
        "exact_match_accuracy",
        "avg_agents_selected",
        "unnecessary_agent_rate",
        "missing_agent_rate",
    ):
        print(f"{key:24s} {summary[key]:.4f}")

    if args.show_misses:
        print("\n--- mismatches ---")
        for d in details:
            if not d["exact_match"]:
                print(
                    f"{d['id']}: missing={d['missing']} unnecessary={d['unnecessary']}\n"
                    f"  Q: {d['query'][:90]}"
                )

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"summary": summary, "details": details}
        args.json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
