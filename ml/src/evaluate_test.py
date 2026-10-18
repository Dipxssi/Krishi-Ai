"""Evaluation of the promoted ElasticNet model on the untouched PlantVillage test set."""

from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path
import joblib
import numpy as np
import sklearn
from PIL import Image
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score

from ml.src.config import FEATURES_DIR, MODELS_DIR, PROJECT_ROOT, SPLITS_DIR, TARGET_CLASSES

ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
from ml.src.extract_features import extract_split_features


def get_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def evaluate_test_set():
    print("=" * 70)
    print("PLANTVILLAGE ELASTICNET: FINAL TEST-SET EVALUATION")
    print("=" * 70)

    test_csv = SPLITS_DIR / "test.csv"
    val_csv = SPLITS_DIR / "val.csv"
    model_path = MODELS_DIR / "elasticnet_plantdisease_best.joblib"

    # 1. Feature Extraction on Test Set
    print("\n--- 1. Extracting Test Features ---")
    t0 = time.time()
    X_test, y_test = extract_split_features("test", test_csv, output_dir=FEATURES_DIR, batch_size=500, max_workers=6)
    feat_time = time.time() - t0
    print(f"Test features ready: shape={X_test.shape}, dtype={X_test.dtype} in {feat_time:.1f}s")

    # 2. Load Promoted Model Bundle
    print("\n--- 2. Loading Promoted Model Bundle ---")
    bundle = joblib.load(model_path)
    clf = bundle["model"]
    scaler = bundle["scaler"]
    classes = bundle["classes"]
    cfg = bundle["config"]
    feat_cfg = bundle["feature_config"]
    repro = bundle["reproducibility"]

    print(f"Loaded model from: {model_path.name}")
    print(f"Classifier: SAGA ElasticNet (C={cfg['C']}, l1_ratio={cfg['l1_ratio']}, tol={cfg.get('tol')}, max_iter={cfg.get('max_iter')})")
    print(f"Scaler: StandardScaler (n_features={scaler.n_features_in_})")

    # 3. Scale Features (Transform ONLY)
    print("\n--- 3. Transforming Test Features with Training Scaler ---")
    X_test_scaled = scaler.transform(X_test)

    # 4. Single Final Evaluation Inference
    print("\n--- 4. Executing Single Test-Set Inference ---")
    t_inf_start = time.time()
    test_probs = clf.predict_proba(X_test_scaled)
    test_preds = np.argmax(test_probs, axis=1)
    inf_time = time.time() - t_inf_start
    print(f"Inference completed in {inf_time:.2f}s ({len(test_preds)/inf_time:.1f} samples/s)")

    # 5. Compute Comprehensive Metrics
    print("\n--- 5. Computing Test Metrics ---")
    acc = float(accuracy_score(y_test, test_preds))
    macro_f1 = float(f1_score(y_test, test_preds, average="macro"))
    macro_prec = float(precision_score(y_test, test_preds, average="macro"))
    macro_rec = float(recall_score(y_test, test_preds, average="macro"))
    weighted_f1 = float(f1_score(y_test, test_preds, average="weighted"))
    weighted_prec = float(precision_score(y_test, test_preds, average="weighted"))
    weighted_rec = float(recall_score(y_test, test_preds, average="weighted"))

    print(f"Test Overall Accuracy:     {acc*100:.2f}% ({acc:.6f})")
    print(f"Test Macro-Averaged F1:    {macro_f1:.6f}")
    print(f"Test Macro Precision:      {macro_prec:.6f}")
    print(f"Test Macro Recall:         {macro_rec:.6f}")
    print(f"Test Weighted-Averaged F1: {weighted_f1:.6f}")

    # Per-Class Report
    raw_report = classification_report(y_test, test_preds, output_dict=True)
    cm = confusion_matrix(y_test, test_preds)

    per_class_results = {}
    print("\n--- Per-Class Test Performance ---")
    print(f"{'Class Name':<35} | {'Prec':<7} | {'Recall':<7} | {'F1-Score':<8} | {'Support':<7}")
    print("-" * 75)
    for meta in TARGET_CLASSES:
        idx = meta["class_idx"]
        name = meta["display_name"]
        cr = raw_report[str(idx)]
        per_class_results[name] = {
            "class_idx": idx,
            "crop": meta["crop"],
            "disease": meta["disease"],
            "is_healthy": meta["is_healthy"],
            "precision": float(cr["precision"]),
            "recall": float(cr["recall"]),
            "f1-score": float(cr["f1-score"]),
            "support": int(cr["support"]),
        }
        print(f"{name:<35} | {cr['precision']:.4f}  | {cr['recall']:.4f}  | {cr['f1-score']:.4f}   | {int(cr['support']):<7}")

    # 6. Read Test Manifest to Identify Misclassified Samples
    print("\n--- 6. Auditing Misclassified Test Samples ---")
    with open(test_csv, encoding="utf-8") as f:
        test_rows = list(csv.DictReader(f))

    misclassified = []
    cross_crop_count = 0
    healthy_confused_count = 0

    for i in range(len(test_rows)):
        true_idx = int(y_test[i])
        pred_idx = int(test_preds[i])
        if true_idx != pred_idx:
            row = test_rows[i]
            true_meta = TARGET_CLASSES[true_idx]
            pred_meta = TARGET_CLASSES[pred_idx]
            conf = float(test_probs[i, pred_idx])
            true_conf = float(test_probs[i, true_idx])

            is_cross_crop = (true_meta["crop"] != pred_meta["crop"])
            is_healthy_conf = (true_meta["is_healthy"] != pred_meta["is_healthy"])

            if is_cross_crop:
                cross_crop_count += 1
            if is_healthy_conf:
                healthy_confused_count += 1

            misclassified.append({
                "sample_idx": i,
                "rel_path": row["rel_path"],
                "group_id": row["group_id"],
                "true_idx": true_idx,
                "true_display_name": true_meta["display_name"],
                "true_crop": true_meta["crop"],
                "true_is_healthy": true_meta["is_healthy"],
                "pred_idx": pred_idx,
                "pred_display_name": pred_meta["display_name"],
                "pred_crop": pred_meta["crop"],
                "pred_is_healthy": pred_meta["is_healthy"],
                "predicted_confidence": round(conf, 4),
                "true_class_confidence": round(true_conf, 4),
                "is_cross_crop": is_cross_crop,
                "is_healthy_confused": is_healthy_conf,
            })

    total_errors = len(misclassified)
    print(f"Total Test Errors: {total_errors} / {len(y_test)} (Error rate: {total_errors/len(y_test)*100:.2f}%)")
    print(f"Within-Crop Errors (same plant species): {total_errors - cross_crop_count} ({(total_errors - cross_crop_count)/total_errors*100:.1f}% of errors)")
    print(f"Cross-Crop Errors: {cross_crop_count} ({cross_crop_count/total_errors*100:.1f}% of errors)")
    print(f"Healthy vs Diseased Confusions: {healthy_confused_count} ({healthy_confused_count/total_errors*100:.1f}% of errors)")
    print(f"Crop-Level Classification Accuracy on Test Set: {(len(y_test) - cross_crop_count) / len(y_test) * 100:.2f}%")
    print(f"Health-Status (Healthy vs Diseased) Accuracy:   {(len(y_test) - healthy_confused_count) / len(y_test) * 100:.2f}%")

    # 7. Comparison with Validation Metrics (Generalization Gap)
    print("\n--- 7. Generalization Gap Analysis (Validation vs. Test) ---")
    val_X = np.load(FEATURES_DIR / "X_val.npy")
    val_y = np.load(FEATURES_DIR / "y_val.npy")
    val_preds = clf.predict(scaler.transform(val_X))
    val_acc = float(accuracy_score(val_y, val_preds))
    val_macro_f1 = float(f1_score(val_y, val_preds, average="macro"))
    val_report = classification_report(val_y, val_preds, output_dict=True)

    acc_gap = acc - val_acc
    f1_gap = macro_f1 - val_macro_f1
    print(f"Validation Accuracy: {val_acc*100:.2f}% | Test Accuracy: {acc*100:.2f}% | Gap: {acc_gap*100:+.2f}%")
    print(f"Validation Macro-F1: {val_macro_f1:.4f} | Test Macro-F1: {macro_f1:.4f} | Gap: {f1_gap:+.4f}")

    per_class_gap = {}
    for meta in TARGET_CLASSES:
        idx = meta["class_idx"]
        name = meta["display_name"]
        v_f1 = val_report[str(idx)]["f1-score"]
        t_f1 = raw_report[str(idx)]["f1-score"]
        gap = t_f1 - v_f1
        per_class_gap[name] = {
            "val_f1": round(v_f1, 4),
            "test_f1": round(t_f1, 4),
            "f1_gap": round(gap, 4),
        }

    # 8. Assemble Full Artifact Payload
    test_results_payload = {
        "evaluation_name": "PlantVillage ElasticNet Final Test Set Evaluation",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_artifact": str(model_path.resolve()),
        "model_config": cfg,
        "feature_config": feat_cfg,
        "reproducibility": {
            **repro,
            "evaluation_time_seconds": round(inf_time, 2),
            "feature_extraction_seconds": round(feat_time, 2),
            "test_manifest_path": str(test_csv),
            "test_manifest_sha256": get_file_sha256(test_csv),
            "test_sample_count": len(y_test),
        },
        "overall_test_metrics": {
            "accuracy": round(acc, 6),
            "macro_f1": round(macro_f1, 6),
            "macro_precision": round(macro_prec, 6),
            "macro_recall": round(macro_rec, 6),
            "weighted_f1": round(weighted_f1, 6),
            "weighted_precision": round(weighted_prec, 6),
            "weighted_recall": round(weighted_rec, 6),
            "total_samples": len(y_test),
            "total_errors": total_errors,
            "crop_level_accuracy": round((len(y_test) - cross_crop_count) / len(y_test), 6),
            "health_status_accuracy": round((len(y_test) - healthy_confused_count) / len(y_test), 6),
        },
        "generalization_gap": {
            "val_accuracy": round(val_acc, 6),
            "test_accuracy": round(acc, 6),
            "accuracy_gap": round(acc_gap, 6),
            "val_macro_f1": round(val_macro_f1, 6),
            "test_macro_f1": round(macro_f1, 6),
            "macro_f1_gap": round(f1_gap, 6),
            "per_class_gap": per_class_gap,
        },
        "per_class_metrics": per_class_results,
        "confusion_matrix": cm.tolist(),
        "error_analysis": {
            "total_misclassified": total_errors,
            "cross_crop_errors": cross_crop_count,
            "within_crop_errors": total_errors - cross_crop_count,
            "healthy_confused_errors": healthy_confused_count,
            "misclassified_samples": misclassified,
        },
    }

    # Save Results JSON
    output_json = ARTIFACTS_DIR / "test_evaluation_results.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(test_results_payload, f, indent=2)
    print(f"\nSaved full structured test results to: {output_json}")

    print("\n" + "=" * 70)
    print("FINAL TEST EVALUATION COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    evaluate_test_set()
