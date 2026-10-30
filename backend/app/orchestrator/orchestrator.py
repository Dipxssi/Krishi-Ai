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
    EscalationDetailsSchema,
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
from app.services.nearby_help import append_nearby_kvk_office
from app.services.multilingual import (
    detect_language,
    get_disclaimer,
    get_ui_text,
    normalize_indic_script,
    normalize_language_code,
)
from app.services.safety_escalation import evaluate_escalation
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


def _clean_internal_metadata(text: str) -> str:
    """Strip bracketed agent tags, conf scores, raw citation IDs, and internal traces."""
    if not text:
        return ""
    # Strip [agent | conf=0.XX]
    text = re.sub(r"(?m)^\[[a-z_]+ \| conf=[0-9.]+\]\s*", "", text)
    text = re.sub(r"\[[a-z_]+ \| conf=[0-9.]+\]", "", text)
    # Strip raw citation markers e.g. "Citations: crop_registry: crop_registry, ..."
    text = re.sub(r"(?i)\bcitations?:\s*[^.\n]+(\.|\n|$)", "", text)
    text = re.sub(r"(?i)\bretrieved guidance:\s*[^.\n]+(\.|\n|$)", "", text)
    # Strip raw json filenames
    text = re.sub(r"rag:[a-z0-9_.-]+", "", text)
    text = re.sub(r"\bconf=[0-9.]+\b", "", text)
    # Clean up double punctuation or empty lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


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
    language: str = "en",
) -> str:
    lang = normalize_language_code(language)
    reason = (
        image_diagnosis.rejection_reason
        or "Image screening cannot reliably establish crop identity or disease."
    )
    if lang == "hi":
        sections = [
            "### Image Diagnosis: Unconfirmed (पत्ती फोटो निदान: व्यक्तिगत पुष्टि आवश्यक)",
            "- **स्थिति (Status)**: Unconfirmed (अपुष्ट)",
            f"- **कारण (Reason)**: {reason}",
            "- **Safe Non-Chemical Next Steps (सुरक्षित गैर-रासायनिक कदम)**:",
            "  1. **स्पष्ट फोटो**: प्राकृतिक दिन के उजाले में एक साफ पृष्ठभूमि पर पूरी पत्ती की स्पष्ट फोटो लें।",
            "  2. **निरीक्षण**: पत्ती के नीचे और तने पर कीट या फफूंद के लक्षणों की जांच करें।",
            "  3. **सावधानी**: ऊपर से पानी देने से बचें; बिना विशेषज्ञ पुष्टि के कोई रासायनिक कीटनाशक या फंगिसाइड न डालें।",
            "- **Referral (विशेषज्ञ परामर्श)**: सटीक पुष्टि के लिए अपने नजदीकी कृषि विज्ञान केंद्र (KVK) या ब्लॉक कृषि अधिकारी से संपर्क करें।",
        ]
    elif lang == "kn":
        sections = [
            "### Image Diagnosis: Unconfirmed (ಎಲೆಯ ಫೋಟೋ ಪರಿಶೀಲನೆ: ತಜ್ಞರ ದೃಢೀಕರಣ ಅಗತ್ಯ)",
            "- **ಸ್ಥಿತಿ (Status)**: Unconfirmed (ದೃಢಪಟ್ಟಿಲ್ಲ)",
            f"- **ಕಾರಣ (Reason)**: {reason}",
            "- **Safe Non-Chemical Next Steps (ಸುರಕ್ಷಿತ ಕೃಷಿ ಕ್ರಮಗಳು)**:",
            "  1. **ಸ್ಪಷ್ಟ ಫೋಟೋ**: ನೈಸರ್ಗಿಕ ಬೆಳಕಿನಲ್ಲಿ ಸ್ಪಷ್ಟ ಹಿನ್ನೆಲೆಯಲ್ಲಿ ಸಂಪೂರ್ಣ ಎಲೆಯ ಫೋಟೋ ತೆಗೆದುಕೊಳ್ಳಿ.",
            "  2. **ಪರಿಶೀಲನೆ**: ಎಲೆಯ ಕೆಳಭಾಗ ಮತ್ತು ಕಾಂಡದಲ್ಲಿ ಕೀಟ ಅಥವಾ ಶಿಲೀಂಧ್ರ ಲಕ್ಷಣಗಳನ್ನು ಪರೀಕ್ಷಿಸಿ.",
            "  3. **ಮುನ್ನೆಚ್ಚರಿಕೆ**: ಗಿಡದ ಮೇಲಿನಿಂದ ನೀರುಣಿಸುವುದನ್ನು ತಪ್ಪಿಸಿ; ತಜ್ಞರ ಸಲಹೆಯಿಲ್ಲದೆ ರಾಸಾಯನಿಕ ಔಷಧ ಸಿಂಪಡಿಸಬೇಡಿ.",
            "- **Referral (ಸಲಹೆ)**: ಖಚಿತ ರೋಗ ನಿರ್ಣಯಕ್ಕಾಗಿ ನಿಮ್ಮ ಹತ್ತಿರದ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ (ಕೆ.ವಿ.ಕೆ) ಅಥವಾ ಕೃಷಿ ಅಧಿಕಾರಿಯನ್ನು ಭೇಟಿ ಮಾಡಿ.",
        ]
    else:
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
            cleaned = _clean_internal_metadata(_scrub_unsafe_chemical_advice(ar.recommendation))
            if cleaned:
                agent_title = ar.agent.replace("_", " ").capitalize()
                non_crop_advisories.append(f"**{agent_title} Advisory**:\n{cleaned}")

    if non_crop_advisories:
        advisory_title = "### Farm Management Advisory"
        sections.append(f"\n{advisory_title}")
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
    language: str = "en",
) -> str:
    lang = normalize_language_code(language)
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
                f"\nVISION PREDICTION CONSTRAINT: Visual classification evaluated {plant_lbl} and detected no supported disease symptoms. "
                "State warmly that the leaf scan indicates healthy growth, but remind the farmer that this is a preliminary AI scan. "
                "Provide preventive cultural care only. Under NO circumstances prescribe disease-specific chemical fungicides, bactericides, or treatments for diseases not detected.\n"
            )
        else:
            dis_lbl = image_diagnosis.predicted_disease or (image_diagnosis.disease.replace('_', ' ').title() if image_diagnosis.disease else "condition")
            safety_rule = (
                f"\nVISION PREDICTION CONSTRAINT: Visual classification identified {plant_lbl} symptoms that may be consistent with {dis_lbl}. "
                f"Communicate uncertainty naturally (e.g. 'Your {plant_lbl} leaves show signs that may be consistent with {dis_lbl}. A closer in-person inspection can help confirm the cause.'). "
                "DO NOT independently invent a different disease label. "
                "Explain potential causes, symptoms, and appropriate next steps using retrieved evidence. "
                "Advise physical agronomist leaf confirmation before any chemical applications.\n"
            )

    lang_name = {
        "kn": "Kannada (ಕನ್ನಡ script)",
        "hi": "Hindi (हिंदी Devanagari script)",
        "en": "English",
    }.get(lang, "English")

    system_prompt = (
        f"You are KrishiAI, a compassionate, practical, and highly trusted agricultural advisor for Indian farmers. "
        f"You MUST write your entire response in natural, fluent {lang_name}. "
        f"CRITICAL MANDATE: If the target language is {lang_name}, you MUST NOT answer in English. Every heading, explanation, and bullet point must be strictly written in {lang_name}. "
        "Speak warmly and directly to the farmer. Explain concepts in simple, everyday language without technical jargon. "
        "NEVER expose internal metadata: no 'conf=0.85', no confidence numbers, no agent names (like crop_health, market), "
        "no model names (like MobileNetV3 or ElasticNet), and no raw citation strings (like rag:crops.json or crop_registry:). "
        "Structure your response clearly: "
        "1. Friendly, direct answer explaining the crop condition or question simply. "
        "2. What the farmer should do next (practical action steps). "
        "3. Important precautions or preventive measures. "
        "4. If and only if the situation involves high risk, uncertainty, or chemical decisions, advise visiting a local KVK or extension officer. "
        "Keep all advice strictly grounded in the provided evidence. Never invent unverified chemical sprays or pesticide doses."
    )

    clean_draft = _clean_internal_metadata(draft)
    template = (
        f"Farmer Query: {query}\n"
        f"Farm Location & Context: {context.location or 'India'}, Crop: {context.crop or 'Crop'}, Area: {context.farm_area_acres} acres\n"
        f"Verified Evidence:\n{evidence_lines}\n"
        f"Specialist Findings Summary:\n{clean_draft}\n"
        f"Critique / Quality Feedback:\n{critique}\n{safety_rule}\n"
        f"Produce a revised final recommendation for the farmer strictly in {lang_name}. "
        f"Cite only evidence above. Label forecasts as forecasts. Be concise, warm, and helpful. "
        f"REMINDER: The entire response must be written in {lang_name}."
    )
    if llm.is_llm_available():
        text = llm.generate(
            template,
            system=system_prompt,
        )
        if text:
            return _clean_internal_metadata(text)

    # Keep the no-LLM fallback farmer-facing: the agent labels and critique are
    # orchestration metadata, not part of the answer. Preserve specialist text
    # without adding unsupported conclusions or figures.
    recommendation_text = _clean_internal_metadata(draft)
    if recommendation_text:
        if lang in ("kn", "hi"):
            from app.services.multilingual import format_fallback_in_language
            return format_fallback_in_language(recommendation_text, lang, context=context)
        return recommendation_text
    return (
        "ನನ್ನ ಬಳಿ ಲಭ್ಯವಿರುವ ಮಾಹಿತಿಯಿಂದ ವಿಶ್ವಾಸಾರ್ಹ ಶಿಫಾರಸು ತಯಾರಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ."
        if lang == "kn"
        else "उपलब्ध जानकारी के आधार पर विश्वसनीय सलाह तैयार नहीं की जा सकी।"
        if lang == "hi"
        else "I could not prepare a reliable recommendation from the available specialist information."
    )


