from app.agents.base import enrich_with_llm, evidence_from_trace, run_knowledge
from app.schemas.models import AgentResult, EvidenceItem, FarmContext
from app.orchestrator.question_bank import apply_guidance
from app.services.crop_registry import build_profit_inputs, estimate_harvest_related_costs
from app.services.multilingual import _current_farmer_question
from app.tools.agriculture import default_today
from app.tools.registry import tool_registry

_SCHEME_QUERY_MARKERS = (
    "subsidy",
    "subsidary",
    "scheme",
    "government",
    "govt",
    "pm-kisan",
    "pmfby",
    "midh",
    "loan",
    "kcc",
    "credit",
    "greenhouse",
    "green house",
    "polyhouse",
    "poly house",
    "protected cultivation",
)

_COST_QUERY_MARKERS = (
    "cost",
    "harvest",
    "harvesting",
    "expense",
    "profit",
    "break-even",
    "break even",
    "how much",
    "price",
    "afford",
)


def _is_scheme_focused(query: str) -> bool:
    q = query.lower()
    has_scheme = any(m in q for m in _SCHEME_QUERY_MARKERS)
    has_cost = any(m in q for m in _COST_QUERY_MARKERS)
    # Loan/scheme questions that also ask about costs should still run cost tools.
    return has_scheme and not has_cost


def _mentions_harvest(query: str) -> bool:
    q = query.lower()
    return any(m in q for m in ("harvest", "harvesting", "digging", "take out", "lifting"))


