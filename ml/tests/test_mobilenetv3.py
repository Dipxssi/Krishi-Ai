"""Automated tests for MobileNetV3 model loading, inference, preprocessing, and safety."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
import pytest
import torch
from PIL import Image

from ml.src.config import TARGET_CLASSES
from ml.src.dataset import (
    IMAGENET_MEAN,
    IMAGENET_STD,
    get_eval_transforms,
    get_train_transforms,
)
from ml.src.evaluate_mobilenetv3 import (
    load_trained_mobilenetv3,
    predict_single_image,
)
from ml.src.train_mobilenetv3 import create_mobilenetv3, get_device


def create_dummy_image(
    size: tuple[int, int] = (224, 224),
    color: tuple[int, int, int] = (80, 140, 50),
) -> Image.Image:
    return Image.new("RGB", size, color=color)


# 1. Model architecture and tensor shapes
def test_mobilenetv3_architecture_and_output_shape():
    model = create_mobilenetv3(num_classes=17, variant="small", pretrained=False)
    model.eval()

    dummy_input = torch.randn(2, 3, 224, 224)
    with torch.no_grad():
        output = model(dummy_input)

    assert output.shape == (2, 17)
    assert not torch.isnan(output).any()


# 2. Input preprocessing and normalization consistency
def test_preprocessing_and_normalization_consistency():
    train_transform = get_train_transforms(224)
    eval_transform = get_eval_transforms(224)

    img = create_dummy_image((300, 400))
    t_train = train_transform(img)
    t_eval = eval_transform(img)

    assert t_train.shape == (3, 224, 224)
    assert t_eval.shape == (3, 224, 224)
    assert t_train.dtype == torch.float32
    assert t_eval.dtype == torch.float32

    # Check normalization parameters match ImageNet constants
    assert IMAGENET_MEAN == [0.485, 0.456, 0.406]
    assert IMAGENET_STD == [0.229, 0.224, 0.225]


# 3. Missing checkpoint error handling
def test_missing_checkpoint_handling():
    with pytest.raises(FileNotFoundError) as exc_info:
        load_trained_mobilenetv3(checkpoint_path=Path("nonexistent_mobilenetv3.pth"))
    assert "not found" in str(exc_info.value).lower()


# 4. Output class mapping integrity
def test_class_mapping_alignment():
    assert len(TARGET_CLASSES) == 17
    for idx, meta in enumerate(TARGET_CLASSES):
        assert meta["class_idx"] == idx
        assert meta["crop"] in ("maize", "potato", "tomato")
        assert "display_name" in meta


# 5. Invalid and corrupted image handling
def test_predict_single_image_invalid_input():
    # Test with empty/corrupt bytes
    corrupt_bytes = b"not-an-image-file"
    with pytest.raises(Exception):
        predict_single_image(corrupt_bytes)


# 6. Rejection of unsupported crops
def test_rejection_of_unsupported_crop_hint():
    # Dummy model for testing rule logic
    model = create_mobilenetv3(num_classes=17, variant="small", pretrained=False)
    model.eval()
    img = create_dummy_image()

    for unsupported in ["apple", "grape", "blueberry", "cotton", "rice", "wheat"]:
        res = predict_single_image(
            img,
            model=model,
            crop_hint=unsupported,
            device=torch.device("cpu"),
        )
        assert res["status"] == "rejected"
        assert res["requires_expert"] is True
        assert f"crop '{unsupported}' is outside" in res["rejection_reason"].lower()
        # Verify safe treatment hints without chemical advice
        hints = " ".join(res["treatment_hints"]).lower()
        assert "avoid unverified chemical spraying" in hints


# 7. Safe abstention on low confidence
def test_rejection_of_uncertain_predictions():
    model = create_mobilenetv3(num_classes=17, variant="small", pretrained=False)
    model.eval()
    img = create_dummy_image()

    # Require an impossible threshold to trigger uncertainty rejection
    res = predict_single_image(
        img,
        model=model,
        confidence_threshold=0.9999,
        device=torch.device("cpu"),
    )
    assert res["status"] == "rejected"
    assert res["requires_expert"] is True
    assert "low model confidence" in res["rejection_reason"].lower()
    assert res["confidence_is_calibrated"] is False
    hints = " ".join(res["treatment_hints"]).lower()
    assert "avoid unverified chemical spraying" in hints
    assert "consult local krishi vigyan kendra" in hints


# 8. Inference response structure verification
def test_inference_response_schema():
    model = create_mobilenetv3(num_classes=17, variant="small", pretrained=False)
    model.eval()
    img = create_dummy_image()

    # With low threshold 0.0 to verify accepted response schema
    res = predict_single_image(
        img,
        model=model,
        confidence_threshold=0.0,
        device=torch.device("cpu"),
    )
    assert res["status"] == "accepted"
    assert "predicted_class" in res
    assert "crop_id" in res
    assert "disease" in res
    assert "confidence" in res
    assert res["confidence_is_calibrated"] is False
    assert "top_3" in res
    assert len(res["top_3"]) == 3
    assert "latency_ms" in res
    assert res["requires_expert"] is False
    for item in res["top_3"]:
        assert item["confidence_is_calibrated"] is False
        assert 0 <= item["class_idx"] < 17
