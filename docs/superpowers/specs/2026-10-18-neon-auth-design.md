# Neon auth (sign-up / sign-in)

**Status:** Approved for implementation (user: Neon + implement)  
**Date:** 2026-10-18

## Approach

Email/password auth against Neon Postgres. JWT bearer tokens for the SPA. On signup, create a `users` row and a default `farm_contexts` profile so `/query` keeps working with `farmer_id`.

## API

| Method | Path | Body | Result |
|--------|------|------|--------|
| POST | `/auth/signup` | name, email, password | user + access_token |
| POST | `/auth/login` | email, password | user + access_token |
| GET | `/auth/me` | Bearer token | current user + farmer_id |

## Data

- `users`: id (uuid), email (unique), name, password_hash, farmer_id, created_at
- Existing `farm_contexts` keyed by `farmer_id` (set to `user.id` on signup)

## Config

- `DATABASE_URL` — Neon connection string (`postgresql+psycopg://...`)
- `JWT_SECRET` — signing key
- Default remains SQLite for local/tests if `DATABASE_URL` unset

## Frontend

- AuthForm calls signup/login; store `access_token` + profile in `localStorage`
- Chat Settings uses authenticated `farmer_id`
- Demo fake delay removed
