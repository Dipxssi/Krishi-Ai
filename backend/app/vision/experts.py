"""Per-crop disease experts (plug-in modules; heuristic v1, swappable for trained models)."""

from __future__ import annotations

from typing import Any

# crop_id -> list of (disease_id, display_name)
CROP_DISEASES: dict[str, list[tuple[str, str]]] = {
    "tomato": [
        ("early_blight", "Early blight"),
        ("late_blight", "Late blight"),
        ("healthy", "Healthy"),
    ],
    "potato": [
        ("late_blight", "Late blight"),
        ("early_blight", "Early blight"),
        ("healthy", "Healthy"),
    ],
    "maize": [
        ("gray_leaf_spot", "Gray leaf spot"),
        ("rust", "Common rust"),
        ("healthy", "Healthy"),
    ],
    "wheat": [("rust", "Rust"), ("healthy", "Healthy")],
    "rice": [("blast", "Blast"), ("healthy", "Healthy")],
    "onion": [("purple_blotch", "Purple blotch"), ("healthy", "Healthy")],
    "cotton": [("boll_rot", "Boll rot"), ("healthy", "Healthy")],
}

SUPPORTED_VISION_CROPS = list(CROP_DISEASES.keys())


def run_crop_expert(
    crop_id: str,
    *,
    quality_score: float,
    brown_ratio: float,
    green_ratio: float,
    yellow_ratio: float,
) -> dict[str, Any]:
    """
    Heuristic expert: uses color ratios as weak proxies until CNN models are trained.
    brown_ratio high -> foliar disease suspicion; green dominant -> healthy bias.
    """
    diseases = CROP_DISEASES.get(crop_id)
    if not diseases:
        return {
            "disease": None,
            "disease_confidence": 0.0,
            "severity": None,
            "requires_expert": True,
            "expert_id": crop_id,
            "treatment_hints": [f"No vision expert trained for {crop_id} yet."],
        }

    if brown_ratio > 0.22 and green_ratio < 0.45:
        disease_id, disease_name = diseases[0] if diseases[0][0] != "healthy" else diseases[0]
        for d_id, d_name in diseases:
            if d_id != "healthy":
                disease_id, disease_name = d_id, d_name
                break
        conf = min(0.92, 0.55 + brown_ratio)
        severity = "moderate" if conf < 0.8 else "high"
        requires_expert = conf < 0.75
        hints = [
            f"Possible {disease_name} on {crop_id} — scout lower leaves and confirm locally.",
            "Avoid spraying before heavy rain; prefer labeled fungicide per extension guidance.",
        ]
        return {
            "disease": disease_id,
            "disease_confidence": round(conf, 3),
            "severity": severity,
            "requires_expert": requires_expert,
            "expert_id": f"{crop_id}_expert_v1",
            "treatment_hints": hints,
        }

    if green_ratio > 0.5 and brown_ratio < 0.12:
        conf = min(0.88, 0.6 + green_ratio * 0.3)
        requires_expert = conf < 0.75
        return {
            "disease": "healthy",
            "disease_confidence": round(conf, 3),
            "severity": "none",
            "requires_expert": requires_expert,
            "expert_id": f"{crop_id}_expert_v1",
            "treatment_hints": ["No strong disease signal — continue scouting and monitor after rain."],
        }

    return {
        "disease": None,
        "disease_confidence": None,
        "severity": None,
        "requires_expert": True,
        "expert_id": f"{crop_id}_expert_v1",
        "treatment_hints": [
            "Automated diagnosis is unconfirmed. Avoid unverified chemical spraying.",
            "Consult local Krishi Vigyan Kendra (KVK) or agricultural extension specialist for physical leaf confirmation.",
            "Uncertain diagnosis — upload a clearer close-up of affected leaves.",
        ],
    }
