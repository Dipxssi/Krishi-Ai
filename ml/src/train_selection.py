"""Systematic hyperparameter tuning and model selection for ElasticNet multiclass classification.

Evaluates configurations using Validation Macro-F1 as primary criterion.
Tracks Potato Healthy metrics, convergence warnings, accuracy, and runtime.
Parallelized across available CPU cores for efficient exploration.
"""

from __future__ import annotations

import json
import time
import warnings
from pathlib import Path
import joblib
import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score, accuracy_score
from sklearn.preprocessing import StandardScaler

from ml.src.config import FEATURES_DIR, MODELS_DIR, TARGET_CLASSES, IDX_TO_CLASS
from ml.src.model import PlantDiseaseElasticNetClassifier


def _eval_single_config(config_id: int, params: dict, X_train_scaled: np.ndarray, y_train: np.ndarray, X_val_scaled: np.ndarray, y_val: np.ndarray, potato_idx: int) -> dict:
    t0 = time.time()
    converged = True
    conv_warning_msg = None

    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        clf = LogisticRegression(
            penalty="elasticnet",
            solver="saga",
            C=params["C"],
            l1_ratio=params["l1_ratio"],
            class_weight=params["class_weight"],
            max_iter=150,
            tol=1e-2,
            random_state=42,
        )
        clf.fit(X_train_scaled, y_train)

        for w in captured_warnings:
            if issubclass(w.category, ConvergenceWarning):
                converged = False
                conv_warning_msg = str(w.message)

    elapsed = time.time() - t0
    y_val_pred = clf.predict(X_val_scaled)

    acc = float(accuracy_score(y_val, y_val_pred))
    macro_f1 = float(f1_score(y_val, y_val_pred, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_val, y_val_pred, average="weighted", zero_division=0))

    p_report = classification_report(y_val, y_val_pred, output_dict=True, zero_division=0)
    potato_stats = p_report.get(str(potato_idx), {"precision": 0.0, "recall": 0.0, "f1-score": 0.0})

    n_iters = int(clf.n_iter_[0]) if hasattr(clf.n_iter_, "__len__") else int(clf.n_iter_)

    return {
        "config_id": config_id,
        "params": params,
        "val_accuracy": round(acc, 4),
        "val_macro_f1": round(macro_f1, 4),
        "val_weighted_f1": round(weighted_f1, 4),
        "potato_healthy_metrics": {
            "precision": round(float(potato_stats["precision"]), 4),
            "recall": round(float(potato_stats["recall"]), 4),
            "f1": round(float(potato_stats["f1-score"]), 4),
            "support": int(potato_stats.get("support", 0)),
        },
        "iterations": n_iters,
        "runtime_seconds": round(elapsed, 1),
        "converged": converged,
        "convergence_warning": conv_warning_msg,
        "fitted_model": clf,
    }


