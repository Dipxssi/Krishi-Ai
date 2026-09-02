"""Plan–Critique–Revise orchestrator with parallel agents + multimodal support."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from app.agents.crop_agent import crop_health_agent
from app.agents.equipment_agent import equipment_agent
from app.agents.finance_agent import finance_agent
from app.agents.knowledge_agent import knowledge_retriever_agent
from app.agents.market_agent import market_agent
from app.agents.soil_agent import soil_agent
from app.agents.weather_agent import weather_agent
from app.core.config import get_settings
from app.orchestrator.router import infer_risk_level, route_query
from app.schemas.models import (
    AgentResult,
    DecisionScore,
    EvidenceItem,
    FarmContext,
    ImageDiagnosisResult,
    QueryResponse,
    StructuredRecommendation,
)
from app.services import llm
from app.services.audit import new_request_id, save_query_run
from app.services.conflict_resolver import resolve_conflicts
from app.services.crop_registry import build_profit_inputs
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
from app.vision.diagnosis import diagnose_image_bytes

AGENT_RUNNERS: dict[str, Callable[..., AgentResult]] = {
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


def _run_agents_parallel(
    selected: list[str],
    query: str,
    context: FarmContext,
    image_diagnosis: ImageDiagnosisResult | None,
) -> list[AgentResult]:
    results: list[AgentResult] = []

    def _run(name: str) -> AgentResult | None:
        runner = AGENT_RUNNERS.get(name)
        if not runner:
            return None
        if name == "crop_health" and image_diagnosis is not None:
            return runner(query, context, image_diagnosis=image_diagnosis)
        return runner(query, context)

    with ThreadPoolExecutor(max_workers=min(6, len(selected))) as pool:
        futures = {pool.submit(_run, name): name for name in selected}
        for fut in as_completed(futures):
            ar = fut.result()
            if ar:
                results.append(ar)
    order = {a: i for i, a in enumerate(selected)}
    results.sort(key=lambda r: order.get(r.agent, 99))
    return results


def _build_draft(agent_results: list[AgentResult]) -> str:
    parts = []
    for ar in agent_results:
        parts.append(f"[{ar.agent} | conf={ar.confidence:.2f}] {ar.recommendation}")
    return "\n\n".join(parts)


def _compute_decision_score(
    context: FarmContext,
    evidence: list[EvidenceItem],
    query: str,
    image_diagnosis: ImageDiagnosisResult | None = None,
) -> DecisionScore | None:
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

    location = context.location
    crop = context.crop or "tomato"
    if rainfall is None and location:
        w = get_weather(location, 7)
        rainfall = float(w["rainfall_mm"])
    if current_price is None and location:
        m = get_market_price(crop, location, default_today())
        current_price = float(m["current_price"])
    if profit_val is None:
        profit_args = build_profit_inputs(
            crop,
            area_acres=context.farm_area_acres,
            selling_price=current_price or 30,
            irrigation_available=context.irrigation_available,
            budget=context.budget,
        )
        p = calculate_profit(
            area=profit_args["area"],
            expected_yield=profit_args["expected_yield"],
            selling_price=profit_args["selling_price"],
            seed_cost=profit_args["seed_cost"],
            fertilizer_cost=profit_args["fertilizer_cost"],
            pesticide_cost=profit_args["pesticide_cost"],
            labor_cost=profit_args["labor_cost"],
            irrigation_cost=profit_args["irrigation_cost"],
            equipment_cost=profit_args["equipment_cost"],
            transport_cost=profit_args["transport_cost"],
        )
        profit_val = float(p["profit"])
        cost_val = float(p["total_cost"])

    water_risk = min(1.0, (rainfall or 0) / 40.0)
    disease_risk = 0.55 if any(k in query.lower() for k in ("spot", "disease", "blight", "pest")) else 0.3
    if image_diagnosis and image_diagnosis.disease and image_diagnosis.disease != "healthy":
        disease_risk = max(disease_risk, 0.65)

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
    return (
        f"Revised recommendation based on specialist outputs and critique.\n"
        f"Critique addressed: {critique}\n\n{draft}\n\n"
        f"Evidence count: {len(evidence)}. Update missing farm context fields before high-stakes actions."
    )


def _clarifying_preface(missing: list[str]) -> str:
    if not missing:
        return ""
    labels = {
        "location": "farm location",
        "crop": "current/planned crop",
        "budget": "available budget (INR)",
        "farm_area_acres": "farm area in acres",
        "soil_type_or_soil_npk": "soil type or NPK values",
    }
    pretty = [labels.get(m, m) for m in missing]
    return (
        "Before acting on high-stakes advice, please update FarmContext with: "
        + ", ".join(pretty)
        + ".\n\n"
    )


def _build_structured(
    final: str,
    agent_results: list[AgentResult],
    validation: dict,
    conflict_notes: list[str],
    decision: DecisionScore | None,
    image_diagnosis: ImageDiagnosisResult | None,
    query: str,
) -> StructuredRecommendation:
    sources = []
    for e in validation["evidence"]:
        sources.append(e.source)
    for ar in agent_results:
        sources.extend(ar.citations)
    human_review = bool(validation["missing_context"]) or bool(
        image_diagnosis and image_diagnosis.requires_expert
    )
    if any("Unsafe" in w for w in validation["warnings"]):
        human_review = True
    financial = None
    if decision:
        financial = {
            "expected_profit_inr": decision.expected_profit,
            "input_cost_inr": decision.input_cost,
            "water_risk": decision.water_risk,
            "disease_risk": decision.disease_risk,
        }
    reasons = conflict_notes[:5]
    for ar in agent_results:
        if ar.confidence >= 0.6:
            reasons.append(f"{ar.agent}: high-confidence specialist input")
    return StructuredRecommendation(
        action_summary=final.split("\n")[0][:500],
        reasons=reasons[:8],
        financial_summary=financial,
        sources=list(dict.fromkeys(sources))[:20],
        human_review_required=human_review,
        risk_level=infer_risk_level(query),
        conflicts_resolved=conflict_notes,
    )


def handle_query(
    query: str,
    context: FarmContext,
    *,
    image_base64: str | None = None,
    request_id: str | None = None,
    persist: bool = True,
) -> QueryResponse:
    _ensure_tools()
    req_id = request_id or new_request_id()
    tool_registry.reset(farmer_id=context.farmer_id)

    image_diagnosis: ImageDiagnosisResult | None = None
    if image_base64:
        image_diagnosis = diagnose_image_bytes(image_base64, crop_hint=context.crop)

    selected, _scores = route_query(query, has_image=image_base64 is not None)
    if "knowledge_retriever" not in selected and len(selected) >= 2:
        selected = [*selected, "knowledge_retriever"]

    agent_results = _run_agents_parallel(selected, query, context, image_diagnosis)

    draft = _build_draft(agent_results)
    revision_count = 0
    settings = get_settings()
    validation = validate_draft(
        context=context,
        agent_results=agent_results,
        tool_traces=tool_registry.traces,
        draft_text=draft,
        image_diagnosis=image_diagnosis,
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
            image_diagnosis=image_diagnosis,
        )
        if validation["ok"] and not validation["missing_context"] and revision_count >= 1:
            break

    conflict_notes, _ = resolve_conflicts(agent_results, validation["evidence"])
    if conflict_notes:
        final = final + "\n\nConflict resolution:\n" + "\n".join(f"- {n}" for n in conflict_notes)

    decision = _compute_decision_score(context, validation["evidence"], query, image_diagnosis)
    confidences = [a.confidence for a in agent_results]
    confidence = sum(confidences) / len(confidences) if confidences else 0.0

    if validation["missing_context"]:
        confidence = min(confidence, 0.4)
        final = _clarifying_preface(validation["missing_context"]) + final

    structured = _build_structured(
        final, agent_results, validation, conflict_notes, decision, image_diagnosis, query
    )

    response = QueryResponse(
        request_id=req_id,
        query=query,
        farmer_id=context.farmer_id,
        final_recommendation=final,
        structured_recommendation=structured,
        image_diagnosis=image_diagnosis,
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
    if persist:
        save_query_run(req_id, context.farmer_id, query, response)
    return response
