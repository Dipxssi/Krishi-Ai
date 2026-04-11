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

### AI (Planned / In Progress)

* LLMs (OpenAI / Ollama)
* RAG (Retrieval-Augmented Generation)
* Vector Database (pgvector )

### Frontend

* React (planned)

---




---

##  Current Status (Phase 1)

*  Backend architecture implemented
* Multi-agent system (4 agents)
*  Rule-based query routing
*  Response aggregation

---

##  Upcoming Features

* LLM-based intelligent routing
*  RAG with real agricultural datasets
*  Voice input using Whisper
*  Crop disease detection via images
*  Regional language support
*  Real-time market price integration

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
