from app.agents.base import enrich_with_llm, run_knowledge
from app.schemas.models import AgentResult, FarmContext


def crop_health_agent(query: str, context: FarmContext) -> AgentResult:
    evidence, citations = run_knowledge("crop_health", query, context.crop)
    crop = context.crop or "the crop"
    stage = context.growth_stage or "unknown stage"
    draft = (
        f"Text-only crop health for {crop} ({stage}). Image diagnosis is not available in V1. "
        f"Based on retrieved guidance, prioritize cultural controls, avoid unnecessary sprays before rain, "
        f"and escalate to an agronomist if disease confidence is unclear. Citations: {', '.join(citations) or 'none'}."
    )
    recommendation = enrich_with_llm("crop_health", context, query, draft, evidence)
    return AgentResult(
        agent="crop_health",
        recommendation=recommendation,
        confidence=0.55 if citations else 0.35,
        tool_evidence=evidence,
        citations=citations,
    )
