"""Shared helpers for specialist agents."""

from __future__ import annotations

from typing import Any

from app.schemas.models import AgentResult, EvidenceItem, FarmContext
from app.services import llm
from app.tools.agriculture import default_today
from app.tools.registry import tool_registry


def evidence_from_trace(agent: str, trace) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    if trace.status not in ("success", "success_after_retry") or not isinstance(trace.output, dict):
        return items
    out = trace.output
    if trace.tool == "get_weather":
        items.append(EvidenceItem(source=out.get("source", "weather"), value=out.get("rainfall_mm"), unit="mm rainfall", agent=agent))
        items.append(EvidenceItem(source=out.get("source", "weather"), value=out.get("avg_temp_c"), unit="C", agent=agent))
        items.append(EvidenceItem(source=out.get("source", "weather"), value=out.get("condition"), unit="condition", agent=agent))
    elif trace.tool == "get_market_price":
        items.append(EvidenceItem(source=out.get("source", "market"), value=out.get("current_price"), unit=out.get("unit", "INR/kg"), agent=agent))
        items.append(
            EvidenceItem(
                source=out.get("source", "market"),
                value={
                    "forecast_price": out.get("forecast_price"),
                    "horizon": out.get("forecast_horizon"),
                    "uncertainty": out.get("forecast_uncertainty"),
                },
                unit="forecast",
                agent=agent,
            )
        )
    elif trace.tool == "calculate_profit":
        items.append(EvidenceItem(source="profit_calculator", value=out.get("profit"), unit="INR profit", agent=agent))
        items.append(EvidenceItem(source="profit_calculator", value=out.get("total_cost"), unit="INR cost", agent=agent))
        items.append(EvidenceItem(source="profit_calculator", value=out.get("revenue"), unit="INR revenue", agent=agent))
    elif trace.tool == "search_crop_knowledge":
        for hit in out.get("results", []):
            items.append(
                EvidenceItem(
                    source=f"rag:{hit.get('source')}",
                    value=hit.get("title"),
                    unit="citation",
                    agent=agent,
                )
            )
    elif trace.tool == "estimate_decision_score":
        items.append(EvidenceItem(source="decision_score", value=out.get("final_score"), unit="score", agent=agent))
    elif trace.tool == "get_equipment_price":
        for m in out.get("matches", [])[:3]:
            items.append(EvidenceItem(source="equipment_prices", value=m.get("name"), unit="equipment", agent=agent))
    elif trace.tool == "search_schemes":
        for m in out.get("matches", [])[:3]:
            items.append(EvidenceItem(source=f"scheme:{m.get('id')}", value=m.get("name"), unit="scheme", agent=agent))
    elif trace.tool == "search_loans":
        for m in out.get("matches", [])[:3]:
            items.append(EvidenceItem(source=f"loan:{m.get('id')}", value=m.get("name"), unit="loan", agent=agent))
    elif trace.tool == "interpret_soil_npk":
        items.append(EvidenceItem(source="soil_npk", value=out.get("summary"), unit="soil summary", agent=agent))
        for gap in out.get("gaps", []):
            if gap.get("status") != "adequate":
                items.append(
                    EvidenceItem(
                        source=f"soil_npk:{gap.get('symbol')}",
                        value=f"{gap.get('status')} ({gap.get('farmer_kg_per_acre')} vs {gap.get('target_kg_per_acre')} kg/acre)",
                        unit="nutrient gap",
                        agent=agent,
                    )
                )
    return items


def citations_from_knowledge(trace) -> list[str]:
    if not isinstance(trace.output, dict):
        return []
    return [f"{h.get('id')}: {h.get('title')}" for h in trace.output.get("results", [])]


def enrich_with_llm(agent: str, context: FarmContext, query: str, draft: str, evidence: list[EvidenceItem]) -> str:
    if not llm.is_llm_available():
        return draft
    from app.services.multilingual import (
        _current_farmer_question,
        detect_language,
        reply_language_instruction,
    )
    lang = detect_language(query, fallback=context.preferred_language or "en")
    lang_name = {
        "kn": "Kannada (ಕನ್ನಡ script)",
        "hi": "Hindi (हिंदी Devanagari script)",
        "en": "English",
    }.get(lang, "English")
    farmer_question = _current_farmer_question(query)
    farm_context = context.model_dump()
    farm_context["preferred_language"] = lang

    evidence_lines = "\n".join(f"- {e.source}: {e.value} {e.unit or ''}" for e in evidence)
    prompt = (
        f"You are the {agent} agent for an Indian farmer decision-support system.\n"
        f"Farm context: {farm_context}\n"
        f"Farmer query: {farmer_question}\n"
        f"Tool/RAG evidence (ONLY use these facts):\n{evidence_lines or '(none)'}\n"
        f"Draft recommendation:\n{draft}\n\n"
        f"Rewrite a concise recommendation grounded ONLY in the evidence and context in fluent {lang_name}. "
        f"If evidence is missing, say what is unknown. Do not invent prices, rainfall, or profits."
    )
    system = (
        f"Evidence-grounded agricultural advisor. {reply_language_instruction(lang)} "
        "Never fabricate numbers. Ignore farm preferred_language when it differs from this instruction."
    )
    text = llm.generate(prompt, system=system)
    return text or draft


def run_knowledge(agent: str, query: str, crop: str | None) -> tuple[list[EvidenceItem], list[str]]:
    trace = tool_registry.execute(
        agent=agent,
        tool="search_crop_knowledge",
        arguments={"query": query, "crop": crop, "top_k": 3},
    )
    return evidence_from_trace(agent, trace), citations_from_knowledge(trace)
