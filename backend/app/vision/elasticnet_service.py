"""Inference service for the ElasticNet plant disease classifier (test endpoint).

Reuses the exact training pipeline:
- Preprocessing: HSV color histogram + moments (38-d) and pure-NumPy HOG features (1,568-d) = 1,606-d
- Scaling: Exact fitted StandardScaler from training
- Inference: SAGA ElasticNet Logistic Regression
- Safety: Explicit uncalibrated confidence labeling, configurable rejection threshold,
  OOD/crop rejection, and abstention to expert review without unverified chemical spraying.
"""

from __future__ import annotations

import base64
import io
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

from app.schemas.models import (
    ElasticNetDiagnosisRequest,
    ElasticNetDiagnosisResponse,
    ElasticNetPredictionItem,
)
from app.services.crop_registry import normalize_crop_name
from app.vision.diagnosis import _image_quality_score
from app.vision.model_loader import load_elasticnet_artifact
from ml.src.features import extract_features_from_image

# Supported crops for the 17-class PlantVillage ElasticNet model
SUPPORTED_ELASTICNET_CROPS = {"tomato", "potato", "maize"}

# Module-level cache for the loaded artifact bundle
_CACHED_BUNDLE: dict[str, Any] | None = None
_CACHED_BUNDLE_PATH: str | None = None

# Input validation limits
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
MIN_IMAGE_BYTES = 100               # 100 bytes
MIN_DIMENSION = 32                  # 32 px
MAX_DIMENSION = 8192                # 8192 px
SUPPORTED_FORMATS = {"JPEG", "JPG", "PNG", "WEBP", "BMP"}


def get_cached_elasticnet_bundle(artifact_path: str | Path | None = None) -> dict[str, Any]:
    """Retrieve or load cached ElasticNet model bundle."""
    global _CACHED_BUNDLE, _CACHED_BUNDLE_PATH

    path_str = str(artifact_path) if artifact_path is not None else "default"
    if _CACHED_BUNDLE is not None and _CACHED_BUNDLE_PATH == path_str:
        return _CACHED_BUNDLE

    bundle = load_elasticnet_artifact(artifact_path=artifact_path)
    _CACHED_BUNDLE = bundle
    _CACHED_BUNDLE_PATH = path_str
    return bundle


def clear_bundle_cache() -> None:
    """Clear cached model bundle (used in tests for simulating missing/corrupt artifacts)."""
    global _CACHED_BUNDLE, _CACHED_BUNDLE_PATH
    _CACHED_BUNDLE = None
    _CACHED_BUNDLE_PATH = None


def validate_and_decode_image(
    image_base64: str,
) -> tuple[Image.Image | None, float, str | None]:
    """
    Validate image base64 input, file size, format, dimensions, and decoding integrity.
    Returns (PIL.Image or None, quality_score, rejection_reason or None).
    """
    if not image_base64 or not image_base64.strip():
        return None, 0.0, "Empty image input provided."

    # Extract base64 payload
    raw_b64 = image_base64.split(",", 1)[-1].strip()
    try:
        data = base64.b64decode(raw_b64, validate=True)
    except Exception as exc:
        return None, 0.0, f"Could not decode base64 payload: {exc}"

    # File size validation
    size_bytes = len(data)
    if size_bytes < MIN_IMAGE_BYTES:
        return None, 0.0, f"Image payload too small ({size_bytes} bytes). Minimum required is {MIN_IMAGE_BYTES} bytes."
    if size_bytes > MAX_IMAGE_BYTES:
        return None, 0.0, f"Image payload exceeds maximum limit of 10MB ({size_bytes / (1024*1024):.1f}MB)."

    # Pillow decoding and verification
    try:
        bio = io.BytesIO(data)
        img = Image.open(bio)
        fmt = (img.format or "").upper()
        if fmt not in SUPPORTED_FORMATS:
            return None, 0.0, f"Unsupported image format '{fmt}'. Please upload JPEG, PNG, or WEBP."

        # Verify integrity and decode image pixels into memory
        img.load()
        rgb_img = img.convert("RGB")
    except UnidentifiedImageError:
        return None, 0.0, "Could not identify image file. Upload a valid JPEG, PNG, or WEBP image."
    except Exception as exc:
        return None, 0.0, f"Image decoding error: {exc}"

    # Dimension validation
    width, height = rgb_img.size
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        return None, 0.0, f"Image dimensions too small ({width}x{height}). Minimum required is {MIN_DIMENSION}x{MIN_DIMENSION} pixels."
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        return None, 0.0, f"Image dimensions exceed {MAX_DIMENSION}x{MAX_DIMENSION} pixel limit ({width}x{height})."

    quality = _image_quality_score(rgb_img)
    return rgb_img, quality, None


