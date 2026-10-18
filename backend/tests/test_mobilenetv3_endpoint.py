"""Automated test suite for MobileNetV3 test inference endpoint and safety gating."""

from __future__ import annotations

import base64
import io
from PIL import Image
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.schemas.models import (
    MobileNetV3DiagnosisRequest,
    MobileNetV3DiagnosisResponse,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def create_test_image_b64(
    size: tuple[int, int] = (224, 224),
    color: tuple[int, int, int] = (80, 140, 50),
    fmt: str = "JPEG",
) -> str:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# 1. Successful inference on valid image
def test_mobilenetv3_successful_inference(client: TestClient):
    b64 = create_test_image_b64()
    resp = client.post("/crop/mobilenetv3-diagnosis", json={"image_base64": b64, "confidence_threshold": 0.0})
    assert resp.status_code == 200

    data = resp.json()
    assert "status" in data
    assert data["status"] == "accepted"
    assert "confidence" in data
    assert data["confidence_is_calibrated"] is False
    assert "predicted_class" in data
    assert "top_3" in data
    assert len(data["top_3"]) == 3
    assert data["requires_expert"] is False
    assert data["model_version"] == "mobilenetv3_plantdisease_best"
    assert "disclaimer" in data


# 2. Rejection of unsupported crops
def test_mobilenetv3_rejection_of_unsupported_crop(client: TestClient):
    b64 = create_test_image_b64()
    resp = client.post(
        "/crop/mobilenetv3-diagnosis",
        json={"image_base64": b64, "crop_hint": "apple"},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "rejected"
    assert data["requires_expert"] is True
    assert "apple" in data["rejection_reason"].lower()
    # Ensure safe abstention without chemical spraying instructions
    hints = " ".join(data["treatment_hints"]).lower()
    assert "avoid unverified chemical spraying" in hints


# 3. Safe abstention on low confidence
def test_mobilenetv3_uncertainty_abstention(client: TestClient):
    b64 = create_test_image_b64()
    resp = client.post(
        "/crop/mobilenetv3-diagnosis",
        json={"image_base64": b64, "confidence_threshold": 0.9999},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "rejected"
    assert data["requires_expert"] is True
    assert "low model confidence" in data["rejection_reason"].lower()
    hints = " ".join(data["treatment_hints"]).lower()
    assert "avoid unverified chemical spraying" in hints
    assert "krishi vigyan kendra" in hints


# 4. Invalid base64 handling
def test_mobilenetv3_invalid_base64(client: TestClient):
    resp = client.post(
        "/crop/mobilenetv3-diagnosis",
        json={"image_base64": "invalid-base64-payload!!!"},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "rejected"
    assert data["requires_expert"] is True
    assert "could not decode base64" in data["rejection_reason"].lower()


# 5. Corrupted image bytes handling
def test_mobilenetv3_corrupted_image(client: TestClient):
    corrupt_b64 = base64.b64encode(b"not-a-valid-image-content-stream-bytes").decode("utf-8")
    resp = client.post(
        "/crop/mobilenetv3-diagnosis",
        json={"image_base64": corrupt_b64},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "rejected"
    assert data["requires_expert"] is True


# 6. Verify production endpoint is untouched
def test_production_endpoint_remains_heuristic(client: TestClient):
    b64 = create_test_image_b64()
    resp = client.post(
        "/crop/image-diagnosis",
        json={"image_base64": b64, "crop_hint": "tomato"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "image_quality_score" in data
    assert "requires_expert" in data
    # Confirm it does NOT have mobilenetv3 model_version field
    assert "model_version" not in data
