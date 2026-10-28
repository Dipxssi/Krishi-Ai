# KrishiAI MobileNetV3-Small Field Generalization Experiments

This directory contains the isolated, non-destructive experimental pipeline designed to improve the real-world field performance of KrishiAI's MobileNetV3-Small crop disease classifier by reconciling the laboratory PlantVillage dataset with in-the-wild PlantDoc field imagery.

All experiments are conducted strictly in this directory (`ml/experiments/`) to preserve the live baseline, production configuration, and deployed checkpoints without changes or risks to production.

---

## Directory Organization

```
ml/experiments/
├── configs/                          # Reproducible experiment configurations
│   ├── exp_b_pv_augmented.json      # Experiment B config (PlantVillage + Realistic Aug)
│   └── exp_c_combined.json          # Experiment C config (Combined PV + PD with Domain-Balanced Sampling)
├── dataset/
│   ├── manifests/                    # Reconciled manifests and split CSVs
│   │   ├── class_mapping_manifest.json
│   │   ├── dataset_audit_report.md
│   │   ├── duplicate_leakage_report.json
│   │   ├── combined_train.csv
│   │   ├── combined_val.csv
│   │   ├── plantdoc_test.csv        # Strictly sealed untouched test benchmark (N=99)
│   │   └── plantdoc_test_ood.csv    # Non-target out-of-scope test benchmark (N=125)
│   └── prepare_datasets.py          # Data ingestion, audit, reconciliation, and split generator
├── src/
│   ├── dataset.py                    # PyTorch datasets, field augmentations, domain-balanced sampler
│   ├── evaluate.py                   # Standardized evaluation engine and confusion matrix generator
│   ├── generate_comparison_report.py# Cross-experiment comparative report and plot generator
│   └── train.py                      # Two-stage transfer learning training pipeline
├── checkpoints/                      # Model checkpoints and training histories
│   ├── exp_b_pv_augmented/
│   └── exp_c_combined/
└── artifacts/                        # Benchmark evaluation reports and confusion matrices
    ├── exp_a_baseline/
    ├── exp_b_pv_augmented/
    ├── exp_c_combined/
    ├── comparison_barchart.png
    └── model_comparison_report.md
```

---

## Reproduction Instructions

### 1. Re-run Dataset Audit & Split Generation
```bash
backend/.venv/bin/python ml/experiments/dataset/prepare_datasets.py
```

### 2. Evaluate Baseline Model (Experiment A)
```bash
backend/.venv/bin/python ml/experiments/src/evaluate.py \
  --checkpoint ml/models/mobilenetv3_plantdisease_best.pth \
  --name "Experiment A - Baseline MobileNetV3" \
  --output-dir ml/experiments/artifacts/exp_a_baseline \
  --device mps
```

### 3. Train Experiment B (PlantVillage with Realistic Augmentation)
```bash
backend/.venv/bin/python ml/experiments/src/train.py \
  --train-csv ml/splits/train.csv \
  --val-csv ml/splits/val.csv \
  --output-dir ml/experiments/checkpoints/exp_b_pv_augmented \
  --name "Experiment B - PlantVillage Augmented" \
  --epochs-phase1 3 \
  --epochs-phase2 7 \
  --batch-size 64 \
  --device mps
```

Evaluate Experiment B:
```bash
backend/.venv/bin/python ml/experiments/src/evaluate.py \
  --checkpoint ml/experiments/checkpoints/exp_b_pv_augmented/best_model.pth \
  --name "Experiment B - PlantVillage Augmented" \
  --output-dir ml/experiments/artifacts/exp_b_pv_augmented \
  --device mps
```

### 4. Train Experiment C (Combined PlantVillage + PlantDoc)
```bash
backend/.venv/bin/python ml/experiments/src/train.py \
  --train-csv ml/experiments/dataset/manifests/combined_train.csv \
  --val-csv ml/experiments/dataset/manifests/combined_val.csv \
  --output-dir ml/experiments/checkpoints/exp_c_combined \
  --name "Experiment C - Combined PlantVillage + PlantDoc" \
  --epochs-phase1 3 \
  --epochs-phase2 7 \
  --batch-size 64 \
  --domain-sampler \
  --plantdoc-weight 0.35 \
  --device mps
```

Evaluate Experiment C:
```bash
backend/.venv/bin/python ml/experiments/src/evaluate.py \
  --checkpoint ml/experiments/checkpoints/exp_c_combined/best_model.pth \
  --name "Experiment C - Combined PlantVillage + PlantDoc" \
  --output-dir ml/experiments/artifacts/exp_c_combined \
  --device mps
```

### 5. Generate Comparative Analysis & Figures
```bash
backend/.venv/bin/python ml/experiments/src/generate_comparison_report.py
```
