from app.agents.base import enrich_with_llm, run_knowledge
from app.orchestrator.question_bank import apply_guidance
from app.schemas.models import AgentResult, FarmContext
from app.tools.registry import tool_registry


def knowledge_retriever_agent(query: str, context: FarmContext) -> AgentResult:
    evidence, citations = run_knowledge("knowledge_retriever", query, context.crop)
    # Also pull explicit tool output for richer draft
    # evidence already from run_knowledge
    draft_bits = [c for c in citations] or ["No matching knowledge passages found."]
    draft = "Retrieved guidance: " + "; ".join(draft_bits)
    draft = apply_guidance(
        "knowledge_retriever",
        query,
        draft,
        evidence,
        tools_empty=not citations and not evidence,
    )
    recommendation = enrich_with_llm("knowledge_retriever", context, query, draft, evidence)
    return AgentResult(
        agent="knowledge_retriever",
        recommendation=recommendation,
        confidence=0.65 if citations else 0.35,
        tool_evidence=evidence,
        citations=citations,
    )


# Keep alias used by tool wiring
def _noop_registry_touch():
    return tool_registry
