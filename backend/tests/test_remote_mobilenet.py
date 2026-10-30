"""Remote MobileNet (Gradio HF Space) client — no torch required."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings
from app.vision.remote_mobilenet import (
    _read_gradio_sse,
    _space_id_or_url,
    diagnose_image_via_remote,
    diagnose_image_with_mobilenetv3,
)


@pytest.fixture(autouse=True)
def clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_space_id_parsing():
    from app.vision.remote_mobilenet import _space_runtime_url

    assert _space_id_or_url("https://huggingface.co/spaces/Dipxssi/krishiai-vision/") == "Dipxssi/krishiai-vision"
    assert _space_id_or_url("https://dipxssi-krishiai-vision.hf.space") == "https://dipxssi-krishiai-vision.hf.space"
    assert _space_id_or_url("Dipxssi/krishiai-vision") == "Dipxssi/krishiai-vision"
    assert _space_runtime_url("Dipssi/krishiai-vision") == "https://dipssi-krishiai-vision.hf.space"


def test_remote_maps_accepted_response(monkeypatch):
    monkeypatch.setenv("VISION_INFERENCE_URL", "https://huggingface.co/spaces/demo/krishiai-vision")
    get_settings.cache_clear()

    payload = {
        "status": "accepted",
        "plant_name": "Tomato",
        "predicted_disease": "Early Blight",
        "is_healthy": False,
        "crop_id": "tomato",
        "disease": "early_blight",
        "confidence": 0.91,
        "top_3": [
            {
                "class_idx": 8,
                "display_name": "Tomato Early Blight",
                "crop": "tomato",
                "disease": "early_blight",
                "is_healthy": False,
                "confidence": 0.91,
            }
        ],
        "treatment_hints": ["Confirm with KVK"],
        "latency_ms": 12.5,
        "inference_source": "hf_space",
        "model_version": "mobilenetv3_plantdisease_best",
    }

    with (
        patch("app.vision.remote_mobilenet._wake_space"),
        patch("app.vision.remote_mobilenet._predict_on_space", return_value=payload) as predict,
    ):
        result = diagnose_image_via_remote("data:image/jpeg;base64,aaa", crop_hint="tomato")

    assert result.status == "accepted"
    assert result.crop_id == "tomato"
    assert result.predicted_disease == "Early Blight"
    assert "hf_space" in (result.model_version or "")
    assert len(result.top_3) == 1
    predict.assert_called_once()
    assert predict.call_args.args[0] == "demo/krishiai-vision"


def test_gradio6_sse_unwraps_complete_payload():
    body = [
        "event: heartbeat",
        "data: null",
        "",
        "event: complete",
        'data: [{"status": "rejected", "rejection_reason": "Image too small", "model_version": "mobilenetv3_plantdisease_best", "inference_source": "hf_space"}]',
        "",
    ]
    parsed = _read_gradio_sse(body)
    assert parsed["status"] == "rejected"
    assert parsed["rejection_reason"] == "Image too small"


def test_remote_error_mentions_wake_space(monkeypatch):
    monkeypatch.setenv("VISION_INFERENCE_URL", "demo/krishiai-vision")
    get_settings.cache_clear()

    with (
        patch("app.vision.remote_mobilenet._wake_space"),
        patch("app.vision.remote_mobilenet.time.sleep"),
        patch(
            "app.vision.remote_mobilenet._predict_on_space",
            side_effect=RuntimeError("Space is sleeping"),
        ),
    ):
        with pytest.raises(RuntimeError, match="Wake the Hugging Face Space"):
            diagnose_image_via_remote("aaa")


def test_facade_uses_remote_when_url_set(monkeypatch):
    monkeypatch.setenv("VISION_INFERENCE_URL", "demo/krishiai-vision")
    get_settings.cache_clear()

    fake = MagicMock()
    with patch(
        "app.vision.remote_mobilenet.diagnose_image_via_remote",
        return_value=fake,
    ) as remote:
        out = diagnose_image_with_mobilenetv3("img", crop_hint="potato")

    assert out is fake
    remote.assert_called_once()
