"""Call remote MobileNetV3 inference (free Gradio HF Space) without loading torch locally."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.schemas.models import ImageDiagnosisResult, MobileNetV3PredictionItem

logger = logging.getLogger(__name__)


def _space_id_or_url(url: str) -> str:
    """Accept Space id, hf.space host, or huggingface.co/spaces/... URL."""
    raw = url.strip().rstrip("/")
    if "huggingface.co/spaces/" in raw:
        # https://huggingface.co/spaces/user/name -> user/name
        part = raw.split("huggingface.co/spaces/", 1)[1]
        return part.strip("/")
    return raw


def diagnose_image_via_remote(
    image_base64: str,
    crop_hint: str | None = None,
    confidence_threshold: float | None = None,
) -> ImageDiagnosisResult:
    settings = get_settings()
    base = settings.vision_inference_url
    if not base:
        raise RuntimeError("VISION_INFERENCE_URL is not configured")

    threshold = (
        confidence_threshold
        if confidence_threshold is not None
        else settings.vision_confidence_threshold
    )

    try:
        from gradio_client import Client
    except ImportError as exc:
        raise RuntimeError(
            "gradio_client is not installed. Add it to the slim backend deps "
            "(needed to call the free Gradio Space)."
        ) from exc

    space = _space_id_or_url(base)
    try:
        client = Client(space, verbose=False)
        # Matches api_name="predict" on the Gradio "API (base64)" tab.
        data = client.predict(
            image_base64,
            crop_hint or "",
            float(threshold),
            api_name="/predict",
        )
    except Exception as exc:
        raise RuntimeError(
            f"Remote MobileNet failed talking to Space '{space}': {exc}. "
            "Wake the Hugging Face Space in a browser, then retry."
        ) from exc

    if isinstance(data, str):
        import json

        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Space returned non-JSON string: {data[:200]}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected Space response type: {type(data)}")

    top_3_raw = data.get("top_3") or []
    top_3 = [
        MobileNetV3PredictionItem(
            class_idx=int(p.get("class_idx", 0)),
            display_name=str(p.get("display_name", "")),
            crop=str(p.get("crop", "")),
            disease=str(p.get("disease", "")),
            is_healthy=bool(p.get("is_healthy", False)),
            confidence=float(p.get("confidence", 0.0)),
            confidence_is_calibrated=bool(p.get("confidence_is_calibrated", False)),
        )
        for p in top_3_raw
        if isinstance(p, dict)
    ]

    status = str(data.get("status") or "rejected")
    model_version = str(data.get("model_version") or "mobilenetv3_plantdisease_best")
    if "hf_space" not in model_version and data.get("inference_source") == "hf_space":
        model_version = f"{model_version}@hf_space"

    if status == "rejected":
        return ImageDiagnosisResult(
            status="rejected",
            rejection_reason=data.get("rejection_reason"),
            plant_name=None,
            predicted_disease=None,
            is_healthy=False,
            crop_id=None,
            disease=None,
            confidence=data.get("confidence"),
            confidence_is_calibrated=False,
            model_version=model_version,
            top_3=top_3,
            requires_expert=True,
            treatment_hints=list(data.get("treatment_hints") or []),
            image_quality_score=data.get("image_quality_score"),
            latency_ms=data.get("latency_ms"),
        )

    return ImageDiagnosisResult(
        status="accepted",
        rejection_reason=None,
        plant_name=data.get("plant_name"),
        predicted_disease=data.get("predicted_disease"),
        is_healthy=bool(data.get("is_healthy", False)),
        crop_id=data.get("crop_id"),
        crop_confidence=data.get("confidence"),
        disease=data.get("disease"),
        disease_confidence=data.get("confidence"),
        confidence=data.get("confidence"),
        confidence_is_calibrated=False,
        severity="none" if data.get("is_healthy") else "moderate",
        model_version=model_version,
        top_3=top_3,
        requires_expert=False,
        treatment_hints=list(data.get("treatment_hints") or []),
        image_quality_score=data.get("image_quality_score"),
        latency_ms=data.get("latency_ms"),
    )


def diagnose_image_with_mobilenetv3(
    image_base64: str,
    crop_hint: str | None = None,
    confidence_threshold: float | None = None,
    checkpoint_path: Any = None,
) -> ImageDiagnosisResult:
    """Prefer remote HF Space when configured; otherwise local torch service."""
    settings = get_settings()
    if settings.vision_inference_url:
        logger.info("Using remote MobileNet Space %s", _space_id_or_url(settings.vision_inference_url))
        return diagnose_image_via_remote(
            image_base64,
            crop_hint=crop_hint,
            confidence_threshold=confidence_threshold,
        )

    from app.vision.mobilenetv3_service import (
        diagnose_image_with_mobilenetv3 as local_diagnose,
    )

    kwargs: dict[str, Any] = {
        "image_base64": image_base64,
        "crop_hint": crop_hint,
    }
    if confidence_threshold is not None:
        kwargs["confidence_threshold"] = confidence_threshold
    if checkpoint_path is not None:
        kwargs["checkpoint_path"] = checkpoint_path
    return local_diagnose(**kwargs)
