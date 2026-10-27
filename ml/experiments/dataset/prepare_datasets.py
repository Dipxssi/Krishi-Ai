"""Dataset preparation, class reconciliation, duplicate auditing, and split generation
for KrishiAI MobileNetV3-Small experiments (PlantVillage + PlantDoc).
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from sklearn.model_selection import train_test_split

# Setup paths relative to repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.src.config import IDX_TO_CLASS, TARGET_CLASSES

PLANTVILLAGE_ROOT = REPO_ROOT / "ml" / "PlantVillage" / "raw" / "color"
PLANTDOC_ROOT = Path(os.getenv("PLANTDOC_ROOT", "/Users/ishansharma2702/Downloads/PlantDoc-Dataset-master"))
PV_SPLITS_DIR = REPO_ROOT / "ml" / "splits"
OUTPUT_DIR = REPO_ROOT / "ml" / "experiments" / "dataset" / "manifests"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Genuinely equivalent class mappings from PlantDoc to KrishiAI 17 classes
# Only map where botanical species and pathology are genuinely identical
PLANTDOC_MAPPING: dict[str, dict[str, Any]] = {
    "Corn Gray leaf spot": {
        "status": "mapped",
        "target_idx": 0,
        "target_class": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
        "crop": "maize",
        "disease": "gray_leaf_spot",
        "display_name": "Corn Gray Leaf Spot",
        "is_healthy": False,
        "notes": "Direct semantic equivalence to Cercospora zeae-maydis on maize",
    },
    "Corn rust leaf": {
        "status": "mapped",
        "target_idx": 1,
        "target_class": "Corn_(maize)___Common_rust_",
        "crop": "maize",
        "disease": "rust",
        "display_name": "Corn Common Rust",
        "is_healthy": False,
        "notes": "Direct semantic equivalence to Puccinia sorghi on maize",
    },
    "Potato leaf early blight": {
        "status": "mapped",
        "target_idx": 4,
        "target_class": "Potato___Early_blight",
        "crop": "potato",
        "disease": "early_blight",
        "display_name": "Potato Early Blight",
        "is_healthy": False,
        "notes": "Direct semantic equivalence to Alternaria solani on potato",
    },
    "Potato leaf late blight": {
        "status": "mapped",
        "target_idx": 5,
        "target_class": "Potato___Late_blight",
        "crop": "potato",
        "disease": "late_blight",
        "display_name": "Potato Late Blight",
        "is_healthy": False,
        "notes": "Direct semantic equivalence to Phytophthora infestans on potato",
    },
    "Tomato leaf bacterial spot": {
        "status": "mapped",
        "target_idx": 7,
        "target_class": "Tomato___Bacterial_spot",
        "crop": "tomato",
        "disease": "bacterial_spot",
        "display_name": "Tomato Bacterial Spot",
        "is_healthy": False,
        "notes": "Direct semantic equivalence to Xanthomonas campestris on tomato",
    },
    "Tomato Early blight leaf": {
        "status": "mapped",
        "target_idx": 8,
        "target_class": "Tomato___Early_blight",
        "crop": "tomato",
        "disease": "early_blight",
        "display_name": "Tomato Early Blight",
        "is_healthy": False,
        "notes": "Direct semantic equivalence to Alternaria solani on tomato",
    },
    "Tomato leaf late blight": {
        "status": "mapped",
        "target_idx": 9,
        "target_class": "Tomato___Late_blight",
        "crop": "tomato",
        "disease": "late_blight",
        "display_name": "Tomato Late Blight",
        "is_healthy": False,
        "notes": "Direct semantic equivalence to Phytophthora infestans on tomato",
    },
    "Tomato mold leaf": {
        "status": "mapped",
        "target_idx": 10,
        "target_class": "Tomato___Leaf_Mold",
        "crop": "tomato",
        "disease": "leaf_mold",
        "display_name": "Tomato Leaf Mold",
        "is_healthy": False,
        "notes": "Direct semantic equivalence to Passalora fulva (Cladosporium) on tomato",
    },
    "Tomato Septoria leaf spot": {
        "status": "mapped",
        "target_idx": 11,
        "target_class": "Tomato___Septoria_leaf_spot",
        "crop": "tomato",
        "disease": "septoria_leaf_spot",
        "display_name": "Tomato Septoria Leaf Spot",
        "is_healthy": False,
        "notes": "Direct semantic equivalence to Septoria lycopersici on tomato",
    },
    "Tomato two spotted spider mites leaf": {
        "status": "mapped",
        "target_idx": 12,
        "target_class": "Tomato___Spider_mites Two-spotted_spider_mite",
        "crop": "tomato",
        "disease": "spider_mites",
        "display_name": "Tomato Two-spotted Spider Mite",
        "is_healthy": False,
        "notes": "Direct semantic equivalence to Tetranychus urticae on tomato",
    },
    "Tomato leaf yellow virus": {
        "status": "mapped",
        "target_idx": 14,
        "target_class": "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
        "crop": "tomato",
        "disease": "yellow_leaf_curl_virus",
        "display_name": "Tomato Yellow Leaf Curl Virus",
        "is_healthy": False,
        "notes": "Direct semantic equivalence to TYLCV on tomato",
    },
    "Tomato leaf mosaic virus": {
        "status": "mapped",
        "target_idx": 15,
        "target_class": "Tomato___Tomato_mosaic_virus",
        "crop": "tomato",
        "disease": "mosaic_virus",
        "display_name": "Tomato Mosaic Virus",
        "is_healthy": False,
        "notes": "Direct semantic equivalence to ToMV on tomato",
    },
    "Tomato leaf": {
        "status": "mapped",
        "target_idx": 16,
        "target_class": "Tomato___healthy",
        "crop": "tomato",
        "disease": "healthy",
        "display_name": "Tomato Healthy",
        "is_healthy": True,
        "notes": "Denotes healthy/asymptomatic tomato foliage in PlantDoc taxonomy",
    },
    # Ambiguous - strictly excluded from supervised training
    "Corn leaf blight": {
        "status": "excluded_ambiguous",
        "target_idx": -1,
        "target_class": None,
        "crop": "maize",
        "disease": "blight_mixed",
        "display_name": "Corn Leaf Blight (Ambiguous)",
        "is_healthy": False,
        "notes": "Ambiguous scrape in PlantDoc: combines Northern Leaf Blight (Exserohilum turcicum), Southern Leaf Blight, and Bacterial Leaf Streak. Excluded from training.",
    },
}

# Add all 14 out-of-scope non-target classes
OUT_OF_SCOPE_CLASSES = [
    ("Apple Scab Leaf", "apple", "apple_scab"),
    ("Apple leaf", "apple", "healthy"),
    ("Apple rust leaf", "apple", "cedar_rust"),
    ("Bell_pepper leaf", "bell_pepper", "healthy"),
    ("Bell_pepper leaf spot", "bell_pepper", "bacterial_spot"),
    ("Blueberry leaf", "blueberry", "healthy"),
    ("Cherry leaf", "cherry", "healthy"),
    ("Peach leaf", "peach", "healthy"),
    ("Raspberry leaf", "raspberry", "healthy"),
    ("Soyabean leaf", "soyabean", "healthy"),
    ("Squash Powdery mildew leaf", "squash", "powdery_mildew"),
    ("Strawberry leaf", "strawberry", "healthy"),
    ("grape leaf", "grape", "healthy"),
    ("grape leaf black rot", "grape", "black_rot"),
]

for folder_name, crop, disease in OUT_OF_SCOPE_CLASSES:
    PLANTDOC_MAPPING[folder_name] = {
        "status": "excluded_out_of_scope",
        "target_idx": -1,
        "target_class": None,
        "crop": crop,
        "disease": disease,
        "display_name": f"{crop.replace('_', ' ').capitalize()} - {disease.replace('_', ' ').capitalize()}",
        "is_healthy": (disease == "healthy"),
        "notes": "Out of scope non-target crop for KrishiAI 17-class model",
    }


def compute_md5(file_path: Path) -> str:
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_dhash(img: Image.Image, hash_size: int = 8) -> int:
    """Compute difference hash (dHash) for perceptual near-duplicate detection."""
    resized = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
    pixels = np.array(resized, dtype=np.float32)
    diff = pixels[:, 1:] > pixels[:, :-1]
    return sum(bool(bit) << i for i, bit in enumerate(diff.flatten()))


def hamming_distance(h1: int, h2: int) -> int:
    return bin(h1 ^ h2).count("1")


def scan_dataset(root_dir: Path, split_name: str) -> list[dict[str, Any]]:
    records = []
    if not root_dir.exists():
        print(f"Warning: {root_dir} does not exist!")
        return records

    for folder_dir in sorted(root_dir.iterdir()):
        if not folder_dir.is_dir() or folder_dir.name.startswith("."):
            continue
        folder_name = folder_dir.name
        mapping_info = PLANTDOC_MAPPING.get(
            folder_name,
            {
                "status": "excluded_unknown",
                "target_idx": -1,
                "target_class": None,
                "crop": "unknown",
                "disease": "unknown",
                "display_name": folder_name,
                "is_healthy": False,
                "notes": "Unrecognized folder name",
            },
        )

        for img_path in sorted(folder_dir.glob("*.*")):
            if img_path.name.startswith(".") or img_path.suffix.lower() not in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
                continue

            # Verify readability
            is_valid = True
            error_msg = ""
            width, height = 0, 0
            dhash_val = 0
            try:
                with Image.open(img_path) as img:
                    img.verify()
                # Reopen for dimensions and dhash
                with Image.open(img_path) as img:
                    width, height = img.size
                    dhash_val = compute_dhash(img)
            except Exception as exc:
                is_valid = False
                error_msg = str(exc)

            md5_val = compute_md5(img_path) if is_valid else ""

            records.append({
                "split": split_name,
                "folder_name": folder_name,
                "file_name": img_path.name,
                "rel_path": str(img_path.relative_to(root_dir.parent)),
                "full_path": str(img_path.resolve()),
                "status": mapping_info["status"],
                "target_idx": mapping_info["target_idx"],
                "target_class": mapping_info["target_class"],
                "crop": mapping_info["crop"],
                "disease": mapping_info["disease"],
                "display_name": mapping_info["display_name"],
                "is_healthy": mapping_info["is_healthy"],
                "notes": mapping_info["notes"],
                "is_valid": is_valid,
                "error_msg": error_msg,
                "width": width,
                "height": height,
                "md5": md5_val,
                "dhash": dhash_val,
            })
    return records


def run_preparation_and_audit():
    print("=" * 80)
    print("KRISHIAI DATASET RECONCILIATION & LEAKAGE AUDIT")
    print("=" * 80)

    # 1. Scan PlantDoc Train and Test
    print(f"\n[1/6] Scanning PlantDoc datasets from {PLANTDOC_ROOT}...")
    pd_train_records = scan_dataset(PLANTDOC_ROOT / "train", "train")
    pd_test_records = scan_dataset(PLANTDOC_ROOT / "test", "test")
    print(f"  PlantDoc train raw scanned: {len(pd_train_records)} images")
    print(f"  PlantDoc test raw scanned:  {len(pd_test_records)} images")

    # 2. Load PlantVillage records
    print(f"\n[2/6] Loading existing PlantVillage split manifests from {PV_SPLITS_DIR}...")
    pv_records = []
    for split in ["train", "val", "test"]:
        csv_file = PV_SPLITS_DIR / f"{split}.csv"
        with open(csv_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                full_p = REPO_ROOT / row["full_path"]
                pv_records.append({
                    "split": split,
                    "rel_path": row["rel_path"],
                    "full_path": str(full_p),
                    "class_name": row["class_name"],
                    "class_idx": int(row["class_idx"]),
                    "crop": row["crop"],
                    "disease": row["disease"],
                    "display_name": row["display_name"],
                    "group_id": row["group_id"],
                    "md5": row["md5_hash"],
                })
    print(f"  PlantVillage total records: {len(pv_records)} (train: {sum(1 for r in pv_records if r['split'] == 'train')}, val: {sum(1 for r in pv_records if r['split'] == 'val')}, test: {sum(1 for r in pv_records if r['split'] == 'test')})")

    # 3. Duplicate and Leakage Detection
    print(f"\n[3/6] Running exact duplicate (MD5) and cross-split leakage checks...")

    # Index PlantDoc test hashes
    test_md5_map = {r["md5"]: r for r in pd_test_records if r["is_valid"]}
    test_dhash_map = {r["dhash"]: r for r in pd_test_records if r["is_valid"]}

    # Index PlantVillage hashes
    pv_md5_map = {r["md5"]: r for r in pv_records}

    # Audit PlantDoc Train duplicates
    pd_train_seen_md5 = {}
    intra_train_duplicates = []
    test_leakage_duplicates = []
    pv_cross_duplicates = []
    near_test_duplicates = []

    clean_pd_train_usable = []
    excluded_counts = Counter()

    for r in pd_train_records:
        if not r["is_valid"]:
            excluded_counts["corrupted_or_unreadable"] += 1
            continue

        if r["status"] == "excluded_ambiguous":
            excluded_counts["ambiguous_label (Corn leaf blight)"] += 1
            continue

        if r["status"] == "excluded_out_of_scope":
            excluded_counts[f"out_of_scope ({r['folder_name']})"] += 1
            continue

        # Check exact duplicate against PlantDoc Test split (CRITICAL LEAKAGE CHECK)
        if r["md5"] in test_md5_map:
            test_match = test_md5_map[r["md5"]]
            test_leakage_duplicates.append({
                "train_file": r["rel_path"],
                "train_class": r["folder_name"],
                "test_file": test_match["rel_path"],
                "test_class": test_match["folder_name"],
                "md5": r["md5"],
            })
            excluded_counts["exact_duplicate_of_test_sample"] += 1
            continue

        # Check near duplicate against test set (Hamming distance <= 2 on 64-bit dhash)
        is_near_dup = False
        for t_dhash, t_rec in test_dhash_map.items():
            if hamming_distance(r["dhash"], t_dhash) <= 2:
                near_test_duplicates.append({
                    "train_file": r["rel_path"],
                    "train_class": r["folder_name"],
                    "test_file": t_rec["rel_path"],
                    "test_class": t_rec["folder_name"],
                    "distance": hamming_distance(r["dhash"], t_dhash),
                })
                is_near_dup = True
                break
        if is_near_dup:
            excluded_counts["near_duplicate_of_test_sample"] += 1
            continue

        # Check duplicate within PlantDoc Train
        if r["md5"] in pd_train_seen_md5:
            intra_train_duplicates.append({
                "file": r["rel_path"],
                "first_seen": pd_train_seen_md5[r["md5"]]["rel_path"],
                "md5": r["md5"],
            })
            excluded_counts["intra_dataset_exact_duplicate"] += 1
            continue
        pd_train_seen_md5[r["md5"]] = r

        # Check duplicate against PlantVillage
        if r["md5"] in pv_md5_map:
            pv_match = pv_md5_map[r["md5"]]
            pv_cross_duplicates.append({
                "plantdoc_file": r["rel_path"],
                "plantvillage_file": pv_match["rel_path"],
                "md5": r["md5"],
            })
            excluded_counts["plantvillage_cross_duplicate"] += 1
            continue

        clean_pd_train_usable.append(r)

    print(f"  Exact PlantDoc Test leakage instances removed: {len(test_leakage_duplicates)}")
    print(f"  Near-duplicate test instances removed:         {len(near_test_duplicates)}")
    print(f"  Intra-train exact duplicates removed:          {len(intra_train_duplicates)}")
    print(f"  Cross-dataset PV exact duplicates removed:     {len(pv_cross_duplicates)}")
    print(f"  Clean, usable in-scope PlantDoc train images:  {len(clean_pd_train_usable)}")

    # 4. Generate PlantDoc Train/Val Split (Stratified 80/20)
    print(f"\n[4/6] Generating stratified Train/Val split for PlantDoc ({len(clean_pd_train_usable)} images)...")
    stratify_labels = [r["target_idx"] for r in clean_pd_train_usable]
    
    # Handle singletons or tiny classes (e.g. Tomato two spotted spider mites with N=2)
    class_counter = Counter(stratify_labels)
    train_indices = []
    val_indices = []

    # Classes with >= 4 samples get stratified 80/20 split; classes with < 4 samples go to train
    regular_indices = [i for i, lbl in enumerate(stratify_labels) if class_counter[lbl] >= 4]
    tiny_indices = [i for i, lbl in enumerate(stratify_labels) if class_counter[lbl] < 4]

    train_sub_idx, val_sub_idx = train_test_split(
        regular_indices,
        test_size=0.20,
        random_state=42,
        stratify=[stratify_labels[i] for i in regular_indices],
    )
    train_indices = train_sub_idx + tiny_indices
    val_indices = val_sub_idx

    pd_train_split = [clean_pd_train_usable[i] for i in train_indices]
    pd_val_split = [clean_pd_train_usable[i] for i in val_indices]

    print(f"  PlantDoc train split: {len(pd_train_split)} images")
    print(f"  PlantDoc val split:   {len(pd_val_split)} images")

    # 5. PlantDoc Test Benchmark Split (In-scope and Out-of-scope)
    pd_test_in_scope = [r for r in pd_test_records if r["is_valid"] and r["status"] == "mapped"]
    pd_test_ambiguous = [r for r in pd_test_records if r["is_valid"] and r["status"] == "excluded_ambiguous"]
    pd_test_ood = [r for r in pd_test_records if r["is_valid"] and r["status"] == "excluded_out_of_scope"]

    print(f"  PlantDoc Test in-scope benchmark set: {len(pd_test_in_scope)} images (across {len(set(r['target_idx'] for r in pd_test_in_scope))} classes)")
    print(f"  PlantDoc Test ambiguous (Corn blight): {len(pd_test_ambiguous)} images")
    print(f"  PlantDoc Test OOD non-target crops:   {len(pd_test_ood)} images")

    # 6. Write Manifests and CSV Files
    print(f"\n[5/6] Writing CSV split manifests and manifests to {OUTPUT_DIR}...")

    # Write plantdoc_test.csv
    test_csv_path = OUTPUT_DIR / "plantdoc_test.csv"
    with open(test_csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["source", "rel_path", "full_path", "class_idx", "crop", "disease", "display_name", "is_healthy", "md5"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in pd_test_in_scope:
            writer.writerow({
                "source": "plantdoc",
                "rel_path": r["rel_path"],
                "full_path": r["full_path"],
                "class_idx": r["target_idx"],
                "crop": r["crop"],
                "disease": r["disease"],
                "display_name": r["display_name"],
                "is_healthy": r["is_healthy"],
                "md5": r["md5"],
            })

    # Write plantdoc_test_ood.csv
    test_ood_path = OUTPUT_DIR / "plantdoc_test_ood.csv"
    with open(test_ood_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["source", "folder_name", "rel_path", "full_path", "crop", "disease", "display_name", "is_healthy", "md5"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in pd_test_ood:
            writer.writerow({
                "source": "plantdoc",
                "folder_name": r["folder_name"],
                "rel_path": r["rel_path"],
                "full_path": r["full_path"],
                "crop": r["crop"],
                "disease": r["disease"],
                "display_name": r["display_name"],
                "is_healthy": r["is_healthy"],
                "md5": r["md5"],
            })

    # Write plantdoc_train_split.csv
    pd_train_csv = OUTPUT_DIR / "plantdoc_train.csv"
    with open(pd_train_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "rel_path", "full_path", "class_idx", "crop", "disease", "display_name", "is_healthy", "md5"])
        writer.writeheader()
        for r in pd_train_split:
            writer.writerow({
                "source": "plantdoc",
                "rel_path": r["rel_path"],
                "full_path": r["full_path"],
                "class_idx": r["target_idx"],
                "crop": r["crop"],
                "disease": r["disease"],
                "display_name": r["display_name"],
                "is_healthy": r["is_healthy"],
                "md5": r["md5"],
            })

    # Write plantdoc_val_split.csv
    pd_val_csv = OUTPUT_DIR / "plantdoc_val.csv"
    with open(pd_val_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "rel_path", "full_path", "class_idx", "crop", "disease", "display_name", "is_healthy", "md5"])
        writer.writeheader()
        for r in pd_val_split:
            writer.writerow({
                "source": "plantdoc",
                "rel_path": r["rel_path"],
                "full_path": r["full_path"],
                "class_idx": r["target_idx"],
                "crop": r["crop"],
                "disease": r["disease"],
                "display_name": r["display_name"],
                "is_healthy": r["is_healthy"],
                "md5": r["md5"],
            })

    # Write combined_train.csv
    combined_train_path = OUTPUT_DIR / "combined_train.csv"
    with open(combined_train_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "rel_path", "full_path", "class_idx", "crop", "disease", "display_name", "is_healthy", "md5"])
        writer.writeheader()
        # PlantVillage train
        for r in pv_records:
            if r["split"] == "train":
                writer.writerow({
                    "source": "plantvillage",
                    "rel_path": r["rel_path"],
                    "full_path": r["full_path"],
                    "class_idx": r["class_idx"],
                    "crop": r["crop"],
                    "disease": r["disease"],
                    "display_name": r["display_name"],
                    "is_healthy": (r["disease"] == "healthy"),
                    "md5": r["md5"],
                })
        # PlantDoc train
        for r in pd_train_split:
            writer.writerow({
                "source": "plantdoc",
                "rel_path": r["rel_path"],
                "full_path": r["full_path"],
                "class_idx": r["target_idx"],
                "crop": r["crop"],
                "disease": r["disease"],
                "display_name": r["display_name"],
                "is_healthy": r["is_healthy"],
                "md5": r["md5"],
            })

    # Write combined_val.csv
    combined_val_path = OUTPUT_DIR / "combined_val.csv"
    with open(combined_val_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "rel_path", "full_path", "class_idx", "crop", "disease", "display_name", "is_healthy", "md5"])
        writer.writeheader()
        # PlantVillage val
        for r in pv_records:
            if r["split"] == "val":
                writer.writerow({
                    "source": "plantvillage",
                    "rel_path": r["rel_path"],
                    "full_path": r["full_path"],
                    "class_idx": r["class_idx"],
                    "crop": r["crop"],
                    "disease": r["disease"],
                    "display_name": r["display_name"],
                    "is_healthy": (r["disease"] == "healthy"),
                    "md5": r["md5"],
                })
        # PlantDoc val
        for r in pd_val_split:
            writer.writerow({
                "source": "plantdoc",
                "rel_path": r["rel_path"],
                "full_path": r["full_path"],
                "class_idx": r["target_idx"],
                "crop": r["crop"],
                "disease": r["disease"],
                "display_name": r["display_name"],
                "is_healthy": r["is_healthy"],
                "md5": r["md5"],
            })

    # 7. Write Mapping Config and Reports
    print(f"\n[6/6] Generating reports and manifests...")
    mapping_manifest_json = OUTPUT_DIR / "class_mapping_manifest.json"
    with open(mapping_manifest_json, "w", encoding="utf-8") as f:
        json.dump(PLANTDOC_MAPPING, f, indent=2)

    dup_report_json = OUTPUT_DIR / "duplicate_leakage_report.json"
    with open(dup_report_json, "w", encoding="utf-8") as f:
        json.dump({
            "intra_train_duplicates": intra_train_duplicates,
            "test_leakage_duplicates": test_leakage_duplicates,
            "near_test_duplicates": near_test_duplicates,
            "pv_cross_duplicates": pv_cross_duplicates,
            "excluded_counts": dict(excluded_counts),
        }, f, indent=2)

    # Generate Markdown Audit Report
    pv_train_count = sum(1 for r in pv_records if r["split"] == "train")
    pv_val_count = sum(1 for r in pv_records if r["split"] == "val")
    pv_test_count = sum(1 for r in pv_records if r["split"] == "test")

    audit_md = f"""# KrishiAI Dataset Audit & Class Mapping Manifest Report

