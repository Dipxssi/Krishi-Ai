"""Generate leakage-aware, specimen-grouped, stratified train/validation/test splits for the 17 target classes."""

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from ml.src.config import (
    DATASET_DIR,
    FOLDER_TO_CLASS,
    SPLITS_DIR,
    TARGET_CLASSES,
)


def extract_group_id(filename: str, class_name: str) -> str:
    """
    Extract physical specimen identifier across multiple days, camera shots, and copies.
    Prevents temporal and camera frame leakage across train/val/test splits.
    """
    if "___" in filename:
        tag_part = filename.split("___", 1)[1]
    else:
        tag_part = filename

    base_tag = Path(tag_part).stem

    # Check for explicit physical leaf identifier (e.g. "Leaf 17", "Leaf 2.1")
    leaf_match = re.search(r"Leaf\s+([\d\.]+)", base_tag, re.IGNORECASE)
    if leaf_match:
        # Unifies GHLB vs GHLB_PS, Day 8 vs Day 9 vs Day 16, and copies under the same leaf specimen
        return f"{class_name}::Leaf_{leaf_match.group(1)}"

    # Strip copy suffix (e.g. "copy 2", "copy")
    base_tag = re.sub(r"\s+copy(\s+\d+)?$", "", base_tag, flags=re.IGNORECASE)
    # Strip Day XX suffix
    base_tag = re.sub(r"\s+Day\s+\d+(\.\d+)?$", "", base_tag, flags=re.IGNORECASE)
    base_tag = re.sub(r"\s+", " ", base_tag).strip()
    return f"{class_name}::{base_tag}"


