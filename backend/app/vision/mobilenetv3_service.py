"""Inference service for the MobileNetV3 plant disease classifier (test endpoint).

Reuses the exact evaluation/inference pipeline:
- Preprocessing: Resize(224), CenterCrop(224), ToTensor, ImageNet Normalization
- Model: Pretrained MobileNetV3-Small with fine-tuned 17-class classification head
- Safety: Explicit uncalibrated confidence labeling, configurable rejection threshold,
  unsupported crop rejection, safe non-chemical abstention, and image quality gating.
"""

from __future__ import annotations

import base64
import io
import time
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError
import torch

from app.schemas.models import (
    ImageDiagnosisResult,
    MobileNetV3DiagnosisRequest,
    MobileNetV3DiagnosisResponse,
    MobileNetV3PredictionItem,
)
from app.vision.diagnosis import _image_quality_score
from ml.src.evaluate_mobilenetv3 import (
    load_trained_mobilenetv3,
    predict_single_image,
)
from ml.src.train_mobilenetv3 import get_device

# Input validation limits
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
MIN_IMAGE_BYTES = 100               # 100 bytes
MIN_DIMENSION = 32                  # 32 px
MAX_DIMENSION = 8192                # 8192 px
SUPPORTED_FORMATS = {"JPEG", "JPG", "PNG", "WEBP", "BMP"}

import threading

# Module-level model cache with thread-safe invalidation and path tracking
_CACHE_LOCK = threading.Lock()
_CACHED_MODEL: torch.nn.Module | None = None
_CACHED_CKPT: dict[str, Any] | None = None
_CACHED_PATH: Path | None = None
_DEVICE: torch.device | None = None


def clear_mobilenetv3_cache() -> None:
    """Safely reset the cached MobileNetV3 model, metadata, and path tracking."""
    global _CACHED_MODEL, _CACHED_CKPT, _CACHED_PATH
    with _CACHE_LOCK:
        _CACHED_MODEL = None
        _CACHED_CKPT = None
        _CACHED_PATH = None


def get_cached_mobilenetv3(
    checkpoint_path: Path | None = None,
) -> tuple[torch.nn.Module, dict[str, Any], torch.device]:
    global _CACHED_MODEL, _CACHED_CKPT, _CACHED_PATH, _DEVICE
    if _DEVICE is None:
        _DEVICE = get_device("auto")

    from app.core.config import get_settings
    settings = get_settings()

    if checkpoint_path is None:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        target_path = repo_root / "ml" / "models" / settings.hf_model_filename
    else:
        target_path = Path(checkpoint_path)

    resolved_path = target_path.resolve()

    with _CACHE_LOCK:
        if (
            _CACHED_MODEL is not None
            and _CACHED_CKPT is not None
            and _CACHED_PATH is not None
            and _CACHED_PATH == resolved_path
        ):
            return _CACHED_MODEL, _CACHED_CKPT, _DEVICE

        model, ckpt = load_trained_mobilenetv3(
            checkpoint_path=resolved_path,
            device=_DEVICE,
            repo_id=settings.hf_model_repo,
            filename=resolved_path.name,
            token=settings.hf_token,
        )
        _CACHED_MODEL = model
        _CACHED_CKPT = ckpt
        _CACHED_PATH = resolved_path
        return _CACHED_MODEL, _CACHED_CKPT, _DEVICE


from app.vision.elasticnet_service import validate_and_decode_image


def run_mobilenetv3_diagnosis(
    request: MobileNetV3DiagnosisRequest,
    checkpoint_path: Path | None = None,
) -> MobileNetV3DiagnosisResponse:
    t_start = time.perf_counter()

    # 1. Validate and decode image using robust validator
    pil_img, quality_score, val_error = validate_and_decode_image(request.image_base64)
    if val_error is not None or pil_img is None:
        latency = (time.perf_counter() - t_start) * 1000.0
        return MobileNetV3DiagnosisResponse(
            status="rejected",
            rejection_reason=val_error or "Image validation failed.",
            requires_expert=True,
            image_quality_score=quality_score,
            treatment_hints=[
                "Upload a valid image in JPEG, PNG, or WEBP format.",
                "Ensure image is well-lit and shows the affected plant leaf clearly.",
            ],
            inference_time_ms=round(latency, 2),
        )

    # 2. Model loading
    try:
        model, ckpt, device = get_cached_mobilenetv3(checkpoint_path=checkpoint_path)
    except FileNotFoundError as exc:
        latency = (time.perf_counter() - t_start) * 1000.0
        return MobileNetV3DiagnosisResponse(
            status="rejected",
            rejection_reason=f"Model artifact not found: {exc}",
            requires_expert=True,
            image_quality_score=quality_score,
            treatment_hints=["Check model checkpoint path in ml/models/."],
            inference_time_ms=round(latency, 2),
        )

    # 3. Predict using reusable inference function
    raw_res = predict_single_image(
        image_input=pil_img,
        model=model,
        crop_hint=request.crop_hint,
        confidence_threshold=request.confidence_threshold,
        device=device,
    )

    latency = (time.perf_counter() - t_start) * 1000.0

    if raw_res["status"] == "rejected":
        return MobileNetV3DiagnosisResponse(
            status="rejected",
            rejection_reason=raw_res.get("rejection_reason"),
            confidence=raw_res.get("confidence"),
            confidence_is_calibrated=False,
            requires_expert=True,
            treatment_hints=raw_res.get("treatment_hints", []),
            image_quality_score=quality_score,
            inference_time_ms=round(latency, 2),
        )

    top_3_items = [
        MobileNetV3PredictionItem(
            class_idx=p["class_idx"],
            display_name=p["display_name"],
            crop=p["crop"],
            disease=p["disease"],
            is_healthy=p["is_healthy"],
            confidence=p["confidence"],
            confidence_is_calibrated=False,
        )
        for p in raw_res.get("top_3", [])
    ]

    return MobileNetV3DiagnosisResponse(
        status="accepted",
        rejection_reason=None,
        plant_name=raw_res.get("plant_name"),
        predicted_disease=raw_res.get("predicted_disease"),
        is_healthy=bool(raw_res.get("is_healthy", False)),
        predicted_class=raw_res.get("predicted_class"),
        crop_id=raw_res.get("crop_id"),
        disease=raw_res.get("disease"),
        confidence=raw_res.get("confidence"),
        confidence_is_calibrated=False,
        top_3=top_3_items,
        requires_expert=False,
        treatment_hints=raw_res.get("treatment_hints", []),
        image_quality_score=quality_score,
        inference_time_ms=round(latency, 2),
    )


