"""Dataset classes, field augmentations, and domain-balanced sampling for KrishiAI experiments."""

from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset, Sampler
from torchvision import transforms

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def get_field_train_transforms(image_size: int = 224) -> transforms.Compose:
    """
    Realistic field-domain augmentation pipeline.
    Simulates real-world farm conditions (varied sun illumination, non-perpendicular angles,
    slight camera shake, color temperature shifts) while strictly preserving fine lesion morphology.
    """
    return transforms.Compose([
        transforms.Resize((256, 256), interpolation=transforms.InterpolationMode.BILINEAR),
        transforms.RandomResizedCrop(
            image_size,
            scale=(0.75, 1.0),
            ratio=(0.85, 1.15),
            interpolation=transforms.InterpolationMode.BILINEAR,
        ),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.2),
        transforms.RandomRotation(degrees=20),
        transforms.RandomPerspective(distortion_scale=0.15, p=0.4),
        transforms.ColorJitter(
            brightness=0.25,
            contrast=0.25,
            saturation=0.25,
            hue=0.08,
        ),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def get_eval_transforms(image_size: int = 224) -> transforms.Compose:
    """Deterministic evaluation transform matching the production pipeline."""
    return transforms.Compose([
        transforms.Resize((image_size, image_size), interpolation=transforms.InterpolationMode.BILINEAR),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


class FoliarDiseaseDataset(Dataset):
    """
    General dataset for PlantVillage, PlantDoc, and Combined splits.
    Reads manifest CSVs containing full_path and class_idx.
    """

    def __init__(
        self,
        csv_path: str | Path,
        transform: Callable | None = None,
        return_meta: bool = False,
    ):
        self.csv_path = Path(csv_path)
        self.transform = transform
        self.return_meta = return_meta
        self.samples: list[dict[str, Any]] = []

        if not self.csv_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.csv_path}")

        with open(self.csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.samples.append({
                    "source": row.get("source", "unknown"),
                    "full_path": Path(row["full_path"]),
                    "class_idx": int(row.get("class_idx", -1)),
                    "crop": row.get("crop", ""),
                    "disease": row.get("disease", ""),
                    "display_name": row.get("display_name", ""),
                    "is_healthy": row.get("is_healthy", "False") == "True",
                    "md5": row.get("md5", ""),
                })

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int] | tuple[torch.Tensor, int, dict[str, Any]]:
        item = self.samples[idx]
        image_path = item["full_path"]

        try:
            image = Image.open(image_path).convert("RGB")
        except Exception as exc:
            raise RuntimeError(f"Error loading image {image_path}: {exc}") from exc

        if self.transform is not None:
            tensor = self.transform(image)
        else:
            tensor = transforms.ToTensor()(image)

        if self.return_meta:
            return tensor, item["class_idx"], item
        return tensor, item["class_idx"]

    def get_class_counts(self, num_classes: int = 17) -> dict[int, int]:
        counts: dict[int, int] = {i: 0 for i in range(num_classes)}
        for s in self.samples:
            counts[s["class_idx"]] += 1
        return counts

    def get_source_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for s in self.samples:
            src = s["source"]
            counts[src] = counts.get(src, 0) + 1
        return counts


class DomainBalancedBatchSampler(Sampler):
    """
    Balanced Sampler for combined laboratory (PlantVillage) and in-the-wild field (PlantDoc) data.
    Ensures that every mini-batch contains a targeted ratio of field images (e.g. 35% field, 65% lab)
    combined with inverse-frequency class balancing, preventing the much larger lab dataset from
    dominating gradient updates.
    """

    def __init__(
        self,
        dataset: FoliarDiseaseDataset,
        plantdoc_weight: float = 0.35,
        total_samples: int | None = None,
        seed: int = 42,
    ):
        self.dataset = dataset
        self.plantdoc_weight = plantdoc_weight
        self.rng = np.random.RandomState(seed)

        self.pv_indices = [i for i, s in enumerate(dataset.samples) if s["source"] == "plantvillage"]
        self.pd_indices = [i for i, s in enumerate(dataset.samples) if s["source"] == "plantdoc"]

        # Number of samples per epoch (defaults to length of dataset)
        self.total_samples = total_samples if total_samples is not None else len(dataset)

        # Class weights within each domain
        self.pv_class_weights = self._compute_domain_weights(self.pv_indices)
        self.pd_class_weights = self._compute_domain_weights(self.pd_indices)

    def _compute_domain_weights(self, indices: list[int]) -> np.ndarray:
        if not indices:
            return np.array([])
        labels = [self.dataset.samples[i]["class_idx"] for i in indices]
        counts = Counter(labels)
        weights = np.zeros(len(indices), dtype=np.float64)
        for idx, i in enumerate(indices):
            lbl = self.dataset.samples[i]["class_idx"]
            weights[idx] = 1.0 / max(counts[lbl], 1)
        # Normalize to probability distribution
        weights /= weights.sum()
        return weights

    def __iter__(self):
        n_pd = int(self.total_samples * self.plantdoc_weight)
        n_pv = self.total_samples - n_pd

        if len(self.pd_indices) > 0 and n_pd > 0:
            chosen_pd = self.rng.choice(self.pd_indices, size=n_pd, replace=True, p=self.pd_class_weights)
        else:
            chosen_pd = np.array([], dtype=int)

        if len(self.pv_indices) > 0 and n_pv > 0:
            chosen_pv = self.rng.choice(self.pv_indices, size=n_pv, replace=True, p=self.pv_class_weights)
        else:
            chosen_pv = np.array([], dtype=int)

        all_chosen = np.concatenate([chosen_pd, chosen_pv])
        self.rng.shuffle(all_chosen)

        for idx in all_chosen:
            yield int(idx)

    def __len__(self) -> int:
        return self.total_samples
