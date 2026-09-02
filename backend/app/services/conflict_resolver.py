"""Resolve contradictions between specialist agent outputs (Phase 4)."""

from __future__ import annotations

from app.schemas.models import AgentResult, EvidenceItem


def resolve_conflicts(agent_results: list[AgentResult], evidence: list[EvidenceItem]) -> tuple[list[str], list[str]]:
    """
    Return (resolved_notes, warnings) when agents disagree on sell vs treat, irrigation, etc.
    """
    notes: list[str] = []
    warnings: list[str] = []

    texts = {ar.agent: ar.recommendation.lower() for ar in agent_results}

    market_sell = "market" in texts and any(w in texts["market"] for w in ("sell early", "sell now", "harvest soon"))
    finance_weak = "finance" in texts and any(w in texts["finance"] for w in ("weak profit", "loss", "negative"))
    weather_rain = "weather" in texts and any(w in texts["weather"] for w in ("rain", "heavy rainfall", "storm"))
    crop_spray = "crop_health" in texts and any(w in texts["crop_health"] for w in ("spray", "pesticide", "fungicide"))

    if weather_rain and crop_spray:
        notes.append("Rain forecast conflicts with immediate spray — prefer cultural controls or spray after rain window.")
        warnings.append("weather_vs_spray_conflict")

    if market_sell and finance_weak:
        notes.append("Market softness aligns with weak economics — early sale may reduce loss if storage costs are high.")

    if market_sell and crop_spray and not weather_rain:
        notes.append("Treat vs sell trade-off: compare treatment cost to expected price recovery before spraying.")

    irrigation_on = any("irrigation" in t and "increase" in t for t in texts.values())
    weather_dry = "weather" in texts and any(w in texts["weather"] for w in ("drought", "dry", "low rainfall"))
    if irrigation_on and weather_dry:
        notes.append("Dry forecast supports irrigation plan from soil/crop guidance.")

    return notes, warnings
