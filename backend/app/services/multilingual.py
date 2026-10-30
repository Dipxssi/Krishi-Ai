"""Multilingual support and language detection for KrishiAI.

Supports English (en), Hindi (hi), and Kannada (kn) end-to-end.
"""

from __future__ import annotations

import re

# Unicode ranges for Indian language scripts
_KANNADA_RE = re.compile(r"[\u0C80-\u0CFF]")
_TELUGU_RE = re.compile(r"[\u0C00-\u0C7F]")
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

_ROMANIZED_KANNADA_WORDS = {
    "nanna", "nimage", "bele", "belege", "beleya", "yava", "hege", "enu", "madabeku",
    "gobbra", "gobbara", "keeta", "keetada", "rooga", "roga", "rogakke", "neeru",
    "houshadhi", "aushadhi", "beku", "maduvudu", "marukatte", "krishi", "raita", "raitare",
    "gidake", "gidagalu", "gidagalige", "thumba", "tumba", "bandide", "hoge", "illa",
}

_ROMANIZED_HINDI_WORDS = {
    "kisan", "fasal", "kheti", "kaise", "kare", "karein", "kitna", "keeda", "keede",
    "paani", "khad", "upchar", "bimaari", "mandi", "bhav", "kya", "hai", "mujhe",
    "mere", "meri", "tamatar",
}


# whisper-large-v3-turbo often tags Hindi speech as Icelandic or a nearby Latin language
# and then writes phonetic garbage ("Ísum meõ kjá…") instead of Devanagari.
_HINDI_MISDETECT_LANGS = {"is", "fo", "cy", "nn", "nb", "sv", "da", "fi"}


def transcript_needs_hindi_retry(text: str, detected_language: str | None = None) -> bool:
    """True when a transcript is a Whisper language-ID miss, not real English or Indic text."""
    if not text or not text.strip():
        return False
    if _DEVANAGARI_RE.search(text) or _KANNADA_RE.search(text) or _TELUGU_RE.search(text):
        return False
    code = (detected_language or "").strip().lower().split("-", 1)[0]
    if code in _HINDI_MISDETECT_LANGS:
        return True
    letters = [char for char in text if char.isalpha()]
    if len(letters) < 12:
        return False
    marked = sum(1 for char in letters if ord(char) > 127)
    return marked / len(letters) >= 0.12


def indic_script_strength(text: str) -> tuple[str | None, int]:
    """Return ('hi'|'kn', char_count) when enough Indic script is present."""
    if not text:
        return None, 0
    hi = len(_DEVANAGARI_RE.findall(text))
    kn = len(_KANNADA_RE.findall(text))
    if hi >= 8 and hi >= kn:
        return "hi", hi
    if kn >= 8 and kn > hi:
        return "kn", kn
    return None, 0


def transcript_lacks_indic_script(text: str) -> bool:
    """True when Whisper returned Latin/English instead of Hindi/Kannada script."""
    lang, count = indic_script_strength(text)
    return lang is None or count < 8


def prefer_indic_transcript(primary: str, candidate: str) -> str:
    """Keep candidate when it has clear Indic script and primary does not."""
    if not candidate or not candidate.strip():
        return primary
    cand_lang, cand_n = indic_script_strength(candidate)
    prim_lang, prim_n = indic_script_strength(primary)
    if cand_lang and cand_n >= 8 and (prim_lang is None or cand_n > prim_n):
        return candidate
    return primary


def normalize_indic_script(text: str) -> str:
    """Normalize any Telugu Unicode characters that Whisper mixed into Kannada speech.

    Kannada (0x0C80-0x0CFF) and Telugu (0x0C00-0x0C7F) share aligned Unicode offsets (+0x80).
    When Whisper transcribes Kannada speech without a language hint, it frequently outputs
    mixed Kannada and Telugu code points. Shifting Telugu code points by +0x80 recovers
    clean, standard Kannada script.
    """
    if not text:
        return ""
    has_kannada = bool(_KANNADA_RE.search(text))
    has_telugu = bool(_TELUGU_RE.search(text))
    # If text has Telugu characters mixed with Kannada or common Kannada-speech transcribed words
    if has_telugu and (
        has_kannada
        or any(w in text for w in ("నాను", "నన్న", "యಾವ", "బయసు", "మత్తు", "సాధన", "అవు", "తోమ"))
    ):
        return "".join(chr(ord(c) + 0x80) if 0x0C00 <= ord(c) <= 0x0C7F else c for c in text)
    return text


