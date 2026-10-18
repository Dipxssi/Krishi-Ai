import base64
import io
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from PIL import Image

from app.agents.crop_agent import crop_health_agent
from app.agents.equipment_agent import equipment_agent
from app.agents.finance_agent import finance_agent
from app.agents.knowledge_agent import knowledge_retriever_agent
from app.agents.market_agent import market_agent
from app.agents.soil_agent import soil_agent
from app.agents.weather_agent import weather_agent
from app.core.config import get_settings
from app.orchestrator.router import infer_risk_level, route_query
from app.schemas.models import (
    AgentResult,
    DecisionScore,
    EvidenceItem,
    FarmContext,
    ImageDiagnosisResult,
    QueryResponse,
    StructuredRecommendation,
)
from app.services import llm
from app.services.audit import new_request_id, save_query_run
from app.services.conflict_resolver import resolve_conflicts
from app.services.crop_registry import build_profit_inputs, extract_crop_from_text, normalize_crop_name
from app.services.validator import validate_draft
from app.tools.agriculture import (
    calculate_profit,
    default_today,
    estimate_decision_score,
    get_market_price,
    get_weather,
    register_all_tools,
)
import re
from app.tools.registry import tool_registry
from app.vision.diagnosis import diagnose_image_bytes, is_image_diagnosis_unconfirmed

AGENT_RUNNERS: dict[str, Callable[..., AgentResult]] = {
    "finance": finance_agent,
    "market": market_agent,
    "weather": weather_agent,
    "crop_health": crop_health_agent,
    "equipment": equipment_agent,
    "soil": soil_agent,
    "knowledge_retriever": knowledge_retriever_agent,
}

_tools_registered = False


def _ensure_tools() -> None:
    global _tools_registered
    if not _tools_registered:
        register_all_tools(tool_registry)
        _tools_registered = True


def _run_agents_parallel(
    selected: list[str],
    query: str,
    context: FarmContext,
    image_diagnosis: ImageDiagnosisResult | None,
) -> list[AgentResult]:
    results: list[AgentResult] = []

    def _run(name: str) -> AgentResult | None:
        runner = AGENT_RUNNERS.get(name)
        if not runner:
            return None
        if name == "crop_health" and image_diagnosis is not None:
            return runner(query, context, image_diagnosis=image_diagnosis)
        return runner(query, context)

    with ThreadPoolExecutor(max_workers=min(6, len(selected))) as pool:
        futures = {pool.submit(_run, name): name for name in selected}
        for fut in as_completed(futures):
            ar = fut.result()
            if ar:
                results.append(ar)
    order = {a: i for i, a in enumerate(selected)}
    results.sort(key=lambda r: order.get(r.agent, 99))
    return results


def _build_draft(agent_results: list[AgentResult]) -> str:
    parts = []
    for ar in agent_results:
        parts.append(f"[{ar.agent} | conf={ar.confidence:.2f}] {ar.recommendation}")
    return "\n\n".join(parts)


def _compute_decision_score(
    context: FarmContext,
    evidence: list[EvidenceItem],
    query: str,
    image_diagnosis: ImageDiagnosisResult | None = None,
) -> DecisionScore | None:
    rainfall = None
    current_price = None
    profit_val = None
    cost_val = None
    for e in evidence:
        if e.unit == "mm rainfall" and isinstance(e.value, (int, float)):
            rainfall = float(e.value)
        if e.unit and "INR/kg" in e.unit and isinstance(e.value, (int, float)):
            current_price = float(e.value)
        if e.unit == "INR profit" and isinstance(e.value, (int, float)):
            profit_val = float(e.value)
        if e.unit == "INR cost" and isinstance(e.value, (int, float)):
            cost_val = float(e.value)

    location = context.location
    crop = context.crop or "tomato"
    if rainfall is None and location:
        w = get_weather(location, 7)
        rainfall = float(w["rainfall_mm"])
    if current_price is None and location:
        m = get_market_price(crop, location, default_today())
        current_price = float(m["current_price"])
    if profit_val is None:
        profit_args = build_profit_inputs(
            crop,
            area_acres=context.farm_area_acres,
            selling_price=current_price or 30,
            irrigation_available=context.irrigation_available,
            budget=context.budget,
        )
        p = calculate_profit(
            area=profit_args["area"],
            expected_yield=profit_args["expected_yield"],
            selling_price=profit_args["selling_price"],
            seed_cost=profit_args["seed_cost"],
            fertilizer_cost=profit_args["fertilizer_cost"],
            pesticide_cost=profit_args["pesticide_cost"],
            labor_cost=profit_args["labor_cost"],
            irrigation_cost=profit_args["irrigation_cost"],
            equipment_cost=profit_args["equipment_cost"],
            transport_cost=profit_args["transport_cost"],
        )
        profit_val = float(p["profit"])
        cost_val = float(p["total_cost"])

