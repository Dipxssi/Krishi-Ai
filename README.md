# KrishiAi — AI Farmer Decision Support System

Multi-agent decision support for farmers: route a query to specialist agents, ground answers in tools + RAG, and return a structured recommendation.

## Key idea

Not a single chatbot. An **orchestrator** selects a **set of agents** (finance, market, weather, crop health, equipment, soil, knowledge), runs typed tools, validates evidence, then revises (max 2 loops).

## Research foundations

KrishiAi adapts ideas from these papers (we implement a student-scale version, not a full reproduction):

| Paper | What we take from it |
|-------|----------------------|
| [Agri-SAGE](https://arxiv.org/abs/2607.00454) | Closed-loop agricultural reasoning: farm context, retrieve → generate → verify, Plan–Critique–Revise (max 2 loops) |
| [Multi-Agent Routing as Set-Valued Prediction](https://arxiv.org/abs/2606.28925) | Multi-label agent routing, threshold + top-1 fallback, cost-aware scoring, set metrics (F1, Jaccard, exact match) |
| [AgroTools](https://arxiv.org/abs/2605.22366) | Typed tools, tool traces, argument validation / one retry, evidence-grounded final answers |
| [Kisan AI](https://arxiv.org/abs/2605.00133) | Profit-aware decisions: agronomic vs economic scores, deterministic profit calculator, labeled price forecasts |
| [AdapterMoE](https://arxiv.org/abs/2608.08808) | Two-stage crop image pipeline (planned): quality/crop route → disease expert, rejection, confidence calibration |

## Features (V1)

* FastAPI backend + React frontend
* Persistent FarmContext (SQLite)
* Multi-label router (keyword / embedding / hybrid) with cost-aware selection
* Typed tools: weather, market, profit, decision score, crop knowledge RAG
* Evidence citations + tool traces
* Plan–Critique–Revise orchestrator
* Groq for text generation (`GROQ_API_KEY`)

## Tech stack

| Layer | Stack |
|-------|--------|
| Backend | FastAPI, Python 3.12+, uv, SQLModel/SQLite |
| LLM | Groq (`llama-3.3-70b-versatile`) |
| Frontend | React + Vite (`frontend/`) |
| RAG | Local corpus + BM25 |

## Run

```bash
# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload
# → http://127.0.0.1:8000/docs

# Frontend
cd frontend
npm install
npm run dev
# → http://127.0.0.1:5173
```

Put secrets in the repo-root `.env` (never commit it). See `backend/.env.example`.

## Routing evaluation

Labeled multi-label routing eval lives under the backend:

| Path | Purpose |
|------|---------|
| [`backend/data/eval/queries.jsonl`](backend/data/eval/queries.jsonl) | 55 labeled farmer queries |
| [`backend/scripts/eval_routing.py`](backend/scripts/eval_routing.py) | Precision / recall / F1 / Jaccard runner |
| [`backend/scripts/sweep_threshold.py`](backend/scripts/sweep_threshold.py) | Threshold sweep (keyword only, no Gemini) |
| [`backend/docs/ORCHESTRATOR_EVAL.md`](backend/docs/ORCHESTRATOR_EVAL.md) | Orchestrator / routing eval guide |

### Recommended router settings

```env
ROUTER_MODE=keyword
ROUTER_THRESHOLD=0.45
ROUTER_COST_LAMBDA=0.02
```

Use **keyword** mode while iterating on routing so eval does not burn Gemini embed quota (`429 RESOURCE_EXHAUSTED`). Hybrid/embedding modes are optional later.

### How to run eval

```bash
cd backend

# Metrics + mismatches
uv run python scripts/eval_routing.py --mode keyword --threshold 0.45 --cost-lambda 0.02 --show-misses

# Threshold sweep (no Gemini calls)
uv run python scripts/sweep_threshold.py
```

### Latest baseline (keyword, threshold 0.45, λ 0.02, n=55)

| Metric | Score |
|--------|------:|
| Precision | 0.96 |
| Recall | 0.97 |
| Multi-label F1 | **0.95** |
| Jaccard | 0.93 |
| Exact-match accuracy | 0.82 |
| Avg agents selected | ~2.2 |
| Unnecessary-agent rate | ~0.05 |
| Missing-agent rate | ~0.04 |

Threshold guidance from the sweep:

* **0.30–0.45** — best F1 / recall (preferred)
* **0.55–0.60** — higher precision, more misses
* **0.65+** — too strict; recall collapses

Exact-match will not hit 100% on multi-label farming queries; remaining mismatches are mostly edge cases (e.g. pure price lookup vs finance).

## Team split

| Role | Owns | Focus |
|------|------|--------|
| Orchestrator | `orchestrator/`, eval harness | Routing quality, validator, revise loop, metrics |
| Data & tools | `tools/`, `data/knowledge/`, RAG | Live weather/market APIs, richer corpus |
| Vision | new vision module | Tomato image diagnosis (quality → crop → disease → reject) |
| Frontend | `frontend/` | UI, evidence display, later image upload |

## Docs

* [backend/README.md](backend/README.md) — API + setup
* [docs/DEPLOY.md](docs/DEPLOY.md) — Vercel + Railway + Neon hosting
* [backend/docs/ORCHESTRATOR_EVAL.md](backend/docs/ORCHESTRATOR_EVAL.md) — routing eval guide
* [frontend/README.md](frontend/README.md) — UI run instructions

## Out of scope / next

* Image diagnosis (V3)
* Larger labeled set (100–300) and tool-level eval
* Live weather/market APIs (until keys are wired)
* Voice / mobile

## Problem statement

Farmers often lack reliable advice on crop health, finance, markets, and equipment. KrishiAi combines those domains in one evidence-grounded assistant.
