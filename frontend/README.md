# Krishi AI Frontend

Lovable-designed React UI wired to the FastAPI multi-agent backend (query, farmers, MobileNetV3 vision).

## Routes

- `/` — marketing landing
- `/auth` — sign-in / sign-up
- `/chat` — live assistant (calls `POST /query`)
- `/field-relay` — how to reach the API via a shop/KVK Wi‑Fi hotspot

## Offline / field relay

Production builds register a PWA service worker (app shell only). If the API is unreachable, chat saves the question in IndexedDB and shows a waiting state. When the phone can reach `GET /health` (own data or a nearby hotspot), queued items flush through `POST /query`. See `docs/DEPLOY.md` and `backend/scripts/field_relay_status.py`.

## Run

1. Backend: `cd backend && uv run uvicorn app.main:app --reload`
2. Frontend: `cd frontend && npm install && npm run dev`
3. Open http://127.0.0.1:5173

Optional: set `VITE_API_URL=http://127.0.0.1:8000` in `frontend/.env` (dev uses the Vite proxy by default).

## Farm profile

Open **Settings** in chat to set farmer ID, location, crop, and acres. The profile is saved via `POST/PUT /farmers` and stored in `localStorage` for the next session.

## Leaf photos

Use the paperclip control in the composer to attach a leaf image. Chat sends it as `image_base64` with `vision_model=mobilenetv3`.

## Voice chat

Use the microphone button to record a question. The transcript appears in the composer for review and is sent through the usual chat endpoint. Assistant messages have a read-aloud control. Configure `GROQ_API_KEY` and `OPENAI_API_KEY` in the backend environment; no provider keys belong in the frontend.
