"""Evidence and safety validator for agent drafts."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.models import AgentResult, EvidenceItem, FarmContext, ToolTrace


UNSAFE_PESTICIDE_PATTERNS = [
    r"\bddl\b",
    r"\bendosulfan\b",
    r"\bmonocrotophos\b",
    r"spray\s+\d+\s*ml\b",  # invented precise doses without citation
]


def _has_numeric_evidence(evidence: list[EvidenceItem]) -> bool:
    for e in evidence:
        if isinstance(e.value, (int, float)):
            return True
        if isinstance(e.value, dict) and any(isinstance(v, (int, float)) for v in e.value.values()):
            return True
    return False


def missing_farm_fields(context: FarmContext, agents_used: list[str]) -> list[str]:
    missing: list[str] = []
    if not context.location:
        missing.append("location")
    if context.farm_area_acres is None:
        missing.append("farm_area_acres")
    if "market" in agents_used or "finance" in agents_used:
        if not context.crop:
            missing.append("crop")
    if "finance" in agents_used and context.budget is None:
        missing.append("budget")
    if "soil" in agents_used and not context.soil_type and not context.soil_npk:
        missing.append("soil_type_or_soil_npk")
    return missing


def validate_draft(
    *,
    context: FarmContext,
    agent_results: list[AgentResult],
    tool_traces: list[ToolTrace],
    draft_text: str,
) -> dict[str, Any]:
    warnings: list[str] = []
    agents_used = [a.agent for a in agent_results]
    missing = missing_farm_fields(context, agents_used)

    all_evidence: list[EvidenceItem] = []
    for ar in agent_results:
        all_evidence.extend(ar.tool_evidence)

    # Numeric claims in draft should have tool evidence
    if re.search(r"\b\d+(\.\d+)?\b", draft_text) and not _has_numeric_evidence(all_evidence):
        warnings.append("Draft contains numbers without tool/RAG numeric evidence.")

    # Block unsafe pesticide escalation without knowledge citations
    has_rag = any(e.source.startswith("rag:") for e in all_evidence)
    lowered = draft_text.lower()
    for pattern in UNSAFE_PESTICIDE_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            if not has_rag:
                warnings.append(f"Unsafe or underspecified pesticide language matched '{pattern}' without RAG evidence.")
            else:
                warnings.append(f"Pesticide-related claim needs agronomist confirmation ({pattern}).")

    failed_tools = [t for t in tool_traces if t.status in ("error", "invalid_args")]
    if failed_tools:
        warnings.append(f"{len(failed_tools)} tool call(s) failed; treat related claims as uncertain.")

    mock_sources = [t for t in tool_traces if isinstance(t.output, dict) and t.output.get("is_mock")]
    if mock_sources:
        warnings.append("Some weather/market values are from labeled mock services, not live APIs.")

    # Critique strengths/weaknesses for revise loop
    critique_parts = []
    if missing:
        critique_parts.append(f"Missing context: {', '.join(missing)}.")
    if warnings:
        critique_parts.append("Warnings: " + " ".join(warnings))
    if not agent_results:
        critique_parts.append("No specialist agents produced results.")
    low_conf = [a.agent for a in agent_results if a.confidence < 0.45]
    if low_conf:
        critique_parts.append(f"Low confidence agents: {', '.join(low_conf)}.")

    ok = not any("Unsafe or underspecified" in w for w in warnings)
    return {
        "ok": ok,
        "warnings": warnings,
        "missing_context": missing,
        "critique": " ".join(critique_parts) if critique_parts else "Draft looks evidence-aligned.",
        "evidence": all_evidence,
    }
