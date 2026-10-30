# Agent question bank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each of the 7 agents 1,000 indexed questions in English, Hindi, and Kannada so routing and empty-record replies come from that bank.

**Architecture:** A generator writes `backend/data/question_bank/{agent}.{lang}.jsonl`. `question_bank.py` loads index rows, scores Unicode-word overlap, and returns a next step. `route_query` adds the bank's agent beside the phrase matcher. Agents append that next step when their tools are empty. Finance also appends it when the match is strong, and appends catalog rate fields only at read time.

**Tech Stack:** Python, existing FastAPI orchestrator, JSONL, no embedding API.

## Global Constraints

- 7 agents: crop_health, finance, equipment, market, weather, soil, knowledge_retriever.
- 1,000 `index` rows and 50 `holdout` rows per agent per language (22,050 rows).
- Hindi in Devanagari. Kannada in Kannada script.
- `next_step` has no `%`, `₹`, `Rs`, `INR`, digits, or `UNSAFE_CHEMICAL_PATTERNS`.
- Office name is Krishi Vigyan Kendra (KVK), never Kisan Vikas Kendra.
- Overlap coefficient: shared Unicode tokens / smaller token count. Empty question scores 0.
- Add a bank agent only when the best score is at least 0.55 and at least 3 of the top 5 neighbors share that agent. Below 0.35 adds nobody.
- Phrase-matcher selections stay. Image still adds crop_health. A finance marker still adds finance.
- A Kannada question reads the Kannada index only.
- Linked loan ids: crop loan and Kisan Credit Card → `kcc-crop-loan`, gold loan → `agri-gold-loan`, equipment loan → `farm-mechanization-loan`, dairy loan → `dairy-loan-nabard`, MUDRA → `mudra-agri`.

## Tasks

- [x] Add `backend/app/orchestrator/question_bank.py` with `neighbors`, `matching_agent`, `apply_guidance`, and `clear_cache`.
- [x] Add `backend/scripts/generate_question_bank.py` and write the 21 JSONL files.
- [x] Call `matching_agent` at the end of `route_query`.
- [x] Append bank guidance from all 7 agents. Finance uses `always_if_strong=True`.
- [x] Tell the final rewrite that a `question_bank:` evidence line is a real next step.
- [x] Test counts, safety, the Bengaluru tomato loan, Kannada next step, holdout routing, and a missing bank directory.