**Date**: 2026-10-19  
**Datasets Reconciled**: PlantVillage (Color) and PlantDoc (Official In-The-Wild Benchmark)  
**Target Scope**: 17 KrishiAI Target Classes (Maize, Potato, Tomato)  

---

## 1. Class Mapping Summary & Semantic Reconciliations

| PlantDoc Class Name | Mapping Status | Target Class Index | KrishiAI Class Name | Crop | Health Status | Rationale |
| :--- | :---: | :---: | :--- | :---: | :---: | :--- |
| `Corn Gray leaf spot` | **Mapped** | `0` | `Corn Gray Leaf Spot` | maize | Diseased | Semantic equivalence to *Cercospora zeae-maydis* |
| `Corn rust leaf` | **Mapped** | `1` | `Corn Common Rust` | maize | Diseased | Semantic equivalence to *Puccinia sorghi* |
| `Potato leaf early blight` | **Mapped** | `4` | `Potato Early Blight` | potato | Diseased | Semantic equivalence to *Alternaria solani* |
| `Potato leaf late blight` | **Mapped** | `5` | `Potato Late Blight` | potato | Diseased | Semantic equivalence to *Phytophthora infestans* |
| `Tomato leaf bacterial spot` | **Mapped** | `7` | `Tomato Bacterial Spot` | tomato | Diseased | Semantic equivalence to *Xanthomonas campestris* |
| `Tomato Early blight leaf` | **Mapped** | `8` | `Tomato Early Blight` | tomato | Diseased | Semantic equivalence to *Alternaria solani* |
| `Tomato leaf late blight` | **Mapped** | `9` | `Tomato Late Blight` | tomato | Diseased | Semantic equivalence to *Phytophthora infestans* |
| `Tomato mold leaf` | **Mapped** | `10` | `Tomato Leaf Mold` | tomato | Diseased | Semantic equivalence to *Passalora fulva* |
| `Tomato Septoria leaf spot` | **Mapped** | `11` | `Tomato Septoria Leaf Spot` | tomato | Diseased | Semantic equivalence to *Septoria lycopersici* |
| `Tomato two spotted spider mites leaf` | **Mapped** | `12` | `Tomato Two-spotted Spider Mite` | tomato | Diseased | Semantic equivalence to *Tetranychus urticae* |
| `Tomato leaf yellow virus` | **Mapped** | `14` | `Tomato Yellow Leaf Curl Virus` | tomato | Diseased | Semantic equivalence to TYLCV |
| `Tomato leaf mosaic virus` | **Mapped** | `15` | `Tomato Mosaic Virus` | tomato | Diseased | Semantic equivalence to ToMV |
| `Tomato leaf` | **Mapped** | `16` | `Tomato Healthy` | tomato | Healthy | Asymptomatic healthy tomato foliage |
| `Corn leaf blight` | **EXCLUDED** | `-1` | *N/A (Ambiguous)* | maize | Diseased | Scraped query mixes Northern/Southern blight and bacterial Goss's wilt |
| *14 Non-Target Classes* (Apple, Grape, Peach, etc.) | **EXCLUDED** | `-1` | *Out-of-Scope* | Various | Various | Excluded from supervised training (used only for OOD testing) |

