# KrishiAi backend — what exists, why it was built, what comes next

This document explains every important backend file, the work done so far and the reason for each choice, and the planned next steps.

V1 is **not a single chatbot**. A farmer stores farm facts once, then asks a text question. The system picks a **set of specialist agents**, runs **typed tools + RAG**, checks evidence and safety, then revises the answer at most twice.

---

## 1. What a request does (end to end)

```text
POST /farmers          → save FarmContext in SQLite
POST /query            → load that context (404 if missing)
        ↓
Router selects agents  → keyword / embedding / hybrid + cost penalty
        ↓
Each agent runs tools  → weather, market, profit, RAG, …
        ↓
Validator              → missing fields, mock data, unsafe spray language
        ↓
Plan–Critique–Revise   → Groq (then Gemini) rewrite, max 2 loops
        ↓
JSON response          → recommendation, scores, evidence, traces
```

Agents never answer from the raw query alone. They need a stored `FarmContext` (location, crop, acres, budget, soil, …). That is intentional: advice without farm facts is easy to invent and hard to trust.

---

## 2. Folder map

```text
backend/
  main.py                 leftover uv hello-world entry (not the API)
  pyproject.toml          Python 3.12+, uv dependencies
  .env.example            keys and router knobs (no secrets)
  app/main.py             FastAPI app, CORS, lifespan DB init
  app/core/config.py      settings from repo-root or backend .env
  app/schemas/models.py   API and domain Pydantic models
  app/db/session.py       SQLite FarmContext + tool traces
  app/api/farmers.py      CRUD for farm profiles
  app/api/query.py        POST /query → orchestrator
  app/orchestrator/       routing, metrics, Plan–Critique–Revise
  app/agents/             one specialist per domain
  app/tools/              typed tools + registry (validate, one retry)
  app/services/           LLM, RAG, validator, legacy aggregator
  data/knowledge/         crop JSON + safety rules markdown
  data/eval/              labeled routing queries
  scripts/                routing eval + threshold sweep
  tests/                  unit / API / routing tests
  docs/ORCHESTRATOR_EVAL.md
```

Empty `__init__.py` files only mark packages. `app/utils/` is an empty package reserved for later helpers.

---

## 3. File-by-file explanation

### 3.1 App shell and config

| File | What it does | Why it exists |
|------|----------------|---------------|
| `app/main.py` | Creates FastAPI, runs `init_db()` on startup, CORS for Vite (`5173`) and CRA (`3000`), mounts `/query` and `/farmers`, root health JSON. | Single HTTP surface for the React UI and Swagger at `/docs`. |
| `main.py` (backend root) | Prints “Hello from backend!”. | Default uv project stub. **Do not run this for the API.** Use `uvicorn app.main:app`. |
| `app/core/config.py` | `Settings` via pydantic-settings. Reads `.env` from **repo root first**, then `backend/`. SQLite path, knowledge dir, Groq/Gemini, router, decision weights, optional weather/market keys. Cached with `@lru_cache`. | One place for env; tests can `cache_clear()` and isolate the DB. |
| `pyproject.toml` | FastAPI, SQLModel, Groq, google-genai, rank-bm25, pytest, uvicorn. Pytest `pythonpath = ["."]`. | Reproducible installs with `uv sync`. |
| `.env.example` | Placeholder keys and recommended `ROUTER_MODE=keyword`, threshold `0.45`, λ `0.02`. | Documents knobs without committing secrets. |

### 3.2 Contracts (schemas)

`app/schemas/models.py` is the typed contract between API, DB, agents, and the frontend.

- **FarmContext** — persistent farmer/farm state. Required on every advice call.
- **QueryRequest** — `query` + `farmer_id`. `image_url` is present but **ignored in V1** (vision is later).
- **EvidenceItem / ToolTrace** — what the UI shows as “why we said this.”
- **DecisionScore** — agronomic vs economic blend (Kisan AI idea, student-scale).
- **AgentResult / QueryResponse** — per-agent drafts plus the final structured payload.

Why Pydantic models everywhere: invalid tool args fail fast, traces stay serializable, the OpenAPI spec stays honest.

### 3.3 Persistence

`app/db/session.py`

