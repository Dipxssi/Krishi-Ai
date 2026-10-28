# Pilot Test Checkpoint Evaluation Benchmark Report

**Evaluation Timestamp**: 2026-10-19 13:02:28  
**Checkpoint**: `best_model.pth` (5.98 MB, 1,535,281 parameters)  
**Evaluation Device**: Apple Silicon MPS (`mps`)  

---

## 1. Executive Summary & Field Generalization

| Evaluation Split | Sample Count ($N$) | Accuracy | Macro-Precision | Macro-Recall | Macro-F1 | Weighted-F1 | Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **PlantDoc Test Benchmark** | **99** | **3.03%** | 0.0024 | 0.0577 | **0.0046** | 0.0024 | 122.72 ms |
| **PlantVillage Test** | **3621** | **2.15%** | 0.0601 | 0.0595 | **0.0038** | 0.0020 | 4.29 ms |
| **PlantDoc OOD Test** | **125** | *Rejection: 23.20%* | - | - | *False Acceptance: 76.80%* | - | - |

* **Laboratory-to-Field Domain Gap**:
  * Accuracy Delta: **-0.88%** (PlantVillage: 2.15% vs PlantDoc: 3.03%)
  * Macro-F1 Delta: **-0.0008** (PlantVillage: 0.0038 vs PlantDoc: 0.0046)

---

## 2. PlantDoc Test Per-Class Performance Breakdown

| Class Index | Target Class Name | Support | Correct | Precision | Recall | F1-Score |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| `00` | Corn Gray Leaf Spot | 4 | 3 | 0.0309 | 0.7500 | 0.0594 |
| `01` | Corn Common Rust | 10 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `02` | Corn Northern Leaf Blight | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `03` | Corn Healthy | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `04` | Potato Early Blight | 8 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `05` | Potato Late Blight | 8 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `06` | Potato Healthy | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `07` | Tomato Bacterial Spot | 9 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `08` | Tomato Early Blight | 9 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `09` | Tomato Late Blight | 10 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `10` | Tomato Leaf Mold | 6 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `11` | Tomato Septoria Leaf Spot | 11 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `12` | Tomato Two-spotted Spider Mite | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `13` | Tomato Target Spot | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `14` | Tomato Yellow Leaf Curl Virus | 6 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `15` | Tomato Mosaic Virus | 10 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `16` | Tomato Healthy | 8 | 0 | 0.0000 | 0.0000 | 0.0000 |

---

## 3. Operational Safety & Confidence Gating ($	au=0.6$)

* **PlantDoc In-Scope Accepted Accuracy**: **1.22%** (Rejection rate: 17.17%)
* **PlantVillage Accepted Accuracy**: **1.94%** (Rejection rate: 5.91%)
* **OOD False Acceptance Rate on Non-Target Crops**: **76.80%** (Median confidence: 0.8083)