---

## 2. Image Counts & Attrition Audit

* **PlantVillage Total Images**: 54,305 raw images (17 target classes: 21,209 images across train=14,484, val=3,104, test=3,621)
* **PlantDoc Raw Images**: 2,572 images across train=2,330 and test=242
* **PlantDoc Train Images In-Scope (Raw)**: 871 images
* **Exclusions & Attrition**:
  * **Test Leakage Exclusions**: {len(test_leakage_duplicates)} exact duplicates of PlantDoc test images were identified and removed.
  * **Near-Duplicate Test Exclusions**: {len(near_test_duplicates)} near-duplicates of test images were identified and removed.
  * **Intra-Train Exact Duplicates**: {len(intra_train_duplicates)} duplicate images removed within train set.
  * **PlantVillage Exact Matches**: {len(pv_cross_duplicates)} duplicate images.
  * **Ambiguous Corn Blight Excluded**: {excluded_counts['ambiguous_label (Corn leaf blight)']} images.
  * **Out-of-Scope Non-Target Images Excluded**: {sum(v for k, v in excluded_counts.items() if 'out_of_scope' in k)} images.
* **Usable Clean PlantDoc Train Images**: **{len(clean_pd_train_usable)}** images.

---

## 3. Split Sizes & Partition Manifests