def _clarifying_preface(missing: list[str], language: str = "en") -> str:
    if not missing:
        return ""
    lang = normalize_language_code(language)
    if lang == "hi":
        labels = {
            "location": "खेत का स्थान",
            "crop": "वर्तमान/नियोजित फसल",
            "budget": "उपलब्ध बजट (रुपये)",
            "farm_area_acres": "खेत का क्षेत्रफल (एकड़)",
            "soil_type_or_soil_npk": "मिट्टी का प्रकार या NPK मान",
        }
        pretty = [labels.get(m, m) for m in missing]
        return "सटीक और प्रभावी सलाह के लिए कृपया प्रोफ़ाइल में यह जानकारी जोड़ें: " + ", ".join(pretty) + "।\n\n"
    elif lang == "kn":
        labels = {
            "location": "ಜಮೀನಿನ ಸ್ಥಳ",
            "crop": "ಬೆಳೆ",
            "budget": "ಬಜೆಟ್ (ರೂ)",
            "farm_area_acres": "ಜಮೀನಿನ ವಿಸ್ತೀರ್ಣ (ಎಕರೆ)",
            "soil_type_or_soil_npk": "ಮಣ್ಣಿನ ವಿವರ ಅಥವಾ NPK",
        }
        pretty = [labels.get(m, m) for m in missing]
        return "ಹೆಚ್ಚು ನಿಖರ ಸಲಹೆಗಾಗಿ ದಯವಿಟ್ಟು ಈ ವಿವರಗಳನ್ನು ನಮೂದಿಸಿ: " + ", ".join(pretty) + ".\n\n"
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


