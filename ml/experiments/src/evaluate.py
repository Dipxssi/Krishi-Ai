"""Standardized evaluation engine for MobileNetV3-Small experiments on PlantDoc and PlantVillage."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import classification_report, confusion_matrix, f1_score, precision_score, recall_score
from torch.utils.data import DataLoader
from torchvision import models

# Ensure repo root is on path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.src.config import IDX_TO_CLASS, TARGET_CLASSES
from ml.experiments.src.dataset import FoliarDiseaseDataset, get_eval_transforms


def get_device(requested: str = "auto") -> torch.device:
    if requested == "auto":
        if torch.backends.mps.is_available():
            return torch.device("mps")
        elif torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    return torch.device(requested)


def create_mobilenetv3_small(num_classes: int = 17, pretrained: bool = False) -> torch.nn.Module:
    weights = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
    model = models.mobilenet_v3_small(weights=weights)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = torch.nn.Linear(in_features, num_classes)
    return model


def load_checkpoint(
    checkpoint_path: str | Path,
    device: torch.device,
) -> tuple[torch.nn.Module, dict[str, Any]]:
    p = Path(checkpoint_path)
    if not p.exists():
        raise FileNotFoundError(f"Checkpoint not found: {p}")

    ckpt = torch.load(p, map_location=device, weights_only=False)
    num_classes = ckpt.get("num_classes", len(TARGET_CLASSES))
    model = create_mobilenetv3_small(num_classes=num_classes, pretrained=False)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    model.eval()
    return model, ckpt


def plot_confusion_matrix(
    cm: np.ndarray,
    class_names: list[str],
    output_path: Path,
    title: str = "Confusion Matrix",
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(14, 12))
    plt.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.title(title, fontsize=14, pad=16)
    plt.colorbar()

    tick_marks = np.arange(len(class_names))
    plt.xticks(tick_marks, class_names, rotation=45, ha="right", fontsize=9)
    plt.yticks(tick_marks, class_names, fontsize=9)

    thresh = cm.max() / 2.0 if cm.max() > 0 else 1.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            val = cm[i, j]
            if val > 0:
                plt.text(
                    j, i, format(val, "d"),
                    ha="center", va="center",
                    color="white" if val > thresh else "black",
                    fontsize=8,
                )

    plt.ylabel("True Label", fontsize=12)
    plt.xlabel("Predicted Label", fontsize=12)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def evaluate_dataset(
    model: torch.nn.Module,
    dataloader: DataLoader,
    device: torch.device,
    dataset_name: str = "Dataset",
    confidence_threshold: float = 0.60,
) -> dict[str, Any]:
    model.eval()
    all_preds: list[int] = []
    all_targets: list[int] = []
    all_confs: list[float] = []

    t0 = time.perf_counter()
    with torch.no_grad():
        for images, targets in dataloader:
            images = images.to(device)
            outputs = model(images)
            probs = F.softmax(outputs, dim=1)
            confs, preds = torch.max(probs, dim=1)

            all_preds.extend(preds.cpu().numpy().tolist())
            all_targets.extend(targets.numpy().tolist())
            all_confs.extend(confs.cpu().numpy().tolist())

    total_time = time.perf_counter() - t0
    n_samples = len(all_targets)
    latency_ms = (total_time / max(n_samples, 1)) * 1000.0

    y_true = np.array(all_targets)
    y_pred = np.array(all_preds)
    confs = np.array(all_confs)

    n_correct = int(np.sum(y_true == y_pred))
    n_incorrect = n_samples - n_correct
    acc = float(n_correct / max(n_samples, 1))

    # Calculate metrics
    macro_p = float(precision_score(y_true, y_pred, average="macro", zero_division=0))
    macro_r = float(recall_score(y_true, y_pred, average="macro", zero_division=0))
    macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))

    weighted_p = float(precision_score(y_true, y_pred, average="weighted", zero_division=0))
    weighted_r = float(recall_score(y_true, y_pred, average="weighted", zero_division=0))
    weighted_f1 = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

    # Confidence gating
    accepted_mask = confs >= confidence_threshold
    rejection_rate = float(np.mean(~accepted_mask))
    accepted_acc = float(np.mean(y_true[accepted_mask] == y_pred[accepted_mask])) if accepted_mask.sum() > 0 else 0.0

    # 17x17 Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(TARGET_CLASSES))))

    # Detailed per-class report
    target_names = [c["display_name"] for c in TARGET_CLASSES]
    rep = classification_report(
        y_true,
        y_pred,
        labels=list(range(len(TARGET_CLASSES))),
        target_names=target_names,
        output_dict=True,
        zero_division=0,
    )

    per_class_summary = {}
    for idx, c in enumerate(TARGET_CLASSES):
        name = c["display_name"]
        item = rep.get(name, {})
        per_class_summary[name] = {
            "class_idx": idx,
            "crop": c["crop"],
            "disease": c["disease"],
            "precision": round(float(item.get("precision", 0.0)), 4),
            "recall": round(float(item.get("recall", 0.0)), 4),
            "f1_score": round(float(item.get("f1-score", 0.0)), 4),
            "support": int(item.get("support", 0)),
        }

    return {
        "dataset_name": dataset_name,
        "sample_count": n_samples,
        "correct_count": n_correct,
        "incorrect_count": n_incorrect,
        "accuracy": round(acc, 4),
        "macro_precision": round(macro_p, 4),
        "macro_recall": round(macro_r, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_precision": round(weighted_p, 4),
        "weighted_recall": round(weighted_r, 4),
        "weighted_f1": round(weighted_f1, 4),
        "latency_ms_per_image": round(latency_ms, 2),
        "confidence_threshold": confidence_threshold,
        "rejection_rate": round(rejection_rate, 4),
        "accepted_accuracy": round(accepted_acc, 4),
        "mean_confidence": round(float(np.mean(confs)), 4),
        "median_confidence": round(float(np.median(confs)), 4),
        "per_class_summary": per_class_summary,
        "confusion_matrix": cm.tolist(),
    }


def evaluate_ood_dataset(
    model: torch.nn.Module,
    dataloader: DataLoader,
    device: torch.device,
    confidence_threshold: float = 0.60,
) -> dict[str, Any]:
    model.eval()
    all_confs: list[float] = []
    all_preds: list[int] = []

    with torch.no_grad():
        for images, targets in dataloader:
            images = images.to(device)
            outputs = model(images)
            probs = F.softmax(outputs, dim=1)
            confs, preds = torch.max(probs, dim=1)
            all_confs.extend(confs.cpu().numpy().tolist())
            all_preds.extend(preds.cpu().numpy().tolist())

    confs_arr = np.array(all_confs)
    n_samples = len(confs_arr)
    rejected_count = int(np.sum(confs_arr < confidence_threshold))
    false_accepted_count = n_samples - rejected_count
    rejection_rate = float(rejected_count / max(n_samples, 1))
    false_acceptance_rate = float(false_accepted_count / max(n_samples, 1))

    return {
        "ood_sample_count": n_samples,
        "rejected_count": rejected_count,
        "false_accepted_count": false_accepted_count,
        "ood_rejection_rate": round(rejection_rate, 4),
        "ood_false_acceptance_rate": round(false_acceptance_rate, 4),
        "median_ood_confidence": round(float(np.median(confs_arr)), 4),
        "mean_ood_confidence": round(float(np.mean(confs_arr)), 4),
    }


def run_full_evaluation(
    model: torch.nn.Module,
    ckpt_path: Path,
    device: torch.device,
    output_dir: Path,
    experiment_name: str = "Experiment",
    batch_size: int = 32,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    eval_transform = get_eval_transforms(224)

    # 1. Official Untouched PlantDoc Test Benchmark
    pd_test_csv = REPO_ROOT / "ml" / "experiments" / "dataset" / "manifests" / "plantdoc_test.csv"
    pd_test_ds = FoliarDiseaseDataset(pd_test_csv, transform=eval_transform)
    pd_test_loader = DataLoader(pd_test_ds, batch_size=batch_size, shuffle=False, num_workers=2)

    print(f"\n--- Evaluating {experiment_name} on Official Untouched PlantDoc Test Set (N={len(pd_test_ds)}) ---")
    pd_metrics = evaluate_dataset(model, pd_test_loader, device, dataset_name="PlantDoc Test Benchmark (In-Scope)")
    print(f"  PlantDoc Test Acc: {pd_metrics['accuracy']:.2%} | Macro-F1: {pd_metrics['macro_f1']:.4f} | Correct: {pd_metrics['correct_count']}/{pd_metrics['sample_count']}")

    # Plot PlantDoc Test Confusion Matrix
    cm_pd = np.array(pd_metrics["confusion_matrix"])
    plot_confusion_matrix(
        cm_pd,
        [c["display_name"] for c in TARGET_CLASSES],
        output_dir / "plantdoc_test_confusion_matrix.png",
        title=f"{experiment_name} - PlantDoc Test Confusion Matrix",
    )

    # 2. PlantDoc OOD Test Set
    pd_ood_csv = REPO_ROOT / "ml" / "experiments" / "dataset" / "manifests" / "plantdoc_test_ood.csv"
    pd_ood_ds = FoliarDiseaseDataset(pd_ood_csv, transform=eval_transform)
    # Target index is dummy for OOD
    for s in pd_ood_ds.samples:
        s["class_idx"] = 0
    pd_ood_loader = DataLoader(pd_ood_ds, batch_size=batch_size, shuffle=False, num_workers=2)

    print(f"\n--- Evaluating {experiment_name} on PlantDoc OOD Test Set (N={len(pd_ood_ds)}) ---")
    ood_metrics = evaluate_ood_dataset(model, pd_ood_loader, device)
    print(f"  OOD Rejection Rate: {ood_metrics['ood_rejection_rate']:.2%} | False Acceptance Rate: {ood_metrics['ood_false_acceptance_rate']:.2%}")

    # 3. PlantVillage Held-Out Test Set
    pv_test_csv = REPO_ROOT / "ml" / "splits" / "test.csv"
    # Convert PlantVillage format
    pv_samples_conv = []
    with open(pv_test_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pv_samples_conv.append({
                "source": "plantvillage",
                "full_path": REPO_ROOT / row["full_path"],
                "class_idx": int(row["class_idx"]),
                "crop": row["crop"],
                "disease": row["disease"],
                "display_name": row["display_name"],
                "is_healthy": (row["disease"] == "healthy"),
                "md5": row["md5_hash"],
            })
    pv_test_ds = FoliarDiseaseDataset.__new__(FoliarDiseaseDataset)
    pv_test_ds.csv_path = pv_test_csv
    pv_test_ds.transform = eval_transform
    pv_test_ds.return_meta = False
    pv_test_ds.samples = pv_samples_conv
    pv_test_loader = DataLoader(pv_test_ds, batch_size=batch_size, shuffle=False, num_workers=2)

    print(f"\n--- Evaluating {experiment_name} on PlantVillage Test Set (N={len(pv_test_ds)}) ---")
    pv_metrics = evaluate_dataset(model, pv_test_loader, device, dataset_name="PlantVillage Test Set")
    print(f"  PlantVillage Test Acc: {pv_metrics['accuracy']:.2%} | Macro-F1: {pv_metrics['macro_f1']:.4f}")

    # Plot PlantVillage Test Confusion Matrix
    cm_pv = np.array(pv_metrics["confusion_matrix"])
    plot_confusion_matrix(
        cm_pv,
        [c["display_name"] for c in TARGET_CLASSES],
        output_dir / "plantvillage_test_confusion_matrix.png",
        title=f"{experiment_name} - PlantVillage Test Confusion Matrix",
    )

    # Compute parameters and file size
    param_count = sum(p.numel() for p in model.parameters())
    file_size_mb = ckpt_path.stat().st_size / (1024 * 1024) if ckpt_path.exists() else 0.0

    results = {
        "experiment_name": experiment_name,
        "checkpoint_path": str(ckpt_path),
        "parameter_count": param_count,
        "model_size_mb": round(file_size_mb, 2),
        "device": str(device),
        "evaluation_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "plantdoc_test_metrics": pd_metrics,
        "plantdoc_ood_metrics": ood_metrics,
        "plantvillage_test_metrics": pv_metrics,
        "domain_gap_delta_accuracy": round(pv_metrics["accuracy"] - pd_metrics["accuracy"], 4),
        "domain_gap_delta_macro_f1": round(pv_metrics["macro_f1"] - pd_metrics["macro_f1"], 4),
    }

    # Save JSON report
    json_path = output_dir / "evaluation_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Generate Markdown Summary
    md_content = f"""# {experiment_name} Evaluation Benchmark Report

