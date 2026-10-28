"""Tests for Phases 2-5 infrastructure."""

import base64
import io
import os

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ROUTER_MODE"] = "keyword"
os.environ["GROQ_API_KEY"] = ""

from app.core.config import get_settings
from app.api.voice import MAX_AUDIO_BYTES, _decode_audio
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
    from tests.auth_helpers import clear_auth_override, install_auth_override

    install_auth_override(app, farmer_id="img1")
    try:
        yield TestClient(app)
    finally:
        clear_auth_override(app)


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


def test_voice_transcribe_requires_groq_key(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()
    r = client.post("/voice/transcribe", json={"audio_base64": base64.b64encode(b"x" * 32).decode()})
    assert r.status_code == 503


def test_voice_transcribe_calls_groq(client, monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"text": "How do I protect my tomato crop?"}

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()
    monkeypatch.setattr("app.api.voice.httpx.post", lambda *args, **kwargs: FakeResponse())
    r = client.post("/voice/transcribe", json={"audio_base64": base64.b64encode(b"x" * 32).decode()})
    assert r.status_code == 200
    assert r.json()["text"] == "How do I protect my tomato crop?"
    assert r.json()["normalized_crop"] == "tomato"


def test_voice_transcribe_rejects_invalid_audio(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()
    r = client.post("/voice/transcribe", json={"audio_base64": "not-base64!"})
    assert r.status_code == 400


def test_voice_transcribe_rejects_oversized_base64_before_decoding():
    encoded_limit = ((MAX_AUDIO_BYTES + 2) // 3) * 4
    with pytest.raises(HTTPException) as exc_info:
        _decode_audio("A" * (encoded_limit + 1))
    assert getattr(exc_info.value, "status_code", None) == 413


def test_voice_speech_returns_audio(client, monkeypatch):
    class FakeResponse:
        content = b"fake-mp3"

        def raise_for_status(self):
            pass

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.api.voice.httpx.post", fake_post)
    r = client.post("/voice/speech", json={"text": "Hello farmer"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/mpeg")
    assert r.content == b"fake-mp3"
    assert captured["url"] == "https://api.openai.com/v1/audio/speech"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"] == {
        "model": "gpt-4o-mini-tts",
        "voice": "alloy",
        "input": "Hello farmer",
        "response_format": "mp3",
    }


def test_voice_speech_logs_provider_error_without_secrets(client, monkeypatch, caplog):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    response = httpx.Response(
        401,
        json={"error": {"type": "authentication_error", "message": "Invalid API key sk-proj-supersecretvalue"}},
        request=httpx.Request("POST", "https://api.openai.com/v1/audio/speech"),
    )
    monkeypatch.setattr("app.api.voice.httpx.post", lambda *args, **kwargs: response)

    with caplog.at_level("WARNING", logger="app.api.voice"):
        r = client.post("/voice/speech", json={"text": "Hello farmer"})

    assert r.status_code == 502
    assert r.json()["detail"] == "Speech playback provider rejected the request."
    assert "authentication_error" in caplog.text
    assert "Invalid API key" in caplog.text
    assert "[REDACTED]" in caplog.text
    assert "sk-proj-supersecretvalue" not in caplog.text


def test_voice_speech_requires_openai_key(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    r = client.post("/voice/speech", json={"text": "Hello farmer"})
    assert r.status_code == 503


def test_voice_and_query_openapi_contracts(client):
    schemas = client.get("/openapi.json").json()
    paths = schemas["paths"]
    components = schemas["components"]["schemas"]

    assert paths["/voice/transcribe"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/VoiceTranscribeRequest")
    assert paths["/voice/transcribe"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/VoiceTranscribeResponse")
    speech_response = paths["/voice/speech"]["post"]["responses"]["200"]["content"]["audio/mpeg"]["schema"]
    assert speech_response == {"type": "string", "format": "binary"}
    assert paths["/query"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/QueryRequest")
    assert paths["/query"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/QueryResponse")
    assert components["QueryRequest"]["required"] == ["query", "farmer_id"]


def test_supervised_router_scores():
    from app.orchestrator.supervised_router import supervised_scores

    scores = supervised_scores("Mandi price for potato today")
    assert "market" in scores
    assert scores["market"] >= 0
