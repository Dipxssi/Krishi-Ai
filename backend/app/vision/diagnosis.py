"""Image diagnosis pipeline with AdapterMoE-style rejection gates."""

from __future__ import annotations

import base64
import io
from typing import Any

from PIL import Image, ImageStat

from app.schemas.models import ImageDiagnosisResult
from app.services.crop_registry import normalize_crop_name
from app.vision.experts import SUPPORTED_VISION_CROPS, run_crop_expert


def _decode_image(image_base64: str) -> Image.Image:
    raw = image_base64.split(",", 1)[-1]
    data = base64.b64decode(raw)
    return Image.open(io.BytesIO(data)).convert("RGB")


def _image_quality_score(img: Image.Image) -> float:
    """
    Extrema dynamic range and illumination proxy score in [0.0, 1.0].

    NOTE: Dynamic range spread is NOT a validated blur detector.
    Known failure modes:
    1. False-rejection risk: A sharp, uniformly colored leaf (e.g. solid healthy green)
       exhibits a narrow extrema range and may be penalized despite being in focus.
    2. False-acceptance risk: A blurry or cluttered field photograph containing dark soil
       and bright glare exhibits wide extrema range [0, 255] and evades rejection.

    Threshold calibration requires a dedicated expert-labeled real-image quality dataset;
    the current 0.65 threshold is a rough operational baseline and must not be altered
    based solely on synthetic image artifacts.
    """
    thumb = img.copy()
    thumb.thumbnail((256, 256))
    stat = ImageStat.Stat(thumb)
    brightness = sum(stat.mean) / (3 * 255)
    # variance proxy via extrema spread (illumination dynamic range, NOT optical blur)
    if stat.extrema and isinstance(stat.extrema[0], tuple):
        spread = sum(mx - mn for mn, mx in stat.extrema) / (len(stat.extrema) * 255)
    elif stat.extrema:
        mn, mx = stat.extrema
        spread = (mx - mn) / 255
    else:
        spread = 0.0
    spread_penalty = 1.0 - min(1.0, spread * 2)
    bright_penalty = abs(brightness - 0.45) * 0.8
    return round(max(0.0, min(1.0, 1.0 - spread_penalty - bright_penalty)), 3)


def _color_ratios(img: Image.Image) -> tuple[float, float, float]:
    thumb = img.copy()
    thumb.thumbnail((128, 128))
    get_pix = getattr(thumb, "get_flattened_data", thumb.getdata)
    pixels = list(get_pix())
    total = max(len(pixels), 1)
    brown = green = yellow = 0
    for r, g, b in pixels:
        if r > 100 and g < 90 and b < 80:
            brown += 1
        elif g > r and g > b:
            green += 1
        elif r > 150 and g > 120 and b < 100:
            yellow += 1
    return brown / total, green / total, yellow / total


def _route_crop(img: Image.Image, crop_hint: str | None) -> tuple[str | None, float]:
    if crop_hint:
        cid = normalize_crop_name(crop_hint)
        if cid and cid in SUPPORTED_VISION_CROPS:
            return cid, 0.85
    return None, 0.0


def diagnose_image_bytes(image_base64: str, crop_hint: str | None = None) -> ImageDiagnosisResult:
    try:
        img = _decode_image(image_base64)
    except Exception:
        return ImageDiagnosisResult(
            status="rejected",
            rejection_reason="Could not decode image — upload JPEG or PNG.",
            image_quality_score=0.0,
            requires_expert=True,
            crop_id=None,
            crop_confidence=None,
            disease=None,
            disease_confidence=None,
            severity=None,
        )

    try:
        quality = _image_quality_score(img)
        if quality < 0.65:
            return ImageDiagnosisResult(
                status="rejected",
                rejection_reason="Image quality too low (blurry, dark, or overexposed) — photograph a single leaf centered in bright daylight against a plain neutral background.",
                image_quality_score=quality,
                requires_expert=True,
                crop_id=None,
                crop_confidence=None,
                disease=None,
                disease_confidence=None,
                severity=None,
            )

        crop_id, crop_conf = _route_crop(img, crop_hint)
        if crop_id is None or crop_conf < 0.70:
            return ImageDiagnosisResult(
                status="rejected",
                rejection_reason="Crop identity not established (Crop not supported or identified confidently) — specify the crop (e.g., tomato, onion, maize) in your question or crop selection before diagnosis, or consult an agricultural extension specialist.",
                image_quality_score=quality,
                crop_id=None,
                crop_confidence=None,
                disease=None,
                disease_confidence=None,
                severity=None,
                requires_expert=True,
                treatment_hints=[
                    "Automated diagnosis requires a known crop to screen for diseases.",
                    "Consult local Krishi Vigyan Kendra (KVK) or agricultural extension specialist for physical leaf examination.",
                ],
            )

        brown, green, yellow = _color_ratios(img)
        expert = run_crop_expert(
            crop_id,
            quality_score=quality,
            brown_ratio=brown,
            green_ratio=green,
            yellow_ratio=yellow,
        )

        if expert["requires_expert"]:
            hints = expert.get("treatment_hints", [])
            safe_hints = [
                "Automated diagnosis is unconfirmed. Avoid unverified chemical spraying.",
                "Consult local Krishi Vigyan Kendra (KVK) or agricultural extension specialist for physical leaf confirmation.",
            ]
            for h in hints:
                if h not in safe_hints:
                    safe_hints.append(h)
            return ImageDiagnosisResult(
                status="rejected",
                rejection_reason="Disease diagnosis uncertain — routed to agricultural extension expert review before applying treatments.",
                image_quality_score=quality,
                crop_id=crop_id,
                crop_confidence=crop_conf,
                disease=None,
                disease_confidence=None,
                severity=None,
                requires_expert=True,
                expert_id=expert.get("expert_id"),
                treatment_hints=safe_hints,
            )

        return ImageDiagnosisResult(
            status="ok",
            image_quality_score=quality,
            crop_id=crop_id,
            crop_confidence=crop_conf,
            disease=expert.get("disease"),
            disease_confidence=expert.get("disease_confidence"),
            severity=expert.get("severity"),
            requires_expert=False,
            expert_id=expert.get("expert_id"),
            treatment_hints=expert.get("treatment_hints", []),
        )
    except Exception as exc:
        return ImageDiagnosisResult(
            status="rejected",
            rejection_reason=f"Inference error encountered: {exc}. Routed to agricultural expert review.",
            image_quality_score=0.0,
            requires_expert=True,
            treatment_hints=[
                "Automated processing encountered an error. Avoid unverified chemical spraying.",
                "Consult local Krishi Vigyan Kendra (KVK) or extension specialist for physical leaf examination.",
            ],
        )


def is_image_diagnosis_unconfirmed(image_diagnosis: ImageDiagnosisResult | None) -> bool:
    if image_diagnosis is None:
        return False
    if image_diagnosis.status not in ("ok", "accepted"):
        return True
    if image_diagnosis.requires_expert:
        return True
    if not image_diagnosis.crop_id or not str(image_diagnosis.crop_id).strip():
        return True
    if not image_diagnosis.disease or str(image_diagnosis.disease).strip().lower() in ("unconfirmed", "unknown", "none", ""):
        return True
    conf = (
        image_diagnosis.disease_confidence
        if image_diagnosis.disease_confidence is not None
        else image_diagnosis.confidence
    )
    if conf is None or float(conf) < 0.60:
        return True
    return False


def diagnosis_to_dict(result: ImageDiagnosisResult) -> dict[str, Any]:
    return result.model_dump()