**Evaluation Timestamp**: {results['evaluation_timestamp']}  
**Checkpoint**: `{ckpt_path.name}` ({results['model_size_mb']} MB, {results['parameter_count']:,} parameters)  
**Evaluation Device**: Apple Silicon MPS (`{device}`)  

---

## 1. Executive Summary & Field Generalization

| Evaluation Split | Sample Count ($N$) | Accuracy | Macro-Precision | Macro-Recall | Macro-F1 | Weighted-F1 | Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **PlantDoc Test Benchmark** | **{pd_metrics['sample_count']}** | **{pd_metrics['accuracy']:.2%}** | {pd_metrics['macro_precision']:.4f} | {pd_metrics['macro_recall']:.4f} | **{pd_metrics['macro_f1']:.4f}** | {pd_metrics['weighted_f1']:.4f} | {pd_metrics['latency_ms_per_image']} ms |
| **PlantVillage Test** | **{pv_metrics['sample_count']}** | **{pv_metrics['accuracy']:.2%}** | {pv_metrics['macro_precision']:.4f} | {pv_metrics['macro_recall']:.4f} | **{pv_metrics['macro_f1']:.4f}** | {pv_metrics['weighted_f1']:.4f} | {pv_metrics['latency_ms_per_image']} ms |
| **PlantDoc OOD Test** | **{ood_metrics['ood_sample_count']}** | *Rejection: {ood_metrics['ood_rejection_rate']:.2%}* | - | - | *False Acceptance: {ood_metrics['ood_false_acceptance_rate']:.2%}* | - | - |