- `FarmContextRow` — one row per `farmer_id`. NPK stored as JSON text (SQLite has no native dict).
- `ToolTraceRow` — every tool call (success, retry, invalid args, error) for audit.
- In-memory SQLite uses `StaticPool` so pytest can share one connection.
- File SQLite creates `backend/data/` if needed.
- `save_tool_trace` is best-effort: if DB write fails, the in-memory trace still returns to the client.

Why SQLite for V1: no extra service, easy local demo, enough for one-machine student/team work. Postgres can replace the URL later without changing agent code.

### 3.4 HTTP API

**`app/api/farmers.py`**

- `POST /farmers` — create; `409` if id exists.
- `GET /farmers/{id}` — read; `404` if missing.
- `PUT /farmers/{id}` — partial update.

**`app/api/query.py`**

- `POST /query` — load context, then `handle_query`. `404` if farmer was never created.

Why a separate farmers API: crop, budget, and soil change slowly; the question changes every time. Forcing context on each query would make the UI worse and the eval harder.

### 3.5 Orchestrator (the “brain”)

**`app/orchestrator/catalog.py`**

Fixed list of seven agents, short English **profiles** (for embeddings), **cost tiers** (crop_health = 3, most others 1–2), and **keywords**.

Why a catalog: routing is set-valued prediction (paper: *Multi-Agent Routing as Set-Valued Prediction*). Costs stop the router from always firing the expensive crop-health path. Keywords were tuned against 55 labeled queries so multi-word phrases (e.g. `sell early`) fire and bare words like `plant` do not over-trigger.

**`app/orchestrator/router.py`**

1. **Keyword scores** — phrase/token hits, then **co-occurrence boosts** (planting → weather+market+finance; blight → crop_health; sell early → market+finance, …).
2. **Embedding scores** — Gemini dense cosine if allowed; otherwise local bag-of-words vs profiles.
3. **Hybrid** — 55% keyword + 45% embedding.
4. **Cost penalty** — `score - λ × cost`.
5. **Select** — all agents ≥ threshold; if none, **top-1 fallback** so the farmer still gets someone.

`score_query` is shared by production and eval so metrics match live routing.

**Why keyword is the recommended default:** Gemini embed quota (`429`) burned eval runs. Keyword mode is deterministic, free, and currently ~0.95 F1 on the 55-query set at threshold 0.45 / λ 0.02.

**`app/orchestrator/orchestrator.py`**

`handle_query`:

1. Register tools once; reset traces for this farmer.
2. Route; if **two or more** specialists are selected, also add `knowledge_retriever` for citations.
3. Run each agent.
4. Concatenate drafts.
5. Validate → critique.
6. Revise with LLM (or a template) up to `max_revisions` (2), stop early if critique is clean.
7. Compute decision score (pull rainfall/price/profit from evidence, or call tools if missing).
8. Cap confidence at 0.4 and prepend a “please update FarmContext” note if fields are missing.

This is the student-scale **Plan–Critique–Revise** loop from Agri-SAGE (max 2), not an unbounded agent swarm.

**`app/orchestrator/metrics.py`**

Set metrics: precision, recall, F1, Jaccard, exact match, unnecessary/missing agent rates. Used by `scripts/eval_routing.py` and tests.

### 3.6 Agents

Shared helpers in `app/agents/base.py`:

- Turn successful tool traces into `EvidenceItem`s.
- `run_knowledge` → `search_crop_knowledge`.
- `enrich_with_llm` — rewrite the draft **only** from evidence; if no API keys, keep the template.

| Agent file | Role | Tools / behavior |
|------------|------|------------------|
| `finance_agent.py` | Costs, profit, break-even, budget pressure | Market price + `calculate_profit`; cheaper pesticide/fertilizer path if budget is tight |
| `market_agent.py` | Price + 30-day **labeled forecast** | Refuses without crop+location |
| `weather_agent.py` | 7-day rainfall/temp/condition | Refuses without location |
| `crop_agent.py` | Text crop health only | RAG; explicitly says V1 has no image diagnosis |
| `equipment_agent.py` | Rent vs buy for small acreage | RAG |
| `soil_agent.py` | Soil type / NPK caution | RAG; low confidence if soil unknown |
| `knowledge_agent.py` | Citations-first retriever | RAG |

Why seven small functions instead of one mega-prompt: each domain can fail, cite, and score independently; the router can skip unused ones (cost and latency).

