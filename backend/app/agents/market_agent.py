from app.agents.base import enrich_with_llm, evidence_from_trace, run_knowledge
from app.orchestrator.question_bank import apply_guidance
from app.schemas.models import AgentResult, FarmContext
from app.tools.agriculture import default_today
from app.tools.registry import tool_registry


def market_agent(query: str, context: FarmContext) -> AgentResult:
    evidence, citations = run_knowledge("market", query, context.crop)
    missing = []
    if not context.crop:
        missing.append("crop")
    if not context.location:
        missing.append("location")

    if missing:
        draft = f"Cannot fetch market prices without: {', '.join(missing)}. Please update FarmContext."
        draft = apply_guidance("market", query, draft, evidence, tools_empty=True)
        return AgentResult(agent="market", recommendation=draft, confidence=0.2, tool_evidence=evidence, citations=citations)

    trace = tool_registry.execute(
        agent="market",
        tool="get_market_price",
        arguments={
            "crop": context.crop,
            "market": context.location,
            "date": default_today(),
        },
        repair_fn=lambda args, _err: {
            "crop": args.get("crop") or context.crop,
            "market": args.get("market") or context.location,
            "date": args.get("date") or default_today(),
        },
    )
    evidence.extend(evidence_from_trace("market", trace))
    out = trace.output if trace.status.startswith("success") and isinstance(trace.output, dict) else {}
    markets = [str(name).strip() for name in (out.get("sell_markets") or []) if str(name).strip()]
    market_line = ", ".join(markets) if markets else "the district APMC yard for this place"
    if out.get("is_mock"):
        price_line = (
            f"An indicative {context.crop} price near {context.location} is {out.get('current_price')} INR/kg. "
            "This is not today's yard rate. Ask the market for the rate before agreeing a sale."
        )
    else:
        price_line = (
            f"Recent {context.crop} modal price near {context.location} is {out.get('current_price')} INR/kg "
            "from the listed yards."
        )
    draft = (
        f"Markets where the farmer can sell {context.crop}: {market_line}. "
        f"{price_line} "
        f"The 30-day outlook is {out.get('forecast_price')} INR/kg. "
        f"Label that outlook as a forecast with {out.get('forecast_uncertainty')} uncertainty. "
        "Name these markets in the answer. Do not replace them with a generic city market. "
        "Do not mention mock services, source labels, or internal system names. "
        "If storage is unavailable and the outlook is lower, say selling sooner is worth asking about."
    )
    draft = apply_guidance("market", query, draft, evidence, tools_empty=not out)
    recommendation = enrich_with_llm("market", context, query, draft, evidence)
    return AgentResult(
        agent="market",
        recommendation=recommendation,
        confidence=0.7 if out else 0.3,
        tool_evidence=evidence,
        citations=citations,
    )
