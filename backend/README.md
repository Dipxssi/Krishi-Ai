# KrishiAi Backend (V1)

Text-only multi-agent farmer decision-support API.

## Features

- Persistent `FarmContext` (SQLite)
- Multi-label router (keyword / embedding / hybrid) with threshold, top-1 fallback, cost penalty
- Specialist agents: finance, market, weather, crop_health, equipment, soil, knowledge_retriever
- Typed tools: weather, market price, profit calculator, decision score, crop knowledge RAG
- Tool traces + evidence citations
- Plan–Critique–Revise orchestrator (max 2 revisions)
- Groq for generation when `GROQ_API_KEY` is set; Gemini fallback + embeddings when `GEMINI_API_KEY` is set

## Setup

```bash
cd backend
uv sync
```

Create a `.env` at the repo root or in `backend/`:

```env
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.3-70b-versatile
GEMINI_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-3.6-flash
# optional
ROUTER_MODE=hybrid
ROUTER_THRESHOLD=0.60
ROUTER_COST_LAMBDA=0.05
AGRONOMIC_WEIGHT=0.6
ECONOMIC_WEIGHT=0.4
```

Never commit API keys.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 — keep the backend running on port 8000.

## Run

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs

## API

### Create farm context

`POST /farmers`

```json
{
  "farmer_id": "farmer-001",
  "location": "Nashik",
  "farm_area_acres": 2.0,
  "crop": "tomato",
  "growth_stage": "fruiting",
  "soil_type": "loam",
  "soil_npk": {"n": 40, "p": 30, "k": 40},
  "irrigation_available": true,
  "budget": 20000,
  "preferred_language": "English",
  "season": "kharif"
}
```

### Ask for advice

`POST /query`

```json
{
  "farmer_id": "farmer-001",
  "query": "Tomato market price is falling, limited budget, rain expected next week. Treat, continue, or sell early?"
}
```

Response includes `final_recommendation`, `agents_used`, `evidence`, `tool_traces`, `decision_score`, `warnings`, `missing_context`, and `revision_count`.

Agents do **not** answer from the raw query alone — they require a stored `FarmContext`.

## Tests

```bash
cd backend
uv run pytest -q
```

## Notes

- Without live weather/market API keys, tools return **labeled mock** data (`is_mock: true`).
- Without `GROQ_API_KEY` and `GEMINI_API_KEY`, recommendations use deterministic templates over tool/RAG evidence.
- Generation uses Groq first and Gemini if Groq is missing or fails. Dense embeddings still require Gemini.
- Image diagnosis is out of scope for V1.
