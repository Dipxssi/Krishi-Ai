# KrishiAi Backend (V1)

Text-only multi-agent farmer decision-support API.

## Features

- Persistent `FarmContext` (SQLite)
- Multi-label router (keyword / embedding / hybrid) with threshold, top-1 fallback, cost penalty
- Specialist agents: finance, market, weather, crop_health, equipment, soil, knowledge_retriever
- Typed tools: weather, market price, profit calculator, decision score, crop knowledge RAG
- Tool traces + evidence citations
- Plan–Critique–Revise orchestrator (max 2 revisions)
- Groq for text generation when `GROQ_API_KEY` is set

## Setup

```bash
cd backend
uv sync
```

Create a `.env` at the repo root or in `backend/`:

```env
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.3-70b-versatile
OPENAI_API_KEY=your_openai_key_here
OPENAI_TTS_MODEL=gpt-4o-mini-tts
# optional
ROUTER_MODE=hybrid
ROUTER_THRESHOLD=0.60
ROUTER_COST_LAMBDA=0.05
AGRONOMIC_WEIGHT=0.6
ECONOMIC_WEIGHT=0.4
```

Never commit API keys.

Voice recording is transcribed by Groq's `whisper-large-v3-turbo` through `POST /voice/transcribe`. Assistant messages can be played with OpenAI `gpt-4o-mini-tts` through `POST /voice/speech`; set `OPENAI_API_KEY` to enable playback. The microphone inserts a transcript into the chat composer for review. Sending it uses the normal `POST /query` endpoint and existing multi-agent router.

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
- With `WEATHER_API_KEY` / `MARKET_API_KEY` (or `DATA_GOV_API_KEY`), tools call WeatherAPI.com and Agmarknet, cached in-process (defaults: weather 1h, market 6h). On HTTP failure or no mandi match, they fall back to labeled mock.
- Without `GROQ_API_KEY`, recommendations use deterministic templates over tool/RAG evidence.
- Image diagnosis is out of scope for V1.
