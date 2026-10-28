# KrishiAI Dataset Audit & Class Mapping Manifest Report

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
  * **Test Leakage Exclusions**: 9 exact duplicates of PlantDoc test images were identified and removed.
  * **Near-Duplicate Test Exclusions**: 4 near-duplicates of test images were identified and removed.
  * **Intra-Train Exact Duplicates**: 1 duplicate images removed within train set.
  * **PlantVillage Exact Matches**: 0 duplicate images.
  * **Ambiguous Corn Blight Excluded**: 179 images.
  * **Out-of-Scope Non-Target Images Excluded**: 1105 images.
* **Usable Clean PlantDoc Train Images**: **1038** images.

---

## 3. Split Sizes & Partition Manifests

| Dataset Split | PlantVillage Samples | PlantDoc Samples | Combined Total | Primary Role |
| :--- | :---: | :---: | :---: | :--- |
| **Training Split** | 16,908 | 830 | **17,738** | Supervised model training |
| **Validation Split** | 3,621 | 208 | **3,829** | Model selection & early stopping |
| **PlantVillage Test** | 3,621 | 0 | **3,621** | In-distribution evaluation |
| **PlantDoc Test (In-Scope)** | 0 | 99 | **99** | **Untouched field generalization benchmark** |
| **PlantDoc Test (OOD)** | 0 | 125 | **125** | Out-of-distribution rejection audit |

---

## 4. Class Distribution Across Usable Splits

| Class Index | Display Name | PlantVillage Train | PlantDoc Train | PlantDoc Val | PlantDoc Test |
| :---: | :--- | :---: | :---: | :---: | :---: |
| `00` | Corn Gray Leaf Spot | 360 | 50 | 12 | 4 |
| `01` | Corn Common Rust | 834 | 85 | 21 | 10 |
| `02` | Corn Northern Leaf Blight | 690 | 0 | 0 | 0 |
| `03` | Corn Healthy | 812 | 0 | 0 | 0 |
| `04` | Potato Early Blight | 700 | 84 | 21 | 8 |
| `05` | Potato Late Blight | 700 | 76 | 19 | 8 |
| `06` | Potato Healthy | 104 | 0 | 0 | 0 |
| `07` | Tomato Bacterial Spot | 1,491 | 80 | 20 | 9 |
| `08` | Tomato Early Blight | 700 | 62 | 16 | 9 |
| `09` | Tomato Late Blight | 1,330 | 79 | 20 | 10 |
| `10` | Tomato Leaf Mold | 669 | 68 | 17 | 6 |
| `11` | Tomato Septoria Leaf Spot | 1,240 | 110 | 28 | 11 |
| `12` | Tomato Two-spotted Spider Mite | 1,174 | 2 | 0 | 0 |
| `13` | Tomato Target Spot | 982 | 0 | 0 | 0 |
| `14` | Tomato Yellow Leaf Curl Virus | 3,751 | 55 | 14 | 6 |
| `15` | Tomato Mosaic Virus | 260 | 35 | 9 | 10 |
| `16` | Tomato Healthy | 1,111 | 44 | 11 | 8 |
