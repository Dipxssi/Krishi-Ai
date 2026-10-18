"""Automated tests for vision image-upload, validation, rejection, feature parity, and abstention policies.

Tests are strictly divided into two independent classes:
1. TestLiveProductionVisionEndpoint: Verifies the live production heuristic pipeline, image-quality gating,
   abstention policies, and FastAPI contracts. Confirms that the live endpoint does NOT load or invoke
   the offline ElasticNet candidate model.
2. TestOfflineElasticNetCandidatePipeline: Verifies the offline ElasticNet candidate feature extraction,
   exact 1,606 feature dimensional parity, and safe artifact loading / error handling.

All tests use deterministic synthetic inputs. No previous test manifests or real-world accuracy claims are used.
"""

from __future__ import annotations

import base64
import io
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from starlette.testclient import TestClient

from app.main import app
from app.vision.diagnosis import _image_quality_score, diagnose_image_bytes
from app.vision.model_loader import load_elasticnet_artifact
from ml.src.features import extract_color_features, extract_features_from_image, extract_hog_features


def _create_test_image_base64(
    color: tuple[int, int, int] = (60, 160, 60),
    size: tuple[int, int] = (256, 256),
    add_texture: bool = True,
) -> str:
    """Generate a base64 encoded synthetic test image deterministically."""
    arr = np.full((size[1], size[0], 3), color, dtype=np.uint8)
    if add_texture:
        # Add realistic spread and contrast so quality score passes
        noise = np.random.RandomState(42).randint(-40, 40, arr.shape, dtype=np.int16)
        arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