def detect_language(text: str, fallback: str = "en") -> str:
    """Detect whether text is primarily Kannada, Hindi (Devanagari/Romanized), or English.
    
    If text contains Kannada script -> 'kn'
    If text contains Devanagari script -> 'hi'
    If text contains romanized Kannada/Hindi keywords -> 'kn' / 'hi'
    Otherwise falls back to provided fallback or 'en'.
    """
    if not text or not text.strip():
        return normalize_language_code(fallback)

    cleaned = normalize_indic_script(text)
    kannada_chars = len(_KANNADA_RE.findall(cleaned))
    hindi_chars = len(_DEVANAGARI_RE.findall(cleaned))

    if kannada_chars > 0 and kannada_chars >= hindi_chars:
        return "kn"
    if hindi_chars > 0 and hindi_chars > kannada_chars:
        return "hi"

    # Check for romanized / transliterated words in English script
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    kn_matches = len(tokens & _ROMANIZED_KANNADA_WORDS)
    hi_matches = len(tokens & _ROMANIZED_HINDI_WORDS)

    if kn_matches >= 1 and kn_matches >= hi_matches:
        return "kn"
    if hi_matches >= 1 and hi_matches > kn_matches:
        return "hi"

    # If no Indic script or markers found, check fallback
    normalized = normalize_language_code(fallback)
    return normalized if normalized in ("en", "hi", "kn") else "en"


def normalize_language_code(lang: str | None) -> str:
    """Normalize language names/codes (e.g. 'Kannada' -> 'kn', 'hi-IN' -> 'hi')."""
    if not lang:
        return "en"
    clean = lang.strip().lower()
    if clean.startswith("kn") or "kannada" in clean:
        return "kn"
    if clean.startswith("hi") or "hindi" in clean:
        return "hi"
    return "en"