UNSAFE_CHEMICAL_PATTERNS = [
    r"\bmancozeb\b",
    r"\bcopper[\s\-]oxychloride\b",
    r"\bcopper[\s\-]based\b",
    r"\bchlorothalonil\b",
    r"\bazoxystrobin\b",
    r"\bcarbendazim\b",
    r"\bpropiconazole\b",
    r"\btebuconazole\b",
    r"\bmetalaxyl\b",
    r"\bridomil\b",
    r"\bstreptocycline\b",
    r"\bimidacloprid\b",
    r"\bcypermethrin\b",
    r"\bmonocrotophos\b",
    r"\bendosulfan\b",
    r"\bfungicide[s]?\b",
    r"\bbactericide[s]?\b",
    r"\bchemical\s+spray[s]?\b",
    r"\bfoliar\s+spray\b",
    r"\bearly\s+blight\b",
    r"\blate\s+blight\b",
    r"\bbacterial\s+speck\b",
    r"\bseptoria\b",
    r"\d+(?:\.\d+)?\s*(?:g|gm|gram|ml|l|kg|litres?|liters?)\s*(?:per|\/)\s*(?:l|liter|litre|acre|ha|hectare|pump)",
    r"\bspray\s+\d+",
    r"\bspray\s+schedule\b",
    r"\bapplication\s+rate\b",
    r"\bapply\s+at\s+\d+",
    r"\bapply\s+(?:mancozeb|copper|fungicide|pesticide)",
]


def _scrub_unsafe_chemical_advice(text: str) -> str:
    cleaned_lines = []
    for line in text.splitlines():
        if any(re.search(pat, line, re.IGNORECASE) for pat in UNSAFE_CHEMICAL_PATTERNS):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _build_unconfirmed_image_response(
    image_diagnosis: ImageDiagnosisResult,
    agent_results: list[AgentResult],
) -> str:
    reason = (
        image_diagnosis.rejection_reason
        or "Image screening cannot reliably establish crop identity or disease."
    )
    sections = [
        "### Image Diagnosis: Unconfirmed",
        "- **Status**: Unconfirmed",
        f"- **Reason**: {reason}",
        "- **Safe Non-Chemical Next Steps**:",
        "  1. **Clearer photography**: Photograph a single, fully visible leaf centered against a plain neutral background in bright natural daylight.",
        "  2. **Physical inspection**: Inspect the underside of leaves and stems for visible pests, mites, or wilting.",
        "  3. **Field sanitation**: Avoid overhead irrigation; isolate visibly affected plants if practical; do not apply chemical fungicides or pesticides without confirmed diagnosis.",
        "- **Referral**: Consult your nearest Krishi Vigyan Kendra (KVK) or a qualified agricultural extension officer for physical leaf diagnosis.",
    ]

    non_crop_advisories = []
    for ar in agent_results:
        if ar.agent != "crop_health" and ar.recommendation:
            cleaned = _scrub_unsafe_chemical_advice(ar.recommendation)
            if cleaned:
                agent_title = ar.agent.replace("_", " ").capitalize()
                non_crop_advisories.append(f"**{agent_title} Advisory**:\n{cleaned}")

    if non_crop_advisories:
        sections.append("\n### Farm Management Advisory")
        sections.extend(non_crop_advisories)

    return "\n".join(sections)


