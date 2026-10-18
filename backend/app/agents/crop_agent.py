from app.agents.base import enrich_with_llm, evidence_from_trace, run_knowledge
from app.schemas.models import AgentResult, EvidenceItem, FarmContext, ImageDiagnosisResult
from app.tools.registry import tool_registry
from app.vision.diagnosis import is_image_diagnosis_unconfirmed


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

    if image_diagnosis and is_image_diagnosis_unconfirmed(image_diagnosis):
        reason = (
            image_diagnosis.rejection_reason
            or "Image screening cannot reliably establish crop identity or disease."
        )
        safe_rec = (
            f"Image screening status: Unconfirmed.\n"
            f"Reason: {reason}\n"
            f"Safe non-chemical next steps:\n"
            f"1. Clearer photography: Photograph a single, fully visible leaf centered against a plain neutral background in bright natural daylight.\n"
            f"2. Physical inspection: Check the underside of leaves and stems for visible pests, mites, or wilting.\n"
            f"3. Field sanitation: Avoid overhead irrigation; isolate affected foliage if practical; do not apply chemical fungicides or pesticides without confirmed diagnosis.\n"
            f"Referral: Consult your nearest Krishi Vigyan Kendra (KVK) or a qualified agricultural extension officer for physical leaf diagnosis."
        )
        return AgentResult(
            agent="crop_health",
            recommendation=safe_rec,
            confidence=0.40,
            tool_evidence=evidence,
            citations=citations,
        )

    if image_diagnosis and image_diagnosis.status in ("ok", "accepted"):
        plant_display = (
            image_diagnosis.plant_name
            or (image_diagnosis.crop_id.capitalize() if image_diagnosis.crop_id else crop)
        )
        if image_diagnosis.is_healthy or (image_diagnosis.disease and image_diagnosis.disease.lower() == "healthy"):
            # Healthy leaf workflow
            disease_display = "Healthy"
            conf_val = (
                image_diagnosis.confidence
                if image_diagnosis.confidence is not None
                else (image_diagnosis.disease_confidence if image_diagnosis.disease_confidence is not None else 0.85)
            )
            conf_str = f"{conf_val:.2f} (uncalibrated)"
            evidence, citations = run_knowledge(
                "crop_health",
                f"{plant_display} preventive care cultural crop management",
                image_diagnosis.crop_id or context.crop,
            )
            evidence.append(
                EvidenceItem(
                    source="vision_diagnosis",
                    value=f"{plant_display}: No supported disease detected (Healthy leaf scan, confidence={conf_str})",
                    unit="mobilenetv3_diagnosis",
                    agent="crop_health",
                )
            )
            draft = (
                f"Image analysis for {plant_display}: Healthy leaf scan. "
                f"The visual model evaluated the leaf and did not detect visible symptoms of any of its 17 supported diseases "
                f"(confidence {conf_str}).\n"
                f"Important distinction: This is an AI preliminary model scan, not a guaranteed disease-free certification. "
                f"Emerging pathogens, root/vascular infections, or unsupported disorders may not be visible on a single leaf.\n"
                f"Preventive care: Maintain adequate plant spacing for airflow, adopt drip irrigation to keep foliage dry, "
                f"and follow balanced nutrition. Do not apply disease-specific chemical fungicides or bactericides.\n"
                f"Hints: {'; '.join(image_diagnosis.treatment_hints) if image_diagnosis.treatment_hints else 'Maintain regular visual crop scouting'}.\n"
                f"Growth stage: {stage}. Citations: {', '.join(citations) or 'none'}."
            )
            confidence = 0.82
        else:
            # Diseased leaf workflow
            disease_display = (
                image_diagnosis.predicted_disease
                or (image_diagnosis.disease.replace('_', ' ').title() if image_diagnosis.disease else "Unknown disease")
            )
            evidence, citations = run_knowledge(
                "crop_health",
                f"{plant_display} {disease_display} symptoms causes management",
                image_diagnosis.crop_id or context.crop,
            )
            conf_val = image_diagnosis.confidence if image_diagnosis.confidence is not None else image_diagnosis.disease_confidence
            conf_str = f"{conf_val:.2f} (uncalibrated)" if conf_val is not None else "uncalibrated"
            evidence.append(
                EvidenceItem(
                    source="vision_diagnosis",
                    value=f"{plant_display}: {disease_display} (confidence={conf_str}, model={image_diagnosis.model_version or 'screening_v1'})",
                    unit="vision_diagnosis",
                    agent="crop_health",
                )
            )
            ttrace = tool_registry.execute(
                agent="crop_health",
                tool="estimate_treatment_cost",
                arguments={
                    "crop": image_diagnosis.crop_id or crop,
                    "disease": image_diagnosis.disease or disease_display.lower().replace(" ", "_"),
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
                f"Image diagnosis for {plant_display}: {disease_display} "
                f"(model confidence {conf_str}, severity {image_diagnosis.severity or 'moderate'}). "
                f"Note: This is an automated AI visual prediction from {image_diagnosis.model_version or 'screening model'}, not a certified agronomist diagnosis. Physical leaf confirmation is advised before chemical application.\n"
                f"{treatment_note}\n"
                f"Symptoms & Causes: Inspect leaves for characteristic lesions, spots, or blighting favored by foliage moisture.\n"
                f"Next Steps & Management: Implement integrated pest management (IPM) starting with field sanitation, removing infected leaves, avoiding overhead irrigation, and applying recommended treatments as cited.\n"
                f"Hints: {'; '.join(image_diagnosis.treatment_hints)}.\n"
                f"Growth stage: {stage}. Citations: {', '.join(citations) or 'none'}."
            )
            confidence = 0.82
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
