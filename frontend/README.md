# KrishiAi Frontend

React UI for the V1 decision-support API.

## Run

1. Backend: `cd backend && uv run uvicorn app.main:app --reload`
2. Frontend: `cd frontend && npm install && npm run dev`
3. Open http://127.0.0.1:5173

Optional: set `VITE_API_URL=http://127.0.0.1:8000` in `frontend/.env`.