def _compute_decision_score(
    context: FarmContext,
    evidence: list[EvidenceItem],
    query: str,
    image_diagnosis: ImageDiagnosisResult | None = None,
) -> DecisionScore | None:
    rainfall = None
    current_price = None
    profit_val = None
    cost_val = None
    for e in evidence:
        if e.unit == "mm rainfall" and isinstance(e.value, (int, float)):
            rainfall = float(e.value)
        if e.unit and "INR/kg" in e.unit and isinstance(e.value, (int, float)):
            current_price = float(e.value)
        if e.unit == "INR profit" and isinstance(e.value, (int, float)):
            profit_val = float(e.value)
        if e.unit == "INR cost" and isinstance(e.value, (int, float)):
            cost_val = float(e.value)

    location = context.location
    crop = context.crop or "tomato"
    if rainfall is None and location:
        w = get_weather(location, 7)
        rainfall = float(w["rainfall_mm"])
    if current_price is None and location:
        m = get_market_price(crop, location, default_today())
        current_price = float(m["current_price"])
    if profit_val is None:
        profit_args = build_profit_inputs(
            crop,
            area_acres=context.farm_area_acres,
            selling_price=current_price or 30,
            irrigation_available=context.irrigation_available,
            budget=context.budget,
        )
        p = calculate_profit(
            area=profit_args["area"],
            expected_yield=profit_args["expected_yield"],
            selling_price=profit_args["selling_price"],
            seed_cost=profit_args["seed_cost"],
            fertilizer_cost=profit_args["fertilizer_cost"],
            pesticide_cost=profit_args["pesticide_cost"],
            labor_cost=profit_args["labor_cost"],
            irrigation_cost=profit_args["irrigation_cost"],
            equipment_cost=profit_args["equipment_cost"],
            transport_cost=profit_args["transport_cost"],
        )
        profit_val = float(p["profit"])
        cost_val = float(p["total_cost"])

    water_risk = min(1.0, (rainfall or 0) / 40.0)

    # Heuristic disease risk calculation
    if image_diagnosis is not None:
        if is_image_diagnosis_unconfirmed(image_diagnosis):
            disease_risk = None  # Suppress when unconfirmed — do not invent uncalibrated probability
        elif image_diagnosis.is_healthy or (image_diagnosis.disease and image_diagnosis.disease.lower() == "healthy"):
            disease_risk = 0.10
        elif image_diagnosis.disease and image_diagnosis.disease != "healthy":
            disease_risk = 0.65
        else:
            disease_risk = 0.20
    else:
        disease_risk = 0.55 if any(k in query.lower() for k in ("spot", "disease", "blight", "pest")) else 0.30

    agronomic = 0.7
    if context.irrigation_available:
        agronomic += 0.05
    if context.soil_type:
        agronomic += 0.05
    agronomic = min(1.0, agronomic)

    raw = estimate_decision_score(
        agronomic_suitability=agronomic,
        expected_profit=profit_val or 0,
        water_risk=water_risk,
        disease_risk=disease_risk,
        input_cost=cost_val or 0,
    )
    return DecisionScore(**raw)


