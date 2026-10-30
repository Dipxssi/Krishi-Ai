from app.agents.base import enrich_with_llm, evidence_from_trace, run_knowledge
from app.orchestrator.question_bank import apply_guidance
from app.schemas.models import AgentResult, FarmContext
from app.tools.registry import tool_registry


def weather_agent(query: str, context: FarmContext) -> AgentResult:
    evidence, citations = run_knowledge("weather", query, context.crop)
    if not context.location:
        draft = apply_guidance(
            "weather",
            query,
            "Location missing from FarmContext; cannot fetch weather.",
            evidence,
            tools_empty=True,
        )
        return AgentResult(
            agent="weather",
            recommendation=draft,
            confidence=0.2,
            tool_evidence=evidence,
            citations=citations,
        )

    trace = tool_registry.execute(
        agent="weather",
        tool="get_weather",
        arguments={"location": context.location, "forecast_days": 7},
        repair_fn=lambda args, _err: {
            "location": args.get("location") or context.location,
            "forecast_days": int(args.get("forecast_days") or 7),
        },
    )
    evidence.extend(evidence_from_trace("weather", trace))
    out = trace.output if trace.status.startswith("success") and isinstance(trace.output, dict) else {}

    draft = (
        f"7-day outlook for {context.location}: rainfall {out.get('rainfall_mm')} mm, "
        f"avg temp {out.get('avg_temp_c')} C, condition {out.get('condition')} "
        f"(source={out.get('source')}, mock={out.get('is_mock')}). "
        f"Avoid spraying immediately before expected rain; watch disease pressure if wet."
    )
    draft = apply_guidance("weather", query, draft, evidence, tools_empty=not out)
    recommendation = enrich_with_llm("weather", context, query, draft, evidence)
    return AgentResult(
        agent="weather",
        recommendation=recommendation,
        confidence=0.7 if out else 0.3,
        tool_evidence=evidence,
        citations=citations,
    )
