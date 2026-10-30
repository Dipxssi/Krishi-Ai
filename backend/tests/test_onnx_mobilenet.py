"""Bundled ONNX MobileNet runs without torch or a GPU quota."""

from __future__ import annotations

import base64
import io

from PIL import Image

from app.vision.onnx_mobilenet import bundled_onnx_path, diagnose_image_with_onnx


def test_bundled_onnx_file_is_present():
    path = bundled_onnx_path()
    assert path is not None
    assert path.stat().st_size > 1_000_000


def test_onnx_scores_a_leaf_sized_image():
    img = Image.new("RGB", (240, 180), (30, 110, 40))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode()
    result = diagnose_image_with_onnx(b64, crop_hint=None, confidence_threshold=0.0)
    assert result.model_version == "mobilenetv3_plantdisease_best@cpu"
    assert result.status == "accepted"
    assert result.crop_id in {"tomato", "potato", "maize"}
    assert result.top_3


def test_maize_profile_beats_a_moderate_tomato_score():
    from app.vision.onnx_mobilenet import _result_from_probs
    import numpy as np

    probs = np.zeros(17, dtype=np.float32)
    probs[11] = 0.62  # tomato septoria
    probs[2] = 0.28  # maize northern leaf blight
    probs[3] = 0.10  # maize healthy
    result = _result_from_probs(
        probs,
        crop_hint=None,
        crop_prior="maize",
        confidence_threshold=0.60,
        latency_ms=1,
    )
    assert result.status == "accepted"
    assert result.crop_id == "maize"
    assert result.disease == "northern_leaf_blight"


def test_confident_tomato_does_not_override_a_maize_profile():
    from app.vision.onnx_mobilenet import _result_from_probs
    import numpy as np

    probs = np.zeros(17, dtype=np.float32)
    probs[11] = 0.99
    probs[2] = 0.01
    result = _result_from_probs(
        probs,
        crop_hint=None,
        crop_prior="maize",
        confidence_threshold=0.60,
        latency_ms=1,
    )
    assert result.status == "rejected"
    assert result.crop_id is None
    assert "maize" in (result.rejection_reason or "")
    assert "Tomato" in (result.rejection_reason or "")


def test_tomato_profile_does_not_override_a_clear_maize_prediction():
    from app.vision.onnx_mobilenet import _result_from_probs
    import numpy as np

    probs = np.zeros(17, dtype=np.float32)
    probs[1] = 0.84  # maize rust
    probs[11] = 0.16
    result = _result_from_probs(
        probs,
        crop_hint=None,
        crop_prior="tomato",
        confidence_threshold=0.60,
        latency_ms=1,
    )
    assert result.status == "accepted"
    assert result.crop_id == "maize"