def finance_agent(query: str, context: FarmContext) -> AgentResult:
    question = _current_farmer_question(query)
    evidence, citations = run_knowledge("finance", question, context.crop)
    scheme_focused = _is_scheme_focused(question)
    harvest_estimate: dict | None = None

    market = None
    profit: dict = {}
    if not scheme_focused and context.crop and context.location:
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
        profit_args = build_profit_inputs(
            context.crop,
            area_acres=context.farm_area_acres,
            selling_price=selling_price,
            irrigation_available=context.irrigation_available,
            budget=context.budget,
        )
        evidence.append(
            EvidenceItem(
                source=f"crop_registry:{profit_args['crop_id']}",
                value=profit_args["expected_yield"],
                unit="kg/acre yield",
                agent="finance",
            )
        )
        prov = profit_args.get("yield_provenance") or {}
        if prov.get("source_year"):
            evidence.append(
                EvidenceItem(
                    source=f"yield_provenance:{profit_args['crop_id']}",
                    value=f"{prov.get('data_origin')} ({prov.get('source_year')})",
                    unit="provenance",
                    agent="finance",
                )
            )

        ptrace = tool_registry.execute(
            agent="finance",
            tool="calculate_profit",
            arguments={
                "area": profit_args["area"],
                "expected_yield": profit_args["expected_yield"],
                "selling_price": profit_args["selling_price"],
                "seed_cost": profit_args["seed_cost"],
                "fertilizer_cost": profit_args["fertilizer_cost"],
                "pesticide_cost": profit_args["pesticide_cost"],
                "labor_cost": profit_args["labor_cost"],
                "irrigation_cost": profit_args["irrigation_cost"],
                "equipment_cost": profit_args["equipment_cost"],
                "transport_cost": profit_args["transport_cost"],
            },
        )
        evidence.extend(evidence_from_trace("finance", ptrace))
        profit = ptrace.output if ptrace.status.startswith("success") else {}

    if context.crop and _mentions_harvest(question):
        harvest_estimate = estimate_harvest_related_costs(
            context.crop,
            area_acres=context.farm_area_acres,
        )
        evidence.append(
            EvidenceItem(
                source=f"crop_registry:harvest_cost:{harvest_estimate['crop_id']}",
                value=harvest_estimate["total_farm"],
                unit="INR harvest-related",
                agent="finance",
            )
        )
        for key, per_acre in harvest_estimate["per_acre"].items():
            evidence.append(
                EvidenceItem(
                    source=f"crop_registry:{harvest_estimate['crop_id']}:{key}",
                    value=round(per_acre * harvest_estimate["area_acres"], 2),
                    unit=f"INR {key.replace('_', ' ')}",
                    agent="finance",
                )
            )

    asks_loan = any(word in question.lower() for word in ("loan", "loans", "kcc", "credit", "कर्ज", "ऋण", "ಲೋನ್", "ಸಾಲ"))
    loan_trace = tool_registry.execute(
        agent="finance",
        tool="search_loans",
        arguments={
            "category": None,
            "amount_needed": None if asks_loan or scheme_focused else context.budget,
            "purpose": question if asks_loan else None,
        },
    )
    loan_lines = []
    if loan_trace.status.startswith("success") and isinstance(loan_trace.output, dict):
        for loan in loan_trace.output.get("matches", [])[:4]:
            rate = loan.get("effective_rate_with_subvention_percent") or loan.get("interest_rate_percent")
            docs = ", ".join(loan.get("documents") or [])
            line = (
                f"{loan['name']}: interest {loan.get('interest_rate_percent')}%"
                + (f", about {rate}% with interest subvention" if loan.get("effective_rate_with_subvention_percent") else "")
                + f", up to ₹{loan.get('max_amount_inr') or 'varies'}"
                + f", repayment {loan.get('repayment_period')}"
                + f", collateral {loan.get('collateral')}"
                + f". Eligibility: {loan.get('eligibility')}"
                + f". Apply at: {loan.get('where_to_apply')}"
                + (f". Documents: {docs}" if docs else "")
                + f". Available through banks that serve {context.location or 'this farm'}; confirm the current rate at the branch."
            )
            loan_lines.append(line)
            evidence.append(EvidenceItem(source=f"loan:{loan['id']}", value=line, unit="loan", agent="finance"))

    scheme_trace = tool_registry.execute(
        agent="finance",
        tool="search_schemes",
        arguments={"query": question, "category": None, "crop": context.crop, "state": None},
    )
    scheme_lines = []
    if scheme_trace.status.startswith("success") and isinstance(scheme_trace.output, dict):
        for s in scheme_trace.output.get("matches", [])[:5]:
            line = f"{s['name']}: {s['benefit']}"
            scheme_lines.append(line)
            evidence.append(
                EvidenceItem(source=f"scheme:{s['id']}", value=line, unit="scheme", agent="finance")
            )

    harvest_note = ""
    if harvest_estimate:
        h = harvest_estimate
        harvest_note = (
            f"\nIndicative harvest-related costs for {h['display_name']} ({h['area_acres']} acres): "
            f"labor INR {round(h['per_acre']['labor_cost'] * h['area_acres'])}, "
            f"equipment INR {round(h['per_acre']['equipment_cost'] * h['area_acres'])}, "
            f"transport INR {round(h['per_acre']['transport_cost'] * h['area_acres'])}, "
            f"total INR {h['total_farm']} ({h['note']})."
        )

    if scheme_focused or asks_loan:
        loan_block = "\n".join(f"- {line}" for line in loan_lines) or "- No matching loan found in the curated list."
        draft = (
            f"Curated agricultural loans for this question:\n{loan_block}\n"
            f"Government schemes matching your query:\n"
            f"{chr(10).join(f'- {line}' for line in scheme_lines) or '- No matching schemes found in knowledge base.'}"
            f"{harvest_note}\n"
            f"Use these records in the answer. Do not say loan information is missing when a loan is listed above. "
            f"Apply through a scheduled commercial bank, cooperative bank, regional rural bank, or the District Horticulture Officer. "
            f"Exact subsidy percent varies by state and farmer category — verify locally before applying."
        )
        confidence = 0.75 if loan_lines or scheme_lines or harvest_estimate else 0.35
    else:
        budget_note = (
            f"Budget available: INR {context.budget}."
            if context.budget is not None
            else "Budget not provided in farm context."
        )
        draft = (
            f"Estimated revenue INR {profit.get('revenue')}, total cost INR {profit.get('total_cost')}, "
            f"profit INR {profit.get('profit')}, break-even INR {profit.get('break_even_price')}/kg. "
            f"{budget_note}\n"
            f"Loans available: {'; '.join(loan_lines) or 'none matched'}.\n"
            f"Schemes: {'; '.join(scheme_lines) or 'none matched'}."
            f"{harvest_note}\n"
            f"Prefer lower-cost treatment or early sale if profit after full treatment is weak "
            f"and prices are soft."
        )
        confidence = 0.75 if profit else 0.45

    draft = apply_guidance(
        "finance",
        question,
        draft,
        evidence,
        tools_empty=not loan_lines,
        always_if_strong=True,
    )
    recommendation = enrich_with_llm("finance", context, query, draft, evidence)
    return AgentResult(
        agent="finance",
        recommendation=recommendation,
        confidence=confidence,
        tool_evidence=evidence,
        citations=citations,
    )
