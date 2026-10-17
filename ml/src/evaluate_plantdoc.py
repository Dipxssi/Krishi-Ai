"""External out-of-distribution evaluation on PlantDoc dataset.

Evaluates the promoted ElasticNet model (trained on PlantVillage) on PlantDoc.
Includes:
- Feature extraction using exact training pipeline
- Unambiguous mapped subset evaluation (13 classes, N=1,151)
- Broad mapped subset evaluation (with Corn leaf blight, N=1,342)
- PlantDoc Test split evaluation
- Confidence and uncertainty rejection audit (including 1,230 OOD samples)
- Saving artifacts to ml/artifacts/
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score

from ml.src.config import FEATURES_DIR, MODELS_DIR, PROJECT_ROOT, TARGET_CLASSES
from ml.src.features import extract_features_from_image

PLANTDOC_ROOT = Path("/Users/ishansharma2702/Downloads/PlantDoc-Dataset-master")
PLANTDOC_DIR = PROJECT_ROOT / "ml" / "plantdoc"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"


def _process_plantdoc_image(args: tuple[int, str]) -> tuple[int, np.ndarray]:
    idx, rel_path = args
    full_path = PLANTDOC_ROOT / rel_path
    feat = extract_features_from_image(full_path)
    return idx, feat


def extract_all_plantdoc_features(manifest_rows: list[dict[str, Any]], batch_size: int = 500, max_workers: int = 6) -> np.ndarray:
    cache_path = PLANTDOC_DIR / "X_plantdoc.npy"
    if cache_path.exists():
        print(f"Loading cached PlantDoc features from: {cache_path}")
        return np.load(cache_path)

    n_samples = len(manifest_rows)
    feature_dim = 1606
    print(f"Extracting features for {n_samples} PlantDoc images using {max_workers} processes...")

    X = np.zeros((n_samples, feature_dim), dtype=np.float32)
    items = [(i, manifest_rows[i]["rel_path"]) for i in range(n_samples)]

    t0 = time.time()
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for start_idx in range(0, n_samples, batch_size):
            chunk = items[start_idx : start_idx + batch_size]
            results = list(executor.map(_process_plantdoc_image, chunk, chunksize=50))
            for idx, feat in results:
                X[idx] = feat
            done = start_idx + len(chunk)
            rate = done / max(time.time() - t0, 1e-3)
            print(f"Progress: {done}/{n_samples} ({done/n_samples*100:.1f}%) - {rate:.1f} img/s")

    assert not np.isnan(X).any(), "NaN values found in PlantDoc feature matrix!"
    assert not np.isinf(X).any(), "Inf values found in PlantDoc feature matrix!"

    np.save(cache_path, X)
    print(f"Saved PlantDoc features to {cache_path} ({X.nbytes / (1024*1024):.1f} MB)")
    return X


def evaluate_plantdoc():
    print("=" * 80)
    print("PLANTDOC EXTERNAL BENCHMARK EVALUATION")
    print("=" * 80)

    # 1. Load Manifest
    manifest_csv = PLANTDOC_DIR / "manifest.csv"
    with open(manifest_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"Loaded PlantDoc manifest: {len(rows)} samples")

    # 2. Extract / Load Features
    X = extract_all_plantdoc_features(rows)

    # 3. Load Promoted Model
    model_path = MODELS_DIR / "elasticnet_plantdisease_best.joblib"
    bundle = joblib.load(model_path)
    clf = bundle["model"]
    scaler = bundle["scaler"]
    cfg = bundle["config"]

    print(f"\nLoaded model: {model_path.name}")
    print(f"Classifier: SAGA ElasticNet (C={cfg['C']}, l1_ratio={cfg['l1_ratio']})")

    # 4. Scale Features
    print("Scaling PlantDoc features with training scaler...")
    X_scaled = scaler.transform(X)

    # 5. Predict Probabilities
    print("Running inference on all 2,572 PlantDoc samples...")
    probs = clf.predict_proba(X_scaled)
    preds = np.argmax(probs, axis=1)
    max_conf = np.max(probs, axis=1)

    # 6. Separate Subsets
    unambiguous_indices = [i for i, r in enumerate(rows) if r["mapping_status"] == "unambiguous_mapped"]
    broad_indices = [i for i, r in enumerate(rows) if r["mapping_status"] in ("unambiguous_mapped", "ambiguous_mapped")]
    test_unambiguous_indices = [i for i, r in enumerate(rows) if r["mapping_status"] == "unambiguous_mapped" and r["split"] == "test"]
    test_broad_indices = [i for i, r in enumerate(rows) if r["mapping_status"] in ("unambiguous_mapped", "ambiguous_mapped") and r["split"] == "test"]
    oos_indices = [i for i, r in enumerate(rows) if r["mapping_status"] == "out_of_scope"]

    print(f"\nSubset Counts:")
    print(f"  Unambiguous Mapped (13 classes):           {len(unambiguous_indices)}")
    print(f"  Broad Mapped (incl. Corn leaf blight):      {len(broad_indices)}")
    print(f"  PlantDoc Test Split (Unambiguous):          {len(test_unambiguous_indices)}")
    print(f"  PlantDoc Test Split (Broad):                {len(test_broad_indices)}")
    print(f"  Out-of-Scope Non-Target Images (OOD):       {len(oos_indices)}")

    # Helper function to compute performance
    def compute_subset_metrics(indices: list[int], name: str) -> dict[str, Any]:
        y_true = np.array([int(rows[i]["target_class_idx"]) for i in indices])
        y_pred = preds[indices]
        y_conf = max_conf[indices]

        acc = float(accuracy_score(y_true, y_pred))
        macro_f1 = float(f1_score(y_true, y_pred, average="macro"))
        macro_prec = float(precision_score(y_true, y_pred, average="macro", zero_division=0))
        macro_rec = float(recall_score(y_true, y_pred, average="macro", zero_division=0))
        weighted_f1 = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

        # Crop-level accuracy
        true_crops = [rows[i]["target_crop"] for i in indices]
        pred_crops = [TARGET_CLASSES[p]["crop"] for p in y_pred]
        crop_correct = sum(tc == pc for tc, pc in zip(true_crops, pred_crops))
        crop_acc = float(crop_correct / len(indices))

        # Health-status accuracy
        true_healthy = [rows[i]["is_healthy"] == "True" for i in indices]
        pred_healthy = [TARGET_CLASSES[p]["is_healthy"] for p in y_pred]
        health_correct = sum(th == ph for th, ph in zip(true_healthy, pred_healthy))
        health_acc = float(health_correct / len(indices))

        # Present classes
        unique_classes = sorted(list(set(y_true)))
        rep = classification_report(y_true, y_pred, output_dict=True, zero_division=0)

        per_class = {}
        for c_idx in unique_classes:
            meta = TARGET_CLASSES[c_idx]
            cr = rep.get(str(c_idx), {"precision": 0.0, "recall": 0.0, "f1-score": 0.0, "support": 0})
            per_class[meta["display_name"]] = {
                "class_idx": c_idx,
                "crop": meta["crop"],
                "precision": round(float(cr["precision"]), 4),
                "recall": round(float(cr["recall"]), 4),
                "f1_score": round(float(cr["f1-score"]), 4),
                "support": int(cr["support"]),
            }

        cm = confusion_matrix(y_true, y_pred, labels=list(range(17)))

        print(f"\n--- {name} (N={len(indices)}) ---")
        print(f"Overall Accuracy:       {acc*100:.2f}% ({acc:.4f})")
        print(f"Macro-F1:               {macro_f1:.4f}")
        print(f"Weighted-F1:            {weighted_f1:.4f}")
        print(f"Crop-Level Accuracy:    {crop_acc*100:.2f}%")
        print(f"Health-Status Accuracy: {health_acc*100:.2f}%")
        print(f"Mean Confidence:        {float(np.mean(y_conf)):.4f}")

        return {
            "name": name,
            "sample_count": len(indices),
            "accuracy": round(acc, 4),
            "macro_f1": round(macro_f1, 4),
            "macro_precision": round(macro_prec, 4),
            "macro_recall": round(macro_rec, 4),
            "weighted_f1": round(weighted_f1, 4),
            "crop_level_accuracy": round(crop_acc, 4),
            "health_status_accuracy": round(health_acc, 4),
            "mean_confidence": round(float(np.mean(y_conf)), 4),
            "per_class_metrics": per_class,
            "confusion_matrix": cm.tolist(),
        }

    # Evaluate Subsets
    unambiguous_results = compute_subset_metrics(unambiguous_indices, "Primary Benchmark: Unambiguous Mapped Subset")
    broad_results = compute_subset_metrics(broad_indices, "Broad Benchmark: Including Corn Leaf Blight")
    test_unambiguous_results = compute_subset_metrics(test_unambiguous_indices, "PlantDoc Test Split (Unambiguous)")
    test_broad_results = compute_subset_metrics(test_broad_indices, "PlantDoc Test Split (Broad)")

    # 7. Confidence & Rejection Safeguard Analysis
    print("\n" + "=" * 80)
    print("CONFIDENCE & UNCERTAINTY REJECTION AUDIT")
    print("=" * 80)

    unamb_conf = max_conf[unambiguous_indices]
    unamb_true = np.array([int(rows[i]["target_class_idx"]) for i in unambiguous_indices])
    unamb_pred = preds[unambiguous_indices]
    unamb_correct_mask = (unamb_true == unamb_pred)

    oos_conf = max_conf[oos_indices]

    print(f"Confidence Distribution Summary:")
    print(f"  In-Scope Correct (N={unamb_correct_mask.sum()}):   Mean={np.mean(unamb_conf[unamb_correct_mask]):.4f}, Median={np.median(unamb_conf[unamb_correct_mask]):.4f}")
    if (~unamb_correct_mask).sum() > 0:
        print(f"  In-Scope Incorrect (N={(~unamb_correct_mask).sum()}): Mean={np.mean(unamb_conf[~unamb_correct_mask]):.4f}, Median={np.median(unamb_conf[~unamb_correct_mask]):.4f}")
    print(f"  Out-of-Scope OOD (N={len(oos_indices)}):       Mean={np.mean(oos_conf):.4f}, Median={np.median(oos_conf):.4f}")

    # Threshold evaluation sweep
    thresholds = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    rejection_sweep = []
    print(f"\n{'Threshold':<10} | {'In-Scope Retained':<18} | {'In-Scope Acc':<14} | {'OOD Rejected':<14} | {'OOD Rejection Rate'}")
    print("-" * 80)
    for tau in thresholds:
        # In-scope accepted
        in_accepted = unamb_conf >= tau
        in_acc = float(accuracy_score(unamb_true[in_accepted], unamb_pred[in_accepted])) if in_accepted.sum() > 0 else 0.0
        in_retained_pct = float(in_accepted.sum() / len(unambiguous_indices) * 100)

        # OOD rejected
        ood_rejected = oos_conf < tau
        ood_rej_pct = float(ood_rejected.sum() / len(oos_indices) * 100)

        rejection_sweep.append({
            "threshold": tau,
            "in_scope_retained_pct": round(in_retained_pct, 2),
            "in_scope_retained_count": int(in_accepted.sum()),
            "in_scope_retained_accuracy": round(in_acc, 4),
            "ood_rejected_pct": round(ood_rej_pct, 2),
            "ood_rejected_count": int(ood_rejected.sum()),
        })
        print(f"{tau:<10.2f} | {in_retained_pct:<5.1f}% ({in_accepted.sum()}/{len(unambiguous_indices)}) | {in_acc*100:<5.2f}%         | {ood_rejected.sum():<5} / {len(oos_indices)} | {ood_rej_pct:.1f}%")

    # Current Threshold 0.60 Performance
    tau_current = 0.60
    current_in_accepted = unamb_conf >= tau_current
    current_in_acc = float(accuracy_score(unamb_true[current_in_accepted], unamb_pred[current_in_accepted])) if current_in_accepted.sum() > 0 else 0.0
    current_ood_rejected = oos_conf < tau_current
    current_ood_rej_rate = float(current_ood_rejected.sum() / len(oos_indices))

    # 8. Save Artifacts
    full_artifact = {
        "evaluation_name": "PlantDoc External Benchmark Evaluation",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_path": str(model_path),
        "dataset": {
            "name": "PlantDoc (Singh et al. 2020)",
            "root_path": str(PLANTDOC_ROOT),
            "total_images": len(rows),
            "unambiguous_mapped_count": len(unambiguous_indices),
            "ambiguous_mapped_count": len(broad_indices) - len(unambiguous_indices),
            "out_of_scope_count": len(oos_indices),
        },
        "benchmarks": {
            "unambiguous_mapped": unambiguous_results,
            "broad_mapped": broad_results,
            "test_split_unambiguous": test_unambiguous_results,
            "test_split_broad": test_broad_results,
        },
        "uncertainty_rejection": {
            "current_threshold": tau_current,
            "in_scope_accepted_count": int(current_in_accepted.sum()),
            "in_scope_retained_rate": round(float(current_in_accepted.sum() / len(unambiguous_indices)), 4),
            "in_scope_retained_accuracy": round(current_in_acc, 4),
            "ood_rejected_count": int(current_ood_rejected.sum()),
            "ood_rejection_rate": round(current_ood_rej_rate, 4),
            "threshold_sweep": rejection_sweep,
        },
    }

    def json_default(obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        raise TypeError(f"Type {type(obj)} not serializable")

    out_json = ARTIFACTS_DIR / "plantdoc_evaluation_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(full_artifact, f, indent=2, default=json_default)
    print(f"\nSaved structured PlantDoc results to: {out_json}")

    print("\n" + "=" * 80)
    print("PLANTDOC EVALUATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    evaluate_plantdoc()
