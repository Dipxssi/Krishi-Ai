# Lovable frontend ↔ backend integration

**Status:** Approved by user (2026-10-18)  
**Goal:** Make the Lovable UI the product frontend, wired to the FastAPI multi-agent backend (including MobileNet vision).

## Decisions

- Lovable-first: landing, auth (demo gate), chat dashboard are the default app.
- Keep Vite (client SPA). Do **not** require TanStack Start SSR for v1; use TanStack Router client-side if present, or thin React Router wrapping the same screens.
- Merge MobileNet backend + `api.ts` contracts; retire old `App.tsx` tab UI as default entry.
- Replace mock chat replies with `POST /query`; ensure farmer via `POST/GET /farmers`.
- Add missing UX in Lovable visual language: farm profile in Settings, leaf image attach, diagnosis summary in assistant messages.
- Auth stays local/demo (no user DB).

## Data flow

1. User opens `/chat` (after demo auth or direct).
2. Settings / first message ensures a `farmer_id` + farm context exists on the backend.
3. Send text (+ optional image base64, crop hint, `vision_model=mobilenetv3`) → `askAdvice`.
4. Map `QueryResponse` → chat bubble (recommendation, agents, warnings, image diagnosis).
5. Optional thumbs → `POST /feedback` with `request_id`.

## Out of scope

- Real authentication / accounts  
- Full knowledge-hub parity in chat  
- Perfect agent taxonomy mapping for every backend agent  

## Success criteria

- `frontend` builds and runs with Lovable UI as entry.
- Chat answers come from the live backend (not `getMockResponse`).
- Leaf photo upload reaches vision path.
- Farm profile can be saved from Settings.