def run_model_selection():
    print("=== Step 3: Train and Select ElasticNet Multiclass Classifier ===")

    # 1. Load cached features
    X_train = np.load(FEATURES_DIR / "X_train.npy")
    y_train = np.load(FEATURES_DIR / "y_train.npy")
    X_val = np.load(FEATURES_DIR / "X_val.npy")
    y_val = np.load(FEATURES_DIR / "y_val.npy")

    print(f"Loaded Train: X={X_train.shape}, y={y_train.shape}")
    print(f"Loaded Val: X={X_val.shape}, y={y_val.shape}")

    # 2. Fit scaler strictly on training set
    print("Fitting StandardScaler strictly on training set...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)

    # 3. Define candidate configurations
    param_grid = [
        {"C": 0.1, "l1_ratio": 0.2, "class_weight": "balanced"},
        {"C": 0.1, "l1_ratio": 0.5, "class_weight": "balanced"},
        {"C": 0.5, "l1_ratio": 0.5, "class_weight": "balanced"},
        {"C": 1.0, "l1_ratio": 0.2, "class_weight": "balanced"},
        {"C": 1.0, "l1_ratio": 0.5, "class_weight": "balanced"},
        {"C": 1.0, "l1_ratio": 0.8, "class_weight": "balanced"},
        {"C": 1.0, "l1_ratio": 0.5, "class_weight": None},
        {"C": 2.0, "l1_ratio": 0.5, "class_weight": "balanced"},
    ]

    potato_idx = next(i for i, c in enumerate(TARGET_CLASSES) if c["folder_name"] == "Potato___healthy")

    print(f"\nEvaluating {len(param_grid)} configurations in parallel across CPU cores...")
    start_all = time.time()

    # Run in parallel across 4 workers
    eval_results = joblib.Parallel(n_jobs=4)(
        joblib.delayed(_eval_single_config)(
            idx + 1, params, X_train_scaled, y_train, X_val_scaled, y_val, potato_idx
        )
        for idx, params in enumerate(param_grid)
    )

    total_time = time.time() - start_all
    print(f"\nGrid search completed in {total_time:.1f}s.")

    # Sort results by validation macro-F1
    eval_results.sort(key=lambda r: r["val_macro_f1"], reverse=True)

    print(f"\n{'Rank':<4} | {'C':<5} | {'l1_ratio':<8} | {'class_weight':<13} | {'Val Acc':<8} | {'Macro-F1':<9} | {'Potato F1':<10} | {'Iters':<6} | {'Time (s)':<8} | {'Converged':<9}")
    print("-" * 98)
    for rank, res in enumerate(eval_results, 1):
        p = res["params"]
        cw_str = str(p["class_weight"])
        pot_f1 = res["potato_healthy_metrics"]["f1"]
        print(f"{rank:<4} | {p['C']:<5} | {p['l1_ratio']:<8} | {cw_str:<13} | {res['val_accuracy']:.4f}   | {res['val_macro_f1']:.4f}   | {pot_f1:.4f}     | {res['iterations']:<6} | {res['runtime_seconds']:<8.1f} | {str(res['converged']):<9}")

    best_res = eval_results[0]
    best_config = best_res["params"]
    best_model = best_res["fitted_model"]
    print("-" * 98)
    print(f"Selected Best Configuration: {best_config}")
    print(f"Validation Macro-F1: {best_res['val_macro_f1']:.4f} | Validation Accuracy: {best_res['val_accuracy']:.4f}")
    print(f"Potato Healthy Metrics: Precision={best_res['potato_healthy_metrics']['precision']}, Recall={best_res['potato_healthy_metrics']['recall']}, F1={best_res['potato_healthy_metrics']['f1']}")

    # Detailed evaluation of best model
    best_val_pred = best_model.predict(X_val_scaled)
    full_report = classification_report(
        y_val,
        best_val_pred,
        target_names=[c["display_name"] for c in TARGET_CLASSES],
        output_dict=True,
        zero_division=0,
    )
    cm = confusion_matrix(y_val, best_val_pred)

    artifacts_dir = Path("ml/artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    serializable_results = []
    for r in eval_results:
        entry = {k: v for k, v in r.items() if k != "fitted_model"}
        serializable_results.append(entry)

    summary = {
        "model_type": "LogisticRegression(penalty='elasticnet', solver='saga')",
        "best_config": best_config,
        "best_val_macro_f1": best_res["val_macro_f1"],
        "best_val_accuracy": best_res["val_accuracy"],
        "potato_healthy_metrics": best_res["potato_healthy_metrics"],
        "total_search_runtime_seconds": round(total_time, 1),
        "grid_results": serializable_results,
        "per_class_validation_report": full_report,
        "confusion_matrix": cm.tolist(),
    }

    with open(artifacts_dir / "model_selection_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved detailed results to {artifacts_dir / 'model_selection_results.json'}")

    # Save fitted model wrapper bundle
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    best_bundle_path = MODELS_DIR / "elasticnet_plantdisease_best.joblib"
    wrapper = PlantDiseaseElasticNetClassifier(
        C=best_config["C"],
        l1_ratio=best_config["l1_ratio"],
        class_weight=best_config["class_weight"],
    )
    wrapper.model = best_model
    wrapper.scaler = scaler
    wrapper.is_fitted = True
    wrapper.save(best_bundle_path)
    print(f"Saved selected model bundle to {best_bundle_path}")

    # Print Per-Class Summary Table
    print("\n=== Per-Class Validation Performance (Best Model) ===")
    print(f"{'Class Name':<35} | {'Precision':<10} | {'Recall':<8} | {'F1-Score':<8} | {'Support':<8}")
    print("-" * 78)
    for c in TARGET_CLASSES:
        name = c["display_name"]
        stats = full_report[name]
        print(f"{name:<35} | {stats['precision']:<10.4f} | {stats['recall']:<8.4f} | {stats['f1-score']:<8.4f} | {stats['support']:<8}")

    return summary


if __name__ == "__main__":
    run_model_selection()
