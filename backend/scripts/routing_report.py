"""Generate HTML routing metrics report (Phase 2.6)."""

from __future__ import annotations

import json
from pathlib import Path

from app.orchestrator.metrics import aggregate_scores, score_sets
from app.orchestrator.router import score_query
from app.core.config import get_settings


def main() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "eval" / "queries.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    settings = get_settings()
    per_query = []
    for row in rows:
        selected, scores = score_query(
            row["query"],
            mode=settings.router_mode if settings.router_mode != "supervised" else "hybrid",
            threshold=settings.router_threshold,
            cost_lambda=settings.router_cost_lambda,
        )
        metrics = score_sets(selected, row.get("required_agents", []))
        per_query.append({**row, "selected": selected, "metrics": metrics})
    agg = aggregate_scores([p["metrics"] for p in per_query])
    out = Path(__file__).resolve().parents[1] / "data" / "eval" / "routing_report.html"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>KrishiAi Routing Report</title>
    <style>body{{font-family:sans-serif;max-width:900px;margin:2rem auto}} table{{border-collapse:collapse;width:100%}}
    td,th{{border:1px solid #ccc;padding:6px;font-size:14px}}</style></head><body>
    <h1>Routing metrics ({len(rows)} queries)</h1>
    <p>Mode: {settings.router_mode} | Threshold: {settings.router_threshold}</p>
    <ul>
    <li>Micro F1: {agg.get('f1', 0):.3f}</li>
    <li>Avg agents/query: {agg.get('avg_agents_selected', 0):.2f}</li>
    </ul>
    <table><tr><th>ID</th><th>Crop</th><th>Selected</th><th>Required</th><th>F1</th></tr>
    """
    for p in per_query[:50]:
        m = p["metrics"]
        html += (
            f"<tr><td>{p['id']}</td><td>{p.get('crop','')}</td>"
            f"<td>{', '.join(p['selected'])}</td><td>{', '.join(p.get('required_agents',[]))}</td>"
            f"<td>{m.f1:.2f}</td></tr>"
        )
    html += "</table></body></html>"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
