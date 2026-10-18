# Lovable ↔ Backend Integration Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox syntax.

**Goal:** Ship Lovable UI as the default frontend, wired to FastAPI query/farmers/vision APIs.

**Architecture:** Merge MobileNet API + Lovable components into one branch; Vite SPA entry mounts router (landing/auth/chat); `api.ts` is the only HTTP client; chat replaces mocks with `askAdvice`.

**Tech Stack:** React 19, Vite, Tailwind/shadcn (Lovable), TanStack Router (client) or React Router, FastAPI backend.

## Global Constraints

- Prefer packages already referenced by Lovable `bun.lock` / known-stable versions.
- Do not commit `.env` or secrets.
- Keep Lovable visual language (rounded-3xl, leaf gradients, chat layout).
- Demo auth only; no user DB.

---

### Task 1: Branch + merge both PR tips

- [x] Create `feat/lovable-backend-integration` from `main`
- [x] Merge `origin/feat/mobilenetv3-multiagent-integration`
- [x] Merge `origin/feature/lovable-frontend`
- [x] Resolve any conflicts favoring MobileNet `api.ts` + Lovable UI files

### Task 2: Make Lovable app buildable

- [x] Sync `frontend/package.json` with deps required by Lovable components
- [x] Add Tailwind, path alias `@/`, update `vite.config.ts` + `tsconfig`
- [x] Port Lovable `styles.css` theme variables
- [x] Point `main.tsx` at router (not old `App.tsx`)
- [x] `npm install` / build until green

### Task 3: API client + farm context

- [x] Ensure MobileNet-capable `api.ts` (askAdvice + farmers + feedback)
- [x] SettingsModal: farmer_id, location, crop, acres → saveFarmer
- [x] Persist farmer_id in localStorage

### Task 4: Wire chat

- [x] `chat.tsx`: replace `getMockResponse` with `askAdvice`
- [x] Map agents / diagnosis into message content
- [x] ChatInput: image attach → base64
- [x] Update demo disclaimer copy

### Task 5: Verify

- [x] Frontend build
- [ ] Manual: create farmer → ask → optional image
- [x] Summarize files + test steps for user
