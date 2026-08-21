"""Plan–Critique–Revise orchestrator."""

from __future__ import annotations

from typing import Callable

from app.agents.crop_agent import crop_health_agent
from app.agents.equipment_agent import equipment_agent
from app.agents.finance_agent import finance_agent
from app.agents.knowledge_agent import knowledge_retriever_agent
from app.agents.market_agent import market_agent
from app.agents.soil_agent import soil_agent
from app.agents.weather_agent import weather_agent
from app.core.config import get_settings
from app.orchestrator.router import route_query
from app.schemas.models import (
    AgentResult,
    DecisionScore,
    EvidenceItem,
    FarmContext,
    QueryResponse,
)
from app.services import llm
from app.services.validator import validate_draft
from app.tools.agriculture import (
    calculate_profit,
    default_today,
    estimate_decision_score,
    get_market_price,
    get_weather,
    register_all_tools,
)
from app.tools.registry import tool_registry

AGENT_RUNNERS: dict[str, Callable[[str, FarmContext], AgentResult]] = {
    "finance": finance_agent,
    "market": market_agent,
    "weather": weather_agent,
    "crop_health": crop_health_agent,
    "equipment": equipment_agent,
    "soil": soil_agent,
    "knowledge_retriever": knowledge_retriever_agent,
}

_tools_registered = False


def _ensure_tools() -> None:
    global _tools_registered
    if not _tools_registered:
        register_all_tools(tool_registry)
        _tools_registered = True


def _build_draft(agent_results: list[AgentResult]) -> str:
    parts = []
    for ar in agent_results:
        parts.append(f"[{ar.agent} | conf={ar.confidence:.2f}] {ar.recommendation}")
    return "\n\n".join(parts)


def _compute_decision_score(context: FarmContext, evidence: list[EvidenceItem], query: str) -> DecisionScore | None:
    # Pull weather/market/profit signals from evidence when present
    rainfall = None
    current_price = None
    profit_val = None
    cost_val = None
    for e in evidence:
        if e.unit == "mm rainfall" and isinstance(e.value, (int, float)):
            rainfall = float(e.value)
        if e.unit and "INR/kg" in e.unit and isinstance(e.value, (int, float)):
            current_price = float(e.value)
        if e.unit == "INR profit" and isinstance(e.value, (int, float)):
            profit_val = float(e.value)
        if e.unit == "INR cost" and isinstance(e.value, (int, float)):
            cost_val = float(e.value)

    # Ensure we have core numbers via deterministic tools if agents didn't run them
    location = context.location
    crop = context.crop or "tomato"
    if rainfall is None and location:
        w = get_weather(location, 7)
        rainfall = float(w["rainfall_mm"])
    if current_price is None and location:
        m = get_market_price(crop, location, default_today())
        current_price = float(m["current_price"])
    if profit_val is None:
        area = context.farm_area_acres
        p = calculate_profit(
            area=area,
            expected_yield=8000,
            selling_price=current_price or 30,
            seed_cost=3000 * area,
            fertilizer_cost=4000 * area,
            pesticide_cost=2500 * area,
            labor_cost=5000 * area,
            irrigation_cost=2000 * area,
            equipment_cost=1500 * area,
            transport_cost=1000 * area,
        )
        profit_val = float(p["profit"])
        cost_val = float(p["total_cost"])

    water_risk = min(1.0, (rainfall or 0) / 40.0)
    disease_risk = 0.55 if any(k in query.lower() for k in ("spot", "disease", "blight", "pest")) else 0.3
    agronomic = 0.7
    if context.irrigation_available:
        agronomic += 0.05
    if context.soil_type:
        agronomic += 0.05
    agronomic = min(1.0, agronomic)

    raw = estimate_decision_score(
        agronomic_suitability=agronomic,
        expected_profit=profit_val or 0,
        water_risk=water_risk,
        disease_risk=disease_risk,
        input_cost=cost_val or 0,
    )
    return DecisionScore(**raw)


def _revise(draft: str, critique: str, evidence: list[EvidenceItem], context: FarmContext, query: str) -> str:
    evidence_lines = "\n".join(f"- {e.source}: {e.value} {e.unit or ''}" for e in evidence)
    template = (
        f"Query: {query}\n"
        f"Farm: {context.model_dump()}\n"
        f"Evidence:\n{evidence_lines}\n"
        f"Draft:\n{draft}\n"
        f"Critique:\n{critique}\n\n"
        "Produce a revised final recommendation for the farmer: treat vs continue vs sell early if relevant. "
        "Cite only evidence above. Label forecasts as forecasts. Be concise."
    )
    if llm.is_llm_available():
        text = llm.generate(
            template,
            system="You are the KrishiAi orchestrator. Revise using evidence only. Max clarity for farmers.",
        )
        if text:
            return text
    # Deterministic fallback synthesis
    return (
        f"Revised recommendation based on specialist outputs and critique.\n"
        f"Critique addressed: {critique}\n\n{draft}\n\n"
        f"Evidence count: {len(evidence)}. Update missing farm context fields before high-stakes actions."
    )


def handle_query(query: str, context: FarmContext) -> QueryResponse:
    _ensure_tools()
    tool_registry.reset(farmer_id=context.farmer_id)

    selected, _scores = route_query(query)
    # Always include knowledge retriever for citations on multi-factor farm decisions
    if "knowledge_retriever" not in selected and len(selected) >= 2:
        selected = [*selected, "knowledge_retriever"]

    agent_results: list[AgentResult] = []
    for name in selected:
        runner = AGENT_RUNNERS.get(name)
        if runner:
            agent_results.append(runner(query, context))

    draft = _build_draft(agent_results)
    revision_count = 0
    settings = get_settings()
    validation = validate_draft(
        context=context,
        agent_results=agent_results,
        tool_traces=tool_registry.traces,
        draft_text=draft,
    )
    final = draft

    while revision_count < settings.max_revisions:
        final = _revise(final, validation["critique"], validation["evidence"], context, query)
        revision_count += 1
        validation = validate_draft(
            context=context,
            agent_results=agent_results,
            tool_traces=tool_registry.traces,
            draft_text=final,
        )
        # Stop early if critique is clean enough
        if validation["ok"] and not validation["missing_context"] and revision_count >= 1:
            break

    decision = _compute_decision_score(context, validation["evidence"], query)
    confidences = [a.confidence for a in agent_results]
    confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return QueryResponse(
        query=query,
        farmer_id=context.farmer_id,
        final_recommendation=final,
        decision_score=decision,
        agents_used=selected,
        confidence=round(confidence, 3),
        evidence=validation["evidence"],
        tool_traces=tool_registry.traces,
        warnings=validation["warnings"],
        missing_context=validation["missing_context"],
        revision_count=revision_count,
        agent_results=agent_results,
    )
