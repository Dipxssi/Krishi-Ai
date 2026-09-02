"""Expand routing eval set to 150+ multi-crop queries (Phase 2.1)."""

from __future__ import annotations

import json
from pathlib import Path

CROPS = ["tomato", "potato", "onion", "maize", "wheat", "rice", "cotton"]

TEMPLATES = [
    ("Should I plant {crop} now with my budget and weather?", ["weather", "finance", "market", "soil"], "medium"),
    ("What is the mandi price for {crop} today?", ["market"], "low"),
    ("Calculate profit for 2 acres of {crop}.", ["finance", "market"], "medium"),
    ("{crop} leaves have spots after rain — treat or wait?", ["crop_health", "weather", "knowledge_retriever"], "high"),
    ("Is my soil NPK suitable for {crop}?", ["soil", "knowledge_retriever"], "medium"),
    ("Drought forecast — irrigate {crop} now?", ["weather", "crop_health", "soil"], "high"),
    ("Loan or subsidy for {crop} fertilizer cost?", ["finance"], "low"),
    ("Sell {crop} early or store if price is falling?", ["market", "finance"], "medium"),
    ("Break-even price for my {crop} harvest?", ["finance", "market"], "medium"),
    ("Equipment rental for {crop} land preparation?", ["equipment"], "low"),
]

RISK = {"low": "low", "medium": "medium", "high": "high"}


def main() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "eval" / "queries.jsonl"
    existing: list[dict] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing.append(json.loads(line))
    ids = {r["id"] for r in existing}
    start = len(existing) + 1
    new_rows: list[dict] = []
    idx = start
    for crop in CROPS:
        for template, agents, risk in TEMPLATES:
            qid = f"q{idx:03d}"
            if qid in ids:
                idx += 1
                continue
            query = template.format(crop=crop)
            new_rows.append(
                {
                    "id": qid,
                    "query": query,
                    "required_agents": agents,
                    "expected_tools": ["search_crop_knowledge"] if "crop_health" in agents else [],
                    "risk_level": risk,
                    "crop": crop,
                }
            )
            idx += 1
    all_rows = existing + new_rows
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in all_rows) + "\n", encoding="utf-8")
    print(f"Wrote {len(all_rows)} queries to {path} (+{len(new_rows)} new)")


if __name__ == "__main__":
    main()
