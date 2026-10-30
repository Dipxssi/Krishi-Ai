#!/usr/bin/env python3
"""Write the agent question bank.

Usage (from backend/):
  uv run python scripts/generate_question_bank.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.orchestrator.orchestrator import UNSAFE_CHEMICAL_PATTERNS  # noqa: E402
from app.orchestrator.question_bank import bank_dir, clear_cache, tokenize  # noqa: E402

AGENTS = [
    "crop_health",
    "finance",
    "equipment",
    "market",
    "weather",
    "soil",
    "knowledge_retriever",
]
LANGS = ("en", "hi", "kn")
INDEX_COUNT = 1000
HOLDOUT_COUNT = 50

PLACES = [
    "Bengaluru",
    "Mysuru",
    "Belagavi",
    "Hubballi",
    "Mandya",
    "Nashik",
    "Pune",
    "Nagpur",
    "Lucknow",
    "Ludhiana",
    "Warangal",
    "Guntur",
]

PLACE_LABEL = {
    "Bengaluru": {"en": "Bengaluru", "hi": "बेंगलुरु", "kn": "ಬೆಂಗಳೂರು"},
    "Mysuru": {"en": "Mysuru", "hi": "मैसूर", "kn": "ಮೈಸೂರು"},
    "Belagavi": {"en": "Belagavi", "hi": "बेलगावि", "kn": "ಬೆಳಗಾವಿ"},
    "Hubballi": {"en": "Hubballi", "hi": "हुबली", "kn": "ಹುಬ್ಬಳ್ಳಿ"},
    "Mandya": {"en": "Mandya", "hi": "मंड्या", "kn": "ಮಂಡ್ಯ"},
    "Nashik": {"en": "Nashik", "hi": "नासिक", "kn": "ನಾಶಿಕ್"},
    "Pune": {"en": "Pune", "hi": "पुणे", "kn": "ಪುಣೆ"},
    "Nagpur": {"en": "Nagpur", "hi": "नागपुर", "kn": "ನಾಗಪುರ"},
    "Lucknow": {"en": "Lucknow", "hi": "लखनऊ", "kn": "ಲಖನೌ"},
    "Ludhiana": {"en": "Ludhiana", "hi": "लुधियाना", "kn": "ಲುಧಿಯಾನಾ"},
    "Warangal": {"en": "Warangal", "hi": "वरंगल", "kn": "ವರಂಗಲ್"},
    "Guntur": {"en": "Guntur", "hi": "गुंटूर", "kn": "ಗುಂಟೂರು"},
}

CROP_LABEL = {
    "cotton": {"en": "cotton", "hi": "कपास", "kn": "ಹತ್ತಿ"},
    "maize": {"en": "maize", "hi": "मक्का", "kn": "ಮೆಕ್ಕೆಜೋಳ"},
    "onion": {"en": "onion", "hi": "प्याज", "kn": "ಈರುಳ್ಳಿ"},
    "potato": {"en": "potato", "hi": "आलू", "kn": "ಆಲೂಗಡ್ಡೆ"},
    "rice": {"en": "rice", "hi": "धान", "kn": "ಭತ್ತ"},
    "tomato": {"en": "tomato", "hi": "टमाटर", "kn": "ಟೊಮೇಟೊ"},
    "wheat": {"en": "wheat", "hi": "गेहूं", "kn": "ಗೋಧಿ"},
}

# id, record or None, en, hi, kn, product en/hi/kn (finance only uses product)
def _intent(intent_id: str, en: str, hi: str, kn: str, record: str | None = None, product: dict | None = None) -> dict:
    return {
        "id": intent_id,
        "record": record,
        "en": en,
        "hi": hi,
        "kn": kn,
        "product": product or {"en": en, "hi": hi, "kn": kn},
    }


INTENTS = {
    "finance": [
        _intent("crop_loan", "crop loan", "फसल ऋण", "ಬೆಳೆ ಸಾಲ", "kcc-crop-loan", {"en": "Kisan Credit Card crop loan", "hi": "किसान क्रेडिट कार्ड फसल ऋण", "kn": "ಕಿಸಾನ್ ಕ್ರೆಡಿಟ್ ಕಾರ್ಡ್ ಬೆಳೆ ಸಾಲ"}),
        _intent("kcc", "Kisan Credit Card", "किसान क्रेडिट कार्ड", "ಕಿಸಾನ್ ಕ್ರೆಡಿಟ್ ಕಾರ್ಡ್", "kcc-crop-loan", {"en": "Kisan Credit Card", "hi": "किसान क्रेडिट कार्ड", "kn": "ಕಿಸಾನ್ ಕ್ರೆಡಿಟ್ ಕಾರ್ಡ್"}),
        _intent("gold_loan", "gold loan", "स्वर्ण ऋण", "ಚಿನ್ನದ ಸಾಲ", "agri-gold-loan", {"en": "agricultural gold loan", "hi": "कृषि स्वर्ण ऋण", "kn": "ಕೃಷಿ ಚಿನ್ನದ ಸಾಲ"}),
        _intent("equipment_loan", "equipment loan", "यंत्र ऋण", "ಯಂತ್ರ ಸಾಲ", "farm-mechanization-loan", {"en": "farm mechanization loan", "hi": "कृषि यंत्र ऋण", "kn": "ಕೃಷಿ ಯಂತ್ರ ಸಾಲ"}),
        _intent("dairy_loan", "dairy loan", "डेयरी ऋण", "ಹೈನುಗಾರಿಕೆ ಸಾಲ", "dairy-loan-nabard", {"en": "dairy loan", "hi": "डेयरी ऋण", "kn": "ಹೈನುಗಾರಿಕೆ ಸಾಲ"}),
        _intent("mudra", "MUDRA loan", "मुद्रा ऋण", "ಮುದ್ರಾ ಸಾಲ", "mudra-agri", {"en": "MUDRA loan", "hi": "मुद्रा ऋण", "kn": "ಮುದ್ರಾ ಸಾಲ"}),
        _intent("subsidy", "subsidy", "सब्सिडी", "ಸಬ್ಸಿಡಿ"),
        _intent("crop_insurance", "crop insurance", "फसल बीमा", "ಬೆಳೆ ವಿಮೆ"),
        _intent("documents", "loan documents", "ऋण कागजात", "ಸಾಲದ ದಾಖಲೆಗಳು"),
        _intent("where_to_apply", "where to apply", "आवेदन कहां करें", "ಎಲ್ಲಿ ಅರ್ಜಿ ಸಲ್ಲಿಸಬೇಕು"),
        _intent("repayment", "repayment", "चुकौती", "ಮರುಪಾವತಿ"),
        _intent("collateral", "collateral", "जमानत", "ಒತ್ತೆ"),
        _intent("tenant_farmer", "tenant farmer credit", "किरायेदार किसान ऋण", "ಗೇಣಿದಾರ ರೈತ ಸಾಲ"),
        _intent("interest_confirmation", "interest confirmation", "ब्याज की पुष्टि", "ಬಡ್ಡಿ ಖಚಿತಪಡಿಸುವುದು"),
    ],
    "equipment": [
        _intent("tractor", "tractor", "ट्रैक्टर", "ಟ್ರಾಕ್ಟರ್"),
        _intent("power_tiller", "power tiller", "पावर टिलर", "ಪವರ್ ಟಿಲ್ಲರ್"),
        _intent("sprayer", "sprayer", "स्प्रेयर", "ಸಿಂಪಡಕ"),
        _intent("harvester", "harvester", "हार्वेस्टर", "ಹಾರ್ವೆಸ್ಟರ್"),
        _intent("drip", "drip irrigation", "ड्रिप सिंचाई", "ಹನಿ ನೀರಾವರಿ"),
        _intent("solar_pump", "solar pump", "सोलर पंप", "ಸೌರ ಪಂಪ್"),
        _intent("rent_or_buy", "rental versus buying", "किराया या खरीद", "ಬಾಡಿಗೆ ಅಥವಾ ಖರೀದಿ"),
        _intent("rotavator", "rotavator", "रोटावेटर", "ರೋಟಾವೇಟರ್"),
        _intent("thresher", "thresher", "थ्रेशर", "ಥ್ರೆಶರ್"),
        _intent("seed_drill", "seed drill", "सीड ड्रिल", "ಬೀಜ ಬಿತ್ತುವ ಯಂತ್ರ"),
    ],
    "crop_health": [
        _intent("leaf_spots", "leaf spots", "पत्ती के धब्बे", "ಎಲೆ ಮೇಲಿನ ಚುಕ್ಕೆಗಳು"),
        _intent("blight", "blight", "झुलसा", "ಎಲೆ ಸುಡು ರೋಗ"),
        _intent("pest", "pest", "कीट", "ಕೀಟ"),
        _intent("yellowing", "yellowing", "पीलापन", "ಎಲೆ ಹಳದಿ"),
        _intent("fungus", "fungus", "फफूंद", "ಶಿಲೀಂಧ್ರ"),
        _intent("treatment_steps", "treatment steps", "देखभाल के कदम", "ಆರೈಕೆಯ ಹೆಜ್ಜೆಗಳು"),
        _intent("whether_to_spray", "whether to spray", "छिड़काव करना है या नहीं", "ಸಿಂಪಡಣೆ ಬೇಕೇ"),
        _intent("spreading", "spreading on leaves", "पत्तियों पर फैलाव", "ಎಲೆಗಳ ಮೇಲೆ ಹರಡುವಿಕೆ"),
        _intent("fruit_damage", "fruit damage", "फल का नुकसान", "ಹಣ್ಣಿನ ಹಾನಿ"),
        _intent("healthy_check", "healthy leaf check", "स्वस्थ पत्ती की जांच", "ಆರೋಗ್ಯಕರ ಎಲೆ ಪರಿಶೀಲನೆ"),
    ],
    "market": [
        _intent("mandi_price", "mandi price", "मंडी भाव", "ಮಂಡಿ ಧಾರಣೆ"),
        _intent("sell_now", "sell now", "अभी बेचना", "ಈಗ ಮಾರಾಟ"),
        _intent("hold", "hold the harvest", "फसल रोकना", "ಬೆಳೆ ಇಡುವುದು"),
        _intent("storage", "storage", "भंडारण", "ಸಂಗ್ರಹಣೆ"),
        _intent("distant_market", "distant market", "दूर की मंडी", "ದೂರದ ಮಾರುಕಟ್ಟೆ"),
        _intent("demand", "demand", "मांग", "ಬೇಡಿಕೆ"),
        _intent("price_forecast", "price forecast", "भाव का पूर्वानुमान", "ಬೆಲೆ ಮುನ್ಸೂಚನೆ"),
        _intent("transport", "transport to market", "मंडी तक ढुलाई", "ಮಾರುಕಟ್ಟೆಗೆ ಸಾಗಣೆ"),
    ],
    "weather": [
        _intent("rain_week", "rain this week", "इस सप्ताह बारिश", "ಈ ವಾರದ ಮಳೆ"),
        _intent("heavy_rain", "heavy rain", "भारी बारिश", "ಭಾರೀ ಮಳೆ"),
        _intent("drought", "drought", "सूखा", "ಬರ"),
        _intent("temperature", "temperature", "तापमान", "ತಾಪಮಾನ"),
        _intent("humidity", "humidity", "नमी", "ತೇವಾಂಶ"),
        _intent("irrigate_or_wait", "irrigate or wait", "सिंचाई या इंतजार", "ನೀರಾವರಿ ಅಥವಾ ಕಾಯುವುದು"),
        _intent("planting_window", "planting window", "बुवाई का समय", "ಬಿತ್ತನೆ ಸಮಯ"),
        _intent("flood_risk", "flood risk", "बाढ़ का खतरा", "ಪ್ರವಾಹದ ಅಪಾಯ"),
    ],
    "soil": [
        _intent("soil_test", "soil test", "मिट्टी जांच", "ಮಣ್ಣಿನ ಪರೀಕ್ಷೆ"),
        _intent("nitrogen", "nitrogen", "नाइट्रोजन", "ಸಾರಜನಕ"),
        _intent("phosphorus", "phosphorus", "फास्फोरस", "ರಂಜಕ"),
        _intent("potassium", "potassium", "पोटाश", "ಪೊಟ್ಯಾಷ್"),
        _intent("ph", "soil reaction", "मिट्टी की प्रतिक्रिया", "ಮಣ್ಣಿನ ಪ್ರತಿಕ್ರಿಯೆ"),
        _intent("fertilizer_timing", "fertilizer timing", "खाद का समय", "ಗೊಬ್ಬರದ ಸಮಯ"),
        _intent("organic_manure", "organic manure", "जैविक खाद", "ಸಾವಯವ ಗೊಬ್ಬರ"),
        _intent("suitability", "suitability for the crop", "फसल के लिए उपयुक्तता", "ಬೆಳೆಗೆ ಹೊಂದಿಕೆ"),
    ],
    "knowledge_retriever": [
        _intent("how_to_grow", "how to grow", "कैसे उगाएं", "ಹೇಗೆ ಬೆಳೆಸುವುದು"),
        _intent("sowing", "sowing method", "बुवाई विधि", "ಬಿತ್ತನೆ ವಿಧಾನ"),
        _intent("seed_guidance", "seed guidance", "बीज मार्गदर्शन", "ಬೀಜ ಮಾರ್ಗದರ್ಶನ"),
        _intent("nursery", "nursery", "नर्सरी", "ನರ್ಸರಿ"),
        _intent("spacing", "spacing", "दूरी", "ಅಂತರ"),
        _intent("harvest_method", "harvesting method", "कटाई विधि", "ಕಟಾವು ವಿಧಾನ"),
        _intent("where_seed", "where to get seed", "बीज कहां से लें", "ಬೀಜ ಎಲ್ಲಿಂದ ಪಡೆಯುವುದು"),
        _intent("kvk_visit", "KVK visit", "केवीके मुलाकात", "ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ ಭೇಟಿ"),
    ],
}

PREFIX = {
    "finance": {
        "en": "What agricultural loan options are there for my {crop} farm in {place}?",
        "hi": "मेरे {crop} खेत के लिए {place} में कृषि ऋण के कौन से विकल्प हैं?",
        "kn": "ನನ್ನ {crop} ಜಮೀನಿಗೆ {place} ನಲ್ಲಿ ಯಾವ ಕೃಷಿ ಸಾಲದ ಆಯ್ಕೆಗಳಿವೆ?",
    },
    "equipment": {
        "en": "Which farm machine should I arrange for {intent} on my {crop} farm in {place}?",
        "hi": "{place} में मेरे {crop} खेत के लिए {intent} हेतु कौन सी मशीन चाहिए?",
        "kn": "{place} ನಲ್ಲಿ ನನ್ನ {crop} ಜಮೀನಿಗೆ {intent} ಗೆ ಯಾವ ಯಂತ್ರ ಬೇಕು?",
    },
    "crop_health": {
        "en": "What leaf symptom should I check for {intent} on my {crop} crop in {place}?",
        "hi": "{place} में मेरी {crop} फसल पर {intent} के लिए कौन सा पत्ती लक्षण देखूं?",
        "kn": "{place} ನಲ್ಲಿ ನನ್ನ {crop} ಬೆಳೆಯಲ್ಲಿ {intent} ಗೆ ಯಾವ ಎಲೆ ಲಕ್ಷಣ ನೋಡಬೇಕು?",
    },
    "market": {
        "en": "What mandi sale choice fits {intent} for my {crop} crop in {place}?",
        "hi": "{place} में मेरी {crop} फसल के {intent} के लिए मंडी में क्या निर्णय लूं?",
        "kn": "{place} ನಲ್ಲಿ ನನ್ನ {crop} ಬೆಳೆಯ {intent} ಗೆ ಮಂಡಿಯಲ್ಲಿ ಯಾವ ನಿರ್ಧಾರ ತೆಗೆದುಕೊಳ್ಳಲಿ?",
    },
    "weather": {
        "en": "What rainfall outlook matters for {intent} around my {crop} crop in {place}?",
        "hi": "{place} में मेरी {crop} फसल के पास {intent} के लिए बारिश का पूर्वानुमान क्या है?",
        "kn": "{place} ನಲ್ಲಿ ನನ್ನ {crop} ಬೆಳೆಯ ಬಳಿ {intent} ಗೆ ಮಳೆ ಮುನ್ಸೂಚನೆ ಏನು?",
    },
    "soil": {
        "en": "What soil fertility step fits {intent} for my {crop} field in {place}?",
        "hi": "{place} में मेरे {crop} खेत की {intent} के लिए मिट्टी की कौन सी तैयारी करें?",
        "kn": "{place} ನಲ್ಲಿ ನನ್ನ {crop} ಜಮೀನಿನ {intent} ಗೆ ಮಣ್ಣಿನ ಯಾವ ಸಿದ್ಧತೆ ಬೇಕು?",
    },
    "knowledge_retriever": {
        "en": "What cultivation practice covers {intent} for my {crop} crop in {place}?",
        "hi": "{place} में मेरी {crop} फसल की {intent} के लिए कौन सी खेती विधि अपनाऊं?",
        "kn": "{place} ನಲ್ಲಿ ನನ್ನ {crop} ಬೆಳೆಯ {intent} ಗೆ ಯಾವ ಕೃಷಿ ಪದ್ಧತಿ ಅನುಸರಿಸಲಿ?",
    },
}

TAILS = {
    "finance": {
        "en": [
            " This question is about {intent}.",
            " I need the bank visit loan documents for {intent} from the agricultural credit desk.",
            " Which bank should I visit for {intent} and which loan documents should I carry?",
            " What loan documents does the agricultural credit desk ask for {intent}?",
            " Can I discuss {intent} at the bank visit with my loan documents?",
            " Who at the agricultural credit desk explains {intent} and the loan documents?",
            " How does a bank visit for {intent} work if I bring the loan documents?",
            " Please guide the loan documents and bank visit for {intent} at the agricultural credit desk.",
        ],
        "hi": [
            " यह प्रश्न {intent} के बारे में है।",
            " मुझे {intent} के लिए बैंक यात्रा और ऋण कागजात चाहिए।",
            " {intent} के लिए किस बैंक जाऊं और कौन से ऋण कागजात ले जाऊं?",
            " कृषि ऋण डेस्क {intent} के लिए कौन से कागजात मांगती है?",
            " क्या मैं ऋण कागजात लेकर {intent} पर बैंक में बात कर सकता हूं?",
            " कृषि ऋण डेस्क पर {intent} कौन समझाएगा?",
            " {intent} के लिए बैंक यात्रा कैसे होती है?",
            " कृपया {intent} के ऋण कागजात और बैंक यात्रा बताएं।",
        ],
        "kn": [
            " ಈ ಪ್ರಶ್ನೆ {intent} ಬಗ್ಗೆ ಇದೆ.",
            " {intent} ಗೆ ಬ್ಯಾಂಕ್ ಭೇಟಿ ಮತ್ತು ಸಾಲದ ದಾಖಲೆಗಳು ಬೇಕು.",
            " {intent} ಗೆ ಯಾವ ಬ್ಯಾಂಕ್ ಗೆ ಹೋಗಲಿ ಮತ್ತು ಯಾವ ಸಾಲದ ದಾಖಲೆ ತೆಗೆದುಕೊಂಡು ಹೋಗಲಿ?",
            " ಕೃಷಿ ಸಾಲದ ಮೇಜು {intent} ಗೆ ಯಾವ ದಾಖಲೆ ಕೇಳುತ್ತದೆ?",
            " ಸಾಲದ ದಾಖಲೆ ತಂದು {intent} ಬಗ್ಗೆ ಬ್ಯಾಂಕ್ ನಲ್ಲಿ ಮಾತನಾಡಬಹುದೇ?",
            " ಕೃಷಿ ಸಾಲದ ಮೇಜಿನಲ್ಲಿ {intent} ಯಾರು ವಿವರಿಸುತ್ತಾರೆ?",
            " {intent} ಗೆ ಬ್ಯಾಂಕ್ ಭೇಟಿ ಹೇಗೆ ನಡೆಯುತ್ತದೆ?",
            " ದಯವಿಟ್ಟು {intent} ನ ಸಾಲದ ದಾಖಲೆ ಮತ್ತು ಬ್ಯಾಂಕ್ ಭೇಟಿ ತಿಳಿಸಿ.",
        ],
    },
    "equipment": {
        "en": [
            " Ask the custom hiring yard about {intent}.",
            " I want the machine rental choice for {intent}.",
            " Should I rent the implement for {intent} or buy it?",
            " Where is the custom hiring yard for {intent}?",
            " Which implement fits {intent} on this farm?",
            " Help me compare machine rental and buying for {intent}.",
            " The custom hiring yard should explain {intent}.",
            " Guide the implement choice for {intent}.",
        ],
        "hi": [
            " {intent} के लिए कस्टम हायरिंग केंद्र से पूछें।",
            " मुझे {intent} के लिए मशीन किराए का विकल्प चाहिए।",
            " {intent} का औजार किराए पर लूं या खरीदूं?",
            " {intent} का कस्टम हायरिंग केंद्र कहां है?",
            " इस खेत के लिए {intent} कौन सा औजार ठीक है?",
            " {intent} के लिए किराया और खरीद की तुलना करें।",
            " कस्टम हायरिंग केंद्र {intent} समझाए।",
            " {intent} का औजार चुनने में मदद करें।",
        ],
        "kn": [
            " {intent} ಬಗ್ಗೆ ಕಸ್ಟಮ್ ಹೈರಿಂಗ್ ಕೇಂದ್ರದಲ್ಲಿ ಕೇಳಿ.",
            " {intent} ಗೆ ಯಂತ್ರ ಬಾಡಿಗೆ ಆಯ್ಕೆ ಬೇಕು.",
            " {intent} ಉಪಕರಣವನ್ನು ಬಾಡಿಗೆಗೆ ತೆಗೆದುಕೊಳ್ಳಲೇ ಅಥವಾ ಖರೀದಿಸಲೇ?",
            " {intent} ನ ಕಸ್ಟಮ್ ಹೈರಿಂಗ್ ಕೇಂದ್ರ ಎಲ್ಲಿದೆ?",
            " ಈ ಜಮೀನಿಗೆ {intent} ಯಾವ ಉಪಕರಣ ಸರಿ?",
            " {intent} ಗೆ ಬಾಡಿಗೆ ಮತ್ತು ಖರೀದಿ ಹೋಲಿಸಿ.",
            " ಕಸ್ಟಮ್ ಹೈರಿಂಗ್ ಕೇಂದ್ರ {intent} ವಿವರಿಸಲಿ.",
            " {intent} ಉಪಕರಣ ಆಯ್ಕೆಗೆ ಮಾರ್ಗ ತಿಳಿಸಿ.",
        ],
    },
    "crop_health": {
        "en": [
            " Please arrange a leaf inspection for this plant health symptom.",
            " I need a leaf inspection before any treatment decision.",
            " The plant health symptom needs a closer leaf inspection.",
            " Help me prepare a leaf inspection at the extension office.",
            " A leaf inspection should look at this plant health symptom.",
            " Tell me how to carry a leaf for inspection.",
            " The extension office should see this plant health symptom.",
            " Guide the leaf inspection for this plant health symptom.",
        ],
        "hi": [
            " इस पौधे के लक्षण के लिए पत्ती निरीक्षण करवाएं।",
            " किसी निर्णय से पहले पत्ती निरीक्षण चाहिए।",
            " पौधे के लक्षण के लिए नजदीक से पत्ती निरीक्षण चाहिए।",
            " विस्तार कार्यालय में पत्ती निरीक्षण की तैयारी बताएं।",
            " पत्ती निरीक्षण में यह पौधा लक्षण दिखाना है।",
            " निरीक्षण के लिए पत्ती कैसे ले जाऊं?",
            " विस्तार कार्यालय इस पौधे के लक्षण देखे।",
            " इस पौधे के लक्षण का पत्ती निरीक्षण समझाएं।",
        ],
        "kn": [
            " ಈ ಸಸ್ಯ ಲಕ್ಷಣಕ್ಕೆ ಎಲೆ ಪರಿಶೀಲನೆ ಏರ್ಪಡಿಸಿ.",
            " ಯಾವುದೇ ನಿರ್ಧಾರದ ಮೊದಲು ಎಲೆ ಪರಿಶೀಲನೆ ಬೇಕು.",
            " ಸಸ್ಯ ಲಕ್ಷಣಕ್ಕೆ ಹತ್ತಿರದ ಎಲೆ ಪರಿಶೀಲನೆ ಬೇಕು.",
            " ವಿಸ್ತರಣಾ ಕಚೇರಿಯಲ್ಲಿ ಎಲೆ ಪರಿಶೀಲನೆಗೆ ಸಿದ್ಧತೆ ತಿಳಿಸಿ.",
            " ಎಲೆ ಪರಿಶೀಲನೆಯಲ್ಲಿ ಈ ಸಸ್ಯ ಲಕ್ಷಣ ತೋರಿಸಬೇಕು.",
            " ಪರಿಶೀಲನೆಗೆ ಎಲೆಯನ್ನು ಹೇಗೆ ತೆಗೆದುಕೊಂಡು ಹೋಗುವುದು?",
            " ವಿಸ್ತರಣಾ ಕಚೇರಿ ಈ ಸಸ್ಯ ಲಕ್ಷಣ ನೋಡಲಿ.",
            " ಈ ಸಸ್ಯ ಲಕ್ಷಣದ ಎಲೆ ಪರಿಶೀಲನೆ ವಿವರಿಸಿ.",
        ],
    },
    "market": {
        "en": [
            " I will check the mandi sale before moving the harvest.",
            " Help me decide the mandi sale for this harvest.",
            " The mandi trading floor should hear this harvest question.",
            " Should the harvest go to the mandi sale today?",
            " Ask the mandi about demand before the harvest moves.",
            " Guide the mandi sale choice for this harvest.",
            " I need the mandi trading floor view on this harvest.",
            " Explain the mandi sale steps for this harvest.",
        ],
        "hi": [
            " फसल ले जाने से पहले मंडी बिक्री देखूंगा।",
            " इस फसल की मंडी बिक्री का निर्णय बताएं।",
            " मंडी इस फसल का प्रश्न सुने।",
            " क्या आज फसल मंडी बिक्री के लिए जाए?",
            " फसल ले जाने से पहले मंडी से मांग पूछें।",
            " इस फसल की मंडी बिक्री के कदम बताएं।",
            " मंडी का नजरिया इस फसल पर चाहिए।",
            " मंडी बिक्री की प्रक्रिया समझाएं।",
        ],
        "kn": [
            " ಬೆಳೆ ಸಾಗಿಸುವ ಮೊದಲು ಮಂಡಿ ಮಾರಾಟ ನೋಡುತ್ತೇನೆ.",
            " ಈ ಬೆಳೆಯ ಮಂಡಿ ಮಾರಾಟದ ನಿರ್ಧಾರ ತಿಳಿಸಿ.",
            " ಮಂಡಿ ಈ ಬೆಳೆಯ ಪ್ರಶ್ನೆ ಕೇಳಲಿ.",
            " ಇಂದು ಬೆಳೆ ಮಂಡಿ ಮಾರಾಟಕ್ಕೆ ಹೋಗಬೇಕೇ?",
            " ಬೆಳೆ ಸಾಗಿಸುವ ಮೊದಲು ಮಂಡಿಯಲ್ಲಿ ಬೇಡಿಕೆ ಕೇಳಿ.",
            " ಈ ಬೆಳೆಯ ಮಂಡಿ ಮಾರಾಟದ ಹೆಜ್ಜೆ ತಿಳಿಸಿ.",
            " ಈ ಬೆಳೆಯ ಬಗ್ಗೆ ಮಂಡಿ ನೋಟ ಬೇಕು.",
            " ಮಂಡಿ ಮಾರಾಟದ ಕ್ರಮ ವಿವರಿಸಿ.",
        ],
    },
    "weather": {
        "en": [
            " I am watching the rainfall outlook and the field weather.",
            " Tell me the field weather before I plan work.",
            " The rainfall outlook should guide this field weather choice.",
            " Help me read the field weather for the coming days.",
            " A rainfall outlook is what I need for field weather.",
            " Should field work wait for the rainfall outlook?",
            " Explain the field weather and the rainfall outlook.",
            " Guide me with the rainfall outlook for field weather.",
        ],
        "hi": [
            " मैं बारिश का पूर्वानुमान और खेत का मौसम देख रहा हूं।",
            " काम की योजना से पहले खेत का मौसम बताएं।",
            " बारिश का पूर्वानुमान इस खेत के मौसम का निर्णय दिखाए।",
            " आने वाले दिनों का खेत का मौसम समझाएं।",
            " खेत के मौसम के लिए बारिश का पूर्वानुमान चाहिए।",
            " क्या खेत का काम बारिश के पूर्वानुमान तक रुके?",
            " खेत का मौसम और बारिश का पूर्वानुमान समझाएं।",
            " बारिश के पूर्वानुमान से खेत का मौसम बताएं।",
        ],
        "kn": [
            " ನಾನು ಮಳೆ ಮುನ್ಸೂಚನೆ ಮತ್ತು ಹೊಲದ ಹವಾಮಾನ ನೋಡುತ್ತಿದ್ದೇನೆ.",
            " ಕೆಲಸ ಯೋಜಿಸುವ ಮೊದಲು ಹೊಲದ ಹವಾಮಾನ ತಿಳಿಸಿ.",
            " ಮಳೆ ಮುನ್ಸೂಚನೆ ಈ ಹೊಲದ ಹವಾಮಾನ ನಿರ್ಧಾರ ತೋರಿಸಲಿ.",
            " ಬರುವ ದಿನಗಳ ಹೊಲದ ಹವಾಮಾನ ವಿವರಿಸಿ.",
            " ಹೊಲದ ಹವಾಮಾನಕ್ಕೆ ಮಳೆ ಮುನ್ಸೂಚನೆ ಬೇಕು.",
            " ಹೊಲದ ಕೆಲಸ ಮಳೆ ಮುನ್ಸೂಚನೆಯವರೆಗೆ ನಿಲ್ಲಬೇಕೇ?",
            " ಹೊಲದ ಹವಾಮಾನ ಮತ್ತು ಮಳೆ ಮುನ್ಸೂಚನೆ ವಿವರಿಸಿ.",
            " ಮಳೆ ಮುನ್ಸೂಚನೆಯಿಂದ ಹೊಲದ ಹವಾಮಾನ ತಿಳಿಸಿ.",
        ],
    },
    "soil": {
        "en": [
            " I will carry the soil fertility report.",
            " The soil fertility report should be read before manure.",
            " Help me take the soil fertility report to the extension office.",
            " Which nutrient does the soil fertility report point to?",
            " Guide the manure plan using the soil fertility report.",
            " A soil fertility report is what I need before manure.",
            " Explain the soil fertility report in simple words.",
            " The extension office should read my soil fertility report.",
        ],
        "hi": [
            " मैं मिट्टी उर्वरता रिपोर्ट ले जाऊंगा।",
            " खाद से पहले मिट्टी उर्वरता रिपोर्ट पढ़ी जाए।",
            " मिट्टी उर्वरता रिपोर्ट विस्तार कार्यालय कैसे ले जाऊं?",
            " मिट्टी उर्वरता रिपोर्ट कौन सा पोषक दिखाती है?",
            " मिट्टी उर्वरता रिपोर्ट से खाद योजना बताएं।",
            " खाद से पहले मिट्टी उर्वरता रिपोर्ट चाहिए।",
            " मिट्टी उर्वरता रिपोर्ट आसान शब्दों में समझाएं।",
            " विस्तार कार्यालय मेरी मिट्टी उर्वरता रिपोर्ट पढ़े।",
        ],
        "kn": [
            " ನಾನು ಮಣ್ಣಿನ ಫಲವತ್ತತೆ ವರದಿ ತೆಗೆದುಕೊಂಡು ಹೋಗುತ್ತೇನೆ.",
            " ಗೊಬ್ಬರದ ಮೊದಲು ಮಣ್ಣಿನ ಫಲವತ್ತತೆ ವರದಿ ಓದಬೇಕು.",
            " ಮಣ್ಣಿನ ಫಲವತ್ತತೆ ವರದಿಯನ್ನು ವಿಸ್ತರಣಾ ಕಚೇರಿಗೆ ಹೇಗೆ ತೆಗೆದುಕೊಂಡು ಹೋಗುವುದು?",
            " ಮಣ್ಣಿನ ಫಲವತ್ತತೆ ವರದಿ ಯಾವ ಪೋಷಕ ತೋರಿಸುತ್ತದೆ?",
            " ಮಣ್ಣಿನ ಫಲವತ್ತತೆ ವರದಿಯಿಂದ ಗೊಬ್ಬರ ಯೋಜನೆ ತಿಳಿಸಿ.",
            " ಗೊಬ್ಬರದ ಮೊದಲು ಮಣ್ಣಿನ ಫಲವತ್ತತೆ ವರದಿ ಬೇಕು.",
            " ಮಣ್ಣಿನ ಫಲವತ್ತತೆ ವರದಿಯನ್ನು ಸರಳವಾಗಿ ವಿವರಿಸಿ.",
            " ವಿಸ್ತರಣಾ ಕಚೇರಿ ನನ್ನ ಮಣ್ಣಿನ ಫಲವತ್ತತೆ ವರದಿ ಓದಲಿ.",
        ],
    },
    "knowledge_retriever": {
        "en": [
            " I need the cultivation practice for this crop lesson.",
            " Explain the cultivation practice in simple steps.",
            " Where do I learn this cultivation practice?",
            " The crop lesson should cover this cultivation practice.",
            " Help me follow the cultivation practice on my farm.",
            " Guide the cultivation practice before sowing or harvest.",
            " A crop lesson on this cultivation practice would help.",
            " Tell me the cultivation practice I should ask about.",
        ],
        "hi": [
            " मुझे इस फसल पाठ की खेती विधि चाहिए।",
            " खेती विधि आसान कदमों में समझाएं।",
            " यह खेती विधि कहां सीखूं?",
            " फसल पाठ में यह खेती विधि होनी चाहिए।",
            " अपने खेत पर खेती विधि अपनाने में मदद करें।",
            " बुवाई या कटाई से पहले खेती विधि बताएं।",
            " इस खेती विधि का फसल पाठ चाहिए।",
            " मैं किस खेती विधि के बारे में पूछूं?",
        ],
        "kn": [
            " ಈ ಬೆಳೆ ಪಾಠದ ಕೃಷಿ ಪದ್ಧತಿ ಬೇಕು.",
            " ಕೃಷಿ ಪದ್ಧತಿಯನ್ನು ಸರಳ ಹೆಜ್ಜೆಗಳಲ್ಲಿ ವಿವರಿಸಿ.",
            " ಈ ಕೃಷಿ ಪದ್ಧತಿ ಎಲ್ಲಿ ಕಲಿಯುವುದು?",
            " ಬೆಳೆ ಪಾಠದಲ್ಲಿ ಈ ಕೃಷಿ ಪದ್ಧತಿ ಇರಬೇಕು.",
            " ನನ್ನ ಜಮೀನಿನಲ್ಲಿ ಕೃಷಿ ಪದ್ಧತಿ ಅನುಸರಿಸಲು ಸಹಾಯ ಮಾಡಿ.",
            " ಬಿತ್ತನೆ ಅಥವಾ ಕಟಾವಿನ ಮೊದಲು ಕೃಷಿ ಪದ್ಧತಿ ತಿಳಿಸಿ.",
            " ಈ ಕೃಷಿ ಪದ್ಧತಿಯ ಬೆಳೆ ಪಾಠ ಬೇಕು.",
            " ಯಾವ ಕೃಷಿ ಪದ್ಧತಿ ಬಗ್ಗೆ ಕೇಳಬೇಕು?",
        ],
    },
}

NEXT_STEP = {
    "finance": {
        "en": "Take land records, Aadhaar, a passport photo, and a crop plan to a scheduled commercial bank, cooperative bank, or regional rural bank in {place}. Ask for the {product} for the {crop} crop. Carry these documents and confirm the current interest rate and collateral rule at the branch.",
        "hi": "{place} में किसी अनुसूचित वाणिज्यिक बैंक, सहकारी बैंक, या क्षेत्रीय ग्रामीण बैंक जाएं। {crop} फसल के लिए {product} के बारे में पूछें। जमीन के कागजात, आधार, फोटो और फसल योजना ले जाएं। ब्याज और जमानत की वर्तमान शर्त शाखा पर पूछें।",
        "kn": "{place} ನಲ್ಲಿ ಅನುಸೂಚಿತ ವಾಣಿಜ್ಯ ಬ್ಯಾಂಕ್, ಸಹಕಾರಿ ಬ್ಯಾಂಕ್, ಅಥವಾ ಪ್ರಾದೇಶಿಕ ಗ್ರಾಮೀಣ ಬ್ಯಾಂಕ್ ಗೆ ಹೋಗಿ. {crop} ಬೆಳೆಗೆ {product} ಬಗ್ಗೆ ಕೇಳಿ. ಭೂ ದಾಖಲೆ, ಆಧಾರ್, ಫೋಟೋ ಮತ್ತು ಬೆಳೆ ಯೋಜನೆ ತೆಗೆದುಕೊಂಡು ಹೋಗಿ. ಬಡ್ಡಿ ಮತ್ತು ಒತ್ತೆ ನಿಯಮವನ್ನು ಶಾಖೆಯಲ್ಲಿ ಖಚಿತಪಡಿಸಿ.",
    },
    "equipment": {
        "en": "Ask a custom hiring centre or the Krishi Vigyan Kendra (KVK) in {place} which machine fits the {crop} crop. Carry land records. Compare rental with buying before you decide.",
        "hi": "{place} के कस्टम हायरिंग केंद्र या कृषि विज्ञान केंद्र (KVK) से पूछें कि {crop} फसल के लिए कौन सी मशीन ठीक है। जमीन के कागजात ले जाएं। निर्णय से पहले किराया और खरीद की तुलना करें।",
        "kn": "{place} ನ ಕಸ್ಟಮ್ ಹೈರಿಂಗ್ ಕೇಂದ್ರ ಅಥವಾ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ (KVK) ನಲ್ಲಿ {crop} ಬೆಳೆಗೆ ಯಾವ ಯಂತ್ರ ಸರಿ ಎಂದು ಕೇಳಿ. ಭೂ ದಾಖಲೆ ತೆಗೆದುಕೊಂಡು ಹೋಗಿ. ನಿರ್ಧಾರದ ಮೊದಲು ಬಾಡಿಗೆ ಮತ್ತು ಖರೀದಿ ಹೋಲಿಸಿ.",
    },
    "crop_health": {
        "en": "Photograph one fully visible leaf in daylight and take it to the Krishi Vigyan Kendra (KVK) in {place}. Carry the land record for the {crop} crop. Ask the officer to inspect the plant before any treatment.",
        "hi": "दिन के उजाले में एक पूरी पत्ती की तस्वीर लें और {place} के कृषि विज्ञान केंद्र (KVK) ले जाएं। {crop} फसल का जमीन का कागजात साथ रखें। किसी निर्णय से पहले अधिकारी से पौधे की जांच करवाएं।",
        "kn": "ಬೆಳಕಿನಲ್ಲಿ ಒಂದು ಪೂರ್ಣ ಎಲೆಯ ಚಿತ್ರ ತೆಗೆದು {place} ನ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ (KVK) ಗೆ ತೆಗೆದುಕೊಂಡು ಹೋಗಿ. {crop} ಬೆಳೆಯ ಭೂ ದಾಖಲೆ ಜೊತೆ ಇಡಿ. ಯಾವುದೇ ನಿರ್ಧಾರದ ಮೊದಲು ಅಧಿಕಾರಿಯಿಂದ ಸಸ್ಯ ಪರಿಶೀಲನೆ ಮಾಡಿಸಿ.",
    },
    "market": {
        "en": "Check the local mandi in {place} for the {crop} crop before you sell or store the harvest. Carry a small sample and ask about today's demand. Treat any later price outlook as a forecast.",
        "hi": "बेचने या रखने से पहले {place} की स्थानीय मंडी में {crop} फसल देखें। छोटा नमूना ले जाएं और आज की मांग पूछें। बाद के भाव को पूर्वानुमान मानें।",
        "kn": "ಮಾರಾಟ ಅಥವಾ ಶೇಖರಣೆಯ ಮೊದಲು {place} ನ ಸ್ಥಳೀಯ ಮಂಡಿಯಲ್ಲಿ {crop} ಬೆಳೆ ನೋಡಿ. ಸಣ್ಣ ಮಾದರಿ ತೆಗೆದುಕೊಂಡು ಹೋಗಿ ಇಂದಿನ ಬೇಡಿಕೆ ಕೇಳಿ. ನಂತರದ ಬೆಲೆಯನ್ನು ಮುನ್ಸೂಚನೆ ಎಂದು ತೆಗೆದುಕೊಳ್ಳಿ.",
    },
    "weather": {
        "en": "Ask the Krishi Vigyan Kendra (KVK) in {place} about the coming days for the {crop} crop. Delay field work when heavy rain is expected. This outlook is a forecast.",
        "hi": "{place} के कृषि विज्ञान केंद्र (KVK) से {crop} फसल के आने वाले दिनों के बारे में पूछें। भारी बारिश की आशंका हो तो खेत का काम टालें। यह पूर्वानुमान है।",
        "kn": "{place} ನ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ (KVK) ನಲ್ಲಿ {crop} ಬೆಳೆಯ ಮುಂದಿನ ದಿನಗಳ ಬಗ್ಗೆ ಕೇಳಿ. ಭಾರೀ ಮಳೆ ನಿರೀಕ್ಷೆ ಇದ್ದರೆ ಹೊಲದ ಕೆಲಸ ಮುಂದೂಡಿ. ಇದು ಮುನ್ಸೂಚನೆ.",
    },
    "soil": {
        "en": "Carry a soil-test report for the {crop} field to the Krishi Vigyan Kendra (KVK) in {place}. Ask which nutrient the crop needs at this stage. Wait for the officer to read the report before you apply manure.",
        "hi": "{crop} खेत की मिट्टी जांच रिपोर्ट {place} के कृषि विज्ञान केंद्र (KVK) ले जाएं। पूछें कि इस अवस्था में फसल को कौन सा पोषक चाहिए। रिपोर्ट पढ़े जाने से पहले खाद न डालें।",
        "kn": "{crop} ಜಮೀನಿನ ಮಣ್ಣು ಪರೀಕ್ಷಾ ವರದಿಯನ್ನು {place} ನ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ (KVK) ಗೆ ತೆಗೆದುಕೊಂಡು ಹೋಗಿ. ಈ ಹಂತದಲ್ಲಿ ಬೆಳೆಗೆ ಯಾವ ಪೋಷಕ ಬೇಕು ಎಂದು ಕೇಳಿ. ವರದಿ ಓದುವವರೆಗೆ ಗೊಬ್ಬರ ಹಾಕಬೇಡಿ.",
    },
    "knowledge_retriever": {
        "en": "Visit the Krishi Vigyan Kendra (KVK) in {place} for {crop} cultivation steps. Carry land records and ask about sowing, spacing, and the harvest method for this crop.",
        "hi": "{crop} की खेती के कदम जानने के लिए {place} के कृषि विज्ञान केंद्र (KVK) जाएं। जमीन के कागजात ले जाएं और बुवाई, दूरी और कटाई की विधि पूछें।",
        "kn": "{crop} ಬೆಳೆಯ ಕೃಷಿ ಹೆಜ್ಜೆಗಳಿಗೆ {place} ನ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ (KVK) ಗೆ ಹೋಗಿ. ಭೂ ದಾಖಲೆ ತೆಗೆದುಕೊಂಡು ಬಿತ್ತನೆ, ಅಂತರ ಮತ್ತು ಕಟಾವು ವಿಧಾನ ಕೇಳಿ.",
    },
}

_BANNED_TEXT = re.compile(r"%|₹|\bRs\b|\bINR\b|\d|Kisan Vikas", re.IGNORECASE)


def _crops() -> list[str]:
    path = BACKEND_ROOT / "data" / "knowledge" / "crop_registry.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    names = sorted(payload["crops"])
    missing = [name for name in names if name not in CROP_LABEL]
    if missing:
        raise SystemExit(f"Missing crop labels: {missing}")
    return names


def _loan_ids() -> set[str]:
    path = BACKEND_ROOT / "data" / "knowledge" / "loans.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {item["id"] for item in payload}


def _questions(agent: str, lang: str, intent: dict, crop: str, place: str) -> list[str]:
    crop_label = CROP_LABEL[crop][lang]
    place_label = PLACE_LABEL[place][lang]
    intent_label = intent[lang]
    prefix = PREFIX[agent][lang].format(intent=intent_label, crop=crop_label, place=place_label)
    tails = TAILS[agent][lang]
    rendered = []
    for index, tail in enumerate(tails):
        if agent == "finance" and intent["id"] == "crop_loan" and index == 0:
            rendered.append(prefix)
            continue
        extra = tail.format(intent=intent_label, crop=crop_label, place=place_label)
        rendered.append(f"{prefix}{extra}")
    return rendered


def _next_step(agent: str, lang: str, intent: dict, crop: str, place: str) -> str:
    return NEXT_STEP[agent][lang].format(
        crop=CROP_LABEL[crop][lang],
        place=PLACE_LABEL[place][lang],
        product=intent["product"][lang],
    )


def _check_next_step(text: str, where: str) -> None:
    if _BANNED_TEXT.search(text):
        raise SystemExit(f"Unsafe next step at {where}: {text}")
    for pattern in UNSAFE_CHEMICAL_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            raise SystemExit(f"Chemical pattern {pattern} matched next step at {where}")


def build_rows() -> dict[tuple[str, str], list[dict]]:
    crops = _crops()
    known_loans = _loan_ids()
    grouped: dict[tuple[str, str], list[dict]] = {}
    for agent in AGENTS:
        for lang in LANGS:
            rows: list[dict] = []
            seen: set[str] = set()
            for intent in INTENTS[agent]:
                if intent["record"] and intent["record"] not in known_loans:
                    raise SystemExit(f"Unknown loan id {intent['record']}")
                for crop in crops:
                    for place in PLACES:
                        for question in _questions(agent, lang, intent, crop, place):
                            key = " ".join(question.split())
                            if key in seen:
                                continue
                            seen.add(key)
                            step = _next_step(agent, lang, intent, crop, place)
                            _check_next_step(step, f"{agent}.{lang}")
                            rows.append(
                                {
                                    "agent": agent,
                                    "language": lang,
                                    "intent": intent["id"],
                                    "crop": crop,
                                    "place": place,
                                    "question": question,
                                    "linked_record_id": intent["record"],
                                    "next_step": step,
                                }
                            )
                            if len(rows) >= INDEX_COUNT + HOLDOUT_COUNT:
                                break
                        if len(rows) >= INDEX_COUNT + HOLDOUT_COUNT:
                            break
                    if len(rows) >= INDEX_COUNT + HOLDOUT_COUNT:
                        break
                if len(rows) >= INDEX_COUNT + HOLDOUT_COUNT:
                    break
            if len(rows) < INDEX_COUNT + HOLDOUT_COUNT:
                raise SystemExit(f"{agent}.{lang} produced {len(rows)} rows, need {INDEX_COUNT + HOLDOUT_COUNT}")
            grouped[(agent, lang)] = rows[: INDEX_COUNT + HOLDOUT_COUNT]
    return grouped


def _assign_ids(grouped: dict[tuple[str, str], list[dict]]) -> None:
    for (agent, lang), rows in grouped.items():
        for number, row in enumerate(rows, start=1):
            row["id"] = f"{agent}-{lang}-{number:05d}"
            row["split"] = "index" if number <= INDEX_COUNT else "holdout"


def _write(grouped: dict[tuple[str, str], list[dict]]) -> Path:
    root = bank_dir()
    root.mkdir(parents=True, exist_ok=True)
    for (agent, lang), rows in grouped.items():
        path = root / f"{agent}.{lang}.jsonl"
        lines = [json.dumps(row, ensure_ascii=False) for row in rows]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def _sanity(grouped: dict[tuple[str, str], list[dict]]) -> None:
    target = "What agricultural loan options are there for my tomato farm in Bengaluru?"
    finance_en = grouped[("finance", "en")]
    if not any(row["question"] == target and row["split"] == "index" for row in finance_en):
        raise SystemExit("Bengaluru tomato loan question is not in the finance English index")
    clear_cache()
    from app.orchestrator.question_bank import matching_agent

    if matching_agent(target, "en") != "finance":
        raise SystemExit("Bengaluru tomato loan question did not match finance")
    sample = next(row for row in grouped[("knowledge_retriever", "kn")] if row["split"] == "holdout")
    if not tokenize(sample["question"]):
        raise SystemExit("Kannada holdout question produced no tokens")


def main() -> None:
    grouped = build_rows()
    _assign_ids(grouped)
    root = _write(grouped)
    _sanity(grouped)
    print(f"Wrote {INDEX_COUNT + HOLDOUT_COUNT} rows x {len(grouped)} files in {root}")


if __name__ == "__main__":
    main()