# =============================================================================
# Path 1: Live Production Vision Endpoint & Gating Tests
# =============================================================================
class TestLiveProductionVisionEndpoint(unittest.TestCase):
    """Test suite verifying the live production heuristic path, image-quality gating, and safe abstention."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_live_endpoint_does_not_invoke_elasticnet_model(self):
        """Confirm that the live endpoint does not load or invoke the offline ElasticNet candidate."""
        leaf_b64 = _create_test_image_base64(color=(40, 160, 40), add_texture=True)
        with patch("app.vision.model_loader.load_elasticnet_artifact") as mock_loader:
            res = diagnose_image_bytes(leaf_b64, crop_hint="tomato")
            self.assertEqual(res.status, "ok")
            mock_loader.assert_not_called()

    # --- Quality Gating Unit Tests ---
    def test_dark_synthetic_image_rejection(self):
        """Very dark synthetic image (near-black) must be rejected by the quality gate."""
        dark_img = Image.new("RGB", (128, 128), (15, 15, 15))
        score = _image_quality_score(dark_img)
        self.assertLess(score, 0.65, "Dark image must score below the 0.65 threshold")

        dark_b64 = _create_test_image_base64(color=(15, 15, 15), add_texture=False)
        res = diagnose_image_bytes(dark_b64, crop_hint="tomato")
        self.assertEqual(res.status, "rejected")
        self.assertIn("quality too low", (res.rejection_reason or "").lower())
        self.assertTrue(res.requires_expert)

    def test_overexposed_synthetic_image_rejection(self):
        """Overexposed synthetic image (near-white / blown out) must be rejected by the quality gate."""
        white_img = Image.new("RGB", (128, 128), (250, 250, 250))
        score = _image_quality_score(white_img)
        self.assertLess(score, 0.65, "Overexposed image must score below the 0.65 threshold")

        white_b64 = _create_test_image_base64(color=(250, 250, 250), add_texture=False)
        res = diagnose_image_bytes(white_b64, crop_hint="tomato")
        self.assertEqual(res.status, "rejected")
        self.assertIn("quality too low", (res.rejection_reason or "").lower())
        self.assertTrue(res.requires_expert)

    def test_flat_color_synthetic_image_rejection(self):
        """Flat uniform color image (zero channel spread) must be rejected by the quality gate."""
        flat_img = Image.new("RGB", (128, 128), (80, 160, 80))
        score = _image_quality_score(flat_img)
        self.assertLess(score, 0.65, "Flat image with zero spread must score below 0.65")

        flat_b64 = _create_test_image_base64(color=(80, 160, 80), add_texture=False)
        res = diagnose_image_bytes(flat_b64, crop_hint="tomato")
        self.assertEqual(res.status, "rejected")
        self.assertTrue(res.requires_expert)

    def test_low_contrast_synthetic_image_rejection(self):
        """Low-contrast synthetic image (very narrow channel spread) must be penalized."""
        # Channels vary only between 110 and 118
        arr = np.random.RandomState(42).randint(110, 118, (128, 128, 3), dtype=np.uint8)
        low_contrast_img = Image.fromarray(arr)
        score = _image_quality_score(low_contrast_img)
        self.assertLess(score, 0.65, "Low-contrast image must score below 0.65")

    def test_textured_synthetic_image_passes_gating(self):
        """Well-balanced synthetic image with daylight exposure and adequate spread must pass gating."""
        textured_b64 = _create_test_image_base64(color=(80, 160, 80), add_texture=True)
        img_data = base64.b64decode(textured_b64.split(",", 1)[-1])
        good_img = Image.open(io.BytesIO(img_data))
        score = _image_quality_score(good_img)
        self.assertGreaterEqual(score, 0.65)

    # --- Input Validation & Routing Tests ---
    def test_invalid_base64_string_rejection(self):
        """Malformed base64 payload must be rejected gracefully with requires_expert=True."""
        res = diagnose_image_bytes("not-a-valid-base64-payload!!!", crop_hint="tomato")
        self.assertEqual(res.status, "rejected")
        self.assertIn("Could not decode image", res.rejection_reason or "")
        self.assertEqual(res.image_quality_score, 0.0)
        self.assertTrue(res.requires_expert)

    def test_corrupted_image_bytes_rejection(self):
        """Valid base64 but non-image bytes must be rejected gracefully."""
        non_image_b64 = base64.b64encode(b"This is just plain text, not an image.").decode("utf-8")
        res = diagnose_image_bytes(non_image_b64, crop_hint="tomato")
        self.assertEqual(res.status, "rejected")
        self.assertIn("Could not decode image", res.rejection_reason or "")
        self.assertTrue(res.requires_expert)

    def test_unsupported_crop_routing_rejection(self):
        """Unsupported crop or unidentifiable crop must be rejected with extension referral."""
        leaf_b64 = _create_test_image_base64(color=(40, 150, 40), add_texture=True)
        res = diagnose_image_bytes(leaf_b64, crop_hint="unsupported_tropical_crop")
        self.assertEqual(res.status, "rejected")
        self.assertIn("Crop not supported", res.rejection_reason or "")
        self.assertTrue(res.requires_expert)

    def test_supported_crop_diagnosis(self):
        """Supported crop with good quality image must proceed and assign crop_id."""
        leaf_b64 = _create_test_image_base64(color=(40, 160, 40), add_texture=True)
        res = diagnose_image_bytes(leaf_b64, crop_hint="tomato")
        self.assertGreaterEqual(res.image_quality_score, 0.65)
        self.assertEqual(res.crop_id, "tomato")
        self.assertIsNotNone(res.disease)

    # --- Safe Abstention & No Chemical Spray Tests ---
    def test_uncertain_diagnosis_abstention_clears_disease_and_forbids_chemical_sprays(self):
        """Uncertain diagnosis must not return a confirmed disease name and must forbid unverified sprays."""
        leaf_b64 = _create_test_image_base64(color=(120, 130, 80), add_texture=True)
        res = diagnose_image_bytes(leaf_b64, crop_hint="tomato")
        if res.requires_expert:
            self.assertEqual(res.status, "rejected")
            # Disease name must NOT be displayed as confirmed when abstaining
            self.assertIsNone(res.disease, "Disease name must be None when diagnosis is rejected/uncertain.")
            self.assertIsNone(res.disease_confidence)
            self.assertIsNone(res.severity)
            self.assertIn("uncertain", (res.rejection_reason or "").lower())
            # Must explicitly warn against unverified chemical spraying
            self.assertTrue(
                any("avoid unverified chemical spraying" in h.lower() for h in res.treatment_hints),
                "Uncertain diagnosis must warn against unverified chemical spraying.",
            )
            # Must route to KVK or extension specialist
            self.assertTrue(
                any("krishi vigyan kendra" in h.lower() for h in res.treatment_hints),
                "Uncertain diagnosis must route to local agricultural extension (KVK).",
            )
            # Must not suggest specific chemical pesticides
            self.assertFalse(
                any("mancozeb" in h.lower() or "chlorothalonil" in h.lower() for h in res.treatment_hints),
                "Uncertain diagnosis must not suggest specific chemical sprays.",
            )

    def test_runtime_inference_error_does_not_become_successful_diagnosis(self):
        """Inference runtime errors must produce structured rejection, never a successful-looking diagnosis."""
        leaf_b64 = _create_test_image_base64(color=(40, 160, 40), add_texture=True)
        with patch("app.vision.diagnosis._image_quality_score", side_effect=RuntimeError("Simulated inference crash")):
            res = diagnose_image_bytes(leaf_b64, crop_hint="tomato")
            self.assertEqual(res.status, "rejected")
            self.assertTrue(res.requires_expert)
            self.assertIsNone(res.disease)
            self.assertIn("Simulated inference crash", res.rejection_reason or "")
            self.assertTrue(any("avoid unverified chemical spraying" in h.lower() for h in res.treatment_hints))

    def test_api_endpoint_crop_image_diagnosis(self):
        """Test FastAPI endpoint /crop/image-diagnosis directly."""
        # 1. Invalid payload
        resp_invalid = self.client.post("/crop/image-diagnosis", json={"image_base64": "invalid", "crop_hint": "tomato"})
        self.assertEqual(resp_invalid.status_code, 200)
        data_invalid = resp_invalid.json()
        self.assertEqual(data_invalid["status"], "rejected")
        self.assertTrue(data_invalid["requires_expert"])

        # 2. Quality rejected payload
        black_b64 = _create_test_image_base64(color=(0, 0, 0), add_texture=False)
        resp_black = self.client.post("/crop/image-diagnosis", json={"image_base64": black_b64, "crop_hint": "tomato"})
        self.assertEqual(resp_black.status_code, 200)
        data_black = resp_black.json()
        self.assertEqual(data_black["status"], "rejected")
        self.assertLess(data_black["image_quality_score"], 0.65)

        # 3. Valid leaf payload
        leaf_b64 = _create_test_image_base64(color=(50, 170, 50), add_texture=True)
        resp_leaf = self.client.post("/crop/image-diagnosis", json={"image_base64": leaf_b64, "crop_hint": "tomato"})
        self.assertEqual(resp_leaf.status_code, 200)
        data_leaf = resp_leaf.json()
        self.assertEqual(data_leaf["crop_id"], "tomato")
        self.assertIn("status", data_leaf)


# =============================================================================
# Path 2: Offline ElasticNet Candidate Artifacts & Feature Pipeline Tests
# =============================================================================
class TestOfflineElasticNetCandidatePipeline(unittest.TestCase):
    """Test suite verifying offline ElasticNet candidate feature extraction, parity, and artifact safety."""

    def test_candidate_feature_parity_with_training_pipeline(self):
        """Verify candidate feature extraction exactly matches training: 1,606 dims, order, and fitted scaler."""
        img = Image.fromarray(np.random.RandomState(42).randint(0, 255, (128, 128, 3), dtype=np.uint8))

        color_feat = extract_color_features(img, h_bins=16, s_bins=8, v_bins=8)
        self.assertEqual(color_feat.shape, (38,), "Color features must be 16 H + 8 S + 8 V + 3 mean + 3 std = 38")

        hog_feat = extract_hog_features(img, target_size=(128, 128), cell_size=16, n_bins=8)
        self.assertEqual(hog_feat.shape, (1568,), "HOG features must be 7x7 blocks x 32 bin components = 1568")

        total_feat = extract_features_from_image(img)
        self.assertEqual(total_feat.shape, (1606,), "Total feature vector must be exactly 1606 dims")
        self.assertEqual(total_feat.dtype, np.float32, "Feature dtype must be float32")

        # Feature order check: color features followed by HOG features
        expected_combined = np.concatenate([color_feat, hog_feat]).astype(np.float32)
        np.testing.assert_array_almost_equal(total_feat, expected_combined, decimal=5)

        # Fitted scaler alignment check
        artifact = load_elasticnet_artifact()
        scaler = artifact["scaler"]
        model = artifact["model"]

        self.assertEqual(scaler.n_features_in_, 1606, "Fitted StandardScaler must expect 1606 features")
        self.assertEqual(scaler.mean_.shape, (1606,))
        self.assertEqual(model.coef_.shape, (17, 1606), "Model coef_ must match (17 classes, 1606 features)")

        scaled_feat = scaler.transform(total_feat.reshape(1, -1))
        self.assertEqual(scaled_feat.shape, (1, 1606))

    def test_candidate_safe_model_artifact_loading(self):
        """Candidate ElasticNet bundle must load safely and contain required keys and metadata."""
        bundle = load_elasticnet_artifact()
        self.assertIn("model", bundle)
        self.assertIn("scaler", bundle)
        self.assertIn("classes", bundle)
        self.assertIn("feature_config", bundle)
        self.assertEqual(len(bundle["classes"]), 17)
        self.assertTrue(bundle.get("is_fitted", False))

    def test_candidate_model_loading_missing_file_failure(self):
        """Missing model file must raise FileNotFoundError rather than fabricating a diagnosis."""
        with self.assertRaises(FileNotFoundError) as ctx:
            load_elasticnet_artifact("non_existent_path_to_model.joblib")
        self.assertIn("Refusing to fabricate automated diagnosis", str(ctx.exception))

    def test_candidate_model_loading_incompatible_artifact_failure(self):
        """Corrupt or incompatible bundle must raise ValueError/TypeError rather than fabricating diagnosis."""
        import joblib

        # 1. Missing required key
        dummy_missing_scaler = {"model": object(), "classes": [0], "feature_config": {}}
        tmp_path = Path("/tmp/test_dummy_missing.joblib")
        joblib.dump(dummy_missing_scaler, tmp_path)
        try:
            with self.assertRaises(ValueError) as ctx:
                load_elasticnet_artifact(tmp_path)
            self.assertIn("missing required keys", str(ctx.exception))
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        # 2. Object missing predict_proba
        dummy_no_predict = {
            "model": object(),
            "scaler": object(),
            "classes": [0],
            "feature_config": {"total_feature_dim": 1606},
        }
        joblib.dump(dummy_no_predict, tmp_path)
        try:
            with self.assertRaises(TypeError) as ctx:
                load_elasticnet_artifact(tmp_path)
            self.assertIn("missing 'predict_proba'", str(ctx.exception))
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


if __name__ == "__main__":
    unittest.main()
