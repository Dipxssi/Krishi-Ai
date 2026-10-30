"""CPU MobileNetV3 inference for Render Free.

The weights are the same Ishan2702/krishiai-mobilenetv3 checkpoint, exported to ONNX
so the API does not need torch or a Hugging Face ZeroGPU quota.
"""

from __future__ import annotations

import base64
import io
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.schemas.models import ImageDiagnosisResult, MobileNetV3PredictionItem

TARGET_CLASSES: list[dict[str, Any]] = [
    {"class_idx": 0, "crop": "maize", "disease": "gray_leaf_spot", "display_name": "Corn Gray Leaf Spot", "is_healthy": False},
    {"class_idx": 1, "crop": "maize", "disease": "rust", "display_name": "Corn Common Rust", "is_healthy": False},
    {"class_idx": 2, "crop": "maize", "disease": "northern_leaf_blight", "display_name": "Corn Northern Leaf Blight", "is_healthy": False},
    {"class_idx": 3, "crop": "maize", "disease": "healthy", "display_name": "Corn Healthy", "is_healthy": True},
    {"class_idx": 4, "crop": "potato", "disease": "early_blight", "display_name": "Potato Early Blight", "is_healthy": False},
    {"class_idx": 5, "crop": "potato", "disease": "late_blight", "display_name": "Potato Late Blight", "is_healthy": False},
    {"class_idx": 6, "crop": "potato", "disease": "healthy", "display_name": "Potato Healthy", "is_healthy": True},
    {"class_idx": 7, "crop": "tomato", "disease": "bacterial_spot", "display_name": "Tomato Bacterial Spot", "is_healthy": False},
    {"class_idx": 8, "crop": "tomato", "disease": "early_blight", "display_name": "Tomato Early Blight", "is_healthy": False},
    {"class_idx": 9, "crop": "tomato", "disease": "late_blight", "display_name": "Tomato Late Blight", "is_healthy": False},
    {"class_idx": 10, "crop": "tomato", "disease": "leaf_mold", "display_name": "Tomato Leaf Mold", "is_healthy": False},
    {"class_idx": 11, "crop": "tomato", "disease": "septoria_leaf_spot", "display_name": "Tomato Septoria Leaf Spot", "is_healthy": False},
    {"class_idx": 12, "crop": "tomato", "disease": "spider_mites", "display_name": "Tomato Two-spotted Spider Mite", "is_healthy": False},
    {"class_idx": 13, "crop": "tomato", "disease": "target_spot", "display_name": "Tomato Target Spot", "is_healthy": False},
    {"class_idx": 14, "crop": "tomato", "disease": "yellow_leaf_curl_virus", "display_name": "Tomato Yellow Leaf Curl Virus", "is_healthy": False},
    {"class_idx": 15, "crop": "tomato", "disease": "mosaic_virus", "display_name": "Tomato Mosaic Virus", "is_healthy": False},
    {"class_idx": 16, "crop": "tomato", "disease": "healthy", "display_name": "Tomato Healthy", "is_healthy": True},
]

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
MODEL_VERSION = "mobilenetv3_plantdisease_best@cpu"

_SESSION: Any = None


def bundled_onnx_path() -> Path | None:
    path = Path(__file__).resolve().parents[2] / "models" / "mobilenetv3_plantdisease.onnx"
    return path if path.is_file() else None


def _session() -> Any:
    global _SESSION
    if _SESSION is not None:
        return _SESSION
    path = bundled_onnx_path()
    if path is None:
        raise RuntimeError("Bundled MobileNet ONNX file is missing")
    import onnxruntime as ort

    _SESSION = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    return _SESSION


def _decode_image(image_base64: str) -> Image.Image:
    raw = (image_base64 or "").split(",", 1)[-1].strip()
    data = base64.b64decode(raw, validate=False)
    if len(data) < 100:
        raise ValueError("Image too small")
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Image must be 10 MB or smaller")
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")
    except UnidentifiedImageError as exc:
        raise ValueError("Unrecognized image format") from exc


def preprocess(img: Image.Image) -> np.ndarray:
    """Match ml/src/dataset.py get_eval_transforms: bilinear resize to 224, ImageNet norm."""
    resized = img.convert("RGB").resize((224, 224), Image.Resampling.BILINEAR)
    arr = np.asarray(resized).astype(np.float32) / 255.0
    arr = (arr - IMAGENET_MEAN) / IMAGENET_STD
    return np.transpose(arr, (2, 0, 1))[None, ...]


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    exp = np.exp(shifted)
    return exp / np.sum(exp)


