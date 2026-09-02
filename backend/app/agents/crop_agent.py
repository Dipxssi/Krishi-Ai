from app.agents.base import enrich_with_llm, evidence_from_trace, run_knowledge
from app.schemas.models import AgentResult, EvidenceItem, FarmContext, ImageDiagnosisResult
from app.tools.registry import tool_registry


def crop_health_agent(
    query: str,
    context: FarmContext,
    *,
    image_diagnosis: ImageDiagnosisResult | None = None,
) -> AgentResult:
    evidence, citations = run_knowledge("crop_health", query, context.crop)
    crop = context.crop or "the crop"
    stage = context.growth_stage or "unknown stage"
    treatment_note = ""

    if image_diagnosis and image_diagnosis.status == "ok":
        evidence.append(
            EvidenceItem(
                source="vision_diagnosis",
                value=f"{image_diagnosis.crop_id}: {image_diagnosis.disease} ({image_diagnosis.severity})",
                unit="image diagnosis",
                agent="crop_health",
            )
        )
        if image_diagnosis.disease and image_diagnosis.disease != "healthy":
            ttrace = tool_registry.execute(
                agent="crop_health",
                tool="estimate_treatment_cost",
                arguments={
                    "crop": image_diagnosis.crop_id or crop,
                    "disease": image_diagnosis.disease,
                    "severity": image_diagnosis.severity or "moderate",
                    "area_acres": context.farm_area_acres,
                },
            )
            evidence.extend(evidence_from_trace("crop_health", ttrace))
            if ttrace.status.startswith("success") and isinstance(ttrace.output, dict):
                treatment_note = (
                    f" Indicative treatment cost INR {ttrace.output.get('total_treatment_cost_inr')} "
                    f"for {ttrace.output.get('disease')} ({ttrace.output.get('severity')})."
                )
        draft = (
            f"Image diagnosis for {image_diagnosis.crop_id}: {image_diagnosis.disease} "
            f"(confidence {image_diagnosis.disease_confidence}, severity {image_diagnosis.severity})."
            f"{treatment_note}\n"
            f"Hints: {'; '.join(image_diagnosis.treatment_hints)}.\n"
            f"Growth stage: {stage}. Citations: {', '.join(citations) or 'none'}."
        )
        confidence = 0.82 if not image_diagnosis.requires_expert else 0.55
    elif image_diagnosis and image_diagnosis.status == "rejected":
        draft = (
            f"Image could not be diagnosed: {image_diagnosis.rejection_reason}. "
            f"Text guidance for {crop} ({stage}): prioritize scouting and local extension advice. "
            f"Citations: {', '.join(citations) or 'none'}."
        )
        confidence = 0.45
    else:
        draft = (
            f"Text-only crop health for {crop} ({stage}). Upload a leaf photo for image diagnosis. "
            f"Based on retrieved guidance, prioritize cultural controls, avoid unnecessary sprays before rain, "
            f"and escalate to an agronomist if disease confidence is unclear. "
            f"Citations: {', '.join(citations) or 'none'}."
        )
        confidence = 0.55 if citations else 0.35

    recommendation = enrich_with_llm("crop_health", context, query, draft, evidence)
    return AgentResult(
        agent="crop_health",
        recommendation=recommendation,
        confidence=confidence,
        tool_evidence=evidence,
        citations=citations,
    )
