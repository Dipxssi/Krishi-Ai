"""Dataset definitions and image transforms for KrishiAI MobileNetV3."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Callable

import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from ml.src.config import IDX_TO_CLASS, PROJECT_ROOT, TARGET_CLASSES

PLANTDOC_ROOT = Path("/Users/ishansharma2702/Downloads/PlantDoc-Dataset-master")
PLANTVILLAGE_ROOT = PROJECT_ROOT / "ml" / "PlantVillage" / "raw" / "color"

# Standard ImageNet normalization constants for pretrained torchvision models
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def get_train_transforms(image_size: int = 224) -> transforms.Compose:
    """
    Realistic augmentation pipeline preserving fine lesion details and pathogen symptoms.
    Avoids aggressive distortions (e.g. extreme cutouts or heavy blurs) that would destroy foliar spots.
    """
    return transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.RandomResizedCrop(
            image_size,
            scale=(0.8, 1.0),
            ratio=(0.9, 1.1),
            interpolation=transforms.InterpolationMode.BILINEAR,
        ),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(
            brightness=0.15,
            contrast=0.15,
            saturation=0.15,
            hue=0.05,
        ),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def get_eval_transforms(image_size: int = 224) -> transforms.Compose:
    """Deterministic preprocessing for validation and test evaluation."""
    return transforms.Compose([
        transforms.Resize((image_size, image_size), interpolation=transforms.InterpolationMode.BILINEAR),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


class PlantVillageDataset(Dataset):
    """
    PyTorch Dataset for PlantVillage splits.
    Reads CSV split manifests generated with zero specimen leakage.
    """

    def __init__(
        self,
        csv_path: str | Path,
        transform: Callable | None = None,
        base_dir: Path = PROJECT_ROOT,
    ):
        self.csv_path = Path(csv_path)
        self.base_dir = base_dir
        self.transform = transform
        self.samples: list[dict[str, Any]] = []

        with open(self.csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.samples.append({
                    "full_path": self.base_dir / row["full_path"],
                    "class_idx": int(row["class_idx"]),
                    "crop": row["crop"],
                    "disease": row["disease"],
                    "display_name": row["display_name"],
                    "group_id": row.get("group_id", ""),
                })

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        item = self.samples[idx]
        image_path = item["full_path"]

        try:
            image = Image.open(image_path).convert("RGB")
        except Exception as exc:
            raise RuntimeError(f"Error loading image {image_path}: {exc}") from exc

        if self.transform is not None:
            image_tensor = self.transform(image)
        else:
            image_tensor = transforms.ToTensor()(image)

        return image_tensor, item["class_idx"]

    def get_class_counts(self) -> dict[int, int]:
        counts: dict[int, int] = {i: 0 for i in range(len(TARGET_CLASSES))}
        for s in self.samples:
            counts[s["class_idx"]] += 1
        return counts


class PlantDocBenchmarkDataset(Dataset):
    """
    PyTorch Dataset for PlantDoc external benchmark evaluation.
    Can filter by mapping status ('unambiguous_mapped', 'out_of_scope', or 'all').
    """

    def __init__(
        self,
        manifest_path: str | Path = PROJECT_ROOT / "ml" / "plantdoc" / "manifest.csv",
        plantdoc_root: Path = PLANTDOC_ROOT,
        mapping_filter: str | None = "unambiguous_mapped",
        transform: Callable | None = None,
    ):
        self.manifest_path = Path(manifest_path)
        self.plantdoc_root = plantdoc_root
        self.transform = transform
        self.mapping_filter = mapping_filter
        self.samples: list[dict[str, Any]] = []

        with open(self.manifest_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if mapping_filter and row["mapping_status"] != mapping_filter:
                    continue

                full_p = self.plantdoc_root / row["rel_path"]
                self.samples.append({
                    "image_id": row["image_id"],
                    "split": row["split"],
                    "plantdoc_folder": row["plantdoc_folder"],
                    "rel_path": row["rel_path"],
                    "full_path": str(full_p),
                    "mapping_status": row["mapping_status"],
                    "target_class_idx": int(row["target_class_idx"]),
                    "target_display_name": row["target_display_name"],
                    "target_crop": row["target_crop"],
                    "is_healthy": row["is_healthy"] == "True",
                })

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int, dict[str, Any]]:
        item = self.samples[idx]
        image_path = item["full_path"]

        try:
            image = Image.open(image_path).convert("RGB")
        except Exception as exc:
            raise RuntimeError(f"Error loading image {image_path}: {exc}") from exc

        if self.transform is not None:
            image_tensor = self.transform(image)
        else:
            image_tensor = transforms.ToTensor()(image)

        return image_tensor, item["target_class_idx"], item
