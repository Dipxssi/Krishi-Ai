from app.agents.base import enrich_with_llm, evidence_from_trace, run_knowledge
from app.schemas.models import AgentResult, FarmContext
from app.tools.agriculture import default_today
from app.tools.registry import tool_registry


def finance_agent(query: str, context: FarmContext) -> AgentResult:
    evidence, citations = run_knowledge("finance", query, context.crop)

    market = None
    if context.crop and context.location:
        mtrace = tool_registry.execute(
            agent="finance",
            tool="get_market_price",
            arguments={
                "crop": context.crop,
                "market": context.location,
                "date": default_today(),
            },
            repair_fn=lambda args, _err: {
                **args,
                "crop": args.get("crop") or context.crop or "tomato",
                "market": args.get("market") or context.location,
                "date": args.get("date") or default_today(),
            },
        )
        evidence.extend(evidence_from_trace("finance", mtrace))
        if mtrace.status.startswith("success") and isinstance(mtrace.output, dict):
            market = mtrace.output

    selling_price = float(market["current_price"]) if market else 30.0
    expected_yield = 8000.0  # kg/acre baseline tomato-ish
    area = context.farm_area_acres
    seed = 3000 * area
    fertilizer = 4000 * area
    pesticide = 2500 * area
    labor = 5000 * area
    irrigation = 2000 * area if not context.irrigation_available else 1500 * area
    equipment = 1500 * area
    transport = 1000 * area

    # If budget-constrained, model a cheaper treatment path
    if context.budget is not None and context.budget < 15000 * area:
        pesticide = min(pesticide, max(0.0, context.budget * 0.15))
        fertilizer = min(fertilizer, max(0.0, context.budget * 0.2))

    ptrace = tool_registry.execute(
        agent="finance",
        tool="calculate_profit",
        arguments={
            "area": area,
            "expected_yield": expected_yield,
            "selling_price": selling_price,
            "seed_cost": seed,
            "fertilizer_cost": fertilizer,
            "pesticide_cost": pesticide,
            "labor_cost": labor,
            "irrigation_cost": irrigation,
            "equipment_cost": equipment,
            "transport_cost": transport,
        },
    )
    evidence.extend(evidence_from_trace("finance", ptrace))
    profit = ptrace.output if ptrace.status.startswith("success") else {}

    budget_note = (
        f"Budget available: INR {context.budget}."
        if context.budget is not None
        else "Budget not provided in farm context."
    )
    draft = (
        f"Estimated revenue INR {profit.get('revenue')}, total cost INR {profit.get('total_cost')}, "
        f"profit INR {profit.get('profit')}, break-even INR {profit.get('break_even_price')}/kg. "
        f"{budget_note} Prefer lower-cost treatment or early sale if profit after full treatment is weak "
        f"and prices are soft."
    )
    recommendation = enrich_with_llm("finance", context, query, draft, evidence)
    confidence = 0.75 if profit else 0.45
    return AgentResult(
        agent="finance",
        recommendation=recommendation,
        confidence=confidence,
        tool_evidence=evidence,
        citations=citations,
    )
