# KrishiAI MobileNetV3 Staging Integration & Deployment Package

**Date**: 2026-10-19  
**Candidate Model**: Experiment C (Combined PlantVillage + PlantDoc with Domain-Balanced Sampling)  
**Staging Artifact**: [`ml/models/mobilenetv3_plantdisease_staging.pth`](file:///Users/ishansharma2702/Downloads/Krishi-Ai-main/ml/models/mobilenetv3_plantdisease_staging.pth)  
**Live Production Baseline**: [`ml/models/mobilenetv3_plantdisease_best.pth`](file:///Users/ishansharma2702/Downloads/Krishi-Ai-main/ml/models/mobilenetv3_plantdisease_best.pth) (UNTOUCHED)  
**Production Backup**: [`ml/models/mobilenetv3_plantdisease_best.production_backup_20261019.pth`](file:///Users/ishansharma2702/Downloads/Krishi-Ai-main/ml/models/mobilenetv3_plantdisease_best.production_backup_20261019.pth) (VERIFIED)  

---

## 1. Executive Summary of Staging Integration

All required pre-staging improvements and safeguards have been implemented and verified:
1. **Thread-Safe Model Cache Invalidation**:
   - Implemented `clear_mobilenetv3_cache()` and path tracking in [`backend/app/vision/mobilenetv3_service.py`](file:///Users/ishansharma2702/Downloads/Krishi-Ai-main/backend/app/vision/mobilenetv3_service.py).
   - Protected model loading and cache lookups with `threading.Lock()`, eliminating race conditions during dynamic checkpoint switching.
2. **Crop Validation & Rejection Safeguards**:
   - Added crop hint dropdown in frontend composer ([`frontend/src/components/chat/ChatInput.tsx`](file:///Users/ishansharma2702/Downloads/Krishi-Ai-main/frontend/src/components/chat/ChatInput.tsx)) and forwarded selected crop to backend.
   - Normalized crop hints against supported crops (`tomato`, `potato`, `maize`).
   - If crop hint is absent, attached explicit provisional warning disclaiming unconfirmed host crop identity.
   - Preserved non-chemical advice on rejected scans.
3. **Regression Test Verification**:
   - **103/103 tests passed** across all backend and vision suites with 0 regressions.
   - End-to-end multi-agent orchestrator workflows verified on staging.

---

## 2. Head-to-Head A/B/C Model Comparison Matrix

### A. Sealed PlantDoc Test Set ($N=99$, In-the-Wild Field Benchmark)

| Metric | Experiment A (Baseline) | Experiment B (PV Aug) | Experiment C (Candidate) | Gain (C vs Baseline) |
| :--- | :---: | :---: | :---: | :---: |
| **Field Top-1 Accuracy** | 24.24% | 23.23% | **43.43%** | **+19.19% abs (+79.2% rel)** |
| **Field Macro-$F_1$** | 0.1486 | 0.1130 | **0.3744** | **+0.2258 abs (+152.0% rel)** |
| **Correct Field Detections** | 24 / 99 | 23 / 99 | **43 / 99** | **+19 real-world images** |
| **PlantVillage Test Acc ($N=3,621$)** | 98.56% | 98.18% | **95.91%** | 97.3% retention |
| **PlantVillage Test Macro-$F_1$** | 0.9805 | 0.9792 | **0.9557** | 97.5% retention |

### B. Validation Split Metrics ($N=3,829$)

| Metric | Baseline (Production) | Experiment C (Candidate) | Impact |
| :--- | :---: | :---: | :---: |
| **PlantDoc Val Accuracy ($N=208$)** | 21.63% | **50.00%** | **+28.37% abs (+131.2% rel)** |
| **PlantDoc Val Macro-$F_1$** | 0.1242 | **0.4529** | **+0.3287 abs (+264.6% rel)** |
| **Expected Calibration Error (ECE)** | 0.5314 | **0.2459** | **-53.7% calibration error** |
| **Brier Multi-Class Score** | 1.2503 | **0.7462** | **-40.3% error reduction** |
| **False Healthy Rate (Field Val)** | 4.1% (8 images) | **3.0% (6 images)** | Reduced under-diagnosis risk |

---

## 3. Real-World Limitations & Ongoing OOD Constraints

> [!WARNING]
> While Experiment C represents a major leap forward over the baseline model, the following architectural and empirical limitations remain and must be accounted for in production operations:

1. **Residual Field Error Rate (~50% to 56%)**:
   - Even with domain-balanced training, real-world farm photography contains complex noise, cluttered foliage, non-uniform sunlight, and multi-disease co-infections.
   - Unassisted raw top-1 predictions still fail on ~50% of field validation images if confidence thresholding is bypassed.
   - **Mitigation**: Confidence thresholding ($\tau = 0.60$) and expert referral flags (`requires_expert=True`) must remain mandatory.
2. **Out-of-Distribution Closed-Set Softmax Fallacy**:
   - Because MobileNetV3-Small outputs a 17-class closed-set softmax probability vector, uploading non-target foliage (e.g. apple, grape, peach) without an explicit crop hint will force an in-scope classification $\ge 0.60$ in 68% of cases.
   - **Mitigation**: The new UI prompt requires or strongly encourages crop identification before submission.
3. **Severe Lesion Overlap in Early Disease Stages**:
   - Morphological similarities between early *Alternaria solani* (Early Blight) and *Septoria lycopersici* remain challenging on low-resolution mobile sensors.

---

## 4. Production Checkpoint Backup Verification

Because this repository is an extracted codebase and not a Git repository, Git cannot recover overwritten files. The physical backup is verified:

* **Original Checkpoint**: [`ml/models/mobilenetv3_plantdisease_best.pth`](file:///Users/ishansharma2702/Downloads/Krishi-Ai-main/ml/models/mobilenetv3_plantdisease_best.pth)
  * Size: `6,272,915 bytes`
  * SHA-256: `ee4052944e659cecada4f8419101ec39611914a48604d3bea014f0c1c5befe76`
* **Backup Checkpoint**: [`ml/models/mobilenetv3_plantdisease_best.production_backup_20261019.pth`](file:///Users/ishansharma2702/Downloads/Krishi-Ai-main/ml/models/mobilenetv3_plantdisease_best.production_backup_20261019.pth)
  * Size: `6,272,915 bytes`
  * SHA-256: `ee4052944e659cecada4f8419101ec39611914a48604d3bea014f0c1c5befe76`
  * Checksum Match: **100% IDENTICAL**

---

## 5. Deployment Procedures & Instructions (Awaiting Approval)

Once approved by the user, deployment proceeds in two simple steps:

### Option A: Local Production Promotion

Promote the staging artifact to become the active production checkpoint:

```bash
# 1. Copy staging checkpoint to active production name
cp ml/models/mobilenetv3_plantdisease_staging.pth ml/models/mobilenetv3_plantdisease_best.pth

# 2. Verify SHA-256 of the newly promoted checkpoint
shasum -a 256 ml/models/mobilenetv3_plantdisease_best.pth
# Expected: 9d931b2b4a9cd385002b8dff2823a4b92b672739483ec73167b07baae65f80b9

# 3. Restart backend service
```

### Option B: Hugging Face Model Hub Deployment

To upload Experiment C to Hugging Face Model Hub (`Dipxssi/krishiai-mobilenetv3`):

```bash
# 1. Export your Hugging Face write token:
export HF_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 2. Execute upload command:
backend/.venv/bin/python ml/src/upload_to_huggingface.py \
  --repo-id "Dipxssi/krishiai-mobilenetv3" \
  --checkpoint ml/models/mobilenetv3_plantdisease_staging.pth
```

* **Files Uploaded**:
  1. `mobilenetv3_plantdisease_best.pth` (The Experiment C weights)
  2. `config.json` (17-class metadata, normalization constants, and class mapping)
  3. `README.md` (Updated model card detailing PlantVillage + PlantDoc benchmarks, calibration, and safety disclaimers)

---

## 6. Immediate Rollback Instructions

If any unforeseen anomaly, latency spike, or operational regression occurs:

```bash
# Step 1: Restore the original baseline checkpoint immediately
cp ml/models/mobilenetv3_plantdisease_best.production_backup_20261019.pth ml/models/mobilenetv3_plantdisease_best.pth

# Step 2: Invalidate model cache / restart backend
backend/.venv/bin/python -c "from app.vision.mobilenetv3_service import clear_mobilenetv3_cache; clear_mobilenetv3_cache(); print('Cache cleared')"

# Step 3: Verify restoration
backend/.venv/bin/python -c "
import hashlib
with open('ml/models/mobilenetv3_plantdisease_best.pth', 'rb') as f:
    h = hashlib.sha256(f.read()).hexdigest()
assert h == 'ee4052944e659cecada4f8419101ec39611914a48604d3bea014f0c1c5befe76', 'Rollback verification failed!'
print('Rollback to baseline confirmed!')
"
```
