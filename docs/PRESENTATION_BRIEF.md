# KrishiAi — presentation brief

Speaker cheat sheet. **Never put real API key values on slides.**

## Elevator pitch (15s)

KrishiAi is a **multi-agent farmer decision-support system**: an orchestrator routes each question to specialist agents, runs **typed tools + BM25 RAG**, validates evidence, and **Plan–Critique–Revise** (max 2 loops) into a structured recommendation grounded in farm context—not a single chatbot.

Research inspiration (student-scale): Agri-SAGE, multi-agent routing, AgroTools, Kisan AI, AdapterMoE (vision).

## Datasets

### Vision

| Dataset | Role | Cite |
|---------|------|------|
| **PlantVillage (Color)** | Primary training | 17 classes (maize, potato, tomato); ~21k target images |
| **PlantDoc** | Field-style benchmark + Exp C mix | Sealed test N=99; OOD N=125 |
| **ImageNet-1K** | Backbone pretrain only | Not our labels |

**Metrics:** Production MobileNetV3 on PlantVillage ~**98.6%** test acc; PlantDoc ~**20–24%** (domain shift). Exp C (PV+PD) ~**43%** PlantDoc. Vision is **experimental / pilot**.

### Non-vision

- RAG: `backend/data/knowledge/` (crops, schemes, loans, KVK, rules)
- Offline pack: `frontend/public/offline-pack/v1.json` (~46 entries)
- Routing eval: ~55 labeled queries; keyword multi-label F1 **~0.95**
- Mandi warehouse: Agmarknet snapshots in Neon/SQLite (`mandi_price_snapshots`)

## APIs & env vars (names only)

Secrets stay on the **backend**. Frontend only: `VITE_API_URL`.

| Var | Service | If missing |
|-----|---------|------------|
| `GROQ_API_KEY` | LLM + Whisper STT + Orpheus TTS | Template text |
| `WEATHER_API_KEY` | WeatherAPI.com | Labeled mock |
| `MARKET_API_KEY` / `DATA_GOV_API_KEY` | Agmarknet | Mock unless fresh DB snapshot |
| `UPAG_API_*` | UPAg yield | No live UPAg |
| `DATABASE_URL` | Neon Postgres | Local SQLite |
| `JWT_SECRET` | Auth | Required strong in prod |
| `VISION_INFERENCE_URL` + `HF_*` | HF Space / Hub | Heuristic vision |

**Hosting:** Vercel (UI), Render (API), Neon (DB), Hugging Face Space (vision).

## Mandi “weekly scrape → DB” (what to say)

> We pull official Agmarknet mandi prices on a weekly job into our database so common crop/location lookups are fast. Runtime order: memory cache → fresh DB snapshot (≤7 days) → live API (write-through) → labeled mock. Weather uses a short TTL cache only—forecasts change daily.

Scripts: `backend/scripts/scrape_market_prices.py --upsert-db --priority`. Docs: `docs/DEPLOY.md` § Mandi weekly job.

## Architecture

User (PWA) → FastAPI orchestrator → multi-label router → 7 specialists → tools/RAG (+ optional MobileNet) → evidence + recommendation. Offline: queue + field relay + offline pack.

**Agents:** crop_health, finance, equipment, market, weather, soil, knowledge_retriever.

## Demo script (~8–10 min)

1. Landing + EN/HI/KN  
2. Auth → farm onboarding  
3. Multi-intent chat (market + rain + budget) → agents, evidence, tool traces  
4. Optional leaf photo (pre-wake HF Space)  
5. Airplane mode → queued/offline → reconnect  
6. Optional: routing F1 0.95 table  

## Likely Q&A

- **Why multi-agent?** Farming needs several specialists + evidence, not one generic LLM.  
- **Mocks?** Explicit `is_mock` so demos never silently invent prices/weather.  
- **Vision weak in field?** PlantVillage ≠ PlantDoc; τ=0.60; confirm with KVK.  
- **Faster mandi?** Weekly DB + 6h TTL + live fallback.  
- **Security?** Keys only on server; JWT + CORS.  

## Do not say

- Do not claim weekly **weather** into DB.  
- Do not show real API keys.  
- Do not claim PlantDoc-level field accuracy for production vision.  
- Do not claim full paper reproductions—say student-scale adaptation.