### 3.7 Tools (AgroTools-style)

**`app/tools/registry.py`**

Register `(function, Pydantic args model)`. On execute: validate → run → on failure **one repair retry**. Always append a `ToolTrace` and persist it.

**`app/tools/agriculture.py`**

| Tool | Behavior |
|------|----------|
| `get_weather` | Live API placeholder; today **labeled mock** (`is_mock: true`) so numbers are never unlabeled inventions |
| `get_market_price` | Crop base prices + date drift; forecast labeled with horizon and uncertainty |
| `calculate_profit` | Pure arithmetic: revenue, cost, profit, break-even ₹/kg |
| `estimate_decision_score` | `final = 0.6 * agronomic + 0.4 * economic` (weights configurable); water/disease/input cost reduce the parts |
| `search_crop_knowledge` | Delegates to RAG |

Why mocks with `is_mock`: demos work without paid weather/mandi keys, and the validator warns the UI that values are not live.

### 3.8 Services

**`app/services/llm.py`**

- Generation: **Groq first** (`llama-3.3-70b-versatile`), **Gemini fallback**.
- Embeddings: **Gemini only** (Groq has no embed API).
- Agents must not import Groq/Gemini SDKs directly.

If both keys are missing, templates still produce a full JSON response (needed for tests and offline demos).

**`app/services/rag.py`**

Loads `data/knowledge/**/*.json` and `*.md` (markdown split on `##`). BM25 always; optional Gemini dense hybrid (60/40). Crop filter when `crop` is set. Returns top_k snippets with ids for citations.

**`app/services/validator.py`**

- Missing farm fields depending on which agents ran.
- Numbers in the draft without numeric evidence → warning.
- Banned / underspecified pesticide language (`endosulfan`, invented `spray 5 ml`, …).
- Failed tools and mock sources → warnings.
- Builds the **critique string** the orchestrator feeds into revise.

**`app/services/aggregator.py`**

Old string joiner. Orchestrator no longer depends on it; kept so older experiments do not break.

### 3.9 Knowledge and eval data

- `data/knowledge/crops.json` — tomato, potato, maize, irrigation, budget, sprayer passages (ids like `tomato-leaf-spot`).
- `data/knowledge/rules.md` — nitrogen caution, never invent pesticide doses, numeric claims must come from tools.
- `data/eval/queries.jsonl` — 55 labeled farmer queries with `required_agents` (and expected tools / risk on some rows).

### 3.10 Scripts and tests

- `scripts/eval_routing.py` — precision/recall/F1/Jaccard; keyword mode never calls Gemini.
- `scripts/sweep_threshold.py` — F1 vs threshold 0.30–0.65.
- `tests/test_v1.py` — profit math, decision score, router fallback/cost, tool registry retry, farmers+query HTTP.
- `tests/test_llm.py` — Groq then Gemini then None.
- `tests/test_routing_eval.py` — set metrics + smoke that the demo query selects market, finance, weather, crop_health.

### 3.11 Docs next to this file

- `docs/architecture.md` — short system diagram.
- `backend/README.md` — run/API.
- `backend/docs/ORCHESTRATOR_EVAL.md` — how to tune routing.
- Root `README.md` — papers, team split, latest eval numbers.

---

## 4. Steps done until now — and why

These are the **design and implementation stages** that produced the current backend (V1). Order is logical; some work overlapped.

### Step 1 — Problem and papers, not a chatbot

Farmers need treat / continue / sell-early style advice that mixes weather, mandi, budget, and crop health. A single LLM call hallucinates prices and spray doses.

**Why:** Ground the project in five papers (Agri-SAGE, set-valued routing, AgroTools, Kisan AI, AdapterMoE) but implement a **student-scale** subset, not a full paper reproduction.

### Step 2 — FastAPI + FarmContext + SQLite

Persistent farm profile and two HTTP resources.

**Why:** Advice without location/crop/acres is unsafe. SQLite is enough for V1 and pytest.

### Step 3 — Specialist agents instead of one prompt

Finance, market, weather, crop_health, equipment, soil, knowledge_retriever.

**Why:** Multi-factor queries need a **set** of experts. Isolation makes routing measurable.

### Step 4 — Typed tools + traces + one retry

Pydantic args, traces in memory and DB, labeled mocks.

