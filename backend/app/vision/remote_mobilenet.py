"""Call remote MobileNetV3 inference (free Gradio HF Space) without loading torch locally."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.models import ImageDiagnosisResult, MobileNetV3PredictionItem

logger = logging.getLogger(__name__)


def _space_id_or_url(url: str) -> str:
    """Accept Space id, hf.space host, or huggingface.co/spaces/... URL."""
    raw = url.strip().rstrip("/")
    if "huggingface.co/spaces/" in raw:
        part = raw.split("huggingface.co/spaces/", 1)[1]
        return part.strip("/")
    return raw


def _space_runtime_url(space: str) -> str:
    raw = space.strip().rstrip("/")
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if "/" not in raw:
        return raw
    owner, name = raw.split("/", 1)
    slug = f"{owner}-{name}".lower().replace("_", "-")
    return f"https://{slug}.hf.space"


def _auth_headers() -> dict[str, str]:
    token = (get_settings().hf_token or "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _wake_space(space: str) -> None:
    """Free Spaces sleep. A GET starts the container before inference."""
    url = _space_runtime_url(space)
    if not url.startswith("http"):
        return
    try:
        httpx.get(
            url,
            timeout=httpx.Timeout(20.0, connect=10.0),
            follow_redirects=True,
            headers=_auth_headers(),
        )
        logger.info("Woke vision Space at %s", url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vision Space wake request failed for %s: %s", url, exc)


def _flush_sse_event(event_name: str, data_lines: list[str]) -> Any:
    """Return a diagnosis payload, raise on error, or None to keep reading."""
    payload = "\n".join(data_lines).strip()
    if event_name in {"heartbeat", "message"} or payload in {"", "null"}:
        return None
    if event_name == "error":
        raise RuntimeError(payload[:500] or "Space returned an error event")
    if event_name != "complete":
        return None
    parsed = json.loads(payload)
    if isinstance(parsed, list):
        if not parsed:
            raise RuntimeError("Space returned an empty result")
        return parsed[0]
    return parsed


def _read_gradio_sse(lines: Any) -> Any:
    event_name = "message"
    data_lines: list[str] = []
    saw_event = False
    for raw in lines:
        line = str(raw).strip("\r")
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
            saw_event = True
            data_lines = []
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].lstrip())
            saw_event = True
        elif line == "" and saw_event:
            result = _flush_sse_event(event_name, data_lines)
            event_name = "message"
            data_lines = []
            saw_event = False
            if result is not None:
                return result
    if saw_event:
        result = _flush_sse_event(event_name, data_lines)
        if result is not None:
            return result
    raise RuntimeError("Space stream ended before a diagnosis")


def _predict_on_space(space: str, image_base64: str, crop_hint: str | None, threshold: float) -> Any:
    """Gradio 6 named API: POST /gradio_api/call/v2/predict, then read the SSE result.

    The positional gradio_client call targets an older protocol and fails closed
    on the live Space, which is what dropped diagnosis onto the color-ratio heuristic.
    """
    runtime = _space_runtime_url(space).rstrip("/")
    timeout = httpx.Timeout(connect=20.0, read=180.0, write=60.0, pool=20.0)
    payload = {
        "image_base64": image_base64,
        "crop_hint": (crop_hint or "").strip() or None,
        "confidence_threshold": float(threshold),
    }
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=_auth_headers()) as client:
        posted = client.post(f"{runtime}/gradio_api/call/v2/predict", json=payload)
        posted.raise_for_status()
        event_id = (posted.json() or {}).get("event_id")
        if not event_id:
            raise RuntimeError(f"Space did not return event_id: {posted.text[:200]}")
        with client.stream(
            "GET",
            f"{runtime}/gradio_api/call/predict/{event_id}",
            headers={"Accept": "text/event-stream"},
        ) as stream:
            stream.raise_for_status()
            return _read_gradio_sse(stream.iter_lines())


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

    space = _space_id_or_url(base)
    last_error: Exception | None = None
    data: Any = None
    for attempt in range(2):
        _wake_space(space)
        try:
            data = _predict_on_space(space, image_base64, crop_hint, float(threshold))
            last_error = None
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "Remote MobileNet attempt %s/2 failed for %s: %s",
                attempt + 1,
                space,
                exc,
            )
            if "zerogpu" in str(exc).lower() or "quota" in str(exc).lower():
                break
            if attempt == 0:
                time.sleep(3)

    if last_error is not None or data is None:
        raise RuntimeError(
            f"Remote MobileNet failed talking to Space '{space}': {last_error}. "
            "Wake the Hugging Face Space in a browser, then retry."
        ) from last_error

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
    crop_prior: str | None = None,
) -> ImageDiagnosisResult:
    """Prefer the bundled ONNX model (no GPU quota). Then the HF Space, then local torch."""
    from app.vision.onnx_mobilenet import bundled_onnx_path

    if bundled_onnx_path() is not None:
        from app.vision.onnx_mobilenet import diagnose_image_with_onnx

        logger.info("Using bundled MobileNet ONNX on CPU")
        return diagnose_image_with_onnx(
            image_base64,
            crop_hint=crop_hint,
            confidence_threshold=confidence_threshold,
            crop_prior=crop_prior,
        )

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