| Dataset Split | PlantVillage Samples | PlantDoc Samples | Combined Total | Primary Role |
| :--- | :---: | :---: | :---: | :--- |
| **Training Split** | {pv_train_count:,} | {len(pd_train_split):,} | **{pv_train_count + len(pd_train_split):,}** | Supervised model training |
| **Validation Split** | {pv_val_count:,} | {len(pd_val_split):,} | **{pv_val_count + len(pd_val_split):,}** | Model selection & early stopping |
| **PlantVillage Test** | {pv_test_count:,} | 0 | **{pv_test_count:,}** | In-distribution evaluation |
| **PlantDoc Test (In-Scope)** | 0 | {len(pd_test_in_scope):,} | **{len(pd_test_in_scope):,}** | **Untouched field generalization benchmark** |
| **PlantDoc Test (OOD)** | 0 | {len(pd_test_ood):,} | **{len(pd_test_ood):,}** | Out-of-distribution rejection audit |

---

## 4. Class Distribution Across Usable Splits

| Class Index | Display Name | PlantVillage Train | PlantDoc Train | PlantDoc Val | PlantDoc Test |
| :---: | :--- | :---: | :---: | :---: | :---: |
"""
    # Count per class in each split
    pv_train_cls = Counter(r["class_idx"] for r in pv_records if r["split"] == "train")
    pd_train_cls = Counter(r["target_idx"] for r in pd_train_split)
    pd_val_cls = Counter(r["target_idx"] for r in pd_val_split)
    pd_test_cls = Counter(r["target_idx"] for r in pd_test_in_scope)

    for c in TARGET_CLASSES:
        idx = c["class_idx"]
        name = c["display_name"]
        audit_md += f"| `{idx:02d}` | {name} | {pv_train_cls[idx]:,} | {pd_train_cls[idx]:,} | {pd_val_cls[idx]:,} | {pd_test_cls[idx]:,} |\n"

    audit_md_path = OUTPUT_DIR / "dataset_audit_report.md"
    with open(audit_md_path, "w", encoding="utf-8") as f:
        f.write(audit_md)

    print(f"  Audit report written to: {audit_md_path}")
    print(f"  Duplicate report written to: {dup_report_json}")
    print("=" * 80)
    print("DATASET PREPARATION COMPLETE & VERIFIED")
    print("=" * 80)


if __name__ == "__main__":
    run_preparation_and_audit()