def _revise(
    draft: str,
    critique: str,
    evidence: list[EvidenceItem],
    context: FarmContext,
    query: str,
    image_unconfirmed: bool = False,
    image_diagnosis: ImageDiagnosisResult | None = None,
) -> str:
    evidence_lines = "\n".join(f"- {e.source}: {e.value} {e.unit or ''}" for e in evidence)
    safety_rule = ""
    if image_unconfirmed:
        safety_rule = (
            "\nCRITICAL SAFETY CONSTRAINT: Leaf image diagnosis is UNCONFIRMED. "
            "Under NO circumstances name chemical fungicides, bactericides, pesticides, brand names, dosages, "
            "application rates, spray schedules, or unconfirmed disease labels. "
            "Limit crop health advice strictly to safe non-chemical cultural practices, clearer photography, "
            "and referral to a local extension specialist.\n"
        )
    elif image_diagnosis and image_diagnosis.status in ("ok", "accepted"):
        plant_lbl = image_diagnosis.plant_name or (image_diagnosis.crop_id.capitalize() if image_diagnosis.crop_id else "Plant")
        conf_val = (
            image_diagnosis.confidence
            if image_diagnosis.confidence is not None
            else (image_diagnosis.disease_confidence if image_diagnosis.disease_confidence is not None else 0.85)
        )
        conf_lbl = f"{conf_val:.2f}"
        if image_diagnosis.is_healthy or (image_diagnosis.disease and image_diagnosis.disease.lower() == "healthy"):
            safety_rule = (
                f"\nVISION PREDICTION CONSTRAINT: MobileNetV3 visual classification evaluated {plant_lbl} and detected NO supported disease symptoms (Healthy leaf scan, uncalibrated confidence={conf_lbl}). "
                "State clearly that this is an AI preliminary model scan, not a guaranteed disease-free certification. "
                "Provide preventive cultural care only. Under NO circumstances prescribe disease-specific chemical fungicides, bactericides, or treatments for diseases not detected.\n"
            )
        else:
            dis_lbl = image_diagnosis.predicted_disease or (image_diagnosis.disease.replace('_', ' ').title() if image_diagnosis.disease else "condition")
            safety_rule = (
                f"\nVISION PREDICTION CONSTRAINT: MobileNetV3 visual classification identified {plant_lbl} with {dis_lbl} (uncalibrated confidence={conf_lbl}). "
                "DO NOT independently invent a different disease label or override the vision model. "
                "Explain potential causes, symptoms, and appropriate next steps using retrieved evidence. "
                "Clearly state that this is an AI prediction and advise physical agronomist leaf confirmation before chemical applications.\n"
            )

    template = (
        f"Query: {query}\n"
        f"Farm: {context.model_dump()}\n"
        f"Evidence:\n{evidence_lines}\n"
        f"Draft:\n{draft}\n"
        f"Critique:\n{critique}\n{safety_rule}\n"
        "Produce a revised final recommendation for the farmer: treat vs continue vs sell early if relevant. "
        "Cite only evidence above. Label forecasts as forecasts. Be concise."
    )
    if llm.is_llm_available():
        text = llm.generate(
            template,
            system="You are the KrishiAi orchestrator. Revise using evidence only. Max clarity for farmers. Never prescribe unconfirmed chemical sprays.",
        )
        if text:
            return text
    return (
        f"Revised recommendation based on specialist outputs and critique.\n"
        f"Critique addressed: {critique}\n\n{draft}\n\n"
        f"Evidence count: {len(evidence)}. Update missing farm context fields before high-stakes actions."
    )


def _clarifying_preface(missing: list[str]) -> str:
    if not missing:
        return ""
    labels = {
        "location": "farm location",
        "crop": "current/planned crop",
        "budget": "available budget (INR)",
        "farm_area_acres": "farm area in acres",
        "soil_type_or_soil_npk": "soil type or NPK values",
    }
    pretty = [labels.get(m, m) for m in missing]
    return (
        "Before acting on high-stakes advice, please update FarmContext with: "
        + ", ".join(pretty)
        + ".\n\n"
    )


def _build_structured(
    final: str,
    agent_results: list[AgentResult],
    validation: dict,
    conflict_notes: list[str],
    decision: DecisionScore | None,
    image_diagnosis: ImageDiagnosisResult | None,
    query: str,
) -> StructuredRecommendation:
    sources = []
    for e in validation["evidence"]:
        sources.append(e.source)
    for ar in agent_results:
        sources.extend(ar.citations)
    
    is_unconfirmed = bool(image_diagnosis and is_image_diagnosis_unconfirmed(image_diagnosis))
    human_review = bool(validation["missing_context"]) or is_unconfirmed or bool(
        image_diagnosis and image_diagnosis.requires_expert
    )
    if any("Unsafe" in w for w in validation["warnings"]):
        human_review = True
    financial = None
    if decision:
        financial = {
            "expected_profit_inr": decision.expected_profit,
            "input_cost_inr": decision.input_cost,
            "water_risk": decision.water_risk,
            "disease_risk": decision.disease_risk,
        }
    reasons = conflict_notes[:5]
    for ar in agent_results:
        if ar.confidence >= 0.6:
            reasons.append(f"{ar.agent}: high-confidence specialist input")

    if is_unconfirmed:
        action_summary = "Image diagnosis unconfirmed — follow safe non-chemical leaf inspection and seek extension review before applying treatments."
    else:
        action_summary = final.split("\n")[0][:500]

    return StructuredRecommendation(
        action_summary=action_summary,
        reasons=reasons[:8],
        financial_summary=financial,
        sources=list(dict.fromkeys(sources))[:20],
        human_review_required=human_review,
        risk_level=infer_risk_level(query),
        conflicts_resolved=conflict_notes,
    )


