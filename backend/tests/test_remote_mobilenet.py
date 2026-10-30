"""Remote MobileNet (Gradio HF Space) client — no torch required."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings
from app.vision.remote_mobilenet import (
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
    assert _space_id_or_url("https://huggingface.co/spaces/Dipxssi/krishiai-vision/") == "Dipxssi/krishiai-vision"
    assert _space_id_or_url("https://dipxssi-krishiai-vision.hf.space") == "https://dipxssi-krishiai-vision.hf.space"
    assert _space_id_or_url("Dipxssi/krishiai-vision") == "Dipxssi/krishiai-vision"


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

    fake_client = MagicMock()
    fake_client.predict.return_value = payload

    with patch("gradio_client.Client", return_value=fake_client) as client_cls:
        result = diagnose_image_via_remote("data:image/jpeg;base64,aaa", crop_hint="tomato")

    assert result.status == "accepted"
    assert result.crop_id == "tomato"
    assert result.predicted_disease == "Early Blight"
    assert "hf_space" in (result.model_version or "")
    assert len(result.top_3) == 1
    client_cls.assert_called_once_with("demo/krishiai-vision", verbose=False)
    fake_client.predict.assert_called_once()


def test_remote_error_mentions_wake_space(monkeypatch):
    monkeypatch.setenv("VISION_INFERENCE_URL", "demo/krishiai-vision")
    get_settings.cache_clear()

    with patch("gradio_client.Client", side_effect=RuntimeError("Space is sleeping")):
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
