"""Field-Data Evaluation Pipeline for KrishiAI Plant Disease Diagnosis.

Evaluates trained classification candidates on expert-labeled field leaf images.
Supports:
1. Strict specimen-level identifier grouping to prevent data leakage between splits.
2. 17 target classes plus 'unsupported_plant' and 'unusable_image' out-of-scope categories.
   (Unsupported plants and unusable images are evaluated strictly as rejection/OOD targets,
   never as standard classes of the 17-class disease classifier).
3. Macro-F1, weighted-F1, per-class precision/recall/F1, and open-set confusion matrix.
4. Operational safety metrics: rejection rate, accepted-prediction error rate, expert-review rate.
5. Paired comparison of guided vs. ordinary captures on identical physical specimens.
6. Strict separation of exploratory calibration data from the locked final evaluation set.

NOTE: Real-world field accuracy requires physical, expert-labeled field specimens.
Synthetic or lab images must never be substituted for reported field performance.
Dry runs validate schema, partition integrity, and specimen isolation only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import classification_report, f1_score

# Ensure ml package is on path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.src.config import IDX_TO_CLASS, TARGET_CLASSES
from ml.src.features import extract_features_from_image
from ml.src.model import PlantDiseaseElasticNetClassifier

# Non-target / out-of-distribution classes (Rejection Targets)
OOD_CLASSES = {
    17: {"folder_name": "unsupported_plant", "crop": "unsupported", "disease": "unsupported", "display_name": "Unsupported Plant / Weed", "is_healthy": False},
    18: {"folder_name": "unusable_image", "crop": "none", "disease": "unusable", "display_name": "Unusable / Degraded Image", "is_healthy": False},
}

ALL_CLASS_METADATA = {**IDX_TO_CLASS, **OOD_CLASSES}
ALL_CLASS_NAMES = [ALL_CLASS_METADATA[i]["display_name"] for i in sorted(ALL_CLASS_METADATA.keys())]
SUPPORTED_CLASS_INDICES = list(range(17))


def generate_manifest_template(output_path: Path) -> None:
    """Generate a template CSV manifest demonstrating the required field evaluation schema."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "image_path",
        "specimen_id",
        "plant_id",
        "condition",  # 'guided' | 'ordinary'
        "true_label",  # target class name/idx or 'unsupported_plant' or 'unusable_image'
        "split",  # 'calibration' | 'locked_test'
        "expert_evaluator_id",
        "crop",
        "location",
        "camera_model",
        "notes",
    ]
    samples = [
        {
            "image_path": "ml/field_data/images/MH_NAS_TOM_001_guided.jpg",
            "specimen_id": "MH_NAS_TOM_001",
            "plant_id": "TOM_PLOT_A_12",
            "condition": "guided",
            "true_label": "Tomato Early Blight",
            "split": "locked_test",
            "expert_evaluator_id": "KVK_AGR_402",
            "crop": "tomato",
            "location": "Nashik, Maharashtra",
            "camera_model": "Redmi Note 11",
            "notes": "Single leaf against white cardboard, diffuse morning light",
        },
        {
            "image_path": "ml/field_data/images/MH_NAS_TOM_001_ordinary.jpg",
            "specimen_id": "MH_NAS_TOM_001",
            "plant_id": "TOM_PLOT_A_12",
            "condition": "ordinary",
            "true_label": "Tomato Early Blight",
            "split": "locked_test",
            "expert_evaluator_id": "KVK_AGR_402",
            "crop": "tomato",
            "location": "Nashik, Maharashtra",
            "camera_model": "Redmi Note 11",
            "notes": "In-situ field background with soil and partial weed clutter",
        },
        {
            "image_path": "ml/field_data/images/MH_NAS_WEED_002_ordinary.jpg",
            "specimen_id": "MH_NAS_WEED_002",
            "plant_id": "WEED_BORDER_03",
            "condition": "ordinary",
            "true_label": "unsupported_plant",
            "split": "locked_test",
            "expert_evaluator_id": "KVK_AGR_402",
            "crop": "parthenium",
            "location": "Nashik, Maharashtra",
            "camera_model": "Redmi Note 11",
            "notes": "Parthenium weed in field furrow (out-of-distribution control)",
        },
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(samples)
    print(f"Generated manifest template at {output_path}")


def resolve_true_label(label_str: str) -> int:
    """Resolve ground-truth string or index to an integer index (0..16 or 17=unsupported, 18=unusable)."""
    norm = label_str.strip().lower().replace("_", " ")
    if norm in ("17", "unsupported", "unsupported plant", "unsupported plant / weed", "weed"):
        return 17
    if norm in ("18", "unusable", "unusable image", "unusable / degraded image", "corrupted"):
        return 18

    # Match target class names or display names
    for idx, meta in IDX_TO_CLASS.items():
        if norm in (str(idx), meta["display_name"].lower(), meta["folder_name"].lower(), f"{meta['crop']} {meta['disease']}".lower()):
            return idx
    raise ValueError(f"Unknown ground-truth label in manifest: '{label_str}'. Must be supported target class or OOD category.")


def audit_specimen_leakage(rows: list[dict[str, str]]) -> None:
    """Verify strict specimen grouping: identical physical specimens must never cross split boundaries."""
    specimen_to_splits: dict[str, set[str]] = {}
    for r in rows:
        spec = r.get("specimen_id", "").strip()
        split = r.get("split", "").strip().lower()
        if not spec or not split:
            continue
        specimen_to_splits.setdefault(spec, set()).add(split)

    leaking = {s: splits for s, splits in specimen_to_splits.items() if len(splits) > 1}
    if leaking:
        sample_leak = list(leaking.items())[:3]
        raise ValueError(
            f"DATA LEAKAGE DETECTED: {len(leaking)} specimen(s) cross multiple splits: {sample_leak}. "
            "All photos of the same physical leaf specimen must belong strictly to either 'calibration' or 'locked_test'."
        )


def validate_manifest_records(rows: list[dict[str, str]], target_split: str = "locked_test") -> list[dict[str, str]]:
    """
    Rigorously validate manifest records before any evaluation occurs.
    Fails clearly on missing labels, unknown class names, duplicate records,
    missing specimen IDs, invalid split names, empty evaluation partitions, or cross-split leakage.
    """
    if not rows:
        raise ValueError("Manifest is empty: 0 records found.")

    required_fields = ["image_path", "specimen_id", "condition", "true_label", "split"]
    seen_image_paths: dict[str, int] = {}
    seen_specimen_conditions: dict[tuple[str, str], int] = {}
    specimen_to_splits: dict[str, set[str]] = {}

    valid_splits = {"calibration", "locked_test"}
    valid_conditions = {"guided", "ordinary"}

    for line_idx, r in enumerate(rows, start=2):  # line 1 is header
        # 1. Missing required fields
        for field in required_fields:
            val = r.get(field, "").strip()
            if not val:
                raise ValueError(
                    f"Manifest Validation Error at line {line_idx}: Missing required field '{field}'. "
                    "Refusing to silently omit invalid records."
                )

        img_path = r["image_path"].strip()
        spec_id = r["specimen_id"].strip()
        cond = r["condition"].strip().lower()
        split = r["split"].strip().lower()
        label = r["true_label"].strip()

        # 2. Invalid condition
        if cond not in valid_conditions:
            raise ValueError(
                f"Manifest Validation Error at line {line_idx}: Invalid condition '{r['condition']}'. "
                f"Condition must be 'guided' or 'ordinary'."
            )

        # 3. Invalid split name
        if split not in valid_splits:
            raise ValueError(
                f"Manifest Validation Error at line {line_idx}: Invalid split name '{r['split']}'. "
                f"Allowed splits are 'calibration' and 'locked_test'."
            )

        # 4. Unknown class label
        try:
            resolve_true_label(label)
        except ValueError as exc:
            raise ValueError(f"Manifest Validation Error at line {line_idx}: {exc}") from exc

        # 5. Duplicate image path
        if img_path in seen_image_paths:
            prev_line = seen_image_paths[img_path]
            raise ValueError(
                f"Manifest Validation Error at line {line_idx}: Duplicate image_path '{img_path}'. "
                f"Already defined at line {prev_line}."
            )
        seen_image_paths[img_path] = line_idx

        # 6. Duplicate specimen condition
        pair_key = (spec_id, cond)
        if pair_key in seen_specimen_conditions:
            prev_line = seen_specimen_conditions[pair_key]
            raise ValueError(
                f"Manifest Validation Error at line {line_idx}: Duplicate specimen condition: "
                f"specimen '{spec_id}' already has a '{cond}' record at line {prev_line}. "
                "Disambiguate duplicate specimen photographs."
            )
        seen_specimen_conditions[pair_key] = line_idx

        # 7. Track specimen to split
        specimen_to_splits.setdefault(spec_id, set()).add(split)

    # 8. Cross-split specimen leakage check
    audit_specimen_leakage(rows)

    # 9. Empty evaluation partition check
    if target_split != "all":
        selected_rows = [r for r in rows if r["split"].strip().lower() == target_split.lower()]
        if not selected_rows:
            raise ValueError(
                f"Empty evaluation partition: Split '{target_split}' contains 0 records in manifest. "
                f"Available splits: {set(r['split'].strip().lower() for r in rows)}"
            )
        return selected_rows

    return rows


def compute_evaluation_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Pure, deterministic metric computation engine.
    Separates supported target classification metrics from out-of-distribution (OOD) rejection metrics.
    """
    if not records:
        raise ValueError("Cannot compute metrics on empty record list.")

    y_true: list[int] = []
    y_pred: list[int] = []
    accepted_mask: list[bool] = []
    expert_mask: list[bool] = []

    for r in records:
        y_true.append(r["true_idx"])
        y_pred.append(r["pred_idx"])
        accepted_mask.append(r["status"] == "ok")
        expert_mask.append(bool(r.get("requires_expert", False)))

    y_true_arr = np.array(y_true)
    y_pred_arr = np.array(y_pred)
    accepted_arr = np.array(accepted_mask)
    expert_arr = np.array(expert_mask)

    total_samples = len(y_true_arr)
    rejection_rate = float(np.mean(~accepted_arr))
    expert_review_rate = float(np.mean(expert_arr))

    # Supported in-scope classes (0..16)
    supported_mask = y_true_arr < 17
    supported_true = y_true_arr[supported_mask]
    supported_pred = y_pred_arr[supported_mask]
    supported_accepted = accepted_arr[supported_mask]

    if len(supported_true) > 0:
        overall_acc = float(np.mean(supported_true == supported_pred))
        macro_f1 = float(f1_score(supported_true, supported_pred, average="macro", zero_division=0))
        weighted_f1 = float(f1_score(supported_true, supported_pred, average="weighted", zero_division=0))
        per_class_rep = classification_report(supported_true, supported_pred, output_dict=True, zero_division=0)
    else:
        overall_acc = macro_f1 = weighted_f1 = 0.0
        per_class_rep = {}

    # Accepted-prediction accuracy and error rate (across accepted samples)
    accepted_count = int(np.sum(accepted_arr))
    if accepted_count > 0:
        # For accepted samples, was prediction correct and was it an in-scope sample?
        # Note: If an OOD sample was accepted, it is ALWAYS an error!
        accepted_correct = np.sum((y_true_arr[accepted_arr] == y_pred_arr[accepted_arr]) & (y_true_arr[accepted_arr] < 17))
        accepted_acc = float(accepted_correct / accepted_count)
        accepted_error_rate = float(1.0 - accepted_acc)
    else:
        accepted_acc = 0.0
        accepted_error_rate = 0.0

    # OOD / Rejection Target Evaluation (classes 17 and 18)
    # The ONLY safe/correct outcome for an OOD sample is REJECTION / ABSTENTION
    unsupported_mask = y_true_arr == 17
    unsupported_count = int(np.sum(unsupported_mask))
    unsupported_rejected = int(np.sum(unsupported_mask & (~accepted_arr)))
    unsupported_rejection_rate = float(unsupported_rejected / unsupported_count) if unsupported_count > 0 else 1.0

    unusable_mask = y_true_arr == 18
    unusable_count = int(np.sum(unusable_mask))
    unusable_rejected = int(np.sum(unusable_mask & (~accepted_arr)))
    unusable_rejection_rate = float(unusable_rejected / unusable_count) if unusable_count > 0 else 1.0

    total_ood_count = unsupported_count + unusable_count
    total_ood_rejected = unsupported_rejected + unusable_rejected
    total_ood_rejection_rate = float(total_ood_rejected / total_ood_count) if total_ood_count > 0 else 1.0
    ood_false_acceptance_rate = float(1.0 - total_ood_rejection_rate)

    # Open-Set Confusion Matrix
    # Rows: True classes 0..16 (supported), 17 (unsupported plant), 18 (unusable image) -> 19 rows
    # Cols: Predicted classes 0..16 (when accepted), Col 17 (abstained / rejected) -> 18 columns
    cm_open_set = np.zeros((19, 18), dtype=int)
    for t_idx, p_idx, is_acc in zip(y_true, y_pred, accepted_mask, strict=False):
        if not is_acc:
            cm_open_set[t_idx, 17] += 1
        else:
            if 0 <= p_idx < 17:
                cm_open_set[t_idx, p_idx] += 1

    # Paired Comparison of Guided vs. Ordinary on Same Physical Specimens
    paired_specimens: dict[str, dict[str, dict[str, Any]]] = {}
    for res in records:
        spec_id = res.get("specimen_id")
        cond = (res.get("condition") or "").lower()
        if spec_id and cond in ("guided", "ordinary"):
            paired_specimens.setdefault(spec_id, {})[cond] = res

    complete_pairs = {k: v for k, v in paired_specimens.items() if "guided" in v and "ordinary" in v}
    paired_summary: dict[str, Any] = {"num_paired_specimens": len(complete_pairs)}

    if complete_pairs:
        both_correct = 0
        guided_only = 0
        ordinary_only = 0
        neither_correct = 0

        guided_accepted = 0
        ordinary_accepted = 0

        for spec_id, pair in complete_pairs.items():
            g = pair["guided"]
            o = pair["ordinary"]

            # For supported: correct means status == ok and pred == true
            # For OOD: correct means rejected (status != ok or requires_expert)
            if g["true_idx"] < 17:
                g_corr = (g["true_idx"] == g["pred_idx"]) and (g["status"] == "ok")
            else:
                g_corr = (g["status"] != "ok") or g.get("requires_expert", False)

            if o["true_idx"] < 17:
                o_corr = (o["true_idx"] == o["pred_idx"]) and (o["status"] == "ok")
            else:
                o_corr = (o["status"] != "ok") or o.get("requires_expert", False)

            if g["status"] == "ok":
                guided_accepted += 1
            if o["status"] == "ok":
                ordinary_accepted += 1

            if g_corr and o_corr:
                both_correct += 1
            elif g_corr and not o_corr:
                guided_only += 1
            elif not g_corr and o_corr:
                ordinary_only += 1
            else:
                neither_correct += 1

        n_pairs = len(complete_pairs)
        paired_summary.update({
            "guided_accuracy": round((both_correct + guided_only) / n_pairs, 4),
            "ordinary_accuracy": round((both_correct + ordinary_only) / n_pairs, 4),
            "delta_accuracy_guided_vs_ordinary": round(((both_correct + guided_only) - (both_correct + ordinary_only)) / n_pairs, 4),
            "contingency_table": {
                "both_correct": both_correct,
                "guided_correct_ordinary_incorrect": guided_only,
                "ordinary_correct_guided_incorrect": ordinary_only,
                "neither_correct": neither_correct,
            },
            "guided_acceptance_rate": round(guided_accepted / n_pairs, 4),
            "ordinary_acceptance_rate": round(ordinary_accepted / n_pairs, 4),
        })

    return {
        "total_samples": total_samples,
        "rejection_rate": round(rejection_rate, 4),
        "expert_review_rate": round(expert_review_rate, 4),
        "accepted_samples": accepted_count,
        "accepted_prediction_accuracy": round(accepted_acc, 4),
        "accepted_prediction_error_rate": round(accepted_error_rate, 4),
        "ood_evaluation": {
            "unsupported_plant_samples": unsupported_count,
            "unsupported_plant_rejections": unsupported_rejected,
            "unsupported_plant_rejection_rate": round(unsupported_rejection_rate, 4),
            "unusable_image_samples": unusable_count,
            "unusable_image_rejections": unusable_rejected,
            "unusable_image_rejection_rate": round(unusable_rejection_rate, 4),
            "total_ood_samples": total_ood_count,
            "total_ood_rejections": total_ood_rejected,
            "total_ood_rejection_rate": round(total_ood_rejection_rate, 4),
            "ood_false_acceptance_rate": round(ood_false_acceptance_rate, 4),
        },
        "supported_classes_accuracy": round(overall_acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class_metrics": per_class_rep,
        "confusion_matrix_open_set": cm_open_set.tolist(),
        "paired_guided_vs_ordinary": paired_summary,
    }


def evaluate_field_manifest(
    manifest_path: Path,
    model_bundle_path: Path,
    target_split: str = "locked_test",
    output_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute evaluation on field dataset manifest with comprehensive validation and safety metrics."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found at {manifest_path}")

    rows: list[dict[str, str]] = []
    with open(manifest_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Rigorous validation of records before any processing occurs
    selected_rows = validate_manifest_records(rows, target_split=target_split)

    if dry_run:
        print("\n[DRY RUN SUCCESSFUL] Manifest schema, required fields, split names, and specimen grouping verified.")
        print(f"Validated {len(rows)} records ({len(selected_rows)} in '{target_split}') with 0 cross-split leakage.")
        print("NOTE: This dry run is strictly a schema/leakage verification check and provides NO proof of real-world model accuracy.\n")
        return {
            "status": "dry_run_success",
            "samples_checked": len(selected_rows),
            "split": target_split,
            "disclaimer": "Schema and leakage validation only; does not execute inference or prove real-world accuracy."
        }

    # Load offline model candidate
    if not model_bundle_path.exists():
        raise FileNotFoundError(f"Model candidate not found at {model_bundle_path}")

    clf = PlantDiseaseElasticNetClassifier.load(model_bundle_path)

    # Predict on field images
    records: list[dict[str, Any]] = []

    for r in selected_rows:
        img_p = Path(r["image_path"])
        if not img_p.is_absolute():
            img_p = REPO_ROOT / img_p

        true_idx = resolve_true_label(r["true_label"])

        # Extract features and predict
        feat = extract_features_from_image(img_p)
        pred_dict = clf.predict_single_with_safeguards(feat)

        pred_idx = -1
        pred_display = pred_dict.get("display_name")
        for idx, meta in IDX_TO_CLASS.items():
            if meta["display_name"] == pred_display:
                pred_idx = idx
                break

        records.append({
            "image_path": str(img_p),
            "specimen_id": r.get("specimen_id"),
            "condition": r.get("condition"),
            "true_idx": true_idx,
            "pred_idx": pred_idx,
            "confidence": pred_dict.get("crop_confidence", 0.0),
            "status": pred_dict["status"],
            "requires_expert": pred_dict.get("requires_expert", False),
            "rejection_reason": pred_dict.get("rejection_reason"),
        })

    eval_report = compute_evaluation_metrics(records)
    eval_report["manifest_path"] = str(manifest_path)
    eval_report["target_split"] = target_split

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_json = output_dir / f"field_eval_{target_split}.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(eval_report, f, indent=2)
        print(f"Saved field evaluation results to {out_json}")

    return eval_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate KrishiAI models on field leaf images.")
    parser.add_argument("--manifest", type=Path, help="Path to field dataset CSV manifest.")
    parser.add_argument("--model-bundle", type=Path, default=REPO_ROOT / "ml" / "models" / "elasticnet_plantdisease_best.joblib", help="Path to trained model bundle.")
    parser.add_argument("--split", type=str, default="locked_test", choices=["locked_test", "calibration", "all"], help="Dataset split to evaluate.")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "ml" / "artifacts", help="Directory to save evaluation reports.")
    parser.add_argument("--generate-template", type=Path, help="Generate a CSV manifest template with schema and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Validate manifest schema and specimen grouping without inference.")

    args = parser.parse_args()

    if args.generate_template:
        generate_manifest_template(args.generate_template)
        return

    if not args.manifest:
        parser.error("--manifest is required unless --generate-template is specified.")

    res = evaluate_field_manifest(
        manifest_path=args.manifest,
        model_bundle_path=args.model_bundle,
        target_split=args.split,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        print("\n=== FIELD EVALUATION RESULTS SUMMARY ===")
        print(f"Split: {res['target_split']} (N = {res['total_samples']})")
        print(f"Supported Accuracy: {res['supported_classes_accuracy']:.2%} | Macro-F1: {res['macro_f1']:.4f}")
        print(f"Rejection Rate: {res['rejection_rate']:.2%} | Accepted Error Rate: {res['accepted_prediction_error_rate']:.2%}")
        ood = res["ood_evaluation"]
        print(f"OOD Rejection Rate: {ood['total_ood_rejection_rate']:.2%} (False Acceptance: {ood['ood_false_acceptance_rate']:.2%})")
        if res["paired_guided_vs_ordinary"].get("num_paired_specimens", 0) > 0:
            paired = res["paired_guided_vs_ordinary"]
            print(f"Paired Specimens (N = {paired['num_paired_specimens']}):")
            print(f"  Guided Accuracy:   {paired['guided_accuracy']:.2%}")
            print(f"  Ordinary Accuracy: {paired['ordinary_accuracy']:.2%}")
            print(f"  Delta (Guided - Ordinary): {paired['delta_accuracy_guided_vs_ordinary']:+.2%}")


if __name__ == "__main__":
    main()
