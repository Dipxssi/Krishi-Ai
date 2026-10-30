"""Comprehensive test suite for KrishiAI human-friendly, multilingual agricultural
assistant and safety-aware expert referrals.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.orchestrator.orchestrator import handle_query
from app.schemas.models import FarmContext
from app.services.multilingual import (
    detect_language,
    get_disclaimer,
    get_ui_text,
    normalize_indic_script,
    normalize_language_code,
    transcript_needs_hindi_retry,
)
from app.services.nearby_help import (
    append_nearby_kvk_office,
    find_nearby_agricultural_help as find_nearby_help,
)
from app.services.safety_escalation import evaluate_escalation
from app.tools.agriculture import calculate_profit


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def base_context():
    return FarmContext(
        farmer_id="farmer-referral-test",
        location="Nashik",
        farm_area_acres=2.0,
        crop="tomato",
        soil_type="loamy",
        budget=40000.0,
        irrigation_available=True,
    )


class TestLanguageDetectionAndDisclaimers:
    def test_language_detection_kannada(self):
        query = "ನನ್ನ ಟೊಮ್ಯಾಟೊ ಗಿಡಗಳಿಗೆ ಯಾವ ಗೊಬ್ಬರ ಹಾಕಬೇಕು?"
        assert detect_language(query) == "kn"

    def test_language_detection_hindi(self):
        query = "टमाटर की फसल में अच्छी पैदावार के लिए क्या करें?"
        assert detect_language(query) == "hi"

    def test_icelandic_misread_of_hindi_needs_retry(self):
        garbage = "Ísum meõ kjá issú hei, kjá hó sakti hei, kïði hún yelú turn"
        assert transcript_needs_hindi_retry(garbage, "is") is True
        assert transcript_needs_hindi_retry("How do I protect my tomato crop?", "en") is False
        assert transcript_needs_hindi_retry("पत्तियाँ पीली हो रही हैं", "hi") is False

    def test_language_detection_english(self):
        query = "How do I care for my tomato plants?"
        assert detect_language(query) == "en"

    def test_language_detection_mixed_fallback(self):
        # When query is ambiguous numbers/punctuation, fallback to user preference
        assert detect_language("12345 ???", fallback="hi") == "hi"
        assert detect_language("12345 ???", fallback="kn") == "kn"
        assert detect_language("12345 ???", fallback="en") == "en"

    def test_disclaimers_localized_and_accurate(self):
        en_disc = get_disclaimer("en")
        hi_disc = get_disclaimer("hi")
        kn_disc = get_disclaimer("kn")

        assert "KrishiAI provides AI-generated guidance" in en_disc
        assert "KrishiAI" in hi_disc and "सलाह" in hi_disc
        assert "KrishiAI" in kn_disc and "ಸಲಹೆ" in kn_disc

    def test_normalize_indic_script_heals_telugu_code_points(self):
        raw = "ನನ್ನ ಟೋಮೇಟೊ ಕ್ರುಷಿಯన్ను విస్తరిసಲು నాను బయసుత్తೇನಿ ಮత్తు వದಕ್ಕಾగి నాను యావ సాధನಗಳన్ను ಬಳಸಬಹುದು ಮత్తు నాను అవుಗಳನು ಯಲ್ನ"
        healed = normalize_indic_script(raw)
        assert "ಕ್ರುಷಿಯನ್ನು" in healed
        assert "ವಿಸ್ತರಿಸಲು" in healed
        assert "ಸಾಧನಗಳನ್ನು" in healed
        assert detect_language(raw) == "kn"
        assert detect_language(healed) == "kn"

    def test_equipment_routing_for_kannada_expansion_query(self, base_context):
        from app.orchestrator.router import route_query
        raw = "ನನ್ನ ಟೋಮೇಟೊ ಕ್ರುಷಿಯన్ను విస్తరిసಲು నాను బయసుత్తೇನಿ ಮత్తు వದಕ್ಕಾగి నాನು యాವ సాధನಗಳన్ను ಬಳಸಬಹುದು ಮత్తు నాನು అవుಗಳನು ಯಲ್ನ"
        healed = normalize_indic_script(raw)
        selected, scores = route_query(healed)
        assert "equipment" in selected


class TestSafetyEscalationPolicy:
    def test_ordinary_growth_query_does_not_escalate(self, base_context):
        res = evaluate_escalation(
            query="How can I improve the growth of tomato plants?",
            context=base_context,
            language="en",
        )
        assert res.requires_escalation is False
        assert res.urgency == "low"

    def test_ordinary_market_query_does_not_escalate(self, base_context):
        res = evaluate_escalation(
            query="What is the current mandi market price of onion in Nashik?",
            context=base_context,
            language="en",
        )
        assert res.requires_escalation is False

    def test_high_impact_chemical_dosage_escalates(self, base_context):
        res = evaluate_escalation(
            query="How many ml per liter of Mancozeb should I mix and spray on my crop?",
            context=base_context,
            language="en",
        )
        assert res.requires_escalation is True
        assert res.urgency == "high"
        assert "chemical" in res.reason.lower() or "pesticide" in res.reason.lower()
        assert "do not spray" in res.safe_next_step.lower() or "label" in res.safe_next_step.lower() or "avoid" in res.safe_next_step.lower()

    def test_severe_disease_rapid_spread_escalates(self, base_context):
        res = evaluate_escalation(
            query="My tomato field has late blight rapidly spreading and entire crop is dying",
            context=base_context,
            language="en",
        )
        assert res.requires_escalation is True
        assert res.urgency == "high"
        assert "severe" in res.reason.lower() or "pathogen" in res.reason.lower()

    def test_hindi_chemical_mixing_escalates(self, base_context):
        res = evaluate_escalation(
            query="कीटनाशक की कितनी खुराक और घोल मिलाकर छिड़काव करें?",
            context=base_context,
            language="hi",
        )
        assert res.requires_escalation is True
        assert "कीटनाशक" in res.reason or "सुरक्षा" in res.reason or "रासायनिक" in res.reason

    def test_kannada_severe_disease_escalates(self, base_context):
        res = evaluate_escalation(
            query="ಟೊಮ್ಯಾಟೊ ಬೆಳೆಯಲ್ಲಿ ರೋಗ ತೀವ್ರವಾಗಿ ಹರಡುತ್ತಿದೆ ಗಿಡಗಳು ಒಣಗುತ್ತಿವೆ",
            context=base_context,
            language="kn",
        )
        assert res.requires_escalation is True
        assert res.urgency == "high"


class TestNearbyHelpVerification:
    def test_gps_coordinate_search_returns_sorted_by_real_distance(self):
        # Coordinates near Nashik KVK (lat 19.99, lon 73.78)
        resp = find_nearby_help(lat=19.95, lon=73.80, limit=3)
        assert resp["status"] == "ok"
        assert len(resp["results"]) > 0
        first = resp["results"][0]
        assert "Nashik" in first["district"] or "Nashik" in first["name"]
        assert first["distance_km"] is not None
        assert first["distance_km"] < 25.0
        assert first["verified"] is True
        assert "1800-180-1551" in first["helpline"]

    def test_district_name_search_returns_verified_kvk(self):
        resp = find_nearby_help(district="Dharwad")
        assert resp["status"] == "ok"
        assert len(resp["results"]) >= 1
        dharwad_kvk = next((r for r in resp["results"] if "Dharwad" in r["name"]), None)
        assert dharwad_kvk is not None
        assert dharwad_kvk["state"] == "Karnataka"
        assert "kvk.icar.gov.in" in dharwad_kvk["website"]
        assert dharwad_kvk["verified"] is True

    def test_pincode_search(self):
        # 580005 is Dharwad area
        resp = find_nearby_help(pincode="580005")
        assert resp["status"] == "ok"
        assert len(resp["results"]) >= 1
        assert "Dharwad" in resp["results"][0]["district"]

    def test_kvk_advice_appends_bengaluru_office_map(self):
        advice = (
            "4. When to Visit Your Local KVK or Extension Officer\n\n"
            "If the yellowing does not improve in 7–10 days, visit your local KVK."
        )
        text = append_nearby_kvk_office(advice, "Bengaluru, Karnataka", "en")
        assert "Bengaluru Urban" in text
        assert "GKVK, Bellary Road" in text
        assert "https://www.google.com/maps/search/?api=1&query=13.0768,77.5753" in text
        assert "Open live location" in text
        assert "Bengaluru Rural" not in text

    def test_kvk_advice_without_a_known_place_does_not_invent_an_office(self):
        advice = "Visit your local KVK before spraying."
        assert append_nearby_kvk_office(advice, "India", "en") == advice

    def test_unmatched_location_returns_fallback_notice_without_fabrication(self):
        # Query with unknown overseas or nonexistent district
        resp = find_nearby_help(district="NonExistentDistrictXYZ999")
        assert resp["status"] == "fallback"
        assert len(resp["results"]) == 0
        assert "Kisan Call Centre" in resp["fallback_notice"]
        assert "1800-180-1551" in resp["fallback_notice"]
        assert "kvk.icar.gov.in" in resp["fallback_notice"]
        # Never fabricate fake offices or assume Bengaluru
        assert "Bengaluru" not in resp.get("message", "")


class TestOrchestratorMultilingualAndCalculations:
    def test_profit_calculator_remains_intact(self):
        # Ensure crop calculator formulas still work precisely
        res = calculate_profit(
            area=2.0,
            expected_yield=10000.0,
            selling_price=25.0,
            seed_cost=10000.0,
            fertilizer_cost=15000.0,
            pesticide_cost=5000.0,
            labor_cost=20000.0,
        )
        assert res["revenue"] == 500000.0
        assert res["total_cost"] == 50000.0
        assert res["profit"] == 450000.0
        assert res["break_even_price"] == 2.5

    def test_kannada_query_returns_kannada_response_and_disclaimer(self, base_context, monkeypatch):
        from app.services import llm
        monkeypatch.setattr(llm, "is_llm_available", lambda: False)

        resp = handle_query(
            query="ಟೊಮ್ಯಾಟೊ ಬೆಳವಣಿಗೆ ಉತ್ತಮಗೊಳಿಸುವುದು ಹೇಗೆ?",
            context=base_context,
            persist=False,
        )
        assert resp.response_language == "kn"
        assert "ಕೃಷಿ AI" in resp.disclaimer
        # Tomato growth answer in Kannada contains Kannada headers
        assert "ಸೂರ್ಯನ ಬೆಳಕು" in resp.final_recommendation
        assert "ನೀರುಣಿಸುವಿಕೆ" in resp.final_recommendation

    def test_kannada_general_fallback_returns_kannada(self, base_context, monkeypatch):
        from app.services import llm
        monkeypatch.setattr(llm, "is_llm_available", lambda: False)

        resp = handle_query(
            query="ನನ್ನ ಬೆಳೆಗೆ ಕೀಟಗಳು ಬಂದಿವೆ ಯಾವ ಔಷಧ ಸಿಂಪಡಿಸಬೇಕು?",
            context=base_context,
            persist=False,
        )
        assert resp.response_language == "kn"
        assert "ಕೃಷಿ AI" in resp.disclaimer
        # Localized Kannada fallback contains Kannada text and not pure English
        assert any(c in resp.final_recommendation for c in "ಕೃಷಿ ಸಲಹೆ ಔಷಧಿ ಕೀಟನಾಶಕ ತಜ್ಞರ ಮಿತ್ರರೇ")

    def test_kannada_routing_and_romanized_detection(self):
        from app.orchestrator.router import route_query

        market_sel, _ = route_query("ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ ಟೊಮೆಟೊ ಧಾರಣೆ ಎಷ್ಟಿದೆ?")
        assert "market" in market_sel

        pest_sel, _ = route_query("ನನ್ನ ಬೆಳೆಗೆ ಕೀಟಗಳು ಬಂದಿವೆ")
        assert "crop_health" in pest_sel

        weather_sel, _ = route_query("ನಾಳೆ ಮಳೆ ಬರುತ್ತಾ?")
        assert "weather" in weather_sel

        # Romanized Kanglish detection
        assert detect_language("nanna belege keeta bandide enu madabeku?") == "kn"

    def test_hindi_query_returns_hindi_response_and_disclaimer(self, base_context, monkeypatch):
        from app.services import llm
        monkeypatch.setattr(llm, "is_llm_available", lambda: False)

        resp = handle_query(
            query="टमाटर की फसल में पौधों का विकास कैसे सुधारें?",
            context=base_context,
            persist=False,
        )
        assert resp.response_language == "hi"
        assert "KrishiAI" in resp.disclaimer
        # Tomato growth answer in Hindi contains Devanagari headers
        assert "धूप" in resp.final_recommendation
        assert "सिंचाई" in resp.final_recommendation


class TestApiHelpEndpoint:
    def test_api_nearby_help_with_coords(self, test_client):
        res = test_client.get("/help/nearby?lat=12.97&lon=77.59")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert len(data["results"]) > 0
        assert "distance_km" in data["results"][0]

    def test_api_nearby_help_with_district(self, test_client):
        res = test_client.get("/help/nearby?district=Pune")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert any("Pune" in r["district"] or "Pune" in r["name"] for r in data["results"])

    def test_api_nearby_help_missing_params_returns_fallback_notice(self, test_client):
        res = test_client.get("/help/nearby")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "fallback"
        assert "Kisan Call Centre" in data["fallback_notice"]