def _is_general_tomato_growth_query(query: str, *, has_image: bool) -> bool:
    if has_image:
        return False
    q = query.lower()
    asks_growth = re.search(
        r"\b(grow|growth|growing|cultivat(?:e|ing|ion))\b|विकास|पैदावार|बढ़ोतरी|बढ़ाना|खेती|ಉತ್ತಮ\s+ಬೆಳವಣಿಗೆ|ಬೆಳವಣಿಗೆ|ಇಳುವರಿ|ಕೃಷಿ|ಬೆಳೆಯ|ಬೆಳೆಸು",
        q,
    )
    mentions_tomato = re.search(r"\btomato(?:es)?\b|टमाटर|ಟೊಮ್ಯಾಟೊ|ಟೊಮೆಟೊ", q)
    asks_other_specific_advice = re.search(
        r"\b(disease|diseased|blight|wilt|wilting|yellow(?:ing)?|spots?|pests?|insects?|diagnos\w*|"
        r"budget|loan|costs?|revenue|profit|subsid(?:y|ies)|market price)\b|बीमारी|रोग|कीट|ರೋಗ|ಕೀಟ|ಹುಳು|ಔಷಧ|ಬೆಲೆ",
        q,
    )
    return bool(asks_growth and mentions_tomato and not asks_other_specific_advice)


