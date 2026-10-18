"""Safe loader and integrity validator for plant disease model artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import joblib


def load_elasticnet_artifact(
    artifact_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Safely load and validate the ElasticNet model bundle.
    Raises clear service errors (FileNotFoundError, ValueError, TypeError)
    on missing, corrupted, or incompatible artifacts rather than fabricating a diagnosis.
    """
    if artifact_path is None:
        # Default project model path relative to project root
        repo_root = Path(__file__).resolve().parents[3]
        artifact_path = repo_root / "ml" / "models" / "elasticnet_plantdisease_best.joblib"
    else:
        artifact_path = Path(artifact_path)

    if not artifact_path.exists():
        raise FileNotFoundError(
            f"Model artifact not found at {artifact_path}. "
            "Refusing to fabricate automated diagnosis without a verified model."
        )

    try:
        bundle = joblib.load(artifact_path)
    except Exception as exc:
        raise ValueError(
            f"Failed to deserialize model artifact at {artifact_path}: {exc}. "
            "Refusing to fabricate diagnosis."
        ) from exc

    if not isinstance(bundle, dict):
        raise ValueError(
            "Incompatible model artifact: expected dictionary bundle. "
            "Refusing to fabricate diagnosis."
        )

    required_keys = {"model", "scaler", "classes", "feature_config"}
    missing = required_keys - set(bundle.keys())
    if missing:
        raise ValueError(
            f"Incompatible model artifact: missing required keys {missing}. "
            "Refusing to fabricate diagnosis."
        )

    model = bundle["model"]
    scaler = bundle["scaler"]
    feature_config = bundle["feature_config"]

    if not hasattr(model, "predict_proba"):
        raise TypeError(
            "Incompatible model object: missing 'predict_proba'. "
            "Refusing to fabricate diagnosis."
        )

    if not hasattr(scaler, "transform"):
        raise TypeError(
            "Incompatible scaler object: missing 'transform'. "
            "Refusing to fabricate diagnosis."
        )

    expected_dim = feature_config.get("total_feature_dim", 1606)
    scaler_dim = getattr(scaler, "n_features_in_", None)
    if scaler_dim != expected_dim:
        raise ValueError(
            f"Feature dimension mismatch: scaler expects {scaler_dim}, "
            f"feature config defines {expected_dim}. Refusing to fabricate diagnosis."
        )

    return bundle
