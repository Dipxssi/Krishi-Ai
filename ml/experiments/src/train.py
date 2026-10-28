"""Modular training pipeline for MobileNetV3-Small experiments.
Supports Experiment B (PlantVillage with realistic augmentation)
and Experiment C (Combined PlantVillage + PlantDoc with domain-balanced sampling).
"""

from __future__ import annotations

import argparse
import csv
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

# Ensure repo root is on path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.src.config import IDX_TO_CLASS, TARGET_CLASSES
from ml.experiments.src.dataset import (
    DomainBalancedBatchSampler,
    FoliarDiseaseDataset,
    get_eval_transforms,
    get_field_train_transforms,
    IMAGENET_MEAN,
    IMAGENET_STD,
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


def create_mobilenetv3_small(num_classes: int = 17, pretrained: bool = True) -> nn.Module:
    weights = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
    model = models.mobilenet_v3_small(weights=weights)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    return model


def compute_class_weights(class_counts: dict[int, int], num_classes: int = 17) -> torch.Tensor:
    total = sum(class_counts.values())
    weights = np.zeros(num_classes, dtype=np.float32)
    for idx in range(num_classes):
        count = class_counts.get(idx, 1)
        weights[idx] = total / (num_classes * max(count, 1))

    weights = np.clip(weights, 0.2, 5.0)
    weights = weights / weights.mean()
    return torch.tensor(weights, dtype=torch.float32)


def evaluate_loader(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, float, float]:
    model.eval()
    total_loss = 0.0
    all_preds: list[int] = []
    all_targets: list[int] = []

    with torch.no_grad():
        for images, targets in loader:
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


def train_experiment(
    train_csv: Path,
    val_csv: Path,
    output_dir: Path,
    experiment_name: str,
    epochs_phase1: int = 3,
    epochs_phase2: int = 7,
    batch_size: int = 64,
    lr_head: float = 5e-4,
    lr_backbone: float = 1e-4,
    use_domain_sampler: bool = False,
    plantdoc_weight: float = 0.35,
    patience: int = 4,
    seed: int = 42,
    device_name: str = "auto",
    pilot_mode: bool = False,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    start_time = time.time()
    set_seed(seed)
    device = get_device(device_name)

    print(f"\n{'='*80}")
    print(f"STARTING TRAINING: {experiment_name.upper()}")
    print(f"Compute device: {device} | Seed: {seed} | Pilot: {pilot_mode}")
    print(f"Train CSV: {train_csv.name} | Val CSV: {val_csv.name}")
    print(f"Batch size: {batch_size} | Phase 1 (Warmup): {epochs_phase1} | Phase 2 (Fine-tune): {epochs_phase2}")
    if use_domain_sampler:
        print(f"Domain-Balanced Sampling enabled: PlantDoc sampling target = {plantdoc_weight:.1%}")
    print(f"{'='*80}")

    # 1. Datasets & Loaders
    train_transform = get_field_train_transforms(224)
    eval_transform = get_eval_transforms(224)

    train_dataset = FoliarDiseaseDataset(train_csv, transform=train_transform)
    val_dataset = FoliarDiseaseDataset(val_csv, transform=eval_transform)

    # In pilot mode, take small subset of data for 1 epoch
    if pilot_mode:
        epochs_phase1 = 1
        epochs_phase2 = 1
        train_dataset.samples = train_dataset.samples[:128]
        val_dataset.samples = val_dataset.samples[:64]
        batch_size = 16

    num_workers = 2 if sys.platform != "win32" else 0
    if use_domain_sampler and not pilot_mode:
        sampler = DomainBalancedBatchSampler(
            train_dataset,
            plantdoc_weight=plantdoc_weight,
            seed=seed,
        )
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            sampler=sampler,
            num_workers=num_workers,
            pin_memory=(device.type == "cuda"),
        )
    else:
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

    class_counts = train_dataset.get_class_counts(num_classes=len(TARGET_CLASSES))
    class_weights = compute_class_weights(class_counts, num_classes=len(TARGET_CLASSES)).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    # 2. Model Initialization
    model = create_mobilenetv3_small(num_classes=len(TARGET_CLASSES), pretrained=True)
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

        epoch_loss = running_loss / max(len(train_preds), 1)
        epoch_acc = float(accuracy_score(train_targets, train_preds))
        epoch_f1 = float(f1_score(train_targets, train_preds, average="macro", zero_division=0))

        val_loss, val_acc, val_f1 = evaluate_loader(model, val_loader, criterion, device)
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
    print("\n--- PHASE 2: Full Backbone Fine-Tuning ---")
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
        epoch_loss = running_loss / max(len(train_preds), 1)
        epoch_acc = float(accuracy_score(train_targets, train_preds))
        epoch_f1 = float(f1_score(train_targets, train_preds, average="macro", zero_division=0))

        val_loss, val_acc, val_f1 = evaluate_loader(model, val_loader, criterion, device)
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
    print(f"Best Validation Macro-F1: {best_val_f1:.4f} (Acc: {best_val_acc:.2%}) at Epoch {best_epoch}")

    # 5. Save Checkpoints
    best_checkpoint_path = output_dir / "best_model.pth"
    latest_checkpoint_path = output_dir / "latest_checkpoint.pth"

    checkpoint_data = {
        "experiment_name": experiment_name,
        "architecture": "mobilenet_v3_small",
        "num_classes": len(TARGET_CLASSES),
        "classes": [c["class_idx"] for c in TARGET_CLASSES],
        "class_metadata": TARGET_CLASSES,
        "class_names": [c["display_name"] for c in TARGET_CLASSES],
        "image_size": (224, 224),
        "normalization": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD},
        "best_epoch": best_epoch,
        "best_val_macro_f1": best_val_f1,
        "best_val_accuracy": best_val_acc,
        "training_history": history,
        "total_training_time_seconds": total_training_time,
        "hyperparameters": {
            "epochs_phase1": epochs_phase1,
            "epochs_phase2": epochs_phase2,
            "batch_size": batch_size,
            "lr_head": lr_head,
            "lr_backbone": lr_backbone,
            "seed": seed,
            "use_domain_sampler": use_domain_sampler,
            "plantdoc_weight": plantdoc_weight if use_domain_sampler else 0.0,
        },
        "reproducibility": {
            "python_version": sys.version,
            "torch_version": torch.__version__,
            "device": str(device),
        },
    }

    # Save best checkpoint
    best_checkpoint_data = {**checkpoint_data, "model_state_dict": best_state_dict}
    torch.save(best_checkpoint_data, best_checkpoint_path)
    print(f"Saved best model checkpoint to: {best_checkpoint_path}")

    # Save latest checkpoint for resumption
    latest_checkpoint_data = {**checkpoint_data, "model_state_dict": {k: v.cpu().clone() for k, v in model.state_dict().items()}}
    torch.save(latest_checkpoint_data, latest_checkpoint_path)

    # Save training log JSON
    with open(output_dir / "training_history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    return {
        "best_epoch": best_epoch,
        "best_val_macro_f1": best_val_f1,
        "best_val_accuracy": best_val_acc,
        "total_time": total_training_time,
        "checkpoint_path": str(best_checkpoint_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Train MobileNetV3 experiment.")
    parser.add_argument("--train-csv", type=str, required=True, help="Path to training CSV manifest")
    parser.add_argument("--val-csv", type=str, required=True, help="Path to validation CSV manifest")
    parser.add_argument("--output-dir", type=str, required=True, help="Output directory for checkpoints")
    parser.add_argument("--name", type=str, required=True, help="Experiment name")
    parser.add_argument("--epochs-phase1", type=int, default=3, help="Warmup epochs")
    parser.add_argument("--epochs-phase2", type=int, default=7, help="Fine-tuning epochs")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size")
    parser.add_argument("--lr-head", type=float, default=5e-4, help="Learning rate head")
    parser.add_argument("--lr-backbone", type=float, default=1e-4, help="Learning rate backbone")
    parser.add_argument("--domain-sampler", action="store_true", help="Use domain-balanced sampler")
    parser.add_argument("--plantdoc-weight", type=float, default=0.35, help="Sampling weight for PlantDoc in combined dataset")
    parser.add_argument("--patience", type=int, default=4, help="Early stopping patience")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--device", type=str, default="auto", help="Compute device (auto, mps, cpu, cuda)")
    parser.add_argument("--pilot", action="store_true", help="Run in fast pilot smoke-test mode")

    args = parser.parse_args()
    train_experiment(
        train_csv=Path(args.train_csv),
        val_csv=Path(args.val_csv),
        output_dir=Path(args.output_dir),
        experiment_name=args.name,
        epochs_phase1=args.epochs_phase1,
        epochs_phase2=args.epochs_phase2,
        batch_size=args.batch_size,
        lr_head=args.lr_head,
        lr_backbone=args.lr_backbone,
        use_domain_sampler=args.domain_sampler,
        plantdoc_weight=args.plantdoc_weight,
        patience=args.patience,
        seed=args.seed,
        device_name=args.device,
        pilot_mode=args.pilot,
    )


if __name__ == "__main__":
    main()