def diagnose_image_with_mobilenetv3(
    image_base64: str,
    crop_hint: str | None = None,
    confidence_threshold: float = 0.60,
    checkpoint_path: Path | None = None,
) -> ImageDiagnosisResult:
    """Run MobileNetV3 visual classification and return structured ImageDiagnosisResult for orchestrator."""
    t_start = time.perf_counter()

    # 1. Validate and decode image
    pil_img, quality_score, val_error = validate_and_decode_image(image_base64)
    if val_error is not None or pil_img is None:
        latency = (time.perf_counter() - t_start) * 1000.0
        return ImageDiagnosisResult(
            status="rejected",
            rejection_reason=val_error or "Image validation failed.",
            plant_name=None,
            predicted_disease=None,
            is_healthy=False,
            confidence=None,
            confidence_is_calibrated=False,
            model_version="mobilenetv3_plantdisease_best",
            requires_expert=True,
            image_quality_score=quality_score,
            treatment_hints=[
                "Upload a valid image in JPEG, PNG, or WEBP format.",
                "Ensure image is well-lit and shows the affected plant leaf clearly.",
            ],
            latency_ms=round(latency, 2),
        )

    # 2. Model loading
    try:
        model, ckpt, device = get_cached_mobilenetv3(checkpoint_path=checkpoint_path)
    except FileNotFoundError as exc:
        latency = (time.perf_counter() - t_start) * 1000.0
        return ImageDiagnosisResult(
            status="rejected",
            rejection_reason=f"Model artifact not found: {exc}",
            plant_name=None,
            predicted_disease=None,
            is_healthy=False,
            confidence=None,
            confidence_is_calibrated=False,
            model_version="mobilenetv3_plantdisease_best",
            requires_expert=True,
            image_quality_score=quality_score,
            treatment_hints=["Check model checkpoint path in ml/models/."],
            latency_ms=round(latency, 2),
        )

    # 3. Predict using reusable inference function
    raw_res = predict_single_image(
        image_input=pil_img,
        model=model,
        crop_hint=crop_hint,
        confidence_threshold=confidence_threshold,
        device=device,
    )
    latency = (time.perf_counter() - t_start) * 1000.0

    top_3_items = [
        MobileNetV3PredictionItem(
            class_idx=p["class_idx"],
            display_name=p["display_name"],
            crop=p["crop"],
            disease=p["disease"],
            is_healthy=p["is_healthy"],
            confidence=p["confidence"],
            confidence_is_calibrated=False,
        )
        for p in raw_res.get("top_3", [])
    ]

    if raw_res["status"] == "rejected":
        return ImageDiagnosisResult(
            status="rejected",
            rejection_reason=raw_res.get("rejection_reason"),
            plant_name=None,
            predicted_disease=None,
            is_healthy=False,
            crop_id=None,
            disease=None,
            confidence=raw_res.get("confidence"),
            confidence_is_calibrated=False,
            model_version="mobilenetv3_plantdisease_best",
            top_3=top_3_items,
            requires_expert=True,
            treatment_hints=raw_res.get("treatment_hints", []),
            image_quality_score=quality_score,
            latency_ms=round(latency, 2),
        )

    return ImageDiagnosisResult(
        status="accepted",
        rejection_reason=None,
        plant_name=raw_res.get("plant_name"),
        predicted_disease=raw_res.get("predicted_disease"),
        is_healthy=bool(raw_res.get("is_healthy", False)),
        crop_id=raw_res.get("crop_id"),
        crop_confidence=raw_res.get("confidence"),
        disease=raw_res.get("disease"),
        disease_confidence=raw_res.get("confidence"),
        confidence=raw_res.get("confidence"),
        confidence_is_calibrated=False,
        severity="none" if raw_res.get("is_healthy") else "moderate",
        model_version="mobilenetv3_plantdisease_best",
        top_3=top_3_items,
        requires_expert=False,
        treatment_hints=raw_res.get("treatment_hints", []),
        image_quality_score=quality_score,
        latency_ms=round(latency, 2),
    )