def run_elasticnet_diagnosis(
    request: ElasticNetDiagnosisRequest,
    artifact_path: str | Path | None = None,
) -> ElasticNetDiagnosisResponse:
    """
    Execute ElasticNet inference with robust input validation, exact training feature
    extraction, uncalibrated confidence labeling, and safety abstentions.
    """
    start_time = time.perf_counter()

    # 1. Validate and decode image
    img, quality_score, validation_error = validate_and_decode_image(request.image_base64)
    if validation_error is not None or img is None:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        return ElasticNetDiagnosisResponse(
            status="rejected",
            rejection_reason=validation_error or "Image validation failed.",
            image_quality_score=quality_score,
            requires_expert=True,
            confidence_is_calibrated=False,
            inference_time_ms=latency,
            treatment_hints=[
                "Automated diagnosis is rejected due to invalid image input. Avoid unverified chemical spraying.",
                "Consult local Krishi Vigyan Kendra (KVK) or extension specialist for physical leaf examination.",
            ],
        )

    # 2. Check crop hint compatibility early if provided
    normalized_crop: str | None = None
    if request.crop_hint:
        normalized_crop = normalize_crop_name(request.crop_hint)
        if normalized_crop not in SUPPORTED_ELASTICNET_CROPS:
            latency = round((time.perf_counter() - start_time) * 1000, 2)
            return ElasticNetDiagnosisResponse(
                status="rejected",
                rejection_reason=(
                    f"Crop '{request.crop_hint}' is outside ElasticNet's 3 supported crops "
                    "(tomato, potato, maize). Model cannot reliably diagnose unsupported crops."
                ),
                crop_id=normalized_crop,
                image_quality_score=quality_score,
                requires_expert=True,
                confidence_is_calibrated=False,
                inference_time_ms=latency,
                treatment_hints=[
                    f"Automated diagnosis is unavailable for {request.crop_hint}. Avoid unverified chemical spraying.",
                    "Consult local Krishi Vigyan Kendra (KVK) or agricultural extension specialist for diagnosis.",
                ],
            )

    # 3. Load model artifact safely
    try:
        bundle = get_cached_elasticnet_bundle(artifact_path=artifact_path)
    except Exception as exc:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        return ElasticNetDiagnosisResponse(
            status="rejected",
            rejection_reason=f"ElasticNet model unavailable: {exc}. Refusing to fabricate diagnosis.",
            image_quality_score=quality_score,
            requires_expert=True,
            confidence_is_calibrated=False,
            inference_time_ms=latency,
            treatment_hints=[
                "Model artifact is temporarily unavailable. Avoid unverified chemical spraying.",
                "Consult local Krishi Vigyan Kendra (KVK) or extension specialist.",
            ],
        )

    model = bundle["model"]
    scaler = bundle["scaler"]
    class_metadata = bundle["class_metadata"]
    feature_config = bundle.get("feature_config", {})

    # 4. Feature Extraction (exact training pipeline)
    try:
        features = extract_features_from_image(img, config=feature_config)
    except Exception as exc:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        return ElasticNetDiagnosisResponse(
            status="rejected",
            rejection_reason=f"Feature extraction failed: {exc}.",
            image_quality_score=quality_score,
            requires_expert=True,
            confidence_is_calibrated=False,
            inference_time_ms=latency,
            treatment_hints=[
                "Feature extraction failed. Avoid unverified chemical spraying.",
                "Consult local extension specialist for physical leaf diagnosis.",
            ],
        )

    # Dimension integrity check
    expected_dim = getattr(scaler, "n_features_in_", 1606)
    if features.shape[0] != expected_dim:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        return ElasticNetDiagnosisResponse(
            status="rejected",
            rejection_reason=(
                f"Feature dimension mismatch: extracted {features.shape[0]}, "
                f"expected {expected_dim}."
            ),
            image_quality_score=quality_score,
            requires_expert=True,
            confidence_is_calibrated=False,
            inference_time_ms=latency,
            treatment_hints=[
                "Model pipeline error. Avoid unverified chemical spraying.",
                "Consult agricultural extension personnel.",
            ],
        )

    # 5. Scale & Predict
    features_scaled = scaler.transform(features.reshape(1, -1))
    probs = model.predict_proba(features_scaled)[0]

    # Rank classes by probability
    ranked_indices = np.argsort(probs)[::-1]
    top_1_idx = int(ranked_indices[0])
    top_1_conf = round(float(probs[top_1_idx]), 4)
    top_1_meta = class_metadata[top_1_idx]

    # Top-3 prediction items
    top_3_items: list[ElasticNetPredictionItem] = []
    for rank_idx in ranked_indices[:3]:
        idx = int(rank_idx)
        meta = class_metadata[idx]
        top_3_items.append(
            ElasticNetPredictionItem(
                class_idx=idx,
                display_name=meta["display_name"],
                crop=meta["crop"],
                disease=meta["disease"],
                is_healthy=meta["is_healthy"],
                confidence=round(float(probs[idx]), 4),
                confidence_is_calibrated=False,
            )
        )

    latency = round((time.perf_counter() - start_time) * 1000, 2)

    # 6. Safety and Uncertainty Evaluation
    # Check crop consistency between user hint and model top prediction
    if normalized_crop is not None and top_1_meta["crop"] != normalized_crop:
        return ElasticNetDiagnosisResponse(
            status="rejected",
            rejection_reason=(
                f"Crop conflict: Provided crop hint '{request.crop_hint}' conflicts with "
                f"predicted crop '{top_1_meta['crop']}'. Automated diagnosis is uncertain."
            ),
            predicted_class=top_1_meta["display_name"],
            crop_id=top_1_meta["crop"],
            disease=top_1_meta["disease"],
            confidence=top_1_conf,
            confidence_is_calibrated=False,
            top_3=top_3_items,
            requires_expert=True,
            image_quality_score=quality_score,
            inference_time_ms=latency,
            treatment_hints=[
                "Crop identity conflict detected. Avoid unverified chemical spraying.",
                "Consult local Krishi Vigyan Kendra (KVK) or agricultural extension specialist.",
            ],
        )

    # Check configurable confidence threshold
    threshold = request.confidence_threshold
    if top_1_conf < threshold:
        return ElasticNetDiagnosisResponse(
            status="rejected",
            rejection_reason=(
                f"Low model confidence ({top_1_conf:.2f} < threshold {threshold:.2f}). "
                "Model confidence is uncalibrated and prediction is uncertain. "
                "Upload a clearer photo or consult an agricultural extension specialist."
            ),
            predicted_class=top_1_meta["display_name"],
            crop_id=top_1_meta["crop"],
            disease=top_1_meta["disease"],
            confidence=top_1_conf,
            confidence_is_calibrated=False,
            top_3=top_3_items,
            requires_expert=True,
            image_quality_score=quality_score,
            inference_time_ms=latency,
            treatment_hints=[
                "Automated diagnosis is unconfirmed due to low/uncalibrated model confidence. Avoid unverified chemical spraying.",
                "Consult local Krishi Vigyan Kendra (KVK) or extension specialist for physical leaf confirmation.",
            ],
        )

    # Accepted prediction (passes confidence threshold and crop gating)
    # Note: Even when accepted, confidence remains uncalibrated, and treatment hints emphasize physical confirmation
    return ElasticNetDiagnosisResponse(
        status="accepted",
        rejection_reason=None,
        predicted_class=top_1_meta["display_name"],
        crop_id=top_1_meta["crop"],
        disease=top_1_meta["disease"],
        confidence=top_1_conf,
        confidence_is_calibrated=False,
        top_3=top_3_items,
        requires_expert=False,
        image_quality_score=quality_score,
        inference_time_ms=latency,
        treatment_hints=[
            f"Experimental ElasticNet prediction: {top_1_meta['display_name']} (uncalibrated confidence: {top_1_conf:.2f}).",
            "This model is under active testing and not yet verified for field deployment. Confirm with local extension personnel before applying treatments.",
        ],
    )
