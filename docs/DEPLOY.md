# Deploy KrishiAi (Vercel + Render + Neon)

## Topology

| Piece | Host | Notes |
|-------|------|--------|
| Frontend | Vercel | Root directory `frontend/` |
| Backend | Render | Root directory `backend/` (see `render.yaml`) |
| Database | Neon Postgres | Set `DATABASE_URL` on Render |

Do **not** use SQLite in production (Render disk is ephemeral).

## Free tier (512 MB) — supported path

Render Free cannot load Torch/MobileNet. The default deploy is **slim**:

- Build: `uv sync --no-dev` (no `torch` / `torchvision`)
- Env: `VISION_MODEL=heuristic`
- Leaf photos use the light heuristic screener; text advice, auth, Neon still work
- Free instances **sleep** when idle (first request after sleep can take ~30–60s)

Later, on a plan with **≥2 GB RAM**:

```bash
# Build command
pip install uv && uv sync --extra vision --no-dev
```

Set `VISION_MODEL=mobilenetv3` and `HF_TOKEN` if the Hugging Face repo needs it.

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
   | `CORS_ORIGINS` | yes | `https://your-app.vercel.app` |
   | `VISION_MODEL` | yes on Free | `heuristic` |
   | `GROQ_API_KEY` | yes for LLM/voice STT | Groq key |
   | `GROQ_MODEL` | optional | e.g. `llama-3.3-70b-versatile` |
   | `OPENAI_API_KEY` | optional | TTS only |
   | `WEATHER_API_KEY` | optional | else labeled mock weather |
   | `MARKET_API_KEY` / `DATA_GOV_API_KEY` | optional | else labeled mock market |
   | `HF_TOKEN` | only with vision extra | Hugging Face token |

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
4. Upload a leaf image → heuristic screening (or safe rejection), not MobileNet.
5. Expired/missing token → redirected to `/auth`.
6. Airplane mode → ask a question → sees “waiting”; leave airplane / join hotspot → answer fills in.

## Local vs production

- Local slim: `cd backend && uv sync --no-dev`
- Local with MobileNet: `uv sync --extra vision`
- Production Free: slim + `VISION_MODEL=heuristic`
- Production with HF model: `--extra vision` + `VISION_MODEL=mobilenetv3` + enough RAM
