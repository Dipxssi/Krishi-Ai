# Deploy KrishiAi (Vercel + Railway + Neon)

## Topology

| Piece | Host | Notes |
|-------|------|--------|
| Frontend | Vercel | Root directory `frontend/` |
| Backend | Railway | Root directory `backend/` |
| Database | Neon Postgres | Set `DATABASE_URL` on Railway |

Do **not** use SQLite in production (Railway disk is ephemeral).

## 1. Neon

1. Create a Neon project and copy the connection string.
2. Prefer the pooled URL if Neon shows one; `sslmode=require` is fine.
3. You will paste this into Railway as `DATABASE_URL`.

## 2. Railway (API)

1. New project → Deploy from GitHub → select this repo.
2. Set **Root Directory** to `backend`.
3. Start command (if not picked up from `railway.toml` / `Procfile`):

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

4. Environment variables:

   | Variable | Required | Example / notes |
   |----------|----------|-----------------|
   | `APP_ENV` | yes | `production` |
   | `DATABASE_URL` | yes | Neon connection string |
   | `JWT_SECRET` | yes | long random string (≥32 chars) |
   | `CORS_ORIGINS` | yes | `https://your-app.vercel.app` (comma-separated; add preview URLs if needed) |
   | `GROQ_API_KEY` | yes for LLM/voice STT | Groq key |
   | `GROQ_MODEL` | optional | e.g. `llama-3.3-70b-versatile` |
   | `VISION_MODEL` | optional | `mobilenetv3` (default) or `heuristic` |
   | `HF_TOKEN` | if model repo is private | Hugging Face token |
   | `HF_MODEL_REPO` | optional | `Ishan2702/krishiai-mobilenetv3` |
   | `OPENAI_API_KEY` | optional | TTS only |
   | `WEATHER_API_KEY` | optional | else labeled mock weather |
   | `MARKET_API_KEY` / `DATA_GOV_API_KEY` | optional | else labeled mock market |

5. Generate a secret locally:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

6. Deploy, open the public Railway URL, confirm `GET /` returns JSON.
7. Prefer a Railway plan with **≥2 GB RAM** for MobileNetV3 + Torch. If the service OOMs, set `VISION_MODEL=heuristic` and redeploy.

## 3. Vercel (UI)

1. New project → import the same GitHub repo.
2. **Root Directory**: `frontend`
3. Framework preset: Vite
4. Build: `npm run build` (default)
5. Output: `dist`
6. Environment variable:

   | Variable | Value |
   |----------|--------|
   | `VITE_API_URL` | `https://<your-railway-service>.up.railway.app` (no trailing slash) |

7. Deploy. Copy the Vercel URL into Railway `CORS_ORIGINS`, then redeploy the API if you added CORS after the first API deploy.

## 4. Smoke checklist

1. Open Vercel URL → Sign up.
2. Complete onboarding (farm profile).
3. Ask a text question in chat → recommendation + agents/evidence appear.
4. Upload a leaf image → diagnosis section appears (or safe rejection).
5. Log out / use an expired token → redirected to `/auth`.

## Local vs production

- Local: leave `VITE_API_URL` unset (Vite proxy) and use SQLite if `DATABASE_URL` is empty.
- Production: `APP_ENV=production` refuses weak `JWT_SECRET` and SQLite.
