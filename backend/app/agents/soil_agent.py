from app.agents.base import enrich_with_llm, run_knowledge
from app.schemas.models import AgentResult, FarmContext


def soil_agent(query: str, context: FarmContext) -> AgentResult:
    evidence, citations = run_knowledge("soil", query, context.crop)
    npk = context.soil_npk or {}
    draft = (
        f"Soil type: {context.soil_type or 'unknown'}. NPK: {npk or 'not provided'}. "
        f"Without lab data, avoid aggressive fertilizer changes. Prefer split doses matching crop stage "
        f"{context.growth_stage or 'unknown'}. Citations: {', '.join(citations) or 'none'}."
    )
    recommendation = enrich_with_llm("soil", context, query, draft, evidence)
    return AgentResult(
        agent="soil",
        recommendation=recommendation,
        confidence=0.5 if context.soil_type or npk else 0.3,
        tool_evidence=evidence,
        citations=citations,
    )
