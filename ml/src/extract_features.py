"""Resumable, parallel feature extraction pipeline for Train and Validation splits."""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np

from ml.src.config import FEATURES_DIR, PROJECT_ROOT, SPLITS_DIR
from ml.src.features import extract_features_from_image


def _process_single_image(args: tuple[int, str, int]) -> tuple[int, np.ndarray, int]:
    idx, rel_path, label = args
    full_path = PROJECT_ROOT / "ml" / "PlantVillage" / "raw" / "color" / rel_path
    feat = extract_features_from_image(full_path)
    return idx, feat, label


def extract_split_features(
    split_name: str,
    csv_path: Path,
    output_dir: Path = FEATURES_DIR,
    batch_size: int = 1000,
    max_workers: int = 6,
) -> tuple[np.ndarray, np.ndarray]:
    output_dir.mkdir(parents=True, exist_ok=True)
    final_x_path = output_dir / f"X_{split_name}.npy"
    final_y_path = output_dir / f"y_{split_name}.npy"

    if final_x_path.exists() and final_y_path.exists():
        print(f"[{split_name}] Found existing cached features: {final_x_path.name}")
        X = np.load(final_x_path)
        y = np.load(final_y_path)
        print(f"[{split_name}] Loaded shape: X={X.shape}, y={y.shape}")
        return X, y

    # Read manifest
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    n_samples = len(rows)
    feature_dim = 1606
    print(f"[{split_name}] Extracting features for {n_samples} images (dimension: {feature_dim})...")

    # Check for resumable partial cache
    partial_x_path = output_dir / f"X_{split_name}_partial.npy"
    partial_y_path = output_dir / f"y_{split_name}_partial.npy"
    meta_path = output_dir / f"{split_name}_extraction_progress.json"

    start_idx = 0
    if partial_x_path.exists() and partial_y_path.exists() and meta_path.exists():
        with open(meta_path) as mf:
            meta = json.load(mf)
        start_idx = meta.get("completed_count", 0)
        if start_idx < n_samples:
            print(f"[{split_name}] Resuming extraction from index {start_idx}/{n_samples}")
            X = np.load(partial_x_path)
            y = np.load(partial_y_path)
        else:
            X = np.load(partial_x_path)
            y = np.load(partial_y_path)
            np.save(final_x_path, X)
            np.save(final_y_path, y)
            return X, y
    else:
        X = np.zeros((n_samples, feature_dim), dtype=np.float32)
        y = np.zeros(n_samples, dtype=np.int64)

    items_to_process = [(i, rows[i]["rel_path"], int(rows[i]["class_idx"])) for i in range(start_idx, n_samples)]

    start_time = time.time()
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for chunk_start in range(0, len(items_to_process), batch_size):
            chunk = items_to_process[chunk_start : chunk_start + batch_size]
            results = list(executor.map(_process_single_image, chunk, chunksize=50))

            for idx, feat, label in results:
                X[idx] = feat
                y[idx] = label

            current_completed = start_idx + chunk_start + len(chunk)
            elapsed = time.time() - start_time
            rate = current_completed / max(elapsed, 1e-3)
            print(f"[{split_name}] Progress: {current_completed}/{n_samples} ({current_completed/n_samples*100:.1f}%) - {rate:.1f} img/s")

            # Checkpoint partial progress
            np.save(partial_x_path, X)
            np.save(partial_y_path, y)
            with open(meta_path, "w") as mf:
                json.dump({"completed_count": current_completed, "total": n_samples}, mf)

    # Verification checks
    assert not np.isnan(X).any(), f"[{split_name}] NaN values detected in feature matrix!"
    assert not np.isinf(X).any(), f"[{split_name}] Inf values detected in feature matrix!"
    assert X.shape == (n_samples, feature_dim), f"Unexpected X shape: {X.shape}"
    assert len(y) == n_samples, f"Unexpected y length: {len(y)}"

    # Save final cache and cleanup partial
    np.save(final_x_path, X)
    np.save(final_y_path, y)
    if partial_x_path.exists():
        partial_x_path.unlink()
    if partial_y_path.exists():
        partial_y_path.unlink()
    if meta_path.exists():
        meta_path.unlink()

    total_time = time.time() - start_time
    print(f"[{split_name}] Completed in {total_time:.1f}s. Saved to {final_x_path.name} ({X.nbytes / (1024*1024):.1f} MB)")
    return X, y


def run_feature_extraction():
    print("=== Step 2: Feature Extraction ===")
    train_csv = SPLITS_DIR / "train.csv"
    val_csv = SPLITS_DIR / "val.csv"

    print("Extracting Validation split first (3,621 images)...")
    X_val, y_val = extract_split_features("val", val_csv)

    print("\nExtracting Training split (16,908 images)...")
    X_train, y_train = extract_split_features("train", train_csv)

    print("\n=== Feature Extraction Verification Summary ===")
    print(f"X_train shape: {X_train.shape}, dtype: {X_train.dtype}, NaNs: {np.isnan(X_train).sum()}, Infs: {np.isinf(X_train).sum()}")
    print(f"y_train shape: {y_train.shape}, dtype: {y_train.dtype}, classes: {len(np.unique(y_train))}")
    print(f"X_val shape: {X_val.shape}, dtype: {X_val.dtype}, NaNs: {np.isnan(X_val).sum()}, Infs: {np.isinf(X_val).sum()}")
    print(f"y_val shape: {y_val.shape}, dtype: {y_val.dtype}, classes: {len(np.unique(y_val))}")
    print(f"Test split status: UNTOUCHED (Not extracted or evaluated)")


if __name__ == "__main__":
    run_feature_extraction()
