# Experiment A - Baseline MobileNetV3 Evaluation Benchmark Report

**Evaluation Timestamp**: 2026-10-19 12:59:33  
**Checkpoint**: `mobilenetv3_plantdisease_best.pth` (5.98 MB, 1,535,281 parameters)  
**Evaluation Device**: Apple Silicon MPS (`mps`)  

---

## 1. Executive Summary & Field Generalization

| Evaluation Split | Sample Count ($N$) | Accuracy | Macro-Precision | Macro-Recall | Macro-F1 | Weighted-F1 | Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **PlantDoc Test Benchmark** | **99** | **24.24%** | 0.2033 | 0.1909 | **0.1486** | 0.1880 | 122.03 ms |
| **PlantVillage Test** | **3621** | **98.56%** | 0.9797 | 0.9814 | **0.9805** | 0.9857 | 4.35 ms |
| **PlantDoc OOD Test** | **125** | *Rejection: 32.00%* | - | - | *False Acceptance: 68.00%* | - | - |

* **Laboratory-to-Field Domain Gap**:
  * Accuracy Delta: **74.32%** (PlantVillage: 98.56% vs PlantDoc: 24.24%)
  * Macro-F1 Delta: **0.8319** (PlantVillage: 0.9805 vs PlantDoc: 0.1486)

---

## 2. PlantDoc Test Per-Class Performance Breakdown

| Class Index | Target Class Name | Support | Correct | Precision | Recall | F1-Score |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| `00` | Corn Gray Leaf Spot | 4 | 1 | 0.1000 | 0.2500 | 0.1429 |
| `01` | Corn Common Rust | 10 | 3 | 0.6000 | 0.3000 | 0.4000 |
| `02` | Corn Northern Leaf Blight | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `03` | Corn Healthy | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `04` | Potato Early Blight | 8 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `05` | Potato Late Blight | 8 | 1 | 1.0000 | 0.1250 | 0.2222 |
| `06` | Potato Healthy | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `07` | Tomato Bacterial Spot | 9 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `08` | Tomato Early Blight | 9 | 6 | 0.2069 | 0.6667 | 0.3158 |
| `09` | Tomato Late Blight | 10 | 8 | 0.3200 | 0.8000 | 0.4571 |
| `10` | Tomato Leaf Mold | 6 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `11` | Tomato Septoria Leaf Spot | 11 | 4 | 0.2857 | 0.3636 | 0.3200 |
| `12` | Tomato Two-spotted Spider Mite | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `13` | Tomato Target Spot | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `14` | Tomato Yellow Leaf Curl Virus | 6 | 1 | 0.3333 | 0.1667 | 0.2222 |
| `15` | Tomato Mosaic Virus | 10 | 0 | 0.0000 | 0.0000 | 0.0000 |
| `16` | Tomato Healthy | 8 | 0 | 0.0000 | 0.0000 | 0.0000 |

---

## 3. Operational Safety & Confidence Gating ($	au=0.6$)

* **PlantDoc In-Scope Accepted Accuracy**: **24.64%** (Rejection rate: 30.30%)
* **PlantVillage Accepted Accuracy**: **98.89%** (Rejection rate: 0.88%)
* **OOD False Acceptance Rate on Non-Target Crops**: **68.00%** (Median confidence: 0.7991)
