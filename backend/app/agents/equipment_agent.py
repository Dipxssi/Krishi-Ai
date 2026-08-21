from app.agents.base import enrich_with_llm, run_knowledge
from app.schemas.models import AgentResult, FarmContext


def equipment_agent(query: str, context: FarmContext) -> AgentResult:
    evidence, citations = run_knowledge("equipment", query, context.crop)
    area = context.farm_area_acres
    draft = (
        f"For {area} acres, prefer rental/shared sprayers or small implements over capital purchase "
        f"unless utilization is high. Factor rental into treatment cost. "
        f"Citations: {', '.join(citations) or 'none'}."
    )
    recommendation = enrich_with_llm("equipment", context, query, draft, evidence)
    return AgentResult(
        agent="equipment",
        recommendation=recommendation,
        confidence=0.55 if citations else 0.4,
        tool_evidence=evidence,
        citations=citations,
    )
