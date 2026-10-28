# Deploy KrishiAi (Vercel + Render + Neon)

## Topology

| Piece | Host | Notes |
|-------|------|--------|
| Frontend | Vercel | Root directory `frontend/` |
| Backend | Render | Root directory `backend/` (see `render.yaml`) |
| Database | Neon Postgres | Set `DATABASE_URL` on Render |

Do **not** use SQLite in production (Render disk is ephemeral).

## 1. Neon

1. Use your existing Neon connection string (from local `.env` is fine).
2. Prefer the **pooled** `DATABASE_URL`; `sslmode=require` is fine.
3. You will paste this into Render as `DATABASE_URL`.

## 2. Render (API)

### Option A — Blueprint

1. [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**.
2. Connect the GitHub repo; Render reads `render.yaml`.
3. Fill in the `sync: false` env vars when prompted (`DATABASE_URL`, `CORS_ORIGINS`, `GROQ_API_KEY`, etc.).

### Option B — Manual Web Service

1. **New** → **Web Service** → select this repo.
2. **Root Directory**: `backend`
3. **Runtime**: Python 3.12
4. **Build command**:

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
   | `DATABASE_URL` | yes | Neon connection string (pooled) |
   | `JWT_SECRET` | yes | long random string (≥32 chars); can use Render “Generate” |
   | `CORS_ORIGINS` | yes | `https://your-app.vercel.app` (comma-separated) |
   | `GROQ_API_KEY` | yes for LLM/voice STT | Groq key |
   | `GROQ_MODEL` | optional | e.g. `llama-3.3-70b-versatile` |
   | `VISION_MODEL` | optional | `mobilenetv3` (default) or `heuristic` |
   | `HF_TOKEN` | if model repo is private | Hugging Face token |
   | `HF_MODEL_REPO` | optional | `Ishan2702/krishiai-mobilenetv3` |
   | `OPENAI_API_KEY` | optional | TTS only |
   | `WEATHER_API_KEY` | optional | else labeled mock weather |
   | `MARKET_API_KEY` / `DATA_GOV_API_KEY` | optional | else labeled mock market |

7. Generate a secret locally if needed:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

8. Deploy, open the public Render URL (`*.onrender.com`), confirm `GET /` returns JSON.
9. Prefer a plan with **≥2 GB RAM** for MobileNetV3 + Torch (Starter or higher). Free tier will likely OOM or sleep; if memory is tight, set `VISION_MODEL=heuristic` and redeploy.

## 3. Vercel (UI)

1. New project → import the same GitHub repo.
2. **Root Directory**: `frontend`
3. Framework preset: Vite
4. Build: `npm run build` (default)
5. Output: `dist`
6. Environment variable:

   | Variable | Value |
   |----------|--------|
   | `VITE_API_URL` | `https://<your-service>.onrender.com` (no trailing slash) |

7. Deploy. Copy the Vercel URL into Render `CORS_ORIGINS`, then **Manual Deploy** the API if CORS was set after the first deploy.

## 4. Smoke checklist

1. Open Vercel URL → Sign up.
2. Complete onboarding (farm profile).
3. Ask a text question in chat → recommendation + agents/evidence appear.
4. Upload a leaf image → diagnosis section appears (or safe rejection).
5. Log out / use an expired token → redirected to `/auth`.

## Local vs production

- Local: leave `VITE_API_URL` unset (Vite proxy) and use SQLite if `DATABASE_URL` is empty.
- Production: `APP_ENV=production` refuses weak `JWT_SECRET` and SQLite.
