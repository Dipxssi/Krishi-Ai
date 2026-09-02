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
    """Blur/brightness proxy: low variance + extreme brightness -> low quality."""
    thumb = img.copy()
    thumb.thumbnail((256, 256))
    stat = ImageStat.Stat(thumb)
    brightness = sum(stat.mean) / (3 * 255)
    # variance proxy via extrema spread
    spread = sum(mx - mn for mx, mn in zip(stat.extrema[0], stat.extrema[1], strict=False)) / (3 * 255)
    blur_penalty = 1.0 - min(1.0, spread * 2)
    bright_penalty = abs(brightness - 0.45) * 0.8
    return round(max(0.0, min(1.0, 1.0 - blur_penalty - bright_penalty)), 3)


def _color_ratios(img: Image.Image) -> tuple[float, float, float]:
    thumb = img.copy()
    thumb.thumbnail((128, 128))
    pixels = list(thumb.getdata())
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
    # weak default: tomato if green/brown leaf-like
    brown, green, _yellow = _color_ratios(img)
    if green + brown > 0.15:
        return "tomato", 0.55
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
        )

    quality = _image_quality_score(img)
    if quality < 0.65:
        return ImageDiagnosisResult(
            status="rejected",
            rejection_reason="Image quality too low — take a clearer close-up in daylight.",
            image_quality_score=quality,
            requires_expert=True,
        )

    crop_id, crop_conf = _route_crop(img, crop_hint)
    if crop_id is None or crop_conf < 0.70:
        return ImageDiagnosisResult(
            status="rejected",
            rejection_reason="Crop not identified confidently — set crop in farm profile or retake photo.",
            image_quality_score=quality,
            crop_id=crop_id,
            crop_confidence=crop_conf,
            requires_expert=True,
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
        return ImageDiagnosisResult(
            status="rejected",
            rejection_reason="Disease diagnosis uncertain — consult local agronomist.",
            image_quality_score=quality,
            crop_id=crop_id,
            crop_confidence=crop_conf,
            disease=expert.get("disease"),
            disease_confidence=expert.get("disease_confidence"),
            severity=expert.get("severity"),
            requires_expert=True,
            expert_id=expert.get("expert_id"),
            treatment_hints=expert.get("treatment_hints", []),
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


def diagnosis_to_dict(result: ImageDiagnosisResult) -> dict[str, Any]:
    return result.model_dump()
