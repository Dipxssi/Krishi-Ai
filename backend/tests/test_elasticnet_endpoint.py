"""Automated test suite for ElasticNet test inference endpoint and safety validation."""

from __future__ import annotations

import base64
import io
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.schemas.models import (
    ElasticNetDiagnosisRequest,
    ElasticNetDiagnosisResponse,
    ImageDiagnosisResult,
)
from app.vision.diagnosis import is_image_diagnosis_unconfirmed
from app.vision.elasticnet_service import (
    clear_bundle_cache,
    run_elasticnet_diagnosis,
    validate_and_decode_image,
)
from app.vision.model_loader import load_elasticnet_artifact
from ml.src.config import TARGET_CLASSES
from ml.src.features import extract_features_from_image


@pytest.fixture
def client() -> TestClient:
    from tests.auth_helpers import clear_auth_override, install_auth_override

    install_auth_override(app)
    try:
        yield TestClient(app)
    finally:
        clear_auth_override(app)


def create_test_image_b64(
    size: tuple[int, int] = (128, 128),
    color: tuple[int, int, int] = (80, 140, 50),
    fmt: str = "JPEG",
) -> str:
    """Helper to generate a valid base64 image string."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# 1. Successful inference on valid image
def test_elasticnet_successful_inference(client: TestClient):
    b64 = create_test_image_b64()
    resp = client.post("/crop/elasticnet-diagnosis", json={"image_base64": b64})
    assert resp.status_code == 200

    data = resp.json()
    assert "status" in data
    assert data["status"] in ("accepted", "rejected")
    assert "confidence" in data
    assert data["confidence_is_calibrated"] is False
    assert "predicted_class" in data
    assert "top_3" in data
    assert len(data["top_3"]) == 3
    assert data["inference_time_ms"] > 0
    assert data["model_version"] == "elasticnet_plantdisease_best"


# 2. Correct class mapping
def test_elasticnet_class_mapping(client: TestClient):
    b64 = create_test_image_b64()
    resp = client.post(
        "/crop/elasticnet-diagnosis",
        json={"image_base64": b64, "crop_hint": "maize"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Verify top-3 prediction item fields
    for item in data["top_3"]:
        assert 0 <= item["class_idx"] < 17
        assert item["crop"] in ("maize", "potato", "tomato")
        assert item["confidence_is_calibrated"] is False
        assert 0.0 <= item["confidence"] <= 1.0

        # Match against TARGET_CLASSES metadata
        meta = TARGET_CLASSES[item["class_idx"]]
        assert item["display_name"] == meta["display_name"]
        assert item["crop"] == meta["crop"]
        assert item["disease"] == meta["disease"]


# 3. Preprocessing and feature-dimension compatibility
def test_elasticnet_feature_dimension_and_scaling():
    img = Image.new("RGB", (128, 128), color=(60, 160, 70))
    bundle = load_elasticnet_artifact()

    feat = extract_features_from_image(img, config=bundle["feature_config"])
    assert feat.shape == (1606,)
    assert feat.dtype.name.startswith("float")

    # Scaler transformation
    scaler = bundle["scaler"]
    assert scaler.n_features_in_ == 1606
    scaled = scaler.transform(feat.reshape(1, -1))
    assert scaled.shape == (1, 1606)

    # Model predict_proba
    probs = bundle["model"].predict_proba(scaled)
    assert probs.shape == (1, 17)
    assert pytest.approx(probs.sum(), abs=1e-4) == 1.0


# 4. Missing or corrupt model artifact
def test_elasticnet_missing_model_artifact():
    b64 = create_test_image_b64()
    req = ElasticNetDiagnosisRequest(image_base64=b64)

    # Test missing file
    res = run_elasticnet_diagnosis(req, artifact_path="nonexistent_artifact.joblib")
    assert res.status == "rejected"
    assert res.requires_expert is True
    assert "unavailable" in res.rejection_reason.lower()

    # Test corrupt bundle
    with tempfile.NamedTemporaryFile(suffix=".joblib") as tmp:
        tmp.write(b"not-a-valid-joblib-bundle")
        tmp.flush()
        clear_bundle_cache()
        res_corrupt = run_elasticnet_diagnosis(req, artifact_path=tmp.name)
        assert res_corrupt.status == "rejected"
        assert res_corrupt.requires_expert is True
        assert "unavailable" in res_corrupt.rejection_reason.lower()
        clear_bundle_cache()


# 5. Invalid image and unsupported input
def test_elasticnet_invalid_image_inputs(client: TestClient):
    # Empty string
    r1 = client.post("/crop/elasticnet-diagnosis", json={"image_base64": ""})
    assert r1.status_code == 200
    assert r1.json()["status"] == "rejected"
    assert "empty" in r1.json()["rejection_reason"].lower()

    # Corrupt base64
    r2 = client.post("/crop/elasticnet-diagnosis", json={"image_base64": "invalid-base64!!!"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "rejected"
    assert "could not decode base64" in r2.json()["rejection_reason"].lower()

    # Image payload too small (< 100 bytes)
    tiny_b64 = base64.b64encode(b"tiny").decode("utf-8")
    r3 = client.post("/crop/elasticnet-diagnosis", json={"image_base64": tiny_b64})
    assert r3.status_code == 200
    assert r3.json()["status"] == "rejected"
    assert "too small" in r3.json()["rejection_reason"].lower()

    # Image dimensions too small (< 32x32)
    small_b64 = create_test_image_b64(size=(16, 16))
    r4 = client.post("/crop/elasticnet-diagnosis", json={"image_base64": small_b64})
    assert r4.status_code == 200
    assert r4.json()["status"] == "rejected"
    assert "too small" in r4.json()["rejection_reason"].lower()


# 6. Low-confidence rejection / abstention
def test_elasticnet_low_confidence_rejection(client: TestClient):
    # A noisy image yields confidence ~0.49, falling below the default 0.60 threshold
    arr = np.random.RandomState(42).randint(0, 255, (128, 128, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    resp = client.post(
        "/crop/elasticnet-diagnosis",
        json={"image_base64": b64, "confidence_threshold": 0.60},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["requires_expert"] is True
    assert "low model confidence" in data["rejection_reason"].lower()
    assert "uncalibrated" in data["rejection_reason"].lower()


# 7. Unsupported plants and out-of-distribution inputs
def test_elasticnet_unsupported_crop_rejection(client: TestClient):
    b64 = create_test_image_b64()
    for unsupported in ["apple", "grape", "blueberry", "cotton", "rice", "wheat", "parthenium"]:
        resp = client.post(
            "/crop/elasticnet-diagnosis",
            json={"image_base64": b64, "crop_hint": unsupported},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["requires_expert"] is True
        assert f"crop '{unsupported}' is outside" in data["rejection_reason"].lower()


# 8. Cross-crop conflict rejection
def test_elasticnet_cross_crop_conflict(client: TestClient):
    # A green image triggers Maize (Corn Healthy). When user specifies 'tomato', it must flag conflict.
    b64 = create_test_image_b64(color=(60, 160, 70))
    resp = client.post(
        "/crop/elasticnet-diagnosis",
        json={"image_base64": b64, "crop_hint": "tomato"},
    )
    assert resp.status_code == 200
    data = resp.json()
    if data["crop_id"] != "tomato":
        assert data["status"] == "rejected"
        assert data["requires_expert"] is True
        assert "crop conflict" in data["rejection_reason"].lower()


# 9. Prevention of unsafe disease-specific chemical advice after rejection
def test_elasticnet_safety_treatment_hints_on_rejection(client: TestClient):
    # Use brownish image with confidence ~0.979, requiring threshold 0.99
    b64 = create_test_image_b64(color=(140, 110, 80))
    resp = client.post(
        "/crop/elasticnet-diagnosis",
        json={"image_base64": b64, "confidence_threshold": 0.99},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["requires_expert"] is True

    # Treatment hints must NOT contain chemical pesticide/fungicide advice
    hints_text = " ".join(data["treatment_hints"]).lower()
    assert "avoid unverified chemical spraying" in hints_text
    assert "mancozeb" not in hints_text
    assert "copper oxychloride" not in hints_text
    assert "carbendazim" not in hints_text

    # Verify downstream safety adapter
    mapped_result = ImageDiagnosisResult(
        status="rejected",
        rejection_reason=data["rejection_reason"],
        image_quality_score=0.0,
        crop_id=data.get("crop_id"),
        disease=data.get("disease"),
        disease_confidence=data.get("confidence"),
        requires_expert=data["requires_expert"],
    )
    assert is_image_diagnosis_unconfirmed(mapped_result) is True


# 10. API response schema and error handling
def test_elasticnet_schema_and_boundaries(client: TestClient):
    b64 = create_test_image_b64()

    # Invalid confidence threshold > 1.0 (Pydantic validation error HTTP 422)
    bad_resp = client.post(
        "/crop/elasticnet-diagnosis",
        json={"image_base64": b64, "confidence_threshold": 1.5},
    )
    assert bad_resp.status_code == 422

    # Negative confidence threshold < 0.0
    neg_resp = client.post(
        "/crop/elasticnet-diagnosis",
        json={"image_base64": b64, "confidence_threshold": -0.2},
    )
    assert neg_resp.status_code == 422

    # Production endpoint unchanged
    prod_resp = client.post(
        "/crop/image-diagnosis",
        json={"image_base64": b64, "crop_hint": "tomato"},
    )
    assert prod_resp.status_code == 200
    prod_data = prod_resp.json()
    assert "image_quality_score" in prod_data
    assert "treatment_hints" in prod_data
