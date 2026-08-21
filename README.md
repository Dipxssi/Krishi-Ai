#  AI Farmer Decision Support System (Multi-Agent AI)

## Project Overview

The **AI Farmer Decision Support System** is a multi-agent AI platform designed to help farmers make informed agricultural and financial decisions.

The system allows farmers to ask queries in natural language (text, voice, or image), and provides **actionable, real-world solutions** by leveraging multiple specialized AI agents.

---

##  Key Idea

Instead of a single chatbot, this system uses a **multi-agent architecture**, where each agent specializes in a specific domain:

*  Crop Health
*  Finance
*  Equipment
* Market

An **Orchestrator** analyzes the query and dynamically routes it to relevant agents, then combines their responses into a single, structured output.

---


##  Features

*  Multi-agent AI architecture
*  Dynamic query routing (Orchestrator)
*  Aggregated, structured responses
*  Modular and scalable design
*  API-based backend (FastAPI)
*  Planned voice input (Whisper)
* Planned image-based crop analysis

---

##  Tech Stack

### Backend

* FastAPI
* Python
* uv (dependency management)

### AI (V1)

* Google Gemini (`GEMINI_API_KEY`, models `gemini-3.6-flash` + `gemini-embedding-001`)
* Local crop knowledge RAG (BM25 + optional dense)
* Typed tools: weather, market, profit, decision score
* React frontend (`frontend/`) for farm profile + advice

---

## Current Status (V1 text-only MVP)

* FastAPI backend with FarmContext (SQLite)
* Multi-label router (keyword / embedding / hybrid) + cost-aware selection
* Finance, market, weather, crop health, equipment, soil, knowledge agents
* Evidence validator + Plan–Critique–Revise (max 2)
* Structured `/query` responses with tool traces and citations

See [backend/README.md](backend/README.md) and [docs/architecture.md](docs/architecture.md).

---

## Upcoming Features

* Routing evaluation suite (labeled queries)
* Crop image diagnosis (two-stage reject/diagnose)
* Voice input using Whisper
* Live market/weather APIs
* React frontend
* Regional language support

---

##  Team Roles

* Backend & Orchestrator
* AI / Agents & RAG
* Frontend (UI/UX)
* Data & Integrations

---

##  Problem Statement

Farmers often lack access to:

* Reliable agricultural advice
* Financial guidance
* Market insights
* Equipment accessibility

This system provides a **unified platform** that combines all these aspects into a single intelligent assistant.

---

##  Conclusion

This project demonstrates a **scalable multi-agent AI system** capable of solving real-world agricultural problems through modular design and intelligent orchestration.

---

##  Future Scope

* Mobile app for rural accessibility
* Offline/low-bandwidth support
* Integration with government APIs
* AI-driven personalized recommendations