def format_fallback_in_language(draft_text: str, language: str, context: object | None = None) -> str:
    """Format specialist findings in fluent Kannada or Hindi when LLM is unavailable."""
    lang = normalize_language_code(language)
    if lang == "en":
        return draft_text

    if lang == "kn":
        lines = [
            "ನಮಸ್ಕಾರ ರೈತ ಮಿತ್ರರೇ, ನಿಮ್ಮ ವಿಚಾರಣೆಗೆ ಸಂಬಂಧಿಸಿದಂತೆ ಕೃಷಿ ತಜ್ಞರ ಮಾಹಿತಿ ಈ ಕೆಳಗಿನಂತಿದೆ:",
            "",
        ]
        # Translate key sections or numbers
        for raw_line in draft_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if "market price" in line.lower() or "price" in line.lower():
                lines.append(f"• **ಮಾರುಕಟ್ಟೆ ಮಾಹಿತಿ**: {line}")
            elif "rainfall" in line.lower() or "weather" in line.lower():
                lines.append(f"• **ಹವಾಮಾನ ಮುನ್ಸೂಚನೆ**: {line}")
            elif "profit" in line.lower() or "revenue" in line.lower() or "loan" in line.lower():
                lines.append(f"• **ಆರ್ಥಿಕ ವಿವರ ಮತ್ತು ಸಾಲ ಸೌಲಭ್ಯ**: {line}")
            elif "disease" in line.lower() or "pest" in line.lower() or "leaf" in line.lower():
                lines.append(f"• **ಬೆಳೆ ಸಂರಕ್ಷಣೆ**: {line}")
            elif "soil" in line.lower() or "fertilizer" in line.lower() or "npk" in line.lower():
                lines.append(f"• **ಮಣ್ಣು ಮತ್ತು ಪೋಷಕಾಂಶ**: {line}")
            else:
                lines.append(f"• {line}")

        lines.extend([
            "",
            "**ಮುಖ್ಯ ಸಲಹೆ**:",
            "1. ಯಾವುದೇ ರಾಸಾಯನಿಕ ಕೀಟನಾಶಕ ಸಿಂಪಡಿಸುವ ಮುನ್ನ ಸ್ಥಳೀಯ ಕೃಷಿ ಅಧಿಕಾರಿ ಅಥವಾ ಕೆ.ವಿ.ಕೆ ತಜ್ಞರ ಸಲಹೆ ಪಡೆಯಿರಿ.",
            "2. ಬೆಳೆಯ ಹಂತಕ್ಕೆ ತಕ್ಕಂತೆ ನೀರು ಮತ್ತು ಗೊಬ್ಬರವನ್ನು ಹಿತಮಿತವಾಗಿ ನೀಡಿ.",
        ])
        return "\n".join(lines)

    if lang == "hi":
        lines = [
            "नमस्ते किसान मित्र, आपकी पूछताछ के संबंध में कृषि विशेषज्ञों की जानकारी निम्नलिखित है:",
            "",
        ]
        for raw_line in draft_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if "market price" in line.lower() or "price" in line.lower():
                lines.append(f"• **मंडी भाव जानकारी**: {line}")
            elif "rainfall" in line.lower() or "weather" in line.lower():
                lines.append(f"• **मौसम पूर्वानुमान**: {line}")
            elif "profit" in line.lower() or "revenue" in line.lower() or "loan" in line.lower():
                lines.append(f"• **वित्तीय विवरण व ऋण**: {line}")
            elif "disease" in line.lower() or "pest" in line.lower() or "leaf" in line.lower():
                lines.append(f"• **फसल सुरक्षा**: {line}")
            elif "soil" in line.lower() or "fertilizer" in line.lower() or "npk" in line.lower():
                lines.append(f"• **मिट्टी व पोषण**: {line}")
            else:
                lines.append(f"• {line}")

        lines.extend([
            "",
            "**महत्वपूर्ण सलाह**:",
            "1. किसी भी रासायनिक कीटनाशक के प्रयोग से पहले स्थानीय कृषि अधिकारी या KVK विशेषज्ञ से परामर्श लें।",
            "2. संतुलित मात्रा में सिंचाई और खाद का प्रयोग करें।",
        ])
        return "\n".join(lines)

    return draft_text


DISCLAIMERS = {
    "en": (
        "KrishiAI provides AI-generated guidance that may not always be accurate. "
        "Verify important crop diagnoses and treatment decisions with a qualified agricultural expert."
    ),
    "hi": (
        "कृषि AI (KrishiAI) कंप्यूटर द्वारा उत्पन्न सलाह प्रदान करता है जो हमेशा सटीक नहीं हो सकती है। "
        "फसल रोग निदान और उपचार के महत्वपूर्ण निर्णयों के लिए योग्य कृषि विशेषज्ञ से पुष्टि अवश्य करें।"
    ),
    "kn": (
        "ಕೃಷಿ AI (KrishiAI) ಕಂಪ್ಯೂಟರ್ ಆಧಾರಿತ ಸಲಹೆಯನ್ನು ಒದಗಿಸುತ್ತದೆ ಮತ್ತು ಇದು ಯಾವಾಗಲೂ ನಿಖರವಾಗಿರದಿರಬಹುದು. "
        "ಬೆಳೆ ರೋಗ ನಿರ್ಣಯ ಮತ್ತು ಚಿಕಿತ್ಸೆಯ ನಿರ್ಧಾರಗಳನ್ನು ದೃಢೀಕರಿಸಲು ಅರ್ಹ ಕೃಷಿ ತಜ್ಞರನ್ನು ಸಂಪರ್ಕಿಸಿ."
    ),
}


def get_disclaimer(language: str) -> str:
    code = normalize_language_code(language)
    return DISCLAIMERS.get(code, DISCLAIMERS["en"])