logger = logging.getLogger("krishiai.pipeline")


def handle_query(
    query: str,
    context: FarmContext,
    *,
    image_base64: str | None = None,
    selected_crop: str | None = None,
    request_id: str | None = None,
    persist: bool = True,
    vision_model: str | None = None,
) -> QueryResponse:
    _ensure_tools()
    req_id = request_id or new_request_id()
    tool_registry.reset(farmer_id=context.farmer_id)
    settings = get_settings()

    farm_profile_crop = normalize_crop_name(context.crop)
    user_selected_crop = normalize_crop_name(selected_crop)
    if not user_selected_crop:
        user_selected_crop = extract_crop_from_text(query)

    effective_crop = user_selected_crop or farm_profile_crop

    image_supplied = bool(image_base64 and str(image_base64).strip())
    image_decoded = False
    vision_function = None
    inference_mechanism = None
    image_diagnosis: ImageDiagnosisResult | None = None

    chosen_vision_model = vision_model or settings.vision_model

    if image_supplied:
        try:
            raw = str(image_base64).split(",", 1)[-1]
            data = base64.b64decode(raw)
            Image.open(io.BytesIO(data))
            image_decoded = True
        except Exception:
            image_decoded = False

        crop_hint = user_selected_crop
        if chosen_vision_model == "mobilenetv3":
            vision_function = "diagnose_image_with_mobilenetv3"
            inference_mechanism = "mobilenetv3_plantdisease_best"
            try:
                from app.vision.mobilenetv3_service import diagnose_image_with_mobilenetv3
                image_diagnosis = diagnose_image_with_mobilenetv3(
                    image_base64,
                    crop_hint=crop_hint,
                    confidence_threshold=settings.vision_confidence_threshold,
                )
            except Exception as exc:
                logger.warning("MobileNetV3 diagnosis failed, falling back to heuristic: %s", exc)
                vision_function = "diagnose_image_bytes"
                inference_mechanism = "color_ratio_heuristic_v1"
                image_diagnosis = diagnose_image_bytes(image_base64, crop_hint=crop_hint)
        else:
            vision_function = "diagnose_image_bytes"
            inference_mechanism = "color_ratio_heuristic_v1"
            image_diagnosis = diagnose_image_bytes(image_base64, crop_hint=crop_hint)

    # If image diagnosis was accepted, determine predicted crop without letting farm profile override
    predicted_image_crop = (
        normalize_crop_name(image_diagnosis.crop_id)
        if image_diagnosis and image_diagnosis.status in ("ok", "accepted")
        else None
    )
    if predicted_image_crop and not user_selected_crop:
        effective_crop = predicted_image_crop

    final_screening_status = image_diagnosis.status if image_diagnosis else None
    abstention_reason = image_diagnosis.rejection_reason if image_diagnosis else None

    # Safe structured diagnostic logging (no base64 or credentials)
    logger.info(
        "Request diagnostic: request_id=%s, image_supplied=%s, image_decoded=%s, "
        "vision_function=%s, inference_mechanism=%s, farm_profile_crop=%s, "
        "user_selected_crop=%s, final_screening_status=%s, abstention_reason=%s",
        req_id,
        image_supplied,
        image_decoded,
        vision_function,
        inference_mechanism,
        farm_profile_crop,
        user_selected_crop or effective_crop,
        final_screening_status,
        abstention_reason,
        extra={
            "request_id": req_id,
            "image_supplied": image_supplied,
            "image_decoded": image_decoded,
            "vision_function": vision_function,
            "inference_mechanism": inference_mechanism,
            "farm_profile_crop": farm_profile_crop,
            "user_selected_crop": user_selected_crop or effective_crop,
            "final_screening_status": final_screening_status,
            "abstention_reason": abstention_reason,
        },
    )

    # Effective farm context for specialist agents
    effective_context = context.model_copy()
    if effective_crop:
        effective_context.crop = effective_crop

    selected, _scores = route_query(query, has_image=image_supplied)
    if "knowledge_retriever" not in selected and len(selected) >= 2:
        selected = [*selected, "knowledge_retriever"]

    agent_results = _run_agents_parallel(selected, query, effective_context, image_diagnosis)

    draft = _build_draft(agent_results)
    revision_count = 0
    validation = validate_draft(
        context=effective_context,
        agent_results=agent_results,
        tool_traces=tool_registry.traces,
        draft_text=draft,
        image_diagnosis=image_diagnosis,
    )

    mismatch_note = None
    if effective_crop and farm_profile_crop and effective_crop != farm_profile_crop:
        mismatch_note = (
            f"Crop context difference: Stored farm profile is set to '{farm_profile_crop}', "
            f"but this inquiry and image are evaluated for '{effective_crop.capitalize()}'. "
            f"Update your farm profile if you have transitioned crops."
        )
        if mismatch_note not in validation["warnings"]:
            validation["warnings"].append(mismatch_note)

    final = draft
    is_unconfirmed_image = bool(image_supplied and is_image_diagnosis_unconfirmed(image_diagnosis))

    while revision_count < settings.max_revisions:
        final = _revise(
            final,
            validation["critique"],
            validation["evidence"],
            effective_context,
            query,
            image_unconfirmed=is_unconfirmed_image,
            image_diagnosis=image_diagnosis,
        )
        revision_count += 1
        validation = validate_draft(
            context=effective_context,
            agent_results=agent_results,
            tool_traces=tool_registry.traces,
            draft_text=final,
            image_diagnosis=image_diagnosis,
        )
        if mismatch_note and mismatch_note not in validation["warnings"]:
            validation["warnings"].append(mismatch_note)
        if validation["ok"] and not validation["missing_context"] and revision_count >= 1:
            break

    conflict_notes, _ = resolve_conflicts(agent_results, validation["evidence"])
    if conflict_notes and not is_unconfirmed_image:
        final = final + "\n\nConflict resolution:\n" + "\n".join(f"- {n}" for n in conflict_notes)

    # Authoritative Final Response Boundary
    if is_unconfirmed_image and image_diagnosis:
        final = _build_unconfirmed_image_response(image_diagnosis, agent_results)
        agent_results = [
            ar.model_copy(update={"recommendation": _scrub_unsafe_chemical_advice(ar.recommendation)})
            for ar in agent_results
        ]
    elif mismatch_note:
        # Prepend clear crop confirmation prompt when farm profile conflicts with evaluated crop
        crop_conflict_header = (
            f"**Note on Crop Identity**: Your registered farm profile crop is **{farm_profile_crop.capitalize()}**, "
            f"while leaf analysis evaluated **{effective_crop.capitalize()}**. "
            f"Please verify your current crop before applying interventions.\n\n"
        )
        if not final.startswith("**Note on Crop Identity**"):
            final = crop_conflict_header + final

    decision = _compute_decision_score(effective_context, validation["evidence"], query, image_diagnosis)
    confidences = [a.confidence for a in agent_results]
    confidence = sum(confidences) / len(confidences) if confidences else 0.0

    if validation["missing_context"] and not is_unconfirmed_image:
        confidence = min(confidence, 0.4)
        final = _clarifying_preface(validation["missing_context"]) + final

    structured = _build_structured(
        final, agent_results, validation, conflict_notes, decision, image_diagnosis, query
    )

    response = QueryResponse(
        request_id=req_id,
        query=query,
        farmer_id=context.farmer_id,
        selected_crop=user_selected_crop or predicted_image_crop,
        farm_profile_crop=farm_profile_crop,
        final_recommendation=final,
        structured_recommendation=structured,
        image_diagnosis=image_diagnosis,
        decision_score=decision,
        agents_used=selected,
        confidence=round(confidence, 3),
        evidence=validation["evidence"],
        tool_traces=tool_registry.traces,
        warnings=validation["warnings"],
        missing_context=validation["missing_context"],
        revision_count=revision_count,
        agent_results=agent_results,
    )
    if persist:
        save_query_run(req_id, context.farmer_id, query, response)
    return response
