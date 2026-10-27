# Experiment B - PlantVillage Augmented Evaluation Benchmark Report

**Evaluation Timestamp**: 2026-10-19 13:14:44  
**Checkpoint**: `best_model.pth` (5.98 MB, 1,535,281 parameters)  
**Evaluation Device**: Apple Silicon MPS (`mps`)  

---

## 1. Executive Summary & Field Generalization

| Evaluation Split | Sample Count ($N$) | Accuracy | Macro-Precision | Macro-Recall | Macro-F1 | Weighted-F1 | Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **PlantDoc Test Benchmark** | **99** | **23.23%** | 0.1208 | 0.1778 | **0.1130** | 0.1548 | 122.71 ms |
| **PlantVillage Test** | **3621** | **98.18%** | 0.9791 | 0.9797 | **0.9792** | 0.9818 | 4.31 ms |
| **PlantDoc OOD Test** | **125** | *Rejection: 27.20%* | - | - | *False Acceptance: 72.80%* | - | - |

* **Laboratory-to-Field Domain Gap**:
  * Accuracy Delta: **74.95%** (PlantVillage: 98.18% vs PlantDoc: 23.23%)
  * Macro-F1 Delta: **0.8662** (PlantVillage: 0.9792 vs PlantDoc: 0.1130)

---

## 2. PlantDoc Test Per-Class Performance Breakdown

| Class Index | Target Class Name | Support | Correct | Precision | Recall | F1-Score |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| `00` | Corn Gray Leaf Spot | 4 | 2 | 0.1250 | 0.5000 | 0.2000 |
| `01` | Corn Common Rust | 10 | 1 | 0.3333 | 0.1000 | 0.1538 |
| `02` | Corn Northern Leaf Blight | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `03` | Corn Healthy | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `04` | Potato Early Blight | 8 | 1 | 0.5000 | 0.1250 | 0.2000 |
| `05` | Potato Late Blight | 8 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `06` | Potato Healthy | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `07` | Tomato Bacterial Spot | 9 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `08` | Tomato Early Blight | 9 | 7 | 0.2258 | 0.7778 | 0.3500 |
| `09` | Tomato Late Blight | 10 | 8 | 0.3200 | 0.8000 | 0.4571 |
| `10` | Tomato Leaf Mold | 6 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `11` | Tomato Septoria Leaf Spot | 11 | 4 | 0.3077 | 0.3636 | 0.3333 |
| `12` | Tomato Two-spotted Spider Mite | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `13` | Tomato Target Spot | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `14` | Tomato Yellow Leaf Curl Virus | 6 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `15` | Tomato Mosaic Virus | 10 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `16` | Tomato Healthy | 8 | 0 | 0.0000 | 0.0000 | 0.0000 |

---

## 3. Operational Safety & Confidence Gating ($	au=0.6$)

* **PlantDoc In-Scope Accepted Accuracy**: **26.32%** (Rejection rate: 23.23%)
* **PlantVillage Accepted Accuracy**: **98.60%** (Rejection rate: 1.10%)
* **OOD False Acceptance Rate on Non-Target Crops**: **72.80%** (Median confidence: 0.8217)
