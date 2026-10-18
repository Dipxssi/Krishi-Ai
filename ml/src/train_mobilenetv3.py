"""Two-stage transfer learning pipeline for MobileNetV3 plant disease classifier."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, f1_score
from torch.utils.data import DataLoader
from torchvision import models

# Ensure ml package is on path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.src.config import IDX_TO_CLASS, MODELS_DIR, PROJECT_ROOT, SPLITS_DIR, TARGET_CLASSES
from ml.src.dataset import (
    IMAGENET_MEAN,
    IMAGENET_STD,
    PlantVillageDataset,
    get_eval_transforms,
    get_train_transforms,
)


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def get_device(requested: str = "auto") -> torch.device:
    if requested == "auto":
        if torch.backends.mps.is_available():
            return torch.device("mps")
        elif torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    return torch.device(requested)


def create_mobilenetv3(
    num_classes: int = 17,
    variant: str = "small",
    pretrained: bool = True,
) -> nn.Module:
    """Create MobileNetV3 model with custom classification head for 17 disease classes."""
    if variant == "small":
        weights = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        model = models.mobilenet_v3_small(weights=weights)
    elif variant == "large":
        weights = models.MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
        model = models.mobilenet_v3_large(weights=weights)
    else:
        raise ValueError(f"Unsupported MobileNetV3 variant: {variant}")

    # Replace the final linear layer of classifier
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    return model


def compute_class_weights(class_counts: dict[int, int], num_classes: int = 17) -> torch.Tensor:
    """Compute balanced class weights with clipping to stabilize gradient updates."""
    total = sum(class_counts.values())
    weights = np.zeros(num_classes, dtype=np.float32)
    for idx in range(num_classes):
        count = class_counts.get(idx, 1)
        weights[idx] = total / (num_classes * count)

    # Clip weights to prevent minor classes from exploding gradient norms
    weights = np.clip(weights, 0.2, 5.0)
    # Normalize so mean weight is 1.0
    weights = weights / weights.mean()
    return torch.tensor(weights, dtype=torch.float32)


def evaluate_dataset(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, float, float]:
    """Evaluate model on a dataloader; returns (avg_loss, accuracy, macro_f1)."""
    model.eval()
    total_loss = 0.0
    all_preds: list[int] = []
    all_targets: list[int] = []

    with torch.no_grad():
        for images, targets in dataloader:
            images = images.to(device)
            targets = targets.to(device)
            outputs = model(images)
            loss = criterion(outputs, targets)
            total_loss += loss.item() * images.size(0)

            preds = torch.argmax(outputs, dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_targets.extend(targets.cpu().numpy())

    total_samples = len(all_targets)
    avg_loss = total_loss / max(total_samples, 1)
    acc = float(accuracy_score(all_targets, all_preds))
    macro_f1 = float(f1_score(all_targets, all_preds, average="macro", zero_division=0))
    return avg_loss, acc, macro_f1


def train_mobilenetv3(
    variant: str = "small",
    epochs_phase1: int = 3,
    epochs_phase2: int = 7,
    batch_size: int = 64,
    lr_head: float = 5e-4,
    lr_backbone: float = 1e-4,
    img_size: int = 224,
    device_name: str = "auto",
    seed: int = 42,
    patience: int = 4,
    output_model_path: Path | None = None,
    output_report_path: Path | None = None,
) -> dict[str, Any]:
    start_time = time.time()
    set_seed(seed)
    device = get_device(device_name)
    print(f"=== TRAINING MOBILENETV3 ({variant.upper()}) ===")
    print(f"Compute device: {device} | Random seed: {seed}")
    print(f"Image resolution: {img_size}x{img_size} | Batch size: {batch_size}")
    print(f"Phase 1 (Warmup): {epochs_phase1} epochs | Phase 2 (Fine-tune): {epochs_phase2} epochs")

    # 1. Datasets and Loaders
    train_csv = SPLITS_DIR / "train.csv"
    val_csv = SPLITS_DIR / "val.csv"
    train_dataset = PlantVillageDataset(train_csv, transform=get_train_transforms(img_size))
    val_dataset = PlantVillageDataset(val_csv, transform=get_eval_transforms(img_size))

    class_counts = train_dataset.get_class_counts()
    class_weights = compute_class_weights(class_counts, num_classes=len(TARGET_CLASSES)).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    num_workers = 4 if sys.platform != "win32" else 0
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=(device.type == "cuda"),
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=(device.type == "cuda"),
    )

    print(f"Loaded {len(train_dataset)} train samples, {len(val_dataset)} validation samples.")

    # 2. Model Initialization
    model = create_mobilenetv3(num_classes=len(TARGET_CLASSES), variant=variant, pretrained=True)
    model.to(device)

    # 3. PHASE 1: Head Warmup (Freeze Backbone)
    print("\n--- PHASE 1: Classifier Head Warmup (Backbone Frozen) ---")
    for param in model.features.parameters():
        param.requires_grad = False
    for param in model.classifier.parameters():
        param.requires_grad = True

    optimizer_head = torch.optim.AdamW(
        model.classifier.parameters(),
        lr=lr_head,
        weight_decay=1e-4,
    )

    history: list[dict[str, Any]] = []
    best_val_f1 = 0.0
    best_val_acc = 0.0
    best_epoch = 0
    best_state_dict: dict[str, Any] | None = None
    epochs_no_improve = 0

    global_epoch = 0
    for epoch in range(1, epochs_phase1 + 1):
        global_epoch += 1
        model.train()
        running_loss = 0.0
        train_preds: list[int] = []
        train_targets: list[int] = []
        t0 = time.time()

        for images, targets in train_loader:
            images = images.to(device)
            targets = targets.to(device)

            optimizer_head.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer_head.step()

            running_loss += loss.item() * images.size(0)
            preds = torch.argmax(outputs, dim=1).detach().cpu().numpy()
            train_preds.extend(preds)
            train_targets.extend(targets.cpu().numpy())

        epoch_loss = running_loss / len(train_dataset)
        epoch_acc = float(accuracy_score(train_targets, train_preds))
        epoch_f1 = float(f1_score(train_targets, train_preds, average="macro", zero_division=0))

        val_loss, val_acc, val_f1 = evaluate_dataset(model, val_loader, criterion, device)
        elapsed = time.time() - t0

        record = {
            "epoch": global_epoch,
            "phase": "head_warmup",
            "train_loss": round(epoch_loss, 4),
            "train_acc": round(epoch_acc, 4),
            "train_macro_f1": round(epoch_f1, 4),
            "val_loss": round(val_loss, 4),
            "val_acc": round(val_acc, 4),
            "val_macro_f1": round(val_f1, 4),
            "time_sec": round(elapsed, 1),
        }
        history.append(record)
        print(
            f"Epoch {global_epoch:02d} [Warmup] - Train Loss: {epoch_loss:.4f}, Acc: {epoch_acc:.2%}, F1: {epoch_f1:.4f} | "
            f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.2%}, F1: {val_f1:.4f} ({elapsed:.1f}s)"
        )

        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_val_acc = val_acc
            best_epoch = global_epoch
            best_state_dict = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    # 4. PHASE 2: Fine-Tuning (Unfreeze Backbone)
    print("\n--- PHASE 2: Selective Backbone Fine-Tuning ---")
    for param in model.features.parameters():
        param.requires_grad = True

    optimizer_ft = torch.optim.AdamW(
        [
            {"params": model.features.parameters(), "lr": lr_backbone},
            {"params": model.classifier.parameters(), "lr": lr_head * 0.2},
        ],
        weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer_ft, T_max=epochs_phase2, eta_min=1e-6)

    for epoch in range(1, epochs_phase2 + 1):
        global_epoch += 1
        model.train()
        running_loss = 0.0
        train_preds: list[int] = []
        train_targets: list[int] = []
        t0 = time.time()

        for images, targets in train_loader:
            images = images.to(device)
            targets = targets.to(device)

            optimizer_ft.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer_ft.step()

            running_loss += loss.item() * images.size(0)
            preds = torch.argmax(outputs, dim=1).detach().cpu().numpy()
            train_preds.extend(preds)
            train_targets.extend(targets.cpu().numpy())

        scheduler.step()
        epoch_loss = running_loss / len(train_dataset)
        epoch_acc = float(accuracy_score(train_targets, train_preds))
        epoch_f1 = float(f1_score(train_targets, train_preds, average="macro", zero_division=0))

        val_loss, val_acc, val_f1 = evaluate_dataset(model, val_loader, criterion, device)
        elapsed = time.time() - t0

        record = {
            "epoch": global_epoch,
            "phase": "fine_tuning",
            "train_loss": round(epoch_loss, 4),
            "train_acc": round(epoch_acc, 4),
            "train_macro_f1": round(epoch_f1, 4),
            "val_loss": round(val_loss, 4),
            "val_acc": round(val_acc, 4),
            "val_macro_f1": round(val_f1, 4),
            "time_sec": round(elapsed, 1),
        }
        history.append(record)
        print(
            f"Epoch {global_epoch:02d} [FineTune] - Train Loss: {epoch_loss:.4f}, Acc: {epoch_acc:.2%}, F1: {epoch_f1:.4f} | "
            f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.2%}, F1: {val_f1:.4f} ({elapsed:.1f}s)"
        )

        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_val_acc = val_acc
            best_epoch = global_epoch
            best_state_dict = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            epochs_no_improve = 0
            print(f"  -> New best validation Macro-F1: {best_val_f1:.4f} (Acc: {best_val_acc:.2%})")
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                print(f"Early stopping triggered at epoch {global_epoch} (patience={patience}).")
                break

    total_training_time = round(time.time() - start_time, 1)
    print(f"\nTraining completed in {total_training_time}s.")
    print(f"Best Validation Macro-F1: {best_val_f1:.4f} (Accuracy: {best_val_acc:.2%}) at Epoch {best_epoch}")

    # 5. Save Artifact Checkpoint
    if output_model_path is None:
        output_model_path = MODELS_DIR / "mobilenetv3_plantdisease_best.pth"
    output_model_path.parent.mkdir(parents=True, exist_ok=True)

    checkpoint = {
        "model_state_dict": best_state_dict,
        "architecture": f"mobilenet_v3_{variant}",
        "num_classes": len(TARGET_CLASSES),
        "classes": [c["class_idx"] for c in TARGET_CLASSES],
        "class_metadata": TARGET_CLASSES,
        "class_names": [c["display_name"] for c in TARGET_CLASSES],
        "image_size": (img_size, img_size),
        "normalization": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD},
        "best_epoch": best_epoch,
        "best_val_macro_f1": best_val_f1,
        "best_val_accuracy": best_val_acc,
        "training_history": history,
        "hyperparameters": {
            "variant": variant,
            "epochs_phase1": epochs_phase1,
            "epochs_phase2": epochs_phase2,
            "batch_size": batch_size,
            "lr_head": lr_head,
            "lr_backbone": lr_backbone,
            "image_size": img_size,
            "seed": seed,
            "optimizer": "AdamW",
            "loss": "WeightedCrossEntropyLoss",
        },
        "reproducibility": {
            "python_version": sys.version,
            "torch_version": torch.__version__,
            "device": str(device),
            "mps_accelerated": (device.type == "mps"),
            "train_samples": len(train_dataset),
            "val_samples": len(val_dataset),
        },
    }
    torch.save(checkpoint, output_model_path)
    print(f"Saved best model checkpoint to: {output_model_path}")

    # 6. Save Training Report
    if output_report_path is None:
        output_report_path = PROJECT_ROOT / "ml" / "artifacts" / "mobilenetv3_training_report.md"
    output_report_path.parent.mkdir(parents=True, exist_ok=True)

    report_md = f"""# MobileNetV3 ({variant.upper()}) Transfer Learning Training Report

