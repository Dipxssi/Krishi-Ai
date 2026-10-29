# Offline unlock + hybrid answers (all phases)

## Phase 1 — Continue as {name}
- Cache auth user + farm profile after online login
- If API unreachable and JWT missing/expired but cache exists → Continue as {name}
- Chat opens in offline mode; signup/first login still need network
- On reconnect, validate token / prompt re-login only if server rejects

## Phase 2 — Offline draft → queue → online detail
- Offline ask → short local suggestion (FAQ + farm profile), labeled offline
- Same question queued; when online, API answer replaces offline draft (verified)

## Phase 3 — Offline pack
- Optional download while online (curated knowledge JSON; tiny model hook optional)
- Used only offline; never blocks unlock
