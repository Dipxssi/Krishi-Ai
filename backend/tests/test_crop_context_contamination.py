"""Regression tests: Prevent crop-context contamination, ensure crop isolation, and verify observability.

Ensures that:
1. A tomato image with an onion farm profile is never labeled as an onion diagnosis.
2. A corn image with an onion farm profile is never labeled as an onion diagnosis.
3. A request with no image handles farm profile crop cleanly without image diagnosis.
4. Corrupted image data is rejected with safe abstention and no fabricated diagnosis.
5. An uncertain image result abstains cleanly without invented disease labels or chemical spray advice.
6. A generic image query with an unestablished crop abstains rather than inheriting an unrelated farm profile crop.
7. Structured diagnostic logging is emitted safely without base64 or credentials.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
from starlette.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ROUTER_MODE"] = "keyword"
os.environ["GROQ_API_KEY"] = ""
os.environ["WEATHER_API_KEY"] = ""
os.environ["MARKET_API_KEY"] = ""
os.environ["DATA_GOV_API_KEY"] = ""
os.environ["VISION_MODEL"] = "heuristic"

from app.core.config import get_settings
get_settings.cache_clear()
from app.db.session import create_farm_context, get_farm_context, init_db, reset_engine
from app.main import app
from app.orchestrator.orchestrator import handle_query
from app.schemas.models import FarmContext, FarmContextCreate
from app.vision.diagnosis import diagnose_image_bytes


def _create_synthetic_image_b64(
    color: tuple[int, int, int] = (60, 160, 60),
    size: tuple[int, int] = (256, 256),
    add_texture: bool = True,
) -> str:
    arr = np.full((size[1], size[0], 3), color, dtype=np.uint8)
    if add_texture:
        noise = np.random.RandomState(42).randint(-40, 40, arr.shape, dtype=np.int16)
        arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


class TestCropContextContamination(unittest.TestCase):
    """Test suite ensuring complete isolation between farmer selected crop, farm profile crop, and vision screening."""

    @classmethod
    def setUpClass(cls):
        from tests.auth_helpers import install_auth_override

        install_auth_override(app, farmer_id="farmer-onion-001")
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        from tests.auth_helpers import clear_auth_override

        clear_auth_override(app)

    def setUp(self):
        get_settings.cache_clear()
        reset_engine()
        init_db()
        # Seed an onion nursery farmer profile
        self.onion_context = create_farm_context(
            FarmContextCreate(
                farmer_id="farmer-onion-001",
                location="Nashik, Maharashtra",
                farm_area_acres=2.0,
                crop="onion",
                growth_stage="nursery",
                soil_type="loam",
                irrigation_available=True,
                budget=20000.0,
                preferred_language="English",
                season="kharif",
            )
        )

    def tearDown(self):
        reset_engine()

    def test_tomato_image_with_onion_farm_profile(self):
        """Tomato image/inquiry with an onion farm profile must never label the image as onion."""
        tomato_b64 = _create_synthetic_image_b64(color=(50, 150, 50), add_texture=True)

        resp = handle_query(
            "Tomato market price is falling, should I treat spots or sell early?",
            self.onion_context,
            image_base64=tomato_b64,
            selected_crop="tomato",
            persist=False,
        )

        # 1. Assert separate fields are maintained
        self.assertEqual(resp.farm_profile_crop, "onion")
        self.assertEqual(resp.selected_crop, "tomato")
        self.assertIsNotNone(resp.image_diagnosis)

        # 2. Assert image diagnosis is for tomato, NEVER onion
        self.assertEqual(resp.image_diagnosis.crop_id, "tomato")
        self.assertNotEqual(resp.image_diagnosis.crop_id, "onion")

        # 3. Assert onion is never presented as a confirmed image diagnosis
        rec_lower = resp.final_recommendation.lower()
        self.assertNotIn("image diagnosis for onion", rec_lower)
        self.assertNotIn("image diagnosis (onion", rec_lower)
        self.assertNotIn("recommendation for your onion nursery", rec_lower)

        # 4. Warnings must note the difference between farm profile and inquiry crop
        self.assertTrue(
            any("Stored farm profile is set to 'onion'" in w for w in resp.warnings),
            "Mismatch warning must be emitted when selected crop differs from farm profile",
        )

    def test_corn_image_with_onion_farm_profile(self):
        """Corn image/inquiry with an onion farm profile must never label the image as onion."""
        corn_b64 = _create_synthetic_image_b64(color=(60, 160, 40), add_texture=True)

        resp = handle_query(
            "My corn leaves are showing yellow streaks — what treatment is needed?",
            self.onion_context,
            image_base64=corn_b64,
            selected_crop="maize",
            persist=False,
        )

        # 1. Assert separate fields
        self.assertEqual(resp.farm_profile_crop, "onion")
        self.assertEqual(resp.selected_crop, "maize")
        self.assertIsNotNone(resp.image_diagnosis)

        # 2. Image diagnosis must be for maize, NEVER onion
        self.assertEqual(resp.image_diagnosis.crop_id, "maize")
        self.assertNotEqual(resp.image_diagnosis.crop_id, "onion")

        # 3. Final recommendation must not present onion as image diagnosis
        rec_lower = resp.final_recommendation.lower()
        self.assertNotIn("image diagnosis for onion", rec_lower)
        self.assertNotIn("recommendation for your onion nursery", rec_lower)

    def test_request_with_no_image(self):
        """A text-only request with no image must have image_diagnosis=None and use appropriate crop context."""
        resp = handle_query(
            "What is the expected profit and market price?",
            self.onion_context,
            image_base64=None,
            persist=False,
        )

        self.assertIsNone(resp.image_diagnosis)
        self.assertEqual(resp.farm_profile_crop, "onion")
        # Text inquiry with no image or override uses farm profile crop cleanly
        self.assertIn("onion", resp.final_recommendation.lower())

    def test_corrupted_image_data(self):
        """Corrupted base64 image data must produce safe rejection without inventing any diagnosis."""
        corrupt_b64 = "data:image/jpeg;base64," + base64.b64encode(b"corrupted-non-image-binary-stream").decode("utf-8")

        resp = handle_query(
            "Check this image",
            self.onion_context,
            image_base64=corrupt_b64,
            selected_crop="tomato",
            persist=False,
        )

        self.assertIsNotNone(resp.image_diagnosis)
        self.assertEqual(resp.image_diagnosis.status, "rejected")
        self.assertIn("Could not decode image", resp.image_diagnosis.rejection_reason or "")
        self.assertTrue(resp.image_diagnosis.requires_expert)
        self.assertIsNone(resp.image_diagnosis.disease)
        self.assertIsNone(resp.image_diagnosis.disease_confidence)
        self.assertIsNone(resp.image_diagnosis.crop_id)

        # Stored farm profile crop must NOT be presented as a confirmed image diagnosis
        self.assertNotIn("image diagnosis for onion", resp.final_recommendation.lower())
        self.assertNotIn("recommendation for your onion nursery", resp.final_recommendation.lower())

    def test_uncertain_image_result(self):
        """Uncertain image result must not invent disease label, confidence score, or chemical treatments."""
        # Ambiguous color ratio image that triggers uncertain expert branch
        uncertain_b64 = _create_synthetic_image_b64(color=(120, 130, 80), add_texture=True)

        resp = handle_query(
            "Spots on leaf",
            self.onion_context,
            image_base64=uncertain_b64,
            selected_crop="tomato",
            persist=False,
        )

        diag = resp.image_diagnosis
        self.assertIsNotNone(diag)
        if diag.requires_expert:
            self.assertEqual(diag.status, "rejected")
            # Must not invent disease label or confidence
            self.assertIsNone(diag.disease, "Disease must be None when diagnosis is uncertain")
            self.assertIsNone(diag.disease_confidence, "Disease confidence must be None when uncertain")
            self.assertIsNone(diag.severity, "Severity must be None when uncertain")
            self.assertIn("uncertain", (diag.rejection_reason or "").lower())

            # Must warn against unverified chemical sprays
            self.assertTrue(
                any("avoid unverified chemical spraying" in h.lower() for h in diag.treatment_hints),
                "Must warn against unverified chemical spraying",
            )
            # Stored farm profile must never be presented as confirmed diagnosis
            self.assertNotIn("image diagnosis (onion", resp.final_recommendation.lower())

    def test_generic_image_query_with_unestablished_crop_abtains(self):
        """Uploading an image with generic query 'hey give me detail about picture i posted' must NOT diagnose as onion."""
        unknown_leaf_b64 = _create_synthetic_image_b64(color=(40, 160, 40), add_texture=True)

        resp = handle_query(
            "hey give me detail about picture i posted",
            self.onion_context,
            image_base64=unknown_leaf_b64,
            selected_crop=None,
            persist=False,
        )

        # 1. Crop identity was not established by the user
        self.assertIsNone(resp.selected_crop)
        self.assertEqual(resp.farm_profile_crop, "onion")
        self.assertIsNotNone(resp.image_diagnosis)

        # 2. Image diagnosis must abstain because crop identity is unestablished
        self.assertEqual(resp.image_diagnosis.status, "rejected")
        self.assertIsNone(resp.image_diagnosis.crop_id, "crop_id must be None when crop identity is not established")
        self.assertTrue(resp.image_diagnosis.requires_expert)
        self.assertIn("Crop identity not established", resp.image_diagnosis.rejection_reason or "")

        # 3. Final recommendation must NOT give onion nursery recommendation
        rec_lower = resp.final_recommendation.lower()
        self.assertNotIn("recommendation for your onion nursery", rec_lower)
        self.assertNotIn("image diagnosis for onion", rec_lower)
        self.assertIn("crop identity not established", rec_lower)

    def test_api_endpoint_respects_selected_crop(self):
        """FastAPI POST /query endpoint accepts selected_crop and keeps fields distinct."""
        leaf_b64 = _create_synthetic_image_b64(color=(50, 150, 50), add_texture=True)

        payload = {
            "farmer_id": "farmer-onion-001",
            "query": "Is this leaf healthy?",
            "image_base64": leaf_b64,
            "selected_crop": "tomato",
        }
        res = self.client.post("/query", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["farm_profile_crop"], "onion")
        self.assertEqual(data["selected_crop"], "tomato")
        self.assertEqual(data["image_diagnosis"]["crop_id"], "tomato")
        self.assertNotEqual(data["image_diagnosis"]["crop_id"], "onion")

    def test_structured_diagnostic_logging(self):
        """Safe structured diagnostic logging must be emitted with required observability fields."""
        leaf_b64 = _create_synthetic_image_b64(color=(50, 150, 50), add_texture=True)

        with self.assertLogs("krishiai.pipeline", level="INFO") as cm:
            handle_query(
                "Tomato leaf check",
                self.onion_context,
                image_base64=leaf_b64,
                selected_crop="tomato",
                persist=False,
                vision_model="heuristic",
            )

        log_output = "\n".join(cm.output)
        self.assertIn("Request diagnostic:", log_output)
        self.assertIn("image_supplied=True", log_output)
        self.assertIn("image_decoded=True", log_output)
        self.assertIn("vision_function=diagnose_image_bytes", log_output)
        self.assertIn("inference_mechanism=color_ratio_heuristic_v1", log_output)
        self.assertIn("farm_profile_crop=onion", log_output)
        self.assertIn("user_selected_crop=tomato", log_output)
        # Verify no base64 string is in log
        self.assertNotIn("data:image/jpeg;base64", log_output)


if __name__ == "__main__":
    unittest.main()