* **Laboratory-to-Field Domain Gap**:
  * Accuracy Delta: **{results['domain_gap_delta_accuracy'] * 100:.2f}%** (PlantVillage: {pv_metrics['accuracy']:.2%} vs PlantDoc: {pd_metrics['accuracy']:.2%})
  * Macro-F1 Delta: **{results['domain_gap_delta_macro_f1']:.4f}** (PlantVillage: {pv_metrics['macro_f1']:.4f} vs PlantDoc: {pd_metrics['macro_f1']:.4f})

---

## 2. PlantDoc Test Per-Class Performance Breakdown

| Class Index | Target Class Name | Support | Correct | Precision | Recall | F1-Score |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
"""
    for idx, c in enumerate(TARGET_CLASSES):
        name = c["display_name"]
        item = pd_metrics["per_class_summary"][name]
        support = item["support"]
        # Find diagonal of confusion matrix for correct count
        correct = cm_pd[idx, idx] if idx < cm_pd.shape[0] else 0
        md_content += f"| `{idx:02d}` | {name} | {support} | {correct} | {item['precision']:.4f} | {item['recall']:.4f} | {item['f1_score']:.4f} |\n"

    md_content += f"""
---

## 3. Operational Safety & Confidence Gating ($\tau={pd_metrics['confidence_threshold']}$)

