"""Tests for Phases 2-5 infrastructure."""

import base64
import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ROUTER_MODE"] = "keyword"
os.environ["GROQ_API_KEY"] = ""

from app.core.config import get_settings
from app.db.session import init_db, reset_engine
from app.main import app
from app.tools.agriculture import estimate_treatment_cost, interpret_soil_npk
from app.vision.diagnosis import diagnose_image_bytes


@pytest.fixture(autouse=True)
def _reset():
    get_settings.cache_clear()
    reset_engine()
    init_db()
    yield
    reset_engine()


@pytest.fixture
def client():
    return TestClient(app)


def _tiny_image_b64() -> str:
    img = Image.new("RGB", (64, 64), color=(80, 120, 40))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_post_route_endpoint(client):
    r = client.post("/route", json={"query": "Tomato price and rain forecast?"})
    assert r.status_code == 200
    body = r.json()
    assert body["selected_agents"]
    assert "risk_level" in body


def test_image_diagnosis_endpoint(client):
    r = client.post(
        "/crop/image-diagnosis",
        json={"image_base64": _tiny_image_b64(), "crop_hint": "tomato"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert body.get("crop_id") == "tomato" or body["status"] == "rejected"


def test_estimate_treatment_cost():
    out = estimate_treatment_cost("tomato", "early_blight", "moderate", 2.0)
    assert out["total_treatment_cost_inr"] > 0


def test_query_with_image_and_audit(client):
    payload = {
        "farmer_id": "img1",
        "location": "Nashik",
        "farm_area_acres": 1.0,
        "crop": "tomato",
        "growth_stage": "fruiting",
        "soil_type": "loam",
        "irrigation_available": True,
        "budget": 20000,
        "preferred_language": "English",
        "season": "kharif",
    }
    assert client.post("/farmers", json=payload).status_code == 201
    q = client.post(
        "/query",
        json={
            "farmer_id": "img1",
            "query": "Brown spots on tomato leaves after rain — treat or sell?",
            "image_base64": _tiny_image_b64(),
        },
    )
    assert q.status_code == 200
    body = q.json()
    assert body["request_id"]
    assert body.get("structured_recommendation")
    audit = client.get(f"/audit/{body['request_id']}")
    assert audit.status_code == 200


def test_voice_transcribe_stub(client):
    r = client.post("/voice/transcribe", json={"audio_base64": base64.b64encode(b"x" * 32).decode()})
    assert r.status_code == 200
    assert "text" in r.json()


def test_supervised_router_scores():
    from app.orchestrator.supervised_router import supervised_scores

    scores = supervised_scores("Mandi price for potato today")
    assert "market" in scores
    assert scores["market"] >= 0
