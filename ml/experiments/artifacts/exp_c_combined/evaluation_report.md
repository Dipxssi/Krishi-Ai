# Experiment C - Combined PlantVillage + PlantDoc Evaluation Benchmark Report

**Evaluation Timestamp**: 2026-10-19 13:30:21  
**Checkpoint**: `best_model.pth` (5.98 MB, 1,535,281 parameters)  
**Evaluation Device**: Apple Silicon MPS (`mps`)  

---

## 1. Executive Summary & Field Generalization

| Evaluation Split | Sample Count ($N$) | Accuracy | Macro-Precision | Macro-Recall | Macro-F1 | Weighted-F1 | Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **PlantDoc Test Benchmark** | **99** | **43.43%** | 0.4044 | 0.3792 | **0.3744** | 0.4207 | 121.22 ms |
| **PlantVillage Test** | **3621** | **95.91%** | 0.9489 | 0.9643 | **0.9557** | 0.9595 | 4.3 ms |
| **PlantDoc OOD Test** | **125** | *Rejection: 31.20%* | - | - | *False Acceptance: 68.80%* | - | - |

* **Laboratory-to-Field Domain Gap**:
  * Accuracy Delta: **52.48%** (PlantVillage: 95.91% vs PlantDoc: 43.43%)
  * Macro-F1 Delta: **0.5813** (PlantVillage: 0.9557 vs PlantDoc: 0.3744)

---

## 2. PlantDoc Test Per-Class Performance Breakdown

| Class Index | Target Class Name | Support | Correct | Precision | Recall | F1-Score |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| `00` | Corn Gray Leaf Spot | 4 | 1 | 0.3333 | 0.2500 | 0.2857 |
| `01` | Corn Common Rust | 10 | 8 | 0.6667 | 0.8000 | 0.7273 |
| `02` | Corn Northern Leaf Blight | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `03` | Corn Healthy | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `04` | Potato Early Blight | 8 | 4 | 0.4000 | 0.5000 | 0.4444 |
| `05` | Potato Late Blight | 8 | 2 | 0.1667 | 0.2500 | 0.2000 |
| `06` | Potato Healthy | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `07` | Tomato Bacterial Spot | 9 | 2 | 0.2000 | 0.2222 | 0.2105 |
| `08` | Tomato Early Blight | 9 | 2 | 0.5000 | 0.2222 | 0.3077 |
| `09` | Tomato Late Blight | 10 | 6 | 0.4615 | 0.6000 | 0.5217 |
| `10` | Tomato Leaf Mold | 6 | 2 | 0.3333 | 0.3333 | 0.3333 |
| `11` | Tomato Septoria Leaf Spot | 11 | 9 | 0.5625 | 0.8182 | 0.6667 |
| `12` | Tomato Two-spotted Spider Mite | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `13` | Tomato Target Spot | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `14` | Tomato Yellow Leaf Curl Virus | 6 | 2 | 0.5000 | 0.3333 | 0.4000 |
| `15` | Tomato Mosaic Virus | 10 | 1 | 0.3333 | 0.1000 | 0.1538 |
| `16` | Tomato Healthy | 8 | 4 | 0.8000 | 0.5000 | 0.6154 |

---

## 3. Operational Safety & Confidence Gating ($	au=0.6$)

* **PlantDoc In-Scope Accepted Accuracy**: **52.00%** (Rejection rate: 24.24%)
* **PlantVillage Accepted Accuracy**: **97.59%** (Rejection rate: 3.67%)
* **OOD False Acceptance Rate on Non-Target Crops**: **68.80%** (Median confidence: 0.7876)
