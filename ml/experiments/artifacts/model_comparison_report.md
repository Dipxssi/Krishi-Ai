# KrishiAI MobileNetV3 Field Generalization: Controlled Experiment Report

**Date**: 2026-10-19  
**Evaluation Scope**: 17 Target Crop-Disease Classes in Tomato, Potato, and Corn (Maize)  
**Evaluated Hardware**: Apple Silicon M5 GPU (`mps` acceleration)  
**Untouched Field Benchmark**: Official PlantDoc Test Split ($N=99$ clean in-scope samples, 0% leakage)  

---

## 1. Executive Summary & Comparative Matrix

| Model Experiment | Training Set | Sampling Strategy | PlantDoc Field Acc ($N=99$) | PlantDoc Field Macro-F1 | PlantVillage Test Acc ($N=3,621$) | PlantVillage Macro-F1 | Domain Gap ($\Delta$ F1) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Experiment A (Baseline)** | PlantVillage (Studio) | Uniform | **24.24%** | **0.1486** | **98.56%** | **0.9805** | 0.8319 |
| **Experiment B (PV Augmented)** | PlantVillage (Studio) | Field Augmentation | **23.23%** | **0.1130** | **98.18%** | **0.9792** | 0.8662 |
| **Experiment C (Combined PV+PD)** | PlantVillage + PlantDoc | Domain-Balanced (35% Field) | **43.43%** | **0.3744** | **95.91%** | **0.9557** | 0.5813 |

---

## 2. Key Findings & Insights

1. **Synthetic / Studio Augmentation Alone Fails to Bridge Field Gap**:
   - Experiment B trained strictly on PlantVillage with aggressive photometric, affine, and scale augmentations achieved **23.23%** accuracy and **0.1130** macro-F1 on PlantDoc.
   - This empirically demonstrates that laboratory leaves on clean backdrops do not provide the convolutional representations needed for real-world foliage, soil backgrounds, and complex lesion textures.
2. **Impact of Domain-Balanced Field Data Mixing (Experiment C)**:
   - Experiment C achieved **43.43%** accuracy (**+19.19%** vs Baseline) and **0.3744** Macro-F1 (**+0.2258** vs Baseline).
   - In-distribution PlantVillage performance remained rock-solid at **95.91%** accuracy and **0.9557** Macro-F1.

---

## 3. PlantDoc Test Per-Class Head-to-Head Comparison

| Target Class Name | Support | Exp A (Baseline) F1 | Exp B (PV Aug) F1 | Exp C (Combined) F1 | Net Gain (C vs Baseline) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Corn Gray Leaf Spot | 4 | 0.1429 | 0.2000 | 0.2857 | **+0.1428** |
| Corn Common Rust | 10 | 0.4000 | 0.1538 | 0.7273 | **+0.3273** |
| Corn Northern Leaf Blight | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Corn Healthy | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Potato Early Blight | 8 | 0.0000 | 0.2000 | 0.4444 | **+0.4444** |
| Potato Late Blight | 8 | 0.2222 | 0.0000 | 0.2000 | **-0.0222** |
| Potato Healthy | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Tomato Bacterial Spot | 9 | 0.0000 | 0.0000 | 0.2105 | **+0.2105** |
| Tomato Early Blight | 9 | 0.3158 | 0.3500 | 0.3077 | **-0.0081** |
| Tomato Late Blight | 10 | 0.4571 | 0.4571 | 0.5217 | **+0.0646** |
| Tomato Leaf Mold | 6 | 0.0000 | 0.0000 | 0.3333 | **+0.3333** |
| Tomato Septoria Leaf Spot | 11 | 0.3200 | 0.3333 | 0.6667 | **+0.3467** |
| Tomato Two-spotted Spider Mite | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Tomato Target Spot | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Tomato Yellow Leaf Curl Virus | 6 | 0.2222 | 0.0000 | 0.4000 | **+0.1778** |
| Tomato Mosaic Virus | 10 | 0.0000 | 0.0000 | 0.1538 | **+0.1538** |
| Tomato Healthy | 8 | 0.0000 | 0.0000 | 0.6154 | **+0.6154** |

---

## 4. Operational Readiness & Reversible Integration Plan

* **Best Performing Candidate**: **Experiment C (Combined PV + PD)**
* **Candidate Checkpoint Location**: `ml/experiments/checkpoints/exp_c_combined/best_model.pth`
* **Current Production Integrity**: The deployed model checkpoint ([ml/models/mobilenetv3_plantdisease_best.pth](file:///Users/ishansharma2702/Downloads/Krishi-Ai-main/ml/models/mobilenetv3_plantdisease_best.pth)), backend endpoints, and Hugging Face repository remain **100% untouched**.

### Reversible Deployment Steps (For Future Approval):
1. **Local Checkpoint Promotion**:
   ```bash
   cp ml/experiments/checkpoints/exp_c_combined/best_model.pth ml/models/mobilenetv3_plantdisease_best.pth
   ```
2. **Backend Regression Testing**:
   ```bash
   backend/.venv/bin/pytest backend/tests/test_mobilenetv3_endpoint.py backend/tests/test_mobilenetv3_orchestrator.py
   ```
3. **Hugging Face Hub Update (Only upon user command)**:
   ```bash
   backend/.venv/bin/python ml/src/upload_to_huggingface.py --repo-id "Ishan2702/krishiai-mobilenetv3"
   ```
4. **Instant Rollback (If needed)**:
   Restore the preserved baseline checkpoint:
   ```bash
   git checkout ml/models/mobilenetv3_plantdisease_best.pth
   ```
