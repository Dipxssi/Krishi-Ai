from app.agents.base import enrich_with_llm, evidence_from_trace, run_knowledge
from app.schemas.models import AgentResult, EvidenceItem, FarmContext
from app.tools.registry import tool_registry


def equipment_agent(query: str, context: FarmContext) -> AgentResult:
    evidence, citations = run_knowledge("equipment", query, context.crop)
    area = context.farm_area_acres

    trace = tool_registry.execute(
        agent="equipment",
        tool="get_equipment_price",
        arguments={
            "equipment_type": None,
            "category": None,
            "farm_area_acres": area,
        },
    )
    if trace.status.startswith("success") and isinstance(trace.output, dict):
        for match in trace.output.get("matches", [])[:3]:
            evidence.append(
                EvidenceItem(
                    source="equipment_prices",
                    value=f"{match['name']}: ₹{match['price_range_inr'][0]}-{match['price_range_inr'][1]}, rental ₹{match.get('rental_per_day_inr') or 'N/A'}/day",
                    unit="equipment",
                    agent="equipment",
                )
            )

    scheme_trace = tool_registry.execute(
        agent="equipment",
        tool="search_schemes",
        arguments={"category": "equipment_subsidy"},
    )
    if scheme_trace.status.startswith("success") and isinstance(scheme_trace.output, dict):
        for s in scheme_trace.output.get("matches", [])[:2]:
            evidence.append(
                EvidenceItem(
                    source=f"scheme:{s['id']}",
                    value=f"{s['name']}: {s['benefit']}",
                    unit="scheme",
                    agent="equipment",
                )
            )

    equip_lines = [e.value for e in evidence if e.unit == "equipment"]
    scheme_lines = [e.value for e in evidence if e.unit == "scheme"]
    draft = (
        f"For {area} acres:\n"
        f"Equipment options: {'; '.join(equip_lines) or 'none found'}.\n"
        f"Subsidies: {'; '.join(scheme_lines) or 'none found'}.\n"
        f"Prefer rental for small farms unless utilization > 100 days/year. "
        f"Citations: {', '.join(citations) or 'none'}."
    )
    recommendation = enrich_with_llm("equipment", context, query, draft, evidence)
    return AgentResult(
        agent="equipment",
        recommendation=recommendation,
        confidence=0.65 if equip_lines else 0.4,
        tool_evidence=evidence,
        citations=citations,
    )
