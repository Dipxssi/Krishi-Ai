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