* **PlantDoc In-Scope Accepted Accuracy**: **{pd_metrics['accepted_accuracy']:.2%}** (Rejection rate: {pd_metrics['rejection_rate']:.2%})
* **PlantVillage Accepted Accuracy**: **{pv_metrics['accepted_accuracy']:.2%}** (Rejection rate: {pv_metrics['rejection_rate']:.2%})
* **OOD False Acceptance Rate on Non-Target Crops**: **{ood_metrics['ood_false_acceptance_rate']:.2%}** (Median confidence: {ood_metrics['median_ood_confidence']:.4f})
"""

    md_path = output_dir / "evaluation_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"  Saved evaluation report to: {md_path}")
    print(f"  Saved JSON metrics to: {json_path}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate MobileNetV3 model on PlantDoc and PlantVillage.")
    parser.add_argument("--checkpoint", type=str, required=True, help="Path to model checkpoint .pth")
    parser.add_argument("--name", type=str, default="Model", help="Experiment / model name")
    parser.add_argument("--output-dir", type=str, required=True, help="Output directory for reports and plots")
    parser.add_argument("--device", type=str, default="auto", help="Compute device (auto, mps, cpu, cuda)")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")

    args = parser.parse_args()
    device = get_device(args.device)
    ckpt_path = Path(args.checkpoint)
    model, _ = load_checkpoint(ckpt_path, device)
    run_full_evaluation(
        model=model,
        ckpt_path=ckpt_path,
        device=device,
        output_dir=Path(args.output_dir),
        experiment_name=args.name,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