def _tomato_growth_answer(language: str = "en") -> str:
    lang = normalize_language_code(language)
    if lang == "hi":
        return (
            "टमाटर की अच्छी पैदावार और स्वस्थ विकास के लिए ये व्यावहारिक उपाय अपनाएं:\n\n"
            "1. **धूप (Sunlight):** टमाटर को प्रतिदिन 6-8 घंटे की सीधी धूप की आवश्यकता होती है।\n"
            "2. **सिंचाई (Watering):** मिट्टी में हल्की नमी बनाए रखें; पौधों की जड़ के पास पानी दें, पत्तियों पर नहीं।\n"
            "3. **मिट्टी और जल निकासी (Soil and drainage):** भुरभुरी, उपजाऊ और अच्छी जल निकासी वाली दोमट मिट्टी सबसे उपयुक्त है।\n"
            "4. **उर्वरक (Fertilizer):** मिट्टी की जांच के आधार पर संतुलित पोषण दें; अत्यधिक नाइट्रोजन से बचें ताकि फूल और फल अच्छे आएं।\n"
            "5. **दूरी (Spacing):** पौधों के बीच उचित दूरी रखें ताकि हवा का आवागमन बना रहे और बीमारियां न फैलें।\n"
            "6. **सहारा (Support):** पौधों को बढ़ने पर डंडे या तार से सहारा दें ताकि फल जमीन को न छुएं।\n"
            "7. **कीट निगरानी (Pest monitoring):** पत्तियों के नीचे नियमित रूप से कीटों की जांच करें; बिना आवश्यकता कीटनाशक का प्रयोग न करें।\n\n"
            "अपनी मिट्टी और क्षेत्र के अनुसार विशिष्ट सलाह के लिए अपनी जानकारी फार्म प्रोफ़ाइल में दर्ज करें।"
        )
    elif lang == "kn":
        return (
            "ಟೊಮ್ಯಾಟೊ ಗಿಡಗಳ ಉತ್ತಮ ಬೆಳವಣಿಗೆ ಮತ್ತು ಅಧಿಕ ಇಳುವರಿಗಾಗಿ ಈ ಕೆಳಗಿನ ಕ್ರಮಗಳನ್ನು ಅನುಸರಿಸಿ:\n\n"
            "1. **ಸೂರ್ಯನ ಬೆಳಕು (Sunlight):** ಗಿಡಗಳಿಗೆ ಪ್ರತಿದಿನ ಸಾಕಷ್ಟು ನೇರ ಸೂರ್ಯನ ಬೆಳಕು ಸಿಗುವಂತೆ ನೋಡಿಕೊಳ್ಳಿ.\n"
            "2. **ನೀರುಣಿಸುವಿಕೆ (Watering):** ಮಣ್ಣಿನಲ್ಲಿ ಹದವಾದ ತೇವಾಂಶವಿರಲಿ; ಗಿಡದ ಬುಡಕ್ಕೆ ನೀರುಣಿಸಿ, ಎಲೆಗಳ ಮೇಲೆ ನೀರು ಚೆಲ್ಲಬೇಡಿ.\n"
            "3. **ಮಣ್ಣು ಮತ್ತು ಒಳಚರಂಡಿ (Soil and drainage):** ನೀರು ಸರಾಗವಾಗಿ ಹರಿದುಹೋಗುವ ಫಲವತ್ತಾದ ಮಣ್ಣು ಅತ್ಯುತ್ತಮ.\n"
            "4. **ಪೋಷಕಾಂಶ/ಗೊಬ್ಬರ (Fertilizer):** ಮಣ್ಣು ಪರೀಕ್ಷೆ ಆಧಾರದ ಮೇಲೆ ಸಮತೋಲಿತ ಗೊಬ್ಬರ ನೀಡಿ; ಕೇವಲ ಎಲೆಗಳ ಬೆಳವಣಿಗೆ ತಡೆಯಲು ಅತಿಯಾದ ಸಾರಜನಕ ಬಳಸಬೇಡಿ.\n"
            "5. **ಅಂತರ (Spacing):** ಗಾಳಿಯಾಡುವಿಕೆ ಮತ್ತು ಬಿಸಿಲಿಗಾಗಿ ಗಿಡಗಳ ನಡುವೆ ಸೂಕ್ತ ಅಂತರ ಕಾಪಾಡಿ.\n"
            "6. **ಆಸರೆ ನೀಡುವುದು (Support):** ಗಿಡಗಳು ಬೆಳೆಯುತ್ತಿದ್ದಂತೆ ಕೋಲು ಅಥವಾ ತಂತಿಯ ಆಸರೆ ನೀಡಿ.\n"
            "7. **ಕೀಟಗಳ ನಿಗಾ (Pest monitoring):** ಎಲೆಗಳ ಕೆಳಭಾಗವನ್ನು ನಿಯಮಿತವಾಗಿ ಪರಿಶೀಲಿಸಿ; ದೃಢೀಕರಣವಿಲ್ಲದೆ ಕೀಟನಾಶಕ ಸಿಂಪಡಿಸಬೇಡಿ.\n\n"
            "ನಿಮ್ಮ ಜಮೀನಿನ ಮಣ್ಣಿಗೆ ತಕ್ಕಂತೆ ನಿರ್ದಿಷ್ಟ ಗೊಬ್ಬರದ ಸಲಹೆಗಾಗಿ ಪ್ರೊಫೈಲ್ ಮಾಹಿತಿ ನವೀಕರಿಸಿ."
        )
    return (
        "For tomato plants generally, these practices support healthy growth:\n\n"
        "1. **Sunlight:** Choose a spot with full sun; tomatoes grow best with several hours of direct light each day.\n"
        "2. **Watering:** Keep soil evenly moist, watering at the base when the surface begins to dry. Avoid frequent shallow watering and waterlogging.\n"
        "3. **Soil and drainage:** Use loose, fertile, well-drained soil. If growing in a container, make sure it has drainage holes.\n"
        "4. **Fertilizer:** Use soil-test guidance when available. Otherwise, follow the label on a balanced vegetable fertilizer and avoid excess nitrogen, which can encourage leafy growth at the expense of fruiting. Do not use a fixed dose without soil and product details.\n"
        "5. **Spacing:** Follow the seed or plant label for the variety, leaving enough room for airflow and access around each plant.\n"
        "6. **Support:** Add a stake or cage while plants are young and tie stems loosely as they grow.\n"
        "7. **Pest monitoring:** Regularly inspect the undersides of leaves, stems, and new growth. Identify a pest before choosing any treatment; avoid pesticide use without a confirmed need and label directions.\n\n"
        "For a tailored fertilizer plan, what growing setup are you using, and do you have a soil-test result?"
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
    language: str | None = None,
) -> QueryResponse:
    _ensure_tools()
    req_id = request_id or new_request_id()
    tool_registry.reset(farmer_id=context.farmer_id)
    settings = get_settings()

    query = normalize_indic_script(query)
    farm_profile_crop = normalize_crop_name(context.crop)
    user_selected_crop = normalize_crop_name(selected_crop)
    if not user_selected_crop:
        user_selected_crop = extract_crop_from_text(query)

    effective_crop = user_selected_crop or farm_profile_crop
    detected_lang = detect_language(query, fallback=language or context.preferred_language or "en")

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

        # Auto-detect: only pass an explicit UI crop to MobileNet. Do not force farm-profile
        # crop (that caused tomato-biased conflicts when the leaf was maize/potato).
        crop_hint = user_selected_crop
        if chosen_vision_model == "mobilenetv3":
            vision_function = "diagnose_image_with_mobilenetv3"
            inference_mechanism = (
                "mobilenetv3_hf_space"
                if settings.vision_inference_url
                else "mobilenetv3_plantdisease_best"
            )
            try:
                # remote_mobilenet prefers VISION_INFERENCE_URL (no torch on Free Render).
                from app.vision.remote_mobilenet import diagnose_image_with_mobilenetv3
                image_diagnosis = diagnose_image_with_mobilenetv3(
                    image_base64,
                    crop_hint=crop_hint,
                    confidence_threshold=settings.vision_confidence_threshold,
                )
                if (
                    image_diagnosis
                    and image_diagnosis.model_version
                    and "hf_space" in image_diagnosis.model_version
                ):
                    inference_mechanism = "mobilenetv3_hf_space"
            except Exception as exc:
                logger.warning("MobileNetV3 diagnosis failed, falling back to heuristic: %s", exc)
                vision_function = "diagnose_image_bytes"
                inference_mechanism = "color_ratio_heuristic_v1"
                image_diagnosis = diagnose_image_bytes(image_base64, crop_hint=crop_hint)
                image_diagnosis.rejection_reason = (
                    f"MobileNet Space was not used ({exc}). "
                    + (image_diagnosis.rejection_reason or "")
                )
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
            language=detected_lang,
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
        title = (
            "ವಿವಾದ ಇತ್ಯರ್ಥ" if detected_lang == "kn"
            else "विरोधाभास समाधान" if detected_lang == "hi"
            else "Conflict resolution"
        )
        final = final + f"\n\n{title}:\n" + "\n".join(f"- {n}" for n in conflict_notes)

    # Authoritative Final Response Boundary
    if is_unconfirmed_image and image_diagnosis:
        final = _build_unconfirmed_image_response(image_diagnosis, agent_results, language=detected_lang)
        agent_results = [
            ar.model_copy(update={"recommendation": _scrub_unsafe_chemical_advice(ar.recommendation)})
            for ar in agent_results
        ]
    elif mismatch_note:
        # Prepend clear crop confirmation prompt when farm profile conflicts with evaluated crop
        if detected_lang == "kn":
            crop_conflict_header = (
                f"**ಬೆಳೆ ವಿವರದ ಸೂಚನೆ**: ನಿಮ್ಮ ನೋಂದಾಯಿತ ಪ್ರೊಫೈಲ್ ಬೆಳೆ **{farm_profile_crop.capitalize()}**, "
                f"ಆದರೆ ಈ ಪರಿಶೀಲನೆ **{effective_crop.capitalize()}** ಗೆ ಸಂಬಂಧಿಸಿದೆ. "
                f"ದಯವಿಟ್ಟು ಯಾವುದೇ ಕ್ರಮ ಕೈಗೊಳ್ಳುವ ಮುನ್ನ ನಿಮ್ಮ ಬೆಳೆ ವಿವರವನ್ನು ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ.\n\n"
            )
        elif detected_lang == "hi":
            crop_conflict_header = (
                f"**फसल पहचान नोट**: आपकी प्रोफ़ाइल में दर्ज फसल **{farm_profile_crop.capitalize()}** है, "
                f"जबकि विश्लेषण **{effective_crop.capitalize()}** के लिए किया गया है। "
                f"उपचार लागू करने से पहले अपनी वर्तमान फसल की पुष्टि करें।\n\n"
            )
        else:
            crop_conflict_header = (
                f"**Note on Crop Identity**: Your registered farm profile crop is **{farm_profile_crop.capitalize()}**, "
                f"while leaf analysis evaluated **{effective_crop.capitalize()}**. "
                f"Please verify your current crop before applying interventions.\n\n"
            )
        if not (final.startswith("**Note on Crop Identity**") or final.startswith("**ಬೆಳೆ ವಿವರದ ಸೂಚನೆ**") or final.startswith("**फसल पहचान नोट**")):
            final = crop_conflict_header + final

    decision = _compute_decision_score(effective_context, validation["evidence"], query, image_diagnosis)
    confidences = [a.confidence for a in agent_results]
    confidence = sum(confidences) / len(confidences) if confidences else 0.0

    if validation["missing_context"] and not is_unconfirmed_image:
        confidence = min(confidence, 0.4)
        final = _clarifying_preface(validation["missing_context"], language=detected_lang) + final

    # Give a direct, safe answer for common tomato-care questions even when
    # retrieved passages or specialist drafts are off-topic. The specialists
    # still provide evidence and diagnostics; their internal draft is not the
    # user-facing answer for this general intent.
    if _is_general_tomato_growth_query(query, has_image=image_supplied):
        final = _tomato_growth_answer(language=detected_lang)

    # Ensure all internal metadata, trace labels, confidence tags, and raw citation markers are stripped
    final = _clean_internal_metadata(final)
    final = append_nearby_kvk_office(
        final,
        effective_context.location,
        detected_lang,
    )

    # Deterministic risk and escalation evaluation
    escalation_result = evaluate_escalation(
        query=query,
        context=effective_context,
        image_diagnosis=image_diagnosis,
        agent_results=agent_results,
        warnings=validation.get("warnings", []),
        missing_context=validation.get("missing_context", []),
        language=detected_lang,
    )
    escalation_schema = EscalationDetailsSchema(
        requires_escalation=escalation_result.requires_escalation,
        urgency=escalation_result.urgency,
        reason=escalation_result.reason,
        safe_next_step=escalation_result.safe_next_step,
        sample_instructions=escalation_result.sample_instructions,
        action_label=escalation_result.action_label,
    )

    disclaimer_text = get_disclaimer(detected_lang)

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
        response_language=detected_lang,
        disclaimer=disclaimer_text,
        escalation=escalation_schema,
    )
    if persist:
        save_query_run(req_id, context.farmer_id, query, response)
    return response

