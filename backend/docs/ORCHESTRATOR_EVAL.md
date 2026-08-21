# Orchestrator & routing evaluation

Guide for routing quality, validation, the revise loop, and the labeled evaluation harness.

## What’s included

| Path | Purpose |
|------|---------|
| [`data/eval/queries.jsonl`](../data/eval/queries.jsonl) | 55 labeled farmer queries |
| [`scripts/eval_routing.py`](../scripts/eval_routing.py) | Routing metrics runner |
| [`app/orchestrator/metrics.py`](../app/orchestrator/metrics.py) | Precision / recall / F1 / Jaccard helpers |
| [`app/orchestrator/router.py`](../app/orchestrator/router.py) | Multi-label router |
| [`app/orchestrator/orchestrator.py`](../app/orchestrator/orchestrator.py) | Plan–Critique–Revise + clarifying preface |

## Run routing eval

From `backend/`:

```bash
# Keyword-only (recommended — does NOT call Gemini, avoids quota 429s)
uv run python scripts/eval_routing.py --mode keyword --threshold 0.45 --show-misses
uv run python scripts/sweep_threshold.py

# Hybrid/embedding modes call Gemini — use sparingly on free tier
uv run python scripts/eval_routing.py --mode hybrid --threshold 0.45
```

Metrics printed:

- precision, recall, multi-label F1
- Jaccard similarity
- exact-match routing accuracy
- average agents selected
- unnecessary-agent rate / missing-agent rate

## How to tune

1. Run with `--show-misses` and note systematic gaps.
2. Adjust keywords in `app/orchestrator/catalog.py` **or** threshold / `ROUTER_COST_LAMBDA`.
3. Re-run eval; keep a small results table (threshold → F1).
4. Prefer higher recall on high `risk_level` queries (disease + money + weather).

Example env knobs (repo root `.env`):

```env
ROUTER_MODE=keyword
ROUTER_THRESHOLD=0.45
ROUTER_COST_LAMBDA=0.02
```

## Expand labels

Append more JSONL lines:

```json
{"id":"q056","query":"...","required_agents":["market","finance"],"expected_tools":["get_market_price"],"risk_level":"low"}
```

Valid agents: `crop_health`, `finance`, `equipment`, `market`, `weather`, `soil`, `knowledge_retriever`.

## Tests

```bash
uv run pytest tests/test_routing_eval.py tests/test_v1.py -q
```

## Related workstreams

- RAG corpus / live weather-market APIs → data & tools track
- Image diagnosis → vision track
- UI polish → frontend track
