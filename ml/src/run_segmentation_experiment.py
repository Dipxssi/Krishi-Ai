"""Controlled experiment comparing Original vs. Segmented PlantDoc development subset.

Evaluates whether ExG + Otsu leaf foreground segmentation improves out-of-distribution
generalization on the deduplicated PlantDoc development subset (1,043 images).
Preserves the existing ElasticNet model and fitted scaler completely unchanged.
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
from PIL import Image
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score

from ml.src.config import FEATURES_DIR, MODELS_DIR, PROJECT_ROOT, TARGET_CLASSES

ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
from ml.src.features import extract_features_from_image
from ml.src.segmentation import segment_leaf_foreground

PLANTDOC_ROOT = Path("/Users/ishansharma2702/Downloads/PlantDoc-Dataset-master")
PLANTDOC_DIR = PROJECT_ROOT / "ml" / "plantdoc"


def _process_single_segmented_image(args: tuple[int, str]) -> tuple[int, np.ndarray, dict[str, Any]]:
    idx, rel_path = args
    full_path = PLANTDOC_ROOT / rel_path
    with Image.open(full_path) as raw_img:
        seg_img, meta = segment_leaf_foreground(raw_img)
    feat = extract_features_from_image(seg_img)
    return idx, feat, meta


def run_experiment():
    print("=" * 80)
    print("CONTROLLED SEGMENTATION EXPERIMENT (PLANTDOC DEVELOPMENT SUBSET)")
    print("=" * 80)

    # 1. Load Manifest & Identify Deduplicated Dev Subset
    manifest_csv = PLANTDOC_DIR / "manifest.csv"
    with open(manifest_csv, encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    # Identify test image hashes to strictly prevent any duplicate leakage
    test_hashes = set()
    for r in all_rows:
        if r["split"] == "test":
            p = PLANTDOC_ROOT / r["rel_path"]
            if p.exists():
                with open(p, "rb") as f:
                    test_hashes.add(hashlib.md5(f.read()).hexdigest())

    # Filter unambiguous train images excluding any test duplicates
    dev_rows = []
    excluded_dups = []
    for r in all_rows:
        if r["split"] == "train" and r["mapping_status"] == "unambiguous_mapped":
            p = PLANTDOC_ROOT / r["rel_path"]
            with open(p, "rb") as f:
                h = hashlib.md5(f.read()).hexdigest()
            if h in test_hashes:
                excluded_dups.append(r)
            else:
                dev_rows.append(r)

    print(f"\nManifest Development Set Breakdown:")
    print(f"  Total Unambiguous Train Images: {len(dev_rows) + len(excluded_dups)}")
    print(f"  Exact Duplicates Excluded:      {len(excluded_dups)}")
    print(f"  Approved Clean Development Set: {len(dev_rows)} images across 13 classes")

    y_dev = np.array([int(r["target_class_idx"]) for r in dev_rows])
    dev_image_ids = [int(r["image_id"]) for r in dev_rows]

    # 2. Load Promoted Production Model & Scaler
    model_path = MODELS_DIR / "elasticnet_plantdisease_best.joblib"
    bundle = joblib.load(model_path)
    clf = bundle["model"]
    scaler = bundle["scaler"]
    print(f"\nLoaded model bundle: {model_path.name}")
    print(f"Classifier: SAGA ElasticNet (C={bundle['config']['C']}, l1_ratio={bundle['config']['l1_ratio']})")
    print(f"Scaler: StandardScaler (n_features={scaler.n_features_in_})")

    # 3. Pipeline A: Original Unsegmented Images
    print("\n" + "-" * 60)
    print("PIPELINE A: ORIGINAL UNSEGMENTED IMAGES")
    print("-" * 60)
    t0_a = time.time()

    # Load from pre-extracted PlantDoc features using exact row indices
    X_all_raw = np.load(PLANTDOC_DIR / "X_plantdoc.npy")
    dev_indices_in_all = [int(r["image_id"]) - 1 for r in dev_rows]
    X_dev_raw = X_all_raw[dev_indices_in_all]

    X_dev_raw_scaled = scaler.transform(X_dev_raw)
    probs_a = clf.predict_proba(X_dev_raw_scaled)
    preds_a = clf.predict(X_dev_raw_scaled)
    t_elapsed_a = time.time() - t0_a

    acc_a = float(accuracy_score(y_dev, preds_a))
    macro_f1_a = float(f1_score(y_dev, preds_a, average="macro", zero_division=0))
    weighted_f1_a = float(f1_score(y_dev, preds_a, average="weighted", zero_division=0))
    corn_healthy_idx = 3
    false_corn_healthy_a = int(np.sum((preds_a == corn_healthy_idx) & (y_dev != corn_healthy_idx)))
    corn_healthy_pred_rate_a = float(np.sum(preds_a == corn_healthy_idx) / len(y_dev))

    print(f"Pipeline A Completed in {t_elapsed_a:.2f}s")
    print(f"  Accuracy:                      {acc_a*100:.2f}% ({acc_a:.4f})")
    print(f"  Macro-F1:                      {macro_f1_a:.4f}")
    print(f"  Weighted-F1:                   {weighted_f1_a:.4f}")
    print(f"  Predictions of 'Corn Healthy': {np.sum(preds_a == corn_healthy_idx)} ({corn_healthy_pred_rate_a*100:.1f}%)")
    print(f"  False 'Corn Healthy' Rate:     {false_corn_healthy_a}/{len(y_dev)} ({false_corn_healthy_a/len(y_dev)*100:.1f}%)")

    # 4. Pipeline B: Segmented Images (ExG + Otsu + Morphological)
    print("\n" + "-" * 60)
    print("PIPELINE B: SEGMENTED IMAGES (ExG + OTSU + GREY INFILL)")
    print("-" * 60)
    t0_b = time.time()

    seg_cache_path = PLANTDOC_DIR / "X_dev_seg.npy"
    seg_meta_path = PLANTDOC_DIR / "seg_metadata_dev.json"

    if seg_cache_path.exists() and seg_meta_path.exists():
        print(f"Loading cached segmented features from: {seg_cache_path}")
        X_dev_seg = np.load(seg_cache_path)
        with open(seg_meta_path) as mf:
            seg_metadata_list = json.load(mf)
    else:
        seg_items = [(i, dev_rows[i]["rel_path"]) for i in range(len(dev_rows))]
        X_dev_seg = np.zeros((len(dev_rows), 1606), dtype=np.float32)
        seg_metadata_list = [{} for _ in range(len(dev_rows))]

        print(f"Extracting segmented features for {len(dev_rows)} images with 6 parallel workers...")
        with ProcessPoolExecutor(max_workers=6) as executor:
            for chunk_start in range(0, len(seg_items), 200):
                chunk = seg_items[chunk_start : chunk_start + 200]
                results = list(executor.map(_process_single_segmented_image, chunk, chunksize=25))
                for i, feat, meta in results:
                    X_dev_seg[i] = feat
                    seg_metadata_list[i] = meta
                done = min(chunk_start + len(chunk), len(dev_rows))
                print(f"  Progress: {done}/{len(dev_rows)} ({done/len(dev_rows)*100:.1f}%)")

        np.save(seg_cache_path, X_dev_seg)
        with open(seg_meta_path, "w") as mf:
            json.dump(seg_metadata_list, mf)
        print(f"Saved segmented features cache to {seg_cache_path}")

    t_feat_b = time.time() - t0_b
    print(f"Feature extraction completed in {t_feat_b:.1f}s")

    # Transform using exact same training scaler
    X_dev_seg_scaled = scaler.transform(X_dev_seg)
    probs_b = clf.predict_proba(X_dev_seg_scaled)
    preds_b = clf.predict(X_dev_seg_scaled)
    t_elapsed_b = time.time() - t0_b

    acc_b = float(accuracy_score(y_dev, preds_b))
    macro_f1_b = float(f1_score(y_dev, preds_b, average="macro", zero_division=0))
    weighted_f1_b = float(f1_score(y_dev, preds_b, average="weighted", zero_division=0))
    false_corn_healthy_b = int(np.sum((preds_b == corn_healthy_idx) & (y_dev != corn_healthy_idx)))
    corn_healthy_pred_rate_b = float(np.sum(preds_b == corn_healthy_idx) / len(y_dev))

    fallback_count = sum(m["is_fallback"] for m in seg_metadata_list)
    fallback_rate = float(fallback_count / len(dev_rows))
    coverages = [m["coverage"] for m in seg_metadata_list]

    print(f"Pipeline B Completed in {t_elapsed_b:.2f}s")
    print(f"  Accuracy:                      {acc_b*100:.2f}% ({acc_b:.4f})")
    print(f"  Macro-F1:                      {macro_f1_b:.4f}")
    print(f"  Weighted-F1:                   {weighted_f1_b:.4f}")
    print(f"  Predictions of 'Corn Healthy': {np.sum(preds_b == corn_healthy_idx)} ({corn_healthy_pred_rate_b*100:.1f}%)")
    print(f"  False 'Corn Healthy' Rate:     {false_corn_healthy_b}/{len(y_dev)} ({false_corn_healthy_b/len(y_dev)*100:.1f}%)")
    print(f"  Segmentation Fallback Count:   {fallback_count} / {len(dev_rows)} ({fallback_rate*100:.2f}%)")
    print(f"  Mean Leaf Coverage:            {np.mean(coverages)*100:.1f}% (median: {np.median(coverages)*100:.1f}%)")

    # 5. Per-Class Performance Comparison
    rep_a = classification_report(y_dev, preds_a, output_dict=True, zero_division=0)
    rep_b = classification_report(y_dev, preds_b, output_dict=True, zero_division=0)
    cm_a = confusion_matrix(y_dev, preds_a, labels=list(range(17)))
    cm_b = confusion_matrix(y_dev, preds_b, labels=list(range(17)))

    unique_classes = sorted(list(set(y_dev)))
    per_class_comparison = {}
    print("\n" + "=" * 80)
    print("PER-CLASS COMPARISON (PIPELINE A: ORIGINAL vs. PIPELINE B: SEGMENTED)")
    print("=" * 80)
    print(f"{'Class Name':<32} | {'Orig F1':<8} | {'Seg F1':<8} | {'F1 Gap':<8} | {'Orig Rec':<9} | {'Seg Rec':<9} | {'Support'}")
    print("-" * 88)
    for c_idx in unique_classes:
        name = TARGET_CLASSES[c_idx]["display_name"]
        cr_a = rep_a.get(str(c_idx), {"f1-score": 0.0, "recall": 0.0, "precision": 0.0, "support": 0})
        cr_b = rep_b.get(str(c_idx), {"f1-score": 0.0, "recall": 0.0, "precision": 0.0, "support": 0})
        gap = float(cr_b["f1-score"] - cr_a["f1-score"])
        sign = "+" if gap >= 0 else ""
        per_class_comparison[name] = {
            "class_idx": c_idx,
            "crop": TARGET_CLASSES[c_idx]["crop"],
            "support": int(cr_a["support"]),
            "orig_f1": round(float(cr_a["f1-score"]), 4),
            "seg_f1": round(float(cr_b["f1-score"]), 4),
            "f1_gap": round(gap, 4),
            "orig_recall": round(float(cr_a["recall"]), 4),
            "seg_recall": round(float(cr_b["recall"]), 4),
            "orig_precision": round(float(cr_a["precision"]), 4),
            "seg_precision": round(float(cr_b["precision"]), 4),
        }
        print(f"{name:<32} | {cr_a['f1-score']:<8.4f} | {cr_b['f1-score']:<8.4f} | {sign}{gap:<7.4f} | {cr_a['recall']:<9.4f} | {cr_b['recall']:<9.4f} | {int(cr_a['support'])}")

    # 6. Visual Audit of 10 Distinct Segmentation Cases
    print("\n" + "=" * 80)
    print("VISUAL AUDIT OF 10 SEGMENTATION CASES")
    print("=" * 80)
    audit_cases = []

    # Select 5 improved/success cases and 5 degraded/fallback cases
    case_indices = [
        # Case 1-3: Samples where segmentation turned incorrect into correct
        *np.where((preds_a != y_dev) & (preds_b == y_dev))[0][:4],
        # Case 4-6: Samples where segmentation turned correct into incorrect
        *np.where((preds_a == y_dev) & (preds_b != y_dev))[0][:3],
        # Case 7-8: Fallback cases
        *np.where(np.array([m["is_fallback"] for m in seg_metadata_list]))[0][:3],
    ]
    # Ensure at least 10 unique
    if len(case_indices) < 10:
        extra = [i for i in range(len(dev_rows)) if i not in case_indices][: 10 - len(case_indices)]
        case_indices.extend(extra)
    case_indices = case_indices[:10]

    for k, idx in enumerate(case_indices, 1):
        r = dev_rows[idx]
        m = seg_metadata_list[idx]
        true_name = TARGET_CLASSES[y_dev[idx]]["display_name"]
        pred_a_name = TARGET_CLASSES[preds_a[idx]]["display_name"]
        pred_b_name = TARGET_CLASSES[preds_b[idx]]["display_name"]
        conf_a = float(probs_a[idx, preds_a[idx]])
        conf_b = float(probs_b[idx, preds_b[idx]])

        if preds_a[idx] != y_dev[idx] and preds_b[idx] == y_dev[idx]:
            outcome = "FIXED (Incorrect -> Correct)"
        elif preds_a[idx] == y_dev[idx] and preds_b[idx] != y_dev[idx]:
            outcome = "DEGRADED (Correct -> Incorrect)"
        elif m["is_fallback"]:
            outcome = f"FALLBACK ({m['fallback_reason']})"
        elif preds_b[idx] == y_dev[idx]:
            outcome = "MAINTAINED_CORRECT"
        else:
            outcome = "MAINTAINED_INCORRECT"

        case_info = {
            "case_id": k,
            "rel_path": r["rel_path"],
            "true_class": true_name,
            "outcome": outcome,
            "coverage": m["coverage"],
            "threshold": m["threshold"],
            "is_fallback": m["is_fallback"],
            "orig_pred": f"{pred_a_name} ({conf_a:.3f})",
            "seg_pred": f"{pred_b_name} ({conf_b:.3f})",
        }
        audit_cases.append(case_info)
        print(f"Case {k:2d}: {r['rel_path']}")
        print(f"  True: {true_name} | Outcome: {outcome}")
        print(f"  Pipeline A: {pred_a_name} ({conf_a:.3f}) -> Pipeline B: {pred_b_name} ({conf_b:.3f})")
        print(f"  Leaf Coverage: {m['coverage']*100:.1f}%, Otsu Thresh: {m['threshold']}, Fallback: {m['is_fallback']}")
        print()

    # 7. Save Comprehensive Artifacts
    experiment_results = {
        "experiment_name": "Controlled Leaf Segmentation Experiment on PlantDoc Development Subset",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset": {
            "source": "PlantDoc (Singh et al. 2020) Train Subset",
            "total_unambiguous_samples": len(dev_rows),
            "excluded_duplicate_samples": len(excluded_dups),
            "excluded_duplicate_ids": [int(r["image_id"]) for r in excluded_dups],
            "sample_ids": dev_image_ids,
        },
        "pipeline_a_baseline": {
            "name": "Original Image (Unsegmented)",
            "accuracy": round(acc_a, 4),
            "macro_f1": round(macro_f1_a, 4),
            "weighted_f1": round(weighted_f1_a, 4),
            "false_corn_healthy_count": false_corn_healthy_a,
            "false_corn_healthy_rate": round(false_corn_healthy_a / len(dev_rows), 4),
            "total_corn_healthy_predictions": int(np.sum(preds_a == corn_healthy_idx)),
            "confusion_matrix": cm_a.tolist(),
        },
        "pipeline_b_segmented": {
            "name": "ExG + Otsu Segmented + Grey Infill",
            "accuracy": round(acc_b, 4),
            "macro_f1": round(macro_f1_b, 4),
            "weighted_f1": round(weighted_f1_b, 4),
            "false_corn_healthy_count": false_corn_healthy_b,
            "false_corn_healthy_rate": round(false_corn_healthy_b / len(dev_rows), 4),
            "total_corn_healthy_predictions": int(np.sum(preds_b == corn_healthy_idx)),
            "fallback_count": fallback_count,
            "fallback_rate": round(fallback_rate, 4),
            "mean_leaf_coverage": round(float(np.mean(coverages)), 4),
            "confusion_matrix": cm_b.tolist(),
        },
        "delta": {
            "accuracy_delta": round(acc_b - acc_a, 4),
            "macro_f1_delta": round(macro_f1_b - macro_f1_a, 4),
            "weighted_f1_delta": round(weighted_f1_b - weighted_f1_a, 4),
            "corn_healthy_reduction": int(np.sum(preds_a == corn_healthy_idx) - np.sum(preds_b == corn_healthy_idx)),
        },
        "per_class_comparison": per_class_comparison,
        "visual_audit_cases": audit_cases,
    }

    def json_default(obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        raise TypeError(f"Type {type(obj)} not serializable")

    out_json = ARTIFACTS_DIR / "segmentation_experiment_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(experiment_results, f, indent=2, default=json_default)
    print(f"\nSaved structured experiment results to: {out_json}")

    print("\n" + "=" * 80)
    print("CONTROLLED EXPERIMENT COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    run_experiment()
