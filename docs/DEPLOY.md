# Deploy KrishiAi (Vercel + Render + Neon)

## Topology

| Piece | Host | Notes |
|-------|------|--------|
| Frontend | Vercel | Root directory `frontend/` |
| Backend | Render | Root directory `backend/` (see `render.yaml`) |
| Database | Neon Postgres | Set `DATABASE_URL` on Render |

Do **not** use SQLite in production (Render disk is ephemeral).

## Free tier (512 MB) — supported path

Render Free cannot load Torch in-process. Keep the API **slim** and run MobileNet on a **free Hugging Face Space**:

- Build: `uv sync --no-dev` (no `torch` / `torchvision` on Render)
- Env: `VISION_MODEL=mobilenetv3` + `VISION_INFERENCE_URL=https://<you>-krishiai-vision.hf.space`
- Space code: [`deploy/hf-space/`](../deploy/hf-space/) (Docker Space, CPU basic)
- Leaf photos → Render proxies to Space `POST /predict` → real MobileNetV3
- If the Space is asleep/unreachable, API falls back to the color-ratio heuristic
- **Demo tip:** open the Space URL once before presenting (cold start 30–120s)
- Render Free itself also sleeps when idle (~30–60s first request)

### Deploy the free vision Space (one-time)

1. Create a Docker Space named e.g. `krishiai-vision` on Hugging Face (CPU basic).
2. Push contents of `deploy/hf-space/` into that Space.
3. On Render → Environment: set `VISION_INFERENCE_URL` to the Space URL (no trailing slash) and `VISION_MODEL=mobilenetv3`.
4. Save → wait for redeploy → smoke-test a leaf on Vercel.

Optional later (paid ≥2 GB RAM, Torch on Render):

```bash
pip install uv && uv sync --extra vision --no-dev
```

Clear `VISION_INFERENCE_URL` and keep `VISION_MODEL=mobilenetv3`.

## 1. Neon

1. Use your existing Neon connection string (from local `.env` is fine).
2. Prefer the **pooled** `DATABASE_URL`; `sslmode=require` is fine.
3. Paste into Render as `DATABASE_URL`.

## 2. Render (API)

### Option A — Blueprint