def _normalize_crop_hint(crop_hint: str | None) -> str | None:
    if not crop_hint:
        return None
    norm = crop_hint.strip().lower()
    if norm in ("corn", "maize", "sweet corn", "corn (maize)"):
        return "maize"
    if norm in ("tomatoes", "tomato"):
        return "tomato"
    if norm in ("potatoes", "potato"):
        return "potato"
    return norm


def _plant_name(crop: str) -> str:
    if crop == "tomato":
        return "Tomato"
    if crop == "potato":
        return "Potato"
    return "Maize"


def _disease_label(meta: dict[str, Any]) -> str:
    if meta["is_healthy"]:
        return "Healthy"
    disp = str(meta["display_name"])
    for prefix in ("Corn ", "Tomato ", "Potato "):
        if disp.startswith(prefix):
            return disp[len(prefix) :]
    return disp


def _crop_indices(crop: str) -> list[int]:
    return [i for i, meta in enumerate(TARGET_CLASSES) if meta["crop"] == crop]


def _best_in_crop(probs: np.ndarray, crop: str) -> tuple[int, float]:
    indices = _crop_indices(crop)
    best = max(indices, key=lambda idx: float(probs[idx]))
    return best, float(probs[best])


def _select_class_index(
    probs: np.ndarray,
    *,
    crop_hint: str | None,
    crop_prior: str | None,
) -> tuple[int, str]:
    """Pick a class index.

    An explicit hint or a farm-profile prior limits the choice to that crop so a
    tomato-heavy 17-class head does not replace maize. Returns (index, mode)
    where mode is "hint", "prior", or "open".
    """
    ranked = [int(idx) for idx in np.argsort(probs)[::-1]]
    open_idx = ranked[0]
    hint = _normalize_crop_hint(crop_hint)
    prior = _normalize_crop_hint(crop_prior)
    supported = {"tomato", "potato", "maize"}

    if hint in supported:
        idx, _ = _best_in_crop(probs, hint)
        return idx, "hint"

    if prior in supported and TARGET_CLASSES[open_idx]["crop"] != prior:
        prior_idx, prior_p = _best_in_crop(probs, prior)
        open_p = float(probs[open_idx])
        open_crop = TARGET_CLASSES[open_idx]["crop"]
        competitive = prior_p >= 0.35 * open_p
        # Ten of the 17 classes are tomato, so a maize or potato profile should
        # win over a tomato label when that crop still has a real score.
        tomato_bias = open_crop == "tomato" and prior in {"maize", "potato"} and prior_p >= 0.08
        if competitive or tomato_bias:
            return prior_idx, "prior"
    return open_idx, "open"


def _top_items(probs: np.ndarray, indices: list[int]) -> list[MobileNetV3PredictionItem]:
    ordered = sorted(indices, key=lambda idx: float(probs[idx]), reverse=True)
    items: list[MobileNetV3PredictionItem] = []
    for idx in ordered[:3]:
        meta = TARGET_CLASSES[idx]
        items.append(
            MobileNetV3PredictionItem(
                class_idx=idx,
                display_name=meta["display_name"],
                crop=meta["crop"],
                disease=meta["disease"],
                is_healthy=bool(meta["is_healthy"]),
                confidence=round(float(probs[idx]), 4),
                confidence_is_calibrated=False,
            )
        )
    return items