def build_split_manifests(
    dataset_dir: Path = DATASET_DIR,
    output_dir: Path = SPLITS_DIR,
    random_state: int = 42,
) -> dict[str, any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading images for {len(TARGET_CLASSES)} target classes from {dataset_dir}...")
    raw_records = []
    seen_hashes = {}
    duplicates_removed = []

    for cls_info in TARGET_CLASSES:
        folder_name = cls_info["folder_name"]
        cls_dir = dataset_dir / folder_name
        if not cls_dir.exists():
            raise FileNotFoundError(f"Missing expected directory: {cls_dir}")

        for file_path in sorted(cls_dir.iterdir()):
            if not file_path.is_file() or file_path.name.startswith("."):
                continue

            file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()

            if file_hash in seen_hashes:
                # Exact duplicate found
                keeper = seen_hashes[file_hash]
                duplicates_removed.append({
                    "duplicate_file": f"{folder_name}/{file_path.name}",
                    "canonical_file": keeper["rel_path"],
                    "class_name": folder_name,
                    "md5_hash": file_hash,
                })
                continue

            rel_path = f"{folder_name}/{file_path.name}"
            group_id = extract_group_id(file_path.name, folder_name)

            record = {
                "rel_path": rel_path,
                "full_path": f"ml/PlantVillage/raw/color/{rel_path}",
                "class_name": folder_name,
                "class_idx": cls_info["class_idx"],
                "crop": cls_info["crop"],
                "disease": cls_info["disease"],
                "display_name": cls_info["display_name"],
                "group_id": group_id,
                "md5_hash": file_hash,
            }
            seen_hashes[file_hash] = record
            raw_records.append(record)

    total_unique = len(raw_records)
    total_duplicates = len(duplicates_removed)
    print(f"Total unique images: {total_unique}, Redundant duplicates excluded: {total_duplicates}")

    # Prepare inputs for StratifiedGroupKFold
    y = np.array([r["class_idx"] for r in raw_records])
    groups = np.array([r["group_id"] for r in raw_records])

    # 20-fold split: 14 folds (70%) train, 3 folds (15%) val, 3 folds (15%) test
    sgkf = StratifiedGroupKFold(n_splits=20, shuffle=True, random_state=random_state)
    fold_assignments = np.zeros(total_unique, dtype=int)
    for fold, (_, test_idx) in enumerate(sgkf.split(raw_records, y, groups)):
        fold_assignments[test_idx] = fold

    train_indices = np.where(fold_assignments < 14)[0]
    val_indices = np.where((fold_assignments >= 14) & (fold_assignments < 17))[0]
    test_indices = np.where(fold_assignments >= 17)[0]

    train_records = [raw_records[i] for i in train_indices]
    val_records = [raw_records[i] for i in val_indices]
    test_records = [raw_records[i] for i in test_indices]

    # Verify zero group leakage
    train_groups = set(groups[train_indices])
    val_groups = set(groups[val_indices])
    test_groups = set(groups[test_indices])

    leakage_train_val = len(train_groups & val_groups)
    leakage_train_test = len(train_groups & test_groups)
    leakage_val_test = len(val_groups & test_groups)

    assert leakage_train_val == 0, f"Leakage detected between Train and Val: {leakage_train_val}"
    assert leakage_train_test == 0, f"Leakage detected between Train and Test: {leakage_train_test}"
    assert leakage_val_test == 0, f"Leakage detected between Val and Test: {leakage_val_test}"
    print("Specimen group verification passed: 0 group leakage across train, val, and test splits!")

    # Write manifests
    csv_fields = [
        "rel_path",
        "full_path",
        "class_name",
        "class_idx",
        "crop",
        "disease",
        "display_name",
        "group_id",
        "md5_hash",
    ]

    for name, split_data in [
        ("train.csv", train_records),
        ("val.csv", val_records),
        ("test.csv", test_records),
    ]:
        dest = output_dir / name
        with open(dest, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=csv_fields)
            writer.writeheader()
            writer.writerows(split_data)
        print(f"Saved {name}: {len(split_data)} rows ({len(split_data)/total_unique*100:.1f}%)")

    # Write duplicates removed log
    with open(output_dir / "duplicates_removed.csv", "w", newline="", encoding="utf-8") as fp:
        dup_fields = ["duplicate_file", "canonical_file", "class_name", "md5_hash"]
        writer = csv.DictWriter(fp, fieldnames=dup_fields)
        writer.writeheader()
        writer.writerows(duplicates_removed)
    print(f"Saved duplicates_removed.csv: {total_duplicates} rows")

    # Write classes mapping
    with open(output_dir / "classes.json", "w", encoding="utf-8") as fp:
        json.dump(TARGET_CLASSES, fp, indent=2)

    # Compile class distributions
    def count_classes(split_list):
        c = Counter(r["class_name"] for r in split_list)
        return {cls["folder_name"]: c[cls["folder_name"]] for cls in TARGET_CLASSES}

    train_dist = count_classes(train_records)
    val_dist = count_classes(val_records)
    test_dist = count_classes(test_records)

    summary = {
        "dataset_name": "PlantVillage",
        "target_classes_count": len(TARGET_CLASSES),
        "split_ratio": "70/15/15",
        "split_counts": {
            "train": len(train_records),
            "val": len(val_records),
            "test": len(test_records),
            "total_unique": total_unique,
            "redundant_duplicates_excluded": total_duplicates,
            "raw_total": total_unique + total_duplicates,
        },
        "group_leakage_audit": {
            "train_val_overlap": leakage_train_val,
            "train_test_overlap": leakage_train_test,
            "val_test_overlap": leakage_val_test,
        },
        "class_distributions": {
            cls["folder_name"]: {
                "class_idx": cls["class_idx"],
                "crop": cls["crop"],
                "disease": cls["disease"],
                "total": train_dist[cls["folder_name"]] + val_dist[cls["folder_name"]] + test_dist[cls["folder_name"]],
                "train": train_dist[cls["folder_name"]],
                "val": val_dist[cls["folder_name"]],
                "test": test_dist[cls["folder_name"]],
            }
            for cls in TARGET_CLASSES
        },
    }

    with open(output_dir / "split_summary.json", "w", encoding="utf-8") as fp:
        json.dump(summary, fp, indent=2)

    print(f"Summary written to {output_dir / 'split_summary.json'}")
    return summary


if __name__ == "__main__":
    build_split_manifests()
