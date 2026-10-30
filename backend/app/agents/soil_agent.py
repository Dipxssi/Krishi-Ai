from app.agents.base import enrich_with_llm, evidence_from_trace, run_knowledge
from app.orchestrator.question_bank import apply_guidance
from app.schemas.models import AgentResult, EvidenceItem, FarmContext
from app.tools.registry import tool_registry


def soil_agent(query: str, context: FarmContext) -> AgentResult:
    evidence, citations = run_knowledge("soil", query, context.crop)
    npk = context.soil_npk or {}
    interpretation: dict = {}

    if context.crop and npk:
        n = npk.get("n")
        p = npk.get("p")
        k = npk.get("k")
        if n is not None and p is not None and k is not None:
            trace = tool_registry.execute(
                agent="soil",
                tool="interpret_soil_npk",
                arguments={
                    "crop": context.crop,
                    "n": float(n),
                    "p": float(p),
                    "k": float(k),
                    "ph": npk.get("ph"),
                    "growth_stage": context.growth_stage,
                    "nutrient_units": "kg_per_ha",
                },
            )
            evidence.extend(evidence_from_trace("soil", trace))
            if trace.status.startswith("success") and isinstance(trace.output, dict):
                interpretation = trace.output
                for rec in interpretation.get("recommendations", [])[:4]:
                    evidence.append(
                        EvidenceItem(
                            source=f"soil_npk:{interpretation.get('crop')}",
                            value=rec,
                            unit="recommendation",
                            agent="soil",
                        )
                    )

    if interpretation:
        draft = (
            f"Soil type: {context.soil_type or 'unknown'}. "
            f"{interpretation.get('summary', '')}\n"
            f"Details: {'; '.join(interpretation.get('recommendations', [])[:5]) or 'No major gaps detected.'}\n"
            f"Growth stage: {context.growth_stage or 'unknown'}. "
            f"Citations: {', '.join(citations) or 'none'}."
        )
        confidence = 0.78 if interpretation.get("recommendations") else 0.65
    else:
        draft = (
            f"Soil type: {context.soil_type or 'unknown'}. NPK: {npk or 'not provided'}. "
            f"Provide lab NPK values (N, P, K in kg/ha) and crop for a structured gap analysis. "
            f"Growth stage: {context.growth_stage or 'unknown'}. "
            f"Citations: {', '.join(citations) or 'none'}."
        )
        confidence = 0.5 if context.soil_type or npk else 0.3

    draft = apply_guidance("soil", query, draft, evidence, tools_empty=not interpretation)
    recommendation = enrich_with_llm("soil", context, query, draft, evidence)
    return AgentResult(
        agent="soil",
        recommendation=recommendation,
        confidence=confidence,
        tool_evidence=evidence,
        citations=citations,
    )