LOCALIZED_MESSAGES = {
    "en": {
        "greeting_name": "Namaste, Kisan Mitra",
        "find_expert_button": "Find an agricultural expert near me",
        "expert_referral_title": "Local Agricultural Expert Consultation Recommended",
        "what_to_bring_title": "What to take to the expert:",
        "sample_instructions": "Take a fresh leaf sample in a clean paper envelope along with photos of the plant and details of recent sprays or fertilizers.",
        "safe_next_step_label": "Immediate safe step:",
        "prevention_label": "Practical Precautions:",
        "next_steps_label": "What to do next:",
        "unconfirmed_image_title": "Leaf Image Diagnosis: Needs In-Person Confirmation",
        "unconfirmed_image_reason": "The leaf image could not be diagnosed with certainty from the photo alone.",
        "unconfirmed_step_1": "Isolate severely affected leaves and avoid overhead watering to prevent moisture-loving fungal spread.",
        "unconfirmed_step_2": "Do not apply chemical pesticides or fungicides without confirmation from a qualified specialist.",
        "unconfirmed_step_3": "Take a clear leaf photo in bright daylight against a plain background for re-inspection.",
        "unconfirmed_step_4": "Consult your local Krishi Vigyan Kendra (KVK) or Block Agriculture Officer.",
        "missing_context_title": "To give you the most accurate advice, please also share:",
    },
    "hi": {
        "greeting_name": "नमस्ते, किसान मित्र",
        "find_expert_button": "मेरे नजदीकी कृषि विशेषज्ञ खोजें",
        "expert_referral_title": "स्थानीय कृषि विशेषज्ञ से परामर्श की सलाह दी जाती है",
        "what_to_bring_title": "विशेषज्ञ के पास क्या लेकर जाएं:",
        "sample_instructions": "एक ताज़ा प्रभावित पत्ती को साफ कागज़ के लिफाफे में रखें, साथ ही पौधे की तस्वीरें और हाल ही में किए गए खाद या छिड़काव की जानकारी साथ ले जाएं।",
        "safe_next_step_label": "तत्काल सुरक्षित कदम:",
        "prevention_label": "आवश्यक सावधानियां:",
        "next_steps_label": "आगे क्या करें:",
        "unconfirmed_image_title": "पत्ती फोटो निदान: व्यक्तिगत पुष्टि आवश्यक है",
        "unconfirmed_image_reason": "केवल फोटो के आधार पर पत्ती के रोग की पूरी पुष्टि नहीं हो सकी।",
        "unconfirmed_step_1": "अत्यधिक प्रभावित पत्तियों को अलग करें और फंगस के फैलाव को रोकने के लिए ऊपर से पानी देने से बचें।",
        "unconfirmed_step_2": "विशेषज्ञ की पुष्टि के बिना किसी रासायनिक कीटनाशक या फफूंदनाशक का छिड़काव न करें।",
        "unconfirmed_step_3": "प्राकृतिक दिन की रोशनी में साफ पृष्ठभूमि पर पत्ती की स्पष्ट फोटो लें।",
        "unconfirmed_step_4": "अपने नजदीकी कृषि विज्ञान केंद्र (KVK) या कृषि अधिकारी से संपर्क करें।",
        "missing_context_title": "सटीक सलाह के लिए कृपया ये विवरण भी बताएं:",
    },
    "kn": {
        "greeting_name": "ನಮಸ್ಕಾರ, ರೈತ ಮಿತ್ರರೇ",
        "find_expert_button": "ನನ್ನ ಹತ್ತಿರದ ಕೃಷಿ ತಜ್ಞರನ್ನು ಹುಡುಕಿ",
        "expert_referral_title": "ಸ್ಥಳೀಯ ಕೃಷಿ ತಜ್ಞರ ಸಲಹೆ ಪಡೆಯಲು ಶಿಫಾರಸು ಮಾಡಲಾಗಿದೆ",
        "what_to_bring_title": "ತಜ್ಞರ ಬಳಿಗೆ ಏನನ್ನು ತೆಗೆದುಕೊಂಡು ಹೋಗಬೇಕು:",
        "sample_instructions": "ರೋಗಲಕ್ಷಣವಿರುವ ತಾಜಾ ಎಲೆಯ ಮಾದರಿಯನ್ನು ಸ್ವಚ್ಛ ಕಾಗದದ ಹೊದಿಕೆಯಲ್ಲಿ ಇಟ್ಟುಕೊಂಡು, ಗಿಡದ ಫೋಟೋಗಳು ಮತ್ತು ಇತ್ತೀಚಿನ ಗೊಬ್ಬರ/ಔಷಧಿ ಸಿಂಪಡಣೆಯ ವಿವರಗಳೊಂದಿಗೆ ಕೊಂಡೊಯ್ಯಿರಿ.",
        "safe_next_step_label": "ತಕ್ಷಣದ ಸುರಕ್ಷಿತ ಕ್ರಮ:",
        "prevention_label": "ಮುನ್ನೆಚ್ಚರಿಕೆ ಕ್ರಮಗಳು:",
        "next_steps_label": "ಮುಂದೆ ನೀವು ಏನು ಮಾಡಬೇಕು:",
        "unconfirmed_image_title": "ಎಲೆಯ ಫೋಟೋ ಪರಿಶೀಲನೆ: ತಜ್ಞರ ದೃಢೀಕರಣದ ಅಗತ್ಯವಿದೆ",
        "unconfirmed_image_reason": "ಕೇವಲ ಫೋಟೋದ ಆಧಾರದ ಮೇಲೆ ರೋಗವನ್ನು ಖಚಿತವಾಗಿ ನಿರ್ಧರಿಸಲು ಸಾಧ್ಯವಾಗಿಲ್ಲ.",
        "unconfirmed_step_1": "ಬಾಧಿತ ಎಲೆಗಳನ್ನು ಪ್ರತ್ಯೇಕಿಸಿ ಮತ್ತು ಶಿಲೀಂಧ್ರ ಹರಡುವುದನ್ನು ತಡೆಯಲು ಗಿಡದ ಮೇಲಿನಿಂದ ನೀರುಣಿಸುವುದನ್ನು ತಪ್ಪಿಸಿ.",
        "unconfirmed_step_2": "ಕೃಷಿ ತಜ್ಞರ ದೃಢೀಕರಣವಿಲ್ಲದೆ ಯಾವುದೇ ರಾಸಾಯನಿಕ ಕೀಟನಾಶಕ ಅಥವಾ ಶಿಲೀಂಧ್ರನಾಶಕವನ್ನು ಸಿಂಪಡಿಸಬೇಡಿ.",
        "unconfirmed_step_3": "ನೈಸರ್ಗಿಕ ಬೆಳಕಿನಲ್ಲಿ ಸ್ಪಷ್ಟ ಹಿನ್ನೆಲೆಯಲ್ಲಿ ಎಲೆಯ ಸ್ಪಷ್ಟ ಚಿತ್ರವನ್ನು ತೆಗೆದುಕೊಳ್ಳಿ.",
        "unconfirmed_step_4": "ನಿಮ್ಮ ಹತ್ತಿರದ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ (ಕೆ.ವಿ.ಕೆ) ಅಥವಾ ಕೃಷಿ ಅಧಿಕಾರಿಯನ್ನು ಭೇಟಿ ಮಾಡಿ.",
        "missing_context_title": "ಹೆಚ್ಚು ನಿಖರವಾದ ಸಲಹೆಗಾಗಿ, ದಯವಿಟ್ಟು ಈ ಮಾಹಿತಿಯನ್ನು ಹಂಚಿಕೊಳ್ಳಿ:",
    },
}


def get_ui_text(key: str, language: str) -> str:
    lang = normalize_language_code(language)
    bundle = LOCALIZED_MESSAGES.get(lang, LOCALIZED_MESSAGES["en"])
    return bundle.get(key, LOCALIZED_MESSAGES["en"].get(key, ""))