**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}  
**Model Architecture**: `mobilenet_v3_{variant}`  
**Pretrained Weights**: `ImageNet-1K` (Torchvision default)  
**Target Classes**: 17 PlantVillage classes (Tomato, Potato, Corn/Maize)  
**Compute Acceleration**: Apple Silicon MPS (`{device}`)  
**Total Training Time**: {total_training_time} seconds  

---

## 1. Executive Summary

A deep convolutional transfer learning model was trained to replace the handcrafted HSV/HOG linear ElasticNet classifier.
The training employed a **two-phase protocol**:
1. **Phase 1 (Warmup)**: Fixed pretrained backbone, training the 17-class classification head with AdamW ($lr={lr_head}$).
2. **Phase 2 (Fine-Tuning)**: Full backbone unfreezing with differential learning rates ($lr_{{\\text{{backbone}}}}={lr_backbone}$, $lr_{{\\text{{head}}}}={lr_head * 0.2}$) and Cosine Annealing.
3. **Class Balancing**: Balanced CrossEntropyLoss with clipped weights to counteract 30:1 imbalance between high-sample classes (`Tomato Yellow Leaf Curl Virus`) and low-sample classes (`Potato Healthy`).

### Key Results
* **Best Validation Accuracy**: **{best_val_acc:.2%}**
* **Best Validation Macro-F1**: **{best_val_f1:.4f}**
* **Peak Performance Epoch**: Epoch {best_epoch}
* **Checkpoint Saved**: [`{output_model_path.name}`](file://{output_model_path})

---

## 2. Epoch-by-Epoch Training Log

| Epoch | Phase | Train Loss | Train Acc | Train Macro-F1 | Val Loss | Val Acc | Val Macro-F1 | Time (s) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""
    for r in history:
        report_md += f"| {r['epoch']} | {r['phase']} | {r['train_loss']:.4f} | {r['train_acc']:.2%} | {r['train_macro_f1']:.4f} | {r['val_loss']:.4f} | {r['val_acc']:.2%} | {r['val_macro_f1']:.4f} | {r['time_sec']}s |\n"

    report_md += f"""
---

## 3. Training Configuration & Reproducibility

* **Architecture**: MobileNetV3-{variant.capitalize()}
* **Batch Size**: {batch_size}
* **Initial Head LR**: {lr_head}
* **Backbone Fine-Tuning LR**: {lr_backbone}
* **Image Size**: {img_size}x{img_size}
* **Random Seed**: {seed}
* **Data Augmentation**: Bilinear RandomResizedCrop(224, scale=(0.8, 1.0)), RandomHorizontalFlip(0.5), RandomRotation(15°), ColorJitter(brightness=0.15, contrast=0.15, saturation=0.15, hue=0.05).
"""
    with open(output_report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"Saved training report to: {output_report_path}")

    return {
        "best_epoch": best_epoch,
        "best_val_macro_f1": best_val_f1,
        "best_val_accuracy": best_val_acc,
        "total_training_time": total_training_time,
        "history": history,
        "checkpoint_path": str(output_model_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Train MobileNetV3 on PlantVillage dataset.")
    parser.add_argument("--variant", type=str, default="small", choices=["small", "large"], help="MobileNetV3 variant.")
    parser.add_argument("--epochs-phase1", type=int, default=3, help="Warmup epochs for head.")
    parser.add_argument("--epochs-phase2", type=int, default=7, help="Fine-tuning epochs.")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size.")
    parser.add_argument("--lr-head", type=float, default=5e-4, help="Learning rate for head.")
    parser.add_argument("--lr-backbone", type=float, default=1e-4, help="Learning rate for backbone.")
    parser.add_argument("--img-size", type=int, default=224, help="Input image dimension.")
    parser.add_argument("--device", type=str, default="auto", help="Compute device (auto, mps, cuda, cpu).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--output-model", type=Path, default=MODELS_DIR / "mobilenetv3_plantdisease_best.pth")
    parser.add_argument("--output-report", type=Path, default=PROJECT_ROOT / "ml" / "artifacts" / "mobilenetv3_training_report.md")

    args = parser.parse_args()
    train_mobilenetv3(
        variant=args.variant,
        epochs_phase1=args.epochs_phase1,
        epochs_phase2=args.epochs_phase2,
        batch_size=args.batch_size,
        lr_head=args.lr_head,
        lr_backbone=args.lr_backbone,
        img_size=args.img_size,
        device_name=args.device,
        seed=args.seed,
        output_model_path=args.output_model,
        output_report_path=args.output_report,
    )


if __name__ == "__main__":
    main()
