"""End-to-end regression tests verifying that unsafe chemical recommendations,
application rates, spray schedules, and unconfirmed disease labels are strictly
blocked at the final response boundary when image diagnosis is unconfirmed,
while ordinary text-only farm management advice continues to work normally.
"""

from __future__ import annotations

import base64
import io
from PIL import Image
import pytest

from app.orchestrator.orchestrator import handle_query
from app.schemas.models import FarmContext
from app.services import llm


from app.services import live_market, live_weather


def _make_synthetic_b64(color=(30, 160, 40), size=(100, 100)) -> str:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


class TestFinalResponseSafetyBoundary:
    @pytest.fixture(autouse=True)
    def _setup_context(self, monkeypatch):
        monkeypatch.setattr(live_weather, "fetch_weather_live", lambda *args, **kwargs: None)
        monkeypatch.setattr(live_market, "fetch_market_price_live", lambda *args, **kwargs: None)
        monkeypatch.setenv("ROUTER_MODE", "keyword")
        monkeypatch.setenv("VISION_MODEL", "heuristic")
        from app.core.config import get_settings
        get_settings.cache_clear()
        self.context = FarmContext(
            farmer_id="farmer-safety-test",
            location="Nashik",
            farm_area_acres=2.5,
            crop="onion",
            growth_stage="vegetative",
            soil_type="black",
            budget=50000.0,
            irrigation_available=True,
        )

    def test_rejected_image_blocks_fungicide_and_spray_schedules_at_boundary(self, monkeypatch):
        """When an image diagnosis is rejected, unsafe LLM advice mentioning fungicides,
        dosages, spray schedules, or unconfirmed disease labels must NEVER reach final response.
        """
        dangerous_draft = (
            "Based on the leaf image, the crop has early blight and late blight. "
            "Apply Mancozeb 75 WP at 2.5 g/L or Copper Oxychloride 50 WP. "
            "Follow a spray schedule of every 7-10 days. Ensure thorough foliar spray coverage."
        )
        monkeypatch.setattr(llm, "is_llm_available", lambda: True)
        monkeypatch.setattr(llm, "generate", lambda *args, **kwargs: dangerous_draft)

        # Flat green synthetic image triggers rejection in live quality gating
        b64 = _make_synthetic_b64(color=(20, 180, 20), size=(80, 80))

        resp = handle_query(
            query="My tomato leaf has brown spots, what should I spray?",
            context=self.context,
            image_base64=b64,
            selected_crop="tomato",
            persist=False,
        )

        assert resp.image_diagnosis is not None
        assert resp.image_diagnosis.status == "rejected"

        final_rec = resp.final_recommendation.lower()

        # Assert no chemical fungicide or pesticide names leaked
        assert "mancozeb" not in final_rec
        assert "copper oxychloride" not in final_rec
        assert "copper" not in final_rec

        # Assert no dosage or application rates leaked
        assert "2.5 g/l" not in final_rec
        assert "g/l" not in final_rec

        # Assert no spray schedules leaked
        assert "every 7-10 days" not in final_rec
        assert "spray schedule" not in final_rec
        assert "foliar spray" not in final_rec

        # Assert no unconfirmed disease claims leaked
        assert "early blight" not in final_rec
        assert "late blight" not in final_rec

        # Assert structured safe unconfirmed advice is present
        assert "image diagnosis: unconfirmed" in final_rec
        assert "safe non-chemical next steps" in final_rec
        assert "referral" in final_rec or "krishi vigyan kendra" in final_rec

        # Assert dashboard disease risk is suppressed
        assert resp.decision_score is not None
        assert resp.decision_score.disease_risk is None

        # Assert structured recommendation requires human review
        assert resp.structured_recommendation is not None
        assert resp.structured_recommendation.human_review_required is True

        # Assert agent results are also scrubbed
        for ar in resp.agent_results:
            ar_text = ar.recommendation.lower()
            assert "mancozeb" not in ar_text
            assert "copper oxychloride" not in ar_text

    def test_requires_expert_image_blocks_chemical_dosages_and_bacterial_speck(self, monkeypatch):
        """When an image requires expert review, LLM cannot introduce chemical treatments."""
        dangerous_draft = (
            "Symptoms indicate bacterial speck. Apply Copper-based bactericide at 3 g/L "
            "or Streptocycline spray. Repeat every 5 days."
        )
        monkeypatch.setattr(llm, "is_llm_available", lambda: True)
        monkeypatch.setattr(llm, "generate", lambda *args, **kwargs: dangerous_draft)

        b64 = _make_synthetic_b64(color=(150, 100, 30), size=(100, 100))

        resp = handle_query(
            query="Check this leaf spot",
            context=self.context,
            image_base64=b64,
            selected_crop=None,  # Unestablished crop identity
            persist=False,
        )

        final_rec = resp.final_recommendation.lower()
        assert "bacterial speck" not in final_rec
        assert "copper" not in final_rec
        assert "streptocycline" not in final_rec
        assert "3 g/l" not in final_rec
        assert "repeat every 5 days" not in final_rec
        assert resp.decision_score.disease_risk is None

    def test_text_only_query_preserves_ordinary_farm_advice(self, monkeypatch):
        """Text-only queries without an uploaded image continue to provide normal advisory."""
        normal_draft = (
            "For onion cultivation in Nashik, maintain balanced nitrogen application. "
            "Irrigate at 7-10 day intervals during bulb enlargement."
        )
        monkeypatch.setattr(llm, "is_llm_available", lambda: True)
        monkeypatch.setattr(llm, "generate", lambda *args, **kwargs: normal_draft)

        resp = handle_query(
            query="What is the irrigation schedule for onion?",
            context=self.context,
            image_base64=None,
            persist=False,
        )

        assert resp.image_diagnosis is None
        # Normal farm advice is preserved, not forced into image abstention
        assert "irrigate at 7-10 day intervals" in resp.final_recommendation.lower()
        assert "image diagnosis: unconfirmed" not in resp.final_recommendation.lower()
        # Decision score includes text-based disease risk heuristic
        assert resp.decision_score is not None
        assert resp.decision_score.disease_risk is not None

    def test_multi_intent_query_separates_unrelated_farm_advice_from_unconfirmed_image(self, monkeypatch):
        """When user asks for market prices and attaches an unconfirmed leaf image,
        market advice is preserved under Farm Management Advisory while leaf diagnosis
        is kept separate and free of chemical sprays.
        """
        def fake_generate(prompt, **kwargs):
            if "market" in prompt.lower():
                return "Tomato modal price at Nashik is ₹42.0/kg with steady demand."
            return "Early blight suspected. Spray Mancozeb at 2 g/L."

        monkeypatch.setattr(llm, "is_llm_available", lambda: True)
        monkeypatch.setattr(llm, "generate", fake_generate)

        b64 = _make_synthetic_b64(color=(20, 180, 20), size=(60, 60))

        resp = handle_query(
            query="What is tomato market price in Nashik today and check this leaf photo?",
            context=self.context,
            image_base64=b64,
            selected_crop="tomato",
            persist=False,
        )

        final_rec = resp.final_recommendation
        assert "### Image Diagnosis: Unconfirmed" in final_rec
        assert "Safe Non-Chemical Next Steps" in final_rec
        # Unrelated market advice is clearly separated
        assert "### Farm Management Advisory" in final_rec
        # No chemical spray leaked into final response
        assert "mancozeb" not in final_rec.lower()
        assert "2 g/l" not in final_rec.lower()