1. [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**.
2. Connect the GitHub repo; Render reads `render.yaml`.
3. Fill in the `sync: false` env vars when prompted.

### Option B — Manual Web Service

1. **New** → **Web Service** → select this repo.
2. **Root Directory**: `backend`
3. **Runtime**: Python 3.12
4. **Build command** (Free / slim):

   ```bash
   pip install uv && uv sync --no-dev
   ```

5. **Start command**:

   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

6. Environment variables:

   | Variable | Required | Example / notes |
   |----------|----------|-----------------|
   | `APP_ENV` | yes | `production` |
   | `DATABASE_URL` | yes | Neon pooled URL |
   | `JWT_SECRET` | yes | ≥32 random chars (or Render Generate) |
   | `CORS_ORIGINS` | yes | `https://krishi-ai-ruddy.vercel.app` (comma-separate more origins; code also allows `*.vercel.app`) |
   | `VISION_MODEL` | yes | `mobilenetv3` with Space URL, else `heuristic` |
   | `VISION_INFERENCE_URL` | for free MobileNet | `https://<you>-krishiai-vision.hf.space` |
   | `GROQ_API_KEY` | yes for LLM/voice STT | Primary Groq key |
   | `GROQ_API_KEYS` | optional | Comma-separated extra keys; failover on 429/auth |
   | `GROQ_MAX_TOKENS` | optional | Default `2200` (Hindi advice; avoid mid-cut) |
   | `GROQ_MODEL` | optional | e.g. `llama-3.3-70b-versatile` |
   | `OPENAI_API_KEY` | optional | TTS only |
   | `WEATHER_API_KEY` | optional | else labeled mock weather |
   | `MARKET_API_KEY` / `DATA_GOV_API_KEY` | optional | else labeled mock market (DB snapshot still used if fresh) |
   | `MARKET_SNAPSHOT_MAX_AGE_DAYS` | optional | default `7` — serve Agmarknet rows from Neon if scraped within N days |
   | `HF_TOKEN` | only with in-process vision | Hugging Face token |

7. Generate a secret locally if needed:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

8. Deploy → open `https://<service>.onrender.com` → confirm `GET /` returns JSON.

## 3. Vercel (UI)

1. New project → import the same GitHub repo.
2. **Root Directory**: `frontend`
3. Framework preset: Vite
4. Env: `VITE_API_URL=https://<service>.onrender.com` (no trailing slash) — **required for cross-device chat history**.
   - Verify the **same** host serves this repo’s FastAPI (not another Krishi app):
     - `GET /health` → JSON with `"app":"farmer-decision-support"` and `"features":{"conversations":true}`
     - `GET /openapi.json` paths include `/conversations`, `/query`, `/auth/login`
     - `GET /` → JSON (not an HTML SPA)
   - If `/conversations` is **404**, chat history cannot sync — redeploy `backend/` from this repo (Render rootDir `backend`, start `uv run uvicorn app.main:app`).
5. Deploy. Put the Vercel URL into Render `CORS_ORIGINS`, then redeploy the API if needed.

## 4. Offline / field relay

Farmers can ask with no mobile data. Questions wait on the phone (IndexedDB) and send when the phone reaches the API — including through a shop/KVK Wi‑Fi hotspot that shares internet.

1. Deploy frontend (HTTPS) so the PWA can install after one online visit.
2. On the relay device (with internet): turn on Mobile Hotspot, then run:

   ```bash
   cd backend
   uv run python scripts/field_relay_status.py --api-url https://<service>.onrender.com --app-url https://<app>.vercel.app --ssid KrishiRelay --password <hotspot-password>
   ```

3. Farmer joins that Wi‑Fi, opens the app URL / installed PWA, stays on Chat. Queued questions call `POST /query` through the relay’s internet.
4. In-app guide: `/field-relay`. Health probe: `GET /health`.

Bluetooth mesh cannot reach the API; a normal hotspot can because the phone still uses HTTPS to your Render URL.

## 5. Smoke checklist

1. Open Vercel URL → Sign up.
2. Complete onboarding.
3. Ask a text question → recommendation appears.
4. Wake HF Space → upload a leaf image → MobileNetV3 prediction (or safe rejection). Without `VISION_INFERENCE_URL`, falls back to heuristic.
5. Expired/missing token → redirected to `/auth`.
6. Airplane mode → ask a question → sees “waiting”; leave airplane / join hotspot → answer fills in.

## Mandi weekly job (Agmarknet → Neon)

Lookup order for market prices: **in-memory TTL (6h)** → **fresh DB snapshot (≤7 days)** → **live Agmarknet API** (write-through to DB) → labeled mock.

### Local / one-shot

```bash
cd backend
uv run python scripts/scrape_market_prices.py --upsert-db --priority --no-json
```

Needs `MARKET_API_KEY` (or `DATA_GOV_API_KEY`) and `DATABASE_URL` (Neon in prod, SQLite locally).

### Render Cron

`render.yaml` defines `krishiai-mandi-weekly` (Mondays 03:00 UTC). Cron services usually need a **paid** Render plan. If Blueprint skips the cron on Free:

1. Create a Cron Job manually on a paid plan, same start command as above, same `DATABASE_URL` + market API key; or
2. Run the local command weekly; or
3. Add a GitHub Action that schedules the same script with secrets.

Weather stays on short TTL only (not weekly DB) — forecasts go stale within hours.

## Local vs production

- Local slim: `cd backend && uv sync --no-dev`
- Local with MobileNet: `uv sync --extra vision` **or** `VISION_INFERENCE_URL` pointing at a Space
- Production Free: slim + `VISION_MODEL=mobilenetv3` + `VISION_INFERENCE_URL` (HF Space)
- Production single-box: `--extra vision` + `VISION_MODEL=mobilenetv3` + ≥2GB RAM (no Space URL)
