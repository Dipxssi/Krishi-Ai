# System Architecture – KrishiAi V1

## Overview

KrishiAi V1 is a **text-only multi-agent decision-support** backend. A multi-label orchestrator routes farmer queries to specialist agents, each using typed tools and RAG. An evidence validator and Plan–Critique–Revise loop produce a structured recommendation grounded in farm context and tool outputs.

## High-level flow

```text
Text query + farmer_id
        ↓
Load FarmContext (SQLite)
        ↓
Multi-label Router (keyword | embedding | hybrid)
        ↓
Specialist agents + Knowledge Retriever
        ↓
Typed tools (weather, market, profit, decision score, RAG)
        ↓
Evidence & Safety Validator
        ↓
Orchestrator revise (max 2)
        ↓
Structured recommendation + evidence + tool traces
```

## Components

| Component | Role |
|-----------|------|
| FarmContext | Persistent farmer/farm state required for every advice call |
| Router | Set-valued agent selection with threshold, top-1 fallback, cost penalty |
| Agents | finance, market, weather, crop_health, equipment, soil, knowledge_retriever |
| Tools | Validated args → execute → one repair retry → tool trace |
| RAG | Local crop knowledge (BM25 + optional Gemini embeddings) |
| Validator | Checks evidence, missing context, unsafe pesticide language |
| LLM | Groq generation first, Gemini fallback, Gemini embeddings (`app/services/llm.py`) |

## Decision score

```text
final_score = agronomic_weight * agronomic_score + economic_weight * economic_score
```

Defaults: `0.6` / `0.4` (configurable). Risks for water, disease, and input cost reduce the component scores.

## Backend map

```text
app/api/query.py, farmers.py     → HTTP API
app/db/session.py                → SQLite FarmContext + tool traces
app/orchestrator/router.py       → Multi-label routing
app/orchestrator/orchestrator.py → Plan–Critique–Revise
app/agents/*                     → Domain specialists
app/tools/*                      → Typed tools + registry
app/services/rag.py, llm.py, validator.py
data/knowledge/                  → Seed corpus
```

## Out of scope (V1)

- Image crop diagnosis
- Large labeled routing evaluation suite
- React frontend / voice
- APSIM / DSSAT simulators