**Why:** AgroTools pattern — the final answer must be able to **cite** weather/price/profit. Mocks keep demos honest (`is_mock`).

### Step 5 — Local RAG corpus

JSON + markdown rules, BM25 (+ optional dense).

**Why:** Crop guidance should come from a small owned corpus, not from the model’s memory. Safety rules live in `rules.md` so the retriever can surface “do not invent doses.”

### Step 6 — Multi-label router + cost + eval harness

Keyword / embedding / hybrid, threshold, top-1 fallback, λ cost, 55 JSONL labels, F1/Jaccard scripts.

**Why:** Routing quality is the orchestrator’s main KPI. Eval showed default threshold 0.60 was too strict; **0.45 + keyword + λ 0.02** became the recommended setting. Co-occurrence boosts fixed systematic misses (planting, blight, sell-early).

### Step 7 — Validator + Plan–Critique–Revise (max 2)

Missing context, mock warnings, pesticide patterns, LLM revise, confidence cap.

**Why:** Agri-SAGE closed loop without unbounded cost. Clarifying preface tells the farmer which FarmContext fields to fill.

### Step 8 — Decision score (agronomic vs economic)

Weighted blend with water/disease/input penalties.

**Why:** Kisan AI idea — “treat” can be agronomically right and economically wrong. The UI can show a score, not only prose.

### Step 9 — LLM wrapper: Groq generate, Gemini fallback + embeddings

**Why:** Groq is cheap/fast for rewrite. Gemini remains for embeddings and backup generation. Offline path still works with templates.

### Step 10 — Tests, CORS, frontend contract

Pytest isolation (`DATABASE_URL=:memory:`), CORS for Vite, `QueryResponse` fields the UI already consumes.

**Why:** Routing and profit math must not regress when keywords or weights change.

### Step 11 — Docs and env example

README, architecture, eval guide, `.env.example`.

**Why:** Team split (orchestrator / data-tools / vision / frontend) needs a shared map. Keys must never be committed.

---

## 5. What is deliberately out of V1

- Image crop diagnosis (AdapterMoE two-stage pipeline).
- Live IMD / mandi APIs (hooks exist; keys not wired).
- Voice / mobile.
- Large routing set (100–300) and tool-level eval.
- Crop simulators (APSIM / DSSAT).
- `image_url` on `/query` is ignored.

---

## 6. Future — now and later

### Now (backend, high value)

1. **Keep routing in keyword mode** while iterating; run `eval_routing.py --show-misses` after keyword edits. Expand JSONL toward 100+ queries.
2. **Wire live weather and market** behind `WEATHER_API_KEY` / `MARKET_API_KEY` without removing `is_mock` for the fallback path.
3. **Grow the RAG corpus** (more crops, regional languages, official fertilizer schedules) and add a small retrieval eval (hit@k).
4. **Replace hardcoded yield/cost constants** in `finance_agent` / orchestrator with crop-specific tables from knowledge data.
5. **Align default `Settings.router_threshold` (0.60)** with the documented 0.45, or always set env in `.env` so production matches eval.

### Next (product)

6. **Vision module (V3)** — quality/crop route → disease expert, reject low-quality images, calibrate confidence; then honor `image_url` / upload.
7. **Tool-level eval** — expected tools per query, mock vs live parity tests.
8. **Postgres + auth** if more than a local demo.
9. **Voice / vernacular** using `preferred_language` already on FarmContext.
10. **Frontend** — show evidence, mock warnings, missing_context, revision_count; later image upload.

### Research-shaped (only if the team wants paper-closer work)

11. Learned set-valued router (not only keywords).
12. Stronger critique (LLM-as-judge with a frozen rubric).
13. AdapterMoE-style rejection and temperature scaling for vision.

---

## 7. How to run (reminder)

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
# http://127.0.0.1:8000/docs

uv run pytest -q
uv run python scripts/eval_routing.py --mode keyword --threshold 0.45 --cost-lambda 0.02 --show-misses
```

Create a farmer with `POST /farmers`, then `POST /query` with the same `farmer_id`.

---

## 8. One-sentence summary

The backend is a **FarmContext-grounded, multi-agent, tool-and-RAG, validated, twice-revised** FastAPI service: routing is measured as a **set**, numbers come from **tools** (mocked until APIs are live), and the LLM is only allowed to **rewrite from evidence**.