def _result_from_probs(
    probs: np.ndarray,
    *,
    crop_hint: str | None,
    crop_prior: str | None,
    confidence_threshold: float,
    latency_ms: float,
) -> ImageDiagnosisResult:
    ranked = [int(idx) for idx in np.argsort(probs)[::-1]]
    open_idx = ranked[0]
    open_meta = TARGET_CLASSES[open_idx]
    open_conf = float(probs[open_idx])
    chosen_idx, mode = _select_class_index(probs, crop_hint=crop_hint, crop_prior=crop_prior)
    top_1_meta = TARGET_CLASSES[chosen_idx]
    top_1_conf = float(probs[chosen_idx])
    pool = _crop_indices(top_1_meta["crop"]) if mode in {"hint", "prior"} else ranked
    top_3 = _top_items(probs, pool)

    def rejected(reason: str, hints: list[str], *, confidence: float | None, include_top3: bool) -> ImageDiagnosisResult:
        return ImageDiagnosisResult(
            status="rejected",
            rejection_reason=reason,
            is_healthy=False,
            confidence=confidence,
            confidence_is_calibrated=False,
            model_version=MODEL_VERSION,
            top_3=top_3 if include_top3 else [],
            requires_expert=True,
            treatment_hints=hints,
            latency_ms=round(latency_ms, 2),
        )

    norm_hint = _normalize_crop_hint(crop_hint)
    if norm_hint is not None and norm_hint not in ("tomato", "potato", "maize"):
        return rejected(
            f"Crop '{crop_hint}' is outside supported crops (tomato, potato, maize).",
            [
                f"Automated leaf diagnosis is unavailable for {crop_hint}. Avoid unverified chemical spraying.",
                "Consult local Krishi Vigyan Kendra (KVK) or agricultural extension specialist.",
            ],
            confidence=None,
            include_top3=False,
        )
    if norm_hint is not None and norm_hint != top_1_meta["crop"]:
        return rejected(
            (
                f"Crop conflict: Provided crop hint '{crop_hint}' conflicts with "
                f"predicted crop '{top_1_meta['crop']}'."
            ),
            [
                "Crop conflict detected between farmer prompt and image prediction. Avoid unverified chemical spraying.",
                "Consult local Krishi Vigyan Kendra (KVK) or extension specialist for physical verification.",
            ],
            confidence=round(top_1_conf, 4),
            include_top3=True,
        )
    prior = _normalize_crop_hint(crop_prior)
    if (
        mode == "open"
        and prior in {"maize", "potato"}
        and open_meta["crop"] == "tomato"
        and norm_hint is None
    ):
        prior_idx, prior_p = _best_in_crop(probs, prior)
        prior_meta = TARGET_CLASSES[prior_idx]
        return ImageDiagnosisResult(
            status="rejected",
            rejection_reason=(
                f"Your farm profile crop is {prior}. This photo was not labeled {open_meta['crop']}. "
                f"The strongest overall class was {_plant_name(open_meta['crop'])} · {_disease_label(open_meta)} "
                f"({open_conf:.0%}). Closest {prior} class is {_disease_label(prior_meta)} ({prior_p:.0%})."
            ),
            is_healthy=False,
            confidence=round(prior_p, 4),
            confidence_is_calibrated=False,
            model_version=MODEL_VERSION,
            top_3=_top_items(probs, _crop_indices(prior)),
            requires_expert=True,
            treatment_hints=[
                f"Confirm the plant is {prior} before any treatment.",
                f"Do not treat this photo as {open_meta['crop']} while the farm profile is {prior}.",
            ],
            latency_ms=round(latency_ms, 2),
        )
    active_threshold = 0.08 if mode == "prior" else confidence_threshold
    if top_1_conf < active_threshold:
        return rejected(
            (
                f"Low model confidence ({top_1_conf:.2f} < threshold {active_threshold:.2f}). "
                "Prediction is uncertain and confidence is uncalibrated. "
                "Upload a clearer photo or consult an extension specialist."
            ),
            [
                "Automated diagnosis is unconfirmed due to low/uncalibrated model confidence. Avoid unverified chemical spraying.",
                "Consult local Krishi Vigyan Kendra (KVK) or extension specialist for physical leaf confirmation.",
            ],
            confidence=round(top_1_conf, 4),
            include_top3=True,
        )

    plant = _plant_name(top_1_meta["crop"])
    disease = _disease_label(top_1_meta)
    is_healthy = bool(top_1_meta["is_healthy"])
    hints = [
        f"MobileNetV3 prediction: {plant} — {disease} (uncalibrated confidence: {top_1_conf:.2f}).",
        "Confirm with local extension personnel before applying treatments.",
    ]
    return ImageDiagnosisResult(
        status="accepted",
        plant_name=plant,
        predicted_disease=disease,
        is_healthy=is_healthy,
        crop_id=top_1_meta["crop"],
        crop_confidence=round(top_1_conf, 4),
        disease=top_1_meta["disease"],
        disease_confidence=round(top_1_conf, 4),
        confidence=round(top_1_conf, 4),
        confidence_is_calibrated=False,
        severity="none" if is_healthy else "moderate",
        model_version=MODEL_VERSION,
        top_3=top_3,
        requires_expert=False,
        treatment_hints=hints,
        latency_ms=round(latency_ms, 2),
    )


def diagnose_image_with_onnx(
    image_base64: str,
    crop_hint: str | None = None,
    confidence_threshold: float | None = None,
    crop_prior: str | None = None,
) -> ImageDiagnosisResult:
    settings = get_settings()
    threshold = (
        confidence_threshold
        if confidence_threshold is not None
        else settings.vision_confidence_threshold
    )
    img = _decode_image(image_base64)
    tensor = preprocess(img)
    session = _session()
    input_name = session.get_inputs()[0].name
    started = time.perf_counter()
    logits = session.run(None, {input_name: tensor})[0][0]
    latency_ms = (time.perf_counter() - started) * 1000.0
    return _result_from_probs(
        _softmax(np.asarray(logits, dtype=np.float32)),
        crop_hint=crop_hint,
        crop_prior=crop_prior,
        confidence_threshold=float(threshold),
        latency_ms=latency_ms,
    )
