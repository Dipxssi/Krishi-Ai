"""Self-contained MobileNetV3 inference for the free Hugging Face Space."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from huggingface_hub import hf_hub_download
from PIL import Image
from torchvision import models, transforms

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

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

_MODEL: nn.Module | None = None
_DEVICE: torch.device | None = None
_CKPT_PATH: Path | None = None


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def create_mobilenetv3(num_classes: int = 17, variant: str = "small") -> nn.Module:
    if variant == "large":
        model = models.mobilenet_v3_large(weights=None)
    else:
        model = models.mobilenet_v3_small(weights=None)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    return model


def _resolve_checkpoint() -> Path:
    global _CKPT_PATH
    if _CKPT_PATH is not None and _CKPT_PATH.exists():
        return _CKPT_PATH
    repo = os.environ.get("HF_MODEL_REPO", "Ishan2702/krishiai-mobilenetv3")
    filename = os.environ.get("HF_MODEL_FILENAME", "mobilenetv3_plantdisease_best.pth")
    token = os.environ.get("HF_TOKEN") or None
    _CKPT_PATH = Path(hf_hub_download(repo_id=repo, filename=filename, token=token))
    return _CKPT_PATH


def load_model() -> tuple[nn.Module, torch.device]:
    """Load (or move) the model onto the current device. Call inside @spaces.GPU on ZeroGPU."""
    global _MODEL, _DEVICE
    device = get_device()
    if _MODEL is not None and _DEVICE == device:
        return _MODEL, _DEVICE

    path = _resolve_checkpoint()
    ckpt = torch.load(path, map_location=device, weights_only=False)
    variant = "small" if "small" in str(ckpt.get("architecture", "small")) else "large"
    model = create_mobilenetv3(num_classes=int(ckpt["num_classes"]), variant=variant)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    model.eval()
    _MODEL = model
    _DEVICE = device
    return model, device


def _eval_transform() -> transforms.Compose:
    # Must match ml/src/dataset.py get_eval_transforms — Resize((224,224)), no CenterCrop.
    # CenterCrop was cutting leaf lesions and making hosted predictions diverge from local.
    return transforms.Compose(
        [
            transforms.Resize(
                (224, 224),
                interpolation=transforms.InterpolationMode.BILINEAR,
            ),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


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


def predict_image(
    img: Image.Image,
    crop_hint: str | None = None,
    confidence_threshold: float = 0.60,
) -> dict[str, Any]:
    model, device = load_model()
    tensor = _eval_transform()(img.convert("RGB")).unsqueeze(0).to(device)

    t0 = time.time()
    with torch.no_grad():
        logits = model(tensor)
        probs = F.softmax(logits, dim=1)[0].cpu().numpy()
    latency_ms = (time.time() - t0) * 1000.0

    ranked = np.argsort(probs)[::-1]
    top_1_idx = int(ranked[0])
    top_1_conf = float(probs[top_1_idx])
    top_1_meta = TARGET_CLASSES[top_1_idx]

    top_3 = []
    for idx in ranked[:3]:
        idx_i = int(idx)
        m = TARGET_CLASSES[idx_i]
        top_3.append(
            {
                "class_idx": idx_i,
                "display_name": m["display_name"],
                "crop": m["crop"],
                "disease": m["disease"],
                "is_healthy": m["is_healthy"],
                "confidence": round(float(probs[idx_i]), 4),
                "confidence_is_calibrated": False,
            }
        )

    norm_hint = _normalize_crop_hint(crop_hint)
    if norm_hint is not None:
        if norm_hint not in ("tomato", "potato", "maize"):
            return {
                "status": "rejected",
                "rejection_reason": f"Crop '{crop_hint}' is outside supported crops (tomato, potato, maize).",
                "plant_name": None,
                "predicted_disease": None,
                "is_healthy": False,
                "predicted_class": None,
                "crop_id": None,
                "disease": None,
                "confidence": None,
                "confidence_is_calibrated": False,
                "model_version": "mobilenetv3_plantdisease_best",
                "top_3": [],
                "requires_expert": True,
                "latency_ms": round(latency_ms, 2),
                "treatment_hints": [
                    f"Automated leaf diagnosis is unavailable for {crop_hint}. Avoid unverified chemical spraying.",
                    "Consult local Krishi Vigyan Kendra (KVK) or agricultural extension specialist.",
                ],
            }
        if norm_hint != top_1_meta["crop"]:
            return {
                "status": "rejected",
                "rejection_reason": (
                    f"Crop conflict: Provided crop hint '{crop_hint}' conflicts with "
                    f"predicted crop '{top_1_meta['crop']}'."
                ),
                "plant_name": None,
                "predicted_disease": None,
                "is_healthy": False,
                "predicted_class": None,
                "crop_id": None,
                "disease": None,
                "confidence": round(top_1_conf, 4),
                "confidence_is_calibrated": False,
                "model_version": "mobilenetv3_plantdisease_best",
                "top_3": top_3,
                "requires_expert": True,
                "latency_ms": round(latency_ms, 2),
                "treatment_hints": [
                    "Crop conflict detected between farmer prompt and image prediction. Avoid unverified chemical spraying.",
                    "Consult local Krishi Vigyan Kendra (KVK) or extension specialist for physical verification.",
                ],
            }

    if top_1_conf < confidence_threshold:
        return {
            "status": "rejected",
            "rejection_reason": (
                f"Low model confidence ({top_1_conf:.2f} < threshold {confidence_threshold:.2f}). "
                "Prediction is uncertain and confidence is uncalibrated. "
                "Upload a clearer photo or consult an extension specialist."
            ),
            "plant_name": None,
            "predicted_disease": None,
            "is_healthy": False,
            "predicted_class": None,
            "crop_id": None,
            "disease": None,
            "confidence": round(top_1_conf, 4),
            "confidence_is_calibrated": False,
            "model_version": "mobilenetv3_plantdisease_best",
            "top_3": top_3,
            "requires_expert": True,
            "latency_ms": round(latency_ms, 2),
            "treatment_hints": [
                "Automated diagnosis is unconfirmed due to low/uncalibrated model confidence. Avoid unverified chemical spraying.",
                "Consult local Krishi Vigyan Kendra (KVK) or extension specialist for physical leaf confirmation.",
            ],
        }

    plant_name = (
        "Tomato"
        if top_1_meta["crop"] == "tomato"
        else ("Potato" if top_1_meta["crop"] == "potato" else "Maize")
    )
    is_healthy = bool(top_1_meta["is_healthy"])
    if is_healthy:
        predicted_disease = "Healthy"
    else:
        disp = top_1_meta["display_name"]
        for prefix in ("Corn ", "Tomato ", "Potato "):
            if disp.startswith(prefix):
                disp = disp[len(prefix) :]
                break
        predicted_disease = disp

    if not crop_hint:
        hints = [
            f"Provisional prediction: {plant_name} — {predicted_disease} (uncalibrated confidence: {top_1_conf:.2f}).",
            "Crop identity was not explicitly confirmed. This closed-set classifier only recognizes Tomato, Potato, and Maize (Corn).",
            "Confirm host crop and symptoms with local extension personnel before applying treatments.",
        ]
    else:
        hints = [
            f"Experimental MobileNetV3 prediction: {plant_name} — {predicted_disease} (uncalibrated confidence: {top_1_conf:.2f}).",
            "This model is under active testing and not yet verified for field deployment. Confirm with local extension personnel before applying treatments.",
        ]

    return {
        "status": "accepted",
        "rejection_reason": None,
        "plant_name": plant_name,
        "predicted_disease": predicted_disease,
        "is_healthy": is_healthy,
        "predicted_class": top_1_meta["display_name"],
        "crop_id": top_1_meta["crop"],
        "disease": top_1_meta["disease"],
        "confidence": round(top_1_conf, 4),
        "confidence_is_calibrated": False,
        "model_version": "mobilenetv3_plantdisease_best",
        "top_3": top_3,
        "requires_expert": False,
        "latency_ms": round(latency_ms, 2),
        "treatment_hints": hints,
    }
