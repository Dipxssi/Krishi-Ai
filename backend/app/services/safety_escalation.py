"""Deterministic safety and risk escalation layer for KrishiAI.

Escalates to qualified local agricultural experts (KVK / Extension Officers)
strictly when justified by risk, uncertainty, or high-impact decisions,
without unnecessarily escalating ordinary farming questions.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.models import AgentResult, FarmContext, ImageDiagnosisResult
from app.services.multilingual import get_ui_text, normalize_language_code
from app.vision.diagnosis import is_image_diagnosis_unconfirmed

# High-threat pathogens and rapid-damage indicators
_SEVERE_DISEASE_PATTERNS = [
    r"\blate\s+blight\b",
    r"\bbacterial\s+(?:wilt|speck|canker)\b",
    r"\byellow\s+leaf\s+curl\b",
    r"\bto?mv|tomato\s+mosaic\b",
    r"\bpanama\s+disease\b",
    r"\bstem\s+rot\b",
    r"\broot\s+rot\b",
    r"\bsevere\s+(?:blight|infestation|rot|wilt)\b",
    r"\brapidly\s+spreading\b",
    r"\bentire\s+crop\s+(?:drying|dying|yellowing)\b",
    r"ತೀವ್ರವಾಗಿ\s+ಹರಡ",
    r"ಗಿಡಗಳು\s+ಒಣಗ",
    r"ರೋಗ.*ತೀವ್ರ",
    r"ಗಂಭೀರ.*ರೋಗ",
    r"गंभीर.*रोग",
    r"फसल.*सूख",
    r"तेजी\s+से\s+फैल",
]

# Chemical mixing, dosages, and restricted pesticide indicators
_HIGH_IMPACT_CHEMICAL_PATTERNS = [
    r"\bpesticide\s+(?:dose|dosage|ratio|mix|mixing|rate)\b",
    r"\bfungicide\s+(?:dose|dosage|ratio|mix|mixing|rate)\b",
    r"\bmix(?:ing)?\s+(?:chemicals?|pesticides?|insecticides?)\b",
    r"\bpre[\s\-]harvest\s+interval\b",
    r"\bapplication\s+rate\b",
    r"\bhow\s+many\s+(?:ml|grams?|gm)\s+per\s+liter\b",
    r"\bmancozeb\b",
    r"\bcopper\s+oxychloride\b",
    r"\bmonocrotophos\b",
    r"\bendosulfan\b",
    r"\bchlorothalonil\b",
    r"\bcarbendazim\b",
    r"\bstreptocycline\b",
    r"कीटनाशक.*(?:खुराक|मात्रा|घोल|छिड़काव|दवा|मिला)",
    r"फफूंदनाशक.*(?:खुराक|मात्रा|छिड़काव|मिला)",
    r"औषधी.*(?:प्रमाण|मात्रा|घोल|छिड़काव)",
    r"ಔಷಧಿ.*(?:ಪ್ರಮಾಣ|ಸಿಂಪಡಣೆ|ಮಿಶ್ರಣ|ಡೋಸ್)",
    r"ಕೀಟನಾಶಕ.*(?:ಪ್ರಮಾಣ|ಮಿಶ್ರಣ|ಸಿಂಪಡಣೆ|ಡೋಸ್)",
]


class EscalationDetails:
    def __init__(
        self,
        requires_escalation: bool,
        urgency: str,  # "high" | "medium" | "low"
        reason: str,
        safe_next_step: str,
        sample_instructions: str,
        action_label: str,
    ):
        self.requires_escalation = requires_escalation
        self.urgency = urgency
        self.reason = reason
        self.safe_next_step = safe_next_step
        self.sample_instructions = sample_instructions
        self.action_label = action_label

    def to_dict(self) -> dict[str, Any]:
        return {
            "requires_escalation": self.requires_escalation,
            "urgency": self.urgency,
            "reason": self.reason,
            "safe_next_step": self.safe_next_step,
            "sample_instructions": self.sample_instructions,
            "action_label": self.action_label,
        }


def evaluate_escalation(
    *,
    query: str,
    context: FarmContext,
    image_diagnosis: ImageDiagnosisResult | None = None,
    agent_results: list[AgentResult] | None = None,
    warnings: list[str] | None = None,
    missing_context: list[str] | None = None,
    language: str = "en",
) -> EscalationDetails:
    """Evaluate whether the farmer's query requires escalation to a local expert."""
    lang = normalize_language_code(language)
    q = query.lower()
    warns = warnings or []
    missing = missing_context or []
    results = agent_results or []

    action_label = get_ui_text("find_expert_button", lang)
    default_sample = get_ui_text("sample_instructions", lang)

    # 1. Unconfirmed or Rejected Image Diagnosis
    if image_diagnosis and is_image_diagnosis_unconfirmed(image_diagnosis):
        if lang == "hi":
            reason = "पत्ती की तस्वीर स्पष्ट न होने के कारण सटीक रोग की पुष्टि नहीं हो सकी।"
            safe_step = "किसी भी रासायनिक दवा का छिड़काव न करें। प्रभावित पत्तियों को अलग करें और दिन की धूप में साफ तस्वीर लें।"
        elif lang == "kn":
            reason = "ಫೋಟೋದ ಗುಣಮಟ್ಟ ಅಥವಾ ಲಕ್ಷಣಗಳು ಸ್ಪಷ್ಟವಾಗಿಲ್ಲದ ಕಾರಣ ಕಾಯಿಲೆಯನ್ನು ಖಚಿತಪಡಿಸಲು ಸಾಧ್ಯವಾಗಿಲ್ಲ."
            safe_step = "ಯಾವುದೇ ರಾಸಾಯನಿಕ ಸಿಂಪಡಿಸಬೇಡಿ. ಬಾಧಿತ ಎಲೆಗಳನ್ನು ಪ್ರತ್ಯೇಕಿಸಿ, ನೈಸರ್ಗಿಕ ಬೆಳಕಿನಲ್ಲಿ ಸ್ಪಷ್ಟ ಫೋಟೋ ತೆಗೆದುಕೊಳ್ಳಿ."
        else:
            reason = "The leaf image could not be diagnosed with certainty from the photo alone."
            safe_step = "Do not apply chemical sprays. Isolate severely affected foliage and water at the base."

        return EscalationDetails(
            requires_escalation=True,
            urgency="medium",
            reason=reason,
            safe_next_step=safe_step,
            sample_instructions=default_sample,
            action_label=action_label,
        )

    # 2. Image Diagnosis explicitly requires expert confirmation
    if image_diagnosis and image_diagnosis.requires_expert:
        if lang == "hi":
            reason = "लक्षण किसी गंभीर फसल रोग के संकेत दे रहे हैं जिसकी भौतिक पुष्टि आवश्यक है।"
            safe_step = "रोग को फैलने से रोकने के लिए खेत में स्वच्छता बनाए रखें और तुरंत विशेषज्ञ की राय लें।"
        elif lang == "kn":
            reason = "ರೋಗದ ಲಕ್ಷಣಗಳು ತೀವ್ರವಾಗಿದ್ದು, ಸ್ಥಳದಲ್ಲೇ ಪರಿಶೀಲಿಸಿ ಖಚಿತಪಡಿಸಿಕೊಳ್ಳುವುದು ಅಗತ್ಯವಾಗಿದೆ."
            safe_step = "ರೋಗ ಹರಡುವುದನ್ನು ತಡೆಯಲು ಜಮೀನಿನಲ್ಲಿ ನೈರ್ಮಲ್ಯ ಕಾಪಾಡಿ ಮತ್ತು ತಕ್ಷಣ ತಜ್ಞರ ಸಲಹೆ ಪಡೆಯಿರಿ."
        else:
            reason = "Visual symptoms suggest a condition requiring physical agronomic confirmation before treatment."
            safe_step = "Maintain field sanitation, avoid overhead watering, and confirm with an agronomist before spraying."

        return EscalationDetails(
            requires_escalation=True,
            urgency="high",
            reason=reason,
            safe_next_step=safe_step,
            sample_instructions=default_sample,
            action_label=action_label,
        )

    # 3. Chemical Doses, Mixing, or High-Impact Pesticide Inquiries
    is_chemical_query = any(re.search(pat, q, re.IGNORECASE) for pat in _HIGH_IMPACT_CHEMICAL_PATTERNS)
    if is_chemical_query:
        if lang == "hi":
            reason = "दवाओं के रासायनिक मिश्रण और सटीक खुराक के लिए स्थानीय फसल स्थिति और लेबल की पुष्टि आवश्यक है।"
            safe_step = "गलत खुराक से फसल जलने या विषाक्तता का खतरा रहता है। केवल अधिकृत कृषि अधिकारी की देखरेख में खुराक तय करें।"
            sample = "कीटनाशक का डिब्बा और प्रभावित पौधे का ताज़ा नमूना लेकर कृषि सेवा केंद्र या केवीके जाएं।"
        elif lang == "kn":
            reason = "ರಾಸಾಯನಿಕಗಳ ಮಿಶ್ರಣ ಮತ್ತು ನಿಖರ ಪ್ರಮಾಣವನ್ನು ನಿರ್ಧರಿಸಲು ಬೆಳೆಯ ಪ್ರಸ್ತುತ ಸ್ಥಿತಿಯ ಪರಿಶೀಲನೆ ಅತ್ಯಗತ್ಯ."
            safe_step = "ತಪ್ಪಾದ ಪ್ರಮಾಣದಿಂದ ಬೆಳೆ ಹಾಳಾಗುವ ಅಪಾಯವಿದೆ. ಕೃಷಿ ಅಧಿಕಾರಿಯ ಮಾರ್ಗದರ್ಶನವಿಲ್ಲದೆ ರಾಸಾಯನಿಕಗಳನ್ನು ಮಿಶ್ರಣ ಮಾಡಬೇಡಿ."
            sample = "ಔಷಧಿಯ ಬಾಟಲಿ/ಪ್ಯಾಕೆಟ್ ಮತ್ತು ಬಾಧಿತ ಗಿಡದ ತಾಜಾ ಎಲೆಯನ್ನು ಕೃಷಿ ತಜ್ಞರ ಬಳಿಗೆ ಕೊಂಡೊಯ್ಯಿರಿ."
        else:
            reason = "Pesticide dosages, chemical mixtures, and pre-harvest intervals require verified local product confirmation to avoid crop burn or toxicity."
            safe_step = "Avoid guessing chemical mixing ratios. Use non-chemical cultural sanitation first and follow certified label directions."
            sample = "Take the product package and an affected crop sample to your nearest Block Agriculture Officer or KVK."

        return EscalationDetails(
            requires_escalation=True,
            urgency="high",
            reason=reason,
            safe_next_step=safe_step,
            sample_instructions=sample,
            action_label=action_label,
        )

    # 4. Severe, rapid-spreading crop disease / damage indicators
    is_severe_disease = any(re.search(pat, q, re.IGNORECASE) for pat in _SEVERE_DISEASE_PATTERNS)
    if is_severe_disease:
        if lang == "hi":
            reason = "लक्षण तेजी से फैलने वाले गंभीर रोग के संकेत देते हैं जिससे फसल का बड़ा नुकसान हो सकता है।"
            safe_step = "संक्रमित पौधों को खेत से बाहर निकालकर नष्ट करें और तुरंत निकटतम कृषि विज्ञान केंद्र (KVK) से संपर्क करें।"
        elif lang == "kn":
            reason = "ರೋಗವು ವೇಗವಾಗಿ ಹರಡುವ ಸಾಧ್ಯತೆಯಿದ್ದು, ಇಳುವರಿ ನಷ್ಟವನ್ನು ತಡೆಯಲು ತಕ್ಷಣದ ಕ್ರಮ ಅಗತ್ಯ."
            safe_step = "ಸೋಂಕಿತ ಗಿಡಗಳನ್ನು ಜಮೀನಿನಿಂದ ಹೊರತೆಗೆದು ನಾಶಪಡಿಸಿ, ತಕ್ಷಣ ಹತ್ತಿರದ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರವನ್ನು ಭೇಟಿ ಮಾಡಿ."
        else:
            reason = "Symptoms suggest a severe or rapidly spreading pathogen that could jeopardize harvest yield without timely intervention."
            safe_step = "Rogue out severely diseased plants, avoid moving through wet foliage, and obtain verified physical diagnosis immediately."

        return EscalationDetails(
            requires_escalation=True,
            urgency="high",
            reason=reason,
            safe_next_step=safe_step,
            sample_instructions=default_sample,
            action_label=action_label,
        )

    # 5. Conflicting advice / treat-vs-sell dilemma with high risk
    has_treat_sell_conflict = any("treat-vs-sell" in w.lower() for w in warns)
    if has_treat_sell_conflict:
        if lang == "hi":
            reason = "फसल को दवा देकर बचाने की लागत और तुरंत मंडी में बेचने के लाभ में आर्थिक टकराव है।"
            safe_step = "महंगे स्प्रे करने से पहले मंडी भाव और उपचार खर्च का आकलन करें।"
        elif lang == "kn":
            reason = "ಔಷಧಿ ಸಿಂಪಡಣೆಯ ವೆಚ್ಚ ಮತ್ತು ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ ತಕ್ಷಣ ಮಾರಾಟ ಮಾಡುವ ನಡುವೆ ನಿರ್ಧಾರ ಕೈಗೊಳ್ಳಬೇಕಿದೆ."
            safe_step = "ದುಬಾರಿ ಔಷಧಿ ಸಿಂಪಡಿಸುವ ಮೊದಲು ಮಾರುಕಟ್ಟೆ ಧಾರಣೆ ಹಾಗೂ ಖರ್ಚನ್ನು ತಜ್ಞರೊಂದಿಗೆ ಚರ್ಚಿಸಿ."
        else:
            reason = "Agronomic treatment expense conflicts with falling market realization or short shelf-life."
            safe_step = "Compare expected chemical treatment cost against current mandi price before committing to high expenditure."

        return EscalationDetails(
            requires_escalation=True,
            urgency="medium",
            reason=reason,
            safe_next_step=safe_step,
            sample_instructions=default_sample,
            action_label=action_label,
        )

    # No high-stakes escalation needed for ordinary farming questions
    return EscalationDetails(
        requires_escalation=False,
        urgency="low",
        reason="",
        safe_next_step="",
        sample_instructions="",
        action_label="",
    )
