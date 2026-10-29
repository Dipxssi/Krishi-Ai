# Auto offline pack + view-only memory

## Decision
Option **B** (2026-10-29).

## Pack
- While online (app origin reachable for `/offline-pack/v1.json`), download/update the pack in the background after auth / chat boot.
- Never blocks unlock or chat.
- Settings: status only + optional **Remove**. No required Download button (optional Retry if missing/failed).

## Memory
- After each successful Q&A (including outbox flush), rolling summary is written to profile memory automatically.
- Settings: **read-only** display of that summary + **Clear**. No Save / no edit.

## Out of scope
- PIN unlock, WebLLM, editing memory in Settings, forcing pack download on every page load when already current.
