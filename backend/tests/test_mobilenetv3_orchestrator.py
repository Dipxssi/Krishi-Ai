"""Comprehensive automated test suite for MobileNetV3 multi-agent orchestrator integration.

Covers:
1. Model loading and class mapping verification (17 closed-set classes)
2. Accepted disease prediction reaching orchestrator, agent selection, and RAG integration
3. Healthy prediction handling (cautious, preventive care only, no chemical treatment, no guarantee)
4. Preservation of confidence and uncalibrated metadata
5. Rejected predictions remaining strictly unconfirmed with safe non-chemical guidance
6. Unsupported crop gating (apple rejected without false classification)
7. Conflicting farm profile vs. image crop (onion profile vs. tomato leaf photo)
8. Prevention of unsafe chemical advice after rejection or healthy scan
9. Text-only query regression (no image supplied)
10. Existing heuristic fallback behavior via vision_model='heuristic'
11. End-to-end API HTTP endpoint schemas
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
import pytest
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.orchestrator.orchestrator import handle_query
from app.schemas.models import (
    FarmContext,
    ImageDiagnosisResult,
    MobileNetV3PredictionItem,
    QueryResponse,
)
from app.services import live_market, live_weather, llm
from app.vision.mobilenetv3_service import (
    diagnose_image_with_mobilenetv3,
    get_cached_mobilenetv3,
)
from ml.src.evaluate_mobilenetv3 import TARGET_CLASSES


def _create_synthetic_image_b64(
    color: tuple[int, int, int] = (60, 150, 60),
    size: tuple[int, int] = (224, 224),
    fmt: str = "JPEG",
) -> str:
    arr = np.full((size[1], size[0], 3), color, dtype=np.uint8)
    # Add subtle texture
    noise = np.random.RandomState(42).randint(-20, 20, arr.shape, dtype=np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


@pytest.fixture
def test_client() -> TestClient:
    from tests.auth_helpers import clear_auth_override, install_auth_override

    install_auth_override(app, farmer_id="test-mobilenet-user")
    try:
        yield TestClient(app)
    finally:
        clear_auth_override(app)


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    from app.db.session import init_db
    init_db()
    monkeypatch.setattr(live_weather, "fetch_weather_live", lambda *args, **kwargs: None)
    monkeypatch.setattr(live_market, "fetch_market_price_live", lambda *args, **kwargs: None)
    monkeypatch.setattr(llm, "is_llm_available", lambda: False)
    monkeypatch.setenv("ROUTER_MODE", "keyword")
    monkeypatch.setenv("VISION_MODEL", "mobilenetv3")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def tomato_context() -> FarmContext:
    return FarmContext(
        farmer_id="farmer-mobilenet-001",
        location="Nashik, Maharashtra",
        farm_area_acres=2.0,
        crop="tomato",
        growth_stage="flowering",
        soil_type="loamy",
        irrigation_available=True,
        budget=45000.0,
        preferred_language="English",
        season="kharif",
    )


@pytest.fixture
def onion_context() -> FarmContext:
    return FarmContext(
        farmer_id="farmer-onion-profile",
        location="Nashik, Maharashtra",
        farm_area_acres=3.0,
        crop="onion",
        growth_stage="bulb_formation",
        soil_type="black",
        irrigation_available=True,
        budget=60000.0,
        preferred_language="English",
        season="rabi",
    )


# 1. Model loading and class mapping
def test_mobilenetv3_model_loading_and_class_mapping():
    """Verify MobileNetV3 loads successfully with exact 17-class mapping."""
    repo_root = Path(__file__).resolve().parents[2]
    ckpt_path = repo_root / "ml" / "models" / "mobilenetv3_plantdisease_best.pth"
    assert ckpt_path.exists(), f"Checkpoint {ckpt_path} must exist"

    model, ckpt, device = get_cached_mobilenetv3(checkpoint_path=ckpt_path)
    assert model is not None
    assert ckpt["num_classes"] == 17
    assert len(ckpt["class_names"]) == 17
    assert len(TARGET_CLASSES) == 17

    # Ensure class names in checkpoint match target classes
    for i, target in enumerate(TARGET_CLASSES):
        assert ckpt["class_names"][i] == target["display_name"]
        assert target["crop"] in ("corn", "maize", "potato", "tomato")


# 2. Accepted disease prediction reaching orchestrator
def test_accepted_disease_prediction_reaches_orchestrator(tomato_context):
    """End-to-end accepted disease prediction reaches crop_health agent, retrieves RAG, and produces safe advice."""
    mock_accepted = ImageDiagnosisResult(
        status="accepted",
        rejection_reason=None,
        plant_name="Tomato",
        predicted_disease="Septoria Leaf Spot",
        is_healthy=False,
        crop_id="tomato",
        disease="septoria_leaf_spot",
        confidence=0.894,
        crop_confidence=0.894,
        disease_confidence=0.894,
        confidence_is_calibrated=False,
        severity="moderate",
        model_version="mobilenetv3_plantdisease_best",
        requires_expert=False,
        treatment_hints=[
            "Remove infected lower leaves and avoid overhead irrigation.",
            "Scout field to assess disease progression.",
        ],
        top_3=[
            MobileNetV3PredictionItem(
                class_idx=14,
                display_name="Tomato Septoria leaf spot",
                crop="tomato",
                disease="septoria_leaf_spot",
                is_healthy=False,
                confidence=0.894,
                confidence_is_calibrated=False,
            ),
            MobileNetV3PredictionItem(
                class_idx=8,
                display_name="Tomato Early blight",
                crop="tomato",
                disease="early_blight",
                is_healthy=False,
                confidence=0.065,
                confidence_is_calibrated=False,
            ),
            MobileNetV3PredictionItem(
                class_idx=10,
                display_name="Tomato Late blight",
                crop="tomato",
                disease="late_blight",
                is_healthy=False,
                confidence=0.021,
                confidence_is_calibrated=False,
            ),
        ],
        image_quality_score=0.92,
        latency_ms=12.5,
    )

    with patch("app.vision.remote_mobilenet.diagnose_image_with_mobilenetv3", return_value=mock_accepted):
        b64 = _create_synthetic_image_b64()
        resp = handle_query(
            "What is affecting my tomato leaf and how do I manage it?",
            tomato_context,
            image_base64=b64,
            selected_crop="tomato",
            persist=False,
            vision_model="mobilenetv3",
        )

        assert resp.image_diagnosis is not None
        assert resp.image_diagnosis.status == "accepted"
        assert resp.image_diagnosis.plant_name == "Tomato"
        assert resp.image_diagnosis.predicted_disease == "Septoria Leaf Spot"
        assert resp.image_diagnosis.is_healthy is False
        assert resp.image_diagnosis.confidence == 0.894
        assert resp.image_diagnosis.confidence_is_calibrated is False
        assert resp.image_diagnosis.model_version == "mobilenetv3_plantdisease_best"
        assert len(resp.image_diagnosis.top_3) == 3

        # Orchestrator routing verification
        assert "crop_health" in resp.agents_used
        assert resp.selected_crop == "tomato"

        # RAG evidence verification
        rag_evidence = [e for e in resp.evidence if e.source.startswith("rag:") or e.source == "vision_diagnosis"]
        assert len(rag_evidence) > 0
        vision_ev = next(e for e in resp.evidence if e.source == "vision_diagnosis")
        assert "Septoria Leaf Spot" in str(vision_ev.value) or "septoria" in str(vision_ev.value).lower()

        # Recommendation clarity: states AI prediction nature, potential causes, and next steps
        rec = resp.final_recommendation
        assert "Septoria Leaf Spot" in rec or "septoria" in rec.lower()
        assert "prediction" in rec.lower() or "preliminary" in rec.lower() or "ai" in rec.lower()
        assert resp.decision_score is not None
        assert resp.decision_score.disease_risk == 0.65


# 3. Healthy prediction handling
def test_healthy_prediction_handling(tomato_context):
    """When MobileNetV3 predicts healthy leaf: identify plant, provide preventive care, no chemical treatment, no disease-free guarantee."""
    mock_healthy = ImageDiagnosisResult(
        status="accepted",
        rejection_reason=None,
        plant_name="Potato",
        predicted_disease="Healthy",
        is_healthy=True,
        crop_id="potato",
        disease="healthy",
        confidence=0.945,
        crop_confidence=0.945,
        disease_confidence=0.945,
        confidence_is_calibrated=False,
        severity="none",
        model_version="mobilenetv3_plantdisease_best",
        requires_expert=False,
        treatment_hints=["Maintain regular field scouting and balanced nutrition."],
        latency_ms=10.2,
    )

    with patch("app.vision.remote_mobilenet.diagnose_image_with_mobilenetv3", return_value=mock_healthy):
        b64 = _create_synthetic_image_b64()
        resp = handle_query(
            "Is my potato plant healthy?",
            tomato_context,
            image_base64=b64,
            selected_crop="potato",
            persist=False,
            vision_model="mobilenetv3",
        )

        assert resp.image_diagnosis is not None
        assert resp.image_diagnosis.status == "accepted"
        assert resp.image_diagnosis.plant_name == "Potato"
        assert resp.image_diagnosis.predicted_disease == "Healthy"
        assert resp.image_diagnosis.is_healthy is True

        rec = resp.final_recommendation.lower()
        # Identifies plant
        assert "potato" in rec
        # Explains no supported disease detected
        assert "no supported disease" in rec or "did not detect" in rec or "healthy" in rec
        # Cautious: does not guarantee disease-free
        assert "guarantee" in rec or "preliminary" in rec or "scan" in rec
        # No chemical fungicides or bactericides invented
        assert "mancozeb" not in rec
        assert "copper oxychloride" not in rec
        assert "fungicide" not in rec or "do not apply" in rec

        # Disease risk is suppressed to low baseline for healthy foliage
        assert resp.decision_score is not None
        assert resp.decision_score.disease_risk == 0.10


# 4. Rejected / uncertain prediction abstention
def test_rejected_prediction_remains_unconfirmed(tomato_context):
    """When MobileNetV3 prediction is uncertain, status remains rejected and expert review is mandated."""
    mock_rejected = ImageDiagnosisResult(
        status="rejected",
        rejection_reason="Low model confidence (0.42 < threshold 0.60). Prediction is uncertain.",
        plant_name=None,
        predicted_disease=None,
        is_healthy=False,
        crop_id=None,
        disease=None,
        confidence=0.42,
        confidence_is_calibrated=False,
        model_version="mobilenetv3_plantdisease_best",
        requires_expert=True,
        treatment_hints=[
            "Automated diagnosis is unconfirmed due to low model confidence. Avoid unverified chemical spraying.",
            "Consult local Krishi Vigyan Kendra (KVK) or extension specialist.",
        ],
        latency_ms=11.0,
    )

    with patch("app.vision.remote_mobilenet.diagnose_image_with_mobilenetv3", return_value=mock_rejected):
        b64 = _create_synthetic_image_b64()
        resp = handle_query(
            "What spray should I use for this spot?",
            tomato_context,
            image_base64=b64,
            selected_crop="tomato",
            persist=False,
            vision_model="mobilenetv3",
        )

        assert resp.image_diagnosis is not None
        assert resp.image_diagnosis.status == "rejected"
        assert resp.image_diagnosis.requires_expert is True
        assert resp.image_diagnosis.plant_name is None
        assert resp.image_diagnosis.predicted_disease is None

        rec = resp.final_recommendation.lower()
        # Authoritative unconfirmed boundary
        assert "image diagnosis: unconfirmed" in rec
        assert "safe non-chemical next steps" in rec
        assert "krishi vigyan kendra" in rec or "extension" in rec

        # Zero chemical recommendations
        assert "mancozeb" not in rec
        assert "copper" not in rec
        assert "spray schedule" not in rec
        assert "g/l" not in rec

        # Disease risk in decision index must be suppressed
        assert resp.decision_score is not None
        assert resp.decision_score.disease_risk is None


# 5. Unsupported crop rejection
def test_unsupported_crop_rejection(tomato_context):
    """Unsupported crop (apple) must be explicitly rejected without false classification."""
    b64 = _create_synthetic_image_b64()
    resp = handle_query(
        "Check my apple leaf",
        tomato_context,
        image_base64=b64,
        selected_crop="apple",
        persist=False,
        vision_model="mobilenetv3",
    )

    assert resp.image_diagnosis is not None
    assert resp.image_diagnosis.status == "rejected"
    assert resp.image_diagnosis.requires_expert is True
    assert "apple" in (resp.image_diagnosis.rejection_reason or "").lower()
    assert "outside supported crops" in (resp.image_diagnosis.rejection_reason or "").lower()

    rec = resp.final_recommendation.lower()
    assert "image diagnosis: unconfirmed" in rec
    assert "mancozeb" not in rec
    assert "copper" not in rec


# 6. Conflicting farm profile vs image crop
def test_conflicting_farm_profile_and_image_crops(onion_context):
    """Farm profile says Onion, but image analysis identifies Tomato.
    Orchestrator must not substitute Onion for Tomato, and must prompt for clarification.
    """
    mock_tomato = ImageDiagnosisResult(
        status="accepted",
        rejection_reason=None,
        plant_name="Tomato",
        predicted_disease="Early Blight",
        is_healthy=False,
        crop_id="tomato",
        disease="early_blight",
        confidence=0.912,
        crop_confidence=0.912,
        disease_confidence=0.912,
        confidence_is_calibrated=False,
        severity="moderate",
        model_version="mobilenetv3_plantdisease_best",
        requires_expert=False,
        treatment_hints=["Scout lower leaves and avoid overhead watering."],
        latency_ms=13.0,
    )

    with patch("app.vision.remote_mobilenet.diagnose_image_with_mobilenetv3", return_value=mock_tomato):
        b64 = _create_synthetic_image_b64()
        # Farmer with onion profile uploads tomato leaf without explicit crop
        resp = handle_query(
            "What is this leaf problem?",
            onion_context,
            image_base64=b64,
            selected_crop=None,
            persist=False,
            vision_model="mobilenetv3",
        )

        assert resp.image_diagnosis is not None
        assert resp.image_diagnosis.status == "accepted"
        assert resp.image_diagnosis.plant_name == "Tomato"

        # Confirmed: Onion profile was NOT used to override Tomato image!
        assert resp.farm_profile_crop == "onion"
        assert resp.selected_crop == "tomato"

        # Crop conflict warning is present
        assert any("Crop context difference" in w for w in resp.warnings)

        # Recommendation clearly clarifies the conflict
        assert "Note on Crop Identity" in resp.final_recommendation
        assert "onion" in resp.final_recommendation.lower()
        assert "tomato" in resp.final_recommendation.lower()


# 7. Text-only query regression
def test_text_only_query_regression(tomato_context):
    """Text queries without image upload continue to operate normally."""
    resp = handle_query(
        "What fertilizer should I apply for flowering tomatoes?",
        tomato_context,
        image_base64=None,
        persist=False,
    )

    assert resp.image_diagnosis is None
    assert resp.selected_crop == "tomato"
    assert len(resp.agents_used) > 0
    assert len(resp.final_recommendation) > 50


# 8. Heuristic fallback path
def test_heuristic_fallback_path(tomato_context):
    """Setting vision_model='heuristic' executes the legacy heuristic fallback route."""
    b64 = _create_synthetic_image_b64()
    with patch("app.orchestrator.orchestrator.diagnose_image_bytes") as mock_heuristic:
        mock_heuristic.return_value = ImageDiagnosisResult(
            status="ok",
            image_quality_score=0.85,
            crop_id="tomato",
            crop_confidence=0.90,
            disease="early_blight",
            disease_confidence=0.75,
            severity="moderate",
            requires_expert=False,
            treatment_hints=["Field sanitation and balanced irrigation."],
        )

        resp = handle_query(
            "Check my tomato leaf",
            tomato_context,
            image_base64=b64,
            selected_crop="tomato",
            persist=False,
            vision_model="heuristic",
        )

        mock_heuristic.assert_called_once()
        assert resp.image_diagnosis is not None
        assert resp.image_diagnosis.status == "ok"
        assert resp.image_diagnosis.disease == "early_blight"


# 9. API /query endpoint integration with MobileNetV3
def test_api_query_endpoint_with_mobilenetv3(test_client: TestClient):
    """Test full HTTP POST /query endpoint with MobileNetV3."""
    from app.db.session import create_farm_context
    from app.schemas.models import FarmContextCreate

    create_farm_context(
        FarmContextCreate(
            farmer_id="test-mobilenet-user",
            location="Nashik",
            farm_area_acres=2.0,
            crop="tomato",
            growth_stage="vegetative",
            budget=30000.0,
            irrigation_available=True,
        )
    )

    b64 = _create_synthetic_image_b64()
    query_payload = {
        "farmer_id": "test-mobilenet-user",
        "query": "Check this tomato leaf",
        "image_base64": b64,
        "selected_crop": "tomato",
        "vision_model": "mobilenetv3",
    }
    resp = test_client.post("/query", json=query_payload)
    assert resp.status_code == 200

    data = resp.json()
    assert "request_id" in data
    assert "final_recommendation" in data
    assert "image_diagnosis" in data
    assert data["image_diagnosis"] is not None
    assert "status" in data["image_diagnosis"]
    assert "confidence_is_calibrated" in data["image_diagnosis"]
    assert data["image_diagnosis"]["confidence_is_calibrated"] is False
