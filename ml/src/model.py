"""ElasticNet Multiclass Classification model pipeline for plant disease diagnosis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from ml.src.config import ELASTICNET_CONFIG, TARGET_CLASSES, IDX_TO_CLASS


class PlantDiseaseElasticNetClassifier:
    """
    Multiclass Logistic Regression with ElasticNet Regularization (L1 + L2).
    Uses SAGA solver with class weighting and probability calibration safeguards.
    """

    def __init__(
        self,
        C: float = 1.0,
        l1_ratio: float = 0.5,
        class_weight: str | dict | None = "balanced",
        max_iter: int = 2000,
        tol: float = 1e-3,
        random_state: int = 42,
        min_confidence_threshold: float = 0.60,
    ):
        self.C = C
        self.l1_ratio = l1_ratio
        self.class_weight = class_weight
        self.max_iter = max_iter
        self.tol = tol
        self.random_state = random_state
        self.min_confidence_threshold = min_confidence_threshold

        self.scaler = StandardScaler()
        self.model = LogisticRegression(
            penalty=ELASTICNET_CONFIG["penalty"],
            solver=ELASTICNET_CONFIG["solver"],
            C=self.C,
            l1_ratio=self.l1_ratio,
            class_weight=self.class_weight,
            max_iter=self.max_iter,
            tol=self.tol,
            random_state=self.random_state,
        )
        self.is_fitted = False
        self.class_metadata = TARGET_CLASSES

    def fit(self, X: np.ndarray, y: np.ndarray) -> "PlantDiseaseElasticNetClassifier":
        """Fit scaler and ElasticNet model on training features."""
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities."""
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted yet.")
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)

    def predict_single_with_safeguards(self, feature_vector: np.ndarray) -> dict[str, Any]:
        """
        Run inference on a single image feature vector with AdapterMoE-style uncertainty rejection.
        Returns a dictionary aligned with backend ImageDiagnosisResult schema.
        """
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted yet.")

        if feature_vector.ndim == 1:
            feature_vector = feature_vector.reshape(1, -1)

        probs = self.predict_proba(feature_vector)[0]
        top_idx = int(np.argmax(probs))
        confidence = float(probs[top_idx])
        meta = IDX_TO_CLASS[top_idx]

        # Uncertainty safeguard: reject if below confidence threshold
        if confidence < self.min_confidence_threshold:
            return {
                "status": "rejected",
                "rejection_reason": (
                    f"Model confidence ({confidence:.2f}) is below threshold ({self.min_confidence_threshold:.2f}). "
                    "Upload a clearer close-up or consult local extension."
                ),
                "crop_id": meta["crop"],
                "crop_confidence": confidence,
                "disease": meta["disease"],
                "disease_confidence": round(confidence, 3),
                "severity": "uncertain",
                "requires_expert": True,
                "display_name": meta["display_name"],
                "probabilities": {IDX_TO_CLASS[i]["display_name"]: round(float(p), 4) for i, p in enumerate(probs)},
            }

        severity = "none" if meta["is_healthy"] else ("moderate" if confidence < 0.85 else "high")

        return {
            "status": "ok",
            "rejection_reason": None,
            "crop_id": meta["crop"],
            "crop_confidence": round(confidence, 3),
            "disease": meta["disease"],
            "disease_confidence": round(confidence, 3),
            "severity": severity,
            "requires_expert": False,
            "display_name": meta["display_name"],
            "probabilities": {IDX_TO_CLASS[i]["display_name"]: round(float(p), 4) for i, p in enumerate(probs)},
        }

    def save(self, filepath: str | Path) -> None:
        """Serialize model, scaler, and metadata."""
        dest = Path(filepath)
        dest.parent.mkdir(parents=True, exist_ok=True)
        bundle = {
            "model": self.model,
            "scaler": self.scaler,
            "config": {
                "C": self.C,
                "l1_ratio": self.l1_ratio,
                "class_weight": self.class_weight,
                "min_confidence_threshold": self.min_confidence_threshold,
            },
            "class_metadata": self.class_metadata,
            "is_fitted": self.is_fitted,
        }
        joblib.dump(bundle, dest)

    @classmethod
    def load(cls, filepath: str | Path) -> "PlantDiseaseElasticNetClassifier":
        """Deserialize trained model."""
        bundle = joblib.load(filepath)
        cfg = bundle["config"]
        instance = cls(
            C=cfg["C"],
            l1_ratio=cfg["l1_ratio"],
            class_weight=cfg["class_weight"],
            min_confidence_threshold=cfg["min_confidence_threshold"],
        )
        instance.model = bundle["model"]
        instance.scaler = bundle["scaler"]
        instance.class_metadata = bundle["class_metadata"]
        instance.is_fitted = bundle["is_fitted"]
        return instance
